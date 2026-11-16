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
"""The thermal analysis of one spacecraft after a run (decision T-01):
the same engine behind Run › Thermal, ``spacemissionstudio thermal`` and
``api.thermal``.

:func:`prepare` builds what does not change between cases once: the
geometry from the 3D model and the incident fluxes on every facet from
the run (``thermal.environment``). :func:`solve_case` then builds a case's
network, its absorbed loads and solves it; repeated solves (cases,
sweeps, Monte Carlo) reuse the prepared fluxes and never rerun Basilisk.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from ..schema import thermal as thermal_schema
from . import cases as cases_module
from . import checks, environment, geometry, network, results, solver


class ThermalAnalysisError(ValueError):
    """The analysis cannot run, saying why (no thermal section, no model,
    a run without what the fluxes need)."""


@dataclass
class Prepared:
    """What stays the same for every case of one spacecraft and run."""

    scenario: object
    spacecraft: object
    geometry: geometry.Geometry
    environment: environment.Environment
    context: thermal_schema.ThermalContext
    shading: object | None  # the shading warning (a Finding) or None
    warnings: list = field(default_factory=list)

    @property
    def mean_beta_deg(self) -> float:
        return float(np.mean(np.abs(self.environment.beta_deg)))


@dataclass
class ThermalAnalysis:
    """Every case solved for one spacecraft."""

    prepared: Prepared
    cases: list[results.CaseResult]

    @property
    def spacecraft(self) -> str:
        return self.prepared.spacecraft.name

    def case(self, name: str) -> results.CaseResult:
        return next(c for c in self.cases if c.name == name)

    def events(self) -> list:
        return [event for case in self.cases for event in case.events]

    def findings(self) -> list:
        found = [self.prepared.shading] if self.prepared.shading is not None else []
        return found + list(self.prepared.warnings) + [f for case in self.cases for f in case.findings]


def prepare(scenario, result, sc_name: str, base_dir=None) -> Prepared:
    """The geometry and the run's fluxes for spacecraft ``sc_name``."""
    sc = next((s for s in scenario.spacecraft if s.name == sc_name), None)
    if sc is None:
        raise ThermalAnalysisError(f"no spacecraft named {sc_name!r}")
    if sc.thermal is None:
        raise ThermalAnalysisError(f"{sc_name} has no thermal model (Spacecraft › Thermal, or generate one from "
                                   "its 3D model)")
    if sc.model is None:
        raise ThermalAnalysisError(f"{sc_name} has no 3D model: the thermal model is built on it")
    geom = geometry.build(sc.model, base_dir)
    try:
        env = environment.build(result, sc_name, scenario.gravity.central_body, geom.facets)
    except environment.ThermalEnvironmentError as exc:
        raise ThermalAnalysisError(str(exc)) from exc
    warnings = [f"{sc_name}: thermal: {w}" for w in env.warnings]
    return Prepared(scenario, sc, geom, env, thermal_schema.context_for(sc), checks.shading_warning(sc, geom),
                    warnings)


def solve_case(prepared: Prepared, case: thermal_schema.ThermalCaseConfig, size_heaters: bool = True,
               step_check: bool = True, thermal=None) -> results.CaseResult:
    """Solve ``case`` on ``prepared`` (``thermal``: the section to start
    from, the spacecraft's by default)."""
    sc = prepared.spacecraft
    env = prepared.environment
    resolved = cases_module.resolve(thermal if thermal is not None else sc.thermal, case, env.central_body, env.band,
                                    prepared.mean_beta_deg, prepared.context, f"{sc.name}: case {case.name!r}")
    net = network.build(sc, resolved.thermal, prepared.geometry)
    environment_config = resolved.thermal.environment
    solar, albedo, infrared = env.fluxes(environment_config.solar_flux_w_m2, environment_config.albedo,
                                         environment_config.planet_ir_w_m2, environment_config.albedo_model)
    loads = solver.loads(net, env.time_s, solar, albedo, infrared)
    config = resolved.thermal.solver
    solution = solver.solve(net, loads, config, env.period_s, step_check=step_check)
    sized = {}
    if size_heaters:
        for heater in net.heaters:
            sized[heater.name] = solver.size_heater(net, loads, config, env.period_s, heater.name)
    notes = list(resolved.notes)
    if net.unassigned:
        notes.append(f"faces in no node, left out: {', '.join(net.unassigned[:8])}")
    return results.summarise(case.name, notes, net, loads, solution, env.period_s, sc.name, sized)


def analyse(scenario, result, sc_name: str, base_dir=None, case_names: list[str] | None = None,
            size_heaters: bool = True, step_check: bool = True,
            progress: Callable[[str], None] | None = None) -> ThermalAnalysis:
    """Solve every case of ``sc_name`` (its section's cases, or nominal,
    hot and cold; ``case_names`` picks some)."""
    prepared = prepare(scenario, result, sc_name, base_dir)
    chosen = cases_module.cases_of(prepared.spacecraft.thermal)
    if case_names:
        unknown = [n for n in case_names if n not in {c.name for c in chosen}]
        if unknown:
            raise ThermalAnalysisError(f"{sc_name}: no case named {', '.join(unknown)} "
                                       f"(cases: {', '.join(c.name for c in chosen)})")
        chosen = [c for c in chosen if c.name in case_names]
    solved = []
    for case in chosen:
        if progress is not None:
            progress(f"solving the {case.name} case")
        try:
            solved.append(solve_case(prepared, case, size_heaters, step_check))
        except (network.ThermalModelError, cases_module.CaseError, solver.ThermalSolveError, ValueError) as exc:
            raise ThermalAnalysisError(f"{sc_name}: case {case.name!r}: {exc}") from exc
    return ThermalAnalysis(prepared, solved)
