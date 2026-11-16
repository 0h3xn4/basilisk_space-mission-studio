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
"""The thermal model's checks in the Problems panel (thermal.checks,
through engine.scenario_checks.plausibility_warnings): faces in no node
or without optics, nodes without capacity or a path to space, and the
shading warning, each a Finding with its rule. No Basilisk."""

import copy
from pathlib import Path

from spacemissionstudio.engine.scenario_checks import plausibility_warnings
from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.thermal import ThermalFaceConfig, ThermalNodeConfig
from spacemissionstudio.thermal import checks, generate

_TEMPLATE = (Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates"
             / "32_smallsat_design_checks.json")


def _scenario(coated: bool = True):
    scenario = load_scenario(_TEMPLATE)
    sc = scenario.spacecraft[0]
    sc.thermal = generate.generate(sc).thermal
    if coated:
        sc.thermal.faces = [ThermalFaceConfig(p.name, coating="white_paint_z93") for p in sc.model.parts]
    return scenario


def _rules(found) -> list[str]:
    return [f.rule_id for f in found]


def test_a_generated_and_coated_model_has_only_the_shading_warning():
    """Template 32's arrays and dish shade the bus: the warning names the
    faces and the parts that shade them, and nothing else is found."""
    scenario = _scenario()
    found = checks.checks(scenario.spacecraft[0])
    assert _rules(found) == ["thermal.shading"]
    assert found[0].startswith("smallsat-1: thermal: ") and "by array" in found[0]


def test_faces_without_optics_are_listed():
    found = checks.checks(_scenario(coated=False).spacecraft[0])
    missing = next(f for f in found if f.rule_id == "thermal.missing_optics")
    assert "bus:+x" in missing and missing.actual.endswith("faces")


def test_a_part_in_no_node_leaves_its_faces_unassigned():
    scenario = _scenario()
    sc = scenario.spacecraft[0]
    sc.thermal.nodes = [n for n in sc.thermal.nodes if n.name != "dish"]
    sc.thermal.conductors = [c for c in sc.thermal.conductors if "dish" not in (c.a, c.b)]
    sc.thermal.faces = [f for f in sc.thermal.faces if f.part != "dish"]
    found = checks.checks(sc)
    unassigned = next(f for f in found if f.rule_id == "thermal.unassigned_face")
    assert "dish:-z" in unassigned and "dish:side 1" in unassigned


def test_a_node_without_mass_or_a_path_to_space_is_found():
    """An extra internal node with neither capacitance nor conductors: no
    capacity and no path; removing the battery's mounting leaves it with
    no path either."""
    scenario = _scenario()
    sc = scenario.spacecraft[0]
    sc.thermal.nodes.append(ThermalNodeConfig("loose"))
    sc.thermal.conductors = [c for c in sc.thermal.conductors if c.name != "bus--battery"]
    found = checks.checks(sc)
    assert "smallsat-1: thermal: node 'loose' has no capacitance and no mass" in found
    paths = [f for f in found if f.rule_id == "thermal.no_path_to_space"]
    assert {f.split("'")[1] for f in paths} == {"loose", "battery"}


def test_the_checks_reach_the_problems_panel():
    """plausibility_warnings carries them, after the model's own checks."""
    scenario = _scenario(coated=False)
    rules = _rules(w for w in plausibility_warnings(scenario) if hasattr(w, "rule_id"))
    assert "thermal.missing_optics" in rules and "thermal.shading" in rules


def test_no_thermal_section_no_thermal_checks():
    scenario = load_scenario(_TEMPLATE)
    assert checks.checks(scenario.spacecraft[0]) == []
    assert not [w for w in plausibility_warnings(copy.deepcopy(scenario)) if "thermal" in str(w)]
