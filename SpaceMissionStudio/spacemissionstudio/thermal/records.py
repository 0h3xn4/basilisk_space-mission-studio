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
"""The thermal analysis's outputs with their provenance, like every
other analysis's (``engine.analysis_records``): a JSON record, its
tables as CSV (summary, heaters, radiators, orbit-average heat flows),
and the temperature and heat-flow series as CSV, each with a provenance
sidecar."""

from __future__ import annotations

import csv
from pathlib import Path

from .. import output_provenance
from ..analyses import records as analysis_tables
from ..engine.analysis_records import _plain, _provenance

THERMAL_KIND = "thermal_analysis"
_METHOD = ("lumped-parameter network on the 3D model's parts; per-facet sunlight, albedo (Basilisk's albedo "
           "module) and planetary infrared (plate-to-sphere view factor); BDF2 with Newton; orbit-periodic "
           "start (docs/models/thermal.md)")


def tables(analysis) -> dict[str, list[dict]]:
    """``{name: rows}``: per case the node summary, the heaters, the
    radiators and the orbit-average heat flows."""
    summary, heaters, radiators, flows = [], [], [], []
    for case in analysis.cases:
        for node in case.summary:
            summary.append({"case": case.name, "node": node.name, "min_c": node.min_c, "max_c": node.max_c,
                            "mean_c": node.mean_c,
                            "operating_low_c": None if node.operating_c is None else node.operating_c[0],
                            "operating_high_c": None if node.operating_c is None else node.operating_c[1],
                            "cold_margin_k": node.cold_margin_k, "hot_margin_k": node.hot_margin_k})
        for heater in case.heaters:
            heaters.append({"case": case.name, "heater": heater.name, "node": heater.node,
                            "power_w": heater.power_w, "duty": heater.duty, "energy_wh": heater.energy_wh,
                            "orbit_average_w": heater.orbit_average_w, "sized_w": heater.sized_w})
        for radiator in case.radiators:
            radiators.append({"case": case.name, "node": radiator.node, "area_m2": radiator.area_m2,
                              "emitted_w": radiator.emitted_w, "absorbed_w": radiator.absorbed_w,
                              "rejected_w": radiator.rejected_w})
        for node, values in case.orbit_average.items():
            flows.append({"case": case.name, "node": node} | {f"{k}_w": v for k, v in values.items()
                                                               if not k.startswith(("conductor ", "heat pipe ",
                                                                                    "link "))})
    out = {"thermal_summary": summary}
    if heaters:
        out["thermal_heaters"] = heaters
    if radiators:
        out["thermal_radiators"] = radiators
    out["thermal_heat_flows"] = flows
    return out


def record(scenario, analysis, result=None) -> dict:
    """The JSON record of a thermal analysis."""
    prepared = analysis.prepared
    env = prepared.environment
    record_ = {
        "kind": THERMAL_KIND,
        "spacecraft": analysis.spacecraft,
        "inputs": {"thermal": _plain(prepared.spacecraft.thermal)},
        "model": {"method": _METHOD, "central_body": env.central_body, "inclination_deg": env.inclination_deg,
                  "inclination_band": env.band, "period_s": env.period_s,
                  "beta_deg": {"min": float(env.beta_deg.min()), "max": float(env.beta_deg.max())},
                  "facets": len(prepared.geometry.facets)},
        "results": {
            "cases": [{"name": c.name, "notes": c.notes,
                       "capacitance": dict(zip(c.network.names, c.network.capacitance_how, strict=True)),
                       "start": c.solution.start,
                       "periodic": None if c.solution.periodic is None else _plain(c.solution.periodic),
                       "energy_residual_j": c.solution.energy_residual_j,
                       "energy_throughput_j": c.solution.energy_throughput_j,
                       "step_check_k": c.solution.step_check_k,
                       "events": [_plain(e) for e in c.events]} for c in analysis.cases],
            "tables": tables(analysis)},
        "findings": [f.to_dict() if hasattr(f, "to_dict") else {"message": str(f)} for f in analysis.findings()],
        "provenance": _provenance(scenario, {}),
    }
    if result is not None and getattr(result, "provenance", None) is not None:
        record_["provenance"]["run"] = _plain(result.provenance_record())
    return record_


def write_tables(analysis, folder, record_: dict) -> list[Path]:
    """The tables (:func:`tables`) and every case's series as CSV in
    ``folder``, each with its provenance sidecar; returns the paths."""
    folder = Path(folder)
    written = analysis_tables.write_tables(tables(analysis), folder, record_)
    for case in analysis.cases:
        for series in case.series("thermal"):
            path = folder / (series.name.replace(".", "_").replace(" ", "_") + ".csv")
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["time_s", *[f"{c} [{series.units}]" for c in series.columns]])
                for t, row in zip(series.time_s, series.data, strict=True):
                    writer.writerow([f"{t:.3f}", *[f"{v:.6g}" for v in row]])
            output_provenance.write_sidecar(path, dict(_plain(record_["provenance"]), kind=record_["kind"],
                                                       series=series.name, spacecraft=record_["spacecraft"]))
            written.append(path)
    return written
