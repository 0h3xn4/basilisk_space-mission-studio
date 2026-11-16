# Thermal analysis

How to give a spacecraft a thermal model built on its 3D model, solve it
on a run, and read and export its temperatures. Template 33 shows it all
on a 150 kg microsatellite. The method and its sources are in
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
     model) is mounted over its largest face.
3. Give the faces their optics on the **Faces** tab. A row with a part
   and no face covers all the part's faces; a row with a face (`+z`,
   `side 1`) overrides it for that face. Pick a **Coating** from the
   library (white paint, black paint, silvered Teflon, solar cells, MLI
   outer layers...) or type an absorptance and an emissivity. For a
   blanket, give **MLI e\*** (0.01 to 0.05 is usual) with the outer
   layer's coating. Mark radiator faces **Radiator**. A thin panel has a
   face per side, each with its own optics.
4. Replace contacts that are not bolted joints. On **Conductors**, a
   conductor of kind `value` takes a conductance in W/K (standoffs,
   isolating washers); kind `material` computes `k A / L` from a length
   and a section; kind `contact` takes an area and a coefficient. Select a
   row and press **Conductance** to see the value and how it was computed.
5. Add what the model cannot know:
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
6. Look at the **Problems** panel. It lists faces in no node or without
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
3. Read:
   - the status line: how many orbits each case needed to repeat itself;
   - the findings: limit violations, the shading warning, a start that
     did not converge, a step that is too long;
   - **Summary per case**: each node's minimum, maximum and mean, and its
     margins to the operating range;
   - the plot of the temperatures: pick a **Node** to see it alone with
     its operating (green) and survival (orange) bands, and its heat flows
     by kind below;
   - **Orbit-average heat flows** (positive into the node), **Heaters**
     (duty, energy, orbit-average and sized power) and **Radiators**
     (heat rejected);
   - the notes: where each case's values come from, the energy balance
     and the step check.
4. A node outside its range appears on the **Timeline** as a `thermal
   limit` event (the **Thermal limits** box).

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

One node per part (no meshing), no shading between parts, diffuse grey
optics, no fluid loops, phase-change materials or coolers, heater power
not taken from the battery, Earth and Mars only. See
[limitations](../reference/limitations.md#thermal-analysis).

---

**Next:** [3D model](3d-model.md) ·
[Analyses built on the 3D model](model-analyses.md) ·
[How-to guides](README.md)
