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
"""Run › Design checks: the static checks of a spacecraft's 3D model
(``analyses.design_checks``) on one page.

The checks run in a worker thread when Check is pressed (a mesh model can
take seconds): fields of view, thrusters and plumes, the mass budget with
maturity margins, and the launcher envelope, each in its table, with the
findings above them (the same findings the Problems panel lists). Save...
writes the record (JSON) and each table (CSV) with its provenance.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import export_log
from .data_table import DataTable, Row
from .theme import set_role
from .value_sheet import NoteList, ValueSheet
from .widgets import ComboBox

STIFFNESS_NOTE = ("Launcher compatibility here is geometry, mass and centre of mass only: stiffness and "
                  "fundamental frequencies need a structural model and are not checked.")


class _Worker(QThread):
    finished_ok = Signal(object)  # DesignReport
    failed = Signal(str)

    def __init__(self, sc, base_dir, parent=None):
        super().__init__(parent)
        self._sc, self._base_dir = sc, base_dir

    def run(self) -> None:
        from ..analyses.design_checks import design_checks

        try:
            self.finished_ok.emit(design_checks(self._sc, base_dir=self._base_dir))
        except Exception as exc:  # noqa: BLE001 -- shown on the page, not raised in the thread
            self.failed.emit(f"{type(exc).__name__}: {exc}")


def _group(title: str, table: DataTable) -> QGroupBox:
    group = QGroupBox(title)
    QVBoxLayout(group).addWidget(table)
    group.setVisible(False)
    return group


class DesignChecksWidget(QWidget):
    """The Design checks page."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._scenario = None
        self._base_dir: Path | None = None
        self._worker: _Worker | None = None
        self.report = None
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Spacecraft"))
        self.spacecraft_combo = ComboBox()
        top.addWidget(self.spacecraft_combo, 1)
        self.check_button = set_role(QPushButton("Check"), variant="primary")
        self.check_button.setToolTip("Check the spacecraft's 3D model: fields of view, thrusters and plumes, mass "
                                     "budget, launcher envelope")
        self.check_button.clicked.connect(self.check)
        top.addWidget(self.check_button)
        self.save_button = QPushButton("Save...")
        self.save_button.setToolTip("Write the record (design_checks.json) and each table (CSV), each with its "
                                    "provenance, to a folder")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self._save_clicked)
        top.addWidget(self.save_button)
        layout.addLayout(top)
        self.status_label = set_role(QLabel("Inputs: the spacecraft's 3D model (Scenario › 3D Model...): its "
                                            "mounted equipment, stowed configuration, maturity categories and "
                                            "launcher."), tone="secondary")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self.findings_label = NoteList("finding", empty="No design finding.")
        layout.addWidget(self.findings_label)
        self.fov_table = DataTable("No mounted sensor, camera or antenna with a field of view.")
        self.thruster_table = DataTable("No thruster with a position and a direction.")
        self.plume_table = DataTable("No thruster with a plume half-angle.")
        self.mass_table = DataTable("No mass.")
        self.launcher_table = DataTable("Every part is inside the envelope.")
        self.fov_group = _group("Field of view obstruction", self.fov_table)
        self.thruster_group = _group("Thruster authority (beginning and end of life)", self.thruster_table)
        self.plume_group = _group("Plume impingement (geometry only)", self.plume_table)
        self.mass_group = _group("Mass budget", self.mass_table)
        self.launcher_group = _group("Launcher envelope", self.launcher_table)
        for group in (self.fov_group, self.thruster_group, self.plume_group, self.mass_group, self.launcher_group):
            layout.addWidget(group)
        # Under each table, its sums and its verdict, a value per row.
        self.mass_sheet = ValueSheet()
        self.mass_group.layout().addWidget(self.mass_sheet)
        self.launcher_sheet = ValueSheet()
        self.launcher_group.layout().addWidget(self.launcher_sheet)
        self.notes_label = NoteList("note", [STIFFNESS_NOTE])
        layout.addWidget(self.notes_label)
        layout.addStretch(1)
        self._update_enabled()

    def set_scenario(self, scenario, base_dir: Path | None = None) -> None:
        self._scenario, self._base_dir = scenario, base_dir
        current = self.spacecraft_combo.currentText()
        names = [sc.name for sc in scenario.spacecraft] if scenario is not None else []
        if names != [self.spacecraft_combo.itemText(i) for i in range(self.spacecraft_combo.count())]:
            self.spacecraft_combo.clear()
            self.spacecraft_combo.addItems(names)
            if current in names:
                self.spacecraft_combo.setCurrentText(current)
        self._update_enabled()

    def _update_enabled(self) -> None:
        self.check_button.setEnabled(self._scenario is not None and self.spacecraft_combo.count() > 0
                                     and self._worker is None)

    def _spacecraft(self):
        name = self.spacecraft_combo.currentText()
        return next((sc for sc in self._scenario.spacecraft if sc.name == name), None) if self._scenario else None

    def check(self) -> None:
        sc = self._spacecraft()
        if sc is None or self._worker is not None:
            return
        self.status_label.setText(f"Checking {sc.name}...")
        self._worker = _Worker(sc, self._base_dir, self)
        self._worker.finished_ok.connect(self._show)
        self._worker.failed.connect(self._show_error)
        self._worker.finished.connect(self._worker_done)
        self._update_enabled()
        self._worker.start()

    def wait_for_worker(self, timeout_ms: int = 60000) -> None:
        if self._worker is not None:
            self._worker.wait(timeout_ms)

    def _worker_done(self) -> None:
        self._worker = None
        self._update_enabled()

    def _show_error(self, message: str) -> None:
        self.status_label.setText(f"The checks could not run: {message}")

    def _show(self, report) -> None:
        self.report = report
        findings = report.findings()
        self.findings_label.set_notes(findings)
        rows = report.fov.rows() if report.fov is not None else []
        self.fov_table.set_table(("Item", "Configuration", "Field of view [deg]", "Blocked [%]", "+- [%]",
                                  "Blocking parts"),
                                 [Row((r["item"], r["configuration"], f"{r['field_of_view_deg']:g}",
                                       f"{r['blocked_percent']:.1f}", f"{r['standard_error_percent']:.1f}",
                                       r["blocking_parts"])) for r in rows], numeric=(2, 3, 4), stretch=5)
        self.fov_group.setVisible(report.fov is not None)
        authority = report.authority
        self.thruster_table.set_table(("Thruster", "Thrust [N]", "Torque, beginning of life [N*m]",
                                       "Torque, end of life [N*m]", "Arm moves [mm]"),
                                      [Row((r["thruster"], f"{r['thrust_n']:g}",
                                            " ".join(f"{v:.4g}" for v in r["torque_bol_n_m"]),
                                            " ".join(f"{v:.4g}" for v in r["torque_eol_n_m"]),
                                            f"{1000.0 * r['arm_change_m']:.1f}"))
                                       for r in (authority.rows() if authority is not None else [])],
                                      numeric=(1, 4), stretch=2)
        self.thruster_group.setVisible(authority is not None)
        if authority is not None:
            self.thruster_group.setTitle(f"Thruster authority: rank {authority.rank('bol')} of 6 at the beginning "
                                         f"of life, {authority.rank('eol')} at the end")
        self.plume_table.set_table(("Thruster", "Half-angle [deg]", "Cone meeting parts [%]", "Parts"),
                                   [Row((p.thruster, f"{p.half_angle_deg:g}", f"{100.0 * p.blocked_fraction:.1f}",
                                         ", ".join(p.by_part))) for p in report.plumes], numeric=(1, 2), stretch=3)
        self.plume_group.setVisible(bool(report.plumes))
        mass = report.mass
        self.mass_table.set_table(("Item", "Subsystem", "Maturity", "Basic [kg]", "Growth [%]", "Growth [kg]"),
                                  [Row((r["item"], r["subsystem"], r["maturity"], f"{r['basic_mass_kg']:.2f}",
                                        f"{r['growth_percent']:g}", f"{r['growth_kg']:.2f}"),
                                       tooltips={4: r["column"]}) for r in mass.rows()], numeric=(3, 4, 5), stretch=0)
        self.mass_group.setVisible(True)
        self.mass_group.setTitle(f"Mass budget ({mass.policy})")
        rows = [("Basic dry mass", f"{mass.basic_dry_kg:.2f}", "kg"), ("+ Growth", f"{mass.growth_kg:.2f}", "kg"),
                ("+ System margin", f"{mass.system_margin_kg:.2f}", "kg"),
                ("+ Propellant", f"{mass.propellant_kg:.2f}", "kg"), ("= Launch mass", f"{mass.launch_mass_kg:.2f}", "kg")]
        if mass.mass_limit_kg is not None:
            rows += [("Launch mass limit", f"{mass.mass_limit_kg:g}", "kg"), ("Headroom", f"{mass.headroom_kg:.2f}", "kg")]
        self.mass_sheet.set_rows(rows)
        self.mass_sheet.note_label.setText("" if mass.mass_limit_kg is None else
                                           f"Limit from {mass.limit_source or 'no source given'}.")
        self.mass_sheet.note_label.setVisible(mass.mass_limit_kg is not None)
        check = report.launcher
        self.launcher_table.set_table(("Part", "Outside [mm]", "Where"),
                                      [Row((p.part, f"{1000.0 * p.distance_m:.0f}", p.where))
                                       for p in (check.protrusions if check is not None else [])], numeric=(1,),
                                      stretch=2)
        self.launcher_group.setVisible(check is not None)
        if check is not None:
            rows = [("Envelope", check.envelope, ""), ("Configuration", check.configuration, ""),
                    ("Parts outside", "none" if check.fits else f"{len(check.protrusions)}", ""),
                    ("Faceting error, at most", f"{1000.0 * check.largest_faceting_error_m:.2f}", "mm")]
            if check.mass_kg is not None:
                rows += [("Centre of mass above the separation plane", f"{check.com_height_m:.3f}", "m"),
                         ("Centre of mass off the axis", f"{check.com_lateral_m:.3f}", "m")]
            self.launcher_sheet.set_rows(rows)
            self.launcher_sheet.note_label.setText(f"Envelope from {check.source or 'no source given'}.")
            self.launcher_sheet.note_label.setVisible(True)
        else:
            self.launcher_sheet.set_rows([])
        notes = [f"field of view not checked: {item}: {why}" for item, why in
                 (report.fov.skipped if report.fov is not None else [])]
        notes += [f"plume not checked: {item}: {why}" for item, why in report.plume_skipped]
        for part in (authority, mass, check):
            notes += list(getattr(part, "notes", []) or [])
        self.notes_label.set_notes(notes + [STIFFNESS_NOTE])
        self.status_label.setText(f"{report.spacecraft}: checked with {report.samples} rays per cone.")
        self.save_button.setEnabled(True)

    def _save_clicked(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Save the design checks to a folder")
        if folder:
            self.save(Path(folder))

    def save(self, folder: Path) -> list[Path]:
        """The record and the tables in ``folder``; returns the files written."""
        from ..analyses import records

        record = records.design_record(self._scenario, self.report)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "design_checks.json"
        records.write_record(path, record)
        written = [path, *records.write_tables(records.design_tables(self.report), folder, record)]
        export_log.record("design_checks", folder)
        self.status_label.setText(f"Saved {len(written)} file(s) to {folder}")
        return written
