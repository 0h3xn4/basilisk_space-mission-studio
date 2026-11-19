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

"""Two small, reusable UX primitives, built once here and reused across
gui/ rather than re-invented per widget -- real user feedback ("make the
GUI more 'reactive'... the user always knows and understands what they
did. visual cues would help... currently, everything looks very raw and
unfinished"), and a follow-up survey of this app's own existing widgets
found the same two gaps repeating across most of them (add/remove
actions with no positive feedback beyond a list silently changing;
invalid input only ever caught by a blocking dialog at Save/Run time,
never at the specific field, at the moment it's typed):

* :func:`show_toast` -- a small, non-blocking, auto-dismissing
  notification, for "did my action actually do something" feedback on
  actions where a blocking ``QMessageBox`` would be overkill (Save, Add
  spacecraft, Remove sensor, ...) and a status-bar message alone is too
  easy to miss (a status-bar message is easily overwritten by the
  "Running..." message that follows moments later).
* :func:`report` -- a routine outcome (a file written, a file that could
  not be read, a launch that failed) said without a message box
  (docs/ux-audit.md U-39): a toast, the window's status bar, and for a
  warning or an error a line in the Log. Message boxes are kept for
  confirming what cannot be undone.
* :func:`show_dialog_error` -- a dialog's own error line, above its
  buttons, for input the dialog refuses on OK (U-39), instead of a box on
  top of the dialog.
* :func:`mark_invalid`/:func:`clear_invalid` -- inline, per-field
  validation feedback (a red border, via theme.py's own
  ``[state="error"]`` QSS rule, plus the reason as a tooltip), so a
  field the user is actively typing into can show it's wrong immediately
  rather than only at Save/Run time via a dialog that names the problem
  but not which of a dialog's many fields caused it.

Both are intentionally widget-library-free (no new PyPI dependency) --
plain ``QLabel``/dynamic-Qt-property mechanisms the Qt Style Sheets
system already documents, matching this project's own "no third-party
GUI-chrome dependency beyond PySide6 itself" precedent (see theme.py).
"""

from __future__ import annotations

import logging
import re

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPoint, QPropertyAnimation, QRect, Qt, QTimer, Signal
from PySide6.QtWidgets import (QAbstractButton, QAbstractSlider, QAbstractSpinBox, QBoxLayout, QComboBox,
                               QDialogButtonBox, QFormLayout, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
                               QLayout, QLineEdit, QMainWindow, QPushButton, QScrollArea, QScrollBar, QStackedWidget,
                               QTabBar, QTabWidget, QWidget)
from shiboken6 import isValid

from .theme import SPACE, TOAST, reduce_motion, set_role

# A toast's status tone per kind (theme/qss.py's QLabel[role="toast"]): the
# status's tinted background and outline, primary text.
_TOAST_KIND_TONES = {"success": "normal", "error": "critical", "info": "standby", "warning": "caution"}
_logger = logging.getLogger("spacemissionstudio.gui")
_REPORT_LOG_LEVELS = {"error": logging.ERROR, "warning": logging.WARNING, "info": logging.INFO,
                      "success": logging.INFO}
_REPORT_TOAST_MS = {"error": 6000, "warning": 6000, "info": 4500, "success": 3000}  # [ms]
_TOAST_STACK_ATTR = "_spacemissionstudio_active_toasts"
_TOAST_FILTER_ATTR = "_spacemissionstudio_toast_filter"
_TOAST_WATCH_MS = 150  # [ms] how often shown toasts check that they cover no control (UI audit UI-54)
TOAST_FADE_MS = 150  # [ms] in and out (the design's 120-180 ms); none with Settings > Reduce motion


class _Toast(QLabel):
    """Not meant to be constructed directly -- see :func:`show_toast`."""

    def __init__(self, parent: QWidget, message: str, kind: str) -> None:
        # A long path has no space to wrap at: a zero-width space after each
        # separator lets it wrap inside the toast's width (shown only; the
        # message itself is unchanged).
        super().__init__(re.sub(r"([/\\])", "\\1\u200b", message), parent)
        set_role(self, role="toast", tone=_TOAST_KIND_TONES.get(kind, "standby"))
        self.setWordWrap(True)
        self.setMaximumWidth(TOAST["max_width"])
        # It says something and has nothing to click: a click on it reaches what is under it (UI audit UI-54).
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # As wide as its text on one line, up to the most a toast takes; a longer text wraps. Qt's own
        # width for a wrapped label broke "New blank scenario" over two lines.
        self.ensurePolished()
        self.setWordWrap(False)
        one_line = self.sizeHint().width()  # [px] with its padding and edge
        self.setWordWrap(True)
        width = min(one_line, TOAST["max_width"])
        self.resize(width, self.heightForWidth(width))


def show_toast(window: QWidget, message: str, kind: str = "success", duration_ms: int = 2600) -> QLabel:
    """Shows ``message`` in a small notification anchored to the
    bottom-right corner of ``window`` (the app's top-level window, or any
    dialog), auto-dismissing after ``duration_ms``. In a main window it
    sits in the central area, above the status bar and beside or above any
    panel, and moves up past a control it would cover (UI audit UI-54):
    see :func:`toast_area`. A click on it reaches what is under it.
    ``kind`` is ``"success"`` (default), ``"error"``, ``"warning"`` or
    ``"info"`` -- picks the
    toast's colour from the theme's status tokens so it reads as part of the
    same themed system, not a visually foreign popup.

    Multiple toasts shown in quick succession (e.g. several list rows
    added back-to-back) stack upward rather than overlapping -- ``window``
    carries its own small list of currently-visible toasts
    (a plain attribute, not a class member, so this works on ANY QWidget
    without every window/dialog that wants toasts needing to inherit from
    a shared base class). Returns the created ``QLabel`` -- mainly useful
    for tests; normal callers can ignore the return value.
    """
    stack: list[QLabel] = getattr(window, _TOAST_STACK_ATTR, None)
    if stack is None:
        stack = []
        setattr(window, _TOAST_STACK_ATTR, stack)

    toast = _Toast(window, message, kind)
    stack.append(toast)
    _follow_resizes(window)
    _reposition_toasts(window, stack)
    # Again once the window has laid out what the action changed (a page shown after its toast), and
    # while it shows (_ToastFollower).
    QTimer.singleShot(0, lambda: _reposition_toasts(window, stack) if isValid(window) else None)
    toast.show()
    toast.raise_()
    fades = not reduce_motion() and duration_ms > 2 * TOAST_FADE_MS
    if fades:
        _fade(toast, 0.0, 1.0, keep=False)

    def _fade_out() -> None:
        if isValid(toast) and toast.isVisible():
            _fade(toast, 1.0, 0.0, keep=True)
        QTimer.singleShot(TOAST_FADE_MS, _dismiss)

    def _dismiss() -> None:
        # The QTimer below can fire AFTER `window` (and so `toast`, its
        # child) was already destroyed -- e.g. the app/dialog was closed
        # while a toast was still showing, a real sequence several
        # existing tests hit (close a window right after an action that
        # shows a toast). shiboken6.isValid() is the documented way to
        # check whether a QObject's underlying C++ object is still alive
        # before touching it; skipping silently here is correct -- there
        # is nothing left to dismiss.
        if not isValid(toast):
            return
        if toast in stack:
            stack.remove(toast)
        # hide(), not deleteLater(): a caller that kept the QLabel
        # show_toast() returned (tests do) must not end up holding a
        # dangling C++ pointer once the auto-dismiss timer fires -- Qt's
        # normal parent-child ownership (toast's parent is `window`)
        # already cleans it up for real once `window` itself is
        # destroyed, so there is nothing to leak by not deleting sooner.
        toast.hide()
        if isValid(window):
            _reposition_toasts(window, stack)

    # The fade-out starts the dismissal: two timers of 2 s or more are
    # coarse (5 %), so a dismissal of its own could come first and skip it.
    if fades:  # faded out by the time it is dismissed
        QTimer.singleShot(duration_ms - TOAST_FADE_MS, _fade_out)
    else:
        QTimer.singleShot(duration_ms, _dismiss)
    return toast


def _fade(toast: QLabel, start: float, end: float, keep: bool) -> None:
    """Fade ``toast``'s opacity from ``start`` to ``end``; ``keep`` the
    effect after (a fade out), or drop it (drawn as before once in)."""
    effect = QGraphicsOpacityEffect(toast)
    effect.setOpacity(start)
    toast.setGraphicsEffect(effect)
    animation = QPropertyAnimation(effect, b"opacity", toast)
    animation.setDuration(TOAST_FADE_MS)
    animation.setStartValue(start)
    animation.setEndValue(end)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    if not keep:  # only its own effect: a stalled fade in can end after the fade out began
        animation.finished.connect(
            lambda: toast.setGraphicsEffect(None) if isValid(toast) and toast.graphicsEffect() is effect else None
        )
    animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)


def report(widget: QWidget | None, text: str, kind: str = "error") -> None:
    """Say ``text`` without a message box (U-39). The first line goes in a
    toast on ``widget``'s window (``kind`` "error", "warning", "info" or
    "success") and in its status bar; the whole text goes in the Log (an
    error or a warning at that level, the others as INFO), where it stays.
    With no widget, only the Log."""
    _logger.log(_REPORT_LOG_LEVELS.get(kind, logging.INFO), "%s", text)
    first = text.strip().splitlines()[0] if text.strip() else text
    if widget is None or not isValid(widget):
        return
    window = widget.window()
    shown = first + (" (more in the Log)" if "\n" in text.strip() and kind in ("error", "warning") else "")
    show_toast(window, shown, kind=kind, duration_ms=_REPORT_TOAST_MS.get(kind, 3000))
    if isinstance(window, QMainWindow):
        show_status(window, first)


_STATUS_TIP_FOR = "_smsStatusTipFor"  # the status-bar message whose tooltip the bar shows


def show_status(window: QMainWindow, text: str, tooltip: str = "") -> str:
    """Show ``text`` in ``window``'s status bar, elided in the middle to
    the room left of its permanent entries, so its end (a file name) stays
    in view and nothing is clipped at the first entry (UI audit UI-09).
    The bar's tooltip is ``tooltip``, or the whole text when it was
    elided, until another message replaces it. Returns the text shown."""
    bar = window.statusBar()
    shown = text
    if bar.isVisible():  # a hidden bar is not laid out: its width says nothing
        entries = [w for w in bar.findChildren(QWidget) if w.parent() is bar and w.isVisible()]
        room = bar.width() - sum(w.sizeHint().width() + SPACE["xs"] for w in entries) - SPACE["md"]  # [px]
        shown = bar.fontMetrics().elidedText(text, Qt.TextElideMode.ElideMiddle, max(room, 0))
    if bar.findChild(_StatusTips) is None:
        _StatusTips(bar)
    bar.setProperty(_STATUS_TIP_FOR, shown)
    bar.showMessage(shown)
    bar.setToolTip(tooltip or (text if shown != text else ""))
    return shown


class _StatusTips(QObject):
    """Clears a status bar's tooltip when another message replaces the
    one it belongs to (:func:`show_status`). A child of the bar, so it
    holds no reference to the window."""

    def __init__(self, bar: QWidget) -> None:
        super().__init__(bar)
        bar.messageChanged.connect(self._forget)

    def _forget(self, message: str) -> None:
        bar = self.parent()
        if message != bar.property(_STATUS_TIP_FOR):
            bar.setProperty(_STATUS_TIP_FOR, None)
            bar.setToolTip("")


_DIALOG_ERROR_NAME = "dialogError"


def show_dialog_error(dialog: QWidget, text: str) -> QLabel:
    """Show ``text`` in ``dialog``'s error line, made the first time just
    above its button box (or at the end of its layout), and keep the
    dialog open (U-39). Cleared by :func:`clear_dialog_error`."""
    label = dialog.findChild(QLabel, _DIALOG_ERROR_NAME)
    if label is None:
        label = QLabel(dialog)
        label.setObjectName(_DIALOG_ERROR_NAME)
        label.setWordWrap(True)
        set_role(label, tone="critical")
        layout = dialog.layout()
        if layout is not None:
            buttons = dialog.findChild(QDialogButtonBox)
            index = layout.indexOf(buttons) if buttons is not None else -1
            if isinstance(layout, QBoxLayout) and index >= 0:
                layout.insertWidget(index, label)
            elif isinstance(layout, QFormLayout):
                layout.addRow(label)
            else:
                layout.addWidget(label)
    label.setText(text)
    label.setToolTip(text)
    label.show()
    return label


def dialog_error_text(dialog: QWidget) -> str:
    """The text of ``dialog``'s error line, "" when it has none showing."""
    label = dialog.findChild(QLabel, _DIALOG_ERROR_NAME)
    return label.text() if label is not None and not label.isHidden() else ""


def clear_dialog_error(dialog: QWidget) -> None:
    label = dialog.findChild(QLabel, _DIALOG_ERROR_NAME)
    if label is not None:
        label.clear()
        label.hide()


def toast_area(window: QWidget) -> QRect:
    """Where ``window``'s toasts may sit, in its coordinates: a main
    window's central area, so never over the menu and top bar, a panel
    (the Inspector, Problems) or the status bar (UI audit UI-54); any other
    window's whole rectangle."""
    central = window.centralWidget() if isinstance(window, QMainWindow) else None
    if central is not None and central.isVisible():
        return QRect(central.mapTo(window, QPoint(0, 0)), central.size())
    area = window.rect()
    status_bar = window.statusBar() if isinstance(window, QMainWindow) else None
    if status_bar is not None and status_bar.isVisible():
        area.setBottom(status_bar.mapTo(window, QPoint(0, 0)).y() - 1)
    return area


# The controls a toast does not cover (UI audit UI-54): what a user clicks or
# types in. Views, text areas and plots are areas, not controls; scroll bars
# are at every page's edge, and a click on a toast reaches them anyway.
_CONTROLS = (QAbstractButton, QComboBox, QLineEdit, QAbstractSpinBox, QAbstractSlider, QTabBar)


def _is_control(widget: QWidget) -> bool:
    if isinstance(widget, QScrollBar):
        return False
    if isinstance(widget, _CONTROLS):
        return True
    return isinstance(widget, QLabel) and "<a " in widget.text()  # a label with a link


def _controls_in(window: QWidget, strip: QRect, skip: list) -> list[QRect]:
    """The rectangles (``window``'s coordinates) of the shown controls that
    meet ``strip``. A hidden widget's children are skipped, and so is a
    widget outside the strip: Qt clips children to their parent."""
    found: list[QRect] = []
    pending = [child for child in window.children() if isinstance(child, QWidget)]
    while pending:
        widget = pending.pop()
        if widget in skip or not widget.isVisible() or widget.isWindow():
            continue
        rect = QRect(widget.mapTo(window, QPoint(0, 0)), widget.size())
        if not rect.intersects(strip):
            continue
        if _is_control(widget):
            found.append(rect.adjusted(-SPACE["xs"], -SPACE["xs"], SPACE["xs"], SPACE["xs"]))  # not touching it
            continue
        pending.extend(child for child in widget.children() if isinstance(child, QWidget))
    return found


def _reposition_toasts(window: QWidget, stack: list[QLabel]) -> None:
    """Lay the toasts out at the bottom right of :func:`toast_area`, the
    newest lowest, :data:`theme.TOAST` apart; the whole stack moves up,
    4 px at a time, until it covers no control (or, with no such place,
    stays at the bottom)."""
    shown = [toast for toast in stack if isValid(toast)]
    if not shown:
        return
    area = toast_area(window)
    margin, gap = TOAST["margin"], TOAST["gap"]
    width = max(toast.width() for toast in shown)
    height = sum(toast.height() for toast in shown) + gap * (len(shown) - 1)
    right = area.right() - margin
    strip = QRect(right - width + 1, area.top(), width, area.height())
    controls = _controls_in(window, strip, shown)
    lowest = area.bottom() - margin - height + 1
    top = lowest
    while top > area.top() + margin and any(c.intersects(QRect(strip.left(), top, width, height)) for c in controls):
        top -= SPACE["xs"]
    if top <= area.top() + margin:
        top = lowest  # nowhere free: the bottom, where a click still goes through it
    y = top + height
    for toast in reversed(shown):
        y -= toast.height()
        toast.move(right - toast.width() + 1, y)
        y -= gap


class _ToastFollower(QObject):
    """Moves a window's toasts when the window or its central area changes
    size (a panel shown or hidden) and, while any shows, when what is under
    them changes (a page laid out or scrolled after its toast): every
    :data:`_TOAST_WATCH_MS`, about a millisecond each time.

    It keeps no Python attribute. It is a child of its window and an event
    filter on it, and its only Python reference is an attribute of the
    window, so Qt can call it after its Python wrapper has gone (a window
    torn down, a test's window collected): a new wrapper then has none of
    the old one's attributes. So it reads its window from its parent and
    keeps its timer's id in a Qt property, and its timer is its own
    (``timerEvent``), not a connection to a method of the old wrapper."""

    _TIMER_PROPERTY = "toastWatchTimer"

    def __init__(self, window: QWidget) -> None:
        super().__init__(window)

    def watched_window(self) -> QWidget | None:
        window = self.parent()
        return window if isinstance(window, QWidget) and isValid(window) else None

    def watch(self) -> None:
        """Check the toasts' place every :data:`_TOAST_WATCH_MS` while one shows."""
        if not self.property(self._TIMER_PROPERTY):
            self.setProperty(self._TIMER_PROPERTY, self.startTimer(_TOAST_WATCH_MS))

    def stop(self) -> None:
        timer = self.property(self._TIMER_PROPERTY)
        if timer:
            self.killTimer(int(timer))
        self.setProperty(self._TIMER_PROPERTY, 0)

    def is_watching(self) -> bool:
        return bool(self.property(self._TIMER_PROPERTY))

    def reposition(self) -> None:
        window = self.watched_window()
        stack = getattr(window, _TOAST_STACK_ATTR, None) if window is not None else None
        if stack:
            _reposition_toasts(window, stack)
        else:
            self.stop()

    def timerEvent(self, _event) -> None:  # noqa: N802 -- Qt API name
        self.reposition()

    def eventFilter(self, _watched, event) -> bool:  # noqa: N802 -- Qt API name
        if event.type() == QEvent.Type.Resize:
            self.reposition()
        return False


def _follow_resizes(window: QWidget) -> None:
    follower = getattr(window, _TOAST_FILTER_ATTR, None)
    if follower is not None and isValid(follower):
        follower.watch()
        return
    follower = _ToastFollower(window)
    follower.watch()
    setattr(window, _TOAST_FILTER_ATTR, follower)
    window.installEventFilter(follower)
    central = window.centralWidget() if isinstance(window, QMainWindow) else None
    if central is not None:
        central.installEventFilter(follower)


_ERROR_STATE_PROPERTY = "state"
_ERROR_STATE_VALUE = "error"
_SAVED_TOOLTIP_PROPERTY = "_feedback_saved_tooltip"


def mark_invalid(widget: QWidget, message: str, warning: bool = False) -> None:
    """Flags ``widget`` (a ``QLineEdit``/``QDoubleSpinBox``/``QSpinBox``/
    ``QComboBox``) as holding an invalid value -- a red border (theme.py's
    ``[state="error"]`` QSS rule) plus ``message`` as its tooltip, so the
    user sees WHICH field is wrong and WHY without waiting for a blocking
    Save/Run dialog. Does not clear itself -- call :func:`clear_invalid`
    once the field holds an acceptable value again (typically wired to
    that widget's own ``textChanged``/``valueChanged`` signal).

    Stashes whatever tooltip the widget already had (if any, and if this
    isn't already a repeat ``mark_invalid`` call) in a dynamic property so
    :func:`clear_invalid` can restore it afterwards, instead of just
    blanking it -- every call site today happens to set no tooltip of its
    own first, so this is currently latent, but a future widget with a
    real, static tooltip (e.g. a units hint) would otherwise lose it
    permanently the first time validation ever flagged that field.
    """
    if not widget.property(_ERROR_STATE_PROPERTY):
        widget.setProperty(_SAVED_TOOLTIP_PROPERTY, widget.toolTip())
    # ``warning``: a value to look at, not one that blocks (the warning outline).
    widget.setProperty(_ERROR_STATE_PROPERTY, "warning" if warning else _ERROR_STATE_VALUE)
    widget.setToolTip(message)
    _repolish(widget)


def clear_invalid(widget: QWidget) -> None:
    """Undoes :func:`mark_invalid` -- a no-op if the widget wasn't
    marked, so this is always safe to call unconditionally (e.g. at the
    top of a field's change handler, before re-validating). Restores
    whatever tooltip the widget had before :func:`mark_invalid` was first
    called, rather than always blanking it.
    """
    if widget.property(_ERROR_STATE_PROPERTY):
        widget.setProperty(_ERROR_STATE_PROPERTY, "")
        widget.setToolTip(widget.property(_SAVED_TOOLTIP_PROPERTY) or "")
        widget.setProperty(_SAVED_TOOLTIP_PROPERTY, None)
        _repolish(widget)


# The attribute show_field_error keeps a field's message label in.
_FIELD_ERROR_ATTR = "_smsFieldErrorLabel"


def _error_label(widget: QWidget):
    label = getattr(widget, _FIELD_ERROR_ATTR, None)
    return label if label is not None and isValid(label) else None


def _find_in_forms(layout, widget: QWidget):
    """``(form, row)`` for ``widget`` in ``layout`` or the layouts nested in
    it, or None."""
    if isinstance(layout, QFormLayout):
        row, _role = layout.getWidgetPosition(widget)
        if row >= 0:
            return layout, row
    # Nested layouts as QObjects, not through itemAt(): see widgets.layout_widgets.
    for child in layout.findChildren(QLayout, options=Qt.FindChildOption.FindDirectChildrenOnly) if layout else []:
        found = _find_in_forms(child, widget)
        if found is not None:
            return found
    return None


def _form_row(widget: QWidget):
    """``(form, row, field)``: the QFormLayout row holding ``widget`` (or
    the row widget it sits in, up to three parents up), or None."""
    field = widget
    for _level in range(4):
        parent = field.parentWidget()
        if parent is None:
            return None
        found = _find_in_forms(parent.layout(), field)
        if found is not None:
            return found[0], found[1], field
        field = parent
    return None


def row_label(widget: QWidget) -> str:
    """The label of the form row holding ``widget``, also in a layout
    nested in its form ("" when there is none), with the unit the form
    moved into the field."""
    found = _form_row(widget)
    if found is None:
        return ""
    form, _row, field = found
    label = form.labelForField(field)
    if not isinstance(label, QLabel):
        return ""
    # With its unit, as the code names it ("Dry mass [kg]"): the form shows
    # the unit in the field (widgets.units_into_fields, M4a).
    text = label.property("sms_full_label") or label.text()
    return text.rstrip(":").strip()


def show_field_error(widget: QWidget, message: str, warning: bool = False) -> None:
    """Marks ``widget`` (see :func:`mark_invalid`) and shows ``message``
    right under it (docs/ux-audit.md U-12): under its row in a form, or
    after it in its own box layout. Calling it again updates the message.
    ``warning`` marks a value to look at rather than an error."""
    mark_invalid(widget, message, warning)
    label = _error_label(widget)
    if label is not None:
        label.setText(message)
        label.setObjectName("fieldWarning" if warning else "fieldError")
        _repolish(label)
        return
    label = QLabel(message)
    label.setObjectName("fieldWarning" if warning else "fieldError")
    label.setWordWrap(True)
    placed = _form_row(widget)
    if placed is not None:
        form, row, _field = placed
        form.insertRow(row + 1, "", label)
    else:
        parent = widget.parentWidget()
        layout = parent.layout() if parent is not None else None
        if not isinstance(layout, QBoxLayout) or layout.indexOf(widget) < 0:
            label.deleteLater()  # nowhere to put it: the border and tooltip still say it
            return
        layout.insertWidget(layout.indexOf(widget) + 1, label)
    setattr(widget, _FIELD_ERROR_ATTR, label)


def clear_field_error(widget: QWidget) -> None:
    """Undoes :func:`show_field_error`; safe to call on any widget."""
    clear_invalid(widget)
    label = _error_label(widget)
    setattr(widget, _FIELD_ERROR_ATTR, None)
    if label is None:
        return
    placed = _form_row(label)
    if placed is not None:
        placed[0].removeRow(placed[1])  # deletes the label and its empty row label
    else:
        label.deleteLater()


def clear_on_edit(widget: QWidget) -> None:
    """Clears ``widget``'s :func:`show_field_error` the first time the user
    changes its value: in a dialog nothing revalidates until OK."""
    for name in ("valueChanged", "textChanged", "currentIndexChanged", "itemChanged"):
        signal = getattr(widget, name, None)
        if signal is None:
            continue

        def clear(*_args, _signal=signal):
            clear_field_error(widget)
            _signal.disconnect(clear)

        signal.connect(clear)
        return


def field_error_text(widget: QWidget) -> str:
    """The message :func:`show_field_error` shows under ``widget``, or ""."""
    label = _error_label(widget)
    return label.text() if label is not None else ""


def bring_into_view(widget: QWidget) -> None:
    """Selects every tab and stacked page ``widget`` sits in, scrolls it into
    view, and focuses it: where Problems sends the user (U-12)."""
    child = widget
    parent = widget.parentWidget()
    while parent is not None:
        if isinstance(parent, QStackedWidget) and parent.indexOf(child) >= 0:
            container = parent.parentWidget()
            if isinstance(container, QTabWidget):
                container.setCurrentWidget(child)
            else:
                parent.setCurrentWidget(child)
        if isinstance(parent, QScrollArea) and parent.widget() is not None:
            parent.ensureWidgetVisible(widget)
        child, parent = parent, parent.parentWidget()
    widget.setFocus()


class ProblemBanner(QFrame):
    """A line at the top of a dialog opened at a problem: what is wrong,
    while the field itself is marked. Hidden until :meth:`show_problem`."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("problemBanner")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 8, 6)  # [px]
        self.label = QLabel()
        self.label.setWordWrap(True)
        layout.addWidget(self.label, 1)
        self.hide()

    def show_problem(self, message: str) -> None:
        self.label.setText(message)
        self.show()


def _repolish(widget: QWidget) -> None:
    """Qt caches a widget's QSS match against its dynamic properties --
    changing one (``state`` above) has no visible effect until the style
    is explicitly told to re-evaluate it (Qt docs, "Qt Style Sheets
    Reference" -> "Qt Style Sheets and Widget Style" -> "Dynamic
    Properties").
    """
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)


class StaleResultsBanner(QFrame):
    """A persistent notice above the run views when the results shown no
    longer match the scenario (UX/UI Standard, "State is always visible";
    docs/ux-audit.md U-20): it names what changed and offers **Re-run**.
    Hidden until :meth:`show_stale` is called; styled by theme.py's
    ``QFrame#staleResultsBanner`` rule."""

    rerun_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("staleResultsBanner")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 8, 6)  # [px]
        self.label = QLabel()
        self.label.setWordWrap(True)
        layout.addWidget(self.label, 1)
        self.rerun_button = QPushButton("Re-run")
        self.rerun_button.setToolTip("Run the scenario as it is now (Ctrl+R)")
        self.rerun_button.clicked.connect(self.rerun_requested)
        layout.addWidget(self.rerun_button)
        self.hide()

    def show_stale(self, scenario_valid: bool) -> None:
        if scenario_valid:
            self.label.setText("These results are from a previous version of this scenario. "
                               "Re-run to see the current one.")
        else:
            self.label.setText("These results are from a previous version of this scenario, "
                               "which now has a problem: fix it in the Scenario Editor, then re-run.")
        self.rerun_button.setEnabled(scenario_valid)
        self.show()
