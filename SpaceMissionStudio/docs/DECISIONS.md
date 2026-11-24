# Decisions

Choices made where the brief (`docs/ui/UI_OVERHAUL.md`) or the plan
(`docs/ui/UI_OVERHAUL_PLAN.md`) is silent, each with a one-line rationale.
The user's own answers to the plan's questions are in the plan's §9.
Newest milestone first.

## The app icon shows a mission (2026-11-17)

The owner's request: the icon did not show what the tool does; the Earth
must look like the Earth; the icon must be visible in dark mode on Ubuntu
and Windows.

- **A scene, not an object:** the Earth, an orbit (solid where flown,
  dashed ahead), a satellite with a beam to a ground station, the Sun.
  Why: each stands for something the tool analyses (orbits, pointing and
  power, passes and links, eclipses); a lone satellite showed hardware
  only.
- **The Earth is the bundled Blue Marble texture**, projected onto a lit
  globe once (about 22 ms warm, 100 ms the first time in a process with
  the JPEG decoder and numpy still to load) and scaled for every size.
  Why: drawn blob continents read as a blue ball; the texture is already
  bundled and public domain, so no new asset or dependency.
- **Africa, the Mediterranean and Europe in view** (centre 20 deg E,
  20 deg S). Why: the most recognisable outline in the visible cap.
- **No eye shape:** the planet is cut by the plate's corner and the orbit
  is an open arc. Why: the first icon, a disc in a centred ring, read as
  an eye at 16-32 px.
- **The scene replaces the satellite on #276's plate.** #276 (merged while
  this was open) kept the satellite and added the plate, the rim, every
  hicolor size, the SVG and the `.ico`. The owner chose the scene ("I want
  your new design"). Why: the plate, its tests and the packaging carry
  any drawing; only the drawing changes.
- **The plate and rim in the scene's navy:** `plate` `#1A2C57`, flat at
  the top and deepening to `#0A1128`, `rim` `#5B7FC7`. Why: the scene's
  colours; they still meet #276's measured 3 : 1 on every dark and light
  panel (the rim 3.33 : 1 on #303030, the lowest) and on the Windows dark
  taskbars.
- **The scene cuts its own shapes to the plate,** not with a clip path.
  Why: `QSvgGenerator` writes no clip paths, so the SVG showed the orbit
  and the Earth outside the rim.
- **An AppUserModelID at start-up on Windows.** Why: without it the
  taskbar groups the window under `pythonw.exe` with Python's icon.

## The 3D View live (2026-11-10)

The owner's request: the 3D View must also work as a live renderer. This
entry adds to "The 3D View as a renderer: three.js" below.

- **A probe in the dynamics task, not samples between run chunks.** A
  Python `sysModel.SysModel` added last to the dynamics task reads each
  spacecraft's state every N steps. Measured: about 1 µs a dynamics step
  and 50 µs a sample (template 06, 43,200 steps of 0.1 s: +4 %; template
  01, a sample every step: +19 %, 0.15 s). Sampling between chunks
  instead needs one `ExecuteSimulation` call per sample and, in
  `run_live`, a result extraction that costs O(samples) each time. Why:
  the probe is cheaper, samples at exact step times, and works the same
  in Mission Sequences (which have no `run_live`) and segmented runs.
- **The probe reads, and is added after the seeds.** It reads the state
  message and the attitude message the results use, and is added after
  `assign_rng_seeds`, so it has no seed and is not in the provenance.
  Why: no number may change. Checked: every template's golden
  fingerprint is the same, as JSON text, with the probe and without it,
  and the golden and regression tests pass with the probe on.
- **An engine change during the overhaul.** CLAUDE.md allows UI changes
  only; the owner asked for a live view, which needs the run's states as
  they are computed. The change is a module that exists only when the
  live view is on, and a field on the service. Why: the owner's request;
  no output changes.
- **How often:** 200 samples an orbit (the shortest at the start), in
  whole dynamics steps; with a pace, at least 20 a real second where the
  step allows; at most 20,000 a run (100,000 paced). Why: smooth enough
  to watch, small enough for the page.
- **Pacing in the probe, on the worker thread:** it sleeps while the
  simulated time is ahead of the wall clock times the factor, in 50 ms
  slices, and stops waiting on Cancel. A run more than 1 s behind starts
  its pace again. Why: the run itself waits; nothing else needs a clock.
- **The GUI drains the feed 20 times a second,** at most 400 samples
  (2,400 spacecraft states) a tick, measured at most 17 ms. Why: the GUI
  thread's 50 ms budget.
- **The frames' Earth rotation, Sun, Moon and line of sight are computed
  in Python** by `scene3d.extend_scene`, which `build_scene` now uses
  too. Why: one source of truth for a finished run and a live one.
- **At the end, the result replaces the live frames** (`set_run`, built
  off the GUI thread as before), in the same view, with the camera kept
  and the newest time shown (or the time the user went back to). Why:
  the result has every series; the live frames have only states.
- **The 3D View opens when a live run starts and stays open at the end,**
  rather than switching to the plots. Why: the user asked to watch it.
- **Not in SIL mode.** Why: `sil.runner` builds its own services and
  bridge; adding the probe there is left for later.
- **Reduced quality from the start on a software renderer** (the WebGL
  renderer's name contains SwiftShader, llvmpipe, softpipe or Software);
  the switch after slow frames stays. A quality chosen in Show is kept
  over the page's own. Why: the first frames were slow before the switch.
- **"Go live" uses the bundled `circle-dot` icon.** Why: no new icon.

## Vizard removed (2026-11-10)

The owner: "I don't want any trace of vizard left in spacemissionstudio".
**Results › 3D View** is the app's 3D view.

- **Everything goes:** the playback file, the live stream, starting a
  Vizard, its settings, Run options, export row, commands, icons, CLI
  options, scenario fields and the controllers' messages that only fed
  its panels. Why: the owner's request.
- **The controllers' telemetry that feeds logs, results and events stays**
  (`last*Km`, the battery, the fuel tank, the access messages, the
  model's `.obj` groups). Why: no result may change; the golden outputs
  are unchanged.
- **Old files open; the retired fields are dropped on load and recorded**
  (`schema/migrations.py`, step "retired fields", in the run's
  `scenario_file_migrations`), and `Scenario.from_dict` drops them too.
  Why: every saved scenario has them, and the loader refuses unknown
  keys; stored run records (bundles, the run store, autosave) are read
  through `from_dict`.
- **No schema version change (it stays 4).** Why: files without the
  fields open in 2.6.0, where they had defaults (checked: the 32
  regenerated templates load and validate with 2.6.0's own code); a new
  version would only stop 2.6.0 from opening files saved now.
- **The migration names the retired fields;** nothing else in the product
  does. Why: it must recognise them.
- **`SimulationService` takes `model_base_dir`.** Why: the Vizard request
  carried the folder a model's relative mesh paths are read from; the GUI
  and the command line now pass it directly, so the model analyses read
  the same files as before.
- **The CLI refuses a `--vizard-*` option as an unknown argument** (exit
  status 2). Why: the simplest; no special message keeps the name alive.
- **The network guard's loopback allowance stays.** Why: it was never for
  Vizard alone: the SIL socket (127.0.0.1), Basilisk's import-time request
  sent to a closed local port and local name lookups use it.
- **The temporary-folder kind for Vizard's model files is removed.** A
  folder of that kind an earlier version left behind after a crash is no
  longer cleaned up at start. Why: no trace; such folders are rare and
  small.
- **Records stay as written** (CHANGELOG releases, HISTORY, AUDIT, past
  decisions, the UI overhaul plan and screenshots, audits, SRelD issues of
  past releases); `tests/gui/test_shell_reachability.py` leaves out the
  plan's rows that name the removed program. Why: records describe what
  was true then.
- **SRS-I-08, ICD-08 and security analysis S-05, S-06 and S-11 are
  retired** with a one-line note, not deleted. Why: their numbers stay
  taken, so references elsewhere still resolve.

## The 3D View as a renderer: three.js (2026-11-10)

The owner's request: the 3D View must become a renderer, as close as
possible to a dedicated mission visualizer, and later also show a run
live. This entry supersedes "plotly.js, not a new 3D library" of the
2026-11-09 entry below.

- **three.js 0.187.0 (MIT), bundled, not plotly.js:** plotly.js draws
  charts; it has no textures, no lights from a direction, no camera
  inside the scene and no per-frame control of objects, and moving a
  model meant re-sending its vertices every frame. three.js is the
  common permissive WebGL library, runs in the same Qt WebEngine view
  (WebGL 2 with software rendering, checked), and is one 770 KB file.
  Why: the smallest library that does the job; no Qt 3D (its Quick 3D
  part is GPL, and it would be a second rendering stack).
- **One classic script, built by a checked-in script:** a page opened
  from `file://` cannot load ES modules (Chromium's rule for file
  origins), so three.js and its `OrbitControls` are bundled by esbuild
  into one script from a pinned `package-lock.json`
  (`scripts/build_three_bundle.py`, reproducible byte for byte). Why: no
  npm or Node at run time or install time.
- **NASA's images, resized, in the package:** Blue Marble (SVS 2915) for
  the Earth, Deep Star Maps 2020 (SVS 4851) for the sky, 4096 x 2048 and
  2048 x 1024 JPEGs (4.4 MB with three.js), public domain with NASA's
  credit (`scripts/prepare_mission_view_textures.py`,
  `docs/THIRD_PARTY_ASSETS.md`). Why: offline, redistributable, and the
  sources are the reference images of their kind. No Moon texture and no
  night lights: not needed for a first version, and one image fewer to
  clear.
- **The page is static in the package** (`gui/assets/mission_view/`),
  not written to a temporary folder; Python sends the theme's style and
  the scene as data (`MV.setStyle`, `MV.load`). Why: the page's code is
  a reviewable `.js` file, and a theme change restyles without reloading
  textures. The page holds no colour, font or size of its own: they come
  from `theme/mission_view_style.py`.
- **Floating origin:** every frame, positions (kilometres, double
  precision in JavaScript) are taken relative to the camera's focus
  before they reach the GPU's single precision, with a logarithmic depth
  buffer. Why: a 1 m spacecraft 7,000 km from the Earth's centre and the
  Moon at 400,000 km in one view, without jitter or depth fighting.
- **The geometry is computed in Python** (`engine/scene3d.py`: normals
  with a 30 degree crease, the Moon, the ground track, each station's line
  of sight above its own minimum elevation, the altitude), off the GUI
  thread, and tested there. Why: the same numbers in tests and view, and
  the page only draws.
- **Space is black and the depicted colours are the same in both
  themes;** the overlays (time panel, labels) take the theme's raised
  surface and text. Why: they are things, not interface; the overlays are
  interface.
- **Reduced quality, chosen by the page:** when the median of five
  frames takes over 50 ms (under 20 frames a second), the page switches
  to 2k textures, no atmosphere rim, no antialiasing and one pixel per
  screen pixel, and the **Show** menu shows it ticked. Measured at
  1296 x 720 in software rendering: 67 ms full, 40 ms reduced. Why: the
  view stays usable on machines without a graphics card; the user can
  switch it back.
- **Live playback is a later step:** the page's arrays grow and its frame
  logic reads their length, so samples can be appended
  (`MV.append`) without a new design.

- **Software WebGL where no driver can start it:** the web views add
  Chromium's `--enable-unsafe-swiftshader`. The Windows CI machines (and
  some virtual machines and remote desktops) could not create a WebGL
  context at all, so the 3D View drew nothing. With the flag Chromium
  falls back to SwiftShader; "unsafe" concerns untrusted web content,
  and the views load only the app's own files (`webengine_setup`). If
  WebGL still cannot start, the page says so in the view instead of
  failing on every frame. `--disable-domain-blocking-for-3d-apis` too:
  after a lost context Chromium blocked WebGL for the shared `file://`
  origin until the app restarted. A quality switch keeps the renderer
  (a second context failed on software GL).

## Landing page at start-up (2026-11-10)

The owner's request: the app starts on a landing page, not on the last
session's work, and closes cleanly. The owner decided: earlier runs only
with their scenario; Home with nothing open; the window's size, position
and panels kept.

- **An explicit "scenario open" state in the main window** (one flag, one
  method that switches it, `MainWindow._set_scenario_open`), not a window
  without an editor scenario: the editor keeps its blank default inside.
  Why: the smallest change; every view and command keeps a scenario to
  read, so nothing can fail on "no scenario".
- **New Scenario, Open..., a recent file, a template (opened or customized)
  and accepting the crash-recovery prompt open a scenario.** No IDM-CIC or
  CCSDS import creates a scenario: both import into a spacecraft of the
  open one, so they need one open. Why: they are every way a scenario
  reaches the editor.
- **No "Close scenario" command:** once a scenario is open, opening another
  replaces it, as before. Why: not asked for; the landing page is for the
  start.
- **A stored run belongs to the scenario of the same name** (the `name` of
  the scenario recorded with the run, compared exactly after trimming
  spaces). Why: the run store records the scenario as it ran, with its
  name, but not the file's path (the provenance names the file only, and
  only for a run of an unchanged file); adding the path would change the
  run store's format.
- **Consequences of matching by name:** a template opened as shipped (or
  customized, untitled) lists the runs of every scenario with its name,
  its own earlier runs included; two different files with the same name
  share their runs; a run made before a rename stays with the old name.
  Why: the same names the run lists already show; nothing is deleted.
- **New Scenario lists no earlier runs:** a new scenario has none. Why:
  its default name ("new scenario") would otherwise gather every blank
  scenario's runs.
- **The runs made since the scenario was opened stay listed** for as long
  as it is open, even if it is renamed; failed runs and Monte Carlo
  batches (listed for the session only, as before) follow the same rule.
  A run still going when another scenario is opened is kept and saved, but
  listed with its own scenario. Why: "runs made in the current session
  stay listed"; switching scenario shows that scenario's runs.
- **The empty state replaces the area's header too** (its commands are
  disabled anyway), with New Scenario as the primary action, Open... and
  Go to Home. Why: the design rules' "every empty state has its primary
  action"; a header of disabled buttons says nothing.
- **Disabled while nothing is open:** Save, Save As, Change History, Undo
  and Redo, Run and the run modes, Live plot, Vizard Configuration, Open
  Monte Carlo Results, Clear Time Cursor, 3D Model, Export Orbits as CCSDS,
  the analyses' and Flight Software's page commands, Explain. Launch
  Vizard, Check a CCSDS File, Check Reference Data, the panels, the
  theme, Settings and Help stay. Why: the first list works on the
  scenario or shows its pages; the second does not.
- **The command palette** lists disabled commands greyed, as before, and
  leaves out the scenario's pages, the run views' tabs and the series
  while nothing is open. Why: they would lead to an empty state.
- **Problems are empty while nothing is open** (the blank default's
  problems are not the user's), and an open scenario's problems only
  count (G8). Why: nothing open has nothing to fix.

## The 3D view, and no Vizard download (2026-11-09)

- **Our own 3D view, not another program:** what the user sees must not
  depend on a third party's build or its telemetry. A view drawn by the
  app itself is covered by the guard, the interceptor and the audit.
- **plotly.js, not a new 3D library:** it is already installed and
  offline, draws WebGL meshes, and the 3D model editor uses it; no new
  dependency (CLAUDE.md).
- **Playback in the page:** each frame is computed in JavaScript from
  arrays sent once, so playback costs the GUI thread nothing.
- **Follow centred on the spacecraft:** WebGL's single precision cannot
  show metres 7,000 km from the origin.
- **Approximate Earth rotation and Sun:** standard closed-form formulas,
  good to a fraction of a degree, are enough to see; the run's own
  numbers stay in the plots and exports.
- **A Results tab, not a dock:** it is a view of the last run, like the
  plots; the time cursor joins them.
- **No download and no search for Vizard:** a program the app starts by
  itself must be one the user chose. Removing the download removes the
  only network use the app made for a third-party program.

## Network use, offline mode and the installers' packages (2026-11-09)

- **Enforce, then observe:** a gateway and a guard inside the tool, and
  an audit from outside it (strace in CI); a colleague can repeat the
  second with their own firewall, without trusting the first.
- **The guard is an audit hook, not a monkeypatch:** PEP 578 hooks see
  every socket call of any Python code, Basilisk's and plugins' too, and
  cannot be removed by later code; a patched `socket` could be bypassed.
- **Refuse rather than log only:** a network use outside a download is a
  defect, so it fails where it happens and is logged; a log alone would
  be read after the fact.
- **Offline is a setting, lockable by a file:** **Settings > Network**
  for a user; a machine-wide file, or an environment variable, for an
  administrator, which the user cannot override (no admin rights needed
  to read it; an unreadable file counts as offline).
- **A section of Settings, not a toolbar switch:** offline is set once
  per computer or per user, not toggled during work.
- **Local loopback stays open:** software-in-the-loop runs and Vizard's
  stream use 127.0.0.1; listening on any other address is refused.
- **Hashes in their own file:** `constraints.txt` stays the readable pin
  list CI installs editable with; hash-checking mode would refuse an
  editable install. The hashed file is generated, never edited, and a
  test fails when the two differ.
- **Every file PyPI publishes for Python 3.14, not one per platform:** a
  Linux on ARM user of `install.sh` gets the same check, and pip still
  picks the right file.
- **No source builds in the installers** (`--only-binary=:all:`): every
  pin has a wheel for Linux x86_64 and Windows x64 (the script checks),
  so a package's build script never runs on the build machine.
- **A Basilisk wheel the user supplies is not hash-checked:** it is their
  own build; its dependencies keep the plain pins.
- **CycloneDX for the bill of materials:** an open standard (ECMA-424)
  most scanners read; the file installed and its SHA-256 come from pip's
  own installation report, not from a second resolution.

## The definition of done (2026-11-03)

- **A bundle made elsewhere, reproduced in CI:** a small Linux bundle is
  test data, so every CI platform reproduces a result it did not make;
  regenerating it after a Basilisk requalification is a stated step.
- **The timing is a person's:** "under a minute, with an engineer who did
  not build it" cannot be automated honestly; the walkthrough and a form
  for the times are in `docs/definition-of-done.md`.

## Open data and the Python API (2026-11-03)

- **A thin API over the engine:** each function calls what the app and
  the command line call, so a script's number is the app's; the objects
  returned are the engine's own, not copies that could drift.
- **A version, not a promise of forever:** `API_VERSION` names the
  contract; a breaking change raises it and is in the changelog.
- **The guide's examples are the tests:** the test runs each example as
  written, so the reference cannot drift from the code.
- **Compare saved runs, not CSV folders:** the run store keeps each
  series with its units and the scenario as run; the CSV folders' headers
  do not say where a column name ends and its unit begins. `run --save`
  puts a command-line run in the same store as the app's.
- **A download is a command, never automatic:** `spaceweather-download`
  is the user's explicit request, as the app's consent prompt is.
## Chained inputs (2026-11-03)

- **The same function shows and computes:** the End of Life page's list
  comes from `lifetime.start_state`, which the estimate now uses, and the
  Budget page's from `run_contributors`, which the budget uses; a value
  shown cannot differ from the value used.
- **A caution, not a lock:** a run of an earlier version of the scenario
  is still a run; the page names what changed and lets the engineer
  decide to run again.
- **Only the propellant is edited:** the starting state belongs to the
  run (or to the scenario's orbit, chosen with **Start of scenario**); the
  propellant left is the value most often questioned, and an edited one
  is recorded as such in the calculation. The budget's contributors were
  already editable ("from last run" or a value).
- **No separate workflow page:** the chain is shown where the next step
  is taken (End of Life, Budget), the run's provenance shows the scenario,
  and Reports > Exports what was written from it; a page repeating them
  would add a place to look without adding a fact.

## Imported values (2026-11-03)

- **Kept in the scenario, not looked up:** the record keeps the values
  as read, so a later edit is told from the file, and the file's SHA-256,
  so a newer file is told from the one read. Neither needs the file to be
  there; without it the check says so.
- **A warning, not a refusal:** the scenario's values are what the user
  chose to run; a newer file may be meant or not. The warning says which
  file and how to take it, and the run records the state either way.
- **Absolute paths:** an import's file is wherever it was read from,
  rarely beside the scenario; a colleague without it sees "missing", the
  honest state. Meshes keep their paths as they were (relative ones
  stay relative).
- **CCSDS orbits and mass properties first:** these are the values the
  tool reads from another tool's file. TLE lines typed or pasted are in
  the scenario itself; catalog presets have their own record (Phase 5b);
  data files are hashed by every run (Phase 2).
## Every value with its unit (2026-11-03)

- **The control law over the header's comment:** `mrpFeedback.h` gives K
  as rad/s and Ki and the integral limit as N·m, which its own control
  law (`mrpFeedback.rst`) does not bear out. The editor shows the law's
  units and the models page gives both, with the derivation. Basilisk
  is not changed.
- **The header's spelling for SIL signals:** the residuals' units are
  read from the vendored payload headers as written ("Nm", "r/s"), not
  respelt: they are Basilisk's statement, and a guessed respelling could
  be wrong. A field without one shows "-".
- **Dimensionless fields stay bare, named in a test:** efficiencies,
  coefficients, fractions, MRPs, directions, counts and seeds show no
  suffix; the test lists each with its reason, so a new field without a
  unit fails until it has one or a reason.
- **The plots' units, not the exports':** the preference changes what
  the plots and the comparison show; the CSV exports stay SI, as
  recorded, so a file handed on never depends on a viewer's setting.
- **TDB named on the axis, not converted:** the elapsed time is the
  simulation's clock; the axis says so. Converting it to UTC would move
  every sample by milliseconds and change what the exports' `time_s`
  means.
## Plugins (2026-11-03)

- **Entry points, not a plugin folder:** an installed distribution's
  entry point (`spacemissionstudio.models`) has a name, a distribution
  and a version a run can record, and needs no path setting; a folder of
  scripts would have none of them.
- **Only the choices with a hook:** a plugin may add models to the link's
  atmospheric loss and the arrays' degradation (each a function the
  engine calls) and margin policies (values only). Sensors, actuators,
  flight-software modes, atmosphere and shadow models are wired into
  Basilisk and need the tool's code; offering them to plugins would mean
  a second, untested way of building a simulation.
- **Everything under the plugin's name:** its parameters are the area
  `<plugin>.*` and its rules `<plugin>.<rule>`, so a plugin cannot change
  or shadow a built-in value or rule, and every record says whose a value
  is. A name that is a built-in area is refused.
- **A failing plugin is left out, not fatal:** what it added is taken
  back and the reason shown, so a broken package never stops the tool or
  leaves half a model in a choice.
- **No sandbox:** a plugin is Python code installed by the user, with
  the user's rights, as any package is, and the guide says so. Loading
  can be turned off with `SPACEMISSIONSTUDIO_PLUGINS=0`.
- **The docs' example is the test's plugin:** the test runs the code of
  `docs/user-manual/plugins.md` as it is, and checks the command's
  output the page shows, so the page cannot drift from the code.

## The History view and labelled Undo (2026-11-02)

- **A dialog, from a command:** the default screens stay as they are
  ("keep the default UI uncluttered"); the history is one command away,
  in the Scenario area and the palette.
- **Read only:** the file is a record, only ever appended to by saves;
  the view and `history` never write it. Going back to an earlier value
  is Undo's (this session) or an edit's (it is then recorded too).
- **A spacecraft's filter keeps the scenario's own lines:** its creation
  and a replaced file belong to every spacecraft's story; scenario-wide
  values (the duration) do not, and are found by the field filter.
- **One description for both:** Undo's label and the history name a
  change from the same comparison (`history.changes`), leaving out the
  value marks and presets, so what the label says is what changes.

## Solar-array degradation (2026-11-02)

- **Two models, by the user's choice:** a yearly rate, simple and
  checkable against flight data, and the displacement-damage-dose fit,
  physically based for triple-junction cells. Both are NASA or NRL
  sources read for this (NTRS), each number cited with its page.
- **No SMAD-style table of rates by cell type:** none was found in a
  document that could be read here, so none is quoted. The yearly rate's
  default is one documented case (ISS P6, expected), and the page lists
  the flight data a project can choose its own from.
- **The dose has no default:** it depends on the orbit and the cover
  glass, and SpaceMissionStudio has no radiation-belt model; a made-up
  dose would be a made-up result. The run is refused without one, naming
  the parameter and SPENVIS.
- **Base-10 logarithm:** the paper writes "log"; its figures only fit
  base 10. The page and the model say this is an inference, with the
  test that checks it.
- **Every panel set each step, before the panels read it:** Basilisk's
  `simpleSolarPanel` reads its efficiency every step, so a small module
  sets it; the framework is unchanged. A long run passes the time already
  flown to each segment.
- **The one-off factors only with a model:** "none" stays exactly what a
  run did before.

## The gases' attenuation of the link, ITU-R P.676-13 (2026-11-02)

- **ITU-R P.676, Annex 2's instantaneous methods:** the user chose
  P.676 for the link losses. Annex 2 gives the slant path from the
  station's surface conditions in closed form; Annex 1's ray tracing
  needs a profile of the atmosphere that a project rarely has.
- **Water vapour by method 1 (Sec. 2.1), not 2:** method 2 needs the
  integrated water-vapour content, and Part 2 for its coefficients;
  method 1 needs only the surface density, the same input as oxygen.
  Part 2 is therefore not fetched: nothing unused is downloaded.
- **Part 1 fetched at installation, by the user's choice:** the ITU's
  file is not committed. The installers and CI download it from the ITU
  and check it against its size and SHA-256 written in the code, as
  Basilisk's support data; runs only read it. The 79 lines of Annex 1's
  Tables 1 and 2 are physical measurements, in the code with their
  citation, and no other part of the Recommendation is.
- **One set of surface conditions for every station:** the parameters
  are a project's, like the other link rules. Their defaults are the
  Recommendation's own "Standard" atmosphere (P.835's mean annual global
  reference), named as such.
- **Outside the method's range, its edge and a warning:** below 5 deg the
  loss at 5 deg (optimistic, warned); below 1 GHz the loss at 1 GHz
  (pessimistic by hundredths of a dB, warned); above 350 GHz refused.
  Extending the method would invent numbers it does not give.
- **The geometric elevation, from the geodetic horizon:** the same one
  the run records, so the live gate and the post-run margin agree; the
  apparent elevation needs a refraction model the run does not have, and
  differs by under 0.2 deg above 5 deg. The page says so.
- **The default is `none`:** every run, budget and export reads as
  before; the new parameters appear in records as parameters do.

## The change history's author (2026-11-02)

- **A plain file, not the app's settings store:** the command line saves
  scenarios too and must record the same name; Qt's INI encoding (quoted
  commas, escaped non-ASCII) would need Qt to read back. A one-line UTF-8
  file reads the same everywhere.
- **Kept when editing finishes:** no Save button for one field; the note
  says what saves will record.

## The change history (2026-11-02)

- **Found by comparing, not by listening:** a save compares the file on
  disk with what it writes. Every way of changing a scenario (a form,
  the JSON view, a command, a generator) is recorded the same, and none
  can forget to report itself.
- **One line per value, JSON Lines, only appended to:** a history is
  never rewritten, so it can be trusted, and a damaged line loses only
  itself.
- **The marks are not values:** an override's line carries the mark's
  reason; the marks and preset records are already the record of those
  values.
- **The save before the history:** a history that cannot be written must
  not lose the user's work; it is reported.
- **The user name until Settings has one:** Section 10's answer, the
  operating-system user name as the default.

## The tabular atmosphere (2026-11-02)

- **Basilisk's own tables:** the user had no table and no reference
  result. Basilisk ships three Earth profiles with recorded sources and
  conditions, read by its own reader; they are the choices, and nothing
  else is made up.
- **In the scenario, as the other atmospheres:** the atmosphere was
  already the scenario's choice (`atmosphere_model`); the table is a
  field beside it, written only when used.
- **A lifetime uses the same table:** otherwise a tabular scenario's
  lifetime would silently use NRLMSISE-00. Its warning says what the
  profile leaves out (the solar cycle; all drag above its top).
- **Above the top, zero and a warning:** the table says nothing there;
  extrapolating would invent a density.

## Shadowing bodies (2026-11-02)

- **One eclipse module per body, combined here:** Basilisk's module with
  several bodies takes only the nearest one's shadow, so it cannot give a
  lunar eclipse of an Earth orbiter. The framework stays as it is; a
  module of SpaceMissionStudio's multiplies the sunlight each body's
  module leaves.
- **The product:** two bodies shading at once are rare (an Earth orbiter
  in the penumbra of both); the product treats the shadows as
  independent and is exact whenever only one body shades. The page says
  so.
- **The default stays the central body:** every run reads as before; the
  other model costs a module per body and per spacecraft.
- **The re-entry criterion and debris rules stay parameters:** both
  altitudes and both disposal rules are named parameters with their own
  criteria; a choice of model would select nothing a project file cannot
  already set.

## Margin policies (2026-11-02)

- **A policy sets parameters, it does not replace them:** each margin
  stays one named parameter with one source; the policy is a set of
  values for them. A project's own value replaces the policy's, so the
  plan's "user" profile is the project file itself, not a third model.
- **Only the differences the repository records:** the summary table's
  10 % residual and 20 % uncertainty, already in the budget's note. No
  other value of the table is written here; the policy says so.
- **The default sets nothing:** with AD10's equations no record, note or
  trace changes, and a record shows `set_by_models` only when a policy
  set a value.

## Selectable models (2026-11-01)

- **A choice is a parameter:** one way to set it (the project file), one
  list of what is in effect (`assumptions`, the Assumptions page), one
  record of what changed (`configuration`). A model registry of its own
  would have needed all three again.
- **The model is declared apart from the parameter:** the parameter says
  which; the model says what it does, on what, assuming what, from which
  reference, checked by which tests. A test fails when a model's evidence
  names a test that does not exist.
- **The default is the earlier behaviour:** no batch, run or export
  changes until a project chooses.
- **A batch keeps the statistic it was run with,** as a run is read with
  its own configuration: a batch opened later reads the same, whatever
  the project file says by then. Re-running the batch is the way to apply
  another; the run table's CSV has every run's offsets for any other
  statistic.
- **The command line's spread lines stay as they were:** the statistic is
  a line of its own after them, so the golden baseline, which records
  them, is unchanged.

## Presets: one record per spacecraft (2026-11-01)

The user's choice, of two offered: one record per spacecraft rather than
a mark on each key value.

- **The values kept, not looked up again:** comparing with the preset as
  the code builds it today would make a scenario look edited after a
  preset's numbers change in a later version. The record keeps the
  numbers the spacecraft was given, as the form added them (rounded to
  its fields), so "as the preset gave it" means exactly that.
- **Numbers only:** a preset's text and choices (an attitude mode) are
  part of the spacecraft and seen in its form; the record is about the
  values an engineer would have had to invent.
- **The orbit left out:** a preset's orbit is a placeholder that the
  engineer replaces at once.

## Computed and overridden values in Explain and Results (2026-11-01)

- **Changed values listed, computed ones counted:** a Walker
  constellation marks hundreds of computed values; listing each would
  bury the one an engineer replaced. A value still as computed is
  counted; a changed one gets its line.
- **The provenance line names them only when there are some:** the
  default line is as before.

## What a changed computed value changes (2026-11-01)

- **Analytic, not simulated:** the note updates as the field is typed;
  a run per keystroke is out of the question, and the first-order J2
  formula is the one that computed the Sun-synchronous value, so it is
  the right measure of what departing from it does.
- **One rule for "Sun-synchronous":** Explain's `explain.sso_tolerance_deg`,
  so the note never says "not Sun-synchronous" for an orbit Explain still
  labels SSO.
- **A line of its own:** the status line stays as it was; the
  consequence goes under it, and only while the value differs.

## Computed and overridden values from the generators (2026-11-01)

- **Only what was computed:** a Walker satellite's semi-major axis,
  RAAN and anomaly are the generator's; its inclination, eccentricity and
  argument of periapsis are the values typed, unless J2 turns them into
  osculating ones. Marking typed values as computed would say the tool
  chose them.
- **Presets are left for a decision:** a preset is a starting point
  spread over dozens of fields; one mark per field would make the marks
  unreadable. Recording "made from preset X" once per spacecraft, or
  marking only the values a preset is known for (mass, drag area), are
  the options.

## Computed and overridden values in the editor (2026-11-01)

- **A note under the field, only when it has a mark:** a field without
  one looks as before, so the default form is unchanged.
- **The reason is asked for when the engineer chooses to give one:** an
  edit stays an edit; asking at every keystroke would interrupt typing,
  and refusing the edit would hide what the field is for.
- **A mark goes with what it marked:** removing a spacecraft, or giving
  its orbit as a Cartesian state or a TLE, leaves no mark pointing at
  nothing; the scenario stays valid.
- **Orbit buttons first:** they are the one place the editor writes a
  computed value into a field the engineer then edits. The wizard,
  generator and presets come next.

## Computed and overridden values (2026-11-01)

- **Marks beside the values, not in them:** a value stays a plain number
  in its field, so every reader of the file, the engine and every test
  see the same scenario. The marks are a list of their own, keyed by a
  path, and a scenario without them is byte-for-byte what it was.
- **"Edited" is a status, not an error:** the plan marks a computed value
  "until edited". An edit is the engineer's choice; refusing it would
  hide the field's purpose. An override is the one that needs a reason,
  because it says the computed value was seen and replaced.
- **Exact comparison for "computed":** the field holds the number the
  tool wrote, and JSON keeps a float exactly, so any tolerance would only
  hide an edit.
- **No version bump:** like `config_file`, the field is written only when
  used, so files without marks still open in older versions. A version
  bump would have made every file unreadable to them.
- **No cap on the number of marks:** the 20 MB file limit bounds them.

## The scenario file's limits, with their rules (2026-10-31)

- **Only the limits that are choices get a rule:** a cap such as 3660
  days or 1000 spacecraft is a choice someone made, so its reason is
  worth stating. A check that a mass is positive or an eccentricity below
  1 states its rule in its message; 330 hand-written rule entries saying
  "a mass must be positive" would add text, not transparency.
- **An error stays an error:** a limit is not overridable. Its rule says
  so, and that the limit is a constant of the code, not a parameter.
  Making such a limit a parameter would let a project file accept what
  the run cannot do (the 100-day single run) or what no real scenario
  needs.
- **The rule rides on the exception:** `ScenarioValidationError` keeps
  its message as before and adds `finding`, so every caller that shows
  `str(exc)` is unchanged.

## The run's warnings, with their rules (2026-10-31)

- **A finished run's warning is not overridden:** it says how to read the
  results (a re-entry, a drift, the forecast space weather read), so its
  override says that, not "run it as it is".
- **A saved run keeps its rules beside the text:** `run.json`'s
  `warning_rules` is a list parallel to `warnings`. The text stays where
  every version reads it, so the format version does not change; an
  unknown rule reads back as plain text rather than failing the load.
- **The tooltip, not a new view:** Results' warning note keeps its text
  and shows the rules on hover, keeping the default view uncluttered.
- **Notes stay notes:** the budget's notes and Explain's gravity fidelity
  notes describe a model, not a finding against a limit; a 3D model's and
  a SIL report's warnings are shown in their own views and are left for
  a later step.

## Structured warnings in the app (2026-10-31)

- **On hover, not in a column:** the brief keeps the default UI
  uncluttered, and a warning's rule is detail asked for once it is
  noticed. A tooltip (and an accessible description, which a screen
  reader reads) shows it without a new column or button; the message,
  the panel's columns and `Ctrl+C`'s rows are as before.

## Structured warnings (2026-10-31)

The transparency plan's Phase 5a: a warning names its rule, what it
found against its limit, why it matters, how to fix it and how to
override it.

- **A warning is still its text:** `Finding` subclasses `str`, so the
  checks' callers, the run's record (`run_warnings`), the exports, the
  GUI and every test see the same strings. The structure rides along for
  the views that show it, and nothing that stored or compared a warning
  had to change.
- **The rules live in one table, `engine.findings.RULES`:** a check names
  its rule by id; the text of the rule, the reason, the fix and the
  override are written once. A test fails if a rule has no check or a
  check's warning has no rule.
- **"Override" means what it can mean today:** a pre-run warning never
  blocks a run, so its override is to run as it is, or to change the
  limit's parameter. Overriding a computed value with a justification is
  Phase 5b.
- **In steps:** the pre-run checks and the command line first; the
  Problems panel and Explain next; then the run's own warnings and the
  schema's limits.

## Explain's rules; the mission sequence's settings (2026-10-31)

- **A value that cannot change a result is not a parameter:** Lambert's
  convergence tolerance looked like a rule, but in the app's use it
  decides nothing (the solver sees the same state each tick). Making it
  a parameter would offer a choice with no effect, so the model page says
  why it is not one and a test shows it, as for the landmark camera's
  focal length.
- **Caps are not parameters:** the loop and event-search limits stop a
  runaway sequence with an error; they set no result of a sequence that
  ends.
- **Explain's checks of the scenario take it optionally:** the Home
  page's template cards label orbits without a project configuration;
  they get the defaults.

## The pre-run checks' rules (2026-10-31)

- **The rules first, the structure next:** this step names each check's
  threshold as a parameter. Phase 5a's structured warnings (rule id, the
  rule, the actual value, the limit, how to fix) build on these names, in
  a step of their own, since they change what every consumer of a
  warning receives.
- **A cosine, not an angle, for the sun sensor:** the check compares a
  cosine with 0.5; an angle of 60 deg would be compared as
  cos(60 deg) = 0.5000000000000001, a different rule at the edge. The
  parameter is the cosine the code uses, and says it is 60 deg.
- **The defaults' wording kept:** a warning that read "in the first week"
  still does at the default; it says the configured length when the
  parameter is set.

## Flight software and navigation rules (2026-10-31)

- **One page for two areas:** `flight_software.*` and `navigation.*`
  share `docs/models/flight-software-and-navigation.md`, as `link.*` and
  `data_handling.*` share theirs: the page is about the onboard chain.
- **The trigger is tested on Basilisk's module:** the case drives
  `thrFiringSchmitt` with four requests and compares the on-times it
  commands, so the test shows each value changes what the thrusters do,
  not only that it was passed.
- **The filter settings are tested on the run's build:** running
  `relativeODuKF` long enough to tell 0.02 from 0.1 would take a full
  optical navigation run per case; the case checks that the run builds
  the filter with the scenario's values. The filter itself is Basilisk's.
- **What cancels is not a parameter:** the focal length cannot change a
  result, so a parameter for it would suggest a choice that has no
  effect. A test shows it cancels.

## The rest of the ROE guidance's rules (2026-10-31)

- **The physics stays in the code:** `1.5 n da` (how fast the mean
  longitude moves for a relative semi-major axis) and `3/4 n da_dot t^2`
  (its drift under a steady decay) are equations, not choices; only the
  thresholds compared with them are parameters.
- **`drag_is_significant` keeps its signature:** `fraction` is optional
  and defaults to the parameter's default, so the ROE math can be called
  without a configuration (its own tests do); the controller passes the
  scenario's value.

## The ROE guidance's rules, as parameters (2026-10-31)

- **Nine now, the rest next:** the guidance's named constants become
  parameters first. The values written inline in the drift logic (its
  slow end, the 1.25 and 1.5 bands, the 60 s earliest look-again, the
  re-plan shift) and `roe.drag_is_significant`'s half tolerance are
  listed on the model page and follow in a second step, so each step
  stays small and its tests specific.
- **Not parameters:** the burn scheduling margins (half a burn part plus
  1 s ahead, 1.5 burn parts apart), the 72-bin eclipse record and
  `follower_orbit`'s six iterations. They keep burns apart and set
  numerical resolution; they are not tuning a project would change.
- **"No derivation recorded":** the code's comments say what each rule
  does, not why its value; the parameters say so rather than give a
  reason no one wrote down.

## The mean elements' trace (2026-10-30)

- **One trace for the series, not one per sample:** every sample goes
  through the same map with the same radius and J2. What differs between
  samples is only the band each falls in, so the trace counts them.
- **The bands are constants, not parameters:** they handle the map's
  singularity (Environment and data, "Fixed rules"). The trace names
  them as `constant:`.
- **Reached from the figure that uses it:** the semi-major axis change
  carries it as a related trace (`Figure.related`), so the Calculation
  panel opens it from there.

## The power and data traces (2026-10-30)

- **Read, not recomputed:** the power is Basilisk's (`simpleBattery`),
  and the data totals are the ledger's. Their traces name the series and
  the sample, not an equation SpaceMissionStudio does not apply. Only the
  state of charge is SpaceMissionStudio's arithmetic, and its trace says
  so.
- **One place for the sample and the formula:** the dashboard's
  last-sample-at-or-before-the-cursor and the state of charge moved to
  `engine.power_state`. The dashboard and the trace use them, so the trace
  states what the card shows.
- **Not yet:** the scenario explanation's pre-run data estimates (data
  per day, memory fill time, data per pass). They are arithmetic on the
  settings and show as text in Scenario › Overview, where the Calculation
  panel does not reach yet.

## The events' traces (2026-10-30)

- **Made when asked, not kept on each event:** a run can have 10,000
  events, and the Timeline must stay instant. `events.trace_of` reads the
  run again for the one event asked about. `Event` is unchanged, so the
  regression baseline and `events.csv` (byte for byte against 1.1.0) are
  too.
- **One set of rules:** the burn and mode rules became tables
  (`_BURN_SOURCES`, `_MODE_SOURCES`) and each rule a function, used by
  extraction and by the trace alike, so the trace cannot state a
  different rule. A test finds every event again from its trace.
- **The samples either side are shown:** they bound when the event began
  and ended, which is what an engineer asks of an event from a run
  recorded every minute.
- **No `--explain` for events:** a long run has thousands; `events.csv`
  lists them, and the rule of each kind is on the models page.

## The provenance view (2026-10-30)

- **A window from the popover, not a bigger popover:** the popover stays
  the quick look the overview and History had; the full record (hundreds
  of rows with the frames and seeds) needs room, a filter and Copy.
- **A tree in fixed groups, with "Other" for the rest:** the groups follow
  what an engineer looks for (software, run, seeds, scenario, data files,
  time scales, frames, configuration). A key no group names, from a newer
  record, still shows, under Other, so nothing recorded is hidden.
- **Numbers in full (`repr`):** a provenance value is evidence, so a GM
  or a tolerance is shown as recorded, not rounded.
- **The record as `provenance.json` holds it**, the run's warnings
  included, so the window and the file agree.

## The run summary's traces (2026-10-30)

- **The card itself opens the calculation, not a button on it:** eleven
  cards with a button each would crowd the overview. A card with a trace
  takes the focus, shows a hand pointer and the tooltip "Show how this
  was computed", and answers Enter and Space as well as a click.
- **`run --explain`, not a new command:** no command reads a run's CSV
  files back, and the figures are worked out at the end of the run, so
  `run` prints them when asked. Its default output is unchanged.
- **The central body's GM says where it came from:**
  `orbit_number.central_body_mu_and_source` gives the value and its
  source together, so the trace cannot name a different GM from the one
  used.
- **Inputs that are whole series are named in the sources of the values
  read from them** (the first window's mean, the median), not given a
  value of their own: a series has no single value to show.

## The Calculation panel (2026-10-30)

- **Named "Calculation", not "Explain":** Explain (Scenario > Overview)
  already says what a scenario does. The plan's "Explain drawer" says how
  a number was computed, so its button is **Show calculation** and its
  panel **Calculation**.
- **A dock beside the Inspector, hidden until asked for:** the default
  window stays as it was; the panel opens from the number, and the
  layout's reset hides it again, as it does Problems.
- **Two lines per input, not a table:** in a side panel the shared table
  cut off the sources, the point of the panel. Each input gives its value
  and meaning, with its source under it.
- **One explanation per page:** a page sends the trace asked about first,
  with every other trace of the same calculation, so **Open** follows an
  input to its own calculation without asking the page again.
- **The Dashboard's link at the time cursor:** the panel's range and
  pointing error are the run's at the cursor (`last run:`), so it
  explains the figures on screen.
- **The window layout's version goes from 4 to 5:** a new dock; a layout
  saved before would leave it out of place.

## The link budget's traces (2026-10-30)

- **A command, not only traces:** a run's link margin is a time series,
  and a design review asks for one budget. `link-budget` gives it at the
  case that sizes the link: the longest range of a pass, at the station's
  minimum elevation. Any other range can be given.
- **The traces are built beside the breakdown, not inside it:** the
  breakdown is evaluated every step of a run, and the traces would cost
  there for nothing. `link_budget_traces` takes its values from the same
  breakdown, so the two cannot differ.
- **Boltzmann's constant stays -228.6 dBW/K/Hz,** as link budgets write it
  (10 log10 of 1.380649e-23 is -228.599). The trace says so.

## The lifetime's traces (2026-10-30)

- **A seventh source kind, `option:`**: the lifetime's drag coefficient,
  solar-activity percentile, look-ahead and deorbit perigee are the
  analysis's own settings, from the command line or the End of Life page,
  each with a parameter as its default. They are neither the scenario's
  nor a parameter's when given.
- **A decay that reaches the ground within a step re-enters there:** the
  step stays at least an orbit, which the orbit-averaged rates need. The
  re-entry time is then known to within that step, which the warning
  gives. Shorter steps near the end would change every lifetime's last
  digits; this changes only the cases that raised.

## The budget's calculation traces (2026-10-30)

The transparency plan's Phase 4a and 4c, first model.

- **The calculation writes its own trace, from the values it computes
  with:** a trace rebuilt afterwards could describe a different
  calculation than the one that ran. `tests/test_trace.py` then
  recomputes each number from its trace's inputs alone, so a trace that
  drifts from the code fails.
- **One trace type for every model** (`engine.trace`): quantity, equation,
  reference, inputs, intermediates and notes, each input with a unit and a
  source of one of six kinds (`scenario:`, `parameter:`, `constant:`,
  `last run:`, `computed:`, `trace:`). The lifetime, link and run-summary
  traces will use the same type, and the GUI's Explain drawer (4b) shows
  any of them.
- **A solver's result is traced to its inputs, not its steps:** the
  disposal burn (a bisection on the lifetime) and the drag make-up name
  the model and every input; the lifetime's own trace will show inside.
- **The baseline records the numbers, not the traces:** the traces
  restate them. They are left out of the regression fingerprint, which
  would otherwise change with every rewording, and checked by their own
  tests.
- **`--explain` is opt-in:** the default table is as it was.

## The orbit controllers' rules, as parameters (2026-10-30)

The transparency plan's Phase 3a, the first area the coverage check
found missing.

- **The controllers' internal rules are a project's, the targets already
  were:** a scenario sets each controller's deadband, thrust and
  propellant. Its decisions inside (when a firing may start, when a burn
  is not worth firing, when phasing gives up, how far a GEO burn
  reaches) are tuning a project may change for its own bus, so they are
  parameters.
- **Two values say "no derivation recorded":** the firing gate's 2.5 and
  the GEO inclination target's quarter. Their parameters say so rather
  than give a reason no one wrote down.
- **J22 and lambda22 are constants, taken from the field:** they describe
  the Earth. The run's gravity is GGM03S, so the controller plans with
  GGM03S's own degree-2 order-2 term. The old values had no recorded
  source and differ from the field's by 2.7e-5 and 0.0009 deg.
- **The ROE guidance is its own area,** next: it has about 15 rules of
  its own and its own model page to write.

## The rest of the one set of constants (2026-10-30)

The first step of the transparency plan's Phase 4: the audit's Section 4
checked against the registry before the traces are built on it.

- **The Earth's rotation is SPICE's, not astroConstants.h's:** the
  decision was Basilisk's constants because the simulation uses them. For
  the Earth's rotation the simulation uses SPICE (pck00010, or ITRF93
  where installed), and the header's `OMEGA_EARTH` is a rounded sidereal
  day, 1.2e-6 slow. That is 4.3e-4 deg a day, which GEO station keeping
  (which already had a better value) would fit as drift. The rule behind
  the decision, agreeing with the simulation, picks pck00010's rate.
- **Time from `time_system`, not a constant:** TT - UTC is not a constant
  (it was 37 leap seconds only since 2017), and the module that converts
  the scenario's epoch for the run already has ERFA's table.
- **The registry's gaps are listed, not filled in this step:** orbit
  controllers, flight software and navigation, the pre-run checks and the
  mission sequence. Each is an area of its own, a pull request each with
  its model page (`docs/models/README.md`, "Not yet covered"); the checks
  go with Phase 5a's structured warnings, which need their limits named.

## The Assumptions page (2026-10-30)

The transparency plan's Phase 3d.

- **A page of the scenario, not a dialog:** the configuration belongs to
  the scenario that names it, so the page is a node of the editor's tree.
  It shows only when chosen, which keeps the default view as it was.
- **The file is edited, not rewritten:** a project's configuration file
  carries its reasons as comments ("our tanks: 5 % measured"). Writing
  the parameters out anew would lose them, so the page changes one line at
  a time and checks that the file still reads.
- **Values are set below the table, not in it:** the selected
  parameter's details (what it controls, its source, its limits) need the
  room, and a single field with Set makes clear when the file is written.
- **The JSON view stays:** it still edits `config_file`, as before.

## One set of physical constants (2026-10-30)

The transparency plan's Phase 3c; the user's answer to the audit's
Section 10, question 2: one set, every changed number recorded.

- **Basilisk's set:** every simulated orbit uses it, so an estimate and a
  run of the same orbit agree on the Earth they describe. A more recent
  set (IAU 2012's AU, GGM03S's GM) would make the estimates disagree with
  the simulation they estimate, by more than they gain.
- **Constants, not parameters:** a project does not change the Earth. A
  study with another set edits one file, and `tests/test_constants.py`
  then shows where it departs from the simulation's.
- **Left as they are, each for a reason** (`docs/models/constants.md`):
  - the gravity files' own reference values;
  - WGS-84's ellipsoid, for geodetic latitude and height;
  - the mean elements' J2;
  - constants inside Basilisk's modules.
- **Two re-entry altitudes, kept:** they are two criteria, not one value
  twice. The run stops on the simulated altitude (100 km, now a
  parameter); the lifetime ends on the orbit-averaged perigee (120 km).
  Unifying them would make one of the two wrong.
- **The baseline is not rewritten:** the largest change in a recorded
  run output is 1.1e-10 of its scale, far below the baseline's 1e-6.
  `docs/changes.md` records it with its digits.

## The environment's data rules, as parameters (2026-10-30)

The transparency plan's Phase 3a, last area.

- **Two of the environment's rules are a project's:** MSFC's 132-month
  repeat, which AD10 sets but a project with its own solar-cycle
  assumption may change, and the TLE age warning.
- **The rest are the data's or the mathematics':**
  - **The Earth-orientation accuracy window:** NAIF states it for its
    predicted file; a project cannot make the prediction better.
  - **The mean-element bands:** the handling of the map's singularities,
    with no physical meaning to tune; they sit inside pure functions used
    by the generators, the lifetime and the runs alike.
  - **WMM's validity:** the model's release rule.
  - **The panel's stale flag:** it covers the whole app, not a scenario.

  Each is documented, with its reason, on the model page.

## The dynamics' integration and run control, as parameters (2026-10-30)

The transparency plan's Phase 3a, fifth area. The dynamics are split in
two: run control here; the environment's data rules next.

- **The tolerances are a project's to choose:** 1e-10 was chosen for long
  steps (audit E3), and a project trading accuracy for speed, or wanting
  more, now sets it. The provenance records the run's own.
- **The re-entry checks' cadence is a parameter, not the trajectory's:**
  the chunks do not change what Basilisk integrates (the same final
  position to the millimetre in every case measured), only how precisely
  the re-entry time is known.
- **Not parameters:**
  - the 100 km re-entry altitude, which Phase 3c reconciles with the
    lifetime's 120 km;
  - the long run's 90-day segments, which only have to fit Basilisk's
    104-day clock;
  - the order of the modules within a step.

## How a run's results are read, as parameters (2026-10-30)

The transparency plan's Phase 3a, fourth area: the run summary, the
events, and the overview's and dashboard's marks.

- **A run is judged by its own values:** each value is read back from the
  run's provenance, not from the configuration open now. A run kept in the
  history and shown a week later, after the project changed its file,
  still reads as it did. The dashboard reads the scenario of the run it
  shows, which carries that run's configuration.
- **The battery limit is a share of the capacity:** a limit in W*h would
  differ for every battery. 0 keeps "Battery empty"; a project with a
  depth-of-discharge limit (Section 7 lists one as missing) sets 0.3 for
  70 %. It marks the result only: Basilisk's battery still runs to 0.
  Without the scenario as run (no capacity), only an empty battery is
  marked.
- **Not parameters:**
  - an eclipse is any sunlight below 1 (a definition, not a choice);
  - a pass is `has_access` on (the station's elevation mask, a scenario
    input, decides it);
  - unit conversions.

## The link's and data handling's rules as parameters (2026-10-30)

The transparency plan's Phase 3a, third area.

- **A required margin, at 0 dB:** the link closes at a margin of at
  least `link.required_margin_db`. The default keeps today's 0 dB, so no
  number changes; a project that requires 3 dB sets it. The audit asked
  for one (Section 7 and Appendix B: "no required-margin policy").
- **One rule wherever the link is judged:** the simulated downlink, the
  Vizard status, the dashboard and the overview card use the same
  `link_budget.link_closes`, so they cannot disagree. A run shown in the
  overview is judged by the value it was run with, read from its
  provenance, not by the configuration open now.
- **Only the "fixed" pattern's loss is a parameter:** the patch and the
  gain table take their shape from the antenna's own inputs, which are
  the scenario's. The 0.05° grid of the reported beamwidth is numerical
  and stays as it is, documented.
- **Constants stay constants:** c, Boltzmann's constant and Basilisk's
  solar flux are not engineering choices. Phase 3c gathers the physical
  constants; the solar flux and the AU are in Basilisk's C++ modules,
  which this tool does not change.
- **Power has no parameter:** every value of the power model is the
  scenario's (panel, battery, loads) or Basilisk's. Its page documents
  the model instead.
- **GUI starting values of new spacecraft groups wait:** the panel
  efficiency 0.29 and the other values a new group starts with are
  scenario defaults, saved in the file once set; they are the scenario
  defaults' area, not a rule's.

## The lifetime's rules as parameters (2026-10-30)

The transparency plan's Phase 3a, second area.

- **The estimate's defaults are parameters:** the drag coefficient,
  percentile, horizon and deorbit perigee that `lifetime` and the End of
  Life page start from are what a project most often wants as its own.
  The CLI's options default to unset and take them per scenario. The page
  sets its controls to them when they change, and not on every edit,
  which would undo the user's own choices.
- **The input limit stays a limit:** `MAX_HORIZON_YEARS` (100 years) bounds
  what the estimate accepts; it is not an assumption of the model.
- **Two re-entry altitudes, kept for now:** the lifetime's 120 km is a
  parameter; the run's 100 km is not yet. Phase 3c reconciles them, as a
  recorded change of numbers.
- **Choices, not only limits:** a percentile parameter takes only MSFC's
  95, 50 and 5, the only ones a forecast can be resolved at. The budget's
  two percentiles, merged with limits 5 to 95, accepted 60 and failed at
  run time; a value outside the choices is now refused when the file is
  read.
- **A GUI default's test is the page's:** the deorbit perigee acts only on
  the End of Life page, so its case is a test of that page, which the
  registry's guard test names.

## The parameter registry and project configuration (2026-10-30)

The transparency plan's Phase 3a and 3b (`docs/transparency_audit.md` 9.2),
for the first area, the propellant budget; Section 10.1 decided YAML.

- **One declaration per parameter:** `config/parameters.py` declares
  each with its name, default, unit, what it controls, source, rationale
  and limits. The code reads the value in effect (`registry.value`); the
  module constants are gone, so there is no second copy to drift. Earth's
  GM and radius stay constants until Phase 3c chooses one set.
- **Named, never found:** a scenario names its file (`config_file`). A
  configuration file lying in the folder changes nothing unless a
  scenario names it, so no result depends on a file nobody chose.
- **Read where the scenario is loaded, carried with it:** the file is read
  by `load_scenario` and by the GUI editor's `to_scenario()`, both of which
  know the scenario's folder, into `Scenario.configuration`. That field is
  never saved (`init=False`, dropped from `to_dict`), never compared, and
  left out of the scenario's hash. It travels with the scenario object
  into Monte Carlo workers (pickled), long-run segments (copied) and the
  altitude trade's processes; a context variable would not survive a
  Windows `spawn`.
- **The hash and the record:** `config_file` is written only when set,
  so every scenario without one saves, and hashes, exactly as before. When
  set, the scenario's hash covers the name, not the file's values; the run's provenance records the
  file's SHA-256 and each value it changes, with its default. A bundle
  copies the file. Two runs of one scenario with different files share a
  scenario hash and differ in `configuration`.
- **Refused, not ignored:** a file that cannot be read, a name the
  registry does not know, or a value outside a parameter's limits makes
  the scenario invalid, naming the file and the parameter. A relative
  `config_file` in a scenario not saved yet is refused, not read from the
  working folder.
- **The defaults file, commented out:** `config/defaults.yaml` is
  generated from the registry and lists every parameter with its default,
  unit, source and limits, each line commented. A copy changes nothing
  until a line is uncommented, so starting a project file cannot change
  a result by accident.
- **Labels follow the values:** the budget's margin labels and notes ("1%
  of tank", "x4 count") are worked out from the values in effect, so a
  changed margin is never labelled with the default. At the defaults they
  read as before, character for character.
- **A test sets each parameter:** `test_config.py` sets each budget
  parameter and checks that what it controls changes, and fails when a
  parameter is declared without such a case (the plan's 9.4).
- **PyYAML declared:** it already shipped with Basilisk's `bsk[all]`
  (6.0.3 in the installers); it is now a core dependency, as the
  configuration needs it whatever Basilisk pulls in.

## Reproduction bundles (2026-10-29)

The transparency plan's Phase 2h (`docs/transparency_audit.md` 9.2;
definition of done: "reproduce a colleague's result from an exported
file").

- **A run folder, extended:** a bundle is the folder `run --out-dir`
  already writes (results, provenance, scenario as run), with `inputs/` and
  `bundle.json`. Copying the files at once is what makes a folder that
  can travel. `--bundle` is opt-in, as a model's meshes can be large.
- **What is copied:** the files the scenario refers to, and the
  space-weather files the run read, because for the `"bundled"` source they
  depend on the computer (the shipped file or a newer download). The
  installed reference data is not: `de430.bsp` is 114 MB, and its hash in
  `provenance.json` is enough to say whether a computer has the same.
- **The scenario's hash is checked before its paths are changed:** the
  scenario as run is checked against `scenario_sha256`; only then are its
  references pointed at the bundle's copies, and each substitution is
  reported. The copies' SHA-256 are checked against the manifest. So the
  new run is the same scenario on the same file contents, at other paths.
- **Compared as written:** both runs' series are compared from their CSV
  files, 9 significant digits each, column by column, as a fraction of the
  series' largest magnitude (its value columns'; the time column's own:
  2026-11-03, a vector's near-zero component had failed on its noise). The default 1e-6 is the regression
  baseline's general rule, found to hold for well-conditioned outputs
  across computers (3.8e-7 measured). Like that rule, it does not hold for
  a noisy sensor across C++ standard libraries, and the report says when
  the platform differs.
- **A verdict and the reasons:** the exit code is 0 or 5 on the series
  alone, and the report lists the versions, platform, reference-data files
  and event counts that differ, for the reader to judge. A different
  Basilisk version is reported, not refused.

## The effective configuration (2026-10-29)

The transparency plan's Phase 2c (`docs/transparency_audit.md` 9.2; gaps C
(a) and (h), 4.2 "Engine defaults behind open `params`", 5 "Silent
migrations").

- **Noted where the engine reads, not listed beside it:** each open
  `params` dictionary is wrapped at build time in a `RecordedParams` that
  notes the keys read and missing, with the default the reader passed. A
  separate list of the 36 defaults would be a second copy free to drift
  from the code. The note is of what this run read: a key that only one
  mode reads appears only when that mode runs.
- **In place, after validation:** the dictionaries are wrapped in the
  scenario being run, after `validate()`, so only the engine's reads are
  noted. The service does not copy its scenario: the mission engine and
  Monte Carlo share it. Every caller hands the service a scenario of its
  own (the GUI's `to_scenario()`, a loaded file, a segment's copy), so no
  editor holds the dictionaries replaced. A `RecordedParams` is still a
  `dict` with the same items: equal to one, saved and pickled as one.
- **`None` kept, and explained:** a default of `None` means the engine
  sets nothing and the Basilisk module keeps its own value. The record
  says so (`effective_config_note`) rather than leaving the key out. The
  Basilisk value itself is not read back; for the devices it is.
- **Devices read back from Basilisk:** a named wheel or thruster takes its
  values from Basilisk's factory. They are read from the devices the
  factory made, in Basilisk's SI units, not looked up in its source, so
  the record is what the simulation flew.
- **Migrations from the file, beside its hash:** loading an older file
  changes values (a v1 `"celestrak"` source becomes `"bundled"`). The
  changes are worked out from the file's bytes with the file's hash
  (`output_provenance.scenario_file_record`), so they are recorded exactly
  when the file is: by `run`, and by the GUI for a run of an unchanged
  file. `validate` prints them.

## The records of a lifetime, a budget, a batch and a SIL run (2026-10-29)

The transparency plan's Phase 2g (`docs/transparency_audit.md` 9.2, gap 8):
the outputs that are not a run's.

- **A file on request, the printout unchanged:** `lifetime` and `budget`
  print as before, and `--out FILE.json` writes the record. Scripts that
  read the printout keep working, and the record has room for what a
  table cannot hold: the decay curve, the rules, the data files.
- **What the code used, named as in the code:** a record's `model` gives
  the values that are not in the scenario file under their names in the
  code (`REENTRY_ALTITUDE_KM`, `CAM_COUNT_FACTOR`, ...), so a reader can
  find each one. They stay constants for now; the parameter registry
  (Phase 3) is where they become editable.
- **What the decay used, kept on the result:** `EndOfLife` keeps the area,
  drag coefficient and space-weather files it used, and `Budget` the files
  its drag estimates read. Working them out again for the export would be
  a second copy of the rule, free to drift from the first.
- **The baseline leaves the data files out:** they are paths, sizes and
  hashes of this computer's files, as the run provenance's `data_files`
  already were. The area and drag coefficient are numbers of the result
  and are compared.
- **A batch's record is built after the batch:** the nominal run is built
  but not run (`SimulationService.nominal_provenance`, 0.2 s for template
  25), after `executeSimulations`, because the Controller forks its
  workers from this process, and a Basilisk simulation left over before
  that can hang them. It is written by `run_monte_carlo` itself, so the
  CLI and the GUI's child process write the same record.
- **No seeds in a batch's record:** Basilisk's Controller draws each run's
  seeds and writes them to its `run<N>.json`, and those are the ones used
  (`assign_rng_seeds` keeps a seed already set). The nominal run's seeds
  would be seeds no run used, so the record says where the real ones are.
- **The SIL report records its run:** the run flown in SIL is a copy of the
  scenario without its Mission Sequence or Monte Carlo, so the report keeps
  both hashes: the scenario's at the top and the run's under `run`.
- **Not yet in the GUI:** the End of Life page has no export, and the
  Budget page copies its table with the scenario lines. Their exports
  belong to Phase 9a (open data), which will reuse these records.

## The run record (2026-10-29)

The transparency plan's Phase 2a, 2b, 2d and 2f (`docs/transparency_audit.md`
9.2): what a colleague needs to re-run a result.

- **The scenario as run, not only its hash:** `run` writes
  `scenario_as_run.json`, the migrated scenario as the app saves it. Its
  canonical JSON hashes to `scenario_sha256`, so the file and the record
  check each other. The GUI's exports do not write it yet: the
  reproduction bundle (Phase 2h) will cover the GUI.
- **Both hashes:** `scenario_sha256` (the scenario as run, after migration)
  and `scenario_file_sha256` (the bytes given). Two files that differ only
  in layout, or an old file and its migrated form, share the first and not
  the second. The GUI records the file only when the run starts from it
  unchanged; after an edit the file is not what ran, and an empty field is
  more honest than a stale hash.
- **Large files hashed once:** hashing `de430.bsp` took 8.2 s on this
  computer. A file over 32 MB is hashed on first use and its hash kept in
  `~/.cache/SpaceMissionStudio/file_hashes.json`, keyed by path, size and
  modification time, as git's index trusts a file; the record says
  `sha256_cached`. A file changed in place with its size and time kept
  would not be noticed: that is the assumption made.
- **Installed kernels re-hashed:** an Earth orientation or small-body
  kernel was trusted on its install manifest. It is now hashed at run time
  (under 32 MB each, the Eros SPK about 5 MB) and a mismatch is a run
  warning, not an error: the run still uses the file, and says so.
- **Warnings in the record, not in the run record:** `run_warnings` is
  added to the exported `provenance.json` and the Timeline and Output
  sidecars, not to `RunProvenance`: the warnings are what the run found,
  the provenance how it was made. Plot images keep the record without
  them.

## GUI defects of the transparency audit (2026-10-29)

The transparency plan's Phase 1b for the GUI (`docs/transparency_audit.md`
3.4, 3.7, 3.8, 3.9, 3.10, 3.12).

- **3.4, shown not changed:** the inertia scaling of the default gains is
  kept (the unscaled gains diverge for small spacecraft, HISTORY.md); the
  form shows the scaled values and the line above it the derivation. The
  defaults and their scaling moved to `engine.control_gains`, which needs no
  Basilisk, so the GUI computes them as the engine does instead of keeping
  a copy.
- **3.7, no spread rather than a guessed one:** a new dispersion starts
  at the spacecraft's own value with zero width. A percentage would be an
  assumption nobody made; zero width disperses nothing until the user sets
  a spread, and the note says so.
- **3.9, the schema's default wins:** the GUI now takes a new station's
  defaults from `GroundStationConfig`, so the receive gain is 0 dBi in
  both. Changing the schema to 45 dBi instead would change every scenario
  file written without the field; the templates that use a link set their
  own gain (35 dBi or 0 dBi).

## Engine and command-line defects (2026-10-29)

The transparency plan's Phase 1b (`docs/transparency_audit.md` 3.1-3.3,
3.5, 3.6, 3.11, 3.13 and 3.14); the GUI and default defects (3.4, 3.7-3.10,
3.12) follow in their own change.

- **The run keeps its central body and GM** (`central_body`,
  `central_body_mu_m3_s2` in the provenance): the orbit-number axis and the
  mean semi-major axis change take the GM from the run itself, not from a
  constant. A record written before (no GM) falls back to the body its
  inertial frame names, and to Earth's GM when that is Earth or unknown, so
  every Earth run reads as before.
- **Exit status 5 for a check that ran and did not pass** (`fsw-status`,
  `sil --max-error`): they returned 2, which ICD-02 gives a missing
  component or a usage error, so a script could not tell "stale export"
  from "no Basilisk". A new status was chosen over reusing 1 (an input
  error) because the input was fine. `monte-carlo` with a failed run
  returns 3 (a run failed), not 4 (an internal error), and `kernels-status`
  with a kernel missing returns 2 (a missing component), not 1.
- **The predicted Earth orientation note reaches the run's warnings:** it
  was shown in the Explain tab only. No reason was recorded for keeping it
  out of the run (#124 added the filter with the coverage notes), and a
  run that uses predicted values has a larger Earth-fixed error, which the
  user should see with the results.
- **A check that fails says so:** the pre-run and plausibility checks
  dropped an exception without a word, so a check that could not run looked
  passed. It is now one line, `check not run: <name> (<error>)`, and the
  traceback goes to the log; the checks still never raise.
- **A stop epoch counts TDB seconds:** the simulation clock counts TDB
  seconds since the epoch, so the time to a stop epoch is now the TDB time
  between the two, leap seconds included (`time_system.tdb_seconds_between`).
- **A split run's provenance is the whole run's:** the scenario hash of the
  file as given (not of segment 0's copy), every segment's seeds, and the
  real space-weather file, with the whole-span file built from it kept as
  `space_weather_resolved`.

## Regression baseline (2026-10-29)

The transparency plan's Phase 1a (`docs/transparency_audit.md` 9.2).

- **Fingerprints, not whole outputs:** each column of each series is kept
  as its first, last, least, greatest and mean value and 11 evenly spaced
  samples. 1.4 MB for 31 templates, where the full CSVs are hundreds of MB,
  and a change anywhere in a column moves at least its mean.
- **Runs capped at 6 hours of simulated time:** the full templates take
  about 20 minutes one after another; capped, the baseline takes 8 min 57 s
  here, 2 min 54 s on 8 test workers. A Mission Sequence runs in full
  (at most 14.4 h), since its steps set the length.
- **Compared within what two computers disagree on, rule by rule**
  (`tests/golden_capture.py`, "How numbers are compared"). A first
  tolerance of 1e-9 of each quantity's scale held here (two runs gave
  identical fingerprints) but failed on CI: 22 templates on Linux, all 31
  on Windows. CI's two Linux runs agreed with each other byte for byte;
  every difference was traced:
  - last bits amplified by ill-conditioned quantities: the angles of a
    circular orbit (an arccos near 1 gives 0 or 2^-26 = 1.5e-8 rad), the
    eccentricity of a circular orbit (2e-15), a mean semi-major axis
    change (a difference of two means of 7000 km), the relative orbit
    elements made from those angles (0.1 m);
  - angles wrapping at 2*pi (a RAAN of 0 against 6.283185);
  - sensor noise: Basilisk's GaussMarkov draws from
    `std::normal_distribution`, whose algorithm each C++ standard library
    chooses, so Windows (MSVC) and Linux draw different noise from the same
    seed, and a spacecraft that closes its attitude loop through its
    sensors carries it into its wheels (4.8e-6 of scale);
  - recorder seed keys spelled by the compiler (a defect, fixed below).

  The rules: 1e-6 of the quantity's scale (well-conditioned outputs
  differed by at most 3.8e-7); absolute floors by unit, about ten times the
  largest difference measured (1e-6 rad, 1e-12 for eccentricity, 1 m for
  relative orbit elements); wrapping angles modulo 2*pi, first, last and
  samples only; a sensor output from another standard library by its
  count only. Every CI difference was replayed through these rules: none
  is reported, and CI's Linux jobs passed.
- **Off the recording platform, a coarse check (1 %):** the second Windows
  run found template 21's magnetorquer and wheel outputs 7.6e-4 of scale
  away, where the first Windows run had matched them within 1e-9. Each
  commit gave the same values on both of its Windows runs, so Windows
  repeats itself per commit; the only engine change between the two
  commits was the recorder seed names, and on Linux changing every
  recorder seed, or running all 30 other templates first in the same
  process, leaves template 21 bit-identical. **The cause was not found.**
  A switching controller (momentum dumping) amplifies any last-bit
  difference, so no small bound can be given. On another C++ standard
  library every number is therefore held to 1e-2 of its scale; texts,
  counts, events and warnings still match exactly. The fine check is
  Linux's, where the baseline is written and the developers and CI run it.
- **What this costs:** a change smaller than 1e-6 of a quantity's scale is
  not caught on Linux (a 1.5e-8 change of Earth's GM moves a 6-hour LEO
  position by about 2e-7 of its scale), nor one under 1 % on Windows. A
  Linux computer whose math library rounds differently could in principle
  also shift template 21's switches; none has so far (this computer and
  CI's Linux runners).
- **Recorder seed keys the same on every platform** (`engine.seeds.model_key`):
  Basilisk names a recorder after the message type as the compiler spells
  it ("Rec:SCStatesMsg" with GCC, "Rec:class <struct SCStatesMsg" with
  MSVC), so the provenance listed different keys on Windows. Recorders draw
  no random numbers: no result changes.
- **Isolated as every test is:** the capture runs in a home of its own (no
  downloaded space weather, no installed Earth orientation files), so the
  update script and the test compute the same thing.
- **Budgets with an Isp of 220 s on templates 22 and 26** as well:
  26 of the 31 templates have no orbit thruster, so their budget is
  refused; the refusal is recorded, and these two also exercise the
  drag-driven budget.
- **`docs/changes.md` starts empty:** the baseline changes no number.

## Transparency plan (2026-10-29)

The user's answers to `docs/transparency_audit.md` Section 10, recorded there in 10.1.

- **YAML for configuration:** comments and units can sit next to each value; PyYAML already
  ships in the installers.
- **One set of constants, with each changed number recorded:** today three sets of Earth
  constants and two solar fluxes give slightly different numbers in different views.
- **Change history in a sidecar file:** the scenario stays a clean input for version control.
- **Author from Settings, defaulting to the operating-system user name:** the audit gave no
  recommendation here. This reading works without setup and can be corrected by the user.
- **Defect 3.4:** the GUI shows the gains applied after inertia scaling. The scaling is kept,
  because the unscaled gains diverge for small spacecraft (HISTORY.md).

## Temporary folders and refusals of the wrong shape (2026-10-29)

The audit's R14 and a note under R5.

- **Removed when their process has ended, not only at exit:** the audit
  proposed `atexit`, but the page folders already went at a normal exit
  (`TemporaryDirectory`) and the icons' folder, which used `atexit`,
  leaked with them: what leaks is a killed or crashed process, which runs
  no exit code. So each name carries the process id, and the next start
  removes the folders of processes that have ended. A process that cannot
  be checked counts as running: a folder in use is never removed.
- **The old names, after a day:** a folder named before this change
  cannot be traced to its process; it is removed once it has not changed
  for a day, as only a session of the old version still running could
  use it.
- **At GUI start, in the background:** the GUI makes all the page folders;
  1014 folders took 10.4 s to remove here, so a thread does it. The CLI
  makes only Vizard's folder, removed at exit; a crashed CLI run's is
  removed at the next GUI start.
- **Coverage of Monte Carlo's workers, set in `pyproject.toml`:** the
  audit read `cli.py`'s 74 % as CLI tests in unmeasured subprocesses.
  They call `cli.main` in the test process; what went unmeasured is Monte
  Carlo's `multiprocessing` workers. Measuring them costs no time (9 min
  41 s against 10 min 18 s) and needs `branch` and `source` in the
  configuration, or the processes' data cannot be combined (the first try
  failed so). Coverage's `patch = ["subprocess"]` adds 3 lines more but
  also starts coverage in pytest-xdist's workers: 6 data files were left
  after the run, one half-written, which a later local run would try to
  combine. The missing CLI tests are a separate change.
- **Refusals keep "malformed scenario structure":** the SUM's message
  table, the JSON view and scripts read it; the part in brackets now says
  where and what instead of Python's own message.

## Output folder and input limits (2026-10-29)

The audit's R7, R8 and R9.

- **A used output folder is named, not refused:** the audit offered
  refusing a non-empty folder unless `--overwrite` is given, or removing
  the files of the previous `provenance.json`. `--out-dir` defaults to
  `results`, so refusing would break every second run of a script that
  never set it; and `provenance.json` does not list the files a run wrote,
  so nothing says which old files are safe to delete. `run` therefore
  writes as before and ends with a `WARNING` naming the files it did not
  write.
- **The output folder is probed, not only created:** `mkdir` succeeds on
  a folder that exists but is read-only; a temporary file written and
  removed in it is the check that matches what the run will do.
- **Limits far above any real scenario:** the templates have at most 6
  spacecraft, files of at most 27 KB, steps of at least 0.1 s and names of
  at most 11 characters. The limits (1000 spacecraft, 20 MB, 0.001 s, 64
  characters, a description of 100 000 characters) only stop a mistyped
  or damaged input; 0.001 s is the GUI's own least step. A file over the
  limit is refused after reading one byte more than the limit, never
  whole.
- **500 MB for a CCSDS message:** a long, finely sampled OEM is
  legitimately large, so the limit is far above a scenario's.

## Parser, look-ahead and exit codes (2026-10-29)

The audit's R5, R6 and R13.

- **A new exit status, 4, for an internal error:** 1 means invalid input
  in ICD-02 and 3 a failed run; a fault in the tool itself is neither,
  and a script deciding whether to retry or fix its file needs to tell
  them apart. The traceback goes to the log file only (its DEBUG level),
  so the terminal shows one line; without a log file it is printed.
- **`--max-years` refused by argparse (status 2):** the same as every
  other bounded option (`--oem-stride 0`, `--altitudes`); the audit asked
  for 1, but ICD-02 gives 2 to a usage error, which this is.
- **100 years, the GUI's limit:** the engine and the CLI now share it;
  the 25-year guideline needs far less, and past 100 years the solar
  cycle forecast only repeats.

## Room for results at 1280 x 720 (2026-10-28)

The audit's G8: "Inspect fields only; collapse the Inspector on small
windows; open Problems on errors only."

- **By the screen, not the window:** the window opens at 1400 x 850, so a
  rule on the window's own width would hide the Inspector on every
  screen. A screen narrower than 1600 px is where the window cannot be
  wider; there the Inspector starts hidden.
- **Only for a new layout:** a layout the app kept (the window's or a
  project's) is applied as it was, so nobody loses a panel they chose to
  keep. Reset Layout gives the new window's panels.
- **An edit's first error opens Problems, nothing else:** the blank
  scenario opens with an error (no spacecraft yet), and opening the panel
  for it, or for a file opened with one, would undo the room it gives. A second error,
  or a warning, only adds to the counts in the status bar and the top
  bar; a panel the user closed stays closed until the scenario is valid
  again. A run that cannot start still opens it.
- **Fields only, and a box's own line edit is its box:** the Inspector
  describes a value: its range and help. A button or a tab has neither,
  so it shows the empty state rather than dashes.

## Control borders at 3:1 (2026-10-28)

The audit's G7: "A control-border token of at least 3:1, added to
CONTRAST_PAIRS."

- **A new token, not a darker border.strong:** border.strong also draws
  panels, toasts and buttons, where it separates surfaces (the design
  rules' "very few lines"); a field or a check box is identified by its
  border, a button by its label.
- **text.primary over the surface, the least share that passes:** the
  same derivation as the other tokens; 51 % light and 42 % dark give
  3.08:1 at worst (on bg.hover), so the borders stay as quiet as the rule
  allows.
- **Disabled controls keep border.subtle:** WCAG 1.4.11 exempts inactive
  components, and the fainter border says that they are.

## A Monte Carlo batch can be cancelled (2026-10-28)

The audit's G3: "Terminate the child process, keep finished cases, offer
'Cancel and close'."

- **The child ends its own processes, then itself:** Basilisk's
  Controller has no way to stop part way, and it starts a pool, a data
  writer and a manager from the batch's child; terminating the child
  alone would leave them running (on Windows, nothing would end them).
  A thread in the child waits for a cancel event and ends every process
  it started; the GUI terminates the child only if that takes over 15 s.
- **The runs finished are summarized by a second, short child:** the run
  files are pickles, read only by the kind of process that had them
  written (security analysis S-04), as the batch does at its end. A file
  cut short by the cancel is skipped. Runs not finished are not listed as
  failed: they were stopped.
- **Closing asks, Keep running the default:** a batch can be hours of
  work; closing by accident must not end it.

## Exports off the GUI thread (2026-10-28)

The audit's G2: "Move them to a worker, as the flight software export
already does."

- **A worker per export, the files only:** the folder dialog and the
  plots' rendering (in the page) stay where they are; what took the time
  was decoding the images and writing the files.
- **Cancel between files, not inside one:** a file is never left half
  written; the ones written stay, and the message says how many.
- **What the files hold is taken when the export starts:** the shown
  plots, their series and the run's provenance, so a new run arriving
  meanwhile does not mix into it.
- **Progress beside the buttons, not in the status bar:** the status bar's
  job strip is the run's; an export is the Results page's own.
- **The window waits for an export when it closes** (seconds at most),
  as it does for the reference data read.

## Monte Carlo off, said before Run (2026-10-28)

The audit's G5: "Let the mode decide, or show an inline 'Enable' banner
before the click."

- **The banner, not the mode deciding:** Scenario > Monte Carlo > Enabled
  is saved in the scenario (a file can carry its dispersions, off, for a
  later batch), and the run mode is not; letting the mode switch it would
  change the file by picking a mode. Enable stays one click, on the Run
  page, and goes to the page where the batch still needs its dispersions.
- **Run is not disabled:** it still says why, as before, for a click made
  anyway (from the toolbar or Ctrl+R, where the note is not seen).

## The run's length with a Mission Sequence (2026-10-28)

The audit's G4: "Say so on the Duration field; make Overview reflect the
sequence."

- **From the steps, without running:** durations add up, an epoch stop
  ends at its epoch; an event stop, or an if/while with a propagate in
  it, ends only when it runs, so it is counted ("+ 2 event or condition
  stops") rather than guessed.
- **Passes over the sequence when it is known,** else over the Duration,
  said so: predicting where an event stop ends would need the run.
- **The Duration field is kept:** it still sets how far the space
  weather and the checks reach, which the note says.

## Space weather past the Duration (2026-10-28)

Found while checking the audit's G4 (the Duration does not limit a run
with a Mission Sequence).

- **Refuse, not extend:** the length of a sequence with event stops or
  loops is not known before it runs, so the loaded span cannot be sized
  to it; a run that would leave it stops, as one past the Earth
  orientation files already does (R1). The message says what to set.
- **An event search is checked where it stopped:** checked at its bound
  (10 x the Duration, at least 10 days), almost every search with drag
  would be refused though it stops long before; where it stopped is what
  used the data. In the CLI's unchunked search that is after the step, so
  its results are not kept; the GUI's search runs in chunks, each checked
  before it runs.

## GUI fixes from the audit, batch 1 (2026-10-28)

- **G6, Save as the default button:** what most editors do; Enter keeps
  the work. Qt's standard buttons, so the platform names them (Save,
  Discard, Cancel; "Don't Save" on macOS styles).
- **G10, Retry in the panel, a note in the status bar:** the status bar
  button already opens the panel; a second Retry there would be one more
  control for a rare failure.
- **G9, not changed:** Spacecraft › Edit in the main window already opens
  the spacecraft's page in the tree (set since U-01); the modal dialog
  the review cited is the list's fallback when it has no page to open,
  used only by its own tests.

## Dependency security (2026-10-28)

The audit's "next" row for R10 to R12: "Update Pillow and certifi;
pip-audit in CI; pin CI tools; tests required on the release tag; fix
Debian copyright" (testing 3.11 and 3.13 no longer applies: 2.0.0 needs
3.14).

- **pillow kept at 12.2.0, its advisories listed:** bsk 2.12.0 requires
  pillow <= 12.2.0, so pip cannot install 13.0.0 (the first without them)
  with the qualified Basilisk, and installing it against Basilisk's own
  requirement is not this project's to do. The 52 advisories are in
  `packaging/audit-exceptions.txt`, each by ID and for pillow 12.2.0
  only; any other advisory still fails CI, and a test fails if pillow
  moves while the list stays (K-25).
- **pip-audit on the pin files, `--no-deps`:** they list every package
  exactly, so the audit sees what the installers ship, not what a runner
  happens to resolve. In the `test` job (required), after the tests and run
  whatever happened before them (`if: always()`), so a new advisory fails
  the job without hiding the test results.
- **The dev tools in their own file:** `constraints.txt` stays the set
  the installers ship; `constraints-dev.txt` holds the tools and what
  they need, resolved against it.
- **Tests on the tag by calling the main workflow** (`workflow_call`,
  with the tag as `ref`): the same jobs as every pull request, with
  nothing to keep in step; `attach` needs them.
- **Copyright by part, last match wins:** the format's own rule; a test
  resolves sample paths of each part to their licence.

## Random seeds (2026-10-28)

The audit's E5: "Derive one seed per sensor from scenario, spacecraft,
sensor and segment; record the seeds in provenance."

- **One scenario seed, `sim_settings.seed` (default 0):** a user can ask
  for another realisation of the noise; the same file still gives the
  same run. Optional with a default, so older files load unchanged.
- **Every model, by name, after the build:** the seeds are set on every
  model still on Basilisk's default, by its ModelTag (the spacecraft and
  sensor names), not in each sensor builder, so a noisy module added
  later is covered too. Seeds set on purpose (a navigation error's own,
  Monte Carlo's) are kept.
- **SHA-256 of the scenario seed and the name:** independent of the order
  the models are built in, and the same on every platform.
- **0 to 2**31 - 1:** what the GUI's spin box holds; Basilisk's RNGSeed is
  32-bit.
- **Monte Carlo batches not changed (K-24):** Basilisk's controller seeds
  each run from its run number; changing that means changing Basilisk.

## The integrator's tolerances (2026-10-28)

The audit's E3: "Set tolerances (about 1e-10 relative) or expose them;
warn above about 60 s; record both in provenance."

- **Fixed values, not a scenario field:** relative 1e-10, absolute 1e-8
  (Basilisk's default). One measured setting serves every template, and
  a new field would change the scenario format for a value nobody has
  needed to change. Provenance records both.
- **Absolute 1e-8 kept:** 1e-10 changed nothing measurable (300 s: 11.3
  against 11.4 m).
- **A warning above 60 s, not a refusal:** under 2 cm after a day at
  60 s, 0.9 m at 120 s; a long step can be a deliberate quick look.
- **Template 17's description corrected, not its scenario:** its fuel
  use was the integrator's error; the scenario was right.

## Python 3.14 only (2026-10-27)

The user: "Drop support for every Python version older than 3.14. The
project should target Python 3.14+ only, everywhere", with three answers:
SpaceMissionStudio only (Basilisk's own packaging and workflows are the
framework's), after the open PRs merged, released as 2.0.0.

- **3.14, not "3.14 and newer" in CI:** Basilisk 2.12.0 and PySide6 6.11
  declare `<3.15`; there is no newer Python the tool installs on.
- **The installers' Python:** CPython 3.14.8 from the same
  python-build-standalone release (20261013) as 3.11.17 was, with the
  digests from that release's `SHA256SUMS` (whose 3.11.17 lines match the
  digests pinned before).
- **sgp4 without its C extension:** no sgp4 release has a 3.14 wheel, so
  pip installs its pure-Python form: the same SGP4 algorithm, slower; the
  TLE tests pass.
- **`from __future__ import annotations` kept:** removing it changes when
  annotations are evaluated (PEP 649), which `schema.scenario`'s type
  check reads; it is not an old-version shim.
- **ruff's upgrade rules once, not in the lint set:** `ruff check --select
  UP --fix` rewrote 1717 places; the leftovers it cannot fix safely stay
  (two `%` formats, one is a JavaScript string; a `Union` alias of Qt
  classes). UP is not added to the configured rules.
- **Records:** requirement and plan documents say 3.14 from today; the
  verification records (SVR, measurements, SRelD of 1.3.1) keep what was
  tested then.

## Generators by mean elements; a continuous map (2026-10-27)

The user: "Merge them all, continue as per your recommendations" (the
audit's E4). It changes the orbits the Walker and phasing generators
write, when the run models J2.

- **Mean elements only when the run has J2:** with point-mass gravity
  (the default) osculating and mean elements are the same, and mapping
  with J2 would put the satellites off by the short-period terms. So the
  generators take `j2` from `constellation.simulated_j2(central_body,
  degree)`: the body's J2 for degree 2 or more, else 0 (the pattern is
  written as before).
- **Placed like the ROE follower:** `mean_elements.osculating_from_mean`
  maps mean to osculating and corrects until mapping back gives the mean
  elements, as `roe_formation.follower_orbit` does, but in equinoctial
  elements (with the retrograde factor), which stay defined for circular
  and equatorial orbits.
- **A blend, not the nearer edge:** placing two satellites needs the map
  to be consistent on both sides of 63.435 deg. With the nearer edge the
  chief (just above) and the follower's mean elements (just below) used
  different edges: 224 m of semi-major axis, a follower 30 km off in a
  day. Blending the two edges' maps by distance keeps it continuous, and
  is closer to the orbit average (0.014 km of perigee for the 600 km
  orbit, was 0.4; the 300 km lifetime 34.82 days against the run's 34.82,
  was 34.46). It costs two Basilisk map calls in the band.
- **An equatorial band:** `clMeanOscMap` divides by `tan i` (an error at
  0 deg). Below 1 deg (above 179) it is evaluated at 1 deg (179) and the
  inclination carried across, turning node and perigee by 180 deg when
  that crosses 0.
- **Templates 04 and 05 unchanged:** regenerating them changes their
  stored orbits and documented results (template 05 holds 50 km within
  5 km); that is a separate change.

## Earth orientation files only for the runs they cover (2026-10-27)

The user: "Continue as per your recommendations" (the audit's critical
findings first).

- **The coverage from the file itself:** `pck_coverage` reads the DAF
  summary records of a binary PCK (the start and end time of each
  segment) without SPICE; a file it cannot read, or whose segments point
  past its end (a truncated download), counts as covering nothing. Read
  once per file version (0.15 ms; the checks while editing ask on every
  edit).
- **All or nothing per run:** the files are loaded when together they
  cover the whole run (`covering`); otherwise none is, and the run uses
  IAU_EARTH, as with no files installed, saying why. Loading them for
  part of a run would end it in SPICE at the first uncovered step.
- **A Mission Sequence's end is not known in advance:** every stop time
  is checked against the end of the files' coverage
  (`SimulationService.check_stop_time`, called before each
  `ConfigureStopTime` in the service and the mission engine) and refused
  with a message past it.
- **Not SPICE's RETURN error action:** with it a lookup outside the files
  would give a run silently wrong frames, which is worse than stopping.
- **Kept for later:** `earth-orientation --import` still checks only the
  header; such a file is now never loaded (it covers nothing), but the
  import could refuse it. Its tests use header-only fake files, so this
  waits for a change of its own.

## A template is a source, not a file to save over (2026-10-27)

The user: "Continue as per your recommendations" (the audit's critical
findings first).

- **Guarded at the save, not at the open:** a template opened from Home
  stays the scenario's current path, so the top bar's "template 22", the
  layout kept per scenario, the Monte Carlo archive folder and the folder
  relative mesh paths resolve against all stay as they are. **Save** on
  a template goes to **Save As** instead, and **Save As** refuses the
  templates folder (`_is_template` in `gui/main_window.py`).
- **Where Save As starts:** the home folder under the template's file
  name, so the user's copy keeps the template's recognisable name until
  they change it.

## Mean elements at the critical inclination (2026-10-27)

The user: "Continue as per your recommendations" (the audit's critical
findings first). It changes what the tool computes, near the critical
inclination only; the overhaul's "UI only" rule covered the overhaul,
which has ended.

- **Basilisk's map, evaluated at the band's edge:** within 1 deg of
  63.435 or 116.565 deg, `clMeanOscMap` is called at the nearer edge and
  the inclination difference carried across (`engine/mean_elements.py`),
  both ways (osculating to mean for the lifetime's start, mean to
  osculating for its density ring) and for the mean-element series of a
  run. Outside the band it is Basilisk's map, bit for bit, so nothing
  else changes.
- **Not an orbit-averaged map everywhere:** averaging the J2 motion over
  an orbit has no singular terms and is the test's reference, but it
  would change every lifetime slightly and cost a propagation per state;
  the edge evaluation agrees with it within 0.4 km of perigee (600 km
  orbit) and 0.7 km (Molniya) across the band.
- **1 deg:** at the edges (62.4 and 64.4 deg) the plain map is within
  about 1 km of the average for a Molniya orbit (0.5 km at 62 deg, 1.1 km
  at 63.9 deg); nearer the critical value it grows (17 km at 63.4 deg).
  Narrower bands were not tried.

## The propellant budget's rocket equation (2026-10-27)

The user: "Continue as per your recommendations", after the audit of
2026-10-27 recommended fixing its critical findings first. This is the
first change since the UI overhaul (1.3.0) to what the tool computes; the
overhaul's "UI only" rule covered the overhaul, which has ended.

- **The mass before each burn:** the budget applied `m * (exp(dV / Ve) - 1)`
  with `m` the phase's starting mass. That form is the rocket equation
  only for the mass after the burn; from the mass before it the
  propellant is `m * (1 - exp(-dV / Ve))`. With the total propellant in
  the starting mass, the old form gave `P = (D + P)(e^x - 1)`, which has
  no solution from `e^x = 2`. The guideline's own text was not consulted
  (it is not in the repository); the physics decides, and the module
  docstring says what changed.
- **In order:** each contributor burns from the mass the ones before it
  left, so the total is the rocket equation for the whole mission
  whatever the order of the rows; a row with a given propellant (from a
  run, attitude control, ignitions) lowers the mass too.

## The first run's end without plotly's first-use cost (2026-10-26)

The user: "Continue" (the next item offered: the end of a run, K-23).

- **Plotly warmed in a worker:** plotly builds its figure classes, their
  validators and narwhals' plugins on first use; the first run's first
  plot paid 0.2-0.3 s for it on the GUI thread. When the start-up read has
  finished, `_FigureWarmUp` (beside `_SpaceWeatherWarmUp`, kept and
  stopped the same way) builds and serialises one small figure laid out
  as the Results page lays one out (`results_widget.warm_up_figures`):
  plain Python, nothing of Qt, its figure thrown away. A run that ends
  before the warm-up has (a few seconds after start-up) still pays for
  what is not loaded yet, as before.
- **Kept:** the pauses after the last step of a run's end (25-55 ms on
  `develop`, 25-38 ms here) are Qt's own event processing while the
  workers save the run, summarise it for Overview and explain it; no
  Python on the GUI thread stands out in them.

## Opening a template faster (2026-10-26)

The user: "Continue" (the next item offered: opening a template, K-23).

- **One check per scenario loaded:** `from_scenario` sets each field, and
  each set was an edit that validated the whole scenario; it now fills
  every field, then validates once (`ScenarioEditorWidget._loading`).
  The problems shown are those the last of the four checks gave.
- **The labels prepared at idle:** the titles for messages about a
  spacecraft are the same for every editor, so they are kept per process
  (`spacecraft_editor._label_titles`). When start-up has settled (the
  reference data read), the main window starts their form as its hidden
  child; it builds a section per event-loop turn, as a page's form does,
  and is read and deleted when complete. A title asked for first still
  finishes the form at once. Its longest turn is the Power section,
  about 0.1 s, once per process, while nothing else happens.
- **The last observed day kept on the data:** `real_data_path` looked
  through every day of each space-weather file for its last observed
  day on every edit-time check (10 ms); `CelestrakData.last_observed`
  finds it once. The engine's result is the same day; nothing computed
  changes.
- **No window size for an embedded Environment form:** like a page's
  spacecraft form, it takes the page's size, so the content is no longer
  measured for a window (8 ms per open).
- **Kept:** the Environment form is still rebuilt on each load (about
  30 ms, with 12 ms of it taking the old form out of the window); loading
  new values into the same form would need a second way to fill it,
  kept in step with the constructor.

## The messages' titles without a hidden form (2026-10-26)

The user: "yes, remove the hidden label form" (K-19).

- **Titles kept as text, the form deleted:** a message about a spacecraft
  whose page has no form was worded from a new spacecraft form built
  for that and kept hidden. `SpacecraftLabels` builds one at the first
  title asked for, reads the title of every code of the schema (197:
  the spacecraft's fields, its sections' fields, the orbit's), keeps
  them and deletes the form. The titles are the same (a test compares
  them with a form's for every code and for template 18's messages).
- **A code outside the schema** (a key of `fsw_params`, a list item's
  field) builds a form once for it; its title is kept too.
- **Most words need no form:** `field_title` answers "" at once for a
  word that names no spacecraft field; that part is now a function both
  use, as is `problem_text`, so the two cannot drift apart.
- **The ground station's label form stays:** it is small.

## The spacecraft page, a section at a time (2026-10-26)

The user: "yes, build the spacecraft page a section at a time" (K-23).

- **The code of each section moved unchanged** into its own method; the
  pages are made first, in their tab order. A script cut the constructor
  at its section headers, so no line inside a section was retyped.
- **Built in the order they always were:** a section's code may use the
  widgets of the sections before it (it ran after them before). So
  showing a later section builds every section before it too.
- **Orbit / mass at once, the rest one per event-loop turn:** the page
  is complete about a second after it is shown, so a run, an undo or a
  save never meets a half-built form in practice. When something does
  read a field of a section not built yet (`to_dataclass()`,
  `field_widget()`, a handler), `__getattr__` builds the rest first: no
  reader needs to know.
- **Not left unbuilt until visited:** `to_dataclass()` reads every
  section after every edit; keeping a section unbuilt would mean
  reading its fields from the config instead, field by field, where a
  field put in the wrong section would quietly lose an edit.
- **The orbit-only adjustments apply per section**, each group once,
  as its section is built; `finish_form` runs per section.
- **The dialog used on its own builds every section at once:** it sizes
  itself from all of them.
- **No gain for the theme switch:** every section is built a second
  later and Qt restyles them all (K-19 stays).

## The theme switch (2026-10-26)

The user: "yes, start on the theme switch" (K-19).

- **Set Fusion only while no sheet is set:** with a style sheet set,
  `app.style()` is Qt's style-sheet style and its `name()` is empty, so
  the check for Fusion failed on every switch and set it again, a full
  restyle before the sheet's. The sheet only ever goes on top of Fusion.
- **The sheet is still cleared before the new one:** measured again, a
  switch without clearing took 3.5-4.1 s, against about 0.5 s with it.
- **What is left is per widget, not per rule:** a one-rule sheet costs
  about 0.3 s of the 0.5 s; the full 195-rule sheet adds 0.1-0.15 s. Only
  97 of about 2,700 widgets are shown, but Qt restyles every one. Fewer
  hidden widgets (the spacecraft page built a section at a time) is the
  next step; trimming the sheet would gain little.

## After the overhaul (2026-10-25)

The user: "fix the engine messages and the shortcut conflict".

- **Engine messages name Settings > Reference data:** the M2a decision
  kept "Tools > Reference Data" in two engine messages because the engine
  did not change during the overhaul. The overhaul is done and the user
  asked for it: the support-data error and the Earth orientation warning
  now name where the dialog is. Text only; nothing the engine computes
  changes, and no output file carries either message.
- **Alt+Backspace is Clear Time Cursor's alone:** Qt's standard Undo keys
  include Alt+Backspace on Linux and Windows, and a key bound to two
  enabled actions fires neither ("Ambiguous shortcut overload"), so once
  there was anything to undo, Alt+Backspace did nothing. Undo keeps its
  other standard keys (`Ctrl+Z`); Clear Time Cursor keeps Alt+Backspace,
  the key the manual, tips and DESIGN document. A test now checks that no
  two commands share a key.

## M9 Final pass (2026-10-22)

Recorded after measuring, before the changes. `scripts/measure_ui_baseline.py`
was run on this machine for both the code the plan's baseline was taken on
(`66949b4`) and M8: the machine is slower than when the plan was written
(the same code now starts in 2.5-2.8 s, not 1.69-1.97 s), so M9 compares
the two on this machine, in the same session, as the plan's §3 asks ("re-
measured on the same kind of machine").

- **Before and after on one machine:** `docs/ui/perf_after.json` holds the
  M9 run and `docs/ui/perf_baseline_rerun.json` the baseline code's run
  of the same day; BEFORE_AFTER.md compares those two, and quotes the
  plan's original figures beside them.
- **The spacecraft forms:** M8 made the first visit to a spacecraft page
  and the editor dialog slower than before the overhaul (671 against 541
  ms; 554 against 415 ms). Each tab page was built, then moved into its
  scroll area, then into the tabs, and the embedded dialog turned into a
  widget last: each move restyles the whole tree under the app's style
  sheet. Pages are now placed before they are filled, and an embedded
  form is a widget from its first line; an embedded form skips measuring
  its tabs for a window size it never takes.
- **Start-up:** the reference data inventory (1.5 s of the window's
  constructor: importing Basilisk, parsing the space-weather file, hashing
  files) was computed twice on the GUI thread, for the Reference data
  dialog and the status bar. It is now read once, after the window is up,
  in a spawned child process (`gui/reference_data_process.py`, as the
  Monte Carlo batch runs): on a worker thread it still held the
  interpreter for most of that time, stalling the new window for up to
  0.7 s. The child returns the Basilisk version with the files, so the
  status bar does not import Basilisk on the GUI thread either. The status
  bar and the dialog fill in when it is done (about 1.5 s later); the
  dialog's Refresh and the refresh after a download stay synchronous, as
  before. Closing the window ends the child (it only reads). Checking a
  scenario's dates needs the space-weather file parsed in the window's
  own process, which the old start-up did as a side effect: without it
  the first scenario opened took 0.5 s longer. A worker thread parses it
  once the child has answered; part of that parse holds the interpreter,
  so it costs one stall of about 0.2 s, about 1.3 s after the window
  appears, where it cost 0.5 s on the first open.
- **The 50 ms first visit** is not reachable for the spacecraft page
  without building its tabs lazily, a rewrite of a 2,000-line editor whose
  tabs read each other's fields: not done; the measured value is recorded.
- **Keyboard-only walk** (`tests/gui/test_keyboard_walk.py`, new): each
  area by its shortcut, then Tab must reach every control in it that takes
  the keyboard, and never land on a hidden widget. An exclusive group of
  buttons (radio buttons, a segmented control) is one stop, chosen with the
  arrows, as in Qt. It found a keyboard trap: Tab in the scenario's
  description typed a tab instead of leaving it, so nothing after it (the
  Form · JSON toggle, the area's commands, the rest of the page) could be
  reached by Tab. Plain-text boxes now pass Tab on (as the JSON view and
  the script and parameter boxes already did), and read-only tables do
  too (the arrows move in them); tables that are edited (facets, data
  handling) keep Tab from cell to cell, which leaves the table after the
  last cell.
- **The garbage collector after a run** (70-83 ms full collections, held
  from M6b): not changed. Tuning the collector's thresholds would move the
  pauses, not remove them, and freezing the run's objects would keep them
  alive for the session; recorded with the end of a run's measurement.
- **Version:** the plan says 1.2.0, written before 1.1.1 and 1.2.0 were
  released (2026-10-21). The UI overhaul's release is **1.3.0** in every
  version file. Tagging and releasing stay the user's.

## M8 Reports, exports and Settings (2026-10-22)

Recorded before coding, after reading the exports of §5.3, the Reports
area (Flight Software only) and the Settings page (appearance, reference
data, layout, keyboard and About as commands).

- **Reports › Exports**, the area's first page: every export of §5.3 in a
  `DataTable`: what it writes, its format, where it is made (the view and
  its button), the default destination, the provenance written beside
  it, and when this machine last wrote one (UTC). Enter or a double-click
  opens the view that makes it. The time is kept by a small export log
  (`gui/export_log.py`, the app's settings, not any file it writes),
  which each export records after it succeeds.
- **The per-view Export buttons stay as they are.** The plan's "one
  Export button per view opening the same export sheet" would move every
  view's buttons for no new export; Reports › Exports is the one place
  that lists them all. Recorded here as not done.
- **Export files byte-identical to 1.1.0, tested:** a script
  (`scripts/make_export_references.py`) writes each export the GUI makes
  from fixed inputs, through the same engine and widget functions; run on
  1.1.0's code (commit `1c7d76f`, the 1.1.0 release) it wrote the
  references, kept in `tests/data/exports_1_1_0.zip` (a zip: the
  repository's line-ending and end-of-file rules would change a CSV's
  CRLF or a file that ends without a newline), and a test runs it on this
  code and compares every byte. The `.obj` comes from a model of simple
  shapes made in the script (no template has a model). Run on 1.2.0's code
  (commit `c92f900`, the latest release) the script writes the same
  bytes. Covered: the results CSVs (with their
  provenance), the events CSV, the Mission Output CSV, the Monte Carlo
  table, the budget CSV, the `.obj` model and the SIL report. Not
  covered, with the reason: the PNG and SVG plots (drawn by the web
  engine, not by this code), the flight-software project (already
  checked byte for byte against Basilisk's files by `test_fsw_export.py`)
  and the Vizard file (written by Basilisk during a run).
- **Settings › Appearance** adds:
  - **UI scale** 90, 100, 110 or 125 %, applied at the next start
    (`QT_SCALE_FACTOR` is read once, before the window exists; a live
    change would need every size in the theme recomputed and every page
    laid out again). The page says so.
  - **Reduce motion:** toasts fade in and out over 150 ms (the design's
    120-180 ms); with reduce motion on they appear and go at once. It is
    the only motion the app has.
- **Settings › Vizard:** the Vizard program's location, with Browse and
  Clear (the one `vizard_launcher` remembers).

## M7 Timeline and plots (2026-10-22)

Recorded before coding, after reading the Timeline and timing it with
10,000 events (`scripts/measure_timeline.py`, new; synthetic passes and
eclipses over a year, given to the Timeline's own entry point): showing
them held the window about 730 ms, a search keystroke 2.3-2.6 s, clearing
it about 1.5 s, a zoom 1.6-1.7 s. The table builds a `QTableWidgetItem`
per cell and sorts them in Python; the timeline draws every event on
every paint and looks for the one under the pointer among all of them.

- **The table is a `DataTable` whose rows are made when shown:** the
  events in a sequence that formats a row when the view asks for it, and
  sorts itself by each column's values with NumPy (a header click), so
  neither filling nor sorting walks every cell. Its text, columns and
  export stay as they are.
- **The search** matches against each event's text made once per run, not
  on every keystroke.
- **The timeline draws what it can show:** per lane, the events in view
  (found by bisection), merged where they fall on the same pixels; the
  event under the pointer is found by bisection too.
- **A UTC axis with `Z`** when the run has an epoch (ticks at round UTC
  times: "08:00Z", the date at midnight), elapsed time without one.
- **Zoom and pan:** the wheel zooms around the pointer (as now);
  Shift+wheel, a horizontal wheel and a right- or middle-button drag pan;
  `+`/`-` zoom, the arrow keys pan, `0` or Home fits. A left click or drag
  still sets the time cursor, which the plots share (as now).
- **Lanes** stay one per spacecraft and kind, a pass's per station and
  spacecraft (as now).
- **Plots:** the display decimation (`_MAX_PLOT_POINTS_PER_LINE`) and the
  time cursor linked across the grid are already there and tested; M7
  adds a test that an export writes every sample.
- **Measured after** (`scripts/measure_timeline.py`, three runs): showing
  10,000 events held the window 35-38 ms, a search keystroke 37-39 ms,
  clearing it about 10 ms, a zoom 5-8 ms, a paint 7-13 ms; at most
  39.4 ms. Met ("without a stall over 50 ms"). Besides the lazy rows and
  the lanes, it took: column widths from font metrics over the first
  rows (Qt's own sizing asked for every role of every sampled cell), no
  filter proxy for a table its owner filters (the proxy called Python
  once a row), one UTC conversion per 128 rows shown (each call costs
  about 4 ms whatever its length), and the axis's UTC span converted once
  a run, interpolated between its ends (TDB - UTC drifts milliseconds
  over a run; the labels are to the minute).
- **The 3D model view** is already created only in the 3D model editor,
  opened on request: lazy and opt-in as asked. Every measurement in this
  overhaul runs with software rendering (offscreen, no GPU), the case
  `--disable-gpu` forces.

## M6b The tables and analysis views (2026-10-22)

Recorded before coding, after reading Output, Monte Carlo, Compare, End
of Life, Budget and the Dashboard, and timing the end of a run (template
23, the second and third runs of a session: 81-132 ms in one slot, of
which showing the Output page 32-54 ms, the results view 20-33 ms and
filling Output's table 12-22 ms).

- **One `DataTable` component** (`gui/data_table.py`): a `QTableView`
  over a `QAbstractTableModel` with the table rules (CLAUDE.md, Tables):
  a sticky header, numeric columns right-aligned in the numeric font with
  their unit in the header, Ctrl+C and Copy as TSV, a column-visibility
  menu on the header, row hover, no zebra, and an empty state with its
  primary action. Filtering is a predicate the view gives it (Output's
  filter shows report columns or rows); sorting is on where rows have no
  order of their own. Group rows span the table.
- **Output and Monte Carlo move onto it.** Each keeps its text, its
  filter and its export as they are; a test that read a `QTableWidget`
  item reads the table's cell or header instead (TEST_CHANGES).
- **Compare, End of Life, Budget and the Dashboard (Telemetry)**, as
  built: Budget's three tables and Compare's three are a `DataTable`
  (Budget's worst case a bold row, a row picked with `row_chosen`;
  Compare's "(same)" cells muted). Compare's run switcher is its list of
  runs to tick, as before. End of Life already shows its results as
  tiles, and the Dashboard's group boxes are headings, not frames, since
  M4a's style sheet: both are kept as they are.
- **The end of a run, as built:** shown in steps, one an event-loop turn
  4 ms apart (the results view; the dashboard, timeline, run record and
  analyses; Output; the view shown), each 17-31 ms after the first run of
  a session. The run's save starts 1 s later (its zip writing shares the
  interpreter with the GUI thread and doubled the steps' time beside
  them). A new run, clearing the views or closing takes the steps left.
  Tables size their columns once when filled (ResizeToContents measured
  every cell at every layout).
- **Measured after** (`scripts/measure_run_end.py`, template 23, two
  sessions of three runs): the run's own slot 21-36 ms after the first run
  (was 102-110 ms); the longest stall in the 3 s after it 47-57 ms in most
  runs, up to 151 ms when a full garbage collection (71-83 ms) fell in it.
  **Not met** ("no stall over 50 ms"): the remainder is the collector and
  the Overview's worker sharing the interpreter; M9's performance pass
  holds it. The first run of a session: 197-268 ms (the first results
  view and figure).

## M6 Results overview and analysis views (2026-10-22)

Recorded before coding, after reading the Results views and timing a plot
switch (`scripts/measure_plot_switch.py`, new; template 23, twelve plots
shown one after the other in the selected cell, two runs on M5b's code):
each switch held the window 59-97 ms (median 72-76 ms), the first one, a
three-line plot, 275-304 ms; the plot was drawn about 400 ms after the
click (354-692 ms). Nearly all of it is building the Plotly figure in
Python (its two `update_layout` calls validate every property), then
writing the page and reloading it with plotly.js.

- **Split before starting, as M4 and M5 were (§8, "Scope"):**
  - **M6a, the Overview and the plot view:** Results › Overview with the
    run's metric cards and its provenance in a popover; the plot page
    persistent, plotly.js loaded once; switching plots under 50 ms, which
    is also what is left of the end of a run's stall (M5a).
  - **M6b, the tables and analysis views:** Output and Monte Carlo as a
    `DataTable` (a `QTableView` with the table rules), Compare's run
    switcher, End of Life, Budget and Telemetry from the components.
- **Overview cards come from `engine.run_summary.summarize`,** as
  Compare's summary does: one card per figure, its label, value and unit
  (in the header of no table: on the card). A card is coloured only where
  the scenario sets the threshold: the lowest link margin below 0 dB (the
  margin already includes the required Eb/N0) and the battery's lowest
  charge at 0 are critical, with an icon and a word; every other card is
  neutral. The figures are computed off the GUI thread.
- **One persistent plot page:** loaded once with plotly.js; a change of
  plots, layout or theme sends the figures' JSON to it (`Plotly.react`),
  with no reload. The page tells the view when a plot is drawn (and
  whether Plotly drew it without an error). A theme switch loads the page
  again (its fonts and surface).
- **Figures are built once and kept** per plot until the result, the
  theme, the x axis, the comparison or the event bands change; showing
  another plot builds only that one. A figure is built in one validated
  construction (its traces and layout together), with the same JSON as
  before (checked on every plot of a template 23 run, three x axes, both
  themes: the same objects; only the order of keys in the text differs,
  and no file holds that text), so exports and every saved image are
  unchanged.
- **The layout is saved after the click,** not in it (a timer; the
  QSettings write took about 15 ms). Reading a saved layout, hiding the
  view and quitting write what is pending first.
- **Start-up's objects leave the garbage collector's full collections**
  (`gc.freeze()` once the window is up, after a collection). A full
  collection walked them all: 190-234 ms on the GUI thread wherever it
  fell, a plot switch or a keystroke. Freezing again after each run would
  keep a whole simulation's cyclic garbage for good, so it is done once.
- **Measured after** (`scripts/measure_plot_switch.py`, which freezes as
  the app does; four runs, 48 switches): a switch holds the window at
  most 34.4 ms (median 19-22 ms), and the plot is drawn after about
  110 ms (median 106-126 ms; was about 415 ms). Met.
- **The end of a run stays held, now for M6b** (`scripts/measure_run_end.py`):
  102-110 ms after the first run of a session (M5a: 152-163 ms; the first
  311 ms, was 519 ms). Of what is left, the Output page (filling its
  command table and showing it) is about half; M6b rebuilds it as a
  `DataTable`.

## M5b The Run area's controls (2026-10-22)

Recorded before coding, after reading the run mode menu, the Vizard
dialog, the SIL prompts and the Monte Carlo folder picker.

- **A Run page, first in the Run area,** holds what the next run uses,
  for the mode chosen: the options that were menu entries and dialogs.
  End of Life, Budget, History and the Log stay beside it.
- **The mode is a segmented control, Single · Monte Carlo · SIL,** in the
  Run area's header, replacing its "Single run ▾" menu button. The top
  bar keeps its compact mode menu: it is on every area, where three
  segments would take the room of the title.
- **Single:** Live plot as a check box (the same command as before, with
  its palette entry), and the Vizard options as a form on the page,
  applied as they are edited (the dialog's form, embedded). Vizard
  Configuration opens the page there; Launch Vizard stays a command.
- **Monte Carlo:** the archive folder as a field with Browse...,
  remembered per scenario (by its file, or its name when unsaved); Run
  uses it without asking. An empty field still asks with the folder
  picker (a chooser, not a question). Overwriting a folder that holds a
  batch stays a confirmation, the one destructive question (§5).
- **SIL:** the spacecraft whose flight software runs (those that can be
  exported) and the run's options (the SIL dialog's form, embedded), on
  the page; Run starts it without a prompt. With none that can be
  exported, the page says why and where to fix it.
- **The header's Live plot and Vizard Configuration buttons go:** they
  are on the page. Their commands stay in the palette.

## M5 Run and logs (2026-10-22)

Recorded before coding, after reading the run, the run store and the
Log, and timing the end of a run (template 23, a second run in the same
window: 286 ms in one slot, of which the results view 75 ms, the run
list 75 ms, Compare 58 ms, saving and pruning 22 ms; the first run of a
session 978 ms).

- **Split before starting, as M4 was (§8, "Scope"):**
  - **M5a, the end of a run and its record:** saving and pruning in a
    worker; the rest of the end of a run broken into steps, none of which
    holds the window long; History (the runs, loaded in a worker); the
    Log's records of each run, in JetBrains Mono, with its filter, search
    and copy.
  - **M5b, the Run area's controls:** the mode as a segmented control,
    and the options inline (Live plot, Vizard, the Monte Carlo archive
    folder, SIL) instead of menus and dialogs.

  Each is one pull request a reviewer can follow; M5a carries M5's
  performance criterion.
- **History needs no new file field.** A saved run already has when it
  started (its provenance's `run_started_utc`) and finished, whether it
  was cancelled, and its provenance: the duration and the status come
  from them. File formats stay as they are (the overhaul's rule). Runs
  that failed, and Monte Carlo batches, are not in the run store; History
  lists them for the session they ran in, from memory.
- **The results view stays as it is in M5:** it rebuilds its plots when a
  run ends, and M6 rebuilds that view. M5 moves it to its own step after
  the others, so it is the only one that can hold the window; what it
  costs is measured and written down.
- **Measured after:** the end of a run holds the window 152-163 ms (was
  301-323 ms; the first run of a session 519 ms, was 788 ms), nearly all
  of it the results view's figure. Not met; M6 holds it.
- **Compare is refreshed when it is shown,** not at the end of every run
  (its plot cost 58-113 ms there); the results view redraws in
  `set_runs` only when the run compared changes.
- **History's double-click compares** the run with the one shown in
  Results: Results shows one run at a time, and drawing another dashed
  beside it is what it already does.
- **The Log's run records come from the GUI** (`spacemissionstudio.run`):
  the engine logs nothing at INFO during a normal run, and it is not
  touched.

## M4b Editing flow (2026-10-22)

Recorded before coding, after reading every editor and measuring the
refresh an edit triggers (`scripts/measure_ui_baseline.py`; a profile
of each part on all 31 templates).

- **Inline, not the inspector, for devices and dispersions.** The
  criterion allows either. The inspector already has one job (the
  focused field: label, value, range; M2), and a form there would give it
  two. The device and dispersion lists get their form under the list on
  the same page, as the mission sequence's step form already is: select
  a row and its form shows; an edit applies once it validates, after the
  same 300 ms settle as a spacecraft's page; a value that does not
  validate is marked at its field and not applied.
- **Add creates the item and opens it:** a spacecraft (from its
  template), a ground station, a device or a dispersion is added with
  its defaults and a name not yet taken, and its page or form opens.
  Nothing modal comes first; Remove and Undo take an unwanted one back.
- **Mission steps need no change:** their form has been inline since
  U-01. The plan's §5 table also suggests the inspector for them; the
  inspector point above applies.
- **Dialogs that make things stay dialogs:** the template picker, the
  Walker, phasing and ROE generators and the 3D model editor create or
  replace several values at once, from inputs that are not the
  scenario's. The brief keeps modal dialogs for multi-step work. The 3D
  model page is §5's, not M4's.
- **The list widgets keep their dialog for a list used on its own:** the
  app has no such use (each list lives in the Scenario editor, which
  edits inline), but their tests build them alone. Removing the path
  would remove those tests.
- **Undo stays `ScenarioHistory`.** Every way of editing (a form, a list,
  the JSON, a generator, Undo itself) ends in one scenario snapshot after
  the edit settles. `QUndoStack` wants a command per kind of edit with
  its own undo, which would re-implement what restoring a snapshot does
  for each of them; wrapping snapshots in commands would add only a
  `QUndoView`, which nothing shows. The criterion keeps
  `ScenarioHistory` when `QUndoStack` does not fit.
- **Form · JSON is a toggle in the Scenario area's header,** replacing
  the JSON node of the tree (§5 table). JSON mode shows the text in
  place of the tree and its page. Back to Form applies the text first,
  through the same parsing as opening a file. Text that does not parse
  or validate keeps JSON mode, with the problem in its banner and a
  Discard button that restores the scenario's text.
- **Explain is the tree's first node, "Overview",** and the Explain dock
  goes. View › Explain opens it. Its title counts what to check, as the
  dock's did. The plan's §5 also has the inspector show the summary when
  nothing is selected; that is not part of M4's criterion and is left
  out.
- **Only the explanation moves off the GUI thread,** because it is the
  cost: `engine.scenario_explainer.explain` takes up to 49 ms per edit
  (26_earth_observation_data_downlink), and rendering it 4–10 ms. Building
  the scenario, the stale-results check, the top bar and the analyses'
  inputs take under 1 ms together and stay immediate, so nothing else
  lags an edit. The explanation is asked for 250 ms after the last edit,
  computed in a `QThread` from the scenario built at that moment, and
  shown only if no later edit is waiting (an older answer is dropped).
- **Not met, recorded:** the keystroke itself is at most 47.2 ms (M4a:
  86.4 ms), but a stall over 50 ms still follows a keystroke on about
  one template pass in 40, at up to 77.3 ms, not on the same template
  twice across sweeps (M4a's code: up to 140.5 ms). The garbage
  collector, the autosave and the rendering are ruled out; the cause is
  not found. M9's performance pass holds it (the plan's §7 status has
  the numbers).
- **A closed window stops its autosave and its explanation:** a window
  closed but not yet deleted autosaved its discarded scenario into
  whatever home the next test had (a test failed on it), and a waiting
  explanation could start a thread for a window going away.
- **Inline forms follow fields added later:** a device's Kind rebuilds
  its fields, which `watch_edits` had not connected; it now marks the
  fields it follows and connects new ones after each edit.

## M4a Forms (2026-10-22)

The user (2026-10-22): "once CI is green continue as per your
recommendations". M4 is split into M4a and M4b, recorded in the plan
before starting (§7 status; §8 allows a split).

- **M4a first: the forms; then M4b, the editing flow.** M4 is one of the
  two heaviest milestones (§7): every field of the editor changes how it
  shows its unit, and four dialogs become inline editors. Two pull
  requests keep each reviewable, as M2's did.
- **One walker, not 147 edited rows:** `finish_form(root)` runs at the
  end of each editor's constructor. For every form row labelled "Name
  [unit]" whose field holds numbers, it moves the unit into those fields'
  suffix and leaves "Name" as the label. Adding a row needs nothing more,
  and the rule cannot drift between forms. Only units listed in
  `gui/units.py` move; a bracket holding something else stays in its
  label (a JSON key, "lo, hi").
- **Units typeset in the field, ASCII elsewhere:** the field shows "m²",
  "kg·m²", "°", "Wh"; file names, field names, messages and exports keep
  the code's spelling. "days" stays a word rather than "d".
- **Messages keep "Name [unit]":** they name a field through its form
  label (`feedback.row_label`, `gui.field_text`). The walker keeps the
  label's full text on it (`sms_full_label`), so "Dry mass [kg] must be in
  (0, 1e6]" reads as before. The inspector names the field the same way.
- **`NumberField` is the existing full-precision spin box** with the number
  look: `PreciseDoubleSpinBox` already keeps every value exactly (a plain
  `QDoubleSpinBox` once rounded template values). The look is right
  alignment, tabular figures and a width cap of 224 px, so a number sits
  beside its label rather than across a 600 px field.
- **A row too wide for its form wraps its field under its label**
  (`QFormLayout.WrapLongRows`), and rows of buttons or boxes wrap
  (`flow_row`). Without this the Power page, the Spacecraft page (the
  three generator buttons) and template 29's ROE helper row scrolled
  sideways at 1280 px.
- **Boxes in a row of several are 128 px and may shrink to 72 px;** their
  size hint follows the widest value the range allows (a million metres),
  which made a row of four 530 px.
- **Optional groups collapse:** every checkable group shows only its title
  while off, and ticked again shows what it showed (rows another control
  hid stay hidden). Monte Carlo's switch is a check box, not a group; its
  page does the same, with one line on what turning it on does.
- **"No boxes in boxes" needed no change:** M1 made group boxes headings.
  An audit of every page of every template finds no framed panel and no
  scroll area inside a page; the test keeps it so.
- **The Customize wizard follows the same units:** its curated key
  settings' suffixes are typeset. A setting it labels from its field
  name has the unit token split off ("record_interval_s" was "Record
  interval s", now "Record interval" with "s").
- **Forms are walked through their widgets and layouts, never their
  `QLayoutItem`s:** Qt deletes a layout item without telling PySide6, and
  the item's Python wrapper can then be handed out for a new object at
  that address. On CI's Windows job a `QMenu`'s new `QAction` came back
  as a `QWidgetItem` after the walker had visited every row of every
  form. `widgets.form_rows` and `layout_widgets` use
  `getWidgetPosition`, `getLayoutPosition` and `indexOf` instead;
  `feedback.row_label` uses `labelForField`.
- **The third-body perturbers stay in lower case:** the list's text is
  the body's code, which tests read. Showing "Mercury" means a data role
  and ported tests, which is outside M4a's criteria.

## M3 Home and templates (2026-10-22)

The user: "start M3 here". Home is rebuilt: template cards, recent
scenarios, New blank scenario, Customize, and a card instead of the
start-up dialog.

- **Three columns, with the reference-data card across the top while it
  asks:**
  - **Start:** New blank scenario, the recent scenarios and Open;
  - **Templates:** the cards, in as many columns as the width holds;
  - **Details:** the selected template's whole description, with Open
    template and Customize....

  The details keep what the old page showed below its list (the
  description with "What to look at" and "Try changing"). A card has
  room for one sentence only.
- **A card's three lines, all read from the template file** (no metadata
  added, plan §7):
  - **mission type:** the attitude mode (`simulation_mode`: Orbit only or
    Full attitude) with the first spacecraft's pointing mode (its
    `fsw_mode`, named as Explain names it), and the number of
    spacecraft;
  - **orbit:** the central body, then the first spacecraft's orbit;
  - **one line:** the description's first sentence.
- **The orbit line, in detail:**
  - a circular orbit (e < 0.01) shows its altitude ("550 km circular");
  - another shows its periapsis and apoapsis altitudes ("941 × 35095
    km");
  - a small body shows the distance from its centre, as Explain does,
    since it has no single radius;
  - then the inclination to 0.1 deg, and "Sun-synchronous" where Explain
    calls the orbit so.

  The body radii and the Sun-synchronous test are Explain's own
  (`engine.scenario_explainer`), imported, not copied. Explain's own
  orbit line ("SSO 97.59 deg, 550 km alt") gives the altitude from the
  semi-major axis even for template 02 (e = 0.7). The card is new text,
  so it gives the periapsis and apoapsis instead. The engine is
  unchanged.
- **Template 19 names no pointing mode:** it points by its comms link
  (`comms_pointing`), not by an `fsw_mode`, and the card says only what
  the file says.
- **The first sentence ends at ".", "!" or "?" before a space,** not after
  "e.g.", "i.e." or "vs.". Template 29's "Sun-synchronous. follower-1"
  ends a sentence even though a lower-case name follows. The sentence
  wraps to at most four lines on the card and then elides; the whole
  sentence is the tooltip.
- **No thumbnails** (Q4).
- **A filter over the cards:** with 31 cards, typing ("monte carlo") is
  quicker than scrolling. Every word must match the title, the two
  summary lines or the description.
- **The cards are one Tab stop:**
  - the arrow keys, Home and End move between them, and Enter opens one;
  - a card's own Open and Customize... are mouse targets;
  - the details' Open template and Customize... are the next Tab stops.

  31 cards with two buttons each would have been 93 Tab stops.
- **Each card keeps its own Customize...:** users had missed one shared
  button that needed a selection first (the old page's history). The
  details have Customize... for the selected card too.
- **One accent button on the page:** Open template, in the details. New
  blank scenario, Open a scenario file... and the cards' buttons are not
  accented (design rule 1).
- **A selected card** is `bg.selected` with an accent edge; a focused card
  has the 2 px ring. On a selected card its buttons use `text.primary`:
  the link colour on `bg.selected` is under 4.5:1 in the light theme. No
  contrast pair is added.
- **Recent scenarios:**
  - the last 10, newest first;
  - kept with `QSettings` in the app's own `settings.ini`, where the
    theme is kept: one settings file, already isolated per test by
    `tests/conftest.py`. No scenario or project file changes;
  - a file is recorded when it is opened (`open_path`) or saved;
  - the built-in templates are not recorded: they have their cards;
  - a file that is gone is marked "(missing)" with a caution icon (text
    and icon, never colour alone), and opening it says so instead of
    failing;
  - `Delete` takes an entry off the list and **Clear** empties it; the
    files stay where they are.
- **The files are checked when Home is shown,** on the GUI thread: at most
  10 `is_file` calls on local paths. A path on an unreachable network
  share could stall it. A worker for 10 calls is more machinery than
  that risk is worth, so it is not used.
- **The empty state's action is Open a scenario file...**, directly under
  it. There is one Open button on the page, not one in the empty state
  and another above it.
- **The reference-data card replaces the start-up dialog** (§5.2):
  - it asks at every start: the user's standing decision says "the user
    always should be asked", and the plan's "first-run card" names where
    the question is asked, not how often;
  - it offers the same three items with the same defaults, built by one
    function (`choice_boxes`) for the card and the dialog;
  - **Fetch now** runs the same worker in the background, with the
    card's controls disabled and an indeterminate bar (each item reports
    only when it is done), and its summary is a toast;
  - **Not now** hides it and fetches nothing, as Skip did.

  The dialog and `maybe_run_startup_fetch` stay, with their tests. The
  window no longer shows them.
- **A window opened on a file** (the command line, or a recovered
  autosave) shows the Scenario area first. The card waits on Home, so the
  question is still asked but is not in view until Home is opened.
- **Closing the window during a fetch waits for it,** as it waits for the
  End of Life and Budget workers, so a file is not cut off mid-download.
- **Start from scratch stacks its button under its text:** the Start
  column is 220–280 px wide, too narrow for the text and the button side
  by side.
- **A card paints its title and two summary lines itself** (`_CardText`:
  the font, a colour token read at each paint, a height from the font
  metrics), instead of using word-wrapped `QLabel`s:
  - with the labels, Home's first show took 108–193 ms, measured offscreen
    on this machine (`develop`'s list: 19–29 ms), mostly the labels'
    height-for-width in the first layout;
  - with `_CardText` it takes 64–135 ms over four sets of runs. The
    cards' 62 buttons are a good part of the rest: 64–68 ms without them
    in a trial.
  - It is still over the 50 ms of design rule 6. Home is the page the
    window opens on, so this time is part of start-up: the window's first
    show took 184–246 ms against 98–121 ms on `develop`, with the
    labels. It is not a stall after start-up: Home stays built, and
    showing it again lays nothing out anew.
  - M9's criterion (the first visit to any page under 50 ms, start-up
    faster than the baseline) holds this value. Building the cards when
    first scrolled into view, or painting them in one view with a
    delegate, are the options there.
- **The names stay:** `LoadScenarioWidget` (also `HomePage`) and
  `MainWindow.load_scenario_widget`. Tests and scripts reach Home through
  them, and a rename would hide the real changes in noise.
- **Template descriptions** (left over from M2a): "the Events tab" is
  "the Timeline" in templates 22 and 26, "Events:" is "Timeline:" in 29,
  and "Explain, in the side panel" is "in the panel on the right" in 22.
  The template files changed only in those words; they are regenerated
  from `scripts/_template_descriptions.py`.
- **`compare_tab.png` and `monte_carlo_tab.png`** (left over from M2a)
  are now captured by `scripts/capture_screenshots.py`. It runs template
  22 a second time, two days long, as the manual's caption says, and
  template 25's batch into a temporary folder.

## M2a Shell (2026-10-21)

The user: "start M2 here". M2 is split into M2a and M2b, recorded in the
plan before starting (§7 status; §8 allows a split).

- **M2a first: the shell, then M2b the panels.** The shell changes every
  path to every screen; the panels each change one widget. Two pull
  requests keep each one reviewable.
- **Areas host the existing screens unchanged:**
  - Home: the Templates page.
  - Scenario: the scenario editor, without Templates and Analyses in its
    tree.
  - Run: the run options, End of Life, Budget and the Log.
  - Results: Plots, Dashboard, Output, Monte Carlo and Compare.
  - Timeline: the Events view.
  - Reports: Flight Software.
  - Settings: appearance, reference data, layout, keyboard and about.
  - Help: the manual.

  Rebuilding the screens is M3 to M8.
- **End of Life and Budget keep their inputs and results on one page, in
  Run:** Q3 puts the inputs in Run › Analyses and the results in Results.
  Splitting a page means rebuilding it (M6), so M2a moves each page whole
  to the area that holds its inputs.
- **Ctrl+1 to Ctrl+6 open the six areas:** the order of the rail, one key
  each, shown in the rail's tooltips. Settings and Help have the palette
  and F1.
- **The 10 icons added for the rail and top bar come from the same
  `lucide-static` 1.52.0 archive as the 35 bundled in M1,** checked
  against the archive's recorded SHA-256 and npm integrity:
  - chart-gantt, chart-line, circle-help, file-output, house;
  - panel-left-close, panel-left-open, redo-2, settings, undo-2.

- **The window opens on Home:** picking a template or a file is a new
  user's first move, as when the window opened on the Templates node.
- **Home's header has no buttons:** its page already has New blank
  scenario and Browse for a file...; New and Open are also `Ctrl+N`,
  `Ctrl+O` and palette commands.
- **The top bar's search is a button that opens the palette,** not a
  text field of its own: one palette, the one the shortcut opens.
- **The shortcut list shows a command's first key:** a standard key binds
  several on some platforms (Redo: Ctrl+Y, Ctrl+Shift+Z, ...); the first
  is the one to learn, as the old shortcuts dialog showed.
- **Settings > Keyboard is a `QTableWidget`,** as the dialog was; the
  `DataTable` component comes with the tables' rebuild (M6).
- **The saved layout's version is 2:** the toolbars are gone, so a layout
  saved by an earlier version is ignored once; the side panel starts
  where a new window has it.
- **Engine messages keep "Tools > Reference Data":** the engine does not
  change during the overhaul (`CLAUDE.md`). The palette lists that
  command under that name, so the message still leads to it; the
  troubleshooting page says where it now is.

## M2b Panels (2026-10-21)

The user: "start M2b here". M2b is the second half of M2 (above).

- **Problems is a bottom dock with a table:** a `QTableView` over
  `ProblemsModel`, as `CLAUDE.md` sets for tables. Its columns:
  - **Severity**: the word and an icon, colour never alone;
  - **ID**: the field path the message is about (`epoch_utc`,
    `dry_mass_kg`), "-" when it names none;
  - **Object**: Scenario, Propagation setup, the spacecraft's or ground
    station's name, Mission sequence or JSON;
  - **Message**: the text the Problems list showed before.

  The ID and the object come from `problem_location.locate`, which the
  jump to the field already used: nothing new is parsed. Errors come first,
  then the scenario's order; a heading sorts by its column.
- **No filter field or column menu on the Problems table yet:** it has
  four columns and a few rows. The `DataTable` component (M6) brings both
  to every table.
- **The counts:** on the panel's title ("Problems (2)"), always in the
  status bar ("1 error · 1 warning", "No problems") and in the top bar
  only while there are any; both buttons open the panel. Qt names a
  dock's toggle after its title, so the command is named "Problems" again
  after each count.
- **The run job and the chip are in the status bar,** before its other
  items, where §5.1 puts the jobs. The chip is hidden while the job is
  shown, because both said "Running 80 %"; afterwards it says how the run
  ended. One job at a time: Run is disabled while a run or a Monte Carlo
  batch goes, so the "job list" has one entry.
- **The status bar fits 1280 px during a run:**
  - the job's phase elides (80 to 320 px) and its bar is 72 px wide;
  - its button says **Cancel**, its key (Esc) in the tooltip, as
    `CLAUDE.md` puts shortcuts;
  - the Earth orientation and frames entries elide down to 48 px, their
    tooltips holding the whole text;
  - the job asks the status bar to lay it out again when its text grows
    (a `QStatusBar` does not notice on its own: the time was cut to
    "0:02 elap" in the harness's run-in-progress screen).

  Measured at 1280 px with the longest data text ("12 of 14 need
  attention") and "80 % · 0:40 elapsed · about 0:09 left", with the theme
  applied: the status bar's minimum is 1207 px. With the theme applied it
  was 1266 px before Cancel and the bar shrank, which left 14 px.
  The test measures with the theme applied: Qt's default point-size font
  measured twice as wide on the Windows runner (192 dpi, an 800 px screen),
  which says nothing about the app's own fonts.
- **The inspector is two docks, Inspector over Explain,** not one dock
  with tabs. Each one is shown, hidden and sized on its own. Explain leaves
  for Scenario › Overview in M4.
- **`Ctrl+I` and `Ctrl+J` toggle the Inspector and Problems panels,** as
  §5.2 sets; "Side Panel" is gone, its keyword finds the Inspector. A
  panel shown from the keyboard takes the focus, so its table is usable at
  once. Explain has its command and its palette entry, with no shortcut.
- **The validation strip under the editor stays until M4.** §5.2 removes
  it once Problems holds what it says. It is part of the scenario
  editor, which M4 rebuilds, and seven tests read it. Problems already
  lists the same problems.
- **The layout is kept per scenario file:** `layout.ini` keeps one group
  per file. The group is named by a SHA-256 of the file's resolved path,
  and its `path` entry names the file for whoever reads it. Each group
  holds:
  - the dock state (visibility and sizes);
  - whether the rail is collapsed;
  - the six main splitters (scenario tree, mission sequence, plots and
    their side, timeline, compare).

  It is saved when another scenario opens, on Save and on close. A file
  without a layout of its own keeps the layout shown: a new project starts
  from the last one. The window-wide layout is kept as before, for a new
  window.
- **The saved layout's version is 3:** the docks changed (Problems at the
  bottom, Explain its own dock), so a layout saved by M2a is ignored once.
- **The keyboard walk:**
  - Tab goes round the whole window and comes back to where it started
    (47 stops with Home shown).
  - The arrow keys move along the rail's areas, as in any group of
    exclusive buttons, and Space or Enter opens one.
  - The Problems table no longer holds Tab (`setTabKeyNavigation(False)`);
    the walk found that trap.
  - The Tab order follows the order the widgets were made in: rail,
    status bar, panels, top bar, area. A deliberate order is M9's
    accessibility pass.
- **The theme switch is not under 100 ms; the criterion moves to M9.**
  Measured on this branch, offscreen, on template 23:
  - 0.42–0.47 s on a new window (1508 widgets);
  - 0.73–0.84 s once every page has been visited (2529 widgets);
  - M1 measured 0.51–0.55 s and 2.4 s.

  Nearly all of it is Qt's `setStyleSheet`: 141 ms to clear the sheet,
  245 ms to set it. Setting it without clearing first takes 2.8–3.0 s.
  The Python redraw handlers take 1 ms. Under 100 ms needs fewer widgets
  alive: pages built when first shown, which the rebuilds of M4–M8 bring.
  M9's performance pass holds the criterion, with these values.

## A mission from scratch (2026-10-21)

The user: "why can't a user create a new blank project completely from
scratch in the tool? that is like one of the most important features to
have." It could (File > New Scenario), but nothing pointed to it and an
empty scenario showed only a red "needs at least one spacecraft". The
user's decision on the mode: "start with orbit only first, but it should
be clear to the user, that this is not the only option. The user shall
understand the full capabilities of the tool and shall not feel
completely lost."

- **A blank scenario starts in Orbit only,** at start-up and after File >
  New. The schema's default stays `full_attitude`: files without the
  field open as before.
- **"Start from scratch" is the Templates page's first choice:** the
  page where the app opens, and where people look for a way in.
- **The guide is on the Scenario page,** between the epoch and the
  description: a blank scenario's description is empty, and the guide is
  what to read there. It is open for a scenario without spacecraft and
  folded for one opened from a file, which keeps a template's
  description in view.
- **State as text in a status pill** (*Needed* caution, *Done* normal,
  *Optional* off): colour never alone (design rule 1).
- **"There is more" lists areas, not every option,** each with a button
  to where it is set, so the list stays short and each line leads
  somewhere.

## macOS removed (2026-10-21)

The user's decision: "please remove macOS completely and entirely, nobody
needs it." SpaceMissionStudio supports Linux and Windows only.

- **CI and releases:** the macOS row of the `platforms` job and the
  release workflow's macOS job are gone. Basilisk's own workflows lost
  macOS too (the user's decisions of 2026-10-21, after #92's checks
  waited on macOS runners that never came: "remove the macOS jobs from
  the framework workflow too", then "I dont want any macOS workflows
  left whatsoever"). The "Pull Request" workflow has no macOS
  build-and-test jobs; its `docs` job, the merge workflow's docs
  deployment and the canary build run on `ubuntu-24.04`, the docs action
  installing Doxygen and Graphviz with apt instead of Homebrew; the
  nightly, optional and publishing wheel workflows build no macOS
  wheels. That drops the framework's only Python 3.9 (minimum version)
  test run on pull requests; Linux and Windows test 3.14. The framework's
  own documentation, which describes macOS installs and the PyPI wheels,
  is unchanged.
- **The app:** the macOS-only code is gone: Vizard's macOS download and
  its `.app` bundle handling. Code that is plain POSIX (the Unix-domain
  SIL socket, skipping hidden files such as `.DS_Store` in a batch
  folder) stays: Linux uses it, and it changes no result. The exported
  flight-software sources keep "Linux, macOS" for their Unix-domain
  socket: they describe where the exported C code can run, and the export
  stays byte-identical.
- **Tests:** the two tests of the removed `.app` bundle handling now
  check that such a path is started as given, and the download test that
  there is no macOS download (`docs/ui/TEST_CHANGES.md`). No test is
  skipped or removed. No test had a macOS-only branch otherwise; comments
  that explain a test's set-up by what the macOS CI runner did keep that
  history, since the set-up still guards the other platforms.
- **Documents:** current statements of platform support say Linux and
  Windows. Dated records (HISTORY, earlier CHANGELOG entries, the audits
  and the SRelD's past known problems) keep what was true then.

## Self-contained installers (unreleased)

The user's request (2026-10-20), after the 1.1.0 setup program stopped
with "SpaceMissionStudio needs Python 3.11 or later, which was not found
on this system": make the installers self-contained, Linux too. macOS
has no installer, so it keeps the install script.

- **One private Python for both installers** (`packaging/bundle_python.py`):
  python-build-standalone's relocatable CPython, the same source on Linux
  and Windows, pinned by release and SHA-256 (the digests published for
  release 20261013). Python's own Windows "embeddable" package has no pip
  and no Linux counterpart.
- **CPython 3.11** (3.11.17): the version CI tests the app with.
- **Built, not installed, with the network:** Basilisk, the wheel and
  every package are installed into it when the installer is built, with
  `constraints.txt`; the installers only copy files. `SPACEMISSIONSTUDIO_RUNTIME.json`
  records what went in.
- **The support data goes into `site-packages/supportData`,** the folder
  Basilisk's own `dataFetcher.find_local_support_data()` reads before its
  download cache. No environment variable, no launcher wrapper, and no
  change to Basilisk (a data folder next to it, read by its own lookup).
  A file a user later downloads still goes to the user's cache.
- **The Earth orientation files** go into `earth_orientation.SYSTEM_DIR`
  (the install-wide folder), as the old installers fetched them, but at
  build time: they are as current as the build. A user's own newer files
  (`DEFAULT_DIR`) take precedence, as before. Their manifest's absolute
  paths are rewritten for the install folder (at build time for the
  `.deb`, by the setup program on Windows), with no engine change.
- **No downloads while installing:** `postinst` only removes the venv of
  packages up to 1.1.0; the setup program's Python check is gone.
- **The `.deb` is `amd64`,** with every file a package file (launcher and
  icon included), and `Depends` on the desktop libraries Qt loads and
  glibc 2.34 (PySide6 6.11 wheels are `manylinux_2_34`).
- **Bytecode names the installed files:** compiled for
  `/opt/spacemissionstudio/python` when the `.deb` is built, and for the
  chosen folder when the Windows setup runs (that folder is not known when
  it is built); hash-based and unchecked, so file times do not matter.
- **xz for the `.deb`, LZMA2 for the setup program:** the smallest files
  for a 1.6 GB install.
- **`install.sh` and `install.ps1` stay as they are** (a venv with the
  computer's Python): they install from a checkout and cover macOS.

## M1 Foundation (released in 1.1.0)

### Release

- **M1 ships in 1.1.0.** The user chose on 2026-10-20 to publish 1.1.0
  from `develop`, which holds M1, instead of from the commit before it
  (`b064bb9ef`). The version stays 1.1.0; the overhaul's later milestones
  and the version 1.2.0 (plan §9, Q7) follow.

### Carbon removed

- **The IBM Carbon theme (g10 and g100 colours, IBM Plex, square
  corners, filled fields with a bottom rule) is replaced** by the brief's
  token table, Inter and JetBrains Mono, Lucide icons, 6 and 8 px radii
  and 1 px borders. The brief requires it. `gui/theme.py` became the
  package `gui/theme/`. Carbon stays in git history, in HISTORY
  and in the CHANGELOG entry of 1.0.0.
- **The older role names stay readable** (`theme.PALETTE["text_muted"]`
  and the rest), each mapped to one token (`theme/state.py`, `ROLES`):
  40 modules read them, and a rename alongside a restyle would hide real
  changes in noise. New code uses token names.

### Tokens

- **The brief's table is used verbatim** (`tokens.BRIEF`); no suite theme
  package exists yet (plan §9, Q6).
- **Changed to pass WCAG 2.2 AA** (`tokens.ADJUSTED`). OKLab lightness was
  moved in 0.005 steps until the value passed on every background it is
  drawn on (canvas, surface, raised, hover, selected); hue and chroma were
  kept:
  - light `text.muted` `#7C838D` -> `#666D77`: 3.83:1 on `bg.surface`;
  - dark `text.muted` `#7A828E` -> `#868E9A`: 4.12:1 on `bg.hover` and
    3.86:1 on `bg.selected`;
  - light status colours, which the brief gives for a dark background
    (2.5-1.6:1 on white), are split into an icon value (3:1) and a text
    value (4.5:1). Icons: `status.critical` `#FF4D4F` (kept, 3.25:1),
    `status.serious` `#E16F18`, `status.caution` `#BE8400`,
    `status.normal` `#00A45D`, `status.standby` `#3496D5`. Text:
    `status.critical.text` `#DA2331`, `status.serious.text` `#BD4E00`,
    `status.caution.text` `#9E6500`, `status.normal.text` `#00833F`,
    `status.standby.text` `#0077B4`;
  - the dark theme's status colours pass as the brief gives them, as icon
    and as text.
- **Text on the accent** is white in the light theme and the dark canvas
  (`#0B0D10`) in the dark theme: white on `#4C8DFF` is 3.2:1.
- **Derived tokens:** `bg.selected` is the brief's accent at 10 % (light)
  or 16 % (dark) over the surface; status and diff tints are the status
  colour at 7 % (light) or 16 % (dark), the most that keeps the status
  text on its own tint at 4.5:1 (at 10 % light it was 4.36-4.44:1); text
  selection is the accent at 22 % / 34 %; disabled text is
  `text.primary` at 38 % (WCAG exempts inactive controls); the accent's
  hover and pressed steps mix 10 % and 20 % of black (light) or white
  (dark).
- **Borders stay low-contrast** (`border.strong` on the surface is 1.5:1):
  the brief asks for "1 px low-contrast borders"; an input is also told
  apart by its fill, its hover edge and its 2 px focus ring, and
  `tests/gui/test_input_borders.py` keeps every input's edge visible.
- **Tooltips are raised surfaces** (`bg.raised`, a 1 px border), not
  inverse: one floating-element style for menus, popovers and tooltips.
- **No shadows:** Qt style sheets cannot draw them; floating elements get
  a 1 px border instead. A `QGraphicsDropShadowEffect` is left to the
  components that need one (M2).

### Chart palette

- **Eight colours per theme, searched in OKLCH and checked with the
  data-visualisation palette validator** (`theme/palettes.py`). A first
  search that also kept the hue bands of every status colour out found no
  eight-colour set; the rule became "at least Delta E 8 from every status
  colour (icon and text values) and from the accent", which keeps a
  series from reading as a status while leaving enough hues.
  - light on `#FFFFFF`: `#AE59B4 #8A3600 #6C25A4 #236400 #00A596 #5283FE
    #B80040 #005F93`; worst adjacent CVD Delta E 14.3 (protan), worst
    adjacent normal-vision Delta E 20.8, all >= 3:1;
  - dark on `#111418`: `#CA4ED3 #B36C0D #8B63B6 #458604 #00A794 #3163F1
    #DA185B #007CB1`; worst adjacent CVD Delta E 14.8 (deutan),
    normal-vision 15.2, all >= 3:1;
  - with all 28 pairs side by side (scatter of eight groups) two pairs
    fall below the floors in each theme: every chart keeps a legend.
- **The time cursor is drawn in the accent**, not in the error red: it is
  a selection, and red is reserved for critical.

### Type and icons

- **Fonts as TTF, not WOFF2:** Qt reads TrueType everywhere; its WOFF2
  support depends on the build.
- **Weights bundled: Inter 400/500/600, JetBrains Mono 400/500;** no
  italics (none is used).
- **Tabular figures:** `theme.numeric_font()` uses Inter with `tnum` on
  Qt 6.7+, JetBrains Mono on older Qt (`pyproject.toml` allows 6.6).
- **Lucide, only the 35 icons used.** The app's names map to Lucide's
  (`theme/icons.py`): Run `play` in the accent, Cancel `circle-stop` in
  critical, Monte Carlo `dices`, Check kernels `file-check`, Vizard
  settings `sliders-horizontal`, Launch Vizard `monitor-play`, 3D model
  `box`; steps `orbit`, `rocket`, `route`, `variable`, `git-branch`,
  `repeat`, `file-text`, `code`.
- **Icons are tinted when drawn** by a `QIconEngine` that reads the token
  each paint, so a live theme change needs no icon to be set again.

### Style sheet

- **One application style sheet, no per-widget sheets.** A widget picks
  its look with dynamic properties (`role`, `tone`, `badge`, `variant`,
  `series`; `theme.set_role`). The 106 `setStyleSheet` calls outside the
  theme became properties; one is left, the swatch of a colour the user
  picked (`palettes.swatch_style`).
- **No `QWidget { ... }` rule:** text colour, selection and the font come
  from the application palette and font. The rule made Qt restyle every
  widget on a switch for nothing (45 ms of the switch).
- **Group boxes are headings, not frames** ("no boxes inside boxes").
- **Rich text** in labels takes its inline CSS from `theme/richtext.py`
  and is rebuilt on a theme change where it holds colours.
- **Item colours** (list, tree and table rows) are set through
  `theme/items.py`, which records the token on the item so `retint`
  recolours a view after a switch.
- **The hard-coded-style test covers strings and font calls:** colours,
  CSS sizes and weights, font families and style sheets outside
  `gui/theme/`. Integer layout margins in code are out of its scope until
  M2-M8 rebuild the screens from components.

### Live theme switch

- **`apply_theme` clears the sheet, then sets the new one:** measured on
  the main window (1,216 widgets), clearing then setting took 210-290 ms
  where swapping one sheet for the other took about 1,000 ms; Qt builds
  the new rules once instead of diffing every widget against the old.
- **Measured** (same machine, same day, the code before M1 (`b064bb9ef`) and this change run in
  turn; `scripts/measure_ui_baseline.py` and a paired script):
  - a fresh main window with template 19 open (1,360 widgets): 0.51-0.55 s,
    against 1.31-1.44 s before M1;
  - in the baseline script's sequence (every page visited, a run done,
    the spacecraft dialog opened): 2.4 s, against 6.1-6.5 s before M1 (the
    plan's 3.8-4.0 s was measured on a faster day).
- **The brief's 100 ms is not met in M1.** The time is Qt re-polishing
  every widget, and most of them are hidden (1,049 of the 1,216 of a new
  window: pages and tabs not shown). M2 hosts the screens in lazily
  created areas; the criterion is carried to M2 with these values.
- **Tried and not taken:** setting the sheet on the main window instead of
  the application halves the switch (200-250 ms on the fresh window) but
  leaves parentless dialogs and tooltips unstyled; revisited in M2.
- **`theme.on_change` holds callbacks weakly** and skips a widget Qt has
  already deleted: a closed dialog's redraw would otherwise raise on its
  deleted children at the next switch (found by the full test suite).
- **Plots redraw after the switch returns** (a zero-time timer), so the
  switch does not wait for the web pages to reload.
- **System follows the desktop live:** with View > Theme > System, a
  change of the platform's colour scheme applies at once.

### Dependencies and outputs

- **No new run-time dependency.** Inter, JetBrains Mono and Lucide are
  files (`docs/THIRD_PARTY_ASSETS.md`). PySide6 and plotly keep their
  ranges (`>=6.6`, `>=5.0`): nothing new depends on a newer version, and
  pinning them is a release decision, not a restyle one.
- **plotly.js is not copied** into the package: the copy in
  `plotly/package_data/` is already bundled with a GUI dependency, offline
  (a second copy would add 4.8 MB).
- **Data exports are unchanged; plot images take the new look.** A PNG or
  SVG of a plot has always taken the theme in use; its data, axes and
  units are the same.

### Records

- **Test changes** are listed in `docs/ui/TEST_CHANGES.md` (plan §9, Q1).
- **`docs/DESIGN.md` is rewritten** for the new system; the Carbon version
  stays in git history.
- **`CLAUDE.md`** (in `SpaceMissionStudio/`) holds the design rules every
  later session follows.

## Decisions from the plan (§10)

- **plotly.js** comes from the plotly package (above).
- **No new runtime dependencies** (above); the licence report is
  `docs/THIRD_PARTY_ASSETS.md`.
- **Status colours:** the brief's Astro values, tuned only where the
  contrast test fails, each tuned value listed above.
- **Categorical plot palette:** 8 hues, validated for CVD separation on
  both surfaces, distinct from the status hues (above).
- **Recent scenarios** (M3) are stored in `QSettings` (organisation
  "AVSLab"): not a file-format change.
- **Run-start and run-end log records** (M5) are emitted by the GUI's run
  controller, not the engine.
- **`docs/DESIGN.md`** is rewritten in M1 (above).

## Legal groundwork, milestone M1 (2026-11-09)

The plan is `docs/legal/PHASE1_PLAN.md`. Not legal advice; a lawyer reviews
the risk register.

- **One tool decides what ships.** `packaging/legal/licences.py` lists every
  file of a package, assigns each to a component with a known licence and fails
  on the rest. Why: the older SBOM (`bundle_python.py`) records where packages
  came from but not which licence owns which file, nor whether a licence text
  travels with it.
- **An unclear licence is left out, not guessed.** A component the tool cannot
  read stays unknown and the gate fails until a person writes the entry with
  its evidence. Why: the project must not redistribute on an assumption.
- **Data with an open redistribution right warns; data a provider restricts
  fails.** `restricted` has no waiver without a recorded decision. Why: the ITU
  file is bundled today and ITU says reproduction needs written permission
  (`docs/legal/DATA_TERMS.md`, D1); the next Linux installer build stops until
  you decide.
- **The python-build-standalone library texts are vendored** in
  `packaging/legal/texts/` (with the source archive's SHA-256), and the bundle
  copies them to `licenses/`. Why: the `install_only` archive carries no text
  for OpenSSL, SQLite, libffi, Tcl/Tk and the others it links.
- **Windows ran the gate in `warn` mode** until a full Windows build listed
  its unclaimed files. Why: only the Linux build could be read here. Since
  2026-11-10 it fails like Linux: the first full Windows build with the
  Windows components reported only the warnings for the open data rights.
- **Wheel notices are generated and committed** (`THIRD_PARTY_NOTICES`),
  and CI fails when they are stale. Why: a hand-kept list drifts.
- **`tool.setuptools.license-files` is used** (deprecated in favour of
  `project.license-files`, which needs an SPDX `license` string). Why: the SPDX
  string arrives with the licence change in M2.

## Legal groundwork, milestone M2: the licence change (2026-11-10)

The owner asked to proceed on the recommended answers of
`docs/legal/PHASE1_PLAN.md` §12. Not legal advice; a lawyer reviews it.

- **EUPL-1.2 from the release after 2.6.0** (the brief's choice). 1.0.0 to
  2.6.0 stay ISC. Why: the brief; written for EU law, official in German.
- **Copyright line: "Copyright (c) 2026 0h3xn4"** (the GitHub account that
  owns the repository). Assumed, not given: the plan made no recommendation.
  Why: it names the licensor without publishing a real name; one constant
  (`spacemissionstudio/legal.py` and the header text) changes it.
- **The commit author `ohexna` is taken to be the owner** (plan Q3); the
  only other author is Claude.
- **Next version 2.7.0, in a release of its own** (plan Q1, recommended:
  its own minor release). Nothing is published by this change; the release
  waits for the decision on the ITU file (`docs/legal/DATA_TERMS.md` D1).
- **`LICENSE` is the SPDX list's text byte for byte**
  (SHA-256 `57fb42fb...68a4b4`); it equals the Commission's English text
  (`EUPL v1_2 EN(1).txt`, SHA-256 `b1e85ac8...24dd47d`) after removing the
  byte-order mark, CR line ends and trailing spaces. Why: plan Q4.
- **`LICENSE.de` is the Commission's German text, whitespace-normalised**
  (as published: SHA-256 `208705be...fe0dce`, BOM and CRLF; stored:
  `849b8890...65b5d67f`). Why: no other official source; the repository's
  whitespace hooks reject BOM-free CRLF text with trailing spaces, as for the
  JetBrains Mono licence before.
- **The header names only the file's own licence.** Its first version also
  said that earlier releases and Basilisk are ISC; ScanCode then read every
  file as "EUPL-1.2 AND ISC". Why: a scanner or a distribution must read
  one licence per file; the history is in README, CHANGELOG and the About box.
- **The new header keeps the old header's 16 lines.** Why: about 2,100
  `file.py:line` references in the audit and history records stay valid.
  The 65 files that had no header got one at the top.
- **No file was copied or adapted from Basilisk** (line-similarity scan of
  796 files against 2,442 upstream files; at most 13 shared lines, all
  Basilisk API calls; no file moved in from upstream). The flight-software
  source zip stays Basilisk's, unchanged, under ISC.
- **The flight-software templates keep their ISC notice.** Why: they are the
  text of the generated C project, and a generated output may not change
  without the owner's approval (`docs/legal/OBLIGATIONS.md`, proposal P1).
- **PEP 639 metadata, no licence classifier.** Why: setuptools 77 and later
  refuse a licence classifier beside an SPDX `license`; the build now
  needs setuptools 77.0.3 or later.
- **Help > Third-Party Licences** shows `LICENSE`, `LICENSE.de` and the
  notices found in the installation (`spacemissionstudio/legal.py`); a
  window of its own, like the manual. Why: the brief (1.1, notices in the
  product).

## Legal groundwork: the owner's answers of 2026-11-10

The owner answered the open questions of `docs/legal/PHASE1_PLAN.md`.
Not legal advice; the owner decided not to involve a lawyer.

- **Q1: `SECURITY.md` at the repository root and a sign-off line in the
  root pull-request template: yes.** Why: GitHub shows a security policy
  only at the root, in `.github/` or in `docs/`. Done in milestone M4.
- **Q2 (D1): the ITU-R P.676-13 data file is not bundled, and ITU is not
  contacted.** Why: ITU allows reproduction only with written permission,
  and the owner wants nothing to do with it. The app's own download command
  stays (it fetches from ITU on the user's request; no template uses it).
- **Q3 (D9): the installers leave out the GPL-only Qt modules, Tcl/Tk and
  `_dbm`** (`bundle_python.prune_unused`). Why: the app uses none of them;
  fewer licences to carry.
- **Q4 (D8): every release carries the Qt and PySide6 source archives**
  (`packaging/legal/qt-sources.json`). Why: the safest way to meet the
  LGPL-3.0's source obligation.
- **Q5 (P1): the generated C project keeps its notice unchanged.** Why: no
  lawyer; a generated output does not change without the owner, and the
  owner chose to leave it.
- **Q6: no copyright is claimed; the files name the licensor.** The line
  "Copyright (c) 2026 0h3xn4" (M2) is replaced by "Licensor: 0h3xn4
  (https://github.com/0h3xn4)" in every header, the About box and the `.deb`
  copyright file. Why: the code was written mainly by an AI model, and the
  owner does not claim copyright in it. German law protects only "persönliche
  geistige Schöpfungen" (§ 2 (2) UrhG) and computer programs that are "das
  Ergebnis der eigenen geistigen Schöpfung ihres Urhebers" (§ 69a (3) UrhG;
  both read on gesetze-im-internet.de, 2026-11-10); whether that test is met
  was not assessed. "Licensor" is the EUPL's own term (Article 1) for the
  person who distributes the Work under it; the EUPL's disclaimers
  (Articles 7 and 8) travel with the code either way.
- **Q7: no website and no hosting.** Why: everything must stay free of cost.
  Milestones M5 (website) and M6 (hosting) are cancelled; the GitHub
  repository is the project's only public page. No website Impressum or
  privacy text is needed.
- **No lawyer.** Items the plan marked "for a lawyer" stay open in the risk
  register, marked as the owner's accepted risk.

## Legal groundwork M4: the risk register (2026-11-10)

`docs/legal/RISK_REGISTER.md` holds R1 to R13 with facts, what was done and
what is open. Not legal advice.

- **Sign-off is checked for pull requests from forks only**
  (`spacemissionstudio-signoff.yml`, `scripts/check_signoff.py`). Why: a
  sign-off is a personal statement under the Developer's Certificate of
  Origin; the maintainer's own commits are written with an AI tool, and
  nobody may sign off on the maintainer's behalf.
- **Release files get a signed build provenance** (`actions/attest@v4`,
  Sigstore). Why: free for a public repository, and anyone can verify it;
  Windows code signing costs money, so it is only proposed (Q7).
- **Licence matching is case-sensitive on every system.** Why: on Windows
  `fnmatch` ignores case, and Tcl's pattern `lib/thread*` claimed
  `Lib/threading.py`.
- **The Microsoft C++ runtime in the Windows Python is a component of its
  own** (D10). Its redistribution status was open until the owner decided
  D10 on 2026-11-10: rely on CPython's statement in its Windows
  `LICENSE.txt`, so the status is `verified`. Why: that statement is the
  only text read, and relying on it was the owner's call.
- **`libtommath.dll` is pruned with Tcl/Tk.** Why: Tcl is its only user;
  this is within the owner's decision Q3 (D9).
- **Non-affiliation (W1) and no warranty (W2) are stated; the flight-use
  sentence (W3) is not** (`docs/legal/WORDING_DRAFTS.md`). W1 and W2 are in
  both READMEs and the manual's introduction, and W2 in the About box. Why:
  the owner approved W1 and W2 and rejected W3 on 2026-11-10; the brief
  allows legal text only with the owner's approval.
- **The author name and import paths in scenario files stay as they are**
  (proposal P2 in the register, declined by the owner on 2026-11-10). Why:
  changing them changes scenario files and CLI output.

## ECSS wording out of the compliance lists (2026-11-11)

- **Decision:** the ECSS requirement lists and the compliance matrix
  point to each requirement (standard, clause, ID) instead of quoting it.
  **Why:** "No ECSS document may be reproduced in any form without the
  explicit consent of ESA" (DATA_TERMS D3); a reference keeps the audit
  usable without a reproduction, and asking ESA was not wanted.
- **Not done:** clause titles (they would come from the standards, which
  are not in the repository); the CCSDS list (its terms are unread, D5);
  the wording in earlier commits (removing it rewrites history, the
  owner's call).

## A menu bar again, and readable drop-down lists (2026-11-12)

- **Decision:** the window has a menu bar (File, Edit, View, Go, Run,
  Tools, Help) built from the action registry (`gui/menu_bar.py`), beside
  the rail, the top bar and the command palette. **Why:** the owner asked
  for one ("I am missing something like this"); M2a removed it
  (2026-10-21) for the palette, which stays. Built from the registry, a
  menu item cannot disagree with its shortcut or buttons, and a test
  keeps every command in exactly one menu.
- **Decision:** View > Menu Bar can hide it, kept with the window's
  layout; Reset Layout shows it. **Why:** the shell without it was a
  deliberate design; those who liked it keep it at no cost.
- **Decision:** Edit > Settings... (`Ctrl+,`) is a new command. **Why:**
  the place people look for settings in a menu bar, and the common key.
- **Decision:** every combo box's list opens below the field
  (`combobox-popup: 0`), 12 rows high with a scroll bar, rows drawn by
  `QStyledItemDelegate` so the style sheet's row height, padding and
  hover apply, and a "Type to filter" field from 12 entries
  (`gui/theme/combo.py`, applied by the application style `AppStyle` as
  Qt polishes each combo box). **Why:** the owner found the lists
  "cramped and unintuitive, particularly with many entries"; measured,
  a 60-entry list covered the screen over its field with 24 px rows and
  arrow scrolling. One place fixes all 93 combo boxes, with no change to
  their values or signals; an editable combo box with a completer was
  not chosen, as it would let any text be typed.
- **Decision:** an optional reference file fetched only on request (the
  Eros files, ITU-R P.676-13) is "not downloaded" when absent, not
  "missing", and does not count as needing attention. **Why:** every new
  install showed three red "missing" files and "3 need attention" for
  data nothing used.

## Values as tables, and dialogs that fit their text (2026-11-12)

- **Decision:** several values of one thing are shown as a
  `ValueSheet` (name, value right-aligned in tabular figures, unit) or a
  `ValueTable`, never as a sentence of numbers; a design rule in
  `CLAUDE.md` and `docs/DESIGN.md`. **Why:** the owner: "raw text is
  visually always like noise. make the information clear and
  understandable. that applies to everything in the tool." First the 3D
  model editor's mass and surface summaries and the orbit-type switch;
  the rest by an audit of every screen, screen by screen.
- **Decision:** the command line keeps its plain lines
  (`model3d.principal_summary`); the editor's summary gives the same
  text for copying. **Why:** a terminal has no table widget, and scripts
  read those lines.
- **Decision:** every `QDialog` gets a minimum height equal to what its
  layout needs at its current width, on show and on each width change
  (`gui/theme/dialogs.py`, from `AppStyle.polish`). **Why:** Qt does not
  size a top-level window by its wrapped labels' height for width; the
  orbit-type switch showed one line of each paragraph and clipped
  buttons on the owner's desktop. One place fixes every dialog.

## Calm by default (2026-11-12)

- **Decision:** Home shows Home: cards with title and kind (the orbit
  and description in the details of the card picked, folded past the
  summary), card buttons on the card picked or pointed at, the side
  panels put aside and restored on leaving. **Why:** the owner: "a user
  easily could get overwhelmed by the amount of information that is
  dumped on them", with a screenshot of Home with every panel open.
- **Decision:** the status bar shows the problem count and only the
  entries that need attention; View > Status Bar: All Details, kept with
  the layout, shows them all. **Why:** the same; versions, frames and an
  "all OK" are reference, not news.
- **Decision:** repeated per-spacecraft notes are grouped, the names in
  the tooltip; the relative orbital elements are named by their effect.
  **Why:** the owner's screenshots: one note fourteen times; "the units
  make no sense here".

## Notes as lists, the remaining values as sheets (2026-11-15)

- **Decision:** notes, warnings and findings are a `NoteList`: one row
  each behind a Lucide icon (info, triangle, circle), the text wrapped
  beside it; past four, "Show n more". The text keeps the body colour,
  and the icon carries the status. **Why:** the owner: raw text "is
  visually always like noise"; the dash-led blocks on the budget, design
  checks, lifetime, model analyses and re-entry pages, and the "⚠" lines
  in Results and the scenario editor, were the remaining raw text.
- **Decision:** the sentences of numbers left are sheets: the budget's
  totals and inputs, the mass sum and launcher verdict (under their
  tables, not under every group), momentum per axis, casualty areas and
  risk, the spacecraft's model summary, products of inertia, and
  Settings' hosts. A text value in a sheet ("Fairing A") keeps the body
  font; numbers keep tabular figures. **Why:** the same, and CLAUDE.md
  design rule 4.
- **Decision:** a widget a component shows or hides is given its parent
  when it is made, never after. **Why:** a title label shown before its
  layout took it was a window for a moment and took the main window's
  activation (its shortcuts went dead in `test_panels.py`).

## Publishing a release automatically (2026-11-15)

- **Decision:** the tag workflow and the release workflow take a
  `publish` input (default off). With it, the release workflow
  publishes the release as its last step, only after every file was
  built, installed and run, checked against its checksum and attached,
  and only if as many files are attached as were built. **Why:** the
  owner, preparing 2.8.0: "Afterwards I want you to automatically
  publish." The draft-first default stays for a run started without
  it, and a push of a tag by hand (2.6.0 and 2.7.0 were public without
  files when published early, `releasing.md`).

## System Budget Studio becomes a feature (2026-11-17)

The plan, its overlap table and its phases are in
[`developer/system-budget-merge-design.md`](developer/system-budget-merge-design.md).

- **Decision:** one tool. System Budget Studio
  (`0h3xn4/system-budget-studio`) becomes a feature of SpaceMissionStudio,
  in the phases of the plan. **Why:** the owner; one set of inputs, and
  the budgets get SpaceMissionStudio's propagation (a tester of System
  Budget Studio 2.11.0 asked for high-precision propagation).
- **Decision:** SpaceMissionStudio wins every overlap. Where both tools
  compute the same thing, SpaceMissionStudio's model stays and System
  Budget Studio's is not ported; what moves is re-implemented on
  SpaceMissionStudio's data structures, with System Budget Studio's code,
  tests and reference cases as its specification. **Why:** the owner.
- **Decision:** the moved code is EUPL-1.2, with the usual SPDX header.
  It is re-implemented, not copied, so no Apache-2.0 notice is needed; a
  file ever copied as it is keeps its Apache-2.0 header and is listed in
  `THIRD_PARTY_NOTICES`. System Budget Studio's released versions stay
  Apache-2.0. **Why:** the owner holds the copyright of both tools and
  decided it (Q1).
- **Decision:** a one-way import opens System Budget Studio projects
  (phase 6); nothing is written back. **Why:** the owner.
- **Decision:** System Budget Studio is frozen at 2.15.1: fixes only
  until the merge is done, then a last release that points here and an
  archived repository. **Why:** the owner.
- **Decision:** CLAUDE.md's hard rule "UI only during the overhaul" is
  replaced: engine and format changes are allowed with a schema
  migration, unchanged golden files for the existing templates (unless
  the owner decides otherwise) and a decisions entry. **Why:** the owner
  (Q4); the merge needs schema version 5 and engine changes, and the
  thermal and operations features were already built as exceptions.
- **Decision:** the other answers of the plan (Q2, Q3, Q5, Q6, Q7): PDF,
  XLSX and DOCX reports are decided in phase 5; a Budgets area in the
  navigation rail; the "TBD" placeholder in the `budgets` section only;
  budget problems may show values; phase 1 builds on the IDM-CIC
  import's power modes. **Why:** the owner, 2026-11-17 (plan, section 7).

## System Budget Studio merge, phase 1: the core (2026-11-17)

- **Decision:** the choices of phase 1 are in the feature's own decisions
  file, [`developer/system-budget-decisions.md`](developer/system-budget-decisions.md):
  B-01 to B-14 from the design note, and B-15 to B-17 made while building
  it (a read-only place for the section in the spacecraft editor, items
  without power modes in the mass budget only, a placeholder with an
  empty source). **Why:** CLAUDE.md asks for a decisions entry with each
  engine or format change; the feature keeps its own, as thermal and
  operations do.

## Desktop integration: the icon plate and AppStream (2026-11-17)

- **Decision:** the app icon keeps its glyph and colours and gets a
  rounded-square plate `#0F172A` with a rim `#94A3B8` (2/64 of the size,
  1 px at least), as `docs/developer/windows-views-design.md` section 5
  says. The panel grid lines take the plate colour; the antenna takes the
  panel blue, because the old dark blue has 1.6 : 1 on the plate. **Why:**
  the design; the rim gives 5.15 : 1 or more on the dark panels, the plate
  15.0 : 1 or more on the light panels, the panels 3.45 : 1 and the body
  9.18 : 1 on the plate.
- **Decision:** the glyph's turned outline fills 85 % of the width inside
  the rim, and 95 % at 32 px and below. **Why:** the design says "about
  80 %"; rendered side by side from 0.80 to 1.0, 85 % keeps the large icon
  calm and 95 % keeps the small sizes readable.
- **Decision:** the Linux icons are rendered when the package is built
  (`icons.write_icon_theme`: PNGs of 16 to 512 px and an SVG through
  `QSvgGenerator`), as the 256 px icon was before; the Windows `.ico` is
  generated by `packaging/make_ico.py` and committed. **Why:** the `.deb`
  build has the bundled Python with PySide6 at hand; the Windows setup is
  built from the repository with Inno Setup. A test fails when the `.ico`
  and the icon differ.
- **Decision:** the `.ico` holds 32-bit bitmaps with alpha from 16 to
  128 px and the PNG at 256 px, not PNG entries at every size. **Why:**
  this is the layout every Windows version since Vista reads and that
  resource editors such as Inno Setup expect; the design's "PNG entries"
  would also work on current Windows, but with less margin.
- **Decision:** the AppStream component id is
  `io.github._0h3xn4.SpaceMissionStudio` (the owner's answer Q4); the
  desktop id stays `spacemissionstudio.desktop` and is the `launchable`.
  appstreamcli's only remark is the pedantic one about capital letters in
  the id, which Flathub's own ids have too. **Why:** the owner; dock
  favourites store the desktop id.
- **Decision:** the screenshots are four that `docs/images/` already has
  (Home, the Scenario form, the Timeline, a Monte Carlo batch, all
  1600 x 900), not new 1280 x 720 captures in `docs/images/appstream/`.
  **Why:** the task asked for existing images; they are the manual's
  screenshots, so they stay current, and a test checks their names and
  sizes.
- **Decision:** the metadata lists the 5 newest releases, each with the
  first paragraph of its CHANGELOG summary as plain text and a link to
  its release page. **Why:** the design; software centres show the newest
  few, and the first paragraph says what a release is for.
- **Decision:** the metadata file is CC0-1.0, with its own stanza in the
  Debian copyright file. **Why:** AppStream asks for a permissive
  metadata licence; the rest of the package keeps its own.

## Dialogs fit the screen (UI audit B1, 2026-11-17)

- **Decision:** `gui/theme/dialogs.py` limits a dialog's minimum height
  to the screen's available height less 64 px (`TITLE_BAR_ROOM`, two
  32 px steps of the grid), and shrinks a dialog that opens taller. Only
  the layout's own minimum can make it taller. **Why:** the audit's
  blockers UI-01 and UI-02; the available area excludes the desktop's
  panels but not the window's title bar, which is about 30 to 40 px.
- **Decision:** the screen limits the height only; a dialog keeps the
  width its code gave it. **Why:** the window manager places a wide
  window, and the Customize dialog is laid out for its width; narrowing
  it to an 800 px test screen made its cards scroll sideways with large
  fonts (`test_wizard_fits_without_sideways_scrolling_with_large_fonts`).
- **Decision:** `widgets.ScrollBody` is a frameless scroll area that asks
  for its content's whole size but has a small minimum height. **Why:** a
  dialog opens as large as before on a large screen and scrolls on a
  small one; the phasing-formation dialog (886 px) uses it.
- **Decision:** `EmptyState` moves from `budgets_area.py` to
  `widgets.py`; `budgets_area` imports it from there. **Why:** the model
  editor's Equipment tab needs it too (UI-29), and the repository has no
  `gui/components/` package.
- **Decision:** a material drop-down is 20 characters wide
  (`model_property_tabs.fill_material_combo`); its open list still shows
  each entry in full. **Why:** the longest entry made the part form
  750 px wide (UI-28).
- **Decision:** the Customize dialog gives every field label one width,
  the widest label's, on its one scrolling page (UI-47). **Why:** the
  audit asked for one label width per page; the dialog has one page.

## Breakout windows (2026-11-17)

The design is in
[`developer/windows-views-design.md`](developer/windows-views-design.md),
section 2, with the owner's answers at its end. The owner: "every
'bigger' feature inside SpaceMissionStudio should have its own breakout
window"; "it would be great if the 3D viewer/render would be a separate
window".

- **Decision:** one mechanism, `gui/breakout.py`, for Results › 3D View,
  Run › Thermal (the whole page) and the Budgets area (its tab widget).
  The live 2D map of PR-3 registers the same way. **Why:** one way to
  open, place, remember and bring back a view, and one set of tests.
- **Decision:** the same widget object becomes a window. It keeps its
  parent: it leaves its tab (`QTabWidget.removeTab` does not reparent) or
  its layout slot and gets the window flags. **Alternatives:** a new
  top-level window that takes the view as its child (the design note's
  first form). **Why:** a new parent makes Qt restyle every widget of the
  view under the application's style sheet. Measured offscreen: 50 to 70
  ms to move Budgets (431 widgets) into a new window, over the 50 ms of
  "Never freeze"; with the parent kept, 15 to 26 ms for Budgets and 4 to
  13 ms for the 3D View and Thermal. Nothing is copied or built twice: the
  web view, the scene, the live timer and the time cursor stay.
- **Decision:** the view's place shows a placeholder: "<view> is in its
  own window", **Bring Back** (primary) and **Show Window**. The tab keeps
  its index and text; the tab goes from the view to the placeholder
  directly, so no other tab is shown (and built) in between.
- **Decision:** the commands are "Open in Own Window" and "Bring Back".
  `Ctrl+Shift+D` (free in 2.11.0) moves the view shown; in a view's own
  window it brings that view back. **View > Own Windows** has it and one
  command per view ("Open 3D View in Own Window" or "Bring Back 3D
  View"); all are in the palette. Each view has an icon button at the end
  of its toolbar (Budgets: in its tab bar's corner) with the shortcut in
  its tooltip and an accessible name. Their palette category is their
  submenu's name, "Own Windows", as "Budgets" is for Tools > Budgets.
  **Why:** CLAUDE.md "Keyboard first"; the words say what happens, and
  "own window" is the one word for it everywhere. The category keeps the
  View commands as `test_workspace.py` lists them.
- **Decision:** two Lucide icons are added, `external-link` (open) and
  `square-arrow-down-left` (bring back), from the same `lucide-static`
  1.52.0 archive, its SHA-256 checked again
  (`docs/THIRD_PARTY_ASSETS.md`).
- **Decision:** a view's window carries the main window's global
  commands, Run and Cancel Run, and the commands of its area, not Go to.
  **Why:** `Ctrl+K`, `Ctrl+S`, `Ctrl+R`, `Ctrl+Shift+D` and, for Budgets,
  its `Ctrl+Shift+N`, `Ctrl+Del` and `Ctrl+Shift+C` work there; Go to
  would change the hidden main window. `Ctrl+K` opens the palette over
  the window it was pressed in.
- **Decision:** the window's geometry is kept per view in `layout.ini`
  (keys `breakout/<id>/geometry` and `breakout/<id>/maximized`). It is
  read with the layout at start, kept in memory while the app runs, and
  written with the layout at quit. It is used again only when the top of
  the window is on a screen that still exists; otherwise the window takes
  the saved size, centred on the main window. On Wayland, which ignores a
  window's position, only the size is used. **Why:** a write of the file
  on the GUI thread measured 50 to 220 ms here (the file lock and `sync`).
  The first version wrote it from a worker when the view came back. That
  still stopped the GUI thread: `QSettings.sync` keeps the interpreter
  lock while it writes (a 30 ms sync stopped a Python loop on the GUI
  thread for 36 ms), and CI measured one move at 146 ms. A crash now
  loses the windows' places since the start, as it loses the rest of the
  layout.
- **Decision:** the Windows CI job draws Chromium's compositor in
  software (`--disable-gpu-compositing` in its `QTWEBENGINE_CHROMIUM_FLAGS`),
  as it already drew WebGL (SwiftShader). The app's own flags do not
  change. **Why:** the runner has no GPU, and the compositor's Direct3D
  shared images lost WebGL contexts at random; after a recovery test took
  one away, no later 3D View in that process got one back, so a different
  set of WebGL tests failed in each run. The owner chose this
  (2026-11-18) over a deeper study on a Windows machine with a GPU.
- **Decision:** when a lost WebGL context comes back too early (no new
  context can start yet), the 3D View tries again 2 s later, five times
  in all, before it says that WebGL is gone. **Why:** on Windows a move
  to another window loses the GPU context, and the GPU process takes a
  moment to start again; giving up at the first try left the view
  without a picture for good (Windows CI, second round).
- **Decision:** every view opens docked at start, and no window opens by
  itself. When no scenario is open, and before the layout is saved at
  quit, every view comes back. Showing a view in its own window (a
  command, the palette, a live run) brings its window to the front and
  leaves the main window's area as it is. **Why:** "Calm by default"
  above. D-191 is a rule of System Budget Studio, not of
  SpaceMissionStudio (the design note, section 2).
- **Decision:** a detached Budgets area counts as shown (B-21, the design
  note's Q2): it is computed after an edit, and Remove and Copy as CSV
  act on it from either window. Its spacecraft picker goes with it, into
  the tab bar's corner, and comes back to the area's header. **Why:** the
  owner's answer to Q2.
- **Decision:** the 3D View's page handles a lost WebGL context: on
  `webglcontextlost` it stops drawing and asks for the context back; on
  `webglcontextrestored`, or after 2 s without it, it makes a new
  renderer and loads the same scene with the camera kept
  (`MV.load(MV.data, {keepCamera: true})`), with the frame and a thermal
  case's colours. **Why:** a `QWebEngineView` that moves to another
  native window can lose its context on some drivers (the design note's
  risk 1).
- **Decision:** a view in its own window has the `bg.canvas` background
  through a style-sheet rule on the property `breakout="true"`
  (`theme/qss.py`). **Why:** a tab page is transparent
  (`QStackedWidget > QWidget`), and a transparent window draws black.

## Ground tracks, stations and the live map (2026-11-17)

The design is in
[`developer/windows-views-design.md`](developer/windows-views-design.md),
section 3, with the owner's answers at its end (Q1 and Q3). The owner: "I
am missing the ground-tracks on the earth surface"; a station must be
clearly visible on the globe; the 2D map lives in the 3D View and can
open in its own window.

- **Decision:** the globe's ground track is on by default (Q1). It is
  solid where the spacecraft has flown and dashed where it is still to
  fly, split at the time shown. The dashes keep their length on screen
  at any zoom (6 px dash, 4 px gap). **Why:** the owner's answer; the
  split tells the past from the future without a second colour.
- **Decision:** a ground station on the globe is a 14 px glyph (a
  triangle on a mast, on a foot) with a 1 px dark outline
  (`palettes.STATION_OUTLINE_COLOUR`) and its name beside it. The glyph is
  an SVG in the page's overlay, placed as the labels are and hidden behind
  the Earth as they are. In contact it takes the line-of-sight colour.
  **Alternatives:** a `THREE.Sprite` (the design note). **Why:** the
  overlay draws it crisp at one size on screen at any zoom and pixel
  ratio, and the outline comes from CSS; a sprite needs a texture per
  colour and blurs when scaled. The Show menu's Stations switches the
  glyph, Labels the name.
- **Decision:** each station has a ring on the surface per spacecraft:
  the visibility circle of its elevation mask at that spacecraft's
  altitude now, Earth central angle `lambda = acos(R / (R + h) cos eps) -
  eps` (Wertz and Larson, *Space Mission Analysis and Design*, 3rd ed.,
  section 5.2), on the ellipsoid. It is drawn again only when `lambda`
  changes by more than 0.01 deg. It is the station's colour at 0.5
  opacity, and the line-of-sight colour at 0.95 while that spacecraft is
  in view (`station_visible`). **Why:** the design note; the station's
  colours, not status colours, because it depicts a thing.
- **Decision:** the 2D map (`gui/ground_map_widget.py`) is a Qt widget
  that paints, not a second web page. A worker paints the Earth image,
  the grid, the night side and the tracks into a `QImage` at device
  pixels; the flown part of a track goes on a layer the worker keeps and
  only adds to while the time moves forward. A long line is drawn in
  pieces of 256 points, because each Qt call holds the interpreter lock
  (about 1.5 ms a call, measured). The GUI thread draws that image and,
  on top, the spacecraft markers, the station glyphs, the visibility
  circles, the labels and the legend (a few ms; a test holds it under
  10 ms median). A resize waits 120 ms; a theme change repaints.
  **Why:** "Never freeze"; no second `QWebEngineView`.
- **Decision:** the map is equirectangular, 2 : 1, with geocentric
  latitude, the same as the globe's track (`scene3d.ground_track_deg`); it
  differs from geodetic latitude by at most about 0.19 deg, and the map
  says so. The image is the 3D View's own Blue Marble (2k, or 4k on a map
  wider than 2048 device pixels): no new asset, no new licence; the NASA
  credit is in the map's tooltip. A track is cut at the date line, at the
  latitude where it crosses. **Why:** the design note's risk 6.
- **Decision:** the map also shades the night side (from the Sun's
  direction at the time shown) and draws a 30 deg latitude and longitude
  grid with labels, and a legend (spacecraft colours; flown solid, to fly
  dashed). Its own **Show** menu switches tracks, stations, day and night,
  grid and labels, each on by default and remembered (`ground_map/<key>`).
  The night shade and the grid colours are depicted things, the same in
  both themes (`palettes.NIGHT_COLOUR`, `palettes.MAP_GRID_COLOUR`); the
  labels and the legend are on the theme's raised panels.
- **Decision:** the 3D View has a segmented control **Globe | Map |
  Both** (keys `G`, `M`, `B` in the view; **View > 3D View** and the
  palette: Show Globe, Show Map, Show Globe and Map), kept per user
  (`mission_view/layout`). It starts on Globe. Both is a splitter, half
  and half. With Map alone the globe's web view is not made. **Why:** Q3
  (the map inside the 3D View area); "Calm by default"; a web view only
  when it is shown. The tab names stay, so `test_workspace.py` and
  `test_live_run_3d.py` reach the 3D View as before.
- **Decision:** the map is a view of its own for `gui.breakout` (id
  "map", title "Map"), with its own **Open in Own Window** button. In its
  own window it shows **Play** and the time, since the 3D View's controls
  stay behind. Brought back while the 3D View shows Globe only, the 3D
  View switches to Both, so the map is seen where it came back to.
- **Decision:** `gui/live_scene.py: LiveScene` is the one consumer of a
  live run's feed (its `drain` removes what it returns). It drains 20
  times a second and, in one serial worker, builds the scene or extends
  it (`extend_scene`) and makes the page's `MV.append` JSON. It extends a
  shallow copy of the scene, so the scene the GUI thread holds stays
  whole. The globe sends the JSON; the map paints the new segments in its
  own worker. `LiveSceneBuilder` is gone; `LIVE_TICK_MS`, `LIVE_BATCH`
  and `LIVE_BATCH_STATES` stay importable from `mission_view_widget`.
  **Why:** the design note's risk 4 (`np.concatenate` grows with the
  run) and "Never freeze".
- **Decision:** no separate `Playback` class. The 3D View's playback (its
  timer, slider, LIVE state and the shared time cursor) stays the one
  clock, and the map follows it (`set_frame`, `set_live`,
  `set_playing`); the map's Play and End ask the 3D View. **Alternatives:**
  the design note's extracted `Playback`. **Why:** the simplest form; the
  map has no clock of its own, and the 3D View's tested playback is left
  as it is.
- **Decision:** `scene3d.Craft.path_times_s` keeps the time of each point
  of the path and the ground track (display data, in memory). The page
  gets it as `tt`, to split the track at the time shown. No output file,
  no golden file and no file format changes.

## Empty states everywhere (UI audit B3, 2026-11-18)

- **Decision:** `widgets.EmptyState` is the GUI's one empty state. B1's
  widget gets a compact form (`compact=True`: left-aligned, as tall as
  its lines, the title a heading; the full form keeps the middle of its
  area with a section title), more buttons (`add_action`) and a detail
  under the text (`add_detail`). `NoScenarioState` and
  `BreakoutPlaceholder` are subclasses of it. **Why:** the audit found
  five styles (UI-15); the repository still has no `gui/components/`
  package, so the widget stays in `widgets.py` (B1's decision).
- **Decision:** the old styles go: the "empty" label role and the
  `emptyState` label leave the style sheet, and the Problems panel, the
  Inspector, Compare, Show calculation, Home's template filter, History,
  Results › Overview, Plots, Dashboard, Output and 3D View, Run › Plan and
  the work areas without a scenario show an `EmptyState`. A `DataTable`'s
  own line inside a table and a `NoteList`'s or `ValueSheet`'s "none"
  line stay. **Why:** those are a line inside a component that is
  already there, not the state of a view; they are used in more than 60
  places.
- **Decision:** a list shows its empty state in its place
  (`widgets.EmptyStack`), and Edit and Remove are off until a row is
  selected. The ground station and spacecraft lists are as tall as their
  rows (`fit_rows`), with the free room below the buttons. The mission
  sequence (a tree) keeps the page's height, and its form pane hides
  while there is no step. The spacecraft list's Add is no longer the
  accent while the list is empty: its empty state's Add spacecraft is
  the action there, a secondary button. **Why:** UI-05; a tree's height
  changes as its steps open and close; one accent per view is batch B2's.
- **Decision:** while a list shows its empty state, the list's own Add
  and the buttons that need a row are hidden (`EmptyStack.hide_while_empty`):
  Add, Edit and Remove on the ground station and spacecraft lists, and
  the whole step row of the mission sequence. Other actions stay (New
  from template... and the three generators). **Why:** the first
  screenshots showed two Add buttons on each of these pages, one in the
  empty state and one just under it.
- **Decision:** Results › Plots shows its empty state over the plot page,
  which stays loaded under it (`QStackedLayout.StackAll`). **Why:** the
  page's size, its loading and its "drawn" signal stay as they were;
  `_empty_state_html` stays because `test_dark_theme.py` reads it.
- **Decision:** End of Life puts the results first (the empty state
  before an estimate, then the tiles, the badges, the notes and the
  plot) and the inputs below them in the existing `FoldSection`
  ("Inputs"), open at first. **Why:** UI-10; the plot is in view after an
  estimate without scrolling, and folding stays the user's choice.
- **Decision:** Run › Plan's empty state says what a plan is. With no
  operations section it offers Open Template 35 (opened as Home opens a
  template, with the unsaved-changes question); with one, Plan. The page
  no longer tells the user to edit JSON; the error after Plan still
  names Scenario › JSON, as the how-to does. **Why:** UI-22; template 35
  is the app's way to start a plan. A form that builds an operations
  section is out of scope for B3.
- **Decision:** Run › Design Checks shows "Not checked yet" with Check
  before the first check (the empty state's Check is a secondary button:
  the page's own Check stays the primary one). **Why:** UI-45; one accent
  per view is batch B2's.
- **Decision:** the Timeline without events hides the timeline, the
  table, the summary and the cursor line, and shows one empty state with
  the reasons as a note list. With events, the summary line is as before.
  The timeline draws nothing without rows; a table that the filters
  empty says so once. **Why:** UI-25.
- **Decision:** the Problems panel says "No scenario is open" while none
  is (`ProblemsWidget.set_scenario_open`, set by the window). The status
  bar's "No problems" chip is left as it is. **Why:** UI-24 names the
  panel; the chip counts problems and is batch B8's (the status bar).

## One primary action, stable headers (UI audit B2, 2026-11-18)

- **Decision:** the top bar's Run is the app's primary action. It is the
  one accent button of every view while a run can start. A page's own
  buttons are secondary: the Run area's Run, the Run of the History and
  Results › Overview empty states, Check on Run › Design Checks,
  Estimate on End of Life, Add Budgets Section and Add Item on
  Budgets › Equipment, a data table's empty-state action and Bring Back
  on a placeholder. **Why:** UI-03 found two or three accent buttons in
  one view. The audit's fix puts the accent on one command in one place.
- **Decision:** Home's Open template is the accent while no scenario is
  open; with a scenario open it is secondary
  (`LoadScenarioWidget.set_primary`). The work areas' New Scenario stays
  primary: it shows only while no scenario is open. **Why:** Home's job
  is to open a scenario. While none is open, Run is disabled and grey, so
  the view still has one accent.
- **Decision:** the Run area keeps its own Run button, now secondary.
  **Why:** `test_main_window.py::test_toolbar_actions_are_all_visible`
  requires Run in the Run area's header. Taking a command away from where
  users find it is the owner's choice.
- **Decision:** a disabled primary button is not counted as an accent.
  **Why:** the style sheet draws it grey (`bg.hover`, `text.disabled`).
  `tests/gui/test_primary_action.py` counts the visible, enabled buttons
  drawn in the accent, in every area, tab and Scenario page, with no
  scenario and with template 01.
- **Decision:** every area shows its header with its title, Home,
  Reports and Settings too. The header has a fixed height of 48 px
  (`theme.AREA_HEADER_HEIGHT`: a 32 px control and 8 px above and below).
  Its commands are one row (a `QHBoxLayout`, no longer a `FlowLayout`).
  When their names do not fit, the buttons show their icons only, with
  the names in their tooltips and accessible names
  (`AreaPage.squeezed`). **Why:** UI-17. A header without commands was
  hidden, and a wrapped row was taller, so the tab rows started at
  different heights. The navigation rail squeezes the same way (B-19).
- **Decision:** `AreaPage.title_bar` is the whole header and is always
  shown; `AreaPage.header` is its commands, hidden with the content while
  the empty state shows. **Why:** the title always says where the user
  is; `test_landing_page.py` checks that the commands give way to the
  empty state.
- **Decision:** the breadcrumb names the Reports tab ("Reports ›
  Exports"). Home, Timeline and Settings have one page, so their
  breadcrumb is the area name. **Why:** UI-17.
- **Decision:** the top bar's Save always reads "Save". The save state
  stays the subtitle's first part and gets an icon of its own before it:
  `circle-dot` for unsaved changes, `circle-check` for unchanged or
  saved, `file-plus` for not saved yet, in `text.secondary`, with the
  state as its accessible name and tooltip. **Why:** UI-36; a button's
  label says what it does. The subtitle already said the state. A status
  colour would make a normal state look like a problem.
- **Decision:** the run-mode button is as wide as its longest mode
  (`app_shell.SteadyToolButton`). The problem count moves to the start
  of the top bar's commands, so it takes its room from the subtitle.
  **Why:** UI-36. The count appears after an edit, and at the end of the
  row it moved Run under the pointer.
- **Decision:** a top bar narrower than 1040 px
  (`theme.TOP_BAR_COMPACT_BELOW`: 1280 px with the Inspector shown) shows
  the search field's icon and key ("Ctrl+K") only. **Why:** at 1280 px
  with the Inspector the subtitle had 29 px ("Un…"). Now the save state
  shows whole. The rule uses the bar's width only, so a mode or a count
  never changes it.
- **Decision:** Clear Time Cursor is enabled only while a scenario is
  open and a time cursor is set. It left `_SCENARIO_COMMANDS`. **Why:**
  UI-41.
- **Decision:** Run is enabled only when a run can start: no run going,
  a scenario open, and no error in the scenario's problem list
  (`ScenarioEditor.problems`, the list the Problems panel shows).
  Otherwise Run is disabled in the top bar, the Run area, the menu, the
  palette and Ctrl+R, and its tooltip and palette entry say why
  (`ActionRegistry.set_available`, `Command.unavailable`). The empty
  states' Run buttons follow it. Warnings do not disable Run, and the
  run-mode controls stay enabled with an error. `on_run` keeps its own
  check (`_cannot_run`). **Why:** UI-55. The editor computes the problem
  list on each edit already, so the check adds no work on the GUI
  thread. Picking a mode starts nothing.
- **Decision:** a disabled palette entry shows its command's reason when
  the command has one, else "Not available right now." **Why:** the
  palette says what the tooltip says. A reason for every other disabled
  command (UI-40) is batch B12's.
- **Decision:** Run › Design Checks shows one Check at a time, both
  secondary: the empty state's before the first check, the row's (beside
  the spacecraft) after it. **Why:** two Check buttons, one under the
  other, did the same thing; an empty list's own Add is hidden in the
  same way (B3, `EmptyStack.hide_while_empty`).

## Value sheets instead of sentences (UI audit B5, 2026-11-18)

- **Decision:** the scenario editor has no footer. Its "✓ valid" line
  and its plausibility warnings are gone. **Why:** UI-09. The Problems
  panel listed every error and warning already, the top bar and the
  status bar count them, and a field with an error is marked under it.
  No information shows only in the footer: `ScenarioEditorWidget.problems`
  holds the same errors and warnings, and the plausibility warnings are
  still computed only while the scenario has no error (UI-50 is another
  batch's).
- **Decision:** a status-bar message about a file names the file
  ("Opened 01_two_body_circular_orbit.json", "Saved mine.json"), elided
  in the middle to the room left of the permanent entries, and the whole
  path is the status bar's tooltip until another message replaces it
  (`MainWindow._show_file_message`). **Why:** UI-09. The path is the
  user's own; it stays out of the visible text, which clipped it. An
  error report that names a path (a save that failed) is left as it is.
- **Decision:** where the core makes a sentence of numbers that the
  window shows, it also gives rows of (label, value, unit), the unit in
  the code's spelling: `control_gains.default_gains_rows`,
  `scenario_explainer.orbit_rows`, `idm_import.ImportSummary.rows` and
  `findings`. The text forms stay as they were (`describe_default_gains`,
  the "Orbit" tile's value, `ImportSummary.lines()`), because the golden
  files, the command line and tests read them. `units.display_rows` turns
  the units into the window's ("N*m" as "N·m"). **Why:** UI-14; the
  golden files stay byte-identical.
- **Decision:** the control gains' sheet lists the applied K and P, the
  integral feedback (off), the mean inertia and the reference inertia;
  the reference gains and the scaling are its tooltip, computed from
  `control_gains`' constants. **Why:** one value per row, and the sheet's
  text stays within the 160 characters of a help label.
- **Decision:** the Overview's orbit tile is three tiles: the kind of
  orbit (Classical, SSO, Cartesian state, TLE), the inclination [°] and
  the altitude [km] ("From the centre" around a small body). A scenario
  with several spacecraft keeps its table. **Why:** UI-14.
- **Decision:** the inputs from the last run (Budgets › Propellant, End of
  Life) are a value sheet titled "From the last run" or "From the end of
  the last run": first "Run started" in ISO 8601 UTC with Z, to the
  second (`run_history_view.utc_text`), then a row per value with its
  unit, its source as the row's tooltip; the contributor hint is the
  sheet's note. `ValueSheet.set_rows` gained `tips` for the tooltips.
  **Why:** UI-14 (the heading printed "2026-11-17T18:49:48.737253+00:00").
- **Decision:** the IDM-CIC import preview is a value sheet (model
  version, project, configuration, body element, the number of elements,
  parts, point masses and meshes, the mass and the propellant [kg], a
  re-import's counts) beside a note list of its findings (left out,
  approximated, the margins in the file, the notes), in the same six
  lines' height, scrolling. The devices, properties and power stay on
  their tabs; the command line prints `lines()` as before. **Why:** UI-14
  and UI-02.
- **Decision:** Results › Overview shows `run_summary.overview_figures`:
  `summarize`'s figures with each spacecraft's orbital period [min] and
  altitude [km] after the run length. The period comes from the median
  semi-major axis (mean elements when recorded) and the run's GM; the
  altitude is the distance from the centre less the central body's
  equatorial radius (a sphere), one "Altitude" when its lowest and
  highest agree to the shown 0.1 km, else "Lowest altitude" and
  "Highest altitude". A small body has no altitude card. `summarize`
  itself is unchanged, so Compare, `run --explain`, the API and the
  golden files are too. Eclipses already had their cards when the run
  recorded the eclipse. **Why:** UI-20. "Lowest" and "highest", not
  "perigee" and "apogee": over a run with manoeuvres or drag they are the
  run's extremes, not one orbit's.
- **Decision:** every Overview card has the height of the tallest one.
  The battery's unit shows as "Wh" (`units` maps "W*h"); the figure keeps
  "W*h". **Why:** UI-20; the figures in files keep their spelling.
- **Decision:** the Problems panel is where a warning is written out.
  The shown run's warnings are Problems rows (`ResultsWidget.run_warning_rows`):
  their object the run ("Run 2"), their tooltip the warning's rule or,
  for a drift warning without a rule, the drift explanation; a
  double-click opens Results › Plots. Results › Plots keeps its
  provenance line and no warning line. The top bar keeps a count that
  opens the panel (`MainWindow.show_problems`, the method this code base
  has for it); the status bar keeps its count. **Why:** UI-37. Before,
  one warning showed in the footer, the top bar, the status bar, Problems
  and the plots page. The run's messages in the status bar ("Run 1
  complete", "Cannot run: ...") are left: they report a run, not a
  warning of the scenario.
- **Decision:** text the window shows names the user manual's section
  ("the user manual, section 6, "Thermal analysis"") instead of a file of
  the source tree (docs/models/..., SpaceMissionStudio/README.md,
  packaging/README.md), in the GUI, the network guard's refusal, the
  support-data error and the two schema comments the JSON page shows as
  help. The command line's texts, the calculation traces' references and
  the model choices' sources keep their paths: a test requires the
  command line's help to name docs/user-manual/command-line.md, and a
  trace's reference is a citation that files written by the app carry.
  **Why:** UI-43; an installed app has no source tree.
- **Decision:** the 3D View's note is one line (`app_shell.ElidedLabel`,
  now inside its margins), in the caption style: "Not to scale:
  spacecraft drawn 298,232× larger than they are, so that you can see
  them." in the whole-orbit and Earth-fixed views while the spacecraft
  are enlarged, the axis colours when following a spacecraft; the scene's
  notes after it and in full in its tooltip. It is hidden in the views
  from a spacecraft, whose name says what they show. **Why:** UI-51.
- **Decision:** the 3D View's page resizes its canvas when its host
  element changes size (a `ResizeObserver`), not only on a window resize.
  **Why:** UI-51. The canvas was sized while the page still had a scroll
  bar; the theme's CSS then hid the overflow and the host grew by 16 px
  with no resize event, which left a dark strip at the right edge.

## Labels instead of identifiers (UI audit B4, 2026-11-19)

- **Decision:** the label maps live in `gui/field_text.py`:
  `DEVICE_KIND_LABELS`, `GUIDANCE_MODE_LABELS`, `BODY_LABELS`,
  `AREA_LABELS` and `PARAMETER_LABELS`, with `kind_label`, `mode_label`,
  `body_label`, `area_label` and `parameter_label`. An unknown code (a
  plugin's parameter) shows as it is. **Why:** UI-08, UI-19; one place
  for the window's names of codes, beside the messages' field titles.
- **Decision:** the labels are the ones the app already uses. The device
  kinds are the IDM-CIC import's names (`idm_devices.KIND_LABELS`:
  "Star tracker", "Gyro / IMU", "Sun sensor", "Magnetorquer"), with
  "Thermal sensor" added. The guidance modes are the Overview's and the
  run summaries' names (`scenario_explainer.FSW_MODE_NAMES`, made
  public): `sunSafePoint` is "Sun pointing", not "Sun-safe pointing".
  The bodies take the manual's spelling ("Mars barycentre"), and Eros is
  "433 Eros", its title in `engine.small_bodies`. **Why:** the golden
  files hold the Overview's names, so they cannot change; one name for
  one thing across the window.
- **Decision:** a form shows the label and keeps the code as the item's
  data (`currentData()`, `Qt.UserRole`); the code is the item's tooltip
  ("kind: star_tracker", "fsw_mode: sunSafePoint"). A device's own name
  stays as the user wrote it, and a new device is still named after its
  kind's code ("star_tracker-1"). **Why:** the scenario file is written
  exactly as before; an engineer can still find the JSON key.
- **Decision:** the configuration parameters' names are a GUI map, not a
  new field of `config.registry.Parameter`. **Why:** the registry, its
  defaults file and the command line stay unchanged; a test checks that
  every registered parameter and area has a name.
- **Decision:** Scenario › Assumptions shows the key as a muted second
  line under the name (`Row.notes`, the monospace font, the secondary
  colour), not as a column. The rows are two lines high. **Why:** UI-19
  asked for "a muted line or column"; a key column made the table
  1165 px wide on a 672 px page at 1280 x 720 with the Inspector open.
  The name takes the width left; Value, Default, Unit and Source start
  at most 96, 96, 72 and 152 px wide and are elided, whole on hover and
  under the table.
- **Decision:** a model's name in Value or Default is left-aligned
  (`Row.plain`); a number and a list of numbers are right-aligned. The
  value stays the code the file takes ("ad10_equations"): it is what the
  Value field below the table accepts. **Why:** UI-19; the detail line
  names the models with their titles already.
- **Decision:** the `DataTable` changes apply to every table that uses
  it: no grid lines, left-aligned headings (a numeric column's right),
  group rows on `bg.canvas` and not selectable, bracketed units in the
  headings typeset (`units.label`). The copied TSV keeps the headings as
  written. **Why:** the design rules ("surfaces, not lines"); UI-19 and
  UI-49 named the grid lines, the centred headings and the heading row
  that looked selected. UI-27 and UI-33 (batches B9 and B7) gain the grid
  and heading part of their fix.
- **Decision:** the reference data panel is a `DataTable`. A status is a
  word with its status icon and ink: Present, Missing, Out of date, Not
  downloaded (`data_panel_widget.STATUS_SHOWN`). A kind starts with a
  capital in the window. A file without dates shows "–" under Covers;
  the column is hidden when no file has dates. Kind, File and Covers
  start at most 170, 200 and 200 px wide, elided in the middle and whole
  on hover, and the window opens 1120 x 480 px (it was 980 x 460).
  **Why:** UI-49; at 980 px the columns needed 949 px before Source.
  The inventory's statuses and kinds (`engine.reference_data`) keep
  their codes.
- **Decision:** `engine.reference_data` lists Basilisk's
  `AtmosphereData` files as "atmosphere table", not "SPICE kernel".
  **Why:** UI-49; they are the tabular atmosphere's CSV and text
  profiles. Only the window reads the inventory's kinds.
- **Decision:** "--" used as a dash in the GUI's strings and in the user
  manual's prose is an en dash with spaces; the Mission dashboard's "--"
  for no value is "–" (`mission_dashboard_widget.NO_VALUE`); the window
  title reads "SpaceMissionStudio – untitled". Comments, docstrings,
  command-line flags and code spans keep their hyphens. The help texts'
  first part is split at " – " or " -- " (`param_form.short_label`,
  `wizard_settings`, the editor's name check), so a message of the core,
  which keeps "--", still splits. **Why:** UI-34. The core's messages,
  which the command line prints and tests and golden files read, are
  unchanged; the Problems panel shows them as they are.
- **Decision:** the GUI writes units in their display form: "°", "m²",
  "kg·m²", "Wh", "N·m·s" in prose and in values beside a unit; a suffix
  made from a unit goes through `units.suffix` (`budget_widget._spin`,
  `model_editor_dialog._spin`, `roe_formation_editor._spin`, the
  navigation errors' rows, the value-mark note: "Edited (computed
  97.59°)"). Bracketed units in form labels stay as they are: the form
  typesets them, and messages name the field with them. `units` learns
  "W/m^2", "g/m^3" and "m per (m^2/kg)". **Why:** UI-35. Field names,
  JSON keys, the command line's output and the file formats keep their
  spelling; text the core makes (the pass summary's "peak 61 deg", the
  value-mark consequences' "deg/day") is unchanged.

## One form grid and page inset (UI audit B6, 2026-11-19)

- **Decision:** one page inset, `theme.PAGE_INSET` = 16 px
  (`SPACE["lg"]`), from a page's left and top edges, for every page of
  every area: each tab of Run, Results, Budgets and Reports, Home,
  Timeline, Settings, each page of the Scenario tree and the JSON page.
  `AreaPage` applies it (`shell.inset_page`, `inset_stack`; pages added
  later too); a page draws no margin of its own. **Why:** UI-16; 16 px is
  the area header's inset of its title, so a page's content lines up
  under the title. The pages had 0, 9, 12, 16, 18, 24 or 25 px.
- **Decision:** a page that scrolls itself is marked `INSET_INSIDE` and
  puts the inset inside its scroll area (the Run page, Overview, Home,
  the embedded spacecraft, ground station and Environment forms); the
  others get it around them, their tables and scroll bars inside it.
  The tab rows and the Scenario tree stay flush with the page's edges.
  **Why:** a scroll bar 16 px from the window's edge looks misplaced; the
  tab rows and the tree are navigation, not content.
- **Decision:** the Scenario area's first form is "General"; its page
  has no group title. The node is found by its item
  (`scenario_item`), never by its text, so nothing else changed; the
  manual and the user guide say General. **Why:** UI-52 ("Scenario" was
  the area's title, the node and the group's title); "General" is the
  usual name of a document's first settings page.
- **Decision:** the Scenario tree is as wide as its longest node needs
  (its indentation, text, padding, frame and scroll bar), between 170 and
  340 px (`theme.PAGE_TREE_WIDTH`), as the tree's minimum width, measured
  with the font in use. "Power / propulsion / link budget" keeps its
  name. **Why:** UI-18. Renaming the section would change the manual,
  the user guide, the flight-software export's traceability text and the
  tests that name it; the tree needs 287 px for it on Linux. A
  minimum width, not a start width: a layout saved with 220 px is
  restored at the width the names need.
- **Decision:** one form grid per page (`widgets.FormGrid`, installed by
  `finish_form`): the label column of every form of a page is as wide as
  the page's longest label needs, at most 224 px
  (`theme.LABEL_COLUMN_MAX_PX`); a longer label wraps onto a second line.
  The grid is measured from the forms' positions, so forms in groups and
  nested widgets line up; it follows the page (a section built, a group
  opened) on the next turn of the event loop. A grid inside another
  page's (the orbit widget's) leaves the line-up to the page's. A form
  inside another form's field keeps its own column. The labels may be
  QLabels or a parameter's include check box. **Why:** UI-26: separate
  QFormLayouts each sized their own label column. Without the cap, one
  label of 300 px ("sigma_BN (MRP, body B relative to EME2000 N)")
  pushed every field of Orbit / mass to the right.
- **Decision:** field widths: a drop-down list at most 320 px
  (`theme.FIELD_WIDTH["choice"]`), a number field at most 224 px
  (`["number"]`, the M4a value, moved to the theme), set by
  `limit_field_widths` for every field under a finished form. An entry
  longer than the drop-down list ends in "…" (`widgets.ComboBox`); the
  open list shows it whole. A button alone in a form row or a column
  keeps its own width at the left; rows with a button and a field get a
  stretch at their end. Text fields (a name, a path, the description)
  keep the form's width. **Why:** UI-26 (combos 770-960 px, "Look ahead"
  820 px, the LTAN 435 px, a button 880 px).
- **Decision:** Run › End of Life's numbers are `NumberField`s ("30
  years", "250 km", "0.000 kg"), and the page is a finished form. **Why:**
  UI-26 named it; its spin boxes were plain ones with a hand-made
  suffix.
- **Decision:** a disabled input's tooltip starts "Off:", says why and
  names what turns it on; `widgets.set_off_reason(widget, enabled,
  reason)` keeps the input's own tooltip after the reason and shows it
  alone while the input is on (`own_tooltip` changes it). Every input the
  test found off without one has one now: the five of the audit (Pace,
  Degree/order, Gravity from the shape model, the dry mass, centre of
  mass, inertia and facets a 3D model gives, the re-entry Estimate), the
  albedo check box, the space-weather fields of a model that does not
  read them, the atmosphere table, the comms-pointing Sun axis, Edit and
  Remove of the spacecraft and station lists, Scenario › Assumptions'
  value, Set and Reset to default, Run › Plan's Save plan... and Compare,
  End of Life's deorbit perigee and propellant, the re-entry density and
  Save..., and Reports › Flight Software's Export... and Open folder.
  The test needs no allow-list. A child of a disabled widget with a
  tooltip says why through it (Qt shows the parent's tooltip). **Why:**
  UI-42.
- **Decision:** the thermal editor's ten kinds of record are six tabs:
  Nodes, Faces, Couplings (conductors, heat pipes, radiative links), Heat
  loads (dissipation, heaters), Cases (the cases and the thermal Monte
  Carlo) and Solver (the environment and the solver). A tab of several
  kinds shows each under its heading. **Why:** UI-13: ten tabs needed
  about 930 px and were cut at "Mon"; six need about 430 px and fit with
  the Inspector open too. Sections in the page tree would need a third level
  of nodes under a spacecraft's section; a segmented control of ten would
  not fit either. "Couplings" and "Heat loads" are the thermal analyst's
  names (conductive and radiative couplings, heat loads).
- **Decision:** the thermal tables are the editable model/view grid of
  the GUI (`thermal_editor.RecordModel`, a `QAbstractTableModel` with
  `ItemIsEditable`, in a `QTableView`), not `DataTable`: every table is
  edited. No grid lines, numbers right-aligned in tabular figures, no row
  numbers, as tall as their rows (no inner scroll bar), the columns
  fitted to the page: each at its heading's and cells' width when they
  fit; else the cells keep theirs and the headings share the rest
  (elided, whole on hover); a table too wide even for its cells is scaled
  down. A list without a row shows its compact empty state with Add
  (`EmptyStack`). The table's API is `row_count`, `cell`, `set_cell`,
  `current_row`, `set_current_row`, `remove_current`, `add_record`,
  `set_records`, `records`. Generate, Conductance, the JSON view and the
  file are unchanged. **Why:** UI-13 (QTableWidgets with grid lines, a
  table scrolling sideways inside the page's scroll area).
- **Decision:** the third bodies stay a `QListWidget` of checkable items
  with the role `checklist`: no frame, the form's background, a row per
  body at the table-row height (`RowHeightDelegate`), as tall as its
  rows, no scroll bar. **Why:** UI-53; it looks like check boxes in the
  form, keeps the keyboard (arrows, Space) and the item data the tests
  and the code read. A `DataTable` with a check column would be a table
  of six rows in a form.
- **Decision:** Scenario › Monte Carlo is a top page (`_page(top=True)`):
  the switch and the line on what it does at the top, a stretch below.
  **Why:** UI-04.

## Settings page controls and keyboard table (UI audit B7, 2026-11-19)

- **Decision:** a command on a page looks like the control it is. A
  choice of a few is a segmented control (`widgets.SegmentedControl`), an
  on/off command a check box (`widgets.ActionCheckBox`), any other
  command a framed push button (`widgets.ActionButton`). Each is bound to
  its registry `QAction`: its state follows the action however it is run
  (a shortcut, a menu item, the palette), its tooltip is the action's,
  with the shortcut, and `defaultAction()` gives the action as a tool
  button's does. **Why:** UI-11. Settings showed its commands as
  frameless `QToolButton`s that read as plain text ("Theme: System",
  "Reference Data"), and a selected theme looked like a hovered word.
- **Decision:** Settings › Appearance › Theme is a segmented control
  System · Light · Dark. Its segments are the three theme commands, so
  View > Theme, the palette and the control agree. A click on the theme
  in effect leaves it chosen. The segments are an exclusive button group:
  one Tab stop, the arrows move in it, as in the other segmented
  controls. **Why:** UI-11 asks for it; it is the look and the keyboard
  of Form · JSON and the run mode.
- **Decision:** Settings › Layout shows the five on/off commands as check
  boxes on three rows: Panels (Menu bar, Inspector, Problems), Status bar
  (All details) and Navigation rail (Icons only). Reset Layout is a
  framed button under them. The check box labels are short; the tooltip
  keeps the command's full name and shortcut. **Why:** the command names
  ("Navigation: Icons Only") repeat the row's label beside a check box.
- **Decision:** the commands in an area header are secondary buttons
  with an edge and a surface (`QToolButton[variant="secondary"]`: the
  push button's `bg.surface` and `border.strong`, `border.subtle` when
  disabled, the 2 px focus ring), at the compact height, the same size
  as before. They stay `QToolButton`s, so they still show their icon
  only when the header is short of room. No header button is the accent:
  the top bar's Run is the one primary action. **Why:** UI-11; a
  frameless tool button on the header's canvas read as a line of text.
  The top bar's buttons are unchanged: UI-11 names the area headers,
  and B2 set the top bar.
- **Decision:** Settings › Keyboard is a `DataTable` (Category, Command,
  Shortcut). The last column takes the width left, the others their
  content's; the headings are left-aligned; no grid lines; rows at
  `theme.ROW_HEIGHT` (26 px); the keys are a code column (JetBrains Mono,
  the secondary colour); Ctrl+C copies TSV. The table is as tall as its
  rows, so the page scrolls, not the table. The rows keep the registry's
  order (by category); the table does not sort, as before. **Why:**
  UI-33 (the columns ended at 438 px in a 910 px frame, a centred
  header, grid lines). The "Known gaps" list in `docs/DESIGN.md` no longer
  names the shortcut list.
- **Decision:** the Settings sections are forms on one label column
  (`widgets.finish_form`, B6's `FormGrid`): Theme, UI scale, Motion, Plot
  units, Network use, Author, Panels, Status bar and Navigation rail. A
  note (the network policy, the author's name, an error) is a row of its
  own under its field, in the field column, hidden while empty. It
  answers for its height at the width it has. **Why:** B6's rule for
  every form; Qt sized a wrapped label in a form row for a narrow guess
  (three lines for one), and the text floated in the row.
- **Decision:** `widgets.ComboBox` adds `SPACE["md"]` to its size hint:
  the room its painter keeps beside the text before it elides. **Why:**
  a field sized to its longest entry still ended it in "…" ("100 %" read
  "10…" in Settings › UI scale, "As fast as possible" read "As fast as
  poss…" on the Run page). A field at its maximum width
  (`FIELD_WIDTH["choice"]`) still elides a longer entry.

## Shell: top bar, panels, status bar and toasts (UI audit B8, 2026-11-19)

- **Decision:** the top bar spans the window under the menu bar. The
  window's menu widget (`QMainWindow.setMenuWidget`) is a header,
  `windowHeader`, that holds the menu bar and the top bar. The docks and
  the rail start under it. `MainWindow.menuBar()` returns the menu bar
  in the header, because `QMainWindow.menuBar()` would replace the header
  with a new, empty menu bar. **Why:** UI-06. The Inspector took the full
  height beside the top bar, and at 1280 px the subtitle read "Unch…". A
  `QToolBar` would also span the window, but the app has no toolbars
  since M2a (their overflow hid a button on one platform), and a test
  keeps it so.
- **Decision:** a new window narrower than 1440 px
  (`theme.INSPECTOR_MIN_WINDOW_PX`), or on a narrower screen, starts
  without the Inspector. Reset Layout follows the same rule. Ctrl+I
  shows it. The rule was a screen narrower than 1600 px. **Why:** UI-06.
  The audit asked that the Inspector not squeeze a window under 1440 px:
  it opens as an overlay, opens narrower, or starts closed there. Closed
  at the start is the simplest of the three and keeps the Inspector a
  dock. An overlay would cover the field the Inspector describes. The
  window's own first size is 1400 px wide, so a first start shows no
  Inspector, also on a wide screen. The app does not hide an open
  Inspector when the user makes the window narrower.
- **Decision:** the Inspector opens 320 px wide (`theme.INSPECTOR_WIDTH`;
  it was 380 px). **Why:** UI-56. Its labels and a wrapped line of help
  fit 320 px. 380 px held one line of placeholder text.
- **Decision:** an embedded Scenario form that scrolls itself (the
  Environment form, a spacecraft's sections) keeps its scroll areas as
  wide as the page. The form inside each scroll area is capped at
  `CONTENT_MAX_WIDTH_PX` and keeps the left edge
  (`scenario_editor._cap_form`), as on the Run page. A form that does
  not scroll (a ground station) is capped whole, as before. **Why:**
  UI-56. The cap was on the whole form, scroll bar included. At 1920 px
  the scroll bar stood 960 px into the page, and a 220 px strip that
  belonged to nothing lay between it and the Inspector. The form keeps
  its width; the blank is now part of the page, and the scroll bar sits
  beside the Inspector.
- **Decision:** the layout version is 6. A layout saved with version 5
  is ignored, and the window opens with the default layout. **Why:** the
  docks have their own title bars and the Inspector a new width. An old
  layout would keep the 380 px Inspector. `restoreState` refuses another
  version without an error (a test opens a version 5 layout).
- **Decision:** each dock has its own title bar, `app_shell.DockTitleBar`:
  the title (it follows the dock's title, "Problems (3)"), then Float and
  Close as compact tool buttons (28 px) with 16 px Lucide icons. Float
  uses `external-link` and reads Dock (`square-arrow-down-left`) while
  the panel floats, the icons of a view's own window (`gui.breakout`).
  Close uses `x`. The tooltip and the accessible name name the panel:
  "Float Inspector", "Close Inspector (Ctrl+I)". The buttons take Tab
  focus and Space. **Why:** UI-39. Qt's own buttons were about 10 px
  and had no tooltip. No new icon file is needed.
- **Decision:** a toast sits in the work area, the main window's central
  widget: at its bottom right, above the status bar and a docked
  Problems panel, left of the Inspector. Its stack moves up 4 px at a
  time until it covers no control (a button, a field, a drop-down list,
  a tab bar or a label with a link, with 4 px to spare). With no free
  place it stays at the bottom. It looks again when the window or the
  work area changes size, and every 150 ms while a toast shows. A click
  on a toast goes to the widget under it. A toast is as wide as its text
  on one line, at most 360 px. **Why:** UI-54. The "New blank scenario"
  toast covered the guide's "Mission sequence" link at 1280 x 720. The
  toast was placed before the page it announced was shown; the check
  runs again after the page is laid out and while the toast shows, so a
  page laid out or scrolled later does not end under it. Scroll bars,
  tables, text areas and plots are not avoided: they are areas, and a
  click goes through the toast to them. A toast has nothing to click.
- **Decision:** every status-bar message goes through
  `feedback.show_status`: it is elided in the middle to the room left of
  the permanent entries, and the whole text is the bar's tooltip while
  it shows. `report` uses it, and so do Opened and Saved, which name the
  file only (B5). **Why:** UI-09. A report that named a long path
  ("Exported the mission output to /…/output.csv") was clipped at the
  first entry, so the file name was lost. The middle elision keeps the
  start and the file name. A report keeps its path in the text, and the
  toast and the Log keep the whole message (B5 left error reports so).
- **Decision:** the status bar's run state chip ("No run yet") and its
  problem count ("No problems") show only while a scenario is open.
  **Why:** found in the B7 review; they say nothing when no scenario is
  open. The reference data, Basilisk and Earth orientation entries stay:
  they are about the installation.
- **Decision:** the top bar's Undo, Redo and Save are secondary buttons
  (`variant="secondary"`), as the area headers' commands since B7. Run
  stays the one accent button. **Why:** found in the B7 review; they
  read as frameless words beside the framed area commands.
- **Decision:** the style sheet sets `qproperty-indent: 0` on section
  titles (`QLabel[role="section-title"]`, `QLabel#sectionTitle`).
  **Why:** found in the B7 review. A title's vertical padding gives the
  label a frame, and a label with a frame and the default indent (-1)
  indents its text by half an "x" (4 px). "Appearance" started 4 px right
  of the line under it. A group box's title already started at the page
  inset; its glyphs are bolder, about 1 px.

## One table style, no cut headings (UI audit B9, 2026-11-19)

- **Decision:** Reports › Exports and the Reference data window fit
  their columns to the view's width (`DataTable.set_fit_width`,
  `data_table.fit_widths`). Each column gets its content's width when
  all fit. Else the widest columns are cut to one width, never below
  their heading's width, and their texts are elided. **Why:** UI-27. At
  1280 px the Exports table scrolled sideways and its last column was
  out of view. Cutting the widest columns to one width keeps the short
  columns ("Last written", "Default destination") whole. Proportional
  shrinking would elide every column. The Reference data window had its
  own pixel caps per column (B4); the shared rule replaces them.
- **Decision:** a cell whose text is elided shows the whole text on
  hover. A cell with its own tooltip keeps that tooltip. **Why:** UI-27
  asks for elided text with a tooltip. One delegate does it for every
  `DataTable`, so no view writes a tooltip per cell.
- **Decision:** the elision of Reports › Exports stays in the middle, as
  in every `DataTable`. **Why:** the end of a "Made in" path is the
  button that makes the export ("… › Save PNG..."). The middle keeps the
  area and the button.
- **Decision:** the remark "The files are the same as in 1.1.0, byte for
  byte" over the Exports table is gone. The line now says what the table
  lists and how to open a view. **Why:** UI-27. The remark was a
  developer's note. The export tests keep the files byte-identical; the
  user needs no version number for that.
- **Decision:** a `DataTable` row is `theme.ROW_HEIGHT` (26 px) high, a
  row with a second line 26 px plus a line of the monospace font. Qt's
  own height was about 30 px. **Why:** the design rule is "table rows
  26 px"; Settings › Keyboard and the Budgets grids already used it.
- **Decision:** the kind of a support-data file comes from the class of
  Basilisk's registry it is in (`reference_data.SUPPORT_DATA_KINDS`):
  `EphemerisData` is "SPICE kernel", `AtmosphereData` "atmosphere
  table", and the other six classes have a name each. A class that is
  not named shows "support data file". **Why:** UI-49. B4 named four
  classes and called every other one a SPICE kernel. That was a guess:
  the atmosphere tables were SPICE kernels before B4, and a new class
  would be one again. A test checks that every class of the installed
  Basilisk has a kind.
- **Decision:** the status words of the Reference data window stay
  "Present", "Out of date", "Missing" and "Not downloaded" (B4), each
  with its icon. Covers shows "–" for data without dates and is hidden
  when no file has dates. **Why:** the audit asked for "OK" or "Needs
  attention" or similar words in sentence case; B4's words are more
  exact and already in sentence case. The SPICE kernels' own coverage
  is not read: that needs a SPICE reader in the GUI's inventory.
- **Decision:** the Problems panel's table has the DataTable look
  (`widgets.set_table_look(..., docked=True)`): headings on the left, no
  grid lines, rows at `ROW_HEIGHT`, and no frame of its own (the style
  sheet's `QTableView[role="docked"]`). Its sort indicator and severity
  icons stay. **Why:** found in the B8 review. The table had centred
  headings, grid lines and a frame inside the dock, a box in a box.
- **Decision:** a thermal table's column is never narrower than its
  heading as the style draws it (`QHeaderView.sectionSizeHint`). The
  headings are short, with the unit ("C [J/K]", "cp [J/(kg·K)]",
  "G [W/K]", "L [m]", "A [m²]", "Ac [m²]", "hc [W/(m²·K)]", "cp(T)",
  "k(T)", "G off [W/K]", "σ or half-width", "Tolerance [K]"), and name
  the field in full on hover. A table whose headings still do not fit
  scrolls sideways itself, every value whole; the page does not.
  **Why:** found in the B6 review. With the Inspector open at 1280 px,
  "Capacitance [J/K]" read "Ca…". The short headings make every table
  fit at 1280 px without the Inspector. With the Inspector, the
  conductors (twelve columns) and the nodes (ten) cannot fit even with
  one-letter headings, so they scroll. The heading's size comes from
  the style, not from a font measured in code: the style sheet's header
  font, padding and margins need about 34 px more than the text.
- **Decision:** the Flight Software card names the pointing mode by its
  label ("Pointing mode: Sun pointing"), from `field_text.mode_label`,
  the same labels as the spacecraft's FSW mode field. The code
  ("fsw_mode: sunSafePoint") is the line's tooltip. **Why:** a B4
  left-over, found in the B6 review.
- **Decision:** every other table takes the DataTable look through
  `widgets.set_table_look`: the Budgets grids, Run › History, the
  readouts, the scenario overview's table, the SIL comparison, the
  facet and data-handling editors, the model analyses' observers, the
  3D model's face properties and envelope, the IDM-CIC import's two
  tables and the input differences dialog. The tables whose cells hold
  controls (the face properties, the IDM-CIC import) keep Qt's row
  height. They stay `QTableWidget`s. **Why:** the batch's sweep. Grid
  lines and centred headings were the only differences that a small
  change fixes. Moving them to `DataTable` (copy, column menu, fitting)
  is a larger change for a later batch.

## Distinct series colours and display units in plots (UI audit B10, 2026-11-19)

- **Decision:** the categorical palette is new in both themes. The
  order is indigo, olive, brick, teal, magenta, violet, plum, orchid;
  each slot keeps its hue family in both themes.
  - light on `#FFFFFF`: `#4C32D4 #839A0D #922116 #0AA39C #B40677 #9780F7
    #7D4E9D #D042C9`;
  - dark on `#111418`: `#5B4AEA #929D03 #9D4B46 #15A8AE #BE1099 #B76CE9
    #72579D #C642D0`.
  **Why:** UI-12. Slots 1 and 3 (a plot's x and z) were orchid and
  purple: CIEDE2000 Delta E 18.8 in the light theme and 12.3 in the dark
  theme, and 2.8 in the dark theme with protanopia. The old palette was
  checked for neighbouring slots only. No reordering of the old eight
  colours passes an all-pairs check, so the colours changed.
- **Decision:** the floors. Every pair of the first six slots
  (`palettes.SHOWN_TOGETHER`) has CIEDE2000 Delta E 18 or more with
  normal vision, 10 or more with simulated protanopia and deuteranopia,
  and 7.5 or more with tritanopia (Machado, Oliveira and Fernandes 2009,
  severity 1.0, on linear sRGB). The first three slots (x, y, z) have 30
  or more, and 20 or more with each deficiency. Every colour is 3:1 or
  more against `bg.surface`. Measured minimums: normal 25.1 (light) and
  19.1 (dark); protan and deutan 12.3 and 10.4; tritan 10.3 and 8.1; x,
  y, z 36.6 or more with normal vision and 21.4 or more with each
  deficiency. `tests/gui/test_theme.py` checks the floors with its own
  CIEDE2000 code, which it checks against Sharma, Wu and Dalal's (2005)
  test data. **Why:** six is the most series a standard plot shows in
  their own colours: x, y and z, a quaternion's four parts, four
  reaction wheels, the event timeline's six kinds. A Monte Carlo plot
  draws its runs in one colour. CIEDE2000 18 is a difference that reads
  at a glance on a thin line. The deficiency floors are lower because a
  simulated deficiency at severity 1 removes one colour axis; the
  legend stays the second cue.
- **Decision:** the palette also passes the data-visualisation
  validator (OKLab, the same CVD model) in both themes: for adjacent
  pairs of all eight slots and for all pairs of the first six; the
  lightness band and the chroma floor too. The earlier rules stay:
  OKLab Delta E 15 or more between neighbouring slots, and 8 or more
  from every status colour and the accent (the search used 9, and kept a
  colour closer than 15 to a status colour only with a hue 15 degrees
  away). **Why:** the status colours take red, orange, amber, green and
  sky blue, and the accent takes blue. The search ran on an OKLCH grid
  with these rules, then took the best six for the light theme and the
  same hue families for the dark theme.
- **Decision:** the 3D View and the live map take the dark steps for the
  spacecraft in both themes (`palettes.depicted()`). **Why:** they draw
  on black space and on the Earth's image in both themes. The light
  steps are made for white: the new light indigo has 2.7:1 against
  black. Every dark step has 3.5:1 or more against black.
- **Decision:** a position (`position_N`) stays in m and velocity and
  delta-V in m/s in both Plot units choices. Altitudes and semi-major
  axes stay in km in the display units. **Why:** the owner's rule
  (HISTORY, "Result plots: titles/axes/legends ... a per-category unit
  policy"): "delta-V shall always be displayed in m/s"; "altitudes,
  semi-major axes shall be displayed in km"; "state vector elements
  shall be displayed in meters for position and m/s for velocity". The
  display units are the default, so a km position would break the rule
  for every user. UI-12 called the m axis a defect; the review found
  that the setting's name was wrong, not the plot. A first version of
  this batch showed position in km; it was reverted before the merge.
- **Decision:** the display choice is called "Display units (altitudes
  in km, °, h)" (it was "Display units (km, °, h)"). Its tooltip lists
  the units in full: altitudes, semi-major axes and distances in km,
  position in m, velocity and delta-V in m/s, angles in degrees, elapsed
  time in hours. **Why:** the old name promised km for every length. The
  new name is short enough for the 320 px drop-down list without "…"
  (207 px of text at the default font; the test checks it is whole).
- **Decision:** with the display units a body rate and a gyroscope show
  in deg/s and a wheel speed in RPM; "As recorded" shows rad/s. **Why:**
  the setting says angles in degrees. RPM is the unit of the wheel's own
  fields (`Omega_max`, the wizard's wheel biases). Small quantities keep
  m in both choices: the navigation errors, the relative semi-major axis
  and the ROE diagram's metres.
- **Decision:** the Mission sequence Output table takes the same display
  units as the plots but does not follow Plot units. **Why:** it is a
  table, not a plot; its CSV export is SI.
- **Decision:** the Thermal plots on screen follow Plot units on their
  time axis: hours, or seconds as recorded. Temperatures stay in °C and
  heat in W: the thermal CSV files hold them so. The exported SVG and
  PNG keep hours (T-31), byte for byte. **Why:** one choice for every
  plot; the exports stay fixed.
- **Decision:** a plot's axis title writes its unit through
  `units.axis_title`: "Inclination [°]", "Torque [N·m]", "Charge [Wh]";
  "[-]" stays for an axis without a name. The readout takes the same
  form. **Why:** the plots were the last place that showed "deg", "N*m"
  and "W*hr" (UI-35). Only the display changes.
- **Decision:** End of Life's altitude chart draws perigee and apogee in
  the first two categorical colours, adds "Re-entry altitude" (dotted)
  to its legend and titles its axis "Altitude [km]". **Why:** the
  perigee line was in the accent, which is for the primary action and
  selection only; the dotted line had no name; the axis said only "km".
- **Left as it is:** the Results plots' event bands take the timeline's
  kind colours at 16 % opacity, so a band can share a hue with a line.
  The bands are named in the band note and lie behind the lines. The
  timeline draws model-analysis, thermal and plan kinds in the accent.
  A nearly constant series (template 01's osculating inclination, which
  moves by 1e-11 degrees) gets tick labels such as "97.03000000000399":
  the axis shows no offset or exponent notation by an earlier user
  request. All three are listed for a later batch.

## Home, command palette, run pages, log and dialogs (UI audit B12, 2026-11-19)

- **Decision B12-1:** the window writes a path with "›" only. The
  strings of the Run page, the action tooltips and the Reference data
  card use "›". A command palette entry keeps "Category > Command" as
  its key (`PaletteEntry.label`) and shows it with "›"
  (`PaletteEntry.shown`). An engine message keeps ">"; the Problems
  panel shows it with "›" (`workspace_panels.window_path`). **Why:**
  UI-23 and UI-40 found ">" and "›" mixed. The palette's key is read by
  DESIGN.md's shortcut table test and about 60 test lookups; showing
  the key with "›" changes what the user sees and no test's way to an
  entry. The engine's messages are in the golden files and the command
  line, which stay as they are.
- **Decision B12-2:** Home's recent list holds the scenario files
  opened or saved, as before. A template opens unsaved (Save goes to
  Save As), so it is listed once it is saved; its card stays on Home.
  The empty state says so: "A scenario file you open or save is listed
  here. A template opens unsaved: save it (Ctrl+S) to list it." The list
  follows an open or a save at once. **Why:** UI-32. After template 01
  opened, the list said "No recent scenarios yet", which read as a bug.
  Listing the template would put a built-in file, which the app keeps as
  shipped, beside the user's files, and its card is already on Home.
- **Decision B12-3:** a template card has no buttons. It shows its title
  and kind and is as tall as they are. Open template in the details, a
  double-click or Enter on the card open the template. The details'
  second button is "Customize and open...": the wizard first, then the
  result opens unsaved. **Why:** UI-38. The card's Open and Customize...
  showed on the card under the pointer and kept their room on every
  other card, so the lower third of each card was blank, and they
  repeated the details' two buttons. The earlier reason for a Customize
  per card ("users missed a single Customize button gated on a
  selection") was about the old list, where the button sat under the
  list; the details now show the selected template's description beside
  the cards, with the button next to it.
- **Decision B12-4:** the selected card's edge is the accent, 2 px wide,
  the focus ring's width. **Why:** UI-38. The 1 px accent border on the
  selected surface did not show.
- **Decision B12-5:** a palette row shows the shortcut in a column of
  its own at the right, in the monospace font (`_EntryDelegate`), and
  under a disabled command the reason it is off, which is also its
  tooltip. The reason is the registry's (`ActionRegistry.set_available`),
  else the "Off:" line of the action's tooltip, else "Not available
  now.". The window now gives a reason for every command it disables:
  no scenario open, nothing to undo or redo, no run going, a run being
  cancelled, a run going, a view without a window of its own. **Why:**
  UI-40. The shortcut was joined to the name with spaces, and a
  disabled command was grey with no reason; most commands were disabled
  with `setEnabled` and no reason.
- **Decision B12-6:** a run's progress lines ("run_live: x% complete")
  are DEBUG records. **Why:** UI-31. About 60 INFO lines per run buried
  the records that matter in Run › Log. The status bar shows the
  progress; the log file takes DEBUG and keeps the lines. The command
  line's `run` uses `SimulationService.run`, not `run_live`, so its
  output is the same (checked with the two-body validation scenario).
  No test read the progress records.
- **Decision B12-7:** About is a small window of the app
  (`gui.about_dialog.AboutDialog`): the name, the version, the Basilisk
  version and the licence (a row each, the value in the monospace font),
  the licence lines and the Third-Party Licences and User Manual
  commands as buttons; Close is its default button. It is
  not modal and is kept when closed, as the manual and the licences.
  **Why:** UI-48. `QMessageBox.about` was a plain box in Qt's look, and
  a modal dialog is only for a destructive confirmation or a wizard.
- **Decision B12-8:** a confirmation keeps `QMessageBox.question`; the
  application style gives every message box the theme's status icons
  (`theme/style.py`, `MESSAGE_ICONS`): the caution sign for a
  confirmation and a warning, the critical sign for an error, the info
  sign for a note, 32 px. **Why:** UI-48. Qt's "?" icon is not the
  theme's. The style changes every confirmation of the app at once, and
  the 67 tests that answer `QMessageBox.question` keep their way to it.
- **Decision B12-9:** the Problems panel lists the plausibility warnings
  while the scenario has an error, under the errors. A "check not run"
  line is left out while there is an error. **Why:** UI-50. The
  warnings were computed only when the scenario validated, so they went
  with the first error. A check that cannot run on a scenario with an
  error says nothing of use until the error is fixed.
- **Decision B12-10:** Reports › Exports wraps its text columns
  (`DataTable.set_fit_width(wrap=...)`): a wrapped column is never
  narrower than its longest word, the time last written keeps one line,
  and each row is as tall as its tallest cell. **Why:** found in the B9
  review. With the Inspector open at 1280 px most "Made in", "Format"
  and "Provenance" cells were elided in the middle. The table is short
  (21 rows), so taller rows cost little, and every entry reads whole
  without hover.
- **Decision B12-11:** the Budgets grids fit their width
  (`EditableTable.fit_columns`, the B9 rule): long headings are two
  lines, the name above the unit ("Average" over "[W]", "Mass" over
  "source"), and the three grids under the equipment list share their
  row by what each needs (`EquipmentPage.fit_lower`) until the user
  drags a divider. Budgets › Power's tables fit their width too, with
  their long headings on two lines. **Why:** found in the B9 review. At
  1280 px the power modes and the power settings scrolled sideways in
  equal thirds of the row. Now no grid scrolls sideways at 1280 px, with
  the Inspector open or closed. Two cases can still scroll inside the
  table, never the page: a system mode grid with many items (one column
  each), and Budgets › Power's table of the items (twelve columns) with
  the Inspector open, whose headings alone are wider than the page.

## Thermal page values, studies and header (UI audit B11, 2026-11-19)

- **Decision:** the Summary tab stays a `DataTable` with every case and
  node, and gains a **Status** column (an icon and words: Within limits,
  Below or Above operating, Below or Above survival, No limits). The
  operating range is one column ("-30 to 50"). **Why:** UI-07 asked for
  each case's values with their margins and a status. Template 33 has 24
  case and node rows; DESIGN.md puts a long or sortable list in a
  `DataTable` and keeps `ValueTable` for a few rows. Survival comes
  first: a node outside its survival range is critical even when the
  operating range is also broken. The two range columns made the table
  scroll sideways beside the Inspector.
- **Decision:** the solution checks of each case (start, orbits to the
  periodic state, energy residual and throughput, half-step change) are
  a `ValueTable` on the Notes tab, one row per case, and the beta angle
  range is a `ValueSheet` beside it. The status line says only "Solved n
  cases.". **Why:** UI-07. These values were sentences of numbers in the
  status line and in the notes. Four cases are a few rows.
- **Decision:** a note that several cases share is shown once, after
  their names. A note that starts with its case's own name loses that
  name; a note that starts with another preset's name says "the cold
  environment". A case override is named by its parameter label ("cold
  safe mode: Dissipation avionics: power set to 15.0 W"). Units in the
  core's sentences go through the new `units.in_text`. **Why:** UI-07
  ("nominal: nominal:"); the cold note was shown twice, once for cold and
  once for cold safe mode. The core's notes and the files keep their
  text: only the window changes.
- **Decision:** one **Save...** button with a menu: Everything to a
  folder..., Temperature plot as SVG..., Temperature plot as PNG....
  The actions call the same `save` and `save_plot` as before. **Why:**
  UI-44 (three save buttons). A menu keeps every format one click away;
  a "Save..." dialog that asks for the format would add a step. The
  results' Export all... already uses a button with a menu.
- **Decision:** the findings count is a `badges.StatusBadge`: the
  status's icon and words on its soft tint, painted from the tokens and
  repainted on a theme change. **Show in Problems** is a plain
  (secondary) push button. It still emits `problems_requested`, which
  the main window connects to `MainWindow.show_problems`. **Why:**
  UI-44. The brief names `MainWindow.reveal_problems`; this app's method
  is `show_problems` (the status bar and the top bar use it), so no
  second name was added. From the Thermal page in its own window,
  `show_problems` now also brings the main window to the front, where
  the panel is.
- **Decision:** the study parameter is a drop-down list of the thermal
  model's parameters (`sweeps.default_parameters`, the ones Sensitivity
  varies), each by its record and field with its unit; the path is the
  entry's tooltip. The last entry, **Other parameter, by its path**,
  shows the old text field. **Why:** UI-30. The text field was the only
  way to sweep a parameter outside that list (`environment.albedo`, a
  node's capacitance), as a case's overrides do; the brief keeps an
  advanced path when a feature needs it. The labels keep the user's
  names ("Face array +y, side +z: absorptance").
- **Decision:** Heat flows: the table asks for its rows' height and the
  plot takes the rest, at least 160 px (`_FLOW_PLOT_MIN_PX`). Short of
  room the table gives way, down to two rows. At 1280 x 720 the table
  shows four of template 33's six rows (two before). **Why:** UI-21. A
  plot lower than 160 px has no readable axis.
- **Decision:** a heat-flow column that is zero for every node of the
  case is hidden; the header's context menu shows it again, and the
  section title's tooltip says so. **Why:** template 33 has ten
  columns. Their headings alone (two lines, the unit under the name)
  need 961 px; the page has 880 px beside the Inspector at 1280 px. The
  zero columns (radiation between nodes, heaters off) carry no
  information. The CSV files keep every column.
- **Decision:** `units.label` keeps a unit on a heading's second line
  ("Cold margin\n[K]"). **Why:** it joined a known unit back onto the
  first line, so a two-line heading was one line. The Timeline's
  headings were written with the unit on a second line for narrow
  columns and now show so.
- **Decision:** a record table's numeric columns are those that hold
  numbers. **Why:** the node and heater names were right-aligned as
  numbers.
- **Left as it is:** a sweep's table has a column per node and extreme
  (13 for template 33) and scrolls sideways at 1280 px. DESIGN.md keeps
  a table of numbers to compare whole, scrolling (Output, Monte Carlo).
  The status line's failure messages from the solver stay as the solver
  writes them.

### B11 follow-up (2026-11-19)

- **A tab never sets the thermal page's least width beyond its header row.** The page's own window must fit on a small screen beside the main window, also with Windows' fonts. A wide table without a scroll area takes an Ignored horizontal size policy instead. The design keeps scroll areas out of the thermal page (`test_thermal_views`).
- **A QObject that Qt calls back (an event filter, a timer) keeps no Python attribute** when only a Python attribute of another object refers to it. It reads what it needs from Qt: its parent, or a Qt property. The toast follower is the first such object.

## Small plot items (2.13.1, SRelD K-46, 2026-11-20)

The B10 section above left three points open; the UI audit added a
fourth. Only the window changes. The series, their columns, the CSV,
JSON and HTML exports and the golden files are unchanged.

- **Decision K46-1:** the Results plots' event bands and mode-change
  lines take one neutral token, `chart.band` (`text.secondary`: light
  `#50565F`, dark `#A1A8B3`), drawn at 16 % behind the lines as before.
  **Why:** a band in a series hue can be read as a line. A grey is the
  simplest colour that no series, status colour or the accent uses
  (`tests/gui/test_plot_items.py` checks it in both themes). The kind of a band is named by the
  Events buttons above the plots, which switch each kind; the Timeline
  keeps its colour per kind. The mode line is drawn solid and keeps 3:1
  against the surface (`CONTRAST_PAIRS`).
- **Decision K46-2:** the Timeline draws the model analyses', thermal
  limits' and plan's events in `chart.event` (also `text.secondary`),
  not in the accent. **Why:** the accent is for the primary action,
  selection and focus; the categorical slots 7 and 8 are too few for
  three groups, and the palette is never cycled. Each group has its own
  named row and check box, so colour is not the only cue. The time
  cursor stays in the accent: it is a selection.
- **Decision K46-3:** a Results plot's y axis includes, through
  Plotly's `autorangeoptions.include`, a span of at least `1e-6` of the
  largest value it shows, centred on the data
  (`results_widget._MIN_Y_SPAN_SHARE`). **Why:** the axis shows no
  offset or exponent notation (an earlier user request), so a series
  that moves by 1e-11 deg read "97.03000000000399". With the floor the
  labels have about seven significant figures ("97.03001"). A relative
  floor keeps real changes visible: 1e-6 of a 6,928 km semi-major axis
  is 7 m. Autorange stays on, so zoom and double-click still work, and
  the plotted values are the series' own.
- **Decision K46-4:** a reaction wheel's line, its readout row, its
  compared run's line and its Compare column are named after the wheel
  in the scenario (`engine.series_names.device_column_labels`: the
  spacecraft's `reaction_wheel` actuators in listed order, as
  `engine.service` records `wheel_0`, `wheel_1` ...). The main window
  hands the labels to the Results tab when a run starts, with the
  featured series; a compared run and the Compare tab read their own
  run's scenario. **Why:** the window should name the device the user
  named; the columns stay `wheel_N`, so the CSV files and the golden
  files do not change. Thruster and torque-rod columns keep their
  indices for now (not in the audit's list).
- **Noted:** a plot saved as PNG or SVG from the window is a picture of
  the window's figure, so it shows the grey bands and the wheel names.

## Small window fixes (2.13.1, 2026-11-20)

- **Decision:** a fitted `DataTable` without a sort indicator may squeeze
  a column to the heading's width as the style draws it
  (`sectionSizeHint`). The 12 px of the sort indicator count only when
  the table shows one. With room, a column keeps its old width. **Why:**
  Budgets › Power's table of the items and the thermal sweep table
  scrolled sideways at 1280 px. Of the fitted tables, none shows a sort
  indicator.
- **Decision:** Budgets › Power's table of the items writes every
  number's heading in two or three lines, the name above the unit, as
  the Equipment grids do (B12). **Why:** with one-line headings the
  twelve columns needed 988 px; the table has 879 px beside the
  Inspector. Two-line headings needed 821 px on Linux, and Windows CI
  showed that this was not enough there. With "Duty", "With margin" and
  "Peak with margin" on one more line they need 786 px on Linux.
- **Decision:** a fitted `DataTable` whose headings do not fit even at
  their least widths scrolls sideways, and its stretching column then
  keeps its whole width (Interactive mode). With room again, the column
  stretches. **Why:** in Qt's Stretch mode an overflowing table
  squeezed the stretching column below its heading (Budgets › Power's
  "Item" on Windows CI, PR #300).
- **Decision:** a sweep's heading is the node's name over its extreme
  and unit ("radiator" over "min [°C]"). The table keeps a column per
  node and extreme. **Why:** template 33's 13 columns needed 1257 px;
  the page has 1005 px beside the Inspector. Now they need 947 px. A
  table in rows of node and value was not chosen: it changes how users
  read a sweep. B11's "Left as it is" for this table no longer holds.
- **Decision:** Run › Thermal › Notes writes the solution checks with
  three significant figures and keeps a trailing zero ("4.90e+03").
  **Why:** `:.3g` dropped it, so one column had two and three figures.
- **Decision:** Home shows a template description's " -- " as " – "
  when it shows the text. The template files keep "--". **Why:** B4
  changed the window's own strings, not the templates; the golden files
  and the command line read the files. A name ("bus--avionics") and a
  flag ("--out") keep their hyphens.
- **Decision:** a thermal heading writes an energy unit "Wh"
  (`units.shown("W*h")`), as the other energy columns do. **Why:** B4
  (UI-35) chose "Wh"; the thermal headings had their own map.

## Background-thread crashes (SRelD K-44, 2026-11-20)

- **Garbage is collected on the GUI thread only** (`gui/background_threads.py`).
  The app turns the automatic collection off at start, and a timer on the
  GUI thread collects the generation that is due by the collector's own
  thresholds. **Why:** Python collects in the thread that passes the
  threshold, and the collection frees every unreachable cycle. A worker
  that parsed a file or wrote one so destroyed widgets of the GUI thread,
  and the process crashed (CI on Windows: an access violation in
  `_SpaceWeatherWarmUp`, "Garbage-collecting"). A script with a worker
  that makes dataclass rows crashed five runs in five on Linux, with the
  same frames; with the collector, none in four. Without it, 214 of 264
  collections during the warm-ups and a run of `two_body_validation` ran
  in worker threads.
- **The collector checks every 20 ms.** **Why:** between two checks the
  young generation takes all that the threads allocated, and one
  collection takes it all. At 100 ms single collections took up to
  91-189 ms; at 20 ms the largest generation-1 collection took 44-70 ms
  in three runs (the machine had a load of 13), and the largest pause of
  all was 50-54 ms (start-up's own `gc.collect()`). Without the collector
  the largest pause was a full collection of 112-219 ms. The check costs
  microseconds when nothing is due. **Trade-off:** a generation-1
  collection can hold the GUI thread up to about 70 ms, above the 50 ms
  rule. Before, a worker's collection held the interpreter, and so the
  window's Python code, for as long.
- **An explicit `gc.collect()` still runs where it is called.** The app
  calls it only on the GUI thread and in the Monte Carlo child process.
- **The tests collect on the GUI thread while a window test runs**
  (`tests/gui/conftest.py`), and give the automatic collection back after
  each one. **Why:** the tests without a window run with no event loop, so
  no timer would collect for them.
- **The start-up warm-ups and a run's first import of the engine hold one
  lock** (`FIRST_IMPORTS`). **Why:** the backlog asked for the warm-ups to
  be serialized. CPython's import is thread safe, and the crash was the
  collection, not the imports. The lock costs a run started in the first
  second at most the rest of the warm-up (under 1 s); one warm-up thread
  would have changed a test's expected threads for no gain.
- **Two more callbacks keep no Python attribute** (the B11 rule): the page
  tree's refit filter and the tool button icon keeper. No Python reference
  kept them; each now reads its parent (and the icon from a Qt property).

## Monte Carlo plan (2026-11-21)

Step 0 of the owner's item "make the Monte Carlo features useful". The
inventory, the gaps, the phases and the open questions are in
[`developer/monte-carlo-plan.md`](developer/monte-carlo-plan.md). No
code changed. The decisions below are defaults for phase A; an answer
of the owner to the plan's questions Q1 to Q5 replaces them.

- **Decision MC-1:** phase A is four items: per-run outcomes (A1),
  requirements with the probability of not meeting them (A2), reproduce
  one case (A3), and the draws of crashed runs (A4); about 11.5 hours in
  two pull requests. **Why:** together they answer the questions an
  engineer asks of a batch ("does it meet the requirement, how sure am
  I, which case fails, why") at the lowest cost; more dispersions (phase
  C) cost more and add nothing until a batch can be judged.
- **Decision MC-2:** a run's outcomes are its Overview figures
  (`engine/run_summary.overview_figures`), computed in the worker and
  returned through Basilisk's `RetentionPolicy.addRetentionFunction`
  (Basilisk 2.12.0) into the run file the app already reads. **Why:**
  the figures are tested and have calculation traces; a case then reads
  the same as a single run; no Basilisk change and no new file.
- **Decision MC-3:** the batch summary keeps format 1; outcomes,
  requirements and the draws of crashed runs are optional keys, and
  `run_table`'s default columns, `final_spread` and `summary_lines` do
  not change. **Why:** older versions still open a new batch, a new
  version opens an old one, and the golden files of templates 09 and 25
  stay byte-identical.
- **Decision MC-4:** requirements live in the scenario, as
  `monte_carlo.requirements`, with scenario schema version 6 and a
  migration that only sets the version, as B-01 did for version 5.
  **Why:** a requirement is shared with the dispersions it is judged
  against; the version step marks files that older versions refuse.
- **Decision MC-5:** the probability of not meeting a requirement is
  shown as k/N and as the exact one-sided Clopper-Pearson upper bound
  (Biometrika 26(4), 1934), computed by bisection on the binomial sum,
  registered as the model `monte_carlo.probability_bound`
  (`clopper_pearson`). The confidence is a required field of each
  requirement, with no default in the code. **Why:** the exact bound
  needs no table and no new dependency; a default confidence would be a
  number without a source (the plan's rule), so the user states it.
- **Decision MC-6:** a crashed run counts as not meeting every
  requirement and is shown apart; a run that did not record the outcome
  is "not evaluated" and is left out of N. **Why:** the conservative
  reading; a crash hidden from the count would make the bound too low
  (Q1).
- **Decision MC-7:** a case is reproduced from its `run<N>.json` (JSON,
  never the pickles, S-04), applied with Basilisk's
  `SimulationExecutor.applyModification`, and refused when the
  scenario's hash differs from the batch's. **Why:** it is the
  controller's own data and setter, so the case is the same; a changed
  scenario would give a different case under the same number (Q3).
- **Decision MC-8:** the batch seed (SRelD K-24) waits for phase B
  (B1). **Why:** today's draws are reproducible; a different seed is
  needed for a second, independent batch, which is less urgent than
  judging one batch (Q2).
- **Decision MC-9:** every new parameter and statistical method goes
  through `config/parameters.py` and `config/models.py`, with its
  source; a value without a source is "TBD". The brief's `settings.py`
  and `model_choices.py` are these two files. **Why:** CLAUDE.md and
  the transparency audit's registry (item 6).
- **Decision MC-10:** `monte-carlo` exits with 5 (ICD-02, "the check did
  not pass") when a requirement with an allowed probability is not shown
  met; 3 (a run failed) comes first. **Why:** a script can tell a batch
  that ran but does not meet its requirement from one that failed; 5
  already means this for `reproduce`, `fsw-status` and `sil` (Q5).

## Monte Carlo phase A, part 1: outcomes, crashed runs, requirements (2026-11-21)

Items A1, A4 and A2 of [`developer/monte-carlo-plan.md`](developer/monte-carlo-plan.md),
built as the plan says. The owner answered Q1, Q2, Q4, Q5 and Q8 for this
work. **MC-11 to MC-15 are provisional: the owner may change them.** They
confirm MC-6, MC-8, MC-5 and MC-10, and keep the "mean ± 3 sigma" lines.

- **Decision MC-11 (provisional, the owner may change it; Q1):** a
  crashed run counts as not meeting every requirement and is shown
  apart: it is in N and in k, and the Requirements table has the column
  "Of which crashed". **Why:** the owner's answer; it is MC-6, the
  conservative reading.
- **Decision MC-12 (provisional, the owner may change it; Q2):** the
  batch seed goes to phase B. Schema version 6 holds the requirements
  only. **Why:** the owner's answer; it is MC-8.
- **Decision MC-13 (provisional, the owner may change it; Q4):** the
  confidence is required per requirement, with no default in the code
  or in the editor. The limit has no default either. A new requirement
  in the editor starts with both "Not set"; the list and the draft
  scenario hold it as it is, and the scenario's check refuses it and
  names the field (the Problems panel shows it). For this, the editor
  checks only the batch's settings and dispersions as they are typed
  (`MonteCarloConfig.validate_settings`); `validate` checks the
  requirements too. **Why:** the owner's answer, and a number without a
  source is not allowed (MC-9). A form that refused every edit until the
  confidence was set would force one order of typing.
- **Decision MC-14 (provisional, the owner may change it; Q5):**
  `monte-carlo` exits with 5 when a requirement with an allowed
  probability is not shown met; 3 (a run failed) comes first. Checked
  before use: ICD-02 and `cli.py` give 5 (`EXIT_CHECK_FAILED`) to "the
  command ran and its check did not pass" (`fsw-status`,
  `sil --max-error`, `reproduce`), and no command gives 5 another
  meaning. So 5 is free for this use and fits the scheme. **Why:** the
  owner's answer; it is MC-10.
- **Decision MC-15 (provisional, the owner may change it; Q8):** the
  thermal and operations batches keep their "mean - 3 sigma" and "mean +
  3 sigma" lines for now. Percentiles are phase B (B3). **Why:** the
  owner's answer.
- **Decision MC-16:** how A1, A4 and A2 are built, where the plan leaves
  the choice open. Each choice has its reason:
  - The requirements' evaluation and the bound are a new module,
    `engine/monte_carlo_requirements.py` (Basilisk-free), mapped to
    SRS-F-13 in the SDD. **Why:** `monte_carlo_results.py` reads and
    saves the summary; the statistics of a requirement are a separate
    concern with their own tests.
  - The summary also keeps `probability_bound`, the bound's model, next
    to `requirements`. The plan lists only `requirements`. **Why:** as
    `spread_statistic`, an opened batch then reads with the model it was
    run with, also after a second model is added.
  - The binomial sum starts at its largest term (the mode, or k) and
    goes outward. **Why:** the plan says "bisection on the binomial
    sum"; summed from i = 0, the first term underflows for a large
    batch and a small p. From the largest term the sum has about
    sqrt(N) terms that matter and no term underflows unless the whole
    sum does.
  - The second reference check of the bound is an independent
    computation, not a table: the regularized incomplete beta function
    I_p(k + 1, N - k), the bound's other form, computed exactly in
    rational numbers at the bound, must equal C. **Why:** SciPy is not in
    the `dev` extra, and no table of the bound was read here: a tabulated
    value from memory would be an invented number.
  - A run that cannot read its outcomes (an error in a figure) keeps
    none and is logged; the run is not failed. A requirement then counts
    it "not evaluated". **Why:** the run itself succeeded; failing it
    would hide its orbit.
  - Basilisk's data writer writes one file per key of the custom data
    (`spacemissionstudio_outcomes.data`, `..._outcome_units.data`). They
    are batch files (`BATCH_FILE_PATTERNS`), so `--overwrite` replaces
    them. **Why:** found by `test_an_earlier_batch_is_replaced_only_with_overwrite`.
  - The Runs table (GUI and CSV) adds the outcome columns, the crashed
    runs, "Status" and "Meets all requirements" only when the batch has
    them, after the existing columns. `run_table`'s default is
    unchanged. **Why:** an older summary shows the table it showed
    before, the existing columns keep their places, and the golden files
    read the default. The CSV writes a missing value as `nan`, as before.
  - The crashed runs are `failed` of the summary: the runs the
    controller reports failed, and in a finished batch the runs whose
    file cannot be read. A cancelled batch has none (A4). **Why:** the
    same list the "Failed" tile counts.
  - The editor's Requirements list switches between the list and its
    empty state itself, not through `widgets.EmptyStack`. **Why:**
    `EmptyStack` follows the list model's `modelReset`, which a
    `QListWidget` emits while it is destroyed; when the Monte Carlo group
    was the first widget of a test process, that reached the half
    destroyed stack ("Slot 'EmptyStack::' not found"). The same happens
    on `develop` with a bare `EmptyStack` under a `FormGrid` as the
    first test of a process. `EmptyStack` itself is not changed here: the
    other lists use it, and the fix belongs to its own change.
    *Superseded in 2.14.1* (below): `EmptyStack` is fixed, and the list
    uses it again.
  - The main window connects the Requirements tab's empty-state action
    to a bound method, not a lambda. **Why:** a lambda that holds the
    window kept a closed window alive (`test_a_closed_window_is_freed`
    failed); the B11 rule.
  - No new keyboard shortcut or palette entry. **Why:** no new frequent
    action. The Requirements tab is a tab of the Monte Carlo view, and
    a requirement is edited where the dispersions are.

## Monte Carlo phase A, part 2: run one case again (2026-11-21)

Item A3 of [`developer/monte-carlo-plan.md`](developer/monte-carlo-plan.md),
built as the plan says. The owner answered Q3 for this work. **MC-17 is
provisional: the owner may change it.** It confirms MC-7.

- **Decision MC-17 (provisional, the owner may change it; Q3):** a case
  is not run again when the scenario changed since the batch. The check
  compares the SHA-256 of the scenario as it is now
  (`output_provenance.scenario_sha256`: its canonical JSON, the
  dispersions and the requirements included) with `scenario_sha256` in
  the batch's `archive.provenance.json`. The batch already records this
  hash (transparency audit, Phase 2g), so no new record is needed and no
  file format changes for it. The message names both hashes, says why
  (the same case number would be a different case) and says what to do:
  open the batch's own scenario, unchanged (its file is named when the
  batch recorded one), then run the case again. A folder without
  `archive.provenance.json`, or whose record has no hash, is refused
  too: the case cannot be checked. **Why:** the owner's answer; it is
  MC-7. A case of a changed scenario run "with a warning" would show
  numbers that no batch ever had.
- **Decision MC-18:** how A3 is built, where the plan leaves the choice
  open. Each choice has its reason:
  - The case is built by the batch's own creation function
    (`_create_sim`), each entry of `run<N>.json` is applied in the
    file's order with `SimulationExecutor.applyModification`, and it is
    flown by `_fly`, which the batch's execution function now calls too.
    It uses no `model_base_dir`, as the batch uses none. **Why:** the
    same code builds and flies the batch's case and the case run again.
    Measured on template 25 (2 runs, 0.05 days, 145 kept samples, one
    and two processes): the positions agree to 0.0 m and the outcomes
    are equal; the acceptance limit is 1e-6 m.
  - The engine has `prepare_case` (build, apply, start up) apart from
    `replay_case` (that, then the flight). **Why:** the GUI's run worker
    flies the case itself, in chunks (`run_live`, for its progress and
    Cancel) or through `MissionEngine` with its Cancel. Flown in chunks,
    the positions also agree to 0.0 m.
  - `replay_case` returns the `ResultSet` and the Mission Sequence's
    `CommandSummary` (or None), as `MissionEngine.run` does; the plan
    says "the `ResultSet`". `api.monte_carlo_case` returns the
    `ResultSet`, as `api.run` does. **Why:** `--case --out-dir` writes
    what `run --out-dir` writes, the command summary included.
  - NumPy's and Python's global generators are not seeded with the case
    number times 10, as Basilisk's worker does before each case
    (`Controller.py`, `SimulationExecutor.__call__`). **Why:** the app
    draws nothing from them during a run (it uses seeded generators of
    its own: optical navigation, thermal sweeps); every model's noise
    comes from its `RNGSeed`, which `run<N>.json` holds. Seeding them
    would change the state of the whole GUI process.
  - The run's provenance gets `monte_carlo_case`: the batch folder
    (absolute), the case, the batch's scenario hash and the case's RNG
    seeds from `run<N>.json`; `rng_seed_note` says the seeds are the
    case's. It is a new optional field of `RunProvenance`, written only
    when set. **Why:** the plan's record; every other run's record, and
    the golden files, stay as they are; a saved case run opens in an
    older version, which ignores the key (`run_store` keeps the fields
    it knows).
  - `monte-carlo --case N` exits with 1 when the case is refused (an
    input error, ICD-02), 3 when its run fails (a crashed case), and 2
    for `--out-dir` without `--case` or `--case` with `--overwrite`
    (usage errors). `--out-dir` defaults to `results`, as for `run`. The
    refusal is checked before `--out-dir` is made. **Why:** the exit
    codes keep their ICD-02 meanings; a refused case writes nothing.
  - Run This Case is a command of the window's registry
    (`run.monte_carlo_case`, category Run, area Results): the Run menu,
    the command palette, Ctrl+Shift+R, the button under the Runs table
    and the table's right-click menu. It acts on exactly one picked run;
    otherwise it is disabled and its tooltip and palette entry say why.
    **Why:** design rule 5 (keyboard first) and the plan ("shortcut in
    the tooltip"); Ctrl+Shift+R was free and sits next to Run (Ctrl+R).
  - The worker checks the hash and reads the case, not the GUI thread.
    A refusal is the worker's `refused` signal: a warning row in the
    Problems panel, which opens, until another case runs or another
    batch is shown; the Log, a toast and the status bar say it too, as
    for any run that cannot start. Success is the run's toast ("Monte
    Carlo case 7 ran again as Run 3"), and Run › History lists the run
    with the mode "Monte Carlo case 7". **Why:** design rule 6 (file I/O
    in workers) and CLAUDE.md (success a toast, a problem in Problems).
    The window checks the case first, on the GUI thread, with
    `engine.monte_carlo_case` (no Basilisk import; it reads two small
    JSON files and hashes the scenario). A refused case so starts no run
    and leaves the views of the run shown before as they are. The worker
    checks again as a backstop. The window's check cannot see the data
    files a case uses (MC-19): they are known only when the service is
    built, which needs Basilisk. A changed data file is therefore refused
    by the worker (its `refused` signal, the same Problems row), after
    the views of the run shown before were cleared. The user manual's
    Run This Case and the how-to note say so.
  - A case run has no live 3D View; Live plot works. **Why:** the live
    view attaches its probe while the service starts up, and the case is
    started as the batch started it.
  - The worker imports pandas on the GUI thread before the first case,
    as `MonteCarloWorker` does before a batch, for the same race with
    plotly (Windows CI). **Measured here: 280 ms, once per process**,
    the first time a case or a batch starts; the 50 ms target of design
    rule 6 is not met for that one click. **Why:** the race crashed CI;
    the cost is paid once, and not again when a batch ran first.
    *Superseded in 2.14.1* (below): the worker imports pandas, and the
    plots wait for that import.
- **Decision MC-19:** a case runs with the batch's reference data, in
  the batch and when it runs again. Found by the Linux CI of PR #307:
  `test_a_case_run_again_is_the_batchs_case[2]` failed, 4.22 m apart
  after 0.05 days (0 at the first sample, 1.3e-4 m at the second). The
  cause: with `thread_count > 1` Basilisk's Controller runs the cases in
  worker processes (`multiprocessing.Pool`; Python 3.14 starts them with
  `forkserver` on Linux). A worker imports the engine again, so its
  module-level data folders (`spaceweather.DEFAULT_CACHE_DIR`,
  `earth_orientation.DEFAULT_DIR` and the others, computed from the home
  folder at import) were its own, not those of the process that started
  the batch. `tests/conftest.py` sets these folders in the test process
  only. The CI runner had the Earth orientation files installed in its
  real home folder (`earth-orientation --fetch`), so the batch flew in
  ITRF93 and the case run again in the test process in IAU_EARTH.
  Reproduced here with the NAIF files installed in a home folder of its
  own: the same 4.22010968 m; without them, 0 m. A newer space-weather
  download in the worker's home folder has the same effect where the run
  is in its days. Two parts, each with its reason:
  - `run_monte_carlo` keeps the data folders of its own process
    (`monte_carlo.data_folders`: the space-weather cache, the Earth
    orientation, small-body and ITU-R P.676-13 folders, user and system,
    the list `tests/conftest.py` sets) and passes them, as plain text,
    in the creation function's `functools.partial`. `_create_sim` sets
    them first (`apply_data_folders`), in the worker before it builds.
    **Why:** every case must read what the process that starts the
    batch reads. In the app the values are already the same, so no
    result changes; the golden files are byte-identical. The GUI's
    batch child (`gui.monte_carlo_process`, spawned) computes them from
    the same home folder as the window, so it is not changed.
  - Each successful run keeps its data files (`SimulationService.
    _data_files`, as built, before the flight: kind, path and SHA-256)
    in its retained custom data (the same retention function as the
    outcomes, key `spacemissionstudio_data_files`) and in the summary as
    the optional key `data_files` (format 1 still, as MC-3). A case run
    again (`prepare_case`, once the service is built) compares its own
    with the batch's record of that case, by SHA-256 only (a folder that
    moved is the same data), and is refused (`MonteCarloCaseRefused`)
    when a file changed, is missing, or is used only now or only in the
    batch. The message names each file by its kind, both hashes, the
    usual cause ("a newer download" for the space weather) and what to
    do: use the batch's data files, or run the batch again. **Why:** a
    case flown with other data is not the batch's case; with the first
    part alone a download between the batch and the case would still
    give other numbers without a word.
  - Not checked for the data files: a summary without `data_files` (a
    batch made by 2.13.1 or earlier) and a case that crashed (it kept
    no data). **Why:** there is nothing to compare with; refusing every
    older batch would take away Run This Case for it.
  - The data-file refusal of `monte-carlo --case` comes after
    `--out-dir` is checked, with status 1 as for a changed scenario.
    **Why:** the files are known only when the case is built.

## 2.14.1: small fixes (2026-11-22)

Three items of `BACKLOG.md` "Next release". Each choice has its reason.

- **A batch's and a case's worker import pandas themselves, with
  `FIRST_IMPORTS` held** (`background_threads.import_pandas`). This
  replaces the import on the GUI thread of MC-18 and of the 2026-10-28
  fix. **Why:** design rule 6. The first start took 258 to 271 ms of the
  GUI thread; now it takes under 1 ms. `MonteCarloWorker` also imports
  `engine.monte_carlo` with the lock held, as `RunWorker` imports its
  engine (K-44: one heavy first import at a time).
- **The GUI thread's plots wait for an import of pandas in progress**
  (`background_threads.wait_for_pandas`, called where the GUI thread runs
  plotly: the Results figures and their JSON, Compare, the 3D model view).
  **Why:** plotly and narwhals read pandas from `sys.modules` and do not
  wait, so the lock alone does not cover the race: the GUI thread does
  not hold it, and it must not wait for it, since the space-weather
  warm-up holds it too. Python's import waits on the module's own lock,
  so the plot waits only for the rest of that import. **Trade-off:** a
  plot built during the import waits up to about 250 ms (measured
  233 ms); this happens only for a plot drawn in that time.
- **Signals that a child sends as it is deleted reach their owner
  through `widgets.connect_while_alive`**: `EmptyStack`'s model signals
  and every `currentChanged` of a tab or stacked widget connected to a
  method (SRelD K-44). It connects a plain function that holds the method
  weakly. **Why:** Python's collector frees a dropped widget tree one
  wrapper at a time, and shiboken then can delete a child before its
  parent; the child's signal reached an owner whose wrapper was already
  cleared ("Slot 'EmptyStack::' not found", "Slot 'MainWindow::' not
  found"). Python clears weak references before it clears the wrappers.
  A direct connection cannot be guarded: PySide fails before the method
  runs. A disconnect on `destroyed` would be one more direct connection
  of the same kind. A test keeps every such signal on the helper.
- **The scenario editor's tab slot gets the tabs as an argument**
  (`sender=` of the helper). **Why:** `QObject.sender()` is None in a
  call through a plain function.
- **The Monte Carlo editor's Requirements list uses `EmptyStack` again,
  with `fit_rows`**; MC-16's own switching is removed. **Why:** the cause
  is fixed in `EmptyStack`; `fit_rows` as the spacecraft and ground
  station lists (UI-05: a short list is as tall as its rows). Before, the
  list kept no height limit while it had rows.
- **CI runs each reference data download through
  `scripts/retry_download.py`**: four attempts in all, 60 s apart, any
  non-zero exit status tried again, the last status kept. **Why:** the
  ITU server's outage lasted a few minutes; three minutes of pauses
  cover that, and a real failure still fails the step. A retry option on
  the fetch commands would change the CLI (ICD-02) for a need of CI
  only; the script changes no interface and works in bash and
  PowerShell. A kept copy checked by SHA-256 (the backlog's other
  option) needs a cache or a stored file and its own update; the retry
  needs neither.
- **The release workflows' `kernels-status` is not wrapped.** **Why:** it
  checks the installed package with an empty cache and must download
  nothing; a failure there is a fault of the package.

## Monte Carlo phase B, part 1: batch seed, thermal node limits, small fixes (2026-11-23)

Items B1, B4 and B8 of [`developer/monte-carlo-plan.md`](developer/monte-carlo-plan.md),
built as the plan says. The owner answered Q2 for this work: the seed is
phase B and has its own schema step (MC-12). The work ran without
questions; each choice below has its reason.

- **Decision MC-20: the batch seed** (B1, SRelD K-24). `monte_carlo.seed`
  is optional, a whole number from 0 to 2147483647, empty by default.
  - Empty: nothing changes. The creation function draws nothing from
    NumPy's legacy global generator or Python's `random` and does not
    reseed them, so the Controller draws from the state its own seeding
    (the run index times 10) left: today's draws. **Why:** batches and
    golden files made before stay as they are; a test checks the state.
  - Set: the creation function, first, reseeds both generators from the
    batch seed and the run index (`engine.monte_carlo._reseed`). The
    order was checked in Basilisk 2.12.0's installed
    `Basilisk/utilities/MonteCarlo/Controller.py`
    (`SimulationExecutor.__call__`, read only): seed with index × 10,
    call the creation function, draw every model's `RNGSeed` from
    `random`, then every dispersion from NumPy. **Why:** the creation
    function is the only code of the app that runs between Basilisk's
    seeding and its draws, and it needs no change to Basilisk.
  - The run index is read back from NumPy's state: right after
    `numpy.random.seed(<int>)` the MT19937 state's first key is that
    integer and its position is 624 (nothing drawn yet). A state that is
    not so (another Basilisk order) fails the run with a message that
    names plan risk R1. **Why:** Basilisk does not pass the index to the
    creation function; a seeded run must not draw from a state it cannot
    name, and a test fails if a new Basilisk changes the order.
  - Both generators get the four 32-bit words of
    `numpy.random.SeedSequence(entropy=seed, spawn_key=(index,))`
    (NumPy's own way to derive independent streams for parallel work);
    `random` gets them as one integer. **Why:** each run's stream is its
    own; the same seed gives the same draws with one process or many (a
    test runs both), another seed other draws.
  - The range is that of the editor's whole-number field, as
    `sim_settings.seed`. **Why:** one range for the two seeds a user sets.
- **Decision MC-21: where the seed is recorded.**
  - The batch summary: optional key `seed`, written only when set
    (format 1 still, as MC-3). **Why:** an older version opens the
    batch; an older batch reads as "no seed".
  - `archive.provenance.json`: `monte_carlo_seed`, always (null for
    Basilisk's own seeding), and `rng_seeds` says the seeds were drawn
    after the batch seed reseeded the run. **Why:** a provenance record
    says what was used, also "none".
  - A case run again (A3): the run's `monte_carlo_case` gains
    `batch_seed`, only when the batch had one. The case itself is not
    reseeded (MC-18 stands): its draws and seeds come from its
    `run<N>.json`. A test runs every case of a seeded batch again: the
    positions agree to 1e-6 m, the outcomes are equal, and the global
    generators are untouched. **Why:** the case file already holds what
    the seed produced; reseeding would change the state of the GUI
    process.
  - The seed is part of the scenario, so of its hash: a case of a seeded
    batch is refused for the scenario with another seed (MC-17). **Why:**
    another seed is another batch.
  - `monte-carlo` prints "Batch seed: N" only when one is set; the
    Monte Carlo view says "Batch seed N." in its hint line. **Why:** the
    output of a batch without a seed stays as it was.
- **Decision MC-22: the thermal Monte Carlo's confidence** (B4).
  `thermal.monte_carlo.confidence` is optional, in (0, 1), with no
  default; without it, the node limits give counts and the estimate
  only. It is written only when set, so template 34 saves as before. It
  shares schema step 7 with the batch seed: both are phase B, part 1,
  and one step marks the files that 2.14.1 refuses. **Why:** a default
  would be a number without a source (MC-9, MC-13); one step per pull
  request, as phase A.
- **Decision MC-23: how a thermal batch is judged against its node
  limits** (B4).
  - Each node with an operating or survival range gets one row per range
    it has, in the thermal model's order, operating first. The ranges
    are the case's (its overrides applied).
  - A run leaves a range when its lowest temperature is below the low
    end or its highest above the high end; a run on a limit is inside.
    The extremes are those of the run's own solved temperatures, not of
    the ones the summary keeps on the first run's time grid. **Why:**
    the exact meaning of "leaves the range"; the kept series are
    resampled and could miss a peak.
  - A run whose draw the model refuses (a "failed" thermal run) counts as
    leaving every range, shown apart ("Of which failed"). **Why:** the
    same conservative reading as a crashed run and a requirement
    (MC-11).
  - The estimate is k/N; the bound is A2's
    (`engine.monte_carlo_requirements.clopper_pearson_upper`), by the
    model `monte_carlo.probability_bound` in effect for the scenario.
    **Why:** one statistic and one model for both, with its source.
  - The counts are made when the batch is solved and kept in the thermal
    summary as the optional key `node_limits` (one row per node and
    range), with `probability_bound`; an opened batch shows the rows it
    keeps. A thermal summary saved before has none, and the tab says so.
    The requirements' verdicts, in contrast, are computed when the batch
    is read (MC-16). **Why:** the exact extremes exist only while the
    batch is solved.
  - The thermal summary also keeps what each failed run drew
    (`failed_drawn`, as A4 does for orbit batches). **Why:** B8 puts the
    failed runs in the Runs table.
  - The GUI shows the rows in a new "Node limits" tab of Results › Monte
    Carlo, a `DataTable` (sortable, copyable), visible for a thermal
    batch only; the runs outside are in each count's tooltip.
    `spacemissionstudio thermal --monte-carlo` prints the same table.
    **Why:** CLAUDE.md design rule 4 (a long, sortable list is a
    `DataTable`); a tab, as the requirements have one.
- **Decision MC-24: the small fixes** (B8).
  - "Thread count" is "Processes" in the editor and in the Problems
    panel's field title. The file keeps `thread_count`. **Why:** the
    plan's item; a file change would need a migration for a label.
  - The "Failed" tile shows the count ("0" when none). The run numbers
    are in the tile's tooltip. The Runs table already lists the crashed
    runs whose draws the batch kept, with "crashed" in its Status
    column; a thermal batch's table now does the same with "failed". No
    new filter: the Status column sorts. A batch saved before A4 keeps
    no draws of its failed runs; the table cannot list them, and the
    tooltip says so. **Why:** the plan names "a filter or a status
    column already there"; the column exists, and a second way to find
    the same rows adds nothing.
  - The starting attitude (`attitude_sigma_bn`, Euler-angle bounds) is
    in degrees in the form, with a "°" suffix, and in radians in the
    file. A bound that was read and not edited is saved exactly as read.
    **Why:** degrees, as every other angle of the GUI; converting an
    unedited value to degrees and back can change its last digit, and
    opening a form must not change the file.
- **Decision MC-25: tests changed for this work.** Two non-GUI tests
  pinned version 6: `test_migrations.py`'s step 5 to 6 now checks the
  step itself (it already did) and that the file reaches the current
  version, as phase A did for the step 4 to 5; `test_scenario_schema.py`'s
  requirement round trip pins 7. Two GUI tests changed, logged in
  `docs/ui/TEST_CHANGES.md`: the "Failed" tile's expected text and the
  renamed field in the display-units test (plus the new "Batch seed"
  field, a seed without a unit). `test_template_claims.py`'s template 34
  test and `test_thermal_studies.py`'s command-line test gained checks.
  **Why:** CLAUDE.md: no test weakened; each change keeps the check's
  strength or adds to it.

## The Budgets area shows quickly (SRelD K-40, 2026-11-23)

The first item of `BACKLOG.md` "Next release".

- **An area's page (`shell.AreaPage`) tells Qt that its height does not
  follow its width** (`hasHeightForWidth` is False). **Why:** the
  Equipment page has a word-wrapped note, so the page said True, and
  Qt's stacked layout then asked every area's page, the hidden ones too,
  for its height for a width at each show. That was the whole cost: on
  Linux the Budgets area took 8 to 11 ms to show (438 widgets, only 52
  of them shown) and takes about 1 ms now; detach and attach take 3 to
  5 ms instead of 10 to 12 ms. A page fills the area stack and the main
  window ignores a height for width, so nothing that the window shows
  changes: 82 grabs of every area and tab at three window sizes and of
  the detached Budgets window were the same before and after, except for
  a toast or a page caught at another moment, which also differ between
  two runs of the same code.
- **The fix is at the area's page, not at the note.** **Why:** a note
  that does not wrap, or that has no height for width, would show
  differently in a narrow window. At the page, every area gains, and the
  wrapped labels inside a page still get their height from the page's
  own layout. A cut at `BudgetsViews` as well gave no more: the rest of
  a move is the window change itself.
- **The move test's limit is a plain 50 ms again**, as the backlog item
  asks; the rule "twice the show time plus 10 ms" is gone
  (`docs/ui/TEST_CHANGES.md`).

## Pointing error budget: design (2026-11-23)

The second item of `BACKLOG.md` "Next release": the design and its
decisions first, then the owner's choice of scope
(`docs/developer/pointing-error-budget-design.md`). All decisions are
provisional until the owner answers that page's section 7. No code
changed.

- **PE-1. A "Pointing" tab of the Budgets area.** **Why:** the area holds
  the spacecraft's other budgets, and its tables, report and CLI can be
  reused.
- **PE-2. The data is a `pointing` subsection of a spacecraft's
  `budgets`, every value a `SourcedValue`.** **Why:** as the other
  budgets; a value without a source is "TBD", never a default number.
- **PE-3. Clean room from ECSS-E-ST-60-10C's public concepts only.**
  **Why:** the owner's rule; no other tool's name, user interface, files
  or numbers, and no text or table of the standard reproduced.
- **PE-4. Summation per index and axis: means linearly, independent
  standard deviations root-sum-square, correlated groups linearly.**
  **Why:** the standard summation idea, and simple to check by hand.
- **PE-5. No default probability level; a new requirement has "TBD".**
  **Why:** every number has a source (question 2 to the owner).
- **PE-6. Per-axis first; a line-of-sight value from two axes by a
  stated rule.** **Why:** per-axis is the simplest correct form
  (question 3 to the owner).
- **PE-7. A periodic contributor enters an index by the share of its
  amplitude seen in the window.** **Why:** the full amplitude in every
  index overstates relative errors over short windows (question 4 to the
  owner gives the simpler, conservative choice).
- **PE-8. A budget with a "TBD" input shows "TBD" for the indices it
  enters.** **Why:** a smaller number would claim more than is known.
- **PE-9. The recommended scope is option B** (the table, plus the
  scenario's sensor noises as knowledge contributors). **Why:** most of
  the value for a third of option C's effort; C is its own item.
- **The owner's answers (2026-11-24): "as per your recommendation"** to
  the design's section 7. PE-1 to PE-9 are final: scope B first, then C
  as its own item; no default probability level (PE-5); per axis and a
  line-of-sight value in the first step (PE-6); the window share rule
  for periodic contributors (PE-7); a tab of the Budgets area (PE-1).

## A hidden area that becomes wider lays the window out again (2.14.2, 2026-11-23)

CI on `develop` (`ce6123e`, run 45114509231) failed
`test_the_sweep_table_fits_the_page_at_1280[inspector]`.

- **An area's page passes its layout request to the area stack while it
  is hidden** (`AreaPage.event`). **Why:** `QStackedLayout` makes the
  stack as wide as its widest page, hidden pages too, but Qt ignores
  `updateGeometry()` from a hidden widget. When the hidden Timeline page
  became wider (its filters, with the theme's fonts: 923 to 1039 px),
  the window kept its old layout: the stack 923 px wide with a minimum
  of 1039 px, the Inspector 277 px, the sweep table 889 px for 947 px of
  headings. It changed only when some other change laid the window out
  again, so the test passed or failed by timing. Measured: the module
  with the theme applied failed 2 of 4 times on `7a9a25f` (before K-40)
  and 6 of 12 times on `develop`; with the fix 11 of 11 passed.
- **K-40 is not the cause and stays.** **Why:** the same failure, with
  the same widths, came on `7a9a25f`. The fix does not ask a hidden page
  its height for a width, so the Budgets area still shows in about 1 ms
  and K-40's probe test passes.
- **Only the request is passed; the hidden page is not laid out.**
  **Why:** laying it out (`QLayout.activate()`) would arm it for its next
  change too, but it asks its wrapped labels their height (K-40's probe
  was asked once). Qt sends a hidden page's request only while its
  layout is armed (laid out since its last change); a later change then
  waits for the next layout of the window, as before.
- **The Windows failure of `test_every_customize_button_is_inside_the_list`
  (PR #313, job 137490865645) is not changed.** **Why:** its numbers
  (the details 320 px wide, its buttons 169 and 266 px wide, 20 px high)
  show a button row wider than the details column, on the shown Home
  page. That is not the hidden-page fault and not K-40, which only
  changes what the stack asks its pages. It did not come in 25 local
  runs, with or without the theme, so no fix is guessed.

## The Home details' buttons wrap (2026-11-23)

`test_every_customize_button_is_inside_the_list` failed on the Windows
runner on `feature/monte-carlo-seed` (#313), twice with the same numbers:
the details column 320 px wide, its two buttons 169 and 266 px wide and
20 px high.

- **The cause.** The details column put Open template and Customize and
  open... in a `QHBoxLayout`. The details' scroll area has no horizontal
  scroll bar, so the part of the row past the column's edge was hidden.
  With a larger font the row squeezed the buttons and cut their text
  (Linux) or went past the edge (the Windows runner).
- **Why only on #313.** A GUI test runs in the native style and font
  unless the test or an earlier test in the same process applied the
  theme (see `test_stale_results_and_window_size.py`'s `app_theme`). The
  buttons were 20 px high, so the theme (32 px controls) was not
  applied. On `develop` an earlier test on that worker had left it
  applied; #313 adds tests, so pytest-xdist gives the Windows worker
  other tests in another order. No test leaks a font or a style sheet:
  every `setFont` and `setStyleSheet` in the tests is restored.
- **Decision: a `FlowLayout`** (`gui/flow_layout.py`, already used for
  the Results toolbar and the overview cards) instead of the row. The
  buttons keep their own width and sit side by side while they fit;
  otherwise Customize and open... goes below Open template. **Why:** it
  fixes the layout for every font and column width, not only for the
  runner, and it needs no new code.
- **Test:** `test_the_details_buttons_go_one_above_the_other_when_they_do_not_fit`
  gives both buttons the largest font with which each fits the column
  alone but the two do not fit side by side (chosen from the measured
  widths, so it holds in the theme and in the native style). It failed
  before the fix (the buttons stayed side by side and were squeezed) and
  passes after. A first version used a fixed 26 px font: on the Windows
  runner's native style one button alone was then wider than the column.
  No existing test changed.

## Monte Carlo phase B, part 2: outcome statistics, sensitivity, trust checks (2026-11-23)

Items B2, B3 and B6 of [`developer/monte-carlo-plan.md`](developer/monte-carlo-plan.md),
built as the plan says, on part 1 (MC-20 to MC-25). The owner has not
answered Q8 (which percentiles; the "mean ± 3 sigma" lines). The work
ran without questions. **MC-27 is provisional: the owner may change
it.** Each choice below has its reason. No scenario field changed, so
there is no schema step: model choices and parameters live in the
project configuration, not in the scenario file. The golden files are
byte-identical.

- **Decision MC-26: the sensitivity** (B2).
  - The model choice `monte_carlo.sensitivity_measure` has two models:
    `spearman` (the default; C. Spearman, American Journal of
    Psychology 15(1), 1904, pp. 72-101) and `pearson` (K. Pearson,
    Philosophical Transactions of the Royal Society of London A 187,
    1896, pp. 253-318). **Why:** the plan's two; the rank correlation
    finds any monotonic relation and a few extreme runs move it little.
  - NumPy only (`engine/monte_carlo_statistics.py`, Basilisk-free and
    Qt-free). Ties get the mean of the ranks they share; Spearman's is
    Pearson's correlation of those ranks. **Why:** that is Spearman's
    coefficient with ties; no SciPy in the dependencies.
  - Pairwise: a run counts for a pair when it recorded both values. A
    crashed run has no outcome, so it is out of every pair; a run
    without one outcome is out of that outcome's pairs only. N is shown
    per pair. **Why:** the task's rule; leaving a run out of every pair
    for one missing outcome would hide data.
  - No value ("—", None in the engine, never NaN) for a column that
    does not vary over the pair's runs, and for a pair of fewer than 3
    runs. **Why:** a constant column has no correlation; two points
    always lie on a line, so 2 runs would always give ±1.
  - The inputs are the drawn values the summary keeps; the outcomes are,
    per spacecraft, the final radial, along-track and cross-track
    offsets (the Runs table's, in km) and the Overview figures; a
    thermal batch's each node's lowest and highest temperature; an
    operations batch's drawn "outcome: ..." values and each profile's
    lowest and highest value. **Why:** the values a batch already keeps
    per run; the final offsets are the classic result of templates 09
    and 25, which have few Overview figures.
  - The final offsets are rounded to the millimetre (1e-6 km) for the
    statistics and the correlations. **Why:** below a millimetre an
    offset is rounding noise (runs that do not differ at all), as the
    tiles already read it (`format_km`); a correlation of noise would be
    a false lead. The Runs table and its CSV keep the full values.
  - The table is sorted by the size of the correlation, whatever its
    sign (the column's sort key is the absolute value), the pairs
    without a value last. One signed column, no second "size" column.
    **Why:** the plan's "sorted by its size"; a click sorts again.
- **Decision MC-27 (provisional, the owner may change it; Q8): the
  percentiles shown and the band of the thermal and operations
  batches.**
  - The percentiles shown are the parameter `monte_carlo.percentiles`
    ([%], a list), default 1, 5, 50, 95 and 99 %. Its source is "TBD:
    the owner has not named them". **Why:** the plan makes it a project
    parameter with the owner's value; until then the median, the 5th
    and 95th and, as the tails, the 1st and 99th.
  - The "mean - 3 sigma" and "mean + 3 sigma" lines stay (MC-15 left
    them to this phase). Their legend labels are now "mean - 3 standard
    deviations (not a probability bound)" and "mean + 3 standard
    deviations (not a probability bound)", and the line under the view's
    title says the same of the band. The values are not changed.
    **Why:** the plan's first option of Q8; the band is useful for the
    eye, and the label stops it being read as a 99.7 % interval, which
    it is only for a normal distribution. The percentiles are in the
    Statistics tab, so no percentile lines are added to the band plot.
- **Decision MC-28: the outcome statistics** (B3).
  - The model choice `monte_carlo.percentile_method` has one model,
    `linear`: `numpy.percentile` with `method="linear"`, NumPy's
    default, Hyndman and Fan's definition 7 (The American Statistician
    50(4), 1996, pp. 361-365). **Why:** the plan's first model; a
    percentile computed with NumPy from the Runs table's CSV is the same
    number. The choice exists so that another model can be added, as
    `monte_carlo.probability_bound`.
  - Per outcome: N (the runs that recorded it), the minimum, the
    percentiles, the maximum, in a `DataTable` with a "Unit" column
    (outcomes of several units share the table). The empirical
    distribution F(x) is drawn as a step plot from 0 to exactly 1.
    **Why:** design rule 4 (every number with its unit); a step plot is
    the distribution itself, with no method to choose.
  - The batch keeps the three choices it was run with in its summary
    (`sensitivity_measure`, `percentile_method`, `percentiles`; optional
    keys, written by every new batch, format 1 still, as MC-3), and the
    provenance records both models under `models` (they apply to
    `monte_carlo`). A summary written before reads with the defaults; an
    unknown model or a percentile outside 0 to 100 is refused. **Why:**
    as `spread_statistic`: an opened batch reads the same later,
    whatever the project file says by then.
  - The CLI does not print the new tables in this part. **Why:** the
    plan's B5 (the batch report) and B7 (the CLI) are the items that
    add them; `monte-carlo`'s output and the golden files stay as they
    are.
- **Decision MC-29: the trust checks** (B6).
  - A plausibility check (`engine.scenario_checks.plausibility_warnings`,
    so the Problems panel lists it while typing), rule
    `monte_carlo.nominal_outside`: while Monte Carlo is on, a dispersion
    of `dry_mass_kg`, `drag_coeff` or `srp_coeff` whose bounds do not
    contain the spacecraft's value (a value on a bound is inside), or
    whose mean (a normal one) differs from it by more than 1e-9 of it.
    The message starts with the spacecraft and the field, so a
    double-click opens the field. **Why:** these three draw an absolute
    value and have a nominal value in the spacecraft. The orbit
    elements, the inertia and the body rate are spread around the
    spacecraft's own value, so they always follow it. The starting
    attitude draws three 3-2-3 Euler angles in one interval; an
    attitude has more than one such angle set, so a containment check
    would give false findings. 1e-9: only floating-point noise is
    allowed; a deliberate offset is the finding's case, and a warning
    never stops a run.
  - Only while Monte Carlo is on. **Why:** the same as
    `monte_carlo.processes`; a scenario that does not run a batch does
    not need its dispersions checked.
  - No template gives the finding, with Monte Carlo on as saved and
    turned on (a test checks the 36). Template 25's drag coefficient 3.0
    is on its dispersion's upper bound, so inside.
  - A batch opened (or finished) while the open scenario's SHA-256 is
    not the one in its `archive.provenance.json` shows a warning under
    the view's title, a `NoteList`, with both hashes and the batch's
    scenario file when it is recorded. It reuses
    `monte_carlo_case.batch_scenario_hash` and the hash Run This Case
    compares (MC-17). Nothing is said with no scenario open, with a
    scenario that does not validate, or for a folder that does not
    record a hash (thermal and operations batches, older batches).
    **Why:** design rule 4 (a warning is a `NoteList` row); the same
    check as Run This Case, so the two never disagree. It is not a
    Problems row: the batch is not a problem of the scenario, and the
    note goes with the batch shown.
- **Decision MC-30: how the two tabs are built** (design rules 4 and 6).
  - Two new tabs of Results › Monte Carlo, "Statistics" and
    "Sensitivity", after "Runs": each a hint, a `DataTable` (sortable,
    copyable; Statistics keeps the batch's order until a header is
    clicked) and, under a splitter, its plot.
  - The statistics and the correlations are worked out in a worker
    (`gui.monte_carlo_insight.InsightComputer`, a `QThreadPool` of one
    thread, as the ground map's renderer), the first time one of the two
    tabs is shown for a batch. A newer batch replaces a request that
    waits; a result for a batch no longer shown is dropped; the pool
    waits for its job when it is deleted, and the window waits for it
    when it closes. **Why:** design rule 6. Measured here for 100 000
    runs: 4 drawn values and 6 outcomes (one with a run missing) take
    about 0.2 s, 10 drawn values and 30 outcomes about 0.5 s; too long
    for the GUI thread. A column that every run has is ranked and
    centred once, so a pair is one dot product (3.3 s before that, for
    10 and 30).
  - The plots are made on the GUI thread, but as Plotly's JSON form
    directly (the layout through plotly's `Layout`, the arrays as
    Plotly's typed arrays, base64), not as `go.Figure`. Measured here
    for 100 000 runs: the scatter's figure and page in about 12 ms
    (57 ms with `go.Figure`), the distribution's in about 10 ms (99 ms).
    A test makes both for 100 000 runs and requires under 50 ms (the
    best of three). Above 5000 points a plot draws with WebGL
    (`scattergl`). **Why:** design rule 6 without a second worker per
    picked row.
  - Each plot's web view is made the first time it has a figure
    (`InsightPlot`), with the theme's Plotly template (fonts, colours,
    the first series colour), axis titles with their units, and is built
    again on a theme change. **Why:** CLAUDE.md (plots lazily created,
    the template from the tokens, redrawn on `theme.on_change`).
  - The tab switch reaches the widget through
    `widgets.connect_while_alive` (2.14.1's rule for `currentChanged`).
- **Decision MC-31: tests changed for this work.** Two non-GUI tests
  list every model choice or parameter and gained the new ones:
  `test_model_registry.py`'s `_PAGES` (the two choices, on
  `monte-carlo-statistics.md`) and `test_config.py`'s `_MODEL_CASES`
  (the three parameters, each set by
  `test_monte_carlo_statistics.py::test_a_batch_reads_with_the_choices_it_was_run_with`).
  No GUI test reaches a widget another way, so `docs/ui/TEST_CHANGES.md`
  has no entry. **Why:** CLAUDE.md: no test weakened; each list only
  grows.

## Monte Carlo plot pages written off the GUI thread (2026-11-23)

`test_the_plots_of_a_batch_of_100000_runs_are_made_within_50_ms` failed
on the Windows runner for #314 (`e6902e4`): 102.6, 88.8 and 50.7 ms,
where the best of three must be under 50 ms. Here the same steps took
12 to 17 ms: the figure 4 to 5 ms, its JSON (base64 arrays) 5 to 10 ms,
the page 1 to 2 ms, plus the write of a 2 to 3 MB file that the test did
not count.

- **Decision:** `InsightPlot` builds the figure on the GUI thread and
  makes its JSON, its page and the page's file in one serial worker
  (`monte_carlo_insight.write_page`, a `QThreadPool` of one thread, as
  `InsightComputer`). The GUI thread then only loads the page. **Why:**
  the JSON and the file are most of the time and touch no Qt or plotly
  object. The figure stays on the GUI thread, because plotly checks its
  layout there for every other plot and is not made for two threads at
  once.
- Each page has its own file name (`monte_carlo_insight_<n>.html`). Only
  the newest page asked for is loaded; an older one is deleted when it
  arrives, and the page shown before is deleted when a new one is shown
  (a file the web view still holds stays until the folder is removed).
  An error writing a page is logged and leaves the shown page as it is.
- Measured here after the change: `show_figure` takes 4 to 7 ms of the
  GUI thread for 100 000 runs (12 to 17 ms before).
- **Test:** the timing test now times `InsightPlot.show_figure`, the GUI
  thread's part, best of three under 50 ms as before, and checks that
  the worker writes the page (over 1 MB), that it is shown and that the
  older pages are gone (`docs/ui/TEST_CHANGES.md`).
- **Amended 2026-11-24: the workers report through a relay.** The plot's
  worker emitted a signal of the plot. The Windows runner raised
  "TypeError: only accepts 0 argument(s), 3 given" when it did so while
  the plot was deleted (CI of #322). **Decision:** `InsightPlot`,
  `InsightComputer` and `ReportWriter` each own a `_Relay` (a parentless
  `QObject` with one `done` signal). The worker's task gets the relay,
  never the view, and emits the relay's signal. The view connects a
  method of its own. **Why:** a worker then never touches a view that
  may be in its destructor, and Qt ends the connection, and drops a
  queued result, when the view is deleted. Catching more exception types
  at the emit was rejected: it would hide the call into a half-deleted
  object, not prevent it. Details in `HISTORY.md`.

## Monte Carlo phase B, part 3: batch report, command line, template 37 (2026-11-23)

Items B5, B7 and B9 of [`developer/monte-carlo-plan.md`](developer/monte-carlo-plan.md),
built on part 2 (MC-26 to MC-31). The owner has not answered Q7 (a
template for the new features). The work ran without questions. **MC-34
is provisional: the owner may change it.** No scenario field changed, so
there is no schema step: the scenario stays at version 7, and the
command-line overrides are not scenario keys. The golden files of the 36
existing templates are byte-identical; template 37 has its own.

- **Decision MC-32: the batch report** (B5).
  - A new module, `engine/monte_carlo_report.py` (Basilisk-free,
    Qt-free), builds the report as a dict and writes it as JSON (`kind:
    "monte_carlo_report"`, `format` 1, `spacemissionstudio_version`,
    `created_utc` with `Z`) or as Markdown. The file's suffix chooses:
    `.json` or `.md`, in any case; another suffix is refused before
    anything runs or is written. **Why:** one file, two readers (a
    script, a person), and no format flag to forget.
  - Its sections: the batch (scenario name, kind, folder, epoch, run
    length, spacecraft or nodes), the settings (runs asked for, done and
    failed; processes asked for and used; the seed; the command-line
    overrides), the dispersions, the spread at the end (the view's
    tiles), the requirements (every field of `RequirementResult`, the
    verdict null without an allowed probability) with the bound's model,
    a thermal batch's node limits, the outcome statistics with the
    percentile method's model record, the sensitivity with the measure's
    model record and every pair, the crashed runs with what they drew,
    and the provenance (the batch's `archive.provenance.json`: scenario
    SHA-256, scenario file and its SHA-256, versions, models, seeds note;
    the data files with their SHA-256). **Why:** the plan's list, plus
    the spread, which is the view's headline.
  - The numbers come from the functions the view uses:
    `monte_carlo_requirements.evaluate`, `monte_carlo_statistics.insight`,
    `monte_carlo_results.final_spread` and `node_spread`. The GUI hands
    the report its own `Insight` when the Statistics or Sensitivity tab
    has worked it out, so the report holds the very objects the tables
    show. The Markdown cells come from the same text functions:
    `table_rows`, `node_limit_rows`, and `number_text` and
    `percentile_title`, which moved from `gui.monte_carlo_insight` to
    `engine.monte_carlo_statistics` (the GUI module keeps the names).
    **Why:** the plan's acceptance ("the report's numbers equal the
    view's") holds by construction, and a test checks it cell by cell.
  - JSON numbers are written in full (Python's shortest round-trip
    form); NaN and infinity are null (`allow_nan=False`). **Why:** a
    script reads the exact value the view rounds; strict JSON.
  - The data files are listed once per kind and SHA-256 with the number
    of runs that read each, from the summary's `data_files`; a summary
    without them falls back to the nominal run's record in the
    provenance, and says so. **Why:** a batch normally reads one set of
    files; a list per run would repeat it N times.
  - A batch made before this version has no `monte_carlo_settings`. Its
    report gives the runs and the seed from the summary, and says that
    the processes and the dispersions are not recorded. A thermal or
    operations batch says why it lists no dispersions. **Why:** the report
    never invents what the batch did not keep.
  - GUI: **Export report...** beside **Open results...**, enabled with a
    batch; a save dialog offers Markdown and JSON, and a name without a
    suffix takes the chosen format. The report is built and written by
    `gui.monte_carlo_insight.ReportWriter`, a one-thread `QThreadPool` as
    the insight's; success is a toast and Reports › Exports lists it
    (`monte_carlo_report`); a failure is said in a toast and the Log.
    The window's close waits for it with the insight. **Why:** design
    rule 6: for a large batch the statistics alone take 0.2 to 0.5 s; the
    GUI thread only starts the job (a test requires under 50 ms).
  - The Runs table's CSV writer moved to the engine
    (`monte_carlo_report.write_runs_csv`); the view's **Export table
    CSV...** calls it and writes what it wrote before. **Why:** the
    command line writes the same file; one writer.
- **Decision MC-33: the command line** (B7).
  - `monte-carlo --summarize DIR` runs nothing and reads only the
    summary. It takes no scenario (a usage error, 2, if one is given):
    the batch records what it ran with. It prints what a batch prints,
    writes the Runs table and, with `--report FILE`, the report. Nothing
    in DIR changes (a test compares every file's bytes). It exits 1 for
    a folder without a summary that can be read, 3 when a file cannot be
    written, 5 when a requirement with an allowed probability is not
    shown met, else 0; never 3 for the batch's own crashed runs, since
    no run fails in this command. **Why:** ICD-02's meanings; the same
    check as after the batch, so a script can judge an old batch.
  - Its Runs table goes to `--csv FILE`, by default `monte_carlo_runs.csv`
    in the working folder (the GUI's default name), with
    `<file>.provenance.json` beside it. Not in DIR. **Why:** a file
    added to the batch folder would make the folder "other" and
    `--overwrite` would then refuse to reuse it.
  - The CSV holds the first spacecraft's (or node's, or profile's) Runs
    table, as the view's first choice; with several, the command says
    which and that the window exports the others. **Why:** the table is
    per spacecraft by design (its offsets and outcomes); a merged table
    would be a second format. A `--spacecraft` flag can come later if
    needed.
  - `--csv FILE` and `--report FILE` also work after a batch run.
    **Why:** the plan's "monte-carlo --report FILE"; the CSV was the
    other half of G9 ("no CSV from the CLI").
  - The batch run and `--summarize` print the same lines (one function):
    as before, then the outcome statistics (the Statistics tab's
    columns) and the 10 strongest correlations, with a pointer to the
    report for the rest. **Why:** MC-28 left these tables to B5 and B7;
    every pair of a large batch (inputs times outcomes, 50 for template
    37) is too long for a terminal.
  - `--runs N` (1 to 100 000) and `--processes N` (1 to 256), the
    scenario file's limits, checked by argparse. They change a copy of
    the Monte Carlo settings for this batch; the scenario object and its
    file are not changed (a test compares the file's bytes), so the
    batch's scenario hash is the file's and Run This Case still accepts
    the file. **Why:** neither changes what a case draws (a case's draws
    depend on its index and the seed, MC-20), so the cases stay
    reproducible from the unchanged file.
  - Every new batch's `archive.provenance.json` gets
    `monte_carlo_settings`: `num_runs` and `thread_count` as used,
    `processes_used` (one per CPU at most), `seed`, the `dispersions` as
    the scenario file writes them, and `overrides`, each overridden value
    as `{"scenario": ..., "batch": ...}` (empty without one). Written
    always, also by the GUI's batches. **Why:** the plan's "recorded in
    the provenance"; a provenance record says what was used, also "no
    override" (as `monte_carlo_seed`, MC-21); the report reads the
    settings and dispersions from it, so `--summarize` needs no
    scenario.
  - `--case` with `--runs`, `--processes`, `--report` or `--csv`, and
    `--summarize` with `--case`, `--out-dir`, `--runs`, `--processes`,
    `--overwrite` or `--allow-scripts` are usage errors (2), said before
    anything is read. **Why:** each would be silently ignored otherwise.
- **Decision MC-34 (provisional, the owner may change it; Q7): template
  37.** A new template, "37 - Monte Carlo: requirements, statistics and
  sensitivity"; template 25 is unchanged, so no golden file changes.
  - Template 25's 150 kg satellite at 400 km (its gravity, Sun, Moon,
    real space weather, Cd 3.0), for 0.5 day; 30 runs, one process,
    batch seed 37; three dispersions: the orbit (1-sigma 0.5 km in
    semi-major axis, 0.02 deg in inclination, 0.05 deg along track), the
    drag coefficient (uniform 2.2 to 3.0, as 25) and the dry mass (normal,
    150 kg, 7.5 kg, 5 %); two requirements at 90 % confidence:
    R-ALT-01, lowest altitude at least 389 km with an allowed probability
    of 0.1, and R-DECAY-01, mean semi-major axis change at least
    -0.019 km with none. **Why:** each phase A and B feature shows: a
    verdict (met), an estimate with its bound and no verdict, the seed,
    percentiles of ten outcomes, and a sensitivity with a strong (Cd)
    and a weak (mass) driver. The limits are round numbers placed by the
    measured batch: 389 km is 1.4 km under the lowest run, -19 m cuts
    the tail.
  - 30 runs: the smallest batch whose bound at k = 0 (1 - 0.1^(1/30) =
    0.074) is under the allowed 0.1, and whose correlations stand out of
    their chance spread (about 1/sqrt(29) = 0.19). **Measured here: 53 s
    for the 30 runs in one process** (the CLI, wall time; 4 CPUs), about
    1.7 s a run. One process, as every other template: a template must
    not warn on a one-CPU computer (more processes than CPUs).
  - Measured with the seed: R-ALT-01 met (0 of 30, bound 0.0739);
    R-DECAY-01 2 of 30 (estimate 0.0667, bound 0.168); Spearman's
    correlation of Cd with the decay -0.90, of the dry mass +0.27.
    `tests/test_template_claims.py` checks these (slow: about a minute).
  - Its golden file was recorded with `scripts/update_golden_outputs.py
    37_ --write` and covers the usual run and a 2-run, 0.05-day batch;
    `tests/data/scenario_hashes.json` gained its two hashes. It has a
    Customize wizard (runs, seed, Cd bounds, dry-mass spread, the two
    limits, duration), a row in the templates' README and the learning
    path's "Uncertainty" step.
  - The wizard's page of the other settings headed a dispersion's group
    with its file name ("Dispersion: sat-1 dry_mass_kg"); it now says
    "Dispersion: sat-1 dry mass" (`gui.wizard_settings`). Found by
    `tests/gui/test_label_text.py` on template 37, whose orbit and mass
    dispersions are not all on its curated pages. **Why:** UI audit B4
    (labels, not identifiers); templates 09 and 25 never showed it.
- **Decision MC-35: tests changed for this work.** Lists that enumerate
  the templates grew by template 37: `tests/gui/test_home.py` (37 cards;
  the "monte carlo" filter finds 09, 25, 34 and 37, "4 of 37") and
  `tests/test_monte_carlo_statistics.py`'s check that no template has a
  false finding (37 files). `tests/gui/test_reports_and_settings.py`'s
  list of exports grew by "Monte Carlo report" (23). No GUI test reaches
  a widget another way, so `docs/ui/TEST_CHANGES.md` has no entry.
  **Why:** CLAUDE.md: no test weakened; each list only grows, and every
  check on the 36 templates still runs on them.

## Template 37's drawn orbit angles held to the golden angle floor (2026-11-23)

`test_37_the_batch_meets_its_altitude_requirement_and_the_drag_coefficient_drives_the_decay`
failed on the Linux CI runner (#316, `c6ef559`). One drawn value of the
first two runs differed from the golden file: the true anomaly,
-0.068391551 deg against -0.068390697 deg, which is 8.54e-7 deg, or
1.49e-8 rad = 2^-26 rad. The test compared every drawn value to 1e-12.

- **Cause:** the drawn orbit elements are not the generator's numbers.
  They come from `rv2elem` of the dispersed initial state
  (`monte_carlo._drawn_values`). Template 37's orbit is near circular, so
  its true anomaly comes through an arccos near 1, which gives 0 on one
  computer and 2^-26 rad on another. `tests/golden_capture.py` already
  describes this and holds such angles to `ABSOLUTE_FLOORS["deg"]`
  (1e-6 rad).
- **Decision:** the test compares a drawn value in degrees with that same
  floor, and every other drawn value (drag coefficient, dry mass,
  semi-major axis) still to a relative 1e-12. **Why:** the golden test of
  the same batch already uses this floor. The draws that the generator
  makes still have to match to the last digits.

## A cancelled Monte Carlo batch leaves no process (2026-11-23)

The backlog item of 2.15.0: twice, a local `pytest tests -n 4` did not end
within 60 min, with a `spawn_main` process and a
`multiprocessing.resource_tracker` alive at 0 % CPU.

- **Cause:** `gui.monte_carlo_process._stop_on` (Cancel, in the batch's
  child) takes one list of the child's processes
  (`multiprocessing.active_children()`), ends them, waits for them and
  calls `os._exit`. With 2 processes, Basilisk's controller runs the
  cases in a `multiprocessing.Pool`. The pool's worker-handler thread
  replaces a worker that ends. So it started a new worker after the list
  was taken, and that worker outlived the child. In the batch's child the
  start method is "spawn" (the child's own), so the orphan is a
  `spawn_main` process. It waits for ever on the pool's task queue
  (`SimpleQueue.get`, `SemLock.__enter__`): its parent is gone and it
  holds the queue's pipe itself. It holds the resource tracker's pipe
  too, so the tracker of the pytest worker does not end either. When the
  tracker or the orphan has the run's own stderr, a run piped to a
  filter never ends, although pytest has ended.
- **Evidence:**
  - Traced (a scratch `sitecustomize` that logs each process start): the
    cancel thread listed the data writer, the manager and pool workers 3
    and 4; 15 ms later the thread `_handle_workers` started
    `SpawnPoolWorker-1:5`; 16 ms after that the child called
    `os._exit(3)`. Worker 5 was the process left.
  - `py-spy dump` of every process left: the worker in
    `pool.worker` > `SimpleQueue.get` > `SemLock.__enter__`, parent PID 1;
    the tracker in `resource_tracker.main`, reading its pipe.
  - Before the fix, on `5ebbd3b`: 3 of 7 runs of `pytest tests/gui -n 4`
    (about 3.7 min each) left a worker and a tracker. The cancel test
    `test_a_monte_carlo_batch_can_be_cancelled_keeping_the_runs_finished`
    alone left them in 4 of 8 runs while the GUI suite ran beside it, and
    in none of 12 runs on an idle machine. Run with `-s` and piped to
    `tail -1`, 2 of 10 runs did not end in 150 s after pytest had ended;
    they ended when the two processes were killed.
  - No other test left a process in these runs.
- **Decision:** the batch's child puts itself in a group of its own
  before it starts a process (`_own_process_group`): on POSIX a process
  group (`os.setpgid(0, 0)`), and `run_batch` sends SIGKILL to that group
  when the child has ended after Cancel or without a result
  (`_end_process_group`); on Windows a job object with
  `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` that holds the child, so every
  process in it ends when the child ends. **Why:** a group takes the
  processes that start after any list is taken, and also those of a
  child that crashed. The alternatives do not end the race: a loop that
  takes the list again never ends, because the pool replaces every
  worker that ends; the controller's pool is Basilisk's and not
  reachable (no patching of Basilisk).
- **Trade-off:** on POSIX the batch's child is no longer in the group of
  the terminal that started the app, so Ctrl+C in that terminal does not
  reach it directly. Closing the window still cancels the batch. When the
  system refuses the group, the child logs a warning and the batch runs
  as before.
- **Test:** `tests/gui/test_run_worker.py::test_a_cancelled_batch_leaves_no_process_that_its_pool_started_late`
  starts `run_batch` with a stand-in child that starts a process just
  after Cancel's list is taken. Without the fix the process still ran 10 s
  later (2 runs of 2); with it, it ends.
- **After the fix:** no process left in 4 runs of `pytest tests/gui -n 4`
  and 20 runs of the cancel test beside them; 10 piped runs with `-s`
  ended in 10 s each. In 12 traced runs the pool started a worker after
  Cancel's list in 2, and the group ended it both times.

## The GUI thread outranks the 3D View's software drawing (SRelD K-40, 2026-11-24)

The item of `BACKLOG.md` "Next release": the 3D View's move into its own
window or back took 64.0 and 72.7 ms on the Windows runner (release run
45148067729), against the plain 50 ms limit. Worked on branch
`fix/3d-view-move` from `develop` at `bb00914`.

- **The cause is not the move's own work.** On Linux the move takes 3 to
  5 ms of the GUI thread's processor time (detach: `_swap` 0.6 to 1.1 ms,
  `setWindowFlags` 0.9 to 1.3, `_show` 0.8 to 3.0, the rest under 1;
  attach: `hide` 0.4 to 1.2, `_swap` 1.2 to 1.9). No native window or
  render widget host is made again: under the offscreen platform Qt
  Quick uses its software back end (the platform has no RHI-based
  rendering, on Windows too), so the web view's `QQuickWidget` gets no
  `WindowAboutToChangeInternal` or `WindowChangeInternal` event; only the
  view's own offscreen window is made and closed (one `PlatformSurface`
  and one `WinIdChange` event per move). Hiding and showing the web view
  takes 0.1 to 0.2 ms.
- **The cause is the wait for a processor.** The move's wall time minus
  its thread time is spent in the run queue (Linux `schedstat`): with
  four busy processes beside it, one move took 27.6 ms, 5.1 ms on the
  processor and 23.9 ms waiting, and the slowest of 16 took 75.8 ms with
  at most 6 ms on the processor. Thermal and Budgets moves do not wait
  so. After each move the 3D View's page draws its new size in software,
  on every processor: per move 240 to 255 ms of processor time in the
  app's process (four `llvmpipe` threads about 40 ms each, the GPU
  thread 40 ms, the GUI thread 20 to 25 ms) and 30 ms in the page's
  processes.
- **On Windows the drawing threads outrank the GUI thread** (a
  diagnostic test on the Windows runner, CI run 45296869864, thread
  priorities read with `GetThreadPriority`). The page draws with ANGLE
  on WARP ("Microsoft Basic Render Driver"), 30.7 ms a frame at reduced
  quality. In 16 moves four WARP threads used 172 to 250 ms each at
  "above normal" priority, as did Chromium's GPU, compositor and IO
  threads; the GUI thread (`CrBrowserMain`) was at "normal". Windows
  runs a higher priority first, so while the page drew, the GUI thread
  got no processor: the slowest move took 56.2 ms. In the same process,
  with the GUI thread at "above normal" the slowest of 16 moves took
  10.4 ms, at "highest" 7.4 ms; with 400 ms between moves, 10.4 ms; with
  the globe hidden (map only), 6.2 ms. Linux as root shows the same: the
  same threads at nice -8 (Chromium may lower them there), the GUI thread
  at 0.
- **Decision: the GUI thread gets the drawing threads' priority**
  (`background_threads.install`: `QThread.Priority.HighPriority`, which is
  "above normal" on Windows; on Linux nice -8 where the process may
  lower it, which needs root, as for Chromium). **Why:** the GUI thread
  must not wait for the 3D View's drawing ("Never freeze"); equal
  priority is enough (10.4 ms) and does not put the GUI thread above
  Chromium's own threads, as "highest" would.
- **The workers take the GUI thread's priority, as before.** A
  `QThread` started with `InheritPriority` (the default) gets the
  priority of the thread that starts it, and on Linux a new thread gets
  its nice value. **Why:** the GUI thread and the workers keep their
  order. The first version started the window's workers at normal
  priority (a `WorkerThread` base for 24 thread classes and a
  `worker_pool` for 5 pools), so that a run would not outrank other
  programs. Both Windows CI runs with it lost a test process ("node down:
  Not properly terminated", no traceback; in `test_display_units.py` in
  run 45304662719 and in `test_design_rules.py` in run 45314703069),
  against none in the 19 Windows runs before. Windows runs the higher
  priority first, so a busy GUI thread could starve a worker below it;
  a test that waits 10 s for its threads, then deletes one that still
  runs, ends the process. The cause is not proven, so the change was
  dropped. **Trade-off:** a run or a study now runs "above normal"
  beside other programs, like the GUI thread and Chromium's drawing.
  **The owner kept this trade-off (2026-11-24, "as per your
  recommendation").**
- **Decision: the page draws each new size once.** The window's
  `resize` event and the page's `ResizeObserver` both reported a move's
  new size, and each made a frame of the same size. `MV.onResized` now
  applies a size only when it is new. **Why:** the second frame showed
  nothing new and took the processors for about 30 ms on the Windows
  runner. Per move the page's processor time fell from 240 to 255 ms to
  123 to 137 ms (Linux). What the view shows is unchanged: the last
  frame of each move is drawn at the host's size, as before.
- **Not done:** no change to how a view moves (its container, its native
  window, a deferred show). The measurements show no cost there to cut.
  No Chromium flag either: CI sets `QTWEBENGINE_CHROMIUM_FLAGS` itself,
  which replaces the app's flags.
- **After the fix**, on the Windows runner (CI run 45304662719): the
  move test's protocol ten times in one process, 60 moves of each view:
  the slowest 3D View move 13.6 ms (5.4 to 13.6 per run), Thermal 3.7 ms,
  Budgets 8.6 ms; the GUI thread at "above normal", and no thread that
  worked during the moves above it. On Linux, with four busy processes
  beside it, the slowest of 80 moves took 7.5 to 9.3 ms in four runs
  (22.9 to 35.8 ms before).
- **Tests:** `test_no_thread_that_draws_the_3d_view_outranks_the_gui_thread`
  and `test_the_3d_view_draws_each_new_size_of_its_page_once`
  (`tests/gui/test_breakout.py`), and one in
  `tests/gui/test_background_threads.py`. The first two fail without the
  fix. The move test is unchanged: a plain 50 ms per view. In CI run
  45314703069 (Windows) the move test and the two new tests passed.

## Monte Carlo phase C: the order of the dispersions (2026-11-24)

The owner answered Q6 of [`developer/monte-carlo-plan.md`](developer/monte-carlo-plan.md)
(§9): which phase C dispersions come first.

- **Decision MC-36: the order of the phase C dispersions** (C1, the
  owner's answer to Q6). The dispersions of item C1 are built in this
  order:
  1. Atmospheric density: a scale on the density, or on F10.7 and Ap.
  2. Maneuver execution errors: the magnitude and the direction of the
     Mission Sequence's impulsive and Lambert burns. The Mission Sequence
     draws them, because the Controller cannot reach a command.
  3. Thruster force and misalignment.
  4. Reaction-wheel friction and bias.
  5. Propellant load and centre-of-mass offset.

  Each item starts with a short spike: read the code of the app and of
  Basilisk 2.12.0 first, then choose the design and record it here.
  **Why:** the owner's order. Density is first: it is the largest
  uncertainty of a low-orbit decay and needs no Mission Sequence.

## Monte Carlo phase C, item 1: the atmospheric density dispersion (2026-11-24)

The first dispersion of C1 by the owner's order (MC-36). The spike is
§6.1 of [`developer/monte-carlo-plan.md`](developer/monte-carlo-plan.md).
The work ran without questions. The choice of meaning in MC-37 was
provisional (Q9); **the owner confirmed it on 2026-11-24 ("as per your
recommendation"): a scale on the density only, no F10.7 and Ap
dispersion.** Schema step 7 to 8. The golden files of the 37 templates are byte-identical.

- **Decision MC-37 (Q9, confirmed by the owner on 2026-11-24): a scale
  on the density that drag reads.**
  - The quantity is `density_scale`, a number with no unit: each run's
    drag reads the atmosphere model's density times the drawn scale.
    1 is the model's own density. Kinds: `uniform` (bounds) and
    `normal` (mean, standard deviation, optional bounds).
  - It applies to the three atmosphere models (`nrlmsise00`,
    `exponential`, `tabular`) and to the sphere and the facet drag.
    **Why:** the owner offered "a scale on the density, or on F10.7 and
    Ap". A density scale is physically the same thing for every model.
    A scale on F10.7 and Ap acts on NRLMSISE-00 only, changes the
    density by no fixed factor, and makes synthetic space weather, which
    the user requirement "real data only" forbids. This is the safer of
    the two meanings. Q9 asked the owner if F10.7 and Ap are wanted
    too; the owner answered "as per your recommendation": not wanted.
  - **How:** a Python `SysModel`, `engine.density_scale.DensityScale`
    (task priority 385), between the model (390) and the drag (100). It
    reads each spacecraft's `AtmoPropsMsg` and writes a copy with the
    density times `scale`; the temperature is unchanged. The drag
    effectors and the atomic-oxygen recorder read the copy. **Why:**
    Basilisk 2.12.0 has no parameter that scales the density of every
    model (`MsisAtmosphere` has none; `DragDynamicEffector`'s
    `densityCorrection` is a state of the dynamics). The message is the
    one place that all models and both drag effectors share. No change
    to Basilisk. The Cd proxy was not taken: it is not the density, and
    the label would mislead.
  - The service builds the module only when asked
    (`SimulationService(density_scale=True)`): `engine.monte_carlo`
    asks for a batch whose scenario has the quantity, and so does a case
    run again. Every other run is built as before. **Why:** a plain run
    keeps its models, their order and their RNG seeds; the golden files
    do not change. At scale 1 the run is identical to a run without the
    module (a test compares every position).
  - One draw per run, constant during the run, the same for every
    spacecraft with drag. **Why:** one atmosphere per run; the simplest
    model of a density model's error. A density error that changes in
    time is not built (see `docs/reference/limitations.md`).
- **Decision MC-38: the schema and its checks** (schema 8).
  - `density_scale` belongs to the atmosphere, not to a spacecraft: its
    `spacecraft` is empty (`""`). A name there is refused. **Why:** one
    scale for every spacecraft with drag. A scale per spacecraft would
    give two spacecraft in one atmosphere independent errors.
  - Refused, never drawn and ignored (`Scenario.validate`,
    `schema.scenario.density_scale_refusal`; the engine checks again
    when it builds the dispersion): no spacecraft with drag; a central
    body other than the Earth; an atmosphere model outside
    `DENSITY_SCALE_ATMOSPHERE_MODELS` (today every model is in it); two
    density scales; a bound below 0; a mean of 0 or below. **Why:** a
    draw that changes nothing would show a spread that is not there.
  - A normal draw without bounds is held at 0 or above (bounds
    [0, inf], the clip of Basilisk's `NormalDispersion`). The module
    stops a run whose scale is negative or not finite. **Why:** a
    negative density has no meaning.
  - A uniform scale with equal bounds gives that value
    (`engine.monte_carlo._UniformDensityScale`). Basilisk 2.12.0's
    `UniformDispersion` divides by the half-width and fails the run when
    the bounds are equal. The form starts a new scale at [1, 1]. The
    subclass takes the same one number from `random`, so the draws after
    it do not change. **Why:** a fixed scale (for example 1.5 in every
    run) is a valid study.
  - Schema step 7 to 8, version only, as the steps to 6 and 7. The 37
    templates change only on their `schema_version` line;
    `tests/data/scenario_hashes.json` is recorded again (74 values);
    `docs/changes.md` says why. A version 8 file does not open in
    2.15.0; a build at version 7 also refuses the quantity by its name.
- **Decision MC-39: where the scale shows.**
  - The drawn value's label is `atmospheric density scale [-]`, with no
    spacecraft in front. `[-]` is the app's mark for "no unit", as for
    the drag coefficient. It reaches the batch summary, the Runs table
    and its CSV, the statistics and the sensitivity, and the report like
    every drawn value. The report's dispersions table names the owner
    "atmosphere".
  - GUI (Scenario › Monte Carlo): `density_scale` is in the quantity
    list; the form hides the spacecraft row for it; a scale the user
    picks starts at 1 with no spread; the list shows
    "atmosphere: density_scale (uniform)". The wizard's group heading
    says "Dispersion: atmosphere density scale".
  - The command line and the API list no quantities, so they do not
    change. `monte-carlo` writes the scale in its Runs CSV and report,
    and ranks it among the correlations it prints.
  - Template 37 does not get the dispersion. **Why:** its claims
    (MC-34: the verdicts, the bound, the correlations) were measured
    without it, and every golden file stays byte-identical. A template
    can show it later.
- **Decision MC-40: tests changed for this work.** Three tests pin the
  schema version: two in `tests/test_scenario_schema.py`
  (`CURRENT_SCHEMA_VERSION == 8`, and a saved seed at version 8) and one
  in `tests/test_migrations.py` (the step from 6 to 7 now ends at the
  current version, as the step from 5 to 6 already did). No GUI test reaches a widget another way.
  `docs/ui/TEST_CHANGES.md` lists the new tests. **Why:** CLAUDE.md: a
  pinned version moves with the schema; no check is weakened.

## Templates for every feature, batch A: templates 39 to 42 (2026-11-24)

The owner wants at least one template for every feature of the tool. The
37 templates on `develop` give every orbit as classical elements and use
only NRLMSISE-00. None uses `constant_thrust`, `navigation_error`, the
`velocityPoint` mode or a `magnetometer` sensor. Batch A adds four
templates for these gaps. Number 38 is kept for the Budgets template (a
separate change). No scenario field changed, so there is no schema step.
The golden files of templates 01 to 37 are byte-identical; each new
template has its own, recorded with `scripts/update_golden_outputs.py
39_ 40_ 41_ 42_ --write`.

- **Decision TPL-A1: what the four templates show, and how their values
  are sourced.** The rule: a value comes from a named source in the app,
  or it is labelled illustrative or synthetic in the generator and in
  the description. No source is invented.
  - **39, orbit inputs.** Three 150 kg satellites, orbit only, no drag.
    - tle-sat: a **synthetic** TLE (catalogue number 99999, no
      international designator, no drag terms, epoch the scenario's,
      51.64 deg, e 0.0004, 15.5 revolutions a day). The generator builds
      each line field by field and computes the checksum
      (`_tle_line`). **Why synthetic:** a real TLE needs a fixed
      historical record that we can cite, the repository holds none,
      and the template must not fetch anything. A TLE more than 3 days
      from the scenario epoch also gets a warning. A synthetic set at
      the epoch avoids both, and it is labelled synthetic.
    - state-sat: an **illustrative** Cartesian state, the perigee of a
      500 x 1500 km orbit at 63.4 deg, with the speed from the vis-viva
      equation and Basilisk's Earth constants
      (`spacemissionstudio.constants`), rounded to 1 m and 1 mm/s.
      **Why:** it is consistent by construction, and the critical
      inclination gives a check (the perigee holds).
    - elements-sat: template 22's 550 km Sun-synchronous orbit.
    - The description points to `ccsds-import` and **Import CCSDS
      OPM/OMM...** for an orbit file.
  - **40, continuous low thrust.** Two 150 kg satellites at 400 km with
    drag from the bundled space weather (2030), three days. ep-sat has
    `constant_thrust` along the velocity (VNB [1, 0, 0]); twin-sat has
    none. The thruster values are the **device catalogue's ENPULSION
    MICRO R3** (`engine/device_catalog.py`: 1 mN, Isp 3000 s, 1.3 kg).
    **Why a twin:** the claim "the thrust raises the orbit" is then a
    comparison in one run. The fuel use shows in the run's
    `constant_thrust.propellant_remaining` and `delta_v` series and in
    the command line's run summary.
  - **41, velocity pointing and navigation errors.** Template 07's
    microsatellite on three wheels in `velocityPoint`, with a star
    tracker, an IMU and a magnetometer (the **device catalogue's MM200**
    noise), for 0.07 day in March 2027. **Why 2027:** the World Magnetic
    Model 2025 is valid from 2025.0 to 2030.0, and the 2030 epoch of the
    other templates is at its end. The navigation errors are
    **illustrative** (attitude 0.002 deg a step within 0.02 deg, rate
    0.0001 deg/s within 0.001 deg/s, position 1 m within 10 m, velocity
    0.01 m/s within 0.1 m/s, seed 41), of the order a star tracker, a
    gyro and a GNSS receiver give. A first draft had the rate bound at
    0.005 deg/s (the values of `tests/test_navigation_error.py`): the
    pointing error was then 0.25 deg, and other draws moved the wheel
    speeds by 0.84 % of their scale (see TPL-A3). With 0.001 deg/s the
    error is about 0.07 deg and other draws move them by 0.22 %.
  - **42, other atmosphere models.** One 150 kg satellite at 350 km, two
    days from 1 October 2024, drag from the **tabular** model with
    NRLMSISE-00's nominal profile (`engine/atmosphere_tables.py`, a
    table Basilisk ships). **Why this table:** the US Standard
    Atmosphere stops at 86 km and Earth-GRAM 2016's profile at 200 km.
    **Why October 2024:** near the maximum of solar cycle 25, so
    NRLMSISE-00 with the observed space weather ("Try changing") gives
    about seven times the decay of the fixed profile; in January 2030,
    at 320 km, the two differed by about 15 %. The exponential model shows in "Try
    changing" only: at 350 km it gives no drag. The End of Life
    estimate reads the same table (re-entry after about 350 days at
    Cd 2.2).
  - Every spacecraft is 150 kg, the class the app is for
    (`tests/test_scenario_templates.py`).
- **Decision TPL-A2: the claims tests.** `tests/test_template_claims.py`
  has one test per template. Each checks what the description says:
  39, the TLE spacecraft's mean semi-major axis against SGP4's (0.5 km)
  and its inclination in TEME of date (0.01 deg), the state vector's
  apsides and its fixed perigee; 40, the rise and the fall, the gap
  against Gauss's equation (2 %) and the propellant against F t / (Isp
  g0); 41, the true pointing error against the bound the errors imply
  (the attitude bound as a rotation, plus 4 x P/K x the rate bound, plus
  0.01 deg), and below 0.01 deg without errors; 42, the tabular decay
  against NRLMSISE-00's and the exponential model's, and the two
  lifetimes. **Why bounds for 41:** another C++ standard library draws
  other errors (TPL-A3). Eight seeds gave 0.064 to 0.076 deg, against
  the implied 0.104 deg.
- **Decision TPL-A3: a navigation error is noise in the golden
  comparison.** `simpleNav` draws its errors with Basilisk's
  GaussMarkov, from `std::normal_distribution`, as the sensors do. So
  on another standard library (Windows) template 41 draws other errors.
  `tests/golden_capture.py` now treats a `navigation_error.` series like
  a `sensor.` one: compared value by value only on the library that
  recorded it, elsewhere by its count. The attitude, rates, wheels and
  torques that the errors steer are still compared, to the other
  library's 1 %. Measured here with six other seeds as a stand-in for
  another library: at most 0.22 % of scale (wheel speeds). No existing
  template has a navigation error, so no existing comparison changes.
  A new test in `tests/test_golden_outputs.py` checks the rule.
- **Decision TPL-A4: the records.** Each template has a Customize wizard
  (39: state-sat's perigee and apogee, the state made again at the
  perigee; 40: thrust, specific impulse, propellant; 41: the attitude
  and rate bounds, the step kept at a tenth of the bound or less, and a
  duration page from 0.01 day; 42: the orbit, the drag area, the
  duration), a row in the templates' README, a place in the learning
  path, and `tests/data/scenario_hashes.json` gained its two hashes. A
  new page, `docs/reference/template-coverage.md`, lists each feature
  with its templates and the gaps for batch B (`BACKLOG.md`). Two tests
  pin the number of templates; only that number changed, from 37 to 41
  (`docs/ui/TEST_CHANGES.md`). The repository's root `README.md`
  (outside `SpaceMissionStudio/`) still says 36 templates: it is part of
  the Basilisk framework's tree, which this work does not change.
