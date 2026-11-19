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

"""Status badges: a small pill that says a state at a glance, its colour
from the status tokens (``theme/qss.py``'s ``[badge=...]`` rules) and its
text always written out, so colour is never the only cue. One look for
every badge in the app (the dashboard, the explainer, the Flight Software
and End of Life tabs), and a status colour means one thing everywhere.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from .theme import ICON_SIZE, SPACE, colour, icon, on_change, set_role, ui_font

# Badge kinds: the Astro UXDS statuses they stand for.
MUTED = "off"
SUCCESS = "normal"
DANGER = "critical"
ACCENT = "standby"
WARNING = "caution"
KINDS = (MUTED, SUCCESS, DANGER, ACCENT, WARNING, "serious")


def set_badge(widget: QWidget, kind: str) -> QWidget:
    """Show ``widget`` (a label or a button) as a badge of ``kind``."""
    if kind not in KINDS:
        raise ValueError(f"unknown badge kind {kind!r}")
    return set_role(widget, badge=kind)


# A status's icon: the one the Problems panel and the note lists show for it.
STATUS_ICONS = {"critical": "octagon-alert", "serious": "circle-alert", "caution": "triangle-alert",
                "normal": "circle-check", "standby": "info", "off": "circle-minus"}


class StatusBadge(QWidget):
    """A status as a chip (UI audit UI-44): the status's icon and its words
    on the status's soft tint, never the colour alone ("2 findings" behind
    the caution triangle). Not a control: it says a state, a button next
    to it acts on it. It paints its tint itself and follows the theme."""

    def __init__(self, kind: str = WARNING, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        if kind not in KINDS:
            raise ValueError(f"unknown status kind {kind!r}")
        self.kind = kind
        row = QHBoxLayout(self)
        row.setContentsMargins(SPACE["sm"], SPACE["xs"] // 2, SPACE["sm"] + SPACE["xs"], SPACE["xs"] // 2)
        row.setSpacing(SPACE["xs"])
        self.icon_label = QLabel(self)
        self.icon_label.setFixedSize(ICON_SIZE["ui"], ICON_SIZE["ui"])
        row.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignVCenter)
        self.text_label = set_role(QLabel(text, self), tone=kind if kind != MUTED else "secondary")
        self.text_label.setFont(ui_font("small", "medium"))
        row.addWidget(self.text_label, 0, Qt.AlignmentFlag.AlignVCenter)
        self.setAccessibleName(text)
        self._restyle()
        on_change(self._restyle)

    def text(self) -> str:
        return self.text_label.text()

    def set_text(self, text: str) -> None:
        self.text_label.setText(text)
        self.setAccessibleName(text)

    def icon_name(self) -> str:
        return STATUS_ICONS[self.kind]

    def _restyle(self, _mode: str | None = None) -> None:
        size = ICON_SIZE["ui"]
        self.icon_label.setPixmap(icon(STATUS_ICONS[self.kind], f"status.{self.kind}").pixmap(size, size))
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 -- Qt's name
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(colour(f"status.{self.kind}.soft")))
        rect = QRectF(self.rect())
        painter.drawRoundedRect(rect, rect.height() / 2.0, rect.height() / 2.0)
        painter.end()
