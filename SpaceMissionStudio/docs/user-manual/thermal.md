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
5. Replace contacts that are not bolted joints. On **Conductors**, a
   conductor of kind `value` takes a conductance in W/K (standoffs,
   isolating washers); kind `material` computes `k A / L` from a length
   and a section; kind `contact` takes an area and a coefficient. Select a
   row and press **Conductance** to see the value and how it was computed.
6. Add what the model cannot know:
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
3. Read the status line: how many orbits each case needed to repeat
   itself, and the run's beta angle. The findings (limit violations, the
   shading warning, a start that did not converge, a step that is too
   long) are in the **Problems** panel; the page says how many there are,
   and **Show in Problems** opens the panel.
4. Pick the **Case** and the **Node** above the tabs; every tab shows
   them. **Save SVG...** and **Save PNG...** beside them save the
   temperature plot at 900 x 420 on white, as before. The tabs:
   - **Temperatures**: every node, or the node picked with its operating
     band (green) and survival band (amber), each named in the legend.
     The plot fills the tab at any window size and follows the light or
     dark theme;
   - **Heat flows**: the node's heat flows by kind (pick a node first),
     over the **Orbit-average heat flows** of every node (positive into
     the node);
   - **Summary**: each node's minimum, maximum and mean in each case, and
     its margins to the operating range;
   - **Heaters and radiators**: the heaters' duty, energy, orbit-average
     and sized power, and the heat the radiators reject;
   - **3D model**, **Studies** and **Notes** (where each case's values
     come from, the energy balance and the step check): see below.
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
  a shorter **Time step** on **Environment and solver** (template 33 uses
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

Under **Studies on the case shown**, each study solves the case again on
the same run. Nothing runs in Basilisk again, so a study takes seconds.

- **Sweep**: type a **Parameter** path (`faces[radiator].absorptance`)
  and its **Values** (`0.1, 0.2, 0.3`), then press **Sweep**. The table
  gives every node's minimum, maximum and mean at each value.
- **Sensitivity**: press **Sensitivity**. Each optic, conductance, heat
  pipe, dissipation, heater power, the sunlight and the infrared moves
  10 % up and down, one at a time. The table ranks them by the largest
  change they cause. Parameters without a number (a dissipation that
  follows the power budget) are listed as left out.
- **Monte Carlo...**: first set the runs, the seed, the case and the
  dispersions on the thermal model's **Monte Carlo** tab (a path, a
  sigma, normal or uniform, absolute or relative to the value). Press
  **Monte Carlo...** and pick a folder. The batch opens in the Monte Carlo
  view by node: the hottest and coldest any run reached, each run's
  curve with the mean and its band, and the run table with the drawn
  values. The same seed gives the same runs.

Template 34's Monte Carlo varies the radiator's absorptance, the heat
pipe and the battery's isolators: in 4 of its 20 runs the battery passes
its 30 degC limit.

From the command line:

```
spacemissionstudio thermal scenario.json --case hot --sweep "faces[radiator].absorptance=0.1,0.2,0.3"
spacemissionstudio thermal scenario.json --sensitivity --relative 0.2
spacemissionstudio thermal scenario.json --monte-carlo mc_folder/
```

From Python: `api.thermal_sweep`, `api.thermal_sensitivity` and
`api.thermal_monte_carlo` ([The Python API](../api.md)).

## Save and export

- **Save...** writes `thermal.json` (the record: inputs, every case's
  results, the findings, the provenance), the tables and every series as
  CSV, and the plots as SVG and PNG, each with a `.provenance.json`
  beside it. Reports › Exports lists it.
- **Save SVG...** and **Save PNG...** save the plot shown.
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
