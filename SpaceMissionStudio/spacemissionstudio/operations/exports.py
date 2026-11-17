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
"""Operations products from a plan (design 2.12), each with its
provenance: the pass schedule (CSV and iCalendar, RFC 5545), the activity
timeline (CSV and JSON), the time-tagged command schedule (JSON and CSV),
station pointing predictions (CSV), CCSDS OEM (3.0) and AEM (2.0) of the
planned trajectory and attitude, and a report (Markdown).

CSV files get a ``.provenance.json`` beside them
(``output_provenance.write_sidecar``); JSON files carry it inside; the
iCalendar file in its own ``X-`` properties; CCSDS files in ``COMMENT``
lines.

The command schedule is a **planning product**, not a flight command
load: its entries use the terminology of the Packet Utilization Standard
(ECSS-E-ST-70-41C, service 11 "time-based scheduling": time-tagged
requests with a release time) but are not telecommands; no binary packet
is written.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from .. import output_provenance
from .plan import Plan

ACTIVITIES_FORMAT = "spacemissionstudio-activities"
COMMANDS_FORMAT = "spacemissionstudio-command-schedule"
_PREDICTED = ("off_nadir_deg", "elevation_deg", "sun_elevation_deg", "range_m", "gsd_m", "coverage", "slew_deg",
              "slew_s", "max_elevation_deg", "margin_low_db", "margin_high_db", "downlink_capacity_bit")


def record(plan: Plan, kind: str) -> dict:
    """The provenance an export carries: the plan's, with what it is."""
    return {**plan.provenance, "kind": kind, "plan_sha256": plan_sha256(plan),
            "note": "a planning product: not a flight command load"}


def plan_sha256(plan: Plan) -> str:
    data = plan.to_dict()
    data["provenance"] = {k: v for k, v in data["provenance"].items() if k not in ("created_utc", "seconds")}
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()


def _write_csv(path: Path, header: list[str], rows: list[list], provenance: dict) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    output_provenance.write_sidecar(path, provenance)
    return path


def _value(value):
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6g}"
    return value


# -- passes ------------------------------------------------------------------------------------------------


def pass_rows(plan: Plan, opportunities, timebase) -> list[dict]:
    """Every pass of a planned spacecraft, with the contact planned on it."""
    contacts = [a for a in plan.activities if a.kind == "contact"]
    rows = []
    for item in opportunities.passes:
        contact = next((a for a in contacts if a.station == item.station and a.spacecraft == item.spacecraft
                        and item.aos_s - 1e-6 <= a.start_s <= item.los_s + 1e-6), None)
        rows.append({"station": item.station, "spacecraft": item.spacecraft, "aos_utc": timebase.text(item.aos_s),
                     "los_utc": timebase.text(item.los_s), "duration_s": item.duration_s,
                     "max_elevation_deg": item.max_elevation_deg,
                     "max_elevation_utc": timebase.text(item.max_elevation_s),
                     "margin_low_db": item.margin_db[0], "margin_high_db": item.margin_db[1],
                     "contact": contact.id if contact is not None else "",
                     "contact_start_utc": contact.start_utc if contact is not None else "",
                     "contact_end_utc": contact.end_utc if contact is not None else ""})
    return rows


def write_passes_csv(path, plan: Plan, opportunities, timebase) -> Path:
    rows = pass_rows(plan, opportunities, timebase)
    header = ["station", "spacecraft", "aos_utc", "los_utc", "duration_s", "max_elevation_deg", "max_elevation_utc",
              "margin_low_db", "margin_high_db", "contact", "contact_start_utc", "contact_end_utc"]
    return _write_csv(path, header, [[_value(r[k]) for k in header] for r in rows], record(plan, "pass schedule"))


def _ics_text(value: str) -> str:
    """RFC 5545 3.3.11 TEXT escaping."""
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    """RFC 5545 3.1: lines of at most 75 octets, continued with CRLF and a
    space."""
    data = line.encode("utf-8")
    if len(data) <= 75:
        return line
    parts, current = [], b""
    for char in line:
        encoded = char.encode("utf-8")
        if len(current) + len(encoded) > (75 if not parts else 74):
            parts.append(current.decode("utf-8"))
            current = b""
        current += encoded
    parts.append(current.decode("utf-8"))
    return "\r\n ".join(parts)


def _ics_time(utc: str) -> str:
    """``2030-01-01T08:30:00.000Z`` -> ``20300101T083000Z`` (RFC 5545 3.3.5,
    UTC form; seconds rounded down: iCalendar has no fractions)."""
    return utc[:19].replace("-", "").replace(":", "") + "Z"


def passes_ics(plan: Plan, opportunities, timebase, all_passes: bool = False) -> str:
    """The planned contacts (or every pass) as an iCalendar file (RFC 5545):
    one VEVENT each, times in UTC, CRLF line ends, folded lines."""
    provenance = record(plan, "pass schedule")
    stamp = _ics_time(plan.provenance.get("created_utc", plan.start_utc) or plan.start_utc)
    digest = provenance["plan_sha256"][:16]
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//SpaceMissionStudio//Operations planning//EN",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
             f"X-SPACEMISSIONSTUDIO-PROVENANCE:{_ics_text(json.dumps(provenance, sort_keys=True))}"]
    for row in pass_rows(plan, opportunities, timebase):
        if not all_passes and not row["contact"]:
            continue
        start = row["contact_start_utc"] or row["aos_utc"]
        end = row["contact_end_utc"] or row["los_utc"]
        what = "contact" if row["contact"] else "pass"
        summary = f"{row['spacecraft']} {what} {row['station']}"
        uid = f"{digest}-{row['station']}-{row['spacecraft']}-{_ics_time(row['aos_utc'])}@spacemissionstudio.invalid"
        description = (f"{row['spacecraft']} over {row['station']}: AOS {row['aos_utc']}, LOS {row['los_utc']}, "
                       f"maximum elevation {row['max_elevation_deg']:.1f} deg at {row['max_elevation_utc']}"
                       + (f"; planned contact {row['contact']}" if row["contact"] else "")
                       + ". A planning product, not a flight command load.")
        lines += ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{stamp}", f"DTSTART:{_ics_time(start)}",
                  f"DTEND:{_ics_time(end)}", f"SUMMARY:{_ics_text(summary)}",
                  f"DESCRIPTION:{_ics_text(description)}", f"LOCATION:{_ics_text(row['station'])}", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


# -- activities ----------------------------------------------------------------------------------------------


_ACTIVITY_COLUMNS = ["id", "spacecraft", "type", "kind", "start_utc", "end_utc", "setup_s", "teardown_s",
                     "pointing", "target", "station", "request", "priority", "locked", "point_from_utc"]


def activity_rows(plan: Plan, timebase) -> list[list]:
    rows = []
    for a in plan.activities:
        point_from = a.predicted.get("point_from_s")
        rows.append([a.id, a.spacecraft, a.type, a.kind, a.start_utc, a.end_utc, _value(a.setup_s),
                     _value(a.teardown_s), a.pointing, a.target, a.station, a.request,
                     "" if a.priority is None else a.priority, "yes" if a.locked else "",
                     timebase.text(point_from) if point_from is not None else ""]
                    + [_value(a.predicted.get(k)) for k in _PREDICTED])
    return rows


def write_activities_csv(path, plan: Plan, timebase) -> Path:
    return _write_csv(path, _ACTIVITY_COLUMNS + list(_PREDICTED), activity_rows(plan, timebase),
                      record(plan, "activity timeline"))


def activities_json(plan: Plan, timebase) -> dict:
    """The activity timeline as documented JSON (docs/models/operations.md)."""
    items = []
    for row in activity_rows(plan, timebase):
        entry = dict(zip(_ACTIVITY_COLUMNS, row[:len(_ACTIVITY_COLUMNS)]))
        entry["predicted"] = {k: plan.find(entry["id"]).predicted.get(k) for k in _PREDICTED
                              if plan.find(entry["id"]).predicted.get(k) is not None}
        entry["locked"] = bool(entry["locked"])
        items.append(entry)
    return {"format": ACTIVITIES_FORMAT, "version": 1, "provenance": record(plan, "activity timeline"),
            "horizon": {"start_utc": plan.start_utc, "end_utc": plan.end_utc}, "activities": items,
            "unscheduled": [{"request": u.request, "spacecraft": u.spacecraft, "kind": u.kind,
                             "priority": u.priority, "reason": u.reason, "text": u.text, "counts": u.counts}
                            for u in plan.unscheduled]}


# -- commands -------------------------------------------------------------------------------------------------


def commands(plan: Plan, scenario, timebase) -> list[dict]:
    """The time-tagged requests that would fly the plan, in release order:
    pointing changes, devices on and off, loads, maneuvers."""
    section = scenario.operations
    out = []

    def add(t: float, spacecraft: str, command: str, arguments: dict, activity: str) -> None:
        out.append({"release_time_utc": timebase.text(t), "release_s": t, "spacecraft": spacecraft,
                    "command": command, "arguments": arguments, "activity": activity})

    for a in plan.activities:
        kind = section.activity_type(a.type)
        settings = section.planned(a.spacecraft)
        point_from = a.predicted.get("point_from_s", a.occupied[0])
        target = {"target": a.target} if a.target else {"station": a.station} if a.station else {}
        add(point_from, a.spacecraft, "SET_POINTING", {"mode": a.pointing, **target}, a.id)
        for name in kind.instruments:
            add(a.start_s, a.spacecraft, "INSTRUMENT_ON", {"instrument": name}, a.id)
            add(a.end_s, a.spacecraft, "INSTRUMENT_OFF", {"instrument": name}, a.id)
        if kind.transmitter:
            add(a.start_s, a.spacecraft, "TRANSMITTER_ON", {"station": a.station}, a.id)
            add(a.end_s, a.spacecraft, "TRANSMITTER_OFF", {"station": a.station}, a.id)
        if kind.power_w:
            add(a.start_s, a.spacecraft, "LOAD_ON", {"power_w": kind.power_w}, a.id)
            add(a.end_s, a.spacecraft, "LOAD_OFF", {"power_w": kind.power_w}, a.id)
        if kind.kind == "maneuver":
            add(a.start_s, a.spacecraft, "MANEUVER", {"delta_v_m_s": list(kind.delta_v_m_s), "frame": kind.frame},
                a.id)
        add(a.occupied[1], a.spacecraft, "SET_POINTING", {"mode": settings.default_pointing}, a.id)
    order = {"SET_POINTING": 1, "INSTRUMENT_OFF": 0, "TRANSMITTER_OFF": 0, "LOAD_OFF": 0}
    out.sort(key=lambda c: (c["release_s"], c["spacecraft"], order.get(c["command"], 2), c["activity"]))
    return out


def commands_json(plan: Plan, scenario, timebase) -> dict:
    return {"format": COMMANDS_FORMAT, "version": 1, "provenance": record(plan, "command schedule"),
            "terminology": "ECSS-E-ST-70-41C service 11 (time-based scheduling): each entry is a time-tagged "
                           "request with its release time; a planning product, not telecommands",
            "requests": [{k: v for k, v in c.items() if k != "release_s"} for c in commands(plan, scenario, timebase)]}


def write_commands_csv(path, plan: Plan, scenario, timebase) -> Path:
    rows = [[c["release_time_utc"], c["spacecraft"], c["command"], json.dumps(c["arguments"], sort_keys=True),
             c["activity"]] for c in commands(plan, scenario, timebase)]
    return _write_csv(path, ["release_time_utc", "spacecraft", "command", "arguments", "activity"], rows,
                      record(plan, "command schedule"))


# -- pointing predictions ------------------------------------------------------------------------------------------


def pointing_rows(plan: Plan, scenario, opportunities, timebase, geometry, step_s: float | None = None) -> list[list]:
    """Azimuth, elevation, range and range rate from each station to its
    spacecraft through each planned contact's pass (AOS to LOS), on the
    geometry grid (or every ``step_s``): the run's access analysis when the
    geometry came from a run, else the planner's own computation."""
    stations = {gs.name: gs for gs in scenario.ground_stations}
    rows = []
    for row in pass_rows(plan, opportunities, timebase):
        if not row["contact"]:
            continue
        item = next(p for p in opportunities.passes if p.station == row["station"]
                    and p.spacecraft == row["spacecraft"] and timebase.text(p.aos_s) == row["aos_utc"])
        view = geometry.views.get((item.station, item.spacecraft))
        if view is None:
            gs = stations[item.station]
            view = geometry.view(item.spacecraft, gs.latitude_deg, gs.longitude_deg, gs.altitude_m)
        t = geometry.time_s
        keep = (t >= item.aos_s - 1e-6) & (t <= item.los_s + 1e-6)
        times = t[keep] if step_s is None else np.arange(item.aos_s, item.los_s + 1e-9, step_s)
        elevation = np.interp(times, t, view.elevation_deg)
        azimuth = np.degrees(np.interp(times, t, np.unwrap(np.radians(view.azimuth_deg)))) % 360.0
        distance = np.interp(times, t, view.range_m)
        rate = np.interp(times, t, np.gradient(view.range_m, t))
        for k, moment in enumerate(timebase.texts(times)):
            rows.append([item.station, item.spacecraft, row["contact"], moment, f"{azimuth[k]:.4f}",
                         f"{elevation[k]:.4f}", f"{distance[k]:.1f}", f"{rate[k]:.3f}"])
    return rows


def write_pointing_csv(path, plan: Plan, scenario, opportunities, timebase, geometry, step_s=None) -> Path:
    rows = pointing_rows(plan, scenario, opportunities, timebase, geometry, step_s)
    return _write_csv(path, ["station", "spacecraft", "contact", "time_utc", "azimuth_deg", "elevation_deg",
                             "range_m", "range_rate_m_s"], rows, record(plan, "station pointing predictions"))


# -- CCSDS --------------------------------------------------------------------------------------------------------


def oem(plan: Plan, geometry, timebase, stride: int = 1) -> dict[str, str]:
    """One OEM (3.0, KVN) per planned spacecraft from the planning geometry."""
    from ..engine import ccsds_odm

    out = {}
    index = np.arange(0, len(geometry.time_s), max(1, int(stride)))
    if index[-1] != len(geometry.time_s) - 1:
        index = np.append(index, len(geometry.time_s) - 1)
    epochs = timebase.to_utc(geometry.time_s[index])
    lines = _ccsds_lines(plan, "planned trajectory")
    for name in plan.resources:
        track = geometry.tracks[name]
        segment = {"object_name": name, "object_id": "UNKNOWN", "center_name": "EARTH", "ref_frame": "EME2000",
                   "time_system": "UTC", "epochs": epochs, "r_km": track.position_n[index] / 1e3,
                   "v_km_s": track.velocity_n[index] / 1e3, "interpolation": "LAGRANGE", "interpolation_degree": 7,
                   "comments": [f"SpaceMissionStudio planning geometry, source {geometry.source}"]}
        out[name] = ccsds_odm.write_oem([segment], comments=lines)
    return out


def aem(plan: Plan, planning, stride: int = 1) -> dict[str, str]:
    """One AEM (2.0, KVN) per planned spacecraft: the planned attitude."""
    from ..engine import ccsds_adm
    from .resources import SpacecraftModel, attitude_series

    geometry, timebase = planning.geometry, planning.timebase
    spacecraft = {sc.name: sc for sc in planning.scenario.spacecraft}
    out = {}
    index = np.arange(0, len(geometry.time_s), max(1, int(stride)))
    if index[-1] != len(geometry.time_s) - 1:
        index = np.append(index, len(geometry.time_s) - 1)
    epochs = timebase.to_utc(geometry.time_s[index])
    for name in plan.resources:
        model = SpacecraftModel(planning.scenario, spacecraft[name], geometry, planning.scenario.operations,
                                planning.slew_models[name])
        mine = sorted(plan.of(name), key=lambda a: a.start_s)
        dcm = attitude_series(model, mine)[index]
        segment = {"object_name": name, "object_id": "UNKNOWN", "center_name": "EARTH", "epochs": epochs,
                   "dcm_bn": dcm, "interpolation": "LINEAR", "interpolation_degree": 1,
                   "comments": ["the planned attitude: each mode as its guidance computes it; slews are not modelled "
                                "(a slew is shown as its end attitude)"]}
        out[name] = ccsds_adm.write_aem([segment], comments=_ccsds_lines(plan, "planned attitude"))
    return out


def _ccsds_lines(plan: Plan, what: str) -> list[str]:
    provenance = record(plan, what)
    return [f"SpaceMissionStudio {provenance.get('tool_version', '')} operations plan, {what}",
            f"Scenario {provenance.get('scenario', '')} SHA-256 {provenance.get('scenario_sha256', '')}",
            f"Plan SHA-256 {provenance['plan_sha256']}", "A planning product, not a flight command load"]


# -- report ---------------------------------------------------------------------------------------------------------


def report(plan: Plan, timebase, verification=None) -> str:
    """A Markdown report of the plan (and of its verification, when given)."""
    provenance = record(plan, "plan report")
    lines = [f"# Operations plan: {provenance.get('scenario', '')}", "",
             f"Horizon {plan.start_utc} to {plan.end_utc}. A planning product, not a flight command load.", "",
             "## Summary", "", "| Spacecraft | Activities | Contacts | Contact time [min] | Lowest SoC [%] | "
             "Most memory [Gbit] | Lost [Gbit] | Downlinked [Gbit] |", "|---|--:|--:|--:|--:|--:|--:|--:|"]
    for name, resources in plan.resources.items():
        mine = plan.of(name)
        contacts = [a for a in mine if a.kind == "contact"]
        lines.append(f"| {name} | {len(mine) - len(contacts)} | {len(contacts)} | "
                     f"{sum(a.duration_s for a in contacts) / 60.0:.1f} | {100.0 * resources['min_soc']:.1f} | "
                     f"{resources['max_memory_bit'] / 1e9:.3f} | {resources['lost_bit'] / 1e9:.3f} | "
                     f"{resources['downlinked_bit'] / 1e9:.3f} |")
    lines += ["", f"Score ({plan.score.get('objective', '')}): {plan.score.get('value')}", "", "## Activities", "",
              "| Id | Spacecraft | Type | Start (UTC) | Duration [s] | Target or station | Off-nadir [deg] | "
              "Slew [deg] |", "|---|---|---|---|--:|---|--:|--:|"]
    for a in plan.activities:
        off = a.predicted.get("off_nadir_deg")
        slew = a.predicted.get("slew_deg")
        lines.append(f"| {a.id} | {a.spacecraft} | {a.type} | {a.start_utc} | {a.duration_s:.0f} | "
                     f"{a.target or a.station} | {'' if off is None else f'{off:.1f}'} | "
                     f"{'' if slew is None else f'{slew:.1f}'} |")
    lines += ["", "## Not scheduled", ""]
    if plan.unscheduled:
        lines += ["| Request | Spacecraft | Priority | Why |", "|---|---|--:|---|"]
        lines += [f"| {u.request} | {u.spacecraft} | {u.priority} | {u.text} |" for u in plan.unscheduled]
    else:
        lines.append("Every request is scheduled.")
    if plan.contention:
        lines += ["", "## Contested passes", "", "| Station | AOS (UTC) | Wanted by | Served |", "|---|---|---|---|"]
        lines += [f"| {c['station']} | {c['aos_utc']} | {', '.join(c['wanted_by'])} | {', '.join(c['served'])} |"
                  for c in plan.contention]
    if verification is not None:
        lines += ["", "## Plan against the simulation", ""] + verification.markdown()
    if plan.notes:
        lines += ["", "## Notes", ""] + [f"- {note}" for note in plan.notes]
    lines += ["", "## Provenance", "", "```json", json.dumps(provenance, indent=1, sort_keys=True), "```", ""]
    return "\n".join(lines)


def write_all(folder, planning, plan: Plan | None = None, verification=None) -> list[Path]:
    """Every product into ``folder``; returns the paths."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    plan = plan if plan is not None else planning.plan
    scenario, timebase, found = planning.scenario, planning.timebase, planning.opportunities
    paths = [write_passes_csv(folder / "passes.csv", plan, found, timebase)]
    ics = folder / "passes.ics"
    ics.write_bytes(passes_ics(plan, found, timebase).encode("utf-8"))
    paths.append(ics)
    paths.append(write_activities_csv(folder / "activities.csv", plan, timebase))
    path = folder / "activities.json"
    path.write_text(json.dumps(activities_json(plan, timebase), indent=1, sort_keys=True, allow_nan=False) + "\n",
                    encoding="utf-8")
    paths.append(path)
    path = folder / "commands.json"
    path.write_text(json.dumps(commands_json(plan, scenario, timebase), indent=1, allow_nan=False) + "\n",
                    encoding="utf-8")
    paths.append(path)
    paths.append(write_commands_csv(folder / "commands.csv", plan, scenario, timebase))
    paths.append(write_pointing_csv(folder / "pointing.csv", plan, scenario, found, timebase, planning.geometry))
    for name, text in oem(plan, planning.geometry, timebase).items():
        path = folder / f"{name}.oem"
        path.write_text(text, encoding="utf-8")
        paths.append(path)
    for name, text in aem(plan, planning).items():
        path = folder / f"{name}.aem"
        path.write_text(text, encoding="utf-8")
        paths.append(path)
    path = folder / "report.md"
    path.write_text(report(plan, timebase, verification), encoding="utf-8")
    paths.append(path)
    return paths
