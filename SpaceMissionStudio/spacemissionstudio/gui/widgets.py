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

"""Small reusable input widgets shared by the GUI's editor dialogs.

:class:`PreciseDoubleSpinBox` exists because a plain ``QDoubleSpinBox``
silently ROUNDS every value to its display ``decimals()`` the moment the
value is set -- so merely opening an editor on an existing scenario and
clicking OK, with zero edits, rewrote its data. Found by round-tripping
every bundled template through every editor dialog: e.g. template 13's
0.00667 kg*m^2 CubeSat inertia came back as 0.007 (a 5% change), and a
2-hour duration of 0.08333 days came back as 0.0833.

A second, smaller version of the same bug: values used to be kept to 10
decimal places, which still rounded a magnetometer's 1.18e-9 T noise to
1.2e-9 T (found applying a catalog preset). Values are now kept exactly
and displayed as their shortest exact text.

A third: a value outside a box's range (one from a file) was silently
clamped to the range. Every spin box here now keeps it
(:class:`_KeepsOutOfRange`): it shows the nearest allowed value, but
``value()`` returns the file's until the box is changed, and
:func:`out_of_range_boxes` finds such boxes so the editor can say so.
"""

from __future__ import annotations

import math
from decimal import Decimal

from PySide6.QtCore import QEvent, QObject, QPoint, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QPalette, QValidator
from PySide6.QtWidgets import (QAbstractItemView, QAbstractSpinBox, QApplication, QBoxLayout, QButtonGroup, QCheckBox,
                               QComboBox, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QFrame, QGroupBox, QHBoxLayout,
                               QLabel, QLayout, QPushButton, QScrollArea, QSizePolicy, QSpinBox, QStackedWidget, QStyle,
                               QStyledItemDelegate, QStyleOptionComboBox, QStylePainter, QTabBar, QTableView,
                               QTabWidget, QVBoxLayout, QWidget)
from shiboken6 import isValid

from .theme import FIELD_WIDTH, LABEL_COLUMN_MAX_PX, ROW_HEIGHT, SPACE, set_role

# The flags of a window of its own: a title bar with the system menu,
# minimise, maximise and close (the 3D model editor, the viewers).
WINDOW_FLAGS = (Qt.WindowType.Window | Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowSystemMenuHint
                | Qt.WindowType.WindowMinMaxButtonsHint | Qt.WindowType.WindowCloseButtonHint)


def make_window(widget: QWidget) -> QWidget:
    """``widget`` as a window of its own (:data:`WINDOW_FLAGS`), still
    owned by its parent, which closes it; returns it. Show it with
    :func:`show_window`. It does not keep the application running once
    the main window has closed."""
    widget.setWindowFlags(WINDOW_FLAGS)
    widget.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
    return widget


def show_window(widget: QWidget) -> None:
    """Show ``widget`` as a window of its own, in front: not modal, and
    not attached to the window that opened it (a window manager moves a
    modal dialog with its parent, and keeps a transient one above it).
    Opened from inside a modal dialog it stays that dialog's transient
    window, the one kind a modal dialog leaves usable."""
    widget.setWindowModality(Qt.WindowModality.NonModal)
    if not widget.isVisible() and QApplication.activeModalWidget() is None:
        widget.winId()  # the native window, so that its transient parent can be cleared before it shows
        handle = widget.windowHandle()
        if handle is not None:
            handle.setTransientParent(None)
    if widget.isMinimized():
        widget.showNormal()
    widget.show()
    widget.raise_()
    widget.activateWindow()


# Qt rounds every value to decimals() as it is set. 40 decimal places
# keep a double's full 17 significant digits for magnitudes down to
# ~1e-23 -- far smaller than any physical value these editors hold
# (nanotesla-level noise is ~1e-9).
_STORAGE_DECIMALS = 40

# Text that is a valid PREFIX of a number while the user is still typing.
_PARTIAL_NUMBERS = {"", "-", "+", ".", "-.", "+."}


class _IgnoreWheel:
    """The mouse wheel never changes this widget's value (real user
    feedback: scrolling a form changed whichever value passed under the
    pointer -- "that's annoying"). The ignored event goes on to the
    parent, so the surrounding page scrolls instead. Values still change
    by typing, the arrow buttons and the keyboard.

    Per-class rather than an app-wide event filter: a Python filter on
    the whole application is called for every event on every object, and
    PySide crashed doing that for objects Qt creates internally."""

    def wheelEvent(self, event):  # noqa: N802 -- Qt API name
        event.ignore()


class _KeepsOutOfRange:
    """A value set outside the box's range is kept, not clamped: the box
    shows the nearest allowed value, :meth:`value` returns the one set
    until the box is changed (typed, stepped) or set again, and
    :meth:`out_of_range_value` says which value it holds. A range set
    later that takes the value shows it. (docs/ux-audit.md: values from a
    file are never changed silently.)"""

    def setValue(self, value) -> None:  # noqa: N802 -- Qt API name
        kept = None
        if isinstance(value, (int, float)) and math.isfinite(value) and not (
                self.minimum() <= value <= self.maximum()):
            kept = value
        self._sms_setting = True
        try:
            super().setValue(value)
        finally:
            self._sms_setting = False
        self._sms_kept = kept
        if kept is not None and not getattr(self, "_sms_watching", False):
            self.valueChanged.connect(self._sms_on_value_changed)
            self._sms_watching = True

    def value(self):
        kept = getattr(self, "_sms_kept", None)
        return kept if kept is not None else super().value()

    def out_of_range_value(self):
        """The value this box holds outside its range, or None."""
        return getattr(self, "_sms_kept", None)

    def _sms_on_value_changed(self, *_args) -> None:
        if not getattr(self, "_sms_setting", False):
            self._sms_kept = None  # changed in the box: what it shows is the value now

    def setRange(self, minimum, maximum) -> None:  # noqa: N802 -- Qt API name
        super().setRange(minimum, maximum)
        self._sms_refit()

    def setMinimum(self, minimum) -> None:  # noqa: N802 -- Qt API name
        super().setMinimum(minimum)
        self._sms_refit()

    def setMaximum(self, maximum) -> None:  # noqa: N802 -- Qt API name
        super().setMaximum(maximum)
        self._sms_refit()

    def _sms_refit(self) -> None:
        kept = getattr(self, "_sms_kept", None)
        if kept is not None and self.minimum() <= kept <= self.maximum():
            self.setValue(kept)


def out_of_range_boxes(root: QWidget) -> list:
    """Every spin box in ``root`` holding a value outside its range."""
    return [box for box in root.findChildren(QAbstractSpinBox)
            if isinstance(box, _KeepsOutOfRange) and box.out_of_range_value() is not None]


class SpinBox(_IgnoreWheel, _KeepsOutOfRange, QSpinBox):
    """A QSpinBox the mouse wheel doesn't change."""


class DoubleSpinBox(_IgnoreWheel, _KeepsOutOfRange, QDoubleSpinBox):
    """A QDoubleSpinBox the mouse wheel doesn't change."""


class ComboBox(_IgnoreWheel, QComboBox):
    """A QComboBox the mouse wheel doesn't change (its open list still
    scrolls). An entry longer than the field (a field is at most
    :data:`CHOICE_FIELD_MAX_WIDTH_PX` wide, UI audit UI-26) ends in "…"
    instead of being cut; the open list shows it whole. Its size hint
    keeps that room beside the text (``SPACE["md"]``), so an entry the
    field was sized for is shown whole ("100 %" read "10…", UI audit B7)."""

    def sizeHint(self) -> QSize:  # noqa: N802 -- Qt API name
        hint = super().sizeHint()
        return QSize(hint.width() + SPACE["md"], hint.height())

    def paintEvent(self, _event) -> None:  # noqa: N802 -- Qt API name
        painter = QStylePainter(self)  # QComboBox.paintEvent, with the text elided
        painter.setPen(self.palette().color(QPalette.ColorRole.Text))
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        painter.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, option)
        if self.currentIndex() < 0 and self.placeholderText():
            option.palette.setBrush(QPalette.ColorRole.ButtonText, option.palette.placeholderText())
            option.currentText = self.placeholderText()
        field = self.style().subControlRect(QStyle.ComplexControl.CC_ComboBox, option,
                                            QStyle.SubControl.SC_ComboBoxEditField, self)
        room = field.width() - option.iconSize.width() * (not option.currentIcon.isNull()) - SPACE["md"]
        if self.fontMetrics().horizontalAdvance(option.currentText) > room:
            option.currentText = self.fontMetrics().elidedText(option.currentText, Qt.TextElideMode.ElideRight,
                                                               max(room, 0))
        painter.drawControl(QStyle.ControlElement.CE_ComboBoxLabel, option)


class _TabBar(_IgnoreWheel, QTabBar):
    pass


class TabWidget(QTabWidget):
    """A QTabWidget whose tab bar the mouse wheel doesn't switch."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setTabBar(_TabBar(self))


class PreciseDoubleSpinBox(_IgnoreWheel, _KeepsOutOfRange, QDoubleSpinBox):
    """A ``QDoubleSpinBox`` that stores values at full precision.

    :meth:`setDecimals` sets the MINIMUM number of decimals shown (e.g.
    ``3`` shows ``500.000``) rather than the precision values are rounded
    to; a value with more significant decimals than that shows them, so
    what is displayed is always what will be saved. Always uses ``.`` as
    the decimal point (a typed ``,`` is accepted too), matching every
    other number this app prints, rather than following the system locale.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._display_decimals = 2
        super().setDecimals(_STORAGE_DECIMALS)

    def setDecimals(self, prec: int) -> None:  # noqa: N802 -- Qt API name
        self._display_decimals = max(0, int(prec))
        self.update()  # re-render the current value with the new minimum

    def decimals(self) -> int:
        return self._display_decimals

    def textFromValue(self, value: float) -> str:  # noqa: N802 -- Qt override
        # The shortest text that parses back to exactly this value, written
        # without an exponent (repr's "1.18e-09" -> "0.00000000118").
        text = format(Decimal(repr(float(value))), "f")
        whole, _, fraction = text.partition(".")
        fraction = fraction.rstrip("0").ljust(self._display_decimals, "0")
        return f"{whole}.{fraction}" if fraction else whole

    def _number_part(self, text: str) -> str:
        text = text.strip()
        if self.prefix() and text.startswith(self.prefix()):
            text = text[len(self.prefix()):]
        if self.suffix() and text.endswith(self.suffix()):
            text = text[:-len(self.suffix())]
        return text.strip().replace(",", ".")

    def valueFromText(self, text: str) -> float:  # noqa: N802 -- Qt override
        try:
            return float(self._number_part(text))
        except ValueError:
            return self.value()

    def validate(self, text: str, pos: int):
        number = self._number_part(text)
        if number in _PARTIAL_NUMBERS:
            return QValidator.State.Intermediate, text, pos
        try:
            value = float(number)
        except ValueError:
            return QValidator.State.Invalid, text, pos
        if not math.isfinite(value):
            return QValidator.State.Invalid, text, pos
        if self.minimum() <= value <= self.maximum():
            return QValidator.State.Acceptable, text, pos
        return QValidator.State.Intermediate, text, pos


def exact_number_text(value: float) -> str:
    """Shortest text that parses back to exactly ``value`` (``repr``-based),
    minus a redundant trailing ``.0`` -- for numbers edited as free text
    (e.g. a comma-separated list), where ``f"{value:g}"`` keeps only 6
    significant digits and so silently changed the data on a round trip.
    """
    text = repr(float(value))
    return text[:-2] if text.endswith(".0") else text


# -- number fields with their unit (UI overhaul M4a) --------------------------------

NUMBER_FIELD_MAX_WIDTH_PX = FIELD_WIDTH["number"]  # [px] a number sits beside its label, not across the page
VECTOR_FIELD_MAX_WIDTH_PX = FIELD_WIDTH["vector"]  # [px] each number of a row of several (x, y, z)
VECTOR_FIELD_MIN_WIDTH_PX = FIELD_WIDTH["vector_min"]  # [px] what one of them shrinks to on a narrow page
CHOICE_FIELD_MAX_WIDTH_PX = FIELD_WIDTH["choice"]  # [px] a drop-down list: as wide as a long entry (UI-26)
FULL_LABEL = "sms_full_label"  # a label's text with its unit, kept when the unit moves into the field


def style_number(box: QAbstractSpinBox, unit: str | None = None,
                 max_width: int = NUMBER_FIELD_MAX_WIDTH_PX) -> QAbstractSpinBox:
    """Give a spin box the number field's look: right-aligned, tabular
    figures, at most ``max_width`` wide, and (with ``unit``) the unit as
    its suffix. Returns ``box``."""
    from . import units
    from .theme import numeric_font

    box.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    box.setFont(numeric_font())
    if box.maximumWidth() > max_width:
        box.setMaximumWidth(max_width)
    if unit is not None and hasattr(box, "setSuffix"):
        box.setSuffix(units.suffix(unit))
    return box


class NumberField(PreciseDoubleSpinBox):
    """A number and its unit: the value kept exactly (PreciseDoubleSpinBox),
    the unit as a suffix ("550.0 km"), right-aligned in tabular figures.
    ``cleanText()`` is the number alone."""

    def __init__(self, unit: str = "", minimum: float = 0.0, maximum: float = 1e12, decimals: int = 2,
                 step: float = 1.0, value: float = 0.0, parent: QWidget | None = None):
        super().__init__(parent)
        self.setRange(minimum, maximum)
        self.setDecimals(decimals)
        self.setSingleStep(step)
        self.setValue(value)
        style_number(self, unit)

    def set_unit(self, unit: str) -> None:
        style_number(self, unit)


# Forms are walked through QObjects only (widgets and layouts), never their
# QLayoutItems: Qt deletes an item without telling PySide6, whose wrapper
# for it can then be handed out for a new object at that address (on CI, a
# QMenu's new QAction came back as a QWidgetItem).
_DIRECT = Qt.FindChildOption.FindDirectChildrenOnly


def layout_widgets(layout: QLayout) -> list:
    """The widgets ``layout`` holds, its nested layouts' too."""
    parent = layout.parentWidget()
    widgets = [w for w in parent.findChildren(QWidget, options=_DIRECT) if layout.indexOf(w) >= 0] if parent else []
    for nested in layout.findChildren(QLayout, options=_DIRECT):
        widgets += layout_widgets(nested)
    return widgets


def form_rows(form: QFormLayout) -> dict:
    """``{row: {role: widget or layout}}`` of ``form``'s rows."""
    rows: dict = {}
    parent = form.parentWidget()
    for widget in parent.findChildren(QWidget, options=_DIRECT) if parent else []:
        row, role = form.getWidgetPosition(widget)
        if row >= 0:
            rows.setdefault(row, {})[role] = widget
    for nested in form.findChildren(QLayout, options=_DIRECT):
        row, role = form.getLayoutPosition(nested)
        if row >= 0:
            rows.setdefault(row, {})[role] = nested
    return rows


def _number_boxes(field) -> list:
    """The spin boxes a form row's field is or holds."""
    if isinstance(field, QAbstractSpinBox):
        return [field]
    if isinstance(field, QWidget):
        return field.findChildren(QAbstractSpinBox)
    if field is not None:  # a layout: the boxes of its widgets
        return [box for widget in layout_widgets(field) for box in _number_boxes(widget)]
    return []


def units_into_fields(root: QWidget) -> None:
    """Every form under ``root``: a row labelled "Name [unit]" whose field
    holds numbers gets the unit as those fields' suffix and the label
    "Name"; its number fields get the number field's look. A label with
    an unknown bracket, or a row without a number, is left as it is; a
    box that already has a suffix keeps it. A row too wide for the form
    wraps its field under its label."""
    from . import units

    for form in root.findChildren(QFormLayout):
        # A row too wide for the page puts its field under its label instead
        # of making the page scroll sideways (the Power page at 1280 px).
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        for _row, roles in sorted(form_rows(form).items()):
            field = roles.get(QFormLayout.ItemRole.FieldRole)
            boxes = _number_boxes(field)
            if not boxes:
                continue
            label = roles.get(QFormLayout.ItemRole.LabelRole)
            unit = None
            if isinstance(label, QLabel):
                text, unit = units.split_label(label.text())
                if unit is not None:
                    # Messages still name the field with its unit ("Dry mass
                    # [kg] must be ..."): feedback.row_label reads this.
                    label.setProperty(FULL_LABEL, label.text())
                    label.setText(text)
            width = NUMBER_FIELD_MAX_WIDTH_PX if len(boxes) == 1 else VECTOR_FIELD_MAX_WIDTH_PX
            for box in boxes:
                style_number(box, unit if unit is not None and not box.suffix() else None, width)
                if len(boxes) > 1:  # several in a row may shrink below their widest value's width
                    box.setMinimumWidth(min(box.minimumSizeHint().width(), VECTOR_FIELD_MIN_WIDTH_PX))


# -- optional groups (UI overhaul M4a) --------------------------------------------

def _set_collapsed(group: QGroupBox, collapsed: bool) -> None:
    if collapsed:
        hidden = [child for child in group.findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly)
                  if not child.isWindow() and not child.isHidden()]
        for child in hidden:
            child.hide()
        group._sms_collapsed = hidden
    else:
        for child in getattr(group, "_sms_collapsed", []):
            child.show()
        group._sms_collapsed = []


def collapse_optional_groups(root: QWidget) -> None:
    """Every checkable group under ``root`` shows only its title while it is
    unticked, instead of every field greyed out at full size; ticked again,
    what it showed comes back."""
    for group in root.findChildren(QGroupBox):
        if not group.isCheckable() or getattr(group, "_sms_collapses", False):
            continue
        group._sms_collapses = True
        group.toggled.connect(lambda on, box=group: _set_collapsed(box, not on))
        if not group.isChecked():
            _set_collapsed(group, True)


def finish_form(root: QWidget) -> None:
    """The form rules of M4a and of the UI audit's B6 for everything under
    ``root``: units as the fields' suffixes (:func:`units_into_fields`),
    optional groups that collapse when off (:func:`collapse_optional_groups`),
    fields at their widths and buttons at their own (:func:`limit_field_widths`),
    and one label column for every form under ``root`` (:class:`FormGrid`)."""
    units_into_fields(root)
    collapse_optional_groups(root)
    limit_field_widths(root)
    FormGrid.of(root)


# -- field widths and the form grid (UI audit UI-26) ------------------------------

def _in_item_view(widget: QWidget, root: QWidget) -> bool:
    """Whether ``widget`` is an item view's editor or part of a spin box or
    combo box (its line edit), not a field of the form."""
    parent = widget.parentWidget()
    while parent is not None and parent is not root:
        if isinstance(parent, (QAbstractItemView, QAbstractSpinBox, QComboBox)):
            return True
        parent = parent.parentWidget()
    return False


def _holding_layout(widget: QWidget) -> QLayout | None:
    """The layout that holds ``widget``: its parent's layout or one nested in it."""
    parent = widget.parentWidget()
    layout = parent.layout() if parent is not None else None
    if layout is None:
        return None
    pending = [layout]
    while pending:
        current = pending.pop()
        if current.indexOf(widget) >= 0:
            return current
        pending += current.findChildren(QLayout, options=_DIRECT)
    return None


def limit_field_widths(root: QWidget) -> None:
    """Every field under ``root`` at its width (UI audit UI-26): a drop-down
    list at most :data:`CHOICE_FIELD_MAX_WIDTH_PX`, a number at most
    :data:`NUMBER_FIELD_MAX_WIDTH_PX` (a row of several keeps its own,
    smaller limit), and a button alone in a row of a form or a column at
    its own width, at the left, never stretched across the page."""
    for combo in root.findChildren(QComboBox):
        if not _in_item_view(combo, root) and combo.maximumWidth() > CHOICE_FIELD_MAX_WIDTH_PX:
            combo.setMaximumWidth(CHOICE_FIELD_MAX_WIDTH_PX)
    for box in root.findChildren(QAbstractSpinBox):
        if not _in_item_view(box, root) and box.maximumWidth() > NUMBER_FIELD_MAX_WIDTH_PX:
            box.setMaximumWidth(NUMBER_FIELD_MAX_WIDTH_PX)
    for button in root.findChildren(QPushButton):
        if _in_item_view(button, root) or isinstance(button.parentWidget(), QDialogButtonBox):
            continue
        layout = _holding_layout(button)
        column = isinstance(layout, QBoxLayout) and layout.direction() in (QBoxLayout.Direction.TopToBottom,
                                                                           QBoxLayout.Direction.BottomToTop)
        if isinstance(layout, QFormLayout) or column:
            button.setSizePolicy(QSizePolicy.Policy.Maximum, button.sizePolicy().verticalPolicy())
            if column:
                layout.setAlignment(button, Qt.AlignmentFlag.AlignLeft)


def _shown_in(widget: QWidget, root: QWidget) -> bool:
    return widget is root or (widget.isVisible() and root.isAncestorOf(widget))


def grid_forms(root: QWidget) -> list:
    """The forms under ``root`` that share its label column: every shown
    :class:`QFormLayout`, but one inside another form's field (its rows are
    a part of that field)."""
    forms = [form for form in root.findChildren(QFormLayout)
             if form.parentWidget() is not None and _shown_in(form.parentWidget(), root)]
    fields = set()
    for form in forms:
        for roles in form_rows(form).values():
            field = roles.get(QFormLayout.ItemRole.FieldRole)
            if isinstance(field, QWidget):
                fields.add(id(field))
    top = []
    for form in forms:
        widget, nested = form.parentWidget(), False
        while widget is not None and widget is not root:
            if id(widget) in fields:
                nested = True
                break
            widget = widget.parentWidget()
        if not nested:
            top.append(form)
    return top


def grid_labels(form: QFormLayout) -> list:
    """``form``'s shown row labels: the labels and the check boxes (a
    parameter's "include" box) in its label column."""
    labels = []
    for roles in form_rows(form).values():
        label = roles.get(QFormLayout.ItemRole.LabelRole)
        if isinstance(label, (QLabel, QCheckBox)) and not label.isHidden():
            labels.append(label)
    return labels


class FormGrid(QObject):
    """One label column for every form on a page (UI audit UI-26): the
    fields of all the forms under ``root`` start at one x, whatever group
    or section a form sits in. The column is as wide as the page's longest
    label needs; each form's labels are widened to reach it. It follows
    the page: a section built, a group opened or a row shown lines up again
    (on the next turn of the event loop, after the layouts have settled).
    :meth:`of` gives a page its grid once."""

    def __init__(self, root: QWidget) -> None:
        super().__init__(root)
        self.root = root
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(0)
        self._timer.timeout.connect(self.align)
        self._mark = f"sms_form_grid_{id(self)}"  # set on each widget this grid watches
        self._watch(root)

    @classmethod
    def of(cls, root: QWidget) -> FormGrid:
        grid = root.findChild(FormGrid, options=_DIRECT)
        return grid if grid is not None else cls(root)

    def _watch(self, widget: QWidget) -> None:
        if not widget.property(self._mark):
            widget.setProperty(self._mark, True)
            widget.installEventFilter(self)

    def eventFilter(self, _watched, event):  # noqa: N802 -- Qt API name
        if event.type() in (QEvent.Type.Show, QEvent.Type.Resize, QEvent.Type.LayoutRequest):
            self._timer.start()
        return False

    @staticmethod
    def _natural(label: QWidget) -> int:
        """[px] the width ``label`` needs on one line; a text label's at most
        the label column's limit (``theme.LABEL_COLUMN_MAX_PX``: it wraps)."""
        if not isinstance(label, QLabel):
            return label.sizeHint().width()
        return min(label.fontMetrics().horizontalAdvance(label.text()) + 2 * label.margin() + 1, LABEL_COLUMN_MAX_PX)

    def column_x(self) -> int | None:
        """[px] where the fields start, in ``root``'s coordinates; None
        without a shown form row."""
        needed = None
        for form in grid_forms(self.root):
            labels = grid_labels(form)
            if not labels:
                continue
            left = _form_left(form, self.root)
            widest = max(self._natural(label) for label in labels)
            x = left + widest + max(form.horizontalSpacing(), 0)
            needed = x if needed is None else max(needed, x)
        return needed

    def outer(self) -> bool:
        """Whether no widget above ``root`` has a grid of its own: a grid
        inside another's page (a widget that finished its own form) leaves
        the line-up to the page's."""
        widget = self.root.parentWidget()
        while widget is not None:
            if widget.findChild(FormGrid, options=_DIRECT) is not None:
                return False
            widget = widget.parentWidget()
        return True

    def align(self) -> None:
        """Widen each form's labels so that its fields start at the page's one x."""
        if not self.root.isVisible() or not self.outer():
            return
        forms = grid_forms(self.root)
        for form in forms:
            self._watch(form.parentWidget())
        column = self.column_x()
        if column is None:
            return
        for form in forms:
            width = max(column - _form_left(form, self.root) - max(form.horizontalSpacing(), 0), 0)
            for label in grid_labels(form):
                # A label longer than the column wraps onto a second line.
                if (isinstance(label, QLabel) and not label.wordWrap()
                        and label.fontMetrics().horizontalAdvance(label.text()) > width):
                    label.setWordWrap(True)
                if label.minimumWidth() != width or label.maximumWidth() != width:
                    label.setFixedWidth(width)


def _form_left(form: QFormLayout, root: QWidget) -> int:
    """[px] the left edge of ``form``'s label column, in ``root``'s coordinates."""
    rect = form.contentsRect()
    return form.parentWidget().mapTo(root, QPoint(rect.x(), rect.y())).x()


def set_off_reason(widget: QWidget, enabled: bool, reason: str) -> None:
    """Enable or disable ``widget``; while it is off its tooltip says why
    and what turns it on (``reason``), before its own tooltip (UI audit
    UI-42). On again, it shows its own tooltip alone."""
    if widget.property("sms_own_tip") is None:
        widget.setProperty("sms_own_tip", widget.toolTip())
    own = widget.property("sms_own_tip") or ""
    widget.setEnabled(enabled)
    widget.setToolTip(own if enabled else (f"{reason}\n\n{own}" if own else reason))


def own_tooltip(widget: QWidget, tip: str) -> None:
    """Set the tooltip ``widget`` shows while it is on (see :func:`set_off_reason`)."""
    widget.setProperty("sms_own_tip", tip)
    if widget.isEnabled():
        widget.setToolTip(tip)


def flow_row(*widgets: QWidget, spacing: int = 6) -> QWidget:
    """``widgets`` side by side, wrapping onto the next line when the page is
    narrower than the row (a row of buttons or boxes that once made a page
    scroll sideways). ``spacing`` in px."""
    from .flow_layout import FlowLayout

    holder = QWidget()
    flow = FlowLayout(holder, spacing=spacing)
    for widget in widgets:
        flow.addWidget(widget)
    return holder


# -- controls for commands (UI audit UI-11) ----------------------------------------------------

class ActionButton(QPushButton):
    """A framed push button for a command of the window's registry
    (``action``): its text (or ``text``), tooltip (the shortcut in it),
    enabled and checked state follow the action, and a click triggers it.
    A secondary button: the one accent of a view is its primary action.
    ``defaultAction()`` gives the action, as a tool button's does."""

    def __init__(self, action: QAction, text: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._action = action
        self._text = text
        self.clicked.connect(self._on_clicked)
        action.changed.connect(self._follow)
        self._follow()

    def defaultAction(self) -> QAction:  # noqa: N802 -- as QToolButton's
        return self._action

    def _follow(self) -> None:
        action = self._action
        if not isValid(action) or not isValid(self):
            return  # the window is closing: the action went first
        self.setText(self._text if self._text is not None else action.text())
        self.setToolTip(action.toolTip())
        self.setAccessibleName(action.text().replace("&", ""))
        self.setEnabled(action.isEnabled())
        self.setCheckable(action.isCheckable())
        self.setChecked(action.isChecked())

    def _on_clicked(self) -> None:
        action = self._action
        group = action.actionGroup()
        if not (action.isCheckable() and action.isChecked() and group is not None and group.isExclusive()):
            action.trigger()  # a choice chosen again stays chosen
        self._follow()


class ActionCheckBox(QCheckBox):
    """A check box for an on/off command (a checkable ``action``): ticked
    while the action is on, and a click turns it on or off as its shortcut
    and menu item do (``trigger``: a dock's own toggle acts on that). The
    label is ``text`` (else the action's); the tooltip is the action's,
    with its shortcut. ``defaultAction()`` gives the action."""

    def __init__(self, action: QAction, text: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._action = action
        self._text = text
        self.clicked.connect(self._on_clicked)
        action.changed.connect(self._follow)
        self._follow()

    def defaultAction(self) -> QAction:  # noqa: N802 -- as QToolButton's
        return self._action

    def _follow(self) -> None:
        action = self._action
        if not isValid(action) or not isValid(self):
            return  # the window is closing: the action went first
        self.setText(self._text if self._text is not None else action.text().replace("&", ""))
        self.setToolTip(action.toolTip())
        self.setEnabled(action.isEnabled())
        self.setChecked(action.isChecked())

    def _on_clicked(self, checked: bool) -> None:
        if self._action.isChecked() != checked:
            self._action.trigger()
        self._follow()


class SegmentedControl(QFrame):
    """One choice of a few, side by side, the chosen one raised (the
    ``segmentedControl`` look of Form · JSON and the run mode). Each
    segment is a command (:meth:`add_action`): an :class:`ActionButton`
    of a checkable action, so the segment chosen follows the action
    however it is chosen (its shortcut, the menu, the palette). The
    segments are an exclusive group: one Tab stop, the arrows move in it,
    as in the other segmented controls. ``name`` is the control's
    accessible name ("Theme")."""

    def __init__(self, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("segmentedControl")
        self.setAccessibleName(name)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(0, 0, 0, 0)
        self._row.setSpacing(0)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.segments: list[ActionButton] = []

    def add_action(self, action: QAction, text: str) -> ActionButton:
        """A segment labelled ``text`` for the checkable ``action``."""
        segment = ActionButton(action, text)
        segment.setObjectName("segmentButton")
        self.group.addButton(segment)
        self._row.addWidget(segment)
        self.segments.append(segment)
        return segment


class EmptyState(QWidget):
    """What an empty view or list says: a title, a line of text and, when
    there is one, the action that fills it. The one empty state of the GUI
    (UI audit UI-05, UI-15): every view, list and panel with nothing to
    show uses it.

    The full form sits in the middle of its area, its title a section
    title. ``compact``: a short form for a panel, a short list or the room
    beside a table (UI-21): left-aligned, as tall as its lines, its title a
    heading. :meth:`add_action` adds a second or third button beside the
    first, :meth:`add_detail` a widget under the text (a short list of
    reasons). ``text()`` gives the title and the text as lines, for tests
    and for copying."""

    def __init__(self, title: str, text: str = "", action: str | None = None, primary: bool = False,
                 parent: QWidget | None = None, compact: bool = False) -> None:
        super().__init__(parent)
        self.compact = compact
        align = Qt.AlignmentFlag.AlignLeft if compact else Qt.AlignmentFlag.AlignHCenter
        layout = QVBoxLayout(self)
        margin = SPACE["sm"] if compact else SPACE["lg"]
        layout.setContentsMargins(margin, margin, margin, margin)
        layout.setSpacing(SPACE["sm"])
        if not compact:
            layout.addStretch(1)
        self.title_label = set_role(QLabel(title), role="heading" if compact else "section-title")
        self.title_label.setAlignment(align)
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        self.text_label = set_role(QLabel(text), tone="secondary")
        self.text_label.setAlignment(align)
        self.text_label.setWordWrap(True)
        self.text_label.setVisible(bool(text))
        layout.addWidget(self.text_label)
        self._details = QVBoxLayout()
        self._details.setSpacing(SPACE["xs"])
        layout.addLayout(self._details)
        self._buttons = QHBoxLayout()
        self._buttons.setSpacing(SPACE["sm"])
        if not compact:
            self._buttons.addStretch(1)
        self.button = QPushButton(action or "")
        if primary:
            set_role(self.button, variant="primary")
        self.button.setVisible(action is not None)
        self._buttons.addWidget(self.button)
        self._buttons.addStretch(1)
        layout.addLayout(self._buttons)
        layout.addStretch(1)  # compact: the lines stay at the top when a stack gives it more room
        if compact:
            self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

    def set_text(self, title: str, text: str = "", action: str | None = None) -> None:
        """A new title and text; ``action`` names the button, None hides it."""
        self.title_label.setText(title)
        self.text_label.setText(text)
        self.text_label.setVisible(bool(text))
        if action is not None:
            self.button.setText(action)
        self.button.setVisible(action is not None)

    def add_action(self, text: str) -> QPushButton:
        """A further button beside the first; the caller connects it."""
        button = QPushButton(text)
        self._buttons.insertWidget(self._buttons.count() - 1, button)
        return button

    def add_detail(self, widget: QWidget) -> QWidget:
        """``widget`` under the text (a short list of reasons, a note). In
        the full form it takes the middle three fifths of the width, so its
        lines wrap there and are never cut."""
        if self.compact:
            self._details.addWidget(widget)
            return widget
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(widget, 3)
        row.addStretch(1)
        self._details.addLayout(row)
        return widget

    def text(self) -> str:
        """The title and the text shown, one per line."""
        return "\n".join(label.text() for label in (self.title_label, self.text_label) if label.text())


class EmptyStack(QStackedWidget):
    """A list, tree or table view, or its :class:`EmptyState` while the
    view has no row (UI audit UI-05): never a blank box over the buttons.

    ``fit_rows``: the stack is as tall as the view's rows (a short list
    does not fill the page with blank rows) and as tall as the empty
    state while there are none; the owner puts a stretch below it. A view
    whose emptiness is not its row count (a search that hides every row)
    calls :meth:`refresh` with ``empty``.

    :meth:`hide_while_empty`: the owner's list buttons that the empty
    state's own action stands in for (Add) or that need a row (Edit,
    Remove) are hidden while it shows, so the page has one Add, not two."""

    def __init__(self, view: QAbstractItemView, empty: EmptyState, fit_rows: bool = False,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.view = view
        self.empty = empty
        self.fit_rows = fit_rows
        self._hidden_while_empty: tuple[QWidget, ...] = ()
        self._empty: bool | None = None  # what the owner said last; None: the row count
        self.addWidget(view)
        self.addWidget(empty)
        model = view.model()
        for signal in (model.rowsInserted, model.rowsRemoved, model.modelReset, model.layoutChanged):
            signal.connect(self._rows_changed)
        self.refresh()

    def _rows_changed(self, *_args) -> None:
        self.refresh(self._empty)

    def showing_empty(self) -> bool:
        return self.currentWidget() is self.empty

    def hide_while_empty(self, *widgets: QWidget) -> None:
        """``widgets`` hidden while the empty state shows, shown with the view."""
        self._hidden_while_empty = widgets
        self.refresh(self._empty)

    def refresh(self, empty: bool | None = None) -> None:
        """The empty state when ``empty`` (None: when the view has no row),
        else the view; with ``fit_rows`` the height follows."""
        self._empty = empty
        if empty is None:
            empty = self.view.model().rowCount() == 0
        self.setCurrentWidget(self.empty if empty else self.view)
        for widget in self._hidden_while_empty:
            widget.setHidden(empty)
        if self.fit_rows:
            self.setMaximumHeight(self.empty.sizeHint().height() if empty else self._rows_height())

    def _rows_height(self) -> int:
        """[px] the view's rows, its header and its frame."""
        view = self.view
        rows = view.model().rowCount()
        height = 2 * view.frameWidth()
        if isinstance(view, QTableView):
            if view.horizontalHeader().isVisible():
                height += view.horizontalHeader().sizeHint().height()
            height += sum(view.rowHeight(row) for row in range(rows))
        else:
            height += sum(max(view.sizeHintForRow(row), 0) for row in range(rows))
        if view.horizontalScrollBar().isVisible():
            height += view.horizontalScrollBar().sizeHint().height()
        return max(height, view.minimumSizeHint().height())

    def showEvent(self, event) -> None:  # noqa: N802 -- Qt's name
        super().showEvent(event)
        self.refresh(self._empty)  # the rows' height once the style's font is known


class ScrollBody(QScrollArea):
    """A dialog's body that scrolls when the screen is too small for it
    (UI audit UI-01): it asks for the whole size of its content, so the
    dialog opens as large as before, but its minimum height is small, so
    the dialog fits the screen (``theme.dialogs``) with its buttons in
    view. Its minimum width is the content's, so it never scrolls
    sideways."""

    def __init__(self, widget: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(widget)

    def _bar_width(self) -> int:
        return self.verticalScrollBar().sizeHint().width() + 2 * self.frameWidth()

    def sizeHint(self) -> QSize:  # noqa: N802 -- Qt's name
        widget = self.widget()
        if widget is None:
            return super().sizeHint()
        hint = widget.sizeHint()
        return QSize(hint.width() + self._bar_width(), hint.height() + 2 * self.frameWidth())

    def minimumSizeHint(self) -> QSize:  # noqa: N802 -- Qt's name
        widget = self.widget()
        if widget is None:
            return super().minimumSizeHint()
        return QSize(widget.minimumSizeHint().width() + self._bar_width(), super().minimumSizeHint().height())


class RowHeightDelegate(QStyledItemDelegate):
    """Rows at least the theme's table-row height (:data:`theme.ROW_HEIGHT`)
    in a list or tree view."""

    def sizeHint(self, option, index) -> QSize:  # noqa: N802 -- Qt's name
        return super().sizeHint(option, index).expandedTo(QSize(0, ROW_HEIGHT))


def set_table_look(view: QTableView, numeric=(), rows: bool = True, docked: bool = False) -> QTableView:
    """The look of a :class:`gui.data_table.DataTable` for a table built
    another way (a ``QTableWidget``, a view over its own model; UI audit
    B9): no grid lines (surfaces, not lines), headings on the left and a
    numeric column's on the right (``numeric``, a ``QTableWidget``'s
    columns; a model aligns its own), rows at the table-row height
    (``rows``; not for a table with controls in its cells), and no frame of
    its own when it fills a dock or a panel (``docked``). Returns ``view``."""
    view.setShowGrid(False)
    header = view.horizontalHeader()
    header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    item_of = getattr(view, "horizontalHeaderItem", None)
    for column in numeric:
        item = item_of(column) if item_of is not None else None
        if item is not None:
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    if rows:
        view.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
    if docked:
        set_role(view, role="docked")
    return view
