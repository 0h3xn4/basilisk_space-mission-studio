# Spacecraft thermal analysis: progress

Branch `feature/thermal-analysis`, from `develop` at `8838a23bd` (after
2.8.0's publication record), with `develop` merged in as it moves.
**Re-read this file first after an interruption.** Design:
[thermal-design.md](thermal-design.md); decisions:
[thermal-decisions.md](thermal-decisions.md).

Worktree used during development:
`/tmp/claude-0/-home-user-basilisk-SpaceMissionStudio/34bf9a8e-f238-57ef-a551-1da2bf43af3d/scratchpad/wtth`
(git needs `HOME=/root`). Tests:
`env HOME=$SP/fh4 QT_QPA_PLATFORM=offscreen PYTHONPATH=$PWD $SP/venv314/bin/python -m pytest ...`
from `SpaceMissionStudio/`, with `SP` the scratchpad.

Basilisk check before every commit:
`git diff --name-only develop...HEAD | grep -v '^SpaceMissionStudio/'`
must print nothing (or only `README.md`, SpaceMissionStudio section).

## Plan (mirrors the design, section 5)

| # | Step | State |
|---|---|---|
| 0 | Investigation, design, decision log, progress file | done |
| 1 | Schema `thermal` section, validation, references, recording | done |
| 2 | Geometry: facets, contacts, shading screen; generation; conductor calculator | next |
| 3 | Environment fluxes: solar, albedo (Basilisk), planetary IR | |
| 4 | Network and solver: MLI, conductors, heat pipes, links, dissipation, heaters, periodic start, energy balance, sizing | |
| 5 | Cases, presets, overrides | |
| 6 | Checks and the shadowing warning | |
| 7 | Results, series, events, record, CSV | |
| 8 | `api.thermal`, CLI `thermal` | |
| 9 | GUI: thermal editor, Run › Thermal, Timeline, Problems | |
| 10 | V&V records (Phase 1) | |
| 11 | Template 33 (150 kg bus), claims, golden file | |
| 12 | Documentation (Phase 1) | |
| 13 | Library: conductivity, honeycomb, MLI, EOL optics where sourced | |
| 14 | Temperature-dependent properties | |
| 15 | Sweeps and sensitivity | |
| 16 | Thermal Monte Carlo | |
| 17 | Temperature colouring of the 3D model | |
| 18 | Solar-array panels as nodes | |
| 19 | Phase 2 template, V&V, docs, final checks | |

## Done

- Step 0 (2026-11-16): codebase investigation (design section 1); the
  NASA guideline NASA/TM-2001-211221 obtained from NTRS for the hot and
  cold values; SATMO unreachable (T-18); the TU Delft tool unlicensed
  (T-19); Basilisk's albedo module probed stand-alone (60 instruments,
  1.4 ms per step).

- Step 1: `schema/thermal.py` (the section, its own version, validation
  against the model, the materials and the power loads; `compact` for
  saving), `SpacecraftConfig.thermal`, central body and Sun checks,
  part renames into nodes and faces, field help and JSON editor tables;
  the run records the central body's and the Sun's positions and the
  central body's orientation (`ephemeris.<body>.dcm_PN`) for a thermal
  spacecraft; `tests/test_thermal_schema.py`.

## Next

Step 2.

## Known issues

None yet.
