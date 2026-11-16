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
"""The thermal model's view of the material library
(``config.materials``) and of a scenario's own materials: optics,
specific heat and conductivity by name, each with its source, and the
sourced defaults the thermal model falls back on.

A value the library cannot source is None, and the caller says so
(decision T-24).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import materials as library

#: Default specific heat: aluminium 6061-T6 from the library (decision T-05).
DEFAULT_SPECIFIC_HEAT_MATERIAL = "aluminium_6061_t6"

#: Default contact conductance coefficient of a bare bolted joint [W/(m^2*K)]
#: (decision T-26): 5.63 W/K measured under an 8 in x 8 in electronics-box
#: baseplate (0.0413 m^2) bolted dry to a cold plate in vacuum.
BARE_JOINT_W_M2_K = 5.63 / (8 * 0.0254) ** 2  # [W/(m^2*K)] about 136
BARE_JOINT_SOURCE = ("D. E. Steinfeld, M. S. Martins, \"Interface Conductance Under a Real Electronics Box\", "
                     "NASA GSFC, TFAWS 2019 (NTRS 20190030287): bare joint, 5.63 W/C over 8 in x 8 in")
#: The same box with a 0.020 in layer of NuSil 2946 between the faces.
FILLED_JOINT_W_M2_K = 108.97 / (8 * 0.0254) ** 2  # [W/(m^2*K)] about 2640
FILLED_JOINT_SOURCE = ("D. E. Steinfeld, M. S. Martins, TFAWS 2019 (NTRS 20190030287): NuSil 2946, 0.020 in, "
                       "8 screws, 108.97 W/C over 8 in x 8 in")


@dataclass(frozen=True)
class Sourced:
    """A number and where it comes from."""

    value: float
    source: str


def _scenario_material(name: str, scenario_materials) -> object | None:
    return next((m for m in scenario_materials or () if m.name == name), None)


def _field(name: str, attribute: str, scenario_materials) -> Sourced | None:
    own = _scenario_material(name, scenario_materials)
    if own is not None:
        value = getattr(own, attribute, None)
        return None if value is None else Sourced(float(value), own.source or f"the scenario's material {name!r}")
    entry = library.MATERIALS.get(name)
    value = None if entry is None else getattr(entry, attribute, None)
    return None if value is None else Sourced(float(value.value), value.source)


def absorptance(name: str, scenario_materials=()) -> Sourced | None:
    """Solar absorptance of material or coating ``name``."""
    return _field(name, "solar_absorptance", scenario_materials)


def emissivity(name: str, scenario_materials=()) -> Sourced | None:
    """Hemispherical infrared emissivity of material or coating ``name``."""
    return _field(name, "emissivity", scenario_materials)


def specific_heat(name: str, scenario_materials=()) -> Sourced | None:
    """Specific heat [J/(kg*K)] of material ``name``."""
    return _field(name, "specific_heat_j_kg_k", scenario_materials)


def conductivity(name: str, scenario_materials=()) -> Sourced | None:
    """Thermal conductivity [W/(m*K)] of material ``name``, where sourced."""
    return _field(name, "conductivity_w_m_k", scenario_materials)


def default_specific_heat() -> Sourced:
    """The specific heat a node falls back on (T-05)."""
    value = specific_heat(DEFAULT_SPECIFIC_HEAT_MATERIAL)
    if value is None:  # the library holds it; a guard against an edit that drops it
        raise LookupError(f"the library has no specific heat for {DEFAULT_SPECIFIC_HEAT_MATERIAL}")
    return Sourced(value.value, f"{library.MATERIALS[DEFAULT_SPECIFIC_HEAT_MATERIAL].description}: {value.source}")
