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

"""What a Monte Carlo batch's outcomes look like, and which drawn values
drive them (Monte Carlo plan B3 and B2).

**Outcome statistics** (B3). Per outcome, over the successful runs that
recorded it: N, the minimum, the percentiles the project names
(``monte_carlo.percentiles``), the maximum, and the empirical
distribution function, F(x) = (runs at or below x) / N, a step function
that ends at 1 (:func:`ecdf`). The percentiles are computed by the
model ``monte_carlo.percentile_method`` (``config.models``): ``linear``,
NumPy's default, Hyndman and Fan's definition 7 (The American
Statistician 50(4), 1996, pp. 361-365).

**Sensitivity** (B2). The correlation of each drawn value with each
outcome, by the model ``monte_carlo.sensitivity_measure``: ``spearman``
(the default; the rank correlation, C. Spearman, American Journal of
Psychology 15(1), 1904, pp. 72-101) or ``pearson`` (the correlation of
the values themselves). Ties get the mean of the ranks they share
(:func:`average_ranks`). Pairwise: a run counts for a pair when it
recorded both values, so a crashed run (it has no outcome) and a run
without that outcome are left out of that pair only; N is kept per
pair. A column that does not vary, or a pair with fewer than
:data:`MIN_PAIRS` runs, has no correlation (None, shown as "—"), never
NaN.

The batch keeps the choices it was run with (the summary's
``sensitivity_measure``, ``percentile_method`` and ``percentiles``), as it
keeps its spread statistic, so an opened batch reads the same later.

NumPy only: no SciPy, no Basilisk, no Qt. The GUI computes
:func:`insight` in a worker thread (a batch can hold 100 000 runs).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

SENSITIVITY_CHOICE = "monte_carlo.sensitivity_measure"
PERCENTILE_CHOICE = "monte_carlo.percentile_method"
PERCENTILES = "monte_carlo.percentiles"
# A pair needs this many runs for a correlation: two points always lie on a line.
MIN_PAIRS = 3
NO_VALUE = "—"  # a cell without a value: a correlation of a column that does not vary, or of too few runs
# The prefix of an operations batch's outcomes among its drawn values (operations.robustness).
_OPERATIONS_OUTCOME = "outcome: "


@dataclass(frozen=True)
class Column:
    """One value per successful run of the batch (``batch.runs`` order),
    NaN where a run has none. ``label`` carries its unit: "sat-1 drag
    coefficient [-]"."""

    label: str
    values: np.ndarray

    @property
    def unit(self) -> str:
        """The unit in the label's last brackets ("-" when it has none)."""
        head, bracket, tail = self.label.rpartition(" [")
        return tail[:-1] if bracket and tail.endswith("]") else "-"

    @property
    def name(self) -> str:
        """The label without its unit."""
        head, bracket, tail = self.label.rpartition(" [")
        return head if bracket and tail.endswith("]") else self.label


def number_text(value: float | None) -> str:
    """A table cell (the Monte Carlo view, the command line, the batch
    report): 6 significant figures; :data:`NO_VALUE` for no value."""
    return NO_VALUE if value is None or not np.isfinite(value) else f"{value:.6g}"


def percentile_title(percentile: float) -> str:
    """A percentile's column heading: "P5" for the 5th."""
    return f"P{percentile:g}"


def choices(scenario=None) -> dict:
    """The three choices in effect for ``scenario`` (its project
    configuration, else the defaults), as a batch keeps them."""
    from ..config import registry

    return {"sensitivity_measure": registry.value(SENSITIVITY_CHOICE, scenario),
            "percentile_method": registry.value(PERCENTILE_CHOICE, scenario),
            "percentiles": [float(p) for p in registry.value(PERCENTILES, scenario)]}


# -- the columns of a batch ----------------------------------------------------------------------


def _column(label: str, rows: list[dict], key: str | None = None) -> Column:
    key = label if key is None else key
    return Column(label, np.array([float(row.get(key, math.nan)) if row is not None else math.nan for row in rows],
                                  dtype=float))


def input_columns(batch) -> list[Column]:
    """The values each successful run drew, one column per drawn value, in
    the order the runs list them. An operations batch's outcomes (its drawn
    values named "outcome: ...") are not inputs."""
    labels: list[str] = []
    for row in batch.drawn:
        labels += [label for label in row if label not in labels and not label.startswith(_OPERATIONS_OUTCOME)]
    rows = [batch.drawn[k] if k < len(batch.drawn) else {} for k in range(len(batch.runs))]
    return [_column(label, rows) for label in labels]


def outcome_columns(batch) -> list[Column]:
    """The outcomes of each successful run, one column each:

    * an orbit batch: per spacecraft, where the run ended against the batch
      mean (radial, along-track, cross-track [km], as the Runs table, to
      the millimetre), then the Overview figures it recorded (``outcomes``,
      plan A1);
    * a thermal batch: per node, its lowest and highest temperature [degC];
    * an operations batch: its outcomes among the drawn values, then per
      profile its lowest and highest value.
    """
    from . import monte_carlo_results as mcr

    if not batch.runs:
        return []
    if batch.kind == "thermal":
        columns = []
        for node, values in batch.temperatures_c.items():
            columns += [Column(f"{node} min [degC]", values.min(axis=1).astype(float)),
                        Column(f"{node} max [degC]", values.max(axis=1).astype(float))]
        return columns
    if batch.kind == "operations":
        labels: list[str] = []
        for row in batch.drawn:
            labels += [label for label in row if label not in labels and label.startswith(_OPERATIONS_OUTCOME)]
        rows = [batch.drawn[k] if k < len(batch.drawn) else {} for k in range(len(batch.runs))]
        columns = [_column(label.removeprefix(_OPERATIONS_OUTCOME), rows, label) for label in labels]
        for name, values in batch.profiles.items():
            unit = batch.profile_units.get(name, "-")
            columns += [Column(f"{name} lowest [{unit}]", values.min(axis=1).astype(float)),
                        Column(f"{name} highest [{unit}]", values.max(axis=1).astype(float))]
        return columns
    columns = []
    for name in batch.spacecraft:
        # [km] to the millimetre: below it an offset is rounding noise (runs that do not differ at all), as the
        # tiles read it (monte_carlo_results.format_km), and noise must not show as a correlation.
        final = np.round(mcr.offsets(batch.positions[name], batch.velocities[name])[:, -1, :] / 1e3, 6) + 0.0
        columns += [Column(f"{name} final {component.replace('_', '-')} offset [km]", final[:, index].copy())
                    for index, component in enumerate(mcr.OFFSET_COMPONENTS)]
    keys: list[str] = []
    for name in batch.spacecraft or [""]:
        keys += [key for key in mcr._outcome_keys(batch, name) if key not in keys]
    rows = [batch.outcomes[k] if k < len(batch.outcomes) else None for k in range(len(batch.runs))]
    columns += [_column(mcr.outcome_label(key, batch.outcome_units.get(key, "-")), rows, key) for key in keys]
    return columns


# -- outcome statistics (B3) ---------------------------------------------------------------------


@dataclass(frozen=True)
class OutcomeStatistics:
    """One outcome over the runs that recorded it: N, the minimum, each
    percentile (in the order of ``percentiles`` [%]), the maximum; the
    extremes and percentiles are None when N is 0. ``label`` is the
    column's (with its unit), ``name`` and ``unit`` its two parts."""

    label: str
    name: str
    unit: str
    n: int
    minimum: float | None
    percentiles: tuple[float, ...]
    values: tuple[float | None, ...]
    maximum: float | None


def shown_percentiles(percentiles) -> tuple[float, ...]:
    """The percentiles [%] to show: each once, in ascending order."""
    return tuple(sorted({float(p) for p in percentiles}))


def outcome_statistics(column: Column, percentiles, method: str = "linear") -> OutcomeStatistics:
    """``column``'s statistics over its finite values; the percentiles by
    ``numpy.percentile(values, percentiles, method=method)``."""
    shown = shown_percentiles(percentiles)
    values = column.values[np.isfinite(column.values)]
    if values.size == 0:
        return OutcomeStatistics(column.label, column.name, column.unit, 0, None, shown, tuple(None for _ in shown),
                                 None)
    found = np.percentile(values, shown, method=method) if shown else np.zeros(0)
    return OutcomeStatistics(column.label, column.name, column.unit, int(values.size), float(values.min()), shown,
                             tuple(float(v) for v in found), float(values.max()))


def ecdf(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The empirical distribution function of the finite ``values``: each
    distinct value x, ascending, and the fraction of values at or below it
    (a step that rises at x). The last fraction is exactly 1; empty arrays
    for no value."""
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return np.zeros(0), np.zeros(0)
    distinct, counts = np.unique(values, return_counts=True)
    fraction = np.cumsum(counts) / values.size
    fraction[-1] = 1.0  # exactly: the sum of the counts is the size
    return distinct, fraction


# -- sensitivity (B2) ----------------------------------------------------------------------------


def average_ranks(values: np.ndarray) -> np.ndarray:
    """The ranks of ``values`` (1 for the smallest), ties given the mean of
    the ranks they share: [10, 20, 20, 30] ranks as [1, 2.5, 2.5, 4]."""
    values = np.asarray(values, dtype=float)
    n = values.size
    if n == 0:
        return np.zeros(0)
    order = np.argsort(values, kind="stable")
    ordered = values[order]
    starts = np.empty(n, dtype=bool)
    starts[0] = True
    starts[1:] = ordered[1:] != ordered[:-1]
    first = np.flatnonzero(starts)  # each group's first position (0-based) in the sorted values
    end = np.append(first[1:], n)  # one past its last
    mean_rank = (first + 1 + end) / 2.0  # the mean of ranks first + 1 .. end
    ranks = np.empty(n, dtype=float)
    ranks[order] = mean_rank[np.cumsum(starts) - 1]
    return ranks


def _constant(values: np.ndarray) -> bool:
    return values.size == 0 or bool(values.min() == values.max())


def _pearson(x: np.ndarray, y: np.ndarray) -> float | None:
    if _constant(x) or _constant(y):
        return None
    dx, dy = x - x.mean(), y - y.mean()
    denominator = math.sqrt(float(dx @ dx) * float(dy @ dy))
    if denominator == 0.0 or not math.isfinite(denominator):
        return None
    return max(-1.0, min(1.0, float(dx @ dy) / denominator))


def correlation(x: np.ndarray, y: np.ndarray, measure: str = "spearman") -> tuple[float | None, int]:
    """(the correlation of ``x`` and ``y`` by ``measure``, the runs N it
    used): pairwise over the runs where both are finite. None when N is
    below :data:`MIN_PAIRS` or either does not vary there."""
    if measure not in ("spearman", "pearson"):
        raise ValueError(f"unknown sensitivity measure {measure!r}")
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    both = np.isfinite(x) & np.isfinite(y)
    n = int(both.sum())
    if n < MIN_PAIRS:
        return None, n
    x, y = x[both], y[both]
    if measure == "spearman":
        if _constant(x) or _constant(y):
            return None, n
        return _pearson(average_ranks(x), average_ranks(y)), n
    return _pearson(x, y), n


@dataclass(frozen=True)
class Sensitivity:
    """One drawn value against one outcome: the correlation (None: "—")
    over the N runs that recorded both."""

    input_label: str
    outcome_label: str
    value: float | None
    n: int


def sensitivities(inputs: list[Column], outputs: list[Column], measure: str = "spearman") -> list[Sensitivity]:
    """Every drawn value against every outcome, sorted by the correlation's
    size, the largest first (whatever its sign); the pairs without one
    last, in the columns' order."""
    if measure not in ("spearman", "pearson"):
        raise ValueError(f"unknown sensitivity measure {measure!r}")
    # A column that every run has (the usual case) is ranked (Spearman's) and centred once, with its norm;
    # a pair of two such columns is then one dot product. A pair with a missing value is worked out
    # over the runs it keeps (correlation()).
    prepared: dict[int, tuple[np.ndarray, float]] = {}
    for column in inputs + outputs:
        values = column.values
        if values.size >= MIN_PAIRS and np.isfinite(values).all() and not _constant(values):
            ranked = average_ranks(values) if measure == "spearman" else values
            centred = ranked - ranked.mean()
            norm = math.sqrt(float(centred @ centred))
            if norm > 0.0:
                prepared[id(column)] = (centred, norm)
    rows = []
    for x in inputs:
        for y in outputs:
            if id(x) in prepared and id(y) in prepared and x.values.size == y.values.size:
                (dx, nx), (dy, ny) = prepared[id(x)], prepared[id(y)]
                value, n = max(-1.0, min(1.0, float(dx @ dy) / (nx * ny))), int(x.values.size)
            else:
                value, n = correlation(x.values, y.values, measure)
            rows.append(Sensitivity(x.label, y.label, value, n))
    order = sorted(range(len(rows)), key=lambda k: (rows[k].value is None,
                                                    -abs(rows[k].value) if rows[k].value is not None else 0.0, k))
    return [rows[k] for k in order]


# -- both, for a batch ---------------------------------------------------------------------------


@dataclass
class Insight:
    """A batch's outcome statistics and sensitivity, with the columns they
    come from (the plots draw them), by the batch's own choices."""

    statistics: list[OutcomeStatistics] = field(default_factory=list)
    sensitivity: list[Sensitivity] = field(default_factory=list)
    inputs: dict[str, Column] = field(default_factory=dict)
    outcomes: dict[str, Column] = field(default_factory=dict)
    measure: str = "spearman"
    method: str = "linear"
    percentiles: tuple[float, ...] = ()


def insight(batch) -> Insight:
    """:class:`Insight` of ``batch``, by the sensitivity measure, the
    percentile method and the percentiles it keeps."""
    inputs, outcomes = input_columns(batch), outcome_columns(batch)
    shown = shown_percentiles(batch.percentiles)
    return Insight([outcome_statistics(column, shown, batch.percentile_method) for column in outcomes],
                   sensitivities(inputs, outcomes, batch.sensitivity_measure),
                   {column.label: column for column in inputs}, {column.label: column for column in outcomes},
                   batch.sensitivity_measure, batch.percentile_method, shown)


# -- the tables as text (the command line and the batch report, plan B5 and B7) ----------------------


def statistics_table(insight: Insight) -> tuple[list[str], list[tuple[str, ...]]]:
    """(headings, rows) of the outcome statistics, the Statistics tab's
    columns and cell text, each outcome's full label."""
    headers = (["Outcome", "Unit", "N", "Minimum"] + [percentile_title(p) for p in insight.percentiles]
               + ["Maximum"])
    rows = [(stat.name, stat.unit, str(stat.n), *(number_text(v) for v in (stat.minimum, *stat.values, stat.maximum)))
            for stat in insight.statistics]
    return headers, rows


def sensitivity_table(insight: Insight, limit: int | None = None) -> tuple[list[str], list[tuple[str, ...]]]:
    """(headings, rows) of the sensitivity, the Sensitivity tab's columns
    and cell text, largest first; at most ``limit`` rows when given."""
    from ..config import models

    title = models.model(SENSITIVITY_CHOICE, insight.measure).title
    pairs = insight.sensitivity if limit is None else insight.sensitivity[:limit]
    return (["Drawn value", "Outcome", f"{title} [-]", "N"],
            [(pair.input_label, pair.outcome_label, number_text(pair.value), str(pair.n)) for pair in pairs])
