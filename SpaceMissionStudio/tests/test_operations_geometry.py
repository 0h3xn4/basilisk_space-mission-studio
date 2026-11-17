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
"""The planner's time base and geometry (operations.timebase,
operations.geometry; decisions O-03 to O-05): UTC in and out with leap
seconds, the three trajectory sources agreeing, the Earth's orientation
and the Sun checked against the run and an independent formula."""

import math

import numpy as np
import operations_fixtures as fixtures
import pytest

from spacemissionstudio.engine import time_system
from spacemissionstudio.operations import geometry
from spacemissionstudio.operations.timebase import TimeBase, format_utc


def test_utc_and_simulation_time_convert_with_leap_seconds_and_tdb():
    """Simulation time is TDB seconds since the epoch: a UTC day is 86400 s
    plus the TDB - TT change; across the 2016-12-31 leap second a UTC
    span gains one second; text rounds to the millisecond."""
    base = TimeBase("2030-01-01T08:30:00")
    day = base.to_sim("2030-01-02T08:30:00Z")
    assert day == pytest.approx(86400.0, abs=1e-3) and day != 86400.0
    assert base.texts([0.0, day]) == ["2030-01-01T08:30:00.000Z", "2030-01-02T08:30:00.000Z"]
    across = TimeBase("2016-12-31T23:59:00")
    assert across.to_sim("2017-01-01T00:01:00Z") == pytest.approx(121.0, abs=1e-3)
    assert across.text(121.0) == "2017-01-01T00:01:00.000Z"
    assert time_system.tai_minus_utc_s("2030-01-01T00:00:00") == 37.0
    from datetime import datetime

    assert format_utc(datetime(2030, 1, 1, 0, 0, 0, 999600)) == "2030-01-01T00:00:01.000Z"


def test_the_grid_is_uniform_within_the_horizon():
    """The grid starts on the horizon's start, keeps its step and ends at
    most a step before the horizon's end."""
    t = geometry.grid(5.0, 125.0, 10.0)
    assert t[0] == 5.0 and t[-1] == 125.0 and np.allclose(np.diff(t), 10.0)
    uneven = geometry.grid(0.0, 86400.00003, 10.0)
    assert uneven[-1] == 86400.0 and len(uneven) == 8641
    short = geometry.grid(0.0, 95.0, 10.0)
    assert short[-1] == 90.0


@pytest.fixture(scope="module")
def propagated():
    scenario = fixtures.scenario()
    end = 0.25 * 86400.0  # [s]
    result = geometry.propagate(scenario, end, 10.0)
    return scenario, result, geometry.from_run(result, scenario, 0.0, end, 10.0, "propagation")


def test_the_planning_propagation_keeps_the_force_model_and_records_what_the_planner_needs(propagated):
    """Orbit-only, the run records the Earth's orientation and the Sun
    (O-04); the planning scenario keeps drag and gravity, drops the
    attitude and devices."""
    scenario, result, _geo = propagated
    planned = geometry.planning_scenario(scenario, 3600.0, 10.0)
    assert planned.simulation_mode == "orbit_only" and planned.operations is None
    assert planned.gravity == scenario.gravity and planned.spacecraft[0].enable_drag == scenario.spacecraft[0].enable_drag
    assert planned.spacecraft[0].fsw_mode is None and planned.spacecraft[0].data_handling is None
    assert {"ephemeris.earth.dcm_PN", "ephemeris.sun.position_N", "eo-sat.position_N"} <= set(result.series)
    assert scenario.operations is not None  # the scenario itself is not changed


def test_station_views_from_the_access_analysis_match_the_geometry_s_own(propagated):
    """The recorded elevation, azimuth and range of berlin-gs equal the
    planner's computation from the same trajectory and Earth orientation
    (so passes from a run and from the planner agree)."""
    _scenario, _result, geo = propagated
    recorded = geo.views[("berlin-gs", "eo-sat")]
    computed = geo.view("eo-sat", 52.52, 13.405, 34.0)
    up = recorded.elevation_deg > -20.0
    assert np.max(np.abs(recorded.elevation_deg - computed.elevation_deg)[up]) < 1e-6
    assert np.max(np.abs(((recorded.azimuth_deg - computed.azimuth_deg) + 180.0) % 360.0 - 180.0)[up]) < 1e-5
    assert np.max(np.abs(recorded.range_m - computed.range_m)) < 1e-3


def test_the_earth_s_orientation_and_the_sun_without_a_run(propagated):
    """ERFA's IAU 2006/2000A rotation (UT1 = UTC, no polar motion) is
    within 30 m on the ground of the run's ITRF93 when IERS files are
    installed, IAU_EARTH within 15 km (O-04); ERFA's Sun within 0.001 deg
    of SPICE's."""
    scenario, _result, geo = propagated
    for function, limit_m in ((geometry.itrs_dcm, 30.0), (geometry.iau_earth_dcm, 15.0e3)):
        dcm = function(scenario.epoch_utc, geo.time_s)
        angle = np.arccos(np.clip((np.einsum("nij,nij->n", dcm, geo.dcm_pn) - 1.0) / 2.0, -1.0, 1.0))
        if function is geometry.itrs_dcm:
            from spacemissionstudio.engine import earth_orientation

            if not earth_orientation.installed():
                continue
        assert np.max(angle) * 6378136.6 < limit_m
    sun = geometry.erfa_sun(scenario.epoch_utc, geo.time_s)
    cosine = np.einsum("ni,ni->n", sun, geo.sun_n) / np.linalg.norm(sun, axis=1) / np.linalg.norm(geo.sun_n, axis=1)
    assert np.degrees(np.arccos(np.clip(cosine.min(), -1, 1))) < 1e-3
    assert np.linalg.norm(sun[0]) == pytest.approx(1.471e11, rel=0.01)  # early January: near perihelion


def test_the_analytic_geometry_follows_the_propagation_within_kilometres(propagated):
    """Kepler with J2 from the mean elements stays within 15 km of the
    full force model over six hours, and the sunlight agrees almost
    everywhere (a cylindrical shadow against a conical one)."""
    scenario, _result, geo = propagated
    quick = geometry.analytic(scenario, 0.0, geo.time_s[-1], 10.0)
    gap = np.linalg.norm(quick.tracks["eo-sat"].position_n - geo.tracks["eo-sat"].position_n, axis=1)
    assert np.max(gap) < 15.0e3
    agree = np.abs(quick.tracks["eo-sat"].sunlight - geo.tracks["eo-sat"].sunlight) < 0.5
    assert np.mean(agree) > 0.99
    assert "analytic geometry" in quick.notes[0]


def test_build_refuses_a_run_that_does_not_cover_the_horizon(propagated):
    """A run shorter than the horizon is refused with the days it covers;
    source 'run' without a run is refused."""
    scenario, result, _geo = propagated
    with pytest.raises(geometry.GeometryError, match="covers 0.250 days"):
        geometry.build(scenario, result)
    scenario.operations.geometry.source = "run"
    with pytest.raises(geometry.GeometryError, match="needs a finished run"):
        geometry.build(scenario)


def test_the_sun_s_elevation_matches_the_almanac_formula():
    """Independent check: the Sun's elevation at Berlin from the
    Astronomical Almanac's low-precision solar coordinates and Greenwich
    mean sidereal time agrees with the planner's within 0.1 deg."""
    scenario = fixtures.scenario()
    geo = geometry.analytic(scenario, 0.0, 86400.0, 600.0)
    planner = geo.sun_elevation_deg(52.52, 13.405)
    base = TimeBase(scenario.epoch_utc)
    for k in range(0, len(geo.time_s), 7):
        moment = base.to_utc([geo.time_s[k]])[0]
        jd = 2440587.5 + moment.timestamp() / 86400.0 if moment.tzinfo else \
            2440587.5 + (moment - moment.__class__(1970, 1, 1)).total_seconds() / 86400.0
        n = jd - 2451545.0
        mean_long = math.radians((280.460 + 0.9856474 * n) % 360.0)
        anomaly = math.radians((357.528 + 0.9856003 * n) % 360.0)
        ecliptic = mean_long + math.radians(1.915 * math.sin(anomaly) + 0.020 * math.sin(2.0 * anomaly))
        obliquity = math.radians(23.439 - 0.0000004 * n)
        ra = math.atan2(math.cos(obliquity) * math.sin(ecliptic), math.cos(ecliptic))
        dec = math.asin(math.sin(obliquity) * math.sin(ecliptic))
        gmst = math.radians((280.46061837 + 360.98564736629 * n) % 360.0)
        hour = gmst + math.radians(13.405) - ra
        lat = math.radians(52.52)
        elevation = math.degrees(math.asin(math.sin(lat) * math.sin(dec) + math.cos(lat) * math.cos(dec)
                                           * math.cos(hour)))
        assert planner[k] == pytest.approx(elevation, abs=0.1)
