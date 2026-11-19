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
spacecraft by a case's temperatures (``analysis_changed``). **Save...**,
the page's one save entry point (a menu, UI audit UI-44), writes the
record, the tables and series (CSV) and the plots (SVG and PNG), each
with its provenance, or the temperature plot shown alone.

The plots on screen are made at their view's size and in the theme
(decision T-40) by a worker (:class:`_PlotRenderer`), again when the view
is resized (once the size holds still) and when the theme changes. The
files keep the fixed 900 x 420 picture of T-31: ``temperature_svg`` and
``flow_svg`` are that text, made when they are read."""

from __future__ import annotations

from pathlib import Path

import re

from PySide6.QtCore import QByteArray, QRectF, Qt, QThread, Signal
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from . import export_log, units
from .badges import StatusBadge
from .data_table import DataTable, Row
from .feedback import report
from .svg_plot import SvgPlotView, render_image, render_size
from .theme import FIELD_WIDTH, ROW_HEIGHT, SPACE, current_theme, on_change, set_role
from .theme.svg_plot_style import svg_plot_style
from .value_sheet import NoteList, ValueSheet, ValueTable
from .widgets import ComboBox, EmptyState, TabWidget, own_tooltip, set_off_reason

_ALL_NODES = "All nodes"
_MODEL_HEIGHT_PX = 240  # [px] the 3D model's least height (the page fits a 720 px window)
_FLOW_PLOT_MIN_PX = 160  # [px] the heat-flow plot's least height: the table below takes the rest (UI audit UI-21)
_UNLIMITED_PX = 16777215  # [px] Qt's QWIDGETSIZE_MAX: no height limit
#: The tabs, in their order (T-41).
TABS = ("Temperatures", "Heat flows", "Summary", "Heaters and radiators", "3D model", "Studies", "Notes")
_DRAWING = "Drawing the plot..."


def _text(value) -> str:
    if value is None:
        return "–"  # a figure the analysis does not give (a node without limits has no margin)
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


def _two_lines(text: str) -> str:
    """A heading with its unit on a second line ("Conduction\n[W]"), so a
    table of many numbers fits the page (UI audit UI-21)."""
    return text.replace(" [", "\n[")


# -- the parameters a study varies, by their labels (UI audit UI-30) ----------------------------------

#: A record kind of the thermal model (``kind[name]`` in a path) and its label.
_RECORD_KINDS = {"faces": "Face", "nodes": "Node", "conductors": "Conductor", "heat_pipes": "Heat pipe",
                 "dissipations": "Dissipation", "heaters": "Heater"}
#: A field and its label and unit (the code's spelling; ``units.label`` shows it).
_FIELDS = {"absorptance": ("absorptance", "-"), "emissivity": ("emissivity", "-"),
           "mli_effective_emittance": ("MLI effective emittance", "-"),
           "conductance_w_k": ("conductance", "W/K"), "contact_coefficient_w_m2_k": ("contact coefficient", "W/(m²·K)"),
           "power_w": ("power", "W"), "capacitance_j_k": ("heat capacity", "J/K"),
           "solar_flux_w_m2": ("solar flux", "W/m²"), "planet_ir_w_m2": ("planetary infrared", "W/m²"),
           "albedo": ("albedo", "-")}
_PATH = re.compile(r"^(?P<kind>\w+)(?:\[(?P<name>[^\]]*)\])?\.(?P<field>\w+)$")


def parameter_label(path: str) -> tuple[str, str]:
    """``(label, unit)`` of a thermal model parameter by its path, as a study
    shows it: "faces[array +y:+z].absorptance" -> ("Face array +y, side +z:
    absorptance", "-"), "environment.solar_flux_w_m2" -> ("Environment:
    solar flux", "W/m²"). The user's names stay as they are; a path this
    does not know is its own label, with no unit."""
    match = _PATH.match(path.strip())
    if match is None:
        return path, ""
    kind, name, field = match.group("kind"), match.group("name"), match.group("field")
    if kind == "environment" and name is None:
        owner = "Environment"
    elif kind in _RECORD_KINDS and name is not None:
        part, _sep, side = name.partition(":")
        owner = f"{_RECORD_KINDS[kind]} {part}" + (f", side {side}" if side else "")
    else:
        return path, ""
    text, unit = _FIELDS.get(field, (field.replace("_", " "), ""))
    return f"{owner}: {text}", unit


def parameter_text(path: str) -> str:
    """A parameter's label with its unit, as a list shows it ("Heater
    battery heater A: power [W]"; no unit for a dimensionless one)."""
    label, unit = parameter_label(path)
    return units.label(f"{label} [{unit}]") if unit else label


def _override_note(note: str) -> str:
    """A case's override as the window names it: "dissipations[avionics].power_w
    = 15.0" -> "Dissipation avionics: power set to 15.0"; anything else as it is."""
    path, sep, value = note.partition(" = ")
    if not sep or _PATH.match(path) is None or parameter_label(path)[0] == path:
        return note
    label, unit = parameter_label(path)
    value = "empty" if value in ("''", '""') else value.strip("'")
    shown = units.suffix(unit) if unit and unit != "-" else ""
    return f"{label} set to {value}{shown}"


def case_notes(cases) -> list[str]:
    """The cases' notes, each once (UI audit UI-07): a note several cases
    share names them together ("cold, cold safe mode: S 1322 W/m²; ...");
    a note that starts with its case's own name loses the repeat (the
    preset environment's note "nominal: ..." of the case nominal read
    "nominal: nominal: ..."); a preset's name of another case says so;
    units as the window writes them."""
    from ..thermal.cases import DEFAULT_CASES

    shared: dict[str, list[str]] = {}
    for case in cases:
        for note in case.notes:
            shared.setdefault(note, [])
            if case.name not in shared[note]:
                shared[note].append(case.name)
    notes = []
    for note, names in shared.items():
        head, sep, rest = note.partition(": ")
        if sep and head in names:
            note = rest
        elif sep and head in DEFAULT_CASES:
            note = f"the {head} environment, {rest}"
        notes.append(f"{', '.join(names)}: {units.in_text(_override_note(note))}")
    return notes


# -- a node's temperatures against its limits (UI audit UI-07) ---------------------------------------

#: status: (words, icon, icon ink, text ink)
_STATUS = {
    "below survival": ("Below survival", "octagon-alert", "status.critical", "status.critical.text"),
    "above survival": ("Above survival", "octagon-alert", "status.critical", "status.critical.text"),
    "below operating": ("Below operating", "triangle-alert", "status.caution", "status.caution.text"),
    "above operating": ("Above operating", "triangle-alert", "status.caution", "status.caution.text"),
    "within": ("Within limits", "circle-check", "status.normal", "status.normal.text"),
    "none": ("No limits", "circle-minus", "text.secondary", "text.secondary"),
}


def node_status(node) -> str:
    """A key of :data:`_STATUS` for a ``thermal.results.NodeSummary``: the
    worst of its range against the survival, then the operating limits."""
    for limits, kind in ((node.survival_c, "survival"), (node.operating_c, "operating")):
        if limits is None:
            continue
        if node.min_c < limits[0]:
            return f"below {kind}"
        if node.max_c > limits[1]:
            return f"above {kind}"
    return "none" if node.operating_c is None and node.survival_c is None else "within"


def _range(limits) -> str:
    return "–" if limits is None else f"{limits[0]:g} to {limits[1]:g}"


def summary_rows(analysis) -> tuple[list[str], list[Row]]:
    """Run › Thermal › Summary: per case and node the extremes, the mean, the
    operating range, the margins and the status, a word behind its icon
    (never the colour alone)."""
    headers = ["Case", "Node", "Min [°C]", "Max [°C]", "Mean [°C]", "Operating [°C]", "Cold margin [K]",
               "Hot margin [K]", "Status"]
    rows = []
    for case in analysis.cases:
        for node in case.summary:
            words, mark, ink, text_ink = _STATUS[node_status(node)]
            cells = (case.name, node.name, _text(node.min_c), _text(node.max_c), _text(node.mean_c),
                     _range(node.operating_c), _text(node.cold_margin_k), _text(node.hot_margin_k), words)
            tip = f"Operating {_range(node.operating_c)} °C; survival {_range(node.survival_c)} °C"
            rows.append(Row(cells, tooltips={8: tip, 5: tip}, plain=frozenset({1, 8}),
                            marks={8: (mark, ink, text_ink)}))
    return [_two_lines(h) for h in headers], rows


def solution_rows(analysis) -> list[list[str]]:
    """Run › Thermal › Notes: per case how it started and the solution's
    checks, one value per cell (they were sentences, UI audit UI-07)."""
    rows = []
    for case in analysis.cases:
        solution = case.solution
        periodic = solution.periodic
        start = ("Initial temperatures" if periodic is None else
                 "Periodic" if periodic.converged else "Not periodic")
        rows.append([case.name, start, "–" if periodic is None else str(periodic.orbits),
                     f"{abs(solution.energy_residual_j):.3g}", f"{solution.energy_throughput_j:.3g}",
                     "–" if solution.step_check_k is None else f"{solution.step_check_k:.3g}"])
    return rows


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


class _Section(QWidget):
    """A titled part of a tab (:func:`_section`). ``wanted`` [px], when set,
    is the content's height it asks for (Heat flows' table: its rows)."""

    wanted = 0

    def sizeHint(self):  # noqa: N802 -- Qt's name
        hint = super().sizeHint()
        if self.wanted:
            hint.setHeight(self.title_label.sizeHint().height() + self.layout().spacing() + self.wanted)
        return hint


def _section(title: str, content: QWidget, note: QWidget | None = None) -> QWidget:
    """A titled part of a tab: its section title, then ``content``. A
    surface, not a frame (no group box)."""
    section = _Section()
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

    def __init__(self, number: int, case, node: str | None, sizes: dict, ratio: float, mode: str, parent=None,
                 time_unit: str = "h"):
        super().__init__(parent)
        self._number, self._case, self._node, self._sizes, self._ratio, self._mode = (number, case, node, sizes,
                                                                                      ratio, mode)
        self._time_unit = time_unit  # thermal.plots.TIME_UNITS: Settings > Plot units (UI audit B10)

    def run(self) -> None:
        from ..thermal import plots

        try:
            style = svg_plot_style(self._mode)
            node = self._node
            size = render_size(self._sizes["temperature"])
            svg = plots.temperature_svg(self._case, [node] if node else None, node, size.width(), size.height(),
                                        style=style, time_unit=self._time_unit)
            pictures = {"temperature": (svg, render_image(svg, size, self._ratio, style["background"])),
                        "flow": None}
            if node:
                size = render_size(self._sizes["flow"])
                svg = plots.heat_flow_svg(self._case, node, size.width(), size.height(), style=style,
                                          time_unit=self._time_unit)
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
        self.spacecraft_combo.setSizeAdjustPolicy(ComboBox.SizeAdjustPolicy.AdjustToContents)
        self.spacecraft_combo.setMaximumWidth(FIELD_WIDTH["choice"])  # a drop-down list's width (UI audit UI-26)
        self.spacecraft_combo.currentTextChanged.connect(lambda _name: self._clear())
        top.addWidget(self.spacecraft_combo)
        self.size_check = QCheckBox("Size the heaters")
        self.size_check.setChecked(True)
        self.size_check.setToolTip("Find each heater's least constant power that holds its 'on' temperature in "
                                   "every case (takes longer)")
        top.addWidget(self.size_check)
        self.solve_button = QPushButton("Solve")
        self.solve_button.setToolTip("Solve the spacecraft's thermal cases on the last run")
        self.solve_button.clicked.connect(self.solve)
        top.addWidget(self.solve_button)
        # One entry point for every file the page writes (UI audit UI-44): it had three buttons.
        self.save_button = QPushButton("Save...")
        self.save_button.setToolTip("Save the thermal analysis: everything to a folder, or the temperature plot "
                                    "shown as SVG or PNG, each with its provenance")
        self.save_menu = QMenu(self.save_button)
        self.save_menu.setToolTipsVisible(True)
        self.save_all_action = self.save_menu.addAction("Everything to a folder...")
        self.save_all_action.setToolTip("The record (thermal.json), the tables and series (CSV) and the plots (SVG "
                                        "and PNG), each with its provenance")
        self.save_all_action.triggered.connect(self._save_clicked)
        self.save_menu.addSeparator()
        self.save_svg_action = self.save_menu.addAction("Temperature plot as SVG...")
        self.save_svg_action.setToolTip("The temperature plot of the case and node shown, 900 x 420, with its "
                                        "provenance")
        self.save_svg_action.triggered.connect(lambda: self._save_plot("svg"))
        self.save_png_action = self.save_menu.addAction("Temperature plot as PNG...")
        self.save_png_action.setToolTip("The temperature plot of the case and node shown, 900 x 420 at twice the "
                                        "pixels, with its provenance")
        self.save_png_action.triggered.connect(lambda: self._save_plot("png"))
        self.save_button.setMenu(self.save_menu)
        top.addWidget(self.save_button)
        top.addStretch(1)
        self._toolbar = top  # add_tool_button: the window's Open in Own Window button goes last
        layout.addLayout(top)

        # The case and node every tab shows, then one short status line and the findings (UI audit UI-07, UI-44).
        status = QHBoxLayout()
        status.setSpacing(SPACE["sm"])
        self.choices = QWidget()
        choices = QHBoxLayout(self.choices)
        choices.setContentsMargins(0, 0, 0, 0)
        choices.setSpacing(SPACE["sm"])
        self.case_label = QLabel("Case")
        choices.addWidget(self.case_label)
        self.case_combo = ComboBox()
        self.case_combo.setSizeAdjustPolicy(ComboBox.SizeAdjustPolicy.AdjustToContents)
        self.case_combo.setMaximumWidth(FIELD_WIDTH["choice"])
        self.case_combo.setToolTip("The case the plots, the tables, the 3D model and the studies show")
        self.case_combo.currentTextChanged.connect(lambda _name: self._show_case())
        self.case_label.setBuddy(self.case_combo)
        choices.addWidget(self.case_combo)
        self.node_label = QLabel("Node")
        choices.addSpacing(SPACE["sm"])
        choices.addWidget(self.node_label)
        self.node_combo = ComboBox()
        self.node_combo.setSizeAdjustPolicy(ComboBox.SizeAdjustPolicy.AdjustToContents)
        self.node_combo.setMaximumWidth(FIELD_WIDTH["choice"])
        self.node_combo.setToolTip("All nodes, or one with its operating and survival ranges and its heat flows")
        self.node_combo.currentTextChanged.connect(lambda _name: self._show_plots())
        self.node_label.setBuddy(self.node_combo)
        choices.addWidget(self.node_combo)
        status.addWidget(self.choices)
        self.status_label = set_role(QLabel(""), tone="secondary")
        self.status_label.setWordWrap(True)
        self.status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        status.addWidget(self.status_label, 1)
        self.findings_label = StatusBadge("caution")  # the count behind its icon, never the colour alone
        status.addWidget(self.findings_label)
        self.problems_button = QPushButton("Show in Problems")  # a command: a framed button, not a link (UI-44)
        self.problems_button.setToolTip("Open the Problems panel (Ctrl+J): the thermal findings (limit violations, "
                                        "shading, the checks) are listed there")
        self.problems_button.clicked.connect(self.problems_requested.emit)
        status.addWidget(self.problems_button)
        layout.addLayout(status)

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
        # The plot takes what the table leaves, never less than its least height (UI audit UI-21).
        self.flow_plot.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
        self.flow_plot.setMinimumHeight(_FLOW_PLOT_MIN_PX)
        layout.addWidget(self.flow_plot, 1)
        # One compact line until a node is picked, so the table below gets the room (UI audit UI-21).
        self.flow_empty = EmptyState("No node picked", "The plot shows the heat flows into one node, by kind: pick "
                                     "it in the Node list above.", compact=True)
        layout.addWidget(self.flow_empty, 0)
        self.tables: dict[str, tuple[QWidget, DataTable]] = {}
        table = DataTable("No heat flow in this case.")
        table.set_fit_width()
        self.tables["flows"] = (_section("Orbit-average heat flows [W] (positive in)", table), table)
        self.tables["flows"][0].title_label.setToolTip("A kind of heat flow that is zero for every node of the case "
                                                       "is hidden; the header's context menu shows it again")
        layout.addWidget(self.tables["flows"][0], 0)
        self.flow_page = page
        self.tabs.addTab(page, TABS[1])

    def _fit_flow_table(self) -> None:
        """Heat flows: the table asks to be as tall as its rows, and the plot
        takes what is left, never less than its least height (UI audit
        UI-21: the table showed two rows at 1280 x 720); short of room the
        table gives way first, down to two rows. With no plot shown, the
        table takes the tab."""
        section, table = self.tables["flows"]
        layout = self.flow_page.layout()
        view = table.view
        header = max(view.horizontalHeader().height(), view.horizontalHeader().sizeHint().height())
        table.setMinimumHeight(header + 2 * ROW_HEIGHT + 2 * view.frameWidth())
        if self.flow_plot.isHidden():
            layout.setStretchFactor(section, 1)
            section.wanted = 0
            table.setMaximumHeight(_UNLIMITED_PX)
        else:
            layout.setStretchFactor(section, 0)
            rows = sum(view.rowHeight(r) for r in range(table.row_count())) if table.row_count() else ROW_HEIGHT
            bar = view.horizontalScrollBar()
            section.wanted = header + rows + 2 * view.frameWidth() + (
                bar.sizeHint().height() if bar.maximum() > 0 else 0)
            table.setMaximumHeight(section.wanted)
        section.updateGeometry()

    def _build_summary(self) -> None:
        page, layout = _page()
        self.summary_table = DataTable("No case solved.")
        self.summary_table.set_fit_width()
        self.summary_group = _section("Summary per case", self.summary_table)
        layout.addWidget(self.summary_group, 1)
        self.summary_page = page
        self.tabs.addTab(page, TABS[2])

    def _build_heaters(self) -> None:
        page, layout = _page()
        for key, title in (("heaters", "Heaters"), ("radiators", "Radiators")):
            table = DataTable(f"No {key} in this case.")
            table.set_fit_width()
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
        colour_label = QLabel("Colour by")
        row.addWidget(colour_label)
        self.colour_combo = ComboBox()
        colour_label.setBuddy(self.colour_combo)
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
        (thermal.sweeps, T-36): solved on the same fluxes, no new run. The
        parameter is chosen by its label from the thermal model's own
        (UI audit UI-30); "Other parameter" takes any path, as a case's
        overrides do."""
        page, layout = _page()
        self.studies_group = QWidget()
        studies = QVBoxLayout(self.studies_group)
        studies.setContentsMargins(0, 0, 0, 0)
        studies.setSpacing(SPACE["sm"])
        row = QHBoxLayout()
        row.setSpacing(SPACE["sm"])
        parameter_label_ = QLabel("Parameter")
        row.addWidget(parameter_label_)
        self.sweep_parameter = ComboBox()
        self.sweep_parameter.setMaximumWidth(FIELD_WIDTH["choice"])
        # Short enough not to widen the page (its own window on a small screen); a long label ends in
        # "…", the whole of it in the list and the tooltip.
        self.sweep_parameter.setMinimumContentsLength(12)
        self.sweep_parameter.currentIndexChanged.connect(lambda _index: self._parameter_chosen())
        parameter_label_.setBuddy(self.sweep_parameter)
        row.addWidget(self.sweep_parameter)
        self.sweep_path = QLineEdit()  # "Other parameter": a path, as in a case's overrides
        self.sweep_path.setPlaceholderText("environment.albedo")
        self.sweep_path.setToolTip("A parameter of the thermal model by its path, as in a case's overrides")
        self.sweep_path.setMaximumWidth(FIELD_WIDTH["choice"])
        self.sweep_path.setAccessibleName("Parameter path")
        row.addWidget(self.sweep_path, 1)
        values_label = QLabel("Values")
        row.addSpacing(SPACE["sm"])
        row.addWidget(values_label)
        self.sweep_values = QLineEdit()
        self.sweep_values.setPlaceholderText("0.1, 0.2, 0.3")
        self.sweep_values.setToolTip("The values to solve the case at, separated by commas, in the parameter's unit")
        self.sweep_values.setMaximumWidth(FIELD_WIDTH["number"])
        values_label.setBuddy(self.sweep_values)
        row.addWidget(self.sweep_values, 1)
        self.sweep_unit = set_role(QLabel(""), tone="secondary")
        row.addWidget(self.sweep_unit)
        self.sweep_button = QPushButton("Sweep")
        self.sweep_button.setToolTip("Solve the case at each value")
        self.sweep_button.clicked.connect(self.run_sweep)
        row.addWidget(self.sweep_button)
        row.addStretch(1)
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
        self.study_table.set_fit_width()
        studies.addWidget(self.study_table, 1)
        self.study_empty = EmptyState("No study yet", "Sweep a parameter, rank the parameters by their effect, or "
                                      "run the thermal Monte Carlo of the case shown.")
        studies.addWidget(self.study_empty, 1)
        self._show_study_table(False)
        self._set_parameters([])
        layout.addWidget(self.studies_group, 1)
        self.studies_page = page
        self.tabs.addTab(page, TABS[5])

    _OTHER_PARAMETER = "Other parameter, by its path"

    def _set_parameters(self, paths: list[str]) -> None:
        """The parameters the Parameter list offers: each by its label and
        unit, its path on hover; then "Other parameter"."""
        self.sweep_parameter.blockSignals(True)
        self.sweep_parameter.clear()
        for path in paths:
            self.sweep_parameter.addItem(parameter_text(path), path)
            self.sweep_parameter.setItemData(self.sweep_parameter.count() - 1, path, Qt.ItemDataRole.ToolTipRole)
        self.sweep_parameter.addItem(self._OTHER_PARAMETER, None)
        self.sweep_parameter.setItemData(self.sweep_parameter.count() - 1, "Any parameter of the thermal model by "
                                         "its path, as in a case's overrides", Qt.ItemDataRole.ToolTipRole)
        self.sweep_parameter.blockSignals(False)
        self._parameter_chosen()

    def _parameter_chosen(self) -> None:
        path = self.sweep_parameter.currentData()
        self.sweep_path.setVisible(path is None)
        unit = parameter_label(path)[1] if path else ""
        self.sweep_unit.setText(units.shown(unit) if unit and unit != "-" else "")
        own_tooltip(self.sweep_parameter, f"{path}: its path in the thermal model" if path else
                    "The parameter to sweep, by its label; its path in the thermal model on hover")

    def choose_parameter(self, path: str) -> None:
        """Sweep ``path``: its entry in the Parameter list, else Other with the path."""
        index = self.sweep_parameter.findData(path)
        if index < 0:
            index = self.sweep_parameter.count() - 1
            self.sweep_path.setText(path)
        self.sweep_parameter.setCurrentIndex(index)

    def sweep_parameter_path(self) -> str:
        """The path of the parameter chosen ("" for none)."""
        path = self.sweep_parameter.currentData()
        return (path if path is not None else self.sweep_path.text()).strip()

    def _build_notes(self) -> None:
        """Each case's start and solution checks in a table, the run's beta
        angle in a sheet, then the notes, each once (UI audit UI-07: they
        were sentences of numbers, "nominal: nominal: ...")."""
        page, layout = _page()
        # The table and the sheet do not set the page's least width (the page's own window on a small
        # screen, where Windows' wider fonts made it wider than the screen); the page has no scroll
        # area of its own, so below the table's width its right edge is cut.
        values_box = QWidget()
        values = QHBoxLayout(values_box)
        values.setContentsMargins(0, 0, 0, 0)
        values.setSpacing(SPACE["xl"])
        self.solution_table = ValueTable("Solution per case", ["Case", "Start", "Orbits", "Energy residual [J]",
                                                               "Energy throughput [J]", "Half-step change [K]"],
                                         numeric=(2, 3, 4, 5))
        self.solution_table.setToolTip("Start: from the orbit-periodic state, or the initial temperatures. Energy "
                                       "residual: how far the energy balance is from closing, of the energy "
                                       "throughput. Half-step change: how much half the time step changes the "
                                       "temperatures.")
        values.addWidget(self.solution_table, 0, Qt.AlignmentFlag.AlignTop)
        self.environment_sheet = ValueSheet("Over the run")
        values.addWidget(self.environment_sheet, 0, Qt.AlignmentFlag.AlignTop)
        values.addStretch(1)
        values_box.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Maximum)
        self.notes_values = values_box
        layout.addWidget(values_box)
        self.notes_title = set_role(QLabel("Notes"), role="heading")
        layout.addWidget(self.notes_title)
        self.notes_list = NoteList("note", empty="No notes.", fold_after=3)
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
        set_off_reason(self.time_slider, at_time and case is not None,
                       "Off: the colours show the whole run. Choose At a time in Colour by to pick a time.")
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
        self.status_label.setText("")  # the empty state says what to do
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
        self.solution_table.set_rows([])
        self.environment_sheet.set_rows([])
        set_off_reason(self.save_button, False, "Off: nothing is solved yet. Press Solve first.")
        self._enable_solve()
        self._enable_studies()
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
        set_off_reason(self.solve_button, False, "Off: the cases are being solved.")
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
            set_off_reason(button, False, "Off: a study is running. It ends by itself.")
        self._study_worker = _StudyWorker(job, self)
        self._study_worker.finished_ok.connect(done)
        self._study_worker.failed.connect(lambda message: self.study_label.setText(message))
        self._study_worker.finished.connect(self._study_done)
        self._study_worker.start()

    def _study_done(self) -> None:
        self._study_worker = None
        self._enable_studies()

    def _enable_studies(self) -> None:
        """The study buttons on, or off with why (UI audit UI-30)."""
        solved = self.analysis is not None
        for button in (self.sweep_button, self.sensitivity_button):
            set_off_reason(button, solved, "Off: nothing is solved yet. Press Solve first.")
        monte_carlo = solved and self.analysis.prepared.spacecraft.thermal.monte_carlo is not None
        set_off_reason(self.monte_carlo_button, monte_carlo,
                       "Off: the thermal model has no Monte Carlo section. Add its runs and dispersions in "
                       "Spacecraft › 3D model › Thermal model › Cases, then run and solve again." if solved else
                       "Off: nothing is solved yet. Press Solve first.")

    def _case_config(self):
        from ..thermal import cases as thermal_cases

        name = self.case_combo.currentText()
        return next(c for c in thermal_cases.cases_of(self.analysis.prepared.spacecraft.thermal) if c.name == name)

    def run_sweep(self) -> None:
        from ..thermal import sweeps

        path = self.sweep_parameter_path()
        try:
            values = [float(v) for v in self.sweep_values.text().replace(";", ",").split(",") if v.strip()]
        except ValueError:
            self.study_label.setText("Values: numbers separated by commas.")
            return
        if not path or not values:
            self.study_label.setText("Give a parameter and its values.")
            return
        prepared, case = self.analysis.prepared, self._case_config()
        self._study(f"Sweeping {parameter_label(path)[0]}...", lambda: sweeps.sweep(prepared, case, path, values),
                    lambda points: self._show_sweep(path, case.name, points))

    def _show_study_table(self, shown: bool) -> None:
        self.study_table.setVisible(shown)
        self.study_empty.setVisible(not shown)

    def _show_sweep(self, path: str, case: str, points) -> None:
        label, unit = parameter_label(path)
        nodes = [n.name for n in points[0].summary]
        # The user's node names as they are ("array +y min", not "Array +y min"; UI audit B11).
        headers = [units.label(f"Value [{unit}]") if unit else "Value"]
        headers += [f"{node} {end}\n[°C]" for node in nodes for end in ("min", "max")]
        rows = []
        for point in points:
            by_node = {n.name: n for n in point.summary}
            rows.append(Row((_text(point.value), *(_text(getattr(by_node[node], f"{end}_c")) for node in nodes
                                                   for end in ("min", "max")))))
        # Numbers to compare: every column whole, the table scrolls sideways when they do not fit (DESIGN.md).
        self.study_table.set_table(headers, rows, numeric=range(len(headers)), stretch=-1)
        self._show_study_table(True)
        self.study_label.setText(f"Sweep of {label} in the {case} case: each node's extremes at each value.")

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
            table.append({"parameter": parameter_text(row.path), "value": row.value, "step": row.step,
                          "largest change_k": row.largest_k, "node": node, "min change_k": d_min,
                          "max change_k": d_max, "mean change_k": d_mean})
        self._fill(self.study_table, table, tips={0: [row.path for row in rows]})
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
        self._enable_solve()

    def _enable_solve(self) -> None:
        if self._worker is not None:
            set_off_reason(self.solve_button, False, "Off: the cases are being solved.")
        elif self._result is None or self.spacecraft_combo.count() == 0:
            set_off_reason(self.solve_button, False, "Off: there is no run of a spacecraft with a thermal model. "
                           "Run a scenario whose spacecraft has one (Spacecraft › 3D model › Thermal model).")
        else:
            set_off_reason(self.solve_button, True, "")

    def _failed(self, message: str) -> None:
        self.status_label.setText(message)

    # -- showing ------------------------------------------------------------

    def show_analysis(self, analysis) -> None:
        """Show ``analysis`` (a thermal.analysis.ThermalAnalysis)."""
        self.analysis = analysis
        self._export_cache = (None, "", "")
        cases = analysis.cases
        # One short line (UI audit UI-07): each case's start and checks are on Notes, the findings in Problems.
        self.status_label.setText(f"Solved {len(cases)} case{'' if len(cases) == 1 else 's'}.")
        env = analysis.prepared.environment
        headers, rows = summary_rows(analysis)
        self.summary_table.set_table(headers, rows, numeric=range(2, 8), stretch=len(headers) - 1)
        findings = analysis.findings()
        self.findings_label.set_text(f"{len(findings)} finding{'' if len(findings) == 1 else 's'}")
        self.findings_label.setVisible(bool(findings))
        self.problems_button.setVisible(bool(findings))
        self.solution_table.set_rows(solution_rows(analysis))
        self.environment_sheet.set_rows([("Beta angle, lowest", f"{float(env.beta_deg.min()):.1f}", "°"),
                                         ("Beta angle, highest", f"{float(env.beta_deg.max()):.1f}", "°")])
        self.notes_list.set_notes(case_notes(cases))
        self.case_combo.blockSignals(True)
        self.case_combo.clear()
        self.case_combo.addItems([c.name for c in cases])
        self.case_combo.blockSignals(False)
        self.choices.setVisible(bool(cases))
        self.stack.setCurrentWidget(self.tabs if cases else self.empty_state)
        self._show_study_table(False)
        self.study_label.setText("")
        from ..thermal import sweeps

        self._set_parameters(sweeps.default_parameters(analysis.prepared.spacecraft.thermal))
        self._enable_studies()
        set_off_reason(self.save_button, True, "")
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
                shown = [{k: v for k, v in r.items() if k != "case"} for r in rows]
                self._fill(table, shown)
                if key == "flows":  # a kind of heat no node has in this case is noise: hidden, on the header's menu
                    table.set_hidden_columns([i for i, k in enumerate(shown[0]) if i and all(
                        isinstance(r[k], (int, float)) and r[k] == 0 for r in shown)])
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
        self._fit_flow_table()
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
                               current_theme(), self, time_unit="s" if units.plot_units() == "recorded" else "h")
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
    def _fill(table: DataTable, rows: list[dict], tips: dict | None = None) -> None:
        """``rows`` of a record table under their headings, the unit on a
        second line; the columns of numbers right-aligned, those of names
        (a node, a heater) left (UI audit B11: a node's name was set right);
        ``tips``: per column, a tooltip per row."""
        columns = list(rows[0]) if rows else []
        numeric = [i for i, c in enumerate(columns)
                   if any(isinstance(r.get(c), (int, float)) and not isinstance(r.get(c), bool) for r in rows)]
        tips = tips or {}
        table.set_table([_two_lines(heading(c)) for c in columns],
                        [Row(tuple(_text(r.get(c)) for c in columns),
                             tooltips={col: tip[i] for col, tip in tips.items() if i < len(tip)})
                         for i, r in enumerate(rows)], numeric=numeric, stretch=0)

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
