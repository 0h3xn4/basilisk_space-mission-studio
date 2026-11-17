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
"""Opportunities on the planning geometry (design 2.4): target windows
with their geometry and coverage, station passes with masks and
interpolated AOS/LOS, eclipses.

A **target window** is a run of grid samples where every limit of the
target holds: off-nadir angle (at the spacecraft, between the geocentric
nadir and the line of sight) at most ``max_off_nadir_deg``; the
spacecraft's elevation seen from the target at least
``min_elevation_deg`` (above the horizon if not given); the Sun's
elevation at the target within ``sun_elevation_deg``; inside the target's
validity and the horizon. Its edges are interpolated where the smallest
margin crosses zero. Ground sample distance: slant range x pixel pitch /
focal length (SMAD).

A **pass** is a run of samples where the elevation is at least the
station's minimum elevation and its azimuth mask (linear in azimuth,
wrapping at 360 deg); AOS and LOS are interpolated the same way. From a
run, the elevation and azimuth are the recorded access analysis's.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..schema.operations import TargetConfig
from . import targets as target_files
from .geometry import PlanningGeometry, StationView


@dataclass
class Window:
    """A target window for one spacecraft, with its sampled geometry."""

    spacecraft: str
    target: str
    start_s: float  # [s] simulation time, interpolated
    end_s: float  # [s]
    time_s: np.ndarray  # samples inside (and the two around) the window [s]
    off_nadir_deg: np.ndarray
    elevation_deg: np.ndarray  # the spacecraft's, seen from the target
    sun_elevation_deg: np.ndarray
    range_m: np.ndarray
    coverage: np.ndarray | None = None  # [-] polygon: the share of its points in the footprint
    gsd_m: np.ndarray | None = None

    def at(self, t: float, name: str) -> float:
        values = getattr(self, name)
        return float(np.interp(t, self.time_s, values)) if values is not None else float("nan")

    @property
    def best_s(self) -> float:
        """The time of the smallest off-nadir angle."""
        inside = (self.time_s >= self.start_s) & (self.time_s <= self.end_s)
        if not inside.any():
            return 0.5 * (self.start_s + self.end_s)
        k = int(np.argmin(np.where(inside, self.off_nadir_deg, np.inf)))
        return float(self.time_s[k])

    @property
    def min_off_nadir_deg(self) -> float:
        return float(min(self.at(self.best_s, "off_nadir_deg"), self.at(self.start_s, "off_nadir_deg"),
                         self.at(self.end_s, "off_nadir_deg")))


@dataclass
class Pass:
    """A station pass of one spacecraft."""

    station: str
    spacecraft: str
    aos_s: float  # [s] interpolated
    los_s: float  # [s]
    max_elevation_deg: float  # [deg]
    max_elevation_s: float  # [s]
    time_s: np.ndarray = field(repr=False, default=None)
    elevation_deg: np.ndarray = field(repr=False, default=None)
    azimuth_deg: np.ndarray = field(repr=False, default=None)
    range_m: np.ndarray = field(repr=False, default=None)
    margin_db: tuple = (float("nan"), float("nan"))  # predicted link margin at the lowest and highest elevation

    @property
    def duration_s(self) -> float:
        return self.los_s - self.aos_s


@dataclass
class Opportunities:
    """Everything the scheduler places activities in."""

    windows: list  # list[Window]
    passes: list  # list[Pass]
    eclipses: dict  # spacecraft -> list of (start_s, end_s)
    polygons: dict = field(default_factory=dict)  # target name -> targets.Sample
    notes: list = field(default_factory=list)

    def windows_of(self, target: str, spacecraft: str | None = None) -> list:
        return [w for w in self.windows if w.target == target and (spacecraft is None or w.spacecraft == spacecraft)]

    def passes_of(self, spacecraft: str | None = None, station: str | None = None) -> list:
        return [p for p in self.passes if (spacecraft is None or p.spacecraft == spacecraft)
                and (station is None or p.station == station)]


def runs(margin: np.ndarray, time_s: np.ndarray) -> list[tuple[float, float, int, int]]:
    """Each run of ``margin >= 0``: ``(start, end, first, last)``, the
    start and end interpolated linearly where the margin crosses zero
    (the grid's ends when the run touches them)."""
    good = np.concatenate([[False], margin >= 0.0, [False]])
    edges = np.flatnonzero(np.diff(good.astype(np.int8)))
    out = []
    for first, stop in zip(edges[0::2], edges[1::2]):
        last = stop - 1
        start = float(time_s[first])
        if first > 0:
            m0, m1 = margin[first - 1], margin[first]
            start = float(time_s[first - 1] + (time_s[first] - time_s[first - 1]) * (-m0) / (m1 - m0))
        end = float(time_s[last])
        if last < len(time_s) - 1:
            m0, m1 = margin[last], margin[last + 1]
            end = float(time_s[last] + (time_s[last + 1] - time_s[last]) * m0 / (m0 - m1))
        out.append((start, end, int(first), int(last)))
    return out


def mask_elevation(azimuth_deg: np.ndarray, minimum_deg: float, mask: list) -> np.ndarray:
    """The lowest usable elevation [deg] at each azimuth: the station's
    minimum elevation, raised by its azimuth mask (linear between the
    mask's points, wrapping at 360 deg)."""
    if not mask:
        return np.full(np.shape(azimuth_deg), minimum_deg)
    points = np.asarray(mask, dtype=float)
    az = np.concatenate([points[:, 0] - 360.0, points[:, 0], points[:, 0] + 360.0])
    el = np.tile(points[:, 1], 3)
    return np.maximum(minimum_deg, np.interp(np.asarray(azimuth_deg) % 360.0, az, el))


def _limit_margins(off_nadir, elevation, sun_elevation, target: TargetConfig, limits_from) -> list[np.ndarray]:
    margins = [target.max_off_nadir_deg - off_nadir,
               elevation - (target.min_elevation_deg if target.min_elevation_deg is not None else 0.0)]
    if target.sun_elevation_deg is not None:
        low, high = target.sun_elevation_deg
        margins += [sun_elevation - low, high - sun_elevation]
    margins += limits_from
    return margins


def target_windows(geometry: PlanningGeometry, target: TargetConfig, spacecraft: list[str], timebase,
                   detector=None, field_of_view_deg: float | None = None) -> list[Window]:
    """The windows of ``target`` for each of ``spacecraft`` (module
    docstring). ``detector`` gives the GSD; ``field_of_view_deg`` (full
    cone) a polygon's coverage."""
    t = geometry.time_s
    lat, lon, alt = target_files.aim_point(target)
    site, up, _north, _east = geometry.site(lat, lon, alt)
    sun_elevation = geometry.sun_elevation_deg(lat, lon, alt)
    validity = []
    if target.valid_utc is not None:
        first, last = (timebase.to_sim(moment) for moment in target.valid_utc)
        validity = [t - first, last - t]
    points = None
    if target.kind == "polygon":
        sampled = target_files.sample(target)
        points = [geometry.site(a, b, alt)[0] for a, b in zip(sampled.latitude_deg, sampled.longitude_deg)]
    windows = []
    for name in spacecraft:
        track = geometry.tracks[name]
        line = site - track.position_n
        distance = np.linalg.norm(line, axis=1)
        unit = line / distance[:, None]
        nadir = -track.position_n / np.linalg.norm(track.position_n, axis=1)[:, None]
        off_nadir = np.degrees(np.arccos(np.clip(np.einsum("ni,ni->n", unit, nadir), -1.0, 1.0)))
        elevation = np.degrees(np.arcsin(np.clip(-np.einsum("ni,ni->n", unit, up), -1.0, 1.0)))
        margins = _limit_margins(off_nadir, elevation, sun_elevation, target, validity)
        margin = np.min(np.vstack(margins), axis=0)
        for start, end, first, last in runs(margin, t):
            lo, hi = max(first - 1, 0), min(last + 2, len(t))
            span = slice(lo, hi)
            coverage = None
            if points is not None and field_of_view_deg is not None:
                half = math.radians(field_of_view_deg) / 2.0
                covered = np.zeros(hi - lo)
                for point in points:
                    to_point = point[span] - track.position_n[span]
                    to_point /= np.linalg.norm(to_point, axis=1)[:, None]
                    covered += np.einsum("ni,ni->n", to_point, unit[span]) >= math.cos(half)
                coverage = covered / len(points)
            gsd = None
            if detector is not None and detector.pixel_pitch_um is not None:
                gsd = distance[span] * detector.pixel_pitch_um * 1e-6 / (detector.focal_length_mm * 1e-3)  # [m]
            windows.append(Window(name, target.name, start, end, t[span].copy(), off_nadir[span].copy(),
                                  elevation[span].copy(), sun_elevation[span].copy(), distance[span].copy(),
                                  coverage, gsd))
    return windows


def station_passes(geometry: PlanningGeometry, station, settings, spacecraft: str, rf_link=None,
                   scenario=None) -> list[Pass]:
    """The passes of ``spacecraft`` over ``station`` (a
    ``GroundStationConfig``) with its planning ``settings`` (a
    ``StationPlanningConfig`` or None): from the run's access series when
    the geometry has them, else computed on the geometry."""
    view: StationView | None = geometry.views.get((station.name, spacecraft))
    if view is None:
        view = geometry.view(spacecraft, station.latitude_deg, station.longitude_deg, station.altitude_m)
    lowest = mask_elevation(view.azimuth_deg, station.min_elevation_deg,
                            settings.azimuth_mask if settings is not None else [])
    margin = view.elevation_deg - lowest
    t = geometry.time_s
    passes = []
    for aos, los, first, last in runs(margin, t):
        if los - aos <= 0.0:
            continue
        lo, hi = max(first - 1, 0), min(last + 2, len(t))
        k = first + int(np.argmax(view.elevation_deg[first:last + 1]))
        peak, peak_t = _parabola_peak(t, view.elevation_deg, k)
        item = Pass(station.name, spacecraft, aos, los, peak, peak_t, t[lo:hi].copy(), view.elevation_deg[lo:hi].copy(),
                    view.azimuth_deg[lo:hi].copy(), view.range_m[lo:hi].copy())
        if rf_link is not None:
            item.margin_db = _margins(item, rf_link, station, scenario, float(np.max(lowest[first:last + 1])))
        passes.append(item)
    return passes


def _parabola_peak(t: np.ndarray, values: np.ndarray, k: int) -> tuple[float, float]:
    """The peak of the parabola through the three samples around ``k``."""
    if k <= 0 or k >= len(t) - 1:
        return float(values[k]), float(t[k])
    y0, y1, y2 = values[k - 1], values[k], values[k + 1]
    denominator = y0 - 2.0 * y1 + y2
    if denominator >= 0.0:
        return float(y1), float(t[k])
    shift = 0.5 * (y0 - y2) / denominator  # [samples]
    return float(y1 - 0.25 * (y0 - y2) * shift), float(t[k] + shift * (t[k + 1] - t[k]))


def _margins(item: Pass, rf_link, station, scenario, lowest_deg: float) -> tuple[float, float]:
    """Predicted Eb/N0 margin [dB] at the pass's lowest usable elevation and
    at its peak, with the antenna on the station (``engine.link_budget``)."""
    from ..engine import link_budget

    out = []
    for elevation in (lowest_deg, item.max_elevation_deg):
        distance = float(np.interp(elevation, *_monotonic(item.elevation_deg, item.range_m)))
        try:
            breakdown = link_budget.link_budget_breakdown(distance, rf_link, station, 0.0, scenario=scenario,
                                                          elevation_deg=elevation)
            out.append(float(breakdown.margin_db))
        except (ValueError, ZeroDivisionError):
            out.append(float("nan"))
    return tuple(out)


def _monotonic(elevation: np.ndarray, distance: np.ndarray):
    order = np.argsort(elevation)
    return elevation[order], distance[order]


def eclipses(geometry: PlanningGeometry) -> dict:
    """Each spacecraft's eclipse intervals (sunlight below 1), simulation
    seconds."""
    out = {}
    for name, track in geometry.tracks.items():
        dark = 0.999 - track.sunlight
        out[name] = [(start, end) for start, end, _f, _l in runs(dark, geometry.time_s)]
    return out


def find(scenario, geometry: PlanningGeometry, timebase) -> Opportunities:
    """Every window, pass and eclipse the scenario's ``operations`` section
    asks for (enabled targets and disabled ones alike: what-if events turn
    those on)."""
    from ..model3d.equipment import mounted_items

    section = scenario.operations
    planned = [p.spacecraft for p in section.spacecraft]
    spacecraft = {sc.name: sc for sc in scenario.spacecraft}
    windows, polygons = [], {}
    for target in section.targets:
        who = target.spacecraft or planned
        kind = section.activity_type(target.activity)
        for name in who:
            settings = section.planned(name)
            detector = settings.detector if settings is not None else None
            fov = detector.field_of_view_deg if detector is not None else None
            if kind is not None and kind.equipment:
                item = next((m for m in mounted_items(spacecraft[name]) if m.name == kind.equipment), None)
                if item is not None and item.field_of_view_deg is not None:
                    fov = item.field_of_view_deg
            windows += target_windows(geometry, target, [name], timebase, detector, fov)
        if target.kind == "polygon":
            polygons[target.name] = target_files.sample(target)
    passes = []
    stations = {gs.name: gs for gs in scenario.ground_stations}
    for settings in section.spacecraft:
        if not settings.contact_activity:
            continue
        sc = spacecraft[settings.spacecraft]
        for gs in stations.values():
            passes += station_passes(geometry, gs, section.station(gs.name), sc.name, sc.rf_link, scenario)
    passes.sort(key=lambda p: (p.aos_s, p.station, p.spacecraft))
    windows.sort(key=lambda w: (w.start_s, w.target, w.spacecraft))
    return Opportunities(windows, passes, eclipses(geometry), polygons, list(geometry.notes))
