# Backlog

## Next release

- Make CI's reference-data downloads survive a short outage of the
  source. On 2026-11-22 the ITU server answered HTTP 404 for the
  ITU-R P.676-13 data file for a few minutes, and CI on `develop`
  stopped before any test (2.14.0; SRelD issue 50). A re-run passed.
  Retry each download a few times with a pause, or keep a copy that CI
  checks against the file's recorded SHA-256 and uses when the source
  does not answer. Do not skip the step: the tests need the files.
- Import pandas off the GUI thread before a Monte Carlo batch or case.
  `MonteCarloWorker` and, since phase A (#307), `RunWorker` for a case
  import pandas on the GUI thread before they start, for an earlier
  import race with plotly on Windows. It takes about 280 ms once per
  process (measured 2026-11-21), above the 50 ms rule. Since K-44 the
  heavy first imports hold `background_threads.FIRST_IMPORTS`; import
  pandas in the worker under that lock instead, and add a test that the
  first batch or case start keeps the GUI thread under 50 ms.
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
  background-thread crashes (K-44)"). Two faults were not reproduced and
  have no cause yet:
  - Windows CI on #297: the child process of
    `test_results_widget.py::test_the_figure_warm_up_loads_what_the_first_plot_needs`
    ended with 0xC0000005 and empty stdout and stderr. It has no Python
    worker thread; it passed eight runs in eight on Linux.
  - A template wizard test reported "Slot 'MainWindow::' not found". No
    log of that run was found. A clue (2026-11-21, Monte Carlo phase A):
    the same kind of message, "Slot 'EmptyStack::' not found", appears
    when `widgets.EmptyStack` gets a list model's reset while the list
    is being destroyed, when that list is the first widget of a test
    process. It also happens on `develop`. The Monte Carlo editor's
    Requirements list so switches its empty state itself (DECISIONS
    MC-16). Look for a slot of a destroyed QObject that a model's reset
    still reaches.
  Needs a human: watch CI after this fix. If either fault comes back,
  keep the job's log and add it to K-44. The child process prints no
  stack today; a decision to run it with `-X faulthandler` would change
  that test.
