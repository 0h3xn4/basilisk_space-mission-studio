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
| 4 | Network and solver: MLI, conductors, heat pipes, links, dissipation, heaters, periodic start, energy balance, sizing | done |
| 5 | Cases, presets, overrides | done |
| 6 | Checks and the shadowing warning | done |
| 7 | Results, series, events, record, CSV | done |
| 8 | `api.thermal`, CLI `thermal` | done |
| 9 | GUI: thermal editor, Run › Thermal, Timeline, Problems | done |
| 10 | V&V records (Phase 1) | done |
| 11 | Template 33 (150 kg bus), claims, golden file | done |
| 12 | Documentation (Phase 1) | done |
| 13 | Library: conductivity, honeycomb, MLI, EOL optics where sourced | done (coatings and UV-aged values; the rest logged unsourced, T-38) |
| 14 | Temperature-dependent properties | done |
| 15 | Sweeps and sensitivity | done |
| 16 | Thermal Monte Carlo | done |
| 17 | Temperature colouring of the 3D model | done |
| 18 | Solar-array panels as nodes | done |
| 19 | Phase 2 template, V&V, docs, final checks | done (final checks: see below) |

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

- Step 4: `thermal/network.py` (facet ownership and optics resolution,
  MLI scaling, capacitances with their sources, conductors, heat pipes,
  links, dissipations from the power budget, heaters),
  `thermal/solver.py` (BDF2 + Newton, steady state, orbit-periodic start
  carrying the step history, energy balance, step check, heater sizing);
  `tests/test_thermal_solver.py` (plate, faceted sphere, conductor, heat
  pipe, MLI, energy balance, periodic start against a cold transient,
  sizing against E T^4, step check).

- Step 5: `thermal/cases.py` (presets from the NASA guideline by band
  with the beta correction, T-27, T-28; overrides by path on a copy with
  type checks; the section's environment over the preset);
  `tests/test_thermal_cases.py`.

- Steps 6-8: `thermal/checks.py` (rules `thermal.*` in
  `engine/findings.py`; in the Problems panel through
  `plausibility_warnings`; the shading screen cached on the model),
  `thermal/results.py` (heat flows by kind and item, orbit averages,
  summary and margins, heaters with sized power, radiators, limit events
  of kind `thermal limit`, series), `thermal/analysis.py` (prepare once,
  solve per case), `thermal/records.py` (JSON record, CSV tables and
  series with provenance), `api.thermal`, `api.thermal_model`, CLI
  `thermal` (`--generate`, `--case`, `--no-sizing`, `--out`, `--tables`);
  the solver steps on the eclipse transitions (step check 1.7 K -> 0.19 K
  on template 32) and sizes heaters by warm-started regula falsi (9.2 s ->
  2.7 s); type hints of the thermal records resolved in their own module
  when a scenario file loads. Tests: `test_thermal_checks.py`,
  `test_thermal_analysis.py` (a real run).

- Step 9: `gui/thermal_editor.py` (the 3D model tab's Thermal model group,
  a table per kind of record, Generate, Conductance; T-32),
  `gui/thermal_widget.py` (Run › Thermal: Solve on a thread, summary,
  SVG plots shown and saved as SVG and PNG, flows, heaters, radiators,
  findings, Save with provenance; T-31), `thermal/plots.py`, Timeline
  events added after the run (Thermal limits box), Run menu entry,
  Reports › Exports row, `--tables` writes the plots. Tests:
  `tests/gui/test_thermal_pages.py`; GUI suite 1847 passed.

- Step 10: `compliance/validation/thermal-vv.md`; `tests/test_thermal_vv.py`
  (Basilisk's sensorThermal regression, 0.072 K at 1 s falling to 0.018 K
  at 0.25 s; thin panel; faceted cylinder; step convergence 3.9-4.1-fold
  per halving). Found: sensorThermal's radiation constant is 1.6 % high
  (T-33, draft upstream issue).

- Step 11: template 33 (`33_microsat_thermal.json`, generator
  `build_33_microsat_thermal`), description, wizard page, README row,
  scenario hash, golden file (now with a `thermal` section:
  `tests/golden_capture.py`), claims (`test_33_...`). The periodic start
  learned slow modes and thermostats (T-34).

- Step 12 (Phase 1 docs): `docs/models/thermal.md`,
  `docs/user-manual/thermal.md`, the 3D model guide, capabilities,
  limitations, glossary, USER_MANUAL, SRS-F-29 rows and the regenerated
  ICD, SDD and SUITP.

- Phase 2, steps 13-19:
  - specific-heat tables solved on the enthalpy, conductivity tables
    (T-35; `tests/test_thermal_tables.py`);
  - sweeps, one-at-a-time sensitivity and the seeded thermal Monte Carlo
    in the Monte Carlo view, in the API, the CLI and the Thermal page
    (T-36; `thermal/sweeps.py`, `tests/test_thermal_studies.py`);
  - the 3D model coloured by temperature (`gui/model_view_widget.py`,
    the Thermal page);
  - flexible solar arrays as nodes whose faces turn with the recorded
    hinge angle (T-37; `tests/test_thermal_arrays.py`);
  - 26 coatings from NASA RP-1121, three of them UV-aged; conductivity,
    honeycomb and mission end-of-life optics logged as unsourced (T-38;
    `tests/test_thermal_library.py`);
  - template 34 with its claims, golden output, hashes and wizard page
    (T-39);
  - the Phase 2 verification records in
    `compliance/validation/thermal-vv.md`;
  - documentation: the model, the user guide, capabilities,
    limitations, USER_MANUAL, CHANGELOG.

- 2.12.0, results presentation (the windows-and-views design, section 1
  and 4; thermal gap analysis phase 1, items 1, 2 and 5):
  - the screen plot at the view's size and in the theme, made in a
    worker, never stretched; the files unchanged (T-40;
    `gui/svg_plot.py`, `tests/test_thermal_plot_style.py`);
  - Run › Thermal as tabs, the findings in the Problems panel (T-41);
  - temperatures on Results › 3D View that follow the playback and the
    time cursor, with a colour bar (T-42;
    `tests/gui/test_thermal_views.py`).

## Next

Final checks: the full suite with coverage, lint, the document and
traceability checks, the Basilisk boundary check, and the final report.

## Known issues

- NIST's property site is not reachable from the build environment, so
  the library has no conductivity or specific-heat tables (T-38).
- The albedo on a flexible array is taken at its initial angle (T-37).
