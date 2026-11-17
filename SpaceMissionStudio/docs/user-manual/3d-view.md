# See it in 3D

**Results › 3D View** shows the last run in 3D, or a run while it runs.
It is part of the app: nothing to install, nothing downloaded, nothing
sent anywhere.

- **What it shows:** the Earth (NASA's Blue Marble, turning, lit by the
  Sun, with its atmosphere's rim) under NASA's star map, the Moon, each
  spacecraft (its [3D model](3d-model.md), or a 1 m cube without one)
  turned by the run's attitude, with its path, trail, body axes, arrows
  to the Sun, to nadir and along its velocity, its instruments' fields
  of view and its thrusters' plumes; the ground stations (a glyph and a
  name, a line to each spacecraft they see, and a ring on the surface:
  what they see above their minimum elevation at that spacecraft's
  altitude, brighter while it is in view); the ground track (on by
  default: solid where flown, dashed where still to fly); labels; and a
  panel with the UTC time, the speed and the followed spacecraft's
  altitude and speed.
- **Globe, Map or Both** (`G`, `M`, `B`; also **View > 3D View**): the
  globe, a flat [map](#the-2d-map) of the ground tracks, or both side by
  side. Your choice is kept.
- **Play** (Space) plays the run. The speed beside it is simulated time
  per second; it starts at the speed that plays the whole run in about
  30 s.
- **The slider** picks a time. It and the shared time cursor move
  together: click a plot or the Timeline and the view follows; pause or
  drag here and the plots' cursor follows.
- **View** (`[` and `]`): **Whole orbit** (the spacecraft drawn larger
  than they are; the note says by how much), **Follow** a spacecraft (true
  size), **Earth-fixed** (the camera turns with the Earth), or **From** a
  spacecraft along a body axis or an instrument, with its field of view.
- **Colours**: the 3D model's own colours, or, after Run › Thermal has
  solved this run, **Temperature: <case>**: each part in its thermal
  node's temperature at the time shown, with a colour bar in °C
  ([Thermal analysis](thermal.md#see-the-temperatures-as-the-run-plays-back)).
- **Show** switches each part on or off, remembered for next time, and
  **Reduced quality** (chosen by itself without a graphics card, or when
  frames are slow; your own choice is kept).
- Drag to turn the view, scroll to zoom, right-drag to pan, double-click
  or Home to reset.
- **Open in Own Window** (the last button of the row, or `Ctrl+Shift+D`):
  the same view in a window of its own, with its run, camera and
  playback; a run shown live goes on there. `Ctrl+Shift+D` in that
  window, **Bring Back** or closing the window puts it back
  ([Open a view in its own window](../../USER_MANUAL.md#open-a-view-in-its-own-window)).

## The 2D map

The map shows the same run at the same time as the globe, on NASA's Blue
Marble, flat (equirectangular: longitude across, latitude up).

- Each spacecraft's ground track in its colour: solid where it has flown,
  dashed where it is still to fly. A dot ringed light and dark shows
  where it is now. The legend names the colours.
- Each ground station: its glyph and name, a line to each spacecraft it
  sees, and its visibility circle for each spacecraft at that
  spacecraft's altitude now (the area where the spacecraft is above the
  station's minimum elevation). The circle is green and thicker while the
  spacecraft is in view.
- The night side is shaded. A grid marks every 30°.
- Latitudes are geocentric (from the Earth's centre), as on the globe:
  at most about 0.19° from the geodetic latitude of a map or GPS.
- **Show** (on the map's bar) switches the tracks, the stations, day and
  night, the grid and the labels; your choice is kept.
- It follows **Play**, the slider and the time cursor, and it is drawn
  live while a run runs.
- **Open in Own Window** (on the map's bar, or **View > Own Windows >
  Open Map in Own Window**): the map in a window of its own, with its own
  **Play** (Space) and the time; **Go live** is End. Bring it back as any
  view; it then shows beside the globe.

## While it runs

Check **Show in 3D View while running** on the Run area's **Run** page
(remembered). The next single run opens the 3D View and is drawn as it
is computed, with a **LIVE** badge: the spacecraft and their growing
paths and ground tracks, the Earth turning, the Sun moving; on the map
too.

- **Pace** (beside it): **As fast as possible**, or **1×** to **1000×
  real time**, so a run can be watched; it can change during the run.
- **Pause** (Space), the slider or the time cursor go back while the run
  goes on; **Go live** (End) returns to the newest state.
- At the end, or on **Cancel**, the run's result replaces what was drawn
  live, in the same view.
- Ordinary runs, Mission Sequences and runs over 100 days; not SIL.
  Watching does not change the run's results.

A spacecraft without an attitude in the run (a translation-only run) is
drawn aligned with the inertial axes, and the note says so. The Earth's
turning, the Sun and the Moon are drawn from standard formulas (the Earth
rotation angle, the Astronomical Almanac's solar and lunar positions),
close enough to see where things are, not to measure them: the plots and
exports hold the run's numbers.

## Limits

- After a run the 3D View keeps up to 1,500 frames spread over it.
- Live, it shows each spacecraft's state about 200 times an orbit (at
  most every dynamics step); between two states the spacecraft does not
  move.

**More detail:** User Manual section 9,
[3D visualization](../../USER_MANUAL.md#9-3d-visualization).

---

**Next:** [Read the results](read-the-results.md) ·
[Flight software and SIL](flight-software-and-sil.md)
