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

## B-15 A read-only place for the section in the spacecraft editor (2026-11-17)

**Chosen:** the spacecraft editor keeps the `budgets` section unchanged
through an edit. Its Power tab shows a read-only group, "Equipment list
and power modes", with the number of items, system modes and buses. The
group is visible only when the spacecraft has a section. A problem in the
section opens this group. **Alternatives:** no place until PR B; leave
the section out of the two GUI tests that need a place for every
spacecraft field. **Why:** without the copy, an edit of the spacecraft
in the window deleted the section. The tests
`test_every_spacecraft_field_has_a_place` and
`test_every_numeric_spacecraft_field_has_a_title` require a place for
each field, and the hard rule does not let PR A change what they check.
PR B can move the place to the Budgets area.

## B-16 An item without power modes is in the mass budget only (2026-11-17)

**Chosen:** an equipment item with no power mode (a structure, a
harness) is not in the power budget. A system mode that does not list it
gives no finding, and it needs no bus. An item with power modes must
name a bus. **Alternatives:** an unknown power in every mode, as B-09
gives an item a mode does not list. **Why:** in SBS each unit has at
least one power mode, and a unit that draws nothing has a 0 W mode. Here
the equipment list also holds mass-only items. To call their power
"unknown" would mark every budget with such an item incomplete without a
reason.

## B-17 A placeholder may have an empty source (2026-11-17)

**Chosen:** a sourced value with a null `value` may have an empty
`source`. A number with an empty source is refused, as the design note
says. **Alternatives:** SBS refuses an empty source on every sourced
value. **Why:** the design note refuses only a number without a source,
and an empty cell of the Equipment grid (PR B) is then a valid
placeholder. The design note's example has `"mass_column": "avionics"`,
which is not an S-120 column; the rule of section 3 applies, so the
example is not a valid file in that one field.

## B-18 The Equipment grid holds the item fields; the power modes have their own table (2026-11-17)

**Chosen:** the grid of Budgets › Equipment has one column per item
field: name, subsystem, mass column, bus, maturity, mass, mass source and
"mass in model". The power modes of the item picked are a second table
(name, average and peak with their sources, duty cycle). The system
modes are a third table (name, duty cycle, the power mode of each item).
The section's numbers (distribution loss, system margin, efficiency per
bus, margin per maturity) are a fourth, "Power settings". **Alternatives:**
the design note's section 8: the power of each mode as more columns of
the grid. **Why:** an item has any number of power modes, each with two
sourced values and a duty cycle. As columns they make a grid with a
varying shape that does not fit 1280 px. The owner's task for PR B asked
for the item fields in the grid and the power modes in a details table.
The editable grids keep the file's order (B-10), so they do not sort;
`Ctrl+C` copies their rows as TSV, as `DataTable` does.

## B-19 The rail shows icons only when it is too short for the names (2026-11-17)

**Chosen:** the navigation rail shows icons only while its height is
less than it needs with the names. The names come back when there is
room. It is not the user's "icons only" choice: that stays as it was.
Each button keeps its tooltip ("Budgets (Ctrl+5)") and its accessible
name. **Alternatives:** smaller rail buttons for everyone; a scrolling
rail. **Why:** with Budgets, the rail has eight areas. At 1280 x 720
with the Problems panel open, the rail is 510 px high and needs 578 px
with the names: Settings and Help lost their labels (measured). Before
Budgets it needed 519 px.

## B-20 The Budgets area's icon is Lucide's "calculator" (2026-11-17)

**Chosen:** `calculator.svg` from the same `lucide-static` 1.52.0
archive (SHA-256 checked against `docs/THIRD_PARTY_ASSETS.md`), copied
unchanged. **Alternatives:** the design note's "budget" (Lucide has no
icon of that name); an icon already bundled. **Why:** a budget sums
numbers; no bundled icon says that, and the rail's icons are all
different.

## B-21 The Budgets commands are window commands (2026-11-17)

**Chosen:** Budgets › Add Equipment Item (`Ctrl+Shift+N`), Remove
Equipment Item (`Ctrl+Del`) and Copy as CSV (`Ctrl+Shift+C`) are
commands of the registry, in **Tools > Budgets** and the palette. Their
shortcuts are the window's. Remove and Copy act only on the Budgets page
shown; from another area they show the area and change nothing.
**Alternatives:** shortcuts that work only inside the area, as the time
cursor's do in Results. **Why:** `test_shell_reachability.py` requires
every command except the time cursor's to be on the window, and a GUI
test may not change what it checks. Acting only on the page shown keeps
`Ctrl+Del` from removing an item the user does not see.

## B-22 Add makes placeholders, never a number (2026-11-17)

**Chosen:** a new item has the mass `{"value": null, "source": "TBD"}`;
a new power mode the average `{"value": null, "source": "TBD"}`; a new
bus a placeholder efficiency. **Add Budgets Section** makes one bus,
"main", and placeholders for its efficiency, the distribution loss and
the system margin, as the IDM-CIC import does (B-08). An item that gets
its first power mode takes the bus when the section has only one, since
an item with power modes must name a bus. **Alternatives:** zeros; an
empty section. **Why:** never guess a number; a placeholder is visible
("TBD" and a finding) and does not stop a run, where an empty source
would.

## B-23 The budgets are computed on the GUI thread, for the page shown (2026-11-17)

**Chosen:** the Budgets pages compute on the GUI thread, only the page
shown, only while the area is shown, and only when the spacecraft
changed. **Alternatives:** a worker thread, as Design Checks. **Why:**
the calculation is small. Measured offscreen, without painting: with
the 18 items of the SBS `microsat_250kg_clean` example, at most 20 ms;
with 180 items, at most 31 ms for a page and 0.5 ms when nothing
changed. A worker would add a waiting state to a page that is ready at
once.

## B-24 A problem in the section opens Budgets › Equipment (2026-11-17)

**Chosen:** a problem or finding whose field is in the `budgets`
section opens Budgets › Equipment of its spacecraft. The spacecraft
editor's read-only group (B-15) stays, so the two GUI tests that need a
place for every spacecraft field are unchanged; its text now points to
the Budgets area. **Alternatives:** the group in the spacecraft editor,
as in PR A. **Why:** the section is edited in the Budgets area.

## B-25 Power and Mass CSV are not rows of Reports › Exports (2026-11-17)

**Chosen:** Copy as CSV on Equipment, Power and Mass copies to the
clipboard with the scenario's provenance, as the propellant budget does.
They are not new rows of Reports › Exports; the Budget row's "Made in"
now says Budgets › Propellant › Copy as CSV. **Alternatives:** three new
rows. **Why:** `test_reports_and_settings.py` pins the list of exports,
and Q3 moved a tab; it did not add exports. A later version can add the
rows with their test.
