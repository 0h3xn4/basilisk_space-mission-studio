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
"""Tests for gui.background_threads (SRelD K-44, K-40): garbage is
collected on the GUI thread only, the heavy first imports off the GUI
thread take turns, and the window's workers do not outrank the GUI
thread."""

import dataclasses
import threading
from pathlib import Path

import pytest

pytestmark = pytest.mark.requires_gui


@dataclasses.dataclass
class _Row:
    value: float
    items: list


def _drop_widgets_in_a_cycle(count: int, destroyed_on: list) -> None:
    """``count`` widgets, each with a child, that only the cyclic garbage
    collector can free; each notes on which thread it went."""
    from PySide6.QtWidgets import QLabel, QWidget

    class Dropped(QWidget):
        def __del__(self):
            destroyed_on.append(threading.current_thread().name)

    for _ in range(count):
        widget = Dropped()
        QLabel("child", widget)
        widget.cycle = widget


def test_a_collection_in_a_worker_thread_never_destroys_a_widget(qtbot):
    """CI (Windows, the 3D step): an access violation in the thread
    ``_SpaceWeatherWarmUp`` while it was "Garbage-collecting" in a
    dataclass ``__init__``. A worker that allocates passes the collector's
    threshold, and the collection destroyed widgets of the GUI thread in
    that worker. With the collection on the GUI thread, the worker
    destroys none; the GUI thread's collector frees them."""
    import gc

    from PySide6.QtCore import QThread

    from spacemissionstudio.gui import background_threads

    background_threads.install()
    gc.collect()
    destroyed_on: list = []
    _drop_widgets_in_a_cycle(20, destroyed_on)

    class Rows(QThread):
        def run(self):
            self.setObjectName("rows")
            rows = [_Row(float(i), [i]) for i in range(100_000)]
            assert len(rows) == 100_000

    worker = Rows()
    worker.start()
    assert worker.wait(30_000)  # [ms]
    assert destroyed_on == [], "a worker thread destroyed widgets of the GUI thread"
    kept = [[i] for i in range(3 * gc.get_threshold()[0])]  # the GUI thread allocates: a collection is due
    qtbot.waitUntil(lambda: len(destroyed_on) == 20, timeout=5000)  # [ms]
    assert set(destroyed_on) == {threading.main_thread().name} and len(kept) > 0


def test_the_collection_that_is_due_is_the_one_the_thresholds_name(monkeypatch):
    """collect_due() collects as the automatic collection would: nothing
    while the young generation is under its threshold, else the oldest
    generation whose count is over its threshold."""
    import gc

    from spacemissionstudio.gui import background_threads

    collected = []
    state = {"counts": (0, 0, 0), "thresholds": (2000, 10, 10)}
    monkeypatch.setattr(gc, "get_count", lambda: state["counts"])
    monkeypatch.setattr(gc, "get_threshold", lambda: state["thresholds"])
    monkeypatch.setattr(gc, "collect", lambda generation=2: collected.append(generation))
    expected = {(150, 3, 0): None, (2001, 3, 0): 0, (2001, 11, 0): 1, (2001, 11, 11): 2, (2001, 3, 11): 2}
    for counts, generation in expected.items():
        state["counts"] = counts
        assert background_threads.collect_due() == generation, counts
    state["thresholds"] = (0, 10, 10)  # gc.set_threshold(0): collection off
    state["counts"] = (5000, 50, 50)
    assert background_threads.collect_due() is None
    assert collected == [0, 1, 2, 2]


def test_install_turns_the_automatic_collection_off_and_uninstall_gives_it_back(qapp):
    """The window collects on its own thread from its start; the tests'
    fixture gives the automatic collection back after each window test."""
    import gc

    from PySide6.QtCore import QObject

    from spacemissionstudio.gui import background_threads

    background_threads.uninstall()
    assert gc.isenabled() and not background_threads.is_installed()
    assert qapp.findChild(QObject, "guiThreadGarbageCollector") is None
    background_threads.install(qapp)
    background_threads.install(qapp)  # a second call adds no second collector
    assert background_threads.is_installed() and not gc.isenabled()
    assert len(qapp.findChildren(QObject, "guiThreadGarbageCollector")) == 1
    gc.enable()  # something turned it on again: install() turns it off
    background_threads.install(qapp)
    assert not gc.isenabled()
    background_threads.uninstall()
    assert gc.isenabled() and qapp.findChild(QObject, "guiThreadGarbageCollector") is None
    background_threads.install(qapp)  # as the fixture left it


def test_install_refuses_a_worker_thread(qapp):
    """The collector is the GUI thread's: install() from a worker fails."""
    from PySide6.QtCore import QThread

    from spacemissionstudio.gui import background_threads

    errors = []

    class Installer(QThread):
        def run(self):
            try:
                background_threads.install(qapp)
            except RuntimeError as exc:
                errors.append(str(exc))

    installer = Installer()
    installer.start()
    assert installer.wait(10_000)  # [ms]
    assert errors == ["install() must run on the GUI thread"]


def test_install_raises_the_gui_thread_and_the_window_s_workers_start_at_normal_priority(qapp):
    """SRelD K-40: from install() on, the GUI thread has Chromium's priority
    (its GPU and compositor threads and the software rasteriser's), and
    uninstall() gives it back its normal one. A worker of the window
    (WorkerThread, worker_pool) starts at normal priority, not at the
    priority of the GUI thread that starts it."""
    import os
    import sys

    from PySide6.QtCore import QThread

    from spacemissionstudio.gui import background_threads

    linux = sys.platform.startswith("linux")

    def nice():
        """The calling thread's nice value (Linux), else None."""
        return os.getpriority(os.PRIO_PROCESS, 0) if linux else None

    gui = QThread.currentThread()
    background_threads.uninstall()
    own_nice = nice()
    background_threads.install(qapp)
    assert gui.priority() == background_threads.GUI_THREAD_PRIORITY == QThread.Priority.HighPriority
    if linux:  # Chromium's nice value where the process may lower it (root), else the thread's own
        assert nice() in (min(background_threads.GUI_THREAD_NICE, own_nice), own_nice)
    seen = []

    class Worker(background_threads.WorkerThread):
        def run(self):
            seen.append((QThread.currentThread().priority(), nice()))

    worker = Worker()
    worker.start()
    assert worker.wait(10_000)  # [ms]
    pool = background_threads.worker_pool(qapp)
    assert (pool.maxThreadCount(), pool.threadPriority()) == (1, QThread.Priority.NormalPriority)
    pool.start(lambda: seen.append((QThread.currentThread().priority(), nice())))
    assert pool.waitForDone(10_000)  # [ms]
    assert seen == [(QThread.Priority.NormalPriority, own_nice)] * 2
    background_threads.uninstall()
    assert gui.priority() == QThread.Priority.NormalPriority and nice() == own_nice
    background_threads.install(qapp)  # as the fixture left it


def test_every_worker_of_the_window_starts_at_normal_priority():
    """Every QThread and thread pool of the window is a WorkerThread or a
    worker_pool: a plain QThread or QThreadPool would start at the GUI
    thread's raised priority (SRelD K-40)."""
    import re

    import spacemissionstudio.gui as gui

    found = []
    for path in sorted(Path(gui.__file__).parent.rglob("*.py")):
        if path.name == "background_threads.py":
            continue
        text = path.read_text(encoding="utf-8")
        found += [f"{path.name}: {match}" for match in re.findall(r"\(QThread\):|QThreadPool\(", text)]
    assert found == []


def test_the_window_s_start_collects_on_the_gui_thread_before_any_worker():
    """main() installs the collector right after it makes the application,
    before the window (whose start-up read starts the warm-ups)."""
    import inspect

    from spacemissionstudio.gui.app import main

    source = inspect.getsource(main)
    assert "background_threads.install(app)" in source
    assert source.index("QApplication(") < source.index("background_threads.install(app)") < source.index(
        "MainWindow()")


@pytest.mark.parametrize("which", ["space weather", "figures", "run"])
def test_the_warm_ups_and_a_run_s_first_import_take_turns(qtbot, monkeypatch, which):
    """CI's access violation came with three threads making heavy first
    imports at once (the space-weather and figure warm-ups, a run's
    engine). Each holds FIRST_IMPORTS for its imports, so they take turns:
    while it is held, none of them starts its work."""
    import sys
    import types

    from spacemissionstudio.engine import spaceweather
    from spacemissionstudio.gui import background_threads, data_panel_widget, results_widget
    from spacemissionstudio.gui.run_worker import RunWorker

    started = threading.Event()

    def note(*_args, **_kwargs):
        started.set()
        raise RuntimeError("stop here")

    if which == "space weather":
        monkeypatch.setattr(spaceweather, "real_data_path", note)
        thread = data_panel_widget._SpaceWeatherWarmUp()
    elif which == "figures":
        monkeypatch.setattr(results_widget, "warm_up_figures", note)
        thread = data_panel_widget._FigureWarmUp()
    else:
        service = types.ModuleType("spacemissionstudio.engine.service")
        service.SimulationCancelled = type("SimulationCancelled", (Exception,), {})
        service.SimulationService = note
        monkeypatch.setitem(sys.modules, "spacemissionstudio.engine.service", service)
        thread = RunWorker(None)
    with background_threads.FIRST_IMPORTS:
        thread.start()
        assert not started.wait(0.3)  # [s]
        assert thread.isRunning()
    assert started.wait(10.0)  # [s]
    assert thread.wait(10_000)  # [ms]


def test_filters_that_only_their_parent_refers_to_keep_no_python_attribute(qtbot):
    """The page tree's refit filter and the tool button's icon keeper are
    children that only their parent refers to, and Qt calls them: a new
    wrapper would have none of the old one's attributes (the toast
    follower on CI, B11). So they keep none and read their parent; both
    still work."""
    from PySide6.QtCore import QEvent, SignalInstance
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QApplication, QToolButton

    from spacemissionstudio.gui import theme
    from spacemissionstudio.gui.page_tree import PageTree, _Refit
    from spacemissionstudio.gui.theme.icons import _KeepIcon, keep_icon

    def own_attributes(obj) -> list:
        return [name for name, value in vars(obj).items() if not isinstance(value, SignalInstance)]

    tree = PageTree()
    qtbot.addWidget(tree)
    refits = tree.findChildren(_Refit)
    assert len(refits) == 1 and own_attributes(refits[0]) == []
    asked = []
    tree.fit_width_later = lambda: asked.append(True)
    QApplication.sendEvent(tree.tree, QEvent(QEvent.Type.FontChange))
    assert asked

    button = QToolButton()
    qtbot.addWidget(button)
    kept = theme.icon("play", "text.on_accent")
    keep_icon(button, kept)
    keepers = button.findChildren(_KeepIcon)
    assert len(keepers) == 1 and own_attributes(keepers[0]) == []
    action = QAction("Run", button)
    action.setIcon(theme.icon("square", "text.secondary"))
    button.setDefaultAction(action)
    action.setText("Run again")
    qtbot.waitUntil(lambda: button.icon().cacheKey() == kept.cacheKey(), timeout=2000)  # [ms]
