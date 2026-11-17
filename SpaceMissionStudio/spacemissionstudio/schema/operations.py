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
"""The scenario's ``operations`` section: what the operations planner
needs to turn mission goals into a time-tagged plan
(docs/developer/operations-planning-design.md, section 2.3).

Targets (points and polygons), activity types, requests (calibrations,
momentum management, maneuvers, user activities), the stations' and the
spacecraft's planning settings, the scheduler's settings, locked
activities, what-if events and the verification tolerances. The section
has its own ``version`` (decision O-06); a scenario without it saves and
hashes as before.

No mission value has a default (decision O-07): durations, power, data
rates, priorities, thresholds, agility and detector values are the
user's. The defaults below are the tool's conventions (score weights,
tolerances, the geometry step), each recorded in the decision log.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, UTC

from .epochs import parse_epoch_utc

OPERATIONS_VERSION = 1
POINTING_MODES = ("sun", "nadir", "target", "station", "inertial")
ACTIVITY_KINDS = ("acquisition", "contact", "maneuver", "calibration", "momentum_management", "user")
TARGET_KINDS = ("point", "polygon")
GEOMETRY_SOURCES = ("propagation", "run", "analytic")
OBJECTIVES = ("lexicographic", "weighted")
AGILITY_SOURCES = ("controller", "limits")
REQUEST_PERIODS = ("horizon", "day", "orbit")
MANEUVER_FRAMES = ("inertial", "rtn", "vnb")
WHAT_IF_KINDS = ("lost_pass", "station_outage", "instrument_outage", "extra_request", "delayed_maneuver")
#: One Basilisk run's longest time (SimSettings._MAX_SINGLE_RUN_DAYS); a plan is flown in one run.
MAX_HORIZON_DAYS = 104.0  # [day]
_MAX_DURATION_S = 86400.0  # [s] one activity at most a day long
_MAX_POWER_W = 1.0e5  # [W] well above this size class
_EARTH_SURFACE_ALTITUDE_M = (-500.0, 9000.0)  # [m] a target's altitude, below sea level to the highest summits


def _fail(message: str) -> None:
    from .scenario import ScenarioValidationError

    raise ScenarioValidationError(message)


def _require(condition: bool, message: str) -> None:
    if not condition:
        _fail(message)


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _range(value, where: str, name: str, low: float, high: float, closed_low: bool = True,
           optional: bool = True) -> None:
    if value is None:
        _require(optional, f"{where}: {name} is needed")
        return
    ok = _number(value) and (value >= low if closed_low else value > low) and value <= high
    _require(ok, f"{where}: {name} must be in {'[' if closed_low else '('}{low:g}, {high:g}]")


def _name(value, where: str, what: str) -> None:
    _require(isinstance(value, str) and value.strip() == value and bool(value) and "]" not in value
             and "," not in value and len(value) <= 127,
             f"{where}: a {what} needs a name of at most 127 characters without ',', ']' or surrounding spaces")


def _vector(value, where: str, name: str, optional: bool = True) -> None:
    if value is None:
        _require(optional, f"{where}: {name} is needed")
        return
    _require(isinstance(value, list) and len(value) == 3 and all(_number(v) for v in value)
             and math.hypot(*value) > 1e-9, f"{where}: {name} must be a non-zero [x, y, z]")


def utc(text, where: str, name: str) -> datetime:
    """``text`` as a naive UTC datetime; refuses anything else."""
    try:
        moment = parse_epoch_utc(text)
    except (TypeError, ValueError):
        _fail(f"{where}: {name} {text!r} is not an ISO 8601 UTC time")
    if moment.tzinfo is not None:
        moment = moment.astimezone(UTC).replace(tzinfo=None)
    return moment


def _window(value, where: str, name: str) -> tuple[datetime, datetime] | None:
    if value is None:
        return None
    _require(isinstance(value, list) and len(value) == 2, f"{where}: {name} must be [start_utc, end_utc]")
    start, end = utc(value[0], where, f"{name} start"), utc(value[1], where, f"{name} end")
    _require(start < end, f"{where}: {name} must start before it ends")
    return start, end


@dataclass
class HorizonConfig:
    """The planning horizon, in UTC."""

    start_utc: str
    end_utc: str


@dataclass
class GeometryConfig:
    """Where the planner's trajectory comes from (decision O-03) and the
    step of its grid. ``step_s`` 10 s is a tool convention: a 20 s
    acquisition window is then sampled at least twice and edges are
    interpolated."""

    source: str = "propagation"  # one of GEOMETRY_SOURCES
    step_s: float = 10.0  # [s]

    def validate(self, where: str) -> None:
        _require(self.source in GEOMETRY_SOURCES, f"{where}: source {self.source!r} must be one of {GEOMETRY_SOURCES}")
        _range(self.step_s, where, "step_s", 0.1, 600.0)


@dataclass
class DetectorConfig:
    """An imager's detector, for the ground sample distance (GSD = slant
    range x pixel pitch / focal length) and its footprint."""

    pixel_pitch_um: float | None = None  # [um]
    focal_length_mm: float | None = None  # [mm]
    field_of_view_deg: float | None = None  # [deg] full cone, for polygon coverage

    def validate(self, where: str) -> None:
        where = f"{where}: detector"
        _range(self.pixel_pitch_um, where, "pixel_pitch_um", 0.0, 1000.0, closed_low=False)
        _range(self.focal_length_mm, where, "focal_length_mm", 0.0, 1.0e5, closed_low=False)
        _require((self.pixel_pitch_um is None) == (self.focal_length_mm is None),
                 f"{where}: give pixel_pitch_um and focal_length_mm together")
        _range(self.field_of_view_deg, where, "field_of_view_deg", 0.0, 120.0, closed_low=False)


@dataclass
class TargetConfig:
    """A place to acquire: a point (latitude, longitude) or a polygon
    (``vertices_deg`` [[lat, lon], ...], sampled every ``cell_km``)."""

    name: str
    priority: int  # 1 is the highest
    activity: str  # the acquisition activity type
    max_off_nadir_deg: float  # [deg]
    kind: str = "point"  # one of TARGET_KINDS
    latitude_deg: float | None = None  # [deg] geodetic (WGS-84)
    longitude_deg: float | None = None  # [deg] east
    altitude_m: float = 0.0  # [m] above the ellipsoid
    vertices_deg: list | None = None  # [[deg, deg], ...] polygon, (latitude, longitude)
    cell_km: float | None = None  # [km] polygon sampling
    min_coverage: float | None = None  # [-] polygon: the fraction an acquisition must cover
    acquisitions: int = 1  # how many acquisitions are wanted
    min_elevation_deg: float | None = None  # [deg] at the target
    sun_elevation_deg: list | None = None  # [deg] [lowest, highest] at the target
    valid_utc: list | None = None  # [start, end]
    spacecraft: list = field(default_factory=list)  # who may acquire it; empty: every planned spacecraft
    enabled: bool = True  # False: only a what-if 'extra_request' brings it in

    def validate(self, where: str) -> None:
        _name(self.name, where, "target")
        where = f"{where}: target {self.name!r}"
        _require(self.kind in TARGET_KINDS, f"{where}: kind {self.kind!r} must be one of {TARGET_KINDS}")
        _require(isinstance(self.priority, int) and not isinstance(self.priority, bool) and 1 <= self.priority <= 99,
                 f"{where}: priority must be a whole number from 1 (highest) to 99")
        _require(isinstance(self.acquisitions, int) and not isinstance(self.acquisitions, bool)
                 and 1 <= self.acquisitions <= 1000, f"{where}: acquisitions must be a whole number from 1 to 1000")
        _range(self.max_off_nadir_deg, where, "max_off_nadir_deg", 0.0, 89.0, optional=False)
        _range(self.min_elevation_deg, where, "min_elevation_deg", 0.0, 90.0)
        _range(self.altitude_m, where, "altitude_m", *_EARTH_SURFACE_ALTITUDE_M)
        if self.sun_elevation_deg is not None:
            band = self.sun_elevation_deg
            _require(isinstance(band, list) and len(band) == 2 and all(_number(v) for v in band)
                     and -90.0 <= band[0] < band[1] <= 90.0,
                     f"{where}: sun_elevation_deg must be [lowest, highest] in [-90, 90] deg")
        _window(self.valid_utc, where, "valid_utc")
        _require(isinstance(self.spacecraft, list) and all(isinstance(s, str) for s in self.spacecraft),
                 f"{where}: spacecraft must be a list of spacecraft names")
        _require(isinstance(self.enabled, bool), f"{where}: enabled must be true or false")
        if self.kind == "point":
            _range(self.latitude_deg, where, "latitude_deg", -90.0, 90.0, optional=False)
            _range(self.longitude_deg, where, "longitude_deg", -180.0, 360.0, optional=False)
            _require(self.vertices_deg is None and self.cell_km is None and self.min_coverage is None,
                     f"{where}: a point has no vertices_deg, cell_km or min_coverage")
        else:
            vertices = self.vertices_deg
            _require(isinstance(vertices, list) and len(vertices) >= 3
                     and all(isinstance(v, list) and len(v) == 2 and all(_number(x) for x in v)
                             and -90.0 <= v[0] <= 90.0 and -180.0 <= v[1] <= 360.0 for v in vertices),
                     f"{where}: vertices_deg must be at least three [latitude, longitude] pairs")
            longitudes = [v[1] for v in vertices]
            _require(max(longitudes) - min(longitudes) < 180.0,
                     f"{where}: the polygon spans 180 deg of longitude or more; split it at the antimeridian")
            _require(self.latitude_deg is None and self.longitude_deg is None,
                     f"{where}: a polygon is given by vertices_deg, not latitude_deg/longitude_deg")
            _range(self.cell_km, where, "cell_km", 0.01, 1000.0, optional=False)
            _range(self.min_coverage, where, "min_coverage", 0.0, 1.0, closed_low=False)


@dataclass
class ActivityTypeConfig:
    """A kind of activity and how it is flown."""

    name: str
    kind: str  # one of ACTIVITY_KINDS
    pointing: str  # one of POINTING_MODES
    duration_s: float | None = None  # [s] contacts take the pass (min_duration_s)
    min_duration_s: float | None = None  # [s] contacts only
    setup_s: float = 0.0  # [s] before the activity (pointing held, devices warming up)
    teardown_s: float = 0.0  # [s] after it
    equipment: str = ""  # mounted equipment (camera, antenna) whose boresight is pointed (and field of view)
    boresight_b: list | None = None  # [-] body axis pointed at the target or station, if no equipment
    sun_axis_b: list | None = None  # [-] 'sun' pointing: the axis on the Sun (default: the panel normal)
    sigma_rn: list | None = None  # [-] 'inertial' pointing: the reference attitude (MRP)
    instruments: list = field(default_factory=list)  # data_handling instruments switched on
    transmitter: bool = False  # contacts: the transmitter downlinks
    power_w: float = 0.0  # [W] load on top of the instruments' and transmitter's
    delta_v_m_s: list | None = None  # [m/s] maneuvers: the impulse
    frame: str = "vnb"  # maneuvers: one of MANEUVER_FRAMES

    def validate(self, where: str) -> None:
        _name(self.name, where, "activity type")
        where = f"{where}: activity type {self.name!r}"
        _require(self.kind in ACTIVITY_KINDS, f"{where}: kind {self.kind!r} must be one of {ACTIVITY_KINDS}")
        _require(self.pointing in POINTING_MODES, f"{where}: pointing {self.pointing!r} must be one of "
                                                  f"{POINTING_MODES}")
        for name in ("setup_s", "teardown_s"):
            _range(getattr(self, name), where, name, 0.0, _MAX_DURATION_S)
        _range(self.power_w, where, "power_w", 0.0, _MAX_POWER_W)
        if self.kind == "contact":
            _require(self.pointing == "station", f"{where}: a contact points at the station (pointing 'station')")
            _require(self.duration_s is None, f"{where}: a contact lasts its pass; give min_duration_s")
            _range(self.min_duration_s, where, "min_duration_s", 0.0, _MAX_DURATION_S, closed_low=False,
                   optional=False)
        else:
            _require(self.min_duration_s is None and not self.transmitter,
                     f"{where}: min_duration_s and transmitter are for contacts")
            _range(self.duration_s, where, "duration_s", 0.0, _MAX_DURATION_S, closed_low=False, optional=False)
        if self.kind == "acquisition":
            _require(self.pointing in ("target", "nadir"), f"{where}: an acquisition points at its target "
                                                          "(pointing 'target' or 'nadir')")
        _require(self.pointing != "target" or self.kind == "acquisition",
                 f"{where}: pointing 'target' is for acquisitions")
        if self.pointing in ("target", "station"):
            _require(bool(self.equipment) or self.boresight_b is not None,
                     f"{where}: pointing {self.pointing!r} needs equipment or boresight_b")
        _require(not (self.equipment and self.boresight_b is not None),
                 f"{where}: give equipment or boresight_b, not both")
        _vector(self.boresight_b, where, "boresight_b")
        _vector(self.sun_axis_b, where, "sun_axis_b")
        if self.pointing == "inertial":
            _require(isinstance(self.sigma_rn, list) and len(self.sigma_rn) == 3
                     and all(_number(v) for v in self.sigma_rn) and math.hypot(*self.sigma_rn) <= 1.0,
                     f"{where}: pointing 'inertial' needs sigma_rn, an MRP [s1, s2, s3] of norm at most 1")
        else:
            _require(self.sigma_rn is None, f"{where}: sigma_rn is for pointing 'inertial'")
        _require(isinstance(self.instruments, list) and all(isinstance(i, str) for i in self.instruments)
                 and len(set(self.instruments)) == len(self.instruments),
                 f"{where}: instruments must be a list of distinct instrument names")
        _require(isinstance(self.transmitter, bool), f"{where}: transmitter must be true or false")
        if self.kind == "maneuver":
            _require(isinstance(self.delta_v_m_s, list) and len(self.delta_v_m_s) == 3
                     and all(_number(v) for v in self.delta_v_m_s) and math.hypot(*self.delta_v_m_s) <= 1.0e4,
                     f"{where}: a maneuver needs delta_v_m_s [x, y, z] in m/s")
            _require(self.frame in MANEUVER_FRAMES, f"{where}: frame {self.frame!r} must be one of {MANEUVER_FRAMES}")
        else:
            _require(self.delta_v_m_s is None, f"{where}: delta_v_m_s is for maneuvers")


@dataclass
class RequestConfig:
    """A request for an activity that is not an acquisition of a target:
    a calibration, momentum management, a maneuver or a user activity,
    ``count`` times per ``per`` (the horizon, each day or each orbit),
    within ``window_utc`` if given, or at ``at_utc`` exactly."""

    name: str
    activity: str
    spacecraft: str
    priority: int
    count: int = 1
    per: str = "horizon"  # one of REQUEST_PERIODS
    window_utc: list | None = None  # [start, end]
    at_utc: str | None = None  # a fixed time (maneuvers)
    enabled: bool = True

    def validate(self, where: str) -> None:
        _name(self.name, where, "request")
        where = f"{where}: request {self.name!r}"
        _require(isinstance(self.priority, int) and not isinstance(self.priority, bool) and 1 <= self.priority <= 99,
                 f"{where}: priority must be a whole number from 1 (highest) to 99")
        _require(isinstance(self.count, int) and not isinstance(self.count, bool) and 1 <= self.count <= 1000,
                 f"{where}: count must be a whole number from 1 to 1000")
        _require(self.per in REQUEST_PERIODS, f"{where}: per {self.per!r} must be one of {REQUEST_PERIODS}")
        _window(self.window_utc, where, "window_utc")
        if self.at_utc is not None:
            utc(self.at_utc, where, "at_utc")
            _require(self.window_utc is None and self.count == 1 and self.per == "horizon",
                     f"{where}: a request at a fixed time has no window_utc, count or per")
        _require(isinstance(self.enabled, bool), f"{where}: enabled must be true or false")


@dataclass
class StationPlanningConfig:
    """A ground station's planning settings."""

    station: str
    azimuth_mask: list = field(default_factory=list)  # [[azimuth deg, minimum elevation deg], ...]
    capacity: int = 1  # spacecraft served at once
    setup_s: float = 0.0  # [s] before each contact
    handover_s: float = 0.0  # [s] between two contacts
    unavailable_utc: list = field(default_factory=list)  # [[start, end], ...]

    def validate(self, where: str) -> None:
        where = f"{where}: station {self.station!r}"
        mask = self.azimuth_mask
        _require(isinstance(mask, list) and all(isinstance(p, list) and len(p) == 2 and all(_number(v) for v in p)
                                                and 0.0 <= p[0] < 360.0 and 0.0 <= p[1] < 90.0 for p in mask),
                 f"{where}: azimuth_mask must be [[azimuth in [0, 360) deg, elevation in [0, 90) deg], ...]")
        azimuths = [p[0] for p in mask]
        _require(azimuths == sorted(azimuths) and len(set(azimuths)) == len(azimuths),
                 f"{where}: azimuth_mask must list increasing azimuths")
        _require(isinstance(self.capacity, int) and not isinstance(self.capacity, bool) and 1 <= self.capacity <= 100,
                 f"{where}: capacity must be a whole number from 1 to 100")
        _range(self.setup_s, where, "setup_s", 0.0, _MAX_DURATION_S)
        _range(self.handover_s, where, "handover_s", 0.0, _MAX_DURATION_S)
        _require(isinstance(self.unavailable_utc, list), f"{where}: unavailable_utc must be a list of windows")
        for k, item in enumerate(self.unavailable_utc):
            _window(item, where, f"unavailable_utc[{k}]")


@dataclass
class AgilityConfig:
    """How fast the spacecraft slews (decision O-08)."""

    source: str = "controller"  # one of AGILITY_SOURCES
    max_rate_deg_s: float | None = None  # [deg/s] 'limits'
    max_acceleration_deg_s2: float | None = None  # [deg/s^2] 'limits'

    def validate(self, where: str) -> None:
        where = f"{where}: agility"
        _require(self.source in AGILITY_SOURCES, f"{where}: source {self.source!r} must be one of {AGILITY_SOURCES}")
        if self.source == "limits":
            _range(self.max_rate_deg_s, where, "max_rate_deg_s", 0.0, 90.0, closed_low=False, optional=False)
            _range(self.max_acceleration_deg_s2, where, "max_acceleration_deg_s2", 0.0, 90.0, closed_low=False,
                   optional=False)
        else:
            _require(self.max_rate_deg_s is None and self.max_acceleration_deg_s2 is None,
                     f"{where}: max_rate_deg_s and max_acceleration_deg_s2 are for source 'limits'")


@dataclass
class ContingencyConfig:
    """Rules the executor applies while flying the plan (Phase 3)."""

    safe_mode_soc: float | None = None  # [-] below it: Sun pointing, instruments off
    recover_soc: float | None = None  # [-] back to the plan above it
    memory_fraction: float | None = None  # [-] above it: acquisitions of priority drop_priority or lower are dropped
    drop_priority: int | None = None

    def validate(self, where: str) -> None:
        where = f"{where}: contingency"
        _range(self.safe_mode_soc, where, "safe_mode_soc", 0.0, 1.0, closed_low=False)
        _range(self.recover_soc, where, "recover_soc", 0.0, 1.0, closed_low=False)
        _require((self.safe_mode_soc is None) == (self.recover_soc is None),
                 f"{where}: give safe_mode_soc and recover_soc together")
        if self.safe_mode_soc is not None:
            _require(self.recover_soc > self.safe_mode_soc, f"{where}: recover_soc must be above safe_mode_soc")
        _range(self.memory_fraction, where, "memory_fraction", 0.0, 1.0, closed_low=False)
        _require((self.memory_fraction is None) == (self.drop_priority is None),
                 f"{where}: give memory_fraction and drop_priority together")
        if self.drop_priority is not None:
            _require(isinstance(self.drop_priority, int) and not isinstance(self.drop_priority, bool)
                     and 1 <= self.drop_priority <= 99, f"{where}: drop_priority must be a whole number from 1 to 99")


@dataclass
class SpacecraftPlanningConfig:
    """A spacecraft's planning settings."""

    spacecraft: str
    default_pointing: str = "sun"  # outside activities; 'sun' or 'nadir' (tool convention: Sun pointing)
    contact_activity: str = ""  # the contact type used on its passes; "" for none
    contact_priority: int = 1  # stations shared: the lower number wins a contested pass
    agility: AgilityConfig = field(default_factory=AgilityConfig)
    min_soc: float | None = None  # [-] the battery's lowest planned state of charge
    max_activities_per_orbit: int | None = None
    max_activities_per_day: int | None = None
    max_contact_s_per_day: float | None = None  # [s]
    exclusions_utc: list = field(default_factory=list)  # [[start, end], ...] nothing may be planned
    star_tracker_exclusion: bool = False  # keep one star tracker clear of the Sun, Earth and Moon
    detector: DetectorConfig | None = None
    contingency: ContingencyConfig = field(default_factory=ContingencyConfig)

    def validate(self, where: str) -> None:
        where = f"{where}: spacecraft {self.spacecraft!r}"
        _require(self.default_pointing in ("sun", "nadir"),
                 f"{where}: default_pointing must be 'sun' or 'nadir'")
        _require(isinstance(self.contact_priority, int) and not isinstance(self.contact_priority, bool)
                 and 1 <= self.contact_priority <= 99, f"{where}: contact_priority must be a whole number from 1 to 99")
        _require(isinstance(self.agility, AgilityConfig), f"{where}: agility must be an object")
        self.agility.validate(where)
        _range(self.min_soc, where, "min_soc", 0.0, 1.0)
        for name in ("max_activities_per_orbit", "max_activities_per_day"):
            value = getattr(self, name)
            _require(value is None or (isinstance(value, int) and not isinstance(value, bool) and value >= 1),
                     f"{where}: {name} must be a whole number of at least 1")
        _range(self.max_contact_s_per_day, where, "max_contact_s_per_day", 0.0, 86400.0, closed_low=False)
        _require(isinstance(self.exclusions_utc, list), f"{where}: exclusions_utc must be a list of windows")
        for k, item in enumerate(self.exclusions_utc):
            _window(item, where, f"exclusions_utc[{k}]")
        _require(isinstance(self.star_tracker_exclusion, bool), f"{where}: star_tracker_exclusion must be true or "
                                                                "false")
        if self.detector is not None:
            _require(isinstance(self.detector, DetectorConfig), f"{where}: detector must be an object")
            self.detector.validate(where)
        _require(isinstance(self.contingency, ContingencyConfig), f"{where}: contingency must be an object")
        self.contingency.validate(where)


@dataclass
class SchedulerConfig:
    """The scheduler's settings (decisions O-10, O-11). The weights are
    tool conventions: off-nadir 1, the others 0."""

    seed: int = 0
    improvement_iterations: int = 0
    objective: str = "lexicographic"  # one of OBJECTIVES
    weights: dict = field(default_factory=lambda: {"off_nadir": 1.0, "gsd": 0.0, "early": 0.0, "slew": 0.0})
    priority_weights: dict = field(default_factory=dict)  # 'weighted': {"1": 100.0, "2": 10.0, ...}

    def validate(self, where: str) -> None:
        where = f"{where}: scheduler"
        _require(isinstance(self.seed, int) and not isinstance(self.seed, bool) and 0 <= self.seed < 2 ** 32,
                 f"{where}: seed must be a whole number in [0, 2^32)")
        _require(isinstance(self.improvement_iterations, int) and not isinstance(self.improvement_iterations, bool)
                 and 0 <= self.improvement_iterations <= 100000,
                 f"{where}: improvement_iterations must be a whole number from 0 to 100000")
        _require(self.objective in OBJECTIVES, f"{where}: objective {self.objective!r} must be one of {OBJECTIVES}")
        known = {"off_nadir", "gsd", "early", "slew"}
        _require(isinstance(self.weights, dict) and set(self.weights) <= known
                 and all(_number(v) and v >= 0.0 for v in self.weights.values()),
                 f"{where}: weights must map {sorted(known)} to numbers of at least 0")
        _require(isinstance(self.priority_weights, dict)
                 and all(isinstance(k, str) and k.isdigit() and _number(v) and v >= 0.0
                         for k, v in self.priority_weights.items()),
                 f"{where}: priority_weights must map priorities (\"1\", \"2\", ...) to numbers of at least 0")
        if self.objective == "weighted":
            _require(bool(self.priority_weights), f"{where}: objective 'weighted' needs priority_weights")

    def weight(self, name: str) -> float:
        return float(self.weights.get(name, {"off_nadir": 1.0}.get(name, 0.0)))


@dataclass
class LockedActivityConfig:
    """An activity fixed by the user: kept as it is when the plan is made
    again."""

    id: str
    spacecraft: str
    activity: str
    start_utc: str
    end_utc: str
    target: str = ""
    station: str = ""
    request: str = ""

    def validate(self, where: str) -> None:
        _name(self.id, where, "locked activity")
        where = f"{where}: locked activity {self.id!r}"
        _window([self.start_utc, self.end_utc], where, "start_utc/end_utc")


@dataclass
class WhatIfConfig:
    """An event applied to a copy of the inputs (Phase 3): a lost pass
    (the pass of ``station`` and ``spacecraft`` in force at ``at_utc``), a
    station outage or an instrument outage over [``at_utc``,
    ``until_utc``], an extra request (enables the disabled target or
    request ``name``), a delayed maneuver (request ``name`` by
    ``delay_s``)."""

    kind: str  # one of WHAT_IF_KINDS
    at_utc: str | None = None
    until_utc: str | None = None
    station: str = ""
    spacecraft: str = ""
    instrument: str = ""
    name: str = ""
    delay_s: float | None = None  # [s]

    def validate(self, where: str) -> None:
        _require(self.kind in WHAT_IF_KINDS, f"{where}: what_if kind {self.kind!r} must be one of {WHAT_IF_KINDS}")
        where = f"{where}: what_if {self.kind!r}"
        if self.at_utc is not None:
            utc(self.at_utc, where, "at_utc")
        if self.until_utc is not None:
            utc(self.until_utc, where, "until_utc")
        need = {"lost_pass": ("at_utc", "station", "spacecraft"),
                "station_outage": ("at_utc", "until_utc", "station"),
                "instrument_outage": ("at_utc", "until_utc", "spacecraft", "instrument"),
                "extra_request": ("name",), "delayed_maneuver": ("name", "delay_s")}[self.kind]
        for name in need:
            _require(getattr(self, name) not in (None, ""), f"{where}: needs {name}")
        if self.at_utc is not None and self.until_utc is not None:
            _window([self.at_utc, self.until_utc], where, "at_utc/until_utc")
        _range(self.delay_s, where, "delay_s", -_MAX_DURATION_S, _MAX_DURATION_S)


@dataclass
class VerificationConfig:
    """Tolerances of the plan-versus-simulation check (decision O-19);
    tool conventions."""

    soc_points: float = 5.0  # [percentage points]
    memory_fraction: float = 0.02  # [-] of the capacity
    off_nadir_deg: float = 1.0  # [deg]
    sun_elevation_deg: float = 0.5  # [deg]

    def validate(self, where: str) -> None:
        where = f"{where}: verification"
        _range(self.soc_points, where, "soc_points", 0.0, 100.0, closed_low=False)
        _range(self.memory_fraction, where, "memory_fraction", 0.0, 1.0, closed_low=False)
        _range(self.off_nadir_deg, where, "off_nadir_deg", 0.0, 90.0, closed_low=False)
        _range(self.sun_elevation_deg, where, "sun_elevation_deg", 0.0, 90.0, closed_low=False)


@dataclass
class OperationsConfig:
    """The scenario's operations planning inputs (module docstring)."""

    horizon: HorizonConfig
    version: int = OPERATIONS_VERSION
    geometry: GeometryConfig = field(default_factory=GeometryConfig)
    targets: list = field(default_factory=list)  # list[TargetConfig]
    activity_types: list = field(default_factory=list)  # list[ActivityTypeConfig]
    requests: list = field(default_factory=list)  # list[RequestConfig]
    stations: list = field(default_factory=list)  # list[StationPlanningConfig]
    spacecraft: list = field(default_factory=list)  # list[SpacecraftPlanningConfig]
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    locked: list = field(default_factory=list)  # list[LockedActivityConfig]
    what_if: list = field(default_factory=list)  # list[WhatIfConfig]
    verification: VerificationConfig = field(default_factory=VerificationConfig)

    def activity_type(self, name: str) -> ActivityTypeConfig | None:
        return next((a for a in self.activity_types if a.name == name), None)

    def planned(self, name: str) -> SpacecraftPlanningConfig | None:
        return next((s for s in self.spacecraft if s.spacecraft == name), None)

    def station(self, name: str) -> StationPlanningConfig | None:
        return next((s for s in self.stations if s.station == name), None)

    def horizon_utc(self) -> tuple[datetime, datetime]:
        return (utc(self.horizon.start_utc, "operations.horizon", "start_utc"),
                utc(self.horizon.end_utc, "operations.horizon", "end_utc"))

    def validate(self, scenario) -> None:
        """Check the section against the scenario: every name it uses
        exists, every window lies in the horizon."""
        where = "operations"
        _require(self.version == OPERATIONS_VERSION,
                 f"{where}: version {self.version!r} is not one this version reads (it reads {OPERATIONS_VERSION})")
        _require(isinstance(self.horizon, HorizonConfig), f"{where}: horizon must be an object")
        start, end = _window([self.horizon.start_utc, self.horizon.end_utc], f"{where}: horizon", "start/end")
        epoch = utc(scenario.epoch_utc, "scenario", "epoch_utc")
        _require(start >= epoch, f"{where}: horizon starts before the scenario's epoch ({scenario.epoch_utc})")
        _require((end - start).total_seconds() <= MAX_HORIZON_DAYS * 86400.0,
                 f"{where}: horizon is longer than {MAX_HORIZON_DAYS:g} days, the most one run can fly")
        _require(scenario.gravity.central_body == "earth", f"{where}: operations planning is for Earth orbits")
        _require(isinstance(self.geometry, GeometryConfig), f"{where}: geometry must be an object")
        self.geometry.validate(f"{where}: geometry")
        spacecraft = {sc.name: sc for sc in scenario.spacecraft}
        stations = {gs.name for gs in scenario.ground_stations}
        for group, key in (("targets", "name"), ("activity_types", "name"), ("requests", "name"),
                           ("stations", "station"), ("spacecraft", "spacecraft"), ("locked", "id")):
            items = getattr(self, group)
            _require(isinstance(items, list), f"{where}: {group} must be a list")
            for item in items:
                item.validate(where)
            names = [getattr(item, key) for item in items]
            repeated = sorted({n for n in names if names.count(n) > 1})
            _require(not repeated, f"{where}: {group} must be unique ({', '.join(map(str, repeated))} repeated)")
        types = {a.name: a for a in self.activity_types}
        for planned in self.spacecraft:
            sc = spacecraft.get(planned.spacecraft)
            _require(sc is not None, f"{where}: spacecraft {planned.spacecraft!r} is not in the scenario")
            if planned.contact_activity:
                kind = types.get(planned.contact_activity)
                _require(kind is not None and kind.kind == "contact",
                         f"{where}: spacecraft {planned.spacecraft!r}: contact_activity "
                         f"{planned.contact_activity!r} is not a contact activity type")
                _require(sc.rf_link is not None, f"{where}: spacecraft {planned.spacecraft!r} has contacts but no "
                                                 "rf_link")
            _require(planned.min_soc is None or sc.power is not None,
                     f"{where}: spacecraft {planned.spacecraft!r}: min_soc needs a power budget")
            _require(planned.agility.source != "controller" or sc.fsw_mode is not None,
                     f"{where}: spacecraft {planned.spacecraft!r}: agility 'controller' needs fsw_mode (attitude "
                     "control); use source 'limits'")
            _require(sc.comms_pointing is None, f"{where}: spacecraft {planned.spacecraft!r} has comms_pointing; a "
                                                "planned spacecraft points by its plan (remove comms_pointing)")
            for k, item in enumerate(planned.exclusions_utc):
                self._inside(item, f"{where}: spacecraft {planned.spacecraft!r}: exclusions_utc[{k}]", start, end)
            contingency = planned.contingency
            if contingency.safe_mode_soc is not None:
                _require(sc.power is not None, f"{where}: spacecraft {planned.spacecraft!r}: contingency "
                                               "safe_mode_soc needs a power budget")
            if contingency.memory_fraction is not None:
                _require(sc.data_handling is not None, f"{where}: spacecraft {planned.spacecraft!r}: contingency "
                                                       "memory_fraction needs data handling")
        _require(bool(self.spacecraft), f"{where}: name at least one spacecraft to plan for in 'spacecraft'")
        planned_names = {p.spacecraft for p in self.spacecraft}
        for item in self.stations:
            _require(item.station in stations, f"{where}: station {item.station!r} is not a ground station of the "
                                               "scenario")
            for k, window in enumerate(item.unavailable_utc):
                self._inside(window, f"{where}: station {item.station!r}: unavailable_utc[{k}]", start, end)
        for kind in self.activity_types:
            self._check_devices(kind, [spacecraft[p] for p in planned_names], where)
        for target in self.targets:
            kind = types.get(target.activity)
            _require(kind is not None and kind.kind == "acquisition",
                     f"{where}: target {target.name!r}: activity {target.activity!r} is not an acquisition type")
            for name in target.spacecraft:
                _require(name in planned_names, f"{where}: target {target.name!r}: spacecraft {name!r} is not planned")
            if target.valid_utc is not None:
                self._inside(target.valid_utc, f"{where}: target {target.name!r}: valid_utc", start, end)
            if target.kind == "polygon":
                _require(kind.equipment or any(p.detector is not None and p.detector.field_of_view_deg is not None
                                               for p in self.spacecraft),
                         f"{where}: target {target.name!r}: a polygon's coverage needs the imager's field of view "
                         "(the activity's equipment, or a detector's field_of_view_deg)")
        for request in self.requests:
            kind = types.get(request.activity)
            _require(kind is not None and kind.kind != "acquisition" and kind.kind != "contact",
                     f"{where}: request {request.name!r}: activity {request.activity!r} must be a calibration, "
                     "momentum management, maneuver or user type (targets ask for acquisitions, passes for contacts)")
            _require(request.spacecraft in planned_names,
                     f"{where}: request {request.name!r}: spacecraft {request.spacecraft!r} is not planned")
            if request.window_utc is not None:
                self._inside(request.window_utc, f"{where}: request {request.name!r}: window_utc", start, end)
            if request.at_utc is not None:
                moment = utc(request.at_utc, where, "at_utc")
                _require(start <= moment <= end, f"{where}: request {request.name!r}: at_utc is outside the horizon")
            if kind.kind == "maneuver":
                _require(request.at_utc is not None, f"{where}: request {request.name!r}: a maneuver needs at_utc")
        for item in self.locked:
            _require(item.spacecraft in planned_names,
                     f"{where}: locked activity {item.id!r}: spacecraft {item.spacecraft!r} is not planned")
            _require(item.activity in types, f"{where}: locked activity {item.id!r}: activity type "
                                             f"{item.activity!r} does not exist")
            _require(not item.station or item.station in stations,
                     f"{where}: locked activity {item.id!r}: station {item.station!r} does not exist")
            _require(not item.target or any(t.name == item.target for t in self.targets),
                     f"{where}: locked activity {item.id!r}: target {item.target!r} does not exist")
            self._inside([item.start_utc, item.end_utc], f"{where}: locked activity {item.id!r}", start, end)
        names = {t.name for t in self.targets} | {r.name for r in self.requests}
        for k, event in enumerate(self.what_if):
            event.validate(f"{where}: what_if[{k}]")
            _require(not event.station or event.station in stations,
                     f"{where}: what_if[{k}]: station {event.station!r} does not exist")
            _require(not event.spacecraft or event.spacecraft in planned_names,
                     f"{where}: what_if[{k}]: spacecraft {event.spacecraft!r} is not planned")
            _require(not event.name or event.name in names,
                     f"{where}: what_if[{k}]: {event.name!r} is not a target or request")
        _require(isinstance(self.scheduler, SchedulerConfig), f"{where}: scheduler must be an object")
        self.scheduler.validate(where)
        _require(isinstance(self.verification, VerificationConfig), f"{where}: verification must be an object")
        self.verification.validate(where)

    @staticmethod
    def _inside(window, where: str, start: datetime, end: datetime) -> None:
        first, last = _window(window, where, "window")
        _require(start <= first and last <= end, f"{where}: the window is outside the horizon")

    @staticmethod
    def _check_devices(kind: ActivityTypeConfig, spacecraft: list, where: str) -> None:
        """The activity's instruments, equipment and transmitter exist on
        every planned spacecraft that could fly it."""
        from ..model3d.equipment import mounted_items

        for sc in spacecraft:
            here = f"{where}: activity type {kind.name!r} on {sc.name!r}"
            handling = sc.data_handling
            instruments = {i.name for i in handling.instruments} if handling is not None else set()
            for name in kind.instruments:
                _require(name in instruments, f"{here}: instrument {name!r} is not in its data_handling")
            if kind.transmitter:
                _require(handling is not None and sc.rf_link is not None,
                         f"{here}: the transmitter needs data_handling and rf_link")
            if kind.equipment:
                items = {item.name for item in mounted_items(sc) if item.boresight_b is not None}
                _require(kind.equipment in items, f"{here}: equipment {kind.equipment!r} is not mounted equipment "
                                                  "with a boresight")


_LISTS = (("targets", TargetConfig), ("activity_types", ActivityTypeConfig), ("requests", RequestConfig),
          ("stations", StationPlanningConfig), ("locked", LockedActivityConfig), ("what_if", WhatIfConfig))


def from_dict(data, where: str, record, records, fields_of) -> OperationsConfig:
    """The section read from its JSON object, with the scenario loader's
    record builders (so every structural error reads the same)."""
    data = fields_of(data, where)
    for name, cls in _LISTS:
        data[name] = records(cls, data.pop(name, []), f"{where}.{name}")
    planned = []
    items = data.pop("spacecraft", [])
    if not isinstance(items, list):
        from .scenario import _StructureError

        raise _StructureError(f"{where}.spacecraft must be a list ([...])")
    for k, item in enumerate(items):
        here = f"{where}.spacecraft[{k}]"
        item = fields_of(item, here)
        item["agility"] = record(AgilityConfig, item.get("agility") or {}, f"{here}.agility")
        item["contingency"] = record(ContingencyConfig, item.get("contingency") or {}, f"{here}.contingency")
        if item.get("detector") is not None:
            item["detector"] = record(DetectorConfig, item["detector"], f"{here}.detector")
        planned.append(record(SpacecraftPlanningConfig, item, here))
    data["spacecraft"] = planned
    if "horizon" not in data:
        from .scenario import _StructureError

        raise _StructureError(f"{where}: missing field 'horizon'")
    data["horizon"] = record(HorizonConfig, data["horizon"], f"{where}.horizon")
    for name, cls in (("geometry", GeometryConfig), ("scheduler", SchedulerConfig),
                      ("verification", VerificationConfig)):
        data[name] = record(cls, data[name], f"{where}.{name}") if data.get(name) is not None else cls()
    return record(OperationsConfig, data, where)


def _drop_defaults(item: dict, defaults: dict) -> dict:
    return {k: v for k, v in item.items() if v is not None and not (k in defaults and v == defaults[k])}


def compact(section: dict) -> dict:
    """The saved form of a section (``dataclasses.asdict``): values left at
    their defaults, None values and empty lists left out."""
    out: dict = {"version": section["version"], "horizon": section["horizon"]}
    for name in ("geometry", "scheduler", "verification"):
        cls = {"geometry": GeometryConfig, "scheduler": SchedulerConfig, "verification": VerificationConfig}[name]
        changed = _drop_defaults(section[name], cls().__dict__)
        if changed:
            out[name] = changed
    list_defaults = {"targets": {"kind": "point", "altitude_m": 0.0, "acquisitions": 1, "spacecraft": [],
                                 "enabled": True},
                     "activity_types": {"setup_s": 0.0, "teardown_s": 0.0, "equipment": "", "instruments": [],
                                        "transmitter": False, "power_w": 0.0, "frame": "vnb"},
                     "requests": {"count": 1, "per": "horizon", "enabled": True},
                     "stations": {"azimuth_mask": [], "capacity": 1, "setup_s": 0.0, "handover_s": 0.0,
                                  "unavailable_utc": []},
                     "locked": {"target": "", "station": "", "request": ""},
                     "what_if": {"station": "", "spacecraft": "", "instrument": "", "name": ""}}
    for name in ("targets", "activity_types", "requests", "stations", "spacecraft", "locked", "what_if"):
        items = []
        for item in section.get(name, []):
            if name == "spacecraft":
                item = dict(item)
                defaults = SpacecraftPlanningConfig(spacecraft="").__dict__
                agility = _drop_defaults(item.pop("agility"), AgilityConfig().__dict__)
                contingency = _drop_defaults(item.pop("contingency"), {})
                detector = item.pop("detector")
                item = _drop_defaults(item, {k: v for k, v in defaults.items()
                                             if k not in ("agility", "contingency", "detector", "spacecraft")})
                if agility:
                    item["agility"] = agility
                if contingency:
                    item["contingency"] = contingency
                if detector is not None:
                    item["detector"] = _drop_defaults(detector, {})
            else:
                item = _drop_defaults(item, list_defaults[name])
            items.append(item)
        if items:
            out[name] = items
    return out


class _Slot:
    """A place in the section that holds a name: an attribute, or a list's item."""

    def __init__(self, owner, key):
        self.owner, self.key = owner, key

    def get(self):
        return self.owner[self.key] if isinstance(self.owner, list) else getattr(self.owner, self.key)

    def set(self, value) -> None:
        if isinstance(self.owner, list):
            self.owner[self.key] = value
        else:
            setattr(self.owner, self.key, value)


def _name_sites(section: OperationsConfig, kind: str):
    """``(path, slot)`` of every place that names a spacecraft (``kind``
    "spacecraft") or a ground station ("ground_station")."""
    sites = []
    if kind == "spacecraft":
        for k, item in enumerate(section.spacecraft):
            sites.append((f"operations.spacecraft[{k}].spacecraft", _Slot(item, "spacecraft")))
        for item in section.targets:
            for k in range(len(item.spacecraft)):
                sites.append((f"operations.targets {item.name!r}.spacecraft[{k}]", _Slot(item.spacecraft, k)))
        for item in section.requests:
            sites.append((f"operations.requests {item.name!r}.spacecraft", _Slot(item, "spacecraft")))
        groups = (("locked", "spacecraft"), ("what_if", "spacecraft"))
    else:
        for k, item in enumerate(section.stations):
            sites.append((f"operations.stations[{k}].station", _Slot(item, "station")))
        groups = (("locked", "station"), ("what_if", "station"))
    for group, attribute in groups:
        for k, item in enumerate(getattr(section, group)):
            sites.append((f"operations.{group}[{k}].{attribute}", _Slot(item, attribute)))
    return sites


def references(section: OperationsConfig | None, kind: str, name: str) -> list[str]:
    """The paths in the section that name ``name``."""
    if section is None:
        return []
    return [path for path, slot in _name_sites(section, kind) if slot.get() == name]


def rename(section: OperationsConfig | None, kind: str, old_name: str, new_name: str) -> int:
    """Rename a spacecraft or a ground station everywhere in the section;
    returns how many places changed."""
    if section is None:
        return 0
    changed = 0
    for _path, slot in _name_sites(section, kind):
        if slot.get() == old_name:
            slot.set(new_name)
            changed += 1
    return changed
