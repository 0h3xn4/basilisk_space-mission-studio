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

"""Dialogs never cut off their own text, and always fit the screen.

Qt does not size a window by the height its wrapped labels need at the
window's width: a dialog with a word-wrapped label gets the height the
label would need on a squarer layout, and when the window manager makes
it wider or narrower than that, or the fonts differ from where it was
laid out, the lines below the first and the buttons are cut off (the
orbit-type switch, reported 2026-11-12). :func:`prepare`, called for
every :class:`QDialog` as Qt polishes it (:class:`theme.style.AppStyle`),
watches the dialog: when it is shown or its width changes, its minimum
height becomes what its layout needs at that width, and it grows to it.
A minimum height the dialog's own code set stays the floor.

The screen limits both (UI audit UI-01, UI-02): on a 1280 x 720 screen
the 3D model editor asked for 967 px and its OK and Cancel were off the
screen. A dialog is never made taller than :func:`room` (the screen
less its panels and the title bar), and a dialog shown taller than that
shrinks to it. Only the layout's own minimum can make it taller: tall
content goes in a scroll area, and ``tests/gui/test_dialogs_fit_the_screen.py``
checks every dialog at 1280 x 720.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QRect, QSize
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QDialog, QWidget

from .typography import SPACE

_ORIGINAL_MIN = "smsOwnMinimumHeight"
_WIDTH = "smsFittedWidth"
# [px] kept free above a dialog's own height: the window frame's title
# bar, which the dialog's height does not include, with a little to spare.
TITLE_BAR_ROOM = 2 * SPACE["xxl"]  # [px]


def prepare(dialog: QDialog) -> None:
    if dialog.property(_ORIGINAL_MIN) is not None:
        return
    dialog.setProperty(_ORIGINAL_MIN, dialog.minimumHeight())
    dialog.installEventFilter(_FitFilter.instance())


def available(widget: QWidget) -> QRect | None:
    """The screen area ``widget`` can use (without the desktop's panels),
    or None when there is no screen."""
    screen = widget.screen() or QGuiApplication.primaryScreen()
    return None if screen is None else screen.availableGeometry()


def room(widget: QWidget) -> QSize | None:
    """The largest size a window fits the screen at: the available area
    less the title bar (:data:`TITLE_BAR_ROOM`); None without a screen."""
    area = available(widget)
    if area is None or area.isEmpty():
        return None
    return QSize(area.width(), max(area.height() - TITLE_BAR_ROOM, 0))


def fit(dialog: QDialog) -> None:
    """Make ``dialog`` at least as tall as its layout needs at its width,
    but no taller than the screen allows (:func:`room`), unless the
    layout's own minimum is taller."""
    layout = dialog.layout()
    if layout is None or not layout.hasHeightForWidth():
        return
    width = dialog.width()
    dialog.setProperty(_WIDTH, width)
    needed = layout.totalHeightForWidth(width)
    floor = dialog.property(_ORIGINAL_MIN) or 0
    minimum = max(int(floor), needed)
    space = room(dialog)
    if space is not None:
        minimum = max(min(minimum, space.height()), layout.totalMinimumSize().height())
    if dialog.minimumHeight() != minimum:
        dialog.setMinimumHeight(minimum)
    if dialog.height() < minimum:
        dialog.resize(width, minimum)


def keep_on_screen(dialog: QDialog) -> None:
    """Make ``dialog`` no taller than the screen allows (:func:`room`) when
    its code made it taller, never below its minimum height. The width
    stays: the window manager places a wide window, and a dialog laid out
    for its width (the Customize dialog's cards) keeps it."""
    space = room(dialog)
    if space is None:
        return
    height = max(min(dialog.height(), space.height()), dialog.minimumHeight())
    if height != dialog.height():
        dialog.resize(dialog.width(), height)


class _FitFilter(QObject):
    """One filter for every dialog, holding none of them."""

    _instance: _FitFilter | None = None

    @classmethod
    def instance(cls) -> _FitFilter:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def eventFilter(self, dialog, event) -> bool:  # noqa: N802 -- Qt's name
        kind = event.type()
        if kind == QEvent.Type.Show:
            fit(dialog)
            keep_on_screen(dialog)
        elif kind == QEvent.Type.Resize and dialog.property(_WIDTH) != dialog.width():
            fit(dialog)
        return False
