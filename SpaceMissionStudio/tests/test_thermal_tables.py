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
"""Temperature-dependent properties (thermal Phase 2): a node's
specific-heat table and a conductor's conductivity table. Flat tables
give exactly the constant-property results; a linear specific heat
heated at constant power follows the analytic enthalpy; the energy
balance closes on the enthalpy. No Basilisk."""

import math

import numpy as np
import pytest

from spacemissionstudio.schema.scenario import ModelPartConfig, SpacecraftModelConfig
from spacemissionstudio.schema.thermal import (ThermalConductorConfig, ThermalConfig, ThermalDissipationConfig,
                                               ThermalFaceConfig, ThermalNodeConfig, ThermalSolverConfig)
from spacemissionstudio.thermal import geometry, network, solver
from spacemissionstudio.thermal.solver import SIGMA, Loads

_K = network.ZERO_C_K


def _model():
    parts = [ModelPartConfig(name="panel", shape="panel", dimensions_m={"width": 1.0, "length": 1.0,
                                                                        "thickness": 0.02}, mass_kg=4.0),
             ModelPartConfig(name="unit", shape="box", dimensions_m={"x": 0.2, "y": 0.2, "z": 0.2},
                             position_b_m=[0.0, 0.0, 0.5], mass_kg=3.0, in_surface_model=False)]
    return SpacecraftModelConfig(parts=parts)


def _thermal(panel_cp=None, panel_table=None, link=None):
    return ThermalConfig(
        nodes=[ThermalNodeConfig("panel", ["panel"], specific_heat_j_kg_k=panel_cp, specific_heat_table=panel_table),
               ThermalNodeConfig("unit", ["unit"], specific_heat_j_kg_k=900.0)],
        faces=[ThermalFaceConfig("panel", absorptance=0.3, emissivity=0.8)],
        conductors=[link or ThermalConductorConfig("strap", "panel", "unit", "value", conductance_w_k=0.5)],
        dissipations=[ThermalDissipationConfig("unit", "unit", power_w=10.0)])


def _solve(thermal):
    model = _model()
    geom = geometry.build(model)
    net = network.build(type("Sc", (), {"name": "sat", "model": model})(), thermal, geom)
    t = np.arange(0.0, 5700.0 * 2 + 1, 30.0)
    m = len(geom.facets)
    sun_on_panel = np.where((t % 5700.0) < 3600.0, 600.0, 0.0)
    solar = np.zeros((len(t), m))
    solar[:, [f.face for f in geom.facets].index("+z")] = sun_on_panel
    zero = np.zeros_like(solar)
    loads = solver.loads(net, t, solar, zero, zero)
    return net, solver.solve(net, loads, ThermalSolverConfig(time_step_s=30.0), period_s=5700.0)


def test_flat_tables_reduce_to_constant_properties():
    """A flat specific-heat table and a flat conductivity table give the
    same temperatures as the constant values, to 1 uK."""
    _net, constant = _solve(_thermal(panel_cp=880.0, link=ThermalConductorConfig(
        "strap", "panel", "unit", "material", conductivity_w_m_k=160.0, length_m=0.2, section_m2=5.0e-4)))
    net, flat = _solve(_thermal(panel_table=[[-100.0, 880.0], [100.0, 880.0]], link=ThermalConductorConfig(
        "strap", "panel", "unit", "material", length_m=0.2, section_m2=5.0e-4,
        conductivity_table=[[-100.0, 160.0], [100.0, 160.0]])))
    assert net.capacitance_tables and net.conductance_tables
    assert np.max(np.abs(flat.integration.temperature_k - constant.integration.temperature_k)) < 1.0e-6


def test_a_linear_specific_heat_follows_the_analytic_enthalpy():
    """A node with cp = a + b T [K], heated at a constant 20 W with no
    losses, has m (a T + b T^2 / 2) rising by 20 W t: the solution's
    temperature after an hour, solved from that quadratic, to 1 mK; a
    constant cp equal to the start's would end 1.5 K hotter."""
    mass, a, b = 2.0, 400.0, 1.5  # [kg], [J/(kg*K)], [J/(kg*K^2)]
    rows = np.array([[0.0, a], [400.0, a + b * 400.0]])  # [K] (linear: exact for interpolation)
    net = network.Network(["node"], np.array([mass * (a + b * 293.15)]), ["table"], [], [], [], [],
                          np.array([20.0]), [], [], [None], [None], np.full(1, np.nan),
                          capacitance_tables={0: (mass, rows)})
    t = np.arange(0.0, 3600.0 + 1, 10.0)
    zero = np.zeros((len(t), 1))
    loads = Loads(t, zero, zero, zero, np.zeros(1))
    run = solver.integrate(net, loads, t, np.array([293.15]))
    h_end = mass * (a * 293.15 + 0.5 * b * 293.15 ** 2) + 20.0 * 3600.0
    expected = (-mass * a + math.sqrt((mass * a) ** 2 + 2.0 * mass * b * h_end)) / (mass * b)
    assert run.temperature_k[-1, 0] == pytest.approx(expected, abs=1.0e-3)
    assert 293.15 + 20.0 * 3600.0 / (mass * (a + b * 293.15)) - expected == pytest.approx(1.5, abs=0.1)


def test_the_energy_balance_closes_on_the_enthalpy():
    """With a specific heat that doubles between -50 and 50 degC, the heat
    stored (the enthalpy's change) still equals the net heat in to 1e-3 of
    the throughput, as with constant properties."""
    net, sol = _solve(_thermal(panel_table=[[-50.0, 600.0], [50.0, 1200.0]]))
    assert abs(sol.energy_residual_j) < 1.0e-3 * sol.energy_throughput_j
    assert sol.periodic.converged
    panel = sol.integration.temperature_k[:, 0]
    assert panel.max() - panel.min() > 5.0  # it swings: the table is used over a range
    assert net.heat_capacity(np.array([_K - 50.0, _K]))[0] == pytest.approx(4.0 * 600.0)
    assert net.heat_capacity(np.array([_K + 80.0, _K]))[0] == pytest.approx(4.0 * 1200.0)  # held beyond the end


def test_a_table_and_a_constant_together_are_refused():
    from spacemissionstudio.schema.validation import ScenarioValidationError

    node = ThermalNodeConfig("panel", ["panel"], specific_heat_j_kg_k=900.0,
                             specific_heat_table=[[0.0, 800.0], [50.0, 900.0]])
    with pytest.raises(ScenarioValidationError, match="specific_heat_table, or capacitance_j_k"):
        node.validate("sat")
    with pytest.raises(ScenarioValidationError, match="specific_heat_table must be at least two"):
        ThermalNodeConfig("panel", ["panel"], specific_heat_table=[[0.0, 800.0]]).validate("sat")


def test_emission_unchanged_by_the_tables():
    """The tables change storage and conduction, not radiation: the
    emission constant is the faces' eps sigma A."""
    net, _sol = _solve(_thermal(panel_table=[[-50.0, 600.0], [50.0, 1200.0]]))
    assert net.facets  # the panel's faces
    emission = sum(f.emissivity * f.area_m2 for f in net.facets if f.node == 0) * SIGMA
    model = _model()
    geom = geometry.build(model)
    loads = solver.loads(net, np.array([0.0, 1.0]), np.zeros((2, len(geom.facets))),
                         np.zeros((2, len(geom.facets))), np.zeros((2, len(geom.facets))))
    assert loads.emission_w_k4[0] == pytest.approx(emission)
