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
it ended and its outcomes (crashed runs with their draws), and the
requirements judged on the runs (``engine.monte_carlo_requirements``).
Filled after a run in Monte Carlo mode, or from a folder an earlier batch
saved (**Open results...**). **Run This Case** (the Runs table's button and
right-click menu) asks for the case picked to run again as a plain run
(Monte Carlo plan A3); the main window runs it.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QMenu, QPushButton, QToolButton, QVBoxLayout,
                               QWidget)

from . import export_log
from ..config import models
from ..engine import monte_carlo_requirements as mcreq
from ..engine import monte_carlo_results as mcr
from .data_table import DataTable, Row
from .results_widget import ResultsWidget
from .scenario_explainer_widget import _stat_tile
from .feedback import report
from .theme import icon, set_role
from .widgets import ComboBox, TabWidget

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
        layout.addLayout(header)

        self.hint_label = QLabel(_EMPTY_HINT)
        self.hint_label.setWordWrap(True)
        set_role(self.hint_label, tone="secondary")
        layout.addWidget(self.hint_label)

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
        layout.addWidget(self.views, 1)
        layout.addStretch(0)  # keeps the empty state's hint at the top
        self._show(None)

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
        has_batch = batch is not None and bool(batch.runs)
        self.views.setVisible(has_batch)
        self.export_button.setEnabled(has_batch)
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
                                    f"the drawn values and the outcomes per draw are in the table.{note}")
        elif batch.kind == "thermal":
            self.hint_label.setText(f"A thermal Monte Carlo on one run ({days:.3g} days), case {batch.case}, "
                                    f"{source}: every run's temperatures, and the 1-sigma of each node's minimum and "
                                    f"maximum over the runs ({statistic.title.lower()}).{note}")
        else:
            self.hint_label.setText(f"{days:.3g} days per run, {source}. Spreads are 1-sigma offsets from the mean "
                                    f"of all runs ({statistic.title.lower()}): along the orbit, radially and "
                                    f"across it.{note}")
        self.hint_label.setToolTip("\n".join(([str(self.folder)] if self.folder else []) + [
            f"{statistic.title}: {statistic.method}",
            f"Chosen by {mcr.SPREAD_CHOICE} on the Assumptions page, as the batch was run."]))
        self._ensure_plots().set_result(mcr.to_result_set(batch), batch.epoch_utc or None)
        self._refresh_spacecraft_views()

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
                ("Failed", ", ".join(str(run) for run in batch.failed) if batch.failed else "none"),
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
            ("Failed", ", ".join(str(run) for run in batch.failed) if batch.failed else "none"),
            ("Along-track spread, end", _km(spread.along_track_m)),
            ("Radial spread, end", _km(spread.radial_m)),
            ("Cross-track spread, end", _km(spread.cross_track_m)),
            ("Altitude, end", f"{spread.altitude_min_m / 1e3:.0f}-{spread.altitude_max_m / 1e3:.0f} km"),
        ] + ([("Requirements met", f"{met} of {len(judged)}")] if judged else []))
        self.plots.set_featured_series([f"{spacecraft}.monte_carlo.{field}" for field in
                                        ("spread", "along_track_offset", "altitude", "radial_offset")])
        self.plots.show_series(f"{spacecraft}.monte_carlo.spread")
        self._fill_table(spacecraft)

    def _set_tiles(self, tiles) -> None:
        while self.tiles_row.count():
            item = self.tiles_row.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        for label, value in tiles:
            self.tiles_row.addWidget(_stat_tile(label, value), 1)  # equal widths

    def _fill_table(self, spacecraft: str) -> None:
        labels, rows = mcr.run_table(self.batch, spacecraft, outcomes=self.batch.kind == "orbit")
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
        provenance (``archive.provenance.json``) when its folder has one."""
        from .. import output_provenance

        path = Path(path)
        spacecraft = self.spacecraft_combo.currentText() or None
        labels, rows = mcr.run_table(self.batch, spacecraft, outcomes=self.batch.kind == "orbit")
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(labels)
            for row in rows:
                # a value a run does not have stays "nan", as before (a crashed run's offsets and outcomes)
                writer.writerow([int(row[0])] + [value if isinstance(value, str) else f"{value:.9g}"
                                                 for value in row[1:]])
        archive = None
        if self.folder is not None and (self.folder / "archive.provenance.json").is_file():
            try:
                archive = json.loads((self.folder / "archive.provenance.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                archive = None
        output_provenance.write_sidecar(path, {
            "export": "Monte Carlo runs table", "spacecraft": spacecraft, "runs": len(rows),
            "batch_folder": str(self.folder) if self.folder is not None else "",
            "batch_provenance": archive if archive is not None else
            "not found: the batch folder's archive.provenance.json"})
        return path

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
