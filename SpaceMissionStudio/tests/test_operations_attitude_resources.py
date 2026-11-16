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
"""Attitude per mode, slew time and the resource profiles
(operations.attitude, operations.resources; decisions O-08, O-09):
rotations checked by hand, bang-coast-bang against its closed form, the
controller model against its linear limit, energy and memory integrals
against hand sums. No Basilisk run."""

import math

import numpy as np
import operations_fixtures as fixtures
import pytest

from spacemissionstudio.operations import attitude, geometry
from spacemissionstudio.operations.plan import Activity
from spacemissionstudio.operations.resources import SpacecraftModel, _clipped_sum, overlap


def test_pointing_an_axis_uses_the_smallest_rotation():
    """Body +z onto inertial +x from the identity is 90 deg about +y; the
    axis then lies on the direction, and the result stays a rotation."""
    dcm = attitude.point_axis(np.eye(3), [0.0, 0.0, 1.0], [1.0, 0.0, 0.0])
    assert np.allclose(dcm.T @ [0.0, 0.0, 1.0], [1.0, 0.0, 0.0])
    assert attitude.angle_deg(np.eye(3), dcm) == pytest.approx(90.0)
    assert np.allclose(dcm.T @ [0.0, 1.0, 0.0], [0.0, 1.0, 0.0])  # the rotation axis is kept
    flipped = attitude.point_axis(np.eye(3), [0.0, 0.0, 1.0], [0.0, 0.0, -1.0])
    assert np.allclose(flipped.T @ [0.0, 0.0, 1.0], [0.0, 0.0, -1.0]) and np.linalg.det(flipped) == pytest.approx(1.0)
    assert attitude.axis_angle_deg(np.eye(3), [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]) == pytest.approx(90.0)
    drift = np.eye(3)
    for k in range(5000):  # chained small rotations stay orthonormal
        drift = attitude.point_axis(drift, [0.0, 0.0, 1.0], [math.sin(k * 1e-3), 0.0, math.cos(k * 1e-3)])
    assert np.allclose(drift @ drift.T, np.eye(3), atol=1e-12)


def test_hill_frame_and_inertial_reference():
    """hillPoint's frame: x along the position, z along the orbit normal;
    inertial3D's MRP zero is the identity."""
    dcm = attitude.hill_dcm(np.array([[7000e3, 0.0, 0.0]]), np.array([[0.0, 7.5e3, 0.0]]))[0]
    assert np.allclose(dcm, np.eye(3))
    assert np.allclose(attitude.inertial_dcm([0.0, 0.0, 0.0]), np.eye(3))
    assert attitude.angle_deg(np.eye(3), attitude.inertial_dcm([0.0, 0.0, math.tan(math.radians(90.0) / 4.0)])) == \
        pytest.approx(90.0)


def test_bang_coast_bang_matches_its_closed_form():
    """1 deg/s and 0.5 deg/s^2: 2 s to full rate over 1 deg each way; 1 deg
    takes 2 sqrt(1/0.5) s, 90 deg takes 90 + 2 s (Wie)."""
    model = attitude.SlewModel.from_limits(1.0, 0.5)
    assert model.time_s(1.0) == pytest.approx(2.0 * math.sqrt(2.0), rel=1e-3)
    assert model.time_s(90.0) == pytest.approx(92.0, rel=1e-3)
    assert model.time_s(0.0) == 0.0


def test_the_controller_model_matches_the_linear_pd_response():
    """Without limits and for a small angle, the MRP PD slew is the linear
    second-order response I x'' = -(K/4) x - P x'; its settling time from
    theta0 to the tolerance agrees within a step of the analytic one."""
    inertia, k, p = 20.0, 1.0, 6.0  # [kg*m^2], [N*m], [N*m*s]
    model = attitude.SlewModel.from_controller(inertia, k, p, settle_deg=1.0)
    wn = math.sqrt(k / 4.0 / inertia)  # [rad/s]
    zeta = p / (2.0 * inertia * wn)
    assert zeta > 1.0  # overdamped: the slowest exponential decides
    slow = wn * (zeta - math.sqrt(zeta ** 2 - 1.0))
    fast = wn * (zeta + math.sqrt(zeta ** 2 - 1.0))
    theta0 = 10.0  # [deg]

    def angle(t):
        return theta0 * (fast * math.exp(-slow * t) - slow * math.exp(-fast * t)) / (fast - slow)

    lo, hi = 0.0, 1000.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if angle(mid) > 1.0 else (lo, mid)
    assert model.time_s(theta0) == pytest.approx(lo, abs=0.2)
    limited = attitude.SlewModel.from_controller(inertia, k, p, 1.0, max_torque_nm=0.001)
    assert limited.time_s(90.0) > model.time_s(90.0)
    assert "wheels" in limited.description and model.time_s(180.0) >= model.time_s(90.0)


def test_the_slew_model_of_the_template_spacecraft():
    """The 150 kg template flies MRP feedback with wheels: its gains, the
    wheels' 0.05 N*m and 6 N*m*s, settled to half the 5 deg convergence
    threshold the verification checks (decision O-25)."""
    scenario = fixtures.scenario()
    model = attitude.slew_model(scenario.spacecraft[0], scenario.operations.planned("eo-sat").agility, scenario)
    assert "0.05 N*m" in model.description and "settled within 2.5 deg" in model.description
    assert 30.0 < model.time_s(30.0) < 120.0 and model.time_s(2.0) == 0.0 and model.time_s(3.0) > 0.0
    assert attitude.wheel_limits(scenario.spacecraft[0]) == (pytest.approx(0.05), pytest.approx(6.0))


def test_clipped_sums_and_overlap():
    """The battery and memory integrators clip at both ends and count what
    the top cuts; a step's share inside an interval is exact."""
    values, cut = _clipped_sum(5.0, np.array([3.0, 4.0, -20.0, 2.0]), 0.0, 10.0)
    assert values.tolist() == [8.0, 10.0, 0.0, 2.0] and cut == 2.0
    assert overlap(np.array([0.0, 10.0, 20.0]), 10.0, 5.0, 22.0).tolist() == [0.5, 1.0, 0.2]


@pytest.fixture(scope="module")
def model():
    scenario = fixtures.scenario()
    geo = geometry.build(scenario)
    sc = scenario.spacecraft[0]
    slew = attitude.slew_model(sc, scenario.operations.planned("eo-sat").agility, scenario)
    return scenario, geo, SpacecraftModel(scenario, sc, geo, scenario.operations, slew)


def test_energy_follows_the_power_budget_s_equation(model):
    """With no activities, Sun pointing on the panel normal: generation is
    S (AU/r)^2 A eta in sunlight, the load the bus idle plus the
    always-on housekeeping; the battery integrates their difference."""
    scenario, geo, spacecraft = model
    profile = spacecraft.evaluate([])
    power = scenario.spacecraft[0].power
    sunlit = geo.tracks["eo-sat"].sunlight > 0.999
    expected = spacecraft.flux * power.panel_area_m2 * power.panel_efficiency
    assert profile.generated_w[sunlit] == pytest.approx(expected[sunlit], rel=1e-9)
    assert np.all(profile.generated_w[geo.tracks["eo-sat"].sunlight < 1e-6] == 0.0)
    assert profile.load_w[0] == pytest.approx(power.bus_idle_power_w + 0.0)  # housekeeping draws no power
    first = power.battery_initial_soc * power.battery_capacity_wh + (profile.generated_w[0] - profile.load_w[0]) * \
        geo.step_s / 3600.0
    assert profile.energy_wh[0] == pytest.approx(min(first, power.battery_capacity_wh))
    assert profile.min_soc > 0.5


def test_memory_and_power_of_an_acquisition_and_a_contact(model):
    """A 20 s acquisition with the 80 kbit/s camera adds 1.6 Mbit and its
    power; a contact downlinks at 5 Mbit/s while the link closes, never
    below empty; housekeeping fills at 4 kbit/s throughout."""
    scenario, geo, spacecraft = model
    t0 = 3000.0
    image = Activity("x", "eo-sat", "image", "acquisition", t0, t0 + 20.0, setup_s=10.0, pointing="target",
                     target="munich")
    quiet = spacecraft.evaluate([])
    busy = spacecraft.evaluate([image])
    after = int(np.searchsorted(geo.time_s, t0 + 40.0))
    assert busy.memory_bit[after] - quiet.memory_bit[after] == pytest.approx(80000.0 * 20.0, rel=1e-9)
    camera_power, extra = 15.0, 5.0  # [W] the camera's and the activity type's
    energy = np.sum(busy.load_w - quiet.load_w) * geo.step_s
    assert energy == pytest.approx((camera_power + extra) * 20.0, rel=1e-9)
    assert quiet.memory_bit[-1] == pytest.approx(4000.0 * geo.step_s * len(geo.time_s), rel=1e-6)
    passes = [p for p in __import__("spacemissionstudio.operations.opportunities", fromlist=["x"]).station_passes(
        geo, scenario.ground_stations[0], scenario.operations.stations[0], "eo-sat", scenario.spacecraft[0].rf_link,
        scenario)]
    item = passes[1]
    contact = Activity("c", "eo-sat", "downlink", "contact", item.aos_s, item.los_s, pointing="station",
                       station="berlin-gs")
    with_contact = spacecraft.evaluate([contact])
    assert with_contact.downlinked_bit == pytest.approx(quiet.memory_bit[int(np.searchsorted(geo.time_s,
                                                                                               item.aos_s))], rel=0.05)
    assert np.min(with_contact.memory_bit) >= 0.0
    assert with_contact.lost_bit == 0.0


def test_the_timeline_reports_slews_and_whether_they_fit(model):
    """Two activities back to back without time between them cannot both
    be reached; spread out, each slews from the default mode."""
    _scenario, _geo, spacecraft = model
    first = Activity("a", "eo-sat", "star cal", "calibration", 1000.0, 1300.0, pointing="inertial")
    near = Activity("b", "eo-sat", "image", "acquisition", 1315.0, 1335.0, setup_s=10.0, pointing="target",
                    target="munich")
    far = Activity("b", "eo-sat", "image", "acquisition", 4000.0, 4020.0, setup_s=10.0, pointing="target",
                   target="munich")
    tight = spacecraft.timeline([first, near])
    assert tight[1]["from"] == "previous" and tight[1]["ok"] is (tight[1]["slew_s"] <= 5.0)
    loose = spacecraft.timeline([first, far])
    assert loose[1]["from"] == "default" and loose[1]["ok"]
    assert loose[1]["point_from_s"] == pytest.approx(far.occupied[0] - loose[1]["slew_s"])
