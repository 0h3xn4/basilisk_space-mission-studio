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
"""The ``budgets`` section of a spacecraft: the equipment list, the system
modes and the numbers of the static power budget
(``docs/developer/system-budget-phase1-design.md``, section 3; decisions
B-02 to B-10 of ``docs/developer/system-budget-decisions.md``).

Each equipment item has a sourced mass and a sourced power per power mode.
A system mode gives each item one of its power modes. The power margin per
maturity category, the system power margin, the converter efficiency per
bus and the distribution loss are sourced too. A sourced value
(:class:`SourcedValue`) is a number with the text that says where it comes
from; it is a placeholder when the number is null or the source is "TBD".
A placeholder makes every result that uses it unknown, never zero
(``analyses.power_budget``).

The section has its own ``version``. It is optional and written only when
set, so a scenario without it saves and hashes as before (apart from the
scenario's schema version, 5 since this section: decision B-01). Without
numpy, Basilisk or the GUI, like the rest of the schema.

Version 2 adds the optional ``pointing`` subsection: the pointing error
budget's requirements and contributors
(``docs/developer/pointing-error-budget-design.md``, decisions PE-1 to
PE-20). A version 1 section has none; :func:`migrate_section` reads it as
version 2 and changes nothing else.
"""

from __future__ import annotations

import math
from dataclasses import MISSING, dataclass, field, fields

from ..config.materials import S120_SUBSYSTEMS

BUDGETS_VERSION = 2
#: The S-120 columns an item's mass can take its growth allowance from
#: ("" takes the largest of the row, as for a part without a column).
MASS_COLUMNS = ("",) + S120_SUBSYSTEMS
#: The source text that marks a placeholder (in any case, with spaces).
PLACEHOLDER_SOURCE = "TBD"

_MAX_MARGIN_PERCENT = 1000.0  # [%] the SBS limit of a margin ratio, 10, in percent


def _fail(message: str) -> None:
    from .scenario import ScenarioValidationError

    raise ScenarioValidationError(message)


def _require(condition: bool, message: str) -> None:
    if not condition:
        _fail(message)


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _name(value, where: str, what: str) -> None:
    _require(isinstance(value, str) and value.strip() == value and bool(value) and "]" not in value
             and "." not in value, f"{where}: a {what} needs a name without '.', ']' or surrounding spaces")


def _unique(names: list, where: str, what: str) -> None:
    repeated = sorted({n for n in names if names.count(n) > 1})
    _require(not repeated, f"{where}: {what} names must be unique ({', '.join(map(str, repeated))} repeated)")


@dataclass
class SourcedValue:
    """A number and where it comes from. A placeholder when ``value`` is
    null or ``source`` is "TBD" (in any case): it gives "unknown" to every
    result that uses it (decision B-04)."""

    value: float | None  # the number, in the unit of the field that holds it; null for a placeholder
    source: str  # where the number comes from (a data sheet, a rule); "TBD" marks a placeholder

    @property
    def placeholder(self) -> bool:
        return self.value is None or self.source.strip().upper() == PLACEHOLDER_SOURCE

    @property
    def known(self) -> float | None:
        """The number, or None for a placeholder."""
        return None if self.placeholder else float(self.value)

    def validate(self, where: str, low: float | None = None, high: float | None = None, low_open: bool = False,
                 high_open: bool = False) -> None:
        """A number with a source, within ``low`` to ``high`` when it is not
        a placeholder (placeholders are not range-checked, as in SBS)."""
        _require(isinstance(self.source, str), f"{where}: source must be text")
        _require(self.value is None or _number(self.value), f"{where}: value must be a number or null")
        _require(self.value is None or bool(self.source.strip()),
                 f"{where}: a number needs a source (write \"{PLACEHOLDER_SOURCE}\" for a placeholder)")
        number = self.known
        if number is None:
            return
        if low is not None:
            _require(number > low if low_open else number >= low,
                     f"{where}: value must be {'above' if low_open else 'at least'} {low:g}")
        if high is not None:
            _require(number < high if high_open else number <= high,
                     f"{where}: value must be {'below' if high_open else 'at most'} {high:g}")


def _sourced(value, where: str, **limits) -> None:
    _require(isinstance(value, SourcedValue), f"{where} must be an object {{\"value\": ..., \"source\": ...}}")
    value.validate(where, **limits)


@dataclass
class BudgetBusConfig:
    """A power bus: its converter efficiency, the share of the bus load the
    source must deliver through the converter (absent: unknown)."""

    name: str
    converter_efficiency: SourcedValue | None = None  # [-] ratio in (0, 1]

    def validate(self, where: str) -> None:
        _name(self.name, where, "bus")
        if self.converter_efficiency is not None:
            _sourced(self.converter_efficiency, f"{where}: bus {self.name!r}: converter_efficiency", low=0.0,
                     high=1.0, low_open=True)


@dataclass
class PowerMarginConfig:
    """The power margin of one maturity category of the mass policy
    (decision B-05)."""

    maturity: str  # a category of the spacecraft's mass policy ("estimated" ... "measured" for AIAA S-120)
    percent: SourcedValue  # [%] the margin on an item's effective power, 0 to 1000

    def validate(self, where: str) -> None:
        _sourced(self.percent, f"{where}: power margin {self.maturity!r}: percent", low=0.0,
                 high=_MAX_MARGIN_PERCENT)


@dataclass
class BudgetPowerModeConfig:
    """One power mode of an equipment item: its average power while in the
    mode and switched on, its peak power (default: the average) and the
    share of the time it is switched on."""

    name: str
    average_w: SourcedValue  # [W] at least 0
    peak_w: SourcedValue | None = None  # [W] at least the average; absent: the average
    duty_cycle: float = 1.0  # [-] 0 to 1, the share of the mode's time the item draws its average power

    @property
    def peak(self) -> SourcedValue:
        return self.peak_w if self.peak_w is not None else self.average_w

    def validate(self, where: str) -> None:
        _name(self.name, where, "power mode")
        here = f"{where}: power mode {self.name!r}"
        _sourced(self.average_w, f"{here}: average_w", low=0.0)
        if self.peak_w is not None:
            _sourced(self.peak_w, f"{here}: peak_w", low=0.0)
            average, peak = self.average_w.known, self.peak_w.known
            _require(average is None or peak is None or peak >= average,
                     f"{here}: peak_w must be at least average_w")
        _require(_number(self.duty_cycle) and 0.0 <= self.duty_cycle <= 1.0, f"{here}: duty_cycle must be in [0, 1]")


@dataclass
class BudgetEquipmentConfig:
    """An item of the equipment list (decision B-03): a functional
    ``subsystem`` (AOCS, DHS) that groups the power budget, an S-120
    ``mass_column`` for its growth allowance (B-06), the bus it draws from,
    its maturity, a sourced mass and its power modes. ``mass_in_model``
    says that the 3D model already holds its mass, so the mass budget adds
    no line for it. ``source_id`` is the IDM-CIC unit's ``fullId`` when an
    import made it."""

    name: str
    subsystem: str = ""  # the functional subsystem (AOCS, DHS, EPS...), free text; groups the power budget
    mass_column: str = ""  # "" or an S-120 column (MASS_COLUMNS): the growth allowance; "" the largest of the row
    bus: str = ""  # the name of an entry of buses; required for an item with power modes
    maturity: str = ""  # "" or a category of the spacecraft's mass policy: the growth allowance and power margin
    mass_kg: SourcedValue | None = None  # [kg] at least 0; may be absent when mass_in_model
    mass_in_model: bool = False  # the 3D model already holds this item's mass: no mass budget line
    power_modes: list = field(default_factory=list)  # list[BudgetPowerModeConfig]
    source_id: str = ""  # the IDM-CIC unit's fullId when an import made the item

    def mode(self, name: str) -> BudgetPowerModeConfig | None:
        return next((m for m in self.power_modes if m.name == name), None)

    def validate(self, where: str, buses: set, categories) -> None:
        _name(self.name, where, "equipment item")
        here = f"{where}: equipment {self.name!r}"
        for key in ("subsystem", "mass_column", "bus", "maturity", "source_id"):
            _require(isinstance(getattr(self, key), str), f"{here}: {key} must be text")
        _require(self.mass_column in MASS_COLUMNS,
                 f"{here}: mass_column {self.mass_column!r} must be \"\" or one of {list(MASS_COLUMNS[1:])}")
        _require(self.maturity == "" or self.maturity in categories,
                 f"{here}: maturity {self.maturity!r} must be \"\" or one of {list(categories)}")
        _require(isinstance(self.mass_in_model, bool), f"{here}: mass_in_model must be true or false")
        if self.mass_kg is not None:
            _sourced(self.mass_kg, f"{here}: mass_kg", low=0.0)
        _require(self.mass_kg is not None or self.mass_in_model,
                 f"{here}: give mass_kg (a placeholder if it is not known), or set mass_in_model when the 3D "
                 "model holds the mass")
        for mode in self.power_modes:
            _require(isinstance(mode, BudgetPowerModeConfig), f"{here}: each power mode must be an object")
            mode.validate(here)
        _unique([m.name for m in self.power_modes], here, "power mode")
        _require(not self.power_modes or self.bus in buses,
                 f"{here}: bus {self.bus!r} must name one of buses ({', '.join(sorted(buses)) or 'none given'})")
        _require(self.bus == "" or self.bus in buses, f"{here}: bus {self.bus!r} is not one of buses")


@dataclass
class BudgetModeConfig:
    """A system mode: the power mode each equipment item is in (``units``,
    item name to power-mode name) and, optionally, the share of the time
    the spacecraft spends in it. An item with power modes that ``units``
    does not list has an unknown power in this mode (decision B-09)."""

    name: str
    duty_cycle: float | None = None  # [-] 0 to 1, the share of the time in this mode; absent: not stated
    units: dict = field(default_factory=dict)  # {equipment item name: its power-mode name}

    def validate(self, where: str, items: dict) -> None:
        _name(self.name, where, "system mode")
        here = f"{where}: mode {self.name!r}"
        _require(self.duty_cycle is None or (_number(self.duty_cycle) and 0.0 <= self.duty_cycle <= 1.0),
                 f"{here}: duty_cycle must be in [0, 1]")
        for item, mode in self.units.items():
            _require(item in items, f"{here}: units: {item!r} is not an equipment item")
            names = [m.name for m in items[item].power_modes]
            _require(isinstance(mode, str) and mode in names,
                     f"{here}: units: {item!r} has no power mode {mode!r} ({', '.join(names) or 'it has none'})")


# -- the pointing error budget (version 2; decisions PE-1 to PE-20) -------------------------------------------

#: The error indices of a pointing requirement (design note, section 2).
POINTING_INDICES = ("absolute", "mean", "relative", "drift", "reproducibility")
#: What a requirement is on: the error of the pointing, or of the knowledge of it.
POINTING_KINDS = ("performance", "knowledge")
#: What a contributor enters: performance, knowledge or both.
POINTING_CONTRIBUTOR_KINDS = ("performance", "knowledge", "both")
#: The body axes a value is given about.
POINTING_AXES = ("x", "y", "z")
#: The axis of a requirement: a body axis, or the line of sight (a half-cone, from the two axes across it).
LINE_OF_SIGHT = "line_of_sight"
POINTING_REQUIREMENT_AXES = POINTING_AXES + (LINE_OF_SIGHT,)
#: Over what population a requirement's probability holds.
POINTING_INTERPRETATIONS = ("temporal", "ensemble", "mixed")
#: The time behaviour of a contributor: it decides the indices it enters (engine.pointing_budget).
POINTING_BEHAVIOURS = ("bias", "random", "periodic", "drift", "transient")
#: The shape of a contributor's spread: its 1-sigma (gaussian), half-width (uniform) or amplitude (sinusoidal).
POINTING_DISTRIBUTIONS = ("gaussian", "uniform", "sinusoidal")


def _choice(value, choices, where: str, what: str) -> None:
    _require(value in choices, f"{where}: {what} {value!r} must be one of {list(choices)}")


@dataclass
class PointingRequirementConfig:
    """A pointing requirement: the error ``index`` of the pointing (or of
    its knowledge) about one ``axis`` must stay within ``limit_arcsec`` with
    the ``probability`` given. The windows are the observation period (mean,
    relative, drift and reproducibility) and, for relative, the shorter
    stability time. ``modes`` names the system modes it applies to (a
    record: the budget does not depend on them)."""

    name: str
    limit_arcsec: SourcedValue  # [arcsec] above 0; a placeholder until known
    probability: SourcedValue  # [-] in (0, 1), the probability the error stays within the limit; no default
    index: str = "absolute"  # one of POINTING_INDICES
    kind: str = "performance"  # "performance" or "knowledge"
    axis: str = "x"  # "x", "y", "z" or "line_of_sight" (a half-cone from the two axes across the line of sight)
    interpretation: str = "temporal"  # "temporal", "ensemble" or "mixed": over what the probability holds
    window_s: SourcedValue | None = None  # [s] above 0, the observation period (mean, relative, drift, reproducibility)
    stability_s: SourcedValue | None = None  # [s] above 0, at most window_s: the window of a relative index
    modes: list = field(default_factory=list)  # list[str], system modes of budgets.modes it applies to

    def validate(self, where: str, modes: set) -> None:
        _name(self.name, where, "pointing requirement")
        here = f"{where}: pointing requirement {self.name!r}"
        _choice(self.index, POINTING_INDICES, here, "index")
        _choice(self.kind, POINTING_KINDS, here, "kind")
        _choice(self.axis, POINTING_REQUIREMENT_AXES, here, "axis")
        _choice(self.interpretation, POINTING_INTERPRETATIONS, here, "interpretation")
        _sourced(self.limit_arcsec, f"{here}: limit_arcsec", low=0.0, low_open=True)
        _sourced(self.probability, f"{here}: probability", low=0.0, high=1.0, low_open=True, high_open=True)
        for key in ("window_s", "stability_s"):
            if getattr(self, key) is not None:
                _sourced(getattr(self, key), f"{here}: {key}", low=0.0, low_open=True)
        window = self.window_s.known if self.window_s is not None else None
        stability = self.stability_s.known if self.stability_s is not None else None
        _require(window is None or stability is None or stability <= window,
                 f"{here}: stability_s must be at most window_s")
        _require(isinstance(self.modes, list) and all(isinstance(m, str) for m in self.modes),
                 f"{here}: modes must be a list of system mode names")
        for mode in self.modes:
            _require(mode in modes, f"{here}: modes: {mode!r} is not a system mode of budgets.modes")
        _unique(list(self.modes), here, "mode")


@dataclass
class PointingContributorConfig:
    """A source of pointing error: its ``kind`` (the indices of performance,
    of knowledge, or both), its time ``behaviour`` (which indices it enters
    and by what share: ``engine.pointing_budget``) and, per body axis, a
    mean and a spread in arcsec. The spread is a 1-sigma (gaussian), a
    half-width (uniform) or an amplitude (sinusoidal). An axis left out of
    ``mean_arcsec`` has no mean; an axis left out of ``spread_arcsec`` has
    no spread: the contributor does not act on it. A placeholder makes
    every index it enters "TBD" (decision PE-8). Contributors of one
    ``group`` are correlated and add linearly (PE-4)."""

    name: str
    kind: str = "performance"  # "performance", "knowledge" or "both"
    behaviour: str = "random"  # one of POINTING_BEHAVIOURS
    distribution: str = "gaussian"  # one of POINTING_DISTRIBUTIONS: what spread_arcsec is
    mean_arcsec: dict = field(default_factory=dict)  # {axis: SourcedValue} [arcsec], any sign; absent: no mean
    spread_arcsec: dict = field(default_factory=dict)  # {axis: SourcedValue} [arcsec] at least 0; absent: no spread
    period_s: SourcedValue | None = None  # [s] above 0, the period of a periodic contributor (needed for it)
    group: str = ""  # contributors of one group are correlated: they add linearly; "" independent
    equipment: str = ""  # the equipment item it comes from (budgets.equipment); "" another source
    sensor: str = ""  # the scenario sensor it was made from (Add Scenario Sensors); "" none

    def validate(self, where: str, items: set) -> None:
        _name(self.name, where, "pointing contributor")
        here = f"{where}: pointing contributor {self.name!r}"
        _choice(self.kind, POINTING_CONTRIBUTOR_KINDS, here, "kind")
        _choice(self.behaviour, POINTING_BEHAVIOURS, here, "behaviour")
        _choice(self.distribution, POINTING_DISTRIBUTIONS, here, "distribution")
        for key in ("group", "equipment", "sensor"):
            _require(isinstance(getattr(self, key), str), f"{here}: {key} must be text")
        for key, low in (("mean_arcsec", None), ("spread_arcsec", 0.0)):
            values = getattr(self, key)
            _require(isinstance(values, dict), f"{here}: {key} must be an object {{\"x\": ..., \"y\": ..., \"z\": ...}}")
            for axis, value in values.items():
                _require(axis in POINTING_AXES, f"{here}: {key}: axis {axis!r} must be one of {list(POINTING_AXES)}")
                _sourced(value, f"{here}: {key}.{axis}", low=low)
        if self.period_s is not None:
            _sourced(self.period_s, f"{here}: period_s", low=0.0, low_open=True)
        _require(self.behaviour != "periodic" or self.period_s is not None,
                 f"{here}: a periodic contributor needs period_s (a placeholder if it is not known)")
        _require(self.equipment == "" or self.equipment in items,
                 f"{here}: equipment {self.equipment!r} is not an item of budgets.equipment")


@dataclass
class PointingConfig:
    """The pointing error budget of a spacecraft (design note section 3.1):
    its requirements, its contributors and the body axis along the line of
    sight, which a half-cone requirement needs."""

    line_of_sight: str = ""  # "x", "y" or "z": the body axis along the line of sight; "" not stated
    requirements: list = field(default_factory=list)  # list[PointingRequirementConfig]
    contributors: list = field(default_factory=list)  # list[PointingContributorConfig]

    def requirement(self, name: str) -> PointingRequirementConfig | None:
        return next((r for r in self.requirements if r.name == name), None)

    def contributor(self, name: str) -> PointingContributorConfig | None:
        return next((c for c in self.contributors if c.name == name), None)

    def validate(self, where: str, modes: set, items: set) -> None:
        where = f"{where}.pointing"
        _require(self.line_of_sight == "" or self.line_of_sight in POINTING_AXES,
                 f"{where}: line_of_sight {self.line_of_sight!r} must be \"\" or one of {list(POINTING_AXES)}")
        for group, cls in (("requirements", PointingRequirementConfig), ("contributors", PointingContributorConfig)):
            _require(isinstance(getattr(self, group), list)
                     and all(isinstance(item, cls) for item in getattr(self, group)),
                     f"{where}: each entry of {group} must be an object")
        for requirement in self.requirements:
            requirement.validate(where, modes)
        _unique([r.name for r in self.requirements], where, "pointing requirement")
        for contributor in self.contributors:
            contributor.validate(where, items)
        _unique([c.name for c in self.contributors], where, "pointing contributor")


@dataclass
class BudgetsConfig:
    """A spacecraft's equipment list, system modes and power budget numbers
    (module docstring)."""

    version: int = BUDGETS_VERSION
    buses: list = field(default_factory=list)  # list[BudgetBusConfig]
    distribution_loss: SourcedValue | None = None  # [-] ratio in [0, 1), lost between source and loads
    power_margins: list = field(default_factory=list)  # list[PowerMarginConfig]
    system_power_margin_percent: SourcedValue | None = None  # [%] 0 to 1000, on the sum of the margined loads
    equipment: list = field(default_factory=list)  # list[BudgetEquipmentConfig]
    modes: list = field(default_factory=list)  # list[BudgetModeConfig]
    pointing: PointingConfig | None = None  # the pointing error budget (version 2); absent: none

    def item(self, name: str) -> BudgetEquipmentConfig | None:
        return next((item for item in self.equipment if item.name == name), None)

    def margin(self, maturity: str) -> PowerMarginConfig | None:
        return next((m for m in self.power_margins if m.maturity == maturity), None)

    def validate(self, where: str, spacecraft) -> None:
        """Check the section against its spacecraft (the maturity categories
        are those of its mass policy)."""
        where = f"{where}: budgets"
        _require(self.version == BUDGETS_VERSION,
                 f"{where}: version {self.version!r} is not one this version reads (it reads {BUDGETS_VERSION})")
        categories = mass_policy_of(spacecraft).categories
        for group, cls in (("buses", BudgetBusConfig), ("power_margins", PowerMarginConfig),
                           ("equipment", BudgetEquipmentConfig), ("modes", BudgetModeConfig)):
            _require(all(isinstance(item, cls) for item in getattr(self, group)),
                     f"{where}: each entry of {group} must be an object")
        for bus in self.buses:
            bus.validate(where)
        _unique([bus.name for bus in self.buses], where, "bus")
        if self.distribution_loss is not None:
            _sourced(self.distribution_loss, f"{where}: distribution_loss", low=0.0, high=1.0, high_open=True)
        for margin in self.power_margins:
            _require(margin.maturity in categories, f"{where}: power margin {margin.maturity!r}: maturity must be "
                                                    f"one of {list(categories)}")
            margin.validate(where)
        _unique([m.maturity for m in self.power_margins], where, "power margin maturity")
        if self.system_power_margin_percent is not None:
            _sourced(self.system_power_margin_percent, f"{where}: system_power_margin_percent", low=0.0,
                     high=_MAX_MARGIN_PERCENT)
        buses = {bus.name for bus in self.buses}
        for item in self.equipment:
            item.validate(where, buses, categories)
        _unique([item.name for item in self.equipment], where, "equipment")
        items = {item.name: item for item in self.equipment}
        for mode in self.modes:
            mode.validate(where, items)
        _unique([mode.name for mode in self.modes], where, "mode")
        if self.pointing is not None:
            _require(isinstance(self.pointing, PointingConfig), f"{where}: pointing must be an object")
            self.pointing.validate(where, {mode.name for mode in self.modes}, set(items))


def mass_policy_of(spacecraft):
    """The mass policy in force for ``spacecraft``: its 3D model's mass
    budget policy, else the default (``config.materials``)."""
    from ..config import materials as library

    model = getattr(spacecraft, "model", None)
    settings = model.mass_budget if model is not None else None
    return library.mass_policy(settings.policy if settings is not None else "")


def powered(item: BudgetEquipmentConfig) -> bool:
    """Whether ``item`` is in the power budget: it has a power mode. An item
    without one (a structure, a harness) is in the mass budget only."""
    return bool(item.power_modes)


# -- reading and saving ------------------------------------------------------------------------------------------

def _sourced_from(data, where: str, record):
    return None if data is None else record(SourcedValue, data, where)


def _migrate_1_to_2(data: dict) -> dict:
    """Section version 1 -> 2: a section can hold ``pointing`` (the pointing
    error budget). The subsection is new and optional, so a version 1
    section has none, and nothing else changes: the step only sets the
    version. Version 2 marks the sections that 2.15.0 and earlier cannot
    read."""
    data["version"] = 2
    return data


#: The steps of the section's own version, {old version: step}, as ``schema.migrations.MIGRATIONS``.
SECTION_MIGRATIONS = {1: _migrate_1_to_2}


def migrate_section(data: dict) -> dict:
    """``data``, a section's JSON object, brought up to
    :data:`BUDGETS_VERSION` one step at a time. Another version (newer, or
    not a number) is left as it is: validation then names it."""
    version = data.get("version", BUDGETS_VERSION)
    while isinstance(version, int) and not isinstance(version, bool) and version in SECTION_MIGRATIONS:
        data = SECTION_MIGRATIONS[version](data)
        version = data["version"]
    return data


def _sourced_axes(data, where: str, record, fields_of) -> dict:
    """``{axis: SourcedValue}`` from its JSON object."""
    return {axis: record(SourcedValue, value, f"{where}.{axis}") for axis, value in fields_of(data, where).items()}


def _pointing_from(data, where: str, record, fields_of) -> PointingConfig:
    data = fields_of(data, where)
    requirements = []
    for k, item in enumerate(_list(data.pop("requirements", []), f"{where}.requirements")):
        here = f"{where}.requirements[{k}]"
        item = fields_of(item, here)
        for key in ("limit_arcsec", "probability"):
            if key in item:
                item[key] = record(SourcedValue, item[key], f"{here}.{key}")
        for key in ("window_s", "stability_s"):
            item[key] = _sourced_from(item.get(key), f"{here}.{key}", record)
        requirements.append(record(PointingRequirementConfig, item, here))
    contributors = []
    for k, item in enumerate(_list(data.pop("contributors", []), f"{where}.contributors")):
        here = f"{where}.contributors[{k}]"
        item = fields_of(item, here)
        for key in ("mean_arcsec", "spread_arcsec"):
            item[key] = _sourced_axes(item.get(key, {}), f"{here}.{key}", record, fields_of)
        item["period_s"] = _sourced_from(item.get("period_s"), f"{here}.period_s", record)
        contributors.append(record(PointingContributorConfig, item, here))
    data.update(requirements=requirements, contributors=contributors)
    return record(PointingConfig, data, where)


def from_dict(data, where: str, record, records, fields_of) -> BudgetsConfig:
    """The section read from its JSON object, with the scenario loader's
    record builders (so every structural error reads the same). An older
    version is migrated first (:func:`migrate_section`)."""
    data = migrate_section(fields_of(data, where))
    buses = []
    for k, bus in enumerate(_list(data.pop("buses", []), f"{where}.buses")):
        bus = fields_of(bus, f"{where}.buses[{k}]")
        bus["converter_efficiency"] = _sourced_from(bus.get("converter_efficiency"),
                                                    f"{where}.buses[{k}].converter_efficiency", record)
        buses.append(record(BudgetBusConfig, bus, f"{where}.buses[{k}]"))
    margins = []
    for k, margin in enumerate(_list(data.pop("power_margins", []), f"{where}.power_margins")):
        margin = fields_of(margin, f"{where}.power_margins[{k}]")
        if "percent" in margin:
            margin["percent"] = record(SourcedValue, margin["percent"], f"{where}.power_margins[{k}].percent")
        margins.append(record(PowerMarginConfig, margin, f"{where}.power_margins[{k}]"))
    equipment = []
    for k, item in enumerate(_list(data.pop("equipment", []), f"{where}.equipment")):
        here = f"{where}.equipment[{k}]"
        item = fields_of(item, here)
        item["mass_kg"] = _sourced_from(item.get("mass_kg"), f"{here}.mass_kg", record)
        modes = []
        for j, mode in enumerate(_list(item.pop("power_modes", []), f"{here}.power_modes")):
            mode = fields_of(mode, f"{here}.power_modes[{j}]")
            if "average_w" in mode:
                mode["average_w"] = record(SourcedValue, mode["average_w"], f"{here}.power_modes[{j}].average_w")
            mode["peak_w"] = _sourced_from(mode.get("peak_w"), f"{here}.power_modes[{j}].peak_w", record)
            modes.append(record(BudgetPowerModeConfig, mode, f"{here}.power_modes[{j}]"))
        item["power_modes"] = modes
        equipment.append(record(BudgetEquipmentConfig, item, here))
    data["modes"] = records(BudgetModeConfig, data.pop("modes", []), f"{where}.modes")
    for name in ("distribution_loss", "system_power_margin_percent"):
        data[name] = _sourced_from(data.get(name), f"{where}.{name}", record)
    if data.get("pointing") is not None:
        data["pointing"] = _pointing_from(data["pointing"], f"{where}.pointing", record, fields_of)
    data.update(buses=buses, power_margins=margins, equipment=equipment)
    return record(BudgetsConfig, data, where)


def _list(data, where: str) -> list:
    if not isinstance(data, list):
        from .scenario import _StructureError

        raise _StructureError(f"{where} must be a list ([...])")
    return data


def _defaults(cls) -> dict:
    found = {}
    for f in fields(cls):
        if f.default is not MISSING:
            found[f.name] = f.default
        elif f.default_factory is not MISSING:
            found[f.name] = f.default_factory()
    return found


def _compact_record(entry: dict, cls) -> dict:
    """``entry`` without the fields that hold their default (a sourced
    value is kept whole: its null value is what makes it a placeholder)."""
    defaults = _defaults(cls)
    return {key: value for key, value in entry.items() if key not in defaults or value != defaults[key]}


def compact(section: dict) -> dict:
    """The saved form of a section (``dataclasses.asdict``): fields at their
    default, absent values and empty lists left out, so a section saves
    only what it sets."""
    out: dict = {"version": section["version"]}
    if section.get("buses"):
        out["buses"] = [_compact_record(bus, BudgetBusConfig) for bus in section["buses"]]
    if section.get("distribution_loss") is not None:
        out["distribution_loss"] = dict(section["distribution_loss"])
    if section.get("power_margins"):
        out["power_margins"] = [dict(margin) for margin in section["power_margins"]]
    if section.get("system_power_margin_percent") is not None:
        out["system_power_margin_percent"] = dict(section["system_power_margin_percent"])
    if section.get("equipment"):
        items = []
        for item in section["equipment"]:
            item = _compact_record(item, BudgetEquipmentConfig)
            if "power_modes" in item:
                item["power_modes"] = [_compact_record(mode, BudgetPowerModeConfig) for mode in item["power_modes"]]
            items.append(item)
        out["equipment"] = items
    if section.get("modes"):
        out["modes"] = [_compact_record(mode, BudgetModeConfig) for mode in section["modes"]]
    if section.get("pointing") is not None:
        out["pointing"] = _compact_pointing(section["pointing"])
    return out


def _compact_pointing(pointing: dict) -> dict:
    """The saved form of the ``pointing`` subsection: as :func:`compact`,
    absent values, empty lists and fields at their default left out."""
    out: dict = {}
    if pointing.get("line_of_sight"):
        out["line_of_sight"] = pointing["line_of_sight"]
    if pointing.get("requirements"):
        out["requirements"] = [_compact_record(_without_none(item), PointingRequirementConfig)
                               for item in pointing["requirements"]]
    if pointing.get("contributors"):
        out["contributors"] = [_compact_record(_without_none(item), PointingContributorConfig)
                               for item in pointing["contributors"]]
    return out


def _without_none(entry: dict) -> dict:
    """``entry`` without its absent optional values (a ``None`` sourced value)."""
    return {key: value for key, value in entry.items() if value is not None}


def import_values(spacecraft) -> dict:
    """The values of the equipment items and system modes an IDM-CIC import
    made (items with a ``source_id``), keyed by that identifier, so a
    renamed item keeps its record: ``budgets.equipment[<source_id>].mass_kg``
    and each power mode's ``average_w`` and ``peak_w``; each system mode's
    ``duty_cycle`` and the power mode it gives each imported item."""
    section = getattr(spacecraft, "budgets", None)
    if section is None:
        return {}
    found: dict = {}
    source_of = {}
    for item in section.equipment:
        if not item.source_id:
            continue
        source_of[item.name] = item.source_id
        where = f"budgets.equipment[{item.source_id}]"
        if item.mass_kg is not None and item.mass_kg.value is not None:
            found[f"{where}.mass_kg"] = item.mass_kg.value
        for mode in item.power_modes:
            for key in ("average_w", "peak_w"):
                value = getattr(mode, key)
                if value is not None and value.value is not None:
                    found[f"{where}.power_modes[{mode.name}].{key}"] = value.value
    for mode in section.modes:
        if mode.duty_cycle is not None:
            found[f"budgets.modes[{mode.name}].duty_cycle"] = mode.duty_cycle
        for item, power_mode in mode.units.items():
            if item in source_of:
                found[f"budgets.modes[{mode.name}].units[{source_of[item]}]"] = power_mode
    return found
