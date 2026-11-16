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
"""The thermal network and its solver against analytical cases
(thermal.network, thermal.solver): equilibrium of an isothermal plate
and sphere, two nodes and a conductor, a heat pipe inside and outside its
range, MLI, the energy balance, the orbit-periodic start independent of
the starting temperature, heater sizing against the hand calculation,
and the time-step check. No Basilisk."""

import copy
import math
from pathlib import Path

import numpy as np
import pytest
import thermal_fixtures as fixtures

from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.scenario import ModelPartConfig, SpacecraftModelConfig
from spacemissionstudio.schema.thermal import (ThermalConfig, ThermalFaceConfig, ThermalNodeConfig,
                                               ThermalSolverConfig)
from spacemissionstudio.thermal import environment, geometry, network, solver
from spacemissionstudio.thermal.network import Heater, HeatPipe, Link, Network
from spacemissionstudio.thermal.solver import SIGMA, Loads

_TEMPLATES = Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates"
_K = network.ZERO_C_K


def _net(names, capacitance, emission, **kw) -> tuple[Network, np.ndarray]:
    m = len(names)
    net = Network(list(names), np.asarray(capacitance, float), ["given"] * m, [], kw.get("conductors", []),
                  kw.get("pipes", []), kw.get("links", []), np.asarray(kw.get("dissipation", [0.0] * m), float), [],
                  kw.get("heaters", []), [None] * m, [None] * m, np.full(m, np.nan))
    return net, np.asarray(emission, float)


def _constant_loads(absorbed, emission, span_s=20000.0) -> Loads:
    absorbed = np.asarray(absorbed, float)
    t = np.array([0.0, span_s])
    zero = np.zeros((2, len(absorbed)))
    return Loads(t, np.tile(absorbed, (2, 1)), zero, zero, np.asarray(emission, float))


def test_isothermal_plate_reaches_its_equilibrium_temperature():
    """A plate facing the Sun, both sides radiating: alpha S A = 2 eps sigma
    A T^4. Built through the 3D model and the environment (no albedo or
    infrared: a plate in the Sun alone)."""
    plate = ModelPartConfig(name="plate", shape="panel", dimensions_m={"width": 1.0, "length": 1.0,
                                                                       "thickness": 0.01},
                            rotation_deg=[0.0, 90.0, 0.0], mass_kg=2.0)
    model = SpacecraftModelConfig(parts=[plate])
    geom = geometry.build(model)
    thermal = ThermalConfig(nodes=[ThermalNodeConfig("plate", ["plate"], specific_heat_j_kg_k=900.0)],
                            faces=[ThermalFaceConfig("plate", absorptance=0.6, emissivity=0.8)])
    sc = type("Sc", (), {"name": "sat", "model": model})()
    net = network.build(sc, thermal, geom)
    run = fixtures.circular_run(orbits=1.0, eclipse=False)
    env = environment.build(run, "sat", "earth", geom.facets)
    zero = np.zeros_like(env.solar_factor)
    loads = solver.loads(net, env.time_s, env.solar(1361.0), zero, zero)
    sol = solver.solve(net, loads, ThermalSolverConfig(start="steady", time_step_s=60.0), env.period_s)
    expected = (0.6 * 1361.0 / (2 * 0.8 * SIGMA)) ** 0.25
    assert sol.integration.temperature_k[-1, 0] == pytest.approx(expected, abs=0.05)


@pytest.mark.parametrize("segments, tolerance", [(4, 0.05), (16, 0.01), (64, 0.003)])
def test_a_faceted_sphere_converges_to_the_isothermal_sphere(segments, tolerance):
    """alpha S pi R^2 = eps sigma 4 pi R^2 T^4: the sphere's faces from the 3D
    model, fluxes summed per facet, converge as the facets get finer."""
    sphere = ModelPartConfig(name="ball", shape="sphere", dimensions_m={"diameter": 1.0}, segments=segments,
                             mass_kg=5.0)
    model = SpacecraftModelConfig(parts=[sphere])
    geom = geometry.build(model)
    thermal = ThermalConfig(nodes=[ThermalNodeConfig("ball", ["ball"], specific_heat_j_kg_k=900.0)],
                            faces=[ThermalFaceConfig("ball", absorptance=0.5, emissivity=0.9)])
    net = network.build(type("Sc", (), {"name": "sat", "model": model})(), thermal, geom)
    run = fixtures.circular_run(orbits=0.2, eclipse=False)
    env = environment.build(run, "sat", "earth", geom.facets)
    zero = np.zeros_like(env.solar_factor)
    loads = solver.loads(net, env.time_s, env.solar(1361.0), zero, zero)
    t = solver.steady_state(net, loads.total().mean(axis=0), loads.emission_w_k4)[0]
    expected = (0.5 * 1361.0 / (4 * 0.9 * SIGMA)) ** 0.25
    assert abs(t - expected) / expected < tolerance


def test_two_nodes_and_a_conductor_reach_the_expected_steady_state():
    """An internal unit dissipating 20 W through G = 2 W/K to a radiating
    panel that also dissipates 5 W: E T_A^4 = 25 W and T_B = T_A + 20 / 2."""
    e = 1.0 * 0.85 * SIGMA
    net, emission = _net(["panel", "unit"], [5000.0, 2000.0], [e, 0.0], dissipation=[5.0, 20.0],
                         conductors=[Link("g", 0, 1, 2.0)])
    loads = _constant_loads([0.0, 0.0], emission)
    sol = solver.solve(net, loads, ThermalSolverConfig(start="steady"), period_s=float("inf"))
    t_a, t_b = sol.integration.temperature_k[-1]
    assert t_a == pytest.approx((25.0 / e) ** 0.25, abs=1e-6)
    assert t_b - t_a == pytest.approx(10.0, abs=1e-6)


def test_a_heat_pipe_conducts_inside_its_range_and_barely_outside():
    """The same pair with a heat pipe of 10 W/K: 2 K apart inside its
    range; 2000 K apart at its 0.01 W/K off conductance when the range is
    below the temperatures (so it stays off: the unit runs away)."""
    e = 1.0 * 0.85 * SIGMA
    inside = HeatPipe("hp", 0, 1, 10.0, 0.01, -200.0 + _K, 150.0 + _K)
    net, emission = _net(["panel", "unit"], [5000.0, 2000.0], [e, 0.0], dissipation=[5.0, 20.0], pipes=[inside])
    t_a, t_b = solver.solve(net, _constant_loads([0, 0], emission), ThermalSolverConfig(start="steady"),
                            float("inf")).integration.temperature_k[-1]
    assert t_b - t_a == pytest.approx(20.0 / 10.0, abs=1e-6)
    frozen = HeatPipe("hp", 0, 1, 10.0, 0.01, -260.0 + _K, -240.0 + _K)
    net, emission = _net(["panel", "unit"], [5000.0, 2000.0], [e, 0.0], dissipation=[5.0, 20.0], pipes=[frozen])
    steady = solver.steady_state(net, np.zeros(2), emission)
    assert steady[1] - steady[0] == pytest.approx(20.0 / 0.01, rel=1e-6)


def test_mli_scales_a_face_as_a_massless_outer_layer():
    """Optics alpha_o, eps_o under e*: the face behaves as k alpha_o, k eps_o
    with k = e* / (eps_o + e*) (decision T-09)."""
    plate = ModelPartConfig(name="wall", shape="box", dimensions_m={"x": 1.0, "y": 1.0, "z": 1.0}, mass_kg=10.0)
    model = SpacecraftModelConfig(parts=[plate])
    geom = geometry.build(model)
    thermal = ThermalConfig(nodes=[ThermalNodeConfig("wall", ["wall"], specific_heat_j_kg_k=900.0)],
                            faces=[ThermalFaceConfig("wall", "+x", absorptance=0.4, emissivity=0.6,
                                                     mli_effective_emittance=0.02),
                                   ThermalFaceConfig("wall", absorptance=0.2, emissivity=0.8)])
    net = network.build(type("Sc", (), {"name": "sat", "model": model})(), thermal, geom)
    optics = {geom.facets[f.facet].face: f for f in net.facets}
    k = 0.02 / (0.6 + 0.02)
    assert optics["+x"].absorptance == pytest.approx(0.4 * k) and optics["+x"].emissivity == pytest.approx(0.6 * k)
    assert optics["-x"].absorptance == 0.2 and optics["+y"].emissivity == 0.8


def test_the_energy_balance_closes_over_an_orbit_with_eclipse_heaters_and_links():
    """Stored heat equals the net heat in (trapezoidal) to 1e-3 of the
    throughput with the Sun switching on and off, a thermostat cycling and
    a radiative link, and the residual shrinks with the step (it is the
    integration's, not lost heat)."""
    e = 0.5 * 0.85 * SIGMA
    net, emission = _net(["panel", "unit"], [8000.0, 1500.0], [e, 0.0], dissipation=[0.0, 5.0],
                         conductors=[Link("g", 0, 1, 0.5)], links=[Link("r", 0, 1, 0.1)],
                         heaters=[Heater("h", 1, 15.0, 40.0 + _K, 45.0 + _K)])
    t = np.arange(0.0, 5700.0 * 3 + 1, 60.0)
    sun = np.where((t % 5700.0) < 3600.0, 400.0, 0.0)
    zero = np.zeros((len(t), 2))
    loads = Loads(t, np.column_stack([sun, np.zeros_like(sun)]), zero, zero, emission)
    sol = solver.solve(net, loads, ThermalSolverConfig(time_step_s=30.0), period_s=5700.0)
    assert abs(sol.energy_residual_j) < 1.0e-3 * sol.energy_throughput_j
    finer = solver.solve(net, loads, ThermalSolverConfig(time_step_s=10.0), period_s=5700.0, step_check=False)
    assert abs(finer.energy_residual_j) < 0.5 * abs(sol.energy_residual_j)
    assert sol.integration.heater_on[:, 0].any() and not sol.integration.heater_on[:, 0].all()


def test_the_periodic_start_does_not_depend_on_where_it_starts():
    """The periodic solution equals a long transient from a cold start
    (40 orbits from -80 degC), within the tolerance."""
    e = 0.5 * 0.85 * SIGMA
    net, emission = _net(["panel", "unit"], [8000.0, 1500.0], [e, 0.0], dissipation=[0.0, 5.0],
                         conductors=[Link("g", 0, 1, 0.5)])
    period = 5700.0
    t = np.arange(0.0, period * 40 + 1, 60.0)
    sun = np.where((t % period) < 3600.0, 400.0, 0.0)
    zero = np.zeros((len(t), 2))
    loads = Loads(t, np.column_stack([sun, np.zeros_like(sun)]), zero, zero, emission)
    periodic = solver.solve(net, loads, ThermalSolverConfig(tolerance_k=0.001), period, 0.0, period,
                            step_check=False)
    assert periodic.periodic.converged and periodic.periodic.residual_k < 0.001
    net.initial_k[:] = -80.0 + _K
    cold = solver.solve(net, loads, ThermalSolverConfig(start="fixed"), period, step_check=False)
    last = cold.integration.temperature_k[-int(period / 30.0) - 1:]
    assert last.min(axis=0) == pytest.approx(periodic.integration.temperature_k.min(axis=0), abs=0.01)
    assert last.max(axis=0) == pytest.approx(periodic.integration.temperature_k.max(axis=0), abs=0.01)


def test_heater_sizing_matches_the_hand_calculation():
    """A node that only radiates (E T^4) in the dark needs E T_on^4 to sit
    at its setpoint: the sized power, to 0.1 W."""
    e = 0.3 * 0.85 * SIGMA
    on = 5.0 + _K
    net, emission = _net(["battery"], [3000.0], [e], heaters=[Heater("h", 0, 10.0, on, on + 3.0)])
    loads = _constant_loads([0.0], emission, span_s=6000.0)
    sized = solver.size_heater(net, loads, ThermalSolverConfig(), period_s=6000.0, heater_name="h")
    assert sized == pytest.approx(e * on ** 4, abs=0.1)


def test_the_step_check_shows_the_result_is_insensitive_to_the_step():
    e = 0.5 * 0.85 * SIGMA
    net, emission = _net(["panel", "unit"], [8000.0, 1500.0], [e, 0.0], dissipation=[0.0, 5.0],
                         conductors=[Link("g", 0, 1, 0.5)])
    t = np.arange(0.0, 5700.0 * 2 + 1, 60.0)
    sun = np.where((t % 5700.0) < 3600.0, 400.0, 0.0)
    zero = np.zeros((len(t), 2))
    loads = Loads(t, np.column_stack([sun, np.zeros_like(sun)]), zero, zero, emission)
    sol = solver.solve(net, loads, ThermalSolverConfig(time_step_s=20.0), period_s=5700.0)
    assert sol.step_check_k < 0.2


def test_a_face_without_optics_is_named():
    """Template 32's parts are bare metals with no sourced optics: the
    faces are listed, with what to do."""
    from spacemissionstudio.thermal import generate

    sc = load_scenario(_TEMPLATES / "32_smallsat_design_checks.json").spacecraft[0]
    thermal = generate.generate(sc).thermal
    geom = geometry.build(sc.model)
    with pytest.raises(network.ThermalModelError, match=r"faces without absorptance and emissivity: bus:\+x"):
        network.build(sc, thermal, geom)
    coated = copy.deepcopy(thermal)
    coated.faces = [ThermalFaceConfig(p.name, coating="white_paint_z93") for p in sc.model.parts]
    net = network.build(sc, coated, geom)
    assert len(net.facets) == len(geom.facets) - 0  # every facet, covered ones with less area
    assert all(f.absorptance == 0.17 and f.emissivity == 0.92 for f in net.facets)
    bus = net.index("bus")
    assert net.capacitance_how[bus] == "252 kg x 896 J/(kg*K) (the parts' materials)"
    assert net.capacitance_j_k[bus] == pytest.approx(252.0 * 896.0, rel=0.05)


def test_a_dissipation_follows_its_power_budget_load():
    sc = load_scenario(_TEMPLATES / "32_smallsat_design_checks.json").spacecraft[0]
    from spacemissionstudio.schema.thermal import ThermalDissipationConfig

    thermal = ThermalConfig(nodes=[ThermalNodeConfig("battery", ["battery"])],
                            dissipations=[ThermalDissipationConfig("bus-load", "battery", source="bus")])
    net = network.build(sc, thermal, geometry.build(sc.model))
    assert net.dissipation_w[0] == pytest.approx(sc.power.bus_idle_power_w)
    assert math.isclose(net.dissipations[0][2], sc.power.bus_idle_power_w)
