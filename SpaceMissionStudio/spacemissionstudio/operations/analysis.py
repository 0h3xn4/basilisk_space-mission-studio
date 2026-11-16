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
"""One entry point for the API, the command line and the GUI: geometry,
opportunities and the scheduler, with the plan's provenance."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, UTC

from . import attitude, geometry as geometry_model, opportunities as opportunity_model
from .plan import Plan
from .scheduler import Scheduler
from .timebase import TimeBase, format_utc


class PlanningError(Exception):
    """The scenario cannot be planned (no operations section, a geometry
    that cannot be built)."""


@dataclass
class Planning:
    """What a planning run built, kept for verification, exports and the
    GUI."""

    scenario: object
    timebase: TimeBase
    geometry: object
    opportunities: object
    slew_models: dict
    plan: Plan | None = None
    seconds: dict | None = None  # time taken by each stage [s]


def prepare(scenario, result=None) -> Planning:
    """Geometry and opportunities of the scenario's ``operations`` section."""
    if getattr(scenario, "operations", None) is None:
        raise PlanningError("the scenario has no 'operations' section")
    scenario.validate()
    timebase = TimeBase(scenario.epoch_utc)
    began = time.perf_counter()
    try:
        geometry = geometry_model.build(scenario, result)
    except geometry_model.GeometryError as exc:
        raise PlanningError(str(exc)) from exc
    built = time.perf_counter()
    opportunities = opportunity_model.find(scenario, geometry, timebase)
    found = time.perf_counter()
    spacecraft = {sc.name: sc for sc in scenario.spacecraft}
    slews = {p.spacecraft: attitude.slew_model(spacecraft[p.spacecraft], p.agility, scenario)
             for p in scenario.operations.spacecraft}
    return Planning(scenario, timebase, geometry, opportunities, slews,
                    seconds={"geometry": built - began, "opportunities": found - built})


def schedule(planning: Planning, scheduler_hook=None) -> Plan:
    """Schedule on a prepared :class:`Planning` and record the plan's
    provenance."""
    began = time.perf_counter()
    scheduler = Scheduler(planning.scenario, planning.geometry, planning.opportunities, planning.timebase,
                          planning.slew_models)
    if scheduler_hook is not None:
        scheduler_hook(scheduler)
    plan = scheduler.run()
    planning.seconds["schedule"] = time.perf_counter() - began
    plan.provenance = provenance(planning)
    planning.plan = plan
    return plan


def provenance(planning: Planning) -> dict:
    from .. import __version__
    from ..output_provenance import scenario_sha256

    scenario = planning.scenario
    section = scenario.operations
    return {"tool": "SpaceMissionStudio", "tool_version": __version__, "scenario": scenario.name,
            "scenario_sha256": scenario_sha256(scenario), "created_utc": format_utc(datetime.now(UTC).replace(tzinfo=None)),
            "geometry_source": planning.geometry.source, "geometry_step_s": planning.geometry.step_s,
            "seed": section.scheduler.seed, "improvement_iterations": section.scheduler.improvement_iterations,
            "objective": section.scheduler.objective, "weights": dict(section.scheduler.weights),
            "slew_models": {name: model.description for name, model in planning.slew_models.items()},
            "seconds": {k: round(v, 3) for k, v in (planning.seconds or {}).items()},
            "note": "a planning product: not a flight command load"}


def plan(scenario, result=None) -> Planning:
    """Prepare and schedule: the plan is ``.plan``."""
    planning = prepare(scenario, result)
    schedule(planning)
    return planning
