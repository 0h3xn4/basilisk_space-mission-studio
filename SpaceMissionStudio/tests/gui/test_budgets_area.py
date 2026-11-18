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
"""The Budgets area (System Budget Studio merge, phase 1, PR B; design note
section 8, decisions B-11, B-12, B-15): its place in the rail, its pages
(Equipment, Power, Mass, Propellant), the editable equipment grid and its
way into the scenario (saved, undone, checked), the placeholders, the
shortcuts and palette entries, the accessible names, both themes and the
1280 x 720 window."""

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import budgets_fixtures as fx  # noqa: E402

pytestmark = pytest.mark.requires_gui

_EQUIPMENT = ("Name", "Subsystem", "Mass column", "Bus", "Maturity", "Mass [kg]", "Mass source", "Mass in model")
_MASS = _EQUIPMENT.index("Mass [kg]")
_SOURCE = _EQUIPMENT.index("Mass source")


@pytest.fixture(autouse=True)
def _isolated_autosave(tmp_path, monkeypatch):
    """Keep the window's autosave away from the real home directory."""
    from spacemissionstudio.gui import autosave

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
    return w


@pytest.fixture
def toasts(monkeypatch):
    """The toasts the Budgets area shows, as ``(message, kind)``."""
    from spacemissionstudio.gui import budgets_area

    shown = []
    real = budgets_area.show_toast
    monkeypatch.setattr(budgets_area, "show_toast", lambda parent, message, kind="success", **k: shown.append(
        (message, kind)) or real(parent, message, kind, **k))
    return shown


def _open(window, folder: Path, data: dict | None = None) -> Path:
    path = folder / "budgets.json"
    path.write_text(json.dumps(fx.scenario_data() if data is None else data), encoding="utf-8")
    assert window.open_path(path)
    return path


@pytest.fixture
def window(unopened, tmp_path):
    """The window with the budgets fixture open (template 22 with the design
    note's section: OBC, camera and a harness of placeholder mass)."""
    unopened.scenario_path = _open(unopened, tmp_path)
    return unopened


def _section(window, name: str = "my-sat"):
    sc = next(sc for sc in window.scenario_editor.draft_scenario().spacecraft if sc.name == name)
    return sc.budgets


def _items(window):
    return window.budgets_views.equipment_page.items_table


# -- the area -----------------------------------------------------------------------------------

def test_the_budgets_area_follows_results_with_its_four_pages(window):
    """Budgets is after Results in the rail, Ctrl+5 (B-11), with Equipment,
    Power, Mass and Propellant; the propellant budget moved there from
    Run › Budget (Q3) and Analyses › Budget shows it there."""
    assert [area_id for area_id, _icon, _label in window._AREAS] == [
        "home", "scenario", "run", "results", "budgets", "timeline", "reports"]
    action = window.commands.action("go.budgets")
    assert action.shortcut().toString() == "Ctrl+5"
    assert window.shell.rail.buttons["budgets"].toolTip() == "Budgets (Ctrl+5)"
    assert window.shell.page("budgets").content is window.budgets_views
    views = window.budgets_views
    assert [views.tabText(i) for i in range(views.count())] == ["Equipment", "Power", "Mass", "Propellant"]
    assert "Budget" not in [window.run_views.tabText(i) for i in range(window.run_views.count())]
    assert window.commands["analyses.budget"].area == "budgets"
    window.commands.action("analyses.budget").trigger()
    assert window.shell.current_area() == "budgets" and window.current_view() is window.budget_widget
    assert window.top_bar.breadcrumb_label.text() == "Budgets › Propellant"
    action.trigger()
    assert window.shell.current_area() == "budgets"


def test_the_go_menu_palette_and_breadcrumbs_name_each_page(window):
    from spacemissionstudio.gui.menu_bar import command_ids

    placed = command_ids()
    assert placed.index("go.budgets") == placed.index("go.results") + 1
    labels = {entry.label: entry for entry in window.palette_entries()}
    for page in ("Equipment", "Power", "Mass", "Propellant"):
        assert f"Go to > Budgets > {page}" in labels
    assert "Go to > Budgets" in labels and "power budget" in labels["Go to > Budgets"].keywords
    labels["Go to > Budgets > Power"].run()
    assert window.current_view() is window.budgets_views.power_page
    assert window.top_bar.breadcrumb_label.text() == "Budgets › Power"


def test_the_area_says_when_no_scenario_is_open(unopened):
    """With nothing open, Budgets shows the empty state, its commands are
    disabled and the palette offers none of its pages."""
    unopened.show()
    unopened.shell.show_area("budgets")
    page = unopened.shell.page("budgets")
    assert page.showing_empty and page.empty_state.isVisible() and not page.content.isVisible()
    assert "No scenario is open" in page.empty_state.title_label.text()
    for command_id in ("budgets.add_item", "budgets.remove_item", "budgets.copy_csv", "analyses.budget"):
        assert not unopened.commands.action(command_id).isEnabled(), command_id
    assert unopened.commands.action("go.budgets").isEnabled()
    assert not any(entry.label.startswith("Go to > Budgets >") for entry in unopened.palette_entries())


# -- the Equipment page ------------------------------------------------------------------------

def test_the_equipment_grid_is_a_model_view_table_of_the_items(window):
    """B-12: a QTableView over an editable QAbstractTableModel (never a
    QTableWidget), with the item fields as columns."""
    from PySide6.QtCore import QAbstractTableModel, Qt
    from PySide6.QtWidgets import QTableView, QTableWidget

    window.show_budgets()
    table = _items(window)
    assert isinstance(table.view, QTableView) and not isinstance(table.view, QTableWidget)
    assert isinstance(table.model, QAbstractTableModel)
    assert window.budgets_views.findChildren(QTableWidget) == []
    assert tuple(table.headers()) == _EQUIPMENT
    assert [table.cell(r, 0) for r in range(table.model.rowCount())] == ["OBC", "camera", "harness"]
    assert table.model.flags(table.model.index(0, 0)) & Qt.ItemFlag.ItemIsEditable
    assert table.model.flags(table.model.index(0, len(_EQUIPMENT) - 1)) & Qt.ItemFlag.ItemIsUserCheckable
    assert table.cell(0, _MASS) == "1.2" and table.cell(0, _SOURCE) == "data sheet rev B"
    assert table.model.data(table.model.index(0, _MASS), Qt.ItemDataRole.TextAlignmentRole) & Qt.AlignmentFlag.AlignRight


def test_a_placeholder_reads_tbd_with_an_icon_and_text(window):
    """The harness's mass is a placeholder (null, "TBD"): "TBD" with the
    caution icon and a tooltip, never a colour alone and never zero."""
    from PySide6.QtCore import Qt

    window.show_budgets()
    model = _items(window).model
    index = model.index(2, _MASS)
    assert model.data(index) == "TBD"
    assert not model.data(index, Qt.ItemDataRole.DecorationRole).isNull()
    assert "unknown" in model.data(index, Qt.ItemDataRole.ToolTipRole)
    assert model.data(model.index(0, _MASS), Qt.ItemDataRole.DecorationRole) is None  # a sourced number
    # a number with the source "TBD" is a placeholder too: its number, and the icon
    assert _items(window).edit_cell(2, _MASS, "0.4")
    assert model.data(index) == "0.4" and not model.data(index, Qt.ItemDataRole.DecorationRole).isNull()
    assert model.data(index, Qt.ItemDataRole.AccessibleTextRole) == "0.4, placeholder"


def test_an_edit_goes_into_the_scenario_and_is_saved_and_undone(window, qtbot):
    """A cell edited: the scenario's section changes (unsaved), Save writes
    it, the file opened again has it, and Undo takes it back."""
    from spacemissionstudio.schema import load_scenario

    window.show_budgets()
    table = _items(window)
    assert table.edit_cell(2, _MASS, "0.5")
    assert table.edit_cell(2, _SOURCE, "harness estimate")
    assert table.edit_cell(0, _EQUIPMENT.index("Subsystem"), "OBDH")
    harness = _section(window).item("harness")
    assert (harness.mass_kg.value, harness.mass_kg.source) == (0.5, "harness estimate")
    assert _section(window).item("OBC").subsystem == "OBDH"
    assert window.windowTitle().endswith("*")
    window.on_save()
    assert not window.windowTitle().endswith("*")
    saved = load_scenario(window.scenario_path).spacecraft[0].budgets
    assert saved.item("harness").mass_kg.value == 0.5 and saved.item("OBC").subsystem == "OBDH"
    assert saved == _section(window)

    assert window.open_path(window.scenario_path)  # opened again: the grid shows the file
    window.show_budgets()
    assert _items(window).cell(2, _MASS) == "0.5" and _items(window).cell(0, 1) == "OBDH"
    assert _items(window).edit_cell(0, 0, "computer")
    window.on_undo()
    assert _section(window).item("OBC") is not None and _section(window).item("computer") is None
    assert _items(window).cell(0, 0) == "OBC"  # the grid follows the undo


def test_a_renamed_item_keeps_its_system_modes(window):
    """Renaming an item renames it in every system mode's units; a power
    mode renamed follows too; the system modes table has a column per item
    with power modes, and an item a mode does not list reads "not listed"."""
    window.show_budgets()
    page = window.budgets_views.equipment_page
    assert _items(window).edit_cell(1, 0, "imager")
    assert [mode.units for mode in _section(window).modes] == [{"OBC": "on", "imager": "off"},
                                                               {"OBC": "on", "imager": "imaging"}]
    assert page.system_modes_table.headers() == ["Name", "Duty cycle [-]", "OBC", "imager"]
    _items(window).select_row(1)
    assert page.modes_table.title_label.text() == "Power modes of imager"
    assert page.modes_table.edit_cell(0, 0, "science")
    assert _section(window).modes[1].units["imager"] == "science"
    assert page.system_modes_table.edit_cell(0, 3, "")
    assert "imager" not in _section(window).modes[0].units
    assert page.system_modes_table.cell(0, 3) == "not listed"


def test_add_and_remove_items_modes_and_buses(window, toasts):
    """The page's buttons and their empty states: Add makes a placeholder,
    never a guessed number; Remove takes an item out of the modes too."""
    window.show_budgets()
    page = window.budgets_views.equipment_page
    page.add_item_action.trigger()
    item = _section(window).item("item 1")
    assert item is not None and item.mass_kg.placeholder
    assert _items(window).cell(3, _MASS) == "TBD"
    assert page.modes_table.stack.currentWidget() is page.modes_table.empty  # the new item has no power mode
    assert page.modes_table.empty.button.text() == "Add Power Mode"
    page.modes_table.empty.button.click()
    item = _section(window).item("item 1")
    assert [m.name for m in item.power_modes] == ["mode 1"] and item.power_modes[0].average_w.placeholder
    assert item.bus == "main"  # an item with power modes names a bus: the one bus
    page.add_system_mode_action.trigger()
    assert _section(window).modes[-1].name == "system mode 1"
    page.add_bus_action.trigger()
    assert [bus.name for bus in _section(window).buses] == ["main", "bus 1"]
    page.settings_table.select_row([r.bus.name if r.bus else "" for r in page.settings_table.model.rows].index("bus 1"))
    page.remove_bus_action.trigger()
    assert [bus.name for bus in _section(window).buses] == ["main"]
    _items(window).select_row(0)
    page.remove_item_action.trigger()
    assert _section(window).item("OBC") is None
    assert all("OBC" not in mode.units for mode in _section(window).modes)
    assert ("Removed OBC. Undo: Ctrl+Z.", "success") in toasts


def test_a_spacecraft_without_a_section_offers_to_add_one(unopened, tmp_path, toasts):
    """Without a section the page says so, with the one primary action;
    the section added has one bus and placeholders, and the empty list
    then offers Add Item."""
    data = fx.scenario_data()
    del data["spacecraft"][0]["budgets"]
    _open(unopened, tmp_path, data)
    unopened.show_budgets()
    page = unopened.budgets_views.equipment_page
    assert page.stack.currentWidget() is page.empty_state
    assert page.empty_state.title_label.text() == "No equipment list"
    assert page.empty_state.button.text() == "Add Budgets Section"
    assert page.empty_state.button.property("variant") != "primary"  # the top bar's Run is the accent (UI-03)
    assert unopened.budgets_views.power_page.empty_state.title_label.text() == "No power budget"
    page.empty_state.button.click()
    section = _section(unopened)
    assert [bus.name for bus in section.buses] == ["main"] and section.buses[0].converter_efficiency.placeholder
    assert section.distribution_loss.placeholder and section.equipment == []
    assert ("Added a budgets section to my-sat.", "success") in toasts
    assert page.stack.currentWidget() is page.editor
    items = page.items_table
    assert items.stack.currentWidget() is items.empty and items.empty.button.text() == "Add Item"
    items.empty.button.click()
    assert [item.name for item in _section(unopened).equipment] == ["item 1"]


def test_a_problem_shows_in_the_problems_panel_not_a_dialog(window):
    """A name used twice does not validate: the Problems panel lists it,
    the Power page says to fix it first, and activating the problem opens
    Budgets › Equipment (no dialog: the GUI tests' guard fails on one)."""
    window.show_budgets()
    assert _items(window).edit_cell(1, 0, "OBC")
    texts = [window.problems_widget.problem_at(r).text for r in range(window.problems_widget.model.rowCount())]
    problem = next(text for text in texts if "equipment names must be unique" in text)
    assert _items(window).cell(1, 0) == "OBC"  # the grid keeps the edit for the user to fix
    window.show_view(window.budgets_views.power_page)  # a page is computed when shown
    assert window.budgets_views.power_page.empty_state.title_label.text() == "The scenario has problems"
    window.shell.show_area("home")
    window._on_problem_activated(problem)
    assert window.current_view() is window.budgets_views.equipment_page


def test_a_budget_finding_opens_the_budgets_area_of_its_spacecraft(window):
    texts = [window.problems_widget.problem_at(r).text for r in range(window.problems_widget.model.rowCount())]
    finding = next(text for text in texts if "the mass of harness is a placeholder" in text)
    window._on_problem_activated(finding)
    assert window.shell.current_area() == "budgets"
    assert window.budgets_views.currentWidget() is window.budgets_views.equipment_page


# -- the Power and Mass pages ------------------------------------------------------------------

def test_the_power_page_shows_each_mode_and_the_duty_cycle_average(window):
    from spacemissionstudio.analyses.power_budget import power_budget

    window.show_view(window.budgets_views.power_page)
    page = window.budgets_views.power_page
    budget = power_budget(window.scenario_editor.to_scenario().spacecraft[0])
    table = page.totals_table
    assert [table.cell(r, 0) for r in range(table.row_count())] == ["nominal", "imaging", "Duty-cycle average"]
    assert table.cell(1, 2) == f"{budget.mode('imaging').average.load_w:.2f}" == "10.00"
    assert table.cell(0, 6) == f"{budget.mode('nominal').average.source_margined_w:.2f}"
    assert table.cell(2, 2) == f"{budget.duty_cycle_average().load_w:.2f}" and table.row_is_bold(2)
    assert table.header_text(2) == "Load [W]"
    assert page.status_badge.text() == "Complete" and page.status_badge.property("badge") == "normal"
    page.mode_combo.setCurrentText("imaging")
    items = page.items_table
    assert [items.cell(r, 0) for r in range(items.row_count())] == ["OBC", "camera"]
    assert items.cell(1, 4) == "imaging" and items.cell(1, 7) == "6.00"  # 12 W at a duty cycle of 0.5
    assert [page.buses_table.cell(r, 0) for r in range(page.buses_table.row_count())] == ["main"]
    assert [page.subsystems_table.cell(r, 0) for r in range(page.subsystems_table.row_count())] == ["DHS", "PL"]
    assert page.inputs_sheet.value("distribution loss") == "0.02"


def test_an_unknown_power_says_so_with_a_badge_and_the_reason(window):
    """A placeholder efficiency: the source power is unknown, never zero;
    the badge says it in text, the notes say why."""
    window.show_budgets()
    page = window.budgets_views.equipment_page
    bus_row = next(r for r, setting in enumerate(page.settings_table.model.rows) if setting.bus is not None)
    assert page.settings_table.edit_cell(bus_row, 3, "TBD")
    window.show_view(window.budgets_views.power_page)
    power = window.budgets_views.power_page
    assert power.status_badge.text() == "Unknown values" and power.status_badge.property("badge") == "caution"
    assert power.totals_table.cell(0, 2) == "4.00" and power.totals_table.cell(0, 5) == "unknown"
    assert any("converter_efficiency" in note and "unknown" in note for note in power.findings.notes)
    assert power.inputs_sheet.value("converter efficiency, bus main") == "TBD"
    assert page.settings_table.model.data(page.settings_table.model.index(bus_row, 1)) == "0.9"


def test_the_mass_page_shows_the_equipment_lines_and_the_unknown_mass(window):
    window.show_view(window.budgets_views.mass_page)
    page = window.budgets_views.mass_page
    table = page.table
    assert [table.cell(r, 0) for r in range(table.row_count())] == ["OBC", "camera", "harness"]
    assert table.cell(2, 4) == "unknown" and table.cell(0, 4) == "1.20" and table.cell(0, 1) == "equipment list"
    assert page.totals_sheet.value("Basic dry mass") == "4.20"
    assert page.status_badge.text() == "Incomplete: unknown masses"
    assert any("unknown mass" in note for note in page.notes.notes)


def test_copy_as_csv_on_each_page_has_the_provenance(window, qapp, toasts):
    from PySide6.QtGui import QGuiApplication

    views = window.budgets_views
    texts = {}
    for page in (views.equipment_page, views.power_page, views.mass_page):
        window.show_view(page)
        window.commands.action("budgets.copy_csv").trigger()
        texts[page] = QGuiApplication.clipboard().text()
        assert "Scenario SHA-256" in texts[page]
    assert texts[views.equipment_page].startswith("item,subsystem,mass_column,bus,maturity,mass_kg")
    assert texts[views.power_page].splitlines()[1].startswith("nominal,0.8,4.0,")
    assert "harness,equipment list,wire_harness,1: estimated,,55.0" in texts[views.mass_page]
    assert ("Copied the mass budget as CSV.", "success") in toasts


# -- the Propellant page and the exports -------------------------------------------------------

def test_the_propellant_page_is_the_budget_widget_and_follows_the_spacecraft(unopened, tmp_path):
    """Two spacecraft: the header's picker shows, picks the pages'
    spacecraft and Propellant's too."""
    data = fx.scenario_data()
    second = copy.deepcopy(data["spacecraft"][0])
    second["name"] = "my-sat-2"
    del second["budgets"]
    data["spacecraft"].append(second)
    _open(unopened, tmp_path, data)
    unopened.show_budgets()
    views = unopened.budgets_views
    assert views.selector.isVisibleTo(unopened)
    assert unopened.shell.page("budgets").header.isAncestorOf(views.selector)
    views.spacecraft_combo.setCurrentText("my-sat-2")
    assert views.equipment_page.empty_state.title_label.text() == "No equipment list"
    assert unopened.budget_widget.spacecraft_combo.currentText() == "my-sat-2"
    unopened.show_budgets("my-sat")
    assert views.spacecraft_name() == "my-sat" and views.equipment_page.items_table.cell(0, 0) == "OBC"


def test_the_exports_page_says_where_the_propellant_budget_is_copied():
    from spacemissionstudio.gui.exports_page import EXPORTS

    budget = next(export for export in EXPORTS if export.key == "budget_csv")
    assert budget.made_in == "Budgets › Propellant › Copy as CSV"


# -- the keyboard ------------------------------------------------------------------------------

@pytest.fixture
def active(unopened, tmp_path, qtbot):
    """The window shown and active (its shortcuts take key presses), then
    the fixture opened, as the keyboard walk's window."""
    unopened.resize(1440, 900)  # [px]
    unopened.show()
    qtbot.waitExposed(unopened)
    unopened.activateWindow()
    _open(unopened, tmp_path)
    return unopened


def test_the_budgets_commands_have_shortcuts_in_tooltips_menus_and_the_palette(active, qtbot):
    from PySide6.QtCore import Qt

    window = active

    expected = {"budgets.add_item": "Ctrl+Shift+N", "budgets.remove_item": "Ctrl+Del",
                "budgets.copy_csv": "Ctrl+Shift+C"}
    labels = {entry.label: entry for entry in window.palette_entries()}
    for command_id, keys in expected.items():
        command = window.commands[command_id]
        assert command.keys == keys and f"({keys})" in command.action.toolTip()
        assert f"Budgets > {command.label}" in labels and labels[f"Budgets > {command.label}"].shortcut == keys
    tools = next(a.menu() for a in window.menuBar().actions() if a.text().replace("&", "") == "Tools")
    budgets_menu = next(a.menu() for a in tools.actions() if a.menu() and a.text().replace("&", "") == "Budgets")
    assert [a for a in budgets_menu.actions() if not a.isSeparator()] == [
        window.commands.action(command_id) for command_id in expected]
    qtbot.keyClick(window, Qt.Key.Key_5, Qt.KeyboardModifier.ControlModifier)
    assert window.shell.current_area() == "budgets"
    window.show_budgets()
    _items(window).view.setFocus()
    qtbot.keyClick(_items(window).view, Qt.Key.Key_N,
                   Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
    assert [item.name for item in _section(window).equipment][-1] == "item 1"
    qtbot.keyClick(_items(window).view, Qt.Key.Key_Delete, Qt.KeyboardModifier.ControlModifier)
    assert [item.name for item in _section(window).equipment] == ["OBC", "camera", "harness"]


def test_remove_from_another_area_only_shows_the_page(window):
    """Ctrl+Del is the window's: from another area it shows Budgets ›
    Equipment and removes nothing."""
    window.shell.show_area("scenario")
    window.commands.action("budgets.remove_item").trigger()
    assert window.current_view() is window.budgets_views.equipment_page
    assert len(_section(window).equipment) == 3


# -- accessibility, themes and room ------------------------------------------------------------

def test_every_control_of_the_area_is_named(window):
    """Icon-only buttons have a tooltip and an accessible name; the grids,
    pickers and badges have a name a screen reader says."""
    from PySide6.QtWidgets import QComboBox, QToolButton

    views = window.budgets_views
    window.show_budgets()
    for button in views.findChildren(QToolButton):
        if button.defaultAction() is not None and \
                button.toolButtonStyle() == button.toolButtonStyle().ToolButtonIconOnly:
            assert button.toolTip() and button.accessibleName(), button
    from PySide6.QtWidgets import QTableView

    for widget in views.findChildren(QTableView) + views.findChildren(QComboBox):
        if widget.isVisibleTo(window) or widget in (views.power_page.mode_combo,):
            assert widget.accessibleName(), widget
    assert views.spacecraft_combo.accessibleName() == "Spacecraft"
    assert views.power_page.status_badge.accessibleName() == "Budget status"


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_the_pages_in_both_themes(window, restored_theme, mode):
    """Each page shows in the light and the dark theme: the badges take the
    theme's status look, the placeholder icon is drawn, nothing sets a
    colour of its own (the design rules test checks the source)."""
    from PySide6.QtCore import Qt

    from spacemissionstudio.gui.theme import apply_theme

    apply_theme(restored_theme, mode)  # the fixture puts the app's look back afterwards
    window.show()
    for page in (window.budgets_views.equipment_page, window.budgets_views.power_page,
                 window.budgets_views.mass_page):
        window.show_view(page)
        restored_theme.processEvents()
        assert not page.grab().isNull()
    decoration = _items(window).model.data(_items(window).model.index(2, _MASS), Qt.ItemDataRole.DecorationRole)
    assert not decoration.pixmap(16, 16).isNull()
    assert window.budgets_views.mass_page.status_badge.property("badge") == "caution"


def test_the_window_fits_1280_by_720_with_the_budgets_area(window, restored_theme, qtbot):
    """At 1280 x 720 with the Problems panel open the window still fits,
    and the rail shows icons only where the names do not fit, every area
    still named by its tooltip and accessible name."""
    from spacemissionstudio.gui.theme import apply_theme

    apply_theme(restored_theme, "light")  # the app's own style and font; the fixture restores the look
    window.show()
    window.show_budgets()
    window.show_problems()
    qtbot.wait(50)  # [ms] let the layouts take in the panel before measuring
    hint = window.minimumSizeHint()
    assert hint.width() <= 1280 and hint.height() <= 720, hint
    window.resize(1280, 720)  # [px]
    qtbot.wait(50)
    assert (window.width(), window.height()) == (1280, 720)
    rail = window.shell.rail
    for area_id, button in rail.buttons.items():
        assert button.height() >= button.sizeHint().height() - 1, area_id  # [px] not cut
        assert button.accessibleName() and button.toolTip(), area_id
    window.resize(1400, 1000)  # [px] room for the names again
    qtbot.wait(50)
    if rail.height() >= rail._named_height:
        assert not rail.squeezed
