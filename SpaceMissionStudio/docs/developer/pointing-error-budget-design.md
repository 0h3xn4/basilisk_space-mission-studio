# Pointing error budget: design (Step 0)

The owner asked for a pointing error budget (feedback, 2026-11-18). On
2026-11-19 a check found none in the app: the Budgets area has mass,
power and propellant, and phase 4 of the System Budget Studio merge plan
(`system-budget-merge-design.md`) ports only the hold power per pointing
mode. This page is Step 0: what exists, the concepts, a design, the
choices and the questions for the owner. **No code changed in this
step.** The owner chooses the scope (section 7) before any code.

- **Decisions:** `docs/DECISIONS.md`, section "Pointing error budget:
  design (2026-11-23)", decisions PE-1 to PE-9, final since the owner's
  answers of 2026-11-24; section "Pointing error budget: scope B built
  (2026-11-24)", PE-10 to PE-20.
- **Progress:** section 8.
- **Backlog:** `BACKLOG.md`, `## Needs human`.
- **Base:** `develop` at `7a9a25f` (release 2.14.1).

**Clean room.** The design uses only the public concepts of the ECSS
control performance standard, ECSS-E-ST-60-10C (15 November 2008): the
error indices, the time windows, the statistical interpretations, the
classes of contributors and the idea of a summation per index. It does
not copy another tool's name, user interface, file format or numbers.
No text or table of the standard is reproduced; the concepts are
described in our own words. **Every number has a source or is "TBD".**

## 1. What exists

| What | Where | Use for this budget |
|---|---|---|
| The Budgets area: Equipment, Power, Mass, Propellant pages; a `budgets` section per spacecraft at its own version (`BUDGETS_VERSION`) with sourced values (`SourcedValue`) | `gui/budgets_area.py`, `schema/budgets.py` | The home of a new "Pointing" page and of its data (PE-1, PE-2) |
| Sensor noise figures with their sources: star tracker `noise_arcsec` (1-sigma), gyroscope `gyro_noise_rad_s`, sun sensor `noise_std`, magnetometer `noise_std_tesla` | `engine/device_catalog.py`, scenario sensors | Knowledge contributors filled from the scenario (option B) |
| The flown attitude: Basilisk's attitude guidance error (`sigma_BR`) and rates in the run's recorded series | `engine/`, Results | Indices measured from a run (option C) |
| Monte Carlo batches with dispersions of attitude, rate and inertia | `engine/monte_carlo.py` | The ensemble view of the indices (option D, after Monte Carlo phase B) |
| Planner slews and pointing modes | `operations/attitude.py`, `engine/fsw.py` | The modes a requirement applies to |

There is no pointing requirement in the scenario, no list of error
contributors, and no index (absolute, relative, knowledge) anywhere in
the engine or the GUI.

## 2. The concepts (in our words)

**Errors.** A *performance error* is the difference between the
direction the spacecraft should point and the direction it really
points. A *knowledge error* is the difference between the direction the
spacecraft believes it points (its estimate) and the real direction.

**Time windows.** An index looks at the error over a stated window: the
*observation period* (for example the length of one image), and for a
stability index a shorter *stability time* inside it.

**Indices.** For performance (and in the same way for knowledge):
- *absolute*: the error at any instant;
- *mean*: the average of the error over an observation period;
- *relative*: the error at an instant minus the mean of its window
  (the jitter inside the window);
- *drift*: the change of the window mean between two windows a stated
  time apart;
- *reproducibility*: the difference between the window means of two
  windows a long time apart (for example one orbit or one pass).

**Statistical interpretation.** A requirement says with what
probability the error stays under its limit and over what population:
over time for one spacecraft (*temporal*), over the possible
spacecraft and conditions at one time (*ensemble*), or over both
(*mixed*). The interpretation decides how contributors combine.

**Contributors and their classes.** Each contributor (a sensor's noise,
a misalignment, a thermal distortion, a controller residual, an
actuator's jitter) has a time behaviour, which decides which indices it
enters, and a distribution:
- *time behaviour*: constant (a bias), random and stationary (noise),
  periodic (an orbit-periodic distortion), a drift, or a transient;
- *distribution*: Gaussian, uniform, or another bounded shape, given by
  a mean and a standard deviation (or bounds).

**Summation.** Per index and per axis, the contributors that enter the
index combine. For independent contributors the means add and the
variances add (the standard deviations add root-sum-square); the
correlated ones add linearly. The result is compared with the limit at
the requirement's probability level (for a Gaussian result, the
standard-normal factor of that level times the standard deviation, plus
the mean).

## 3. Design

### 3.1 Data (a new subsection of a spacecraft's `budgets`)

```
budgets.pointing
  frame:            the body axis or line of sight the budget is for
  requirements:     list of
      index:        "absolute" | "mean" | "relative" | "drift" | "reproducibility"
      kind:         "performance" | "knowledge"
      axis:         "x" | "y" | "z" | "line_of_sight" (half-cone)
      limit:        SourcedValue  [arcsec]
      probability:  SourcedValue  [-]  (for example 0.9973; "TBD" if unknown)
      interpretation: "temporal" | "ensemble" | "mixed"
      window_s:     SourcedValue  [s]  (observation period; relative, mean, drift)
      stability_s:  SourcedValue  [s]  (relative only; optional)
      modes:        the system modes it applies to (Equipment page names)
  contributors:     list of
      name, source (equipment item or "other")
      kind:         "performance" | "knowledge" | "both"
      behaviour:    "bias" | "random" | "periodic" | "drift" | "transient"
      distribution: "gaussian" | "uniform"
      mean:         SourcedValue [arcsec] per axis
      std:          SourcedValue [arcsec] per axis (or bounds for uniform)
      period_s:     SourcedValue [s] (periodic only)
      correlated_with: optional group name (adds linearly in its group)
```

Every value is a `SourcedValue`, as in the rest of `budgets`: a number
with its source, or "TBD". A missing value makes the index "TBD", never
zero.

### 3.2 Computation (a pure function in `engine/`)

For each requirement, per axis:
1. Select the contributors that enter the index, from their behaviour
   and the window (a table in the code, written from section 2, with a
   test per row): a bias enters absolute and mean, not relative; random
   noise enters absolute and relative; a periodic term enters an index
   by the share of its amplitude seen in the window; a drift enters
   drift and reproducibility.
2. Sum: means linearly, standard deviations root-sum-square, correlated
   groups linearly first.
3. The value at the requirement's probability (Gaussian factor; a
   uniform term is converted to its standard deviation first) and the
   margin against the limit.
4. A line-of-sight (half-cone) value from two axes, by a stated rule
   (PE-6).

The result is a table: index, axis, value, limit, margin, and the
contributors with their share. It is in the budget report and the CLI
like the other budgets.

### 3.3 GUI

A "Pointing" tab in the Budgets area, after Mass: the requirements as an
`EditableTable`, the contributors as an `EditableTable`, and the result
as a `DataTable` with each margin's status (icon and text, design
rule 1). Empty states with their primary action. No new dependency.

### 3.4 Records (hard rules)

The scenario format changes, so: `BUDGETS_VERSION` steps by one with a
migration (an older file opens with no `pointing`); a decisions entry;
the golden files of the templates unchanged (a template without
`pointing` gives the same outputs); the ICD and the SRS get the new
section and requirement.

## 4. Options of scope

| Option | What | Effort (estimate) |
|---|---|---|
| **A. Budget table** | Sections 3.1 to 3.4: requirements and contributors entered by hand, the summation, margins, report and CLI | about 16 hours |
| **B. A + contributors from the scenario** | A, and a button that adds the scenario's sensor noises (star tracker, gyroscope, sun sensor) as knowledge contributors with their catalog sources | A + about 6 hours |
| **C. B + indices measured from a run** | B, and the absolute, relative and mean performance errors computed from the run's attitude error series over the requirement's windows, shown next to the budget's value | B + about 12 hours |
| **D. C + ensemble from Monte Carlo** | C over a Monte Carlo batch: the index at the requirement's probability over the runs | after Monte Carlo phase B |

The estimates are this session's own, not measured.

## 5. What is not in it

Pointing *stability* requirements in the frequency domain (power
spectral densities), structural modes, and actuator micro-vibration
models are out of scope; a contributor from such an analysis is entered
by hand as a number with its source.

## 6. Risks

- **The selection table of 3.2 step 1 is where a budget goes wrong.**
  Each row gets a test with a hand-computed case, and the table is shown
  to the user as text next to each contributor.
- **Units.** Inputs in arcsec; the engine works in radians. One
  conversion at the boundary, tested.
- **False confidence.** A budget with many "TBD" values shows "TBD" for
  its indices, not a smaller number.

## 7. Questions for the owner

1. **Scope:** A, B, C or D (section 4)? This session recommends **B**
   first, then C as its own item.
2. **Default probability level** for a new requirement: "TBD" until set
   (PE-5), or a value the owner names with its source?
3. **Line of sight:** is a half-cone line-of-sight requirement needed in
   the first step, or per-axis only (PE-6)?
4. **Periodic contributors:** the window share rule of 3.2 step 1 (PE-7)
   or only "the full amplitude enters every index it can"
   (conservative, simpler)?
5. **Place:** a tab of the Budgets area (PE-1), or a page of its own?

## 8. Progress

**2026-11-24: the owner's answers.** (1) Scope B. (2) No default
probability level: a new requirement has "TBD". (3) Per axis, plus a
line-of-sight (half-cone) value from two axes by a stated rule, in this
step. (4) The window share rule for periodic contributors (PE-7). (5) A
"Pointing" tab of the Budgets area, after Mass.

**2026-11-24: scope B built** on branch `feature/pointing-budget`
(SRS-F-32; decisions PE-10 to PE-20):

| Part | Where | State |
|---|---|---|
| 3.1 Data: `budgets.pointing`, section version 2 with a migration from 1 | `schema/budgets.py` | done |
| 3.2 Computation: selection table, window shares, sum, value at the probability, margin, line of sight, "TBD" | `engine/pointing_budget.py` | done |
| 3.3 GUI: Budgets › Pointing (requirements, contributors, result with status, Add Scenario Sensors, Copy as CSV) | `gui/budgets_area.py` (`PointingPage`) | done |
| 3.4 Records: decisions, ICD (generated), SRS-F-32, user manual, golden files unchanged | `docs/`, `compliance/docs/` | done |
| Report and CLI: `budgets --pointing` (`--csv`), `api.pointing_budget` | `cli.py`, `api.py` | done |
| Option B: the scenario's star trackers, gyroscopes and sun sensors as knowledge contributors | `engine/pointing_budget.py` (`sensor_contributors`) | done; a gyroscope's angle is "TBD" (PE-15) |

**Next (not in this step):** option C, the indices measured from a run's
attitude error series over the requirement's windows, is its own item;
option D waits for Monte Carlo phase B. A use of the statistical
interpretation in the sum (PE-14) and an angle for a gyroscope's noise
(PE-15) need a rule from the owner.
