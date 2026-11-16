# Thermal model

How SpaceMissionStudio computes a spacecraft's temperatures after a run,
and from what sources. The user's guide is
[docs/user-manual/thermal.md](../user-manual/thermal.md); the design is
[thermal-design.md](../developer/thermal-design.md) and every decision is
in [thermal-decisions.md](../developer/thermal-decisions.md) (T-nn below).
The verification record is
[compliance/validation/thermal-vv.md](../../compliance/validation/thermal-vv.md).

The analysis runs after a run, on what the run recorded (T-01). It never
changes the run, and it never changes how Basilisk computes anything:
Basilisk's `albedo` module is used through its public API, stand-alone,
and everything else is SpaceMissionStudio's own code.

## The model

A lumped-parameter network: each node is isothermal and has a heat
capacity. By default a node is one part of the 3D model (T-04); a node
may gather several parts. For node i:

```
C_i dT_i/dt = sum over its faces [ alpha_f (q_s + q_a) + eps_f q_ir ] A_f
            - sum over its faces eps_f sigma A_f T_i^4
            + sum_j G_ij (T_j - T_i)            conductors and heat pipes
            + sum_j sigma (eA)_ij (T_j^4 - T_i^4)  radiative links
            + Q_dissipated,i + Q_heater,i
```

- **Capacitance** `C_i`: given, or mass times specific heat; the mass is
  the parts' (from the 3D model) and the specific heat the node's, its
  material's (library or the model's own), or aluminium 6061-T6's from
  NASA DAS 3.0 (T-05). Each node's record says which. A node can instead
  have a **specific-heat table** of temperature (`specific_heat_table`,
  `[[degC, J/(kg K)], ...]`, linear between rows, held beyond the ends):
  the solver then integrates its enthalpy `H(T) = m * integral of cp dT`,
  so the stored heat stays exact as cp changes (T-35).
- **Faces** are the 3D model's outer faces (curved faces in their
  segments, which keep the true curved area). A face touching another
  part is not radiating over the touching area (T-25). Internal parts
  (out of the surface model) have no faces.
- **Flexible solar arrays** (the spacecraft's `solar_arrays`, Basilisk's
  hinged panels in the run) are parts of their own, `solar array <name>`:
  a flat panel of span x width with a `cells` and a `back` face and the
  array's mass. Their faces turn about the hinge by the angle the run
  recorded (T-37). A model part drawn for an array (`counts_toward_mass`
  off) is left out by the generator, so the array is not counted twice.
- **Optics** per face: a coating or material from the library
  (`config/materials.py`, Henninger, NASA RP-1121, 1984, for the
  coatings), or absorptance and emissivity given. A thin panel has a
  face per side, each with its own optics.
- **MLI** on a face: a massless outer layer of optics (alpha_o, eps_o)
  over a blanket of effective emittance e*. In balance, the face behaves
  as `k alpha_o`, `k eps_o` with `k = e* / (eps_o + e*)` (T-09).
- **Radiators**: faces marked `radiator`; their area and their emitted,
  absorbed and net rejected heat are reported, orbit-averaged.
- **Conductors**: a conductance given (`value`), `k A / L` from a
  material's conductivity, a value given or a **conductivity table** of
  temperature (`material`; the table is read at the mean of the two nodes
  at the start of each step), or a contact area times a coefficient
  (`contact`). The inputs are stored, and the
  calculator says how it computed. A contact between two parts of the
  model is found from the meshes, with its exact overlap area, and gets
  the coefficient of a bare bolted aluminium joint, 136 W/(m^2 K), from
  NASA GSFC's measurement (TFAWS 2019, NTRS 20190030287) unless given
  (T-25, T-26). An internal part sits in the part around it, mounted over
  its largest face.
- **Heat pipes**: a high conductance while the pipe's hotter end is
  within its operating range, a small one outside it (frozen or dried
  out); the state is taken at the start of each step (T-08).
- **Radiative links**: an effective area between two nodes (emittance,
  area and view factor together), given (T-10).
- **Dissipation**: a constant power, or a power-budget load by name
  (`bus`, `comms`, `transmitter`, `instrument:<name>`) (T-11).
- **Heaters**: thermostatic, on below `on_c` and off above `off_c`; their
  duty, energy and orbit-average power are reported. Sizing finds the
  least constant power that holds the node at `on_c` over the periodic
  orbit (regula falsi on periodic solves, warm-started: T-12, T-30).
- **Limits**: each node's operating and survival ranges. A span outside
  them becomes a Timeline event (`thermal limit`) and a finding.

## The environment on every face

On the run's recorded times, per face, from the run's position, attitude
and eclipse:

- **Sunlight**: `q_s = S (1 AU / r)^2 illumination max(0, n . s)`, with the
  run's Sun distance and eclipse factor. The case gives `S` at 1 AU.
- **Albedo**: Basilisk's `albedo` module, stand-alone, one instrument per
  face normal (90 degree half-angle): the CERES (Earth) or TES (Mars)
  albedo map on the planet's orientation the run recorded, or Basilisk's
  constant-albedo model when the case gives a coefficient. Basilisk's own
  solar flux (1361 W/m^2 at 1 AU) is rescaled to the case's.
- **Planetary infrared**: `q_ir = OLR F`, with `F` the view factor from
  a flat plate to a sphere (Gilmore, *Spacecraft Thermal Control
  Handbook*, vol. 1, ch. 2): with `h = r / R_ir` and `lam` the angle
  between the plate's normal and the nadir, `F = cos(lam) / h^2` while
  the whole disk is in view, 0 when the planet is behind the plate, and
  the partial closed form between. `R_ir` is the Earth's equatorial
  radius plus 30 km (the top of the atmosphere the NASA guideline's OLR
  refers to); Mars uses its radius.
- **Flexible arrays**: their sunlight and planetary infrared follow the
  turned normal at each recorded time; their albedo is taken at the
  initial normal (Basilisk's albedo module runs once per fixed normal; at
  the few degrees a flexible array deflects, the difference is second
  order). A run without the hinge record keeps the initial deflection,
  with a warning.
- Earth and Mars only; any other central body is refused (T-17).

**Shading between parts is not modelled.** A face another part can
shade gets its full sunlight. A ray-cast screen finds those faces and
the analysis warns, naming each face and the parts that can shade it,
in the Problems panel, on the Thermal page and in every record.

## Cases

A case is a preset and overrides. The presets come from B. J. Anderson,
C. G. Justus, G. W. Batts, *Guidelines for the Selection of Near-Earth
Thermal Environment Parameters for Spacecraft Design*, NASA/TM-2001-211221,
2001, for the orbit's inclination band (below 30, 30 to 60, above 60
degrees) (T-27):

| Preset | Solar constant | Albedo | OLR |
|---|---|---|---|
| nominal | 1367 W/m^2 | the albedo map | the band's mean (246, 234, 211 W/m^2) |
| hot | 1414 W/m^2 | the hot combined pair at 90-minute averaging, plus the orbit-average correction for the run's mean beta (Table 4.2.1-1) | its pair |
| cold | 1322 W/m^2 | the cold combined pair at 90-minute averaging, plus the correction | its pair |

Mars keeps its own environment: its distance's sunlight, the TES map
and an OLR from its radiative balance, stated as an estimate (T-28).
The optics are beginning of life. The library has no sourced end-of-life
values for a mission's duration; for three coatings it has the values
Henninger measured after ultraviolet exposure (`..._uv_<n>esh`, T-38). A
case can override any face's optics.

Overrides set any parameter by its path in the thermal section, for
example `faces[bus:+x].absorptance`, `nodes[battery].capacitance_j_k`,
`dissipations[avionics].power_w` or `environment.albedo` (T-13).

**The worst-case beta angle is yours to choose.** The run's orbit and
epoch fix the Sun's angle to the orbit plane, and the result reports the
run's beta range. For a hot case, run at the epoch of the highest beta of
the mission (the longest sunlight, no eclipse above about 70 degrees in
LEO, depending on altitude); for a cold case, at the lowest beta (the
longest eclipse). A second run at another epoch gives the other extreme.

## Solver

BDF2 (second-order backward differences, variable step, its first step
backward Euler) with Newton's method on the whole network: A-stable for
the stiff `T^4` and heat-pipe terms (T-07). The step (`time_step_s`,
default 30 s) does not depend on the recording interval. Loads are
linear between recorded samples, and the solver also steps on each
eclipse entry and exit, so no load jumps inside a step (T-29).

- **Step check**: the same solve with half the step; the largest change
  of any node is reported, and a finding is raised above 0.5 K.
- **Energy balance**: the heat stored, `sum C dT`, against the
  trapezoidal integral of the net heat in over the window; the residual
  is reported in J and as a fraction of the heat that came in.
- **Start** (`solver.start`):
  - `periodic` (default): from the steady state on the orbit-averaged
    loads, orbits are repeated until the run's first orbit repeats itself:
    what is left to go (the last change divided by `1 - rho`, `rho` the
    ratio by which the change shrinks per orbit) below `tolerance_k`
    (0.01 K), at most `max_orbits` (50). A slow mode is extrapolated; nodes
    a thermostat holds cycle at their own pace and are judged by their
    neighbours (T-34). The result does not depend on a start temperature.
  - `steady`: the steady state on the orbit-averaged loads.
  - `fixed`: every node from its `initial_c` (or one value).

## Studies

Three studies solve a case again with parameters changed by path, on the
same fluxes: nothing is rerun in Basilisk (T-36).

- **Sweep**: the case at each value of one parameter.
- **Sensitivity**, one at a time: each parameter up and down by a
  fraction of its value (10 % by default; optics kept within [0, 1]); the
  change of every node's minimum, maximum and mean between the two, per
  step and per unit, ranked by the largest. By default it varies every
  face entry's optics, the conductances, heat pipes, constant
  dissipations, heater powers, the sunlight and the infrared.
- **Thermal Monte Carlo**: the section's `monte_carlo` (`runs`, `seed`,
  `case`, `dispersions`: a path, a sigma, `normal` or `uniform`, absolute
  or relative). One generator seeded once draws every run in a fixed
  order, so the same seed gives the same runs. A draw outside a
  parameter's range is clipped (optics to [0, 1], the rest to 0 and up);
  a draw the model refuses is a failed run. The batch is saved in the
  Monte Carlo summary format with `kind: thermal` and opens in the Monte
  Carlo view, by node.

## Results

Per case: every node's temperature with its operating and survival
ranges; the heat flows into every node by kind (sunlight, albedo,
infrared, emitted, conduction, heat pipes, radiation, dissipation,
heater) and by item, as series and orbit averages; the summary (minimum,
maximum, mean, margins); heaters (duty, energy, orbit-average and sized
power); radiators; limit violations as Timeline events; the step check,
the energy balance and how the start converged.

Exports: a JSON record with provenance (`kind: thermal_analysis`), the
tables and every series as CSV, and the plots as SVG and PNG, each with a
provenance sidecar (T-31).

The 3D model can be coloured by temperature (Run › Thermal): each part
takes its node's hottest, coldest or mean value, or its value at a chosen
time, on a diverging scale; parts without a node are grey.

## Not modelled

Ray-traced radiation between parts and self-shadowing, specular and
spectral radiation, fluid loops, meshing (a part is one node), phase
change materials and thermoelectric coolers, heater power fed back to the
battery, the electrical power solar cells take out of the sunlight they
absorb, arrays turned by a drive (only flexible hinges turn), shading by
or of the flexible arrays, and STEP-TAS exchange: see
[limitations](../reference/limitations.md#thermal-analysis).
