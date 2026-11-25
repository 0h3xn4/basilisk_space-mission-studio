# Tips

Shortcuts and good habits, and each file that the app reads and writes.
Use the file list to move data to and from other tools.

## Contents

- [Keyboard and palette](#keyboard-and-palette)
- [Working habits](#working-habits)
- [Scripting and batch runs](#scripting-and-batch-runs)
- [Files the app reads and writes](#files-the-app-reads-and-writes)
- [Other tools](#other-tools)

## Keyboard and palette

| Keys | Action |
|---|---|
| `Ctrl+K` | The command palette (the **Search...** box of the top bar). Type a few letters to find a command, an area, a page, a spacecraft, a setting, a template or a result series. |
| `Ctrl+R` | **Run**, in the mode beside it (**Single run**, **Monte Carlo**, **SIL (flight software in the loop)**) |
| `Esc` | **Cancel Run** |
| `Ctrl+Shift+R` | **Run This Case**: run the case picked in **Results › Monte Carlo › Runs** again, as a single run |
| `F1` | The User Manual |
| `Ctrl+Z`, `Ctrl+Shift+Z` (`Ctrl+Y` on Windows) | **Undo**, **Redo** a scenario edit. The menu names the edit. |
| `Ctrl+J`, `Ctrl+I` | Show or hide the **Problems** panel, the **Inspector** |
| `Ctrl+1` to `Ctrl+7` | Go to **Home**, **Scenario**, **Run**, **Results**, **Budgets**, **Timeline**, **Reports** |
| `Ctrl+N`, `Ctrl+O`, `Ctrl+S`, `Ctrl+Shift+S` | **New Scenario**, **Open...**, **Save**, **Save As...** |
| `Alt+Backspace` (also `Esc` in the **Timeline**) | **Clear Time Cursor** |
| `Alt+Right`, `Alt+Left` (with `Shift`: ten samples) | Move the time cursor one sample |
| `Alt+PgDown`, `Alt+PgUp`, `Alt+Home`, `Alt+End` | Move the time cursor to the next event, the previous event, the start or the end of the run |
| `Ctrl+Shift+N`, `Ctrl+Del` | **Add Equipment Item**, **Remove Equipment Item** (**Budgets › Equipment**) |
| `Ctrl+Shift+C` | **Copy as CSV**: the **Budgets** page that shows |
| `Ctrl+Shift+D` | **Open in Own Window**: the view that shows |

On the JSON page (**Scenario**, **JSON**), when the text has the focus:

| Keys | Action |
|---|---|
| `Ctrl+Space` | Suggest what you can type at the cursor: fields, choices, names |
| `Ctrl+Shift+Space` | Describe the key at the cursor: type, default, unit, meaning |
| `F8`, `Shift+F8` | Go to the next or the previous problem |
| `F2` | Rename the spacecraft, ground station or 3D model part at the cursor, everywhere |
| `F12` | Go to the definition of the name at the cursor |
| `Ctrl+.` | Show the quick fixes for the key or value at the cursor |
| `Shift+Alt+F` | Format the text |

**Help › Keyboard Shortcuts** (`Ctrl+/`) shows each shortcut in
**Settings › Keyboard**. The right-click menu of the JSON page shows its
keys. **Reports › Exports** lists each export and where you make it.

## Working habits

- **Save As first.** The templates never change on disk. Your edits stay
  only after you save them under your own name.
- **Read Overview before you run** (**Scenario › Overview**, also
  **View › Explain**). It predicts the ground passes. It warns about a
  set-up that cannot work, for example station keeping without drag.
  Its title gives the number of warnings: "Overview (1 to check)".
- **Change one thing at a time.** Run after each change. Then you know
  which change changed the result.
- **Compare runs.** Run, change one thing, and run again. **Results ›
  Compare** shows the differences in the inputs and in the results.
  **Compare with** in **Results** puts the earlier run on the plots. The
  app keeps the runs, so you can compare with a run of yesterday.
- **Use orbit only while you design the orbit.** It is much faster than
  full attitude.
- **Set Record every** (**Scenario › Environment**) for runs longer than
  a few weeks. If not, the results fill the memory.
- **Put the pointer on a field** to see a short explanation. When a value
  is not valid, the message at the bottom of the **Scenario** area names
  the field.
- **Write series names in the description** of your scenario, under
  "What to look at". They show as **Suggested** buttons in **Results**.

## Scripting and batch runs

- `spacemissionstudio validate` needs no Basilisk. Use it in CI to check
  scenario files.
- `spacemissionstudio run ... --out-dir` and `monte-carlo` give the same
  numbers as the GUI.
- `spacemissionstudio sil ... --max-error 1e-9` ends with exit status 5
  when external flight software does not agree with the simulation. Use
  it as a CI gate. An internal error ends with exit status 4.
- `spacemissionstudio run ... --bundle` makes a result folder that
  another person can run again. `spacemissionstudio reproduce` runs it
  and compares.
- `spacemissionstudio.api` ([The Python API](api.md)) gives a script the
  same lifetime, budget, run, comparison, design checks, model analyses
  and re-entry estimate as the app.
- The [examples](../examples/README.md) use the engine from Python:
  build a scenario, sweep a parameter, read a Monte Carlo batch.

## Files the app reads and writes

**The app reads:**

| File | Format | Where in the app, and the command |
|---|---|---|
| Scenario | JSON (`.json`) | **File › Open...** (`Ctrl+O`); every command |
| TLE | Two lines of text, pasted | The spacecraft dialog, **Orbit / mass** |
| Orbit messages | CCSDS OPM, OMM (KVN text) | The spacecraft dialog, **Orbit / mass › Import CCSDS OPM/OMM...**; `ccsds-import` |
| Orbit messages to check | CCSDS OPM, OMM, OEM (KVN text) | **Tools › Check a CCSDS File...**; `ccsds-validate` |
| Space weather | CelesTrak CSV or TXT | **Reference data** window, **Import file...**; **Scenario › Environment** |
| Solar activity prediction | NASA MSFC table (`.txt`) | **Scenario › Environment** |
| Earth orientation | NAIF Earth PCK (`.bpc`, `.cmt`) | **Reference data** window, **Import file...**; `earth-orientation --import` |
| 3D shapes | Wavefront OBJ (`.obj`, with its `.mtl`) | 3D model editor, **Import .obj...** |
| Mass properties | JSON or CSV | 3D model editor, **Mass properties**, **Import file...** |
| IDM-CIC model | `.idm` (IDM-CIC is © CNES; read only) | 3D model editor, **Import IDM-CIC model...**; `idm-import`, `idm-info` |
| Flight software | A program that follows the SIL contract | A run in **SIL** mode; `sil --binary` |
| Project configuration | YAML (`config_file` in the scenario) | **Scenario › Assumptions**; `assumptions` |
| Atmosphere gases data | ITU-R P.676-13 Part 1 (`.txt`) | **Reference data** window, **Import file...**; `gaseous-attenuation --import` |
| Small-body ephemeris | NAIF `eros_1900_2100.bsp` | **Reference data** window, **Import file...**; `small-bodies --import` |
| Plugins | Python packages with the entry point `spacemissionstudio.models` | At start ([Plugins](user-manual/plugins.md)) |
| Reproduction bundle | A folder from `run --bundle` | `reproduce` |

**The app writes:**

| File | Format | Where in the app, and the command |
|---|---|---|
| Scenario | JSON | **File › Save** (`Ctrl+S`), **File › Save As...** (`Ctrl+Shift+S`) |
| Results | CSV, one file for each series, SI units, time in seconds | **Results › Plots › Export CSV...**; `run --out-dir` |
| Events | CSV (seconds and UTC) | **Timeline › Export CSV...**; `run` (`events.csv`) |
| Mission output | CSV | **Results › Output › Export CSV...** |
| Provenance | JSON: the versions and checksums of each input | Beside or in every export |
| Scenario as run | JSON (`scenario_as_run.json`) | `run --out-dir`, beside the results |
| Reproduction bundle | A folder: results, provenance, the scenario as run, copies of its files (`bundle.json`) | **Results › Plots › Export all... › Reproduction bundle...**; `run --bundle` |
| Plots | PNG, SVG | **Results › Plots › Save PNG...**, **Save SVG...**; **Export all...** (each plot that shows, with CSV) |
| Lifetime | JSON with the inputs, the traces and the provenance | **Run › End of Life › Export JSON...**; `lifetime --out` |
| Propellant budget | CSV on the clipboard | **Budgets › Propellant › Copy as CSV**; `budget --out` (JSON) |
| Power and mass budgets, equipment list | CSV on the clipboard | **Budgets › Power**, **Mass** or **Equipment**, **Copy as CSV** (`Ctrl+Shift+C`) |
| Design checks | JSON, and a CSV file for each table | **Run › Design Checks › Save...**; `check-design --out --tables` |
| Model analyses | JSON, and a CSV file for each table | **Results › Model Analyses › Save...**; `model-analyses --out --tables` |
| Thermal analysis | JSON, CSV tables and series, SVG and PNG plots | **Run › Thermal › Save...** |
| Re-entry estimate | JSON with the provenance | **Run › End of Life › Re-entry casualty › Save...**; `reentry --out` |
| Operations plan and products | JSON; CSV, iCalendar, CCSDS OEM and AEM, Markdown | **Run › Plan › Save plan...**, **Run › Plan › Export...** |
| Change history | `mission.history.jsonl` beside `mission.json` | Each save; **File › Change History...** |
| Orbit messages | CCSDS OPM, OMM, OEM (KVN text) | **File › Export Orbits as CCSDS...**; **Results › Plots › Export all... › CCSDS ephemeris (OEM)...**; `ccsds-export`, `run --oem` |
| Monte Carlo batch | `batch_results.npz` and `.json`, and Basilisk's archive | A run in **Monte Carlo** mode; `monte-carlo --archive-dir` |
| Monte Carlo table and report | CSV; Markdown or JSON | **Results › Monte Carlo › Export table CSV...**, **Export report...** |
| 3D model | Wavefront OBJ and `.mtl` | 3D model editor, **Export .obj...**; `model --export-obj` |
| Flight software | A C project with CMake, `ICD.md`, `TRACEABILITY.md`, `manifest.json` | **Reports › Flight Software › Export...**; `export-fsw` |
| SIL report | JSON and CSV | **Reports › Flight Software › Save report...**; `sil --report` |
| Logs | Text | `~/.spacemissionstudio/logs/` |
| Network log | Text, one line for each network use that the app allowed or refused | `~/.spacemissionstudio/logs/network.log` |
| Offline choice | JSON | `~/.spacemissionstudio/network.json` (**Settings › Network**) |

## Other tools

SpaceMissionStudio has **no direct link** to Harness Design Studio,
Requirements Studio, Budget Studio, AIT Logbook or ICD Studio. It does
not import from them or export to them. It has no format for them.

To move data to such a tool, use a format that the tool reads: CSV,
JSON, CCSDS, or the `ICD.md` of the flight software export. For other
flight dynamics tools, CCSDS messages are the standard route. See
[Orbit files](user-manual/orbit-files.md) for the limits of GMAT.

---

**Next:** [How-to guides](user-manual/README.md) ·
[Use the command line](user-manual/command-line.md) ·
[FAQ](faq.md)
