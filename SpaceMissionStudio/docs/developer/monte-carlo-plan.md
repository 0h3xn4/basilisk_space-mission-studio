# Monte Carlo: plan (Step 0)

The owner's backlog item is "make the Monte Carlo features useful". The
owner accepted "Monte Carlo phase A" as the next item. This page defines
phase A, and phases B and C after it. It is Step 0 of the feature: an
investigation, a design and a plan. No code changed in this step.

- **Decisions:** `docs/DECISIONS.md`, section "Monte Carlo plan
  (2026-11-21)", decisions MC-1 to MC-10.
- **Backlog:** `BACKLOG.md`. Phase A is under "Next release"; phases B
  and C are under "Later".
- **Base:** `develop` at `93eb298` (release 2.13.1), Basilisk 2.12.0
  from PyPI. Every Basilisk line cited below was read in the installed
  2.12.0 wheel (`Basilisk/utilities/MonteCarlo/`), not only in `../src`.

**Absolute rule.** Nothing outside `SpaceMissionStudio/` changes. The
plan uses Basilisk's Monte Carlo framework through its public API only:
`Controller`, `Dispersions`, `RetentionPolicy` and
`SimulationExecutor.applyModification`.

**Constants and models.** Every new number and every new statistical
method goes through the project's registry: parameters in
`spacemissionstudio/config/parameters.py`, model choices in
`spacemissionstudio/config/models.py` (the brief calls them
`settings.py` and `model_choices.py`; those files do not exist here).
Each method names its source. A value without a source is "TBD".

## 1. What exists

### 1.1 Inventory

| Layer | What it does | Where |
|---|---|---|
| Scenario schema | `MonteCarloConfig`: `enabled`, `num_runs` (default 10), `thread_count` (default 1), `verbose`, `dispersions`. No seed, no requirement, no outcome. | `schema/scenario.py:3028-3058` |
| Dispersions | `DispersionConfig`: spacecraft, quantity, kind, bounds, mean, std_deviation, element_spread, angle_std_deg. Seven quantities: `dry_mass_kg`, `attitude_sigma_bn`, `orbit_elements`, `inertia_kg_m2`, `angular_rate_bn_b`, `drag_coeff`, `srp_coeff`. | `schema/scenario.py:278-302`, `:2943-3010` |
| Limits (audit R4) | At most 100 000 runs and 256 processes; the batch uses one process per CPU at most. R2 and R3 of the same audit row are not about Monte Carlo (conditions, script consent). | `schema/scenario.py:3017-3024`; `HISTORY.md` "Limits on conditions, script consent and Monte Carlo" |
| Cross checks | A dispersion names a real spacecraft; inertia and rate need full attitude; Cd and Cr need drag or SRP and no facets. | `schema/scenario.py:3954-3970` |
| Engine | Wraps Basilisk's `Controller`. Each run builds the service with `initialize=False`, the controller applies the draws, then the run starts and flies the Mission Sequence or the set duration. | `engine/monte_carlo.py:399-439`, `:449-557` |
| Retained data | Each spacecraft's `r_BN_N` and `v_BN_N` only. | `engine/monte_carlo.py:442-446` |
| Seeds | `setShouldDisperseSeeds(True)`. Basilisk seeds NumPy and `random` with the run index times 10 before each run, then draws every model's `RNGSeed`. `sim_settings.seed` has no effect on a batch (SRelD K-24). | `engine/monte_carlo.py:524`, `:560-561`; Basilisk 2.12.0 `Controller.py:790`; `compliance/docs/SRelD.md:1115` |
| Summary | `batch_results.npz` and `.json` (format 1, pickle free): time grid (at most 2000 samples), r and v per run, the values each run drew, the failed run indices, the statistic. Kinds `orbit`, `thermal`, `operations`. | `engine/monte_carlo_results.py:60-72`, `:126-157`, `:214-266` |
| Statistics | Curvilinear radial, along-track and cross-track offsets from the runs' mean; their standard deviation (population or sample, the model `monte_carlo.spread_statistic`). Thermal and operations batches add "mean - 3 sigma" and "mean + 3 sigma" lines. | `engine/monte_carlo_results.py:274-296`, `:329-350`; `config/models.py:139-173`; `config/parameters.py:558-566` |
| Provenance | `archive.provenance.json`: versions, the scenario's hash, the nominal run's settings, the seed note, the models. | `engine/monte_carlo.py:573-601` |
| CLI | `monte-carlo SCENARIO --archive-dir --overwrite --allow-scripts`. Prints the 1-sigma at the end. Exit 3 when a run failed. No CSV, no seed, no run count override, no way to open an earlier batch. | `cli.py:567-608`, `:2487-2497` |
| API | `api.monte_carlo(scenario, archive_dir, ...)` returns the batch. It does not pass the file record to the provenance. | `api.py:185-199` |
| GUI: settings | Scenario tree › Monte Carlo: enabled, runs, "Thread count", the dispersion list and form. A new dispersion starts at the spacecraft's own value (audit 3.7). The starting attitude is in rad, the rest of the app uses deg. | `gui/monte_carlo_editor.py:85`, `:95`, `:246-255`, `:495-503` |
| GUI: run | The run mode "Monte Carlo" beside Run. The batch runs in a child process, with progress (finished cases) and cancel. | `gui/monte_carlo_process.py`; `gui/main_window.py:1904-1916` |
| GUI: results | Results › Monte Carlo: tiles (runs, failed, the three spreads at the end, the altitude range at the end), plots (per-run curves, spread), the Runs table (drawn values and the final offsets), Export table CSV with a provenance sidecar. | `gui/monte_carlo_results_widget.py:113`, `:196-239`, `:264-287` |
| Pre-run checks | One warning: more processes than CPUs. | `engine/scenario_checks.py:745-755` |
| Thermal Monte Carlo | Per spacecraft `thermal.monte_carlo`: runs, `seed` (default 1), case, dispersions by path. Seeded NumPy generator. Each node has `operating_c` and `survival_c` limits, but the batch does not count runs outside them. | `schema/thermal.py:112-113`, `:380-420`; `thermal/sweeps.py:188-227` |
| Operations robustness | `plan robustness --runs --seed ...`: a seeded batch of the plan, shown in the same view. | `cli.py:2606-2617`; `operations/robustness.py` |
| Templates | 09: dry mass, normal, 20 runs, 1 day. 25: orbit elements (normal) and drag coefficient (uniform), 20 runs, 3 days. 34: thermal Monte Carlo, 20 runs, seed 34. | `spacemissionstudio/scenarios/templates/` |
| Docs | User Manual section 10; how-to `docs/user-manual/monte-carlo.md`; `docs/models/monte-carlo-statistics.md`; `docs/reference/limitations.md:108-125`; `examples/monte_carlo_spread.py`. | as named |
| Tests | `tests/test_monte_carlo.py` (21 tests), `tests/test_monte_carlo_results.py` (9), `tests/gui/test_monte_carlo_editor.py` (15), `tests/gui/test_monte_carlo_results_widget.py` (8). The golden files run a 2-run batch of 0.05 days for templates 09 and 25 and keep `final_spread`, `run_table` and `summary_lines`. | `tests/golden_capture.py:124-125`, `:310-327` |
| Run time | The example's 20 runs of template 25 (3 days) took 126 s in the documentation audit; the how-to says 2 to 3 minutes. | `docs/DOCS_AUDIT.md:196`; `docs/user-manual/monte-carlo.md` |

### 1.2 What is good and stays

- The draws are made by Basilisk's own dispersion classes. The app's
  subclasses only fix two known traps (dry mass plus propellant, rate
  added to the nominal rate).
- Every run flies what `run` flies (Mission Sequence included, audit H1).
- The summary never unpickles a file it did not write (S-04).
- The orbit spread is curvilinear, so a large along-track spread does not
  show up as a false radial one.
- Cancel keeps the finished cases. A reused folder never shows an older
  batch as the new one (M10).
- The statistic is a declared model with a source, and a batch keeps the
  one it was run with.

## 2. An engineer's walk-through, on paper

The task: a 3-day LEO case like template 25. The engineer wants to know
if the spacecraft stays above an altitude and meets a link and a battery
requirement, with what confidence, and why some runs do not.

| Step | What the engineer can do today | Evidence | Gap |
|---|---|---|---|
| Disperse the initial state | Yes: orbital elements (normal or uniform per element), starting attitude (uniform Euler angles, in rad), starting body rate. | `schema/scenario.py:292-302` | The attitude unit (rad) differs from the rest of the GUI (deg): `gui/monte_carlo_editor.py:85`. |
| Disperse mass properties | Dry mass, inertia (diagonal plus a small rotation). | same | No centre-of-mass offset, no propellant load. Dry mass, Cd and Cr are absolute values: when the user edits the spacecraft's mass, the dispersion does not follow it, and no check warns (`engine/scenario_checks.py:745-755` has only the process check). |
| Disperse actuator errors | No. | `DISPERSION_QUANTITIES`, `schema/scenario.py:292` | No maneuver execution error, no thruster magnitude or misalignment, no reaction-wheel friction or bias. Sensor noise differs per run only through the dispersed `RNGSeed`s. |
| Disperse drag | The drag coefficient, for a spacecraft without facets. | `schema/scenario.py:3965-3967` | No density or solar-activity dispersion. A faceted spacecraft (the 3D-model templates) cannot disperse drag at all. |
| Run N cases | Yes, in parallel processes, with progress and cancel. | `engine/monte_carlo.py:520-546` | The default is one process (`schema/scenario.py:3038`); the field is called "Thread count" but means processes (`gui/monte_carlo_editor.py:503`). The CLI cannot change N or the processes without editing the file. |
| See which cases fail a requirement | No. "Failed" means only "the run raised an error". | `engine/monte_carlo_results.py:79-107` | No requirement exists in the schema. Each run's `ResultSet` is built and thrown away (`engine/monte_carlo.py:437-439`): no per-run altitude minimum, link margin, battery charge, delta-V. |
| Know why a run crashed | Partly: Basilisk prints the traceback to the child's stdout. | Basilisk 2.12.0 `Controller.py:894-897` | The summary drops a failed run's drawn values (`engine/monte_carlo.py:682-683`, `:692-694`), so the Runs table cannot show what it drew. A `TypeError` inside a run makes Basilisk call the execution function again with two arguments (`Controller.py:865-867`); that call fails at once, so the log shows a second, misleading error after the first. |
| Get percentiles and a confidence on a probability | No. One statistic: the 1-sigma at the end. Thermal and operations add "mean ± 3 sigma" lines, which suggest a normal distribution that nothing checks. | `engine/monte_carlo_results.py:291-296`, `:337-339`, `:348-350` | No percentile, no exceedance count, no confidence bound. The orbit tiles show the end only, not the largest spread during the run. |
| Find which inputs drive a result | Only by sorting the Runs table by hand. | `gui/monte_carlo_results_widget.py:113` | No correlation or sensitivity measure, no scatter plot. |
| Reproduce one case | No. `run<N>.json` holds that case's draws and seeds, but nothing reads it back. Basilisk's `reRunCases` keeps no data. | Basilisk 2.12.0 `Controller.py:333-379` | The user cannot open case 7 as a normal run with every series, events and the Overview. |
| Compare against a requirement | No (see above). | | |
| Export a report | The Runs table as CSV, with the batch's provenance beside it (GUI only). | `gui/monte_carlo_results_widget.py:264-287` | No CSV from the CLI. No report of the batch (settings, draws, statistics, failures, provenance). |
| Trust what is shown | Partly. | | Two batches of one scenario draw the same samples (K-24; `docs/reference/limitations.md:120-122`). An opened batch is not checked against the open scenario's hash, although `archive.provenance.json` has it (`engine/monte_carlo.py:590`). |
| Thermal Monte Carlo | Seeded, reproducible, in the same view. | `thermal/sweeps.py:188-227` | The node limits exist (`schema/thermal.py:112-113`), but the batch does not say how many runs leave them. |

## 3. Gaps, ranked

Value: what a user gains (H high, M medium, L low). Cost: realistic
hours for this project, with tests and the records CLAUDE.md asks for
(decisions, CHANGELOG, user manual and `sync_help.py`, ICD, test
specifications).

| # | Gap | Evidence | Value | Cost [h] | Phase |
|---|---|---|---|---|---|
| G1 | No per-run outcomes other than position and velocity. | `engine/monte_carlo.py:437-446` | H | 3 | A1 |
| G2 | No requirement, no pass or fail per run, no probability with a confidence bound. | `schema/scenario.py:3028-3058` | H | 4.5 | A2 |
| G3 | A case cannot be reproduced and opened as a normal run. | §2 "Reproduce one case" | H | 3 | A3 |
| G4 | A crashed run's draws are dropped from the summary. | `engine/monte_carlo.py:682-694` | M | 1 | A4 |
| G5 | No sensitivity (which input drives an outcome). | §2 | H | 3 | B2 |
| G6 | One statistic only; no percentiles; "± 3 sigma" lines assume a normal distribution. | `engine/monte_carlo_results.py:291-350` | M | 2.5 | B3 |
| G7 | Two batches of one scenario draw the same samples; `sim_settings.seed` has no effect (K-24). | `Controller.py:790` | M | 2 | B1 |
| G8 | Thermal Monte Carlo does not count runs outside the node limits. | `schema/thermal.py:112-113` | M | 2 | B4 |
| G9 | No batch report; no CSV or summary from the CLI; no CLI overrides of runs and processes. | `cli.py:567-608` | M | 4.5 | B5, B7 |
| G10 | Absolute dispersion values do not follow an edit of the nominal; an opened batch is not checked against the scenario. | §2 | M | 1.5 | B6 |
| G11 | Few dispersions: no maneuver execution error, thruster, wheel, density, propellant load, centre of mass. | `schema/scenario.py:292` | H | 8 to 12 | C1 |
| G12 | Outcomes only from the run summary's figures; no user-chosen outcome (pointing error, wheel speed). | `engine/run_summary.py:22-43` | M | 4 | C2 |
| G13 | No convergence view; a batch cannot be extended with more cases. | — | M | 4 (with a spike) | C3 |
| G14 | No percentile bands over time for retained series. | `engine/monte_carlo_results.py:329-350` | L | 3 | C4 |
| G15 | Small labels: "Thread count" for processes; the "Failed" tile lists every index as text; the attitude in rad. | `gui/monte_carlo_editor.py:85`, `:503`; `gui/monte_carlo_results_widget.py:234` | L | 1 | B8 |
| G16 | No other sampling than simple random sampling (no Latin hypercube). | `Controller.py:790` | L | 10 (with a spike) | C5 |

Not a gap: speed. A case costs about 6 s for 3 days of template 25
(126 s for 20 cases, `docs/DOCS_AUDIT.md:196`), and the batch runs one
process per CPU when the user asks. The default of one process is a
usability point (G15, B8), not a speed problem of the engine.

## 4. Phase A: outcomes, requirements, reproduce a case

**Goal:** after phase A the engineer can state a requirement, see how
many runs meet it, read the probability of not meeting it with an exact
upper bound at a confidence the engineer chose, see what a failed or
crashed run drew, and open any case as a normal run.

**Size:** about 11.5 hours, in two pull requests:

| PR | Items | Hours |
|---|---|---|
| A-1 | A1 outcomes, A4 draws of crashed runs, A2 requirements | 8.5 |
| A-2 | A3 reproduce one case | 3 |

Commits name `SRS-F-13` (Monte Carlo dispersions,
`compliance/docs/SRS.md:162`).

### A1. Per-run outcomes (3 h)

**What.** Each run computes its headline figures, the same as Results ›
Overview for a single run (`engine/run_summary.overview_figures`): run
length, delta-V, propellant used, mean semi-major axis change, lowest
link margin, lowest battery charge, passes, contact time, eclipses,
eclipse time, data downlinked, lowest and highest altitude, orbital
period. A figure appears only when the run recorded its source, as for a
single run.

**How.**
- `_execute_sim` keeps the `ResultSet` that `service.run()` or
  `MissionEngine.run()` returns (today it is dropped,
  `engine/monte_carlo.py:437-439`) and stores the figures' keys, values
  and units on the sim object.
- A module-level retention function, added with
  `RetentionPolicy.addRetentionFunction` (Basilisk 2.12.0
  `RetentionPolicy.py:250-258`, called at `:372-374`), returns them.
  Basilisk puts them in the run's retained `custom` data, in the same
  `run<N>.data` file the app already reads back (S-04 unchanged).
- `collect_batch` reads them. `MonteCarloBatch` gets `outcomes` (one
  dict per successful run) and `outcome_units`.
- When the altitude does not vary (the figure is then "altitude", not
  "lowest altitude" and "highest altitude",
  `engine/run_summary.py:376-383`), the outcome keeps its value as both
  lowest and highest. So every run has the same keys.
- The summary JSON gains the optional keys `outcomes` and
  `outcome_units` (MC-3: format stays 1).
- GUI: the Runs table gets one column per outcome, after the drawn
  values; units in the headers. CSV export follows the table.
- CLI: `monte-carlo` prints, per outcome, the lowest and the highest
  value over the runs (a short table, not a sentence).
- `run_table(batch)` keeps its default columns: a new argument
  (`outcomes=True`) adds them. The golden files call the default.

**File format.** Summary JSON: two optional keys. No scenario change.

**Acceptance.**
- A 2-run batch of template 25 (0.05 days) has, for each run, the same
  figures as `run_summary.overview_figures` of a plain run of that
  case's draws (A3 makes that run).
- An older summary without `outcomes` still opens; the Runs table has no
  outcome columns then.
- The golden files are byte-identical.
- The extra time per case is measured on template 25 and recorded in
  HISTORY (no target number is invented; see risk R4).

**Tests.** `tests/test_monte_carlo.py`: outcomes present for every
successful run, keys and units; `tests/test_monte_carlo_results.py`:
save and load round trip with and without outcomes, `run_table` default
unchanged; `tests/gui/test_monte_carlo_results_widget.py`: outcome
columns and CSV.

### A2. Requirements and the probability of not meeting them (4.5 h)

**What.** The scenario can state requirements on the outcomes. For each
requirement the batch shows: the runs evaluated, the runs that do not
meet it, the estimated probability of not meeting it (k/N), and an
exact one-sided upper bound on that probability at the confidence the
user gave. When the user also gives an allowed probability, a verdict:
"met" when the upper bound is at or below it, else "not shown".

**Schema** (`MonteCarloRequirementConfig`, in
`monte_carlo.requirements`, a list):

| Field | Type | Meaning |
|---|---|---|
| `name` | text | The requirement's label, unique in the list (e.g. "R-ALT-01"). |
| `spacecraft` | text | A spacecraft of the scenario. |
| `outcome` | text | An outcome key of A1 (`lowest_altitude`, `lowest_battery_charge`, ...). The schema keeps the list and each unit (`MONTE_CARLO_OUTCOMES`), in step with `engine/run_summary.py` (a test checks it). |
| `at_least` or `at_most` | number | The limit, in the outcome's unit. Exactly one of the two. |
| `confidence` | number in (0, 1) | The confidence of the bound. Required; no default in the code (MC-5). |
| `max_probability` | number in [0, 1), optional | The allowed probability of not meeting the requirement. |

**Statistics** (MC-5). With N evaluated runs and k runs that do not
meet the requirement:
- the estimate is k/N;
- the bound is the one-sided Clopper-Pearson upper limit: the
  probability p at which the binomial probability of k or fewer
  failures in N runs equals 1 - C. Source: C. J. Clopper and E. S.
  Pearson, "The use of confidence or fiducial limits illustrated in the
  case of the binomial", Biometrika 26(4), 1934, pp. 404-413. It is
  computed by bisection on the binomial sum (`math.lgamma`, no table, no
  SciPy). For k = 0 it equals 1 - (1 - C)^(1/N), which a test checks.
- The method is registered as a model choice,
  `monte_carlo.probability_bound`, with one model, `clopper_pearson`
  (`config/models.py`), so a later model can be added.

**Crashed runs** (MC-6). A run that raised an error has no outcome. It
counts as not meeting every requirement, and the table shows how many of
the k are crashed runs. This is the conservative reading; question Q1
asks the owner.

**Missing outcomes.** A successful run without the outcome (the run did
not record its source) is "not evaluated" and is shown in its own
column; it is not in N.

**GUI.**
- Scenario tree › Monte Carlo: a "Requirements" list under the
  dispersions, with the same list-and-form pattern
  (`gui/monte_carlo_editor.py`). The outcome is a combo box of the
  outcome labels with units.
- Results › Monte Carlo: a "Requirements" tab, a `DataTable`:
  requirement, limit with unit, evaluated, not met (of which crashed),
  estimate, upper bound at C, allowed, verdict (icon and text, never
  colour alone). A tile "Requirements met: m of r" when any has an
  allowed probability.
- Runs table: a column "Meets all requirements" (yes, no, not
  evaluated).

**CLI.** `monte-carlo` prints the requirements table. The exit code is 5
(ICD-02 "the command ran and its check did not pass") when a requirement
with `max_probability` is not shown met; 3 (a run failed) still comes
first (MC-10).

**File format.**
- Scenario schema 5 to 6: the optional `monte_carlo.requirements` list.
  The migration only sets the version, as B-01 did for 5 (commit
  `9bc3937`): the templates' `schema_version` line changes,
  `tests/data/scenario_hashes.json` is recorded again,
  `docs/changes.md` says why, the golden outputs do not change.
- Summary JSON: the optional key `requirements` (the definitions the
  batch was run with), so an opened batch reads the same later, as
  `spread_statistic` does. The verdicts are computed when the batch is
  read, from the stored outcomes.

**Acceptance.**
- A version 5 file opens unchanged and records no migrated value.
- A requirement on an unknown spacecraft or outcome, with both or
  neither of `at_least` and `at_most`, or with a confidence outside
  (0, 1), is refused with a message that names the field.
- The bound for (k, N, C) matches the closed form for k = 0, is
  monotonic in k and C, and equals 1 for k = N.
- A batch with a crashed run counts it in k and shows it apart.
- Golden files byte-identical (templates 09 and 25 have no
  requirement).

**Tests.** `tests/test_scenario_schema.py` (fields, validation,
migration 5 to 6); a new `tests/test_monte_carlo_requirements.py`
(evaluation, bound, crashed and not-evaluated runs, the summary round
trip); `tests/test_model_registry.py` (the new model);
`tests/test_cli.py` (exit codes 0, 3 and 5);
`tests/gui/test_monte_carlo_editor.py` and
`tests/gui/test_monte_carlo_results_widget.py` (form round trip, the
Requirements tab, an empty state with its action).

### A3. Reproduce one case (3 h)

**What.** Any case of a batch, successful or crashed, runs again as a
normal run and opens in Results with every series, the events and the
Overview. A crashed case shows its error in full.

**How** (MC-7).
- `engine.monte_carlo.replay_case(scenario, archive_dir, case,
  allow_scripts)`: build the run as `_create_sim` does, read
  `run<case>.json` (JSON, written by Basilisk before the case ran; never
  the pickles), apply each entry in the file's order with Basilisk's
  `SimulationExecutor.applyModification` (2.12.0
  `Controller.py:1076`; the same call the controller makes), then
  `SimulationService.initialize()` and the run or the Mission Sequence.
  It returns the `ResultSet`.
- It refuses when the scenario's hash differs from the batch's
  (`archive.provenance.json`, `scenario_sha256`), naming both (Q3).
- The run's provenance gets `monte_carlo_case`: the batch folder, the
  case number and the batch's scenario hash.
- GUI: "Run this case" on the Runs table (button and context menu,
  shortcut in the tooltip). It runs in the normal run worker (no
  `Controller`, so the signal limit of `gui/monte_carlo_process.py` does
  not apply) and opens like any run.
- CLI: `monte-carlo SCENARIO --archive-dir DIR --case N [--out-dir D]`
  runs that case only and writes what `run --out-dir` writes.
- API: `api.monte_carlo_case(scenario, archive_dir, case)`.

**File format.** CLI flag `--case`; the run record's new
`monte_carlo_case` key. No scenario change.

**Acceptance.**
- For a 2-run batch of template 25 (0.05 days), the replayed case's
  position agrees with the batch summary at every kept sample to
  1e-6 m, for both cases (`thread_count` 1 and 2).
- A changed scenario is refused with both hashes in the message.
- A crashed case (forced in a test) raises its own error.

**Tests.** `tests/test_monte_carlo.py` (replay equals the batch, hash
refusal, missing case file); `tests/test_cli.py` (`--case`);
`tests/test_api.py`; `tests/gui/test_monte_carlo_results_widget.py`
(the action is there, disabled without a selection).

### A4. Draws of crashed runs (1 h)

**What.** `collect_batch` also reads `run<N>.json` of each crashed or
unfinished run (JSON, safe) and keeps its drawn values as
`failed_drawn`. The Runs table lists those runs with their draws and the
status "crashed", outcomes empty. A cancelled batch's unfinished cases
stay out (they did not fail).

**File format.** Summary JSON: the optional key `failed_drawn`.

**Acceptance and tests.** A forced crash in a 2-run batch shows its
draws in the table and the CSV (`tests/test_monte_carlo.py`,
`tests/gui/test_monte_carlo_results_widget.py`); `run_table`'s default
output is unchanged.

### Phase A records

`docs/DECISIONS.md` (the MC section, updated with what was built),
CHANGELOG "Unreleased", User Manual section 10 and the how-to (then
`scripts/sync_help.py`), `docs/models/monte-carlo-statistics.md` (the
bound), `scripts/build_field_help.py` and
`scripts/build_config_defaults.py` outputs, the ICD (scenario fields,
CLI, ICD-02), `compliance/tools/build_test_specs.py`, HISTORY.

## 5. Phase B: insight and trust (about 18 hours)

| Item | What | Acceptance | Hours |
|---|---|---|---|
| B1 Batch seed (K-24) | Optional `monte_carlo.seed`. Empty: today's draws (golden files unchanged). Set: the creation function reseeds NumPy and `random` from the seed and the value Basilisk's own seeding gives that run, before the service is built. Recorded in the provenance. | Two seeds give different draws; one seed gives the same draws twice; no seed gives today's draws; replay (A3) still matches. | 2 |
| B2 Sensitivity | Rank correlation of each drawn value with each outcome, a table sorted by its size, a scatter plot of the selected pair. Model choice `monte_carlo.sensitivity_measure`: `spearman` (C. Spearman, "The proof and measurement of association between two things", American Journal of Psychology 15(1), 1904, pp. 72-101) and `pearson`. NumPy only, ties ranked by their mean rank. | Known monotonic and unrelated inputs give values near +1, -1 and 0 in a synthetic test; the plot follows the theme. | 3 |
| B3 Outcome statistics | Per outcome: minimum, percentiles, maximum, and the empirical distribution as a step plot. Percentile method as a model choice `monte_carlo.percentile_method`, first model NumPy's default `linear` (R. J. Hyndman and Y. Fan, "Sample quantiles in statistical packages", The American Statistician 50(4), 1996, pp. 361-365, definition 7). Which percentiles to show is a parameter with a value from the owner (TBD). The "mean ± 3 sigma" lines of the thermal and operations batches get a label that says what they are, or give way to percentile lines (Q8). | Percentiles equal `numpy.percentile` with the chosen method; the step plot ends at 1. | 2.5 |
| B4 Thermal against node limits | For each node with limits, the runs that leave the operating and the survival range, the estimate and the A2 bound at a confidence the user gives in `thermal.monte_carlo`. | A synthetic batch with known exceedances gives the expected counts. | 2 |
| B5 Batch report | "Export report..." and `monte-carlo --report FILE`: JSON (and Markdown) with the settings, the dispersions, the requirements and verdicts, the outcome statistics, the sensitivity, the crashed cases and the provenance. | The report's numbers equal the view's; a test reads it back. | 3 |
| B6 Trust checks | A finding when a dispersion's mean or bounds do not contain the spacecraft's nominal value (dry mass, Cd, Cr). Opening a batch whose scenario hash differs from the open scenario says so. | Both shown in tests; no false finding on the templates. | 1.5 |
| B7 CLI | `monte-carlo --summarize DIR` (print and write the Runs CSV of an earlier batch), `--runs N`, `--processes N` (they override the file for this batch and are recorded in the provenance). | Tests for each flag; the file is not changed. | 1.5 |
| B8 Small fixes | "Thread count" becomes "Processes"; the "Failed" tile shows a count, the indices go to the table; the starting attitude in deg in the form (the file keeps rad, the form converts). | GUI tests; `docs/ui/TEST_CHANGES.md` if a test reaches a widget another way. | 1 |
| B9 A template | A requirement on template 25, or a new template 37 that shows the phase A and B features (Q7). | Golden files: as the owner decides. | 1 |

**File format in phase B.** Scenario: `monte_carlo.seed` (optional) and
the thermal Monte Carlo's `confidence` (optional): one schema step, 6 to
7, version only, unless the owner folds B1 into phase A's step (Q2).
Summary JSON: optional `seed`. A new report file (`kind:
monte_carlo_report`). CLI: `--summarize`, `--report`, `--runs`,
`--processes`. Parameters and models: `monte_carlo.sensitivity_measure`,
`monte_carlo.percentile_method`, the percentiles shown.

## 6. Phase C: more dispersions and outcomes (about 30 hours, each with a spike)

| Item | What | Hours |
|---|---|---|
| C1 More dispersions | Maneuver execution errors of the Mission Sequence's impulsive and Lambert burns (magnitude and direction), thruster force and misalignment, reaction-wheel friction and bias, propellant load, centre-of-mass offset, atmospheric density (a scale on the density or on F10.7 and Ap). Each mapped to a path or a setting that Basilisk 2.12.0 and the app's own models provide, checked by reading the code first. Maneuver errors need the Mission Sequence to draw them, as the Controller cannot reach a command. | 8 to 12 |
| C2 Custom outcomes | `monte_carlo.outcomes`: any recorded series of a spacecraft with a reduction (minimum, maximum, maximum of the magnitude, final, mean), for example the largest pointing error or wheel speed. Usable in requirements. | 4 |
| C3 Convergence and more cases | The running estimate and bound against the number of runs; "add M cases" to a batch. Basilisk numbers the cases from 0, so adding cases needs a spike (`runInitialConditions`, `Controller.py:381`, or a second batch merged by case number). | 4 |
| C4 Envelopes over time | Percentile bands of a retained series over time (the thermal and operations batches first). | 3 |
| C5 Other sampling | Latin hypercube or other stratified designs. The app would draw the values and give them to Basilisk as initial conditions. Needs a spike; value only for expensive runs. | 10 |

**File format in phase C.** New dispersion quantities and
`monte_carlo.outcomes` in the scenario (a schema step: an older version
refuses an unknown quantity). The summary NPZ may hold per-run reduced
series. Each with its own decisions.

## 7. File format changes, per phase

| Phase | Scenario file | Batch summary | Other outputs | CLI and API |
|---|---|---|---|---|
| A | Schema 6: `monte_carlo.requirements` (optional). Version-only migration. | Format 1 kept; optional keys `outcomes`, `outcome_units`, `requirements`, `failed_drawn`. | Runs CSV: outcome and status columns. Run record: `monte_carlo_case`. | `monte-carlo --case`, `--out-dir`; exit code 5; `api.monte_carlo_case`. |
| B | Schema 7 (or 6, Q2): `monte_carlo.seed`; thermal Monte Carlo `confidence`. | Optional `seed`; thermal limit counts. | The batch report (JSON, Markdown). | `--summarize`, `--report`, `--runs`, `--processes`. |
| C | New dispersion quantities; `monte_carlo.outcomes`. | Reduced series per run. | — | as needed. |

**Why each change.** A requirement belongs to the scenario, so it is
shared and kept with the dispersions it is judged against. A version
step marks files that older versions would refuse by an unknown key, as
5 did. The summary keeps format 1 because each new key is optional: an
older version opens a new batch and ignores what it does not know, and a
new version opens an old batch without them.

## 8. Risks

- **R1 Basilisk's Monte Carlo internals.** Phase A uses three public
  points of Basilisk 2.12.0: `addRetentionFunction`, the order of
  `run<N>.json` entries, `SimulationExecutor.applyModification`. B1 also
  relies on the order "seed, create, disperse" (`Controller.py:790-830`).
  A new Basilisk can change them. The tests in A1, A3 and B1 fail if
  they do; `docs/developer/upstream-sync.md` should name them.
- **R2 Missing outcomes.** A figure exists only when the run recorded
  its source. A requirement on it is then "not evaluated" for that run;
  the view must show it, or users read a too-small N.
- **R3 Golden files.** `run_table`'s default, `final_spread` and
  `summary_lines` must not change; the outcomes and requirements are
  added beside them. A test guards each.
- **R4 Run time.** Each case now extracts events and figures. No target
  is set from thin air: A1 measures the time per case on template 25
  before and after and records both.
- **R5 Misreading few runs.** With 20 runs and no failure the estimate
  is 0, but the 95 % bound (if the user picks C = 0.95) is about 0.139
  (1 - 0.05^(1/20)). The view must put the bound next to the estimate.
- **R6 Unattended backlog runs.** An item that needs an owner's choice
  stops in "Needs human". The phase A items name their defaults (MC-5 to
  MC-10) so that they can run; Q1 to Q5 change them only if the owner
  answers before.
- **R7 Replay across processes and platforms.** A3's identity check
  runs on Linux in the suite; Windows CI runs it too. A difference there
  is a finding, not a tolerance to widen.

## 9. Open questions for the owner

- **Q1** A crashed run: count it as not meeting every requirement
  (proposed, MC-6), or leave it out of N?
- **Q2** One schema step for phase A (requirements) and B1 (the seed),
  by doing B1 in phase A (+2 h), or two steps (proposed)?
- **Q3** Replaying a case when the scenario changed since the batch:
  refuse (proposed, MC-7), or run it with a warning?
- **Q4** The confidence of a bound: given by the user per requirement,
  with no default (proposed, MC-5), or a project parameter with a
  default the owner names?
- **Q5** Exit code 5 from `monte-carlo` when a requirement is not shown
  met (proposed, MC-10): acceptable for scripts that call it today?
- **Q6** Phase C: which dispersions first (maneuver errors, thrusters,
  wheels, density)?
- **Q7** A template for the new features: change template 25 (its
  golden file changes) or add template 37?
- **Q8** Thermal and operations batches: keep the "mean ± 3 sigma"
  lines with a clear label, or replace them by percentile lines (B3)?
  Which percentiles should the view show?

## 10. Progress

| Step | State |
|---|---|
| 0 Investigation, plan, decisions, backlog | done (this page) |
| A-1 Outcomes, draws of crashed runs, requirements | done (`feature/monte-carlo-outcomes`, 2026-11-21; DECISIONS MC-11 to MC-16) |
| A-2 Reproduce one case | backlog |
| B | later |
| C | later |

---

**Next:** [Decisions](../DECISIONS.md) · [Backlog](../../BACKLOG.md) ·
[Developer guide](README.md)
