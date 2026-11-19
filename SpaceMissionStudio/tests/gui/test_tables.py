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

"""One table style and no cut headings (UI audit B9), measured in a shown
1280 x 720 window with the app's theme, the Inspector open and closed:

- UI-27: Reports › Exports fits the page: no sideways scroll, every heading
  whole, a long cell elided and whole on hover, rows at the table-row
  height, no developer remark;
- UI-49: each reference data file's kind comes from its Basilisk registry
  class, never a guess;
- the Problems panel's table has the DataTable look: headings on the left,
  no grid lines, no frame of its own, rows at the table-row height, its
  sort and severity icons kept;
- the thermal editor's tables never cut a heading: a column is at least as
  wide as its heading; a table too wide for the page scrolls itself, never
  the page;
- the Flight Software card names the pointing mode by its label;
- every other table of the window has headings on the left and no grid
  lines.

Sizes are read from widgets that are shown and laid out (a hidden widget is
never laid out); the tests assert relations, not pixel positions."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.requires_gui

_TEMPLATES = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"
_INSPECTOR = (False, True)


@pytest.fixture(scope="module")
def _shared_window(qapp, tmp_path_factory):
    """One 1280 x 720 main window with the app's theme for the module, in a
    home of its own, template 33 open (the thermal model)."""
    with pytest.MonkeyPatch.context() as patch:
        home = tmp_path_factory.mktemp("home")
        patch.setattr(Path, "home", lambda: home)
        yield from _made_shared_window(qapp)


def _made_shared_window(qapp):
    import gc

    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication

    from spacemissionstudio.gui.main_window import MainWindow
    from spacemissionstudio.gui.theme import apply_theme, state

    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    gc.collect()
    saved = (qapp.font(), qapp.palette(), qapp.styleSheet())
    apply_theme(qapp, "light")
    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    window._confirm_discard_unsaved = lambda: True
    window.resize(1280, 720)  # [px]
    window.show()
    window.problems_dock.hide()
    QApplication.processEvents()
    assert window.open_path(_TEMPLATES / "33_microsat_thermal.json")
    QApplication.processEvents()
    yield window
    window._mark_clean()
    window.close()
    window.deleteLater()
    QApplication.processEvents()
    state.select("light")
    qapp.setStyleSheet(saved[2])
    qapp.setPalette(saved[1])
    qapp.setFont(saved[0])


@pytest.fixture
def window(_shared_window):
    yield _shared_window
    _shared_window.side_dock.hide()
    _shared_window.problems_dock.hide()


def _settle(qtbot, widget=None, ms: int = 30) -> None:
    from PySide6.QtWidgets import QApplication

    if widget is not None:
        qtbot.waitUntil(widget.isVisible, timeout=5000)
    for _ in range(3):
        QApplication.processEvents()
        qtbot.wait(ms)


def _inspector(window, qtbot, shown: bool) -> None:
    window.side_dock.setVisible(shown)
    _settle(qtbot)
    assert window.side_dock.isVisible() == shown


def _cut_headings(view) -> list[str]:
    """The headings of ``view``'s shown columns narrower than the size the
    style gives them (``QHeaderView.sectionSizeHint``: the style sheet's
    font and padding, the header's margins): such a heading is elided."""
    from PySide6.QtCore import Qt

    header, model = view.horizontalHeader(), view.model()
    return [str(model.headerData(c, Qt.Orientation.Horizontal)) for c in range(model.columnCount())
            if not view.isColumnHidden(c) and header.sectionSize(c) < header.sectionSizeHint(c)]


def _alignment(view, column: int):
    """The horizontal alignment of ``view``'s heading ``column``."""
    from PySide6.QtCore import Qt

    alignment = view.model().headerData(column, Qt.Orientation.Horizontal, Qt.ItemDataRole.TextAlignmentRole)
    if alignment is None:
        alignment = view.horizontalHeader().defaultAlignment()
    return Qt.AlignmentFlag(int(alignment)) & Qt.AlignmentFlag.AlignHorizontal_Mask


def _left(view, column: int = 0) -> bool:
    """Whether ``view``'s heading ``column`` is aligned to the left."""
    from PySide6.QtCore import Qt

    return _alignment(view, column) == Qt.AlignmentFlag.AlignLeft


def _not_centred(view) -> bool:
    """Whether every heading of ``view`` is on the left, or on the right (a
    numeric column's), never centred."""
    from PySide6.QtCore import Qt

    return all(_alignment(view, c) in (Qt.AlignmentFlag.AlignLeft, Qt.AlignmentFlag.AlignRight)
               for c in range(view.model().columnCount()))


# -- UI-27: Reports › Exports --------------------------------------------------------------------

@pytest.mark.parametrize("inspector", _INSPECTOR)
def test_the_exports_fit_the_page_with_every_heading_whole(window, qtbot, inspector):
    """At 1280 x 720 the table does not scroll sideways, the last column is
    in view, no heading is cut, and the rows are at least the table-row
    height. No cell is elided: since UI audit B12 the text columns wrap and
    a row grows to its tallest cell (a cell that were elided would show
    whole on hover)."""
    from spacemissionstudio.gui.exports_page import EXPORTS
    from spacemissionstudio.gui.theme import ROW_HEIGHT

    _inspector(window, qtbot, inspector)
    window.shell.show_area("reports")
    window.reports_views.setCurrentWidget(window.exports_page)
    table = window.exports_page.table
    _settle(qtbot, table.view)
    view = table.view
    assert view.horizontalScrollBar().maximum() == 0
    assert view.horizontalHeader().length() <= view.viewport().width()
    assert _cut_headings(view) == []
    assert min(view.rowHeight(r) for r in range(table.row_count())) >= ROW_HEIGHT
    elided = [(row, column) for row in range(table.row_count()) for column in table.shown_columns()
              if table.cell_elided(row, column)]
    assert elided == []  # the text columns wrap (UI audit B12), with the Inspector too
    for row, column in elided:
        assert table.hover_text(row, column) in (table.cell(row, column), table.cell_tooltip(row, column))
    assert len(EXPORTS) == table.row_count()


def test_the_exports_page_has_no_developer_remark(qtbot):
    """The line over the table speaks to the user: no version, no "byte for byte"."""
    from PySide6.QtWidgets import QLabel

    from spacemissionstudio.gui.exports_page import ExportsPage

    page = ExportsPage()
    qtbot.addWidget(page)
    texts = " ".join(label.text() for label in page.findChildren(QLabel))
    assert "1.1.0" not in texts and "byte for byte" not in texts
    assert "Enter or a double-click opens the view" in texts


# -- UI-49: the reference data kinds -------------------------------------------------------------

def test_every_support_data_class_has_a_kind_of_its_own():
    """Every class of Basilisk's support-data registry has a kind; no file
    the app checks falls back to the unknown kind, and only the ephemeris
    class is a SPICE kernel."""
    pytest.importorskip("Basilisk")
    from Basilisk.utilities.supportDataTools import dataFetcher

    from spacemissionstudio.engine import kernels, reference_data

    classes = [name for name in dir(dataFetcher.DataFile) if not name.startswith("_")]
    assert set(classes) <= set(reference_data.SUPPORT_DATA_KINDS)
    assert [name for name, kind in reference_data.SUPPORT_DATA_KINDS.items() if kind == "SPICE kernel"] == \
        ["EphemerisData"]
    for kernel in kernels.ALL_SUPPORT_DATA_FILES:
        assert reference_data.support_data_kind(kernel) != reference_data.UNKNOWN_SUPPORT_DATA_KIND
    assert reference_data.support_data_kind(object()) == reference_data.UNKNOWN_SUPPORT_DATA_KIND


# -- the Problems panel ----------------------------------------------------------------------------

def test_the_problems_table_has_the_data_table_look(window, qtbot):
    """Headings on the left, no grid lines, no frame of its own in the
    dock, rows at the table-row height; the severity keeps its icon and
    word, and errors still sort first."""
    from PySide6.QtCore import Qt

    from spacemissionstudio.gui.theme import ROW_HEIGHT

    widget = window.problems_widget
    widget.set_problems([("warning", "sim_settings.duration_s: a long run"),
                         ("error", "spacecraft[0].mass_kg: must be positive")], ["microsat-1"])
    window.show_problems()
    _settle(qtbot, widget.table)
    table = widget.table
    assert not table.showGrid()
    assert all(_left(table, c) for c in range(table.model().columnCount()))
    assert table.frameWidth() == 0
    assert {table.rowHeight(r) for r in range(table.model().rowCount())} == {ROW_HEIGHT}
    assert widget.shown_rows()[0][0] == "Error"
    assert not table.model().index(0, 0).data(Qt.ItemDataRole.DecorationRole).isNull()
    assert table.isSortingEnabled() and table.horizontalHeader().isSortIndicatorShown()


# -- the thermal editor ----------------------------------------------------------------------------

@pytest.mark.parametrize("inspector", _INSPECTOR)
def test_no_thermal_heading_is_cut(window, qtbot, inspector):
    """Template 33's thermal editor, each tab, the Inspector open and
    closed: every heading of every table shows whole; a table wider than
    the page scrolls itself and is as tall as its rows and its scroll bar;
    the page never scrolls sideways."""
    from PySide6.QtWidgets import QScrollArea

    from spacemissionstudio.gui.thermal_editor import RecordTable

    _inspector(window, qtbot, inspector)
    editor = window.scenario_editor
    window.shell.show_area("scenario")
    window._show_tree_item(dict(editor.page_tree.paths())["Spacecraft > microsat-1 > 3D model"])
    group = editor._spacecraft_nodes[0].form.thermal_group
    _settle(qtbot, group)
    for index in range(group.tabs.count()):
        group.tabs.setCurrentIndex(index)
        _settle(qtbot)
        tables = [t for t in group.tabs.currentWidget().findChildren(RecordTable) if t.isVisible()]
        assert tables, group.tabs.tabText(index)
        for table in tables:
            assert _cut_headings(table) == [], (group.tabs.tabText(index), inspector)
            scrolls = table.horizontalHeader().length() > table.viewport().width()
            assert table.horizontalScrollBar().isVisible() == scrolls
            assert table.verticalScrollBar().maximum() == 0  # as tall as its rows
        sideways = [area for area in editor.findChildren(QScrollArea)
                    if area.isVisible() and area.horizontalScrollBar().maximum() > 0]
        assert sideways == [], group.tabs.tabText(index)


def test_a_short_thermal_heading_has_its_full_name_on_hover():
    """A heading shortened to fit ("C [J/K]") gives its full name on hover."""
    from PySide6.QtCore import Qt

    from spacemissionstudio.gui.thermal_editor import TABLES, RecordModel

    for _key, _title, _cls, columns in TABLES:
        model = RecordModel(columns)
        for column, spec in enumerate(columns):
            label = model.headerData(column, Qt.Orientation.Horizontal)
            tip = model.headerData(column, Qt.Orientation.Horizontal, Qt.ItemDataRole.ToolTipRole)
            assert tip and label in tip or tip == label, spec
    nodes = RecordModel(TABLES[0][3])
    labels = [nodes.headerData(c, Qt.Orientation.Horizontal) for c in range(nodes.columnCount())]
    assert "C [J/K]" in labels and "Capacitance [J/K]" not in labels


# -- the Flight Software card ----------------------------------------------------------------------

def test_the_flight_software_card_names_the_mode_by_its_label(qtbot):
    from spacemissionstudio.gui.field_text import mode_label
    from spacemissionstudio.gui.fsw_workbench_widget import FlightSoftwareWidget
    from spacemissionstudio.schema import load_scenario

    scenario = load_scenario(_TEMPLATES / "33_microsat_thermal.json")
    widget = FlightSoftwareWidget()
    qtbot.addWidget(widget)
    widget.set_scenario(scenario)
    widget._refresh()
    detail = widget.card("microsat-1").detail
    assert scenario.spacecraft[0].fsw_mode == "sunSafePoint"
    assert "sunSafePoint" not in detail.text() and mode_label("sunSafePoint") in detail.text()
    assert "sunSafePoint" in detail.toolTip()  # the code, for the JSON, on hover


# -- the sweep: every other table ------------------------------------------------------------------

def test_every_table_of_the_window_has_left_headings_and_no_grid(window):
    """Every table view in the window, shown or not, follows the DataTable
    look: no grid lines, no heading centred (on the left; a numeric
    column's on the right)."""
    from PySide6.QtWidgets import QTableView

    views = window.findChildren(QTableView)
    assert len(views) > 5
    grid = [f"{type(v).__name__}:{v.objectName()}" for v in views if v.showGrid()]
    centred = [f"{type(v).__name__}:{v.objectName()}" for v in views if v.model() is not None
               and v.model().columnCount() and not _not_centred(v)]
    assert grid == [] and centred == []


def test_the_editors_tables_have_left_headings_and_no_grid(qtbot):
    """The tables of the dialogs and editors outside the window: the facet
    and data-handling editors, the model analyses' observers, the 3D model's
    face properties and envelope, the IDM import and the readouts."""
    from PySide6.QtWidgets import QTableView

    from spacemissionstudio.gui.data_handling_editor import GainTableWidget, InstrumentTableWidget
    from spacemissionstudio.gui.facet_editor import FacetTableWidget
    from spacemissionstudio.gui.idm_import_dialog import IdmImportDialog
    from spacemissionstudio.gui.model_analyses_editor import ModelAnalysesGroup
    from spacemissionstudio.gui.model_editor_dialog import ModelEditorDialog
    from spacemissionstudio.gui.readout_panel import ReadoutPanel
    from spacemissionstudio.gui.sil_comparison_widget import SilComparisonWidget
    from spacemissionstudio.schema.scenario import ModelPartConfig, SpacecraftModelConfig

    model = SpacecraftModelConfig(parts=[ModelPartConfig(name="bus", shape="box", mass_kg=50.0,
                                                         dimensions_m={"x": 1.0, "y": 1.0, "z": 1.0})])
    widgets = [InstrumentTableWidget(), GainTableWidget(), FacetTableWidget(), IdmImportDialog(), ReadoutPanel(),
               SilComparisonWidget(), ModelAnalysesGroup(None),
               ModelEditorDialog(model, spacecraft_name="sat-1")]
    seen = 0
    for widget in widgets:
        qtbot.addWidget(widget)
        for view in widget.findChildren(QTableView):
            seen += 1
            assert not view.showGrid(), type(widget).__name__
            assert _not_centred(view), type(widget).__name__
    assert seen >= len(widgets)
