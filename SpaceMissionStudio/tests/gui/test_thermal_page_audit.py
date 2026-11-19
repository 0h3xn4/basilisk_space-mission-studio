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
"""UI audit batch B11, Run › Thermal: the notes say each thing once and
the values are in tables, with a short status line (UI-07); Heat flows
gives its table the room, without sideways scroll at 1280 px (UI-21);
Studies chooses a parameter by its label and Monte Carlo... says why it
is off (UI-30); the header has one Save... entry point, the findings
are a chip with an icon and Show in Problems is a button (UI-44)."""

import pytest
from PySide6.QtCore import Qt

pytestmark = pytest.mark.requires_gui

_STATUS_WORDS = {"Below survival", "Above survival", "Below operating", "Above operating", "Within limits",
                 "No limits"}


@pytest.fixture(scope="module")
def solved():
    """Template 33 (four cases, two findings) run for 0.07 days and solved
    without heater sizing."""
    pytest.importorskip("Basilisk")
    from spacemissionstudio import api

    path = api.template("33_microsat_thermal")
    scenario = api.load(path)
    scenario.sim_settings.duration_days = 0.07
    result = api.run(scenario)
    return scenario, result, path.parent, api.thermal(scenario, result, base_dir=path.parent, size_heaters=False)


def _page(qtbot, solved, width=1280, height=720):
    from spacemissionstudio.gui.thermal_widget import ThermalWidget

    scenario, result, base_dir, analysis = solved
    widget = ThermalWidget()
    qtbot.addWidget(widget)
    widget.set_run(scenario, result, base_dir)
    widget.resize(width, height)
    widget.show()
    qtbot.waitExposed(widget)
    widget.show_analysis(analysis)
    return widget


def _tab(widget, qtbot, title):
    from spacemissionstudio.gui.thermal_widget import TABS

    widget.tabs.setCurrentIndex(list(TABS).index(title))
    qtbot.wait(50)


# -- UI-07: notes once, values in tables, a short status -------------------------------------------------

def test_units_in_the_core_s_sentences_and_on_a_heading_s_second_line():
    """The notes come from the core in the code's spelling ("W/m^2",
    "17 deg"): the window writes them as it writes units. A heading's unit
    on a second line stays there ("Cold margin\\n[K]" was joined back
    onto one line, so the thermal tables did not fit)."""
    from spacemissionstudio.gui import units

    assert units.in_text("S 1367 W/m^2, mean OLR 211 W/m^2 (orbit average at beta 17 deg)") == (
        "S 1367 W/m², mean OLR 211 W/m² (orbit average at beta 17°)")
    assert units.in_text("over 0.0016 m^2: contact; 5 deg C; faces[radiator] deg") == (
        "over 0.0016 m²: contact; 5 °C; faces[radiator] deg")
    assert units.label("Cold margin\n[K]") == "Cold margin\n[K]"
    assert units.label("Off-nadir [deg]") == "Off-nadir [°]" and units.label("Ratio [-]") == "Ratio"


def test_a_parameter_s_label_names_its_record_and_field():
    """A study's parameter by its record kind, the user's name and the
    field, with the unit in the window's spelling; a path it does not
    know stays as it is."""
    from spacemissionstudio.gui.thermal_widget import parameter_label, parameter_text

    assert parameter_label("conductors[bus--avionics].contact_coefficient_w_m2_k") == (
        "Conductor bus--avionics: contact coefficient", "W/(m²·K)")
    assert parameter_label("heat_pipes[avionics heat pipe].conductance_w_k") == (
        "Heat pipe avionics heat pipe: conductance", "W/K")
    assert parameter_text("faces[bus].emissivity") == "Face bus: emissivity"
    assert parameter_text("environment.planet_ir_w_m2") == "Environment: planetary infrared [W/m²]"
    assert parameter_label("something odd") == ("something odd", "")

@pytest.mark.requires_basilisk
def test_the_notes_say_each_thing_once_with_the_window_s_units(qtbot, solved):
    """The notes read "nominal: nominal: S 1367 W/m^2 ..." and repeated
    the cold environment for cold safe mode; the energy balance was a
    sentence of numbers. Now each note is there once, named by its cases,
    with its units as the window writes them, and no number sentence."""
    widget = _page(qtbot, solved)
    notes = widget.notes_list.notes
    assert notes and len(notes) == len(set(notes))
    for note in notes:
        head, _sep, rest = note.partition(": ")
        assert not rest.startswith(f"{head}:"), note
        assert "W/m^2" not in note and " deg " not in note and "deg)" not in note, note
        assert "energy balance" not in note, note
    assert any(note.startswith("nominal: S 1367 W/m²") for note in notes)
    assert any(note.startswith("cold, cold safe mode: S 1322 W/m²") for note in notes)
    assert any(note.startswith("cold safe mode: Dissipation avionics: power set to 15.0 W") for note in notes)


@pytest.mark.requires_basilisk
def test_each_case_s_solution_is_a_table_and_the_status_is_one_short_line(qtbot, solved):
    """The status line was a sentence of every case's start and the beta
    angle (two lines at 1280 px). Now it says how many cases were solved;
    each case's start and checks are a value table, one value a cell, and
    the beta angle a value sheet."""
    from spacemissionstudio.gui.value_sheet import ValueTable

    widget = _page(qtbot, solved)
    analysis = solved[3]
    assert widget.status_label.text() == f"Solved {len(analysis.cases)} cases."
    table = widget.solution_table
    assert isinstance(table, ValueTable)
    assert table.headers == ["Case", "Start", "Orbits", "Energy residual [J]", "Energy throughput [J]",
                             "Half-step change [K]"]
    assert [row[0] for row in table.rows] == [case.name for case in analysis.cases]
    for row, case in zip(table.rows, analysis.cases):
        assert row[1] == "Periodic" and row[2] == str(case.solution.periodic.orbits)
        assert float(row[3]) == pytest.approx(abs(case.solution.energy_residual_j), rel=1e-2)
        assert float(row[4]) == pytest.approx(case.solution.energy_throughput_j, rel=1e-2)
        assert float(row[5]) == pytest.approx(case.solution.step_check_k, rel=1e-2)
    beta = analysis.prepared.environment.beta_deg
    sheet = widget.environment_sheet
    assert float(sheet.value("Beta angle, lowest")) == pytest.approx(float(beta.min()), abs=0.05)
    assert float(sheet.value("Beta angle, highest")) == pytest.approx(float(beta.max()), abs=0.05)
    _tab(widget, qtbot, "Notes")
    assert table.isVisible() and sheet.isVisible() and widget.notes_list.isVisible()
    bottom = widget.notes_list.mapTo(widget, widget.notes_list.rect().bottomLeft()).y()
    assert bottom <= widget.height()


@pytest.mark.requires_basilisk
def test_the_summary_gives_each_node_its_status_behind_an_icon(qtbot, solved):
    """Summary: per case and node the extremes, the operating range, the
    margins and a status: a word behind its status icon, never the colour
    alone. The node's name is text, on the left (it was right-aligned)."""
    widget = _page(qtbot, solved)
    table = widget.summary_table
    status = table.column_count() - 1
    assert table.header_text(status) == "Status" and table.header_text(2) == "Min\n[°C]"
    found = {}
    for row in range(table.row_count()):
        word = table.cell(row, status)
        assert word in _STATUS_WORDS
        mark, ink, text_ink = table.model.rows[table.shown_rows()[row]].marks[status]
        assert mark and ink and text_ink
        found[(table.cell(row, 0), table.cell(row, 1))] = (word, ink)
        assert not table.cell_alignment(row, 1) & int(Qt.AlignmentFlag.AlignRight)
        assert table.cell_alignment(row, 2) & int(Qt.AlignmentFlag.AlignRight)
    assert found[("cold safe mode", "avionics")] == ("Below operating", "status.caution")
    assert found[("nominal", "battery")] == ("Within limits", "status.normal")
    assert found[("nominal", "radiator")][0] == "No limits"
    assert table.row_count() == sum(len(case.summary) for case in solved[3].cases)


# -- UI-21: Heat flows ---------------------------------------------------------------------------------------

@pytest.mark.requires_basilisk
def test_the_node_picker_is_a_compact_row_of_labels_and_lists(qtbot, solved):
    """The spacecraft, case and node lists sit beside their labels at a
    drop-down list's width (the spacecraft list was 480 px wide)."""
    from spacemissionstudio.gui.theme import FIELD_WIDTH

    widget = _page(qtbot, solved)
    for label, combo in ((widget.case_label, widget.case_combo), (widget.node_label, widget.node_combo)):
        assert label.buddy() is combo and label.isVisible() and combo.isVisible()
        assert combo.width() <= FIELD_WIDTH["choice"]
        assert abs(label.mapTo(widget, label.rect().center()).y() - combo.mapTo(widget, combo.rect().center()).y()) <= 2
    assert widget.spacecraft_combo.width() <= FIELD_WIDTH["choice"]


@pytest.mark.requires_basilisk
def test_heat_flows_give_the_table_the_room_once_a_node_is_picked(qtbot, solved):
    """With a node picked the table showed two rows at 1280 x 720. Now it
    is as tall as its rows, as far as the plot's least height leaves room."""
    from spacemissionstudio.gui.thermal_widget import _FLOW_PLOT_MIN_PX

    for height, every_row in ((560, False), (900, True)):
        widget = _page(qtbot, solved, 1280, height)
        widget.node_combo.setCurrentText("battery")
        _tab(widget, qtbot, "Heat flows")
        section, table = widget.tables["flows"]
        view = table.view
        assert widget.flow_plot.isVisible() and widget.flow_plot.height() >= _FLOW_PLOT_MIN_PX
        shown = view.viewport().height() // view.rowHeight(0)
        assert shown >= min(table.row_count(), 4)
        if every_row:
            assert view.verticalScrollBar().maximum() == 0 and shown >= table.row_count()
        else:  # all the room the plot leaves: the plot at its least height, or every row shown
            assert (widget.flow_plot.height() <= _FLOW_PLOT_MIN_PX + 2
                    or view.verticalScrollBar().maximum() == 0)


@pytest.mark.requires_basilisk
@pytest.mark.parametrize("inspector", [True, False], ids=["inspector", "no-inspector"])
def test_no_thermal_table_scrolls_sideways_at_1280(qtbot, monkeypatch, solved, inspector):
    """Heat flows, Summary and Heaters and radiators fit the page at 1280 x
    720 with the Inspector open or closed (the flows and the summary
    scrolled sideways beside the Inspector)."""
    window, page = _window(qtbot, monkeypatch, solved)
    window.side_dock.setVisible(inspector)
    page.node_combo.setCurrentText("battery")
    for case in [page.case_combo.itemText(i) for i in range(page.case_combo.count())]:
        page.case_combo.setCurrentText(case)
        for title, keys in (("Heat flows", ("flows",)), ("Summary", ()),
                            ("Heaters and radiators", ("heaters", "radiators"))):
            _tab(page, qtbot, title)
            tables = [page.tables[key][1] for key in keys] or [page.summary_table]
            for table in tables:
                qtbot.waitUntil(lambda t=table: t.view.horizontalScrollBar().maximum() == 0, timeout=3000)


# -- UI-30: Studies ------------------------------------------------------------------------------------------

@pytest.mark.requires_basilisk
def test_studies_choose_a_parameter_by_its_label(qtbot, solved):
    """The parameter was a code path typed into a text field. Now it is a
    list of the thermal model's parameters by label and unit, each path
    on hover; "Other parameter" takes any path; a sweep runs on the path."""
    from spacemissionstudio.thermal import sweeps

    widget = _page(qtbot, solved)
    combo = widget.sweep_parameter
    paths = sweeps.default_parameters(solved[3].prepared.spacecraft.thermal)
    assert [combo.itemData(i) for i in range(combo.count())] == [*paths, None]
    for index, path in enumerate(paths):
        text = combo.itemText(index)
        assert path not in text and "_" not in text, text
        assert "faces[" not in text and "].power" not in text, text
        assert combo.itemData(index, Qt.ItemDataRole.ToolTipRole) == path
    labels = {combo.itemData(i): combo.itemText(i) for i in range(len(paths))}
    assert labels["heaters[battery heater A].power_w"] == "Heater battery heater A: power [W]"
    assert labels["faces[array +y:+z].absorptance"] == "Face array +y, side +z: absorptance"
    assert labels["environment.solar_flux_w_m2"] == "Environment: solar flux [W/m²]"
    assert widget.sweep_path.isHidden()
    widget.choose_parameter("environment.albedo")  # not in the list: Other, by its path
    assert combo.currentData() is None and not widget.sweep_path.isHidden()
    assert widget.sweep_parameter_path() == "environment.albedo"
    widget.choose_parameter("faces[radiator].emissivity")
    assert widget.sweep_path.isHidden() and "faces[radiator].emissivity" in combo.toolTip()
    widget.sweep_values.setText("0.8, 0.9")
    widget.run_sweep()
    qtbot.waitUntil(lambda: widget._study_worker is None and not widget.study_table.isHidden(), timeout=120000)
    assert widget.study_table.row_count() == 2
    assert widget.study_table.header_text(1) == "bus min\n[°C]"  # the user's name as it is
    assert widget.study_label.text().startswith("Sweep of Face radiator: emissivity in the nominal case")


@pytest.mark.requires_basilisk
def test_monte_carlo_says_why_it_is_off_and_what_turns_it_on(qtbot, solved, monkeypatch):
    """Monte Carlo... was off with no reason. Off, its tooltip starts
    "Off:", says the thermal model has no Monte Carlo section and where to
    add one; with a section it is on, with its own tooltip."""
    from spacemissionstudio.schema.thermal import ThermalDispersionConfig, ThermalMonteCarloConfig

    widget = _page(qtbot, solved)
    button = widget.monte_carlo_button
    _tab(widget, qtbot, "Studies")
    assert button.isVisible() and not button.isEnabled()
    tip = button.toolTip()
    assert tip.startswith("Off:") and "no Monte Carlo section" in tip and "Thermal model" in tip
    thermal = solved[3].prepared.spacecraft.thermal
    monkeypatch.setattr(thermal, "monte_carlo", ThermalMonteCarloConfig(3, 1, "nominal", [ThermalDispersionConfig(
        "dissipations[battery].power_w", 1.0)]))
    widget.show_analysis(solved[3])
    assert button.isEnabled() and not button.toolTip().startswith("Off:")


@pytest.mark.requires_basilisk
def test_every_disabled_input_on_the_page_says_why(qtbot, solved):
    """Before a solve (Save...) and on every tab after it, a disabled input
    has a tooltip that starts "Off:" (the time slider and Monte Carlo...
    said nothing)."""
    from PySide6.QtWidgets import QAbstractButton, QAbstractSlider, QComboBox, QLineEdit

    from spacemissionstudio.gui.thermal_widget import TABS, ThermalWidget

    scenario, result, base_dir, _analysis = solved
    fresh = ThermalWidget()
    qtbot.addWidget(fresh)
    fresh.set_run(scenario, result, base_dir)
    fresh.show()
    assert not fresh.save_button.isEnabled() and fresh.save_button.toolTip().startswith("Off:")
    fresh.set_run(None, None)
    assert not fresh.solve_button.isEnabled() and fresh.solve_button.toolTip().startswith("Off:")
    widget = _page(qtbot, solved)
    for title in TABS:
        _tab(widget, qtbot, title)
        silent = [w for kind in (QAbstractButton, QAbstractSlider, QComboBox, QLineEdit)
                  for w in widget.findChildren(kind)
                  if w.isVisible() and not w.isEnabled() and not w.toolTip().startswith("Off:")
                  and not isinstance(w.parentWidget(), QComboBox)]
        assert silent == [], (title, silent)


# -- UI-44: the header ---------------------------------------------------------------------------------------

@pytest.mark.requires_basilisk
def test_one_save_entry_point_writes_the_same_files(qtbot, solved, tmp_path, monkeypatch):
    """Save..., Save SVG... and Save PNG... are one Save... with a menu;
    each entry writes what the page's save and save_plot write."""
    from PySide6.QtWidgets import QFileDialog, QPushButton

    from spacemissionstudio.thermal import plots

    widget = _page(qtbot, solved)
    saves = [b for b in widget.findChildren(QPushButton) if b.text().startswith("Save")]
    assert saves == [widget.save_button] and widget.save_button.isEnabled()
    menu = widget.save_button.menu()
    assert [a.text() for a in menu.actions() if not a.isSeparator()] == [
        "Everything to a folder...", "Temperature plot as SVG...", "Temperature plot as PNG..."]
    case = widget.analysis.case(widget.case_combo.currentText())
    for fmt, action in (("svg", widget.save_svg_action), ("png", widget.save_png_action)):
        target = tmp_path / f"menu.{fmt}"
        monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, t=target, **k: (str(t), "")))
        action.trigger()
        assert target.read_bytes() == widget.save_plot(tmp_path / f"direct.{fmt}", fmt).read_bytes()
    assert (tmp_path / "menu.svg").read_text(encoding="utf-8") == plots.temperature_svg(case)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: str(tmp_path / "all")))
    widget.save_all_action.trigger()
    direct = widget.save(tmp_path / "direct_all")
    for path in direct:
        if path.suffix in (".csv", ".svg", ".png"):
            assert (tmp_path / "all" / path.name).read_bytes() == path.read_bytes(), path.name


@pytest.mark.requires_basilisk
def test_the_findings_are_a_chip_and_show_in_problems_is_a_button(qtbot, monkeypatch, solved):
    """"2 findings" was a word in the caution colour and Show in Problems
    a link. Now the count is a chip with the caution icon and its words,
    and Show in Problems a framed button that opens the Problems panel."""
    from PySide6.QtWidgets import QPushButton

    from spacemissionstudio.gui.badges import StatusBadge

    window, page = _window(qtbot, monkeypatch, solved)
    findings = solved[3].findings()
    chip = page.findings_label
    assert isinstance(chip, StatusBadge) and chip.kind == "caution" and chip.isVisible()
    assert chip.text() == f"{len(findings)} findings" and chip.icon_name() == "triangle-alert"
    assert not chip.icon_label.pixmap().isNull()
    button = page.problems_button
    assert isinstance(button, QPushButton) and button.property("variant") != "ghost" and button.isVisible()
    assert "Ctrl+J" in button.toolTip()
    window.problems_dock.hide()
    button.click()
    assert window.problems_dock.isVisible()


def _window(qtbot, monkeypatch, solved):
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    window.resize(1280, 720)
    window.show()
    qtbot.waitExposed(window)
    scenario, result, base_dir, analysis = solved
    window.open_path(base_dir / "33_microsat_thermal.json")
    page = window.thermal_widget
    page.set_run(scenario, result, base_dir)
    page.show_analysis(analysis)
    window.show_view(page)
    qtbot.wait(50)
    return window, page
