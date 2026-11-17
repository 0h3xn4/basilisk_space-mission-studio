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
"""Flying a plan in the simulation (design 2.9, decisions O-14, O-15):
the app's own Python ``SysModel``\\ s, generalising
``engine.fsw._CommsPointingArbitrator``.

* :class:`PlanWriter` runs early in each step (priority 60, after SPICE,
  before the power sinks): it finds what the plan asks for now, writes
  the ``GroundStateMsg`` the target and station ``locationPointing``
  chains aim at (the site's position from its geodetic coordinates and
  the Earth's live ``J20002Pfix``, as ``groundLocation`` computes it),
  sets ``inertial3D``'s reference, writes a ``DeviceStatusMsg`` to each
  planned instrument, the transmitter and their power sinks, and drives
  its own power sink with the activities' extra load. With contingency
  rules it reads the battery and the memory and overrides the plan
  (Phase 3).
* :class:`PlanArbitrator` runs after the guidance chains (default
  priority, added last): it forwards the active mode's ``AttGuidMsg`` to
  ``mrpFeedback`` and logs the mode, the activity, the pointing error and
  the contingency state.

Neither sets the attitude: the controller and the actuators slew.
Basilisk modules are used through their public API only.
"""

from __future__ import annotations

import bisect
import math

import numpy as np
from Basilisk.architecture import messaging, sysModel
from Basilisk.utilities import macros

from ..engine import geodesy
from ..engine.orbit_maintenance import LogThinner
from . import targets as target_files

MODES = ("sun", "nadir", "target", "station", "inertial")
WRITER_PRIORITY = 60  # after SPICE (500), before the power sinks (50) and the battery (40)
CONTINGENCY_NONE, CONTINGENCY_SAFE, CONTINGENCY_MEMORY = 0, 1, 2


class Schedule:
    """One spacecraft's plan as the executor reads it: pointing segments,
    device intervals and loads, in simulation seconds."""

    def __init__(self, plan, scenario, spacecraft: str):
        section = scenario.operations
        settings = section.planned(spacecraft)
        self.default_mode = settings.default_pointing
        stations = {gs.name: gs for gs in scenario.ground_stations}
        self.segments = []  # (t0, t1, mode, site_P or None, sigma or None, activity index, activity)
        self.devices: dict[str, list] = {}  # device -> [(t0, t1, activity index)]
        self.loads = []  # (t0, t1, power_w, activity index)
        self.activities = sorted((a for a in plan.activities if a.spacecraft == spacecraft), key=lambda a: a.start_s)
        for index, activity in enumerate(self.activities):
            kind = section.activity_type(activity.type)
            point_from = activity.predicted.get("point_from_s", activity.occupied[0])
            site = None
            if activity.pointing == "target":
                target = next(t for t in section.targets if t.name == activity.target)
                lat, lon, alt = target_files.aim_point(target)
                site = geodesy.geodetic_to_pcpf(math.radians(lat), math.radians(lon), alt)
            elif activity.pointing == "station":
                gs = stations[activity.station]
                site = geodesy.geodetic_to_pcpf(math.radians(gs.latitude_deg), math.radians(gs.longitude_deg),
                                                gs.altitude_m)
            sigma = list(kind.sigma_rn) if kind.sigma_rn is not None else None
            self.segments.append((float(point_from), float(activity.occupied[1]), activity.pointing, site, sigma, index,
                                  activity))
            for name in kind.instruments:
                self.devices.setdefault(name, []).append((activity.start_s, activity.end_s, index))
            if kind.transmitter:
                self.devices.setdefault("transmitter", []).append((activity.start_s, activity.end_s, index))
            if kind.power_w:
                self.loads.append((activity.start_s, activity.end_s, kind.power_w, index))
        self.starts = [s[0] for s in self.segments]
        self.switched = sorted(self.devices)

    def segment_at(self, t: float):
        """The pointing segment in force at ``t``, or None (default mode)."""
        i = bisect.bisect_right(self.starts, t) - 1
        if i >= 0 and self.segments[i][0] <= t < self.segments[i][1]:
            return self.segments[i]
        return None

    def device_on(self, name: str, t: float) -> int:
        """The activity index switching ``name`` on at ``t``, or -1."""
        for t0, t1, index in self.devices.get(name, ()):
            if t0 <= t < t1:
                return index
        return -1

    def load_at(self, t: float) -> float:
        return sum(p for t0, t1, p, _i in self.loads if t0 <= t < t1)  # [W]


class PlanWriter(sysModel.SysModel):
    """See the module docstring."""

    def __init__(self, name: str, schedule: Schedule, contingency=None, priorities: dict | None = None):
        super().__init__()
        self.ModelTag = name
        self.schedule = schedule
        self.planetInMsg = messaging.SpicePlanetStateMsgReader()
        self.batteryInMsg = messaging.PowerStorageStatusMsgReader()
        self.storageInMsg = messaging.DataStorageStatusMsgReader()
        self.targetStateOutMsg = messaging.GroundStateMsg()
        self.stationStateOutMsg = messaging.GroundStateMsg()
        # per device: the data node's command (DeviceCmdMsg) and its power sink's status (DeviceStatusMsg)
        self.deviceOutMsgs = {device: (messaging.DeviceCmdMsg(), messaging.DeviceStatusMsg())
                              for device in schedule.switched}
        self.inertialModule = None  # inertial3D, wired by build(); its sigma_R0N follows the plan
        self.loadSink = None  # simplePowerSink, wired by build()
        self.batteryCapacityWs = None  # [W*s] with a contingency on the battery
        self.storageCapacityBits = None  # [bit] with a contingency on the memory
        self.contingency = contingency
        self.priorities = priorities or {}  # activity index -> priority (acquisitions)
        self.mode = schedule.default_mode
        self.activity = -1
        self.state = CONTINGENCY_NONE
        self.firings: list = []  # (t, state) each time the contingency state changes
        self.skipped: set = set()  # activity indices the contingency dropped
        for msg in (self.targetStateOutMsg, self.stationStateOutMsg):
            msg.write(messaging.GroundStateMsgPayload())
        for command, status in self.deviceOutMsgs.values():
            self._write_device(command, status, False)

    def Reset(self, CurrentSimNanos):
        if self.loadSink is not None:
            self.loadSink.nodePowerOut = 0.0

    def _write_device(self, command, status, on: bool, nanos: int | None = None) -> None:
        cmd = messaging.DeviceCmdMsgPayload()
        cmd.deviceCmd = 1 if on else 0
        state = messaging.DeviceStatusMsgPayload()
        state.deviceStatus = 1 if on else 0
        if nanos is None:
            command.write(cmd)
            status.write(state)
        else:
            command.write(cmd, nanos, self.moduleID)
            status.write(state, nanos, self.moduleID)

    def _site_state(self, site_p, planet) -> messaging.GroundStateMsgPayload:
        dcm_pn = np.asarray(planet.J20002Pfix, dtype=float).reshape(3, 3)
        r_lp_n = dcm_pn.T @ np.asarray(site_p, dtype=float)
        payload = messaging.GroundStateMsgPayload()
        payload.r_LP_N = r_lp_n.tolist()
        payload.r_LN_N = (np.asarray(planet.PositionVector, dtype=float) + r_lp_n).tolist()
        payload.rHat_LP_N = (r_lp_n / np.linalg.norm(r_lp_n)).tolist()
        return payload

    def _contingency(self, t: float) -> None:
        rules = self.contingency
        if rules is None:
            return
        previous = self.state
        if rules.safe_mode_soc is not None and self.batteryCapacityWs:
            soc = float(self.batteryInMsg().storageLevel) / self.batteryCapacityWs
            if self.state == CONTINGENCY_SAFE:
                if soc >= rules.recover_soc:
                    self.state = CONTINGENCY_NONE
            elif soc < rules.safe_mode_soc:
                self.state = CONTINGENCY_SAFE
        if self.state != CONTINGENCY_SAFE and rules.memory_fraction is not None and self.storageCapacityBits:
            level = float(self.storageInMsg().storageLevel) / self.storageCapacityBits
            self.state = CONTINGENCY_MEMORY if level >= rules.memory_fraction else CONTINGENCY_NONE
        if self.state != previous:
            self.firings.append((t, self.state))

    def _dropped(self, index: int) -> bool:
        """Whether the contingency state drops activity ``index`` now."""
        if index < 0:
            return False
        if self.state == CONTINGENCY_SAFE:
            return True
        if self.state == CONTINGENCY_MEMORY:
            activity = self.schedule.activities[index]
            return activity.kind == "acquisition" and (activity.priority or 99) >= self.contingency.drop_priority
        return False

    def UpdateState(self, CurrentSimNanos):
        t = CurrentSimNanos * macros.NANO2SEC  # [s]
        self._contingency(t)
        planet = self.planetInMsg()
        segment = self.schedule.segment_at(t)
        if segment is not None and self._dropped(segment[5]):
            self.skipped.add(segment[5])
            segment = None
        if self.state == CONTINGENCY_SAFE:
            self.mode, self.activity = "sun", -1
        elif segment is None:
            self.mode, self.activity = self.schedule.default_mode, -1
        else:
            _t0, _t1, mode, site, sigma, index, _activity = segment
            self.mode, self.activity = mode, index
            if mode in ("target", "station") and site is not None:
                out = self.targetStateOutMsg if mode == "target" else self.stationStateOutMsg
                out.write(self._site_state(site, planet), CurrentSimNanos, self.moduleID)
            if mode == "inertial" and sigma is not None and self.inertialModule is not None:
                self.inertialModule.sigma_R0N = sigma
        for device, (command, status) in self.deviceOutMsgs.items():
            index = self.schedule.device_on(device, t)
            self._write_device(command, status, index >= 0 and not self._dropped(index), CurrentSimNanos)
        if self.loadSink is not None:
            load = 0.0 if self.state == CONTINGENCY_SAFE else self.schedule.load_at(t)
            self.loadSink.nodePowerOut = -load  # [W]


class PlanArbitrator(sysModel.SysModel):
    """See the module docstring."""

    def __init__(self, name: str, writer: PlanWriter, record_interval_s: float = 0.0):
        super().__init__()
        self.ModelTag = name
        self.writer = writer
        self.guidInMsgs = {mode: messaging.AttGuidMsgReader() for mode in MODES}
        self.attGuidOutMsg = messaging.AttGuidMsg()
        self.logThinner = LogThinner(record_interval_s)
        self.tLog: list = []
        self.modeLog: list = []  # index into MODES
        self.activityLog: list = []  # index into the spacecraft's activities, -1 for none
        self.pointingErrorDegLog: list = []  # [deg] the active chain's tracking error
        self.contingencyLog: list = []

    def UpdateState(self, CurrentSimNanos):
        t = CurrentSimNanos * macros.NANO2SEC  # [s]
        mode = self.writer.mode
        reader = self.guidInMsgs[mode]
        guid = reader() if reader.isLinked() else self.guidInMsgs[self.writer.schedule.default_mode]()
        self.attGuidOutMsg.write(guid, CurrentSimNanos, self.moduleID)
        theta_deg = math.degrees(4.0 * math.atan(float(np.linalg.norm(guid.sigma_BR))))
        if self.logThinner.due(t):
            self.tLog.append(t)
            self.modeLog.append(MODES.index(mode))
            self.activityLog.append(self.writer.activity)
            self.pointingErrorDegLog.append(theta_deg)
            self.contingencyLog.append(self.writer.state)


class ExecutorHandle:
    """What :func:`build` made for one spacecraft (kept alive by the
    service's spacecraft handle)."""

    def __init__(self, writer, arbitrator, schedule, keep_alive):
        self.writer, self.arbitrator, self.schedule, self.keep_alive = writer, arbitrator, schedule, keep_alive

    @property
    def device_msgs(self) -> dict:
        return self.writer.deviceOutMsgs


def build(service, task_name: str, sc_config, nav, mu: float, plan, battery=None) -> ExecutorHandle:
    """Build one spacecraft's executor and guidance chains; returns the
    handle (its arbitrator's ``attGuidOutMsg`` feeds ``mrpFeedback``).
    Called by ``engine.service`` in place of the single ``fsw_mode``
    guidance when the run flies a plan."""
    from Basilisk.simulation import simplePowerSink

    from ..engine import fsw

    scenario = service.scenario
    section = scenario.operations
    schedule = Schedule(plan, scenario, sc_config.name)
    settings = section.planned(sc_config.name)
    priorities = {i: a.priority for i, a in enumerate(schedule.activities)}
    writer = PlanWriter(f"{sc_config.name}_planWriter", schedule, settings.contingency, priorities)
    writer.planetInMsg.subscribeTo(service._planet_state_out_msgs["earth"])
    service.scSim.AddModelToTask(task_name, writer, WRITER_PRIORITY)
    keep = [writer]
    if sc_config.power is not None and battery is not None:
        sink = simplePowerSink.SimplePowerSink()
        sink.ModelTag = f"{sc_config.name}PlanLoadSink"
        sink.nodePowerOut = 0.0
        service.scSim.AddModelToTask(task_name, sink, 50)
        battery.addPowerNodeToModel(sink.nodePowerOutMsg)
        writer.loadSink = sink
        writer.batteryInMsg.subscribeTo(battery.batPowerOutMsg)
        writer.batteryCapacityWs = sc_config.power.battery_capacity_wh * 3600.0  # [W*s]
        keep.append(sink)
    sun_axis = sc_config.power.panel_normal_b if sc_config.power is not None else [0.0, 0.0, 1.0]
    used = {schedule.default_mode, "sun"} | {s[2] for s in schedule.segments}
    chains = {}
    for mode in MODES:
        if mode not in used:
            continue
        tag = f"{sc_config.name}_plan_{mode}"
        if mode == "sun":
            chains[mode] = fsw.build_guidance(service.scSim, task_name, tag, "sunSafePoint", {"sHatBdyCmd": sun_axis},
                                              nav, mu, {})
        elif mode == "nadir":
            chains[mode] = fsw.build_guidance(service.scSim, task_name, tag, "hillPoint", {}, nav, mu, {})
        elif mode == "inertial":
            chains[mode], module = _inertial(service, task_name, tag, nav)
            writer.inertialModule = module
        else:
            axis = _boresight(section, sc_config, schedule, mode)
            chains[mode] = _location(service, task_name, tag, nav, axis,
                                     writer.targetStateOutMsg if mode == "target" else writer.stationStateOutMsg)
    arbitrator = PlanArbitrator(f"{sc_config.name}_planArbitrator", writer,
                                scenario.sim_settings.record_interval_s)
    for mode, msg in chains.items():
        arbitrator.guidInMsgs[mode].subscribeTo(msg)
    service.scSim.AddModelToTask(task_name, arbitrator)
    keep.append(arbitrator)
    return ExecutorHandle(writer, arbitrator, schedule, keep)


def _boresight(section, sc_config, schedule: Schedule, mode: str) -> list:
    """The body axis the spacecraft's ``mode`` activities point (one per
    mode: the first activity type's)."""
    from ..model3d.equipment import mounted_items

    for _t0, _t1, segment_mode, _site, _sigma, _i, activity in schedule.segments:
        if segment_mode != mode:
            continue
        kind = section.activity_type(activity.type)
        if kind.equipment:
            item = next(m for m in mounted_items(sc_config) if m.name == kind.equipment)
            return [float(v) for v in item.boresight_b]
        return list(kind.boresight_b)
    return [0.0, 0.0, 1.0]


def _location(service, task_name: str, tag: str, nav, axis, state_msg):
    from Basilisk.fswAlgorithms import locationPointing

    module = locationPointing.locationPointing()
    module.ModelTag = f"{tag}_locationPointing"
    module.pHat_B = list(axis)
    module.useBoresightRateDamping = 1
    module.scAttInMsg.subscribeTo(nav.attOutMsg)
    module.scTransInMsg.subscribeTo(nav.transOutMsg)
    module.locationInMsg.subscribeTo(state_msg)
    service.scSim.AddModelToTask(task_name, module)
    service._plan_keep_alive.append(module)
    return module.attGuidOutMsg


def _inertial(service, task_name: str, tag: str, nav):
    from Basilisk.fswAlgorithms import attTrackingError, inertial3D

    module = inertial3D.inertial3D()
    module.ModelTag = f"{tag}_inertial3D"
    module.sigma_R0N = [0.0, 0.0, 0.0]
    service.scSim.AddModelToTask(task_name, module)
    tracking = attTrackingError.attTrackingError()
    tracking.ModelTag = f"{tag}_attTrackingError"
    tracking.attRefInMsg.subscribeTo(module.attRefOutMsg)
    tracking.attNavInMsg.subscribeTo(nav.attOutMsg)
    service.scSim.AddModelToTask(task_name, tracking)
    service._plan_keep_alive += [module, tracking]
    return tracking.attGuidOutMsg, module


def attach(handle: ExecutorHandle, data_handling_handle) -> None:
    """After the data handling is built: the memory the contingency reads."""
    if data_handling_handle is not None and data_handling_handle.storage is not None:
        handle.writer.storageInMsg.subscribeTo(data_handling_handle.storage.storageUnitDataOutMsg)
        handle.writer.storageCapacityBits = float(data_handling_handle.storage.storageCapacity)


def result_series(handle: ExecutorHandle, name: str) -> list:
    """The executor's recorded series (``<sc>.plan.*``)."""
    from ..engine.results import TimeSeries

    arbitrator = handle.arbitrator
    t = np.asarray(arbitrator.tLog, dtype=float)
    out = [TimeSeries(f"{name}.plan.mode", t, ("mode",), np.asarray(arbitrator.modeLog, dtype=float)[:, None], "-"),
           TimeSeries(f"{name}.plan.activity", t, ("activity",),
                      np.asarray(arbitrator.activityLog, dtype=float)[:, None], "-"),
           TimeSeries(f"{name}.plan.pointing_error_deg", t, ("pointing_error",),
                      np.asarray(arbitrator.pointingErrorDegLog, dtype=float)[:, None], "deg"),
           TimeSeries(f"{name}.plan.contingency", t, ("contingency",),
                      np.asarray(arbitrator.contingencyLog, dtype=float)[:, None], "-")]
    if not len(t):
        return []
    return out
