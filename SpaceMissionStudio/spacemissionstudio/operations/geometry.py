#
#  SpaceMissionStudio
#
#  Licensor: 0h3xn4 (https://github.com/0h3xn4)
#
#  Licensed under the EUPL
#
#  SPDX-License-Identifier: EUPL-1.2
#
#  The European Union Public Licence v. 1.2 is in the files LICENSE
#  (English) and LICENSE.de (German) of the SpaceMissionStudio folder and
#  of every package. Third-party components, each under its own licence,
#  are listed in THIRD_PARTY_NOTICES.
#
#
#
#
"""The planner's geometry: each spacecraft's position, velocity and
sunlight, the Earth's orientation and the Sun, on one time grid over the
horizon (design 2.4, decisions O-03 and O-04).

Three sources:

* ``run``: a finished run's recorded series, interpolated onto the grid;
  the stations' recorded access series (elevation, azimuth, range) are
  kept, so passes come from the existing access analysis;
* ``propagation``: the scenario made orbit-only and run by the existing
  service from its epoch to the horizon's end, then read as ``run``;
* ``analytic``: Kepler with J2's secular rates from the mean elements
  (the propagator of ``engine.scenario_checks.predict_passes``), the
  Earth's rotation as a run would have it (ERFA's IAU 2006/2000A when the
  IERS files cover the horizon, else the full IAU_EARTH model), ERFA's Sun
  and a cylindrical shadow.

Simulation time throughout (TDB seconds since the epoch, O-05).
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field

import erfa
import numpy as np

from .. import constants
from ..engine import geodesy, time_system
from .timebase import TimeBase

#: IAU_EARTH's pole (the IAU WGCCRE report, as NAIF's pck00010.tpc): right
#: ascension and declination at J2000 and their rates per Julian century.
IAU_EARTH_POLE_RA_DEG = (0.0, -0.641)  # [deg], [deg/century]
IAU_EARTH_POLE_DEC_DEG = (90.0, -0.557)  # [deg], [deg/century]
_SUN_GRID_S = 3600.0  # [s] the Sun's direction is computed hourly and interpolated (it moves ~0.04 deg/h)


class GeometryError(Exception):
    """The geometry cannot be built (a missing series, no orbit)."""


@dataclass
class Track:
    """One spacecraft on the grid, from the Earth's centre in the inertial
    frame (Basilisk's N, EME2000)."""

    name: str
    position_n: np.ndarray  # (n, 3) [m]
    velocity_n: np.ndarray  # (n, 3) [m/s]
    sunlight: np.ndarray  # (n,) [-] 1 in sunlight, 0 in umbra


@dataclass
class StationView:
    """A station's view of a spacecraft on the grid."""

    elevation_deg: np.ndarray  # (n,) [deg] geodetic
    azimuth_deg: np.ndarray  # (n,) [deg] from north, east positive
    range_m: np.ndarray  # (n,) [m]


@dataclass
class PlanningGeometry:
    epoch_utc: str
    source: str
    time_s: np.ndarray  # (n,) [s] simulation time
    dcm_pn: np.ndarray  # (n, 3, 3) [-] inertial to Earth-fixed
    sun_n: np.ndarray  # (n, 3) [m] Earth's centre to the Sun
    tracks: dict  # spacecraft name -> Track
    views: dict = field(default_factory=dict)  # (station, spacecraft) -> StationView, from a run's access series
    notes: list = field(default_factory=list)

    @property
    def step_s(self) -> float:
        return float(self.time_s[1] - self.time_s[0]) if len(self.time_s) > 1 else 0.0

    def site(self, latitude_deg: float, longitude_deg: float, altitude_m: float = 0.0):
        """A ground point's inertial position (n, 3) [m] and its local up,
        north and east (n, 3) in the inertial frame (WGS-84, geodetic)."""
        lat, lon = math.radians(latitude_deg), math.radians(longitude_deg)
        r_p = geodesy.geodetic_to_pcpf(lat, lon, altitude_m)
        up_p = np.array([math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat)])
        north_p = np.array([-math.sin(lat) * math.cos(lon), -math.sin(lat) * math.sin(lon), math.cos(lat)])
        east_p = np.array([-math.sin(lon), math.cos(lon), 0.0])
        to_n = np.transpose(self.dcm_pn, (0, 2, 1))
        return tuple(np.einsum("nij,j->ni", to_n, v) for v in (r_p, up_p, north_p, east_p))

    def view(self, spacecraft: str, latitude_deg: float, longitude_deg: float, altitude_m: float = 0.0) -> StationView:
        """Elevation, azimuth and range of ``spacecraft`` from a ground point."""
        site, up, north, east = self.site(latitude_deg, longitude_deg, altitude_m)
        line = self.tracks[spacecraft].position_n - site
        distance = np.linalg.norm(line, axis=1)
        unit = line / distance[:, None]
        elevation = np.degrees(np.arcsin(np.clip(np.einsum("ni,ni->n", unit, up), -1.0, 1.0)))
        azimuth = np.degrees(np.arctan2(np.einsum("ni,ni->n", unit, east), np.einsum("ni,ni->n", unit, north))) % 360.0
        return StationView(elevation, azimuth, distance)

    def sun_elevation_deg(self, latitude_deg: float, longitude_deg: float, altitude_m: float = 0.0) -> np.ndarray:
        """The Sun's elevation [deg] at a ground point (geodetic horizon, no
        refraction)."""
        site, up, _north, _east = self.site(latitude_deg, longitude_deg, altitude_m)
        line = self.sun_n - site
        unit = line / np.linalg.norm(line, axis=1)[:, None]
        return np.degrees(np.arcsin(np.clip(np.einsum("ni,ni->n", unit, up), -1.0, 1.0)))


def grid(start_s: float, end_s: float, step_s: float) -> np.ndarray:
    """``start_s`` every ``step_s`` up to ``end_s`` [s]: a uniform grid,
    whose last sample is less than a step before ``end_s`` when the span is
    not a whole number of steps (TDB runs a few microseconds a day ahead of
    UTC, so a UTC horizon never is exactly)."""
    count = max(2, int(math.floor((end_s - start_s) / step_s + 1e-6)) + 1)
    return start_s + step_s * np.arange(count)


def _tdb_centuries_and_days(epoch_utc, t: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    seconds = time_system.tdb_seconds_past_j2000(epoch_utc) + t  # [s TDB past J2000]
    return seconds / (86400.0 * 36525.0), seconds / 86400.0


def iau_earth_dcm(epoch_utc, t) -> np.ndarray:
    """``[PN]`` (n, 3, 3) of IAU_EARTH at simulation times ``t``: the pole's
    right ascension and declination with their rates and the prime
    meridian (pck00010), ``[PN] = R3(W) R1(90 - dec) R3(90 + ra)``."""
    t = np.asarray(t, dtype=float)
    centuries, days = _tdb_centuries_and_days(epoch_utc, t)
    ra = np.radians(IAU_EARTH_POLE_RA_DEG[0] + IAU_EARTH_POLE_RA_DEG[1] * centuries)
    dec = np.radians(IAU_EARTH_POLE_DEC_DEG[0] + IAU_EARTH_POLE_DEC_DEG[1] * centuries)
    w = np.radians(constants.IAU_EARTH_PRIME_MERIDIAN_DEG + constants.IAU_EARTH_PRIME_MERIDIAN_RATE_DEG_DAY * days)
    return _r3(w) @ _r1(np.pi / 2.0 - dec) @ _r3(np.pi / 2.0 + ra)


def itrs_dcm(epoch_utc, t) -> np.ndarray:
    """``[PN]`` (n, 3, 3) from the GCRS to the ITRS (ERFA ``c2t06a``, IAU
    2006/2000A), with UT1 taken as UTC (|UT1 - UTC| < 0.9 s, under 0.4 km
    at the equator) and no polar motion (under 15 m): what a run in
    ITRF93 uses, without its IERS data. The GCRS and EME2000 differ by the
    23 mas frame bias, left out."""
    t = np.asarray(t, dtype=float)
    seconds = time_system.tdb_seconds_past_j2000(epoch_utc) + t  # [s TDB ~ TT past J2000]
    leap = time_system.tai_minus_utc_s(epoch_utc)  # [s] no leap second is announced after 2017
    utc_seconds = seconds - time_system.TT_MINUS_TAI_S - leap  # [s]
    zeros = np.zeros(len(t))
    return np.asarray(erfa.c2t06a(np.full(len(t), 2451545.0), seconds / 86400.0,
                                  np.full(len(t), 2451545.0), utc_seconds / 86400.0, zeros, zeros), dtype=float)


def earth_dcm(epoch_utc, t, end_s: float | None = None) -> np.ndarray:
    """The Earth's orientation a run would use over ``t``: the ITRS
    (:func:`itrs_dcm`) when the IERS Earth orientation files cover it, as a
    run then flies in ITRF93; IAU_EARTH otherwise (engine.service)."""
    from datetime import timedelta

    from ..engine import earth_orientation
    from .timebase import _naive

    t = np.asarray(t, dtype=float)
    start = _naive(epoch_utc)
    end = start + timedelta(seconds=float(end_s if end_s is not None else (t.max() if len(t) else 0.0)))
    if earth_orientation.covering(earth_orientation.installed(), start, end):
        return itrs_dcm(epoch_utc, t)
    return iau_earth_dcm(epoch_utc, t)


def _r1(angle: np.ndarray) -> np.ndarray:
    c, s = np.cos(angle), np.sin(angle)
    out = np.zeros((len(angle), 3, 3))
    out[:, 0, 0] = 1.0
    out[:, 1, 1], out[:, 1, 2], out[:, 2, 1], out[:, 2, 2] = c, s, -s, c
    return out


def _r3(angle: np.ndarray) -> np.ndarray:
    c, s = np.cos(angle), np.sin(angle)
    out = np.zeros((len(angle), 3, 3))
    out[:, 2, 2] = 1.0
    out[:, 0, 0], out[:, 0, 1], out[:, 1, 0], out[:, 1, 1] = c, s, -s, c
    return out


def erfa_sun(epoch_utc, t) -> np.ndarray:
    """The Sun from the Earth's centre (n, 3) [m], ICRS axes (ERFA's
    ``epv00``: the Earth's heliocentric position), computed hourly and
    interpolated."""
    t = np.asarray(t, dtype=float)
    coarse = grid(float(t.min()), float(t.max()) + _SUN_GRID_S, _SUN_GRID_S) if len(t) else t
    seconds = time_system.tdb_seconds_past_j2000(epoch_utc) + coarse  # [s TDB past J2000]
    pvh, _pvb = erfa.epv00(np.full(len(seconds), 2451545.0), seconds / 86400.0)
    sun = -np.asarray(pvh["p"] if pvh.dtype.names else pvh[:, 0], dtype=float) * erfa.DAU  # [m]
    return np.column_stack([np.interp(t, coarse, sun[:, k]) for k in range(3)])


def cylindrical_sunlight(position_n: np.ndarray, sun_n: np.ndarray,
                         radius_m: float = constants.EARTH_EQUATORIAL_RADIUS_M) -> np.ndarray:
    """1 in sunlight, 0 in the Earth's cylindrical shadow."""
    unit = sun_n / np.linalg.norm(sun_n, axis=1)[:, None]
    along = np.einsum("ni,ni->n", position_n, unit)
    across = np.linalg.norm(position_n - along[:, None] * unit, axis=1)
    return np.where((along < 0.0) & (across < radius_m), 0.0, 1.0)


def analytic(scenario, start_s: float, end_s: float, step_s: float) -> PlanningGeometry:
    """Kepler + J2 secular from each spacecraft's mean elements (the
    osculating initial state mapped by ``engine.mean_elements``); the
    short-period terms are left out (a few km), so this source is for quick
    what-ifs and is marked in the plan's provenance (O-03)."""
    from Basilisk.utilities import orbitalMotion

    from ..engine import scenario_checks
    from ..engine.mean_elements import cl_mean_osc_map

    t = grid(start_s, end_s, step_s)
    dcm = earth_dcm(scenario.epoch_utc, t)
    sun = erfa_sun(scenario.epoch_utc, t)
    with_j2 = (scenario.gravity.central_body_degree or 0) >= 2
    tracks = {}
    for sc in scenario.spacecraft:
        elements = scenario_checks.orbit_elements(sc.orbit, scenario.epoch_utc)
        if elements is None:
            raise GeometryError(f"{sc.name}: its orbit has no elements the analytic geometry can propagate")
        if with_j2:
            a, e, i, raan, argp, mean_anomaly = elements
            osc, mean = orbitalMotion.ClassicElements(), orbitalMotion.ClassicElements()
            osc.a, osc.e, osc.i, osc.Omega, osc.omega = a, e, i, raan, argp
            osc.f = orbitalMotion.E2f(orbitalMotion.M2E(mean_anomaly, e), e)
            cl_mean_osc_map(constants.EARTH_EQUATORIAL_RADIUS_M, constants.EARTH_J2, osc, mean, -1)
            elements = (mean.a, mean.e, mean.i, mean.Omega, mean.omega,
                        orbitalMotion.E2M(orbitalMotion.f2E(mean.f, mean.e), mean.e))
        position = scenario_checks.kepler_j2_positions(elements, t, with_j2)
        half = 0.5  # [s] central difference for the velocity
        velocity = (scenario_checks.kepler_j2_positions(elements, t + half, with_j2)
                    - scenario_checks.kepler_j2_positions(elements, t - half, with_j2)) / (2.0 * half)
        tracks[sc.name] = Track(sc.name, position, velocity, cylindrical_sunlight(position, sun))
    return PlanningGeometry(scenario.epoch_utc, "analytic", t, dcm, sun, tracks,
                            notes=["analytic geometry: Kepler with J2's secular rates from the mean elements; "
                                   "no drag, no short-period terms, cylindrical shadow"])


def _interpolate(series, t: np.ndarray) -> np.ndarray:
    data = np.asarray(series.data, dtype=float)
    data = data.reshape(len(series.time_s), -1)
    return np.column_stack([np.interp(t, series.time_s, data[:, k]) for k in range(data.shape[1])])


def from_run(result, scenario, start_s: float, end_s: float, step_s: float, source: str = "run") -> PlanningGeometry:
    """The geometry from a run's recorded series (module docstring)."""
    series = result.series
    t = grid(start_s, end_s, step_s)
    notes = []
    first = [series[f"{sc.name}.position_N"] for sc in scenario.spacecraft if f"{sc.name}.position_N" in series]
    if not first:
        raise GeometryError("the run recorded no spacecraft position")
    covered = min(float(s.time_s[-1]) for s in first)
    if covered < end_s - 1e-3 or min(float(s.time_s[0]) for s in first) > start_s + 1e-3:
        raise GeometryError(f"the run covers {covered / 86400.0:.3f} days; the horizon needs it to "
                            f"{end_s / 86400.0:.3f} days after the epoch")
    body = scenario.gravity.central_body
    centre = series.get(f"ephemeris.{body}.position_N")
    centre_n = _interpolate(centre, t) if centre is not None else np.zeros((len(t), 3))
    orientation = series.get(f"ephemeris.{body}.dcm_PN")
    if orientation is not None:
        index = np.clip(np.searchsorted(orientation.time_s, t), 0, len(orientation.time_s) - 1)
        # the rotation is interpolated by re-orthonormalising a linear blend (a 10 s step turns it 0.04 deg)
        dcm = _interpolate(orientation, t).reshape(-1, 3, 3)
        u, _s, vt = np.linalg.svd(dcm)
        dcm = u @ vt
        del index
    else:
        dcm = earth_dcm(scenario.epoch_utc, t)
        notes.append("the run did not record the Earth's orientation: computed with ERFA or IAU_EARTH")
    sun_series = series.get("ephemeris.sun.position_N")
    if sun_series is not None:
        sun = _interpolate(sun_series, t) - centre_n
    else:
        sun = erfa_sun(scenario.epoch_utc, t)
        notes.append("the run did not record the Sun: ERFA's Sun used")
    tracks = {}
    for sc in scenario.spacecraft:
        position = series.get(f"{sc.name}.position_N")
        velocity = series.get(f"{sc.name}.velocity_N")
        if position is None or velocity is None:
            raise GeometryError(f"{sc.name}: the run recorded no position or velocity")
        r = _interpolate(position, t) - centre_n
        light = series.get(f"{sc.name}.eclipse.illumination_factor")
        sunlight = _interpolate(light, t)[:, 0] if light is not None else cylindrical_sunlight(r, sun)
        tracks[sc.name] = Track(sc.name, r, _interpolate(velocity, t), np.clip(sunlight, 0.0, 1.0))
    views = {}
    for gs in scenario.ground_stations:
        for sc in scenario.spacecraft:
            prefix = f"{gs.name}.access_to_{sc.name}"
            elevation, azimuth, distance = (series.get(f"{prefix}.{part}")
                                            for part in ("elevation", "azimuth", "slant_range"))
            if elevation is None or azimuth is None or distance is None:
                continue
            unwrapped = np.unwrap(np.asarray(azimuth.data, dtype=float).reshape(-1))
            views[(gs.name, sc.name)] = StationView(
                np.degrees(np.interp(t, elevation.time_s, np.asarray(elevation.data, dtype=float).reshape(-1))),
                np.degrees(np.interp(t, azimuth.time_s, unwrapped)) % 360.0,
                np.interp(t, distance.time_s, np.asarray(distance.data, dtype=float).reshape(-1)))
    return PlanningGeometry(scenario.epoch_utc, source, t, dcm, sun, tracks, views, notes)


def planning_scenario(scenario, end_s: float, step_s: float):
    """The scenario made orbit-only for the planning propagation: the force
    model, drag, maneuvers and orbit control kept; attitude, devices and
    analyses off (drag on facets, which needs the attitude, becomes drag on
    the spacecraft's ``drag_area_m2``); from the epoch to ``end_s`` [s],
    recorded every ``step_s``."""
    planned = copy.deepcopy(scenario)
    planned.simulation_mode = "orbit_only"
    planned.operations = None
    planned.monte_carlo.enabled = False
    planned.fsw_exports = []
    for sc in planned.spacecraft:
        sc.fsw_mode = None
        sc.fsw_params = {}
        for name in ("sensors", "actuators", "solar_arrays", "facets"):  # facet drag needs the attitude
            setattr(sc, name, [])
        for name in ("power", "rf_link", "comms_pointing", "data_handling", "model_analyses", "thermal",
                     "momentum_dumping", "magnetic_momentum_management", "navigation_error", "fuel_tank",
                     "optical_navigation", "landmark_navigation"):
            setattr(sc, name, None)
        sc.enable_gravity_gradient = False
    planned.sim_settings.duration_days = (end_s + step_s) / 86400.0  # a step past the end: TDB runs ahead of UTC
    planned.sim_settings.record_interval_s = step_s
    planned.sim_settings.dynamics_task_rate_s = step_s
    return planned


def propagate(scenario, end_s: float, step_s: float):
    """Run the planning propagation (the existing service) and return its
    results."""
    from ..engine.service import SimulationService
    from ..schema.command import runs_sequence

    planned = planning_scenario(scenario, end_s, step_s)
    planned.validate()
    service = SimulationService(planned, record_orientation=True)
    if runs_sequence(planned.mission_sequence):
        from ..engine.mission_engine import MissionEngine

        result, _summary = MissionEngine(planned, service=service).run()
    else:
        result = service.run()
    return result


def build(scenario, result=None) -> PlanningGeometry:
    """The geometry the scenario's ``operations`` section asks for: from
    ``result`` whenever a run is given (whatever the source says), else from
    a planning propagation or analytic; source ``run`` needs a run."""
    section = scenario.operations
    timebase = TimeBase(scenario.epoch_utc)
    start, end = (timebase.to_sim(moment) for moment in section.horizon_utc())
    step = section.geometry.step_s
    source = section.geometry.source
    if result is not None:
        return from_run(result, scenario, start, end, step, "run")
    if source == "run":
        raise GeometryError("geometry source 'run' needs a finished run of the scenario")
    if source == "analytic":
        return analytic(scenario, start, end, step)
    return from_run(propagate(scenario, end, step), scenario, start, end, step, "propagation")
