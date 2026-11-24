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

"""No feature is hidden (the owner, 2026-11-24; ``docs/reference/feature-access.md``):
every command of the window is in the palette and runs from it, every
command is in the feature-access page with its keys, and the paths this
audit added work end to end (decisions FA-1 to FA-7).

``tests/test_feature_access.py`` checks the page itself: every command
line command and flag, the manual links, the tests it names and the
scenario fields without a form."""

import re
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

pytestmark = pytest.mark.requires_gui

_PAGE = Path(__file__).resolve().parents[2] / "docs" / "reference" / "feature-access.md"
_TEMPLATE_23 = "23_starter_complete_small_satellite.json"
_TEMPLATE_38 = "38_budgets_equipment_power_mass_propellant.json"

# Commands the palette test does not run, each with its reason; each is run by the test named.
_NOT_RUN_HERE = {
    "file.quit": "closes the window (tests/gui/test_main_window.py)",
    "file.new": "replaces the scenario open (tests/gui/test_menu_bar.py::test_menu_items_follow_their_commands_state)",
    "file.open": "replaces the scenario open (tests/gui/test_main_window.py)",
    "run.run": "starts Basilisk (tests/gui/test_home_palette_run.py)",
    "run.monte_carlo_case": "starts Basilisk (tests/gui/test_monte_carlo_results_widget.py)",
}
# Commands that may be off with no reason of their own (the palette then says "Not available now.").
_OFF_WITHOUT_REASON = ("edit.undo", "edit.redo")
# Commands that change a state the next command reads: run twice, so the state is back.
_TOGGLES = ("view.menu_bar", "view.status_details", "view.rail_icons", "view.inspector", "view.calculation",
            "view.problems", "view.breakout", "view.window.")


@pytest.fixture(scope="module")
def window(qapp, tmp_path_factory):
    """Template 23 open at 1280 x 720, in a home of its own."""
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR
    from spacemissionstudio.gui.main_window import MainWindow

    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication

    before = set(QApplication.topLevelWidgets())
    with pytest.MonkeyPatch.context() as patch:
        home = tmp_path_factory.mktemp("home")
        patch.setattr(Path, "home", lambda: home)
        patch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
        window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
        window.resize(1280, 720)  # [px]
        window.show()
        assert window.open_path(TEMPLATES_DIR / _TEMPLATE_23)
        qapp.processEvents()
        yield window
        window.scenario_editor.spacecraft_list.close_model_editors()
        window.close()
        # The windows the commands opened (About, Licences, Change History, ...) go with it, while the
        # application lives: left to the session's end, one was freed after its web profile (a crash).
        for widget in [window] + [w for w in set(QApplication.topLevelWidgets()) - before
                                  if w.parent() is None and w is not window]:
            widget.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.fixture
def quiet_dialogs(monkeypatch):
    """Every modal dialog answers at once: Cancel, no file, rejected."""
    from PySide6.QtWidgets import QDialog, QFileDialog, QInputDialog, QMenu, QMessageBox

    for name in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Cancel))
    monkeypatch.setattr(QMessageBox, "about", staticmethod(lambda *a, **k: None))
    for name, answer in (("getOpenFileName", ("", "")), ("getSaveFileName", ("", "")),
                         ("getOpenFileNames", ([], "")), ("getExistingDirectory", "")):
        monkeypatch.setattr(QFileDialog, name, staticmethod(lambda *a, answer=answer, **k: answer))
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    monkeypatch.setattr(QMenu, "exec", lambda *a, **k: None)
    for name, answer in (("getItem", ("", False)), ("getText", ("", False)), ("getInt", (0, False)),
                         ("getDouble", (0.0, False))):
        monkeypatch.setattr(QInputDialog, name, staticmethod(lambda *a, answer=answer, **k: answer))


def _open(window, qapp, name):
    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR

    assert window.open_path(TEMPLATES_DIR / name)
    qapp.processEvents()


# -- every command, from the palette ------------------------------------------------------------------------------

def test_every_command_is_in_the_palette_and_runs_from_it(window, qapp, quiet_dialogs):
    """Each command of the registry has its palette entry ("Category >
    Label"), the palette says why one is off, and running each enabled
    entry raises nothing (pytest-qt fails the test on an exception in a
    slot); one that is off says why, but Undo and Redo with nothing to
    undo. A command that changes a view's state runs twice, so the next
    starts where it did. The few not run here are listed with the test
    that runs them."""
    entries = {entry.label: entry for entry in window.palette_entries()}
    ran = []
    for command in window.commands:
        if command.id == "help.palette":
            continue  # the palette does not list itself
        entry = entries.get(f"{command.category} > {command.label}")
        assert entry is not None, command.id
        if not entry.enabled:
            assert entry.reason or command.id in _OFF_WITHOUT_REASON, command.id
            continue
        if command.id in _NOT_RUN_HERE:
            continue
        times = 2 if command.id.startswith(_TOGGLES) or command.action.isCheckable() else 1
        for _ in range(times):
            entry.run()
            qapp.processEvents()
        ran.append(command.id)
        assert window.scenario_open, command.id
    for command_id in ("budgets.pointing.add_requirement", "scenario.add_ground_station", "tools.model_3d",
                       "analyses.thermal", "go.budgets"):
        assert command_id in ran
    window.show_view(window.results_views)


def test_every_page_settings_section_and_export_of_the_palette_opens(window, qapp, quiet_dialogs):
    """The palette's other entries: each area, page, panel, Settings
    section and export (FA-5) opens its place without an error."""
    prefixes = ("Go to >", "Go to panel >", "Settings >", "Export >")
    shown = 0
    for entry in window.palette_entries():
        if entry.label.startswith(prefixes):
            entry.run()
            qapp.processEvents()
            shown += 1
    assert shown > 60
    exports = [entry for entry in window.palette_entries() if entry.label.startswith("Export >")]
    from spacemissionstudio.gui.exports_page import EXPORTS

    assert len(exports) == len(EXPORTS)
    next(entry for entry in exports if entry.label == "Export > Events").run()
    assert window.current_view() is window.event_timeline_widget


# -- the feature-access page names every command, with its keys ----------------------------------------------------

_COMMAND_ID = re.compile(r"`((?:file|edit|view|go|run|tools|analyses|budgets|scenario|cursor|help)\.[a-z_0-9.]+)`")
_KEYS = re.compile(r"`((?:Ctrl|Alt|Shift|F\d+|Esc)[^`]*)`")
# Commands whose keys are the platform's own (QKeySequence.StandardKey): they differ between systems.
_PLATFORM_KEYS = ("file.new", "file.open", "file.save", "file.save_as", "file.quit", "edit.undo", "edit.redo",
                  "help.manual")


def _page_ids():
    """{command id: [keys of each row of that one command, or None]} of the page's tables."""
    text = _PAGE.read_text(encoding="utf-8")
    found = {}
    for row in text.splitlines():
        if not row.startswith("| ") or row.startswith("|---"):
            continue
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        ids = _COMMAND_ID.findall(row)
        keys = _KEYS.findall(cells[1]) if len(cells) > 1 else []
        for command_id in ids:
            found.setdefault(command_id, []).append(keys if len(ids) == 1 else None)
    return found


def test_the_feature_access_page_names_every_command_with_its_keys(window):
    """Every command of the window is on the page (a new command needs its
    row), every command id the page names exists, and a row of one command
    gives the keys the command has (none when it has none; the platform's
    own keys, which differ between systems, may be left out)."""
    from PySide6.QtGui import QKeySequence

    named = _page_ids()
    commands = {command.id: command for command in window.commands}
    assert sorted(set(commands) - set(named)) == []
    assert sorted(set(named) - set(commands)) == []
    for command_id, rows in named.items():
        command = commands[command_id]
        bound = [keys.toString(QKeySequence.SequenceFormat.NativeText) for keys in command.action.shortcuts()]
        for keys in rows:
            if keys is None:
                continue
            assert all(key in bound for key in keys), command_id
            if command_id not in _PLATFORM_KEYS:
                assert keys == ([command.keys] if command.keys else []), command_id


# -- the paths this audit added ----------------------------------------------------------------------------------

def test_the_pointing_commands_show_the_page_and_act(window, qapp, quiet_dialogs):
    """Tools › Budgets › Add Pointing Requirement (Ctrl+Shift+E) and Add
    Pointing Contributor (Ctrl+Shift+T) show Budgets › Pointing and add a
    row; with no pointing budget they say so and change nothing, and Add
    Pointing Budget makes one (FA-2). The page's buttons show the keys."""
    _open(window, qapp, _TEMPLATE_38)
    page = window.budgets_views.pointing_page
    window.show_view(window.scenario_editor)
    window.commands.action("budgets.pointing.add_requirement").trigger()
    qapp.processEvents()
    assert window.current_view() is page
    requirements, contributors = len(page.pointing.requirements), len(page.pointing.contributors)
    window.commands.action("budgets.pointing.add_requirement").trigger()
    window.commands.action("budgets.pointing.add_contributor").trigger()
    qapp.processEvents()
    assert len(page.pointing.requirements) == requirements + 1
    assert len(page.pointing.contributors) == contributors + 1
    assert page.add_requirement_action.toolTip() == "Add Requirement (Ctrl+Shift+E)"
    assert page.add_contributor_action.toolTip() == "Add Contributor (Ctrl+Shift+T)"
    assert "budgets.pointing.add_requirement" in [i for _t, i in _menu_ids(window.menus["Budgets"])]

    _open(window, qapp, _TEMPLATE_23)  # no budgets section
    window.commands.action("budgets.pointing.add_requirement").trigger()
    qapp.processEvents()
    assert window.current_view() is page and page.pointing is None
    window.commands.action("budgets.pointing.add_budget").trigger()
    qapp.processEvents()
    assert page.pointing is not None
    window.commands.action("budgets.pointing.add_requirement").trigger()
    qapp.processEvents()
    assert len(page.pointing.requirements) == 1


def _menu_ids(menu):
    return [(action.text(), action.objectName()) for action in menu.actions()]


def test_the_scenario_commands_click_the_pages_buttons(window, qapp, quiet_dialogs, monkeypatch):
    """Tools › Scenario › Add Spacecraft and Add Ground Station add one
    and show its list (FA-3); the generators open their dialog."""
    _open(window, qapp, _TEMPLATE_23)
    editor = window.scenario_editor
    spacecraft = len(editor.spacecraft_list.to_list())
    stations = len(editor.ground_station_list.to_list())
    window.commands.action("scenario.add_spacecraft").trigger()
    window.commands.action("scenario.add_ground_station").trigger()
    qapp.processEvents()
    assert len(editor.spacecraft_list.to_list()) == spacecraft + 1
    assert len(editor.ground_station_list.to_list()) == stations + 1
    opened = []
    from PySide6.QtWidgets import QDialog

    monkeypatch.setattr(QDialog, "exec", lambda self: opened.append(type(self).__name__) or QDialog.DialogCode.Rejected)
    for command_id in ("scenario.generate_constellation", "scenario.generate_phasing_formation",
                       "scenario.generate_roe_formation", "scenario.spacecraft_from_template"):
        window.commands.action(command_id).trigger()
        qapp.processEvents()
    assert opened == ["WalkerConstellationDialog", "PhasingFormationDialog", "RoeFormationDialog",
                      "SpacecraftTemplateDialog"]


def test_the_run_exports_are_in_the_file_menu_while_a_run_is_shown(window, qapp, monkeypatch):
    """File › Export Reproduction Bundle... and Export Ephemeris as CCSDS
    OEM... are off, with the reason, until a run is shown; then they do
    Results › Plots › Export all...'s own actions (FA-4)."""
    from spacemissionstudio.engine.results import ResultSet, TimeSeries
    from spacemissionstudio.gui.run_history import RunRecord

    _open(window, qapp, _TEMPLATE_23)
    file_ids = [i for _t, i in _menu_ids(window.menus["File"])]
    assert file_ids.index("file.export_oem") == file_ids.index("tools.ccsds_export") + 1
    bundle = window.commands["file.export_bundle"]
    widget = window.results_widget
    widget.set_runs([], None)
    assert not bundle.action.isEnabled() and "No run is shown" in bundle.unavailable
    t = np.linspace(0.0, 600.0, 5)  # [s]
    result = ResultSet(scenario_name="demo")
    result.add(TimeSeries("sat-1.position_N", t, ("x", "y", "z"), np.ones((5, 3)) * 7.0e6, units="m"))
    record = RunRecord(1, window.scenario_editor.to_scenario().to_dict(), result, "2030-01-01T00:00:00",
                       datetime.now(UTC))
    widget.set_result(result, "2030-01-01T00:00:00")
    widget.set_runs([record], record)
    assert bundle.action.isEnabled() and window.commands.action("file.export_oem").isEnabled()
    asked = []
    monkeypatch.setattr("PySide6.QtWidgets.QFileDialog.getExistingDirectory",
                        lambda *a, **k: asked.append(a[1]) or "")
    bundle.action.trigger()
    assert asked == ["Export a reproduction bundle (choose an empty folder)"]
    widget.set_result(None)
    widget.set_runs([], None)
    assert not bundle.action.isEnabled()


def test_the_run_views_empty_states_lead_to_their_action(window, qapp, monkeypatch):
    """Before a run, Plots, 3D View, Map, Timeline, Compare and Dashboard
    offer Run (on and off with Run); Output offers Go to Mission
    Sequence, and Dashboard also Open Template 19 (FA-6)."""
    from PySide6.QtWidgets import QPushButton

    _open(window, qapp, _TEMPLATE_23)
    buttons = window._empty_run_buttons()
    assert all(button.text() == "Run" for button in buttons)
    for view in (window.results_widget.plot_empty, window.mission_view_widget.empty,
                 window.mission_view_widget.ground_map.empty, window.event_timeline_widget.empty_state,
                 window.compare_widget.empty_label):
        assert view.button.text() == "Run" and not view.button.isHidden()
    run = window.commands.action("run.run")
    assert all(button.isEnabled() == run.isEnabled() for button in buttons)
    started = []
    monkeypatch.setattr(window, "on_run", lambda *a: started.append(True))
    window.event_timeline_widget.run_requested.disconnect()
    window.event_timeline_widget.run_requested.connect(window.on_run)
    window.event_timeline_widget.empty_run_button.click()
    assert started == [True]

    output = window.mission_output_widget.empty_state
    assert output.button.text() == "Go to Mission Sequence"
    output.button.click()
    qapp.processEvents()
    assert window.scenario_editor.page_tree.current_page() is window.scenario_editor.mission_sequence_page

    opened = []
    monkeypatch.setattr(window, "_on_load_scenario_path_chosen", lambda path: opened.append(path.name))
    window.mission_dashboard_widget.template_requested.disconnect()
    window.mission_dashboard_widget.template_requested.connect(window._open_template_named)
    dashboard = next(b for b in window.mission_dashboard_widget.findChildren(QPushButton)
                     if b.text() == "Open Template 19")
    dashboard.click()
    assert opened == ["19_sun_pointing_comms_link.json"]


def test_a_long_palette_entry_neither_scrolls_sideways_nor_hides_the_keys(qtbot):
    """A template's entry with its category is longer than the palette is
    wide: its name is elided, the list does not scroll sideways, and the
    keys of a command stay whole at the right (they were cut, FA-10)."""
    from spacemissionstudio.gui.command_palette import SHORTCUT_ROLE, CommandPalette, PaletteEntry

    long_name = "Open template > 19 sun pointing comms link (Power, communications and data and more words)"
    palette = CommandPalette([PaletteEntry(long_name, lambda: None),
                              PaletteEntry("Budgets > Add Pointing Requirement", lambda: None, "Ctrl+Shift+E")])
    qtbot.addWidget(palette)
    palette.show()
    qtbot.waitExposed(palette)
    view = palette.list
    assert view.horizontalScrollBar().maximum() == 0
    keyed = next(view.item(row) for row in range(view.count()) if view.item(row).data(SHORTCUT_ROLE))
    rect = view.visualItemRect(keyed)
    assert rect.right() <= view.viewport().width()
