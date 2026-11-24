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

"""Each bundled template, run for real, does what its description says.

Several templates shipped claims their own setup could not deliver (16
failed at its first command, 19 had no contact for 8 h, 20's sensor never
saw the Sun, 07's battery never moved). The only all-template Basilisk
test strips the Mission Sequence and runs two minutes, so none of that
was caught. These tests run each template as shipped -- shortened only
where the claim allows -- and check its headline claim.
"""

from pathlib import Path

import numpy as np
import pytest

from spacemissionstudio.schema import load_scenario

pytestmark = pytest.mark.requires_basilisk

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "spacemissionstudio" / "scenarios" / "templates"


def _template(prefix):
    return load_scenario(next(_TEMPLATES_DIR.glob(f"{prefix}_*.json")))


def _run(scenario, duration_days=None):
    from spacemissionstudio.engine.service import SimulationService

    if duration_days is not None:
        scenario.sim_settings.duration_days = duration_days
    return SimulationService(scenario).run()


def _at(series, t_s, column=0):
    return float(series.data[int(np.argmin(np.abs(series.time_s - t_s))), column])


def test_16_lambert_transfer_lands_on_its_target():
    """Used to fail at its first command (a report before any propagate);
    the description promises arrival within about 2 m."""
    from spacemissionstudio.engine.mission_engine import MissionEngine

    scenario = _template("16")
    _result, summary = MissionEngine(scenario).run()
    assert [r.label for r in summary.reports] == ["Before transfer", "After transfer (should match target_position_m)"]
    target = np.array(scenario.mission_sequence[2].params["target_position_m"])  # [m]
    assert np.linalg.norm(summary.reports[1].values["sat-1.position_N"] - target) < 5.0  # [m]


def test_19_first_berlin_pass_comes_early_and_switches_the_pointing_mode():
    """Used to start at midnight UTC: no contact for the first 8 h."""
    result = _run(_template("19"), duration_days=25.0 / 1440.0)  # [day] the first pass only
    access = result.series["berlin-gs.access_to_leo-comms-1.has_access"]
    visible = access.data[:, 0] > 0.5
    assert visible.any()
    first_s = float(access.time_s[np.argmax(visible)])  # [s]
    assert 5 * 60 <= first_s <= 15 * 60
    mode = result.series["leo-comms-1.comms_pointing.active_mode"]
    assert _at(mode, first_s + 120.0) == 1.0  # pointing at the station during the pass
    assert _at(mode, first_s - 120.0) == 0.0  # Sun pointing before it


def test_20_thermal_sensor_heats_in_sunlight_and_cools_in_eclipse():
    """therm-1 used to face +X, edge-on to the Sun once Sun-pointed."""
    result = _run(_template("20"), duration_days=70.0 / 1440.0)  # [day] first sunlit arc and eclipse
    therm = result.series["sat-1.sensor.therm-1"]
    start, sunlit_end, eclipse_end = _at(therm, 60.0), _at(therm, 22 * 60.0), _at(therm, 57 * 60.0)  # [C]
    assert sunlit_end > start + 10.0
    assert eclipse_end < sunlit_end - 10.0
    motor = result.series["sat-1.actuator.rw-1.motor_temperature"].data[:, 0]  # [C]
    assert 0.01 < motor.max() - 20.0 < 0.2  # "only ~0.05 C above its 20 C ambient"


def test_07_battery_charges_in_sunlight_and_drains_in_eclipse():
    """Used to start full with a 0 W bus load: flat at 80 Wh all run."""
    result = _run(_template("07"), duration_days=60.0 / 1440.0)  # [day]
    charge = result.series["sat-1.battery_charge"]
    assert _at(charge, 20 * 60.0) > _at(charge, 0.0) + 5.0  # [Wh] charging
    assert _at(charge, 55 * 60.0) < _at(charge, 25 * 60.0) - 3.0  # [Wh] eclipse at the 12 W bus load
    sun = result.series["sat-1.sun_heading_body"]
    assert sun.data[-1, 2] > 0.99  # +Z settled on the Sun


@pytest.mark.slow
def test_03_geo_slot_is_held_in_longitude_and_inclination():
    """A real 45-day run: east-west burns at days 12.5, 21.4, 31.1, 36.9, north-
    south burns at days 16.4 and 30.4. 32 days covers three and two of them."""
    result = _run(_template("03"), duration_days=32.0)  # [day]
    prefix = "geo-sat-1.geo_station_keeping."
    longitude = np.degrees(result.series[prefix + "longitude"].data[:, 1])  # [deg] one-day fit
    assert 9.945 < np.nanmin(longitude) and np.nanmax(longitude) < 10.055  # [deg] box 10 +/- 0.05
    inclination = np.degrees(result.series[prefix + "inclination"].data[:, 0])  # [deg]
    assert inclination[0] < 1e-3  # starts in Earth's true equator
    assert inclination.max() < 0.053  # [deg] limit 0.05
    burns = result.series[prefix + "burn_on"].data > 0.5
    starts = [np.count_nonzero(np.diff(burns[:, col].astype(int)) == 1) for col in (0, 1)]
    assert starts == [3, 2]  # [east-west, north-south]


def test_10_uncontrolled_spacecraft_drifts_under_gravity_gradient():
    """Its attitude used to be unrecorded."""
    result = _run(_template("10"), duration_days=2.0 / 24.0)  # [day]
    sigma = result.series["sat-1.attitude_sigma_BN"]
    assert np.linalg.norm(sigma.data[0]) < 1e-6
    assert np.linalg.norm(sigma.data[-1]) > 0.1


def test_12_thrusters_dump_wheel_momentum():
    """Template 12 fires its thrusters three times and slows the first wheel by
    over 10 %."""
    result = _run(_template("12"))
    firing = result.series["sat-1.thruster_on_time"].data.max(axis=1) > 0.0
    assert np.count_nonzero(np.diff(firing.astype(int)) == 1) == 3  # "three in the first 4 minutes"
    speeds = result.series["sat-1.rw_speeds"].data  # [rad/s]
    assert speeds[-1, 0] < 0.9 * speeds[0, 0]


def test_17_fuel_tank_drains_about_as_described():
    """About 12 g drains while the attitude settles in the first 3 minutes,
    about 14 g in all. On an earlier 10 kg*m^2 bus the thrusters' on-times
    stayed under their 20 ms minimum: no propellant used at all. With the
    integrator's default tolerance (until 2026-10-28) a 0.5 s step skipped
    most of the 20-40 ms pulses and only 0.3 g drained; a run at 1e-12
    drains 13.6 g."""
    result = _run(_template("17"))
    fuel = result.series["sat-1.fuel_mass_remaining"]
    drained = fuel.data[0, 0] - fuel.data[:, 0]  # [kg]
    assert 10e-3 <= drained[-1] <= 20e-3  # [kg] "about 12 g ... about 2 g more"
    assert drained[np.searchsorted(fuel.time_s, 180.0)] >= 0.75 * drained[-1]  # most of it while settling


def test_11_thrusters_settle_the_attitude_within_a_few_minutes():
    """Template 11 fires real pulses and settles within a few degrees in four
    minutes."""
    result = _run(_template("11"), duration_days=4.0 / 1440.0)  # [day]
    assert result.series["sat-1.thruster_on_time"].data.max() > 0.02  # [s] real pulses, above the minimum on-time
    sigma = result.series["sat-1.attitude_sigma_BN"]
    assert np.linalg.norm(sigma.data[-1]) < 0.03  # within a few degrees ("about 2 minutes")


def test_08_prograde_burn_raises_the_orbit_on_the_far_side():
    """Template 08's 50 m/s prograde burn raises the semi-major axis by 60 to
    100 km and makes the orbit elliptical."""
    from spacemissionstudio.engine.mission_engine import MissionEngine

    _result, summary = MissionEngine(_template("08")).run()
    before, after = summary.reports
    a_before = before.values["sat-1.orbit_elements.semi_major_axis"][0]  # [m]
    a_after = after.values["sat-1.orbit_elements.semi_major_axis"][0]  # [m]
    # [m] vis-viva: +50 m/s prograde at 400 km raises a by ~88 km (osculating
    # snapshots, after half a day of drag and J2: ~76 km in a real run)
    assert 60e3 < a_after - a_before < 100e3
    assert after.values["sat-1.orbit_elements.eccentricity"][0] > 0.01  # now an ellipse


def test_13_torque_rods_steer_the_wheels_to_their_target_speeds():
    """Template 13's torque rods bring every wheel within 0.5 RPM of its
    target."""
    scenario = _template("13")
    result = _run(scenario)
    speeds_rpm = result.series["sat-1.rw_speeds"].data[-1] * 60.0 / (2.0 * np.pi)  # [RPM]
    targets_rpm = np.array(scenario.spacecraft[0].magnetic_momentum_management.wheel_speed_biases_rad_s) \
        * 60.0 / (2.0 * np.pi)  # [RPM]
    assert np.abs(speeds_rpm - targets_rpm).max() < 0.5  # [RPM] "within ~0.5 RPM"


def test_14_css_estimate_settles_on_the_sun_axis_and_is_lost_in_the_shadow():
    """The estimate settles near [0, 0, 1]; in Earth's shadow (minutes
    10 to 44) every sensor reads zero and the estimate is [0, 0, 0], and
    out of it the estimate is back at the end of the orbit."""
    result = _run(_template("14"))
    estimate = result.series["sat-1.sun_heading_body_estimated"]
    assert estimate.data[-1][2] / np.linalg.norm(estimate.data[-1]) > 0.98  # near [0, 0, 1]
    illumination = result.series["sat-1.eclipse.illumination_factor"]
    dark = illumination.data.ravel() == 0.0
    shadow_min = illumination.time_s[dark] / 60.0  # [min]
    assert 9.0 < shadow_min.min() < 11.0 and 43.0 < shadow_min.max() < 45.0  # [min]
    in_shadow = np.isin(estimate.time_s, illumination.time_s[dark])
    assert in_shadow.any() and not estimate.data[in_shadow].any()
    for i in range(1, 9):
        sensor = result.series[f"sat-1.sensor.css-{i}"]
        assert not sensor.data[np.isin(sensor.time_s, illumination.time_s[dark])].any()


def test_14_earths_albedo_pulls_the_estimate_off_the_sun():
    """With "Reflected sunlight on the sun sensors" on, the estimate in
    sunlight is about 16 deg off the Sun (median), up to 27 deg, and +Z
    follows it (the description's "Try changing" claim)."""
    scenario = _template("14")
    scenario.gravity.albedo = True
    result = _run(scenario)
    true = result.series["sat-1.sun_heading_body"]
    estimate = result.series["sat-1.sun_heading_body_estimated"].data
    lit = (np.linalg.norm(estimate, axis=1) > 0.0) & (result.series["sat-1.eclipse.illumination_factor"].data.ravel()
                                                      == 1.0)
    error_deg = np.degrees(np.arccos(np.clip(np.einsum(
        "ij,ij->i", estimate[lit] / np.linalg.norm(estimate[lit], axis=1)[:, None],
        true.data[lit] / np.linalg.norm(true.data[lit], axis=1)[:, None]), -1.0, 1.0)))
    assert 13.0 < np.median(error_deg) < 19.0 and 22.0 < error_deg.max() < 30.0  # [deg] "about 16", "up to 27"
    off_sun_deg = np.degrees(np.arccos(np.clip(true.data[:, 2] / np.linalg.norm(true.data, axis=1), -1.0, 1.0)))
    assert 22.0 < off_sun_deg[true.time_s > 600.0].max() < 30.0  # [deg] +Z follows the estimate


def test_21_off_centre_array_loads_the_wheels_unless_torque_rods_unload_them():
    """A real run: rods-off stores ~1.7 N*m*s by the end of the day (1.72,
    rw-x -815 RPM), rods-on keeps its wheels under ~20 RPM (18.7): January
    2030 on NASA MSFC's 50th-percentile prediction, Cd 3.0 (re-measured
    after F-07 and F-09, compliance/drag_remeasure.md)."""
    result = _run(_template("21"))
    js = 12.0 / (6000.0 * np.pi / 30.0)  # [kg*m^2] HR12 12 N*m*s at 6000 RPM
    stored = {name: np.linalg.norm(result.series[f"{name}.rw_speeds"].data[-1]) * js  # [N*m*s]
              for name in ("rods-off", "rods-on")}
    assert 1.5 < stored["rods-off"] < 1.9  # [N*m*s] "about 1.7 N*m*s stored by the end"
    rods_on_rpm = result.series["rods-on.rw_speeds"].data[-1] * 30.0 / np.pi  # [RPM]
    assert np.abs(rods_on_rpm).max() < 25.0  # [RPM] "stay under ~20 RPM"
    for name in ("rods-off", "rods-on"):
        sun = result.series[f"{name}.sun_heading_body"]
        assert sun.data[sun.time_s > 600.0, 2].min() > 0.99  # still Sun-pointed


def test_22_starter_has_four_berlin_passes_and_a_sun_synchronous_plane():
    """The starter's description: four Berlin passes in its day, the first
    10-18 min in, and the mean orbit plane turning ~1 deg a day."""
    result = _run(_template("22"))
    access = result.series["berlin-gs.access_to_my-sat.has_access"]
    visible = np.concatenate([[0], (access.data[:, 0] > 0.5).astype(int), [0]])
    starts = access.time_s[np.flatnonzero(np.diff(visible) == 1)]  # [s]
    assert len(starts) == 4
    assert 9 * 60 <= starts[0] <= 12 * 60  # [s]
    raan = result.series["my-sat.orbit_elements_mean.raan"]
    rate_deg_day = np.degrees(raan.data[-1, 0] - raan.data[0, 0]) / (raan.time_s[-1] / 86400.0)  # [deg/day]
    assert 0.9 < rate_deg_day < 1.1  # Sun-synchronous: 0.986 deg/day


def test_23_mission_sequence_reports_at_the_pass_and_the_wheels_unload():
    """Reports at pass start and end (about 10 and 18 min in); the wheels
    spin up to turn to the Sun, then the torque rods bring them back."""
    from spacemissionstudio.engine.mission_engine import MissionEngine

    result, summary = MissionEngine(_template("23")).run()
    assert [r.label for r in summary.reports] == ["Pass start", "Pass end"]
    start_s, end_s = (r.t_s for r in summary.reports)  # [s]
    assert 9 * 60 <= start_s <= 12 * 60 and 16 * 60 <= end_s <= 20 * 60
    margin = summary.reports[0].values["berlin-gs.access_to_smallsat-1.link_margin_db"][0]  # [dB]
    assert 8.0 < margin < 14.0  # "11 dB at the 10 deg edge of the pass"
    rpm = np.abs(result.series["smallsat-1.rw_speeds"].data) * 30.0 / np.pi  # [RPM]
    assert 200.0 < rpm.max() < 400.0  # "up to ~300 RPM"
    assert rpm[-1].max() < 5.0  # [RPM] "back near zero"
    assert result.series["smallsat-1.sun_heading_body"].data[-1, 2] > 0.99  # Sun-pointed


def test_24_mean_element_control_holds_tens_of_metres():
    """Within ~65 m after the first day, at a few tenths of a m/s; three of
    its fourteen days."""
    result = _run(_template("24"), duration_days=3.0)  # [day]
    error = result.series["follower-1.phasing_keeping.separation_error"]
    error_m = np.radians(error.data[:, 0]) * 6928.0e3  # [m] along-track arc on the chief's orbit
    assert np.abs(error_m[error.time_s > 86400.0]).max() < 80.0  # [m]
    delta_v = result.series["follower-1.phasing_keeping.delta_v"].data[-1, 0]  # [m/s]
    assert 0.1 < delta_v < 0.5  # [m/s] 0.20 the first day, 0.46 in 14 days
    force = result.series["follower-1.phasing_keeping.force"].data  # [N] commanded, applied
    assert force[:, 0].max() < 0.01  # requests of a few mN, under the 50 mN thruster


@pytest.mark.slow
def test_26_the_memory_overflows_between_berlin_pass_groups_and_the_patch_link_holds():
    """The first day: the 3 Gbit memory is full by about 12 h in and data
    is lost; Berlin's link closes throughout its passes, with ~16 dB at the
    best and ~3.7 dB at the 10 deg edge, 65 deg off the patch's boresight."""
    result = _run(_template("26"), duration_days=1.0)  # [day]
    stored = result.series["eo-sat.data_handling.stored"]
    full = stored.time_s[stored.data[:, 0] > 3.0e9 - 0.1e9]  # [s] within 0.1 Gbit of the capacity
    assert full.size and 10.0 * 3600.0 < full[0] < 13.0 * 3600.0
    assert result.series["eo-sat.data_handling.data_lost"].data[-1, 0] > 0.0
    pair = "berlin-gs.access_to_eo-sat"
    margin = result.series[f"{pair}.link_margin_db"].data[:, 0]  # [dB]
    assert 15.0 < np.nanmax(margin) < 17.5 and 2.5 < np.nanmin(margin) < 4.5
    angle = result.series[f"{pair}.antenna_off_boresight"].data[:, 0]  # [deg]
    assert 60.0 < angle[np.nanargmin(margin)] < 68.0
    access = result.series[f"{pair}.has_access"].data[:, 0]
    assert np.array_equal(result.series[f"{pair}.link_closed"].data[:, 0], access)


def test_27_the_wings_ring_at_their_coupled_mode_and_the_pointing_settles():
    """The turn to the Sun swings each wing ~0.07 deg, ringing at ~0.26 Hz
    (above its hub-fixed 0.2 Hz) and below 0.001 deg within ~4.3 min; the
    Sun is within 0.1 deg after ~7.1 min; each wing gives up to ~980 W.
    The first 15 minutes, all in sunlight."""
    result = _run(_template("27"), duration_days=0.01)  # [day]
    deflection = result.series["flex-sat.solar_array.wing-1.deflection"]
    theta_deg = np.degrees(deflection.data[:, 0])
    assert 0.05 < np.abs(theta_deg).max() < 0.08  # [deg]
    assert np.allclose(theta_deg, -np.degrees(result.series["flex-sat.solar_array.wing-2.deflection"].data[:, 0]),
                       atol=0.002)  # [deg] the two wings swing as a mirror pair
    t = deflection.time_s
    above = t[np.abs(theta_deg) > 0.001]  # [s]
    assert 3.5 * 60.0 < above[-1] < 5.0 * 60.0
    window = (t > 5.0) & (t < 120.0)  # [s] the ringing, less its slow drift
    ringing = theta_deg[window] - np.convolve(theta_deg[window], np.ones(41) / 41, mode="same")
    crossings = t[window][30:-30][np.nonzero(np.diff(np.sign(ringing[30:-30])) != 0)[0]]
    assert 0.24 < 1.0 / (2.0 * np.mean(np.diff(crossings))) < 0.28  # [Hz]
    heading = result.series["flex-sat.sun_heading_body"]
    unit = heading.data / np.linalg.norm(heading.data, axis=1)[:, None]
    off_sun_deg = np.degrees(np.arccos(np.clip(unit[:, 2], -1.0, 1.0)))
    assert 6.5 * 60.0 < heading.time_s[off_sun_deg > 0.1][-1] < 7.7 * 60.0  # [s]
    power = result.series["flex-sat.solar_array.wing-1.power"].data[:, 0]  # [W]
    assert 960.0 < power.max() < 1000.0


def test_28_the_model_s_center_of_mass_offset_drives_the_y_wheel():
    """The model gives 300 kg and a center of mass [4.8, 0, -6.3] cm from
    B. The turn to the Sun takes the wheels up to ~850 RPM and ends within
    0.1 deg after ~7 min; then sunlight, pushing 4.8 cm off the center of
    mass, drifts rw-y ~-2.1 RPM an orbit, to ~-6.5 RPM after three orbits.
    The same run with the center of mass put back at B ends near +0.3 RPM,
    so the drift is the offset's."""
    scenario = _template("28")
    spacecraft = scenario.spacecraft[0]
    assert spacecraft.dry_mass_kg == pytest.approx(300.0)
    np.testing.assert_allclose(spacecraft.center_of_mass_b_m, [0.0482, 0.0, -0.0627], atol=1e-4)  # [m]
    result = _run(scenario)
    rpm = result.series["octa-sat.rw_speeds"].data * 30.0 / np.pi  # [RPM]
    assert 750.0 < np.abs(rpm).max() < 950.0
    heading = result.series["octa-sat.sun_heading_body"]
    unit = heading.data / np.linalg.norm(heading.data, axis=1)[:, None]
    off_sun_deg = np.degrees(np.arccos(np.clip(unit[:, 2], -1.0, 1.0)))
    assert 6.0 * 60.0 < heading.time_s[off_sun_deg > 0.1][-1] < 8.0 * 60.0  # [s]
    orbit_s = 5739.0  # [s] at 550 km
    wheels = result.series["octa-sat.rw_speeds"]
    for orbits, expected_rpm in ((1, -2.1), (2, -4.3), (3, -6.5)):
        assert _at(wheels, orbits * orbit_s, column=1) * 30.0 / np.pi == pytest.approx(expected_rpm, abs=0.4)

    centred = _template("28")
    centred.spacecraft[0].center_of_mass_b_m = [0.0, 0.0, 0.0]  # [m]
    centred_rpm = _run(centred).series["octa-sat.rw_speeds"].data[-1, 1] * 30.0 / np.pi  # [RPM]
    assert 0.0 < centred_rpm < 1.5


def _roe_flight(result, name="follower-1"):
    """Days, the ROE error box (|a da|, |a dlambda|, |a de|, |a di|) [m],
    delta-V [m/s], closest radial/cross-track approach [m] and ROE [m]."""
    error = result.series[f"{name}.roe_formation.roe_error"]
    e = error.data
    box = np.c_[np.abs(e[:, 0]), np.abs(e[:, 1]), np.hypot(e[:, 2], e[:, 3]), np.hypot(e[:, 4], e[:, 5])]
    return (error.time_s / 86400.0, box, result.series[f"{name}.roe_formation.delta_v"].data[:, 0],
            result.series[f"{name}.roe_formation.min_rn_separation"].data[:, 0],
            result.series[f"{name}.roe_formation.roe"].data)


def _dv_at(day, dv, when):
    return float(dv[int(np.argmin(np.abs(day - when)))])


def test_29_the_follower_moves_to_a_passively_safe_helix_and_holds_it():
    """Held 2 km behind to day 1; the e/i vectors reach 300 m within 5 h
    while a_dlambda slips to ~4 km behind (eclipse spreads the burns), and
    a drift closes it by day 2.5. The closest approach is 0 m while
    behind, 147 m between the cross-track burns, then 292 m or more from
    day 1.2. 0.56 m/s for the move, 0.026 m/s to hold it to day 4, within
    13 m along-track."""
    day, box, dv, margin, roe_m = _roe_flight(_run(_template("29")))
    before = day < 1.0
    assert np.all(np.abs(roe_m[before, 1] + 2000.0) < 5.0)  # [m] held 2 km behind
    assert np.all(margin[before] < 1.0)  # [m] the orbits cross
    shaped = day >= 1.0 + 5.0 / 24.0
    assert np.all(np.abs(np.hypot(roe_m[shaped, 2], roe_m[shaped, 3]) - 300.0) < 11.0)  # [m] |a de|
    assert np.all(np.abs(np.hypot(roe_m[shaped, 4], roe_m[shaped, 5]) - 300.0) < 11.0)  # [m] |a di|
    assert -4100.0 < roe_m[:, 1].min() < -3800.0  # [m] the slip
    assert 140.0 < margin[(day > 1.15) & (day < 1.17)].min() < 155.0  # [m] between the cross-track burns
    assert margin[day >= 1.2].min() > 290.0  # [m]
    settled = day >= 2.5
    assert box[settled, 1].max() < 15.0  # [m] a dlambda
    assert _dv_at(day, dv, 2.5) == pytest.approx(0.56, abs=0.02)  # [m/s]
    assert dv[-1] - _dv_at(day, dv, 2.5) == pytest.approx(0.026, abs=0.01)  # [m/s]


@pytest.mark.slow
def test_29_continuous_law_and_a_zero_phase_helix():
    """Continuous: on target by day 1.4, within 3 m from day 2 (still
    converging at 1.4: 7 to 9 m there, by platform), 1.85 m/s in
    all. A 0 deg phase (dix nonzero, which J2 turns): holding from day 2.5
    costs about three times the 90 deg helix's 0.026 m/s."""
    continuous = _template("29")
    continuous.spacecraft[1].roe_formation.control_law = "continuous"
    day, box, dv, _margin, _roe = _roe_flight(_run(continuous))
    outside = (day >= 1.0) & np.any(box > np.array([6.0, 20.0, 10.0, 10.0]), axis=1)  # [m] 3 x the da tolerance
    assert day[outside].max() < 1.45  # [day]
    assert box[day >= 2.0].max() < 3.0  # [m]
    assert dv[-1] == pytest.approx(1.85, abs=0.1)  # [m/s]

    zero_phase = _template("29")
    zero_phase.spacecraft[1].roe_formation.targets[1].roe_m = [0.0, 0.0, 300.0, 0.0, 300.0, 0.0]  # [m]
    day, _box, dv, _margin, _roe = _roe_flight(_run(zero_phase))
    assert 2.0 < (dv[-1] - _dv_at(day, dv, 2.5)) / 0.026 < 4.5


def _opnav_flight(result):
    prefix = "probe-1.optical_navigation."
    error = result.series[prefix + "position_error"]
    return (error.time_s / 86400.0, error.data, result.series[prefix + "position_3sigma"].data,
            result.series[prefix + "measurement_error"].data[:, 3],
            result.series[prefix + "measurement_state"].data[:, 0], result.series[prefix + "measurement"].data)


def test_30_the_filter_converges_from_mars_images():
    """From 68 km off to under 2 km by day 1 (1.6 km median after it), up
    to 12 km just after each night-side stretch, inside the filter's
    3-sigma for 94 % of the axis samples; one image alone 56 km (median);
    62 % of the images used; the disk 110 to 152 px in radius."""
    day, error, sigma3, single, state, disk = _opnav_flight(_run(_template("30")))
    assert error[0, 3] == pytest.approx(68.2e3, rel=0.01)  # [m] the seeded start
    after = day >= 1.0
    assert error[np.searchsorted(day, 1.0), 3] < 2.0e3  # [m]
    assert np.median(error[after, 3]) < 2.5e3  # [m]
    assert error[after, 3].max() < 20.0e3  # [m]
    assert np.mean(np.abs(error[:, :3]) <= sigma3) > 0.9
    assert 45.0e3 < np.nanmedian(single) < 70.0e3  # [m]
    assert 0.55 < np.mean(state == 0) < 0.7
    assert 105.0 < np.nanmin(disk[:, 2]) and np.nanmax(disk[:, 2]) < 160.0  # [px]


def test_30_without_pixel_noise_every_image_gives_the_true_position():
    """With centre and radius noise at 0 every used image gives the true
    position (pixelLineConverter inverts the camera model exactly); with
    the largest phase angle at 180 deg every image is used."""
    scenario = _template("30")
    camera = scenario.spacecraft[0].optical_navigation
    camera.center_noise_px = camera.radius_noise_px = 0.0  # [px]
    camera.max_phase_angle_deg = 180.0  # [deg]
    _day, _error, _sigma3, single, state, _disk = _opnav_flight(_run(scenario))
    assert np.all(state == 0)
    assert np.nanmax(single) < 1.0e-3  # [m]


def _landmark_flight(result):
    prefix = "probe-1.landmark_navigation."
    error = result.series[prefix + "position_error"]
    return (error.time_s, error.data, result.series[prefix + "position_3sigma"].data,
            result.series[prefix + "landmarks_seen"].data[:, 0], result.series[prefix + "residual_rms"].data[:, 0],
            result.series["probe-1.small_body.distance"].data[:, 0])


@pytest.mark.slow
def test_31_the_filter_finds_the_orbit_from_eros_landmarks(real_small_body_files):
    """5.5 m after the first image, 0.35 m median after, up to 4.8 m just
    after the night-side stretches, inside the filter's 3-sigma; about 18
    landmarks per image and none in 22 of 289; 0.28 px residuals; the
    probe between 35.0 and 38.0 km from the centre."""
    _t, error, sigma3, seen, residual, distance = _landmark_flight(_run(_template("31")))
    assert error[0, 3] == pytest.approx(5.5, abs=0.1)  # [m] after the first image
    assert np.median(error[1:, 3]) == pytest.approx(0.35, abs=0.05)  # [m]
    assert error[1:, 3].max() == pytest.approx(4.8, abs=0.2)  # [m]
    assert np.mean(np.abs(error[:, :3]) <= sigma3) > 0.99
    assert np.median(seen) == 18 and np.sum(seen == 0) == 22 and len(seen) == 289
    assert np.nanmedian(residual) == pytest.approx(0.28, abs=0.01)  # [px]
    assert distance.min() == pytest.approx(35.0e3, rel=1e-3) and distance.max() == pytest.approx(38.0e3, abs=100.0)


@pytest.mark.slow
def test_31_one_pixel_of_noise_shows_in_the_residuals_and_the_error(real_small_body_files):
    """Added pixel noise 1 px: residuals of about 1 px (hypot(0.29, 1)) and
    a median error of about 5 m over the first half day (5.1 m seen)."""
    scenario = _template("31")
    scenario.spacecraft[0].landmark_navigation.pixel_noise_px = 1.0  # [px]
    _t, error, _sigma3, _seen, residual, _distance = _landmark_flight(_run(scenario, duration_days=0.5))
    assert np.nanmedian(residual) == pytest.approx(1.04, abs=0.1)  # [px]
    assert np.median(error[1:, 3]) == pytest.approx(5.1, abs=0.5)  # [m]


def test_32_the_design_checks_find_the_array_in_the_tracker_s_view_and_the_plume():
    """Template 32's design checks: the +y array takes about 5.5 % of the
    star tracker's 20 deg view (looking 10 deg below the arrays' plane) and
    about 9.4 % of the station-keeping nozzle's 15 deg plume, both only
    deployed; the AIAA S-120 growth is 42.54 kg on 300 kg (bus 15 %,
    arrays 10 %, tracker 3 %, dish 25 %, battery 5 %), 352.54 kg with the
    10 kg of propellant; folded, the arrays fit the envelope."""
    from spacemissionstudio.analyses import design_checks

    scenario = _template("32")
    path = next(_TEMPLATES_DIR.glob("32_*.json"))
    report = design_checks.design_checks(scenario.spacecraft[0], base_dir=path.parent)
    fov = {(o.item, o.configuration): o for o in report.fov.obstructions}
    tracker = fov[("st-1", "deployed")]
    assert list(tracker.by_part) == ["array +y"] and 0.02 < tracker.blocked_fraction < 0.09
    assert fov[("st-1", "stowed")].blocked_fraction == 0.0
    assert list(report.plumes[0].by_part) == ["array +y"] and 0.06 < report.plumes[0].blocked_fraction < 0.13
    assert report.mass.basic_dry_kg == pytest.approx(300.0) and report.mass.growth_kg == pytest.approx(42.54)
    assert report.mass.launch_mass_kg == pytest.approx(352.54)
    assert report.launcher.configuration == "stowed" and report.launcher.fits
    assert [f.rule_id for f in report.findings()] == ["design.fov_obstructed", "design.plume_impingement"]


@pytest.mark.slow
def test_32_the_run_records_the_disturbances_and_the_arrays_shading():
    """One orbit: the gravity gradient dominates, at most 8.0e-5 N*m, under
    its analytical worst case 8.5e-5 N*m; about 0.2 N*m*s builds up about z
    in the orbit, far below the 12 N*m*s wheels; the arrays give up to
    about 1.37 kW unshaded and lose about 0.6 % of their energy to shading."""
    from spacemissionstudio.analyses import run_analyses

    scenario = _template("32")
    result = _run(scenario)
    report = run_analyses.report(result, scenario, scenario.spacecraft[0])
    gravity = report.disturbances.sources["gravity_gradient"]
    assert gravity.max_n_m == pytest.approx(7.96e-5, rel=0.05)
    assert gravity.max_n_m <= gravity.analytic_worst_n_m == pytest.approx(8.48e-5, rel=0.02)
    assert report.disturbances.whole_orbits == 1
    assert report.disturbances.required_momentum_n_m_s()[2] == pytest.approx(0.204, rel=0.1)
    assert report.findings() == []
    power = result.series["smallsat-1.shading.power"]
    assert power.data[:, -2].max() == pytest.approx(1372.0, rel=0.02)
    assert any("0.59 %" in note or "0.6 %" in note for note in report.notes)


@pytest.mark.slow
def test_33_the_thermal_cases_keep_the_bus_warm_and_safe_mode_needs_the_heater():
    """Template 33's thermal model on its run: every case orbit-periodic,
    its energy balance closed to 1e-3 and changing by less than 0.5 K with
    half the step; the MLI-covered bus at 11 to 14.6 degC in the nominal,
    hot and cold cases (hot warmest, cold coldest) and the radiator
    rejecting about 37 W; in the cold safe-mode case (avionics at 15 W)
    the bus at about -22.5 degC, battery heater A on all the time and sized
    at about 7.6 W, and the avionics below their -20 degC operating limit,
    a Timeline event and a finding."""
    from spacemissionstudio import api
    from spacemissionstudio.engine.events import THERMAL_LIMIT

    scenario = _template("33")
    analysis = api.thermal(scenario, _run(scenario))
    by = {c.name: c for c in analysis.cases}
    assert list(by) == ["nominal", "hot", "cold", "cold safe mode"]
    for case in analysis.cases:
        solution = case.solution
        assert solution.periodic.converged
        assert abs(solution.energy_residual_j) < 1.0e-3 * solution.energy_throughput_j
        assert solution.step_check_k < 0.5

    def node(case, name):
        return next(n for n in by[case].summary if n.name == name)

    for case in ("nominal", "hot", "cold"):
        assert 11.0 < node(case, "bus").min_c and node(case, "bus").max_c < 14.6
        assert by[case].radiators[0].rejected_w == pytest.approx(37.0, abs=1.0)
        assert all(h.duty == 0.0 for h in by[case].heaters)
    assert node("hot", "bus").mean_c > node("nominal", "bus").mean_c > node("cold", "bus").mean_c
    safe = by["cold safe mode"]
    assert node("cold safe mode", "bus").mean_c == pytest.approx(-22.5, abs=1.0)
    heater_a = next(h for h in safe.heaters if h.name == "battery heater A")
    assert heater_a.duty == 1.0 and heater_a.sized_w == pytest.approx(7.6, abs=0.3)
    assert node("cold safe mode", "avionics").min_c < -20.0 < node("cold safe mode", "avionics").min_c + 5.0
    events = analysis.events()
    assert events and all(e.kind == THERMAL_LIMIT and e.label == "avionics below operating" for e in events)
    assert "thermal.limit" in {getattr(f, "rule_id", None) for f in analysis.findings()}


def test_34_the_wings_turn_with_the_run_and_the_monte_carlo_finds_a_warm_battery():
    """Template 34's flexible wings as thermal nodes: the run records each
    hinge angle (0.012 deg at most, in the Sun-safe turn), the cases are
    orbit-periodic with their energy balance closed and a step check under
    0.5 K, each wing swings between about -46 and 88 degC, the bus stays at
    13.5 to 18.5 degC and the battery at 24 to 28.5 degC; the hot case's
    Monte Carlo (20 runs, seed 34) puts the battery above its 30 degC limit
    in 4 runs, the same 4 again from the same seed."""
    import numpy as np

    from spacemissionstudio import api

    scenario = _template("34")
    result = _run(scenario)
    for wing in ("wing-1", "wing-2"):
        deflection = np.degrees(np.asarray(result.series[f"microsat-2.solar_array.{wing}.deflection"].data))
        assert 0.005 < np.abs(deflection).max() < 0.02
    analysis = api.thermal(scenario, result)
    assert not analysis.prepared.warnings  # the deflections were recorded and used
    by = {c.name: {n.name: n for n in c.summary} for c in analysis.cases}
    for case in analysis.cases:
        assert case.solution.periodic.converged and case.solution.step_check_k < 0.5
        assert abs(case.solution.energy_residual_j) < 1.0e-3 * case.solution.energy_throughput_j
        assert 13.5 < by[case.name]["bus"].min_c and by[case.name]["bus"].max_c < 18.5
        assert 24.0 < by[case.name]["battery"].min_c and by[case.name]["battery"].max_c < 28.5
    wing = by["hot"]["solar array wing-1"]
    assert wing.min_c == pytest.approx(-42.6, abs=1.0) and wing.max_c == pytest.approx(87.5, abs=1.0)
    assert by["nominal"]["solar array wing-1"].min_c == pytest.approx(-45.7, abs=1.0)
    batch = api.thermal_monte_carlo(scenario, result)
    warm = batch.temperatures_c["battery"].max(axis=1) > 30.0
    assert len(batch.runs) == 20 and not batch.failed and int(warm.sum()) == 4
    battery = next(row for row in batch.node_limits if (row["node"], row["range"]) == ("battery", "operating"))
    assert (battery["outside"], battery["evaluated"], battery["high_c"]) == (4, 20, 30.0)  # B4 counts them
    assert np.array_equal(api.thermal_monte_carlo(scenario, result).temperatures_c["battery"],
                          batch.temperatures_c["battery"])


def test_35_a_week_of_operations_fills_the_memory_faster_than_the_contacts_empty_it():
    """Template 35's week (SRS-F-30): about 18 of the 23 images wanted, one
    calibration a day and 37 contacts, never more than the 40 min a day the
    ground segment books; the memory climbs to about 2.6 of its 3 Gbit and
    is that full at the end; Rotterdam's second image loses to the passes
    over Europe; Kilimanjaro and the Danube delta have no lit window within
    30 deg off nadir. The first six hours of the plan, flown in the
    simulation, keep within the verification's tolerances.

    The Alps' window sits at the 30 deg limit: with the Earth orientation
    files (ITRF93) it holds an image, without them (IAU_EARTH, about 10 km
    apart on the ground, as in this test run) it is too short. Both are
    accepted here."""
    from collections import Counter

    from spacemissionstudio.operations import analysis, verify
    from spacemissionstudio.operations.plan import Plan

    scenario = _template("35")
    planning = analysis.plan(scenario)
    plan = planning.plan
    kinds = Counter(a.kind for a in plan.activities)
    assert kinds["calibration"] == 7 and kinds["contact"] == 37 and kinds["acquisition"] in (17, 18)
    wanted = sum(t.acquisitions for t in scenario.operations.targets)
    assert wanted == 23
    per_day = Counter(int((a.start_s - plan.start_s) // 86400.0) for a in plan.activities if a.kind == "contact"
                      for _ in range(int(a.duration_s)))
    assert max(per_day.values()) <= 2400
    assert Counter(a.station for a in plan.activities if a.kind == "contact")["svalbard-gs"] > 30
    resources = plan.resources["eo-micro"]
    assert 2.5e9 < resources["max_memory_bit"] <= 3.0e9 and resources["memory_bit"][-1] > 2.5e9
    assert resources["lost_bit"] == 0.0 and resources["min_soc"] > 0.8
    reasons = {u.request: u.reason for u in plan.unscheduled if u.kind != "contact"}
    assert reasons["rotterdam-port"] == "conflict" and reasons["alps-glacier"] in ("conflict", "too_short")
    assert reasons["kilimanjaro"] == reasons["danube-delta"] == "no_opportunity"
    first = [a for a in plan.activities if a.end_s <= plan.start_s + 6 * 3600.0]
    assert len(first) >= 4
    six_hours = Plan(plan.epoch_utc, plan.start_s, plan.start_s + 6 * 3600.0, plan.start_utc,
                     planning.timebase.text(plan.start_s + 6 * 3600.0), first, resources=plan.resources)
    checked = verify.check(scenario, six_hours, analysis.fly(scenario, six_hours))
    assert all(a.flown and a.slew_done for a in checked.activities) and checked.flags == []


def test_36_three_imagers_share_the_contested_passes():
    """Template 36 (SRS-F-30): the three spacecraft reach the pole together,
    so 33 passes are wanted by two or three of them; with equal priorities
    each gets 11 contacts; a station never serves two at once; passes are
    lost to a busy station."""
    from collections import Counter

    from spacemissionstudio.operations import analysis

    plan = analysis.plan(_template("36")).plan
    assert len(plan.contention) == 33 and all(len(c["wanted_by"]) >= 2 for c in plan.contention)
    assert Counter(a.spacecraft for a in plan.activities if a.kind == "contact") == {"eo-a": 11, "eo-b": 11,
                                                                                    "eo-c": 11}
    for station in ("svalbard-gs", "berlin-gs"):
        spans = sorted((a.start_s, a.end_s) for a in plan.activities if a.station == station)
        assert all(later[0] >= earlier[1] for earlier, later in zip(spans, spans[1:]))
    assert Counter(u.reason for u in plan.unscheduled if u.kind == "contact")["station_busy"] > 20


@pytest.mark.slow
def test_37_the_batch_meets_its_altitude_requirement_and_the_drag_coefficient_drives_the_decay(tmp_path):
    """Template 37 (Monte Carlo plan B9, decision MC-34): its 30 runs as
    shipped (seed 37, one process; 53 s measured here). R-ALT-01 is met:
    no run below 389 km, the bound 1 - 0.1^(1/30) = 0.074 under the allowed
    0.1. R-DECAY-01 has no allowed probability: 2 of 30 runs lose more than
    19 m, estimate 0.067, bound about 0.17. The drag coefficient drives the
    semi-major axis change (rank correlation about -0.9), the dry mass much
    less (about +0.3). The batch seed gives the draws the golden file
    recorded for its first two runs. The report says the same."""
    import json

    from spacemissionstudio import api
    from spacemissionstudio.engine import monte_carlo_report
    from spacemissionstudio.engine import monte_carlo_requirements as mcreq
    from spacemissionstudio.engine import monte_carlo_statistics as mcs

    scenario = _template("37")
    assert (scenario.monte_carlo.num_runs, scenario.monte_carlo.thread_count, scenario.monte_carlo.seed) == (30, 1, 37)
    batch = api.monte_carlo(scenario, tmp_path / "mc")
    assert len(batch.runs) == 30 and not batch.failed and batch.seed == 37
    altitude, decay = mcreq.evaluate(batch)
    assert (altitude.name, altitude.evaluated, altitude.not_met, altitude.verdict) == ("R-ALT-01", 30, 0, mcreq.MET)
    assert altitude.upper_bound == pytest.approx(1.0 - 0.1 ** (1.0 / 30.0), rel=1e-9)
    assert altitude.upper_bound == pytest.approx(0.074, abs=5e-4)
    assert (decay.name, decay.not_met, decay.verdict) == ("R-DECAY-01", 2, "")
    assert decay.estimate == pytest.approx(2.0 / 30.0) and decay.upper_bound == pytest.approx(0.17, abs=0.005)
    insight = mcs.insight(batch)
    pairs = {(p.input_label, p.outcome_label): p.value for p in insight.sensitivity}
    change = "sat-1 mean semi-major axis change [km]"
    assert pairs[("sat-1 drag coefficient [-]", change)] < -0.85
    assert 0.0 < pairs[("sat-1 dry mass [kg]", change)] < 0.5
    lowest = next(s for s in insight.statistics if s.name == "sat-1 lowest altitude")
    assert lowest.minimum > 389.0
    golden = json.loads((Path(__file__).resolve().parent / "golden"
                         / "37_monte_carlo_requirements_and_sensitivity.json").read_text(encoding="utf-8"))
    labels, rows = golden["monte_carlo"]["runs"]
    import golden_capture

    for k in range(2):
        drawn = {label: value for label, value in zip(labels[1:6], rows[k][1:6])}
        assert batch.drawn[k].keys() >= drawn.keys()
        for label, value in drawn.items():
            # The drawn orbit angles are rv2elem of the dispersed state; for this near-circular orbit an
            # arccos near 1 differs by 2^-26 rad between computers (8.5e-7 deg on the Linux runner), so they
            # get the golden files' angle floor. The other draws are the generator's own numbers.
            tolerance = ({"abs": golden_capture.ABSOLUTE_FLOORS["deg"]} if label.endswith("[deg]")
                         else {"rel": 1e-12})
            assert batch.drawn[k][label] == pytest.approx(value, **tolerance), label
    report = monte_carlo_report.build(batch, tmp_path / "mc", insight)
    assert report["settings"]["seed"] == 37 and report["settings"]["processes"] == 1
    assert [r["verdict"] for r in report["requirements"]["results"]] == ["met", None]
    assert len(report["dispersions"]) == 3


def test_38_the_power_mass_and_pointing_budgets_are_complete():
    """Template 38's Budgets area (SRS-F-31), with the functions its Power and Mass
    pages and the ``budgets`` command use: every number of the power
    budget is known, with no finding; the four system modes' duty cycles
    add up to 1, so the duty-cycle average is 54.2 W of load and 77.1 W at
    the source with margins; the mass budget is 110.3 kg basic with
    22.9 kg of AIAA S-120 growth and 6 kg of propellant, 139.2 kg against
    the 150 kg limit, with no unknown line. The 3D model holds every item,
    so the run flies the same 110.3 kg. The pointing budget (the Pointing
    page and ``budgets --pointing``) meets its three requirements: the
    line of sight at 22.1 of 60 arcsec, the relative error about x at
    12.4 of 15 arcsec, the knowledge about x at 3.9 of 15 arcsec. Each
    number of the section is an example, and its source says so."""
    from spacemissionstudio.analyses.mass_budget import mass_budget
    from spacemissionstudio.analyses.power_budget import power_budget
    from spacemissionstudio.engine.pointing_budget import MET, pointing_budget, rad_to_arcsec

    sc = _template("38").spacecraft[0]
    section = sc.budgets
    values = [bus.converter_efficiency for bus in section.buses] + [m.percent for m in section.power_margins]
    values += [section.distribution_loss, section.system_power_margin_percent]
    for item in section.equipment:
        values += [item.mass_kg] + [v for mode in item.power_modes for v in (mode.average_w, mode.peak_w)
                                    if v is not None]
    for requirement in section.pointing.requirements:
        values += [v for v in (requirement.limit_arcsec, requirement.probability, requirement.window_s,
                               requirement.stability_s) if v is not None]
    for contributor in section.pointing.contributors:
        values += list(contributor.spread_arcsec.values()) + list(contributor.mean_arcsec.values())
        values += [contributor.period_s] if contributor.period_s is not None else []
    assert {v.source for v in values} == {"Synthetic example value; not from a data sheet or a standard."}
    assert not any(v.placeholder for v in values)
    assert len(section.equipment) == 12

    power = power_budget(sc)
    assert power.complete and power.findings == []
    assert [m.mode for m in power.modes] == ["safe", "nominal", "imaging", "downlink"]
    loads = {m.mode: m.average.load_w for m in power.modes}  # [W]
    assert loads == pytest.approx({"safe": 38.0, "nominal": 43.5, "imaging": 87.5, "downlink": 65.5})
    imaging = power.mode("imaging")
    assert [b.bus for b in imaging.buses] == ["platform", "payload"]
    assert imaging.average.source_margined_w == pytest.approx(129.586, abs=1e-3)  # [W]
    assert imaging.peak.load_w == pytest.approx(139.5)  # [W]
    average = power.duty_cycle_average()
    assert average is not None and average.complete
    assert average.load_w == pytest.approx(54.225) and average.source_margined_w == pytest.approx(77.079, abs=1e-3)

    mass = mass_budget(sc)
    assert mass.unknown == []
    assert all(item.mass_in_model for item in section.equipment)
    assert {line.kind for line in mass.lines} == {"part"} and len(mass.lines) == 13
    assert mass.basic_dry_kg == pytest.approx(110.3) and mass.growth_kg == pytest.approx(22.866)  # [kg]
    assert mass.propellant_kg == pytest.approx(6.0) and mass.launch_mass_kg == pytest.approx(139.166)  # [kg]
    assert mass.mass_limit_kg == 150.0 and mass.headroom_kg == pytest.approx(10.834)  # [kg]
    assert sc.dry_mass_kg == pytest.approx(mass.basic_dry_kg)  # [kg] the run's and the propellant budget's

    pointing = pointing_budget(sc)
    assert pointing.complete and pointing.contributors == 5
    assert [r.status for r in pointing.results] == [MET, MET, MET]
    values = {r.requirement: rad_to_arcsec(r.value_rad) for r in pointing.results}  # [arcsec]
    assert values == pytest.approx({"APE line of sight": 22.11, "RPE x": 12.43, "AKE x": 3.92}, abs=0.01)


@pytest.mark.slow
def test_38_the_propellant_budget_fits_the_tank():
    """Template 38's Propellant page, with the function it and the
    ``budget`` command use, without a run: the station keeper's orbit
    control is estimated from the drag, the disposal is solved, and five
    years take 83.0 m/s and 5.23 kg at 220 s, inside the 8 kg tank."""
    from spacemissionstudio.engine import propellant_budget

    budget = propellant_budget.compute_budget(_template("38"), "eo-sat")
    assert budget.isp_s == 220.0 and budget.dry_mass_kg == pytest.approx(110.3 * 1.15)  # [s], [kg]
    assert budget.total_delta_v_m_s == pytest.approx(83.0, abs=0.1)  # [m/s]
    assert budget.total_propellant_kg == pytest.approx(5.23, abs=0.01)  # [kg]
    assert all(row.propellant_kg is not None for row in budget.rows)
    assert not any("exceeds the tank" in note for note in budget.notes)


def _mean_elements(result, name, element):
    return result.series[f"{name}.orbit_elements_mean.{element}"].data[:, 0]


def test_39_each_orbit_input_flies_the_orbit_it_states():
    """Template 39 (decision TPL-A1): the synthetic TLE flies near the mean
    elements it encodes (SGP4's semi-major axis, its inclination in TEME of
    date, about 15.5 revolutions a day); the illustrative state vector is the
    perigee of a 500 x 1500 km orbit at the critical inclination, so its
    perigee stays while its node moves; the classical elements are taken as
    given."""
    import math

    from sgp4.api import Satrec

    from spacemissionstudio import constants
    from spacemissionstudio.engine import tle

    scenario = _template("39")
    assert [sc.orbit.type for sc in scenario.spacecraft] == ["tle", "cartesian", "classical_elements"]
    result = _run(scenario)

    orbit = scenario.spacecraft[0].orbit
    tle.check_lines(orbit.tle_line1, orbit.tle_line2)  # columns and checksums
    assert orbit.tle_line1[2:7] == "99999"  # the analysts' number: no real satellite
    record = Satrec.twoline2rv(orbit.tle_line1, orbit.tle_line2)
    sgp4_a_km = record.a * record.radiusearthkm  # [km]
    assert float(np.mean(_mean_elements(result, "tle-sat", "semi_major_axis"))) / 1e3 == pytest.approx(
        sgp4_a_km, abs=0.5)
    position = result.series["tle-sat.position_N"]
    velocity = result.series["tle-sat.velocity_N"].data
    first_orbit = position.time_s <= 2.0 * math.pi * math.sqrt((sgp4_a_km * 1e3) ** 3 / constants.EARTH_GM_M3_S2)
    to_teme = tle.teme_to_eme2000_matrix(tle._naive_utc(scenario.epoch_utc)).T
    h = to_teme @ np.cross(position.data[first_orbit], velocity[first_orbit]).mean(axis=0)
    assert math.degrees(math.acos(h[2] / np.linalg.norm(h))) == pytest.approx(51.64, abs=0.01)  # [deg]
    assert float(np.mean(_mean_elements(result, "tle-sat", "eccentricity"))) < 0.002
    turns = np.unwrap(np.arctan2(position.data[:, 1], position.data[:, 0]))  # [rad] near enough for 51.6 deg
    revolutions_per_day = abs(turns[-1] - turns[0]) / (2.0 * math.pi) / (position.time_s[-1] / 86400.0)
    assert revolutions_per_day == pytest.approx(15.5, rel=2e-3)

    state = scenario.spacecraft[1].orbit
    r_km, v_km_s = np.array(state.position_km), np.array(state.velocity_km_s)
    mu_km3_s2 = constants.EARTH_GM_M3_S2 / 1e9  # [km^3/s^2]
    a_km = -mu_km3_s2 / (2.0 * (v_km_s @ v_km_s / 2.0 - mu_km3_s2 / np.linalg.norm(r_km)))
    radius_km = constants.EARTH_EQUATORIAL_RADIUS_M / 1e3  # [km]
    assert np.linalg.norm(r_km) - radius_km == pytest.approx(500.0, abs=0.01)  # [km] perigee
    assert 2.0 * a_km - np.linalg.norm(r_km) - radius_km == pytest.approx(1500.0, abs=0.01)  # [km] apogee
    assert math.degrees(math.atan2(v_km_s[2], v_km_s[1])) == pytest.approx(63.4, abs=1e-4)  # [deg]
    assert result.series["state-sat.orbit_elements.semi_major_axis"].data[0, 0] / 1e3 == pytest.approx(a_km, abs=1e-3)
    perigee = np.degrees(_mean_elements(result, "state-sat", "arg_periapsis"))  # [deg]
    node = np.degrees(_mean_elements(result, "state-sat", "raan"))  # [deg]
    assert abs((perigee[-1] - perigee[0] + 180.0) % 360.0 - 180.0) < 0.1  # [deg/day] critical inclination
    assert (node[0] - node[-1]) % 360.0 == pytest.approx(2.7, abs=0.1)  # [deg/day] the node regresses

    elements = scenario.spacecraft[2].orbit
    assert result.series["elements-sat.orbit_elements.semi_major_axis"].data[0, 0] / 1e3 == pytest.approx(
        elements.semi_major_axis_km, abs=1e-6)
    assert math.degrees(result.series["elements-sat.orbit_elements.inclination"].data[0, 0]) == pytest.approx(
        elements.inclination_deg, abs=1e-9)


def test_40_the_thruster_raises_the_orbit_against_drag_and_spends_what_the_rocket_equation_says():
    """Template 40 (decision TPL-A1): over three days ep-sat's 1 mN along the
    velocity raises its mean semi-major axis by about 2.8 km while its
    unthrusted twin sinks by about 0.3 km; the gap is Gauss's 2 a^1.5 /
    sqrt(mu) per m/s of delta-V; the propellant used is F t / (Isp g0),
    8.8 g."""
    import math

    from spacemissionstudio import constants

    scenario = _template("40")
    thrust = scenario.spacecraft[0].constant_thrust
    assert (thrust.frame, thrust.direction, thrust.thrust_n, thrust.isp_s, thrust.propellant_kg) == (
        "VNB", [1.0, 0.0, 0.0], 1.0e-3, 3000.0, 1.3)  # the catalogue's MICRO R3
    assert scenario.spacecraft[1].constant_thrust is None
    result = _run(scenario)
    raised = _mean_elements(result, "ep-sat", "semi_major_axis") / 1e3  # [km]
    sunk = _mean_elements(result, "twin-sat", "semi_major_axis") / 1e3  # [km]
    assert raised[-1] - raised[0] == pytest.approx(2.8, abs=0.1)
    assert sunk[-1] - sunk[0] == pytest.approx(-0.3, abs=0.1)

    delta_v = result.series["ep-sat.constant_thrust.delta_v"]
    elapsed_s = float(delta_v.time_s[-1])  # [s]
    gauss_km = 2.0 * (raised[0] * 1e3) ** 1.5 / math.sqrt(constants.EARTH_GM_M3_S2) * float(delta_v.data[-1, 0]) / 1e3
    assert (raised[-1] - sunk[-1]) - (raised[0] - sunk[0]) == pytest.approx(gauss_km, rel=0.02)
    assert float(delta_v.data[-1, 0]) == pytest.approx(1.7, abs=0.05)  # [m/s]
    used_kg = thrust.propellant_kg - float(result.series["ep-sat.constant_thrust.propellant_remaining"].data[-1, 0])
    assert used_kg == pytest.approx(thrust.thrust_n * elapsed_s / (thrust.isp_s * constants.STANDARD_GRAVITY_M_S2),
                                    rel=1e-3)
    assert used_kg == pytest.approx(8.8e-3, abs=0.1e-3)  # [kg]
    assert thrust.propellant_kg / (used_kg / 3.0) / 30.4 == pytest.approx(14.5, abs=0.5)  # [month] of firing


def _velocity_pointing_error_deg(result, name="sat-1", after_s=600.0):
    """The true angle [deg] between the body frame and velocityPoint's
    frame (y along the velocity, z along the orbit normal), from the true
    state, after ``after_s``."""
    r = result.series[f"{name}.position_N"].data
    v = result.series[f"{name}.velocity_N"].data
    sigma = result.series[f"{name}.attitude_sigma_BN"]
    errors = []
    for k in np.flatnonzero(sigma.time_s >= after_s):
        y = v[k] / np.linalg.norm(v[k])
        z = np.cross(r[k], v[k])
        z /= np.linalg.norm(z)
        reference = np.array([np.cross(y, z), y, z])  # RN
        s = sigma.data[k]
        cross = np.array([[0.0, -s[2], s[1]], [s[2], 0.0, -s[0]], [-s[1], s[0], 0.0]])
        body = np.eye(3) + (8.0 * cross @ cross - 4.0 * (1.0 - s @ s) * cross) / (1.0 + s @ s) ** 2  # BN
        cosine = (np.trace(body @ reference.T) - 1.0) / 2.0
        errors.append(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))))
    return np.array(errors)


def test_41_velocity_pointing_stays_within_what_the_navigation_errors_imply():
    """Template 41 (decision TPL-A1): after the first 10 minutes the true
    attitude stays within the velocity frame by what its navigation errors
    imply: the attitude bound as a rotation (each MRP component at the
    bound), plus the turn a rate error w gives, 4 x P/K x w (the controller
    damps a rate that is not there), plus the controller's own 0.01 deg.
    Without the errors it points within 0.01 deg; with them the rate error,
    not the attitude error, sets the size. The magnetometer reads the
    Earth's field, 19 to 50 uT. Bounds only: another standard library
    draws other errors (golden_capture)."""
    import math

    from spacemissionstudio.engine import control_gains
    from spacemissionstudio.schema.scenario import NavigationErrorConfig

    scenario = _template("41")
    sc = scenario.spacecraft[0]
    assert sc.fsw_mode == "velocityPoint" and {s.kind for s in sc.sensors} == {"star_tracker", "imu", "magnetometer"}
    errors = sc.navigation_error
    assert errors.any_error and errors.sun_step_deg == 0.0
    result = _run(scenario)

    def rotation_deg(bound_deg):  # each MRP component held within tan(bound/4)
        return math.degrees(4.0 * math.atan(math.sqrt(3.0) * math.tan(math.radians(bound_deg) / 4.0)))

    gains = control_gains.default_mrp_gains_for_inertia(sc.inertia_kg_m2)
    rate_turn_deg = 4.0 * gains["P"] / gains["K"] * errors.rate_bound_deg_s * math.sqrt(3.0)  # [deg]
    implied_deg = rotation_deg(errors.attitude_bound_deg) + rate_turn_deg + 0.01  # [deg]
    pointing = _velocity_pointing_error_deg(result)
    assert pointing.max() < implied_deg
    assert pointing.max() > rotation_deg(errors.attitude_bound_deg)  # the rate error shows
    assert result.series["sat-1.navigation_error.attitude"].data[:, 0].max() <= rotation_deg(
        errors.attitude_bound_deg) * (1 + 1e-6)
    field = np.linalg.norm(result.series["sat-1.sensor.mag-1"].data, axis=1) * 1e6  # [uT]
    assert 17.0 < field.min() and field.max() < 52.0 and field.max() - field.min() > 20.0

    exact = _template("41")
    exact.spacecraft[0].navigation_error = None
    assert _velocity_pointing_error_deg(_run(exact)).max() < 0.01  # [deg]
    wider = _template("41")
    wider.spacecraft[0].navigation_error = NavigationErrorConfig(
        **{**errors.__dict__, "rate_step_deg_s": 0.0005, "rate_bound_deg_s": 0.005})
    assert _velocity_pointing_error_deg(_run(wider, duration_days=0.03)).max() > 2.0 * pointing.max()


def test_42_the_tabular_atmosphere_decays_otherwise_than_nrlmsise_00():
    """Template 42 (decision TPL-A1): two days at 350 km from 1 October 2024.
    The NRLMSISE-00 nominal profile (one table, no solar cycle) lowers the
    mean semi-major axis by about 0.4 km; NRLMSISE-00 with that month's real
    space weather, near the solar maximum, about seven times as far; the
    exponential model about as much as no drag at all. The lifetime estimate
    reads the same table: re-entry after about 350 days at Cd 2.2, under two
    months with NRLMSISE-00, and it warns about the table."""
    from spacemissionstudio.engine import lifetime

    scenario = _template("42")
    assert (scenario.space_weather.atmosphere_model, scenario.space_weather.atmosphere_table) == (
        "tabular", "nrlmsise00_nominal")

    def decay_km(model=None, drag=True):
        variant = _template("42")
        if model is not None:
            variant.space_weather.atmosphere_model = model
        variant.spacecraft[0].enable_drag = drag
        a = _mean_elements(_run(variant), "low-sat", "semi_major_axis") / 1e3  # [km]
        return float(a[-1] - a[0])

    tabular, msis, exponential, none = decay_km(), decay_km("nrlmsise00"), decay_km("exponential"), decay_km(drag=False)
    assert tabular == pytest.approx(-0.4, abs=0.05)
    assert msis / tabular == pytest.approx(7.3, abs=0.5)
    assert (msis - none) / (tabular - none) > 5.0  # the drag alone
    assert exponential == pytest.approx(none, abs=1e-3)

    table_life = lifetime.end_of_life(scenario, "low-sat", drag_coeff=2.2)
    assert table_life.lifetime.reentered and table_life.lifetime.lifetime_s / 86400.0 == pytest.approx(350.0, abs=10.0)
    assert any("tabular atmosphere" in w for w in table_life.lifetime.warnings)
    scenario.space_weather.atmosphere_model = "nrlmsise00"
    msis_life = lifetime.end_of_life(scenario, "low-sat", drag_coeff=2.2)
    assert msis_life.lifetime.reentered and msis_life.lifetime.lifetime_s / 86400.0 < 61.0


def _parallel_axis(mass_kg, inertia_cm, position_m):
    """``inertia_cm`` [kg*m^2] about a part's own center of mass, moved to
    the body origin (parallel-axis theorem)."""
    r = np.asarray(position_m, dtype=float)
    return np.asarray(inertia_cm, dtype=float) + mass_kg * (r @ r * np.eye(3) - np.outer(r, r))


def test_43_the_model_gives_the_mass_properties_of_its_cylinders_spheres_and_mesh():
    """Template 43 (decision TPL-B1): the mass, center of mass and inertia
    the run flies are those of the parts. The bus and the tank, the
    magnetometer and the camera's box are checked against the textbook
    formulas (a solid cylinder, solid spheres, a solid box); the boom (a
    thin shell) and the camera's open hood (a shell mesh) take the app's
    own values, as no closed formula covers them. The mesh file is the
    synthetic one shipped next to the template, in millimetres, unchanged
    since its SHA-256 was recorded. Without attitude control the body
    rates stay below 0.01 deg/s for the 2.4 hours."""
    from spacemissionstudio.model3d import mass_properties as mp
    from spacemissionstudio.model3d import model as model3d
    from spacemissionstudio.model3d import obj_io

    scenario = _template("43")
    sc = scenario.spacecraft[0]
    parts = {part.name: part for part in sc.model.parts}
    assert {p.shape for p in parts.values()} == {"cylinder", "sphere", "mesh"}
    mesh = sc.model.meshes[0]
    mesh_path = _TEMPLATES_DIR / mesh.path
    assert mesh.path == "../meshes/43_synthetic_camera.obj" and (mesh.units, mesh.up_axis) == ("mm", "z")
    assert model3d.file_sha256(mesh_path) == mesh.sha256
    assert "synthetic" in mesh_path.read_text(encoding="utf-8").splitlines()[0]
    assert [g.name for g in obj_io.read_obj(mesh_path, units="mm").groups] == ["camera_body", "camera_hood"]
    derived = model3d.derive(sc.model, _TEMPLATES_DIR)
    assert not derived.errors and not derived.warnings

    def solid_cylinder(m, diameter, height):
        r = diameter / 2.0  # [m]
        across = m * (3 * r * r + height * height) / 12.0  # [kg*m^2]
        return np.diag([across, across, m * r * r / 2.0])

    def solid_sphere(m, diameter):
        return np.eye(3) * 0.4 * m * (diameter / 2.0) ** 2

    def solid_box(m, x, y, z):
        return np.diag([m * (y * y + z * z), m * (x * x + z * z), m * (x * x + y * y)]) / 12.0

    bus, tank, boom, magnetometer = parts["bus"], parts["tank"], parts["boom"], parts["magnetometer"]
    body, hood = parts["camera body"], parts["camera hood"]
    bodies = [  # (mass [kg], inertia about its own center of mass [kg*m^2], center of mass [m])
        (bus.mass_kg, solid_cylinder(bus.mass_kg, **bus.dimensions_m), bus.position_b_m),
        (tank.mass_kg, solid_sphere(tank.mass_kg, **tank.dimensions_m), tank.position_b_m),
        (magnetometer.mass_kg, solid_sphere(magnetometer.mass_kg, **magnetometer.dimensions_m),
         magnetometer.position_b_m),
        (body.mass_kg, solid_box(body.mass_kg, 0.3, 0.3, 0.4), np.add(body.position_b_m, [0.0, 0.0, -0.2])),
    ]
    tube = mp.cylinder(boom.mass_kg, boom.dimensions_m["diameter"] / 2.0, boom.dimensions_m["height"], shell=True)
    turn = np.array([[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]])  # pitch 90 deg: the axis along x
    bodies.append((boom.mass_kg, turn @ tube.inertia_kg_m2 @ turn.T, boom.position_b_m))
    funnel = mp.shell_mesh(obj_io.read_obj(mesh_path, units="mm").group("camera_hood").mesh, hood.mass_kg)
    bodies.append((hood.mass_kg, funnel.inertia_kg_m2, np.add(hood.position_b_m, funnel.center_of_mass_m)))
    mass = sum(m for m, _i, _r in bodies)  # [kg]
    com = sum(m * np.asarray(r, dtype=float) for m, _i, r in bodies) / mass  # [m]
    inertia = sum(_parallel_axis(m, i, r) for m, i, r in bodies) - _parallel_axis(mass, np.zeros((3, 3)), com)

    assert sc.dry_mass_kg == pytest.approx(mass) and mass == pytest.approx(150.0)  # [kg]
    assert sc.center_of_mass_b_m == pytest.approx(com, abs=1e-9)
    assert com == pytest.approx([0.0203, 0.0, -0.0329], abs=1e-4)  # [m] toward the boom and the camera
    assert np.array(sc.inertia_kg_m2).reshape(3, 3) == pytest.approx(inertia, rel=1e-8, abs=1e-8)
    assert inertia[0, 2] == pytest.approx(0.377, abs=1e-3)  # [kg*m^2] the product of inertia
    assert {f.name.split(":")[0] for f in sc.facets} == {"bus", "boom", "magnetometer", "camera body", "camera hood"}
    assert not any(f.name.startswith("tank") for f in sc.facets)  # hidden inside the bus

    result = _run(scenario)
    rates = np.degrees(np.abs(result.series["cyl-sat.body_rate_omega_BN_B"].data))  # [deg/s]
    assert rates[0] == pytest.approx([0.0, 0.0, 0.0], abs=1e-12)
    assert 0.003 < rates.max() < 0.01


@pytest.mark.slow
def test_44_the_density_scale_sets_the_decay_and_every_case_turns_onto_the_sun(tmp_path):
    """Template 44 (decision TPL-B2): its 12 runs as shipped (seed 44, one
    process). Each run draws an attitude, a body rate, an inertia, an SRP
    coefficient and a density scale within what the batch says; the
    density scale alone sets the orbit's outcomes (rank correlation 1 with
    the along-track offset), as drag at 350 km is about a thousand times
    sunlight's push. Run again, the case with the largest drawn rate starts
    at its drawn attitude and rate and turns its +z face to the Sun within
    15 minutes."""
    import math

    from spacemissionstudio import api
    from spacemissionstudio.engine import monte_carlo_statistics as mcs

    scenario = _template("44")
    config = scenario.monte_carlo
    assert (config.num_runs, config.thread_count, config.seed) == (12, 1, 44)
    assert {d.quantity for d in config.dispersions} == {"attitude_sigma_bn", "angular_rate_bn_b", "inertia_kg_m2",
                                                       "srp_coeff", "density_scale"}
    batch = api.monte_carlo(scenario, tmp_path / "mc")
    assert len(batch.runs) == 12 and not batch.failed
    for drawn in batch.drawn:
        assert 1.2 <= drawn["sat-1 SRP coefficient [-]"] <= 1.8
        assert 0.7 <= drawn["atmospheric density scale [-]"] <= 1.3
        assert all(abs(drawn[f"sat-1 rate {axis} [deg/s]"]) < 1.0 for axis in "xyz")  # [deg/s] 5 sigma
        assert all(abs(drawn[f"sat-1 I{axis}{axis} [kg m^2]"] - nominal) < 5.0
                   for axis, nominal in zip("xyz", (20.5, 20.5, 16.0)))  # [kg*m^2] 5 sigma
    insight = mcs.insight(batch)
    pairs = {(p.input_label, p.outcome_label): p.value for p in insight.sensitivity}
    density = "atmospheric density scale [-]"
    assert pairs[(density, "sat-1 final along-track offset [km]")] == pytest.approx(1.0)
    assert pairs[(density, "sat-1 lowest altitude [km]")] == pytest.approx(-1.0)

    fastest = max(range(12), key=lambda k: sum(batch.drawn[k][f"sat-1 rate {a} [deg/s]"] ** 2 for a in "xyz"))
    case = api.monte_carlo_case(scenario, tmp_path / "mc", fastest)
    rate = np.degrees(case.series["sat-1.body_rate_omega_BN_B"].data[0])  # [deg/s]
    drawn_rate = [batch.drawn[fastest][f"sat-1 rate {a} [deg/s]"] for a in "xyz"]  # the nominal rate and the spread
    assert rate == pytest.approx(drawn_rate, abs=1e-6)
    sigma = case.series["sat-1.attitude_sigma_BN"].data[0]
    drawn_sigma = [batch.drawn[fastest][f"sat-1 attitude MRP {k} [-]"] for k in (1, 2, 3)]
    assert sigma == pytest.approx(drawn_sigma, abs=1e-9)
    sun = case.series["sat-1.sun_heading_body"]
    angle = np.degrees(np.arccos(np.clip(sun.data[:, 2] / np.linalg.norm(sun.data, axis=1), -1.0, 1.0)))  # [deg]
    lit = case.series["sat-1.eclipse.illumination_factor"]
    after = (sun.time_s >= 15 * 60.0) & (np.interp(sun.time_s, lit.time_s, lit.data[:, 0]) > 0.5)
    assert after.any() and angle[after].max() < 1.0  # [deg]
    assert math.isfinite(float(angle[0]))


@pytest.mark.slow
def test_45_the_conservative_sun_decays_the_orbit_faster_over_a_chained_run():
    """Template 45 (decision TPL-B3): 110 days at 400 km from 1 January
    2030, past Basilisk's 104-day clock: the run is chained (90 days, then
    20) into one result on one time axis, every value finite to the end
    and no step at day 90. MSFC's 95th percentile (F10.7 about 78 and Ap
    about 15 in early 2030, from the prediction the app ships) lowers the
    mean semi-major axis by about 9.2 km, the 5th percentile (F10.7 about
    70, Ap about 6) by about 6.0 km. Two runs of about 30 s each."""
    from datetime import date

    from spacemissionstudio.engine import long_run, spaceweather

    scenario = _template("45")
    assert scenario.sim_settings.duration_days == 110.0 and scenario.space_weather.forecast_percentile == 95.0
    assert [s / 86400.0 for s in long_run.segment_lengths_s(scenario)] == pytest.approx([90.0, 20.0])
    msfc = spaceweather.load_msfc(Path(spaceweather.__file__).resolve().parents[1] / "data" / "spaceweather"
                                  / "nov2026f10-prd.txt")
    assert msfc.values(date(2030, 1, 1), 95.0)[:2] == pytest.approx((78.7, 15.9))
    assert msfc.values(date(2030, 1, 1), 5.0)[:2] == pytest.approx((70.6, 6.2))

    def decay_km(result):
        a = _mean_elements(result, "sat-1", "semi_major_axis") / 1e3  # [km]
        return float(a[-1] - a[0])

    result = _run(scenario)
    position = result.series["sat-1.position_N"]
    assert position.time_s[-1] == pytest.approx(110.0 * 86400.0)  # [s]
    assert np.isfinite(position.data).all()
    assert np.diff(position.time_s) == pytest.approx(600.0, abs=1e-6)  # [s] Record every, no repeated sample
    step = np.linalg.norm(np.diff(position.data, axis=0), axis=1)  # [m] in 600 s
    at_90 = int(np.searchsorted(position.time_s, 90.0 * 86400.0))
    assert step[at_90 - 3:at_90 + 3] == pytest.approx(np.median(step), rel=0.01)
    conservative = decay_km(result)
    assert conservative == pytest.approx(-9.2, abs=0.2)

    low = _template("45")
    low.space_weather.forecast_percentile = 5.0
    quiet = decay_km(_run(low))
    assert quiet == pytest.approx(-6.0, abs=0.2)
    assert conservative / quiet == pytest.approx(1.5, abs=0.1)


def test_46_the_sequence_fires_in_a_loop_until_420_km_and_the_script_reports_the_orbit():
    """Template 46 (decision TPL-B4): the assignments switch the thruster
    off and on, the while loop fires 0.05 day at a time until the altitude
    is 420 km (21 times, to day 1.3), the if takes its snapshot, and the
    script block's semi-major axis and period (vis-viva and Kepler's third
    law) match the run's own orbit elements. The delta-V is about 11.7 m/s
    and the propellant used is F t / (Isp g0), about 123 g. The run refuses
    the script block without consent."""
    import math

    from spacemissionstudio import constants
    from spacemissionstudio.engine.mission_engine import MissionEngine, MissionEngineError

    scenario = _template("46")
    assert [c.kind for c in scenario.mission_sequence] == ["assignment", "propagate", "report", "assignment", "while",
                                                          "assignment", "if", "script_block", "propagate", "report"]
    with pytest.raises(MissionEngineError, match="script_block"):
        MissionEngine(_template("46")).run()
    result, summary = MissionEngine(scenario, allow_scripts=True).run()
    reports = {r.label: r for r in summary.reports}
    assert list(reports) == ["Before the raise", "Raised", "Script: semi-major axis and period", "End"]
    sma = "raise-sat.orbit_elements.semi_major_axis"
    assert reports["Before the raise"].t_s == pytest.approx(0.25 * 86400.0)  # [s]
    assert float(reports["Before the raise"].values["raise-sat.constant_thrust.delta_v"][0]) == 0.0  # off
    assert reports["Raised"].t_s == pytest.approx(1.3 * 86400.0)  # [s] 21 times 0.05 day
    radius_m = constants.EARTH_EQUATORIAL_RADIUS_M  # [m]
    raised_m = float(reports["Raised"].values[sma][0])  # [m]
    assert 420.0e3 <= raised_m - radius_m < 421.5e3  # [m] two-body, a circle: the altitude
    script = reports["Script: semi-major axis and period"].values
    assert float(script["raise-sat.script.semi_major_axis_km"]) == pytest.approx(raised_m / 1e3, abs=1e-3)
    period_min = 2.0 * math.pi * math.sqrt(raised_m ** 3 / constants.EARTH_GM_M3_S2) / 60.0  # [min]
    assert float(script["raise-sat.script.period_min"]) == pytest.approx(period_min, rel=1e-6)
    assert float(script["raise-sat.script.semi_major_axis_km"]) == pytest.approx(6798.7, abs=0.1)
    assert float(script["raise-sat.script.period_min"]) == pytest.approx(93.0, abs=0.05)
    end = reports["End"].values
    assert float(end[sma][0]) == pytest.approx(raised_m, abs=50.0)  # [m] the thruster stayed off
    thrust = scenario.spacecraft[0].constant_thrust
    delta_v = float(end["raise-sat.constant_thrust.delta_v"][0])  # [m/s]
    used_kg = thrust.propellant_kg - float(end["raise-sat.constant_thrust.propellant_remaining"][0])
    fired_s = 21 * 0.05 * 86400.0  # [s]
    assert used_kg == pytest.approx(thrust.thrust_n * fired_s / (thrust.isp_s * constants.STANDARD_GRAVITY_M_S2),
                                    rel=1e-3)
    assert delta_v == pytest.approx(11.7, abs=0.05) and used_kg == pytest.approx(0.123, abs=0.001)  # [m/s], [kg]


def test_47_each_faulty_sensor_reports_its_fault_and_the_attitude_is_the_same():
    """Template 47 (decision TPL-B5): faulty-sat's css-2, facing away from
    the Sun, reads 1.0 all the time where healthy-sat's reads 0; its
    magnetometer's z axis is now and then three times the field (about 1 %
    of the samples) while x and y match; its thermal sensor reads 20 C while
    healthy-sat's warms from 0 to about 53 C in sunlight and cools in the
    shadow. Both fly the same attitude: the flight software reads the true
    state. Bounds only for the spikes: another standard library draws other
    ones (golden_capture)."""
    scenario = _template("47")
    faulty = {s.name: s.params for s in scenario.spacecraft[1].sensors}
    assert faulty["css-2"]["fault_mode"] == "stuck_max" and faulty["mag-1"]["fault_mode"] == "spiking"
    assert faulty["therm-1"]["measurement_fault_mode"] == "stuck_value"
    result = _run(scenario)

    def reading(name, sensor):
        return result.series[f"{name}-sat.sensor.{sensor}"]

    assert (reading("healthy", "css-2").data == 0.0).all()
    assert (reading("faulty", "css-2").data == 1.0).all()
    healthy_css = reading("healthy", "css-1").data[:, 0]
    assert healthy_css.max() > 1.0 and healthy_css[-1] == 0.0  # full Sun (closer than 1 au in March), then shadow
    assert (reading("faulty", "css-1").data[:, 0] == healthy_css).all()  # no fault on css-1

    healthy_mag, faulty_mag = reading("healthy", "mag-1").data, reading("faulty", "mag-1").data  # [T]
    assert faulty_mag[:, :2] == pytest.approx(healthy_mag[:, :2], abs=1e-6)  # [T] noise only
    # z: each reading is the field, or three times it (a spike). The two
    # spacecraft draw their own noise (1e-7 T, another seed each, and other
    # draws on another C++ library), so each is compared within 1 uT, 7 sigma
    # of the difference (3 uT for a spike: three times the noise), where the
    # field is strong enough (10 uT) that the two cases cannot be confused.
    healthy_z, faulty_z = healthy_mag[:, 2], faulty_mag[:, 2]  # [T]
    strong = np.abs(healthy_z) > 10e-6  # [T]
    plain = np.abs(faulty_z - healthy_z) < 1e-6  # [T]
    spiked = np.abs(faulty_z - 3.0 * healthy_z) < 3e-6  # [T]
    assert strong.mean() > 0.5 and (plain | spiked)[strong].all()
    assert 0.003 < spiked[strong].mean() < 0.03

    healthy_temp, faulty_temp = reading("healthy", "therm-1"), reading("faulty", "therm-1")  # [C]
    assert (faulty_temp.data == 20.0).all()
    assert healthy_temp.data[0, 0] == 0.0 and healthy_temp.data[:, 0].max() == pytest.approx(53.0, abs=1.0)
    lit = result.series["healthy-sat.eclipse.illumination_factor"]
    shadow_s = float(lit.time_s[np.argmax(lit.data[:, 0] < 0.5)])  # [s]
    assert shadow_s / 60.0 == pytest.approx(25.1, abs=0.5)  # [min]
    assert healthy_temp.data[-1, 0] < healthy_temp.data[:, 0].max() - 20.0
    assert result.series["faulty-sat.attitude_sigma_BN"].data == pytest.approx(
        result.series["healthy-sat.attitude_sigma_BN"].data, abs=1e-12)
