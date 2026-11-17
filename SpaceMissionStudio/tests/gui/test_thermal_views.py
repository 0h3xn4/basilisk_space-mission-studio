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
"""Run › Thermal's results and the temperatures on Results › 3D View
(2.12.0, decisions T-40 to T-42): the plot is drawn at its own aspect
ratio at any view size, made at the view's size and in the theme by a
worker, again after a resize and a theme switch, while Save SVG/PNG keep
2.11.0's pictures; the page is tabs that fit 1280 x 720 in both themes,
every control of 2.11.0 still reachable; the findings go to the Problems
panel; on the 3D View each part takes its thermal node's colour at the
frame shown, following playback and the time cursor, with a colour bar;
nothing heavy runs on the GUI thread."""

import json
import threading
import time
import xml.etree.ElementTree as ET
from types import SimpleNamespace as NS

import numpy as np
import pytest
from PySide6.QtCore import QRectF, QSize

pytestmark = pytest.mark.requires_gui

_GUI_THREAD_MS = 50.0  # [ms] CLAUDE.md "Never freeze": nothing longer on the GUI thread
_SVG_WIDTH, _SVG_HEIGHT = 900, 420  # [px] the exported picture (T-31)


def _svg(width: int = _SVG_WIDTH, height: int = _SVG_HEIGHT) -> str:
    return (f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} "
            f"{height}'><rect width='{width}' height='{height}' fill='#808080'/></svg>")


def _size(svg: str) -> tuple[int, int]:
    root = ET.fromstring(svg)
    return int(root.get("width")), int(root.get("height"))


# -- the plot view: never stretched -----------------------------------------------------
@pytest.mark.parametrize("width, height", [(1400, 380), (600, 600), (900, 420), (320, 900), (1913, 241)])
def test_the_plot_keeps_its_aspect_ratio_at_every_size(qtbot, width, height):
    """2.11.0 stretched a 900 x 420 picture over 1400 x 380 px (x 1.56,
    y 0.90): text 1.7 times too wide. Now it is drawn at its own aspect
    ratio, as large as fits, centred, at every size of the view."""
    from spacemissionstudio.gui.svg_plot import SvgPlotView

    view = SvgPlotView("plot")
    qtbot.addWidget(view)
    view.load(_svg())
    view.resize(width, height)
    view.show()
    qtbot.waitExposed(view)
    rect = view.target_rect()
    assert rect.width() / rect.height() == pytest.approx(_SVG_WIDTH / _SVG_HEIGHT, rel=1e-9)
    assert QRectF(view.rect()).adjusted(-0.01, -0.01, 0.01, 0.01).contains(rect)
    assert rect.width() == pytest.approx(width) or rect.height() == pytest.approx(height)  # as large as fits
    assert rect.center().x() == pytest.approx(width / 2.0) and rect.center().y() == pytest.approx(height / 2.0)
    image = view.grab().toImage()  # drawn there: grey inside, nothing outside
    inside, corner = image.pixelColor(int(rect.center().x()), int(rect.center().y())), image.pixelColor(0, 0)
    assert inside.name() == "#808080"
    if rect.left() > 2 or rect.top() > 2:
        assert corner.name() != "#808080"


def test_a_resize_asks_for_a_new_picture_once_the_size_holds_still(qtbot):
    from spacemissionstudio.gui.svg_plot import SETTLE_MS, SvgPlotView

    view = SvgPlotView("plot")
    qtbot.addWidget(view)
    view.resize(800, 400)
    view.show()
    asked = []
    view.size_settled.connect(lambda: asked.append(view.size()))
    for width in (810, 820, 830, 840):
        view.resize(width, 400)
    assert asked == []  # a drag of the window's edge: nothing yet
    qtbot.waitUntil(lambda: bool(asked), timeout=SETTLE_MS * 8)
    assert asked == [QSize(840, 400)]


# -- Run › Thermal ---------------------------------------------------------------------
@pytest.fixture(scope="module")
def solved():
    """Template 33 (the 150 kg microsatellite with its thermal model) run
    for 0.07 days and solved without heater sizing: four cases."""
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


def _picture_made(widget) -> bool:
    plot = widget.temperature_plot
    return bool(plot.svg()) and not plot.needs_picture() and widget._plot_worker is None


@pytest.mark.requires_basilisk
def test_the_screen_plot_is_made_at_the_view_s_size_in_the_theme_by_a_worker(qtbot, solved, monkeypatch):
    """The temperature plot fills its view without a stretch: its SVG is
    made at the view's size, in Inter and JetBrains Mono on the theme's
    surface, off the GUI thread; after a resize, a new one at the new size."""
    from spacemissionstudio.gui import svg_plot, thermal_widget
    from spacemissionstudio.gui.theme import TOKENS

    threads = []
    real = svg_plot.render_image

    def recording(*args, **kwargs):
        threads.append(threading.current_thread() is threading.main_thread())
        return real(*args, **kwargs)

    monkeypatch.setattr(thermal_widget, "render_image", recording)
    widget = _page(qtbot, solved)
    plot = widget.temperature_plot
    qtbot.waitUntil(lambda: _picture_made(widget), timeout=20000)
    assert threads and not any(threads)  # made in the worker only
    assert _size(plot.svg()) == (plot.width(), plot.height())
    rect = plot.target_rect()
    assert (rect.width(), rect.height()) == (pytest.approx(plot.width()), pytest.approx(plot.height()))
    root = ET.fromstring(plot.svg())
    assert root.get("font-family") == "Inter" and root.find("{http://www.w3.org/2000/svg}rect").get("fill") == \
        TOKENS["bg.surface"]
    assert "JetBrains Mono" in plot.svg()
    widget.resize(1000, 640)
    qtbot.waitUntil(lambda: _picture_made(widget) and _size(plot.svg()) == (plot.width(), plot.height()),
                    timeout=20000)
    assert plot.width() < 1000 and plot.height() < 640  # the new, smaller view's own size
    widget.node_combo.setCurrentText("battery")
    widget.tabs.setCurrentWidget(widget.flow_page)
    qtbot.waitUntil(lambda: bool(widget.flow_plot.svg()) and not widget.flow_plot.needs_picture()
                    and widget._plot_worker is None, timeout=20000)
    assert _size(widget.flow_plot.svg()) == (widget.flow_plot.width(), widget.flow_plot.height())
    assert "Heat flows into battery" in widget.flow_plot.svg()


@pytest.mark.requires_basilisk
def test_a_theme_switch_redraws_the_plot_in_the_new_theme(qtbot, solved, restored_theme):
    from spacemissionstudio.gui.theme import apply_theme, tokens

    widget = _page(qtbot, solved)
    qtbot.waitUntil(lambda: _picture_made(widget), timeout=20000)
    assert tokens.tokens("light")["bg.surface"] in widget.temperature_plot.svg()
    apply_theme(restored_theme, "dark")
    dark = tokens.tokens("dark")
    qtbot.waitUntil(lambda: _picture_made(widget) and dark["bg.surface"] in widget.temperature_plot.svg(),
                    timeout=20000)
    assert dark["text.primary"] in widget.temperature_plot.svg()
    apply_theme(restored_theme, "light")
    qtbot.waitUntil(lambda: _picture_made(widget) and tokens.tokens("light")["bg.surface"]
                    in widget.temperature_plot.svg(), timeout=20000)


@pytest.mark.requires_basilisk
def test_the_exports_are_still_2_11_s_pictures(qtbot, solved, tmp_path):
    """Save SVG writes thermal.plots' default text (900 x 420, white,
    DejaVu Sans), whatever the view's size and theme; Save writes it too."""
    from spacemissionstudio.thermal import plots

    widget = _page(qtbot, solved)
    case = widget.analysis.case(widget.case_combo.currentText())
    assert widget.temperature_svg == plots.temperature_svg(case)
    widget.node_combo.setCurrentText("battery")
    assert widget.temperature_svg == plots.temperature_svg(case, ["battery"], "battery")
    assert widget.flow_svg == plots.heat_flow_svg(case, "battery")
    path = widget.save_plot(tmp_path / "plot.svg", "svg")
    assert path.read_text(encoding="utf-8") == plots.temperature_svg(case, ["battery"], "battery")
    assert _size(path.read_text(encoding="utf-8")) == (_SVG_WIDTH, _SVG_HEIGHT)
    widget.save(tmp_path / "all")
    written = (tmp_path / "all" / "thermal_nominal_temperature.svg").read_text(encoding="utf-8")
    assert written == plots.temperature_svg(widget.analysis.case("nominal"))


@pytest.mark.requires_basilisk
@pytest.mark.parametrize("mode", ["light", "dark"])
def test_the_page_is_tabs_that_fit_1280_by_720(qtbot, solved, restored_theme, mode):
    """No group box and no scroll area: the toolbar, one status line, the
    case and node, then tabs; it fits 1280 x 720 in both themes, and
    every control of 2.11.0's page is on a tab and shown there."""
    from PySide6.QtWidgets import QGroupBox, QScrollArea

    from spacemissionstudio.gui.theme import apply_theme
    from spacemissionstudio.gui.thermal_widget import TABS

    apply_theme(restored_theme, mode)
    widget = _page(qtbot, solved)
    assert not widget.findChildren(QGroupBox) and not widget.findChildren(QScrollArea)
    assert [widget.tabs.tabText(i) for i in range(widget.tabs.count())] == list(TABS)
    hint = widget.minimumSizeHint()
    assert hint.width() <= 1280 and hint.height() <= 720
    assert widget.stack.currentWidget() is widget.tabs and widget.choices.isVisible()
    for control in (widget.spacecraft_combo, widget.size_check, widget.solve_button, widget.save_button,
                    widget.case_combo, widget.node_combo, widget.save_svg_button, widget.save_png_button):
        assert control.isVisible()  # above the tabs
    reached = {"Temperatures": (widget.temperature_plot,),
               "Heat flows": (widget.tables["flows"][1],),
               "Summary": (widget.summary_table,),
               "Heaters and radiators": (widget.tables["heaters"][1], widget.tables["radiators"][1]),
               "3D model": (widget.colour_combo, widget.time_slider, widget.view_3d_button),
               "Studies": (widget.sweep_path, widget.sweep_values, widget.sweep_button, widget.sensitivity_button,
                           widget.monte_carlo_button),
               "Notes": (widget.notes_list,)}
    for tab, controls in reached.items():
        widget.tabs.setCurrentIndex(list(TABS).index(tab))
        for control in controls:
            assert control.isVisible(), (tab, control)
            bottom = control.mapTo(widget, control.rect().bottomRight()).y()
            assert bottom <= widget.height(), (tab, control)
    assert widget.notes_list.notes  # the energy balance and the step check


@pytest.mark.requires_basilisk
def test_the_findings_go_to_the_problems_panel_with_one_line_on_the_page(qtbot, solved):
    widget = _page(qtbot, solved)
    findings = widget.analysis.findings()
    assert widget.problem_rows() == [("warning", str(f), str(f)) for f in findings]
    if findings:
        assert widget.findings_label.text().startswith(f"{len(findings)} finding")
        asked = []
        widget.problems_requested.connect(lambda: asked.append(True))
        widget.problems_button.click()
        assert asked == [True]
    changed = []
    widget.problems_changed.connect(lambda: changed.append(True))
    widget.set_run(None, None)
    assert widget.problem_rows() == [] and changed == [True]
    assert widget.stack.currentWidget() is widget.empty_state


@pytest.mark.requires_basilisk
def test_choosing_a_node_and_resizing_leave_the_gui_thread_free(qtbot, solved):
    """Choosing a case or a node, and resizing, ask the worker; the GUI
    thread spends less than 50 ms on each (2.11.0 drew the SVG there)."""
    widget = _page(qtbot, solved)
    qtbot.waitUntil(lambda: _picture_made(widget), timeout=20000)
    took = []
    for step in (lambda: widget.node_combo.setCurrentText("battery"),
                 lambda: widget.case_combo.setCurrentText("hot"),
                 lambda: widget.node_combo.setCurrentText("All nodes"),
                 lambda: widget.resize(1100, 700)):
        start = time.perf_counter()
        step()
        took.append(1000.0 * (time.perf_counter() - start))
        qtbot.waitUntil(lambda: widget._plot_worker is None, timeout=20000)
    assert max(took) < _GUI_THREAD_MS, took


@pytest.mark.requires_basilisk
def test_the_main_window_holds_the_page_and_still_fits_1280_by_720(qtbot, monkeypatch, solved):
    """Run › Thermal is the page itself, no scroll area around it; with a
    result and its 3D model shown, the window still fits 1280 x 720, and
    the findings reach the Problems panel."""
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    index = [window.run_views.tabText(i) for i in range(window.run_views.count())].index("Thermal")
    assert window.run_views.widget(index) is window.thermal_widget
    window.resize(1280, 720)
    window.show()
    scenario, result, base_dir, analysis = solved
    window.open_path(base_dir / "33_microsat_thermal.json")  # the Problems panel lists an open scenario's
    page = window.thermal_widget
    page.set_run(scenario, result, base_dir)
    page.show_analysis(analysis)
    window.show_view(page)
    page.tabs.setCurrentWidget(page.model_page)
    qtbot.waitUntil(lambda: page.model_view is not None, timeout=20000)
    hint = window.minimumSizeHint()
    assert hint.width() <= 1280 and hint.height() <= 720
    assert window.size() == QSize(1280, 720)
    listed = {problem[1] for problem in window.problems_widget.problems}
    assert {str(f) for f in analysis.findings()} <= listed


# -- Results › 3D View ---------------------------------------------------------------------
_PERIOD_S = 5800.0  # [s] an invented orbit
_RADIUS_M = 7000e3  # [m]


def _run_33():
    """Template 33's scenario (its 3D model and thermal nodes) with an
    invented circular orbit and attitude: 300 samples over one orbit."""
    from spacemissionstudio import api
    from spacemissionstudio.engine.results import ResultSet, TimeSeries

    path = api.template("33_microsat_thermal")
    scenario = api.load(path)
    name = scenario.spacecraft[0].name
    t = np.linspace(0.0, _PERIOD_S, 300)
    angle = 2.0 * np.pi * t / _PERIOD_S
    result = ResultSet(scenario_name=scenario.name)
    result.add(TimeSeries(f"{name}.position_N", t, ("x", "y", "z"),
                          np.column_stack([_RADIUS_M * np.cos(angle), _RADIUS_M * np.sin(angle), 0 * t]), units="m"))
    result.add(TimeSeries(f"{name}.attitude_sigma_BN", t, ("s1", "s2", "s3"),
                          np.column_stack([0 * t, 0 * t, np.tan(angle / 4.0)])))
    return scenario, result, path.parent


def _analysis(scenario):
    """An invented thermal result of template 33's spacecraft: two cases;
    in each, node k warms linearly from 10 k to 10 k + 40 degC (hot) or
    cools (cold) over the orbit."""
    sc = scenario.spacecraft[0]
    names = [node.name for node in sc.thermal.nodes]
    time_s = np.linspace(0.0, _PERIOD_S, 121)

    def case(name, sign):
        table = np.column_stack([10.0 * k + sign * 40.0 * time_s / _PERIOD_S for k in range(len(names))])
        return NS(name=name, time_s=time_s, network=NS(names=names), temperature_c=lambda n: table[:, names.index(n)])

    cases = [case("hot", 1.0), case("cold", -1.0)]
    return NS(spacecraft=sc.name, cases=cases, case=lambda n: next(c for c in cases if c.name == n),
              prepared=NS(spacecraft=sc))


def test_each_part_takes_its_node_s_colour_on_one_scale_per_case():
    """The table the page takes: per triangle its part's node; per frame
    each node's temperature, interpolated onto the frame's time, on the
    scale from the case's coldest to its hottest drawn node."""
    from spacemissionstudio.engine import scene3d
    from spacemissionstudio.gui.mission_view_widget import temperature_frames
    from spacemissionstudio.gui.theme.palettes import temperature_rgb

    scenario, result, base_dir = _run_33()
    scene = scene3d.build_scene(scenario, result, base_dir=base_dir)
    analysis = _analysis(scenario)
    table = temperature_frames(scene, analysis, "hot")
    craft = scene.crafts[0]
    names = analysis.cases[0].network.names
    node_of = {part: node.name for node in scenario.spacecraft[0].thermal.nodes for part in node.parts}
    expected = [names.index(node_of[craft.part_names[k]]) if craft.part_names[k] in node_of else -1
                for k in craft.part_of_triangle]
    assert table["triangles"] == expected and table["craft"] == 0 and len(table["colours"]) == len(scene.times_s)
    drawn = sorted({k for k in expected if k >= 0})
    case = analysis.cases[0]
    temperatures = np.column_stack([case.temperature_c(n) for n in names])
    assert table["low_c"] == pytest.approx(temperatures[:, drawn].min())
    assert table["high_c"] == pytest.approx(temperatures[:, drawn].max())
    for frame in (0, 150, len(scene.times_s) - 1):
        for node in drawn:
            value = np.interp(scene.times_s[frame], case.time_s, temperatures[:, node])
            fraction = (value - table["low_c"]) / (table["high_c"] - table["low_c"])
            assert table["colours"][frame][3 * node:3 * node + 3] == np.rint(temperature_rgb(fraction)).astype(
                int).tolist()
    hottest = max(drawn)  # warmest node: red at the end of the hot case, its colder start bluer
    end, start = table["colours"][-1][3 * hottest:3 * hottest + 3], table["colours"][0][3 * hottest:3 * hottest + 3]
    assert end[0] > end[2] and end[0] - end[2] > start[0] - start[2]
    other = NS(spacecraft="no such spacecraft", case=analysis.case, prepared=analysis.prepared)
    assert temperature_frames(scene, other, "hot") is None


def _js(qtbot, view, script):
    out = []
    view.web_view.page().runJavaScript(script, 0, out.append)
    qtbot.waitUntil(lambda: bool(out), timeout=20000)
    return out[0]


def _state(qtbot, view):
    return json.loads(_js(qtbot, view, "JSON.stringify(MV.state())"))


def _linear(rgb):
    value = np.asarray(rgb, dtype=float) / 255.0
    return np.where(value <= 0.04045, value / 12.92, ((value + 0.055) / 1.055) ** 2.4)


def _first_colour(table, frame):
    node = table["triangles"][0]
    return _linear(table["none"] if node < 0 else table["colours"][frame][3 * node:3 * node + 3])


def test_temperatures_on_the_3d_view_follow_the_time_cursor(qtbot):
    """With a thermal result of the run shown, the Colours list offers its
    cases; one colours the spacecraft frame by frame, as the slider and
    the time cursor move, with a colour bar in degC; Model colours puts
    the model back; a result of another run offers nothing."""
    from spacemissionstudio.gui.mission_view_widget import MODEL_COLOURS, MissionViewWidget
    from spacemissionstudio.gui.time_cursor import TimeCursor

    scenario, result, base_dir = _run_33()
    view = MissionViewWidget()
    qtbot.addWidget(view)
    cursor = TimeCursor()
    view.set_time_cursor(cursor)
    view.resize(1280, 720)
    view.show()
    assert not view.colour_combo.isEnabled()
    view.set_run(scenario, result, base_dir)
    qtbot.waitUntil(lambda: view.scene is not None, timeout=30000)
    qtbot.waitUntil(lambda: view._page_ready, timeout=60000)
    qtbot.waitUntil(lambda: _js(qtbot, view, "MV.ready === true && MV.style !== null") is True, timeout=60000)
    model = _state(qtbot, view)["crafts"][0]["meshColour"]
    assert [view.colour_combo.itemText(i) for i in range(view.colour_combo.count())] == [MODEL_COLOURS]
    assert not view.colour_combo.isEnabled() and view.temperature_bar.isHidden()
    analysis = _analysis(scenario)
    view.set_thermal(analysis, result)
    assert [view.colour_combo.itemText(i) for i in range(view.colour_combo.count())] == [
        MODEL_COLOURS, "Temperature: hot", "Temperature: cold"]
    assert view.colour_combo.isEnabled() and view.temperature_case() is None  # off until chosen
    assert view.show_temperatures("hot") and view.temperature_case() == "hot"
    qtbot.waitUntil(lambda: _state(qtbot, view)["temperatures"] is not None, timeout=20000)
    table = view._temperatures[0]
    assert _state(qtbot, view)["temperatures"] == {"craft": 0, "case": "hot", "frames": len(view.scene.times_s)}
    assert not view.temperature_bar.isHidden()
    assert view.temperature_bar.title_label.text() == "Temperature, hot case"
    assert view.temperature_bar.low_label.text() == f"{table['low_c']:.1f} °C"
    assert view.temperature_bar.high_label.text() == f"{table['high_c']:.1f} °C"
    np.testing.assert_allclose(_state(qtbot, view)["crafts"][0]["meshColour"], _first_colour(table, 0), atol=1e-6)
    for frame in (150, 299, 40):
        cursor.set_time(float(view.scene.times_s[frame]))
        assert view.slider.value() == frame
        np.testing.assert_allclose(_state(qtbot, view)["crafts"][0]["meshColour"], _first_colour(table, frame),
                                   atol=1e-6)
    view.slider.setValue(200)
    np.testing.assert_allclose(_state(qtbot, view)["crafts"][0]["meshColour"], _first_colour(table, 200), atol=1e-6)
    view.show_temperatures("cold")
    qtbot.waitUntil(lambda: _state(qtbot, view)["temperatures"]["case"] == "cold", timeout=20000)
    view.colour_combo.setCurrentText(MODEL_COLOURS)
    state = _state(qtbot, view)
    assert state["temperatures"] is None and view.temperature_bar.isHidden()
    np.testing.assert_allclose(state["crafts"][0]["meshColour"], model, atol=1e-6)
    view.set_thermal(analysis, object())  # solved on another run
    assert view.colour_combo.count() == 1 and not view.colour_combo.isEnabled()


def test_temperatures_on_the_3d_view_leave_the_gui_thread_free(qtbot, monkeypatch):
    """The colour table is made in a worker; choosing a case, moving the
    time cursor and playing take the GUI thread less than 50 ms each."""
    from spacemissionstudio.gui import mission_view_widget
    from spacemissionstudio.gui.mission_view_widget import MissionViewWidget
    from spacemissionstudio.gui.time_cursor import TimeCursor

    threads = []
    real = mission_view_widget.temperature_frames

    def recording(*args, **kwargs):
        threads.append(threading.current_thread() is threading.main_thread())
        return real(*args, **kwargs)

    monkeypatch.setattr(mission_view_widget, "temperature_frames", recording)
    scenario, result, base_dir = _run_33()
    view = MissionViewWidget()
    qtbot.addWidget(view)
    cursor = TimeCursor()
    view.set_time_cursor(cursor)
    view.resize(1280, 720)
    view.show()
    view.set_run(scenario, result, base_dir)
    qtbot.waitUntil(lambda: view.scene is not None and view._page_ready, timeout=60000)
    qtbot.waitUntil(lambda: _js(qtbot, view, "MV.ready === true") is True, timeout=60000)
    view.set_thermal(_analysis(scenario), result)
    took = []
    start = time.perf_counter()
    view.show_temperatures("hot")
    took.append(1000.0 * (time.perf_counter() - start))
    qtbot.waitUntil(lambda: view._temperatures is not None, timeout=20000)
    assert threads == [False]
    for frame in (10, 100, 250):
        start = time.perf_counter()
        cursor.set_time(float(view.scene.times_s[frame]))
        took.append(1000.0 * (time.perf_counter() - start))
    view.toggle_play()
    start = time.perf_counter()
    view._tick()
    took.append(1000.0 * (time.perf_counter() - start))
    view.pause()
    assert max(took) < _GUI_THREAD_MS, took
