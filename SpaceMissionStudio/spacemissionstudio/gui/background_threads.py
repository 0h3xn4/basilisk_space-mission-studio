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

"""Three things the window's background threads must not do on their own
(SRelD K-44, K-40): collect garbage, make the heavy first imports
together, and take the processors from the GUI thread.

**Garbage collection on the GUI thread only.** Python's cyclic garbage
collector runs in the thread that allocates when a generation passes its
threshold, and it frees every unreachable cycle, whichever thread made it.
A widget made on the GUI thread that ends in a reference cycle (a window a
test dropped, a dialog with a lambda that refers to it) was so destroyed in
a worker thread that only parsed a file or wrote a CSV file, while the GUI
thread used it. Qt objects are not thread safe: the process crashed. CI
showed it on Windows (an access violation in ``_SpaceWeatherWarmUp``,
"Garbage-collecting", in a dataclass ``__init__``) and a short script with
a worker that makes dataclass rows crashes the same way on Linux.

:func:`install` turns the automatic collection off and collects on the GUI
thread instead: every :data:`COLLECT_INTERVAL_MS` it checks the collector's
counts against its thresholds and collects the generation that is due
(:func:`collect_due`), as the automatic collection would. An explicit
``gc.collect()`` still runs where it is called.

**One heavy first import at a time.** The start-up warm-ups (the
space-weather file, plotly's figure classes) and a run's first import of
the engine each import large packages. CPython's import is thread safe, so
this is not known to crash. They take :data:`FIRST_IMPORTS` all the same,
so that they do not import at the same time and the warm-ups do not compete
with each other for the interpreter.

**pandas, imported in a worker.** A Monte Carlo batch's worker and the
worker of a case run again need pandas (Basilisk's Monte Carlo controller
imports it). The first import takes about 0.25 s, so the worker makes it
(:func:`import_pandas`, with :data:`FIRST_IMPORTS` held), not the GUI
thread. But plotly and narwhals find pandas with ``sys.modules.get`` and do
not wait for an import in progress: a plot built meanwhile read the half
made module ("partially initialized module 'pandas'", Windows CI,
2026-10-28). The lock keeps the figure warm-up away from that import; the
GUI thread cannot hold the lock (it would wait for the warm-ups too), so
the window's plots call :func:`wait_for_pandas` before plotly runs.

**The GUI thread first.** Without a graphics card, Chromium draws the 3D
View's WebGL in software (on Windows WARP, "Microsoft Basic Render
Driver"), with one thread per processor. On the Windows runner those
threads and Chromium's GPU, compositor and IO threads ran above normal
priority, and the GUI thread at normal. While the page drew a frame
(about 30 ms at reduced quality, after each move of the view or change of
its size), Windows gave the GUI thread no processor, and a move of the 3D
View into its own window took up to 64 ms (SRelD K-40). :func:`install`
gives the GUI thread the priority of those threads
(:data:`GUI_THREAD_PRIORITY`). Linux has nice values instead: a process
that may lower them (as root) gives the GUI thread Chromium's
(:data:`GUI_THREAD_NICE`); for others, Chromium cannot lower its own either,
and nothing changes. A new thread starts at the priority of the thread
that starts it, so the window's workers go back to normal priority
(:class:`WorkerThread`, :func:`worker_pool`): a run or a study does not
take the processors from other programs or from the 3D View's drawing.
"""

from __future__ import annotations

import gc
import os
import sys
import threading

from PySide6.QtCore import QCoreApplication, QObject, Qt, QThread, QThreadPool

# How often the GUI thread checks whether a collection is due. Between two
# checks the young generation grows past its threshold by what the threads
# allocate in that time, and one collection then takes all of it: with the
# warm-ups and a run, 100 ms gave collections of up to 91-189 ms, 20 ms
# gave at most 29-43 ms (as without this module). A check that finds
# nothing due costs microseconds.
COLLECT_INTERVAL_MS = 20  # [ms]

#: The GUI thread's priority from :func:`install` on: the one of Chromium's
#: GPU, compositor and IO threads and of the software rasteriser's threads.
GUI_THREAD_PRIORITY = QThread.Priority.HighPriority
#: A worker's priority (:class:`WorkerThread`, :func:`worker_pool`).
WORKER_PRIORITY = QThread.Priority.NormalPriority
#: Linux has no priorities for normal threads, only nice values: Chromium
#: gives its display threads this one when the process may (as root), and
#: the software rasteriser's threads take it from its GPU thread (measured).
GUI_THREAD_NICE = -8

# Held for a heavy first import made off the GUI thread (the warm-ups, a run's engine, pandas).
FIRST_IMPORTS = threading.Lock()

_COLLECTOR_NAME = "guiThreadGarbageCollector"


def import_pandas() -> None:
    """Import pandas, with :data:`FIRST_IMPORTS` held: a worker's first
    import of it, off the GUI thread (about 0.25 s once per process).
    Without pandas (no Basilisk) nothing happens; the worker's next import
    reports Basilisk missing."""
    with FIRST_IMPORTS:
        try:
            import pandas  # noqa: F401
        except ImportError:
            pass


def wait_for_pandas() -> None:
    """Before plotly builds or writes a figure: when another thread is
    importing pandas, wait until that import is done. plotly would read the
    half-made module from ``sys.modules`` and fail (see the module's
    docstring). Python's import waits on the module's own lock, so this
    waits for the rest of that import only, and only when a plot is drawn
    during it; otherwise it costs one dictionary look-up."""
    module = sys.modules.get("pandas")
    if module is not None and getattr(getattr(module, "__spec__", None), "_initializing", False):
        import pandas  # noqa: F401 -- waits for the other thread's import

# The collector object, kept so that its Python wrapper lives as long as the
# application (a child of it: Qt deletes it with the application).
_state: dict = {"collector": None, "was_enabled": None, "nice": None}


def collect_due() -> int | None:
    """Collect the oldest generation whose count is over its threshold,
    when the young generation's is (the rule of the automatic collection);
    return the generation collected, or None when none was due."""
    counts = gc.get_count()
    thresholds = gc.get_threshold()
    if not thresholds[0] or counts[0] <= thresholds[0]:
        return None
    generation = 0
    for older in (1, 2):
        if thresholds[older] and counts[older] > thresholds[older]:
            generation = older
    gc.collect(generation)
    return generation


def _set_nice(nice: int) -> None:
    """The calling thread's nice value on Linux, where the system allows it
    (a lower value needs root); nothing elsewhere."""
    if sys.platform.startswith("linux"):
        try:
            os.setpriority(os.PRIO_PROCESS, threading.get_native_id(), nice)
        except OSError:  # not allowed: the thread keeps its value
            pass


def _normal_nice() -> None:
    """A worker's nice value back to the process's own (Linux)."""
    if _state["nice"] is not None:
        _set_nice(_state["nice"])


class WorkerThread(QThread):
    """A thread of the window's own work. It starts at normal priority
    (:data:`WORKER_PRIORITY`), not at the GUI thread's, which it would
    take from the thread that starts it."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.started.connect(_normal_nice, Qt.ConnectionType.DirectConnection)  # in the new thread

    def start(self, priority: QThread.Priority = WORKER_PRIORITY) -> None:
        super().start(priority)


class _WorkerPool(QThreadPool):
    """The pool of :func:`worker_pool`: each task first gives its thread the
    process's own nice value back (Linux)."""

    def start(self, task, priority: int = 0) -> None:
        if callable(task):
            work = task

            def task() -> None:
                _normal_nice()
                work()

        super().start(task, priority)


def worker_pool(parent: QObject | None = None, max_threads: int = 1) -> QThreadPool:
    """A thread pool of the window's own work, with ``max_threads`` threads
    (one by default: one task after the other) at normal priority, as
    :class:`WorkerThread`. A task is a callable."""
    pool = _WorkerPool(parent)
    pool.setMaxThreadCount(max_threads)
    pool.setThreadPriority(WORKER_PRIORITY)
    return pool


class _Collector(QObject):
    """Calls :func:`collect_due` on the GUI thread every
    :data:`COLLECT_INTERVAL_MS`. It keeps no Python attribute (the toast
    follower's lesson, B11): its timer is its own."""

    def __init__(self, app: QCoreApplication) -> None:
        super().__init__(app)
        self.setObjectName(_COLLECTOR_NAME)
        self.startTimer(COLLECT_INTERVAL_MS)

    def timerEvent(self, _event) -> None:  # noqa: N802 -- Qt API name
        collect_due()


def _live_collector() -> _Collector | None:
    from shiboken6 import isValid

    collector = _state["collector"]
    return collector if collector is not None and isValid(collector) else None


def install(app: QCoreApplication | None = None) -> None:
    """Collect garbage on the GUI thread only, from now on: turn the
    automatic collection off and start the collector, a child of ``app``
    (the running application by default), and give the GUI thread
    :data:`GUI_THREAD_PRIORITY`. Call it on the GUI thread; a second call
    changes nothing but turns the automatic collection off again if
    something turned it on."""
    app = app or QCoreApplication.instance()
    if app is None:
        raise RuntimeError("install() needs the application")
    if QThread.currentThread() is not app.thread():
        raise RuntimeError("install() must run on the GUI thread")
    if _live_collector() is None:
        if _state["was_enabled"] is None:
            _state["was_enabled"] = gc.isenabled()
        _state["collector"] = _Collector(app)
    gc.disable()
    QThread.currentThread().setPriority(GUI_THREAD_PRIORITY)
    if sys.platform.startswith("linux"):
        if _state["nice"] is None:
            _state["nice"] = os.getpriority(os.PRIO_PROCESS, 0)  # this thread's own on Linux
        _set_nice(min(GUI_THREAD_NICE, _state["nice"]))


def uninstall() -> None:
    """Stop the collector and give the automatic collection back as it was
    before :func:`install`, and the GUI thread its normal priority (the
    tests' fixture: the tests without a window run as before)."""
    from shiboken6 import delete

    QThread.currentThread().setPriority(QThread.Priority.NormalPriority)
    if _state["nice"] is not None:
        _set_nice(_state["nice"])
        _state["nice"] = None

    collector = _live_collector()
    _state["collector"] = None
    if collector is not None:
        delete(collector)  # on the GUI thread, as install() made it
    if _state["was_enabled"]:
        gc.enable()
    _state["was_enabled"] = None


def is_installed() -> bool:
    """Whether the collector runs (and the automatic collection is off)."""
    return _live_collector() is not None and not gc.isenabled()
