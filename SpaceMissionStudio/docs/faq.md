# Frequently asked questions

Short answers to the questions of new users, with links to the details.

## Contents

- [What is SpaceMissionStudio?](#what-is-spacemissionstudio)
- [Do I need to know programming, or spaceflight?](#do-i-need-to-know-programming-or-spaceflight)
- [Which systems does it run on?](#which-systems-does-it-run-on)
- [Does it need the internet?](#does-it-need-the-internet)
- [Where does the space weather come from?](#where-does-the-space-weather-come-from)
- [How accurate is it?](#how-accurate-is-it)
- [Orbit only or full attitude?](#orbit-only-or-full-attitude)
- [How long can a run be, and how long does it take?](#how-long-can-a-run-be-and-how-long-does-it-take)
- [Can I exchange data with other tools?](#can-i-exchange-data-with-other-tools)
- [Can I use it from Python?](#can-i-use-it-from-python)
- [Does it comply with ECSS or CCSDS standards?](#does-it-comply-with-ecss-or-ccsds-standards)
- [Who wrote it, and under what licence?](#who-wrote-it-and-under-what-licence)
- [Why does every command show an INFO line?](#why-does-every-command-show-an-info-line)

## What is SpaceMissionStudio?

A desktop app to plan and simulate satellite missions. It calculates
orbits, pointing, power, radio links, station keeping, formations,
lifetime, budgets and temperatures. It also holds the spacecraft's 3D
model and does design checks on it.

[Basilisk](https://avslab.github.io/basilisk/) calculates every number.
Basilisk is the open-source astrodynamics framework of the AVS Lab
(University of Colorado Boulder). SpaceMissionStudio adds the windows,
the forms, the plots, the templates and the checks.

## Do I need to know programming, or spaceflight?

No. Start from a template and change it in the forms
([Getting started](getting-started.md)). The [glossary](glossary.md)
explains the terms. Python is optional: use it for scripts and batch
runs.

## Which systems does it run on?

| System | Installer | From source |
|---|---|---|
| Linux x86_64, glibc 2.34 or newer | The `.deb` | Yes, Python 3.14 |
| Linux aarch64, glibc 2.34 or newer | No | Yes, Python 3.14 |
| Windows 10 or 11, x86_64 | The setup program | Yes, Python 3.14 |
| macOS | No | Not supported |

The installers contain Python 3.14. CI runs the tests on Linux and
Windows. Details: [Getting started, section 1](getting-started.md#1-what-you-need).

## Does it need the internet?

Not with the installers: they contain Python, Basilisk and the reference
data. From source, you need the internet one time, to install and to get
the reference data. After that, the app works offline:

- A run never downloads. If a file is missing, the run stops and names
  the file.
- Nothing downloads without your consent. At each start, the card
  **Fetch or update reference data?** on **Home** offers newer data.
  **Not now** uses no network.
- A download in the **Reference data** window asks first. It names the
  source, the files and the size. The default answer is No.
- On the command line, only these commands download: `kernels-status`,
  `earth-orientation --fetch`, `small-bodies --fetch`,
  `gaseous-attenuation --fetch` and `spaceweather-download`.
- You can install each file from disk, for a computer that is never
  online.
- Offline mode stops all downloads: **Settings › Network › Work offline:
  no downloads**, or `spacemissionstudio network --offline on`. An
  administrator can set it for all users of a computer with a policy file.
- There is no telemetry: no usage statistics, no crash reports, no update
  checks.

See [Network use and offline mode](reference/network.md),
[Reference data](user-manual/reference-data.md) and
[`packaging/README.md`](../packaging/README.md).

## Where does the space weather come from?

From real data only. The app contains CelesTrak's record of the observed
solar flux (F10.7) and geomagnetic index (Ap), and its 45-day forecast.
After that, it uses NASA MSFC's prediction of the solar cycle. There is
no synthetic profile.

A run after the end of the record shows
`WARNING: space weather uses MSFC's prediction (...)`. This is normal.

## How accurate is it?

As accurate as Basilisk and its inputs. The checks of the app are in
[`compliance/`](../compliance/README.md): validation runs against GMAT,
IERS and SOFA reference values. These checks found two accuracy defects
in Basilisk, and the app works around them.

The [template catalog](../spacemissionstudio/scenarios/templates/README.md)
says what a real run of each template measured. The known gaps are in
[Known limitations](reference/limitations.md).

## Orbit only or full attitude?

| Mode | Simulates | Use it for |
|---|---|---|
| **Orbit only** | Where each spacecraft goes | Orbits, drag, station keeping, formations, ground passes. It is fast. |
| **Full attitude** | Also where each spacecraft points | Sensors, wheels, torque rods, pointing modes, surface facets, power. It is slower. |

Start with orbit only. Change to full attitude when you need pointing.

## How long can a run be, and how long does it take?

A run can be up to about 10 years. A run longer than 100 days is cut
into segments, which the app joins. For a long run, set **Record every**
(**Scenario › Environment**), or the results fill the memory.

| Run | Time |
|---|---|
| Template 22: one day, orbit only | About 5 s |
| Five years of LEO station keeping | About 50 minutes |

Mission sequences, phasing keeping, ROE formations, optical navigation,
runs around a small body and Monte Carlo batches are limited to 100 days.

## Can I exchange data with other tools?

Yes, through standard files:

| Data | Format | How-to |
|---|---|---|
| Orbits, in and out | CCSDS OPM, OMM and OEM; TLE (in only) | [Orbit files](user-manual/orbit-files.md) |
| A spacecraft from a concurrent design | An IDM-CIC model (`.idm`, read only; IDM-CIC is © CNES) | [Import from IDM-CIC](user-manual/idm-cic.md) |
| 3D shapes, in and out | Wavefront `.obj` | [3D model](user-manual/3d-model.md) |
| Results | CSV in SI units | [Read the results](user-manual/read-the-results.md) |
| Scenarios | JSON | [Build your own scenario](user-manual/build-your-own-scenario.md) |
| Attitude flight software | A C project with an interface control document | [Flight software and SIL](user-manual/flight-software-and-sil.md) |

There is no direct link to other applications. [Tips](tips.md#files-the-app-reads-and-writes)
lists each file that the app reads and writes.

## Can I use it from Python?

Yes. Use one of these:

- [`examples/`](../examples/README.md): scripts that build a scenario,
  run templates, plan a Hohmann transfer, sweep altitudes and read a
  Monte Carlo batch.
- `spacemissionstudio.api` ([The Python API](api.md)): load, check and
  run a scenario; get its lifetime, budget, comparisons, design checks,
  model analyses and re-entry estimate.
- The command line ([Use the command line](user-manual/command-line.md)).
  It uses the same engine as the app.

## Does it comply with ECSS or CCSDS standards?

The project keeps records of how it applies ECSS-E-ST-40C,
ECSS-Q-ST-80C, ECSS-E-ST-10-09C, ECSS-E-ST-10-04C and CCSDS 502.0-B-3.
The records are requirements, design, verification, a compliance matrix
and the deviations, in [`compliance/`](../compliance/README.md). They
are the project's own records, not a certification by an outside body.

## Who wrote it, and under what licence?

Claude, Anthropic's AI model, wrote the application, its tests and its
documentation, through Claude Code. A person reviewed the work and
chose what to build and to merge.

From the release after 2.6.0, the licence is the European Union Public
Licence v. 1.2 (EUPL-1.2, [`LICENSE`](../LICENSE), German text
[`LICENSE.de`](../LICENSE.de)). Releases 1.0.0 to 2.6.0 stay under the
ISC licence. Basilisk keeps its own ISC licence and its copyright
holders.

## Why does every command show an INFO line?

The line `INFO ... Logging to ~/.spacemissionstudio/logs/...log` gives
the log file of the command. It is not an error.
[Troubleshooting](troubleshooting.md#messages-that-are-normal) lists the
other normal messages.

---

**Next:** [Troubleshooting](troubleshooting.md) ·
[Glossary](glossary.md) ·
[Documentation index](README.md)
