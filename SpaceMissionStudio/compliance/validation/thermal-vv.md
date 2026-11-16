# Verification and validation: the thermal model

The record of how the multi-node thermal model (requirement SRS-F-29) was
checked. Each case is a test that runs in the suite. The reference is a
closed-form result, a hand calculation, Basilisk's own module or a cited
source, never the code under test. Measured 2026-11-16 on Python 3.14.6,
Basilisk 2.12.0, x86-64 with 4 cores. The design is in
`docs/developer/thermal-design.md` and the decisions (T-nn) in
`docs/developer/thermal-decisions.md`.

## Regression against Basilisk's sensorThermal (`tests/test_thermal_vv.py`)

Basilisk's `sensorThermal` integrates one plate:
`m c dT/dt = S A_proj alpha + P - eps sigma_B A T^4`, by explicit Euler.
It is driven here through its public API with stand-alone messages, and
the same plate is solved by this tool's solver on the same loads.

| Case | Reference | Tolerance | Result |
|---|---|---|---|
| A 0.1 m^2 plate (alpha 0.6, eps 0.8, 0.5 kg, 890 J/(kg K), 2 W) spinning through the Sun once per 30 min for 90 min from 20 degC, with Basilisk's S = 1366 W/m^2 and its radiation constant, 1 s step | Basilisk's temperature at every step | 0.1 K | 0.072 K at most, over a swing of -21.9 to 39.7 degC |
| The same at 0.25 s | Basilisk's temperature | 0.025 K | 0.018 K: the difference fell 4.0-fold for a 4-fold smaller step, as explicit Euler's first-order error does |
| This tool's solution at 1 s against 0.25 s | Itself | 1 mK | Within |
| The plate held facing the Sun: equilibrium with the Stefan-Boltzmann constant against Basilisk's 5.76051e-8 | Ratio (5.76051e-8 / 5.670374e-8)^(1/4) | 1e-9 | Equal; the plate is 1.4 K warmer with the correct constant |

Basilisk's radiation constant is 1.6 % above the Stefan-Boltzmann
constant (CODATA 2018: 5.670374419e-8 W/(m^2 K^4)). This tool uses the
correct value; the regression uses Basilisk's so that only the
integration differs. A draft upstream issue is in decision T-33.

## Analytic cases (`tests/test_thermal_solver.py`, `tests/test_thermal_vv.py`)

| Case | Reference | Tolerance | Result |
|---|---|---|---|
| A 1 m^2 plate facing the Sun, both sides radiating (built from the 3D model and the environment) | `alpha S = 2 eps sigma T^4` | 0.05 K | Within |
| A faceted sphere (D 1 m) in the Sun, 4 / 16 / 64 segments | `alpha S pi R^2 = eps sigma 4 pi R^2 T^4`: 240.286 K | 5 % / 1 % / 0.3 % | 1.6e-2 / 6.6e-4 / 1.4e-4 relative |
| A faceted cylinder (D 1 m, H 2 m), the Sun across its axis, 6 / 24 / 96 segments | `alpha S D H = eps sigma (pi D H + pi D^2 / 2) T^4`: 235.120 K | 2 % / 0.2 % / 0.02 % | 1.2e-2 / 1.4e-3 / 7.2e-5 relative |
| Two nodes: a unit dissipating 20 W through 2 W/K to a radiating panel dissipating 5 W | `E T_A^4 = 25 W`, `T_B - T_A = 10 K` | 1 uK | Equal |
| A heat pipe of 10 W/K between them, inside its range | `T_B - T_A = 2 K` | 1 uK | Equal |
| The same heat pipe below its range (0.01 W/K off) | `T_B - T_A = 2000 K` | 1e-6 relative | Equal |
| MLI on a face (alpha_o 0.4, eps_o 0.6, e* 0.02) | `k = e* / (eps_o + e*)` scales both optics (T-09) | exact | Equal; other faces unchanged |
| A thin panel, nadir-pointed, solar cells on +z and black paint on -z, beta 30 deg | Each side lit only facing the Sun, never both; infrared `OLR / h^2` on +z, none on -z; each side's absorptance and emissivity | 1e-9 relative | Equal |
| Plate-to-sphere view factor, full, partial and none (Gilmore's closed forms) | Numerical integration of the definition | 0.5 % of the nadir value | Within; continuous at both boundaries to 1e-5 |
| Heater sizing: a node radiating `E T^4` in the dark, thermostat on at 5 degC | `E T_on^4` | 0.1 W | Within |

## Solver behaviour (`tests/test_thermal_solver.py`, `tests/test_thermal_vv.py`)

| Case | Reference | Tolerance | Result |
|---|---|---|---|
| Energy balance over three orbits with the Sun switching, a thermostat cycling, a conductor and a radiative link, 30 s step | Stored heat = trapezoidal integral of the net heat in | 1e-3 of the throughput | Within; the residual halves at least at a 10 s step |
| One eclipsing node, steps 120 / 60 / 30 / 5 s: the step check (the change with half the step) | Second order: about 4-fold per halving | 30 s result within 0.05 K of the 5 s one | 0.250 / 0.064 / 0.016 / 0.0003 K (3.9 and 4.1-fold); extremes within 0.02 K |
| The same: energy residual | | | -124 J at 120 s, 2e-4 J at 60 s and below, of 1.45e6 J |
| Orbit-periodic start against 40 orbits from -80 degC | The long transient's last orbit | 0.01 K | Within; periodic in 6 orbits to 1 mK |
| Template 32, 0.15 days, three cases (`tests/test_thermal_analysis.py`) | Hot above nominal above cold; periodic; balance; step check | 1e-3, 0.5 K | Periodic in 8-9 orbits; residual about 2e-4 of the throughput; step check 0.19 K (1.7 K before the solver stepped on eclipse transitions, T-29) |
| Sized heater held at constant power | Its coldest temperature at the setpoint | 0.2 K | Within |

## Environment (`tests/test_thermal_environment.py`)

| Case | Reference | Result |
|---|---|---|
| Sunlight on an inertially fixed cube, Sun along +x | `S` on +x in sunlight, nothing in eclipse; scales as `1/r^2` at 0.98 AU | Equal |
| Planetary infrared on a nadir cube | `OLR / h^2` on +z (top of the atmosphere 30 km up, NASA/TM-2001-211221); the partial form on the sides; none on -z | Equal to 1e-6 |
| Albedo from Basilisk's albedo module, stand-alone, per facet normal | Peak near the subsolar point (within 5 % of Basilisk's 5 deg patches), none on a zenith face; linear in the coefficient and the solar constant | As expected |
| Hot, nominal and cold presets | NASA/TM-2001-211221 (its solar constant values and Tables 4.2.1-1 and 4.2.3): solar 1414 / 1367 / 1322 W/m^2, the band's mean OLR and albedo, the 90-minute combined pairs, the albedo correction by beta | Taken from the tables and cited in each case's notes |

## Model generation and checks (`tests/test_thermal_geometry.py`, `tests/test_thermal_checks.py`)

| Case | Reference | Result |
|---|---|---|
| Two boxes face to face | Contact over the exact overlap (polygon clipping) | Equal |
| A gap of a few millimetres | No contact | None |
| Template 32's 300 kg spacecraft | A node per part, the battery internal; contact conductors bus-star tracker (0.15 x 0.25 m), bus-dish and bus-battery (0.4 x 0.4 m base) at the bare-joint coefficient 136.35 W/(m^2 K) (NASA GSFC TFAWS 2019, NTRS 20190030287) | As expected |
| Template 33's 150 kg bus | See its claims in `tests/test_template_claims.py` | |
| Faces in no node, without optics; nodes without capacity or without a path to space; parts that can shade faces | Problems panel findings with their rule | Each found, nothing else on a complete model |

## Sources not reachable or not usable

- SATMO (arXiv 2512.07896): the network policy of the build environment
  refused the host, so its cases could not be reproduced (T-18).
- The TU Delft thermal tool: its repository has no licence, so neither
  its code nor its cases are used (T-19).
