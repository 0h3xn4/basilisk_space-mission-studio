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
"""The scheduler (design 2.7, decisions O-10 to O-13).

Constructive and deterministic:

1. locked activities, then requests at a fixed time (maneuvers);
2. contacts: passes in time order; spacecraft wanting overlapping passes
   of one station are served by contact priority, then the least contact
   time so far, then name (O-12); a contact takes the pass after the
   station's setup and handover;
3. every other request (each acquisition a target wants, each occurrence
   of a request) by priority, then fewest chances, then earliest deadline,
   then name; its chances in order of quality; the first that keeps every
   hard constraint is taken.

Each insertion is checked against the spacecraft's other activities and
the slews between them, the stations' capacity, the exclusion windows and
outages, the per-orbit and per-day limits, the star trackers' exclusion
angles, and the energy and memory profiles (incrementally, from the
insertion until the profile meets the one before it). A chance that
fails records the first constraint it breaks; an unplaced request reports
the most frequent (O-13).

Then, optionally, a seeded large-neighbourhood search: remove one to
three activities at random, insert the unplaced requests again (then the
removed ones), keep the result when the score improves.
"""

from __future__ import annotations

import bisect
import copy
import math
from collections import Counter
from dataclasses import dataclass, field

import numpy as np

from . import attitude as attitude_model
from .opportunities import Opportunities, Window
from .plan import Activity, Plan, Unscheduled
from .resources import SpacecraftModel, overlap

_EPS = 1e-6  # [s]
_MAX_POSITIONS = 24  # start times tried per window
_REQUEST_STEP_S = 60.0  # [s] start times tried within a request's window, at least


@dataclass
class Request:
    """One thing to place: an acquisition of a target, an occurrence of a
    request, or a fixed-time request."""

    name: str  # target or request name
    kind: str  # activity kind
    type: str  # activity type
    priority: int
    spacecraft: tuple  # who may do it
    windows: list  # list[Window] (targets) or [(spacecraft, start_s, end_s)] (requests)
    occurrence: int = 0
    fixed_s: float | None = None
    deadline_s: float = math.inf
    target: str = ""

    @property
    def label(self) -> str:
        return self.name if self.occurrence == 0 else f"{self.name}#{self.occurrence + 1}"


@dataclass
class Candidate:
    spacecraft: str
    start_s: float
    end_s: float
    quality: float  # higher is better
    window: Window | None = None
    station: str = ""
    pass_: object = None


@dataclass
class _State:
    """One spacecraft's plan and resource arrays during scheduling."""

    model: SpacecraftModel
    activities: list = field(default_factory=list)
    starts: list = field(default_factory=list)  # occupied starts, sorted with activities
    timeline: list = field(default_factory=list)
    cosine: np.ndarray = None
    load: np.ndarray = None
    rate_in: np.ndarray = None
    rate_out: np.ndarray = None
    energy: np.ndarray = None
    memory: np.ndarray = None
    lost: np.ndarray = None  # cumulative [bit]

    def copy(self) -> _State:
        clone = copy.copy(self)
        clone.activities, clone.starts, clone.timeline = list(self.activities), list(self.starts), list(self.timeline)
        for name in ("cosine", "load", "rate_in", "rate_out", "energy", "memory", "lost"):
            setattr(clone, name, getattr(self, name).copy())
        return clone


class Scheduler:
    """Builds a plan from the scenario's ``operations`` section, its
    opportunities and the spacecraft models."""

    def __init__(self, scenario, geometry, opportunities: Opportunities, timebase, slew_models: dict):
        self.scenario, self.geometry, self.opportunities, self.timebase = scenario, geometry, opportunities, timebase
        self.section = scenario.operations
        self.settings = self.section.scheduler
        self.t = geometry.time_s
        self.step = geometry.step_s
        self.start_s, self.end_s = float(self.t[0]), float(self.t[-1])
        spacecraft = {sc.name: sc for sc in scenario.spacecraft}
        self.states = {}
        for planned in self.section.spacecraft:
            sc = spacecraft[planned.spacecraft]
            model = SpacecraftModel(scenario, sc, geometry, self.section, slew_models[sc.name])
            self.states[sc.name] = self._fresh(model)
        self.exclusions = {p.spacecraft: [tuple(timebase.to_sim(m) for m in w) for w in p.exclusions_utc]
                           for p in self.section.spacecraft}
        self.outages = {s.station: [tuple(timebase.to_sim(m) for m in w) for w in s.unavailable_utc]
                        for s in self.section.stations}
        self.instrument_outages: dict = {}
        self.lost_passes: set = set()
        self.station_load: dict = {}  # station -> sorted list of (start, end) busy intervals incl. setup
        self.contention: list = []
        self.reasons: dict = {}
        self._star_trackers: dict = {}
        self._moon = None

    # -- state -------------------------------------------------------------
    def _fresh(self, model: SpacecraftModel) -> _State:
        state = _State(model)
        profile = model.evaluate([], [])
        n = len(self.t)
        state.cosine = model.panel_cosine([], [])
        state.load = profile.load_w.copy()
        state.rate_in = np.zeros(n)
        state.rate_out = np.zeros(n)
        for instrument in model.always_on:
            state.rate_in += instrument.data_rate_bps
        state.energy = profile.energy_wh.copy()
        state.memory, state.lost = self._memory(model, state.rate_in, state.rate_out, None, 0, None)
        return state

    def _memory(self, model, rate_in, rate_out, base: _State | None, k0: int, k1: int | None):
        """Memory and cumulative loss, from sample ``k0`` (with ``base``'s
        values before it), stopping where they meet ``base`` again after
        ``k1``."""
        handling = model.sc.data_handling
        n = len(self.t)
        if handling is None:
            return np.zeros(n), np.zeros(n)
        capacity = handling.storage_capacity_gbit * 1e9  # [bit]
        if base is None:
            memory, lost = np.empty(n), np.empty(n)
            stored = sum(i.initial_data_gbit for i in handling.instruments) * 1e9
            total = 0.0
            start = 0
        else:
            memory, lost = base.memory.copy(), base.lost.copy()
            stored = base.memory[k0 - 1] if k0 > 0 else sum(i.initial_data_gbit for i in handling.instruments) * 1e9
            total = base.lost[k0 - 1] if k0 > 0 else 0.0
            start = k0
        gain, drain = rate_in * self.step, rate_out * self.step
        for k in range(start, n):
            stored += gain[k]
            if stored > capacity:
                total += stored - capacity
                stored = capacity
            stored -= min(stored, drain[k])
            if base is not None and k1 is not None and k > k1 and stored == base.memory[k]:
                lost[k:] = base.lost[k:] + (total - base.lost[k])
                memory[k] = stored
                return memory, lost
            memory[k], lost[k] = stored, total
        return memory, lost

    def _energy(self, model, state: _State, cosine, load, k0: int, k1: int):
        power = model.sc.power
        if power is None:
            return state.energy.copy()
        capacity = power.battery_capacity_wh
        energy = state.energy.copy()
        value = energy[k0 - 1] if k0 > 0 else power.battery_initial_soc * capacity
        generated = model.flux * power.panel_area_m2 * power.panel_efficiency * model.track.sunlight * cosine
        delta = (generated - load) * self.step / 3600.0
        for k in range(k0, len(self.t)):
            value = min(capacity, max(0.0, value + delta[k]))
            if k > k1 and value == state.energy[k]:
                energy[k] = value
                return energy
            energy[k] = value
        return energy

    # -- checks -------------------------------------------------------------
    def _neighbours(self, state: _State, start: float):
        i = bisect.bisect_left(state.starts, start)
        previous = state.activities[i - 1] if i > 0 else None
        following = state.activities[i] if i < len(state.activities) else None
        return i, previous, following

    def _check(self, state: _State, activity: Activity, request: Request | None) -> tuple[str | None, dict]:
        """The first constraint ``activity`` breaks (a REASONS key), or None
        and the new state's pieces."""
        model = state.model
        start, end = activity.occupied
        if start < self.start_s - _EPS or end > self.end_s + _EPS:
            return "conflict", {}
        name = model.sc.name
        for first, last in self.exclusions.get(name, []):
            if start < last and end > first:
                return "exclusion", {}
        kind = self.section.activity_type(activity.type)
        for instrument in kind.instruments:
            for first, last in self.instrument_outages.get((name, instrument), []):
                if activity.start_s < last and activity.end_s > first:
                    return "exclusion", {}
        i, previous, following = self._neighbours(state, start)
        if previous is not None and previous.occupied[1] > start + _EPS:
            return "conflict", {}
        if following is not None and following.occupied[0] < end - _EPS:
            return "conflict", {}
        limit = self._limits(state, activity)
        if limit is not None:
            return limit, {}
        # slews: onto this activity, and from it onto the next
        timeline = self._local_timeline(state, [activity] + ([following] if following is not None else []), i)
        mine = timeline[0]
        if not mine["ok"]:
            return "slew", {}
        if following is not None and not timeline[1]["ok"]:
            return "slew", {}
        if model.settings.star_tracker_exclusion and not self._trackers_clear(model, activity, mine):
            return "star_tracker", {}
        # resources
        pieces = self._resources(state, activity, mine, following, timeline[1] if following is not None else None)
        settings = model.settings
        if model.sc.power is not None and settings.min_soc is not None:
            # below the floor, and lower than it was without this activity, anywhere
            floor = settings.min_soc * model.sc.power.battery_capacity_wh  # [W*h]
            k0 = pieces["k0"]
            new, old = pieces["energy"][k0:], state.energy[k0:]
            if np.any((new < floor - 1e-9) & (new < old - 1e-9)):
                return "battery", {}
        if model.sc.data_handling is not None and pieces["lost"][-1] > state.lost[-1] + 1.0:
            return "memory", {}
        pieces["timeline"] = timeline
        pieces["index"] = i
        return None, pieces

    def _limits(self, state: _State, activity: Activity) -> str | None:
        settings = state.model.settings
        if activity.kind != "contact":
            others = [a for a in state.activities if a.kind != "contact"]
            if settings.max_activities_per_day is not None:
                day = math.floor((activity.start_s - self.start_s) / 86400.0)
                count = sum(1 for a in others if math.floor((a.start_s - self.start_s) / 86400.0) == day)
                if count >= settings.max_activities_per_day:
                    return "per_day"
            if settings.max_activities_per_orbit is not None:
                period = self._period(state.model)
                orbit = math.floor((activity.start_s - self.start_s) / period)
                count = sum(1 for a in others if math.floor((a.start_s - self.start_s) / period) == orbit)
                if count >= settings.max_activities_per_orbit:
                    return "per_orbit"
        elif settings.max_contact_s_per_day is not None:
            day = math.floor((activity.start_s - self.start_s) / 86400.0)
            used = sum(a.duration_s for a in state.activities
                       if a.kind == "contact" and math.floor((a.start_s - self.start_s) / 86400.0) == day)
            if used + activity.duration_s > settings.max_contact_s_per_day + _EPS:
                return "per_day"
        return None

    def _period(self, model: SpacecraftModel) -> float:
        r = float(np.mean(np.linalg.norm(model.track.position_n, axis=1)))
        from .. import constants

        return 2.0 * math.pi * math.sqrt(r ** 3 / constants.EARTH_GM_M3_S2)  # [s]

    def _local_timeline(self, state: _State, activities: list, index: int) -> list:
        """The timeline entries of ``activities`` (consecutive), placed at
        ``index`` in the spacecraft's list: after the activity before
        them, as it is cached."""
        if index > 0:
            prior = state.activities[index - 1]
            after = {"end_attitude": state.timeline[index - 1]["end_attitude"], "free_from": prior.occupied[1]}
            return state.model.timeline(activities, after)
        return state.model.timeline(activities)

    def _resources(self, state: _State, activity: Activity, entry: dict, following, following_entry) -> dict:
        model = state.model
        k0 = model.index(entry["point_from_s"])
        k1 = model.index(activity.occupied[1])
        cosine, load = state.cosine.copy(), state.load.copy()
        rate_in, rate_out = state.rate_in.copy(), state.rate_out.copy()
        segment = model.panel_cosine([activity], [entry])
        cosine[k0:k1 + 1] = segment[k0:k1 + 1]
        if following is not None and following_entry is not None:
            old = state.timeline[state.activities.index(following)]
            f0 = min(model.index(old["point_from_s"]), model.index(following_entry["point_from_s"]))
            f1 = model.index(following.occupied[1])
            base = model.panel_cosine([], [])
            cosine[k1 + 1:f0] = base[k1 + 1:f0]
            seg = model.panel_cosine([following], [following_entry])
            g0 = model.index(following_entry["point_from_s"])
            cosine[f0:g0] = base[f0:g0]
            cosine[g0:f1 + 1] = seg[g0:f1 + 1]
            k1 = max(k1, f1)
        kind = self.section.activity_type(activity.type)
        share = overlap(self.t, self.step, activity.start_s, activity.end_s)
        load += share * kind.power_w
        for name in kind.instruments:
            instrument = model.instruments[name]
            rate_in += share * instrument.data_rate_bps
            load += share * instrument.power_w
        handling, rf = model.sc.data_handling, model.sc.rf_link
        if kind.transmitter and handling is not None and rf is not None:
            load += share * handling.transmitter_power_w
            rate_out += model.link_fraction(activity, activity.start_s, activity.end_s) * rf.data_rate_bps
        energy = self._energy(model, state, cosine, load, k0, k1)
        memory, lost = self._memory(model, rate_in, rate_out, state, model.index(activity.start_s), k1)
        return {"k0": k0, "cosine": cosine, "load": load, "rate_in": rate_in, "rate_out": rate_out,
                "energy": energy, "memory": memory, "lost": lost}

    def _commit(self, state: _State, activity: Activity, pieces: dict) -> None:
        i = pieces["index"]
        state.activities.insert(i, activity)
        state.starts.insert(i, activity.occupied[0])
        timeline = pieces["timeline"]
        state.timeline.insert(i, timeline[0])
        if i + 1 < len(state.activities):
            state.timeline[i + 1] = timeline[1]
        for name in ("cosine", "load", "rate_in", "rate_out", "energy", "memory", "lost"):
            setattr(state, name, pieces[name])
        if activity.station:
            setup = self._station_setup(activity.station)
            bisect.insort(self.station_load.setdefault(activity.station, []),
                          (activity.start_s - setup, activity.end_s, activity.spacecraft))

    def _station_setup(self, station: str) -> float:
        settings = self.section.station(station)
        return settings.setup_s if settings is not None else 0.0

    def _station_free(self, station: str, start: float, end: float) -> bool:
        """Capacity left at ``station`` over [start, end] (with its setup and
        the handover after other contacts)."""
        settings = self.section.station(station)
        capacity = settings.capacity if settings is not None else 1
        handover = settings.handover_s if settings is not None else 0.0
        for first, last in self.outages.get(station, []):
            if start < last and end > first:
                return False
        busy = [(a, b + handover) for a, b, _sc in self.station_load.get(station, []) if a < end and b + handover > start]
        if len(busy) < capacity:
            return True
        points = sorted({start} | {a for a, _b in busy if a > start})
        return all(sum(1 for a, b in busy if a <= p < b) < capacity for p in points if p < end)

    def _trackers_clear(self, model: SpacecraftModel, activity: Activity, entry: dict) -> bool:
        """At the activity's start, middle and end, at least one star tracker
        with exclusion angles is clear of the Sun, the Earth (with its
        atmosphere) and the Moon."""
        trackers = self._trackers(model)
        if not trackers:
            return True
        from .. import constants

        attitude = entry["start_attitude"]
        kind = self.section.activity_type(activity.type)
        aim = model.aim(activity)
        for t in (activity.start_s, 0.5 * (activity.start_s + activity.end_s), activity.end_s):
            k = model.index(t)
            if aim is not None:
                attitude = attitude_model.point_axis(attitude, model.boresight(kind), aim[k])
            r = model.track.position_n[k]
            earth = -r / np.linalg.norm(r)
            moon = self._moon_n(k) - r
            moon /= np.linalg.norm(moon)
            if not any(self._tracker_clear(item, attitude, model.sun_unit[k], earth, moon, np.linalg.norm(r),
                                           constants.EARTH_EQUATORIAL_RADIUS_M) for item in trackers):
                return False
        return True

    @staticmethod
    def _tracker_clear(item, dcm_bn, sun, earth, moon, radius_m, earth_radius_m) -> bool:
        boresight = dcm_bn.T @ item.boresight_b

        def angle(direction):
            return math.degrees(math.acos(min(1.0, max(-1.0, float(np.dot(boresight, direction))))))

        if item.exclusion_sun_deg is not None and angle(sun) < item.exclusion_sun_deg:
            return False
        if item.exclusion_earth_deg is not None:
            limb = math.degrees(math.asin(min(1.0, (earth_radius_m + 1e3 * (item.earth_atmosphere_km or 0.0))
                                              / radius_m)))
            if angle(earth) < item.exclusion_earth_deg + limb:
                return False
        if item.exclusion_moon_deg is not None and angle(moon) < item.exclusion_moon_deg:
            return False
        return True

    def _trackers(self, model):
        if model.sc.name not in self._star_trackers:
            from ..model3d.equipment import mounted_items

            self._star_trackers[model.sc.name] = [m for m in mounted_items(model.sc)
                                                  if m.kind == "star_tracker" and m.has_exclusions
                                                  and m.boresight_b is not None]
        return self._star_trackers[model.sc.name]

    def _moon_n(self, k: int) -> np.ndarray:
        if self._moon is None:
            import erfa

            from ..engine import time_system

            seconds = time_system.tdb_seconds_past_j2000(self.scenario.epoch_utc) + self.t
            pv = erfa.moon98(np.full(len(self.t), 2451545.0), seconds / 86400.0)
            position = np.asarray(pv["p"] if getattr(pv, "dtype", None) is not None and pv.dtype.names
                                  else pv[:, 0], dtype=float) * erfa.DAU
            # moon98 gives GCRS (mean equator and equinox of J2000 to within the frame bias)
            self._moon = position
        return self._moon[k]

    # -- requests -----------------------------------------------------------
    def requests(self) -> list[Request]:
        """Every request the section makes, as placeable items (module
        docstring order is applied by :meth:`run`)."""
        section = self.section
        planned = [p.spacecraft for p in section.spacecraft]
        out = []
        for target in section.targets:
            if not target.enabled:
                continue
            kind = section.activity_type(target.activity)
            windows = self.opportunities.windows_of(target.name)
            for occurrence in range(target.acquisitions):
                out.append(Request(target.name, kind.kind, kind.name, target.priority,
                                   tuple(target.spacecraft or planned), windows, occurrence,
                                   deadline_s=max((w.end_s for w in windows), default=math.inf), target=target.name))
        for request in section.requests:
            if not request.enabled:
                continue
            kind = section.activity_type(request.activity)
            if request.at_utc is not None:
                at = self.timebase.to_sim(request.at_utc) + self._delays.get(request.name, 0.0)
                out.append(Request(request.name, kind.kind, kind.name, request.priority, (request.spacecraft,),
                                   [(request.spacecraft, at, at + kind.duration_s)], fixed_s=at, deadline_s=at))
                continue
            first, last = self.start_s, self.end_s
            if request.window_utc is not None:
                first, last = (self.timebase.to_sim(m) for m in request.window_utc)
            spans = [(first, last)]
            if request.per == "day":
                spans = [(max(first, self.start_s + d * 86400.0), min(last, self.start_s + (d + 1) * 86400.0))
                         for d in range(int(math.ceil((self.end_s - self.start_s) / 86400.0 - 1e-9)))]
            elif request.per == "orbit":
                period = self._period(self.states[request.spacecraft].model)
                spans = [(max(first, self.start_s + j * period), min(last, self.start_s + (j + 1) * period))
                         for j in range(int(math.ceil((self.end_s - self.start_s) / period - 1e-9)))]
            index = 0
            for a, b in spans:
                if b - a < kind.duration_s:
                    continue
                for _ in range(request.count):
                    out.append(Request(request.name, kind.kind, kind.name, request.priority, (request.spacecraft,),
                                       [(request.spacecraft, a, b)], occurrence=index, deadline_s=b))
                    index += 1
        return out

    _delays: dict = {}

    def candidates(self, request: Request) -> list[Candidate]:
        """Every placement worth trying, best first."""
        kind = self.section.activity_type(request.type)
        out = []
        if request.target:
            weights = self.settings
            target = next(t for t in self.section.targets if t.name == request.target)
            for window in request.windows:
                if window.spacecraft not in request.spacecraft or window.spacecraft not in self.states:
                    continue
                duration = kind.duration_s
                if window.end_s - window.start_s < duration - _EPS:
                    out.append(Candidate(window.spacecraft, window.start_s, window.start_s, -math.inf, window))
                    continue
                if target.kind == "polygon" and target.min_coverage is not None and window.coverage is not None:
                    if float(np.max(window.coverage)) < target.min_coverage:
                        continue
                latest = window.end_s - duration
                best = min(max(window.best_s - duration / 2.0, window.start_s), latest)
                count = max(1, min(_MAX_POSITIONS, int((latest - window.start_s) / self.step) + 1))
                positions = sorted(set([best, window.start_s, latest]
                                       + list(np.linspace(window.start_s, latest, count))),
                                   key=lambda s: abs(s - best))
                for start in positions:
                    middle = start + duration / 2.0
                    quality = -weights.weight("off_nadir") * window.at(middle, "off_nadir_deg") / target.max_off_nadir_deg
                    if window.gsd_m is not None:
                        quality -= weights.weight("gsd") * window.at(middle, "gsd_m") / float(np.max(window.gsd_m))
                    quality -= weights.weight("early") * (start - self.start_s) / (self.end_s - self.start_s)
                    out.append(Candidate(window.spacecraft, start, start + duration, quality, window))
            out.sort(key=lambda c: (-c.quality, c.start_s, c.spacecraft))
            return out
        for spacecraft, first, last in request.windows:
            if spacecraft not in self.states:
                continue
            if request.fixed_s is not None:
                out.append(Candidate(spacecraft, first, last, 0.0))
                continue
            step = max(self.step, _REQUEST_STEP_S, kind.duration_s / 4.0)
            for start in np.arange(first + kind.setup_s, last - kind.duration_s - kind.teardown_s + _EPS, step):
                out.append(Candidate(spacecraft, float(start), float(start) + kind.duration_s,
                                     -(start - first) / max(last - first, 1.0)))
        return out

    def _activity(self, request: Request, candidate: Candidate, kind) -> Activity:
        return Activity("", candidate.spacecraft, kind.name, kind.kind, candidate.start_s, candidate.end_s,
                        setup_s=kind.setup_s, teardown_s=kind.teardown_s, pointing=kind.pointing,
                        target=request.target, station=candidate.station, request=request.label,
                        priority=request.priority)

    def place(self, request: Request) -> tuple[bool, Counter]:
        """Try ``request``'s candidates in order; True when one is placed."""
        kind = self.section.activity_type(request.type)
        reasons: Counter = Counter()
        candidates = self.candidates(request)
        if not candidates:
            reasons[self._no_window_reason(request)] += 1
            return False, reasons
        conflicted = []
        for candidate in candidates:
            if candidate.quality == -math.inf:
                reasons["too_short"] += 1
                continue
            activity = self._activity(request, candidate, kind)
            state = self.states[candidate.spacecraft]
            reason, pieces = self._check(state, activity, request)
            if reason is None:
                self._fill_prediction(activity, candidate, pieces)
                self._commit(state, activity, pieces)
                return True, reasons
            reasons[reason] += 1
            if reason in ("conflict", "slew"):
                conflicted.append((candidate, activity))
        for candidate, activity in conflicted:  # a contact may give way, kept at its minimum length
            if self._trim_contact(self.states[candidate.spacecraft], activity, candidate):
                return True, reasons
        return False, reasons

    def _trim_contact(self, state: _State, activity: Activity, candidate: Candidate) -> bool:
        """Place ``activity`` by shortening the one unlocked contact it
        collides with (from its start or its end), when the contact keeps
        its minimum duration; undone when anything else breaks."""
        start, end = activity.occupied
        contacts = [a for a in state.activities if a.kind == "contact" and not a.locked
                    and a.occupied[0] < end + 600.0 and a.occupied[1] > start - 600.0]
        if len(contacts) != 1:
            return False
        contact = contacts[0]
        kind = self.section.activity_type(contact.type)
        saved = (state.copy(), copy.deepcopy(self.station_load))
        self._remove(state, contact)
        reason, pieces = self._check(state, activity, None)
        if reason is not None:
            self.states[state.model.sc.name], self.station_load = saved
            return False
        self._fill_prediction(activity, candidate, pieces)
        self._commit(state, activity, pieces)
        step = self.step
        options = []
        if contact.start_s < activity.start_s:  # keep its beginning
            options += [(contact.start_s, e) for e in np.arange(min(contact.end_s, start), contact.start_s, -step)]
        if contact.end_s > activity.end_s:  # keep its end
            options += [(b, contact.end_s) for b in np.arange(max(contact.start_s, end), contact.end_s, step)]
        options = [(b, e) for b, e in options if e - b >= kind.min_duration_s - _EPS]
        options.sort(key=lambda o: -(o[1] - o[0]))
        item = next((p for p in self.opportunities.passes if p.station == contact.station
                     and p.spacecraft == contact.spacecraft and p.aos_s <= contact.start_s + _EPS
                     and p.los_s >= contact.end_s - _EPS), None)
        for b, e in options:
            shorter = copy.copy(contact)
            shorter.start_s, shorter.end_s, shorter.predicted = float(b), float(e), {}
            reason, pieces = self._check(state, shorter, None)
            if reason is None and self._station_free(contact.station, b - self._station_setup(contact.station), e):
                self._fill_prediction(shorter, Candidate(contact.spacecraft, b, e, 0.0, station=contact.station,
                                                         pass_=item), pieces)
                shorter.predicted["trimmed_for"] = activity.request
                self._commit(state, shorter, pieces)
                return True
        self.states[state.model.sc.name], self.station_load = saved
        return False

    def _no_window_reason(self, request: Request) -> str:
        if request.target:
            target = next(t for t in self.section.targets if t.name == request.target)
            if target.valid_utc is not None:
                return "outside_validity"
        return "no_opportunity"

    def _fill_prediction(self, activity: Activity, candidate: Candidate, pieces: dict) -> None:
        entry = pieces["timeline"][0]
        predicted = {"slew_deg": entry["slew_deg"], "slew_s": entry["slew_s"], "point_from_s": entry["point_from_s"],
                     "slew_from": entry["from"]}
        if candidate.window is not None:
            middle = 0.5 * (activity.start_s + activity.end_s)
            window = candidate.window
            predicted.update(off_nadir_deg=window.at(middle, "off_nadir_deg"),
                             elevation_deg=window.at(middle, "elevation_deg"),
                             sun_elevation_deg=window.at(middle, "sun_elevation_deg"),
                             range_m=window.at(middle, "range_m"))
            if window.gsd_m is not None:
                predicted["gsd_m"] = window.at(middle, "gsd_m")
            if window.coverage is not None:
                predicted["coverage"] = window.at(middle, "coverage")
        if candidate.pass_ is not None:
            item = candidate.pass_
            predicted.update(aos_s=item.aos_s, los_s=item.los_s, max_elevation_deg=item.max_elevation_deg,
                             margin_low_db=item.margin_db[0], margin_high_db=item.margin_db[1])
        activity.predicted = {k: (None if isinstance(v, float) and not math.isfinite(v) else v)
                              for k, v in predicted.items()}

    # -- contacts -------------------------------------------------------------
    def contacts(self) -> None:
        """Contacts on passes, with contention (O-12)."""
        section = self.section
        wanting = {p.spacecraft: p for p in section.spacecraft if p.contact_activity}
        passes = [p for p in self.opportunities.passes if p.spacecraft in wanting]
        used: dict = Counter()
        clusters = []
        for item in sorted(passes, key=lambda p: (p.station, p.aos_s)):
            if clusters and clusters[-1][0].station == item.station and item.aos_s < max(p.los_s for p in clusters[-1]):
                clusters[-1].append(item)
            else:
                clusters.append([item])
        clusters.sort(key=lambda c: (c[0].aos_s, c[0].station))
        for cluster in clusters:
            order = sorted(cluster, key=lambda p: (wanting[p.spacecraft].contact_priority, used[p.spacecraft],
                                                   p.spacecraft, p.aos_s))
            winners = []
            for item in order:
                label = f"contact {item.station} {self.timebase.text(item.aos_s)[:16]}Z"
                if (item.station, item.spacecraft, round(item.aos_s)) in self.lost_passes:
                    self._reason(label, item.spacecraft, "contact", wanting[item.spacecraft].contact_priority,
                                 "exclusion")
                    continue
                placed, reason = self._place_contact(item, wanting[item.spacecraft])
                if placed is not None:
                    used[item.spacecraft] += placed.duration_s
                    winners.append(item.spacecraft)
                else:
                    self._reason(label, item.spacecraft, "contact", wanting[item.spacecraft].contact_priority, reason)
            if len(cluster) > 1:
                self.contention.append({"station": cluster[0].station,
                                        "aos_utc": self.timebase.text(min(p.aos_s for p in cluster)),
                                        "wanted_by": sorted({p.spacecraft for p in cluster}), "served": winners})

    def _place_contact(self, item, settings):
        kind = self.section.activity_type(settings.contact_activity)
        station = self.section.station(item.station)
        setup = station.setup_s if station is not None else 0.0
        handover = station.handover_s if station is not None else 0.0
        start = max(item.aos_s, self.start_s + kind.setup_s)
        for a, b, _sc in self.station_load.get(item.station, []):
            if a < item.los_s and b + handover > start:
                start = max(start, b + handover + setup)
        start = max(start, item.aos_s + 0.0)
        end = min(item.los_s, self.end_s - kind.teardown_s)
        if end - start < kind.min_duration_s - _EPS:
            return None, "station_busy" if start > max(item.aos_s, self.start_s + kind.setup_s) + _EPS else "too_short"
        if not self._station_free(item.station, start - setup, end):
            return None, "station_busy"
        request = Request(f"contact {item.station}", "contact", kind.name, settings.contact_priority,
                          (item.spacecraft,), [])
        candidate = Candidate(item.spacecraft, start, end, 0.0, station=item.station, pass_=item)
        activity = self._activity(request, candidate, kind)
        activity.request = ""
        state = self.states[item.spacecraft]
        reason, pieces = self._check(state, activity, None)
        if reason is not None:
            # a shorter contact: start later, after what blocks it
            return None, reason
        self._fill_prediction(activity, candidate, pieces)
        downlinked = float(np.sum(pieces["rate_out"] - state.rate_out) * self.step)
        activity.predicted["downlink_capacity_bit"] = downlinked
        self._commit(state, activity, pieces)
        return activity, None

    def _reason(self, name, spacecraft, kind, priority, reason) -> None:
        key = (name, spacecraft)
        entry = self.reasons.setdefault(key, {"kind": kind, "priority": priority, "counts": Counter()})
        entry["counts"][reason] += 1

    # -- locked and the whole run ------------------------------------------------
    def locked(self) -> None:
        for item in self.section.locked:
            kind = self.section.activity_type(item.activity)
            start, end = self.timebase.to_sim(item.start_utc), self.timebase.to_sim(item.end_utc)
            activity = Activity(item.id, item.spacecraft, kind.name, kind.kind, start, end, setup_s=kind.setup_s,
                                teardown_s=kind.teardown_s, pointing=kind.pointing, target=item.target,
                                station=item.station, request=item.request, locked=True)
            state = self.states[item.spacecraft]
            reason, pieces = self._check(state, activity, None)
            if reason in (None, "battery", "memory", "slew", "star_tracker", "per_day", "per_orbit", "exclusion"):
                # kept as the user locked it; a broken constraint is reported
                if reason is not None:
                    pieces = self._force(state, activity)
                    self.notes.append(f"locked activity {item.id}: {reason} (kept as locked)")
                self._fill_prediction(activity, Candidate(item.spacecraft, start, end, 0.0, station=item.station),
                                      pieces)
                self._commit(state, activity, pieces)
            else:
                self.notes.append(f"locked activity {item.id} overlaps another locked activity; left out")

    def _force(self, state, activity):
        i, _previous, following = self._neighbours(state, activity.occupied[0])
        timeline = self._local_timeline(state, [activity] + ([following] if following is not None else []), i)
        pieces = self._resources(state, activity, timeline[0], following, timeline[1] if following is not None
                                 else None)
        pieces["timeline"], pieces["index"] = timeline, i
        return pieces

    notes: list

    def order(self, requests: list[Request]) -> list[Request]:
        counts = {id(r): len(self.candidates(r)) if r.fixed_s is None else 0 for r in requests}
        return sorted(requests, key=lambda r: (r.fixed_s is None, r.priority, counts[id(r)], r.deadline_s, r.name,
                                               r.occurrence))

    def run(self) -> Plan:
        """The plan (module docstring)."""
        self.notes = []
        self.locked()
        all_requests = self.requests()
        fixed = [r for r in all_requests if r.fixed_s is not None]
        for request in fixed:
            placed, reasons = self.place(request)
            if not placed:
                self._unplaced(request, reasons)
        self.contacts()
        rest = self.order([r for r in all_requests if r.fixed_s is None])
        pending = {}
        for request in rest:
            placed, reasons = self.place(request)
            if not placed:
                pending[(request.name, request.occurrence)] = (request, reasons)
        if self.settings.improvement_iterations and pending:
            pending = self.improve(rest, pending)
        for request, reasons in pending.values():
            self._unplaced(request, reasons)
        return self.plan()

    def _unplaced(self, request: Request, reasons: Counter) -> None:
        key = (request.name, ",".join(request.spacecraft))
        entry = self.reasons.setdefault(key, {"kind": request.kind, "priority": request.priority,
                                              "counts": Counter(), "needed": 0})
        entry["counts"].update(reasons or {"no_opportunity": 1})
        entry["needed"] = entry.get("needed", 0) + 1

    # -- improvement ---------------------------------------------------------------
    def score(self) -> tuple:
        """Lexicographic (O-11): acquisitions per priority (1 first), then the
        quality sum; or the weighted priority sum then quality."""
        placed = [a for s in self.states.values() for a in s.activities if a.kind != "contact" and not a.locked]
        priorities = sorted({r.priority for r in self.requests()} | {a.priority for a in placed if a.priority})
        counts = tuple(sum(1 for a in placed if a.priority == p) for p in priorities)
        quality = 0.0
        weights = self.settings
        for activity in placed:
            off = activity.predicted.get("off_nadir_deg")
            if off is not None and activity.target:
                target = next(t for t in self.section.targets if t.name == activity.target)
                quality -= weights.weight("off_nadir") * off / target.max_off_nadir_deg
        slew = sum(a.predicted.get("slew_s") or 0.0 for s in self.states.values() for a in s.activities)
        quality -= weights.weight("slew") * slew / (self.end_s - self.start_s)
        if weights.objective == "weighted":
            total = sum(float(weights.priority_weights.get(str(p), 0.0)) * c for p, c in zip(priorities, counts))
            return (total, quality)
        return counts + (quality,)

    def improve(self, requests: list[Request], pending: dict) -> dict:
        """Seeded large-neighbourhood search (module docstring)."""
        rng = np.random.default_rng(self.settings.seed)
        best = self.score()
        by_label = {r.label: r for r in requests}
        for _ in range(self.settings.improvement_iterations):
            removable = [(name, a) for name, s in self.states.items() for a in s.activities
                         if not a.locked and a.kind != "contact" and a.request in by_label]
            if not removable:
                break
            saved = ({k: s.copy() for k, s in self.states.items()}, copy.deepcopy(self.station_load), dict(pending))
            count = int(rng.integers(1, min(3, len(removable)) + 1))
            picks = rng.choice(len(removable), size=count, replace=False)
            removed = []
            for index in sorted(picks.tolist(), reverse=True):
                name, activity = removable[index]
                self._remove(self.states[name], activity)
                removed.append(by_label[activity.request])
            retry = [request for request, _r in pending.values()] + removed
            retry.sort(key=lambda r: (r.priority, r.deadline_s, r.name, r.occurrence))
            new_pending = {}
            for request in retry:
                placed, reasons = self.place(request)
                if not placed:
                    new_pending[(request.name, request.occurrence)] = (request, reasons)
            score = self.score()
            if score > best:
                best, pending = score, new_pending
            else:
                self.states, self.station_load, pending = saved
        return pending

    def _remove(self, state: _State, activity: Activity) -> None:
        """Take ``activity`` out and rebuild the spacecraft's arrays."""
        keep = [a for a in state.activities if a is not activity]
        fresh = self._fresh(state.model)
        state.activities, state.starts, state.timeline = [], [], []
        for name in ("cosine", "load", "rate_in", "rate_out", "energy", "memory", "lost"):
            setattr(state, name, getattr(fresh, name))
        if activity.station:
            self.station_load[activity.station] = [x for x in self.station_load.get(activity.station, [])
                                                   if not (x[2] == activity.spacecraft
                                                           and abs(x[1] - activity.end_s) < _EPS)]
        for other in keep:
            self._commit(state, other, self._force(state, other))

    # -- output ----------------------------------------------------------------------
    def plan(self) -> Plan:
        """The plan, with final profiles from a full evaluation."""
        activities = sorted((a for s in self.states.values() for a in s.activities),
                            key=lambda a: (a.start_s, a.spacecraft))
        number = 0
        for activity in activities:
            if not activity.locked or not activity.id:
                number += 1
                activity.id = f"A{number:04d}"
            activity.start_utc, activity.end_utc = self.timebase.text(activity.start_s), self.timebase.text(activity.end_s)
        resources, notes = {}, list(self.notes) + list(self.opportunities.notes)
        for name, state in self.states.items():
            mine = sorted(state.activities, key=lambda a: a.start_s)
            timeline = state.model.timeline(mine)
            for activity, entry in zip(mine, timeline):
                activity.predicted.update(slew_deg=entry["slew_deg"], slew_s=entry["slew_s"],
                                          point_from_s=entry["point_from_s"], slew_from=entry["from"])
                if not entry["ok"]:
                    notes.append(f"{name}: activity {activity.id} has no time for its slew in the final plan")
            profile = state.model.evaluate(mine, timeline)
            keep = slice(None, None, max(1, int(round(60.0 / self.step))))
            resources[name] = {"time_s": profile.time_s[keep].tolist(), "soc": profile.soc[keep].tolist(),
                               "memory_bit": profile.memory_bit[keep].tolist(), "min_soc": profile.min_soc,
                               "max_memory_bit": profile.max_memory_bit, "lost_bit": profile.lost_bit,
                               "downlinked_bit": profile.downlinked_bit, "capacity_wh": profile.capacity_wh,
                               "capacity_bit": profile.capacity_bit if math.isfinite(profile.capacity_bit) else None}
        unscheduled = []
        for (name, spacecraft), entry in sorted(self.reasons.items(), key=lambda kv: (kv[1]["priority"], kv[0])):
            counts = entry["counts"]
            reason = sorted(counts.items(), key=lambda kv: (-kv[1], list(_REASON_ORDER).index(kv[0])
                                                            if kv[0] in _REASON_ORDER else 99))[0][0]
            unscheduled.append(Unscheduled(name, spacecraft, entry["kind"], entry["priority"], reason, dict(counts),
                                           needed=entry.get("needed", 1)))
        score = self.score()
        return Plan(self.scenario.epoch_utc, self.start_s, self.end_s, self.timebase.text(self.start_s),
                    self.timebase.text(self.end_s), activities, unscheduled,
                    {"objective": self.settings.objective, "value": list(score)}, {}, resources,
                    self.contention, notes)


_REASON_ORDER = ("no_opportunity", "outside_validity", "too_short", "exclusion", "conflict", "slew", "station_busy",
                 "per_orbit", "per_day", "star_tracker", "battery", "memory")
