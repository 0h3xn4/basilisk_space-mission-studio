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
"""Parametric sweeps, one-at-a-time sensitivity and the thermal Monte
Carlo (thermal Phase 2, T-36). Each solves a case of a prepared analysis
(``thermal.analysis.prepare``: the run's fluxes on every face, computed
once) with parameters overridden by path, as a case's own overrides are
(T-13): nothing is rerun in Basilisk.

- :func:`sweep`: the case at each value of one parameter.
- :func:`sensitivity`: each parameter moved by a step up and down from its
  value, the change of every node's extremes per step and per unit; ranked
  by the largest change.
- :func:`monte_carlo`: runs drawn from the dispersions (a seeded
  generator: the same seed, the same draws), each solved; the batch saved
  as a Monte Carlo summary of kind ``thermal`` that the Monte Carlo view
  opens (``engine.monte_carlo_results``).
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from ..schema import thermal as thermal_schema
from ..schema.scenario import resolve_value_path
from . import analysis, cases, library, results

_OPTICS = ("absorptance", "emissivity")


class SweepError(ValueError):
    """A parameter that cannot be swept, varied or drawn, saying why."""


def current_value(thermal, path: str, spacecraft=None) -> float:
    """The value of ``path`` in ``thermal`` (a case's section): the number
    set there, or, for a face's optics set through a coating, the coating's
    library value. Raises :class:`SweepError` for a path that has none."""
    try:
        record, name = resolve_value_path(thermal, path)
    except ValueError as exc:
        raise SweepError(f"{path}: {exc}") from exc
    value = getattr(record, name, None)
    if value is None and name in _OPTICS and getattr(record, "coating", ""):
        materials = list(getattr(getattr(spacecraft, "model", None), "materials", []) or [])
        found = (library.absorptance if name == "absorptance" else library.emissivity)(record.coating, materials)
        value = None if found is None else found.value
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SweepError(f"{path}: no number to vary (give the value in the thermal model)")
    return float(value)


def _case_with(case: thermal_schema.ThermalCaseConfig, overrides: dict) -> thermal_schema.ThermalCaseConfig:
    changed = copy.deepcopy(case)
    changed.overrides = {**case.overrides, **overrides}
    return changed


def _solve(prepared, case, overrides, **options) -> results.CaseResult:
    return analysis.solve_case(prepared, _case_with(case, overrides), size_heaters=False, step_check=False,
                               **options)


def _resolved(prepared, case) -> object:
    env = prepared.environment
    return cases.resolve(prepared.spacecraft.thermal, case, env.central_body, env.band, prepared.mean_beta_deg,
                         prepared.context, prepared.spacecraft.name).thermal


@dataclass
class SweepPoint:
    value: float
    summary: list  # results.NodeSummary per node


def sweep(prepared, case: thermal_schema.ThermalCaseConfig, path: str, values: list[float],
          progress: Callable[[str], None] | None = None) -> list[SweepPoint]:
    """``case`` solved with ``path`` at each of ``values``."""
    if not values:
        raise SweepError("give at least one value to sweep")
    current_value(_resolved(prepared, case), path, prepared.spacecraft)  # refuse a bad path before solving
    points = []
    for index, value in enumerate(values):
        if progress is not None:
            progress(f"{path} = {value:g} ({index + 1} of {len(values)})")
        points.append(SweepPoint(float(value), _solve(prepared, case, {path: float(value)}).summary))
    return points


@dataclass
class Sensitivity:
    """One parameter's effect: ``changes[node] = (d min, d max, d mean)``
    [K] between the step up and the step down (a central difference over
    ``2 step``)."""

    path: str
    value: float
    step: float
    changes: dict

    @property
    def largest_k(self) -> float:
        return max((abs(v) for row in self.changes.values() for v in row), default=0.0)

    def per_unit(self, node: str) -> tuple:
        """``d(min, max, mean) / d(parameter)`` [K per unit]."""
        return tuple(v / (2.0 * self.step) for v in self.changes[node])


def default_parameters(thermal) -> list[str]:
    """The parameters a sensitivity varies by default: every face entry's
    optics, conductor and heat pipe conductance, dissipation and heater
    power, and the environment's sunlight and infrared."""
    paths = []
    for entry in thermal.faces:
        paths += [f"faces[{entry.name}].{name}" for name in _OPTICS]
    paths += [f"conductors[{c.name}].conductance_w_k" for c in thermal.conductors if c.kind == "value"]
    paths += [f"conductors[{c.name}].contact_coefficient_w_m2_k" for c in thermal.conductors if c.kind == "contact"]
    paths += [f"heat_pipes[{p.name}].conductance_w_k" for p in thermal.heat_pipes]
    paths += [f"dissipations[{d.name}].power_w" for d in thermal.dissipations if d.power_w is not None]
    paths += [f"heaters[{h.name}].power_w" for h in thermal.heaters]
    paths += ["environment.solar_flux_w_m2", "environment.planet_ir_w_m2"]
    return paths


def sensitivity(prepared, case: thermal_schema.ThermalCaseConfig, paths: list[str] | None = None,
                relative: float = 0.1, progress: Callable[[str], None] | None = None) -> tuple[list, list]:
    """Each of ``paths`` (default :func:`default_parameters`) moved up and
    down by ``relative`` of its value (optics kept within [0, 1]), the rest
    at the case's values. Returns ``(rows ranked by their largest change,
    notes on parameters left out)``."""
    resolved = _resolved(prepared, case)
    paths = paths if paths is not None else default_parameters(resolved)
    rows, notes = [], []
    for index, path in enumerate(paths):
        try:
            value = current_value(resolved, path, prepared.spacecraft)
        except SweepError as exc:
            notes.append(str(exc))
            continue
        if value == 0.0:
            notes.append(f"{path}: zero, no relative step")
            continue
        step = abs(value) * relative
        up, down = value + step, value - step
        if path.rsplit(".", 1)[-1] in _OPTICS:
            up, down = min(up, 1.0), max(down, 0.0)
            step = 0.5 * (up - down)
        if progress is not None:
            progress(f"varying {path} ({index + 1} of {len(paths)})")
        high = {n.name: n for n in _solve(prepared, case, {path: up}).summary}
        low = {n.name: n for n in _solve(prepared, case, {path: down}).summary}
        changes = {name: (high[name].min_c - low[name].min_c, high[name].max_c - low[name].max_c,
                          high[name].mean_c - low[name].mean_c) for name in high}
        rows.append(Sensitivity(path, value, step, changes))
    rows.sort(key=lambda row: -row.largest_k)
    return rows, notes


def _draw(rng: np.random.Generator, dispersion, base: float) -> float:
    scale = dispersion.sigma * (abs(base) if dispersion.relative else 1.0)
    offset = rng.normal(0.0, scale) if dispersion.distribution == "normal" else rng.uniform(-scale, scale)
    value = base + offset
    name = dispersion.path.rsplit(".", 1)[-1]
    if name in _OPTICS:
        return float(min(max(value, 0.0), 1.0))
    return float(max(value, 0.0)) if base >= 0.0 else float(value)


def monte_carlo(prepared, config: thermal_schema.ThermalMonteCarloConfig,
                progress: Callable[[str], None] | None = None):
    """The thermal Monte Carlo of ``config`` on ``prepared``: an
    ``engine.monte_carlo_results.MonteCarloBatch`` of kind ``thermal``
    (each run's node temperatures and drawn values). Draws are clipped to
    a parameter's valid range (optics to [0, 1], the rest to 0 and up)."""
    from ..engine import monte_carlo_results as mcr

    case = next((c for c in cases.cases_of(prepared.spacecraft.thermal) if c.name == config.case), None)
    if case is None:
        raise SweepError(f"no case named {config.case!r}")
    resolved = _resolved(prepared, case)
    bases = {d.path: current_value(resolved, d.path, prepared.spacecraft) for d in config.dispersions}
    rng = np.random.default_rng(config.seed)
    draws = [{d.path: _draw(rng, d, bases[d.path]) for d in config.dispersions} for _run in range(config.runs)]
    temperatures, drawn, done, failed = {}, [], [], []
    time_s = None
    for run, values in enumerate(draws):
        if progress is not None:
            progress(f"run {run + 1} of {config.runs}")
        try:
            solved = _solve(prepared, case, values)
        except (ValueError, cases.CaseError) as exc:  # a draw the model refuses: counted as failed
            failed.append(run)
            del exc
            continue
        if time_s is None:
            time_s = solved.time_s
            temperatures = {name: [] for name in solved.network.names}
        for name in solved.network.names:
            temperatures[name].append(np.interp(time_s, solved.time_s, solved.temperature_c(name)))
        drawn.append(dict(values))
        done.append(run)
    if not done:
        raise SweepError("every run failed: the dispersions draw values the model refuses")
    return mcr.MonteCarloBatch(
        f"{prepared.scenario.name}: {prepared.spacecraft.name} thermal, case {case.name}",
        prepared.environment.central_body, np.asarray(time_s), done, failed, {}, {}, drawn,
        getattr(prepared.scenario, "epoch_utc", "") or "", kind="thermal",
        temperatures_c={name: np.array(rows) for name, rows in temperatures.items()}, case=case.name)
