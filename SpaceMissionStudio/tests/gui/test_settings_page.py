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

"""The Settings page and the area headers (UI audit B7), measured in a
shown 1280 x 720 window with the app's theme:

- UI-11: the theme is a segmented control, an on/off setting a check box,
  an action a framed button; the area headers' commands draw a frame, in
  both themes;
- UI-33: Settings › Keyboard is a DataTable whose columns fill the width,
  with left-aligned headings, no grid lines, the theme's row height and
  the keys in the monospace font;
- the Settings forms share one label column, and no drop-down list cuts
  its entry.

Sizes are read from widgets that are shown and laid out (a hidden widget
is never laid out, and Qt's default size differs between platforms)."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.requires_gui

_TEMPLATES = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"


@pytest.fixture(scope="module")
def _shared_window(qapp, tmp_path_factory):
    """One 1280 x 720 main window with the app's light theme for the
    module, in a home of its own (the theme choice is kept there)."""
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
        window.side_dock.hide()
        window.problems_dock.hide()
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
def window(_shared_window):
    """The module's window, its scenario discarded after the test."""
    yield _shared_window
    _shared_window._mark_clean()


def _settle(qtbot, widget=None, ms: int = 30) -> None:
    """Let the layouts settle (the form grid lines up on the next turn of
    the event loop)."""
    from PySide6.QtWidgets import QApplication

    if widget is not None:
        qtbot.waitUntil(widget.isVisible, timeout=5000)
    for _ in range(3):
        QApplication.processEvents()
        qtbot.wait(ms)


def _settings(window, qtbot, section: str = "appearance"):
    window.shell.show_area("settings")
    page = window.settings_page
    page.show_section(section)
    _settle(qtbot, page)
    return page


def _theme(qapp, mode: str) -> None:
    from spacemissionstudio.gui.theme import apply_theme, current_theme

    if current_theme() != mode:
        apply_theme(qapp, mode)


def _distance(a, b) -> int:
    """The sum of the RGB channels' differences of two QColors."""
    return abs(a.red() - b.red()) + abs(a.green() - b.green()) + abs(a.blue() - b.blue())


def _draws_a_frame(button, surface) -> bool:
    """Whether ``button`` draws an edge of its own on ``surface`` (the
    widget behind it): the middle of its left edge, grabbed with what is
    behind it, differs from the surface's background (``bg.canvas``)."""
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QColor

    from spacemissionstudio.gui.theme import TOKENS

    image = surface.grab().toImage()
    edge = button.mapTo(surface, QPoint(0, button.height() // 2))
    return _distance(image.pixelColor(edge), QColor(TOKENS["bg.canvas"])) > 30


# -- UI-11: controls that look like controls ----------------------------------------------------

def test_the_theme_is_a_segmented_control(window, qtbot):
    """System · Light · Dark is one segmented control: the theme in effect
    is its checked segment, and a click on another applies that theme at
    once, through the theme command (its shortcut, menu and palette
    entry)."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from spacemissionstudio.gui.theme import current_theme
    from spacemissionstudio.gui.widgets import SegmentedControl

    page = _settings(window, qtbot)
    control = page.theme_control
    assert isinstance(control, SegmentedControl) and control.objectName() == "segmentedControl"
    assert [segment.text() for segment in control.segments] == ["System", "Light", "Dark"]
    assert control.accessibleName() == "Theme"
    try:
        qtbot.mouseClick(page.buttons["view.theme.dark"], Qt.MouseButton.LeftButton)
        assert current_theme() == "dark" and window.theme_actions["dark"].isChecked()
        assert [segment.isChecked() for segment in control.segments] == [False, False, True]
        qtbot.mouseClick(page.buttons["view.theme.dark"], Qt.MouseButton.LeftButton)  # chosen again: stays
        assert [segment.isChecked() for segment in control.segments] == [False, False, True]
        window.theme_actions["light"].trigger()  # the menu or the palette: the control follows
        assert current_theme() == "light"
        assert [segment.isChecked() for segment in control.segments] == [False, True, False]
    finally:
        window.theme_actions["light"].trigger()
        _theme(QApplication.instance(), "light")


def test_settings_actions_are_framed_buttons_and_switches_check_boxes(window, qtbot):
    """Every command on the Settings page is a framed push button (an
    action), a check box (an on/off setting) or a segment of the theme's
    control; none is a frameless tool button that reads as plain text.
    Each draws its frame, and none is the accent: the top bar's Run is the
    one primary action."""
    from PySide6.QtWidgets import QCheckBox, QPushButton, QToolButton

    from spacemissionstudio.gui.widgets import ActionButton, ActionCheckBox

    page = _settings(window, qtbot)
    assert page.findChildren(QToolButton) == []
    toggles = {"view.menu_bar", "view.status_details", "view.rail_icons", "view.inspector", "view.problems"}
    actions = {"tools.reference_data", "view.reset_layout", "help.about", "help.licences", "help.manual"}
    assert toggles | actions | {f"view.theme.{t}" for t in ("system", "light", "dark")} <= set(page.buttons)
    for command_id in toggles:
        box = page.buttons[command_id]
        assert isinstance(box, ActionCheckBox) and box.defaultAction() is window.commands.action(command_id)
    for command_id in actions:
        button = page.buttons[command_id]
        assert isinstance(button, ActionButton) and button.defaultAction() is window.commands.action(command_id)
        assert button.toolTip() == window.commands.action(command_id).toolTip()  # with its shortcut
    for button in page.findChildren(QPushButton):
        assert button.property("variant") != "primary" and not button.property("primary"), button.text()
    framed = [b for b in page.findChildren(QPushButton) if b.objectName() != "segmentButton"]
    for section in ("reference_data", "network", "layout", "about"):
        page.show_section(section)
        _settle(qtbot)
        for button in framed:
            if button.isVisible() and page.viewport().rect().contains(button.mapTo(page.viewport(),
                                                                                  button.rect().center())):
                assert _draws_a_frame(button, page.widget()), button.text()
    assert all(isinstance(b, QCheckBox) for b in (page.reduce_motion, page.offline_box))


def test_a_layout_check_box_follows_its_command(window, qtbot):
    """Settings › Layout › Inspector: a click shows or hides the panel as
    Ctrl+I does, and the box follows the panel when the shortcut or the
    menu changes it."""
    from PySide6.QtCore import Qt

    page = _settings(window, qtbot, "layout")
    box = page.buttons["view.inspector"]
    assert box.text() == "Inspector" and not box.isChecked() and not window.side_dock.isVisible()
    qtbot.mouseClick(box, Qt.MouseButton.LeftButton)
    assert window.side_dock.isVisible() and box.isChecked()
    window.commands.action("view.inspector").trigger()  # Ctrl+I
    assert not window.side_dock.isVisible() and not box.isChecked()


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_the_area_headers_commands_draw_a_frame(window, qtbot, mode):
    """The commands in the headers of Scenario, Run, Results, Budgets and
    Reports are buttons with a visible edge in both themes (they read as
    plain text on the header's surface), and none is the accent."""
    from PySide6.QtWidgets import QApplication

    assert window.open_path(_TEMPLATES / "07_attitude_pointing_with_adcs_hardware.json")
    _theme(QApplication.instance(), mode)
    try:
        checked = 0
        for area_id in ("scenario", "run", "results", "budgets", "reports"):
            window.shell.show_area(area_id)
            page = window.shell.page(area_id)
            _settle(qtbot, page)
            for button in page.buttons.values():
                if not button.isVisible():
                    continue
                assert button.property("variant") == "secondary", button.text()
                assert _draws_a_frame(button, page.title_bar), f"{area_id}: {button.text()}"
                checked += 1
        assert checked >= 5
    finally:
        _theme(QApplication.instance(), "light")


# -- UI-33: the keyboard table ------------------------------------------------------------------

def test_the_keyboard_table_fills_the_width(window, qtbot):
    """Settings › Keyboard: a DataTable whose columns fill the table (they
    ended at 438 px in a 910 px frame), the last column taking the rest;
    headings left-aligned; no grid lines; rows at the theme's height; the
    keys in the monospace font; every row in view (the page scrolls)."""
    from PySide6.QtCore import Qt

    from spacemissionstudio.gui.data_table import DataTable
    from spacemissionstudio.gui.theme import MONO_FONT_FAMILY, ROW_HEIGHT

    page = _settings(window, qtbot, "keyboard")
    table = page.shortcuts_table
    assert isinstance(table, DataTable)
    view = table.view
    _settle(qtbot, view)
    assert table.row_count() > 20 and [table.header_text(c) for c in range(3)] == ["Category", "Command", "Shortcut"]
    widths = sum(view.columnWidth(c) for c in range(table.column_count()))
    assert abs(widths - view.viewport().width()) <= 1
    assert view.columnWidth(2) > view.columnWidth(0)  # the last column stretches
    assert view.width() > page.viewport().width() / 2
    model = view.model()
    for column in range(table.column_count()):
        alignment = model.headerData(column, Qt.Orientation.Horizontal, Qt.ItemDataRole.TextAlignmentRole)
        assert alignment & int(Qt.AlignmentFlag.AlignLeft)
    assert not view.showGrid()
    assert {view.rowHeight(r) for r in range(table.row_count())} == {ROW_HEIGHT}
    font = model.data(model.index(0, 2), Qt.ItemDataRole.FontRole)
    assert font is not None and font.family() == MONO_FONT_FAMILY
    assert view.verticalScrollBar().maximum() == 0 and view.horizontalScrollBar().maximum() == 0
    rows = {table.cell(r, 1): table.cell(r, 2) for r in range(table.row_count())}
    assert rows["Save"] == "Ctrl+S" and rows["Command Palette..."] == "Ctrl+K"


# -- B6's form grid on the Settings page --------------------------------------------------------

def _elided(combo) -> bool:
    """Whether ``combo`` ends its entry in "…" (widgets.ComboBox: the room
    for its text is the edit field less SPACE["md"])."""
    from PySide6.QtWidgets import QStyle, QStyleOptionComboBox

    from spacemissionstudio.gui.theme import SPACE

    option = QStyleOptionComboBox()
    combo.initStyleOption(option)
    field = combo.style().subControlRect(QStyle.ComplexControl.CC_ComboBox, option,
                                         QStyle.SubControl.SC_ComboBoxEditField, combo)
    return combo.fontMetrics().horizontalAdvance(combo.currentText()) > field.width() - SPACE["md"]


def test_the_settings_forms_share_one_label_column(window, qtbot):
    """Appearance, Network, Change history and Layout are forms on one
    label column (B6's FormGrid): Theme, UI scale, Motion, Plot units,
    Network use, Author and the Layout rows start their fields at one x. A
    drop-down list shows its entry whole ("100 %" read "10…") and is no
    wider than FIELD_WIDTH["choice"]."""
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QFormLayout, QLabel

    from spacemissionstudio.gui.theme import FIELD_WIDTH
    from spacemissionstudio.gui.widgets import ComboBox, form_rows, grid_forms

    page = _settings(window, qtbot)
    body = page.widget()
    columns, labels = {}, []
    for form in grid_forms(body):
        for roles in form_rows(form).values():
            label, field = roles.get(QFormLayout.ItemRole.LabelRole), roles.get(QFormLayout.ItemRole.FieldRole)
            if isinstance(label, QLabel) and label.text() and field is not None and field.isVisible():
                columns.setdefault(field.mapTo(body, QPoint(0, 0)).x(), []).append(label.text())
                labels.append(label.text())
    assert {"Theme", "UI scale", "Motion", "Plot units", "Network use", "Author", "Panels"} <= set(labels)
    assert len(columns) == 1, columns
    combos = [combo for combo in body.findChildren(ComboBox) if combo.isVisible()]
    assert len(combos) == 2
    for combo in combos:
        for index in range(combo.count()):
            combo.setCurrentIndex(index)
            assert not _elided(combo), combo.currentText()
            assert combo.width() <= FIELD_WIDTH["choice"]
    page.ui_scale.setCurrentIndex(page.ui_scale.findData(100))
    page.plot_units.setCurrentIndex(0)
