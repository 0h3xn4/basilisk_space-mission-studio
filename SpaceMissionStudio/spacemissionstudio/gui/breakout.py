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
"""A view of the main window in a window of its own, and back (2.12.0,
``docs/developer/windows-views-design.md`` section 2; decision "Breakout
windows" in ``docs/DECISIONS.md``).

One mechanism for every view that can open in its own window:

* :class:`Breakouts` -- one per main window. :meth:`Breakouts.register`
  names a view; :meth:`Breakouts.detach` makes **the same widget object**
  a top-level window, :meth:`Breakouts.attach` puts it back in its place.
  Nothing is copied or built twice: a web view, its scene, a live timer and
  the time cursor keep working, and the view keeps receiving its data.
* :class:`BreakoutPlaceholder` -- what the view's place in the main window
  shows while the view is away: the tab keeps its index and its text, and
  **Bring Back** (primary) and **Show Window** are its actions.
* :class:`BreakoutButton` -- the icon button in the view's own toolbar.

The view keeps its parent: it leaves its tab (``QTabWidget.removeTab``
does not reparent) or its layout slot (``QLayout.replaceWidget``) and gets
the window flags (``widgets.WINDOW_FLAGS``). A new parent would make Qt
restyle every widget of the view under the application's style sheet: 50
to 70 ms for Budgets' 431 widgets, measured, against 2 to 14 ms this way
("Never freeze"). A window child of the main window is not hidden with its
area, closes with the main window and is not a second application window.
The window has the app icon and the title "<view> - <scenario> -
SpaceMissionStudio". Closing it brings the view back. While it is a window,
the view carries the main window's global commands, so their shortcuts
(Ctrl+K, Ctrl+S, Ctrl+R, Ctrl+Shift+D, ...) work there too.

A tab is swapped for the placeholder and back at the same index, without
another tab being shown in between.

The window's geometry is kept per view in the main window's layout file
(``layout.ini``, key ``breakout/<view id>/geometry``): read with the layout
at start (:meth:`Breakouts.read_geometry`), kept in memory while the app
runs, and written with the layout when the app quits
(:meth:`Breakouts.write_geometry`). No move writes the file: on the GUI
thread one write measured 50 to 220 ms, and from a worker it still stopped
the GUI thread, because ``QSettings.sync`` keeps the interpreter lock. It is used again only when it is on a
screen that still exists; otherwise the window is centred on the main
window. Wayland ignores a window's position, so there only the size is
used. Every view opens docked at start ("Calm by default"); no window opens
by itself.

Usage (the live 2D map of PR-3 is one more registration)::

    breakouts = Breakouts(main_window,
                          actions=main_window._breakout_actions)
    breakouts.register("3d_view", mission_view_widget, "3D View")
    mission_view_widget.add_tool_button(breakouts.button("3d_view"))
    breakouts.toggle("3d_view")   # or detach(), attach(), attach_all()
"""

from __future__ import annotations

import weakref
from collections.abc import Callable
from dataclasses import dataclass, field

from PySide6.QtCore import QEvent, QObject, QRect, QSize, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLayout, QPushButton, QStackedWidget, QTabWidget,
                               QToolButton, QWidget)

from .budgets_area import EmptyState
from .theme import SPACE, icon, set_role
from .widgets import WINDOW_FLAGS, show_window

#: The command that opens the view shown in its own window, or brings it back.
SHORTCUT = "Ctrl+Shift+D"
OPEN_TEXT = "Open in Own Window"
BACK_TEXT = "Bring Back"
OPEN_ICON = "external-link"
BACK_ICON = "square-arrow-down-left"
APP_NAME = "SpaceMissionStudio"

_DEFAULT_SIZE = QSize(960, 640)  # [px] a first window, when the view's own size is smaller
_MIN_SIZE = QSize(480, 320)  # [px] a window is never made smaller than this from a saved size
_TITLE_STRIP_PX = 32  # [px] a saved window is used only if this strip of its top edge is on a screen


def settings_key(view_id: str) -> str:
    """The layout file's key of a view's window geometry."""
    return f"breakout/{view_id}/geometry"


def _maximized_key(view_id: str) -> str:
    return f"breakout/{view_id}/maximized"


def _weak(function: Callable | None) -> Callable[[], Callable | None]:
    """A callable held weakly when it is a bound method (a bound method of
    the main window would keep it alive: tests/gui/test_menu_bar.py frees
    the window by reference count)."""
    if function is None:
        return lambda: None
    if hasattr(function, "__self__"):
        return weakref.WeakMethod(function)
    return lambda: function


def on_a_screen(rect: QRect) -> bool:
    """Whether the top strip of ``rect`` (its title bar) is on a screen that
    exists now: a window saved on a screen since unplugged is not."""
    if rect.isNull() or rect.width() <= 0 or rect.height() <= 0:
        return False
    strip = QRect(rect.x(), rect.y(), rect.width(), min(rect.height(), _TITLE_STRIP_PX))
    for screen in QGuiApplication.screens():
        common = screen.availableGeometry().intersected(strip)
        if common.width() >= min(rect.width(), 2 * _TITLE_STRIP_PX) and common.height() > 0:
            return True
    return False


def position_ignored() -> bool:
    """Wayland places windows itself: a saved position is ignored there."""
    return QGuiApplication.platformName().lower().startswith("wayland")


class _CloseWatcher(QObject):
    """On a view while it is a window: closing the window asks for the view
    to come back (the close itself is refused, so Qt does not hide the view
    after it is back in its place)."""

    close_requested = Signal(str)

    def __init__(self, view_id: str, parent: QObject) -> None:
        super().__init__(parent)
        self.view_id = view_id

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 -- Qt API name
        if event.type() == QEvent.Type.Close and isinstance(watched, QWidget) and watched.isWindow():
            event.ignore()
            self.close_requested.emit(self.view_id)
            return True
        return False


class BreakoutPlaceholder(EmptyState):
    """The view's place while it is in its own window: "<view> is in its
    own window", **Bring Back** (primary) and **Show Window**."""

    bring_back_requested = Signal(str)
    show_requested = Signal(str)

    def __init__(self, view_id: str, title: str, parent: QWidget | None = None) -> None:
        super().__init__(f"{title} is in its own window",
                         f"It keeps working there, with its data. Bring Back ({SHORTCUT}) or closing its window "
                         "puts it here again.", action=BACK_TEXT, primary=True, parent=parent)
        self.view_id = view_id
        self.setObjectName("breakoutPlaceholder")
        self.button.setToolTip(f"{BACK_TEXT} ({SHORTCUT})\nMove {title} back into this window.")
        self.button.setAccessibleName(f"{BACK_TEXT}: {title}")
        self.show_button = set_role(QPushButton("Show Window"), variant="ghost")
        self.show_button.setToolTip(f"Bring the window of {title} to the front.")
        self.show_button.setAccessibleName(f"Show the window of {title}")
        layout = self.layout()
        index = layout.indexOf(self.button)
        layout.removeWidget(self.button)
        row = QHBoxLayout()
        row.setSpacing(SPACE["sm"])
        row.addStretch(1)
        row.addWidget(self.button)
        row.addWidget(self.show_button)
        row.addStretch(1)
        layout.insertLayout(index, row)
        self.button.clicked.connect(self._on_bring_back)
        self.show_button.clicked.connect(self._on_show)

    def _on_bring_back(self) -> None:
        self.bring_back_requested.emit(self.view_id)

    def _on_show(self) -> None:
        self.show_requested.emit(self.view_id)


class BreakoutButton(QToolButton):
    """The icon button in a view's own toolbar: Open in Own Window, or
    Bring Back while the view is away; its tooltip gives the shortcut."""

    toggle_requested = Signal(str)

    def __init__(self, view_id: str, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.view_id = view_id
        self.title = title
        self.setObjectName("breakoutButton")
        self.setAutoRaise(True)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.clicked.connect(self._on_clicked)
        self.show_state(False)

    def show_state(self, detached: bool) -> None:
        text = BACK_TEXT if detached else OPEN_TEXT
        self.setIcon(icon(BACK_ICON if detached else OPEN_ICON, "text.secondary"))
        self.setText(text)
        does = (f"Move {self.title} back into the main window." if detached
                else f"Show {self.title} in a window of its own, beside the main window.")
        self.setToolTip(f"{text} ({SHORTCUT})\n{does}")
        self.setAccessibleName(f"{text}: {self.title}")

    def _on_clicked(self) -> None:
        self.toggle_requested.emit(self.view_id)


@dataclass
class _View:
    """A registered view, its placeholder and, while it is a window, what
    the window took on."""

    id: str
    widget: QWidget
    title: str
    placeholder: BreakoutPlaceholder
    watcher: _CloseWatcher
    detached: bool = False
    buttons: list = field(default_factory=list)
    added_actions: list = field(default_factory=list)  # the window's commands the view carries while detached


def _tabs_of(widget: QWidget) -> QTabWidget | None:
    """The tab widget whose page ``widget`` is, or None."""
    stack = widget.parentWidget()
    if isinstance(stack, QStackedWidget) and isinstance(stack.parentWidget(), QTabWidget):
        tabs = stack.parentWidget()
        return tabs if tabs.indexOf(widget) >= 0 else None
    return None


def _layout_of(widget: QWidget) -> QLayout | None:
    parent = widget.parentWidget()
    layout = parent.layout() if parent is not None else None
    return layout if layout is not None and layout.indexOf(widget) >= 0 else None


def _swap(old: QWidget, new: QWidget) -> None:
    """Put ``new`` where ``old`` is: the same tab (index, text, icon,
    tooltip; selected if ``old`` was) or the same layout slot. ``old`` is
    taken out, not deleted, and keeps its parent."""
    tabs = _tabs_of(old)
    if tabs is not None:
        index = tabs.indexOf(old)
        current = tabs.currentIndex() == index
        text, tab_icon, tip = tabs.tabText(index), tabs.tabIcon(index), tabs.tabToolTip(index)
        tabs.insertTab(index, new, tab_icon, text)
        tabs.setTabToolTip(index, tip)
        if current:
            tabs.setCurrentIndex(index)  # straight from old to new: no other tab is shown in between
        tabs.removeTab(index + 1)
        return
    layout = _layout_of(old)
    if layout is None:
        raise ValueError(f"{type(old).__name__} is neither a tab nor in a layout: it cannot move")
    layout.replaceWidget(old, new)
    new.show()
    old.hide()


class Breakouts(QObject):
    """The views of a main window that can open in a window of their own.
    :attr:`changed` carries (view id, detached) after every move."""

    changed = Signal(str, bool)

    def __init__(self, owner: QWidget, actions: Callable | None = None) -> None:
        """``actions(view_id)`` gives the commands the view's window carries.
        The windows' geometry is read from the layout file at start
        (:meth:`read_geometry`) and written to it at quit
        (:meth:`write_geometry`), with the rest of the layout."""
        super().__init__(owner)
        self._owner = weakref.ref(owner)
        self._actions = _weak(actions)
        self._views: dict[str, _View] = {}
        self._document = ""  # the scenario named in the windows' titles
        self._geometry: dict[str, tuple[QRect, bool]] = {}  # view id -> (window rectangle, maximised), as kept

    # -- registration ---------------------------------------------------------------------------------------
    def register(self, view_id: str, widget: QWidget, title: str) -> None:
        """``widget`` (a tab or in a layout of the main window) can open in a
        window of its own, named ``title``."""
        if view_id in self._views:
            raise ValueError(f"view {view_id!r} is registered twice")
        # A child of the view's parent from the start, hidden: never a window of its own, and no new parent
        # (and restyle) when it takes the view's place.
        placeholder = BreakoutPlaceholder(view_id, title, parent=widget.parentWidget() or self._owner())
        placeholder.hide()
        placeholder.bring_back_requested.connect(self.attach)
        placeholder.show_requested.connect(self.show_window)
        watcher = _CloseWatcher(view_id, self)
        watcher.close_requested.connect(self.attach, Qt.ConnectionType.QueuedConnection)
        self._views[view_id] = _View(view_id, widget, title, placeholder, watcher)

    def button(self, view_id: str) -> BreakoutButton:
        """A new toolbar button for the view (it follows the view's state)."""
        view = self._views[view_id]
        button = BreakoutButton(view_id, view.title)
        button.toggle_requested.connect(self.toggle)
        button.show_state(view.detached)
        view.buttons.append(button)
        return button

    def ids(self) -> list[str]:
        return list(self._views)

    def title(self, view_id: str) -> str:
        return self._views[view_id].title

    def widget(self, view_id: str) -> QWidget:
        return self._views[view_id].widget

    def placeholder(self, view_id: str) -> BreakoutPlaceholder:
        return self._views[view_id].placeholder

    def is_detached(self, view_id: str) -> bool:
        return self._views[view_id].detached

    def window(self, view_id: str) -> QWidget | None:
        """The view's window (the view itself) while it is detached, else None."""
        view = self._views[view_id]
        return view.widget if view.detached else None

    # -- finding a view -------------------------------------------------------------------------------------
    def view_at(self, widget: QWidget | None) -> str | None:
        """The id of the view that is ``widget``, holds it, or whose
        placeholder it is; None for any other widget."""
        node = widget
        while node is not None:
            for view in self._views.values():
                if node is view.widget or node is view.placeholder:
                    return view.id
            node = node.parentWidget()
        return None

    def detached_at(self, widget: QWidget | None) -> str | None:
        """The id of the detached view whose window ``widget`` is in (a
        dialog opened over that window too), or None."""
        owner = self._owner()
        node = widget
        while node is not None and node is not owner:
            for view in self._views.values():
                if node is view.widget and view.detached:
                    return view.id
            node = node.parentWidget()
        return None

    def resolve(self, widget: QWidget) -> QWidget:
        """The view itself for its placeholder; any other widget as it is."""
        for view in self._views.values():
            if widget is view.placeholder:
                return view.widget
        return widget

    # -- moving ---------------------------------------------------------------------------------------------
    def toggle(self, view_id: str) -> None:
        if self.is_detached(view_id):
            self.attach(view_id)
        else:
            self.detach(view_id)

    def detach(self, view_id: str) -> QWidget:
        """Make the view a window of its own, shown and in front; the
        placeholder takes its place. Already detached: the window comes to
        the front. Returns the window (the view)."""
        view = self._views[view_id]
        widget = view.widget
        if view.detached:
            self.show_window(view_id)
            return widget
        docked_size = widget.size()
        _swap(widget, view.placeholder)
        view.detached = True
        widget.setWindowFlags(WINDOW_FLAGS)
        widget.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        set_role(widget, breakout="true")  # the window's own background (theme/qss.py), not a page's
        app = QApplication.instance()
        if app is not None and not app.windowIcon().isNull():
            widget.setWindowIcon(app.windowIcon())
        self._retitle(view)
        actions = self._actions()
        own = set(widget.actions())
        view.added_actions = [action for action in (actions(view_id) if actions is not None else []) if action not in own]
        widget.addActions(view.added_actions)
        widget.installEventFilter(view.watcher)
        self._place(view, docked_size)
        self._show(view, first=True)
        self._focus(view)
        self._notify(view)
        return widget

    def attach(self, view_id: str) -> None:
        """Put the view back in its place in the main window (its window's
        geometry kept)."""
        view = self._views[view_id]
        if not view.detached:
            return
        widget = view.widget
        self._remember(view)
        widget.removeEventFilter(view.watcher)
        for action in view.added_actions:
            widget.removeAction(action)
        view.added_actions = []
        widget.hide()
        widget.setWindowFlags(Qt.WindowType.Widget)
        set_role(widget, breakout=None)
        view.detached = False
        _swap(view.placeholder, widget)
        view.placeholder.hide()
        self._notify(view)

    def attach_all(self) -> None:
        """Every view back in the main window (on quit, before the layout
        is saved, and when no scenario is open)."""
        for view_id in self._views:
            self.attach(view_id)

    def show_window(self, view_id: str) -> None:
        """The view's window in front (when it is detached)."""
        view = self._views[view_id]
        if view.detached:
            self._show(view)

    # -- titles, geometry -----------------------------------------------------------------------------------
    def set_document(self, name: str) -> None:
        """The scenario the windows' titles name ("" when none is open)."""
        self._document = name
        for view in self._views.values():
            self._retitle(view)

    def window_title(self, view_id: str) -> str:
        view = self._views[view_id]
        parts = [view.title, self._document, APP_NAME] if self._document else [view.title, APP_NAME]
        return " - ".join(parts)

    def read_geometry(self, settings) -> None:
        """The windows' geometry kept in ``settings`` (the layout file, read
        at start with the rest of the layout)."""
        for view_id in self._views:
            rect = settings.value(settings_key(view_id))
            if isinstance(rect, QRect) and rect.isValid():
                maximized = str(settings.value(_maximized_key(view_id), False)).lower() == "true"
                self._geometry[view_id] = (QRect(rect), maximized)

    def write_geometry(self, settings) -> None:
        """The windows' geometry into ``settings`` (the caller syncs it): on
        quit, with the layout."""
        for view_id, (rect, maximized) in self._geometry.items():
            settings.setValue(settings_key(view_id), rect)
            settings.setValue(_maximized_key(view_id), maximized)

    def saved_geometry(self, view_id: str) -> tuple[QRect | None, bool]:
        """(rectangle, maximised) kept for the view's window; None when none is."""
        rect, maximized = self._geometry.get(view_id, (None, False))
        return (QRect(rect) if rect is not None else None), maximized

    def _remember(self, view: _View) -> None:
        """The window's place and size, kept in memory. The layout file gets
        them at quit (:meth:`write_geometry`). Writing it here, even from a
        worker, stopped the GUI thread: ``QSettings.sync`` keeps the
        interpreter lock while it writes, and a move took up to 168 ms."""
        window = view.widget
        if not window.isVisible():
            return
        maximized = window.isMaximized()
        rect = window.normalGeometry() if maximized and window.normalGeometry().isValid() else window.geometry()
        self._geometry[view.id] = (QRect(rect), maximized)

    def _place(self, view: _View, docked_size: QSize) -> None:
        """A saved rectangle on a screen that exists; else the saved (or the
        docked) size, centred on the main window. Wayland: the size only."""
        window = view.widget
        rect, _maximized = self.saved_geometry(view.id)
        if rect is not None and not position_ignored() and on_a_screen(rect):
            window.setGeometry(rect)
            return
        size = rect.size() if rect is not None else docked_size.expandedTo(_DEFAULT_SIZE)
        size = size.expandedTo(_MIN_SIZE)
        owner = self._owner()
        screen = (owner.screen() if owner is not None else None) or QGuiApplication.primaryScreen()
        if screen is not None:
            size = size.boundedTo(screen.availableGeometry().size())
        window.resize(size)
        if position_ignored():
            return  # the compositor places it
        if owner is not None and owner.isVisible():
            centre = owner.frameGeometry().center()
        elif screen is not None:
            centre = screen.availableGeometry().center()
        else:
            return
        frame = QRect(window.geometry())
        frame.moveCenter(centre)
        window.move(frame.topLeft())

    def _show(self, view: _View, first: bool = False) -> None:
        show_window(view.widget)
        if first and self.saved_geometry(view.id)[1]:
            view.widget.showMaximized()

    def _focus(self, view: _View) -> None:
        """The keyboard in the window: its first control takes the focus."""
        widget = view.widget
        if widget.focusPolicy() != Qt.FocusPolicy.NoFocus:
            widget.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        child = widget.nextInFocusChain()
        while child is not None and child is not widget:
            if widget.isAncestorOf(child) and child.focusPolicy() & Qt.FocusPolicy.TabFocus and \
                    child.isVisibleTo(widget) and child.isEnabled():
                child.setFocus(Qt.FocusReason.OtherFocusReason)
                return
            child = child.nextInFocusChain()

    def _retitle(self, view: _View) -> None:
        if view.detached:
            view.widget.setWindowTitle(self.window_title(view.id))

    def _notify(self, view: _View) -> None:
        for button in view.buttons:
            button.show_state(view.detached)
        self.changed.emit(view.id, view.detached)
