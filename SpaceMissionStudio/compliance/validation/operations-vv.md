# Verification and validation: operations planning

This is the record of how the operations planner (requirement SRS-F-30) was
checked. Each case is a test that runs in the suite. The reference is a
closed-form result, Basilisk's own modules or a run of the simulation,
a brute-force search, or a cited standard. It is never the code under
test. Measured 2026-11-16 on Python 3.14.6, Basilisk 2.12.0, x86-64 with
4 cores. The design is in `docs/developer/operations-planning-design.md`.
The decisions (O-nn) are in `docs/developer/operations-planning-decisions.md`.

A plan is a planning product, not a flight command load: every export
says so.

## Time and geometry (`tests/test_operations_geometry.py`)

| Case | Reference | Tolerance | Result |
|---|---|---|---|
| UTC text to simulation time (TDB seconds since the epoch) and back, across a leap second | ERFA, as the engine's time system | 1 ms (UTC text is rounded to the millisecond) | Equal |
| The sample grid | Uniform at the asked step from the horizon's start, the last sample at or before its end (O-21) | exact | Equal |
| Station elevation, azimuth and range from the planner's geometry against Basilisk's `groundLocation` on the same run | The run's access series | 1e-6 deg, 1e-5 deg, 1 mm | Within |
| Earth orientation without a run: ERFA `c2t06a` (IAU 2006/2000A with the IERS polar motion and UT1-UTC) against the run's ITRF93 kernels | The run's `J20002Pfix` | 50 m on the ground | About 13 m. IAU_EARTH, the previous choice, was 0.094 deg (about 10 km) off (O-04) |
| The analytic geometry (mean elements, J2 secular rates) against an orbit-only Basilisk propagation of the same scenario, one day | The propagation | 10 km | 7.0 km at most, 4.8 km mean |
| The Sun's elevation at a site | The almanac formula (declination and hour angle) | 0.1 deg | Within |
| A run that does not cover the horizon | Refused, with the span it covers | - | Refused |

## Opportunities (`tests/test_operations_opportunities.py`)

| Case | Reference | Result |
|---|---|---|
| Window and pass edges | Linear interpolation of the margin between the two samples around each edge | At the interpolated root |
| An azimuth mask | Raises the minimum elevation by azimuth and wraps at 360 deg; a masked pass is shorter and inside the unmasked one | As expected |
| A target window | Every sample inside meets every limit (off-nadir, elevation, Sun elevation, validity); the off-nadir angle recomputed independently from the positions | Limits kept to 1e-9 deg; off-nadir within 0.2 deg (the ellipsoid's normal against the radius) |
| Eclipses | The cylindrical shadow from the same Sun vector | As expected |
| A polygon target | Sampled at cell centres inside it; coverage is the share of cells in the footprint | As expected |
| Targets from CSV and GeoJSON | The files' own coordinates | Equal; a bad file is refused with its line or feature named |

## Attitude, slews and resources (`tests/test_operations_attitude_resources.py`)

| Case | Reference | Result |
|---|---|---|
| Pointing an axis | The smallest rotation (Rodrigues): the axis kept, 90 and 180 deg cases | As expected; chained rotations stay orthonormal to 1e-12 |
| Hill frame and an inertial MRP reference | Basilisk's `hillPoint` and `inertial3D` definitions | Equal |
| Bang-coast-bang slew | Its closed form (Wie) | Equal |
| The controller slew model | The linear PD response `I θ'' + P θ' + K θ/4 = 0`, solved in closed form for a small angle | Within 0.2 s |
| The planner's slews | Settle to half the 5 deg convergence threshold the verification checks (O-25) | Template 35's flown activities start 1.0 to 3.1 deg off; before O-25 two started 5.7 and 5.9 deg off |
| Energy | The power budget's own equation (generation minus loads, clipped at empty and full) | Generation equal to 1e-9 relative; nothing in eclipse |
| Memory and power of an acquisition and a contact | Hand calculation: rate x time in, link fraction x data rate out | Equal |

## The scheduler (`tests/test_operations_scheduler.py`)

| Case | Reference | Result |
|---|---|---|
| Hard constraints over seeded random instances | Checked one by one on every plan: no overlap, slews fit, battery floor and memory sample by sample, per-orbit and per-day limits, exclusions, station capacity | Never broken |
| Determinism | The same inputs and seed twice (and, measured by hand on template 36, under two Python hash seeds) | The same plan |
| Small instances | Brute force over every placement in every window | The planner's score is within 1 acquisition of the optimum on every instance |
| The improvement step | The plan before it | Never worse |
| Locked activities | Kept as they are; the rest planned around them | As expected |
| Requests not placed | Each with its reason, counted over the chances tried | As expected |
| A contested pass | Priority first, then fairness (O-12) | As expected; template 36 gives each of three spacecraft 11 contacts |

## Flying the plan in Basilisk (`tests/test_operations_flight.py`)

The executor (`PlanWriter`, `PlanArbitrator`: SpaceMissionStudio's own
`SysModel`s, decision O-14) switches pointing and devices at the plan's
times. The attitude comes from Basilisk's guidance and control.

| Case | Reference | Tolerance | Result |
|---|---|---|---|
| A two-hour plan on template 26's spacecraft (gains K 1, P 8): every activity in its mode over its interval | The executor's activity log | exact | Equal |
| The camera's data | 80 kbit/s x 20 s per image on top of housekeeping | 0.2 % | Within |
| Off-nadir angle at an image | The planner's prediction | 1 deg | 43.66 deg planned, 43.43 deg flown |
| Sun elevation at the target | The planner's prediction | 0.5 deg | 10.962 deg both |
| Pointing error at each activity's start | The 5 deg convergence threshold | 5 deg | 0.82 to 2.28 deg |
| State of charge | The plan's profile | 5 points | 1.23 points at most; lowest 265.0 Wh planned, 265.1 Wh flown |
| Memory | The plan's profile | 2 % of the capacity | 0.12 % |
| Template 35, its first six hours (`tests/test_template_claims.py`) | The same checks | The same | Every activity flown with its slew finished; state of charge within 1.6 points; memory within 0.09 % of the capacity (O-26) |
| The template's default (soft) gains | The verification | - | Flags "slew not finished" with the angle |
| The same scenario run without a plan | The run before this feature | - | No executor and no plan series; templates 26 and 19 give their recorded outputs |
| Stop during a flight | `SimulationCancelled` after the first chunk | - | As expected |

## Exports (`tests/test_operations_exports.py`)

| Case | Reference | Result |
|---|---|---|
| Passes as iCalendar | RFC 5545: CRLF line ends, lines folded at 75 octets, escaped text, UTC times with Z, a UID and DTSTAMP per event | As expected |
| OEM | CCSDS 502.0-B-3, written by the app's own OEM writer, read back by its reader | Round trip within the written precision |
| AEM 2.0 | The CCSDS NDM/XML 4.0.0 schema's AEM 2.0 keywords; quaternions scalar last (O-20) | Round trip within the written precision |
| Quaternions | Basilisk's `C2EP` on the same matrices | Equal to 1e-12 (sign fixed by the scalar part) |
| Pointing predictions | Basilisk's access analysis of the same run | Within 1e-3 deg |
| Activities, command schedule | The plan's activities and the scenario's device names | As expected |

## What-if, replanning and robustness (`tests/test_operations_phase3.py`)

| Case | Reference | Result |
|---|---|---|
| A lost pass replanned from its start | Hand calculation of the data that waits for the next pass | Equal |
| What-if events | Applied to a copy; the scenario is unchanged | As expected |
| The robustness batch | The same seed twice | The same draws and outcomes; saved and read back as a Monte Carlo batch |
| Contingency rules in the simulation | Safe mode below its state of charge, back above the recovery value; low-priority acquisitions dropped above the memory fraction | As expected |

## Sensitivity to the Earth orientation data

A test run has no Earth orientation files (it uses IAU_EARTH, about 10 km
off on the ground); a user with the files installed gets ITRF93. Template
35's window over the Alps sits at the 30 deg off-nadir limit: with the
files it holds an image, without them it is too short. Its claims accept
both (17 or 18 of 23 images). The off-nadir angles of the other images
move by up to 0.9 deg. This is reported in the limitations.

## Performance (this computer)

| Case | Time |
|---|---|
| Geometry by orbit-only propagation, one spacecraft, one week at 30 s | 12 s |
| Template 35's week, scheduling without and with 20 improvement steps | 9 s and 31 s |
| Template 36, three spacecraft, two days | 15 s in all |
| Flying a two-hour plan (record every 5 s) | 7 s |
| Ten robustness draws (re-check) | 2.4 s |
