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
"""Labels instead of identifiers (UI audit batch B4).

The audit found raw identifiers as labels: "star_tracker: st-1",
"sunSafePoint", "mars barycenter" (UI-08); the Assumptions page's codes
in a table with grid lines, centred headings and a heading row that
looked selected (UI-19); units in the code's ASCII spelling ("deg",
"W*h") beside values (UI-35, with the scan of the window's strings in
``tests/test_gui_strings.py``, as UI-34's double hyphens); and the
Reference data panel's atmosphere tables listed as SPICE kernels, "ok" in
lower case, an empty Covers column, grid lines and a horizontal scroll bar
at 1280 x 720 (UI-49). These tests check each defect. The scenario file
keeps every code: a form shows the label and writes the code.
"""

import dataclasses
from pathlib import Path

import pytest

pytestmark = pytest.mark.requires_gui

_TEMPLATES = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"
_T07 = _TEMPLATES / "07_attitude_pointing_with_adcs_hardware.json"
_T30 = _TEMPLATES / "30_mars_optical_navigation.json"
_CODE = 0x0100  # Qt.ItemDataRole.UserRole


# -- UI-08: device kinds, guidance modes and bodies --------------------------------------------

def test_the_label_maps_cover_every_code_and_agree_with_the_app_s_other_names():
    """Every device kind, guidance mode and body the schema takes has a
    label, and each label is the one the app already uses elsewhere: the
    IDM-CIC import's device names, the Overview's mode names, 433 Eros."""
    from spacemissionstudio.engine import scenario_explainer, small_bodies
    from spacemissionstudio.gui import field_text
    from spacemissionstudio.idm_devices import KIND_LABELS
    from spacemissionstudio.schema import scenario

    kinds = scenario.SUPPORTED_SENSOR_KINDS + scenario.SUPPORTED_ACTUATOR_KINDS
    assert set(kinds) <= set(field_text.DEVICE_KIND_LABELS)
    assert {k: field_text.DEVICE_KIND_LABELS[k] for k in KIND_LABELS} == KIND_LABELS
    assert field_text.kind_label("star_tracker") == "Star tracker" and field_text.kind_label("thermal") == "Thermal sensor"
    assert set(scenario.SUPPORTED_FSW_MODES) <= set(field_text.GUIDANCE_MODE_LABELS)
    assert field_text.GUIDANCE_MODE_LABELS == scenario_explainer.FSW_MODE_NAMES
    assert field_text.mode_label("sunSafePoint") == "Sun pointing"
    bodies = scenario.SUPPORTED_CENTRAL_BODIES + scenario.SMALL_BODY_CENTRAL_BODIES
    assert set(bodies) == set(field_text.BODY_LABELS)
    assert field_text.body_label("mars barycenter") == "Mars barycentre"
    assert field_text.body_label("eros") == small_bodies.BODIES["eros"].title
    for label in list(field_text.DEVICE_KIND_LABELS.values()) + list(field_text.BODY_LABELS.values()):
        assert "_" not in label and label[:1].isupper() or label[:1].isdigit()
    assert field_text.kind_label("no_such_kind") == "no_such_kind"  # an unknown code as it is


def test_the_device_list_names_the_kind_and_keeps_the_device_s_own_name(qtbot):
    """"star_tracker: st-1" reads "Star tracker: st-1": the kind's label and
    the user's own name, the kind's code on hover; the Kind field shows
    labels and gives the code."""
    from spacemissionstudio.gui.sensor_actuator_editor import SensorActuatorListWidget
    from spacemissionstudio.schema.scenario import SUPPORTED_SENSOR_KINDS, SensorConfig

    widget = SensorActuatorListWidget(SensorConfig, SUPPORTED_SENSOR_KINDS)
    qtbot.addWidget(widget)
    devices = [SensorConfig(kind="star_tracker", name="st-1", params={}),
               SensorConfig(kind="coarse_sun_sensor", name="css-1", params={})]
    widget.from_list(devices)
    rows = [widget.list_widget.item(i) for i in range(widget.list_widget.count())]
    assert [row.text() for row in rows] == ["Star tracker: st-1", "Sun sensor: css-1"]
    assert [row.toolTip() for row in rows] == ["kind: star_tracker", "kind: coarse_sun_sensor"]
    widget.list_widget.setCurrentRow(0)
    form = widget.inline.form
    combo = form.kind_combo
    assert [combo.itemText(i) for i in range(combo.count())] == [
        "Star tracker", "Gyro / IMU", "Sun sensor", "Magnetometer", "Thermal sensor"]
    assert combo.currentText() == "Star tracker" and form.kind() == "star_tracker"
    assert widget.to_list() == devices  # the codes the file writes, unchanged


def test_a_device_added_is_named_by_its_code_and_listed_by_its_label(qtbot):
    """A new device's own name stays "star_tracker-1" (the file's value, as
    before); its row and the toast name the kind's label."""
    from spacemissionstudio.gui.sensor_actuator_editor import SensorActuatorListWidget
    from spacemissionstudio.schema.scenario import SUPPORTED_SENSOR_KINDS, SensorConfig

    widget = SensorActuatorListWidget(SensorConfig, SUPPORTED_SENSOR_KINDS)
    qtbot.addWidget(widget)
    widget._on_add()
    assert widget.to_list()[0].kind == "star_tracker" and widget.to_list()[0].name == "star_tracker-1"
    assert widget.list_widget.item(0).text() == "Star tracker: star_tracker-1"


def test_the_guidance_modes_are_named_and_the_code_is_kept(qtbot):
    """"sunSafePoint" in the FSW mode field reads "Sun pointing", as the
    Overview names it; the scenario keeps the code."""
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog
    from spacemissionstudio.schema import load_scenario

    config = next(sc for sc in load_scenario(_T07).spacecraft if sc.fsw_mode)
    dialog = SpacecraftEditorDialog(config)
    qtbot.addWidget(dialog)
    combo = dialog.fsw_mode_combo
    shown = [combo.itemText(i) for i in range(1, combo.count())]
    assert shown == ["Inertial hold", "Orbit-frame (nadir) pointing", "Velocity pointing", "Sun pointing",
                     "Target pointing"]
    assert combo.currentData() == config.fsw_mode and combo.currentText() != config.fsw_mode
    assert dialog.to_dataclass().fsw_mode == config.fsw_mode


def test_the_bodies_are_named_and_the_gravity_keeps_their_codes(qtbot):
    """"mars barycenter" reads "Mars barycentre" as the central body and
    among the third bodies; the gravity written is the template's."""
    from spacemissionstudio.gui.propagation_setup_dialog import PropagationSetupDialog
    from spacemissionstudio.schema import load_scenario

    scenario = load_scenario(_T30)
    dialog = PropagationSetupDialog(scenario.gravity, scenario.sim_settings, scenario.space_weather)
    qtbot.addWidget(dialog)
    assert dialog.central_body_combo.currentText() == "Mars barycentre"
    assert dialog.central_body() == scenario.gravity.central_body == "mars barycenter"
    items = [dialog.third_body_list.item(i) for i in range(dialog.third_body_list.count())]
    assert [item.text() for item in items] == ["Sun", "Mercury", "Venus", "Earth", "Moon", "Jupiter barycentre"]
    assert [item.data(_CODE) for item in items][-1] == "jupiter barycenter"
    assert dialog.to_gravity() == scenario.gravity


def test_the_scenario_file_is_written_as_before(qtbot, tmp_path):
    """Template 07 (devices and a guidance mode) and template 30 (Mars) open
    in the editor and are saved byte for byte as the editor saved them
    before: every code is kept."""
    from spacemissionstudio.gui.scenario_editor import ScenarioEditorWidget
    from spacemissionstudio.schema import load_scenario

    for template in (_T07, _T30):
        scenario = load_scenario(template)
        editor = ScenarioEditorWidget()
        qtbot.addWidget(editor)
        editor.from_scenario(scenario)
        scenario.save(tmp_path / "loaded.json")
        editor.to_scenario().save(tmp_path / "edited.json")
        assert (tmp_path / "edited.json").read_bytes() == (tmp_path / "loaded.json").read_bytes()


# -- UI-19: Scenario › Assumptions ----------------------------------------------------------------

@pytest.fixture
def assumptions(qtbot, tmp_path, restored_theme):
    from spacemissionstudio.gui.assumptions_page import AssumptionsPage
    from spacemissionstudio.gui.theme import apply_theme

    apply_theme(restored_theme, "light")
    page = AssumptionsPage()
    page.set_base_dir_provider(lambda: tmp_path)
    qtbot.addWidget(page)
    yield page
    restored_theme.setStyle("Fusion")


def test_every_parameter_has_a_name_and_its_key_as_a_muted_second_line(assumptions):
    """The first column names the parameter ("Residual propellant
    fraction"), not its code; the key the file uses is the cell's second
    line, in the monospace font (the secondary colour when painted), and
    starts its tooltip; every parameter and area of the registry has its
    own name; the rows are two lines high."""
    from spacemissionstudio.config import registry
    from spacemissionstudio.gui import field_text
    from spacemissionstudio.gui.data_table import NOTE_ROLE

    names = [p.name for p in registry.parameters()]
    assert set(names) == set(field_text.PARAMETER_LABELS)
    assert {p.area for p in registry.parameters()} == set(field_text.AREA_LABELS)
    table = assumptions.table
    assert [table.header_text(c) for c in range(table.column_count())] == [
        "Parameter", "Value", "Default", "Unit", "Source"]
    row = assumptions._names.index("propellant_budget.residual_fraction")
    assert table.model.text(row, 0) == "Residual propellant fraction"
    assert table.model.data(table.model.index(row, 0), NOTE_ROLE) == "propellant_budget.residual_fraction"
    assert table.model.rows[row].tooltips[0].startswith("propellant_budget.residual_fraction: ")
    assert table._notes.note_font.family() == "JetBrains Mono"
    assert table.view.verticalHeader().defaultSectionSize() > table._one_line_px
    shown = [table.model.text(r, 0) for r in range(len(assumptions._names)) if assumptions._names[r] is not None]
    assert len(shown) == len(names) and not any("_" in name for name in shown)


def test_numbers_right_text_left_and_units_typeset(assumptions):
    """Values and defaults that are numbers are right-aligned (their headings
    too); a model's name is text, left-aligned; the other headings are
    left-aligned, not centred; "[deg]" shows "°" and "[-]" nothing."""
    from PySide6.QtCore import Qt

    table = assumptions.table
    right, left = int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter), \
        int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    def model_row(name):
        return assumptions._names.index(name)

    def alignment(name, column):
        return table.model.data(table.model.index(model_row(name), column), Qt.ItemDataRole.TextAlignmentRole) or 0

    assert alignment("propellant_budget.cam_count_factor", 1) == right
    assert alignment("propellant_budget.cam_count_factor", 2) == right
    assert alignment("propellant_budget.margin_policy", 1) in (0, left)  # "ad10_equations": text
    assert alignment("propellant_budget.cam_count_factor", 0) in (0, left)
    headings = [table.model.headerData(c, Qt.Orientation.Horizontal, Qt.ItemDataRole.TextAlignmentRole)
                for c in range(table.column_count())]
    assert headings == [left, right, right, left, left]
    assert table.model.text(model_row("explain.sso_tolerance_deg"), 3) == "°"
    assert table.model.text(model_row("propellant_budget.cam_count_factor"), 3) == ""
    assert table.model.text(model_row("propellant_budget.geo_graveyard_per_cr_a_m"), 3) == "m per (m²/kg)"


def test_area_rows_are_headings_not_a_selection_and_the_table_has_no_grid(assumptions):
    """An area's row is a section heading: its name, in the heading weight,
    on the canvas surface (not the selected-row colour), and it cannot be
    selected; the table draws no grid lines."""
    from PySide6.QtCore import Qt

    from spacemissionstudio.gui.theme import TOKENS

    table = assumptions.table
    row = assumptions._names.index("propellant_budget.cam_count_factor") - 1
    heading = table.model.index(row, 0)
    assert table.model.text(row, 0) == "Propellant budget"
    background = table.model.data(heading, Qt.ItemDataRole.BackgroundRole).name().upper()
    assert background == TOKENS["bg.canvas"].upper() != TOKENS["bg.selected"].upper()
    assert not table.model.flags(heading) & Qt.ItemFlag.ItemIsSelectable
    assert table.model.flags(table.model.index(row + 1, 0)) & Qt.ItemFlag.ItemIsSelectable
    assert not table.view.showGrid()


def test_the_page_fits_1280_by_720_without_a_sideways_scroll(qtbot, tmp_path):
    """At 1280 x 720 the Assumptions page in the window shows every column
    without a horizontal scroll bar; a long name is whole on hover."""
    from spacemissionstudio.gui.main_window import MainWindow

    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    window.resize(1280, 720)
    window.show()
    window.open_path(_TEMPLATES / "01_two_body_circular_orbit.json")
    tree = window.scenario_editor.page_tree
    tree.tree.setCurrentItem(dict(tree.paths())["Assumptions"])
    page = window.scenario_editor.assumptions_page
    qtbot.waitUntil(page.table.isVisible, timeout=5000)
    qtbot.wait(50)
    assert page.table.view.horizontalScrollBar().maximum() == 0
    window._dirty = False


# -- UI-35: units through units.py ----------------------------------------------------------------

def test_units_show_in_their_display_form(qtbot):
    """A table heading's "[deg]", a value-mark note's computed value and a
    hand-made spin box's suffix show "°", "W*h" shows "Wh"; the copied
    text keeps the heading as written."""
    from PySide6.QtCore import Qt

    from spacemissionstudio.gui import units
    from spacemissionstudio.gui.budget_widget import _spin
    from spacemissionstudio.gui.data_table import DataTable, Row
    from spacemissionstudio.gui.value_mark_note import ValueMarkNote

    assert units.label("Off-nadir [deg]") == "Off-nadir [°]" and units.label("Eccentricity [-]") == "Eccentricity"
    assert units.label("Antenna gain table [deg, dBi]") == "Antenna gain table [deg, dBi]"  # not a unit
    assert units.shown("W*h") == "Wh" and units.shown("kg*m^2") == "kg·m²" and units.shown("W/m^2") == "W/m²"
    table = DataTable()
    qtbot.addWidget(table)
    table.set_table(["Activity", "Off-nadir [deg]"], [Row(("a", "12.0"))], numeric=(1,))
    assert table.model.headerData(1, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) == "Off-nadir [°]"
    assert table.text().splitlines()[0] == "Activity\tOff-nadir [deg]"
    note = ValueMarkNote("deg")
    qtbot.addWidget(note)
    assert note._value(97.59) == "97.59°"
    assert _spin(0.0, 90.0, 1.0, suffix=" deg").suffix() == "°"


# -- UI-49: the Reference data panel --------------------------------------------------------------

_INVENTORY = [  # the shape of a real inventory: 19 files, long names, dates and sources
    ("SPICE kernel", "naif0012.tls", "ok", "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/lsk/naif0012.tls", ""),
    ("SPICE kernel", "de430.bsp", "ok", "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de430.bsp", ""),
    ("SPICE kernel", "de-403-masses.tpc", "ok", "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/x.tpc", ""),
    ("SPICE kernel", "pck00010.tpc", "ok", "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/pck00010.tpc", ""),
    ("gravity field", "GGM03S.txt", "ok", "https://raw.githubusercontent.com/AVSLab/basilisk/develop/supportData/"
                                          "LocalGravData/GGM03S.txt", ""),
    ("gravity field", "GGM2BData.txt", "ok", "https://raw.githubusercontent.com/AVSLab/basilisk/x/GGM2BData.txt", ""),
    ("magnetic model", "WMM2025.COF", "ok", "https://raw.githubusercontent.com/AVSLab/basilisk/x/WMM2025.COF", ""),
    ("albedo map", "Earth_ALB_2018_CERES_All_5x5.csv", "ok", "https://raw.githubusercontent.com/AVSLab/x.csv", ""),
    ("albedo map", "Mars_ALB_TES_5x5.csv", "ok", "https://raw.githubusercontent.com/AVSLab/basilisk/x.csv", ""),
    ("atmosphere table", "USStandardAtmosphere1976.csv", "ok", "https://raw.githubusercontent.com/AVSLab/y.csv", ""),
    ("atmosphere table", "EarthGRAMNominal.txt", "ok", "https://raw.githubusercontent.com/AVSLab/y.txt", ""),
    ("atmosphere table", "NRLMSISE00Nominal.txt", "ok", "https://raw.githubusercontent.com/AVSLab/z.txt", ""),
    ("space weather", "SW-All.txt", "out of date", "bundled with SpaceMissionStudio (CelesTrak SW-All)",
     "1957-10-01 to 2041-10-31 (observed to 2026-11-18)"),
    ("solar-activity prediction", "nov2026f10-prd.txt", "ok", "bundled with SpaceMissionStudio (NASA MSFC)", ""),
    ("Earth orientation", "earth_1962_260806_2126_combined.bpc", "ok",
     "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/earth_1962_260806_2126_combined.bpc",
     "1962-2126, measured to 2026-08-06"),
    ("Earth orientation", "earth_latest_high_prec.bpc", "missing", "https://naif.jpl.nasa.gov/pub/naif/x.bpc", ""),
    ("small-body ephemeris", "eros_1900_2100.bsp", "not downloaded", "https://naif.jpl.nasa.gov/x.bsp",
     "1900-01-01 to 2100-01-01"),
    ("shape model", "eros007790.tab", "ok", "Basilisk support data", ""),
    ("ITU-R recommendation data", "R-REC-P.676-13-Part1.txt", "ok", "https://www.itu.int/rec/R-REC-P.676", ""),
]


def _files():
    from spacemissionstudio.engine.reference_data import ReferenceFile

    return [ReferenceFile(kind, name, status, source, f"/cache/{name}", 1000, "ab" * 32, "2026-10-22T00:00:00+00:00",
                          covers) for kind, name, status, source, covers in _INVENTORY]


def test_the_atmosphere_tables_are_not_listed_as_spice_kernels():
    """The tabular atmosphere's published profiles (CSV and text tables)
    are "atmosphere table" files; the SPICE kernels stay SPICE kernels."""
    pytest.importorskip("Basilisk")
    from spacemissionstudio.engine import kernels, reference_data

    files = {f.name: f.kind for f in reference_data._support_files()}
    for name in ("USStandardAtmosphere1976.csv", "EarthGRAMNominal.txt", "NRLMSISE00Nominal.txt"):
        assert files[name] == "atmosphere table"
    for kernel in kernels.DEFAULT_KERNELS:
        assert files[kernel.value] == "SPICE kernel"


def test_the_panel_is_a_table_of_words_with_status_icons(qtbot, restored_theme):
    """The panel's table is a DataTable (no QTableWidget, no grid lines);
    a kind starts with a capital; each status is a word with its status
    icon and colour ("Present", not "ok"); a file without dates shows "–"
    under Covers."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QTableWidget

    from spacemissionstudio.gui import data_panel_widget as dp
    from spacemissionstudio.gui.data_table import DataTable
    from spacemissionstudio.gui.theme import TOKENS, apply_theme

    apply_theme(restored_theme, "light")
    panel = dp.DataPanelWidget(load=False)
    qtbot.addWidget(panel)
    panel.show_files(_files())
    assert isinstance(panel.table, DataTable) and not panel.findChildren(QTableWidget)
    assert not panel.table.view.showGrid()
    status, covers = dp._COLUMNS.index("Status"), dp._COLUMNS.index("Covers")
    assert panel.table.cell(9, 0) == "Atmosphere table" and panel.table.cell(0, 0) == "SPICE kernel"
    words = [panel.table.cell(r, status) for r in range(panel.table.row_count())]
    assert set(words) == {"Present", "Out of date", "Missing", "Not downloaded"} and "ok" not in words
    for row, ink in ((0, "status.normal.text"), (12, "status.caution.text"), (15, "status.critical.text")):
        index = panel.table.model.index(row, status)
        assert not panel.table.model.data(index, Qt.ItemDataRole.DecorationRole).isNull()
        assert panel.table.model.data(index, Qt.ItemDataRole.ForegroundRole).name().upper() == TOKENS[ink].upper()
    assert panel.table.cell(0, covers) == "–" and panel.table.cell(12, covers).startswith("1957-10-01 to")
    assert "need attention" in panel.status_label.text() and " ok" not in panel.status_label.text()
    panel.show_files([f for f in _files() if not f.covers])
    assert covers not in panel.table.shown_columns()  # no file has dates: no empty column


def test_the_reference_data_window_has_no_sideways_scroll_at_1280_by_720(qtbot, monkeypatch):
    """The Reference data window, opened in a 1280 x 720 window, shows
    every column without a horizontal scroll bar; a long name, date range
    or source is elided and whole on hover."""
    from spacemissionstudio.gui import data_panel_widget as dp
    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(dp.reference_data, "inventory", lambda now=None: _files())
    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    window.resize(1280, 720)
    window.show()
    window.data_panel_widget.show_files(_files())
    window.show_view(window.data_panel_widget)
    dialog = window.data_dialog
    qtbot.waitUntil(dialog.isVisible, timeout=5000)
    qtbot.wait(50)
    assert dialog.width() <= 1280 and dialog.height() <= 720
    table = window.data_panel_widget.table
    assert table.view.horizontalScrollBar().maximum() == 0
    covers = dp._COLUMNS.index("Covers")
    assert table.cell_tooltip(12, covers) == _INVENTORY[12][4]
    dialog.close()
    window._dirty = False


def test_a_status_never_shows_its_code():
    """Every status the inventory gives has a word of its own."""
    from spacemissionstudio.engine import reference_data
    from spacemissionstudio.gui import data_panel_widget as dp

    for status in ("ok", "missing", "out of date", reference_data.NOT_DOWNLOADED):
        word = dp.status_text(status)
        assert word[:1].isupper() and word != status
    assert dataclasses.is_dataclass(reference_data.ReferenceFile)
