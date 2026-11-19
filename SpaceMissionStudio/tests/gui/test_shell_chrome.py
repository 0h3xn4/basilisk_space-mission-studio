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

"""The window's shell: top bar, panels, status bar and toasts (UI audit
B8), measured in a shown window with the app's theme:

- UI-06: the top bar spans the window above the panels, and its subtitle
  is whole at 1280 px with the Inspector shown; a window narrower than
  1440 px starts without the Inspector;
- UI-09: the status bar never clips a message with a path at its first
  entry; the end (the file name) stays in view, the whole text in the
  tooltip;
- UI-39: each panel's title bar has Float and Close buttons of the
  interface's icon size, with tooltips and accessible names, reachable
  with the keyboard, in both themes;
- UI-54: a toast covers no control, no panel and not the status bar, and
  a click on it reaches what is under it;
- UI-56: the Inspector has the theme's width, and at 1920 px a form's page
  reaches the Inspector (no strip between them that belongs to nothing);
- from B7's review: section titles start at the page inset, the top bar's
  Undo, Redo and Save are framed secondary buttons, and the status bar
  shows no scenario chips while no scenario is open.

Positions are compared with each other (no overlap, inside the window, not
elided), never with fixed pixel values a platform style would change. Sizes
are read from widgets that are shown and laid out."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.requires_gui

_TEMPLATES = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"
_T01 = _TEMPLATES / "01_two_body_circular_orbit.json"


@pytest.fixture(scope="module")
def _shared_window(qapp, tmp_path_factory):
    """One main window with the app's light theme for the module, in a home
    of its own (its layout file is kept there)."""
    import gc

    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication

    from spacemissionstudio.gui.theme import apply_theme, state

    with pytest.MonkeyPatch.context() as patch:
        home = tmp_path_factory.mktemp("home")
        patch.setattr(Path, "home", lambda: home)
        from spacemissionstudio.gui.main_window import MainWindow

        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        gc.collect()
        saved = (qapp.font(), qapp.palette(), qapp.styleSheet())
        apply_theme(qapp, "light")
        window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
        window._confirm_discard_unsaved = lambda: True
        window.resize(1280, 720)  # [px]
        window.show()
        QApplication.processEvents()
        yield window
        window._mark_clean()
        window.close()
        window.deleteLater()
        QApplication.processEvents()
        state.select("light")
        qapp.setStyleSheet(saved[2])
        qapp.setPalette(saved[1])
        qapp.setFont(saved[0])


@pytest.fixture
def window(_shared_window, qtbot):
    """The module's window at 1280 x 720 with a scenario open, the panels
    hidden; put back so after the test."""
    _shared_window.resize(1280, 720)  # [px]
    assert _shared_window.open_path(_T01)
    _shared_window.side_dock.hide()
    _shared_window.problems_dock.hide()
    _shared_window.calculation_dock.hide()
    _settle(qtbot)
    yield _shared_window
    for dock in (_shared_window.side_dock, _shared_window.problems_dock, _shared_window.calculation_dock):
        dock.setFloating(False)
    _shared_window._mark_clean()
    _shared_window.resize(1280, 720)  # [px]


def _settle(qtbot, ms: int = 30) -> None:
    from PySide6.QtWidgets import QApplication

    for _ in range(3):
        QApplication.processEvents()
        qtbot.wait(ms)


def _rect(widget, window):
    """``widget``'s rectangle in ``window``'s coordinates."""
    from PySide6.QtCore import QPoint, QRect

    return QRect(widget.mapTo(window, QPoint(0, 0)), widget.size())


def _theme(qapp, mode: str) -> None:
    from spacemissionstudio.gui.theme import apply_theme, current_theme

    if current_theme() != mode:
        apply_theme(qapp, mode)


def _distance(a, b) -> int:
    return abs(a.red() - b.red()) + abs(a.green() - b.green()) + abs(a.blue() - b.blue())


# -- UI-06: the top bar spans the window ---------------------------------------------------------

def test_the_top_bar_spans_the_window_above_the_panels(window, qtbot):
    """The top bar is as wide as the window, under the menu bar; the
    Inspector starts under it, not beside it. At 1280 px with the Inspector
    shown, its subtitle ("Unchanged · from template 01 · not run yet") is
    whole: it read "Unch..." when the Inspector took the top bar's width."""
    window.side_dock.show()
    window.shell.show_area("scenario")
    _settle(qtbot)
    bar = _rect(window.top_bar, window)
    assert bar.left() == 0 and bar.width() == window.width()
    assert _rect(window.menuBar(), window).bottom() < bar.top()
    inspector = _rect(window.side_dock, window)
    assert inspector.top() > bar.bottom()
    assert not inspector.intersects(bar)
    label = window.top_bar.detail_label
    assert label.text().startswith("Unchanged")
    assert label.fontMetrics().horizontalAdvance(label.text()) <= label.contentsRect().width()


def test_the_menu_bar_still_hides_and_shows(window, qtbot):
    """View > Menu Bar still hides the menu bar, which now sits above the
    top bar in the window's header; the top bar stays."""
    action = window.menu_bar_action
    try:
        action.setChecked(False)
        _settle(qtbot)
        assert not window.menuBar().isVisible() and window.top_bar.isVisible()
        assert _rect(window.top_bar, window).top() == 0
    finally:
        action.setChecked(True)
    _settle(qtbot)
    assert window.menuBar().isVisible()


class _Screen:
    """A screen of a given width, for the Inspector's start rule."""

    def __init__(self, width: int) -> None:
        self._width = width

    def availableGeometry(self):  # noqa: N802 -- Qt API name
        from PySide6.QtCore import QRect

        return QRect(0, 0, self._width, 1400)


def test_a_window_narrower_than_1440_px_starts_without_the_inspector(window, qtbot, monkeypatch):
    """On a wide screen, a new layout (Reset Layout) shows the Inspector in
    a window of 1440 px or more, and not in a narrower one: beside a
    1280 px window's content it took a quarter of the width."""
    from spacemissionstudio.gui import main_window
    from spacemissionstudio.gui.theme import INSPECTOR_MIN_WINDOW_PX

    assert main_window._INSPECTOR_MIN_SCREEN_PX == INSPECTOR_MIN_WINDOW_PX == 1440
    monkeypatch.setattr(window, "screen", lambda: _Screen(2560))
    for width, shown in ((1400, False), (1439, False), (1440, True), (1920, True)):  # [px]
        window.resize(width, 900)
        _settle(qtbot)
        window.reset_layout()
        _settle(qtbot)
        assert window.side_dock.isVisible() is shown, width


# -- UI-56: the Inspector's width, no strip between the page and the Inspector --------------------

def test_the_inspector_has_the_theme_width_and_the_page_reaches_it(window, qtbot):
    """At 1920 x 1080 the Inspector opens at ``theme.INSPECTOR_WIDTH`` (it
    was 380 px for one line of placeholder text), and Scenario ›
    Environment's scroll area reaches it: before, the form and its scroll
    bar ended 960 px in, and a 220 px strip of nothing lay between it and
    the Inspector. The form itself keeps its width and the left edge."""
    from PySide6.QtWidgets import QScrollArea

    from spacemissionstudio.gui.theme import CONTENT_MAX_WIDTH_PX, INSPECTOR_WIDTH, SPACE

    window.resize(1920, 1080)  # [px]
    window.reset_layout()  # a new window's layout at this width: the Inspector shown
    window.side_dock.show()
    editor = window.scenario_editor
    window.show_view(editor)
    editor.page_tree.tree.setCurrentItem(editor.environment_item)
    _settle(qtbot)
    inspector = _rect(window.side_dock, window)
    assert abs(inspector.width() - INSPECTOR_WIDTH) <= SPACE["sm"]
    assert INSPECTOR_WIDTH < 380
    form = editor._environment_form
    scroll = next(area for area in form.findChildren(QScrollArea) if area.isVisible())
    page = _rect(scroll, window)
    assert page.right() < inspector.left()
    assert inspector.left() - page.right() <= SPACE["md"], (page, inspector)
    assert scroll.widget().width() <= CONTENT_MAX_WIDTH_PX
    assert _rect(scroll.widget(), window).left() == page.left()  # the form keeps the left edge


# -- UI-09: no clipped path in the status bar -----------------------------------------------------

def test_a_reported_path_is_not_clipped_in_the_status_bar(window, qtbot, tmp_path):
    """A report that names a long path ("Exported the mission output to
    /.../output.csv") showed in the status bar cut off at its first entry.
    It is elided in the middle, so its end (the file name) stays in view;
    the tooltip has the whole line until another message replaces it."""
    from PySide6.QtWidgets import QWidget

    from spacemissionstudio.gui.feedback import report

    bar = window.statusBar()
    path = tmp_path.joinpath(*(["a-folder-with-a-long-name"] * 12), "output.csv")
    text = f"Exported the mission output to {path}"
    report(window, text, kind="success")
    shown = bar.currentMessage()
    assert shown.endswith("output.csv") and "…" in shown, shown
    entries = [w for w in bar.findChildren(QWidget) if w.parent() is bar and w.isVisible()]
    room = min((_rect(w, bar).left() for w in entries), default=bar.width())  # [px] the first entry's left edge
    assert bar.fontMetrics().horizontalAdvance(shown) < room
    assert bar.toolTip() == text
    bar.showMessage("Ready.")
    assert bar.toolTip() == ""


def test_the_footer_is_gone_and_a_file_message_names_the_file(window, qtbot):
    """B5 removed the footer under the editor (UI-09's first part); the
    status bar names an opened file by its name, the path in the tooltip."""
    assert window.scenario_editor.layout().count() == 1
    assert window.statusBar().currentMessage() == f"Opened {_T01.name}"
    assert Path(window.statusBar().toolTip()).resolve() == _T01.resolve()


# -- UI-39: the panels' title bars ----------------------------------------------------------------

@pytest.mark.parametrize("mode", ["light", "dark"])
def test_each_panel_title_bar_has_float_and_close_buttons(window, qtbot, mode):
    """The Inspector, Problems and Calculation panels have Float and Close
    buttons of the interface's icon size on compact buttons (Qt's own were
    about 10 px, without a tooltip), each with a tooltip and an accessible
    name that name the panel, reachable with Tab, and drawn in both
    themes."""
    from PySide6.QtCore import QSize, Qt
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QApplication

    from spacemissionstudio.gui.app_shell import DockTitleBar
    from spacemissionstudio.gui.theme import CONTROL_HEIGHT, ICON_SIZE, TOKENS

    _theme(QApplication.instance(), mode)
    try:
        window.shell.show_area("scenario")
        window.side_dock.show()
        window.problems_dock.show()
        _settle(qtbot)
        for dock, name, keys in ((window.side_dock, "Inspector", "Ctrl+I"), (window.problems_dock, "Problems", "Ctrl+J"),
                                 (window.calculation_dock, "Calculation", "")):
            bar = dock.titleBarWidget()
            assert isinstance(bar, DockTitleBar), name
            for button, verb in ((bar.float_button, "Float"), (bar.close_button, "Close")):
                assert button.accessibleName() == f"{verb} {name}"
                assert button.toolTip().startswith(f"{verb} {name}")
                assert button.iconSize() == QSize(ICON_SIZE["ui"], ICON_SIZE["ui"])
                assert button.focusPolicy() & Qt.FocusPolicy.TabFocus
            if keys:
                assert keys in bar.close_button.toolTip()
            if dock.isVisible():
                assert bar.float_button.isVisible() and bar.close_button.isVisible()
                assert bar.close_button.height() == CONTROL_HEIGHT["compact"]
                assert bar.title_label.text().startswith(name)
                image = bar.grab().toImage()
                surface = QColor(TOKENS["bg.surface"])
                for button in (bar.float_button, bar.close_button):  # the icon is drawn, in this theme's ink
                    box = _rect(button, bar)
                    inked = max(_distance(image.pixelColor(x, y), surface)
                                for x in range(box.left(), box.right()) for y in range(box.top(), box.bottom()))
                    assert inked > 100, (name, button.accessibleName(), mode)
    finally:
        _theme(QApplication.instance(), "light")


def test_float_and_close_work_from_the_keyboard(window, qtbot):
    """Space on a focused Float floats the panel and it then reads Dock;
    Space on Dock docks it again; Space on Close hides the panel, as Ctrl+I
    does."""
    from PySide6.QtCore import Qt

    window.shell.show_area("scenario")
    window.side_dock.show()
    _settle(qtbot)
    bar = window.side_dock.titleBarWidget()
    bar.float_button.setFocus()
    qtbot.keyClick(bar.float_button, Qt.Key.Key_Space)
    _settle(qtbot)
    assert window.side_dock.isFloating()
    assert bar.float_button.accessibleName() == "Dock Inspector"
    qtbot.keyClick(bar.float_button, Qt.Key.Key_Space)
    _settle(qtbot)
    assert not window.side_dock.isFloating()
    assert bar.float_button.accessibleName() == "Float Inspector"
    qtbot.keyClick(bar.close_button, Qt.Key.Key_Space)
    _settle(qtbot)
    assert not window.side_dock.isVisible()
    assert not window.commands.action("view.inspector").isChecked()


def test_the_problems_title_bar_shows_the_count(window, qtbot):
    """The Problems panel's own title bar follows its title ("Problems (1)")."""
    window.show_problems()
    _settle(qtbot)
    assert window.problems_dock.titleBarWidget().title_label.text() == window.problems_dock.windowTitle()


# -- UI-54: toasts ---------------------------------------------------------------------------------

def _controls(window, skip):
    from PySide6.QtWidgets import QAbstractButton, QAbstractSpinBox, QComboBox, QLineEdit, QTabBar, QWidget

    kinds = (QAbstractButton, QComboBox, QLineEdit, QAbstractSpinBox, QTabBar)
    return [w for w in window.findChildren(QWidget)
            if isinstance(w, kinds) and w.isVisible() and not w.isWindow() and w not in skip
            and not any(s.isAncestorOf(w) for s in skip)]


def test_the_new_scenario_toast_covers_no_guide_link(window, qtbot):
    """The audit's case: New blank scenario at 1280 x 720 shows its guide
    with Go to ... buttons at the page's right edge; the toast covered one.
    It now covers no control, sits in the central area (above the status
    bar, beside the Inspector) and lets a click through."""
    from PySide6.QtCore import Qt

    window.side_dock.show()
    window.on_new()
    _settle(qtbot)
    toast = next(t for t in window._spacemissionstudio_active_toasts if t.text() == "New blank scenario")
    assert toast.isVisible()
    area = _rect(window.centralWidget(), window)
    shown = toast.geometry()
    assert area.contains(shown)
    assert shown.bottom() < _rect(window.statusBar(), window).top()
    assert not shown.intersects(_rect(window.side_dock, window))
    guide = window.scenario_editor.mission_guide
    assert any(b.isVisible() for b in guide.step_buttons.values())

    def covered():
        return [w for w in _controls(window, [toast]) if _rect(w, window).intersects(toast.geometry())]

    qtbot.waitUntil(lambda: not covered(), timeout=2000)  # the page is laid out after its toast shows
    assert _rect(window.centralWidget(), window).contains(toast.geometry())
    assert toast.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert toast.height() < 2 * toast.fontMetrics().lineSpacing() + 2 * 16  # one line: it fits its width


def test_a_toast_stays_off_the_panels_and_follows_them(window, qtbot):
    """With Problems shown under the work area and the Inspector beside it,
    a toast sits above Problems and left of the Inspector; when Problems
    opens after the toast, the toast moves up with the work area."""
    from spacemissionstudio.gui.feedback import show_toast

    window.shell.show_area("results")
    window.side_dock.show()
    _settle(qtbot)
    toast = show_toast(window, "Saved mine.json", duration_ms=10_000)
    _settle(qtbot)
    assert not toast.geometry().intersects(_rect(window.side_dock, window))
    window.problems_dock.show()
    _settle(qtbot)
    assert _rect(window.centralWidget(), window).contains(toast.geometry())
    assert not toast.geometry().intersects(_rect(window.problems_dock, window))
    toast.hide()


# -- from B7's review --------------------------------------------------------------------------------

def _text_left(label, window) -> int:
    """Where ``label``'s text starts, in ``window``'s coordinates: Qt indents
    a label with a frame (a style sheet's padding gives it one) by half an
    "x" when its indent is the default, -1."""
    indent = label.indent()
    if indent < 0:
        indent = label.fontMetrics().horizontalAdvance("x") // 2 if label.frameWidth() > 0 else 0
    return _rect(label, window).left() + label.contentsRect().left() + label.margin() + indent


def test_section_titles_start_at_the_page_inset(window, qtbot):
    """Settings' section titles ("Appearance") started 4 px right of the
    line under them; they start where it does. Scenario › Environment's
    group titles ("Gravity") start where the page's first line does."""
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QGroupBox, QLabel, QStyle, QStyleOptionGroupBox

    window.shell.show_area("settings")
    page = window.settings_page
    _settle(qtbot)
    lines = [label for label in page.widget().findChildren(QLabel)
             if label.property("tone") == "secondary" and label.isVisible() and label.text()]
    first_line = min(_text_left(label, window) for label in lines)
    for key, title in page.section_titles.items():
        assert _text_left(title, window) == first_line, key
    editor = window.scenario_editor
    window.show_view(editor)
    editor.page_tree.tree.setCurrentItem(editor.environment_item)
    _settle(qtbot)
    form = editor._environment_form
    intro = next(label for label in form.findChildren(QLabel) if label.isVisible() and label.wordWrap())
    for group in form.findChildren(QGroupBox):
        if not group.isVisible() or not group.title():
            continue
        option = QStyleOptionGroupBox()
        group.initStyleOption(option)
        label = group.style().subControlRect(QStyle.ComplexControl.CC_GroupBox, option,
                                             QStyle.SubControl.SC_GroupBoxLabel, group)
        assert group.mapTo(window, QPoint(label.left(), 0)).x() == _text_left(intro, window), group.title()


def test_the_top_bar_undo_redo_and_save_are_framed(window, qtbot):
    """Undo, Redo and Save in the top bar are secondary buttons with an
    edge (they were frameless, unlike the area headers' commands after B7);
    Run is still the one accent button."""
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QToolButton

    from spacemissionstudio.gui.theme import TOKENS

    bar = window.top_bar
    _settle(qtbot)
    image = bar.grab().toImage()
    surface = QColor(TOKENS["bg.surface"])
    for button in (bar.undo_button, bar.redo_button, bar.save_button):
        assert button.property("variant") == "secondary", button.accessibleName()
        edge = button.mapTo(bar, QPoint(0, button.height() // 2))
        assert _distance(image.pixelColor(edge), surface) > 30, button.accessibleName()
    accents = [b for b in window.findChildren(QToolButton) if b.objectName() == "primaryToolButton" and b.isVisible()]
    assert accents == [bar.run_button]


def test_no_scenario_chips_while_no_scenario_is_open(qtbot, monkeypatch, tmp_path):
    """With no scenario open, the status bar shows neither "No problems"
    nor "No run yet"; both show once one is open."""
    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    window.resize(1280, 720)  # [px]
    window.show()
    _settle(qtbot)
    assert not window.status_items.problems_button.isVisible()
    assert not window.run_chip.isVisible()
    assert window.open_path(_T01)
    _settle(qtbot)
    assert window.status_items.problems_button.isVisible() and window.run_chip.isVisible()
    window._mark_clean()


# -- the saved layout ------------------------------------------------------------------------------

def test_an_older_saved_layout_opens_without_error(qtbot, monkeypatch, tmp_path):
    """A layout saved by an earlier version (saveState version 5, Qt's own
    dock title bars) opens without error: the window starts with its
    default panels, and a layout saved now comes back."""
    from PySide6.QtCore import QSettings

    from spacemissionstudio.gui import main_window
    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    old = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(old)
    old.problems_dock.show()
    settings = QSettings(str(tmp_path / ".spacemissionstudio" / "layout.ini"), QSettings.Format.IniFormat)
    settings.setValue("window/state", old.saveState(5))
    settings.sync()
    assert main_window._LAYOUT_VERSION > 5
    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    window.show()
    window.shell.show_area("scenario")  # Home puts the panels aside
    _settle(qtbot)
    assert not window.problems_dock.isVisible()  # the default layout, not the old one
    window.problems_dock.show()
    window._save_layout()
    again = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(again)
    again.show()
    again.shell.show_area("scenario")
    _settle(qtbot)
    assert again.problems_dock.isVisible()


def test_the_toast_follower_keeps_no_python_attribute(window, qtbot):
    """The follower that moves a window's toasts is a child of the window
    and an event filter on it, and only an attribute of the window refers
    to it. Qt can call it after its Python wrapper has gone, and a new
    wrapper has none of the old one's attributes ("'_ToastFollower' object
    has no attribute '_window'" on CI, and every later test of that worker
    failed). So it keeps no attribute: its window is its parent, its timer
    is its own, and it still follows a resize and stops with no toast."""
    from spacemissionstudio.gui.feedback import _TOAST_FILTER_ATTR, _TOAST_STACK_ATTR, show_toast

    window.shell.show_area("results")
    _settle(qtbot)
    toast = show_toast(window, "Saved mine.json", duration_ms=10_000)
    _settle(qtbot)
    from PySide6.QtCore import SignalInstance

    follower = getattr(window, _TOAST_FILTER_ATTR)
    assert [name for name, value in vars(follower).items() if not isinstance(value, SignalInstance)] == []
    assert follower.watched_window() is window and follower.is_watching()
    window.side_dock.show()
    _settle(qtbot)
    assert not toast.geometry().intersects(_rect(window.side_dock, window))
    toast.hide()
    setattr(window, _TOAST_STACK_ATTR, [])
    follower.reposition()
    assert not follower.is_watching()
