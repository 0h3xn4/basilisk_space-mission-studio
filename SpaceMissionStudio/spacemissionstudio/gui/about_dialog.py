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
"""Help › About SpaceMissionStudio (UI audit UI-48): a small window in the
app's theme, not Qt's plain message box. Its name, then the version, the
Basilisk version and the licence (a name and its value per row, the
value in the monospace font, selectable), the licence lines of
``spacemissionstudio.legal``, and the two places to read more: the
third-party licences and the user manual (the window's own commands, so
their shortcuts and states are the menu's). Close or Esc closes it.

Not modal: a modal dialog only confirms something destructive or runs a
wizard (``docs/DESIGN.md``). One window, kept when closed, like the
manual and the licences (``widgets.show_window``)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import QDialog, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .. import dependencies, legal
from .theme import DIALOG_WIDTH, SPACE, set_role
from .widgets import ActionButton, make_window

TITLE = "About SpaceMissionStudio"


def about_rows() -> list[tuple[str, str, str]]:
    """(name, value) of the About window's rows: the version, the Basilisk
    version (or that it is not installed) and the licence."""
    import spacemissionstudio

    basilisk = dependencies.basilisk_version()
    return [("Version", spacemissionstudio.__version__),
            ("Basilisk", basilisk if basilisk is not None else "not installed (user manual, section 2)"),
            ("Licence", "EUPL-1.2")]


class AboutDialog(QDialog):
    """The About window (module docstring). ``licences`` and ``manual`` are
    the window's Help commands; without them (a test, a tool) the buttons
    are left out."""

    def __init__(self, parent: QWidget | None = None, licences: QAction | None = None,
                 manual: QAction | None = None) -> None:
        super().__init__(parent)
        make_window(self)
        self.setWindowTitle(TITLE)
        self.setFixedWidth(DIALOG_WIDTH["small"])
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE["xl"], SPACE["xl"], SPACE["xl"], SPACE["lg"])
        layout.setSpacing(SPACE["md"])
        self.title_label = set_role(QLabel("SpaceMissionStudio"), role="page-title")
        layout.addWidget(self.title_label)
        intro = set_role(QLabel("Mission analysis on the Basilisk astrodynamics framework (AVS Lab, University of "
                                "Colorado Boulder)."), tone="secondary")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        facts = QGridLayout()
        facts.setHorizontalSpacing(SPACE["lg"])
        facts.setVerticalSpacing(SPACE["xs"])
        self.value_labels = []
        for row, (name, value) in enumerate(about_rows()):
            facts.addWidget(set_role(QLabel(name), tone="secondary"), row, 0)
            value_label = set_role(QLabel(value), role="mono")  # a version is an identifier
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            facts.addWidget(value_label, row, 1)
            self.value_labels.append(value_label)
        facts.setColumnStretch(1, 1)
        layout.addLayout(facts)
        self.licence_label = set_role(QLabel(legal.about_html()), role="caption")
        self.licence_label.setTextFormat(Qt.TextFormat.RichText)
        self.licence_label.setWordWrap(True)
        self.licence_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.licence_label)
        buttons = QHBoxLayout()
        buttons.setSpacing(SPACE["sm"])
        self.link_buttons = [ActionButton(action) for action in (licences, manual) if action is not None]
        for button in self.link_buttons:
            button.setAutoDefault(False)  # secondary: Close is the window's one default (accent) button
            buttons.addWidget(button)
        buttons.addStretch(1)
        self.close_button = QPushButton("Close")
        self.close_button.setToolTip("Close (Esc)")
        self.close_button.setDefault(True)
        self.close_button.clicked.connect(self.close)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, activated=self.close)

    def text(self) -> str:
        """Its text, line by line: the name, the sheet's rows and the licence lines."""
        rows = [f"{name}: {value}" for name, value in about_rows()]
        return "\n".join([self.title_label.text(), *rows, self.licence_label.text()])
