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

"""One-off generator for spacemissionstudio/scenarios/templates/*.json -- run
directly (``python3 scripts/_generate_templates.py``) whenever a template
needs regenerating after a schema change. Not part of the installed
package and not imported by anything else; building the templates through
``schema.scenario`` dataclasses + ``Scenario.validate()`` (rather than
hand-writing JSON) is what guarantees they're actually schema-valid --
this script is the source of truth for that construction logic, kept
around instead of thrown away so future schema/field changes have a clear
place to regenerate from.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from spacemissionstudio.engine.constellation import WalkerConstellationRequest, generate_walker_constellation

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _template_descriptions import DESCRIPTIONS  # noqa: E402 -- short, user-facing; see that module
from spacemissionstudio.engine.facets import box_facets
from spacemissionstudio.config import registry
from spacemissionstudio.engine.orbit_design import (
    geostationary_elements_deg,
    raan_for_ltan_deg,
    sun_synchronous_inclination_deg,
)
from spacemissionstudio.schema.scenario import (
    CommsPointingConfig,
    ConstantThrustConfig,
    DataHandlingConfig,
    DispersionConfig,
    FuelTankConfig,
    GeoStationKeepingConfig,
    GravityConfig,
    GroundStationConfig,
    InstrumentConfig,
    MagneticMomentumManagementConfig,
    MomentumDumpingConfig,
    MonteCarloConfig,
    MonteCarloRequirementConfig,
    NavigationErrorConfig,
    LandmarkNavigationConfig,
    OpticalNavigationConfig,
    OrbitIC,
    PhasingKeepingConfig,
    PowerConfig,
    RoeTargetConfig,
    RFLinkConfig,
    Scenario,
    SensorConfig,
    ActuatorConfig,
    SimSettings,
    SolarArrayConfig,
    SpacecraftConfig,
    SpaceWeatherConfig,
    StationKeepingConfig,
)

# 3.0: ESA AD10 Sec. 5.2, now the parameter propellant_budget.operations_drag_coeff (config.parameters)
OPERATIONS_DRAG_COEFF = registry.default("propellant_budget.operations_drag_coeff")  # [-]

OUT_DIR = Path(__file__).resolve().parent.parent / "spacemissionstudio" / "scenarios" / "templates"

_RPM_TO_RAD_S = math.pi / 30.0


def _box_inertia(mass_kg: float, size_m: tuple) -> list:
    """Row-major principal inertia [kg*m^2] of a uniform box of ``size_m``
    (x, y, z) [m]: I_xx = m (y^2 + z^2) / 12, and so on."""
    x, y, z = size_m
    return [round(mass_kg * (y * y + z * z) / 12.0, 1), 0.0, 0.0,
            0.0, round(mass_kg * (x * x + z * z) / 12.0, 1), 0.0,
            0.0, 0.0, round(mass_kg * (x * x + y * y) / 12.0, 1)]


# Every template flies a 100-500 kg spacecraft, the class this app is for.
# Three buses, each with an inertia derived from its own mass and size:
_MICROSAT_MASS_KG = 150.0  # [kg]
_MICROSAT_SIZE_M = (0.8, 0.8, 1.0)  # [m] -> I = 20.5, 20.5, 16.0 kg*m^2
_SMALLSAT_MASS_KG = 300.0  # [kg]
_SMALLSAT_SIZE_M = (1.2, 1.2, 1.5)  # [m] -> I = 92.3, 92.3, 72.0 kg*m^2
_WING_MASS_KG = 8.0  # [kg] each of template 27's two wings
_WING_SIZE_M = (2.4, 1.0)  # [m] span, width
_WING_FIRST_MODE_HZ = 0.2  # [Hz] assumed, with the hub held fixed
_WING_DAMPING_RATIO = 0.005  # [-] assumed structural damping
_FLEX_DURATION_DAYS = 0.1  # [day] about one and a half orbits
_LARGE_SMALLSAT_MASS_KG = 500.0  # [kg]
_LARGE_SMALLSAT_SIZE_M = (1.2, 1.2, 1.6)  # [m] -> I = 166.7, 166.7, 120.0 kg*m^2

# A 6 N*m*s, 50 mN*m wheel at up to 6000 RPM: the size of the VECTRONIC
# VRW-D-6 in engine/device_catalog.py, which suits the 150 kg bus. "custom"
# derives the rotor inertia from maxMomentum/Omega_max, so any maxMomentum
# a wizard sets stays valid (a named Honeywell type accepts only three).
_MICROSAT_WHEEL = {"rw_type": "custom", "maxMomentum": 6.0, "Omega_max": 6000.0, "u_max": 0.05}


def _corner_thrusters(half_size_m: tuple, max_thrust_n: float, **extra) -> list:
    """Eight thrusters on the bus corners, two per couple axis (the layout
    of Basilisk's examples/BskSim, scaled to this bus). Returns one
    thruster ``params`` dict each."""
    hx, hy, hz = half_size_m
    positions = [[-hx, -hy, hz], [hx, -hy, -hz], [hx, -hy, hz], [hx, hy, -hz],
                 [hx, hy, hz], [-hx, hy, -hz], [-hx, hy, hz], [-hx, -hy, -hz]]
    directions = [[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0],
                  [-1, 0, 0], [1, 0, 0], [0, -1, 0], [0, 1, 0]]
    return [{"r_B": pos, "tHat_B": direction, "MaxThrust": max_thrust_n, **extra}
            for pos, direction in zip(positions, directions)]

# Skewed-pyramid 4-wheel layout, beta=52deg -- the exact spin axes
# examples/scenarioMtbMomentumManagement.py uses, computed here (not
# copied as decimals) so the values stay traceably derived from that
# same beta angle.
_MTB_DEMO_BETA_RAD = 52.0 * math.pi / 180.0
_MTB_DEMO_RW_AXES = [
    [0.0, math.cos(_MTB_DEMO_BETA_RAD), math.sin(_MTB_DEMO_BETA_RAD)],
    [0.0, math.sin(_MTB_DEMO_BETA_RAD), -math.cos(_MTB_DEMO_BETA_RAD)],
    [math.cos(_MTB_DEMO_BETA_RAD), -math.sin(_MTB_DEMO_BETA_RAD), 0.0],
    [-math.cos(_MTB_DEMO_BETA_RAD), -math.sin(_MTB_DEMO_BETA_RAD), 0.0],
]

# -- Sun-synchronous (10:30 AM LTAN) orbit + Berlin ground station ---------
# Real user request: templates should default to a realistic Sun
# -synchronous orbit (10:30 AM local time of ascending node -- the most
# common real operational choice for Earth-observation/commercial
# smallsats) and a Berlin, Germany ground station, wherever a template's
# own lesson doesn't specifically need something else (GEO/Walker
# -coverage/transfer-trajectory geometry, or a sun-angle/geomagnetic-field
# -sensitive demo whose numeric claims were confirmed against its CURRENT
# orbit -- see each affected build_*() function's own comment for which
# templates keep their existing orbit and why).
#
# sun_synchronous_inclination_deg()/raan_for_ltan_deg() used to be defined
# HERE, as this dev-only generator script's own private helpers -- moved
# to engine.orbit_design (Phase 6 audit fix) so the running app can import
# the exact same, already-verified implementation these 12 templates rely
# on, instead of a user having no way to reproduce a Sun-synchronous orbit
# by hand when building a bespoke scenario from scratch. See that
# module's own docstring for the full verification details (J2 secular
# RAAN-rate derivation, the three real Sun-right-ascension reference
# points). This is a pure import -- zero behavior change here.


def _berlin_ground_station(**overrides) -> GroundStationConfig:
    """Berlin, Germany (city-center reference: Alexanderplatz, ~34 m
    above the WGS84 ellipsoid) -- the real user-requested baseline ground
    station for every template that has one.
    """
    params = dict(name="berlin-gs", latitude_deg=52.5200, longitude_deg=13.4050, altitude_m=34.0,
                  min_elevation_deg=10.0)
    params.update(overrides)
    return GroundStationConfig(**params)


def _real_space_weather() -> SpaceWeatherConfig:
    """Drag from NRLMSISE-00 driven by real data shipped with the app
    (``source="bundled"``: CelesTrak's observed record, then NASA MSFC's
    50th-percentile prediction, the nominal case) -- a fresh instance per
    call, since ``SpaceWeatherConfig`` is mutable. Solar activity
    "Conservative" in Propagation setup is MSFC's 95th percentile (ESA
    AD10 Sec. 5.9, operations).
    """
    return SpaceWeatherConfig(source="bundled", atmosphere_model="nrlmsise00", forecast_percentile=50.0)


def _save(scenario: Scenario, filename: str) -> None:
    scenario.validate()  # fail loudly here, not for whoever opens the file later
    path = OUT_DIR / filename
    scenario.save(path)
    print(f"wrote {path}")


def build_01_two_body_circular_orbit() -> Scenario:
    return Scenario(
        name="01 - Two-body circular orbit",
        description=(
            DESCRIPTIONS["01"]
        ),
        epoch_utc="2030-01-01T00:00:00",
        simulation_mode="orbit_only",
        gravity=GravityConfig(central_body="earth", central_body_degree=0),
        sim_settings=SimSettings(duration_days=1.0, dynamics_task_rate_s=30.0, integrator="rkf78"),
        spacecraft=[
            SpacecraftConfig(
                name="sat-1",
                orbit=OrbitIC(type="classical_elements", semi_major_axis_km=6778.0, eccentricity=0.0,
                               inclination_deg=sun_synchronous_inclination_deg(6778.0),
                               raan_deg=raan_for_ltan_deg("2030-01-01T00:00:00"),
                               arg_periapsis_deg=0.0, true_anomaly_deg=0.0),
                dry_mass_kg=_LARGE_SMALLSAT_MASS_KG,
                inertia_kg_m2=_box_inertia(_LARGE_SMALLSAT_MASS_KG, _LARGE_SMALLSAT_SIZE_M),
            ),
        ],
    )


def build_02_elliptical_orbit_with_perturbations() -> Scenario:
    return Scenario(
        name="02 - Elliptical orbit with perturbations",
        description=(
            DESCRIPTIONS["02"]
        ),
        epoch_utc="2030-01-01T00:00:00",
        simulation_mode="orbit_only",
        gravity=GravityConfig(central_body="earth", central_body_degree=10, third_body_perturbers=["sun", "moon"]),
        sim_settings=SimSettings(duration_days=3.0, dynamics_task_rate_s=1.0, integrator="rkf78"),
        spacecraft=[
            SpacecraftConfig(
                name="sat-1",
                orbit=OrbitIC(type="classical_elements", semi_major_axis_km=24396.0, eccentricity=0.7,
                               inclination_deg=28.5, raan_deg=0.0, arg_periapsis_deg=180.0, true_anomaly_deg=0.0),
                dry_mass_kg=_LARGE_SMALLSAT_MASS_KG,
                inertia_kg_m2=_box_inertia(_LARGE_SMALLSAT_MASS_KG, _LARGE_SMALLSAT_SIZE_M),
            ),
        ],
    )


def build_03_geo_station_keeping() -> Scenario:
    # A 500 kg spacecraft in the 10 deg E slot (a European one), held in a
    # +/-0.05 deg longitude box and below 0.05 deg inclination. It starts in
    # Earth's TRUE equator (engine.orbit_design.geostationary_elements_deg):
    # i = 0 in J2000 is already ~0.17 deg inclined to it by 2030, which the
    # first real run showed as an immediate north-south burn. a = 42166.2 km
    # is the geosynchronous radius once J2 is included. Confirmed in a real
    # Basilisk run, see tests/test_template_claims.py.
    epoch = "2030-01-01T00:00:00"
    inclination_deg, raan_deg, true_anomaly_deg = geostationary_elements_deg(epoch, 10.0)
    return Scenario(
        name="03 - GEO station-keeping",
        description=(
            DESCRIPTIONS["03"]
        ),
        epoch_utc=epoch,
        simulation_mode="orbit_only",
        gravity=GravityConfig(central_body="earth", central_body_degree=10, third_body_perturbers=["sun", "moon"]),
        sim_settings=SimSettings(duration_days=45.0, dynamics_task_rate_s=30.0, integrator="rkf78"),
        spacecraft=[
            SpacecraftConfig(
                name="geo-sat-1",
                orbit=OrbitIC(type="classical_elements", semi_major_axis_km=42166.2, eccentricity=0.0,
                               inclination_deg=inclination_deg, raan_deg=raan_deg, arg_periapsis_deg=0.0,
                               true_anomaly_deg=true_anomaly_deg),
                dry_mass_kg=_LARGE_SMALLSAT_MASS_KG,
                inertia_kg_m2=_box_inertia(_LARGE_SMALLSAT_MASS_KG, _LARGE_SMALLSAT_SIZE_M),
                enable_srp=True, srp_coeff=1.3, srp_area_m2=8.0,
                geo_station_keeping=GeoStationKeepingConfig(
                    target_longitude_deg=10.0, longitude_deadband_deg=0.05, inclination_max_deg=0.05,
                    thrust_n=1.0, isp_s=220.0, propellant_kg=50.0,  # [N], [s] (hydrazine), [kg]
                ),
            ),
        ],
    )


def build_04_walker_constellation() -> Scenario:
    # 700 km is genuinely drag-relevant LEO altitude -- drag/SRP enabled
    # on the shared template so generate_walker_constellation() copies it
    # onto every satellite (see this function's own description update
    # below for the reasoning).
    template = SpacecraftConfig(
        name="placeholder",  # replaced per-satellite by generate_walker_constellation()
        orbit=OrbitIC(type="classical_elements", semi_major_axis_km=1.0, eccentricity=0.0,
                       inclination_deg=0.0, raan_deg=0.0, arg_periapsis_deg=0.0, mean_anomaly_deg=0.0,
                       anomaly_type="mean"),
        dry_mass_kg=180.0,
        inertia_kg_m2=_box_inertia(180.0, _MICROSAT_SIZE_M),
        enable_drag=True, drag_coeff=OPERATIONS_DRAG_COEFF, drag_area_m2=1.0,
        enable_srp=True, srp_coeff=1.3, srp_area_m2=1.0,
    )
    request = WalkerConstellationRequest(
        total_satellites=6, num_planes=2, phasing_factor=1, altitude_km=700.0, inclination_deg=53.0,
        pattern="delta", name_prefix="leo",
    )
    spacecraft = generate_walker_constellation(request, template)
    return Scenario(
        name="04 - Walker delta constellation",
        description=(
            DESCRIPTIONS["04"]
        ),
        epoch_utc="2030-01-01T00:00:00",
        simulation_mode="orbit_only",
        gravity=GravityConfig(central_body="earth", central_body_degree=10, third_body_perturbers=["sun", "moon"]),
        sim_settings=SimSettings(duration_days=1.0, dynamics_task_rate_s=30.0, integrator="rkf78"),
        space_weather=_real_space_weather(),
        spacecraft=spacecraft,
    )


def build_05_formation_flying_phasing() -> Scenario:
    return Scenario(
        name="05 - Formation flying (phasing control)",
        description=(
            DESCRIPTIONS["05"]
        ),
        epoch_utc="2030-01-01T00:00:00",
        simulation_mode="orbit_only",
        # third_body_perturbers=["sun", "moon"]: follower-1's station_keeping
        # (below, required by phasing_keeping) needs the real eclipse shadow
        # factor for its eclipse-gated reboost burn, which needs a sun
        # ephemeris -- see engine.service.SimulationService.build()'s own
        # SimulationServiceError if this is missing (caught on a real run:
        # this template originally had an empty third_body_perturbers list).
        # "moon" added alongside "sun" for full-perturbation realism (see
        # this function's own description update above).
        gravity=GravityConfig(central_body="earth", central_body_degree=10, third_body_perturbers=["sun", "moon"]),
        # duration_days=90.0 -- a real user pointed out that a short run here
        # isn't interesting: phasing_keeping's whole point is the LONG-TERM
        # along-track drift/correction cycle and its accumulated delta-V, and
        # a 24-day run (an earlier revision of this template) never drifts
        # far enough to trigger even one correction -- confirmed directly
        # against a real Basilisk run (degree-10 Earth gravity, no Sun/Moon/
        # drag): over 90 days the separation drifts to phasing_keeping's 10%
        # tolerance band around day 28, which fires one real correction that
        # brings it back in ~2.4 days, keeping it within ~45-52 km for
        # ~0.014 m/s of phasing delta-V (re-verified with the 3-day default
        # correction window; 21 days gave ~0.003 m/s over ~2 weeks) -- exactly the
        # "drift, then correct" behavior this controller exists to show, not
        # visible at 24 days.
        #
        # 90 days (not longer) is also a real platform ceiling, not just a
        # stylistic choice: Basilisk's own nanoToSec() (C++,
        # src/architecture/utilities/macroDefinitions.h) can only exactly
        # represent a nanosecond count up to 2**53 ns (~104.25 days) as a
        # double; past that it prints a stderr error on EVERY call and
        # returns NaN, poisoning all downstream time-dependent math (hit
        # directly in this audit with a 180-day test run: simulated time
        # barely progressed past the cliff at all). 90 days stays safely
        # clear of that limit with margin -- see SimSettings.validate()'s
        # own upper bound on duration_days, added for exactly this reason.
        sim_settings=SimSettings(duration_days=90.0, dynamics_task_rate_s=30.0, integrator="rkf78"),
        space_weather=_real_space_weather(),
        spacecraft=[
            SpacecraftConfig(
                name="chief-1",
                # eccentricity=0.001, not 0.0 -- both orbits used to be exactly
                # circular, which crashed on a real run: orbitalMotion.rv2elem()
                # (used by engine.orbit_maintenance.PhasingKeepingController to
                # measure each spacecraft's along-track phase) only trusts its
                # stable near-circular formula below e=1e-11, and this
                # template's own sun third-body perturbation and commanded
                # thrust are enough to push a nominally-circular orbit's real,
                # propagated eccentricity above that -- at which point rv2elem()
                # silently falls back to measuring phase from the eccentricity
                # VECTOR's direction, which is numerically meaningless (noise
                # -dominated) once eccentricity is that close to zero. A small,
                # deliberate eccentricity (0.001) keeps rv2elem() safely on its
                # normal, stable branch for SMA/e/i recovery -- but
                # PhasingKeepingController no longer uses rv2elem()'s own
                # (e, omega, f) decomposition for its phase error AT ALL (see
                # that class's own "Numerical conditioning of the phase error"
                # docstring section: it was found, by audit against a real
                # Basilisk build with real J2 active on exactly these elements,
                # to be independently singular at this same e -> 0 regime no
                # matter how small a deliberate eccentricity is chosen --
                # replaced with a numerically robust argument-of-latitude
                # computed directly from r/v).
                #
                # The "~7 km of altitude variation -- well inside
                # station_keeping's deadband once smoothed over one orbital
                # period" claim this comment used to make here was WRONG,
                # also found only once checked against a real Basilisk build
                # with real (degree >= 2) spherical-harmonics gravity active:
                # a one-orbital-period boxcar average of the RAW osculating
                # altitude at these elements converges to a STABLE ~545 km,
                # not the ~550 km target -- a genuine ~5 km secular offset
                # between the osculating semi-major axis this orbit is
                # initialized with and the true time-averaged radius under
                # real J2 (confirmed stable across 1/2/3/5/10-orbital-period
                # windows alike, so this is not averaging noise/bias from an
                # imperfect window length -- it is real), on top of which
                # J2's own short-period altitude oscillation adds further
                # swing. A 2 km deadband has no margin over either -- see
                # station_keeping's own deadband_km below, widened for
                # exactly this reason.
                orbit=OrbitIC(type="classical_elements", semi_major_axis_km=6928.0, eccentricity=0.001,
                               inclination_deg=sun_synchronous_inclination_deg(6928.0, 0.001),
                               raan_deg=raan_for_ltan_deg("2030-01-01T00:00:00"),
                               arg_periapsis_deg=0.0, true_anomaly_deg=0.0),
                dry_mass_kg=400.0,
                inertia_kg_m2=_box_inertia(400.0, _SMALLSAT_SIZE_M),
                enable_drag=True, drag_coeff=OPERATIONS_DRAG_COEFF, drag_area_m2=1.0,
                enable_srp=True, srp_coeff=1.3, srp_area_m2=1.0,
                # chief-1 needs its OWN station_keeping too -- a real
                # design bug, found from direct user feedback: a "chief"
                # that holds no altitude at all isn't a chief, it's just an
                # uncontrolled object the follower happens to be phased
                # against -- and it directly contradicts
                # engine.formation.py's own stated design for this exact
                # two-spacecraft shape ("the two-satellite 'chief holds
                # station, follower holds formation' case
                # 05_formation_flying_phasing.json demonstrates by hand" --
                # see that module's own docstring, written when this
                # template was first built but never actually implemented
                # here). Same hardware as follower-1's own station_keeping
                # below -- a realistic "sister satellite" pair, not a
                # special case.
                station_keeping=StationKeepingConfig(
                    target_altitude_km=550.0, deadband_km=15.0, thrust_n=0.05, isp_s=1500.0, propellant_kg=5.0,
                ),
            ),
            SpacecraftConfig(
                name="follower-1",
                # anomaly_type="mean", mean_anomaly_deg=0.413509 (not
                # true_anomaly_deg=-0.5) -- a real design-intent bug, found
                # from direct user feedback: the ORIGINAL -0.5 deg offset put
                # follower-1 trailing chief-1 by ~60 km while
                # phasing_keeping's target_separation_km=50.0 (below) is
                # defined as a LEADING separation (see
                # PhasingKeepingController's own docstring: always a
                # positive, "B leads A" distance) -- so the default run
                # didn't demonstrate "hold a fixed formation distance with a
                # small margin of error" at all; it demonstrated a one-time,
                # 110 km realignment maneuver that passes close by the chief
                # on the way (see duration_days's own comment below for that
                # whole investigation). phasing_keeping is a FORMATION
                # -KEEPING controller, not a rendezvous/phasing-transfer
                # planner -- its correct default demo is steady-state
                # maintenance, not a transition between two different
                # relative states.
                #
                # Fixed by placing follower-1's own initial mean anomaly
                # EXACTLY at the target separation from chief-1's (chief is
                # at true_anomaly_deg=0.0 above, which for ANY eccentricity
                # is exactly mean anomaly 0.0 too -- true and mean anomaly
                # are identically 0 at periapsis, no approximation here):
                # along_track_rad = target_separation_km * 1000 / chief_sma_m
                #                 = 50000 / 6928000 = 0.0072171 rad
                #                 = 0.413509 deg
                # -- the exact same arc-length relation both
                # engine.orbit_maintenance.SeparationSchedule and
                # engine.formation.generate_phasing_follower() already use
                # (the latter is this exact fix's own precedent: the
                # "Generate phasing formation..." GUI generator has ALWAYS
                # placed a new follower exactly at its target separation --
                # "Achieved to that exact value ... confirmed against a real
                # Basilisk run" per that function's own docstring -- this
                # template's hand-authored JSON was simply never updated to
                # match that same, already-correct design). Starting exactly
                # on target means the run now shows what phasing_keeping
                # actually does in normal operation: small, periodic
                # corrections holding the separation within
                # tolerance_fraction of target as real perturbations
                # (differential drag from follower-1's extra propellant
                # mass, J2, Sun/Moon) nudge it off -- never a large
                # transition, never passing the chief.
                orbit=OrbitIC(type="classical_elements", semi_major_axis_km=6928.0, eccentricity=0.001,
                               inclination_deg=sun_synchronous_inclination_deg(6928.0, 0.001),
                               raan_deg=raan_for_ltan_deg("2030-01-01T00:00:00"),
                               arg_periapsis_deg=0.0, anomaly_type="mean", mean_anomaly_deg=0.413509),
                dry_mass_kg=400.0,
                inertia_kg_m2=_box_inertia(400.0, _SMALLSAT_SIZE_M),
                enable_drag=True, drag_coeff=OPERATIONS_DRAG_COEFF, drag_area_m2=1.0,
                enable_srp=True, srp_coeff=1.3, srp_area_m2=1.0,
                station_keeping=StationKeepingConfig(
                    # deadband_km=15.0, not 2.0 -- widened by audit (see the
                    # orbit= comment above): this orbit's own real, natural
                    # (non-decaying) J2 + eccentricity altitude variation is
                    # already ~5-10 km, which a 2 km deadband has no margin
                    # over at all, so the smoothed altitude reads "below
                    # target" from legitimate orbital mechanics alone -- not
                    # real secular (e.g. drag) decay -- and the controller
                    # (correctly, by its own design) burns to correct it,
                    # confirmed on a real Basilisk run to fire continuously
                    # for ~7 real hours straight at deadband_km=2.0. Standard
                    # industry practice for a real deadband is to size it
                    # with margin over an orbit's own natural short-period
                    # variation, not just "as tight as the mission can
                    # tolerate" -- 15 km comfortably covers this orbit's
                    # natural swing while still catching genuine drag decay
                    # (this template's own enable_drag=True) well before it
                    # could matter.
                    target_altitude_km=550.0, deadband_km=15.0, thrust_n=0.05, isp_s=1500.0, propellant_kg=5.0,
                ),
                phasing_keeping=PhasingKeepingConfig(
                    chief_spacecraft="chief-1", target_separation_km=[50.0],
                ),
            ),
        ],
    )


def build_06_attitude_pointing_basic() -> Scenario:
    return Scenario(
        name="06 - Basic attitude pointing (idealized actuation)",
        description=(
            DESCRIPTIONS["06"]
        ),
        epoch_utc="2030-01-01T00:00:00",
        simulation_mode="full_attitude",
        # Gravity harmonics/third-body added for realism (invisible to the
        # attitude-pointing lesson below); drag/SRP deliberately NOT
        # enabled -- this template's own role is to stay the SIMPLE
        # version ('07' is explicitly "the realistic counterpart").
        gravity=GravityConfig(central_body="earth", central_body_degree=10, third_body_perturbers=["sun", "moon"]),
        # dynamics_task_rate_s=0.1 (NOT the schema's own 10.0 default, and
        # NOT this template's previous 1.0): confirmed directly against a
        # real Basilisk build that idealized-actuation mrpFeedback control
        # (engine/fsw.py's DEFAULT_MRP_GAINS, K=3.5/P=30 -- lifted from
        # Basilisk's own examples/BskSim reference, which runs its FSW task
        # at fswRate=0.1s) goes numerically unstable -- sigma_BN reaches
        # NaN within ~15 task ticks -- at 1.0s with this template's inertia
        # (then 12.5 kg*m^2), because mrpFeedback's commanded torque is a
        # zero-order hold applied for the WHOLE task period: a coarser
        # period needs a proportionally weaker P relative to inertia to stay
        # discrete-time stable (see _osculating_elements()'s own
        # SimulationServiceError message in engine/service.py, which already
        # names exactly this failure mode). 0.1s matches the reference
        # fswRate this K/P pair is tuned against and was confirmed stable
        # (no NaN) over this template's full duration. See HISTORY.md for
        # the full investigation -- this is a general risk for ANY
        # idealized-actuation spacecraft left on a coarse
        # dynamics_task_rate_s, not specific to this template.
        sim_settings=SimSettings(duration_days=0.05, dynamics_task_rate_s=0.1, integrator="rkf78"),
        spacecraft=[
            SpacecraftConfig(
                name="sat-1",
                orbit=OrbitIC(type="classical_elements", semi_major_axis_km=6928.0, eccentricity=0.0,
                               inclination_deg=sun_synchronous_inclination_deg(6928.0),
                               raan_deg=raan_for_ltan_deg("2030-01-01T00:00:00"),
                               arg_periapsis_deg=0.0, true_anomaly_deg=0.0),
                dry_mass_kg=_SMALLSAT_MASS_KG,
                inertia_kg_m2=_box_inertia(_SMALLSAT_MASS_KG, _SMALLSAT_SIZE_M),
                sigma_bn_init=[0.1, 0.2, -0.15],
                omega_bn_b_init_rad_s=[0.001, -0.001, 0.0005],
                fsw_mode="hillPoint",
            ),
        ],
    )


def build_07_attitude_pointing_with_adcs_hardware() -> Scenario:
    return Scenario(
        name="07 - Attitude pointing with real ADCS hardware",
        description=(
            DESCRIPTIONS["07"]
        ),
        epoch_utc="2030-01-01T00:00:00",
        simulation_mode="full_attitude",
        # third_body_perturbers=["sun", "moon"]: sat-1's PowerConfig (below)
        # needs the real eclipse shadow factor for its solar-panel power
        # generation, which needs a sun ephemeris -- same reasoning as '05'
        # -- and sunSafePoint's own sun-pointing already conceptually wants
        # a real sun to point at. See engine.service.SimulationService.
        # build()'s own SimulationServiceError if this is missing (caught
        # on a real run: this template originally had an empty
        # third_body_perturbers list). "moon" added alongside "sun" for
        # full-perturbation realism (see this function's own description
        # update above).
        gravity=GravityConfig(central_body="earth", central_body_degree=10, third_body_perturbers=["sun", "moon"]),
        sim_settings=SimSettings(duration_days=0.05, dynamics_task_rate_s=1.0, integrator="rkf78"),
        space_weather=_real_space_weather(),
        spacecraft=[
            SpacecraftConfig(
                name="sat-1",
                orbit=OrbitIC(type="classical_elements", semi_major_axis_km=6928.0, eccentricity=0.0,
                               inclination_deg=sun_synchronous_inclination_deg(6928.0),
                               raan_deg=raan_for_ltan_deg("2030-01-01T00:00:00"),
                               arg_periapsis_deg=0.0, true_anomaly_deg=0.0),
                dry_mass_kg=_MICROSAT_MASS_KG,
                inertia_kg_m2=_box_inertia(_MICROSAT_MASS_KG, _MICROSAT_SIZE_M),
                enable_drag=True, drag_coeff=OPERATIONS_DRAG_COEFF, drag_area_m2=1.0,
                enable_srp=True, srp_coeff=1.3, srp_area_m2=1.0,
                sigma_bn_init=[0.1, 0.2, -0.15],
                omega_bn_b_init_rad_s=[0.001, -0.001, 0.0005],
                sensors=[
                    SensorConfig(kind="star_tracker", name="st-1", params={"noise_arcsec": 5.0}),
                    SensorConfig(kind="imu", name="imu-1", params={"gyro_noise_rad_s": 1e-5}),
                    # +Z: the face sunSafePoint turns to the Sun (its default
                    # sHatBdyCmd); a +X sensor would see it edge-on, i.e. never.
                    SensorConfig(kind="coarse_sun_sensor", name="css-1", params={"nHat_B": [0.0, 0.0, 1.0]}),
                ],
                actuators=[
                    ActuatorConfig(kind="reaction_wheel", name="rw-1",
                                    params={"gsHat_B": [1.0, 0.0, 0.0], **_MICROSAT_WHEEL}),
                    ActuatorConfig(kind="reaction_wheel", name="rw-2",
                                    params={"gsHat_B": [0.0, 1.0, 0.0], **_MICROSAT_WHEEL}),
                    ActuatorConfig(kind="reaction_wheel", name="rw-3",
                                    params={"gsHat_B": [0.0, 0.0, 1.0], **_MICROSAT_WHEEL}),
                ],
                fsw_mode="sunSafePoint",
                # No control_params: the default gains are scaled to this
                # bus's inertia (engine.fsw._default_mrp_gains_for_inertia).
                # The unscaled K=3.5/P=30 (tuned for a 900 kg*m^2 spacecraft)
                # left an earlier 5 kg*m^2 version of this template in a
                # 30-degree oscillation.
                # A 12 W bus load and a battery starting at 80%: with the old
                # 0 W load and a full battery, charge sat flat at 80 Wh for
                # the whole run (confirmed in a real Basilisk run). Now it
                # charges to full in sunlight and drains ~6 Wh per eclipse.
                power=PowerConfig(panel_area_m2=0.3, panel_efficiency=0.28, battery_capacity_wh=80.0,
                                  bus_idle_power_w=12.0, battery_initial_soc=0.8),
            ),
        ],
    )


def build_08_mission_sequence_orbit_raise() -> Scenario:
    from spacemissionstudio.schema.command import Command

    return Scenario(
        name="08 - Mission sequence: impulsive orbit raise",
        description=(
            DESCRIPTIONS["08"]
        ),
        epoch_utc="2030-01-01T00:00:00",
        simulation_mode="orbit_only",
        gravity=GravityConfig(central_body="earth", central_body_degree=10, third_body_perturbers=["sun", "moon"]),
        sim_settings=SimSettings(duration_days=1.0, dynamics_task_rate_s=10.0, integrator="rkf78"),
        space_weather=_real_space_weather(),
        spacecraft=[
            SpacecraftConfig(
                name="sat-1",
                orbit=OrbitIC(type="classical_elements", semi_major_axis_km=6778.0, eccentricity=0.0,
                               inclination_deg=sun_synchronous_inclination_deg(6778.0),
                               raan_deg=raan_for_ltan_deg("2030-01-01T00:00:00"),
                               arg_periapsis_deg=0.0, true_anomaly_deg=0.0),
                dry_mass_kg=_LARGE_SMALLSAT_MASS_KG,
                inertia_kg_m2=_box_inertia(_LARGE_SMALLSAT_MASS_KG, _LARGE_SMALLSAT_SIZE_M),
                enable_drag=True, drag_coeff=OPERATIONS_DRAG_COEFF, drag_area_m2=1.0,
                enable_srp=True, srp_coeff=1.3, srp_area_m2=1.0,
            ),
        ],
        mission_sequence=[
            Command(kind="propagate", label="Coast before burn",
                    params={"stop_condition": "duration", "duration_days": 0.1}),
            Command(kind="report", label="Before burn", params={"series": []}),
            Command(kind="maneuver", label="Prograde raise burn",
                    params={"spacecraft": "sat-1", "delta_v_m_s": [50.0, 0.0, 0.0], "frame": "vnb"}),
            Command(kind="propagate", label="Coast after burn",
                    params={"stop_condition": "duration", "duration_days": 0.5}),
            Command(kind="report", label="After burn", params={"series": []}),
        ],
    )


def build_09_monte_carlo_dispersion_analysis() -> Scenario:
    return Scenario(
        name="09 - Monte Carlo dispersion analysis",
        description=(
            DESCRIPTIONS["09"]
        ),
        epoch_utc="2030-01-01T00:00:00",
        simulation_mode="orbit_only",
        gravity=GravityConfig(central_body="earth", central_body_degree=0),
        sim_settings=SimSettings(duration_days=1.0, dynamics_task_rate_s=30.0, integrator="rkf78"),
        spacecraft=[
            SpacecraftConfig(
                name="sat-1",
                orbit=OrbitIC(type="classical_elements", semi_major_axis_km=6778.0, eccentricity=0.0,
                               inclination_deg=sun_synchronous_inclination_deg(6778.0),
                               raan_deg=raan_for_ltan_deg("2030-01-01T00:00:00"),
                               arg_periapsis_deg=0.0, true_anomaly_deg=0.0),
                dry_mass_kg=_LARGE_SMALLSAT_MASS_KG,
                inertia_kg_m2=_box_inertia(_LARGE_SMALLSAT_MASS_KG, _LARGE_SMALLSAT_SIZE_M),
            ),
        ],
        monte_carlo=MonteCarloConfig(
            enabled=True, num_runs=20, thread_count=1,
            dispersions=[
                DispersionConfig(spacecraft="sat-1", quantity="dry_mass_kg", kind="normal",
                                   mean=500.0, std_deviation=25.0),
            ],
        ),
    )


def build_10_gravity_gradient_torque() -> Scenario:
    return Scenario(
        name="10 - Gravity gradient torque (uncontrolled)",
        description=(
            DESCRIPTIONS["10"]
        ),
        epoch_utc="2030-01-01T00:00:00",
        simulation_mode="full_attitude",
        # Point-mass gravity only, no third-body perturbers, no drag/SRP --
        # isolates the gravity-gradient effect from every other torque/
        # perturbation source, same "isolate the one concept" role as '01'/
        # '06'/'09'.
        gravity=GravityConfig(central_body="earth", central_body_degree=0),
        sim_settings=SimSettings(duration_days=0.5, dynamics_task_rate_s=5.0, integrator="rkf78"),
        spacecraft=[
            SpacecraftConfig(
                name="sat-1",
                orbit=OrbitIC(type="classical_elements", semi_major_axis_km=6778.0, eccentricity=0.0,
                               inclination_deg=sun_synchronous_inclination_deg(6778.0),
                               raan_deg=raan_for_ltan_deg("2030-01-01T00:00:00"),
                               arg_periapsis_deg=0.0, true_anomaly_deg=0.0),
                # An elongated 1 x 1 x 2 m bus: the spread between Izz and
                # Ixx/Iyy is what gravity gradient acts on.
                dry_mass_kg=_LARGE_SMALLSAT_MASS_KG,
                inertia_kg_m2=_box_inertia(_LARGE_SMALLSAT_MASS_KG, (1.0, 1.0, 2.0)),  # [kg*m^2] 208.3/208.3/83.3
                sigma_bn_init=[0.0, 0.0, 0.0],
                omega_bn_b_init_rad_s=[0.0, 0.0, 0.0],
                enable_gravity_gradient=True,
            ),
        ],
    )


def build_11_thruster_attitude_control() -> Scenario:
    return Scenario(
        name="11 - Attitude control via thrusters (no reaction wheels)",
        description=(
            DESCRIPTIONS["11"]
        ),
        epoch_utc="2030-01-01T00:00:00",
        simulation_mode="full_attitude",
        gravity=GravityConfig(central_body="earth", central_body_degree=0),
        sim_settings=SimSettings(duration_days=0.01, dynamics_task_rate_s=0.5, integrator="rkf78"),
        spacecraft=[
            SpacecraftConfig(
                name="sat-1",
                orbit=OrbitIC(type="classical_elements", semi_major_axis_km=6928.0, eccentricity=0.0,
                               inclination_deg=45.0, raan_deg=0.0, arg_periapsis_deg=0.0, true_anomaly_deg=0.0),
                dry_mass_kg=_SMALLSAT_MASS_KG,
                inertia_kg_m2=_box_inertia(_SMALLSAT_MASS_KG, _SMALLSAT_SIZE_M),
                sigma_bn_init=[0.3, 0.2, -0.1],
                omega_bn_b_init_rad_s=[0.0, 0.0, 0.0],
                fsw_mode="inertial3D",
                fsw_params={"sigma_R0N": [0.0, 0.0, 0.0]},
                # Default (inertia-scaled) gains. On an earlier 10 kg*m^2
                # version they asked for on-times below the thrusters' 20 ms
                # minimum, so the thrusters barely fired; on this bus they
                # do not.
                actuators=[
                    ActuatorConfig(kind="thruster", name=f"thr-{i + 1}", params=params)
                    for i, params in enumerate(_corner_thrusters((0.6, 0.6, 0.75), 1.0))  # [m], [N]
                ],
            ),
        ],
    )


def build_12_reaction_wheel_momentum_dumping() -> Scenario:
    return Scenario(
        name="12 - Reaction wheel momentum dumping",
        description=(
            DESCRIPTIONS["12"]
        ),
        epoch_utc="2030-01-01T00:00:00",
        simulation_mode="full_attitude",
        gravity=GravityConfig(central_body="earth", central_body_degree=0),
        sim_settings=SimSettings(duration_days=0.01, dynamics_task_rate_s=1.0, integrator="rkf78"),
        spacecraft=[
            SpacecraftConfig(
                name="sat-1",
                orbit=OrbitIC(type="classical_elements", semi_major_axis_km=6928.0, eccentricity=0.0,
                               inclination_deg=sun_synchronous_inclination_deg(6928.0),
                               raan_deg=raan_for_ltan_deg("2030-01-01T00:00:00"),
                               arg_periapsis_deg=0.0, true_anomaly_deg=0.0),
                dry_mass_kg=_LARGE_SMALLSAT_MASS_KG,
                inertia_kg_m2=_box_inertia(_LARGE_SMALLSAT_MASS_KG, _LARGE_SMALLSAT_SIZE_M),
                sigma_bn_init=[0.0, 0.0, 0.0],
                omega_bn_b_init_rad_s=[0.0, 0.0, 0.0],
                fsw_mode="inertial3D",
                fsw_params={"sigma_R0N": [0.0, 0.0, 0.0]},
                actuators=[
                    ActuatorConfig(kind="reaction_wheel", name="rw-1",
                                     params={"gsHat_B": [0.7071, 0.0, 0.7071], "rw_type": "Honeywell_HR12",
                                             "maxMomentum": 12.0, "Omega": 4000.0}),
                    ActuatorConfig(kind="reaction_wheel", name="rw-2",
                                     params={"gsHat_B": [0.0, 0.7071, 0.7071], "rw_type": "Honeywell_HR12",
                                             "maxMomentum": 12.0, "Omega": 2000.0}),
                    ActuatorConfig(kind="reaction_wheel", name="rw-3",
                                     params={"gsHat_B": [-0.7071, 0.0, 0.7071], "rw_type": "Honeywell_HR12",
                                             "maxMomentum": 12.0, "Omega": 3500.0}),
                    ActuatorConfig(kind="reaction_wheel", name="rw-4",
                                     params={"gsHat_B": [0.0, -0.7071, 0.7071], "rw_type": "Honeywell_HR12",
                                             "maxMomentum": 12.0, "Omega": 0.0}),
                    *[
                        ActuatorConfig(kind="thruster", name=f"desat-{i + 1}", params=params)
                        for i, params in enumerate(_corner_thrusters(
                            (0.6, 0.6, 0.8), 1.0, thruster_type="MOOG_Monarc_1"))  # [m], [N]
                    ],
                ],
                momentum_dumping=MomentumDumpingConfig(hs_max=9.6, thr_min_fire_time=0.02, max_counter_value=100),  # [N*m*s], [s]
            ),
        ],
    )


def build_13_magnetic_torque_rod_momentum_management() -> Scenario:
    return Scenario(
        name="13 - Reaction wheel momentum management via magnetic torque rods",
        description=(
            DESCRIPTIONS["13"]
        ),
        epoch_utc="2030-01-01T00:00:00",
        simulation_mode="full_attitude",
        gravity=GravityConfig(central_body="earth", central_body_degree=0),
        sim_settings=SimSettings(duration_days=120.0 / 1440.0, dynamics_task_rate_s=2.0, integrator="rkf78"),
        spacecraft=[
            SpacecraftConfig(
                name="sat-1",
                orbit=OrbitIC(type="classical_elements", semi_major_axis_km=6778.14, eccentricity=0.0,
                               inclination_deg=45.0, raan_deg=60.0, arg_periapsis_deg=0.0, true_anomaly_deg=0.0),
                dry_mass_kg=_MICROSAT_MASS_KG,
                inertia_kg_m2=_box_inertia(_MICROSAT_MASS_KG, _MICROSAT_SIZE_M),
                sigma_bn_init=[0.1, 0.2, -0.3],
                omega_bn_b_init_rad_s=[0.001, -0.01, 0.03],
                fsw_mode="inertial3D",
                fsw_params={"sigma_R0N": [0.0, 0.0, 0.0]},
                actuators=[
                    *[
                        ActuatorConfig(kind="reaction_wheel", name=f"rw-{i + 1}",
                                         params={"gsHat_B": axis, **_MICROSAT_WHEEL})
                        for i, axis in enumerate(_MTB_DEMO_RW_AXES)
                    ],
                    ActuatorConfig(kind="magnetic_torque_rod", name="mtb-1",
                                     params={"gtHat_B": [1.0, 0.0, 0.0], "max_dipole_a_m2": 15.0}),
                    ActuatorConfig(kind="magnetic_torque_rod", name="mtb-2",
                                     params={"gtHat_B": [0.0, 1.0, 0.0], "max_dipole_a_m2": 15.0}),
                    ActuatorConfig(kind="magnetic_torque_rod", name="mtb-3",
                                     params={"gtHat_B": [0.0, 0.0, 1.0], "max_dipole_a_m2": 15.0}),
                    ActuatorConfig(kind="magnetic_torque_rod", name="mtb-4",
                                     params={"gtHat_B": [0.70710678, 0.70710678, 0.0], "max_dipole_a_m2": 15.0}),
                ],
                magnetic_momentum_management=MagneticMomentumManagementConfig(
                    wheel_speed_biases_rad_s=[
                        800.0 * _RPM_TO_RAD_S, 600.0 * _RPM_TO_RAD_S, 400.0 * _RPM_TO_RAD_S, 200.0 * _RPM_TO_RAD_S,
                    ],
                    c_gain=0.003,
                ),
            ),
        ],
    )


def build_14_css_sun_heading_estimation() -> Scenario:
    return Scenario(
        name="14 - Sun-heading estimation from coarse sun sensors",
        description=(
            DESCRIPTIONS["14"]
        ),
        epoch_utc="2030-01-01T00:00:00",
        simulation_mode="full_attitude",
        # "sun" must be SPICE-tracked (third_body_perturbers) -- the CSS
        # estimation chain's sunInMsg needs the same SpicePlanetStateMsg
        # simpleNav's own truth sun direction uses (see engine.service.py's
        # SimulationServiceError guard for this exact requirement).
        gravity=GravityConfig(central_body="earth", central_body_degree=0, third_body_perturbers=["sun"]),
        # one orbit: through Earth's shadow (minutes 9.5 to 44.3) and out
        sim_settings=SimSettings(duration_days=5760.0 / 86400.0, dynamics_task_rate_s=1.0,  # [day], [s]
                                 integrator="rkf78"),
        spacecraft=[
            SpacecraftConfig(
                name="sat-1",
                orbit=OrbitIC(type="classical_elements", semi_major_axis_km=6928.0, eccentricity=0.0,
                               inclination_deg=45.0, raan_deg=0.0, arg_periapsis_deg=0.0, true_anomaly_deg=0.0),
                dry_mass_kg=_MICROSAT_MASS_KG,
                inertia_kg_m2=_box_inertia(_MICROSAT_MASS_KG, _MICROSAT_SIZE_M),
                sigma_bn_init=[0.1, 0.2, -0.15],
                omega_bn_b_init_rad_s=[0.001, -0.001, 0.0005],
                sensors=[
                    SensorConfig(kind="coarse_sun_sensor", name=f"css-{i + 1}",
                                   params={"nHat_B": nhat, "fov_deg": 160.0})
                    for i, nhat in enumerate([
                        [0.0, 0.707107, 0.707107], [0.707107, 0.0, 0.707107],
                        [0.0, -0.707107, 0.707107], [-0.707107, 0.0, 0.707107],
                        [0.0, -0.965926, -0.258819], [-0.707107, -0.353553, -0.612372],
                        [0.0, 0.258819, -0.965926], [0.707107, -0.353553, -0.612372],
                    ])
                ],
                actuators=[
                    ActuatorConfig(kind="reaction_wheel", name="rw-1",
                                     params={"gsHat_B": [1.0, 0.0, 0.0], **_MICROSAT_WHEEL}),
                    ActuatorConfig(kind="reaction_wheel", name="rw-2",
                                     params={"gsHat_B": [0.0, 1.0, 0.0], **_MICROSAT_WHEEL}),
                    ActuatorConfig(kind="reaction_wheel", name="rw-3",
                                     params={"gsHat_B": [0.0, 0.0, 1.0], **_MICROSAT_WHEEL}),
                ],
                fsw_mode="sunSafePoint",
                fsw_params={"sHatBdyCmd": [0.0, 0.0, 1.0], "use_css_estimation": True},
            ),
        ],
    )


def build_15_celestial_body_pointing() -> Scenario:
    return Scenario(
        name="15 - Direct celestial-body pointing (Moon)",
        description=(
            DESCRIPTIONS["15"]
        ),
        epoch_utc="2030-01-01T00:00:00",
        simulation_mode="full_attitude",
        gravity=GravityConfig(central_body="earth", central_body_degree=10, third_body_perturbers=["sun", "moon"]),
        # dynamics_task_rate_s=0.1: idealized (no actuator hardware)
        # mrpFeedback control with DEFAULT_MRP_GAINS needs this fine a rate
        # to stay discrete-time stable -- see '06's own comment and
        # HISTORY.md for the full investigation; confirmed directly for
        # this exact locationPointing/target_body combination in
        # tests/test_location_pointing_target_body.py.
        sim_settings=SimSettings(duration_days=0.05, dynamics_task_rate_s=0.1, integrator="rkf78"),
        spacecraft=[
            SpacecraftConfig(
                name="sat-1",
                orbit=OrbitIC(type="classical_elements", semi_major_axis_km=6928.0, eccentricity=0.0,
                               inclination_deg=sun_synchronous_inclination_deg(6928.0),
                               raan_deg=raan_for_ltan_deg("2030-01-01T00:00:00"),
                               arg_periapsis_deg=0.0, true_anomaly_deg=0.0),
                dry_mass_kg=_SMALLSAT_MASS_KG,
                inertia_kg_m2=_box_inertia(_SMALLSAT_MASS_KG, _SMALLSAT_SIZE_M),
                sigma_bn_init=[0.1, 0.2, -0.15],
                omega_bn_b_init_rad_s=[0.001, -0.001, 0.0005],
                fsw_mode="locationPointing",
                fsw_params={"target_body": "moon", "pHat_B": [0.0, 0.0, 1.0]},
            ),
        ],
    )


def build_16_lambert_transfer() -> Scenario:
    from spacemissionstudio.schema.command import Command

    r_earth_m = 6378.0e3
    # Same timing as examples/scenarioLambertSolver.py: burn a quarter
    # orbit in, arrive half an orbit in. Burning at t = 0 instead puts the
    # transfer arc below Earth's surface (~6366 km), which
    # min_orbit_radius_m rejects; the coast also gives the first report
    # something recorded to show.
    maneuver_time_s = 2490.0  # [s] a quarter of the 9952 s orbit
    time_of_flight_s = 2490.0  # [s]

    return Scenario(
        name="16 - Lambert transfer: solving for a point-to-point delta-V",
        description=(
            DESCRIPTIONS["16"]
        ),
        epoch_utc="2030-01-01T00:00:00",
        simulation_mode="orbit_only",
        gravity=GravityConfig(central_body="earth", central_body_degree=0),
        sim_settings=SimSettings(duration_days=0.2, dynamics_task_rate_s=10.0, integrator="rkf78"),
        spacecraft=[
            SpacecraftConfig(
                name="sat-1",
                orbit=OrbitIC(type="classical_elements", semi_major_axis_km=10000.0, eccentricity=0.001,
                               inclination_deg=5.0, raan_deg=10.0, arg_periapsis_deg=10.0, true_anomaly_deg=10.0),
                dry_mass_kg=330.0,
                inertia_kg_m2=_box_inertia(330.0, _SMALLSAT_SIZE_M),
            ),
        ],
        mission_sequence=[
            Command(kind="propagate", label="Coast to burn point",
                    params={"stop_condition": "duration", "duration_days": maneuver_time_s / 86400.0}),
            Command(kind="report", label="Before transfer", params={"series": []}),
            Command(kind="lambert_transfer", label="Lambert transfer burn", params={
                "spacecraft": "sat-1",
                "target_position_m": [-(r_earth_m + 200.0e3), 0.0, 0.0],
                "time_of_flight_s": time_of_flight_s,
                "max_distance_target_m": 500.0,
                "min_orbit_radius_m": r_earth_m,
            }),
            Command(kind="propagate", label="Coast to arrival",
                    params={"stop_condition": "duration", "duration_days": time_of_flight_s / 86400.0}),
            Command(kind="report", label="After transfer (should match target_position_m)", params={"series": []}),
        ],
    )


def build_17_fuel_tank_depletion() -> Scenario:
    return Scenario(
        name="17 - Real propellant depletion (fuel tank)",
        description=(
            DESCRIPTIONS["17"]
        ),
        epoch_utc="2030-01-01T00:00:00",
        simulation_mode="full_attitude",
        gravity=GravityConfig(central_body="earth", central_body_degree=0),
        sim_settings=SimSettings(duration_days=0.01, dynamics_task_rate_s=0.5, integrator="rkf78"),
        spacecraft=[
            SpacecraftConfig(
                name="sat-1",
                orbit=OrbitIC(type="classical_elements", semi_major_axis_km=6928.0, eccentricity=0.0,
                               inclination_deg=45.0, raan_deg=0.0, arg_periapsis_deg=0.0, true_anomaly_deg=0.0),
                dry_mass_kg=_SMALLSAT_MASS_KG,
                inertia_kg_m2=_box_inertia(_SMALLSAT_MASS_KG, _SMALLSAT_SIZE_M),
                sigma_bn_init=[0.3, 0.2, -0.1],
                omega_bn_b_init_rad_s=[0.0, 0.0, 0.0],
                fsw_mode="inertial3D",
                fsw_params={"sigma_R0N": [0.0, 0.0, 0.0]},
                # Default (inertia-scaled) gains. On an earlier 10 kg*m^2
                # version they asked for on-times below the thrusters' 20 ms
                # minimum, so the thrusters barely fired; on this bus they
                # do not.
                actuators=[
                    ActuatorConfig(kind="thruster", name=f"thr-{i + 1}", params=params)
                    for i, params in enumerate(_corner_thrusters((0.6, 0.6, 0.75), 1.0))  # [m], [N]
                ],
                fuel_tank=FuelTankConfig(propellant_mass_kg=0.5, max_propellant_mass_kg=1.0),
            ),
        ],
    )


def build_18_leo_station_keeping() -> Scenario:
    # Verification note (see this function's own description string
    # below for the user-facing version): this sandbox has no route to
    # CelesTrak, so the shipped nrlmsise00 atmosphere model's exact decay
    # rate couldn't be re-verified end-to-end here (same gap as '04'/'05'
    # already document). The station_keeping/drag parameters below WERE
    # tuned and confirmed against a real Basilisk build, bypassing SPICE
    # the same way tests/test_mtb_desaturation.py does, using
    # engine.orbit_maintenance.build_station_keeping() directly against a
    # bare SimulationBaseClass with a real dragDynamicEffector fed by
    # ExponentialAtmosphere -- NOT the shipped nrlmsise00 model, but
    # re-parameterized with a realistic ~400 km reference density
    # (~2.8e-12 kg/m^3, moderate solar activity) and a LEO-appropriate
    # ~60 km scale height (ExponentialAtmosphere's own built-in Earth
    # preset uses an 8.5 km scale height -- correct near the surface, but
    # it underestimates LEO density by roughly 15 orders of magnitude and
    # produces no meaningful decay at all over weeks). With that
    # realistic density, these parameters produced 2-3 real reboost burns
    # over the same 14-day window as '03' and used well under the
    # propellant_kg budget below -- the dragDynamicEffector/
    # StationKeepingController code paths themselves are the SAME
    # already-shipped, already-verified code every other enable_drag
    # template uses, only the verification harness differs.
    return Scenario(
        name="18 - LEO station-keeping",
        description=(
            DESCRIPTIONS["18"]
        ),
        epoch_utc="2030-01-01T00:00:00",
        simulation_mode="orbit_only",
        gravity=GravityConfig(central_body="earth", central_body_degree=10, third_body_perturbers=["sun", "moon"]),
        sim_settings=SimSettings(duration_days=14.0, dynamics_task_rate_s=30.0, integrator="rkf78"),
        space_weather=_real_space_weather(),
        spacecraft=[
            SpacecraftConfig(
                name="leo-sat-1",
                orbit=OrbitIC(type="classical_elements", semi_major_axis_km=6778.0, eccentricity=0.0,
                               inclination_deg=sun_synchronous_inclination_deg(6778.0),
                               raan_deg=raan_for_ltan_deg("2030-01-01T00:00:00"),
                               arg_periapsis_deg=0.0, true_anomaly_deg=0.0),
                dry_mass_kg=120.0,
                inertia_kg_m2=_box_inertia(120.0, _MICROSAT_SIZE_M),
                enable_drag=True, drag_coeff=OPERATIONS_DRAG_COEFF, drag_area_m2=1.5,
                station_keeping=StationKeepingConfig(
                    target_altitude_km=400.0, deadband_km=1.0, thrust_n=0.05, isp_s=1500.0,
                    propellant_kg=2.0,
                ),
            ),
        ],
    )


# 08:30 UTC: Berlin is near this orbit's ~09:50-local crossing, so the
# first pass comes ~10 min in (see build_19's comment).
_COMMS_EPOCH_UTC = "2030-01-01T08:30:00"


def build_19_sun_pointing_comms_link() -> Scenario:
    # Verification note (see this function's own user-facing description
    # below for the short version): this sandbox has no Basilisk build, so
    # nothing here could be run end-to-end. The ONE piece of numeric tuning
    # this template reuses -- idealized-torque mrpFeedback control on
    # dynamics_task_rate_s=0.1s with the inertia-scaled default gains --
    # is the EXACT combination '06' already confirmed stable against a real
    # Basilisk build (see build_06_attitude_pointing_basic()'s own comment);
    # comms_pointing only supports idealized actuation (see
    # engine.service's own scope note at the comms_pointing branch), so no
    # actuators are configured here, matching that constraint. What is NOT
    # independently re-confirmed here: that this same combo stays stable
    # through MUCH LARGER-angle slews (Sun-pointing <-> ground-station
    # -pointing can be up to a ~180-degree reorientation, not '06's small
    # initial offset) over a much longer run. MRP feedback's own
    # commanded-torque term is naturally bounded regardless of angle size
    # (sigma_BR's magnitude never exceeds 1, with the shadow-set switch
    # keeping it there), which is why this risk is believed low -- but
    # please report back if a real run shows otherwise.
    #
    # Ground-station pass geometry. A Sun-synchronous orbit crosses a given
    # latitude only at two fixed LOCAL times: for this 10:30-LTAN orbit,
    # Berlin (52.5 N) passes under it around 09:50 and 23:10 local solar
    # time. The old midnight-UTC epoch (00:50 in Berlin) therefore put the
    # first pass ~8.2 h into a 12 h run -- real user report: "there's never
    # ground station contact". The epoch is now 08:30 UTC (09:23 in
    # Berlin), so with true_anomaly_deg=0 the first pass starts ~10 min in
    # (sunlit, ~61 deg peak elevation) and a second, low one (~16 deg)
    # follows one orbit later, ~107 min in. Found by searching epoch and
    # starting anomaly with a J2 orbit model and the IAU_EARTH rotation
    # SPICE uses (pck00010), then checked with an RK4 J2 propagation; not
    # yet confirmed in a Basilisk run in this sandbox (no SPICE kernels).
    # tests/test_scenario_templates.py re-checks the geometry offline.
    return Scenario(
        name="19 - Sun-pointing spacecraft with automatic ground-station comms link",
        description=(
            DESCRIPTIONS["19"]
        ),
        epoch_utc=_COMMS_EPOCH_UTC,
        simulation_mode="full_attitude",
        gravity=GravityConfig(central_body="earth", central_body_degree=10, third_body_perturbers=["sun", "moon"]),
        sim_settings=SimSettings(duration_days=135.0 / 1440.0, dynamics_task_rate_s=0.1, integrator="rkf78"),
        ground_stations=[
            _berlin_ground_station(rx_antenna_gain_dbi=35.0, system_noise_temp_k=150.0),
        ],
        spacecraft=[
            SpacecraftConfig(
                name="leo-comms-1",
                orbit=OrbitIC(type="classical_elements", semi_major_axis_km=6928.0, eccentricity=0.0,
                               inclination_deg=sun_synchronous_inclination_deg(6928.0),
                               raan_deg=raan_for_ltan_deg(_COMMS_EPOCH_UTC),
                               arg_periapsis_deg=0.0, true_anomaly_deg=0.0),
                dry_mass_kg=_MICROSAT_MASS_KG,
                inertia_kg_m2=_box_inertia(_MICROSAT_MASS_KG, _MICROSAT_SIZE_M),
                sigma_bn_init=[0.2, -0.1, 0.15],
                omega_bn_b_init_rad_s=[0.001, -0.001, 0.0005],
                power=PowerConfig(
                    panel_area_m2=0.4, panel_efficiency=0.28, panel_normal_b=[0.0, 0.0, 1.0],
                    bus_idle_power_w=8.0, battery_capacity_wh=40.0, battery_initial_soc=0.9,
                ),
                rf_link=RFLinkConfig(
                    tx_power_w=5.0, frequency_hz=2.2e9, data_rate_bps=5.0e6, tx_antenna_gain_dbi=6.0,
                    required_ebno_db=10.0, antenna_beamwidth_deg=30.0,
                ),
                comms_pointing=CommsPointingConfig(
                    # A different body axis than power.panel_normal_b ([0,0,1], above) --
                    # the downlink patch antenna sits on a different face than the solar
                    # panel, so Sun-pointing and ground-station-pointing are genuinely
                    # different whole-body attitudes, not the same axis re-aimed twice.
                    target_ground_station="berlin-gs", antenna_boresight_b=[1.0, 0.0, 0.0],
                    comms_power_w=15.0,
                ),
            ),
        ],
    )


def build_20_thermal_simulation() -> Scenario:
    # Verification note (same sandbox limitation as every other template's
    # own comment): no Basilisk build exists here, so this couldn't be run
    # end-to-end in this environment. sunSafePoint control uses the same
    # bus, wheels and inertia-scaled default gains as '07';
    # the "thermal" sensor/motor-thermal physical parameters themselves
    # (area_m2/absorptivity/emissivity/mass_kg/specific_heat_j_kg_k) were
    # run for real against this project's own Basilisk venv in
    # tests/test_thermal_simulation.py (realistic values, not the
    # numerically-unstable simplification an early draft of that test
    # file briefly used -- see that test module's own comment on why a
    # tiny heat capacity explodes sensorThermal's explicit-Euler
    # integration at a 1 Hz task rate).
    return Scenario(
        name="20 - Thermal simulation: sensor heating/cooling + reaction-wheel motor heat",
        description=(
            DESCRIPTIONS["20"]
        ),
        epoch_utc="2030-01-01T00:00:00",
        simulation_mode="full_attitude",
        gravity=GravityConfig(central_body="earth", central_body_degree=10, third_body_perturbers=["sun", "moon"]),
        # duration_days=0.3 (~7.2 hours) at this orbit's ~100-minute period
        # covers roughly 4 full orbits -- several complete sunlight/eclipse
        # cycles for therm-1's temperature to visibly track, without the
        # dataset size of a much longer run.
        sim_settings=SimSettings(duration_days=0.3, dynamics_task_rate_s=1.0, integrator="rkf78"),
        spacecraft=[
            SpacecraftConfig(
                name="sat-1",
                orbit=OrbitIC(type="classical_elements", semi_major_axis_km=6928.0, eccentricity=0.0,
                               inclination_deg=sun_synchronous_inclination_deg(6928.0),
                               raan_deg=raan_for_ltan_deg("2030-01-01T00:00:00"),
                               arg_periapsis_deg=0.0, true_anomaly_deg=0.0),
                dry_mass_kg=_MICROSAT_MASS_KG,
                inertia_kg_m2=_box_inertia(_MICROSAT_MASS_KG, _MICROSAT_SIZE_M),
                sigma_bn_init=[0.1, 0.2, -0.15],
                omega_bn_b_init_rad_s=[0.001, -0.001, 0.0005],
                sensors=[
                    SensorConfig(kind="star_tracker", name="st-1", params={"noise_arcsec": 5.0}),
                    SensorConfig(kind="imu", name="imu-1", params={"gyro_noise_rad_s": 1e-5}),
                    # +Z: the face sunSafePoint turns to the Sun (its default
                    # sHatBdyCmd); a +X sensor would see it edge-on, i.e. never.
                    SensorConfig(kind="coarse_sun_sensor", name="css-1", params={"nHat_B": [0.0, 0.0, 1.0]}),
                    # A small (0.05 m^2), externally-mounted panel sharing
                    # the CSS's own sun-facing +Z normal, so it genuinely
                    # tracks this spacecraft's real sunlight/eclipse cycle.
                    # It used to face +X, which sunSafePoint holds edge-on
                    # to the Sun: zero projected area, so no solar heating
                    # at all once the attitude settled.
                    SensorConfig(kind="thermal", name="therm-1", params={
                        "nHat_B": [0.0, 0.0, 1.0], "area_m2": 0.05, "absorptivity": 0.25, "emissivity": 0.34,
                        "mass_kg": 0.3, "specific_heat_j_kg_k": 890.0, "initial_temp_c": 0.0,
                        "power_draw_w": 0.5, "measurement_noise_std_c": 0.2,
                    }),
                ],
                actuators=[
                    ActuatorConfig(kind="reaction_wheel", name="rw-1",
                                    params={"gsHat_B": [1.0, 0.0, 0.0], **_MICROSAT_WHEEL,
                                            # Optional motor-thermal model
                                            # -- see this template's own
                                            # description above for why
                                            # only this ONE wheel has it.
                                            "motor_thermal_initial_temp_c": 20.0,
                                            "motor_thermal_ambient_temp_c": 20.0,
                                            "motor_thermal_efficiency": 0.7,
                                            "motor_thermal_ambient_resistance_w_c": 5.0,
                                            "motor_thermal_heat_capacity_j_c": 50.0}),
                    ActuatorConfig(kind="reaction_wheel", name="rw-2",
                                    params={"gsHat_B": [0.0, 1.0, 0.0], **_MICROSAT_WHEEL}),
                    ActuatorConfig(kind="reaction_wheel", name="rw-3",
                                    params={"gsHat_B": [0.0, 0.0, 1.0], **_MICROSAT_WHEEL}),
                ],
                fsw_mode="sunSafePoint",
                power=PowerConfig(panel_area_m2=0.3, panel_efficiency=0.28, battery_capacity_wh=80.0),
            ),
        ],
    )


def build_21_disturbance_torques() -> Scenario:
    # Two copies of one 300 kg Sun-pointing spacecraft, flown side by side:
    # a facet model with the 2.5 m^2 array on a boom 1.5 m off to +Y, so
    # solar pressure (and drag) push off-centre. "rods-off" has only its
    # wheels, which soak up that torque all day; "rods-on" also has torque
    # rods steering its wheels back to rest. Confirmed in a real Basilisk
    # run (see tests/test_template_claims.py).
    epoch = "2030-01-01T00:00:00"
    semi_major_axis_km = 6378.0 + 450.0  # [km] low enough for drag torque to matter too

    def spacecraft(name: str, with_rods: bool) -> SpacecraftConfig:
        axes = (("x", [1.0, 0.0, 0.0]), ("y", [0.0, 1.0, 0.0]), ("z", [0.0, 0.0, 1.0]))
        actuators = [ActuatorConfig(kind="reaction_wheel", name=f"rw-{axis_name}",
                                    params={"gsHat_B": axis, "rw_type": "Honeywell_HR12", "maxMomentum": 12.0})
                     for axis_name, axis in axes]
        if with_rods:
            actuators += [ActuatorConfig(kind="magnetic_torque_rod", name=f"mtb-{axis_name}",
                                         params={"gtHat_B": axis, "max_dipole_a_m2": 30.0})  # [A*m^2]
                          for axis_name, axis in axes]
        return SpacecraftConfig(
            name=name,
            orbit=OrbitIC(type="classical_elements", semi_major_axis_km=semi_major_axis_km, eccentricity=0.0,
                          inclination_deg=sun_synchronous_inclination_deg(semi_major_axis_km),
                          raan_deg=raan_for_ltan_deg(epoch), arg_periapsis_deg=0.0, true_anomaly_deg=0.0),
            dry_mass_kg=_SMALLSAT_MASS_KG,
            inertia_kg_m2=_box_inertia(_SMALLSAT_MASS_KG, _SMALLSAT_SIZE_M),
            enable_drag=True, enable_srp=True,
            facets=box_facets(_SMALLSAT_SIZE_M, 2.5, (0.0, 0.0, 1.0), (0.0, 1.5, 0.75),  # [m], [m^2]
                              drag_coeff=OPERATIONS_DRAG_COEFF),
            sensors=[SensorConfig(kind="coarse_sun_sensor", name="css-1", params={"nHat_B": [0.0, 0.0, 1.0]})],
            actuators=actuators,
            magnetic_momentum_management=(MagneticMomentumManagementConfig(wheel_speed_biases_rad_s=[0.0] * 3)
                                          if with_rods else None),
            fsw_mode="sunSafePoint",
            fsw_params={"sHatBdyCmd": [0.0, 0.0, 1.0]},
        )

    return Scenario(
        name="21 - Disturbance torques from a facet model",
        description=DESCRIPTIONS["21"],
        epoch_utc=epoch,
        simulation_mode="full_attitude",
        gravity=GravityConfig(central_body="earth", central_body_degree=2, third_body_perturbers=["sun"]),
        sim_settings=SimSettings(duration_days=1.0, dynamics_task_rate_s=10.0, integrator="rkf78"),
        space_weather=_real_space_weather(),
        spacecraft=[spacecraft("rods-off", False), spacecraft("rods-on", True)],
    )



# -- Starter templates (22-25): starting points for your own missions -----
# 22 and 23 are meant to be copied (File > Save As) and edited into a new
# mission; 24 and 25 revisit 05 and 09 with the newer features (Basilisk's
# mean-element formation law, orbit and drag dispersions) so the pair can
# be compared directly.

# The same pass geometry as template 19 (550 km Sun-synchronous orbit,
# 10:30 LTAN, 08:30 UTC epoch): Berlin's first pass comes ~10 min in.
_STARTER_EPOCH_UTC = _COMMS_EPOCH_UTC
_STARTER_SMA_KM = 6928.0  # [km] 550 km altitude


def _starter_orbit(semi_major_axis_km: float = _STARTER_SMA_KM, epoch_utc: str = _STARTER_EPOCH_UTC) -> OrbitIC:
    """A circular Sun-synchronous orbit (10:30 LTAN) of ``semi_major_axis_km``."""
    return OrbitIC(type="classical_elements", semi_major_axis_km=semi_major_axis_km, eccentricity=0.0,
                   inclination_deg=sun_synchronous_inclination_deg(semi_major_axis_km),
                   raan_deg=raan_for_ltan_deg(epoch_utc), arg_periapsis_deg=0.0, true_anomaly_deg=0.0)


def build_22_starter_first_leo_satellite() -> Scenario:
    # The smallest scenario that is still realistic: one spacecraft, the
    # environment every LEO mission needs (degree-10 gravity, Sun and Moon,
    # drag from real space weather, solar pressure) and one ground station.
    # No attitude, so it runs in seconds; 23 adds the rest.
    return Scenario(
        name="22 - Starter: your first LEO satellite",
        description=DESCRIPTIONS["22"],
        epoch_utc=_STARTER_EPOCH_UTC,
        simulation_mode="orbit_only",
        gravity=GravityConfig(central_body="earth", central_body_degree=10, third_body_perturbers=["sun", "moon"]),
        sim_settings=SimSettings(duration_days=1.0, dynamics_task_rate_s=30.0, integrator="rkf78"),
        space_weather=_real_space_weather(),
        ground_stations=[_berlin_ground_station()],
        spacecraft=[
            SpacecraftConfig(
                name="my-sat",
                orbit=_starter_orbit(),
                dry_mass_kg=_MICROSAT_MASS_KG,
                inertia_kg_m2=_box_inertia(_MICROSAT_MASS_KG, _MICROSAT_SIZE_M),
                enable_drag=True, drag_coeff=OPERATIONS_DRAG_COEFF, drag_area_m2=0.8,  # [-], [m^2]
                enable_srp=True, srp_coeff=1.3, srp_area_m2=1.5,  # [-], [m^2]
            ),
        ],
    )


def build_23_starter_complete_small_satellite() -> Scenario:
    # The GUI's "Microsatellite (150 kg)" spacecraft preset
    # (engine.spacecraft_templates), flown as a whole mission: Sun-safe
    # pointing with star tracker, IMU, sun sensor, wheels unloaded by torque
    # rods, facets, power and a downlink, plus a Mission Sequence that stops
    # at the start and end of the first Berlin pass and reports both.
    from spacemissionstudio.engine.spacecraft_templates import SPACECRAFT_TEMPLATES
    from spacemissionstudio.schema.command import Command

    preset = next(t for t in SPACECRAFT_TEMPLATES if t.name == "Microsatellite (150 kg)")
    spacecraft = preset.build()
    spacecraft.name = "smallsat-1"
    spacecraft.orbit = _starter_orbit()
    spacecraft.sigma_bn_init = [0.1, 0.2, -0.15]  # [-] MRP, tipped away from the Sun
    spacecraft.omega_bn_b_init_rad_s = [0.001, -0.001, 0.0005]  # [rad/s]
    # Cd 3.0 on every facet (ESA AD10's operations value), like the other templates.
    spacecraft.facets = box_facets(_MICROSAT_SIZE_M, spacecraft.power.panel_area_m2,
                                   spacecraft.power.panel_normal_b, drag_coeff=OPERATIONS_DRAG_COEFF)
    spacecraft.rf_link = RFLinkConfig(tx_power_w=5.0, frequency_hz=2.2e9, data_rate_bps=5.0e6,  # [W], [Hz], [bit/s]
                                      tx_antenna_gain_dbi=6.0, required_ebno_db=10.0)  # [dBi], [dB]
    return Scenario(
        name="23 - Starter: complete small-satellite mission",
        description=DESCRIPTIONS["23"],
        epoch_utc=_STARTER_EPOCH_UTC,
        simulation_mode="full_attitude",
        gravity=GravityConfig(central_body="earth", central_body_degree=10, third_body_perturbers=["sun", "moon"]),
        sim_settings=SimSettings(duration_days=0.1, dynamics_task_rate_s=1.0, integrator="rkf78"),
        space_weather=_real_space_weather(),
        ground_stations=[_berlin_ground_station(rx_antenna_gain_dbi=35.0, system_noise_temp_k=150.0)],
        spacecraft=[spacecraft],
        mission_sequence=[
            Command(kind="propagate", label="Coast to the first Berlin pass",
                    params={"stop_condition": "event", "event_kind": "pass_start",
                            "spacecraft": "smallsat-1", "ground_station": "berlin-gs"}),
            Command(kind="report", label="Pass start", params={"series": []}),
            Command(kind="propagate", label="Fly the pass",
                    params={"stop_condition": "event", "event_kind": "pass_end",
                            "spacecraft": "smallsat-1", "ground_station": "berlin-gs"}),
            Command(kind="report", label="Pass end", params={"series": []}),
            Command(kind="propagate", label="Coast on", params={"duration_days": 0.04}),  # [day] about an hour
        ],
    )


def build_24_formation_mean_element_control() -> Scenario:
    # Template 05's formation, held by Basilisk's meanOEFeedback instead of
    # the drift-orbit controller (User Manual, "Formation control laws"):
    # same spacecraft, orbits, thruster and tank, so the two runs compare
    # directly. 14 days rather than 90: the law acts continuously, so the
    # pattern shows within a day and a run stays short.
    scenario = build_05_formation_flying_phasing()
    scenario.name = "24 - Formation flying with Basilisk's mean-element control"
    scenario.description = DESCRIPTIONS["24"]
    scenario.sim_settings.duration_days = 14.0  # [day]
    follower = next(sc for sc in scenario.spacecraft if sc.name == "follower-1")
    follower.phasing_keeping.control_law = "mean_oe"
    return scenario


def build_25_monte_carlo_orbit_and_drag_dispersions() -> Scenario:
    # Launch-injection and drag uncertainty for one 150 kg LEO satellite:
    # each run starts on a slightly different orbit (a 1-sigma of 1 km in
    # semi-major axis, 0.02 deg in inclination, 0.1 deg along track) and
    # flies with a different drag coefficient. 400 km, so three days of
    # drag already separate the runs.
    semi_major_axis_km = 6378.0 + 400.0  # [km]
    return Scenario(
        name="25 - Monte Carlo: orbit-injection and drag uncertainty",
        description=DESCRIPTIONS["25"],
        epoch_utc="2030-01-01T00:00:00",
        simulation_mode="orbit_only",
        gravity=GravityConfig(central_body="earth", central_body_degree=10, third_body_perturbers=["sun", "moon"]),
        sim_settings=SimSettings(duration_days=3.0, dynamics_task_rate_s=30.0, integrator="rkf78"),
        space_weather=_real_space_weather(),
        spacecraft=[
            SpacecraftConfig(
                name="sat-1",
                orbit=_starter_orbit(semi_major_axis_km, "2030-01-01T00:00:00"),
                dry_mass_kg=_MICROSAT_MASS_KG,
                inertia_kg_m2=_box_inertia(_MICROSAT_MASS_KG, _MICROSAT_SIZE_M),
                enable_drag=True, drag_coeff=OPERATIONS_DRAG_COEFF, drag_area_m2=0.8,  # [-], [m^2]
            ),
        ],
        monte_carlo=MonteCarloConfig(
            enabled=True, num_runs=20, thread_count=1,
            dispersions=[
                DispersionConfig(spacecraft="sat-1", quantity="orbit_elements", kind="normal",
                                 element_spread={"semi_major_axis_km": 1.0,  # [km] 1-sigma
                                                 "inclination_deg": 0.02,  # [deg]
                                                 "true_anomaly_deg": 0.1}),  # [deg]
                DispersionConfig(spacecraft="sat-1", quantity="drag_coeff", kind="uniform",
                                 bounds=[2.2, 3.0]),  # [-] AD10's end-of-life to operations values
            ],
        ),
    )


def build_37_monte_carlo_requirements_and_sensitivity() -> Scenario:
    # The Monte Carlo features of phases A and B in one small batch (Monte
    # Carlo plan B9, decision MC-34): template 25's satellite for half a day,
    # three dispersions (the orbit, the drag coefficient, the dry mass), a
    # batch seed, and two requirements with a confidence: one with an
    # allowed probability (a verdict), one without (the estimate and its
    # bound only). 30 runs: enough for the percentiles and the rank
    # correlations, about a minute in one process.
    scenario = build_25_monte_carlo_orbit_and_drag_dispersions()
    scenario.name = "37 - Monte Carlo: requirements, statistics and sensitivity"
    scenario.description = DESCRIPTIONS["37"]
    scenario.sim_settings.duration_days = 0.5  # [day]
    scenario.monte_carlo = MonteCarloConfig(
        enabled=True, num_runs=30, thread_count=1, seed=37,
        dispersions=[
            DispersionConfig(spacecraft="sat-1", quantity="orbit_elements", kind="normal",
                             element_spread={"semi_major_axis_km": 0.5,  # [km] 1-sigma
                                             "inclination_deg": 0.02,  # [deg]
                                             "true_anomaly_deg": 0.05}),  # [deg]
            DispersionConfig(spacecraft="sat-1", quantity="drag_coeff", kind="uniform",
                             bounds=[2.2, 3.0]),  # [-] AD10's end-of-life to operations values
            DispersionConfig(spacecraft="sat-1", quantity="dry_mass_kg", kind="normal",
                             mean=_MICROSAT_MASS_KG, std_deviation=7.5),  # [kg] 5 % 1-sigma
        ],
        requirements=[
            MonteCarloRequirementConfig(name="R-ALT-01", spacecraft="sat-1", outcome="lowest_altitude",
                                        at_least=389.0, confidence=0.9, max_probability=0.1),  # [km], [-], [-]
            MonteCarloRequirementConfig(name="R-DECAY-01", spacecraft="sat-1", outcome="mean_sma_change",
                                        at_least=-0.019, confidence=0.9),  # [km] at most 19 m lost, [-]
        ],
    )
    return scenario


def build_26_earth_observation_data_downlink() -> Scenario:
    # The microsatellite preset turned to nadir (hillPoint: body x up, so
    # the camera and the S-band patch antenna sit on the -x face), with a
    # camera and housekeeping filling a 3 Gbit memory that Berlin's passes
    # empty at 5 Mbit/s whenever the patch's link closes.
    from spacemissionstudio.engine.spacecraft_templates import SPACECRAFT_TEMPLATES

    preset = next(t for t in SPACECRAFT_TEMPLATES if t.name == "Microsatellite (150 kg)")
    spacecraft = preset.build()
    spacecraft.name = "eo-sat"
    spacecraft.orbit = _starter_orbit()
    spacecraft.fsw_mode = "hillPoint"
    spacecraft.fsw_params = {}
    spacecraft.sigma_bn_init = [0.1, 0.2, -0.15]  # [-] MRP
    spacecraft.omega_bn_b_init_rad_s = [0.001, -0.001, 0.0005]  # [rad/s]
    spacecraft.power.panel_normal_b = [1.0, 0.0, 0.0]  # zenith-facing array
    spacecraft.facets = box_facets(_MICROSAT_SIZE_M, spacecraft.power.panel_area_m2,
                                   spacecraft.power.panel_normal_b, drag_coeff=OPERATIONS_DRAG_COEFF)
    spacecraft.rf_link = RFLinkConfig(
        tx_power_w=2.0, frequency_hz=2.2e9, data_rate_bps=5.0e6,  # [W] RF out, [Hz], [bit/s]
        tx_antenna_gain_dbi=6.0, required_ebno_db=10.0,  # [dBi], [dB]
        antenna_pattern="cosine", antenna_front_to_back_db=15.0,  # [dB]
        antenna_boresight_b=[-1.0, 0.0, 0.0],  # nadir under hillPoint
    )
    spacecraft.data_handling = DataHandlingConfig(
        storage_capacity_gbit=3.0,  # [Gbit]
        instruments=[InstrumentConfig("camera", data_rate_bps=8.0e4, power_w=15.0),  # [bit/s] orbit average, [W]
                     InstrumentConfig("housekeeping", data_rate_bps=4.0e3)],  # [bit/s]
        transmitter_power_w=12.0,  # [W] DC while sending
    )
    return Scenario(
        name="26 - Earth observation: data and its downlink",
        description=DESCRIPTIONS["26"],
        epoch_utc=_STARTER_EPOCH_UTC,
        simulation_mode="full_attitude",
        gravity=GravityConfig(central_body="earth", central_body_degree=10, third_body_perturbers=["sun", "moon"]),
        sim_settings=SimSettings(duration_days=2.0, dynamics_task_rate_s=1.0, integrator="rkf78",
                                 record_interval_s=10.0),  # [day], [s], [s]
        space_weather=_real_space_weather(),
        ground_stations=[_berlin_ground_station(rx_antenna_gain_dbi=35.0, system_noise_temp_k=150.0)],
        spacecraft=[spacecraft],
    )


def build_27_flexible_solar_arrays() -> Scenario:
    # The 300 kg preset with its cells on two deployed wings, one on each
    # side face, each a panel on a spring-damper hinge (Basilisk's
    # hingedRigidBodyStateEffector). It starts tipped away from the Sun, so
    # the Sun-safe turn that opens the run swings the wings. The wings' mass
    # is part of the 300 kg: the hub gets the rest, and its inertia is the
    # box's for that mass.
    from spacemissionstudio.engine.spacecraft_templates import SPACECRAFT_TEMPLATES

    preset = next(t for t in SPACECRAFT_TEMPLATES if t.name == "Small satellite (300 kg)")
    spacecraft = preset.build()
    spacecraft.name = "flex-sat"
    spacecraft.orbit = _starter_orbit()
    spacecraft.sigma_bn_init = [0.1, 0.2, -0.15]  # [-] MRP, tipped away from the Sun
    spacecraft.omega_bn_b_init_rad_s = [0.0, 0.0, 0.0]  # [rad/s]
    span_m, width_m = _WING_SIZE_M
    half_y = _SMALLSAT_SIZE_M[1] / 2.0  # [m] the side faces
    spacecraft.solar_arrays = [
        SolarArrayConfig(
            name=f"wing-{number}", mass_kg=_WING_MASS_KG, span_m=span_m, width_m=width_m,
            hinge_position_b=[0.0, sign * half_y, 0.0],  # [m]
            deploy_direction_b=[0.0, sign, 0.0], normal_b=[0.0, 0.0, 1.0],  # cells on +z, the Sun-safe axis
            first_mode_hz=_WING_FIRST_MODE_HZ, damping_ratio=_WING_DAMPING_RATIO)
        for number, sign in ((1, 1.0), (2, -1.0))  # wing-1 on +y, wing-2 on -y
    ]
    hub_mass_kg = _SMALLSAT_MASS_KG - 2 * _WING_MASS_KG  # [kg]
    spacecraft.inertia_kg_m2 = _box_inertia(hub_mass_kg, _SMALLSAT_SIZE_M)
    spacecraft.power.panel_area_m2 = 0.5  # [m^2] body cells on the +z face; the wings carry the rest
    facets = box_facets(_SMALLSAT_SIZE_M, spacecraft.power.panel_area_m2, spacecraft.power.panel_normal_b,
                        drag_coeff=OPERATIONS_DRAG_COEFF)
    for number, sign in ((1, 1.0), (2, -1.0)):  # each wing, undeflected, as a front and back plate
        wing = box_facets(_SMALLSAT_SIZE_M, span_m * width_m, [0.0, 0.0, 1.0],
                          array_location_b=[0.0, sign * (half_y + span_m / 2.0), 0.0],
                          drag_coeff=OPERATIONS_DRAG_COEFF)[6:]
        for facet in wing:
            facet.name = f"wing-{number} {facet.name.split()[-1]}"
        facets.extend(wing)
    spacecraft.facets = facets
    return Scenario(
        name="27 - Flexible solar arrays",
        description=DESCRIPTIONS["27"],
        epoch_utc=_STARTER_EPOCH_UTC,
        simulation_mode="full_attitude",
        gravity=GravityConfig(central_body="earth", central_body_degree=10, third_body_perturbers=["sun", "moon"]),
        sim_settings=SimSettings(duration_days=_FLEX_DURATION_DAYS, dynamics_task_rate_s=0.5, integrator="rkf78"),
        space_weather=_real_space_weather(),
        spacecraft=[spacecraft],
    )


# Template 28's model: an octagonal bus (1.2 m across flats, 1.4 m tall),
# two deployed panels on the +/-y faces, a dish on +x, a star tracker on -x
# and the battery inside, off-centre -- that puts the center of mass a few
# centimetres from B. Masses add up to the 300 kg class [kg].
_OCTA_BUS_WIDTH_M = 1.2  # [m] across flats
_OCTA_BUS_HEIGHT_M = 1.4  # [m]
_OCTA_PANEL_SIZE_M = (1.0, 2.0, 0.03)  # [m] width (x), length (y), thickness (z)
_OCTA_PANEL_GAP_M = 0.1  # [m] from the bus face to the panel's inner edge (the yoke is not modelled)


def _octagonal_bus_model():
    """Template 28's :class:`SpacecraftModelConfig`: six parts, mass
    properties computed from them, facets from their outer faces."""
    from spacemissionstudio.schema.scenario import ModelPartConfig, SpacecraftModelConfig

    half_width = _OCTA_BUS_WIDTH_M / 2.0  # [m]
    width, length, thickness = _OCTA_PANEL_SIZE_M
    panel_y = half_width + _OCTA_PANEL_GAP_M + length / 2.0  # [m] panel centre
    common = dict(drag_coeff=OPERATIONS_DRAG_COEFF)
    panels = [
        ModelPartConfig(name=f"panel {side}", shape="panel",
                        dimensions_m={"width": width, "length": length, "thickness": thickness},
                        position_b_m=[0.0, sign * panel_y, 0.0], color=[0.15, 0.2, 0.45],
                        mass_kg=10.0, specular_coeff=0.05, diffuse_coeff=0.1, **common)  # [kg], [-], [-]
        for side, sign in (("+y", 1.0), ("-y", -1.0))
    ]
    return SpacecraftModelConfig(parts=[
        ModelPartConfig(name="bus", shape="prism", sides=8,
                        dimensions_m={"width_across_flats": _OCTA_BUS_WIDTH_M, "height": _OCTA_BUS_HEIGHT_M},
                        color=[0.85, 0.7, 0.25], mass_kg=232.0, **common),  # [kg] structure and equipment
        *panels,
        ModelPartConfig(name="dish", shape="cone", dimensions_m={"base_diameter": 0.6, "height": 0.2},  # [m]
                        position_b_m=[half_width + 0.1, 0.0, -0.3], rotation_deg=[0.0, 90.0, 0.0],  # [m], [deg]
                        color=[0.9, 0.9, 0.9], mass_kg=6.0, distribution="shell", **common),  # [kg]
        ModelPartConfig(name="star tracker", shape="box", dimensions_m={"x": 0.15, "y": 0.15, "z": 0.25},  # [m]
                        position_b_m=[-half_width - 0.075, 0.0, 0.5], color=[0.3, 0.3, 0.3],  # [m]
                        mass_kg=2.0, excluded_faces=["+x"], **common),  # [kg]; +x sits on the bus
        ModelPartConfig(name="battery", shape="box", dimensions_m={"x": 0.4, "y": 0.5, "z": 0.3},  # [m]
                        position_b_m=[0.3, 0.0, -0.45], color=[0.6, 0.2, 0.2], visible=False,  # [m]
                        mass_kg=40.0, in_surface_model=False),  # [kg] inside the bus: no outer faces
    ])


def build_28_octagonal_bus_3d_model() -> Scenario:
    # A spacecraft described by a 3D model (spacemissionstudio.model3d):
    # its mass, center of mass, inertia (with products of inertia) and
    # drag/SRP facets are all derived from the parts and written into the
    # spacecraft's own fields, and the 3D views draw the model. Sun-safe
    # pointing with wheels only (no torque rods), so the wheels keep the
    # momentum that drag and sunlight put in through the offset center of
    # mass.
    from spacemissionstudio.model3d import model as model3d

    axes = (("x", [1.0, 0.0, 0.0]), ("y", [0.0, 1.0, 0.0]), ("z", [0.0, 0.0, 1.0]))
    spacecraft = SpacecraftConfig(
        name="octa-sat",
        orbit=_starter_orbit(),
        enable_drag=True, enable_srp=True,
        sensors=[
            SensorConfig(kind="star_tracker", name="st-1", params={"noise_arcsec": 5.0}),  # [arcsec]
            SensorConfig(kind="imu", name="imu-1", params={"gyro_noise_rad_s": 1e-5}),  # [rad/s]
            SensorConfig(kind="coarse_sun_sensor", name="css-1", params={"nHat_B": [0.0, 0.0, 1.0]}),
        ],
        actuators=[ActuatorConfig(kind="reaction_wheel", name=f"rw-{axis_name}",
                                  params={"gsHat_B": axis, "rw_type": "Honeywell_HR12",
                                          "maxMomentum": 12.0})  # [N*m*s]
                   for axis_name, axis in axes],
        power=PowerConfig(panel_area_m2=4.0, panel_efficiency=0.29, panel_normal_b=[0.0, 0.0, 1.0],  # [m^2], [-]
                          bus_idle_power_w=150.0, battery_capacity_wh=700.0,  # [W], [W*h]
                          battery_initial_soc=0.9),  # [-]
        sigma_bn_init=[0.1, 0.2, -0.15],  # [-] MRP, tipped away from the Sun (as template 27)
        fsw_mode="sunSafePoint",
        fsw_params={"sHatBdyCmd": [0.0, 0.0, 1.0]},
        model=_octagonal_bus_model(),
    )
    derived = model3d.derive(spacecraft.model)
    if derived.errors:
        raise ValueError(f"template 28's model: {derived.errors}")
    model3d.apply(spacecraft, derived)
    return Scenario(
        name="28 - Octagonal bus from a 3D model",
        description=DESCRIPTIONS["28"],
        epoch_utc=_STARTER_EPOCH_UTC,
        simulation_mode="full_attitude",
        gravity=GravityConfig(central_body="earth", central_body_degree=10, third_body_perturbers=["sun", "moon"]),
        sim_settings=SimSettings(duration_days=0.2, dynamics_task_rate_s=1.0, integrator="rkf78",
                                 record_interval_s=10.0),  # [day], [s], [s]
        space_weather=_real_space_weather(),
        spacecraft=[spacecraft],
    )


def _smallsat_300_model():
    """Template 32's model: the 300 kg bus (1.2 x 1.2 x 1.5 m, the Small
    satellite (300 kg) preset's box), two deployed arrays, a star tracker
    on +y, a dish on +x and a battery inside; each part with its material,
    subsystem and maturity; the arrays folded against the bus when
    stowed; the solar cells, the antenna and a station-keeping nozzle as
    mounted equipment; an illustrative launcher envelope."""
    from spacemissionstudio.schema.scenario import (LauncherConfig, MassBudgetConfig, ModelPartConfig, MountConfig,
                                                    MountedEquipmentConfig, PartPoseConfig, SpacecraftModelConfig)

    width, length, thickness = 1.2, 1.4, 0.03  # [m] each array
    array_y = 0.6 + 0.1 + length / 2.0  # [m] 0.1 m from the bus
    common = dict(drag_coeff=OPERATIONS_DRAG_COEFF)
    arrays = [ModelPartConfig(name=f"array {side}", shape="panel",
                              dimensions_m={"width": width, "length": length, "thickness": thickness},
                              position_b_m=[0.0, sign * array_y, 0.0], color=[0.15, 0.2, 0.45], mass_kg=12.0,
                              specular_coeff=0.05, diffuse_coeff=0.1, material="cfrp", subsystem="solar_array",
                              maturity="pre_release", **common)  # [kg]
              for side, sign in (("+y", 1.0), ("-y", -1.0))]
    return SpacecraftModelConfig(
        parts=[
            ModelPartConfig(name="bus", shape="box", dimensions_m={"x": 1.2, "y": 1.2, "z": 1.5},  # [m]
                            color=[0.85, 0.7, 0.25], mass_kg=252.0, material="aluminium_6061_t6",  # [kg]
                            subsystem="structure", maturity="layout", **common),
            *arrays,
            ModelPartConfig(name="star tracker", shape="box", dimensions_m={"x": 0.15, "y": 0.15, "z": 0.25},
                            position_b_m=[0.3, 0.675, 0.45], color=[0.3, 0.3, 0.3], mass_kg=3.0,  # [m], [kg]
                            material="titanium_6al_4v", subsystem="electronics", maturity="existing",
                            excluded_faces=["-y"], **common),  # -y sits on the bus
            ModelPartConfig(name="dish", shape="cone", dimensions_m={"base_diameter": 0.6, "height": 0.2},  # [m]
                            position_b_m=[0.7, 0.0, -0.3], rotation_deg=[0.0, 90.0, 0.0], color=[0.9, 0.9, 0.9],
                            mass_kg=6.0, distribution="shell", material="aluminium", subsystem="electronics",
                            maturity="estimated", **common),  # [kg]
            ModelPartConfig(name="battery", shape="box", dimensions_m={"x": 0.4, "y": 0.4, "z": 0.25},  # [m]
                            position_b_m=[0.0, 0.0, -0.5], color=[0.6, 0.2, 0.2], visible=False, mass_kg=15.0,
                            in_surface_model=False, material="stainless_steel", subsystem="battery",
                            maturity="released"),  # [kg] inside the bus
        ],
        equipment=[
            *[MountedEquipmentConfig(f"cells {side}", "solar_cell", MountConfig(
                part=f"array {side}", position_m=[0.0, 0.0, thickness / 2.0], boresight=[0.0, 0.0, 1.0]))
              for side in ("+y", "-y")],
            MountedEquipmentConfig("antenna", "antenna", MountConfig(part="dish", position_m=[0.0, 0.0, 0.1],
                                                                     boresight=[0.0, 0.0, 1.0],
                                                                     field_of_view_deg=20.0)),  # [deg]
            MountedEquipmentConfig("sk thruster", "thruster", MountConfig(
                position_m=[-0.3, 0.6, 0.3], boresight=[0.0, -1.0, 0.0], plume_half_angle_deg=15.0),  # [m], [deg]
                thrust_n=0.05),  # [N] the station keeping's thrust
        ],
        stowed=[PartPoseConfig(f"array {side}", [0.0, sign * (0.6 + thickness / 2.0 + 0.005), 0.0],
                               [90.0, 0.0, 0.0])  # [m], [deg] folded flat against the bus's side
                for side, sign in (("+y", 1.0), ("-y", -1.0))],
        mass_budget=MassBudgetConfig(policy="aiaa_s120_2006"),
        launcher=LauncherConfig(envelope="custom", shape="cylinder", diameter_m=1.9, height_m=2.0,  # [m]
                                origin_b_m=[0.0, 0.0, -0.75],  # [m] the bus's bottom face
                                source="an illustrative envelope for this template, not a launcher's"),
    )


def build_32_smallsat_design_checks() -> Scenario:
    # The 300 kg small-satellite bus built as a 3D model with mounted
    # equipment, to show the model analyses: the star tracker's field of
    # view and the station-keeping nozzle's plume both reach the +y array
    # (the design checks find them), the disturbance torques are recorded
    # and the arrays' shading and power computed in the run.
    from spacemissionstudio.model3d import model as model3d
    from spacemissionstudio.schema.scenario import ModelAnalysesConfig, MountConfig

    tilt = math.radians(10.0)  # [rad]
    axes = (("x", [1.0, 0.0, 0.0]), ("y", [0.0, 1.0, 0.0]), ("z", [0.0, 0.0, 1.0]))
    spacecraft = SpacecraftConfig(
        name="smallsat-1",
        orbit=_starter_orbit(),
        enable_drag=True, enable_srp=True,
        sensors=[
            SensorConfig(kind="star_tracker", name="st-1", params={"noise_arcsec": 5.0},  # [arcsec]
                         # 20 deg circular field of view: the Terma T1's (NASA/TP-20250000142, Table 5-5)
                         mount=MountConfig(part="star tracker", position_m=[0.0, 0.075, 0.0],
                                           boresight=[0.0, math.cos(tilt), -math.sin(tilt)], field_of_view_deg=20.0)),
            SensorConfig(kind="imu", name="imu-1", params={"gyro_noise_rad_s": 1e-5}),  # [rad/s]
            SensorConfig(kind="coarse_sun_sensor", name="css-1", params={"nHat_B": [0.0, 0.0, 1.0]}),
        ],
        actuators=[ActuatorConfig(kind="reaction_wheel", name=f"rw-{axis_name}",
                                  params={"gsHat_B": axis, "rw_type": "Honeywell_HR12",
                                          "maxMomentum": 12.0})  # [N*m*s]
                   for axis_name, axis in axes],
        power=PowerConfig(panel_area_m2=3.36, panel_efficiency=0.29, panel_normal_b=[0.0, 0.0, 1.0],  # [m^2], [-]
                          bus_idle_power_w=150.0, battery_capacity_wh=700.0,  # [W], [W*h]
                          battery_initial_soc=0.9),  # [-]
        station_keeping=StationKeepingConfig(target_altitude_km=550.0, deadband_km=15.0, thrust_n=0.05,  # [km], [N]
                                             isp_s=1500.0, propellant_kg=10.0),  # [s], [kg]
        sigma_bn_init=[0.0, 0.0, 0.0],
        fsw_mode="sunSafePoint",
        fsw_params={"sHatBdyCmd": [0.0, 0.0, 1.0]},
        model=_smallsat_300_model(),
        model_analyses=ModelAnalysesConfig(disturbance_torques=True, array_shading=True),
    )
    derived = model3d.derive(spacecraft.model)
    if derived.errors:
        raise ValueError(f"template 32's model: {derived.errors}")
    model3d.apply(spacecraft, derived)
    return Scenario(
        name="32 - Small satellite: design checks on the 3D model",
        description=DESCRIPTIONS["32"],
        epoch_utc=_STARTER_EPOCH_UTC,
        simulation_mode="full_attitude",
        gravity=GravityConfig(central_body="earth", central_body_degree=10, third_body_perturbers=["sun", "moon"]),
        sim_settings=SimSettings(duration_days=0.07, dynamics_task_rate_s=1.0, integrator="rkf78",
                                 record_interval_s=10.0),  # [day], [s], [s]
        space_weather=_real_space_weather(),
        spacecraft=[spacecraft],
    )


def _microsat_150_model():
    """Template 33's model: the 150 kg microsatellite bus (0.8 x 0.8 x
    1.0 m, the Microsatellite (150 kg) preset's box) under MLI, two
    deployed 0.5 m^2 arrays, a radiator on the anti-Sun face, and the
    battery and the avionics inside."""
    from spacemissionstudio.schema.scenario import ModelPartConfig, SpacecraftModelConfig

    width, length, thickness = 0.7, 0.72, 0.025  # [m] each array, about 0.5 m^2
    array_y = 0.4 + 0.1 + length / 2.0  # [m] 0.1 m from the bus
    common = dict(drag_coeff=OPERATIONS_DRAG_COEFF)
    arrays = [ModelPartConfig(name=f"array {side}", shape="panel",
                              dimensions_m={"width": width, "length": length, "thickness": thickness},
                              position_b_m=[0.0, sign * array_y, 0.0], color=[0.15, 0.2, 0.45], mass_kg=4.0,
                              material="cfrp", subsystem="solar_array", **common)  # [kg]
              for side, sign in (("+y", 1.0), ("-y", -1.0))]
    return SpacecraftModelConfig(parts=[
        ModelPartConfig(name="bus", shape="box", dimensions_m={"x": 0.8, "y": 0.8, "z": 1.0},  # [m]
                        color=[0.8, 0.65, 0.2], mass_kg=120.0, material="aluminium_6061_t6",  # [kg]
                        subsystem="structure", **common),
        *arrays,
        ModelPartConfig(name="radiator", shape="panel", dimensions_m={"width": 0.4, "length": 0.4, "thickness": 0.01},
                        position_b_m=[0.0, 0.0, -0.505], color=[0.9, 0.9, 0.95], mass_kg=2.0,  # [m], [kg]
                        material="aluminium_6061_t6", subsystem="thermal", **common),
        ModelPartConfig(name="battery", shape="box", dimensions_m={"x": 0.25, "y": 0.2, "z": 0.15},  # [m]
                        position_b_m=[0.2, 0.0, -0.3], color=[0.6, 0.2, 0.2], visible=False, mass_kg=8.0,
                        in_surface_model=False, material="stainless_steel", subsystem="battery"),  # [kg]
        ModelPartConfig(name="avionics", shape="box", dimensions_m={"x": 0.3, "y": 0.3, "z": 0.2},  # [m]
                        position_b_m=[-0.15, 0.0, -0.25], color=[0.2, 0.5, 0.3], visible=False, mass_kg=10.0,
                        in_surface_model=False, material="aluminium_6061_t6", subsystem="electronics"),  # [kg]
    ])


def _microsat_150_thermal(spacecraft):
    """Template 33's thermal model: generated from the 3D model (a node
    per part, the contact conductors), then the optics, the radiator's
    standoffs, a heat pipe from the avionics to the radiator, the heat
    dissipated, two battery heaters and each node's limits."""
    from spacemissionstudio.schema.thermal import (ThermalCaseConfig, ThermalConductorConfig,
                                                   ThermalDissipationConfig, ThermalFaceConfig, ThermalHeaterConfig,
                                                   ThermalHeatPipeConfig)
    from spacemissionstudio.thermal import generate

    thermal = generate.generate(spacecraft).thermal
    limits = {"bus": ([-30.0, 50.0], [-40.0, 60.0]), "array +y": ([-100.0, 110.0], None),
              "array -y": ([-100.0, 110.0], None), "radiator": (None, None),
              "battery": ([10.0, 30.0], [-5.0, 40.0]), "avionics": ([-20.0, 50.0], [-40.0, 70.0])}  # [degC]
    for node in thermal.nodes:
        node.operating_c, node.survival_c = limits[node.name]
    thermal.faces = [
        # MLI: an aluminised Kapton outer layer over a blanket of effective emittance 0.03
        ThermalFaceConfig("bus", coating="mli_kapton_aluminised_1mil", mli_effective_emittance=0.03),
        *[entry for side in ("+y", "-y") for entry in (
            ThermalFaceConfig(f"array {side}", coating="black_paint_z306"),
            ThermalFaceConfig(f"array {side}", "+z", coating="solar_cell_triple_junction"))],
        ThermalFaceConfig("radiator", coating="silvered_teflon_5mil", radiator=True),
    ]
    # The radiator stands on low-conductance standoffs, and the battery on isolating washers: their own
    # values, not bolted contacts.
    thermal.conductors = [c for c in thermal.conductors if c.name not in ("bus--radiator", "bus--battery")]
    thermal.conductors += [ThermalConductorConfig("radiator standoffs", "bus", "radiator", "value",
                                                  conductance_w_k=0.5),  # [W/K]
                           ThermalConductorConfig("battery isolators", "bus", "battery", "value",
                                                  conductance_w_k=0.3)]  # [W/K]
    thermal.heat_pipes = [ThermalHeatPipeConfig("avionics heat pipe", "avionics", "radiator", 8.0,  # [W/K]
                                                [-40.0, 80.0], 0.01)]  # [degC], [W/K]
    thermal.dissipations = [ThermalDissipationConfig("avionics", "avionics", source="bus"),
                            ThermalDissipationConfig("battery", "battery", power_w=3.0)]  # [W]
    thermal.heaters = [ThermalHeaterConfig("battery heater A", "battery", 8.0, 12.0, 15.0),  # [W], [degC]
                       ThermalHeaterConfig("battery heater B", "battery", 8.0, 10.0, 12.0)]  # the backup, lower
    thermal.solver.time_step_s = 10.0  # [s] the arrays' eclipse exit at the run's start needs it (step check)
    # The three presets, and the cold one in safe mode: the avionics down to 15 W.
    thermal.cases = [ThermalCaseConfig("nominal", "nominal"), ThermalCaseConfig("hot", "hot"),
                     ThermalCaseConfig("cold", "cold"),
                     ThermalCaseConfig("cold safe mode", "cold", {"dissipations[avionics].source": "",
                                                                  "dissipations[avionics].power_w": 15.0})]  # [W]
    return thermal


def build_33_microsat_thermal() -> Scenario:
    # The 150 kg microsatellite preset flown Sun-safe with a 3D model and a
    # thermal model on it: nominal, hot and cold cases after the run
    # (Run > Thermal).
    from spacemissionstudio.engine.spacecraft_templates import SPACECRAFT_TEMPLATES
    from spacemissionstudio.model3d import model as model3d

    preset = next(t for t in SPACECRAFT_TEMPLATES if t.name == "Microsatellite (150 kg)")
    spacecraft = preset.build()
    spacecraft.name = "microsat-1"
    spacecraft.orbit = _starter_orbit()
    spacecraft.model = _microsat_150_model()
    derived = model3d.derive(spacecraft.model)
    if derived.errors:
        raise ValueError(f"template 33's model: {derived.errors}")
    model3d.apply(spacecraft, derived)
    spacecraft.thermal = _microsat_150_thermal(spacecraft)
    return Scenario(
        name="33 - Microsatellite: thermal model",
        description=DESCRIPTIONS["33"],
        epoch_utc=_STARTER_EPOCH_UTC,
        simulation_mode="full_attitude",
        gravity=GravityConfig(central_body="earth", central_body_degree=10, third_body_perturbers=["sun", "moon"]),
        sim_settings=SimSettings(duration_days=0.15, dynamics_task_rate_s=1.0, integrator="rkf78",
                                 record_interval_s=30.0),  # [day], [s], [s]
        space_weather=_real_space_weather(),
        spacecraft=[spacecraft],
    )


# Template 34's wings: template 33's arrays as flexible panels on hinges
# (Basilisk's hingedRigidBodyStateEffector), each about 0.5 m^2.
_MICROSAT_WING_SPAN_M = 0.72  # [m] hinge to tip
_MICROSAT_WING_WIDTH_M = 0.7  # [m] along the hinge
_MICROSAT_WING_MASS_KG = 4.0  # [kg]


def _microsat_flex_thermal(spacecraft):
    """Template 34's thermal model: template 33's, on a bus whose arrays are
    flexible wings (a node each, T-37), a 10 mil silvered-Teflon radiator,
    a conductance for each hinge, and a thermal Monte Carlo of the
    radiator's absorptance, the heat pipe and the battery's isolators."""
    from spacemissionstudio.schema.thermal import (ThermalCaseConfig, ThermalConductorConfig,
                                                   ThermalDispersionConfig, ThermalDissipationConfig,
                                                   ThermalFaceConfig, ThermalHeaterConfig, ThermalHeatPipeConfig,
                                                   ThermalMonteCarloConfig)
    from spacemissionstudio.thermal import generate

    thermal = generate.generate(spacecraft).thermal
    limits = {"bus": ([-30.0, 50.0], [-40.0, 60.0]), "radiator": (None, None),
              "battery": ([10.0, 30.0], [-5.0, 40.0]), "avionics": ([-20.0, 50.0], [-40.0, 70.0]),
              "solar array wing-1": ([-100.0, 110.0], None), "solar array wing-2": ([-100.0, 110.0], None)}  # [degC]
    for node in thermal.nodes:
        node.operating_c, node.survival_c = limits[node.name]
    thermal.faces = [
        ThermalFaceConfig("bus", coating="mli_kapton_aluminised_1mil", mli_effective_emittance=0.03),
        *[f for f in thermal.faces if f.part.startswith("solar array ")],  # cells and black paint, generated
        ThermalFaceConfig("radiator", coating="silvered_teflon_10mil", radiator=True),
    ]
    thermal.conductors = [c for c in thermal.conductors if c.name not in ("bus--radiator", "bus--battery")]
    thermal.conductors += [ThermalConductorConfig("radiator standoffs", "bus", "radiator", "value",
                                                  conductance_w_k=0.5),  # [W/K]
                           ThermalConductorConfig("battery isolators", "bus", "battery", "value",
                                                  conductance_w_k=0.3),  # [W/K]
                           *[ThermalConductorConfig(f"wing-{n} hinge", "bus", f"solar array wing-{n}", "value",
                                                    conductance_w_k=0.2) for n in (1, 2)]]  # [W/K] hinge, harness
    thermal.heat_pipes = [ThermalHeatPipeConfig("avionics heat pipe", "avionics", "radiator", 8.0,  # [W/K]
                                                [-40.0, 80.0], 0.01)]  # [degC], [W/K]
    thermal.dissipations = [ThermalDissipationConfig("avionics", "avionics", source="bus"),
                            ThermalDissipationConfig("battery", "battery", power_w=3.0)]  # [W]
    thermal.heaters = [ThermalHeaterConfig("battery heater A", "battery", 8.0, 12.0, 15.0),  # [W], [degC]
                       ThermalHeaterConfig("battery heater B", "battery", 8.0, 10.0, 12.0)]
    thermal.solver.time_step_s = 5.0  # [s] the light wings at eclipse exit need it (step check)
    thermal.cases = [ThermalCaseConfig("nominal", "nominal"), ThermalCaseConfig("hot", "hot"),
                     ThermalCaseConfig("cold", "cold")]
    # 20 runs of the hot case: the radiator's absorptance (its ageing unknown) +-25 % (1 sigma), the heat
    # pipe's conductance +-20 % (uniform), the isolators' +-30 % (1 sigma).
    thermal.monte_carlo = ThermalMonteCarloConfig(runs=20, seed=34, case="hot", dispersions=[
        ThermalDispersionConfig("faces[radiator].absorptance", 0.25, relative=True),
        ThermalDispersionConfig("heat_pipes[avionics heat pipe].conductance_w_k", 0.2, "uniform", relative=True),
        ThermalDispersionConfig("conductors[battery isolators].conductance_w_k", 0.3, relative=True)])
    return thermal


def build_34_microsat_flexible_thermal() -> Scenario:
    # Template 33's microsatellite with its arrays as flexible wings: each a
    # thermal node whose faces turn with the hinge angle the run records;
    # the Sun-safe turn that opens the run swings them. The thermal
    # section carries a Monte Carlo for Run > Thermal's studies.
    from spacemissionstudio.engine.spacecraft_templates import SPACECRAFT_TEMPLATES
    from spacemissionstudio.model3d import model as model3d
    from spacemissionstudio.schema.scenario import SpacecraftModelConfig

    preset = next(t for t in SPACECRAFT_TEMPLATES if t.name == "Microsatellite (150 kg)")
    spacecraft = preset.build()
    spacecraft.name = "microsat-2"
    spacecraft.orbit = _starter_orbit()
    spacecraft.sigma_bn_init = [0.05, 0.1, 0.0]  # [-] MRP, tipped: the Sun-safe turn swings the wings
    spacecraft.omega_bn_b_init_rad_s = [0.0, 0.0, 0.0]  # [rad/s]
    base = _microsat_150_model()
    spacecraft.model = SpacecraftModelConfig(parts=[p for p in base.parts if not p.name.startswith("array ")])
    spacecraft.solar_arrays = [
        SolarArrayConfig(name=f"wing-{number}", mass_kg=_MICROSAT_WING_MASS_KG, span_m=_MICROSAT_WING_SPAN_M,
                         width_m=_MICROSAT_WING_WIDTH_M, hinge_position_b=[0.0, sign * 0.45, 0.0],  # [m] on a yoke
                         deploy_direction_b=[0.0, sign, 0.0], normal_b=[0.0, 0.0, 1.0],  # cells on +z
                         first_mode_hz=0.8, damping_ratio=0.01, generates_power=False)  # [Hz], [-]
        for number, sign in ((1, 1.0), (2, -1.0))]
    derived = model3d.derive(spacecraft.model)
    if derived.errors:
        raise ValueError(f"template 34's model: {derived.errors}")
    model3d.apply(spacecraft, derived)
    spacecraft.thermal = _microsat_flex_thermal(spacecraft)
    return Scenario(
        name="34 - Microsatellite: flexible arrays and thermal studies",
        description=DESCRIPTIONS["34"],
        epoch_utc=_STARTER_EPOCH_UTC,
        simulation_mode="full_attitude",
        gravity=GravityConfig(central_body="earth", central_body_degree=10, third_body_perturbers=["sun", "moon"]),
        # Recorded every 0.5 s step: slower sampling would alias the wings' 0.8 Hz flexing.
        sim_settings=SimSettings(duration_days=0.15, dynamics_task_rate_s=0.5, integrator="rkf78"),  # [day], [s]
        space_weather=_real_space_weather(),
        spacecraft=[spacecraft],
    )


def build_29_roe_formation_helix() -> Scenario:
    # An ROE formation (engine.roe, engine.roe_formation): two 150 kg
    # sister satellites, the follower placed 2 km behind the chief by
    # generate_roe_follower (mean elements mapped to osculating with
    # Basilisk's J2 mapping), reconfiguring on day 1 to a passively safe
    # helix (parallel e/i vectors, 300 m) centred on the chief and holding
    # it for 3 days with the impulsive law.
    from spacemissionstudio.engine.roe_formation import generate_roe_follower

    approach_m = [0.0, -2000.0, 0.0, 0.0, 0.0, 0.0]  # [m] 2 km behind
    helix_m = [0.0, 0.0, 0.0, 300.0, 0.0, 300.0]  # [m] radial and cross-track half-sizes 300 m
    epoch_utc = "2030-01-01T00:00:00"
    chief = SpacecraftConfig(
        name="chief-1",
        orbit=OrbitIC(type="classical_elements", semi_major_axis_km=6928.0, eccentricity=0.001,  # [km], [-]
                      inclination_deg=sun_synchronous_inclination_deg(6928.0, 0.001),
                      raan_deg=raan_for_ltan_deg(epoch_utc), arg_periapsis_deg=0.0, true_anomaly_deg=0.0),
        dry_mass_kg=150.0,  # [kg]
        inertia_kg_m2=_box_inertia(150.0, _SMALLSAT_SIZE_M),
        enable_drag=True, drag_coeff=OPERATIONS_DRAG_COEFF, drag_area_m2=1.0,  # [m^2]
        enable_srp=True, srp_coeff=1.3, srp_area_m2=1.0,  # [-], [m^2]
        station_keeping=StationKeepingConfig(target_altitude_km=550.0, deadband_km=15.0, thrust_n=0.05,  # [km], [N]
                                             isp_s=1500.0, propellant_kg=5.0),  # [s], [kg]
    )
    follower = generate_roe_follower(chief, chief, "follower-1", approach_m, "impulsive")
    follower.roe_formation.targets.append(RoeTargetConfig(1.0, helix_m))  # [day]
    return Scenario(
        name="29 - ROE formation: approach and passively safe helix",
        description=DESCRIPTIONS["29"],
        epoch_utc=epoch_utc,
        simulation_mode="orbit_only",
        gravity=GravityConfig(central_body="earth", central_body_degree=10, third_body_perturbers=["sun", "moon"]),
        sim_settings=SimSettings(duration_days=4.0, dynamics_task_rate_s=30.0, integrator="rkf78",
                                 record_interval_s=60.0),  # [day], [s], [s]
        space_weather=_real_space_weather(),
        spacecraft=[chief, follower],
    )


def build_30_mars_optical_navigation() -> Scenario:
    # Optical navigation around Mars (engine.opnav, engine.optical_navigation):
    # an 18 000 km x 0.2 orbit around the Mars barycentre (DE430 has no Mars
    # itself), the Sun as a third body for the phase angle, a 40 deg 512 x
    # 512 px camera pointed perfectly (orbit only), and a filter that starts
    # 50 km and 5 m/s (1 sigma per axis) off.
    epoch_utc = "2030-01-01T00:00:00"
    return Scenario(
        name="30 - Mars orbit: optical navigation from the planet's disk",
        description=DESCRIPTIONS["30"],
        epoch_utc=epoch_utc,
        simulation_mode="orbit_only",
        gravity=GravityConfig(central_body="mars barycenter", central_body_degree=0, third_body_perturbers=["sun"]),
        sim_settings=SimSettings(duration_days=2.0, dynamics_task_rate_s=30.0, integrator="rkf78",
                                 record_interval_s=60.0),  # [day], [s], [s]
        spacecraft=[
            SpacecraftConfig(
                name="probe-1",
                orbit=OrbitIC(type="classical_elements", semi_major_axis_km=18000.0, eccentricity=0.2,  # [km], [-]
                              inclination_deg=30.0, raan_deg=0.0, arg_periapsis_deg=0.0,  # [deg]
                              true_anomaly_deg=0.0),  # [deg]
                dry_mass_kg=_SMALLSAT_MASS_KG,
                inertia_kg_m2=_box_inertia(_SMALLSAT_MASS_KG, _SMALLSAT_SIZE_M),
                optical_navigation=OpticalNavigationConfig(initial_position_sigma_m=50.0e3,  # [m]
                                                           initial_velocity_sigma_mps=5.0),  # [m/s]
            ),
        ],
    )


def build_31_eros_landmark_navigation() -> Scenario:
    # Landmark navigation around 433 Eros (engine.landmarks,
    # engine.landmark_navigation): a 35 km circular orbit polar to Eros's
    # spin axis (its pole is RA 11.35 deg, Dec 17.22 deg in pck00010: an
    # orbit normal at inclination 90 deg and RAAN 11.35 deg is perpendicular
    # to it), gravity from the NEAR shape, the Sun for the lighting, 100
    # landmarks, and a filter that starts 100 m and 5 cm/s (1 sigma per axis) off.
    return Scenario(
        name="31 - Eros orbit: landmark navigation with the shape's gravity",
        description=DESCRIPTIONS["31"],
        epoch_utc="2030-01-01T00:00:00",
        simulation_mode="orbit_only",
        gravity=GravityConfig(central_body="eros", central_body_degree=0, third_body_perturbers=["sun"],
                              polyhedral_gravity=True),
        sim_settings=SimSettings(duration_days=2.0, dynamics_task_rate_s=10.0, integrator="rkf78",
                                 record_interval_s=60.0),  # [day], [s], [s]
        spacecraft=[
            SpacecraftConfig(
                name="probe-1",
                orbit=OrbitIC(type="classical_elements", semi_major_axis_km=35.0, eccentricity=0.0,  # [km], [-]
                              inclination_deg=90.0, raan_deg=11.35, arg_periapsis_deg=0.0,  # [deg]
                              true_anomaly_deg=0.0),  # [deg]
                dry_mass_kg=_SMALLSAT_MASS_KG,
                inertia_kg_m2=_box_inertia(_SMALLSAT_MASS_KG, _SMALLSAT_SIZE_M),
                landmark_navigation=LandmarkNavigationConfig(),
            ),
        ],
    )


# Operations planning (SRS-F-30): ground stations at three latitudes. The
# coordinates are of the places named; the masks are illustrative terrain
# (mission values, not defaults).
def _station(name: str, latitude_deg: float, longitude_deg: float, altitude_m: float,
             min_elevation_deg: float) -> GroundStationConfig:
    return _berlin_ground_station(name=name, latitude_deg=latitude_deg, longitude_deg=longitude_deg,
                                  altitude_m=altitude_m, min_elevation_deg=min_elevation_deg,
                                  rx_antenna_gain_dbi=35.0, system_noise_temp_k=150.0)


_OPS_STATIONS = (  # name, latitude [deg], longitude [deg], altitude [m], lowest elevation [deg]
    ("svalbard-gs", 78.23, 15.41, 480.0, 5.0),  # Platåberget above Longyearbyen
    ("berlin-gs", 52.52, 13.405, 34.0, 10.0),  # the templates' Berlin station
    ("santiago-gs", -33.45, -70.66, 570.0, 10.0),  # Santiago de Chile
)
_OPS_STATION_PLANNING = {  # azimuth masks [[azimuth deg, lowest elevation deg], ...] and setup [s]
    "svalbard-gs": {"azimuth_mask": [[0.0, 5.0], [90.0, 8.0], [200.0, 12.0], [300.0, 5.0]], "setup_s": 120.0},
    "berlin-gs": {"setup_s": 120.0},
    "santiago-gs": {"azimuth_mask": [[0.0, 10.0], [45.0, 20.0], [135.0, 10.0]], "setup_s": 120.0},
}
_OPS_TARGETS = (  # name, latitude [deg], longitude [deg], priority (1 highest), acquisitions wanted
    ("rotterdam-port", 51.95, 4.14, 1, 2), ("rhine-delta", 51.85, 4.60, 2, 1), ("alps-glacier", 46.50, 8.00, 1, 2),
    ("po-valley", 45.10, 10.00, 2, 1), ("danube-delta", 45.20, 29.50, 2, 1), ("lisbon", 38.72, -9.14, 3, 1),
    ("madrid", 40.42, -3.70, 3, 1), ("etna", 37.75, 14.99, 1, 1), ("nile-delta", 31.00, 31.00, 2, 1),
    ("lake-chad", 13.30, 14.10, 3, 1), ("kilimanjaro", -3.07, 37.35, 3, 1), ("amazon-manaus", -3.10, -60.00, 2, 1),
    ("atacama", -24.50, -69.25, 2, 1), ("patagonia-icefield", -49.00, -73.30, 1, 1),
    ("iceland-vatnajokull", 64.40, -16.80, 2, 1), ("greenland-jakobshavn", 69.20, -49.80, 1, 2),
    ("aral-sea", 45.00, 59.50, 3, 1), ("ganges-delta", 22.00, 89.00, 3, 1), ("tokyo-bay", 35.50, 139.80, 3, 1),
    ("mississippi-delta", 29.20, -89.30, 2, 1),
)
_OPS_EPOCH_UTC = "2030-06-03T08:30:00"  # northern summer: the high-latitude targets are lit


def _ops_activity_types() -> list[dict]:
    """The camera's image, the S-band downlink and a star-tracker
    calibration; the camera and the patch antenna sit on the -x face."""
    return [
        {"name": "image", "kind": "acquisition", "pointing": "target", "duration_s": 20.0, "setup_s": 15.0,
         "boresight_b": [-1.0, 0.0, 0.0], "instruments": ["camera"]},
        {"name": "downlink", "kind": "contact", "pointing": "station", "min_duration_s": 180.0, "setup_s": 30.0,
         "boresight_b": [-1.0, 0.0, 0.0], "transmitter": True},
        {"name": "star cal", "kind": "calibration", "pointing": "inertial", "duration_s": 600.0,
         "sigma_rn": [0.0, 0.0, 0.0]},
    ]


def _ops_spacecraft(name: str, raan_offset_deg: float = 0.0):
    """Template 26's microsatellite as an imager flown by a plan: a camera
    that sends 40 Mbit/s while it images (25 W), a 3 Gbit memory, stiffer
    attitude gains so a 30 deg slew settles in about half a minute."""
    spacecraft = build_26_earth_observation_data_downlink().spacecraft[0]
    spacecraft.name = name
    spacecraft.comms_pointing = None  # the plan points the spacecraft
    spacecraft.orbit.raan_deg = (spacecraft.orbit.raan_deg + raan_offset_deg) % 360.0  # [deg]
    spacecraft.control_params = {"K": 1.0, "P": 8.0}  # [N*m], [N*m*s] an agile imager
    camera = spacecraft.data_handling.instruments[0]
    camera.data_rate_bps, camera.power_w = 40.0e6, 25.0  # [bit/s] while imaging, [W]
    return spacecraft


def _with_operations(scenario: Scenario, section: dict) -> Scenario:
    data = scenario.to_dict()
    data["operations"] = section
    return Scenario.from_dict(data)


def build_35_eo_operations_week() -> Scenario:
    # A week of operations for the 150 kg imager: twenty targets around the
    # world, three stations at 78 N, 52 N and 33 S, a daily star-tracker
    # calibration, and a ground segment that books 40 min of contacts a
    # day. The tension: the camera fills the 3 Gbit memory faster than the
    # booked contacts empty it, and the passes over Europe compete with
    # the European targets.
    scenario = Scenario(
        name="35 - Operations: a week of an Earth observation microsatellite",
        description=DESCRIPTIONS["35"],
        epoch_utc=_OPS_EPOCH_UTC,
        simulation_mode="full_attitude",
        gravity=GravityConfig(central_body="earth", central_body_degree=10, third_body_perturbers=["sun", "moon"]),
        sim_settings=SimSettings(duration_days=7.0, dynamics_task_rate_s=1.0, integrator="rkf78",
                                 record_interval_s=10.0),  # [day], [s], [s]
        space_weather=_real_space_weather(),
        ground_stations=[_station(*item) for item in _OPS_STATIONS],
        spacecraft=[_ops_spacecraft("eo-micro")],
    )
    section = {
        "version": 1,
        "horizon": {"start_utc": "2030-06-03T08:30:00Z", "end_utc": "2030-06-10T08:30:00Z"},
        "geometry": {"source": "propagation", "step_s": 30.0},
        "targets": [{"name": name, "priority": priority, "activity": "image", "max_off_nadir_deg": 30.0,
                     "latitude_deg": lat, "longitude_deg": lon, "sun_elevation_deg": [15.0, 90.0],
                     "acquisitions": wanted} for name, lat, lon, priority, wanted in _OPS_TARGETS],
        "activity_types": _ops_activity_types(),
        "requests": [{"name": "daily-cal", "activity": "star cal", "spacecraft": "eo-micro", "priority": 2,
                      "count": 1, "per": "day"}],
        "stations": [{"station": name, **_OPS_STATION_PLANNING[name]} for name, *_rest in _OPS_STATIONS],
        "spacecraft": [{"spacecraft": "eo-micro", "contact_activity": "downlink", "min_soc": 0.4,
                        "max_activities_per_orbit": 4, "max_contact_s_per_day": 2400.0}],
        "scheduler": {"seed": 1, "improvement_iterations": 20},
    }
    return _with_operations(scenario, section)


def build_36_constellation_operations() -> Scenario:
    # Three of template 35's imagers in Sun-synchronous planes 30 deg of
    # RAAN apart (2 h of local time), each at the same point of its orbit:
    # they reach the pole together, so the two stations, which serve one
    # spacecraft at a time, are contested on most passes, while their
    # ground tracks differ. Any of them may take a target. The plan says
    # who gets each pass, and why.
    scenario = Scenario(
        name="36 - Operations: three imagers sharing two stations",
        description=DESCRIPTIONS["36"],
        epoch_utc=_OPS_EPOCH_UTC,
        simulation_mode="full_attitude",
        gravity=GravityConfig(central_body="earth", central_body_degree=10, third_body_perturbers=["sun", "moon"]),
        sim_settings=SimSettings(duration_days=2.0, dynamics_task_rate_s=1.0, integrator="rkf78",
                                 record_interval_s=10.0),  # [day], [s], [s]
        space_weather=_real_space_weather(),
        ground_stations=[_station(*item) for item in _OPS_STATIONS[:2]],
        spacecraft=[_ops_spacecraft(f"eo-{letter}", offset)
                    for letter, offset in (("a", 0.0), ("b", 30.0), ("c", 60.0))],
    )
    names = [sc.name for sc in scenario.spacecraft]
    section = {
        "version": 1,
        "horizon": {"start_utc": "2030-06-03T08:30:00Z", "end_utc": "2030-06-05T08:30:00Z"},
        "geometry": {"source": "propagation", "step_s": 30.0},
        "targets": [{"name": name, "priority": priority, "activity": "image", "max_off_nadir_deg": 30.0,
                     "latitude_deg": lat, "longitude_deg": lon, "sun_elevation_deg": [15.0, 90.0],
                     "acquisitions": wanted} for name, lat, lon, priority, wanted in _OPS_TARGETS[:10]],
        "activity_types": _ops_activity_types(),
        "stations": [{"station": name, **_OPS_STATION_PLANNING[name]} for name, *_rest in _OPS_STATIONS[:2]],
        "spacecraft": [{"spacecraft": name, "contact_activity": "downlink", "min_soc": 0.4,
                        "max_activities_per_orbit": 4, "max_contact_s_per_day": 2400.0} for name in names],
        "scheduler": {"seed": 1, "improvement_iterations": 10},
    }
    return _with_operations(scenario, section)


# -- Template 38: the Budgets area (decisions TB-1 to TB-8) -----------------
# Every number of the budgets section is an example: none comes from a data
# sheet, a standard or another tool. Each says so in its source, with the
# words of the budgets test data (tests/data/budgets). The mass growth
# allowances are not entered: the mass budget takes them from AIAA
# S-120-2006 (config.materials).
_T38_SOURCE = "Synthetic example value; not from a data sheet or a standard."
_T38_SIZE_M = (0.8, 0.8, 1.0)  # [m] the bus box, the Microsatellite (150 kg) preset's
# name: (subsystem, S-120 column, maturity, mass [kg], bus, power modes, model part)
# power modes: (name, average [W], peak [W] or None, duty cycle [-])
# model part: (shape, dimensions [m], position [m], visible, material); None: the two array parts
_T38_EQUIPMENT = {
    "structure": ("structure", "structure", "layout", 40.0, "", (),
                  ("box", {"x": 0.8, "y": 0.8, "z": 1.0}, [0.0, 0.0, 0.0], True, "aluminium_6061_t6")),
    "solar arrays": ("power", "solar_array", "pre_release", 12.0, "", (), None),  # the two array parts
    "battery": ("power", "battery", "existing", 10.0, "", (),
                ("box", {"x": 0.3, "y": 0.2, "z": 0.2}, [0.15, 0.15, -0.3], False, "stainless_steel")),
    "PCDU": ("power", "electronics", "released", 4.0, "platform", (("on", 9.0, 12.0, 1.0),),
             ("box", {"x": 0.25, "y": 0.2, "z": 0.1}, [-0.15, 0.15, -0.3], False, "aluminium")),
    "OBC": ("OBC", "electronics", "existing", 2.0, "platform", (("on", 7.0, 9.0, 1.0),),
            ("box", {"x": 0.2, "y": 0.15, "z": 0.08}, [-0.15, -0.15, -0.3], False, "aluminium")),
    "reaction wheels": ("ADCS", "mechanisms", "existing", 7.2, "platform",
                        (("idle", 6.0, 8.0, 1.0), ("slewing", 14.0, 36.0, 1.0)),
                        ("box", {"x": 0.3, "y": 0.3, "z": 0.15}, [0.0, 0.0, 0.15], False, "aluminium")),
    "star tracker": ("ADCS", "electronics", "existing", 1.0, "platform", (("off", 0.0, None, 1.0),
                                                                        ("on", 2.5, 3.5, 1.0)),
                     ("box", {"x": 0.15, "y": 0.1, "z": 0.1}, [-0.475, 0.2, 0.3], True, "titanium_6al_4v")),
    "S-band transceiver": ("comms", "electronics", "released", 1.6, "platform",
                           (("receive", 4.0, 5.0, 1.0), ("transmit", 18.0, 22.0, 1.0)),
                           ("box", {"x": 0.15, "y": 0.1, "z": 0.05}, [0.15, -0.15, -0.3], False, "aluminium")),
    "camera": ("payload", "instrumentation", "estimated", 18.0, "payload",
               (("off", 0.0, None, 1.0), ("standby", 6.0, 7.0, 1.0), ("imaging", 42.0, 50.0, 1.0)),
               ("box", {"x": 0.25, "y": 0.25, "z": 0.35}, [0.0, 0.0, 0.675], True, "aluminium")),
    # Thermostats switch the heaters: the duty cycle is the share of the time they are on.
    "heaters": ("thermal", "thermal", "estimated", 1.5, "platform",
                (("survival", 20.0, None, 0.6), ("operational", 20.0, None, 0.3)),
                ("box", {"x": 0.3, "y": 0.2, "z": 0.01}, [0.15, 0.15, -0.195], False, "kapton_h")),  # on the battery
    "harness": ("harness", "wire_harness", "estimated", 6.5, "", (),
                ("box", {"x": 0.7, "y": 0.7, "z": 0.02}, [0.0, 0.0, 0.45], False, "copper")),  # its mass, spread
    "propulsion module": ("propulsion", "propulsion", "pre_release", 6.5, "platform",
                          (("off", 0.0, None, 1.0), ("standby", 3.0, 4.0, 1.0)),
                          ("box", {"x": 0.3, "y": 0.3, "z": 0.25}, [0.0, 0.0, -0.1], False, "titanium_6al_4v")),
}
# system mode: (duty cycle [-], {item: its power mode}); the duty cycles add up to 1
_T38_MODES = {
    "safe": (0.05, {"PCDU": "on", "OBC": "on", "reaction wheels": "idle", "star tracker": "off",
                    "S-band transceiver": "receive", "camera": "off", "heaters": "survival",
                    "propulsion module": "off"}),
    "nominal": (0.65, {"PCDU": "on", "OBC": "on", "reaction wheels": "idle", "star tracker": "on",
                       "S-band transceiver": "receive", "camera": "standby", "heaters": "operational",
                       "propulsion module": "standby"}),
    "imaging": (0.2, {"PCDU": "on", "OBC": "on", "reaction wheels": "slewing", "star tracker": "on",
                      "S-band transceiver": "receive", "camera": "imaging", "heaters": "operational",
                      "propulsion module": "standby"}),
    "downlink": (0.1, {"PCDU": "on", "OBC": "on", "reaction wheels": "slewing", "star tracker": "on",
                       "S-band transceiver": "transmit", "camera": "standby", "heaters": "operational",
                       "propulsion module": "standby"}),
}
# The pointing example: the camera looks along +z. requirement: (index, kind, axis, limit [arcsec],
# probability [-], window [s] or None, stability [s] or None, system modes)
_T38_POINTING_REQUIREMENTS = {
    "APE line of sight": ("absolute", "performance", "line_of_sight", 60.0, 0.95, None, None, ["imaging"]),
    "RPE x": ("relative", "performance", "x", 15.0, 0.95, 60.0, 1.0, ["imaging"]),
    "AKE x": ("absolute", "knowledge", "x", 15.0, 0.95, None, None, ["imaging", "downlink"]),
}
# contributor: (kind, behaviour, distribution, spread per axis [arcsec], period [s] or None, equipment item)
_T38_POINTING_CONTRIBUTORS = {
    "star tracker noise": ("both", "random", "gaussian", {"x": 2.0, "y": 2.0, "z": 15.0}, None, "star tracker"),
    "camera alignment": ("performance", "bias", "uniform", {"x": 10.0, "y": 10.0}, None, "camera"),
    "attitude control error": ("performance", "random", "gaussian", {"x": 6.0, "y": 6.0, "z": 8.0}, None, ""),
    "wheel jitter": ("performance", "random", "gaussian", {"x": 0.5, "y": 0.5, "z": 0.5}, None,
                     "reaction wheels"),
    "thermal distortion": ("performance", "periodic", "sinusoidal", {"x": 4.0, "y": 4.0}, 5700.0, "structure"),
}
_T38_BUSES = {"platform": 0.92, "payload": 0.88}  # [-] converter efficiency
_T38_POWER_MARGINS = {"estimated": 25.0, "layout": 20.0, "pre_release": 15.0, "released": 8.0,
                      "existing": 4.0, "measured": 2.0}  # [%] per maturity category


def _t38_budgets():
    """Template 38's budgets section: the equipment list, the system modes,
    the numbers of the power budget and a small pointing error budget, each
    number with its source."""
    from spacemissionstudio.schema.budgets import (BudgetBusConfig, BudgetEquipmentConfig, BudgetModeConfig,
                                                   BudgetPowerModeConfig, BudgetsConfig, PointingConfig,
                                                   PointingContributorConfig, PointingRequirementConfig,
                                                   PowerMarginConfig, SourcedValue)

    def sourced(value):
        return SourcedValue(value, _T38_SOURCE)

    equipment = []
    for name, (subsystem, column, maturity, mass, bus, modes, _part) in _T38_EQUIPMENT.items():
        equipment.append(BudgetEquipmentConfig(
            name=name, subsystem=subsystem, mass_column=column, bus=bus, maturity=maturity,
            mass_kg=sourced(mass), mass_in_model=True,
            power_modes=[BudgetPowerModeConfig(mode, sourced(average), None if peak is None else sourced(peak),
                                               duty)
                         for mode, average, peak, duty in modes]))
    return BudgetsConfig(
        buses=[BudgetBusConfig(name, sourced(efficiency)) for name, efficiency in _T38_BUSES.items()],
        distribution_loss=sourced(0.02),  # [-]
        power_margins=[PowerMarginConfig(maturity, sourced(percent))
                       for maturity, percent in _T38_POWER_MARGINS.items()],
        system_power_margin_percent=sourced(12.0),  # [%]
        equipment=equipment,
        modes=[BudgetModeConfig(name, duty, dict(units)) for name, (duty, units) in _T38_MODES.items()],
        pointing=PointingConfig(
            line_of_sight="z",
            requirements=[PointingRequirementConfig(
                name, sourced(limit), sourced(probability), index=index, kind=kind, axis=axis,
                window_s=None if window is None else sourced(window),
                stability_s=None if stability is None else sourced(stability), modes=list(modes))
                for name, (index, kind, axis, limit, probability, window, stability, modes)
                in _T38_POINTING_REQUIREMENTS.items()],
            contributors=[PointingContributorConfig(
                name, kind=kind, behaviour=behaviour, distribution=distribution,
                spread_arcsec={axis: sourced(value) for axis, value in spread.items()},
                period_s=None if period is None else sourced(period), equipment=equipment)
                for name, (kind, behaviour, distribution, spread, period, equipment)
                in _T38_POINTING_CONTRIBUTORS.items()],
        ),
    )


def _t38_model():
    """Template 38's 3D model: the bus structure, two deployed arrays, the
    camera and the star tracker outside, and the other items of the
    equipment list inside (hidden), each with the mass, S-120 column and
    maturity of its equipment-list item, so the model holds every item and
    the run flies the whole dry mass; the arrays folded against the bus
    when stowed; an illustrative launcher envelope and mass limit."""
    from spacemissionstudio.schema.scenario import (LauncherConfig, MassBudgetConfig, ModelPartConfig,
                                                    PartPoseConfig, SpacecraftModelConfig)

    common = dict(drag_coeff=OPERATIONS_DRAG_COEFF)
    parts = []
    for name, (_subsystem, column, maturity, mass, _bus, _modes, part) in _T38_EQUIPMENT.items():
        if part is None:
            continue
        shape, dimensions, position, visible, material = part
        extra = common if visible else dict(in_surface_model=False)
        if name == "star tracker":
            extra = dict(common, excluded_faces=["+x"])  # +x sits on the bus
        parts.append(ModelPartConfig(name=name, shape=shape, dimensions_m=dimensions, position_b_m=position,
                                     color=[0.85, 0.7, 0.25] if name == "structure" else [0.3, 0.3, 0.3],
                                     visible=visible, mass_kg=mass, material=material, subsystem=column,
                                     maturity=maturity, **extra))
    width, length, thickness = 0.8, 0.9, 0.025  # [m] each array
    array_y = _T38_SIZE_M[1] / 2.0 + 0.05 + length / 2.0  # [m] 5 cm from the bus
    _subsystem, column, maturity, arrays_mass, *_rest = _T38_EQUIPMENT["solar arrays"]
    parts += [ModelPartConfig(name=f"array {side}", shape="panel",
                              dimensions_m={"width": width, "length": length, "thickness": thickness},
                              position_b_m=[0.0, sign * array_y, 0.0], color=[0.15, 0.2, 0.45],
                              mass_kg=arrays_mass / 2.0, specular_coeff=0.05, diffuse_coeff=0.1, material="cfrp",
                              subsystem=column, maturity=maturity, **common)  # [kg]
              for side, sign in (("+y", 1.0), ("-y", -1.0))]
    return SpacecraftModelConfig(
        parts=parts,
        stowed=[PartPoseConfig(f"array {side}", [0.0, sign * (_T38_SIZE_M[1] / 2.0 + thickness / 2.0 + 0.005), 0.0],
                               [90.0, 0.0, 0.0])  # [m], [deg] folded flat against the bus's side
                for side, sign in (("+y", 1.0), ("-y", -1.0))],
        mass_budget=MassBudgetConfig(policy="aiaa_s120_2006", mass_limit_kg=150.0,  # [kg]
                                     limit_source="an illustrative limit for this template, not a launcher's"),
        launcher=LauncherConfig(envelope="custom", shape="cylinder", diameter_m=1.3, height_m=1.5,  # [m]
                                origin_b_m=[0.0, 0.0, -_T38_SIZE_M[2] / 2.0],  # [m] the bus's bottom face
                                source="an illustrative envelope for this template, not a launcher's"),
    )


def build_38_budgets_equipment_power_mass_propellant() -> Scenario:
    # The Budgets area on one small LEO imager (decisions TB-1 to TB-8): template
    # 22's orbit, environment and ground station; an equipment list of 12
    # items with four system modes whose duty cycles add up to 1; a 3D
    # model that holds every item, with the S-120 mass budget and a
    # launcher envelope; and a propellant budget with a tank and a specific
    # impulse. Orbit only, so a day runs in seconds. A station keeper with
    # a 15 km deadband (as template 32) gives the propellant budget its
    # orbit control from the drag without a run; it does not fire in a day.
    # The station keeper's and the propellant budget's numbers are examples
    # too (these fields have no source; decision TB-5).
    from spacemissionstudio.model3d import model as model3d
    from spacemissionstudio.schema.scenario import PropellantBudgetConfig

    spacecraft = SpacecraftConfig(
        name="eo-sat",
        orbit=_starter_orbit(),
        enable_drag=True, drag_coeff=OPERATIONS_DRAG_COEFF, drag_area_m2=0.8,  # [-], [m^2]
        enable_srp=True, srp_coeff=1.3, srp_area_m2=1.5,  # [-], [m^2]
        station_keeping=StationKeepingConfig(target_altitude_km=550.0, deadband_km=15.0, thrust_n=1.0,  # [km], [N]
                                             isp_s=220.0, propellant_kg=6.0),  # [s], [kg]
        propellant_budget=PropellantBudgetConfig(mission_years=5.0,  # [year]
                                                 tank_capacity_kg=8.0, isp_s=220.0,  # [kg], [s]
                                                 injection_sma_error_km=10.0,  # [km]
                                                 injection_inclination_error_deg=0.05,  # [deg]
                                                 collision_avoidance_count=3.0),  # [-]
        model=_t38_model(),
    )
    spacecraft.budgets = _t38_budgets()
    derived = model3d.derive(spacecraft.model)
    if derived.errors:
        raise ValueError(f"template 38's model: {derived.errors}")
    model3d.apply(spacecraft, derived, orbit_only=True)
    return Scenario(
        name="38 - Budgets: equipment list, power, mass and propellant",
        description=DESCRIPTIONS["38"],
        epoch_utc=_STARTER_EPOCH_UTC,
        simulation_mode="orbit_only",
        gravity=GravityConfig(central_body="earth", central_body_degree=10, third_body_perturbers=["sun", "moon"]),
        sim_settings=SimSettings(duration_days=1.0, dynamics_task_rate_s=30.0, integrator="rkf78"),
        space_weather=_real_space_weather(),
        ground_stations=[_berlin_ground_station()],
        spacecraft=[spacecraft],
    )


# -- Templates for every feature, batch A (39-42) -----------------------------
# Each shows a feature no earlier template uses: the TLE and Cartesian orbit
# inputs (39), continuous low thrust (40), velocity pointing with a
# magnetometer and navigation errors (41), and the tabular atmosphere with
# the lifetime estimate (42). Decisions TPL-A1 to TPL-A4 record the sources.


def _tle_line(body: str) -> str:
    """A TLE line: its 68 columns and the modulo-10 checksum the format
    puts in column 69 (digits count as their value, a minus sign as 1)."""
    assert len(body) == 68, (len(body), body)
    return body + str(sum(int(c) if c.isdigit() else 1 if c == "-" else 0 for c in body) % 10)


# A SYNTHETIC TLE (not a real satellite): catalogue number 99999 (the
# analysts' number), no international designator, epoch the template's
# epoch (2030 day 1.35416667 = 08:30 UTC), no drag terms (B* 0: the run
# models drag from its own settings, never from the TLE), and mean elements
# chosen for a 51.64 deg orbit of about 420 km: e 0.0004, 15.5 revolutions
# a day. Built field by field in the TLE column layout.
_SYNTHETIC_TLE = (
    _tle_line("1 99999U          30001.35416667  .00000000  00000-0  00000-0 0    1"),
    _tle_line("2 99999  51.6400 120.0000 0004000  90.0000 270.0000 15.50000000    1"),
)

# An ILLUSTRATIVE state vector: the perigee of a 500 x 1500 km orbit
# inclined 63.4 deg, its node and perigee on the J2000 x axis. Position
# [r_p, 0, 0]; speed from the vis-viva equation, v_p = sqrt(mu (2/r_p -
# 1/a)), with Basilisk's Earth (spacemissionstudio.constants), turned by
# the inclination about x. Rounded to 1 m and 1 mm/s.
_STATE_PERIGEE_KM = 500.0  # [km] altitude above the equatorial radius
_STATE_APOGEE_KM = 1500.0  # [km]
_STATE_INCLINATION_DEG = 63.4  # [deg]


def _illustrative_state_vector() -> tuple[list, list]:
    from spacemissionstudio import constants

    radius_km = constants.EARTH_EQUATORIAL_RADIUS_M / 1000.0  # [km]
    mu_km3_s2 = constants.EARTH_GM_M3_S2 / 1e9  # [km^3/s^2]
    r_p = radius_km + _STATE_PERIGEE_KM  # [km]
    a = radius_km + (_STATE_PERIGEE_KM + _STATE_APOGEE_KM) / 2.0  # [km]
    v_p = math.sqrt(mu_km3_s2 * (2.0 / r_p - 1.0 / a))  # [km/s]
    inc = math.radians(_STATE_INCLINATION_DEG)
    return ([round(r_p, 3), 0.0, 0.0],
            [0.0, round(v_p * math.cos(inc), 6), round(v_p * math.sin(inc), 6)])


def build_39_orbit_inputs_tle_and_state_vector() -> Scenario:
    # Three 150 kg satellites, each orbit given in another form the schema
    # takes: a TLE (synthetic, above), a Cartesian state (illustrative,
    # above) and classical elements (the starter orbit of 22). Orbit only,
    # no drag: the lesson is the input, so each orbit keeps its size.
    position_km, velocity_km_s = _illustrative_state_vector()

    def spacecraft(name: str, orbit: OrbitIC) -> SpacecraftConfig:
        return SpacecraftConfig(name=name, orbit=orbit, dry_mass_kg=_MICROSAT_MASS_KG,
                                inertia_kg_m2=_box_inertia(_MICROSAT_MASS_KG, _MICROSAT_SIZE_M))

    return Scenario(
        name="39 - Orbit inputs: TLE, state vector and elements",
        description=DESCRIPTIONS["39"],
        epoch_utc=_STARTER_EPOCH_UTC,
        simulation_mode="orbit_only",
        gravity=GravityConfig(central_body="earth", central_body_degree=10, third_body_perturbers=["sun", "moon"]),
        sim_settings=SimSettings(duration_days=1.0, dynamics_task_rate_s=30.0, integrator="rkf78"),
        spacecraft=[
            spacecraft("tle-sat", OrbitIC(type="tle", tle_line1=_SYNTHETIC_TLE[0], tle_line2=_SYNTHETIC_TLE[1])),
            spacecraft("state-sat", OrbitIC(type="cartesian", position_km=position_km, velocity_km_s=velocity_km_s)),
            spacecraft("elements-sat", _starter_orbit()),
        ],
    )


# The ENPULSION MICRO R3 of the device catalogue (engine/device_catalog.py,
# its datasheet values): an indium FEEP thruster, 1 mN, Isp 3000 s (the
# catalogue's choice in the published 1500 to 4500 s), 1.3 kg of propellant.
_FEEP_THRUST_N = 1.0e-3  # [N]
_FEEP_ISP_S = 3000.0  # [s]
_FEEP_PROPELLANT_KG = 1.3  # [kg]


def build_40_continuous_low_thrust() -> Scenario:
    # Two of 22's 150 kg satellites side by side at 400 km, one with an
    # electric thruster firing along the velocity the whole run (the
    # constant_thrust controller, VNB frame), one without. Drag from real
    # space weather: the twin decays, the thruster more than makes up for it.
    epoch_utc = "2030-01-01T00:00:00"
    semi_major_axis_km = 6378.0 + 400.0  # [km] as 25

    def spacecraft(name: str, thrust: bool) -> SpacecraftConfig:
        sc = SpacecraftConfig(
            name=name, orbit=_starter_orbit(semi_major_axis_km, epoch_utc),
            dry_mass_kg=_MICROSAT_MASS_KG, inertia_kg_m2=_box_inertia(_MICROSAT_MASS_KG, _MICROSAT_SIZE_M),
            enable_drag=True, drag_coeff=OPERATIONS_DRAG_COEFF, drag_area_m2=0.8,  # [-], [m^2]
        )
        if thrust:
            sc.constant_thrust = ConstantThrustConfig(frame="VNB", direction=[1.0, 0.0, 0.0], thrust_n=_FEEP_THRUST_N,
                                                      isp_s=_FEEP_ISP_S, propellant_kg=_FEEP_PROPELLANT_KG)
        return sc

    return Scenario(
        name="40 - Continuous low thrust: electric propulsion against drag",
        description=DESCRIPTIONS["40"],
        epoch_utc=epoch_utc,
        simulation_mode="orbit_only",
        gravity=GravityConfig(central_body="earth", central_body_degree=10, third_body_perturbers=["sun", "moon"]),
        sim_settings=SimSettings(duration_days=3.0, dynamics_task_rate_s=30.0, integrator="rkf78"),
        space_weather=_real_space_weather(),
        spacecraft=[spacecraft("ep-sat", True), spacecraft("twin-sat", False)],
    )


# Navigation errors (Basilisk's simpleNav random walk), ILLUSTRATIVE values
# of the order a star tracker, a gyro and a GNSS receiver give: attitude
# 0.002 deg a step within 0.02 deg per axis, rate 0.0001 deg/s within
# 0.001 deg/s, position 1 m within 10 m, velocity 1 cm/s within 0.1 m/s. No
# Sun-heading error: velocity pointing does not use the Sun.
_NAV_ERRORS = dict(attitude_step_deg=0.002, attitude_bound_deg=0.02, rate_step_deg_s=0.0001,  # [deg], [deg/s]
                   rate_bound_deg_s=0.001, position_step_m=1.0, position_bound_m=10.0,  # [deg/s], [m]
                   velocity_step_m_s=0.01, velocity_bound_m_s=0.1, seed=41)  # [m/s]


def build_41_velocity_pointing_with_navigation_errors() -> Scenario:
    # 07's 150 kg microsatellite, wheels and star tracker, turned to fly its
    # body y axis along the velocity (velocityPoint: y along v, z along the
    # orbit normal, x completing the frame), with a magnetometer (the MM200 of
    # the device catalogue) and errors on what the flight software is told.
    # 2027: inside the World Magnetic Model 2025's five years.
    epoch_utc = "2027-03-01T00:00:00"
    from spacemissionstudio.engine.device_catalog import CATALOG

    mm200 = next(entry for entry in CATALOG if entry.product_name == "MM200")
    return Scenario(
        name="41 - Velocity pointing with a magnetometer and navigation errors",
        description=DESCRIPTIONS["41"],
        epoch_utc=epoch_utc,
        simulation_mode="full_attitude",
        gravity=GravityConfig(central_body="earth", central_body_degree=10, third_body_perturbers=["sun", "moon"]),
        sim_settings=SimSettings(duration_days=0.07, dynamics_task_rate_s=1.0, integrator="rkf78"),
        spacecraft=[
            SpacecraftConfig(
                name="sat-1",
                orbit=_starter_orbit(epoch_utc=epoch_utc),
                dry_mass_kg=_MICROSAT_MASS_KG,
                inertia_kg_m2=_box_inertia(_MICROSAT_MASS_KG, _MICROSAT_SIZE_M),
                sigma_bn_init=[0.1, 0.2, -0.15],
                omega_bn_b_init_rad_s=[0.001, -0.001, 0.0005],
                sensors=[
                    SensorConfig(kind="star_tracker", name="st-1", params={"noise_arcsec": 5.0}),
                    SensorConfig(kind="imu", name="imu-1", params={"gyro_noise_rad_s": 1e-5}),
                    SensorConfig(kind="magnetometer", name="mag-1", params=dict(mm200.params)),
                ],
                actuators=[
                    ActuatorConfig(kind="reaction_wheel", name=f"rw-{k + 1}",
                                   params={"gsHat_B": axis, **_MICROSAT_WHEEL})
                    for k, axis in enumerate(([1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]))
                ],
                fsw_mode="velocityPoint",
                navigation_error=NavigationErrorConfig(**_NAV_ERRORS),
            ),
        ],
    )


def build_42_tabular_atmosphere_and_lifetime() -> Scenario:
    # One of 22's 150 kg satellites low enough to come down within the
    # lifetime estimate's year: 320 km. Drag reads NRLMSISE-00's nominal
    # profile, one of the tables Basilisk ships (engine.atmosphere_tables):
    # density by altitude only, with no solar activity, day or night.
    epoch_utc = "2024-10-01T00:00:00"
    return Scenario(
        name="42 - Atmosphere models: a tabular profile and the lifetime",
        description=DESCRIPTIONS["42"],
        epoch_utc=epoch_utc,
        simulation_mode="orbit_only",
        gravity=GravityConfig(central_body="earth", central_body_degree=10, third_body_perturbers=["sun", "moon"]),
        sim_settings=SimSettings(duration_days=2.0, dynamics_task_rate_s=30.0, integrator="rkf78"),
        space_weather=SpaceWeatherConfig(source="bundled", atmosphere_model="tabular",
                                         atmosphere_table="nrlmsise00_nominal", forecast_percentile=50.0),
        spacecraft=[
            SpacecraftConfig(
                name="low-sat",
                orbit=_starter_orbit(6378.0 + 350.0, epoch_utc),
                dry_mass_kg=_MICROSAT_MASS_KG,
                inertia_kg_m2=_box_inertia(_MICROSAT_MASS_KG, _MICROSAT_SIZE_M),
                enable_drag=True, drag_coeff=OPERATIONS_DRAG_COEFF, drag_area_m2=0.8,  # [-], [m^2]
            ),
        ],
    )



# -- Templates for every feature, batch B (43-47) -----------------------------
# Each shows a feature no earlier template uses: a 3D model from cylinders,
# spheres and an imported .obj mesh (43), the Monte Carlo dispersions of the
# attitude, inertia, body rate, SRP coefficient and atmospheric density (44),
# solar activity at MSFC's 95th percentile over a run chained past
# Basilisk's 104 days (45), the Mission Sequence's assignment, if, while and
# script block (46), and sensor faults (47). Decisions TPL-B1 to TPL-B6
# record the sources and the choices.

# Template 43's imported mesh: a SYNTHETIC camera, written here (not taken
# from any product or file) in millimetres, as many CAD tools export, with
# two groups: "camera_body", a closed 300 x 300 x 400 mm box (a solid part),
# and "camera_hood", an open square funnel 150 mm long from a 260 mm to a
# 340 mm opening (a shell part). +z is up; the camera looks along -z.
T43_MESH_FILE = "../meshes/43_synthetic_camera.obj"  # relative to the template's folder: scenarios/meshes/
_T43_BODY_MM = (300.0, 300.0, 400.0)  # [mm] x, y, z
_T43_HOOD_MM = (260.0, 340.0, 150.0)  # [mm] inner opening, outer opening, length


def _t43_camera_obj() -> str:
    """The text of template 43's synthetic ``.obj`` file (see above)."""
    hx, hy, bz = _T43_BODY_MM[0] / 2.0, _T43_BODY_MM[1] / 2.0, _T43_BODY_MM[2]  # [mm]
    inner, outer, length = _T43_HOOD_MM[0] / 2.0, _T43_HOOD_MM[1] / 2.0, _T43_HOOD_MM[2]  # [mm]
    lines = ["# A synthetic camera for SpaceMissionStudio's template 43: not a real product.",
             "# Written by scripts/_generate_templates.py. Units: mm. +z up; the camera looks along -z.",
             "o camera_body"]
    corners = [(sx * hx, sy * hy, z) for z in (-bz, 0.0) for sy in (-1, 1) for sx in (-1, 1)]
    lines += [f"v {x:g} {y:g} {z:g}" for x, y, z in corners]
    # Outward winding: bottom (-z), top (+z), then the four sides.
    lines += ["f 1 3 4 2", "f 5 6 8 7", "f 1 2 6 5", "f 3 7 8 4", "f 1 5 7 3", "f 2 4 8 6"]
    lines.append("o camera_hood")
    ring = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
    top = [(sx * inner, sy * inner, -bz) for sx, sy in ring]
    bottom = [(sx * outer, sy * outer, -bz - length) for sx, sy in ring]
    lines += [f"v {x:g} {y:g} {z:g}" for x, y, z in top + bottom]
    base = 8
    for k in range(4):  # four trapezoids, open at both ends, normals outward
        a, b = base + 1 + k, base + 1 + (k + 1) % 4
        lines.append(f"f {a} {a + 4} {b + 4} {b}")
    return "\n".join(lines) + "\n"


def _t43_model(mesh_sha256: str):
    """Template 43's model: a cylindrical bus with a spherical tank inside,
    a cylindrical boom with a spherical magnetometer at its tip, and the
    imported camera under the bus. Masses are illustrative."""
    from spacemissionstudio.schema.scenario import ModelMeshConfig, ModelPartConfig, SpacecraftModelConfig

    common = dict(drag_coeff=OPERATIONS_DRAG_COEFF)
    bus_radius_m, bus_height_m = 0.45, 1.0  # [m]
    boom_length_m = 1.0  # [m]
    return SpacecraftModelConfig(
        meshes=[ModelMeshConfig(path=T43_MESH_FILE, sha256=mesh_sha256, units="mm", up_axis="z")],
        parts=[
            ModelPartConfig(name="bus", shape="cylinder", dimensions_m={"diameter": 2 * bus_radius_m,
                                                                          "height": bus_height_m},
                            segments=24, color=[0.8, 0.65, 0.2], mass_kg=127.5, **common),  # [kg]
            ModelPartConfig(name="tank", shape="sphere", dimensions_m={"diameter": 0.4},  # [m]
                            position_b_m=[0.0, 0.0, 0.1], color=[0.6, 0.6, 0.65], visible=False,  # [m]
                            mass_kg=12.0, in_surface_model=False),  # [kg] tank and propellant, inside the bus
            ModelPartConfig(name="boom", shape="cylinder", dimensions_m={"diameter": 0.03, "height": boom_length_m},
                            position_b_m=[bus_radius_m + boom_length_m / 2.0, 0.0, 0.3],  # [m]
                            rotation_deg=[0.0, 90.0, 0.0], color=[0.3, 0.3, 0.3], mass_kg=1.0,  # [deg], [kg]
                            distribution="shell", excluded_faces=["-z"], **common),  # -z end sits on the bus
            ModelPartConfig(name="magnetometer", shape="sphere", dimensions_m={"diameter": 0.1},  # [m]
                            position_b_m=[bus_radius_m + boom_length_m + 0.05, 0.0, 0.3],  # [m]
                            color=[0.9, 0.9, 0.9], mass_kg=0.5, **common),  # [kg]
            ModelPartConfig(name="camera body", shape="mesh", mesh_index=0, mesh_group="camera_body",
                            position_b_m=[0.15, 0.0, -bus_height_m / 2.0], color=[0.2, 0.2, 0.25],  # [m]
                            mass_kg=8.0, **common),  # [kg]
            ModelPartConfig(name="camera hood", shape="mesh", mesh_index=0, mesh_group="camera_hood",
                            position_b_m=[0.15, 0.0, -bus_height_m / 2.0], color=[0.1, 0.1, 0.1],  # [m]
                            mass_kg=1.0, distribution="shell", **common),  # [kg]
        ],
    )


def build_43_3d_model_cylinders_spheres_and_mesh() -> Scenario:
    # A 150 kg microsatellite whose 3D model uses the shapes no other
    # template uses: cylinders (the bus, the boom), spheres (the tank, the
    # magnetometer) and two groups of an imported .obj mesh (the camera).
    # The run flies the mass, center of mass, inertia and facets derived
    # from them. Uncontrolled, so the small torques of drag, sunlight and
    # gravity on the offset center of mass show in the body rates.
    from spacemissionstudio.model3d import model as model3d

    mesh_path = OUT_DIR / T43_MESH_FILE
    mesh_path.parent.mkdir(parents=True, exist_ok=True)
    mesh_path.write_text(_t43_camera_obj(), encoding="utf-8", newline="\n")
    spacecraft = SpacecraftConfig(
        name="cyl-sat",
        orbit=_starter_orbit(),
        enable_drag=True, enable_srp=True,
        sigma_bn_init=[0.0, 0.0, 0.0],
        omega_bn_b_init_rad_s=[0.0, 0.0, 0.0],
        model=_t43_model(model3d.file_sha256(mesh_path)),
    )
    derived = model3d.derive(spacecraft.model, OUT_DIR)
    if derived.errors or derived.warnings:
        raise ValueError(f"template 43's model: {derived.errors + derived.warnings}")
    model3d.apply(spacecraft, derived)
    return Scenario(
        name="43 - 3D model: cylinders, spheres and an imported mesh",
        description=DESCRIPTIONS["43"],
        epoch_utc=_STARTER_EPOCH_UTC,
        simulation_mode="full_attitude",
        gravity=GravityConfig(central_body="earth", central_body_degree=10, third_body_perturbers=["sun", "moon"]),
        sim_settings=SimSettings(duration_days=0.1, dynamics_task_rate_s=1.0, integrator="rkf78",
                                 record_interval_s=10.0),  # [day], [s], [s]
        space_weather=_real_space_weather(),
        spacecraft=[spacecraft],
    )


def build_44_monte_carlo_attitude_inertia_rate_srp_density() -> Scenario:
    # The five dispersions no other template draws, in one small batch:
    # template 07's 150 kg microsatellite on three wheels in Sun-safe
    # pointing at 350 km, with drag and sunlight pressure; each run draws its
    # initial attitude (any), its body rate, its inertia, its SRP
    # coefficient and the atmosphere's density scale. Every spread is
    # illustrative. Half an orbit: enough for the wheels to turn every run
    # onto the Sun and for the density to separate the decays.
    epoch_utc = "2030-01-01T00:00:00"
    deg = math.pi / 180.0
    return Scenario(
        name="44 - Monte Carlo: attitude, inertia, body rate, SRP and density",
        description=DESCRIPTIONS["44"],
        epoch_utc=epoch_utc,
        simulation_mode="full_attitude",
        gravity=GravityConfig(central_body="earth", central_body_degree=10, third_body_perturbers=["sun", "moon"]),
        sim_settings=SimSettings(duration_days=0.03, dynamics_task_rate_s=1.0, integrator="rkf78",
                                 record_interval_s=10.0),  # [day], [s], [s]
        space_weather=_real_space_weather(),
        spacecraft=[
            SpacecraftConfig(
                name="sat-1",
                orbit=_starter_orbit(6378.0 + 350.0, epoch_utc),
                dry_mass_kg=_MICROSAT_MASS_KG,
                inertia_kg_m2=_box_inertia(_MICROSAT_MASS_KG, _MICROSAT_SIZE_M),
                enable_drag=True, drag_coeff=OPERATIONS_DRAG_COEFF, drag_area_m2=0.8,  # [-], [m^2]
                enable_srp=True, srp_coeff=1.5, srp_area_m2=0.8,  # [-], [m^2]
                sigma_bn_init=[0.1, 0.2, -0.15],
                omega_bn_b_init_rad_s=[0.001, -0.001, 0.0005],  # [rad/s]
                actuators=[
                    ActuatorConfig(kind="reaction_wheel", name=f"rw-{k + 1}", params={"gsHat_B": axis, **_MICROSAT_WHEEL})
                    for k, axis in enumerate(([1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]))
                ],
                fsw_mode="sunSafePoint",
                fsw_params={"sHatBdyCmd": [0.0, 0.0, 1.0]},
            ),
        ],
        monte_carlo=MonteCarloConfig(
            enabled=True, num_runs=12, thread_count=1, seed=44,
            dispersions=[
                DispersionConfig(spacecraft="sat-1", quantity="attitude_sigma_bn", kind="uniform_euler_mrp",
                                 bounds=[-180.0 * deg, 180.0 * deg]),  # [rad] any attitude
                DispersionConfig(spacecraft="sat-1", quantity="angular_rate_bn_b", kind="normal",
                                 std_deviation=0.2),  # [deg/s] 1-sigma, each axis
                DispersionConfig(spacecraft="sat-1", quantity="inertia_kg_m2", kind="normal",
                                 std_deviation=1.0, angle_std_deg=2.0),  # [kg*m^2], [deg]
                DispersionConfig(spacecraft="sat-1", quantity="srp_coeff", kind="uniform",
                                 bounds=[1.2, 1.8]),  # [-]
                DispersionConfig(spacecraft="", quantity="density_scale", kind="uniform",
                                 bounds=[0.7, 1.3]),  # [-]
            ],
        ),
    )


def build_45_solar_activity_past_104_days() -> Scenario:
    # A 150 kg satellite at 400 km for 110 days, longer than one Basilisk
    # simulation can hold (about 104 days): the run is chained, 90 days and
    # then 20. The Sun of those days is MSFC's prediction at its 95th
    # percentile (ESA AD10's conservative case for operations). Orbit only
    # at Basilisk's long-step limit (60 s) with J2 alone, so the 110 days
    # take seconds.
    epoch_utc = "2030-01-01T00:00:00"
    return Scenario(
        name="45 - Solar activity at the 95th percentile, past 104 days",
        description=DESCRIPTIONS["45"],
        epoch_utc=epoch_utc,
        simulation_mode="orbit_only",
        gravity=GravityConfig(central_body="earth", central_body_degree=2),
        sim_settings=SimSettings(duration_days=110.0, dynamics_task_rate_s=60.0, integrator="rkf78",
                                 record_interval_s=600.0),  # [day], [s], [s]
        space_weather=SpaceWeatherConfig(source="bundled", atmosphere_model="nrlmsise00", forecast_percentile=95.0),
        spacecraft=[
            SpacecraftConfig(
                name="sat-1",
                orbit=_starter_orbit(6378.0 + 400.0, epoch_utc),
                dry_mass_kg=_MICROSAT_MASS_KG,
                inertia_kg_m2=_box_inertia(_MICROSAT_MASS_KG, _MICROSAT_SIZE_M),
                enable_drag=True, drag_coeff=OPERATIONS_DRAG_COEFF, drag_area_m2=0.8,  # [-], [m^2]
            ),
        ],
    )


# Template 46's script block: plain Python that the run executes only after
# the user agrees. It reads the state the Mission Sequence gives every
# script (spacecraft, t_s) and adds a row to Results > Output.
T46_SCRIPT = """\
# Semi-major axis and period from the state now (vis-viva), as a row of Results > Output.
import math
from spacemissionstudio.engine.results import ReportEntry

state = spacecraft["raise-sat"]
r_m = math.sqrt(sum(x * x for x in state["r_BN_N"]))
v2_m2_s2 = sum(v * v for v in state["v_BN_N"])
mu_m3_s2 = 3.986004415e14  # Earth's GM [m^3/s^2]
a_m = 1.0 / (2.0 / r_m - v2_m2_s2 / mu_m3_s2)
summary.reports.append(ReportEntry(label="Script: semi-major axis and period", t_s=t_s, values={
    "raise-sat.script.semi_major_axis_km": a_m / 1000.0,
    "raise-sat.script.period_min": 2.0 * math.pi * math.sqrt(a_m ** 3 / mu_m3_s2) / 60.0,
}))
"""

_T46_TARGET_ALTITUDE_M = 420.0e3  # [m] above the equatorial radius
_T46_THRUST_N = 0.02  # [N] illustrative: a small electric thruster
_T46_ISP_S = 1500.0  # [s] illustrative
_T46_PROPELLANT_KG = 5.0  # [kg] illustrative


def build_46_mission_sequence_control_flow() -> Scenario:
    # The four Mission Sequence commands no other template uses, on one
    # orbit raise: assignments switch a 20 mN thruster (constant_thrust)
    # off and on, a while loop fires in short steps until the altitude is
    # 420 km, an if checks it and takes a snapshot, and a script block works
    # out the new semi-major axis and period. Two-body gravity, no drag:
    # only the thrust changes the orbit, so the altitude the conditions read
    # is that of a slowly widening circle.
    from spacemissionstudio.schema.command import Command

    epoch_utc = "2030-01-01T00:00:00"
    target = "raise-sat.constant_thrust.thrust_n"
    altitude = "spacecraft['raise-sat']['altitude_m']"
    snapshot = ["raise-sat.orbit_elements.semi_major_axis", "raise-sat.constant_thrust.delta_v",
                "raise-sat.constant_thrust.propellant_remaining"]
    return Scenario(
        name="46 - Mission Sequence: assignment, if, while and a script block",
        description=DESCRIPTIONS["46"],
        epoch_utc=epoch_utc,
        simulation_mode="orbit_only",
        gravity=GravityConfig(central_body="earth", central_body_degree=0),
        sim_settings=SimSettings(duration_days=2.0, dynamics_task_rate_s=30.0, integrator="rkf78"),  # [day], [s]
        spacecraft=[
            SpacecraftConfig(
                name="raise-sat",
                orbit=_starter_orbit(6378.0 + 400.0, epoch_utc),
                dry_mass_kg=_MICROSAT_MASS_KG,
                inertia_kg_m2=_box_inertia(_MICROSAT_MASS_KG, _MICROSAT_SIZE_M),
                constant_thrust=ConstantThrustConfig(frame="VNB", direction=[1.0, 0.0, 0.0], thrust_n=_T46_THRUST_N,
                                                     isp_s=_T46_ISP_S, propellant_kg=_T46_PROPELLANT_KG),
            ),
        ],
        mission_sequence=[
            Command(kind="assignment", label="Thruster off", params={"target": target, "value": 0.0}),
            Command(kind="propagate", label="Coast at 400 km",
                    params={"stop_condition": "duration", "duration_days": 0.25}),
            Command(kind="report", label="Before the raise", params={"series": snapshot}),
            Command(kind="assignment", label="Thruster on", params={"target": target, "value": _T46_THRUST_N}),
            Command(kind="while", label="Fire until 420 km",
                    params={"condition": f"{altitude} < {_T46_TARGET_ALTITUDE_M:.1f}"},
                    children=[Command(kind="propagate", label="Fire for 0.05 day",
                                      params={"stop_condition": "duration", "duration_days": 0.05})]),
            Command(kind="assignment", label="Thruster off again", params={"target": target, "value": 0.0}),
            Command(kind="if", label="Check the altitude",
                    params={"condition": f"{altitude} >= {_T46_TARGET_ALTITUDE_M:.1f}"},
                    children=[Command(kind="report", label="Raised", params={"series": snapshot})]),
            Command(kind="script_block", label="Semi-major axis and period", params={"code": T46_SCRIPT}),
            Command(kind="propagate", label="Coast at the new height",
                    params={"stop_condition": "duration", "duration_days": 0.25}),
            Command(kind="report", label="End", params={"series": snapshot}),
        ],
    )


# Template 47's thermal sensor: template 20's (a 0.05 m^2 plate on the
# Sun-facing +z face), without measurement noise so the fault stands out.
_T47_THERMAL = {"nHat_B": [0.0, 0.0, 1.0], "area_m2": 0.05, "absorptivity": 0.25, "emissivity": 0.34,  # [m^2]
                "mass_kg": 0.3, "specific_heat_j_kg_k": 890.0, "initial_temp_c": 0.0,  # [kg], [J/(kg*K)], [C]
                "power_draw_w": 0.5}  # [W]
_T47_STUCK_TEMPERATURE_C = 20.0  # [C] illustrative


def build_47_sensor_faults() -> Scenario:
    # Two of template 14's microsatellites side by side in Sun-safe pointing
    # (from the true Sun direction), each with two coarse sun sensors (+z
    # toward the Sun, -z away), a magnetometer and a thermal sensor.
    # faulty-sat has three of the fault modes Basilisk models: css-2 (the
    # one facing away from the Sun) stuck at its largest output, the
    # magnetometer's z axis spiking (now and then a reading times 3) and the
    # thermal sensor's reading stuck at 20 C. healthy-sat has none. The
    # faults change what the sensors report; the flight software here reads
    # the true state, so both spacecraft fly the same attitude.
    epoch_utc = "2027-03-01T00:00:00"  # inside the World Magnetic Model 2025's five years (as 41)

    def spacecraft(name: str, faulty: bool) -> SpacecraftConfig:
        css_plus = {"nHat_B": [0.0, 0.0, 1.0], "fov_deg": 160.0}
        css_minus = {"nHat_B": [0.0, 0.0, -1.0], "fov_deg": 160.0}
        mag = {"noise_std_tesla": [1.0e-7, 1.0e-7, 1.0e-7]}  # [T] illustrative
        thermal = dict(_T47_THERMAL)
        if faulty:
            css_minus["fault_mode"] = "stuck_max"
            mag.update(fault_mode="spiking", fault_axis=2, spike_probability=0.01, spike_amount=3.0)  # [-]
            thermal.update(measurement_fault_mode="stuck_value", measurement_stuck_value_c=_T47_STUCK_TEMPERATURE_C)
        return SpacecraftConfig(
            name=name,
            orbit=OrbitIC(type="classical_elements", semi_major_axis_km=6928.0, eccentricity=0.0,
                          inclination_deg=45.0, raan_deg=0.0, arg_periapsis_deg=0.0, true_anomaly_deg=0.0),
            dry_mass_kg=_MICROSAT_MASS_KG,
            inertia_kg_m2=_box_inertia(_MICROSAT_MASS_KG, _MICROSAT_SIZE_M),
            sigma_bn_init=[0.1, 0.2, -0.15],
            omega_bn_b_init_rad_s=[0.001, -0.001, 0.0005],  # [rad/s]
            sensors=[
                SensorConfig(kind="coarse_sun_sensor", name="css-1", params=css_plus),
                SensorConfig(kind="coarse_sun_sensor", name="css-2", params=css_minus),
                SensorConfig(kind="magnetometer", name="mag-1", params=mag),
                SensorConfig(kind="thermal", name="therm-1", params=thermal),
            ],
            actuators=[
                ActuatorConfig(kind="reaction_wheel", name=f"rw-{k + 1}", params={"gsHat_B": axis, **_MICROSAT_WHEEL})
                for k, axis in enumerate(([1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]))
            ],
            fsw_mode="sunSafePoint",
            fsw_params={"sHatBdyCmd": [0.0, 0.0, 1.0]},
        )

    return Scenario(
        name="47 - Sensor faults: stuck and spiking readings",
        description=DESCRIPTIONS["47"],
        epoch_utc=epoch_utc,
        simulation_mode="full_attitude",
        gravity=GravityConfig(central_body="earth", central_body_degree=0, third_body_perturbers=["sun"]),
        sim_settings=SimSettings(duration_days=0.04, dynamics_task_rate_s=1.0, integrator="rkf78",
                                 seed=47),  # [day], [s]
        spacecraft=[spacecraft("healthy-sat", False), spacecraft("faulty-sat", True)],
    )

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _save(build_01_two_body_circular_orbit(), "01_two_body_circular_orbit.json")
    _save(build_02_elliptical_orbit_with_perturbations(), "02_elliptical_orbit_with_perturbations.json")
    _save(build_03_geo_station_keeping(), "03_geo_station_keeping.json")
    _save(build_04_walker_constellation(), "04_walker_constellation.json")
    _save(build_05_formation_flying_phasing(), "05_formation_flying_phasing.json")
    _save(build_06_attitude_pointing_basic(), "06_attitude_pointing_basic.json")
    _save(build_07_attitude_pointing_with_adcs_hardware(), "07_attitude_pointing_with_adcs_hardware.json")
    _save(build_08_mission_sequence_orbit_raise(), "08_mission_sequence_orbit_raise.json")
    _save(build_09_monte_carlo_dispersion_analysis(), "09_monte_carlo_dispersion_analysis.json")
    _save(build_10_gravity_gradient_torque(), "10_gravity_gradient_torque.json")
    _save(build_11_thruster_attitude_control(), "11_thruster_attitude_control.json")
    _save(build_12_reaction_wheel_momentum_dumping(), "12_reaction_wheel_momentum_dumping.json")
    _save(build_13_magnetic_torque_rod_momentum_management(),
          "13_magnetic_torque_rod_momentum_management.json")
    _save(build_14_css_sun_heading_estimation(), "14_css_sun_heading_estimation.json")
    _save(build_15_celestial_body_pointing(), "15_celestial_body_pointing.json")
    _save(build_16_lambert_transfer(), "16_lambert_transfer.json")
    _save(build_17_fuel_tank_depletion(), "17_fuel_tank_depletion.json")
    _save(build_18_leo_station_keeping(), "18_leo_station_keeping.json")
    _save(build_19_sun_pointing_comms_link(), "19_sun_pointing_comms_link.json")
    _save(build_20_thermal_simulation(), "20_thermal_simulation.json")
    _save(build_21_disturbance_torques(), "21_disturbance_torques.json")
    _save(build_22_starter_first_leo_satellite(), "22_starter_first_leo_satellite.json")
    _save(build_23_starter_complete_small_satellite(), "23_starter_complete_small_satellite.json")
    _save(build_24_formation_mean_element_control(), "24_formation_mean_element_control.json")
    _save(build_25_monte_carlo_orbit_and_drag_dispersions(), "25_monte_carlo_orbit_and_drag_dispersions.json")
    _save(build_26_earth_observation_data_downlink(), "26_earth_observation_data_downlink.json")
    _save(build_27_flexible_solar_arrays(), "27_flexible_solar_arrays.json")
    _save(build_28_octagonal_bus_3d_model(), "28_octagonal_bus_3d_model.json")
    _save(build_29_roe_formation_helix(), "29_roe_formation_helix.json")
    _save(build_30_mars_optical_navigation(), "30_mars_optical_navigation.json")
    _save(build_31_eros_landmark_navigation(), "31_eros_landmark_navigation.json")
    _save(build_32_smallsat_design_checks(), "32_smallsat_design_checks.json")
    _save(build_33_microsat_thermal(), "33_microsat_thermal.json")
    _save(build_34_microsat_flexible_thermal(), "34_microsat_flexible_thermal.json")
    _save(build_35_eo_operations_week(), "35_eo_operations_week.json")
    _save(build_36_constellation_operations(), "36_constellation_operations.json")
    _save(build_37_monte_carlo_requirements_and_sensitivity(), "37_monte_carlo_requirements_and_sensitivity.json")
    _save(build_38_budgets_equipment_power_mass_propellant(), "38_budgets_equipment_power_mass_propellant.json")
    _save(build_39_orbit_inputs_tle_and_state_vector(), "39_orbit_inputs_tle_and_state_vector.json")
    _save(build_40_continuous_low_thrust(), "40_continuous_low_thrust.json")
    _save(build_41_velocity_pointing_with_navigation_errors(), "41_velocity_pointing_with_navigation_errors.json")
    _save(build_42_tabular_atmosphere_and_lifetime(), "42_tabular_atmosphere_and_lifetime.json")
    _save(build_43_3d_model_cylinders_spheres_and_mesh(), "43_3d_model_cylinders_spheres_and_mesh.json")
    _save(build_44_monte_carlo_attitude_inertia_rate_srp_density(),
          "44_monte_carlo_attitude_inertia_rate_srp_density.json")
    _save(build_45_solar_activity_past_104_days(), "45_solar_activity_past_104_days.json")
    _save(build_46_mission_sequence_control_flow(), "46_mission_sequence_control_flow.json")
    _save(build_47_sensor_faults(), "47_sensor_faults.json")


if __name__ == "__main__":
    main()
