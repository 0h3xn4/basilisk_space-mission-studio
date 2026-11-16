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
"""The solvable thermal network (design 2.6), built from a spacecraft's
``thermal`` section and its 3D model:

- each external facet belongs to one node (a face entry naming a node
  wins over its part's node; an exact face over a face group over the
  whole part), with its radiating area (less what touching parts cover),
  its solar absorptance and infrared emissivity: the face entry's values,
  else its coating's, else the model's face or part material's;
- MLI on a face scales its optics by ``e* / (eps_o + e*)`` (a massless
  outer layer, decision T-09);
- each node's capacitance (T-05), conductors through the calculator,
  heat pipes, radiative links, dissipations (constant or a power-budget
  load, T-11) and heaters.

A face without optics, a material without a value, or a part in no
node is a :class:`ThermalModelError` naming it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import conductors, library

ZERO_C_K = 273.15  # [K]


class ThermalModelError(ValueError):
    """A thermal model that cannot be solved, saying what to fix."""


@dataclass(frozen=True)
class FacetOptics:
    """One external facet as the network uses it."""

    facet: int  # index into the geometry's facets
    node: int
    area_m2: float  # [m^2] radiating: the facet's less what touching parts cover
    absorptance: float  # [-] effective (MLI included)
    emissivity: float  # [-] effective (MLI included)
    radiator: bool
    source: str  # where the optics come from


@dataclass(frozen=True)
class Link:
    name: str
    i: int
    j: int
    value: float  # [W/K] or [m^2] for a radiative link
    how: str = ""


@dataclass(frozen=True)
class HeatPipe:
    name: str
    i: int
    j: int
    on_w_k: float  # [W/K]
    off_w_k: float  # [W/K]
    low_k: float  # [K]
    high_k: float  # [K]


@dataclass(frozen=True)
class Heater:
    name: str
    node: int
    power_w: float  # [W]
    on_k: float  # [K]
    off_k: float  # [K]


@dataclass
class Network:
    """Everything the solver needs (module docstring)."""

    names: list[str]
    capacitance_j_k: np.ndarray  # (m,) [J/K]
    capacitance_how: list[str]
    facets: list[FacetOptics]
    conductors: list[Link]
    heat_pipes: list[HeatPipe]
    links: list[Link]  # radiative, value = eA [m^2]
    dissipation_w: np.ndarray  # (m,) [W]
    dissipations: list[tuple[str, int, float, str]]  # (name, node, W, how)
    heaters: list[Heater]
    operating_k: list  # per node: (low, high) [K] or None
    survival_k: list
    initial_k: np.ndarray  # (m,) [K] NaN where not given
    unassigned: list[str] = field(default_factory=list)  # "part:face" of facets in no node
    conductance_tables: dict = field(default_factory=dict)  # conductor index -> (ThermalConductorConfig, materials)
    capacitance_tables: dict = field(default_factory=dict)  # node index -> (mass [kg], (k, 2) [[K, J/(kg*K)]])

    def index(self, name: str) -> int:
        return self.names.index(name)

    def heat_capacity(self, temperatures_k: np.ndarray) -> np.ndarray:
        """``C(T)`` [J/K] per node: the constant one, or mass times the
        specific-heat table at the node's temperature (held beyond its
        ends)."""
        if not self.capacitance_tables:
            return self.capacitance_j_k
        out = self.capacitance_j_k.copy()
        for i, (mass, rows) in self.capacitance_tables.items():
            out[i] = mass * float(np.interp(temperatures_k[i], rows[:, 0], rows[:, 1]))
        return out

    def enthalpy(self, temperatures_k: np.ndarray) -> np.ndarray:
        """``H(T)`` [J] per node, ``C T`` for a constant capacity and the
        exact integral of mass times the piecewise-linear specific heat
        from 0 K otherwise (an offset that cancels in every difference)."""
        out = self.capacitance_j_k * temperatures_k
        for i, (mass, rows) in self.capacitance_tables.items():
            out[i] = mass * _integral(rows, float(temperatures_k[i]))
        return out

    def conductance_matrix(self, temperatures_k: np.ndarray | None = None) -> np.ndarray:
        """``K`` (m, m): ``K @ T`` is the net conducted heat into each node
        [W], from the conductors (temperature-dependent ones at the mean
        of their nodes, Phase 2)."""
        m = len(self.names)
        k = np.zeros((m, m))
        for index, link in enumerate(self.conductors):
            g = link.value
            if index in self.conductance_tables and temperatures_k is not None:
                config, materials = self.conductance_tables[index]
                mean_c = 0.5 * (temperatures_k[link.i] + temperatures_k[link.j]) - ZERO_C_K
                g = conductors.conductance(config, materials, mean_c).value_w_k
            k[link.i, link.i] -= g
            k[link.j, link.j] -= g
            k[link.i, link.j] += g
            k[link.j, link.i] += g
        return k


def _integral(rows: np.ndarray, upper: float) -> float:
    """``integral from 0 to upper`` of the table (linear between rows,
    constant beyond its ends)."""
    x, y = rows[:, 0], rows[:, 1]
    if upper <= x[0]:
        return y[0] * upper
    total = y[0] * x[0]
    for k in range(len(x) - 1):
        if upper <= x[k + 1]:
            value = y[k] + (y[k + 1] - y[k]) * (upper - x[k]) / (x[k + 1] - x[k])
            return total + 0.5 * (y[k] + value) * (upper - x[k])
        total += 0.5 * (y[k] + y[k + 1]) * (x[k + 1] - x[k])
    return total + y[-1] * (upper - x[-1])


def _material_optics(name: str, materials) -> tuple[float | None, float | None]:
    a = library.absorptance(name, materials)
    e = library.emissivity(name, materials)
    return (None if a is None else a.value), (None if e is None else e.value)


def _face_entry(entries: dict, part: str, face: str, group: str):
    """The most specific face entry of a facet: the exact face, its group,
    the whole part; or None."""
    for key in (f"{part}:{face}", f"{part}:{group}", part):
        if key in entries:
            return entries[key]
    return None


def _model_material(model, part, face_group: str) -> str:
    for prop in model.face_properties:
        if prop.part == part.name and prop.face == face_group and prop.material:
            return prop.material
    return part.material


def _load_power(spacecraft, source: str) -> float:
    if source == "bus":
        return float(spacecraft.power.bus_idle_power_w)
    if source == "comms":
        return float(spacecraft.comms_pointing.comms_power_w)
    if source == "transmitter":
        return float(spacecraft.data_handling.transmitter_power_w)
    name = source.split(":", 1)[1]
    return float(next(i.power_w for i in spacecraft.data_handling.instruments if i.name == name))


def build(spacecraft, thermal, geometry) -> Network:
    """The :class:`Network` of ``spacecraft`` with thermal section
    ``thermal`` (a case's, overrides applied) on ``geometry``
    (``thermal.geometry.build`` of its model)."""
    model = spacecraft.model
    materials = list(model.materials) if model is not None else []
    parts = {p.name: p for p in model.parts} if model is not None else {}
    names = [n.name for n in thermal.nodes]
    owner = {part: names.index(node.name) for node in thermal.nodes for part in node.parts}
    entries = {e.name: e for e in thermal.faces}

    facets, unassigned, missing = [], [], []
    for index, facet in enumerate(geometry.facets):
        entry = _face_entry(entries, facet.part, facet.face, facet.group)
        node = names.index(entry.node) if entry is not None and entry.node else owner.get(facet.part)
        if node is None:
            unassigned.append(facet.key)
            continue
        alpha = entry.absorptance if entry is not None else None
        eps = entry.emissivity if entry is not None else None
        source = "face entry"
        if (alpha is None or eps is None) and entry is not None and entry.coating:
            a, e = _material_optics(entry.coating, materials)
            alpha, eps = (a if alpha is None else alpha), (e if eps is None else eps)
            source = f"coating {entry.coating}"
        if alpha is None or eps is None:
            material = _model_material(model, parts[facet.part], facet.group) if facet.part in parts else ""
            if material:
                a, e = _material_optics(material, materials)
                alpha, eps = (a if alpha is None else alpha), (e if eps is None else eps)
                source = f"model material {material}"
        if alpha is None or eps is None:
            missing.append(facet.key)
            continue
        if entry is not None and entry.mli_effective_emittance is not None:
            scale = entry.mli_effective_emittance / (eps + entry.mli_effective_emittance)
            alpha, eps = alpha * scale, eps * scale
            source += f", MLI e* {entry.mli_effective_emittance:g}"
        area = facet.area_m2 - geometry.covered_m2(index)
        if area <= 1.0e-12:
            continue
        facets.append(FacetOptics(index, node, area, float(alpha), float(eps),
                                  bool(entry.radiator) if entry is not None else False, source))
    if missing:
        shown = ", ".join(missing[:8]) + (", ..." if len(missing) > 8 else "")
        raise ThermalModelError(f"{spacecraft.name}: faces without absorptance and emissivity: {shown} -- give them "
                                "a coating or values in the thermal model's faces, or a material in the 3D model")

    capacitance, how, cp_tables = [], [], {}
    default_cp = library.default_specific_heat()
    for node in thermal.nodes:
        if node.specific_heat_table is not None:
            mass = node.mass_kg if node.mass_kg is not None else sum(parts[p].mass_kg for p in node.parts
                                                                      if p in parts)
            if mass <= 0.0:
                raise ThermalModelError(f"{spacecraft.name}: node {node.name!r} has a specific_heat_table and no mass")
            rows = np.array(node.specific_heat_table, dtype=float)
            rows[:, 0] += ZERO_C_K
            cp_tables[len(capacitance)] = (float(mass), rows)
            capacitance.append(float(mass * np.interp(ZERO_C_K + 20.0, rows[:, 0], rows[:, 1])))
            how.append(f"{mass:.4g} kg x a specific-heat table ({len(rows)} rows; at 20 degC shown)")
            continue
        if node.capacitance_j_k is not None:
            capacitance.append(float(node.capacitance_j_k))
            how.append("given")
            continue
        node_parts = [parts[p] for p in node.parts if p in parts]
        mass = node.mass_kg if node.mass_kg is not None else sum(p.mass_kg for p in node_parts)
        if node.specific_heat_j_kg_k is not None:
            cp, where = float(node.specific_heat_j_kg_k), "given"
        else:
            found = library.specific_heat(node.material, materials) if node.material else None
            if found is None:
                weighted = [(p.mass_kg, library.specific_heat(p.material, materials)) for p in node_parts
                            if p.material]
                weighted = [(m, v) for m, v in weighted if v is not None and m > 0]
                if weighted:
                    total = sum(m for m, _v in weighted)
                    found = library.Sourced(sum(m * v.value for m, v in weighted) / total, "the parts' materials")
            found = found or default_cp
            cp, where = found.value, found.source
        if mass <= 0.0:
            raise ThermalModelError(f"{spacecraft.name}: node {node.name!r} has no mass and no capacitance_j_k")
        capacitance.append(mass * cp)
        how.append(f"{mass:.4g} kg x {cp:.4g} J/(kg*K) ({where})")

    links, tables = [], {}
    for item in thermal.conductors:
        value = conductors.conductance(item, materials)
        links.append(Link(item.name, names.index(item.a), names.index(item.b), value.value_w_k, value.how))
        if item.kind == "material" and item.conductivity_table:
            tables[len(links) - 1] = (item, materials)
    pipes = [HeatPipe(p.name, names.index(p.a), names.index(p.b), float(p.conductance_w_k),
                      float(p.off_conductance_w_k), p.operating_c[0] + ZERO_C_K, p.operating_c[1] + ZERO_C_K)
             for p in thermal.heat_pipes]
    radiative = [Link(r.name, names.index(r.a), names.index(r.b), float(r.effective_area_m2))
                 for r in thermal.radiative_links]
    dissipation = np.zeros(len(names))
    dissipations = []
    for item in thermal.dissipations:
        power = float(item.power_w) if item.power_w is not None else _load_power(spacecraft, item.source)
        dissipation[names.index(item.node)] += power
        dissipations.append((item.name, names.index(item.node), power, item.source or "given"))
    heaters = [Heater(h.name, names.index(h.node), float(h.power_w), h.on_c + ZERO_C_K, h.off_c + ZERO_C_K)
               for h in thermal.heaters if h.enabled]

    def limits(value):
        return None if value is None else (value[0] + ZERO_C_K, value[1] + ZERO_C_K)

    initial = np.array([np.nan if n.initial_c is None else n.initial_c + ZERO_C_K for n in thermal.nodes])
    return Network(names, np.array(capacitance), how, facets, links, pipes, radiative, dissipation, dissipations,
                   heaters, [limits(n.operating_c) for n in thermal.nodes],
                   [limits(n.survival_c) for n in thermal.nodes], initial, unassigned, tables, cp_tables)
