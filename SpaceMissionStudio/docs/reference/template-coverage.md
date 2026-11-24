# Template coverage

Each feature of the tool and the templates that show it. The owner asks
for at least one template for every feature. This page shows where that
is done and where it is not done yet.

The feature list comes from [Capabilities and verification](capabilities.md)
and from the spacecraft and scenario sections of the scenario schema
(`spacemissionstudio/schema/scenario.py`). A template "shows" a feature
when the template file uses it as shipped. A feature that only a
template's "Try changing" uses is marked so. The
[template catalog](../../spacemissionstudio/scenarios/templates/README.md)
says what each template teaches.

**No template** marks a feature that a scenario template cannot carry,
with the reason and where the feature is shown instead. Batch A
(templates 39 to 42) and batch B (templates 43 to 47) added the templates
for the other gaps.

## Scenario and environment

| Feature | Where | Templates |
|---|---|---|
| Orbit only | Scenario › General | 01-05, 08, 09, 16, 18, 22, 24, 25, 29-31, 37, 39, 40, 42, 45, 46 |
| Full attitude | Scenario › General | 06, 07, 10-15, 17, 19-21, 23, 26-28, 32-36, 41, 43, 44, 47 |
| Earth as the central body | Scenario › Environment | all except 30 and 31 |
| Mars as the central body | Scenario › Environment | 30 |
| A small body (433 Eros) with polyhedral gravity | Scenario › Environment | 31 |
| Spherical-harmonics gravity | Scenario › Environment | 02-08, 15, 18-29, 32-37, 39-45 (45: J2 only) |
| Sun and Moon as third bodies | Scenario › Environment | 02-08, 14, 15, 18-37, 39-44, 47 (14 and 47: the Sun only) |
| Drag, NRLMSISE-00 with real space weather | Scenario › Environment | 04, 05, 07, 08, 18, 21-29, 32-37, 40, 43-45 |
| Drag, tabular atmosphere (a published profile) | Scenario › Environment | 42 |
| Drag, exponential atmosphere | Scenario › Environment | 42 ("Try changing" only) |
| Solar activity at the 95th or 5th percentile, or a local space-weather file | Scenario › Environment | 45 (the 95th percentile; the 5th and a local file in its "Try changing") |
| Solar radiation pressure | Orbit / mass | 03-05, 07, 08, 21-24, 26-29, 32-36, 43, 44 |
| Sunlight that Earth reflects onto the sun sensors (albedo) | Scenario › Environment | 14 ("Try changing" only) |
| Ground stations and passes | Ground stations | 19, 22, 23, 26, 35, 36 |
| Random seed of the noise | Scenario › Environment | 41 (navigation error seed), 47 (seed 47: the magnetometer's spikes); the other templates with sensors use the default |
| Long runs chained past Basilisk's 104 days | Scenario › Environment, Duration | 45 (110 days: 90 and 20) |

## Orbits

| Feature | Where | Templates |
|---|---|---|
| Orbit as classical elements, true anomaly | Orbit / mass | all but 39's first two spacecraft |
| Orbit as classical elements, mean anomaly | Orbit / mass | 04, 05, 24 |
| Orbit as a Cartesian state vector | Orbit / mass | 39 |
| Orbit as a TLE | Orbit / mass | 39 |
| Orbit from a CCSDS OPM or OMM | Import CCSDS OPM/OMM..., `ccsds-import` | 39 (its description points to it) |
| Orbits written as CCSDS OPM, OMM and OEM | Export Orbits as CCSDS..., `ccsds-export`, `run --oem` | any template |
| A Sun-synchronous orbit | Orbit / mass, Compute inclination | 01, 05-10, 12, 15, 18-29, 32-37, 39-45 |
| Walker constellation generator | Generate Walker constellation... | 04 |
| Phasing formation generator | Generate phasing formation... | 05 |

## Orbit control and propulsion

| Feature | Where | Templates |
|---|---|---|
| Altitude station keeping | Power / propulsion / link budget | 05, 18, 24, 29, 32 |
| GEO station keeping | Power / propulsion / link budget | 03 |
| Phasing keeping (drift orbit, mean elements) | Power / propulsion / link budget | 05, 24 |
| Formation in relative orbital elements | Power / propulsion / link budget | 29 |
| Continuous low thrust (`constant_thrust`) | Power / propulsion / link budget | 40, 46 |
| Thrusters and a fuel tank | Sensors / actuators | 11, 12, 17 |
| Mission Sequence: propagate, maneuver, report | Mission sequence | 08, 16, 23, 46 (propagate and report) |
| Mission Sequence: Lambert transfer | Mission sequence | 16 |
| Mission Sequence: stop at a pass | Mission sequence | 23 |
| Mission Sequence: assignment, if, while, script block | Mission sequence | 46 |

## Attitude, sensors and actuators

| Feature | Where | Templates |
|---|---|---|
| `inertial3D` pointing | Attitude control | 11, 12, 13, 17 |
| `hillPoint` pointing | Attitude control | 06, 26, 35, 36 |
| `velocityPoint` pointing | Attitude control | 41 |
| `sunSafePoint` pointing | Attitude control | 07, 14, 20, 21, 23, 27, 28, 32-34, 44, 47 |
| `locationPointing` at a body | Attitude control | 15 |
| Sun pointing that turns to a ground station in a pass | Attitude control, Comms pointing | 19 |
| Control gains set by hand | Attitude control | 35, 36 |
| Navigation error | Attitude control | 41 |
| Star tracker | Sensors / actuators | 07, 20, 23, 26-28, 32-36, 41 |
| IMU | Sensors / actuators | 07, 20, 23, 26-28, 32-36, 41 |
| Coarse sun sensors, and the Sun heading estimated from them | Sensors / actuators | 07, 14, 20, 21, 23, 26-28, 32-36, 47 (the sensors) |
| Magnetometer | Sensors / actuators | 41, 47 |
| Thermal sensor | Sensors / actuators | 20, 47 |
| Sensor faults | Sensors / actuators | 47 (a sun sensor stuck at its largest output, a spiking magnetometer axis, a thermal reading stuck at a value) |
| Reaction wheels | Sensors / actuators | 07, 12-14, 20, 21, 23, 26-28, 32-36, 41, 44, 47 |
| Wheel motor temperature | Sensors / actuators | 20 |
| Magnetic torque rods and momentum management | Sensors / actuators | 13, 21, 23, 26, 27, 33-36 |
| Momentum dumping with thrusters | Attitude control | 12 |
| Gravity-gradient torque | Orbit / mass | 10 |
| Surface facets (drag and sunlight torques) | Orbit / mass | 21, 23, 26-28, 32-36, 43 |
| Flexible solar arrays | Power / propulsion / link budget | 27, 34 |

## Power, link, data and operations

| Feature | Where | Templates |
|---|---|---|
| Power: panels, battery, eclipses | Power / propulsion / link budget | 07, 19, 20, 23, 26-28, 32-36 |
| Radio link margin | Power / propulsion / link budget | 19, 23, 26, 35, 36 |
| Instruments, memory and downlink | Data handling | 26, 35, 36 |
| Operations planning (targets, passes, scheduler, flying the plan) | Run › Plan | 35, 36 |
| Equipment list and power budget (the Budgets area) | Budgets | 38 |

## The spacecraft as designed

| Feature | Where | Templates |
|---|---|---|
| 3D model from boxes, prisms, cones and panels | 3D model | 28, 32-34 |
| 3D model from cylinders and spheres | 3D model | 43 |
| 3D model from an imported `.obj` mesh | 3D model | 43 (a synthetic camera in millimetres, `scenarios/meshes/43_synthetic_camera.obj`) |
| Import from IDM-CIC (synthetic file only) | 3D model, `idm-import` | No template: the import reads a model file of another format into a scenario, and a template is the scenario itself. Shown by the importer's synthetic test fixtures (`tests/idm_fixtures.py`) and [Import a spacecraft from IDM-CIC](../user-manual/idm-cic.md) (decision TPL-B6) |
| Design checks: fields of view, plume, mass budget, launcher envelope | Run › Design Checks | 32 |
| Model analyses in a run: disturbance torques, shading | Results › Model Analyses | 32 |
| Thermal analysis | Run › Thermal | 33, 34 |
| Pointing error budget | Budgets › Pointing, `budgets --pointing` | 38 |

## Navigation

| Feature | Where | Templates |
|---|---|---|
| Optical navigation from a planet's disk | Power / propulsion / link budget | 30 |
| Landmark navigation around a small body | Power / propulsion / link budget | 31 |

## Uncertainty

| Feature | Where | Templates |
|---|---|---|
| Monte Carlo batch | Monte Carlo | 09, 25, 37, 44 |
| Dispersion of dry mass, orbit elements, drag coefficient | Monte Carlo | 09, 25, 37 |
| Dispersion of attitude, inertia, body rate, SRP coefficient, density scale | Monte Carlo | 44 |
| Batch seed, requirements, statistics, sensitivity, report | Monte Carlo | 37 (all), 44 (seed, statistics, sensitivity) |
| Thermal Monte Carlo | Run › Thermal | 34 |

## End of life, budgets and traceability

| Feature | Where | Templates |
|---|---|---|
| Lifetime estimate | Run › End of Life, `lifetime` | any template with drag; 22 and 42 describe it |
| Lifetime with the tabular atmosphere | Run › End of Life | 42 |
| Re-entry casualty estimate | Run › End of Life | 28, 32-34 (any template with a 3D model) |
| Propellant budget (ESA AD10) | Budgets › Propellant, `budget` | 18 (the User Manual's example), 38 (a tank and a specific impulse) |
| Flight-software export and software in the loop | Reports › Flight Software, `export-fsw`, `sil` | any template with an attitude mode |
| Assumptions: named parameters and a project configuration | Scenario › Assumptions | 44 ("Try changing" only). No template carries a configuration file: it is named relative to the scenario's folder, so a template saved elsewhere or customized would lose it and no longer validate. Shown by [Change a parameter](../user-manual/project-configuration.md) and its tests (decision TPL-B6) |
| Plugins | Scenario › Assumptions, `plugins` | No template: a plugin is a Python package installed next to the app, which a scenario file cannot carry. [Add your own models and rules](../user-manual/plugins.md) has a complete example that `tests/test_plugins.py` runs (decision TPL-B6) |

## Without a template

Three features have no template, because a scenario template cannot
carry them (decision TPL-B6):

- an IDM-CIC import: the import makes a scenario's 3D model from a file
  of another format; the importer's synthetic test fixtures and its
  how-to page show it;
- plugins: a plugin is a Python package installed next to the app;
- a project configuration: a file named relative to the scenario's
  folder, which a template saved elsewhere or customized would lose.
  Template 44's "Try changing" sets a parameter in one after Save As.

These are shown only in a "Try changing": the exponential atmosphere
(42), the albedo on the sun sensors (14), the 5th percentile and a local
space-weather file (45), and a project configuration (44).
