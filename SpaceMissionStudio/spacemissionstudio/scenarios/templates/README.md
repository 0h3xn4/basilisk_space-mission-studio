# Template missions

Ready-to-run scenario files. Use them to learn the app and orbital
mechanics, and as start points for your own missions. There are 47
templates in nine categories.

**New here?** Run 22, then 01. Then continue down the catalog. For your
own mission, open 22 or 23 and save it under a new name.

## Open a template

| Where | How |
|---|---|
| The app | On **Home**, click the card of the template, then **Open template**. Or use **File › Open...** (`Ctrl+O`). |
| The app, with changes | On the card, click **Customize and open...**. Change the key settings, then click **Open in editor**. |
| The command line | `spacemissionstudio run spacemissionstudio/scenarios/templates/22_starter_first_leo_satellite.json --out-dir out` |
| A check without Basilisk | `spacemissionstudio validate spacemissionstudio/scenarios/templates/22_starter_first_leo_satellite.json` |

The app never changes a template file. Before you edit a template, save
it under a new name (**File › Save As...**).

Each template has a `description`. It tells what the template shows,
what to look at after the run, and what to change. The app shows it on
the card on **Home** and on the **General** page of the **Scenario**
area.

Templates with drag (04, 05, 07, 08, 18, 21) use a drag coefficient of
3.0, the value of ESA AD10 for operations (Sec. 5.2). **Run › End of
Life** and `spacemissionstudio lifetime` use the end-of-life value 2.2.

## Catalog

The templates are in categories, and in each category from simple to
advanced. **Home** shows them in the same order. The numbers are
identifiers: they give the order in which the templates were added. No
template needs another template to run first.

`spacemissionstudio/scenarios/catalog.py` holds the categories and the
order. `tests/test_template_catalog.py` checks that this list agrees
with it. `tests/test_template_claims.py` checks the values that each
description claims, with real runs.

### Getting started

Starting points for your own mission, and the simplest orbits.

| # | File | Teaches |
|---|------|---------|
| 22 | `22_starter_first_leo_satellite.json` | **Start here.** One 150 kg satellite at 550 km, Sun-synchronous, with gravity, Sun, Moon, drag and the Berlin station. One day runs in seconds. |
| 23 | `23_starter_complete_small_satellite.json` | **Start here.** A complete small satellite: the 150 kg microsatellite preset in Sun-safe pointing, with power and a radio link to Berlin. |
| 01 | `01_two_body_circular_orbit.json` | One circular orbit around a point-mass Earth: no perturbations, no attitude. The baseline for the other templates. |
| 02 | `02_elliptical_orbit_with_perturbations.json` | An eccentric orbit with Earth's oblateness and Sun and Moon gravity: nodal regression and apsidal rotation. |

### Orbits and orbit keeping

Orbit inputs, drag and solar activity, station keeping, low thrust, formations.

| # | File | Teaches |
|---|------|---------|
| 39 | `39_orbit_inputs_tle_and_state_vector.json` | Three ways to give an orbit: a TLE, a position and a velocity, and classical elements. |
| 42 | `42_tabular_atmosphere_and_lifetime.json` | Drag from a tabular atmosphere profile, and the orbital lifetime that it gives. |
| 45 | `45_solar_activity_past_104_days.json` | Solar activity at MSFC's 95th percentile over 110 days: a run longer than one Basilisk simulation. |
| 18 | `18_leo_station_keeping.json` | LEO station keeping: a 400 km satellite holds its altitude against drag with a 1 km deadband. |
| 03 | `03_geo_station_keeping.json` | GEO station keeping: east-west and north-south burns hold a 500 kg satellite in its 10 deg E slot. |
| 40 | `40_continuous_low_thrust.json` | Continuous low thrust: a 1 mN electric thruster against drag, beside a twin with no thruster. |
| 04 | `04_walker_constellation.json` | A Walker delta constellation: six satellites in two planes, with all perturbations. |
| 05 | `05_formation_flying_phasing.json` | A formation: the follower holds a position 50 km ahead of the chief for 90 days. |
| 24 | `24_formation_mean_element_control.json` | Template 05's formation, held by Basilisk's mean-element feedback (`meanOEFeedback`). Compare the two runs. |
| 29 | `29_roe_formation_helix.json` | A formation set by relative orbital elements: an approach to a passively safe helix. |

### Maneuvers and Mission Sequence

Burns, transfers and control flow as a list of commands in time order.

| # | File | Teaches |
|---|------|---------|
| 08 | `08_mission_sequence_orbit_raise.json` | The Mission Sequence: coast, burn +50 m/s prograde, coast, with snapshots. |
| 16 | `16_lambert_transfer.json` | A Lambert transfer: the Mission Sequence finds the burn that gets to a target position in a set time. |
| 46 | `46_mission_sequence_control_flow.json` | Mission Sequence control: assignments, `if`, `while` and a script block raise an orbit to 420 km. |

### Attitude and control

Pointing, sensors and actuators, disturbance torques and wheel momentum.

| # | File | Teaches |
|---|------|---------|
| 06 | `06_attitude_pointing_basic.json` | Nadir pointing with an ideal control torque: the pointing concept without hardware. |
| 07 | `07_attitude_pointing_with_adcs_hardware.json` | Template 06 with real hardware: star tracker, IMU, sun sensor, three reaction wheels, solar array and battery. |
| 41 | `41_velocity_pointing_with_navigation_errors.json` | Velocity pointing with a star tracker, a gyro, a magnetometer and navigation errors. |
| 15 | `15_celestial_body_pointing.json` | Pointing at a celestial body: the +Z axis stays on the Moon. |
| 10 | `10_gravity_gradient_torque.json` | Gravity gradient torque on an elongated spacecraft with no attitude control. |
| 11 | `11_thruster_attitude_control.json` | Attitude control with eight 1 N thrusters, not reaction wheels. |
| 17 | `17_fuel_tank_depletion.json` | Template 11 with a fuel tank: the propellant decreases as the thrusters fire. |
| 12 | `12_reaction_wheel_momentum_dumping.json` | Momentum dumping: thrusters unload four reaction wheels that start with too much momentum. |
| 13 | `13_magnetic_torque_rod_momentum_management.json` | Momentum management with magnetic torque rods and Earth's magnetic field. |
| 14 | `14_css_sun_heading_estimation.json` | Sun direction from eight coarse sun sensors and an estimator, not from the true direction. |
| 47 | `47_sensor_faults.json` | Sensor faults: a stuck sun sensor, a spiking magnetometer and a stuck thermal sensor, beside a healthy twin. |
| 21 | `21_disturbance_torques.json` | Disturbance torques from a facet model: sunlight and drag on an array off the center. |

### Power, communications and data

Power, the radio link to a ground station and the data on board.

| # | File | Teaches |
|---|------|---------|
| 19 | `19_sun_pointing_comms_link.json` | Sun pointing, with automatic slews to the Berlin station for the radio link, and the power budget. |
| 26 | `26_earth_observation_data_downlink.json` | Earth observation data: a camera fills the onboard memory, and an S-band link sends the data to Berlin. |

### Spacecraft model, thermal and budgets

The spacecraft as designed: 3D model, equipment, flexible arrays, thermal and budgets.

| # | File | Teaches |
|---|------|---------|
| 28 | `28_octagonal_bus_3d_model.json` | A 3D model: an octagonal bus with panels, a dish and a star tracker. The model gives the mass properties and surfaces. |
| 43 | `43_3d_model_cylinders_spheres_and_mesh.json` | A 3D model from cylinders, spheres and an imported `.obj` mesh. |
| 32 | `32_smallsat_design_checks.json` | Design checks on a 3D model: fields of view, a thruster plume, disturbance torques and array shading. |
| 38 | `38_budgets_equipment_power_mass_propellant.json` | The **Budgets** area: an equipment list, system modes, and the power, mass, pointing and propellant budgets. |
| 27 | `27_flexible_solar_arrays.json` | Flexible solar arrays: two wings on spring-damper hinges that act back on the attitude. |
| 20 | `20_thermal_simulation.json` | Thermal sensors: a panel that heats in the Sun and cools in eclipse, and a wheel motor model. |
| 33 | `33_microsat_thermal.json` | A thermal model on a 3D model: hot, cold and nominal cases, heaters and a radiator. |
| 34 | `34_microsat_flexible_thermal.json` | Template 33 with flexible arrays as thermal nodes, and thermal studies with a Monte Carlo. |

### Operations planning

Plans of images, calibrations and ground contacts for one or more spacecraft.

| # | File | Teaches |
|---|------|---------|
| 35 | `35_eo_operations_week.json` | A week of operations for one imager: targets, three stations, calibrations and contacts. |
| 36 | `36_constellation_operations.json` | Three imagers that share two stations, each station for one spacecraft at a time. |

### Uncertainty (Monte Carlo)

Batches of runs with dispersed inputs, requirements and statistics.

| # | File | Teaches |
|---|------|---------|
| 09 | `09_monte_carlo_dispersion_analysis.json` | A Monte Carlo batch of 20 runs of template 01, with a dispersed dry mass. |
| 25 | `25_monte_carlo_orbit_and_drag_dispersions.json` | A Monte Carlo batch with orbit injection errors and a dispersed drag coefficient. |
| 37 | `37_monte_carlo_requirements_and_sensitivity.json` | A Monte Carlo batch with requirements, a batch seed, outcome statistics and sensitivity. |
| 44 | `44_monte_carlo_attitude_inertia_rate_srp_density.json` | Five more Monte Carlo dispersions: attitude, body rate, inertia, SRP coefficient and atmosphere density. |

### Deep space and navigation

Orbits around Mars and an asteroid, estimated from camera images.

| # | File | Teaches |
|---|------|---------|
| 30 | `30_mars_optical_navigation.json` | Mars orbit: optical navigation from the disk of the planet in camera images. |
| 31 | `31_eros_landmark_navigation.json` | Asteroid Eros: landmark navigation, with gravity from the shape model. |

## Start your own mission from a template

22 and 23 are made for this. 22 has the environment that each LEO
mission needs, and nothing more. 23 is a complete small satellite.

1. Open 22 or 23.
2. Click **File › Save As...**, and save it under your own name.
3. Change one thing.
4. Run, and look at the result.
5. Do steps 3 and 4 again for each change.

The User Manual, section 6, shows this step by step. Templates 01 to 18
show one idea each, with nothing more. To combine ideas, start from the
nearest template and add the next idea from another template.

---

**Next:** [Run a template](../../../docs/user-manual/run-a-template.md) ·
[Build your own scenario](../../../docs/user-manual/build-your-own-scenario.md) ·
[Documentation index](../../../docs/README.md)
