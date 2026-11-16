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
"""How robust a plan is (design 2.11, decision O-18), and two plans
compared.

The robustness batch draws, per run (``numpy.random.default_rng(seed)``,
recorded): lost passes (each planned contact lost with a probability), a
degraded link (an offset added to every predicted margin, normal with a
given sigma), pointing time (every slew scaled, uniform within a given
spread) and the initial state of charge (uniform within a range). Each
draw either re-checks the plan as it is, activity by activity in time
order with the planner's own constraints (an activity that no longer
fits is lost, with its reason), or replans with the draw's conditions.
The batch is an ``engine.monte_carlo_results.MonteCarloBatch`` of kind
``operations``: each spacecraft's state of charge and memory per draw,
the drawn values and the outcomes in the table.
"""

from __future__ import annotations

import copy
from collections import Counter
from dataclasses import dataclass, field

import numpy as np

from . import analysis
from .plan import Plan
from .scheduler import Candidate, Scheduler


@dataclass
class Draw:
    """One run of the batch: what was drawn and what came out."""

    run: int
    lost_passes: list
    margin_offset_db: float
    slew_scale: float
    initial_soc: float | None
    acquisitions: int = 0
    acquisitions_lost: int = 0
    contacts_lost: int = 0
    min_soc: float = 1.0
    lost_bit: float = 0.0
    backlog_bit: float = 0.0
    reasons: dict = field(default_factory=dict)
    profiles: dict = field(default_factory=dict)  # "<sc> state of charge" / "<sc> memory" -> samples


def _perturbed(planning, plan: Plan, draw: Draw):
    scenario = copy.deepcopy(planning.scenario)
    if draw.initial_soc is not None:
        for sc in scenario.spacecraft:
            if sc.power is not None and scenario.operations.planned(sc.name) is not None:
                sc.power.battery_initial_soc = draw.initial_soc
    slews = {}
    for name, model in planning.slew_models.items():
        slews[name] = copy.copy(model)
        slews[name].scale = draw.slew_scale
    scheduler = Scheduler(scenario, planning.geometry, planning.opportunities, planning.timebase, slews)
    scheduler.notes = []
    for state in scheduler.states.values():
        state.model.margin_offset_db = draw.margin_offset_db
        fresh = scheduler._fresh(state.model)
        for attr in ("cosine", "load", "rate_in", "rate_out", "energy", "memory", "lost"):
            setattr(state, attr, getattr(fresh, attr))
    scheduler.lost_passes = set(draw.lost_passes)
    return scenario, scheduler


def check_plan(planning, plan: Plan, draw: Draw, keep_ids: bool = False) -> Plan:
    """Re-check ``plan`` under the draw's conditions: each activity in time
    order is kept if it still fits. ``keep_ids``: the activities kept keep
    their ids and locks (an edit of the plan), else they are numbered anew."""
    scenario, scheduler = _perturbed(planning, plan, draw)
    reasons = Counter()
    kept = {}
    for activity in sorted(plan.activities, key=lambda a: (a.start_s, a.spacecraft)):
        item = None
        if activity.kind == "contact":
            item = next((p for p in planning.opportunities.passes_of(activity.spacecraft, activity.station)
                         if p.aos_s - 1e-6 <= activity.start_s <= p.los_s + 1e-6), None)
            if item is not None and (item.station, item.spacecraft, round(item.aos_s)) in scheduler.lost_passes:
                reasons["lost_pass"] += 1
                draw.contacts_lost += 1
                continue
        trial = copy.copy(activity)
        trial.predicted = {}
        trial.locked = False
        state = scheduler.states[activity.spacecraft]
        reason, pieces = scheduler._check(state, trial, None)
        if reason is not None:
            reasons[reason] += 1
            if activity.kind == "acquisition":
                draw.acquisitions_lost += 1
            elif activity.kind == "contact":
                draw.contacts_lost += 1
            continue
        window = next((w for w in planning.opportunities.windows_of(activity.target, activity.spacecraft)
                       if w.start_s - 1e-6 <= activity.start_s <= w.end_s + 1e-6), None) if activity.target else None
        scheduler._fill_prediction(trial, Candidate(activity.spacecraft, trial.start_s, trial.end_s, 0.0, window,
                                                    activity.station, item), pieces)
        scheduler._commit(state, trial, pieces)
        kept[id(trial)] = activity
    draw.reasons = dict(reasons)
    result = scheduler.plan()
    if keep_ids:
        for activity in result.activities:
            original = kept.get(id(activity))
            if original is not None:
                activity.id, activity.locked = original.id, original.locked
                activity.predicted.update({k: v for k, v in original.predicted.items() if k not in activity.predicted})
        result.unscheduled = list(plan.unscheduled)
        result.provenance = dict(plan.provenance, edited=True)
    return result


def _outcome(draw: Draw, result: Plan, every: slice) -> None:
    draw.acquisitions = sum(1 for a in result.activities if a.kind == "acquisition")
    for name, resources in result.resources.items():
        draw.min_soc = min(draw.min_soc, resources["min_soc"])
        draw.lost_bit += resources["lost_bit"]
        memory = np.asarray(resources["memory_bit"], dtype=float)
        draw.backlog_bit += float(memory[-1]) if len(memory) else 0.0
        draw.profiles[f"{name} state of charge"] = np.asarray(resources["soc"], dtype=float)[every] * 100.0
        draw.profiles[f"{name} memory"] = memory[every] / 1e9


def run(planning, plan: Plan, runs: int, seed: int = 0, lost_pass_probability: float = 0.0,
        margin_sigma_db: float = 0.0, slew_spread: float = 0.0, soc_range: tuple | None = None,
        replan: bool = False) -> list[Draw]:
    """The batch (module docstring); the same seed gives the same draws."""
    rng = np.random.default_rng(seed)
    contacts = [a for a in plan.activities if a.kind == "contact"]
    passes = []
    for activity in contacts:
        item = next((p for p in planning.opportunities.passes_of(activity.spacecraft, activity.station)
                     if p.aos_s - 1e-6 <= activity.start_s <= p.los_s + 1e-6), None)
        if item is not None:
            passes.append((item.station, item.spacecraft, round(item.aos_s)))
    draws = []
    every = slice(None)
    for k in range(runs):
        lost = [key for key in passes if rng.random() < lost_pass_probability]
        offset = float(rng.normal(0.0, margin_sigma_db)) if margin_sigma_db > 0.0 else 0.0
        scale = float(rng.uniform(1.0 - slew_spread, 1.0 + slew_spread)) if slew_spread > 0.0 else 1.0
        soc = float(rng.uniform(*soc_range)) if soc_range is not None else None
        draw = Draw(k, lost, offset, scale, soc)
        if replan:
            scenario, scheduler = _perturbed(planning, plan, draw)
            result = scheduler.run()
            draw.contacts_lost = len(lost)
            draw.acquisitions_lost = max(0, sum(1 for a in plan.activities if a.kind == "acquisition")
                                         - sum(1 for a in result.activities if a.kind == "acquisition"))
            draw.reasons = dict(Counter(u.reason for u in result.unscheduled))
        else:
            result = check_plan(planning, plan, draw)
        _outcome(draw, result, every)
        draws.append(draw)
    return draws


def to_batch(planning, plan: Plan, draws: list[Draw], seed: int, settings: dict):
    """The draws as a ``MonteCarloBatch`` of kind ``operations``."""
    from ..engine.monte_carlo_results import MonteCarloBatch

    first = next(iter(plan.resources.values()))
    time_s = np.asarray(first["time_s"], dtype=float)
    names = list(draws[0].profiles) if draws else []
    profiles = {name: np.vstack([d.profiles[name] for d in draws]) for name in names}
    units = {name: ("%" if name.endswith("state of charge") else "Gbit") for name in names}
    drawn = []
    for d in draws:
        drawn.append({"lost passes [-]": float(len(d.lost_passes)), "link margin offset [dB]": d.margin_offset_db,
                      "slew time scale [-]": d.slew_scale,
                      **({"initial state of charge [-]": d.initial_soc} if d.initial_soc is not None else {}),
                      "outcome: acquisitions [-]": float(d.acquisitions),
                      "outcome: acquisitions lost [-]": float(d.acquisitions_lost),
                      "outcome: contacts lost [-]": float(d.contacts_lost),
                      "outcome: lowest state of charge [%]": 100.0 * d.min_soc,
                      "outcome: data lost [Gbit]": d.lost_bit / 1e9,
                      "outcome: backlog at the end [Gbit]": d.backlog_bit / 1e9})
    return MonteCarloBatch(planning.scenario.name, "earth", time_s, [d.run for d in draws], [], {}, {}, drawn,
                           planning.scenario.epoch_utc, "population", "operations", {},
                           f"robustness, seed {seed}, {settings}", profiles, units)


def compare(a: Plan, b: Plan) -> dict:
    """Two plans side by side: per request whether each holds it, and per
    spacecraft the activity count, contact time, lowest state of charge,
    data lost and the score."""
    def held(plan: Plan) -> Counter:
        return Counter((x.target or x.request or f"contact {x.station}", x.spacecraft) for x in plan.activities)

    ha, hb = held(a), held(b)
    keys = sorted(set(ha) | set(hb))
    requests = [{"request": k[0], "spacecraft": k[1], "a": ha.get(k, 0), "b": hb.get(k, 0)} for k in keys]
    spacecraft = sorted(set(a.resources) | set(b.resources))
    rows = []
    for name in spacecraft:
        row = {"spacecraft": name}
        for label, plan in (("a", a), ("b", b)):
            mine = plan.of(name)
            resources = plan.resources.get(name, {})
            row[label] = {"activities": len(mine), "contact_s": sum(x.duration_s for x in mine if x.kind == "contact"),
                          "acquisitions": sum(1 for x in mine if x.kind == "acquisition"),
                          "min_soc": resources.get("min_soc"), "lost_bit": resources.get("lost_bit"),
                          "max_memory_bit": resources.get("max_memory_bit")}
        rows.append(row)
    only_a = [r for r in requests if r["a"] > r["b"]]
    only_b = [r for r in requests if r["b"] > r["a"]]
    return {"score": {"a": a.score.get("value"), "b": b.score.get("value")}, "requests": requests,
            "spacecraft": rows, "only_in_a": only_a, "only_in_b": only_b,
            "unscheduled": {"a": [(u.request, u.reason) for u in a.unscheduled],
                            "b": [(u.request, u.reason) for u in b.unscheduled]}}


def robustness(scenario, plan: Plan, runs: int, seed: int = 0, result=None, **settings):
    """Prepare the scenario's planning and run the batch: ``(draws, batch)``."""
    planning = analysis.prepare(scenario, result)
    draws = run(planning, plan, runs, seed, **settings)
    return draws, to_batch(planning, plan, draws, seed, settings)
