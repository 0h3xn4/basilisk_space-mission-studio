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
"""Thermal studies (Phase 2, T-36) on template 33's run: a sweep's points
are the single cases they stand for; the one-at-a-time sensitivity is the
central difference of two single cases and ranks the radiator's optics
first for the avionics; the thermal Monte Carlo draws the same values from
the same seed, saves a batch the Monte Carlo summary reads back, and gives
the run table and plots the Monte Carlo view shows; the API and the
command line reach all three."""

import copy
import re

import numpy as np
import pytest

from spacemissionstudio import api, cli
from spacemissionstudio.engine import monte_carlo_results as mcr
from spacemissionstudio.schema.thermal import ThermalDispersionConfig, ThermalMonteCarloConfig
from spacemissionstudio.thermal import analysis, cases, sweeps

pytestmark = pytest.mark.requires_basilisk

_RADIATOR = "faces[radiator].absorptance"


@pytest.fixture(scope="module")
def prepared():
    scenario = api.load(api.template("33_microsat_thermal"))
    scenario.spacecraft[0].thermal.monte_carlo = ThermalMonteCarloConfig(
        runs=6, seed=7, case="nominal",
        dispersions=[ThermalDispersionConfig(_RADIATOR, 0.2, relative=True),
                     ThermalDispersionConfig("heat_pipes[avionics heat pipe].conductance_w_k", 1.0, "uniform")])
    scenario.validate()
    result = api.run(scenario)
    return scenario, result, analysis.prepare(scenario, result, "microsat-1")


def _nominal(prep):
    return next(c for c in cases.cases_of(prep.spacecraft.thermal) if c.name == "nominal")


def _single(prep, overrides):
    case = copy.deepcopy(_nominal(prep))
    case.overrides.update(overrides)
    return {n.name: n for n in analysis.solve_case(prep, case, size_heaters=False, step_check=False).summary}


def test_a_sweep_point_is_the_single_case_it_stands_for(prepared):
    """The radiator's absorptance (silvered Teflon, 0.08 in the library)
    swept 0.05, 0.2, 0.35: each point equals the case solved with that
    override; the avionics warm as the radiator absorbs more."""
    _scenario, _result, prep = prepared
    assert sweeps.current_value(sweeps._resolved(prep, _nominal(prep)), _RADIATOR, prep.spacecraft) == 0.08
    points = sweeps.sweep(prep, _nominal(prep), _RADIATOR, [0.05, 0.2, 0.35])
    for point in points:
        single = _single(prep, {_RADIATOR: point.value})
        for node in point.summary:
            assert node.max_c == pytest.approx(single[node.name].max_c, abs=1e-9)
    avionics = [next(n.mean_c for n in p.summary if n.name == "avionics") for p in points]
    assert avionics[0] < avionics[1] < avionics[2]
    with pytest.raises(sweeps.SweepError, match="has no item 'ghost'"):
        sweeps.sweep(prep, _nominal(prep), "faces[ghost].absorptance", [0.1])


def test_sensitivity_is_the_central_difference_of_two_single_cases(prepared):
    """The heat pipe's conductance +-20 %: the change equals the two single
    cases' difference; over the default parameters the avionics' largest
    driver is the radiator (its optics or the heat pipe), and parameters
    with no number (a power-budget dissipation) are left out with a note."""
    _scenario, _result, prep = prepared
    path = "heat_pipes[avionics heat pipe].conductance_w_k"
    rows, notes = sweeps.sensitivity(prep, _nominal(prep), [path], relative=0.2)
    assert notes == [] and rows[0].value == 8.0 and rows[0].step == pytest.approx(1.6)
    up, down = _single(prep, {path: 9.6}), _single(prep, {path: 6.4})
    assert rows[0].changes["avionics"][1] == pytest.approx(up["avionics"].max_c - down["avionics"].max_c, abs=1e-9)
    assert rows[0].per_unit("avionics")[1] == pytest.approx(rows[0].changes["avionics"][1] / 3.2)
    rows, notes = sweeps.sensitivity(prep, _nominal(prep))
    assert [r.largest_k for r in rows] == sorted((r.largest_k for r in rows), reverse=True)
    avionics_driver = max(rows, key=lambda r: abs(r.changes["avionics"][2]))
    assert avionics_driver.path in ("faces[radiator].emissivity", _RADIATOR, path, "environment.planet_ir_w_m2")
    assert not any("dissipations[avionics]" in r.path for r in rows)


def test_the_thermal_monte_carlo_is_reproducible_and_opens_in_the_monte_carlo_view(prepared, tmp_path, qtbot):
    """Six runs from seed 7: the same draws and temperatures twice, other
    draws from another seed; the batch saves and reads back (kind thermal,
    every node), its run table has the drawn values and each run's node
    extremes, its plots the per-run temperatures and the spread, and the
    Monte Carlo view shows it with the node's tiles."""
    from spacemissionstudio.gui.monte_carlo_results_widget import MonteCarloResultsWidget

    scenario, _result, prep = prepared
    config = scenario.spacecraft[0].thermal.monte_carlo
    first = sweeps.monte_carlo(prep, config)
    again = sweeps.monte_carlo(prep, config)
    assert first.drawn == again.drawn and len(first.runs) == 6 and not first.failed
    assert np.array_equal(first.temperatures_c["avionics"], again.temperatures_c["avionics"])
    other = sweeps.monte_carlo(prep, copy.replace(config, seed=8))
    assert other.drawn != first.drawn
    assert all(0.0 <= row[_RADIATOR] <= 1.0 for row in first.drawn)
    mcr.save(first, tmp_path / "batch")
    loaded = mcr.load(tmp_path / "batch")
    assert loaded.kind == "thermal" and loaded.items == first.items and loaded.case == "nominal"
    assert np.array_equal(loaded.temperatures_c["battery"], first.temperatures_c["battery"])
    labels, rows = mcr.run_table(loaded, "avionics")
    assert labels[1:3] == [_RADIATOR, "heat_pipes[avionics heat pipe].conductance_w_k"]
    assert labels[-3:] == ["avionics min [degC]", "avionics max [degC]", "avionics mean [degC]"] and len(rows) == 6
    series = mcr.to_result_set(loaded).series
    assert series["thermal_monte_carlo.avionics.temperature"].data.shape[1] == 6
    spread = series["thermal_monte_carlo.avionics.spread"].data
    assert np.all(spread[:, 3] <= spread[:, 0]) and np.all(spread[:, 0] <= spread[:, 4])
    assert any(line.startswith("avionics:") for line in mcr.summary_lines(loaded))
    view = MonteCarloResultsWidget()
    qtbot.addWidget(view)
    assert view.load_folder(tmp_path / "batch")
    assert view.spacecraft_label.text() == "Node:" and view.spacecraft_combo.count() == len(loaded.items)
    assert "thermal Monte Carlo" in view.hint_label.text()
    assert view.table.row_count() == 6


def test_the_thermal_monte_carlo_counts_the_runs_outside_each_node_range(prepared, tmp_path):
    """Monte Carlo plan B4 on template 33's nominal case: each node with
    limits gets a row per range it has (battery, avionics and bus: both;
    the arrays: operating only; the radiator: none); a run is outside when
    its own temperature leaves the range, so the counts equal those read
    from the kept temperatures; with a confidence the bound is the A2 bound,
    without one there is none. The failed runs' draws are kept."""
    from spacemissionstudio.engine import monte_carlo_requirements as req

    scenario, _result, prep = prepared
    config = copy.replace(scenario.spacecraft[0].thermal.monte_carlo, confidence=0.9)
    batch = sweeps.monte_carlo(prep, config)
    results = [req.NodeLimitResult.from_dict(row) for row in batch.node_limits]
    assert [(r.node, r.range) for r in results] == [
        ("bus", "operating"), ("bus", "survival"), ("array +y", "operating"), ("array -y", "operating"),
        ("battery", "operating"), ("battery", "survival"), ("avionics", "operating"), ("avionics", "survival")]
    nodes = {node.name: node for node in prep.spacecraft.thermal.nodes}
    for r in results:
        low, high = getattr(nodes[r.node], f"{r.range}_c")
        values = batch.temperatures_c[r.node]
        outside = [run for run, row in zip(batch.runs, values) if row.min() < low or row.max() > high]
        assert (r.low_c, r.high_c, r.evaluated, r.failed) == (low, high, 6, 0)
        assert r.outside_runs == tuple(outside) and r.outside == len(outside)
        assert r.upper_bound == req.clopper_pearson_upper(r.outside, 6, 0.9) and r.confidence == 0.9
    assert batch.failed_drawn == {} and batch.probability_bound == "clopper_pearson"
    mcr.save(batch, tmp_path / "batch")
    assert mcr.load(tmp_path / "batch").node_limits == batch.node_limits
    plain = sweeps.monte_carlo(prep, scenario.spacecraft[0].thermal.monte_carlo)
    assert all(row["upper_bound"] is None and row["confidence"] is None for row in plain.node_limits)
    assert [row["outside"] for row in plain.node_limits] == [r.outside for r in results]


def test_the_api_and_the_command_line_reach_the_studies(prepared, tmp_path, capsys):
    scenario, result, _prep = prepared
    points = api.thermal_sweep(scenario, result, _RADIATOR, [0.1, 0.2])
    assert [p.value for p in points] == [0.1, 0.2]
    rows, _notes = api.thermal_sensitivity(scenario, result, [_RADIATOR], relative=0.5)
    assert rows[0].path == _RADIATOR
    batch = api.thermal_monte_carlo(scenario, result, folder=tmp_path / "api")
    assert mcr.has_summary(tmp_path / "api") and batch.kind == "thermal"
    from spacemissionstudio.schema.scenario import scenario_text

    path = tmp_path / "s.json"
    path.write_text(scenario_text(scenario), encoding="utf-8")
    code = cli.main(["thermal", str(path), "--case", "nominal", "--no-sizing", "--sweep", f"{_RADIATOR}=0.1,0.3",
                     "--sensitivity", _RADIATOR, "--monte-carlo", str(tmp_path / "cli")])
    out = capsys.readouterr().out
    assert code == 0 and "sweep of faces[radiator].absorptance" in out and "sensitivity in case nominal" in out
    assert mcr.has_summary(tmp_path / "cli") and "wrote the thermal Monte Carlo" in out
    assert "Node limits (monte_carlo.probability_bound: clopper_pearson" in out
    assert re.search(r"^ +battery +operating +10 +30 +6 ", out, re.MULTILINE)
