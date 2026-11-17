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
"""The equipment list in the mass budget (analyses.mass_budget, design
note section 5) and the ``budget.*`` findings (engine.findings,
engine.scenario_checks, section 6), SRS-F-31: a spacecraft without a
``budgets`` section has the lines and warnings it always had; every
template gives no ``budget.*`` finding; each rule fires when it should and
names what it found. No Basilisk."""

import copy

import pytest

import budgets_fixtures as fx
from spacemissionstudio.analyses import design_checks, mass_budget
from spacemissionstudio.engine import scenario_checks
from spacemissionstudio.engine.findings import explanation_lines
from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.scenario import MassBudgetConfig


def _rules(warnings) -> list[str]:
    return [getattr(w, "rule_id", None) for w in warnings]


@pytest.mark.parametrize("path", sorted(fx.TEMPLATES.glob("*.json")), ids=lambda p: p.stem)
def test_no_template_gives_a_budget_finding_or_an_equipment_list_line(path):
    """The templates have no section: no ``budget.*`` finding in their
    warnings (so the golden texts are unchanged) and no line of kind
    "equipment list" in their mass budgets."""
    scenario = load_scenario(path)
    warnings = scenario_checks.plausibility_warnings(scenario, path.parent) + scenario_checks.scenario_warnings(
        scenario)
    assert not [w for w in warnings if (getattr(w, "rule_id", "") or "").startswith("budget.")]
    for sc in scenario.spacecraft:
        assert all(line.kind != "equipment list" for line in mass_budget.mass_budget(sc).lines)


def test_a_section_without_listed_items_changes_no_mass_line():
    """Items whose mass the 3D model holds add no line: template 32's
    budget is the same with them as without the section."""
    scenario = load_scenario(fx.MODEL_TEMPLATE)
    sc = scenario.spacecraft[0]
    before = mass_budget.mass_budget(sc)
    data = fx.section()
    for item in data["equipment"]:
        item["mass_in_model"] = True
    with_section = fx.scenario(data, fx.MODEL_TEMPLATE).spacecraft[0]
    after = mass_budget.mass_budget(with_section)
    assert after.rows() == before.rows() and after.notes == before.notes


def test_without_a_model_the_equipment_list_replaces_the_dry_mass_line():
    """The design note's items by hand: the OBC (1.2 kg, existing,
    electronics up to 5 kg: 3 %), the camera (3.0 kg, estimated, no column:
    the row's largest, 55 %) and the harness, whose mass is a placeholder:
    a line with no mass, left out of the totals, which are incomplete. The
    run's dry_mass_kg is not changed; a note compares it."""
    sc = fx.scenario().spacecraft[0]
    budget = mass_budget.mass_budget(sc)
    assert [(line.item, line.kind) for line in budget.lines] == [
        ("OBC", "equipment list"), ("camera", "equipment list"), ("harness", "equipment list")]
    lines = {line.item: line for line in budget.lines}
    assert (lines["OBC"].margin_percent, lines["OBC"].column) == (3.0, "electronics_0_5_kg")
    assert lines["camera"].margin_percent == 55.0 and "largest" in lines["camera"].column
    assert lines["harness"].mass_kg is None and lines["harness"].margin_kg is None
    assert lines["harness"].column == "wire_harness" and lines["harness"].margin_percent == 55.0
    assert budget.unknown == ["harness"]
    assert budget.basic_dry_kg == pytest.approx(1.2 + 3.0)
    assert budget.growth_kg == pytest.approx(1.2 * 0.03 + 3.0 * 0.55)
    assert budget.by_subsystem() == {"electronics": pytest.approx((1.2, 0.036)), "(none)": pytest.approx((3.0, 1.65))}
    row = next(r for r in budget.rows() if r["item"] == "harness")
    assert row["basic_mass_kg"] is None and row["mass_with_growth_kg"] is None
    assert any("the run uses dry_mass_kg" in note and f"{sc.dry_mass_kg:g} kg" in note for note in budget.notes)
    assert any("1 line(s) of unknown mass" in note for note in budget.notes)
    assert sc.dry_mass_kg == load_scenario(fx.STARTER).spacecraft[0].dry_mass_kg  # the run's input


def test_an_unknown_electronics_mass_takes_the_largest_bracket():
    data = fx.section()
    data["equipment"][0]["mass_kg"] = fx.sourced(None, "TBD")
    line = mass_budget.mass_budget(fx.scenario(data).spacecraft[0]).lines[0]
    assert line.mass_kg is None and line.margin_percent == 3.0 and "largest bracket" in line.column


def test_with_a_model_the_listed_items_add_lines_and_the_cache_sees_them():
    """Template 32: the parts and its equipment, then the listed items; the
    design checks' cache key covers the section, so a heavy listed item
    raises the mass limit finding at once."""
    base = load_scenario(fx.MODEL_TEMPLATE)
    scenario = fx.scenario(template=fx.MODEL_TEMPLATE)
    sc = scenario.spacecraft[0]
    before = mass_budget.mass_budget(base.spacecraft[0])
    after = mass_budget.mass_budget(sc)
    assert after.lines[:len(before.lines)] == before.lines
    assert [line.item for line in after.lines[len(before.lines):]] == ["OBC", "camera", "harness"]
    assert after.basic_dry_kg == pytest.approx(before.basic_dry_kg + 4.2)
    assert any("3 equipment list item(s) are not in the 3D model" in note for note in after.notes)
    sc.model.mass_budget = MassBudgetConfig(mass_limit_kg=after.launch_mass_kg + 1.0, limit_source="a test limit")
    assert "design.mass_over_limit" not in _rules(design_checks.design_findings(scenario, fx.TEMPLATES))
    sc.budgets.item("camera").mass_kg.value = 50.0
    assert "design.mass_over_limit" in _rules(design_checks.design_findings(scenario, fx.TEMPLATES))


def test_the_design_note_example_gives_its_one_finding():
    """The harness's mass is a placeholder: one ``budget.mass_unknown``,
    and nothing else (the margins, efficiency, loss are given, the duty
    cycles add up to 1, every powered item is in every mode)."""
    scenario = fx.scenario()
    warnings = scenario_checks.plausibility_warnings(scenario)
    found = [w for w in warnings if (getattr(w, "rule_id", "") or "").startswith("budget.")]
    assert _rules(found) == ["budget.mass_unknown"]
    assert found[0].startswith(f"{scenario.spacecraft[0].name}: budgets.equipment: the mass of harness")


def test_each_rule_fires_and_names_what_it_found():
    data = fx.section()
    data["equipment"][1]["maturity"] = ""  # the camera: no maturity
    data["equipment"][0]["maturity"] = "layout"  # no margin for layout
    data["system_power_margin_percent"] = fx.sourced(10, "TBD")
    del data["distribution_loss"]
    del data["modes"][0]["units"]["camera"]
    data["modes"][1]["duty_cycle"] = 0.3
    scenario = fx.scenario(data)
    name = scenario.spacecraft[0].name
    found = [w for w in scenario_checks.plausibility_warnings(scenario) if getattr(w, "rule_id", "").startswith("budget.")]
    texts = {f.rule_id: [] for f in found}
    for f in found:
        texts[f.rule_id].append(str(f))
    assert sorted(texts) == ["budget.mass_unknown", "budget.mode_duty_sum", "budget.no_margin", "budget.placeholder",
                             "budget.unit_not_in_mode"]
    assert f"{name}: budgets.power_margins has no margin for maturity 'layout': the margined power of OBC is " \
           "unknown" in texts["budget.no_margin"]
    assert f"{name}: budgets.equipment: no maturity for camera, so no power margin: their margined power is " \
           "unknown" in texts["budget.no_margin"]
    assert f"{name}: budgets.system_power_margin_percent is a placeholder (source 'TBD'): the system-margined " \
           "power of every mode is unknown" in texts["budget.placeholder"]
    assert f"{name}: budgets.distribution_loss is not given: the source power of every mode is unknown" \
        in texts["budget.placeholder"]
    assert texts["budget.unit_not_in_mode"] == [
        f"{name}: budgets.modes[nominal].units does not give a power mode to camera: their power in this mode is "
        "unknown"]
    assert texts["budget.mode_duty_sum"] == [
        f"{name}: budgets.modes: the duty cycles add up to 1.1, not 1: the time-weighted average power is not computed"]
    duty = next(f for f in found if f.rule_id == "budget.mode_duty_sum")
    assert (duty.actual, duty.limit) == ("1.1", "1 +- 1e-06")
    assert explanation_lines(duty)[0].startswith("rule budget.mode_duty_sum: When every system mode")
    assert all(f.startswith(f"{name}: budgets.") for f in found)


def test_a_budget_finding_points_at_its_field():
    """The Problems panel locates a finding by its prefix: the spacecraft
    and the section's path."""
    pytest.importorskip("PySide6")
    from spacemissionstudio.gui.problem_location import SPACECRAFT, locate

    scenario = fx.scenario()
    name = scenario.spacecraft[0].name
    data = fx.section()
    del data["modes"][0]["units"]["camera"]
    found = next(w for w in scenario_checks.plausibility_warnings(fx.scenario(data))
                 if getattr(w, "rule_id", "") == "budget.unit_not_in_mode")
    location = locate(found, [name])
    assert (location.area, location.name, location.path) == (SPACECRAFT, name, "budgets.modes[nominal].units")


def test_a_check_that_fails_says_so():
    """A section the check cannot read (a half-edited scenario) gives
    ``check.not_run``, not a traceback."""
    scenario = fx.scenario()
    broken = copy.deepcopy(scenario)
    broken.spacecraft[0].budgets.equipment = None
    warnings = scenario_checks.plausibility_warnings(broken)
    assert any(getattr(w, "rule_id", "") == "check.not_run" and "budgets" in w for w in warnings)


def test_the_design_record_names_the_unknown_masses():
    """The record of the design checks lists the lines the totals leave out;
    a spacecraft without them has no such key, as before."""
    from spacemissionstudio.analyses import records

    scenario = fx.scenario()
    record = records.design_record(scenario, design_checks.design_checks(scenario.spacecraft[0]))
    assert record["results"]["mass_budget_totals"]["unknown_items"] == ["harness"]
    plain = load_scenario(fx.STARTER)
    totals = records.design_record(plain, design_checks.design_checks(plain.spacecraft[0]))["results"]
    assert "unknown_items" not in totals["mass_budget_totals"]
