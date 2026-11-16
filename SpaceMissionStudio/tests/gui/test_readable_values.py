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

"""Values shown to be read, not as a line of text (gui.value_sheet), and
dialogs that never cut off their own text (gui.theme.dialogs)."""

import pytest

pytestmark = pytest.mark.requires_gui


def test_a_value_sheet_gives_each_value_its_row(qtbot):
    from PySide6.QtCore import Qt

    from spacemissionstudio.gui.value_sheet import ValueSheet

    sheet = ValueSheet("Mass", [("Mass", "86", "kg"), ("Eccentricity", "0.001", "")], note="From B")
    qtbot.addWidget(sheet)
    value = sheet.grid.itemAtPosition(0, 1).widget()
    assert value.text() == "86" and value.alignment() & Qt.AlignmentFlag.AlignRight
    assert sheet.grid.itemAtPosition(0, 2).widget().text() == "kg"
    assert sheet.value("Eccentricity") == "0.001"
    assert sheet.text() == "Mass\nMass: 86 kg\nEccentricity: 0.001\nFrom B"
    empty = ValueSheet("Page", empty="No values yet.")
    qtbot.addWidget(empty)
    assert empty.text() == "Page\nNo values yet."


def test_a_value_table_aligns_numbers_right(qtbot):
    from PySide6.QtCore import Qt

    from spacemissionstudio.gui.value_sheet import ValueTable

    table = ValueTable("Inertia [kg m²]", ["", "x", "y"], [["x", "14.0", "0"], ["y", "0", "12.5"]], numeric=(1, 2))
    qtbot.addWidget(table)
    assert table.grid.itemAtPosition(1, 1).widget().alignment() & Qt.AlignmentFlag.AlignRight
    assert table.grid.itemAtPosition(1, 0).widget().alignment() & Qt.AlignmentFlag.AlignLeft
    assert table.text().splitlines()[1:] == ["\tx\ty", "x\t14.0\t0", "y\t0\t12.5"]


def test_the_3d_model_editor_shows_mass_properties_as_tables(qtbot):
    """Mass and centre of mass as rows, the inertia as a matrix, the
    principal axes with their nearest body axis; the plain text stays the
    command line's."""
    from spacemissionstudio.gui.model_editor_dialog import ModelEditorDialog

    dialog = ModelEditorDialog(None, spacecraft_name="sat-1")
    qtbot.addWidget(dialog)
    dialog.add_part("prism")
    dialog.add_part("panel")
    dialog.recompute_now()
    summary = dialog.mass_summary
    assert summary.mass_sheet.rows[0] == ("Mass", "86", "kg")
    assert [row[0] for row in summary.inertia_table.rows] == ["x", "y", "z"]
    assert summary.inertia_table.rows[0][1] == "14.0113"
    assert [row[3] for row in summary.axes_table.rows] == ["+y", "+z", "+x"]
    assert summary.text().startswith("mass 86 kg")
    surfaces = dialog.surfaces_label
    assert surfaces.sheet.value("Number of facets") == "12" and surfaces.areas.value("From +z") == "2.828"


def test_a_titled_sheet_opens_no_window_of_its_own(qtbot):
    """A title or note label shown before the layout took it was a window of
    its own for a moment: it took the activation from the main window, whose
    shortcuts then went dead (tests/gui/test_panels.py, after a window with
    the budget's "Totals" sheet)."""
    from PySide6.QtCore import QEvent, QObject
    from PySide6.QtWidgets import QApplication

    from spacemissionstudio.gui.value_sheet import NoteList, ValueSheet, ValueTable

    windows = []

    class Watch(QObject):
        def eventFilter(self, watched, event):  # noqa: N802 -- Qt's name
            if event.type() == QEvent.Type.Show and getattr(watched, "isWindow", None) and watched.isWindow():
                windows.append(type(watched).__name__)
            return False

    watch = Watch()
    QApplication.instance().installEventFilter(watch)
    try:
        sheet = ValueSheet("Totals", [("Delta-V", "41.27", "m/s")], note="From the last run.")
        table = ValueTable("Momentum [N·m·s]", ["", "x"], [["Needed", "0.1"]], note="Body frame.")
        notes = NoteList("warning", ["one", "two", "three", "four", "five"])
        for widget in (sheet, table, notes):
            qtbot.addWidget(widget)
        QApplication.processEvents()
    finally:
        QApplication.instance().removeEventFilter(watch)
    assert windows == []


def test_a_note_list_puts_each_note_on_its_row_and_folds_a_long_list(qtbot):
    """Each note behind its icon, wrapped beside it; after four, the rest
    wait behind "Show n more"; ``text()`` keeps every note."""
    from spacemissionstudio.gui.value_sheet import NoteList

    notes = NoteList("warning", [f"warning {n}" for n in range(6)])
    qtbot.addWidget(notes)
    notes.show()
    assert len(notes.rows) == 6 and [row.isVisible() for row in notes.rows] == [True] * 4 + [False] * 2
    assert notes.more_button.isVisible() and notes.more_button.text() == "Show 2 more"
    notes.more_button.click()
    assert all(row.isVisible() for row in notes.rows) and notes.more_button.text() == "Show fewer"
    assert notes.text().splitlines()[0] == "⚠ warning 0" and len(notes.text().splitlines()) == 6
    notes.set_notes(["one", " ", ""])
    assert len(notes.rows) == 1 and not notes.more_button.isVisible()  # blank notes are dropped
    empty = NoteList("finding", empty="No design finding.")
    qtbot.addWidget(empty)
    empty.show()
    assert empty.text() == "No design finding." and empty.empty_label.isVisible() and not empty.rows


def test_text_values_in_a_sheet_keep_the_body_font(qtbot):
    from spacemissionstudio.gui.value_sheet import ValueSheet

    sheet = ValueSheet("Launcher", [("Envelope", "Fairing A", ""), ("Faceting error", "0.42", "mm"),
                                    ("Offset", "-.5", "m"), ("Iterations", "4", "")])
    qtbot.addWidget(sheet)
    numeric = [bool(sheet.grid.itemAtPosition(row, 1).widget().property("smsNumeric")) for row in range(4)]
    assert numeric == [False, True, True, True]


def test_the_spacecraft_model_summary_is_a_sheet(qtbot):
    from spacemissionstudio.gui.spacecraft_editor import ModelSummary

    summary = ModelSummary()
    qtbot.addWidget(summary)
    summary.show_model([("Parts", "2", ""), ("Mass", "86", "kg")], "Parts: prism, panel.", ["open mesh"],
                       "Out of date: dry mass. Click Apply the model.", stale=True)
    assert summary.sheet.value("Mass") == "86" and summary.problems.notes == ["open mesh"]
    assert summary.text().startswith("Out of date: dry mass.")
    summary.show_text("No 3D model: mass, inertia and facets are typed in.")
    assert not summary.sheet.rows and not summary.problems.notes


@pytest.fixture
def themed(restored_theme):
    from spacemissionstudio.gui.theme import apply_theme

    apply_theme(restored_theme, "light")
    yield restored_theme
    restored_theme.setStyle("Fusion")


def test_a_dialog_grows_to_fit_its_wrapped_text(qtbot, themed):
    """Made narrower than its text was laid out for, a dialog with a
    word-wrapped label grows taller, so no line or button is cut off."""
    from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

    dialog = QDialog()
    layout = QVBoxLayout(dialog)
    label = QLabel("A long explanation that wraps onto several lines when the dialog is narrow. " * 6)
    label.setWordWrap(True)
    layout.addWidget(label)
    layout.addWidget(QDialogButtonBox(QDialogButtonBox.StandardButton.Ok))
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)
    dialog.resize(260, dialog.height())
    qtbot.waitUntil(lambda: dialog.height() >= layout.totalHeightForWidth(dialog.width()))
    assert dialog.minimumHeight() >= layout.totalHeightForWidth(dialog.width())
    assert label.geometry().bottom() <= dialog.height()
