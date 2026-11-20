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
- Find the cause of the intermittent crashes around background threads
  (SRelD K-44). Seen on 2026-11-19, none reproduced on demand:
  - Windows CI, the platforms job's 3D step (`test_live_run_3d`): an
    access violation in the thread `_SpaceWeatherWarmUp` during a
    garbage collection, while `_FigureWarmUp` imported plotly and
    `RunWorker` imported `engine.service`;
  - Linux CI, one xdist worker: a segmentation fault in
    `tests/gui/test_results_widget.py::test_an_export_runs_off_the_gui_thread_with_progress_and_cancel`;
  - a template wizard test: the Qt error "Slot 'MainWindow::' not found".
  Investigate them as one item. Serialize the warm-up imports (one
  warm-up thread, or import plotly and the engine on the GUI thread at
  start) and check for a CPython 3.14 import or garbage-collection
  problem. Also check every other QObject that keeps Python state while
  only a Python attribute refers to it, as the toast follower did (B11
  follow-up). Add a test that fails without the fix where one can be
  made; otherwise record the measurements and move the item to
  `## Needs human`.
- Make the small plot items clear (UI audit, 2026-11-19; SRelD K-46): the event
  bands share hues with the plotted lines; some Timeline events use the
  accent colour, which is only for the primary action, selection and
  focus; an angle that is nearly constant gets long tick labels; the
  reaction wheel lines are labelled "wheel_0" instead of the wheel's
  name. The exported files must not change.
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

## Done

## Needs human
