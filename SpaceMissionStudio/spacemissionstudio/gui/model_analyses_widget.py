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
"""Results › Model Analyses: a run's model analyses
(``analyses.run_analyses``) for each spacecraft that asked for them: the
disturbance-torque budget with the momentum and the sizing, the blinding,
antenna obstruction, array shading, exposure and brightness tables, and
the findings. The series themselves are in Results › Plots and the
events on the Timeline. Save... writes the record and the tables with
their provenance."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QGroupBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from . import export_log
from .data_table import DataTable, Row
from .theme import set_role
from .value_sheet import NoteList, ValueSheet, ValueTable
from .widgets import ComboBox

_TABLES = (("disturbance_torques", "Disturbance torques"), ("blinding", "Sensor blinding"),
           ("antenna_obstruction", "Antenna obstruction during passes"), ("array_shading", "Array shading"),
           ("surface_exposure", "Surface exposure (atomic oxygen, sun hours)"),
           ("brightness", "Brightness from the ground"))


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


class ModelAnalysesWidget(QWidget):
    """The Model Analyses tab of Results."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._scenario = None
        self._result = None
        self._base_dir = None  # set_run
        self.report = None
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Spacecraft"))
        self.spacecraft_combo = ComboBox()
        self.spacecraft_combo.currentTextChanged.connect(lambda _name: self._show())
        top.addWidget(self.spacecraft_combo, 1)
        self.save_button = QPushButton("Save...")
        self.save_button.setToolTip("Write the record (model_analyses.json) and each table (CSV), each with its "
                                    "provenance, to a folder")
        self.save_button.clicked.connect(self._save_clicked)
        top.addWidget(self.save_button)
        layout.addLayout(top)
        self.summary_label = set_role(QLabel(""), tone="secondary")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)
        # The momentum the disturbances build up, per body axis (never a sentence of numbers).
        self.momentum_table = ValueTable("Momentum [N·m·s]", ["", "x", "y", "z"], numeric=(1, 2, 3))
        self.momentum_sheet = ValueSheet()
        self.momentum_table.layout().addWidget(self.momentum_sheet)
        self.momentum_table.setVisible(False)
        layout.addWidget(self.momentum_table)
        self.findings_label = NoteList("finding")
        layout.addWidget(self.findings_label)
        self.tables: dict = {}
        self.groups: dict = {}
        for key, title in _TABLES:
            table = DataTable()
            group = QGroupBox(title)
            QVBoxLayout(group).addWidget(table)
            layout.addWidget(group)
            self.tables[key], self.groups[key] = table, group
        self.notes_label = NoteList("note")
        layout.addWidget(self.notes_label)
        layout.addStretch(1)

    @staticmethod
    def has_analyses(scenario) -> bool:
        return scenario is not None and any(sc.model_analyses is not None for sc in scenario.spacecraft)

    def set_run(self, scenario, result, base_dir=None) -> None:
        """The run's scenario and results (None: nothing to show), and the
        folder its model's relative mesh paths are read from."""
        self._scenario, self._result, self._base_dir = scenario, result, base_dir
        names = [sc.name for sc in scenario.spacecraft if sc.model_analyses is not None] if scenario else []
        self.spacecraft_combo.blockSignals(True)
        self.spacecraft_combo.clear()
        self.spacecraft_combo.addItems(names)
        self.spacecraft_combo.blockSignals(False)
        self._show()

    def _show(self) -> None:
        from ..analyses import run_analyses

        name = self.spacecraft_combo.currentText()
        sc = next((s for s in self._scenario.spacecraft if s.name == name), None) if self._scenario else None
        self.report = run_analyses.report(self._result, self._scenario, sc, self._base_dir) if sc and self._result else None
        self.save_button.setEnabled(self.report is not None)
        if self.report is None:
            self.summary_label.setText("Run a scenario whose spacecraft set model analyses to see them here.")
            for group in self.groups.values():
                group.setVisible(False)
            self.momentum_table.setVisible(False)
            self.findings_label.set_notes([])
            self.notes_label.set_notes([])
            return
        tables = self.report.tables()
        for key, table in self.tables.items():
            rows = tables.get(key, [])
            self.groups[key].setVisible(bool(rows))
            if rows:
                columns = list(rows[0])
                table.set_table(columns, [Row(tuple(_text(r.get(c)) for c in columns)) for r in rows],
                                numeric=range(1, len(columns)), stretch=0)
                table.fit_rows()
        budget = self.report.disturbances
        if budget is not None:
            per_orbit = budget.required_momentum_n_m_s()
            span = "per orbit" if budget.momentum_per_orbit_n_m_s is not None else "over the run"
            rows = [[f"Needed {span}"] + [f"{v:.4g}" for v in per_orbit]]
            if budget.wheel_capacity_n_m_s is not None:
                rows.append(["The wheels hold"] + [f"{v:.4g}" for v in budget.wheel_capacity_n_m_s])
            self.momentum_table.set_rows(rows)
            self.momentum_sheet.set_rows([("Largest over the run", f"{budget.momentum_max_n_m_s:.4g}", "N·m·s")])
            self.momentum_table.setVisible(True)
            self.summary_label.setText("From the disturbance torques of the run, in the body frame.")
        else:
            self.momentum_table.setVisible(False)
            self.summary_label.setText("No disturbance torques recorded (model_analyses.disturbance_torques).")
        findings = self.report.findings()
        self.findings_label.set_notes(findings)
        notes = list(self.report.notes) + (list(budget.notes) if budget is not None else [])
        self.notes_label.set_notes(notes)

    def _save_clicked(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Save the model analyses to a folder")
        if folder:
            self.save(Path(folder))

    def save(self, folder: Path) -> list[Path]:
        from ..analyses import records

        record = records.run_record(self._scenario, self.report, self._result)
        folder.mkdir(parents=True, exist_ok=True)
        written = [records.write_record(folder / "model_analyses.json", record)]
        written += records.write_tables(self.report.tables(), folder, record)
        export_log.record("model_analyses", folder)
        return written
