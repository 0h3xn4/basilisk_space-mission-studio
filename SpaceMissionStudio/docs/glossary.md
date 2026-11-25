# Glossary

The terms and abbreviations of the SpaceMissionStudio documentation, in
plain words and in alphabetical order. The User Manual in the app has a
shorter list (**Help**, `F1`, section 12).

[A](#a) · [B](#b) · [C](#c) · [D](#d) · [E](#e) · [F](#f) · [G](#g) ·
[H](#h) · [I](#i) · [J](#j) · [K](#k) · [L](#l) · [M](#m) · [N](#n) ·
[O](#o) · [P](#p) · [R](#r) · [S](#s) · [T](#t) · [U](#u) · [V](#v) ·
[W](#w)

## A

**Absorptance (solar):** the part of the sunlight that a surface
absorbs, from 0 to 1. White paint absorbs about 0.2, black paint about
0.96. With the [emissivity](#e), it sets the temperature of a surface in
the Sun ([Thermal analysis](user-manual/thermal.md)).

**Acquisition:** an activity of an [operations plan](#o) that takes an
image of a target. The spacecraft points its instrument at the target
and switches it on for a time.

**Activity:** one task of a spacecraft in an [operations plan](#o): an
acquisition, a contact, a calibration or a maneuver. It has a start, an
end, a pointing mode and the devices that it switches on
([Operations planning](user-manual/operations.md)).

**AD10:** ESA's guideline for delta-V and propellant budgets (document
EOP-FM/2024-07-177). The **Budget (AD10)** page follows its structure:
margins, residual propellant, and solar activity at the 95th percentile
for operations.

**ADCS:** Attitude Determination and Control System. The sensors,
actuators and software that find the direction of a spacecraft and turn
it.

**AEM (Attitude Ephemeris Message):** the [CCSDS](#c) file of the
attitude of a spacecraft over time, as quaternions. **Run › Plan**
exports the planned attitude as AEM 2.0.

**Albedo:** the part of the sunlight that a planet reflects: about 30 %
for Earth, about 16 % for Mars. This light also gets to the sun sensors.
It can move the estimate of the Sun direction (template 14).

**Ap:** a daily index of the disturbance of Earth's magnetic field. With
[F10.7](#f), it sets the density of the upper atmosphere, and thus the
[drag](#d) on a low satellite.

**Assumptions:** the page **Scenario › Assumptions**. It lists each
[parameter](#p) with its value, unit, source and rationale.
`spacemissionstudio assumptions` shows the same list. A
[project configuration file](#p) changes the parameters.

**Atomic oxygen (AO):** single oxygen atoms, the main gas of the upper
atmosphere in low Earth orbit. They erode some materials (Kapton, Mylar)
on surfaces that face the direction of flight. The erosion is the number
of atoms per area (the fluence) times the erosion yield of the material.

**Attitude:** the direction in which a spacecraft points. Attitude
control keeps it pointed at a target: the ground, the Sun, a ground
station or a planet.

## B

**Basilisk:** the open-source spacecraft simulation framework of the AVS
Lab, University of Colorado Boulder. It calculates every number in
SpaceMissionStudio. This repository is a fork of Basilisk.

**Beta angle:** the angle between the Sun direction and the plane of an
orbit. At a high beta angle, a low orbit has little or no eclipse and
is hot. At a low beta angle, the eclipse is longest and the orbit is
cold. The orbit and the epoch of the run set it.

**Body frame:** the axes that are fixed to the spacecraft. The positions
of its parts, sensors, thrusters and facets are given in it. The origin
is the body point B of the spacecraft. An [IDM-CIC](#i) import keeps the origin of the
body element, or moves it to the [center of mass](#c) if you choose.

**Boresight:** the direction straight out of an antenna or a sensor. Its
gain or its field of view has its center on this direction.

## C

**Calculation panel:** the panel beside the **Inspector** that explains
a number. It shows the equation and the standard, and each input with
its unit and its source. An **Open** button goes to each input that is
calculated too. **Show calculation** beside a calculated number opens
it. `--explain` shows the same on the command line.

**Casualty area:** the area in which falling debris can hurt a person.
For each fragment that gets to the ground with more than 15 J, it is
`(0.6 + sqrt(A))^2` m². `A` is the mean cross-section of the fragment,
and 0.6 m is the root of the area of a standing person. The casualty
area times the population density gives the casualty risk.

**CCSDS:** the Consultative Committee for Space Data Systems. It
publishes the standard file formats that space agencies exchange.
SpaceMissionStudio reads and writes three of its orbit messages:
[OPM, OMM and OEM](#o).

**Cd (drag coefficient):** a number for the drag of the upper atmosphere
on a spacecraft, for its size. ESA's [AD10](#a) uses 3.0 for
operations, a conservative value, and 2.2 for the end of life.

**Center of mass (center of gravity):** the point on which the mass of
the spacecraft balances. A force that does not go through it (drag,
sunlight, a thruster off its axis) turns the spacecraft. The app gives
it from the body point B (`center_of_mass_b_m`). A 3D model calculates
it.

**Change history:** the record of each saved change, beside the scenario
(`mission.history.jsonl`). It holds the value before and after, the
time, the author and the reason for an [override](#v). The author is the
name in **Settings › Change history**. **File › Change History...**
shows the record. `spacemissionstudio history` shows it on the command
line.

**Classical orbit elements:** six numbers that describe an orbit:

- the semi-major axis: approximately the mean size;
- the eccentricity: how stretched the orbit is;
- the inclination: the tilt to the equator;
- the [RAAN](#r) and the argument of periapsis: the orientation;
- an anomaly: the start point of the spacecraft on the orbit.

**Contact:** the part of a station [pass](#p) that a plan uses to send
data down or up. A station serves a limited number of spacecraft at the
same time. When more spacecraft want the same pass, the pass is
*contested*.

**Contact conductance:** how well heat goes across a joint between two
parts: an area times a coefficient in W/(m² K). A bare bolted aluminium
joint has about 136 W/(m² K) (NASA GSFC). A filler makes it about twenty
times larger.

**CSS (coarse sun sensor):** a small, simple light sensor. Several of
them, in different directions, give an approximate direction to the
Sun.

## D

**Delta-V:** the change of velocity of a maneuver, in m/s. It is the
usual way to give the propellant cost of a maneuver, independently of
the spacecraft.

**Design checks:** checks of the 3D model of a spacecraft that need no
run (**Run › Design Checks**, `spacemissionstudio check-design`). They
find parts in a field of view or in a thruster plume. They also check
the thruster authority, the mass budget with growth allowances, and the
fit in a launcher.

**Differential drag:** the difference in [drag](#d) between two
spacecraft that fly together. It comes from a different mass, area or
drag coefficient. Their orbits decay at different rates, so one
spacecraft slowly moves along the track away from the other.

**Drag:** the force of the thin upper atmosphere against a spacecraft in
a low orbit. It slowly makes the orbit lower until the spacecraft
re-enters.

## E

**ECSS:** the European Cooperation for Space Standardization. European
space projects follow its standards. The `compliance/` folder records
how SpaceMissionStudio applies four of them, and one CCSDS standard.

**Effective emittance (e\*):** one number for the heat that a
multi-layer insulation blanket lets through by radiation, usually 0.01
to 0.05. See [MLI](#m).

**EME2000:** an inertial reference frame (axes fixed relative to distant
stars) set by Earth's equator and equinox on 1 January 2000.
SpaceMissionStudio writes CCSDS files in this frame.

**E/i vectors:** the eccentricity and inclination parts of the
[relative orbital elements](#r) of a formation. The eccentricity vector
sets the radial motion of the follower around the chief. The inclination
vector sets its cross-track motion. Parallel vectors make the formation
[passively safe](#p).

**Emissivity (infrared):** how well a surface radiates heat, compared
with a perfect black body, from 0 to 1. It also sets how much of the
infrared of the planet the surface absorbs.

**Epoch:** the date and time at which a simulation starts, in [UTC](#u),
for example `2030-01-01T00:00:00`. The positions of the Sun and the
Moon, the density of the atmosphere and the position of the ground all
depend on it.

**Events:** things that occur at a time during a run: passes over ground
stations, eclipses, burns and changes of the attitude mode. The
**Timeline** area lists and shows them.

**Exclusion angle:** the smallest angle between the boresight of a star
tracker or a camera and a bright body before the sensor is blinded. The
bright body can be the Sun, the lit limb of the Earth or the Moon.

## F

**F10.7:** the radio brightness of the Sun at a wavelength of 10.7 cm, a
daily measure of solar activity. A more active Sun heats and expands the
upper atmosphere, so low satellites have more [drag](#d).

**Facet model:** the spacecraft as flat plates. Each plate has an area,
a direction and a center of pressure. Drag and solar pressure push on
each plate that faces the flow or the Sun. Thus both forces depend on
the attitude, and they can turn the spacecraft.

**Field of view (FOV):** the cone that a sensor, a camera or an antenna
sees, given as its full angle.

**Flexible appendage:** a large, light part, for example a solar array
wing, that bends and swings when the spacecraft turns. Its first mode is
its lowest bending frequency. Its damping ratio tells how quickly the
swing stops.

**FSW (flight software):** the software on the spacecraft. In
SpaceMissionStudio it is the attitude software: navigation, guidance and
control, made from Basilisk's own modules.

**FSW mode:** the built-in pointing behaviour of a spacecraft, for
example pointing straight down (nadir), at the Sun, or at a ground
station.

## G

**GCRF, ICRF:** modern inertial reference frames. For most purposes they
are the same as [EME2000](#e). SpaceMissionStudio accepts both in
imported [OPM](#o) files.

**GEO (geostationary orbit):** a circular orbit about 35,786 km above
the equator. A satellite in it goes around once a day, so it stays above
the same point on the ground.

**Ground station:** an antenna at a fixed point on Earth.
SpaceMissionStudio calculates when each spacecraft can see each station
(a **pass**), and the range and elevation.

## H

**Heat pipe:** a closed tube with a fluid that moves heat from a hot end
to a cold end, with a very small temperature difference. This is true
only in its operating range. When the fluid is frozen or dry, the pipe
almost does not conduct.

**Heater (thermostatic):** an electric heater that a thermostat switches
on below one temperature and off above a higher one. Its duty is the
part of the time that it is on. Its sized power is the smallest constant
power that keeps its node warm enough.

**Hill frame (R/T/N):** axes that move with a reference spacecraft (the
chief). **R** is radial (away from Earth), **T** is transverse (along the
direction of travel), and **N** is normal (out of the orbit plane). The
formation offsets are given in this frame.

**Horizon:** the time span of an [operations plan](#o), from its start
to its end (up to 104 days).

## I

**Inertia (moments and products of inertia):** how hard it is to turn
the spacecraft about each axis, in kg m². It is the rotational
equivalent of mass. The moments Ixx, Iyy, Izz are about the body axes.
The products Ixy, Ixz, Iyz tell how the mass is off those axes (zero for
a symmetric body). The app uses the tensor sign convention, Ixy = -∫xy dm.

**ICD (interface control document):** a document that lists each
message that a piece of software reads and writes. For each message, it
gives the fields, the units, the writer and the reader. Each flight
software export has one.

**IDM-CIC:** a concurrent engineering tool (IDM-CIC is © CNES). Its
models (`.idm` files) describe the elements, equipment, shapes, masses
and power modes of a spacecraft. SpaceMissionStudio reads them with its
own reader. It makes a 3D model, and adds sensors, actuators and power
budget values. It never writes `.idm` files. See
[Import a spacecraft from IDM-CIC](user-manual/idm-cic.md).

**IERS:** the International Earth Rotation and Reference Systems
Service. It measures how Earth turns. Its data make the [ITRF93](#i)
frame accurate.

**IMU (inertial measurement unit):** a sensor that measures the rotation
rate of the spacecraft. Some also measure its acceleration.

**ITRF93, IAU_EARTH:** two models of the orientation of Earth in space.
The app uses them to put ground stations on Earth and to calculate the
ground track. ITRF93 uses the measured Earth rotation ([IERS](#i) data,
from `spacemissionstudio earth-orientation --fetch`). IAU_EARTH is a
simpler formula, about 10 km wrong at the surface in 2026. Each run
tells which model it used.

## J

**J2:** the largest effect of the equatorial bulge of Earth on an orbit.
It slowly turns the orbit plane. [Sun-synchronous](#s) orbits use this
effect.

**JSON page:** the text of the scenario, under **JSON** in the
**Scenario** area. It is the file as saved, and you can edit it. It
marks each problem where it is. It has completion (`Ctrl+Space`), help
for each key, rename (`F2`), go to definition (`F12`) and quick fixes
(`Ctrl+.`).

## K

**Kalman filter:** an estimator that keeps a best estimate of a state
(here a position and a velocity) and its uncertainty. It moves both
forward with a model of the motion. It corrects them with each
measurement, by how much it trusts the measurement. Basilisk's
`relativeODuKF`, which [optical navigation](#o) uses, is an *unscented*
Kalman filter.

**KVN (keyword = value notation):** the plain text form of [CCSDS](#c)
files, with one `KEYWORD = value` on each line. SpaceMissionStudio reads
and writes KVN, not the XML form.

## L

**Lambert transfer:** the burn that moves a spacecraft from its position
to a selected position in a selected time. The `lambert_transfer`
command of a [Mission Sequence](#m) calculates it.

**Landmark navigation:** an estimate of the position of a spacecraft
from known surface features of a small body (landmarks) in camera
images. A [Kalman filter](#k) combines many images.

**LEO (low Earth orbit):** orbits below about 2000 km. Most satellites
fly there. The orbit is low enough for [drag](#d).

**Link margin:** the difference between the received radio signal and
the signal that the receiver needs, in dB. At 0 dB or more, the link
closes and data can go through. Below 0 dB, it cannot. A project can
require more (`link.required_margin_db`,
[RF link, data handling and power](models/link-data-and-power.md)).

**LTAN (local time of the ascending node):** the local solar time when
a satellite crosses the equator to the north, for example 10:30. It is
used for a [Sun-synchronous orbit](#s). It sets the light
conditions of the satellite.

## M

**Maturity (mass):** how well the mass of a part is known. The levels
are: estimated, from a layout, a design before release, a released
design, existing hardware, measured. A less mature mass gets a larger
growth allowance (AIAA S-120-2006).

**Mean elements:** orbit elements without the short, regular
oscillations. They make slow trends easy to see, for example the turn of
the orbit plane by [J2](#j). The opposite is the osculating elements.

**Mission Sequence:** a list of commands that a run does in order. A
command can propagate until an event, burn, calculate a Lambert
transfer, report a value, branch with `if` or `while`, or run a script
block. It is like the mission sequence of GMAT or FreeFlyer.

**MLI (multi-layer insulation):** a blanket of many thin reflective
layers that insulates the surface of a spacecraft. The thermal model
describes it by the optical properties of its outer layer and by its
[effective emittance](#e).

**Model analyses:** what a run calculates on the 3D model of the
spacecraft (**Results › Model Analyses**,
`spacemissionstudio model-analyses`). They are disturbance torques,
sensor blinding, antenna obstruction, array shading, atomic oxygen
exposure and brightness.

**Monte Carlo:** many runs of the same scenario with small random
changes (mass, attitude, orbit, drag and more). The result is the range
of outcomes, not one answer.

**MRP (modified Rodrigues parameters):** three numbers that describe an
[attitude](#a). Basilisk uses them for attitudes and attitude errors.

**MSFC:** NASA's Marshall Space Flight Center. It publishes the monthly
prediction of solar activity ([F10.7](#f) and [Ap](#a)).
SpaceMissionStudio uses it after the end of the measured record.

## N

**NAIF:** NASA's Navigation and Ancillary Information Facility. It
publishes the [SPICE kernels](#s) and the Earth orientation files.

**Navigation error:** an error that you add on purpose to what the
flight software knows about the spacecraft: attitude, rate, position.
The run then shows how the software works with imperfect sensors.

**NRLMSISE-00:** the model of the density of the upper atmosphere that
the drag uses. [F10.7](#f) and [Ap](#a) drive it.

## O

**OBJ (Wavefront .obj):** a common text file format for 3D shapes. CAD
and modelling tools write it. The app reads it into a 3D model, and
exports the model in this format.

**OEM, OMM, OPM:** three [CCSDS](#c) orbit files:

- an **OPM** (Orbit Parameter Message) gives one state at one time;
- an **OMM** (Orbit Mean-Elements Message) gives mean elements, as a
  [TLE](#t) does;
- an **OEM** (Orbit Ephemeris Message) lists positions and velocities
  over time.

**OLR (outgoing longwave radiation):** the infrared that a planet
radiates, in W/m² at the top of its atmosphere. For the Earth, the mean
is about 211 to 246 W/m². It depends on the latitudes that an orbit
crosses.

**Operations plan:** the [activities](#a) of one or more spacecraft over
a [horizon](#h). The scheduler puts them so that the slews fit, and the
battery and the memory stay in their limits. It is a planning product,
not a command load ([Operations planning](user-manual/operations.md)).

**Opportunity:** a time at which an activity can occur: a target
[window](#w) or a station [pass](#p).

**Optical navigation:** an estimate of the position of a spacecraft from
camera images. Here, the position of the disk of a planet in the image
gives the direction. The size of the disk gives the range. A
[Kalman filter](#k) combines many images.

**Orbit-periodic:** a state that repeats in each orbit. The thermal
model starts its cases from the orbit-periodic state. Thus the result
does not depend on an estimated start temperature.

**Orbital lifetime:** the time until [drag](#d) brings an orbit down to
re-entry. Here, re-entry is when the perigee gets to 120 km. Disposal
rules limit the lifetime after the end of the mission. The limit is 5
years under ESA's Zero Debris approach and the FCC, and 25 years under
the older IADC guideline.

**Osculating elements:** the [classical elements](#c) of the orbit that
the spacecraft would follow if all forces except the central gravity
stopped at that instant. They oscillate along the orbit. See mean
elements.

**Overridden value:** see [value mark](#v).

## P

**Parameter:** a named rule, margin or model choice of an analysis, for
example `propellant_budget.residual_fraction`. It has a default, a unit,
a source and limits. A [project configuration file](#p) changes it
without a change to the code. Each result records the changes. See
[Models, rules and assumptions](models/README.md).

**Pass:** one period when a spacecraft is above the horizon of a ground
station, and above its minimum elevation.

**Passive safety:** a property of a formation. Its two spacecraft never
meet in the radial and cross-track plane. Thus they cannot collide, even
if the along-track spacing is lost. Its [e/i vectors](#e) are parallel.
The app shows the closest radial and cross-track approach.

**Patch antenna:** a flat antenna on one face of the spacecraft. Its
gain is highest straight out of the face and decreases to the sides.
Thus the link depends on the pointing of the spacecraft.

**Phase angle:** the angle at a planet between the Sun and the
spacecraft. At 0 deg, the camera sees the full lit disk. Above 90 deg,
it sees mostly the night side.

**Phasing (along-track separation):** the distance of a satellite ahead
of or behind another spacecraft (the chief) on the same orbit. Phasing
keeping holds that distance, as station keeping holds an altitude.

**Plugin:** a Python package with an entry point in the group
`spacemissionstudio.models`. It adds its own [parameters](#p), pre-run
rules and models, without a change to the tool. A run records the
plugins that it loaded. A plugin cannot add to what Basilisk simulates.
See [Add your own models and rules](user-manual/plugins.md).

**Polyhedral gravity:** the gravity of a body, calculated from its shape
at constant density (Werner and Scheeres 1997). The shape is a closed
surface of triangles (a polyhedron). Near an irregular small body, for
example an asteroid, it is much nearer to the real gravity than a point
mass.

**Principal axes:** the three axes about which the products of inertia
of a body are zero. The moments about them are its principal moments. A
model shows both, and the angle from each axis to the nearest body axis.

**Project configuration file:** a YAML file that a scenario names
(`config_file`). It changes [parameters](#p) for a project. Select it or
make it in **Scenario › Assumptions**. See
[Change a parameter](user-manual/project-configuration.md).

**Provenance:** the file `provenance.json`, written with the results of
each run. It records:

- the Basilisk version, and if it is the verified version;
- the versions of the other software;
- the checksums of the scenario and of each reference file used;
- each random seed;
- the values that the run used and that the file did not give;
- each [parameter](#p) that a project changed.

**Show everything recorded** shows all of it.

## R

**RAAN (right ascension of the ascending node):** the direction in space
where the orbit crosses the equator to the north. It sets the direction
of the orbit plane.

**Radiator:** a surface that sends the heat of a spacecraft to space. It
usually faces away from the Sun. It has a low [absorptance](#a) and a
high [emissivity](#e), for example white paint or silvered Teflon.

**Random seed:** a number (`sim_settings.seed`, default 0). The app
derives the random sequence of each sensor noise model from it. Thus the
same scenario gives the same run, and no two sensors get the same noise.

**Ray casting:** straight lines (rays) through the 3D model, to find
what they hit. The app uses it to find parts in a field of view, in a
plume or in the path of the sunlight.

**Reaction wheel (RW):** a wheel that turns inside the spacecraft. When
it turns faster or slower, the spacecraft turns in the other direction.
It uses no propellant.

**Reference data:** the data files that runs need: [SPICE kernels](#s),
the gravity field, the magnetic field model, the Earth orientation files
and the space weather. The **Reference data** window lists them.

**Relative orbital elements (ROE):** six numbers that describe the orbit
of one spacecraft relative to another (D'Amico's quasi-nonsingular set).
They are a relative semi-major axis (a drift), a relative mean longitude
(the along-track offset) and the two [e/i vectors](#e). The app gives
them in metres: the numbers times the semi-major axis of the chief.

**Replanning:** a new plan from a given time. Activities that started
before that time stay as flown. The app plans the rest of the horizon
again, for example after a lost pass.

**Reproduction bundle:** a folder with the results of a run, its
provenance, the scenario as run and copies of the files that it uses.
Make it with `run --bundle`, or with **Results › Plots › Export all... ›
Reproduction bundle...**. `spacemissionstudio reproduce` runs it again
and shows the differences.

**RF:** radio frequency: the radio link between the spacecraft and the
ground.

**RTN, VNB:** two sets of axes for the direction of a burn. **RTN** is
Radial, Transverse (along the track) and Normal. **VNB** is Velocity,
Normal (orbit normal) and Binormal. Both move with the spacecraft.

## S

**Scenario:** one mission set-up, saved as a JSON file. It holds the
spacecraft, the orbits, the ground stations, the environment, the run
settings and, as an option, a Mission Sequence. A **template** is a
ready-made scenario.

**SHA-256:** a checksum of the bytes of a file. The provenance records
one for the scenario and for each data file of a run. Thus a changed
file shows.

**Show calculation:** see [Calculation panel](#c).

**SIL (software in the loop):** the flight software runs as its own
program against the simulated spacecraft, step by step. The simulation
sends it the sensor values. The commands of the flight software fly the
simulated spacecraft.

**Space weather:** solar activity ([F10.7](#f)) and geomagnetic activity
([Ap](#a)) over time. SpaceMissionStudio uses only real data: measured
values, CelesTrak's 45-day forecast, and NASA [MSFC](#m)'s prediction
for the future.

**SPICE kernels:** reference files from [NAIF](#n) with the positions
and shapes of the planets and the leap seconds. Basilisk needs them for
real time and real positions.

**Spherical harmonics gravity:** a gravity model of the real, slightly
irregular shape of a planet, not only a point mass. A higher degree
gives more detail and needs more calculation time.

**SRP (solar radiation pressure):** the very small force of sunlight on
a spacecraft. It is most important for high orbits and for large, light
spacecraft.

**Station keeping:** small, regular burns that move a satellite back to
its position when drag and gravity move it away.

**Stowed configuration:** the positions of the deployable parts (arrays,
booms, antennas) during launch, folded against the bus.

**Sun-synchronous orbit (SSO):** a near-polar orbit whose plane turns
once a year, in step with the Sun. The satellite flies over each
latitude at the same local solar time every day. Earth observation
satellites often use it.

## T

**TAI, TDB, TT, UT1:** time scales:

- **TAI** is atomic time;
- **TT** is TAI plus 32.184 s;
- **TDB** is the time scale of the planet positions, within 2 ms of TT;
- **UT1** is time by the real rotation of Earth.

[UTC](#u) follows TAI with leap seconds, and stays within 0.9 s of UT1.

**Template:** one of the 47 ready-made scenarios of the app, in nine
categories. Each one shows one idea or a complete mission. See the
[template catalog](../spacemissionstudio/scenarios/templates/README.md).

**Thermal node:** one or more parts of the spacecraft with one
temperature and one heat capacity in the
[thermal model](user-manual/thermal.md). Conductors, heat pipes and
radiation connect the nodes.

**Third-body perturbation:** the small additional pull of a body other
than the central body. An example is the pull of the Sun or the Moon on
a satellite of Earth.

**TLE (two-line element set):** the short text format of the published
orbits of tracked satellites, for example from CelesTrak. You can use
one to give the start orbit.

**Torque rod (magnetic torquer, MTB):** an electromagnet that pushes
against the magnetic field of Earth to turn the spacecraft. Here it
unloads the reaction wheels.

**Trace (calculation trace):** how the app calculated one number: its
equation, the clause of the standard, and each input with its unit and
source. The sources are `scenario:`, `parameter:`, `constant:`,
`last run:` and `computed:`. The [Calculation panel](#c) shows it, and
`--explain` and `--out` write it.

## U

**UTC:** Coordinated Universal Time, the civil time standard.
SpaceMissionStudio gives each epoch and time in UTC, unless it says
otherwise.

## V

**Value mark:** the status that the scenario file keeps for a value:

- **computed:** SpaceMissionStudio calculated or suggested it, and the
  mark tells what calculated it;
- **edited:** you changed it after the calculation;
- **overridden:** you replaced it on purpose, with a reason (the reason
  is necessary).

Runs and records list the marks. See
[Computed and overridden values](models/value-marks.md).

**View factor:** the part of the radiation from one surface that gets to
another surface. The thermal model uses the closed-form view factor from
a flat plate to a sphere for the infrared of the planet.

**Visual magnitude:** the brightness of an object to the eye. A smaller
number is brighter. The Sun is -26.7, the brightest stars are about 0,
and the faintest stars in a dark sky are about 6.

**VNB:** see [RTN, VNB](#r).

## W

**Walker constellation:** satellites spread evenly over several orbit
planes, given as total satellites / planes / phasing factor. **Generate
Walker constellation** makes one. **Hold each plane's spacing** makes
the first satellite of each plane the chief. It gives the other
satellites [phasing keeping](#p), which holds their positions.

**Window (target):** a time span when a target is in reach of the
instrument and has the necessary light. The reach is set by the
off-nadir angle and the elevation. The light is set by the elevation of
the Sun. A window is an [opportunity](#o) for an acquisition.

---

**Next:** [Documentation index](README.md) ·
[Getting started](getting-started.md) · [FAQ](faq.md)
