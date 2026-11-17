# System Budget Studio merge, phase 1: equipment list and static budgets

Status: design accepted under the owner's standing instruction (2026-11-17).
Plan: [system-budget-merge-design.md](system-budget-merge-design.md), phase 1.
Decisions: [system-budget-decisions.md](system-budget-decisions.md) (B-01 to
B-14). The System Budget Studio (SBS) code, tests and reference cases are
the specification. SpaceMissionStudio (SMS) wins every overlap.

## 1. Scope

Phase 1 adds these things:

1. A `budgets` section per spacecraft, with its own `version`, in scenario
   schema version 5. A migration from 4 to 5 changes nothing else.
2. An equipment list. Each item has a sourced mass and a sourced power per
   power mode. A sourced value can be a placeholder ("TBD").
3. System modes. Each system mode gives each item one of its power modes.
4. A power margin per maturity category, a system power margin, the
   converter efficiency per bus and the distribution loss. All are sourced.
5. The static power budget per system mode, per subsystem and per bus. It
   is the SBS calculation (D-040), with the same reference numbers.
6. The equipment list feeds the existing mass budget (S-120 policy).
7. The IDM-CIC import can fill the equipment list and the system modes.
8. A **Budgets** area in the navigation rail: Equipment, Power, Mass and
   Propellant. Propellant is the Run › Budget tab, moved.
9. The CLI command `spacemissionstudio budgets` prints the power budget.

Phase 1 does not change a run. The power modes become a Basilisk power
sink in phase 2.

## 2. What the investigation found

The two reports are in the session scratchpad. The facts that decide the
design are these:

- `MountedEquipmentConfig` needs a 3D model, a mount position and a
  boresight. Its mass changes `dry_mass_kg` and the inertia of the run. It
  has no power field. So it cannot be the equipment list (B-03).
- The IDM-CIC import computes system modes and per-unit powers
  (`idm/power.py`), but it keeps only one number in the scenario:
  `bus_idle_power_w`. The modes live only in memory (B-08).
- Power, the 3D model, the mass budget and thermal are per spacecraft.
  Templates have up to 6 spacecraft. The plan's sketch had no spacecraft
  key (B-02).
- The SMS maturity codes are the S-120 policy's: `estimated`, `layout`,
  `pre_release`, `released`, `existing`, `measured`. The plan's sketch
  used `off_the_shelf`, which does not exist (B-05).
- SMS `subsystem` is also the S-120 mass column (electronics, structure).
  IDM-CIC and SBS use functional subsystems (AOCS, DHS) (B-06).
- `ValueMark` needs a finite number, so it cannot hold a "TBD" (B-04).
- Optional sections were added before without a schema step (thermal,
  operations). The owner's plan and the 2026-11-17 hard rule ask for
  version 5 (B-01).
- No editable table exists in the window. `DataTable` is read-only (B-12).

## 3. The file format

The section is `SpacecraftConfig.budgets`. It is absent when the
spacecraft has no budget. An absent section writes nothing, so a scenario
without it hashes as before, apart from the schema version.

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
      "name": "OBC",
      "subsystem": "DHS",
      "mass_column": "electronics",
      "bus": "main",
      "maturity": "existing",
      "mass_kg": {"value": 1.2, "source": "data sheet rev B"},
      "mass_in_model": false,
      "power_modes": [
        {"name": "on", "average_w": {"value": 4.0, "source": "data sheet rev B"},
         "peak_w": {"value": 5.5, "source": "data sheet rev B"}, "duty_cycle": 1.0},
        {"name": "off", "average_w": {"value": 0.0, "source": "switched off"}}
      ],
      "source_id": ""
    }
  ],
  "modes": [
    {"name": "nominal", "duty_cycle": 0.8, "units": {"OBC": "on"}},
    {"name": "safe", "duty_cycle": 0.2, "units": {"OBC": "on"}}
  ]
}
```

**Sourced value.** An object `{"value": number or null, "source": text}`.
It is a **placeholder** when `value` is null or `source` is "TBD" (as in
SBS `model/base.py`). A placeholder gives "unknown" up the chain, never
zero. A number without a source is refused at validation.

**Rules.**

- `name` is unique in `equipment`, `buses` and `modes`.
- `bus` names an entry of `buses`.
- `maturity` is "" or a category of the mass policy of the spacecraft
  (the 3D model's mass budget policy, else the default policy).
- `mass_column` is "" or an S-120 column. "" uses the existing rule: the
  largest allowance of the row.
- A power mode's `peak_w` defaults to `average_w`. When both are numbers,
  peak is at least average. `duty_cycle` is 0 to 1, default 1.
- `modes[].units` maps an item name to one of its power-mode names. An
  item a mode does not list has an **unknown** power in that mode, and a
  finding says so. (SBS refuses the file. SMS keeps it, because the
  IDM-CIC import has unstated units.)
- `modes[].duty_cycle` is optional. When every mode has one and they sum
  to 1 ± 1e-6, the Power page also shows the duty-cycle average, as
  `idm/power.py` does.
- `mass_in_model` true says that the 3D model already holds this item's
  mass. Then the mass budget adds no line for it, and `mass_kg` may be
  absent.
- `source_id` is the IDM-CIC unit `fullId` when the import made the item.
- Ratios (`converter_efficiency`, `distribution_loss`, `duty_cycle`) are
  0 to 1. Margins are in percent, as in the SMS mass budget.

## 4. The calculation

`spacemissionstudio/analyses/power_budget.py` is a pure function of one
spacecraft: `power_budget(sc) -> PowerBudget`. It ports
`budget_core/power/static_budget.py` without change to the arithmetic:

| Step | Formula |
| --- | --- |
| Effective power | `average_w × duty_cycle` |
| Unit margin | `effective × (1 + percent / 100)` of the item's maturity |
| Subsystem | sum of effective, margined and peak per functional subsystem |
| Bus load | sum per bus, with the system margin on the margined sum |
| Source power | `load / (η_bus × (1 − distribution_loss))`, nominal and margined |
| Peak | sum of the peaks, the same chain |
| Spacecraft | sum of the buses |

Any placeholder in a step makes that step and every step after it
`None`. The nominal chain does not need the margins, so a missing margin
still gives the load and the nominal source power (SBS case 11).

The order of modes and rows is the file's order, not alphabetical (SBS
sorts by id; SMS keeps the user's order, as everywhere else). The
reference tests compare by name, so the numbers are the same.

The SBS reference cases 01 to 17 move to
`tests/test_power_budget_reference.py` with the same inputs, the same
expected numbers and the same relative tolerance, 1e-12. The SBS
`eps/clean` example becomes a test fixture. Its five mode totals (load,
system-margined, source-margined) are pinned (section 9 of the SBS
findings).

## 5. The mass budget

`analyses/mass_budget.mass_budget(sc)` gets one more source of lines:
each equipment item with `mass_in_model` false. The line kind is
"equipment list". Its subsystem for the S-120 column is `mass_column`.

- A placeholder mass gives a line with no mass, the note "unknown", and
  the totals are marked incomplete (`MassBudget.unknown`). A finding says
  which items.
- Without a 3D model, the budget is today one line, `dry_mass_kg`. With a
  `budgets` equipment list and no 3D model, the lines are the equipment
  items. The dry mass of the run is not changed. A note compares the
  budget's basic dry mass with `dry_mass_kg`.
- `design_checks._spacecraft_key` already hashes the whole spacecraft, so
  the section on the spacecraft is in the cache key.

A spacecraft without a `budgets` section gives exactly the lines of
today. The golden files stay byte-identical.

## 6. Findings

New rules in `engine/findings.RULES`, emitted by a `_budget_warnings`
check in `plausibility_warnings`. The check returns nothing when no
spacecraft has a `budgets` section, so the golden texts do not change.
Per Q6, the messages may show values.

| Rule | When |
| --- | --- |
| `budget.placeholder` | an input the budget uses is a placeholder |
| `budget.unit_not_in_mode` | a system mode does not give an item a power mode |
| `budget.no_margin` | an item's maturity has no power margin, or the item has no maturity |
| `budget.mode_duty_sum` | mode duty cycles are all given and do not sum to 1 |
| `budget.mass_unknown` | an item's mass is a placeholder |

## 7. The IDM-CIC import

`PowerChoice` gets one more flag: `budgets`. When it is set,
`apply_power` also writes the `budgets` section:

- one item per placed unit with a power mode, `source_id` = the unit's
  `fullId`, `subsystem` = the IDM subsystem, `mass_in_model` true when the
  model import placed its shapes, else `mass_kg` from the unit;
- one power mode per IDM equipment power mode the system modes use, with
  `average_w` = `peak_w` = the IDM power, source "IDM-CIC file `<name>`";
- one system mode per IDM system mode, with its duty cycle; a unit the
  mapping does not cover is not listed (unknown, finding);
- one bus, "main", with a placeholder efficiency, and a placeholder
  distribution loss. The file gives neither. The import never guesses.

The import records target `"budgets"` (`IMPORT_TARGETS`). The CLI gets
`idm-import --budgets`. `bus_idle_power_w` behaves as before.

## 8. The window

- A **Budgets** area after Results, icon "budget", `Ctrl+5`. Timeline
  and Reports move to `Ctrl+6` and `Ctrl+7` (B-11).
- Tabs: **Equipment** (an editable grid with a model/view table: name,
  subsystem, bus, maturity, mass and source, and the power of each mode),
  **Power** (the budget of the selected spacecraft per mode: rows, per
  subsystem, per bus, totals, and an "unknown" badge with the reason),
  **Mass** (the mass budget table of Design Checks, with the new lines),
  **Propellant** (the `BudgetWidget`, moved from Run › Budget).
- The editor keeps the section through a channel like `set_operations`.
- Every empty list has an `EmptyState`. Copy as CSV on each table.

## 9. Delivery

Two pull requests, then the 2.11.0 release:

- **PR A, core:** schema 5 and the migration, `schema/budgets.py`, the
  power budget, the mass budget lines, the findings, the IDM-CIC import,
  the CLI, the generators (ICD, field help, editor fields), the reference
  tests, docs and the compliance records.
- **PR B, window:** the Budgets area and its four pages, the moved tab,
  the GUI tests, `docs/ui/TEST_CHANGES.md`, the user manual pages.

## 10. Risks and what protects against them

| Risk | Protection |
| --- | --- |
| The schema step changes the 72 hashes in `tests/data/scenario_hashes.json` and the 36 template files (`schema_version`). | The template change is that one line. The hash file is regenerated, and `docs/changes.md` explains it. The 36 golden output files do not change (they hold no version). |
| A file saved by 2.11.0 does not open in 2.10.0 or earlier. | This is the cost of the step the owner chose. The release notes say it. A 2.10.0 user can still open every older file. |
| A budgets check changes the golden texts. | The check returns nothing without a section. A test checks all 36 templates. |
| The moved tab changes GUI tests. | Q3 moved it. Each changed test line is logged in `docs/ui/TEST_CHANGES.md` with the reason "the Budget tab moved to the Budgets area (Q3)". No test is removed or weakened. |
