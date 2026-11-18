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
"""Value sheets instead of sentences (UI audit batch B5).

The audit found a footer under the scenario editor that said "✓ valid"
next to warnings and a clipped absolute path in the status bar (UI-09);
sentences of numbers for the control gains, the Overview's orbit, the
inputs from the last run (with microsecond timestamps) and the IDM-CIC
import preview (UI-14); one card on Results › Overview for template 01,
cards of different heights and "W*h" (UI-20); one warning in four or five
places (UI-37); repository paths in the window's text (UI-43, in
``tests/test_value_rows.py``); and a developer note and a dark strip in
the 3D View (UI-51). These tests check each defect.
"""

import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

pytestmark = pytest.mark.requires_gui

_TESTS = Path(__file__).resolve().parents[1]
_TEMPLATES = _TESTS.parent / "spacemissionstudio" / "scenarios" / "templates"
_T01 = _TEMPLATES / "01_two_body_circular_orbit.json"
_RADIUS_M = 6778.1366e3  # [m] 400 km above Earth's equatorial radius


@pytest.fixture
def window(qtbot, monkeypatch, tmp_path, restored_theme):
    """A main window at 1280 x 720 in the light theme."""
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


def _circle(name: str = "sat-1", samples: int = 300, provenance=None, warnings=()):
    """A result: a 400 km circular orbit over two periods."""
    from spacemissionstudio.constants import EARTH_GM_M3_S2
    from spacemissionstudio.engine.results import ResultSet, TimeSeries

    period_s = 2.0 * math.pi * math.sqrt(_RADIUS_M ** 3 / EARTH_GM_M3_S2)  # [s]
    t = np.linspace(0.0, 2.0 * period_s, samples)
    angle = 2.0 * math.pi * t / period_s
    result = ResultSet(scenario_name="circle", provenance=provenance, warnings=list(warnings))
    result.add(TimeSeries(f"{name}.position_N", t, ("x", "y", "z"),
                          np.column_stack([_RADIUS_M * np.cos(angle), _RADIUS_M * np.sin(angle), 0 * t]), units="m"))
    result.add(TimeSeries(f"{name}.velocity_N", t, ("x", "y", "z"), np.zeros((t.size, 3)), units="m/s"))
    result.add(TimeSeries(f"{name}.orbit_elements.semi_major_axis", t, ("semi_major_axis",),
                          np.full(t.size, _RADIUS_M), units="m"))
    return result


# -- UI-09: the footer and the status bar ---------------------------------------------------------

def test_the_editor_has_no_footer_and_problems_lists_its_warnings(window, qtbot):
    """No "✓ valid" and no warning lines under the editor: the Problems panel
    and the top bar's count already show them, and each warning the footer
    listed is in Problems."""
    from spacemissionstudio.schema import load_scenario

    editor = window.scenario_editor
    assert editor.layout().count() == 1  # the tree or the JSON page, nothing under it
    assert not hasattr(editor, "validation_label") and not hasattr(editor, "plausibility_label")
    window.open_path(_T01)
    scenario = load_scenario(_T01)
    scenario.spacecraft[0].orbit.semi_major_axis_km = 6300.0  # [km] below Earth's surface
    editor.from_scenario(scenario)
    editor.revalidate()
    rows = window.problems_widget.shown_rows()
    assert any(severity == "Warning" and "below Earth's surface" in message for severity, _id, _obj, message in rows)
    assert window.top_bar.problems_button.isVisibleTo(window)


def test_the_status_bar_names_the_file_and_keeps_its_path_in_the_tooltip(window, qtbot, tmp_path):
    """"Opened /tmp/.../01_two_body_circular_orbit.json" was clipped at the
    first permanent entry. The bar names the file; the tooltip has its path;
    a name too long for the bar ends in an ellipsis."""
    window.show()
    window.open_path(_T01)
    bar = window.statusBar()
    assert bar.currentMessage() == f"Opened {_T01.name}"
    assert Path(bar.toolTip()).resolve() == _T01.resolve()
    target = tmp_path / "mine.json"
    window._save_to(target)
    assert bar.currentMessage() == "Saved mine.json" and Path(bar.toolTip()) == target
    long_name = tmp_path / ("a-very-long-scenario-name-" * 7 + ".json")  # 187 characters, wider than the bar
    window._save_to(long_name)
    assert "…" in bar.currentMessage() and str(tmp_path) not in bar.currentMessage()
    assert Path(bar.toolTip()) == long_name
    bar.showMessage("Ready.")
    assert bar.toolTip() == ""  # the path went with its message


# -- UI-14: sentences of numbers ------------------------------------------------------------------

def test_the_control_gains_are_a_value_sheet(qtbot):
    """"Unticked: K 0.03889, P 0.3333, integral off. That is K 3.5, P 30
    (tuned for 900 kg*m^2) times mean inertia 10 kg*m^2 / 900." is one row
    per value, with its unit, and follows an inertia edit."""
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog
    from spacemissionstudio.gui.value_sheet import ValueSheet

    dialog = SpacecraftEditorDialog()
    qtbot.addWidget(dialog)
    sheet = dialog.control_legend
    assert isinstance(sheet, ValueSheet)
    assert sheet.value("Attitude gain K") == "0.03889" and sheet.value("Rate gain P") == "0.3333"
    units = {name: unit for name, _value, unit in sheet.rows}
    assert units["Attitude gain K"] == "N·m" and units["Rate gain P"] == "N·m·s" and units["Mean inertia"] == "kg·m²"
    for box in (dialog.ixx, dialog.iyy, dialog.izz):
        box.setValue(40.0)  # [kg*m^2]
    assert sheet.value("Mean inertia") == "40" and sheet.value("Attitude gain K") == "0.1556"


def test_the_overview_shows_the_orbit_as_values(qtbot):
    """Template 01's tile "Classical 97.03 deg, 400 km alt" is three tiles:
    the kind of orbit, the inclination and the altitude, each with its unit;
    no tile holds a list."""
    from spacemissionstudio.gui.scenario_explainer_widget import ScenarioExplainerWidget
    from spacemissionstudio.schema import load_scenario

    widget = ScenarioExplainerWidget()
    qtbot.addWidget(widget)
    widget.resize(900, 600)
    widget.show()
    widget.set_scenario(load_scenario(_T01))
    assert ("Orbit", "Classical", "") in widget.tiles
    assert ("Inclination", "97.03", "°") in widget.tiles and ("Altitude", "400", "km") in widget.tiles
    assert all(", " not in value for _label, value, _unit in widget.tiles)
    qtbot.wait(50)
    heights = {frame.height() for frame in widget.tile_frames}
    assert len(heights) == 1, heights


def test_the_last_run_inputs_are_a_value_sheet_with_an_iso_time(qtbot):
    """"From the last run, started 2026-11-17T18:49:48.737253+00:00 (a
    contributor set to 'from last run' takes these):" is a titled sheet:
    the start time in ISO 8601 UTC with Z to the second, then a row per
    value with its unit."""
    from spacemissionstudio.engine.results import ResultSet, RunProvenance, TimeSeries
    from spacemissionstudio.gui.budget_widget import BudgetWidget
    from spacemissionstudio.gui.value_sheet import ValueSheet
    from spacemissionstudio.schema import load_scenario

    scenario = load_scenario(_TEMPLATES / "22_starter_first_leo_satellite.json")
    name = scenario.spacecraft[0].name
    t = np.array([0.0, 86400.0])  # [s]
    provenance = RunProvenance("3.0.0", "2.12.0", "2026-11-17T18:49:48.737253+00:00", "rkf78", 30.0)
    result = ResultSet(scenario_name="budget", provenance=provenance)
    result.add(TimeSeries(f"{name}.position_N", t, ("x", "y", "z"), np.zeros((2, 3))))
    result.add(TimeSeries(f"{name}.station_keeping.delta_v", t, ("delta_v",), np.array([[0.0], [0.02]])))
    widget = BudgetWidget()
    qtbot.addWidget(widget)
    widget.set_scenario(scenario)
    widget.set_last_run(scenario, result)
    panel = widget.chain_panel
    assert isinstance(panel.sheet, ValueSheet) and panel.sheet.title_label.text() == "From the last run"
    assert panel.sheet.value("Run started") == "2026-11-17T18:49:48Z"
    assert panel.sheet.value("Run length") == "1" and dict((n, u) for n, _v, u in panel.sheet.rows)["Run length"]
    assert ".737253" not in panel.sheet.text() and "+00:00" not in panel.sheet.text()


def test_the_import_preview_is_a_value_sheet_and_a_note_list(qtbot, tmp_path):
    """The IDM-CIC preview was a text dump; it is a sheet of the import's
    facts (the mass in kg) and its findings, one row each behind an icon."""
    sys.path.insert(0, str(_TESTS))
    from idm_fixtures import write_idm

    from spacemissionstudio.gui.idm_import_dialog import IdmImportDialog
    from spacemissionstudio.gui.value_sheet import NoteList, ValueSheet

    dialog = IdmImportDialog(write_idm(tmp_path / "demosat.idm"))
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: not dialog.busy() and dialog.plan() is not None, timeout=30000)
    assert isinstance(dialog.preview_sheet, ValueSheet) and isinstance(dialog.preview_notes, NoteList)
    assert dialog.preview_sheet.value("Mass imported") == "38.7"
    assert dict((n, u) for n, _v, u in dialog.preview_sheet.rows)["Mass imported"] == "kg"
    assert dialog.preview_sheet.value("Body element") == "Bus"
    assert any(note.startswith("Left out: element Ground jig") for note in dialog.preview_notes.notes)
    assert not hasattr(dialog, "preview")  # no text dump


# -- UI-20: Results › Overview --------------------------------------------------------------------

def test_the_overview_has_the_orbit_cards_one_height_and_wh(qtbot):
    """Template 01's run gave one card. The orbit's period and altitude come
    from the recorded orbit; every card has one height, a status line or
    not; the battery's unit reads "Wh"."""
    from spacemissionstudio.engine.results import TimeSeries
    from spacemissionstudio.gui.results_overview import ResultsOverview

    result = _circle()
    t = result.series["sat-1.position_N"].time_s
    result.add(TimeSeries("sat-1.battery_charge", t, ("charge",), np.linspace(20.0, 0.0, t.size), units="W*h"))
    overview = ResultsOverview()
    qtbot.addWidget(overview)
    overview.resize(1000, 600)
    overview.show()
    overview.set_run(result, "Run 1")
    qtbot.waitUntil(lambda: not overview.pending, timeout=20000)
    labels = [card.figure.label for card in overview.cards]
    assert labels[:3] == ["Run length", "Orbital period", "Altitude"]
    battery = next(card for card in overview.cards if card.figure.label == "Lowest battery charge")
    assert battery.unit.text() == "Wh" and battery.status == "Battery empty"
    qtbot.wait(50)
    assert len({card.height() for card in overview.cards}) == 1


# -- UI-37: one place for a warning ---------------------------------------------------------------

def test_a_run_warning_lives_in_problems_not_on_the_plots_page(window, qtbot):
    """The shown run's warnings are rows of the Problems panel, with their
    rule on hover; the plots page keeps the provenance line and no warning
    text; the top bar counts them."""
    from PySide6.QtCore import Qt

    from spacemissionstudio.engine.findings import Finding
    from spacemissionstudio.engine.results import RunProvenance
    from spacemissionstudio.gui.value_sheet import NoteList
    from spacemissionstudio.gui.workspace_panels import PROBLEM_COLUMNS

    window.open_path(_T01)
    before = len(window.problems_widget.shown_rows())
    warning = Finding("sat-1 re-entered: below 100 km at t = 3.20 days -- the run stopped there",
                      "run.reentry_stopped", limit="100 km")
    provenance = RunProvenance("3.0.0", "2.12.0", "2026-11-17T18:49:48+00:00", "rkf78", 30.0)
    window.results_widget.set_result(_circle(provenance=provenance, warnings=[warning]), "2030-01-01T00:00:00")
    rows = window.problems_widget.shown_rows()
    assert len(rows) == before + 1
    row = next(i for i, shown in enumerate(rows) if shown[3] == str(warning))
    assert rows[row][0] == "Warning"
    model = window.problems_widget.table.model()
    tip = model.index(row, PROBLEM_COLUMNS.index("Message")).data(Qt.ItemDataRole.ToolTipRole)
    assert tip.startswith("rule run.reentry_stopped: ")
    results = window.results_widget
    assert results.provenance_label.text() and "re-entered" not in results.provenance_label.text()
    assert not any("re-entered" in notes.text() for notes in results.findChildren(NoteList))
    window.results_widget.set_result(None)
    assert len(window.problems_widget.shown_rows()) == before


# -- UI-51: the 3D View ---------------------------------------------------------------------------

def _js(qtbot, view, script):
    out = []
    view.web_view.page().runJavaScript(script, 0, out.append)
    qtbot.waitUntil(lambda: bool(out), timeout=20000)
    return out[0]


def test_the_3d_view_fills_its_width_and_its_note_is_one_line_where_it_helps(qtbot):
    """The canvas was 16 px narrower than its page (a dark strip on the
    right); the scale note was two lines under the controls in every view.
    It is one line, worded for the user, with the scene's notes in its
    tooltip, and gone from a view from the spacecraft (true size, as its
    name says)."""
    from spacemissionstudio import api
    from spacemissionstudio.gui.mission_view_widget import MissionViewWidget
    from spacemissionstudio.gui.time_cursor import TimeCursor

    scenario = api.load(api.template("01_two_body_circular_orbit"))
    view = MissionViewWidget()
    qtbot.addWidget(view)
    view.set_time_cursor(TimeCursor())
    view.resize(900, 600)
    view.show()
    view.set_run(scenario, _circle(scenario.spacecraft[0].name))
    qtbot.waitUntil(lambda: view.scene is not None, timeout=30000)
    qtbot.waitUntil(lambda: view._page_ready, timeout=60000)
    qtbot.waitUntil(lambda: _js(qtbot, view, "MV.ready === true && MV.style !== null") is True, timeout=60000)
    qtbot.wait(500)
    widths = json.loads(_js(qtbot, view, "JSON.stringify([document.getElementById('view').clientWidth, "
                                         "MV.renderer.domElement.clientWidth, window.innerWidth])"))
    assert widths[0] == widths[1] == widths[2], widths
    note = view.scale_note
    assert note.isVisibleTo(view) and not note.wordWrap()
    assert note.text().startswith("Not to scale: ") and "larger than they are" in note.text()
    assert "no attitude in this run" in note.toolTip()
    assert note.height() <= 2 * note.fontMetrics().height()
    index = view.view_combo.findText(f"From {scenario.spacecraft[0].name} along +x_B")
    view.view_combo.setCurrentIndex(index)
    assert not note.isVisibleTo(view)
