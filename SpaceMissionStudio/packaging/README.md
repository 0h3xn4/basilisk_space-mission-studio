# Packaging

How SpaceMissionStudio becomes an installable application for Linux and
Windows, and what the release workflow checks. The records of earlier
checks by hand are in [`VERIFICATION_HISTORY.md`](VERIFICATION_HISTORY.md).

## Two ways to install

| Way | Files | What it contains | Needs |
|---|---|---|---|
| **Installer** | The Linux `.deb` (`build_deb.sh`); the Windows setup program (`windows/spacemissionstudio.iss`) | A private Python 3.14 with Basilisk, SpaceMissionStudio, every Python package and the reference data | No Python, no terminal, no internet |
| **Install script** | `install.sh`, `install.ps1` (and `build_wheel.sh`, `build_wheel.ps1`) | A virtual environment made with the computer's Python 3.14; Basilisk and the packages from PyPI | Python 3.14 and internet. Use it for Linux on ARM (aarch64), which has no installer. |

**Basilisk version:** the installers contain `bsk[all]==2.12.0`, the
version that the app is qualified with. Two places set it:
`spacemissionstudio/dependencies.py` and `BASILISK_REQUIREMENT` in
`bundle_python.py`. Change them together. `tests/test_dependencies.py`
fails when they are different.

## The files in this folder

| File | What it does |
|---|---|
| `bundle_python.py` | Builds the private Python of the two installers ([The bundled Python](#the-bundled-python)) |
| `build_deb.sh` | Builds the Linux `.deb` |
| `windows/spacemissionstudio.iss` | The Inno Setup script of the Windows setup program |
| `windows/spacemissionstudio.ico` | The icon of the setup program and its shortcuts. `make_ico.py` makes it from `gui/icons.py`. |
| `build_wheel.sh`, `build_wheel.ps1` | Build the wheel and the sdist (`python -m build`) |
| `install.sh`, `install.ps1` | Install from a clone into a virtual environment, with a launcher |
| `spacemissionstudio.desktop.in` | The desktop entry template of `install.sh` |
| `linux/io.github._0h3xn4.SpaceMissionStudio.metainfo.xml.in`, `metainfo.py` | The AppStream metadata of the `.deb` |
| `constraints.txt` | The exact version of each package that the installers contain |
| `constraints-hashes.txt`, `hash_constraints.py` | The same pins with the SHA-256 of their files, and the script that writes them |
| `constraints-dev.txt` | The exact versions of the CI tools (pytest and its plugins, ruff, pip-audit, pre-commit) |
| `audit-exceptions.txt` | The advisories that `pip-audit` accepts, each with its ID, version and reason (pillow 12.2.0, which the qualified Basilisk caps; SRelD K-25) |
| `release_notes.py`, `release_check.py` | The release notes from the CHANGELOG, and the checks before a release ([Releasing](../docs/developer/releasing.md)) |
| `legal/` | The licence texts and notices that the packages contain |

CI's `test` job checks `constraints.txt` and `constraints-dev.txt`
against the advisory databases (`pip-audit --no-deps`). It fails on a
known vulnerability that `audit-exceptions.txt` does not list.

## Offline policy

The app makes no network call at run time. The reference data comes
with the installation:

- **The installers** contain all support data files (117 MB) and the
  Earth orientation files (36 MB). The support data is the SPICE
  kernels, gravity fields, the magnetic model, albedo maps and the
  atmosphere tables. `bundle_python.py`
  downloads them when the installer is built. The computer that installs
  downloads nothing.
- **The ITU-R P.676-13 data file** is not in the installers. ITU allows
  its copy only with written permission (`docs/legal/DATA_TERMS.md`, D1).
  A user who selects this model downloads it with
  `spacemissionstudio gaseous-attenuation --fetch` or in the **Reference
  data** window.
- **The install scripts** download the support data and the Earth
  orientation files one time, after the installation, when you give
  `--basilisk-wheel` (`-BasiliskWheel`). A failure does not stop the
  script. It shows if you must run `spacemissionstudio kernels-status`
  later, with internet.
- **At each start of the GUI**, the card **Fetch or update reference
  data?** on **Home** offers newer data. Nothing downloads before you
  click **Fetch now**. **Not now** uses no network.

**Not in the installers:** the Qt modules that Qt 6.11 gives only under
the GPL v3, the plugins that load them, Tcl/Tk and `_dbm`
(`bundle_python.prune_unused`; owner's decision D9 in
`docs/legal/OBLIGATIONS.md`). The app imports none of them (`tests/test_hashed_installs.py`
checks it).

## The release files

The workflow `.github/workflows/spacemissionstudio-release.yml` builds
the release files of a tag (`spacemissionstudio-vX.Y.Z`) on GitHub's
runners ([Releasing](../docs/developer/releasing.md), sections 5 and 6).
It attaches nothing before the full test suite passes on the tag.

| Platform | Files | Installed and run in the workflow |
|---|---|---|
| Linux (x86_64, `ubuntu-24.04`) | The wheel, the sdist, the `.deb` and its bill of materials, `SHA256SUMS-linux` | The desktop entry, the icons and the AppStream metadata are validated. The `.deb` installs with the network cut off. Then, offline and with an empty support data cache: `--version`, `kernels-status`, each template validated, template 01 run, the Earth orientation files found, the main window opened. |
| Windows (x64, `windows-latest`) | The setup program and its bill of materials, `SHA256SUMS-windows` | A silent install (`/VERYSILENT /CURRENTUSER`). Then, with an empty support data cache, the same checks with one template. |
| Sources (the `attach` job) | The two Qt and PySide6 source archives (LGPL-3.0, `legal/qt-sources.json`) and `SHA256SUMS-sources` | Downloaded from download.qt.io and checked against their recorded sizes and SHA-256 |

A release has eleven files. Their checksums are in the `SHA256SUMS-*`
files of the release. A local build of the same commit gives different
checksums. macOS is not supported.

## The `.deb` package

`build_deb.sh` makes `spacemissionstudio_<version>_amd64.deb`. It
contains:

| Path | What |
|---|---|
| `/opt/spacemissionstudio/python` | The bundled Python, with Basilisk, the wheel, each package, the support data and the Earth orientation files |
| `/usr/bin/spacemissionstudio` | A launcher that runs that Python isolated (`-I -m spacemissionstudio.cli`) |
| `/usr/share/applications/`, `/usr/share/icons/hicolor/` | The desktop entry, and the icon from 16 to 512 px and as SVG |
| `/usr/share/metainfo/io.github._0h3xn4.SpaceMissionStudio.metainfo.xml` | The AppStream metadata for software centres. The app does not read it. |

dpkg removes each file at uninstall. `postinst` removes the virtual
environment of packages up to 1.1.0, and updates the desktop and icon
caches. It downloads nothing. `postrm` removes what is left under
`/opt/spacemissionstudio`.

`Depends` lists the X11, OpenGL, font and sound libraries that Qt loads
from the system. It also requires glibc 2.34 or newer, because the
PySide6 6.11 wheels are `manylinux_2_34`: Ubuntu 22.04, Debian 12 or
newer.

## The Windows setup program

`windows/spacemissionstudio.iss` is an
[Inno Setup](https://jrsoftware.org/isinfo.php) script. It makes
`spacemissionstudio-<version>-setup.exe`, a wizard: Welcome, licence,
install location, Install, and an optional "launch now" on Finish.

- It installs the bundled Python in `{app}\python`. The computer needs
  no Python and no internet.
- It installs for the user (`{localappdata}`), without administrator
  rights.
- It adds a Start Menu entry and, as an option, a desktop shortcut. They
  start the GUI with `pythonw.exe -I` (no console window).
- After the copy, it compiles the bytecode for the selected folder and
  points the Earth orientation manifest to it.
- An upgrade first removes the earlier `python` folder, and what setups
  up to 1.1.0 left. Uninstall removes `{app}\python`.

To build it on Windows, with Inno Setup 6, Python 3.14 and internet:

```powershell
cd SpaceMissionStudio
powershell -File packaging\build_wheel.ps1 packaging\windows\dist
python packaging\bundle_python.py --platform windows --dest packaging\windows\python --wheel (Get-ChildItem packaging\windows\dist\spacemissionstudio-*.whl).FullName
ISCC packaging\windows\spacemissionstudio.iss
```

After a change to the icon, make the `.ico` again.
`tests/gui/test_icons.py` fails while the file and the icon are
different:

```bash
QT_QPA_PLATFORM=offscreen python packaging/make_ico.py --from-app packaging/windows/spacemissionstudio.ico
```

The workflow `.github/workflows/spacemissionstudio-windows-installer.yml`
builds the setup program on a Windows runner, installs it silently and
runs the installed tool. A push to `packaging/windows/`,
`bundle_python.py` or `constraints.txt` starts it. To attach a setup
program to a release, start it from the Actions tab
("SpaceMissionStudio Windows installer") with the tag, and tick
"attach".

## The install scripts

`install.sh` makes a private virtual environment. It installs the wheel
with its `gui` extra and, with `--basilisk-wheel`, Basilisk. It writes
a `spacemissionstudio` launcher and a desktop entry in
`~/.local/share/applications/` (not with `--no-desktop-entry`). It
draws the app icon into `$XDG_DATA_HOME/icons/hicolor/` with the
`offscreen` Qt platform. If the icon fails, the desktop entry still
installs.

`install.ps1` and `build_wheel.ps1` do the same steps on Windows, with
the flags `-Prefix`, `-BasiliskWheel`, `-SpaceMissionStudioWheel` and
`-NoShortcut`. The shortcut is
`%APPDATA%\Microsoft\Windows\Start Menu\Programs\SpaceMissionStudio.lnk`,
with the icon `windows/spacemissionstudio.ico`.

**The two PowerShell scripts were not run on a real Windows computer.**
They follow the Linux scripts step by step. If you run them, report
each problem. CI runs the app itself on Windows: the `platforms`
job installs it with `pip` and runs the full test suite.

## The bundled Python

`bundle_python.py` builds the same kind of folder for each installer,
on the platform of the installer:

1. **CPython 3.14.8** from python-build-standalone release 20261013, the relocatable `install_only_stripped` build (`PYTHON_BUILDS`). The script checks the archive against its pinned SHA-256 before it unpacks it.
2. **Basilisk and the app:** `bsk[all]==2.12.0`, then the wheel with its `gui` extra. Both are hash-checked against `constraints-hashes.txt` (`--require-hashes --only-binary=:all:`), by the bundled pip, isolated (`-I`).
3. **The check of the packages:** each installed package must be one of the pins, at its version. If not, the build stops.
4. **The reference data:** every file of `engine.kernels.ALL_SUPPORT_DATA_FILES` goes to `site-packages/supportData`. The Earth orientation files go to `share/spacemissionstudio/earth_orientation`.
5. **An offline check,** with no network and an empty download cache. The script must find each support file and the Earth orientation files. If not, the build stops.
6. **With `--prefix`** (the `.deb`): the script compiles the bytecode for that folder and points the Earth orientation manifest there. The Windows setup program does this at install time.
7. **`SPACEMISSIONSTUDIO_RUNTIME.json`** records the CPython archive, the versions, each package, and each data file with its size and SHA-256.
8. **`SPACEMISSIONSTUDIO_SBOM.cdx.json`** is the software bill of materials (CycloneDX 1.6 JSON). The release attaches it beside each installer.

The data is as new as the build. A newer download of a user goes to the
user's cache, and the app uses it first. The installed copy never
changes. The licences of the folder's contents are in
[`docs/THIRD_PARTY_ASSETS.md`](../docs/THIRD_PARTY_ASSETS.md), "In the
installers".

## Pinned and hash-checked dependencies

`constraints-hashes.txt` adds the SHA-256 of each file that PyPI
publishes for each pin and that Python 3.14 can install. With it, pip
works in hash-checking mode: a file with an unknown SHA-256, or a
package that is not pinned, stops the installation.

| Who | Uses |
|---|---|
| `bundle_python.py` (the installers) | `constraints-hashes.txt`, with `--only-binary=:all:` |
| `install.sh`, `install.ps1` | `constraints-hashes.txt` for SpaceMissionStudio and its packages; the plain pins for the Basilisk wheel that you give |
| CI and developers | `constraints.txt` (an editable install cannot be hash-checked) |

After you change a pin in `constraints.txt`, write the hashed file again:

```bash
python packaging/hash_constraints.py           # writes constraints-hashes.txt
python packaging/hash_constraints.py --check   # the two files agree (no network)
```

The script follows each requirement of `bsk[all]` and of
`spacemissionstudio[gui]` on Linux x86_64 and Windows x64. It stops when
a requirement is not pinned, or when a pin has no wheel for one of them.
`tests/test_hashed_installs.py` fails when the two files do not agree.

## Not done

- An installation by hand on a desktop, with the app opened from the
  application menu.
- The Windows wizard clicked through by hand, and the GUI opened from
  the Start Menu, on a real Windows 10 or 11 computer.
- The `.deb` on a Debian 12 or Ubuntu 22.04 computer.

---

**Next:** [Getting started](../docs/getting-started.md) ·
[Documentation index](../docs/README.md)
