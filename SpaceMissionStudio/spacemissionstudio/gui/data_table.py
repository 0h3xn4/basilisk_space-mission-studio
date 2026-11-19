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

"""DataTable (UI overhaul M6b): a table of values with the table rules
(CLAUDE.md, Tables), for the views that showed a ``QTableWidget``.

- a ``QTableView`` over :class:`DataModel` (a ``QAbstractTableModel``),
  through :class:`_Filter` (a ``QSortFilterProxyModel``);
- a sticky header, its headings left-aligned (a numeric column's right);
  numeric columns right-aligned in the numeric font, their unit in the
  header (a cell of text in one, :class:`Row` ``plain``, left-aligned);
  code columns (keys, identifiers) in the monospace font and the
  secondary colour; no zebra, no grid lines (surfaces, not lines; UI audit
  B4); row hover (the style sheet);
- Ctrl+C and :meth:`DataTable.copy` copy the selected rows (or every
  shown row) as TSV with the header; :meth:`DataTable.text` is the same
  text for the rows shown;
- the header's context menu shows and hides columns;
- a cell can carry a muted second line (:class:`Row` ``notes``): a
  parameter's key under its name, in the monospace font (UI-19); the rows
  are then two lines high;
- a group row (:class:`Row` ``group=True``) spans the table as a section
  heading: the heading weight on the canvas surface, never selectable
  (it looked selected on the selected-row surface, UI-19);
- the rows can be any sequence of :class:`Row` (a long table's are made
  when the view asks for them, :class:`LazyRows`); such a table sorts
  itself (:meth:`DataTable.set_presorted`) instead of through the proxy;
- filtering is a predicate on the model's rows (:meth:`DataTable.set_row_filter`);
  columns can be hidden (:meth:`DataTable.set_hidden_columns`);
- an empty state (its text, and its action when one is given)
  instead of an empty grid;
- rows at the theme's table-row height (``ROW_HEIGHT``, UI audit B9);
- a table that fits its width (:meth:`DataTable.set_fit_width`, UI audit
  UI-27): the columns share the width of the view, the longest texts
  elided first and never a heading cut (:func:`fit_widths`); it scrolls
  sideways only when even its headings do not fit. A short table of text
  can name its ``wrap`` columns instead (UI audit B12, Reports ›
  Exports): their text wraps at word boundaries, never narrower than its
  longest word, and each row grows to its tallest cell, so every entry
  reads whole without hover; the other columns keep their whole text;
- a cell whose text is elided shows it whole on hover (its own tooltip
  first).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Callable, Sequence
from collections.abc import Sequence as SequenceABC

from PySide6.QtCore import QAbstractTableModel, QEvent, QObject, QRect, QSortFilterProxyModel, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QKeySequence, QPalette
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QHeaderView, QLabel, QMenu, QPushButton,
                               QStackedWidget, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QTableView,
                               QToolTip, QVBoxLayout, QWidget)

from . import units
from .theme import ROW_HEIGHT, TOKENS, icon, mono_font, numeric_font, set_role, ui_font

_SORT_ROLE = Qt.ItemDataRole.UserRole  # a cell's sort key (Row.keys)
NOTE_ROLE = Qt.ItemDataRole.UserRole + 1  # a cell's muted second line (Row.notes)
_SIZED_ROWS = 200  # rows a column's width is measured from
_CELL_PAD_PX = 16  # [px] beside a cell's text (the style sheet's padding and the grid)
_HEADER_PAD_PX = 28  # [px] beside a heading (its padding and the sort indicator)
_ICON_PAD_PX = 24  # [px] a status icon (16 px) and its gap, before a marked cell's text
_MAX_COLUMN_PX = 480  # [px] a long text is elided past this; the column can still be dragged wider


def fit_widths(wanted: Sequence[int], floors: Sequence[int], room: int, grow: int = -1) -> list[int]:
    """[px] column widths that share ``room`` (UI audit B9): each column
    ``wanted`` wide when they all fit, column ``grow`` taking what is left;
    else the widest are cut down to one width (their text elided), never
    below their ``floors`` (a heading's width); when even the floors do not
    fit, ``wanted`` (the table then scrolls sideways, and nothing need be
    elided)."""
    floors = [min(floor, want) for floor, want in zip(floors, wanted)]
    if not wanted:
        return []
    if sum(wanted) <= room:
        widths = list(wanted)
        widths[grow] += room - sum(widths)
        return widths
    if sum(floors) >= room:
        return list(wanted)
    low, high = 0, max(wanted)  # the one width the widest columns are cut to: the largest that fits
    while low < high:
        cap = (low + high + 1) // 2
        if sum(max(floor, min(want, cap)) for floor, want in zip(floors, wanted)) <= room:
            low = cap
        else:
            high = cap - 1
    widths = [max(floor, min(want, low)) for floor, want in zip(floors, wanted)]
    widths[grow] += room - sum(widths)  # the pixels the rounding left
    return widths


@dataclass
class Row:
    """One row: a text per column; ``tooltips`` by column; ``keys`` the
    values a sortable table sorts by (default: the texts); ``group`` makes
    it a heading row across the table (its first cell only); ``bold`` sets
    the row in the heading weight (Budget's worst case); ``muted`` are
    columns in the secondary colour (Compare's "(same)"); ``plain`` are
    cells of numeric columns that hold text (a model's name), left-aligned
    in the UI font; ``marks`` give a cell a status's icon and text colour,
    ``{column: (icon, icon ink, text ink)}`` ("circle-check",
    "status.normal", "status.normal.text"): the word in the cell says the
    status too, never the colour alone; ``notes`` are a muted second line
    under a cell's text, in the monospace font (a key under a name)."""

    cells: Sequence[str]
    tooltips: dict[int, str] = field(default_factory=dict)
    keys: Sequence | None = None
    group: bool = False
    bold: bool = False
    muted: frozenset = frozenset()
    plain: frozenset = frozenset()
    marks: dict[int, tuple[str, str, str]] = field(default_factory=dict)
    notes: dict[int, str] = field(default_factory=dict)


class LazyRows(SequenceABC):
    """Rows made when asked for (a long table): :meth:`make` builds row
    ``index`` of the current order, kept until the order changes;
    :meth:`sort` reorders them by a column."""

    has_groups = False

    def __init__(self, count: int) -> None:
        self.count = count
        self._made: dict[int, Row] = {}

    def __len__(self) -> int:
        return self.count

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self[i] for i in range(*index.indices(self.count))]
        if index < 0:
            index += self.count
        if not 0 <= index < self.count:
            raise IndexError(index)
        row = self._made.get(index)
        if row is None:
            row = self._made[index] = self.make(index)
        return row

    def forget(self) -> None:
        """Make the rows again (their order changed)."""
        self._made = {}

    def make(self, index: int) -> Row:
        raise NotImplementedError

    def sort(self, column: int, descending: bool) -> None:
        raise NotImplementedError


class DataModel(QAbstractTableModel):
    """The rows of a :class:`DataTable`."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.headers: list[str] = []
        self.header_tooltips: dict[int, str] = {}
        self.bold_columns: set = set()
        self.numeric: set = set()  # columns of numbers
        self.code: set = set()  # columns of keys and identifiers
        self.rows: Sequence[Row] = []
        self.has_groups = False
        self.has_notes = False
        # Made once: data() is asked for every cell's font while the view sizes
        # its columns, and a QFont with its features is slow to make.
        self._numeric_font = numeric_font()
        self._heading_font = ui_font("small", "semibold")
        self._code_font = mono_font()

    def set_table(self, headers: Sequence[str], rows: Sequence[Row], numeric: Sequence[int] = (),
                  code: Sequence[int] = ()) -> None:
        self.beginResetModel()
        self.headers, self.numeric, self.code = list(headers), set(numeric), set(code)
        self.rows = rows if isinstance(rows, LazyRows) else list(rows)
        self.has_groups = bool(self.rows.has_groups) if isinstance(rows, LazyRows) else any(r.group for r in rows)
        self.has_notes = not isinstance(rows, LazyRows) and any(r.notes for r in rows)
        self.header_tooltips, self.bold_columns = {}, set()
        self.endResetModel()

    def reorder(self, column: int, descending: bool) -> None:
        """Sort lazy rows by ``column`` (they sort themselves)."""
        self.beginResetModel()
        self.rows.sort(column, descending)
        self.rows.forget()
        self.endResetModel()

    def set_header_marks(self, bold: Sequence[int], tooltips: dict[int, str]) -> None:
        """Columns whose header is in bold (Output's report at the time cursor), and header tooltips."""
        self.bold_columns, self.header_tooltips = set(bold), dict(tooltips)
        if self.headers:
            self.headerDataChanged.emit(Qt.Orientation.Horizontal, 0, len(self.headers) - 1)

    def rowCount(self, parent=None) -> int:  # noqa: N802 -- Qt API name
        return 0 if parent is not None and parent.isValid() else len(self.rows)

    def columnCount(self, parent=None) -> int:  # noqa: N802 -- Qt API name
        return 0 if parent is not None and parent.isValid() else len(self.headers)

    def text(self, row: int, column: int) -> str:
        cells = self.rows[row].cells
        return cells[column] if column < len(cells) else ""

    def note(self, row: int, column: int) -> str:
        """The muted second line of a cell ("" for none)."""
        return self.rows[row].notes.get(column, "")

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row, column = self.rows[index.row()], index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            return self.text(index.row(), column)
        if role == Qt.ItemDataRole.ToolTipRole:
            return row.tooltips.get(column)
        if role == NOTE_ROLE:
            return row.notes.get(column)
        if role == _SORT_ROLE:
            return row.keys[column] if row.keys is not None and column < len(row.keys) else self.text(index.row(),
                                                                                                         column)
        if row.group:
            if role == Qt.ItemDataRole.FontRole:
                return self._heading_font
            if role == Qt.ItemDataRole.BackgroundRole:
                return QColor(TOKENS["bg.canvas"])  # a section's heading; looked up when drawn: follows a theme change
            return None
        mark = row.marks.get(column)
        if mark is not None:
            if role == Qt.ItemDataRole.DecorationRole:
                return icon(mark[0], mark[1])
            if role == Qt.ItemDataRole.ForegroundRole:
                return QColor(TOKENS[mark[2]])  # looked up when drawn: it follows a theme change
        if role == Qt.ItemDataRole.FontRole and row.bold:
            return self._heading_font
        if role == Qt.ItemDataRole.ForegroundRole and (column in row.muted or column in self.code):
            return QColor(TOKENS["text.secondary"])  # looked up when drawn: it follows a theme change
        if column in self.code and role == Qt.ItemDataRole.FontRole:
            return self._code_font
        if column in self.numeric and column not in row.plain:
            if role == Qt.ItemDataRole.TextAlignmentRole:
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if role == Qt.ItemDataRole.FontRole:
                return self._numeric_font
        return None

    def flags(self, index):
        flags = super().flags(index)
        # A heading is not a row to pick. Only a table with headings looks (a lazy row is made when read).
        if self.has_groups and index.isValid() and self.rows[index.row()].group:
            flags &= ~Qt.ItemFlag.ItemIsSelectable
        return flags

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802 -- Qt API name
        if orientation != Qt.Orientation.Horizontal or not 0 <= section < len(self.headers):
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return units.label(self.headers[section])  # "[deg]" shows "[°]" (UI-35); the copy keeps the text
        if role == Qt.ItemDataRole.ToolTipRole:
            return self.header_tooltips.get(section)
        if role == Qt.ItemDataRole.FontRole and section in self.bold_columns:
            return self._heading_font
        if role == Qt.ItemDataRole.TextAlignmentRole:
            horizontal = Qt.AlignmentFlag.AlignRight if section in self.numeric else Qt.AlignmentFlag.AlignLeft
            return int(horizontal | Qt.AlignmentFlag.AlignVCenter)
        return None


class _Filter(QSortFilterProxyModel):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.predicate: Callable[[int], bool] | None = None

    def filterAcceptsRow(self, source_row, source_parent) -> bool:  # noqa: N802 -- Qt API name
        return self.predicate is None or self.predicate(source_row)


class _Direct:
    """The view on the model itself (a :class:`DataTable` with ``direct``):
    what the filter proxy offers, for the model's own rows. A long lazy
    table is filtered by its owner, and the proxy called Python once a row
    on every change (10,000 calls)."""

    predicate = None

    def __init__(self, model: DataModel) -> None:
        self.model = model

    def mapToSource(self, index):  # noqa: N802 -- the proxy's name
        return index

    def index(self, row: int, column: int):
        return self.model.index(row, column)

    def rowCount(self) -> int:  # noqa: N802 -- the proxy's name
        return self.model.rowCount()

    def data(self, index, role):
        return self.model.data(index, role)

    def invalidate(self) -> None:
        pass


def _wrapped_height(metrics: QFontMetrics, text: str, room: int) -> int:
    """[px] ``text`` wrapped at word boundaries to ``room``: its lines' height."""
    return metrics.boundingRect(QRect(0, 0, max(room, 1), 1 << 20), int(Qt.TextFlag.TextWordWrap), text).height()


def _longest_word(metrics: QFontMetrics, text: str) -> int:
    """[px] the widest word of ``text``: a wrapped column is never narrower."""
    return max((metrics.horizontalAdvance(word) for word in str(text).split()), default=0)


def _elided(view: QTableView, index) -> bool:
    """Whether the text of cell ``index`` is wider than its column leaves it
    (in a wrapping column: a word wider than it, or more lines than its row holds)."""
    text = index.data(Qt.ItemDataRole.DisplayRole)
    if not text:
        return False
    font = index.data(Qt.ItemDataRole.FontRole) or view.font()
    room = view.columnWidth(index.column()) - _CELL_PAD_PX
    if index.data(Qt.ItemDataRole.DecorationRole) is not None:
        room -= _ICON_PAD_PX
    metrics = QFontMetrics(font)
    if index.column() in getattr(view, "wrap_columns", ()):
        lines = _wrapped_height(metrics, str(text), room)
        return _longest_word(metrics, str(text)) > room or lines > view.rowHeight(index.row()) - _row_pad(view)
    return metrics.horizontalAdvance(str(text)) > room


def text_elided(view: QTableView, index) -> bool:
    """Whether the text of cell ``index`` of ``view`` (any table view) is
    elided: wider than its column leaves it."""
    return _elided(view, index)


def _row_pad(view: QTableView) -> int:
    """[px] a row's height above and below its text: the table-row height less one line."""
    return max(ROW_HEIGHT - QFontMetrics(view.font()).height(), 0)


class _CellDelegate(QStyledItemDelegate):
    """A cell as usual; on hover, its tooltip, or its whole text when the
    column elides it (UI audit B9)."""

    def helpEvent(self, event, view, option, index) -> bool:  # noqa: N802 -- Qt API name
        if event.type() == QEvent.Type.ToolTip and index.isValid() and not index.data(Qt.ItemDataRole.ToolTipRole) \
                and _elided(view, index):
            QToolTip.showText(event.globalPos(), str(index.data(Qt.ItemDataRole.DisplayRole)), view)
            return True
        return super().helpEvent(event, view, option, index)


class _NoteDelegate(_CellDelegate):
    """Paints a cell with a second line (:data:`NOTE_ROLE`): its text, and
    under it the note in the monospace font and the secondary colour, each
    elided to the cell's width; any other cell as usual."""

    def __init__(self, font: QFont, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.note_font = font

    def paint(self, painter, option, index) -> None:
        note = index.data(NOTE_ROLE)
        if not note:
            super().paint(painter, option, index)
            return
        item = QStyleOptionViewItem(option)
        self.initStyleOption(item, index)
        text, item.text = item.text, ""
        style = item.widget.style() if item.widget is not None else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, item, painter, item.widget)  # surface, hover, focus
        margin = style.pixelMetric(QStyle.PixelMetric.PM_FocusFrameHMargin, item, item.widget) + 1  # as Qt's own text
        rect = style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, item, item.widget).adjusted(
            margin, 0, -margin, 0)
        half = rect.height() // 2
        left = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        painter.save()
        painter.setFont(item.font)
        painter.setPen(item.palette.color(QPalette.ColorRole.Text))
        painter.drawText(rect.adjusted(0, 0, 0, -half), left,
                         QFontMetrics(item.font).elidedText(text, Qt.TextElideMode.ElideRight, rect.width()))
        painter.setFont(self.note_font)
        painter.setPen(QColor(TOKENS["text.secondary"]))  # looked up when drawn: it follows a theme change
        painter.drawText(rect.adjusted(0, half, 0, 0), left,
                         QFontMetrics(self.note_font).elidedText(note, Qt.TextElideMode.ElideMiddle, rect.width()))
        painter.restore()


class _View(QTableView):
    copy_requested = Signal()
    resized = Signal()  # its width changed: a table that fits its width fits again
    wrap_columns: frozenset = frozenset()  # the columns whose text wraps (DataTable.set_fit_width)

    def resizeEvent(self, event):  # noqa: N802 -- Qt API name
        super().resizeEvent(event)
        if event.size().width() != event.oldSize().width():
            self.resized.emit()

    def keyPressEvent(self, event):  # noqa: N802 -- Qt API name
        if event.matches(QKeySequence.StandardKey.Copy):
            self.copy_requested.emit()
            return
        super().keyPressEvent(event)


class DataTable(QWidget):
    """A table of values (see the module docstring). ``action_requested``:
    the empty state's action."""

    action_requested = Signal()
    row_chosen = Signal(int)  # the model row picked (set_single_pick)
    sorted = Signal(int)  # a presorted table was sorted by this column (set_presorted)

    def __init__(self, empty_text: str = "Nothing to show.", action: str | None = None,
                 parent: QWidget | None = None, direct: bool = False) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)
        self.empty = QWidget()
        empty_layout = QVBoxLayout(self.empty)
        empty_layout.addStretch(1)
        self.empty_label = set_role(QLabel(empty_text), tone="secondary")
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self.empty_label)
        self.empty_button = QPushButton(action or "")  # secondary: the top bar's Run is the one accent (UI-03)
        self.empty_button.setVisible(action is not None)
        self.empty_button.clicked.connect(self.action_requested)
        empty_layout.addWidget(self.empty_button, 0, Qt.AlignmentFlag.AlignHCenter)
        empty_layout.addStretch(1)
        self.stack.addWidget(self.empty)

        self.model = DataModel(self)
        if direct:  # no filter proxy: the owner filters (a long lazy table)
            self.proxy = _Direct(self.model)
        else:
            self.proxy = _Filter(self)
            self.proxy.setSourceModel(self.model)
            self.proxy.setSortRole(_SORT_ROLE)
        self.view = _View()
        self.view.setModel(self.model if direct else self.proxy)
        self.view.verticalHeader().setVisible(False)
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setWordWrap(False)
        self.view.setShowGrid(False)  # surfaces, not lines (UI audit B4)
        self._one_line_px = ROW_HEIGHT  # [px] the theme's table row (UI audit B9; Qt's own was about 30 px)
        self.view.verticalHeader().setDefaultSectionSize(self._one_line_px)
        self._cells = _CellDelegate(self.view)
        self.view.setItemDelegate(self._cells)
        self._notes = _NoteDelegate(self.model._code_font, self.view)
        self._fit_width = False  # set_fit_width
        self._natural: list[int] = []  # [px] each column's width for its heading and text (_size_columns)
        self._floors: list[int] = []  # [px] each column's heading width
        self._grow = -1  # the column that takes the width left
        # Fitted again once the view's width, or its vertical scroll bar (the viewport's width), changes.
        self._fit_timer = QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.setInterval(0)
        self._fit_timer.timeout.connect(self._fit_columns)
        self.view.setTabKeyNavigation(False)  # read-only: Tab leaves the table; the arrows move in it (M9)
        self.view.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.view.copy_requested.connect(lambda: QGuiApplication.clipboard().setText(self.copy_text()))
        header = self.view.horizontalHeader()
        header.setResizeContentsPrecision(_SIZED_ROWS)
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(self._on_header_menu)
        self.stack.addWidget(self.view)
        self.stack.setCurrentWidget(self.empty)

    # -- content ------------------------------------------------------------------------------
    def set_table(self, headers: Sequence[str], rows: Sequence[Row], numeric: Sequence[int] = (),
                  stretch: int = 0, code: Sequence[int] = ()) -> None:
        """Show ``rows`` under ``headers``; ``numeric`` are the columns of
        numbers, ``code`` those of keys and identifiers; column ``stretch``
        takes the width left, the others their content's."""
        self.view.setUpdatesEnabled(False)
        self.model.set_table(headers, rows, numeric, code)
        header = self.view.horizontalHeader()
        for column in range(len(headers)):
            # Sized to their content once, here, not on every layout of the view
            # (that asked for every cell's text and font at each one, M6b).
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch if column == stretch
                                        else QHeaderView.ResizeMode.Interactive)
            self.view.setColumnHidden(column, False)
        self._grow = stretch
        self._size_columns(-2 if self._fit_width else stretch)  # fitted: every column measured
        self._fit_columns()
        self._show_notes()
        self._update_spans()
        self.view.setUpdatesEnabled(True)
        self.stack.setCurrentWidget(self.view if rows else self.empty)

    def _size_columns(self, stretch: int) -> None:
        """Each column as wide as its heading and the text of a sample of
        rows (M7: Qt's own sizing asked the model for every role of every
        sampled cell, 200 ms for a 10,000-event table)."""
        rows = self.model.rows
        sample = range(min(len(rows), _SIZED_ROWS // 4))  # the first rows: a lazy table makes no others
        header_metrics = QFontMetrics(self._header_font())
        plain, numbers = QFontMetrics(self.view.font()), QFontMetrics(self.model._numeric_font)
        codes = QFontMetrics(self.model._code_font)
        bold = QFontMetrics(self.model._heading_font)
        self._natural, self._floors = [], []
        header = self.view.horizontalHeader()
        for column, heading in enumerate(self.model.headers):
            # The heading's width, and at least its size as the style draws it (font, padding, margins, sort arrow).
            floor = max(max(header_metrics.horizontalAdvance(line) for line in units.label(heading).split("\n"))
                        + _HEADER_PAD_PX, header.sectionSizeHint(column))
            self._floors.append(floor)
            if column == stretch:
                self._natural.append(floor)
                continue
            width = floor
            word = 0  # [px] the widest word: a wrapping column is never narrower (UI audit B12)
            metrics = numbers if column in self.model.numeric else codes if column in self.model.code else plain
            for index in sample:
                row = rows[index]
                if row.group or column >= len(row.cells):
                    continue
                font = bold if row.bold else plain if column in row.plain else metrics
                pad = _CELL_PAD_PX + (_ICON_PAD_PX if column in row.marks else 0)
                width = max(width, font.horizontalAdvance(row.cells[column]) + pad)
                word = max(word, _longest_word(font, row.cells[column]) + pad)
            self._natural.append(min(width, _MAX_COLUMN_PX))
            if self.view.wrap_columns:  # a wrapping column down to its longest word; the others whole
                self._floors[-1] = max(floor, word) if column in self.view.wrap_columns else self._natural[-1]
            self.view.setColumnWidth(column, self._natural[-1])

    def set_fit_width(self, on: bool = True, wrap: Sequence[int] = ()) -> None:
        """Fit the columns to the view's width (UI audit UI-27): call before
        :meth:`set_table`. The longest texts are elided first (whole on
        hover), a heading is never cut, the ``stretch`` column takes what
        is left; only a table whose headings alone are too wide scrolls
        sideways.

        ``wrap`` (UI audit B12, for a short table of text such as Reports ›
        Exports): these columns' text wraps instead of being elided, never
        narrower than its longest word; the others keep their whole text;
        each row is as tall as its tallest cell. Every entry then reads
        whole without hover."""
        if on and not self._fit_width:
            self.view.resized.connect(self._fit_timer.start)
            self.view.verticalScrollBar().rangeChanged.connect(lambda *_range: self._fit_timer.start())
        self._fit_width = on
        self.view.wrap_columns = frozenset(wrap) if on else frozenset()
        self.view.setWordWrap(bool(self.view.wrap_columns))

    def _fit_columns(self) -> None:
        """The shown columns fitted to the view's width (:func:`fit_widths`)."""
        if not self._fit_width or not self._natural:
            return
        columns = self.shown_columns()
        room = self.view.viewport().width()
        if not columns or room <= 0:
            return
        grow = columns.index(self._grow) if self._grow in columns else -1
        widths = fit_widths([self._natural[c] for c in columns], [self._floors[c] for c in columns], room, grow)
        for column, width in zip(columns, widths):
            if column != self._grow:  # the stretching column takes the rest itself
                self.view.setColumnWidth(column, width)
        if self.view.wrap_columns:
            self._fit_row_heights(dict(zip(columns, widths)))

    def _fit_row_heights(self, widths: dict[int, int]) -> None:
        """Each row as tall as its tallest wrapped cell at ``widths`` (the
        columns' widths), at least the table-row height (UI audit B12)."""
        header = self.view.verticalHeader()
        pad = _row_pad(self.view)
        metrics = QFontMetrics(self.view.font())
        for row in range(self.proxy.rowCount()):
            lines = metrics.height()
            for column in self.view.wrap_columns:
                if column in widths:
                    text = self.proxy.index(row, column).data(Qt.ItemDataRole.DisplayRole) or ""
                    lines = max(lines, _wrapped_height(metrics, str(text), widths[column] - _CELL_PAD_PX))
            header.resizeSection(row, max(self._one_line_px, lines + pad))

    def cell_elided(self, row: int, column: int) -> bool:
        """Whether the shown row ``row``'s cell in ``column`` is elided (too long for its column)."""
        return _elided(self.view, self.proxy.index(row, column))

    def hover_text(self, row: int, column: int) -> str | None:
        """What hovering the shown row ``row``'s cell shows: its tooltip, or
        its whole text when it is elided (None: nothing)."""
        tooltip = self.cell_tooltip(row, column)
        if tooltip:
            return tooltip
        return self.cell(row, column) if self.cell_elided(row, column) else None

    def _show_notes(self) -> None:
        """Rows two lines high, painted by the note delegate, while a row has a note."""
        if self.model.has_notes:
            self.view.setItemDelegate(self._notes)
            self.view.verticalHeader().setDefaultSectionSize(
                self._one_line_px + QFontMetrics(self.model._code_font).height())
        elif self.view.itemDelegate() is self._notes:
            self.view.setItemDelegate(self._cells)
            self.view.verticalHeader().setDefaultSectionSize(self._one_line_px)

    def _header_font(self):
        return self.view.horizontalHeader().font()

    def clear(self, empty_text: str | None = None) -> None:
        self.model.set_table([], [])
        self.view.clearSpans()
        if empty_text is not None:
            self.empty_label.setText(empty_text)
        self.stack.setCurrentWidget(self.empty)

    def set_empty_text(self, text: str) -> None:
        self.empty_label.setText(text)

    def set_row_filter(self, predicate: Callable[[int], bool] | None) -> None:
        """Show the model rows ``predicate(row)`` accepts (None: every row; not for a ``direct`` table)."""
        self.proxy.predicate = predicate
        self.proxy.invalidate()
        self._update_spans()

    def set_hidden_columns(self, columns: Sequence[int]) -> None:
        hidden = set(columns)
        for column in range(self.model.columnCount()):
            self.view.setColumnHidden(column, column in hidden)
        self._fit_columns()

    def set_single_pick(self) -> None:
        """One row at a time is picked; ``row_chosen`` carries it (a model row)."""
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.view.selectionModel().selectionChanged.connect(self._on_picked)

    def _on_picked(self, *_args) -> None:
        rows = self.view.selectionModel().selectedRows()
        if rows:
            self.row_chosen.emit(self.proxy.mapToSource(rows[0]).row())

    def chosen_row(self) -> int | None:
        """The model row picked, or None."""
        rows = self.view.selectionModel().selectedRows()
        return self.proxy.mapToSource(rows[0]).row() if rows else None

    def fit_rows(self) -> None:
        """As tall as its rows: a short table under others needs no scroll bar of its own."""
        header = self.view.horizontalHeader()
        self.view.setFixedHeight(header.height() + sum(self.view.rowHeight(r) for r in range(self.row_count())) + 4)

    def row_is_bold(self, row: int) -> bool:
        """The shown row ``row`` is in the heading weight."""
        return self.model.rows[self.shown_rows()[row]].bold

    def set_sortable(self, column: int = 0, order=Qt.SortOrder.AscendingOrder) -> None:
        """Sort by a header click, by the rows' keys; sorted by ``column`` first."""
        self.view.setSortingEnabled(True)
        self.view.sortByColumn(column, order)

    def set_presorted(self) -> None:
        """A header click sorts the rows themselves (:class:`LazyRows`):
        sorting through the proxy would ask every row's key, one call a
        comparison."""
        header = self.view.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        header.sortIndicatorChanged.connect(self._on_presorted_click)
        self._presorted = True

    def _on_presorted_click(self, column: int, order) -> None:
        if isinstance(self.model.rows, LazyRows):
            self.model.reorder(column, order == Qt.SortOrder.DescendingOrder)
            self._update_spans()
        self.sorted.emit(column)

    def sort_by(self, column: int, order=Qt.SortOrder.AscendingOrder) -> None:
        if getattr(self, "_presorted", False):
            header = self.view.horizontalHeader()
            if header.sortIndicatorSection() == column and header.sortIndicatorOrder() == order:
                self._on_presorted_click(column, order)  # already shown: sort the (new) rows again
            else:
                header.setSortIndicator(column, order)  # sorts the rows (sortIndicatorChanged)
            return
        self.view.sortByColumn(column, order)

    def column_count(self) -> int:
        return self.model.columnCount()

    def set_header_marks(self, bold: Sequence[int] = (), tooltips: dict[int, str] | None = None) -> None:
        self.model.set_header_marks(bold, tooltips or {})

    def _update_spans(self) -> None:
        self.view.clearSpans()
        columns = self.model.columnCount()
        if not self.model.has_groups:
            return
        for row in range(self.proxy.rowCount()):
            source = self.proxy.mapToSource(self.proxy.index(row, 0)).row()
            if self.model.rows[source].group and columns > 1:
                self.view.setSpan(row, 0, 1, columns)

    # -- reading it ---------------------------------------------------------------------------
    def row_count(self) -> int:
        """The rows shown."""
        return self.proxy.rowCount()

    def shown_rows(self) -> list[int]:
        """The model rows shown, in their order."""
        return [self.proxy.mapToSource(self.proxy.index(row, 0)).row() for row in range(self.proxy.rowCount())]

    def shown_columns(self) -> list[int]:
        return [c for c in range(self.model.columnCount()) if not self.view.isColumnHidden(c)]

    def header_text(self, column: int) -> str:
        return self.model.headers[column]

    def header_is_bold(self, column: int) -> bool:
        return column in self.model.bold_columns

    def cell(self, row: int, column: int) -> str:
        """The text of the shown row ``row``, column ``column``."""
        return self.model.text(self.shown_rows()[row], column)

    def cell_alignment(self, row: int, column: int) -> int:
        """The alignment flags of the shown row ``row``'s cell (0: the default, left)."""
        index = self.proxy.index(row, column)
        return int(self.proxy.data(index, Qt.ItemDataRole.TextAlignmentRole) or 0)

    def cell_note(self, row: int, column: int) -> str:
        """The muted second line of the shown row ``row``'s cell ("" for none)."""
        return self.model.note(self.shown_rows()[row], column)

    def cell_tooltip(self, row: int, column: int) -> str | None:
        return self.model.rows[self.shown_rows()[row]].tooltips.get(column)

    def _tsv(self, rows: list[int]) -> str:
        columns = self.shown_columns()
        lines = ["\t".join(self.model.headers[c].replace("\n", " ") for c in columns)]
        for row in rows:
            lines.append("\t".join(self.model.text(row, c) for c in columns).rstrip("\t"))
        return "\n".join(lines)

    def text(self) -> str:
        """The rows shown as tab-separated text, the header first."""
        return self._tsv(self.shown_rows())

    def copy_text(self) -> str:
        """The selected rows (every row shown when none is) as TSV."""
        selected = sorted({self.proxy.mapToSource(index).row()
                           for index in self.view.selectionModel().selectedRows()})
        return self._tsv(selected or self.shown_rows())

    def copy(self) -> None:
        QGuiApplication.clipboard().setText(self.copy_text())

    def _on_header_menu(self, at) -> None:
        menu = QMenu(self)
        for column, name in enumerate(self.model.headers):
            action = menu.addAction(name.replace("\n", " "))
            action.setCheckable(True)
            action.setChecked(not self.view.isColumnHidden(column))
            action.setEnabled(column != 0)  # the first column names the row
            action.toggled.connect(lambda on, c=column: self._show_column(c, on))
        menu.popup(self.view.horizontalHeader().mapToGlobal(at))
        self.column_menu = menu  # kept while it is open

    def _show_column(self, column: int, shown: bool) -> None:
        self.view.setColumnHidden(column, not shown)
        self._fit_columns()
