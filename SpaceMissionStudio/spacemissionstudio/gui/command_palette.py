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
"""The command palette (UX/UI guidelines, "a command palette"; Ctrl+K):
every command of the window's action registry, every area and page, the
scenario's objects and the settings, found by typing a few letters of
their name.

Each word typed must appear in the entry or its keywords (a command's
older names: "events" finds the Timeline); entries whose name starts with
the first word come first. Enter runs the highlighted entry; a disabled
command is listed, greyed, and not run.

Each row (UI audit UI-40, :class:`_EntryDelegate`): the entry's name, its
path written with "›" (the window's one path separator; an entry's
``label`` keeps ">" as its key); its shortcut in a column of its own at
the right, in the monospace font; and, under a disabled command, why it
is off (also its tooltip): the reason the registry gives
(``ActionRegistry.set_available``), else the "Off:" line of its tooltip.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPalette
from PySide6.QtWidgets import (QApplication, QDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QStyle,
                               QStyledItemDelegate, QStyleOptionViewItem, QVBoxLayout, QWidget)

from .theme import ROW_HEIGHT, SPACE, TOKENS, mono_font, ui_font

PATH_SEPARATOR = " › "  # the window's one path separator (UI audit UI-23, UI-40)
_KEY_SEPARATOR = " > "  # in an entry's label, its key (tests, the docs' shortcut table, the Scenario tree's paths)
SHORTCUT_ROLE = Qt.ItemDataRole.UserRole + 1  # a row's shortcut, drawn in its own column
REASON_ROLE = Qt.ItemDataRole.UserRole + 2  # why a disabled row's command is off, drawn under its name
NOT_AVAILABLE = "Not available now."  # a disabled command that says no more


@dataclass
class PaletteEntry:
    label: str  # e.g. "Run > Run": its key; the palette shows it as "Run › Run" (:attr:`shown`)
    run: Callable[[], object]
    shortcut: str = ""
    enabled: bool = True
    keywords: str = ""  # other names it is found by, not shown
    reason: str = ""  # why it is disabled, when it is and the command says

    @property
    def shown(self) -> str:
        """The name as the palette shows it: its path written with "›"."""
        return self.label.replace(_KEY_SEPARATOR, PATH_SEPARATOR)


def _off_reason(command) -> str:
    """Why ``command`` (disabled) is off: the registry's reason, else the
    "Off:" line of its action's tooltip (``widgets.set_off_reason``'s
    form), else "" (the palette then says :data:`NOT_AVAILABLE`)."""
    if command.unavailable:
        return command.unavailable
    return next((line for line in command.action.toolTip().splitlines() if line.startswith("Off:")), "")


def command_entries(registry) -> list[PaletteEntry]:
    """One entry per command of ``registry`` (:class:`gui.actions.ActionRegistry`),
    named "Category > Command"."""
    return [PaletteEntry(f"{command.category} > {command.label}", command.action.trigger, command.keys,
                         command.action.isEnabled(), " ".join(command.keywords),
                         "" if command.action.isEnabled() else _off_reason(command)) for command in registry]


def matches(query: str, entries: list[PaletteEntry]) -> list[PaletteEntry]:
    """Entries containing every word of ``query`` (any case) in their name
    or keywords; those whose command name starts with the first word first,
    then in order."""
    words = query.lower().split()
    if not words:
        return list(entries)
    found = [e for e in entries if all(w in f"{e.label} {e.shown} {e.keywords}".lower() for w in words)]
    return sorted(found, key=lambda e: not e.label.lower().rsplit("> ", 1)[-1].startswith(words[0]))


class _EntryDelegate(QStyledItemDelegate):
    """A row: its name on the left; its shortcut at the right in the
    monospace font, a column of its own; under a disabled command's name,
    the reason it is off, in the caption size. Colours are read from the
    theme when drawn, so a theme switch needs nothing else."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.key_font = mono_font()
        self.reason_font = ui_font("caption")

    def _inset(self) -> int:
        return SPACE["sm"]  # [px] from the row's edges, as the list's own item padding

    def key_rect(self, option, index) -> QRect:
        """Where the shortcut is drawn: right-aligned at the row's right inset, on the first line."""
        keys = index.data(SHORTCUT_ROLE) or ""
        width = QFontMetrics(self.key_font).horizontalAdvance(keys)
        rect = option.rect.adjusted(self._inset(), 0, -self._inset(), 0)
        return QRect(rect.right() - width + 1, rect.top(), width, ROW_HEIGHT)

    def sizeHint(self, option, index) -> QSize:  # noqa: N802 -- Qt API name
        hint = super().sizeHint(option, index)
        height = ROW_HEIGHT
        if index.data(REASON_ROLE):
            height += QFontMetrics(self.reason_font).height() + SPACE["xs"]
        return QSize(hint.width(), height)

    def paint(self, painter, option, index) -> None:
        item = QStyleOptionViewItem(option)
        self.initStyleOption(item, index)
        name, item.text = item.text, ""
        widget = item.widget
        style = widget.style() if widget is not None else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, item, painter, widget)  # surface, hover, selection
        enabled = bool(index.flags() & Qt.ItemFlag.ItemIsEnabled)
        keys = index.data(SHORTCUT_ROLE) or ""
        reason = index.data(REASON_ROLE) or ""
        rect = option.rect.adjusted(self._inset(), 0, -self._inset(), 0)
        key_rect = self.key_rect(option, index)
        name_room = (key_rect.left() - SPACE["lg"] if keys else rect.right()) - rect.left()
        first = QRect(rect.left(), rect.top(), max(name_room, 0), ROW_HEIGHT)
        painter.save()
        text_colour = item.palette.color(QPalette.ColorGroup.Normal if enabled else QPalette.ColorGroup.Disabled,
                                         QPalette.ColorRole.Text)
        painter.setFont(item.font)
        painter.setPen(text_colour)
        middle = Qt.AlignmentFlag.AlignVCenter
        painter.drawText(first, Qt.AlignmentFlag.AlignLeft | middle,
                         QFontMetrics(item.font).elidedText(name, Qt.TextElideMode.ElideRight, first.width()))
        if keys:
            painter.setFont(self.key_font)
            painter.setPen(QColor(TOKENS["text.secondary"]))
            painter.drawText(key_rect, Qt.AlignmentFlag.AlignRight | middle, keys)
        if reason:
            painter.setFont(self.reason_font)
            painter.setPen(QColor(TOKENS["text.secondary"]))
            below = QRect(rect.left(), rect.top() + ROW_HEIGHT - SPACE["xs"], rect.width(),
                          option.rect.bottom() - rect.top() - ROW_HEIGHT + SPACE["xs"])
            painter.drawText(below, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                             QFontMetrics(self.reason_font).elidedText(reason, Qt.TextElideMode.ElideRight,
                                                                        below.width()))
        painter.restore()


class CommandPalette(QDialog):
    """Type to filter, arrows to choose, Enter to run, Esc to close."""

    def __init__(self, entries: list[PaletteEntry], parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Command Palette")
        self.resize(520, 420)  # [px]
        self._entries = entries
        self.ran: PaletteEntry | None = None
        layout = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Type a command, a page or an object, e.g. \"run\", \"save as\", \"sat-1\"")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._fill)
        self.search.returnPressed.connect(self.run_current)
        layout.addWidget(self.search)
        self.list = QListWidget()
        self.list.setObjectName("commandPaletteList")
        self.delegate = _EntryDelegate(self.list)
        self.list.setItemDelegate(self.delegate)
        self.list.setUniformItemSizes(False)  # a disabled command's row has its reason under it
        self.list.itemActivated.connect(lambda _item: self.run_current())
        layout.addWidget(self.list, 1)
        self.hint = QLabel("")
        layout.addWidget(self.hint)
        self.search.installEventFilter(self)
        self._fill("")

    def _fill(self, query: str) -> None:
        self.list.clear()
        for entry in matches(query, self._entries):
            item = QListWidgetItem(entry.shown)
            item.setData(Qt.ItemDataRole.UserRole, entry)
            item.setData(SHORTCUT_ROLE, entry.shortcut)
            item.setData(Qt.ItemDataRole.AccessibleTextRole,
                         f"{entry.shown}, {entry.shortcut}" if entry.shortcut else entry.shown)
            if not entry.enabled:
                reason = entry.reason or NOT_AVAILABLE
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                item.setData(REASON_ROLE, reason)
                item.setToolTip(reason)
            self.list.addItem(item)
        first = next((i for i in range(self.list.count()) if self.list.item(i).flags() & Qt.ItemFlag.ItemIsEnabled),
                     None)
        if first is not None:
            self.list.setCurrentRow(first)
        self.hint.setText("" if self.list.count() else "Nothing matches.")

    def eventFilter(self, watched, event):  # noqa: N802 -- Qt API name
        """Up and Down in the search box move through the list."""
        if watched is self.search and event.type() == event.Type.KeyPress and \
                event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            step = -1 if event.key() == Qt.Key.Key_Up else 1
            row = self.list.currentRow()
            while 0 <= row + step < self.list.count():
                row += step
                if self.list.item(row).flags() & Qt.ItemFlag.ItemIsEnabled:
                    self.list.setCurrentRow(row)
                    break
            return True
        return super().eventFilter(watched, event)

    def run_current(self) -> None:
        item = self.list.currentItem()
        entry = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if entry is None or not entry.enabled:
            return
        self.ran = entry
        self.accept()
        entry.run()
