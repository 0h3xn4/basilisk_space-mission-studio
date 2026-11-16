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
"""Case sets (thermal.cases): the presets carry NASA/TM-2001-211221's
values by inclination band and beta, overrides set any parameter by path
on a copy and refuse what they cannot set. No Basilisk."""

import pytest

from spacemissionstudio.schema.thermal import (ThermalCaseConfig, ThermalConfig, ThermalEnvironmentConfig,
                                               ThermalFaceConfig, ThermalNodeConfig)
from spacemissionstudio.thermal import cases


def _thermal() -> ThermalConfig:
    return ThermalConfig(nodes=[ThermalNodeConfig("bus", ["bus"]), ThermalNodeConfig("battery", ["battery"])],
                         faces=[ThermalFaceConfig("bus", "+x", absorptance=0.2, emissivity=0.9, radiator=True)])


@pytest.mark.parametrize("beta, correction", [(0.0, 0.04), (35.0, 0.065), (60.0, 0.12), (-90.0, 0.31)])
def test_the_albedo_correction_follows_table_4_2_1_1(beta, correction):
    assert cases.albedo_correction(beta) == pytest.approx(correction)


def test_presets_carry_the_guideline_values():
    """Hot: 1414 W/m^2, the combined hot pair at 90 minutes plus the beta
    correction; cold: 1322 and the cold pair; nominal: 1367, the map and
    the band's mean OLR."""
    hot = cases.preset_environment("hot", "earth", "medium", 20.0)
    assert hot.environment == ThermalEnvironmentConfig(1414.0, 0.31, 257.0, "average")
    cold = cases.preset_environment("cold", "earth", "low", 0.0)
    assert cold.environment == ThermalEnvironmentConfig(1322.0, 0.18, 228.0, "average")
    nominal = cases.preset_environment("nominal", "earth", "high", 0.0)
    assert nominal.environment == ThermalEnvironmentConfig(1367.0, None, 211.0, "map")
    assert "NASA/TM-2001-211221" in hot.notes[0]
    mars = cases.preset_environment("hot", "mars barycenter", "low", 0.0)
    assert mars.environment == ThermalEnvironmentConfig() and "no sourced extremes" in mars.notes[0]


def test_overrides_set_parameters_by_path_on_a_copy():
    thermal = _thermal()
    changed = cases.apply(thermal, {"faces[bus:+x].absorptance": 0.35, "nodes[battery].capacitance_j_k": 9000,
                                    "environment.albedo_model": "average", "faces[bus:+x].radiator": False})
    assert changed.faces[0].absorptance == 0.35 and changed.faces[0].radiator is False
    assert changed.nodes[1].capacitance_j_k == 9000.0 and changed.environment.albedo_model == "average"
    assert thermal.faces[0].absorptance == 0.2 and thermal.nodes[1].capacitance_j_k is None


@pytest.mark.parametrize("overrides, message", [
    ({"nodes[ghost].mass_kg": 3.0}, "has no item 'ghost'"),
    ({"faces[bus:+x].colour": 1}, "has no field 'colour'"),
    ({"faces[bus:+x].absorptance": "high"}, "is not a number"),
    ({"faces[bus:+x].radiator": 1}, "is not true or false"),
])
def test_an_override_that_cannot_be_set_is_refused_by_path(overrides, message):
    with pytest.raises(cases.CaseError, match=message):
        cases.apply(_thermal(), overrides)


def test_a_case_takes_the_preset_where_the_section_sets_nothing():
    """The section's own environment wins over the preset; overrides win
    over both; the notes say where each value comes from."""
    thermal = _thermal()
    thermal.environment = ThermalEnvironmentConfig(planet_ir_w_m2=240.0)
    case = cases.resolve(thermal, ThermalCaseConfig("hot", "hot", {"faces[bus:+x].emissivity": 0.8}),
                         "earth", "low", 0.0)
    env = case.thermal.environment
    assert (env.solar_flux_w_m2, env.albedo, env.planet_ir_w_m2) == (1414.0, 0.28, 240.0)
    assert case.thermal.faces[0].emissivity == 0.8
    assert case.notes[-1] == "faces[bus:+x].emissivity = 0.8"


def test_without_cases_the_three_presets_are_solved():
    assert [c.name for c in cases.cases_of(_thermal())] == ["nominal", "hot", "cold"]
