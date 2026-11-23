#
#  SpaceMissionStudio
#
#  Licensor: 0h3xn4 (https://github.com/0h3xn4)
#
#  Licensed under the EUPL
#
#  SPDX-License-Identifier: EUPL-1.2
#
#  The European Union Public Licence v. 1.2 is in the files LICENSE
#  (English) and LICENSE.de (German) of the SpaceMissionStudio folder and
#  of every package. Third-party components, each under its own licence,
#  are listed in THIRD_PARTY_NOTICES.
#
#
#
#

"""The Monte Carlo view of the Results tab: a batch's tiles, plots and run
table, from its pickle-free summary; and when the main window shows the view."""

import csv
import math
from pathlib import Path

import numpy as np
import pytest

from spacemissionstudio.gui.widgets import layout_item_widgets

pytestmark = pytest.mark.requires_gui

_R_M = 6778.0e3  # [m]
_N_RAD_S = math.sqrt(3.986004415e14 / _R_M ** 3)  # [rad/s]


def _save_batch(folder, runs=5, names=("sat-1",)):
    """A synthetic batch: circular orbits 0.1 mrad apart along track, run k
    drawing Cd = 2.0 + 0.2 k, saved as engine.monte_carlo_results does."""
    from spacemissionstudio.engine import monte_carlo_results as mcr

    t = np.linspace(0.0, 3000.0, 30)  # [s]
    phase = (np.arange(runs) - (runs - 1) / 2) * 1e-4  # [rad]
    u = _N_RAD_S * t[None, :] + phase[:, None]
    r = np.stack([_R_M * np.cos(u), _R_M * np.sin(u), np.zeros_like(u)], axis=-1)
    v = np.stack([-_R_M * _N_RAD_S * np.sin(u), _R_M * _N_RAD_S * np.cos(u), np.zeros_like(u)], axis=-1)
    batch = mcr.MonteCarloBatch("Synthetic batch", "earth", t, list(range(runs)), [runs],
                                {n: r for n in names}, {n: v for n in names},
                                [{f"{names[0]} drag coefficient [-]": 2.0 + 0.2 * k} for k in range(runs)],
                                "2030-01-01T00:00:00")
    mcr.save(batch, folder)
    return batch


def _tile_texts(widget):
    from PySide6.QtWidgets import QLabel

    texts = []
    for tile in layout_item_widgets(widget.tiles_row):
        if tile is not None:
            texts.append(" | ".join(label.text() for label in tile.findChildren(QLabel)))
    return texts


def test_a_saved_batch_shows_tiles_plots_and_a_sortable_run_table(qtbot, tmp_path):
    """Five runs plus one failed: the tiles count them and give the final
    spread, the plots open on the spread, the table lists every run."""
    from spacemissionstudio.gui.monte_carlo_results_widget import MonteCarloResultsWidget

    _save_batch(tmp_path)
    widget = MonteCarloResultsWidget()
    qtbot.addWidget(widget)
    assert widget.load_folder(tmp_path)
    assert widget.title_label.text() == "Synthetic batch"
    tiles = _tile_texts(widget)
    assert tiles[0] == "5 of 6 | Runs" and tiles[1] == "1 | Failed"
    along_km = np.std((np.arange(5) - 2) * 1e-4) * _R_M / 1e3  # [km]
    assert tiles[2] == f"{along_km:.3g} km | Along-track spread, end"
    assert widget.plots.current_series_name() == "sat-1.monte_carlo.spread"
    table = widget.table
    assert table.row_count() == 5
    headers = [table.header_text(c) for c in range(table.column_count())]
    assert headers[:2] == ["Run", "drag coefficient [-]"]  # one spacecraft: its name is not repeated
    from PySide6.QtCore import Qt

    table.sort_by(1, Qt.SortOrder.DescendingOrder)  # by Cd: a numeric sort, not text
    assert [table.cell(r, 0) for r in range(5)] == ["4", "3", "2", "1", "0"]
    assert not widget.spacecraft_combo.isVisible()


def test_the_run_table_exports_to_csv(qtbot, tmp_path):
    """The run table exports to CSV with each run's dispersed values."""
    from spacemissionstudio.gui.monte_carlo_results_widget import MonteCarloResultsWidget

    _save_batch(tmp_path)
    widget = MonteCarloResultsWidget()
    qtbot.addWidget(widget)
    widget.load_folder(tmp_path)
    rows = list(csv.reader(widget.export_table_csv(tmp_path / "runs.csv").open(encoding="utf-8")))
    assert rows[0][:2] == ["Run", "sat-1 drag coefficient [-]"]
    assert [row[0] for row in rows[1:]] == ["0", "1", "2", "3", "4"]
    assert float(rows[3][1]) == pytest.approx(2.4)


def test_a_folder_without_results_says_so_and_shows_nothing(qtbot, tmp_path):
    """A folder without results says so, and nothing is shown or plotted."""
    from spacemissionstudio.gui.monte_carlo_results_widget import MonteCarloResultsWidget

    widget = MonteCarloResultsWidget()
    qtbot.addWidget(widget)
    assert widget.views.isHidden()
    assert widget.plots is None  # no idle web view until there is a batch to plot
    assert not widget.load_folder(tmp_path)
    assert "has no Monte Carlo results" in widget.hint_label.text()
    assert widget.batch is None and widget.views.isHidden() and _tile_texts(widget) == []


def test_several_spacecraft_choose_whose_spread_is_shown(qtbot, tmp_path):
    """With two spacecraft, the list chooses whose spread is plotted and
    tabulated."""
    from spacemissionstudio.gui.monte_carlo_results_widget import MonteCarloResultsWidget

    _save_batch(tmp_path, names=("chief", "follower"))
    widget = MonteCarloResultsWidget()
    qtbot.addWidget(widget)
    widget.load_folder(tmp_path)
    assert not widget.spacecraft_combo.isHidden()
    widget.spacecraft_combo.setCurrentText("follower")
    assert widget.plots.current_series_name() == "follower.monte_carlo.spread"
    assert widget.table.header_text(widget.table.column_count() - 1).startswith("follower final")


def test_the_mouse_wheel_does_not_change_whose_spread_is_shown(qtbot, qapp, tmp_path):
    """The spacecraft choice is a no-wheel drop-down like every other in the
    app: scrolling the tab over it changes nothing."""
    from test_wheel_in_dialogs import _changed_by_wheel

    from spacemissionstudio.gui.monte_carlo_results_widget import MonteCarloResultsWidget

    _save_batch(tmp_path, names=("chief", "follower"))
    widget = MonteCarloResultsWidget()
    qtbot.addWidget(widget)
    widget.load_folder(tmp_path)
    widget.resize(1000, 800)  # [px]
    widget.show()
    qtbot.waitExposed(widget)
    changed, count = _changed_by_wheel(widget, qapp)
    assert count > 0 and not changed, changed


def test_per_run_series_are_drawn_as_one_ensemble(qtbot, tmp_path):
    """Interchangeable runs get one colour, thin translucent lines and a
    single legend entry, and the hover shows the run under the pointer --
    not a colour each from a cycled palette and a 20-row hover box."""
    from spacemissionstudio.gui.monte_carlo_results_widget import MonteCarloResultsWidget

    _save_batch(tmp_path)
    widget = MonteCarloResultsWidget()
    qtbot.addWidget(widget)
    widget.load_folder(tmp_path)
    widget.plots.show_series("sat-1.monte_carlo.along_track_offset")
    fig = widget.plots.figure
    runs = [trace for trace in fig.data if trace.legendgroup == "runs"]
    assert len(runs) == 5
    assert len({trace.line.color for trace in runs}) == 1
    assert [trace.showlegend for trace in runs] == [True, False, False, False, False]
    assert runs[0].name == "Each run (5)" and fig.layout.hovermode == "closest"
    widget.plots.show_series("sat-1.monte_carlo.spread")  # three distinct quantities: a colour and entry each
    assert len({trace.line.color for trace in widget.plots.figure.data}) == 3


def test_the_main_window_shows_the_tab_only_when_it_has_something(qtbot, tmp_path, monkeypatch):
    """The Monte Carlo view, the last of the Results views, is there for a
    scenario with Monte Carlo on, or once a batch is open. It is removed,
    not hidden, otherwise: a hidden tab can still be selected
    programmatically, and selecting one crashed the macOS test run."""
    from PySide6.QtWidgets import QFileDialog

    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR
    from spacemissionstudio.gui.main_window import MainWindow

    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    tabs, tab = window.results_views, window.monte_carlo_results_widget
    assert tabs.indexOf(tab) < 0 and tab.isHidden()
    window.open_path(TEMPLATES_DIR / "09_monte_carlo_dispersion_analysis.json")
    assert tabs.indexOf(tab) == tabs.count() - 1  # the last of the Results views
    window.open_path(TEMPLATES_DIR / "01_two_body_circular_orbit.json")
    assert tabs.indexOf(tab) < 0 and tab.isHidden()

    _save_batch(tmp_path)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args, **kwargs: str(tmp_path))
    window.open_monte_carlo_results_action.trigger()
    assert tabs.indexOf(tab) >= 0 and window.current_view() is tab
    assert tab.folder == Path(tmp_path)
    assert all(tabs.isTabVisible(i) for i in range(tabs.count()))  # no hidden tabs anywhere


def test_the_page_names_the_statistic_of_the_spread(qtbot, tmp_path):
    """Transparency plan, Phase 6a: the line under the title names the
    statistic the batch was run with, its tooltip the formula and the
    parameter that chose it; the tiles use it (sample: divided by N - 1)."""
    from dataclasses import replace

    from spacemissionstudio.engine import monte_carlo_results as mcr
    from spacemissionstudio.gui.monte_carlo_results_widget import MonteCarloResultsWidget

    mcr.save(replace(_save_batch(tmp_path / "first"), spread_statistic="sample"), tmp_path / "sample")
    widget = MonteCarloResultsWidget()
    qtbot.addWidget(widget)
    assert widget.load_folder(tmp_path / "first")
    assert "(population standard deviation)" in widget.hint_label.text()
    assert widget.load_folder(tmp_path / "sample")
    assert "all runs (sample standard deviation): along the orbit" in widget.hint_label.text()
    tip = widget.hint_label.toolTip()
    assert "Sample standard deviation: " in tip and "(N - 1)" in tip and "monte_carlo.spread_statistic" in tip
    along_km = np.std((np.arange(5) - 2) * 1e-4, ddof=1) * _R_M / 1e3  # [km]
    assert _tile_texts(widget)[2] == f"{along_km:.3g} km | Along-track spread, end"


def _save_batch_with_outcomes(folder, requirements=()):
    """``_save_batch``'s five runs with outcomes (the lowest altitude 395 +
    5 k km), run 5 crashed with its draws, and ``requirements``."""
    from dataclasses import replace

    from spacemissionstudio.engine import monte_carlo_results as mcr

    batch = _save_batch(folder)
    batch = replace(batch, outcomes=[{"run_length": 1.0, "sat-1.lowest_altitude": 395.0 + 5.0 * k} for k in range(5)],
                    outcome_units={"run_length": "h", "sat-1.lowest_altitude": "km"},
                    failed_drawn={5: {"sat-1 drag coefficient [-]": 3.0}}, requirements=list(requirements))
    mcr.save(batch, folder)
    return batch


_ALTITUDE = {"name": "R-ALT", "spacecraft": "sat-1", "outcome": "lowest_altitude", "at_least": 400.0,
             "at_most": None, "confidence": 0.9, "max_probability": 0.5}


def test_the_run_table_shows_each_runs_outcomes_and_the_crashed_run_with_its_draws(qtbot, tmp_path):
    """A1 and A4: the Runs table has a column per outcome, after the drawn
    values and the offsets, units in the headers; the crashed run is listed
    with what it drew and the status "crashed", its outcomes empty; with a
    requirement, whether each run meets them all. The CSV is the table."""
    from spacemissionstudio.gui.monte_carlo_results_widget import MonteCarloResultsWidget

    _save_batch_with_outcomes(tmp_path, [_ALTITUDE])
    widget = MonteCarloResultsWidget()
    qtbot.addWidget(widget)
    assert widget.load_folder(tmp_path)
    table = widget.table
    headers = [table.header_text(c) for c in range(table.column_count())]
    assert headers[:2] == ["Run", "drag coefficient [-]"]
    assert headers[5:] == ["Run length [h]", "lowest altitude [km]", "Status", "Meets all requirements"]
    assert table.row_count() == 6
    crashed = [r for r in range(6) if table.cell(r, 0) == "5"][0]
    assert table.cell(crashed, 1) == "3" and table.cell(crashed, 6) == "" and table.cell(crashed, 7) == "crashed"
    assert [table.cell(r, 8) for r in range(6) if table.cell(r, 0) in ("0", "1", "5")] == ["no", "yes", "no"]

    rows = list(csv.reader(widget.export_table_csv(tmp_path / "runs.csv").open(encoding="utf-8")))
    assert rows[0][6:] == ["sat-1 lowest altitude [km]", "Status", "Meets all requirements"]
    assert rows[6][0] == "5" and rows[6][1] == "3" and rows[6][6:] == ["nan", "crashed", "no"]
    assert float(rows[2][6]) == pytest.approx(400.0)


def test_the_requirements_tab_judges_each_requirement(qtbot, tmp_path):
    """A2: the Requirements tab lists each requirement: its limit with the
    unit, the runs evaluated, not met and of them crashed, the estimate,
    the upper bound at its confidence, the allowed probability and the
    verdict (a word behind its icon); a tile counts the requirements met."""
    from spacemissionstudio.engine import monte_carlo_requirements as req
    from spacemissionstudio.gui.monte_carlo_results_widget import MonteCarloResultsWidget

    loose = dict(_ALTITUDE, name="R-LOOSE", at_least=0.0, max_probability=0.9)
    _save_batch_with_outcomes(tmp_path, [_ALTITUDE, loose])
    widget = MonteCarloResultsWidget()
    qtbot.addWidget(widget)
    widget.load_folder(tmp_path)
    assert _tile_texts(widget)[-1] == "1 of 2 | Requirements met"
    table = widget.requirements_table
    assert [table.header_text(c) for c in range(table.column_count())] == list(req.TABLE_HEADER)
    assert table.row_count() == 2
    row = [table.cell(0, c) for c in range(table.column_count())]
    bound = req.clopper_pearson_upper(2, 6, 0.9)  # runs 0 (395 km) and 5 (crashed) of 6
    assert row == ["R-ALT", "Lowest altitude", "at least 400 km", "6", "2", "1", "0", "0.3333", f"{bound:.4g}",
                   "0.9", "0.5", "not shown"]
    assert table.cell(1, 11) == "met"
    assert "Runs not met: 0, 5" in table.cell_tooltip(0, 4)
    assert "Clopper-Pearson" in widget.requirements_hint.toolTip()


def test_without_requirements_the_tab_says_where_to_add_them(qtbot, tmp_path):
    """A batch without requirements (or an older summary) shows the tab's
    empty state; its action asks for the scenario's Monte Carlo settings;
    no tile and no "Meets all requirements" column."""
    from spacemissionstudio.gui.monte_carlo_results_widget import MonteCarloResultsWidget

    _save_batch(tmp_path)
    widget = MonteCarloResultsWidget()
    qtbot.addWidget(widget)
    widget.load_folder(tmp_path)
    table = widget.requirements_table
    assert table.stack.currentWidget() is table.empty and "Scenario › Monte Carlo › Requirements" in \
        table.empty_label.text()
    asked = []
    widget.edit_requirements_requested.connect(lambda: asked.append(True))
    table.empty_button.click()
    assert asked == [True]
    assert "Requirements met" not in " ".join(_tile_texts(widget))
    headers = [widget.table.header_text(c) for c in range(widget.table.column_count())]
    assert "Meets all requirements" not in headers and "Status" not in headers


def test_a_thermal_batch_after_one_with_requirements_shows_none(qtbot, tmp_path):
    """The Requirements tab follows the batch shown: a thermal batch opened
    after an orbit batch with requirements shows the empty state, not the
    earlier batch's table."""
    from dataclasses import replace

    from spacemissionstudio.engine import monte_carlo_results as mcr
    from spacemissionstudio.gui.monte_carlo_results_widget import MonteCarloResultsWidget

    batch = _save_batch_with_outcomes(tmp_path / "orbit", [_ALTITUDE])
    thermal = replace(batch, kind="thermal", positions={}, velocities={}, outcomes=[], outcome_units={},
                      failed_drawn={}, requirements=[], case="hot",
                      temperatures_c={"bus": np.linspace(10.0, 20.0, 5 * batch.time_s.size).reshape(5, -1)})
    mcr.save(thermal, tmp_path / "thermal")
    widget = MonteCarloResultsWidget()
    qtbot.addWidget(widget)
    widget.load_folder(tmp_path / "orbit")
    assert widget.requirements_table.row_count() == 1
    widget.load_folder(tmp_path / "thermal")
    assert widget.requirements_table.stack.currentWidget() is widget.requirements_table.empty


# -- Run This Case (Monte Carlo plan A3) --------------------------------------


def _pick_rows(widget, *rows):
    """Select the shown rows ``rows`` of the Runs table."""
    from PySide6.QtCore import QItemSelectionModel

    view = widget.table.view
    view.clearSelection()
    for row in rows:
        view.selectionModel().select(view.model().index(row, 0),
                                     QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)


def test_run_this_case_is_there_and_disabled_without_a_picked_run(qtbot, tmp_path):
    """The Runs page has Run This Case (a button, the right-click menu, the
    shortcut in its tooltip). It is disabled until one run is picked, and
    then asks for that run's case, also after a sort; two runs picked, or
    a thermal batch, disable it again."""
    from dataclasses import replace

    from PySide6.QtCore import Qt

    from spacemissionstudio.engine import monte_carlo_results as mcr
    from spacemissionstudio.gui import monte_carlo_results_widget as view_module
    from spacemissionstudio.gui.monte_carlo_results_widget import MonteCarloResultsWidget

    widget = MonteCarloResultsWidget()
    qtbot.addWidget(widget)
    action = widget.run_case_action
    assert widget.run_case_button.defaultAction() is action and not action.isEnabled()
    assert "Ctrl+Shift+R" in action.toolTip() and action.shortcut().toString() == "Ctrl+Shift+R"
    assert widget.case_unavailable() == view_module._NO_BATCH

    batch = _save_batch(tmp_path / "orbit")
    widget.load_folder(tmp_path / "orbit")
    assert not action.isEnabled() and widget.case_unavailable() == view_module._PICK_ONE_CASE
    asked = []
    widget.case_requested.connect(asked.append)
    widget.table.sort_by(0, Qt.SortOrder.DescendingOrder)  # the case is the run's number, not the row
    _pick_rows(widget, 1)
    assert action.isEnabled() and widget.picked_case() == 3
    action.trigger()
    assert asked == [3]

    widget._on_runs_menu(widget.table.view.rect().center())
    assert action in widget.runs_menu.actions()
    widget.runs_menu.close()

    _pick_rows(widget, 0, 1)
    assert not action.isEnabled() and widget.picked_case() is None

    thermal = replace(batch, kind="thermal", positions={}, velocities={}, case="hot",
                      temperatures_c={"bus": np.linspace(10.0, 20.0, 5 * batch.time_s.size).reshape(5, -1)})
    mcr.save(thermal, tmp_path / "thermal")
    widget.load_folder(tmp_path / "thermal")
    _pick_rows(widget, 0)
    assert not action.isEnabled() and widget.case_unavailable() == view_module._NOT_AN_ORBIT_BATCH


def test_a_refused_case_is_a_problem_until_another_batch_is_shown(qtbot, tmp_path):
    """Why a case was not run is a Problems row (problem_rows); it goes when
    another batch is shown."""
    from spacemissionstudio.gui.monte_carlo_results_widget import MonteCarloResultsWidget

    _save_batch(tmp_path)
    widget = MonteCarloResultsWidget()
    qtbot.addWidget(widget)
    widget.load_folder(tmp_path)
    with qtbot.waitSignal(widget.problems_changed):
        widget.set_case_problem("Case 1 was not run: the scenario changed since the batch")
    assert widget.problem_rows() == [("warning", "Case 1 was not run: the scenario changed since the batch",
                                      "Case 1 was not run: the scenario changed since the batch")]
    with qtbot.waitSignal(widget.problems_changed):
        widget.load_folder(tmp_path)
    assert widget.problem_rows() == []


def _short_template_25(path):
    """Template 25 with 2 runs of 0.01 days, saved to ``path``; and its batch."""
    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR
    from spacemissionstudio.schema import load_scenario

    scenario = load_scenario(TEMPLATES_DIR / "25_monte_carlo_orbit_and_drag_dispersions.json")
    scenario.sim_settings.duration_days = 0.01  # [day]
    scenario.monte_carlo.num_runs, scenario.monte_carlo.thread_count = 2, 1
    scenario.save(path)
    return load_scenario(path)


@pytest.mark.requires_basilisk
def test_the_main_window_runs_a_case_again_or_says_why_not(qtbot, tmp_path, monkeypatch):
    """Monte Carlo plan A3 in the window: Run This Case (the window's
    command, in the palette) runs the picked case in the run worker and
    shows it as a run, with a toast; its provenance names the case. With a
    batch of another scenario, the case is refused before a run starts: the
    Problems panel has the reason and what to do, and the run shown before
    stays in Results."""
    import json
    import shutil

    from spacemissionstudio import output_provenance
    from spacemissionstudio.engine import monte_carlo
    from spacemissionstudio.gui import main_window as main_window_module
    from spacemissionstudio.gui.main_window import MainWindow

    path = tmp_path / "orbit_batch.json"
    scenario = _short_template_25(path)
    folder = tmp_path / "batch"
    assert monte_carlo.run_monte_carlo(scenario, scenario.monte_carlo, folder) == []
    toasts = []
    real_toast = main_window_module.show_toast
    monkeypatch.setattr(main_window_module, "show_toast",
                        lambda window, message, kind="success", **k: toasts.append((message, kind))
                        or real_toast(window, message, kind, **k))

    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    window.open_path(path)
    assert output_provenance.scenario_sha256(window.scenario_editor.to_scenario()) == \
        output_provenance.scenario_sha256(scenario)  # the editor's scenario is the batch's
    command = window.commands["run.monte_carlo_case"]
    assert command.category == "Run" and not command.action.isEnabled()
    assert command.unavailable.startswith("No Monte Carlo batch is shown")  # its palette entry says why
    widget = window.monte_carlo_results_widget
    assert widget.load_folder(folder)
    assert "Pick one run" in command.unavailable
    _pick_rows(widget, 1)
    assert command.action.isEnabled() and widget.picked_case() == 1
    command.action.trigger()
    qtbot.waitUntil(lambda: any(message.startswith("Monte Carlo case 1 ran again as Run ") and kind == "success"
                                for message, kind in toasts), timeout=60000)
    qtbot.waitUntil(lambda: not window.run_end_pending, timeout=30000)
    shown = window.results_widget._result
    assert shown is not None and shown.provenance.monte_carlo_case["case"] == 1
    assert window.current_view() is window.results_widget

    other = tmp_path / "other"
    shutil.copytree(folder, other)
    record = json.loads((other / "archive.provenance.json").read_text())
    record["scenario_sha256"] = "0" * 64
    (other / "archive.provenance.json").write_text(json.dumps(record))
    assert widget.load_folder(other)
    _pick_rows(widget, 0)
    command.action.trigger()
    # Refused before any run starts: the case shown before stays in Results.
    assert widget.case_problem and not window._run_going()
    assert window.results_widget._result is shown
    assert "the scenario changed since the batch" in widget.case_problem and "0" * 64 in widget.case_problem
    assert any(widget.case_problem == text for _severity, text in window.problems_widget.problems)
    assert not window.problems_dock.isHidden()  # the Problems panel opened


# -- Monte Carlo plan B8 (the Failed tile) and B4 (a thermal batch's node limits) ----


def test_the_failed_tile_counts_and_the_table_lists_the_crashed_runs(qtbot, tmp_path):
    """The "Failed" tile shows how many runs failed, not their numbers; the
    numbers are in its tooltip, and the Runs table lists each crashed run
    whose draws the batch kept, with "crashed" in its Status column."""
    from dataclasses import replace

    from spacemissionstudio.engine import monte_carlo_results as mcr
    from spacemissionstudio.gui.monte_carlo_results_widget import MonteCarloResultsWidget

    batch = _save_batch(tmp_path / "older")  # five runs, run 5 failed, no draws of it kept
    widget = MonteCarloResultsWidget()
    qtbot.addWidget(widget)
    widget.load_folder(tmp_path / "older")
    tile = [t for t in layout_item_widgets(widget.tiles_row) if t is not None][1]
    assert _tile_texts(widget)[1] == "1 | Failed"
    assert "Failed runs: 5." in tile.toolTip() and "keeps no draws" in tile.toolTip()
    kept = replace(batch, runs=[0, 1, 3, 4, 6], failed=[2, 5],
                   failed_drawn={2: {"sat-1 drag coefficient [-]": 2.4}, 5: {"sat-1 drag coefficient [-]": 3.0}})
    mcr.save(kept, tmp_path / "kept")
    widget.load_folder(tmp_path / "kept")
    tile = [t for t in layout_item_widgets(widget.tiles_row) if t is not None][1]
    assert _tile_texts(widget)[1] == "2 | Failed" and "Failed runs: 2, 5." in tile.toolTip()
    table = widget.table
    headers = [table.header_text(c) for c in range(table.column_count())]
    status = headers.index("Status")
    assert {table.cell(r, 0): table.cell(r, status) for r in range(table.row_count())} == {
        "0": "succeeded", "1": "succeeded", "2": "crashed", "3": "succeeded", "4": "succeeded", "5": "crashed",
        "6": "succeeded"}
    clean = replace(batch, failed=[])
    mcr.save(clean, tmp_path / "clean")
    widget.load_folder(tmp_path / "clean")
    assert _tile_texts(widget)[1] == "0 | Failed"


def test_a_thermal_batch_shows_its_node_limits_and_its_failed_runs(qtbot, tmp_path):
    """A thermal batch has a Node limits tab: one row per node and range,
    with the runs evaluated, the runs outside (failed ones included), the
    estimate, the bound and the confidence; the runs outside in the
    tooltip. The Runs table lists its failed run with its status. An orbit
    batch, or a thermal one saved before B4, has no such rows."""
    from spacemissionstudio.engine import monte_carlo_requirements as req
    from spacemissionstudio.engine import monte_carlo_results as mcr
    from spacemissionstudio.gui.monte_carlo_results_widget import MonteCarloResultsWidget

    t = np.linspace(0.0, 100.0, 5)  # [s]
    peaks = np.array([20.0, 31.0, 25.0, 35.0])  # [degC] runs 0, 2, 3 and 4; run 1 failed
    temperatures = np.outer(peaks, np.linspace(0.5, 1.0, t.size))
    limits = {"battery": {"operating": [0.0, 30.0], "survival": [-20.0, 45.0]}}
    extremes = {"battery": [(float(row.min()), float(row.max())) for row in temperatures]}
    judged = req.node_limits(limits, extremes, [0, 2, 3, 4], [1], 0.9)
    batch = mcr.MonteCarloBatch("Thermal", "earth", t, [0, 2, 3, 4], [1], {}, {},
                                [{"a [-]": 0.1}, {"a [-]": 0.3}, {"a [-]": 0.4}, {"a [-]": 0.5}], kind="thermal",
                                temperatures_c={"battery": temperatures}, case="hot", failed_drawn={1: {"a [-]": 0.2}},
                                node_limits=[row.to_dict() for row in judged])
    mcr.save(batch, tmp_path / "thermal")
    widget = MonteCarloResultsWidget()
    qtbot.addWidget(widget)
    _save_batch(tmp_path / "orbit")
    widget.load_folder(tmp_path / "orbit")
    assert not widget.views.isTabVisible(widget._node_limits_index)
    widget.load_folder(tmp_path / "thermal")
    assert widget.views.isTabVisible(widget._node_limits_index)
    assert widget.views.tabText(widget._node_limits_index) == "Node limits"
    table = widget.node_limits_table
    headers = [table.header_text(c) for c in range(table.column_count())]
    assert headers == list(req.NODE_LIMITS_HEADER)
    assert table.row_count() == 2
    rows = {table.cell(r, 1): [table.cell(r, c) for c in range(table.column_count())] for r in range(2)}
    assert rows["operating"][:7] == ["battery", "operating", "0", "30", "5", "3", "1"]
    assert rows["operating"][7] == f"{3 / 5:.4g}" and rows["operating"][9] == "0.9"
    assert rows["operating"][8] == f"{req.clopper_pearson_upper(3, 5, 0.9):.4g}"
    assert rows["survival"][5] == "1"  # the failed run only
    operating = next(r for r in range(2) if table.cell(r, 1) == "operating")
    assert table.hover_text(operating, 5) == "Runs outside: 1, 2, 4"
    assert _tile_texts(widget)[1] == "1 | Failed"
    runs = widget.table
    headers = [runs.header_text(c) for c in range(runs.column_count())]
    assert headers[-1] == "Status" and runs.row_count() == 5
    assert {runs.cell(r, 0): runs.cell(r, len(headers) - 1) for r in range(5)}["1"] == "failed"
    older = mcr.MonteCarloBatch("Thermal", "earth", t, [0, 2, 3, 4], [1], {}, {}, [{} for _ in range(4)],
                                kind="thermal", temperatures_c={"battery": temperatures}, case="hot")
    mcr.save(older, tmp_path / "older")
    widget.load_folder(tmp_path / "older")
    assert widget.views.isTabVisible(widget._node_limits_index)
    assert table.stack.currentWidget() is table.empty


# -- Statistics and Sensitivity (Monte Carlo plan B3 and B2) -------------------------------------------

def _show_tab(qtbot, widget, index):
    """Show tab ``index`` of the view and wait for the batch's statistics."""
    widget.views.setCurrentIndex(index)
    qtbot.waitUntil(lambda: not widget.insight_pending, timeout=10000)
    assert widget.insight is not None, widget.insight_error


def test_the_statistics_tab_gives_each_outcomes_percentiles_and_its_distribution(qtbot, tmp_path, restored_theme):
    """Shown, the tab works its numbers out off the GUI thread; per outcome:
    N, the minimum, the percentiles of the batch (NumPy's, by its method),
    the maximum, the unit; the picked row's empirical distribution is a step
    plot that ends at 1, drawn with the theme's template and drawn again in
    the new theme's colours on a theme change."""
    import threading

    from spacemissionstudio.engine import monte_carlo_statistics as mcs
    from spacemissionstudio.gui.monte_carlo_results_widget import MonteCarloResultsWidget
    from spacemissionstudio.gui.theme import SERIES_COLORS, TOKENS, apply_theme

    _save_batch_with_outcomes(tmp_path)
    widget = MonteCarloResultsWidget()
    qtbot.addWidget(widget)
    threads = []

    def compute(batch):
        threads.append(threading.current_thread())
        return mcs.insight(batch)

    widget.insight_computer.compute = compute
    widget.load_folder(tmp_path)
    assert widget.insight is None and threads == []  # nothing worked out before the tab is shown
    _show_tab(qtbot, widget, widget._statistics_index)
    assert threads and threads[0] is not threading.main_thread()
    table = widget.statistics_table
    headers = [table.header_text(c) for c in range(table.column_count())]
    assert headers == ["Outcome", "Unit", "N", "Minimum", "P1", "P5", "P50", "P95", "P99", "Maximum"]
    rows = {table.cell(r, 0): [table.cell(r, c) for c in range(table.column_count())] for r in range(table.row_count())}
    altitude = rows["lowest altitude"]
    values = 395.0 + 5.0 * np.arange(5)
    expected = np.percentile(values, [1, 5, 50, 95, 99], method="linear")
    assert altitude[1:4] == ["km", "5", "395"]
    assert altitude[4:9] == [f"{v:.6g}" for v in expected] and altitude[9] == "415"
    assert rows["Run length"][1:3] == ["h", "5"]
    assert [table.cell(r, 0) for r in range(3)] == ["final radial offset", "final along-track offset",
                                                    "final cross-track offset"]  # the batch's order first
    from PySide6.QtCore import Qt

    table.sort_by(4, Qt.SortOrder.DescendingOrder)  # sortable: by P1, the lowest altitude's the largest
    assert table.cell(0, 0) == "lowest altitude"
    assert widget.statistics_plot.figure is not None  # the first row is picked and plotted
    table.view.selectRow([table.cell(r, 0) for r in range(table.row_count())].index("lowest altitude"))
    figure = widget.statistics_plot.figure
    (trace,) = figure["data"]
    assert trace["line"]["shape"] == "hv" and trace["y"][0] == 0.0 and trace["y"][-1] == 1.0
    assert list(trace["x"]) == [395.0, 395.0, 400.0, 405.0, 410.0, 415.0]
    assert figure["layout"]["xaxis"]["title"]["text"] == "lowest altitude [km]"
    assert figure["layout"]["yaxis"]["title"]["text"] == "Fraction of runs at or below [-]"
    assert trace["line"]["color"] == SERIES_COLORS[0]
    apply_theme(restored_theme, "light")
    qtbot.waitUntil(lambda: widget.statistics_plot.figure is not figure)
    light = widget.statistics_plot.figure["layout"]["xaxis"]["gridcolor"]
    assert light == TOKENS["border.subtle"]
    apply_theme(restored_theme, "dark")
    qtbot.waitUntil(lambda: widget.statistics_plot.figure["layout"]["xaxis"]["gridcolor"] != light)
    assert widget.statistics_plot.figure["layout"]["xaxis"]["gridcolor"] == TOKENS["border.subtle"]
    assert widget.statistics_plot.figure["layout"]["font"]["color"] == TOKENS["text.primary"]


def test_the_sensitivity_tab_sorts_the_correlations_by_size(qtbot, tmp_path):
    """Every drawn value against every outcome, the largest first whatever
    its sign, with N per pair; a value that does not vary shows "—"; the
    picked pair is a scatter plot of the runs, its axes with their units."""
    from dataclasses import replace

    from spacemissionstudio.engine import monte_carlo_results as mcr
    from spacemissionstudio.gui.monte_carlo_results_widget import MonteCarloResultsWidget

    batch = _save_batch_with_outcomes(tmp_path)
    batch = replace(batch, drawn=[{**row, "sat-1 dry mass [kg]": 100.0} for row in batch.drawn],
                    outcomes=[dict(row, **({} if k == 2 else {"sat-1.delta_v": 10.0 - k}))
                              for k, row in enumerate(batch.outcomes)],
                    outcome_units={**batch.outcome_units, "sat-1.delta_v": "m/s"})
    mcr.save(batch, tmp_path)
    widget = MonteCarloResultsWidget()
    qtbot.addWidget(widget)
    widget.load_folder(tmp_path)
    _show_tab(qtbot, widget, widget._sensitivity_index)
    table = widget.sensitivity_table
    assert [table.header_text(c) for c in range(table.column_count())] == [
        "Drawn value", "Outcome", "Spearman's rank correlation [-]", "N"]
    rows = [[table.cell(r, c) for c in range(4)] for r in range(table.row_count())]
    sizes = [abs(float(row[2])) for row in rows if row[2] != "—"]
    assert sizes == sorted(sizes, reverse=True) and sizes[0] == pytest.approx(1.0)
    by_pair = {(row[0], row[1]): row[2:] for row in rows}
    assert by_pair[("drag coefficient [-]", "lowest altitude [km]")] == ["1", "5"]
    assert by_pair[("drag coefficient [-]", "delta-V [m/s]")] == ["-1", "4"]  # run 2 recorded none
    assert by_pair[("dry mass [kg]", "lowest altitude [km]")] == ["—", "5"]
    assert rows[-1][2] == "—"
    pick = next(r for r, row in enumerate(rows) if row[:2] == ["drag coefficient [-]", "delta-V [m/s]"])
    table.view.selectRow(pick)
    figure = widget.sensitivity_plot.figure
    (trace,) = figure["data"]
    assert trace["mode"] == "markers" and list(trace["customdata"]) == [0, 1, 3, 4]
    assert list(trace["x"]) == pytest.approx([2.0, 2.2, 2.6, 2.8]) and list(trace["y"]) == [10.0, 9.0, 7.0, 6.0]
    layout = figure["layout"]
    assert (layout["xaxis"]["title"]["text"], layout["yaxis"]["title"]["text"]) == ("drag coefficient [-]",
                                                                                    "delta-V [m/s]")
    assert "Spearman's rank correlation -1 over 4 runs" in layout["title"]["text"]


def test_the_plots_of_a_batch_of_100000_runs_take_under_50_ms_of_the_gui_thread(qtbot, tmp_path):
    """Design rule 6: a figure of 100 000 runs (the scatter of a pair, the
    step plot of an outcome) is built and its page started in under 50 ms
    of the GUI thread (the best of three, so a busy test machine does not
    decide it). The page itself, its JSON and its file, megabytes, is made
    by the plot's worker: on the Windows CI runner that part alone took 50
    to 100 ms. The page reads the typed arrays back as the values, and the
    newest page is the one shown."""
    import base64
    import json
    import time
    from pathlib import Path

    from spacemissionstudio.engine import monte_carlo_statistics as mcs
    from spacemissionstudio.gui import monte_carlo_insight as mi

    rng = np.random.default_rng(30)
    x, y = mcs.Column("a [-]", rng.normal(size=100_000)), mcs.Column("b [km]", rng.normal(size=100_000))
    runs = list(range(100_000))
    builds = (lambda: mi.scatter_figure(x, y, runs, "b against a", "", "a [-]", "b [km]"),
              lambda: mi.ecdf_figure(y, "b", ""))
    plot = mi.InsightPlot("empty")
    qtbot.addWidget(plot)
    for build in builds:
        plot.show_figure(build)  # plotly's first import and the web view are not the plot's
        plot.wait()
        took = []
        for _ in range(3):
            start = time.perf_counter()
            plot.show_figure(build)
            took.append(time.perf_counter() - start)
            plot.wait()
        assert min(took) < 0.050, took
        qtbot.waitUntil(lambda: plot._shown_page.endswith(f"_{plot._request}.html"))
        assert plot.page_error == "" and plot.stack.currentWidget() is plot.web_view
        page = Path(plot._shown_page)
        assert page.stat().st_size > 1_000_000
        assert sorted(page.parent.glob("monte_carlo_insight_*.html")) == [page]  # the older pages removed
    trace = json.loads(mi.figure_json(builds[0]()))["data"][0]
    assert trace["type"] == "scattergl" and trace["x"]["dtype"] == "f8"
    assert np.frombuffer(base64.b64decode(trace["x"]["bdata"]), "<f8").tolist() == x.values.tolist()
    assert np.frombuffer(base64.b64decode(trace["customdata"]["bdata"]), "<i4").tolist() == runs
    assert mi.write_page(builds[1](), "plotly.js", "", tmp_path / "gone" / "page.html") == "the plot folder is gone"


def test_a_batch_without_draws_says_there_is_nothing_to_correlate(qtbot, tmp_path):
    """No drawn value (a batch saved before they were kept): the
    Sensitivity table's empty state says so; the statistics are still
    there."""
    from dataclasses import replace

    from spacemissionstudio.engine import monte_carlo_results as mcr
    from spacemissionstudio.gui.monte_carlo_results_widget import MonteCarloResultsWidget

    mcr.save(replace(_save_batch(tmp_path), drawn=[{} for _ in range(5)]), tmp_path)
    widget = MonteCarloResultsWidget()
    qtbot.addWidget(widget)
    widget.load_folder(tmp_path)
    _show_tab(qtbot, widget, widget._sensitivity_index)
    assert widget.sensitivity_table.row_count() == 0
    assert "nothing to correlate" in widget.sensitivity_table.empty_label.text()
    assert widget.statistics_table.row_count() == 3  # the final offsets


def test_another_batch_shown_while_one_is_worked_out_shows_its_own_numbers(qtbot, tmp_path):
    """The worker's result for a batch no longer shown is dropped; the batch
    shown gets its own."""
    from spacemissionstudio.gui.monte_carlo_results_widget import MonteCarloResultsWidget

    _save_batch(tmp_path / "five")
    _save_batch(tmp_path / "seven", runs=7)
    widget = MonteCarloResultsWidget()
    qtbot.addWidget(widget)
    widget.load_folder(tmp_path / "five")
    widget.views.setCurrentIndex(widget._statistics_index)
    widget.load_folder(tmp_path / "seven")
    qtbot.waitUntil(lambda: not widget.insight_pending and widget.insight is not None, timeout=10000)
    widget.wait_for_insight()
    assert widget.statistics_table.cell(0, 2) == "7"


def test_a_batch_of_another_scenario_says_so(qtbot, tmp_path):
    """Plan B6: opened next to a scenario whose SHA-256 is not the one the
    batch's archive.provenance.json records, the view says so with both
    hashes; with the batch's own scenario, or with no scenario open, it
    says nothing."""
    import json as json_module

    from spacemissionstudio import output_provenance
    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR
    from spacemissionstudio.gui.monte_carlo_results_widget import MonteCarloResultsWidget
    from spacemissionstudio.schema import load_scenario

    scenario = load_scenario(TEMPLATES_DIR / "25_monte_carlo_orbit_and_drag_dispersions.json")
    digest = output_provenance.scenario_sha256(scenario)
    _save_batch(tmp_path)
    (tmp_path / "archive.provenance.json").write_text(json_module.dumps({"scenario_sha256": digest,
                                                                         "scenario_file": "t25.json"}))
    widget = MonteCarloResultsWidget()
    qtbot.addWidget(widget)
    widget.load_folder(tmp_path)
    widget.compare_with_scenario(scenario)
    assert widget.scenario_notes.notes == []
    scenario.monte_carlo.num_runs = 21
    widget.compare_with_scenario(scenario)
    (note,) = widget.scenario_notes.notes
    assert note.startswith("This batch was run with another scenario than the one open: scenario SHA-256 "
                           f"{digest} at the batch, {output_provenance.scenario_sha256(scenario)} now.")
    assert "(t25.json)" in note
    widget.compare_with_scenario(None)
    assert widget.scenario_notes.notes == []
    widget.compare_with_scenario(scenario)
    widget.load_folder(tmp_path)  # another batch shown: the note was about the one before
    assert widget.scenario_notes.notes == []


def test_the_main_window_compares_an_opened_batch_with_the_open_scenario(qtbot, tmp_path, monkeypatch):
    """Open Monte Carlo Results... next to another scenario: the view says
    the batch is of another scenario."""
    import json as json_module

    from PySide6.QtWidgets import QFileDialog

    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR
    from spacemissionstudio.gui.main_window import MainWindow

    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    window.open_path(TEMPLATES_DIR / "09_monte_carlo_dispersion_analysis.json")
    _save_batch(tmp_path)
    (tmp_path / "archive.provenance.json").write_text(json_module.dumps({"scenario_sha256": "0" * 64}))
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args, **kwargs: str(tmp_path))
    window.open_monte_carlo_results_action.trigger()
    (note,) = window.monte_carlo_results_widget.scenario_notes.notes
    assert f"scenario SHA-256 {'0' * 64} at the batch" in note


def test_the_report_has_the_views_numbers_and_is_written_off_the_gui_thread(qtbot, tmp_path):
    """Plan B5 (decision MC-32): Export report... hands the batch, its
    folder and the view's own statistics to a worker; the GUI thread
    returns at once (under 50 ms, design rule 6) and a toast says where the
    report is. Each number of the report is the one the view's tables show:
    the Statistics and Sensitivity cells, the Requirements cells."""
    import threading
    import time

    from spacemissionstudio.engine import monte_carlo_report
    from spacemissionstudio.engine.monte_carlo_statistics import number_text
    from spacemissionstudio.gui import export_log
    from spacemissionstudio.gui.monte_carlo_results_widget import MonteCarloResultsWidget

    _save_batch_with_outcomes(tmp_path, [_ALTITUDE])
    widget = MonteCarloResultsWidget()
    qtbot.addWidget(widget)
    assert not widget.report_button.isEnabled()  # no batch yet
    widget.load_folder(tmp_path)
    assert widget.report_button.isEnabled()
    _show_tab(qtbot, widget, widget._sensitivity_index)
    threads, given = [], []
    real = widget.report_writer.write

    def write(batch, path, folder, insight):
        threads.append(threading.current_thread())
        given.append(insight)
        return real(batch, path, folder, insight)

    widget.report_writer.write = write
    path = tmp_path / "report.json"
    start = time.perf_counter()
    widget.export_report(path)
    assert time.perf_counter() - start < 0.050
    qtbot.waitUntil(lambda: widget.report_writer.pending == 0, timeout=10000)
    assert threads[0] is not threading.main_thread() and given[0] is widget.insight
    assert export_log.last("monte_carlo_report")[1] == str(path)
    report = monte_carlo_report.load(path)

    table = widget.statistics_table
    shown = {table.cell(r, 0): [table.cell(r, c) for c in range(table.column_count())]
             for r in range(table.row_count())}
    for outcome in report["outcome_statistics"]["outcomes"]:
        cells = shown[widget._short(outcome["name"])]
        assert cells[1:] == [outcome["unit"], str(outcome["n"]), number_text(outcome["minimum"]),
                             *(number_text(p["value"]) for p in outcome["percentiles"]),
                             number_text(outcome["maximum"])]
    assert [o["minimum"] for o in report["outcome_statistics"]["outcomes"]] == [
        s.minimum for s in widget.insight.statistics]
    table = widget.sensitivity_table
    shown = [[table.cell(r, c) for c in range(4)] for r in range(table.row_count())]
    assert shown == [[widget._short(p["drawn_value"]), widget._short(p["outcome"]), number_text(p["correlation"]),
                      str(p["n"])] for p in report["sensitivity"]["pairs"]]
    table = widget.requirements_table
    (row,) = report["requirements"]["results"]
    assert [table.cell(0, c) for c in (0, 3, 4, 5, 7, 8, 11)] == [
        row["name"], str(row["evaluated"]), str(row["not_met"]), str(row["crashed"]), f"{row['estimate']:.4g}",
        f"{row['upper_bound']:.4g}", row["verdict"]]


def test_export_report_asks_for_the_file_and_its_format(qtbot, tmp_path, monkeypatch):
    """The dialog offers Markdown and JSON; a name without a suffix takes
    the format chosen; a file that cannot be written is said, not raised."""
    from PySide6.QtWidgets import QFileDialog

    from spacemissionstudio.engine import monte_carlo_report
    from spacemissionstudio.gui.monte_carlo_results_widget import MonteCarloResultsWidget

    _save_batch_with_outcomes(tmp_path)
    widget = MonteCarloResultsWidget()
    qtbot.addWidget(widget)
    widget.load_folder(tmp_path)
    answers = iter([(str(tmp_path / "mine"), "JSON (*.json)"), (str(tmp_path / "notes"), "Markdown (*.md)"),
                    (str(tmp_path / "missing" / "report.md"), "Markdown (*.md)")])
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: next(answers)))
    said = []
    monkeypatch.setattr("spacemissionstudio.gui.monte_carlo_results_widget.report",
                        lambda widget, text, kind="error": said.append((kind, text)))
    for _ in range(3):
        widget.report_button.click()
        qtbot.waitUntil(lambda: widget.report_writer.pending == 0, timeout=10000)
    assert monte_carlo_report.load(tmp_path / "mine.json")["batch"]["scenario_name"] == "Synthetic batch"
    assert (tmp_path / "notes.md").read_text(encoding="utf-8").startswith("# Monte Carlo report: Synthetic batch")
    assert [kind for kind, _text in said] == ["success", "success", "error"]
    assert said[2][1].startswith(f"Could not export the Monte Carlo report to {tmp_path / 'missing' / 'report.md'}")
