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
"""Flexible solar arrays as thermal nodes (thermal Phase 2, T-37): each
array a panel of its own with a cell side and a back; their normals turn
about the hinge by the deflection the run recorded, so their sunlight
and planetary infrared follow it; a deflection held still gives what a
panel built at that angle gives. On the synthetic run; no Basilisk."""

import copy

import numpy as np
import pytest
import thermal_fixtures as fixtures

from spacemissionstudio.constants import SOLAR_FLUX_1AU_W_M2
from spacemissionstudio.engine.results import TimeSeries
from spacemissionstudio.schema import thermal as thermal_schema
from spacemissionstudio.schema.scenario import ModelPartConfig, SolarArrayConfig, SpacecraftModelConfig
from spacemissionstudio.schema.thermal import ThermalConfig, ThermalFaceConfig, ThermalNodeConfig
from spacemissionstudio.thermal import environment, generate, geometry, network, solver

_PART = "solar array wing"


def _array(**kw) -> SolarArrayConfig:
    """A 2 m x 1 m wing on the +y side, deploying along +y, its cells
    facing +x (the synthetic run's Sun at beta 0 when the attitude is
    inertial and the spacecraft at the orbit's start)."""
    values = dict(name="wing", mass_kg=6.0, span_m=2.0, width_m=1.0, hinge_position_b=[0.0, 0.5, 0.0],
                  deploy_direction_b=[0.0, 1.0, 0.0], normal_b=[1.0, 0.0, 0.0], first_mode_hz=0.3,
                  damping_ratio=0.01)
    values.update(kw)
    return SolarArrayConfig(**values)


def _spacecraft(*arrays, drawn=False):
    parts = [ModelPartConfig(name="bus", shape="box", dimensions_m={"x": 1.0, "y": 1.0, "z": 1.0}, mass_kg=200.0)]
    if drawn:
        parts.append(ModelPartConfig(name="wing drawing", shape="panel", position_b_m=[0.0, 1.5, 0.0],
                                     dimensions_m={"width": 1.0, "length": 2.0, "thickness": 0.02}, mass_kg=6.0,
                                     counts_toward_mass=False))
    return type("Sc", (), {"name": "sat", "model": SpacecraftModelConfig(parts=parts), "solar_arrays": list(arrays),
                           "power": None, "data_handling": None, "comms_pointing": None})()


def _with_deflection(run, theta):
    t = run.series["sat.position_N"].time_s
    run.add(TimeSeries("sat.solar_array.wing.deflection", t, ("deflection",), np.asarray(theta)[:, None], "rad"))
    return run


def test_an_array_is_a_panel_with_a_cell_side_and_a_back():
    """Area span x width on each side, normals +-n, the centre half a span
    from the hinge; an initial deflection of 30 deg turns the cells toward
    -e by sin 30 and the centre toward n."""
    sc = _spacecraft(_array())
    geom = geometry.build(sc.model, arrays=sc.solar_arrays)
    cells, back = [f for f in geom.facets if f.array == "wing"]
    assert (cells.key, back.key) == (f"{_PART}:cells", f"{_PART}:back")
    assert cells.area_m2 == back.area_m2 == pytest.approx(2.0)
    assert np.allclose(cells.normal_b, [1.0, 0.0, 0.0]) and np.allclose(back.normal_b, [-1.0, 0.0, 0.0])
    assert np.allclose(cells.centroid_b, [0.0, 1.5, 0.0]) and _PART in geom.surface_parts
    tilted = geometry.build(sc.model, arrays=[_array(initial_deflection_deg=30.0)]).facets[-2]
    assert np.allclose(tilted.normal_b, [np.cos(np.radians(30)), -0.5, 0.0])
    assert np.allclose(tilted.centroid_b, [0.5, 0.5 + np.cos(np.radians(30)), 0.0])
    assert [(p.name, p.mass_kg) for p in geometry.array_parts(sc)] == [(_PART, 6.0)]


def test_the_normals_turn_with_the_deflection_toward_the_cell_side():
    """+90 deg brings the tip along n and the cells to face -e, as Basilisk's
    hinge turns the panel (engine.solar_arrays: positive toward s3)."""
    sc = _spacecraft(_array())
    geom = geometry.build(sc.model, arrays=sc.solar_arrays)
    turned = geometry.articulated_normals(geom.facets, geom.arrays, {"wing": np.radians([0.0, 90.0, -45.0])})
    assert turned.shape == (3, len(geom.facets), 3)
    cells, back = len(geom.facets) - 2, len(geom.facets) - 1
    assert np.allclose(turned[1, cells], [0.0, -1.0, 0.0]) and np.allclose(turned[1, back], [0.0, 1.0, 0.0])
    assert np.allclose(turned[2, cells], [np.sqrt(0.5), np.sqrt(0.5), 0.0])
    assert np.allclose(turned[:, 0], geom.facets[0].normal_b)  # the bus does not turn


def test_sunlight_and_infrared_follow_the_recorded_deflection():
    """Inertial attitude, the Sun along +x: the cells get S cos(theta) in
    sunlight for a recorded theta(t), the back nothing while theta stays
    within 90 deg; the infrared's view factor follows the turned normal;
    without the record, the initial deflection holds, with a warning."""
    sc = _spacecraft(_array())
    geom = geometry.build(sc.model, arrays=sc.solar_arrays)
    run = fixtures.circular_run(orbits=1.0)
    t = run.series["sat.position_N"].time_s
    theta = np.radians(40.0) * np.sin(2.0 * np.pi * t / 600.0)
    env = environment.build(_with_deflection(run, theta), "sat", "earth", geom.facets, arrays=geom.arrays)
    solar = env.solar()
    cells = len(geom.facets) - 2
    lit = env.illumination > 0.5
    assert solar[lit, cells] == pytest.approx(SOLAR_FLUX_1AU_W_M2 * np.cos(theta[lit]), rel=2e-4)
    assert np.all(solar[:, cells + 1] < 0.1) and not env.warnings
    turned = geometry.articulated_normals(geom.facets, geom.arrays, {"wing": theta})
    nadir = -run.series["sat.position_N"].data / np.linalg.norm(run.series["sat.position_N"].data, axis=1)[:, None]
    h = np.linalg.norm(run.series["sat.position_N"].data, axis=1) / (6378136.6 + 30.0e3)
    expected = environment.plate_sphere_view_factor(np.einsum("ni,ni->n", nadir, turned[:, cells]), h)
    assert env.view_factor[:, cells] == pytest.approx(expected, rel=1e-3, abs=1e-6)
    still = environment.build(fixtures.circular_run(orbits=1.0), "sat", "earth", geom.facets, arrays=geom.arrays)
    assert still.solar()[lit, cells] == pytest.approx(SOLAR_FLUX_1AU_W_M2, rel=2e-4)
    assert any("deflection was not recorded" in w for w in still.warnings)


def test_a_deflection_held_still_matches_a_panel_built_at_that_angle():
    """A recorded deflection of 35 deg throughout gives the same fluxes and
    temperatures as an array whose initial deflection is 35 deg and no
    record: the turning is the geometry, nothing else."""
    run = fixtures.circular_run(orbits=2.0)
    t = run.series["sat.position_N"].time_s
    moving = _spacecraft(_array())
    built = _spacecraft(_array(initial_deflection_deg=35.0))
    thermal = ThermalConfig(nodes=[ThermalNodeConfig("bus", ["bus"]), ThermalNodeConfig("wing", [_PART])],
                            faces=[ThermalFaceConfig("bus", coating="white_paint_z93"),
                                   ThermalFaceConfig(_PART, "cells", coating="solar_cell_triple_junction"),
                                   ThermalFaceConfig(_PART, "back", coating="black_paint_z306")])
    temperatures = []
    for sc, record in ((moving, np.full(len(t), np.radians(35.0))), (built, None)):
        geom = geometry.build(sc.model, arrays=sc.solar_arrays)
        source = _with_deflection(copy.deepcopy(run), record) if record is not None else run
        env = environment.build(source, "sat", "earth", geom.facets, arrays=geom.arrays)
        net = network.build(sc, thermal, geom)
        solar, _albedo, infrared = env.solar(), np.zeros_like(env.solar_factor), env.infrared(230.0)
        loads = solver.loads(net, env.time_s, solar, _albedo, infrared)
        temperatures.append(solver.solve(net, loads, thermal_schema.ThermalSolverConfig(), env.period_s)
                            .integration.temperature_k)
    assert np.max(np.abs(temperatures[0] - temperatures[1])) < 1.0e-9
    assert net.capacitance_j_k[1] == pytest.approx(6.0 * 896.0, rel=0.05)  # the array's mass x aluminium's cp


def test_generation_gives_each_array_a_node_and_leaves_its_drawing_out():
    sc = _spacecraft(_array(), drawn=True)
    built = generate.generate(sc)
    assert [n.name for n in built.thermal.nodes] == ["bus", _PART]
    assert {(f.part, f.face, f.coating) for f in built.thermal.faces} == {
        (_PART, "cells", "solar_cell_triple_junction"), (_PART, "back", "black_paint_z306")}
    assert any("wing drawing" in n and "left out" in n for n in built.notes)
    assert any("hinge's conductance" in n for n in built.notes)
    context = thermal_schema.context_for(sc)
    assert context.parts[_PART] == ("cells", "back")
