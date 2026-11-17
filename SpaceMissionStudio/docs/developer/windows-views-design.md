# SpaceMissionStudio 2.12.0: windows and views (design)

Date: 2026-11-17. Status: accepted under the owner's standing instruction; questions answered at the end. Written from
the code of release 2.11.0. Paths are relative to `SpaceMissionStudio/`.
Nothing in this note changes a file format, the engine or a golden file (section 9).

## 1. Thermal plot: cramped and skewed (defect)

**Today.** `thermal/plots.py:150-151,186` writes a fixed 900 x 420 SVG with a white background
(`:69`) and its own font (`:39`, DejaVu Sans). `gui/thermal_widget.py:197-202` shows it in two
`QSvgWidget`s with a minimum height of 380 px (`_PLOT_HEIGHT_PX`, `:58`). The page is a stack of
`QGroupBox` frames (`:170-221`) in a `QScrollArea` (`gui/main_window.py:336-338`).

**Root cause.** `QSvgWidget` paints the SVG into its whole rectangle with the renderer's default
`IgnoreAspectRatio`, so x and y stretch differently: at 1400 x 380 px, x 1.56 and y 0.90, so text
and legend are 1.7 times too wide. The SVG ignores the theme (white in dark mode), and the group
boxes break "no group-box frames".

**Change (GUI only).**
- New `gui/svg_plot.py: SvgPlotView`: draws the SVG with `QSvgRenderer` in a rectangle of the SVG's
  own aspect ratio (`setAspectRatioMode(KeepAspectRatio)`, PySide6 6.7 or later; the pin is 6.11.2,
  `pyproject.toml` says `>=6.6`, so raise the floor to 6.7 or centre the rectangle by hand).
- Screen only: render at the view's width (about 2.1 : 1) with theme colours and Inter / JetBrains
  Mono, through new optional `style=` arguments of `temperature_svg`/`heat_flow_svg`. Make the text
  in a worker, debounced about 250 ms after a resize, and on `theme.on_change`. Defaults stay, so
  Save SVG/PNG and `spacemissionstudio thermal --tables` write the 2.11.0 files. A new T-nn amends
  T-31 ("the screen and both exports are the same picture"): same content, screen size and theme.
- Page (thermal gap analysis, phase 1, item 2): a toolbar row, then tabs (Temperatures, Heat flows,
  Summary, Heaters and radiators, 3D model, Studies, Notes). No group boxes, no outer scroll area.
  Findings go to the Problems panel, with one status line on the page.

**Tests.** `tests/gui/test_thermal_pages.py:158-238` reaches `temperature_svg`, `flow_svg`,
`flow_plot.isHidden()`, `tables["heaters"][0]`, `model_view`, `colour_combo`, `time_slider`,
`study_table`. These names stay (`tables[key]` stays a `(page, DataTable)` tuple), so no change.

## 2. One breakout-window mechanism

**Today.** The precedent, the 3D model editor, is a non-modal `QDialog` with no transient parent
(`gui/model_editor_dialog.py:302-308`, `gui/widgets.py:67-83`), one per spacecraft
(`gui/spacecraft_editor.py:3520-3565`). It edits a copy with OK/Cancel. A view needs the same live
widget in another window, with no copy.

**Proposal: `gui/breakout.py`.**
- `BreakoutWindow(QWidget, Qt.Window)` has the app icon and the title "<view> - SpaceMissionStudio".
  It opens through `show_window()`. `Breakouts.register(view_id, widget, title)` (one per
  `MainWindow`). **Detach** reparents the same widget object into the window. Its old slot (tab
  index and text kept) gets an `EmptyState` ("3D View is in a separate window", **Bring back**,
  primary). **Re-attach** (the shortcut, Bring back, or closing the window) moves it back. One
  widget moves, so nothing is built twice: the web view, the scene, the live timer and the cursor stay.
- **Geometry per view**: `layout.ini` (`main_window.py:1422-1425`), key `breakout/<id>/geometry`,
  written on re-attach and on quit. It is restored only when the rectangle is on a screen that still
  exists. Otherwise the window is centred on the main window's screen.
- **Keyboard**: registry command `view.breakout` "Open in Separate Window / Bring Back",
  `Ctrl+Shift+D` (free in 2.11.0), on the view shown. View > Separate Windows has one entry per view.
  All are in Ctrl+K. Main-window shortcuts are `WindowShortcut`s, so the window adds the global
  actions (`addActions`): Ctrl+K, Ctrl+S, Ctrl+R and Ctrl+Shift+D work there too.
- **Theme**: `apply_theme` styles the whole `QApplication` (`theme/apply.py:164-168`), so a new
  top-level window is styled. The views already redraw on `theme.on_change`.
- **Calm and focused view**: SMS has no D-191. That rule is System Budget Studio's. SMS has "Calm
  by default" (`docs/DECISIONS.md:3239`). So views open docked at start, and no window opens by
  itself. If the merge brings D-191, a separate window has the main window's focus level and never
  shows Inspector or Provenance. A problem link there calls `MainWindow.show_problems()`
  (`main_window.py:1105`) and raises the main window.
- **Window rules**: `show_view()` (`main_window.py:1119`) raises the separate window of a detached
  view (this covers `start_live`, `:2534-2535`). `closeEvent` (`:2903`) re-attaches all views before
  `saveState`.
- **WebGL**: a `QWebEngineView` that moves to another native window can lose its context.
  `mission_view.js` has no `webglcontextlost`/`restored` handler. Add one: rebuild the renderer and
  call `MV.load(MV.data, {keepCamera: true})`.
- **Tests (offscreen)**, new `tests/gui/test_breakout.py`: the same `web_view` and `scene` objects
  after detach and re-attach. The placeholder shows. `Ctrl+Shift+D` toggles. Geometry round-trips
  through a temporary HOME. A theme switch restyles the window. Close re-attaches. A live run runs
  while detached. `WEBGL_lose_context` recovers. Add DESIGN.md shortcut rows
  (`test_design_rules.py:78`) and View menu entries (`test_shell_reachability.py:369`).

**Views in 2.12.0.** The 3D globe, the live map (section 3) and Thermal. **Budgets** is cheap too,
but B-21 (`docs/developer/system-budget-decisions.md:212`) acts "only on the Budgets page shown":
does a detached page count as shown (Q2)?

## 3. Live 3D view: ground tracks, stations and a live 2D map

**Live data path today.** "Show in 3D View while running" makes a `LiveFeed`
(`main_window.py:2482-2484`); a probe pushes `(t, r, v, sigma)` (`engine/live_view.py:206-280`).
`MissionViewWidget._live_tick` (`gui/mission_view_widget.py:486-516`, 20 Hz, `:89`) drains it,
extends the scene **on the GUI thread** (`live_frames` -> `scene3d.extend_scene`, `:175-181`,
bounded by `LIVE_BATCH_STATES`, "about 20 ms", `:91`) and sends `MV.append(JSON)` (`:535-546`).
`extend_scene` already computes `ground_track_deg` (geocentric, `engine/scene3d.py:92,226,459-460`)
and `station_visible` (`:465-468`); a finished run has the same arrays (`:518`).

**Ground track missing (defect, by default).** The globe draws it (`mission_view.js:548-575,
761-768`), but the toggle is off by default (`mission_view_widget.py:100`, `mission_view.js:34`).
Change: on by default (owner item 4), as a decision, with the test change logged (section 8).

**Station not recognisable (defect).** A station is an 8 px square `THREE.Points`
(`mission_view.js:425-437`, `theme/mission_view_style.py:36`) in near-white `#F4F5F7`
(`theme/palettes.py:79`): lost on clouds and ice, no outline, no shape. Change: a 14 px screen-size
sprite (triangle on a mast) with a 1 px dark outline, the label kept, and a surface ring at the
visibility circle (below), stronger while a spacecraft is in view. Colours from `palettes.py`; no
status colours.

**Live 2D map (new): `gui/ground_map_widget.py: GroundMapWidget`.**
- Projection: equirectangular, `x = (lon + 180) / 360 * W`, `y = (90 - lat) / 180 * H` (2 : 1).
  Label "geocentric latitude" (at most about 0.19 deg from geodetic).
- Background: `gui/assets/mission_view/earth_day_2k.jpg` (2048 x 1024, -180 to 180 deg; 4k on wide
  screens), NASA Blue Marble SVS 2915, public domain, already listed (`docs/THIRD_PARTY_ASSETS.md:19`,
  `NASA_IMAGES.txt`). No new asset, no new licence. The map's tooltip gives the NASA credit.
- Tracks: `scene.crafts[k].ground_track_deg`, split where `|dlon| > 180 deg`, in each craft's
  categorical colour, with a marker at the playback frame.
- Stations: the globe's glyph, a label, and a visibility circle per spacecraft at its current
  altitude: Earth central angle `lambda = acos(R / (R + h) * cos(eps)) - eps`, `eps =
  min_elevation_deg` (Wertz and Larson, *Space Mission Analysis and Design*, 3rd ed., section 5.2).
  A contact (`station_visible`) draws the station-to-subpoint line.
- Off the GUI thread: a worker paints the static layer (texture plus tracks) into a `QImage` at
  device pixels (allowed outside the GUI thread). A live run adds only the new segments.
  `paintEvent` draws the image plus markers and labels (well under 5 ms). Resize (debounced) and
  `theme.on_change` repaint the layer.
- Place: inside the 3D View tab, a `SegmentedControl` "Globe | Map | Both" (Both is a splitter). So
  `test_workspace.py:99` and `test_live_run_3d.py:85` stay. Globe and map detach separately.

**Shared feed without double work.** `LiveFeed.drain` removes samples (`live_view.py:173-187`,
pinned by `test_live_view.py:70`), so no second consumer can drain it. Extract `LiveScene` (QObject,
one per run) from `_live_tick`: it owns the 20 Hz drain, runs `extend_scene` and the
`frames_payload` JSON in one serial worker, and emits `extended(start, stop)`. The globe only calls
`runJavaScript`; the map's worker adds segments. Extract `Playback` (frame, playing, following,
speed), so globe and map follow one clock and the shared `TimeCursor`. A hidden view skips its work
and catches up on show, as now (`mission_view_widget.py:439-447`). Detach is a reparent, so docked
and detached never both work. The GUI thread only gets signals and paints (D-182/D-183 in System
Budget Studio; in SMS, CLAUDE.md "Never freeze").

## 4. Thermal results on the 3D View (playback of a finished run)

Thermal is solved after the run (T-01, `docs/developer/thermal-decisions.md:8`). So "live" means
temperatures that follow the playback and time cursor of the finished run; none exist while
Basilisk runs. Today per-part colours exist only in the small Plotly view on the Thermal page
(`thermal_widget.py:224-275`, `model_view_widget.py:119-151`). The 3D View has `face_rgb` per
triangle (`mission_view_widget.py:129`), but `scene3d.spacecraft_mesh` drops each triangle's part
(`engine/scene3d.py:316-343`).

Change: `spacecraft_mesh` also returns `part_of_triangle` (display data). The 3D View gets a Colour
list "Model | Temperature: <case>", enabled when `ThermalWidget.analysis` belongs to the run shown.
A worker resamples each node to the scene's frame times and maps it to RGB on a fixed scale per
case (stops in `theme/palettes.py`, the diverging scale of `TEMPERATURE_SCALE`). The page gets the
table once; `MV.setFrame` writes the colour attribute. A colour bar overlay shows degC.

## 5. App icon barely visible on Ubuntu (defect)

**Today.** `gui/icons.py:102-170` draws a plate-less glyph turned -32 deg: blue panels, gold body,
lines (`theme/palettes.py:57-62`). `app_icon()` has 16 to 256 px (`:173-181`). The `.deb` and
`install.sh:164-172` install only `hicolor/256x256/apps/spacemissionstudio.png`
(`packaging/build_deb.sh:82-88`). **Measured** (PySide6 6.11.2 offscreen, WCAG luminance): the glyph
covers 30 % of the canvas at every size; the panels are about 84 % of the glyph.

| Colour | on #303030 | on #1D1D1D | on #242424 | on #FAFAFA | on #EBEBEB |
|---|---|---|---|---|---|
| panel #2563EB | 2.55 | 3.26 | 3.00 | 4.95 | 4.34 |
| panel line #1E3A8A | 1.27 | 1.63 | 1.50 | 9.92 | 8.69 |
| body #CFB87C | 6.79 | 8.67 | 7.98 | 1.86 | 1.63 |

At 64 px on #303030, 86 % of the glyph is below 3 : 1. On light panels, the gold body is at 1.6 to
1.9. Root cause: there is no plate, the glyph is small, and the blue is too dark for dark panels.

**Fix that keeps the design.** Same glyph and colours on a rounded-square plate `#0F172A` with a
2/64 rim `#94A3B8`; the glyph fills about 80 % of the plate; grid lines in the plate colour.
Measured: plate on #FAFAFA 17.1, on #EBEBEB 15.0; rim on #303030 5.15, on #1D1D1D 6.57; panel on
plate 3.45, body on plate 9.18. Add `APP_ICON["plate"]`/`["rim"]` and a contrast test in
`test_icons.py` (3 : 1 or more against all four panels). `test_icons.py:55-78` still passes.

**Later (2026-11-17).** The owner chose a new drawing: a mission scene (the Earth from the Blue
Marble texture, an orbit, a satellite with a link beam, the Sun) inside the same plate, in the
scene's navy: plate `#1A2C57`, rim `#5B7FC7` (rim on #303030 3.33, on #1D1D1D 4.26; plate on
#FAFAFA 13.05, on #EBEBEB 11.43). The plate's geometry, the sizes, the SVG, the `.ico` and the
tests stay. See `docs/DECISIONS.md`, "The app icon shows a mission".

**Sizes.** Install hicolor 16 to 512 PNGs and `scalable/apps/spacemissionstudio.svg` (same painter
code through `QSvgGenerator`) from the `.deb` and `install.sh`. Software centres want 128 px or
scalable. `postinst` already updates the icon cache. **Windows**: no `.ico` exists; the shortcuts
use Python's icon (`packaging/windows/spacemissionstudio.iss:103,105`, `IconFilename:
"{app}\python\python.exe"`). Add `packaging/make_ico.py` (standard library; PNG entries 16 to 256)
for `SetupIconFile`, `UninstallDisplayIcon`, `IconFilename` and `install.ps1:166-172`.

## 6. AppStream metainfo for the Ubuntu App Center (missing)

**Today.** The `.deb` has no `/usr/share/metainfo/`, and `control.in` has no licence field (Debian
has none). So App Center shows no screenshots, details, licence or age rating.

**Id and file.** Keep the desktop id `spacemissionstudio.desktop`: `gui/app.py:104` sets it,
`tests/gui/test_app.py:43` pins it, and dock favourites store it. Use a reverse-DNS component id
with `launchable`: `io.github._0h3xn4.SpaceMissionStudio` (a segment that starts with a digit gets a
leading `_`, as on Flathub). File: `/usr/share/metainfo/io.github._0h3xn4.SpaceMissionStudio.metainfo.xml`.

```xml
<component type="desktop-application"><id>io.github._0h3xn4.SpaceMissionStudio</id>
  <name>SpaceMissionStudio</name><summary>Design and analyse spacecraft missions with Basilisk</summary>
  <metadata_license>CC0-1.0</metadata_license><project_license>EUPL-1.2</project_license>
  <developer id="io.github._0h3xn4"><name>SpaceMissionStudio contributors</name></developer>
  <description><p>(from README.md, publication voice, not STE)</p></description>
  <launchable type="desktop-id">spacemissionstudio.desktop</launchable>
  <url type="homepage">https://github.com/0h3xn4/basilisk_space-mission-studio</url>
  <screenshots><screenshot type="default"><caption>Results › 3D View</caption><image>https://raw.
  githubusercontent.com/0h3xn4/basilisk_space-mission-studio/spacemissionstudio-v@VERSION@/
  SpaceMissionStudio/docs/images/appstream/3d-view.png</image></screenshot>(+3 more)</screenshots>
  <content_rating type="oars-1.1"/><provides><binary>spacemissionstudio</binary></provides>
  <releases><!-- generated at build time --></releases></component>
```

- Build: template `packaging/metainfo.xml.in`. `build_deb.sh` fills `@VERSION@`, writes
  `<releases>` from the last 5 `## X.Y.Z (date)` sections of `CHANGELOG.md` (summary paragraph,
  via `release_notes.changelog_section()`, `packaging/release_notes.py:73`), and runs
  `install -D -m 644` to `$staging/usr/share/metainfo/`.
- Screenshots: 1280 x 720 PNGs from `scripts/capture_ui_screens.py` on an invented example, in
  `docs/images/appstream/`. The URL pins the tag (`spacemissionstudio-v<version>`,
  `release_notes.py:146`). It works only while the repository is public.
- Offline: SMS reads none of this at run time; only the software centre fetches the images. Say
  so in `docs/reference/network.md`.
- CI: the `.deb` builds on `ubuntu-24.04`, no container (`.github/workflows/
  spacemissionstudio-release.yml:61,95-99`). Ubuntu 24.04 has `appstream` (appstreamcli 1.0.x) and
  `desktop-file-utils`. Install both, then run `appstreamcli validate --no-net --explain` and
  `desktop-file-validate`, there and in `spacemissionstudio.yml`. appstreamcli fails on warnings.
  Not run here: appstreamcli is not in this sandbox.
- Not certain: App Center may show a downloaded `.deb` before install from control fields only.
  Check both pages by hand on Ubuntu 24.04.

## 7. Records to write

DECISIONS (breakout, map, station marker, track default, icon plate, AppStream); a T-nn amending
T-31; `docs/ui/TEST_CHANGES.md`; DESIGN.md (shortcut rows, breakout rule); USER_MANUAL plus
`scripts/sync_help.py`; CHANGELOG "Unreleased"; `docs/reference/network.md`; THIRD_PARTY_ASSETS.md
(the map as a second use of Blue Marble, no new row). Never name the other tool: "a separate window".

## 8. Tests that pin the current behaviour

| Test | Pins | 2.12.0 |
|---|---|---|
| `tests/gui/test_mission_view.py:288` | ground track off by default | **changes**: needs the owner's decision (item 4), logged in TEST_CHANGES.md |
| `tests/gui/test_mission_view.py:300,363` | toggles remembered; style keys | no change (keys are added, none removed) |
| `tests/gui/test_mission_view.py:427-502`, `test_live_run_3d.py:98-135` | live frames, `view.scene`, `slider`, `play_button`, `following` | no change if `MissionViewWidget` keeps them as forwarding attributes after the extraction |
| `tests/test_live_view.py:70` | each sample is drained once | no change (one consumer) |
| `tests/gui/test_workspace.py:99`, `test_live_run_3d.py:85` | tab names; the "Show in 3D View while running" label | no change (the map is inside 3D View) |
| `tests/gui/test_thermal_pages.py:158-238` | thermal widget attributes | no change (names kept) |
| `tests/test_thermal_analysis.py:162-164` | thermal SVG files | no change (export defaults kept) |
| `tests/gui/test_icons.py:24-78`, `tests/gui/test_app.py:43` | icon not blank, gold body; desktop file name | no change |
| `test_design_rules.py:78`, `test_shell_reachability.py:369`, `test_menu_bar.py` | shortcut table, one menu per command | no test change; DESIGN.md gets rows |

A separate "Map" tab instead would change `test_workspace.py:99` and needs a decision (Q3).

## 9. Golden files and file formats

No change: no scenario or project field, no schema version step, no engine or CLI change. `scene3d`
additions are display data. Thermal files keep the 900 x 420 defaults. The 36 files in
`tests/golden/` stay byte-identical. Only the `.deb` gets new files (icons, metainfo).

## 10. Delivery (hours are for this agent, with tests and records)

| PR | Content | Hours |
|---|---|---|
| PR-1 Thermal results | `SvgPlotView`, screen SVG at size and theme in a worker, tabbed page, temperatures on the 3D View (section 4), T-nn | 7-10 |
| PR-2 Breakout windows | `gui/breakout.py`, command and shortcut, geometry, WebGL context recovery, 3D View and Thermal (Budgets after Q2), tests | 6-9 |
| PR-3 Tracks, stations, live map | `LiveScene`/`Playback` extraction, `extend_scene` off the GUI thread, `GroundMapWidget`, globe marker and ring, track on by default | 10-14 |
| PR-4 Desktop integration | icon plate and contrast test, hicolor sizes and SVG, `.ico` and Inno Setup, metainfo, CI validation, screenshots | 5-7 |

Total about 28-40 h. PR-4 does not depend on the others and can go first. PR-3 builds on PR-2.

**Risks.** (1) WebGL context loss on reparent (some drivers, SwiftShader): the handler and a test.
(2) Wayland ignores a saved position (it keeps the size), and a saved screen can be gone: validate
and fall back. (3) The `LiveScene` extraction touches a subtle, tested path (cancel, the result
replacing frames): keep the public names, and repeat the live tests before merge. (4)
`np.concatenate` in `extend_scene` is O(n) per tick: it moves to the worker. (5) AppStream: the
digit segment in the id, a public repository for the screenshot URLs, and the pre-install page.
(6) A geocentric track differs slightly from geodetic plots: the label says which. (7) Scope: the
thermal range chart (G4) stays in the thermal plan.

**Questions for the owner, answered from the owner's feedback (2026-11-17).**
- Q1, ground tracks on by default: **yes**. The owner wrote "I am missing the ground-tracks on the earth surface". The one changed test line is logged in `docs/ui/TEST_CHANGES.md` with this reason.
- Q2, Budgets detachable: **yes**. The owner wrote "every bigger feature inside SpaceMissionStudio should have its own breakout window". A detached page counts as shown for B-21.
- Q3, the live map: **inside the 3D View area, with its own breakout button**, so it can sit beside the globe in its own window. No tab-name test changes.
- Q4, the AppStream id: **`io.github._0h3xn4.SpaceMissionStudio`** (reverse DNS of the public repository; the underscore is the AppStream rule for a name part that starts with a digit).
