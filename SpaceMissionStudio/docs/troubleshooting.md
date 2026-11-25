# Troubleshooting

What to do when the installation or a run goes wrong. Each problem is
listed by the message that you see. The messages are quoted exactly.

## Contents

- [Installing](#installing)
- [Starting the app](#starting-the-app)
- [Reference data](#reference-data)
- [Running a scenario](#running-a-scenario)
- [Scenario files](#scenario-files)
- [Messages that are normal](#messages-that-are-normal)
- [Reporting a problem](#reporting-a-problem)

## Installing

### `pip` cannot find `bsk`

Basilisk 2.12.0 has prebuilt wheels only for:

- Linux x86_64 and aarch64 with glibc 2.28 or newer (`ldd --version`
  shows your version);
- Windows x86_64;
- Python 3.14 (`python3 --version`).

On other systems, for example Ubuntu 18.04, pip finds no wheel. Use a
newer system. You can also build Basilisk from source, but this is
rarely necessary ([Basilisk's build guide](../../docs/source/Build.rst)).

### Behind a company firewall or proxy

`pip` and the reference data downloads use the `HTTPS_PROXY`
environment variable. Set it before the installation. Allow these hosts:

| Host | For |
|---|---|
| `pypi.org`, `files.pythonhosted.org` | Basilisk and the Python packages |
| `naif.jpl.nasa.gov` | SPICE kernels and Earth orientation files |
| `raw.githubusercontent.com` | The gravity field and the magnetic model |
| `hanspeterschaub.info` | Basilisk's second source of the support data |
| `celestrak.org` | Newer space weather, only when you ask for it |
| `www.itu.int` | The ITU-R P.676-13 data file (`gaseous-attenuation --fetch`), only when you ask for it |

### Windows: "running scripts is disabled on this system"

PowerShell does not run `Activate.ps1`. Allow the scripts that you start
yourself, for your account only:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then activate the environment again.

## Starting the app

### Linux: `ImportError: libEGL.so.1` (or another `.so`) when the GUI starts

A minimal system does not have the Qt libraries. On Debian or Ubuntu,
install them:

```bash
sudo apt-get install libegl1 libopengl0 libxcb-cursor0 libgl1 libxkbcommon0
```

### The Results plot stays blank

The plots use an embedded web view (Qt WebEngine). On a minimal Linux
system, it needs more libraries. On Debian or Ubuntu, install them:

```bash
sudo apt-get install libnss3 libatk-bridge2.0-0 libgbm1
```

### A 3D view says WebGL is not supported or could not start, or stays blank

The 3D model editor and **Results › 3D View** use WebGL. Without a
usable GPU (a virtual machine, a remote desktop), the app lets Chromium
use software rendering.

If you set `QTWEBENGINE_CHROMIUM_FLAGS` yourself, the app uses only your
flags. Add these flags to them:
`--ignore-gpu-blocklist --enable-unsafe-swiftshader --disable-domain-blocking-for-3d-apis`.

The 3D model works without the view. The tabs below the view show the
mass properties and the facets.

### "(not qualified)" after the Basilisk version in the status bar

A Basilisk version other than 2.12.0 is installed. Runs work, but the
app is not verified with that version. To go back, type
`pip install "bsk[all]==2.12.0"`.

## Reference data

### `FAIL  naif0012.tls: Support data file not found via pooch: ...`

`kernels-status` could not download a file. Usually there is no internet
connection. The command tries NAIF first, then Basilisk's second host.
Do one of these:

- Connect to the internet and type `spacemissionstudio kernels-status`
  again.
- Install the files from disk ([Work offline](user-manual/reference-data.md#work-offline)).

### `ERROR: run failed: support-data file GGM03S.txt is not installed (...)`

The message continues:

```text
SpaceMissionStudio does not download during a run: download it from the Reference data dialog (Settings > Reference data, Download... > Support data) or with `spacemissionstudio kernels-status`.
```

Do these steps:


1. Open the **Reference data** window: **Tools › Reference Data...**, or click the reference data item in the status bar.
2. Click **Download...**, then **Support data**. Or type `spacemissionstudio kernels-status`.
3. Run again.

### `Earth orientation: no IERS files installed -- the Earth-fixed frame is IAU_EARTH (about 160 m/day of error at 400 km); Settings > Reference data downloads them`

**Scenario › Overview** shows this message. A run shows
`Earth orientation: IAU rotation model, no IERS data installed`. The
measured Earth orientation files are not installed, so the run uses the
simpler IAU model. Do one of these:

- Type `spacemissionstudio earth-orientation --fetch`.
- In the **Reference data** window, click **Download...**, then **Earth
  orientation**.

## Running a scenario

### `ERROR: Basilisk is not installed/built (No module named 'Basilisk') -- see SpaceMissionStudio/README.md`

The GUI can also say that Basilisk is not installed. The GUI works
without Basilisk, but runs need it.

1. Activate your environment: `source .venv/bin/activate`, or `.venv\Scripts\Activate.ps1` on Windows.
2. Type `pip install "bsk[all]==2.12.0"`.

With an installer, install the app again.

### Run is not available

Look at the message at the bottom of the **Scenario** area. It names
the field to correct. The **Problems** panel (`Ctrl+J`) lists all
problems. **✓ valid** means that you can run.

### A run takes too long, or you started the wrong one

Click **Cancel Run** (`Esc`). The run stops safely at the next
checkpoint, and keeps its results. The stop is not immediate.

**Cancel Run** also stops a Monte Carlo batch. Its processes stop. The
finished runs stay in the archive folder, and **Results › Monte Carlo**
opens on them. If you close the window during a batch, the app asks:
**Cancel and close** or **Keep running**.

### A long run fills memory

Set **Record every** on the **Scenario › Environment** page, for example
600 s. With this setting, five years of LEO station keeping took about
50 minutes and 450 MB.

### A run with script blocks is refused

```text
1 script_block(s) (...) run unrestricted Python from the scenario file. Read the code first, then pass --allow-scripts to run it.
```

The Mission Sequence of the scenario contains Python code. Read the
code. If you trust it, add `--allow-scripts`. The GUI asks you instead.

## Scenario files

`spacemissionstudio validate` and **File › Open...** name the problem:

| Message | Meaning |
|---|---|
| `INVALID: f.json: not valid JSON (Expecting property name enclosed in double quotes: line 1 column 3 (char 2))` | The file is not JSON. The message gives the position. |
| `INVALID: f.json: spacecraft[0].dry_mass_kg: expected a number, got text` | A value has the wrong type. The message names the field. |
| `INVALID: my-sat: dry_mass_kg must be in (0, 1e6] -- if your intended value is outside this range, check for a units mixup (e.g. g instead of kg)` | A value is out of range. |
| `INVALID: f.json: could not read file (No such file or directory)` | The path is wrong. |
| `INVALID: f.json: malformed scenario structure (...)` in an old version | A newer version saved the file. Open it with that version or a newer one. Update all computers of a team together. |

`ccsds-import` refuses a message with an epoch that is not the epoch of
the scenario:

```text
ERROR: the OPM state is at 2030-01-01T08:30:00 UTC, the scenario epoch is 2030-02-01T00:00:00; pass --set-epoch to move the scenario epoch to the OPM's
```

### `Cannot import here yet: the scenario is a built-in template: save it as your own file first (File › Save As), then try again.`

**Import IDM-CIC model...** in the 3D model editor writes the meshes of
the model beside the scenario file. The app does not change the
templates.

1. Click **File › Save As...** (`Ctrl+Shift+S`), and save the scenario under your own name.
2. Import the model again.

The app refuses an import in the same way for a scenario that you did
not save, or that is in a read-only folder. The message gives the
reason.

## Messages that are normal

| Message | Why |
|---|---|
| `INFO ... Logging to ~/.spacemissionstudio/logs/...log` | Each command gives its log file. |
| `INFO matplotlib.font_manager: ... generated new fontManager` | The first run makes a font cache, one time. |
| `WARNING: space weather uses MSFC's prediction (nov2026f10-prd.txt), 50th percentile F10.7 and Ap` | The run is after the end of the observed space weather, so the drag uses NASA MSFC's prediction. |
| `WARNING: past 2041-10 MSFC's last 132 months repeat (ESA AD10 Sec. 5.9)` | A long lifetime estimate goes past the end of MSFC's prediction. The app repeats its last solar cycle. |
| `N: Download is performed unsandboxed as root, as file '.../spacemissionstudio_<version>_amd64.deb' couldn't be accessed by user '_apt'` | apt shows this notice when its user `_apt` cannot read the folder of the `.deb`, for example your home folder. The installation is correct. To prevent the notice, copy the `.deb` to `/tmp` and install it from there. |

## Reporting a problem

[Open an issue](https://github.com/0h3xn4/basilisk_space-mission-studio/issues)
with:

- the log file that the error dialog names (in `~/.spacemissionstudio/logs/`);
- the versions, from **Help › About SpaceMissionStudio** or
  `spacemissionstudio --version`;
- the scenario file, if you can share it.

The [FAQ](faq.md) answers questions that are not errors.

---

**Next:** [FAQ](faq.md) ·
[Getting started](getting-started.md) ·
[Documentation index](README.md)
