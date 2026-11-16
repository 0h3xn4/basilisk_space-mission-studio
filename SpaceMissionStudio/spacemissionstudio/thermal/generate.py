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
"""A starting thermal model from the 3D model (decision T-04): one node
per part with mass, external when the part is in the surface model and
internal otherwise; a contact conductor wherever two parts touch face to
face (``geometry.contacts``) and between each internal part and the part
it sits in, over its mounting face (``geometry.enclosures``, T-25), with
the bare-joint coefficient (T-26). Optics are not written: each face
takes its part's material until the user gives it a coating.

The user then merges, splits and renames nodes in the editor.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..schema.thermal import ThermalConfig, ThermalNodeConfig
from . import conductors, geometry

_BAD = re.compile(r"[.\]]")


def node_name(part_name: str) -> str:
    """A node name for a part: its name, without '.' or ']' (which a
    parameter path cannot hold)."""
    return _BAD.sub("-", part_name).strip() or "node"


@dataclass
class Generated:
    """The generated model and what was decided for it, line by line."""

    thermal: ThermalConfig
    notes: list[str] = field(default_factory=list)


def generate(spacecraft, base_dir=None, geom: geometry.Geometry | None = None) -> Generated:
    """The starting thermal model of ``spacecraft`` (module docstring).
    Raises ValueError when it has no 3D model."""
    model = spacecraft.model
    if model is None or not model.parts:
        raise ValueError(f"{spacecraft.name} has no 3D model to build a thermal model from")
    geom = geom if geom is not None else geometry.build(model, base_dir)
    notes: list[str] = []
    nodes, owner = [], {}
    taken: set[str] = set()
    for part in model.parts:
        if part.mass_kg <= 0.0 and part.name not in geom.surface_parts:
            notes.append(f"{part.name}: no mass and no outer faces, left out")
            continue
        name = node_name(part.name)
        while name in taken:
            name += "-1"
        taken.add(name)
        nodes.append(ThermalNodeConfig(name=name, parts=[part.name]))
        owner[part.name] = name
        kind = "external" if part.name in geom.surface_parts else "internal"
        notes.append(f"{part.name}: {kind} node {name!r}"
                     + ("" if part.mass_kg > 0.0 else ", no mass: give it a capacitance"))
    links = []
    for contact in geometry.contacts(geom):
        if contact.a in owner and contact.b in owner:
            a, b = owner[contact.a], owner[contact.b]
            links.append(conductors.contact(f"{a}--{b}", a, b, contact.area_m2))
            notes.append(f"{contact.a} touches {contact.b} over {contact.area_m2:.4f} m^2: contact conductor")
    for inner, holder in geometry.enclosures(model, geom).items():
        if inner in owner and holder in owner:
            area = geometry.mounting_area_m2(geom, inner)
            a, b = owner[holder], owner[inner]
            links.append(conductors.contact(f"{a}--{b}", a, b, area))
            notes.append(f"{inner} sits in {holder}: mounted over its largest face, {area:.4f} m^2")
    names = set()
    unique = []
    for link in links:
        if link.name not in names:
            names.add(link.name)
            unique.append(link)
    return Generated(ThermalConfig(nodes=nodes, conductors=unique), notes)
