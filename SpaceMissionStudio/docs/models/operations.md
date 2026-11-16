# Operations planning: the method and the files

How the planner (requirement SRS-F-30) builds a plan, how the simulation
flies it, how the two are compared, and the files it reads and writes.
The how-to is [Operations planning](../user-manual/operations.md). The
design and its decisions (O-nn) are in
`docs/developer/operations-planning-design.md` and
`docs/developer/operations-planning-decisions.md`. The checks are in
[the V&V record](../../compliance/validation/operations-vv.md).

Nothing in the planner changes the Basilisk framework. It uses
Basilisk's own modules (an orbit-only propagation, `groundLocation`,
`simpleSolarPanel`'s equation, the storage unit, the guidance modes,
`C2EP`) and two SpaceMissionStudio `SysModel`s, the plan executor.

## Time

Inside, times are simulation seconds: TDB seconds since the scenario's
epoch, as everywhere in the app. In files they are UTC with a `Z`,
rounded to the millisecond, converted with ERFA (leap seconds included).
Both are written (O-05).

## Geometry

The planner samples each spacecraft's position, attitude references, the
Sun and the Earth's orientation on a uniform grid of `geometry.step_s`
(10 s unless the section says otherwise; a tool convention). The grid
starts at the horizon's start, and its last sample is at or before its
end (O-21). There are three sources:

| `geometry.source` | Trajectory | Earth orientation |
|---|---|---|
| `propagation` (default) | An orbit-only Basilisk run of the scenario's force model over the horizon | The run's: ITRF93 with the Earth orientation files, else IAU_EARTH |
| `run` | A finished run that covers the horizon | The run's |
| `analytic` | Mean elements with J2 secular rates (`cl_mean_osc_map`) | ERFA `c2t06a` (IAU 2006/2000A, with the IERS polar motion and UT1 - UTC when the files cover the horizon) |

The analytic source agrees with the propagation to about 7 km over a
day. ITRF93 and IAU_EARTH differ by about 10 km on the ground, which
moves an off-nadir angle by up to 1 deg (see Limitations).

## Opportunities

- **Target windows:** the spans where every limit of a target holds:
  off-nadir angle, the spacecraft's elevation seen from the target, the
  Sun's elevation at the target, and the validity span. Edges are
  interpolated linearly between samples. A polygon is sampled at cell
  centres (`cell_km`). A window's coverage is the share of cells inside
  the instrument's footprint (`detector.field_of_view_deg`), and its
  ground sample distance comes from the detector's pixel pitch and focal
  length.
- **Passes:** the spans where a station sees the spacecraft above its
  minimum elevation and its azimuth mask (the mask's elevation is
  interpolated by azimuth and wraps at 360 deg). The peak comes from a
  parabola through the three samples around it. The predicted link
  margin at the lowest and the highest elevation comes from the app's
  link budget.
- **Eclipses:** a cylindrical shadow.

## Attitude and slews

Each pointing mode's attitude is computed as the guidance the executor
flies computes it (O-09): `sunSafePoint` (`sun`), `hillPoint` (`nadir`),
`locationPointing` (`target`, `station`) and `inertial3D` (`inertial`).
A pointed axis turns by the smallest rotation.

A slew's duration comes from a model of the attitude controller (O-08):
the closed-loop MRP PD response `I θ'' = -K tan(θ/4) - P θ'`. The model
uses the largest principal inertia, the controller's K and P, and the
wheels' torque and momentum limits about the weakest axis. It counts the
slew as done when the angle settles within half of
`results.pointing_converged_deg` (2.5 deg). Half the threshold is a
margin: the one-axis model ignores the three-axis coupling and a moving
target (O-25). With `agility.source: limits` a bang-coast-bang profile of
a given rate and acceleration is used instead (Wie).

## Resources

The energy is the power budget's equation:

`S A η cos θ f_sun - loads`

with θ from the planned attitude, integrated with clipping at 0 and the
capacity. The loads are the bus idle power, the activity's power and the
power of instruments and the transmitter while they are on. The memory
grows with each instrument's data rate while it is on (always-on
instruments all the time). During a contact it drains at the link's data
rate while the predicted margin closes. It is clipped at 0 and at
capacity; data above the capacity is lost.

Each value is the state at the end of its step; the plan file labels it
with that time (O-26).

## The scheduler

A deterministic, priority-driven constructive pass (O-10; Wolfe and
Sorensen 2000; Lemaître et al. 2002), then an optional seeded
improvement:

1. Place the locked activities, fixed maneuvers and exclusions.
2. Contacts: passes in time order. When several spacecraft want a pass
   (contention), the lower `contact_priority` wins, then the spacecraft
   with the least contact time so far (O-12). A contact takes the pass,
   less the station's setup and handover times, while the station has
   capacity and the spacecraft is free.
3. Requests (acquisitions, calibrations, momentum management, user
   activities): ordered by priority, then fewest opportunities, then
   earliest deadline, then name. For each, its opportunities are tried
   from the best (the smallest off-nadir angle) down. The first that
   keeps every hard constraint is taken. A request that collides with
   exactly one contact may shorten it, down to the contact type's
   `min_duration_s` (O-21).
4. After each insertion, the energy and memory are evaluated
   incrementally from the insertion's time. An insertion that breaks a
   limit is undone.

**Hard constraints:**
- the battery's planned floor (`min_soc`) and the memory capacity,
  checked sample by sample;
- one pointing at a time, with the slew between activities;
- the station's capacity, with its setup and handover times;
- per-orbit and per-day activity limits, and contact time per day;
- exclusion windows and outages;
- star-tracker exclusion: at least one tracker clear of the Sun, the
  Earth's limb (with its atmosphere) and the Moon.

**Reasons (O-13).** For a request it could not place, the planner records
one reason per chance tried and reports the most frequent. The reasons:
- `no_opportunity`
- `outside_validity`
- `too_short`
- `lost_pass`
- `exclusion`
- `conflict`
- `slew`
- `station_busy`
- `per_orbit`
- `per_day`
- `star_tracker`
- `battery`
- `memory`

**Score (O-11).** The default is lexicographic. First come the
acquisitions placed at priority 1, then at priority 2, and so on. Then
comes a quality term:

`-Σ (w_off_nadir η/η_max + w_gsd GSD/GSD_max + w_early (t - t_start)/horizon) - w_slew Σ slew time / horizon`

The sum runs over the acquisitions. The same per-acquisition term orders
the candidates of a request. With `objective: weighted`,
`Σ priority_weight[p] · count[p]` replaces the lexicographic part. The
weights' defaults (off-nadir 1, the others 0) are conventions of this
tool.

**Improvement.** For `improvement_iterations` steps, seeded with
`scheduler.seed`: take one to three unlocked activities out at random,
place every request not held, and keep the result only when the score is
better (a large-neighbourhood search). The same inputs and seed give the
same plan.

## The plan and the Mission Sequence

A plan is a layer of its own, not compiled into Mission Sequence
commands (O-02). The Mission Sequence is an imperative program over one
run. A plan is declarative and in UTC. It holds activities per spacecraft
and is checked against resources before any run. A module inside the run
flies it.

The two meet at maneuvers. The Mission Sequence's maneuvers are planning
events the scheduler works around. When the scenario has no sequence,
the planned maneuvers become a generated one (propagate to the burn,
burn, propagate to the plan's end; O-16).

## Flying the plan

`PlanWriter` (priority 60) writes, at every step, the mode and the
device commands of the activity in force. `PlanArbitrator` passes the
guidance of that mode to the controller (O-14). Instruments and the
transmitter are switched through Basilisk's `DeviceCmdMsg`
(the data nodes) and `DeviceStatusMsg` (their power sinks; O-15).
Contingency rules act inside the run:
- below `safe_mode_soc`: Sun pointing and instruments off, until the
  state of charge is above `recover_soc` again;
- above `memory_fraction` of the memory: acquisitions of priority
  `drop_priority` or lower are dropped.

The run records `<spacecraft>.plan.mode`, `.activity`,
`.pointing_error_deg` and `.contingency`. A scenario run without a plan
builds no executor and is unchanged.

## Verification

The flight is compared with the plan where the run flew. The default
tolerances are conventions (O-19), adjustable in `verification`:

| Check | Default |
|---|---|
| Pointing error at each activity's start | `results.pointing_converged_deg` (5 deg) |
| State of charge | 5 percentage points |
| Memory | 2 % of the capacity |
| A target's off-nadir angle | 1 deg |
| The Sun's elevation at a target | 0.5 deg |

## What-if, replanning, robustness, comparison

- **What-if events** change a copy of the inputs:
  - `lost_pass`;
  - `station_outage`;
  - `instrument_outage`;
  - `extra_request` (a target or request kept `enabled: false`);
  - `delayed_maneuver`.
- **Replanning from T** keeps, with their ids, the activities that start
  more than 1 ms before T (O-22). It counts what they did as done and
  places nothing new before T.
- **Robustness** draws, per run (`numpy.random.default_rng(seed)`):
  - lost passes;
  - a normal offset on every link margin;
  - a uniform factor on every slew time;
  - an initial state of charge.

  It re-checks the plan activity by activity, or replans. The batch is a
  Monte Carlo batch of kind `operations` (O-18).
- **Comparison** lists, per request, whether each plan holds it. Per
  spacecraft it gives the activities, contact time, lowest state of
  charge, data lost and the score.

## The plan file

`spacemissionstudio-plan`, version 1, JSON:

| Key | Content |
|---|---|
| `format`, `version` | `"spacemissionstudio-plan"`, `1` |
| `epoch_utc`, `start_s`, `end_s`, `start_utc`, `end_utc` | The scenario's epoch and the horizon |
| `activities` | Each: `id`, `spacecraft`, `type`, `kind`, `start_s`, `end_s`, `start_utc`, `end_utc`, `setup_s`, `teardown_s`, `pointing`, `target`, `station`, `request`, `priority`, `locked`, `predicted` (off-nadir, elevation, Sun elevation, range, GSD, coverage, slew angle and time, the pointing start, link margins, downlink capacity) |
| `unscheduled` | Each: `request`, `spacecraft`, `kind`, `priority`, `reason`, `counts` (per reason), `needed`, `placed` |
| `score` | `objective`, `value` |
| `provenance` | Tool and version, scenario name and SHA-256, creation time, geometry source and step, seed, iterations, objective, weights, slew models, times per stage, a replan's origin and what-if events, and `"note": "a planning product: not a flight command load"` |
| `resources` | Per spacecraft: `time_s` (each the end of its step), `soc`, `memory_bit` (every 60 s or the step), `min_soc`, `max_memory_bit`, `lost_bit`, `downlinked_bit`, `capacity_wh`, `capacity_bit` |
| `contention` | Each contested pass: `station`, `aos_utc`, `wanted_by`, `served` |
| `notes` | What the planner noted (a locked activity that breaks a limit, a slew without time) |

## The activity timeline

`activities.json` (`spacemissionstudio-activities`, version 1) has:
- `provenance`;
- `horizon`;
- `activities`: each with the plan file's fields, as UTC, and
  `predicted`;
- `unscheduled`: with the reason's text.

`activities.csv` has the same columns, one row per activity, and a
`.provenance.json` beside it.

## The command schedule

`commands.json` (`spacemissionstudio-command-schedule`, version 1) holds
`provenance`, `terminology` and `requests`, in release order.

Each request has these fields:
- `release_time_utc`;
- `spacecraft`;
- `command`;
- `arguments`;
- `activity`.

The commands are:
- `SET_POINTING` (`mode`, and `target` or `station`);
- `INSTRUMENT_ON`, `INSTRUMENT_OFF` (`instrument`);
- `TRANSMITTER_ON`, `TRANSMITTER_OFF` (`station`);
- `LOAD_ON`, `LOAD_OFF` (`power_w`);
- `MANEUVER` (`delta_v_m_s`, `frame`).

The terms follow the Packet Utilization Standard's time-based scheduling
service (ECSS-E-ST-70-41C, service 11): time-tagged requests with a
release time. They are not telecommands: no packet, binary format or
database (XTCE, SCOS, YAMCS) is written. `commands.csv` has the same
rows.

## Other products

| File | Standard and content |
|---|---|
| `passes.csv` | Every pass: station, spacecraft, AOS, LOS, duration, highest elevation and its time, predicted margins, the contact planned on it |
| `passes.ics` | iCalendar (RFC 5545): one event per contact, with UID, DTSTAMP, UTC times, folded lines and the provenance in `X-` properties |
| `pointing.csv` | Each contact's azimuth, elevation and range from its station |
| `<spacecraft>.oem` | CCSDS OEM (502.0-B-3), the planned trajectory, written by the app's OEM writer |
| `<spacecraft>.aem` | CCSDS AEM 2.0 (504.0-B-2): `REF_FRAME_A` EME2000, `REF_FRAME_B` SC_BODY_1, quaternions `Q1 Q2 Q3 QC` (scalar last) of the rotation from A to B, stated in a `COMMENT` (O-20) |
| `report.md` | The plan in words, and its verification when there is one |
