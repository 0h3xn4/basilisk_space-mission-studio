# Monte Carlo statistics

How a Monte Carlo batch's spread is measured: each run's offset from the
mean of all runs, and the 1-sigma of those offsets. And how a batch
judges a requirement on its runs' outcomes: the probability of not
meeting it, with an exact upper bound. Code:
`spacemissionstudio/engine/monte_carlo_results.py` and
`spacemissionstudio/engine/monte_carlo_requirements.py`; the models are
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

## Not covered

No other statistic (a percentile, a median absolute deviation) and no
confidence interval on the spread itself. No two-sided interval on a
probability, and no requirement on a combination of outcomes. The runs'
drawn values, final offsets and outcomes are in the run table, and its
CSV export, for any other statistic.
