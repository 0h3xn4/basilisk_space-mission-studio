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
- Make the small plot items clear (UI audit, 2026-11-19; SRelD K-46): the event
  bands share hues with the plotted lines; some Timeline events use the
  accent colour, which is only for the primary action, selection and
  focus; an angle that is nearly constant gets long tick labels; the
  reaction wheel lines are labelled "wheel_0" instead of the wheel's
  name. The exported files must not change.
- Run › Thermal › Notes: "Energy residual [J]" mixes significant
  figures (5.11e+03 and 4.9e+03). Give the column one number of
  significant figures, as the design rules ask for one quantity.
- Budgets › Power: with the Inspector open at 1280 px, the items table
  scrolls inside itself. Make it fit the page, as the other Budgets
  grids do since B12, and add a test at 1280 px with the Inspector open.
- Three small window items seen while 2.13.0 was prepared. Home's
  template cards show "--" in some descriptions, although B4 writes a
  dash as "–". The thermal sweep table scrolls sideways at 1280 px. The
  heater energy heading reads "W·h"; write the unit as the other
  energy columns do. Change only what the window shows; the scenario
  files and the exported files must not change.
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
