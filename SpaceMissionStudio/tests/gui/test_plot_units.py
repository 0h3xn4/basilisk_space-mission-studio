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
"""The plots' units (UI audit B10, UI-12): with Settings > Appearance >
Plot units "Display units (km, °, h)" a position axis reads km, angles and
rates degrees and time hours; "As recorded" reads the SI unit each series
records. Axis titles carry the unit as the window writes it ("[°]"). The
exported data never changes with the choice."""

import numpy as np
import pytest

from spacemissionstudio.engine.results import ResultSet, TimeSeries
from spacemissionstudio.gui import units
from spacemissionstudio.plot_categories import shown

pytestmark = pytest.mark.requires_gui

_T_S = np.linspace(0.0, 7200.0, 5)  # [s]


def _series(name, columns, units_text, scale=1.0):
    return TimeSeries(name, _T_S, columns, np.outer(np.linspace(1.0, 2.0, len(_T_S)), np.ones(len(columns))) * scale,
                      units=units_text)


def _result() -> ResultSet:
    result = ResultSet(scenario_name="demo")
    result.add(_series("sat-1.position_N", ("x", "y", "z"), "m", 7.0e6))
    result.add(_series("sat-1.velocity_N", ("x", "y", "z"), "m/s", 7.5e3))
    result.add(_series("sat-1.body_rate_omega_BN_B", ("x", "y", "z"), "rad/s", 1.0e-3))
    result.add(_series("sat-1.rw_speeds", ("wheel_0", "wheel_1"), "rad/s", 100.0))
    result.add(_series("sat-1.control_torque", ("x", "y", "z"), "N*m", 1.0e-4))
    result.add(_series("sat-1.battery_charge", ("charge",), "W*hr", 50.0))
    result.add(_series("sat-1.orbit_elements.inclination", ("i",), "rad", 1.7))
    return result


def test_the_display_units_are_km_degrees_and_rpm_and_as_recorded_is_si():
    """Each series in the two choices: (unit, factor) in the display units,
    then as recorded."""
    result = _result()
    result.add(_series("sat-1.sensor.imu-1.gyro", ("x", "y", "z"), "rad/s", 1.0e-3))
    result.add(_series("ephemeris.sun.position_N", ("x", "y", "z"), "m", 1.5e11))
    expected = {
        "sat-1.position_N": (("km", 1e-3), ("m", 1.0)),
        "ephemeris.sun.position_N": (("km", 1e-3), ("m", 1.0)),
        "sat-1.velocity_N": (("m/s", 1.0), ("m/s", 1.0)),  # the user's request: velocity in m/s
        "sat-1.body_rate_omega_BN_B": (("deg/s", 180.0 / np.pi), ("rad/s", 1.0)),
        "sat-1.sensor.imu-1.gyro": (("deg/s", 180.0 / np.pi), ("rad/s", 1.0)),
        "sat-1.rw_speeds": (("RPM", 30.0 / np.pi), ("rad/s", 1.0)),
        "sat-1.orbit_elements.inclination": (("deg", 180.0 / np.pi), ("rad", 1.0)),
    }
    for name, (display, recorded) in expected.items():
        series = result.series[name]
        for found, (unit, factor) in ((shown(name, series), display), (shown(name, series, recorded=True), recorded)):
            assert (found.unit, found.factor) == (unit, pytest.approx(factor)), name


def test_a_position_plot_reads_km_and_follows_the_setting(qtbot):
    """UI-12: the position axis was in m although Plot units said km. With
    the display units it reads "Position [km]" and the values are in km,
    over hours; as recorded, "Position [m]" over seconds."""
    from spacemissionstudio.gui.results_widget import ResultsWidget

    result = _result()
    raw_m = result.series["sat-1.position_N"].data[:, 0]
    for choice, title, factor, x_title in (("display", "Position [km]", 1e-3, "Elapsed time since t0, TDB [h]"),
                                           ("recorded", "Position [m]", 1.0, "Elapsed time since t0, TDB [s]")):
        units.set_plot_units(choice)
        widget = ResultsWidget()
        qtbot.addWidget(widget)
        widget.set_result(result)
        widget.show_series("sat-1.position_N")
        assert widget.figure.layout.yaxis.title.text == title
        assert widget.figure.layout.xaxis.title.text == x_title
        np.testing.assert_allclose(np.asarray(widget.figure.data[0].y), raw_m * factor)


def test_axis_titles_carry_the_unit_as_the_window_writes_it(qtbot):
    """"[deg]" reads "[°]", "N*m" "N·m", "W*hr" "Wh", a rate "°/s"; an axis
    without a name keeps "[-]"."""
    from spacemissionstudio.gui.results_widget import ResultsWidget

    widget = ResultsWidget()
    qtbot.addWidget(widget)
    widget.set_result(_result())
    for name, title in (("sat-1.orbit_elements.inclination", "Inclination [°]"),
                        ("sat-1.control_torque", "Torque [N·m]"), ("sat-1.battery_charge", "Charge [Wh]"),
                        ("sat-1.body_rate_omega_BN_B", "Angular rate [°/s]"),
                        ("sat-1.rw_speeds", "Wheel speed [RPM]")):
        widget.show_series(name)
        assert widget.figure.layout.yaxis.title.text == title, name
    assert units.axis_title("", "-") == "[-]" and units.axis_title("Mode", "-") == "Mode [-]"
    assert units.axis_title("", "") is None


def test_the_plot_units_leave_the_exported_data_unchanged(qtbot, tmp_path, monkeypatch, reported):
    """The CSV files are the same bytes with either choice, and the same as
    the result's own export: the units change only the display."""
    from PySide6.QtWidgets import QFileDialog

    from spacemissionstudio.gui.results_widget import ResultsWidget

    result = _result()
    reference = tmp_path / "reference"
    reference.mkdir()
    result.export_csv(reference)
    for choice in ("display", "recorded"):
        units.set_plot_units(choice)
        folder = tmp_path / choice
        folder.mkdir()
        widget = ResultsWidget()
        qtbot.addWidget(widget)
        widget.set_result(result)
        widget.show_series("sat-1.position_N")
        monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, f=folder, **k: str(f)))
        count = len(reported)
        widget._on_export()
        qtbot.waitUntil(lambda c=count: len(reported) > c, timeout=10000)
        for path in sorted(reference.glob("*.csv")):
            assert (folder / path.name).read_bytes() == path.read_bytes(), (choice, path.name)
    assert len(list(reference.glob("*.csv"))) == len(result.series)
