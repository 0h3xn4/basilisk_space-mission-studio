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
"""Flying a plan in Basilisk (operations.execution) and checking it
(operations.verify): the executor switches pointing and devices at the
plan's times, never the attitude; the flown resources follow the plan;
the verification flags what is beyond its tolerances. A two-hour plan on
the 150 kg template, with stiffer gains so the slews finish in time."""

import numpy as np
import operations_fixtures as fixtures
import pytest

from spacemissionstudio.operations import analysis, execution, verify

_HORIZON = {"start_utc": "2030-01-01T08:30:00Z", "end_utc": "2030-01-01T10:30:00Z"}


@pytest.fixture(scope="module")
def flown():
    scenario = fixtures.scenario(horizon=_HORIZON)
    scenario.spacecraft[0].control_params = {"K": 1.0, "P": 8.0}  # [N*m], [N*m*s] an agile imager
    scenario.sim_settings.record_interval_s = 5.0
    planning = analysis.plan(scenario)
    result = analysis.fly(scenario, planning.plan)
    return scenario, planning, result


def test_the_executor_flies_every_activity_and_logs_it(flown):
    """Each planned activity appears in the executor's activity log over
    its interval, in its mode; outside activities the default mode."""
    scenario, planning, result = flown
    mode = result.series["eo-sat.plan.mode"]
    activity = result.series["eo-sat.plan.activity"]
    mine = sorted(planning.plan.of("eo-sat"), key=lambda a: a.start_s)
    assert len(mine) >= 3
    t = mode.time_s
    for index, item in enumerate(mine):
        inside = (t >= item.start_s) & (t < item.end_s)
        assert inside.any() and np.all(activity.data[inside, 0] == index)
        assert np.all(mode.data[inside, 0] == execution.MODES.index(item.pointing))
    idle = activity.data[:, 0] == -1
    assert np.all(mode.data[idle, 0] == execution.MODES.index("sun"))


def test_devices_are_on_only_during_their_activities(flown):
    """The camera's data appears only during acquisitions (80 kbit/s x 20 s
    each, on top of the always-on housekeeping); the transmitter takes data
    down only during contacts."""
    scenario, planning, result = flown
    generated = result.series["eo-sat.data_handling.data_generated"]
    t = generated.time_s
    images = [a for a in planning.plan.activities if a.kind == "acquisition"]
    housekeeping = 4000.0 * t[-1]
    assert generated.data[-1, 0] == pytest.approx(housekeeping + 80000.0 * 20.0 * len(images), rel=2e-3)
    rate = result.series["eo-sat.data_handling.downlink_rate"]
    contacts = [a for a in planning.plan.activities if a.kind == "contact"]
    during = np.zeros(len(rate.time_s), dtype=bool)
    for contact in contacts:
        during |= (rate.time_s >= contact.start_s) & (rate.time_s <= contact.end_s + 10.0)
    assert np.all(rate.data[~during, 0] == 0.0) and np.any(rate.data[during, 0] > 0.0)


def test_the_flown_plan_agrees_with_the_planner(flown):
    """Verification: every activity flown with its slew finished, the
    battery within 5 points, the memory within 2 % of its capacity, the
    target geometry within 1 deg; nothing flagged."""
    scenario, planning, result = flown
    checked = verify.check(scenario, planning.plan, result)
    assert all(a.flown and a.slew_done for a in checked.activities)
    resources = checked.resources[0]
    assert resources.soc_max_difference_points < 5.0 and resources.memory_max_difference_fraction < 0.02
    for a in checked.activities:
        if a.off_nadir_planned_deg is not None:
            assert abs(a.off_nadir_flown_deg - a.off_nadir_planned_deg) < 1.0
            assert abs(a.sun_elevation_flown_deg - a.sun_elevation_planned_deg) < 0.5
        if a.kind == "contact":
            assert a.margin_min_db is not None and a.downlinked_bit > 0.0
    assert checked.flags == []
    assert "| A0001 |" in "\n".join(checked.markdown())


def test_a_soft_controller_is_flagged(flown):
    """With the template's default (soft) gains the same plan's slews do
    not finish in time: the verification says which and by how much."""
    scenario, planning, _result = flown
    soft = scenario.__class__.from_dict(scenario.to_dict())
    soft.spacecraft[0].control_params = {"K": 0.02, "P": 0.3}  # [N*m], [N*m*s]
    result = analysis.fly(soft, planning.plan)
    checked = verify.check(soft, planning.plan, result)
    assert any("slew not finished" in flag for flag in checked.flags)


def test_the_run_without_a_plan_is_unchanged(flown):
    """A run of the same scenario without a plan builds no executor and
    records no plan series (the template's behaviour is untouched)."""
    from spacemissionstudio.engine.service import SimulationService

    scenario, _planning, _result = flown
    short = scenario.__class__.from_dict(scenario.to_dict())
    short.sim_settings.duration_days = 0.01
    service = SimulationService(short)
    result = service.run()
    assert not any(".plan." in name for name in result.series)
    assert all(h.plan_executor is None for h in service._handles.values())


def test_flight_scenario_turns_planned_maneuvers_into_a_sequence(flown):
    """A planned maneuver becomes propagate-to-epoch and maneuver commands
    (O-16); the run lasts to the plan's end."""
    from spacemissionstudio.operations.plan import Activity, Plan

    scenario, planning, _result = flown
    burn = Activity("B1", "eo-sat", "raise", "maneuver", 3600.0, 3660.0, start_utc="2030-01-01T09:30:00.000Z")
    data = scenario.to_dict()
    data["operations"]["activity_types"].append({"name": "raise", "kind": "maneuver", "pointing": "sun",
                                                 "duration_s": 60.0, "delta_v_m_s": [0.0, 0.1, 0.0], "frame": "vnb"})
    with_burn = scenario.__class__.from_dict(data)
    plan = Plan(scenario.epoch_utc, planning.plan.start_s, planning.plan.end_s, planning.plan.start_utc,
                planning.plan.end_utc, [burn])
    flown_scenario = analysis.flight_scenario(with_burn, plan)
    kinds = [(c.kind, c.params.get("stop_epoch_utc") or c.params.get("delta_v_m_s")) for c in
             flown_scenario.mission_sequence]
    assert kinds == [("propagate", "2030-01-01T09:30:00.000Z"), ("maneuver", [0.0, 0.1, 0.0]),
                     ("propagate", planning.plan.end_utc)]
    assert flown_scenario.sim_settings.duration_days == pytest.approx(2.0 / 24.0, abs=1e-6)


def test_a_flight_can_be_stopped(flown):
    """With should_cancel the flight runs in chunks and stops after the
    first one that finds it set (Run › Plan's Stop)."""
    from spacemissionstudio.engine.service import SimulationCancelled

    scenario, planning, _result = flown
    asked = []
    with pytest.raises(SimulationCancelled):
        analysis.fly(scenario, planning.plan, should_cancel=lambda: asked.append(1) or True)
    assert asked == [1]
