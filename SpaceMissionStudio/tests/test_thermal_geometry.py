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
"""The thermal model's geometry from the 3D model (thermal.geometry),
the starting model generated from the parts (thermal.generate), the
conductor calculator (thermal.conductors) and the thermal view of the
material library (thermal.library). Hand-checked areas; no Basilisk."""

import math
from pathlib import Path

import pytest

from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.scenario import ModelPartConfig, SpacecraftModelConfig
from spacemissionstudio.schema.thermal import ThermalConductorConfig
from spacemissionstudio.thermal import conductors, generate, geometry, library

_TEMPLATES = Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates"


def _box(name, size, position, **kw) -> ModelPartConfig:
    return ModelPartConfig(name=name, shape="box", dimensions_m=dict(zip("xyz", size, strict=True)),
                           position_b_m=list(position), mass_kg=kw.pop("mass_kg", 1.0), **kw)


def _model(*parts) -> SpacecraftModelConfig:
    return SpacecraftModelConfig(parts=list(parts))


def test_facets_are_every_outer_face_with_its_true_area():
    """A cylinder keeps one facet per side, each its share of the curved
    area (pi d h in total), so fluxes are summed per facet (T-06)."""
    cylinder = ModelPartConfig(name="tank", shape="cylinder", dimensions_m={"diameter": 0.4, "height": 1.0},
                               segments=24, mass_kg=10.0)
    facets = geometry.facets(_model(cylinder))
    sides = [f for f in facets if f.group == "sides"]
    assert len(sides) == 24 and len(facets) == 26
    assert sum(f.area_m2 for f in sides) == pytest.approx(math.pi * 0.4 * 1.0)
    assert {f.key for f in facets} >= {"tank:+z", "tank:-z", "tank:side 1", "tank:side 24"}


def test_two_boxes_face_to_face_touch_over_their_exact_overlap():
    """A 0.2 m cube against a 1 m cube, offset so 0.1 x 0.2 m of its face
    overlaps: 0.02 m^2, covered on both faces."""
    bus = _box("bus", (1, 1, 1), (0, 0, 0))
    unit = _box("unit", (0.2, 0.2, 0.2), (0.6, 0.5, 0.0))
    geom = geometry.build(_model(bus, unit))
    (contact,) = geometry.contacts(geom)
    assert (contact.a, contact.b) == ("bus", "unit")
    assert contact.area_m2 == pytest.approx(0.1 * 0.2)
    covered = {geom.facets[i].key: geom.covered_m2(i) for i in range(len(geom.facets)) if geom.covered_m2(i)}
    assert covered == pytest.approx({"bus:+x": 0.02, "unit:-x": 0.02})


def test_a_gap_of_a_few_millimetres_is_no_contact():
    bus = _box("bus", (1, 1, 1), (0, 0, 0))
    unit = _box("unit", (0.2, 0.2, 0.2), (0.605, 0.0, 0.0))
    assert geometry.contacts(geometry.build(_model(bus, unit))) == []


def test_an_internal_part_sits_in_the_part_around_it():
    """A part out of the surface model is enclosed by the smallest surface
    part around its centre, and mounted over its largest face."""
    bus = _box("bus", (1, 1, 1), (0, 0, 0))
    battery = _box("battery", (0.4, 0.3, 0.1), (0, 0, -0.3), in_surface_model=False)
    geom = geometry.build(_model(bus, battery))
    assert geometry.enclosures(_model(bus, battery), geom) == {"battery": "bus"}
    assert geometry.mounting_area_m2(geom, "battery") == pytest.approx(0.4 * 0.3)


def test_the_shading_screen_finds_a_deployed_panel_shading_the_bus():
    """One convex part shades nothing; a panel standing off the bus's +y
    side shades that side from some directions, and the bus shades it."""
    bus = _box("bus", (1, 1, 1), (0, 0, 0))
    assert geometry.shading_screen(_model(bus), geometry.build(_model(bus))) == []
    panel = ModelPartConfig(name="array", shape="panel", dimensions_m={"width": 1.0, "length": 1.0,
                                                                       "thickness": 0.02},
                            position_b_m=[0.0, 1.2, 0.0], rotation_deg=[90.0, 0.0, 0.0], mass_kg=2.0)
    model = _model(bus, panel)
    shaded = {(s.part, s.face): s for s in geometry.shading_screen(model, geometry.build(model))}
    assert ("bus", "+y") in shaded and shaded["bus", "+y"].by == ("array",)
    assert ("bus", "-y") not in shaded


def test_generation_on_the_300_kg_template():
    """Template 32's model gives one node per part (the battery internal),
    contact conductors where the star tracker and the dish meet the bus,
    and the battery mounted in the bus over its 0.4 x 0.4 m base, all with
    the bare-joint coefficient (T-25, T-26)."""
    sc = load_scenario(_TEMPLATES / "32_smallsat_design_checks.json").spacecraft[0]
    made = generate.generate(sc)
    assert [n.name for n in made.thermal.nodes] == ["bus", "array +y", "array -y", "star tracker", "dish", "battery"]
    links = {c.name: c for c in made.thermal.conductors}
    assert set(links) == {"bus--star tracker", "bus--dish", "bus--battery"}
    assert links["bus--star tracker"].contact_area_m2 == pytest.approx(0.15 * 0.25)
    assert links["bus--battery"].contact_area_m2 == pytest.approx(0.4 * 0.4)
    assert all(c.contact_coefficient_w_m2_k == pytest.approx(library.BARE_JOINT_W_M2_K, abs=1e-3)
               for c in links.values())
    assert "battery: internal node 'battery'" in made.notes
    sc.thermal = made.thermal
    sc.thermal.validate(sc.name, __import__("spacemissionstudio.schema.thermal", fromlist=["x"]).context_for(sc))


def test_generation_needs_a_model():
    sc = load_scenario(_TEMPLATES / "01_two_body_circular_orbit.json").spacecraft[0]
    with pytest.raises(ValueError, match="has no 3D model"):
        generate.generate(sc)


def test_node_names_cannot_break_a_parameter_path():
    assert generate.node_name("panel.1]") == "panel-1-"


def test_the_conductor_calculator_says_how_it_computed():
    """value, k A / L, h A, and a conductivity table read at the mean
    temperature; a material without a sourced conductivity is refused."""
    given = ThermalConductorConfig(name="g", a="a", b="b", conductance_w_k=1.5)
    assert conductors.conductance(given).value_w_k == 1.5
    bar = ThermalConductorConfig(name="bar", a="a", b="b", kind="material", conductivity_w_m_k=167.0,
                                 length_m=0.5, section_m2=1.0e-4)
    assert conductors.conductance(bar).value_w_k == pytest.approx(167.0 * 1.0e-4 / 0.5)
    joint = conductors.contact("j", "a", "b", 0.04)
    result = conductors.conductance(joint)
    assert result.value_w_k == pytest.approx(0.04 * library.BARE_JOINT_W_M2_K, rel=1e-4)
    assert result.how.startswith("contact: 0.04 m^2")
    table = ThermalConductorConfig(name="t", a="a", b="b", kind="material", length_m=1.0, section_m2=1.0,
                                   conductivity_table=[[0.0, 100.0], [100.0, 200.0]])
    assert conductors.conductance(table, temperature_c=25.0).value_w_k == pytest.approx(125.0)
    assert conductors.conductance(table).value_w_k == pytest.approx(100.0)
    unsourced = ThermalConductorConfig(name="u", a="a", b="b", kind="material", material="white_paint_z93",
                                       length_m=1.0, section_m2=1.0)
    with pytest.raises(conductors.ConductorError, match="no sourced conductivity"):
        conductors.conductance(unsourced)


def test_library_defaults_carry_their_sources():
    """The bare-joint coefficient is the NASA GSFC measurement (5.63 W/K over
    8 in x 8 in, about 136 W/(m^2*K)); the default specific heat is
    aluminium 6061-T6's from DAS 3.0."""
    assert library.BARE_JOINT_W_M2_K == pytest.approx(136.35, abs=0.01)
    assert "20190030287" in library.BARE_JOINT_SOURCE
    default = library.default_specific_heat()
    assert default.value > 800.0 and "DAS" in default.source
    assert library.absorptance("white_paint_z93").value == 0.17
    assert library.emissivity("white_paint_z93").value == 0.92
    assert library.absorptance("nonexistent") is None
