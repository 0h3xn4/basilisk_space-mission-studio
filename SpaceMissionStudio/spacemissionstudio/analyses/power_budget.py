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
"""The static power budget of a spacecraft per system mode, with margins
and losses, from its ``budgets`` section (``schema.budgets``;
``docs/developer/system-budget-phase1-design.md``, section 4).

It is System Budget Studio's static budget (its decision D-040), with the
same arithmetic, re-implemented here:

=================  ==========================================================
Effective power    ``average_w * duty_cycle`` of the item's power mode
Unit margin        ``effective * (1 + percent / 100)``, the percent of the
                   item's maturity (decision B-07: margins in percent)
Subsystem          sums of effective, margined and peak per functional
                   subsystem (no system margin at this level)
Bus load           sums per bus; the system margin on the margined sum
Source power       ``load / (eta_bus * (1 - distribution_loss))``, of the
                   nominal load and of the system-margined load
Peak               every item at its peak at once (the duty cycle does not
                   lower it), its unit margin, the same chain
Spacecraft         the sum of the buses
=================  ==========================================================

A placeholder or a missing number makes every result that needs it None
("unknown"); it is never replaced by zero. The nominal chain needs no
margin, so a missing margin still gives the load and the nominal source
power. An item that a system mode does not list has an unknown power in
that mode (decision B-09); an item with no power mode is in the mass
budget only (B-16). Modes, rows, subsystems and buses keep the file's
order (B-10). No run uses the budget yet (B-14).
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, field

from ..engine.findings import Finding

#: Duty cycles that add up to 1 within this give a time-weighted average
#: (as ``idm.power.duty_cycle_average``).
DUTY_SUM_TOLERANCE = 1.0e-6  # [-]


# -- the scalar steps (pure) -------------------------------------------------------------------------------------

def effective_power_w(average_w: float | None, duty_cycle: float) -> float | None:
    """The item's mean power in the mode: its average while on times the
    share of the time it is on [W]; None when the average is unknown."""
    return None if average_w is None else average_w * duty_cycle


def with_margin_w(power_w: float | None, margin_percent: float | None) -> float | None:
    """``power_w`` with a margin of ``margin_percent`` [%]; None when either
    is unknown."""
    if power_w is None or margin_percent is None:
        return None
    return power_w * (1.0 + margin_percent / 100.0)


def system_margined_w(unit_margined_w: float | None, system_margin_percent: float | None) -> float | None:
    """The margined load with the system margin [W]; None when either is
    unknown."""
    return with_margin_w(unit_margined_w, system_margin_percent)


def source_power_w(load_w: float | None, efficiency: float | None, distribution_loss: float | None) -> float | None:
    """The power the source must deliver for ``load_w``: through the bus's
    converter (``efficiency`` in (0, 1]) and the distribution (``loss`` in
    [0, 1)) [W]; None when any input is unknown."""
    if load_w is None or efficiency is None or distribution_loss is None:
        return None
    if not 0.0 < efficiency <= 1.0 or not 0.0 <= distribution_loss < 1.0:
        raise ValueError("the efficiency must be in (0, 1] and the distribution loss in [0, 1)")
    return load_w / (efficiency * (1.0 - distribution_loss))


def _sum_opt(values: Iterable[float | None]) -> float | None:
    items = list(values)
    return None if any(v is None for v in items) else math.fsum(items)


# -- the results -------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Flow:
    """One power quantity (average or peak) along the chain: the load, with
    the unit margins, with the system margin, at the source, and at the
    source with the margins [W]. None: unknown."""

    load_w: float | None
    unit_margined_w: float | None
    system_margined_w: float | None
    source_w: float | None
    source_margined_w: float | None

    @property
    def complete(self) -> bool:
        return None not in (self.load_w, self.unit_margined_w, self.system_margined_w, self.source_w,
                            self.source_margined_w)


@dataclass(frozen=True)
class ItemPower:
    """One item in one system mode. ``power_mode`` is "" when the system
    mode does not give it one (its power is then unknown)."""

    item: str
    subsystem: str
    bus: str
    maturity: str
    power_mode: str
    average_w: float | None  # [W]
    duty_cycle: float  # [-]
    effective_w: float | None  # [W]
    peak_w: float | None  # [W]
    margin_percent: float | None  # [%]
    margined_w: float | None  # [W]
    margined_peak_w: float | None  # [W]


@dataclass(frozen=True)
class SubsystemPower:
    subsystem: str
    effective_w: float | None  # [W]
    margined_w: float | None  # [W]
    peak_w: float | None  # [W]
    margined_peak_w: float | None  # [W]


@dataclass(frozen=True)
class BusPower:
    bus: str
    converter_efficiency: float | None  # [-]
    average: Flow
    peak: Flow


@dataclass(frozen=True)
class ModePower:
    """The budget of one system mode: its rows, subsystems, buses and the
    spacecraft's totals."""

    mode: str
    duty_cycle: float | None  # [-]
    rows: tuple
    subsystems: tuple
    buses: tuple
    average: Flow
    peak: Flow


@dataclass(frozen=True)
class BudgetInput:
    """A number of the section the budget uses: a margin, the system margin,
    the distribution loss, a bus's efficiency. ``state`` is "given",
    "placeholder" or "missing"."""

    name: str
    path: str  # its place in the spacecraft ("budgets.distribution_loss")
    value: float | None
    unit: str
    source: str
    state: str


@dataclass
class PowerBudget:
    """A spacecraft's static power budget (module docstring)."""

    spacecraft: str
    modes: list = field(default_factory=list)  # list[ModePower], the file's order
    inputs: list = field(default_factory=list)  # list[BudgetInput], the numbers used
    findings: list = field(default_factory=list)  # list[Finding] (engine.findings)

    def mode(self, name: str) -> ModePower:
        return next(m for m in self.modes if m.mode == name)

    @property
    def complete(self) -> bool:
        """Whether every number of every mode is known."""
        return all(m.average.complete and m.peak.complete for m in self.modes)

    def duty_cycle_average(self) -> Flow | None:
        """The time-weighted average of the modes' average flows, when every
        mode has a duty cycle and they add up to 1 within
        :data:`DUTY_SUM_TOLERANCE`; None otherwise."""
        cycles = [m.duty_cycle for m in self.modes]
        if not cycles or None in cycles or abs(math.fsum(cycles) - 1.0) > DUTY_SUM_TOLERANCE:
            return None
        names = ("load_w", "unit_margined_w", "system_margined_w", "source_w", "source_margined_w")
        values = []
        for name in names:
            terms = [getattr(m.average, name) for m in self.modes]
            values.append(None if None in terms else math.fsum(m.duty_cycle * t for m, t in zip(self.modes, terms)))
        return Flow(*values)

    def rows(self) -> list[dict]:
        """One row per item and system mode, for export."""
        return [{"mode": m.mode, "item": r.item, "subsystem": r.subsystem, "bus": r.bus, "maturity": r.maturity,
                 "power_mode": r.power_mode, "average_w": r.average_w, "duty_cycle": r.duty_cycle,
                 "effective_w": r.effective_w, "margin_percent": r.margin_percent, "margined_w": r.margined_w,
                 "peak_w": r.peak_w, "margined_peak_w": r.margined_peak_w} for m in self.modes for r in m.rows]

    def mode_rows(self) -> list[dict]:
        """One row per system mode: the spacecraft's totals, for export."""
        return [{"mode": m.mode, "duty_cycle": m.duty_cycle, **_flow_row(m.average, ""), **_flow_row(m.peak, "peak_")}
                for m in self.modes]

    def bus_rows(self) -> list[dict]:
        """One row per system mode and bus, for export."""
        return [{"mode": m.mode, "bus": b.bus, "converter_efficiency": b.converter_efficiency,
                 **_flow_row(b.average, ""), **_flow_row(b.peak, "peak_")} for m in self.modes for b in m.buses]

    def subsystem_rows(self) -> list[dict]:
        """One row per system mode and subsystem, for export."""
        return [{"mode": m.mode, "subsystem": s.subsystem, "effective_w": s.effective_w, "margined_w": s.margined_w,
                 "peak_w": s.peak_w, "margined_peak_w": s.margined_peak_w} for m in self.modes for s in m.subsystems]


def _flow_row(flow: Flow, prefix: str) -> dict:
    return {f"{prefix}load_w": flow.load_w, f"{prefix}unit_margined_w": flow.unit_margined_w,
            f"{prefix}system_margined_w": flow.system_margined_w, f"{prefix}source_w": flow.source_w,
            f"{prefix}source_margined_w": flow.source_margined_w}


# -- the calculation ---------------------------------------------------------------------------------------------

def _known(value) -> float | None:
    return None if value is None else value.known


def _flow(load, unit_margined, system_margin, efficiency, loss) -> Flow:
    system = system_margined_w(unit_margined, system_margin)
    return Flow(load, unit_margined, system, source_power_w(load, efficiency, loss),
                source_power_w(system, efficiency, loss))


def _combine(flows: list) -> Flow:
    return Flow(*(_sum_opt(getattr(f, name) for f in flows) for name in
                  ("load_w", "unit_margined_w", "system_margined_w", "source_w", "source_margined_w")))


def _first_use(values) -> list:
    return list(dict.fromkeys(values))


def power_budget(sc) -> PowerBudget:
    """The :class:`PowerBudget` of spacecraft ``sc`` (empty without a
    ``budgets`` section)."""
    from ..schema.budgets import powered

    budget = PowerBudget(sc.name)
    section = sc.budgets
    if section is None:
        return budget
    system_margin = _known(section.system_power_margin_percent)
    loss = _known(section.distribution_loss)
    efficiency = {bus.name: _known(bus.converter_efficiency) for bus in section.buses}
    margins = {m.maturity: m.percent.known for m in section.power_margins}
    items = [item for item in section.equipment if powered(item)]
    for system_mode in section.modes:
        rows = []
        for item in items:
            mode = item.mode(system_mode.units.get(item.name, ""))
            margin = margins.get(item.maturity) if item.maturity else None
            average = mode.average_w.known if mode is not None else None
            peak = mode.peak.known if mode is not None else None
            duty = float(mode.duty_cycle) if mode is not None else 1.0
            effective = effective_power_w(average, duty)
            rows.append(ItemPower(item.name, item.subsystem, item.bus, item.maturity, mode.name if mode else "",
                                  average, duty, effective, peak, margin, with_margin_w(effective, margin),
                                  with_margin_w(peak, margin)))
        subsystems = tuple(
            SubsystemPower(name, _sum_opt(r.effective_w for r in rows if r.subsystem == name),
                           _sum_opt(r.margined_w for r in rows if r.subsystem == name),
                           _sum_opt(r.peak_w for r in rows if r.subsystem == name),
                           _sum_opt(r.margined_peak_w for r in rows if r.subsystem == name))
            for name in _first_use(r.subsystem for r in rows))
        buses = []
        for name in _first_use(r.bus for r in rows):
            members = [r for r in rows if r.bus == name]
            eta = efficiency.get(name)
            buses.append(BusPower(name, eta,
                                  _flow(_sum_opt(r.effective_w for r in members),
                                        _sum_opt(r.margined_w for r in members), system_margin, eta, loss),
                                  _flow(_sum_opt(r.peak_w for r in members),
                                        _sum_opt(r.margined_peak_w for r in members), system_margin, eta, loss)))
        budget.modes.append(ModePower(system_mode.name, system_mode.duty_cycle, tuple(rows), subsystems,
                                      tuple(buses), _combine([b.average for b in buses]),
                                      _combine([b.peak for b in buses])))
    budget.inputs = _inputs(section, items)
    budget.findings = findings(sc, budget.inputs)
    return budget


def _input(name: str, path: str, value, unit: str) -> BudgetInput:
    if value is None:
        return BudgetInput(name, path, None, unit, "", "missing")
    return BudgetInput(name, path, value.value, unit, value.source, "placeholder" if value.placeholder else "given")


def _inputs(section, items) -> list:
    """The numbers of the section the budget uses (as SBS's assumptions):
    the margin of each maturity the items use, the system margin, the
    distribution loss and the efficiency of each bus they use."""
    found = []
    for maturity in _first_use(item.maturity for item in items if item.maturity):
        margin = section.margin(maturity)
        found.append(_input(f"power margin, maturity {maturity}", f"budgets.power_margins[{maturity}].percent",
                            margin.percent if margin is not None else None, "%"))
    found.append(_input("system power margin", "budgets.system_power_margin_percent",
                        section.system_power_margin_percent, "%"))
    found.append(_input("distribution loss", "budgets.distribution_loss", section.distribution_loss, "-"))
    buses = {bus.name: bus for bus in section.buses}
    for name in _first_use(item.bus for item in items):
        found.append(_input(f"converter efficiency, bus {name}", f"budgets.buses[{name}].converter_efficiency",
                            buses[name].converter_efficiency, "-"))
    return found


# -- findings ----------------------------------------------------------------------------------------------------

def _listed(names: list) -> str:
    return ", ".join(names[:6]) + (f" and {len(names) - 6} more" if len(names) > 6 else "")


_EFFECT = {"power margin": "the margined power of its items is unknown",
           "system power margin": "the system-margined power of every mode is unknown",
           "distribution loss": "the source power of every mode is unknown",
           "converter efficiency": "the source power of the bus is unknown"}


def findings(sc, inputs: list | None = None) -> list:
    """The findings of spacecraft ``sc``'s ``budgets`` section
    (``budget.*`` rules of ``engine.findings``): the placeholders and
    missing numbers the power budget uses, items without a power margin,
    items a system mode leaves out, duty cycles that do not add up to one
    and masses that are placeholders. Nothing without a section."""
    from ..schema.budgets import powered

    section = sc.budgets
    if section is None:
        return []
    items = [item for item in section.equipment if powered(item)]
    if inputs is None:
        inputs = _inputs(section, items)
    name = sc.name
    found: list = []
    for entry in inputs:
        if entry.state == "given":
            continue
        effect = next(text for key, text in _EFFECT.items() if entry.name.startswith(key))
        if entry.name.startswith("power margin") and entry.state == "missing":
            maturity = entry.name.rsplit(" ", 1)[1]
            users = [item.name for item in items if item.maturity == maturity]
            found.append(Finding(f"{name}: budgets.power_margins has no margin for maturity {maturity!r}: the "
                                 f"margined power of {_listed(users)} is unknown", "budget.no_margin",
                                 actual=f"maturity {maturity}: no margin", limit="a margin for each maturity used"))
            continue
        if entry.state == "missing":
            state = "is not given"
        elif entry.value is None:
            state = "has no value (a placeholder)"
        else:
            state = f"is a placeholder (source {entry.source!r})"
        found.append(Finding(f"{name}: {entry.path} {state}: {effect}", "budget.placeholder",
                             actual=f"{entry.name}: {entry.state}", limit="a number with its source"))
    unclassified = [item.name for item in items if not item.maturity]
    if unclassified:
        found.append(Finding(f"{name}: budgets.equipment: no maturity for {_listed(unclassified)}, so no power "
                             "margin: their margined power is unknown", "budget.no_margin",
                             actual=f"{len(unclassified)} item(s) without a maturity",
                             limit="a maturity for each item with power modes"))
    used = set()
    for mode in section.modes:
        missing = [item.name for item in items if item.name not in mode.units]
        if missing:
            found.append(Finding(f"{name}: budgets.modes[{mode.name}].units does not give a power mode to "
                                 f"{_listed(missing)}: their power in this mode is unknown",
                                 "budget.unit_not_in_mode", actual=f"{len(missing)} item(s) not listed",
                                 limit="every item with power modes listed"))
        for item in items:
            if item.name in mode.units:
                used.add((item.name, mode.units[item.name]))
    unknown_power = []
    for item in items:
        for power_mode in item.power_modes:
            if (item.name, power_mode.name) in used and (power_mode.average_w.placeholder or power_mode.peak.placeholder):
                unknown_power.append(f"{item.name} ({power_mode.name})")
    if unknown_power:
        found.append(Finding(f"{name}: budgets.equipment: the power of {_listed(unknown_power)} is a placeholder: "
                             "the power of the modes that use it is unknown", "budget.placeholder",
                             actual=f"{len(unknown_power)} power mode(s) with a placeholder",
                             limit="a number with its source"))
    cycles = [mode.duty_cycle for mode in section.modes]
    if cycles and None not in cycles and abs(math.fsum(cycles) - 1.0) > DUTY_SUM_TOLERANCE:
        total = math.fsum(cycles)
        found.append(Finding(f"{name}: budgets.modes: the duty cycles add up to {total:.6g}, not 1: the time-weighted "
                             "average power is not computed", "budget.mode_duty_sum", actual=f"{total:.6g}",
                             limit=f"1 +- {DUTY_SUM_TOLERANCE:g}"))
    no_mass = [item.name for item in section.equipment
               if not item.mass_in_model and item.mass_kg is not None and item.mass_kg.placeholder]
    if no_mass:
        found.append(Finding(f"{name}: budgets.equipment: the mass of {_listed(no_mass)} is a placeholder: the mass "
                             "budget leaves it out and is incomplete", "budget.mass_unknown",
                             actual=f"{len(no_mass)} item(s) with a placeholder mass", limit="a mass with its source"))
    return found
