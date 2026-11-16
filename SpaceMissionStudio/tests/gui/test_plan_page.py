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
"""Run › Plan (SRS-F-30): the Gantt chart (rows, bars, a drag held within
the window), the page (Plan on a background thread, the tables, the status
at the time cursor, lock, unlock, delete, move, lose a pass, robustness,
export, save and open, compare), the plan's activities on the Timeline,
its warnings in Problems, and the scenario editor keeping the operations
section."""

import sys
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: operations_fixtures

import operations_fixtures as fixtures  # noqa: E402

from spacemissionstudio.engine.events import PLANNED, THERMAL_LIMIT, Event  # noqa: E402
from spacemissionstudio.gui import export_log  # noqa: E402
from spacemissionstudio.gui.event_timeline_widget import PLAN_BOX, THERMAL_BOX, EventTimelineWidget  # noqa: E402
from spacemissionstudio.gui.gantt import PlanGantt, kind_colour  # noqa: E402
from spacemissionstudio.operations.opportunities import Opportunities, Pass, Window  # noqa: E402
from spacemissionstudio.operations.plan import Activity, Plan, Unscheduled  # noqa: E402

_HORIZON = {"start_utc": "2030-01-01T08:30:00Z", "end_utc": "2030-01-01T20:30:00Z"}


def _synthetic():
    """A plan of one acquisition (in a 600 s window) and one contact, with
    a pass, an eclipse and resource profiles."""
    t = np.array([1000.0, 1300.0, 1600.0])
    window = Window("sat", "paris", 1000.0, 1600.0, t, np.array([30.0, 10.0, 30.0]), np.zeros(3), np.zeros(3),
                    np.zeros(3))
    item = Pass("gs", "sat", 3000.0, 3600.0, 40.0, 3300.0)
    found = Opportunities([window], [item], {"sat": [(5000.0, 7000.0)]})
    image = Activity("A0001", "sat", "image", "acquisition", 1200.0, 1220.0, "2030-01-01T00:20:00.000Z",
                     "2030-01-01T00:20:20.000Z", pointing="target", target="paris",
                     predicted={"slew_deg": 30.0, "slew_s": 60.0})
    contact = Activity("A0002", "sat", "downlink", "contact", 3100.0, 3500.0, pointing="station", station="gs",
                       locked=True)
    resources = {"sat": {"time_s": [0.0, 4000.0, 8000.0], "soc": [0.9, 0.7, 0.8],
                         "memory_bit": [0.0, 1e9, 2e8], "capacity_bit": 4e9, "min_soc": 0.7}}
    plan = Plan("2030-01-01T00:00:00", 0.0, 8000.0, activities=[image, contact],
                unscheduled=[Unscheduled("lyon", "sat", "acquisition", 2, "conflict", {"conflict": 3})],
                resources=resources)
    return plan, found


def test_the_gantt_has_a_row_per_spacecraft_kind_and_station(qtbot):
    """Activities, eclipse, state of charge and memory per spacecraft; one
    row per station with its passes and contacts; the slew drawn before an
    activity; a locked activity flagged."""
    plan, found = _synthetic()
    gantt = PlanGantt()
    qtbot.addWidget(gantt)
    gantt.resize(900, 300)
    gantt.set_plan(plan, found, plan.epoch_utc, {"sat": 0.3})
    assert gantt.rows == ["sat", "sat eclipse", "sat state of charge", "sat memory", "gs"]
    kinds = sorted((gantt.gantt_rows[b.row].kind, b.kind) for b in gantt.bars)
    assert kinds == [("activities", "acquisition"), ("activities", "contact"), ("eclipse", "eclipse"),
                     ("station", "contact"), ("station", "pass")]
    image = next(b for b in gantt.bars if b.activity == "A0001")
    assert image.slew_from_s == pytest.approx(1140.0) and (image.low, image.high) == (1000.0, 1580.0)
    assert any(b.locked for b in gantt.bars if b.activity == "A0002")
    assert gantt.view == (0.0, 8000.0)
    gantt.grab()  # paints every row kind without error
    assert kind_colour("acquisition") != kind_colour("contact")
    gantt.set_plan(None)
    assert gantt.rows == [] and gantt.bars == []
    gantt.grab()


def test_a_click_selects_and_a_drag_moves_within_the_window(qtbot):
    """A click on the acquisition selects it; dragging it far to the right
    stops at the window's end (its start at 1580 s); a click on empty time
    picks the time and clears the selection."""
    plan, found = _synthetic()
    gantt = PlanGantt()
    qtbot.addWidget(gantt)
    gantt.resize(900, 300)
    gantt.show()
    gantt.set_plan(plan, found, plan.epoch_utc)
    gantt._show(900.0, 800.0)  # 900 s to 1700 s across
    selected, moved, picked = [], [], []
    gantt.activity_selected.connect(selected.append)
    gantt.activity_moved.connect(lambda name, start: moved.append((name, start)))
    gantt.time_picked.connect(picked.append)
    y = gantt._row_top(0) + 11
    x = int(gantt.x_of(1210.0))
    QTest.mousePress(gantt, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(x, y))
    assert selected == ["A0001"] and gantt.selected == "A0001"
    QTest.mouseMove(gantt, QPoint(gantt.width() - 10, y))
    QTest.mouseRelease(gantt, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                       QPoint(gantt.width() - 10, y))
    assert moved and moved[0][0] == "A0001" and moved[0][1] == pytest.approx(1580.0)
    QTest.mouseClick(gantt, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                     QPoint(int(gantt.x_of(1650.0)), y))
    assert selected[-1] == "" and picked and picked[-1] == pytest.approx(1650.0, abs=2.0)


def test_the_timeline_keeps_each_analysis_events_apart(qtbot):
    """Run › Plan's activities and Run › Thermal's limits are added by
    source: one replacing its own leaves the other's; a new run clears
    both; the "Planned activities" box filters them."""
    widget = EventTimelineWidget()
    qtbot.addWidget(widget)
    planned = Event(PLANNED, "sat", 10.0, 30.0, "A0001 image", other="gs")
    limit = Event(THERMAL_LIMIT, "sat", 100.0, 400.0, "battery below operating")
    widget.set_extra_events([planned], source="plan")
    widget.set_extra_events([limit])
    assert set(widget.events) == {planned, limit}
    assert not widget.kind_boxes[PLAN_BOX].isHidden() and not widget.kind_boxes[THERMAL_BOX].isHidden()
    widget.set_extra_events([])
    assert widget.events == [planned]
    widget.kind_boxes[PLAN_BOX].setChecked(False)
    assert widget.visible_events() == []
    widget.set_result(None)
    assert widget.events == []


def test_the_editor_keeps_the_operations_section_and_its_names_follow(qtbot):
    """A scenario with an operations section comes back from the editor
    with it; set_operations replaces it; a renamed spacecraft is renamed
    in the section too."""
    from spacemissionstudio.gui.scenario_editor import ScenarioEditorWidget

    scenario = fixtures.scenario()
    editor = ScenarioEditorWidget()
    qtbot.addWidget(editor)
    editor.from_scenario(scenario)
    assert editor.to_scenario().operations == scenario.operations
    section = editor.operations()
    section.targets = section.targets[:1]
    editor.set_operations(section)
    assert [t.name for t in editor.to_scenario().operations.targets] == ["rotterdam"]
    editor.show_spacecraft(0)
    node = editor._spacecraft_nodes[0]
    node.form.name_edit.setText("eo-sat-2")
    editor.flush_forms()
    assert editor.to_scenario().operations.spacecraft[0].spacecraft == "eo-sat-2"


@pytest.fixture(scope="module")
def planned_scenario():
    pytest.importorskip("Basilisk")
    return fixtures.scenario(horizon=_HORIZON)


def _page(qtbot, scenario):
    from spacemissionstudio.gui.plan_widget import PlanWidget

    page = PlanWidget()
    qtbot.addWidget(page)
    holder = {"scenario": scenario}
    page.set_scenario_provider(lambda: holder["scenario"])
    events, sections, problems = [], [], []
    page.events_changed.connect(events.append)
    page.operations_changed.connect(lambda section: (sections.append(section),
                                                     setattr(holder["scenario"], "operations", section)))
    page.problems_changed.connect(lambda: problems.append(page.problem_rows()))
    return page, holder, events, sections, problems


def _plan(qtbot, page):
    page.make_plan()
    qtbot.waitUntil(lambda: page.plan is not None and page._worker is None, timeout=120000)


def test_the_page_plans_and_shows_the_plan(qtbot, planned_scenario):
    """Plan fills the chart, the activity and request tables, the status
    at the time cursor; the activities go to the Timeline and the requests
    not placed to Problems."""
    import copy

    page, _holder, events, _sections, problems = _page(qtbot, copy.deepcopy(planned_scenario))
    assert page.chart_group.isHidden() and not page.fly_button.isEnabled()
    _plan(qtbot, page)
    plan = page.plan
    assert plan.activities and page.status_label.text().startswith(f"{len(plan.activities)} activities planned")
    assert page.activities_table.row_count() == len(plan.activities)
    assert page.gantt.rows[:2] == ["eo-sat", "eo-sat eclipse"] and "berlin-gs" in page.gantt.rows
    assert [e.label.split()[0] for e in events[-1]] == [a.id for a in plan.activities]
    assert all(e.kind == PLANNED for e in events[-1])
    assert problems[-1] == page.problem_rows()
    assert len(page.problem_rows()) == sum(1 for u in plan.unscheduled if u.kind != "contact")
    first = plan.activities[0]
    page.on_cursor_changed(first.start_s + 1.0)
    row = page.status_rows()[0]
    assert row["now"] == f"{first.id} {first.type}" and row["mode"] == first.pointing and row["done"] == 0
    assert 0.0 < row["soc_planned"] <= 100.0
    assert page.status_table.row_count() == 1
    page.on_cursor_changed(plan.end_s)
    assert page.status_rows()[0]["done"] == len(plan.of("eo-sat"))
    assert page.fly_button.isEnabled() and page.export_button.isEnabled()


def test_lock_unlock_delete_and_move(qtbot, planned_scenario):
    """Lock puts the activity in the section's locked list, Unlock takes it
    out; Delete takes one out of the plan and the others keep their ids; a
    move locks the activity at its new time and plans again."""
    import copy

    page, holder, _events, sections, _problems = _page(qtbot, copy.deepcopy(planned_scenario))
    _plan(qtbot, page)
    image = next(a for a in page.plan.activities if a.kind == "acquisition")
    page.gantt.select(image.id)
    page._on_selected(image.id)
    assert page.lock_button.isEnabled() and not page.unlock_button.isEnabled()
    assert image.id in page.selected_label.text()
    page.lock(image.id)
    assert [item.id for item in sections[-1].locked] == [image.id]
    assert page.plan.find(image.id).locked and page.unlock_button.isEnabled()
    page.unlock(image.id)
    assert sections[-1].locked == [] and not page.plan.find(image.id).locked
    others = [a.id for a in page.plan.activities if a.id != image.id]
    page.delete(image.id)
    assert page.plan.find(image.id) is None and [a.id for a in page.plan.activities] == others
    _plan(qtbot, page)
    image = next(a for a in page.plan.activities if a.kind == "acquisition")
    low, high = page.gantt._range(image, page.planning.opportunities)
    target = high if high - image.start_s > 1.0 else low
    page.move_activity(image.id, target)
    qtbot.waitUntil(lambda: page._worker is None and page.plan.find(image.id) is not None
                    and page.plan.find(image.id).locked, timeout=120000)
    moved = page.plan.find(image.id)
    assert moved.start_s == pytest.approx(target, abs=2e-3)
    assert [item.id for item in holder["scenario"].operations.locked] == [image.id]


def test_lose_a_pass_replans_and_compares(qtbot, planned_scenario):
    """Lose this pass replans from the contact's start without that pass;
    the comparison with the plan before is shown."""
    import copy

    page, _holder, _events, _sections, _problems = _page(qtbot, copy.deepcopy(planned_scenario))
    _plan(qtbot, page)
    contact = next(a for a in page.plan.activities if a.kind == "contact")
    page.gantt.select(contact.id)
    page._on_selected(contact.id)
    assert page.lose_button.isEnabled()
    page.lose_pass(contact.id)
    qtbot.waitUntil(lambda: page._worker is None and "replanned_from_utc" in page.plan.provenance,
                    timeout=120000)
    assert not any(a.kind == "contact" and a.station == contact.station and abs(a.start_s - contact.start_s) < 1.0
                   for a in page.plan.activities)
    assert page.other_plan is not None and page.compare_table.row_count() == 1
    assert page.compare_label.text().startswith("Compared with the plan before.")


def test_robustness_export_save_and_open(qtbot, planned_scenario, tmp_path):
    """Robustness fills its table and saves a batch the Monte Carlo view
    reads; Export writes every product; a saved plan opens again."""
    import copy

    from spacemissionstudio.engine import monte_carlo_results

    page, _holder, _events, _sections, _problems = _page(qtbot, copy.deepcopy(planned_scenario))
    _plan(qtbot, page)
    page.runs_spin.setValue(3)
    page.lost_spin.setValue(0.5)
    page.run_robustness()
    qtbot.waitUntil(lambda: page._worker is None and page.draws is not None, timeout=120000)
    assert page.robustness_table.row_count() == 6 and page.batch_button.isEnabled()
    page.save_batch(tmp_path / "batch")
    assert monte_carlo_results.load(tmp_path / "batch").kind == "operations"
    assert export_log.last("operations_robustness")[1].endswith("batch")
    written = page.export(tmp_path / "out")
    assert {"passes.csv", "passes.ics", "activities.json", "commands.json", "report.md"} <= {p.name for p in written}
    assert export_log.last("operations")[1].endswith("out")
    path = page.plan.save(tmp_path / "plan.json")
    ids = [a.id for a in page.plan.activities]
    page.load_plan(path)
    assert [a.id for a in page.plan.activities] == ids and page.planning is None
    assert not page.fly_button.isEnabled() and page.save_button.isEnabled()
    page.clear()
    assert page.plan is None and page.chart_group.isHidden()


def test_a_scenario_without_a_section_says_so(qtbot):
    from spacemissionstudio.gui.plan_widget import PlanWidget
    from spacemissionstudio.schema import load_scenario
    from spacemissionstudio import api

    page = PlanWidget()
    qtbot.addWidget(page)
    page.set_scenario_provider(lambda: load_scenario(api.template("26_earth_observation_data_downlink.json")))
    page.make_plan()
    assert "no 'operations' section" in page.status_label.text() and page._worker is None
    page.set_scenario_provider(None)
    page.make_plan()
    assert page.status_label.text() == "no scenario is open"


@pytest.mark.slow
def test_fly_and_verify_from_the_page(qtbot):
    """Fly and verify on a two-hour plan (an agile imager): the flags list
    is empty, the tables are filled and the status shows the flown mode
    and pointing error at the cursor."""
    pytest.importorskip("Basilisk")
    scenario = fixtures.scenario(horizon={"start_utc": "2030-01-01T08:30:00Z", "end_utc": "2030-01-01T10:30:00Z"})
    scenario.spacecraft[0].control_params = {"K": 1.0, "P": 8.0}  # [N*m], [N*m*s]
    page, _holder, _events, _sections, problems = _page(qtbot, scenario)
    _plan(qtbot, page)
    page.fly()
    assert page.stop_button.isEnabled()
    qtbot.waitUntil(lambda: page._worker is None and page.verification is not None, timeout=600000)
    assert page.verification.flags == [] and page.status_label.text() == "Flown: nothing beyond the tolerances."
    assert page.verification_table.row_count() == len(page.plan.activities)
    first = page.plan.activities[0]
    page.on_cursor_changed(0.5 * (first.start_s + first.end_s))
    row = page.status_rows()[0]
    assert row["mode_flown"] == first.pointing and row["pointing_error_deg"] < 5.0
