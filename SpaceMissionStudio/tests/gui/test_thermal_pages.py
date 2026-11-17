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
"""The thermal model's GUI (SRS-F-29): the spacecraft editor's Thermal
model group (tables that round-trip the section exactly, Generate from
the 3D model, the conductance calculator, a cell that does not read
refused with its place), Run › Thermal (solve on a background thread, the
summary, plots, tables and findings, Save with provenance, SVG and PNG)
and the thermal limit events on the Timeline."""

import copy
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from spacemissionstudio.engine.events import THERMAL_LIMIT, Event
from spacemissionstudio.gui import export_log
from spacemissionstudio.gui.event_timeline_widget import THERMAL_BOX, EventTimelineWidget
from spacemissionstudio.gui.thermal_editor import ThermalGroup
from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.thermal import (ThermalCaseConfig, ThermalConductorConfig, ThermalDispersionConfig,
                                               ThermalDissipationConfig, ThermalFaceConfig, ThermalHeaterConfig,
                                               ThermalHeatPipeConfig, ThermalMonteCarloConfig)
from spacemissionstudio.thermal import generate

_TEMPLATE = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates" \
    / "32_smallsat_design_checks.json"
_ARRAYS = ("array +y", "array -y")


def _thermal(sc):
    thermal = generate.generate(sc, _TEMPLATE.parent).thermal
    thermal.faces = [ThermalFaceConfig(p.name, coating="white_paint_z93") for p in sc.model.parts
                     if p.name not in _ARRAYS]
    for array in _ARRAYS:
        thermal.faces += [ThermalFaceConfig(array, "+z", coating="solar_cell_triple_junction"),
                          ThermalFaceConfig(array, "-z", coating="black_paint_z306", mli_effective_emittance=0.03)]
    battery = next(n for n in thermal.nodes if n.name == "battery")
    battery.operating_c = [0.0, 30.0]
    thermal.dissipations = [ThermalDissipationConfig("battery-loss", "battery", power_w=5.0)]
    thermal.heaters = [ThermalHeaterConfig("battery-heater", "battery", 10.0, 5.0, 8.0)]
    thermal.heat_pipes = [ThermalHeatPipeConfig("hp", "battery", "bus", 2.0, [-60.0, 60.0], 0.01)]
    thermal.conductors.append(ThermalConductorConfig("strap", "battery", "dish", "material", material="copper",
                                                     length_m=0.3, section_m2=1.0e-4,
                                                     conductivity_table=[[-50.0, 410.0], [50.0, 395.0]]))
    thermal.cases = [ThermalCaseConfig("cold", "cold", {"environment.albedo": 0.2})]
    return thermal


def test_the_group_round_trips_the_section_exactly(qtbot):
    """Every record of every kind, the environment and the solver come
    back from the tables equal to what went in; off means no section."""
    sc = load_scenario(_TEMPLATE).spacecraft[0]
    thermal = _thermal(sc)
    thermal.solver.time_step_s = 20.0
    thermal.environment.albedo_model = "average"
    thermal.monte_carlo = ThermalMonteCarloConfig(20, 3, "cold", [ThermalDispersionConfig(
        "faces[array +y:-z].emissivity", 0.05, "uniform"), ThermalDispersionConfig("heaters[battery-heater].power_w",
                                                                                    0.1, relative=True)])
    group = ThermalGroup(copy.deepcopy(thermal))
    qtbot.addWidget(group)
    assert group.to_config() == thermal
    assert group.tables["nodes"].rowCount() == len(thermal.nodes)
    group.setChecked(False)
    assert group.to_config() is None
    assert ThermalGroup(None).to_config() is None


def test_a_cell_that_does_not_read_names_its_place(qtbot):
    sc = load_scenario(_TEMPLATE).spacecraft[0]
    group = ThermalGroup(_thermal(sc))
    qtbot.addWidget(group)
    nodes = group.tables["nodes"]
    column = [name for name, _label, _kind in nodes.columns].index("operating_c")
    nodes.item(1, column).setText("0")
    with pytest.raises(ValueError, match=r"thermal\.nodes\[1\]\.operating_c: give 'lowest, highest'"):
        group.to_config()
    assert group.field_widget("nodes[1].operating_c") is nodes
    assert group.field_widget("solver.time_step_s") is group.solver_table


def test_generate_fills_the_tables_from_the_3d_model_and_keeps_the_rest(qtbot, monkeypatch):
    """No model: a message. With one: a node per part and its conductors;
    the heaters, heat pipes and cases already set are kept."""
    from spacemissionstudio.gui import thermal_editor

    scenario = load_scenario(_TEMPLATE)
    sc = scenario.spacecraft[0]
    group = ThermalGroup(None, lambda: None)
    qtbot.addWidget(group)
    group._on_generate()
    assert "needs a 3D model" in group.status_label.text()
    kept = _thermal(sc)
    kept.nodes, kept.faces, kept.conductors = [], [], []
    group = ThermalGroup(kept, lambda: sc, lambda: _TEMPLATE.parent)
    qtbot.addWidget(group)
    monkeypatch.setattr(thermal_editor.QMessageBox, "question",
                        staticmethod(lambda *a, **k: thermal_editor.QMessageBox.StandardButton.Yes))
    group._on_generate()
    made = group.to_config()
    assert [n.name for n in made.nodes] == [n.name for n in generate.generate(sc, _TEMPLATE.parent).thermal.nodes]
    assert made.heaters == kept.heaters and made.heat_pipes == kept.heat_pipes and made.cases == kept.cases
    assert group.status_label.text().startswith(f"Generated {len(made.nodes)} nodes")


def test_the_conductance_button_shows_the_selected_conductors_value(qtbot):
    sc = load_scenario(_TEMPLATE).spacecraft[0]
    group = ThermalGroup(_thermal(sc), lambda: sc)
    qtbot.addWidget(group)
    group._on_conductance()
    assert group.conductance_label.text() == "Select a conductor."
    table = group.tables["conductors"]
    table.setCurrentCell(table.rowCount() - 1, 0)
    group._on_conductance()
    assert group.conductance_label.text().startswith("strap: 0.1367 W/K")  # 410 W/(m K) * 1e-4 m^2 / 0.3 m


def test_table_headings_carry_their_units():
    from spacemissionstudio.gui.thermal_widget import heading

    assert [heading(k) for k in ("min_c", "cold_margin_k", "energy_wh", "area_m2", "heat pipes_w", "duty")] == [
        "Min [°C]", "Cold margin [K]", "Energy [W·h]", "Area [m²]", "Heat pipes [W]", "Duty"]


def test_the_timeline_shows_thermal_limit_events_added_after_the_run(qtbot):
    widget = EventTimelineWidget()
    qtbot.addWidget(widget)
    widget.set_result(None)
    assert widget.kind_boxes[THERMAL_BOX].isHidden()
    event = Event(THERMAL_LIMIT, "sat", 100.0, 400.0, "battery below operating", detail="cold: battery",
                  quantities=(("temperature", -12.5),), note="cold")
    widget.set_extra_events([event])
    assert widget.events == [event] and not widget.kind_boxes[THERMAL_BOX].isHidden()
    assert widget.visible_events() == [event]
    widget.kind_boxes[THERMAL_BOX].setChecked(False)
    assert widget.visible_events() == []
    widget.set_extra_events([])
    assert widget.events == []


@pytest.mark.slow
def test_run_thermal_solves_shows_and_saves(qtbot, tmp_path, monkeypatch):
    """Template 32 run for 0.1 days with its thermal model: Solve (no
    sizing) fills the summary for nominal, hot and cold, the plots, the
    heaters and flows; the battery's limit events reach the Timeline; Save
    writes the record, the tables, the series and the plots (SVG, PNG),
    each with its provenance."""
    pytest.importorskip("Basilisk")
    from spacemissionstudio.engine.service import SimulationService
    from spacemissionstudio.gui.thermal_widget import ThermalWidget

    scenario = load_scenario(_TEMPLATE)
    scenario.sim_settings.duration_days = 0.1
    sc = scenario.spacecraft[0]
    sc.model_analyses = None
    sc.thermal = _thermal(sc)
    sc.thermal.cases = []
    scenario.validate()
    result = SimulationService(scenario).run()
    widget = ThermalWidget()
    qtbot.addWidget(widget)
    timeline = EventTimelineWidget()
    qtbot.addWidget(timeline)
    timeline.set_result(result)
    widget.events_changed.connect(timeline.set_extra_events)
    assert not widget.solve_button.isEnabled()
    widget.set_run(scenario, result, _TEMPLATE.parent)
    assert widget.solve_button.isEnabled() and not widget.save_button.isEnabled()
    widget.size_check.setChecked(False)
    widget.solve()
    qtbot.waitUntil(lambda: widget.analysis is not None and widget._worker is None, timeout=240000)
    assert widget.status_label.text().startswith("Solved nominal: periodic after")
    assert "Beta angle over the run:" in widget.status_label.text()
    assert widget.summary_table.row_count() == 3 * len(sc.thermal.nodes)
    assert [widget.case_combo.itemText(i) for i in range(widget.case_combo.count())] == ["nominal", "hot", "cold"]
    assert ET.fromstring(widget.temperature_svg).tag.endswith("svg") and widget.flow_plot.isHidden()
    widget.node_combo.setCurrentText("battery")
    assert "battery operating" in widget.temperature_svg and "Heat flows into battery" in widget.flow_svg
    assert not widget.tables["heaters"][0].isHidden()
    assert any(e.kind == THERMAL_LIMIT for e in timeline.events)
    written = widget.save(tmp_path / "out")
    names = {p.name for p in written}
    assert {"thermal.json", "thermal_summary.csv", "thermal_nominal_temperature.svg",
            "thermal_cold_battery_heat_flow.png"} <= names
    assert all((p.parent / (p.name + ".provenance.json")).exists() for p in written if p.suffix != ".json")
    assert json.loads((tmp_path / "out" / "thermal.json").read_text())["kind"] == "thermal_analysis"
    assert export_log.last("thermal")[1].endswith("out")
    png = widget.save_plot(tmp_path / "plot.png", "png")
    assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    # The 3D model in its node temperatures: the hottest by default, then a chosen time.
    widget.tabs.setCurrentWidget(widget.model_page)  # its tab makes the web view (2.12.0, TEST_CHANGES.md)
    assert widget.model_view is not None
    hot = widget.part_temperatures()
    battery = next(c for c in widget.analysis.cases if c.name == widget.case_combo.currentText())
    assert hot["battery"] == pytest.approx(battery.temperature_c("battery").max())
    widget.colour_combo.setCurrentText("At a time")
    widget.time_slider.setValue(3)
    assert widget.part_temperatures()["battery"] == pytest.approx(battery.temperature_c("battery")[3])
    assert widget.time_label.text().endswith(" h") and widget.time_slider.isEnabled()
    # Studies on the case shown: a sweep, a sensitivity (one parameter), a Monte Carlo into the Monte Carlo view.
    widget.case_combo.setCurrentText("cold")
    widget.sweep_path.setText("faces[battery].emissivity")
    widget.sweep_values.setText("0.5, 0.9")
    widget.run_sweep()
    qtbot.waitUntil(lambda: widget._study_worker is None and not widget.study_table.isHidden(), timeout=120000)
    assert widget.study_table.row_count() == 2 and widget.study_label.text().startswith("Sweep of faces[battery]")
    monkeypatch.setattr("spacemissionstudio.thermal.sweeps.default_parameters",
                        lambda thermal: ["dissipations[battery-loss].power_w"])
    widget.run_sensitivity()
    qtbot.waitUntil(lambda: widget._study_worker is None and "Sensitivity" in widget.study_label.text(),
                    timeout=120000)
    assert widget.study_table.row_count() == 1
    assert not widget.monte_carlo_button.isEnabled()  # no monte_carlo section
    sc.thermal.monte_carlo = ThermalMonteCarloConfig(3, 1, "nominal", [ThermalDispersionConfig(
        "dissipations[battery-loss].power_w", 1.0)])
    saved = []
    widget.monte_carlo_saved.connect(saved.append)
    widget.run_monte_carlo(tmp_path / "mc")
    qtbot.waitUntil(lambda: widget._study_worker is None and bool(saved), timeout=120000)
    assert saved == [str(tmp_path / "mc")] and (tmp_path / "mc" / "batch_results.json").exists()
    widget.set_run(None, None)
    assert timeline.events == [e for e in timeline.events if e.kind != THERMAL_LIMIT]


def test_the_spacecraft_editor_keeps_the_thermal_model(qtbot):
    """Template 32's spacecraft with a thermal model comes back from the
    spacecraft editor with the same section; the 3D model tab holds it and
    a problem in it opens its table."""
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog

    sc = load_scenario(_TEMPLATE).spacecraft[0]
    sc.thermal = _thermal(sc)
    dialog = SpacecraftEditorDialog(config=copy.deepcopy(sc))
    qtbot.addWidget(dialog)
    assert dialog.to_dataclass().thermal == sc.thermal
    assert dialog.field_widget("thermal.heaters[0].power_w") is dialog.thermal_group.tables["heaters"]


def test_the_model_figure_colours_parts_by_their_temperature():
    """Each part in its temperature's colour on the scale (the coldest at
    one end, the hottest at the other), a part without one grey, and a
    colour bar over the range; without temperatures, the parts' own
    colours."""
    from spacemissionstudio.gui.model_view_widget import model_figure, temperature_color
    from spacemissionstudio.model3d import model as model3d

    sc = load_scenario(_TEMPLATE).spacecraft[0]
    derived = model3d.derive(sc.model, _TEMPLATE.parent)
    figure = model_figure(derived, temperatures={"bus": -10.0, "array +y": 80.0, "array -y": 35.0})
    meshes = {trace.name: trace for trace in figure.data if trace.type == "mesh3d"}
    assert meshes["bus"].color == temperature_color(-10.0, -10.0, 80.0)
    assert meshes["array +y"].color == temperature_color(80.0, -10.0, 80.0) != meshes["bus"].color
    assert meshes["dish"].color == "rgb(160,160,160)"
    bar = next(trace for trace in figure.data if trace.name == "temperature")
    assert bar.marker.showscale and (bar.marker.cmin, bar.marker.cmax) == (-10.0, 80.0)
    plain = {trace.name: trace for trace in model_figure(derived).data if trace.type == "mesh3d"}
    assert plain["bus"].color != meshes["bus"].color
