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
"""Signals sent while Python's collector frees a widget tree (SRelD K-44).

The collector frees a dropped widget tree one Python wrapper at a time, and
shiboken can then delete a child before its parent. A ``QListWidget``'s
model resets while the list is deleted, and a tab widget changes its current
page when a page goes. Such a signal reached a method of an owner whose
wrapper the collector had already cleared: "Slot 'EmptyStack::' not found"
(the first test of a process), "Slot 'MainWindow::' not found" (CI). The
owners now connect these signals with ``widgets.connect_while_alive``.

The scripts run in a fresh interpreter, so the widget is the first of its
process and nothing else is collected with it.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.requires_gui

_ROOT = Path(__file__).resolve().parents[2]

_START = """
import gc
from PySide6.QtWidgets import QApplication, QListWidget, QVBoxLayout, QWidget
app = QApplication([])
gc.disable()  # one collection, below
"""

# A list in an EmptyStack, the list also held by another widget, the page in
# a reference cycle: only the collector frees it.
_EMPTY_STACK = _START + """
from spacemissionstudio.gui.widgets import EmptyStack, EmptyState

class Page(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        self.list_stack = EmptyStack(self.list_widget, EmptyState("Nothing", "Add one."))
        layout.addWidget(self.list_stack)
        self.holder = QWidget(self)
        self.holder.list_widget = self.list_widget
        self.holder.page = self

page = Page()
del page
gc.collect()
print("collected")
"""

_REQUIREMENTS = _START + """
from spacemissionstudio.gui.monte_carlo_editor import MonteCarloGroupWidget

widget = MonteCarloGroupWidget()
widget.requirement_list.set_spacecraft_names(["sat-1"])
widget.to_dataclass()
widget.cycle = widget
del widget
gc.collect()
print("collected")
"""

# The main window's shape: its view tabs, a page also held elsewhere, the
# window's own method on the tabs' currentChanged.
_TABS = _START + """
from PySide6.QtWidgets import QLabel
from spacemissionstudio.gui.widgets import TabWidget, connect_while_alive

class Window(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.page = QLabel("a page")
        self.views = TabWidget()
        self.views.page = self.page
        self.views.addTab(self.page, "Page")
        self.views.addTab(QLabel("another page"), "Other")
        layout.addWidget(self.views)
        connect_while_alive(self.views.currentChanged, self._on_view_changed)
        self.holder = QWidget(self)
        self.holder.page = self.page
        self.holder.window_ = self

    def _on_view_changed(self, index):
        print("changed", index)

window = Window()
del window
gc.collect()
print("collected")
"""


def _run(script: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-c", script], cwd=_ROOT, capture_output=True, text=True,  # noqa: S603
                          timeout=120, env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONPATH": str(_ROOT)})


@pytest.mark.parametrize("script", [_EMPTY_STACK, _REQUIREMENTS, _TABS], ids=["empty-stack", "requirements", "tabs"])
def test_a_widget_tree_freed_by_the_collector_calls_no_cleared_owner(script):
    """Freed by the collector as the first widget of a process, a list in an
    ``EmptyStack``, the Monte Carlo editor's Requirements list and a window
    with view tabs send their teardown signals to nobody: no "Slot '...::'
    not found". Before the fix, each printed it."""
    done = _run(script)
    assert done.returncode == 0, done.stderr[-2000:]
    assert done.stdout.splitlines()[-1] == "collected"
    assert "not found" not in done.stderr, done.stderr[-2000:]
    assert "changed" not in done.stdout  # the window's method was not called while it was freed


def test_connect_while_alive_passes_what_the_method_takes(qtbot):
    """As a direct connection: the method gets the signal's first arguments
    that it takes, and with ``sender`` the sender first."""
    from PySide6.QtCore import QObject, Signal

    from spacemissionstudio.gui.widgets import connect_while_alive

    class Source(QObject):
        moved = Signal(int, str)

    class Owner(QObject):
        def __init__(self):
            super().__init__()
            self.calls = []

        def none(self):
            self.calls.append(("none",))

        def one(self, index):
            self.calls.append(("one", index))

        def every(self, *args):
            self.calls.append(("every", *args))

        def with_sender(self, source, index):
            self.calls.append(("sender", source, index))

    source, owner = Source(), Owner()
    for method in (owner.none, owner.one, owner.every):
        connect_while_alive(source.moved, method)
    connect_while_alive(source.moved, owner.with_sender, sender=source)
    source.moved.emit(3, "x")
    assert owner.calls == [("none",), ("one", 3), ("every", 3, "x"), ("sender", source, 3)]


def test_connect_while_alive_calls_nothing_once_the_owner_is_gone(qtbot):
    """The connection holds the owner weakly: a dropped owner is freed, and
    the signal then calls nothing; an owner whose C++ object is deleted is
    not called either."""
    import gc
    import weakref

    from PySide6.QtCore import QObject, Signal
    from shiboken6 import delete

    from spacemissionstudio.gui.widgets import connect_while_alive

    calls = []

    class Source(QObject):
        moved = Signal(int)

    class Owner(QObject):
        def on_moved(self, index):
            calls.append(index)

    source = Source()
    dropped, deleted = Owner(), Owner()
    connect_while_alive(source.moved, dropped.on_moved)
    connect_while_alive(source.moved, deleted.on_moved)
    ref = weakref.ref(dropped)
    del dropped
    gc.collect()
    assert ref() is None  # the connection did not keep it
    delete(deleted)
    source.moved.emit(1)
    assert calls == []


def test_teardown_signals_are_connected_weakly():
    """No view or list connects a tab or stacked widget's ``currentChanged``
    or an item model's row signals straight to a method: each goes through
    ``connect_while_alive`` (a page or a list deleted before its owner sends
    them)."""
    pattern = re.compile(r"\.(currentChanged|modelReset|modelAboutToBeReset|rowsInserted|rowsRemoved|layoutChanged)"
                         r"\.connect\(")
    found = [f"{path.relative_to(_ROOT)}:{number}"
             for path in sorted((_ROOT / "spacemissionstudio" / "gui").rglob("*.py"))
             for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
             if pattern.search(line)]
    assert found == []
