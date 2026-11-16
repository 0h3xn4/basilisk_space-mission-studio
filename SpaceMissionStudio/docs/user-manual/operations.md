# Operations planning

Plan what your spacecraft do over days or weeks: which targets they image
and when, which ground-station passes they use to send the data down, when
they calibrate. Then fly the plan in the simulation and check it,
export the products an operations team works with, and plan again when
something goes wrong.

The planner works from the scenario's `operations` section. It finds the
opportunities (target windows, station passes, eclipses), places the
activities with a deterministic scheduler, and tells you why it could not
place a request. A plan is a planning product, not a command load: no
telecommand is ever written.

Two templates show it: **35 - Operations: a week of an Earth
observation microsatellite** and **36 - Operations: three imagers sharing
two stations**. The method is described in
[the operations model](../models/operations.md); what was checked, and
how well it agrees, is in
[the V&V record](../../compliance/validation/operations-vv.md).

## Plan a week of operations

1. Open template 35 (**Home**, or **File › New from template**).
2. Go to **Run › Plan** and press **Plan**. The planner builds the
   geometry from an orbit-only propagation of the week (about 12 s),
   finds the target windows and passes, and schedules (about half a
   minute with the template's 20 improvement steps).
3. Read the chart. Each spacecraft has four rows: its activities (with
   the slew before each as a thin bar), its eclipses, its state of
   charge (the dashed line is the planned floor) and its memory. Each
   ground station has a row with its passes (pale) and the contacts
   planned in them. Scroll the mouse wheel to zoom; Shift+wheel or a
   right-button drag moves along the week; **Fit** (or `0`) shows it all.
4. Read **Requests not placed**: every target or request the plan does
   not hold, with the reason (no window, conflict, slew, station busy,
   battery, memory, a per-orbit or per-day limit, too short, ...). Hover
   the reason to see how often each reason applied. The same requests
   are listed in the **Problems** panel. Unused passes are listed on the
   page only.
5. Move the time cursor (click on the chart, or anywhere a run's time
   is shown): **Plan status at the time cursor** gives, per spacecraft,
   the activity in progress and the next one, the pointing mode, the
   planned state of charge and memory, and how many activities are done.
6. The plan's activities are also on the **Timeline**, under
   **Planned activities**.

To change what the plan asks for, edit the `operations` section in
**Scenario › JSON** (completion and help know every field): add a target,
change a priority, the off-nadir limit, the contact time per day, a
station's mask or capacity. Then press **Plan** again. The customize
wizard of templates 35 and 36 offers the most useful of these.

### Fix an activity by hand

Click an activity on the chart (or a row of **Activities**) to select it.

- **Lock** keeps it where it is the next time you plan. The lock is saved
  in the scenario (`operations.locked`), so it is undone with **Edit ›
  Undo** and seen by the command line.
- **Unlock** takes the lock away.
- Drag the activity along its row to move it. It can only move within its
  window or pass. When you let go, it is locked at its new time and the
  rest of the plan is made again.
- **Delete** takes it out of the plan shown. The other activities are
  checked again in time order and keep their ids.

### Geometry from the last run

By default the geometry comes from the section's `geometry.source`:
`propagation` (an orbit-only Basilisk run with the scenario's force
model), or `analytic` (mean elements with J2, within about 7 km of the
propagation over a day; fast, for a first look). Tick **Geometry from
the last run** to use the trajectory of the run you made (the run must
cover the horizon).

## Fly and verify a plan

1. With a plan shown, press **Fly and verify** (the **Fly and verify**
   group). The simulation runs from the scenario's epoch to the plan's
   end, with the plan executor switching the pointing and the devices at
   the planned times; the attitude comes from the spacecraft's own
   guidance and control. **Stop** ends the flight at the next step.
2. The flags list says what is beyond the verification's tolerances:
   a slew not finished at an activity's start (pointing error above
   the convergence threshold, 5 deg), a target's off-nadir angle or Sun
   elevation more than 1 or 0.5 deg from the plan, a state of charge more
   than 5 points away, a memory more than 2 % of its capacity away.
   Nothing listed means the flight did what the plan said.
3. The tables give each activity's pointing error at its start and its
   largest, the planned and flown off-nadir angles, the lowest link
   margin of a contact; and per spacecraft the largest differences in
   state of charge and memory.
4. With a flight done, **Plan status at the time cursor** also shows the
   flown mode and pointing error at the cursor.

A week of template 35 takes about ten minutes to fly. To check a
change quickly, plan a shorter horizon first.

On the command line:

```
spacemissionstudio plan schedule my_scenario.json --plan-out plan.json
spacemissionstudio plan verify my_scenario.json plan.json --out products --strict
```

`--strict` exits with 1 when anything is flagged.

## Export operations products

Press **Export...** and choose a folder. It receives:

| File | What it holds | Standard |
|---|---|---|
| `passes.csv` | Every pass of every planned spacecraft: AOS, LOS, the highest elevation and its time, the predicted link margins, and the contact planned on it | CSV |
| `passes.ics` | The contacts as calendar events | iCalendar (RFC 5545) |
| `activities.csv`, `activities.json` | The activity timeline with the predicted geometry, and the requests not placed | CSV; JSON documented in [the model](../models/operations.md#the-activity-timeline) |
| `commands.json`, `commands.csv` | The time-tagged requests that would fly the plan: pointing, instruments, transmitter, loads, maneuvers | ECSS-E-ST-70-41C service 11 terminology; a planning product, not telecommands |
| `pointing.csv` | Each contact's azimuth, elevation and range from the station | CSV |
| `<spacecraft>.oem` | The planned trajectory | CCSDS OEM (502.0-B-3) |
| `<spacecraft>.aem` | The planned attitude | CCSDS AEM 2.0 (504.0-B-2) |
| `report.md` | The plan in words: the activities, the requests not placed and why, the resources, the verification when there is one | Markdown |

Each file carries its provenance (the tool version, the scenario's
SHA-256, the geometry, the seed and the plan's SHA-256): CSV files in a
`.provenance.json` beside them, the others inside. **Save plan...**
writes the plan file itself (`spacemissionstudio-plan` JSON), which
**Open plan...** and the command line read back.

On the command line: `spacemissionstudio plan export my_scenario.json
plan.json --out products`.

## Replan after a lost pass

A pass is lost (the station is down, the antenna did not acquire). Plan
again from that moment:

1. Click the contact on the chart and press **Lose this pass**. The
   planner keeps every activity that started before the contact, marks
   that pass lost, and plans the rest of the horizon. The data that
   should have gone down stays in the memory: the memory row shows it.
2. **Replan and compare** shows the new plan against the one before:
   per spacecraft the activities, images, contact time and lowest state
   of charge, and the requests only one of the two plans holds.

To replan from any time (for example after editing the section), type a
UTC time in **Replan from (UTC)**, or leave it empty to use the time
cursor, and press **Replan**. The scenario's `what_if` events apply:
a lost pass, a station or instrument outage, an extra request brought in
(a target or request kept `enabled: false` until then), a delayed
maneuver.

```
spacemissionstudio plan replan my_scenario.json plan.json --from 2030-06-05T12:00:00Z --plan-out replan.json
spacemissionstudio plan compare my_scenario.json plan.json replan.json
```

## How robust is the plan?

**Robustness** draws, per run, lost passes (each planned contact lost
with the given probability), an offset on every link margin, a factor on
every slew time and an initial state of charge, then re-checks the plan
under those conditions (or, with **Replan each draw**, plans again). The
table gives the least, mean and most of each outcome: images and contacts
lost, the lowest state of charge, data lost, data left in the memory at
the end. The same seed gives the same draws. **Save batch...** saves the
draws so the Monte Carlo view shows their state of charge and memory
over time.

## Several spacecraft

A section may plan several spacecraft. Stations serve `capacity`
spacecraft at a time (one by default). When more want a pass, the lower
`contact_priority` number wins, then the one that has had the fewest
contacts. Template 36 shows three spacecraft sharing two stations: the
station rows of the chart say whose contact each pass holds.

## Limits

The planner's models are simpler than the simulation: the slew time from
a one-axis model of the controller (planned to half the convergence
threshold, as a margin), the panel's angle to the Sun from the planned
attitude, resources at the geometry's step. Fly and verify tells you how
far that matters for your spacecraft. The plan does not model weather or
clouds, conjunctions, a ground network's costs or bookings, or binary
telecommands. See [Limitations](../reference/limitations.md#operations-planning).

---

**Next:** [Thermal analysis](thermal.md) ·
[How-to guides](README.md)
