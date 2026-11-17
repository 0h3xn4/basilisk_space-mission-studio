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
"""The plan against the simulation that flew it (design 2.10, decision
O-19).

Per activity: whether it was flown (the executor's activity log), the
pointing error at its start (the slew finished when it is within
``results.pointing_converged_deg``) and through it, the off-nadir angle
and the Sun's elevation at the target from the flown trajectory and the
recorded Earth and Sun, the link margin and the data a contact took
down. Per spacecraft: the battery's state of charge and the memory
against the planned profiles. Every difference beyond the scenario's
tolerances (``operations.verification``) is flagged.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .. import output_provenance
from . import geometry as geometry_model
from . import targets as target_files


@dataclass
class ActivityCheck:
    id: str
    spacecraft: str
    type: str
    kind: str
    start_utc: str
    flown: bool
    error_at_start_deg: float | None = None
    error_max_deg: float | None = None
    error_mean_deg: float | None = None
    slew_done: bool | None = None
    off_nadir_planned_deg: float | None = None
    off_nadir_flown_deg: float | None = None
    sun_elevation_planned_deg: float | None = None
    sun_elevation_flown_deg: float | None = None
    margin_min_db: float | None = None
    downlinked_bit: float | None = None
    flags: list = field(default_factory=list)


@dataclass
class ResourceCheck:
    spacecraft: str
    soc_max_difference_points: float | None = None
    soc_min_planned: float | None = None
    soc_min_flown: float | None = None
    memory_max_difference_fraction: float | None = None
    memory_max_planned_bit: float | None = None
    memory_max_flown_bit: float | None = None
    flags: list = field(default_factory=list)


@dataclass
class Verification:
    activities: list
    resources: list
    tolerances: dict
    contingency: dict = field(default_factory=dict)  # spacecraft -> [(utc, state)]

    @property
    def flags(self) -> list[str]:
        return [f"{a.id} {f}" for a in self.activities for f in a.flags] + \
               [f"{r.spacecraft} {f}" for r in self.resources for f in r.flags]

    def markdown(self) -> list[str]:
        lines = ["| Id | Type | Flown | Error at start [deg] | Max error [deg] | Off-nadir plan/flown [deg] | "
                 "Sun elev. plan/flown [deg] | Flags |", "|---|---|---|--:|--:|--:|--:|---|"]
        for a in self.activities:
            lines.append(f"| {a.id} | {a.type} | {'yes' if a.flown else 'no'} | {_f(a.error_at_start_deg)} | "
                         f"{_f(a.error_max_deg)} | {_f(a.off_nadir_planned_deg)}/{_f(a.off_nadir_flown_deg)} | "
                         f"{_f(a.sun_elevation_planned_deg)}/{_f(a.sun_elevation_flown_deg)} | "
                         f"{'; '.join(a.flags)} |")
        lines += ["", "| Spacecraft | SoC max difference [points] | Lowest SoC plan/flown [%] | "
                      "Memory max difference [% of capacity] | Flags |", "|---|--:|--:|--:|---|"]
        for r in self.resources:
            lines.append(f"| {r.spacecraft} | {_f(r.soc_max_difference_points)} | "
                         f"{_f(_pct(r.soc_min_planned))}/{_f(_pct(r.soc_min_flown))} | "
                         f"{_f(_pct(r.memory_max_difference_fraction))} | {'; '.join(r.flags)} |")
        return lines


def _f(value, digits: int = 2) -> str:
    return "" if value is None or (isinstance(value, float) and not math.isfinite(value)) else f"{value:.{digits}f}"


def _pct(value):
    return None if value is None else 100.0 * value


def _interval(series, start: float, end: float) -> np.ndarray:
    """The samples in [start, end): at ``end`` the executor has already
    switched to what comes next."""
    t = np.asarray(series.time_s, dtype=float)
    keep = (t >= start - 1e-6) & (t < end - 1e-6)
    return np.asarray(series.data, dtype=float).reshape(len(t), -1)[keep, 0]


def check(scenario, plan, result) -> Verification:
    """Compare ``plan`` with the run ``result`` that flew it."""
    from ..config import registry

    section = scenario.operations
    tolerances = section.verification
    settle = float(registry.value("results.pointing_converged_deg", scenario))
    flown_geometry = geometry_model.from_run(result, scenario, plan.start_s, plan.end_s, section.geometry.step_s, "run")
    activities, resources, contingency = [], [], {}
    for name in plan.resources:
        mine = sorted(plan.of(name), key=lambda a: a.start_s)
        error = result.series.get(f"{name}.plan.pointing_error_deg")
        index = result.series.get(f"{name}.plan.activity")
        state = result.series.get(f"{name}.plan.contingency")
        if state is not None:
            values = np.asarray(state.data, dtype=float)[:, 0]
            changes = np.flatnonzero(np.diff(values) != 0.0) + 1
            from .timebase import TimeBase

            base = TimeBase(scenario.epoch_utc)
            contingency[name] = [(base.text(state.time_s[k]), int(values[k])) for k in changes]
        for number, activity in enumerate(mine):
            row = ActivityCheck(activity.id, name, activity.type, activity.kind, activity.start_utc, False)
            if index is not None:
                logged = _interval(index, activity.start_s, activity.end_s)
                row.flown = bool(np.any(logged == number))
            if error is not None and row.flown:
                t = np.asarray(error.time_s, dtype=float)
                data = np.asarray(error.data, dtype=float)[:, 0]
                row.error_at_start_deg = float(np.interp(activity.start_s, t, data))
                during = _interval(error, activity.start_s, activity.end_s)
                if len(during):
                    row.error_max_deg = float(np.max(during))
                    row.error_mean_deg = float(np.mean(during))
                row.slew_done = row.error_at_start_deg <= settle
                if not row.slew_done:
                    row.flags.append(f"slew not finished: {row.error_at_start_deg:.1f} deg at the start "
                                     f"(converged below {settle:g} deg)")
            if not row.flown:
                row.flags.append("not flown (dropped by a contingency rule, or outside the run)")
            if activity.target:
                _target_geometry(row, activity, section, flown_geometry, name, tolerances)
            if activity.kind == "contact":
                _contact(row, activity, result, name)
            activities.append(row)
        resources.append(_resources(plan, result, scenario, name, tolerances))
    return Verification(activities, resources, {"pointing_converged_deg": settle,
                                                "soc_points": tolerances.soc_points,
                                                "memory_fraction": tolerances.memory_fraction,
                                                "off_nadir_deg": tolerances.off_nadir_deg,
                                                "sun_elevation_deg": tolerances.sun_elevation_deg}, contingency)


def _target_geometry(row: ActivityCheck, activity, section, geometry, name: str, tolerances) -> None:
    target = next(t for t in section.targets if t.name == activity.target)
    lat, lon, alt = target_files.aim_point(target)
    middle = 0.5 * (activity.start_s + activity.end_s)
    k = int(np.clip(np.searchsorted(geometry.time_s, middle), 0, len(geometry.time_s) - 1))
    site = geometry.site(lat, lon, alt)[0][k]
    r = geometry.tracks[name].position_n[k]
    line = (site - r) / np.linalg.norm(site - r)
    off = math.degrees(math.acos(min(1.0, max(-1.0, float(np.dot(line, -r / np.linalg.norm(r)))))))
    sun = float(geometry.sun_elevation_deg(lat, lon, alt)[k])
    row.off_nadir_planned_deg = activity.predicted.get("off_nadir_deg")
    row.sun_elevation_planned_deg = activity.predicted.get("sun_elevation_deg")
    row.off_nadir_flown_deg, row.sun_elevation_flown_deg = off, sun
    if row.off_nadir_planned_deg is not None and abs(off - row.off_nadir_planned_deg) > tolerances.off_nadir_deg:
        row.flags.append(f"off-nadir {off:.2f} deg flown, {row.off_nadir_planned_deg:.2f} planned")
    if off > target.max_off_nadir_deg + 1e-6:
        row.flags.append(f"off-nadir {off:.2f} deg beyond the target's {target.max_off_nadir_deg:g} deg")
    if row.sun_elevation_planned_deg is not None and \
            abs(sun - row.sun_elevation_planned_deg) > tolerances.sun_elevation_deg:
        row.flags.append(f"Sun elevation {sun:.2f} deg flown, {row.sun_elevation_planned_deg:.2f} planned")


def _contact(row: ActivityCheck, activity, result, name: str) -> None:
    margin = result.series.get(f"{activity.station}.access_to_{name}.link_margin_db")
    if margin is not None:
        values = _interval(margin, activity.start_s, activity.end_s)
        values = values[np.isfinite(values)]
        if len(values):
            row.margin_min_db = float(np.min(values))
    downlinked = result.series.get(f"{name}.data_handling.data_downlinked")
    if downlinked is not None:
        t = np.asarray(downlinked.time_s, dtype=float)
        data = np.asarray(downlinked.data, dtype=float)[:, 0]
        row.downlinked_bit = float(np.interp(activity.end_s, t, data) - np.interp(activity.start_s, t, data))


def _within(t_plan: np.ndarray, series) -> np.ndarray:
    """The planned samples inside the flown series' span."""
    if series.time_s.size == 0:
        return np.zeros(len(t_plan), dtype=bool)
    return (t_plan >= series.time_s[0] - 1e-6) & (t_plan <= series.time_s[-1] + 1e-6)


def _resources(plan, result, scenario, name: str, tolerances) -> ResourceCheck:
    check_ = ResourceCheck(name)
    planned = plan.resources[name]
    t_plan = np.asarray(planned["time_s"], dtype=float)
    sc = next(s for s in scenario.spacecraft if s.name == name)
    battery = result.series.get(f"{name}.battery_charge")
    if battery is not None and sc.power is not None and _within(t_plan, battery).any():
        inside = _within(t_plan, battery)  # only where the run flew: a shorter flight is not a difference
        flown = np.interp(t_plan[inside], battery.time_s, np.asarray(battery.data, dtype=float)[:, 0]) \
            / sc.power.battery_capacity_wh
        soc = np.asarray(planned["soc"], dtype=float)[inside]
        check_.soc_max_difference_points = float(np.max(np.abs(flown - soc))) * 100.0
        check_.soc_min_planned, check_.soc_min_flown = float(np.min(soc)), float(np.min(flown))
        if check_.soc_max_difference_points > tolerances.soc_points:
            check_.flags.append(f"state of charge differs by {check_.soc_max_difference_points:.1f} points")
    stored = result.series.get(f"{name}.data_handling.stored")
    if stored is not None and sc.data_handling is not None and _within(t_plan, stored).any():
        inside = _within(t_plan, stored)
        flown = np.interp(t_plan[inside], stored.time_s, np.asarray(stored.data, dtype=float)[:, 0])
        memory = np.asarray(planned["memory_bit"], dtype=float)[inside]
        capacity = sc.data_handling.storage_capacity_gbit * 1e9
        check_.memory_max_difference_fraction = float(np.max(np.abs(flown - memory))) / capacity
        check_.memory_max_planned_bit, check_.memory_max_flown_bit = float(np.max(memory)), float(np.max(flown))
        if check_.memory_max_difference_fraction > tolerances.memory_fraction:
            check_.flags.append(f"memory differs by {100.0 * check_.memory_max_difference_fraction:.1f} % of "
                                "the capacity")
    return check_


_ACTIVITY_FIELDS = ("id", "spacecraft", "type", "kind", "start_utc", "flown", "error_at_start_deg", "error_max_deg",
                    "error_mean_deg", "slew_done", "off_nadir_planned_deg", "off_nadir_flown_deg",
                    "sun_elevation_planned_deg", "sun_elevation_flown_deg", "margin_min_db", "downlinked_bit")


def write_csv(path, verification: Verification, provenance: dict) -> list[Path]:
    """The activity and resource tables as CSV, each with its provenance."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(list(_ACTIVITY_FIELDS) + ["flags"])
        for a in verification.activities:
            writer.writerow([_cell(getattr(a, k)) for k in _ACTIVITY_FIELDS] + ["; ".join(a.flags)])
    output_provenance.write_sidecar(path, {**provenance, "kind": "plan verification", "tolerances":
                                           verification.tolerances})
    second = path.with_name(path.stem + "_resources.csv")
    with second.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        fields = ("spacecraft", "soc_max_difference_points", "soc_min_planned", "soc_min_flown",
                  "memory_max_difference_fraction", "memory_max_planned_bit", "memory_max_flown_bit")
        writer.writerow(list(fields) + ["flags"])
        for r in verification.resources:
            writer.writerow([_cell(getattr(r, k)) for k in fields] + ["; ".join(r.flags)])
    output_provenance.write_sidecar(second, {**provenance, "kind": "plan verification, resources",
                                             "tolerances": verification.tolerances})
    return [path, second]


def _cell(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.6g}"
    return value
