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
"""The Budgets area (System Budget Studio merge, phase 1;
``docs/developer/system-budget-phase1-design.md``, section 8): a
spacecraft's equipment list, its static power budget per system mode, its
mass budget and, moved from Run › Budget, the delta-V and propellant
budget.

* :class:`BudgetsViews` -- the area's tabs (Equipment, Power, Mass,
  Pointing and, added by the window, Propellant) and the spacecraft picker of the
  area's header;
* :class:`EquipmentPage` -- the ``budgets`` section as editable tables:
  the items, the power modes of the item picked, the system modes and the
  power settings (buses, distribution loss, margins);
* :class:`PowerPage` -- ``analyses.power_budget`` of the spacecraft;
* :class:`MassPage` -- ``analyses.mass_budget`` of the spacecraft (the
  Mass budget group of Run › Design Checks, with the equipment list);
* :class:`PointingPage` -- the ``budgets.pointing`` subsection as editable
  tables (requirements, contributors) and ``engine.pointing_budget`` of
  it, each margin's status an icon and a word
  (``docs/developer/pointing-error-budget-design.md``, PE-1 to PE-20).

The editable tables are a model/view grid (:class:`GridModel`, a
``QAbstractTableModel`` with ``ItemIsEditable``; decision B-12). An edit
changes the page's copy of the section and :attr:`EquipmentPage.edited`
hands a copy to the window, which puts it in the scenario through
``ScenarioEditorWidget.set_budgets``: it is saved, undone and checked as
any other edit, and a problem shows in the Problems panel. A placeholder
(a null value or the source "TBD") reads "TBD" behind a caution icon.

The budgets are small (tens to hundreds of items) and are computed on the
GUI thread, only for the page shown, only when the area is shown, and
only when the spacecraft changed: an edit elsewhere in the scenario costs
the area nothing (decision B-23).
"""

from __future__ import annotations

import copy
import csv
import io
from collections.abc import Callable, Sequence
from dataclasses import dataclass, fields, is_dataclass

from PySide6.QtCore import QAbstractTableModel, QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QGuiApplication, QKeySequence, QValidator
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QScrollArea, QSizePolicy, QSplitter, QStackedWidget, QStyledItemDelegate, QTableView,
                               QToolButton, QToolTip, QVBoxLayout, QWidget)

from .. import output_provenance
from ..schema.budgets import (MASS_COLUMNS, BudgetBusConfig, BudgetEquipmentConfig, BudgetModeConfig,
                              BudgetPowerModeConfig, BudgetsConfig, PowerMarginConfig, SourcedValue, mass_policy_of,
                              powered)
from .badges import DANGER, SUCCESS, WARNING, set_badge
from .data_table import DataTable, Row, fit_widths, text_elided
from .feedback import show_toast
from .theme import SPACE, icon, numeric_font, set_role
from .value_sheet import NoteList, ValueSheet
from .widgets import ComboBox, EmptyState, TabWidget, connect_while_alive, exact_number_text, set_table_look

PLACEHOLDER_TEXT = "TBD"  # what a placeholder reads in a table cell
UNKNOWN_TEXT = "unknown"  # a result a placeholder or a missing number leaves unknown
NOT_LISTED_TEXT = "not listed"  # an item a system mode gives no power mode
_NEW_SOURCE = "TBD"  # the source of a value made by Add: a placeholder until the user gives one
_SIZED_ROWS = 25  # [-] rows a grid's column widths are measured from (all of them took 100 ms at 180 items)
_SIZED_COLUMNS = 30  # [-] more columns (a system mode per item) keep their width, but the first two


# -- an editable grid (decision B-12) ----------------------------------------------------------------------------

@dataclass
class Column:
    """One column of a :class:`GridModel`. ``get(row)`` gives the value
    (text, a number or None, or a bool for a check box); ``put(row, value)``
    stores an edit (None: read-only); ``kind`` is "text", "number",
    "choice" or "check"; ``choices(row)`` the values a choice offers;
    ``placeholder(row)`` says the cell is a placeholder (a caution icon,
    and ``placeholder_text`` when it has no value); ``empty`` is shown for
    an empty value; ``editable(row)`` can make single rows read-only."""

    header: str
    get: Callable
    put: Callable | None = None
    kind: str = "text"
    choices: Callable | None = None
    placeholder: Callable | None = None
    placeholder_text: str = PLACEHOLDER_TEXT
    empty: str = ""
    tip: str = ""
    editable: Callable | None = None
    display: Callable | None = None  # row -> the text shown, when it differs from the value edited
    heading: str = ""  # the heading shown, when it differs from ``header`` (two lines: "Average\n[W]", UI audit B12)

    @property
    def numeric(self) -> bool:
        return self.kind == "number"


def number_text(value) -> str:
    """A number the user typed, as typed back (``:g`` would drop digits)."""
    return "" if value is None else exact_number_text(value)


class GridModel(QAbstractTableModel):
    """Rows of objects under :class:`Column` specs. :attr:`edited` follows
    every edit that changed a value."""

    edited = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.columns: list[Column] = []
        self.rows: list = []
        self._numeric_font = numeric_font()

    def set_rows(self, rows: Sequence, columns: Sequence[Column] | None = None) -> None:
        self.beginResetModel()
        self.rows = list(rows)
        if columns is not None:
            self.columns = list(columns)
        self.endResetModel()

    def rowCount(self, parent=None) -> int:  # noqa: N802 -- Qt API name
        return 0 if parent is not None and parent.isValid() else len(self.rows)

    def columnCount(self, parent=None) -> int:  # noqa: N802 -- Qt API name
        return 0 if parent is not None and parent.isValid() else len(self.columns)

    def column(self, index: int) -> Column:
        return self.columns[index]

    def _placeholder(self, column: Column, row) -> bool:
        return column.placeholder is not None and bool(column.placeholder(row))

    def text(self, row_index: int, column_index: int) -> str:
        """What the cell shows (a check box: "yes" or "no")."""
        column, row = self.columns[column_index], self.rows[row_index]
        if column.display is not None:
            return column.display(row)
        value = column.get(row)
        if column.kind == "check":
            return "yes" if value else "no"
        if value is None or value == "":
            return column.placeholder_text if self._placeholder(column, row) else column.empty
        return number_text(value) if column.numeric else str(value)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        column, row = self.columns[index.column()], self.rows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return None if column.kind == "check" else self.text(index.row(), index.column())
        if role == Qt.ItemDataRole.EditRole:
            value = column.get(row)
            return number_text(value) if column.numeric else ("" if value is None else value)
        if role == Qt.ItemDataRole.CheckStateRole and column.kind == "check":
            return Qt.CheckState.Checked if column.get(row) else Qt.CheckState.Unchecked
        if role == Qt.ItemDataRole.DecorationRole and self._placeholder(column, row):
            return icon("triangle-alert", "status.caution")  # a status: an icon and its text, never colour alone
        if role == Qt.ItemDataRole.ToolTipRole:
            if self._placeholder(column, row):
                return (f"{column.header}: {column.placeholder_text}. Every result that needs it is unknown, never "
                        "zero. Give the number and its source.")
            return column.tip or None
        if role == Qt.ItemDataRole.AccessibleTextRole:
            text = self.text(index.row(), index.column())
            return f"{text}, placeholder" if self._placeholder(column, row) and text != column.placeholder_text \
                else text
        if column.numeric:
            if role == Qt.ItemDataRole.TextAlignmentRole:
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if role == Qt.ItemDataRole.FontRole:
                return self._numeric_font
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802 -- Qt API name
        if orientation != Qt.Orientation.Horizontal or not 0 <= section < len(self.columns):
            return None
        column = self.columns[section]
        if role == Qt.ItemDataRole.DisplayRole:
            return column.heading or column.header
        if role == Qt.ItemDataRole.ToolTipRole:
            return column.tip or None
        if role == Qt.ItemDataRole.TextAlignmentRole and column.numeric:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        column, row = self.columns[index.column()], self.rows[index.row()]
        if column.put is None or (column.editable is not None and not column.editable(row)):
            return flags
        if column.kind == "check":
            return flags | Qt.ItemFlag.ItemIsUserCheckable
        return flags | Qt.ItemFlag.ItemIsEditable

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole) -> bool:  # noqa: N802 -- Qt API name
        if not index.isValid() or not self.flags(index) & (Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsUserCheckable):
            return False
        column, row = self.columns[index.column()], self.rows[index.row()]
        if column.kind == "check":
            if role != Qt.ItemDataRole.CheckStateRole:
                return False
            new = Qt.CheckState(value) == Qt.CheckState.Checked if not isinstance(value, bool) else value
        elif role != Qt.ItemDataRole.EditRole:
            return False
        elif column.numeric:
            new = parse_number(value)
            if new is _INVALID:
                return False
        else:
            new = "" if value is None else str(value).strip()
        if new == column.get(row):
            return False
        column.put(row, new)
        self.dataChanged.emit(self.index(index.row(), 0), self.index(index.row(), len(self.columns) - 1))
        self.edited.emit()
        return True


_INVALID = object()


def parse_number(value):
    """A cell's number: None for an empty cell, :data:`_INVALID` for text
    that is not a finite number."""
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return _INVALID
    return number if number == number and abs(number) != float("inf") else _INVALID


class _NumberValidator(QValidator):
    """A finite number, or nothing (an empty cell clears the value)."""

    def validate(self, text, pos):
        stripped = text.strip()
        if not stripped or parse_number(stripped) is not _INVALID:
            return QValidator.State.Acceptable, text, pos
        if stripped in ("-", "+", ".", "-.", "+.") or stripped[-1:] in ("e", "E", "-", "+"):
            return QValidator.State.Intermediate, text, pos
        return QValidator.State.Invalid, text, pos


class _Delegate(QStyledItemDelegate):
    """A combo box for a choice, a line edit (numbers only for a number)
    for the rest. On hover, a cell's tooltip, or its whole text when its
    column elides it (as a DataTable's, UI audit B9)."""

    def helpEvent(self, event, view, option, index) -> bool:  # noqa: N802 -- Qt API name
        if event.type() == QEvent.Type.ToolTip and index.isValid() and text_elided(view, index):
            tip = index.data(Qt.ItemDataRole.ToolTipRole)
            text = str(index.data(Qt.ItemDataRole.DisplayRole))
            QToolTip.showText(event.globalPos(), f"{text}\n{tip}" if tip else text, view)
            return True
        return super().helpEvent(event, view, option, index)

    def createEditor(self, parent, option, index):  # noqa: N802 -- Qt API name
        model = index.model()
        column, row = model.column(index.column()), model.rows[index.row()]
        if column.kind == "choice":
            box = ComboBox(parent)
            for choice in column.choices(row):
                box.addItem(choice or column.empty or "(none)", choice)
            box.setAccessibleName(column.header)
            return box
        editor = QLineEdit(parent)
        editor.setAccessibleName(column.header)
        if column.numeric:
            editor.setValidator(_NumberValidator(editor))
        return editor

    def setEditorData(self, editor, index):  # noqa: N802 -- Qt API name
        value = index.data(Qt.ItemDataRole.EditRole)
        if isinstance(editor, QComboBox):
            editor.setCurrentIndex(max(editor.findData(value), 0))
        else:
            editor.setText("" if value is None else str(value))

    def setModelData(self, editor, model, index):  # noqa: N802 -- Qt API name
        value = editor.currentData() if isinstance(editor, QComboBox) else editor.text()
        model.setData(index, value, Qt.ItemDataRole.EditRole)


class _GridView(QTableView):
    """The grid: Ctrl+C copies the selected rows (all when none is) as TSV.
    ``resized``: its width changed, so its columns fit again."""

    resized = Signal()

    def resizeEvent(self, event):  # noqa: N802 -- Qt API name
        super().resizeEvent(event)
        if event.size().width() != event.oldSize().width():
            self.resized.emit()

    def keyPressEvent(self, event):  # noqa: N802 -- Qt API name
        if event.matches(QKeySequence.StandardKey.Copy):
            QGuiApplication.clipboard().setText(grid_tsv(self.model(), self.selected_rows()))
            return
        super().keyPressEvent(event)

    def selected_rows(self) -> list[int]:
        return sorted({index.row() for index in self.selectionModel().selectedIndexes()})


def grid_tsv(model: GridModel, rows: Sequence[int] = ()) -> str:
    rows = list(rows) or range(model.rowCount())
    lines = ["\t".join(column.header for column in model.columns)]
    lines += ["\t".join(model.text(row, c) for c in range(len(model.columns))) for row in rows]
    return "\n".join(lines)


def _icon_button(action: QAction) -> QToolButton:
    """A small button for ``action``: its icon, its text as the tooltip and
    the accessible name (an icon-only button is never unnamed)."""
    button = QToolButton()
    button.setDefaultAction(action)
    button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
    button.setAccessibleName(action.text().replace("&", ""))
    button.setAutoRaise(True)
    return button


def _text_button(action: QAction) -> QToolButton:
    button = QToolButton()
    button.setDefaultAction(action)
    button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    button.setAccessibleName(action.text().replace("&", ""))
    return button


class EditableTable(QWidget):
    """A titled :class:`GridModel` grid with its buttons, and an
    :class:`EmptyState` instead of an empty grid."""

    def __init__(self, title: str, empty_title: str, empty_text: str = "", empty_action: QAction | None = None,
                 actions: Sequence[QAction] = (), icon_only: bool = True, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE["xs"])
        top = QHBoxLayout()
        top.setSpacing(SPACE["xs"])
        self.top_layout = top
        self.title_label = set_role(QLabel(title), role="heading")
        top.addWidget(self.title_label, 1)
        self.buttons = []
        for action in actions:
            button = _icon_button(action) if icon_only else _text_button(action)
            top.addWidget(button)
            self.buttons.append(button)
        layout.addLayout(top)
        self.stack = QStackedWidget()
        self.empty = EmptyState(empty_title, empty_text, empty_action.text().replace("&", "") if empty_action
                                else None)
        if empty_action is not None:
            self.empty.button.clicked.connect(empty_action.trigger)
        self.stack.addWidget(self.empty)
        self.model = GridModel(self)
        self.view = _GridView()
        self.view.setModel(self.model)
        self.view.setItemDelegate(_Delegate(self.view))
        self.view.setAccessibleName(title)
        self.view.verticalHeader().setVisible(False)
        set_table_look(self.view)  # no grid lines, headings left (a number's right), rows at ROW_HEIGHT (B9)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked
                                  | QAbstractItemView.EditTrigger.EditKeyPressed
                                  | QAbstractItemView.EditTrigger.AnyKeyPressed)
        self.view.setTabKeyNavigation(False)  # Tab leaves the grid; the arrows move in it (as DataTable, M9)
        self.view.setWordWrap(False)
        self.view.horizontalHeader().setStretchLastSection(True)
        self.view.horizontalHeader().setResizeContentsPrecision(_SIZED_ROWS)  # a long list: its first rows
        self.view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        # The columns fit the grid's width (UI audit B12, as a DataTable's set_fit_width): each its content's
        # width when they all fit, else the widest elided (whole on hover), never below its heading.
        self._natural: list[int] = []  # [px] each column's width for its heading and content
        self._floors: list[int] = []  # [px] each column's heading width, as the style draws it
        self._fit_timer = QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.setInterval(0)
        self._fit_timer.timeout.connect(self.fit_columns)
        self.view.resized.connect(self._fit_timer.start)
        self.view.verticalScrollBar().rangeChanged.connect(lambda *_range: self._fit_timer.start())
        self.stack.addWidget(self.view)
        layout.addWidget(self.stack, 1)

    def set_rows(self, rows: Sequence, columns: Sequence[Column] | None = None) -> None:
        current = self.current_row()
        self.model.set_rows(rows, columns)
        if len(self.model.columns) <= _SIZED_COLUMNS:
            self.view.resizeColumnsToContents()
        else:
            for column in range(2):
                self.view.resizeColumnToContents(column)
        header = self.view.horizontalHeader()
        self._natural = [self.view.columnWidth(column) for column in range(self.model.columnCount())]
        self._floors = [min(header.sectionSizeHint(column), natural) for column, natural in enumerate(self._natural)]
        self.fit_columns()
        self.stack.setCurrentWidget(self.view if self.model.rows else self.empty)
        if current is not None and self.model.rows:
            self.select_row(min(current, len(self.model.rows) - 1))

    def fit_columns(self) -> None:
        """The columns fitted to the grid's width (:func:`data_table.fit_widths`;
        the last one takes what is left)."""
        room = self.view.viewport().width()
        if not self._natural or room <= 0:
            return
        widths = fit_widths(self._natural, self._floors, room)
        # Every width set here, the last taking the rest: a stretched last section never went below
        # Qt's default section size (100 px), so a narrow grid scrolled sideways by its last column.
        self.view.horizontalHeader().setStretchLastSection(False)
        for column, width in enumerate(widths):
            self.view.setColumnWidth(column, width)

    def needed_width(self) -> int:
        """[px] the least width the grid shows every heading whole at, and
        the width its headings and content want: (floor, natural)."""
        frame = 2 * self.view.frameWidth()
        return sum(self._floors) + frame, sum(self._natural) + frame

    def current_row(self) -> int | None:
        index = self.view.currentIndex()
        return index.row() if index.isValid() else None

    def select_row(self, row: int, column: int = 0) -> None:
        if 0 <= row < self.model.rowCount():
            self.view.setCurrentIndex(self.model.index(row, column))

    def cell(self, row: int, column: int) -> str:
        return self.model.text(row, column)

    def headers(self) -> list[str]:
        return [column.header for column in self.model.columns]

    def edit_cell(self, row: int, column: int, value) -> bool:
        """``value`` into a cell, as typing it would (tests, scripts)."""
        index = self.model.index(row, column)
        role = Qt.ItemDataRole.CheckStateRole if self.model.column(column).kind == "check" else \
            Qt.ItemDataRole.EditRole
        if role == Qt.ItemDataRole.CheckStateRole and isinstance(value, bool):
            value = Qt.CheckState.Checked if value else Qt.CheckState.Unchecked
        return self.model.setData(index, value, role)


# -- sourced values -------------------------------------------------------------------------------------------------

def clone(value):
    """A deep copy of a section (its dataclasses, lists, dicts and plain
    values), several times faster than ``copy.deepcopy``: the page copies
    the section at each edit (50 ms at 180 items with ``deepcopy``)."""
    if is_dataclass(value) and not isinstance(value, type):
        return type(value)(**{f.name: clone(getattr(value, f.name)) for f in fields(value) if f.init})
    if isinstance(value, list):
        return [clone(item) for item in value]
    if isinstance(value, dict):
        return {key: clone(item) for key, item in value.items()}
    return value


def with_value(value: SourcedValue | None, number: float | None) -> SourcedValue | None:
    """``value`` with another number (None when nothing is left: no number
    and no source)."""
    source = value.source if value is not None else _NEW_SOURCE
    if number is None and not source:
        return None
    return SourcedValue(number, source)


def with_source(value: SourcedValue | None, source: str) -> SourcedValue | None:
    """``value`` with another source (None when nothing is left)."""
    number = value.value if value is not None else None
    if number is None and not source:
        return None
    return SourcedValue(number, source)


def is_placeholder(value: SourcedValue | None) -> bool:
    return value is not None and value.placeholder


def unique_name(stem: str, names) -> str:
    names = set(names)
    number = 1
    while f"{stem} {number}" in names:
        number += 1
    return f"{stem} {number}"


def new_section() -> BudgetsConfig:
    """The section Add budgets section makes: one bus, "main", and the
    numbers of the power chain as placeholders. It guesses no number."""
    return BudgetsConfig(buses=[BudgetBusConfig("main", SourcedValue(None, _NEW_SOURCE))],
                         distribution_loss=SourcedValue(None, _NEW_SOURCE),
                         system_power_margin_percent=SourcedValue(None, _NEW_SOURCE))


@dataclass
class _Setting:
    """A row of the power settings table: a number of the section."""

    label: str
    unit: str
    get: Callable  # () -> SourcedValue | None
    put: Callable  # (SourcedValue | None) -> None
    bus: BudgetBusConfig | None = None  # the bus of an efficiency row (its name is editable)
    tip: str = ""


def _csv_text(rows: Sequence[Sequence], scenario=None) -> str:
    """CSV with the scenario's provenance as the last lines (as Budgets ›
    Propellant's Copy as CSV)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    for row in rows:
        writer.writerow(["" if value is None else value for value in row])
    if scenario is not None:
        for line in output_provenance.scenario_lines(scenario):
            writer.writerow([line])
    return buffer.getvalue().rstrip("\n")


# -- the Equipment page ---------------------------------------------------------------------------------------------

class EquipmentPage(QWidget):
    """The ``budgets`` section of one spacecraft as editable tables (module
    docstring). :attr:`edited` carries a copy of the section after each
    edit; :attr:`section_added` asks for a new section."""

    edited = Signal(object)  # schema.budgets.BudgetsConfig (a copy)
    section_added = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.spacecraft_name = ""
        self.section: BudgetsConfig | None = None  # the page's copy of the section shown
        self._categories: tuple = ()
        self._scenario = None
        # Two commands of the window's registry (Budgets › Add/Remove Equipment Item; their shortcuts are
        # the window's). Remove acts only while the page is shown: from elsewhere the window shows it.
        self.add_item_action = self._action("Add Equipment Item", "file-plus", self.add_item, "Ctrl+Shift+N")
        self.remove_item_action = self._action("Remove Equipment Item", "circle-minus", self.remove_item, "Ctrl+Del")
        self.add_mode_action = self._action("Add Power Mode", "file-plus", self.add_power_mode)
        self.remove_mode_action = self._action("Remove Power Mode", "circle-minus", self.remove_power_mode)
        self.add_system_mode_action = self._action("Add System Mode", "file-plus", self.add_system_mode)
        self.remove_system_mode_action = self._action("Remove System Mode", "circle-minus", self.remove_system_mode)
        self.add_bus_action = self._action("Add Bus", "file-plus", self.add_bus)
        self.remove_bus_action = self._action("Remove Bus", "circle-minus", self.remove_bus)
        self.copy_action: QAction | None = None  # the area's Copy as CSV (BudgetsViews), shown here as a button

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE["lg"], SPACE["md"], SPACE["lg"], SPACE["md"])
        layout.setSpacing(SPACE["sm"])
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)
        self.empty_state = EmptyState("No spacecraft")  # its button secondary: Run is the one accent (UI-03)
        self.empty_state.button.clicked.connect(self.section_added)
        self.stack.addWidget(self.empty_state)

        self.editor = QWidget()
        editor_layout = QVBoxLayout(self.editor)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(SPACE["sm"])
        self.items_table = EditableTable(
            "Equipment list", "No equipment item yet",
            "Add an item for each unit: its mass, maturity, bus and power modes.", self.add_item_action,
            (self.add_item_action, self.remove_item_action), icon_only=False)
        self.items_table.empty.button.setText("Add Item")  # secondary: Run is the one accent (UI-03)
        self.items_table.model.edited.connect(self._on_items_edited)
        self.items_table.view.selectionModel().currentRowChanged.connect(self._on_item_picked)
        self.modes_table = EditableTable(
            "Power modes", "No power mode", "An item without a power mode is in the mass budget only.",
            self.add_mode_action, (self.add_mode_action, self.remove_mode_action))
        self.modes_table.model.edited.connect(self._on_modes_edited)
        self.system_modes_table = EditableTable(
            "System modes", "No system mode yet", "A system mode gives each item one of its power modes.",
            self.add_system_mode_action, (self.add_system_mode_action, self.remove_system_mode_action))
        self.system_modes_table.model.edited.connect(self._commit)
        self.settings_table = EditableTable("Power settings", "No setting", "",
                                            None, (self.add_bus_action, self.remove_bus_action))
        self.settings_table.model.edited.connect(self._on_settings_edited)
        lower = QSplitter(Qt.Orientation.Horizontal)
        lower.setChildrenCollapsible(False)
        for table in (self.modes_table, self.system_modes_table, self.settings_table):
            lower.addWidget(table)
        # The three grids share the row by what they need (UI audit B12): each its headings and
        # content when they fit, else each its headings and a share of the rest, until the user
        # drags a divider. Equal thirds made the power modes and settings scroll sideways at 1280 px.
        self.lower = lower
        self._lower_by_user = False
        lower.splitterMoved.connect(self._on_lower_moved)
        lower.installEventFilter(self)
        self._lower_timer = QTimer(self)
        self._lower_timer.setSingleShot(True)
        self._lower_timer.setInterval(0)
        self._lower_timer.timeout.connect(self.fit_lower)
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(self.items_table)
        self.splitter.addWidget(lower)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        editor_layout.addWidget(self.splitter, 1)
        self.notes = set_role(QLabel("The run does not use the budgets yet: it uses the spacecraft's dry mass and "
                                     "its power budget's bus load."), role="caption")
        self.notes.setWordWrap(True)
        editor_layout.addWidget(self.notes)
        self.stack.addWidget(self.editor)
        self._show_state()

    def _action(self, text: str, icon_name: str, handler, keys: str | None = None) -> QAction:
        action = QAction(icon(icon_name, "text.secondary"), text, self)
        action.setToolTip(f"{text} ({keys})" if keys else text)
        if keys:
            action.setShortcut(QKeySequence(keys))
        action.triggered.connect(handler)
        return action

    def set_copy_action(self, action: QAction) -> None:
        """The area's Copy as CSV, as a button beside the item buttons."""
        self.copy_action = action
        button = _text_button(action)
        self.items_table.top_layout.addWidget(button)
        self.items_table.buttons.append(button)

    # -- what is shown --------------------------------------------------------------------------------------------
    def set_spacecraft(self, sc, scenario=None) -> None:
        """Show ``sc``'s section (None: no spacecraft). The page's own copy
        stays when it equals the spacecraft's (the edit just made), so the
        grids keep their place."""
        self._scenario = scenario
        name = sc.name if sc is not None else ""
        section = sc.budgets if sc is not None else None
        categories = tuple(mass_policy_of(sc).categories) if sc is not None else ()
        if (name, section, categories) == (self.spacecraft_name, self.section, self._categories):
            return
        picked = self._picked_item_name()
        self.spacecraft_name, self._categories = name, categories
        self.section = clone(section)
        self._show_state()
        if self.section is not None:
            self._reload(picked)

    def _show_state(self) -> None:
        if not self.spacecraft_name:
            self.empty_state.set_text("No spacecraft", "The scenario has no spacecraft. Add one in Scenario › "
                                                       "Spacecraft, then give it an equipment list here.")
            self.stack.setCurrentWidget(self.empty_state)
        elif self.section is None:
            self.empty_state.set_text(
                "No equipment list", f"{self.spacecraft_name} has no budgets section: no equipment list, system "
                "modes or power budget. The run does not use it.", "Add Budgets Section")
            self.stack.setCurrentWidget(self.empty_state)
        else:
            self.stack.setCurrentWidget(self.editor)

    def _reload(self, picked: str | None = None) -> None:
        """Every table from the page's section."""
        section = self.section
        self.items_table.set_rows(section.equipment, self._item_columns())
        self.items_table.title_label.setText(f"Equipment list ({len(section.equipment)})")
        names = [item.name for item in section.equipment]
        if picked in names:
            self.items_table.select_row(names.index(picked))
        elif names and self.items_table.current_row() is None:
            self.items_table.select_row(0)
        self._reload_modes()
        self._reload_system_modes()
        self._reload_settings()
        self._lower_timer.start()  # the grids' needs changed: their widths follow

    def _picked_item_name(self) -> str | None:
        row = self.items_table.current_row()
        if self.section is None or row is None or row >= len(self.section.equipment):
            return None
        return self.section.equipment[row].name

    def picked_item(self) -> BudgetEquipmentConfig | None:
        name = self._picked_item_name()
        return self.section.item(name) if name is not None else None

    def _reload_modes(self) -> None:
        item = self.picked_item()
        self.modes_table.set_rows(item.power_modes if item is not None else [], self._mode_columns())
        self.modes_table.title_label.setText(f"Power modes of {item.name}" if item is not None else "Power modes")
        self.modes_table.empty.set_text(
            "No power mode" if item is not None else "No item picked",
            "An item without a power mode is in the mass budget only." if item is not None
            else "Pick an item of the equipment list.", "Add Power Mode" if item is not None else None)
        for action in (self.add_mode_action, self.remove_mode_action):
            action.setEnabled(item is not None)

    def _reload_system_modes(self) -> None:
        self.system_modes_table.set_rows(self.section.modes, self._system_mode_columns())

    def _reload_settings(self) -> None:
        self.settings_table.set_rows(self._settings_rows(), self._setting_columns())

    def _on_item_picked(self, *_args) -> None:
        if self.section is not None:
            self._reload_modes()

    # -- the lower row's widths ---------------------------------------------------------------------------------
    def _on_lower_moved(self, *_args) -> None:
        self._lower_by_user = True  # the user's widths stay

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 -- Qt API name
        if watched is getattr(self, "lower", None) and event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            self._lower_timer.start()
        return super().eventFilter(watched, event)

    def fit_lower(self) -> None:
        """The power modes, system modes and power settings side by side, each
        as wide as it needs (:meth:`EditableTable.needed_width`): all their
        content when it fits, else every heading whole and the rest shared
        by what each still wants, else by their headings' widths."""
        lower = self.lower
        tables = [lower.widget(index) for index in range(lower.count())]
        room = lower.width() - lower.handleWidth() * (len(tables) - 1)
        if self._lower_by_user or room <= 0:
            return
        floors, naturals = zip(*(table.needed_width() for table in tables))
        if sum(naturals) <= room:
            base, weights = naturals, naturals
        elif sum(floors) <= room:
            base, weights = floors, [natural - floor for floor, natural in zip(floors, naturals)]
        else:
            base, weights = [0] * len(tables), floors
        spare, total = room - sum(base), sum(weights) or 1
        sizes = [int(width + spare * weight / total) for width, weight in zip(base, weights)]
        sizes[-1] += room - sum(sizes)
        lower.setSizes(sizes)

    # -- the columns ----------------------------------------------------------------------------------------------
    def _item_columns(self) -> list[Column]:
        def mass(item):
            return item.mass_kg.value if item.mass_kg is not None else None

        def put_mass(item, number):
            item.mass_kg = with_value(item.mass_kg, number) or (None if item.mass_in_model else
                                                                  SourcedValue(None, ""))

        def put_mass_source(item, source):
            item.mass_kg = with_source(item.mass_kg, source) or (None if item.mass_in_model else
                                                                   SourcedValue(None, ""))

        def mass_placeholder(item):
            return not item.mass_in_model and (item.mass_kg is None or item.mass_kg.placeholder)

        return [
            Column("Name", lambda i: i.name, self._rename_item, tip="Unique in the list"),
            Column("Subsystem", lambda i: i.subsystem, lambda i, v: setattr(i, "subsystem", v),
                   tip="The functional subsystem (AOCS, DHS, EPS...): the power budget groups by it"),
            Column("Mass column", lambda i: i.mass_column, lambda i, v: setattr(i, "mass_column", v), "choice",
                   lambda _i: list(MASS_COLUMNS), empty="(largest)", heading="Mass\ncolumn",
                   tip="The AIAA S-120 column of the mass growth allowance; empty: the largest of the row"),
            Column("Bus", lambda i: i.bus, lambda i, v: setattr(i, "bus", v), "choice",
                   lambda _i: [""] + [bus.name for bus in self.section.buses],
                   tip="The bus the item draws from (needed when it has power modes)"),
            Column("Maturity", lambda i: i.maturity, lambda i, v: setattr(i, "maturity", v), "choice",
                   lambda _i: [""] + list(self._categories),
                   tip="The maturity category: the mass growth allowance and the power margin"),
            Column("Mass [kg]", mass, put_mass, "number", placeholder=mass_placeholder, heading="Mass\n[kg]",
                   empty="", tip="The basic mass; empty with Mass in model ticked: the 3D model holds it"),
            Column("Mass source", lambda i: i.mass_kg.source if i.mass_kg is not None else "", put_mass_source,
                   heading="Mass\nsource", tip='Where the mass comes from; "TBD" marks a placeholder'),
            Column("Mass in model", lambda i: i.mass_in_model, self._put_mass_in_model, "check",
                   heading="Mass in\nmodel", tip="The 3D model already holds this mass: the mass budget adds no line for it"),
        ]

    def _put_mass_in_model(self, item, on: bool) -> None:
        item.mass_in_model = bool(on)
        if not on and item.mass_kg is None:
            item.mass_kg = SourcedValue(None, _NEW_SOURCE)

    def _rename_item(self, item, name: str) -> None:
        old = item.name
        item.name = name
        for mode in self.section.modes:
            if old in mode.units:
                mode.units = {(name if key == old else key): value for key, value in mode.units.items()}
        for contributor in self._pointing_contributors():
            if contributor.equipment == old:
                contributor.equipment = name  # the pointing contributor keeps its item

    def _pointing_contributors(self) -> list:
        pointing = self.section.pointing if self.section is not None else None
        return pointing.contributors if pointing is not None else []

    def _pointing_requirements(self) -> list:
        pointing = self.section.pointing if self.section is not None else None
        return pointing.requirements if pointing is not None else []

    def _mode_columns(self) -> list[Column]:
        def put_average(mode, number):
            mode.average_w = with_value(mode.average_w, number) or SourcedValue(None, "")

        def put_average_source(mode, source):
            mode.average_w = with_source(mode.average_w, source) or SourcedValue(None, "")

        def put_duty(mode, number):
            mode.duty_cycle = 1.0 if number is None else number

        return [
            Column("Name", lambda m: m.name, self._rename_power_mode, tip="Unique for the item"),
            Column("Average [W]", lambda m: m.average_w.value, put_average, "number",
                   placeholder=lambda m: m.average_w.placeholder, tip="While in the mode and switched on",
                   heading="Average\n[W]"),
            Column("Average source", lambda m: m.average_w.source, put_average_source, heading="Average\nsource",
                   tip="Where the average power comes from"),
            Column("Peak [W]", lambda m: m.peak_w.value if m.peak_w is not None else None,
                   lambda m, v: setattr(m, "peak_w", with_value(m.peak_w, v)), "number",
                   placeholder=lambda m: is_placeholder(m.peak_w), empty="= average",
                   tip="Empty: the average; at least the average", heading="Peak\n[W]"),
            Column("Peak source", lambda m: m.peak_w.source if m.peak_w is not None else "",
                   lambda m, v: setattr(m, "peak_w", with_source(m.peak_w, v)), heading="Peak\nsource",
                   tip="Where the peak power comes from"),
            Column("Duty cycle [-]", lambda m: m.duty_cycle, put_duty, "number", heading="Duty\ncycle [-]",
                   tip="The share of the time the item is switched on, 0 to 1 (empty: 1)"),
        ]

    def _rename_power_mode(self, mode, name: str) -> None:
        item = self.picked_item()
        old = mode.name
        mode.name = name
        if item is None:
            return
        for system_mode in self.section.modes:
            if system_mode.units.get(item.name) == old:
                system_mode.units[item.name] = name

    def _system_mode_columns(self) -> list[Column]:
        def put_duty(mode, number):
            mode.duty_cycle = number

        columns = [
            Column("Name", lambda m: m.name, self._rename_system_mode, tip="Unique among the system modes"),
            Column("Duty cycle [-]", lambda m: m.duty_cycle, put_duty, "number", heading="Duty\ncycle [-]",
                   tip="The share of the time in this mode, 0 to 1; empty: not stated"),
        ]
        for item in self.section.equipment:
            if not powered(item):
                continue
            columns.append(Column(
                item.name, lambda m, name=item.name: m.units.get(name, ""),
                lambda m, v, name=item.name: self._put_unit(m, name, v), "choice",
                lambda _m, item=item: [""] + [mode.name for mode in item.power_modes],
                placeholder=lambda m, name=item.name: name not in m.units, placeholder_text=NOT_LISTED_TEXT,
                tip=f"The power mode of {item.name} in this system mode; not listed: its power is unknown"))
        return columns

    @staticmethod
    def _put_unit(mode, item: str, power_mode: str) -> None:
        units = dict(mode.units)
        if power_mode:
            units[item] = power_mode
        else:
            units.pop(item, None)
        mode.units = units

    def _rename_system_mode(self, mode, name: str) -> None:
        old = mode.name
        mode.name = name
        for requirement in self._pointing_requirements():  # a pointing requirement keeps its mode
            requirement.modes = [name if entry == old else entry for entry in requirement.modes]

    def _settings_rows(self) -> list[_Setting]:
        section = self.section
        rows = [
            _Setting("Distribution loss", "-", lambda: section.distribution_loss,
                     lambda v: setattr(section, "distribution_loss", v),
                     tip="The share lost between the source and the loads, 0 to below 1"),
            _Setting("System power margin", "%", lambda: section.system_power_margin_percent,
                     lambda v: setattr(section, "system_power_margin_percent", v),
                     tip="The margin on the sum of the margined loads"),
        ]
        for bus in section.buses:
            rows.append(_Setting(bus.name, "-", lambda bus=bus: bus.converter_efficiency,
                                 lambda v, bus=bus: setattr(bus, "converter_efficiency", v), bus=bus,
                                 tip="The bus's converter efficiency, above 0 to 1. The name is editable."))
        for category in self._categories:
            rows.append(_Setting(f"Power margin, {category}", "%",
                                 lambda category=category: _margin(section, category),
                                 lambda v, category=category: self._put_margin(category, v),
                                 tip=f"The power margin of the items of maturity {category}"))
        return rows

    def _put_margin(self, category: str, value: SourcedValue | None) -> None:
        section = self.section
        margins = [m for m in section.power_margins if m.maturity != category]
        if value is not None:
            margins.append(PowerMarginConfig(category, value))
            order = {name: index for index, name in enumerate(self._categories)}
            margins.sort(key=lambda m: order.get(m.maturity, len(order)))
        section.power_margins = margins

    def _setting_columns(self) -> list[Column]:
        def value(setting):
            sourced = setting.get()
            return sourced.value if sourced is not None else None

        return [
            Column("Setting", lambda s: s.bus.name if s.bus is not None else s.label, self._rename_bus,
                   editable=lambda s: s.bus is not None, tip="The name of a bus row is editable",
                   display=lambda s: f"Bus {s.bus.name}: efficiency" if s.bus is not None else s.label),
            Column("Value", value, lambda s, v: s.put(with_value(s.get(), v)), "number",
                   placeholder=lambda s: s.get() is None or s.get().placeholder,
                   display=lambda s: "not given" if s.get() is None else (
                       PLACEHOLDER_TEXT if s.get().value is None else number_text(s.get().value)),
                   tip="Empty: not given; the results that need it are unknown"),
            Column("Unit", lambda s: s.unit),
            Column("Source", lambda s: s.get().source if s.get() is not None else "",
                   lambda s, v: s.put(with_source(s.get(), v))),
        ]

    def _rename_bus(self, setting: _Setting, name: str) -> None:
        old = setting.bus.name
        setting.bus.name = name
        for item in self.section.equipment:
            if item.bus == old:
                item.bus = name

    # -- edits ------------------------------------------------------------------------------------------------------
    def _commit(self) -> None:
        """Hand a copy of the section to the window (the scenario)."""
        if self.section is not None:
            self.edited.emit(clone(self.section))

    def _on_items_edited(self) -> None:
        self._reload_modes()
        self._reload_system_modes()  # a renamed item, a bus or a power mode changes the system mode columns
        self._commit()

    def _on_modes_edited(self) -> None:
        self.system_modes_table.view.viewport().update()  # a renamed power mode: the system modes show it
        self._commit()

    def _on_settings_edited(self) -> None:
        self.items_table.view.viewport().update()  # a renamed bus: the items show it
        self._commit()

    def add_item(self) -> None:
        if self.section is None:
            return
        name = unique_name("item", [item.name for item in self.section.equipment])
        self.section.equipment.append(BudgetEquipmentConfig(name, mass_kg=SourcedValue(None, _NEW_SOURCE)))
        self._reload(name)
        self.items_table.select_row(len(self.section.equipment) - 1)
        self.items_table.view.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._commit()

    def shown(self) -> bool:
        """The page is the one shown (in its window, shown or not)."""
        return self.isVisibleTo(self.window())

    def remove_item(self) -> None:
        item = self.picked_item()
        if item is None or not self.shown():
            return
        row = self.section.equipment.index(item)
        del self.section.equipment[row]
        for mode in self.section.modes:
            mode.units = {key: value for key, value in mode.units.items() if key != item.name}
        for contributor in self._pointing_contributors():
            if contributor.equipment == item.name:
                contributor.equipment = ""
        self._reload()
        if self.section.equipment:
            self.items_table.select_row(min(row, len(self.section.equipment) - 1))
        self._commit()
        show_toast(self.window(), f"Removed {item.name}. Undo: Ctrl+Z.")

    def add_power_mode(self) -> None:
        item = self.picked_item()
        if item is None:
            return
        name = unique_name("mode", [mode.name for mode in item.power_modes])
        item.power_modes.append(BudgetPowerModeConfig(name, SourcedValue(None, _NEW_SOURCE)))
        if not item.bus and len(self.section.buses) == 1:
            item.bus = self.section.buses[0].name  # an item with power modes names a bus; one bus is the one
        self._reload(item.name)
        self.modes_table.select_row(len(item.power_modes) - 1)
        self._commit()

    def remove_power_mode(self) -> None:
        item = self.picked_item()
        row = self.modes_table.current_row()
        if item is None or row is None or row >= len(item.power_modes):
            return
        mode = item.power_modes.pop(row)
        for system_mode in self.section.modes:
            if system_mode.units.get(item.name) == mode.name:
                system_mode.units = {k: v for k, v in system_mode.units.items() if k != item.name}
        self._reload(item.name)
        self._commit()

    def add_system_mode(self) -> None:
        if self.section is None:
            return
        name = unique_name("system mode", [mode.name for mode in self.section.modes])
        self.section.modes.append(BudgetModeConfig(name))
        self._reload_system_modes()
        self.system_modes_table.select_row(len(self.section.modes) - 1)
        self._commit()

    def remove_system_mode(self) -> None:
        row = self.system_modes_table.current_row()
        if self.section is None or row is None or row >= len(self.section.modes):
            return
        removed = self.section.modes.pop(row).name
        for requirement in self._pointing_requirements():
            requirement.modes = [entry for entry in requirement.modes if entry != removed]
        self._reload_system_modes()
        self._commit()

    def add_bus(self) -> None:
        if self.section is None:
            return
        name = unique_name("bus", [bus.name for bus in self.section.buses])
        self.section.buses.append(BudgetBusConfig(name, SourcedValue(None, _NEW_SOURCE)))
        self._reload_settings()
        self._commit()

    def remove_bus(self) -> None:
        row = self.settings_table.current_row()
        rows = self.settings_table.model.rows
        if self.section is None or row is None or row >= len(rows) or rows[row].bus is None:
            return
        name = rows[row].bus.name
        self.section.buses = [bus for bus in self.section.buses if bus.name != name]
        for item in self.section.equipment:
            if item.bus == name:
                item.bus = ""
        self._reload(self._picked_item_name())
        self._commit()

    # -- copy -------------------------------------------------------------------------------------------------------
    def csv_text(self) -> str:
        if self.section is None:
            return ""
        rows = [("item", "subsystem", "mass_column", "bus", "maturity", "mass_kg", "mass_source", "mass_in_model",
                 "power_mode", "average_w", "average_source", "peak_w", "peak_source", "duty_cycle")]
        for item in self.section.equipment:
            mass = item.mass_kg
            base = (item.name, item.subsystem, item.mass_column, item.bus, item.maturity,
                    mass.value if mass is not None else None, mass.source if mass is not None else "",
                    "true" if item.mass_in_model else "false")
            if not item.power_modes:
                rows.append(base)
            for mode in item.power_modes:
                peak = mode.peak_w
                rows.append(base + (mode.name, mode.average_w.value, mode.average_w.source,
                                    peak.value if peak is not None else None, peak.source if peak is not None else "",
                                    mode.duty_cycle))
        return _csv_text(rows, self._scenario)


def _margin(section: BudgetsConfig, category: str) -> SourcedValue | None:
    margin = section.margin(category)
    return margin.percent if margin is not None else None


# -- the Power page -------------------------------------------------------------------------------------------------

def _w(value) -> str:
    return UNKNOWN_TEXT if value is None else f"{value:.2f}"


def _ratio(value) -> str:
    return UNKNOWN_TEXT if value is None else f"{value:g}"


def _status_badge() -> QLabel:
    badge = set_badge(QLabel(), SUCCESS)
    badge.setAccessibleName("Budget status")
    return badge


def _show_status(badge: QLabel, complete: bool, complete_text: str, unknown_text: str) -> None:
    badge.setText(complete_text if complete else unknown_text)
    set_badge(badge, SUCCESS if complete else WARNING)


def _fitted(table: DataTable) -> DataTable:
    """A table as tall as its rows (:func:`_fit`), no taller: the page
    scrolls, not each table. Its columns fit its width (UI audit B12): its
    headings are two lines, the name above the unit, so a table of the
    Power page fits at 1280 px with the Inspector open."""
    table.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    table.set_fit_width()
    return table


def _fit(table: DataTable) -> None:
    """``table`` as tall as its rows, or as its empty state."""
    if table.row_count():
        table.fit_rows()  # the view's height: its rows
        table.setFixedHeight(table.view.maximumHeight())
    else:
        table.setFixedHeight(table.empty.sizeHint().height())


def _scroll(widget: QWidget) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(widget)
    return scroll


# Two lines where a heading is long: the line breaks before the word with the unit, as units.label
# joins a unit to its word ("Load [W]" stays one line).
_FLOW_HEADERS = ("Load [W]", "With unit\nmargins [W]", "With system\nmargin [W]", "Source [W]",
                 "Source with\nmargins [W]")


def _flow_cells(flow) -> tuple:
    return (_w(flow.load_w), _w(flow.unit_margined_w), _w(flow.system_margined_w), _w(flow.source_w),
            _w(flow.source_margined_w))


class PowerPage(QWidget):
    """The static power budget of one spacecraft per system mode
    (``analyses.power_budget``): the totals of each mode, the duty-cycle
    average when the modes' duty cycles add up to 1, and for the system
    mode picked its items, subsystems and buses. "unknown": a placeholder
    or a missing number; the status and the notes say which."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.budget = None
        self._scenario = None
        self._shown: tuple = (object(), None)  # (spacecraft, invalid) last shown: the same is not computed again
        self.copy_action: QAction | None = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        outer.addWidget(self.stack)
        self.empty_state = EmptyState("No power budget")
        self.stack.addWidget(self.empty_state)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)  # the area insets the page (UI audit UI-16)
        layout.setSpacing(SPACE["md"])
        self.top_row = QHBoxLayout()
        self.top_row.setSpacing(SPACE["sm"])
        self.title_label = set_role(QLabel("Power budget"), role="section-title")
        self.top_row.addWidget(self.title_label)
        self.status_badge = _status_badge()
        self.top_row.addWidget(self.status_badge)
        self.top_row.addStretch(1)
        layout.addLayout(self.top_row)
        self.findings = NoteList("finding")
        layout.addWidget(self.findings)
        self.totals_table = _fitted(DataTable("No system mode: add one on the Equipment page."))
        self.totals_table.view.setAccessibleName("Power per system mode")
        layout.addWidget(set_role(QLabel("Per system mode"), role="heading"))
        layout.addWidget(self.totals_table)
        mode_row = QHBoxLayout()
        mode_row.setSpacing(SPACE["sm"])
        mode_label = QLabel("System mode")
        self.mode_combo = ComboBox()
        self.mode_combo.setAccessibleName("System mode")
        mode_label.setBuddy(self.mode_combo)
        self.mode_combo.currentIndexChanged.connect(self._show_mode)
        mode_row.addWidget(mode_label)
        mode_row.addWidget(self.mode_combo)
        mode_row.addStretch(1)
        layout.addLayout(mode_row)
        self.items_table = _fitted(DataTable("No item with power modes."))
        self.items_table.view.setAccessibleName("Items in the system mode")
        self.subsystems_table = _fitted(DataTable("No subsystem."))
        self.subsystems_table.view.setAccessibleName("Subsystems in the system mode")
        self.buses_table = _fitted(DataTable("No bus."))
        self.buses_table.view.setAccessibleName("Buses in the system mode")
        for title, table in (("Items", self.items_table), ("Per subsystem", self.subsystems_table),
                             ("Per bus", self.buses_table)):
            layout.addWidget(set_role(QLabel(title), role="heading"))
            layout.addWidget(table)
        self.inputs_sheet = ValueSheet("Computed with")
        layout.addWidget(self.inputs_sheet)
        layout.addStretch(1)
        self.stack.addWidget(_scroll(body))
        self.body = body

    def set_copy_action(self, action: QAction) -> None:
        self.copy_action = action
        self.top_row.addWidget(_text_button(action))

    def set_spacecraft(self, sc, scenario=None, invalid: bool = False) -> None:
        """Show ``sc``'s power budget; ``invalid``: the scenario does not
        validate, so no budget is computed (its problems are in the
        Problems panel). Nothing is computed again for the same
        spacecraft."""
        from ..analyses.power_budget import power_budget

        if (sc, invalid) == self._shown:
            self._scenario = scenario
            return
        self._shown = (copy.deepcopy(sc), invalid)  # a copy: the editor may change its own in place
        self._scenario = scenario
        self.budget = None
        if invalid:
            self.empty_state.set_text("The scenario has problems", "Fix them first: they are listed in the "
                                                                   "Problems panel (Ctrl+J).")
        elif sc is None:
            self.empty_state.set_text("No spacecraft", "The scenario has no spacecraft.")
        elif sc.budgets is None:
            self.empty_state.set_text("No power budget", f"{sc.name} has no budgets section. Add one on the "
                                                         "Equipment page.")
        else:
            self.budget = power_budget(sc)
        if self.budget is None:
            self.stack.setCurrentWidget(self.empty_state)
            return
        self.stack.setCurrentIndex(1)
        budget = self.budget
        self.title_label.setText(f"Power budget of {budget.spacecraft}")
        _show_status(self.status_badge, budget.complete, "Complete", "Unknown values")
        self.findings.set_notes([str(finding) for finding in budget.findings if finding.rule_id != "budget.mass_unknown"])
        rows = []
        for mode in budget.modes:
            rows.append(Row((mode.mode, _ratio(mode.duty_cycle) if mode.duty_cycle is not None else "",
                             *_flow_cells(mode.average), _w(mode.peak.load_w), _w(mode.peak.source_margined_w))))
        average = budget.duty_cycle_average()
        if average is not None and rows:
            rows.append(Row(("Duty-cycle average", "1", *_flow_cells(average), "", ""), bold=True))
        self.totals_table.set_table(("Mode", "Duty [-]", *_FLOW_HEADERS, "Peak [W]", "Peak source\nwith margins [W]"),
                                    rows, numeric=range(1, 9), stretch=0)
        _fit(self.totals_table)
        current = self.mode_combo.currentText()
        self.mode_combo.blockSignals(True)
        self.mode_combo.clear()
        self.mode_combo.addItems([mode.mode for mode in budget.modes])
        if current in [mode.mode for mode in budget.modes]:
            self.mode_combo.setCurrentText(current)
        self.mode_combo.blockSignals(False)
        self.mode_combo.setEnabled(bool(budget.modes))
        self._show_mode()
        inputs = []
        for entry in budget.inputs:
            if entry.state == "given":
                inputs.append((entry.name, f"{entry.value:g}", entry.unit))
            else:
                inputs.append((entry.name, PLACEHOLDER_TEXT if entry.state == "placeholder" else "not given",
                               entry.unit))
        self.inputs_sheet.set_rows(inputs)

    def _show_mode(self, *_args) -> None:
        budget = self.budget
        mode = next((m for m in budget.modes if m.mode == self.mode_combo.currentText()), None) if budget else None
        rows = mode.rows if mode is not None else ()
        # Twelve columns beside the Inspector at 1280 px: every number's heading is two or three lines, the
        # name above the unit (2.13.1; one-line headings made the table scroll sideways inside itself, and
        # two-line ones still did with the wider font metrics on Windows).
        self.items_table.set_table(
            ("Item", "Subsystem", "Bus", "Maturity", "Power\nmode", "Average\n[W]", "Duty\n[-]", "Effective\n[W]",
             "Margin\n[%]", "With\nmargin\n[W]", "Peak\n[W]", "Peak with\nmargin\n[W]"),
            [Row((r.item, r.subsystem, r.bus, r.maturity, r.power_mode or NOT_LISTED_TEXT, _w(r.average_w),
                  f"{r.duty_cycle:g}", _w(r.effective_w), _ratio(r.margin_percent), _w(r.margined_w), _w(r.peak_w),
                  _w(r.margined_peak_w)),
                 tooltips={4: "Not listed in this system mode: the item's power is unknown"} if not r.power_mode
                 else {}) for r in rows], numeric=range(5, 12), stretch=0)
        self.subsystems_table.set_table(
            ("Subsystem", "Effective [W]", "With\nmargins [W]", "Peak [W]", "Peak with\nmargins [W]"),
            [Row((s.subsystem or "(none)", _w(s.effective_w), _w(s.margined_w), _w(s.peak_w), _w(s.margined_peak_w)))
             for s in (mode.subsystems if mode is not None else ())], numeric=range(1, 5), stretch=0)
        self.buses_table.set_table(
            ("Bus", "Efficiency [-]", *_FLOW_HEADERS, "Peak source\nwith margins [W]"),
            [Row((b.bus, _ratio(b.converter_efficiency), *_flow_cells(b.average), _w(b.peak.source_margined_w)))
             for b in (mode.buses if mode is not None else ())], numeric=range(1, 8), stretch=0)
        for table in (self.items_table, self.subsystems_table, self.buses_table):
            _fit(table)

    def csv_text(self) -> str:
        budget = self.budget
        if budget is None:
            return ""
        rows: list = [("mode", "duty_cycle", "load_w", "unit_margined_w", "system_margined_w", "source_w",
                       "source_margined_w", "peak_load_w", "peak_unit_margined_w", "peak_system_margined_w",
                       "peak_source_w", "peak_source_margined_w")]
        rows += [tuple(row.values()) for row in budget.mode_rows()]
        average = budget.duty_cycle_average()
        if average is not None:
            rows.append(("duty-cycle average", 1, average.load_w, average.unit_margined_w, average.system_margined_w,
                         average.source_w, average.source_margined_w))
        for name, table in (("items", budget.rows()), ("subsystems", budget.subsystem_rows()),
                            ("buses", budget.bus_rows())):
            rows.append(())
            if table:
                rows.append(tuple(table[0].keys()))
                rows += [tuple(row.values()) for row in table]
            else:
                rows.append((f"no {name}",))
        return _csv_text(rows, self._scenario)


# -- the Mass page --------------------------------------------------------------------------------------------------

def _kg(value) -> str:
    return UNKNOWN_TEXT if value is None else f"{value:.2f}"


class MassPage(QWidget):
    """The mass budget of one spacecraft (``analyses.mass_budget``): the
    lines of Run › Design Checks' Mass budget group, with the equipment
    list's lines; a placeholder mass is "unknown" and the totals leave it
    out."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.budget = None
        self._scenario = None
        self._shown: tuple = (object(), None)  # (spacecraft, invalid) last shown: the same is not computed again
        self.copy_action: QAction | None = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        outer.addWidget(self.stack)
        self.empty_state = EmptyState("No mass budget")
        self.stack.addWidget(self.empty_state)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)  # the area insets the page (UI audit UI-16)
        layout.setSpacing(SPACE["md"])
        self.top_row = QHBoxLayout()
        self.top_row.setSpacing(SPACE["sm"])
        self.title_label = set_role(QLabel("Mass budget"), role="section-title")
        self.top_row.addWidget(self.title_label)
        self.status_badge = _status_badge()
        self.top_row.addWidget(self.status_badge)
        self.top_row.addStretch(1)
        layout.addLayout(self.top_row)
        self.table = _fitted(DataTable("No mass line."))
        self.table.view.setAccessibleName("Mass budget lines")
        layout.addWidget(self.table)
        self.totals_sheet = ValueSheet("Totals")
        layout.addWidget(self.totals_sheet)
        self.notes = NoteList("note")
        layout.addWidget(self.notes)
        layout.addStretch(1)
        self.stack.addWidget(_scroll(body))

    def set_copy_action(self, action: QAction) -> None:
        self.copy_action = action
        self.top_row.addWidget(_text_button(action))

    def set_spacecraft(self, sc, scenario=None, invalid: bool = False) -> None:
        """Show ``sc``'s mass budget (as :meth:`PowerPage.set_spacecraft`)."""
        from ..analyses.mass_budget import mass_budget

        if (sc, invalid) == self._shown:
            self._scenario = scenario
            return
        self._shown = (copy.deepcopy(sc), invalid)
        self._scenario = scenario
        self.budget = None
        if invalid:
            self.empty_state.set_text("The scenario has problems", "Fix them first: they are listed in the "
                                                                   "Problems panel (Ctrl+J).")
        elif sc is None:
            self.empty_state.set_text("No spacecraft", "The scenario has no spacecraft.")
        else:
            self.budget = mass_budget(sc)
        if self.budget is None:
            self.stack.setCurrentWidget(self.empty_state)
            return
        self.stack.setCurrentIndex(1)
        mass = self.budget
        self.title_label.setText(f"Mass budget of {mass.spacecraft} ({mass.policy})")
        _show_status(self.status_badge, not mass.unknown, "Complete", "Incomplete: unknown masses")
        self.table.set_table(("Item", "Kind", "Subsystem", "Maturity", "Basic [kg]", "Growth [%]", "Growth [kg]"),
                             [Row((r["item"], r["kind"], r["subsystem"], r["maturity"], _kg(r["basic_mass_kg"]),
                                   f"{r['growth_percent']:g}", _kg(r["growth_kg"])), tooltips={5: r["column"]})
                              for r in mass.rows()], numeric=(4, 5, 6), stretch=0)
        _fit(self.table)
        rows = [("Basic dry mass", f"{mass.basic_dry_kg:.2f}", "kg"), ("+ Growth", f"{mass.growth_kg:.2f}", "kg"),
                ("+ System margin", f"{mass.system_margin_kg:.2f}", "kg"),
                ("+ Propellant", f"{mass.propellant_kg:.2f}", "kg"),
                ("= Launch mass", f"{mass.launch_mass_kg:.2f}", "kg")]
        if mass.mass_limit_kg is not None:
            rows += [("Launch mass limit", f"{mass.mass_limit_kg:g}", "kg"),
                     ("Headroom", f"{mass.headroom_kg:.2f}", "kg")]
        self.totals_sheet.set_rows(rows)
        self.notes.set_notes(mass.notes)

    def csv_text(self) -> str:
        mass = self.budget
        if mass is None:
            return ""
        rows: list = [("item", "kind", "subsystem", "maturity", "basic_mass_kg", "growth_percent", "growth_kg",
                       "mass_with_growth_kg", "column")]
        rows += [(r["item"], r["kind"], r["subsystem"], r["maturity"], r["basic_mass_kg"], r["growth_percent"],
                  r["growth_kg"], r["mass_with_growth_kg"], r["column"]) for r in mass.rows()]
        rows += [(), ("total", "basic_dry_kg", mass.basic_dry_kg), ("total", "growth_kg", mass.growth_kg),
                 ("total", "system_margin_kg", mass.system_margin_kg), ("total", "propellant_kg", mass.propellant_kg),
                 ("total", "launch_mass_kg", mass.launch_mass_kg)]
        if mass.unknown:
            rows.append(("incomplete", "unknown_mass_items", ";".join(mass.unknown)))
        return _csv_text(rows, self._scenario)


# -- the Pointing page ----------------------------------------------------------------------------------------------

#: A requirement's status in the result table: its icon, the icon's ink and the word's ink (design rule 1: the
#: word says it too, never the colour alone).
_POINTING_MARKS = {
    "met": ("circle-check", "status.normal", "status.normal.text"),
    "not met": ("octagon-alert", "status.critical", "status.critical.text"),
    "TBD": ("triangle-alert", "status.caution", "status.caution.text"),
    "no contributor": ("triangle-alert", "status.caution", "status.caution.text"),
}
_AXIS_TEXT = {"": "not stated", "x": "x", "y": "y", "z": "z"}
_POINTING_SIZED_ROWS = 8  # [-] rows the requirement and contributor columns are measured from (15 columns each)


def _axis_values(contributor) -> list:
    """Every sourced value of a contributor: its spreads, means and period."""
    values = list(contributor.spread_arcsec.values()) + list(contributor.mean_arcsec.values())
    return values + ([contributor.period_s] if contributor.period_s is not None else [])


def contributor_source(contributor) -> str:
    """The source the contributor's values share; "" when they have none or
    differ (the Source column then says "several")."""
    sources = list(dict.fromkeys(value.source for value in _axis_values(contributor)))
    return sources[0] if len(sources) == 1 else ""


def _new_value(contributor, number: float) -> SourcedValue:
    """A new value of ``contributor``: with the source its values share, else "TBD"."""
    return SourcedValue(number, contributor_source(contributor) or _NEW_SOURCE)


class PointingPage(QWidget):
    """The pointing error budget of one spacecraft (``budgets.pointing``;
    ``engine.pointing_budget``): its requirements and contributors as
    editable tables, the body axis of the line of sight, and the result per
    requirement with each margin's status and the contributors that enter
    it. :attr:`edited` carries a copy of the whole section after each edit,
    as the Equipment page's. The result is computed from the section on
    the GUI thread, in the event after the tables are filled, so neither
    step takes long (PE-20)."""

    edited = Signal(object)  # schema.budgets.BudgetsConfig (a copy)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.spacecraft_name = ""
        self.section: BudgetsConfig | None = None  # the page's copy of the spacecraft's section
        self.budget = None  # engine.pointing_budget.PointingBudget of the section, None while not computed
        self._sc = None
        self._scenario = None
        self._invalid = False
        self._computed_for: tuple = (object(), None, None)  # (name, section, invalid) of the result shown
        self._compute_timer = QTimer(self)
        self._compute_timer.setSingleShot(True)
        self._compute_timer.setInterval(0)
        self._compute_timer.timeout.connect(self._compute)
        self._items: tuple = ()  # the equipment items' names (the Equipment column's choices)
        self._modes: tuple = ()  # the system modes' names
        self.copy_action: QAction | None = None
        self.add_pointing_action = self._action("Add Pointing Budget", "file-plus", self.add_pointing)
        self.add_requirement_action = self._action("Add Requirement", "file-plus", self.add_requirement)
        self.remove_requirement_action = self._action("Remove Requirement", "circle-minus", self.remove_requirement)
        self.add_contributor_action = self._action("Add Contributor", "file-plus", self.add_contributor)
        self.remove_contributor_action = self._action("Remove Contributor", "circle-minus", self.remove_contributor)
        self.add_sensors_action = self._action("Add Scenario Sensors", "activity", self.add_sensors)
        self.add_sensors_action.setToolTip("Add the star trackers, gyroscopes and sun sensors of the spacecraft as "
                                           "knowledge contributors, with their noise and its source")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        outer.addWidget(self.stack)
        self.empty_state = EmptyState("No pointing budget")  # its button secondary: Run is the one accent (UI-03)
        self.empty_state.button.clicked.connect(self.add_pointing_action.trigger)
        self.stack.addWidget(self.empty_state)

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)  # the area insets the page (UI audit UI-16)
        layout.setSpacing(SPACE["sm"])
        self.top_row = QHBoxLayout()
        self.top_row.setSpacing(SPACE["sm"])
        self.title_label = set_role(QLabel("Pointing budget"), role="section-title")
        self.top_row.addWidget(self.title_label)
        self.status_badge = _status_badge()
        self.top_row.addWidget(self.status_badge)
        self.top_row.addStretch(1)
        self.top_row.addWidget(set_role(QLabel("Line of sight along"), tone="secondary"))
        self.line_of_sight_combo = ComboBox()
        self.line_of_sight_combo.setAccessibleName("Line of sight along")
        self.line_of_sight_combo.setToolTip("The body axis along the line of sight: a half-cone requirement adds the "
                                            "errors about the two axes across it")
        for axis, text in _AXIS_TEXT.items():
            self.line_of_sight_combo.addItem(text, axis)
        self.line_of_sight_combo.currentIndexChanged.connect(self._on_line_of_sight)
        self.top_row.addWidget(self.line_of_sight_combo)
        layout.addLayout(self.top_row)

        self.requirements_table = EditableTable(
            "Requirements", "No pointing requirement yet",
            "Add one for each error the mission limits: its index, axis, limit and probability.",
            self.add_requirement_action, (self.add_requirement_action, self.remove_requirement_action),
            icon_only=False)
        self.requirements_table.empty.button.setText("Add Requirement")
        self.requirements_table.model.edited.connect(self._on_edited)
        self.requirements_table.view.selectionModel().currentRowChanged.connect(self._on_requirement_picked)
        self.contributors_table = EditableTable(
            "Contributors", "No contributor yet",
            "Add each source of pointing error with its behaviour and spread, or the scenario's sensors.",
            self.add_contributor_action,
            (self.add_contributor_action, self.remove_contributor_action, self.add_sensors_action), icon_only=False)
        self.contributors_table.empty.button.setText("Add Contributor")
        self.contributors_table.empty.add_action("Add Scenario Sensors").clicked.connect(
            self.add_sensors_action.trigger)
        self.contributors_table.model.edited.connect(self._on_edited)
        for table in (self.requirements_table, self.contributors_table):
            table.view.horizontalHeader().setResizeContentsPrecision(_POINTING_SIZED_ROWS)

        results = QWidget()
        results_layout = QVBoxLayout(results)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.setSpacing(SPACE["xs"])
        results_layout.addWidget(set_role(QLabel("Result per requirement"), role="heading"))
        self.results_table = DataTable("No requirement: add one above.", "Add Requirement")
        self.results_table.action_requested.connect(self.add_requirement_action.trigger)
        self.results_table.view.setAccessibleName("Pointing budget per requirement")
        self.results_table.set_fit_width()
        self.results_table.set_single_pick()
        self.results_table.row_chosen.connect(self._on_result_chosen)
        results_layout.addWidget(self.results_table, 3)
        self.terms_label = set_role(QLabel("Contributors that enter it"), role="heading")
        results_layout.addWidget(self.terms_label)
        self.terms_table = DataTable("No contributor enters this requirement.", "Add Contributor")
        self.terms_table.action_requested.connect(self.add_contributor_action.trigger)
        self.terms_table.view.setAccessibleName("Contributors that enter the requirement")
        self.terms_table.set_fit_width()
        results_layout.addWidget(self.terms_table, 2)
        self.notes = NoteList("note")
        results_layout.addWidget(self.notes)

        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setChildrenCollapsible(False)
        for widget in (self.requirements_table, self.contributors_table, results):
            self.splitter.addWidget(widget)
        for index, stretch in enumerate((2, 3, 4)):
            self.splitter.setStretchFactor(index, stretch)
        self.splitter.setSizes([180, 240, 400])  # [px] the result the tallest, until the user drags a divider
        layout.addWidget(self.splitter, 1)
        self.rule_label = set_role(QLabel(
            "Per index and axis the means add linearly; correlated groups add linearly, then root-sum-square with "
            "the independent contributors. The value is |mean| + k std at the probability; the line of sight's is "
            "|mean| + std max sqrt(-2 ln(1 - P)) from the two axes across it. Angles in arcsec."), role="caption")
        self.rule_label.setWordWrap(True)
        layout.addWidget(self.rule_label)
        body.setMinimumHeight(880)  # [px] the three tables at a useful height; the page scrolls below it
        self.stack.addWidget(_scroll(body))
        self.body = body
        self._show_state()

    def _action(self, text: str, icon_name: str, handler) -> QAction:
        action = QAction(icon(icon_name, "text.secondary"), text, self)
        action.setToolTip(text)
        action.triggered.connect(handler)
        return action

    def set_copy_action(self, action: QAction) -> None:
        self.copy_action = action
        self.top_row.addWidget(_text_button(action))

    @property
    def pointing(self):
        return self.section.pointing if self.section is not None else None

    # -- what is shown --------------------------------------------------------------------------------------------
    def set_spacecraft(self, sc, scenario=None, invalid: bool = False) -> None:
        """Show ``sc``'s pointing budget (``sc`` as edited, valid or not;
        ``invalid``: the scenario does not validate, so no result is
        computed). The page's own copy stays when it equals the
        spacecraft's (the edit just made), so the tables keep their place."""
        self._sc, self._scenario = sc, scenario
        name = sc.name if sc is not None else ""
        section = sc.budgets if sc is not None else None
        if (name, section) != (self.spacecraft_name, self.section):
            self.spacecraft_name = name
            self.section = clone(section)
            self._items = tuple(item.name for item in section.equipment) if section is not None else ()
            self._modes = tuple(mode.name for mode in section.modes) if section is not None else ()
            self._show_state()
            if self.pointing is not None:
                self._reload()
        if (name, section, invalid) != self._computed_for:
            self._computed_for = (name, clone(section), invalid)
            self._invalid = invalid
            self.budget = None
            self._compute_timer.start()  # the result in the next event: each step stays well under 50 ms

    def _show_state(self) -> None:
        if not self.spacecraft_name:
            self.empty_state.set_text("No spacecraft", "The scenario has no spacecraft. Add one in Scenario › "
                                                       "Spacecraft, then give it a pointing budget here.")
            self.stack.setCurrentWidget(self.empty_state)
        elif self.pointing is None:
            self.empty_state.set_text(
                "No pointing budget", f"{self.spacecraft_name} has no pointing budget: no pointing requirement or "
                "error contributor. Every number it holds has a source or is TBD.", "Add Pointing Budget")
            self.stack.setCurrentWidget(self.empty_state)
        else:
            self.stack.setCurrentIndex(1)

    def _reload(self) -> None:
        pointing = self.pointing
        self.requirements_table.set_rows(pointing.requirements, self._requirement_columns())
        self.requirements_table.title_label.setText(f"Requirements ({len(pointing.requirements)})")
        self.contributors_table.set_rows(pointing.contributors, self._contributor_columns())
        self.contributors_table.title_label.setText(f"Contributors ({len(pointing.contributors)})")
        self.line_of_sight_combo.blockSignals(True)
        self.line_of_sight_combo.setCurrentIndex(max(self.line_of_sight_combo.findData(pointing.line_of_sight), 0))
        self.line_of_sight_combo.blockSignals(False)
        if pointing.requirements and self.requirements_table.current_row() is None:
            self.requirements_table.select_row(0)

    def _compute(self) -> None:
        """The result from the page's section (nothing while the scenario
        does not validate: its problems are in the Problems panel)."""
        from ..engine.pointing_budget import pointing_budget

        self.budget = None
        if self.pointing is None:
            return
        if self._invalid:
            self.results_table.clear("The scenario has problems. Fix them first: they are listed in the Problems "
                                     "panel (Ctrl+J).")
            self.terms_table.clear("")
            self.notes.set_notes([])
            self.status_badge.setText("Not computed")
            set_badge(self.status_badge, WARNING)
            return
        self.results_table.set_empty_text("No requirement: add one above.")
        self.terms_table.set_empty_text("No contributor enters this requirement.")
        holder = copy.copy(self._sc)
        holder.budgets = self.section
        self.budget = budget = pointing_budget(holder)
        self.title_label.setText(f"Pointing budget of {self.spacecraft_name}")
        statuses = [result.status for result in budget.results]
        if "not met" in statuses:
            self.status_badge.setText(f"Not met: {statuses.count('not met')}")
            set_badge(self.status_badge, DANGER)
        elif budget.results and all(status == "met" for status in statuses):
            self.status_badge.setText("All met")
            set_badge(self.status_badge, SUCCESS)
        else:
            self.status_badge.setText("TBD values" if budget.results else "No requirement")
            set_badge(self.status_badge, WARNING)
        from ..engine.pointing_budget import RESULT_HEADER, result_cells

        rows = []
        for result in budget.results:
            cells = result_cells(result)
            tips = {10: "; ".join(result.notes)} if result.notes else {}
            rows.append(Row(cells, tooltips=tips, plain=frozenset({0, 1, 2, 3, 10}),
                            marks={10: _POINTING_MARKS[result.status]}))
        picked = self.results_table.chosen_row()
        self.results_table.set_table(tuple(_two_lines(h) for h in RESULT_HEADER), rows, numeric=range(4, 10),
                                     stretch=0)
        if rows:
            self.results_table.view.selectRow(min(picked or 0, len(rows) - 1))  # its terms follow (row_chosen)
        else:
            self._show_terms()

    def _on_result_chosen(self, row: int) -> None:
        if row != self.requirements_table.current_row():
            self.requirements_table.select_row(row)  # the requirement of the result picked
        self._show_terms()

    def _show_terms(self, *_args) -> None:
        from ..engine.pointing_budget import number, rad_to_arcsec

        budget = self.budget
        row = self.results_table.chosen_row()
        result = budget.results[row] if budget is not None and row is not None and row < len(budget.results) else None
        self.terms_label.setText(f"Contributors that enter {result.requirement}" if result is not None
                                 else "Contributors that enter it")
        terms = result.terms if result is not None else ()
        self.terms_table.set_table(
            ("Contributor", "Axis", "Behaviour", "Group", "Share\n[-]", "Mean\n[arcsec]", "Std\n[arcsec]", "Rule"),
            [Row((t.contributor, t.axis, t.behaviour, t.group, number(t.share), number(rad_to_arcsec(t.mean_rad)),
                  number(rad_to_arcsec(t.std_rad)), t.rule), plain=frozenset({0, 1, 2, 3, 7})) for t in terms],
            numeric=range(4, 7), stretch=7)
        self.notes.set_notes(result.notes if result is not None else ())

    def _on_requirement_picked(self, current, _previous=None) -> None:
        row = current.row() if current.isValid() else None
        if row is not None and self.budget is not None and row < self.results_table.row_count() \
                and row != self.results_table.chosen_row():
            self.results_table.view.selectRow(row)  # the result of the requirement picked

    # -- the columns ----------------------------------------------------------------------------------------------
    def _requirement_columns(self) -> list[Column]:
        from ..schema.budgets import (POINTING_INDICES, POINTING_INTERPRETATIONS, POINTING_KINDS,
                                      POINTING_REQUIREMENT_AXES)

        def put_number(key):
            def put(requirement, number):
                value = with_value(getattr(requirement, key), number)
                if key in ("limit_arcsec", "probability"):  # required: an empty cell is a placeholder
                    value = value or SourcedValue(None, _NEW_SOURCE)
                setattr(requirement, key, value)
            return put

        def put_source(key):
            def put(requirement, source):
                value = with_source(getattr(requirement, key), source)
                if key in ("limit_arcsec", "probability"):
                    value = value or SourcedValue(None, "")
                setattr(requirement, key, value)
            return put

        def times_source(requirement):
            values = [v for v in (requirement.window_s, requirement.stability_s) if v is not None]
            return values[0].source if values else ""

        def put_times_source(requirement, source):
            for key in ("window_s", "stability_s"):
                if getattr(requirement, key) is not None:
                    setattr(requirement, key, with_source(getattr(requirement, key), source))

        def number_of(key):
            return lambda r: getattr(r, key).value if getattr(r, key) is not None else None

        return [
            Column("Name", lambda r: r.name, lambda r, v: setattr(r, "name", v), tip="Unique among the requirements"),
            Column("Index", lambda r: r.index, lambda r, v: setattr(r, "index", v), "choice",
                   lambda _r: list(POINTING_INDICES),
                   tip="absolute: at any instant; mean: over the window; relative: about the window's mean; drift "
                       "and reproducibility: the change of the window mean between two windows"),
            Column("Kind", lambda r: r.kind, lambda r, v: setattr(r, "kind", v), "choice",
                   lambda _r: list(POINTING_KINDS), tip="performance: where it points; knowledge: what it believes"),
            Column("Axis", lambda r: r.axis, lambda r, v: setattr(r, "axis", v), "choice",
                   lambda _r: list(POINTING_REQUIREMENT_AXES),
                   display=lambda r: "line of sight" if r.axis == "line_of_sight" else r.axis,
                   tip="A body axis, or the line of sight (a half-cone from the two axes across it)"),
            Column("Limit [arcsec]", number_of("limit_arcsec"), put_number("limit_arcsec"), "number",
                   placeholder=lambda r: r.limit_arcsec.placeholder, heading="Limit\n[arcsec]",
                   tip="The largest error allowed, above 0"),
            Column("Limit source", lambda r: r.limit_arcsec.source, put_source("limit_arcsec"),
                   heading="Limit\nsource", tip='Where the limit comes from; "TBD" marks a placeholder'),
            Column("Probability [-]", number_of("probability"), put_number("probability"), "number",
                   placeholder=lambda r: r.probability.placeholder, heading="Probability\n[-]",
                   tip="The probability that the error stays within the limit, in (0, 1); no default"),
            Column("Probability source", lambda r: r.probability.source, put_source("probability"),
                   heading="Probability\nsource", tip="Where the probability comes from"),
            Column("Interpretation", lambda r: r.interpretation, lambda r, v: setattr(r, "interpretation", v),
                   "choice", lambda _r: list(POINTING_INTERPRETATIONS),
                   tip="Over what the probability holds: time (temporal), spacecraft and conditions (ensemble) or "
                       "both (mixed). Recorded; the sum is the same for each"),
            Column("Window [s]", number_of("window_s"), put_number("window_s"), "number",
                   placeholder=lambda r: is_placeholder(r.window_s), empty="none", heading="Window\n[s]",
                   tip="The observation period of a mean, relative, drift or reproducibility index; a periodic "
                       "contributor needs it"),
            Column("Stability [s]", number_of("stability_s"), put_number("stability_s"), "number",
                   placeholder=lambda r: is_placeholder(r.stability_s), empty="none", heading="Stability\n[s]",
                   tip="The shorter window of a relative index, at most the window; empty: the window"),
            Column("Times source", times_source, put_times_source, heading="Times\nsource",
                   tip="Where the window and the stability time come from"),
            Column("Modes", lambda r: ", ".join(r.modes), self._put_modes,
                   tip=f"The system modes it applies to, separated by commas ({', '.join(self._modes) or 'none yet'})"),
        ]

    @staticmethod
    def _put_modes(requirement, text: str) -> None:
        requirement.modes = [name.strip() for name in text.split(",") if name.strip()]

    def _contributor_columns(self) -> list[Column]:
        from ..engine.pointing_budget import RULES
        from ..schema.budgets import (POINTING_AXES, POINTING_BEHAVIOURS, POINTING_CONTRIBUTOR_KINDS,
                                      POINTING_DISTRIBUTIONS)

        def spread(axis):
            def get(c):
                value = c.spread_arcsec.get(axis)
                return value.value if value is not None else None

            def put(c, number):
                values = dict(c.spread_arcsec)
                if number is None:
                    if axis in values:
                        values[axis] = SourcedValue(None, values[axis].source or _NEW_SOURCE)  # a placeholder
                else:
                    values[axis] = SourcedValue(number, values[axis].source) if axis in values \
                        else _new_value(c, number)
                c.spread_arcsec = values

            return Column(f"Spread {axis} [arcsec]", get, put, "number",
                          placeholder=lambda c: is_placeholder(c.spread_arcsec.get(axis)), empty="none",
                          heading=f"Spread {axis}\n[arcsec]",
                          tip=f"About {axis}: the 1-sigma (gaussian), half-width (uniform) or amplitude (sinusoidal); "
                              "none: it does not act about this axis")

        def mean(axis):
            def get(c):
                value = c.mean_arcsec.get(axis)
                return value.value if value is not None else None

            def put(c, number):
                values = dict(c.mean_arcsec)
                if number is None:
                    values.pop(axis, None)
                else:
                    values[axis] = SourcedValue(number, values[axis].source) if axis in values \
                        else _new_value(c, number)
                c.mean_arcsec = values

            return Column(f"Mean {axis} [arcsec]", get, put, "number",
                          placeholder=lambda c: is_placeholder(c.mean_arcsec.get(axis)), empty="none",
                          heading=f"Mean {axis}\n[arcsec]", tip=f"About {axis}: the constant part, any sign; none: no mean")

        def put_period(c, number):
            if number is None:
                c.period_s = SourcedValue(None, c.period_s.source if c.period_s else _NEW_SOURCE) \
                    if c.behaviour == "periodic" else None
            else:
                c.period_s = SourcedValue(number, c.period_s.source) if c.period_s is not None \
                    else _new_value(c, number)

        def put_behaviour(c, behaviour):
            c.behaviour = behaviour
            if behaviour == "periodic" and c.period_s is None:
                c.period_s = SourcedValue(None, _NEW_SOURCE)  # needed: a placeholder until given

        def put_source(c, source):
            c.spread_arcsec = {axis: SourcedValue(v.value, source) for axis, v in c.spread_arcsec.items()}
            c.mean_arcsec = {axis: SourcedValue(v.value, source) for axis, v in c.mean_arcsec.items()}
            if c.period_s is not None:
                c.period_s = SourcedValue(c.period_s.value, source)

        columns = [
            Column("Name", lambda c: c.name, self._rename_contributor, tip="Unique among the contributors"),
            Column("Kind", lambda c: c.kind, lambda c, v: setattr(c, "kind", v), "choice",
                   lambda _c: list(POINTING_CONTRIBUTOR_KINDS),
                   tip="The requirements it enters: performance, knowledge or both"),
            Column("Behaviour", lambda c: c.behaviour, put_behaviour, "choice", lambda _c: list(POINTING_BEHAVIOURS),
                   tip="Its time behaviour: it decides the indices it enters (the Enters column)"),
            Column("Distribution", lambda c: c.distribution, lambda c, v: setattr(c, "distribution", v), "choice",
                   lambda _c: list(POINTING_DISTRIBUTIONS), heading="Distri-\nbution",
                   tip="What the spread is: a 1-sigma (gaussian), a half-width (uniform) or an amplitude (sinusoidal)"),
        ]
        columns += [spread(axis) for axis in POINTING_AXES] + [mean(axis) for axis in POINTING_AXES]
        columns += [
            Column("Period [s]", lambda c: c.period_s.value if c.period_s is not None else None, put_period, "number",
                   placeholder=lambda c: is_placeholder(c.period_s), empty="none", heading="Period\n[s]",
                   tip="The period of a periodic contributor (needed for it)"),
            Column("Source", contributor_source, put_source,
                   display=lambda c: contributor_source(c) or ("several" if _axis_values(c) else ""),
                   tip='Where its values come from (an edit sets every value\'s source); "TBD" marks placeholders'),
            Column("Group", lambda c: c.group, lambda c, v: setattr(c, "group", v),
                   tip="Contributors of one group are correlated: they add linearly; empty: independent"),
            Column("Equipment", lambda c: c.equipment, lambda c, v: setattr(c, "equipment", v), "choice",
                   lambda _c: [""] + list(self._items), empty="(other)",
                   tip="The item of the equipment list it comes from"),
            Column("Enters", lambda c: RULES[c.behaviour], tip="Which indices it enters, by its behaviour"),
        ]
        return columns

    def _rename_contributor(self, contributor, name: str) -> None:
        contributor.name = name

    # -- edits ------------------------------------------------------------------------------------------------------
    def _commit(self) -> None:
        if self.section is not None:
            self.edited.emit(clone(self.section))

    def _on_edited(self) -> None:
        self._commit()

    def _on_line_of_sight(self, *_args) -> None:
        if self.pointing is None:
            return
        self.pointing.line_of_sight = self.line_of_sight_combo.currentData() or ""
        self._commit()

    def add_pointing(self) -> None:
        """Add Pointing Budget: an empty pointing budget on the spacecraft
        shown (and a budgets section, without any other number, when it has
        none)."""
        from ..schema.budgets import PointingConfig

        if not self.spacecraft_name or self.pointing is not None:
            return
        self.section = clone(self.section) if self.section is not None else BudgetsConfig()
        self.section.pointing = PointingConfig()
        self._show_state()
        self._reload()
        self._commit()
        show_toast(self.window(), f"Added a pointing budget to {self.spacecraft_name}.")

    def add_requirement(self) -> None:
        from ..schema.budgets import PointingRequirementConfig

        pointing = self.pointing
        if pointing is None:
            return
        name = unique_name("requirement", [r.name for r in pointing.requirements])
        pointing.requirements.append(PointingRequirementConfig(
            name, SourcedValue(None, _NEW_SOURCE), SourcedValue(None, _NEW_SOURCE)))  # no default probability (PE-5)
        self._reload()
        self.requirements_table.select_row(len(pointing.requirements) - 1)
        self.requirements_table.view.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._commit()

    def remove_requirement(self) -> None:
        row = self.requirements_table.current_row()
        pointing = self.pointing
        if pointing is None or row is None or row >= len(pointing.requirements):
            return
        removed = pointing.requirements.pop(row)
        self._reload()
        self._commit()
        show_toast(self.window(), f"Removed {removed.name}. Undo: Ctrl+Z.")

    def add_contributor(self) -> None:
        from ..schema.budgets import POINTING_AXES, PointingContributorConfig

        pointing = self.pointing
        if pointing is None:
            return
        name = unique_name("contributor", [c.name for c in pointing.contributors])
        pointing.contributors.append(PointingContributorConfig(
            name, spread_arcsec={axis: SourcedValue(None, _NEW_SOURCE) for axis in POINTING_AXES}))
        self._reload()
        self.contributors_table.select_row(len(pointing.contributors) - 1)
        self.contributors_table.view.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._commit()

    def remove_contributor(self) -> None:
        row = self.contributors_table.current_row()
        pointing = self.pointing
        if pointing is None or row is None or row >= len(pointing.contributors):
            return
        removed = pointing.contributors.pop(row)
        self._reload()
        self._commit()
        show_toast(self.window(), f"Removed {removed.name}. Undo: Ctrl+Z.")

    def add_sensors(self) -> None:
        """Add Scenario Sensors: each star tracker, gyroscope and sun sensor
        of the spacecraft not in the list yet, as a knowledge contributor
        with its noise and the noise's source (PE-15)."""
        from ..engine.pointing_budget import sensor_contributors

        pointing = self.pointing
        if pointing is None or self._sc is None:
            return
        added = sensor_contributors(self._sc, pointing)
        if not added:
            show_toast(self.window(), f"{self.spacecraft_name} has no star tracker, gyroscope or sun sensor that "
                                      "is not in the list yet.", kind="info")
            return
        pointing.contributors.extend(added)
        self._reload()
        self._commit()
        show_toast(self.window(), f"Added {len(added)} sensor contributor(s): "
                                  + ", ".join(c.name for c in added) + ".")

    # -- copy -------------------------------------------------------------------------------------------------------
    def csv_text(self) -> str:
        from ..engine.pointing_budget import csv_rows

        if self.budget is None:
            return ""
        return _csv_text(csv_rows(self.budget), self._scenario)


def _two_lines(header: str) -> str:
    """A heading with its unit on a second line ("Value\\n[arcsec]")."""
    return header.replace(" [", "\n[", 1)


# -- the area -------------------------------------------------------------------------------------------------------

class BudgetsViews(TabWidget):
    """The Budgets area's tabs and the spacecraft picker of its header.
    :attr:`budgets_edited` carries (spacecraft name, section) after an edit
    on the Equipment or the Pointing page; :attr:`spacecraft_changed` the spacecraft
    picked."""

    budgets_edited = Signal(str, object)
    spacecraft_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("budgetsViews")
        self._scenario = None
        self._draft = None
        self._stale = False  # a scenario came while the area was not shown: shown, it refreshes
        self._pending: dict = {}  # page -> the arguments of its set_spacecraft, until it is shown
        # The spacecraft picker, in the area's header (MainWindow), shown when there are several.
        self.selector = QWidget()
        row = QHBoxLayout(self.selector)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(SPACE["sm"])
        label = QLabel("Spacecraft")
        self.spacecraft_combo = ComboBox()
        self.spacecraft_combo.setAccessibleName("Spacecraft")
        self.spacecraft_combo.setToolTip("The spacecraft whose budgets the pages show")
        label.setBuddy(self.spacecraft_combo)
        row.addWidget(label)
        row.addWidget(self.spacecraft_combo)
        self.selector.setVisible(False)
        self.spacecraft_combo.currentTextChanged.connect(self._on_spacecraft_picked)

        self.equipment_page = EquipmentPage()
        self.equipment_page.edited.connect(self._on_edited)
        self.equipment_page.section_added.connect(self.add_section)
        self.power_page = PowerPage()
        self.mass_page = MassPage()
        self.pointing_page = PointingPage()
        self.pointing_page.edited.connect(self._on_edited)
        self.addTab(self.equipment_page, "Equipment")
        self.addTab(self.power_page, "Power")
        self.addTab(self.mass_page, "Mass")
        self.addTab(self.pointing_page, "Pointing")  # after Mass (the owner, 2026-11-24; PE-1)
        # Copy as CSV: the table of the page shown (the window's Budgets › Copy Budget as CSV).
        self.copy_action = QAction(icon("file-output", "text.secondary"), "Copy as CSV", self)
        self.copy_action.setShortcut(QKeySequence("Ctrl+Shift+C"))  # the window's (Budgets › Copy as CSV)
        self.copy_action.triggered.connect(self.copy_csv)
        for page in (self.equipment_page, self.power_page, self.mass_page, self.pointing_page):
            page.set_copy_action(self.copy_action)
        self.propellant_widget = None  # BudgetWidget, given by add_propellant
        connect_while_alive(self.currentChanged, self._apply_pending)  # sent when a page is deleted (K-44)
        # The tab bar's right corner: the window's Open in Own Window button (gui.breakout) and, while the
        # area is in a window of its own, the spacecraft picker (the area's header stays in the main window).
        self.corner = QWidget()
        self.corner_layout = QHBoxLayout(self.corner)
        self.corner_layout.setContentsMargins(0, 0, SPACE["sm"], 0)
        self.corner_layout.setSpacing(SPACE["sm"])
        self.setCornerWidget(self.corner, Qt.Corner.TopRightCorner)

    def add_tool_button(self, button: QWidget) -> None:
        """A button of the window's in the tab bar's corner (it moves with the area)."""
        self.corner_layout.addWidget(button)

    def add_propellant(self, scroll: QScrollArea, budget_widget) -> None:
        """The delta-V and propellant budget, moved from Run › Budget (Q3)."""
        self.propellant_widget = budget_widget
        self.addTab(scroll, "Propellant")

    # -- the scenario ---------------------------------------------------------------------------------------------
    def set_scenario(self, scenario, draft=None) -> None:
        """``scenario``: the edited scenario when it validates, else None;
        ``draft``: the scenario as edited, valid or not (the Equipment page
        edits it either way)."""
        self._scenario = scenario
        self._draft = draft if draft is not None else scenario
        names = [sc.name for sc in self._draft.spacecraft] if self._draft is not None else []
        if names != [self.spacecraft_combo.itemText(i) for i in range(self.spacecraft_combo.count())]:
            current = self.spacecraft_combo.currentText()
            self.spacecraft_combo.blockSignals(True)
            self.spacecraft_combo.clear()
            self.spacecraft_combo.addItems(names)
            if current in names:
                self.spacecraft_combo.setCurrentText(current)
            self.spacecraft_combo.blockSignals(False)
        self.selector.setVisible(len(names) > 1)
        self.refresh()

    def spacecraft_name(self) -> str:
        return self.spacecraft_combo.currentText()

    def show_spacecraft(self, name: str) -> None:
        if self.spacecraft_combo.findText(name) >= 0:
            self.spacecraft_combo.setCurrentText(name)

    def _on_spacecraft_picked(self, name: str) -> None:
        self.refresh()
        self.spacecraft_changed.emit(name)

    @staticmethod
    def _named(scenario, name: str):
        if scenario is None:
            return None
        return next((sc for sc in scenario.spacecraft if sc.name == name), None)

    def shown(self) -> bool:
        """The area is the one shown (in its window, shown or not)."""
        return self.isVisibleTo(self.window())

    def refresh(self) -> None:
        """The pages from the scenario: the page shown now, the others when
        they are shown; nothing while the area is not shown."""
        if not self.shown():
            self._stale = True
            return
        self._stale = False
        name = self.spacecraft_name()
        draft_sc = self._named(self._draft, name)
        valid_sc = self._named(self._scenario, name)
        invalid = self._scenario is None and self._draft is not None and draft_sc is not None
        self._pending = {self.equipment_page: (draft_sc, self._scenario),
                         self.power_page: (valid_sc, self._scenario, invalid),
                         self.mass_page: (valid_sc, self._scenario, invalid),
                         self.pointing_page: (draft_sc, self._scenario, invalid)}
        self._apply_pending()

    def refresh_if_stale(self, *_args) -> None:
        if self._stale:
            self.refresh()

    def showEvent(self, event) -> None:  # noqa: N802 -- Qt API name
        super().showEvent(event)
        self.refresh_if_stale()

    def _apply_pending(self, *_args) -> None:
        if self._stale:
            self.refresh()
            return
        page = self.currentWidget()
        arguments = self._pending.pop(page, None)
        if arguments is not None:
            page.set_spacecraft(*arguments)

    # -- edits ------------------------------------------------------------------------------------------------------
    def _on_edited(self, section) -> None:
        self.budgets_edited.emit(self.spacecraft_name(), section)

    def add_section(self) -> None:
        """Add budgets section: a new section on the spacecraft shown."""
        name = self.spacecraft_name()
        if not name or self.equipment_page.section is not None:
            return
        self.budgets_edited.emit(name, new_section())
        show_toast(self.window(), f"Added a budgets section to {name}.")

    # -- copy -------------------------------------------------------------------------------------------------------
    def _current_csv_page(self):
        page = self.currentWidget()
        return page if page in (self.equipment_page, self.power_page, self.mass_page, self.pointing_page) else None

    def copy_csv(self) -> str:
        """The table of the page shown, as CSV, to the clipboard (Propellant:
        its own Copy as CSV). Returns the text copied; nothing while the
        area is not shown (the window shows it)."""
        if not self.isVisibleTo(self.window()):
            return ""
        page = self._current_csv_page()
        if page is None:
            if self.propellant_widget is not None and self.propellant_widget.copy_button.isEnabled():
                self.propellant_widget.copy_button.click()
                return QGuiApplication.clipboard().text()
            show_toast(self.window(), "Compute the propellant budget first: nothing to copy yet.", kind="info")
            return ""
        text = page.csv_text()
        if not text:
            show_toast(self.window(), "Nothing to copy on this page yet.", kind="info")
            return ""
        QGuiApplication.clipboard().setText(text)
        show_toast(self.window(), f"Copied the {self.tabText(self.currentIndex()).lower()} budget as CSV.")
        return text
