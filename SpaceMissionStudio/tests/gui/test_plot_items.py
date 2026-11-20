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
"""The small plot items (UI audit, 2026-11-19; SRelD K-46): the event
bands of the Results plots take a neutral colour that no series uses; the
Timeline draws no event in the accent; a nearly constant series gets
short tick labels; and a reaction wheel's line carries the wheel's name.
The series, their columns and the exported files do not change."""

import math

import numpy as np
import pytest

pytestmark = pytest.mark.requires_gui

_T_S = np.linspace(0.0, 7200.0, 121)  # [s]


def _oklab_chroma(colour):
    """The OKLab chroma of ``#RRGGBB`` (0 for a grey)."""
    r, g, b = (int(colour[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
    r, g, b = (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b))
    lms = [v ** (1 / 3) for v in (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b,
                                  0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b,
                                  0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)]
    a = 1.9779984951 * lms[0] - 2.4285922050 * lms[1] + 0.4505937099 * lms[2]
    b = 0.0259040371 * lms[0] + 0.7827717662 * lms[1] - 0.8086757660 * lms[2]
    return math.hypot(a, b)


def _reserved(t):
    """The colours a chart item must not take: the accent and its steps,
    and every status colour."""
    from spacemissionstudio.gui.theme import tokens

    return {t["accent"], t["accent.hover"], t["accent.pressed"]} | {
        t[f"status.{name}{part}"] for name in tokens.STATUSES[:-1] for part in ("", ".text")}


def _events_result():
    """One spacecraft with two eclipses, a mode change and a nearly constant
    osculating inclination (it moves by about 1e-11 degrees, as template 01's)."""
    from spacemissionstudio.engine.results import ResultSet, TimeSeries

    sunlight = np.where((_T_S % 3600.0) > 2400.0, 0.0, 1.0)  # [-] in shadow for the last third of each hour
    mode = (_T_S > 3600.0).astype(float)  # [-]
    inclination = math.radians(97.03) + 1e-13 * np.sin(_T_S / 600.0)  # [rad]
    result = ResultSet("demo")
    result.add(TimeSeries("sat-1.eclipse.illumination_factor", _T_S, ("illumination_factor",), sunlight[:, None]))
    result.add(TimeSeries("sat-1.comms_pointing.active_mode", _T_S, ("active_mode",), mode[:, None]))
    result.add(TimeSeries("sat-1.orbit_elements.inclination", _T_S, ("i",), inclination[:, None], units="rad"))
    return result


def _results_widget(qtbot):
    from spacemissionstudio.gui.results_widget import ResultsWidget

    widget = ResultsWidget()
    qtbot.addWidget(widget)
    return widget


def test_event_bands_take_a_neutral_colour_that_no_series_uses(qtbot, restored_theme):
    """In both themes every event band and mode-change line of a Results
    plot is the theme's ``chart.band``: a grey, not one of the eight
    series colours, the accent or a status colour; it keeps 3:1 against
    the plot's surface where it is drawn solid (the mode line)."""
    from spacemissionstudio.gui.theme import SERIES_COLORS, TOKENS, apply_theme, palettes, tokens

    for mode in tokens.MODES:
        apply_theme(restored_theme, mode)
        band = TOKENS["chart.band"]
        assert band not in palettes.CATEGORICAL[mode] and band not in _reserved(TOKENS), mode
        assert _oklab_chroma(band) < 0.02, (mode, band)  # neutral: no hue a series could share
        assert tokens.contrast(band, TOKENS["bg.surface"]) >= 3.0, mode
        widget = _results_widget(qtbot)
        widget.set_result(_events_result(), "2030-01-01T08:30:00")
        widget.show_series("sat-1.orbit_elements.inclination")
        shapes = [shape for shape in widget.figure.layout.shapes if str(shape.name).startswith("event-")]
        bands = [shape for shape in shapes if shape.type == "rect"]
        lines = [shape for shape in shapes if shape.type == "line"]
        assert len(bands) == 2 and len(lines) == 2, mode  # a line at the start of each mode span
        for shape in bands:
            assert shape.fillcolor == band and shape.fillcolor not in SERIES_COLORS, mode
        for shape in lines:
            assert shape.line.color == band and shape.line.color not in SERIES_COLORS, mode


def test_the_timeline_draws_no_event_in_the_accent(qtbot, restored_theme):
    """The accent is for the primary action, selection and focus. Every
    event kind, the model analyses', the thermal limits' and the plan's
    included, takes a colour that is not the accent or a status colour,
    with 3:1 against the timeline's surface; a timeline of those events
    without a time cursor has no pixel in the accent."""
    from PySide6.QtGui import QColor

    from spacemissionstudio.engine import events as event_model
    from spacemissionstudio.gui.event_timeline_widget import GanttView, kind_colour
    from spacemissionstudio.gui.theme import TOKENS, apply_theme, tokens

    kinds = event_model.KINDS + event_model.MODEL_KINDS + event_model.THERMAL_KINDS + event_model.PLAN_KINDS
    for mode in tokens.MODES:
        apply_theme(restored_theme, mode)
        for kind in kinds:
            colour = kind_colour(kind)
            assert colour not in _reserved(TOKENS), (mode, kind, colour)
            assert tokens.contrast(colour, TOKENS["bg.surface"]) >= 3.0, (mode, kind)
        extra = event_model.MODEL_KINDS + event_model.THERMAL_KINDS + event_model.PLAN_KINDS
        shown = [event_model.Event(kind, "sat-1", 600.0 * i, 600.0 * i + 1800.0, kind) for i, kind in enumerate(extra)]
        view = GanttView()
        qtbot.addWidget(view)
        view.resize(800, 200)  # [px]
        view.set_events(shown, 7200.0)
        image = view.grab().toImage()
        accent = QColor(TOKENS["accent"]).rgb()
        drawn = {image.pixel(x, y) for x in range(0, image.width(), 2) for y in range(0, image.height(), 2)}
        assert accent not in drawn, mode
        assert QColor(kind_colour(event_model.BLINDING)).rgb() in drawn, mode  # the bars were drawn


def _tick_labels(low, high):
    """The tick labels a Plotly axis from ``low`` to ``high`` shows with
    exponentformat "none" at its densest (ten ticks): a step of 1, 2 or 5
    times a power of ten, written with as many decimals as the step needs."""
    rough = (high - low) / 10.0
    power = 10.0 ** math.floor(math.log10(rough))
    step = next(power * m for m in (1.0, 2.0, 5.0, 10.0) if power * m >= rough)
    decimals = max(0, -math.floor(math.log10(step) + 1e-9))
    first = math.ceil(low / step)
    return [f"{k * step:,.{decimals}f}" for k in range(first, int(math.floor(high / step)) + 1)]


def _y_span(figure):
    """What the y axis's autorange spans: the data and what the axis
    includes besides them."""
    values = np.concatenate([np.asarray(trace.y, dtype=float) for trace in figure.data])
    low, high = float(np.nanmin(values)), float(np.nanmax(values))
    include = figure.layout.yaxis.autorangeoptions.include
    if include:
        low, high = min(low, *include), max(high, *include)
    return low, high


def test_a_nearly_constant_angle_gets_short_tick_labels(qtbot):
    """An osculating inclination that moves by 1e-11 degrees read
    "97.03000000000399". The axis now spans at least a millionth of the
    value, so each tick label has at most ten characters; the plotted
    values are the series' own, and a series that moves keeps Plotly's
    own range."""
    widget = _results_widget(qtbot)
    result = _events_result()
    widget.set_result(result)
    widget.show_series("sat-1.orbit_elements.inclination")
    figure = widget.figure
    labels = _tick_labels(*_y_span(figure))
    assert labels and max(len(label) for label in labels) <= 10, labels
    np.testing.assert_array_equal(np.asarray(figure.data[0].y),
                                  result.series["sat-1.orbit_elements.inclination"].data[:, 0] * (180.0 / math.pi))
    assert figure.layout.yaxis.autorange in (None, True)  # the user's zoom and double-click still work
    widget.show_series("sat-1.eclipse.illumination_factor")
    assert not widget.figure.layout.yaxis.autorangeoptions.include


def _wheel_result():
    from spacemissionstudio.engine.results import ResultSet, TimeSeries

    result = ResultSet("demo")
    speeds = np.outer(np.linspace(10.0, 20.0, len(_T_S)), [1.0, -1.0, 0.5])  # [rad/s]
    result.add(TimeSeries("sat-1.rw_speeds", _T_S, ("wheel_0", "wheel_1", "wheel_2"), speeds, units="rad/s"))
    return result


def test_the_wheel_lines_carry_the_wheels_names(qtbot, tmp_path, monkeypatch, reported):
    """The scenario's reaction wheels, in the order of its actuators, name
    the lines of the wheel-speed plot, the readout and a compared run's
    lines. The series keeps its columns wheel_0 to wheel_2, and the
    window's CSV export is the same bytes as the result's own."""
    from datetime import UTC, datetime

    from PySide6.QtWidgets import QFileDialog

    from spacemissionstudio.engine.series_names import device_column_labels
    from spacemissionstudio.gui.run_history import RunRecord
    from spacemissionstudio.schema.scenario import ActuatorConfig, OrbitIC, Scenario, SpacecraftConfig

    orbit = OrbitIC(type="cartesian", position_km=[7000, 0, 0], velocity_km_s=[0, 7.5, 0])
    wheels_and_a_thruster = [ActuatorConfig(kind="reaction_wheel", name="rw-x"),
                             ActuatorConfig(kind="thruster", name="desat-1"),
                             ActuatorConfig(kind="reaction_wheel", name="rw-y"),
                             ActuatorConfig(kind="reaction_wheel", name="rw-z")]
    scenario = Scenario(name="demo", epoch_utc="2030-01-01T00:00:00",
                        spacecraft=[SpacecraftConfig(name="sat-1", orbit=orbit, actuators=wheels_and_a_thruster)])
    labels = device_column_labels(scenario)
    assert labels == {"sat-1.rw_speeds": {"wheel_0": "rw-x", "wheel_1": "rw-y", "wheel_2": "rw-z"}}
    assert device_column_labels(scenario.to_dict()) == labels  # a kept run's scenario is a dict

    widget = _results_widget(qtbot)
    widget.set_device_labels(labels)
    result = _wheel_result()
    widget.set_result(result)
    widget.show_series("sat-1.rw_speeds")
    assert [trace.name for trace in widget.figure.data] == ["rw-x", "rw-y", "rw-z"]
    assert widget.figure.layout.showlegend
    widget._hover_time_s = 3600.0  # [s] the pointer over the plot
    widget._update_readout()
    table = widget.readout.table
    rows = [table.item(row, 0).text().strip() for row in range(table.rowCount()) if table.item(row, 0) is not None]
    assert rows[1:] == ["rw-x", "rw-y", "rw-z"]

    finished = datetime.now(UTC)
    shown, other = (RunRecord(number, scenario.to_dict(), _wheel_result(), "", finished) for number in (2, 1))
    widget.set_runs([other, shown], shown)
    widget.compare_combo.setCurrentIndex(widget.compare_combo.findData(1))
    assert [trace.name for trace in widget.figure.data] == ["rw-x (Run 2)", "rw-y (Run 2)", "rw-z (Run 2)",
                                                            "rw-x (Run 1)", "rw-y (Run 1)", "rw-z (Run 1)"]

    assert result.series["sat-1.rw_speeds"].columns == ("wheel_0", "wheel_1", "wheel_2")
    reference, exported = tmp_path / "reference", tmp_path / "exported"
    reference.mkdir()
    exported.mkdir()
    result.export_csv(reference)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: str(exported)))
    count = len(reported)
    widget._on_export()
    qtbot.waitUntil(lambda: len(reported) > count, timeout=10000)
    for path in sorted(reference.glob("*.csv")):
        assert (exported / path.name).read_bytes() == path.read_bytes(), path.name
    assert "wheel_0" in next(reference.glob("*.csv")).read_text(encoding="utf-8")


def test_the_compare_tab_names_the_wheels_too(qtbot, tmp_path):
    """Results › Compare offers a wheel-speed column by the wheel's name
    from the runs' scenario, as the plots do."""
    from datetime import datetime

    from spacemissionstudio.gui.compare_widget import CompareWidget
    from spacemissionstudio.gui.run_history import RunHistory

    scenario = {"name": "demo", "spacecraft": [{"name": "sat-1", "actuators": [
        {"kind": "reaction_wheel", "name": "rw-x"}, {"kind": "reaction_wheel", "name": "rw-y"},
        {"kind": "reaction_wheel", "name": "rw-z"}]}]}
    widget = CompareWidget()
    qtbot.addWidget(widget)
    history = RunHistory(store_root=tmp_path / "runs")
    for minute in (0, 5):
        history.add(scenario, _wheel_result(), "2030-01-01T00:00:00", finished=datetime(2026, 11, 20, 9, minute))
    widget.set_runs(history.runs, history.runs[-1], None, history.store_root)
    widget.series_combo.setCurrentIndex(widget.series_combo.findData("sat-1.rw_speeds"))
    assert [widget.column_combo.itemText(i) for i in range(widget.column_combo.count())] == ["rw-x", "rw-y", "rw-z"]
