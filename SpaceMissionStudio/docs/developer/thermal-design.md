# Spacecraft thermal analysis: design

A lumped-parameter (nodal) thermal model of a spacecraft, built on its 3D
model and solved after a run on the run's recorded states. The question it
answers: does each unit stay within its limits through the orbit, in the
hot and the cold case, how much heater power does it take, and how much
do the coatings matter?

Decisions are numbered T-01... in
[thermal-decisions.md](thermal-decisions.md); progress is in
[thermal-progress.md](thermal-progress.md). The target is spacecraft of
100 kg and more (the app's ESPA-class, 150, 300 and 500 kg buses), not
CubeSats.

**Absolute rule.** Nothing of upstream Basilisk changes: no file outside
`SpaceMissionStudio/` (but the SpaceMissionStudio part of the root
README), no monkeypatching, no change to the installed `bsk` 2.12.0. Every
Basilisk module below is used through its public API (section 3).

## 1. What exists (Step 0 findings)

### 1.1 The thermal sensor and the motor thermal model

The `"thermal"` sensor is Basilisk's `sensorThermal.SensorThermal`
(`engine/fsw.py`, `attach_sensors`). Basilisk's equations
(`src/simulation/thermal/sensorThermal/sensorThermal.cpp`):

- in: `illum * S * A * max(0, s_B . n_B) * alpha + P * powerStatus`, with
  S fixed at 1366 W/m^2 (no distance scaling) and `illum` from the
  optional eclipse message;
- out: `A * eps * sigma * (T + 273.15)^4`, with sigma = 5.76051e-8 (to 0 K,
  no sink);
- `T += (Q_in - Q_out) / (m c) * dt`: explicit Euler at the task rate.

It has **no albedo, no planetary infrared and no conduction**; it is one
isolated plate seen from one side. SpaceMissionStudio already corrects
Basilisk's two constants by rescaling alpha, eps, P and m with one factor
so the module integrates `m c dT/dt = alpha F A_proj + P - eps sigma A T^4`
with the flux at the spacecraft's Sun distance and CODATA's sigma
(`engine/environment_models.sensor_thermal_inputs`). Template 20 uses it.

`motorThermal.MotorThermal` (reaction-wheel motors) heats a wheel motor
from its own losses and cools it through a resistance to an ambient
temperature; explicit Euler too. It is unrelated to the spacecraft's
other parts and stays as it is.

### 1.2 Albedo

Basilisk's `albedo.Albedo` is used for coarse sun sensors only
(`engine/fsw.build_albedo`), with the CERES 2018 map for Earth
(`Earth_ALB_2018_CERES_All_5x5`) and TES for Mars, one instrument per
sensor. Its public API takes any number of instruments
(`addInstrumentConfig(fov, nHat_B, r_IB_B)`), each giving
`AfluxAtInstrument` [W/m^2]: the reflected flux on a plate of that normal,
summed over the planet's lit patches with the cosine at the plate. It also
has a constant-albedo model (`addPlanetandAlbedoAverageModel`). A probe
showed it runs **outside a simulation**: stand-alone messages for the
spacecraft, the Sun and the planet, `Reset`, then `UpdateState` per time;
60 instruments take 1.4 ms per time on the development computer. Basilisk
also has `earthRadiationModel` (albedo and OLR as one total flux, no
per-normal instruments); it is not used.

### 1.3 The 3D model, its identifiers and its faces

`SpacecraftConfig.model` (`schema/scenario.py`, `SpacecraftModelConfig`)
holds parts (box, prism, cylinder, cone, sphere, panel, mesh), each with a
unique `name`, a `mass_kg`, an optional `material`, `in_surface_model` and
`excluded_faces`. **Identifiers:** a part is its name; a face is
(part name, face name), as the model analyses decided (their D-02).
Face names come from the shape (`model3d/shapes.faces`): a box has
`+x ... -z`, a panel `+z` and `-z` (its two sides), prisms and cylinders
`+z`, `-z` and `side k`, a cone `-z` and `side k`, a sphere `face k`.
These are fixed by the shape and its facet count, so they survive edits
and saves; a renamed part is renamed everywhere by
`schema/references.rename_part`. Only an imported mesh's faces
(`plane k`, ranked by area) change when the mesh does; the model already
takes mesh properties per part, not per face, and so will the thermal
model (T-03). **No migration is needed for identifiers.**

`model3d/model.derive` places every face in the body frame
(`DerivedModel.faces`: name `"part: face"`, area, normal, centroid, with
no cap); the drag and SRP facets are the first 200 of them. A cylinder's
`side k` carries its share of the true curved area. **Neither drag nor SRP
models shadowing between parts**: `model3d/surfaces.py` says so, and faces
that touch another part are left out by hand (`excluded_faces`). The
model analyses' ray caster (`model3d/raycast.py`, `face_shading`) can tell
whether a face can be shaded by another part.

Materials: `config/materials.py` is a library of sourced values (NASA DAS
3.0 for density and specific heat of metals; Henninger, NASA RP-1121, for
solar absorptance and emissivity of coatings, films and metals; MISSE for
atomic-oxygen yields); the scenario adds its own (`model.materials`), and
parts and faces name a material (`model.face_properties`). Emissivity and
absorptance are read by no analysis yet. There is no thermal
conductivity, and no contact or view-factor function.

### 1.4 Templates, power, records

- The four bus presets (`engine/spacecraft_templates.py`: 100 kg ESPA,
  150 kg, 300 kg, 500 kg) have **no 3D model**; templates 28 and 32 build
  a 300 kg model of their own.
- Power (`PowerConfig`) is one body panel, a constant bus load, a
  battery; other loads are the comms load, the instruments' power and the
  transmitter. There are no per-unit power modes and no per-unit power
  series: a dissipation "from the power budget" can name these loads
  (T-11).
- A run records `<sc>.position_N`, `<sc>.attitude_sigma_BN` (with an FSW
  mode or full attitude), `<sc>.eclipse.illumination_factor` and, only when
  a model analysis asks, `ephemeris.<body>.position_N` for the central
  body, the Sun and the Moon. `analyses/run_geometry.RunGeometry` turns
  them into body-frame directions; the thermal model reuses it.
- Post-run analyses follow one pattern: an engine function, `api.<name>`,
  a CLI command with `--out`, a record with provenance
  (`engine/analysis_records.py`), and a page with a worker thread
  (`gui/lifetime_widget.py`, `gui/model_analyses_widget.py`).
- Monte Carlo (`engine/monte_carlo.py`) wraps Basilisk's controller and
  keeps positions only; a batch that reruns a post-processing step has no
  hook. `engine/seeds.derived_seed` gives reproducible seeds.
- Checks are `engine/findings.Finding`s with rule ids, shown in the
  Problems panel from `scenario_checks.plausibility_warnings`. Timeline
  events are `engine/events.Event` with kinds registered in
  `engine/events.py` and `gui/event_timeline_widget.py`.
- The schema is at version 4 (`schema/migrations.py`); new optional
  fields need no migration when old files load unchanged.
- `scenario.resolve_value_path` already resolves paths such as
  `spacecraft[sat-1].orbit.inclination_deg` (fields, `[name]` or index):
  the parameter-override mechanism reuses it (T-13).
- The built-in 3D View draws one colour per triangle; the model editor's
  view draws Plotly meshes with one colour per part (Plotly accepts a
  colour per face). Vizard support was removed from SpaceMissionStudio by
  the owner's decision before this work; nothing of it is left.

### 1.5 What contradicts the brief

- The brief asks for code compatible with ISC; SpaceMissionStudio is
  EUPL-1.2 since 2.7.0. Nothing is copied from other code (T-19), so the
  question does not arise.
- The SATMO paper (arXiv 2512.07896) cannot be reached from the
  development environment (arxiv.org is outside its network); the TU Delft
  repository has no licence file. Validation rests on analytical cases and
  on Basilisk itself (T-18, T-19).
- The bus presets have no 3D model, so "generate the thermal model from
  the parts" needs a model first: the new template builds one for the
  150 kg bus (T-23).
- Ephemeris and attitude are not always recorded. A spacecraft with a
  `thermal` section makes the run record what the thermal solve needs
  (T-16); a run without attitude is refused with a message.

## 2. Design

### 2.1 Module layout

All new code is in `spacemissionstudio/thermal/` (numpy only, except the
albedo evaluator, which imports Basilisk lazily):

| Module | Content |
|---|---|
| `geometry.py` | Thermal facets from the derived 3D model; contacts and contact areas between parts; the shadowing screen |
| `network.py` | The solvable network: nodes, capacities, facet-to-node map, optics per facet, conductors, heat pipes, radiative links, dissipations, heaters; built from the scenario and a case |
| `generate.py` | Default nodes from parts and suggested contact conductors |
| `conductors.py` | The conductor calculator (material, length, section; contact area and coefficient) |
| `environment.py` | Incident solar, albedo and planetary-infrared flux per facet over time; orbit period, beta angle |
| `albedo.py` | Basilisk's `albedo` module run stand-alone per facet normal |
| `solver.py` | Implicit integration, orbit-periodic start, steady state, heater sizing |
| `cases.py` | Case sets, parameter overrides, the nominal, hot and cold presets |
| `checks.py` | Model checks as findings |
| `results.py` | Temperatures, heat flows, summaries, energy balance, series, events |
| `records.py` | The record with provenance and CSV tables |
| `library.py` | Thermal views of the material library (optics, specific heat, conductivity) |
| `studies.py` | Phase 2: sweeps, one-at-a-time sensitivity, thermal Monte Carlo |
| `properties.py` | Phase 2: temperature-dependent tables |

Around it: `schema/scenario.py` (the `thermal` section, validation),
`schema/references.py` (part and face references), `engine/service.py`
(what the run records), `engine/findings.py` (rules), `engine/events.py`
(the limit event), `api.thermal`, the CLI command `thermal`, and the GUI
page Run › Thermal (`gui/thermal_widget.py`) with the thermal editor in
the spacecraft editor.

### 2.2 Scenario schema

A versioned section per spacecraft, written only when set:

```json
"thermal": {
  "version": 1,
  "nodes": [
    {"name": "bus-structure", "parts": ["bus"], "capacitance_j_k": null,
     "specific_heat_j_kg_k": null, "mass_kg": null,
     "operating_c": [-20, 50], "survival_c": [-40, 70], "initial_c": null}
  ],
  "faces": [
    {"part": "bus", "face": "+x", "node": "radiator", "coating": "silvered_teflon_5mil",
     "absorptance": null, "emissivity": null, "mli_effective_emittance": null,
     "radiator": true}
  ],
  "conductors": [
    {"name": "bus-battery", "a": "bus-structure", "b": "battery",
     "kind": "contact", "conductance_w_k": null,
     "contact_area_m2": 0.04, "contact_coefficient_w_m2_k": 500,
     "material": null, "conductivity_w_m_k": null, "length_m": null, "section_m2": null}
  ],
  "heat_pipes": [
    {"name": "hp-1", "a": "avionics", "b": "radiator", "conductance_w_k": 5.0,
     "off_conductance_w_k": 0.01, "operating_c": [-30, 60]}
  ],
  "radiative_links": [{"a": "battery", "b": "bus-structure", "effective_area_m2": 0.02}],
  "dissipations": [{"node": "avionics", "power_w": 25.0, "source": ""}],
  "heaters": [{"name": "bat-htr", "node": "battery", "power_w": 10, "on_c": 5, "off_c": 8}],
  "environment": {"solar_flux_w_m2": null, "albedo": null, "planet_ir_w_m2": null,
                  "albedo_model": "map"},
  "solver": {"time_step_s": 30, "start": "periodic", "tolerance_k": 0.01,
             "max_orbits": 50, "window": "run"},
  "cases": [{"name": "hot", "preset": "hot", "overrides": {}}]
}
```

- **Nodes.** A node owns the external faces of its `parts` and of the
  `faces` entries that name it. A `faces` entry with a `node` moves that
  face (or that panel side) to another node, so one part's faces can be
  split. A node with no faces is internal. Its capacitance is
  `capacitance_j_k`, or `mass_kg` (else the parts' mass) times
  `specific_heat_j_kg_k` (else the parts' material's, else aluminium's,
  T-05).
- **Faces.** One entry per (part, face) or per part (`face` empty: all its
  faces). Optics come from `absorptance`/`emissivity`, else `coating` (a
  library or scenario material), else the face's or the part's model
  material (`model.face_properties`, `ModelPartConfig.material`); a face
  without optics is a model check (T-02). `mli_effective_emittance` covers
  the face with MLI (2.6). `radiator` flags it for the radiator report.
- **Conductors** store the calculator's inputs (`kind` `value`,
  `material` or `contact`), so the conductance can be traced and
  recomputed (`thermal/conductors.py`).
- **Cases** are named override sets on top of the base model (2.8).
- **References** to parts and faces follow the model's rules: a part
  rename renames them (`references.rename_part`); a node, conductor,
  heater or dissipation naming something that does not exist fails
  validation with a specific message; a face missing from its part is
  reported in the Problems panel.

`CURRENT_SCHEMA_VERSION` stays 4: the section is new and optional, old
files load unchanged and files without it are written as before. The
section carries its own `version` (1); a `thermal` migration table in
`thermal/` takes later versions forward, registered beside the scenario
migrations (T-02).

### 2.3 Optical properties

Stored in the thermal section, referencing the model (the brief's
preference): the geometry stays free of thermal concepts, and a thermal
case can override a face's optics without touching the model. The
model's existing material assignments are reused as the fallback, so a
model that already names materials gets optics with no extra input. The
library and the scenario's materials keep one set of optical values that
other analyses can read later (T-02, T-24).

### 2.4 Parameter overrides

Every parameter has a path in `resolve_value_path`'s form, rooted at the
spacecraft's thermal section:

- `nodes[battery].capacitance_j_k`
- `faces[bus:+x].absorptance`
- `conductors[bus-battery].contact_coefficient_w_m2_k`
- `dissipations[avionics].power_w`
- `heaters[bat-htr].on_c`
- `environment.solar_flux_w_m2`

The one function `cases.apply(thermal, overrides)` copies the section and
sets the values; case sets, sweeps, sensitivity and Monte Carlo all use
it (T-13).

### 2.5 Environment fluxes per facet

The run's recorded times give, per facet in the body frame (attitude
interpolated as `RunGeometry` does):

- **Direct solar**: `q_s = S(r) * illum * max(0, n . s)`, with
  `S(r) = S_1AU * (1 AU / r)^2` and `illum` the run's eclipse factor. The
  case may fix `S_1AU` (1414, 1367 or 1322 W/m^2, section 4).
- **Albedo**: `q_a` from Basilisk's `albedo` module, one instrument per
  facet normal with a 90 degree half-angle, run stand-alone on the
  recorded states (`thermal/albedo.py`). The CERES/TES map needs the
  planet's orientation, which the run records for a thermal spacecraft
  (T-16); a case that fixes an albedo coefficient uses Basilisk's
  constant-albedo model with that coefficient. Basilisk scales its own
  solar flux by distance (1361 W/m^2 at 1 AU); the thermal model rescales
  `q_a` to the case's `S_1AU`.
- **Planetary infrared**: `q_ir = OLR * F(n)`, with `F` the view factor
  from a flat plate to a sphere (Gilmore, *Spacecraft Thermal Control
  Handbook*, vol. 1, ch. 2; the closed forms of Nusselt's unit-sphere
  method; the same as the catalogue form for a differential plane element
  and a sphere): with `h = r / R_ir` and `lam` the angle between the
  plate's normal and the nadir,
  - `lam <= acos(1/h)` (the whole disk in view): `F = cos(lam) / h^2`;
  - `lam >= pi/2 + asin(1/h)` (the planet behind the plate): `F = 0`;
  - otherwise (the plate's plane cuts the planet's disk):
    `F = 1/2 - 1/pi * asin(sqrt(h^2-1)/(h sin(lam)))`
    `+ 1/(pi h^2) * (cos(lam) acos(-sqrt(h^2-1) cot(lam)) - sqrt(h^2-1) sqrt(1 - h^2 cos^2(lam)))`.
  `R_ir` is the radius plus 30 km for Earth (the "top of the atmosphere"
  the NASA guideline references its OLR to). Mars uses its mean radius.
- Other central bodies are refused with a validation message (T-17).

The fluxes are incident (before optics): absorption is applied per facet
when the network is built, so a change of coating does not recompute
them. Each array is `(n_times, n_facets)`; a future self-shadowing factor
`f(t, facet)` multiplies `q_s` (and optionally `q_a`) there, before
absorption, with no other change (T-06).

### 2.6 The nodal model

For node i with capacitance `C_i`:

`C_i dT_i/dt = sum_facets [alpha_f (q_s + q_a) + eps_f q_ir] A_f`
`- sum_facets eps_f sigma A_f T_i^4`
`+ sum_conductors G_ij (T_j - T_i) + sum_links sigma eA_ij (T_j^4 - T_i^4)`
`+ Q_diss,i + Q_heater,i`

- **MLI** on a face: a massless outer layer of optics (alpha_o, eps_o)
  in radiative balance between the environment and the node through the
  effective emittance e*. Eliminating the layer gives the face the
  optics `k alpha_o` and `k eps_o`, with `k = e* / (eps_o + e*)`; exact for a
  massless layer (T-09).
- **Heat pipes**: conductance `G_on` while the hotter end is within the
  pipe's operating range, `G_off` outside; the state is taken from the
  temperatures at the start of the step (T-08).
- **Radiators**: faces flagged `radiator`; reported with their area and
  orbit-average emitted, absorbed and net rejected heat.
- **Dissipation**: a constant power, or `source` naming a power-budget
  load (`bus`, `comms`, `transmitter`, an instrument's name): its power,
  through the duty the run recorded when it has one (T-11).
- **Heaters**: thermostatic, on below `on_c` and off above `off_c`
  (hysteresis), state from the start of the step; duty cycle and energy
  reported. Sizing finds the least constant power that holds the node at
  or above `on_c` over the periodic orbit (bisection on periodic solves),
  reported as the figure to carry into the power budget (T-12).

### 2.7 Solver

Backward Euler with Newton's method on the full network (dense `n x n`
Jacobian, tens of nodes): unconditionally stable for the stiff `T^4` and
heat-pipe terms. The step `time_step_s` is independent of the recording
interval; fluxes are interpolated linearly between recorded samples. The
solver runs the step and half the step and reports the largest
temperature difference as the step check (T-07).

Initial conditions (`solver.start`):

- `periodic` (default): from the steady state on orbit-averaged loads,
  repeat the first full orbit of the run until the largest change of any
  node over one orbit is below `tolerance_k` (default 0.01 K, at most
  `max_orbits`); the number of orbits and the residual are reported. Then
  the whole run window is solved from that state.
- `steady`: the steady state on orbit-averaged loads.
- `fixed`: every node from its `initial_c` (or one value).

The result does not depend on a starting temperature unless the user
asks for `fixed`. An energy balance closes every solve:
`sum(C dT) - integral(sum Q) dt` over the window, reported in J and as a
fraction of the throughput.

### 2.8 Case sets

A case is `{name, preset, overrides}`. Presets (section 4):

- `nominal`: S = 1367 W/m^2, the albedo map, the mean OLR of the orbit's
  inclination band;
- `hot`: S = 1414 W/m^2, the guideline's hot "combined" albedo and OLR
  pair for 90-minute averaging;
- `cold`: S = 1322 W/m^2, the cold "combined" pair.

Beginning- and end-of-life optics: a case can override any face's
absorptance and emissivity. The library carries end-of-life values only
where a source gives them (T-24); the hot preset applies them, and
reports each face it could not.

The worst-case beta angle is the user's choice of orbit and epoch; the
documentation says so and the result reports the run's beta range.

### 2.9 Checks

Rules `thermal.*` in `engine/findings.py`, shown in the Problems panel:
a node with zero or no capacitance; a node with no conductive or
radiative path to space; optics outside [0, 1]; external faces with no
node or no optics; a reference to a missing part, face, node or power
load; a heat pipe range that is empty; a central body other than Earth
and Mars; and the **shadowing warning** when another part can shade a
face (ray-cast screen, `geometry.shading_candidates`). The same warning
is at the top of the Thermal page and in every result.

### 2.10 Results

- temperatures per node on the run's time axis, with operating and
  survival bands;
- heat flows per node, as series and orbit averages: solar, albedo,
  planetary infrared, emitted, each conductor, each heat pipe, each
  radiative link, dissipation, heater;
- limit violations as Timeline events (kind `thermal limit`);
- a summary per case: min and max per node, margin to the limits,
  radiator heat, heater duty, energy and sized power;
- exports: CSV of every series and table, PNG and SVG of the plots, and a
  JSON record with provenance, as the other analyses.

### 2.11 Phase 2 without rework

- Sweeps and sensitivity call the same `solve(thermal_with_overrides)` on
  the cached fluxes, so only the network changes.
- Thermal Monte Carlo draws overrides with `seeds.derived_seed`, the same
  call again.
- Temperature-dependent properties enter the Newton iteration as
  `C(T)` and `G(T)` evaluated at the iterate; constant tables reduce to
  Phase 1.
- The material library gains fields, nothing else changes.
- Coloring the 3D model reads the node temperature of each face's node.
- Flexible solar-array panels become nodes through their recorded
  attitude: their facet normals rotate with the array angle series.

## 3. Basilisk modules used

- `albedo.Albedo` with `addPlanetandAlbedoDataModel`,
  `addPlanetandAlbedoAverageModel`, `addInstrumentConfig`, `Reset`,
  `UpdateState`, and stand-alone `messaging.SCStatesMsg`,
  `messaging.SpicePlanetStateMsg` (writing payloads), reading `albOutMsgs`.
- The run's existing modules and recorders: `spiceInterface` planet state
  messages (recording the planet's position and `J20002Pfix` for a
  thermal spacecraft), the spacecraft's state and eclipse messages.
- `sensorThermal.SensorThermal` in a test, as the regression reference.

Nothing in this design changes Basilisk or its behaviour. Missing
functions are written in SpaceMissionStudio's own code.

## 4. Sources

- Solar constant, hot, median and cold: 1414, 1367 and 1322 W/m^2;
  albedo and OLR engineering-extreme pairs by inclination band and
  averaging time; orbit-average albedo correction by beta angle:
  B. J. Anderson, C. G. Justus, G. W. Batts, *Guidelines for the Selection
  of Near-Earth Thermal Environment Parameters for Spacecraft Design*,
  NASA/TM-2001-211221, October 2001 (section 4.1, Tables 4.2.1-1 and
  4.2.3-1 to -3). The presets use the "combined" columns at 90-minute
  averaging, the time constant typical of the 100 kg class's units.
- Plate-to-sphere view factor: D. G. Gilmore (ed.), *Spacecraft Thermal
  Control Handbook*, vol. 1, 2nd ed., The Aerospace Corporation, 2002,
  ch. 2 and appendix; the same closed forms are in ECSS-E-HB-31-01.
- Mars: albedo from Basilisk's TES map and its average (0.16, `albedo`
  module); OLR from radiative balance `(1 - a) S / 4`, stated as an
  estimate.
- Optics and specific heats: the existing library (Henninger, NASA
  RP-1121; NASA DAS 3.0). New values are added only with a source.
- Stefan-Boltzmann constant: CODATA 2018 (`spacemissionstudio.constants`).

## 5. Implementation plan

Mirrored in [thermal-progress.md](thermal-progress.md).

Phase 1:

1. Schema: the `thermal` section, validation, references and renames,
   the section's own version; recording what a thermal spacecraft needs.
2. Geometry: thermal facets, contact areas, the shadowing screen;
   default nodes and suggested conductors; the conductor calculator.
3. Environment: solar, albedo (Basilisk stand-alone), planetary IR; orbit
   period and beta.
4. Network and solver: optics, MLI, conductors, heat pipes, radiative
   links, dissipation, heaters, backward Euler, periodic start, steady
   state, energy balance, step check, heater sizing.
5. Cases and presets; overrides.
6. Checks (findings) and the shadowing warning.
7. Results, series, events, record, CSV.
8. API `api.thermal`, CLI `thermal`.
9. GUI: the thermal editor in the spacecraft editor (generate from the
   model, nodes, faces, conductors with the calculator, heat pipes,
   links, dissipations, heaters, cases), Run › Thermal (cases, plots,
   heat flows, summary, exports), the Timeline events, the Problems.
10. Verification records: SensorThermal regression, analytical cases,
    geometry convergence, the bus template's nodes and conductances.
11. Template 33 on the 150 kg bus, its claims and golden file.
12. Documentation.

Phase 2:

13. Material library: conductivity, honeycomb, MLI, end-of-life optics
    where sourced; selection in the forms; user entries.
14. Temperature-dependent capacity and conductivity tables.
15. Sweeps and one-at-a-time sensitivity.
16. Thermal Monte Carlo and its view.
17. Temperature colouring of the 3D model.
18. Articulating solar-array panels as nodes.
19. Template 34 (or template 33 extended), V&V of Phase 2, docs, final
    checks.
