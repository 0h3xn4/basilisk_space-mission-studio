# Backlog

## Next release

- Make the Budgets area quicker to show on a slow Windows machine
  (SRelD K-40). On the Windows CI runner, moving the area into its own
  window or back takes 50 to 81 ms of the GUI thread; on Linux it takes
  about 10 ms. The time is the `show()` of the area's 435 widgets, and
  no single part dominates. Find what makes the show slow (for example
  widgets that are built or styled at the first show, or pages that are
  not visible but still laid out), make it quicker without changing what
  the area shows, and add a test that measures the show of the area in
  place. Done when `test_breakout.py::test_detach_and_attach_take_under_50_ms_on_the_gui_thread`
  passes on the Windows runner with every view under 50 ms; then make
  that test's limit a plain 50 ms again (drop the "twice the show time
  plus 10 ms" rule) and record the change in `docs/ui/TEST_CHANGES.md`. If the cause is Qt's own drawing on the
  runner and no change in the app helps, move the item to
  `## Needs human` with the measurements.
- A pointing error budget (the owner's feedback, 2026-11-18). Checked on
  2026-11-19: the app has none. The Budgets area has mass, power and
  propellant; the System Budget Studio merge plan
  (`docs/developer/system-budget-merge-design.md`, phase 4) ports only
  the hold power per pointing mode. Design it clean-room, from the
  public concepts of ECSS-E-ST-60-10C (the error indices such as
  absolute and relative performance and knowledge errors, the
  contributors and their statistical classes, the summation rules).
  Never copy another tool's name, user interface, files or numbers.
  Every number has a source or is a placeholder ("TBD"). Write the
  design and the decisions first; the item needs the owner's choice of
  scope before code, so move it to `## Needs human` with the design.

## Later

Not for an unattended run: these wait until phase A is done and the
owner has answered the plan's open questions.

- Monte Carlo phase B: insight and trust
  (`docs/developer/monte-carlo-plan.md` section 5; about 18 hours).
  The batch seed (SRelD K-24), sensitivity by rank correlation with a
  scatter plot, outcome percentiles and the empirical distribution,
  thermal Monte Carlo runs against the node limits, a batch report
  (JSON and Markdown), checks that a dispersion contains the nominal
  value and that an opened batch matches the scenario, CLI
  `--summarize`, `--report`, `--runs` and `--processes`, small label
  fixes, and a template for the new features.
- Monte Carlo phase C: more dispersions and outcomes
  (`docs/developer/monte-carlo-plan.md` section 6; about 30 hours, each
  item with a spike first). Maneuver execution errors, thruster and
  reaction-wheel errors, propellant load, centre of mass and
  atmospheric density; outcomes from any recorded series; convergence
  and adding cases to a batch; percentile bands over time; other
  sampling designs.

## Done

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
