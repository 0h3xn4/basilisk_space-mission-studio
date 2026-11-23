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

"""Requirements on a Monte Carlo batch's outcomes, and the probability of
not meeting them (decisions MC-4 to MC-6 of the Monte Carlo plan).

A requirement (``schema.scenario.MonteCarloRequirementConfig``) names one
outcome of one spacecraft and a limit: ``at_least`` or ``at_most``, in the
outcome's unit. For each requirement the batch gives:

* N, the runs evaluated: the successful runs that recorded the outcome and
  the crashed runs. A successful run without the outcome is "not
  evaluated" and is left out of N (it did not record what the outcome is
  read from).
* k, the runs that do not meet it. A crashed run has no outcome and
  counts as not meeting every requirement (MC-6, the conservative
  reading); the count of crashed runs among the k is kept apart.
* the estimate of the probability of not meeting it, k/N, and its exact
  one-sided upper bound at the requirement's confidence C: the model
  ``monte_carlo.probability_bound`` (``config.models``), Clopper and
  Pearson's (Biometrika 26(4), 1934, pp. 404-413), by
  :func:`clopper_pearson_upper`.
* with an allowed probability (``max_probability``), the verdict: "met"
  when the upper bound is at or below it, else "not shown".

The verdicts are computed when the batch is read, from the outcomes the
summary keeps and the requirements it was run with, so an opened batch
reads the same later. Basilisk-free, with no SciPy.

A thermal Monte Carlo is judged the same way against its nodes' limits
(Monte Carlo plan B4, :func:`node_limits`): for each node with an
operating or survival range, the runs that leave it, the estimate and, at
the confidence the thermal Monte Carlo gives, the same upper bound. These
are counted when the batch is solved, from each run's own temperatures,
and kept in the summary (``node_limits``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..schema.scenario import MONTE_CARLO_OUTCOME_TITLES, MONTE_CARLO_OUTCOME_UNITS, monte_carlo_outcome_key

BOUND_CHOICE = "monte_carlo.probability_bound"
# Verdicts: the bound at or below the allowed probability, or not.
MET = "met"
NOT_SHOWN = "not shown"
# A run's "meets all requirements" cell.
YES, NO, NOT_EVALUATED = "yes", "no", "not evaluated"
# Bisection steps: each halves the interval of p, which starts at [0, 1];
# 60 halvings leave less than 1e-18, below the resolution of a float near
# any bound of interest. The loop also stops when the midpoint no longer moves.
_BISECTION_STEPS = 200


def binomial_cdf(k: int, n: int, p: float) -> float:
    """The probability of ``k`` or fewer successes in ``n`` independent
    trials of probability ``p``: sum over i = 0..k of C(n, i) p^i (1 - p)^(n - i).

    The largest term of the sum is at m, the binomial's mode floor((n + 1) p),
    or at k when the mode is above k. It is computed in logarithms
    (``math.lgamma``), so no factorial overflows; the sum then goes down from
    m and up from m to k, each term from its neighbour by the ratio of
    successive binomial terms, and stops when a term no longer changes it."""
    if k >= n or p <= 0.0:
        return 1.0
    if k < 0 or p >= 1.0:
        return 0.0
    m = min(k, int((n + 1) * p))
    peak = math.exp(math.lgamma(n + 1) - math.lgamma(m + 1) - math.lgamma(n - m + 1)
                    + m * math.log(p) + (n - m) * math.log1p(-p))
    total = peak
    odds = (1.0 - p) / p
    term = peak
    for i in range(m, 0, -1):  # term(i - 1) = term(i) * i / (n - i + 1) * (1 - p) / p
        term *= i / (n - i + 1) * odds
        total += term
        if term <= total * 1e-17:
            break
    term = peak
    for i in range(m, k):  # term(i + 1) = term(i) * (n - i) / (i + 1) * p / (1 - p)
        term *= (n - i) / (i + 1) / odds
        total += term
        if term <= total * 1e-17:
            break
    return min(total, 1.0)


def clopper_pearson_upper(k: int, n: int, confidence: float) -> float:
    """The exact one-sided upper bound, at ``confidence``, on the
    probability of an event seen ``k`` times in ``n`` independent trials
    (Clopper and Pearson, 1934): the p at which :func:`binomial_cdf` of
    (k, n, p) equals 1 - ``confidence``, by bisection. 1 for k = n."""
    if not (isinstance(n, int) and n >= 1 and isinstance(k, int) and 0 <= k <= n):
        raise ValueError(f"the bound needs 0 <= k <= n and n >= 1, got k={k!r}, n={n!r}")
    if not 0.0 < confidence < 1.0:
        raise ValueError(f"the confidence must be between 0 and 1 (both excluded), got {confidence!r}")
    if k == n:
        return 1.0
    alpha = 1.0 - confidence
    low, high = 0.0, 1.0  # binomial_cdf falls from 1 at p = 0 to 0 at p = 1
    for _ in range(_BISECTION_STEPS):
        middle = 0.5 * (low + high)
        if middle in (low, high):
            break
        if binomial_cdf(k, n, middle) > alpha:
            low = middle
        else:
            high = middle
    return high


# The bound of each model of BOUND_CHOICE (config.models).
_BOUNDS = {"clopper_pearson": clopper_pearson_upper}


@dataclass(frozen=True)
class RequirementResult:
    """One requirement judged on one batch."""

    name: str
    spacecraft: str
    outcome: str
    unit: str
    at_least: float | None
    at_most: float | None
    confidence: float
    max_probability: float | None
    evaluated: int  # N: the successful runs with the outcome, and the crashed runs
    not_met: int  # k, crashed runs included
    crashed: int  # of the k, the crashed runs
    not_evaluated: int  # successful runs without the outcome (not in N)
    estimate: float | None  # k / N; None when N = 0
    upper_bound: float | None  # at ``confidence``; None when N = 0
    not_met_runs: tuple[int, ...] = ()  # the runs of the k, crashed ones included

    @property
    def verdict(self) -> str:
        """``MET``, ``NOT_SHOWN``, or "" without an allowed probability."""
        if self.max_probability is None:
            return ""
        if self.upper_bound is None:
            return NOT_SHOWN
        return MET if self.upper_bound <= self.max_probability else NOT_SHOWN

    def limit_text(self) -> str:
        """``"at least 400 km"`` or ``"at most 2 m/s"``."""
        word, value = ("at least", self.at_least) if self.at_least is not None else ("at most", self.at_most)
        unit = "" if self.unit == "-" else f" {self.unit}"
        return f"{word} {value:g}{unit}"

    def outcome_title(self) -> str:
        return MONTE_CARLO_OUTCOME_TITLES.get(self.outcome, self.outcome)


def _meets(requirement: dict, value: float) -> bool:
    if requirement.get("at_least") is not None:
        return value >= float(requirement["at_least"])
    return value <= float(requirement["at_most"])


def evaluate(batch) -> list[RequirementResult]:
    """Each of ``batch.requirements`` judged on the batch's outcomes
    (module docstring). Crashed runs are ``batch.failed``."""
    bound = _BOUNDS[getattr(batch, "probability_bound", "clopper_pearson")]
    crashed = [int(run) for run in batch.failed]
    results = []
    for requirement in batch.requirements:
        key = monte_carlo_outcome_key(requirement["spacecraft"], requirement["outcome"])
        failing, skipped, evaluated = [], 0, 0
        for k, run in enumerate(batch.runs):
            row = batch.outcomes[k] if k < len(batch.outcomes) else {}
            value = row.get(key)
            if value is None or not math.isfinite(value):
                skipped += 1
                continue
            evaluated += 1
            if not _meets(requirement, value):
                failing.append(int(run))
        n = evaluated + len(crashed)
        not_met = len(failing) + len(crashed)
        confidence = float(requirement["confidence"])
        allowed = requirement.get("max_probability")
        results.append(RequirementResult(
            str(requirement["name"]), str(requirement["spacecraft"]), str(requirement["outcome"]),
            MONTE_CARLO_OUTCOME_UNITS.get(requirement["outcome"], "-"),
            None if requirement.get("at_least") is None else float(requirement["at_least"]),
            None if requirement.get("at_most") is None else float(requirement["at_most"]),
            confidence, None if allowed is None else float(allowed), n, not_met, len(crashed), skipped,
            not_met / n if n else None, bound(not_met, n, confidence) if n else None,
            tuple(sorted(failing + crashed))))
    return results


def run_verdicts(batch) -> dict[int, str]:
    """Each run's "meets all requirements": :data:`YES`, :data:`NO` (a
    crashed run, or one requirement not met) or :data:`NOT_EVALUATED` (none
    failed, but one or more could not be judged). Empty without
    requirements."""
    if not batch.requirements:
        return {}
    verdicts = {int(run): NO for run in batch.failed}
    for k, run in enumerate(batch.runs):
        row = batch.outcomes[k] if k < len(batch.outcomes) else {}
        verdict = YES
        for requirement in batch.requirements:
            value = row.get(monte_carlo_outcome_key(requirement["spacecraft"], requirement["outcome"]))
            if value is None or not math.isfinite(value):
                verdict = NOT_EVALUATED if verdict == YES else verdict
            elif not _meets(requirement, value):
                verdict = NO
        verdicts[int(run)] = verdict
    return verdicts


def not_shown_met(results: list[RequirementResult]) -> list[RequirementResult]:
    """The requirements with an allowed probability that the batch does not
    show met: the command line then exits with status 5 (decision MC-10)."""
    return [result for result in results if result.verdict == NOT_SHOWN]


def _probability(value: float | None) -> str:
    return "" if value is None else f"{value:.4g}"


TABLE_HEADER = ("Requirement", "Outcome", "Limit", "Evaluated", "Not met", "Of which crashed", "Not evaluated",
                "Estimate [-]", "Upper bound [-]", "Confidence [-]", "Allowed [-]", "Verdict")


def table_rows(results: list[RequirementResult], several_spacecraft: bool = True) -> list[tuple[str, ...]]:
    """The Requirements table, one text row per requirement (the command
    line and the Results page)."""
    rows = []
    for r in results:
        outcome = f"{r.spacecraft} {r.outcome_title().lower()}" if several_spacecraft else r.outcome_title()
        if r.outcome == "run_length":
            outcome = r.outcome_title()
        rows.append((r.name, outcome, r.limit_text(), str(r.evaluated), str(r.not_met), str(r.crashed),
                     str(r.not_evaluated), _probability(r.estimate), _probability(r.upper_bound),
                     f"{r.confidence:g}", "" if r.max_probability is None else f"{r.max_probability:g}",
                     r.verdict or "no allowed probability"))
    return rows


# -- A thermal batch against its nodes' limits (Monte Carlo plan B4) ----------

#: A node's ranges, by name, and the node field that holds each.
NODE_RANGES = (("operating", "operating_c"), ("survival", "survival_c"))


@dataclass(frozen=True)
class NodeLimitResult:
    """One range of one thermal node judged on a thermal Monte Carlo
    (decisions MC-22 and MC-23): of the N runs evaluated (the runs solved
    and the failed runs), the k that leave the range at any sample (a
    failed run counts as leaving it, shown apart, as a crashed run counts
    as not meeting a requirement, MC-11); the estimate k/N and, with a
    confidence, the exact upper bound (:func:`clopper_pearson_upper`)."""

    node: str
    range: str  # "operating" or "survival"
    low_c: float  # [degC]
    high_c: float  # [degC]
    evaluated: int  # N
    outside: int  # k, failed runs included
    failed: int  # of the k, the failed runs
    outside_runs: tuple[int, ...]  # the runs of the k, failed ones included
    estimate: float  # k / N
    confidence: float | None = None
    upper_bound: float | None = None  # at ``confidence``; None without one

    def to_dict(self) -> dict:
        return {"node": self.node, "range": self.range, "low_c": self.low_c, "high_c": self.high_c,
                "evaluated": self.evaluated, "outside": self.outside, "failed": self.failed,
                "outside_runs": list(self.outside_runs), "estimate": self.estimate, "confidence": self.confidence,
                "upper_bound": self.upper_bound}

    @classmethod
    def from_dict(cls, row: dict) -> NodeLimitResult:
        """A row as :meth:`to_dict` wrote it; raises ``KeyError``,
        ``TypeError`` or ``ValueError`` for anything else."""
        confidence, bound = row.get("confidence"), row.get("upper_bound")
        return cls(str(row["node"]), str(row["range"]), float(row["low_c"]), float(row["high_c"]),
                   int(row["evaluated"]), int(row["outside"]), int(row["failed"]),
                   tuple(int(run) for run in row["outside_runs"]), float(row["estimate"]),
                   None if confidence is None else float(confidence), None if bound is None else float(bound))


def node_limits(limits: dict, extremes: dict, runs: list[int], failed: list[int], confidence: float | None,
                bound: str = "clopper_pearson") -> list[NodeLimitResult]:
    """Each node's operating and survival range judged on a thermal batch
    (:class:`NodeLimitResult`). ``limits`` is ``{node: {"operating": [low,
    high] or None, "survival": ...}}`` [degC], in the thermal model's
    order; ``extremes[node]`` the (lowest, highest) temperature [degC] of
    each run of ``runs``, in that order. A run leaves a range when its
    lowest temperature is below the range's low end or its highest above
    its high end. The bound is the model ``bound`` of
    ``monte_carlo.probability_bound`` at ``confidence``; without a
    confidence, counts and the estimate only."""
    upper = _BOUNDS[bound]
    failed = sorted(int(run) for run in failed)
    results = []
    for node, ranges in limits.items():
        for name, _field in NODE_RANGES:
            limit = ranges.get(name)
            if limit is None or node not in extremes:
                continue
            low, high = float(limit[0]), float(limit[1])
            outside = [int(run) for run, (lowest, highest) in zip(runs, extremes[node])
                       if lowest < low or highest > high]
            n = len(runs) + len(failed)
            k = len(outside) + len(failed)
            results.append(NodeLimitResult(
                str(node), name, low, high, n, k, len(failed), tuple(sorted(outside + failed)),
                k / n if n else 0.0, None if confidence is None else float(confidence),
                upper(k, n, float(confidence)) if confidence is not None and n else None))
    return results


NODE_LIMITS_HEADER = ("Node", "Range", "Low [degC]", "High [degC]", "Evaluated", "Outside", "Of which failed",
                      "Estimate [-]", "Upper bound [-]", "Confidence [-]")


def node_limit_rows(results: list[NodeLimitResult]) -> list[tuple[str, ...]]:
    """The node limits table, one text row per node and range (the command
    line and the Results page)."""
    return [(r.node, r.range, f"{r.low_c:g}", f"{r.high_c:g}", str(r.evaluated), str(r.outside), str(r.failed),
             _probability(r.estimate), _probability(r.upper_bound),
             "" if r.confidence is None else f"{r.confidence:g}") for r in results]
