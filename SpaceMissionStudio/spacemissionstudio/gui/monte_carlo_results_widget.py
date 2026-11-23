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

"""The "Monte Carlo" tab: what a batch produced.

Shows the summary ``engine.monte_carlo_results`` keeps of a batch (never
Basilisk's pickled archive, security analysis S-04): headline tiles for
how far the runs spread, the per-run curves and their 1-sigma spread in
an embedded Results view, a sortable table of what each run drew, where
it ended and its outcomes (crashed runs with their draws, and a "Status"
column that finds them), the requirements judged on the runs
(``engine.monte_carlo_requirements``), each outcome's statistics and
empirical distribution (Monte Carlo plan B3: the Statistics tab), the
correlation of each drawn value with each outcome (B2: the Sensitivity
tab) and, for a thermal batch, each node's operating and survival range
judged on the runs (B4: the Node limits tab). The statistics and the
correlations are worked out off the GUI thread, when one of their tabs is
first shown for a batch (``gui.monte_carlo_insight``). **Export report...**
writes the batch report (B5, ``engine.monte_carlo_report``), Markdown or
JSON, in a worker thread. A batch whose
scenario is not the one open says so in a note under the title (B6,
:meth:`MonteCarloResultsWidget.compare_with_scenario`).
Filled after a run in Monte Carlo mode, or from a folder an earlier batch
saved (**Open results...**). **Run This Case** (the Runs table's button and
right-click menu) asks for the case picked to run again as a plain run
(Monte Carlo plan A3); the main window runs it.
"""

from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QMenu, QPushButton, QSplitter, QToolButton,
                               QVBoxLayout, QWidget)

from . import export_log
from ..config import models
from ..engine import monte_carlo_requirements as mcreq
from ..engine import monte_carlo_results as mcr
from ..engine import monte_carlo_statistics as mcs
from .data_table import DataTable, Row
from ..engine import monte_carlo_report
from .monte_carlo_insight import (NO_VALUE, InsightComputer, InsightPlot, ReportWriter, ecdf_figure, number_text,
                                  percentile_title, scatter_figure)
from .results_widget import ResultsWidget
from .scenario_explainer_widget import _stat_tile
from .feedback import report
from .theme import icon, set_role
from .value_sheet import NoteList
from .widgets import ComboBox, TabWidget, connect_while_alive

_EMPTY_HINT = ("A run in Monte Carlo mode (the run mode beside Run) shows its batch here. Open results... "
               "shows one an earlier batch saved (the folder you chose for it).")


def _number_text(value: float) -> str:
    """A table cell: 6 significant figures (sorted by the value itself)."""
    return "" if math.isnan(value) else f"{value:.6g}"


_km = mcr.format_km

# A requirement's verdict: its words behind a status icon, never the colour alone.
_VERDICT_MARKS = {
    mcreq.MET: ("circle-check", "status.normal", "status.normal.text"),
    mcreq.NOT_SHOWN: ("triangle-alert", "status.caution", "status.caution.text"),
}
_REQUIREMENTS_HINT = ("Each requirement judged on the runs: of the N runs evaluated, k do not meet it; the estimate "
                      "is k/N and the upper bound is exact at the requirement's confidence. A crashed run counts as "
                      "not meeting every requirement; a run that did not record the outcome is not evaluated.")
_NO_REQUIREMENTS = ("No requirements in this batch. Add them under Scenario › Monte Carlo › Requirements; the next "
                    "batch judges them.")
_NODE_LIMITS_HINT = ("Each node's operating and survival range judged on the runs: of the N runs evaluated, k "
                     "leave the range at some time step; the estimate is k/N and, with the thermal Monte Carlo's "
                     "confidence, the upper bound is exact at it. A failed run (a draw the model refused) counts as "
                     "leaving every range.")
# What the band of a thermal or operations batch's spread plot is (decision MC-27, plan Q8).
_BAND = ("The band around the mean is the mean plus and minus 3 standard deviations of the runs at each step, not a "
         "probability bound; the Statistics tab gives percentiles.")
_STATISTICS_HINT = ("Each outcome over the runs that recorded it: N, the minimum, the percentiles and the maximum, in "
                    "the unit of its row. A crashed run has no outcome and is not in N. Pick a row to plot its "
                    "empirical distribution: the fraction of runs at or below each value.")
_SENSITIVITY_HINT = ("How each drawn value goes with each outcome: +1, the outcome always grows with it; -1, it always "
                     "falls; near 0, they are unrelated. N is the runs that recorded both. Sorted by size, whatever "
                     "the sign; \"—\" where a value does not vary. A correlation is not a cause. Pick a row to plot "
                     "the pair.")
_WORKING = "Working out the statistics of the runs..."
_NO_OUTCOMES = "This batch keeps no outcome of its runs."
_NO_DRAWS = ("This batch keeps no drawn values, or no outcome, of its runs: there is nothing to correlate. A batch "
             "made before its draws were kept shows none.")
_PICK_STATISTIC = "Pick an outcome in the table to plot its distribution."
_PICK_PAIR = "Pick a drawn value and an outcome in the table to plot them against each other."
_NO_NODE_LIMITS = ("No node limits in this batch: no node of the thermal model has an operating or survival range, "
                   "or the batch was saved before they were judged. Give the ranges under Spacecraft › 3D model › "
                   "Thermal model › Nodes, then run the Monte Carlo again.")


REPORT_TIP = ("Write the batch report, Markdown (.md) or JSON (.json): the settings, dispersions, requirements and "
              "their verdicts, outcome statistics, sensitivity, crashed runs and provenance, the numbers this view "
              "shows.")

# Run This Case (plan A3): its keys, what it does, and why it cannot run now.
RUN_CASE_KEYS = "Ctrl+Shift+R"
RUN_CASE_TIP = ("Run the case picked in the Runs table again, as a plain run with the same draws and seeds: every "
                "series, the events and the Overview. The open scenario must be the batch's, unchanged.")
_NO_BATCH = "No Monte Carlo batch is shown. Run one, or open its folder (Open results...)."
_NOT_AN_ORBIT_BATCH = "A thermal or operations batch has no Basilisk cases to run again."
_NO_FOLDER = "The batch's folder is not known: open it with Open results..."
_PICK_ONE_CASE = "Pick one run in Results › Monte Carlo › Runs."


class MonteCarloResultsWidget(QWidget):
    #: The Requirements tab's empty state asks for the scenario's Monte Carlo settings.
    edit_requirements_requested = Signal()
    #: Run This Case: the case (Basilisk's number) to run again.
    case_requested = Signal(int)
    #: Whether Run This Case can act changed (case_unavailable()).
    case_changed = Signal()
    #: problem_rows() changed: a case was refused, or that is no longer current.
    problems_changed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.batch: mcr.MonteCarloBatch | None = None
        self.folder: Path | None = None
        self.case_problem = ""  # why the last case asked for was not run (main window: case_refused)
        # The window's command (Run › Run This Case, gui.actions); its shortcut is the window's.
        self.run_case_action = QAction(icon("play"), "Run This Case", self)
        self.run_case_action.setShortcut(QKeySequence(RUN_CASE_KEYS))
        self.run_case_action.setToolTip(f"Run This Case ({RUN_CASE_KEYS})\n{RUN_CASE_TIP}")
        self.run_case_action.triggered.connect(self._on_run_case)

        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        self.title_label = QLabel("No Monte Carlo batch yet")
        set_role(self.title_label, role="section-title")
        header.addWidget(self.title_label, 1)
        self.spacecraft_label = QLabel("Spacecraft:")
        self.spacecraft_combo = ComboBox()
        self.spacecraft_combo.currentIndexChanged.connect(self._refresh_spacecraft_views)
        header.addWidget(self.spacecraft_label)
        header.addWidget(self.spacecraft_combo)
        self.open_button = QPushButton("Open results...")
        self.open_button.setToolTip("Show the batch an earlier Monte Carlo run saved in a folder.")
        self.open_button.clicked.connect(self._on_open)
        header.addWidget(self.open_button)
        # The batch report (plan B5): written in a worker, a toast when it is there.
        self.report_button = QPushButton("Export report...")
        self.report_button.setToolTip(REPORT_TIP)
        self.report_button.clicked.connect(self._on_export_report)
        header.addWidget(self.report_button)
        self.report_writer = ReportWriter(self)
        self.report_writer.written.connect(self._on_report_written)
        layout.addLayout(header)

        self.hint_label = QLabel(_EMPTY_HINT)
        self.hint_label.setWordWrap(True)
        set_role(self.hint_label, tone="secondary")
        layout.addWidget(self.hint_label)
        # A batch of another scenario than the one open (plan B6): a warning under the title.
        self.scenario_notes = NoteList("warning")
        layout.addWidget(self.scenario_notes)

        self.tiles_row = QHBoxLayout()
        layout.addLayout(self.tiles_row)

        self.views = TabWidget()
        # The plot view (a second QWebEngineView next to the Results tab's)
        # is built only once a batch is shown: an idle one in every window
        # costs a Chromium renderer, and a CI test worker crashed showing
        # it on a plain tab switch.
        self.plots: ResultsWidget | None = None
        self._plots_placeholder = QWidget()
        self.views.addTab(self._plots_placeholder, "Plots")
        runs_page = QWidget()
        runs_layout = QVBoxLayout(runs_page)
        runs_layout.setContentsMargins(0, 4, 0, 0)
        runs_hint = QLabel("What each run drew, and where it ended against the batch mean. Click a column to sort; "
                           "pick a run and Run This Case to open it as a plain run.")
        runs_hint.setWordWrap(True)
        set_role(runs_hint, tone="secondary")
        runs_layout.addWidget(runs_hint)
        self.table = DataTable("No runs in this batch.")  # UI overhaul M6b
        self.table.view.selectionModel().selectionChanged.connect(self._refresh_case_action)
        self.table.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.view.customContextMenuRequested.connect(self._on_runs_menu)
        runs_layout.addWidget(self.table, 1)
        export_row = QHBoxLayout()
        self.run_case_button = QToolButton()  # secondary: the top bar's Run is the one accent (UI-03)
        self.run_case_button.setDefaultAction(self.run_case_action)
        self.run_case_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.run_case_button.setAccessibleName("Run This Case")
        export_row.addWidget(self.run_case_button)
        export_row.addStretch(1)
        self.export_button = QPushButton("Export table CSV...")
        self.export_button.clicked.connect(self._on_export)
        export_row.addWidget(self.export_button)
        runs_layout.addLayout(export_row)
        self.views.addTab(runs_page, "Runs")
        # Statistics (plan B3) and Sensitivity (B2): worked out when one of the two is first shown.
        self.insight: mcs.Insight | None = None
        self._insight_batch = None  # the batch self.insight is of
        self.insight_error = ""
        self.insight_computer = InsightComputer(self)
        self.insight_computer.ready.connect(self._on_insight_ready)
        self.statistics_hint = QLabel(_STATISTICS_HINT)
        self.statistics_table = DataTable(_WORKING)
        self.statistics_plot = InsightPlot(_PICK_STATISTIC)
        self._statistics_index = self.views.addTab(
            self._table_and_plot(self.statistics_hint, self.statistics_table, self.statistics_plot), "Statistics")
        self.sensitivity_hint = QLabel(_SENSITIVITY_HINT)
        self.sensitivity_table = DataTable(_WORKING)
        self.sensitivity_plot = InsightPlot(_PICK_PAIR)
        self._sensitivity_index = self.views.addTab(
            self._table_and_plot(self.sensitivity_hint, self.sensitivity_table, self.sensitivity_plot), "Sensitivity")
        for table, chosen in ((self.statistics_table, self._on_statistic_chosen),
                              (self.sensitivity_table, self._on_pair_chosen)):
            table.set_single_pick()
            table.row_chosen.connect(chosen)
        connect_while_alive(self.views.currentChanged, self._on_view_changed)
        requirements_page = QWidget()
        requirements_layout = QVBoxLayout(requirements_page)
        requirements_layout.setContentsMargins(0, 4, 0, 0)
        self.requirements_hint = QLabel(_REQUIREMENTS_HINT)
        self.requirements_hint.setWordWrap(True)
        set_role(self.requirements_hint, tone="secondary")
        requirements_layout.addWidget(self.requirements_hint)
        self.requirements_table = DataTable(_NO_REQUIREMENTS, action="Edit Monte Carlo settings")
        self.requirements_table.action_requested.connect(self.edit_requirements_requested)
        requirements_layout.addWidget(self.requirements_table, 1)
        self.views.addTab(requirements_page, "Requirements")
        limits_page = QWidget()
        limits_layout = QVBoxLayout(limits_page)
        limits_layout.setContentsMargins(0, 4, 0, 0)
        self.node_limits_hint = QLabel(_NODE_LIMITS_HINT)
        self.node_limits_hint.setWordWrap(True)
        set_role(self.node_limits_hint, tone="secondary")
        limits_layout.addWidget(self.node_limits_hint)
        self.node_limits_table = DataTable(_NO_NODE_LIMITS)
        limits_layout.addWidget(self.node_limits_table, 1)
        self._node_limits_index = self.views.addTab(limits_page, "Node limits")
        self.views.setTabVisible(self._node_limits_index, False)  # a thermal batch's only
        layout.addWidget(self.views, 1)
        layout.addStretch(0)  # keeps the empty state's hint at the top
        self._show(None)

    @staticmethod
    def _table_and_plot(hint: QLabel, table: DataTable, plot: InsightPlot) -> QWidget:
        """A tab of a hint, a table and, under it, its plot."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 4, 0, 0)
        hint.setWordWrap(True)
        set_role(hint, tone="secondary")
        page_layout.addWidget(hint)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(table)
        splitter.addWidget(plot)
        splitter.setSizes([200, 300])  # [px]
        page_layout.addWidget(splitter, 1)
        return page

    # -- loading -----------------------------------------------------------

    def load_folder(self, folder: str | Path) -> bool:
        """Show the batch summarized in ``folder``. On a problem, says so in
        the hint line and returns False."""
        folder = Path(folder)
        try:
            batch = mcr.load(folder)
        except mcr.MonteCarloResultsError as exc:
            self._show(None)
            self.hint_label.setText(str(exc))
            return False
        self.folder = folder
        self._show(batch)
        return True

    def _on_open(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Open Monte Carlo results")
        if folder and not self.load_folder(folder):
            report(self, f"No Monte Carlo results in {folder}: {self.hint_label.text()}", kind="warning")

    def _show(self, batch: mcr.MonteCarloBatch | None) -> None:
        self.batch = batch
        self.set_case_problem("")  # a refusal was about the batch shown before
        self.scenario_notes.set_notes([])  # compare_with_scenario says it for the batch shown now
        self._clear_insight()
        has_batch = batch is not None and bool(batch.runs)
        self.views.setVisible(has_batch)
        self.export_button.setEnabled(has_batch)
        self.report_button.setEnabled(has_batch)
        self.spacecraft_combo.blockSignals(True)
        self.spacecraft_combo.clear()
        if has_batch:
            self.spacecraft_combo.addItems(batch.items)
        self.spacecraft_combo.blockSignals(False)
        several = has_batch and len(batch.items) > 1
        if has_batch:
            self.spacecraft_label.setText({"thermal": "Node:", "operations": "Profile:"}.get(batch.kind, "Spacecraft:"))
        self.spacecraft_label.setVisible(several)
        self.spacecraft_combo.setVisible(several)
        if not has_batch:
            self.title_label.setText("No Monte Carlo batch yet")
            self.hint_label.setText(_EMPTY_HINT)
            self._set_tiles([])
            if self.plots is not None:
                self.plots.set_result(None)
            self.table.clear()
            self.requirements_table.clear()
            self.node_limits_table.clear()
            self.views.setTabVisible(self._node_limits_index, False)
            self._refresh_case_action()
            return
        self.title_label.setText(batch.scenario_name)
        days = float(batch.time_s[-1]) / 86400.0 if batch.time_s.size else 0.0
        shown = min(len(batch.runs), mcr.MAX_PLOTTED_RUNS)
        note = f" Plots show the first {shown} runs; the spread uses all." if shown < len(batch.runs) else ""
        source = f"saved in {self.folder.name}" if self.folder else "from this session"
        statistic = mcr.spread_model(batch)
        if batch.kind == "operations":
            self.hint_label.setText(f"An operations robustness batch on one plan ({days:.3g} days), {source}: every "
                                    f"draw's profile, and the 1-sigma over the draws ({statistic.title.lower()}); "
                                    f"the drawn values and the outcomes per draw are in the table. {_BAND}{note}")
        elif batch.kind == "thermal":
            self.hint_label.setText(f"A thermal Monte Carlo on one run ({days:.3g} days), case {batch.case}, "
                                    f"{source}: every run's temperatures, and the 1-sigma of each node's minimum and "
                                    f"maximum over the runs ({statistic.title.lower()}). {_BAND}{note}")
        else:
            seed = "" if batch.seed is None else f" Batch seed {batch.seed}."
            self.hint_label.setText(f"{days:.3g} days per run, {source}. Spreads are 1-sigma offsets from the mean "
                                    f"of all runs ({statistic.title.lower()}): along the orbit, radially and "
                                    f"across it.{seed}{note}")
        self.hint_label.setToolTip("\n".join(([str(self.folder)] if self.folder else []) + [
            f"{statistic.title}: {statistic.method}",
            f"Chosen by {mcr.SPREAD_CHOICE} on the Assumptions page, as the batch was run."]))
        self._ensure_plots().set_result(mcr.to_result_set(batch), batch.epoch_utc or None)
        self.views.setTabVisible(self._node_limits_index, batch.kind == "thermal")
        self._fill_node_limits()
        self._refresh_spacecraft_views()
        self._on_view_changed(self.views.currentIndex())

    def _ensure_plots(self) -> ResultsWidget:
        if self.plots is None:
            self.plots = ResultsWidget()
            index = self.views.indexOf(self._plots_placeholder)
            self.views.removeTab(index)
            self._plots_placeholder.deleteLater()
            self.views.insertTab(index, self.plots, "Plots")
            self.views.setCurrentIndex(index)
        return self.plots

    def _refresh_spacecraft_views(self) -> None:
        batch = self.batch
        if batch is None or not batch.runs:
            return
        spacecraft = self.spacecraft_combo.currentText() or batch.items[0]
        requested = len(batch.runs) + len(batch.failed)
        results = mcreq.evaluate(batch)  # none for a thermal or operations batch: the tab's empty state
        self._fill_requirements(results)
        if batch.kind == "operations":  # a profile (decision O-18)
            spread = mcr.node_spread(batch, spacecraft)
            unit = batch.profile_units.get(spacecraft, "")
            self._set_tiles([
                ("Draws", f"{len(batch.runs)} of {requested}"),
                ("Lowest", f"{spread.coldest_c:.3g} {unit}"),
                ("Highest", f"{spread.hottest_c:.3g} {unit}"),
                ("Lowest, 1-sigma", f"{spread.sigma_min_k:.3g} {unit}"),
            ])
            self.plots.set_featured_series([f"operations_monte_carlo.{spacecraft}.{field}"
                                            for field in ("spread", "value")])
            self.plots.show_series(f"operations_monte_carlo.{spacecraft}.spread")
            self._fill_table(spacecraft)
            return
        if batch.kind == "thermal":  # a node (decision T-36)
            spread = mcr.node_spread(batch, spacecraft)
            self._set_tiles([
                ("Runs", f"{len(batch.runs)} of {requested}"),
                self._failed_tile(),
                ("Coldest", f"{spread.coldest_c:.1f} °C"),
                ("Hottest", f"{spread.hottest_c:.1f} °C"),
                ("Minimum, 1-sigma", f"{spread.sigma_min_k:.2f} K"),
                ("Maximum, 1-sigma", f"{spread.sigma_max_k:.2f} K"),
            ])
            self.plots.set_featured_series([f"thermal_monte_carlo.{spacecraft}.{field}"
                                            for field in ("spread", "temperature")])
            self.plots.show_series(f"thermal_monte_carlo.{spacecraft}.spread")
            self._fill_table(spacecraft)
            return
        spread = mcr.final_spread(batch, spacecraft)
        judged = [result for result in results if result.max_probability is not None]
        met = sum(1 for result in judged if result.verdict == mcreq.MET)
        self._set_tiles([
            ("Runs", f"{len(batch.runs)} of {requested}"),
            self._failed_tile(),
            ("Along-track spread, end", _km(spread.along_track_m)),
            ("Radial spread, end", _km(spread.radial_m)),
            ("Cross-track spread, end", _km(spread.cross_track_m)),
            ("Altitude, end", f"{spread.altitude_min_m / 1e3:.0f}-{spread.altitude_max_m / 1e3:.0f} km"),
        ] + ([("Requirements met", f"{met} of {len(judged)}")] if judged else []))
        self.plots.set_featured_series([f"{spacecraft}.monte_carlo.{field}" for field in
                                        ("spread", "along_track_offset", "altitude", "radial_offset")])
        self.plots.show_series(f"{spacecraft}.monte_carlo.spread")
        self._fill_table(spacecraft)

    def _failed_tile(self) -> tuple[str, str, str]:
        """The "Failed" tile: how many runs failed (Monte Carlo plan B8); which
        ones is in the Runs table (its Status column) and in the tooltip."""
        batch = self.batch
        failed = sorted(int(run) for run in batch.failed)
        if not failed:
            return "Failed", "0", "No run failed."
        listed = sorted(run for run in batch.failed_drawn if run in set(failed))
        where = ("The Runs table lists them with the status in its Status column; sort by it to group them."
                 if listed == failed else
                 "The Runs table lists those whose draws the batch kept, with the status in its Status column."
                 if listed else "This batch's summary keeps no draws of its failed runs, so the Runs table does "
                 "not list them.")
        return "Failed", str(len(failed)), f"Failed runs: {', '.join(str(run) for run in failed)}.\n{where}"

    def _set_tiles(self, tiles) -> None:
        while self.tiles_row.count():
            item = self.tiles_row.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        for label, value, *tip in tiles:
            tile = _stat_tile(label, value)
            if tip:
                tile.setToolTip(tip[0])
            self.tiles_row.addWidget(tile, 1)  # equal widths

    def _fill_table(self, spacecraft: str) -> None:
        labels, rows = mcr.run_table(self.batch, spacecraft, outcomes=self.batch.kind in ("orbit", "thermal"))
        if len(self.batch.spacecraft) == 1:  # the spacecraft's name on every column says nothing
            labels = [label.removeprefix(f"{spacecraft} ") for label in labels]
        text = frozenset(k for k, value in enumerate(rows[0] if rows else []) if isinstance(value, str))
        table_rows = [Row([str(int(row[0]))] + [value if isinstance(value, str) else _number_text(value)
                                                for value in row[1:]],
                          keys=[value if isinstance(value, str) else float(value) for value in row], plain=text)
                      for row in rows]
        self.table.set_table(labels, table_rows, numeric=[k for k in range(len(labels)) if k not in text],
                             stretch=-1)
        self.table.set_sortable(0, Qt.SortOrder.AscendingOrder)
        self._refresh_case_action()

    def _fill_requirements(self, results: list) -> None:
        """The Requirements tab: one row per requirement (the command line's
        table), the verdict a word behind its icon."""
        model = models.model(mcr.BOUND_CHOICE, self.batch.probability_bound)
        self.requirements_hint.setToolTip(f"{model.title}: {model.method}\n{model.references[0]}")
        rows = []
        for result, cells in zip(results, mcreq.table_rows(results, len(self.batch.spacecraft) > 1)):
            mark = _VERDICT_MARKS.get(result.verdict)
            tips = {8: f"{model.title} at confidence {result.confidence:g}"}
            if result.not_met_runs:
                tips[4] = "Runs not met: " + ", ".join(str(run) for run in result.not_met_runs)
            rows.append(Row(list(cells), tooltips=tips, plain=frozenset({0, 1, 2, 11}),
                            keys=[cell if k in (0, 1, 2, 11) else (float(cell) if cell else -1.0)
                                  for k, cell in enumerate(cells)],
                            marks={11: mark} if mark is not None else {},
                            muted=frozenset() if mark is not None else frozenset({11})))
        self.requirements_table.set_table(list(mcreq.TABLE_HEADER), rows, numeric=range(3, 11), stretch=1)
        self.requirements_table.set_sortable(0, Qt.SortOrder.AscendingOrder)

    def _fill_node_limits(self) -> None:
        """The Node limits tab of a thermal batch (Monte Carlo plan B4): one
        row per node and range, the runs outside it in the tooltip."""
        batch = self.batch
        if batch is None or batch.kind != "thermal" or not batch.node_limits:
            self.node_limits_table.clear()
            return
        model = models.model(mcr.BOUND_CHOICE, batch.probability_bound)
        self.node_limits_hint.setToolTip(f"{model.title}: {model.method}\n{model.references[0]}")
        results = [mcreq.NodeLimitResult.from_dict(row) for row in batch.node_limits]
        rows = []
        for result, cells in zip(results, mcreq.node_limit_rows(results)):
            tips = {8: f"{model.title} at confidence {result.confidence:g}" if result.confidence is not None else
                    "No confidence in the thermal Monte Carlo: counts and the estimate only"}
            if result.outside_runs:
                tips[5] = "Runs outside: " + ", ".join(str(run) for run in result.outside_runs)
            rows.append(Row(list(cells), tooltips=tips, plain=frozenset({0, 1}),
                            keys=[cell if k in (0, 1) else (float(cell) if cell else -1.0)
                                  for k, cell in enumerate(cells)]))
        self.node_limits_table.set_table(list(mcreq.NODE_LIMITS_HEADER), rows, numeric=range(2, 10), stretch=0)
        self.node_limits_table.set_sortable(0, Qt.SortOrder.AscendingOrder)

    # -- statistics and sensitivity (plan B3 and B2) -----------------------

    def _clear_insight(self) -> None:
        self.insight, self._insight_batch, self.insight_error = None, None, ""
        for table in (self.statistics_table, self.sensitivity_table):
            table.clear(_WORKING)
        self.statistics_plot.clear(_PICK_STATISTIC)
        self.sensitivity_plot.clear(_PICK_PAIR)

    def _on_view_changed(self, index: int) -> None:
        """The Statistics or Sensitivity tab shown: its numbers are worked
        out, once per batch, off the GUI thread."""
        if index in (self._statistics_index, self._sensitivity_index):
            self.request_insight()

    def request_insight(self) -> None:
        """Work out the shown batch's statistics and sensitivity, unless they
        are known or on their way (:attr:`insight_pending`)."""
        batch = self.batch
        if batch is None or not batch.runs or self._insight_batch is batch:
            return
        self._insight_batch = batch
        self.insight_computer.request(batch)

    @property
    def insight_pending(self) -> bool:
        """The shown batch's statistics are being worked out."""
        return self._insight_batch is not None and self.insight is None and not self.insight_error

    def _on_insight_ready(self, batch, insight, error: str) -> None:
        if batch is not self.batch:  # another batch was shown meanwhile; its own request follows
            return
        self.insight, self.insight_error = insight, error
        if insight is None:
            text = f"The statistics of this batch could not be worked out: {error}"
            for table in (self.statistics_table, self.sensitivity_table):
                table.clear(text)
            return
        self._fill_statistics()
        self._fill_sensitivity()

    def _short(self, label: str) -> str:
        """A column's label without the spacecraft's name when the batch has one spacecraft."""
        names = self.batch.spacecraft if self.batch is not None else []
        return label.removeprefix(f"{names[0]} ") if len(names) == 1 else label

    def _fill_statistics(self) -> None:
        insight = self.insight
        model = models.model(mcs.PERCENTILE_CHOICE, insight.method)
        self.statistics_hint.setToolTip(f"{model.title}: {model.method}\n{model.references[0]}\n"
                                        f"Chosen by {mcs.PERCENTILE_CHOICE} and {mcs.PERCENTILES} on the "
                                        "Assumptions page, as the batch was run.")
        if not insight.statistics:
            self.statistics_table.clear(_NO_OUTCOMES)
            self.statistics_plot.clear(_NO_OUTCOMES)
            return
        percentiles = list(insight.percentiles)
        headers = (["Outcome", "Unit", "N", "Minimum"] + [percentile_title(p) for p in percentiles]
                   + ["Maximum"])
        rows = []
        for stat in insight.statistics:
            values = [stat.minimum, *stat.values, stat.maximum]
            rows.append(Row([self._short(stat.name), stat.unit, str(stat.n)] + [number_text(v) for v in values],
                            keys=[self._short(stat.name), stat.unit, float(stat.n)]
                            + [float(v) if v is not None else -math.inf for v in values]))
        self.statistics_table.set_table(headers, rows, numeric=range(2, len(headers)), stretch=0)
        tips = {3 + k: f"The {p:g}th percentile ({model.title.lower()}), in the row's unit"
                for k, p in enumerate(percentiles, start=1)}
        tips.update({2: "The runs that recorded the outcome", 3: "The lowest value, in the row's unit",
                     len(headers) - 1: "The highest value, in the row's unit"})
        self.statistics_table.set_header_marks(tooltips=tips)
        # Sortable by a header click, but first in the batch's order (where the runs ended, then the Overview's).
        self.statistics_table.view.horizontalHeader().setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        self.statistics_table.view.setSortingEnabled(True)
        self.statistics_table.view.selectRow(0)

    def _fill_sensitivity(self) -> None:
        insight = self.insight
        model = models.model(mcs.SENSITIVITY_CHOICE, insight.measure)
        self.sensitivity_hint.setToolTip(f"{model.title}: {model.method}\n{model.references[0]}\n"
                                         f"Chosen by {mcs.SENSITIVITY_CHOICE} on the Assumptions page, as the "
                                         "batch was run.")
        if not insight.sensitivity:
            self.sensitivity_table.clear(_NO_DRAWS)
            self.sensitivity_plot.clear(_NO_DRAWS)
            return
        headers = ["Drawn value", "Outcome", f"{model.title} [-]", "N"]
        rows = [Row([self._short(row.input_label), self._short(row.outcome_label), number_text(row.value),
                     str(row.n)],
                    keys=[self._short(row.input_label), self._short(row.outcome_label),
                          abs(row.value) if row.value is not None else -1.0, float(row.n)],
                    tooltips={} if row.value is not None else {
                        2: "No correlation: one of the two does not vary over these runs, or fewer than "
                           f"{mcs.MIN_PAIRS} runs recorded both"},
                    muted=frozenset() if row.value is not None else frozenset({2}))
                for row in insight.sensitivity]
        self.sensitivity_table.set_table(headers, rows, numeric=(2, 3), stretch=1)
        self.sensitivity_table.set_header_marks(tooltips={2: "Sorted by its size, whatever the sign",
                                                          3: "The runs that recorded both"})
        self.sensitivity_table.set_sortable(2, Qt.SortOrder.DescendingOrder)
        self.sensitivity_table.view.selectRow(0)

    def _on_statistic_chosen(self, row: int) -> None:
        insight = self.insight
        if insight is None or not 0 <= row < len(insight.statistics):
            return
        stat = insight.statistics[row]
        column = insight.outcomes[stat.label]
        title = f"{self._short(stat.name)}: distribution over the runs"
        subtitle = f"{stat.n} runs; the fraction at or below each value"
        shown = mcs.Column(self._short(column.label), column.values)
        self.statistics_plot.show_figure(lambda: ecdf_figure(shown, title, subtitle))

    def _on_pair_chosen(self, row: int) -> None:
        insight = self.insight
        if insight is None or not 0 <= row < len(insight.sensitivity):
            return
        pair = insight.sensitivity[row]
        x, y = insight.inputs[pair.input_label], insight.outcomes[pair.outcome_label]
        model = models.model(mcs.SENSITIVITY_CHOICE, insight.measure)
        value = NO_VALUE if pair.value is None else f"{pair.value:.3g}"
        title = f"{self._short(y.name)} against {self._short(x.name)}"
        subtitle = f"{model.title} {value} over {pair.n} runs"
        runs = list(self.batch.runs)
        x_title, y_title = self._short(x.label), self._short(y.label)
        self.sensitivity_plot.show_figure(lambda: scatter_figure(x, y, runs, title, subtitle, x_title, y_title))

    def wait_for_insight(self) -> None:
        """Until the statistics in progress are worked out and the reports
        asked for are written (tests, closing)."""
        self.insight_computer.wait()
        self.report_writer.wait()

    # -- the batch's scenario (plan B6) --------------------------------------

    def compare_with_scenario(self, scenario) -> None:
        """Say under the title when the batch shown was run with another
        scenario than ``scenario`` (the one open; None: nothing is open, so
        nothing is said). The batch's scenario is its folder's
        ``archive.provenance.json`` ``scenario_sha256``
        (``engine.monte_carlo_case.batch_scenario_hash``), the same check
        as Run This Case's; a batch whose folder does not record it (a
        thermal or operations batch) is not compared."""
        from .. import output_provenance
        from ..engine.monte_carlo_case import batch_scenario_hash

        notes = []
        if scenario is not None and self.batch is not None and self.folder is not None:
            found = batch_scenario_hash(self.folder)
            if not isinstance(found, str):
                batch_digest, batch_file = found
                digest = output_provenance.scenario_sha256(scenario)
                if digest != batch_digest:
                    named = f" ({batch_file})" if batch_file else ""
                    notes.append(f"This batch was run with another scenario than the one open: scenario SHA-256 "
                                 f"{batch_digest} at the batch, {digest} now. Its draws, outcomes and statistics "
                                 "are the batch's, not the open scenario's; Run This Case refuses its cases until "
                                 f"the batch's own scenario{named} is open, unchanged.")
        self.scenario_notes.set_notes(notes)

    # -- one case again (plan A3) -------------------------------------------

    def picked_case(self) -> int | None:
        """The case of the one run picked in the Runs table (Basilisk's
        number, its first column), or None."""
        rows = self.table.view.selectionModel().selectedRows() if self.table.model.rowCount() else []
        if len(rows) != 1:
            return None
        row = self.table.proxy.mapToSource(rows[0]).row()
        return int(float(self.table.model.text(row, 0)))

    def case_unavailable(self) -> str:
        """Why Run This Case cannot act now, or "" when it can."""
        if self.batch is None or not self.batch.runs:
            return _NO_BATCH
        if self.batch.kind != "orbit":
            return _NOT_AN_ORBIT_BATCH
        if self.folder is None:
            return _NO_FOLDER
        if self.picked_case() is None:
            return _PICK_ONE_CASE
        return ""

    def _refresh_case_action(self, *_args) -> None:
        self.run_case_action.setEnabled(not self.case_unavailable())
        self.case_changed.emit()

    def _on_run_case(self) -> None:
        case = self.picked_case()
        if case is not None and not self.case_unavailable():
            self.case_requested.emit(case)

    def _on_runs_menu(self, at) -> None:
        """The Runs table's right-click menu: Run This Case, Copy."""
        menu = QMenu(self)
        menu.addAction(self.run_case_action)
        menu.addAction("Copy", self.table.copy)
        menu.popup(self.table.view.viewport().mapToGlobal(at))
        self.runs_menu = menu  # kept while it is open

    def set_case_problem(self, text: str) -> None:
        """Why the case asked for was not run ("" once that is no longer
        current): a row of the Problems panel (:meth:`problem_rows`)."""
        if text != self.case_problem:
            self.case_problem = text
            self.problems_changed.emit()

    def problem_rows(self) -> list:
        """A refused case as a Problems row ``(severity, text, shown text)``."""
        return [("warning", self.case_problem, self.case_problem)] if self.case_problem else []

    # -- export ------------------------------------------------------------

    def export_table_csv(self, path: str | Path) -> Path:
        """The Runs table, for the shown spacecraft, as CSV, with
        ``<file>.provenance.json`` beside it (Phase 9a): the batch's own
        provenance (``archive.provenance.json``) when its folder has one.
        The command line's ``monte-carlo --csv`` writes the same
        (``engine.monte_carlo_report.write_runs_csv``)."""
        return monte_carlo_report.write_runs_csv(self.batch, path, self.spacecraft_combo.currentText() or None,
                                                 self.folder)

    def export_report(self, path: str | Path) -> None:
        """Write the shown batch's report to ``path`` (``.md`` or ``.json``)
        in a worker (design rule 6), with the statistics this view shows
        when they are worked out; :meth:`_on_report_written` says how it
        went."""
        insight = self.insight if self._insight_batch is self.batch else None
        self.report_writer.request(self.batch, Path(path), self.folder, insight)

    def _on_export_report(self) -> None:
        if self.batch is None or not self.batch.runs:
            return
        path_str, chosen = QFileDialog.getSaveFileName(self, "Export Monte Carlo report", "monte_carlo_report.md",
                                                       "Markdown (*.md);;JSON (*.json)")
        if not path_str:
            return
        path = Path(path_str)
        if path.suffix.lower() not in monte_carlo_report.SUFFIXES:  # the format chosen in the dialog
            path = path.with_name(path.name + (".json" if "json" in chosen.lower() else ".md"))
        self.export_report(path)

    def _on_report_written(self, path, error: str) -> None:
        if error:
            report(self, f"Could not export the Monte Carlo report to {path}: {error}")
            return
        export_log.record("monte_carlo_report", path)
        report(self, f"Exported the Monte Carlo report to {path}", kind="success")

    def _on_export(self) -> None:
        path_str, _ = QFileDialog.getSaveFileName(self, "Export Monte Carlo runs to CSV", "monte_carlo_runs.csv",
                                                  "CSV files (*.csv)")
        if not path_str:
            return
        path = Path(path_str)
        if path.suffix != ".csv":
            path = path.with_suffix(".csv")
        try:
            self.export_table_csv(path)
        except OSError as exc:
            report(self, f"Could not export the Monte Carlo table to {path}: {exc}")
            return
        export_log.record("monte_carlo_csv", path)
        report(self, f"Exported the Monte Carlo table to {path}", kind="success")
