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

**None yet** marks a feature without a template. "Batch B" is the next
set of templates (`BACKLOG.md`, "Templates for every feature, batch B").

## Scenario and environment

| Feature | Where | Templates |
|---|---|---|
| Orbit only | Scenario › General | 01-05, 08, 09, 16, 18, 22, 24, 25, 29-31, 37, 39, 40, 42 |
| Full attitude | Scenario › General | 06, 07, 10-15, 17, 19-21, 23, 26-28, 32-36, 41 |
| Earth as the central body | Scenario › Environment | all except 30 and 31 |
| Mars as the central body | Scenario › Environment | 30 |
| A small body (433 Eros) with polyhedral gravity | Scenario › Environment | 31 |
| Spherical-harmonics gravity | Scenario › Environment | 02-08, 15, 18-29, 32-37, 39-42 |
| Sun and Moon as third bodies | Scenario › Environment | 02-08, 14, 15, 18-37, 39-42 |
| Drag, NRLMSISE-00 with real space weather | Scenario › Environment | 04, 05, 07, 08, 18, 21-29, 32-37, 40 |
| Drag, tabular atmosphere (a published profile) | Scenario › Environment | 42 |
| Drag, exponential atmosphere | Scenario › Environment | 42 ("Try changing" only) |
| Solar activity at the 95th or 5th percentile, or a local space-weather file | Scenario › Environment | None yet |
| Solar radiation pressure | Orbit / mass | 03-05, 07, 08, 21-24, 26-29, 32-36 |
| Sunlight that Earth reflects onto the sun sensors (albedo) | Scenario › Environment | 14 ("Try changing" only) |
| Ground stations and passes | Ground stations | 19, 22, 23, 26, 35, 36 |
| Random seed of the noise | Scenario › Environment | 41 (navigation error seed); every template with sensors uses the default |
| Long runs chained past Basilisk's 104 days | Scenario › Environment, Duration | None yet (the longest template runs 90 days: 05) |

## Orbits

| Feature | Where | Templates |
|---|---|---|
| Orbit as classical elements, true anomaly | Orbit / mass | all but 39's first two spacecraft |
| Orbit as classical elements, mean anomaly | Orbit / mass | 04, 05, 24 |
| Orbit as a Cartesian state vector | Orbit / mass | 39 |
| Orbit as a TLE | Orbit / mass | 39 |
| Orbit from a CCSDS OPM or OMM | Import CCSDS OPM/OMM..., `ccsds-import` | 39 (its description points to it) |
| Orbits written as CCSDS OPM, OMM and OEM | Export Orbits as CCSDS..., `ccsds-export`, `run --oem` | any template |
| A Sun-synchronous orbit | Orbit / mass, Compute inclination | 01, 05-10, 12, 15, 18-29, 32-37, 39-42 |
| Walker constellation generator | Generate Walker constellation... | 04 |
| Phasing formation generator | Generate phasing formation... | 05 |

## Orbit control and propulsion

| Feature | Where | Templates |
|---|---|---|
| Altitude station keeping | Power / propulsion / link budget | 05, 18, 24, 29, 32 |
| GEO station keeping | Power / propulsion / link budget | 03 |
| Phasing keeping (drift orbit, mean elements) | Power / propulsion / link budget | 05, 24 |
| Formation in relative orbital elements | Power / propulsion / link budget | 29 |
| Continuous low thrust (`constant_thrust`) | Power / propulsion / link budget | 40 |
| Thrusters and a fuel tank | Sensors / actuators | 11, 12, 17 |
| Mission Sequence: propagate, maneuver, report | Mission sequence | 08, 16, 23 |
| Mission Sequence: Lambert transfer | Mission sequence | 16 |
| Mission Sequence: stop at a pass | Mission sequence | 23 |
| Mission Sequence: assignment, if, while, script block | Mission sequence | None yet |

## Attitude, sensors and actuators

| Feature | Where | Templates |
|---|---|---|
| `inertial3D` pointing | Attitude control | 11, 12, 13, 17 |
| `hillPoint` pointing | Attitude control | 06, 26, 35, 36 |
| `velocityPoint` pointing | Attitude control | 41 |
| `sunSafePoint` pointing | Attitude control | 07, 14, 20, 21, 23, 27, 28, 32-34 |
| `locationPointing` at a body | Attitude control | 15 |
| Sun pointing that turns to a ground station in a pass | Attitude control, Comms pointing | 19 |
| Control gains set by hand | Attitude control | 35, 36 |
| Navigation error | Attitude control | 41 |
| Star tracker | Sensors / actuators | 07, 20, 23, 26-28, 32-36, 41 |
| IMU | Sensors / actuators | 07, 20, 23, 26-28, 32-36, 41 |
| Coarse sun sensors, and the Sun heading estimated from them | Sensors / actuators | 07, 14, 20, 21, 23, 26-28, 32-36 |
| Magnetometer | Sensors / actuators | 41 |
| Thermal sensor | Sensors / actuators | 20 |
| Sensor faults | Sensors / actuators | None yet |
| Reaction wheels | Sensors / actuators | 07, 12-14, 20, 21, 23, 26-28, 32-36, 41 |
| Wheel motor temperature | Sensors / actuators | 20 |
| Magnetic torque rods and momentum management | Sensors / actuators | 13, 21, 23, 26, 27, 33-36 |
| Momentum dumping with thrusters | Attitude control | 12 |
| Gravity-gradient torque | Orbit / mass | 10 |
| Surface facets (drag and sunlight torques) | Orbit / mass | 21, 23, 26-28, 32-36 |
| Flexible solar arrays | Power / propulsion / link budget | 27, 34 |

## Power, link, data and operations

| Feature | Where | Templates |
|---|---|---|
| Power: panels, battery, eclipses | Power / propulsion / link budget | 07, 19, 20, 23, 26-28, 32-36 |
| Radio link margin | Power / propulsion / link budget | 19, 23, 26, 35, 36 |
| Instruments, memory and downlink | Data handling | 26, 35, 36 |
| Operations planning (targets, passes, scheduler, flying the plan) | Run › Plan | 35, 36 |
| Equipment list and power budget (the Budgets area) | Budgets | None yet (template 38 is in a separate change) |

## The spacecraft as designed

| Feature | Where | Templates |
|---|---|---|
| 3D model from boxes, prisms, cones and panels | 3D model | 28, 32-34 |
| 3D model from cylinders and spheres | 3D model | None yet |
| 3D model from an imported `.obj` mesh | 3D model | None yet (batch B) |
| Import from IDM-CIC (synthetic file only) | 3D model, `idm-import` | None yet (batch B) |
| Design checks: fields of view, plume, mass budget, launcher envelope | Run › Design Checks | 32 |
| Model analyses in a run: disturbance torques, shading | Results › Model Analyses | 32 |
| Thermal analysis | Run › Thermal | 33, 34 |
| Pointing error budget | Budgets › Pointing, `budgets --pointing` | None yet (batch B) |

## Navigation

| Feature | Where | Templates |
|---|---|---|
| Optical navigation from a planet's disk | Power / propulsion / link budget | 30 |
| Landmark navigation around a small body | Power / propulsion / link budget | 31 |

## Uncertainty

| Feature | Where | Templates |
|---|---|---|
| Monte Carlo batch | Monte Carlo | 09, 25, 37 |
| Dispersion of dry mass, orbit elements, drag coefficient | Monte Carlo | 09, 25, 37 |
| Dispersion of attitude, inertia, body rate, SRP coefficient, density scale | Monte Carlo | None yet (batch B) |
| Batch seed, requirements, statistics, sensitivity, report | Monte Carlo | 37 |
| Thermal Monte Carlo | Run › Thermal | 34 |

## End of life, budgets and traceability

| Feature | Where | Templates |
|---|---|---|
| Lifetime estimate | Run › End of Life, `lifetime` | any template with drag; 22 and 42 describe it |
| Lifetime with the tabular atmosphere | Run › End of Life | 42 |
| Re-entry casualty estimate | Run › End of Life | 28, 32-34 (any template with a 3D model) |
| Propellant budget (ESA AD10) | Budgets › Propellant, `budget` | 18 (the User Manual's example) |
| Flight-software export and software in the loop | Reports › Flight Software, `export-fsw`, `sil` | any template with an attitude mode |
| Assumptions: named parameters and a project configuration | Scenario › Assumptions | None yet (batch B) |
| Plugins | Scenario › Assumptions | None yet (batch B) |

## Still without a template

Batch B adds templates for these, as the owner asked:

- a 3D model from an imported `.obj` mesh;
- an IDM-CIC import, from a synthetic file only;
- the other Monte Carlo dispersions: attitude, inertia, body rate, SRP
  coefficient and the atmospheric density scale;
- plugins and project parameters (a project configuration);
- the pointing error budget (Budgets › Pointing).

These are without a template too, and batch B lists them:

- solar activity at the 95th or 5th percentile, or a local space-weather
  file;
- long runs chained past Basilisk's 104 days;
- Mission Sequence assignment, `if`, `while` and script blocks;
- sensor faults;
- a 3D model from cylinders and spheres;
- the equipment list and power budget, if template 38 does not land.

The exponential atmosphere and the albedo on the sun sensors are shown
only in a "Try changing" (templates 42 and 14).
