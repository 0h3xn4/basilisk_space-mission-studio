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
"""The nodal network solved in time (design 2.7):

``C_i dT_i/dt = Q_abs,i(t) - E_i T_i^4 + sum_j G_ij (T_j - T_i)
+ sum_j sigma eA_ij (T_j^4 - T_i^4) + Q_diss,i + Q_heater,i``

with ``Q_abs`` the absorbed solar, albedo and planetary infrared of the
node's facets and ``E_i = sum eps sigma A`` over them.

- BDF2 (second-order backward differentiation, variable step, the first
  step backward Euler) with Newton's method on the whole network
  (decision T-07): A-stable, so stable for any step with the stiff
  ``T^4``, heat-pipe and heater terms, and second-order accurate. The
  step is the solver's, not the run's recording interval: absorbed loads
  are interpolated linearly in time.
- Heat pipes and heaters switch on the temperatures at the start of a
  step (T-08, T-12).
- The orbit-periodic start (``periodic``): from the steady state on
  orbit-averaged loads, the run's first orbit is repeated until no node
  changes by more than the tolerance over an orbit; the run is then
  solved from there.
- Every solve closes an energy balance (the heat stored against the
  trapezoidal integral of the net heat in); the step check solves again
  with half the step and reports the largest difference.

Temperatures are kelvin inside, degC at the edges. Numpy only.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .network import ZERO_C_K, Network

SIGMA = 5.670374419e-8  # [W/(m^2*K^4)] Stefan-Boltzmann, CODATA 2018
_NEWTON_TOLERANCE_K = 1.0e-7  # [K]
_NEWTON_ITERATIONS = 200
_STEADY_GUESS_K = 293.15  # [K]
_FLOOR_K = 3.0  # [K] a node with no heat at all settles here (the solver's floor, not physics)


class ThermalSolveError(RuntimeError):
    """The solver did not converge, saying where."""


@dataclass
class Loads:
    """Absorbed environmental heat per node [W] on the run's times."""

    time_s: np.ndarray  # (n,)
    solar_w: np.ndarray  # (n, m)
    albedo_w: np.ndarray  # (n, m)
    infrared_w: np.ndarray  # (n, m)
    emission_w_k4: np.ndarray  # (m,) E_i = sum eps sigma A
    breaks_s: np.ndarray = field(default_factory=lambda: np.zeros(0))  # [s] where the loads jump (eclipse)

    def total(self) -> np.ndarray:
        return self.solar_w + self.albedo_w + self.infrared_w

    def at(self, t: np.ndarray, which: str = "total") -> np.ndarray:
        """Loads interpolated linearly at times ``t`` (k,) -> (k, m)."""
        values = self.total() if which == "total" else getattr(self, f"{which}_w")
        return np.column_stack([np.interp(t, self.time_s, values[:, i]) for i in range(values.shape[1])])


def loads(network: Network, time_s: np.ndarray, solar: np.ndarray, albedo: np.ndarray,
          infrared: np.ndarray) -> Loads:
    """The :class:`Loads` of ``network`` from incident fluxes per facet
    (n, f) [W/m^2] (``Environment.fluxes``)."""
    m = len(network.names)
    w_vis = np.zeros((solar.shape[1], m))
    w_ir = np.zeros((solar.shape[1], m))
    emission = np.zeros(m)
    for facet in network.facets:
        w_vis[facet.facet, facet.node] += facet.absorptance * facet.area_m2
        w_ir[facet.facet, facet.node] += facet.emissivity * facet.area_m2
        emission[facet.node] += facet.emissivity * SIGMA * facet.area_m2
    absorbed = solar @ w_vis
    total = absorbed.sum(axis=1)
    # Times around a jump of the loads (eclipse entry and exit between two recorded samples): the solver
    # steps on them, so the loads are linear within every step and the integration keeps its order.
    jump = np.abs(np.diff(total)) > 0.05 * max(float(np.abs(total).max()), 1.0e-12)
    breaks = np.unique(np.concatenate([np.asarray(time_s, float)[:-1][jump], np.asarray(time_s, float)[1:][jump]]))
    return Loads(np.asarray(time_s, float), absorbed, albedo @ w_vis, infrared @ w_ir, emission, breaks)


@dataclass
class Integration:
    """One integration: temperatures [K] at the solver's times, the heaters'
    and heat pipes' states (on during the step ending there)."""

    time_s: np.ndarray  # (k,)
    temperature_k: np.ndarray  # (k, m)
    heater_on: np.ndarray  # (k, h) bool
    pipe_on: np.ndarray  # (k, p) bool


def grid(start_s: float, end_s: float, step_s: float, breaks_s: np.ndarray | None = None) -> np.ndarray:
    """Times from ``start_s`` to ``end_s`` by ``step_s``, the last step
    shortened to end exactly at ``end_s``, with ``breaks_s`` (where the
    loads jump) added and any step shorter than a tenth of ``step_s`` that
    they make merged away."""
    count = max(int(np.ceil((end_s - start_s) / step_s - 1.0e-9)), 1)
    times = start_s + step_s * np.arange(count + 1)
    times[-1] = end_s
    if breaks_s is None or not len(breaks_s):
        return times
    inside = breaks_s[(breaks_s > start_s) & (breaks_s < end_s)]
    merged = np.unique(np.concatenate([times, inside]))
    keep = [merged[0]]
    for t in merged[1:-1]:
        if t - keep[-1] >= 0.1 * step_s or t in inside:
            if keep[-1] not in inside and t in inside and t - keep[-1] < 0.1 * step_s and len(keep) > 1:
                keep[-1] = t
            else:
                keep.append(t)
    if merged[-1] - keep[-1] < 0.1 * step_s and len(keep) > 1 and keep[-1] not in inside:
        keep[-1] = merged[-1]
    else:
        keep.append(merged[-1])
    return np.asarray(keep)


def _pipe_matrix(network: Network, temperature: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    m = len(network.names)
    k = np.zeros((m, m))
    on = np.zeros(len(network.heat_pipes), dtype=bool)
    for index, pipe in enumerate(network.heat_pipes):
        hot = max(temperature[pipe.i], temperature[pipe.j])
        on[index] = pipe.low_k <= hot <= pipe.high_k
        g = pipe.on_w_k if on[index] else pipe.off_w_k
        k[pipe.i, pipe.i] -= g
        k[pipe.j, pipe.j] -= g
        k[pipe.i, pipe.j] += g
        k[pipe.j, pipe.i] += g
    return k, on


def _radiation(network: Network, t: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Net radiative-link heat into each node [W] and its Jacobian."""
    m = len(network.names)
    q = np.zeros(m)
    jac = np.zeros((m, m))
    for link in network.links:
        c = SIGMA * link.value
        flow = c * (t[link.j] ** 4 - t[link.i] ** 4)
        q[link.i] += flow
        q[link.j] -= flow
        di, dj = 4.0 * c * t[link.i] ** 3, 4.0 * c * t[link.j] ** 3
        jac[link.i, link.i] -= di
        jac[link.i, link.j] += dj
        jac[link.j, link.j] -= dj
        jac[link.j, link.i] += di
    return q, jac


def _heater_power(network: Network, on: np.ndarray, fixed: dict | None) -> np.ndarray:
    power = np.zeros(len(network.names))
    for index, heater in enumerate(network.heaters):
        if fixed is not None and heater.name in fixed:
            power[heater.node] += fixed[heater.name]
        elif on[index]:
            power[heater.node] += heater.power_w
    return power


def _newton(network: Network, base: np.ndarray, guess: np.ndarray, source: np.ndarray, k_matrix: np.ndarray,
            c_over_dt: np.ndarray, emission: np.ndarray, where: str) -> np.ndarray:
    """Solve ``c_over_dt (T - base) = source - E T^4 + K T + R(T)`` from
    ``guess`` (with ``c_over_dt`` zero: the steady state)."""
    t = guess.copy()
    diagonal = np.diag_indices(len(t))
    links = bool(network.links)
    for _ in range(_NEWTON_ITERATIONS):
        t3 = t * t * t
        residual = c_over_dt * (t - base) - (source - emission * t3 * t + k_matrix @ t)
        jac = -k_matrix
        jac[diagonal] += c_over_dt + 4.0 * emission * t3
        if links:
            rad, rad_jac = _radiation(network, t)
            residual -= rad
            jac -= rad_jac
        try:
            delta = np.linalg.solve(jac, -residual)
        except np.linalg.LinAlgError as exc:
            raise ThermalSolveError(f"{where}: the network is singular (a node with no capacitance and no path?)") \
                from exc
        limit = float(np.abs(delta).max())
        if limit > 50.0:
            delta *= 50.0 / limit  # [K] damping far from the solution
            limit = 50.0
        t = np.maximum(t + delta, _FLOOR_K)
        if limit < _NEWTON_TOLERANCE_K or np.all((t <= _FLOOR_K) | (np.abs(delta) < 1e-7)):
            return t
    raise ThermalSolveError(f"{where}: Newton did not converge in {_NEWTON_ITERATIONS} iterations")


def integrate(network: Network, loads_: Loads, times: np.ndarray, start_k: np.ndarray,
              heaters_on: np.ndarray | None = None, fixed_heaters: dict | None = None,
              before: tuple[np.ndarray, float] | None = None) -> Integration:
    """BDF2 over ``times`` from ``start_k`` (module docstring).
    ``fixed_heaters`` maps a heater's name to a constant power (sizing).
    ``before`` is ``(temperatures, step)`` one step before the start, so a
    continued integration keeps second order from its first step."""
    m = len(network.names)
    absorbed = loads_.at(times)
    temperature = np.empty((len(times), m))
    temperature[0] = start_k
    on = np.zeros(len(network.heaters), dtype=bool) if heaters_on is None else heaters_on.copy()
    heater_history = np.zeros((len(times), len(network.heaters)), dtype=bool)
    pipe_history = np.zeros((len(times), len(network.heat_pipes)), dtype=bool)
    for index, heater in enumerate(network.heaters):
        on[index] = on[index] if start_k[heater.node] >= heater.on_k else True
    heater_history[0] = on
    k_fixed = None if network.conductance_tables else network.conductance_matrix()
    for step in range(1, len(times)):
        previous = temperature[step - 1]
        for index, heater in enumerate(network.heaters):
            if previous[heater.node] < heater.on_k:
                on[index] = True
            elif previous[heater.node] > heater.off_k:
                on[index] = False
        k_pipes, pipes_on = _pipe_matrix(network, previous)
        k_cond = k_fixed if k_fixed is not None else network.conductance_matrix(previous)
        dt = times[step] - times[step - 1]
        source = absorbed[step] + network.dissipation_w + _heater_power(network, on, fixed_heaters)
        if step == 1 and before is not None:  # BDF2 continued from an earlier integration
            w = dt / before[1]
            a0 = (1.0 + 2.0 * w) / (1.0 + w)
            base = ((1.0 + w) * previous - w * w / (1.0 + w) * before[0]) / a0
        elif step == 1:  # backward Euler
            a0, base = 1.0, previous
        else:  # variable-step BDF2
            w = dt / (times[step - 1] - times[step - 2])
            a0 = (1.0 + 2.0 * w) / (1.0 + w)
            base = ((1.0 + w) * previous - w * w / (1.0 + w) * temperature[step - 2]) / a0
        guess = previous if step == 1 else np.maximum(2.0 * previous - temperature[step - 2], _FLOOR_K)
        temperature[step] = _newton(network, base, guess, source, k_cond + k_pipes,
                                    a0 * network.capacitance_j_k / dt, loads_.emission_w_k4,
                                    f"step to t = {times[step]:.0f} s")
        heater_history[step] = on
        pipe_history[step] = pipes_on
    return Integration(times, temperature, heater_history, pipe_history)


def steady_state(network: Network, mean_loads_w: np.ndarray, emission: np.ndarray,
                 heater_power_w: np.ndarray | None = None) -> np.ndarray:
    """The steady state [K] on constant loads (heaters off unless given);
    heat pipes take the state of the solution (iterated)."""
    source = mean_loads_w + network.dissipation_w + (0.0 if heater_power_w is None else heater_power_w)
    radiating = emission > 0.0
    t = np.full(len(network.names), _STEADY_GUESS_K)
    if radiating.any():  # each radiating node alone in radiative balance with all the heat: a good start
        alone = (max(float(source.sum()), 1.0e-6) / emission[radiating].sum()) ** 0.25
        t[:] = max(alone, _FLOOR_K)
    k_cond = network.conductance_matrix(t)
    for _ in range(20):
        k_pipes, _on = _pipe_matrix(network, t)
        new = _newton(network, t, t, source, k_cond + k_pipes, np.zeros(len(t)), emission, "steady state")
        k_cond = network.conductance_matrix(new)
        if np.max(np.abs(new - t)) < 1.0e-6:
            return new
        t = new
    return t


@dataclass
class Periodic:
    """How the orbit-periodic start converged."""

    orbits: int
    residual_k: float  # [K] largest change of a node over the last orbit
    converged: bool
    period_s: float


@dataclass
class Solution:
    """A solve over the run window (design 2.7)."""

    integration: Integration
    start: str
    periodic: Periodic | None
    energy_residual_j: float  # [J]
    energy_throughput_j: float  # [J]
    step_check_k: float | None  # [K] largest difference with half the step
    warnings: list = field(default_factory=list)

    @property
    def time_s(self) -> np.ndarray:
        return self.integration.time_s

    @property
    def temperature_c(self) -> np.ndarray:
        return self.integration.temperature_k - ZERO_C_K


def _periodic_start(network: Network, loads_: Loads, start_s: float, period_s: float, step_s: float,
                    tolerance_k: float, max_orbits: int, fixed_heaters: dict | None, warm: tuple | None = None) -> tuple:
    """``(T, heaters on, before, Periodic)`` at the start of the converged
    orbit; ``warm`` is a previous solve's ``(T, on, before)`` to start from
    instead of the steady state (sizing, sweeps)."""
    orbit = grid(start_s, start_s + period_s, step_s, loads_.breaks_s)
    if warm is not None:
        t0, on, before = warm
    else:
        mean = loads_.at(orbit)[:-1].mean(axis=0)
        t0 = steady_state(network, mean, loads_.emission_w_k4)
        on, before = None, None
    residual = float("inf")
    for count in range(1, max_orbits + 1):
        run = integrate(network, loads_, orbit, t0, on, fixed_heaters, before)
        end = run.temperature_k[-1]
        residual = float(np.max(np.abs(end - t0)))
        t0, on = end, run.heater_on[-1]
        before = (run.temperature_k[-2], float(orbit[-1] - orbit[-2]))
        if residual < tolerance_k:
            return t0, on, before, Periodic(count, residual, True, period_s)
    return t0, on, before, Periodic(max_orbits, residual, False, period_s)


def energy_balance(network: Network, loads_: Loads, run: Integration,
                   fixed_heaters: dict | None = None) -> tuple[float, float]:
    """``(residual, throughput)`` [J]: the heat stored, ``sum C (T_end -
    T_start)``, minus the trapezoidal integral of the net heat in
    (absorbed, dissipated and heater heat less emission; internal
    exchanges cancel); throughput is all the heat that came in. Heater
    power is constant over each step, as the solver applies it."""
    stored = float(network.capacitance_j_k @ (run.temperature_k[-1] - run.temperature_k[0]))
    dt = np.diff(run.time_s)
    absorbed = loads_.at(run.time_s).sum(axis=1) + network.dissipation_w.sum()
    emitted = (loads_.emission_w_k4 * run.temperature_k ** 4).sum(axis=1)
    heaters = np.array([_heater_power(network, on, fixed_heaters).sum() for on in run.heater_on[1:]])
    smooth = absorbed - emitted
    net = float(np.sum(dt * 0.5 * (smooth[1:] + smooth[:-1])) + np.sum(dt * heaters))
    throughput = float(np.sum(dt * 0.5 * (absorbed[1:] + absorbed[:-1])) + np.sum(dt * heaters))
    return stored - net, throughput


def solve(network: Network, loads_: Loads, solver, period_s: float, start_s: float | None = None,
          end_s: float | None = None, step_check: bool = True, fixed_heaters: dict | None = None,
          warm: tuple | None = None) -> Solution:
    """Solve the network over the run window (``start_s`` to ``end_s``,
    the loads' span by default) with the ``ThermalSolverConfig``
    ``solver`` (module docstring)."""
    start_s = float(loads_.time_s[0]) if start_s is None else start_s
    end_s = float(loads_.time_s[-1]) if end_s is None else end_s
    warnings = []
    periodic = None
    on, before = None, None
    if solver.start == "fixed":
        guess = np.where(np.isnan(network.initial_k),
                         (solver.initial_c + ZERO_C_K) if solver.initial_c is not None else np.nan, network.initial_k)
        if np.isnan(guess).any():
            missing = [n for n, v in zip(network.names, guess, strict=True) if np.isnan(v)]
            raise ThermalSolveError(f"start 'fixed' needs an initial temperature for {', '.join(missing)}")
        t0 = guess
    elif solver.start == "steady" or not np.isfinite(period_s) or start_s + period_s > end_s + 1.0e-6:
        if solver.start == "periodic":
            warnings.append("the run is shorter than an orbit: started from the steady state on its average loads")
        window = grid(start_s, end_s, solver.time_step_s)
        t0 = steady_state(network, loads_.at(window).mean(axis=0), loads_.emission_w_k4)
    else:
        t0, on, before, periodic = _periodic_start(network, loads_, start_s, period_s, solver.time_step_s,
                                                   solver.tolerance_k, solver.max_orbits, fixed_heaters, warm)
        if not periodic.converged:
            warnings.append(f"the orbit-periodic start did not converge in {periodic.orbits} orbits "
                            f"(last change {periodic.residual_k:.3g} K); raise max_orbits")
    times = grid(start_s, end_s, solver.time_step_s, loads_.breaks_s)
    run = integrate(network, loads_, times, t0, on, fixed_heaters, before)
    residual, throughput = energy_balance(network, loads_, run, fixed_heaters)
    check = None
    if step_check:
        half_before = None if before is None else (before[0], before[1])
        half = integrate(network, loads_, grid(start_s, end_s, solver.time_step_s / 2.0, loads_.breaks_s), t0, on,
                         fixed_heaters,
                         half_before)
        check = float(np.max(np.abs(np.interp(times, half.time_s, half.temperature_k[:, 0]) - run.temperature_k[:, 0])))
        for i in range(1, len(network.names)):
            diff = np.abs(np.interp(times, half.time_s, half.temperature_k[:, i]) - run.temperature_k[:, i])
            check = max(check, float(diff.max()))
    return Solution(run, solver.start, periodic, residual, throughput, check, warnings)


def size_heater(network: Network, loads_: Loads, solver, period_s: float, heater_name: str,
                resolution_w: float = 0.1, start_s: float | None = None) -> float:
    """The least constant power [W] of heater ``heater_name`` that keeps
    its node at or above its ``on`` setpoint over the orbit-periodic
    solution (decision T-12), found by bisection to ``resolution_w``."""
    heater = next(h for h in network.heaters if h.name == heater_name)
    start_s = float(loads_.time_s[0]) if start_s is None else start_s
    span = period_s if np.isfinite(period_s) else float(loads_.time_s[-1] - start_s)

    state: dict = {}

    def margin(power: float) -> float:
        """The node's coldest temperature less its setpoint [K] with the
        heater at ``power``, warm-started from the previous evaluation."""
        sol = solve(network, loads_, solver, span, start_s, start_s + span, step_check=False,
                    fixed_heaters={heater_name: power}, warm=state.get("warm"))
        run = sol.integration
        state["warm"] = (run.temperature_k[-1], run.heater_on[-1], (run.temperature_k[-2],
                                                                     float(run.time_s[-1] - run.time_s[-2])))
        return float(run.temperature_k[:, heater.node].min()) - heater.on_k

    low, f_low = 0.0, margin(0.0)
    if f_low >= 0.0:
        return 0.0
    high = max(heater.power_w, 1.0)
    f_high = margin(high)
    while f_high < 0.0:
        low, f_low = high, f_high
        high *= 2.0
        if high > 1.0e5:
            raise ThermalSolveError(f"heater {heater_name!r}: no power up to 100 kW holds its node at its setpoint")
        f_high = margin(high)
    side = 0
    while high - low > resolution_w:  # Illinois (regula falsi): the margin grows smoothly with the power
        mid = high - f_high * (high - low) / (f_high - f_low)
        mid = min(max(mid, low + 0.25 * resolution_w), high - 0.25 * resolution_w)
        f_mid = margin(mid)
        if f_mid >= 0.0:
            high, f_high = mid, f_mid
            if side == 1:
                f_low *= 0.5
            side = 1
        else:
            low, f_low = mid, f_mid
            if side == -1:
                f_high *= 0.5
            side = -1
        if abs(f_mid) < 1.0e-3 and f_mid >= 0.0:  # [K] within a millikelvin above the setpoint
            break
    return high
