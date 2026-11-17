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
"""Views in a window of their own (``gui.breakout``; 2.12.0, windows and
views design section 2, decision "Breakout windows"): Results › 3D View,
Run › Thermal and the Budgets area move into their own window and back as
the same widget, with their state and their data; the placeholder; closing
the window; the geometry kept and checked; Ctrl+Shift+D, the View menu,
the palette and the toolbar button; the theme; the 3D View's lost WebGL
context; Budgets counted as shown; detach and attach under 50 ms."""

import json
import math
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import budgets_fixtures as fx  # noqa: E402

pytestmark = pytest.mark.requires_gui

_GUI_THREAD_MS = 50.0  # [ms] CLAUDE.md "Never freeze": nothing longer on the GUI thread
_RADIUS_M = 7000e3  # [m]
_VIEWS = ("3d_view", "thermal", "budgets")


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    """A home of its own (layout.ini, the 3D View's settings) and no real autosave."""
    from spacemissionstudio.gui import autosave

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setattr(autosave, "_AUTOSAVE_DIR", tmp_path / "autosave")
    monkeypatch.setattr(autosave, "_RECOVERY_FILE", tmp_path / "autosave" / "recovery.json")


@pytest.fixture
def unopened(qtbot, monkeypatch):
    """A main window as it starts: on Home, nothing open."""
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    w = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(w)
    w.resize(1280, 720)  # [px]
    w.show()
    qtbot.waitExposed(w)
    return w


@pytest.fixture
def window(unopened, tmp_path):
    """The window with the budgets fixture open (template 22 with an equipment list)."""
    path = tmp_path / "budgets.json"
    path.write_text(json.dumps(fx.scenario_data()), encoding="utf-8")
    assert unopened.open_path(path)
    return unopened


def _activate(widget) -> None:
    """Qt's own active window, which the shortcut map checks (as test_keyboard_cursor.py)."""
    from PySide6.QtWidgets import QApplication

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        QApplication.setActiveWindow(widget)
    assert QApplication.activeWindow() is widget


def _press_ctrl_shift_d(qtbot, widget) -> None:
    from PySide6.QtCore import Qt

    qtbot.keyClick(widget, Qt.Key.Key_D, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)


def _tab_index(tabs, text: str) -> int:
    return [tabs.tabText(i).replace("&", "") for i in range(tabs.count())].index(text)


def _run():
    """Template 01 and one invented orbit (as tests/gui/test_mission_view.py)."""
    from spacemissionstudio import api
    from spacemissionstudio.engine.results import ResultSet, TimeSeries

    scenario = api.load(api.template("01_two_body_circular_orbit"))
    name = scenario.spacecraft[0].name
    t = np.linspace(0.0, 5800.0, 300)
    angle = 2.0 * math.pi * t / 5800.0
    result = ResultSet(scenario_name=scenario.name)
    result.add(TimeSeries(f"{name}.position_N", t, ("x", "y", "z"),
                          np.column_stack([_RADIUS_M * np.cos(angle), _RADIUS_M * np.sin(angle), 0 * t]), units="m"))
    result.add(TimeSeries(f"{name}.attitude_sigma_BN", t, ("s1", "s2", "s3"),
                          np.column_stack([0 * t, 0 * t, np.tan(angle / 4.0)])))
    return scenario, result


def _js(qtbot, view, script):
    out = []
    view.web_view.page().runJavaScript(script, 0, out.append)
    qtbot.waitUntil(lambda: bool(out), timeout=20000)
    return out[0]


def _state(qtbot, view):
    return json.loads(_js(qtbot, view, "JSON.stringify(MV.state())"))


def _drawn(qtbot, view) -> None:
    qtbot.waitUntil(lambda: view.scene is not None and view._page_ready, timeout=60000)
    qtbot.waitUntil(lambda: _js(qtbot, view, "MV.ready === true && MV.style !== null") is True, timeout=60000)


def _with_run(window, qtbot):
    """Results › 3D View shown with a run drawn."""
    view = window.mission_view_widget
    view.set_run(*_run())
    window.show_view(view)
    _drawn(qtbot, view)
    return view


# -- the views, their commands and buttons --------------------------------------------------------------

def test_every_view_opens_docked_with_its_button_and_no_window_opens_by_itself(unopened):
    """Calm by default: the three views start in the main window, no window
    of their own is open, and each view's toolbar has its icon button,
    named, with the shortcut in its tooltip."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QWidget

    from spacemissionstudio.gui.breakout import BreakoutButton

    window = unopened
    assert window.breakouts.ids() == list(_VIEWS)
    assert not any(window.breakouts.is_detached(view_id) for view_id in _VIEWS)
    assert not [w for w in window.findChildren(QWidget) if w.isWindow() and w.isVisible()]
    for view_id in _VIEWS:
        view = window.breakouts.widget(view_id)
        assert not view.isWindow() and window.breakouts.placeholder(view_id).isHidden()
        (button,) = [b for b in view.findChildren(BreakoutButton)]
        assert button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
        assert not button.icon().isNull()
        assert button.toolTip().startswith("Open in Own Window (Ctrl+Shift+D)")
        assert button.accessibleName() == f"Open in Own Window: {window.breakouts.title(view_id)}"
    assert window.shell.page("budgets").content is window.budgets_views


def test_the_commands_are_in_the_view_menu_the_palette_and_the_shortcut_list(window):
    """View > Own Windows: Open in Own Window (Ctrl+Shift+D, for the view
    shown) and one command per view; all in the palette; the shortcut is
    the only Ctrl+Shift+D and is listed in Settings > Keyboard."""
    menu = window.menus["Own Windows"]
    assert [a for a in menu.actions() if not a.isSeparator()] == [
        window.commands.action(command_id) for command_id in
        ("view.breakout", "view.window.3d_view", "view.window.thermal", "view.window.budgets")]
    assert menu.menuAction() in window.menus["View"].actions()
    command = window.commands["view.breakout"]
    assert command.keys == "Ctrl+Shift+D" and "(Ctrl+Shift+D)" in command.action.toolTip()
    assert [c.id for c in window.commands if c.keys == "Ctrl+Shift+D"] == ["view.breakout"]
    assert ("Own Windows", "Open in Own Window", "Ctrl+Shift+D") in window.commands.shortcut_rows()
    labels = {entry.label: entry for entry in window.palette_entries()}
    for title in ("3D View", "Thermal", "Budgets"):
        assert f"Own Windows > Open {title} in Own Window" in labels
    assert labels["Own Windows > Open in Own Window"].shortcut == "Ctrl+Shift+D"
    assert "separate window" in labels["Own Windows > Open in Own Window"].keywords


def test_the_commands_need_an_open_scenario(unopened):
    """With nothing open, the views show the empty state, and none can open
    in its own window."""
    for command_id in ("view.breakout", "view.window.3d_view", "view.window.thermal", "view.window.budgets"):
        assert not unopened.commands.action(command_id).isEnabled(), command_id


# -- detach and attach ------------------------------------------------------------------------------------

def test_detach_and_attach_keep_the_same_3d_view_its_page_and_its_state(window, qtbot):
    """The same widget, web view and scene in the window and back; the
    slider, the camera's view and the page's frame as they were; the tab
    keeps its index and text and shows the placeholder meanwhile."""
    view = _with_run(window, qtbot)
    web_view, scene = view.web_view, view.scene
    view.slider.setValue(42)
    view.view_combo.setCurrentIndex(1)  # Follow the spacecraft
    qtbot.waitUntil(lambda: _js(qtbot, view, "MV.frame") == 42, timeout=10000)
    tabs = window.results_views
    index = tabs.indexOf(view)
    count = tabs.count()

    window.breakouts.detach("3d_view")
    placeholder = window.breakouts.placeholder("3d_view")
    assert view.isWindow() and view.isVisible() and window.breakouts.window("3d_view") is view
    assert view.windowTitle() == "3D View - budgets.json - SpaceMissionStudio"
    assert tabs.widget(index) is placeholder and tabs.tabText(index) == "3D View" and tabs.count() == count
    assert tabs.currentIndex() == index and placeholder.isVisible()
    assert placeholder.title_label.text() == "3D View is in its own window"
    assert placeholder.button.text() == "Bring Back" and placeholder.button.property("variant") == "primary"
    assert view.web_view is web_view and view.scene is scene and view.slider.value() == 42
    view.slider.setValue(100)  # the page keeps drawing in the window
    qtbot.waitUntil(lambda: _js(qtbot, view, "MV.frame") == 100, timeout=10000)
    state = _state(qtbot, view)
    assert state["view"]["mode"] == "follow" and state["contextAlive"] is True

    placeholder.button.click()
    assert not window.breakouts.is_detached("3d_view") and not view.isWindow()
    assert tabs.widget(index) is view and tabs.currentIndex() == index and placeholder.isHidden()
    assert view.isVisible() and view.web_view is web_view and view.scene is scene
    assert view.slider.value() == 100 and view.view_combo.currentIndex() == 1
    qtbot.waitUntil(lambda: _state(qtbot, view)["frame"] == 100, timeout=10000)
    assert _js(qtbot, view, "JSON.stringify(MV_ERRORS)") == "[]"


def test_closing_the_window_brings_the_view_back(window, qtbot):
    """Closing the Thermal window puts the page back in Run › Thermal, with
    what it held."""
    view = window.thermal_widget
    view.size_check.setChecked(False)
    index = _tab_index(window.run_views, "Thermal")
    window.breakouts.detach("thermal")
    assert window.run_views.widget(index) is window.breakouts.placeholder("thermal")
    view.close()
    qtbot.waitUntil(lambda: not window.breakouts.is_detached("thermal"), timeout=5000)
    assert window.run_views.widget(index) is view and not view.isWindow() and not view.size_check.isChecked()
    assert window.breakouts.placeholder("thermal").isHidden()


def test_the_main_window_never_jumps_to_a_detached_view(window):
    """Showing a view in its own window (a command, the palette, a live run)
    brings its window to the front; the main window keeps its area."""
    window.shell.show_area("scenario")
    window.breakouts.detach("3d_view")
    window.show_view(window.mission_view_widget)
    assert window.shell.current_area() == "scenario" and window.mission_view_widget.isVisible()
    labels = {entry.label: entry for entry in window.palette_entries()}
    labels["Go to > Results > 3D View"].run()  # the tab holds the placeholder: the window is meant
    assert window.shell.current_area() == "scenario"
    window.breakouts.attach("3d_view")
    labels["Go to > Results > 3D View"].run()
    assert window.shell.current_area() == "results" and window.current_view() is window.mission_view_widget


def test_closing_the_scenario_and_quitting_bring_every_view_back(window, qtbot, monkeypatch):
    """No scenario open: the views are back, in their areas' empty state.
    Quitting puts them back before the layout is saved."""
    for view_id in _VIEWS:
        window.breakouts.detach(view_id)
    window._set_scenario_open(False)
    assert not any(window.breakouts.is_detached(view_id) for view_id in _VIEWS)
    assert window.shell.page("budgets").content is window.budgets_views
    window._set_scenario_open(True)
    window.breakouts.detach("budgets")
    window.close()
    assert not window.breakouts.is_detached("budgets")


# -- geometry ---------------------------------------------------------------------------------------------

def test_the_geometry_is_kept_per_view_and_used_again(window):
    """Kept when the view comes back, and the window opens there again;
    written to layout.ini on quit (no move writes the file: a write stops
    the GUI thread), and read at start."""
    from PySide6.QtCore import QRect

    from spacemissionstudio.gui.breakout import settings_key

    rect = QRect(40, 60, 640, 420)  # [px] inside the offscreen screen
    view = window.breakouts.detach("budgets")
    view.setGeometry(rect)
    window.breakouts.attach("budgets")
    assert window.breakouts.saved_geometry("budgets") == (rect, False)
    assert window._layout_settings().value(settings_key("budgets")) is None  # not written by the move
    window.breakouts.detach("budgets")
    assert view.geometry() == rect
    moved = QRect(60, 80, 600, 400)  # [px]
    view.setGeometry(moved)
    window.close()  # quitting
    assert (Path.home() / ".spacemissionstudio" / "layout.ini").is_file()
    assert window._layout_settings().value(settings_key("budgets")) == moved
    assert window._layout_settings().value(settings_key("3d_view")) is None  # never opened: nothing kept
    from spacemissionstudio.gui.main_window import MainWindow

    again = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    try:
        assert again.breakouts.saved_geometry("budgets") == (moved, False)
    finally:
        again.close()
        again.deleteLater()


def test_a_window_saved_on_a_screen_that_is_gone_opens_on_the_main_window(window):
    """A rectangle no screen shows (a monitor unplugged): its size, centred
    on the main window."""
    from PySide6.QtCore import QRect, QSize

    from spacemissionstudio.gui.breakout import on_a_screen, settings_key

    settings = window._layout_settings()
    settings.setValue(settings_key("thermal"), QRect(9000, 9000, 620, 410))
    window.breakouts.read_geometry(settings)  # as at start
    view = window.breakouts.detach("thermal")
    # The saved size, or the view's own minimum where that is larger (on Windows its fonts make it 714 px wide).
    assert view.size() == QSize(620, 410).expandedTo(view.minimumSizeHint())
    assert on_a_screen(view.geometry())
    centre, middle = view.geometry().center(), window.frameGeometry().center()
    assert abs(centre.x() - middle.x()) <= 4 and abs(centre.y() - middle.y()) <= 4  # [px] the frame's margins


def test_on_wayland_only_the_size_is_used(window, monkeypatch):
    """Wayland ignores a window's position: the saved size is kept, the
    compositor places the window."""
    from PySide6.QtCore import QRect, QSize

    from spacemissionstudio.gui import breakout

    settings = window._layout_settings()
    settings.setValue(breakout.settings_key("thermal"), QRect(30, 40, 630, 430))
    window.breakouts.read_geometry(settings)  # as at start
    moves = []
    monkeypatch.setattr(breakout, "position_ignored", lambda: True)
    view = window.thermal_widget
    real_move = type(view).move
    monkeypatch.setattr(type(view), "move", lambda self, *a: moves.append(a) or real_move(self, *a))
    window.breakouts.detach("thermal")
    assert view.size() == QSize(630, 430).expandedTo(view.minimumSizeHint()) and moves == []


# -- the keyboard -----------------------------------------------------------------------------------------

def test_ctrl_shift_d_moves_the_view_shown_from_either_window(window, qtbot):
    """In the main window it opens the view shown in its own window; in that
    window it brings it back. Where no view can move, it is disabled."""
    action = window.commands.action("view.breakout")
    window.shell.show_area("scenario")
    _activate(window)
    assert not action.isEnabled()
    window.show_view(window.thermal_widget)
    _activate(window)
    assert action.isEnabled() and action.text() == "Open in Own Window"
    _press_ctrl_shift_d(qtbot, window)
    view = window.thermal_widget
    assert window.breakouts.is_detached("thermal") and view.isWindow()
    _activate(view)
    assert action.text() == "Bring Back" and "(Ctrl+Shift+D)" in action.toolTip()
    assert window.commands.action("view.window.thermal").text() == "Bring Back Thermal"
    _press_ctrl_shift_d(qtbot, view.solve_button)
    assert not window.breakouts.is_detached("thermal")
    assert window.commands.action("view.window.thermal").text() == "Open Thermal in Own Window"


def test_the_keyboard_works_in_the_window(window, qtbot, monkeypatch):
    """The window's first control has the focus, Tab moves on inside the
    window, and Ctrl+K opens the palette over the window."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from spacemissionstudio.gui import command_palette

    opened = []
    monkeypatch.setattr(command_palette.CommandPalette, "exec", lambda self: opened.append(self.parentWidget()) or 0)
    view = window.breakouts.detach("thermal")
    _activate(view)
    view.spacecraft_combo.setFocus()
    first = QApplication.focusWidget()
    assert first is not None and view.isAncestorOf(first)
    qtbot.keyClick(first, Qt.Key.Key_Tab)
    second = QApplication.focusWidget()
    assert second is not first and view.isAncestorOf(second)
    qtbot.keyClick(second, Qt.Key.Key_K, Qt.KeyboardModifier.ControlModifier)
    assert opened == [view]
    assert window.commands.action("run.run") in view.actions()  # Ctrl+R, Ctrl+S ... work there too
    assert window.commands.action("go.results") not in view.actions()
    window.breakouts.attach("thermal")
    assert window.commands.action("run.run") not in view.actions()


def test_the_view_s_own_button_and_the_menu_command_move_it(window):
    from spacemissionstudio.gui.breakout import BreakoutButton

    (button,) = window.budgets_views.findChildren(BreakoutButton)
    button.click()
    assert window.breakouts.is_detached("budgets")
    assert button.toolTip().startswith("Bring Back (Ctrl+Shift+D)") and button.text() == "Bring Back"
    window.commands.action("view.window.budgets").trigger()
    assert not window.breakouts.is_detached("budgets")
    window.commands.action("view.window.3d_view").trigger()
    assert window.breakouts.is_detached("3d_view")


# -- theme ------------------------------------------------------------------------------------------------

def test_a_theme_change_reaches_the_window(window, qtbot, restored_theme):
    """The window takes the application's palette and style sheet: a
    switch restyles it at once, as the main window."""
    from PySide6.QtGui import QPalette

    from spacemissionstudio.gui.breakout import BreakoutButton
    from spacemissionstudio.gui.theme import TOKENS, apply_theme, tokens

    apply_theme(restored_theme, "light")
    view = window.breakouts.detach("thermal")
    assert view.palette().color(QPalette.ColorRole.Window).name().upper() == tokens.tokens("light")["bg.canvas"]
    (button,) = view.findChildren(BreakoutButton)
    light = button.icon().pixmap(16, 16).toImage()
    apply_theme(restored_theme, "dark")
    dark = tokens.tokens("dark")
    assert view.palette().color(QPalette.ColorRole.Window).name().upper() == dark["bg.canvas"]
    assert view.status_label.palette().color(QPalette.ColorRole.WindowText).name().upper() == dark["text.secondary"]
    assert TOKENS["bg.canvas"] == dark["bg.canvas"]
    assert button.icon().pixmap(16, 16).toImage() != light  # the icon follows its token


# -- the 3D View's WebGL context ---------------------------------------------------------------------------

def _lose_context(qtbot, view) -> int:
    """Take the 3D View's WebGL context away; the recoveries counted before."""
    # A live context first: a GPU process can lose and give back every context by itself (Windows CI's D3D
    # backend does), and a lost context has no WEBGL_lose_context extension to call. For the same reason the
    # tests count recoveries from here, not from zero.
    qtbot.waitUntil(lambda: _js(qtbot, view, "Boolean(MV.renderer) && !MV.contextLost && "
                                             "!MV.renderer.getContext().isContextLost()") is True, timeout=10000)
    before = _js(qtbot, view, "MV.recoveries")
    _js(qtbot, view, "window.LOSE = MV.renderer.getContext().getExtension('WEBGL_lose_context'); "
                     "window.CANVAS = MV.renderer.domElement; LOSE.loseContext(); 1")
    qtbot.waitUntil(lambda: _js(qtbot, view, "MV.contextLost") is True, timeout=10000)
    return before


def test_the_3d_view_recovers_a_webgl_context_given_back(qtbot):
    """webglcontextlost stops drawing; webglcontextrestored makes a new
    renderer and keeps the same scene, camera, frame and time shown.

    The scene is not loaded again: its objects, materials and textures
    are the same objects after the recovery."""
    from spacemissionstudio.gui.mission_view_widget import MissionViewWidget

    view = MissionViewWidget()
    qtbot.addWidget(view)
    view.resize(900, 600)
    view.show()
    view.set_run(*_run())
    _drawn(qtbot, view)
    view.slider.setValue(77)
    qtbot.waitUntil(lambda: _js(qtbot, view, "MV.frame") == 77, timeout=10000)
    _js(qtbot, view, "MV.camera.position.set(9000, 1000, 2000); MV.dirty = true; "
                     "window.KEEP = [MV.scene, MV.body, MV.body.material, MV.body.material.map, MV.crafts[0].mesh]; 1")
    clock = _js(qtbot, view, "document.getElementById('hud-time').textContent")
    before = _lose_context(qtbot, view)
    _js(qtbot, view, "LOSE.restoreContext(); 1")
    qtbot.waitUntil(lambda: _js(qtbot, view, "MV.recoveries") == before + 1, timeout=10000)
    state = _state(qtbot, view)
    assert state["contextLost"] is False and state["contextAlive"] is True and state["ready"] is True
    assert state["frame"] == 77 and state["frames"] == 300 and state["webgl"] is True
    np.testing.assert_allclose(json.loads(_js(qtbot, view, "JSON.stringify(MV.camera.position.toArray())")),
                               [9000, 1000, 2000])
    assert _js(qtbot, view, "MV.renderer.domElement !== CANVAS && !document.body.contains(CANVAS)") is True
    assert _js(qtbot, view, "MV.scene === KEEP[0] && MV.body === KEEP[1] && MV.body.material === KEEP[2] "
                            "&& MV.body.material.map === KEEP[3] && MV.crafts[0].mesh === KEEP[4]") is True
    assert _js(qtbot, view, "document.getElementById('hud-time').textContent") \
        == clock
    view.slider.setValue(120)  # it draws again
    qtbot.waitUntil(lambda: _state(qtbot, view)["frame"] == 120, timeout=10000)
    qtbot.waitUntil(lambda: _js(qtbot, view, "MV.dirty") is False, timeout=10000)
    assert _js(qtbot, view, "JSON.stringify(MV_ERRORS)") == "[]"


def test_the_3d_view_recovers_a_webgl_context_never_given_back(qtbot):
    """A context the browser does not give back: a new renderer of its own
    after RECOVER_AFTER_MS. Meanwhile the overlay follows the frame: only
    the draw call waits for a context."""
    from spacemissionstudio.gui.mission_view_widget import MissionViewWidget

    view = MissionViewWidget()
    qtbot.addWidget(view)
    view.resize(900, 600)
    view.show()
    view.set_run(*_run())
    _drawn(qtbot, view)
    before = _lose_context(qtbot, view)
    # The page's own timer waits while the overlay is checked (a slow runner can take RECOVER_AFTER_MS for it).
    _js(qtbot, view, "clearTimeout(MV.recoverTimer); 1")
    shown = _js(qtbot, view, "document.getElementById('hud-time').textContent").split("\n")[0]
    view.slider.setValue(120)
    qtbot.waitUntil(lambda: _js(qtbot, view, "MV.frame") == 120, timeout=10000)
    qtbot.waitUntil(lambda: _js(qtbot, view, "document.getElementById('hud-time').textContent")
                    .split("\n")[0] != shown, timeout=10000)
    # Still lost: the overlay was drawn without a context.
    assert _js(qtbot, view, "MV.contextLost") is True and _js(qtbot, view, "MV.recoveries") == before
    _js(qtbot, view, "MV.recoverTimer = setTimeout(MV.recover, RECOVER_AFTER_MS); 1")  # as onContextLost set it
    qtbot.waitUntil(lambda: _js(qtbot, view, "MV.recoveries") == before + 1, timeout=15000)
    state = _state(qtbot, view)
    assert state["contextAlive"] is True and state["ready"] is True and state["frames"] == 300
    assert _js(qtbot, view, "JSON.stringify(MV_ERRORS)") == "[]"


# -- Budgets ----------------------------------------------------------------------------------------------

def test_budgets_in_its_own_window_counts_as_shown(window, qtbot):
    """B-21 with the windows design's Q2: a detached Budgets area is shown.
    It is computed on an edit while the main window shows another area, its
    commands act on it there, and its spacecraft picker goes with it."""
    views = window.budgets_views
    window.shell.show_area("scenario")
    views.setCurrentWidget(views.equipment_page)
    window.breakouts.detach("budgets")
    assert window.shell.current_area() == "scenario"
    assert views.shown() and views.equipment_page.shown()
    assert views.corner.isAncestorOf(views.selector)
    names = [item.name for item in window.scenario_editor.draft_scenario().spacecraft[0].budgets.equipment]
    views.equipment_page.items_table.select_row(0)
    window.commands.action("budgets.remove_item").trigger()
    after = [item.name for item in window.scenario_editor.draft_scenario().spacecraft[0].budgets.equipment]
    assert after == names[1:]
    assert window.shell.current_area() == "scenario"  # the command showed the window, not the area
    window.breakouts.attach("budgets")
    assert window.shell.page("budgets").header.isAncestorOf(views.selector)


# -- timing -----------------------------------------------------------------------------------------------

def test_detach_and_attach_take_under_50_ms_on_the_gui_thread(window, qtbot):
    """The view keeps its parent and becomes a window: no restyle of its
    widgets (a new parent took 50 to 70 ms for Budgets). Each view three
    times, the 3D View with its page loaded."""
    from PySide6.QtWidgets import QApplication

    _with_run(window, qtbot)
    took = {}
    for view_id in _VIEWS:
        window.show_view(window.breakouts.widget(view_id))
        QApplication.processEvents()
        for _round in range(3):
            for move in (window.breakouts.detach, window.breakouts.attach):
                start = time.perf_counter()
                move(view_id)
                took.setdefault(view_id, []).append(1000.0 * (time.perf_counter() - start))
                QApplication.processEvents()
    assert max(max(times) for times in took.values()) < _GUI_THREAD_MS, took


# -- a live run -------------------------------------------------------------------------------------------

@pytest.mark.requires_basilisk
def test_a_live_run_goes_on_in_the_3d_view_s_own_window(window, qtbot, monkeypatch):
    """The detached 3D View receives the live run (the same widget: no
    second consumer of the feed); starting the run brings its window to the
    front and leaves the main window where it was; the result replaces the
    live frames there."""
    from spacemissionstudio import api

    scenario = api.load(api.template("01_two_body_circular_orbit"))
    scenario.sim_settings.duration_days = 0.1  # [day] 8.6 s at 1000× real time
    monkeypatch.setattr(window.scenario_editor, "to_scenario", lambda: scenario)
    window.run_page.live_view_check.setChecked(True)
    window.run_page.pacing_combo.setCurrentIndex(window.run_page.pacing_combo.findData(1000.0))
    view = window.mission_view_widget
    window.breakouts.detach("3d_view")
    window.shell.show_area("run")
    window.on_run()
    assert view.is_live() and view.isWindow() and view.isVisible() and window.shell.current_area() == "run"
    qtbot.waitUntil(lambda: view.scene is not None and view._page_ready, timeout=60000)
    qtbot.waitUntil(lambda: _js(qtbot, view, "MV.ready === true") is True, timeout=60000)
    qtbot.waitUntil(lambda: _state(qtbot, view)["frames"] >= 20, timeout=30000)
    assert _state(qtbot, view)["live"] is True
    qtbot.waitUntil(lambda: not window._run_worker.isRunning(), timeout=60000)
    qtbot.waitUntil(lambda: not view.is_live() and view.scene is not None and view._run is None
                    and len(view.scene.times_s) == 289, timeout=60000)
    assert window.breakouts.is_detached("3d_view") and window.mission_view_widget is view
