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
"""What-if events and replanning from a time (design 2.11).

What-if events change a copy of the inputs, never the scenario: a lost
pass (the pass of a station and a spacecraft in force at a time), a
station outage, an instrument outage, an extra request (a target or
request kept disabled until then), a delayed maneuver.

Replanning from a time T (rolling horizon): the activities of the plan
that start before T are kept as they are (locked: they have flown, or are
flying); what they satisfied is not asked for again; nothing new starts
before T; the scheduler fills the rest of the horizon. The battery and
the memory follow from the kept activities (the plan's own profile up to
T: the state at T is what the plan predicted).
"""

from __future__ import annotations

import copy
from collections import Counter

from ..schema.operations import LockedActivityConfig, WhatIfConfig
from . import analysis
from .plan import Plan

_MATCH_S = 1.0  # [s] a time given in UTC text (rounded to the millisecond) still names its pass
_TEXT_S = 1.0e-3  # [s] UTC text is rounded to the millisecond: a start within it of T starts at T


class WhatIf:
    """Events applied to a scheduler (``hook``) and to a scenario copy
    (``scenario``)."""

    def __init__(self, scenario, events: list[WhatIfConfig]):
        self.events = list(events)
        self.scenario = copy.deepcopy(scenario)
        section = self.scenario.operations
        for event in self.events:
            if event.kind == "station_outage":
                settings = section.station(event.station)
                if settings is None:
                    from ..schema.operations import StationPlanningConfig

                    settings = StationPlanningConfig(event.station)
                    section.stations.append(settings)
                settings.unavailable_utc.append([event.at_utc, event.until_utc])
            elif event.kind == "extra_request":
                for item in list(section.targets) + list(section.requests):
                    if item.name == event.name:
                        item.enabled = True

    def hook(self, scheduler) -> None:
        """Apply the events that act inside the scheduler."""
        base = scheduler.timebase
        for event in self.events:
            if event.kind == "lost_pass":
                at = base.to_sim(event.at_utc)
                for item in scheduler.opportunities.passes_of(event.spacecraft, event.station):
                    if item.aos_s - _MATCH_S <= at <= item.los_s + _MATCH_S:
                        scheduler.lost_passes.add((item.station, item.spacecraft, round(item.aos_s)))
            elif event.kind == "instrument_outage":
                scheduler.instrument_outages.setdefault((event.spacecraft, event.instrument), []).append(
                    (base.to_sim(event.at_utc), base.to_sim(event.until_utc)))
            elif event.kind == "delayed_maneuver":
                scheduler._delays[event.name] = float(event.delay_s)


def plan_with(scenario, events=None, result=None, planning=None):
    """A plan with ``events`` (the scenario's own ``what_if`` when None)
    applied: the ``Planning`` (its scenario is the changed copy)."""
    events = scenario.operations.what_if if events is None else events
    what = WhatIf(scenario, events)
    if planning is None:
        planning = analysis.prepare(what.scenario, result)
    else:
        planning = copy.copy(planning)
        planning.scenario = what.scenario
        planning.seconds = dict(planning.seconds or {})
    analysis.schedule(planning, what.hook)
    planning.plan.provenance["what_if"] = [vars(e) for e in what.events]
    return planning


def replan(scenario, plan: Plan, from_utc: str, events=None, result=None, planning=None):
    """Replan from ``from_utc`` (module docstring): the ``Planning`` with
    the new plan; activities starting before then are kept with their ids."""
    from .timebase import TimeBase

    base = TimeBase(scenario.epoch_utc)
    t0 = base.to_sim(from_utc)
    kept = [a for a in plan.activities if a.start_s < t0 - _TEXT_S]
    changed = copy.deepcopy(scenario)
    section = changed.operations
    section.locked = [item for item in section.locked if base.to_sim(item.start_utc) >= t0 - _TEXT_S]
    done = Counter()
    for activity in kept:
        section.locked.append(LockedActivityConfig(activity.id, activity.spacecraft, activity.type, activity.start_utc,
                                                   activity.end_utc, activity.target, activity.station,
                                                   activity.request.split("#")[0] if activity.request else ""))
        if activity.target:
            done[activity.target] += 1
        elif activity.request:
            done[activity.request.split("#")[0]] += 1
    events = list(section.what_if if events is None else events)
    what = WhatIf(changed, events)

    def hook(scheduler) -> None:
        what.hook(scheduler)
        scheduler.not_before = t0
        scheduler.done = done

    if planning is None:
        planning = analysis.prepare(what.scenario, result)
    else:
        planning = copy.copy(planning)
        planning.scenario = what.scenario
        planning.seconds = dict(planning.seconds or {})
    analysis.schedule(planning, hook)
    new = planning.plan
    new.provenance.update(replanned_from_utc=base.text(t0), replanned_from_plan=plan.provenance.get("scenario_sha256"),
                          what_if=[vars(e) for e in events], kept=[a.id for a in kept])
    for activity in new.activities:  # what was kept keeps being shown as flown, not as the user's lock
        if activity.id in {a.id for a in kept}:
            activity.predicted["kept_from_plan"] = True
    return planning
