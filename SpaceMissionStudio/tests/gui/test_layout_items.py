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

"""Layout items are read without leaving a wrapper behind (2.13.0).

PySide keeps the wrapper of a layout item that is not a QObject for as long
as its layout's wrapper lives, and is not told when Qt deletes the item. A
later object at the freed address then got that wrapper: on Windows CI,
``windowHandle()`` returned a ``QWidgetItem`` in place of the new
``QWindow`` and detaching the Budgets view failed."""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.requires_gui

_GUI = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "gui"


def _item_wrappers() -> int:
    import shiboken6
    from PySide6.QtWidgets import QWidgetItem

    return sum(1 for wrapper in shiboken6.getAllValidWrappers() if type(wrapper) is QWidgetItem)


def test_reading_a_layout_item_leaves_no_wrapper(qtbot):
    """Each helper returns what the item holds and leaves no QWidgetItem
    wrapper registered; the layout goes on working."""
    from PySide6.QtWidgets import QFormLayout, QGridLayout, QLabel, QVBoxLayout, QWidget

    from spacemissionstudio.gui.widgets import layout_item_widget, layout_item_widgets, read_layout_item

    host = QWidget()
    qtbot.addWidget(host)
    column = QVBoxLayout(host)
    first, second = QLabel("first"), QLabel("second")
    column.addWidget(first)
    column.addWidget(second)
    before = _item_wrappers()
    assert layout_item_widget(column, 1) is second
    assert layout_item_widgets(column) == [first, second]
    assert read_layout_item(column, lambda item: item.widget().text(), 0) == "first"
    assert layout_item_widget(column, 5) is None
    form_box, grid_box = QWidget(), QWidget()
    qtbot.addWidget(form_box)
    qtbot.addWidget(grid_box)
    form, grid = QFormLayout(form_box), QGridLayout(grid_box)
    name, cell = QLabel("Name"), QLabel("cell")
    form.addRow(name, QLabel("value"))
    grid.addWidget(cell, 1, 2)
    assert layout_item_widget(form, 0, QFormLayout.ItemRole.LabelRole) is name
    assert layout_item_widget(grid, 1, 2) is cell
    assert _item_wrappers() == before
    assert column.count() == 2 and column.indexOf(second) == 1


def test_a_nested_layout_and_a_python_made_item_stay_usable(qtbot):
    """A nested layout is a QObject and stays as it is; FlowLayout keeps the
    items it made in Python, so they are not released either."""
    from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

    from spacemissionstudio.gui.flow_layout import FlowLayout
    from spacemissionstudio.gui.widgets import layout_item_widgets, read_layout_item

    host = QWidget()
    qtbot.addWidget(host)
    column = QVBoxLayout(host)
    row = QHBoxLayout()
    column.addLayout(row)
    assert read_layout_item(column, lambda item: item.layout(), 0) is row
    assert layout_item_widgets(column) == [None]
    tiles_box = QWidget()
    qtbot.addWidget(tiles_box)
    flow = FlowLayout(tiles_box)
    tiles = [QLabel("a"), QLabel("b")]
    for tile in tiles:
        flow.addWidget(tile)
    assert layout_item_widgets(flow) == tiles
    assert layout_item_widgets(flow) == tiles  # read twice: the items are still valid
    tiles_box.resize(200, 100)
    tiles_box.show()
    qtbot.waitExposed(tiles_box)
    assert all(tile.isVisible() for tile in tiles)


def test_a_view_opens_in_its_window_past_a_stale_handle(qtbot, monkeypatch):
    """show_window drops a wrapper of the wrong type at the native window's
    address, asks again and clears the window's transient parent."""
    from PySide6.QtGui import QWindow
    from PySide6.QtWidgets import QLabel, QWidget, QWidgetItem

    from spacemissionstudio.gui.widgets import make_window, show_window

    owner = QWidget()
    qtbot.addWidget(owner)
    view = make_window(QWidget(owner))
    stale = QWidgetItem(QLabel("stale"))
    answers = [stale]
    real = QWidget.windowHandle

    def window_handle(widget):
        return answers.pop() if answers else real(widget)

    monkeypatch.setattr(type(view), "windowHandle", window_handle)
    show_window(view)
    qtbot.waitExposed(view)
    assert not answers and view.isVisible()
    assert isinstance(real(view), QWindow) and real(view).transientParent() is None


def test_the_app_reads_layout_items_only_through_the_helpers():
    """No module of the window calls itemAt() or itemAtPosition() on a
    layout but widgets.read_layout_item (FlowLayout defines itemAt, and a
    tree's itemAt(point) returns a tree item)."""
    allowed = {("widgets.py", "item = layout.itemAt(*where)"),
               ("widgets.py", "item = layout.itemAtPosition(*where)")}
    found = []
    for path in sorted(_GUI.rglob("*.py")):
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if re.search(r"\.itemAt(Position)?\(", text) and not text.startswith("def ") \
                    and "self.itemAt(event" not in text and (path.name, text) not in allowed:
                found.append(f"{path.relative_to(_GUI)}: {text}")
    assert not found, found
