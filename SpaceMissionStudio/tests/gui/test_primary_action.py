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
"""One primary action, stable headers (UI audit batch B2).

The audit found two or three accent buttons in one view (UI-03), area
headers without a title and tab rows at a different height in each area
(UI-17), a Save button that showed the save state and top-bar buttons
that moved with the run mode (UI-36), Clear Time Cursor enabled with no
cursor (UI-41) and Run enabled and accent when no run could start
(UI-55). These tests check each defect.
"""

from pathlib import Path

import pytest

pytestmark = pytest.mark.requires_gui

_TEMPLATES = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"
_T01 = _TEMPLATES / "01_two_body_circular_orbit.json"
_T22 = _TEMPLATES / "22_starter_first_leo_satellite.json"


@pytest.fixture
def window(qtbot, monkeypatch, tmp_path, restored_theme):
    """A main window at 1280 x 720 in the light theme: the sizes the
    tests measure are those of the style sheet."""
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui import autosave
    from spacemissionstudio.gui.main_window import MainWindow
    from spacemissionstudio.gui.theme import apply_theme

    apply_theme(restored_theme, "light")

    monkeypatch.setattr(autosave, "_AUTOSAVE_DIR", tmp_path / "autosave")
    monkeypatch.setattr(autosave, "_RECOVERY_FILE", tmp_path / "autosave" / "recovery.json")
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    window.resize(1280, 720)
    yield window
    restored_theme.setStyle("Fusion")


def _settle(qtbot):
    qtbot.wait(20)


def _is_accent(button) -> bool:
    """Drawn in the accent: the style sheet's primary rules
    (``theme/qss.py``). A disabled primary button is drawn grey."""
    from PySide6.QtWidgets import QPushButton, QToolButton

    if isinstance(button, QToolButton):
        return button.objectName() == "primaryToolButton"
    if isinstance(button, QPushButton):
        return button.isDefault() or button.property("primary") is True or button.property("variant") == "primary"
    return False


def _accent_buttons(window) -> list:
    from PySide6.QtWidgets import QAbstractButton

    return [button for button in window.findChildren(QAbstractButton)
            if button.isVisible() and button.isEnabled() and _is_accent(button)]


def _views(window):
    """Every view of the window: each area, each tab of an area with
    tabs, each page of the Scenario tree. Yields its name once shown."""
    from PySide6.QtWidgets import QTabWidget

    for area in window.shell.page_areas():
        window.shell.show_area(area.id)
        content = area.page.content
        if area.id == "scenario" and window.scenario_open:
            tree = window.scenario_editor.page_tree
            for path, item in tree.paths():
                tree.tree.setCurrentItem(item)
                yield f"Scenario › {path}"
        elif isinstance(content, QTabWidget) and not area.page.showing_empty:
            for index in range(content.count()):
                content.setCurrentIndex(index)
                yield f"{area.label} › {content.tabText(index).replace('&', '')}"
        else:
            yield area.label


def _labels(buttons) -> list:
    return [(button.text() or button.accessibleName()) for button in buttons]


# -- UI-03: one accent per view ------------------------------------------------------------------------------------

def test_every_view_shows_at_most_one_accent_button(window, qtbot):
    """Every area, tab and Scenario page, with no scenario open and with
    template 01 open: at most one button in the accent."""
    window.show()
    qtbot.waitExposed(window)
    found = {}
    for opened in (None, _T01):
        if opened is not None:
            assert window.open_path(opened)
        for name in _views(window):
            _settle(qtbot)
            found[(opened is not None, name)] = _labels(_accent_buttons(window))
    assert len(found) > 30  # the walk covers the views: every area, and with a scenario every tab and page
    crowded = {name: labels for name, labels in found.items() if len(labels) > 1}
    assert crowded == {}


def test_the_top_bar_run_is_the_one_accent_and_page_buttons_are_secondary(window, qtbot):
    """With a scenario open, the accent is the top bar's Run in every view;
    the Run area's own Run, the empty states' Run, Check, Estimate, the
    Budgets empty states and Bring Back are secondary."""
    from PySide6.QtWidgets import QPushButton

    assert window.open_path(_T01)
    window.show()
    qtbot.waitExposed(window)
    assert window.top_bar.run_button.objectName() == "primaryToolButton"
    assert not _is_accent(window.shell.page("run").buttons[window.run_action])
    for button in (window.history_view.empty_run_button, window.results_overview.empty_run_button,
                   window.design_checks_widget.check_button, window.lifetime_widget.reentry_section.compute_button,
                   window.budgets_views.equipment_page.empty_state.button,
                   window.budgets_views.equipment_page.items_table.empty.button):
        assert isinstance(button, QPushButton)
        assert not _is_accent(button), button.text()
    window.show_view(window.history_view)
    _settle(qtbot)
    assert [window.top_bar.run_button] == _accent_buttons(window)


def test_bring_back_is_secondary_while_run_is_the_accent(window, qtbot):
    """A view in its own window leaves a placeholder; its Bring Back is
    secondary, as Run is the accent."""
    assert window.open_path(_T01)
    window.show()
    qtbot.waitExposed(window)
    window.breakouts.detach("budgets")
    try:
        placeholder = window.breakouts.placeholder("budgets")
        window.shell.show_area("budgets")
        _settle(qtbot)
        assert placeholder.isVisible() and not _is_accent(placeholder.button)
        assert _accent_buttons(window) == [window.top_bar.run_button]
    finally:
        window.breakouts.attach_all()


def test_home_has_its_own_primary_only_while_nothing_is_open(window, qtbot):
    """Home's Open template is the accent while no scenario is open (Run
    cannot start then); with one open, Run is the accent and Open template
    is secondary."""
    home = window.load_scenario_widget
    window.show()
    qtbot.waitExposed(window)
    home.select(0)
    _settle(qtbot)
    assert _accent_buttons(window) == [home.open_template_button]
    assert window.open_path(_T01)
    window.shell.show_area("home")
    home.select(1)
    _settle(qtbot)
    assert _accent_buttons(window) == [window.top_bar.run_button]


# -- UI-17: area headers -------------------------------------------------------------------------------------------

@pytest.mark.parametrize("opened", [None, _T01], ids=["no scenario", "template 01"])
def test_every_area_shows_its_title_in_a_header_of_one_height(window, qtbot, opened):
    """Every area with a page, Home, Reports and Settings among them, shows
    its header with the area's name, one height for all."""
    from spacemissionstudio.gui.theme import AREA_HEADER_HEIGHT

    if opened is not None:
        assert window.open_path(opened)
    window.show()
    qtbot.waitExposed(window)
    seen = {}
    for area in window.shell.page_areas():
        window.shell.show_area(area.id)
        _settle(qtbot)
        page = area.page
        assert page.title_bar.isVisible(), area.id
        assert page.title_label.isVisible() and page.title_label.text() == area.label
        seen[area.id] = page.title_bar.height()
    assert set(seen) == {"home", "scenario", "run", "results", "budgets", "timeline", "reports", "settings"}
    assert set(seen.values()) == {AREA_HEADER_HEIGHT}


@pytest.mark.parametrize("inspector", [False, True], ids=["no inspector", "inspector"])
def test_the_tab_rows_sit_at_one_height_in_every_area(window, qtbot, inspector):
    """At 1280 x 720 the tab rows of Run, Results, Budgets and Reports start
    at the same height of the window, the Inspector shown or not."""
    from PySide6.QtCore import QPoint

    assert window.open_path(_T01)
    window.show()
    qtbot.waitExposed(window)
    tops = {}
    for area_id, tabs in (("run", window.run_views), ("results", window.results_views),
                          ("budgets", window.budgets_views), ("reports", window.reports_views)):
        window.shell.show_area(area_id)
        window.side_dock.setVisible(inspector)
        _settle(qtbot)
        assert tabs.tabBar().isVisible()
        tops[area_id] = tabs.tabBar().mapTo(window, QPoint(0, 0)).y()
    assert len(set(tops.values())) == 1, tops


def test_a_crowded_header_keeps_its_height(qtbot, restored_theme):
    """A header with more commands than room shows them as icons, each
    with its name as tooltip and accessible name; it does not grow. With
    room again, the names come back."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QLabel

    from spacemissionstudio.gui.shell import AreaPage
    from spacemissionstudio.gui.theme import AREA_HEADER_HEIGHT, apply_theme, icon

    apply_theme(restored_theme, "light")
    page = AreaPage("run", "Run", QLabel("content"))
    qtbot.addWidget(page)
    actions = [QAction(icon("file-check"), f"Check Reference Data {n}", page) for n in range(6)]
    buttons = [page.add_command(action) for action in actions]
    page.resize(1600, 400)
    page.show()
    qtbot.waitExposed(page)
    assert not page.squeezed and page.title_bar.height() == AREA_HEADER_HEIGHT
    assert buttons[0].toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextBesideIcon
    page.resize(600, 400)
    qtbot.waitUntil(lambda: page.squeezed, timeout=2000)
    assert page.title_bar.height() == AREA_HEADER_HEIGHT and page.title_label.isVisible()
    assert all(b.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly for b in buttons)
    assert buttons[0].accessibleName() == "Check Reference Data 0" and "Check Reference Data 0" in buttons[0].toolTip()
    page.resize(1600, 400)
    qtbot.waitUntil(lambda: not page.squeezed, timeout=2000)
    assert buttons[0].toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextBesideIcon
    restored_theme.setStyle("Fusion")


def test_the_breadcrumb_names_the_page_in_every_area(window, qtbot):
    """Reports › Exports and Reports › Flight Software, as Run and Results
    name their tab."""
    assert window.open_path(_T01)
    window.show_view(window.exports_page)
    assert window.top_bar.breadcrumb_label.text() == "Reports › Exports"
    window.show_view(window.flight_software_widget)
    assert window.top_bar.breadcrumb_label.text() == "Reports › Flight Software"
    window.show_view(window.history_view)
    assert window.top_bar.breadcrumb_label.text() == "Run › History"


# -- UI-36: the top bar --------------------------------------------------------------------------------------------

def test_save_says_save_and_the_state_has_its_own_text_and_icon(window, qtbot):
    """Save always reads "Save". The save state is the subtitle's first
    part, with an icon of its own whose accessible name is the state."""
    bar = window.top_bar
    assert window.open_path(_T22)
    assert bar.save_button.text() == "Save"
    assert bar.detail_label.text().startswith("Unchanged · ")
    assert bar.save_state_icon.accessibleName() == "Unchanged" and not bar.save_state_icon.pixmap().isNull()
    window.scenario_editor.name_edit.setText("changed")
    assert bar.save_button.text() == "Save"
    assert bar.detail_label.text().startswith("Unsaved changes · ")
    assert bar.save_state_icon.accessibleName() == "Unsaved changes"
    window._dirty = False
    window.on_new()
    assert bar.save_button.text() == "Save" and bar.detail_label.text().startswith("Not saved yet")
    assert bar.save_state_icon.accessibleName() == "Not saved yet"


def test_switching_run_modes_moves_no_top_bar_button(window, qtbot):
    """The run-mode button has the width of its longest mode: Single run,
    Monte Carlo and SIL leave every top-bar button where it was."""
    from PySide6.QtWidgets import QToolButton

    assert window.open_path(_T01)
    window.show()
    qtbot.waitExposed(window)
    places = []
    for mode in ("single", "monte_carlo", "sil", "single"):
        window.set_run_mode(mode)
        _settle(qtbot)
        places.append({button.accessibleName() or button.text(): button.geometry().getRect()
                       for button in window.top_bar.findChildren(QToolButton) if button.isVisible()})
    moved = [{name: (rect, place.get(name)) for name, rect in places[0].items() if place.get(name) != rect}
             for place in places[1:]]
    assert places[0] and moved == [{}, {}, {}]


def test_a_problem_count_appearing_moves_no_command(window, qtbot):
    """The problem count sits left of the commands: when it shows, Save,
    Run and the search stay where they were."""
    assert window.open_path(_T01)
    window.show()
    qtbot.waitExposed(window)
    bar = window.top_bar
    bar.set_problem_counts(0, 0)
    _settle(qtbot)
    before = [w.geometry().getRect() for w in (bar.save_button, bar.run_button, bar.search_button)]
    bar.set_problem_counts(2, 13)
    _settle(qtbot)
    assert bar.problems_button.isVisible()
    assert [w.geometry().getRect() for w in (bar.save_button, bar.run_button, bar.search_button)] == before


def test_the_subtitle_shows_the_save_state_whole_at_1280_with_the_inspector(window, qtbot):
    """At 1280 x 720 with the Inspector shown, the subtitle still shows its
    save state whole; the rest elides, and the tooltip has all of it."""
    from PySide6.QtCore import Qt

    assert window.open_path(_T01)
    window.show()
    qtbot.waitExposed(window)
    window.shell.show_area("results")
    window.side_dock.show()
    window.resizeDocks([window.side_dock], [380], Qt.Orientation.Horizontal)  # [px] the window's own start width
    window.top_bar.set_problem_counts(0, 1)
    _settle(qtbot)
    label = window.top_bar.detail_label
    shown = label.fontMetrics().elidedText(label.text(), Qt.TextElideMode.ElideRight, label.width())
    assert shown.startswith("Unchanged"), shown
    assert label.toolTip() == label.text()


# -- UI-41: Clear Time Cursor --------------------------------------------------------------------------------------

def _palette_entry(window, label):
    return next(entry for entry in window.palette_entries() if entry.label == label)


def test_clear_time_cursor_is_enabled_only_while_a_cursor_is_set(window, qtbot):
    """No cursor, or no scenario: Clear Time Cursor is disabled in the menu,
    the palette and the header, and says why. A cursor set enables it."""
    action = window.clear_cursor_action
    assert not action.isEnabled()
    assert window.open_path(_T22)
    assert not action.isEnabled() and "No time cursor" in action.toolTip()
    assert not _palette_entry(window, "Run > Clear Time Cursor").enabled
    assert "No time cursor" in _palette_entry(window, "Run > Clear Time Cursor").reason
    button = window.shell.page("results").buttons[action]
    assert not button.isEnabled()
    window.time_cursor.set_time(120.0)
    assert action.isEnabled() and button.isEnabled() and _palette_entry(window, "Run > Clear Time Cursor").enabled
    assert "No time cursor" not in action.toolTip()
    action.trigger()
    assert window.time_cursor.time_s is None and not action.isEnabled()
    window.time_cursor.set_time(60.0)
    window._dirty = False
    window._set_scenario_open(False)
    assert not action.isEnabled()


# -- UI-55: Run when it cannot start -------------------------------------------------------------------------------

def test_run_is_disabled_with_the_reason_when_it_cannot_start(window, qtbot):
    """No scenario, an error in the scenario, a run going: Run is disabled
    in the top bar, the Run area, the palette and Ctrl+R, its tooltip says
    why, and it is not drawn in the accent. A valid scenario enables it."""
    run = window.run_action
    fired = []
    run.triggered.connect(lambda *_: fired.append(True))
    assert not run.isEnabled() and "No scenario is open" in run.toolTip()

    window.on_new()  # no spacecraft: an error
    assert not run.isEnabled() and "error" in run.toolTip()
    assert not _palette_entry(window, "Run > Run").enabled
    assert "error" in _palette_entry(window, "Run > Run").reason
    assert not window.top_bar.run_button.isEnabled()
    assert not window.history_view.empty_run_button.isEnabled()
    assert "error" in window.history_view.empty_run_button.toolTip()
    run.trigger()  # Ctrl+R: nothing starts
    assert fired == []

    window._dirty = False
    assert window.open_path(_T22)
    assert run.isEnabled() and window.top_bar.run_button.isEnabled() and window.history_view.empty_run_button.isEnabled()
    assert "error" not in run.toolTip() and "No scenario" not in run.toolTip()
    assert _palette_entry(window, "Run > Run").enabled

    window._start_busy("Running")
    assert not run.isEnabled() and "A run is going" in run.toolTip()
    window._stop_busy("Done.", "done", "Done")
    assert run.isEnabled()


def test_an_edit_that_makes_the_scenario_invalid_disables_run(window, qtbot):
    """Run follows the scenario's errors as they come and go."""
    assert window.open_path(_T22)
    run = window.run_action
    assert run.isEnabled()
    editor = window.scenario_editor
    configs = editor.spacecraft_list.to_list()
    editor.spacecraft_list.from_list([])
    editor.changed.emit()
    qtbot.waitUntil(lambda: not run.isEnabled(), timeout=3000)
    editor.spacecraft_list.from_list(configs)
    editor.changed.emit()
    qtbot.waitUntil(run.isEnabled, timeout=3000)
