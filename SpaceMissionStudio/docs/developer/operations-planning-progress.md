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
| 1 | Schema `operations` section; recording for it | to do |
| 2 | Time base and geometry (run, propagation, analytic) | to do |
| 3 | Targets and opportunities (windows, coverage, passes, eclipses, maneuvers) | to do |
| 4 | Attitude per mode, slew time | to do |
| 5 | Resources: energy and memory | to do |
| 6 | Plan model and file | to do |
| 7 | Scheduler | to do |
| 8 | Analysis entry point, API, CLI | to do |
| 9 | GUI: Run › Plan, Gantt, edits, Problems, Timeline | to do |
| 10 | Executor `SysModel`, device switching, maneuvers | to do |
| 11 | Verification plan vs simulation | to do |
| 12 | Dashboard | to do |
| 13 | Exports (CSV, ICS, JSON, command schedule, pointing, AEM, OEM, report) | to do |
| 14 | What-if and replanning | to do |
| 15 | Contingency rules | to do |
| 16 | Robustness batch and plan comparison | to do |
| 17 | Templates and claims | to do |
| 18 | V&V records | to do |
| 19 | Documentation, final checks, report | to do |

## Done

- Step 0 (2026-11-16): codebase investigation (design section 1);
  orbit-only propagation timed (22 s for three spacecraft over a week at
  30 s); AEM 2.0 structure from the CCSDS XML schema (the Blue Book site
  is refused by the network policy, O-20).
