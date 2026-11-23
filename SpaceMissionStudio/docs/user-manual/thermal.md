# Thermal analysis

How to give a spacecraft a thermal model built on its 3D model, solve it
on a run, study it, and read and export its temperatures. Template 33
shows the basics on a 150 kg microsatellite; template 34 adds flexible
solar arrays and a thermal Monte Carlo. The method and its sources are in
[docs/models/thermal.md](../models/thermal.md).

The analysis is for spacecraft of about 100 kg and more around the Earth
or Mars. It runs after a run, on what the run recorded: the orbit, the
attitude and the eclipses. It does not change the run.

## Build a thermal model from your 3D model

You need a 3D model of the spacecraft ([3D model](3d-model.md)), with a
mass on each part and, where you can, each part's material.

1. **Spacecraft › Edit › 3D model**, then tick **Thermal model**.
2. Press **Generate from the 3D model**. You get:
   - a node per part, with the part's mass and its material's specific
     heat (aluminium 6061-T6's if it names none);
   - a face entry per part, with its material's optics where the library
     has them;
   - a contact conductor wherever two parts touch, over their exact
     touching area, at the coefficient of a bare bolted joint
     (136 W/(m^2 K)); a part inside another one (out of the surface
     model) is mounted over its largest face;
   - a node for each flexible solar array (**Spacecraft › Solar arrays**),
     named `solar array <name>`, with solar cells on its `cells` face
     and black paint on its `back`. Join it to the bus yourself: add a
     conductor of kind `value` with the hinge's conductance. A model part
     drawn for an array, with **Counts toward mass** off, is left out, so
     the array is not counted twice.
3. Give the faces their optics on the **Faces** tab. A row with a part
   and no face covers all the part's faces; a row with a face (`+z`,
   `side 1`) overrides it for that face. Pick a **Coating** from the
   library (white paint, black paint, silvered Teflon, solar cells, MLI
   outer layers...) or type an absorptance and an emissivity. For a
   blanket, give **MLI e\*** (0.01 to 0.05 is usual) with the outer
   layer's coating. Mark radiator faces **Radiator**. A thin panel has a
   face per side, each with its own optics.
4. Where a property changes with temperature, give a table instead of
   one value: a node's **specific_heat_table** (`[[degC, J/(kg K)], ...]`)
   or a `material` conductor's **conductivity_table**
   (`[[degC, W/(m K)], ...]`), on the JSON page. Linear between rows,
   held beyond the ends.
5. Replace contacts that are not bolted joints. On the **Couplings**
   tab, under **Conductors**, a
   conductor of kind `value` takes a conductance in W/K (standoffs,
   isolating washers); kind `material` computes `k A / L` from a length
   and a section; kind `contact` takes an area and a coefficient. Select a
   row and press **Conductance** to see the value and how it was computed.
6. Add what the model cannot know (the **Heat loads** tab holds
   Dissipation and Heaters; the **Couplings** tab Heat pipes and
   Radiative links):
   - **Dissipation**: the heat each unit gives off, a power in W, or the
     name of a power-budget load (`bus`, `comms`, `transmitter`,
     `instrument:<name>`) to follow it;
   - **Heat pipes**: the two nodes, the conductance in W/K and the
     operating range;
   - **Heaters**: the node, the power, and the thermostat's on and off
     temperatures;
   - **Radiative links**: an effective area between two nodes, if two
     inner surfaces see each other;
   - each node's **Operating** and **Survival** ranges (`lowest, highest`
     in degC).
7. Look at the **Problems** panel. It lists faces in no node or without
   optics, nodes without capacity or without a path to space, and the
   faces another part can shade (see "Shading" below).

The same section is in the scenario file as the spacecraft's `thermal`,
and the JSON page edits it with completion and help. From the command
line, `spacemissionstudio thermal scenario.json --generate out.json`
writes the scenario with a generated model.

## Choose the cases

With no cases you get three: **nominal**, **hot** and **cold**. They take
the solar constant (1367, 1414, 1322 W/m^2) and the albedo and planetary
infrared of NASA's guideline (NASA/TM-2001-211221) for the orbit's
inclination band; hot and cold use its combined pairs at 90-minute
averaging, corrected for the run's beta angle.

On the **Cases** tab, a case has a name, a preset and overrides: any
value of the thermal model by its path, as JSON. Template 33's
safe-mode case is:

```json
{"name": "cold safe mode", "preset": "cold",
 "overrides": {"dissipations[avionics].source": "", "dissipations[avionics].power_w": 15.0}}
```

Paths name records by their name: `faces[bus:+x].absorptance`,
`nodes[battery].capacitance_j_k`, `heaters[battery heater A].on_c`,
`environment.albedo`.

**Choose the worst-case beta angle with the run.** The run's orbit and
epoch fix the Sun's angle to the orbit plane. For the hot case, run at
the epoch of the mission's highest beta (longest sunlight); for the cold
case, at its lowest (longest eclipse). The Thermal page shows the run's
beta range.

## Solve and read the results

1. Run the scenario. A spacecraft with a thermal model records what the
   analysis needs.
2. **Run › Thermal**, pick the spacecraft, press **Solve**. Each case
   takes seconds; sizing the heaters takes longer (untick **Size the
   heaters** to skip it).
3. The status line says how many cases were solved. The findings (limit
   violations, the shading warning, a start that did not converge, a
   step that is too long) are in the **Problems** panel. The chip beside
   the status line counts them (a warning triangle and "2 findings"), and
   the **Show in Problems** button opens the panel (`Ctrl+J`).
4. Pick the **Case** and the **Node** above the tabs; every tab shows
   them. The tabs:
   - **Temperatures**: every node, or the node picked with its operating
     band (green) and survival band (amber), each named in the legend.
     The plot fills the tab at any window size and follows the light or
     dark theme;
   - **Heat flows**: the node's heat flows by kind (pick a node first),
     over the **Orbit-average heat flows** of every node (positive into
     the node). The table is as tall as its rows; the plot takes the rest
     of the tab. A kind of heat flow that is zero for every node of the
     case is hidden; the table header's context menu shows it again;
   - **Summary**: each node's minimum, maximum and mean in each case, its
     operating range, its margins to that range, and its **Status**: an
     icon and words (**Within limits**, **Below operating**, **Above
     operating**, **Below survival**, **Above survival** or **No
     limits**). The pointer over a status gives the operating and
     survival ranges;
   - **Heaters and radiators**: the heaters' duty, energy, orbit-average
     and sized power, and the heat the radiators reject;
   - **3D model** and **Studies**: see below;
   - **Notes**: the **Solution per case** table (how each case started,
     the orbits it needed to repeat itself, the energy balance's residual
     and throughput, and how much half the time step changes the
     temperatures), the beta angle over the run, and the notes: where
     each case's environment comes from and the values a case overrides.
     A note that several cases share is listed once, with their names.
5. A node outside its range appears on the **Timeline** as a `thermal
   limit` event (the **Thermal limits** box).
6. **Open in Own Window** (the last button of the top row, or
   `Ctrl+Shift+D`) puts the whole Thermal page in a window of its own,
   for a second screen, with everything it holds; `Ctrl+Shift+D` there,
   **Bring Back** or closing the window puts it back
   ([Open a view in its own window](../../USER_MANUAL.md#open-a-view-in-its-own-window)).

**Sized power** is the least constant heater power that holds the node at
its "on" temperature over the orbit. Carry it into the power budget.

### When the checks complain

- **Halving the time step changes temperatures by more than 0.5 K**: set
  a shorter **Time step** on the **Solver** tab (template 33 uses
  10 s; a light panel at eclipse exit needs it).
- **The orbit-periodic start did not converge**: raise **Max orbits**.
  If a heater cycles over many orbits on a large structure, the
  spacecraft has no orbit-periodic state; put the unit on isolators, as
  template 33's battery is, or solve from fixed temperatures (**Start**
  `fixed`).

### Shading

The model does not shade one part with another. A face that a deployed
array or an antenna can shade gets its full sunlight, so it is warmer
than it would be. The analysis names those faces and the parts in its
warning. For a face that matters, check its worst case by hand, or
override its absorptance in a case.

## Colour the 3D model by temperature

On the Thermal page's **3D model** tab, each part takes its node's
colour: blue is cold, red is warm. Pick **Hottest over the run**,
**Coldest over the run**, **Mean over the run**, or **At a time** and
move the slider. Parts without a node are grey. Flexible arrays are not
drawn in the 3D model, so they do not appear there.

## See the temperatures as the run plays back

**Results › 3D View** can colour the spacecraft by a case's temperatures
while it plays the run back:

1. Solve the run on **Run › Thermal**.
2. On **Results › 3D View**, open the **Colours** list (beside the
   speed) and pick **Temperature: <case>**. Or press **Show on 3D View**
   on the Thermal page's **3D model** tab: it opens the 3D View with the
   case shown there.
3. Play the run, drag the slider, or click a plot or the Timeline. Each
   part takes its node's temperature at that moment, on the same scale
   as the 3D model tab: blue is cold, red is warm, grey is a part in no
   node. The colour bar in the view's top right corner gives the case,
   the coldest and the hottest temperature in °C; the scale stays the
   same for the whole case.
4. **Model colours** puts the model's own colours back.

The list offers the cases only when the thermal result belongs to the
run the 3D View shows. A run shown while it runs has no temperatures:
the thermal analysis runs after the run.

## Study the case: sweeps, sensitivity, Monte Carlo

On the **Studies** tab, each study solves the case shown again on
the same run. Nothing runs in Basilisk again, so a study takes seconds.

- **Sweep**: choose the **Parameter** in the list. Each entry is named
  by its record and field, with its unit ("Face radiator: absorptance",
  "Heater battery heater A: power [W]"); the pointer over it gives its
  path in the thermal model (`faces[radiator].absorptance`). For a
  parameter that is not in the list (`environment.albedo`), choose
  **Other parameter, by its path** and type the path, as in a case's
  overrides. Type the **Values** (`0.1, 0.2, 0.3`), then press
  **Sweep**. The table gives every node's minimum and maximum at each
  value.
- **Sensitivity**: press **Sensitivity**. Each optic, conductance, heat
  pipe, dissipation, heater power, the sunlight and the infrared moves
  10 % up and down, one at a time. The table ranks them by the largest
  change they cause. Parameters without a number (a dissipation that
  follows the power budget) are listed as left out.
- **Monte Carlo...**: it is off while the thermal model has no Monte
  Carlo section, and its tooltip says so. First set the runs, the seed, the case and the
  dispersions under **Monte Carlo** on the thermal model's **Cases** tab (a path, a
  sigma, normal or uniform, absolute or relative to the value), and, if
  you want a bound, the **Confidence** (between 0 and 1; no default).
  Press **Monte Carlo...** and pick a folder. The batch opens in the Monte Carlo
  view by node: the hottest and coldest any run reached, each run's
  curve with the mean and its band (the mean plus and minus 3 standard
  deviations of the runs, which is not a probability bound), the
  Statistics and Sensitivity tabs (each node's lowest and highest
  temperature over the runs, and which drawn value goes with them), and
  the run table with the drawn
  values (a run whose draw the model refused is listed as "failed").
  The **Node limits** tab counts, for each node with an operating or
  survival range, the runs whose temperature leaves it at any step: the
  runs evaluated (N), the runs outside (k; a failed run counts as
  outside every range), the rate k/N and, with a confidence, the exact
  upper bound on the rate at it. The same seed gives the same runs.

Template 34's Monte Carlo varies the radiator's absorptance, the heat
pipe and the battery's isolators: in 4 of its 20 runs the battery passes
its 30 degC limit, and the Node limits tab shows them as 4 of 20 outside
the battery's operating range.

From the command line:

```
spacemissionstudio thermal scenario.json --case hot --sweep "faces[radiator].absorptance=0.1,0.2,0.3"
spacemissionstudio thermal scenario.json --sensitivity --relative 0.2
spacemissionstudio thermal scenario.json --monte-carlo mc_folder/
```

With `--monte-carlo`, the command also prints the node limits table.

From Python: `api.thermal_sweep`, `api.thermal_sensitivity` and
`api.thermal_monte_carlo` ([The Python API](../api.md)).

## Save and export

**Save...** in the top row opens a menu with every export of the page:

- **Everything to a folder...** writes `thermal.json` (the record:
  inputs, every case's results, the findings, the provenance), the
  tables and every series as CSV, and the plots as SVG and PNG, each
  with a `.provenance.json` beside it. Reports › Exports lists it.
- **Temperature plot as SVG...** and **Temperature plot as PNG...** save
  the temperature plot of the case and node shown at 900 x 420 on
  white, as before. (They were the **Save SVG...** and **Save PNG...**
  buttons.)
- From the command line:

```
spacemissionstudio thermal scenario.json --case cold --out thermal.json --tables thermal/
```

- From Python: `api.thermal(scenario, result)` returns the analysis;
  `api.thermal_model(scenario)` generates the section
  ([The Python API](../api.md)).

## Limits of the model

One node per part (no meshing), no shading between parts (flexible arrays
included), diffuse grey optics, no fluid loops, phase-change materials or
coolers, heater power not taken from the battery, no electrical power
taken out of the cells' sunlight, Earth and Mars only. The library's
optics are beginning of life, apart from three coatings measured after
ultraviolet exposure; it has no conductivities. See
[limitations](../reference/limitations.md#thermal-analysis).

---

**Next:** [3D model](3d-model.md) ·
[Analyses built on the 3D model](model-analyses.md) ·
[How-to guides](README.md)
