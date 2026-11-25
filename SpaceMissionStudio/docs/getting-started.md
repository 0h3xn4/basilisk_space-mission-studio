# Getting started

This page tells you how to install SpaceMissionStudio, check the
installation and do your first run.

## Contents

1. [What you need](#1-what-you-need)
2. [Pick an install path](#2-pick-an-install-path)
3. [Path A: the installer](#3-path-a-the-installer)
4. [Path B: the install script](#4-path-b-the-install-script)
5. [Path C: from source, step by step](#5-path-c-from-source-step-by-step)
6. [Check that it works](#6-check-that-it-works)
7. [Your first run](#7-your-first-run)
8. [Where things are kept](#8-where-things-are-kept)
9. [If something goes wrong](#9-if-something-goes-wrong)

## 1. What you need

| | |
|---|---|
| Linux | x86_64 or aarch64, glibc 2.34 or newer: Ubuntu 22.04, Debian 12, RHEL 9 or newer. CI uses Ubuntu 24.04. |
| Windows | Windows 10 or 11, x86_64. CI runs the tests on Windows. |
| Python | None for the installers (path A). Paths B and C need Python 3.14. Older versions are not supported. |
| Disk | About 1.7 GB: Python with Basilisk and Qt, 117 MB of reference data, 36 MB of Earth orientation files |
| Internet | None for the installers. Paths B and C: one time, during the installation. |

After the installation, the app works offline. It downloads nothing
without your consent.

The app has two parts:

- **SpaceMissionStudio:** the windows, the forms, the plots and the
  scenario files.
- **Basilisk:** the simulation engine of the AVS Lab (University of
  Colorado Boulder). It calculates every number. Without Basilisk, you
  can make and save scenarios, but you cannot run them.

## 2. Pick an install path

| Path | For | You type |
|---|---|---|
| **A. Installer** (`.deb` on Linux, setup program on Windows) | Use of the app | Nothing: double-click |
| **B. Install script** (`packaging/install.sh` or `install.ps1`) | Use of the app from a clone of this repository | One command |
| **C. From source** with `pip` | Development, Python scripts, the tests | About eight commands |

All three paths install Basilisk 2.12.0. The app is verified with this
version. Linux on ARM (aarch64) has no installer: use path B or C.

## 3. Path A: the installer

1. Go to the [releases page](https://github.com/0h3xn4/basilisk_space-mission-studio/releases).
2. Download the installer for your system and its checksum file.
3. Check the download. On Linux, type `sha256sum -c SHA256SUMS-linux --ignore-missing`. On Windows, use `Get-FileHash` in PowerShell.
4. Install it. See the steps for your system below.
5. Open **SpaceMissionStudio** from the application menu or the Start Menu.
6. Go to [section 6](#6-check-that-it-works).

The installers contain Python, Basilisk and the reference data. The
computer needs no Python and no internet.

**Linux** (x86_64; Ubuntu 22.04, Debian 12 or newer): double-click
`spacemissionstudio_<version>_amd64.deb`, or type:

```bash
sudo apt install ./spacemissionstudio_<version>_amd64.deb
```

A last line `N: Download is performed unsandboxed as root ...` is a
normal apt notice
([Troubleshooting](troubleshooting.md#messages-that-are-normal)).

**Windows 10 or 11** (x64): run `spacemissionstudio-<version>-setup.exe`.
The setup program has no signature, so Windows asks before it runs it.
Click **More info**, then **Run anyway**. The program installs for your
user only, without administrator rights, in
`%LOCALAPPDATA%\SpaceMissionStudio`.

To build the installers yourself, and to see what the release workflow
checks, read [`packaging/README.md`](../packaging/README.md).

## 4. Path B: the install script

In the `SpaceMissionStudio` folder of a clone, type one command:

```bash
packaging/install.sh --basilisk-wheel "bsk[all]==2.12.0"            # Linux
```

```powershell
packaging\install.ps1 -BasiliskWheel "bsk[all]==2.12.0"             # Windows PowerShell
```

The script makes a private Python environment. It installs the two
parts and the reference data, and adds a launcher: a desktop entry on
Linux, a Start Menu shortcut on Windows. The Linux script was run from
start to end. The Windows script was not run on a real Windows computer.

## 5. Path C: from source, step by step

1. Get the code, and go to its `SpaceMissionStudio` folder:

   ```bash
   git clone https://github.com/0h3xn4/basilisk_space-mission-studio.git
   cd basilisk_space-mission-studio/SpaceMissionStudio
   ```

2. Make a private Python environment. Then your system Python does not change.

   | Linux | Windows (PowerShell) |
   |---|---|
   | `python3 -m venv .venv` | `python -m venv .venv` |
   | `source .venv/bin/activate` | `.venv\Scripts\Activate.ps1` |

   The prompt starts with `(.venv)`. Activate the environment again in
   each new terminal. If Windows does not run `Activate.ps1`, see
   [Troubleshooting](troubleshooting.md#windows-running-scripts-is-disabled-on-this-system).

3. Install Basilisk. The wheel is prebuilt, so you need no compiler. This step takes 1.5 to 7 minutes.

   ```bash
   pip install "bsk[all]==2.12.0"
   ```

4. Install SpaceMissionStudio with its GUI. This step takes about a minute.

   ```bash
   pip install -e ".[gui]"
   ```

   To run the tests too, use `".[dev,gui]"`.

5. Get the reference data. Do this one time.

   ```bash
   spacemissionstudio kernels-status
   spacemissionstudio earth-orientation --fetch
   ```

The first command downloads 116 MB: SPICE kernels, gravity fields, the
magnetic model, albedo maps and atmosphere tables. It shows twelve files
as `OK`. The second command downloads the measured Earth orientation
files (36 MB). It ends with a line like this one:

```text
Earth-fixed frame: ITRF93; high accuracy until 2026-12-18, predicted after.
```

The date changes with each update. Without these files, runs use a
simpler model of the Earth rotation, and they tell you so.

Two more downloads are necessary only for some scenarios
([Reference data](user-manual/reference-data.md)):

| For | Command |
|---|---|
| Template 31, the asteroid Eros | `spacemissionstudio small-bodies --fetch` |
| `link.atmospheric_loss: itu_r_p676` | `spacemissionstudio gaseous-attenuation --fetch` |

Each command first shows a line `INFO ... Logging to
~/.spacemissionstudio/logs/...log`. This line is normal.

## 6. Check that it works

Type this command. It needs no Basilisk:

```console
$ spacemissionstudio validate spacemissionstudio/scenarios/templates/22_starter_first_leo_satellite.json
OK: '22 - Starter: your first LEO satellite' -- 1 spacecraft, schema version 8, epoch 2030-01-01T08:30:00
```

Then start the GUI: from the application menu, or with
`spacemissionstudio gui`. Check these items:

| Check | Expected result |
|---|---|
| The status bar | No item about Basilisk. The status bar shows **Basilisk not installed**, or **(not qualified)** after the version, only when there is a problem. **View › Status Bar: All Details** always shows the version. |
| **Tools › Check Reference Data**, or **Check Reference Data** in the **Run** area | The **Reference data** window opens. Each file shows **Present**. |
| **Help › About SpaceMissionStudio** | The versions of the app and of Basilisk. In a terminal: `spacemissionstudio --version`. |

**(not qualified)** means that a Basilisk version other than 2.12.0 is
installed. Runs work, but the app is not verified with that version.

## 7. Your first run

Template 22 is one 150 kg satellite in a 550 km Sun-synchronous orbit.
The run is one day, with a ground station in Berlin.

**In the GUI** (about a minute):

1. Start the app. It opens on **Home**, with no scenario open.
2. On the card **Fetch or update reference data?**, click **Not now**. Click **Fetch now** only for newer data.
3. Click the card **22 - Starter: your first LEO satellite**. Its description shows at the right.
4. Click **Open template**. The **Scenario** area shows the mission.
5. Read **Overview** at the top of the tree. It predicts `berlin-gs: 4 passes`.
6. Click **Run** in the top bar (`Ctrl+R`). The run takes a few seconds.
7. Look at the **Results** area. It opens when the run ends.
8. Click the **Plots** tab. In the plot list, click **Inertial Position (ECI)**.
9. Open the **Timeline** (`Ctrl+6`). It shows four Berlin passes and fifteen eclipses of about 35 minutes.
10. Click **File › Save As...** (`Ctrl+Shift+S`). Save your own copy before you change it.

**On the command line:**

```console
$ spacemissionstudio run spacemissionstudio/scenarios/templates/22_starter_first_leo_satellite.json --out-dir out
Running '22 - Starter: your first LEO satellite' (1 spacecraft, 1.0 day(s), rkf78)...
Wrote 20 result file(s) to out:
  berlin-gs.access_to_my-sat.azimuth: out/berlin-gs.access_to_my-sat.azimuth.csv
  ...
  provenance: out/provenance.json
  events (19): out/events.csv
WARNING: space weather uses MSFC's prediction (nov2026f10-prd.txt), 50th percentile F10.7 and Ap
```

The `WARNING` is normal. The mission is in 2030, after the end of the
observed space weather. Thus the drag uses NASA MSFC's prediction.

The folder `out/` contains:

- one CSV file for each quantity (time in seconds, values in SI units);
- `events.csv`, the passes and eclipses;
- `provenance.json`: the software versions, the reference files and the
  scenario that gave the numbers.

**From Python:** `python3 examples/build_a_scenario.py my_first_mission.json`
makes a scenario in code. [The examples](../examples/README.md) show
more.

## 8. Where things are kept

On Windows, read `%USERPROFILE%` for `~`.

| What | Where |
|---|---|
| Your scenarios | Where you save them: `.json` files |
| The templates | `spacemissionstudio/scenarios/templates/`. The app never changes them. |
| Autosave | `~/.spacemissionstudio/autosave/` |
| Log files | `~/.spacemissionstudio/logs/`. An error dialog names the current one. |
| Support data (SPICE, gravity, magnetic model) | Installers: in the install folder (`.../site-packages/supportData/`). Other installations: the Basilisk cache, for example `~/.cache/bsk_support_data/`. `kernels-status` shows the folder. |
| Earth orientation | Installers: in the install folder (`.../share/spacemissionstudio/earth_orientation/`). Your downloads go to `~/.cache/SpaceMissionStudio/earth_orientation/`, and the app uses them first. |
| Space weather downloads | `~/.cache/SpaceMissionStudio/spaceweather/`, only after you download newer data |

## 9. If something goes wrong

| Problem | What to do |
|---|---|
| **Run** says that Basilisk is not installed | Activate the environment. Type `pip install "bsk[all]==2.12.0"`. |
| Linux: `ImportError: libEGL.so.1` when the GUI starts, or an empty plot | Install the Qt system libraries ([Troubleshooting](troubleshooting.md#linux-importerror-libeglso1-or-another-so-when-the-gui-starts)). |
| `pip` cannot find `bsk` | Your Python or your system has no Basilisk wheel. See [section 1](#1-what-you-need). |

For all other problems, see [Troubleshooting](troubleshooting.md).

---

**Next:** [Run a template](user-manual/run-a-template.md) ·
[How-to guides](user-manual/README.md) ·
[FAQ](faq.md)
