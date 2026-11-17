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
"""The IDM-CIC import fills the ``budgets`` section (idm_import.apply_budgets,
``idm-import --budgets``; design note section 7, decision B-08), the
``budgets`` command prints the power budget, and the API returns it
(SRS-F-31). The fixture ``tests/data/idm/powersat`` is synthetic: system
mode Cruise (duty cycle 0.8) links the element mode Quiet (star tracker
1.5 W, wheel 3 W, gyro 6 W); Downlink (0.2) maps the wheel to a custom
4.5 W and the gyro to Off (0 W) and leaves the star tracker unstated."""

import csv
import io
import json
import shutil
from pathlib import Path

import pytest
from idm_fixtures import model_xml, write_idm

import budgets_fixtures as fx
from spacemissionstudio import api, cli, idm, idm_import
from spacemissionstudio.analyses.power_budget import power_budget
from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.scenario import import_status

_FULL_ATTITUDE = fx.TEMPLATES / "06_attitude_pointing_basic.json"  # one spacecraft, sat-1, no power budget
_SOURCE = "IDM-CIC file powersat.idm"
_ST, _WHEEL, _GYRO = "Star tracker head ST200", "Reaction Wheel X", "Gyro unit"


def _model(tmp_path) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    return write_idm(tmp_path / "powersat.idm", model_xml("powersat"))


def _scenario_file(tmp_path, source=_FULL_ATTITUDE) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "scenario.json"
    shutil.copyfile(source, path)
    return path


def _imported(tmp_path, merge: bool = True, choice=None):
    path = _scenario_file(tmp_path)
    scenario = load_scenario(path)
    plan = idm_import.plan(idm.load(_model(tmp_path)))
    summary = idm_import.merge(scenario, "sat-1", plan, path) if merge else plan.summary
    idm_import.apply_power(scenario, "sat-1", plan, choice or idm_import.PowerChoice(budgets=True), "me", summary)
    scenario.validate()
    return scenario, plan, summary


def test_the_import_writes_the_equipment_list_and_the_system_modes(tmp_path):
    """One item per unit that draws power, with the power modes its system
    modes use (average = peak = the file's power, sourced to the file);
    one system mode per system mode with its duty cycle; a unit a mode does
    not map is not listed; bus main, the loss and the system margin are
    placeholders. The 3D model holds the units' shapes: no mass here."""
    scenario, plan, summary = _imported(tmp_path)
    section = scenario.spacecraft[0].budgets
    assert [(i.name, i.subsystem, i.bus, i.maturity, i.mass_in_model, i.mass_kg) for i in section.equipment] == [
        (_ST, "AOCS", "main", "", True, None), (_WHEEL, "AOCS", "main", "", True, None),
        (_GYRO, "AOCS", "main", "", True, None)]
    assert [i.source_id for i in section.equipment] == [u.full_id for u in plan.power.units]
    wheel = section.item(_WHEEL)
    assert [(m.name, m.average_w.value, m.peak_w.value, m.average_w.source) for m in wheel.power_modes] == [
        ("Idle", 3.0, 3.0, _SOURCE), ("custom Downlink", 4.5, 4.5, _SOURCE)]
    assert [(m.name, m.duty_cycle, m.units) for m in section.modes] == [
        ("Cruise", 0.8, {_ST: "On", _WHEEL: "Idle", _GYRO: "On"}),
        ("Downlink", 0.2, {_WHEEL: "custom Downlink", _GYRO: "Off"})]
    assert section.buses[0].name == "main" and section.buses[0].converter_efficiency.placeholder
    assert section.distribution_loss.placeholder and section.system_power_margin_percent.placeholder
    assert section.power_margins == []
    assert any(line.startswith("  budgets: made: 3 item(s) added, 0 updated, 2 system mode(s); not in the file")
               for line in summary.lines())


def test_the_loads_are_the_files_and_what_it_does_not_give_is_unknown(tmp_path):
    """Cruise's load is the IDM-CIC total, 10.5 W; with the efficiency, the
    loss and the margins placeholders, everything after the load is
    unknown, and Downlink's load too (the star tracker is unstated). The
    findings say each."""
    scenario, plan, _ = _imported(tmp_path)
    result = power_budget(scenario.spacecraft[0])
    cruise = next(p for p in plan.power.modes if p.mode.name == "Cruise")
    assert result.mode("Cruise").average.load_w == pytest.approx(cruise.total_w) == pytest.approx(10.5)
    assert result.mode("Cruise").average.source_w is None and result.mode("Cruise").average.unit_margined_w is None
    assert result.mode("Downlink").average.load_w is None
    rules = [f.rule_id for f in result.findings]
    assert sorted(set(rules)) == ["budget.no_margin", "budget.placeholder", "budget.unit_not_in_mode"]
    unstated = next(f for f in result.findings if f.rule_id == "budget.unit_not_in_mode")
    assert unstated == f"sat-1: budgets.modes[Downlink].units does not give a power mode to {_ST}: their power in " \
                       "this mode is unknown"


def test_the_import_is_recorded_and_its_values_followed(tmp_path):
    """An import record of target "budgets" (format idm_cic) keeps each
    imported number by its source id; an edit shows as changed; the record
    round-trips through the file."""
    scenario, _, _ = _imported(tmp_path)
    record = next(r for r in scenario.imports if r.target == "budgets")
    assert (record.format, record.author, record.source) == ("idm_cic", "me", str(tmp_path / "powersat.idm"))
    assert record.details["placeholders"] == "converter efficiency (bus main), distribution loss, system power margin"
    wheel = scenario.spacecraft[0].budgets.item(_WHEEL)
    key = f"budgets.equipment[{wheel.source_id}].power_modes[Idle].average_w"
    assert record.values[key] == 3.0 and import_status(scenario, record)["changed"] == []
    wheel.power_modes[0].average_w.value = 2.5
    assert import_status(scenario, record)["changed"] == [(key, 3.0, 2.5)]
    path = tmp_path / "saved.json"
    scenario.save(path)
    again = load_scenario(path)
    assert again.spacecraft[0].budgets == scenario.spacecraft[0].budgets
    assert next(r for r in again.imports if r.target == "budgets") == record


def test_without_the_model_merge_the_items_carry_their_masses(tmp_path):
    """No 3D model holds the units: each item has its mass from the file,
    the sum of its shapes' masses (as the model import gives its parts)."""
    scenario, plan, _ = _imported(tmp_path, merge=False)
    path = _scenario_file(tmp_path)
    merged = load_scenario(path)
    idm_import.merge(merged, "sat-1", idm_import.plan(idm.load(_model(tmp_path))), path)
    for unit, item in zip(plan.power.units, scenario.spacecraft[0].budgets.equipment):
        assert item.mass_in_model is False and item.mass_kg.source == _SOURCE
        parts = [p for p in [*merged.spacecraft[0].model.parts, *merged.spacecraft[0].model.equipment]
                 if p.source_id == unit.full_id or p.source_id in unit.shape_ids.values()]
        assert parts and item.mass_kg.value == pytest.approx(sum(p.mass_kg for p in parts)), item.name


def test_the_bus_load_is_set_as_before(tmp_path):
    """``bus_idle_power_w`` and the power record are the same with and
    without the budgets section (B-08: its behaviour does not change)."""
    with_budgets, _, _ = _imported(tmp_path / "a", choice=idm_import.PowerChoice("Cruise", True, -1, budgets=True))
    without, _, _ = _imported(tmp_path / "b", choice=idm_import.PowerChoice("Cruise", True, -1))
    assert with_budgets.spacecraft[0].power == without.spacecraft[0].power
    assert with_budgets.spacecraft[0].power.bus_idle_power_w == pytest.approx(10.5)
    power = [next(r for r in s.imports if r.target == "power") for s in (with_budgets, without)]
    assert power[0].values == power[1].values and power[0].details == power[1].details
    assert without.spacecraft[0].budgets is None and not any(r.target == "budgets" for r in without.imports)


def test_a_re_import_keeps_the_users_choices(tmp_path):
    """Matched by source id: the user's name, maturity, bus and own items,
    modes and numbers stay; the file's power modes and duty cycles are
    taken again; nothing is added twice."""
    scenario, plan, _ = _imported(tmp_path)
    sc = scenario.spacecraft[0]
    section = sc.budgets
    from spacemissionstudio.schema.budgets import (BudgetBusConfig, BudgetEquipmentConfig, BudgetPowerModeConfig,
                                                   PowerMarginConfig, SourcedValue)

    gyro = section.item(_GYRO)
    gyro.name, gyro.maturity, gyro.bus = "gyro", "released", "aux"
    section.buses.append(BudgetBusConfig("aux", SourcedValue(0.95, "PCDU data sheet")))
    for mode in section.modes:
        if _GYRO in mode.units:
            mode.units["gyro"] = mode.units.pop(_GYRO)
    section.distribution_loss = SourcedValue(0.02, "harness estimate")
    section.power_margins.append(PowerMarginConfig("released", SourcedValue(10.0, "company rule")))
    section.equipment.append(BudgetEquipmentConfig("heater", bus="main", mass_kg=SourcedValue(0.3, "estimate"),
                                                   power_modes=[BudgetPowerModeConfig("on", SourcedValue(2.0, "x"))]))
    section.modes[0].units["heater"] = "on"
    section.item(_WHEEL).power_modes[0].average_w.value = 2.5
    section.modes[0].duty_cycle = 0.5
    sc.validate()
    summary = plan.summary
    summary.budgets_set.clear()
    idm_import.apply_budgets(scenario, "sat-1", plan, "me", summary)
    scenario.validate()
    assert [i.name for i in section.equipment] == [_ST, _WHEEL, "gyro", "heater"]
    gyro = section.item("gyro")
    assert (gyro.maturity, gyro.bus, [m.name for m in gyro.power_modes]) == ("released", "aux", ["On", "Off"])
    assert section.item(_WHEEL).power_modes[0].average_w.value == 3.0  # the file's again
    assert section.distribution_loss.value == 0.02 and [b.name for b in section.buses] == ["main", "aux"]
    assert section.modes[0].duty_cycle == 0.8
    assert section.modes[0].units == {"heater": "on", _ST: "On", _WHEEL: "Idle", "gyro": "On"}
    assert summary.budgets_set[0].startswith("updated: 0 item(s) added, 3 updated, 2 system mode(s)")
    assert "distribution loss" not in summary.budgets_set[0]


def test_a_model_without_power_modes_writes_no_section(tmp_path):
    scenario = load_scenario(_scenario_file(tmp_path))
    plan = idm_import.plan(idm.load(write_idm(tmp_path / "devicesat.idm", model_xml("devicesat"))))
    assert idm_import.apply_budgets(scenario, "sat-1", plan, "", plan.summary) == 0
    assert scenario.spacecraft[0].budgets is None and "not written" in plan.summary.budgets_set[0]
    with pytest.raises(idm.IdmError, match="no spacecraft 'nope'"):
        idm_import.apply_budgets(scenario, "nope", plan)


def test_idm_import_budgets_on_the_command_line(tmp_path, capsys):
    """``idm-import --budgets`` writes the section and says so; an
    orbit-only scenario gets it too (no run uses it), while the power
    budget there is still not set."""
    model, path = _model(tmp_path), _scenario_file(tmp_path)
    assert cli.main(["idm-import", str(model), str(path), "--spacecraft", "sat-1", "--budgets"]) == 0
    assert "budgets: made: 3 item(s) added" in capsys.readouterr().out
    saved = load_scenario(path).spacecraft[0]
    assert [i.name for i in saved.budgets.equipment] == [_ST, _WHEEL, _GYRO] and saved.power is None
    orbit = _scenario_file(tmp_path / "orbit", fx.STARTER)
    name = load_scenario(orbit).spacecraft[0].name
    assert cli.main(["idm-import", str(model), str(orbit), "--spacecraft", name, "--budgets", "--bus-load",
                     "Cruise"]) == 0
    out = capsys.readouterr().out
    assert "runs orbit only, which simulates no power budget" in out and "budgets: made" in out
    again = load_scenario(orbit).spacecraft[0]
    assert again.power is None and len(again.budgets.modes) == 2


def test_the_budgets_command_prints_each_mode(tmp_path, capsys):
    """The SBS example's five modes with their totals; --csv the same
    numbers as CSV; findings and --explain for an incomplete section."""
    path = tmp_path / "clean.json"
    fx.scenario(fx.sbs_clean_section()).save(path)
    assert cli.main(["budgets", str(path)]) == 0
    out = capsys.readouterr().out
    assert out.startswith("my-sat: power budget, 5 system mode(s), 18 item(s) with power modes\n")
    lines = out.splitlines()
    imaging = next(line for line in lines if line.strip().startswith("imaging "))
    assert imaging.split() == ["imaging", "100.7", "113.17", "124.487", "115.349", "142.597", "207.3", "295.387"]
    assert "imaging, bus payload (efficiency 0.9): load 45 W, with margins 58.41 W" in out and "FINDING" not in out
    assert cli.main(["budgets", str(path), "--csv"]) == 0
    rows = list(csv.DictReader(io.StringIO(capsys.readouterr().out)))
    assert [r["mode"] for r in rows] == ["charging", "downlink", "imaging", "nominal", "safe"]
    assert float(rows[2]["source_margined_w"]) == pytest.approx(142.596793, abs=5e-7)
    assert rows[2]["duty_cycle"] == ""

    data = fx.section()
    del data["modes"][0]["units"]["camera"]
    incomplete = tmp_path / "note.json"
    fx.scenario(data).save(incomplete)
    assert cli.main(["budgets", str(incomplete), "--explain"]) == 0
    out = capsys.readouterr().out
    assert "; incomplete (unknown values below)" in out.splitlines()[0]
    assert "nominal, bus main (efficiency 0.9): load unknown, with margins unknown" in out
    assert "FINDING: my-sat: budgets.modes[nominal].units does not give a power mode to camera" in out
    assert "  rule budget.unit_not_in_mode: Each system mode gives every equipment item" in out
    assert cli.main(["budgets", str(incomplete), "--csv"]) == 0
    rows = list(csv.DictReader(io.StringIO(capsys.readouterr().out)))
    assert rows[0]["load_w"] == "" and float(rows[1]["load_w"]) == pytest.approx(10.0)


def test_the_budgets_command_refuses_what_it_cannot_print(tmp_path, capsys):
    path = tmp_path / "plain.json"
    shutil.copyfile(fx.STARTER, path)
    assert cli.main(["budgets", str(path)]) == 1
    assert "has no budgets section (idm-import --budgets makes one" in capsys.readouterr().err
    assert cli.main(["budgets", str(path), "--spacecraft", "nope"]) == 1
    assert "no spacecraft named 'nope'" in capsys.readouterr().err
    bad = tmp_path / "bad.json"
    data = fx.scenario_data()
    data["spacecraft"][0]["budgets"]["equipment"][0]["bus"] = "aux"
    bad.write_text(json.dumps(data), encoding="utf-8")
    assert cli.main(["budgets", str(bad)]) == 1
    assert "INVALID" in capsys.readouterr().err


def test_the_api_returns_the_engine_s_budget():
    scenario = fx.scenario(fx.sbs_clean_section())
    assert api.power_budget(scenario) == power_budget(scenario.spacecraft[0])
    assert api.power_budget(load_scenario(fx.STARTER)).modes == []
