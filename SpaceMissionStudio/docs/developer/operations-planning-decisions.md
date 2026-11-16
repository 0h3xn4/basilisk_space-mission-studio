# Mission operations planning: decision log

Every non-trivial choice made while building the operations planning
layer, with the alternatives and the reason, in place of asking the
owner. Design: [operations-planning-design.md](operations-planning-design.md);
progress: [operations-planning-progress.md](operations-planning-progress.md).

## O-01 Two layers: a planner on numpy, the Basilisk run to check it (2026-11-16)

**Chosen:** the planner (opportunities, resources, scheduler) is numpy
only and works on a geometry computed once; the existing Basilisk
simulation flies the plan through an executor module, and the two are
compared automatically. **Alternatives:** schedule inside the
simulation (every candidate would cost a run); plan without flying (no
check of slews, pointing and resources). **Why:** as the brief asks;
scheduling needs thousands of feasibility checks, a run needs seconds to
minutes.

## O-02 The plan is its own layer, not Mission Sequence commands (2026-11-16)

**Chosen:** a plan file flown by an executor `SysModel`; the Mission
Sequence's maneuvers are planning events; planned maneuvers become a
generated Mission Sequence when the scenario has none. **Alternatives:**
compile the plan into propagate/assignment commands. **Why:** the
sequence has no pointing, devices or resources, its event stops are
known only when it runs, and step-resolution switching through commands
would need thousands of them (design section 3).

## O-03 Trajectory source: a run, a planning propagation, or analytic (2026-11-16)

**Chosen:** `geometry.source` = `run` (a finished run's recorded
states), `propagation` (default: the scenario made orbit-only and run by
the existing service over the horizon) or `analytic` (the Kepler +
J2-secular propagator already used by `predict_passes`, shared rather
than copied). **Alternatives:** analytic only (fast, but drag and the
force model differ from the simulation the plan is checked against);
run only (a full-attitude run before every plan). **Why:** the brief
asks for the app's own propagated trajectory where possible; an
orbit-only propagation costs about 7 s per spacecraft-week at 30 s
(measured, design 1.14) and has the simulation's force model; the
analytic source stays for quick what-ifs and is flagged in the plan's
provenance.

## O-04 Earth orientation and Sun for planning (2026-11-16)

**Chosen:** record the central body's `J20002Pfix` and the Sun's
position for a scenario with an `operations` section (extending the
thermal analysis's recording, T-16) and use them; the analytic source
uses the full IAU_EARTH model (pole right ascension and declination
rates and the prime meridian) and ERFA's `epv00` for the Sun.
**Alternatives:** the prime-meridian-only angle of `predict_passes`.
**Why:** IAU_EARTH's pole has moved about 0.17 deg from J2000 by 2026
(-0.641 and -0.557 deg per century), about 18 km on the ground: too much
for target windows. `predict_passes` is left as it is (its outputs are
only a pre-run summary).

## O-05 Times in the plan: UTC strings outside, simulation seconds inside (2026-11-16)

**Chosen:** UTC ISO 8601 with `Z` and milliseconds in files and
exports; TDB seconds since the epoch inside, converted only through
`engine.time_system` (ERFA). **Alternatives:** UTC seconds since epoch
inside. **Why:** every recorded series is in simulation time, so the
executor and the verification need no conversion; ERFA carries the
leap seconds and TDB - TT exactly; one conversion place.

## O-06 One `operations` section at scenario level with its own version (2026-11-16)

**Chosen:** `Scenario.operations` (optional, `version` 1), holding
targets, activity types, requests, station planning settings, per
spacecraft planning settings, scheduler settings, locked activities,
what-if events and contingency rules. `CURRENT_SCHEMA_VERSION` stays 4.
**Alternatives:** settings spread over `GroundStationConfig` and
`SpacecraftConfig`. **Why:** stations and spacecraft are shared with the
simulation; planning settings change without touching them; the thermal
section's pattern (T-02).

## O-07 No default for a mission value (2026-11-16)

**Chosen:** durations, power, data rates, priorities, minimum state of
charge, agility limits, masks, detector values and thresholds have no
default; validation asks for them where they are needed. **Why:** the
brief: mission-specific values are user inputs. The tool conventions
that do have defaults (score weights, verification tolerances,
improvement iterations, geometry step) are recorded as conventions here.

## O-08 Slew time from the controller the simulation flies (2026-11-16)

**Chosen:** `agility.source = "controller"`: the closed-loop slew time of
the spacecraft's own MRP feedback (`L = -K sigma - P omega`, gains as
`engine.control_gains` scales them), on the largest principal inertia,
with the wheels' torque and momentum limits, integrated to the
convergence threshold `results.pointing_converged_deg`; or
`"limits"`: user maximum rate and acceleration, bang-coast-bang (Wie).
**Alternatives:** bang-coast-bang only. **Why:** a time-optimal slew is
faster than the simulated PD controller, so a plan built on it would
fail its own verification; the controller model predicts what the run
will do.

## O-09 Attitude of each mode as Basilisk's guidance computes it (2026-11-16)

**Chosen:** the planner's attitude per mode follows the modules the
executor will fly (Hill frame for `nadir`, boresight on the target with
the minimum rotation for `target` and `station`, the Sun axis on the Sun
for `sun`, a fixed attitude for `inertial`). **Why:** the energy model
and the slew angles depend on it; matching the flown guidance keeps the
plan and the simulation close. The free rotation about a pointed axis is
taken as the minimum rotation from the previous attitude, the
eigen-axis behaviour of `locationPointing` and `sunSafePoint`; it is an
approximation of the closed-loop path, checked by the verification.

## O-10 Priority-driven constructive scheduling with seeded improvement (2026-11-16)

**Chosen:** a deterministic greedy pass (locked and fixed events,
contacts with contention, then requests by priority, fewest
opportunities, deadline, name; opportunities by quality), every
insertion checked against all hard constraints and the resource
profiles; then an optional seeded large-neighbourhood search (remove one
to three activities, re-insert greedily, keep improvements).
**Alternatives:** an exact solver (MILP or constraint programming: a new
dependency and exponential time; out of scope); a genetic algorithm (less
predictable, harder to explain). **Why:** standard in Earth-observation
scheduling (Wolfe and Sorensen 2000; Lemaitre et al. 2002), fast,
deterministic, and each rejection has a reason; the optimality gap is
measured on small instances against brute force.

## O-11 Score: lexicographic by priority, then quality (2026-11-16)

**Chosen:** completed acquisitions per priority level compared in order
(1 first), then a weighted quality sum (off-nadir, GSD, earliness, slew
time); `objective: "weighted"` with per-priority weights as the
alternative. Default quality weights 1 (off-nadir), 0, 0, 0.
**Why:** a lexicographic objective needs no arbitrary exchange rate
between priorities; the weights are tool conventions, adjustable, and
written into the plan file.

## O-12 Contention: priority, then fairness (2026-11-16)

**Chosen:** when spacecraft want the same station at the same time, the
higher spacecraft contact priority wins; equal priorities go to the
spacecraft with the least contact time scheduled so far, then by name.
**Why:** predictable, and fair over a week; recorded per contested pass
in the plan.

## O-13 Unscheduled reasons are counted per opportunity (2026-11-16)

**Chosen:** each opportunity tried for a request records the first hard
constraint it fails; the request's reason is the most frequent, with the
full count kept. **Why:** "why was this not scheduled" has one honest
answer per window; the summary is what a user reads first.

## O-14 The executor generalises the comms arbitrator on the fsw_mode path (2026-11-16)

**Chosen:** `_PlanExecutor` (app `SysModel`) forwards one of several
guidance chains' `AttGuidMsg`, writes the target's or station's
`GroundStateMsg` for `locationPointing`, and switches devices through
`nodeStatusInMsg`; it is built in place of the spacecraft's single
`fsw_mode` guidance, so wheels, momentum management and the other
actuators fly. **Alternatives:** extend `comms_pointing` (idealized
actuation only); one `groundLocation` per target (many modules, and the
station chain would still need switching). **Why:** reuse of the
`fsw_mode` actuator chain; one module, public messages only.

## O-15 Device switching through Basilisk's node status messages (2026-11-16)

**Chosen:** the executor writes `DeviceStatusMsg` to the planned
instruments, the transmitter and their power sinks; `_DataLedger` reads
the same status so its count follows. **Why:** every Basilisk data and
power node has `nodeStatusInMsg`; it is the public way to switch them.

## O-16 Planned maneuvers fly through the Mission Sequence (2026-11-16)

**Chosen:** a planned maneuver activity (delta-v in a frame) becomes a
generated Mission Sequence (propagate to its epoch, maneuver) when the
scenario has none; with a sequence, its own maneuvers are the planning
events and planned maneuvers are refused. **Why:** the brief: maneuvers
via the existing mechanisms.

## O-17 Polygons sampled on a grid; coverage by footprint (2026-11-16)

**Chosen:** a polygon is sampled at the centres of a latitude-longitude
grid of user cell size inside it; a window covers the points inside the
instrument's footprint (field-of-view cone around the boresight
intersected with the ellipsoid); coverage accumulates over the plan.
**Alternatives:** strip decomposition (swaths along the track): more
exact for push-broom imagers, much more code. **Why:** simple, honest,
and the coverage fraction converges with the cell size (checked).

## O-18 Robustness on the planner, not a Basilisk batch (2026-11-16)

**Chosen:** the robustness batch perturbs the plan's inputs and
re-evaluates (and optionally replans) with the planner's own models,
seeded, as a `MonteCarloBatch(kind="operations")`; one draw can be
flown on request. **Alternatives:** Basilisk Monte Carlo per draw (a
full run each). **Why:** the brief's quantities (lost passes, link,
pointing time, initial battery) are planner inputs; the thermal batch
set the pattern.

## O-19 Verification tolerances are tool conventions (2026-11-16)

**Chosen:** defaults, adjustable: pointing error at the activity's
start below `results.pointing_converged_deg`; state of charge within 5
percentage points; memory within 2 % of capacity; off-nadir within 1
deg; Sun elevation within 0.5 deg. **Why:** no standard gives these;
they are what the planner's simplifications (attitude about the
boresight, panel cosine, step resolution) can promise; recorded and
shown with the results.

## O-20 AEM version 2.0 from the CCSDS XML schema; Blue Book unreachable (2026-11-16)

**Found:** `public.ccsds.org`, `orekit.org` and other mirrors are
refused by this environment's network policy. **Chosen:** the AEM 2.0
keywords and the quaternion order (`Q1 Q2 Q3 QC`, scalar last) from the
CCSDS NDM/XML 4.0.0 schema for AEM 2.0, read from the `ccsds-ndm` 3.1.1
package (GPL-3.0; only read as a reference, nothing copied or bundled).
The schema confirms the keywords and the order; the rotation's
direction is taken as from `REF_FRAME_A` (EME2000) to `REF_FRAME_B`
(`SC_BODY_1`), the convention of version 1's `ATTITUDE_DIR = A2B`,
and is stated in each file's `COMMENT`. To confirm against the Blue
Book (section 4 of CCSDS 504.0-B-2) when it can be read.
