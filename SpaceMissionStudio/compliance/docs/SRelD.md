# SpaceMissionStudio: Software Release Document (SRelD)

DRD: ECSS-E-ST-40C Annex G
Document: SMS-SRelD, issue 56, 2026-11-24. Remediation R14.

**Status:** release **2.15.0**, published 2026-11-24 (00:38 UTC).
2.15.0 is a minor release: it adds features and
a scenario schema step (version 7). It holds Monte Carlo phase B
(`docs/developer/monte-carlo-plan.md`; #313, #314 and #316, decisions
MC-20 to MC-35) and the 2.14.2 publication record (#317):
- **The batch seed** (#313, plan item B1, K-24). The optional
  `monte_carlo.seed` reseeds each run's NumPy and Python generators from
  the batch seed and the run index, after Basilisk's own seeding and
  before the draws. Another seed gives an independent batch; the same
  seed gives the same batch, with one process or many. Without a seed,
  each run draws what it drew before.
- **Thermal node limits** (#313, B4). A thermal Monte Carlo counts, per
  node and range (operating, survival), the runs that leave the range at
  any time step, and with its optional `confidence` gives the one-sided
  Clopper-Pearson upper bound. Results › Monte Carlo › Node limits and
  `thermal --monte-carlo` show them.
- **Small fixes of phase A** (#313, B8): "Processes" for "Thread count",
  the Failed tile as a count, a thermal batch's failed runs in the Runs
  table, the starting attitude in degrees in the form. Also the Home
  page's template details: Customize and open... goes below Open
  template when the two do not fit (`FlowLayout`).
- **Outcome statistics** (#314, B3). Per outcome: N, the minimum, the
  percentiles (`numpy.percentile`, `monte_carlo.percentile_method`
  `linear`; shown: 1, 5, 50, 95 and 99 %, provisional, MC-27) and the
  maximum, with the empirical distribution as a step plot (Results ›
  Monte Carlo › Statistics).
- **Sensitivity** (#314, B2). Spearman's rank correlation (or Pearson's,
  `monte_carlo.sensitivity_measure`) of each drawn value with each
  outcome, with N per pair, strongest first, and a scatter plot (Results
  › Monte Carlo › Sensitivity). The plot pages are written in a worker,
  so the GUI thread's part stays under 50 ms for 100 000 runs.
- **Trust checks** (#314, B6). The finding `monte_carlo.nominal_outside`
  in the Problems panel when a dispersion of the dry mass, the drag or
  the SRP coefficient no longer fits its spacecraft; a warning when a
  batch is shown next to another scenario (both SHA-256).
- **The batch report** (#316, B5). Export report... and `monte-carlo
  --report FILE` write one report, JSON (`kind: monte_carlo_report`,
  `format` 1) or Markdown, with the numbers of the view.
- **The command line** (#316, B7). `monte-carlo --summarize DIR` (an
  earlier batch, running nothing), `--csv FILE`, `--runs N` and
  `--processes N` (one batch only; recorded in
  `archive.provenance.json`'s `monte_carlo_settings`).
- **Template 37** (#316, B9, provisional, MC-34): "Monte Carlo:
  requirements, statistics and sensitivity", 30 runs with the batch seed
  37 and two requirements; about a minute in one process. Template 25 is
  unchanged.

The scenario file moves to schema version 7 (K-49). The step only sets
the version. `git diff 452e164` (the 2.14.2 tag) shows the step in
`schema/`, `tests/data/scenario_hashes.json` recorded again (72 hashes
changed, 2 added for template 37), template 37 and its golden file new,
and the 36 earlier templates changed only on their `schema_version`
line: with that line set back to 6, each is byte for byte the file at
`452e164`. The 36 earlier golden files are byte-identical. No computed
result of a run changed. The bundled CelesTrak space weather is
2.13.0's (observations to 2026-11-18; K-13, not refreshed: CelesTrak
reset the connection). By the owner's decision of 2026-11-19, the
release pull request may be merged with CI's "Windows (MAX Python)" job
red, but only for the Basilisk framework test `LambertInputValidation`
(K-45). Basilisk is unchanged. Outside `SpaceMissionStudio/` only the
front-page `README.md`'s SpaceMissionStudio part changed (section 4).

How 2.15.0 was tagged and published:
- The release pull request #318 was merged at 20:40 UTC on 2026-11-23
  as `5ebbd3b`, after #317 (`f4ab371`). On the head of #318
  (`3fd215f`), only CI's "Windows (MAX Python)" job was red. It failed
  only the framework test of K-45, 1 test of 842.
- CI ("SpaceMissionStudio") on `develop`'s head `5ebbd3b`, the merge of
  #318 ([run 45261875723](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/45261875723)), passed at
  the first attempt. No job was run again.
- The tag workflow ([run 45294312275](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/45294312275)) ran from
  00:05:49 to 00:07:06 UTC on 2026-11-24. It ran the release check on
  `5ebbd3b` and passed.
- The tag workflow (github-actions) tagged `spacemissionstudio-v2.15.0`
  (annotated, not signed, D-13; tag object `56e0831`) on commit
  `5ebbd3b` (`5ebbd3bda91fa52fe907a1a3747b8ebe1c1eaee0`) at 00:06:56
  UTC.
- The release workflow ([run 45294483106](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/45294483106)) ran from
  00:07:02 to 00:38:47 UTC and passed at the first attempt. Every job
  passed, the Windows tests too. It built, installed, checked and
  attached the eleven files. It counted the eleven files and then
  published the GitHub release "SpaceMissionStudio 2.15.0" at 00:38:45
  UTC, not as a draft and not as a pre-release
  (<https://github.com/0h3xn4/basilisk_space-mission-studio/releases/tag/spacemissionstudio-v2.15.0>).
  The release was never public without its files. Its notes are the
  CHANGELOG's 2.15.0 section.
- GitHub's SHA-256 digests: `.deb` (`spacemissionstudio_2.15.0_amd64.deb`,
  440 912 148 bytes) `4a53c2ec...d1e3`, setup program
  (`spacemissionstudio-2.15.0-setup.exe`, 387 174 918 bytes)
  `3683a4e5...cf40`, wheel (9 102 884 bytes) `52a0b15b...013d`, sdist
  (9 423 227 bytes) `345655c5...c9d9`, the `.deb`'s bill of materials
  (`spacemissionstudio_2.15.0_amd64.cdx.json`, 35 359 bytes)
  `c676bc43...d07a`, the setup program's
  (`spacemissionstudio-2.15.0-setup.cdx.json`, 36 459 bytes)
  `40400646...126c`, `SHA256SUMS-linux` `793224ec...26b5`,
  `SHA256SUMS-windows` `6d7a4265...6118`, and the LGPL sources, the same
  as 2.14.x's: `qt-everywhere-src-6.11.2.tar.xz` (1 019 661 552 bytes)
  `6dcfbca2...6f33`, `pyside-setup-everywhere-src-6.11.2.tar.xz`
  (18 053 248 bytes) `cba47efb...fdf8`, `SHA256SUMS-sources`
  `1301daba...e6f6`.
- Every file's digest equals its checksum in `SHA256SUMS-*`. The
  digests table of the release notes gives the same digests for the
  `.deb` and the setup program. Every small file (the wheel, the sdist,
  both bills of materials and the three `SHA256SUMS-*` files),
  downloaded from the release, gives the same digest. The release notes
  do not name the 3D vendor.
- #319 (a cancelled Monte Carlo batch leaves no process) was merged
  after the tag, as `bb00914`. It is not in 2.15.0. Its CHANGELOG entry
  stays under "Unreleased".

**Previous release:** 2.14.2, published 2026-11-23 (11:13 UTC), tag
`spacemissionstudio-v2.14.2` on `452e164`; its publication is recorded
in issue 54 of this document (#317).
2.14.2 is a patch release. The backlog procedure (`CLAUDE.md`, "Backlog
and release procedure") prepared it: no release pull request. It holds
two fixes and the 2.14.1 publication record (#312):
- **The Budgets area shows quickly** (`29bbdb5`, K-40). The Equipment
  page's word-wrapped note made the area's page report a height for
  width, and Qt's stacked layout then asked every area's page, the
  hidden ones too, at each show: 8 to 11 ms on Linux, 50 to 81 ms on
  the Windows CI runner. `shell.AreaPage` now reports none. The area
  shows in about 1 ms on Linux, and the move test passes on the Windows
  runner with a plain 50 ms limit (CI run 45109373728). K-40 is only
  partly met: on the release workflow's Windows runner, the 3D View's
  move took 64.0 ms and 72.7 ms (section 5.2).
- **A hidden area that becomes wider lays the window out again at
  once** (#315, `452e164`). Qt ignores `updateGeometry()` from a hidden
  widget. When a hidden area's page became wider (Timeline's row of
  filters), the window kept the layout of the old width until another
  change laid it out again. `AreaPage.event()` now passes a hidden
  page's layout request to the area stack. The fault is older than
  K-40: it failed 2 of 4 runs on `7a9a25f`.

How 2.14.2 was tagged and published:
- The unattended backlog run made the release commit `ce6123e` at
  04:53 UTC (issue 53, "prepared").
- CI ("SpaceMissionStudio") on `ce6123e` ([run 45114509231](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/45114509231))
  failed the Linux `test` job:
  `test_thermal_page_audit.py::test_the_sweep_table_fits_the_page_at_1280[inspector]`.
  The backlog run stopped without a fix, and it tagged nothing.
- #315 found the cause and fixed it (the second fix above). It was
  merged at 09:02:53 UTC as `452e164`. On the head of #315, only CI's
  "Windows (MAX Python)" job was red. It failed only the framework test
  of K-45, 1 test of 842.
- CI on `develop`'s head `452e164`, the merge of #315
  ([run 45143562273](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/45143562273)), ran from 09:02:55 to 09:31:20 UTC
  and passed at the first attempt.
- The tag workflow ([run 45147869658](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/45147869658)) ran from 09:31:50
  to 09:33:11 UTC. It ran the release check on `452e164` and passed.
- The tag workflow (github-actions) tagged `spacemissionstudio-v2.14.2`
  (annotated, not signed, D-13; tag object `d916f0c`) on commit
  `452e164` (`452e164e7652de7135fe513d82039bbf311b388f`) at 09:33:01
  UTC. The tagged commit is the merge of #315, not `ce6123e`.
- The release workflow ([run 45148067729](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/45148067729)) needed two
  attempts:
  - Attempt 1 (09:33:07 to 10:23:40 UTC) failed. Its job "tests /
    platforms (windows-latest)" failed
    `tests/gui/test_breakout.py::test_detach_and_attach_take_under_50_ms_on_the_gui_thread`:
    the 3D View's slowest move took 64.0 ms, and 72.7 ms when the test
    timed it again, against the plain 50 ms limit of K-40. The attach
    job was skipped, so nothing was published.
  - The same test passed on the same commit in CI run 45143562273. So
    the failed jobs were run again, once.
  - Attempt 2 (10:26:10 to 11:13:16 UTC) passed. It built, installed,
    checked and attached the eleven files. It counted the eleven files
    and then published the GitHub release "SpaceMissionStudio 2.14.2"
    at 11:13:13 UTC, not as a draft and not as a pre-release
    (<https://github.com/0h3xn4/basilisk_space-mission-studio/releases/tag/spacemissionstudio-v2.14.2>).
    The release was never public without its files. Its notes are the
    CHANGELOG's 2.14.2 section.
- GitHub's SHA-256 digests: `.deb` (`spacemissionstudio_2.14.2_amd64.deb`,
  441 058 000 bytes) `a739a471...2b0a`, setup program
  (`spacemissionstudio-2.14.2-setup.exe`, 387 084 882 bytes)
  `eec0d743...97d4`, wheel (9 060 659 bytes) `cfd39e0a...7ad8`, sdist
  (9 369 416 bytes) `b5352941...f3d5`, the `.deb`'s bill of materials
  (`spacemissionstudio_2.14.2_amd64.cdx.json`, 35 359 bytes)
  `e433b5a8...65b5`, the setup program's
  (`spacemissionstudio-2.14.2-setup.cdx.json`, 36 459 bytes)
  `84423398...0023`, `SHA256SUMS-linux` `ed0494ba...f848`,
  `SHA256SUMS-windows` `867c046e...eb2e`, and the LGPL sources, the same
  as 2.14.0's and 2.14.1's: `qt-everywhere-src-6.11.2.tar.xz`
  (1 019 661 552 bytes) `6dcfbca2...6f33`,
  `pyside-setup-everywhere-src-6.11.2.tar.xz` (18 053 248 bytes)
  `cba47efb...fdf8`, `SHA256SUMS-sources` `1301daba...e6f6`.
- Every file's digest equals its checksum in `SHA256SUMS-*`. The
  digests table of the release notes gives the same digests for the
  `.deb` and the setup program. The wheel, the sdist, both bills of
  materials and the three `SHA256SUMS-*` files, downloaded from the
  release, give the same digests.

Also on `develop` since 2.14.1, with no effect on the software: the
pointing error budget's design (`39da9d7`, no code; `BACKLOG.md`,
"Needs human") and the backlog's moves (`c0f62c7`).

No file format changed: the scenario file is still at schema version 6
(K-47). `schema/`, the templates, the golden files and `packaging/` have
no change since the 2.14.1 tag `caabf11`; in the package only
`gui/shell.py` changed. No computed result changed. The bundled
CelesTrak space weather is 2.13.0's (observations to 2026-11-18; K-13,
not refreshed: CelesTrak reset the connection). Basilisk is unchanged.
Outside `SpaceMissionStudio/` only the front-page `README.md`'s
SpaceMissionStudio part changed (section 4).

Before it: 2.14.1, published 2026-11-23 (02:20 UTC), tag
`spacemissionstudio-v2.14.1` on `caabf11`; its publication is recorded
in issue 52 of this document (#312).
2.14.0 is a minor release: it adds features and
an optional scenario field. It holds Monte Carlo phase A
(`docs/developer/monte-carlo-plan.md`), the plan (#305) and the 2.13.1
publication record (#304):
- **Outcomes per run** (#306, plan item A1). Each successful run keeps
  its Overview figures: run length, orbital period, lowest and highest
  altitude, delta-V, propellant used, mean semi-major axis change,
  lowest link margin, lowest battery charge, passes, contact time,
  eclipses, eclipse time and data downlinked. The Runs table, its CSV
  and the command line show them.
- **Requirements** (#306, A2). The scenario's `monte_carlo.requirements`
  limits one outcome per requirement, with a confidence that the user
  sets (no default) and an optional allowed probability. The batch
  counts the runs that do not meet it (k of N) and gives the one-sided
  Clopper-Pearson upper bound. Results › Monte Carlo › Requirements and
  `monte-carlo` show them; `monte-carlo` exits with status 5 when a
  requirement is not shown met.
- **Draws of crashed runs** (#306, A4). The Runs table lists a crashed
  run with its drawn values and the status "crashed".
- **One case run again** (#307, A3). Run This Case (Results › Monte
  Carlo › Runs), `monte-carlo --case N` and `api.monte_carlo_case` run a
  case again with its draws and seeds. A case is refused when the
  scenario or a reference data file changed since the batch. Each case
  of a batch now gets the data folders of the process that started the
  batch (MC-19).

The scenario file moves to schema version 6 (K-47). 2.14.0 opens every
older file. 2.13.1 and earlier refuse every file that 2.14.0 saves, by
its version. The batch summary stays at format 1 with optional keys.
No computed result changed: the golden files are byte-identical, and
the 36 templates changed only in their version line
(`docs/changes.md`, 2026-11-21). The bundled CelesTrak space weather is
2.13.0's (observations to 2026-11-18; K-13, not refreshed: CelesTrak
reset the connection). By the owner's decision of 2026-11-19, the
release pull request may be merged with CI's "Windows (MAX Python)" job
red, but only for the Basilisk framework test `LambertInputValidation`
(K-45). Basilisk is unchanged. Outside `SpaceMissionStudio/` only the
front-page `README.md`'s SpaceMissionStudio part changed (section 4).
The release pull request (#308) was merged at 18:34 UTC on 2026-11-22;
as the owner asked, the assistant tagged and published it with the tag
workflow.
- CI ("SpaceMissionStudio") on `develop`'s head `1b4060c`, the merge of
  #308 ([run 45055869064](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/45055869064)), first failed before any
  test: the ITU server answered HTTP 404 for the ITU-R P.676-13 data
  file that CI downloads. The same URL answered 200 (44 100 bytes) a
  few minutes later. The one re-run of the failed jobs passed.
- The tag workflow ([run 45061002580](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/45061002580)), started at
  19:29 UTC with publish on, ran the release check on `1b4060c` and
  passed.
- Tagged `spacemissionstudio-v2.14.0` (annotated, not signed, D-13) on
  commit `1b4060c` (`1b4060c9eedfd9029d0e08e2a33ede0ee36a8792`) by the
  tag workflow (github-actions) at 19:30 UTC. GitHub release
  "SpaceMissionStudio 2.14.0", published by the release workflow at
  20:07:07 UTC, after it had counted its eleven files attached, with
  the notes written from the CHANGELOG
  (<https://github.com/0h3xn4/basilisk_space-mission-studio/releases/tag/spacemissionstudio-v2.14.0>);
  it was never public without its files.
- Its eleven files were built, installed, checked and attached by the
  release workflow ([run 45061087902](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/45061087902)). GitHub's SHA-256
  digests: `.deb` (`spacemissionstudio_2.14.0_amd64.deb`,
  441 222 632 bytes) `0a4f5edd...cf56`, setup program
  (`spacemissionstudio-2.14.0-setup.exe`, 387 036 160 bytes)
  `10ee7947...c1bd`, wheel (9 058 206 bytes) `ce2cdcba...f044`, sdist
  (9 364 823 bytes) `23412702...57ac`, the `.deb`'s bill of materials
  (`spacemissionstudio_2.14.0_amd64.cdx.json`, 35 359 bytes)
  `d2d12f04...fa49`, the setup program's
  (`spacemissionstudio-2.14.0-setup.cdx.json`, 36 459 bytes)
  `e9368de5...e8e1`, `SHA256SUMS-linux` `28e9c00d...675c`,
  `SHA256SUMS-windows` `5a45de53...a7a3`, and the LGPL sources, the same
  as 2.13.1's: `qt-everywhere-src-6.11.2.tar.xz` (1 019 661 552 bytes)
  `6dcfbca2...6f33`, `pyside-setup-everywhere-src-6.11.2.tar.xz`
  (18 053 248 bytes) `cba47efb...fdf8`, `SHA256SUMS-sources`
  `1301daba...e6f6`. Every file's digest equals its checksum in
  `SHA256SUMS-*`, and the `.deb`'s and the setup program's also those in
  the release notes; the wheel, the sdist and both bills of materials,
  downloaded from the release, give the same digests.

Earlier: 2.13.1, published 2026-11-20 (16:50 UTC).
2.13.1 is a patch release. It holds three fixes
and the 2.13.0 publication record (#299):
- **Background-thread crashes** (#302, K-44, partly fixed). Python's
  garbage collector ran in worker threads and destroyed widgets of the
  GUI thread there. Garbage is now collected on the GUI thread only
  (`gui/background_threads.py`). The start-up warm-ups and a run's first
  import of the engine hold one lock. Two more event filters keep no
  Python attribute. Two faults of K-44 were not reproduced and have no
  cause yet.
- **Plot items** (#301, K-46). The event bands, the mode lines and three
  kinds of Timeline events are neutral grey, not series colours or the
  accent. A nearly constant series gets short tick labels. A wheel's
  line carries the wheel's name from the scenario.
- **Small window fixes** (#300, K-46). Run › Thermal › Notes writes
  three significant figures. Budgets › Power and the thermal sweep table
  fit at 1280 px, also with the Inspector open. Home writes "–" for
  "--" in template descriptions. The heater energy reads "Wh".

No interface changed (ICD). `schema/`, the templates, the golden files
and the packaging are unchanged since 2.13.0. The only change outside
`gui/` is `engine/series_names.device_column_labels`, a map of wheel
names for the window; the series, the CSV columns and the exported files
keep `wheel_N`. The bundled CelesTrak space weather is 2.13.0's
(observations to 2026-11-18; K-13, not refreshed). K-46 is closed, and
K-44 is partly fixed. By the owner's decision of 2026-11-19, the
release pull request may be merged with CI's "Windows (MAX Python)" job
red, but only for the Basilisk framework test `LambertInputValidation`
(K-45). Basilisk is unchanged. Outside `SpaceMissionStudio/` only the
front-page `README.md`'s SpaceMissionStudio part changed (section 4).
The release pull request (#303) was merged at 14:50 UTC on 2026-11-20,
after #300 to #302; as the owner asked, the assistant tagged and
published it with the tag workflow.
- On #300, Windows CI first failed two of its own layout tests (the
  Power table did not fit with Windows' wider text). A follow-up commit
  fixed them. One Windows timing test (moving the 3D view to its own
  window, 52 ms against a 50 ms limit) then failed once, on code #300
  does not change; the one re-run passed.
- CI ("SpaceMissionStudio") passed on `develop`'s head `a9af24e`, the
  merge of #303 ([run 44757407951](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/44757407951)). The tag workflow
  ([run 44768019598](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/44768019598)), started at 15:54 UTC with publish
  on, ran the release check on `a9af24e` and passed.
- Tagged `spacemissionstudio-v2.13.1` (annotated, not signed, D-13) on
  commit `a9af24e` (`a9af24edc0dc96f94824a592d86a39d7308d5d7a`) by the
  tag workflow (github-actions) at 15:55 UTC. GitHub release
  "SpaceMissionStudio 2.13.1", published by the release workflow at
  16:50:10 UTC, after it had counted its eleven files attached, with
  the notes written from the CHANGELOG
  (<https://github.com/0h3xn4/basilisk_space-mission-studio/releases/tag/spacemissionstudio-v2.13.1>);
  it was never public without its files.
- Its eleven files were built, installed, checked and attached by the
  release workflow ([run 44768147987](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/44768147987)). GitHub's SHA-256
  digests: `.deb` (`spacemissionstudio_2.13.1_amd64.deb`,
  440 952 896 bytes) `555d775c...606a`, setup program
  (`spacemissionstudio-2.13.1-setup.exe`, 386 996 869 bytes)
  `87306e25...b04f`, wheel (9 031 295 bytes) `4da7229c...0632`, sdist
  (9 324 195 bytes) `197d61a7...54fe`, the `.deb`'s bill of materials
  (`spacemissionstudio_2.13.1_amd64.cdx.json`, 35 359 bytes)
  `1ed64958...98da`, the setup program's
  (`spacemissionstudio-2.13.1-setup.cdx.json`, 36 459 bytes)
  `0e3509ed...e011`, `SHA256SUMS-linux` `19ed2271...704e`,
  `SHA256SUMS-windows` `16c55dd4...8fa4`, and the LGPL sources, the same
  as 2.13.0's: `qt-everywhere-src-6.11.2.tar.xz` (1 019 661 552 bytes)
  `6dcfbca2...6f33`, `pyside-setup-everywhere-src-6.11.2.tar.xz`
  (18 053 248 bytes) `cba47efb...fdf8`, `SHA256SUMS-sources`
  `1301daba...e6f6`. Every file's digest equals its checksum in
  `SHA256SUMS-*`, and the `.deb`'s and the setup program's also those in
  the release notes; the wheel, the sdist and both bills of materials,
  downloaded from the release, give the same digests.

Earlier: 2.13.0, published 2026-11-20 (02:02 UTC): the UI audit's batches B2 to B12 (#285 to #295), with
the 2.12.0 publication recorded. Each view has one primary action, the
top bar's Run, which is off with its reason when no run can start (B2,
#286). Every empty view, list and panel says what it waits for, with
the action that fills it (B3, #285). Lists and fields show labels, not
codes; the scenario file keeps the codes (B4, #288). Several values of
one thing are a value sheet, with a unit per row (B5, #287). Every page
has one form grid and a 16 px inset (B6, #289). The Settings page has
real controls and a keyboard table (B7, #290). The top bar spans the
window, the Inspector starts closed below 1440 px, and the toasts cover
no control (B8, #291). Every table has one style (B9, #292). The first
six plot colours differ clearly in both themes, also with a colour-vision
deficiency, and the display units cover body rates, gyroscopes and wheel
speeds (B10, #293). The thermal page has one Save..., a findings chip,
status words and named study parameters (B11, #295, with its CI
follow-up: the page's least width and the toast follower). Home's cards,
the command palette, the run pages, Run › Log, About and the
confirmations are reworked (B12, #294). No interface changed (ICD):
`schema/` changed only in two comments and their field help, the
templates did not change, and 2.12.0 and 2.13.0 save the 36 templates
and a file with a `budgets` section byte for byte the same; each opens
all 37 files of the other. The golden outputs of the 36 templates are
unchanged. The bundled CelesTrak space weather was refreshed
(observations to 2026-11-18; K-13). Known limits added: K-44 to K-46.
By the owner's decision of 2026-11-19, the release pull request is
merged with CI's "Windows (MAX Python)" job red: it is a Basilisk
framework job, and one framework test fails with MSVC 19.52 (K-45).
Basilisk is unchanged; outside `SpaceMissionStudio/` only the
front-page `README.md`'s SpaceMissionStudio part changed (section 4).
The release pull request (#296) was merged at 20:10 UTC on 2026-11-19;
as the owner asked, the assistant tagged and published it with the tag
workflow.
- The first tag run ([run 44605951583](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/44605951583)) stopped at its
  release check because CI on `develop`'s merge commit `88ac9e01d9` was
  still running; nothing was tagged.
- CI on `88ac9e01d9` then failed one Windows test twice (the one re-run
  included): `test_breakout.py::test_detach_and_attach_take_under_50_ms_on_the_gui_thread`.
  `windowHandle()` returned a stale `QWidgetItem` wrapper in place of
  the new `QWindow`. #297 fixed the cause (layout items read through
  helpers that release their wrappers; K-44) before any tag. On #297,
  one run's Windows job failed once with an access violation in a fresh
  process that builds a plotly figure (`test_the_figure_warm_up_loads_what_the_first_plot_needs`);
  that code path is not changed by #297, the other run on the same
  commit passed, and the one re-run passed (K-44). #297 was merged at
  23:32 UTC with every check green.
- #297 was merged after midnight UTC, and the release check needs the
  CHANGELOG section dated the day of the tag: #298 dated the heading
  2026-11-20 and nothing else. It was merged at 01:20 UTC.
- CI ("SpaceMissionStudio") passed on `develop`'s head `c3eeb85`, the
  merge of #298 ([run 44652910748](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/44652910748)); the full suite had
  passed on `feb4880`, the merge of #297, which has the same code
  ([run 44638510711](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/44638510711)). The tag workflow
  ([run 44653376716](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/44653376716)), started at 01:24 UTC with publish
  on, ran the release check on `c3eeb85` and passed.
- Tagged `spacemissionstudio-v2.13.0` (annotated, not signed, D-13) on
  commit `c3eeb85` (`c3eeb852f6a9cae50e9e01508f7e9e9f916aaf7e`) by the
  tag workflow (github-actions) at 01:25 UTC. GitHub release
  "SpaceMissionStudio 2.13.0", published by the release workflow at
  02:02:31 UTC, after it had counted its eleven files attached, with
  the notes written from the CHANGELOG
  (<https://github.com/0h3xn4/basilisk_space-mission-studio/releases/tag/spacemissionstudio-v2.13.0>);
  it was never public without its files.
- Its eleven files were built, installed, checked and attached by the
  release workflow ([run 44653476286](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/44653476286)). GitHub's SHA-256
  digests: `.deb` (`spacemissionstudio_2.13.0_amd64.deb`,
  441 084 916 bytes) `421431fe...c43f`, setup program
  (`spacemissionstudio-2.13.0-setup.exe`, 386 995 821 bytes)
  `b206d5ec...e4f3`, wheel (9 025 467 bytes) `1062792c...ddb9`, sdist
  (9 319 691 bytes) `adb1f8cb...581e`, the `.deb`'s bill of materials
  (`spacemissionstudio_2.13.0_amd64.cdx.json`, 35 359 bytes)
  `9a79bcce...d8ec`, the setup program's
  (`spacemissionstudio-2.13.0-setup.cdx.json`, 36 459 bytes)
  `7c1442da...9d93`, `SHA256SUMS-linux` `6bf5ad46...63eb`,
  `SHA256SUMS-windows` `78597cee...e7da`, and the LGPL sources, the same
  as 2.12.0's: `qt-everywhere-src-6.11.2.tar.xz` (1 019 661 552 bytes)
  `6dcfbca2...6f33`, `pyside-setup-everywhere-src-6.11.2.tar.xz`
  (18 053 248 bytes) `cba47efb...fdf8`, `SHA256SUMS-sources`
  `1301daba...e6f6`. The `.deb`'s, the setup program's and the LGPL
  sources' digests equal the checksums in `SHA256SUMS-*`, and the
  `.deb`'s and the setup program's also those in the release notes; the
  wheel, the sdist and both bills of materials, downloaded from the
  release, pass `sha256sum -c`.

Earlier: 2.12.0, published 2026-11-18 (09:01 UTC): the
2.12.0 windows and views
(`docs/developer/windows-views-design.md`), with the 2.11.0 publication
recorded (#279). Results › 3D View, Run › Thermal and the Budgets area
can each open in a window of their own and come back (#281; decision
"Breakout windows", B-26): the view is the same live widget, so the run,
the camera, the playback and a live run stay; `Ctrl+Shift+D`, **View >
Own Windows** and the palette move it, and each window keeps its size and
place. The 3D View recovers a lost WebGL context. The globe shows the
ground track by default, solid where flown and dashed ahead, and each
ground station as a glyph with its name and a visibility ring per
spacecraft; a live 2D map (Globe | Map | Both) shows the tracks, the
stations with their lines of sight and visibility circles (SMAD 5.2),
the night side and a grid, and has its own window (#282; decision
"Ground tracks, stations and the live map"). A live run is extended in a
worker. Run › Thermal is a set of tabs whose plots keep their aspect
ratio, and each part on the 3D View can take its thermal node's
temperature as a solved run plays back (#278; T-40 to T-42). Every
dialog fits a 1280 x 720 screen (#283, UI audit batch B1). The app icon
is a mission scene on a plate, visible on dark and light panels, at
every hicolor size, as an SVG and as a Windows `.ico`, and the `.deb`
carries AppStream metadata (#276, #280). No interface changed (ICD): the
scenario file is still at schema version 5, `schema/` is unchanged since
2.11.0, and 2.11.0 and 2.12.0 save the 36 templates and a file with a
`budgets` section byte for byte the same; each opens all 37 files of the
other. The golden outputs of the 36 templates are unchanged, and the
thermal plot files are the same byte for byte. The bundled CelesTrak
space weather is 2.8.0's (K-13: not refreshed). Known limits added:
K-40 to K-43. Basilisk is unchanged; outside `SpaceMissionStudio/`
only SpaceMissionStudio's own workflows, `.claude/settings.json` and the
front-page `README.md`'s SpaceMissionStudio part changed (section 4).
The release pull request (#284) was merged at 07:39 UTC; as the owner
asked, the assistant tagged and published it with the tag workflow.
- CI on the release pull request first failed one test on its first
  commit `24b402f`: in the Linux job one move of the Budgets area into
  its own window took 60 ms, over the 50 ms limit, because a full
  garbage collection fell in it. The second commit `044c1d8` makes the
  timing test take the objects that exist before the moves out of the
  full collections, as the app does after start-up; the limits are
  unchanged (`docs/ui/TEST_CHANGES.md`). CI then passed on every check.
- CI ("SpaceMissionStudio") passed on `develop`'s head `2718e78`, the
  merge of #284, at 08:11 UTC ([run 44260636345](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/44260636345)). The tag
  workflow ([run 44265090291](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/44265090291)), started at 08:13:04 UTC with publish
  on, ran the release check on that commit and passed.
- Tagged `spacemissionstudio-v2.12.0` (annotated, not signed, D-13) on
  commit `2718e78` (`2718e7807439f2338a4eecd971268b8b7afa19f6`), the
  merge of #284 into `develop`, by the tag workflow (github-actions) at
  08:14 UTC. GitHub release "SpaceMissionStudio 2.12.0", published by
  the release workflow at 09:01:35 UTC, after it had counted its eleven
  files attached, with the notes written from the CHANGELOG
  (<https://github.com/0h3xn4/basilisk_space-mission-studio/releases/tag/spacemissionstudio-v2.12.0>); it was never public
  without its files.
- Its eleven files were built, installed, checked and attached by the
  release workflow ([run 44265254780](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/44265254780)) at 09:01. GitHub's
  SHA-256 digests: `.deb` (`spacemissionstudio_2.12.0_amd64.deb`,
  440 688 084 bytes) `c3a41f58...ef5e`, setup program
  (`spacemissionstudio-2.12.0-setup.exe`, 386 952 305 bytes)
  `df4bb857...d166`, wheel (8 943 641 bytes) `95c90fcd...dcc1`, sdist
  (9 231 488 bytes) `b560e5c3...617c`, the `.deb`'s bill of materials
  (`spacemissionstudio_2.12.0_amd64.cdx.json`, 35 359 bytes)
  `9eb877b3...4fa7`, the setup program's
  (`spacemissionstudio-2.12.0-setup.cdx.json`, 36 459 bytes)
  `927642db...9329`, `SHA256SUMS-linux` `4db15a94...ae9f`,
  `SHA256SUMS-windows` `1f7f4922...480b`, and the LGPL sources, the same
  as 2.11.0's: `qt-everywhere-src-6.11.2.tar.xz` (1 019 661 552 bytes)
  `6dcfbca2...6f33`, `pyside-setup-everywhere-src-6.11.2.tar.xz`
  (18 053 248 bytes) `cba47efb...fdf8`, `SHA256SUMS-sources`
  `1301daba...e6f6`. The `.deb`'s, the setup program's and the LGPL
  sources' digests equal the checksums in `SHA256SUMS-*`, and the
  `.deb`'s and the setup program's also those in the release notes; the
  wheel, the sdist and both bills of materials, downloaded from the
  release, pass `sha256sum -c`.

Earlier: 2.11.0, published 2026-11-17 (17:54 UTC):
phase 1 of the System Budget Studio merge, the
equipment list and the static power budget (#273, SRS-F-31) and the
Budgets area in the window (#274), with the merge plan (#270), phase 0
(#272) and the 2.10.0 publication recorded (#271). The scenario file is
at schema version 5 (decision B-01); the migration from 4 only sets the
version. Each spacecraft can carry a `budgets` section with its own
version: an equipment list with a sourced mass and sourced powers per
power mode, system modes, power margins per maturity category, a system
margin, a converter efficiency per bus and a distribution loss. A number
can be a placeholder ("TBD"): every result that needs it is then
unknown, never zero (B-04). The static power budget per system mode, per
subsystem and per bus is System Budget Studio's calculation (its D-040),
ported with its 17 reference cases and their numbers at 1e-12. The
equipment list adds lines to the mass budget, and five `budget.*`
findings report what the section leaves unknown. `idm-import --budgets`
fills the section from an IDM-CIC model. The section, the import record
target `budgets`, the `budgets` command and `api.power_budget` are new
interfaces (ICD). The **Budgets** area of the window (`Ctrl+5`) has the
pages Equipment, Power, Mass and Propellant (the former Run › Budget);
Timeline and Reports move to `Ctrl+6` and `Ctrl+7`, and the navigation
rail shows only its icons when the window is short (B-19). The run does
not use the section yet (phase 2; K-39). The golden outputs of the 36
templates are unchanged, and the templates change only in their
`schema_version` line. 2.10.0 and earlier refuse every file 2.11.0
saves, by its version (K-38); 2.11.0 opens every earlier file. The
bundled CelesTrak space weather is 2.8.0's (K-13: CelesTrak reset the
connection). Basilisk is unchanged; nothing outside `SpaceMissionStudio/`
changed but the front-page `README.md`'s SpaceMissionStudio part. The
release pull request (#275) was merged at 16:13 UTC; at the owner's
request the assistant tagged and published it with the tag workflow.
- The first tag workflow run
  ([run 44123360812](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/44123360812)), started at
  16:13:52 UTC, stopped at the release check because CI had not yet
  finished on the merge commit ("CI has not passed on this commit");
  every other check passed. It tagged nothing.
- CI ("SpaceMissionStudio") passed on `develop`'s head `d387dc5` at
  17:02 UTC ([run 44123329286](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/44123329286)). The tag
  workflow ([run 44133160433](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/44133160433)), started at
  17:05:47 UTC with publish on, ran the release check on that commit and
  passed.
- Tagged `spacemissionstudio-v2.11.0` (annotated, not signed, D-13) on
  commit `d387dc5` (`d387dc547a472c95b22a9645cdd3ce95e3f43740`), the
  merge of #275 into `develop`, by the tag workflow (github-actions) at
  17:06 UTC. GitHub release "SpaceMissionStudio 2.11.0", published by
  the release workflow at 17:54:47 UTC, after it had counted its eleven
  files attached, with the notes written from the CHANGELOG
  (<https://github.com/0h3xn4/basilisk_space-mission-studio/releases/tag/spacemissionstudio-v2.11.0>); it was never public
  without its files.
- Its eleven files were built, installed, checked and attached by the
  release workflow
  ([run 44133393083](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/44133393083)) at 17:54. GitHub's
  SHA-256 digests: `.deb` (`spacemissionstudio_2.11.0_amd64.deb`,
  440 286 236 bytes) `26991a79...a160`, setup program
  (`spacemissionstudio-2.11.0-setup.exe`, 386 388 046 bytes)
  `6d5a0f54...a0b6`, wheel (8 886 880 bytes) `acf3201e...3f37`, sdist
  (9 172 698 bytes) `1983a04e...c893`, the `.deb`'s bill of materials
  (`spacemissionstudio_2.11.0_amd64.cdx.json`, 35 359 bytes)
  `35b1cc2f...933f`, the setup program's
  (`spacemissionstudio-2.11.0-setup.cdx.json`, 36 459 bytes)
  `9a92f880...8fa2`, `SHA256SUMS-linux` `abdbead3...4776`,
  `SHA256SUMS-windows` `de0afd72...8b87`, and the LGPL sources, the same
  as 2.10.0's: `qt-everywhere-src-6.11.2.tar.xz` (1 019 661 552 bytes)
  `6dcfbca2...6f33`, `pyside-setup-everywhere-src-6.11.2.tar.xz`
  (18 053 248 bytes) `cba47efb...fdf8`, `SHA256SUMS-sources`
  `1301daba...e6f6`. The `.deb`'s, the setup program's and the LGPL
  sources' digests equal the checksums in `SHA256SUMS-*` and in the
  release notes; the wheel, the sdist and both bills of materials,
  downloaded from the release, pass `sha256sum -c`.

Earlier: 2.10.0, published 2026-11-17 (10:37 UTC):
mission operations planning (#268, SRS-F-30), with
the upstream Basilisk sync (#258) and the 2.9.0 publication recorded
(#267). A scenario can carry an optional `operations` section (schema
version still 4): targets as points or polygons (also from CSV or
GeoJSON), activity types, requests, station masks, capacity and
outages, each spacecraft's limits. The planner takes its geometry from a
run, an orbit-only Basilisk propagation or an analytic model, finds the
target windows, passes and eclipses, and schedules a horizon with a
deterministic, seeded scheduler (decisions O-10 to O-13): slews from the
attitude controller, battery and memory sample by sample, per-orbit and
per-day limits, station capacity and contention, locked activities and a
reason for every request not placed. Two of SpaceMissionStudio's own
`SysModel`s, `PlanWriter` and `PlanArbitrator`, fly the plan inside the
run, and the flight is compared with the plan (O-14, O-19, O-25, O-26);
the plan is exported as operations products with provenance (passes as
CSV and iCalendar, activities, a command schedule, pointing
predictions, OEM and AEM 2.0, a report); what-if events, replanning, a
seeded robustness batch and plan comparison complete it. **Run › Plan**,
the `plan` command and the API's `plan_*` functions are new interfaces
(ICD). Templates 35 and 36 show it. The golden outputs of the 34
earlier templates are unchanged. 2.9.0 opens the files 2.10.0 saves,
except those with an `operations` section, which it refuses by name
(K-36). The bundled CelesTrak space weather is 2.8.0's (K-13: CelesTrak
reset the connection). The feature changed nothing in Basilisk and
nothing outside `SpaceMissionStudio/` but the front-page `README.md`'s
SpaceMissionStudio part; the upstream sync (#258) brought upstream
Basilisk's `develop` into the repository, which the installers do not
use (section 4). The release pull request (#269) was merged once CI was
green; at the owner's request the assistant tagged and published it with
the tag workflow.
- CI ("SpaceMissionStudio") passed on `develop`'s head `b074260` at
  09:56 UTC ([run 44054252128](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/44054252128)). The tag
  workflow ([run 44060467004](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/44060467004)), started at
  09:58 UTC with publish on, ran the release check on that commit and
  passed.
- Tagged `spacemissionstudio-v2.10.0` (annotated, not signed, D-13) on
  commit `b074260` (`b074260f6b05f1b4f176ec1c7960857d35e05e0f`), the
  merge of #269 into `develop`, by the tag workflow (github-actions) at
  09:59 UTC. GitHub release "SpaceMissionStudio 2.10.0", published by
  the release workflow at 10:37:39 UTC, after it had counted its eleven
  files attached, with the notes written from the CHANGELOG
  (<https://github.com/0h3xn4/basilisk_space-mission-studio/releases/tag/spacemissionstudio-v2.10.0>); it was never public
  without its files.
- Its eleven files were built, installed, checked and attached by the
  release workflow
  ([run 44060591211](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/44060591211)) at 10:37. GitHub's
  SHA-256 digests: `.deb` (`spacemissionstudio_2.10.0_amd64.deb`,
  440 095 796 bytes) `7bedbeee...8c2d`, setup program
  (`spacemissionstudio-2.10.0-setup.exe`, 386 352 223 bytes)
  `dd882645...ec9f`, wheel (8 848 074 bytes) `8a6098ad...0c58`, sdist
  (9 117 174 bytes) `2fc5ce94...bf7a`, the `.deb`'s bill of materials
  (`spacemissionstudio_2.10.0_amd64.cdx.json`, 35 359 bytes)
  `37e049a1...df17`, the setup program's
  (`spacemissionstudio-2.10.0-setup.cdx.json`, 36 459 bytes)
  `feab839c...fd9b`, `SHA256SUMS-linux` `e9a9925e...2d53`,
  `SHA256SUMS-windows` `4ed9fd82...99b2`, and the LGPL sources, the same
  as 2.9.0's: `qt-everywhere-src-6.11.2.tar.xz` (1 019 661 552 bytes)
  `6dcfbca2...6f33`, `pyside-setup-everywhere-src-6.11.2.tar.xz`
  (18 053 248 bytes) `cba47efb...fdf8`, `SHA256SUMS-sources`
  `1301daba...e6f6`. The `.deb`'s and the setup program's digests equal
  the checksums in the release notes.

Earlier: 2.9.0, published 2026-11-16 (19:03 UTC):
spacecraft thermal analysis (#265, SRS-F-29), with
NASA MSFC's November 2026 solar-cycle prediction (#264, K-33 closed) and
the 2.8.0 publication recorded (#263). A spacecraft with a 3D model can
carry a lumped-parameter thermal model (the optional `thermal` section;
schema version still 4), generated from its parts and refined in the 3D
model editor; after a run, **Run › Thermal** solves it on the run's
orbit, attitude and eclipses in NASA's nominal, hot and cold cases
(NASA/TM-2001-211221) or the user's, with Basilisk's `albedo` module run
stand-alone through its public interface, and reports temperatures
against limits, heat flows, heaters, radiators, limit events and checks,
exported with provenance; sweeps, a one-at-a-time sensitivity and a
seeded thermal Monte Carlo run on the same fluxes, the 3D model can be
coloured by temperature, flexible solar arrays are nodes that turn with
the recorded hinge angle, and specific heat and conductivity can follow
tables. Templates 33 and 34 show it; the material library gained 26
coatings from NASA RP-1121. The thermal record, the `thermal` command and
a Monte Carlo summary of kind `thermal` are new interfaces (ICD). The
golden outputs changed since 2.8.0 only through the MSFC prediction
(lifetimes, and runs that start after CelesTrak's forecast, by
millimetres) and the two new templates. 2.8.0 opens the files 2.9.0
saves, except those with a thermal model, which it refuses by name. The
bundled CelesTrak space weather is 2.8.0's (K-13: CelesTrak refused the
connection). Basilisk is unchanged; nothing outside `SpaceMissionStudio/`
changed but the front-page `README.md`'s SpaceMissionStudio part. The
release pull request (#266) was merged once CI was green (its first run
found template 27's wheel speeds 1.04e-6 of their scale off, fixed by a
named tolerance, HISTORY); at the owner's request the assistant tagged
and published it with the tag workflow.
- CI ("SpaceMissionStudio") passed on `develop`'s head `8646823` at
  18:16 UTC ([run 43921940617](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/43921940617)). The tag
  workflow ([run 43930553885](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/43930553885)), started at
  18:36 UTC with publish on, ran the release check on that commit and
  passed.
- Tagged `spacemissionstudio-v2.9.0` (annotated, not signed, D-13) on
  commit `8646823` (`86468233e3d83c7e6564f09b4b60113f8893b3c0`), the
  merge of #266 into `develop`, by the tag workflow (github-actions) at
  18:37:03 UTC. GitHub release "SpaceMissionStudio 2.9.0", published by
  the release workflow at 19:03:35 UTC, after it had counted its eleven
  files attached, with the notes written from the CHANGELOG
  (<https://github.com/0h3xn4/basilisk_space-mission-studio/releases/tag/spacemissionstudio-v2.9.0>); it was never public
  without its files.
- Its eleven files were built, installed, checked and attached by the
  release workflow
  ([run 43930715195](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/43930715195)) at 19:03. GitHub's
  SHA-256 digests: `.deb` (`spacemissionstudio_2.9.0_amd64.deb`,
  439 908 004 bytes) `b39e0f90...d281`, setup program
  (`spacemissionstudio-2.9.0-setup.exe`, 385 992 328 bytes)
  `9f03cd5a...c869`, wheel (8 730 400 bytes) `cd1f0d47...7128`, sdist
  (8 994 245 bytes) `8f2ce5a5...c76f`, the `.deb`'s bill of materials
  (`spacemissionstudio_2.9.0_amd64.cdx.json`, 35 354 bytes)
  `a86d8354...4b4e`, the setup program's
  (`spacemissionstudio-2.9.0-setup.cdx.json`, 36 454 bytes)
  `4cf33e6c...6dab`, `SHA256SUMS-linux` `a9347678...5270`,
  `SHA256SUMS-windows` `19f30124...751f`, and the LGPL sources, the same
  as 2.8.0's: `qt-everywhere-src-6.11.2.tar.xz` (1 019 661 552 bytes)
  `6dcfbca2...6f33`, `pyside-setup-everywhere-src-6.11.2.tar.xz`
  (18 053 248 bytes) `cba47efb...fdf8`, `SHA256SUMS-sources`
  `1301daba...e6f6`. The `.deb`'s and the setup program's digests equal
  the checksums in the release notes.

Earlier: 2.8.0, published 2026-11-16 (00:35 UTC): a calmer interface that is easier to read, with what the tool
computes unchanged. The menu bar (File, Edit, View, Go, Run, Tools,
Help) built from the action registry, drop-down lists that open below
their field and filter a long list, dialogs that grow to fit their
wrapped text, values as sheets and tables in the 3D model editor and
the orbit-type switch, the optional reference files shown as "not
downloaded" rather than missing, plots that fill their grid and a
one-row Results toolbar (#257); Home's cards and details folded, the
side panels put aside on Home, a status bar that shows only what needs
attention, the plot list in levels, grouped 3D View notes and the
relative orbital elements named by their effect (#259); notes, warnings
and findings as lists and the remaining sentences of numbers as sheets
on every page (#261). With them: the release check and tag workflows
(#255), the compliance lists pointing to ECSS clauses instead of quoting
them (#254), the 2.7.0 publication recorded (#253), private
vulnerability reporting on (#256), tornado 6.6.1 and two pillow
advisories accepted (#260, K-25) and the documentation's screenshots
retaken. No golden file, template, scenario field, command or exit
status changed (schema version 4): every template's outputs are as in
2.7.0, and 2.7.0 opens the files 2.8.0 saves. The bundled CelesTrak
space weather was refreshed (observations to 2026-11-14; K-13); NASA
MSFC's November 2026 prediction is still not adopted (K-33). The release
pull request (#262) was merged once CI was green; at the owner's request
the assistant tagged and published it with the tag workflow, the first
release made that way (the environment cannot push tags, but can start a
workflow).
- CI ("SpaceMissionStudio") passed on `develop`'s head `db58ba6` at
  23:16 UTC on 2026-11-15. The tag workflow
  ([run 43778375893](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/43778375893)), started at 00:06 UTC
  on 2026-11-16 with publish on, ran the release check on that commit
  (CI passed on it, the CHANGELOG dated 2026-11-16, nothing under
  Unreleased, the tag new, pip-audit with no advisory not accepted) and
  passed.
- Tagged `spacemissionstudio-v2.8.0` (annotated, not signed, D-13) on
  commit `db58ba6` (`db58ba665d6c97cb8ccd945e822cf72fe1731406`), the
  merge of #262 into `develop`, by the tag workflow (github-actions) at
  00:07:05 UTC. GitHub release "SpaceMissionStudio 2.8.0", published by
  the release workflow at 00:35:50 UTC, after it had counted its eleven
  files attached, with the notes written from the CHANGELOG
  (<https://github.com/0h3xn4/basilisk_space-mission-studio/releases/tag/spacemissionstudio-v2.8.0>); it was never public
  without its files.
- Its eleven files were built, installed, checked and attached by the
  release workflow
  ([run 43778461245](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/43778461245)) at 00:35. GitHub's
  SHA-256 digests: `.deb` (`spacemissionstudio_2.8.0_amd64.deb`,
  439 911 352 bytes) `b96388d8...d44f`, setup program
  (`spacemissionstudio-2.8.0-setup.exe`, 385 849 282 bytes)
  `0ee31cf9...5e5c`, wheel (8 633 311 bytes) `1c85b074...0f55`, sdist
  (8 888 369 bytes) `e23e0b0a...bea7`, the `.deb`'s bill of materials
  (`spacemissionstudio_2.8.0_amd64.cdx.json`, 35 354 bytes)
  `36393ff6...631a`, the setup program's
  (`spacemissionstudio-2.8.0-setup.cdx.json`, 36 454 bytes)
  `b281d693...f687`, `SHA256SUMS-linux` `d0666fcd...4735`,
  `SHA256SUMS-windows` `65b35670...a0b1`, and the LGPL sources, the same
  as 2.7.0's: `qt-everywhere-src-6.11.2.tar.xz` (1 019 661 552 bytes)
  `6dcfbca2...6f33`, `pyside-setup-everywhere-src-6.11.2.tar.xz`
  (18 053 248 bytes) `cba47efb...fdf8`, `SHA256SUMS-sources`
  `1301daba...e6f6`.

Earlier: 2.7.0, published 2026-11-11 (18:25 UTC): **Results › 3D View**
as a renderer (#248, SRS-F-16) that can show a run live while it is
computed (#249, SRS-F-16), the start on Home with no scenario open
(#246, SRS-O-02), the external viewer support removed (#247; SRS-I-08,
ICD-08 and security analysis S-05, S-06 and S-11 retired), and the legal
groundwork: the licence inventory, gate and notices of every package
(#241, milestone M1), the licence change to EUPL-1.2 with the provenance
scan (#242, M2 and M3), the owner's decisions on it (#243: no copyright
claimed, ITU-R P.676-13's data file and the GPL-only Qt modules left
out of the installers, the Qt and PySide6 sources with every release),
and the risk register, security policy, sign-off check, signed build
provenance and the Windows licence gate (#245, M4); with the 2.6.0
publication and the repository's new name recorded (#244). The 3D View
is drawn by three.js 0.187.0 (MIT, bundled) in the lazily created web
view: the Earth with NASA's Blue Marble, turning by the IERS Earth
rotation angle and lit by the Sun, NASA's star map (J2000), the Moon,
each spacecraft's model shaded with its path, body axes, fields of view
and plumes, the ground stations with their line of sight and the ground
track, from the whole orbit, a followed spacecraft, the Earth's frame
or along a body axis or instrument. With **Show in 3D View while
running**, a probe last in the dynamics task samples each spacecraft
about 200 times an orbit into a feed the view draws as the run goes,
optionally paced at 1×, 10×, 100× or 1000× real time; every series of
every template is equal bit for bit with and without it. The app opens
on Home with no scenario open and lists only the open scenario's runs.
Nothing of the external viewer is left: its settings, run options,
exports, commands, CLI options and the five scenario fields, which older
files still carry and which are dropped on load and recorded in the
run's provenance (schema version 4, unchanged). From 2.7.0 the app is
licensed under the EUPL-1.2 (1.0.0 to 2.6.0 stay ISC). No golden file
changed and no scenario field was added (the templates lost only the
external viewer's fields): every template's outputs are as in 2.6.0, and
2.6.0 opens the files 2.7.0 saves (checked with 2.6.0's code on the 32 templates as 2.7.0 saves
them: all open and validate with no message). The bundled CelesTrak
space weather was refreshed (observations to 2026-11-09; K-13); NASA
MSFC's November 2026 prediction was not adopted (K-33). The release
pull request (#250) was merged once CI was green, then #251 (the release
notes' links lead to the tag; the 2.7.0 entry no longer names the
removed viewer) and #252 (below); tagging and publishing were the user's
(the environment cannot push tags).
- A first tag, on `d3d2534e1` (#250's merge) at 07:19 UTC, was deleted
  before its release run's Windows job fetched it (run 42978636332 failed
  at checkout). The user then published the release from the web at
  09:31 UTC with notes written for it, which made the tag on `96a2ec22f`
  (#251's merge); the release was public without files. That run
  ([42995929426](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/42995929426)) passed every test and
  built, installed and ran both installers, but failed at pip-audit:
  PYSEC-2026-4363 (CVE-2026-112902), a pillow 12.2.0 advisory found that
  day, in the TIFF encoder, so it attached nothing. #252 accepted it with
  its reason (K-25) and dated the CHANGELOG heading 2026-11-11. The user
  deleted the tag, which turned the release into a draft that kept its
  notes, and tagged again.
- Tagged `spacemissionstudio-v2.7.0` (annotated, not signed, D-13) on
  commit `ae5525cb8` (`ae5525cb8528c887697af4affb8669fb0aca0cef`), the
  merge of #252 into `develop`, by the user, at 17:22 UTC. GitHub release
  "Space Mission Studio 2.7.0", published by the user at 18:25:30 UTC,
  after the files were attached, with the notes written for it
  (<https://github.com/0h3xn4/basilisk_space-mission-studio/releases/tag/spacemissionstudio-v2.7.0>).
- Its eleven files were built, installed, checked and attached by the
  release workflow
  ([run 43067454786](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/43067454786)) at 18:00, which kept
  the release's notes. GitHub's SHA-256 digests: `.deb`
  (`spacemissionstudio_2.7.0_amd64.deb`, 439 988 856 bytes)
  `8992453f...1424`, setup program (`spacemissionstudio-2.7.0-setup.exe`,
  385 855 125 bytes) `03711aed...3921`, wheel (8 754 116 bytes)
  `fdb7a4cd...c7f0`, sdist (9 011 632 bytes) `92ca1133...61eb`, the
  `.deb`'s bill of materials (`spacemissionstudio_2.7.0_amd64.cdx.json`,
  35 346 bytes) `1bf39004...f449`, the setup program's
  (`spacemissionstudio-2.7.0-setup.cdx.json`, 36 446 bytes)
  `84891b5d...e138`, `SHA256SUMS-linux` `6ce7f48b...a6b4`,
  `SHA256SUMS-windows` `132d578e...6245`, and the LGPL sources:
  `qt-everywhere-src-6.11.2.tar.xz` (1 019 661 552 bytes)
  `6dcfbca2...6f33`, `pyside-setup-everywhere-src-6.11.2.tar.xz`
  (18 053 248 bytes) `cba47efb...fdf8`, `SHA256SUMS-sources`
  `1301daba...e6f6`.

Earlier: 2.6.0, published 2026-11-10 (06:51 UTC): the run in 3D inside
the app in place of the Vizard download (#239, SRS-F-16), network use
enforced and offline mode (#235, SRS-S-05), the network audit (#236),
and hash-checked installers with a bill of materials (#237, security
analysis S-08), with the documentation brought up to 2.5.0 and the 2.5.0
publication recorded (#234). **Results › 3D View** draws the run from its
own series with the app's plotly.js: the Earth turning by the IERS Earth
rotation angle and shaded by Basilisk's albedo map, each spacecraft's
path and 3D model turned by its attitude, the ground stations and the
Sun's direction, played back and kept with the shared time cursor; it
follows one spacecraft at true size with its body axes. The Vizard AVS
Lab publishes has Unity Analytics switched on (its project settings,
Unity's analytics libraries, AVS Lab's Unity project ID and Unity's
event addresses, read from the program, not run), so the tool no longer
downloads Vizard, no longer looks for one and ignores a copy an earlier
version downloaded; only a Vizard the user chooses is started (K-32).
Every download goes through one gateway that knows its hosts; offline
mode, set by the user or locked by an administrator's policy file,
switches them all off; a Python audit hook refuses any other network use
in every process the tool starts, and every use is logged. The network
audit traces every network call of a full GUI and command-line session
and fails on any call to another computer (CI on every change; here: 146
processes, none to another computer). Both installers install every
package against its recorded SHA-256, from wheels only, and carry a
CycloneDX 1.6 bill of materials, attached to the release beside them.
No template, golden file or scenario field changed: every template's
outputs are as in 2.5.0, and 2.5.0 opens the files 2.6.0 saves (checked
with 2.5.0's code on the 32 templates as 2.6.0 saves them). The bundled
space weather is still 1.3.0's: CelesTrak reset the connection again
(K-13). The release pull request (#240) was merged once CI was green;
tagging and publishing were the user's (the environment cannot push tags).
- Tagged `spacemissionstudio-v2.6.0` (not signed, D-13) on commit
  `dcbb95e09` (`dcbb95e097c42013433438cc92196ee78139f97d`), the merge of
  #240 into `develop`, by the user. GitHub release "Space Mission Studio
  2.6.0", published by the user with notes written for it
  (<https://github.com/0h3xn4/basilisk_space-mission-studio/releases/tag/spacemissionstudio-v2.6.0>).
  The user saved it as a draft first and published it at 06:51:54 UTC,
  about 1 minute 40 s after the tag started the release workflow, so it
  was public without files until the workflow attached them at 07:29.
- Its eight files were built, installed, checked and attached by the
  release workflow
  ([run 42771178369](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/42771178369)),
  which kept the release's notes. GitHub's SHA-256 digests: `.deb`
  (`spacemissionstudio_2.6.0_amd64.deb`, 451 353 268 bytes)
  `a853e7b6...4505`, setup program (`spacemissionstudio-2.6.0-setup.exe`,
  395 789 722 bytes) `1d655470...2c9e`, wheel (4 952 642 bytes)
  `b56926b2...e541`, sdist (5 155 285 bytes) `37515fb5...73f4`, the
  `.deb`'s bill of materials (`spacemissionstudio_2.6.0_amd64.cdx.json`,
  36 033 bytes) `f3dd942b...2c5b`, the setup program's
  (`spacemissionstudio-2.6.0-setup.cdx.json`, 37 155 bytes)
  `f9748a6f...c1c5`, `SHA256SUMS-linux` `1df98586...dae5`,
  `SHA256SUMS-windows` `514a9fe8...74cc`.
- The repository was renamed on 2026-11-10, after the release, from
  `0h3xn4/basilisk-SpaceMissionStudio` to
  `0h3xn4/basilisk_space-mission-studio`. GitHub redirects the old
  addresses, so the release's notes, which use them, still work; this
  document and the others now use the new name.

Earlier: 2.5.0, published 2026-11-08 (19:29 UTC): thrusters from the
IDM-CIC model (#230, SRS-F-28, decision IDM-32) and the JSON page as a
code editor (#231, #232, SRS-F-15, decisions JE-01 to JE-10), with the
documentation brought up to 2.4.0 and the 2.4.0 publication recorded
(#229). A thruster whose plume the team drew as a cone is now added to
the 3D model's equipment, where the design checks use it: placed where
the plume starts, pushing against it, with the plume's half-angle and
the thrust of the catalog product or of a mapped property
(`thruster.MaxThrust`, N or mN); it has no mass, the equipment's being
counted already. The JSON page (**Form · JSON**) colours the text, numbers
its lines, shows the matching bracket and marks every problem of the
**Problems** list where it is; it offers completion from the scenario's
own records (fields with their defaults, choices, names, a device's and a
mission step's `params`), describes the key under the cursor, renames a
spacecraft, ground station or 3D model part everywhere (F2), goes to a
name's definition (F12), offers quick fixes (Ctrl+.) and formats the text
(Shift+Alt+F). No template, golden file or scenario field changed: every
template's outputs are as in 2.4.0, and 2.4.0 opens the files 2.5.0 saves
(checked with 2.4.0's code on a file with a thruster imported at the
centre of gravity; its design checks run on the thruster). The bundled
space weather is still 1.3.0's: CelesTrak refused the connection again
(K-13). The release pull request (#233) was merged once CI was green;
tagging and publishing were the user's (the environment cannot push tags).
- Tagged `spacemissionstudio-v2.5.0` (not signed, D-13) on commit
  `1951a028c` (`1951a028ce436c6ba0452056da4c4dfed2c05b6c`), the merge of
  #233 into `develop`, by the user. GitHub release "Space Mission Studio
  2.5.0", published by the user with notes written for it
  (<https://github.com/0h3xn4/basilisk_space-mission-studio/releases/tag/spacemissionstudio-v2.5.0>).
  It was published at 19:29:07 UTC, one second before the release
  workflow started, so it was public without files until the workflow
  attached them at 20:01.
- Its six files were built, installed, checked and attached by the
  release workflow
  ([run 42515265320](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/42515265320)),
  which kept the release's notes. GitHub's SHA-256 digests: `.deb`
  (`spacemissionstudio_2.5.0_amd64.deb`, 451 057 276 bytes)
  `ef4d8e89...a530`, setup program (`spacemissionstudio-2.5.0-setup.exe`,
  395 336 265 bytes) `0a8842a2...e884`, wheel (4 786 182 bytes)
  `c4131028...ca91`, sdist (4 983 209 bytes) `17d2bf77...7515`,
  `SHA256SUMS-linux` `dc4881a3...bbd2`, `SHA256SUMS-windows`
  `4d046517...deac`.

Earlier: 2.4.0, published 2026-11-05 (20:58 UTC): each device's axis
from the IDM-CIC model (#227, SRS-F-28, decision IDM-30), and the body
frame's origin at the centre of gravity (decision IDM-31, on the release
branch, asked by the user while it was prepared). The import
already placed a sensor or actuator as its equipment is placed; it now
also reads which way it points or spins from the equipment's shapes: a
field-of-view cone gives a sensor's boresight and field of view (shown in
the 3D view, not simulated), a cylinder a wheel's spin axis or a
magnetorquer's rod axis, and +z of the equipment frame is kept when the
shapes show none. On the example models it gives the magnetorquers their
rod axes, which the +z rule of 2.3.0 had swapped. On request, the import
puts the origin of the body frame at the model's centre of gravity
(0.35 m and 0.39 m from the element's origin in the example satellites)
and moves every position of the spacecraft with it; by default it stays
the element's, as before. No template, golden file or scenario field
changed: every template's outputs are as in 2.3.0, and 2.3.0 and 2.4.0
open each other's files (checked with 2.3.0's code on files with devices
imported along the model's axes and with the origin at the centre of
gravity); a 2.3.0 re-import of a spacecraft centred by 2.4.0 does not
keep it centred (K-31). The bundled space
weather is still 1.3.0's: CelesTrak refused the connection again (K-13).
The release pull request (#228) was merged once CI was green; tagging
and publishing were the user's (the environment cannot push tags).
- Tagged `spacemissionstudio-v2.4.0` (not signed, D-13) on commit
  `ac4b90065` (`ac4b9006573dee84f68bcb1cf7800edc2a843544`), the merge of
  #228 into `develop`, by the user. GitHub release "Space Mission Studio
  2.4.0", published by the user with notes written for it
  (<https://github.com/0h3xn4/basilisk_space-mission-studio/releases/tag/spacemissionstudio-v2.4.0>).
  It was published at 20:58:24 UTC, two seconds before the release
  workflow started, so it was public without files until the workflow
  attached them at 21:33.
- Its six files were built, installed, checked and attached by the
  release workflow
  ([run 42108301360](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/42108301360)),
  which kept the release's notes. GitHub's SHA-256 digests: `.deb`
  (`spacemissionstudio_2.4.0_amd64.deb`, 451 140 540 bytes)
  `890a7bc9...71a7`, setup program (`spacemissionstudio-2.4.0-setup.exe`,
  395 007 143 bytes) `51fe6365...d442`, wheel (4 670 778 bytes)
  `7d9e5360...67b4`, sdist (4 860 633 bytes) `a277c3c1...a708`,
  `SHA256SUMS-linux` `ee7cd196...cb81`, `SHA256SUMS-windows`
  `bddb791d...882b`.

Earlier: 2.3.0, published 2026-11-05 (16:17 UTC): the satellite's
components from IDM-CIC, and a Walker constellation that holds its
spacing. The IDM-CIC import (SRS-F-28) finds the sensors and actuators an
IDM-CIC model names (#222), sets the power budget's bus load from the
model's power modes and its panel from the solar arrays' shapes (#223),
and reads the values a team keeps as properties through a mapping the
user gives (#224); the Walker generator can give every plane's
satellites phasing keeping on its first (#220, SRS-F-10). Nothing is
estimated: what the file does not give stays a product's, Basilisk's or
the editor's, and the pre-run checks say so (`import.device_defaults`,
`import.power_defaults`). No template or golden file changed: every
template's outputs are as in 2.2.0. The scenario format gained the
import record targets `devices` and `power`; 2.2.0 refuses a file that
has one (K-30) and opens every other file 2.3.0 saves; 2.3.0 opens every
2.2.0 file. The bundled space weather is still 1.3.0's: CelesTrak reset
the connection again (K-13). The release pull request (#225) was merged
once CI was green; tagging and publishing were the user's (the
environment cannot push tags).
- Tagged `spacemissionstudio-v2.3.0` (not signed, D-13) on commit
  `3f11a0227` (`3f11a022715c41bc16094d34937b586c1eb0910b`), the merge of
  #225 into `develop`, by the user. GitHub release "Space Mission Studio
  2.3.0", published by the user with notes written for it
  (<https://github.com/0h3xn4/basilisk_space-mission-studio/releases/tag/spacemissionstudio-v2.3.0>).
  It was published at 16:17:58 UTC, two seconds before the release
  workflow started, so it was public without files until the workflow
  attached them at 16:56.
- Its six files were built, installed, checked and attached by the
  release workflow
  ([run 42062956336](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/42062956336)),
  which kept the release's notes. GitHub's SHA-256 digests: `.deb`
  (`spacemissionstudio_2.3.0_amd64.deb`, 451 386 808 bytes)
  `d5622c3b...b616`, setup program (`spacemissionstudio-2.3.0-setup.exe`,
  395 189 224 bytes) `d494bb23...8b0d`, wheel (4 662 880 bytes)
  `c2009352...931a`, sdist (4 847 062 bytes) `e5b3469c...5e7d`,
  `SHA256SUMS-linux` `33822d77...499f`, `SHA256SUMS-windows`
  `d55fdf53...6dee`.

Earlier: 2.2.0, published 2026-11-05 (08:55 UTC): CCSDS orbit files in
the app (#218, SRS-F-14). What the command line already did with CCSDS
502.0-B-3 orbit messages, the GUI now does too, through one module both
use (`spacemissionstudio.ccsds_files`): import a spacecraft's orbit from
an OPM or a TLE-based OMM (recorded as `ccsds-import` records it), export
the starting orbits (OPM, or OMM for a TLE) and a run's OEMs, and check an
OPM, OMM or OEM against the standard. The windows read beside the main
window (change history, CCSDS check, input differences, manual, reference
data, run record) are windows of their own. Since 2.1.1 no scenario field,
template or golden file changed, and the command line writes the same
files: every template's outputs are as in 2.1.1, and 2.1.1 and 2.2.0 open
each other's files. The bundled space weather is still 1.3.0's: CelesTrak
reset the connection again (K-13). The release pull request (#219) was
merged once CI was green; tagging and publishing were the user's (the
environment cannot push tags).
- Tagged `spacemissionstudio-v2.2.0` (not signed, D-13) on commit
  `fa9d2b6b9` (`fa9d2b6b9f015d70cdec7f21360a762b2d26fd22`), the merge of
  #219 into `develop`, by the user. GitHub release "Space Mission Studio
  2.2.0", published by the user with notes written for it
  (<https://github.com/0h3xn4/basilisk_space-mission-studio/releases/tag/spacemissionstudio-v2.2.0>).
  It was published at 08:55:50 UTC, two seconds before the release
  workflow started, so it was public without files until the workflow
  attached them at 09:34.
- Its six files were built, installed, checked and attached by the
  release workflow
  ([run 41998260915](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/41998260915)),
  which kept the release's notes. GitHub's SHA-256 digests: `.deb`
  (`spacemissionstudio_2.2.0_amd64.deb`, 450 735 196 bytes)
  `2e4cfab3...72ae`, setup program (`spacemissionstudio-2.2.0-setup.exe`,
  395 168 677 bytes) `68715e0b...9b52`, wheel (4 629 618 bytes)
  `cf71e95e...5f99`, sdist (4 804 357 bytes) `eeffa315...b7ee`,
  `SHA256SUMS-linux` `f58d682e...96de`, `SHA256SUMS-windows`
  `5530d333...0372`.

Earlier: 2.1.1, published 2026-11-04 (19:58 UTC): fixes to problems
reported on 2.1.0 (#215, K-29). The 3D model editor is a window of its
own (it was a modal dialog, which GNOME moved with the main window); the
editor no longer writes into the built-in templates' folder (an IDM-CIC
import from a template failed with "Permission denied"); a failed
IDM-CIC import changes nothing (it left parts naming a mesh file the
model did not have); Vizard's battery panel shows watt-hours (it showed
watt-seconds). Since 2.1.0 no scenario field, template or golden file
changed, and only `engine/vizard.py`, `idm_import.py` and four GUI
modules changed in the code: every template's outputs are as in 2.1.0,
and 2.1.0 and 2.1.1 open each other's files. The bundled space weather is
still 1.3.0's: CelesTrak reset the connection again (K-13). The release
pull request (#216) was merged once CI was green; tagging and publishing
were the user's (the environment cannot push tags).
- Tagged `spacemissionstudio-v2.1.1` (not signed, D-13) on commit
  `a6413c1cb` (`a6413c1cb44fa3ec98c47ed11cd43b254b5f44c2`), the merge of
  #216 into `develop`, by the user. GitHub release "Space Mission Studio
  2.1.1", published by the user with notes written for it
  (<https://github.com/0h3xn4/basilisk_space-mission-studio/releases/tag/spacemissionstudio-v2.1.1>).
  It was published at 19:58:37 UTC, two seconds before the release
  workflow started, so it was public without files until the workflow
  attached them at 20:33.
- Its six files were built, installed, checked and attached by the
  release workflow
  ([run 41902117432](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/41902117432)),
  which kept the release's notes. GitHub's SHA-256 digests: `.deb`
  (`spacemissionstudio_2.1.1_amd64.deb`, 451 169 664 bytes)
  `4e8533e5...8909`, setup program (`spacemissionstudio-2.1.1-setup.exe`,
  394 813 391 bytes) `275df5b9...2b62`, wheel (4 619 166 bytes)
  `a1673f6a...a8eb`, sdist (4 793 047 bytes) `ed2b28cf...fbda`,
  `SHA256SUMS-linux` `bc123a74...f328`, `SHA256SUMS-windows`
  `0fb42dad...3ce0`.

Earlier: 2.1.0, published 2026-11-04 (14:57 UTC): the
spacecraft as designed. The analyses built on the 3D model (#209:
mounted equipment, a stowed configuration, materials and maturity;
design checks of fields of view, thrusters and plumes, the mass budget
and the launcher envelope; disturbance torques, blinding, antenna
obstruction, array shading, exposure and brightness after a run; a
preliminary re-entry casualty estimate), the 3D model editor's tabs for
all of it (#210, #211), and the import of IDM-CIC models (#212; IDM-CIC
is (c) CNES, read by the tool's own code). Requirements SRS-F-25 to
F-28, ICD-12. Every new scenario field is optional and written only when
set: every template's outputs are as in 2.0.0 (the golden baseline), and
2.0.0 opens a file 2.1.0 saves unless it uses them (K-27). The bundled
space weather is still 1.3.0's: CelesTrak reset the connection again
(K-13). The release pull request (#213) was merged once CI was green;
tagging and publishing were the user's.
- Tagged `spacemissionstudio-v2.1.0` (not signed, D-13) on commit
  `4346b4189` (`4346b41899378824855e190f2a6834d506ceb8c7`), the merge of
  #213 into `develop`, by the user. GitHub release "Space Mission Studio
  2.1.0", published by the user with notes written for it
  (<https://github.com/0h3xn4/basilisk_space-mission-studio/releases/tag/spacemissionstudio-v2.1.0>).
  It was published at 14:57:45 UTC, two seconds before the release
  workflow started, so it was public without files until the workflow
  attached them at 15:34.
- Its six files were built, installed, checked and attached by the
  release workflow
  ([run 41852813354](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/41852813354)),
  which kept the release's notes. GitHub's SHA-256 digests: `.deb`
  (`spacemissionstudio_2.1.0_amd64.deb`, 451 211 836 bytes)
  `5bacd782...cb04`, setup program (`spacemissionstudio-2.1.0-setup.exe`,
  395 109 752 bytes) `b930ab76...7b94`, wheel (4 615 131 bytes)
  `b7e363c9...fe3e`, sdist (4 788 403 bytes) `fb695401...3dd2`,
  `SHA256SUMS-linux` `0a91eb5c...0b00`, `SHA256SUMS-windows`
  `ddbd3093...b376`.

Earlier: 2.0.0, published 2026-11-03 (12:30 UTC): a
glass box, and Python 3.14. It takes the audit of 2026-10-27 (#120 to
#148: engine E1-E5, interface G1-G10, robustness R1-R14) and the
transparency work (`docs/transparency_audit.md`, Phases 0 to 10, #149
to #205): every figure with its calculation, every rule a parameter
a project file can change, a record of what each run, lifetime, budget
and batch came from, a reproduction bundle, value marks for computed,
overridden, preset and imported values, a change history, plugins, units
everywhere and a Python API. `docs/definition-of-done.md` says how each
of its four criteria is checked. The major version is for Python 3.14
only (`requires-python = ">=3.14"`) and for the scenario files 2.0.0
saves, which 1.3.1 and earlier do not open (K-26).

Results change where a defect was fixed, each with its before and after
values: in `CHANGELOG.md` 2.0.0 and RD1 for the audit's (the propellant
budget's rocket equation, E2: 232 kg for a 1 km/s transfer, now 93 kg;
the lifetime at the critical inclination, E1; the integrator's
tolerances, E3; the generators' mean elements, E4; the noise seeds, E5),
and in `docs/changes.md` for the transparency work's. Since Phase 1a
(2026-10-29) the golden baseline of every template's outputs
(`tests/golden/`) has held every other result, and the export files are still tested byte
for byte against those 1.1.0 wrote, less the keys added since and the
Monte Carlo table's new provenance file (`tests/gui/test_export_files.py`).
The bundled space weather is 1.3.0's (observations to 2026-10-24,
updated 2026-10-25): CelesTrak refused the download for this release
(K-13). By the user's instruction of 2026-11-03 the release pull request
(#206) was merged without asking; the tag could not be pushed from the
environment that prepared it (the git proxy refused it, HTTP 403), so
tagging and publishing were the user's.
- Tagged `spacemissionstudio-v2.0.0` (not signed, D-13) on commit
  `6608682a3` (`6608682a34c3694a1df7de86b5553d85e7ea9167`), the merge of
  #206 into `develop`, by the user. GitHub release "Space Mission Studio
  2.0.0", published by the user with notes written for it
  (<https://github.com/0h3xn4/basilisk_space-mission-studio/releases/tag/spacemissionstudio-v2.0.0>).
  It was published at 12:30:59 UTC, before the release workflow had
  started, so it was public without files until the workflow attached
  them at 13:02.
- Its six files were built, installed, checked and attached by the
  release workflow
  ([run 41636370025](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/41636370025)),
  which kept the release's notes. GitHub's SHA-256 digests: `.deb`
  (`spacemissionstudio_2.0.0_amd64.deb`, 450 924 188 bytes)
  `c54f6dad...1fb7`, setup program (`spacemissionstudio-2.0.0-setup.exe`,
  394 949 676 bytes) `84da6c46...0fbf`, wheel (4 433 556 bytes)
  `3af733a6...fb9f`, sdist (4 617 680 bytes) `ddabb97a...c2d8`,
  `SHA256SUMS-linux` `d7aded00...23ea`, `SHA256SUMS-windows`
  `84b0360a...3e05`.

Earlier still: 1.3.1, published 2026-10-27 (06:05 UTC): a
faster window (#116, #117, #118). What the tool computes is unchanged
from 1.3.0: since commit `7bdfa21ac` the only change in `engine/`,
`schema/`, `sil/`, `fsw_export/`, `model3d/`, `cli.py` or
`output_provenance.py` is in `engine/spaceweather.py`, where
`real_data_path` takes each file's last observed day from a value found
once per file (`CelestrakData.last_observed`), the same day as before
(`test_the_last_observed_day_is_found_once`). No template, data file or
golden file changed, packaging only in the version, and nothing outside
`SpaceMissionStudio/`. The export files are still tested byte for byte
against those 1.1.0 wrote (`tests/gui/test_export_files.py`). The
bundled space weather is 1.3.0's (observations to 2026-10-24, updated
2026-10-25). Merging the release pull request (#119), tagging and
publishing were the user's.
- Tagged `spacemissionstudio-v1.3.1` (not signed, D-13) on commit
  `081f74079` (`081f7407938d97abf8bcff3aae402b8235ea7c86`), the merge of
  #119 into `develop`. GitHub release "Space Mission Studio 1.3.1",
  published by the user:
  <https://github.com/0h3xn4/basilisk_space-mission-studio/releases/tag/spacemissionstudio-v1.3.1>.
  It was published at 06:05:53 UTC, before the release workflow had
  started, so it was public without files or notes until the workflow
  attached them at 06:18. The tagged `CHANGELOG.md` heading reads
  "1.3.1 (2026-10-26)", the day the release was prepared; `develop` has
  2026-10-27, the day it was published.
- Its six files were built, installed, checked and attached by the
  release workflow
  ([run 40459074482](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/40459074482)),
  which also wrote the notes because the release had none. GitHub's
  SHA-256 digests: `.deb` (`spacemissionstudio_1.3.1_amd64.deb`,
  447 262 520 bytes) `09d9a34c...4f44`, setup program
  (`spacemissionstudio-1.3.1-setup.exe`, 395 406 016 bytes)
  `486abd52...0a7e`, wheel (4 210 164 bytes) `a5b687ae...5593`, sdist
  (4 303 416 bytes) `8ffad3c5...1154`, `SHA256SUMS-linux`
  `71ab4063...1f3f`, `SHA256SUMS-windows` `2b4dbc8e...e1a9`.

Earlier: 1.3.0, published 2026-10-26 (11:55 UTC), the
UI overhaul (`docs/ui/UI_OVERHAUL_PLAN.md`, milestones M2a to M9, PRs #96
to #107; the user's brief, `docs/ui/UI_OVERHAUL.md`). What the tool
computes is unchanged from 1.2.0: since commit `c92f90040` nothing changed
in `engine/`, `schema/`, `sil/`, `fsw_export/`, `model3d/`, `cli.py` or
`output_provenance.py`, three templates changed their description text
only, and the golden files are unchanged. The export files are tested
byte for byte against those 1.1.0 wrote (`tests/gui/test_export_files.py`;
1.2.0's code writes the same bytes). Merging the release pull request,
tagging and publishing were the user's (decision of 2026-10-19, HISTORY
"Towards release 1.1.0"). After the preparation it also took the
documentation refresh (#109), the Alt+Backspace fix and the engine
messages (#110), the space weather refreshed to 2026-10-24 (#111, which
changes drag on dates from 2026-09-09 to 2026-12-07 and in 2027-01 and
2027-02), the MSFC check (#112), the theme switch (#113) and the
spacecraft page built a section at a time (#114).
- Tagged `spacemissionstudio-v1.3.0` (a lightweight tag, not signed,
  D-13) on commit `7bdfa21ac` (`7bdfa21ac8262e358e18ae040972ed95944c4246`),
  the merge of #114 into `develop`. GitHub release "Space Mission Studio
  1.3.0", published by the user:
  <https://github.com/0h3xn4/basilisk_space-mission-studio/releases/tag/spacemissionstudio-v1.3.0>.
  It was published at 11:55 UTC, before the release workflow had attached
  anything, so it was public without files or notes until the workflow
  finished at 12:07. The tagged `CHANGELOG.md` still reads "1.3.0 (not
  yet released)"; `develop` has the date.
- Its six files were built, installed, checked and attached by the
  release workflow
  ([run 40318662400](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/40318662400)),
  which also wrote the notes because the release had none. GitHub's
  SHA-256 digests: `.deb` (`spacemissionstudio_1.3.0_amd64.deb`,
  447 092 940 bytes) `77cae8f5...5d8f`, setup program
  (`spacemissionstudio-1.3.0-setup.exe`, 395 419 705 bytes)
  `d36d40c8...036a`, wheel (4 207 447 bytes) `f1c69d00...0fd2`, sdist
  (4 300 623 bytes) `f0aaa103...9fd7`, `SHA256SUMS-linux`
  `cbaef561...bc7c`, `SHA256SUMS-windows` `e95391ec...7964`.

Before that: 1.2.0, published 2026-10-21 (17:20 UTC), starting a
mission from scratch, guided, and the end of macOS support:
- Tagged `spacemissionstudio-v1.2.0` (a lightweight tag, not signed,
  D-13) on commit `c92f90040` (`c92f9004075bb28bbad361d55408b827670c0e1a`),
  the merge of the release pull request (#94) into `develop`. GitHub
  release "Space Mission Studio 1.2.0", published by the user:
  <https://github.com/0h3xn4/basilisk_space-mission-studio/releases/tag/spacemissionstudio-v1.2.0>.
  It was published at 17:20 UTC, before the release workflow had
  attached anything, so it was public without files or notes until the
  workflow finished at 17:33.
- Its six files were built, installed, checked and attached by the
  release workflow
  ([run 39642864007](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/39642864007)).
  GitHub's SHA-256 digests: `.deb` (`spacemissionstudio_1.2.0_amd64.deb`,
  446 730 028 bytes) `92760538...0809`, setup program
  (`spacemissionstudio-1.2.0-setup.exe`, 394 968 402 bytes)
  `747bdee3...f3bc`, wheel (4 066 610 bytes) `db73117d...3d23`, sdist
  (4 177 942 bytes) `6b940d87...8a5d`, `SHA256SUMS-linux`
  `50ec7c8c...c4ed`, `SHA256SUMS-windows` `fec5c2f8...46e0`.
- Its release notes were the first the workflow wrote itself
  (`packaging/release_notes.py`, from `CHANGELOG.md` 1.2.0).

And before: 1.1.1, published 2026-10-21 (tag `spacemissionstudio-v1.1.1` on
`57a54ae92`, PR #90), the self-contained installers; 1.1.0, published
2026-10-20 (tag `spacemissionstudio-v1.1.0` on `1f8ad1663`, PR #86),
whose installers set up a virtual environment while installing, needing
internet access and, for the setup program, Python 3.11 on `PATH`
(K-20).

## 1 Introduction (G.2.1<1>)

This SRelD describes release 2.15.0 of SpaceMissionStudio in
`0h3xn4/basilisk_space-mission-studio`: what it contains, what changed since 2.14.2
(commit `452e164`), what is known to be wrong, and how to use it.

## 2 Applicable and reference documents (G.2.1<2>)

| Ref. | Document |
|---|---|
| RD1 | `HISTORY.md`: the change log, with an entry per change |
| RD2 | SVR (`SVR.md`): the verification and validation results of this release |
| RD3 | SRF (`SRF.md`): the reused software baseline |
| RD4 | `compliance/deviations.md`, `compliance/human_actions.md` |
| RD5 | SUM (`SUM.md`) |

## 3 Terms, definitions and abbreviated terms (G.2.1<3>)

| Term | Meaning |
|---|---|
| SPR | Software problem report: here, a known open problem listed in 5.2 (no SPR system exists yet, H05) |
| SW&D | Software waiver and deviation: the deviations D-01 to D-13 |

## 4 Software release overview (G.2.1<4>)

| Item | Value |
|---|---|
| Configuration item | SpaceMissionStudio (`SpaceMissionStudio/` in the repository) |
| Baseline | `develop` after the 2.15.0 release pull request (the changes of #313, #314, #316 and #317, from `records/2.14.2-published` at `79e0331`, which holds `develop` at `0dc0810`, and the release's records), tagged `spacemissionstudio-v2.15.0` on `5ebbd3b` (`5ebbd3bda91fa52fe907a1a3747b8ebe1c1eaee0`), the merge of #318, by the tag workflow. Previous release: 2.14.2, commit `452e164` (`452e164e7652de7135fe513d82039bbf311b388f`), tagged `spacemissionstudio-v2.14.2`. |
| Reused software baseline | Basilisk 2.12.0 (PyPI), numpy, sgp4, pyerfa, PySide6, plotly (RD3); the tested versions are pinned in `packaging/constraints.txt`. Bundled with the GUI as files, not packages: Inter 4.1 and JetBrains Mono 2.304 (SIL OFL 1.1), 47 Lucide icons from lucide-static 1.52.0 (ISC), and for the 3D View three.js 0.187.0 (MIT, one bundle built from the pinned npm packages) and resized copies of NASA's Blue Marble (also under the 2D map and in the app icon) and Deep Star Maps 2020 (public domain), with versions, sources and checksums in `docs/THIRD_PARTY_ASSETS.md`. The installers also carry CPython 3.14.8 (python-build-standalone 20261013, SHA-256 pinned) with every installed package and the reference data; each build lists them in its `SPACEMISSIONSTUDIO_RUNTIME.json`, and `docs/THIRD_PARTY_ASSETS.md` ("In the installers") gives their licences |
| Platform | The installers: Linux x86_64 with glibc 2.34 or newer (`.deb`), Windows 10/11 x64; no Python needed. From source: Python 3.14 (3.11 to 3.13 are no longer supported; Basilisk 2.12.0 and PySide6 6.11 do not install on 3.15 yet) |
| Delivery | Attached to the GitHub release by the release workflow (`.github/workflows/spacemissionstudio-release.yml`): the wheel and sdist, the Debian package `spacemissionstudio_2.15.0_amd64.deb`, the Windows setup program `spacemissionstudio-2.15.0-setup.exe` (not signed, D-13), each installer's bill of materials (`spacemissionstudio_2.15.0_amd64.cdx.json`, `spacemissionstudio-2.15.0-setup.cdx.json`, CycloneDX 1.6), `SHA256SUMS-linux` and `SHA256SUMS-windows`; since 2.7.0, the complete source of the LGPL-3.0 Qt libraries the installers carry (`qt-everywhere-src-6.11.2.tar.xz`, `pyside-setup-everywhere-src-6.11.2.tar.xz`, checked against the size and SHA-256 Qt publishes, `packaging/legal/qt-sources.json`) with `SHA256SUMS-sources`, and a Sigstore-signed build provenance of every built file (`gh attestation verify`) |
| Documentation | SUM and `USER_MANUAL.md`; the documents in `compliance/docs/` |
| Basilisk framework | No Basilisk source, module or test changed. Since 2.14.2 one file outside `SpaceMissionStudio/` changed (`git diff --name-only 452e164`): the front-page `README.md`'s SpaceMissionStudio part (its version badge and Version line). Monte Carlo phase A uses Basilisk 2.12.0's own interfaces as in 2.14.0: `RetentionPolicy.addRetentionFunction` for the outcomes and data files, and `SimulationExecutor.applyModification` to apply a case's `run<N>.json`. Phase B adds no Basilisk interface: the batch seed reseeds in the app's creation function, which Basilisk 2.12.0's `Controller.SimulationExecutor.__call__` calls after its own seeding and before the draws (read in the installed wheel, not changed; K-49). CI's "Windows (MAX Python)" job, in Basilisk's own "Pull Request" workflow, fails the framework test `LambertInputValidation.RejectsCollinearityBeforeLambdaAndTimeScaling` on GitHub's runner image 20261111 (MSVC 19.52.37029; it passed on 20261103, MSVC 19.51); by the owner's decision of 2026-11-19 SpaceMissionStudio's pull requests are merged with that check red, and the framework is not changed (K-45). The installers carry Basilisk 2.12.0 from PyPI, not this repository's framework, and add its support data next to the installed package, in the folder its own `dataFetcher` reads |

## 5 Status of the software configuration item

### 5.1 Evolution since previous version (G.2.1<5.1>)

`CHANGELOG.md` 2.15.0 lists the changes since 2.14.2 (commit `452e164`);
RD1 has the full story ("Monte Carlo phase B, part 1", "part 2" and
"part 3", with their follow-ups). In summary, Monte Carlo phase B
(`docs/developer/monte-carlo-plan.md`; decisions MC-20 to MC-35 in
`docs/DECISIONS.md`, MC-27 and MC-34 provisional):

- **Batch seed** (#313, B1, K-24; `engine.monte_carlo._reseed`,
  `basilisk_run_index`): `monte_carlo.seed` at schema version 7. The
  creation function reseeds NumPy's legacy generator and `random` with
  `SeedSequence(entropy=seed, spawn_key=(index,))`. The run index is
  read back from the MT19937 state that Basilisk's seeding left; a state
  already drawn from fails the run with a message (plan risk R1). The
  summary keeps `seed`, `archive.provenance.json` `monte_carlo_seed`,
  and `monte-carlo` prints it. Without a seed nothing is reseeded.
- **Thermal node limits** (#313, B4;
  `monte_carlo_requirements.node_limits`): each run's lowest and highest
  solved temperature per node, judged against the case's operating and
  survival ranges (a run on a limit is inside, a failed run outside
  every range), with `clopper_pearson_upper` at the thermal Monte
  Carlo's optional `confidence` (no default). Template 34: the battery
  is outside its operating range in 4 of 20 runs.
- **Small fixes** (#313, B8): "Processes" (the file keeps
  `thread_count`), the Failed tile as a count, a thermal batch's Status
  column, the starting attitude's bounds in degrees in the form (radians
  in the file). The Home details' buttons in a `FlowLayout`.
- **Outcome statistics** (#314, B3; `engine/monte_carlo_statistics.py`):
  N, minimum, percentiles and maximum per outcome, and the empirical
  distribution function. `numpy.percentile` with
  `monte_carlo.percentile_method` (`linear`, Hyndman and Fan's
  definition 7); `monte_carlo.percentiles` 1, 5, 50, 95 and 99 % with
  the source "TBD" (MC-27, provisional). The thermal and operations
  band is labelled "mean ± 3 standard deviations (not a probability
  bound)"; its values do not change.
- **Sensitivity** (#314, B2): Spearman's rank correlation (ties at
  their mean rank) or Pearson's, by `monte_carlo.sensitivity_measure`,
  pairwise, with N per pair; "—" for a column that does not vary or
  fewer than 3 runs. About 0.5 s for 100 000 runs, 10 drawn values and
  30 outcomes, in a one-thread `QThreadPool`. The plots' JSON, page and
  page file are made in a worker; the GUI thread's part takes 4 to 7 ms
  for 100 000 runs (a test requires under 50 ms).
- **Trust checks** (#314, B6): the plausibility finding
  `monte_carlo.nominal_outside` (dry mass, drag and SRP coefficient;
  none of the 36 earlier templates gives it), and a warning with both
  SHA-256 when a batch's scenario is not the open one
  (`monte_carlo_case.batch_scenario_hash`).
- **Batch report** (#316, B5; `engine/monte_carlo_report.py`): JSON
  (`kind: "monte_carlo_report"`, `format` 1) or Markdown by the file's
  suffix, from the functions the view uses; written in a one-thread
  worker. The Runs table's CSV writer moved to the engine.
- **Command line** (#316, B7): `monte-carlo --summarize DIR` (prints
  the batch and writes its Runs table, changes nothing in DIR, exit
  status 5 as after a batch), `--csv FILE`, `--report FILE`, `--runs N`
  and `--processes N` (the scenario file is unchanged; recorded in
  `archive.provenance.json`'s `monte_carlo_settings.overrides`). A batch
  run also prints the outcome statistics and the ten strongest
  correlations. Flags that do not go together are usage errors (2).
- **Template 37** (#316, B9, MC-34 provisional): template 25's satellite
  for half a day, 30 runs, batch seed 37, three dispersions, two
  requirements at 90 % confidence; 53 s in one process. Its golden file
  is new, with the golden angle floor for drawn angles in degrees.
- **Records:** the 2.14.2 publication (#317); `docs/changes.md`,
  "Scenario schema version 7"; `docs/models/monte-carlo-statistics.md`.

**Unchanged:** every existing field, command, option, exit status and
API function, and what runs compute. A batch without a seed draws what
it drew before. The golden outputs of the 36 earlier templates pass
unchanged, the Monte Carlo goldens of templates 09 and 25 included.
The batch summary is still format 1.
**Changed in the interface** (ICD): the scenario file's
`schema_version` 7, `monte_carlo.seed` and a thermal Monte Carlo's
`confidence`; `monte-carlo --summarize`, `--csv`, `--report`, `--runs`
and `--processes`; `thermal --monte-carlo`'s node limits table; the
batch summary's optional `seed`, node limits, `sensitivity_measure`,
`percentile_method` and `percentiles`; `archive.provenance.json`'s
`monte_carlo_seed` and `monte_carlo_settings`; the Monte Carlo report
and the Runs table CSV with its provenance; the project parameters
`monte_carlo.percentiles`, `monte_carlo.percentile_method` and
`monte_carlo.sensitivity_measure`; the finding
`monte_carlo.nominal_outside`.
**File format, checked on the code with `git diff 452e164`** (the 2.14.2
tag): `schema/` has the step to version 7 (`migrations.py`,
`scenario.py`, `thermal.py`, `field_help.json`), and
`tests/data/scenario_hashes.json` was recorded again (the 72 hashes of
the 36 templates changed, template 37's 2 added). Template 37
(`scenarios/templates/`) and its golden file (`tests/golden/`) are new.
The 36 earlier templates differ only on their `schema_version` line:
with the line set back to 6, all 36 are byte for byte the files at
`452e164`, and the version 6 text and scenario give the hashes recorded
at `452e164`. The 36 earlier golden files are byte-identical.
`packaging/` changed only in the version line of the Inno Setup script.
**Compatibility, checked with 2.14.2's code (the tag, `452e164`):**
2.14.2 refuses all 37 templates as 2.15.0 saves them, each with
"scenario file is schema_version 7, but this build of SpaceMissionStudio
only understands up to version 6" (K-49). 2.15.0 opens the 36 templates
as 2.14.2 saves them (version 6) and saves them again byte for byte as
its own templates. 2.14.2 opens a batch summary that 2.15.0 writes
(template 37, 4 runs, with the seed, the requirements and the new
optional keys) and ignores the new keys.

**Tests:** 5947 passed and 19 skipped on Linux, Python 3.14, on the
release's code, in one run of `pytest tests -q -n 4 -p no:cacheprovider
-o faulthandler_timeout=300` (5967 tests: 3692 outside `tests/gui/`
and 2275 in it; 5863 passed at 2.14.2, in a run with the reference data
fetched); coverage was not measured again for this release. One test
failed: `tests/gui/test_shell_chrome.py::test_a_reported_path_is_not_clipped_in_the_status_bar`
(511 px against 509 px). It fails only in this container, on `develop`
too; CI is the reference. The run ended in 20 min 24 s; no test hung.
The new test files are `tests/test_monte_carlo_statistics.py` and
`tests/test_monte_carlo_report.py`; more new tests are in
`tests/test_monte_carlo.py`, `test_cli.py`, `test_migrations.py`,
`test_scenario_schema.py`, `test_template_claims.py` and others, and
in `tests/gui/test_monte_carlo_results_widget.py`,
`test_monte_carlo_editor.py` and `test_home.py`. The changed test
lines are in `docs/ui/TEST_CHANGES.md` (MC-25, MC-31, MC-35). The
release itself changed no test. CI on the tagged commit `5ebbd3b` (run
45261875723) passed at the first attempt. The release workflow's tests
(run 45294483106) passed at the first attempt, on the Windows runner
too.

**Still open:** K-19 (about 0.4 s), K-22, K-23 (smaller), K-24 (fixed
when a seed is set), K-25, K-26, K-27, K-28, K-30, K-31, K-34, K-35,
K-36, K-37, K-38, K-39, K-40 (partly met), K-41, K-42, K-43, K-44
(partly fixed), K-45, K-47, K-48, K-49, K-50, K-51. Closed: none.

**Changes users notice:** a Batch seed under Scenario › Monte Carlo;
the Statistics, Sensitivity and, for a thermal batch, Node limits tabs
and Export report... under Results › Monte Carlo; a Problems panel
warning for a dispersion that no longer fits its spacecraft; a warning
on a batch of another scenario; "Processes", the Failed tile as a count
and the starting attitude in degrees; `monte-carlo --summarize`,
`--report`, `--csv`, `--runs` and `--processes`; template 37; the Home
details' buttons one above the other when they do not fit; files saved
at schema version 7, which 2.14.2 does not open.

### 5.2 Known problems and limitations (G.2.1<5.2>)

**Known problems (no SPR system exists, so these stand in for SPRs):**

| # | Problem | Effect | Ref. |
|---|---|---|---|
| K-01 | Closed: the drag figures published before F-07 and F-09 (5-year runs, re-entry from 300 km, launch-delay sweep, altitude trade, disposal, templates 05 and 21) were re-measured on Basilisk 2.12.0. Station-keeping and trade figures fall 12-20 %; HISTORY, the template 05 and 21 descriptions, the template 21 claim test and the drag make-up docstring now give the new values. The bundled space weather has also changed since some were published, and the re-measurement does not separate the two; the disposal figures move both ways, not explained | – | `compliance/drag_remeasure.md`; HISTORY.md |
| K-02 | The drag case of V-04 has an unexplained 1.6 % decay difference from GMAT (within tolerance) | Drag results carry it | `phase3_log.md` |
| K-03 | The time argument is TDB, not TAI (F-05) | About 0.1 m/day in LEO | `phase3_log.md` |
| K-04 | Radius part closed (2026-10-19): Basilisk put the body's radius in place of the field file's (F-03), which scaled Mars's GGM2B J2 by 4.8e-4 and Earth's by 1e-7. The tool now rescales the coefficients so that the file's field is applied (`engine/gravity_field.py`, `tests/test_gravity_field.py`). The field's GM is still the body's (D-07) | GM: 1.4e-8 (Earth) and 1.4e-6 (Mars) on the harmonic terms | `phase3_log.md` F-03 |
| K-05 | Closed in 2.7.0 (#247): the tool no longer streams to an external viewer, so no live stream and no listening viewer exist. Before: during a live stream Vizard, a separate program, listened on port 5556; the tool opened no port. Earlier issues of the security analysis wrongly said Basilisk binds 5556 and 5570 on all interfaces | – | security analysis S-06 (retired 2026-11-10) |
| K-06 | The Windows setup program has not been run by hand on a Windows machine; 1.1.0 to 1.3.0 ship it, built, installed silently and run on a GitHub Windows runner (K-12) | Unknown for interactive use | SValP 9 |
| K-07 | Closed (decision 19): SRS-P-09 and SRS-R-02 measured and met on the reference PC | – | SVR; `compliance/performance.md` |
| K-10 | Closed: the test suite failed on Windows (34 tests) and macOS (10 tests) in CI run 20. Four causes were tool defects (F-09 to F-12, fixed); the rest were tests that assumed Linux. Since commit `41b73b1c3` the suite passes on all three (2259 passed, 11 skipped, 0 failed; run 37854361784). The GUI has not been used by hand on Windows or macOS | – | SVR 4.6; `review_log.md` |
| K-11 | F-09, fixed: parallel runs could read a half-written space-weather file. Altitude trades with more than one worker and Monte Carlo runs with NRLMSISE-00 drag, made before the fix, may have used wrong solar activity | Those results are to be re-run | `review_log.md` F-09 |
| K-08 | Closed: the PNG/SVG export polled the page with overlapping asynchronous queries; a late timer tick read the cleared state (the CI tracebacks), and several answers could save the file twice. One query at a time now, late answers ignored (F-12) | – | `review_log.md` F-12 |
| K-09 | Closed (2026-10-19): 1054 of the 2314 unit and integration test functions had no docstring. Every one now has a docstring stating what it checks, read from its body; no test code changed (each file's syntax tree without docstrings equals the one before) | – | `SUITP_test_cases.md`; HISTORY.md |
| K-12 | The Windows setup program is built, installed silently and the installed tool run on a GitHub Windows runner (1.1.1: with an empty support-data cache, the GUI opened offscreen); the wizard has not been clicked through by hand and the GUI not opened on a real Windows machine, and an upgrade over an installed 1.1.0 has not been tried. The graceful SIL close (M15) has not run on Windows | Unknown for interactive use on Windows | `AUDIT.md` sections 5 and 6; `packaging/README.md` |
| K-13 | Closed: the bundled CelesTrak space weather (observations to 2025-07-20) was refreshed for this release: observations to 2026-10-11, updated 2026-10-12. Refreshed again on 2026-10-19 for the next release: observations to 2026-10-18, CelesTrak's daily forecast to 2026-12-02, updated 2026-10-19 20:34 UTC. Refreshed for 1.3.0 on 2026-10-26: observations to 2026-10-24, daily forecast to 2026-12-07, updated 2026-10-25 23:32 UTC (CelesTrak revised its values from 2026-09-09 and the monthly forecast's 2027-01 and 2027-02). Results of drag runs dated after 2025-07-20 change, because observed solar activity replaces the earlier forecasts. Not refreshed for 2.0.0, 2.1.0, 2.1.1, 2.2.0, 2.3.0, 2.4.0, 2.5.0 nor 2.6.0: on 2026-11-03, twice on 2026-11-04, three times on 2026-11-05, on 2026-11-08 and on 2026-11-09 CelesTrak reset or refused every connection from the environment the release was prepared in, so 2.0.0 to 2.6.0 carry 1.3.0's file (observations to 2026-10-24, forecast to 2026-12-07). Refreshed for 2.7.0 on 2026-11-10: observations to 2026-11-09, daily forecast to 2026-12-24, updated 2026-11-10 21:33 UTC (CelesTrak revised its observed values from 2026-09-17 and NOAA the monthly forecast's 2027-01 to 2031-09, which no run uses while an MSFC prediction is there); drag on dates from 2026-09-17 to 2026-12-24 changes, no template does. Refreshed for 2.8.0 on 2026-11-15: observations to 2026-11-14, daily forecast to 2026-12-29, updated 2026-11-15 20:37 UTC (CelesTrak reset the first two connections from this environment and answered the third); drag on dates from 2026-11-10 to 2026-12-29 changes, no template does (the golden outputs pass unchanged). Not refreshed for 2.9.0: on 2026-11-16 CelesTrak reset all three connections from this environment, so 2.9.0 carries 2.8.0's file. Not refreshed for 2.10.0: on 2026-11-17 CelesTrak reset the connection again, so 2.10.0 carries the same file. Not refreshed for 2.11.0: later on 2026-11-17 CelesTrak reset the connection again, so 2.11.0 carries the same file. Not refreshed for 2.12.0: the release was prepared without a refresh (not tried), so 2.12.0 carries the same file. Refreshed for 2.13.0 on 2026-11-19: observations to 2026-11-18, daily forecast to 2027-01-02, updated 2026-11-19 17:33 UTC (CelesTrak answered the first connection; it revised its 81-day averages from 2026-10-08, and its monthly forecast now starts in February 2027, so the file has no row from 2027-01-03 to 2027-01-31, which NASA MSFC's prediction covers); drag on dates from 2026-10-08 to 2027-01-02 changes, no template does (the golden outputs pass unchanged). NASA MSFC's November 2026 prediction is still the latest issue (checked on 2026-11-19). Not refreshed for 2.13.1: it was refreshed for 2.13.0 the day before, so 2.13.1 carries 2.13.0's file. Not refreshed for 2.14.0: on 2026-11-22 CelesTrak reset all three connections from this environment (the TLS handshake, `curl` error 35), so 2.14.0 carries 2.13.0's file; NASA MSFC's November 2026 prediction is still the latest issue (its page, checked on 2026-11-22, links `nov2026f10-prd.txt`). Not refreshed for 2.14.1: on 2026-11-22 at 23:16 UTC CelesTrak again reset all three connections from this environment (`curl` error 35), so 2.14.1 carries 2.13.0's file; NASA MSFC's page still links `nov2026f10-prd.txt`, the bundled prediction. Not refreshed for 2.14.2: on 2026-11-23 from 04:27 to 04:28 UTC CelesTrak again reset all three connections from this environment (`curl` error 35), so 2.14.2 carries 2.13.0's file; NASA MSFC's page still links `nov2026f10-prd.txt`. Not refreshed for 2.15.0: on 2026-11-23 at 18:45 UTC CelesTrak again reset all three connections from this environment (`curl` error 35), so 2.15.0 carries 2.13.0's file; NASA MSFC's page, checked at the same time, still links `nov2026f10-prd.txt`, the bundled prediction. Users fetch the current one in the app (Home's reference-data card, **Settings > Reference data**) or with `spacemissionstudio spaceweather-download` | Drag on dates after 2026-11-18 uses CelesTrak's forecast until the file is fetched | `spacemissionstudio/data/spaceweather/README.md` |
| K-14 | Addressed, under watch: platform test failures. On Windows, two tests fail intermittently in CI (PR #64, 2026-10-14; each passed on the same commit in another run). `test_the_altitude_trade_runs_its_altitudes_in_parallel_processes`: a worker hit a Basilisk error whose exception cannot be pickled, so its message is lost (cause not yet known; suspected: the cached space-weather file opened by one worker while another replaces it). `test_a_step_without_deadline_waits_while_earlier_steps_are_still_answered`: its fake flight software went over the 0.3 s step timeout on a loaded runner (a test margin). On macOS (PR #65, 2026-10-14), `test_forms_stay_at_a_readable_width` and `test_a_template_row_keeps_its_customize_button_close` fail their own precondition: Qt's `cocoa` platform fits the 2560 x 1440 test window to the runner's screen, so the page is 618 px wide and there is no wide screen to check (a test set-up problem, not the layout). Fixed on the ROE branch (PR #73, commit `f601576c1`, 2026-10-18): the test window is laid out with `WA_DontShowOnScreen`, which the screen does not constrain, and the fixture asserts its 2560 x 1440 size; macOS CI then passed both (3347 passed, 0 failed, 11 skipped, run 39165811899). On the release commit `f288e0c73` (run 38633749308) Windows passed (3224 passed, 16 skipped) and macOS failed these two (3229 passed, 2 failed, 11 skipped). By the user's decision 1.0.0 is a Linux release; Windows and macOS are fixed and released later. Windows pair addressed on 2026-10-18 (after PR #73): the SIL test's step timeout is 1 s against 30 ms answers (it was 0.3 s against 20 ms), and the altitude trade's lost message is a confirmed bug, now fixed: Basilisk's `BasiliskError` cannot be pickled (its module `_bskLogging` does not import by that name), so any Basilisk error in a worker arrived as a pickling error. Workers now send such an error as a `BudgetError` with its type, message and traceback. The suspected cause is removed too: a complete space-weather file is no longer replaced by a second worker's copy, which on Windows could meet the first worker opening it. The Basilisk error behind the 2026-10-14 failure was never seen, so its cause is not confirmed; if it recurs, its message now shows. macOS, 2026-10-19 (PR #75, run 39218996167): `test_the_keys_work_where_results_has_the_focus` timed out waiting for its window to become active (passed on the PR's previous commit). On macOS activation is per application, and the parallel test workers are separate processes whose windows can keep it from this one; the test now sets Qt's active window itself (`QApplication.setActiveWindow`), which is what the shortcut map checks. Not reproducible on Linux (offscreen activates every shown window); confirmed only by the next macOS CI runs. Windows, 2026-10-19 (PR #76, job 118026573080): `test_thousands_of_dropped_steps_never_block_the_link[tcp]` failed with "the flight software took no STEP for 10 s" at step 16172 of 20000; the other Windows job on the same commit and the one re-run passed. The fake flight software was waiting to read when the link closed, so the simulation side's send found the socket not writable for 10 s, or did not run for that long. Cause not confirmed: not reproduced on Linux in 60 runs under CPU overload. A related defect was confirmed and fixed: `SocketTransport.send` gave up as soon as its time had run out, before trying the socket again, so a stall of the simulation's own process counted as the flight software's silence. The send now counts its time from the last bytes the peer took and tries once more without waiting before it gives up (`test_a_stall_of_this_process_is_not_the_peers_silence`, which fails on the previous code). Whether this was the Windows failure is confirmed only if it does not recur. It recurred on 2026-10-21 (PR #90, job 119083739177, on the 1.1.1 release commit `9dca37d5f`): the same message at step 10907 of 20000, and again the fake flight software was waiting to read when the link closed. So the send's stall handling was not the cause, and the cause is still not known. Not a Basilisk thread holding Python's interpreter lock: a Basilisk run in a second thread let the other thread run at least every 0.03 s (measured on Linux). Only this test has shown it (20000 steps, every one dropped, over TCP on a Windows runner); it may also stop a Windows SIL session that drops thousands of steps, with "the flight software took no STEP for 10 s". Not reproduced since (PR #91, 2026-10-21): the test alone passed 240 times on `windows-latest` (four workers side by side, two processes keeping the CPU busy) and the whole suite passed seven times on Windows (six runs of the new workflow "SpaceMissionStudio SIL stress (Windows)" and the platforms job). On a stall the test now fails with the state of both ends of the link: frames sent and dropped, bytes received and not read, the socket buffer sizes, what the fake flight software last did, when, and its stack, and the last `select()` calls of the send. The next recurrence names its cause. It recurred three times on 2026-10-27 (runs 40526819275 and 40543074495, twice) and named it: every `select()` of the stalled send saw the socket readable and not writable, the fake flight software alive and reading its backlog (12462 frames sent, 4568 read). The send's 10 s limit counted only bytes the peer took, and Windows reopens a full receive window only once the reader has freed much of it, so a peer that was answering looked silent. Fixed in 2.0.0 (#128): bytes the peer sends count too (`SocketTransport.send`); `test_a_peer_that_keeps_answering_is_not_silent` fails without the fix | Windows: an altitude trade with several workers may have failed with an unexplained error; a recurrence now names the error. macOS: the wide-screen layout was not checked in CI until PR #73 | PR #64 and #65 comments |
| K-15 | Fixed (2026-10-19): a run around, or with a third body, `mars` or `jupiter` passed validation and then failed. The bundled DE430 ephemeris has the Mars and Jupiter system barycentres, not the planets: a `mars` run stopped the whole process with `SPICE(SPKINSUFFDATA)` (the GUI runs in its own process, so the app closed), and Basilisk has no body named `jupiter`. The schema now offers `mars barycenter` and `jupiter barycenter` (Basilisk gives them the planet's mass and radius) and refuses the two old names with the one to use; a test flies every offered body | A scenario with `mars` or `jupiter` could not be run, and in the GUI closed the app; no result was ever produced with them | `tests/test_central_bodies.py`; HISTORY.md |
| K-16 | Fixed (2026-10-19): a thermal sensor's heat balance used the solar flux at Earth's distance from the Sun on the epoch, whatever the central body. Basilisk's `sensorThermal` assumes 1366 W/m^2 at any distance, and the tool's correction of it took Earth's flux. The flux is now the one at the spacecraft's own distance from the Sun when the run starts (SPICE), for every central body | Thermal sensors around the Sun, Mercury or Venus ran too cold, and around Mars, Jupiter or Eros too hot: around Mars on 2030-01-01 they absorbed 1408 W/m^2 instead of 713 W/m^2. Runs around Earth or the Moon are unchanged | `tests/test_sensor_thermal_flux.py`; HISTORY.md |
| K-17 | Fixed (2026-10-19): coarse sun sensors read the Sun in the planet's shadow. Basilisk's `coarseSunSensor` takes the eclipse as an optional input and, with it unlinked, counts itself fully lit; the tool linked it for thermal sensors and solar panels but not for sun sensors. Both the per-sensor telemetry and the cluster behind the CSS sun-heading estimate now take the spacecraft's eclipse message | In eclipse, sun-sensor telemetry was as in sunlight (template 14: 0.73 in Earth's shadow, now 0.0), and the CSS sun-heading estimate kept the true Sun direction, which real sensors cannot see. Runs that never enter a shadow are unchanged | `tests/test_template_claims.py::test_14_css_estimate_settles_on_the_sun_axis_and_is_lost_in_the_shadow`; HISTORY.md |
| K-18 | Fixed in 1.1.0 (2026-10-20, before its publication): a Monte Carlo batch started from the GUI with `thread_count` 1 (the default, and template 09) failed every run. Basilisk's `MonteCarlo.Controller` calls `signal.signal()` at the start of each case, which Python allows only on a process's main thread, and with one thread the controller runs the cases in the calling process: the GUI's worker `QThread`. The GUI now runs the batch in a spawned child process (`gui/monte_carlo_process.py`); Basilisk is unchanged | In 1.0.0 and the first 1.1.0 candidate, GUI batches with one thread produced no results ("N of N runs failed"). The command line runs batches on its main thread and is not affected; with more than one thread each case runs in a pool process, so GUI batches should not have been affected either (read from the controller, not re-run on 1.1.0). Found by the UI screenshot harness | `tests/gui/test_run_worker.py::test_monte_carlo_worker_runs_a_single_thread_batch`; HISTORY.md |
| K-19 | Limitation (2026-10-20, re-measured 2026-10-22): applying a theme (Settings > Appearance, or a change of the desktop's scheme with System) took about 2.0-2.1 s on a main window with template 23 open, against 6.1 s for the interface before the overhaul on the same machine (`docs/ui/BEFORE_AFTER.md`). Re-measured 2026-10-26 after a fix (every switch set the Fusion style again, a second restyle of every widget): 1.0-1.2 s with the same probe, against 2.0-2.2 s for the code before the fix in the same session; about 0.5 s in a session that has not opened the spacecraft editor dialog. After 1.3.0 (2026-10-26), the hidden spacecraft form kept for messages' titles (about 1,000 widgets) is no longer kept: 359 ms against 532 ms with every template opened, then template 23. The overhaul brief's target is 0.1 s. Qt re-polishes every widget under the application style sheet, shown or not, at a fixed cost per widget (a one-rule sheet takes about 0.3 s of it) | The window does not respond for that time after a theme change | `docs/DECISIONS.md` M1, M9; `docs/ui/BEFORE_AFTER.md` |
| K-20 | Fixed in 1.1.1 (2026-10-20): the 1.1.0 installers built a virtual environment while installing. The setup program stopped before its wizard when no Python 3.11 was on `PATH` ("SpaceMissionStudio needs Python 3.11 or later, which was not found"), and both needed internet access. The `.deb`'s `postinst` also fetched the SPICE kernels as root, into root's own cache (`~/.cache/bsk_support_data` of root), so every other user had no kernels until they downloaded them. The 1.1.1 installers carry their own Python and the data, in the folder Basilisk's `dataFetcher` reads for every user | 1.1.0: no install on a Windows machine without Python 3.11 on `PATH`; no offline install; Linux users other than root had to download the kernels | `packaging/README.md`, "The bundled Python"; HISTORY.md |
| K-21 | Fixed (2026-10-21): `test_autosave.py::test_read_with_no_recovery_file_returns_none` failed now and then on Windows CI (PR #89). A main window an earlier GUI test had left open kept its 30 s autosave timer; pytest-qt processes Qt events after each test's set-up, so the overdue tick wrote that window's scenario into the recovery file the test had just pointed at its temporary folder. Reproduced with a window holding template 22, as in the failure; the test now stops such timers first. A test defect: the app writes its recovery file only where it should | None for users | `docs/ui/TEST_CHANGES.md`; HISTORY.md |
| K-22 | Open (2026-10-21): on Windows CI a test worker crashed with "Windows fatal exception: access violation" in `tests/gui/test_template_wizard.py::test_wizard_is_sized_to_fit_its_own_busiest_page_not_a_flat_default[17_fuel_tank_depletion.json]` (PR #91, job 119157936897, commit `895ebcb96`); the other 3557 tests passed. The Python stack ends in pytest's call of the test, with no frame inside it, so the crash came in native code as the test returned, most likely when Python freed a Qt object whose C++ side Qt had already deleted. Seen once: the other seven whole-suite Windows runs of the same commit passed, and the file passed three times on Linux. The test and the wizard did not change in that PR. Cause not known | A crash of this kind could also end the app on Windows; none has been reported | PR #91 comment; HISTORY.md |
| K-23 | Limitation (2026-10-22): some actions hold the window for longer than the 50 ms the UI overhaul aims at, measured on one Linux container: opening a template 156-463 ms, the first visit to a spacecraft page 456 ms and the spacecraft editor dialog 381 ms (the editor is built at once; re-measured 2026-10-26 with the page built a section at a time: 157-168 ms, against 403 ms for the code before the change in the same session; the dialog used on its own still builds every section), the end of a run 474 ms (the results, the events and the garbage collector's full collections). Re-measured 2026-10-26 after 1.3.0, every template opened in turn: 72-134 ms (median 94 ms), against 82-459 ms (median 111 ms) for the code before the change in the same session; a scenario loaded is checked once, and the titles for spacecraft messages are prepared after start-up in turns of up to 0.13 s, once per process. The end of a run, re-measured 2026-10-26 after 1.3.0 (template 23, the longest stall of a 2 ms heartbeat): the first run of a session 191-244 ms before plotly's figure classes were loaded in a worker after start-up, 27-38 ms after; later runs 31-52 ms before, 31-35 ms after. Most are shorter than before the overhaul on the same machine; opening template 23 a second time measured 222 against 175 ms, one run each | The window does not respond for that time | `docs/ui/BEFORE_AFTER.md`; `docs/DECISIONS.md` M9 |
| K-24 | Fixed when a seed is set, in 2.15.0 (2026-11-23, #313, decision MC-20): the optional `monte_carlo.seed` (scenario schema 7) reseeds each run's NumPy and Python generators from the batch seed and the run index after Basilisk's own seeding and before the draws, so another seed gives other draws and the same seed the same draws (with one process or many; `tests/test_monte_carlo.py`). Without a seed the limitation below remains, on purpose, so that earlier batches and the golden files stay as they are. Limitation (2026-10-28): two Monte Carlo batches of the same scenario draw the same samples. Basilisk's Monte Carlo controller seeds Python's and NumPy's generators with the run number times 10 (`src/utilities/MonteCarlo/Controller.py`, `np.random.seed(simParams.index * 10)`) before a run's dispersions and model seeds are drawn, and disperses every model's seed itself, so `sim_settings.seed` does not change a batch. Not fixed from SpaceMissionStudio: the seeding is in Basilisk's controller, which this project does not change | Without a seed, run k of every batch gets the same dispersed values; within a batch every run differs, as it should. Set a batch seed for an independent batch | Audit E5; `HISTORY.md` "Random seeds" and "Monte Carlo phase B, part 1"; `docs/DECISIONS.md` MC-20, MC-21 |
| K-25 | Limitation (2026-10-28): the installers ship pillow 12.2.0, which has 52 published advisories (pip-audit; 13 fixed in 12.3.0, 39 in 13.0.0). The qualified Basilisk, bsk 2.12.0, requires pillow <= 12.2.0, so no fixed version can be installed with it. Every advisory is about decoding a crafted image file; neither SpaceMissionStudio nor the Basilisk modules it uses decodes an image with pillow (searched: no Image.open, imread or imsave), and pillow is loaded only because Basilisk imports matplotlib. CI's pip-audit accepts exactly these (`packaging/audit-exceptions.txt`) and fails on any other. 2026-11-11: 65 accepted. One, PYSEC-2026-4363 (CVE-2026-112902, fixed in 13.0.0), is about encoding instead: the TIFF encoder can leak process memory into a compressed TIFF written from crafted metadata; neither writes a TIFF, or any image, with pillow (the plots are saved as PNG or SVG by plotly.js); it stopped the 2.7.0 release run and was accepted in #252. 2026-11-15: 67 accepted; two more TIFF ones, both fixed in 13.0.0, were accepted in #260 for the same reason: CVE-2026-128067 (GHSA-xcvg-w56q-r89m), the libtiff encoder reading or writing past a heap buffer when saving a compressed TIFF whose tags override the image size, and CVE-2026-128066 (GHSA-wqgw-9xfh-qf2g), opening a crafted TIFF or EXIF block taking thousands of times its size in memory. The repository's one pillow user, `scripts/prepare_mission_view_textures.py` (a maintainer's script, not shipped), opens two PNG textures after checking their SHA-256 | None found in what the app does; a script block that opened an image with pillow would be exposed | `packaging/audit-exceptions.txt`; HISTORY.md "Dependency security" |
| K-26 | Limitation (2026-11-03): 1.3.1 and earlier do not open a scenario file saved by 2.0.0. They refuse any key they do not know, and 2.0.0 saves fields added since, starting with `sim_settings.seed` (audit E5), which it always writes: 1.3.1's `load_scenario` refused all 31 templates as 2.0.0 saves them ("malformed scenario structure (SimSettings.__init__() got an unexpected keyword argument 'seed')"). 2.0.0 opens every 1.x file (its 31 templates as 1.3.1 saved them load) | A team updates together; a file saved by 2.0.0 and sent to a 1.x user does not open | `CHANGELOG.md` 2.0.0, Who should update |
| K-27 | Limitation (2026-11-04): 2.0.0 does not open a scenario file saved by 2.1.0 that uses a field added since: a mount, model equipment, a stowed pose, a material or maturity, model analyses, face properties, a mass budget or launcher, or an IDM-CIC import (`source_id`, an import record of target `model`). It refuses unknown keys, naming the first ("spacecraft[0].sensors[0]: unexpected field 'mount', not one this version knows"; "spacecraft[0].model.parts[0]: unexpected field 'subsystem'..."). Every new field is written only when set, so a file that uses none opens: checked with 2.0.0's code on the 32 templates as 2.1.0 saves them (31 open; template 32, which uses mounts, is refused). 2.1.0 opens every 2.0.0 file | A file using the new fields, sent to a 2.0.0 user, does not open | `CHANGELOG.md` 2.1.0, Who should update |
| K-28 | Limitation (2026-11-04): the IDM-CIC import is verified against hand calculations on a synthetic model (`tests/test_idm_import.py`), not against IDM-CIC's own mass, centre-of-gravity and inertia report, which no example model stores. Some conventions are assumed and reported in each import's summary (the extruded shapes' corner, sphere and torus centres, inward thicknesses, the tank's straight part). Unsupported shapes (STEP, Collada, pipes, labels, intersections, section planes) become point masses; a typed-in inertia, margins and maturity levels are reported, not applied. The IDM-CIC licence was not available to review; the reader uses the format's published description only | Mass properties of models with assumed or unsupported shapes are approximate, as their summary says | `docs/developer/idm-cic-integration.md` sections 12 and 14; `docs/reference/limitations.md` |
| K-29 | Fixed in 2.1.1 (2026-11-04), reported by the user on 2.1.0: (1) the 3D model editor was a modal dialog of the main window; GNOME attaches a modal dialog to its parent, so dragging the editor dragged the whole application. (2) A scenario opened from a built-in template has the templates' folder as its folder, so the IDM-CIC import wrote its meshes there: "Permission denied" in an installed copy, the repository's templates in a source checkout. (3) That failed import had already added its parts, which named a mesh file the model did not have, so the editor's OK refused the model ("mesh_index must name one of the model's 0 mesh file(s)"). (4) Vizard's battery panel showed watt-seconds ("2520000 / 2520000 W-s" for 700 Wh), the numbers Basilisk's battery message carries. Each fix has a test that fails on 2.1.0's code | 2.1.0: the editor could not be moved apart from the main window; no IDM-CIC import into a scenario opened from a template; a confusing battery unit in Vizard. Workaround in 2.1.0: save a template-based scenario as your own file before importing | `CHANGELOG.md` 2.1.1; `docs/ui/TEST_CHANGES.md`; HISTORY.md |
| K-30 | Limitation (2026-11-05): 2.2.0 does not open a scenario file saved by 2.3.0 in which an IDM-CIC import added devices or set the power budget: its import record's target (`devices`, `power`) is one 2.2.0 does not know ("imports[1].target must be one of ('orbit', 'model')"). Checked with 2.2.0's code on three files saved by 2.3.0 after an IDM-CIC import: the model only (opens), devices added (refused), the power budget set (refused). 2.3.0 opens every 2.2.0 file | A file using them, sent to a 2.2.0 user, does not open | `CHANGELOG.md` 2.3.0, Who should update |

| K-31 | Limitation (2026-11-05): a spacecraft whose body frame origin 2.4.0 put at the centre of gravity (`idm-import --origin cog`) opens and validates in 2.3.0, but a re-import of its IDM-CIC model in 2.3.0, which does not know the recorded origin, puts the model's parts and point masses back in the body element's frame and leaves the other positions (devices, facets, tank) at the centre of gravity's: the spacecraft's positions no longer agree. Checked with 2.3.0's code on the devicesat fixture: after the re-import the centre of mass is 0.447 m from B and the gyro where 2.4.0 put it | A team re-importing in 2.3.0 a file saved by 2.4.0 with the origin at the centre of gravity | `CHANGELOG.md` 2.4.0, Who should update |

| K-32 | Closed in 2.7.0 (#247): the tool no longer starts any external viewer, so none the user chooses runs from it. Before, limitation (2026-11-09): the Vizard AVS Lab publishes has Unity Analytics switched on (its project settings, Unity's analytics libraries, AVS Lab's Unity project ID and Unity's event addresses, read from the program on 2026-11-09; it was not run, so what it sends was not measured). 2.6.0 no longer downloads or looks for Vizard and ignores a copy an earlier version downloaded; a Vizard the user chooses in **Settings > Vizard** is still started, as a separate program outside the tool's network rules. A build of Vizard without analytics was prepared (`0h3xn4/vizard`, branch `sms/telemetry-free-build`) and parked: it needs a Unity licence, and **Results › 3D View** replaces the need | A user who starts AVS Lab's Vizard may send usage data to Unity | security analysis S-05; `CHANGELOG.md` 2.6.0, Removed |

| K-33 | Closed in 2.9.0 (2026-11-16, #264). Limitation from 2026-11-10: the bundled NASA MSFC solar-cycle prediction is the October 2026 issue (`oct2026f10-prd.txt`). The November 2026 issue (`nov2026f10-prd.txt`) was published before 2.7.0 was prepared; it moves the 2030 values a little (January 2030 at the 50th percentile: F10.7 74.1 sfu and Ap 11.3, were 74.2 and 11.5), so adopting it changes every template's drag and golden outputs, and is the owner's decision, not taken for the release. Still so for 2.8.0 (2026-11-15). Closed by the owner's decision on 2026-11-16: 2.9.0 bundles the November 2026 issue; the lifetimes over a year move, and the runs starting after CelesTrak's forecast by millimetres (`docs/changes.md`) | 2.7.0 and 2.8.0: drag after CelesTrak's daily forecast uses the October 2026 prediction unless the study sets its own file (**MSFC prediction**, Scenario › Environment) | `spacemissionstudio/data/spaceweather/README.md`; `CHANGELOG.md` 2.7.0, Known limits |
| K-34 | Limitation (2026-11-16): 2.8.0 does not open a scenario file saved by 2.9.0 that has a thermal model. It refuses unknown keys by name: "malformed scenario structure (spacecraft[0]: unexpected field 'thermal', not one this version knows)". Checked with 2.8.0's code (`db58ba6`) on the 34 templates as 2.9.0 saves them: the 32 without a thermal model open and validate with no message, templates 33 and 34 are refused | A team that shares files with a thermal model updates together | `CHANGELOG.md` 2.9.0, Who should update |
| K-35 | Limitation (2026-11-16): the thermal model is for preliminary design: one isothermal node per part, no shading between parts or by the flexible arrays (the analysis names the faces another part can shade), diffuse grey optics, no fluid loops, phase-change materials or coolers, heater power not drawn from the battery, no electrical power taken out of the cells' sunlight, Earth and Mars only. The library has beginning-of-life optics (three coatings with UV-aged values) and no conductivities: NIST's property fits could not be reached from the build environment, and no other reachable source gave them (T-38). A flexible array's albedo is taken at its initial angle (T-37) | Faces that can be shaded are warmer than they would be; end-of-life optics and conductivities are the user's to give | `docs/reference/limitations.md`, "Thermal analysis"; `docs/developer/thermal-decisions.md` T-06, T-37, T-38 |
| K-36 | Limitation (2026-11-17): 2.9.0 does not open a scenario file saved by 2.10.0 that has an `operations` section. It refuses unknown keys by name: "malformed scenario structure (the scenario: unexpected field 'operations', not one this version knows)". Checked with 2.9.0's code (`8646823`) on the 36 templates as 2.10.0 saves them: the 34 without an `operations` section open and validate with no message, templates 35 and 36 are refused | A team that shares files with an operations plan updates together | `CHANGELOG.md` 2.10.0, Who should update |
| K-37 | Limitation (2026-11-17): the operations planner's models are simpler than the simulation: a one-axis slew model of the controller (planned to half the convergence threshold, O-25), the panel's angle to the Sun from the planned attitude, resources at the geometry's step (O-26); no weather or clouds, conjunctions, a ground network's costs or bookings, or binary telecommands. Without the IERS Earth orientation files the geometry is about 10 km off on the ground (IAU_EARTH in the run), so a window at a limit can hold an image or not: template 35 plans 17 or 18 of 23 images. A week of template 35 takes about 40 s to plan with 20 improvement steps, more than the design's aim (a few seconds), and about ten minutes to fly. The AEM's rotation direction (EME2000 to the body) follows the CCSDS NDM/XML schema and version 1's convention; the Blue Book could not be read to confirm it (O-20) | **Fly and verify** says how far the simplifications matter for a spacecraft; an AEM reader that assumes the other direction gets the inverse rotation | `docs/reference/limitations.md`, "Operations planning"; `docs/developer/operations-planning-decisions.md` O-20, O-25, O-26 |
| K-38 | Limitation (2026-11-17): 2.10.0 and earlier do not open a scenario file saved by 2.11.0, with or without a `budgets` section: 2.11.0 saves every file at schema version 5 (B-01), and an older version refuses a newer schema version. 2.10.0's message: "scenario file is schema_version 5, but this build of SpaceMissionStudio only understands up to version 4 -- upgrade SpaceMissionStudio to open it, or use the version that wrote it." (its `validate` command prints it after "INVALID:" and exits with status 1). Checked with 2.10.0's code (`b074260`) on the 36 templates as 2.11.0 saves them and a file with a `budgets` section: all 37 are refused with that message. 2.11.0 opens and validates the 36 templates as 2.10.0 saves them (version 4) with no message | A team that shares scenario files updates together; a user of 2.10.0 or earlier still opens every file those versions saved | `CHANGELOG.md` 2.11.0, Who should update; `docs/changes.md`, 2026-11-17 |
| K-39 | Limitation (2026-11-17): phase 1 of the System Budget Studio merge. The run does not use the `budgets` section: it still takes `dry_mass_kg` and the power budget's bus load, and the power modes become a load in the simulation only in phase 2. No budget report is exported: each Budgets page copies its table as CSV with the provenance, and `budgets --csv` prints the totals (B-25). An IDM-CIC model gives no converter efficiency, distribution loss or power margin, so `idm-import --budgets` writes them as placeholders, and the power at the source stays unknown until the user sets them (B-08) | The budgets are a design check beside the run, not an input of it | `docs/user-manual/budgets.md`; `docs/developer/system-budget-phase1-design.md`; `docs/developer/system-budget-decisions.md` B-08, B-25 |
| K-40 | Partly met in 2.14.2 (2026-11-23, `29bbdb5`). Was a limitation (2026-11-18): on a slow Windows machine the Budgets area took 50 ms or more of the GUI thread to show; on the Windows CI runner each move into its own window or back took 50 to 81 ms, on Linux 10 to 11 ms. **Cause found:** the Equipment page's word-wrapped note made the area's page report a height for width, and Qt's stacked layout then asked every area's page, the hidden ones too, for its height at each show (on Linux, without the note's height for width, the show took 0.4 ms instead of 8 to 11 ms). `shell.AreaPage` now reports none; the area shows in about 1 ms on Linux, and a move takes 3 to 5 ms. The move test's limit is a plain 50 ms again and passed on the Windows runner (CI run 45109373728); a new test checks that no hidden area is asked its height. **Only partly met:** the backlog item's done criterion was every view under 50 ms on the Windows runner. On the tagged commit `452e164` the move test passed in CI (run 45143562273, Windows runner), but it failed in the release workflow (run 45148067729, attempt 1, job "tests / platforms (windows-latest)"): the 3D View's slowest move took 64.0 ms, and 72.7 ms when the test timed it again, against the 50 ms limit. The run again of the failed jobs (attempt 2) passed. So the 3D View's move sits at the limit on the Windows runner; the cause is not known. The test is not loosened | On the Windows runner, a move of the 3D View into its own window or back can take 64 to 73 ms of the GUI thread (design rule 6: about 50 ms at most). The Budgets area shows quickly | HISTORY.md, "2.12.0 windows and views: breakout windows", "2.14.2: the Budgets area shows quickly" and "Release 2.14.2 published"; `docs/ui/TEST_CHANGES.md`; `docs/DECISIONS.md`; `BACKLOG.md`, "Next release" |
| K-41 | Limitation (2026-11-18): the Windows CI job draws Chromium's compositor in software (`--disable-gpu-compositing`), as it already drew WebGL (SwiftShader), because the runner has no GPU: with the compositor's Direct3D shared images, WebGL contexts were lost at random and a different set of 3D View tests failed in each run. The app's own Chromium flags (`gui/webengine_setup.py`) are unchanged. So CI on Windows does not test the 3D View, its own window or the WebGL recovery with the GPU compositor, and they have not been tried on a Windows machine with a GPU (see also K-12) | Unknown for the 3D View on Windows with a GPU; a lost context is recovered up to five times, then the view says WebGL is gone | `docs/DECISIONS.md`, "Breakout windows" (the owner's decision, 2026-11-18); `.github/workflows/spacemissionstudio.yml` |
| K-42 | Not verified (2026-11-18): the screenshot harness (`scripts/capture_ui_screens.py`) was not run for the new 2D map; a software centre's page for a downloaded `.deb` before it is installed was not seen (it needs Ubuntu 24.04 with a desktop; appstreamcli and desktop-file-validate accept the files); the taskbar icon and its AppUserModelID were not seen on a real Windows machine; Inno Setup compiles the script with the `.ico` only in the Windows installer workflow | The map has no reference screenshot; how the App Center and the Windows taskbar show the app is unknown | HISTORY.md, "Desktop integration", "A new app icon" and "ground tracks, stations and a live 2D map" |
| K-43 | Limitation (2026-11-18): the 2.12.0 windows and views. On Wayland a view's window keeps only its size, not its place; a crash loses the windows' places since the start, as it loses the rest of the layout. The 2D map uses geocentric latitude (at most about 0.19 deg from geodetic) and says so. A run shown while it runs has no temperatures: the thermal analysis runs after the run (T-01, T-42). The app icon's Earth layer takes about 100 ms the first time it is made, once per process at start-up, above the 50 ms target | Small; the map says that its latitude is geocentric, and the user manual says what Wayland keeps | `docs/developer/windows-views-design.md`; `docs/DECISIONS.md`, "Ground tracks, stations and the live map" and "The app icon shows a mission" |
| K-44 | Partly fixed for 2.13.1 (2026-11-20, #302) and 2.14.1 (#310): intermittent crashes around background threads, seen in CI on 2026-11-19. **Cause found and fixed** for the Windows access violation in `_SpaceWeatherWarmUp` ("Garbage-collecting", in the 3D step `test_live_run_3d`) and the Linux segmentation fault in `test_results_widget.py::test_an_export_runs_off_the_gui_thread_with_progress_and_cancel`: Python's garbage collector ran in the worker thread that allocated and destroyed widgets of the GUI thread there. A Linux script with the same stacks crashed five runs in five; with the fix, none in four. Garbage is now collected on the GUI thread only (`gui/background_threads.py`), the start-up warm-ups and a run's first import of the engine hold one lock, and two more event filters keep no Python attribute (the B11 rule). **Cause found and fixed for 2.14.1** (2026-11-22, branch `fix/2.14.1-small`, #310) for "Slot 'EmptyStack::' not found" (the first test of a process) and, by the same mechanism, "Slot 'MainWindow::' not found": Python's collector freed a dropped widget tree one wrapper at a time, and shiboken deleted a child before its owner (a `gdb` backtrace: `gc_collect`, a wrapper's clear, `dict_dealloc`, `QListWidget::~QListWidget`). The child's last signal (an item widget's model reset, a tab widget's `currentChanged`) reached the owner's method after its wrapper was cleared. Reproduced in a fresh interpreter for a list in `EmptyStack` and for a window with view tabs; the CI run of the `MainWindow` message has no log, so that run itself is not proven. These signals now reach their owner through `widgets.connect_while_alive` (a weak reference). **Still open:** the Windows 0xC0000005 of the warm-up check's child process (`test_the_figure_warm_up_loads_what_the_first_plot_needs`, #297; it has no Python worker thread and its stdout was empty); not reproduced. Earlier causes fixed: the toast follower's Python state (B11 follow-up) and stale layout item wrappers (2.13.0) | Unknown; not reported from use of the app. A crash closes the window. The fixed cause could strike whenever a worker ran (a run, an export, the start-up warm-ups). In the app, "Slot not found" was logged as an uncaught error, not a crash; under pytest-qt it fails the test that runs at that moment | `BACKLOG.md`, "Needs human"; HISTORY.md, "2.13.1: background-thread crashes (K-44)", "B11 CI follow-up" and "2.14.1: small fixes" |
| K-45 | Owner decision (2026-11-19): CI's "Windows (MAX Python)" job, in Basilisk's own "Pull Request" workflow, fails the Basilisk framework test `LambertInputValidation.RejectsCollinearityBeforeLambdaAndTimeScaling` on GitHub's runner image 20261111 (MSVC 19.52.37029); it passed on image 20261103 (MSVC 19.51). It fails on every branch, also without a change of SpaceMissionStudio. The owner chose to merge SpaceMissionStudio's pull requests (B10 to B12 and the 2.13.0 release) with this one check red, and never to change the framework. The decision also covers the 2.13.1, 2.14.0, 2.14.1 and 2.15.0 release pull requests, for this framework test only. The "SpaceMissionStudio" workflow, which the release check and the release workflow need, is a separate check | None on SpaceMissionStudio's results: the installers carry Basilisk 2.12.0 from PyPI, not a build of this repository's framework | HISTORY.md, "Release 2.13.0 prepared", "Release 2.14.0 prepared", "Release 2.14.1 prepared" and "Release 2.15.0 prepared"; the audit report's owner decision |
| K-46 | Closed: fixed for 2.13.1 (2026-11-20, #300 and #301). Limitation (2026-11-19): what the UI audit left for later, as users see it. Plots: fixed for 2.13.1 (`ui/plot-items`, #301): the event bands and mode lines are the neutral `chart.band`, the Timeline's model-analysis, thermal and plan events the neutral `chart.event` (not the accent), a y axis spans at least 1e-6 of its largest value (ticks such as "97.03001"), and a wheel's line carries its name from the scenario; the series, the CSV columns and the golden files are unchanged (`tests/gui/test_plot_items.py`). Fixed for 2.13.1 (`ui/small-fixes-2.13.1`, #300): Run › Thermal › Notes wrote "Energy residual [J]" with two or three significant figures (5.11e+03, 4.9e+03); each column now has three (4.90e+03). Budgets › Power's items table scrolled inside itself with the Inspector open at 1280 px; its number headings are now two or three lines and it fits (HISTORY.md, "2.13.1: small window fixes") | – (was small: how the window shows values, not the values) | `CHANGELOG.md` 2.13.1, Fixed; `CHANGELOG.md` 2.13.0, Known limits |
| K-47 | Limitation (2026-11-22): 2.13.1 and earlier do not open a scenario file saved by 2.14.0, with or without `monte_carlo.requirements`: 2.14.0 saves every file at schema version 6 (decision MC-4), and an older version refuses a newer schema version. 2.13.1's message: "scenario file is schema_version 6, but this build of SpaceMissionStudio only understands up to version 5 -- upgrade SpaceMissionStudio to open it, or use the version that wrote it." Checked with 2.13.1's code (`a9af24e`) on the 36 templates as 2.14.0 saves them and template 25 with a requirement: all 37 are refused with that message. 2.14.0 opens and validates the 36 templates as 2.13.1 saves them (version 5) with no message, and saves them again byte for byte as its own templates. A batch summary stays at format 1: 2.13.1 opens one that 2.14.0 writes and ignores its new keys | A team that shares scenario files updates together; a user of 2.13.1 or earlier still opens every file those versions saved | `CHANGELOG.md` 2.14.0, Who should update; `docs/changes.md`, "Scenario schema version 6" |
| K-48 | Limitation (2026-11-22): Monte Carlo phase A. A requirement limits one outcome (at least or at most a value); its Clopper-Pearson bound is one-sided and assumes independent runs with one probability of failure each; there is no requirement on a combination of outcomes and no outcome from another series, and a crashed run counts as not meeting every requirement. A case runs again only with the batch's own, unchanged scenario (MC-17) and the data files it used in the batch (MC-19), and without the live 3D View; the window checks the data files only when the case is built, after the run shown before is cleared; cases of a batch made by 2.13.1 or earlier, and crashed cases, are not checked for data files. Two batches of one scenario still draw the same values (K-24). Fixed for 2.14.1 (#310): the first Monte Carlo batch or case of a process imported pandas on the GUI thread (about 280 ms, above the 50 ms target; for a batch since before 2.14.0, MC-18). The batch's or the case's worker now imports it with `FIRST_IMPORTS` held, and the GUI thread's part of the first start is under 1 ms (258 to 271 ms before; `tests/gui/test_run_worker.py`) | Small; each refusal says why and what to do, and the bound is shown next to the estimate | `docs/developer/monte-carlo-plan.md`; `docs/DECISIONS.md` MC-16 to MC-19; `docs/reference/limitations.md`; HISTORY.md, "2.14.1: small fixes" |
| K-49 | Limitation (2026-11-23): Monte Carlo phase B, part 1, in 2.15.0 (#313). 2.14.2 and earlier do not open a scenario file saved by 2.15.0, with or without a batch seed or a thermal confidence: every file is saved at schema version 7 (decisions MC-20 and MC-22). 2.14.1's and 2.14.2's message: "scenario file is schema_version 7, but this build of SpaceMissionStudio only understands up to version 6 -- upgrade SpaceMissionStudio to open it, or use the version that wrote it." Checked with 2.14.1's code (`7a9a25f`) on the 36 templates as this version saves them, template 25 with a seed and template 34 with a confidence: all 38 are refused with that message. This version opens the 36 templates as 2.14.1 saves them (version 6) with no migration recorded and saves them again byte for byte as its own templates. A batch summary stays at format 1: 2.14.1 opens a seeded batch and a thermal batch with node limits and ignores the new keys. Checked again for the release with 2.14.2's code (the tag `452e164`): it refuses all 37 templates as 2.15.0 saves them with that message, 2.15.0 opens 2.14.2's 36 templates and saves them byte for byte as its own, and 2.14.2 opens a 2.15.0 batch summary of template 37 (seed, requirements, percentiles, sensitivity measure) and ignores the new keys. The batch seed relies on Basilisk 2.12.0's order (seed each run with its index times 10, build, draw; plan risk R1): a Basilisk that seeds otherwise fails every run of a seeded batch with a message, not silently. The node limits' bound is one-sided and assumes independent runs with one probability each; a failed thermal run counts as leaving every range; a thermal batch saved before has no node limits | A team that shares scenario files updates together; a batch without a seed is unchanged | `docs/developer/monte-carlo-plan.md`; `docs/DECISIONS.md` MC-20 to MC-25; `docs/reference/limitations.md`; `docs/changes.md`, "Scenario schema version 7" |
| K-50 | Limitation (2026-11-23): Monte Carlo phase B, part 2, in 2.15.0 (#314). The Sensitivity tab gives one drawn value against one outcome (Spearman's rank correlation, or Pearson's by `monte_carlo.sensitivity_measure`): no partial correlation and no variance-based index, so it does not separate the effects of several drawn values; a pair needs 3 runs and a value that varies ("—" otherwise). The Statistics tab's percentiles (`monte_carlo.percentile_method`, NumPy's linear, Hyndman and Fan's definition 7) describe the runs and carry no confidence; the percentiles shown, 1, 5, 50, 95 and 99 %, are a provisional default (`monte_carlo.percentiles`, source "TBD", decision MC-27) that the owner may change. The final offsets are read to the millimetre for both. The command line prints them since part 3 (K-51). The thermal and operations batches keep their mean ± 3 standard deviation band, now labelled "not a probability bound". The trust check covers the dry mass, the drag and the SRP coefficient while Monte Carlo is on; the starting attitude is not checked (its Euler angles are not unique). The note that a batch is of another scenario needs `archive.provenance.json` (orbit batches only). No file format changed: the batch summary keeps format 1 with three optional keys | Small; each table says what it holds, and the label of the band says what it is not | `docs/developer/monte-carlo-plan.md`; `docs/DECISIONS.md` MC-26 to MC-31; `docs/models/monte-carlo-statistics.md`; `docs/reference/limitations.md` |
| K-51 | Limitation (2026-11-23): Monte Carlo phase B, part 3, in 2.15.0 (#316). The batch report (Export report..., `monte-carlo --report`) reads the settings and dispersions from `archive.provenance.json`'s `monte_carlo_settings`: a batch made by 2.14.2 or earlier has none, and its report says the processes and dispersions are not recorded; a thermal or operations batch lists no dispersions. The command line's Runs table (`--csv`, `--summarize`) is the first spacecraft's (or node's, or profile's); the window exports the others. `--summarize` reads the batch folder only and does not compare the batch with a scenario. `--runs` and `--processes` change one batch only and are recorded in its provenance, not in the scenario file. Template 37 (decision MC-34, provisional) takes about a minute in one process (53 s measured, 30 runs). No scenario field changed: schema version 7 | Small; the report and the command line say what they do not have | `docs/developer/monte-carlo-plan.md`; `docs/DECISIONS.md` MC-32 to MC-35; `docs/reference/limitations.md` |

**Waivers and deviations:** D-01 to D-13 (RD4). D-08 to D-13 are signed; D-01 to D-07
are not (decision 14, H08).

## 6 Operational aspects (G.2.1<6>)

- **Use the installers, or Python 3.14 with Basilisk 2.12.0.**
  The installers carry Python 3.14.8, Basilisk 2.12.0 and the versions
  in `packaging/constraints.txt`. Other Basilisk versions run, but with a
  warning: their results are not covered by the validation.
- **Earth orientation:** the installers carry the IERS-based files as
  current as their build; for later runs, fetch newer ones:
  - the reference-data card on Home at start-up, or **Settings >
    Reference data**, or
  - `spacemissionstudio earth-orientation --fetch`.

  Installed from source, install them before any run with a gravity
  field. Without them, the Earth frame costs about 160 m/day at degree 20.
- **Re-run drag-dependent studies made with earlier versions.** F-07
  changes drag.
- **Re-run propellant budgets made with 1.x** (E2) and lifetimes at the
  critical inclinations (E1).
- **Fetch the current space weather before a drag study** (K-13): the
  bundled file's observations end on 2026-11-18, and its MSFC prediction
  is November 2026's.
- **Update a team together** (K-26, K-27, K-30, K-31, K-34, K-36, K-38,
  K-47).
- **Run script blocks only from scenarios you trust and have read**
  (SUM 9.9).
- **Exchanging OEMs with GMAT R2026a:** use
  `run --oem-interpolation lagrange`, and convert to version 1.0
  (F-08).

## 7 Future evolutions (G.2.1<7>)

Planned, in order:
1. Windows: fix K-22, and run the installers by hand (K-06, K-12).
2. The interface's remaining pauses (K-19, K-23): the spacecraft editor
   built a tab at a time (done for the Scenario editor's page,
   2026-10-26), a theme change that restyles what is shown first.
3. The human actions of RD4: reviews, PA organisation, signatures;
   and the definition of done's timing with an engineer who did not
   build the tool (`docs/definition-of-done.md`).

Dropping the two Basilisk workarounds also depends on Basilisk: they go
once a qualified Basilisk release fixes F-01 and F-07 (H10).
