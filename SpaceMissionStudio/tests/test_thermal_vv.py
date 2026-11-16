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
"""Verification cases of the thermal model that the other thermal tests
do not cover (compliance/validation/thermal-vv.md): a regression against
Basilisk's own sensorThermal module, a thin panel's two sides, and a
faceted cylinder converging to the analytic cylinder."""

import math

import numpy as np
import pytest
import thermal_fixtures as fixtures

from spacemissionstudio.schema.scenario import ModelPartConfig, SpacecraftModelConfig
from spacemissionstudio.schema.thermal import ThermalConfig, ThermalFaceConfig, ThermalNodeConfig, ThermalSolverConfig
from spacemissionstudio.thermal import environment, geometry, network, solver
from spacemissionstudio.thermal.network import Network
from spacemissionstudio.thermal.solver import SIGMA, Loads

# Basilisk's sensorThermal (src/simulation/thermal/sensorThermal/sensorThermal.cpp): S = 1366 W/m^2 at any
# distance and a radiation constant of 5.76051e-8 W/(m^2 K^4), 1.6 % above Stefan-Boltzmann's (T-33).
_BSK_SOLAR_W_M2 = 1366.0
_BSK_SIGMA = 5.76051e-8
_PLATE = {"area": 0.1, "absorptance": 0.6, "emissivity": 0.8, "mass": 0.5, "specific_heat": 890.0, "power": 2.0,
          "start_c": 20.0}
_SPIN_RAD_S = 2.0 * math.pi / 1800.0  # [rad/s] one turn in 30 minutes: the plate's normal sweeps through the Sun
_DT_S = 1.0  # [s]
_SPAN_S = 5400.0  # [s] three turns


def _cos_sun(t: np.ndarray) -> np.ndarray:
    """The cosine between the plate's normal (+z of the body) and the Sun
    (+z of the inertial frame) while the body spins about +x."""
    return np.cos(_SPIN_RAD_S * t)


def _sensor_thermal_run(dt_s: float) -> tuple[np.ndarray, np.ndarray]:
    """Basilisk's sensorThermal through its public API, its messages
    written stand-alone each step; returns (time [s], temperature [degC])."""
    from Basilisk.architecture import messaging
    from Basilisk.simulation import sensorThermal
    from Basilisk.utilities import macros

    module = sensorThermal.SensorThermal()
    module.nHat_B = [0.0, 0.0, 1.0]
    module.sensorArea = _PLATE["area"]
    module.sensorAbsorptivity = _PLATE["absorptance"]
    module.sensorEmissivity = _PLATE["emissivity"]
    module.sensorMass = _PLATE["mass"]
    module.sensorSpecificHeat = _PLATE["specific_heat"]
    module.sensorPowerDraw = _PLATE["power"]
    module.T_0 = _PLATE["start_c"]
    sun = messaging.SpicePlanetStateMsgPayload()
    sun.PositionVector = [0.0, 0.0, 1.496e11]
    sun_msg = messaging.SpicePlanetStateMsg().write(sun)
    state_msg = messaging.SCStatesMsg()
    module.sunInMsg.subscribeTo(sun_msg)
    module.stateInMsg.subscribeTo(state_msg)
    times = np.arange(0.0, _SPAN_S + dt_s / 2, dt_s)
    temperature = []
    for k, t in enumerate(times):
        angle = _SPIN_RAD_S * t
        state = messaging.SCStatesMsgPayload()
        state.r_BN_N = [7.0e6, 0.0, 0.0]
        state.sigma_BN = [math.tan(angle / 4.0), 0.0, 0.0]  # a rotation by angle about +x
        state_msg.write(state, int(macros.sec2nano(t)))
        if k == 0:
            module.Reset(0)
        module.UpdateState(int(macros.sec2nano(t)))
        temperature.append(module.temperatureOutMsg.read().temperature)
    return times, np.array(temperature)


def _plate_network(sigma: float, dt_s: float = _DT_S) -> tuple[Network, Loads]:
    """The same plate as one node of this tool's network, sunlit on +z."""
    p = _PLATE
    net = Network(["plate"], np.array([p["mass"] * p["specific_heat"]]), ["given"], [], [], [], [],
                  np.array([p["power"]]), [], [], [None], [None], np.full(1, np.nan))
    t = np.arange(0.0, _SPAN_S + dt_s / 2, dt_s)
    sun = (_BSK_SOLAR_W_M2 * p["area"] * p["absorptance"] * np.clip(_cos_sun(t), 0.0, None))[:, None]
    zero = np.zeros_like(sun)
    emission = np.array([p["emissivity"] * p["area"] * sigma])
    return net, Loads(t, sun, zero, zero, emission)


@pytest.mark.requires_basilisk
def test_the_solver_reproduces_basilisks_sensor_thermal():
    """A 0.1 m^2 plate that dissipates 2 W, spinning through the Sun for
    three 30-minute turns from 20 degC, with Basilisk's constants: this
    tool's BDF2 solution and Basilisk's explicit Euler agree to 0.1 K at a
    1 s step and to 0.025 K at 0.25 s; the difference falls with the step
    as Euler's first-order error does, while this tool's own solution
    changes by less than 1 mK between the two steps. With the
    Stefan-Boltzmann constant the plate runs warmer, by the fourth root of
    the two constants' ratio at equilibrium."""
    differences, ours = [], []
    for dt_s in (_DT_S, _DT_S / 4.0):
        times, basilisk_c = _sensor_thermal_run(dt_s)
        net, loads = _plate_network(_BSK_SIGMA, dt_s)
        run = solver.integrate(net, loads, times, np.array([_PLATE["start_c"] + network.ZERO_C_K]))
        ours_c = run.temperature_k[:, 0] - network.ZERO_C_K
        differences.append(float(np.max(np.abs(ours_c - basilisk_c))))
        ours.append(np.interp(np.arange(0.0, _SPAN_S + 1.0, 60.0), run.time_s, ours_c))
        assert basilisk_c.max() - basilisk_c.min() > 20.0  # the case swings: the comparison means something
    assert differences[0] < 0.1 and differences[1] < 0.025
    assert 3.0 < differences[0] / differences[1] < 5.0  # first order: a quarter of the step, about a quarter
    assert np.max(np.abs(ours[0] - ours[1])) < 1.0e-3
    # Equilibrium of the plate held facing the Sun, Basilisk's constant against Stefan-Boltzmann's.
    absorbed = np.array([_BSK_SOLAR_W_M2 * _PLATE["area"] * _PLATE["absorptance"]])  # and the 2 W dissipated
    t_bsk = solver.steady_state(net, absorbed, loads.emission_w_k4)[0]
    true_net, true_loads = _plate_network(SIGMA)
    t_true = solver.steady_state(true_net, absorbed, true_loads.emission_w_k4)[0]
    assert t_true / t_bsk == pytest.approx((_BSK_SIGMA / SIGMA) ** 0.25, rel=1e-9)
    assert t_true - t_bsk == pytest.approx(1.4, abs=0.1)  # [K]


def _model_net(part: ModelPartConfig, faces: list[ThermalFaceConfig]):
    model = SpacecraftModelConfig(parts=[part])
    geom = geometry.build(model)
    thermal = ThermalConfig(nodes=[ThermalNodeConfig(part.name, [part.name], specific_heat_j_kg_k=900.0)],
                            faces=faces)
    return geom, network.build(type("Sc", (), {"name": "sat", "model": model})(), thermal, geom)


def test_a_thin_panel_takes_sun_and_earth_on_each_side_with_that_sides_optics():
    """A 2 m x 1 m panel, nadir-pointed (+z to the Earth), solar cells on
    +z and black paint on -z, beta 30 deg: each side gets the Sun only
    when it faces it (never both), the Earth's infrared only on +z
    (F = 1/h^2) and none on -z; the node absorbs each side's flux with
    that side's absorptance and emits with each side's emissivity."""
    panel = ModelPartConfig(name="panel", shape="panel", dimensions_m={"width": 2.0, "length": 1.0,
                                                                       "thickness": 0.02}, mass_kg=6.0)
    faces = [ThermalFaceConfig("panel", "+z", absorptance=0.91, emissivity=0.85),
             ThermalFaceConfig("panel", "-z", absorptance=0.95, emissivity=0.88),
             ThermalFaceConfig("panel", absorptance=0.5, emissivity=0.5)]
    geom, net = _model_net(panel, faces)
    run = fixtures.circular_run(altitude_m=600.0e3, beta_deg=30.0, orbits=1.0, attitude="nadir")
    env = environment.build(run, "sat", "earth", geom.facets)
    names = [f.face for f in geom.facets]
    top, bottom = names.index("+z"), names.index("-z")
    solar = env.solar(1361.0)
    assert np.all((solar[:, top] < 1e-9) | (solar[:, bottom] < 1e-9))
    assert solar[:, top].max() > 0.0 and solar[:, bottom].max() > 0.0
    infrared = env.infrared(240.0)
    h = (6378137.0 + 600.0e3) / (6378137.0 + 30.0e3)
    assert infrared[:, top] == pytest.approx(240.0 / h ** 2, rel=1e-6)
    assert infrared[:, bottom] == pytest.approx(0.0, abs=1e-9)
    zero = np.zeros_like(solar)
    loads = solver.loads(net, env.time_s, solar, zero, infrared)
    area = 2.0
    expected_sun = area * (0.91 * solar[:, top] + 0.95 * solar[:, bottom])
    edges = [i for i, n in enumerate(names) if n not in ("+z", "-z")]
    expected_sun += sum(geom.facets[i].area_m2 * 0.5 * solar[:, i] for i in edges)
    assert loads.solar_w[:, 0] == pytest.approx(expected_sun, rel=1e-9)
    assert loads.infrared_w[:, 0] == pytest.approx(area * 0.85 * infrared[:, top] + sum(
        geom.facets[i].area_m2 * 0.5 * infrared[:, i] for i in edges), rel=1e-9)
    edge_area = sum(geom.facets[i].area_m2 for i in edges)
    assert loads.emission_w_k4[0] == pytest.approx(SIGMA * (area * (0.85 + 0.88) + 0.5 * edge_area), rel=1e-9)


@pytest.mark.parametrize("segments, tolerance", [(6, 0.02), (24, 0.002), (96, 2e-4)])
def test_a_faceted_cylinder_converges_to_the_isothermal_cylinder(segments, tolerance):
    """A cylinder (D 1 m, height 2 m) with the Sun across its axis:
    alpha S D H = eps sigma (pi D H + pi D^2 / 2) T^4. Its side faces keep
    the curved area (model3d.shapes), so only the projected area depends
    on the faceting; the error falls as the faces get finer."""
    cylinder = ModelPartConfig(name="can", shape="cylinder", dimensions_m={"diameter": 1.0, "height": 2.0},
                               segments=segments, mass_kg=20.0)
    geom, net = _model_net(cylinder, [ThermalFaceConfig("can", absorptance=0.4, emissivity=0.8)])
    run = fixtures.circular_run(orbits=0.2, eclipse=False)
    env = environment.build(run, "sat", "earth", geom.facets)
    zero = np.zeros_like(env.solar_factor)
    loads = solver.loads(net, env.time_s, env.solar(1361.0), zero, zero)
    t = solver.steady_state(net, loads.total().mean(axis=0), loads.emission_w_k4)[0]
    expected = (0.4 * 1361.0 * 1.0 * 2.0 / (0.8 * SIGMA * (math.pi * 2.0 + math.pi / 2.0))) ** 0.25
    assert abs(t - expected) / expected < tolerance


def test_the_step_check_falls_with_the_step():
    """The same eclipsing orbit solved at 120, 60 and 30 s: the change the
    step check reports falls about four-fold per halving (BDF2 is second
    order) and the 30 s result is within 0.05 K of a 5 s reference."""
    e = 0.5 * 0.85 * SIGMA
    net = Network(["panel"], np.array([6000.0]), ["given"], [], [], [], [], np.array([0.0]), [], [], [None], [None],
                  np.full(1, np.nan))
    t = np.arange(0.0, 5700.0 * 2 + 1, 10.0)
    sun = (300.0 * np.clip(np.sin(2 * math.pi * t / 5700.0) + 0.2, 0.0, None))[:, None]
    zero = np.zeros_like(sun)
    loads = Loads(t, sun, zero, zero, np.array([e]))
    checks, ends = [], []
    for step in (120.0, 60.0, 30.0, 5.0):
        sol = solver.solve(net, loads, ThermalSolverConfig(time_step_s=step), period_s=5700.0)
        checks.append(sol.step_check_k)
        ends.append(sol.integration.temperature_k[:, 0])
    assert checks[0] > checks[1] > checks[2]
    assert checks[1] / checks[2] > 2.5
    assert abs(ends[2].max() - ends[3].max()) < 0.05 and abs(ends[2].min() - ends[3].min()) < 0.05
