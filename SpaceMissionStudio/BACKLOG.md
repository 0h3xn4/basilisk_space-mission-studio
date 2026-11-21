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
- Monte Carlo phase A, part 1: outcomes, crashed runs' draws and
  requirements (`docs/developer/monte-carlo-plan.md` section 4, items
  A1, A4 and A2; decisions MC-1 to MC-6, MC-9 and MC-10 in
  `docs/DECISIONS.md`; about 8.5 hours). Each run keeps its Overview
  figures as outcomes (through `RetentionPolicy.addRetentionFunction`);
  the summary keeps the draws of crashed runs; the scenario gets
  `monte_carlo.requirements` (schema version 6, a migration that only
  sets the version, as B-01 did); the Monte Carlo view and the CLI show,
  per requirement, the runs that do not meet it, k/N and the one-sided
  Clopper-Pearson upper bound at the requirement's own confidence.
  `monte-carlo` exits with 5 when a requirement with an allowed
  probability is not shown met. Done when the plan's acceptance criteria
  for A1, A2 and A4 pass, the golden files are byte-identical, and the
  time per case of template 25 before and after is in HISTORY. If the
  owner has answered Q1, Q4 or Q5 of the plan, follow the answer.
- Monte Carlo phase A, part 2: reproduce one case
  (`docs/developer/monte-carlo-plan.md` section 4, item A3; decision
  MC-7; about 3 hours). Any case of a batch runs again from its
  `run<N>.json` as a normal run and opens in Results: "Run this case" on
  the Runs table, `monte-carlo --case N [--out-dir D]`, and
  `api.monte_carlo_case`. Refused when the scenario's hash differs from
  the batch's. Done when the replayed case agrees with the batch summary
  at every kept sample to 1e-6 m for a 2-run batch of template 25 with
  one and with two processes. If the owner has answered Q3, follow the
  answer.

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
    log of that run was found.
  Needs a human: watch CI after this fix. If either fault comes back,
  keep the job's log and add it to K-44. The child process prints no
  stack today; a decision to run it with `-X faulthandler` would change
  that test.
