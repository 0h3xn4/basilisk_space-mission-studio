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
"""The conductor calculator: a conductance from what the scenario stores
about it, so the value can be traced and recomputed.

- ``value``: the conductance as given [W/K];
- ``material``: ``G = k A / L`` with the conductivity ``k`` given, from a
  table at the mean temperature (Phase 2), or from the material;
- ``contact``: ``G = h A`` with the contact area (from the 3D model, see
  ``thermal.geometry.contacts``) and the contact coefficient ``h``
  (``thermal.library.BARE_JOINT_W_M2_K`` by default).

Each result carries a sentence saying how it was computed.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import library


class ConductorError(ValueError):
    """A conductor whose conductance cannot be computed (a material with
    no sourced conductivity)."""


@dataclass(frozen=True)
class Conductance:
    value_w_k: float  # [W/K]
    how: str


def table_value(table, temperature_c: float) -> float:
    """Linear interpolation in a ``[[degC, value], ...]`` table, held
    constant beyond its ends."""
    rows = np.asarray(table, dtype=float)
    return float(np.interp(temperature_c, rows[:, 0], rows[:, 1]))


def conductance(conductor, scenario_materials=(), temperature_c: float | None = None) -> Conductance:
    """The conductance of a :class:`ThermalConductorConfig`.
    ``temperature_c`` is the mean of its two nodes, for a conductivity
    table; without it a table is read at its first row's temperature."""
    if conductor.kind == "value":
        return Conductance(float(conductor.conductance_w_k), "given")
    if conductor.kind == "contact":
        area, h = float(conductor.contact_area_m2), float(conductor.contact_coefficient_w_m2_k)
        return Conductance(area * h, f"contact: {area:.4g} m^2 x {h:.4g} W/(m^2*K)")
    length, section = float(conductor.length_m), float(conductor.section_m2)
    if conductor.conductivity_table:
        at = conductor.conductivity_table[0][0] if temperature_c is None else temperature_c
        k = table_value(conductor.conductivity_table, at)
        where = f"table at {at:.1f} degC"
    elif conductor.conductivity_w_m_k is not None:
        k, where = float(conductor.conductivity_w_m_k), "given"
    else:
        found = library.conductivity(conductor.material, scenario_materials)
        if found is None:
            raise ConductorError(f"conductor {conductor.name!r}: material {conductor.material!r} has no sourced "
                                 "conductivity; give conductivity_w_m_k")
        k, where = found.value, f"{conductor.material}, {found.source}"
    return Conductance(k * section / length,
                       f"material: k {k:.4g} W/(m*K) ({where}) x {section:.4g} m^2 / {length:.4g} m")


def contact(name: str, a: str, b: str, area_m2: float, coefficient_w_m2_k: float | None = None):
    """A ``contact`` conductor between nodes ``a`` and ``b`` over
    ``area_m2``, with the bare-joint coefficient by default (T-26)."""
    from ..schema.thermal import ThermalConductorConfig

    h = library.BARE_JOINT_W_M2_K if coefficient_w_m2_k is None else coefficient_w_m2_k
    return ThermalConductorConfig(name=name, a=a, b=b, kind="contact", contact_area_m2=round(float(area_m2), 6),
                                  contact_coefficient_w_m2_k=round(float(h), 3))
