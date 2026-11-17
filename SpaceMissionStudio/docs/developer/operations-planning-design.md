# Mission operations planning: design

An operations planning layer: from mission goals (targets to image,
stations to contact, maneuvers, calibrations) to a conflict-free,
time-tagged plan per spacecraft; the plan flown in the Basilisk simulation
to check it; operations products exported from it. Plan, simulate,
verify is the core.

Decisions are numbered O-01... in
[operations-planning-decisions.md](operations-planning-decisions.md);
progress is in
[operations-planning-progress.md](operations-planning-progress.md). The
target is spacecraft of 100 kg and more (ESPA class and small satellites)
on Earth-observation and communications missions in low Earth orbit, with
one or more ground stations and possibly a constellation. Not CubeSats.

**Absolute rule.** Nothing of upstream Basilisk changes: no file outside
`SpaceMissionStudio/` (but the SpaceMissionStudio part of the root
README), no monkeypatching or wrapping of Basilisk classes, no change to
the installed `bsk` 2.12.0. Every Basilisk module below is used through
its public API (section 4). Checked before every commit with
`git diff --name-only develop...HEAD`.

## 1. What exists (Step 0 findings)

### 1.1 Ground-station access

- `GroundStationConfig` (`schema/scenario.py`): name, geodetic latitude
  and longitude (WGS-84), altitude, `min_elevation_deg` (default 10),
  receive gain, noise temperature. No azimuth mask, no maximum range.
- `fsw.build_ground_location` builds Basilisk's `groundLocation` per
  station (`specifyLocationPCPF`, `minimumElevation`, no range limit);
  `fsw.add_access_analysis` adds every spacecraft once all exist.
- Recorded per station and spacecraft: `<gs>.access_to_<sc>.has_access`,
  `.slant_range` [m], `.elevation` [rad] and `.azimuth` [rad] (geodetic
  horizon, `geodesy.geodetic_elevation_azimuth`), with `.link_margin_db`
  and, with a link gate, `.antenna_off_boresight` and `.link_closed`.
- `events._passes` turns `has_access` runs into Timeline "pass" events
  with the peak elevation. AOS and LOS are the first and last samples
  with access: no interpolation, so they are good to one record interval.
- `scenario_checks.predict_passes` predicts passes before a run with a
  Kepler + J2-secular propagator (Earth only), the IAU_EARTH rotation
  angle (prime meridian only) and the WGS-84 site; 30 s steps. It feeds
  the pre-run pass summary and warnings.

### 1.2 Eclipse

`<sc>.eclipse.illumination_factor` (1 in sunlight, 0 in umbra) from
Basilisk's `eclipse` module whenever the Sun is tracked (optionally the
app's `CombinedEclipse` over several bodies). `events._eclipses` makes
umbra and penumbra events.

### 1.3 Power

`PowerConfig`: panel area, efficiency, panel normal, bus idle load,
battery capacity and initial state of charge. Basilisk's
`simpleSolarPanel` (S A eta cos(theta) times the eclipse factor),
`simplePowerSink` (bus, instruments, transmitter, comms) and
`simpleBattery`. Series `<sc>.battery_charge` [W*hr] and
`<sc>.battery_net_power` [W]. Flexible solar arrays and the panel
degradation choice (`power.degradation`) modify the generation.

### 1.4 Data handling

`DataHandlingConfig` (storage capacity, instruments with a constant data
rate and power, transmitter power) on Basilisk's `simpleInstrument`,
`partitionedStorageUnit` and `spaceToGroundTransmitter`, as
`examples/scenarioGroundDownlink.py` wires them; the app's
`_DownlinkGate` clears access unless the link closes (Eb/N0 margin from
`engine.link_budget`, antenna gain toward the station from the
simulated attitude) and `_DataLedger` counts generated, lost and
downlinked data and switches the transmitter's power. Instruments run
all the time: there is no switching by time today. Basilisk's data and
power nodes all have a `nodeStatusInMsg` (`DeviceStatusMsg`) that turns
them on and off: the plan executor uses it (section 2.7).

### 1.5 Link budget

`engine.link_budget` (Basilisk-free): `link_budget_breakdown(range,
rf_link, station, pointing_error, scenario, elevation)` gives EIRP,
free-space loss, pointing loss, atmospheric loss (ITU-R P.676, optional),
C/N0, Eb/N0 and margin; `link_margin_series` builds the recorded margin.
The planner reuses `link_budget_breakdown` for a pass's predicted margin.

### 1.6 Attitude switching

- `fsw.build_guidance` builds one guidance mode per spacecraft:
  `inertial3D`, `hillPoint`, `velocityPoint`, `sunSafePoint`,
  `locationPointing` (to a station's `groundLocation` or a body's
  ephemeris). The reference-only modes go through `attTrackingError`.
- `_CommsPointingArbitrator` (`fsw.py`), the app's own Python `SysModel`:
  two guidance chains (Sun, station) run every step and it forwards the
  active one's `AttGuidMsg` to `mrpFeedback`, chosen by the live
  `AccessMsg.hasAccess`. It never sets the attitude: the controller
  slews. It switches a comms power sink and logs its mode and the active
  chain's pointing error. It is limited to idealized actuation and is
  mutually exclusive with `fsw_mode`.
- `fsw_mode` spacecraft can fly reaction wheels (`rwMotorTorque`, wheel
  torque and speed limits), thrusters, momentum dumping and magnetic
  desaturation behind `mrpFeedback`.
- No slew-rate or agility model exists. The dashboard's "Converged" /
  "Slewing" badge uses the parameter `results.pointing_converged_deg`
  (5 deg).
- Everything runs in one task (`dynTask`), at the dynamics step.

### 1.7 Mission Sequence (MissionEngine)

`schema/command.py` commands (propagate by duration, epoch or event;
impulsive maneuver; Lambert transfer; assignment; report; if; while;
script block) executed by `MissionEngine` with repeated
`ConfigureStopTime`/`ExecuteSimulation` on the one Basilisk run; event
stops use Basilisk's own event mechanism (periapsis, apoapsis, pass
start/end from the live access message). One run is limited to about 104
days (Basilisk's nanosecond clock).

### 1.8 Time and epochs

`Scenario.epoch_utc` (ISO 8601 UTC) is the one stored epoch. The
simulation's time is TDB seconds since the epoch (Basilisk's SPICE time).
`engine.time_system` (ERFA) converts: `tdb_seconds_between(start, end)`
and `elapsed_to_utc(epoch, t)` carry the leap-second count (37 s since
2017-01-01, ERFA's table and `naif0012.tls`) and the periodic TDB - TT
term. A UTC instant in the plan therefore maps exactly to simulation
time and back. ERFA warns "dubious year" past its table's validity; no
leap second has been announced after 2017-01-01 (IERS Bulletin C).

### 1.9 CCSDS

`engine.ccsds_odm`: OPM, OMM and OEM 3.0 in KVN (CCSDS 502.0-B-3), read
and validate; `oem_from_result` writes a run's trajectory in EME2000 /
UTC. No AEM and no XML.

### 1.10 Timeline, Dashboard, Problems

- `events.Event(kind, spacecraft, start_s, end_s, label, detail, other,
  quantities, note)`; an analysis adds its events through
  `EventTimelineWidget.set_extra_events` (as thermal limits do).
- The Mission Dashboard shows one spacecraft's latest (or cursor) sample:
  mode, pointing, power, RF link.
- Findings (`engine.findings.Finding`) feed the Problems panel.

### 1.11 Monte Carlo

Basilisk batches (`engine.monte_carlo`, `MonteCarloBatch(kind="orbit")`)
and the non-Basilisk thermal batch (`MonteCarloBatch(kind="thermal")`,
seeded `numpy.random.default_rng`). The robustness batch follows the
thermal pattern (section 2.11).

### 1.12 Mounted equipment, field of view, exclusion angles

`MountConfig` on sensors, actuators and the antenna (part, boresight,
full-cone field of view, Sun/Earth/Moon exclusion half-angles, Earth
atmosphere height) and `MountedEquipmentConfig` (cameras, antennas, star
trackers...) in the 3D model; `analyses.blinding` checks exclusions on a
run. The planner reuses the mounts: a camera's boresight and field of
view for acquisitions, the star trackers' exclusion angles as a
constraint, the antenna's boresight for contacts.

### 1.13 Adding a section, a CLI command and a GUI tab

The thermal section is the pattern: `schema/thermal.py` with its own
`version`, `from_dict(..., record, records, fields_of)` called from
`Scenario.from_dict`, `compact()` on save; no scenario-version bump
for a new optional section (`CURRENT_SCHEMA_VERSION` 4, migrations only
for breaking changes); `cli.build_parser` subcommand with `set_defaults`;
`main_window` adds a Run tab and wires `events_changed` to the Timeline.

### 1.14 Speed of the existing propagation

Measured on this machine: an orbit-only Basilisk run of three LEO
spacecraft over seven days (degree-10 gravity, Sun and Moon, drag) takes
22 s at a 30 s step and 84 s at 10 s. The J2-secular propagator of
`predict_passes` takes milliseconds.

### 1.15 What contradicts or is missing for the brief

- No AOS/LOS interpolation, no azimuth mask: added in the planner (the
  recorded series are unchanged).
- No agility model: added (section 2.5), derived from the controller
  the simulation flies, so the plan and the simulation agree.
- No time switching of instruments, transmitter or loads: added through
  Basilisk's `nodeStatusInMsg`, written by the app's executor.
- No AEM: added (KVN, version 2.0).
- `comms_pointing` cannot fly wheels; the executor is built on the
  `fsw_mode` path instead, so wheels, momentum management and the
  existing actuators work under a plan.

## 2. Design

### 2.1 Module layout

A new package `spacemissionstudio/operations/`, numpy only, Basilisk only
in `execution.py`:

| Module | What it does |
|---|---|
| `schema/operations.py` | the scenario's `operations` section, its own version, validation, references |
| `operations/timebase.py` | UTC <-> simulation time (TDB s since epoch) through `engine.time_system` |
| `operations/geometry.py` | planning geometry per spacecraft: position, velocity, Earth orientation, Sun, sunlight; from a run or analytic |
| `operations/targets.py` | point and polygon targets; CSV and GeoJSON import; polygon sampling |
| `operations/opportunities.py` | target windows with geometry and coverage; station passes with AOS/LOS, masks, predicted margin; eclipses; maneuvers |
| `operations/attitude.py` | the attitude of each pointing mode (as the guidance modules compute it); slew angle and slew time |
| `operations/resources.py` | energy (state of charge) and memory profiles of a plan |
| `operations/plan.py` | the plan: activities, unscheduled requests with reasons, provenance; JSON I/O |
| `operations/scheduler.py` | constructive scheduler, local improvement, constraints, contention |
| `operations/execution.py` | the plan executor `SysModel` and its wiring (Basilisk) |
| `operations/verify.py` | plan versus simulation, per activity and resource |
| `operations/exports.py` | pass schedule CSV/ICS, activity CSV/JSON, command schedule JSON/CSV, pointing predictions CSV, report |
| `engine/ccsds_adm.py` | AEM 2.0 KVN writer and reader |
| `operations/whatif.py` | what-if events, replanning from a time |
| `operations/robustness.py` | seeded robustness batch; plan comparison |
| `operations/analysis.py` | one entry point for API, CLI and GUI |
| `gui/plan_widget.py`, `gui/gantt.py` | Run › Plan with a Gantt chart |

### 2.2 Time

Every time in the plan file and every export is UTC, ISO 8601 with `Z`
and milliseconds. Inside the planner, time is simulation time: TDB
seconds since the scenario epoch, the time of every recorded series.
`timebase.to_sim(utc)` is `time_system.tdb_seconds_between(epoch, utc)`
and `timebase.to_utc(t)` is `time_system.elapsed_to_utc(epoch, t)`, so
leap seconds are those of ERFA's table and the TDB - TT term is kept. A
plan spanning a leap second would therefore be right (none is announced).
The scheduler works on float seconds; exports round to the millisecond.

### 2.3 Scenario section `operations`

Scenario level (`Scenario.operations`), optional, its own `version` (1).
No default for a mission value: every duration, power, data rate,
priority, threshold and agility value is a user input. A sketch:

```json
"operations": {
  "version": 1,
  "horizon": {"start_utc": "2027-03-01T00:00:00Z", "end_utc": "2027-03-08T00:00:00Z"},
  "geometry": {"source": "propagation", "step_s": 10.0},
  "targets": [
    {"name": "delta-01", "kind": "point", "latitude_deg": 52.1, "longitude_deg": 5.2,
     "priority": 1, "acquisitions": 2, "max_off_nadir_deg": 25.0, "min_elevation_deg": 50.0,
     "sun_elevation_deg": [20.0, 90.0], "valid_from_utc": null, "valid_to_utc": null,
     "activity": "image"},
    {"name": "field-07", "kind": "polygon", "vertices_deg": [[lat, lon], ...], "...": "..."}
  ],
  "activity_types": [
    {"name": "image", "kind": "acquisition", "duration_s": 20.0, "setup_s": 10.0, "teardown_s": 5.0,
     "pointing": "target", "boresight_b": [0, 0, 1], "instruments": ["camera"], "power_w": 30.0},
    {"name": "downlink", "kind": "contact", "pointing": "station", "boresight_b": [-1, 0, 0],
     "setup_s": 60.0, "teardown_s": 30.0, "min_duration_s": 120.0, "transmitter": true, "power_w": 20.0},
    {"name": "wheel unload", "kind": "momentum_management", "duration_s": 600.0, "pointing": "sun", ...}
  ],
  "requests": [
    {"name": "cal-1", "activity": "star cal", "spacecraft": "eo-1", "count": 1,
     "window_utc": ["...", "..."], "priority": 2, "per": "day"}
  ],
  "stations": [
    {"station": "svalbard", "azimuth_mask": [[0, 5.0], [90, 10.0], ...], "capacity": 1,
     "setup_s": 300.0, "handover_s": 120.0, "unavailable_utc": [["...", "..."]]}
  ],
  "spacecraft": [
    {"spacecraft": "eo-1", "default_pointing": "sun", "agility": {"source": "controller"},
     "min_soc": 0.4, "memory_gbit": null, "max_activities_per_orbit": 4,
     "max_contact_s_per_day": 3600.0, "exclusions_utc": [], "star_tracker_exclusion": true,
     "detector": {"pixel_pitch_um": 5.5, "focal_length_mm": 580.0}}
  ],
  "scheduler": {"seed": 1, "improvement_iterations": 200, "objective": "lexicographic",
                "weights": {"off_nadir": 1.0, "gsd": 0.0, "early": 0.0, "slew": 0.0}},
  "locked": [ {"id": "...", "spacecraft": "...", "type": "...", "start_utc": "...", "end_utc": "...", ...} ],
  "what_if": [ {"kind": "lost_pass", "station": "...", "spacecraft": "...", "at_utc": "..."} ],
  "contingency": {"safe_mode_soc": 0.25, "recover_soc": 0.4, "drop_priority_above_memory": 0.9}
}
```

Validation: names unique; references to spacecraft, stations,
instruments, mounts, activity types and targets resolve (renames follow,
as for the thermal section); windows inside the horizon; the horizon
inside one run (about 104 days) for flying; polygons simple and not
crossing the antimeridian (split them); a contact type needs `rf_link`
and `data_handling` on its spacecraft; the executor needs `fsw_mode` on
the spacecraft (`comms_pointing` and a plan are exclusive).

The plan itself (the scheduler's output) is a separate JSON file (the
"plan file", section 2.8). Locked activities are kept in the scenario,
so a re-run respects them.

### 2.4 Geometry and opportunities

**Source of the trajectory (O-03).** The planner works on the app's own
propagated trajectory where possible:

1. `run`: a finished run's recorded `position_N`, `velocity_N`,
   `eclipse.illumination_factor`, the stations' access series, and the
   Earth's orientation and the Sun (recorded for a scenario with an
   `operations` section, as for thermal, decision T-16);
2. `propagation` (default): a planning propagation, the scenario made
   orbit-only (attitude, devices and analyses off; the force model, drag,
   station keeping and the Mission Sequence's maneuvers kept) and run by
   the existing service over the horizon; about 7 s per spacecraft-week
   at 30 s;
3. `analytic`: the Kepler + J2-secular propagator of `predict_passes`
   (refactored to be shared), for quick what-ifs, flagged as
   approximate in the plan's provenance.

The Earth's orientation is the recorded `J20002Pfix` (ITRF93 with EOP
kernels, IAU_EARTH otherwise); analytic geometry uses the full IAU_EARTH
model (pole and prime meridian). The Sun's direction is the recorded
one, else ERFA's `epv00` (geocentric Sun from the Earth's heliocentric
position); sunlight is the recorded eclipse factor, else a cylindrical
shadow.

**Target windows.** For each spacecraft and target, on the geometry grid:
off-nadir angle eta (at the spacecraft, between nadir and the line of
sight), elevation at the target, Sun elevation at the target, slant
range, and, with a detector, the ground sample distance
`GSD = R p / f` (slant range R, pixel pitch p, focal length f; SMAD).
A window is a run of samples where all of the target's limits hold and
the target is valid; its edges are refined by linear interpolation of
the limiting margin. Polygons are sampled on a grid of points
(cell size set by the user, default none: required for polygons); a
window covers a polygon point when the point is inside the instrument's
footprint (its field of view projected on the ellipsoid along the
boresight pointed at the polygon's centroid), and the window's coverage
fraction is the share of points covered; repeated windows accumulate
coverage.

**Station passes.** From the run's access series when the source is
`run` or `propagation` (the existing access analysis, at the station's
own minimum elevation), else from the analytic geometry. The station's
azimuth mask (piecewise linear in azimuth) raises the minimum elevation
where it is higher. AOS and LOS are interpolated linearly where
`elevation - mask(azimuth)` crosses zero; max elevation, duration and
the predicted link margin at the pass's best and worst elevation
(`link_budget_breakdown`) are kept.

**Planning events.** Eclipses (from the sunlight), maneuvers (the
Mission Sequence's maneuvers at their times in the propagation, and
planned maneuver activities), station outages and spacecraft exclusion
windows.

### 2.5 Activities, attitude and slews

Activity kinds: `acquisition`, `contact` (downlink and uplink),
`maneuver`, `calibration`, `momentum_management`, `user`. Each activity
type has a duration (or a minimum duration for a contact, which takes
the pass), setup and teardown, a pointing mode (`sun`, `nadir`,
`target`, `station`, `inertial` with a fixed attitude), extra power,
instruments switched on (their data rate and power come from
`data_handling`), and for a contact the transmitter.

`operations.attitude` gives the body-to-inertial attitude of each mode
as Basilisk's guidance computes it: `sunSafePoint` (the Sun axis on the
Sun, the rotation about it left free: the minimum rotation from the
previous attitude), `hillPoint` (body = Hill frame), `locationPointing`
(boresight on the target, the minimum rotation from the previous
attitude, as the module's eigen-axis error does), `inertial3D`.

**Slew time (O-08).** The angle between the attitude at the end of one
activity and at the start of the next. Two agility sources:

- `controller` (default when `fsw_mode` is set): the time the simulated
  controller takes, from the same MRP feedback law
  (`L = -K sigma - P omega`, Schaub & Junkins) on the largest principal
  inertia, with the wheels' torque and momentum limits when the
  spacecraft has wheels, until the error is below
  `results.pointing_converged_deg`; integrated once per angle on a grid
  and interpolated;
- `limits`: user-set maximum rate and acceleration, the rest-to-rest
  bang-coast-bang time `2 sqrt(theta/a)` when `theta <= w^2/a`, else
  `theta/w + w/a` (Wie).

### 2.6 Resources

- **Energy:** the panels' generation `S A eta cos(theta) f_sun` (the same
  equation as `simpleSolarPanel`, the same `PowerConfig`, degradation
  and flexible arrays' power as fixed panels) with theta from the
  planned attitude of each interval; loads: the bus idle load, the
  activity's power, the instruments' and transmitter's power while on;
  the battery integrated with the same clipping at 0 and capacity. That
  is the power budget's model, so the planner's state of charge is the
  power budget's for the same attitude history.
- **Memory:** the instruments' data rate while on (always-on instruments,
  such as housekeeping, all the time), minus the downlink rate
  (`rf_link.data_rate_bps`) during a contact while the predicted margin
  is at least `link.required_margin_db`; clipped at 0 and at capacity
  (data lost above it, as the storage unit does).
- **Pointing:** one pointing at a time; a slew between activities.

### 2.7 Scheduler

**Constructive pass (O-10).** Deterministic, priority-driven (Wolfe and
Sorensen 2000; Lemaitre et al. 2002):

1. place locked activities, fixed maneuvers and exclusion windows;
2. contacts: passes sorted by start, for each pass the spacecraft that
   want it (contention) in priority order, then fairness (least contact
   time so far, then name); a contact takes the pass less the setup and
   handover times, if the station has capacity and the spacecraft is
   free;
3. requests (acquisitions, calibrations, momentum management, user
   activities) in order of priority, then fewest opportunities, then
   earliest deadline, then name; for each, its opportunities in order of
   quality (the score's per-activity term); the first that passes every
   hard constraint is taken;
4. resources are checked by simulating each spacecraft's energy and
   memory over the horizon after every insertion (incremental from the
   insertion time); an insertion that breaks a limit is undone.

**Hard constraints.** Minimum state of charge; memory capacity (no data
lost); no overlapping pointing, with the slew time between consecutive
activities; station capacity with setup and handover; maximum
activities per orbit and per day, maximum contact time per day;
exclusion windows; star tracker exclusion angles (when the spacecraft
has star trackers with exclusions and the option is on: the Sun, the
lit Earth limb and the Moon outside each tracker's exclusion cone for
at least one tracker, at the activity's attitude).

**Reasons.** Every unscheduled request gets one reason per opportunity
tried, summarised as the most frequent: `no opportunity` (geometry),
`outside validity`, `conflict` (with which activity), `slew too long`,
`station busy`, `battery`, `memory`, `per-orbit limit`, `per-day limit`,
`exclusion window`, `star tracker`.

**Score (O-11).** Lexicographic by default: first the number of
acquisitions completed at priority 1, then 2, and so on; then the sum of
quality terms `-(w_off_nadir eta/eta_max + w_gsd GSD/GSD_max +
w_early (t - t_window_start)/window) - w_slew total slew time/horizon`.
`objective: "weighted"` replaces the lexicographic part with
`sum priority_weight[p]`. Weights are user-adjustable; their defaults
(1, 0, 0, 0) are conventions of this tool, not physical values.

**Local improvement.** Optional, seeded: remove one to three scheduled
activities at random and re-run the constructive pass for the
unscheduled requests; keep the change when the score improves (a large
neighbourhood search). The seed is recorded in the plan.

**Multi-spacecraft.** One timeline per spacecraft; stations shared;
contention as above.

**Performance.** Measured and documented in the User Manual: the target
is a week for three spacecraft, fifty targets and three stations in a
few seconds of scheduling (the geometry is computed once and cached).

### 2.8 The plan file

JSON, documented (`docs/models/operations.md`): `format`
("spacemissionstudio-plan"), `version` 1, provenance (scenario name and
hash, tool version, geometry source, seed, created UTC), the horizon,
activities (id, spacecraft, type, kind, start/end UTC and sim seconds,
setup/teardown, pointing mode and target, station, instruments,
predicted geometry and resources, locked), unscheduled requests with
reasons, the score, and the resource profiles summarised.

### 2.9 How a plan drives the simulation

**The executor (O-14)**, `operations.execution._PlanExecutor`, the app's
Python `SysModel`, generalises `_CommsPointingArbitrator`:

- Guidance chains built with `fsw.build_guidance` for every mode the
  spacecraft's plan uses: `sunSafePoint`, `hillPoint`, one
  `locationPointing` for targets and one for stations, `inertial3D`. The
  two `locationPointing` chains read a `GroundStateMsg` the executor
  writes: the current target's or station's position, from its geodetic
  coordinates and the Earth's live `J20002Pfix` (the same
  computation as `groundLocation`). `inertial3D`'s reference is set from
  the activity.
- At each step it finds the activity in force at the step's time
  (binary search on start times, including the setup before it and the
  teardown after it) and forwards that mode's `AttGuidMsg`; outside
  activities it forwards the spacecraft's default mode. It never sets
  the attitude: `mrpFeedback` and the actuators slew.
- It writes `DeviceStatusMsg` to each planned instrument's and the
  transmitter's `nodeStatusInMsg` (and to their power sinks), on only
  during the activities that use them; it drives its own
  `simplePowerSink` with the activity's extra power.
- It logs, thinned like the other controllers: the activity index, the
  mode, the active chain's pointing error, the devices' state and the
  contingency state; recorded as `<sc>.plan.*` series.
- Contingency rules (Phase 3): it reads the battery's
  `PowerStorageStatusMsg` and the storage unit's `DataStorageStatusMsg`;
  below the safe-mode state of charge it goes to Sun pointing with
  instruments off until the recovery level; above the memory threshold
  it skips acquisitions below the given priority. Every firing is
  logged.

Maneuvers fly through the existing mechanisms: the Mission Sequence's
maneuvers as they are, and planned maneuver activities turned into a
Mission Sequence (propagate to the epoch, maneuver) when the scenario
has none; station keeping as configured.

"Fly the plan" is a run of the scenario with the plan file attached
(`spacemissionstudio plan verify scenario plan.json` or Run › Plan ›
Fly), with the executor built in place of the spacecraft's single
`fsw_mode` guidance; the data ledger reads the devices' status so its
count follows the switching.

### 2.10 Verification (plan versus simulation)

For each activity: achieved pointing error during the activity (mean and
maximum of the executor's log), whether the slew finished before the
activity's start (pointing error under the convergence threshold at the
start), the off-nadir angle and the Sun elevation from the simulated
trajectory and attitude, the link margin and the data downlinked for a
contact; for each resource: the simulated battery and memory against the
predicted profile (maximum difference). Flags beyond tolerances
(user-set; defaults are tool conventions recorded in the decision log).
Shown as a table and a timeline overlay; written as CSV.

### 2.11 What-if, replanning, robustness, comparison

- What-if events (lost pass, station outage, instrument outage, extra
  request, delayed maneuver) edit a copy of the inputs.
- Replanning from a time T: activities before T are kept as flown
  (locked), the state at T (battery, memory) is taken from the plan's
  profile or a run, and the scheduler runs on (T, horizon end).
- Robustness batch (seeded `default_rng`, recorded): per draw, lost
  passes (probability per pass), degraded link (margin offset), pointing
  time variation (slew time scale), initial battery; the plan is
  re-evaluated (and optionally replanned) per draw; results as a
  `MonteCarloBatch(kind="operations")` summary (completed acquisitions,
  backlog, minimum SoC, data lost).
- Plan comparison: two plan files, per request (scheduled in A, B, both),
  score, resource extremes, contact time.

### 2.12 Surfaces

- **GUI:** Run › Plan: the request and target lists, the Gantt (rows per
  spacecraft and per station: activities, passes, eclipses, slews; the
  state of charge and memory as strips below each spacecraft), edits
  (lock, unlock, delete, move within the window, re-run around locked
  activities), conflicts in place and in the Problems panel; Fly and
  Verify; exports. Plan activities in the Timeline (kind "activity").
  The Dashboard shows the current and next activity, the pointing mode
  and the plan's progress when a run flew a plan.
- **CLI:** `spacemissionstudio plan opportunities|schedule|verify|export|
  replan|robustness|compare`.
- **API:** `api.plan_opportunities`, `api.plan_schedule`, `api.plan_fly`,
  `api.plan_verify`, `api.plan_export`, `api.plan_replan`,
  `api.plan_robustness`, `api.plan_compare`.
- **Exports** with provenance headers (`output_provenance`): CSV, PNG
  and SVG of the Gantt.

## 3. The plan and the Mission Sequence

The plan is a layer of its own, not compiled into Mission Sequence
commands (O-02). The Mission Sequence is an imperative program over one
run: propagate, burn, branch, loop; it has no notion of pointing,
instruments, stations' capacity or resources, and its event stops make
its timing known only when it runs. A plan is declarative, in absolute
UTC, per spacecraft, editable item by item, checked against resources
before any run, and flown by a module inside the run that switches
pointing and devices at step resolution, which a sequence of
propagate/assignment commands could only do at the cost of thousands of
commands and a slower run. The two meet at maneuvers: the Mission
Sequence's maneuvers are planning events the scheduler works around;
planned maneuvers become a generated Mission Sequence when the scenario
has none. A scenario keeps its sequence while a plan is flown.

## 4. Basilisk modules used

All through the public API, as the existing code already uses them:

- `groundLocation` (access, the existing analysis), `eclipse`,
  `spiceInterface` planet state messages (`J20002Pfix`, positions);
- guidance: `sunSafePoint`, `hillPoint`, `locationPointing`,
  `inertial3D`, `attTrackingError`; control: `mrpFeedback`,
  `rwMotorTorque`, the existing actuators;
- `simplePowerSink`, `simpleBattery`, `simpleSolarPanel`;
  `simpleInstrument`, `partitionedStorageUnit`,
  `spaceToGroundTransmitter`, through `nodeStatusInMsg`
  (`DeviceStatusMsg`), `PowerStorageStatusMsg`, `DataStorageStatusMsg`;
- `messaging.GroundStateMsg`, `AttGuidMsg`, `sysModel.SysModel` (the
  executor, as `_CommsPointingArbitrator`).

No Basilisk change is needed: everything missing is SpaceMissionStudio
code.

## 5. Standards and sources

- Time: ECSS-E-ST-10-09C (as `engine.time_system`); ERFA (SOFA) for
  leap seconds and TDB; IERS Bulletin C for the leap-second status.
- CCSDS 502.0-B-3 Orbit Data Messages (OEM 3.0, existing).
- CCSDS 504.0-B-2 Attitude Data Messages (January 2024), AEM 2.0 in KVN:
  `CCSDS_AEM_VERS = 2.0`; header `CREATION_DATE`, `ORIGINATOR`
  (mandatory), `MESSAGE_ID`, `CLASSIFICATION`, `COMMENT`; metadata
  `OBJECT_NAME`, `OBJECT_ID`, `CENTER_NAME` (optional), `REF_FRAME_A`,
  `REF_FRAME_B`, `TIME_SYSTEM`, `START_TIME`, `USEABLE_START_TIME`,
  `USEABLE_STOP_TIME`, `STOP_TIME`, `ATTITUDE_TYPE`, `INTERPOLATION_METHOD`,
  `INTERPOLATION_DEGREE`; quaternion components `Q1 Q2 Q3 QC` (scalar
  last); `ATTITUDE_DIR` and `QUATERNION_TYPE` of version 1 are gone.
  Confirmed from the CCSDS NDM/XML 4.0.0 schema for AEM 2.0 (as shipped
  in the `ccsds-ndm` 3.1.1 package, read only, not used or bundled); the
  Blue Book itself was not reachable from this environment (O-20).
- RFC 5545 (iCalendar): `VCALENDAR`/`VEVENT`, `VERSION:2.0`, `PRODID`,
  `UID`, `DTSTAMP`, `DTSTART`/`DTEND` in UTC with `Z`, CRLF line ends,
  lines folded at 75 octets, text escaping.
- ECSS-E-ST-70-41C (Packet Utilization Standard): terminology only for
  the command schedule (service 11, "time-based scheduling"; a
  "time-tagged" request with its release time); no binary telecommand.
- Slew: B. Wie, *Space Vehicle Dynamics and Control*, 2nd ed., AIAA,
  2008 (rest-to-rest bang-coast-bang); H. Schaub, J. L. Junkins,
  *Analytical Mechanics of Space Systems*, AIAA (MRP feedback), as
  Basilisk's `mrpFeedback` documents it.
- GSD: J. R. Wertz, D. F. Everett, J. J. Puschell (eds.), *Space Mission
  Engineering: The New SMAD*, Microcosm, 2011 (ground sample distance
  from slant range, pixel size and focal length).
- Scheduling: W. J. Wolfe, S. E. Sorensen, "Three scheduling algorithms
  applied to the Earth observing systems domain", *Management Science*
  46(1), 2000; M. Lemaitre, G. Verfaillie, F. Jouhaud, J.-M. Lachiver,
  N. Bataille, "Selecting and scheduling observations of agile
  satellites", *Aerospace Science and Technology* 6(5), 2002.
- Independent Sun position for verification: the low-precision solar
  coordinates of the *Astronomical Almanac* (section C), about 0.01 deg.
- Earth: WGS-84 (`engine.geodesy`); IAU_EARTH rotation (the IAU WGCCRE
  report, as NAIF's `pck00010.tpc`).
- GeoJSON: RFC 7946 (Point, Polygon; WGS-84 longitude, latitude order).

## 6. Implementation plan

Mirrored in
[operations-planning-progress.md](operations-planning-progress.md).

Phase 1:

1. Schema `operations` section: validation, references, renames,
   compact; recording the Earth's orientation and the Sun for it.
2. Time base and geometry (run, propagation, analytic); shared
   propagator refactor.
3. Targets (points, polygons, CSV, GeoJSON) and opportunities (target
   windows, coverage, passes with masks and AOS/LOS, eclipses,
   maneuvers).
4. Attitude per mode, slew time (controller and limits).
5. Resources: energy and memory profiles.
6. Plan model and file.
7. Scheduler: constructive, constraints, reasons, locked, contention,
   local improvement, score.
8. Analysis entry point, API, CLI (`plan opportunities`, `plan
   schedule`).
9. GUI: Run › Plan, Gantt, edits, Problems, Timeline.

Phase 2:

10. Executor `SysModel` and its wiring; device switching; maneuvers.
11. Verification plan versus simulation; CLI `plan verify`.
12. Dashboard: current and next activity, mode, progress.
13. Exports: pass schedule CSV/ICS, activities CSV/JSON, command
    schedule JSON/CSV, pointing predictions CSV, AEM (and OEM extended),
    report; CLI `plan export`.

Phase 3:

14. What-if events and replanning from a time.
15. Contingency rules in the executor.
16. Robustness batch and plan comparison.

Then:

17. Templates: the 150 kg EO microsatellite and the three-spacecraft
    constellation, claims, golden files.
18. V&V records and tests.
19. Documentation; final checks; report.
