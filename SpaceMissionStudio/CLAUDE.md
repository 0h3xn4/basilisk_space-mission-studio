# CLAUDE.md: rules for work on SpaceMissionStudio

Read `CONTRIBUTING.md` and `docs/developer/README.md` first. The GUI was
overhauled milestone by milestone for 1.3.0 (`docs/ui/UI_OVERHAUL.md`, the
brief; `docs/ui/UI_OVERHAUL_PLAN.md`, the plan). Every session that
touches the GUI follows the design rules below; where they and older
documents disagree, these win.

## Hard rules

- **Engine and format changes come with their records** (replaces the
  1.3.0 overhaul's "UI only" rule, owner 2026-11-17): a change to
  computation, the engine, the scenario or project file formats, CLI
  commands and flags, or a generated output file is allowed only with
  - a schema version step and a migration when a file format changes, so
    every older file still opens;
  - the golden files of the existing templates byte-identical, unless the
    owner decides otherwise and `docs/changes.md` explains each change;
  - a decisions entry (`docs/DECISIONS.md` or the feature's decisions
    file).

  Every existing test passes and none is weakened. A GUI test may change
  only how it reaches a widget, each change logged in
  `docs/ui/TEST_CHANGES.md`.
- **Do not modify the Basilisk framework** (anything outside
  `SpaceMissionStudio/`): no edits, patches or monkey-patching.
- **PySide6 only:** no web frontend, no Electron/Tauri, no third-party Qt
  theme package.
- **Offline:** every font, icon and script is bundled; nothing is fetched
  at run time, no CDN.
- **Dependencies:** prefer none. Anything new is permissively licensed,
  pinned, in the `gui` extra only, and recorded in `docs/DECISIONS.md` and
  `docs/THIRD_PARTY_ASSETS.md`.
- **Decisions:** where the brief is silent, take the simplest option and
  record it in `docs/DECISIONS.md` with a one-line rationale; ask where a
  choice changes a workflow users rely on.
- **Never claim compliance without evidence;** a target that is not met
  is written down with the measured value.

## Design rules

**Character:** calm, dense, precise. Quiet neutral surfaces, crisp type,
very few lines, colour only where it means something.

1. **Colour means something.** The interface is neutral. The accent is
   for the primary action, selection and focus only. Status colours
   (critical, serious, caution, normal, standby, off) are for status
   only, always with an icon or text, never colour alone.
2. **Surfaces, not lines.** Separate areas by background (`bg.canvas`,
   `bg.surface`, `bg.raised`) and spacing. Borders are 1 px and subtle,
   for inputs, table headers, panels and splitters. No boxes in boxes, no
   group-box frames.
3. **Density with order:** a strict 4 px grid (4, 8, 12, 16, 24, 32);
   controls 32 px (28 px compact); table rows 26 px.
4. **Precision:** every number shows its unit (field suffix or column
   header), right-aligned with tabular figures, consistent significant
   figures per quantity; timestamps ISO 8601 UTC with `Z`; values, IDs
   and table selections copyable.
   **Never a sentence of numbers:** several values of one thing are a
   `value_sheet.ValueSheet` (name, value, unit per row) or a
   `ValueTable` (a matrix, a few rows), with a title saying what they
   are; a long or sortable list is a `DataTable`. Raw text dumps
   ("a 6928 km, e 0.0, i 97.59 deg, ...") read as noise (the owner,
   2026-11-12). Notes, warnings and findings are a `NoteList` (one row
   each behind its icon, folded after four), never dash-led lines.
5. **Keyboard first:** Ctrl+K command palette, shortcuts for frequent
   actions shown in tooltips and menus, visible focus everywhere.
6. **Never freeze:** nothing over about 50 ms on the GUI thread;
   simulations, generation, imports, file I/O and checks in workers with
   progress and cancel; heavy tabs and every `QWebEngineView` created
   lazily; typing-triggered recomputation debounced (about 250 ms).

## How the code applies them

- **One source of truth: `spacemissionstudio/gui/theme/`.** Tokens
  (`tokens.py`), type and spacing (`typography.py`), chart palette
  (`palettes.py`), fonts (`fonts.py`), icons (`icons.py`), the generated
  style sheet (`qss.py`), the Plotly template (`plotly_template.py`),
  `apply_theme` and the `changed` signal (`apply.py`). `docs/DESIGN.md`
  describes it.
- **No colour, font family, CSS size or style sheet in GUI code outside
  `gui/theme/`** (`tests/gui/test_design_rules.py` enforces it). Read
  `theme.TOKENS["text.secondary"]`; give a widget its look with
  `theme.set_role(widget, role=..., tone=..., badge=...)`; use
  `theme.ui_font(size, weight)`, `theme.mono_font()`,
  `theme.numeric_font()`; icons with `theme.icon(name, ink)` (Lucide,
  bundled).
- **Live theme switch:** the whole UI restyles at once. Anything that
  paints a colour itself (plots, diagrams, item colours, rich text)
  redraws on `theme.on_change(...)`; item colours go through
  `theme.items.tint` / `retint`.
- **Contrast:** every text/background pair the GUI draws is in
  `tokens.CONTRAST_PAIRS` and passes WCAG 2.2 AA in both themes
  (`tests/gui/test_dark_theme.py`). A new pair is added there.
- **Type:** Inter for the UI, JetBrains Mono for numbers in tables, IDs,
  code and logs. Sizes 11 caption, 12 small and table, 13 body, 15
  section title, 18 page title, 22 display. Weights 400, 500, 600 only.
- **Shape:** radius 6 px for controls, 8 px for panels, popovers and
  dialogs; 2 px accent focus ring; shadows only on floating elements.
- **Icons:** Lucide only, 16 px in the UI, 20 px in the navigation rail.
- **Motion:** 120-180 ms ease-out for hover, panel open/close and toasts;
  never animate data values or plots; respect "reduce motion".
- **Plots:** the Plotly template from the tokens; axis titles with units;
  the 8-colour categorical palette in fixed order, never cycled; a legend
  for more than one series.
- **Shell (M2 onward):** left navigation rail, top bar with Ctrl+K,
  central tabs and splitters, right inspector, status bar with jobs,
  collapsible Problems panel. Modal dialogs only for destructive
  confirmations and multi-step wizards; success feedback is a toast;
  every list and table has an empty state with its primary action.
- **Tables:** `QTableView` + `QAbstractTableModel`, sortable and
  filterable, sticky header, numeric columns right-aligned with units in
  the header, copy as TSV, column-visibility menu, row hover, no zebra.

## Checks before a commit

- `python -m ruff check spacemissionstudio tests scripts compliance/tools`
- `QT_QPA_PLATFORM=offscreen python -m pytest tests -q -n auto -p no:cacheprovider`
- the compliance generators leave `compliance/docs` unchanged
  (`compliance/tools/build_icd_schema.py`, `build_sdd_components.py`,
  `build_test_specs.py`) and `compliance/tools/check_drds.py` passes;
- `python scripts/sync_help.py` after a change to `USER_MANUAL.md`;
- the screenshot harness (`scripts/capture_ui_screens.py`) at the end of a
  milestone, with the differences noted;
- CHANGELOG "Unreleased" and `docs/DECISIONS.md` updated.

## Backlog and release procedure

An unattended run (a scheduled task) follows this procedure. Paths are
relative to `SpaceMissionStudio/` unless they start with `.github/`.

- **The backlog** is the items under `## Next release` in `BACKLOG.md`.
- **Stop at once**, change nothing and report it in one short message,
  in each of these cases. Check them before any other work:
  - `## Next release` has no items (an empty backlog is a finished run,
    not a failure);
  - the GitHub tools (`mcp__github__*`) are missing, so the release
    cannot be published. They are deferred: load them with ToolSearch
    (`select:mcp__github__actions_run_trigger,mcp__github__actions_list`)
    before you decide that they are missing;
  - the tests cannot run in this container: Basilisk is missing and
    `pip install -c packaging/constraints.txt bsk==2.12.0` fails, or the
    Qt libraries for the GUI tests are missing.
- **Branch.** Find the default branch with
  `git symbolic-ref refs/remotes/origin/HEAD` (today it is `develop`).
  Never assume it is called `main`. Work on that branch and push to it.
  A backlog run does not open pull requests.
- **One item at a time:**
  1. Fix the item.
  2. Add a test that fails without the fix.
  3. Run the checks below.
  4. Commit with `git commit -s`. Write the message in short, plain
     sentences, about 80 % of the way to ASD-STE100 Simplified Technical
     English. Name every choice you made without asking.
  5. Push. First run `git pull --rebase origin <default branch>`: other
     work lands on the same branch. If the rebase conflicts, abort it,
     drop your commit and move the item to `## Needs human`.
  6. Move the item to `## Done` with the short commit hash.
- **The checks** (from `SpaceMissionStudio/`), all must pass before a push:
  - `python -m ruff check spacemissionstudio tests scripts compliance/tools`
  - `QT_QPA_PLATFORM=offscreen python -m pytest tests -q -n auto`
  - `pre-commit run --files <changed files>` (from the repository root;
    `pip install pre-commit` first, it is not in the `dev` extra)
  - `python compliance/tools/check_drds.py`, the other generators in
    "Checks before a commit", then `git diff --exit-code compliance/docs`
  The hard rules above still apply. The golden files stay byte-identical.
- **Unclear or blocked items** move to `## Needs human` with a short
  reason. Examples: the fix breaks a hard rule, changes a golden file,
  or needs a choice that changes a workflow users rely on. Skip the item
  and continue.
- **Never ask questions** during a backlog run. Make reasonable choices
  and note them in the commit message.
- **A denied tool call** is not retried in another form. Report it and
  stop.
- **Waiting for CI** uses a background command or the Monitor tool, never
  a foreground `sleep`. Wait at most two hours; then stop and report.
  CI is red when a check of the "SpaceMissionStudio" workflow failed.
  If CI turns red after one of your pushes and the cause is in your
  change, fix it once; otherwise stop, publish nothing and report it.
- **Semver:** a breaking change is a major step, a new feature a minor
  step, anything else a patch.
- **No release without done items.** If every item of this run went to
  `## Needs human`, push the moves, publish nothing and report it.
- **No release of other work.** `CHANGELOG.md` `## Unreleased` can hold
  entries of work that a person or another session merged and that is
  not finished. If it holds any entry that did not come from an item of
  this run, do not release: push the item commits, publish nothing and
  report that the release waits for that work. Do the same when CI was
  already red on the default branch before your first push.
- **Release** (only when `## Next release` is empty, this run moved at
  least one item to `## Done`, and the two rules above allow it), by
  `docs/developer/releasing.md` sections 2 to 4 and 6:
  1. The version: take the newest tag with
     `git ls-remote --tags --refs origin 'spacemissionstudio-v*' | sed 's|.*/spacemissionstudio-v||' | sort -V | tail -1`
     and raise it by the semver rule above. It must be new. Sort by
     version (`sort -V`): a plain sort puts 2.9.0 after 2.11.0. Every
     SpaceMissionStudio tag is `spacemissionstudio-vX.Y.Z`, all lower
     case: the release workflow starts only on that pattern, git tags
     are case sensitive, and `vX.Y.Z` belongs to Basilisk upstream.
  2. Set it in `pyproject.toml`, `spacemissionstudio/__init__.py` and
     `packaging/windows/spacemissionstudio.iss`.
  3. Move the Unreleased entries in `CHANGELOG.md` under
     `## X.Y.Z (YYYY-MM-DD)`, dated today in UTC, with a one-paragraph
     summary first (the release notes use it). List every item.
  4. Update the release records: HISTORY, SRelD, and the others
     `releasing.md` sections 3 and 4 name.
  5. Run the checks and
     `python packaging/release_check.py --commit "$(git rev-parse HEAD)" --tags "$(git ls-remote --tags origin)"`.
     It must pass. Commit (`-s`), pull with rebase, push.
  6. Wait until CI is green on that commit (see "Waiting for CI").
  7. **Tag and publish in one step:** start the workflow
     `spacemissionstudio-tag-release.yml` with the GitHub tool
     `mcp__github__actions_run_trigger` (`run_workflow`, ref the default
     branch, inputs `version: X.Y.Z`, `ref: <default branch>`,
     `publish: true`). It checks the head commit again (CI passed,
     pip-audit with today's advisories, the CHANGELOG), tags exactly that
     commit `spacemissionstudio-vX.Y.Z` and starts the release workflow,
     which builds, installs, checks, attaches the eleven files and
     publishes. Do not tag by hand and do not use the `gh` CLI. If
     another commit landed on the branch after yours, the check runs on
     that head; wait for its CI first.
  8. Wait for both workflows (at most two hours). If one fails, stop and
     report it: a failed check tags nothing, a failed build leaves at
     most a draft.
  9. Check that `git ls-remote --tags origin` shows the tag and that the
     published release has its eleven files. Download them and run
     `sha256sum -c SHA256SUMS-linux` and `sha256sum -c SHA256SUMS-windows`.
  10. Record the publication as `releasing.md` section 6 says (SRelD
      status and baseline, `compliance/human_actions.md` H05, then
      `compliance/tools/build_matrix.py`). Commit, pull with rebase, push.
- **Progress** goes to `PROGRESS.md`, next to this file. Git ignores it.
