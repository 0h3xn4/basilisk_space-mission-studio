# Backlog

## Next release

## Later

Not for an unattended run: these wait until phase A is done and the
owner has answered the plan's open questions.

- A pointing error budget, scope C: the absolute, relative and mean
  performance errors measured from a run's attitude error series over
  each requirement's windows, next to the budget's value (design
  section 4; about 12 hours). After scope B. Scope D (over a Monte
  Carlo batch) follows C.

- Monte Carlo phase C: more dispersions and outcomes
  (`docs/developer/monte-carlo-plan.md` section 6; about 30 hours, each
  item with a spike first). In the owner's order (MC-36): maneuver
  execution errors of the Mission Sequence's burns, thruster force and
  misalignment, reaction-wheel friction and bias, propellant load and
  centre of mass (the atmospheric density is done); then outcomes from
  any recorded series; convergence and adding cases to a batch;
  percentile bands over time; other sampling designs.
- A uniform dispersion of the dry mass, the drag coefficient or the SRP
  coefficient with equal bounds fails every run of the batch
  (`ZeroDivisionError` in Basilisk 2.12.0's `UniformDispersion.generate`,
  which divides by the half-width). The form starts a new dispersion at
  [nominal, nominal], so an untouched new one crashes the batch. Found
  while building the density scale, which has its own fix
  (`engine.monte_carlo._UniformDensityScale`, MC-38); the same subclass
  idea fits the other three. Reproduced on template 25 (0.001 day, one
  run, dry mass uniform [150, 150]: run 0 failed).

## Done

- A pointing error budget, scope B (the owner's answers of 2026-11-24
  to `docs/developer/pointing-error-budget-design.md` section 7), on
  branch `feature/pointing-budget` (2026-11-24). Budgets › Pointing after
  Mass: requirements and contributors entered by hand, the sum per index
  and axis, the value at the requirement's probability (no default
  probability: "TBD"), the margin with its status, a line-of-sight
  (half-cone) value, the window share for periodic contributors, the
  scenario's star trackers, gyroscopes and sun sensors as knowledge
  contributors with their sources, `budgets --pointing` and
  `api.pointing_budget`. Budgets section version 2 with a migration; no
  template or golden file changed. Decisions PE-10 to PE-20; SRS-F-32.
- Monte Carlo phase C, item 1: the atmospheric density dispersion, on
  branch `feature/monte-carlo-density` (2026-11-24). The owner's order
  of the phase C dispersions (Q6) is recorded as MC-36. A spike
  (`docs/developer/monte-carlo-plan.md` §6.1) chose a scale on the
  density that drag reads, between the atmosphere model and the drag, so
  it works with the three atmosphere models and with facets. New
  quantity `density_scale` (no spacecraft), scenario schema 8 with a
  version-only migration, the form, the summary, the Runs table, its CSV
  and the report. Decisions MC-37 to MC-40; the owner confirmed
  MC-37's meaning on 2026-11-24 (Q9: no F10.7 and Ap dispersion).
- Make the move of the 3D View into its own window, or back, take under
  50 ms of the GUI thread on the Windows runner, every time (SRelD K-40),
  on branch `fix/3d-view-move` (2026-11-24). Not the move's own work (3
  to 5 ms) and no native window made again: the GUI thread waited for a
  processor. After a move the page draws in software (WARP on the
  runner) on every processor, with threads at "above normal" priority,
  and the GUI thread was at "normal". The GUI thread now has their
  priority (its workers take it from it, as before), and the page draws
  each new size once. On the Windows runner the slowest of 60
  moves of the 3D View took 13.6 ms (56.2 ms before in 16). Measured:
  HISTORY.md and `docs/DECISIONS.md`, "The GUI thread outranks the 3D
  View's software drawing".
- Find and fix the test that sometimes made a local suite run hang
  (2026-11-23), on branch `fix/suite-hang`. The cancel test of a batch
  with 2 processes: Cancel's thread ended the processes in its list, but
  Basilisk's process pool started a new worker meanwhile, which outlived
  the batch with the resource tracker and kept the run's output open.
  The batch's child now has a process group of its own (a job on
  Windows) that ends with it. Measured: HISTORY.md and
  `docs/DECISIONS.md`, "A cancelled Monte Carlo batch leaves no process".
- Monte Carlo phase B, parts 2 and 3: the outcome statistics, the
  sensitivity and the trust checks (B2, B3, B6) on branch
  `feature/monte-carlo-insight`, decisions MC-26 to MC-31; the batch
  report (B5), `monte-carlo --summarize`, `--report`, `--csv`, `--runs`
  and `--processes` (B7) and template 37 (B9) on branch
  `feature/monte-carlo-report`, decisions MC-32 to MC-35 (2026-11-23).
  Phase B is done when the three parts are merged.
- Monte Carlo phase B, part 1: the batch seed (B1, SRelD K-24), the
  thermal Monte Carlo against the node limits (B4) and the small fixes
  (B8), on branch `feature/monte-carlo-seed` (2026-11-23). Optional
  `monte_carlo.seed` and thermal `confidence` at schema version 7; the
  Node limits tab and table; "Processes"; the Failed tile as a count;
  the starting attitude in degrees in the form. Decisions MC-20 to
  MC-25.
- Make the Budgets area quicker to show on a slow Windows machine
  (SRelD K-40), on `develop` at `29bbdb5` (2026-11-23). The cause: the
  Equipment page's word-wrapped note made the area's page say that its
  height follows its width, and Qt's stacked layout then asked every
  area's page, the hidden ones too, at each show. `shell.AreaPage` now
  says it does not. On Linux the area shows in about 1 ms (8 to 11 ms
  before), a move takes 3 to 5 ms (10 to 12 ms). The move test's limit is
  a plain 50 ms again, and it passed on the Windows runner (CI run
  45109373728). What the window shows is unchanged (82 grabs). Records:
  `docs/DECISIONS.md`, `docs/ui/TEST_CHANGES.md`. Only partly met: on
  the 2.14.2 release run's Windows runner the 3D View's move took 64.0
  and 72.7 ms (the item under "Next release").
- 2.14.1 small fixes, on branch `fix/2.14.1-small` (2026-11-22). pandas
  is imported in the batch's or the case's worker with
  `FIRST_IMPORTS` held, and the plots wait for that import (the first
  start: 258-271 ms of the GUI thread before, under 1 ms now). CI runs
  each reference data download through `scripts/retry_download.py`
  (four attempts, 60 s apart). "Slot '...::' not found" of K-44 has its
  cause and fix (below, and HISTORY.md, "2.14.1: small fixes").
- Monte Carlo phase A, part 2: run one case again (A3), on branch
  `feature/monte-carlo-rerun-case` (2026-11-21, based on
  `feature/monte-carlo-outcomes`). Run This Case in Results › Monte
  Carlo › Runs (Ctrl+Shift+R, the palette, the right-click menu),
  `monte-carlo --case N [--out-dir D]` and `api.monte_carlo_case`. The
  case agrees with the batch summary to 0.0 m at every kept sample for
  a 2-run batch of template 25 with one and with two processes. The
  owner's answer to Q3 is the provisional decision MC-17 (refuse when
  the scenario changed since the batch); the build choices are MC-18.
- Monte Carlo phase A, part 1: outcomes (A1), crashed runs' draws (A4)
  and requirements (A2), on branch `feature/monte-carlo-outcomes`
  (2026-11-21). Each run keeps its Overview figures; the summary keeps
  the draws of crashed runs; `monte_carlo.requirements` at schema
  version 6; the Requirements tab, the CLI table and exit status 5. The
  owner's answers to Q1, Q2, Q4, Q5 and Q8 are applied as provisional
  decisions (`docs/DECISIONS.md`, MC-11 to MC-16). Time per case of
  template 25: HISTORY.md, "Monte Carlo phase A, part 1".

## Needs human

- The rest of SRelD K-44 (fix/k44-thread-crashes, 2026-11-20). The
  access violation in `_SpaceWeatherWarmUp` and the export test's
  segmentation fault had one cause, now fixed: a garbage collection in a
  worker thread destroyed widgets of the GUI thread (HISTORY.md, "2.13.1:
  background-thread crashes (K-44)"). "Slot 'MainWindow::' not found"
  has a found cause and a fix in 2.14.1: the collector deleted a child
  before its owner, and the child's last signal reached the half-freed
  owner (reproduced with "Slot 'EmptyStack::'" and with a window's view
  tabs; the CI run itself has no log). One fault was not reproduced and
  has no cause yet:
  - Windows CI on #297: the child process of
    `test_results_widget.py::test_the_figure_warm_up_loads_what_the_first_plot_needs`
    ended with 0xC0000005 and empty stdout and stderr. It has no Python
    worker thread; it passed eight runs in eight on Linux.
  Needs a human: watch CI. If the 0xC0000005 or a "Slot '...::' not
  found" comes back, keep the job's log and add it to K-44. The child process prints no stack today; a
  decision to run it with `-X faulthandler` would change that test.
