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
    assert tiles[0] == "5 of 6 | Runs" and tiles[1] == "5 | Failed"
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
