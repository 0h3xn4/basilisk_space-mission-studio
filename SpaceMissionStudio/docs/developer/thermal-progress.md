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
| 2 | Geometry: facets, contacts, shading screen; generation; conductor calculator | done |
| 3 | Environment fluxes: solar, albedo (Basilisk), planetary IR | done |
| 4 | Network and solver: MLI, conductors, heat pipes, links, dissipation, heaters, periodic start, energy balance, sizing | next |
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

- Step 2: `thermal/geometry.py` (facets from the derived model, contacts
  with exact overlap and the covered area taken off each face,
  enclosures, the shading screen by ray casting), `thermal/library.py`
  (sourced optics, specific heat, the bare-joint coefficient T-26),
  `thermal/conductors.py` (the calculator), `thermal/generate.py` (nodes
  per part, contact and mounting conductors);
  `tests/test_thermal_geometry.py`.

- Step 3: `thermal/environment.py` (solar factor with distance and
  eclipse, plate-to-sphere view factor checked against direct
  integration, OLR defaults from the NASA guideline by inclination band,
  Mars by radiative balance, period, inclination, beta; the albedo map
  found offline or the mean used with a warning), `thermal/albedo.py`
  (Basilisk's albedo module stand-alone, one instrument per distinct
  normal); `tests/thermal_fixtures.py` (a synthetic run),
  `tests/test_thermal_environment.py`.

## Next

Step 4.

## Known issues

None yet.
