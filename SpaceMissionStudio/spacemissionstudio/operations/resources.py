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
"""A spacecraft's pointing timeline, slews, energy and memory under a
plan (design 2.5 and 2.6).

**Pointing.** Outside activities the spacecraft holds its default mode.
Before an activity it slews from where it was: from the default mode
when the gap allows a slew there and back, else straight from the
previous activity. The time the slew starts is the activity's
``point_from_s``; the executor flies the same timeline.

**Energy.** The power budget's model: the panel gives ``S (AU/r)^2 A eta
max(0, cos theta) f_sun`` (``simpleSolarPanel``'s equation, the same
``PowerConfig``, theta from the planned attitude), less the bus idle
load, the instruments and transmitter while on and the activities' own
power; the battery is integrated and kept within 0 and its capacity.

**Memory.** The instruments' data rate while on (always for an
instrument no activity type switches), minus the downlink rate during a
contact while the predicted margin is at least ``link.required_margin_db``;
kept within 0 and the storage capacity (data above it is lost, as the
storage unit refuses it).

Activities switch their devices on from ``start_s`` to ``end_s``; the
share of each grid step they cover is used, so the integrals do not
depend on the grid.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .. import constants
from . import attitude
from . import targets as target_files
from .geometry import PlanningGeometry

_SAME_TIME_S = 1e-6  # [s]


@dataclass
class Profile:
    """A spacecraft's resources on the geometry grid."""

    time_s: np.ndarray  # (n,) [s]
    energy_wh: np.ndarray  # (n,) [W*h] battery charge at each sample
    soc: np.ndarray  # (n,) [-]
    memory_bit: np.ndarray  # (n,) [bit]
    generated_w: np.ndarray  # (n,) [W]
    load_w: np.ndarray  # (n,) [W]
    lost_bit: float  # [bit] over the horizon
    downlinked_bit: float  # [bit]
    capacity_wh: float  # [W*h]
    capacity_bit: float  # [bit]

    @property
    def min_soc(self) -> float:
        return float(np.min(self.soc)) if len(self.soc) else 1.0

    @property
    def max_memory_bit(self) -> float:
        return float(np.max(self.memory_bit)) if len(self.memory_bit) else 0.0


def _clipped_sum(start: float, deltas: np.ndarray, low: float, high: float) -> tuple[np.ndarray, float]:
    """``s_k = clip(s_{k-1} + d_k, low, high)`` and how much was cut above
    ``high``."""
    out = np.empty(len(deltas))
    value, cut = start, 0.0
    for k, delta in enumerate(deltas.tolist()):
        value += delta
        if value > high:
            cut += value - high
            value = high
        elif value < low:
            value = low
        out[k] = value
    return out, cut


def overlap(time_s: np.ndarray, step_s: float, start: float, end: float) -> np.ndarray:
    """The share [-] of each grid step [t_k, t_k + step) inside [start, end]."""
    lo = np.maximum(time_s, start)
    hi = np.minimum(time_s + step_s, end)
    return np.clip((hi - lo) / step_s, 0.0, 1.0)


class SpacecraftModel:
    """What the planner knows of one spacecraft: its track, its devices and
    its pointing; evaluates a list of activities."""

    def __init__(self, scenario, sc, geometry: PlanningGeometry, section, slew_model):
        self.scenario, self.sc, self.geometry, self.section = scenario, sc, geometry, section
        self.settings = section.planned(sc.name)
        self.slew = slew_model
        self.track = geometry.tracks[sc.name]
        self.t = geometry.time_s
        self.step = geometry.step_s
        sun_rel = geometry.sun_n - self.track.position_n
        distance = np.linalg.norm(sun_rel, axis=1)
        self.sun_unit = sun_rel / distance[:, None]
        self.flux = constants.SOLAR_FLUX_1AU_W_M2 * (constants.ASTRONOMICAL_UNIT_M / distance) ** 2  # [W/m^2]
        self.hill = attitude.hill_dcm(self.track.position_n, self.track.velocity_n)
        power = sc.power
        self.panel_b = attitude.unit(np.asarray(power.panel_normal_b, dtype=float)) if power is not None else None
        self.sun_axis_b = self.panel_b if self.panel_b is not None else np.array([0.0, 0.0, 1.0])
        handling = sc.data_handling
        switched = {name for kind in section.activity_types for name in kind.instruments}
        self.instruments = {i.name: i for i in handling.instruments} if handling is not None else {}
        self.always_on = [i for name, i in self.instruments.items() if name not in switched]
        self._sites: dict = {}
        self._equipment: dict | None = None

    # -- directions ------------------------------------------------------
    def site(self, latitude_deg: float, longitude_deg: float, altitude_m: float) -> np.ndarray:
        key = (latitude_deg, longitude_deg, altitude_m)
        if key not in self._sites:
            self._sites[key] = self.geometry.site(*key)[0]
        return self._sites[key]

    def aim(self, activity) -> np.ndarray | None:
        """The inertial line of sight (n, 3) the activity points along, or
        None for a mode that is not an axis on a direction."""
        if activity.pointing == "target":
            target = next(t for t in self.section.targets if t.name == activity.target)
            point = self.site(*target_files.aim_point(target))
        elif activity.pointing == "station":
            station = next(g for g in self.scenario.ground_stations if g.name == activity.station)
            point = self.site(station.latitude_deg, station.longitude_deg, station.altitude_m)
        elif activity.pointing == "sun":
            return self.sun_unit
        else:
            return None
        line = point - self.track.position_n
        return line / np.linalg.norm(line, axis=1)[:, None]

    def boresight(self, kind) -> np.ndarray:
        """The body axis an activity type points (its equipment's or its
        own), the Sun axis for 'sun'."""
        if kind.pointing == "sun":
            return attitude.unit(np.asarray(kind.sun_axis_b, dtype=float)) if kind.sun_axis_b is not None \
                else self.sun_axis_b
        if kind.equipment:
            if self._equipment is None:
                from ..model3d.equipment import mounted_items

                self._equipment = {m.name: m for m in mounted_items(self.sc)}
            item = self._equipment[kind.equipment]
            return attitude.unit(np.asarray(item.boresight_b, dtype=float))
        if kind.boresight_b is not None:
            return attitude.unit(np.asarray(kind.boresight_b, dtype=float))
        return np.array([0.0, 0.0, 1.0])

    def index(self, t: float) -> int:
        return int(np.clip(round((t - self.t[0]) / self.step), 0, len(self.t) - 1))

    def attitude_at(self, mode: str, k: int, previous: np.ndarray, axis_b=None, aim=None, sigma=None) -> np.ndarray:
        """The attitude of ``mode`` at sample ``k``, from ``previous`` where
        the mode leaves a rotation free."""
        if mode == "nadir":
            return self.hill[k]
        if mode == "inertial":
            return attitude.inertial_dcm(sigma)
        return attitude.point_axis(previous, axis_b, aim[k])

    # -- the timeline ------------------------------------------------------
    def default_attitude(self, k: int, previous: np.ndarray) -> np.ndarray:
        mode = self.settings.default_pointing
        return self.attitude_at(mode, k, previous, self.sun_axis_b, self.sun_unit)

    def start_attitude(self, activity, kind, previous: np.ndarray, k: int) -> np.ndarray:
        return self.attitude_at(activity.pointing, k, previous, self.boresight(kind), self.aim(activity), kind.sigma_rn)

    def slew_between(self, previous: np.ndarray, activity, kind, k: int) -> tuple[float, np.ndarray]:
        """The slew angle [deg] onto the activity's attitude at sample ``k``
        from ``previous``, and that attitude."""
        target = self.start_attitude(activity, kind, previous, k)
        if activity.pointing in ("nadir", "inertial"):
            return attitude.angle_deg(previous, target), target
        aim = self.aim(activity)
        return attitude.axis_angle_deg(previous, self.boresight(kind), aim[k]), target

    def timeline(self, activities: list, after: dict | None = None) -> list[dict]:
        """For each activity (sorted by start), how it is reached: the slew
        angle and time, whether from the default mode, when the slew starts
        (``point_from_s``) and whether there is time for it (``ok``).
        ``after``: start after an activity already placed,
        ``{"end_attitude", "free_from"}``."""
        out = []
        if after is None:
            current = self.default_attitude(0, np.eye(3))
            free_from = self.t[0]  # [s] when the spacecraft is free (end of the previous occupation)
            previous_was_default = True
        else:
            current, free_from, previous_was_default = after["end_attitude"], after["free_from"], False
        for activity in activities:
            kind = self.section.activity_type(activity.type)
            start, end = activity.occupied
            k_start = self.index(start)
            k_free = self.index(free_from)
            if previous_was_default:
                home = self.default_attitude(k_start, current)
                angle, target = self.slew_between(home, activity, kind, k_start)
                slew_s = self.slew.time_s(angle)
                entry = {"from": "default", "slew_deg": angle, "slew_s": slew_s, "point_from_s": start - slew_s,
                         "ok": start - slew_s >= free_from - _SAME_TIME_S}
            else:
                home = self.default_attitude(k_free, current)
                back = self.slew.time_s(attitude.angle_deg(current, home) if self.settings.default_pointing ==
                                        "nadir" else attitude.axis_angle_deg(current, self.sun_axis_b,
                                                                              self.sun_unit[k_free]))
                angle_home, target_home = self.slew_between(home, activity, kind, k_start)
                via_default = back + self.slew.time_s(angle_home)
                if start - free_from >= via_default - _SAME_TIME_S:
                    slew_s = self.slew.time_s(angle_home)
                    entry = {"from": "default", "slew_deg": angle_home, "slew_s": slew_s,
                             "point_from_s": start - slew_s, "ok": True}
                    target = target_home
                else:
                    angle, target = self.slew_between(current, activity, kind, k_start)
                    slew_s = self.slew.time_s(angle)
                    entry = {"from": "previous", "slew_deg": angle, "slew_s": slew_s, "point_from_s": free_from,
                             "ok": start - free_from >= slew_s - _SAME_TIME_S}
            # the attitude through the activity (an axis on a moving direction: smallest rotations)
            k_end = self.index(end)
            current = target
            if activity.pointing in ("target", "station", "sun"):
                axis, aim = self.boresight(kind), self.aim(activity)
                for k in range(k_start + 1, k_end + 1):
                    current = attitude.point_axis(current, axis, aim[k])
            elif activity.pointing == "nadir":
                current = self.hill[k_end]
            entry["end_attitude"] = current
            entry["start_attitude"] = target
            out.append(entry)
            free_from = end
            previous_was_default = False
        return out

    # -- resources ----------------------------------------------------------
    def panel_cosine(self, activities: list, timeline: list) -> np.ndarray:
        """max(0, cos) of the panel to the Sun at each sample, from the
        planned attitude (the activity's mode from ``point_from_s`` to its
        end, the default mode elsewhere)."""
        n = len(self.t)
        if self.panel_b is None:
            return np.zeros(n)
        mode = self.settings.default_pointing
        if mode == "nadir":
            cosine = np.einsum("nji,j,ni->n", self.hill, self.panel_b, self.sun_unit)
        else:
            cosine = np.full(n, float(np.dot(self.panel_b, self.sun_axis_b)))
        for activity, entry in zip(activities, timeline):
            kind = self.section.activity_type(activity.type)
            k0, k1 = self.index(entry["point_from_s"]), self.index(activity.occupied[1])
            if activity.pointing == "nadir":
                cosine[k0:k1 + 1] = np.einsum("nji,j,ni->n", self.hill[k0:k1 + 1], self.panel_b,
                                              self.sun_unit[k0:k1 + 1])
                continue
            if activity.pointing == "sun":
                axis = self.boresight(kind)
                cosine[k0:k1 + 1] = float(np.dot(self.panel_b, axis))
                continue
            if activity.pointing == "inertial":
                panel_n = attitude.inertial_dcm(kind.sigma_rn).T @ self.panel_b
                cosine[k0:k1 + 1] = self.sun_unit[k0:k1 + 1] @ panel_n
                continue
            current = entry["start_attitude"]
            axis, aim = self.boresight(kind), self.aim(activity)
            for k in range(k0, k1 + 1):
                current = attitude.point_axis(current, axis, aim[k])
                cosine[k] = float(np.dot(current.T @ self.panel_b, self.sun_unit[k]))
        return np.maximum(cosine, 0.0)

    def link_fraction(self, activity, start: float, end: float) -> np.ndarray:
        """The share of each step a contact downlinks: inside it and where
        the predicted margin is at least the required margin."""
        from ..config import registry
        from ..engine import link_budget

        share = overlap(self.t, self.step, start, end)
        station = next(g for g in self.scenario.ground_stations if g.name == activity.station)
        required = float(registry.value("link.required_margin_db", self.scenario))
        view = self.geometry.views.get((station.name, self.sc.name))
        if view is None:
            view = self.geometry.view(self.sc.name, station.latitude_deg, station.longitude_deg, station.altitude_m)
        for k in np.flatnonzero(share > 0.0):
            try:
                margin = link_budget.link_budget_breakdown(float(view.range_m[k]), self.sc.rf_link, station, 0.0,
                                                           scenario=self.scenario,
                                                           elevation_deg=float(view.elevation_deg[k])).margin_db
            except (ValueError, ZeroDivisionError):
                margin = -math.inf
            if not margin >= required or view.elevation_deg[k] < 0.0:
                share[k] = 0.0
        return share

    def evaluate(self, activities: list, timeline: list | None = None) -> Profile:
        """The energy and memory profiles under ``activities`` (sorted)."""
        timeline = self.timeline(activities) if timeline is None else timeline
        n = len(self.t)
        sc = self.sc
        power, handling = sc.power, sc.data_handling
        generated = np.zeros(n)
        load = np.zeros(n)
        if power is not None:
            sunlight = self.track.sunlight
            generated = (self.flux * power.panel_area_m2 * power.panel_efficiency * sunlight
                         * self.panel_cosine(activities, timeline))
            load += power.bus_idle_power_w
        rate_in = np.zeros(n)  # [bit/s]
        rate_out = np.zeros(n)  # [bit/s]
        for instrument in self.always_on:
            rate_in += instrument.data_rate_bps
            load += instrument.power_w
        for activity in activities:
            kind = self.section.activity_type(activity.type)
            share = overlap(self.t, self.step, activity.start_s, activity.end_s)
            load += share * kind.power_w
            for name in kind.instruments:
                instrument = self.instruments[name]
                rate_in += share * instrument.data_rate_bps
                load += share * instrument.power_w
            if kind.transmitter and handling is not None and sc.rf_link is not None:
                load += share * handling.transmitter_power_w
                rate_out += self.link_fraction(activity, activity.start_s, activity.end_s) * sc.rf_link.data_rate_bps
        capacity_wh = power.battery_capacity_wh if power is not None else 0.0
        if power is not None:
            energy, _cut = _clipped_sum(power.battery_initial_soc * capacity_wh,
                                        (generated - load) * self.step / 3600.0, 0.0, capacity_wh)
            soc = energy / capacity_wh
        else:
            energy = np.zeros(n)
            soc = np.ones(n)
        capacity_bit = handling.storage_capacity_gbit * 1e9 if handling is not None else math.inf
        memory, lost, downlinked = self._memory(rate_in, rate_out, capacity_bit)
        return Profile(self.t, energy, soc, memory, generated, load, lost, downlinked, capacity_wh, capacity_bit)

    def _memory(self, rate_in: np.ndarray, rate_out: np.ndarray, capacity: float):
        handling = self.sc.data_handling
        n = len(self.t)
        if handling is None:
            return np.zeros(n), 0.0, 0.0
        stored = sum(i.initial_data_gbit for i in handling.instruments) * 1e9  # [bit]
        memory = np.empty(n)
        lost = downlinked = 0.0
        gain, drain = (rate_in * self.step).tolist(), (rate_out * self.step).tolist()
        for k in range(n):
            stored += gain[k]
            if stored > capacity:
                lost += stored - capacity
                stored = capacity
            taken = min(stored, drain[k])
            stored -= taken
            downlinked += taken
            memory[k] = stored
        return memory, lost, downlinked


def attitude_series(model: SpacecraftModel, activities: list, timeline: list | None = None) -> np.ndarray:
    """The planned attitude ``[BN]`` (n, 3, 3) at every grid sample: the
    default mode, each activity's mode from its ``point_from_s`` to the end
    of its teardown (a slew is shown as its destination), as the energy
    model takes it. For the AEM and the 3D view of a plan."""
    timeline = model.timeline(activities) if timeline is None else timeline
    n = len(model.t)
    out = np.empty((n, 3, 3))
    spans = [(model.index(entry["point_from_s"]), model.index(activity.occupied[1]), activity, entry)
             for activity, entry in zip(activities, timeline)]
    current = model.default_attitude(0, np.eye(3))
    k = 0
    for k0, k1, activity, entry in spans + [(n, n, None, None)]:
        for j in range(k, min(k0, n)):  # the default mode
            current = model.default_attitude(j, current)
            out[j] = current
        if activity is None:
            break
        kind = model.section.activity_type(activity.type)
        current = entry["start_attitude"]
        aim = model.aim(activity)
        for j in range(max(k0, k), min(k1 + 1, n)):
            if activity.pointing == "nadir":
                current = model.hill[j]
            elif activity.pointing == "inertial":
                current = attitude.inertial_dcm(kind.sigma_rn)
            else:
                current = attitude.point_axis(current, model.boresight(kind), aim[j])
            out[j] = current
        k = min(k1 + 1, n)
    return out
