# Spacecraft thermal analysis: decision log

Every non-trivial choice made while building the thermal analysis, with
the alternatives and the reason, in place of asking the owner. Design:
[thermal-design.md](thermal-design.md); progress:
[thermal-progress.md](thermal-progress.md).

## T-01 Post-processing on a finished run (2026-11-16)

**Chosen:** the thermal solve runs after the run, on its recorded states:
Run › Thermal, `spacemissionstudio thermal`, `api.thermal`, one engine.
**Alternatives:** a Basilisk module in the loop (a C++ or Python
`SysModel`). **Why:** temperatures do not feed back into orbit or
attitude, so nothing is lost; cases, sweeps and Monte Carlo then cost a
network solve, not a Basilisk run; it follows End of Life and the model
analyses. As the brief proposed.

## T-02 The thermal section references the 3D model; optics stored there, model materials as fallback (2026-11-16)

**Chosen:** a `thermal` section per spacecraft (`SpacecraftConfig.thermal`)
with its own `version` (1). Optical properties are stored in its `faces`
entries, keyed by (part, face) or by part. When an entry gives neither
values nor a coating, the face's or part's material in the model is used
(the existing `model.face_properties` and `ModelPartConfig.material`).
**Alternatives:** optics on the model's parts and faces (geometry would
carry thermal concepts, and a case override would edit the model); a
separate thermal geometry (refused by the brief). **Why:** the owner's
preference; cases override faces without touching the model; reusing the
model's materials gives a model that names them optics for free.
`CURRENT_SCHEMA_VERSION` stays 4 (the section is optional and new); the
section's own version lets it change without moving the scenario's.

## T-03 Part and face identifiers: no change needed (2026-11-16)

**Found:** parts are identified by their unique name and faces by
(part, face name), with face names fixed by the shape and its facet count
(model analyses D-02); renames go through `references.rename_part`.
Imported meshes' `plane k` faces change with the mesh. **Chosen:** keep
the identifiers; the thermal model references a mesh part as a whole
(all its planes in one node, one set of optics), as the model's face
properties already do. **Alternatives:** stable ids per face (uuids) with
a migration. **Why:** primitive face names are already stable; a uuid
per mesh plane would not survive re-importing the mesh either.

## T-04 One node per part by default; thin panels one node (2026-11-16)

**Chosen:** "Generate from model" makes one node per part with mass;
parts in the surface model are external (their faces, less
`excluded_faces`), the others internal; a panel's two sides are two
faces of one node. Parts with no mass and no outer faces are left out.
The model's equipment point masses are not made nodes: they carry no
geometry, and their mass is usually inside a part's already; the user
adds a node for one when it matters. The user merges, splits (moving
faces to another node) and renames. **Why:** the brief.

## T-05 Default specific heat (2026-11-16)

**Chosen:** a node's specific heat is its own, else its parts' material's
(the library's DAS 3.0 value), else aluminium 6061-T6's from the library,
and the default is reported in the node's description. **Why:** sourced,
and the structure of this size class is mostly aluminium.

## T-06 Fluxes per facet, incident, with a place for shading (2026-11-16)

**Chosen:** incident solar, albedo and IR flux per facet and time, before
absorption; a shading factor per facet and time multiplies the solar (and
albedo) term there. **Why:** curved parts and meshes get their true
distribution; a coating change does not recompute fluxes; self-shadowing
can be added without rework.

## T-07 BDF2 with Newton (2026-11-16)

**Chosen:** second-order backward differentiation (variable step; the
first step backward Euler, and continued across orbits of the periodic
start), Newton on the full network, dense Jacobian; step independent of
the recording; a step check comparing the step with half the step.
**Alternatives:** backward Euler (tried first: first order, 0.28 K off
on a 20 s step in the step-check test against 0.12 K now);
Crank-Nicolson (second order, but not L-stable: rings on stiff heat
pipes and heater switching); explicit RK (step limited by the smallest
capacitance); scipy's BDF (new dependency). **Why:** A-stable for any
step, second order, numpy only; the step check shows when the step is
too long. The energy balance is the heat stored against the
trapezoidal integral of the net heat in: its residual is the
integration's (2.9e-4 of the throughput on a 30 s step in the test,
smaller with a smaller step), reported with every solve.

## T-08 Heat pipes switch on the start-of-step state (2026-11-16)

**Chosen:** a heat pipe conducts `G_on` while its hotter end is within
its operating range, else `G_off`, the state set from the temperatures at
the start of each step. **Why:** keeps Newton smooth; the error is one
step at a switch, which the step check measures. Documented as an
approximation of a heat pipe's transport limit and freeze/dry-out.

## T-09 MLI as an effective emittance through a massless outer layer (2026-11-16)

**Chosen:** a face with MLI keeps its outer layer's optics (alpha_o,
eps_o) and the effective emittance e*; eliminating the massless layer
scales the face's optics by `e*/(eps_o + e*)`. **Alternatives:** an
extra node per blanket (a capacitance the user does not know); e* in
place of the emissivity alone (ignores the sunlight the blanket absorbs).
**Why:** exact for a massless blanket, no extra node, and it keeps the
sunlit blanket's heating.

## T-10 Radiative links are user-given effective areas (2026-11-16)

**Chosen:** `sigma * eA * (T_i^4 - T_j^4)` with `eA` given by the user.
**Why:** view factors between parts are out of scope (no ray tracing).

## T-11 Dissipation from the power budget names a load (2026-11-16)

**Found:** the power budget has a constant bus load, the comms load, the
transmitter's power and each instrument's power; no per-unit modes or
series. **Chosen:** a dissipation is a constant power or names one of
those loads (`bus`, `comms`, `transmitter`, `instrument:<name>`), whose
configured power is used. **Why:** that is what the power budget knows.

## T-12 Heaters on start-of-step state; sizing by bisection (2026-11-16)

**Chosen:** thermostats with hysteresis (on below `on_c`, off above
`off_c`), state from the start of the step. Sizing: the least constant
power that keeps the node at or above `on_c` over the periodic orbit of
the case, found by bisection (to 0.1 W) on periodic solves. **Why:**
direct, and it matches what a designer carries into the power budget.

## T-13 One override mechanism: paths into the thermal section (2026-11-16)

**Chosen:** overrides are `{path: value}` with paths in
`scenario.resolve_value_path`'s form, rooted at the spacecraft's thermal
section (`nodes[battery].capacitance_j_k`, `faces[bus:+x].absorptance`,
`environment.solar_flux_w_m2`). Cases, sweeps, sensitivity and Monte
Carlo all use it. **Why:** reuses the existing path syntax; one place to
validate.

## T-16 What the run records for a thermal spacecraft (2026-11-16)

**Chosen:** a spacecraft with a `thermal` section makes the run record
the central body's and the Sun's positions and the central body's
orientation (`J20002Pfix`), as the model analyses do for theirs; the
thermal solve refuses a run without attitude (`attitude_sigma_BN`) with
a message saying to set an FSW mode or full attitude. **Why:** the fluxes
need them; recording nothing more for other scenarios keeps every
existing template's output unchanged.

## T-17 Central bodies: Earth and Mars (2026-11-16)

**Chosen:** Earth (CERES albedo map, NASA guideline albedo and OLR) and
Mars (TES map; OLR from radiative balance); any other central body is
refused by validation. **Alternatives:** direct sunlight only for other
bodies. **Why:** a result without albedo and IR would look complete and
not be; refusing is clearer.

## T-18 SATMO could not be reached (2026-11-16)

arxiv.org is outside the development environment's network (the proxy
refuses it; a fetch through another path failed to resolve the host).
**Chosen:** rely on the analytical checks and on Basilisk's SensorThermal
and albedo modules as references; the record says so. **Why:** the
brief's fallback.

## T-19 The TU Delft tool has no licence (2026-11-16)

The repository (github.com/FrankMeijering/ThermalAnalysis) has no LICENSE
file and no licence in its metadata, so its code is all rights reserved.
**Chosen:** nothing read from or copied out of its code; only published
equations (Gilmore, the NASA guideline) are used. Its thesis's finding
that solar absorptivity is the most sensitive parameter is used only as
a sanity check of the sensitivity ranking. (The brief asks for ISC
compatibility; SpaceMissionStudio is EUPL-1.2 since 2.7.0. Nothing is
copied, so neither applies.)

## T-23 The bus presets have no 3D model (2026-11-16)

**Chosen:** the new template builds a 3D model of the 150 kg bus (bus
box, two deployed arrays, a radiator panel, internal battery and
avionics) in its generator; the presets are unchanged. **Why:** changing
the presets would change templates 23 and 26 and their golden files.

## T-24 Library additions only with a source (2026-11-16)

**Chosen:** new library fields (conductivity, end-of-life optics,
honeycomb) are filled only where a source is in hand; others stay empty
and the analysis says so. **Why:** the library's rule and the brief's.

## T-25 Contacts from the meshes; internal parts mounted over their largest face (2026-11-16)

**Chosen:** two parts touch where their outer triangles face each other
(normals within about 1.8 deg of opposite) within 2 mm of one plane; the
touching area is the exact overlap of those triangles (polygon clipping),
and it is taken off both faces' radiating area. A part out of the surface
model sits in the smallest surface part around its centre and is mounted
over its largest flat face. **Alternatives:** contacts from bounding
boxes (wrong for cylinders and rotated parts); asking the user for every
mounting area. **Why:** exact for the model as drawn; an internal unit is
usually bolted on its base, and the user can change the area.

## T-26 Default contact coefficient: a measured bare bolted joint (2026-11-16)

**Chosen:** 136 W/(m^2*K), from NASA GSFC's measurement of an 8 in x
8 in electronics-box baseplate bolted dry (8 #8 bolts, 40 in-lb) to a
cold plate in vacuum: 5.63 W/C (Steinfeld and Martins, "Interface
Conductance Under a Real Electronics Box", TFAWS 2019, NTRS
20190030287). The same test with 0.020 in of NuSil 2946 filler gave
108.97 W/C (about 2640 W/(m^2*K)), offered as the filled-joint value.
**Alternatives:** an unsourced handbook range. **Why:** a measured value
for the kind of joint this size class has, cited; it is deliberately the
conservative (dry) case.

## T-27 Hot and cold presets: the guideline's combined pairs at 90 minutes, orbit-averaged (2026-11-16)

**Chosen:** hot and cold take NASA/TM-2001-211221's "combined" albedo and
OLR pair (the extreme of their sum) for 90-minute averaging, by the
orbit's inclination band, with the solar constant 1414 or 1322 W/m^2;
nominal takes 1367 W/m^2, the CERES map and the band's mean OLR. The
guideline's albedo is at a solar zenith angle of 0; Table 4.2.1-1's
orbit-average correction for the run's mean |beta| is added. Albedo in
the hot and cold cases is a constant coefficient (Basilisk's average
model) at that value. **Alternatives:** the "maximum albedo" or "maximum
OLR" columns (extreme for one kind of surface, not for a whole
spacecraft); shorter averaging (the time constant of a solar cell, not of
a 100 kg spacecraft's units). **Why:** 90 minutes is the order of the
thermal time constants of this size class's units and of an orbit; the
combined pair is the guideline's choice when both albedo and OLR heat
the hardware. The user overrides any value per case.

## T-28 Mars presets keep the planet's own environment (2026-11-16)

**Chosen:** for Mars, the hot and cold presets do not change the
environment (TES map, infrared from radiative balance); their notes say
so. **Why:** no sourced engineering extremes for Mars are in hand; the
Sun distance of the run already gives Mars's large seasonal variation.

## T-29 The solver steps on eclipse transitions (2026-11-16)

**Found:** on template 32 the step check showed 1.7 K: sunlight jumps at
eclipse entry and exit between two recorded samples, inside a solver
step, and any integrator loses its order there. **Chosen:** the recorded
times on either side of a jump in the absorbed loads are added to the
solver's grid (`Loads.breaks_s`), so the loads are linear within every
step; the step check fell to 0.19 K. **Alternatives:** a smaller default
step (three times the cost everywhere for an error at two instants per
orbit).

## T-30 Heater sizing by warm-started regula falsi (2026-11-16)

**Chosen:** the coldest temperature less the setpoint grows smoothly
with the power, so the root is found by the Illinois variant of regula
falsi after bracketing, each trial's orbit-periodic start warm-started
from the previous trial's orbit; stops within 0.1 W or 1 mK above the
setpoint. **Why:** bisection with a cold start took 9.2 s per heater and
case on template 32; this takes 2.7 s with the same result (846.4 W).

## T-31 Plots as SVG written by the app (2026-11-16)

**Chosen:** `thermal/plots.py` writes the temperature and heat-flow plots
as plain SVG text. Run › Thermal shows that SVG (`QSvgWidget`), Save
SVG writes it, and Save PNG renders it with Qt's SVG renderer, so the
screen and both exports are the same picture; `spacemissionstudio thermal
--tables` writes the SVGs too. Lines keep each stride's minimum and
maximum when a series has more than 1,500 samples, so no peak is lost.
**Why:** the Results plots are Plotly in a web view; their PNG and SVG
export needs the page loaded and an asynchronous render, which a command
line run and a test cannot rely on. matplotlib is not a dependency.
**Alternatives:** Plotly figures in a web view (no export without the
page); matplotlib (a new dependency for two plots).

## T-32 The thermal editor as tables (2026-11-16)

**Chosen:** the spacecraft editor's 3D model tab gets a checkable Thermal
model group: one table per kind of record (nodes, faces, conductors,
heat pipes, radiative links, dissipation, heaters, cases) and one-row
tables for the environment and the solver, all from one `RecordTable`
that reads each column by its kind (number, optional number, names,
range, JSON). Floats are written as their shortest exact text, so an
unchanged table gives back the section exactly. Generate from the 3D
model replaces the nodes, faces and conductors and keeps the rest; the
Conductance button computes the selected conductor. Run › Thermal is a
Run tab (beside End of Life, Budget and Design Checks), solved on a
background thread on demand, as End of Life is. **Why:** the section
has eleven kinds of records with up to twelve fields; a form per record
would be large for little gain, and the JSON view edits the same
section. **Alternatives:** a form per record (more code, slower to fill
for 20 nodes); JSON only (no help for the conductor calculator and
generation).
