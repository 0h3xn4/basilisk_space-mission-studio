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


"""Reports › Exports (UI overhaul M8, plan §5.3): every export the app
makes, in one table, with its format, where it is made, its default
destination, the provenance written with it and when this machine last
wrote one (:mod:`gui.export_log`). Enter or a double-click opens the view
that makes it; the exports themselves stay on their views' buttons.

The table fits the page (UI audit UI-27): at 1280 px, with the Inspector
open or closed, it does not scroll sideways; the longest texts are elided
and whole on hover, and no heading is cut.
"""

from __future__ import annotations

from typing import NamedTuple

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from . import export_log
from .data_table import DataTable, Row
from .theme import SPACE, set_role


class Export(NamedTuple):
    key: str  # export_log's key
    name: str
    file_format: str
    made_in: str  # the view and its button
    destination: str  # the default destination
    provenance: str  # what is written with it, in short
    provenance_detail: str = ""  # the cell's tooltip


EXPORTS = (
    Export("plot_csv", "Plot data", "CSV, a file a series", "Results › Plots › Export CSV...", "Folder chosen",
           "provenance.json", "provenance.json in the folder"),
    Export("plot_png", "Plot image", "PNG", "Results › Plots › Save PNG...", "<series>.png", "In the file",
           "In the image, as a PNG text chunk"),
    Export("plot_svg", "Plot image", "SVG", "Results › Plots › Save SVG...", "<series>.svg", "In the file",
           "In the image, as SVG metadata"),
    Export("plots_all", "Every shown plot", "PNG or SVG, CSV", "Results › Plots › Export all...", "Folder chosen",
           "In each image; provenance.json", "In each image, and provenance.json in the folder"),
    Export("bundle", "Reproduction bundle", "CSV, JSON and the files referred to",
           "Results › Plots › Export all... › Reproduction bundle...", "Empty folder chosen",
           "provenance.json, bundle.json", "provenance.json, and bundle.json listing each file copied with its "
           "SHA-256"),
    Export("events_csv", "Events", "CSV", "Timeline › Export CSV...", "events.csv", "<file>.provenance.json",
           "<file>.provenance.json beside it"),
    Export("output_csv", "Mission output", "CSV", "Results › Output › Export CSV...", "File chosen",
           "<file>.provenance.json", "<file>.provenance.json beside it"),
    Export("monte_carlo_csv", "Monte Carlo runs", "CSV", "Results › Monte Carlo › Export table CSV...",
           "monte_carlo_runs.csv", "<file>.provenance.json",
           "<file>.provenance.json beside it, with the batch's own (archive.provenance.json)"),
    Export("lifetime_json", "Lifetime estimate", "JSON", "Run › End of Life › Export JSON...", "lifetime.json",
           "In the file", "In the file: the inputs, rules, traces, decay curve, data files and the scenario's SHA-256"),
    Export("budget_csv", "Budget", "CSV text", "Budgets › Propellant › Copy as CSV", "Clipboard", "Its last lines",
           "Its last lines: the versions, the scenario's SHA-256 and the time"),
    Export("design_checks", "Design checks", "JSON, a CSV a table", "Run › Design Checks › Save...", "Folder chosen",
           "In the record; <file>.provenance.json", "In design_checks.json, and <file>.provenance.json beside each "
           "table"),
    Export("model_analyses", "Model analyses", "JSON, a CSV a table", "Results › Model Analyses › Save...",
           "Folder chosen", "In the record; <file>.provenance.json", "In model_analyses.json (with the run's own "
           "record), and <file>.provenance.json beside each table"),
    Export("thermal", "Thermal analysis", "JSON, CSV tables and series, SVG and PNG plots",
           "Run › Thermal › Save...", "Folder chosen", "In the record; <file>.provenance.json",
           "In thermal.json (with the run's own record), and <file>.provenance.json beside each table, series "
           "and plot"),
    Export("plan", "Operations plan", "JSON (spacemissionstudio-plan)", "Run › Plan › Save plan...", "plan.json",
           "In the file", "In the file: the tool version, the scenario's SHA-256, the geometry, seed and settings"),
    Export("operations", "Operations products", "CSV, iCalendar, JSON, CCSDS OEM and AEM, Markdown",
           "Run › Plan › Export...", "Folder chosen", "In each file; <file>.provenance.json",
           "In each file's header or COMMENT lines where its format has room, else <file>.provenance.json beside it; "
           "the plan's SHA-256 in each"),
    Export("operations_robustness", "Plan robustness batch", "Monte Carlo archive", "Run › Plan › Save batch...",
           "Folder chosen", "archive.provenance.json", "archive.provenance.json: the seed and the draw settings"),
    Export("reentry_json", "Re-entry estimate", "JSON", "Run › End of Life › Re-entry casualty › Save...",
           "reentry.json", "In the file", "In the file: the rules in effect, each part's fate and the scenario's "
           "SHA-256"),
    Export("fsw_project", "Flight software", "C project (CMake)", "Reports › Flight Software › Export...",
           "Folder chosen", "manifest.json", "manifest.json in the folder"),
    Export("sil_report", "SIL report", "JSON, residuals CSV", "Reports › Flight Software › Save report...",
           "File chosen", "In the report", "In the report: the binary's and the configurations' SHA-256"),
    Export("ccsds_orbits", "Starting orbits", "CCSDS OPM, or OMM for a TLE", "Tools › Export Orbits as CCSDS...",
           "Folder chosen", "In the file", "COMMENT lines: the scenario's name and hash"),
    Export("ccsds_oem", "Ephemeris", "CCSDS OEM, a file a spacecraft",
           "Results › Plots › Export all... › CCSDS ephemeris (OEM)...", "Folder chosen", "In the file",
           "COMMENT lines: the run's provenance"),
    Export("model_obj", "3D model", "OBJ and MTL", "Scenario › 3D Model... › Export .obj...", "<spacecraft>.obj",
           "None"),
)
_HEADERS = ("Export", "Last written\n[UTC]", "Format", "Made in", "Default destination", "Provenance")
_LAST = 1  # the column of the time last written
_WRAPPED = (0, 2, 3, 4, 5)  # the columns of text, which wrap; the time stays on one line


class ExportsPage(QWidget):
    """The table of exports; ``open_requested`` carries the key of the one
    whose view should open."""

    open_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE["lg"], SPACE["lg"], SPACE["lg"], SPACE["lg"])
        layout.setSpacing(SPACE["sm"])
        note = set_role(QLabel("Every file the app writes, where it is made and what is written with it. Enter or "
                               "a double-click opens the view that makes one."), tone="secondary")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.table = DataTable("No exports.")
        # No sideways scroll at 1280 px (UI-27); the text columns wrap, so every entry reads whole (UI audit B12).
        self.table.set_fit_width(wrap=_WRAPPED)
        self.table.view.activated.connect(self._on_activated)
        layout.addWidget(self.table, 1)
        export_log.signals.changed.connect(self._on_logged)
        self._stale = False
        self.refresh()

    def refresh(self) -> None:
        """The table again, with the times of the export log."""
        rows = []
        for export in EXPORTS:
            last = export_log.last(export.key)
            when, path = last if last is not None else ("never", "")
            tooltips = {5: export.provenance_detail} if export.provenance_detail else {}
            if path:
                tooltips[_LAST] = path
            rows.append(Row((export.name, when, export.file_format, export.made_in, export.destination,
                             export.provenance), tooltips=tooltips))
        self.table.set_table(_HEADERS, rows, stretch=-1)  # fitted to the page; the last column takes what is left
        self._stale = False

    def last_written(self, key: str) -> str:
        """The "Last written" cell of export ``key``."""
        return self.table.cell([export.key for export in EXPORTS].index(key), _LAST)

    def _on_logged(self, _key: str) -> None:
        if self.isVisible():
            self.refresh()
        else:
            self._stale = True  # refreshed when shown

    def showEvent(self, event) -> None:
        if self._stale:
            self.refresh()
        super().showEvent(event)

    def _on_activated(self, index) -> None:
        row = self.table.proxy.mapToSource(index).row()
        self.open_requested.emit(EXPORTS[row].key)
