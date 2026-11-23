# Backlog

## Next release

- Make the move of the 3D View into its own window, or back, take under
  50 ms of the GUI thread on the Windows runner, every time (SRelD K-40,
  partly met). In the release workflow's run 45148067729, attempt 1, on
  `452e164` (the 2.14.2 tag), the Windows job failed
  `tests/gui/test_breakout.py::test_detach_and_attach_take_under_50_ms_on_the_gui_thread`:
  the 3D View's slowest move took 64.0 ms, and 72.7 ms when the test
  timed it again. The same test passed on the same commit in CI run
  45143562273 (Windows runner). So the move sits at the limit. Find the
  cause of the time in the 3D View's move, and fix it in the app. Do
  not loosen the test: its limit stays a plain 50 ms. Done when the
  move test passes on the Windows runner with every view under 50 ms.
  If the cause is QtWebEngine's own reparenting and no change in the app
  helps, move this item to `## Needs human` with the measurements.

## Later

Not for an unattended run: these wait until phase A is done and the
owner has answered the plan's open questions.

- Monte Carlo phase B, the rest: insight and trust
  (`docs/developer/monte-carlo-plan.md` section 5; part 1, B1, B4 and
  B8, is done, below). Sensitivity by rank correlation with a scatter
  plot, outcome percentiles and the empirical distribution, a batch
  report (JSON and Markdown), checks that a dispersion contains the
  nominal value and that an opened batch matches the scenario, CLI
  `--summarize`, `--report`, `--runs` and `--processes`, and a template
  for the new features.
- Monte Carlo phase C: more dispersions and outcomes
  (`docs/developer/monte-carlo-plan.md` section 6; about 30 hours, each
  item with a spike first). Maneuver execution errors, thruster and
  reaction-wheel errors, propellant load, centre of mass and
  atmospheric density; outcomes from any recorded series; convergence
  and adding cases to a batch; percentile bands over time; other
  sampling designs.

## Done

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

- A pointing error budget: the owner's choice of scope (the owner's
  feedback, 2026-11-18). The design and its provisional decisions are on
  `develop` at `39da9d7` (2026-11-23):
  `docs/developer/pointing-error-budget-design.md` and
  `docs/DECISIONS.md`, PE-1 to PE-9. Clean room from the public concepts
  of ECSS-E-ST-60-10C; every number has a source or is "TBD"; no code.
  Needs a human: answer the design's section 7 (scope A, B, C or D, with
  B recommended; the default probability level; line of sight; periodic
  contributors; the place in the app). Then the chosen scope can be a
  "Next release" item.

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
