# Monte Carlo statistics

How a Monte Carlo batch's spread is measured: each run's offset from the
mean of all runs, and the 1-sigma of those offsets. How a batch judges a
requirement on its runs' outcomes: the probability of not meeting it,
with an exact upper bound. And how it describes its outcomes (minimum,
percentiles, maximum, the empirical distribution) and which drawn values
go with them (the sensitivity). Code:
`spacemissionstudio/engine/monte_carlo_results.py`,
`spacemissionstudio/engine/monte_carlo_requirements.py` and
`spacemissionstudio/engine/monte_carlo_statistics.py`; the models are
declared in `spacemissionstudio/config/models.py` (see
[Selectable models](README.md#selectable-models)).

## The offsets

At each sample, R points from the central body to the runs' mean
position, W along the mean orbit's angular momentum, and S = W x R. A
run's offsets, in metres:

- **radial:** its distance from the central body minus the runs' mean
  distance;
- **along-track:** the arc, at that mean distance, by which it leads (+)
  or trails (-) R in the R-S plane;
- **cross-track:** the arc out of that plane.

Arcs, not straight lines: a straight-line frame would turn a large
along-track spread into a false radial one, as the orbit curves away from
the chord.

## The spread: `spread_statistic`

The spread is the standard deviation of each offset over the N runs that
succeeded, at each sample. Which standard deviation is a choice,
`monte_carlo.spread_statistic`, set in the project configuration like any
parameter:

```yaml
parameters:
  monte_carlo.spread_statistic: sample   # [-] population (default) or sample
```

| Model | Name | Formula | Use it when |
|---|---|---|---|
| Population standard deviation | `population` (default) | sqrt(sum((x_k - mean)^2) / N) | the spread should describe these runs |
| Sample standard deviation | `sample` | sqrt(sum((x_k - mean)^2) / (N - 1)) | the runs stand for the distribution the dispersions describe |

The sample standard deviation is sqrt(N / (N - 1)) times the population
one: 1.22 times for 3 runs, 1.05 for 10, 1.005 for 100. The difference
only matters for small batches.

### Population standard deviation (`population`)

- **Inputs:** each successful run's radial, along-track and cross-track
  offset from the batch's mean [m], at each sample; N, the number of runs
  that succeeded.
- **Outputs:** the `<spacecraft>.monte_carlo.spread` series [m], the Monte
  Carlo page's spread tiles, the command line's "1-sigma at the end" line.
- **Assumptions:** the spread describes these N runs only, not the
  distribution they were drawn from. One run gives a spread of 0.
- **Reference:** NumPy reference, `numpy.std`: the `ddof` argument (0, the
  default, divides by N).
- **Checked against:** `tests/test_monte_carlo_results.py` (the spread is
  `numpy.std` of the runs' offsets), `tests/test_model_registry.py` (the
  formula for three runs).
- **Why it is the default:** the tool used it before the choice existed,
  so every batch reads as it did. No derivation recorded.

### Sample standard deviation (`sample`)

- **Inputs and outputs:** as for the population standard deviation.
- **Assumptions:** the runs are a random sample of the distribution the
  dispersions describe. Dividing by N - 1 (Bessel's correction) makes the
  variance an unbiased estimate of that distribution's; the standard
  deviation itself is still slightly low for few runs. One run gives a
  spread of 0, since N - 1 would be 0.
- **Reference:** NumPy reference, `numpy.std`: the `ddof` argument (1
  divides by N - 1).
- **Checked against:** `tests/test_model_registry.py` (the formula, and
  the sqrt(3/2) ratio for three runs), `tests/test_monte_carlo.py` (a
  batch run with it keeps and records it).

## Where the choice shows

- **The batch keeps it:** `batch_results.json` records the statistic the
  batch was run with (`spread_statistic`), so a batch opened later reads
  the same, whatever the project file says by then. A summary written
  before the choice existed reads as `population`.
- **The batch's provenance** (`archive.provenance.json`) records it under
  `models`: the model's name, title, method and references.
- **The Monte Carlo page** names it in the line under the title
  ("... 1-sigma offsets from the mean of all runs (population standard
  deviation) ..."); its tooltip gives the formula.
- **The command line** prints it after the spread:
  `1-sigma: the population standard deviation of the 20 run(s)
  (monte_carlo.spread_statistic: population)`.

## The outcomes of each run

Each run of a batch keeps its headline figures, the same as Results ›
Overview shows for a single run (`engine/run_summary.py`,
`overview_figures`): the run length, and per spacecraft the orbital
period, the lowest and highest altitude, delta-V, propellant used, the
mean semi-major axis change, the lowest link margin, the lowest battery
charge, passes, contact time, eclipses, eclipse time and data
downlinked. A figure is there only when the run recorded what it is read
from. When a run's altitude does not vary (Overview then shows one
altitude), the batch keeps that value as both the lowest and the highest
altitude, so that every run has the same outcomes. The list and each unit
are `MONTE_CARLO_OUTCOMES` in `schema/scenario.py`.

## The probability of not meeting a requirement: `probability_bound`

A requirement (`monte_carlo.requirements` in the scenario) limits one
outcome of one spacecraft: `at_least` or `at_most`, in the outcome's unit.
For each requirement:

- **N**, the runs evaluated: the successful runs that recorded the
  outcome, and the crashed runs. A successful run without the outcome is
  *not evaluated* and is not in N.
- **k**, the runs that do not meet it. A crashed run has no outcome and
  counts as not meeting every requirement: the conservative reading
  (decision MC-6). The table shows how many of the k crashed.
- **The estimate** k/N.
- **The upper bound** at the requirement's confidence C: the
  one-sided Clopper-Pearson bound, the choice
  `monte_carlo.probability_bound`.
- **The verdict**, with an allowed probability (`max_probability`):
  *met* when the upper bound is at or below it, else *not shown*.

There is one model; the choice exists so that a later one can be added.

| Model | Name | Formula |
|---|---|---|
| Clopper-Pearson exact upper bound | `clopper_pearson` (default) | the p at which sum over i = 0..k of C(N, i) p^i (1 - p)^(N - i) = 1 - C |

### Clopper-Pearson exact upper bound (`clopper_pearson`)

- **Inputs:** N, the runs evaluated; k, the runs that do not meet the
  requirement (crashed runs included); C, the requirement's confidence.
  C has no default: each requirement states it (decision MC-5).
- **Method:** the bound is the probability p at which the binomial
  probability of k or fewer failures in N runs equals 1 - C. It is found
  by bisection on that sum; the sum's largest term is computed with
  `math.lgamma`, so no factorial overflows. No table and no SciPy. For
  k = 0 the bound is 1 - (1 - C)^(1/N); for k = N it is 1.
- **Outputs:** the Requirements table's estimate, upper bound and
  verdict (Results › Monte Carlo › Requirements, and the command line's
  table); `monte-carlo`'s exit status 5 when a requirement with an
  allowed probability is not shown met.
- **Assumptions:** the runs are independent and each fails with the same
  probability (a binomial count): Basilisk's controller draws each run's
  dispersions and seeds independently. One-sided: an upper bound only.
  Exact, so conservative: the true coverage is at least C, and more for
  small N.
- **Reference:** C. J. Clopper and E. S. Pearson, "The use of confidence
  or fiducial limits illustrated in the case of the binomial",
  Biometrika 26(4), 1934, pp. 404-413.
- **Checked against:** `tests/test_monte_carlo_requirements.py`: the
  closed form for k = 0; the regularized incomplete beta function
  I_p(k + 1, N - k) = C, the bound's other form, computed exactly in
  rational numbers (an independent method); monotonic in k and C; 1 for
  k = N.

**Read the bound, not only the estimate.** With 20 runs and no failure the
estimate is 0, but the bound at C = 0.95 is 1 - 0.05^(1/20) = 0.139: 20
runs cannot show a probability of failure below 0.139 at that confidence.

**The batch keeps it:** `batch_results.json` records the requirements the
batch was run with (`requirements`) and the bound's model
(`probability_bound`); the verdicts are computed when the batch is read,
from the outcomes it keeps. The batch's provenance records the model
under `models`.

## A thermal batch against its nodes' limits

The thermal Monte Carlo (`thermal.monte_carlo`) uses the same bound for
the probability that a run leaves a node's operating or survival range
(Monte Carlo plan B4, decisions MC-22 and MC-23):

- **Inputs:** N, the runs evaluated (the runs solved and the runs whose
  draw the model refused); k, the runs whose own solved temperature is,
  at any time step, below the range's low end or above its high end (a
  refused run counts as outside every range); C, the thermal Monte
  Carlo's `confidence`, optional, with no default.
- **Outputs:** per node and range, k/N and, with C, the Clopper-Pearson
  upper bound above (the model in effect for `probability_bound`); the
  Node limits tab of Results › Monte Carlo and the command line's
  `thermal --monte-carlo` table. The thermal summary keeps the rows
  (`node_limits`), counted when the batch is solved.
- **Assumptions:** as above (independent runs, one probability each),
  and the ranges of the case solved (its overrides applied).
- **Checked against:** `tests/test_monte_carlo_requirements.py` (a
  synthetic batch with known exceedances) and
  `tests/test_thermal_studies.py` (template 33: the counts equal those
  read from the kept temperatures).

## The band of a thermal or operations batch

The plots of a thermal and an operations batch draw, at each sample, the
runs' mean and the lines "mean - 3 standard deviations (not a
probability bound)" and "mean + 3 standard deviations (not a probability
bound)": the mean plus or minus three standard deviations of the runs at
that sample, by the batch's `spread_statistic`. The label says what they
are. They assume no distribution, so they are no bound on a
probability: for a normal distribution about 0.27 % of the runs would
fall outside, for another distribution any share can. For a probability,
use the outcome statistics below, a requirement, or the Node limits tab
of a thermal batch (decision MC-27).

## Outcome statistics: `percentile_method` and `percentiles`

Each outcome of a batch, over the successful runs that recorded it
(Monte Carlo plan B3): N, the minimum, the percentiles, the maximum, and
the empirical distribution. The outcomes are where each run ended
against the batch mean (the radial, along-track and cross-track offsets
of the Runs table, in km) and its Overview figures; for a thermal batch
each node's lowest and highest temperature; for an operations batch its
drawn outcomes and each profile's lowest and highest value. A crashed run
has no outcome and is not in N.

- **The percentiles** shown are a parameter, `monte_carlo.percentiles`
  [%]. Its value is provisional: the owner has not named the
  percentiles (plan Q8), so the source is "TBD", and the default is 1,
  5, 50, 95 and 99 % (decision MC-27). A project file changes them:

  ```yaml
  parameters:
    monte_carlo.percentiles: [10, 50, 90]   # [%]
  ```

- **The method** is a choice, `monte_carlo.percentile_method`, with one
  model; the choice exists so that a later one can be added.
- **The empirical distribution function** F(x) is the fraction of the N
  runs whose value is at or below x. The Statistics tab draws it as a
  step plot: 0 below the smallest value, a step up at each value by the
  share of runs that have it, 1 from the largest value on. No method is
  chosen for it: it is the runs themselves.

| Model | Name | Formula |
|---|---|---|
| Linear interpolation (Hyndman and Fan's definition 7) | `linear` (default) | h = (N - 1) p / 100 + 1; x_j + (h - j)(x_(j+1) - x_j), j = floor(h) |

### Linear interpolation (Hyndman and Fan's definition 7) (`linear`)

- **Inputs:** each successful run's value of the outcome (a run without
  it is left out); the percentiles to show, `monte_carlo.percentiles`.
- **Method:** for the p-th percentile of the N values sorted,
  x_1 <= ... <= x_N: h = (N - 1) p / 100 + 1, and the percentile is
  x_j + (h - j)(x_(j+1) - x_j) with j = floor(h). The 0th percentile is
  the minimum and the 100th the maximum. It is `numpy.percentile` with
  `method="linear"`, NumPy's default, so a percentile computed with
  NumPy from the Runs table's CSV is the same number.
- **Outputs:** the Statistics table of Results › Monte Carlo.
- **Assumptions:** the percentiles describe these N runs, not the
  distribution they were drawn from; they are no confidence bound. With
  few runs the 1st and 99th percentiles lie between the two most extreme
  runs.
- **References:** R. J. Hyndman and Y. Fan, "Sample quantiles in
  statistical packages", The American Statistician 50(4), 1996,
  pp. 361-365, definition 7; NumPy reference, `numpy.percentile`.
- **Checked against:** `tests/test_monte_carlo_statistics.py`: the
  percentiles equal `numpy.percentile` with the method, for every model;
  the step function's last value is exactly 1.

## Sensitivity: `sensitivity_measure`

Which drawn values go with which outcomes (Monte Carlo plan B2): the
correlation of each drawn value (each dispersion's value in each run)
with each outcome above, in a table sorted by the correlation's size,
whatever its sign, and a scatter plot of the pair picked. The measure is
a choice, `monte_carlo.sensitivity_measure`.

- **Pairwise:** a run counts for a pair when it recorded both values. A
  crashed run (no outcome) and a run without that outcome are left out of
  that pair only. The table shows N per pair.
- **No value:** a column that does not vary over those runs (template
  09's drag-free orbit: the mass changes no outcome), or a pair of fewer
  than 3 runs, has no correlation; the table shows "—", never NaN.
- **Not a cause:** a correlation says which drawn values go with which
  outcomes in these runs. Basilisk's controller draws each dispersion
  independently, so two drawn values do not share a correlation by their
  draw.

| Model | Name | Formula |
|---|---|---|
| Spearman's rank correlation | `spearman` (default) | Pearson's correlation of the ranks, tied values at their mean rank |
| Pearson's correlation | `pearson` | sum((x_k - mean x)(y_k - mean y)) / sqrt(sum((x_k - mean x)^2) sum((y_k - mean y)^2)) |

```yaml
parameters:
  monte_carlo.sensitivity_measure: pearson   # [-] spearman (default) or pearson
```

### Spearman's rank correlation (`spearman`)

- **Inputs:** each run's drawn value and outcome, pairwise; N.
- **Method:** each column is replaced by its ranks (1 for the smallest;
  tied values get the mean of the ranks they share, so 10, 20, 20, 30
  rank 1, 2.5, 2.5, 4), then Pearson's correlation of the ranks is
  computed. NumPy only, no SciPy.
- **Outputs:** the Sensitivity table and its scatter plot.
- **Reading it:** +1 when the outcome always grows with the drawn value,
  -1 when it always falls, near 0 when they are unrelated. Any monotonic
  relation counts, not only a straight line, and a few extreme runs move
  it little: so it is the default.
- **Reference:** C. Spearman, "The proof and measurement of association
  between two things", American Journal of Psychology 15(1), 1904,
  pp. 72-101.
- **Checked against:** `tests/test_monte_carlo_statistics.py`: inputs
  that make the outcome grow, fall or not change give +1, -1 and about 0;
  ties take their mean rank (a case of four values computed by hand gives
  sqrt(0.9)); a case of five values computed by hand.

### Pearson's correlation (`pearson`)

- **Inputs, outputs, assumptions:** as Spearman's.
- **Method:** the correlation of the values themselves. +1 or -1 only
  when the outcome is a straight-line function of the drawn value.
- **Reference:** K. Pearson, "Mathematical contributions to the theory of
  evolution. III. Regression, heredity, and panmixia", Philosophical
  Transactions of the Royal Society of London A 187, 1896, pp. 253-318.
- **Checked against:** `tests/test_monte_carlo_statistics.py`: a straight
  line gives 1; x = 1..5 against (1, 2, 3, 4, 100) gives 20 / sqrt(761),
  computed by hand.

## Where these choices show

- **The batch keeps them:** `batch_results.json` records
  `sensitivity_measure`, `percentile_method` and `percentiles` as the
  batch was run (optional keys, format 1 still), so a batch opened later
  reads the same. A summary written before them reads with the defaults.
  The batch's provenance records both models under `models`.
- **The Monte Carlo view** names the model in the Sensitivity table's
  heading, and each tab's hint gives the method and its reference in its
  tooltip. The statistics and correlations are worked out off the GUI
  thread when the Statistics or Sensitivity tab is first shown.

## Not covered

No confidence interval on the spread, on a percentile or on a
correlation. No two-sided interval on a probability, and no requirement
on a combination of outcomes. No partial correlation and no
variance-based sensitivity index: the correlation of one drawn value with
one outcome does not separate the effects of several drawn values. The
runs' drawn values, final offsets and outcomes are in the run table, and
its CSV export, for any other statistic.
