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
"""Run › Thermal: the thermal analysis of a run (``thermal.analysis``) for
a spacecraft with a thermal model. **Solve** solves its cases on a
background thread (seconds per case; sizing the heaters takes longer);
the page then shows the summary per case with the margins, the
temperatures with a node's operating and survival bands, a node's heat
flows by kind, the orbit-average heat flows, the heaters and radiators,
and the findings. Limit violations go to the Timeline. **Save...** writes
the record, the tables and series (CSV) and the plots (SVG and PNG), each
with its provenance."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, QThread, Signal
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QCheckBox,
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
from .feedback import report
from .theme import set_role
from .value_sheet import NoteList
from .widgets import ComboBox

_ALL_NODES = "All nodes"
_PLOT_HEIGHT_PX = 380


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


_UNITS = (("_wh", "W·h"), ("_m2", "m²"), ("_w", "W"), ("_c", "°C"), ("_k", "K"))


def heading(key: str) -> str:
    """A table column's heading from its record key: "cold_margin_k" ->
    "Cold margin [K]"."""
    for suffix, unit in _UNITS:
        if key.endswith(suffix):
            return f"{key[:-len(suffix)].replace('_', ' ').capitalize()} [{unit}]"
    return key.replace("_", " ").capitalize()


def write_png(svg: str, path, scale: float = 2.0) -> Path:
    """Render ``svg`` (thermal.plots) to a PNG at ``path``."""
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    size = renderer.defaultSize()
    image = QImage(int(size.width() * scale), int(size.height() * scale), QImage.Format.Format_ARGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    renderer.render(painter, QRectF(0, 0, image.width(), image.height()))
    painter.end()
    if not image.save(str(path), "PNG"):
        raise OSError(f"could not write {path}")
    return Path(path)


class _ThermalWorker(QThread):
    progress = Signal(str)
    finished_ok = Signal(object)  # thermal.analysis.ThermalAnalysis
    failed = Signal(str)

    def __init__(self, scenario, result, name, base_dir, size_heaters, parent=None):
        super().__init__(parent)
        self._args = (scenario, result, name, base_dir, size_heaters)

    def run(self) -> None:
        from ..thermal import analysis

        scenario, result, name, base_dir, size_heaters = self._args
        try:
            self.finished_ok.emit(analysis.analyse(scenario, result, name, base_dir, size_heaters=size_heaters,
                                                   progress=self.progress.emit))
        except analysis.ThermalAnalysisError as exc:
            self.failed.emit(str(exc))
        except (Exception, SystemExit) as exc:  # noqa: BLE001 -- shown on the page, never a crashed thread
            self.failed.emit(f"thermal analysis failed: {exc}")


class ThermalWidget(QWidget):
    """Run › Thermal."""

    events_changed = Signal(list)  # the thermal limit events of the analysis shown (engine.events.Event)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._scenario = self._result = self._base_dir = None
        self.analysis = None
        self._worker: _ThermalWorker | None = None
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Spacecraft"))
        self.spacecraft_combo = ComboBox()
        self.spacecraft_combo.currentTextChanged.connect(lambda _name: self._clear())
        top.addWidget(self.spacecraft_combo, 1)
        self.size_check = QCheckBox("Size the heaters")
        self.size_check.setChecked(True)
        self.size_check.setToolTip("Find each heater's least constant power that holds its 'on' temperature in "
                                   "every case (takes longer)")
        top.addWidget(self.size_check)
        self.solve_button = QPushButton("Solve")
        self.solve_button.setToolTip("Solve the spacecraft's thermal cases on the last run")
        self.solve_button.clicked.connect(self.solve)
        top.addWidget(self.solve_button)
        self.save_button = QPushButton("Save...")
        self.save_button.setToolTip("Write the record (thermal.json), the tables and series (CSV) and the plots (SVG "
                                    "and PNG), each with its provenance, to a folder")
        self.save_button.clicked.connect(self._save_clicked)
        top.addWidget(self.save_button)
        layout.addLayout(top)
        self.status_label = set_role(QLabel(""), tone="secondary")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self.findings_list = NoteList("finding")
        layout.addWidget(self.findings_list)

        self.summary_group = QGroupBox("Summary per case")
        self.summary_table = DataTable()
        QVBoxLayout(self.summary_group).addWidget(self.summary_table)
        layout.addWidget(self.summary_group)

        self.plot_group = QGroupBox("Temperatures and heat flows")
        plot_layout = QVBoxLayout(self.plot_group)
        choices = QHBoxLayout()
        choices.addWidget(QLabel("Case"))
        self.case_combo = ComboBox()
        self.case_combo.currentTextChanged.connect(lambda _name: self._show_case())
        choices.addWidget(self.case_combo)
        choices.addWidget(QLabel("Node"))
        self.node_combo = ComboBox()
        self.node_combo.setToolTip("All nodes, or one with its operating and survival ranges and its heat flows")
        self.node_combo.currentTextChanged.connect(lambda _name: self._show_plots())
        choices.addWidget(self.node_combo)
        choices.addStretch(1)
        self.save_svg_button = QPushButton("Save SVG...")
        self.save_svg_button.clicked.connect(lambda: self._save_plot("svg"))
        self.save_png_button = QPushButton("Save PNG...")
        self.save_png_button.clicked.connect(lambda: self._save_plot("png"))
        choices.addWidget(self.save_svg_button)
        choices.addWidget(self.save_png_button)
        plot_layout.addLayout(choices)
        self.temperature_plot = QSvgWidget()
        self.temperature_plot.setMinimumHeight(_PLOT_HEIGHT_PX)
        plot_layout.addWidget(self.temperature_plot)
        self.flow_plot = QSvgWidget()
        self.flow_plot.setMinimumHeight(_PLOT_HEIGHT_PX)
        plot_layout.addWidget(self.flow_plot)
        layout.addWidget(self.plot_group)
        self.temperature_svg = self.flow_svg = ""

        self.tables: dict[str, tuple[QGroupBox, DataTable]] = {}
        for key, title in (("flows", "Orbit-average heat flows [W] (positive in)"), ("heaters", "Heaters"),
                           ("radiators", "Radiators")):
            group = QGroupBox(title)
            table = DataTable()
            QVBoxLayout(group).addWidget(table)
            layout.addWidget(group)
            self.tables[key] = (group, table)
        self.notes_list = NoteList("note")
        layout.addWidget(self.notes_list)
        layout.addStretch(1)
        self._clear()

    @staticmethod
    def has_thermal(scenario) -> bool:
        return scenario is not None and any(getattr(sc, "thermal", None) is not None for sc in scenario.spacecraft)

    def set_run(self, scenario, result, base_dir=None) -> None:
        """The run whose spacecraft can be solved (None: nothing)."""
        self._scenario, self._result, self._base_dir = scenario, result, base_dir
        names = [sc.name for sc in scenario.spacecraft if sc.thermal is not None] if scenario else []
        self.spacecraft_combo.blockSignals(True)
        self.spacecraft_combo.clear()
        self.spacecraft_combo.addItems(names)
        self.spacecraft_combo.blockSignals(False)
        self._clear()

    def _clear(self) -> None:
        self.analysis = None
        ready = self._result is not None and self.spacecraft_combo.count() > 0
        self.status_label.setText("Press Solve to solve the thermal cases on this run." if ready else
                                  "Run a scenario whose spacecraft has a thermal model (Spacecraft › 3D model › "
                                  "Thermal model) to solve it here.")
        for widget in (self.summary_group, self.plot_group, *(group for group, _table in self.tables.values())):
            widget.setVisible(False)
        self.findings_list.set_notes([])
        self.notes_list.set_notes([])
        self.save_button.setEnabled(False)
        self.solve_button.setEnabled(ready and self._worker is None)
        self.events_changed.emit([])

    # -- solving ------------------------------------------------------------

    def solve(self) -> None:
        name = self.spacecraft_combo.currentText()
        if self._worker is not None or self._result is None or not name:
            return
        self._worker = _ThermalWorker(self._scenario, self._result, name, self._base_dir, self.size_check.isChecked(),
                                      self)
        self._worker.progress.connect(lambda text: self.status_label.setText(text.capitalize() + "..."))
        self._worker.finished_ok.connect(self.show_analysis)
        self._worker.failed.connect(self._failed)
        self._worker.finished.connect(self._worker_done)
        self.solve_button.setEnabled(False)
        self.status_label.setText("Building the fluxes on every facet...")
        self._worker.start()

    def wait_for_worker(self, timeout_ms: int = 300000) -> None:
        if self._worker is not None:
            self._worker.wait(timeout_ms)

    def _worker_done(self) -> None:
        self._worker = None
        self.solve_button.setEnabled(self._result is not None and self.spacecraft_combo.count() > 0)

    def _failed(self, message: str) -> None:
        self.status_label.setText(message)

    # -- showing ------------------------------------------------------------

    def show_analysis(self, analysis) -> None:
        """Show ``analysis`` (a thermal.analysis.ThermalAnalysis)."""
        from ..thermal import records

        self.analysis = analysis
        cases = analysis.cases
        solved = [f"{c.name}: periodic after {c.solution.periodic.orbits} orbits"
                  if c.solution.periodic is not None else f"{c.name}: from the initial temperatures" for c in cases]
        self.status_label.setText("Solved " + "; ".join(solved) + ".")
        tables = records.tables(analysis)
        self._fill(self.summary_table, tables["thermal_summary"])
        self.summary_group.setVisible(True)
        self.findings_list.set_notes(analysis.findings())
        notes = [f"{c.name}: {note}" for c in cases for note in c.notes]
        notes += [f"{c.name}: energy balance closes to {abs(c.solution.energy_residual_j):.3g} J of "
                  f"{c.solution.energy_throughput_j:.3g} J; half the step changes it by "
                  f"{c.solution.step_check_k:.3g} K" for c in cases if c.solution.step_check_k is not None]
        self.notes_list.set_notes(notes)
        self.case_combo.blockSignals(True)
        self.case_combo.clear()
        self.case_combo.addItems([c.name for c in cases])
        self.case_combo.blockSignals(False)
        self.plot_group.setVisible(bool(cases))
        self.save_button.setEnabled(True)
        self._show_case()
        self.events_changed.emit(analysis.events())

    def _case(self):
        if self.analysis is None or not self.case_combo.currentText():
            return None
        return self.analysis.case(self.case_combo.currentText())

    def _show_case(self) -> None:
        from ..thermal import records

        case = self._case()
        if case is None:
            return
        current = self.node_combo.currentText()
        self.node_combo.blockSignals(True)
        self.node_combo.clear()
        self.node_combo.addItems([_ALL_NODES, *case.network.names])
        self.node_combo.setCurrentIndex(max(self.node_combo.findText(current), 0))
        self.node_combo.blockSignals(False)
        tables = records.tables(self.analysis)
        for key, name in (("flows", "thermal_heat_flows"), ("heaters", "thermal_heaters"),
                          ("radiators", "thermal_radiators")):
            rows = [r for r in tables.get(name, []) if r["case"] == case.name]
            group, table = self.tables[key]
            group.setVisible(bool(rows))
            if rows:
                self._fill(table, [{k: v for k, v in r.items() if k != "case"} for r in rows])
        self._show_plots()

    def _show_plots(self) -> None:
        from ..thermal import plots

        case = self._case()
        if case is None:
            return
        node = self.node_combo.currentText()
        node = node if node in case.network.names else None
        self.temperature_svg = plots.temperature_svg(case, [node] if node else None, node)
        self.temperature_plot.load(QByteArray(self.temperature_svg.encode("utf-8")))
        self.flow_svg = plots.heat_flow_svg(case, node) if node else ""
        self.flow_plot.setVisible(bool(node))
        if node:
            self.flow_plot.load(QByteArray(self.flow_svg.encode("utf-8")))

    @staticmethod
    def _fill(table: DataTable, rows: list[dict]) -> None:
        columns = list(rows[0]) if rows else []
        table.set_table([heading(c) for c in columns], [Row(tuple(_text(r.get(c)) for c in columns)) for r in rows],
                        numeric=range(1, len(columns)), stretch=0)
        table.fit_rows()

    # -- saving -------------------------------------------------------------

    def _record(self) -> dict:
        from ..thermal import records

        return records.record(self._scenario, self.analysis, self._result)

    def _save_clicked(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Save the thermal analysis to a folder")
        if folder:
            try:
                written = self.save(Path(folder))
            except OSError as exc:
                report(self, f"Could not write {folder}: {exc}")
                return
            report(self, f"Saved {len(written)} files to {folder}", kind="success")

    def save(self, folder: Path) -> list[Path]:
        """The record, the tables and series and the plots in ``folder``."""
        from ..engine import analysis_records
        from ..thermal import records

        record = self._record()
        folder.mkdir(parents=True, exist_ok=True)
        written = [analysis_records.write(folder / "thermal.json", record)]
        written += records.write_tables(self.analysis, folder, record)
        written += records.write_plots(self.analysis, folder, record, png=write_png)
        export_log.record("thermal", folder)
        return written

    def _save_plot(self, fmt: str) -> None:
        if not self.temperature_svg:
            return
        case = self._case()
        node = self.node_combo.currentText()
        stem = f"thermal_{case.name}_" + ("temperature" if node == _ALL_NODES else f"{node}_temperature")
        path, _ = QFileDialog.getSaveFileName(self, f"Save the temperature plot as {fmt.upper()}",
                                              f"{stem.replace(' ', '_')}.{fmt}", f"{fmt.upper()} (*.{fmt})")
        if path:
            self.save_plot(Path(path), fmt)

    def save_plot(self, path: Path, fmt: str) -> Path:
        """The temperature plot shown, as SVG or PNG, with its provenance."""
        from .. import output_provenance
        from ..engine.analysis_records import _plain

        if fmt == "svg":
            path.write_text(self.temperature_svg, encoding="utf-8")
        else:
            write_png(self.temperature_svg, path)
        record = self._record()
        output_provenance.write_sidecar(path, dict(_plain(record["provenance"]), kind=record["kind"],
                                                   plot=path.stem, spacecraft=record["spacecraft"]))
        export_log.record("thermal", path)
        return path

