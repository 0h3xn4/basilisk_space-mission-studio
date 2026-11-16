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
"""The thermal analysis on a real run (thermal.analysis, api.thermal, the
record and the CLI): template 32's 300 kg spacecraft with a thermal model
generated from its 3D model, run for 0.15 days. The run records what the
fluxes need; the three presets are ordered hot above nominal above cold;
the orbit-periodic start converges; the energy balance and the step check
hold; limit violations become Timeline events and findings; heaters are
sized; the record and the CSV tables carry their provenance; the CLI
generates a model and solves it."""

import json

import pytest

from spacemissionstudio import api, cli
from spacemissionstudio.engine.events import THERMAL_LIMIT
from spacemissionstudio.schema.scenario import scenario_text
from spacemissionstudio.schema.thermal import (ThermalDissipationConfig, ThermalFaceConfig, ThermalHeaterConfig,
                                               ThermalHeatPipeConfig)
from spacemissionstudio.thermal import records

pytestmark = pytest.mark.requires_basilisk

_ARRAYS = ("array +y", "array -y")


def _scenario():
    scenario = api.load(api.template("32_smallsat_design_checks"))
    scenario.sim_settings.duration_days = 0.15
    sc = scenario.spacecraft[0]
    sc.model_analyses = None
    thermal = api.thermal_model(scenario).thermal
    thermal.faces = [ThermalFaceConfig(p.name, coating="white_paint_z93") for p in sc.model.parts
                     if p.name not in _ARRAYS]
    for array in _ARRAYS:
        thermal.faces += [ThermalFaceConfig(array, "+z", coating="solar_cell_triple_junction"),
                          ThermalFaceConfig(array, "-z", coating="black_paint_z306")]
    battery = next(n for n in thermal.nodes if n.name == "battery")
    battery.operating_c = [0.0, 30.0]
    thermal.dissipations = [ThermalDissipationConfig("battery-loss", "battery", power_w=5.0)]
    thermal.heaters = [ThermalHeaterConfig("battery-heater", "battery", 10.0, 5.0, 8.0)]
    thermal.heat_pipes = [ThermalHeatPipeConfig("hp", "battery", "bus", 2.0, [-60.0, 60.0], 0.01)]
    sc.thermal = thermal
    scenario.validate()
    return scenario


@pytest.fixture(scope="module")
def solved():
    scenario = _scenario()
    result = api.run(scenario)
    return scenario, result, api.thermal(scenario, result, size_heaters=False)


def test_the_run_records_what_the_fluxes_need(solved):
    _scenario_, result, _analysis = solved
    for name in ("ephemeris.earth.position_N", "ephemeris.earth.dcm_PN", "ephemeris.sun.position_N"):
        assert name in result.series


def test_hot_above_nominal_above_cold_and_the_solve_holds(solved):
    """The arrays' hottest temperature and the bus's mean order with the
    presets; every case converges, closes its energy balance to 1e-3 and
    changes by less than 0.5 K with half the step."""
    _scenario_, _result, analysis = solved
    by = {c.name: c for c in analysis.cases}
    assert list(by) == ["nominal", "hot", "cold"]
    hottest = {name: max(n.max_c for n in c.summary if n.name in _ARRAYS) for name, c in by.items()}
    assert hottest["hot"] > hottest["nominal"] > hottest["cold"]
    mean = {name: next(n.mean_c for n in c.summary if n.name == "bus") for name, c in by.items()}
    assert mean["hot"] > mean["nominal"] > mean["cold"]
    for case in analysis.cases:
        sol = case.solution
        assert sol.periodic.converged and sol.periodic.residual_k < 0.01
        assert abs(sol.energy_residual_j) < 1.0e-3 * sol.energy_throughput_j
        assert sol.step_check_k < 0.5
        assert "NASA/TM-2001-211221" in case.notes[0]


def test_limit_violations_become_events_and_findings(solved):
    _scenario_, _result, analysis = solved
    events = analysis.events()
    assert events and {e.kind for e in events} == {THERMAL_LIMIT}
    assert all(e.label.startswith("battery below operating") for e in events)
    rules = {getattr(f, "rule_id", None) for f in analysis.findings()}
    assert {"thermal.shading", "thermal.limit"} <= rules


def test_heat_flows_balance_each_node(solved):
    """Per node, the orbit-average heat flows in add up to the heat stored
    over the orbit (near zero for a periodic orbit)."""
    _scenario_, _result, analysis = solved
    kinds = ("solar", "albedo", "infrared", "emitted", "conduction", "heat pipes", "radiation", "dissipation",
             "heater")
    for case in analysis.cases:
        for node, average in case.orbit_average.items():
            total = sum(average[k] for k in kinds)
            scale = sum(abs(average[k]) for k in kinds) or 1.0
            assert abs(total) < 0.02 * scale, (case.name, node, average)


def test_a_heater_is_sized_for_its_setpoint(solved):
    """Sized for the cold case, the heater holds the battery at its 5 degC
    setpoint over the orbit: solved again with that power, its coldest
    temperature is at the setpoint (within the resolution)."""
    from spacemissionstudio.schema.thermal import ThermalCaseConfig
    from spacemissionstudio.thermal import analysis as thermal_analysis

    scenario, result, _analysis = solved
    prepared = thermal_analysis.prepare(scenario, result, "smallsat-1")
    cold = thermal_analysis.solve_case(prepared, ThermalCaseConfig("cold", "cold"), size_heaters=True,
                                       step_check=False)
    sized = cold.heaters[0].sized_w
    assert sized > 10.0
    import copy

    held = copy.deepcopy(scenario.spacecraft[0].thermal)
    held.heaters[0].power_w = sized
    held.heaters[0].on_c, held.heaters[0].off_c = 1000.0, 1001.0  # always below "on": a constant power
    check = thermal_analysis.solve_case(prepared, ThermalCaseConfig("cold", "cold"), size_heaters=False,
                                        step_check=False, thermal=held)
    coldest = next(n.min_c for n in check.summary if n.name == "battery")
    assert coldest == pytest.approx(5.0, abs=0.2)


def test_the_record_and_tables_carry_provenance(solved, tmp_path):
    scenario, result, analysis = solved
    record = records.record(scenario, analysis, result)
    path = tmp_path / "thermal.json"
    from spacemissionstudio.engine import analysis_records

    analysis_records.write(path, record)
    loaded = json.loads(path.read_text())
    assert loaded["kind"] == "thermal_analysis" and loaded["provenance"]["scenario_sha256"]
    assert [c["name"] for c in loaded["results"]["cases"]] == ["nominal", "hot", "cold"]
    written = records.write_tables(analysis, tmp_path / "tables", record)
    names = {p.name for p in written}
    assert {"thermal_summary.csv", "thermal_heat_flows.csv", "thermal_nominal_temperature.csv"} <= names
    assert all(p.with_suffix(p.suffix + ".provenance.json").exists() or
               (p.parent / (p.name + ".provenance.json")).exists() for p in written)


def test_the_cli_generates_a_model_and_solves_a_case(tmp_path, capsys):
    scenario = _scenario()
    raw = tmp_path / "in.json"
    sc = scenario.spacecraft[0]
    saved_thermal, sc.thermal = sc.thermal, None
    raw.write_text(scenario_text(scenario), encoding="utf-8")
    generated = tmp_path / "generated.json"
    assert cli.main(["thermal", str(raw), "--generate", str(generated)]) == 0
    assert "smallsat-1: 6 nodes, 3 conductors" in capsys.readouterr().out
    sc.thermal = saved_thermal
    full = tmp_path / "full.json"
    full.write_text(scenario_text(scenario), encoding="utf-8")
    out = tmp_path / "record.json"
    assert cli.main(["thermal", str(full), "--case", "cold", "--no-sizing", "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "case cold: periodic after" in printed and "battery:" in printed
    assert json.loads(out.read_text())["results"]["cases"][0]["name"] == "cold"
    assert cli.main(["thermal", str(raw)]) == 1
