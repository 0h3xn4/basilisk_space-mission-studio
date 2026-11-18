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
background thread (seconds per case; sizing the heaters takes longer).
The page then has a tab each (decision T-41) for the temperatures with a
node's operating and survival bands, a node's heat flows by kind with the
orbit-average heat flows, the summary per case with the margins, the
heaters and radiators, the 3D model in its temperatures, the studies and
the notes; the findings go to the Problems panel, with one line here.
Limit violations go to the Timeline, and Results › 3D View can colour the
spacecraft by a case's temperatures (``analysis_changed``). **Save...**
writes the record, the tables and series (CSV) and the plots (SVG and
PNG), each with its provenance.

The plots on screen are made at their view's size and in the theme
(decision T-40) by a worker (:class:`_PlotRenderer`), again when the view
is resized (once the size holds still) and when the theme changes. The
files keep the fixed 900 x 420 picture of T-31: ``temperature_svg`` and
``flow_svg`` are that text, made when they are read."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, Qt, QThread, Signal
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QCheckBox,
    QCompleter,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from . import export_log
from .data_table import DataTable, Row
from .feedback import report
from .svg_plot import SvgPlotView, render_image, render_size
from .theme import SPACE, current_theme, on_change, set_role
from .theme.svg_plot_style import svg_plot_style
from .value_sheet import NoteList
from .widgets import ComboBox, EmptyState, TabWidget

_ALL_NODES = "All nodes"
_MODEL_HEIGHT_PX = 240  # [px] the 3D model's least height (the page fits a 720 px window)
#: The tabs, in their order (T-41).
TABS = ("Temperatures", "Heat flows", "Summary", "Heaters and radiators", "3D model", "Studies", "Notes")
_DRAWING = "Drawing the plot..."


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


def _section(title: str, content: QWidget, note: QWidget | None = None) -> QWidget:
    """A titled part of a tab: its section title, then ``content``. A
    surface, not a frame (no group box)."""
    section = QWidget()
    layout = QVBoxLayout(section)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(SPACE["sm"])
    title_label = set_role(QLabel(title), role="section-title")
    layout.addWidget(title_label)
    if note is not None:
        layout.addWidget(note)
    layout.addWidget(content, 1)
    section.title_label = title_label
    return section


def _page() -> tuple[QWidget, QVBoxLayout]:
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, SPACE["md"], 0, 0)
    layout.setSpacing(SPACE["md"])
    return page, layout


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


class _StudyWorker(QThread):
    """A sweep, a sensitivity or a Monte Carlo (thermal.sweeps) off the GUI thread."""

    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, job, parent=None):
        super().__init__(parent)
        self._job = job

    def run(self) -> None:
        try:
            self.finished_ok.emit(self._job())
        except (Exception, SystemExit) as exc:  # noqa: BLE001 -- shown on the page, never a crashed thread
            self.failed.emit(str(exc))


class _PlotRenderer(QThread):
    """The screen copies of the plots shown (T-40), off the GUI thread:
    each plot's SVG at its view's size in the theme's style, and its
    picture (``svg_plot.render_image``)."""

    rendered = Signal(int, object)  # the request's number, {"temperature": (svg, QImage), "flow": ... or None}
    failed = Signal(int, str)

    def __init__(self, number: int, case, node: str | None, sizes: dict, ratio: float, mode: str, parent=None):
        super().__init__(parent)
        self._number, self._case, self._node, self._sizes, self._ratio, self._mode = (number, case, node, sizes,
                                                                                      ratio, mode)

    def run(self) -> None:
        from ..thermal import plots

        try:
            style = svg_plot_style(self._mode)
            node = self._node
            size = render_size(self._sizes["temperature"])
            svg = plots.temperature_svg(self._case, [node] if node else None, node, size.width(), size.height(),
                                        style=style)
            pictures = {"temperature": (svg, render_image(svg, size, self._ratio, style["background"])),
                        "flow": None}
            if node:
                size = render_size(self._sizes["flow"])
                svg = plots.heat_flow_svg(self._case, node, size.width(), size.height(), style=style)
                pictures["flow"] = (svg, render_image(svg, size, self._ratio, style["background"]))
        except Exception as exc:  # noqa: BLE001 -- a plot that cannot be drawn says so; the analysis stays
            self.failed.emit(self._number, str(exc))
            return
        self.rendered.emit(self._number, pictures)


class ThermalWidget(QWidget):
    """Run › Thermal."""

    events_changed = Signal(list)  # the thermal limit events of the analysis shown (engine.events.Event)
    monte_carlo_saved = Signal(str)  # the folder a thermal Monte Carlo was saved in (the Monte Carlo view opens it)
    analysis_changed = Signal(object, object)  # the analysis shown (or None) and the run's result it belongs to
    problems_changed = Signal()  # problem_rows() changed
    problems_requested = Signal()  # "Show in Problems": the main window shows the Problems panel
    show_in_3d_view = Signal(str)  # a case to show on Results › 3D View

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._scenario = self._result = self._base_dir = None
        self.analysis = None
        self._worker: _ThermalWorker | None = None
        self._study_worker: _StudyWorker | None = None
        self._plot_worker: _PlotRenderer | None = None
        self._plot_number = 0  # the newest plot request; an older picture is dropped
        self._plot_pending = False  # a request came while the worker was busy
        self._export_cache: tuple = (None, "", "")  # (case and node, temperature SVG, heat-flow SVG) as the files
        layout = QVBoxLayout(self)
        layout.setSpacing(SPACE["sm"])
        top = QHBoxLayout()
        top.setSpacing(SPACE["sm"])
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
        self._toolbar = top  # add_tool_button: the window's Open in Own Window button goes last
        layout.addLayout(top)

        status = QHBoxLayout()
        status.setSpacing(SPACE["sm"])
        self.status_label = set_role(QLabel(""), tone="secondary")
        self.status_label.setWordWrap(True)
        self.status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        status.addWidget(self.status_label, 1)
        self.findings_label = set_role(QLabel(""), tone="caution")
        status.addWidget(self.findings_label)
        self.problems_button = set_role(QPushButton("Show in Problems"), variant="ghost")
        self.problems_button.setToolTip("The thermal findings (limit violations, shading, the checks) are in the "
                                        "Problems panel")
        self.problems_button.clicked.connect(self.problems_requested.emit)
        status.addWidget(self.problems_button)
        layout.addLayout(status)

        self.choices = QWidget()  # the case and node every tab shows
        choices = QHBoxLayout(self.choices)
        choices.setContentsMargins(0, 0, 0, 0)
        choices.setSpacing(SPACE["sm"])
        choices.addWidget(QLabel("Case"))
        self.case_combo = ComboBox()
        self.case_combo.setSizeAdjustPolicy(ComboBox.SizeAdjustPolicy.AdjustToContents)
        self.case_combo.setToolTip("The case the plots, the tables, the 3D model and the studies show")
        self.case_combo.currentTextChanged.connect(lambda _name: self._show_case())
        choices.addWidget(self.case_combo)
        choices.addWidget(QLabel("Node"))
        self.node_combo = ComboBox()
        self.node_combo.setSizeAdjustPolicy(ComboBox.SizeAdjustPolicy.AdjustToContents)
        self.node_combo.setToolTip("All nodes, or one with its operating and survival ranges and its heat flows")
        self.node_combo.currentTextChanged.connect(lambda _name: self._show_plots())
        choices.addWidget(self.node_combo)
        choices.addStretch(1)
        self.save_svg_button = QPushButton("Save SVG...")
        self.save_svg_button.setToolTip("Save the temperature plot of the case and node shown as SVG (900 x 420, "
                                        "with its provenance)")
        self.save_svg_button.clicked.connect(lambda: self._save_plot("svg"))
        self.save_png_button = QPushButton("Save PNG...")
        self.save_png_button.setToolTip("Save the temperature plot of the case and node shown as PNG (900 x 420 at "
                                        "twice the pixels, with its provenance)")
        self.save_png_button.clicked.connect(lambda: self._save_plot("png"))
        choices.addWidget(self.save_svg_button)
        choices.addWidget(self.save_png_button)
        layout.addWidget(self.choices)

        self.stack = QStackedWidget()
        self.empty_state = EmptyState("No thermal result")
        self.stack.addWidget(self.empty_state)
        self.tabs = TabWidget()
        self.tabs.setObjectName("thermalViews")
        self.stack.addWidget(self.tabs)
        layout.addWidget(self.stack, 1)
        self._build_temperatures()
        self._build_heat_flows()
        self._build_summary()
        self._build_heaters()
        self._build_model_view()
        self._build_studies()
        self._build_notes()
        self.tabs.currentChanged.connect(self._on_tab)
        on_change(self._on_theme_changed)
        self._clear()

    # -- the tabs -----------------------------------------------------------------
    def add_tool_button(self, button: QWidget) -> None:
        """A button of the window's at the end of the page's top row (Open in
        Own Window: it moves with the page, gui.breakout)."""
        self._toolbar.addWidget(button)

    def _build_temperatures(self) -> None:
        page, layout = _page()
        self.temperature_plot = SvgPlotView("Temperatures", _DRAWING)
        self.temperature_plot.size_settled.connect(self._request_plots)
        layout.addWidget(self.temperature_plot, 1)
        self.temperature_page = page
        self.tabs.addTab(page, TABS[0])

    def _build_heat_flows(self) -> None:
        page, layout = _page()
        self.flow_plot = SvgPlotView("Heat flows", _DRAWING)
        self.flow_plot.size_settled.connect(self._request_plots)
        layout.addWidget(self.flow_plot, 3)
        # One compact line until a node is picked, so the table below gets the room (UI audit UI-21).
        self.flow_empty = EmptyState("No node picked", "The plot shows the heat flows into one node, by kind: pick "
                                     "it in the Node list above.", compact=True)
        layout.addWidget(self.flow_empty, 0)
        self.tables: dict[str, tuple[QWidget, DataTable]] = {}
        table = DataTable("No heat flow in this case.")
        self.tables["flows"] = (_section("Orbit-average heat flows [W] (positive in)", table), table)
        layout.addWidget(self.tables["flows"][0], 2)
        self.flow_page = page
        self.tabs.addTab(page, TABS[1])

    def _build_summary(self) -> None:
        page, layout = _page()
        self.summary_table = DataTable("No case solved.")
        self.summary_group = _section("Summary per case", self.summary_table)
        layout.addWidget(self.summary_group, 1)
        self.summary_page = page
        self.tabs.addTab(page, TABS[2])

    def _build_heaters(self) -> None:
        page, layout = _page()
        for key, title in (("heaters", "Heaters"), ("radiators", "Radiators")):
            table = DataTable(f"No {key} in this case.")
            self.tables[key] = (_section(title, table), table)
            layout.addWidget(self.tables[key][0], 1)
        self.heaters_empty = EmptyState("No heaters or radiators",
                                        "The thermal model has no heater and no face marked as a radiator (Spacecraft "
                                        "› 3D model › Thermal model).")
        layout.addWidget(self.heaters_empty, 1)
        self.heaters_page = page
        self.tabs.addTab(page, TABS[3])

    _COLOUR_MODES = ("Hottest over the run", "Coldest over the run", "Mean over the run", "At a time")

    def _build_model_view(self) -> None:
        """The 3D model coloured by temperature (thermal Phase 2): each part
        in its node's colour, for the case shown. Its web view is made the
        first time the tab is shown."""
        page, layout = _page()
        self.model_group = QWidget()  # the tab's content (the name of 2.11.0's group)
        model_layout = QVBoxLayout(self.model_group)
        model_layout.setContentsMargins(0, 0, 0, 0)
        model_layout.setSpacing(SPACE["sm"])
        row = QHBoxLayout()
        row.setSpacing(SPACE["sm"])
        self.colour_combo = ComboBox()
        self.colour_combo.addItems(self._COLOUR_MODES)
        self.colour_combo.setToolTip("Which temperature of each node colours its parts")
        self.colour_combo.currentTextChanged.connect(lambda _text: self._show_model_colours())
        row.addWidget(self.colour_combo)
        self.time_slider = QSlider(Qt.Orientation.Horizontal)
        self.time_slider.setToolTip("The time shown, with 'At a time'")
        self.time_slider.valueChanged.connect(lambda _value: self._show_model_colours())
        row.addWidget(self.time_slider, 1)
        self.time_label = set_role(QLabel(""), role="mono")
        row.addWidget(self.time_label)
        self.view_3d_button = QPushButton("Show on 3D View")
        self.view_3d_button.setToolTip("Colour the spacecraft on Results › 3D View by this case's temperatures, as "
                                       "the run plays back")
        self.view_3d_button.clicked.connect(lambda: self.show_in_3d_view.emit(self.case_combo.currentText()))
        row.addWidget(self.view_3d_button)
        model_layout.addLayout(row)
        self.model_view = None  # gui.model_view_widget.ModelViewWidget, made when the tab is first shown
        layout.addWidget(self.model_group, 1)
        self.model_page = page
        self.tabs.addTab(page, TABS[4])

    def _build_studies(self) -> None:
        """Sweeps, sensitivity and the thermal Monte Carlo of the case shown
        (thermal.sweeps, T-36): solved on the same fluxes, no new run."""
        page, layout = _page()
        self.studies_group = QWidget()
        studies = QVBoxLayout(self.studies_group)
        studies.setContentsMargins(0, 0, 0, 0)
        studies.setSpacing(SPACE["sm"])
        row = QHBoxLayout()
        row.setSpacing(SPACE["sm"])
        row.addWidget(QLabel("Parameter"))
        self.sweep_path = QLineEdit()
        self.sweep_path.setPlaceholderText("faces[radiator].absorptance")
        self.sweep_path.setToolTip("A parameter of the thermal model by its path, as in a case's overrides")
        row.addWidget(self.sweep_path, 2)
        row.addWidget(QLabel("Values"))
        self.sweep_values = QLineEdit()
        self.sweep_values.setPlaceholderText("0.1, 0.2, 0.3")
        row.addWidget(self.sweep_values, 1)
        self.sweep_button = QPushButton("Sweep")
        self.sweep_button.setToolTip("Solve the case at each value")
        self.sweep_button.clicked.connect(self.run_sweep)
        row.addWidget(self.sweep_button)
        studies.addLayout(row)
        row = QHBoxLayout()
        row.setSpacing(SPACE["sm"])
        self.sensitivity_button = QPushButton("Sensitivity")
        self.sensitivity_button.setToolTip("Move each optic, conductance, dissipation, heater power, the sunlight and "
                                           "the infrared 10 % up and down, one at a time, and rank their effect")
        self.sensitivity_button.clicked.connect(self.run_sensitivity)
        row.addWidget(self.sensitivity_button)
        self.monte_carlo_button = QPushButton("Monte Carlo...")
        self.monte_carlo_button.setToolTip("Run the thermal model's Monte Carlo (its monte_carlo section) and show "
                                           "it in the Monte Carlo view")
        self.monte_carlo_button.clicked.connect(self._monte_carlo_clicked)
        row.addWidget(self.monte_carlo_button)
        row.addStretch(1)
        studies.addLayout(row)
        self.study_label = set_role(QLabel(""), tone="secondary")
        self.study_label.setWordWrap(True)
        studies.addWidget(self.study_label)
        self.study_table = DataTable("No study yet.")
        studies.addWidget(self.study_table, 1)
        self.study_empty = EmptyState("No study yet", "Sweep a parameter, rank the parameters by their effect, or "
                                      "run the thermal Monte Carlo of the case shown.")
        studies.addWidget(self.study_empty, 1)
        self._show_study_table(False)
        layout.addWidget(self.studies_group, 1)
        self.studies_page = page
        self.tabs.addTab(page, TABS[5])

    def _build_notes(self) -> None:
        page, layout = _page()
        self.notes_list = NoteList("note", empty="No notes.")
        layout.addWidget(self.notes_list)
        layout.addStretch(1)
        self.notes_page = page
        self.tabs.addTab(page, TABS[6])

    def _on_tab(self, _index: int) -> None:
        if self.tabs.currentWidget() is self.model_page:
            self._show_model_colours()

    def part_temperatures(self) -> dict:
        """``{part: degC}`` for the case shown, by the colour mode: each part
        takes its node's temperature."""
        case = self._case()
        if case is None:
            return {}
        mode = self.colour_combo.currentText()
        index = min(self.time_slider.value(), len(case.time_s) - 1)
        values = {}
        for node in self.analysis.prepared.spacecraft.thermal.nodes:
            series = case.temperature_c(node.name)
            value = {self._COLOUR_MODES[0]: series.max(), self._COLOUR_MODES[1]: series.min(),
                     self._COLOUR_MODES[2]: series.mean()}.get(mode, series[index])
            values.update({part: float(value) for part in node.parts})
        return values

    def _show_model_colours(self) -> None:
        case = self._case()
        at_time = self.colour_combo.currentText() == self._COLOUR_MODES[3]
        self.time_slider.setEnabled(at_time and case is not None)
        if case is None:
            self.time_label.setText("")
            return
        index = min(self.time_slider.value(), len(case.time_s) - 1)
        self.time_label.setText(f"{case.time_s[index] / 3600.0:.2f} h" if at_time else "")
        if self.tabs.currentWidget() is not self.model_page:
            return  # drawn when the tab is shown: the web view is made only then
        if self.model_view is None:
            from .model_view_widget import ModelViewWidget

            self.model_view = ModelViewWidget()
            self.model_view.setMinimumHeight(_MODEL_HEIGHT_PX)
            self.model_group.layout().addWidget(self.model_view, 1)
        self.model_view.show_model(self.analysis.prepared.geometry.derived, temperatures=self.part_temperatures())

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
        had = self.analysis is not None
        self.analysis = None
        self._export_cache = (None, "", "")
        self._plot_number += 1  # a picture still being made is not wanted
        ready = self._result is not None and self.spacecraft_combo.count() > 0
        self.status_label.setText("Press Solve to solve the thermal cases on this run." if ready else
                                  "Run a scenario whose spacecraft has a thermal model (Spacecraft › 3D model › "
                                  "Thermal model) to solve it here.")
        if ready:
            self.empty_state.set_text("No thermal result", "Press Solve to solve the thermal cases of "
                                      f"{self.spacecraft_combo.currentText()} on this run.")
        else:
            self.empty_state.set_text("No thermal result", "Run a scenario whose spacecraft has a thermal model "
                                      "(Spacecraft › 3D model › Thermal model), then solve it here.")
        self.stack.setCurrentWidget(self.empty_state)
        self.choices.setVisible(False)
        for group, _table in self.tables.values():
            group.setVisible(False)
        self.temperature_plot.clear()
        self.flow_plot.clear()
        self.flow_plot.setVisible(False)
        self.flow_empty.setVisible(True)
        self.findings_label.setVisible(False)
        self.problems_button.setVisible(False)
        self.notes_list.set_notes([])
        self.save_button.setEnabled(False)
        self.solve_button.setEnabled(ready and self._worker is None)
        self.events_changed.emit([])
        if had:
            self.problems_changed.emit()
        self.analysis_changed.emit(None, None)

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
        for worker in (self._worker, self._study_worker, self._plot_worker):
            if worker is not None:
                worker.wait(timeout_ms)

    # -- studies --------------------------------------------------------------

    def _study(self, text: str, job, done) -> None:
        if self._study_worker is not None or self.analysis is None:
            return
        self.study_label.setText(text)
        for button in (self.sweep_button, self.sensitivity_button, self.monte_carlo_button):
            button.setEnabled(False)
        self._study_worker = _StudyWorker(job, self)
        self._study_worker.finished_ok.connect(done)
        self._study_worker.failed.connect(lambda message: self.study_label.setText(message))
        self._study_worker.finished.connect(self._study_done)
        self._study_worker.start()

    def _study_done(self) -> None:
        self._study_worker = None
        self.sweep_button.setEnabled(True)
        self.sensitivity_button.setEnabled(True)
        self.monte_carlo_button.setEnabled(self.analysis is not None
                                           and self.analysis.prepared.spacecraft.thermal.monte_carlo is not None)

    def _case_config(self):
        from ..thermal import cases as thermal_cases

        name = self.case_combo.currentText()
        return next(c for c in thermal_cases.cases_of(self.analysis.prepared.spacecraft.thermal) if c.name == name)

    def run_sweep(self) -> None:
        from ..thermal import sweeps

        path = self.sweep_path.text().strip()
        try:
            values = [float(v) for v in self.sweep_values.text().replace(";", ",").split(",") if v.strip()]
        except ValueError:
            self.study_label.setText("Values: numbers separated by commas.")
            return
        if not path or not values:
            self.study_label.setText("Give a parameter and its values.")
            return
        prepared, case = self.analysis.prepared, self._case_config()
        self._study(f"Sweeping {path}...", lambda: sweeps.sweep(prepared, case, path, values),
                    lambda points: self._show_sweep(path, case.name, points))

    def _show_study_table(self, shown: bool) -> None:
        self.study_table.setVisible(shown)
        self.study_empty.setVisible(not shown)

    def _show_sweep(self, path: str, case: str, points) -> None:
        nodes = [n.name for n in points[0].summary]
        rows = [{"value": p.value, **{f"{n.name} min_c": n.min_c for n in p.summary},
                 **{f"{n.name} max_c": n.max_c for n in p.summary}} for p in points]
        columns = ["value"] + [f"{n} {e}_c" for n in nodes for e in ("min", "max")]
        self._fill(self.study_table, [{c: r[c] for c in columns} for r in rows])
        self._show_study_table(True)
        self.study_label.setText(f"Sweep of {path} in the {case} case: each node's extremes at each value.")

    def run_sensitivity(self) -> None:
        from ..thermal import sweeps

        prepared, case = self.analysis.prepared, self._case_config()
        self._study("Varying each parameter up and down by 10 %...",
                    lambda: sweeps.sensitivity(prepared, case), lambda found: self._show_sensitivity(case.name, found))

    def _show_sensitivity(self, case: str, found) -> None:
        rows, notes = found
        table = []
        for row in rows:
            node = max(row.changes, key=lambda n: max(abs(v) for v in row.changes[n]))
            d_min, d_max, d_mean = row.changes[node]
            table.append({"parameter": row.path, "value": row.value, "step": row.step,
                          "largest change_k": row.largest_k, "node": node, "min change_k": d_min,
                          "max change_k": d_max, "mean change_k": d_mean})
        self._fill(self.study_table, table)
        self._show_study_table(bool(table))
        left_out = f" Left out: {'; '.join(notes)}." if notes else ""
        self.study_label.setText(f"Sensitivity in the {case} case: each parameter 10 % up and down (optics kept "
                                 f"within 0 to 1), the change between the two, largest first.{left_out}")

    def _monte_carlo_clicked(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Save the thermal Monte Carlo to a folder")
        if folder:
            self.run_monte_carlo(Path(folder))

    def run_monte_carlo(self, folder: Path) -> None:
        from ..engine import monte_carlo_results
        from ..thermal import sweeps

        prepared = self.analysis.prepared
        config = prepared.spacecraft.thermal.monte_carlo

        def job():
            batch = sweeps.monte_carlo(prepared, config)
            monte_carlo_results.save(batch, folder)
            return batch

        self._study(f"Running {config.runs} thermal Monte Carlo runs...", job,
                    lambda batch: self._monte_carlo_done(folder, batch))

    def _monte_carlo_done(self, folder: Path, batch) -> None:
        self.study_label.setText(f"Thermal Monte Carlo: {len(batch.runs)} runs saved in {folder}; the Monte Carlo "
                                 "view shows them.")
        self.monte_carlo_saved.emit(str(folder))

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
        self._export_cache = (None, "", "")
        cases = analysis.cases
        solved = [f"{c.name}: periodic after {c.solution.periodic.orbits} orbits"
                  if c.solution.periodic is not None else f"{c.name}: from the initial temperatures" for c in cases]
        env = analysis.prepared.environment
        self.status_label.setText("Solved " + "; ".join(solved) + f". Beta angle over the run: "
                                  f"{float(env.beta_deg.min()):.1f} to {float(env.beta_deg.max()):.1f} deg.")
        tables = records.tables(analysis)
        self._fill(self.summary_table, tables["thermal_summary"])
        findings = analysis.findings()
        self.findings_label.setText(f"{len(findings)} finding{'' if len(findings) == 1 else 's'}")
        self.findings_label.setVisible(bool(findings))
        self.problems_button.setVisible(bool(findings))
        notes = [f"{c.name}: {note}" for c in cases for note in c.notes]
        notes += [f"{c.name}: energy balance closes to {abs(c.solution.energy_residual_j):.3g} J of "
                  f"{c.solution.energy_throughput_j:.3g} J; half the step changes it by "
                  f"{c.solution.step_check_k:.3g} K" for c in cases if c.solution.step_check_k is not None]
        self.notes_list.set_notes(notes)
        self.case_combo.blockSignals(True)
        self.case_combo.clear()
        self.case_combo.addItems([c.name for c in cases])
        self.case_combo.blockSignals(False)
        self.choices.setVisible(bool(cases))
        self.stack.setCurrentWidget(self.tabs if cases else self.empty_state)
        self._show_study_table(False)
        self.study_label.setText("")
        from ..thermal import sweeps

        self.sweep_path.setCompleter(QCompleter(sweeps.default_parameters(analysis.prepared.spacecraft.thermal), self))
        self.monte_carlo_button.setEnabled(analysis.prepared.spacecraft.thermal.monte_carlo is not None)
        self.save_button.setEnabled(True)
        self._show_case()
        self.events_changed.emit(analysis.events())
        self.problems_changed.emit()
        self.analysis_changed.emit(analysis, self._result)

    def problem_rows(self) -> list:
        """The findings of the analysis shown as Problems rows ``(severity,
        text, shown text)``: limit violations, the shading warning, a start
        that did not converge, a step that is too long."""
        if self.analysis is None:
            return []
        return [("warning", str(finding), str(finding)) for finding in self.analysis.findings()]

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
        self.time_slider.blockSignals(True)
        self.time_slider.setRange(0, len(case.time_s) - 1)
        self.time_slider.blockSignals(False)
        tables = records.tables(self.analysis)
        for key, name in (("flows", "thermal_heat_flows"), ("heaters", "thermal_heaters"),
                          ("radiators", "thermal_radiators")):
            rows = [r for r in tables.get(name, []) if r["case"] == case.name]
            group, table = self.tables[key]
            group.setVisible(bool(rows))
            if rows:
                self._fill(table, [{k: v for k, v in r.items() if k != "case"} for r in rows])
        self.heaters_empty.setVisible(self.tables["heaters"][0].isHidden() and self.tables["radiators"][0].isHidden())
        self._show_plots()
        self._show_model_colours()

    def _node(self, case) -> str | None:
        node = self.node_combo.currentText()
        return node if node in case.network.names else None

    def _show_plots(self) -> None:
        case = self._case()
        if case is None:
            return
        node = self._node(case)
        self.flow_plot.setVisible(bool(node))
        self.flow_empty.setVisible(not node)
        self._request_plots()

    # -- the plots: the files' text, and the screen's pictures (T-40) ---------------

    def _exported(self) -> tuple[str, str]:
        """The plots shown as the files have them (T-31's defaults), made
        once per case and node."""
        case = self._case()
        if case is None:
            return "", ""
        node = self._node(case)
        key = (id(case), node)
        if self._export_cache[0] != key:
            from ..thermal import plots

            self._export_cache = (key, plots.temperature_svg(case, [node] if node else None, node),
                                  plots.heat_flow_svg(case, node) if node else "")
        return self._export_cache[1], self._export_cache[2]

    @property
    def temperature_svg(self) -> str:
        """The temperature plot shown, as Save SVG writes it ("" without one)."""
        return self._exported()[0]

    @property
    def flow_svg(self) -> str:
        """The heat-flow plot of the node shown, as the files have it ("" for all nodes)."""
        return self._exported()[1]

    def _request_plots(self) -> None:
        """Make the screen's pictures of the case and node shown, at the
        views' sizes and in the theme, in the worker; one request at a
        time, the newest wins."""
        case = self._case()
        if case is None:
            return
        self._plot_number += 1
        self.temperature_plot.waiting = _DRAWING
        if self._plot_worker is not None:
            self._plot_pending = True
            return
        sizes = {"temperature": self.temperature_plot.size(), "flow": self.flow_plot.size()}
        worker = _PlotRenderer(self._plot_number, case, self._node(case), sizes, self.devicePixelRatioF(),
                               current_theme(), self)
        worker.rendered.connect(self._on_rendered)
        worker.failed.connect(self._on_render_failed)
        worker.finished.connect(lambda w=worker: self._plot_done(w))
        self._plot_worker = worker
        worker.start()

    def _plot_done(self, worker) -> None:
        if self._plot_worker is worker:
            self._plot_worker = None
        worker.deleteLater()
        if self._plot_pending:
            self._plot_pending = False
            self._request_plots()

    def _on_rendered(self, number: int, pictures: dict) -> None:
        if number != self._plot_number or self.analysis is None:
            return  # an older request's, or the analysis is gone
        self.temperature_plot.set_image(*pictures["temperature"])
        if pictures["flow"] is not None:
            self.flow_plot.set_image(*pictures["flow"])

    def _on_render_failed(self, number: int, message: str) -> None:
        if number == self._plot_number:
            self.temperature_plot.waiting = f"The plot could not be drawn: {message}"
            self.temperature_plot.clear()

    def _on_theme_changed(self, _mode: str) -> None:
        self._request_plots()

    @staticmethod
    def _fill(table: DataTable, rows: list[dict]) -> None:
        columns = list(rows[0]) if rows else []
        table.set_table([heading(c) for c in columns], [Row(tuple(_text(r.get(c)) for c in columns)) for r in rows],
                        numeric=range(1, len(columns)), stretch=0)

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
