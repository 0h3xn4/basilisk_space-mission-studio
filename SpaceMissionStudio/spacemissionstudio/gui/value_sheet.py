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

"""ValueSheet: values laid out to be read, not a line of text.

A run of "a 6928.000 km, e 0.000000, i 97.5900 deg, RAAN ..." reads as
noise. A value sheet gives each quantity its own row: the name on the
left in the secondary tone, the number right-aligned in tabular figures
so digits line up, and the unit beside it. A title says what the values
are; a note under it says what the reader should know (a frame, a
source). Values can be selected and copied.

Use it wherever the GUI shows several values of one thing: a dialog that
compares two states, a summary, a popover. ``rows`` are
``(name, value, unit)``; an empty unit leaves the cell blank.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .theme import SPACE, numeric_font, set_role

Row = tuple[str, str, str]


def _looks_numeric(value: str) -> bool:
    return bool(re.match(r"^[-+\u2212]?(\d|\.\d)", value.strip()))


class ValueSheet(QWidget):
    """A titled sheet of ``(name, value, unit)`` rows (module docstring)."""

    def __init__(self, title: str = "", rows: Iterable[Row] = (), note: str = "", empty: str = "",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(SPACE["xs"])
        self.title_label = set_role(QLabel(title, self), role="heading")  # a parent first: shown, it is no window
        self.title_label.setVisible(bool(title))
        column.addWidget(self.title_label)
        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(SPACE["md"])
        self.grid.setVerticalSpacing(SPACE["xs"])
        column.addLayout(self.grid)
        self.empty_label = set_role(QLabel(empty), tone="secondary")
        column.addWidget(self.empty_label)
        self.note_label = set_role(QLabel(note, self), role="caption")
        self.note_label.setVisible(bool(note))
        column.addWidget(self.note_label)
        column.addStretch(1)
        self.rows: list[Row] = []
        self.set_rows(rows)

    def set_rows(self, rows: Iterable[Row]) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.rows = [tuple(row) for row in rows]
        for index, (name, value, unit) in enumerate(self.rows):
            name_label = set_role(QLabel(name), tone="secondary")
            value_label = QLabel(value)
            if _looks_numeric(value):  # tabular figures for numbers; a name ("fits", an envelope) reads as text
                value_label.setFont(numeric_font("body"))
                value_label.setProperty("smsNumeric", True)
            value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            unit_label = set_role(QLabel(unit), tone="secondary")
            self.grid.addWidget(name_label, index, 0)
            self.grid.addWidget(value_label, index, 1)
            self.grid.addWidget(unit_label, index, 2)
        self.grid.setColumnStretch(3, 1)  # the room is left over on the right, values stay by their names
        self.empty_label.setVisible(not self.rows and bool(self.empty_label.text()))

    def value(self, name: str) -> str:
        """The value shown for ``name`` ("" when there is none)."""
        return next((value for row_name, value, _unit in self.rows if row_name == name), "")

    def text(self) -> str:
        """The sheet as plain lines, "name: value unit" (for copying, tests
        and screen readers)."""
        lines = [self.title_label.text()] if self.title_label.text() else []
        lines += [f"{name}: {value} {unit}".rstrip() for name, value, unit in self.rows]
        if not self.rows and self.empty_label.text():
            lines.append(self.empty_label.text())
        if self.note_label.text():
            lines.append(self.note_label.text())
        return "\n".join(lines)


class ValueTable(QWidget):
    """A small read-only table of values with a title: a header row in the
    caption style, numbers right-aligned in tabular figures, text left.
    For a matrix (an inertia tensor) or a handful of rows (principal
    axes); a long or sortable list is a :class:`gui.data_table.DataTable`.
    ``numeric`` names the columns (by index) that hold numbers."""

    def __init__(self, title: str, headers: list[str], rows: Iterable[Iterable[str]] = (),
                 numeric: Iterable[int] = (), note: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(SPACE["xs"])
        self.title_label = set_role(QLabel(title, self), role="heading")  # a parent first: shown, it is no window
        self.title_label.setVisible(bool(title))
        column.addWidget(self.title_label)
        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(SPACE["lg"])
        self.grid.setVerticalSpacing(SPACE["xs"])
        column.addLayout(self.grid)
        self.note_label = set_role(QLabel(note, self), role="caption")
        self.note_label.setVisible(bool(note))
        column.addWidget(self.note_label)
        self.headers = list(headers)
        self.numeric = set(numeric)
        self.rows: list[list[str]] = []
        self.set_rows(rows)

    def _align(self, index: int) -> Qt.AlignmentFlag:
        horizontal = Qt.AlignmentFlag.AlignRight if index in self.numeric else Qt.AlignmentFlag.AlignLeft
        return horizontal | Qt.AlignmentFlag.AlignVCenter

    def set_rows(self, rows: Iterable[Iterable[str]]) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.rows = [list(row) for row in rows]
        for index, header in enumerate(self.headers):
            label = set_role(QLabel(header), role="caption")
            label.setAlignment(self._align(index))
            self.grid.addWidget(label, 0, index)
        for row_index, row in enumerate(self.rows, start=1):
            for index, value in enumerate(row):
                label = QLabel(value)
                if index in self.numeric:
                    label.setFont(numeric_font("body"))
                elif index == 0:
                    set_role(label, tone="secondary")
                label.setAlignment(self._align(index))
                label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                self.grid.addWidget(label, row_index, index)
        self.grid.setColumnStretch(len(self.headers), 1)

    def text(self) -> str:
        """The table as tab-separated lines, with its title."""
        lines = [self.title_label.text()] if self.title_label.text() else []
        lines += ["\t".join(self.headers)] + ["\t".join(row) for row in self.rows]
        return "\n".join(lines)


class FoldSection(QWidget):
    """A titled part that starts folded: a disclosure button with the title,
    and the body under it once opened. For what a reader may want but need
    not see at first (a template's "What to look at", details of a
    finding): the screen shows the gist, the rest is one click away."""

    def __init__(self, title: str, body: QWidget, folded: bool = True, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from PySide6.QtWidgets import QToolButton

        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(SPACE["xs"])
        self.button = QToolButton()
        self.button.setText(title)
        self.button.setCheckable(True)
        self.button.setChecked(not folded)
        self.button.setAutoRaise(True)
        self.button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.button.setAccessibleName(title)
        self.button.toggled.connect(self.set_open)
        column.addWidget(self.button)
        self.body = body
        column.addWidget(body)
        self.set_open(not folded)

    def set_open(self, opened: bool) -> None:
        self.button.blockSignals(True)
        self.button.setChecked(opened)
        self.button.blockSignals(False)
        self.button.setArrowType(Qt.ArrowType.DownArrow if opened else Qt.ArrowType.RightArrow)
        self.body.setVisible(opened)

    def is_open(self) -> bool:
        return self.button.isChecked()


# kind: (Lucide icon, its ink, the text tone, the mark in ``text()``)
NOTE_KINDS = {
    "note": ("info", "text.secondary", "secondary", "-"),
    "warning": ("triangle-alert", "status.caution", None, "⚠"),
    "finding": ("circle-alert", "status.caution", None, "-"),
}
FOLD_AFTER = 4  # notes shown before "Show n more"


class _Mark(QWidget):
    """A 16 px icon painted each time, so it takes the theme's colour at once
    (``theme.icon`` reads its token when it paints)."""

    SIZE = 16  # [px]

    def __init__(self, name: str, ink: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from .theme import icon

        self._icon = icon(name, ink)
        self.setFixedSize(self.SIZE, self.SIZE)

    def paintEvent(self, _event) -> None:  # noqa: N802 -- Qt's name
        from PySide6.QtGui import QPainter

        painter = QPainter(self)
        self._icon.paint(painter, self.rect())
        painter.end()


class NoteList(QWidget):
    """Notes, warnings or findings one per row, each behind its icon, the
    text wrapped beside it; never a block of dash-led lines. After
    :data:`FOLD_AFTER` notes the rest wait behind "Show n more", so a long
    list does not push the page down. ``empty`` is shown when there are no
    notes ("No design finding."); with no ``empty`` the list takes no room.
    ``text()`` gives every note as a line behind its mark, for copying and
    tests."""

    def __init__(self, kind: str = "note", notes: Iterable[str] = (), empty: str = "",
                 fold_after: int = FOLD_AFTER, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from PySide6.QtWidgets import QPushButton

        self.kind = kind
        self.empty = empty
        self.fold_after = fold_after
        self.notes: list[str] = []
        self.rows: list[QWidget] = []
        self._column = QVBoxLayout(self)
        self._column.setContentsMargins(0, 0, 0, 0)
        self._column.setSpacing(SPACE["xs"])
        self.empty_label = set_role(QLabel(empty), tone="secondary")
        self.empty_label.setWordWrap(True)
        self._column.addWidget(self.empty_label)
        self.more_button = set_role(QPushButton(), variant="ghost")  # quiet: text, no frame
        self.more_button.setCheckable(True)
        self.more_button.toggled.connect(self._show_rows)
        self._column.addWidget(self.more_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.set_notes(notes)

    def set_notes(self, notes: Iterable[str]) -> None:
        for row in self.rows:
            self._column.removeWidget(row)
            row.deleteLater()
        self.notes = [str(note) for note in notes if str(note).strip()]
        icon_name, ink, tone, _mark = NOTE_KINDS[self.kind]
        self.rows = []
        for index, note in enumerate(self.notes):
            row = QWidget()
            line = QHBoxLayout(row)
            line.setContentsMargins(0, 0, 0, 0)
            line.setSpacing(SPACE["sm"])
            line.addWidget(_Mark(icon_name, ink), 0, Qt.AlignmentFlag.AlignTop)
            label = set_role(QLabel(note), tone=tone)
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            line.addWidget(label, 1)
            self._column.insertWidget(1 + index, row)
            self.rows.append(row)
        self.empty_label.setVisible(not self.notes and bool(self.empty))
        self.more_button.blockSignals(True)
        self.more_button.setChecked(False)
        self.more_button.blockSignals(False)
        self._show_rows(False)

    def _show_rows(self, all_shown: bool) -> None:
        hidden = max(len(self.rows) - self.fold_after, 0)
        for index, row in enumerate(self.rows):
            row.setVisible(all_shown or index < self.fold_after)
        self.more_button.setVisible(hidden > 0)
        self.more_button.setText("Show fewer" if all_shown else f"Show {hidden} more")

    # Qt's guess at the height of wrapped text lays it out narrow (four
    # lines for one): the list answers for the width it has, and asks its
    # layout again when that width changes (Results at 1280 x 720).
    _LAYOUT_WIDTH = 360  # [px] the width assumed before the list is laid out

    def _width(self) -> int:
        laid_out = self.testAttribute(Qt.WidgetAttribute.WA_Resized) or self.isVisible()
        return self.width() if laid_out else max(self.minimumWidth(), self._LAYOUT_WIDTH)

    def hasHeightForWidth(self) -> bool:  # noqa: N802 -- Qt's name
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 -- Qt's name
        return self.layout().totalHeightForWidth(width)

    def sizeHint(self):  # noqa: N802 -- Qt's name
        hint = super().sizeHint()
        hint.setHeight(self.heightForWidth(self._width()))
        return hint

    def resizeEvent(self, event) -> None:  # noqa: N802 -- Qt's name
        super().resizeEvent(event)
        if event.oldSize().width() != event.size().width():
            self.updateGeometry()

    def text(self) -> str:
        if not self.notes:
            return self.empty
        mark = NOTE_KINDS[self.kind][3]
        return "\n".join(f"{mark} {note}" for note in self.notes)
