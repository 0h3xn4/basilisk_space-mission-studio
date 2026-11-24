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
"""The ``budgets.pointing`` subsection (schema.budgets, section version 2;
decisions PE-2, PE-5, PE-16, SRS-F-32): it saves and loads unchanged and
saves only what it sets, a version 1 section opens (the migration only
sets the version), each validation rule refuses bad input and names it,
and a section with only a pointing budget has no power finding. No
Basilisk."""

import copy
import json

import pytest

import budgets_fixtures as fx
from spacemissionstudio.analyses.power_budget import power_budget
from spacemissionstudio.engine import scenario_checks
from spacemissionstudio.schema import budgets as budgets_schema
from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.budgets import BUDGETS_VERSION, migrate_section
from spacemissionstudio.schema.scenario import (Scenario, ScenarioValidationError, parse_scenario_text,
                                                scenario_text)

POINTING = {
    "line_of_sight": "z",
    "requirements": [
        {"name": "APE", "limit_arcsec": fx.sourced(30.0, "MR-12"), "probability": fx.sourced(0.95, "MR-12"),
         "index": "relative", "axis": "line_of_sight", "interpretation": "ensemble",
         "window_s": fx.sourced(10.0, "MR-12"), "stability_s": fx.sourced(1.0, "MR-12"), "modes": ["imaging"]},
        {"name": "AKE", "limit_arcsec": fx.sourced(None, "TBD"), "probability": fx.sourced(None, "TBD"),
         "kind": "knowledge"},
    ],
    "contributors": [
        {"name": "thermal", "behaviour": "periodic", "distribution": "sinusoidal", "group": "structure",
         "equipment": "camera", "spread_arcsec": {"x": fx.sourced(4.0, "thermal analysis TA-3")},
         "mean_arcsec": {"y": fx.sourced(-2.0, "thermal analysis TA-3")}, "period_s": fx.sourced(5900.0, "orbit")},
        {"name": "st-1 noise", "kind": "knowledge", "sensor": "st-1",
         "spread_arcsec": {axis: fx.sourced(None, "TBD") for axis in "xyz"}},
    ],
}


def _section(pointing=None, version=BUDGETS_VERSION) -> dict:
    data = fx.section(version=version)
    data["pointing"] = copy.deepcopy(POINTING if pointing is None else pointing)
    return data


def test_the_version_is_2():
    """The section's own version steps by one for ``pointing`` (PE-2): the
    scenario's schema version does not change, so no template changes."""
    assert BUDGETS_VERSION == 2
    assert budgets_schema.SECTION_MIGRATIONS == {1: budgets_schema._migrate_1_to_2}


def test_the_subsection_round_trips_and_saves_only_what_it_sets(tmp_path):
    scenario = fx.scenario(_section())
    path = tmp_path / "pointing.json"
    scenario.save(path)
    again = load_scenario(path)
    assert again.spacecraft[0].budgets == scenario.spacecraft[0].budgets
    assert scenario_text(again) == path.read_text(encoding="utf-8")
    saved = json.loads(path.read_text(encoding="utf-8"))["spacecraft"][0]["budgets"]
    assert saved["version"] == 2 and saved["pointing"] == POINTING  # defaults are left out
    second = saved["pointing"]["requirements"][1]
    assert set(second) == {"name", "limit_arcsec", "probability", "kind"}  # no window, no modes, defaults left out


def test_an_empty_pointing_budget_saves_as_an_empty_object():
    scenario = fx.scenario(_section({}))
    assert scenario.to_dict()["spacecraft"][0]["budgets"]["pointing"] == {}
    assert scenario.spacecraft[0].budgets.pointing == budgets_schema.PointingConfig()


def test_a_new_requirement_has_no_probability():
    """PE-5: the probability is required in the file and has no default;
    the dataclass has none either."""
    data = _section()
    del data["pointing"]["requirements"][1]["probability"]
    with pytest.raises(ScenarioValidationError, match=r"requirements\[1\]: missing field 'probability'"):
        parse_scenario_text(json.dumps(fx.scenario_data(data)), "test.json")
    with pytest.raises(TypeError):
        budgets_schema.PointingRequirementConfig("R", budgets_schema.SourcedValue(1.0, "x"))  # noqa


# -- the migration ------------------------------------------------------------------------------------------------

def test_a_version_1_section_opens_as_version_2_with_nothing_else_changed(tmp_path):
    """A file of 2.15.0 (section version 1, no pointing) opens, through the
    file loader and through ``Scenario.from_dict``; saved again, only the
    version changes."""
    old = fx.section(version=1)
    path = tmp_path / "old.json"
    path.write_text(json.dumps(fx.scenario_data(old)), encoding="utf-8")
    loaded = load_scenario(path)
    direct = Scenario.from_dict(fx.scenario_data(old))
    current = fx.scenario(fx.section())
    assert loaded.spacecraft[0].budgets == direct.spacecraft[0].budgets == current.spacecraft[0].budgets
    assert loaded.spacecraft[0].budgets.version == 2 and loaded.spacecraft[0].budgets.pointing is None
    saved = loaded.to_dict()["spacecraft"][0]["budgets"]
    assert saved == {**old, "version": 2}


def test_the_older_sbs_example_still_opens():
    """``tests/data/budgets/sbs_microsat_250kg_clean.json`` is a version 1
    section, as 2.15.0 wrote it."""
    data = fx.sbs_clean_section()
    assert data["version"] == 1
    assert fx.scenario(data).spacecraft[0].budgets.version == 2


@pytest.mark.parametrize(("given", "result"), [({"version": 1}, {"version": 2}), ({"version": 2}, {"version": 2}),
                                                ({"version": 3}, {"version": 3}), ({"version": "1"}, {"version": "1"}),
                                                ({"version": True}, {"version": True}), ({}, {})])
def test_migrate_section_steps_only_known_versions(given, result):
    """An unknown version is left for the validation to name."""
    assert migrate_section(dict(given)) == result


def test_a_newer_section_is_refused_by_name():
    with pytest.raises(ScenarioValidationError, match=r"budgets: version 3 is not one this version reads \(it reads 2\)"):
        fx.scenario(fx.section(version=3))


def test_a_scenario_without_pointing_saves_as_before():
    """The templates have no budgets section: they save byte for byte as
    their files (tests/test_scenario_hashes.py has their hashes)."""
    for path in sorted(fx.TEMPLATES.glob("*.json")):
        assert scenario_text(load_scenario(path)) == path.read_text(encoding="utf-8"), path.stem


# -- validation ----------------------------------------------------------------------------------------------------

def _refused(change, match: str) -> None:
    data = _section()
    change(data["pointing"])
    with pytest.raises(ScenarioValidationError, match=match):
        fx.scenario(data)


@pytest.mark.parametrize(("change", "match"), [
    (lambda p: p.update(line_of_sight="w"), r"pointing: line_of_sight 'w' must be \"\" or one of"),
    (lambda p: p["requirements"][0].update(index="peak"), r"requirement 'APE': index 'peak' must be one of"),
    (lambda p: p["requirements"][0].update(kind="both"), r"requirement 'APE': kind 'both' must be one of"),
    (lambda p: p["requirements"][0].update(axis="w"), r"requirement 'APE': axis 'w' must be one of"),
    (lambda p: p["requirements"][0].update(interpretation="any"), r"interpretation 'any' must be one of"),
    (lambda p: p["requirements"][0].update(limit_arcsec=fx.sourced(0.0, "x")), r"limit_arcsec: value must be above 0"),
    (lambda p: p["requirements"][0].update(probability=fx.sourced(1.0, "x")), r"probability: value must be below 1"),
    (lambda p: p["requirements"][0].update(probability=fx.sourced(0.0, "x")), r"probability: value must be above 0"),
    (lambda p: p["requirements"][0].update(probability=fx.sourced(0.9, " ")), r"probability: a number needs a source"),
    (lambda p: p["requirements"][0].update(window_s=fx.sourced(-1.0, "x")), r"window_s: value must be above 0"),
    (lambda p: p["requirements"][0].update(stability_s=fx.sourced(20.0, "x")),
     r"stability_s must be at most window_s"),
    (lambda p: p["requirements"][0].update(modes=["safe"]), r"modes: 'safe' is not a system mode of budgets.modes"),
    (lambda p: p["requirements"][0].update(modes=["imaging", "imaging"]), r"mode names must be unique"),
    (lambda p: p["requirements"][1].update(name="APE"), r"pointing requirement names must be unique \(APE"),
    (lambda p: p["requirements"][0].update(name="a.b"), r"needs a name without"),
    (lambda p: p["contributors"][0].update(kind="other"), r"contributor 'thermal': kind 'other' must be one of"),
    (lambda p: p["contributors"][0].update(behaviour="noise"), r"behaviour 'noise' must be one of"),
    (lambda p: p["contributors"][0].update(distribution="normal"), r"distribution 'normal' must be one of"),
    (lambda p: p["contributors"][0].pop("period_s"), r"a periodic contributor needs period_s"),
    (lambda p: p["contributors"][0].update(period_s=fx.sourced(0.0, "x")), r"period_s: value must be above 0"),
    (lambda p: p["contributors"][0]["spread_arcsec"].update(x=fx.sourced(-1.0, "x")),
     r"spread_arcsec.x: value must be at least 0"),
    (lambda p: p["contributors"][0]["spread_arcsec"].update(w=fx.sourced(1.0, "x")),
     r"spread_arcsec: axis 'w' must be one of"),
    (lambda p: p["contributors"][0].update(equipment="gyro"), r"equipment 'gyro' is not an item of budgets.equipment"),
    (lambda p: p["contributors"][1].update(name="thermal"), r"pointing contributor names must be unique"),
])
def test_each_rule_refuses_bad_input_and_names_it(change, match):
    _refused(change, match)


@pytest.mark.parametrize(("change", "match"), [
    (lambda p: p["requirements"][0].update(colour="red"), r"requirements\[0\]: unexpected field 'colour'"),
    (lambda p: p.update(frame="body"), r"pointing: unexpected field 'frame'"),
    (lambda p: p["contributors"][0].update(spread_arcsec=4.0), r"spread_arcsec must be an object"),
    (lambda p: p["contributors"][0]["spread_arcsec"].update(x=4.0), r"spread_arcsec.x must be an object"),
    (lambda p: p.update(requirements={}), r"pointing.requirements must be a list"),
])
def test_a_wrong_shape_is_refused(change, match):
    data = _section()
    change(data["pointing"])
    with pytest.raises(ScenarioValidationError, match=match):
        parse_scenario_text(json.dumps(fx.scenario_data(data)), "test.json")


def test_a_placeholder_needs_no_number_and_no_source():
    data = _section()
    data["pointing"]["contributors"][0]["spread_arcsec"]["x"] = fx.sourced(None, "")
    assert fx.scenario(data).spacecraft[0].budgets.pointing.contributors[0].spread_arcsec["x"].placeholder


# -- a pointing budget alone --------------------------------------------------------------------------------------

def test_a_section_with_only_a_pointing_budget_has_no_power_finding():
    """PE-16: no item with a power mode, so no power budget and no finding
    about its margins or its distribution loss (before: two findings, "is
    not given")."""
    scenario = fx.scenario({"version": 2, "pointing": {}})
    sc = scenario.spacecraft[0]
    assert power_budget(sc).findings == [] and power_budget(sc).inputs == []
    warnings = [w for w in scenario_checks.plausibility_warnings(scenario)
                if (getattr(w, "rule_id", "") or "").startswith("budget.")]
    assert warnings == []
