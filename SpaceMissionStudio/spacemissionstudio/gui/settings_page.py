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

"""The Settings area (UI overhaul plan §5.2): appearance, reference data,
network, change history, layout, the keyboard shortcuts and about, each a
section of one page.

Every command is one of the window's action registry (:mod:`gui.actions`)
and looks like the control it is (UI audit UI-11): the theme a segmented
control, an on/off command a check box, any other a framed button
(:mod:`gui.widgets` ``SegmentedControl``, ``ActionCheckBox``,
``ActionButton``). Each follows its command, however it is run (a
shortcut, a menu, the palette). The settings are forms on one label
column (``widgets.finish_form``, UI audit B6). The shortcut list is a
``DataTable`` generated from the registry (UI-33), so this page and the
command palette agree. The UI scale and reduce motion (M8) are
preferences, not commands: they are set here only.
"""

from __future__ import annotations

import weakref

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea,
                               QSizePolicy, QVBoxLayout, QWidget)

from .. import history, network
from . import units
from .data_table import DataTable, Row
from .theme import (CONTENT_MAX_WIDTH_PX, ROW_HEIGHT, SPACE, UI_SCALES, reduce_motion, set_reduce_motion, set_role,
                    set_ui_scale_setting, ui_scale_setting)
from .value_sheet import ValueTable
from .widgets import ActionButton, ActionCheckBox, ComboBox, SegmentedControl, finish_form

# (key, title, what it is for)
_SECTIONS: tuple[tuple[str, str, str], ...] = (
    ("appearance", "Appearance", "The theme applies at once, to every open view; the UI scale at the next "
                                 "start."),
    ("reference_data", "Reference data", "The SPICE kernels, gravity fields, magnetic model, space weather and "
                                         "Earth orientation files, with their sources, dates and checksums."),
    ("network", "Network", "SpaceMissionStudio reaches the network only for a download you start, and "
                         "only the addresses listed for it. Offline, no download can start."),
    ("history", "Change history", "Each save records what it changed beside the scenario "
                                  "(mission.history.jsonl), with this name as its author; the command line uses "
                                  "it too. Empty: your user name."),
    ("layout", "Layout", "The navigation rail, the inspector and the Problems panel; Reset Layout puts them "
                         "back as a new window has them."),
    ("keyboard", "Keyboard", "Every command with a shortcut. Ctrl+K finds any command by name."),
    ("about", "About", ""),
)

# The theme's segments: (command, label)
_THEMES = (("view.theme.system", "System"), ("view.theme.light", "Light"), ("view.theme.dark", "Dark"))

# Settings › Layout: (row label, ((command, check box label), ...))
_LAYOUT_ROWS = (
    ("Panels", (("view.menu_bar", "Menu bar"), ("view.inspector", "Inspector"), ("view.problems", "Problems"))),
    ("Status bar", (("view.status_details", "All details"),)),
    ("Navigation rail", (("view.rail_icons", "Icons only"),)),
)

_SHORTCUT_HEADERS = ("Category", "Command", "Shortcut")


class _Note(QLabel):
    """A wrapped note in a form's field column, in the secondary tone,
    hidden with its (empty) label while it has no text. Qt's guess at a
    wrapped label's height lays it out narrow (three lines for one, the
    text then floats in the middle of the row): the note answers for the
    width it has, as ``value_sheet.NoteList`` does."""

    def __init__(self, buddy: QLabel) -> None:
        super().__init__("")
        self._buddy = buddy
        set_role(self, tone="secondary")
        self.setWordWrap(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setText("")

    def setText(self, text: str) -> None:  # noqa: N802 -- Qt's name
        super().setText(text)
        self.setVisible(bool(text))
        self._buddy.setVisible(bool(text))
        self.updateGeometry()

    def sizeHint(self):  # noqa: N802 -- Qt's name
        hint = super().sizeHint()
        if self.testAttribute(Qt.WidgetAttribute.WA_Resized) and self.width() > 0:
            hint.setHeight(self.heightForWidth(self.width()))
        return hint

    def minimumSizeHint(self):  # noqa: N802 -- Qt's name
        hint = super().minimumSizeHint()
        hint.setHeight(min(hint.height(), self.sizeHint().height()))
        return hint

    def resizeEvent(self, event) -> None:  # noqa: N802 -- Qt's name
        super().resizeEvent(event)
        if event.oldSize().width() != event.size().width():
            self.updateGeometry()


class SettingsPage(QScrollArea):
    """The settings, one section under the other."""

    def __init__(self, commands, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # Weakly: the registry holds the window, and a child holding the
        # window would keep it alive once closed (test_a_closed_window_is_freed).
        self._commands = weakref.ref(commands)
        self.setWidgetResizable(True)
        body = QWidget()
        body.setMaximumWidth(CONTENT_MAX_WIDTH_PX)
        self.setWidget(body)
        self._layout = QVBoxLayout(body)
        self._layout.setContentsMargins(SPACE["xl"], SPACE["lg"], SPACE["xl"], SPACE["lg"])
        self._layout.setSpacing(SPACE["sm"])
        self.section_titles: dict[str, QLabel] = {}
        # Each command's control: an ActionButton, a theme segment or an ActionCheckBox.
        self.buttons: dict[str, QWidget] = {}
        for key, title, text in _SECTIONS:
            if self.section_titles:
                self._layout.addSpacing(SPACE["lg"])
            heading = set_role(QLabel(title), role="section-title")
            heading.setObjectName(f"settings_{key}")
            self.section_titles[key] = heading
            self._layout.addWidget(heading)
            if text:
                line = set_role(QLabel(text), tone="secondary")
                line.setWordWrap(True)
                self._layout.addWidget(line)
            getattr(self, f"_build_{key}")()
        self._layout.addStretch(1)
        finish_form(body)  # one label column, fields at their widths (UI audit B6)

    def sections(self) -> list[tuple[str, str]]:
        """(key, title) of each section, in order."""
        return [(key, title) for key, title, _text in _SECTIONS]

    def show_section(self, key: str) -> None:
        """Scroll ``key``'s section to the top and refresh what it lists."""
        if key == "keyboard":
            self.refresh_shortcuts()
        heading = self.section_titles[key]
        self.verticalScrollBar().setValue(heading.y() - SPACE["sm"])

    # -- building blocks -----------------------------------------------------------------------
    def _form(self) -> QFormLayout:
        """A section's form; every form of the page shares one label column."""
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(SPACE["md"])
        form.setVerticalSpacing(SPACE["sm"])
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self._layout.addLayout(form)
        return form

    @staticmethod
    def _note(form: QFormLayout) -> _Note:
        """A note under the row above, in ``form``'s field column; hidden while empty."""
        buddy = QLabel("")
        note = _Note(buddy)
        form.addRow(buddy, note)
        return note

    @staticmethod
    def _holder(*widgets: QWidget, row: bool = True) -> QWidget:
        """``widgets`` as one field: side by side (``row``, a stretch after
        them) or one under the other."""
        holder = QWidget()
        layout = QHBoxLayout(holder) if row else QVBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE["sm"] if row else SPACE["xs"])
        for widget in widgets:
            layout.addWidget(widget)
        if row:
            layout.addStretch(1)
        return holder

    def _row(self, command_ids: tuple[str, ...]) -> None:
        """A row of framed buttons, one per command, at the left."""
        row = QHBoxLayout()
        row.setSpacing(SPACE["sm"])
        for command_id in command_ids:
            row.addWidget(self._button(command_id))
        row.addStretch(1)
        self._layout.addLayout(row)

    def _button(self, command_id: str) -> ActionButton:
        button = ActionButton(self._commands().action(command_id))
        self.buttons[command_id] = button
        return button

    def _check_box(self, command_id: str, text: str) -> ActionCheckBox:
        box = ActionCheckBox(self._commands().action(command_id), text)
        self.buttons[command_id] = box
        return box

    # -- the sections ---------------------------------------------------------------------------
    def _build_appearance(self) -> None:
        form = self._form()
        self.theme_control = SegmentedControl("Theme")
        for command_id, label in _THEMES:
            self.buttons[command_id] = self.theme_control.add_action(self._commands().action(command_id), label)
        form.addRow("Theme", self._holder(self.theme_control))
        self.ui_scale = ComboBox()  # the wheel does not change it
        for percent in UI_SCALES:
            self.ui_scale.addItem(f"{percent} %", percent)
        self.ui_scale.setCurrentIndex(UI_SCALES.index(ui_scale_setting()))
        self.ui_scale.setToolTip("The size of text and controls, from the next start")
        self.ui_scale.setAccessibleName("UI scale")
        self.ui_scale.currentIndexChanged.connect(self._on_ui_scale)
        self.ui_scale_note = set_role(QLabel(""), tone="secondary")
        form.addRow("UI scale", self._holder(self.ui_scale, self.ui_scale_note))
        self.reduce_motion = QCheckBox("Reduce motion")
        self.reduce_motion.setToolTip("Notifications appear and go at once, without fading")
        self.reduce_motion.setChecked(reduce_motion())
        self.reduce_motion.toggled.connect(set_reduce_motion)
        form.addRow("Motion", self.reduce_motion)
        self.plot_units = ComboBox()
        for value, text in units.PLOT_UNITS:
            self.plot_units.addItem(text, value)
        self.plot_units.setCurrentIndex(self.plot_units.findData(units.plot_units()))
        self.plot_units.setToolTip("The units the plots and the run comparison show. Display units: altitudes, "
                                   "semi-major axes and distances in km, position in m, velocity and delta-V in "
                                   "m/s, angles in degrees, elapsed time in hours. As recorded: the values as "
                                   "recorded and exported (SI: m, rad, s). The exports are always SI.")
        self.plot_units.setAccessibleName("Plot units")
        self.plot_units.currentIndexChanged.connect(self._on_plot_units)
        self.plot_units_note = set_role(QLabel(""), tone="secondary")
        form.addRow("Plot units", self._holder(self.plot_units, self.plot_units_note))

    def _on_plot_units(self, index: int) -> None:
        units.set_plot_units(self.plot_units.itemData(index))
        self.plot_units_note.setText("Applies to the plots drawn next.")

    def _on_ui_scale(self, index: int) -> None:
        set_ui_scale_setting(self.ui_scale.itemData(index))
        self.ui_scale_note.setText("Applies at the next start.")

    def _build_history(self) -> None:
        form = self._form()
        self.author_edit = QLineEdit(history.set_author_name())
        self.author_edit.setPlaceholderText(history.default_author())
        self.author_edit.setToolTip("Your name, as the change history records it; empty: your user name")
        self.author_edit.setAccessibleName("Author")
        self.author_edit.editingFinished.connect(self._on_author)
        form.addRow("Author", self.author_edit)
        self.author_note = self._note(form)

    def _build_network(self) -> None:
        form = self._form()
        self.offline_box = QCheckBox("Work offline: no downloads")
        self.offline_box.toggled.connect(self._on_offline)
        form.addRow("Network use", self.offline_box)
        self.network_note = self._note(form)
        # Each host on its own row, under the purpose it is contacted for.
        rows = [[purpose.label if index == 0 else "", host] for purpose in network.PURPOSES.values()
                for index, host in enumerate(purpose.hosts)]
        self.network_hosts = ValueTable("Hosts it may contact, by purpose", ["Purpose", "Host"], rows)
        self._layout.addWidget(self.network_hosts)
        row = QHBoxLayout()
        row.setSpacing(SPACE["sm"])
        self.network_log_button = QPushButton("Open the network log")
        self.network_log_button.setToolTip(f"Every network use allowed or refused: {network.log_path()}")
        self.network_log_button.clicked.connect(self._open_network_log)
        row.addWidget(self.network_log_button)
        row.addStretch(1)
        self._layout.addLayout(row)
        self.refresh_network()

    def refresh_network(self) -> None:
        """Show the policy in effect; the box is locked when an administrator
        or the environment sets it."""
        current = network.policy()
        self.offline_box.blockSignals(True)
        self.offline_box.setChecked(current.offline)
        self.offline_box.blockSignals(False)
        self.offline_box.setEnabled(not current.locked)
        note = current.describe()
        if current.locked:
            note += " You cannot change this here."
        self.network_note.setText(note)

    def _on_offline(self, offline: bool) -> None:
        try:
            network.set_user_offline(offline)
        except (OSError, PermissionError) as exc:
            set_role(self.network_note, tone="critical")
            self.network_note.setText(f"Not changed: {exc}")
            return
        set_role(self.network_note, tone="secondary")
        self.refresh_network()
        window = self.window()
        if hasattr(window, "apply_network_policy"):
            window.apply_network_policy()

    def _open_network_log(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        path = network.log_path()
        if not path.exists():
            self.network_note.setText("Nothing logged yet: no network use was allowed or refused.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _on_author(self) -> None:
        try:
            history.set_author(self.author_edit.text())
        except OSError as exc:
            set_role(self.author_note, tone="critical")
            self.author_note.setText(f"Could not keep the name: {exc}")
            return
        self.author_edit.setText(history.set_author_name())
        set_role(self.author_note, tone="secondary")
        self.author_note.setText(f"Saves are recorded as {history.current_author()}.")

    def _build_reference_data(self) -> None:
        self._row(("tools.reference_data",))

    def _build_layout(self) -> None:
        form = self._form()
        for label, boxes in _LAYOUT_ROWS:
            form.addRow(label, self._holder(*(self._check_box(command_id, text) for command_id, text in boxes),
                                            row=False))
        self._row(("view.reset_layout",))

    def _build_keyboard(self) -> None:
        # A DataTable (UI-33): the columns fill the width, the last one the
        # rest; headings left; no grid lines; the keys in the monospace font.
        self.shortcuts_table = DataTable("No command has a shortcut.")
        self._layout.addWidget(self.shortcuts_table)
        self.refresh_shortcuts()

    def refresh_shortcuts(self) -> None:
        """The table again from the registry."""
        commands = self._commands()
        rows = commands.shortcut_rows() if commands is not None else []
        table = self.shortcuts_table
        table.set_table(_SHORTCUT_HEADERS, [Row(list(values)) for values in rows], stretch=len(_SHORTCUT_HEADERS) - 1,
                        code=(len(_SHORTCUT_HEADERS) - 1,))
        table.view.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
        # Every row in view: the page scrolls, not the table.
        table.fit_rows()

    def _build_about(self) -> None:
        import spacemissionstudio

        self.version_label = set_role(QLabel(f"SpaceMissionStudio {spacemissionstudio.__version__}"), role="strong")
        self._layout.addWidget(self.version_label)
        self._row(("help.about", "help.licences", "help.manual"))
