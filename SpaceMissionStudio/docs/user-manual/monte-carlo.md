# Run many variations at once (Monte Carlo)

How to run a scenario many times with small random changes, and see how
far apart the results end up.

## Set up a batch

1. In the scenario tree, open the **Monte Carlo** page and tick
   **Enabled**.
2. Set how many runs (**Number of runs**, up to 100 000), and how many
   run in parallel (**Processes**; at most one process per CPU is used).
   Optionally give a **Batch seed** for an independent batch: left at
   **Not set**, two batches of the scenario draw the same values; with a
   seed, another seed gives other draws and the same seed the same batch.
3. Add one or more **dispersions**: which quantity varies, for which
   spacecraft, and by how much. A new dispersion starts at the
   spacecraft's own value (dry mass, drag or radiation-pressure
   coefficient) with no spread: widen its bounds, or give it a standard
   deviation, for it to vary.
4. Set the mode beside **Run** to **Monte Carlo** (if the batch is off,
   **Run > Run** says so and offers **Enable Monte Carlo**), press
   **Run**, and choose a folder (or set it first under **Archive folder** on **Run >
   Run**, where it is remembered for the scenario). Every run is saved there; the progress in the status bar counts
   the cases done. **Cancel** (`Esc`) stops the batch: the runs
   finished stay in the folder and **Results > Monte Carlo** opens on them.

What can vary:

| Quantity | Varies | Kinds |
|---|---|---|
| `dry_mass_kg` | Dry mass [kg] | uniform, normal |
| `attitude_sigma_bn` | Starting attitude, Euler angles [deg] (saved in rad) | uniform_euler_mrp |
| `orbit_elements` | Each orbital element of the starting orbit | normal, uniform |
| `inertia_kg_m2` | The inertia [kg m^2] | normal |
| `angular_rate_bn_b` | Starting body rate [deg/s] | normal, uniform |
| `drag_coeff`, `srp_coeff` | The drag or solar-pressure coefficient | uniform, normal |

Inertia and body rate need *Full attitude*; the coefficients need drag or
solar pressure on.

## State a requirement

Under the dispersions, **Requirements** holds limits on one outcome of
every run.

1. **Add requirement** (or **Add**) adds one and opens its form.
2. Choose the spacecraft and the **Outcome** (the figures Results ›
   Overview shows for one run: lowest altitude [km], delta-V [m/s],
   lowest battery charge [W*h], ...).
3. Set the **Limit**: **At least** or **At most**, in the outcome's unit.
4. Set the **Confidence** of the bound, between 0 and 1. It has no
   default: you choose it.
5. Optional: tick **Judge against an allowed probability** and set the
   probability of not meeting the requirement that you accept.

The limit and the confidence start **Not set**; until both are given, the
Problems panel names the missing field.

## Read the batch

**Results > Monte Carlo** opens on the batch:

- **Tiles:** how many runs succeeded, how many failed (the tile's tooltip
  names them), and the 1-sigma spread at the end along track, radially
  and across track.
- **Plots:** every run's altitude and its offset from the mean, and the
  spread over time.
- **Runs:** what each run drew, where it ended and its outcomes (the
  Overview figures of that run). A crashed run is listed with what it
  drew and the status "crashed". Sort a column to see which drawn value
  goes with the largest offset. **Export table CSV...** saves it, with
  the batch's provenance in `<file>.provenance.json` beside it.
- **Requirements:** per requirement, the runs evaluated (N), the runs
  that do not meet it (k; a crashed run counts as not meeting every
  requirement), the estimate k/N, the exact upper bound at its
  confidence and, with an allowed probability, the verdict: **met** or
  **not shown**. Read the bound next to the estimate: 20 runs without a
  failure show, at a confidence of 0.95, only that the probability is
  below 0.139.
- **Statistics:** per outcome, the runs that recorded it (N), the
  minimum, the percentiles (1, 5, 50, 95 and 99 % by default) and the
  maximum. Pick a row for its empirical distribution: the fraction of runs
  at or below each value, a step plot that ends at 1.
- **Sensitivity:** Spearman's rank correlation of each drawn value with
  each outcome, the strongest first, with N per pair; "—" where a value
  does not vary. Pick a row for the scatter plot of the runs. Read it as
  "goes with", not "causes".

**Export report...** (beside **Open results...**) writes all of this to
one file, Markdown (`.md`) or JSON (`.json`): the settings, the
dispersions, the spread, the requirements with their verdicts, the
statistics, the sensitivity, the crashed runs and the provenance (the
scenario's and the data files' SHA-256, the versions). The numbers are
the view's. It is written in the background; a message says where.

The spread is the population standard deviation of the runs, unless a
project file chooses the sample one
([Choose a model](project-configuration.md#choose-a-model)); the page
names the statistic, and a batch keeps the one it was run with.

The percentiles, their method and the correlation are project
parameters (`monte_carlo.percentiles`, `monte_carlo.percentile_method`,
`monte_carlo.sensitivity_measure`); a batch keeps the ones it was run
with. A thermal or operations batch's band around the mean is the mean
plus and minus 3 standard deviations of the runs, labelled "not a
probability bound".

**Open Monte Carlo Results...** (the Run area) opens a batch you ran
earlier. If the scenario open is not the one the batch was run with, a
warning under the title says so, with both scenario hashes.

Before a batch, the Problems panel warns when a dispersion of the dry
mass, the drag coefficient or the SRP coefficient no longer contains the
spacecraft's value (its bounds around it, a normal one's mean on it):
the dispersion keeps its own numbers when you edit the spacecraft.

## Run one case again

To look at one case in detail, for example the run with the lowest
altitude:

1. Open the batch's own scenario, unchanged, and its batch in **Results >
   Monte Carlo**.
2. On **Runs**, sort the column you are after and pick the run.
3. Choose **Run This Case** (the button under the table, the right-click
   menu, or `Ctrl+Shift+R`).

The case runs again with the same drawn values and random seeds, so it
gives the batch's outcomes, and it opens in Results as a normal run:
every series, the events and the Overview. A case that crashed in the
batch crashes again with its own error; the Log shows it in full. If the
scenario changed since the batch, the case is not run: the Problems
panel gives the scenario's SHA-256 now and at the batch. Open the
batch's own scenario and try again.

The case also runs only with the reference data files it used in the
batch. If one changed since (a newer space-weather download, Earth
orientation files installed or updated, another support-data file), the
case would fly with other data and is not run: the Problems panel names
the file, with its SHA-256 now and at the batch. Put the batch's files
back (roll a download back in **Settings > Reference data**), or run the
batch again. The window can check only the scenario before it starts the
case; the data files are checked when the case is built, so the run shown
before is already cleared then. A batch made by 2.13.1 or earlier did not
keep its data files, and its cases are not checked for them.

## From the command line or Python

```bash
spacemissionstudio monte-carlo spacemissionstudio/scenarios/templates/25_monte_carlo_orbit_and_drag_dispersions.json --archive-dir mc
spacemissionstudio monte-carlo spacemissionstudio/scenarios/templates/25_monte_carlo_orbit_and_drag_dispersions.json --archive-dir mc --case 7 --out-dir case7
spacemissionstudio monte-carlo spacemissionstudio/scenarios/templates/37_monte_carlo_requirements_and_sensitivity.json --archive-dir mc37 --runs 60 --processes 4 --report mc37.md
spacemissionstudio monte-carlo --summarize mc37 --csv runs.csv --report mc37.json
python3 examples/monte_carlo_spread.py --runs 20 --archive mc_out
```

`monte-carlo` also prints the batch seed (when one is set), each
outcome's lowest and highest value over the runs, the requirements
table, the outcome statistics and the ten strongest correlations. It
exits with status 3 when a run failed, else 5 when a requirement with an
allowed probability is not shown met.

`--runs N` and `--processes N` change the batch's size and processes for
this batch only; the scenario file is not changed, and
`archive.provenance.json` records both values (`monte_carlo_settings`).
`--report FILE` writes the batch report, Markdown for a `.md` file and
JSON for a `.json` file, and `--csv FILE` the Runs table.
`--summarize DIR` (with no scenario) runs nothing: it prints the batch in
DIR as above and writes its Runs table (`monte_carlo_runs.csv` unless
`--csv` names another file) and, with `--report`, its report. It exits
with 5 when a requirement is not shown met, and 1 for a folder without a
batch.

With `--case N`, `monte-carlo` runs case N of the batch in
`--archive-dir` again and writes what `run --out-dir` writes (default
folder `results`); `provenance.json` names the batch and the case
(`monte_carlo_case`). It exits with status 1 when the scenario or a
reference data file changed since the batch, and 3 when the case's run
fails. From Python,
`api.monte_carlo_case(scenario, "mc", 7)` returns the run's results.

The example prints the spread day by day and ends with a line like
`day 3.00: 1-sigma 448.0 km along track`. Its 20 runs took 2 to 3
minutes in our clean-install tests.

## Templates

**09** varies the mass of a drag-free orbit (and shows that it changes
nothing). **25** varies the orbit and the drag coefficient: the runs
spread about 150 km per day along track. **37** is 25's satellite for
half a day, 30 runs with a batch seed and two requirements: one is met
(its 90 % bound under the allowed probability), the other shows its
estimate and bound, and the Sensitivity tab finds that the drag
coefficient drives the decay. It takes about a minute in one process.

**More detail:** User Manual section 10,
[Monte Carlo](../../USER_MANUAL.md#10-monte-carlo-running-many-variations-at-once).

---

**Next:** [Lifetime and propellant budget](lifetime-and-budget.md) ·
[Read the results](read-the-results.md)
