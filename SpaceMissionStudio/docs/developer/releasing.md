# Releasing

How to cut a SpaceMissionStudio release. The formal procedure is in the
Software Maintenance Plan,
[`compliance/docs/SMP.md`](../../compliance/docs/SMP.md) section 10.6; this
page is the checklist.

**Contents**

1. [Before you start](#1-before-you-start)
2. [Set the version](#2-set-the-version)
3. [Update the records](#3-update-the-records)
4. [Check](#4-check)
5. [Build](#5-build)
6. [Publish](#6-publish)

## 1. Before you start

- The release branch has green CI on every job (`test` and the
  `platforms` job).
- The bundled space weather is current: download the latest CelesTrak
  `SW-All.txt` and NASA MSFC tables into
  `spacemissionstudio/data/spaceweather/` (see the `README.md` there),
  then run the tests. The forecast part ages within months.
- If the release moves to a new Basilisk version, requalify it first
  (SMP section 8, "Requalify a new Basilisk release"): run the full suite
  and the validation against it before changing
  `QUALIFIED_BASILISK_VERSION` in `spacemissionstudio/dependencies.py`.

## 2. Set the version

The version (semantic versioning) is in three places. Change all three
to the same value:

| File | Line |
|---|---|
| `pyproject.toml` | `version = "X.Y.Z"` |
| `spacemissionstudio/__init__.py` | `__version__ = "X.Y.Z"` |
| `packaging/windows/spacemissionstudio.iss` | `#define MyAppVersion "X.Y.Z"` |

The `.deb` reads `spacemissionstudio.__version__`, so it needs no change.

## 3. Update the records

- [`CHANGELOG.md`](../../CHANGELOG.md): move the "Unreleased" entries
  under a new `## X.Y.Z (date)` heading. The release notes are built from
  this section (section 5), so write it for someone deciding whether to
  download:
  - start with one or two paragraphs that say what the release is for:
    they become the notes' summary. The first paragraph is also the
    release's text in software centres (the `.deb`'s AppStream metadata,
    `packaging/metainfo.py`), so it must stand alone;
  - then the list of changes, which becomes "What's new";
  - optionally, after the list, `### Who should update` and
    `### Known limits` (each runs to the next `###` heading): they get a
    section of their own, and the known limits follow the standing ones
    (the unsigned Windows setup, no installer for ARM Linux).
- [`HISTORY.md`](../../HISTORY.md): a short entry for the release.
- [`README.md`](../../README.md): the version badge and the "Version" and
  "Platforms" lines of its status section (they name the release).
- The Software Release Document,
  [`compliance/docs/SRelD.md`](../../compliance/docs/SRelD.md): the
  release's contents, known problems and dependency versions.
- Regenerate the generated documents (see the
  [developer guide](README.md#4-generated-files-regenerate-never-edit)).

## 4. Check

```bash
cd SpaceMissionStudio
python -m ruff check spacemissionstudio tests scripts compliance/tools
QT_QPA_PLATFORM=offscreen python -m pytest tests -q -n auto
for t in check_drds build_icd_schema build_sdd_components build_test_specs build_traceability; do
  python compliance/tools/$t.py
done
git diff --exit-code -- compliance/docs
```

## 5. Build

**The release files are built in CI.** Pushing the tag (section 6) starts
the workflow `.github/workflows/spacemissionstudio-release.yml` ("SpaceMissionStudio
release"). On GitHub's runners it:

- checks that the tag matches the version files and that the CHANGELOG
  has a section for the version;
- runs the SpaceMissionStudio workflow on the tagged commit (job
  `tests`): lint, the document checks, the whole test suite on Linux and
  Windows and pip-audit on every pinned package. Nothing is attached
  unless it passes;
- builds the wheel, sdist and the self-contained `.deb` (the bundled
  Python of `packaging/bundle_python.py`) on Linux; checks what the `.deb`
  gives the desktop: the desktop entry (`desktop-file-validate`), the icon
  at every hicolor size and the AppStream metadata (`appstreamcli validate
  --no-net`, which fails on a warning); installs the `.deb`
  with the network cut off and runs the installed tool offline: version,
  support data, every template validated, template 01 run from the
  bundled kernels, the Earth orientation files found and the main window
  opened in Inter;
- builds the bundled Python on Windows, then the setup program around
  it, installs it silently and runs it the same way;
- takes each installer's software bill of materials
  (`SPACEMISSIONSTUDIO_SBOM.cdx.json`, written by `bundle_python.py`;
  every package with the file installed and its SHA-256) and attaches it
  beside the installer as `spacemissionstudio_X.Y.Z_amd64.cdx.json` and
  `spacemissionstudio-X.Y.Z-setup.cdx.json`;
- downloads the complete source of the Qt and PySide6 libraries the
  installers carry (`packaging/legal/qt-sources.json`), checked against
  the size and SHA-256 Qt publishes, with `SHA256SUMS-sources`, and signs
  a build provenance of every built file (Sigstore; `gh attestation
  verify <file> --repo 0h3xn4/basilisk_space-mission-studio`);
- writes `SHA256SUMS-linux` and `SHA256SUMS-windows` (the bills of
  materials included), checks every file against them and attaches all
  of them, and the source archives, to the tag's release. A release
  that does not exist yet is created as a draft. An existing release
  keeps its notes unless they are empty, and its files are replaced.
- writes the notes with `packaging/release_notes.py`, in a fixed layout:
  summary, who should update, downloads with their sizes, install or
  upgrade, how to check a download (with the installers' SHA-256), what's
  new, what the installers contain (the Python, Basilisk and PySide6
  versions and the bundled space weather, read from this checkout), how
  the files were checked (linking the run), and the known limits. The
  text comes from the CHANGELOG section (section 3); a release without
  one gets no notes and the job fails. To see the notes before tagging:
  `python3 packaging/release_notes.py --version X.Y.Z --files <folder
  with the four packages> --run-url <any URL>`.

Actions > "SpaceMissionStudio release" > Run workflow, with the tag, runs
it again for an existing tag. A pull request that changes the workflow
runs the tests, the build and the install jobs for its own commit and
attaches nothing.

To check a build locally before tagging, from the `SpaceMissionStudio`
folder:

| Artifact | Command | Output |
|---|---|---|
| Wheel (any platform) | `packaging/build_wheel.sh` (Windows: `packaging\build_wheel.ps1`) | `dist/spacemissionstudio-X.Y.Z-py3-none-any.whl` |
| Linux installer | `packaging/build_deb.sh` (about 8 minutes; downloads CPython, the packages and the support data) | `dist/spacemissionstudio_X.Y.Z_amd64.deb` |
| Windows installer | Windows only (`bundle_python.py --platform windows`, then Inno Setup): the release workflow above, or Actions > "SpaceMissionStudio Windows installer" > Run workflow | `spacemissionstudio-X.Y.Z-setup.exe` |

[`packaging/README.md`](../../packaging/README.md) explains each one and
what has been verified where.

## 6. Publish

- Check the commit first: Actions > "SpaceMissionStudio release check" >
  Run workflow, on `develop` (`.github/workflows/spacemissionstudio-release-check.yml`).
  It changes nothing. It fails unless CI passed on the commit at
  `develop`'s head, pip-audit finds no vulnerability that
  `packaging/audit-exceptions.txt` does not accept (today's advisories),
  the version files agree, the CHANGELOG's newest section is that version
  dated today, no Unreleased entries are left out, the tag does not exist
  yet and the notes render (`packaging/release_check.py`, which also runs
  locally). Its summary names the commit and gives the two commands
  below with it filled in. Tag that commit, once.
- Tag it, preferably with Actions > "SpaceMissionStudio tag release" >
  Run workflow, giving the version (`.github/workflows/spacemissionstudio-tag-release.yml`;
  the assistant can start it when asked to tag). It runs the release
  check above and stops on any failure; otherwise it tags exactly the
  commit the check passed and starts the release workflow for the tag
  (a tag pushed with a workflow's token starts no workflow by itself).
  With **publish** ticked, the release workflow publishes the release
  once every file is built, installed, checked against its checksum and
  attached; any failure leaves it a draft (or creates none). Without it,
  the release stays a draft for a person to check and publish. The owner
  asked for publishing to be automatic from 2.8.0 on (2026-11-15), and
  the assistant starts the workflow with it when asked to publish.
  If a tag ruleset (Settings > Rules > Rulesets) restricts creating
  tags, GitHub Actions needs to be on its bypass list. Or tag by hand:
- Tag the release commit (`develop` after the release pull request is
  merged) and push the tag:

  ```bash
  git tag -a spacemissionstudio-vX.Y.Z <commit> -m "SpaceMissionStudio X.Y.Z"
  git push origin spacemissionstudio-vX.Y.Z
  ```

  The release workflow (section 5) builds, checks and attaches the files
  to a draft release titled "SpaceMissionStudio X.Y.Z". If the tests, the
  Linux or the Windows job fail, nothing is attached; fix the cause and run the
  workflow again for the tag.
- Read the draft on
  <https://github.com/0h3xn4/basilisk_space-mission-studio/releases>: the
  eleven files (the wheel, the sdist, each installer and its bill of
  materials, `SHA256SUMS-linux` and `SHA256SUMS-windows`, and from 2.7.0
  the two Qt source archives and `SHA256SUMS-sources`), and the notes, which say which platform has which file and
  name the workflow run that installed them. Then publish it.
- After publishing, download the assets from the release and run
  `sha256sum -c SHA256SUMS-linux` and `sha256sum -c SHA256SUMS-windows`.
- Update the records that name the release: the Software Release
  Document (status, baseline commit), `compliance/human_actions.md` H05,
  and the compliance assessments (then run `compliance/tools/build_matrix.py`).

**Tag name: use `spacemissionstudio-vX.Y.Z`, not `vX.Y.Z`.** This fork
keeps Basilisk's own workflows, and a `v*` tag starts two of them:
`publish-container.yml`, which pushes a *Basilisk* image tagged with the
version and `latest` to this repository's GHCR, and `publish-wheels.yml`,
which builds Basilisk wheels and tries to upload them to PyPI. Both ran
for a `v3.0.0` tag of the earlier numbering: PyPI refused the upload (no trusted publisher for
the fork), and the container run was cancelled after its arm64 image had
been pushed. A `spacemissionstudio-v*` tag starts neither. The
SpaceMissionStudio workflow also runs on a tag push, on the commit
`develop` already passed.

**Releases.** The tool was renewed on 2026-10-14 and its numbering
restarted at 1.0.0; the releases and tags of the earlier numbering
(1.0.0 to 3.0.0) were removed. 1.0.0 is a Linux release: the wheel,
sdist, `.deb` and `SHA256SUMS-linux`, without the Windows setup program
(SRelD K-14). `pip` and `apt` see 1.0.0 as older than the earlier
3.0.0, so the release notes tell users of that build to remove it first.
It was published on 2026-10-14: tag `spacemissionstudio-v1.0.0` on
`f288e0c73`, and GitHub's SHA-256 digest of each attached file equals
the file built and installed for it (SRelD, status).

1.1.0 was prepared on 2026-10-19 by the same checklist, again for Linux,
and rebuilt on 2026-10-20 with the fix of SRelD K-18:
the version set in the three files, the CHANGELOG section, the SRelD
(issue 6), the build, and the `.deb` installed as an upgrade over 1.0.0
(`packaging/README.md`). On 2026-10-20 the user chose to release from
`develop`, which by then held the first step of the UI overhaul (M1, the
new look), so 1.1.0 includes it: its CHANGELOG section and SRelD issue 8
say so, and the files were built and installed again. A first tag, made
before those records on commit `c931ccd4d`, is replaced by one on the
merge of that pull request. Merging, tagging (`spacemissionstudio-v1.1.0`)
and publishing are the user's. 1.1.0 was published on 2026-10-20: tag
`spacemissionstudio-v1.1.0` on `1f8ad1663`, its six files (the first
with a Windows setup program) built and attached by the release workflow.

1.1.1 was prepared on 2026-10-21 by this checklist: the self-contained
installers of PR #89 and no change to the app. The space weather is the
copy refreshed for 1.1.0 (observations to 2026-10-18), one release
earlier. It was published on 2026-10-21: tag `spacemissionstudio-v1.1.1`
on `57a54ae92`, its six files built, installed and attached by the
release workflow. A first tag and release were deleted and the tag
pushed again; a release created by hand before the workflow has attached
its files is public with none, so push the tag and let the workflow
create the draft.

1.2.0 was prepared on 2026-10-21 by this checklist: starting a mission
from scratch (PR #92) and the end of macOS support (PR #92, #93), with
no change to what the tool computes. The space weather is again the copy
refreshed for 1.1.0 (observations to 2026-10-18, updated 2026-10-19), two
days old. It is the first release whose notes the release workflow writes
with `packaging/release_notes.py`. It was published on 2026-10-21: tag
`spacemissionstudio-v1.2.0` on `c92f90040`, its six files built,
installed and attached by the release workflow, which also wrote the
notes because the release had none. The release had been published by
hand before the workflow ran, so it was public without files for
13 minutes: push the tag first and publish the draft the workflow makes.

1.3.0 was prepared on 2026-10-23 by this checklist: the UI overhaul (PRs
#96 to #107), with no change to what the tool computes (the engine, the
schema, the command line and the exported files are unchanged; the
exports are tested byte for byte). The space weather was refreshed for
it on 2026-10-26 (observations to 2026-10-24, updated 2026-10-25); NASA
MSFC's October 2026 prediction is still the latest issue (checked on
2026-10-26: the shipped copy matches the published file but for
whitespace). Its notes come from `CHANGELOG.md` 1.3.0, which has a
summary, "Who should update" and "Known limits". It was published on
2026-10-26: tag `spacemissionstudio-v1.3.0` on `7bdfa21ac`, its six files
built, installed and attached by the release workflow, which wrote the
notes. As with 1.2.0, the release was published by hand before the
workflow ran, so it was public without files for 12 minutes, and the
CHANGELOG heading was dated after the tag: date the heading, then push
the tag, then publish the draft the workflow makes.

1.3.1 was prepared on 2026-10-26 by this checklist: three changes that
shorten the window's pauses (PRs #116 to #118), with no change to what
the tool computes. The space weather is 1.3.0's (observations to
2026-10-24, updated 2026-10-25). The CHANGELOG heading is dated
2026-10-26, the day it was prepared: if the tag is pushed on another
day, correct the date first. It was published on 2026-10-27: tag
`spacemissionstudio-v1.3.1` on `081f74079`, its six files built,
installed and attached by the release workflow, which wrote the notes.
The tag was pushed the day after the heading's date, so `develop`'s
heading was corrected to 2026-10-27 afterwards (the tagged CHANGELOG
reads 2026-10-26). For the third release running, the release was
published four seconds after the tag was pushed, before the workflow
started, so it was public without files or notes for 12 minutes: push
the tag, wait for the workflow's draft (about 13 minutes), read it, then
publish it.

2.0.0 was prepared on 2026-11-03 by this checklist: the audit of
2026-10-27 and the transparency work (PRs #120 to #205), and Python 3.14
only. Two steps could not be done as written. The space weather was not
refreshed: CelesTrak reset every connection from the environment the
release was prepared in, so it is 1.3.0's (observations to 2026-10-24),
said in the CHANGELOG's known limits and SRelD K-13. And by the user's
instruction of the day, the release pull request was merged without
asking, but the tag could not be pushed from that environment (its git
proxy refused tags), so the user tagged and published. It was published
on 2026-11-03 at 12:30 UTC: tag `spacemissionstudio-v2.0.0` on
`6608682a3`, with the user's own notes, which the workflow kept. Published before the workflow
started, it was public without files for 32 minutes, until the workflow
attached them at 13:02, the fourth release so. Push the tag first,
or save the release as a draft and run the workflow on its tag, and
publish only once the files are there.

2.1.0 was prepared on 2026-11-04 by this checklist: the analyses built
on the 3D model (#209), the 3D model editor's equipment, stowed,
materials, budget and launcher tabs (#210, #211) and the IDM-CIC import
(#212). The space weather again could not be refreshed (CelesTrak reset
the connection), so it is 1.3.0's, said in the known limits and SRelD
K-13. The release pull request (#213) was merged once CI was green, and
the user tagged and published (the environment cannot push tags). It was
published on 2026-11-04 at 14:57 UTC: tag `spacemissionstudio-v2.1.0` on
`4346b4189`, with notes written for it, which the workflow kept.
Published two seconds before the workflow started, it was public without
files for 37 minutes, until the workflow attached them at 15:34, the
fifth release so. Push the tag, wait for the workflow's draft (about 37
minutes now that it runs the whole suite on both platforms), then edit
its notes and publish.

2.1.1 was prepared on 2026-11-04 by this checklist, a patch release with
the fixes reported on 2.1.0 (#215: the 3D model editor as a window of its
own, the IDM-CIC import from a template, Vizard's battery in watt-hours).
No scenario field, template or golden file changed. The space weather is
still 1.3.0's (CelesTrak reset the connection again, K-13). The release
pull request (#216) was merged once CI was green, and the user tagged
`spacemissionstudio-v2.1.1` on `a6413c1cb` and published it on
2026-11-04 at 19:58 UTC, with notes written for it, which the workflow
kept. Published two seconds before the workflow started, it was public
without files for 35 minutes, until the workflow attached them at 20:33,
the sixth release so. To avoid it: push the tag, or save the release as
a draft, wait for the files (about 35 minutes), then publish.

2.2.0 was prepared on 2026-11-05 by this checklist: CCSDS orbit files in
the app (#218) and more windows of their own, a minor release because it
adds features. No scenario
field, template or golden file changed. The space weather is still
1.3.0's (CelesTrak reset the connection again, K-13). The release pull
request (#219) was merged once CI was green, and the user tagged
`spacemissionstudio-v2.2.0` on `fa9d2b6b9` and published it on
2026-11-05 at 08:55 UTC, with notes written for it, which the workflow
kept. Published two seconds before the workflow started, it was public
without files for 38 minutes, until the workflow attached them at 09:34,
the seventh release so. To avoid it: push the tag, or save the release as
a draft, wait for the files (about 40 minutes), then publish.

2.3.0 was prepared on 2026-11-05 by this checklist: a Walker
constellation that holds its spacing (#220) and the satellite's
components from IDM-CIC (#222 devices, #223 power, #224 properties), a
minor release because it adds features. No template or golden file
changed; the scenario format gained the import record targets `devices`
and `power`, which 2.2.0 refuses (K-30). The space weather is still
1.3.0's (CelesTrak reset the connection again, K-13). The release pull
request (#225) was merged once CI was green, and the user tagged
`spacemissionstudio-v2.3.0` on `3f11a0227` and published it on
2026-11-05 at 16:17 UTC, with notes written for it, which the workflow
kept. Published two seconds before the workflow started, it was public
without files for 39 minutes, until the workflow attached them at 16:56,
the eighth release so. To avoid it: push the tag, or save the release as
a draft, wait for the files (about 40 minutes), then publish.

2.4.0 was prepared on 2026-11-05 by this checklist: device axes read
from the IDM-CIC model's shapes (#227) and, added on the release branch
at the user's question, the body frame's origin at the centre of gravity,
a minor release because it adds features. No template, golden file or scenario field changed; 2.3.0
opens the files 2.4.0 saves (checked with 2.3.0's code on a file with
devices imported along the model's axes). The space weather is still
1.3.0's (CelesTrak refused the connection again, K-13). The release pull
request (#228) was merged once CI was green, and the user tagged
`spacemissionstudio-v2.4.0` on `ac4b90065` and published it on
2026-11-05 at 20:58 UTC, with notes written for it, which the workflow
kept. Published two seconds before the workflow started, it was public
without files for 35 minutes, until the workflow attached them at 21:33,
the ninth release so. To avoid it: push the tag, or save the release as
a draft, wait for the files (about 40 minutes), then publish.

2.5.0 was prepared on 2026-11-08 by this checklist: thrusters from the
IDM-CIC model (#230) and the JSON page as a code editor (#231, #232),
with the documentation refresh and the 2.4.0 publication record (#229),
a minor release because it adds features. No template, golden file or
scenario field changed; 2.4.0 opens the files 2.5.0 saves (checked with
2.4.0's code on a file with a thruster imported at the centre of
gravity). The space weather is still 1.3.0's (CelesTrak refused the
connection again, K-13). The release pull request (#233) was merged once
CI was green, and the user tagged `spacemissionstudio-v2.5.0` on
`1951a028c` and published it on 2026-11-08 at 19:29 UTC, with notes
written for it, which the workflow kept. Published one second before the
workflow started, it was public without files for 33 minutes, until the
workflow attached them at 20:01, the tenth release so. To avoid it: push
the tag, or save the release as a draft, wait for the files (about 35
minutes), then publish.

2.6.0 was prepared on 2026-11-09 by this checklist: network use enforced
and offline mode (#235), the network audit (#236), hash-checked
installers with a bill of materials (#237) and the 3D View in place of
the Vizard download (#239), with the documentation refresh and the 2.5.0
publication record (#234), a minor release because it adds features.
The first release whose files include each installer's bill of
materials (`*.cdx.json`), listed in `SHA256SUMS-*`. No template, golden
file or scenario field changed; 2.5.0 opens the files 2.6.0 saves
(checked with 2.5.0's code on the 32 templates as 2.6.0 saves them). The
space weather is still 1.3.0's (CelesTrak reset the connection again,
K-13). The release pull request (#240) was merged once CI was green, and
the user tagged `spacemissionstudio-v2.6.0` on `dcbb95e09`, pushed the
tag and published the release on 2026-11-10 at 06:51 UTC, with notes
written for it, which the workflow kept. The release had been saved as a
draft first, as advised, but was published about two minutes after the
tag, so it was public without files for 38 minutes, until the workflow
attached its eight files at 07:29, the eleventh release so. To avoid
it: keep the draft until the workflow has attached the files (about 40
minutes: the full suite runs on both platforms first), then publish.

2.7.0 was prepared on 2026-11-10 by this checklist: the 3D View as a
renderer (#248) that can show a run live (#249), the start on Home with
no scenario open (#246), the external viewer support removed (#247),
and the legal groundwork (#241 to #243, #245), with the 2.6.0
publication record and the repository's new name (#244), a minor release
because it adds features. The first release under the EUPL-1.2, and the
first whose files include the Qt and PySide6 source archives with
`SHA256SUMS-sources` (eleven files) and a signed build provenance of
each built file. No golden file changed and no scenario field was added
(the templates lost only the external viewer's fields); 2.6.0 opens the
files 2.7.0 saves (checked with 2.6.0's
code on the 32 templates as 2.7.0 saves them). The space weather was
refreshed: CelesTrak answered for the first time since 1.3.0
(observations to 2026-11-09). NASA MSFC's November 2026 prediction was
not adopted, because it changes every template's drag (SRelD K-33).
It was published on 2026-11-11 at 18:25 UTC, after a day of detours
(SRelD issue 34). A first tag on #250's merge was deleted while its run
was starting. The release was then published from the web, which made
the tag on #251's merge, and was public without files; its run passed
every test and built both installers but failed at pip-audit on a pillow
advisory published that day (accepted in #252). The user deleted the
tag (the release became a draft and kept its notes), tagged #252's
merge `ae5525cb8`, the workflow attached the eleven files at 18:00
([run 43067454786](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/43067454786)),
and the draft was published after them. It had been public without
files from 09:31 until the tag was deleted. Two lessons: tag only once, the commit
the release pull request's last CI ran on; and since advisories appear
daily, run the pip-audit step locally just before tagging, so a new
advisory is handled before the tag rather than after.

2.8.0 was prepared on 2026-11-15 by this checklist: the menu bar,
readable lists, values as sheets and dialogs that fit (#257), calm by
default and the plot list in levels (#259), notes as lists and the
remaining values as sheets (#261), with the release check and tag
workflows (#255), the ECSS clause references (#254), the 2.7.0
publication record (#253), private vulnerability reporting (#256),
tornado 6.6.1 and two pillow advisories accepted (#260), and the
documentation's screenshots retaken; a minor release because it adds
features. No golden file, template, scenario field, command or exit
status changed; 2.7.0 opens the files 2.8.0 saves (checked with 2.7.0's
code on the 32 templates as 2.8.0 saves them). The space weather was
refreshed (observations to 2026-11-14); CelesTrak reset the first two
connections and answered the third. NASA MSFC's November 2026
prediction is still not adopted (SRelD K-33). The CHANGELOG's heading
carries 2026-11-16, the day of the tag, not the day it was prepared: the
release check wants the tag's day, and the release pull request's CI and
then `develop`'s take about two hours, past midnight UTC.
It was published on 2026-11-16 at 00:35 UTC, the first release tagged and
published from the Actions tab with **publish** on (SRelD issue 36): the
tag workflow ([run 43778375893](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/43778375893)) passed the
release check on `db58ba6`, #262's merge, and tagged it at 00:07; the
release workflow ([run 43778461245](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/43778461245)) built,
installed and checked every file, attached the eleven and published the
release 29 minutes later. It was never a public release without files.

2.9.0 was prepared on 2026-11-16 by this checklist: the spacecraft
thermal analysis with templates 33 and 34 (#265), NASA MSFC's November
2026 prediction (#264) and the 2.8.0 publication record (#263); a minor
release because it adds a feature and an optional scenario field
(`thermal`, schema version still 4). 2.8.0 opens the files 2.9.0 saves
except those with a thermal model, which it refuses by name (checked
with 2.8.0's code on the 34 templates as 2.9.0 saves them: 32 open with
no message, 33 and 34 refused). The space weather was not refreshed:
CelesTrak reset all three connections, so 2.9.0 carries 2.8.0's file
(observations to 2026-11-14).
It was published on 2026-11-16 at 19:03 UTC, tagged and published from
the Actions tab with **publish** on (SRelD issue 38): the tag workflow
([run 43930553885](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/43930553885)) passed the release
check on `8646823`, #266's merge, and tagged it at 18:37; the release
workflow ([run 43930715195](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/43930715195)) built, installed
and checked every file, attached the eleven and published the release 26
minutes later. It was never a public release without files.

2.10.0 was prepared on 2026-11-17 by this checklist: mission operations
planning with templates 35 and 36 (#268), the upstream Basilisk sync
(#258) and the 2.9.0 publication record (#267); a minor release because
it adds a feature and an optional scenario field (`operations`, schema
version still 4). 2.9.0 opens the files 2.10.0 saves except those with
an `operations` section, which it refuses by name (checked with 2.9.0's
code on the 36 templates as 2.10.0 saves them: 34 open with no message,
35 and 36 refused). The space weather was not refreshed: CelesTrak reset
the connection, so 2.10.0 carries 2.8.0's file (observations to
2026-11-14). The sync changed upstream Basilisk's files in the
repository, not the Basilisk 2.12.0 the installers carry.
It was published on 2026-11-17 at 10:37 UTC, tagged and published from
the Actions tab with **publish** on (SRelD issue 40): the tag workflow
([run 44060467004](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/44060467004)) passed the release
check on `b074260`, #269's merge, and tagged it at 09:59; the release
workflow ([run 44060591211](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/44060591211)) built, installed
and checked every file, attached the eleven and published the release 38
minutes later. It was never a public release without files.

2.11.0 was prepared on 2026-11-17 by this checklist: phase 1 of the
System Budget Studio merge, the equipment list and the static power
budget (#273) and the Budgets area in the window (#274), with the merge
plan (#270), phase 0 (#272) and the 2.10.0 publication record (#271); a
minor release because it adds features and a scenario section
(`budgets`). The scenario file moves to schema version 5, so 2.10.0 and
earlier refuse every file 2.11.0 saves, by its version (checked with
2.10.0's code on the 36 templates as 2.11.0 saves them and a file with a
`budgets` section: all refused, "scenario file is schema_version 5, but
this build of SpaceMissionStudio only understands up to version 4");
2.11.0 opens the files 2.10.0 saves (the 36 templates, with no message).
The space weather was not refreshed: CelesTrak reset the connection, so
2.11.0 carries 2.8.0's file (observations to 2026-11-14).
It was published on 2026-11-17 at 17:54 UTC, tagged and published from
the Actions tab with **publish** on (SRelD issue 42). The first tag
workflow run ([run 44123360812](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/44123360812)), started
at 16:13, stopped at the release check because CI on `d387dc5`, #275's
merge, had not finished yet; it tagged nothing. Once CI had passed, the
second ([run 44133160433](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/44133160433)) passed the
release check on `d387dc5` and tagged it at 17:06; the release workflow
([run 44133393083](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/44133393083)) built, installed and
checked every file, attached the eleven and published the release 48
minutes later. It was never a public release without files.

2.12.0 was prepared on 2026-11-18 by this checklist: the 2.12.0 windows
and views (`windows-views-design.md`): the thermal results (#278), the
breakout windows (#281), the ground tracks, stations and live 2D map
(#282), the desktop integration (#276) and the new app icon (#280),
with UI audit batch B1 (#283) and the 2.11.0 publication record (#279);
a minor release because it adds features. No file format changed: the
scenario schema is still version 5 and `schema/` is unchanged since
2.11.0. Checked with 2.11.0's code (the tag, `d387dc5`): 2.11.0 and
2.12.0 save the 36 templates and a file with a `budgets` section byte
for byte the same, and each version opens and validates all 37 files of
the other with no message. The space weather was not refreshed (not
tried), so 2.12.0 carries 2.8.0's file (observations to 2026-11-14).
It was published on 2026-11-18 at 09:01 UTC, tagged and published from
the Actions tab with **publish** on (SRelD issue 44). CI on the release
pull request first failed the breakout windows' timing test (a full
garbage collection in one move); the test was fixed in the pull request
(`docs/ui/TEST_CHANGES.md`). After #284's merge, CI passed on `2718e78`
([run 44260636345](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/44260636345)); the tag workflow
([run 44265090291](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/44265090291)) passed the release check and tagged it
at 08:14; the release workflow ([run 44265254780](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/44265254780)) built,
installed and checked every file, attached the eleven and published the
release 47 minutes later. It was never a public release without files.

2.13.0 was prepared on 2026-11-19 by this checklist: the UI audit's
batches B2 to B12 (#285 to #295), with the B11 follow-up (the thermal
page's least width and the toast follower), a minor release because it
adds features to the window (the Settings page's controls, the command
palette's shortcuts and reasons, the About window). No file format changed: `schema/` changed
only in two comments since 2.12.0, and the templates not at all.
Checked with 2.12.0's code (the tag, `2718e78`): 2.12.0 and 2.13.0 save
the 36 templates and a file with a `budgets` section byte for byte the
same, and each version opens and validates all 37 files of the other
with no message. The space weather was refreshed: CelesTrak answered the
first connection (observations to 2026-11-18, updated 2026-11-19), and
NASA MSFC's November 2026 prediction is still the latest issue (the
published file equals the bundled one but for whitespace). The golden
outputs pass unchanged. The documentation's screenshots were retaken
with `scripts/capture_screenshots.py`; the two dialogs at their earlier
sizes on a 2560 x 1440 offscreen screen, because the offscreen platform's
800 x 800 screen cuts them since B1. CI's "Windows (MAX Python)" job, a
Basilisk framework job, fails one framework test on the runner image
20261111 (MSVC 19.52); by the owner's decision of 2026-11-19 the release
pull request is merged with that check red (SRelD K-45).
It was published on 2026-11-20 at 02:02 UTC, tagged and published from
the Actions tab with **publish** on (SRelD issue 46). After #296's
merge, CI on `develop` failed one Windows test twice: a stale layout item
wrapper was returned for a new window. #297 fixed the cause before any
tag. It was merged after midnight UTC, so #298 dated the CHANGELOG
heading 2026-11-20 for the release check. CI passed on `c3eeb85`
([run 44652910748](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/44652910748)); the tag workflow
([run 44653376716](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/44653376716)) passed the release check and tagged
it at 01:25; the release workflow ([run 44653476286](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/44653476286))
built, installed and checked every file, attached the eleven and
published the release 37 minutes later. It was never a public release
without files.

2.13.1 was prepared on 2026-11-20 by this checklist, a patch release
with three fixes: one cause of the background-thread crashes removed
(#302, SRelD K-44, partly fixed), the small plot items (#301) and small
window fixes (#300, both K-46), with the 2.13.0 publication record
(#299). #302 was still in CI, so the release branch starts from its
head `ed436170f7` and the release pull request carries #302 until #302
merges. No file format changed: `schema/`, the templates, the golden
files and `packaging/` are as at the 2.13.0 tag `c3eeb85`. The space
weather was not refreshed: 2.13.0 refreshed it the day before
(observations to 2026-11-18). By the owner's decision (SRelD K-45), the
release pull request may be merged with CI's "Windows (MAX Python)" job
red, for the Basilisk framework test `LambertInputValidation` only.
It was published on 2026-11-20 at 16:50 UTC, tagged and published from
the Actions tab with **publish** on (SRelD issue 48). #303 was merged at
14:50 UTC; CI passed on `a9af24e` ([run 44757407951](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/44757407951));
the tag workflow ([run 44768019598](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/44768019598)) passed the release
check and tagged it at 15:55; the release workflow
([run 44768147987](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/44768147987)) built, installed and checked every
file, attached the eleven and published the release 55 minutes later.
It was never a public release without files.

2.14.0 was prepared on 2026-11-22 by this checklist: Monte Carlo phase A
(`monte-carlo-plan.md`), with outcomes per run, requirements with the
Clopper-Pearson bound and the draws of crashed runs (#306), one case run
again with the batch's data folders and data files (#307), the plan
(#305) and the 2.13.1 publication record (#304); a minor release
because it adds features and the optional scenario field
`monte_carlo.requirements`. The scenario file moves to schema version
6, so 2.13.1 and earlier refuse every file 2.14.0 saves, by its version
(checked with 2.13.1's code, the tag `a9af24e`, on the 36 templates as
2.14.0 saves them and a file with a requirement: all 37 refused,
"scenario file is schema_version 6, but this build of SpaceMissionStudio
only understands up to version 5"); 2.14.0 opens the files 2.13.1 saves
(the 36 templates, with no message). The golden files are
byte-identical. The space weather was not refreshed: CelesTrak reset all
three connections, so 2.14.0 carries 2.13.0's file (observations to
2026-11-18). By the owner's decision (SRelD K-45), the release pull
request may be merged with CI's "Windows (MAX Python)" job red, for the
Basilisk framework test `LambertInputValidation` only.
It was published on 2026-11-22 at 20:07 UTC, tagged and published from
the Actions tab with **publish** on (SRelD issue 50). #308 was merged at
18:34 UTC. CI on `1b4060c` first failed before any test, because the
ITU server answered HTTP 404 for the ITU-R P.676-13 data file; the one
re-run passed ([run 45055869064](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/45055869064)). The tag workflow
([run 45061002580](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/45061002580)) passed the release check and tagged
it at 19:30; the release workflow ([run 45061087902](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/45061087902))
built, installed and checked every file, attached the eleven and
published the release 37 minutes later. It was never a public release
without files.

2.14.1 was prepared on 2026-11-22 by this checklist, a patch release
with the fixes of #310: pandas imported in the batch's or the case's
worker, not on the GUI thread (SRelD K-48), the cause of "Slot '...::'
not found" fixed with weak-reference connections (K-44), CI downloads
tried again, and the SIL stress workflow given CI's WebGL set-up; with
the 2.14.0 publication record (#309). No file format changed: the
scenario file is still at schema version 6, and `schema/`, the
templates and the golden files are as at the 2.14.0 tag `1b4060c`. The
space weather was not refreshed: CelesTrak reset all three connections,
so 2.14.1 carries 2.13.0's file (observations to 2026-11-18). The
CHANGELOG heading carries 2026-11-23, the UTC day the tag will be made,
because the release check wants the tag's day. By the owner's decision
(SRelD K-45), the release pull request may be merged with CI's "Windows
(MAX Python)" job red, for the Basilisk framework test
`LambertInputValidation` only.
It was published on 2026-11-23 at 02:20 UTC, tagged and published from
the Actions tab with **publish** on (SRelD issue 52). #311 was merged at
00:34 UTC. CI on `caabf11` passed at the first attempt
([run 45089535321](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/45089535321)). The tag workflow
([run 45094821804](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/45094821804)) passed the release check and tagged
it at 01:29:52. The release workflow ([run 45094885068](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/45094885068))
built, installed and checked every file. It attached the eleven and
published the release 51 minutes after the tag. It was never a public
release without files.

2.14.2 was prepared on 2026-11-23 by this checklist, from the backlog
procedure (`CLAUDE.md`, "Backlog and release procedure") of an
unattended run: a patch release with one fix, the Budgets area shown
quickly (SRelD K-40), and the 2.14.1 publication record (#312). It has
no release pull request: the run commits to `develop` and starts the tag
workflow there. No file format changed: the scenario file is still at
schema version 6, and `schema/`, the templates, the golden files and
`packaging/` are as at the 2.14.1 tag `caabf11`. The space weather was
not refreshed: CelesTrak reset all three connections, so 2.14.2 carries
2.13.0's file (observations to 2026-11-18).
It was published on 2026-11-23 at 11:13 UTC (SRelD issue 54). It was
not tagged on the release commit `ce6123e`: CI on it
([run 45114509231](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/45114509231)) failed one Linux test, and the
unattended run stopped and tagged nothing. #315 fixed the cause, a
fault older than 2.14.1, and was merged at 09:02 UTC as `452e164`. CI
on `452e164` passed at the first attempt
([run 45143562273](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/45143562273)). The tag workflow
([run 45147869658](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/45147869658)) passed the release check and tagged
`452e164` at 09:33:01. The first attempt of the release workflow
([run 45148067729](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/45148067729)) failed one Windows test: the 3D
View's move took 64.0 ms, then 72.7 ms, against the 50 ms limit (SRelD
K-40). The attach job did not run, so nothing was published. The same
test had passed on the same commit in CI, so the failed jobs were run
again once. The second attempt built, installed and checked every file,
attached the eleven and published the release 100 minutes after the
tag. It was never a public release without files.

2.15.0 was prepared on 2026-11-23 by this checklist: Monte Carlo phase B
(`monte-carlo-plan.md`), with the batch seed, the thermal node limits
and the small fixes (#313), the outcome statistics, the sensitivity and
the trust checks (#314), the batch report, `monte-carlo --summarize`,
`--report`, `--csv`, `--runs` and `--processes`, and template 37 (#316),
and the 2.14.2 publication record (#317); a minor release because it
adds features and a scenario schema step. The release branch starts
from `records/2.14.2-published` at `79e0331` (#317, not merged yet),
which holds `develop` at `0dc0810`, so the release pull request merges
after #317. The scenario file moves to schema version 7, so 2.14.2 and
earlier refuse every file 2.15.0 saves, by its version (checked with
2.14.2's code, the tag `452e164`, on the 37 templates as 2.15.0 saves
them: all refused); 2.15.0 opens the files 2.14.2 saves. `git diff
452e164` shows the step in `schema/`, the scenario hashes recorded
again, template 37 and its golden file new, and the 36 earlier
templates changed only on their version line; the 36 earlier golden
files are byte-identical. The space weather was not refreshed:
CelesTrak reset all three connections, so 2.15.0 carries 2.13.0's file
(observations to 2026-11-18). The CHANGELOG heading carries 2026-11-24,
the UTC day the tag will be made, because the release check wants the
tag's day. By the owner's decision (SRelD K-45), the release pull
request may be merged with CI's "Windows (MAX Python)" job red, for the
Basilisk framework test `LambertInputValidation` only.

---

**Next:** [Syncing with upstream Basilisk](upstream-sync.md) ·
[Developer guide](README.md)
