# Mission operations planning: progress

Branch `feature/operations-planning`, from `develop` at `86468233e`
(release 2.9.0). **Re-read this file first after an interruption.**
Design: [operations-planning-design.md](operations-planning-design.md);
decisions: [operations-planning-decisions.md](operations-planning-decisions.md).

Worktree used during development:
`/tmp/claude-0/-home-user-basilisk-SpaceMissionStudio/34bf9a8e-f238-57ef-a551-1da2bf43af3d/scratchpad/wtops`
(git needs `HOME=/root`). Tests:
`env HOME=$SP/fh4 QT_QPA_PLATFORM=offscreen PYTHONPATH=$PWD $SP/venv314/bin/python -m pytest ...`
from `SpaceMissionStudio/`, with `SP` the scratchpad.

Basilisk check before every commit:
`git fetch -q origin develop:develop; git diff --name-only develop...HEAD | grep -v '^SpaceMissionStudio/'`
must print nothing (or only `README.md`, SpaceMissionStudio section).

## Plan (mirrors the design, section 6)

| # | Step | State |
|---|---|---|
| 0 | Investigation, design, decision log, progress file | done |
| 1 | Schema `operations` section; recording for it | done |
| 2 | Time base and geometry (run, propagation, analytic) | done |
| 3 | Targets and opportunities (windows, coverage, passes, eclipses, maneuvers) | done |
| 4 | Attitude per mode, slew time | done |
| 5 | Resources: energy and memory | done |
| 6 | Plan model and file | done |
| 7 | Scheduler | done |
| 8 | Analysis entry point, API, CLI | done |
| 9 | GUI: Run › Plan, Gantt, edits, Problems, Timeline | done |
| 10 | Executor `SysModel`, device switching, maneuvers | done |
| 11 | Verification plan vs simulation | done |
| 12 | Dashboard | done |
| 13 | Exports (CSV, ICS, JSON, command schedule, pointing, AEM, OEM, report) | done |
| 14 | What-if and replanning | done |
| 15 | Contingency rules | done |
| 16 | Robustness batch and plan comparison | done |
| 17 | Templates and claims | done |
| 18 | V&V records | done |
| 19 | Documentation, final checks, report | done |

## Done

- Step 0 (2026-11-16): codebase investigation (design section 1);
  orbit-only propagation timed (22 s for three spacecraft over a week at
  30 s); AEM 2.0 structure from the CCSDS XML schema (the Blue Book site
  is refused by the network policy, O-20).
- Steps 1-8 (2026-11-16): the `operations` section (validation,
  references and renames, field help); time base; geometry from a run,
  an orbit-only propagation or the analytic model (ERFA `c2t06a`, O-04);
  targets (points, CSV, GeoJSON polygons); windows, passes with masks and
  link margins, eclipses; attitude per mode and the slew model; energy
  and memory profiles; the plan model and file; the scheduler (requests,
  locks, contention, reasons, seeded improvement); `operations.analysis`,
  the API (`plan_*`) and `spacemissionstudio plan`. Scheduling a day takes
  0.3-0.5 s.
- Steps 10-13 (2026-11-16): the plan executor (`PlanWriter`,
  `PlanArbitrator`; app-owned `SysModel`s), device switching through
  `DeviceCmdMsg`/`DeviceStatusMsg`, planned maneuvers as a generated
  Mission Sequence; verification plan vs flight; ten export products.
  On a two-hour plan the flown off-nadir angle is within 0.23 deg of the
  plan and the state of charge within 1.25 points.
- Steps 14-16 (2026-11-16): what-if events, replanning from a time
  (O-22), contingency rules in the executor, the robustness batch (a
  `MonteCarloBatch` of kind `operations`), plan comparison.
- Step 9 and the dashboard (Step 12) (2026-11-16): Run › Plan with the
  Gantt chart (drag within the window), Lock, Unlock, Delete, Lose this
  pass, Replan, Compare, Robustness, Export, Fly and verify (Stop works),
  the plan status at the time cursor; the plan's activities on the
  Timeline ("Planned activities"); unplaced requests and verification
  flags in Problems; the editor keeps the section (O-23, O-24).
- Steps 17-19 (2026-11-16): templates 35 (a week of the 150 kg imager,
  three stations, a daily contact budget) and 36 (three imagers sharing
  two stations), with claims, goldens (with the plan), hashes, wizard
  pages and README rows; flying template 35 led to O-25 (slew margin)
  and O-26 (resource times, verification span); the V&V record; SRS-F-30
  and its verification row; the User Manual, the how-tos (Plan a week of
  operations, Fly and verify a plan, Export operations products, Replan
  after a lost pass), the model page with the file formats,
  capabilities, limitations, glossary, CHANGELOG, HISTORY, the root
  README's mention.

## Deviations from the design

- Performance (design 2.7 aimed at "a week for three spacecraft, fifty
  targets and three stations in a few seconds"): a week of one
  spacecraft with twenty targets takes 9 s to schedule without the
  improvement step and 31 s with 20 steps, after a speed-up of the
  removal path; the geometry adds about 12 s per spacecraft-week.
- The flown plan is checked on the Plan page and not shown as a run in
  Results (O-24); the plan's dashboard is the status at the time cursor.
