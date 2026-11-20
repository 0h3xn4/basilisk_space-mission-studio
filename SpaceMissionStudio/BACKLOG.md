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
