# System Budget Studio merge: decision log

Every non-trivial choice made while moving System Budget Studio (SBS)
features into SpaceMissionStudio (SMS), with the alternatives and the
reason, in place of asking the owner. Plan:
[system-budget-merge-design.md](system-budget-merge-design.md); phase 1:
[system-budget-phase1-design.md](system-budget-phase1-design.md). The
owner's answers Q1 to Q7 are in the plan, section 7.

## B-01 Scenario schema version 5 (2026-11-17)

**Chosen:** `CURRENT_SCHEMA_VERSION` becomes 5. The migration from 4 to 5
only sets the version. The 36 templates are saved at version 5, and
`tests/data/scenario_hashes.json` is regenerated (`docs/changes.md`).
**Alternatives:** no step, only the section's own `version`, as thermal
(T-02) and operations (O-06) did. **Why:** the owner accepted the plan
with "schema version 5 with a migration from 4", and the hard rule of
2026-11-17 asks for a version step when a file format changes. The cost
is known: a file saved by 2.11.0 does not open in 2.10.0. The release
notes say so.

## B-02 The section is per spacecraft (2026-11-17)

**Chosen:** `SpacecraftConfig.budgets`, as `SpacecraftConfig.thermal`.
**Alternatives:** a scenario-level section with a spacecraft key per
entry (the operations pattern). **Why:** power, the 3D model, the mass
budget and thermal are per spacecraft; a per-spacecraft section needs no
rename handling and goes with the spacecraft when it is copied.

## B-03 The equipment list is its own list, not the 3D model's equipment (2026-11-17)

**Chosen:** `budgets.equipment` items with a name, a functional
subsystem, an S-120 mass column, a bus, a maturity, a sourced mass, the
flag `mass_in_model` and sourced power modes. **Alternatives:** extend
`MountedEquipmentConfig` with power fields; refer to it by name.
**Why:** a mounted item needs a 3D model, a mount position and a
boresight, and its mass changes the run's mass properties. Many budget
items (harness, a PCDU inside the bus) have no place in the model. The
flag `mass_in_model` keeps one mass from being counted twice when the
model already holds it. A link by name to model parts can come later
without a format change.

## B-04 The sourced value and the placeholder (2026-11-17)

**Chosen:** a budget number is `{"value": number or null, "source":
text}`. It is a placeholder when the value is null or the source is
"TBD", as in SBS. A placeholder gives "unknown" to every result that
uses it. A number with an empty source is refused. **Alternatives:**
`ValueMark` (it needs a finite number); a plain number (no source).
**Why:** Q5 puts the placeholder in the `budgets` section only. The
`ValueMark` and the parameter registry stay as they are.

## B-05 Maturity codes are the mass policy's (2026-11-17)

**Chosen:** an item's `maturity` is "" or a category of the spacecraft's
mass policy (`estimated`, `layout`, `pre_release`, `released`,
`existing`, `measured` for AIAA S-120). The power margin table is keyed
by the same codes. **Alternatives:** SBS's free class names. **Why:** SMS
wins; one maturity drives both the mass growth and the power margin. The
SBS reference cases use two classes; they map to `estimated` and
`layout` with the same numbers.

## B-06 Two subsystem fields (2026-11-17)

**Chosen:** `subsystem` is the functional subsystem (AOCS, DHS, as in
IDM-CIC and SBS) and groups the power budget. `mass_column` is "" or an
S-120 column and picks the growth allowance. **Alternatives:** one field
used for both. **Why:** the two meanings differ; with one field, an
"AOCS" item would always get the largest allowance of its row.

## B-07 Percent for margins, ratios for efficiencies (2026-11-17)

**Chosen:** `power_margins[].percent` and `system_power_margin_percent`
in percent; `converter_efficiency`, `distribution_loss` and `duty_cycle`
as ratios from 0 to 1. **Alternatives:** SBS's ratios everywhere.
**Why:** the SMS mass budget uses percent for margins and
`panel_efficiency` is a ratio. The arithmetic is the same: the reference
tests keep their numbers within 1e-12.

## B-08 The IDM-CIC import can fill the section (2026-11-17)

**Chosen:** a new `PowerChoice.budgets` flag and `idm-import --budgets`.
The import writes one item per unit with a power mode, the system modes
with their duty cycles, one bus "main" and placeholders for what the file
does not give (efficiency, distribution loss, margins). **Alternatives:**
keep the modes in memory only (today). **Why:** Q7: one equipment list
and one power-mode model, filled by the IDM-CIC import. The import never
guesses a number.

## B-09 An item a mode does not list is unknown, not an error (2026-11-17)

**Chosen:** the power of an item that a system mode does not list is
unknown in that mode, with the finding `budget.unit_not_in_mode`.
**Alternatives:** refuse the file (SBS `UNIT_NOT_MAPPED`); count 0 W
(the IDM-CIC bus load today). **Why:** the IDM-CIC files have unstated
units. Zero would hide them; a refusal would stop the import.

## B-10 File order, not alphabetical order (2026-11-17)

**Chosen:** modes, rows, buses and subsystems follow the order in the
file (subsystems and buses: first use). **Alternatives:** SBS sorts by
id. **Why:** SMS keeps the user's order in every list. SBS reference case
15 tests the SBS order; the port tests the file order instead and says
so in the test.

## B-11 The Budgets area takes Ctrl+5 (2026-11-17)

**Chosen:** Budgets after Results in the rail, `Ctrl+5`; Timeline and
Reports move to `Ctrl+6` and `Ctrl+7`. **Alternatives:** put Budgets
last (`Ctrl+7`). **Why:** Q3 places the area beside the results; the
shortcuts follow the rail order, as the existing tests require.

## B-12 An editable table model for the Equipment grid (2026-11-17)

**Chosen:** a new `QAbstractTableModel` with `ItemIsEditable` and a
`QTableView` from the components. **Alternatives:** `QTableWidget` (the
UI rules forbid it for lists that can be large); a form per item.
**Why:** an equipment list has tens to hundreds of rows and is edited
like a spreadsheet.

## B-13 Budget findings are SMS findings (2026-11-17)

**Chosen:** `budget.*` rules in `engine/findings.RULES`, emitted from
`plausibility_warnings` only when a spacecraft has a `budgets` section.
They may show values (Q6). **Alternatives:** the SBS problem catalogue.
**Why:** SMS wins; one Problems panel.

## B-14 The run does not use the budget yet (2026-11-17)

**Chosen:** phase 1 changes no run. `bus_idle_power_w` and `dry_mass_kg`
stay the run's inputs. The Mass page notes the difference between the
budget's dry mass and `dry_mass_kg`. **Alternatives:** feed the budget
into the run now. **Why:** phase 2 makes the power modes a Basilisk sink;
the golden files must not change in phase 1.
