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

"""Two things the window's background threads must not do on their own
(SRelD K-44): collect garbage, and make the heavy first imports together.

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
"""

from __future__ import annotations

import gc
import threading

from PySide6.QtCore import QCoreApplication, QObject, QThread

# How often the GUI thread checks whether a collection is due. Between two
# checks the young generation grows past its threshold by what the threads
# allocate in that time, and one collection then takes all of it: with the
# warm-ups and a run, 100 ms gave collections of up to 91-189 ms, 20 ms
# gave at most 29-43 ms (as without this module). A check that finds
# nothing due costs microseconds.
COLLECT_INTERVAL_MS = 20  # [ms]

# Held for a heavy first import made off the GUI thread (the warm-ups, a run's engine).
FIRST_IMPORTS = threading.Lock()

_COLLECTOR_NAME = "guiThreadGarbageCollector"

# The collector object, kept so that its Python wrapper lives as long as the
# application (a child of it: Qt deletes it with the application).
_state: dict = {"collector": None, "was_enabled": None}


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
    (the running application by default). Call it on the GUI thread; a
    second call changes nothing but turns the automatic collection off
    again if something turned it on."""
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


def uninstall() -> None:
    """Stop the collector and give the automatic collection back as it was
    before :func:`install` (the tests' fixture: the tests without a window
    run with the automatic collection)."""
    from shiboken6 import delete

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
