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
"""The thermal model's checks, shown in the Problems panel while the
scenario is edited (design 2.9): outer faces in no node, faces without
optics, nodes without capacity or without a path to space, and the
faces another part can shade, which the model does not account for
(decision T-06). References to missing parts, faces, nodes and power
loads are refused by the schema's validation, as every reference is.

Each is an :class:`engine.findings.Finding` prefixed with the spacecraft
and ``thermal``, so the Problems panel places it.
"""

from __future__ import annotations

from ..engine.findings import Finding
from . import geometry as geometry_module
from . import network

_SHOWN = 6
_SCREEN_CACHE: dict[str, list] = {}


def _shown(items: list[str]) -> str:
    return ", ".join(items[:_SHOWN]) + (f" and {len(items) - _SHOWN} more" if len(items) > _SHOWN else "")


def shaded_faces(model, geom) -> list:
    """The shading screen of ``model`` (``geometry.shading_screen``),
    cached on the model's content: it is ray casting, and the checks run
    on every edit."""
    import json
    from dataclasses import asdict

    key = json.dumps(asdict(model), sort_keys=True, default=str)
    if key not in _SCREEN_CACHE:
        if len(_SCREEN_CACHE) > 32:
            _SCREEN_CACHE.clear()
        _SCREEN_CACHE[key] = geometry_module.shading_screen(model, geom)
    return _SCREEN_CACHE[key]


def shading_warning(sc, geom) -> Finding | None:
    """The prominent warning when parts can shade one another, or None."""
    shaded = shaded_faces(sc.model, geom)
    if not shaded:
        return None
    worst = sorted(shaded, key=lambda s: -s.fraction)
    faces = [f"{s.part}:{s.face} (up to {s.fraction:.0%} by {', '.join(s.by)})" for s in worst]
    return Finding(f"{sc.name}: thermal: {len(shaded)} faces can be shaded by other parts, which the thermal model "
                   f"does not account for -- their sunlight is overestimated: {_shown(faces)}", "thermal.shading",
                   actual=f"{len(shaded)} faces")


def checks(sc, base_dir=None, geom=None) -> list[Finding]:
    """The checks of spacecraft ``sc``'s thermal section (module
    docstring); empty when it has none."""
    thermal = sc.thermal
    if thermal is None or sc.model is None:
        return []
    geom = geom if geom is not None else geometry_module.build(sc.model, base_dir)
    where = f"{sc.name}: thermal"
    found: list[Finding] = []
    names = thermal.node_names()
    owner = {part: node.name for node in thermal.nodes for part in node.parts}
    entries = {e.name: e for e in thermal.faces}
    materials = list(sc.model.materials)
    parts = {p.name: p for p in sc.model.parts}
    unassigned, missing = [], []
    radiating: set[str] = set()
    for facet in geom.facets:
        entry = network._face_entry(entries, facet.part, facet.face, facet.group)
        node = entry.node if entry is not None and entry.node else owner.get(facet.part)
        if node is None:
            unassigned.append(facet.key)
            continue
        alpha = entry.absorptance if entry is not None else None
        eps = entry.emissivity if entry is not None else None
        for material in ([entry.coating] if entry is not None and entry.coating else []) + \
                [network._model_material(sc.model, parts[facet.part], facet.group)]:
            if material and (alpha is None or eps is None):
                a, e = network._material_optics(material, materials)
                alpha, eps = (a if alpha is None else alpha), (e if eps is None else eps)
        if alpha is None or eps is None:
            missing.append(facet.key)
        elif eps > 0.0:
            radiating.add(node)
    if unassigned:
        found.append(Finding(f"{where}: outer faces in no node: {_shown(unassigned)}", "thermal.unassigned_face",
                             actual=f"{len(unassigned)} faces"))
    if missing:
        found.append(Finding(f"{where}: faces without absorptance and emissivity: {_shown(missing)}",
                             "thermal.missing_optics", actual=f"{len(missing)} faces"))
    for node in thermal.nodes:
        mass = node.mass_kg if node.mass_kg is not None else sum(parts[p].mass_kg for p in node.parts if p in parts)
        if node.capacitance_j_k is None and mass <= 0.0:
            found.append(Finding(f"{where}: node {node.name!r} has no capacitance and no mass",
                                 "thermal.no_capacitance"))
    edges = {name: set() for name in names}
    for item in list(thermal.conductors) + list(thermal.heat_pipes) + list(thermal.radiative_links):
        edges[item.a].add(item.b)
        edges[item.b].add(item.a)
    for node in names:
        seen, stack = {node}, [node]
        while stack:
            for nxt in edges[stack.pop()] - seen:
                seen.add(nxt)
                stack.append(nxt)
        if not seen & radiating:
            found.append(Finding(f"{where}: node {node!r} has no path to space (no conductor, heat pipe or link to "
                                 "a node with radiating faces)", "thermal.no_path_to_space"))
    warning = shading_warning(sc, geom)
    if warning is not None:
        found.append(warning)
    return found
