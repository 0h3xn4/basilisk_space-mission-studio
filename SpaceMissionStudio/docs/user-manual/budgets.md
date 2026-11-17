# Equipment list and power budget

How to give a spacecraft an equipment list and system modes, and get its
static power budget per mode: the load, the load with margins and the
power the source must deliver. The calculation is System Budget Studio's
static budget, with the same reference numbers
([design note](../developer/system-budget-phase1-design.md)).

The budget is a design check. It does not change a run: the run still
uses the spacecraft's `dry_mass_kg` and its power budget's bus load.

You edit the section in the **Budgets** area of the window (below), on
the **JSON** page of the Scenario Editor, or let the IDM-CIC import make
it. The spacecraft editor's **Power** tab shows a summary of it, and
**Run › Design Checks** shows its masses in the mass budget.

## The Budgets area

**Budgets** is the area after **Results** in the navigation rail
(`Ctrl+5`, or **Go > Go to Budgets**). It has four pages. When the
scenario has more than one spacecraft, pick one with **Spacecraft** at
the top; every page, **Propellant** too, shows that spacecraft.

**Equipment** edits the section in tables:

- **Equipment list**: one row per item, with its name, subsystem, mass
  column, bus, maturity, mass, the source of the mass and **Mass in
  model**. Double-click a cell, or select it and type, to change it;
  `Enter` keeps the change, `Esc` drops it. Clear a number to make it a
  placeholder.
- **Power modes of** the item picked: name, average power and its
  source, peak power and its source (empty: the average), duty cycle.
- **System modes**: name, duty cycle, and for each item with power modes
  the power mode it is in. "not listed" means that the mode gives the
  item no power mode: its power is unknown in that mode.
- **Power settings**: the distribution loss, the system power margin,
  each bus's converter efficiency (the bus name can be changed here) and
  the power margin of each maturity category.

A placeholder shows **TBD** behind a caution icon. A new item, power
mode or bus starts with placeholders: the window never guesses a number.
Each change goes into the scenario at once: **Undo** (`Ctrl+Z`) takes
it back and **Save** writes it. A change that makes the section invalid,
for example a name used twice, shows in the **Problems** panel. Double-
click the problem to come back to the page. A spacecraft without a
section shows **Add Budgets Section**. It adds a section with one bus,
"main", and placeholders for the efficiency, the distribution loss and
the system margin.

**Power** shows the power budget of each system mode: the load, the load
with the margins, the power at the source, and the peak. When the duty
cycles of the modes add up to 1, the last row is the duty-cycle average.
Pick a **System mode** to see its items, subsystems and buses. A badge
says **Complete** or **Unknown values**; the notes under it say which
number is missing. A cell that cannot be computed says "unknown".
**Computed with** lists the margins, losses and efficiencies the budget
used.

**Mass** shows the mass budget: the lines of the 3D model and of the
equipment list, with the AIAA S-120 growth allowances, and the totals. A
placeholder mass reads "unknown", and the badge says the totals are
incomplete. It is the same budget as **Run › Design Checks**.

**Propellant** is the delta-V and propellant budget. Until 2.10.0 it was
**Run > Budget**; it works as before
([Lifetime and propellant budget](lifetime-and-budget.md)).

Each page has **Copy as CSV**. The CSV ends with the scenario's
provenance (the versions, the scenario's SHA-256 and the time).

| Keys | Does |
|---|---|
| `Ctrl+5` | Go to the Budgets area |
| `Ctrl+Shift+N` | Add an item to the equipment list |
| `Ctrl+Del` | Remove the item picked (Budgets › Equipment only) |
| `Ctrl+Shift+C` | Copy the page shown as CSV |
| `Ctrl+C` | Copy the selected rows of a table as tab-separated text |

The commands are also in **Tools > Budgets** and in the command palette
(`Ctrl+K`, type "budget").

## The budgets section

Each spacecraft can have a `budgets` section:

```json
"budgets": {
  "version": 1,
  "buses": [
    {"name": "main", "converter_efficiency": {"value": 0.9, "source": "PCDU data sheet"}}
  ],
  "distribution_loss": {"value": 0.02, "source": "harness estimate"},
  "power_margins": [
    {"maturity": "estimated", "percent": {"value": 20, "source": "company rule 4.2"}},
    {"maturity": "existing", "percent": {"value": 5, "source": "company rule 4.2"}}
  ],
  "system_power_margin_percent": {"value": 10, "source": "company rule 4.3"},
  "equipment": [
    {
      "name": "OBC", "subsystem": "DHS", "mass_column": "electronics", "bus": "main",
      "maturity": "existing", "mass_kg": {"value": 1.2, "source": "data sheet rev B"},
      "power_modes": [
        {"name": "on", "average_w": {"value": 4.0, "source": "data sheet rev B"},
         "peak_w": {"value": 5.5, "source": "data sheet rev B"}},
        {"name": "off", "average_w": {"value": 0.0, "source": "switched off"}}
      ]
    }
  ],
  "modes": [
    {"name": "nominal", "duty_cycle": 0.8, "units": {"OBC": "on"}},
    {"name": "safe", "duty_cycle": 0.2, "units": {"OBC": "on"}}
  ]
}
```

**Every number has a source.** A number is written as `{"value": ...,
"source": "..."}`. When you do not know it yet, write `{"value": null,
"source": "TBD"}`: a placeholder. A placeholder (a null value, or the
source "TBD") is never counted as zero: every result that needs it is
**unknown**. A number without a source is refused.

The fields:

- `buses`: the power buses, each with its converter efficiency (0 to 1).
- `distribution_loss`: the share lost between the source and the loads
  (0 to below 1).
- `power_margins`: a power margin in percent for each maturity category
  of the spacecraft's mass policy (`estimated`, `layout`, `pre_release`,
  `released`, `existing`, `measured`).
- `system_power_margin_percent`: the margin on the sum of the margined
  loads.
- `equipment`: one entry per item.
  - `subsystem`: the functional subsystem (AOCS, DHS, EPS...). The
    budget groups by it.
  - `mass_column`: an AIAA S-120 column (`electronics`, `structure`,
    `wire_harness`...) for the mass growth allowance. Empty: the largest
    allowance of the row.
  - `bus`: the bus the item draws from (needed when it has power modes).
  - `maturity`: its maturity category, for the mass growth allowance and
    the power margin.
  - `mass_kg`, or `mass_in_model: true` when the 3D model already holds
    the item's mass.
  - `power_modes`: each with its `average_w` (while on), `peak_w`
    (default: the average) and `duty_cycle` (the share of the time it is
    on, default 1). An item without power modes, a structure for
    example, is in the mass budget only.
- `modes`: the system modes. `units` gives each item one of its power
  modes. An item a mode does not list has an unknown power in that mode.
  `duty_cycle` (optional) is the share of the time in the mode; when all
  modes have one and they add up to 1, the budget also gives the
  time-weighted average.

Names are unique in each list. The section has its own `version`. A
scenario file with a `budgets` section is at schema version 5, which
SpaceMissionStudio 2.10.0 and earlier cannot open.

## How the budget is computed

For each system mode:

| Step | Formula |
|---|---|
| Effective power of an item | average power × duty cycle |
| With its margin | effective power × (1 + margin / 100), the margin of its maturity |
| Bus load | the sum of the effective powers on the bus |
| With the system margin | the sum of the margined powers × (1 + system margin / 100) |
| At the source | load / (converter efficiency × (1 − distribution loss)), for the load and for the margined load |
| Peak | every item at its peak at once, with the same margins and losses |
| Spacecraft | the sum of the buses |

A missing margin still gives the load and the power at the source
without margins.

## Make it from an IDM-CIC model

`spacemissionstudio idm-import model.idm scenario.json --spacecraft sat-1
--budgets` writes the section from the model: one item per imported unit
that draws power, its power modes, and one system mode per system mode
with its duty cycle (see [Import from IDM-CIC](idm-cic.md#power-from-the-model)).
The model gives no converter efficiency, distribution loss or margin, so
they are placeholders: set them. Import the model again later and the
items you renamed, their maturity and bus, and your own items stay.

## Print the budget

```console
$ spacemissionstudio budgets scenario.json
my-sat: power budget, 2 system mode(s), 1 item(s) with power modes
  Mode     Duty [-]  Load [W]  With unit margins [W]  With system margin [W]  Source [W]  Source with margins [W]  Peak [W]  Peak source with margins [W]
  nominal       0.8         4                    4.2                    4.62     4.53515                   5.2381       5.5                       7.20238
  safe          0.2         4                    4.2                    4.62     4.53515                   5.2381       5.5                       7.20238
  nominal, bus main (efficiency 0.9): load 4 W, with margins 4.62 W, at the source with margins 5.2381 W
  safe, bus main (efficiency 0.9): load 4 W, with margins 4.62 W, at the source with margins 5.2381 W
  duty-cycle average: load 4 W, at the source with margins 5.2381 W
```

`--spacecraft NAME` picks a spacecraft (default: the first), `--csv`
prints the totals of each mode as CSV, and `--explain` each finding's
rule. From Python: `api.power_budget(scenario)` ([The Python API](../api.md)).

## What the checks say

The Problems panel lists what the section leaves unknown:

| Rule | When |
|---|---|
| `budget.placeholder` | a number the budget uses is a placeholder or is not given |
| `budget.unit_not_in_mode` | a system mode does not give an item one of its power modes |
| `budget.no_margin` | an item has no maturity, or its maturity has no power margin |
| `budget.mode_duty_sum` | every mode has a duty cycle, and they do not add up to 1 |
| `budget.mass_unknown` | an item's mass is a placeholder: the mass budget leaves it out |

---

**Next:** [Power, link and data](power-link-and-data.md) ·
[How-to guides](README.md)
