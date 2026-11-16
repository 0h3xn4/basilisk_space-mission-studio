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
"""The ``thermal`` section of a spacecraft (schema.thermal): it saves and
loads unchanged and saves only what it sets, each validation rule names
what is wrong, renaming a part follows into it, and every named entry is
reachable by a parameter path. No Basilisk."""

import copy
import json
from pathlib import Path

import pytest

from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema import thermal as thermal_schema
from spacemissionstudio.schema.references import find_part_references, rename_part
from spacemissionstudio.schema.scenario import Scenario, ScenarioValidationError, resolve_value_path

_TEMPLATE = (Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates"
             / "32_smallsat_design_checks.json")

_THERMAL = {
    "nodes": [
        {"name": "structure", "parts": ["bus"], "operating_c": [-20, 50]},
        {"name": "arrays", "parts": ["array +y", "array -y"]},
        {"name": "battery", "parts": ["battery"], "operating_c": [0, 30], "survival_c": [-10, 40]},
        {"name": "radiator", "capacitance_j_k": 4000.0},
    ],
    "faces": [
        {"part": "bus", "face": "+x", "node": "radiator", "coating": "silvered_teflon_5mil", "radiator": True},
        {"part": "bus", "face": "-x", "mli_effective_emittance": 0.03, "coating": "mli_kapton_aluminised_1mil"},
        {"part": "array +y", "face": "+z", "absorptance": 0.92, "emissivity": 0.85},
    ],
    "conductors": [
        {"name": "bus-battery", "a": "structure", "b": "battery", "kind": "contact",
         "contact_area_m2": 0.04, "contact_coefficient_w_m2_k": 500.0},
        {"name": "bus-radiator", "a": "structure", "b": "radiator", "conductance_w_k": 2.0},
    ],
    "heat_pipes": [{"name": "hp-1", "a": "battery", "b": "radiator", "conductance_w_k": 5.0}],
    "radiative_links": [{"name": "bat-bus", "a": "battery", "b": "structure", "effective_area_m2": 0.05}],
    "dissipations": [{"name": "battery-loss", "node": "battery", "power_w": 3.0},
                     {"name": "bus-load", "node": "structure", "source": "bus"}],
    "heaters": [{"name": "bat-htr", "node": "battery", "power_w": 10.0, "on_c": 5.0, "off_c": 8.0}],
    "cases": [{"name": "hot", "preset": "hot", "overrides": {"faces[bus:+x].absorptance": 0.12}}],
}


def _data(thermal=None) -> dict:
    data = json.loads(_TEMPLATE.read_text(encoding="utf-8"))
    data["spacecraft"][0]["thermal"] = copy.deepcopy(_THERMAL if thermal is None else thermal)
    return data


def _load(thermal=None) -> Scenario:
    scenario = Scenario.from_dict(_data(thermal))
    scenario.validate()
    return scenario


def test_a_scenario_without_thermal_saves_as_before():
    """A template without the section has no ``thermal`` key when saved, so
    its file and hash are unchanged."""
    scenario = load_scenario(_TEMPLATE)
    assert scenario.spacecraft[0].thermal is None
    assert "thermal" not in scenario.to_dict()["spacecraft"][0]


def test_the_section_saves_only_what_it_sets_and_loads_back_unchanged():
    """Unset optional fields, empty lists and default solver settings are
    left out; loading the saved form gives the same section."""
    scenario = _load()
    saved = scenario.to_dict()["spacecraft"][0]["thermal"]
    assert saved["version"] == 1
    assert "solver" not in saved and "environment" not in saved
    assert saved["nodes"][3] == {"name": "radiator", "parts": [], "capacitance_j_k": 4000.0}
    assert saved["faces"][0]["radiator"] is True and "absorptance" not in saved["faces"][0]
    again = Scenario.from_dict(scenario.to_dict())
    again.validate()
    assert again.spacecraft[0].thermal == scenario.spacecraft[0].thermal


@pytest.mark.parametrize("change, message", [
    (lambda t: t["nodes"][0]["parts"].append("hull"), "part 'hull' is not in the 3D model"),
    (lambda t: t["nodes"][1]["parts"].append("bus"), "belongs to nodes 'structure' and 'arrays'"),
    (lambda t: t["faces"].append({"part": "bus", "face": "+w"}), "'+w' is not a face of 'bus'"),
    (lambda t: t["faces"].append({"part": "dish", "face": "side 99"}), "'side 99' is not a face of 'dish'"),
    (lambda t: t["faces"].append({"part": "star tracker"}), "'star tracker' belongs to no node"),
    (lambda t: t["faces"].append(dict(t["faces"][0])), "faces bus:+x are given more than once"),
    (lambda t: t["faces"][0].update(node="nowhere"), "node 'nowhere' is not a node"),
    (lambda t: t["faces"][0].update(coating="unobtainium"), "coating 'unobtainium' is not in the library"),
    (lambda t: t["faces"][2].update(absorptance=1.2), "absorptance must be in [0, 1]"),
    (lambda t: t["faces"][0].update(mli_effective_emittance=0.02), "a radiator face cannot be covered with MLI"),
    (lambda t: t["nodes"].append({"name": "structure"}), "nodes names must be unique (structure repeated)"),
    (lambda t: t["nodes"][2].update(operating_c=[30, 0]), "lowest below highest"),
    (lambda t: t["nodes"][2].update(operating_c=[-20, 30]), "operating_c must lie within survival_c"),
    (lambda t: t["nodes"][3].update(capacitance_j_k=0.0), "capacitance_j_k must be in (0, 1e+09]"),
    (lambda t: t["conductors"][0].update(b="structure"), "a and b must be different nodes"),
    (lambda t: t["conductors"][0].pop("contact_area_m2"), "kind \"contact\" needs contact_area_m2"),
    (lambda t: t["conductors"][1].update(kind="material"), "kind \"material\" needs length_m and section_m2"),
    (lambda t: t["conductors"][1].update(b="ghost"), "'ghost' is not a node"),
    (lambda t: t["heat_pipes"][0].update(off_conductance_w_k=9.0), "off_conductance_w_k must not exceed"),
    (lambda t: t["dissipations"][0].update(source="bus"), "give either power_w or source"),
    (lambda t: t["dissipations"][1].update(source="instrument:camera"), "'instrument:camera' is not a power-budget"),
    (lambda t: t["heaters"][0].update(on_c=9.0), "on_c must be below off_c"),
    (lambda t: t["cases"][0].update(preset="lukewarm"), "preset must be one of"),
    (lambda t: t.update(solver={"start": "cold"}), "start must be one of"),
    (lambda t: t.update(environment={"albedo": 1.5}), "albedo must be in [0, 1]"),
    (lambda t: t.update(version=2), "version 2 is not one this version reads"),
    (lambda t: t.update(nodes=[], faces=[], conductors=[], heat_pipes=[], radiative_links=[], dissipations=[],
                        heaters=[]), "needs at least one node"),
])
def test_each_rule_names_what_is_wrong(change, message):
    """Every validation rule refuses its case with a specific message
    naming the spacecraft, the entry and the field."""
    thermal = copy.deepcopy(_THERMAL)
    change(thermal)
    with pytest.raises(ScenarioValidationError) as error:
        _load(thermal)
    assert message in str(error.value)
    assert str(error.value).startswith("smallsat-1: thermal")


def test_an_unknown_field_is_refused_by_name():
    data = _data()
    data["spacecraft"][0]["thermal"]["nodes"][0]["temperature"] = 20
    with pytest.raises(ValueError, match=r"thermal\.nodes\[0\]: unexpected field 'temperature'"):
        Scenario.from_dict(data)


def test_a_central_body_without_albedo_and_infrared_models_is_refused():
    """Earth and Mars only (decision T-17)."""
    data = _data()
    data["gravity"].update(central_body="moon", central_body_degree=0)
    with pytest.raises(ScenarioValidationError, match="thermal needs Earth or Mars"):
        Scenario.from_dict(data).validate()


def test_renaming_a_part_follows_into_the_thermal_section():
    """A part's references in node part lists and face entries are found
    before a delete and renamed with the part."""
    scenario = _load()
    sc = scenario.spacecraft[0]
    paths = [ref.path for ref in find_part_references(sc, "bus")]
    assert "smallsat-1: thermal.nodes 'structure'.parts" in paths
    assert "smallsat-1: thermal.faces 'bus:+x'" in paths
    rename_part(sc, "bus", "main body")
    assert sc.thermal.nodes[0].parts == ["main body"]
    assert [f.part for f in sc.thermal.faces[:2]] == ["main body", "main body"]
    scenario.validate()


def test_every_named_entry_is_reachable_by_a_parameter_path():
    """Cases, sweeps and Monte Carlo override values by path (T-13): faces
    by ``part:face``, the others by name."""
    thermal = _load().spacecraft[0].thermal
    for path, expected in [("nodes[radiator].capacitance_j_k", 4000.0), ("faces[bus:+x].radiator", True),
                           ("conductors[bus-battery].contact_coefficient_w_m2_k", 500.0),
                           ("heaters[bat-htr].on_c", 5.0), ("environment.albedo_model", "map"),
                           ("solver.time_step_s", 30.0)]:
        record, name = resolve_value_path(thermal, path)
        assert getattr(record, name) == expected


def test_shape_face_names_follow_the_shape():
    """A box's six faces, a cylinder's caps, group and numbered sides, a
    sphere's numbered faces, and None for an imported mesh (T-03)."""
    sc = _load().spacecraft[0]
    parts = {p.name: p for p in sc.model.parts}
    assert thermal_schema.shape_face_names(parts["bus"]) == ("+x", "-x", "+y", "-y", "+z", "-z")
    dish = thermal_schema.shape_face_names(parts["dish"])
    assert dish[:2] == ("-z", "sides") and dish[-1] == f"side {parts['dish'].segments}"
    mesh = copy.deepcopy(parts["bus"])
    mesh.shape = "mesh"
    assert thermal_schema.shape_face_names(mesh) is None
