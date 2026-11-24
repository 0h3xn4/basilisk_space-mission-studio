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
"""Run › Plan: the operations plan of the scenario's ``operations``
section (SRS-F-30; docs/developer/operations-planning-design.md 2.9).

**Plan** builds the geometry, finds the opportunities and schedules, on a
background thread; the page then shows the plan as a Gantt chart
(:class:`gui.gantt.PlanGantt`), the plan's status at the time cursor (per
spacecraft: the activity now and the next one, the pointing mode, the
state of charge and the memory, the activities done), the requests it
could not place and why, and every activity.

Edits: **Lock** keeps an activity where it is when the plan is made again
(it goes into the scenario's ``operations.locked``, so it is saved and
undone with the scenario); **Unlock** takes the lock away; **Delete**
takes the activity out of the plan shown (the others are checked again
and keep their ids); a drag in the chart moves an activity within its
window or pass: it is locked at its new time and the rest is planned
again. **Lose this pass** replans from a contact's start with that pass
lost (a what-if event).

**Fly and verify** flies the plan in the simulation (the plan executor)
and checks the flown run against the plan; **Export...** writes the
operations products; **Replan from** keeps what started before a time
and plans the rest with the scenario's what-if events; **Robustness**
draws lost passes, link margins, slew times and the initial charge and
re-checks (or replans) each draw; **Compare with...** sets another plan
file beside this one. The plan's activities go to the Timeline and its
unplaced requests and verification flags to Problems.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from . import export_log
from .background_threads import WorkerThread
from .data_table import DataTable, Row
from .feedback import report
from .gantt import PlanGantt
from .theme import set_role
from .value_sheet import NoteList
from .widgets import EmptyState, set_off_reason

# The template the empty state opens: a week of an Earth observation microsatellite (User Manual, operations).
PLAN_TEMPLATE = "35_eo_operations_week.json"


class _Worker(WorkerThread):
    """One planning job off the GUI thread."""

    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, job, parent=None):
        super().__init__(parent)
        self._job = job

    def run(self) -> None:
        try:
            self.finished_ok.emit(self._job())
        except (Exception, SystemExit) as exc:  # noqa: BLE001 -- shown on the page, never a crashed thread
            self.failed.emit(str(exc) or type(exc).__name__)


def _number(value, digits: int = 1) -> str:
    if value is None:
        return ""
    try:
        if not np.isfinite(value):
            return ""
    except TypeError:
        return str(value)
    return f"{value:.{digits}f}"


def _minutes(seconds: float) -> str:
    return f"{seconds / 60.0:.1f}"


class PlanWidget(QWidget):
    """Run › Plan (module docstring)."""

    events_changed = Signal(list)  # the plan's activities as Timeline events (engine.events.Event)
    operations_changed = Signal(object)  # the scenario's new operations section (a lock or an unlock)
    problems_changed = Signal()  # problem_rows() changed
    monte_carlo_saved = Signal(str)  # the folder a robustness batch was saved in
    template_requested = Signal(str)  # the empty state's Open Template 35: the template's file name

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._scenario = self._result = self._base_dir = None
        self._scenario_provider = None
        self._cursor = None
        self.cursor_s: float | None = None
        self.planning = None  # operations.analysis.Planning
        self.plan = None  # operations.plan.Plan shown
        self.other_plan = None  # the plan compared with
        self.flown = None  # the flown run (ResultSet)
        self.verification = None
        self.draws = self.batch = None
        self._worker: _Worker | None = None
        self._cancel = False
        self._has_operations: bool | None = None  # the edited scenario has an operations section (None: unknown)

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.plan_button = QPushButton("Plan")
        self.plan_button.setToolTip("Build the geometry, find the opportunities and schedule the horizon of the "
                                    "scenario's operations section")
        self.plan_button.clicked.connect(self.make_plan)
        top.addWidget(self.plan_button)
        self.from_run_check = QCheckBox("Geometry from the last run")
        self.from_run_check.setToolTip("Use the last run's orbit and Earth orientation instead of the section's own "
                                       "geometry source (the run must cover the horizon)")
        top.addWidget(self.from_run_check)
        top.addStretch(1)
        self.open_button = QPushButton("Open plan...")
        self.open_button.setToolTip("Show a plan file (spacemissionstudio-plan JSON)")
        self.open_button.clicked.connect(self._open_clicked)
        top.addWidget(self.open_button)
        self.save_button = QPushButton("Save plan...")
        self.save_button.clicked.connect(self._save_clicked)
        top.addWidget(self.save_button)
        self.export_button = QPushButton("Export...")
        self.export_button.setToolTip("Write the operations products to a folder: passes (CSV, iCalendar), "
                                      "activities (CSV, JSON), the command schedule (JSON, CSV), pointing "
                                      "predictions, OEM and AEM, and the plan report")
        self.export_button.clicked.connect(self._export_clicked)
        top.addWidget(self.export_button)
        layout.addLayout(top)
        self.status_label = set_role(QLabel(""), tone="secondary")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self.notes_list = NoteList("note")
        layout.addWidget(self.notes_list)
        # No plan yet: what a plan is, and how to start one (UI audit UI-22).
        self.empty_state = EmptyState("No plan yet", "")
        self.empty_state.button.clicked.connect(self._on_empty_action)
        layout.addWidget(self.empty_state)

        self.chart_group = QGroupBox("Plan")
        chart = QVBoxLayout(self.chart_group)
        self.gantt = PlanGantt()
        self.gantt.activity_selected.connect(self._on_selected)
        self.gantt.activity_moved.connect(self.move_activity)
        self.gantt.time_picked.connect(self._pick_time)
        chart.addWidget(self.gantt)
        edits = QHBoxLayout()
        self.selected_label = set_role(QLabel("Click an activity to select it."), tone="secondary")
        self.selected_label.setWordWrap(True)
        edits.addWidget(self.selected_label, 1)
        self.lock_button = QPushButton("Lock")
        self.lock_button.setToolTip("Keep this activity where it is when the plan is made again (saved in the "
                                    "scenario's operations.locked)")
        self.lock_button.clicked.connect(lambda: self.lock(self.gantt.selected))
        self.unlock_button = QPushButton("Unlock")
        self.unlock_button.clicked.connect(lambda: self.unlock(self.gantt.selected))
        self.delete_button = QPushButton("Delete")
        self.delete_button.setToolTip("Take the activity out of this plan; the others are checked again")
        self.delete_button.clicked.connect(lambda: self.delete(self.gantt.selected))
        self.lose_button = QPushButton("Lose this pass")
        self.lose_button.setToolTip("Replan from this contact's start with its pass lost (a what-if event)")
        self.lose_button.clicked.connect(lambda: self.lose_pass(self.gantt.selected))
        self.fit_button = QPushButton("Fit")
        self.fit_button.setToolTip("Show the whole horizon (0). The wheel zooms; Shift+wheel or a right-button "
                                   "drag moves the chart.")
        self.fit_button.clicked.connect(self.gantt.fit)
        for button in (self.lock_button, self.unlock_button, self.delete_button, self.lose_button, self.fit_button):
            edits.addWidget(button)
        chart.addLayout(edits)
        layout.addWidget(self.chart_group)

        self.status_group = QGroupBox("Plan status at the time cursor")
        self.status_table = DataTable()
        QVBoxLayout(self.status_group).addWidget(self.status_table)
        layout.addWidget(self.status_group)

        self.unscheduled_group = QGroupBox("Requests not placed")
        self.unscheduled_table = DataTable()
        QVBoxLayout(self.unscheduled_group).addWidget(self.unscheduled_table)
        layout.addWidget(self.unscheduled_group)

        self.activities_group = QGroupBox("Activities")
        self.activities_table = DataTable()
        self.activities_table.set_single_pick()
        self.activities_table.row_chosen.connect(self._on_row_chosen)
        QVBoxLayout(self.activities_group).addWidget(self.activities_table)
        layout.addWidget(self.activities_group)

        self._build_flight(layout)
        self._build_replan(layout)
        self._build_robustness(layout)
        layout.addStretch(1)
        self._show()

    # -- building -----------------------------------------------------------

    def _build_flight(self, layout) -> None:
        self.flight_group = QGroupBox("Fly and verify")
        flight = QVBoxLayout(self.flight_group)
        row = QHBoxLayout()
        self.fly_button = QPushButton("Fly and verify")
        self.fly_button.setToolTip("Fly the plan in the simulation (the plan executor switches pointing and "
                                   "devices at the plan's times) and check the flown run against the plan")
        self.fly_button.clicked.connect(self.fly)
        row.addWidget(self.fly_button)
        self.stop_button = QPushButton("Stop")
        self.stop_button.setToolTip("Stop the flight at the next step")
        self.stop_button.clicked.connect(self._stop)
        self.stop_button.setEnabled(False)
        row.addWidget(self.stop_button)
        row.addStretch(1)
        flight.addLayout(row)
        self.flags_list = NoteList("warning", empty="")
        flight.addWidget(self.flags_list)
        self.verification_table = DataTable()
        flight.addWidget(self.verification_table)
        self.resources_table = DataTable()
        flight.addWidget(self.resources_table)
        layout.addWidget(self.flight_group)

    def _build_replan(self, layout) -> None:
        self.replan_group = QGroupBox("Replan and compare")
        replan = QVBoxLayout(self.replan_group)
        row = QHBoxLayout()
        row.addWidget(QLabel("Replan from (UTC)"))
        self.replan_edit = QLineEdit()
        self.replan_edit.setPlaceholderText("2030-01-01T12:00:00Z (empty: the time cursor)")
        self.replan_edit.setToolTip("Activities that start before this time are kept; the scenario's what-if "
                                    "events apply; the rest of the horizon is planned again")
        row.addWidget(self.replan_edit, 1)
        self.replan_button = QPushButton("Replan")
        self.replan_button.clicked.connect(lambda: self.replan(self.replan_edit.text().strip()))
        row.addWidget(self.replan_button)
        self.compare_button = QPushButton("Compare with...")
        self.compare_button.setToolTip("Set a plan file beside this plan: what each holds, per spacecraft")
        self.compare_button.clicked.connect(self._compare_clicked)
        row.addWidget(self.compare_button)
        replan.addLayout(row)
        self.compare_label = set_role(QLabel(""), tone="secondary")
        self.compare_label.setWordWrap(True)
        replan.addWidget(self.compare_label)
        self.compare_table = DataTable()
        replan.addWidget(self.compare_table)
        layout.addWidget(self.replan_group)

    def _build_robustness(self, layout) -> None:
        self.robustness_group = QGroupBox("Robustness")
        robustness = QVBoxLayout(self.robustness_group)
        row = QHBoxLayout()
        self.runs_spin = QSpinBox()
        self.runs_spin.setRange(1, 10000)
        self.runs_spin.setValue(50)
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 2**31 - 1)
        self.lost_spin = QDoubleSpinBox()
        self.lost_spin.setRange(0.0, 1.0)
        self.lost_spin.setSingleStep(0.05)
        self.lost_spin.setToolTip("Each planned contact is lost with this probability")
        self.sigma_spin = QDoubleSpinBox()
        self.sigma_spin.setRange(0.0, 20.0)
        self.sigma_spin.setSuffix(" dB")
        self.sigma_spin.setToolTip("Standard deviation of an offset added to every predicted link margin")
        self.spread_spin = QDoubleSpinBox()
        self.spread_spin.setRange(0.0, 0.9)
        self.spread_spin.setSingleStep(0.05)
        self.spread_spin.setToolTip("Every slew takes its time times a factor drawn within 1 ± this")
        for text, widget in (("Runs", self.runs_spin), ("Seed", self.seed_spin), ("Lost pass [-]", self.lost_spin),
                             ("Link sigma", self.sigma_spin), ("Slew spread [-]", self.spread_spin)):
            row.addWidget(QLabel(text))
            row.addWidget(widget)
        self.replan_draws_check = QCheckBox("Replan each draw")
        self.replan_draws_check.setToolTip("Plan again under each draw's conditions instead of re-checking this plan")
        row.addWidget(self.replan_draws_check)
        row.addStretch(1)
        robustness.addLayout(row)
        row = QHBoxLayout()
        self.robustness_button = QPushButton("Run robustness")
        self.robustness_button.clicked.connect(self.run_robustness)
        row.addWidget(self.robustness_button)
        self.batch_button = QPushButton("Save batch...")
        self.batch_button.setToolTip("Save the draws as a Monte Carlo batch and show it in the Monte Carlo view")
        self.batch_button.clicked.connect(self._batch_clicked)
        row.addWidget(self.batch_button)
        row.addStretch(1)
        robustness.addLayout(row)
        self.robustness_label = set_role(QLabel(""), tone="secondary")
        self.robustness_label.setWordWrap(True)
        robustness.addWidget(self.robustness_label)
        self.robustness_table = DataTable()
        robustness.addWidget(self.robustness_table)
        layout.addWidget(self.robustness_group)

    # -- wiring -------------------------------------------------------------

    def set_scenario_provider(self, provider) -> None:
        """``provider()`` gives the scenario as edited (validated); it is
        what Plan, Fly and Replan use."""
        self._scenario_provider = provider

    def set_time_cursor(self, cursor) -> None:
        self._cursor = cursor
        cursor.changed.connect(self.on_cursor_changed)
        self.on_cursor_changed(cursor.time_s)

    def on_cursor_changed(self, time_s: float | None) -> None:
        self.cursor_s = time_s
        self.gantt.set_cursor_time(time_s)
        self._show_status()

    def _pick_time(self, time_s: float) -> None:
        if self._cursor is not None:
            self._cursor.set_time(time_s)
        else:
            self.on_cursor_changed(time_s)

    def set_scenario(self, scenario) -> None:
        """The edited scenario (None while it does not validate): whether it
        has an operations section decides what the empty state offers."""
        has = None if scenario is None else getattr(scenario, "operations", None) is not None
        if has != self._has_operations:
            self._has_operations = has
            self._show_empty()

    def _show_empty(self) -> None:
        """The empty state while there is no plan: with an operations
        section, Plan; without one, the template that has one."""
        empty = self.plan is None
        self.empty_state.setVisible(empty)
        if not empty:
            return
        what = ("A plan schedules the activities of the scenario's operations section (images, passes, "
                "calibrations) against the battery and the memory.")
        if self._has_operations is False:
            self.empty_state.set_text("No operations section", f"{what} This scenario has none. Template 35 has "
                                      "one: a week of an Earth observation microsatellite. Open plan... shows a "
                                      "saved plan.", "Open Template 35")
        else:
            self.empty_state.set_text("No plan yet", f"{what} Plan makes one from the scenario's section; Open "
                                      "plan... shows a saved plan.", "Plan")
        self.empty_state.button.setEnabled(self._worker is None)

    def _note_missing_section(self) -> None:
        """Plan found no operations section: the empty state then offers
        the template that has one."""
        try:
            scenario = self.scenario()
        except Exception:  # noqa: BLE001 -- no scenario, or one that does not validate: the status says why
            return
        self.set_scenario(scenario)

    def _on_empty_action(self) -> None:
        if self._has_operations is False:
            self.template_requested.emit(PLAN_TEMPLATE)
        else:
            self.make_plan()

    def set_run(self, scenario, result, base_dir=None) -> None:
        """The last run (its geometry can be used; None: no run)."""
        self._scenario, self._result, self._base_dir = scenario, result, base_dir
        self._show()
        self.events_changed.emit(self.events())

    def clear(self) -> None:
        """Forget the plan, the run and what was made from them (another scenario)."""
        self.planning = self.plan = self.other_plan = self.flown = self.verification = None
        self.draws = self.batch = None
        self._scenario = self._result = None
        self.gantt.set_plan(None)
        self._show()
        self.events_changed.emit([])
        self.problems_changed.emit()

    def scenario(self):
        """The scenario Plan, Fly and Replan use: the edited one when a
        provider is set, else the last run's."""
        if self._scenario_provider is not None:
            return self._scenario_provider()
        if self._scenario is None:
            raise ValueError("no scenario is open")
        return self._scenario

    def _planned_scenario(self):
        scenario = self.scenario()
        if getattr(scenario, "operations", None) is None:
            raise ValueError("the scenario has no 'operations' section: add one in Scenario › JSON (see the "
                             "how-to 'Plan a week of operations')")
        return scenario

    def wait_for_worker(self, timeout_ms: int = 600000) -> None:
        if self._worker is not None:
            self._worker.wait(timeout_ms)

    def _run(self, text: str, job, done) -> bool:
        if self._worker is not None:
            return False
        self.status_label.setText(text)
        self._worker = _Worker(job, self)
        self._worker.finished_ok.connect(done)
        self._worker.failed.connect(self._failed)
        self._worker.finished.connect(self._worker_done)
        self._show_buttons()
        self._worker.start()
        return True

    def _worker_done(self) -> None:
        self._worker = None
        self._cancel = False
        self._show_buttons()

    def _failed(self, message: str) -> None:
        self.status_label.setText(message)

    # -- planning -----------------------------------------------------------

    def make_plan(self) -> None:
        from ..operations import analysis

        try:
            scenario = self._planned_scenario()
        except Exception as exc:  # noqa: BLE001 -- an invalid scenario is said on the page
            self.status_label.setText(str(exc))
            self._note_missing_section()
            return
        result = self._result if self.from_run_check.isChecked() else None
        self._run("Building the geometry and scheduling...", lambda: analysis.plan(scenario, result),
                  self.show_planning)

    def show_planning(self, planning) -> None:
        """Show what a planning run built (operations.analysis.Planning)."""
        self.planning = planning
        self.flown = self.verification = None
        self.draws = self.batch = None
        self._set_plan(planning.plan)
        seconds = planning.seconds or {}
        self.status_label.setText(
            f"{len(planning.plan.activities)} activities planned, {len(planning.plan.unscheduled)} requests not "
            f"placed; geometry {planning.geometry.source} at {planning.geometry.step_s:g} s "
            f"({sum(seconds.values()):.1f} s).")

    def _set_plan(self, plan) -> None:
        self.plan = plan
        floors = {}
        section = getattr(self.planning.scenario, "operations", None) if self.planning is not None else None
        if section is not None:
            floors = {p.spacecraft: p.min_soc for p in section.spacecraft if p.min_soc is not None}
        epoch = plan.epoch_utc if plan is not None else None
        self.gantt.set_plan(plan, self.planning.opportunities if self.planning is not None else None, epoch, floors)
        self._show()
        self.events_changed.emit(self.events())
        self.problems_changed.emit()

    def load_plan(self, path) -> None:
        """Show the plan file at ``path``; the scenario's geometry is not
        built until Plan (the chart has no passes or eclipses then)."""
        from ..operations.plan import Plan

        plan = Plan.load(path)
        self.planning = None
        self.flown = self.verification = None
        self._set_plan(plan)
        self.status_label.setText(f"Plan file {Path(path).name}: {len(plan.activities)} activities.")

    def _open_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open a plan", "", "Plan (*.json)")
        if path:
            try:
                self.load_plan(path)
            except (OSError, ValueError, TypeError) as exc:
                report(self, f"Could not open {path}: {exc}")

    def _save_clicked(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save the plan", "plan.json", "Plan (*.json)")
        if path:
            try:
                self.plan.save(path)
            except OSError as exc:
                report(self, f"Could not write {path}: {exc}")
                return
            export_log.record("plan", Path(path))
            report(self, f"Saved the plan to {path}", kind="success")

    def export(self, folder: Path) -> list[Path]:
        """Every operations product in ``folder``."""
        from ..operations import exports

        written = exports.write_all(folder, self.planning, self.plan, self.verification)
        export_log.record("operations", folder)
        return written

    def _export_clicked(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Export the operations products to a folder")
        if folder:
            self._run("Writing the operations products...", lambda: self.export(Path(folder)),
                      lambda written: self.status_label.setText(f"Wrote {len(written)} files to {folder}."))

    # -- edits --------------------------------------------------------------

    def _section(self):
        import copy

        return copy.deepcopy(self.scenario().operations)

    def lock(self, activity_id: str) -> None:
        """Lock the activity at its time (in the scenario's operations.locked)."""
        from ..schema.operations import LockedActivityConfig

        activity = self.plan.find(activity_id) if self.plan is not None else None
        if activity is None or activity.locked:
            return
        section = self._section()
        request = activity.request.split("#")[0] if activity.request else ""
        section.locked = [item for item in section.locked if item.id != activity.id]
        section.locked.append(LockedActivityConfig(activity.id, activity.spacecraft, activity.type,
                                                   activity.start_utc, activity.end_utc, activity.target,
                                                   activity.station, request))
        activity.locked = True
        self.operations_changed.emit(section)
        self._refresh_plan_view(activity.id)

    def unlock(self, activity_id: str) -> None:
        activity = self.plan.find(activity_id) if self.plan is not None else None
        if activity is None:
            return
        section = self._section()
        section.locked = [item for item in section.locked if item.id != activity.id]
        activity.locked = False
        self.operations_changed.emit(section)
        self._refresh_plan_view(activity.id)

    def delete(self, activity_id: str) -> None:
        """Take the activity out of the plan shown (its lock goes too)."""
        from ..operations import analysis

        activity = self.plan.find(activity_id) if self.plan is not None else None
        if activity is None or self.planning is None:
            return
        if activity.locked:
            self.unlock(activity_id)
        self._set_plan(analysis.without(self.planning, self.plan, activity_id))
        self.status_label.setText(f"Deleted {activity_id}; the other activities were checked again.")

    def move_activity(self, activity_id: str, start_s: float) -> None:
        """Lock the activity at ``start_s`` and plan the rest again."""
        from ..schema.operations import LockedActivityConfig

        activity = self.plan.find(activity_id) if self.plan is not None else None
        if activity is None or self.planning is None:
            return
        base = self.planning.timebase
        section = self._section()
        section.locked = [item for item in section.locked if item.id != activity.id]
        request = activity.request.split("#")[0] if activity.request else ""
        section.locked.append(LockedActivityConfig(activity.id, activity.spacecraft, activity.type, base.text(start_s),
                                                   base.text(start_s + activity.duration_s), activity.target,
                                                   activity.station, request))
        self.operations_changed.emit(section)
        self.make_plan()

    def _refresh_plan_view(self, selected: str) -> None:
        self._set_plan(self.plan)
        self.gantt.select(selected)
        self._on_selected(selected)

    def _on_selected(self, activity_id: str) -> None:
        activity = self.plan.find(activity_id) if self.plan is not None and activity_id else None
        if activity is None:
            self.selected_label.setText("Click an activity to select it.")
        else:
            what = activity.type + (f" of {activity.target}" if activity.target else "") + \
                (f" via {activity.station}" if activity.station else "")
            predicted = activity.predicted
            extra = []
            if predicted.get("off_nadir_deg") is not None:
                extra.append(f"off-nadir {predicted['off_nadir_deg']:.1f}°")
            if predicted.get("slew_deg"):
                extra.append(f"slew {predicted['slew_deg']:.0f}° in {predicted.get('slew_s', 0.0):.0f} s")
            self.selected_label.setText(f"{activity.id}: {what}, {activity.spacecraft}, {activity.start_utc} for "
                                        f"{activity.duration_s:.0f} s" + (f"; {', '.join(extra)}" if extra else "")
                                        + ("; locked" if activity.locked else ""))
        self._show_buttons()

    def _on_row_chosen(self, row: int) -> None:
        if self.plan is not None and 0 <= row < len(self.plan.activities):
            activity = self.plan.activities[row]
            self.gantt.select(activity.id)
            self._on_selected(activity.id)

    # -- flying ---------------------------------------------------------------

    def fly(self) -> None:
        from ..operations import analysis, verify

        try:
            scenario = self._planned_scenario()
        except Exception as exc:  # noqa: BLE001 -- said on the page
            self.status_label.setText(str(exc))
            return
        plan = self.plan

        def job():
            result = analysis.fly(scenario, plan, should_cancel=lambda: self._cancel)
            return result, verify.check(scenario, plan, result)

        self._run("Flying the plan in the simulation...", job, self.show_flight)

    def _stop(self) -> None:
        self._cancel = True

    def show_flight(self, flown) -> None:
        result, verification = flown
        self.flown, self.verification = result, verification
        self.status_label.setText("Flown: " + (f"{len(verification.flags)} flags." if verification.flags
                                               else "nothing beyond the tolerances."))
        self._show()
        self.problems_changed.emit()

    # -- replanning and comparing ---------------------------------------------

    def replan(self, from_utc: str = "", events=None) -> None:
        """Replan from ``from_utc`` (empty: the time cursor) with ``events``
        (None: the scenario's what-if events)."""
        from ..operations import whatif

        if self.plan is None:
            return
        try:
            scenario = self._planned_scenario()
        except Exception as exc:  # noqa: BLE001 -- said on the page
            self.status_label.setText(str(exc))
            return
        if not from_utc:
            from ..operations.timebase import TimeBase

            at = self.cursor_s if self.cursor_s is not None else self.plan.start_s
            from_utc = TimeBase(scenario.epoch_utc).text(at)
        before, planning = self.plan, self.planning
        result = self._result if self.from_run_check.isChecked() else None

        def job():
            return whatif.replan(scenario, before, from_utc, events, result, planning)

        def done(new) -> None:
            self.show_planning(new)
            self.compare_with(before, "the plan before")
            self.status_label.setText(f"Replanned from {from_utc}: {len(new.plan.activities)} activities.")

        self._run(f"Replanning from {from_utc}...", job, done)

    def lose_pass(self, activity_id: str) -> None:
        """Replan from a contact's start with its pass lost."""
        from ..schema.operations import WhatIfConfig

        activity = self.plan.find(activity_id) if self.plan is not None else None
        if activity is None or activity.kind != "contact":
            return
        event = WhatIfConfig("lost_pass", at_utc=activity.start_utc, station=activity.station,
                             spacecraft=activity.spacecraft)
        self.replan(activity.start_utc, [event])

    def compare_with(self, other, name: str) -> None:
        """Show ``other`` (a Plan) beside the plan shown: "a" is this plan."""
        from ..operations import robustness

        self.other_plan = other
        found = robustness.compare(self.plan, other)
        rows = []
        for row in found["spacecraft"]:
            a, b = row["a"], row["b"]
            rows.append(Row((row["spacecraft"], str(a["activities"]), str(b["activities"]), str(a["acquisitions"]),
                             str(b["acquisitions"]), _minutes(a["contact_s"]), _minutes(b["contact_s"]),
                             _number(100.0 * a["min_soc"] if a["min_soc"] is not None else None),
                             _number(100.0 * b["min_soc"] if b["min_soc"] is not None else None))))
        self.compare_table.set_table(["Spacecraft", "Activities (this)", f"Activities ({name})",
                                      "Acquisitions (this)", f"Acquisitions ({name})", "Contact [min] (this)",
                                      f"Contact [min] ({name})", "Lowest SoC [%] (this)", f"Lowest SoC [%] ({name})"],
                                     rows, numeric=range(1, 9))
        self.compare_table.fit_rows()
        only_a = ", ".join(f"{r['request']} ({r['spacecraft']})" for r in found["only_in_a"]) or "none"
        only_b = ", ".join(f"{r['request']} ({r['spacecraft']})" for r in found["only_in_b"]) or "none"
        self.compare_label.setText(f"Compared with {name}. Only in this plan: {only_a}. Only in {name}: {only_b}.")
        self.compare_table.setVisible(True)

    def _compare_clicked(self) -> None:
        from ..operations.plan import Plan

        path, _ = QFileDialog.getOpenFileName(self, "Compare with a plan", "", "Plan (*.json)")
        if path:
            try:
                self.compare_with(Plan.load(path), Path(path).name)
            except (OSError, ValueError, TypeError) as exc:
                report(self, f"Could not open {path}: {exc}")

    # -- robustness -----------------------------------------------------------

    def robustness_settings(self) -> dict:
        return {"lost_pass_probability": self.lost_spin.value(), "margin_sigma_db": self.sigma_spin.value(),
                "slew_spread": self.spread_spin.value(), "replan": self.replan_draws_check.isChecked()}

    def run_robustness(self) -> None:
        from ..operations import robustness

        if self.planning is None or self.plan is None:
            return
        planning, plan = self.planning, self.plan
        runs, seed, settings = self.runs_spin.value(), self.seed_spin.value(), self.robustness_settings()

        def job():
            draws = robustness.run(planning, plan, runs, seed, **settings)
            return draws, robustness.to_batch(planning, plan, draws, seed, settings)

        self._run(f"Drawing {runs} runs...", job, self.show_robustness)

    def show_robustness(self, found) -> None:
        self.draws, self.batch = found
        draws = self.draws
        rows = []
        for label, values, digits in (
                ("Acquisitions", [d.acquisitions for d in draws], 0),
                ("Acquisitions lost", [d.acquisitions_lost for d in draws], 0),
                ("Contacts lost", [d.contacts_lost for d in draws], 0),
                ("Lowest state of charge [%]", [100.0 * d.min_soc for d in draws], 1),
                ("Data lost [Gbit]", [d.lost_bit / 1e9 for d in draws], 3),
                ("Backlog at the end [Gbit]", [d.backlog_bit / 1e9 for d in draws], 3)):
            values = np.asarray(values, dtype=float)
            rows.append(Row((label, _number(values.min(), digits), _number(values.mean(), digits),
                             _number(values.max(), digits))))
        self.robustness_table.set_table(["Outcome", "Least", "Mean", "Most"], rows, numeric=(1, 2, 3))
        self.robustness_table.fit_rows()
        self.robustness_table.setVisible(True)
        self.robustness_label.setText(f"{len(draws)} draws, seed {self.seed_spin.value()}: the same seed gives the "
                                      "same draws.")
        self.status_label.setText("Robustness done.")
        self._show_buttons()

    def save_batch(self, folder: Path) -> Path:
        from ..engine import monte_carlo_results

        path = monte_carlo_results.save(self.batch, folder)
        export_log.record("operations_robustness", folder)
        return path

    def _batch_clicked(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Save the robustness batch to a folder")
        if folder:
            try:
                self.save_batch(Path(folder))
            except OSError as exc:
                report(self, f"Could not write {folder}: {exc}")
                return
            self.monte_carlo_saved.emit(folder)

    # -- showing --------------------------------------------------------------

    def events(self) -> list:
        """The plan's activities as Timeline events."""
        from ..engine.events import PLANNED, Event

        if self.plan is None:
            return []
        return [Event(PLANNED, a.spacecraft, a.start_s, a.end_s, f"{a.id} {a.type}",
                      detail=(f"{a.target} " if a.target else "") + ("locked" if a.locked else ""),
                      other=a.station) for a in self.plan.activities]

    def problem_rows(self) -> list:
        """The plan's warnings as Problems rows ``(severity, text, shown text)``."""
        rows = []
        if self.plan is not None:
            for item in self.plan.unscheduled:
                if item.kind == "contact":  # a pass not used is a choice, listed on the page only
                    continue
                text = f"Plan: {item.kind} {item.request} ({item.spacecraft}) not placed: {item.text}"
                rows.append(("warning", text, text))
        if self.verification is not None:
            for flag in self.verification.flags:
                text = f"Plan verification: {flag}"
                rows.append(("warning", text, text))
        return rows

    def _show_buttons(self) -> None:
        busy = self._worker is not None
        self.empty_state.button.setEnabled(not busy)
        has_plan = self.plan is not None
        selected = self.plan.find(self.gantt.selected) if has_plan and self.gantt.selected else None
        editable = selected is not None and self.planning is not None and not busy
        self.plan_button.setEnabled(not busy)
        self.from_run_check.setEnabled(self._result is not None)
        for button in (self.save_button, self.compare_button):  # off with the reason (UI audit UI-42)
            set_off_reason(button, has_plan and not busy, "Off: planning is running." if busy else
                           "Off: there is no plan yet. Press Plan first.")
        planned = has_plan and self.planning is not None and not busy
        for button in (self.export_button, self.fly_button, self.replan_button, self.robustness_button):
            button.setEnabled(planned)
        self.stop_button.setEnabled(busy)
        self.lock_button.setEnabled(editable and not selected.locked)
        self.unlock_button.setEnabled(editable and selected.locked)
        self.delete_button.setEnabled(editable)
        self.lose_button.setEnabled(editable and selected.kind == "contact")
        self.batch_button.setEnabled(self.batch is not None and not busy)

    def _show(self) -> None:
        plan = self.plan
        self.chart_group.setVisible(plan is not None)
        for group in (self.status_group, self.activities_group, self.flight_group, self.replan_group,
                      self.robustness_group):
            group.setVisible(plan is not None)
        self._show_empty()
        if plan is None:
            self.status_label.setText("" if self._worker is None else self.status_label.text())
            self.notes_list.set_notes([])
            self.unscheduled_group.setVisible(False)
            self._show_buttons()
            return
        self.notes_list.set_notes(list(plan.notes))
        self.unscheduled_group.setVisible(bool(plan.unscheduled))
        self.unscheduled_table.set_table(
            ["Request", "Spacecraft", "Kind", "Priority", "Placed", "Needed", "Reason"],
            [Row((u.request, u.spacecraft, u.kind, str(u.priority), str(u.placed), str(u.needed), u.text),
                 tooltips={6: ", ".join(f"{k}: {v}" for k, v in sorted(u.counts.items()))})
             for u in plan.unscheduled], numeric=(3, 4, 5), stretch=6)
        self.unscheduled_table.fit_rows()
        rows = []
        for a in plan.activities:
            predicted = a.predicted
            rows.append(Row((a.id, a.spacecraft, a.type, a.start_utc, _number(a.duration_s, 0),
                             a.target or a.station or a.request, a.pointing,
                             _number(predicted.get("off_nadir_deg")), _number(predicted.get("slew_deg"), 0),
                             "yes" if a.locked else "")))
        self.activities_table.set_table(["Id", "Spacecraft", "Type", "Start (UTC)", "Duration [s]", "Of",
                                         "Pointing", "Off-nadir [deg]", "Slew [deg]", "Locked"], rows,
                                        numeric=(4, 7, 8), stretch=5)
        self.activities_table.fit_rows()
        self._show_verification()
        self.compare_table.setVisible(self.other_plan is not None)
        self.robustness_table.setVisible(self.draws is not None)
        self._show_status()
        self._show_buttons()

    def _show_verification(self) -> None:
        verification = self.verification
        self.flags_list.set_notes(verification.flags if verification is not None else [])
        self.verification_table.setVisible(verification is not None)
        self.resources_table.setVisible(verification is not None)
        if verification is None:
            return
        rows = [Row((a.id, a.type, "yes" if a.flown else "no", _number(a.error_at_start_deg, 2),
                     _number(a.error_max_deg, 2), _number(a.off_nadir_planned_deg, 2),
                     _number(a.off_nadir_flown_deg, 2), _number(a.margin_min_db, 1), "; ".join(a.flags)))
                for a in verification.activities]
        self.verification_table.set_table(["Id", "Type", "Flown", "Error at start [deg]", "Max error [deg]",
                                           "Off-nadir planned [deg]", "Off-nadir flown [deg]", "Lowest margin [dB]",
                                           "Flags"], rows, numeric=range(3, 8), stretch=8)
        self.verification_table.fit_rows()
        rows = [Row((r.spacecraft, _number(r.soc_max_difference_points, 2),
                     _number(100.0 * r.soc_min_planned if r.soc_min_planned is not None else None),
                     _number(100.0 * r.soc_min_flown if r.soc_min_flown is not None else None),
                     _number(100.0 * r.memory_max_difference_fraction
                             if r.memory_max_difference_fraction is not None else None, 2), "; ".join(r.flags)))
                for r in verification.resources]
        self.resources_table.set_table(["Spacecraft", "SoC difference [points]", "Lowest SoC planned [%]",
                                        "Lowest SoC flown [%]", "Memory difference [% of capacity]", "Flags"], rows,
                                       numeric=range(1, 5), stretch=5)
        self.resources_table.fit_rows()

    def status_rows(self, time_s: float | None = None) -> list[dict]:
        """Per spacecraft at ``time_s`` (None: the time cursor, else the
        horizon's start): the activity now and the next one, the mode, the
        planned (and flown) state of charge and memory, the activities done."""
        from ..operations.execution import MODES

        plan = self.plan
        if plan is None:
            return []
        t = time_s if time_s is not None else (self.cursor_s if self.cursor_s is not None else plan.start_s)
        defaults = {}
        if self.planning is not None and self.planning.scenario.operations is not None:
            defaults = {p.spacecraft: p.default_pointing for p in self.planning.scenario.operations.spacecraft}
        rows = []
        for name in dict.fromkeys([a.spacecraft for a in plan.activities] + list(plan.resources)):
            mine = sorted(plan.of(name), key=lambda a: a.start_s)
            now = next((a for a in mine if a.start_s <= t < a.end_s), None)
            following = next((a for a in mine if a.start_s > t), None)
            row = {"spacecraft": name, "now": f"{now.id} {now.type}" if now else "",
                   "mode": now.pointing if now else defaults.get(name, "sun"),
                   "next": f"{following.id} {following.type}" if following else "",
                   "next_in_min": (following.start_s - t) / 60.0 if following else None,
                   "done": sum(1 for a in mine if a.end_s <= t), "total": len(mine)}
            resources = plan.resources.get(name)
            if resources and resources.get("time_s"):
                time = np.asarray(resources["time_s"], dtype=float)
                row["soc_planned"] = float(np.interp(t, time, resources["soc"])) * 100.0
                row["memory_planned_gbit"] = float(np.interp(t, time, resources["memory_bit"])) / 1e9
            if self.flown is not None:
                mode = self.flown.series.get(f"{name}.plan.mode")
                if mode is not None and mode.time_s.size:
                    k = int(np.clip(np.searchsorted(mode.time_s, t, "right") - 1, 0, mode.time_s.size - 1))
                    row["mode_flown"] = MODES[int(mode.data[k, 0])] if 0 <= int(mode.data[k, 0]) < len(MODES) else ""
                error = self.flown.series.get(f"{name}.plan.pointing_error_deg")
                if error is not None and error.time_s.size:
                    row["pointing_error_deg"] = float(np.interp(t, error.time_s, error.data[:, 0]))
            rows.append(row)
        return rows

    def _show_status(self) -> None:
        if self.plan is None:
            return
        rows = []
        for row in self.status_rows():
            rows.append(Row((row["spacecraft"], row["now"] or "(none)", row.get("mode_flown") or row["mode"],
                             row["next"], _number(row["next_in_min"]), f"{row['done']} of {row['total']}",
                             _number(row.get("soc_planned")), _number(row.get("memory_planned_gbit"), 3),
                             _number(row.get("pointing_error_deg"), 2))))
        self.status_table.set_table(["Spacecraft", "Now", "Mode", "Next", "Next in [min]", "Done",
                                     "SoC planned [%]", "Memory planned [Gbit]", "Pointing error flown [deg]"],
                                    rows, numeric=(4, 6, 7, 8))
        self.status_table.fit_rows()
