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

"""The Monte Carlo view's Statistics and Sensitivity tabs (Monte Carlo plan
B3 and B2): their worker, their plots and their tables' rows.

* :class:`InsightComputer` computes ``engine.monte_carlo_statistics.insight``
  of a batch off the GUI thread: a batch can hold 100 000 runs, and its
  ranks and percentiles take longer than design rule 6 allows.
* :class:`ReportWriter` writes a batch's report (plan B5) off the GUI
  thread.
* :class:`InsightPlot` shows one Plotly figure. Its web view is made
  the first time it has a figure to show (an idle web view costs a
  Chromium renderer). It builds the figure again in the new theme's
  colours on a theme change.
* :func:`ecdf_figure` and :func:`scatter_figure` make the two figures with
  the theme's Plotly template; the axis titles carry the units. They build
  Plotly's JSON form directly (:func:`figure_json`), fast enough for the
  GUI thread with 100 000 runs (decision MC-30).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtWidgets import QLabel, QStackedWidget, QVBoxLayout, QWidget

from .. import temp_folders
from ..engine import monte_carlo_report
from ..engine import monte_carlo_statistics as mcs
from .theme import SERIES_COLORS, TOKENS, on_change, set_role
from .theme import plotly_template as pt

logger = logging.getLogger(__name__)

# Above this many points a plot draws with WebGL (Scattergl): SVG markers of 100 000 runs are slow to draw.
WEBGL_POINTS = 5000
# The cells' text is the engine's, so the batch report and the command line read as the view (plan B5).
NO_VALUE, number_text, percentile_title = mcs.NO_VALUE, mcs.number_text, mcs.percentile_title


class InsightComputer(QObject):
    """Works out :func:`engine.monte_carlo_statistics.insight` of a batch in
    one serial worker (a ``QThreadPool`` of one thread, as the ground map's
    renderer). A request made while one is worked out waits; a newer one
    replaces it. ``ready(batch, insight, error)`` arrives on the GUI thread
    (``insight`` None and ``error`` its text when it failed). The pool waits
    for its job when it is deleted, so a closed view never leaves a thread
    running."""

    ready = Signal(object, object, str)
    _done = Signal(object, object, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self.compute: Callable = mcs.insight  # what the worker runs (a test may replace it)
        self.busy = False
        self._pending = None
        self._done.connect(self._on_done)

    def request(self, batch) -> None:
        if self.busy:
            self._pending = batch
            return
        self._start(batch)

    def wait(self) -> None:
        """Until the job in progress is done (tests, closing)."""
        self._pool.waitForDone()

    def _start(self, batch) -> None:
        self.busy = True
        compute = self.compute
        self._pool.start(lambda: self._work(compute, batch))

    def _work(self, compute: Callable, batch) -> None:
        try:
            result, error = compute(batch), ""
        except Exception as exc:  # noqa: BLE001 -- said in the tab, never a crash of the window
            result, error = None, f"{type(exc).__name__}: {exc}"
        try:
            self._done.emit(batch, result, error)
        except RuntimeError:  # the view was closed meanwhile
            pass

    def _on_done(self, batch, result, error: str) -> None:
        self.busy = False
        if self._pending is not None:  # a newer batch was asked for: only its result is wanted
            batch, self._pending = self._pending, None
            self._start(batch)
            return
        self.ready.emit(batch, result, error)


class ReportWriter(QObject):
    """Writes a batch's report (``engine.monte_carlo_report.write``, Monte
    Carlo plan B5) in one serial worker, so the GUI thread neither works out
    the statistics nor writes the file (design rule 6). ``written(path,
    error)`` arrives on the GUI thread (``error`` "" when the file is
    written). The pool waits for its job when it is deleted."""

    written = Signal(object, str)
    _done = Signal(object, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self.write: Callable = monte_carlo_report.write  # what the worker runs (a test may replace it)
        self.pending = 0  # reports asked for and not yet written
        self._done.connect(self._on_done)

    def request(self, batch, path: Path, folder: Path | None, insight=None) -> None:
        self.pending += 1
        write = self.write
        self._pool.start(lambda: self._work(write, batch, path, folder, insight))

    def wait(self) -> None:
        """Until the reports asked for are written (tests, closing)."""
        self._pool.waitForDone()

    def _work(self, write: Callable, batch, path: Path, folder: Path | None, insight) -> None:
        try:
            write(batch, path, folder, insight)
            error = ""
        except (OSError, ValueError, monte_carlo_report.MonteCarloReportError) as exc:
            error = str(exc)
        except Exception as exc:  # noqa: BLE001 -- said in a toast and the Log, never a crash of the window
            error = f"{type(exc).__name__}: {exc}"
        try:
            self._done.emit(path, error)
        except RuntimeError:  # the view was closed meanwhile
            pass

    def _on_done(self, path, error: str) -> None:
        self.pending -= 1
        self.written.emit(path, error)


# -- the figures --------------------------------------------------------------------------------
#
# A figure is Plotly's JSON form, a dict: {"data": [trace, ...], "layout": {...}}. The layout goes
# through plotly's own Layout (a few keys: it is checked and its short names nested); the traces are
# written directly, their arrays as Plotly's typed arrays (base64), so that a batch of 100 000 runs
# builds its figure in a few milliseconds on the GUI thread (go.Figure checks every value: about 25 ms
# for a scatter of 100 000 points and 75 ms for their distribution, measured here).


def _typed(values: np.ndarray) -> dict:
    """``values`` as a Plotly typed array: little-endian 8-byte floats, or 4-byte integers."""
    import base64

    if np.issubdtype(values.dtype, np.integer):
        data, dtype = np.ascontiguousarray(values, dtype="<i4"), "i4"
    else:
        data, dtype = np.ascontiguousarray(values, dtype="<f8"), "f8"
    return {"dtype": dtype, "bdata": base64.b64encode(data.tobytes()).decode("ascii")}


def figure_json(figure: dict) -> str:
    """``figure`` as the JSON the plot page takes (``plot_page.build_page``)."""
    import json

    def encode(value):
        if isinstance(value, np.ndarray):
            return _typed(value)
        if isinstance(value, np.generic):
            return value.item()
        raise TypeError(f"{type(value).__name__} is not JSON")

    return json.dumps(figure, default=encode)


def _layout(title: str, subtitle: str, x_title: str, y_title: str, **extra) -> dict:
    import plotly.graph_objects as go

    from .background_threads import wait_for_pandas
    from .results_widget import _template_layout

    axis = dict(pt.axis(TOKENS), separatethousands=True)
    wait_for_pandas()  # plotly reads pandas; a batch's worker may be importing it (SRelD K-44)
    layout = go.Layout(**_template_layout(), title=pt.title(TOKENS, title, subtitle),
                       xaxis=dict(axis, title_text=x_title), yaxis=dict(axis, title_text=y_title, **extra),
                       showlegend=False, margin=dict(l=70, r=30, t=70, b=60))
    return layout.to_plotly_json()


def _trace_type(points: int) -> str:
    return "scattergl" if points > WEBGL_POINTS else "scatter"


def ecdf_figure(column: mcs.Column, title: str, subtitle: str) -> dict:
    """The empirical distribution of ``column``'s finite values as a step
    plot: 0 below the smallest value, rising at each value by the share of
    runs that have it, 1 from the largest on."""
    x, fraction = mcs.ecdf(column.values)
    xs = np.concatenate([x[:1], x]) if x.size else x
    ys = np.concatenate([[0.0], fraction]) if x.size else fraction
    trace = {"type": _trace_type(xs.size), "x": xs, "y": ys, "mode": "lines", "name": column.name,
             "line": {"shape": "hv", "width": 2, "color": SERIES_COLORS[0]},
             "hovertemplate": "%{x:.6g}: %{y:.3f} of the runs at or below<extra></extra>"}
    return {"data": [trace], "layout": _layout(title, subtitle, column.label, "Fraction of runs at or below [-]",
                                               range=[0.0, 1.02])}


def scatter_figure(x: mcs.Column, y: mcs.Column, runs, title: str, subtitle: str, x_title: str,
                   y_title: str) -> dict:
    """Each run that recorded both, as a point: ``x``'s drawn value against
    ``y``'s outcome; the run's number in its hover text."""
    both = np.isfinite(x.values) & np.isfinite(y.values)
    numbers = np.asarray(runs, dtype=int)[both] if len(runs) == both.size else np.flatnonzero(both)
    trace = {"type": _trace_type(int(both.sum())), "x": x.values[both], "y": y.values[both], "mode": "markers",
             "customdata": numbers, "name": y.name,
             "marker": {"size": 6, "color": SERIES_COLORS[0], "opacity": 0.8},
             "hovertemplate": "Run %{customdata}: %{x:.6g}, %{y:.6g}<extra></extra>"}
    return {"data": [trace], "layout": _layout(title, subtitle, x_title, y_title)}


# -- the plot view ------------------------------------------------------------------------------


def write_page(figure: dict, plotly_js: str, style: str, page: Path) -> str:
    """Write the plot page of ``figure`` to ``page``: the work of
    :class:`InsightPlot` that runs in its worker. Returns an error's text,
    or "" when the page was written."""
    from . import plot_page

    try:
        html = plot_page.build_page([figure_json(figure)], "1x1", 0, [False], plotly_js, style)
        if not page.parent.is_dir():  # the view was closed and its folder removed
            return "the plot folder is gone"
        page.write_text(html, encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 -- said in the view, never a crash of the window
        return f"{type(exc).__name__}: {exc}"
    return ""


def _remove(page: str) -> None:
    """Delete a plot page that is no longer shown; a file the web view still
    holds open (Windows) stays until its folder is removed."""
    try:
        Path(page).unlink(missing_ok=True)
    except OSError:
        pass


class InsightPlot(QWidget):
    """One figure in a web view made when it is first needed. :meth:`show`
    takes a function that builds the figure in the current theme;
    :meth:`clear` shows ``empty`` instead. A theme change builds it again.

    The figure is built on the GUI thread (plotly checks its layout there,
    as for every other plot); its JSON, the page around it and the page's
    file, megabytes for a batch of 100 000 runs, are made in one serial
    worker (:func:`write_page`). On the Windows CI runner that part took
    50 to 100 ms, above the 50 ms of design rule 6. Only the newest
    page is shown: a page that an older request wrote is not loaded."""

    _written = Signal(int, str, str)

    def __init__(self, empty: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._request = 0  # the number of the newest page asked for
        self.page_error = ""  # the last page's error, for tests and the log
        self._shown_page = ""  # the file of the page in the web view
        self._written.connect(self._on_written)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)
        self.empty_label = set_role(QLabel(empty), tone="secondary")
        self.empty_label.setWordWrap(True)
        self.stack.addWidget(self.empty_label)
        self.web_view = None  # made by the first figure
        self.figure = None  # the figure shown (Plotly's JSON form, a dict), for tests
        self._build: Callable | None = None
        self._page_dir = None
        on_change(self._on_theme_changed)

    def show_figure(self, build: Callable) -> None:
        """Show ``build()``, a figure (:func:`figure_json`'s dict) in the current theme."""
        self._build = build
        self._draw()

    def clear(self, empty: str | None = None) -> None:
        self._build, self.figure = None, None
        self._request += 1  # a page still being written is not shown
        if empty is not None:
            self.empty_label.setText(empty)
        self.stack.setCurrentWidget(self.empty_label)

    def _draw(self) -> None:
        if self._build is None:
            return
        from .results_widget import _page_style, _plotlyjs_path

        self.figure = self._build()
        if self.web_view is None:
            from . import webengine_setup  # sets the Chromium flags, before QtWebEngine is imported
            from PySide6.QtWebEngineWidgets import QWebEngineView

            webengine_setup.guard_profile()  # the app's own pages only (network.md)
            self.web_view = QWebEngineView()
            self.stack.addWidget(self.web_view)
            self._page_dir = temp_folders.temporary_directory(temp_folders.PLOT_PAGE)
        self._request += 1
        request, figure = self._request, self.figure
        plotly_js = QUrl.fromLocalFile(str(_plotlyjs_path())).toString()
        style = _page_style()  # the theme's, read here on the GUI thread
        page = Path(self._page_dir.name) / f"monte_carlo_insight_{request}.html"
        self._pool.start(lambda: self._write(request, figure, plotly_js, style, page))

    def _write(self, request: int, figure: dict, plotly_js: str, style: str, page: Path) -> None:
        error = write_page(figure, plotly_js, style, page)
        try:
            self._written.emit(request, str(page), error)
        except RuntimeError:  # the view was closed meanwhile
            pass

    def _on_written(self, request: int, page: str, error: str) -> None:
        if request != self._request or self.web_view is None:
            _remove(page)  # a newer figure was asked for, or the plot was cleared
            return
        self.page_error = error
        if error:
            logger.warning("Monte Carlo plot page not written: %s", error)
            return
        self.web_view.load(QUrl.fromLocalFile(page))
        self.stack.setCurrentWidget(self.web_view)
        if self._shown_page and self._shown_page != page:
            _remove(self._shown_page)  # the page shown before: a few megabytes each
        self._shown_page = page

    def wait(self) -> None:
        """Until the page being written is written (tests, closing)."""
        self._pool.waitForDone()

    def _on_theme_changed(self, _mode: str) -> None:
        """Build the figure again in the new theme, after the switch itself has returned."""
        if self._build is not None:
            QTimer.singleShot(0, self, self._draw)
