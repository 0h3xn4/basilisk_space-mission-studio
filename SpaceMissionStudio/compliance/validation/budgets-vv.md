# Verification and validation: equipment list and static power budget

This is the record of how the `budgets` section and the static power
budget (requirement SRS-F-31) were checked. Each case is a test that runs
in the suite. The reference is a hand calculation, System Budget Studio
(SBS) 2.15.1's own reference cases and results, or the code before the
change. It is never the code under test. Measured 2026-11-17 on Python
3.14, x86-64. The design is in
`docs/developer/system-budget-phase1-design.md`. The decisions (B-nn) are
in `docs/developer/system-budget-decisions.md`.

The budget is a design check. No run uses it (B-14).

## The power budget (`tests/test_power_budget_reference.py`)

| Case | Reference | Tolerance | Result |
|---|---|---|---|
| SBS cases 01 to 17: the scalar steps, the full chain on three units and two buses, a zero duty cycle, placeholder and missing margins, a TBD source, missing settings, a unit off, the order, the findings, determinism | SBS `tests/regression/test_static_power.py`, the same inputs and expected numbers (classes m1 and m2 as `estimated` and `layout`, B-05; ratios as percent, B-07) | relative 1e-12 | Equal |
| Case 15, the order | SMS keeps the file's order (B-10); SBS sorts by id | exact | The file's order |
| SBS example `microsat_250kg_clean`: the five modes' load, system-margined load and source power with margins; the peaks; the imaging mode's buses and subsystems | SBS 2.15.1 run on the example (the study's section 2.6; its compare golden file) | relative 1e-12, or 5e-7 W for a value given to 6 decimals | Equal |
| The same example, source power | The system-margined load / (0.9 × 0.97): both buses at 0.9, loss 0.03 | relative 1e-12 | Equal |
| The example as a fixture | Each unit, mode, margin, efficiency and loss compared with the SBS YAML files by a script, once | exact | Equal |
| An item a mode does not list, a placeholder power, the duty-cycle average | Hand calculation | relative 1e-12 | Unknown where it must be, never 0; the average equals the weighted sum |

## The section and the mass budget

| Case | Reference | Result |
|---|---|---|
| Round trip, absence, placeholders, every refusal (`tests/test_budgets_schema.py`) | The design note's rules (section 3) | As specified; a scenario without the section saves as before |
| The mass budget of the 47 spacecraft of the 36 templates | The module before the change, loaded from git, once | Identical lines, notes and totals |
| The equipment list's mass lines (`tests/test_budgets_mass_and_findings.py`) | Hand calculation with AIAA S-120's allowances | Equal |
| No template gives a `budget.*` finding; the golden output files | `tests/test_golden_outputs.py` | Unchanged |

## The schema step

The 36 templates at version 5, with the version set back to 4, give the
recorded version 4 hashes of their saved text and their scenario (checked
once, `docs/changes.md`). A version 4 file opens with no recorded change
(`tests/test_migrations.py`).

## The IDM-CIC import (`tests/test_budgets_import_and_cli.py`)

| Case | Reference | Result |
|---|---|---|
| Cruise's load from the imported section | The IDM-CIC total of `idm.power.mode_powers`, 10.5 W | Equal |
| An item's mass without the model merge | The masses the model import gives the unit's parts | Equal |
| The bus load with and without the section | The power budget and its record without the flag | Identical |

The model is synthetic (`tests/data/idm/powersat`). No real IDM-CIC file
is used.
