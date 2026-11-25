# Writing style

How to write SpaceMissionStudio documentation. The rules follow the
public principles of ASD-STE100 Simplified Technical English (STE). This
page is a short summary in our own words, not the specification. The
check `scripts/check_writing.py` tests the rules that a script can test.

## Which documents follow it

| Follow this page | Keep their own form |
|---|---|
| The READMEs (the root README's SpaceMissionStudio part, `SpaceMissionStudio/README.md`, the folder READMEs) | Append-only records: `CHANGELOG.md`, `HISTORY.md`, `docs/DECISIONS.md`, `BACKLOG.md`, `docs/ui/TEST_CHANGES.md` |
| Getting started, the FAQ, the tips, troubleshooting, the glossary, the documentation index | The CHANGELOG and the release notes keep a natural voice (the owner's decision) |
| The how-to guides (`docs/user-manual/`) and the User Manual | Generated documents (`compliance/docs/` tables, `spacemissionstudio/help/`, `field_help.json`) |
| The model and reference pages (`docs/models/`, `docs/reference/`) | Basilisk's own documents (everything outside `SpaceMissionStudio/`, and the root README from "Original Basilisk README" down) |
| The developer guides (`docs/developer/`) | Quoted text: messages, licences, standards |

The documents that pass the check are listed in
`tests/test_writing_style.py`. Add a document to that list when you
rewrite it.

## The rules

<!-- check-writing: off -->

| Rule | Write | Do not write |
|---|---|---|
| A procedure sentence has 20 words or fewer | Click **Run**. | When you are ready to start the simulation, you can now click the Run button in the top bar. |
| A description sentence has 25 words or fewer | The run uses NASA MSFC's prediction after the end of the observed record. | (one long sentence with three clauses and two lists) |
| One instruction in each sentence | Open the template. Click **Run**. | Open the template and then click Run. |
| Use the imperative for steps | Save the scenario. | You should save the scenario. |
| Use the active voice | The app writes the log file. | The log file is written by the app. |
| Use the present tense | The run stops. | The run will stop. |
| One word for one meaning, one meaning for one word | Use the names in the [term list](#term-list) only. | the sidebar, the nav bar, the rail (for one thing) |
| Use a simple verb, not a phrasal verb | Do the check. Find the cause. | Carry out the check. Find out the cause. |
| Keep the articles | Click the **Run** button. | Click Run button. |
| Keep paragraphs short: 6 sentences or fewer | Split a long paragraph, or make a list. | |
| Put lists and tables before prose | A table of the install paths. | A paragraph that compares three install paths. |
| Use the app's names exactly | **Settings › About** | the About page in the preferences |

<!-- check-writing: on -->

More rules:

- **Steps** are a numbered list, one action in each step. Put the result
  of a step after the step, in a new sentence: "The Results area opens."
- **Warnings and cautions** come before the step that they apply to.
- **Numbers** have their unit: `550 km`, `35 min`, `1.7 GB`.
- **Abbreviations:** write the full term the first time on a page, or
  link it to the [glossary](../glossary.md).
- **Links:** use relative links to files in the repository. A link text
  says where the link goes ("Getting started"), not "here".
- **Code, commands, file names and keys** are in `code`: `Ctrl+R`,
  `spacemissionstudio run`, `scenario.json`.
- **Names in the app** (areas, tabs, menus, buttons, fields) are in
  **bold** and are spelled as the app spells them, with its capitals.
- **A path in the app** uses "›", as the app does:
  **Results › Plots**, **File › Save As...**. Do not use ">".
- **Block quotes** are for quoted text only (a message, a licence
  clause). Do not put your own text in a block quote.
- **Examples of bad text** in a document go between the lines
  `<!-- check-writing: off -->` and `<!-- check-writing: on -->`. The
  check does not read them.
- **History** goes to `CHANGELOG.md` and `HISTORY.md`. A user document
  tells what is true now. It does not tell what changed in which
  release, except where a user must know it (a file that an older version
  cannot open).

## Term list

Use these names, and only these names, for the parts of the app. They
come from the code: the navigation rail (`gui/shell.py`), the menu bar
(`gui/menu_bar.py`), the commands (`gui/actions.py`, the command
palette), and the area pages. When the app changes a name, change it
here and in every document of the list in `tests/test_writing_style.py`.

### The window

| Name | What it is |
|---|---|
| navigation rail | The column of area buttons at the left edge |
| area | One button of the navigation rail and its page: **Home**, **Scenario**, **Run**, **Results**, **Budgets**, **Timeline**, **Reports**; at the bottom **Settings** and **Help** |
| top bar | The bar at the top: the scenario name, **Save**, undo and redo, **Run**, the run mode (**Single run**, **Monte Carlo**, **SIL (flight software in the loop)**) and **Search...** |
| command palette | The search box of the top bar (`Ctrl+K`); it finds every command, area, page, setting, template and result series |
| menu bar | **File**, **Edit**, **View**, **Go**, **Run**, **Tools**, **Help** |
| **Inspector** | The panel at the right (`Ctrl+I`) |
| **Calculation** panel | The panel that **Show calculation** opens (**View › Calculation**) |
| **Problems** panel | The panel at the bottom (`Ctrl+J`) |
| status bar | The bar at the bottom edge |
| own window | A view that you move out of the main window (**View › Own Windows**, `Ctrl+Shift+D`) |

### The areas and their pages

| Area | Pages and main buttons |
|---|---|
| **Home** | The template cards in nine categories; in a card's details **Open template** and **Customize and open...**; **New blank scenario**; **Open a scenario file...**; the card **Fetch or update reference data?** with **Fetch now** and **Not now** |
| **Scenario** | **Form** and **JSON** (the JSON page); **3D Model**; **Change History**. The tree: **Overview** (Explain), **General**, **Environment**, **Spacecraft** (each spacecraft: **Orbit / mass**, **Power / propulsion / link budget**, **3D model**, **Budget (AD10)**), **Ground stations**, **Mission sequence**, **Monte Carlo**, **Assumptions** |
| **Run** | Tabs **Run**, **End of Life**, **Design Checks**, **Thermal**, **Plan**, **History**, **Log**; buttons **Run**, **Cancel Run**, **Check Reference Data** |
| **Results** | Tabs **Overview**, **Plots**, **3D View**, **Dashboard**, **Output**, **Compare**, and **Model Analyses** and **Monte Carlo** when the run has them |
| **Budgets** | Tabs **Equipment**, **Power**, **Mass**, **Pointing**, **Propellant** |
| **Timeline** | The events of the run: passes, eclipses, burns, modes |
| **Reports** | Tabs **Exports** and **Flight Software** |
| **Settings** | Sections **Appearance**, **Reference data**, **Network**, **Change history**, **Layout**, **Keyboard**, **About** |
| **Help** | Opens the User Manual (`F1`) |

### Windows and dialogs

| Name | How to open it |
|---|---|
| **Reference data** window | **Tools › Reference Data...**, or **Settings › Reference data** |
| 3D model editor | **Tools › 3D Model...**, or **3D Model** in the Scenario area |
| Customize dialog | **Customize and open...** on a template card |
| User Manual | **Help** on the navigation rail, **Help › User Manual**, `F1` |
| **About SpaceMissionStudio** | **Help › About SpaceMissionStudio**, or **Settings › About** |

### Menus and shortcuts

| Menu | Items (shortcut) |
|---|---|
| **File** | **New Scenario** (`Ctrl+N`), **Open...** (`Ctrl+O`), **Open Recent**, **Save** (`Ctrl+S`), **Save As...** (`Ctrl+Shift+S`), **Change History...**, **Export Orbits as CCSDS...**, **Quit** |
| **Edit** | **Undo** (`Ctrl+Z`), **Redo** (`Ctrl+Shift+Z`; `Ctrl+Y` on Windows), **Settings...** (`Ctrl+,`) |
| **View** | **Inspector**, **Calculation**, **Problems**, **Explain**, **Own Windows**, **3D View**, **Menu Bar**, **Status Bar: All Details**, **Navigation: Icons Only**, the three themes, **Reset Layout**, **Command Palette...** (`Ctrl+K`) |
| **Go** | **Go to Home** to **Go to Reports** (`Ctrl+1` to `Ctrl+7`), **Time Cursor** |
| **Run** | **Run** (`Ctrl+R`), **Cancel Run** (`Esc`), **Run Mode**, **Live plot**, **End of Life**, **Budget**, **Design Checks**, **Thermal**, **Plan**, **Open Monte Carlo Results...**, **Run This Case** (`Ctrl+Shift+R`) |
| **Tools** | **3D Model...**, **Flight Software**, **Budgets**, **Check a CCSDS File...**, **Reference Data...**, **Check Reference Data** |
| **Help** | **User Manual** (`F1`), **Keyboard Shortcuts** (`Ctrl+/`), **Third-Party Licences...**, **About SpaceMissionStudio** |

### Things and files

| Name | What it is |
|---|---|
| scenario | One mission set-up, saved as a JSON file (`.json`) |
| template | A ready-made scenario that comes with the app (47, in nine categories) |
| run | One simulation of a scenario; its results |
| Monte Carlo batch | Many runs of one scenario with drawn inputs |
| reference data | The data files that runs need: SPICE kernels, gravity fields, the magnetic model, Earth orientation, space weather |
| project configuration file | A YAML file that changes the parameters of a project (`config_file`) |
| change history | `mission.history.jsonl` beside the scenario |
| provenance | `provenance.json`, written with each run's results |
| reproduction bundle | A folder that runs a result again (`run --bundle`) |
| installer | The Linux `.deb` package or the Windows setup program |
| setup program | The Windows installer, `spacemissionstudio-<version>-setup.exe` |

## Words not to use

`scripts/check_writing.py` reads this table. Each word or phrase in the
left column is an error in a checked document, outside code. Separate
the variants with commas.

<!-- check-writing: off -->

| Do not use | Use |
|---|---|
| sidebar, side bar, nav rail, navigation bar, nav bar | navigation rail |
| start page, start screen, welcome page, welcome screen | **Home** |
| preferences, options dialog | **Settings** |
| toolbar, tool bar | top bar |
| scenario editor | the **Scenario** area |
| Results tab, Results page, Results view, Results window | the **Results** area |
| problems pane, problems view | the **Problems** panel |
| reference data dialog, Reference Data dialog | the **Reference data** window |
| e.g. | for example |
| i.e. | that is |
| etc. | (list the items) |
| click on | click |
| in order to | to |
| utilize, utilise | use |
| please | (delete it) |
| simply, just | (delete it) |
| carry out | do |
| find out | find |
| look up | find |
| set up | install, prepare, make |
| make sure | check that |
| fill in | write, type |

<!-- check-writing: on -->

---

**Next:** [Developer guide](README.md) ·
[Documentation index](../README.md)
