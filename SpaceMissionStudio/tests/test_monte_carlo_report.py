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

"""The batch report and the Runs table as files (Monte Carlo plan B5,
decision MC-32): the report's numbers are the view's (the same functions),
it reads back, Markdown and JSON by the suffix, an older batch's report
says what it does not record. Basilisk-free."""

import csv
import json
import math
from dataclasses import replace

import numpy as np
import pytest

from spacemissionstudio.engine import monte_carlo_report as report
from spacemissionstudio.engine import monte_carlo_requirements as mcreq
from spacemissionstudio.engine import monte_carlo_results as mcr
from spacemissionstudio.engine import monte_carlo_statistics as mcs

_R_M = 6778.0e3  # [m] orbit radius
_N_RAD_S = math.sqrt(3.986004415e14 / _R_M ** 3)  # [rad/s] mean motion
_ALTITUDE = {"name": "R-ALT", "spacecraft": "sat-1", "outcome": "lowest_altitude", "at_least": 400.0,
             "at_most": None, "confidence": 0.9, "max_probability": 0.5}
_DECAY = {"name": "R-DECAY", "spacecraft": "sat-1", "outcome": "mean_sma_change", "at_least": -0.02,
          "at_most": None, "confidence": 0.9, "max_probability": None}


def _batch(runs=6):
    """``runs`` successful runs 0.1 mrad apart along track, drawing Cd and a
    dry mass, with two outcomes; run ``runs`` crashed with its draws."""
    t = np.linspace(0.0, 3000.0, 20)  # [s]
    phase = (np.arange(runs) - (runs - 1) / 2) * 1e-4  # [rad]
    u = _N_RAD_S * t[None, :] + phase[:, None]
    r = np.stack([_R_M * np.cos(u), _R_M * np.sin(u), np.zeros_like(u)], axis=-1)
    v = np.stack([-_R_M * _N_RAD_S * np.sin(u), _R_M * _N_RAD_S * np.cos(u), np.zeros_like(u)], axis=-1)
    drawn = [{"sat-1 drag coefficient [-]": 2.2 + 0.1 * k, "sat-1 dry mass [kg]": 150.0 + (-1) ** k * k}
             for k in range(runs)]
    outcomes = [{"run_length": 1.0, "sat-1.lowest_altitude": 395.0 + 5.0 * k, "sat-1.mean_sma_change": -0.01 * k}
                for k in range(runs)]
    return mcr.MonteCarloBatch("Report batch", "earth", t, list(range(runs)), [runs], {"sat-1": r}, {"sat-1": v},
                               drawn, "2030-01-01T00:00:00", outcomes=outcomes,
                               outcome_units={"run_length": "h", "sat-1.lowest_altitude": "km",
                                              "sat-1.mean_sma_change": "km"},
                               failed_drawn={runs: {"sat-1 drag coefficient [-]": 3.0, "sat-1 dry mass [kg]": 140.0}},
                               requirements=[dict(_ALTITUDE), dict(_DECAY)], seed=37,
                               data_files=[{"spice:de430.bsp": {"path": "/data/de430.bsp", "sha256": "ab" * 32}}
                                           for _ in range(runs)])


def _provenance(folder, **settings):
    record = {"scenario_name": "Report batch", "scenario_sha256": "cd" * 32, "scenario_file": "s.json",
              "scenario_file_sha256": "ef" * 32, "spacemissionstudio_version": "9.9.9", "basilisk_version": "2.12.0",
              "created_utc": "2030-01-01T00:00:00+00:00", "monte_carlo_seed": 37}
    if settings:
        record["monte_carlo_settings"] = settings
    (folder / "archive.provenance.json").write_text(json.dumps(record), encoding="utf-8")


_SETTINGS = {"num_runs": 7, "thread_count": 4, "processes_used": 2, "seed": 37,
             "dispersions": [{"spacecraft": "sat-1", "quantity": "drag_coeff", "kind": "uniform",
                              "bounds": [2.2, 3.0], "mean": None, "std_deviation": None, "element_spread": None,
                              "angle_std_deg": None}],
             "overrides": {"num_runs": {"scenario": 20, "batch": 7}}}


def test_the_reports_numbers_are_the_views_and_it_reads_back(tmp_path):
    """Every number of the JSON report is what the view's functions give:
    the requirements (evaluate), the statistics and the sensitivity
    (insight, by the batch's choices), the spread (final_spread); the
    crashed run with its draws; the settings and dispersions from the
    batch's provenance. Read back, it is the same report."""
    batch = _batch()
    mcr.save(batch, tmp_path)
    _provenance(tmp_path, **_SETTINGS)
    batch = mcr.load(tmp_path)
    path = report.write(batch, tmp_path / "report.json", tmp_path)
    read = report.load(path)
    assert read == json.loads(path.read_text(encoding="utf-8"))
    assert read["kind"] == "monte_carlo_report" and read["format"] == report.REPORT_FORMAT
    from spacemissionstudio import __version__

    assert read["spacemissionstudio_version"] == __version__ and read["created_utc"].endswith("Z")

    settings = read["settings"]
    assert (settings["runs_requested"], settings["runs_succeeded"], settings["runs_failed"]) == (7, 6, 1)
    assert (settings["processes"], settings["processes_used"], settings["seed"]) == (4, 2, 37)
    assert settings["overrides"] == {"num_runs": {"scenario": 20, "batch": 7}} and settings["note"] == ""
    assert read["dispersions"][0]["quantity"] == "drag_coeff" and read["dispersions"][0]["unit"] == "-"

    results = mcreq.evaluate(batch)
    for row, result in zip(read["requirements"]["results"], results, strict=True):
        assert (row["name"], row["evaluated"], row["not_met"], row["crashed"]) == (
            result.name, result.evaluated, result.not_met, result.crashed)
        assert row["estimate"] == result.estimate and row["upper_bound"] == result.upper_bound
        assert row["verdict"] == (result.verdict or None) and row["not_met_runs"] == list(result.not_met_runs)
    assert read["requirements"]["probability_bound"]["model"] == "clopper_pearson"

    insight = mcs.insight(batch)
    stats = read["outcome_statistics"]
    assert stats["percentile_method"]["model"] == "linear" and stats["percentiles"] == [1.0, 5.0, 50.0, 95.0, 99.0]
    for row, stat in zip(stats["outcomes"], insight.statistics, strict=True):
        assert (row["label"], row["n"], row["minimum"], row["maximum"]) == (stat.label, stat.n, stat.minimum,
                                                                            stat.maximum)
        assert [p["value"] for p in row["percentiles"]] == list(stat.values)
    altitude = next(row for row in stats["outcomes"] if row["name"] == "sat-1 lowest altitude")
    assert [p["value"] for p in altitude["percentiles"]] == list(
        np.percentile(395.0 + 5.0 * np.arange(6), [1, 5, 50, 95, 99], method="linear"))
    pairs = read["sensitivity"]["pairs"]
    assert read["sensitivity"]["measure"]["model"] == "spearman"
    assert [(p["drawn_value"], p["outcome"], p["correlation"], p["n"]) for p in pairs] == [
        (s.input_label, s.outcome_label, s.value, s.n) for s in insight.sensitivity]

    spread = mcr.final_spread(batch, "sat-1")
    (item,) = read["spread"]["items"]
    assert item["along_track_m"] == spread.along_track_m and item["altitude_min_m"] == spread.altitude_min_m
    assert read["crashed_runs"] == [{"run": 6, "drawn": {"sat-1 drag coefficient [-]": 3.0,
                                                         "sat-1 dry mass [kg]": 140.0}}]
    provenance = read["provenance"]
    assert provenance["scenario_sha256"] == "cd" * 32 and provenance["versions"]["spacemissionstudio"] == "9.9.9"
    assert provenance["data_files"] == [{"kind": "spice:de430.bsp", "sha256": "ab" * 32, "path": "/data/de430.bsp",
                                         "runs": 6}]


def test_the_report_takes_the_views_statistics_when_they_are_known(tmp_path):
    """Given the view's insight, the report writes it as it is (no second
    computation); its numbers then equal the view's by construction."""
    batch = _batch()
    insight = mcs.insight(batch)
    built = report.build(batch, None, insight)
    assert built["outcome_statistics"]["outcomes"][0]["minimum"] == insight.statistics[0].minimum
    stub = replace(insight, statistics=insight.statistics[:1])
    assert len(report.build(batch, None, stub)["outcome_statistics"]["outcomes"]) == 1


def test_the_markdown_report_has_the_views_tables(tmp_path):
    """Markdown for a .md file: each section a table whose cells are the
    view's text (the requirements by table_rows, the statistics and the
    correlations by number_text)."""
    batch = _batch()
    mcr.save(batch, tmp_path)
    _provenance(tmp_path, **_SETTINGS)
    batch = mcr.load(tmp_path)
    text = report.write(batch, tmp_path / "report.md", tmp_path).read_text(encoding="utf-8")
    assert text.startswith("# Monte Carlo report: Report batch\n")
    for heading in ("## Settings", "## Dispersions", "## Spread", "## Requirements", "## Outcome statistics",
                    "## Sensitivity", "## Crashed runs", "## Provenance"):
        assert f"\n{heading}\n" in text
    for cells in mcreq.table_rows(mcreq.evaluate(batch), False):
        assert "| " + " | ".join(cells) + " |" in text
    insight = mcs.insight(batch)
    headers, rows = mcs.statistics_table(insight)
    assert "| " + " | ".join(headers) + " |" in text
    for cells in rows:
        assert "| " + " | ".join(cells) + " |" in text
    for cells in mcs.sensitivity_table(insight)[1]:
        assert "| " + " | ".join(cells) + " |" in text
    assert "| Batch seed | 37 |" in text and "| Processes used | 2 |" in text
    assert "num_runs 20 in the scenario, 7 for this batch" in text
    assert "| 6 | 3 | 140 |" in text  # the crashed run and what it drew
    assert "(`spearman`)" in text and "(`linear`)" in text and "(`clopper_pearson`)" in text  # each model named


def test_an_older_batch_says_what_it_does_not_record(tmp_path):
    """A batch made before its settings were kept (no monte_carlo_settings,
    or no provenance at all): the report says the processes and the
    dispersions are not recorded; the numbers are still there."""
    batch = _batch()
    built = report.build(batch, tmp_path)  # no archive.provenance.json
    assert built["settings"]["processes"] is None and built["settings"]["note"] == report.NOT_RECORDED
    assert built["dispersions"] == [] and built["dispersions_note"] == report.NOT_RECORDED
    assert built["provenance"]["batch_provenance"] is None and built["provenance"]["scenario_sha256"] is None
    assert built["settings"]["runs_requested"] == 7 and built["settings"]["seed"] == 37
    _provenance(tmp_path)
    assert report.build(batch, tmp_path)["provenance"]["scenario_sha256"] == "cd" * 32
    text = report.markdown(report.build(batch, tmp_path), batch)
    assert "| Processes asked for | not recorded |" in text and "None listed: not recorded" in text


def test_the_suffix_chooses_the_format_and_other_files_are_refused(tmp_path):
    """.json and .md (any case); any other suffix is refused before
    anything is written; a file that is not a report does not load."""
    assert report.suffix_error("a.json") == report.suffix_error("b.MD") == ""
    assert "a .json or a .md file" in report.suffix_error("c.txt")
    with pytest.raises(report.MonteCarloReportError, match="a .json or a .md file"):
        report.write(_batch(), tmp_path / "report.txt")
    assert not (tmp_path / "report.txt").exists()
    other = tmp_path / "other.json"
    other.write_text(json.dumps({"kind": "thermal_analysis"}), encoding="utf-8")
    with pytest.raises(report.MonteCarloReportError, match="is not a Monte Carlo report"):
        report.load(other)
    other.write_text(json.dumps({"kind": "monte_carlo_report", "format": 99}), encoding="utf-8")
    with pytest.raises(report.MonteCarloReportError, match="format-99"):
        report.load(other)


def test_a_value_that_is_not_a_number_is_null_in_the_json(tmp_path):
    """No NaN in the JSON (written with allow_nan=False): a correlation
    without a value and a run without an outcome are null."""
    batch = _batch()
    batch = replace(batch, drawn=[{**row, "sat-1 dry mass [kg]": 150.0} for row in batch.drawn])
    path = report.write(batch, tmp_path / "report.json")
    pairs = report.load(path)["sensitivity"]["pairs"]
    assert any(pair["correlation"] is None for pair in pairs)
    assert "NaN" not in path.read_text(encoding="utf-8")


def test_a_thermal_batch_reports_its_node_limits(tmp_path):
    """A thermal batch: the nodes' spread, the node limits as kept, its
    statistics; no dispersions or processes, and the report says why."""
    t = np.linspace(0.0, 600.0, 5)
    temperatures = np.array([[20.0, 25.0, 31.0, 22.0, 21.0], [19.0, 24.0, 28.0, 23.0, 20.0],
                             [18.0, 22.0, 26.0, 21.0, 19.0]])
    limits = mcreq.node_limits({"battery": {"operating": [0.0, 30.0], "survival": None}},
                               {"battery": [(row.min(), row.max()) for row in temperatures]}, [0, 1, 2], [], 0.9)
    batch = mcr.MonteCarloBatch("Thermal", "earth", t, [0, 1, 2], [], {}, {},
                                [{"battery capacity [J/K]": 900.0 + 10 * k} for k in range(3)], kind="thermal",
                                temperatures_c={"battery": temperatures}, case="hot",
                                node_limits=[row.to_dict() for row in limits])
    built = report.build(batch)
    assert built["node_limits"]["results"][0]["outside"] == 1 and built["batch"]["case"] == "hot"
    assert built["spread"]["items"][0]["highest"] == 31.0
    assert built["dispersions"] == [] and "thermal batch" in built["dispersions_note"]
    text = report.markdown(built, batch)
    assert "## Node limits" in text and "| battery | operating |" in text


def test_the_runs_table_is_written_as_the_view_writes_it(tmp_path):
    """The CSV is run_table with the outcomes, crashed runs and verdicts; a
    missing value is nan; the provenance sidecar has the batch's own."""
    batch = _batch()
    _provenance(tmp_path, **_SETTINGS)
    path = report.write_runs_csv(batch, tmp_path / "runs.csv", folder=tmp_path)
    rows = list(csv.reader(path.open(encoding="utf-8")))
    labels, table = mcr.run_table(batch, None, outcomes=True)
    assert rows[0] == labels and len(rows) == len(table) + 1
    assert rows[-1][0] == "6" and rows[-1][labels.index("sat-1 lowest altitude [km]")] == "nan"
    assert rows[-1][labels.index(mcr.STATUS_LABEL)] == mcr.CRASHED
    sidecar = json.loads((tmp_path / "runs.csv.provenance.json").read_text(encoding="utf-8"))
    assert sidecar["export"] == "Monte Carlo runs table" and sidecar["batch_provenance"]["scenario_sha256"] == "cd" * 32
