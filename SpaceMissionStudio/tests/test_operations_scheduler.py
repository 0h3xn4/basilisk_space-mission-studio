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
"""The scheduler (operations.scheduler; decisions O-10 to O-13): no hard
constraint broken over seeded random instances, the same plan for the
same inputs, locked activities kept, reasons given, contention by
priority and fairness, the improvement step, and the optimality gap
against brute force on small instances. Analytic geometry; no Basilisk
run."""

import copy
import itertools
import json

import numpy as np
import operations_fixtures as fixtures
import pytest

from spacemissionstudio.operations import analysis
from spacemissionstudio.operations.plan import Plan, REASONS
from spacemissionstudio.operations.scheduler import Scheduler

_TWO_DAYS = {"start_utc": "2030-01-01T08:30:00Z", "end_utc": "2030-01-03T08:30:00Z"}
_CITIES = [("rotterdam", 51.92, 4.48), ("munich", 48.14, 11.58), ("lyon", 45.76, 4.84), ("prague", 50.08, 14.44),
           ("milan", 45.46, 9.19), ("vienna", 48.21, 16.37), ("zurich", 47.37, 8.54), ("hamburg", 53.55, 9.99),
           ("krakow", 50.06, 19.94), ("turin", 45.07, 7.69), ("leipzig", 51.34, 12.37), ("graz", 47.07, 15.44)]


def _targets(rng, count):
    picks = rng.choice(len(_CITIES), size=count, replace=False)
    return [{"name": _CITIES[k][0], "priority": int(rng.integers(1, 4)), "activity": "image",
             "max_off_nadir_deg": float(rng.uniform(25.0, 45.0)), "latitude_deg": _CITIES[k][1],
             "longitude_deg": _CITIES[k][2], "acquisitions": int(rng.integers(1, 3))} for k in sorted(picks)]


def _hard_violations(scenario, planning, plan) -> list[str]:
    """Every hard constraint checked again on the finished plan, from
    scratch."""
    found = []
    section = scenario.operations
    by_sc = {}
    for activity in plan.activities:
        by_sc.setdefault(activity.spacecraft, []).append(activity)
    for name, items in by_sc.items():
        items.sort(key=lambda a: a.start_s)
        for a, b in zip(items, items[1:]):
            if a.occupied[1] > b.occupied[0] + 1e-6:
                found.append(f"{a.id} and {b.id} overlap")
        settings = section.planned(name)
        resources = plan.resources[name]
        if settings.min_soc is not None and resources["min_soc"] < settings.min_soc - 1e-9:
            found.append(f"{name}: state of charge {resources['min_soc']:.3f}")
        if resources["lost_bit"] > 1.0:
            found.append(f"{name}: {resources['lost_bit']:.0f} bit lost")
        for activity in items:
            if activity.locked:
                continue
            kind = section.activity_type(activity.type)
            if kind.kind == "acquisition":
                window = next((w for w in planning.opportunities.windows_of(activity.target, name)
                               if w.start_s - 1e-6 <= activity.start_s and activity.end_s <= w.end_s + 1e-6), None)
                if window is None:
                    found.append(f"{activity.id}: outside every window of {activity.target}")
            if kind.kind == "contact":
                item = next((p for p in planning.opportunities.passes_of(name, activity.station)
                             if p.aos_s - 1e-6 <= activity.start_s and activity.end_s <= p.los_s + 1e-6), None)
                if item is None or activity.duration_s < kind.min_duration_s - 1e-6:
                    found.append(f"{activity.id}: not inside a pass for its minimum duration")
    for note in plan.notes:
        if "no time for its slew" in note:
            found.append(note)
    stations = {}
    for activity in plan.activities:
        if activity.station:
            stations.setdefault(activity.station, []).append(activity)
    for station, items in stations.items():
        items.sort(key=lambda a: a.start_s)
        for a, b in zip(items, items[1:]):
            if a.end_s > b.start_s - 1e-6:
                found.append(f"station {station}: {a.id} and {b.id} overlap")
    return found


@pytest.mark.parametrize("seed", range(6))
def test_no_hard_constraint_is_broken_over_seeded_random_instances(seed):
    """Random targets, priorities, limits and battery floor: the finished
    plan keeps every hard constraint (property test)."""
    rng = np.random.default_rng(seed)
    scenario = fixtures.scenario(horizon=_TWO_DAYS, targets=_targets(rng, 8), spacecraft=[
        {"spacecraft": "eo-sat", "contact_activity": "downlink", "min_soc": float(rng.uniform(0.3, 0.8)),
         "max_activities_per_orbit": int(rng.integers(1, 4))}])
    planning = analysis.plan(scenario)
    assert _hard_violations(scenario, planning, planning.plan) == []
    per_orbit = scenario.operations.planned("eo-sat").max_activities_per_orbit
    period = 5760.0  # [s] about 96 min at 550 km
    counts = {}
    for activity in planning.plan.activities:
        if activity.kind != "contact":
            counts.setdefault(int((activity.start_s - planning.plan.start_s) // (period * 0.995)), []).append(activity)
    assert all(len(v) <= per_orbit + 1 for v in counts.values())


def test_the_same_inputs_give_the_same_plan():
    """Determinism: two runs give byte-identical plans (but for the
    creation time and the timings)."""
    scenario = fixtures.scenario(horizon=_TWO_DAYS, scheduler={"seed": 7, "improvement_iterations": 5})
    first, second = (analysis.plan(copy.deepcopy(scenario)).plan.to_dict() for _ in range(2))
    for plan in (first, second):
        plan["provenance"].pop("created_utc")
        plan["provenance"].pop("seconds")
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_locked_activities_are_kept_and_planned_around():
    """A locked calibration stays exactly where the user put it; nothing
    else overlaps it; it is flagged locked and keeps its id."""
    locked = [{"id": "mine", "spacecraft": "eo-sat", "activity": "star cal", "start_utc": "2030-01-01T09:00:00Z",
               "end_utc": "2030-01-01T09:05:00Z"}]
    scenario = fixtures.scenario(horizon=_TWO_DAYS, locked=locked)
    planning = analysis.plan(scenario)
    plan = planning.plan
    kept = plan.find("mine")
    assert kept is not None and kept.locked
    assert kept.start_utc == "2030-01-01T09:00:00.000Z" and kept.end_utc == "2030-01-01T09:05:00.000Z"
    assert _hard_violations(scenario, planning, plan) == []


def test_unscheduled_requests_say_why():
    """A target nothing can see says 'no window'; one valid only when it
    cannot be seen says so; a battery floor above what is possible gives
    'battery'; every reason has its text."""
    targets = [{"name": "south-pole", "priority": 1, "activity": "image", "max_off_nadir_deg": 10.0,
                "latitude_deg": -89.9, "longitude_deg": 0.0, "sun_elevation_deg": [30.0, 90.0]},
               {"name": "munich", "priority": 2, "activity": "image", "max_off_nadir_deg": 45.0,
                "latitude_deg": 48.14, "longitude_deg": 11.58,
                "valid_utc": ["2030-01-01T12:00:00Z", "2030-01-01T13:00:00Z"]}]
    plan = analysis.plan(fixtures.scenario(horizon=_TWO_DAYS, targets=targets)).plan
    reasons = {u.request: u.reason for u in plan.unscheduled}
    assert reasons["south-pole"] == "no_opportunity" and reasons["munich"] == "outside_validity"
    types = fixtures.operations_dict()["activity_types"]
    types[0]["power_w"] = 30000.0  # [W] 167 W*h in 20 s: the 300 W*h battery would fall below half
    hungry = fixtures.scenario(horizon=_TWO_DAYS, activity_types=types, spacecraft=[{"spacecraft": "eo-sat",
                                                                                    "min_soc": 0.5}])
    plan = analysis.plan(hungry).plan
    assert {u.request: u.reason for u in plan.unscheduled}["munich"] == "battery"
    assert plan.resources["eo-sat"]["min_soc"] >= 0.5
    assert all(u.text == REASONS[u.reason] for u in plan.unscheduled)


def test_contention_goes_by_priority_then_fairness():
    """Two spacecraft in the same orbit a minute apart want every pass of
    one station of capacity 1: the higher contact priority wins the first
    contested pass; with equal priorities they alternate (the one with less
    contact time so far wins)."""
    data = fixtures.scenario_dict(horizon=_TWO_DAYS)
    twin = copy.deepcopy(data["spacecraft"][0])
    twin["name"] = "eo-twin"
    twin["orbit"]["true_anomaly_deg"] = 1.0
    data["spacecraft"].append(twin)
    data["operations"]["targets"] = []
    data["operations"]["requests"] = []
    data["operations"]["spacecraft"] = [{"spacecraft": "eo-sat", "contact_activity": "downlink", "contact_priority": 2},
                                        {"spacecraft": "eo-twin", "contact_activity": "downlink", "contact_priority": 1}]
    from spacemissionstudio.schema.scenario import Scenario

    scenario = Scenario.from_dict(data)
    plan = analysis.plan(scenario).plan
    contested = plan.contention
    assert contested and contested[0]["served"][0] == "eo-twin"
    data["operations"]["spacecraft"][0]["contact_priority"] = 1
    fair = analysis.plan(Scenario.from_dict(data)).plan
    firsts = [c["served"][0] for c in fair.contention if c["served"]]
    assert "eo-sat" in firsts and "eo-twin" in firsts
    hours = {name: sum(a.duration_s for a in fair.of(name)) for name in ("eo-sat", "eo-twin")}
    assert abs(hours["eo-sat"] - hours["eo-twin"]) < 0.5 * max(hours.values())


def test_the_plan_file_round_trips():
    """The plan saves to JSON (no NaN) and loads back equal."""
    plan = analysis.plan(fixtures.scenario(horizon=_TWO_DAYS)).plan
    data = json.loads(json.dumps(plan.to_dict(), allow_nan=False))
    again = Plan.from_dict(data)
    assert again.activities == plan.activities and again.unscheduled == plan.unscheduled
    assert data["format"] == "spacemissionstudio-plan" and data["provenance"]["geometry_source"] == "analytic"
    with pytest.raises(ValueError, match="not a SpaceMissionStudio plan"):
        Plan.from_dict({"format": "other"})


def _brute_force(scenario, planning):
    """The best lexicographic score over every subset of placements:
    each request either left out or at one of its top candidates, inserted
    in time order with the scheduler's own checks."""
    base = Scheduler(scenario, planning.geometry, planning.opportunities, planning.timebase, planning.slew_models)
    requests = base.requests()
    options = []
    for request in requests:
        # per window: its best position, its earliest and its latest
        candidates = [c for c in base.candidates(request) if c.quality != float("-inf")]
        per_window = {}
        for c in candidates:
            per_window.setdefault(id(c.window), []).append(c)
        chosen = []
        for group in per_window.values():
            chosen += [group[0], min(group, key=lambda c: c.start_s), max(group, key=lambda c: c.start_s)]
        options.append([None] + chosen)
    best = None
    for choice in itertools.product(*options):
        trial = Scheduler(scenario, planning.geometry, planning.opportunities, planning.timebase, planning.slew_models)
        trial.notes = []
        picked = [(r, c) for r, c in zip(requests, choice) if c is not None]
        names = [(r.name, r.occurrence) for r, _c in picked]
        ok = len(set(names)) == len(names)
        for request, candidate in sorted(picked, key=lambda rc: rc[1].start_s):
            if not ok:
                break
            kind = scenario.operations.activity_type(request.type)
            activity = trial._activity(request, candidate, kind)
            reason, pieces = trial._check(trial.states[candidate.spacecraft], activity, request)
            if reason is not None:
                ok = False
                break
            trial._fill_prediction(activity, candidate, pieces)
            trial._commit(trial.states[candidate.spacecraft], activity, pieces)
        if ok:
            score = trial.score()[:-1]
            best = score if best is None or score > best else best
    return best


@pytest.mark.parametrize("seed", range(4))
def test_the_greedy_plan_is_close_to_the_brute_force_optimum(seed):
    """Small instances (four targets, no contacts): the scheduler with its
    improvement step places at most one acquisition fewer than the best
    of every subset over each window's best, earliest and latest
    positions (the brute force's own candidate set, narrower than the
    scheduler's: it can do better; the gap is recorded in
    compliance/validation/operations-vv.md)."""
    rng = np.random.default_rng(100 + seed)
    targets = _targets(rng, 4)
    for target in targets:
        target["acquisitions"] = 1
    scenario = fixtures.scenario(horizon=_TWO_DAYS, targets=targets, requests=[], spacecraft=[
        {"spacecraft": "eo-sat", "min_soc": 0.3}], scheduler={"seed": seed, "improvement_iterations": 20})
    planning = analysis.plan(scenario)
    greedy = tuple(planning.plan.score["value"][:-1])
    optimum = _brute_force(scenario, analysis.prepare(scenario))
    assert len(greedy) == len(optimum)
    assert sum(optimum) - sum(greedy) <= 1


def test_the_improvement_step_never_makes_the_plan_worse():
    """With improvement iterations the score is at least the constructive
    plan's, and the seed is recorded."""
    rng = np.random.default_rng(3)
    targets = _targets(rng, 10)
    plain = analysis.plan(fixtures.scenario(horizon=_TWO_DAYS, targets=targets)).plan
    better = analysis.plan(fixtures.scenario(horizon=_TWO_DAYS, targets=targets,
                                             scheduler={"seed": 3, "improvement_iterations": 30})).plan
    assert tuple(better.score["value"]) >= tuple(plain.score["value"])
    assert better.provenance["seed"] == 3 and better.provenance["improvement_iterations"] == 30
