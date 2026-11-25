# Packaging: verification records

The records of the packaging checks that were made by hand or in a
container, before the release workflow did them for each release. They
were in `packaging/README.md` until 2026-11-25. They are kept here as
they were written, as an append-only record (decision DOC-6). For what
is true now, read [`README.md`](README.md).

## `build_wheel.sh`: two bugs found when it was first run

When `build_wheel.sh` was first run, a real bug was caught: `spacemissionstudio/scenarios/*.json` (the
two-body validation scenario) was silently missing from the built wheel,
because `setuptools.packages.find()` only picks up Python packages
(directories with `__init__.py`), and `scenarios/` has none. Fixed via
`pyproject.toml`'s `[tool.setuptools.package-data]` -- re-verified by
rebuilding and confirming the file is now present in the wheel and
loadable from the installed copy.

A second real bug was caught running this script TWICE in a row:
`python -m build`'s own temp output directory (`./build/`, gitignored)
is left behind after a run, and because Python inserts the current
directory at the front of `sys.path` for both `-c` and `-m` invocations,
that leftover directory silently SHADOWED the real installed `build`
package on the next run (`ModuleNotFoundError`-adjacent: `No module
named build.__main__`). Fixed by having the script clean `./build/`
before it starts, and by checking installedness with `pip show build`
instead of `python -c "import build"` (which was itself vulnerable to
the same shadowing). Re-verified by running the script twice
back-to-back after the fix.

## `install.sh`: verified for 1.0.0

**Verified for 1.0.0**
(2026-10-14, Ubuntu 24.04 container, Python 3.11, a fresh `$HOME`):
`install.sh --basilisk-wheel "bsk[all]==2.12.0"` with the 1.0.0 wheel
installed every pinned version of `constraints.txt` (bsk 2.12.0, numpy,
PySide6, plotly, sgp4, pyerfa as listed), pre-fetched the support data
and the Earth orientation files, and wrote the launcher, the desktop
entry and the icon. The launcher reported 1.0.0 with Basilisk 2.12.0,
validated all 28 templates, ran templates 01, 16 and 28, and ran the
Monte Carlo template 09's 20 runs.

## The `.deb` package before 1.1.1 (venv-based)

The two sections below record the earlier, venv-based package (up to
1.1.0), which needed a system Python 3.11 and internet access during
`apt install`.

**Verified for 1.1.0** (2026-10-20, Ubuntu 24.04 container, Python
3.11, as root), with the files built from a clean checkout of commit
`1db38b521` (the release records with UI overhaul M1, SRelD issue 8).
This section was written after the build; this file is in neither the
wheel nor the sdist, so the files match the commit that records them:

- `build_wheel.sh` and `build_deb.sh` built
  `spacemissionstudio-1.1.0-py3-none-any.whl`, the sdist and
  `spacemissionstudio_1.1.0_all.deb`. The wheel holds the five font
  files, their two OFL texts, the 35 Lucide icons and Lucide's licence,
  and no IBM Plex file. Their SHA-256:

  ```
  28de266c634df2578427900e13ebfb29108c29a835909c148cb9f72ea6d1f253  spacemissionstudio-1.1.0-py3-none-any.whl
  48f726c51fff1bfafc64ad60317cdeca8b94f624d595911a55b98f932332eabe  spacemissionstudio-1.1.0.tar.gz
  09dbc7d8454e42de2590ed172c3c641945dd0b38536fe6f417ef141478289bbe  spacemissionstudio_1.1.0_all.deb
  ```
- **Upgrade from 1.0.0:** the published 1.0.0 package, downloaded from
  its GitHub release and checked against its `SHA256SUMS-linux`, was
  installed first on a purged system (it reported 1.0.0). Then `apt-get
  install -y ./spacemissionstudio_1.1.0_all.deb` reported "Unpacking
  spacemissionstudio (1.1.0) over (1.0.0)". `postinst` rebuilt
  `/opt/spacemissionstudio/venv` with `bsk[all]==2.12.0` and the bundled
  wheel.
- The installed tool (`/usr/bin/spacemissionstudio`):
  - `--version` gave SpaceMissionStudio 1.1.0 and Basilisk 2.12.0, and
    `kernels-status` found all nine support files;
  - all 31 templates validated;
  - templates 01 and 22 ran, and 22's `provenance.json` records 1.1.0;
  - the Monte Carlo template 09 (20 runs, one thread) ran through the
    GUI's `MonteCarloWorker` from the installed package, offscreen: no
    failed run, 20 run files (K-18);
  - the GUI started (offscreen) with Inter at 13 px as its font, Inter and
    JetBrains Mono registered and the Run icon drawn; with the start-up
    data prompt skipped, the dark theme applied live in 0.37-0.42 s with
    no style-sheet warning, and the window stayed up for 25 s.
- Not done for 1.1.0: an install by hand on a desktop, with the app
  opened from the application menu.

**Verified for 1.0.0** (2026-10-14, Ubuntu 24.04 container, Python
3.11, as root):

- `build_wheel.sh` and `build_deb.sh` built
  `spacemissionstudio-1.0.0-py3-none-any.whl`, the sdist and
  `spacemissionstudio_1.0.0_all.deb`.
- `apt install ./spacemissionstudio_1.0.0_all.deb` completed: `postinst`
  created `/opt/spacemissionstudio/venv`, installed `bsk[all]==2.12.0`
  from PyPI and the bundled wheel, pre-fetched the support data and the
  Earth orientation files, and wrote `/usr/bin/spacemissionstudio` and
  the desktop entry.
- The installed tool: `--version` gave SpaceMissionStudio 1.0.0 and
  Basilisk 2.12.0; `kernels-status` found every kernel; all 28 templates
  validated; templates 01 and 22 ran (22's `provenance.json` records
  1.0.0); the Monte Carlo template 09 ran its 20 runs; the GUI started
  (offscreen) and stayed up.
- Not done for 1.0.0: an install by hand on a desktop, with the app
  opened from the application menu.

Uninstalling (`apt remove`/`apt purge spacemissionstudio`) removes
everything: the package's own files, and whatever else is left under
`/opt/spacemissionstudio` (`postrm`: bytecode Python wrote when the tool
was run as root, or a venv left by a package up to 1.1.0).

**Coming from 3.0.0** (the earlier numbering): apt sees 1.0.0 as older.
Tried on 2026-10-14: over an installed 3.0.0 `.deb`, `apt-get install -y
./spacemissionstudio_1.0.0_all.deb` refused the downgrade ("Packages were
downgraded and -y was used without --allow-downgrades"); after `apt
remove spacemissionstudio` the same command installed 1.0.0, which then
reported 1.0.0 with Basilisk 2.12.0.

**The published 1.0.0 files.** The final wheel, sdist and `.deb` were
rebuilt from the release commit `f288e0c73` and the `.deb` installed
again (it reported 1.0.0 with Basilisk 2.12.0, validated the 28
templates and ran template 01). Those are the files attached to the
[1.0.0 release](https://github.com/0h3xn4/basilisk_space-mission-studio/releases/tag/spacemissionstudio-v1.0.0):
GitHub's SHA-256 digest of each attached file equals the built file's
(`SHA256SUMS-linux`).

## The Windows install scripts: not run on Windows

**Honesty note, matching this project's own discipline elsewhere:**
these two scripts have NOT been run against a real Windows 11 machine --
this development sandbox is Linux-only, with no Windows environment
available at any point in this project's history. They were written
against documented, standard PowerShell/`venv`/`pip`/`WScript.Shell`
behavior and against `build_wheel.sh`/`install.sh`'s own
already-verified logic (matched step-for-step), and reviewed for syntax
by hand since no `pwsh`/`powershell.exe` was available in this sandbox
to actually execute them either -- but "written carefully" is not the
same claim as "run and confirmed working" that the rest of this
directory makes for the Linux scripts. The Start Menu shortcut gets the app icon
from `windows/spacemissionstudio.ico` (since 2.12.0; a `.lnk`'s
`IconLocation` needs an `.ico`, not a `.png`), copied next to the
launcher. If you
run these on a real Windows 11 machine, please report anything that
doesn't work as documented here.

What *is* run on Windows: the application itself. CI installs it with
`pip` on GitHub's `windows-latest` runner, with Basilisk 2.12.0 and the
reference data, and runs the full test suite there on every change
(`.github/workflows/spacemissionstudio.yml`, job `platforms`), and the
setup program is built, installed and run in CI (above). Only these two
scripts are unrun.

## The bundled Python: verified on Linux and Windows

**Verified on Linux (2026-11-09):** `bundle_python.py --platform linux`
built the folder hash-checked (40 packages, the support data, the
offline check passed); its bill of materials validated against the
CycloneDX 1.6 schema (`cyclonedx-python-lib`, strict) with 38 packages,
each with its SHA-256, and 19 data files. A constraints file with one
digest changed stopped pip with "THESE PACKAGES DO NOT MATCH THE HASHES".
`install.sh`'s hash-checked step installed the wheel and its packages
into a fresh virtual environment.

The data is as current as the build: the Earth orientation files carry
data up to their last datum (`earth-orientation` status, the **Reference
data** dialog). A user's own newer download goes to their cache and is
used first; the installed copy is never changed.

Licences of everything the folder contains:
[`docs/THIRD_PARTY_ASSETS.md`](../docs/THIRD_PARTY_ASSETS.md), "In the
installers".

**Verified on Linux (2026-10-20, Ubuntu 24.04 container, as root to
install and as an ordinary user to run),** with the package built from
the working tree of the commit that adds this section, before this
section was written (this file is not in the package; the version in
its files is still 1.1.0):

- `build_deb.sh` took 6.6 minutes (CPython archive already downloaded)
  and built `spacemissionstudio_1.1.0_amd64.deb`: 446,990,484 bytes,
  `Installed-Size` 1,654,980 KiB, 41 packages and 14 data files in
  `SPACEMISSIONSTUDIO_RUNTIME.json`.
- **Upgrade over the venv-based package:** with the earlier 1.1.0 `_all`
  package installed, `unshare --net dpkg -i` (no network) unpacked the
  new package over it in 25 s. `postinst` removed
  `/opt/spacemissionstudio/venv`; the old wheel and `constraints.txt` went
  with the old package, and dpkg took over `/usr/bin/spacemissionstudio`
  and the icon.
- **Purge and fresh install:** `dpkg --purge` left no
  `/opt/spacemissionstudio`, launcher or icon. `unshare --net dpkg -i`
  then installed the package with no network.
- **Run offline as an ordinary user** (`unshare --net su <user>`, an
  empty `HOME` and `BSK_SUPPORT_DATA_CACHE` pointing at an empty folder):
  `--version` gave SpaceMissionStudio 1.1.0, Basilisk 2.12.0, Python
  3.11.17; `kernels-status` found all nine support files in the bundle;
  all 31 templates validated; templates 01 and 22 ran, 22's
  `provenance.json` naming the bundled SPICE kernels and `GGM03S.txt`
  and the ITRF93 Earth frame; the Earth orientation files were found; the
  main window opened (offscreen) in Inter. Nothing was downloaded: no
  Basilisk cache was created.
- Not done: an install by hand on a desktop, with the app opened from the
  menu; a Debian 12 or Ubuntu 22.04 machine.

**Verified on Windows (2026-10-20, `windows-latest`, the release
workflow's pull-request run for this change,
[run 39504407640](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/39504407640)):**
`bundle_python.py --platform windows` built the bundle in the runner's
short temporary folder; Inno Setup compiled it in 143 s into
`spacemissionstudio-1.1.0-setup.exe` (about 395 MB); the silent install
(`/VERYSILENT /CURRENTUSER`) took 72 s. With an empty support-data cache
the installed tool reported 1.1.0, `kernels-status` found all nine files
in `{app}\python\Lib\site-packages\supportData`, template 01 validated
and ran from them, the Earth orientation files were found (the run's
note: "high accuracy until 2026-12-28"), and the main window opened
(offscreen) in Inter. The Windows installer workflow passed the same
checks on the push. Not done: the wizard clicked through by hand, on a
real Windows 10/11 machine (this sandbox has no Windows).
