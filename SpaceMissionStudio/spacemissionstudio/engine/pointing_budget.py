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
"""The pointing error budget of a spacecraft: per requirement, the
contributors that enter its error index, their sum, the value at the
requirement's probability and the margin against its limit
(``docs/developer/pointing-error-budget-design.md``, sections 2 and 3.2;
decisions PE-1 to PE-20 of ``docs/DECISIONS.md``).

Clean room: the concepts are the public ones of the ECSS control
performance standard (error indices, windows, statistical
interpretations, classes of contributors, a summation per index), in
this project's own words and arithmetic. No other tool's rules or numbers.

**Units.** The ``budgets.pointing`` section holds angles in arcsec. This
module computes in radians and seconds. There is one boundary:
:func:`inputs` turns the section's arcsec into radians
(:func:`arcsec_to_rad`), and the rows for display and export turn the
results back (:func:`rad_to_arcsec`). Nothing else converts.

**The selection table** (:data:`SELECTION`, step 1 of the design's 3.2):
which share of a contributor, by its time behaviour, enters each index.
The share multiplies the contributor's mean and its standard deviation.

=============  ========  =====  ========  =====  ===============
behaviour      absolute  mean   relative  drift  reproducibility
=============  ========  =====  ========  =====  ===============
bias           1         1      0         0      0
random         1         0      1         0      0
periodic       1         s_m    s_r       2 s_m  2 s_m
drift          1         1      0         1      1
transient      1         1      1         0      0
=============  ========  =====  ========  =====  ===============

A periodic contributor enters by the share of it that the window sees
(PE-7), for a sinusoid of period ``T`` and a window ``t``, ``r = t / T``:

* ``s_m`` (:func:`mean_share`), the window mean: ``1`` while
  ``pi r <= 1``, else ``1 / (pi r)``. The exact largest window mean is
  ``|sin(pi r)| / (pi r)``; its bound is used, so a term does not vanish
  at whole periods when the period is not exactly known (PE-11);
* ``s_r`` (:func:`relative_share`), the largest distance from the window
  mean, exact: ``1 + |sin(pi r)| / (pi r)`` from one period on, and the
  largest over every phase below it (for half a period
  ``sqrt(1 + 4 / pi^2)``);
* drift and reproducibility, the change of the window mean between two
  windows: at most twice the window mean, ``2 s_m``, whatever their
  distance (PE-12).

**The sum** (PE-4): per index and axis, the means add linearly; within a
correlated group the standard deviations add linearly; the groups and
the independent contributors add root-sum-square. A spread is a
standard deviation for a Gaussian, ``half-width / sqrt(3)`` for a
uniform and ``amplitude / sqrt(2)`` for a sinusoid (PE-13).

**The value at the probability** ``P`` of a requirement about one axis:
``|mean| + k std`` with ``k`` the two-sided standard-normal factor,
``P(|X| <= k) = P``. About the line of sight (a half-cone, PE-6 and
PE-10): from the two axes across it, ``sqrt(mean_a^2 + mean_b^2) +
max(std_a, std_b) sqrt(-2 ln(1 - P))``: the radius that holds ``P`` of
a circular Gaussian with the larger deviation, plus the length of the
mean (exact for equal deviations and no mean, above the true value
otherwise). The margin is the limit minus the value.

**"TBD"** (PE-8): a placeholder, a missing window or period that a
contributor needs, or a probability not known makes every value that
needs it None ("TBD"), never zero. The statistical interpretation is
recorded and shown; the sum is the same for each (PE-14).

Pure Python and NumPy: no Basilisk, no Qt.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import lru_cache
from statistics import NormalDist

import numpy as np

#: [rad] one arcsecond: pi / (180 * 3600).
ARCSEC_RAD = math.pi / 648000.0

WINDOW = "window"  # a share given by the periodic window rule

#: The share of a contributor in each index, by its behaviour (the module docstring's table).
SELECTION = {
    "bias": {"absolute": 1.0, "mean": 1.0, "relative": 0.0, "drift": 0.0, "reproducibility": 0.0},
    "random": {"absolute": 1.0, "mean": 0.0, "relative": 1.0, "drift": 0.0, "reproducibility": 0.0},
    "periodic": {"absolute": 1.0, "mean": WINDOW, "relative": WINDOW, "drift": WINDOW, "reproducibility": WINDOW},
    "drift": {"absolute": 1.0, "mean": 1.0, "relative": 0.0, "drift": 1.0, "reproducibility": 1.0},
    "transient": {"absolute": 1.0, "mean": 1.0, "relative": 1.0, "drift": 0.0, "reproducibility": 0.0},
}

#: The selection table as text, shown next to each contributor (design note, section 6).
RULES = {
    "bias": "constant: enters absolute and mean; no relative, drift or reproducibility",
    "random": "noise: enters absolute and relative; its window mean goes to zero",
    "periodic": "periodic: absolute in full; mean, relative, drift and reproducibility by the share its window sees",
    "drift": "slow change: enters absolute, mean, drift and reproducibility; not relative",
    "transient": "short event: enters absolute, mean and relative; not drift or reproducibility",
}

#: The standard deviation of a spread of 1, by the distribution (PE-13).
STD_OF_SPREAD = {"gaussian": 1.0, "uniform": 1.0 / math.sqrt(3.0), "sinusoidal": 1.0 / math.sqrt(2.0)}

#: The statuses of a requirement.
MET, NOT_MET, TBD, NO_CONTRIBUTOR = "met", "not met", "TBD", "no contributor"

_PHASES = 720  # [-] phases a relative share below one period is searched over, before its refinement


# -- the boundary: arcsec in, radians inside -----------------------------------------------------------------------

def arcsec_to_rad(value: float | None) -> float | None:
    """[rad] ``value`` [arcsec]; None stays None ("TBD")."""
    return None if value is None else value * ARCSEC_RAD


def rad_to_arcsec(value: float | None) -> float | None:
    """[arcsec] ``value`` [rad]; None stays None ("TBD")."""
    return None if value is None else value / ARCSEC_RAD


# -- the rules (pure) ----------------------------------------------------------------------------------------------

def probability_factor(probability: float) -> float:
    """``k`` with ``P(|X| <= k) = probability`` for a standard normal X: the
    two-sided factor of a value about one axis."""
    if not 0.0 < probability < 1.0:
        raise ValueError("the probability must be in (0, 1)")
    return NormalDist().inv_cdf(0.5 + probability / 2.0)


def cone_factor(probability: float) -> float:
    """``sqrt(-2 ln(1 - P))``: the radius, in standard deviations, that
    holds ``probability`` of a circular two-axis Gaussian (PE-10)."""
    if not 0.0 < probability < 1.0:
        raise ValueError("the probability must be in (0, 1)")
    return math.sqrt(-2.0 * math.log1p(-probability))


def mean_share(ratio: float) -> float:
    """The share of a sinusoid's amplitude in the mean of a window of
    ``ratio`` periods: the bound ``min(1, 1 / (pi ratio))`` of the exact
    ``|sin(pi ratio)| / (pi ratio)`` (PE-11)."""
    if ratio <= 0.0:
        raise ValueError("the window must be longer than zero")
    return 1.0 if math.pi * ratio <= 1.0 else 1.0 / (math.pi * ratio)


def _distance(start: float, width: float) -> float:
    """The largest value of a unit sinusoid over the window that starts at
    phase ``start`` and is ``width`` [rad] long, minus the window's mean."""
    mean = (math.cos(start) - math.cos(start + width)) / width
    holds_crest = (math.pi / 2.0 - start) % (2.0 * math.pi) <= width
    crest = 1.0 if holds_crest else max(math.sin(start), math.sin(start + width))
    return crest - mean


@lru_cache(maxsize=4096)
def relative_share(ratio: float) -> float:
    """The largest distance, in amplitudes, between a sinusoid and its mean
    over a window of ``ratio`` periods, over every phase and instant: exact,
    ``1 + |sin(pi ratio)| / (pi ratio)`` from one period on; below it the
    largest over :data:`_PHASES` phases, then refined around it by a
    golden-section search (to about 1e-12)."""
    if ratio <= 0.0:
        raise ValueError("the window must be longer than zero")
    if ratio >= 1.0:
        return 1.0 + abs(math.sin(math.pi * ratio)) / (math.pi * ratio)
    width = 2.0 * math.pi * ratio
    start = np.linspace(0.0, 2.0 * math.pi, _PHASES, endpoint=False)
    mean = (np.cos(start) - np.cos(start + width)) / width
    holds_crest = np.mod(math.pi / 2.0 - start, 2.0 * math.pi) <= width
    crest = np.where(holds_crest, 1.0, np.maximum(np.sin(start), np.sin(start + width)))
    distances = crest - mean  # the trough side is the same at the opposite phase
    best = int(np.argmax(distances))
    step = 2.0 * math.pi / _PHASES
    low, high = start[best] - step, start[best] + step
    golden = (math.sqrt(5.0) - 1.0) / 2.0
    for _ in range(30):
        left, right = high - golden * (high - low), low + golden * (high - low)
        if _distance(left, width) < _distance(right, width):
            low = left
        else:
            high = right
    return max(float(distances[best]), _distance((low + high) / 2.0, width))


def periodic_share(index: str, period_s: float, window_s: float) -> float:
    """The share of a periodic contributor in ``index`` for a window of
    ``window_s`` [s] (the module docstring's rule)."""
    if index == "absolute":
        return 1.0
    ratio = window_s / period_s
    if index == "mean":
        return mean_share(ratio)
    if index == "relative":
        return relative_share(ratio)
    return 2.0 * mean_share(ratio)  # drift and reproducibility


# -- the inputs, in radians ----------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Contributor:
    """A contributor in the engine's units: per axis its mean and its
    spread [rad] (an axis left out does not have one; None: "TBD")."""

    name: str
    kind: str  # "performance", "knowledge" or "both"
    behaviour: str
    distribution: str
    mean_rad: dict  # {axis: float | None}
    spread_rad: dict  # {axis: float | None}
    period_s: float | None = None  # [s] None: not known
    group: str = ""

    def enters(self, kind: str) -> bool:
        return self.kind in (kind, "both")


@dataclass(frozen=True)
class Requirement:
    """A requirement in the engine's units (None: "TBD")."""

    name: str
    index: str
    kind: str
    axis: str
    limit_rad: float | None
    probability: float | None
    interpretation: str = "temporal"
    window_s: float | None = None
    stability_s: float | None = None
    modes: tuple = ()

    def window_for(self, index: str) -> float | None:
        """[s] the window of ``index``: the stability time for relative
        when it is given, else the observation period."""
        if index == "relative" and self.stability_s is not None:
            return self.stability_s
        return self.window_s


def _known(value) -> float | None:
    return None if value is None else value.known


def inputs(pointing) -> tuple[str, list[Requirement], list[Contributor]]:
    """``(line_of_sight, requirements, contributors)`` of a
    ``schema.budgets.PointingConfig``, the angles turned from arcsec to
    radians: the one conversion of the inputs."""
    requirements = [Requirement(r.name, r.index, r.kind, r.axis, arcsec_to_rad(r.limit_arcsec.known),
                                r.probability.known, r.interpretation, _known(r.window_s), _known(r.stability_s),
                                tuple(r.modes)) for r in pointing.requirements]
    contributors = [Contributor(c.name, c.kind, c.behaviour, c.distribution,
                                {axis: arcsec_to_rad(v.known) for axis, v in c.mean_arcsec.items()},
                                {axis: arcsec_to_rad(v.known) for axis, v in c.spread_arcsec.items()},
                                _known(c.period_s), c.group) for c in pointing.contributors]
    return pointing.line_of_sight, requirements, contributors


# -- the results ---------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Term:
    """One contributor about one axis in one requirement's index: its share
    and what enters (the share times its mean and its standard deviation)
    [rad]. None: "TBD"."""

    contributor: str
    axis: str
    behaviour: str
    group: str
    share: float | None
    mean_rad: float | None
    std_rad: float | None
    rule: str


@dataclass(frozen=True)
class AxisSum:
    """The sum about one axis: the mean and the standard deviation [rad]
    (None: "TBD") and whether any contributor entered."""

    axis: str
    mean_rad: float | None
    std_rad: float | None
    entered: bool


@dataclass(frozen=True)
class RequirementResult:
    """One requirement's budget. For the line of sight, ``mean_rad`` is the
    length of the mean across it and ``std_rad`` the larger deviation of
    its two axes; ``factor`` is the factor of the probability that gives
    the value (two-sided normal, or the cone's)."""

    requirement: str
    index: str
    kind: str
    axis: str
    interpretation: str
    modes: tuple
    probability: float | None
    factor: float | None
    mean_rad: float | None
    std_rad: float | None
    value_rad: float | None
    limit_rad: float | None
    margin_rad: float | None
    status: str
    sums: tuple  # tuple[AxisSum]
    terms: tuple  # tuple[Term]
    notes: tuple  # tuple[str]: why a value is "TBD"


def _share(contributor: Contributor, requirement: Requirement, notes: list) -> float | None:
    share = SELECTION[contributor.behaviour][requirement.index]
    if share != WINDOW:
        return share
    if requirement.index == "absolute":
        return 1.0
    window = requirement.window_for(requirement.index)
    if contributor.period_s is None:
        notes.append(f"the period of {contributor.name} is TBD, so its share of the {requirement.index} index is TBD")
        return None
    if window is None:
        what = "stability time or observation period" if requirement.index == "relative" else "observation period"
        notes.append(f"the {what} of {requirement.name} is TBD, so the share of the periodic {contributor.name} "
                     "is TBD")
        return None
    return periodic_share(requirement.index, contributor.period_s, window)


def _term(contributor: Contributor, axis: str, share: float | None, notes: list) -> Term | None:
    """The term of ``contributor`` about ``axis``, or None when it does not
    act on that axis or does not enter the index (share 0)."""
    if axis not in contributor.mean_rad and axis not in contributor.spread_rad:
        return None
    if share == 0.0:
        return None
    mean = contributor.mean_rad.get(axis, 0.0)
    spread = contributor.spread_rad.get(axis, 0.0)
    if mean is None or spread is None:
        notes.append(f"{contributor.name}: a value about {axis} is TBD")
    std = None if spread is None else spread * STD_OF_SPREAD[contributor.distribution]
    return Term(contributor.name, axis, contributor.behaviour, contributor.group, share,
                None if share is None or mean is None else share * mean,
                None if share is None or std is None else share * std, RULES[contributor.behaviour])


def sum_terms(axis: str, terms: list) -> AxisSum:
    """The means linearly; within a correlated group the deviations
    linearly; the groups and the independent terms root-sum-square (PE-4)."""
    if any(term.mean_rad is None for term in terms):
        mean = None
    else:
        mean = math.fsum(term.mean_rad for term in terms)
    if any(term.std_rad is None for term in terms):
        std = None
    else:
        groups: dict = {}
        independent = []
        for term in terms:
            if term.group:
                groups[term.group] = groups.get(term.group, 0.0) + term.std_rad
            else:
                independent.append(term.std_rad)
        std = math.sqrt(math.fsum(value * value for value in independent + list(groups.values())))
    return AxisSum(axis, mean, std, bool(terms))


def _cross_axes(line_of_sight: str) -> tuple:
    return tuple(axis for axis in ("x", "y", "z") if axis != line_of_sight)


def evaluate(requirement: Requirement, contributors: list, line_of_sight: str = "") -> RequirementResult:
    """The budget of ``requirement`` (the module docstring's rules)."""
    notes: list = []
    cone = requirement.axis == "line_of_sight"
    if cone and line_of_sight not in ("x", "y", "z"):
        notes.append("the line of sight's body axis is not stated, so the half-cone value is TBD")
        axes: tuple = ()
    else:
        axes = _cross_axes(line_of_sight) if cone else (requirement.axis,)
    entering = [c for c in contributors if c.enters(requirement.kind)]
    terms: list = []
    sums = []
    shares: dict = {}
    for axis in axes:
        axis_terms = []
        for contributor in entering:
            if axis not in contributor.mean_rad and axis not in contributor.spread_rad:
                continue
            if contributor.name not in shares:
                shares[contributor.name] = _share(contributor, requirement, notes)
            term = _term(contributor, axis, shares[contributor.name], notes)
            if term is not None:
                axis_terms.append(term)
        terms += axis_terms
        sums.append(sum_terms(axis, axis_terms))
    probability = requirement.probability
    if probability is None:
        notes.append(f"the probability of {requirement.name} is TBD")
    factor = mean = std = value = None
    if axes:
        if cone:
            known = all(s.mean_rad is not None for s in sums)
            mean = math.hypot(*(s.mean_rad for s in sums)) if known else None
            std = max(s.std_rad for s in sums) if all(s.std_rad is not None for s in sums) else None
            factor = cone_factor(probability) if probability is not None else None
        else:
            mean = abs(sums[0].mean_rad) if sums[0].mean_rad is not None else None
            std = sums[0].std_rad
            factor = probability_factor(probability) if probability is not None else None
        if None not in (mean, std, factor):
            value = mean + factor * std
    limit = requirement.limit_rad
    if limit is None:
        notes.append(f"the limit of {requirement.name} is TBD")
    margin = None if value is None or limit is None else limit - value
    if axes and not terms:
        status = NO_CONTRIBUTOR
        notes.append(f"no contributor enters the {requirement.kind} {requirement.index} index of {requirement.name}")
    elif margin is None:
        status = TBD
    else:
        status = MET if margin >= 0.0 else NOT_MET
    return RequirementResult(requirement.name, requirement.index, requirement.kind, requirement.axis,
                             requirement.interpretation, requirement.modes, probability, factor, mean, std, value,
                             limit, margin, status, tuple(sums), tuple(terms), tuple(dict.fromkeys(notes)))


@dataclass
class PointingBudget:
    """A spacecraft's pointing error budget: one result per requirement, in
    the section's order. :meth:`rows` and :meth:`term_rows` give it in
    arcsec, for display and export (the boundary's other side)."""

    spacecraft: str
    line_of_sight: str = ""
    results: list = field(default_factory=list)  # list[RequirementResult]
    contributors: int = 0  # [-] contributors in the section

    @property
    def complete(self) -> bool:
        """Every requirement has a value and a margin."""
        return all(result.margin_rad is not None for result in self.results)

    def result(self, name: str) -> RequirementResult:
        return next(r for r in self.results if r.requirement == name)

    def rows(self) -> list[dict]:
        """One row per requirement, angles in arcsec (None: "TBD")."""
        return [{"requirement": r.requirement, "index": r.index, "kind": r.kind, "axis": r.axis,
                 "interpretation": r.interpretation, "probability": r.probability, "factor": r.factor,
                 "mean_arcsec": rad_to_arcsec(r.mean_rad), "std_arcsec": rad_to_arcsec(r.std_rad),
                 "value_arcsec": rad_to_arcsec(r.value_rad), "limit_arcsec": rad_to_arcsec(r.limit_rad),
                 "margin_arcsec": rad_to_arcsec(r.margin_rad), "status": r.status} for r in self.results]

    def term_rows(self) -> list[dict]:
        """One row per requirement, axis and contributor that enters it,
        angles in arcsec (None: "TBD")."""
        return [{"requirement": r.requirement, "contributor": t.contributor, "axis": t.axis,
                 "behaviour": t.behaviour, "group": t.group, "share": t.share,
                 "mean_arcsec": rad_to_arcsec(t.mean_rad), "std_arcsec": rad_to_arcsec(t.std_rad), "rule": t.rule}
                for r in self.results for t in r.terms]


def pointing_budget(sc) -> PointingBudget:
    """The :class:`PointingBudget` of spacecraft ``sc`` (empty without a
    ``budgets.pointing`` section)."""
    section = sc.budgets.pointing if sc.budgets is not None else None
    if section is None:
        return PointingBudget(sc.name)
    line_of_sight, requirements, contributors = inputs(section)
    return PointingBudget(sc.name, line_of_sight, [evaluate(r, contributors, line_of_sight) for r in requirements],
                          len(contributors))


# -- text and CSV --------------------------------------------------------------------------------------------------

def number(value: float | None, digits: int = 4) -> str:
    """``value`` with ``digits`` significant figures, or "TBD"."""
    return TBD if value is None else f"{value:.{digits}g}"


RESULT_HEADER = ("Requirement", "Index", "Kind", "Axis", "Probability [-]", "Mean [arcsec]", "Std [arcsec]",
                 "Value [arcsec]", "Limit [arcsec]", "Margin [arcsec]", "Status")


def result_cells(result: RequirementResult) -> tuple:
    """The cells of :data:`RESULT_HEADER` for ``result``."""
    return (result.requirement, result.index, result.kind, axis_label(result.axis), number(result.probability, 6),
            number(rad_to_arcsec(result.mean_rad)), number(rad_to_arcsec(result.std_rad)),
            number(rad_to_arcsec(result.value_rad)), number(rad_to_arcsec(result.limit_rad)),
            number(rad_to_arcsec(result.margin_rad)), result.status)


def axis_label(axis: str) -> str:
    return "line of sight" if axis == "line_of_sight" else axis


def report_lines(budget: PointingBudget) -> list[str]:
    """The budget as text: the results as a table, then for each
    requirement the contributors that enter it with their share and rule,
    and why a value is "TBD"."""
    lines = [f"{budget.spacecraft}: pointing error budget, {len(budget.results)} requirement(s), "
             f"{budget.contributors} contributor(s)" + ("" if budget.complete else "; incomplete (TBD below)")]
    if budget.line_of_sight:
        lines.append(f"  line of sight along body {budget.line_of_sight}")
    table = [RESULT_HEADER] + [result_cells(result) for result in budget.results]
    widths = [max(len(row[k]) for row in table) for k in range(len(RESULT_HEADER))]
    numeric = range(4, 10)
    for row in table:
        lines.append("  " + "  ".join(cell.rjust(w) if k in numeric else cell.ljust(w)
                                      for k, (cell, w) in enumerate(zip(row, widths))).rstrip())
    for result in budget.results:
        lines.append(f"  {result.requirement} ({result.kind} {result.index}, {axis_label(result.axis)}, "
                     f"{result.interpretation}):")
        for term in result.terms:
            lines.append(f"    {term.contributor} about {term.axis}: share {number(term.share)}, mean "
                         f"{number(rad_to_arcsec(term.mean_rad))} arcsec, std {number(rad_to_arcsec(term.std_rad))} "
                         f"arcsec{', group ' + term.group if term.group else ''} ({term.rule})")
        for note in result.notes:
            lines.append(f"    TBD: {note}" if result.status == TBD else f"    note: {note}")
    return lines


def csv_rows(budget: PointingBudget) -> list[tuple]:
    """The budget as CSV rows: the results, a blank row, the terms."""
    results = budget.rows()
    terms = budget.term_rows()
    rows: list = [tuple(results[0]) if results else ("no requirement",)]
    rows += [tuple(row.values()) for row in results]
    rows.append(())
    rows.append(tuple(terms[0]) if terms else ("no contributor enters a requirement",))
    rows += [tuple(row.values()) for row in terms]
    return rows


# -- the scenario's sensors as contributors (option B) -------------------------------------------------------------

#: The sensor kinds Add Scenario Sensors reads, with the parameter that holds their noise.
SENSOR_NOISE = {"star_tracker": "noise_arcsec", "imu": "gyro_noise_rad_s", "coarse_sun_sensor": "noise_std"}
#: [deg] The sun angle at which a sun sensor's output noise is turned into an angle: the angle the device
#: catalog derives its sun sensors' output noise at (engine.device_catalog, the SS200 and nanoSSOC entries).
SUN_SENSOR_REFERENCE_ANGLE_DEG = 45.0


def _noise_source(sc, sensor, key: str) -> tuple:
    """``(value, source)`` of a sensor's noise parameter: the catalog
    product its name names when the value is that product's, else the
    scenario; ``(None, reason)`` when the scenario does not give it."""
    from .. import idm_devices

    where = f"{sc.name}.sensors[{sensor.name}].params.{key}"
    value = sensor.params.get(key)
    if value is None:
        return None, f"TBD: {where} is not given (the run models no noise)"
    product = idm_devices.catalog_product(sensor.name, sensor.kind)
    if product is not None and product.params.get(key) == value:
        return float(value), f"catalog: {product.display_name}, {product.source_url}"
    return float(value), f"scenario: {where}"


def sensor_contributor(sc, sensor):
    """The knowledge contributor of a star tracker, gyroscope or sun sensor
    of ``sc`` (a ``schema.budgets.PointingContributorConfig``, arcsec), or
    None for another kind (PE-15):

    * a star tracker: its 1-sigma ``noise_arcsec`` about each axis;
    * a sun sensor: its output noise as an angle, ``noise_std /
      sin(45 deg)`` [rad] (:data:`SUN_SENSOR_REFERENCE_ANGLE_DEG`), about
      each axis;
    * a gyroscope: "TBD" about each axis, its rate noise in the source: the
      angle error it gives depends on the time between attitude fixes,
      which the scenario does not state.
    """
    from ..schema.budgets import POINTING_AXES, PointingContributorConfig, SourcedValue

    key = SENSOR_NOISE.get(sensor.kind)
    if key is None:
        return None
    value, source = _noise_source(sc, sensor, key)
    if sensor.kind == "imu":
        if value is not None:
            source = (f"TBD: rate noise {value:g} rad/s ({source}); the angle error it gives depends on the time "
                      "between attitude fixes")
        value = None
    elif sensor.kind == "coarse_sun_sensor" and value is not None:
        angle = math.sin(math.radians(SUN_SENSOR_REFERENCE_ANGLE_DEG))
        source = (f"{source}; as an angle: {value:g} / sin({SUN_SENSOR_REFERENCE_ANGLE_DEG:g} deg), the catalog's "
                  "reference sun angle")
        value = rad_to_arcsec(value / angle)
    spread = {axis: SourcedValue(value, source) for axis in POINTING_AXES}
    return PointingContributorConfig(f"{sensor.name} noise", kind="knowledge", behaviour="random",
                                     distribution="gaussian", spread_arcsec=spread, sensor=sensor.name)


def sensor_contributors(sc, pointing) -> list:
    """The contributors of ``sc``'s star trackers, gyroscopes and sun
    sensors that ``pointing`` does not hold yet (by the sensor's name),
    each with a name not taken."""
    have = {c.sensor for c in pointing.contributors if c.sensor}
    names = {c.name for c in pointing.contributors}
    added = []
    for sensor in sc.sensors:
        if sensor.name in have:
            continue
        contributor = sensor_contributor(sc, sensor)
        if contributor is None:
            continue
        stem, number_ = contributor.name, 2
        while contributor.name in names:
            contributor.name = f"{stem} {number_}"
            number_ += 1
        names.add(contributor.name)
        added.append(contributor)
    return added
