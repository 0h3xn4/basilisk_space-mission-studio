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
"""What-if events, replanning, the robustness batch, plan comparison and
the executor's contingency rules (operations.whatif, operations.robustness,
operations.execution; decision O-18). The lost-pass backlog is checked
against a hand calculation."""

import numpy as np
import operations_fixtures as fixtures
import pytest

from spacemissionstudio.engine import monte_carlo_results as mcr
from spacemissionstudio.operations import analysis, robustness, whatif
from spacemissionstudio.schema.operations import WhatIfConfig

_DAY = {"start_utc": "2030-01-01T08:30:00Z", "end_utc": "2030-01-02T08:30:00Z"}


@pytest.fixture(scope="module")
def planning():
    return analysis.plan(fixtures.scenario(horizon=_DAY))


def test_a_lost_pass_replanned_leaves_the_hand_calculated_backlog(planning):
    """Housekeeping fills the memory at 4 kbit/s. Losing the 10:17 pass and
    replanning from 10:00: just before the next contact the memory holds
    everything generated since the last contact before the lost one ended,
    4000 bit/s times that gap (the camera's image went down earlier)."""
    scenario, plan = planning.scenario, planning.plan
    contacts = sorted((a for a in plan.activities if a.kind == "contact"), key=lambda a: a.start_s)
    lost = next(a for a in contacts if a.start_utc.startswith("2030-01-01T10:1"))
    event = WhatIfConfig("lost_pass", at_utc=lost.start_utc, station="berlin-gs", spacecraft="eo-sat")
    replanned = whatif.replan(scenario, plan, "2030-01-01T10:00:00Z", [event], planning=planning).plan
    assert lost.start_utc not in {a.start_utc for a in replanned.activities}
    assert any(u.reason == "lost_pass" for u in replanned.unscheduled)
    before = max((a for a in replanned.activities if a.kind == "contact" and a.end_s < lost.start_s),
                 key=lambda a: a.end_s)
    after = min((a for a in replanned.activities if a.kind == "contact" and a.start_s > lost.end_s),
                key=lambda a: a.start_s)
    resources = replanned.resources["eo-sat"]
    t = np.asarray(resources["time_s"])
    memory = np.asarray(resources["memory_bit"])
    k = int(np.searchsorted(t, after.start_s)) - 1  # the profile's last sample (every 60 s) before the contact
    backlog = float(memory[k])
    assert backlog == pytest.approx(4000.0 * (t[k] - before.end_s), rel=0.01)
    kept = set(replanned.provenance["kept"])
    assert kept == {a.id for a in plan.activities if a.start_s < lost.start_s - 600.0}
    assert all(a.locked for a in replanned.activities if a.id in kept)


def test_what_if_events_change_a_copy(planning):
    """A station outage removes the contacts in it, an instrument outage
    the acquisitions using it, an extra request brings a disabled target
    in; the scenario itself is not changed."""
    scenario = planning.scenario
    outage = WhatIfConfig("station_outage", at_utc="2030-01-01T08:30:00Z", until_utc="2030-01-01T12:00:00Z",
                          station="berlin-gs")
    camera = WhatIfConfig("instrument_outage", at_utc="2030-01-01T08:30:00Z", until_utc="2030-01-02T08:30:00Z",
                          spacecraft="eo-sat", instrument="camera")
    changed = whatif.plan_with(scenario, [outage, camera], planning=planning).plan
    assert not [a for a in changed.activities if a.station and a.start_utc < "2030-01-01T12:00"]
    assert not [a for a in changed.activities if a.kind == "acquisition"]
    assert scenario.operations.stations[0].unavailable_utc == []
    data = fixtures.operations_dict(horizon=_DAY)
    data["targets"][1]["enabled"] = False
    quiet = fixtures.scenario(horizon=_DAY, targets=data["targets"])
    assert not [a for a in analysis.plan(quiet).plan.activities if a.target == "munich"]
    extra = whatif.plan_with(quiet, [WhatIfConfig("extra_request", name="munich")]).plan
    assert [a for a in extra.activities if a.target == "munich"]


def test_the_robustness_batch_is_reproducible_and_saves(planning, tmp_path):
    """The same seed gives the same draws; losing every pass loses every
    contact; the batch saves as an 'operations' Monte Carlo summary the
    view reads back."""
    plan = planning.plan
    first = robustness.run(planning, plan, 6, seed=11, lost_pass_probability=0.4, margin_sigma_db=2.0,
                           slew_spread=0.2, soc_range=(0.6, 0.9))
    second = robustness.run(planning, plan, 6, seed=11, lost_pass_probability=0.4, margin_sigma_db=2.0,
                            slew_spread=0.2, soc_range=(0.6, 0.9))
    assert [(d.lost_passes, d.margin_offset_db, d.slew_scale, d.initial_soc, d.min_soc) for d in first] == \
           [(d.lost_passes, d.margin_offset_db, d.slew_scale, d.initial_soc, d.min_soc) for d in second]
    contacts = sum(1 for a in plan.activities if a.kind == "contact")
    every = robustness.run(planning, plan, 2, seed=1, lost_pass_probability=1.0)
    assert all(d.contacts_lost == contacts for d in every)
    assert every[0].backlog_bit > robustness.run(planning, plan, 1, seed=1)[0].backlog_bit
    batch = robustness.to_batch(planning, plan, first, 11, {"lost_pass_probability": 0.4})
    mcr.save(batch, tmp_path)
    loaded = mcr.load(tmp_path)
    assert loaded.kind == "operations" and loaded.items == ["eo-sat state of charge", "eo-sat memory"]
    assert loaded.profiles["eo-sat state of charge"].shape == (6, len(plan.resources["eo-sat"]["time_s"]))
    labels, rows = mcr.run_table(loaded)
    assert "outcome: acquisitions [-]" in labels and len(rows) == 6
    assert any("eo-sat state of charge" in name for name in mcr.to_result_set(loaded).series)
    replanned = robustness.run(planning, plan, 2, seed=5, lost_pass_probability=0.5, replan=True)
    assert len(replanned) == 2 and all(d.profiles for d in replanned)


def test_two_plans_compared(planning):
    """The comparison names what only one plan holds."""
    plan = planning.plan
    lost = WhatIfConfig("station_outage", at_utc="2030-01-01T08:30:00Z", until_utc="2030-01-02T08:30:00Z",
                        station="berlin-gs")
    other = whatif.plan_with(planning.scenario, [lost], planning=planning).plan
    compared = robustness.compare(plan, other)
    assert compared["only_in_a"] and not compared["only_in_b"]
    assert compared["spacecraft"][0]["a"]["contact_s"] > compared["spacecraft"][0]["b"]["contact_s"] == 0.0


def test_contingency_rules_fire_in_the_simulation():
    """Safe mode: below the state of charge floor the executor points at
    the Sun, drops the activities and logs it, until the recovery level.
    Memory: above the fraction it drops acquisitions of the priority or
    lower. Each firing is in the log and in the verification."""
    from spacemissionstudio.operations import verify

    horizon = {"start_utc": "2030-01-01T08:30:00Z", "end_utc": "2030-01-01T09:30:00Z"}
    scenario = fixtures.scenario(horizon=horizon, spacecraft=[{
        "spacecraft": "eo-sat", "contact_activity": "downlink",
        "contingency": {"safe_mode_soc": 0.95, "recover_soc": 0.99}}])
    scenario.spacecraft[0].control_params = {"K": 1.0, "P": 8.0}
    planning = analysis.plan(scenario)
    result = analysis.fly(scenario, planning.plan)
    state = result.series["eo-sat.plan.contingency"]
    assert state.data[0, 0] == 1.0  # the battery starts at 0.9: safe mode from the first step
    checked = verify.check(scenario, planning.plan, result)
    assert checked.contingency["eo-sat"] and checked.contingency["eo-sat"][0][1] == 0  # recovered
    safe = state.data[:, 0] == 1.0
    activity = result.series["eo-sat.plan.activity"].data[:, 0]
    mode = result.series["eo-sat.plan.mode"].data[:, 0]
    assert np.all(activity[safe] == -1) and np.all(mode[safe] == 0)  # no activity, Sun pointing
    soc = result.series["eo-sat.battery_charge"]
    recovered = np.interp(result.series["eo-sat.plan.contingency"].time_s[np.argmin(safe)], soc.time_s,
                          soc.data[:, 0]) / scenario.spacecraft[0].power.battery_capacity_wh
    assert recovered >= 0.99 - 0.002
    memory = fixtures.scenario(horizon=horizon, spacecraft=[{
        "spacecraft": "eo-sat", "contact_activity": "downlink",
        "contingency": {"memory_fraction": 1e-9, "drop_priority": 1}}])
    memory.spacecraft[0].control_params = {"K": 1.0, "P": 8.0}
    planned = analysis.plan(memory)
    flown = analysis.fly(memory, planned.plan)
    images = [a for a in verify.check(memory, planned.plan, flown).activities if a.kind == "acquisition"]
    assert images and not any(a.flown for a in images)
