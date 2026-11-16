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
"""What a thermal solve gives (design 2.10): temperatures per node on
the solver's times, the heat flows into each node by kind (solar,
albedo, planetary infrared, emitted, each conductor, heat pipe and
radiative link, dissipation, heater) as series and as orbit averages,
the summary per node against its limits, the radiators' heat, the
heaters' duty, energy and sized power, the limit violations as
Timeline events, and the result as named series for plots and CSV.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..engine.events import THERMAL_LIMIT, Event, intervals
from ..engine.findings import Finding
from ..engine.results import TimeSeries
from .network import ZERO_C_K, Network
from .solver import SIGMA, Loads, Solution, _heater_power

FLOW_KINDS = ("solar", "albedo", "infrared", "emitted", "conduction", "heat pipes", "radiation", "dissipation",
              "heater")
_STEP_LIMIT_K = 0.5  # [K] the step check's rule (thermal.step)


@dataclass
class NodeSummary:
    name: str
    min_c: float  # [degC]
    max_c: float  # [degC]
    mean_c: float  # [degC]
    operating_c: tuple | None
    survival_c: tuple | None

    @property
    def cold_margin_k(self) -> float | None:
        """Lowest temperature less the operating minimum [K] (negative: below)."""
        return None if self.operating_c is None else self.min_c - self.operating_c[0]

    @property
    def hot_margin_k(self) -> float | None:
        """Operating maximum less the highest temperature [K] (negative: above)."""
        return None if self.operating_c is None else self.operating_c[1] - self.max_c


@dataclass
class HeaterReport:
    name: str
    node: str
    power_w: float  # [W] as set
    duty: float  # [-] fraction of the window it is on
    energy_wh: float  # [W*h] over the window
    orbit_average_w: float  # [W]
    sized_w: float | None = None  # [W] the least constant power that holds the setpoint (T-12)


@dataclass
class RadiatorReport:
    node: str
    area_m2: float  # [m^2]
    emitted_w: float  # [W] orbit average
    absorbed_w: float  # [W] orbit average
    rejected_w: float  # [W] orbit average, emitted less absorbed


@dataclass
class CaseResult:
    """One case's solve and what is read from it."""

    name: str
    notes: list[str]
    network: Network
    loads: Loads
    solution: Solution
    flows: dict  # node -> {flow name: (k,) [W]}
    orbit_average: dict  # node -> {flow name: [W]}
    summary: list[NodeSummary]
    heaters: list[HeaterReport]
    radiators: list[RadiatorReport]
    events: list[Event]
    findings: list[str] = field(default_factory=list)

    @property
    def time_s(self) -> np.ndarray:
        return self.solution.time_s

    def temperature_c(self, node: str) -> np.ndarray:
        return self.solution.temperature_c[:, self.network.index(node)]

    def series(self, prefix: str) -> list[TimeSeries]:
        """Named series of this case: ``<prefix>.<case>.temperature`` (a
        column per node, degC) and ``<prefix>.<case>.<node>.heat_flow`` (a
        column per flow, W)."""
        names = self.network.names
        out = [TimeSeries(f"{prefix}.{self.name}.temperature", self.time_s, tuple(names),
                          self.solution.temperature_c, units="degC")]
        for node in names:
            flows = self.flows[node]
            out.append(TimeSeries(f"{prefix}.{self.name}.{node}.heat_flow", self.time_s, tuple(flows),
                                  np.column_stack(list(flows.values())), units="W"))
        heaters = self.solution.integration.heater_on
        if heaters.size:
            out.append(TimeSeries(f"{prefix}.{self.name}.heaters", self.time_s,
                                  tuple(h.name for h in self.network.heaters), heaters.astype(float), units="on"))
        return out


def flows(network: Network, loads_: Loads, solution: Solution) -> dict:
    """``{node: {flow: (k,) W}}``: heat into each node by kind (module
    docstring), positive in; ``conduction`` etc. also per item, as
    ``conductor <name>``."""
    run = solution.integration
    t = run.temperature_k
    absorbed = {kind: loads_.at(run.time_s, kind) for kind in ("solar", "albedo", "infrared")}
    out = {}
    m = len(network.names)
    heater_w = np.array([_heater_power(network, on, None) for on in run.heater_on]).reshape(len(t), m)
    pipe_k = np.zeros((len(t), m))
    pipe_items: dict[str, np.ndarray] = {}
    for k_index, pipe in enumerate(network.heat_pipes):
        g = np.array([pipe.on_w_k if on[k_index] else pipe.off_w_k for on in run.pipe_on]) \
            if run.pipe_on.size else np.full(len(t), pipe.off_w_k)
        flow = g * (t[:, pipe.j] - t[:, pipe.i])
        pipe_k[:, pipe.i] += flow
        pipe_k[:, pipe.j] -= flow
        pipe_items[pipe.name] = flow
    for i, node in enumerate(network.names):
        node_flows = {"solar": absorbed["solar"][:, i], "albedo": absorbed["albedo"][:, i],
                      "infrared": absorbed["infrared"][:, i],
                      "emitted": -loads_.emission_w_k4[i] * t[:, i] ** 4}
        conduction = np.zeros(len(t))
        for link in network.conductors:
            if i in (link.i, link.j):
                g = np.array([network.conductance_matrix(row)[link.i, link.j] for row in t]) \
                    if network.conductance_tables else link.value
                other = link.j if i == link.i else link.i
                flow = g * (t[:, other] - t[:, i])
                node_flows[f"conductor {link.name}"] = flow
                conduction += flow
        node_flows["conduction"] = conduction
        node_flows["heat pipes"] = pipe_k[:, i]
        for pipe in network.heat_pipes:
            if i in (pipe.i, pipe.j):
                node_flows[f"heat pipe {pipe.name}"] = pipe_items[pipe.name] * (1.0 if i == pipe.i else -1.0)
        radiation = np.zeros(len(t))
        for link in network.links:
            if i in (link.i, link.j):
                other = link.j if i == link.i else link.i
                flow = SIGMA * link.value * (t[:, other] ** 4 - t[:, i] ** 4)
                node_flows[f"link {link.name}"] = flow
                radiation += flow
        node_flows["radiation"] = radiation
        node_flows["dissipation"] = np.full(len(t), network.dissipation_w[i])
        node_flows["heater"] = heater_w[:, i]
        out[node] = node_flows
    return out


def orbit_window(time_s: np.ndarray, period_s: float) -> slice:
    """The last full orbit of ``time_s`` (all of it when shorter)."""
    if not np.isfinite(period_s) or time_s[-1] - time_s[0] <= period_s:
        return slice(0, len(time_s))
    start = int(np.searchsorted(time_s, time_s[-1] - period_s))
    return slice(start, len(time_s))


def _average(series: np.ndarray, time_s: np.ndarray, window: slice) -> float:
    t, y = time_s[window], series[window]
    if len(t) < 2:
        return float(y.mean()) if len(y) else 0.0
    return float(np.trapezoid(y, t) / (t[-1] - t[0]))


def summarise(name: str, notes: list[str], network: Network, loads_: Loads, solution: Solution,
              period_s: float, spacecraft: str, sized: dict | None = None) -> CaseResult:
    """The :class:`CaseResult` of a solve (module docstring)."""
    node_flows = flows(network, loads_, solution)
    window = orbit_window(solution.time_s, period_s)
    averages = {node: {kind: _average(values, solution.time_s, window) for kind, values in f.items()}
                for node, f in node_flows.items()}
    temp_c = solution.temperature_c
    summary = []
    for i, node in enumerate(network.names):
        op = network.operating_k[i]
        sv = network.survival_k[i]
        summary.append(NodeSummary(node, float(temp_c[:, i].min()), float(temp_c[:, i].max()),
                                   float(temp_c[:, i].mean()),
                                   None if op is None else (op[0] - ZERO_C_K, op[1] - ZERO_C_K),
                                   None if sv is None else (sv[0] - ZERO_C_K, sv[1] - ZERO_C_K)))
    run = solution.integration
    dt = np.diff(run.time_s)
    heaters = []
    for k, heater in enumerate(network.heaters):
        on = run.heater_on[1:, k] if len(run.heater_on) > 1 else np.zeros(0, bool)
        energy = float(np.sum(dt * on) * heater.power_w) / 3600.0
        span = float(run.time_s[-1] - run.time_s[0]) or 1.0
        heaters.append(HeaterReport(heater.name, network.names[heater.node], heater.power_w,
                                    float(np.sum(dt * on) / span), energy,
                                    _average(run.heater_on[:, k].astype(float) * heater.power_w, run.time_s, window),
                                    (sized or {}).get(heater.name)))
    radiators = []
    for node_index, node in enumerate(network.names):
        faces = [f for f in network.facets if f.radiator and f.node == node_index]
        if not faces:
            continue
        area = sum(f.area_m2 for f in faces)
        e_rad = sum(f.emissivity * SIGMA * f.area_m2 for f in faces)
        emitted = _average(e_rad * run.temperature_k[:, node_index] ** 4, run.time_s, window)
        share = e_rad / loads_.emission_w_k4[node_index] if loads_.emission_w_k4[node_index] > 0 else 0.0
        visible_share = sum(f.absorptance * f.area_m2 for f in faces) / max(
            sum(g.absorptance * g.area_m2 for g in network.facets if g.node == node_index), 1.0e-12)
        absorbed = (visible_share * (averages[node]["solar"] + averages[node]["albedo"])
                    + share * averages[node]["infrared"])
        radiators.append(RadiatorReport(node, area, emitted, absorbed, emitted - absorbed))
    events, findings = limit_events(network, solution, spacecraft, name)
    if solution.periodic is not None and not solution.periodic.converged:
        findings.append(Finding(f"{spacecraft}: thermal {name}: the orbit-periodic start did not converge "
                                f"({solution.periodic.residual_k:.3g} K over the last orbit)", "thermal.not_converged",
                                actual=f"{solution.periodic.residual_k:.3g} K"))
    if solution.step_check_k is not None and solution.step_check_k > _STEP_LIMIT_K:
        findings.append(Finding(f"{spacecraft}: thermal {name}: halving the time step changes temperatures by "
                                f"{solution.step_check_k:.2f} K", "thermal.step",
                                actual=f"{solution.step_check_k:.2f} K", limit=f"{_STEP_LIMIT_K} K"))
    return CaseResult(name, notes, network, loads_, solution, node_flows, averages, summary, heaters, radiators,
                      events, findings + list(solution.warnings))


def limit_events(network: Network, solution: Solution, spacecraft: str, case: str) -> tuple[list[Event], list]:
    """The spans each node is outside its operating range (and survival
    range), as Timeline events of kind ``thermal limit``, and a finding
    per node that leaves its range."""
    events, findings = [], []
    t = solution.time_s
    temp_c = solution.temperature_c
    for i, node in enumerate(network.names):
        for label, limits in (("operating", network.operating_k[i]), ("survival", network.survival_k[i])):
            if limits is None:
                continue
            low, high = limits[0] - ZERO_C_K, limits[1] - ZERO_C_K
            for side, mask in (("below", temp_c[:, i] < low), ("above", temp_c[:, i] > high)):
                spans = intervals(t, mask)
                for first, last in spans:
                    extreme = float(temp_c[first:last + 1, i].min() if side == "below"
                                    else temp_c[first:last + 1, i].max())
                    events.append(Event(THERMAL_LIMIT, spacecraft, float(t[first]), float(t[last]),
                                        f"{node} {side} {label}", detail=f"{case}: {node} {side} its {label} range "
                                        f"[{low:g}, {high:g}] degC", other="",
                                        quantities=(("temperature", extreme),), note=case))
                if spans:
                    worst = float(temp_c[:, i][mask].min() if side == "below" else temp_c[:, i][mask].max())
                    findings.append(Finding(f"{spacecraft}: thermal {case}: {node} goes {side} its {label} range "
                                            f"[{low:g}, {high:g}] degC, to {worst:.1f} degC", "thermal.limit",
                                            actual=f"{worst:.1f} degC",
                                            limit=f"{low:g} degC" if side == "below" else f"{high:g} degC"))
    return events, findings
