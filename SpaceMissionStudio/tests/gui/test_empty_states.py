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
"""Empty states everywhere (UI audit batch B3).

The audit found blank boxes with Edit and Remove enabled (UI-05), an
empty plot box on End of Life (UI-10), five different empty-state styles
(UI-15), a 220 px "Pick a node" over a two-row table (UI-21), a Plan page
that told the user to edit JSON (UI-22), a Problems panel that called a
scenario valid when none was open (UI-24), "No events in this run." twice
on the Timeline (UI-25) and "No design finding." before any check
(UI-45). Every empty view, list and panel now shows the one
``widgets.EmptyState``; these tests check each defect.
"""

from pathlib import Path

import pytest

pytestmark = pytest.mark.requires_gui

_TEMPLATES = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"


def _template(name):
    from spacemissionstudio.schema import load_scenario

    return load_scenario(next(_TEMPLATES.glob(f"{name}_*.json")))


def _shown(widget, root) -> bool:
    return widget.isVisibleTo(root)


# -- UI-15: one empty state ---------------------------------------------------------------------------------------

@pytest.fixture
def window(qtbot, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui import autosave
    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(autosave, "_AUTOSAVE_DIR", tmp_path / "autosave")
    monkeypatch.setattr(autosave, "_RECOVERY_FILE", tmp_path / "autosave" / "recovery.json")
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    return window


def test_every_empty_view_uses_the_one_empty_state(window):
    """No label of the old styles is left (the "empty" role, the
    "emptyState" label, the views' own centred lines), and the views the
    audit named, with the others, show a ``widgets.EmptyState``."""
    from PySide6.QtWidgets import QLabel, QWidget

    from spacemissionstudio.gui import compare_widget, workspace_panels
    from spacemissionstudio.gui.theme import qss
    from spacemissionstudio.gui.widgets import EmptyState

    window.open_path(_TEMPLATES / "01_two_body_circular_orbit.json")
    old = [w for w in window.findChildren(QLabel) if w.property("role") == "empty" or w.objectName() == "emptyState"]
    assert old == []
    assert not hasattr(workspace_panels, "_empty_state") and not hasattr(compare_widget, "_empty_state")
    from spacemissionstudio.gui.theme import TOKENS

    assert 'role="empty"' not in qss.stylesheet(TOKENS) and "#emptyState" not in qss.stylesheet(TOKENS)
    states = {
        "plots": window.results_widget.plot_empty,
        "dashboard": window.mission_dashboard_widget._placeholder,
        "output": window.mission_output_widget.empty_state,
        "history": window.history_view.empty,
        "plan": window.plan_widget.empty_state,
        "overview": window.results_overview.empty,
        "3d view": window.mission_view_widget.empty,
        "compare": window.compare_widget.empty_label,
        "timeline": window.event_timeline_widget.empty_state,
        "problems": window.problems_widget.empty_label,
        "inspector": window.inspector_widget.empty_label,
        "end of life": window.lifetime_widget.empty_state,
        "design checks": window.design_checks_widget.empty_state,
        "no scenario": window.no_scenario_states["run"],
    }
    for name, state in states.items():
        assert isinstance(state, EmptyState), name
    # Before a run each of the five views of UI-15 shows its empty state, and nothing else says it.
    for name in ("plots", "dashboard", "output", "history", "plan"):
        assert not states[name].isHidden(), name
    sentences = [w for w in window.findChildren(QWidget)
                 if isinstance(w, QLabel) and w.text().startswith(("Run a simulation to see results here",
                                                                   "No live telemetry yet.", "No runs yet. "))]
    assert sentences == []


def test_the_empty_state_has_a_compact_form_and_further_actions(qtbot):
    """The full form centres its title, text and buttons; the compact one
    is as tall as its lines; ``text()`` gives the lines shown."""
    from PySide6.QtWidgets import QLabel

    from spacemissionstudio.gui.widgets import EmptyState

    full = EmptyState("No runs yet", "Each run is listed here.", "Run")
    compact = EmptyState("No node picked", "Pick one above.", compact=True)
    for state in (full, compact):
        qtbot.addWidget(state)
    second = full.add_action("Open...")
    full.add_detail(QLabel("a reason"))
    assert full.text() == "No runs yet\nEach run is listed here." and second.text() == "Open..."
    assert compact.sizeHint().height() < full.sizeHint().height()
    full.set_text("No plot shown")
    assert full.text() == "No plot shown" and full.button.isHidden()


# -- UI-05: lists ---------------------------------------------------------------------------------------------------

def test_the_ground_station_list_has_an_empty_state_and_selection_actions(qtbot):
    """No station: the empty state with Add, Edit and Remove off. A short
    list is as tall as its rows; Edit and Remove need a selection."""
    from spacemissionstudio.gui.ground_station_editor import GroundStationListWidget
    from spacemissionstudio.schema.scenario import GroundStationConfig

    widget = GroundStationListWidget()
    qtbot.addWidget(widget)
    widget.resize(800, 600)
    widget.show()
    assert widget.list_stack.showing_empty() and widget.empty_state.button.text() == "Add ground station"
    assert not widget.edit_button.isEnabled() and not widget.remove_button.isEnabled()
    # One Add on the page: the list's own buttons are hidden while the empty state shows.
    assert all(button.isHidden() for button in (widget.add_button, widget.edit_button, widget.remove_button))
    widget.from_list([GroundStationConfig(name="gs-1", latitude_deg=48.0, longitude_deg=11.0),
                      GroundStationConfig(name="gs-2", latitude_deg=-30.0, longitude_deg=150.0)])
    assert not widget.list_stack.showing_empty()
    assert not any(button.isHidden() for button in (widget.add_button, widget.edit_button, widget.remove_button))
    assert not widget.edit_button.isEnabled() and not widget.remove_button.isEnabled()
    assert widget.list_stack.height() < 200  # two rows, not the page's height
    widget.list_widget.setCurrentRow(0)
    assert widget.edit_button.isEnabled() and widget.remove_button.isEnabled()


def test_the_mission_sequence_has_an_empty_state_with_add_step(qtbot):
    """No step: the empty state, whose Add step opens the kinds' menu, and
    no form pane beside it; one step brings the tree back."""
    from spacemissionstudio.gui.mission_sequence_editor import MissionSequenceEditorWidget

    widget = MissionSequenceEditorWidget()
    qtbot.addWidget(widget)
    assert widget.steps_stack.showing_empty() and widget.form_stack.isHidden()
    assert widget.empty_state.button.menu() is widget.add_button.menu()
    assert not widget.remove_button.isEnabled() and not widget.duplicate_button.isEnabled()
    row = (widget.add_button, widget.add_child_button, widget.duplicate_button, widget.remove_button,
           widget.move_up_button, widget.move_down_button)
    assert all(button.isHidden() for button in row)  # the empty state's Add step is the only one
    widget.add_step("propagate")
    assert not widget.steps_stack.showing_empty() and not widget.form_stack.isHidden()
    assert not any(button.isHidden() for button in row)


def test_the_spacecraft_list_has_an_empty_state_with_add(qtbot, monkeypatch):
    """No spacecraft: the empty state, whose button is Add."""
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftListWidget
    from spacemissionstudio.gui.widgets import EmptyState

    widget = SpacecraftListWidget()
    qtbot.addWidget(widget)
    assert isinstance(widget.empty_state, EmptyState) and widget.list_stack.showing_empty()
    added = []
    monkeypatch.setattr(widget, "_on_add", lambda: added.append(True))
    widget.empty_state.button.click()
    assert added == [True] and not widget.edit_button.isEnabled()
    assert all(button.isHidden() for button in (widget.add_button, widget.edit_button, widget.remove_button))
    assert not widget.new_from_template_button.isHidden()  # not what the empty state's Add stands in for
    widget.from_list(_template("01").spacecraft)
    assert not widget.list_stack.showing_empty() and widget.list_stack.height() < 200
    assert not any(button.isHidden() for button in (widget.add_button, widget.edit_button, widget.remove_button))


def test_the_idm_devices_table_has_an_empty_state_with_browse(qtbot):
    """Before a file: the empty state, whose Browse... chooses one; not an
    empty table."""
    from spacemissionstudio.gui.idm_import_dialog import IdmImportDialog

    dialog = IdmImportDialog()
    qtbot.addWidget(dialog)
    assert dialog.devices_stack.showing_empty() and dialog.devices_empty.button.text() == "Browse..."


def test_the_plot_list_has_an_empty_state(qtbot):
    """No run: the empty state; a search that leaves nothing says so,
    with Clear search."""
    from spacemissionstudio.gui.plot_catalog import PlotCatalog

    catalog = PlotCatalog()
    qtbot.addWidget(catalog)
    assert catalog.stack.showing_empty() and catalog.empty_state.title_label.text() == "No plots yet"
    catalog.set_entries([("sat.position", "Position", "Orbit")], [])
    assert not catalog.stack.showing_empty()
    catalog.search.setText("no such plot")
    assert catalog.stack.showing_empty() and catalog.empty_state.button.text() == "Clear search"
    catalog.empty_state.button.click()
    assert not catalog.stack.showing_empty()


# -- UI-10: End of Life -----------------------------------------------------------------------------------------------

def test_end_of_life_shows_an_empty_state_then_the_results_above_the_inputs(qtbot):
    """Before an estimate: the empty state, no empty plot box. The results
    come before the inputs, and the inputs fold."""
    from spacemissionstudio.gui.lifetime_widget import LifetimeWidget
    from spacemissionstudio.gui.value_sheet import FoldSection

    widget = LifetimeWidget()
    qtbot.addWidget(widget)
    assert _shown(widget.empty_state, widget) and not _shown(widget.chart, widget)
    assert isinstance(widget.inputs, FoldSection) and widget.inputs.is_open()
    layout = widget.layout()
    assert layout.indexOf(widget.results) < layout.indexOf(widget.inputs)
    assert layout.indexOf(widget.empty_state) < layout.indexOf(widget.inputs)
    widget.inputs.set_open(False)
    assert not _shown(widget.spacecraft_combo, widget)


@pytest.mark.requires_basilisk
def test_an_estimate_replaces_the_empty_state_with_the_plot(qtbot):
    from spacemissionstudio.gui.lifetime_widget import LifetimeWidget

    widget = LifetimeWidget()
    qtbot.addWidget(widget)
    scenario = _template("18")
    scenario.spacecraft[0].orbit.semi_major_axis_km = 6378.1366 + 350.0  # [km] a short decay
    widget.set_scenario(scenario)
    widget.compute()
    qtbot.waitUntil(lambda: widget.tiles_row.count() > 0, timeout=60000)
    widget.wait_for_worker()
    assert _shown(widget.chart, widget) and not _shown(widget.empty_state, widget)


# -- UI-21: Thermal › Heat flows ------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def solved():
    """Template 33 run for 0.07 days and solved without heater sizing."""
    pytest.importorskip("Basilisk")
    from spacemissionstudio import api

    path = api.template("33_microsat_thermal")
    scenario = api.load(path)
    scenario.sim_settings.duration_days = 0.07
    result = api.run(scenario)
    return scenario, result, path.parent, api.thermal(scenario, result, base_dir=path.parent, size_heaters=False)


@pytest.mark.requires_basilisk
def test_the_heat_flows_prompt_is_one_compact_line_and_the_table_gets_the_room(qtbot, solved):
    """No node picked: a compact empty state over the table, which takes
    the rest of the tab (it had two rows at 1280 x 720)."""
    from spacemissionstudio.gui.thermal_widget import TABS, ThermalWidget

    scenario, result, base_dir, analysis = solved
    widget = ThermalWidget()
    qtbot.addWidget(widget)
    widget.set_run(scenario, result, base_dir)
    widget.resize(1280, 560)  # the page's room in a 1280 x 720 window
    widget.show()
    qtbot.waitExposed(widget)
    widget.show_analysis(analysis)
    widget.tabs.setCurrentIndex(list(TABS).index("Heat flows"))
    qtbot.wait(50)
    section, table = widget.tables["flows"]
    assert widget.flow_empty.compact and widget.flow_empty.isVisible() and not widget.flow_plot.isVisible()
    assert widget.flow_empty.height() <= 96
    assert section.height() >= 3 * widget.flow_empty.height()


# -- UI-22: Run › Plan ----------------------------------------------------------------------------------------------

def test_the_plan_page_says_what_a_plan_is_and_offers_the_template(qtbot):
    """No plan: the empty state says what a plan is, never to edit JSON;
    without an operations section it opens template 35, with one it plans."""
    from spacemissionstudio.gui.plan_widget import PLAN_TEMPLATE, PlanWidget

    page = PlanWidget()
    qtbot.addWidget(page)
    assert not page.empty_state.isHidden() and "JSON" not in page.empty_state.text()
    assert "JSON" not in page.status_label.text()
    assert "schedules the activities" in page.empty_state.text()
    page.set_scenario(_template("01"))  # no operations section
    assert page.empty_state.button.text() == "Open Template 35"
    with qtbot.waitSignal(page.template_requested) as blocker:
        page.empty_state.button.click()
    assert blocker.args == [PLAN_TEMPLATE] and (_TEMPLATES / PLAN_TEMPLATE).is_file()
    page.set_scenario(_template("35"))
    assert page.empty_state.button.text() == "Plan"


def test_the_window_opens_the_plan_template(window, monkeypatch):
    opened = []
    monkeypatch.setattr(window, "open_path", opened.append)
    window.plan_widget.template_requested.emit("35_eo_operations_week.json")
    assert opened == [_TEMPLATES / "35_eo_operations_week.json"]


# -- UI-24: Problems with no scenario -------------------------------------------------------------------------------

def test_the_problems_panel_does_not_call_a_missing_scenario_valid(window):
    """No scenario open: "No scenario is open", not "the scenario is
    valid"; once one is open and valid it says so."""
    state = window.problems_widget.empty_label
    assert "valid" not in state.text() and "No scenario is open" in state.text()
    window.open_path(_TEMPLATES / "01_two_body_circular_orbit.json")
    window.problems_widget.set_problems([])
    assert "No scenario is open" not in state.text()


# -- UI-25: Timeline ------------------------------------------------------------------------------------------------

def test_the_timeline_says_no_events_once_with_its_reasons_as_a_list(qtbot):
    """No run: one empty state. A run without events: "No events in this
    run" once, the reasons as rows of a list, no timeline and no table."""
    from PySide6.QtWidgets import QLabel

    from spacemissionstudio.engine.results import ResultSet
    from spacemissionstudio.gui.event_timeline_widget import EventTimelineWidget

    widget = EventTimelineWidget()
    qtbot.addWidget(widget)
    widget.resize(1100, 600)
    widget.show()
    assert widget.empty_state.isVisible() and not widget.splitter.isVisible()
    assert not widget.summary_label.isVisible() and not widget.cursor_label.isVisible()
    widget.set_result(ResultSet("empty"))
    qtbot.wait(20)
    said = [w for w in widget.findChildren(QLabel) if w.isVisible() and "No events" in w.text()]
    assert len(said) == 1 and widget.empty_state.title_label.text() == "No events in this run"
    assert len(widget.reasons.notes) >= 2 and all(note.startswith("No ") for note in widget.reasons.notes)
    assert not widget.gantt.isVisible() and not widget.table.isVisible()


# -- UI-45: Design Checks -------------------------------------------------------------------------------------------

def test_design_checks_offer_check_before_the_first_one(qtbot):
    """Before Check: an empty state that offers Check, not "No design
    finding."; after a check without findings: that, once."""
    from spacemissionstudio.gui.design_checks_widget import DesignChecksWidget

    page = DesignChecksWidget()
    qtbot.addWidget(page)
    assert not page.empty_state.isHidden() and page.findings_label.isHidden()
    assert page.empty_state.button.text() == "Check" and not page.empty_state.button.isEnabled()
    scenario = _template("28")
    scenario.spacecraft[0].model = None
    page.set_scenario(scenario, _TEMPLATES)
    assert page.empty_state.button.isEnabled()
    page.empty_state.button.click()
    qtbot.waitUntil(lambda: page.report is not None and page._worker is None, timeout=30000)
    assert page.empty_state.isHidden() and not page.findings_label.isHidden()
    assert page.findings_label.text() == "No design finding."
