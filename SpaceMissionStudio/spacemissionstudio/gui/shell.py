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

"""The window's navigation (UI overhaul plan §5.1): a rail of areas on the
left and the area shown beside it.

* :class:`NavRail`: one button per area, icon and label, collapsible to
  icons only. Settings and Help sit at its bottom.
* :class:`AreaPage`: an area's page, a header (its title and the
  commands of the area, one height in every area) over the screen it
  hosts, whose pages start their content at one inset
  (:func:`inset_page`, ``theme.PAGE_INSET``).
* :class:`AreaStack`: the pages, one shown at a time.
* :class:`Shell`: the rail and the stack. :meth:`Shell.register` adds an
  area, so a later area (Operations) is one more call, with no change to
  the shell.

The shell only shows and switches; the window decides what each area
holds (``MainWindow``).
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy, QStackedWidget,
                               QTabWidget, QToolButton, QVBoxLayout, QWidget)

from .theme import AREA_HEADER_HEIGHT, ICON_SIZE, PAGE_INSET, SPACE, icon, set_role


def page_body(page: QWidget) -> QWidget:
    """The widget whose layout holds ``page``'s content: a scroll area's
    widget (its scroll bar stays at the page's edge), else the page."""
    if isinstance(page, QScrollArea) and page.widget() is not None:
        return page.widget()
    return page


# A page whose form scrolls itself (an embedded editor): it puts the inset
# inside its own scroll areas, so their scroll bars stay at the page's edge.
INSET_INSIDE = "insetInside"


def inset_page(page: QWidget) -> QWidget:
    """``page``'s content at ``theme.PAGE_INSET`` from the page's edges (UI
    audit UI-16): the one inset of every page of every area, as the area
    header's title is inset. A page draws no margin of its own around its
    content; the area gives it this one. A page marked :data:`INSET_INSIDE`
    applies it itself. Returns ``page``."""
    if page.property(INSET_INSIDE):
        return page
    layout = page_body(page).layout()
    if layout is not None:
        layout.setContentsMargins(PAGE_INSET, PAGE_INSET, PAGE_INSET, PAGE_INSET)
    return page


def inset_stack(stack: QStackedWidget) -> None:
    """Every page of ``stack`` at the page inset, the pages added later too."""
    for index in range(stack.count()):
        inset_page(stack.widget(index))
    stack.widgetAdded.connect(lambda index, stack=stack: inset_page(stack.widget(index)))


@dataclass
class Area:
    """One area of the rail."""

    id: str
    label: str
    icon: str  # a bundled Lucide icon
    order: int
    page: AreaPage | None  # None: a button that runs ``action`` instead of showing a page (Help)
    bottom: bool = False  # pinned at the rail's bottom (Settings, Help)
    action: QAction | None = None


class AreaPage(QWidget):
    """An area's page: a header with the title and the area's commands,
    over ``content``, the screen it hosts unchanged. With an empty state
    (:meth:`set_empty_state`) the page can show that instead of its
    commands and content (:meth:`show_empty`): the area while no scenario
    is open.

    The header (``title_bar``) is always shown, with the area's title, and
    has one height in every area (``theme.AREA_HEADER_HEIGHT``), so the
    tab rows under it start at one height (UI audit UI-17). The commands
    (``header``) are one row beside the title. When the row has no room
    for their names, the buttons show their icons only (``squeezed``),
    each with its name as tooltip and accessible name; the names come back
    when there is room.

    Its pages start their content at one inset (``theme.PAGE_INSET``; UI
    audit UI-16): each tab of a tabbed area, the area itself when it has no
    tabs, or the pages a screen names with ``inset_pages()`` (the Scenario
    tree's pages and the JSON page). The tab rows and the Scenario tree
    stay flush with the page's edges."""

    def __init__(self, area_id: str, title: str, content: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.area_id = area_id
        self.content = content
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.title_bar = QFrame()
        self.title_bar.setObjectName("areaHeader")
        self.title_bar.setFixedHeight(AREA_HEADER_HEIGHT)
        bar_layout = QHBoxLayout(self.title_bar)
        bar_layout.setContentsMargins(SPACE["lg"], 0, SPACE["lg"], 0)
        bar_layout.setSpacing(SPACE["md"])
        self.title_label = set_role(QLabel(title), role="page-title")
        bar_layout.addWidget(self.title_label, 0, Qt.AlignmentFlag.AlignVCenter)
        # The commands: one row, never taller than the header, never holding the window wider.
        self.header = QWidget()
        self.header.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self._buttons_layout = QHBoxLayout(self.header)
        self._buttons_layout.setContentsMargins(0, 0, 0, 0)
        self._buttons_layout.setSpacing(SPACE["xs"])
        self._buttons_layout.addStretch(1)
        bar_layout.addWidget(self.header, 1, Qt.AlignmentFlag.AlignVCenter)
        self.buttons: dict[QAction, QToolButton] = {}
        self._has_commands = False  # the commands show once there is one
        self.header.setVisible(False)
        self.squeezed = False
        layout.addWidget(self.title_bar)
        layout.addWidget(content, 1)
        self._inset_content()
        self.empty_state: QWidget | None = None
        self.showing_empty = False

    def _inset_content(self) -> None:
        content = self.content
        if isinstance(content, QTabWidget):
            stack = content.findChild(QStackedWidget, "qt_tabwidget_stackedwidget")
            if stack is not None:
                inset_stack(stack)
        elif hasattr(content, "inset_pages"):
            content.inset_pages()
        else:
            inset_page(content)

    def add_command(self, action: QAction) -> QToolButton:
        """A button for ``action`` in the header: its text, icon and
        enabled state follow the action. It is secondary: the one accent
        is the top bar's Run (UI audit UI-03); its edge and surface show it
        is a button, not a line of text (``variant="secondary"``, UI-11)."""
        button = set_role(QToolButton(), variant="secondary")
        button.setDefaultAction(action)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly if self.squeezed
                                  else Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setAccessibleName(action.text().replace("&", ""))
        self._add(button)
        self.buttons[action] = button
        return button

    def add_widget(self, widget: QWidget) -> None:
        """A control of the area's own in the header (the run mode button)."""
        self._add(widget)

    def _add(self, widget: QWidget) -> None:
        self._buttons_layout.insertWidget(self._buttons_layout.count() - 1, widget, 0,
                                          Qt.AlignmentFlag.AlignVCenter)
        self._has_commands = True
        self.header.setVisible(not self.showing_empty)
        self._fit_commands()

    def set_empty_state(self, widget: QWidget) -> None:
        """``widget``: what the page shows instead of its commands and
        content while :meth:`show_empty` says so."""
        self.empty_state = widget
        self.layout().addWidget(widget, 1)
        widget.setVisible(self.showing_empty)

    def show_empty(self, empty: bool) -> None:
        """The empty state (``empty``, when the page has one) or the
        commands and content; the title stays."""
        self.showing_empty = empty and self.empty_state is not None
        self.header.setVisible(self._has_commands and not self.showing_empty)
        self.content.setVisible(not self.showing_empty)
        if self.empty_state is not None:
            self.empty_state.setVisible(self.showing_empty)
        self._fit_commands()

    def resizeEvent(self, event) -> None:  # noqa: N802 -- Qt API name
        super().resizeEvent(event)
        self._fit_commands()

    def showEvent(self, event) -> None:  # noqa: N802 -- Qt API name
        super().showEvent(event)
        self._fit_commands()

    def _named_width(self) -> int:
        """The width the commands take with their names [px]."""
        layout = self._buttons_layout
        widgets = [layout.itemAt(i).widget() for i in range(layout.count())]
        shown = [w for w in widgets if w is not None and not w.isHidden()]
        width = 0
        for widget in shown:
            if isinstance(widget, QToolButton) and widget in self.buttons.values():
                style = widget.toolButtonStyle()
                widget.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
                width += widget.sizeHint().width()
                widget.setToolButtonStyle(style)
            else:
                width += widget.sizeHint().width()
        return width + layout.spacing() * max(len(shown) - 1, 0)

    def _fit_commands(self) -> None:
        """Icons only while the names do not fit the header's width; the
        names again once they fit."""
        if not self._has_commands or not self.isVisible():
            return
        margins = self.title_bar.layout().contentsMargins()
        room = (self.title_bar.width() - margins.left() - margins.right() - self.title_label.sizeHint().width()
                - self.title_bar.layout().spacing())
        squeezed = self._named_width() > room
        if squeezed == self.squeezed:
            return
        self.squeezed = squeezed
        for button in self.buttons.values():
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly if squeezed
                                      else Qt.ToolButtonStyle.ToolButtonTextBesideIcon)


class AreaStack(QStackedWidget):
    """The areas' pages; :meth:`MainWindow.show_view` walks up to it."""


class NavRail(QFrame):
    """The areas as buttons, top to bottom; the collapse button last."""

    area_chosen = Signal(str)
    collapsed_changed = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("navRail")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(SPACE["xs"], SPACE["sm"], SPACE["xs"], SPACE["sm"])
        self._layout.setSpacing(SPACE["xs"])
        self._top = QVBoxLayout()
        self._top.setSpacing(SPACE["xs"])
        self._bottom = QVBoxLayout()
        self._bottom.setSpacing(SPACE["xs"])
        self._layout.addLayout(self._top)
        self._layout.addStretch(1)
        self._layout.addLayout(self._bottom)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: dict[str, QToolButton] = {}
        self._labels: dict[str, str] = {}
        self._keys: dict[str, str] = {}
        self.collapse_button = QToolButton()
        self.collapse_button.setObjectName("railCollapseButton")
        self.collapse_button.setAutoRaise(True)
        self.collapse_button.clicked.connect(lambda: self.set_collapsed(not self.collapsed))
        self._layout.addWidget(self.collapse_button, 0, Qt.AlignmentFlag.AlignHCenter)
        self.collapsed = False
        # Icons only while the rail is too short for the names (a 720 px window with the Problems
        # panel open: eight areas and their names need about 580 px). Not the user's choice:
        # ``collapsed`` stays as it is, and the names come back when there is room.
        self.squeezed = False
        self._named_height = 0  # [px] the rail's height with the names, when it was squeezed
        self._show_collapse_state()

    def add_area(self, area: Area, keys: str = "", index: int = -1) -> QToolButton:
        """A button for ``area`` at ``index`` of its group (top or bottom;
        last when -1)."""
        button = QToolButton()
        button.setObjectName("railButton")
        button.setIcon(icon(area.icon, "text.secondary"))
        button.setIconSize(QSize(ICON_SIZE["rail"], ICON_SIZE["rail"]))
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._labels[area.id] = area.label
        self._keys[area.id] = keys
        if area.page is not None:
            button.setCheckable(True)
            self.group.addButton(button)
            button.clicked.connect(lambda _checked=False, area_id=area.id: self.area_chosen.emit(area_id))
        elif area.action is not None:
            button.clicked.connect(area.action.trigger)
        (self._bottom if area.bottom else self._top).insertWidget(index, button)
        self.buttons[area.id] = button
        self._show_label(area.id)
        return button

    def set_current(self, area_id: str) -> None:
        button = self.buttons.get(area_id)
        if button is not None and button.isCheckable():
            button.setChecked(True)

    def current(self) -> str | None:
        return next((area_id for area_id, button in self.buttons.items() if button.isChecked()), None)

    def set_collapsed(self, collapsed: bool) -> None:
        """Icons only (``collapsed``) or icon and label."""
        if collapsed == self.collapsed:
            return
        self.collapsed = collapsed
        for area_id in self.buttons:
            self._show_label(area_id)
        self._show_collapse_state()
        self.collapsed_changed.emit(collapsed)
        self._fit_names()

    def resizeEvent(self, event) -> None:  # noqa: N802 -- Qt API name
        super().resizeEvent(event)
        self._fit_names()

    def showEvent(self, event) -> None:  # noqa: N802 -- Qt API name
        super().showEvent(event)
        self._fit_names()

    def _fit_names(self) -> None:
        """Icons only while the names do not fit the rail's height (see
        ``squeezed``); the names again once they fit."""
        if self.collapsed or not self.isVisible() or not self.buttons:
            return
        needed = self._named_height if self.squeezed else self.sizeHint().height()
        short = self.height() < needed
        if short == self.squeezed:
            return
        if short:
            self._named_height = needed
        self.squeezed = short
        for area_id in self.buttons:
            self._show_label(area_id)

    def _show_label(self, area_id: str) -> None:
        button, label, keys = self.buttons[area_id], self._labels[area_id], self._keys[area_id]
        button.setText(label)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly if self.collapsed or self.squeezed
                                  else Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        button.setToolTip(f"{label} ({keys})" if keys else label)
        button.setAccessibleName(label)

    def _show_collapse_state(self) -> None:
        name = "panel-left-open" if self.collapsed else "panel-left-close"
        self.collapse_button.setIcon(icon(name, "text.secondary"))
        text = "Show the area names" if self.collapsed else "Icons only"
        self.collapse_button.setToolTip(text)
        self.collapse_button.setAccessibleName(text)


class Shell(QWidget):
    """The rail and the areas. ``area_changed`` says which is shown."""

    area_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.rail = NavRail()
        self.stack = AreaStack()
        layout.addWidget(self.rail)
        self.work = QWidget()  # the window puts its top bar and banners above the stack
        self.work_layout = QVBoxLayout(self.work)
        self.work_layout.setContentsMargins(0, 0, 0, 0)
        self.work_layout.setSpacing(0)
        self.work_layout.addWidget(self.stack, 1)
        layout.addWidget(self.work, 1)
        self.areas: dict[str, Area] = {}
        self.rail.area_chosen.connect(self.show_area)
        self.stack.currentChanged.connect(self._on_current_changed)

    def register(self, area_id: str, icon_name: str, label: str, content: QWidget | None, order: int,
                 bottom: bool = False, action: QAction | None = None, keys: str = "") -> Area:
        """Add an area: ``content`` is the screen it hosts (None for a
        button that triggers ``action``); ``order`` places it on the rail;
        ``keys`` is the shortcut shown in its tooltip."""
        if area_id in self.areas:
            raise ValueError(f"area {area_id!r} is registered twice")
        page = AreaPage(area_id, label, content) if content is not None else None
        area = Area(area_id, label, icon_name, order, page, bottom, action)
        self.areas[area_id] = area
        if page is not None:
            self.stack.addWidget(page)
        # In its place among the areas of its group: a later area slots in.
        index = sum(1 for other in self.areas.values()
                    if other.bottom == bottom and other.order < order)
        self.rail.add_area(area, keys, index)
        return area

    def page(self, area_id: str) -> AreaPage:
        page = self.areas[area_id].page
        if page is None:
            raise KeyError(f"area {area_id!r} has no page")
        return page

    def show_area(self, area_id: str) -> None:
        self.stack.setCurrentWidget(self.page(area_id))

    def current_area(self) -> str | None:
        page = self.stack.currentWidget()
        return page.area_id if isinstance(page, AreaPage) else None

    def area_of(self, widget: QWidget) -> str | None:
        """The area whose page holds ``widget``, or None."""
        return next((area.id for area in self.areas.values()
                     if area.page is not None and (area.page is widget or area.page.isAncestorOf(widget))), None)

    def page_areas(self) -> list[Area]:
        """The areas with a page, in rail order."""
        return [area for area in sorted(self.areas.values(), key=lambda a: a.order) if area.page is not None]

    def _on_current_changed(self, _index: int) -> None:
        area_id = self.current_area()
        if area_id is not None:
            self.rail.set_current(area_id)
            self.area_changed.emit(area_id)
