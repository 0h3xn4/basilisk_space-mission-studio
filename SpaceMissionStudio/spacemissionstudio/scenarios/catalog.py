#
#  SpaceMissionStudio
#
#  Licensor: 0h3xn4 (https://github.com/0h3xn4)
#
#  Licensed under the EUPL
#
#  SPDX-License-Identifier: EUPL-1.2
#
#  The European Union Public Licence v. 1.2 is in the files LICENSE
#  (English) and LICENSE.de (German) of the SpaceMissionStudio folder and
#  of every package. Third-party components, each under its own licence,
#  are listed in THIRD_PARTY_NOTICES.
#
#
#
#

"""The template catalog: the categories of the bundled templates, in order,
and each template's place in its category, from simple to advanced.

This module is the one source of truth for the order in which the
templates are shown and for their categories: Home, the command palette
and the catalog in ``templates/README.md`` follow it
(``tests/test_template_catalog.py`` checks the README and the folder).

The template numbers are identifiers, not an order: they only tell in
which order the templates were added. The file names, the numbers and the
golden files stay as they are. The template files hold no category: a
field in them would need a schema step and would change their hashes. No
other ``.json`` file goes into ``templates/``: the loaders read every
``*.json`` file there as a template.

A new template gets one entry here, in the ``files`` of its category, at
its place from simple to advanced. Without an entry, the catalog test
fails, and the app shows the template last, under :data:`OTHER`.
Templates of other changes go here (docs/DECISIONS.md, decision TC-1):
38 (budgets) in "Spacecraft model, thermal and budgets"; 39 (orbit
inputs: TLE, state vector), 40 (continuous low thrust) and 42 (other
atmosphere models) in "Orbits and orbit keeping"; 41 (velocity pointing,
magnetometer, navigation error) in "Attitude and control".
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


@dataclass(frozen=True)
class Category:
    """A group of templates: its title, a line that says what its
    templates show, and its templates' file names from simple to
    advanced."""

    key: str
    title: str
    description: str
    files: tuple[str, ...]


CATEGORIES: tuple[Category, ...] = (
    Category("getting-started", "Getting started",
             "Starting points for your own mission, and the simplest orbits.",
             ("22_starter_first_leo_satellite.json",
              "23_starter_complete_small_satellite.json",
              "01_two_body_circular_orbit.json",
              "02_elliptical_orbit_with_perturbations.json")),
    Category("orbits", "Orbits and orbit keeping",
             "Orbit inputs and drag, station keeping, low thrust, a constellation, formations.",
             ("39_orbit_inputs_tle_and_state_vector.json",
              "42_tabular_atmosphere_and_lifetime.json",
              "18_leo_station_keeping.json",
              "03_geo_station_keeping.json",
              "40_continuous_low_thrust.json",
              "04_walker_constellation.json",
              "05_formation_flying_phasing.json",
              "24_formation_mean_element_control.json",
              "29_roe_formation_helix.json")),
    Category("maneuvers", "Maneuvers and Mission Sequence",
             "Burns and transfers as a list of commands in time order.",
             ("08_mission_sequence_orbit_raise.json",
              "16_lambert_transfer.json")),
    Category("attitude", "Attitude and control",
             "Pointing, sensors and actuators, disturbance torques and wheel momentum.",
             ("06_attitude_pointing_basic.json",
              "07_attitude_pointing_with_adcs_hardware.json",
              "41_velocity_pointing_with_navigation_errors.json",
              "15_celestial_body_pointing.json",
              "10_gravity_gradient_torque.json",
              "11_thruster_attitude_control.json",
              "17_fuel_tank_depletion.json",
              "12_reaction_wheel_momentum_dumping.json",
              "13_magnetic_torque_rod_momentum_management.json",
              "14_css_sun_heading_estimation.json",
              "21_disturbance_torques.json")),
    Category("power-comms-data", "Power, communications and data",
             "Power, the radio link to a ground station and the data on board.",
             ("19_sun_pointing_comms_link.json",
              "26_earth_observation_data_downlink.json")),
    Category("spacecraft-model", "Spacecraft model, thermal and budgets",
             "The spacecraft as designed: 3D model, equipment, flexible arrays, thermal and budgets.",
             ("28_octagonal_bus_3d_model.json",
              "32_smallsat_design_checks.json",
              "27_flexible_solar_arrays.json",
              "20_thermal_simulation.json",
              "33_microsat_thermal.json",
              "34_microsat_flexible_thermal.json")),
    Category("operations", "Operations planning",
             "Plans of images, calibrations and ground contacts for one or more spacecraft.",
             ("35_eo_operations_week.json",
              "36_constellation_operations.json")),
    Category("monte-carlo", "Uncertainty (Monte Carlo)",
             "Batches of runs with dispersed inputs, requirements and statistics.",
             ("09_monte_carlo_dispersion_analysis.json",
              "25_monte_carlo_orbit_and_drag_dispersions.json",
              "37_monte_carlo_requirements_and_sensitivity.json")),
    Category("deep-space", "Deep space and navigation",
             "Orbits around Mars and an asteroid, estimated from camera images.",
             ("30_mars_optical_navigation.json",
              "31_eros_landmark_navigation.json")),
)

# Where the app shows a template file that has no entry: last, so it is
# still there to open. The catalog test fails for it.
OTHER = Category("other", "Other templates", "Templates that have no place in the catalog yet.", ())


@dataclass(frozen=True)
class Entry:
    """A template's place: its category and its position in it (0 first)."""

    file_name: str
    category: Category
    position: int

    @property
    def number(self) -> str:
        """The template's number, its identifier ("22")."""
        return template_number(self.file_name)


def entries() -> list[Entry]:
    """Every catalog entry, in catalog order."""
    return [Entry(name, category, position)
            for category in CATEGORIES for position, name in enumerate(category.files)]


_BY_FILE = {entry.file_name: entry for entry in entries()}


def entry(file_name: str) -> Entry | None:
    """The entry of the template file ``file_name`` (a name, not a path),
    or None when the catalog has no entry for it."""
    return _BY_FILE.get(Path(file_name).name)


def category_of(file_name: str) -> Category:
    """The category of ``file_name``; :data:`OTHER` when it has no entry."""
    found = entry(file_name)
    return found.category if found is not None else OTHER


def template_number(file_name: str) -> str:
    """The number at the start of a template's file name ("22" for
    ``22_starter_first_leo_satellite.json``): its identifier."""
    return Path(file_name).name.split("_", 1)[0]


def template_files(folder: Path = TEMPLATES_DIR) -> list[Path]:
    """The template files in ``folder``, in file-name order."""
    return sorted(folder.glob("*.json")) if folder.is_dir() else []


def _order_key(path: Path) -> tuple[int, int, str]:
    found = entry(path.name)
    if found is None:
        return (len(CATEGORIES), 0, path.name)
    return (CATEGORIES.index(found.category), found.position, path.name)


def ordered(paths: Iterable[Path]) -> list[Path]:
    """``paths`` in catalog order; a file with no entry last, by name."""
    return sorted(paths, key=_order_key)


def grouped(paths: Iterable[Path]) -> list[tuple[Category, list[Path]]]:
    """``paths`` by category, in catalog order: a ``(category, paths)``
    pair for each category that has one of them; files with no entry in a
    last :data:`OTHER` group."""
    groups: dict[str, tuple[Category, list[Path]]] = {}
    for path in ordered(paths):
        category = category_of(path.name)
        groups.setdefault(category.key, (category, []))[1].append(path)
    return list(groups.values())
