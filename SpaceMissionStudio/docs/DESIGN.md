# SpaceMissionStudio design system

The reference for how the app looks and behaves: its colour tokens, type,
layout, components, message and feedback patterns, and keyboard model.
It describes what the code does today. Where a rule is checked by a test,
the test is named; where the app falls short of `docs/ux-standard.md`,
the gap is listed under [Known gaps](#known-gaps) rather than glossed
over.

- **Standard:** `docs/ux-standard.md` (the goals).
- **Audit:** `docs/ux-audit.md` (the findings and each iteration's changes).
- **Brief:** `docs/ui/UI_OVERHAUL.md` (the design language this follows)
  and `docs/ui/UI_OVERHAUL_PLAN.md` (its milestones).
- **Single source of truth:** the theme package
  `spacemissionstudio/gui/theme/`. Its tokens generate the application
  style sheet, the `QPalette`, the Plotly template, the chart palette and
  the icon tints. No widget picks a colour, a font or a size of its own.
- **Decisions:** `docs/DECISIONS.md`; licences: `docs/THIRD_PARTY_ASSETS.md`.

This replaces the Carbon-based system of 1.0 and 1.1 (IBM Carbon g10/g100
colours and IBM Plex), which stays in git history.

## Contents

1. [Foundations](#foundations): colour, status colours, data colours,
   type, layout, icons
2. [Components](#components)
3. [Patterns](#patterns): messages, feedback, keyboard, themes, long
   operations, empty states, views in their own windows
4. [Rules for new code](#rules-for-new-code)
5. [Checking a change](#checking-a-change)
6. [Known gaps](#known-gaps)

## Foundations

### Colour

Calm, neutral surfaces with one accent; colour only where it means
something. The tokens are the brief's table, the same in
SpaceMissionStudio, SystemDesignStudio and HarnessDesignStudio
(`theme/tokens.py`, `BRIEF`). Values changed to pass WCAG 2.2 AA are in
`tokens.ADJUSTED` and in `docs/DECISIONS.md`; everything else is derived
from the table (`tokens.tokens(mode)`).

- **Accent:** the primary action, the selection and the focus ring only.
  **One accent button per view** (UI audit B2): the top bar's Run, while
  a run can start. A page's own buttons are secondary (the Run area's
  Run, Check, Estimate, the empty states' Run and Add, Bring Back). Two
  exceptions, both while Run cannot start because no scenario is open:
  Home's Open template and the work areas' New Scenario. A disabled Run
  is grey, so such a view has no second accent
  (`tests/gui/test_primary_action.py` walks every area, tab and Scenario
  page).
- **Surfaces, not lines:** areas differ by background (canvas, surface,
  raised) and spacing; borders are 1 px and subtle, for inputs, table
  headers, panels and splitters. Group boxes have no frame: their title
  is a heading.
- **Themes:** light and dark, following the system by default, switched
  live (Settings > Appearance).

| Token | Light | Dark | Use |
|---|---|---|---|
| `bg.canvas` | `#F7F7F8` | `#0B0D10` | window background (the brief) |
| `bg.surface` | `#FFFFFF` | `#111418` | lists, tables, cards, plots (the brief) |
| `bg.raised` | `#FFFFFF` | `#171B21` | menus, popups, tooltips (the brief; light: plus a border, Qt draws no shadows) |
| `bg.hover` | `#F0F1F3` | `#1D222A` | hovered rows and controls (the brief) |
| `border.subtle` | `#E4E5E9` | `#222832` | panel and table edges, splitters (the brief) |
| `border.strong` | `#D0D3D9` | `#2E3540` | input borders, check boxes (the brief) |
| `text.primary` | `#16181D` | `#E7E9EC` | body text (the brief) |
| `text.secondary` | `#50565F` | `#A1A8B3` | hints, labels, axis text (the brief) |
| `text.muted` | `#666D77` | `#868E9A` | placeholders, the off status (the brief; adjusted, see DECISIONS) |
| `accent` | `#2563EB` | `#4C8DFF` | the primary action, selection and focus only (the brief) |
| `bg.selected` | `#E9EFFD` | `#1A273D` | selected rows: the accent at 10 % (light) or 16 % (dark) over bg.surface |
| `bg.field` | `#FFFFFF` | `#111418` | inputs: bg.surface |
| `border.focus` | `#2563EB` | `#4C8DFF` | the 2 px focus ring: the accent |
| `border.control` | `#88898C` | `#6B6D71` | the border of a field, a check box and a radio button: text.primary over the surface (51 % light, 42 % dark), 3:1 against every background a control sits on (WCAG 1.4.11; audit G7) |
| `text.disabled` | `#A6A7A9` | `#626569` | disabled text: text.primary at 38 % |
| `text.on_accent` | `#FFFFFF` | `#0B0D10` | text on the accent fill (dark: the canvas, white is 3.2:1) |
| `text.link` | `#2563EB` | `#4C8DFF` | links: the accent |
| `accent.hover` | `#2159D4` | `#5E98FF` | primary button hover |
| `accent.pressed` | `#1E4FBC` | `#70A4FF` | primary button pressed |
| `accent.soft` | `#CFDDFB` | `#253D67` | text selection in fields |
| `status.critical` | `#FF4D4F` | `#FF4D4F` | critical: icons and indicators (3:1) |
| `status.critical.text` | `#DA2331` | `#FF4D4F` | critical: words (4.5:1) |
| `status.critical.soft` | `#FFF3F3` | `#371D21` | critical: tinted background |
| `status.serious` | `#E16F18` | `#FF8A3D` | serious: icons and indicators (3:1) |
| `status.serious.text` | `#BD4E00` | `#FF8A3D` | serious: words (4.5:1) |
| `status.serious.soft` | `#FDF5EF` | `#37271E` | serious: tinted background |
| `status.caution` | `#BE8400` | `#F5B83D` | caution: icons and indicators (3:1) |
| `status.caution.text` | `#9E6500` | `#F5B83D` | caution: words (4.5:1) |
| `status.caution.soft` | `#FAF6ED` | `#352E1E` | caution: tinted background |
| `status.normal` | `#00A45D` | `#3DD68C` | normal: icons and indicators (3:1) |
| `status.normal.text` | `#00833F` | `#3DD68C` | normal: words (4.5:1) |
| `status.normal.soft` | `#EDF9F4` | `#18332B` | normal: tinted background |
| `status.standby` | `#3496D5` | `#56B4F5` | standby: icons and indicators (3:1) |
| `status.standby.text` | `#0077B4` | `#56B4F5` | standby: words (4.5:1) |
| `status.standby.soft` | `#F1F8FC` | `#1C2E3B` | standby: tinted background |
| `status.off` | `#666D77` | `#868E9A` | off: icons and indicators (3:1) |
| `status.off.text` | `#666D77` | `#868E9A` | off: words (4.5:1) |
| `status.off.soft` | `#F0F1F3` | `#1D222A` | off: tinted background |
| `code.key` | `#2563EB` | `#4C8DFF` | the JSON page: a key (text.link) |
| `code.string` | `#00833F` | `#3DD68C` | the JSON page: a string value (status.normal.text) |
| `code.number` | `#BD4E00` | `#FF8A3D` | the JSON page: a number (status.serious.text) |
| `code.literal` | `#0077B4` | `#56B4F5` | the JSON page: true, false, null (status.standby.text) |
| `code.punctuation` | `#50565F` | `#A1A8B3` | the JSON page: braces, brackets, commas, colons (text.secondary) |
| `code.current_line` | `#F8F8F8` | `#1E2125` | the JSON page: the cursor's line, text.primary at 3 % (light) or 6 % (dark) over bg.surface, every code colour 4.5:1 on it |
| `code.bracket` | `#F4F7FE` | `#1A273D` | the JSON page: a matched bracket, the accent at 5 % (light) or 16 % (dark) over bg.surface, every code colour 4.5:1 on it |
| `diff.added` | `#EDF9F4` | `#18332B` | diff background: normal tint |
| `diff.removed` | `#FFF3F3` | `#371D21` | diff background: critical tint |
| `diff.changed` | `#FAF6ED` | `#352E1E` | diff background: caution tint |
| `shadow` | `#16181D` | `#000000` | floating elements' shadow colour |

The table is checked against the theme package by
`tests/gui/test_design_rules.py::test_the_token_table_matches_the_theme`.

Widgets written before the token table read the role names in
`theme.PALETTE` (`text_muted`, `danger_soft` ...). Each role stands for
one token (`theme/state.py`, `ROLES`); new code uses the token names
(`theme.TOKENS["text.secondary"]`).

**Contrast.** Every pair the GUI draws is listed in
`tokens.CONTRAST_PAIRS` and tested in both themes
(`tests/gui/test_dark_theme.py::test_every_pair_the_app_draws_meets_wcag_aa`):

- text (primary, secondary, muted, links, status words) on every
  background it is drawn on: at least 4.5:1;
- icons, indicators and the focus ring: at least 3:1.

These are WCAG 2.2 criteria 1.4.3 and 1.4.11. Borders between surfaces
are deliberately low-contrast (the brief's 1 px subtle borders); an input
is also told apart by its fill and its hover and focus states.

### Status colours

The Astro UXDS taxonomy: critical, serious, caution, normal, standby, off.
A status colour means one thing everywhere, is the only coloured thing on
a neutral screen, and never stands alone: a status is always written out
as well (a badge's text, a problem's "Error:" or "Warning:", a toast's
words).

| Status | Means | Icon / indicator | Words | Tint |
|---|---|---|---|---|
| critical | error, failed, blocks a run | `status.critical` | `status.critical.text` | `status.critical.soft` |
| serious | a serious condition | `status.serious` | `status.serious.text` | `status.serious.soft` |
| caution | warning, look at this | `status.caution` | `status.caution.text` | `status.caution.soft` |
| normal | success, done, met | `status.normal` | `status.normal.text` | `status.normal.soft` |
| standby | information, in progress | `status.standby` | `status.standby.text` | `status.standby.soft` |
| off | neutral, not known | `status.off` (text.muted) | `status.off.text` | `status.off.soft` |

**Badges** (`gui/badges.py`): `set_badge(label, kind)` with
`MUTED` (off), `SUCCESS` (normal), `DANGER` (critical), `ACCENT`
(standby) or `WARNING` (caution); the style sheet's `[badge=...]` rules
draw them.

**Problem counts in the scenario tree** (`PageTree.set_problem_count`):
caution when every problem is a warning, critical when at least one is an
error; a tooltip counts each kind.

### Data colours

`theme.SERIES_COLORS` is the theme's 8-colour categorical palette
(`theme/palettes.py`), stepped for each theme's surface:

- **Order:** fixed, assigned in order and never cycled.
- **Every pair of the first six slots differs** (`palettes.SHOWN_TOGETHER`,
  the most series a standard plot shows: x, y, z, a quaternion, the
  timeline's six event kinds; UI audit B10): CIEDE2000 Delta E 18 or more
  with normal vision, 10 with simulated protanopia or deuteranopia and 7.5
  with tritanopia (Machado 2009, severity 1); x, y and z 30, and 20 with
  each deficiency
  (`tests/gui/test_theme.py::test_the_series_a_plot_shows_together_differ_in_every_pair`).
  A new palette meets the same floors.
- **Validated** with the data-visualisation palette validator in both
  themes, for adjacent pairs of all eight and for all pairs of the first
  six; every colour at least 3:1 against its surface.
- **Distinct from status and the accent:** every colour is at least
  Delta E 8 from each status colour and from the accent
  (`tests/gui/test_theme.py::test_the_categorical_palette_is_distinct_and_readable`).
- **One hue family per slot in both themes:** indigo, olive, brick, teal,
  magenta, violet, plum, orchid.
- **A legend always:** slots 7 and 8 are checked against their neighbours
  only, so colour is never the only cue.
- **On space or the Earth's image** (3D View, live map) the spacecraft take
  the dark steps in both themes (`palettes.depicted()`): the light steps are
  made for a white surface.
- **Data, not the accent:** a chart line takes a categorical colour, never
  the accent (End of Life's altitudes, UI audit B10).

The 3D view's body axes use x red, y green, z blue
(`palettes.AXIS_COLOURS`): an identity convention for geometry, not a
status.

**Results › 3D View** takes its whole look as data from
`theme/mission_view_style.py` (its page under `gui/assets/mission_view/`
holds no colour, font or size). What it depicts keeps the same colour in
both themes (`palettes.py`: black space, the Sun, the atmosphere's rim,
the nadir and velocity arrows, stations and their line of sight; each
spacecraft takes the categorical palette in order); fields of view are
the accent and plumes `status.caution`, as in the 3D model view. Its
overlays (the time panel and the labels) are floating panels on
`bg.raised` with `text.primary`, 8 px radius, JetBrains Mono for the
time, and restyle with the theme.

**Temperatures on a 3D model** (Run › Thermal's 3D model tab, Results ›
3D View's Colours list) take `palettes.TEMPERATURE_STOPS`: ColorBrewer's
diverging RdBu, reversed, cold blue to hot red, the same in both themes;
a part in no thermal node is `palettes.NO_TEMPERATURE_COLOUR` grey. Each
view shows a colour bar with the values and the unit (thermal decision
T-42).

**The thermal plots** are SVG made by the app (thermal decisions T-31,
T-40). On screen, `svg_plot.SvgPlotView` draws them at their own aspect
ratio, never stretched, and a worker makes them at the view's size in
`theme/svg_plot_style.py`'s look: `bg.surface`, the text tokens, Inter
with JetBrains Mono for the numbers, the categorical palette, the bands
in `status.normal` and `status.caution`, each named in the legend. The
exported files keep their fixed 900 x 420 look.

**Plots** take the Plotly template from the tokens
(`theme/plotly_template.py`): Inter, transparent backgrounds over
`bg.surface`, gridlines in `border.subtle`, axis text in
`text.secondary`, hover labels on `bg.raised`. Axis titles carry their
units, written as the window writes them (`units.axis_title`: "Inclination
[°]", "Torque [N·m]"; "[-]" for a dimensionless axis without a name). The
values and units follow Settings > Appearance > Plot units
(`plot_categories.shown`): the display units (km, °, h; body rates in °/s,
wheel speeds in RPM, velocity and delta-V in m/s) or as recorded (SI); the
Thermal plots' time axis follows it too, and no exported file changes. The
time cursor is drawn in the accent: it is a selection.

### Type

| Use | Font | Size | Weight |
|---|---|---|---|
| Caption | Inter | 11 px | 400 |
| Small text, table cells, field messages, the status bar | Inter | 12 px | 400 |
| Body (the base) | Inter | 13 px | 400 |
| Buttons, tabs | Inter | 13 px | 500 |
| Section title, scenario name | Inter | 15 px | 600 |
| Page title | Inter | 18 px | 600 |
| Display (rare) | Inter | 22 px | 600 |
| Numbers in tables, IDs, code, logs | JetBrains Mono, or Inter with tabular figures | 12 px | 400 |

- **Weights:** 400, 500 and 600 only.
- **Files:** Inter 4.1 and JetBrains Mono 2.304 as TTF, unmodified, under
  the SIL Open Font License 1.1 (`gui/assets/fonts/<family>/`), registered
  with `QFontDatabase` at start-up; the GUI never depends on a system font.
- **Tabular figures:** `theme.numeric_font()` switches on Inter's `tnum`
  where Qt supports font features (6.7 and later), and uses JetBrains
  Mono otherwise.
- **Roles:** a label's size and weight come from its role
  (`theme.set_role(label, role="section-title")`), not from code.
- **Tests:** `tests/gui/test_theme.py::test_the_bundled_fonts_register_and_are_the_application_font`.

### Layout

The app shell (`gui/shell.py`, `gui/app_shell.py`; M2a), with no menu
bar and no toolbar:

- **Navigation rail:** Home, Scenario, Run, Results, Budgets, Timeline
  and Reports (Ctrl+1 to Ctrl+7), Settings and Help at the bottom; icon
  and label, or icons only (its last button). A rail too short for the
  names (a 720 px window with the Problems panel open) shows icons only
  until there is room again; the tooltips and accessible names keep the
  names (decision B-19).
- **Area header:** the area's title and its commands as buttons (Run's
  run controls, Scenario's 3D Model...). A command there is a secondary
  button with an edge and a surface (`variant="secondary"`, the push
  button's look at the compact height), never a frameless word (UI audit
  UI-11); none is the accent. Every area shows it, Home,
  Reports and Settings too, and it has one height in every area
  (`theme.AREA_HEADER_HEIGHT`, 48 px), so the tab rows under it start at
  one height. The commands are one row; with no room for their names
  they show their icons only, the names in their tooltips and
  accessible names, until there is room again. With no scenario open
  the title stays and the commands step aside for the empty state.
- **Top bar:** across the window, under the menu bar and above the
  panels (UI audit UI-06): the window's menu widget (`windowHeader`)
  holds the menu bar and the top bar, so the Inspector and the rail start
  under it and never take its width. `MainWindow.menuBar()` returns the
  menu bar inside the header.
  - the scenario name, then its save state (an icon and the words
    "Unsaved changes", "Unchanged", "Saved" or "Not saved yet"), where it
    came from and the last run, with the breadcrumbs (area › page, in
    every area with pages) under them. The subtitle elides; its tooltip
    has all of it;
  - while there are any, the problem count, then Undo, Redo, Save (it
    always reads Save; the three are secondary buttons with an edge, as
    the area headers' commands, UI audit B8), Run (the one primary, accent, button; disabled,
    with the reason in its tooltip, while no run can start) with its
    mode, and the command search (Ctrl+K). The count comes first and the
    mode button is as wide as its longest mode, so no button moves when
    the count shows or the mode changes. A top bar narrower than
    `theme.TOP_BAR_COMPACT_BELOW` (1040 px: the top bar is as wide as the
    window) shows the search's icon and key only. At 1280 px with the
    Inspector shown the subtitle is whole.
- **Home (M3, `gui/load_scenario_widget.py`):** while it asks, the
  reference-data card across the top (it replaced the start-up dialog);
  then three columns: Start (New blank scenario, the recent scenarios
  with their empty state, Open a scenario file...), the template cards in as many columns
  as fit (at least 264 px each) with a filter, and the selected card's
  whole description with Open template (the page's one accent button
  while no scenario is open; with one open, the top bar's Run is the
  accent and Open template is secondary) and Customize. A card is a `card` surface: hover `bg.hover`, selected
  `bg.selected` with an accent edge, focus the 2 px ring; its three
  lines (attitude mode, orbit, the description's first sentence) are
  read from the template file. The cards are one Tab stop; the arrow
  keys, Home and End move between them, Enter opens.
- **Scenario area:** the scenario tree on the left. Each spacecraft has a
  node per part of its editor. The first form is **General** (name,
  mode, epoch, description): the area and the breadcrumb already say
  Scenario (UI audit UI-52). The tree is as wide as its longest node
  needs, between 170 and 340 px (`theme.PAGE_TREE_WIDTH`; UI-18): its
  minimum width follows its nodes, so a restored narrower splitter
  position cannot cut a name; a longer one is elided, whole on hover.
- **Page inset (UI audit UI-16):** every page of every area starts its
  content `theme.PAGE_INSET` (16 px) from its left and top edges, as the
  area header's title is inset: each tab of a tabbed area, the area
  itself when it has no tabs, each page of the Scenario tree and the
  JSON page. The area applies it (`shell.inset_page`, from `AreaPage`),
  so a page draws no margin of its own around its content. A page that
  scrolls itself (the Run page, Overview, Home, the embedded spacecraft,
  station and Environment forms) is marked `shell.INSET_INSIDE` and puts
  the inset inside its scroll area, so its scroll bar stays at the
  page's edge. The tab rows and the Scenario tree stay flush with the
  edges: they are navigation. `tests/gui/test_form_grid.py` measures
  every page. A section title starts at the inset too, where the line
  under it starts: the style sheet sets `qproperty-indent: 0` on
  `QLabel[role="section-title"]`, since its padding gave it a frame and
  Qt then indented its text by half an "x" (4 px; UI audit B8).
- **Forms (M4a, `gui/widgets.py`, `gui/units.py`):** a number field
  (`NumberField`, or any spin box `finish_form` styles) carries its unit as
  a suffix, typeset ("550.0 km", "97.59°", "1.000 m²", "300.00 Wh"),
  right-aligned in tabular figures, at most 224 px wide (128 px each in a
  row of several, shrinking to 72 px on a narrow page). The label is the
  name alone; messages still name the field "Name [unit]", the label's
  full text kept on it. A row too wide for its form puts its field under
  its label. An optional (checkable) group shows only its title while
  off. Rows of buttons or boxes wrap (`flow_row`) instead of widening the
  page. No framed panel and no scroll area inside a page.
- **One form grid (UI audit UI-26, `widgets.finish_form`):** all the
  forms of a page share one label column (`widgets.FormGrid`): the fields
  start at one x, whatever group or section holds them, as wide as the
  page's longest label needs, at most 224 px
  (`theme.LABEL_COLUMN_MAX_PX`); a longer label wraps onto a second line.
  A drop-down list is at most 320 px (`theme.FIELD_WIDTH["choice"]`; an
  entry longer than the field ends in "…", whole in the open list; a
  field sized to its entries shows them whole, UI audit B7), a
  number field at most 224 px (`FIELD_WIDTH["number"]`), and a button
  alone in a row keeps its own width at the left. The grid lines up again
  when a section is built, a group opens or a row shows. A form inside
  another form's field keeps its own column. Every Scenario page and
  Run › End of Life (its numbers are `NumberField`s) is checked at
  1280 x 720.
- **A disabled input says why (UI audit UI-42):** a field or button that
  is off has a tooltip that starts "Off:", says why and names what turns
  it on ("Off: the central body is a point mass. Tick Enable
  spherical-harmonics gravity to set it."): `widgets.set_off_reason`
  keeps the input's own tooltip after the reason and shows it alone
  while the input is on. Every disabled input on the Scenario pages and
  the Run and Reports tabs has one (a test walks them).
- **A command looks like its control (UI audit UI-11):** a choice of a
  few is a segmented control (`widgets.SegmentedControl`), an on/off
  command a check box (`widgets.ActionCheckBox`), any other command a
  framed push button (`widgets.ActionButton`), each bound to its
  registry action, so it follows the action's state and shows its
  tooltip with the shortcut. A page shows no frameless tool button that
  reads as text.
- **Settings (UI audit B7, `gui/settings_page.py`):** one section under
  the other, each a form on the page's one label column: Appearance
  (Theme, a segmented control System · Light · Dark; UI scale; Motion;
  Plot units), Reference data, Network (Network use, its note, the hosts,
  Open the network log), Change history (Author), Layout (Panels, Status
  bar and Navigation rail as check boxes; Reset Layout), Keyboard (a
  `DataTable`: the last column takes the width left, the keys in the
  monospace font, rows at `ROW_HEIGHT`, as tall as its rows) and About. A
  note under a field is a row of its own, hidden while empty.
- **Check boxes in a form (UI audit UI-53):** a list of choices to tick
  (the third bodies) is a `QListWidget` with the role `checklist`: no
  frame, the form's background, a row per choice at the table-row height
  (`RowHeightDelegate`), as tall as its rows, no scroll bar.
- **Inspector, on the right:** one dock, the focused field (Ctrl+I). No
  tabs. It opens `theme.INSPECTOR_WIDTH` (320 px) wide (UI audit UI-56;
  it was 380 px for one line of placeholder text). A new window narrower
  than `theme.INSPECTOR_MIN_WINDOW_PX` (1440 px), or on a narrower
  screen, starts without it, so it never squeezes a 1280 px window
  (UI-06); Ctrl+I shows it. An embedded Scenario form that scrolls
  itself keeps its scroll area as wide as the page and caps the form
  inside it (`scenario_editor._cap_form`), so its scroll bar sits beside
  the Inspector, with no strip between them that belongs to nothing. Explain is the Scenario tree's first node, Overview (M4b): asked
  for 250 ms after an edit and computed in a `QThread`, an overtaken
  answer dropped.
- **Form · JSON:** a segmented control in the Scenario area's header;
  JSON mode shows the text in place of the tree. Back to Form applies a
  waiting edit and is refused while the text does not apply (Discard).
- **Lists edit inline:** a device's or dispersion's form is under its list
  (`gui.inline_form.InlineForm`), applied 300 ms after the last edit once
  it validates, the reason above the form when it does not. Add creates
  the item and opens it; no modal dialog.
- **Run › History (M5a):** a `QTableView` over `HistoryModel`: status (an
  icon and a word), run, scenario, mode, start (ISO 8601 UTC with Z) and
  duration in JetBrains Mono, right-aligned duration, and whether it is
  saved; sortable, newest first, Ctrl+C copies TSV; an empty state with
  Run (secondary, and disabled with Run's reason while no run can
  start); the provenance in a popover (a card).
- **The Log's record of a run (M5a):** the GUI logs each run's start,
  end, warnings and where it is saved (`spacemissionstudio.run`), in
  JetBrains Mono, with the level filter, the search and Copy.
- **The end of a run (M5a):** saving and pruning in a worker; Compare
  refreshed when shown; the results drawn once.
- **Results › Overview (M6a):** `gui.results_overview`: one metric card
  (`role="card"`, 216 px wide, in a `FlowLayout`) per `run_summary`
  figure: its label in the secondary tone, its value in the numeric font
  (page size) and its unit; critical (an icon, the words, the critical
  tone) only for a link margin below the run's `link.required_margin_db`
  (0 dB by default) and a battery at or below the run's
  `results.battery_critical_fraction` of its capacity (empty by default).
  Worked out
  in a `QThread`; the provenance in History's popover; an empty state with
  Run.
- **The plot page (M6a):** one persistent `QWebEngineView` page
  (`plot_page.shell_page`): plotly.js loaded once, each change sent with
  `Plotly.react` (`render_script`, only the cells whose figure changed);
  the page reports "drawn" through its title (`plot_drawn`). Figures are
  kept per plot until what they show changes.
- **The Timeline (M7):** its table is a `DataTable` over lazy rows
  (`data_table.LazyRows`, `direct=True`): a row is formatted when shown,
  sorted with NumPy by a header click; columns sized from the first rows.
  The Gantt keeps each lane's starts, ends and their running maximum in
  NumPy arrays: what is in view is found by bisection and drawn merged by
  pixel. The axis is UTC with `Z` when the run has an epoch. Zoom: the
  wheel, `+`/`-`; pan: Shift+wheel, a right or middle drag, the arrow keys;
  fit: `0` or Home.
- **Reports › Exports (M8):** `gui.exports_page`, the first page of
  Reports: every export (`EXPORTS`) in a `DataTable` with its format,
  view, destination, provenance and the last time written, which each
  export records with `gui.export_log.record(key, path)` once its files
  are written. A new export adds a row to `EXPORTS` and records itself.
- **Motion and scale (M8):** toasts fade in and out over
  `feedback.TOAST_FADE_MS` (150 ms, ease-out), the only motion; with
  `theme.reduce_motion()` they appear and go at once. The UI scale
  (`theme.ui_scale_setting()`, 90-125 %) is applied as `QT_SCALE_FACTOR`
  by `app.main` before the application exists, so it takes effect at the
  next start.
- **DataTable (M6b):** `gui.data_table`, the table of a view: a
  `QTableView` over `DataModel` through a filter proxy; numeric columns
  right-aligned in the numeric font (units in the headers, typeset by
  `units.label`: "[deg]" shows "[°]"), a cell of text in one (`Row.plain`,
  a model's name) left-aligned; headings left-aligned, a numeric column's
  right; code columns (`code=`: keys, checksums) in the monospace font
  and the secondary colour; a muted second line under a cell
  (`Row.notes`: a key under a name), the rows then two lines high; a
  status as a word with its status icon and ink (`Row.marks`); no grid
  lines; group rows across the table as section headings, in the heading
  weight on `bg.canvas`, never selectable (UI audit B4, UI-19); bold and
  muted cells by role; Ctrl+C copies TSV with the header; the header's
  context menu shows and hides columns; columns sized once when filled;
  an empty state with its action. Output, Monte Carlo, Budget, Compare,
  Scenario › Assumptions, Settings › Keyboard and the Reference data
  window use it.
- **Editable tables:** a table edited in place is a model/view grid too
  (a `QAbstractTableModel` with `ItemIsEditable`): Budgets' grids
  (`budgets_area.GridModel`) and the 3D model's thermal records
  (`thermal_editor.RecordTable`, UI audit UI-13): no grid lines, numbers
  right-aligned in tabular figures, as tall as their rows, their columns
  fitted to the page (a heading or a value too long is elided, whole on
  hover), so a page never scrolls sideways; a list without a row shows
  its compact empty state with Add. The thermal model's ten kinds of
  record are six tabs that fit 1280 x 720: Nodes, Faces, Couplings, Heat
  loads, Cases and Solver.
- **Run › Run (M5b):** the run mode as a segmented control in the Run
  area's header (`gui.run_page.RunModeControl`, the same `segmentedControl`
  look as Form · JSON); the Run page (`RunPage`) shows what the next run
  uses for the mode chosen: Live plot for a single
  run, the archive folder (a field and Browse..., remembered per
  scenario) for a Monte Carlo batch, the spacecraft and the program for
  a SIL run. Forms that were dialogs are embedded (`embed_dialog`) and
  applied as edited; no OK.
- **Problems panel, at the bottom (Ctrl+J):** a `QTableView` over
  `ProblemsModel`: Severity (icon and word), ID (the field path), Object,
  Message; errors first, any column sorts, Ctrl+C copies TSV, Enter or a
  double-click goes to the field. Its counts are on its title, in the
  status bar and the top bar.
- **One place for a warning (UI audit B5, UI-37):** a problem or a
  warning is written out in the Problems panel only: the scenario's
  errors and plausibility warnings, Run › Plan's and Run › Thermal's,
  and the shown run's warnings (`ResultsWidget.run_warning_rows`, the
  run as their Object, their rule on hover). The top bar and the status
  bar show its count, which opens the panel (`MainWindow.show_problems`);
  a field with an error is marked under the field. There is no footer
  under the editor and no warning line on Results › Plots, whose
  provenance line names what produced the run only.
- **Status bar:** the run job (phase, progress, time so far and left,
  Cancel) while a run goes, the run state chip otherwise; then the problem count
  (it opens Problems), Basilisk version, reference data, Earth
  orientation data, frames. The run state chip and the problem count show
  only while a scenario is open: "No run yet" and "No problems" say
  nothing about no scenario (UI audit B8). A message about a file names the file
  ("Opened 01_two_body_circular_orbit.json"), with the whole path as the
  bar's tooltip while it shows. Every message (`feedback.show_status`,
  which `report` uses too) is elided in the middle to the room left of
  the permanent entries, so its end, a file name, stays in view and
  nothing is clipped at the first entry (UI-09); the whole text is then
  the tooltip.
- **Panels' title bars (UI audit UI-39):** each dock (Inspector,
  Problems, Calculation) has its own title bar (`app_shell.DockTitleBar`,
  `theme.DOCK_TITLE_HEIGHT`): its title (it follows the dock's, "Problems
  (3)"), then **Float** (**Dock** while it floats) and **Close** as
  compact icon buttons with 16 px icons, each with a tooltip and an
  accessible name that name the panel ("Float Inspector", "Close
  Inspector (Ctrl+I)"), reachable with Tab and pressed with Space. Qt's
  own buttons were about 10 px, with no tooltip. A drag or a double-click
  on the title still moves or floats the panel. The layout version is 6:
  a layout saved with Qt's title bars (version 5) opens the default
  layout.
- **Layout memory:** Settings > Layout > Reset Layout restores the panels
  and the rail. The layout (docks, rail, the main splitters) is kept per
  scenario file, and for the window between sessions (`layout.ini`).
- **Commands:** every command is in one registry (`gui/actions.py`):
  the command palette, the menu bar, the area headers, the top bar, the
  shortcut list and every tooltip ("Save (Ctrl+S)", then what it does)
  come from it.
- **Menu bar:** File, Edit, View, Go, Run, Tools and Help
  (`gui/menu_bar.py`, `MENUS`), each item a registry command, so a menu
  item, its shortcut and its buttons share one text and one enabled
  state. Every command is in exactly one menu
  (`tests/gui/test_menu_bar.py`). File > Open Recent reads the same list
  as Home. View > Menu Bar hides it (kept with the layout); the
  shortcuts and the palette work without it.
- **Dialogs fit their text:** every dialog is at least as tall as its
  layout needs at its width (`gui/theme/dialogs.py`, applied by the
  application style), so a wrapped line or a button is never cut off,
  whatever size the window manager gives it.
- **Dialogs fit the screen:** a dialog is never taller than the screen's
  free area less 64 px for the title bar, and one opened taller shrinks
  to it (`gui/theme/dialogs.py`). Tall content goes in a scroll area
  (`widgets.ScrollBody` for a dialog's body), so OK and Cancel stay in
  view. `tests/gui/test_dialogs_fit_the_screen.py` opens every dialog on
  a 1280 x 720 screen; a new dialog class gets an entry there.
- **Drop-down lists:** every combo box's list opens below the field,
  12 rows high with a scroll bar, at least as wide as its longest entry,
  with control-height rows, a hover mark and the current entry selected.
  A list of 12 entries or more has a "Type to filter" field: typing
  narrows the list, the arrows move in it, Enter picks
  (`gui/theme/combo.py`, applied by the application style to every combo
  box). Menus have 32 px rows.

| Measure | Value | Where |
|---|---|---|
| Grid | 4 px: 4, 8, 12, 16, 24, 32 | `theme.SPACE` |
| Control height | 32 px (28 px compact: header and top-bar buttons) | `theme.CONTROL_HEIGHT` |
| Table rows | 26 px | `theme.ROW_HEIGHT` |
| Corner radius | 6 px controls, 8 px panels, popovers and dialogs | `theme.RADIUS` |
| Focus ring | 2 px, the accent | `theme/qss.py` |
| Smallest window the views are checked at | 1280 x 720 px | `scripts/capture_screenshots.py --size` |
| Widest a form or a list editor grows | 960 px (`theme.CONTENT_MAX_WIDTH_PX`) | `scenario_editor._page`, the embedded forms, End of Life |
| Page inset | 16 px from a page's left and top edges, every page of every area | `theme.PAGE_INSET` |
| Number field | at most 224 px; 128 px each in a row of several, 72 px at least | `theme.FIELD_WIDTH` (`widgets.NUMBER_FIELD_MAX_WIDTH_PX`, `VECTOR_FIELD_MAX_WIDTH_PX`, `VECTOR_FIELD_MIN_WIDTH_PX`) |
| Drop-down list in a form | at most 320 px | `theme.FIELD_WIDTH["choice"]` |
| Form label column | one per page, at most 224 px (a longer label wraps) | `theme.LABEL_COLUMN_MAX_PX`, `widgets.FormGrid` |
| Scenario tree | as wide as its longest node, 170 to 340 px; 220 px to start | `theme.PAGE_TREE_WIDTH`, `gui/page_tree.py` |
| Results plot list | 16 % of the pane, 250 to 400 px, until the user drags the divider | `gui/results_widget.py` |
| Toast | as wide as its text on one line, at most 360 px; 16 px from the work area's edge, 8 px apart | `theme.TOAST`, `gui/feedback.py` |
| Inspector | 320 px; a new window under 1440 px starts without it | `theme.INSPECTOR_WIDTH`, `theme.INSPECTOR_MIN_WINDOW_PX` |
| A panel's title bar | a compact button's height and 4 px; 16 px icons on 28 px buttons | `theme.DOCK_TITLE_HEIGHT` |

**What keeps the full width:** plots, tables, the event timeline, the
JSON view, Compare and the model editor. A form keeps the left edge, and
the Scenario form sits at the top of its page.

**Fields:** a 1 px `border.strong` edge on `bg.field`, 6 px corners; hover
darkens the edge, focus draws the 2 px accent ring; an error or warning
draws a 2 px status ring (`tests/gui/test_input_borders.py`).

**Shadows:** Qt style sheets cannot draw them; floating elements (menus,
popovers, tooltips) are `bg.raised` with a 1 px border instead.

### Icons

- **One set:** Lucide (ISC licence), only the icons the GUI uses, in
  `gui/assets/icons/lucide/` with its licence.
- **Tinted from the tokens when drawn:** `theme.icon(name, ink)` returns
  a `QIcon` whose engine looks the colour up each time it paints, so an
  icon follows a live theme change; a disabled icon takes
  `text.disabled`. The style sheet's arrows and ticks are tinted copies
  (`theme/icons.py`, `icon_file`).
- **Sizes:** 16 px in the interface, 20 px in the navigation rail.
- **Command buttons:** every button of the top bar and the area headers
  has an icon, the run-mode drop-downs aside
  (`tests/gui/test_theme.py::test_every_command_button_has_an_icon`): Run
  in the accent, Cancel in critical, the rest in `text.secondary`. The
  top bar's Run draws its icon in `text.on_accent` on the accent fill.
  The top bar's Undo, Redo and Save are secondary buttons
  (`variant="secondary"`), as the area headers' commands.
- **App icon:** drawn in code (`gui/icons.py`) in `palettes.APP_ICON`: the
  Earth (the 3D view's Blue Marble texture), an orbit, a satellite with a
  link beam to a ground station, and the Sun, on a dark rounded-square
  plate with a light rim, so it has 3 : 1 or more on dark and light
  desktop panels (`tests/gui/test_icons.py`). The installers use the same
  drawing: the hicolor PNGs and SVG of the `.deb`, the `.ico` of the
  Windows setup (`packaging/make_ico.py --from-app`).
  `scripts/build_app_icon_files.py` writes the documentation copies
  (`docs/images/app_icon.png`, the banner's icon).

## Components

| Component | Code | Use it for |
|---|---|---|
| Page tree | `page_tree.PageTree`: `add_page`, `add_section`, `set_problem_count`, `show_page`, `show_section` | A view with several forms: one node per form, sections per part, problem counts on nodes |
| Embedded form | `page_tree.embed_dialog`, then `setMaximumWidth(CONTENT_MAX_WIDTH_PX)` | A dialog's form shown as a page: no window, no OK/Cancel, long rows wrap |
| Form fields | `widgets.SpinBox`, `DoubleSpinBox`, `PreciseDoubleSpinBox`, `ComboBox` | Numbers and choices: they ignore the mouse wheel unless focused, keep a value from a file that is outside their range (and mark it), and show full precision |
| Field map | each form's `field_widget(path)`, `field_title(code)`, `problem_text(message)` | Where a field is, and what it is called, for Problems and for messages |
| Finished form | `widgets.finish_form(root)`: units into the fields, optional groups that collapse, `limit_field_widths`, a `FormGrid` | Every form, dialog or page: fields at their widths and one label column per page (UI audit UI-26) |
| Off reason | `widgets.set_off_reason(widget, enabled, reason)`, `own_tooltip(widget, tip)` | An input that can be off: its tooltip says "Off:", why and what turns it on, before its own (UI audit UI-42) |
| Page inset | `shell.inset_page(page)`, `inset_stack(stack)`, the `shell.INSET_INSIDE` property | A page's content at `theme.PAGE_INSET` from its edges; `AreaPage` applies it to its pages (UI audit UI-16) |
| List editor | a list with Add / Edit / Remove at their own width, left-aligned | Spacecraft, stations, sensors, actuators, dispersions |
| Command controls | `widgets.ActionButton(action, text=None)`, `ActionCheckBox(action, text=None)`, `SegmentedControl(name).add_action(action, text)`; `defaultAction()` | A command on a page: a framed button, an on/off check box, or one segment of a choice of a few; each follows its registry action (UI audit UI-11) |
| Empty state | `widgets.EmptyState(title, text, action, primary=, compact=)`: `set_text`, `add_action`, `add_detail`, `text()` | The one empty state of every view, list and panel: a title, a line of text and the action that fills it. The full form sits in the middle of its area; `compact=True` is as tall as its lines, for a panel, a short list or the room beside a table |
| Empty list | `widgets.EmptyStack(view, empty_state, fit_rows=)`: `refresh(empty=None)`, `showing_empty()` | A list, tree or table, or its `EmptyState` while it has no row; `fit_rows=True` makes a short list as tall as its rows. Edit, Remove and the other actions on a row are off until a row is selected |
| Badge / tag | `badges.set_badge(label, badges.SUCCESS)` and the other kinds | A state in a word: Explain, the dashboard, rule results |
| Role | `theme.set_role(widget, role=..., tone=..., badge=...)` | A label's or frame's look from the style sheet: caption, heading, section-title, mono, hint, card; a status tone |
| Toast | `feedback.report(widget, text, kind)` | Something finished or failed, not tied to a field |
| Problem banner | `feedback.ProblemBanner` | Above a form: what is wrong in it |
| Stale results banner | `feedback.StaleResultsBanner` | Above the run views: the results no longer match the scenario, with Re-run |
| Field error | `feedback.show_field_error(widget, message, warning=False)`, `clear_field_error`, `clear_on_edit` | Under the field the problem is about, and the field marked |
| Dialog error | `feedback.show_dialog_error(dialog, text)` | A dialog's own problem, above its buttons |
| Problems | `workspace_panels.ProblemsWidget` (`ProblemsModel`, `ProblemsTable`) | Every problem with severity, ID, object and message; Enter or double-click jumps to the field |
| Inspector | `workspace_panels.InspectorWidget` | The focused field: label, value, range, help |
| Time cursor | `time_cursor.TimeCursor`, `ResultsWidget.cursor_actions` | One time shared by the plots, the timeline, the dashboard and the output |
| Command | `actions.ActionRegistry.add(id, text, handler, category=, area=, shortcut=, tip=)` | Every command of the window: its palette entry, header and top-bar buttons, tooltip ("Save (Ctrl+S)") and shortcut row come from it |
| Area | `shell.Shell.register(id, icon, label, content, order)`, `AreaPage.add_command(action)` | A top-level area of the navigation rail, hosting a screen, with its commands in its header |
| Value sheet | `value_sheet.ValueSheet(title, rows=[(name, value, unit)], note=, empty=)`; `set_rows(rows, tips=)` gives a row a tooltip (its source) | Several values of one thing, to be read: one row each, the number right-aligned in tabular figures beside its unit, a title and a note (frame, source). Never a sentence of numbers. The core gives such values as rows of (label, value, unit), the unit in the code's spelling; `units.display_rows` shows each unit as the window does ("kg*m^2" as "kg·m²") |
| Value table | `value_sheet.ValueTable(title, headers, rows, numeric=)` | A matrix (an inertia tensor) or a few rows with several columns (principal axes); a long or sortable list is a `DataTable` |
| Note list | `value_sheet.NoteList(kind, notes, empty=, fold_after=4)` | Notes (`"note"`, info icon, secondary text), warnings (`"warning"`, caution triangle) or findings (`"finding"`): one row each, the icon then the wrapped text; past `fold_after`, "Show n more". `text()` gives the lines behind a mark for copying. Never a block of dash-led lines |
| Elided label | `app_shell.ElidedLabel` | One line that ends in "..." rather than widening the window; the whole text is its tooltip |
| SVG plot | `svg_plot.SvgPlotView`: `set_image(svg, image)`, `load(svg)`, `target_rect()`, `size_settled`; `svg_plot.render_image` in a worker | A plot made as SVG (the thermal plots): drawn at its own aspect ratio, made again at the view's size once a resize ends |
| Event table | `EventTimelineWidget.table`, a `DataTable` over `event_timeline_widget._EventRows` | Events, sortable; Ctrl+C copies the selection as TSV |
| Own window | `breakout.Breakouts`: `register(id, widget, title)`, `button(id)` for the view's toolbar, `detach`, `attach`, `toggle`, `attach_all`; `breakout.BreakoutPlaceholder` | A bigger view in a window of its own and back (3D View, Thermal, Budgets, the 3D View's map): the same widget, so nothing is built twice; its place shows the placeholder with Bring Back; Ctrl+Shift+D, View > Own Windows and the palette |
| Ground map | `ground_map_widget.GroundMapWidget`: `set_scene`, `extend`, `set_frame`, `set_live`; `ground_map_widget.MapRenderer` and `render_map` in a worker; the look in `theme/ground_map_style.py` | Ground tracks, stations and visibility circles on a flat Earth (Results › 3D View's Map), painted by a worker into a `QImage`; the GUI thread draws only that image and the markers; an `EmptyState` without a run |

## Patterns

### Messages

A message says what is wrong and what to do, in the user's terms.

**Field names.** In the GUI a message names a field by its form label,
after its section: "my-sat: Station keeping: Reboost thrust [N] must be
> 0".

- **How:** `gui/field_text.py` replaces the codes when the message is
  shown.
- **Unchanged:** the message itself, the command line and the Log keep
  the scenario file's names (`station_keeping.thrust_n`), which is where
  a user fixes them by hand.
- **Orbit messages** start "Orbit (Classical elements): ...".
- **A section is named once** in a message.

**Units.** A label carries its unit in brackets ("Dry mass [kg]"); a
dimensionless value has "[-]". The window shows every unit through
`gui/units.py`: a field's suffix ("97.59°"), a table heading
(`units.label`: "Off-nadir [°]"), a value beside its unit
(`units.shown`: "W*h" as "Wh"). Text written in the GUI uses the
display form ("0° = equatorial", "kg·m²"), never the code's ASCII
spelling ("deg", "kg*m^2", "W/m^2"), which field names, JSON keys, the
command line, messages and files keep (UI audit B4, UI-35).

**Labels, not identifiers.** A form names a code by its professional
term (`gui/field_text.py`): a device kind ("Star tracker" for
`star_tracker`), a guidance mode ("Sun pointing" for `sunSafePoint`, as
the Overview names it), a body ("Mars barycentre" for
`mars barycenter`), a configuration parameter ("Residual propellant
fraction" for `propellant_budget.residual_fraction`). The code stays the
item's data, so the file is written as before, and an engineer finds it
on hover or as a muted second line. The user's own names (st-1) stay as
they are (UI audit B4, UI-08, UI-19).

**Dashes.** A dash in the window's text and in the manual is an en dash
with spaces (" – "), never "--"; a figure the run does not give is "–"
(UI audit B4, UI-34). Command-line flags keep their hyphens.

**One line first.**

- A toast shows the message's first line whole, on one line when it fits
  its 360 px.
- Long paths wrap inside its 360 px (a zero-width space after each `/`
  or `\`, in the displayed text only).
- A multi-line error or warning adds "(more in the Log)", and the Log
  has all of it.

**Confirmations name the object and the consequence** ("Replace the
earlier export?"). They are the only message boxes the app uses.

### Feedback: which one

| Situation | Use | Never |
|---|---|---|
| A field's value is wrong | Field error + the form's banner + a Problems row | A message box |
| A value from a file is outside a field's range | The field shows the nearest value, is marked as a warning, and Problems says which value the scenario keeps | Clamping silently |
| A routine action finished (saved, exported) | Success toast | A message box |
| An action failed (a file cannot be read) | Error toast; full text in the Log | A message box |
| A dialog's input cannot be used | Dialog error above its buttons; the dialog stays open | Closing the dialog |
| A run failed | The run chip says so; the Log opens at the error | |
| Results no longer match the scenario | Stale results banner with Re-run | Silent stale plots |
| Something cannot be undone | A confirmation that names the object and the consequence | Proceeding without asking |

**Toast durations** (`feedback._REPORT_TOAST_MS`):

| Kind | Duration |
|---|---|
| error | 6 s |
| warning | 6 s |
| info | 4.5 s |
| success | 3 s |

**Status bar:** `report` also writes the message there.

**Where a toast sits (UI audit UI-54):** at the bottom right of the
work area (`feedback.toast_area`: a main window's central widget), so
never over the top bar, a panel (it sits beside the Inspector and above
Problems) or the status bar. It covers no control: the stack moves up,
4 px at a time, until no button, field, drop-down list, tab bar or link
is under it (with 4 px to spare); with no such place it stays at the
bottom. It looks again when the window or the work area changes size and,
while it shows, every 150 ms (a page laid out or scrolled after its
toast), about a millisecond each time. A click on a toast reaches what is
under it (`WA_TransparentForMouseEvents`): it has nothing to click.

### Keyboard

Every command is in the action registry, and every command with a
shortcut shows it in its tooltip. Keyboard Shortcuts (Ctrl+/, Settings >
Keyboard) lists them all. The command palette (Ctrl+K, the top bar's
search) finds, by name or an older name ("events" finds the Timeline):

- the registry's commands;
- the areas and the pages of Run and Results;
- the Scenario tree's pages, its spacecraft and ground stations;
- the panels (Inspector, Problems) and the Settings sections;
- the templates;
- the plotted series.

A command that cannot run now is disabled in every place at once: the
menu, the palette, the header or top-bar button and its shortcut. Its
tooltip and its palette entry say why (`ActionRegistry.set_available`):
Run with no scenario, with an error in the scenario or while a run goes;
Clear Time Cursor while no cursor is set (UI audit B2).

Commands with a **standard key** take the platform's own key for it
(Qt's `QKeySequence.StandardKey`), so their keys differ between systems.
The table gives them as Qt binds them without a desktop theme (the CI's
offscreen platform). Qt's documentation gives Ctrl+Shift+Z for Redo on
GNOME and KDE. A command is named by its palette category and its
label, which is also its menu's name and item in the menu bar (the
Time Cursor commands are under Go > Time Cursor).

| Command | Keys | Standard key |
|---|---|---|
| File > New Scenario | Ctrl+N | New |
| File > Open... | Ctrl+O | Open |
| File > Save | Ctrl+S | Save |
| File > Save As... | Ctrl+Shift+S | SaveAs |
| File > Quit | none | Quit |
| Edit > Undo | Ctrl+Z | Undo |
| Edit > Redo | Ctrl+Y | Redo |
| Edit > Settings... | Ctrl+, | - |
| Run > Run | Ctrl+R | - |
| Run > Cancel Run | Esc | - |
| Run > Clear Time Cursor | Alt+Backspace | - |
| View > Inspector | Ctrl+I | - |
| View > Problems | Ctrl+J | - |
| Own Windows > Open in Own Window | Ctrl+Shift+D | - |
| Time Cursor > Next Sample | Alt+Right | - |
| Time Cursor > Previous Sample | Alt+Left | - |
| Time Cursor > Ten Samples On | Alt+Shift+Right | - |
| Time Cursor > Ten Samples Back | Alt+Shift+Left | - |
| Time Cursor > Next Event | Alt+PgDown | - |
| Time Cursor > Previous Event | Alt+PgUp | - |
| Time Cursor > Start of the Run | Alt+Home | - |
| Time Cursor > End of the Run | Alt+End | - |
| Help > User Manual | F1 | - |
| Help > Keyboard Shortcuts | Ctrl+/ | - |
| Help > Command Palette... | Ctrl+K | - |
| Go > Go to Home | Ctrl+1 | - |
| Go > Go to Scenario | Ctrl+2 | - |
| Go > Go to Run | Ctrl+3 | - |
| Go > Go to Results | Ctrl+4 | - |
| Go > Go to Budgets | Ctrl+5 | - |
| Go > Go to Timeline | Ctrl+6 | - |
| Go > Go to Reports | Ctrl+7 | - |
| Budgets > Add Equipment Item | Ctrl+Shift+N | - |
| Budgets > Remove Equipment Item | Ctrl+Del | - |
| Budgets > Copy as CSV | Ctrl+Shift+C | - |

Open in Own Window (in View > Own Windows) moves the view shown (Results ›
3D View, Run › Thermal, Budgets) into a window of its own; in that window, or on its
placeholder, it reads Bring Back. A view's window carries the global
commands and those of its area, so their shortcuts work there too.

The Time Cursor commands work while Results has the focus. Remove
Equipment Item and Copy as CSV act on the Budgets page shown; from
another area they show the Budgets area first. The table is
checked against the registry by `tests/gui/test_design_rules.py`; a
standard key is checked against the running platform's binding.

**Shortcuts inside a view:**

| Where | Keys | Does |
|---|---|---|
| Timeline | Ctrl+F | Search the events |
| Timeline | Esc | Clear the search |
| Timeline's event table | Ctrl+C | Copy the selected rows as TSV |
| Mission Sequence list | Alt+Up, Alt+Down | Move the step |
| Mission Sequence list | Delete | Remove the step |
| Scenario tree | Up, Down | Pass through a group or a page's sections in the key's direction |
| Home, template cards | Arrows, Home, End | Move between the cards |
| Home, template cards | Enter | Open the card's template |
| Home, recent scenarios | Delete | Take the scenario off the list |
| Scenario JSON page | Ctrl+Space | Suggest what can be typed at the cursor |
| Scenario JSON page | Ctrl+Shift+Space | Describe the key at the cursor |
| Scenario JSON page | F8, Shift+F8 | Go to the next, the previous problem |
| Scenario JSON page | F2 | Rename the spacecraft, ground station or part named at the cursor, everywhere |
| Scenario JSON page | F12 | Go to where the name at the cursor is defined |
| Scenario JSON page | Ctrl+. | Quick fixes for the key or value at the cursor |
| Scenario JSON page | Shift+Alt+F | Format the text |

**Tab order.** A Tab walk of Templates, the Scenario page, a spacecraft's
page, Results, Events, Log, End of Life and Budget at 1280 x 720
(iteration 7b) found:

- every visible field, button and list is in the chain, in reading order;
- since M2a the toolbars are gone; the rail, the area headers and the top
  bar are buttons in the chain, and every command has a shortcut or a
  palette entry. The keyboard-only walk of the shell is M2b's.

### Themes

Settings > Appearance offers System, Light and Dark:

- **System** follows the desktop (`QStyleHints.colorScheme`).
- **Storage:** `~/.spacemissionstudio/settings.ini`, key
  `appearance/theme`.
- **When it applies:** at once. `theme.apply_theme(app, mode)` sets the
  palette and the one application style sheet and emits
  `theme.signals.changed`; plots, diagrams and item colours connect to it
  and redraw (`theme.on_change`, `theme/items.py`). With System, a change
  of the desktop's scheme applies while the app runs.
- **Time:** about 0.36 s with every template opened in turn, then
  template 23 (1.3.1; 0.53 s before it, 6.1 s before the overhaul on the
  same machine: SRelD K-19); Qt re-polishes every widget, most of them
  hidden. The brief's 100 ms is not met (see [Known gaps](#known-gaps);
  `docs/DECISIONS.md`).

### Long operations

Every slow job runs in a `QThread` worker, so the window never waits
on it:

- **Simulations:** a job in the status bar with progress and Cancel (Esc, in its tooltip).
- **The AD10 budget's sweeps:** their button turns into Cancel while
  they run.
- **Lifetime estimates and reference-data downloads:** run in workers
  too.

A widget that owns a worker has `wait_for_worker()`:

- `MainWindow` calls it on close;
- tests call it before a widget is destroyed, because destroying a
  running `QThread` aborts the process.

### Empty states

An empty view, list or panel shows `widgets.EmptyState`, the GUI's one
empty state (UI audit B3): a title, a line of text and the action that
fills it (Add, Run, Check, Browse...). A list shows it in the list's
place (`widgets.EmptyStack`), never a blank box, and a short list is as
tall as its rows. Its Edit and Remove stay off until a row is selected.
A panel, a short list or the room beside a table takes the compact form
(Run › Thermal › Heat flows before a node is picked), so the table keeps
the height. Reasons go in a short list under the text
(`EmptyState.add_detail`, the Timeline's run without events). No view
draws its own centred line of text any more, and the style sheet has no
"empty" label role. An empty view says why it is empty and what fills
it, for example:

- **Results Dashboard:** "No live telemetry yet. Run a scenario with
  Comms pointing (e.g. template 19) to see it here."
- **Output:** why it is empty after a run without Report steps.
- **Log:** "Nothing logged yet in this session."
- **Run › Plan:** what a plan is; with no operations section, Open
  Template 35 (the template that has one), else Plan.
- **Run › Design Checks, before the first check:** "Not checked yet",
  with Check; after a check without findings, "No design finding." once.
- **Problems, with no scenario open:** "No scenario is open", never "the
  scenario is valid".
- **Explain, while the scenario does not validate:** "The scenario has
  a problem (see Problems): fix it to see its summary here."
- **A work area with no scenario open** (Scenario, Run, Results,
  Timeline, Reports; the window starts so): "No scenario is open", what
  the area works on, and New Scenario (the primary action), Open... and
  Go to Home (`gui.app_shell.NoScenarioState`, under the area's title in
  place of its commands and content: `AreaPage.show_empty`).

The other empty states' buttons are secondary: the top bar's Run is the
view's one accent (UI audit B2).

### Views in their own windows

A bigger view can open in a window of its own (`gui/breakout.py`,
decision "Breakout windows" in `docs/DECISIONS.md`):

- **The same widget moves.** Its tab or slot shows a
  `BreakoutPlaceholder`: "<view> is in its own window", **Bring Back**
  (secondary: the top bar's Run is the accent) and **Show Window**. The tab keeps its index and its text.
- **Every view opens docked** at start ("Calm by default"); no window
  opens by itself. Closing the window brings the view back; so do Bring
  Back, the view's own button and Ctrl+Shift+D.
- **The window** has the app icon, the title "<view> - <scenario> -
  SpaceMissionStudio", the `bg.canvas` background (`QWidget[breakout="true"]`
  in `theme/qss.py`) and the theme of the app. Its geometry is kept in
  `layout.ini` and used again only on a screen that still exists.
- **Showing a view in its window** (a command, the palette, a live run)
  brings that window to the front; the main window keeps its area.

## Rules for new code

| Rule | Checked by |
|---|---|
| No colour, CSS size, font family or style sheet in `gui/` outside `gui/theme/`; take tokens, fonts and roles from the theme (the exceptions are listed in the test, each with its reason) | `tests/gui/test_design_rules.py::test_no_hard_coded_style_outside_the_theme` |
| A new token is derived in `theme/tokens.py` for both themes, and is in the table above | `tests/gui/test_theme.py::test_both_themes_have_the_same_tokens_and_the_selected_tint`, `tests/gui/test_design_rules.py` |
| A colour pair a widget draws is in `tokens.CONTRAST_PAIRS` | `tests/gui/test_dark_theme.py` |
| Whatever paints a colour itself redraws on `theme.signals.changed` | `tests/gui/test_dark_theme.py::test_a_live_switch_restyles_every_open_view` |
| The style sheet parses without a Qt warning | `tests/gui/test_theme.py::test_the_style_sheet_parses_without_qt_warnings` |
| A new spacecraft number has a labelled widget in the spacecraft form's `field_widget` map | `tests/gui/test_field_text.py::test_every_numeric_spacecraft_field_has_a_title` |
| A validation message starts with what it is about (`<spacecraft>: <field path> ...`, `sim_settings.<field> ...`) so the GUI can locate and label it | `tests/gui/test_field_text.py::test_no_template_message_shows_a_field_code` |
| A form grows no wider than `CONTENT_MAX_WIDTH_PX` | `tests/gui/test_wide_screen.py` |
| Validation is never a message box; a message box only confirms | `tests/gui/test_messages.py::test_no_information_warning_or_critical_message_box_is_left` |
| A command with a shortcut is in the table above | `tests/gui/test_design_rules.py::test_the_shortcut_table_matches_the_registry` |
| A widget with a worker thread waits for it before it is destroyed | `tests/gui/test_lifetime_widget.py`, `test_budget_widget.py`, `test_data_panel_widget.py` |
| Help text is short and plain | `tests/gui/test_label_text.py` |
| No "--" as a dash and no unit in its ASCII spelling in the GUI's strings or the manual; a suffix from a unit goes through `units.suffix` | `tests/test_gui_strings.py` |
| A device kind, guidance mode, body and configuration parameter has a label in `gui/field_text.py` | `tests/gui/test_labels.py` |
| Every input box has a visible border in both themes | `tests/gui/test_input_borders.py` |
| A command on a page or in an area header looks like a button, a check box or a segment, never plain text | `tests/gui/test_settings_page.py` |

## Checking a change

Each view is checked against the standard's list:

- keyboard only;
- light and dark;
- long names and 10-year runs;
- empty and error states;
- 1280 x 720 and 2560 x 1440;
- the tests;
- no new colour, size or font literal.

The screenshots come from an offscreen `QApplication`:

```bash
QT_QPA_PLATFORM=offscreen python scripts/capture_screenshots.py out/light --theme light --size 1280x720
QT_QPA_PLATFORM=offscreen python scripts/capture_screenshots.py out/dark --theme dark --size 2560x1440
```

`scripts/capture_ux_audit.py` captures the template 22 walk-through the
audit uses.

## Known gaps

Where the app does not meet `docs/ui/UI_OVERHAUL.md` after the overhaul
(measured in `docs/ui/BEFORE_AFTER.md`, the reasons in `docs/DECISIONS.md`):

- **Live theme switch time:** about 0.4 s, not the brief's 100 ms: the
  application style sheet is applied to every widget (6.1 s before the
  overhaul; SRelD K-19).
- **Stalls over 50 ms** remain when a template is opened (72-134 ms), on
  the first visit to a spacecraft page (157-168 ms) and in the spacecraft
  editor dialog (381 ms), and at the end of a run that ends in the first
  seconds after start-up (up to 0.3 s; 27-52 ms otherwise). SRelD K-23.
- **Tables:** Output, Monte Carlo, Budget, Compare, the Timeline,
  Reports › Exports and Settings › Keyboard are `DataTable`s. The
  reference data list, the readouts, the scenario overview's table, the
  SIL comparison, the facet and data-handling editors and the series
  dialog are still `QTableWidget`s.
- **Spacing:** the 4 px grid is in the style sheet and the theme's
  `SPACE`; some layouts built in code still set their own margins.
