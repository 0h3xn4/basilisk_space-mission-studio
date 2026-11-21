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
"""A validation message as a form shows it: each field code in it
("station_keeping.thrust_n", "sim_settings.duration_days") replaced by the
label the form gives that field, after its section's title ("Station
keeping: Reboost thrust [N]"). The messages themselves keep their codes:
the command line, the Log and the scenario file speak in them.

A form passes :func:`labelled` its own lookup from a code to a field's
title; a code it does not know stays as it is.

The label maps (UI audit B4, UI-08): the professional term a form shows
for a device kind ("Star tracker" for ``star_tracker``), a guidance mode
("Sun pointing" for ``sunSafePoint``), a body ("Mars barycentre" for
``mars barycenter``) and a configuration parameter ("Residual propellant
fraction" for ``propellant_budget.residual_fraction``, UI-19). The scenario file, the command line and the
messages keep the codes; a form shows the label and keeps the code as
the item's data, so it writes the file exactly as before.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from PySide6.QtWidgets import QGroupBox, QWidget

from ..engine.scenario_explainer import FSW_MODE_NAMES
from ..idm_devices import KIND_LABELS
from .workspace_panels import field_label

#: Device kinds (``SensorConfig.kind``, ``ActuatorConfig.kind``) as the
#: forms name them: the IDM-CIC import's names, and the thermal sensor.
DEVICE_KIND_LABELS = {**KIND_LABELS, "thermal": "Thermal sensor"}
#: Guidance modes (``SpacecraftConfig.fsw_mode``): the names the
#: Overview and the run summaries use.
GUIDANCE_MODE_LABELS = dict(FSW_MODE_NAMES)
#: Bodies (``GravityConfig.central_body``, ``third_body_perturbers``).
BODY_LABELS = {"sun": "Sun", "mercury": "Mercury", "venus": "Venus", "earth": "Earth", "moon": "Moon",
               "mars barycenter": "Mars barycentre", "jupiter barycenter": "Jupiter barycentre",
               "eros": "433 Eros"}

#: The areas of the project configuration's parameters (``config.registry``),
#: as Scenario › Assumptions heads them.
AREA_LABELS = {
    "propellant_budget": "Propellant budget", "lifetime": "Orbital lifetime", "power": "Power",
    "link": "RF link", "data_handling": "Data handling", "results": "Results", "dynamics": "Dynamics",
    "space_weather": "Space weather", "tle": "TLE", "orbit_control": "Orbit control",
    "geo_station_keeping": "GEO station keeping", "roe_formation": "ROE formation",
    "flight_software": "Flight software", "navigation": "Navigation", "checks": "Scenario checks",
    "explain": "Scenario explanation", "monte_carlo": "Monte Carlo", "analyses": "Model analyses",
    "reentry": "Re-entry",
}
#: The parameters of the project configuration, as Scenario › Assumptions
#: names them; the key (``propellant_budget.cam_count_factor``) is what the
#: configuration file and the command line use.
PARAMETER_LABELS = {
    "propellant_budget.cam_count_factor": "Collision avoidance count factor",
    "propellant_budget.cam_sma_change_m": "Collision avoidance semi-major axis change",
    "propellant_budget.attitude_propellant_factor": "Attitude propellant factor",
    "propellant_budget.controlled_last_burn_margin": "Controlled re-entry last burn margin",
    "propellant_budget.residual_fraction": "Residual propellant fraction",
    "propellant_budget.uncertainty_fraction": "Loading and gauging uncertainty",
    "propellant_budget.eol_drag_coeff": "End-of-life drag coefficient",
    "propellant_budget.operations_drag_coeff": "Operations drag coefficient",
    "propellant_budget.operations_percentile": "Operations solar-activity percentile",
    "propellant_budget.eol_percentile": "End-of-life solar-activity percentile",
    "propellant_budget.geo_graveyard_base_m": "GEO graveyard raise, base",
    "propellant_budget.geo_graveyard_per_cr_a_m": "GEO graveyard raise per Cr·A/m",
    "propellant_budget.margin_policy": "Margin policy",
    "propellant_budget.convergence_kg": "Budget convergence",
    "propellant_budget.max_iterations": "Budget iterations, maximum",
    "propellant_budget.launch_delays_years": "Launch delays",
    "propellant_budget.scaled_run_ratio": "Scaled run ratio",
    "propellant_budget.altitude_step_km": "Altitude trade step",
    "propellant_budget.altitude_floor_km": "Altitude trade floor",
    "lifetime.reentry_altitude_km": "Re-entry altitude",
    "lifetime.ring_points": "Drag averaging points per orbit",
    "lifetime.max_step_s": "Decay step, maximum",
    "lifetime.max_perigee_drop_fraction": "Perigee drop per step, maximum",
    "lifetime.zero_debris_years": "Zero-debris disposal limit",
    "lifetime.iadc_years": "IADC disposal limit",
    "lifetime.makeup_step_s": "Drag make-up sampling step",
    "lifetime.default_drag_coeff": "Default drag coefficient",
    "lifetime.default_forecast_percentile": "Default solar-activity percentile",
    "lifetime.default_horizon_years": "Default horizon",
    "lifetime.default_deorbit_perigee_km": "Default deorbit perigee",
    "power.degradation": "Solar panel degradation model",
    "power.years_in_orbit_at_start": "Time in orbit at start",
    "power.degradation_per_year": "Yearly degradation",
    "power.displacement_damage_dose_per_year_mev_g": "Yearly displacement damage dose",
    "power.dose_fit_c": "Dose fit C",
    "power.dose_fit_dx_mev_g": "Dose fit Dx",
    "power.uv_darkening_factor": "UV darkening factor",
    "power.thermal_cycling_factor": "Thermal cycling factor",
    "link.required_margin_db": "Required link margin",
    "link.pointing_loss_coeff_db": "Pointing loss coefficient",
    "link.max_pointing_loss_db": "Pointing loss, maximum",
    "link.atmospheric_loss": "Atmospheric loss model",
    "link.surface_pressure_hpa": "Surface pressure",
    "link.surface_temperature_k": "Surface temperature",
    "link.surface_water_vapour_density_g_m3": "Surface water-vapour density",
    "data_handling.packet_size_bits": "Packet size",
    "data_handling.explainer_pass_minutes": "Pass length for the explanation",
    "results.sma_window_orbits": "Mean semi-major axis window",
    "results.umbra_sunlight_fraction": "Umbra sunlight fraction",
    "results.pointing_converged_deg": "Pointing converged below",
    "results.battery_critical_fraction": "Battery critical fraction",
    "dynamics.integrator_relative_tolerance": "Integrator relative tolerance",
    "dynamics.integrator_absolute_tolerance": "Integrator absolute tolerance",
    "dynamics.reentry_altitude_km": "Re-entry altitude",
    "dynamics.shadowing_bodies": "Shadowing bodies",
    "dynamics.reentry_check_s": "Re-entry check interval",
    "dynamics.reentry_near_perigee_km": "Low perigee for re-entry checks",
    "dynamics.reentry_near_check_s": "Re-entry check interval, low perigee",
    "dynamics.conservation_tolerance": "Conservation tolerance",
    "space_weather.msfc_repeat_months": "MSFC prediction repeat",
    "tle.age_warning_days": "TLE age warning",
    "orbit_control.eccentricity_gate_factor": "Eccentricity gate factor",
    "orbit_control.min_impulse_skip_fraction": "Minimum impulse skip fraction",
    "orbit_control.phasing_non_convergent_cycles": "Phasing non-convergent cycles",
    "orbit_control.relative_sma_trim_m": "Relative semi-major axis trim",
    "geo_station_keeping.max_half_arc_deg": "North-south burn half-arc, maximum",
    "geo_station_keeping.inclination_reset_fraction": "Inclination reset fraction",
    "geo_station_keeping.fit_interval_s": "East-west fit interval",
    "geo_station_keeping.drift_stop_fraction": "Drift stop fraction",
    "geo_station_keeping.ns_completion_fraction": "North-south completion fraction",
    "roe_formation.holding_check_fraction": "Holding check interval",
    "roe_formation.glide_orbits": "Glide-in orbits",
    "roe_formation.direct_dl_factor": "Direct along-track correction factor",
    "roe_formation.eclipse_retries": "Eclipse retries",
    "roe_formation.drag_min_orbits": "Drag fit orbits, minimum",
    "roe_formation.drag_jump_m": "Drag fit jump",
    "roe_formation.drag_hold_fraction": "Drag hold fraction",
    "roe_formation.drag_lookahead_orbits": "Drag look-ahead",
    "roe_formation.drag_trigger_fraction": "Drag trigger fraction",
    "roe_formation.drag_significance_fraction": "Drag significance fraction",
    "roe_formation.slow_drift_fraction": "Slow drift fraction",
    "roe_formation.stop_band_factor": "Stop band factor",
    "roe_formation.cutback_band_factor": "Cut-back band factor",
    "roe_formation.stop_reached_fraction": "Stop reached fraction",
    "roe_formation.min_check_s": "Check interval, minimum",
    "roe_formation.replan_shift_fraction": "Replan shift fraction",
    "flight_software.thruster_min_fire_time_s": "Thruster minimum fire time",
    "flight_software.thruster_level_on": "Thruster on level",
    "flight_software.thruster_level_off": "Thruster off level",
    "navigation.opnav_ukf_alpha": "Optical navigation UKF alpha",
    "navigation.opnav_ukf_beta": "Optical navigation UKF beta",
    "navigation.opnav_ukf_kappa": "Optical navigation UKF kappa",
    "navigation.opnav_ukf_noise_scale": "Optical navigation UKF noise scale",
    "navigation.landmark_filter_max_step_s": "Landmark filter step, maximum",
    "checks.pass_step_s": "Pass prediction step",
    "checks.pass_horizon_days": "Pass prediction horizon",
    "checks.pass_lookahead_days": "Pass look-ahead",
    "checks.many_samples": "Samples per series, maximum",
    "checks.coarse_recording_factor": "Coarse recording factor",
    "checks.long_step_s": "Long dynamics step",
    "checks.late_first_pass_fraction": "Late first pass fraction",
    "checks.css_facing_min_cosine": "Sun sensor facing cosine, minimum",
    "explain.sso_tolerance_deg": "Sun-synchronous tolerance",
    "explain.differential_drag_fraction": "Differential drag fraction",
    "explain.passive_safety_margin_m": "Passive safety margin",
    "explain.camera_axis_tolerance_deg": "Camera axis tolerance",
    "monte_carlo.spread_statistic": "Spread statistic",
    "monte_carlo.probability_bound": "Probability bound",
    "analyses.observer_sun_depression_deg": "Observer Sun depression",
    "reentry.breakup_altitude_km": "Break-up altitude",
    "reentry.casualty_energy_j": "Casualty energy threshold",
    "reentry.casualty_risk_limit": "Casualty risk limit",
}


def kind_label(kind: str) -> str:
    """The label of a device kind; an unknown kind as it is."""
    return DEVICE_KIND_LABELS.get(kind, kind)


def mode_label(mode: str) -> str:
    """The label of a guidance mode; an unknown mode as it is."""
    return GUIDANCE_MODE_LABELS.get(mode, mode)


def body_label(body: str) -> str:
    """The label of a body; an unknown body as it is."""
    return BODY_LABELS.get(body, body)


def area_label(area: str) -> str:
    """The heading of a configuration area; an unknown area (a plugin's) as it is."""
    return AREA_LABELS.get(area, area)


def parameter_label(name: str) -> str:
    """The name of a configuration parameter; an unknown one (a plugin's) as its key."""
    return PARAMETER_LABELS.get(name, name)

# A word made of lower-case parts joined by "_" or ".": not inside a file
# name or path (a neighbouring "-", "/", "\\" or "."), a quoted key or an
# indexed name ("params['rw_type']"), nor a call. A word with neither "_"
# nor "." is plain English ("eccentricity") and is left alone.
_CODE = re.compile(r"(?<![\w.\-/\\'\"])[a-z][a-z0-9]*(?:[_.][a-z][a-z0-9]*|_[0-9]+)*(?![\w\-/\\'\"(\[]|\.\w)")


def section_title(widget: QWidget | None) -> str:
    """The title of the nearest group box around ``widget``, up to its
    first " (" or ":": "Station keeping" for "Station keeping (altitude
    maintenance, delta-V + fuel tracking)"."""
    node = widget
    while node is not None:
        if isinstance(node, QGroupBox) and node.title():
            return _short(node.title())
        node = node.parentWidget()
    return ""


def field_title(widget: QWidget | None) -> str:
    """The field's label after its section's title ("Station keeping:
    Reboost thrust [N]"), its label alone when it has no section or the
    label already names it, or the section alone for a section's own box;
    "" when the form gives it no label."""
    if widget is None:
        return ""
    if isinstance(widget, QGroupBox):
        return _short(widget.title())
    label = _plain(field_label(widget)).split(" (")[0].strip()  # "Restore tolerance [-] (fraction of target)"
    if not label:
        return ""
    section = section_title(widget.parentWidget())
    if section and not label.lower().startswith(section.lower()):
        return f"{section}: {label}"
    return label


def attribute_title(owner: QWidget, code: str, section: str, aliases: dict | None = None) -> str:
    """The title of ``owner``'s widget for a field of ``section``
    ("constellation.num_planes" or "num_planes": ``owner.num_planes``,
    or the attribute ``aliases`` names for it), or ""."""
    if code.startswith(section + "."):
        code = code[len(section) + 1:]
    if "." in code:
        return ""
    widget = getattr(owner, (aliases or {}).get(code, code), None)
    return field_title(widget) if isinstance(widget, QWidget) else ""


def labelled(text: str, title_for: Callable[[str], str]) -> str:
    """``text`` with each field code ``title_for`` gives a title replaced
    by that title. A code without a section ("target_altitude_km" in
    "station_keeping.deadband_km must be < target_altitude_km") is first
    looked up in the section of the dotted code before it; a title whose
    section an earlier one named drops it ("Fuel tank: Propellant mass
    [kg] must be between 0 and Tank capacity [kg]")."""
    sections: list = []
    named: set = set()

    def title_of(code: str) -> str:
        if "." in code:
            sections.append(code.rsplit(".", 1)[0])
        elif sections:
            title = title_for(f"{sections[-1]}.{code}")
            if title:
                return title
        return title_for(code)

    def replace(match: re.Match) -> str:
        code = match.group(0)
        if "_" not in code and "." not in code:
            return code
        title = title_of(code)
        if not title:
            return code
        section, _, label = title.rpartition(": ")
        if section in named:
            return label
        if section:
            named.add(section)
        return title

    return _CODE.sub(replace, text)


def _plain(text: str) -> str:
    """``text`` without its mnemonic "&" ("&&" is a shown "&")."""
    return text.replace("&&", "\0").replace("&", "").replace("\0", "&")


def _short(title: str) -> str:
    return re.split(r" \(|:", _plain(title), maxsplit=1)[0].strip()
