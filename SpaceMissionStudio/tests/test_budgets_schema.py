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
"""The ``budgets`` section of a spacecraft (schema.budgets, SRS-F-31): it
saves and loads unchanged and saves only what it sets, a scenario without
it saves as before, a sourced value is a placeholder when its number is
null or its source is "TBD", and each validation rule refuses bad input
and names what is wrong. No Basilisk."""

import copy
import json

import pytest

import budgets_fixtures as fx
from spacemissionstudio.schema import fields, load_scenario
from spacemissionstudio.schema import budgets as budgets_schema
from spacemissionstudio.schema.budgets import SourcedValue
from spacemissionstudio.schema.scenario import (Scenario, ScenarioValidationError, parse_scenario_text,
                                                scenario_text)


def _refused(budgets, match: str, template=fx.STARTER) -> None:
    with pytest.raises(ScenarioValidationError, match=match):
        fx.scenario(budgets, template)


def _parse_refused(budgets, match: str) -> None:
    with pytest.raises(ScenarioValidationError, match=match):
        parse_scenario_text(json.dumps(fx.scenario_data(budgets)), "test.json")


def test_the_section_round_trips_and_saves_only_what_it_sets(tmp_path):
    """Saved, loaded and saved again, the section is the same; defaults
    (an empty subsystem, mass_in_model false, a duty cycle of 1, an empty
    source_id) are not written, a placeholder's null value is."""
    scenario = fx.scenario()
    path = tmp_path / "budgets.json"
    scenario.save(path)
    again = load_scenario(path)
    assert again.spacecraft[0].budgets == scenario.spacecraft[0].budgets
    assert scenario_text(again) == path.read_text(encoding="utf-8")
    saved = json.loads(path.read_text(encoding="utf-8"))["spacecraft"][0]["budgets"]
    assert saved == fx.SECTION
    harness = saved["equipment"][2]
    assert harness["mass_kg"] == {"value": None, "source": "TBD"} and "power_modes" not in harness
    assert "duty_cycle" not in saved["equipment"][0]["power_modes"][0]
    assert all("mass_in_model" not in item and "source_id" not in item for item in saved["equipment"])


def test_a_scenario_without_budgets_saves_as_before():
    """A template without the section has no ``budgets`` key when saved, so
    its file is unchanged (tests/test_scenario_hashes.py has every
    template's hash)."""
    for path in sorted(fx.TEMPLATES.glob("*.json")):
        scenario = load_scenario(path)
        assert all(sc.budgets is None for sc in scenario.spacecraft), path.stem
        assert all("budgets" not in sc for sc in scenario.to_dict()["spacecraft"]), path.stem
        assert scenario_text(scenario) == path.read_text(encoding="utf-8"), path.stem


def test_a_minimal_section_is_only_its_version():
    """An empty section saves as its version alone and loads back."""
    scenario = fx.scenario({"version": 1})
    assert scenario.to_dict()["spacecraft"][0]["budgets"] == {"version": 1}
    assert Scenario.from_dict(scenario.to_dict()).spacecraft[0].budgets == scenario.spacecraft[0].budgets


@pytest.mark.parametrize(("value", "source", "placeholder"), [
    (None, "anything", True), (0.1, "TBD", True), (0.1, " tbd ", True), (0.1, "Company margin table rev A", False),
    (0.0, "switched off", False), (None, "", True)])
def test_a_placeholder_is_a_null_value_or_a_tbd_source(value, source, placeholder):
    """As SBS ``Sourced.is_placeholder``: a number with source "TBD" (in any
    case, with spaces) is not used; a placeholder is unknown, never zero."""
    item = SourcedValue(value, source)
    assert item.placeholder is placeholder
    assert item.known == (None if placeholder else value)


def test_a_number_without_a_source_is_refused():
    """A number needs a source; a placeholder may have none."""
    data = fx.section()
    data["equipment"][0]["mass_kg"] = {"value": 1.2, "source": "  "}
    _refused(data, r"equipment 'OBC': mass_kg: a number needs a source \(write \"TBD\" for a placeholder\)")
    data["equipment"][0]["mass_kg"] = {"value": None, "source": ""}
    assert fx.scenario(data).spacecraft[0].budgets.item("OBC").mass_kg.placeholder


@pytest.mark.parametrize(("where", "value", "match"), [
    ("value", True, r"expected a number"), ("value", "1.2", r"expected a number"),
    ("source", None, r"expected text")])
def test_a_sourced_value_of_the_wrong_type_is_refused(where, value, match):
    data = fx.section()
    data["equipment"][0]["mass_kg"][where] = value
    _parse_refused(data, match)


@pytest.mark.parametrize(("change", "match"), [
    (lambda d: d["equipment"][0].update(colour="red"), r"equipment\[0\]: unexpected field 'colour'"),
    (lambda d: d["equipment"][0]["mass_kg"].update(note="x"), r"mass_kg: unexpected field 'note'"),
    (lambda d: d["equipment"][0].update(mass_kg=1.2), r"mass_kg must be an object"),
    (lambda d: d["equipment"][0]["mass_kg"].pop("value"), r"mass_kg: missing field 'value'"),
    (lambda d: d["buses"][0].update(voltage_v=28), r"buses\[0\]: unexpected field 'voltage_v'"),
    (lambda d: d["modes"][0].update(pointing="nadir"), r"modes\[0\]: unexpected field 'pointing'"),
    (lambda d: d.update(units=[]), r"budgets: unexpected field 'units'"),
    (lambda d: d["equipment"][0]["power_modes"][0].pop("average_w"), r"missing field 'average_w'"),
    (lambda d: d.update(equipment={}), r"budgets.equipment must be a list"),
])
def test_an_unknown_field_or_a_wrong_shape_is_refused(change, match):
    """Every record is built through the loader's ``_record``: an unknown
    field, a missing one or a number where an object belongs is refused,
    naming where."""
    data = fx.section()
    change(data)
    _parse_refused(data, match)


@pytest.mark.parametrize(("change", "match"), [
    (lambda d: d.update(version=2), r"budgets: version 2 is not one this version reads"),
    (lambda d: d["equipment"].append(copy.deepcopy(d["equipment"][0])), r"equipment names must be unique \(OBC"),
    (lambda d: d["buses"].append({"name": "main"}), r"bus names must be unique"),
    (lambda d: d["modes"].append({"name": "nominal"}), r"mode names must be unique"),
    (lambda d: d["power_margins"].append({"maturity": "existing", "percent": fx.sourced(3, "x")}),
     r"power margin maturity names must be unique"),
    (lambda d: d["equipment"][0]["power_modes"].append({"name": "on", "average_w": fx.sourced(1.0)}),
     r"equipment 'OBC': power mode names must be unique"),
    (lambda d: d["equipment"][0].update(bus="aux"), r"equipment 'OBC': bus 'aux' must name one of buses \(main\)"),
    (lambda d: d["equipment"][0].update(bus=""), r"equipment 'OBC': bus '' must name one of buses"),
    (lambda d: d["equipment"][2].update(bus="aux"), r"equipment 'harness': bus 'aux' is not one of buses"),
    (lambda d: d["equipment"][0].update(maturity="off_the_shelf"), r"maturity 'off_the_shelf' must be \"\" or one of"),
    (lambda d: d["power_margins"][0].update(maturity="class_a"), r"power margin 'class_a': maturity must be one of"),
    (lambda d: d["equipment"][0].update(mass_column="avionics"), r"mass_column 'avionics' must be \"\" or one of"),
    (lambda d: d["equipment"][0].pop("mass_kg"), r"equipment 'OBC': give mass_kg"),
    (lambda d: d["equipment"][0]["mass_kg"].update(value=-1.0), r"mass_kg: value must be at least 0"),
    (lambda d: d["equipment"][0]["power_modes"][0].update(peak_w=fx.sourced(3.0)),
     r"power mode 'on': peak_w must be at least average_w"),
    (lambda d: d["equipment"][0]["power_modes"][0].update(average_w=fx.sourced(-0.5)),
     r"power mode 'on': average_w: value must be at least 0"),
    (lambda d: d["equipment"][0]["power_modes"][0].update(duty_cycle=1.5), r"duty_cycle must be in \[0, 1\]"),
    (lambda d: d["modes"][0].update(duty_cycle=-0.1), r"mode 'nominal': duty_cycle must be in \[0, 1\]"),
    (lambda d: d["modes"][0]["units"].update(GPS="on"), r"mode 'nominal': units: 'GPS' is not an equipment item"),
    (lambda d: d["modes"][0]["units"].update(OBC="standby"), r"units: 'OBC' has no power mode 'standby' \(on, off\)"),
    (lambda d: d["modes"][0]["units"].update(harness="on"), r"units: 'harness' has no power mode 'on' \(it has none\)"),
    (lambda d: d.update(distribution_loss=fx.sourced(1.0, "x")), r"distribution_loss: value must be below 1"),
    (lambda d: d["buses"][0].update(converter_efficiency=fx.sourced(0.0, "x")),
     r"converter_efficiency: value must be above 0"),
    (lambda d: d["buses"][0].update(converter_efficiency=fx.sourced(1.2, "x")),
     r"converter_efficiency: value must be at most 1"),
    (lambda d: d["power_margins"][0].update(percent=fx.sourced(-5, "x")), r"percent: value must be at least 0"),
    (lambda d: d.update(system_power_margin_percent=fx.sourced(2000, "x")),
     r"system_power_margin_percent: value must be at most 1000"),
    (lambda d: d["equipment"][0].update(name="a.b"), r"needs a name without"),
    (lambda d: d["modes"][0].update(name=" safe"), r"needs a name without"),
])
def test_each_rule_refuses_bad_input_and_names_it(change, match):
    data = fx.section()
    change(data)
    _refused(data, match)


def test_placeholders_are_not_range_checked_and_the_model_holds_a_mass():
    """As in SBS, a placeholder's number is not range-checked; an item whose
    mass the 3D model holds needs no mass_kg."""
    data = fx.section()
    data["buses"][0]["converter_efficiency"] = fx.sourced(1.5, "TBD")
    data["equipment"][0].pop("mass_kg")
    data["equipment"][0]["mass_in_model"] = True
    budgets = fx.scenario(data).spacecraft[0].budgets
    assert budgets.buses[0].converter_efficiency.known is None and budgets.item("OBC").mass_kg is None


def test_the_maturity_categories_are_the_spacecraft_s_mass_policy():
    """Decision B-05: every category of the S-120 policy is accepted, for
    an item and a power margin; the design note's off_the_shelf is not."""
    from spacemissionstudio.config import materials

    for category in materials.mass_policy().categories:
        data = fx.section()
        data["equipment"][0]["maturity"] = category
        data["power_margins"] = [{"maturity": category, "percent": fx.sourced(1, "x")}]
        assert fx.scenario(data).spacecraft[0].budgets.item("OBC").maturity == category


def test_the_section_is_on_a_spacecraft_with_a_3d_model_too():
    """Template 32 (a 3D model with a mass budget policy) takes the section."""
    scenario = fx.scenario(template=fx.MODEL_TEMPLATE)
    assert scenario.spacecraft[0].model is not None and scenario.spacecraft[0].budgets.item("OBC")


def test_the_editor_s_record_paths_reach_the_section():
    """The JSON page's completion knows every record of the section and the
    mass columns' choices."""
    assert fields.record_at(("spacecraft", 0, "budgets")) is budgets_schema.BudgetsConfig
    assert fields.record_at(("spacecraft", 0, "budgets", "equipment", 0)) is budgets_schema.BudgetEquipmentConfig
    assert fields.record_at(("spacecraft", 0, "budgets", "equipment", 0, "power_modes", 1, "peak_w")) \
        is SourcedValue
    assert fields.record_at(("spacecraft", 0, "budgets", "buses", 0, "converter_efficiency")) is SourcedValue
    assert fields.record_at(("spacecraft", 0, "budgets", "modes", 0)) is budgets_schema.BudgetModeConfig
    assert fields.record_at(("spacecraft", 0, "budgets", "modes", 0, "units")) is None  # free keys
    assert fields.field(budgets_schema.BudgetEquipmentConfig, "mass_column").choices == budgets_schema.MASS_COLUMNS
    help_ = fields.field(SourcedValue, "source").describe()
    assert "TBD" in help_


def test_the_imported_values_are_keyed_by_source_id():
    """The import record of target "budgets" keeps each imported item's
    numbers by its source_id, so a renamed item keeps its record."""
    data = fx.section()
    data["equipment"][0]["source_id"] = "unit-1"
    sc = fx.scenario(data).spacecraft[0]
    values = budgets_schema.import_values(sc)
    assert values == {"budgets.equipment[unit-1].mass_kg": 1.2,
                      "budgets.equipment[unit-1].power_modes[on].average_w": 4.0,
                      "budgets.equipment[unit-1].power_modes[on].peak_w": 5.5,
                      "budgets.equipment[unit-1].power_modes[off].average_w": 0.0,
                      "budgets.modes[nominal].duty_cycle": 0.8, "budgets.modes[nominal].units[unit-1]": "on",
                      "budgets.modes[imaging].duty_cycle": 0.2, "budgets.modes[imaging].units[unit-1]": "on"}
    sc.budgets.equipment[0].name = "computer"
    for mode in sc.budgets.modes:
        mode.units["computer"] = mode.units.pop("OBC")
    assert budgets_schema.import_values(sc) == values
