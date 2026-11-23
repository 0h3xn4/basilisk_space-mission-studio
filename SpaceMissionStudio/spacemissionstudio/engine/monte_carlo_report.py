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

"""The files a Monte Carlo batch gives (Monte Carlo plan B5 and B7): the
batch report and the Runs table as CSV.

**The batch report** (:func:`build`, :func:`write`) holds, for one batch:
the settings (runs, processes, the batch seed and any command-line
override), the dispersions, the requirements with their verdicts, the
spread at the end, the outcome statistics (with the percentile method),
the sensitivity (with the measure), the crashed runs with what they drew,
and the provenance (the scenario's hash, the data files' hashes, the
versions). It is JSON (``kind: "monte_carlo_report"``, :data:`REPORT_FORMAT`)
or Markdown, by the file's suffix.

Every number comes from the functions the Monte Carlo view uses
(``monte_carlo_requirements.evaluate``, ``monte_carlo_statistics.insight``,
``monte_carlo_results.final_spread`` and ``node_spread``), and every cell of
the Markdown tables from the same text functions (``table_rows``,
``number_text``): no second implementation. The settings and the
dispersions are read from the batch folder's ``archive.provenance.json``
(``monte_carlo_settings``, written since this version); a batch made
before records neither, and the report says so.

**The Runs table** (:func:`write_runs_csv`) is the view's Runs table for
one spacecraft (or node, or profile), as CSV, with
``<file>.provenance.json`` beside it.

Basilisk-free and Qt-free: the command line writes both, and the GUI
writes them in a worker thread.
"""

from __future__ import annotations

import csv
import json
import math
from datetime import UTC, datetime
from pathlib import Path

from ..config import models
from . import monte_carlo_requirements as mcreq
from . import monte_carlo_results as mcr
from . import monte_carlo_statistics as mcs

REPORT_KIND = "monte_carlo_report"
REPORT_FORMAT = 1
SUFFIXES = (".json", ".md")
ARCHIVE_PROVENANCE = "archive.provenance.json"
# What a batch's archive.provenance.json records of its settings (engine.monte_carlo.archive_record).
SETTINGS_KEY = "monte_carlo_settings"
NOT_RECORDED = "not recorded: the batch was made before its settings were kept (SpaceMissionStudio 2.14.2 or earlier)"
# The unit of each dispersed quantity's bounds, mean and spread (schema.scenario.DispersionConfig).
DISPERSION_UNITS = {"dry_mass_kg": "kg", "attitude_sigma_bn": "rad", "orbit_elements": "per element",
                    "inertia_kg_m2": "kg*m^2", "angular_rate_bn_b": "deg/s", "drag_coeff": "-", "srp_coeff": "-"}


class MonteCarloReportError(Exception):
    """A report file that cannot be written or read back."""


def suffix_error(path: str | Path) -> str:
    """Why ``path`` cannot hold a report ("" when it can): the suffix
    chooses the format, ``.json`` or ``.md``."""
    suffix = Path(path).suffix.lower()
    if suffix in SUFFIXES:
        return ""
    return f"{path}: a Monte Carlo report is a .json or a .md file (the suffix chooses the format)"


def archive_provenance(folder: str | Path | None) -> dict | None:
    """The batch folder's ``archive.provenance.json``, or None when there is
    none or it cannot be read."""
    if folder is None:
        return None
    try:
        record = json.loads((Path(folder) / ARCHIVE_PROVENANCE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return record if isinstance(record, dict) else None


def _finite(value):
    """A number for JSON: None for NaN or infinity."""
    if value is None:
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def _model(choice: str, name: str) -> dict:
    return models.record(models.model(choice, name))


def _settings(batch, record: dict | None) -> dict:
    recorded = (record or {}).get(SETTINGS_KEY)
    settings = {"runs_requested": len(batch.runs) + len(batch.failed), "runs_succeeded": len(batch.runs),
                "runs_failed": len(batch.failed), "seed": batch.seed, "processes": None, "processes_used": None,
                "overrides": {}, "note": ""}
    if isinstance(recorded, dict):
        settings.update(runs_requested=recorded.get("num_runs", settings["runs_requested"]),
                        processes=recorded.get("thread_count"), processes_used=recorded.get("processes_used"),
                        overrides=dict(recorded.get("overrides") or {}))
    elif batch.kind == "orbit":
        settings["note"] = NOT_RECORDED
    else:
        settings["note"] = f"a {batch.kind} batch runs in this process: no processes, no overrides"
    return settings


def _dispersions(batch, record: dict | None) -> tuple[list[dict], str]:
    recorded = (record or {}).get(SETTINGS_KEY)
    if isinstance(recorded, dict) and isinstance(recorded.get("dispersions"), list):
        return [dict(d, unit=DISPERSION_UNITS.get(d.get("quantity"), "-")) for d in recorded["dispersions"]], ""
    if batch.kind != "orbit":
        return [], f"a {batch.kind} batch's draws are in its Runs table; its scenario holds the dispersions"
    return [], NOT_RECORDED


def _spread(batch) -> dict:
    statistic = _model(mcr.SPREAD_CHOICE, batch.spread_statistic)
    if batch.kind == "orbit":
        items = []
        for name in batch.spacecraft:
            s = mcr.final_spread(batch, name)
            items.append({"spacecraft": name, "radial_m": s.radial_m, "along_track_m": s.along_track_m,
                          "cross_track_m": s.cross_track_m, "altitude_min_m": s.altitude_min_m,
                          "altitude_max_m": s.altitude_max_m})
        return {"statistic": statistic, "at": "the end of the run", "items": items}
    unit = "degC"
    items = []
    for name in batch.items:
        s = mcr.node_spread(batch, name)
        if batch.kind == "operations":
            unit = batch.profile_units.get(name, "-")
        items.append({"item": name, "unit": unit, "lowest": s.coldest_c, "highest": s.hottest_c,
                      "sigma_of_lowest": s.sigma_min_k, "sigma_of_highest": s.sigma_max_k})
    return {"statistic": statistic, "at": "over the whole run", "items": items}


def _requirements(batch, results) -> dict:
    rows = []
    for r in results:
        rows.append({"name": r.name, "spacecraft": r.spacecraft, "outcome": r.outcome, "unit": r.unit,
                     "at_least": r.at_least, "at_most": r.at_most, "confidence": r.confidence,
                     "max_probability": r.max_probability, "evaluated": r.evaluated, "not_met": r.not_met,
                     "crashed": r.crashed, "not_evaluated": r.not_evaluated, "estimate": _finite(r.estimate),
                     "upper_bound": _finite(r.upper_bound), "verdict": r.verdict or None,
                     "not_met_runs": list(r.not_met_runs)})
    return {"probability_bound": _model(mcr.BOUND_CHOICE, batch.probability_bound), "results": rows}


def _statistics(insight: mcs.Insight) -> dict:
    outcomes = []
    for stat in insight.statistics:
        outcomes.append({"label": stat.label, "name": stat.name, "unit": stat.unit, "n": stat.n,
                         "minimum": _finite(stat.minimum),
                         "percentiles": [{"percentile": p, "value": _finite(v)}
                                         for p, v in zip(stat.percentiles, stat.values)],
                         "maximum": _finite(stat.maximum)})
    return {"percentile_method": _model(mcs.PERCENTILE_CHOICE, insight.method),
            "percentiles": list(insight.percentiles), "outcomes": outcomes}


def _sensitivity(insight: mcs.Insight) -> dict:
    return {"measure": _model(mcs.SENSITIVITY_CHOICE, insight.measure), "minimum_runs": mcs.MIN_PAIRS,
            "pairs": [{"drawn_value": pair.input_label, "outcome": pair.outcome_label,
                       "correlation": _finite(pair.value), "n": pair.n} for pair in insight.sensitivity]}


def _crashed(batch) -> list[dict]:
    return [{"run": int(run), "drawn": batch.failed_drawn.get(int(run))} for run in sorted(batch.failed)]


def _data_files(batch, record: dict | None) -> tuple[list[dict], str]:
    """Each data file the runs read, once per (kind, SHA-256), with the runs
    that read it; from the summary's ``data_files``, else the nominal run's
    record in the provenance."""
    found: dict[tuple[str, str], dict] = {}
    for row in batch.data_files:
        for kind, file in row.items():
            entry = found.setdefault((kind, file.get("sha256", "")),
                                     {"kind": kind, "sha256": file.get("sha256", ""), "path": file.get("path", ""),
                                      "runs": 0})
            entry["runs"] += 1
    if found:
        return [found[key] for key in sorted(found)], "each run's own (the batch summary)"
    nominal = ((record or {}).get("nominal_run") or {}).get("data_files")
    if isinstance(nominal, dict) and nominal:
        return ([{"kind": str(kind), "sha256": str(file.get("sha256", "")), "path": str(file.get("path", "")),
                  "runs": None} for kind, file in sorted(nominal.items()) if isinstance(file, dict)],
                "the nominal run's (the batch summary keeps none)")
    return [], "none recorded"


def _provenance(batch, folder, record: dict | None) -> dict:
    files, source = _data_files(batch, record)
    record = record or {}
    return {"batch_provenance": ARCHIVE_PROVENANCE if record else None,
            "scenario_name": record.get("scenario_name", batch.scenario_name),
            "scenario_sha256": record.get("scenario_sha256"), "scenario_file": record.get("scenario_file"),
            "scenario_file_sha256": record.get("scenario_file_sha256"),
            "versions": {"spacemissionstudio": record.get("spacemissionstudio_version"),
                         "basilisk": record.get("basilisk_version"),
                         "qualified_basilisk": record.get("qualified_basilisk_version"),
                         "dependencies": record.get("dependency_versions")},
            "batch_made_utc": record.get("created_utc"), "rng_seeds": record.get("rng_seeds"),
            "models": record.get("models"), "data_files": files, "data_files_source": source}


def build(batch: mcr.MonteCarloBatch, folder: str | Path | None = None,
          insight: mcs.Insight | None = None) -> dict:
    """The report of ``batch`` (saved in ``folder``, which holds its
    provenance), as a dict that JSON writes as it is. ``insight``: the
    view's statistics and sensitivity of the batch, when they are known;
    else they are worked out here, by the same function."""
    from .. import __version__

    record = archive_provenance(folder)
    insight = mcs.insight(batch) if insight is None else insight
    dispersions, dispersions_note = _dispersions(batch, record)
    node_limits = [mcreq.NodeLimitResult.from_dict(row).to_dict() for row in batch.node_limits]
    days = float(batch.time_s[-1]) / 86400.0 if batch.time_s.size else 0.0
    return {
        "kind": REPORT_KIND,
        "format": REPORT_FORMAT,
        "spacemissionstudio_version": __version__,
        "created_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "batch": {"scenario_name": batch.scenario_name, "kind": batch.kind,
                  "folder": str(Path(folder).resolve()) if folder is not None else None,
                  "epoch_utc": batch.epoch_utc or None, "duration_days": days, "items": batch.items,
                  "case": batch.case or None},
        "settings": _settings(batch, record),
        "dispersions": dispersions,
        "dispersions_note": dispersions_note,
        "spread": _spread(batch),
        "requirements": _requirements(batch, mcreq.evaluate(batch)),
        "node_limits": {"probability_bound": _model(mcr.BOUND_CHOICE, batch.probability_bound),
                        "results": node_limits} if node_limits else None,
        "outcome_statistics": _statistics(insight),
        "sensitivity": _sensitivity(insight),
        "crashed_runs": _crashed(batch),
        "provenance": _provenance(batch, folder, record),
    }


# -- Markdown -----------------------------------------------------------------------------------------


def _cell(value) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _table(headers, rows, numeric=()) -> list[str]:
    """A Markdown table: the columns ``numeric`` right-aligned (numbers),
    the others left-aligned."""
    numeric = set(numeric)
    align = ["---:" if k in numeric else "---" for k in range(len(headers))]
    lines = ["| " + " | ".join(_cell(h) for h in headers) + " |", "| " + " | ".join(align) + " |"]
    lines += ["| " + " | ".join(_cell(c) for c in row) + " |" for row in rows]
    return lines


def _model_line(record: dict) -> str:
    references = "; ".join(reference.rstrip(".") for reference in record["references"])
    return f"{record['title']} (`{record['model']}`): {record['method'].rstrip('.')}. Source: {references}."


def _overrides_text(overrides: dict) -> str:
    if not overrides:
        return "none"
    return "; ".join(f"{name} {change.get('scenario')} in the scenario, {change.get('batch')} for this batch"
                     for name, change in sorted(overrides.items()))


def _dispersion_rows(dispersions: list[dict]) -> list[tuple]:
    rows = []
    for d in dispersions:
        bounds = d.get("bounds")
        spread = d.get("element_spread")
        rows.append((d.get("spacecraft", ""), d.get("quantity", ""), d.get("kind", ""), d.get("unit", "-"),
                     "" if not bounds else f"{bounds[0]:g} to {bounds[1]:g}",
                     "" if d.get("mean") is None else f"{d['mean']:g}",
                     "" if d.get("std_deviation") is None else f"{d['std_deviation']:g}",
                     "" if not spread else ", ".join(f"{key} {value:g}" for key, value in spread.items()),
                     "" if d.get("angle_std_deg") is None else f"{d['angle_std_deg']:g}"))
    return rows


def _spread_lines(spread: dict) -> list[str]:
    lines = [f"Statistic: {spread['statistic']['title']}, {spread['at']}.", ""]
    if spread["items"] and "spacecraft" in spread["items"][0]:
        rows = [(s["spacecraft"], mcr.format_km(s["along_track_m"]).removesuffix(" km"),
                 mcr.format_km(s["radial_m"]).removesuffix(" km"), mcr.format_km(s["cross_track_m"]).removesuffix(" km"),
                 f"{s['altitude_min_m'] / 1e3:.3f}", f"{s['altitude_max_m'] / 1e3:.3f}") for s in spread["items"]]
        return lines + _table(("Spacecraft", "Along-track 1-sigma [km]", "Radial 1-sigma [km]",
                               "Cross-track 1-sigma [km]", "Lowest altitude [km]", "Highest altitude [km]"), rows,
                               numeric=range(1, 6))
    rows = [(s["item"], s["unit"], f"{s['lowest']:.4g}", f"{s['highest']:.4g}", f"{s['sigma_of_lowest']:.3g}",
             f"{s['sigma_of_highest']:.3g}") for s in spread["items"]]
    return lines + _table(("Item", "Unit", "Lowest", "Highest", "1-sigma of the lowest", "1-sigma of the highest"),
                          rows, numeric=range(2, 6))


def markdown(report: dict, batch: mcr.MonteCarloBatch) -> str:
    """``report`` (:func:`build` of ``batch``) as a Markdown page. The
    requirements and node limits are written by the text functions the
    view and the command line use (``table_rows``, ``node_limit_rows``)."""
    batch_info, settings = report["batch"], report["settings"]
    lines = [f"# Monte Carlo report: {batch_info['scenario_name']}", "",
             f"Made by SpaceMissionStudio {report['spacemissionstudio_version']} on {report['created_utc']}"
             + (f" from the batch in `{batch_info['folder']}`." if batch_info["folder"] else "."), ""]
    lines += ["## Settings", ""]
    rows = [("Kind of batch", batch_info["kind"]), ("Run length [day]", f"{batch_info['duration_days']:.6g}"),
            ("Runs asked for", settings["runs_requested"]), ("Runs that succeeded", settings["runs_succeeded"]),
            ("Runs that failed", settings["runs_failed"]),
            ("Processes asked for", "not recorded" if settings["processes"] is None else settings["processes"]),
            ("Processes used", "not recorded" if settings["processes_used"] is None else settings["processes_used"]),
            ("Batch seed", "none (Basilisk's own seeding)" if settings["seed"] is None else settings["seed"]),
            ("Command-line overrides", _overrides_text(settings["overrides"]))]
    if batch_info.get("case"):
        rows.insert(1, ("Case", batch_info["case"]))
    lines += _table(("Setting", "Value"), rows)
    if settings["note"]:
        lines += ["", f"Note: {settings['note']}."]
    lines += ["", "## Dispersions", ""]
    if report["dispersions"]:
        lines += _table(("Spacecraft", "Quantity", "Kind", "Unit", "Bounds", "Mean", "Standard deviation",
                         "Element spread", "Angle 1-sigma [deg]"), _dispersion_rows(report["dispersions"]),
                        numeric=())
    else:
        lines.append(f"None listed: {report['dispersions_note']}.")
    lines += ["", "## Spread", ""] + _spread_lines(report["spread"])

    lines += ["", "## Requirements", ""]
    requirements = report["requirements"]
    if requirements["results"]:
        lines += [f"Bound: {_model_line(requirements['probability_bound'])} A crashed run counts as not meeting "
                  "every requirement; a run that did not record the outcome is not evaluated.", ""]
        results = mcreq.evaluate(batch)
        rows = mcreq.table_rows(results, len(batch.spacecraft) > 1)
        lines += _table(mcreq.TABLE_HEADER, rows, numeric=range(3, 11))
    else:
        lines.append("None in this batch.")
    if report.get("node_limits"):
        limits = report["node_limits"]
        results = [mcreq.NodeLimitResult.from_dict(row) for row in limits["results"]]
        lines += ["", "## Node limits", "", f"Bound: {_model_line(limits['probability_bound'])} A failed run counts "
                  "as leaving every range.", ""]
        lines += _table(mcreq.NODE_LIMITS_HEADER, mcreq.node_limit_rows(results), numeric=range(2, 10))

    statistics = report["outcome_statistics"]
    lines += ["", "## Outcome statistics", "", f"Percentiles: {_model_line(statistics['percentile_method'])} "
              "N is the runs that recorded the outcome; a crashed run is not in N.", ""]
    if statistics["outcomes"]:
        headers = (["Outcome", "Unit", "N", "Minimum"] + [mcs.percentile_title(p) for p in statistics["percentiles"]]
                   + ["Maximum"])
        rows = [(o["name"], o["unit"], o["n"], mcs.number_text(o["minimum"]),
                 *(mcs.number_text(p["value"]) for p in o["percentiles"]), mcs.number_text(o["maximum"]))
                for o in statistics["outcomes"]]
        lines += _table(headers, rows, numeric=range(2, len(headers)))
    else:
        lines.append("This batch keeps no outcome of its runs.")
    sensitivity = report["sensitivity"]
    title = sensitivity["measure"]["title"]
    lines += ["", "## Sensitivity", "", f"Measure: {_model_line(sensitivity['measure'])} N is the runs that recorded "
              f"both; {mcs.NO_VALUE} where a value does not vary or fewer than {sensitivity['minimum_runs']} runs "
              "recorded both. Sorted by size, whatever the sign. A correlation is not a cause.", ""]
    if sensitivity["pairs"]:
        lines += _table(("Drawn value", "Outcome", f"{title} [-]", "N"),
                        [(p["drawn_value"], p["outcome"], mcs.number_text(p["correlation"]), p["n"])
                         for p in sensitivity["pairs"]], numeric=(2, 3))
    else:
        lines.append("Nothing to correlate: the batch keeps no drawn values, or no outcome, of its runs.")

    lines += ["", "## Crashed runs", ""]
    crashed = report["crashed_runs"]
    if crashed:
        labels: list[str] = []
        for case in crashed:
            labels += [label for label in (case["drawn"] or {}) if label not in labels]
        rows = [(case["run"], *(mcs.number_text((case["drawn"] or {}).get(label)) if case["drawn"] is not None
                                else "not kept" for label in labels)) for case in crashed]
        lines += _table(["Run"] + labels, rows, numeric=range(len(labels) + 1))
    else:
        lines.append("None.")

    provenance = report["provenance"]
    versions = provenance["versions"]
    lines += ["", "## Provenance", ""]
    rows = [("Batch provenance file", provenance["batch_provenance"] or "none in the batch folder"),
            ("Scenario", provenance["scenario_name"]), ("Scenario SHA-256", provenance["scenario_sha256"] or "not recorded"),
            ("Scenario file", provenance["scenario_file"] or "not recorded"),
            ("Scenario file SHA-256", provenance["scenario_file_sha256"] or "not recorded"),
            ("Batch made [UTC]", provenance["batch_made_utc"] or "not recorded"),
            ("SpaceMissionStudio (batch)", versions["spacemissionstudio"] or "not recorded"),
            ("Basilisk (batch)", versions["basilisk"] or "not recorded"),
            ("SpaceMissionStudio (report)", report["spacemissionstudio_version"])]
    lines += _table(("Item", "Value"), rows)
    lines += ["", f"Data files: {provenance['data_files_source']}.", ""]
    if provenance["data_files"]:
        lines += _table(("Kind", "SHA-256", "Runs", "Path"),
                        [(f["kind"], f["sha256"], "nominal" if f["runs"] is None else f["runs"], f["path"])
                         for f in provenance["data_files"]], numeric=(2,))
    return "\n".join(lines).rstrip() + "\n"


def write(batch: mcr.MonteCarloBatch, path: str | Path, folder: str | Path | None = None,
          insight: mcs.Insight | None = None) -> Path:
    """Write the report of ``batch`` to ``path``: JSON for ``.json``,
    Markdown for ``.md`` (:func:`suffix_error`). Returns the path."""
    path = Path(path)
    problem = suffix_error(path)
    if problem:
        raise MonteCarloReportError(problem)
    report = build(batch, folder, insight)
    if path.suffix.lower() == ".json":
        text = json.dumps(report, indent=1, allow_nan=False) + "\n"
    else:
        text = markdown(report, batch)
    path.write_text(text, encoding="utf-8")
    return path


def load(path: str | Path) -> dict:
    """A JSON report written by :func:`write`, checked for its kind and format."""
    path = Path(path)
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise MonteCarloReportError(f"could not read {path}: {exc}") from exc
    if not isinstance(report, dict) or report.get("kind") != REPORT_KIND:
        raise MonteCarloReportError(f"{path} is not a Monte Carlo report (kind {REPORT_KIND!r})")
    if report.get("format") != REPORT_FORMAT:
        raise MonteCarloReportError(f"{path} is a format-{report.get('format')} Monte Carlo report; this version "
                                    f"reads format {REPORT_FORMAT}")
    return report


# -- the Runs table ----------------------------------------------------------------------------------


def write_runs_csv(batch: mcr.MonteCarloBatch, path: str | Path, item: str | None = None,
                   folder: str | Path | None = None) -> Path:
    """The Runs table of ``batch`` for ``item`` (a spacecraft, node or
    profile; by default the first) as CSV, with ``<file>.provenance.json``
    beside it: the batch's own provenance (``archive.provenance.json``)
    when ``folder`` has one. A value a run does not have is ``nan``."""
    from .. import output_provenance

    path = Path(path)
    labels, rows = mcr.run_table(batch, item, outcomes=batch.kind in ("orbit", "thermal"))
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(labels)
        for row in rows:
            writer.writerow([int(row[0])] + [value if isinstance(value, str) else f"{value:.9g}" for value in row[1:]])
    archive = archive_provenance(folder)
    output_provenance.write_sidecar(path, {
        "export": "Monte Carlo runs table", "spacecraft": item, "runs": len(rows),
        "batch_folder": str(folder) if folder is not None else "",
        "batch_provenance": archive if archive is not None else
        "not found: the batch folder's archive.provenance.json"})
    return path
