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
"""Home, the command palette, the run pages, the Log and the dialogs (UI
audit B12), measured in a shown window with the app's theme:

- UI-23: Run › Run in SIL mode shows the "Spacecraft" label only with its
  list; the window writes every path with "›", never ">";
- UI-31: a run's progress lines are not in the Log (the engine test is in
  ``tests/test_service_run_live.py``);
- UI-32: Home's recent list says what it lists (a file opened or saved; a
  template once saved) and follows an open or a save at once;
- UI-38: a template card is as tall as its title and kind, has no buttons
  of its own, and the selected card has the accent edge; the details have
  one Open and a Customize that names what it does differently;
- UI-40: the palette shows each shortcut in a column of its own at the
  right in the monospace font, and a disabled command's reason under it
  and as its tooltip; every disabled command of the window says why;
- UI-48: About is a themed window with the versions, the licence and the
  licences' and manual's commands; a confirmation shows the theme's
  caution sign, not Qt's question mark;
- UI-50: Problems lists the warnings with an error, errors first;
- from B9's review: Reports › Exports wraps its text columns so every entry
  reads whole at 1280 px, the Inspector open or closed, without a sideways
  scroll; the Budgets grids fit their width at 1280 px.

Positions and sizes are compared with each other, never with fixed pixel
values a platform's fonts would change. Sizes are read from widgets that
are shown and laid out."""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.requires_gui

_TEMPLATES = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"
_T01 = _TEMPLATES / "01_two_body_circular_orbit.json"
_PATH_WITH_ANGLE = re.compile(r"[\w.)] > [A-Z]")  # "Settings > Keyboard": a path written with ">"


@pytest.fixture(scope="module")
def _shared_window(qapp, tmp_path_factory):
    """One 1280 x 720 main window with the app's light theme for the module,
    in a home of its own."""
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
    """The module's window at 1280 x 720 with template 01 open, the panels hidden."""
    _shared_window.resize(1280, 720)  # [px]
    assert _shared_window.open_path(_T01)
    _shared_window.side_dock.hide()
    _shared_window.problems_dock.hide()
    _settle(qtbot)
    yield _shared_window
    _shared_window._mark_clean()
    _shared_window.side_dock.hide()
    _shared_window.problems_dock.hide()


def _settle(qtbot, widget=None, ms: int = 30) -> None:
    from PySide6.QtWidgets import QApplication

    if widget is not None:
        qtbot.waitUntil(widget.isVisible, timeout=5000)
    for _ in range(3):
        QApplication.processEvents()
        qtbot.wait(ms)


def _inspector(window, qtbot, shown: bool) -> None:
    window.side_dock.setVisible(shown)
    _settle(qtbot)
    assert window.side_dock.isVisible() == shown


# -- UI-23: Run › Run in SIL mode; one path separator --------------------------------------------

def test_the_sil_spacecraft_label_shows_only_with_its_list(qtbot):
    """With no spacecraft whose flight software can be exported, Run › Run
    in SIL mode shows neither the "Spacecraft" label nor its list, only the
    note that says why; with one, the label shows with its list, which it
    names (its buddy)."""
    from PySide6.QtWidgets import QLabel

    from spacemissionstudio.gui.run_page import RunPage

    page = RunPage()
    qtbot.addWidget(page)
    page.show_mode("sil")
    page.show()
    page.set_sil_spacecraft([], lambda _name: None)
    labels = [label for label in page.findChildren(QLabel) if label.text() == "Spacecraft"]
    assert len(labels) == 1
    assert not labels[0].isVisibleTo(page) and not page.sil_combo.isVisibleTo(page)
    assert page.sil_none_label.isVisibleTo(page)
    page.set_sil_spacecraft(["sat-1"], lambda _name: None)
    assert labels[0].isVisibleTo(page) and page.sil_combo.isVisibleTo(page)
    assert labels[0].buddy() is page.sil_combo and not page.sil_none_label.isVisibleTo(page)


def _window_texts(window) -> list[str]:
    """Every text the window can show: each widget's text, placeholder and
    tooltip (shown or not), each action's text and tooltip, each tab's
    text and tooltip, and the palette's rows."""
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QAbstractButton, QLabel, QLineEdit, QTabBar, QWidget

    from spacemissionstudio.gui.command_palette import CommandPalette

    texts = []
    for widget in [window, *window.findChildren(QWidget)]:
        texts.append(widget.toolTip())
        if isinstance(widget, (QLabel, QAbstractButton)):
            texts.append(re.sub(r"<[^>]+>", "", widget.text()))
        if isinstance(widget, QLineEdit):
            texts.append(widget.placeholderText())
        if isinstance(widget, QTabBar):
            for index in range(widget.count()):
                texts += [widget.tabText(index), widget.tabToolTip(index)]
    for action in window.findChildren(QAction):
        texts += [action.text(), action.toolTip()]
    palette = CommandPalette(window.palette_entries(), window)
    texts += [palette.list.item(row).text() for row in range(palette.list.count())]
    texts += [palette.list.item(row).toolTip() for row in range(palette.list.count())]
    palette.deleteLater()
    return [text for text in texts if text]


def test_the_window_writes_every_path_with_the_single_angle_quote(window, qtbot):
    """"›" is the only path separator in the window (UI audit UI-23, UI-40):
    no label, button, tooltip, action, tab or palette row writes a path
    with ">", in each run mode."""
    found = set()
    for mode in ("single", "monte_carlo", "sil"):
        window.set_run_mode(mode)
        window.shell.show_area("run")
        window.run_views.setCurrentWidget(window.run_page)
        _settle(qtbot)
        found |= {text for text in _window_texts(window) if _PATH_WITH_ANGLE.search(text)}
    window.set_run_mode("single")
    assert sorted(found) == []


def test_the_problems_panel_writes_an_engine_path_with_the_single_angle_quote():
    """An engine message's path ("Settings > Reference data") shows with
    "›" in the Problems panel; a comparison ("> 0") stays as it is."""
    from spacemissionstudio.gui.workspace_panels import problem_row, window_path

    assert window_path("files missing; Settings > Reference data downloads them") == \
        "files missing; Settings › Reference data downloads them"
    assert window_path("Mass [kg] must be > 0") == "Mass [kg] must be > 0"
    assert problem_row("warning", "x: Settings > Reference data", "x: Settings > Reference data").shown == \
        "x: Settings › Reference data"


# -- UI-32: Home's recent scenarios ------------------------------------------------------------

def test_the_recent_list_says_its_rule_and_follows_an_open_or_a_save_at_once(window, qtbot, tmp_path):
    """A template opens unsaved, so it is not a recent file: the list stays
    empty and its empty state says what it lists, a template once it is
    saved, every line of it in view. Saved, the file is listed at once, without Home being shown
    again; a file opened is listed at once too."""
    from spacemissionstudio.gui import recent_files
    from spacemissionstudio.gui.widgets import EmptyState

    recent_files.clear()
    home = window.load_scenario_widget
    home.refresh_recent()
    assert window.open_path(_T01)
    window.shell.show_area("home")
    _settle(qtbot, home)
    assert home.recent_paths() == []
    assert isinstance(home.recent_empty, EmptyState) and home.recent_empty.isVisible()
    words = home.recent_empty.text().lower()
    assert "open or save" in words and "template" in words and "save it" in words
    label = home.recent_empty.text_label  # every line of it in view, at the column's width
    assert label.height() >= label.heightForWidth(label.width())
    saved = tmp_path / "my_orbit.json"
    window._save_to(saved)
    assert home.recent_paths() == [saved.resolve()]
    assert home.recent_list.isVisible() and not home.recent_empty.isVisible()
    other = tmp_path / "other.json"
    other.write_text(_T01.read_text(encoding="utf-8"), encoding="utf-8")
    assert window.open_path(other)
    assert home.recent_paths() == [other.resolve(), saved.resolve()]
    recent_files.clear()
    home.refresh_recent()


# -- UI-38: the template cards ----------------------------------------------------------------

def test_a_card_is_as_tall_as_its_title_and_kind_and_has_no_buttons(window, qtbot):
    """A card holds its title and its kind, no buttons (the details hold
    them): no row of the grid is taller than its tallest card's text and
    the card's margins, so no card has a blank lower third."""
    from PySide6.QtWidgets import QAbstractButton

    window.shell.show_area("home")
    home = window.load_scenario_widget
    _settle(qtbot, home.grid)
    cards = home.grid.visible_cards()
    assert cards and all(card.findChildren(QAbstractButton) == [] for card in cards)
    rows: dict[int, list] = {}
    for card in cards:
        rows.setdefault(card.y(), []).append(card)
    for row in rows.values():
        margins = row[0].layout().contentsMargins()
        needed = max(margins.top() + margins.bottom() + row[0].layout().spacing()
                     + card.title_label.heightForWidth(card.title_label.width())
                     + card.type_label.heightForWidth(card.type_label.width())
                     + 2 * card.frameWidth() for card in row)
        assert max(card.height() for card in row) <= needed + 2 * 2  # [px] the focus ring's margin


def _edge_colours(widget) -> set[str]:
    """The colours of ``widget``'s left edge, its first three pixel columns at its middle."""
    image = widget.grab().toImage()
    y = image.height() // 2
    return {image.pixelColor(x, y).name() for x in range(3)}


def test_the_selected_card_has_the_accent_edge(window, qtbot):
    """The selected card shows the theme's selection edge in the accent;
    another card does not."""
    from spacemissionstudio.gui.theme import TOKENS

    window.shell.show_area("home")
    home = window.load_scenario_widget
    _settle(qtbot, home.grid)
    selected, other = home.select(2), home.cards[3]
    _settle(qtbot)
    accent = TOKENS["accent"].lower()
    assert selected.is_selected()
    assert accent in _edge_colours(selected)
    assert accent not in _edge_colours(other)


def test_the_details_have_one_open_and_a_customize_that_names_its_difference(window, qtbot, monkeypatch):
    """One way to open a template: Open template in the details (Enter or a
    double-click on the card do the same). Customize and open... names what
    it does differently: the wizard first, then the result opens."""
    from PySide6.QtWidgets import QPushButton

    from spacemissionstudio.gui.template_wizard import TemplateCustomizeWizard

    window.shell.show_area("home")
    home = window.load_scenario_widget
    card = home.select("22 - Starter: your first LEO satellite")
    names = [button.text() for button in home.findChildren(QPushButton) if button.isVisibleTo(home)]
    assert names.count("Open template") == 1 and "Open" not in names
    assert "Customize and open..." in names and "Customize..." not in names
    assert "wizard" in home.customize_template_button.toolTip()
    monkeypatch.setattr(TemplateCustomizeWizard, "exec", lambda self: TemplateCustomizeWizard.DialogCode.Accepted)
    home.customize_template_button.click()
    assert window.current_view() is window.scenario_editor and window._current_path is None
    assert window.scenario_editor.to_scenario().name == card.name


# -- UI-40: the command palette ---------------------------------------------------------------

def _palette(qtbot, entries):
    from spacemissionstudio.gui.command_palette import CommandPalette

    palette = CommandPalette(entries)
    qtbot.addWidget(palette)
    palette.resize(520, 420)  # [px]
    palette.show()
    qtbot.waitExposed(palette)
    return palette


def _row(palette, shown: str) -> int:
    return next(row for row in range(palette.list.count()) if palette.list.item(row).text() == shown)


def test_the_palette_shows_each_shortcut_right_aligned_in_the_monospace_font(qtbot):
    """A row's name is the entry's path written with "›", without its
    shortcut; the shortcut is drawn in a column of its own, right-aligned at
    the row's right inset, in the monospace font, the same for every row."""
    from PySide6.QtWidgets import QStyleOptionViewItem

    from spacemissionstudio.gui.command_palette import SHORTCUT_ROLE, PaletteEntry
    from spacemissionstudio.gui.theme import mono_font

    palette = _palette(qtbot, [PaletteEntry("File > Save", lambda: None, "Ctrl+S"),
                               PaletteEntry("File > Save As...", lambda: None, "Ctrl+Shift+S"),
                               PaletteEntry("Go to > Timeline", lambda: None)])
    rights = set()
    for shown, keys in (("File › Save", "Ctrl+S"), ("File › Save As...", "Ctrl+Shift+S")):
        row = _row(palette, shown)
        item = palette.list.item(row)
        assert item.data(SHORTCUT_ROLE) == keys and keys not in item.text()
        option = QStyleOptionViewItem()
        option.rect = palette.list.visualItemRect(item)
        rect = palette.delegate.key_rect(option, palette.list.indexFromItem(item))
        assert rect.width() > 0 and rect.left() > option.rect.center().x()
        rights.add(rect.right())
    assert len(rights) == 1  # one right edge: a column
    assert palette.delegate.key_font.family() == mono_font().family()
    assert palette.list.item(_row(palette, "Go to › Timeline")).data(SHORTCUT_ROLE) == ""


def test_a_disabled_palette_row_says_why_under_its_name_and_on_hover(qtbot):
    """A disabled command is listed, greyed, with its reason under its name
    (its row is taller) and as its tooltip; the "Off:" line of its action's
    tooltip is the reason when the registry gives none."""
    from PySide6.QtCore import Qt

    from spacemissionstudio.gui.command_palette import REASON_ROLE, PaletteEntry

    palette = _palette(qtbot, [PaletteEntry("Run > Run", lambda: None, "Ctrl+R"),
                               PaletteEntry("Run > Cancel Run", lambda: None, "Esc", enabled=False,
                                            reason="No run is going.")])
    on, off = (palette.list.item(_row(palette, shown)) for shown in ("Run › Run", "Run › Cancel Run"))
    assert not off.flags() & Qt.ItemFlag.ItemIsEnabled
    assert off.toolTip() == off.data(REASON_ROLE) == "No run is going."
    assert not on.data(REASON_ROLE)
    assert palette.list.visualItemRect(off).height() > palette.list.visualItemRect(on).height()


def test_the_off_line_of_a_tooltip_is_a_commands_reason(qtbot):
    """A command disabled with an "Off:" line in its tooltip and no registry
    reason gives that line as its palette reason."""
    from PySide6.QtWidgets import QWidget

    from spacemissionstudio.gui.actions import ActionRegistry
    from spacemissionstudio.gui.command_palette import command_entries

    owner = QWidget()
    qtbot.addWidget(owner)
    registry = ActionRegistry(owner)
    action = registry.add("x.go", "Go", category="X", area="global")
    action.setToolTip("Go\nOff: nothing to go to. Add a target first.")
    action.setEnabled(False)
    (entry,) = command_entries(registry)
    assert entry.reason == "Off: nothing to go to. Add a target first."


@pytest.mark.parametrize("scenario_open", (False, True))
def test_every_disabled_command_of_the_window_says_why(qtbot, monkeypatch, scenario_open):
    """With no scenario open, and with one open before a run, every command
    the palette lists as disabled says why it is off."""
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    if scenario_open:
        assert window.open_path(_T01)
    disabled = [entry for entry in window.palette_entries() if not entry.enabled]
    assert disabled
    assert [entry.label for entry in disabled if not entry.reason] == []
    window._mark_clean()


# -- UI-48: About and the confirmations ---------------------------------------------------------

def test_about_is_a_themed_window_with_the_versions_the_licence_and_the_links(window, qtbot):
    """Help › About opens a window of the app (not a modal message box):
    its name, the version, the Basilisk version, the licence, and the
    Third-Party Licences and User Manual commands of the window; Close
    closes it. A second About shows the same window."""
    import spacemissionstudio
    from spacemissionstudio import dependencies
    from spacemissionstudio.gui.about_dialog import AboutDialog

    window.on_about()
    dialog = window._about_dialog
    _settle(qtbot, dialog)
    assert isinstance(dialog, AboutDialog) and not dialog.isModal()
    text = dialog.text()
    assert "SpaceMissionStudio" in text and spacemissionstudio.__version__ in text
    basilisk = dependencies.basilisk_version()
    assert f"Basilisk: {basilisk}" in text if basilisk else "Basilisk: not installed" in text
    assert "EUPL" in text and "ISC" in text
    assert [button.defaultAction() for button in dialog.link_buttons] == [window.licences_action,
                                                                          window.manual_action]
    window.on_about()
    assert window._about_dialog is dialog
    dialog.close_button.click()
    assert not dialog.isVisible()


def test_a_confirmation_shows_the_theme_caution_sign_not_a_question_mark(qapp):
    """A confirmation (Qt's question box, which every confirmation of the
    app uses) shows the theme's caution sign: the same image as the
    warning's, the Lucide triangle in the caution colour, at the theme's
    message icon size; never Fusion's "?"."""
    from PySide6.QtWidgets import QMessageBox, QStyle, QStyleFactory

    from spacemissionstudio.gui.theme import icon
    from spacemissionstudio.gui.theme.style import MESSAGE_ICON_PX, AppStyle

    style = AppStyle()
    question = style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxQuestion).pixmap(MESSAGE_ICON_PX).toImage()
    caution = icon("triangle-alert", "status.caution").pixmap(MESSAGE_ICON_PX).toImage()
    fusion = QStyleFactory.create("Fusion").standardIcon(
        QStyle.StandardPixmap.SP_MessageBoxQuestion).pixmap(MESSAGE_ICON_PX).toImage()
    assert question == caution and question != fusion.convertToFormat(question.format())
    assert style.pixelMetric(QStyle.PixelMetric.PM_MessageBoxIconSize) == MESSAGE_ICON_PX
    if isinstance(qapp.style(), AppStyle):  # the app's style (set by apply_theme): a question box shows it
        box = QMessageBox(QMessageBox.Icon.Question, "Unsaved changes", "Save them?")
        assert box.iconPixmap().toImage() == caution.convertToFormat(box.iconPixmap().toImage().format())


# -- UI-50: Problems with an error and warnings ------------------------------------------------------

def test_problems_list_the_warnings_with_an_error_errors_first(window, qtbot):
    """A scenario with plausibility warnings keeps them listed while an
    error is in it, under the error; no "check not run" line stands in
    for a check the error stops."""
    assert window.open_path(_TEMPLATES / "32_smallsat_design_checks.json")
    editor = window.scenario_editor
    warnings_before = [text for severity, text in editor.problems if severity == "warning"]
    assert warnings_before and not [text for severity, text in editor.problems if severity == "error"]
    editor.name_edit.setText("")
    editor.revalidate()
    severities = [row[0] for row in window.problems_widget.shown_rows()]
    assert "Error" in severities and "Warning" in severities
    assert severities == sorted(severities, key=lambda word: word != "Error")  # errors first
    assert not [text for _severity, text in editor.problems if text.startswith("check not run")]
    assert len([word for word in severities if word == "Warning"]) >= len(warnings_before)


# -- B9 review: Reports › Exports wraps; the Budgets grids fit ---------------------------------------

@pytest.mark.parametrize("inspector", (False, True))
def test_every_export_reads_whole_without_hover(window, qtbot, inspector):
    """At 1280 x 720, the Inspector open or closed, Reports › Exports does
    not scroll sideways and no cell is elided: the text columns wrap and a
    row grows to its tallest cell, never below the table-row height; with
    the Inspector open some rows are taller."""
    from spacemissionstudio.gui.theme import ROW_HEIGHT

    _inspector(window, qtbot, inspector)
    window.shell.show_area("reports")
    window.reports_views.setCurrentWidget(window.exports_page)
    table = window.exports_page.table
    _settle(qtbot, table.view)
    view = table.view
    assert view.horizontalScrollBar().maximum() == 0
    elided = [(table.cell(row, column), column) for row in range(table.row_count())
              for column in table.shown_columns() if table.cell_elided(row, column)]
    assert elided == []
    heights = [view.rowHeight(row) for row in range(table.row_count())]
    assert min(heights) >= ROW_HEIGHT
    if inspector:
        assert max(heights) > ROW_HEIGHT


def _budgets_window(window, tmp_path):
    """The window with the budgets fixture open (template 22 with the design
    note's section: OBC, camera and a harness), on Budgets › Equipment."""
    import json
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import budgets_fixtures as fx

    path = tmp_path / "budgets.json"
    path.write_text(json.dumps(fx.scenario_data()), encoding="utf-8")
    assert window.open_path(path)
    window.shell.show_area("budgets")
    return window.budgets_views


def _heading_cut(view) -> list[str]:
    """The headings of ``view`` narrower than the style draws them."""
    from PySide6.QtCore import Qt

    header, model = view.horizontalHeader(), view.model()
    return [str(model.headerData(c, Qt.Orientation.Horizontal)) for c in range(model.columnCount())
            if not view.isColumnHidden(c) and header.sectionSize(c) < header.sectionSizeHint(c)]


@pytest.mark.parametrize("inspector", (False, True))
def test_the_budgets_grids_fit_their_width(window, qtbot, tmp_path, inspector):
    """At 1280 x 720 without the Inspector, no grid of Budgets › Equipment
    and no table of Budgets › Power scrolls sideways, and no heading is cut:
    the columns fit each grid's width, the three lower grids share their row
    by what each needs, and long headings are two lines. With the Inspector
    open no heading is cut either and the page itself never scrolls
    sideways; a table whose headings alone are wider than its share (the
    power table of the items, twelve columns) scrolls inside itself."""
    from PySide6.QtWidgets import QScrollArea

    from spacemissionstudio.gui.budgets_area import EditableTable
    from spacemissionstudio.gui.data_table import DataTable

    views = _budgets_window(window, tmp_path)
    _inspector(window, qtbot, inspector)
    page = views.equipment_page
    views.setCurrentWidget(page)
    _settle(qtbot, page.items_table.view)
    grids = [table for table in page.findChildren(EditableTable) if table.view.isVisible()]
    assert len(grids) == 4
    for grid in grids:
        assert _heading_cut(grid.view) == [], grid.title_label.text()
        if not inspector:
            assert grid.view.horizontalScrollBar().maximum() == 0, grid.title_label.text()
    views.setCurrentWidget(views.power_page)
    _settle(qtbot, views.power_page.totals_table.view)
    tables = [table for table in views.power_page.findChildren(DataTable) if table.view.isVisible()]
    assert tables
    for table in tables:
        assert _heading_cut(table.view) == [], table.view.accessibleName()
        if not inspector:
            assert table.view.horizontalScrollBar().maximum() == 0, table.view.accessibleName()
    pages = [area for area in views.findChildren(QScrollArea) if area.isVisible()]  # the page, not a table
    assert pages and all(area.horizontalScrollBar().maximum() == 0 for area in pages)
    window._mark_clean()
