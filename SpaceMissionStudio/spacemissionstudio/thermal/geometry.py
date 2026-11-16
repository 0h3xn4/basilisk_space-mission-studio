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
"""The thermal model's geometry, all from the spacecraft's 3D model
(``docs/developer/thermal-design.md``, 2.1):

- :func:`facets`: every outer face of the parts in the surface model, in
  the body frame (the same faces drag and SRP use, without their cap of
  200): a curved part keeps one facet per side, so fluxes are summed per
  facet, never on an averaged normal;
- :func:`contacts`: parts that touch, face to face, and the touching area;
- :func:`enclosures`: the part each internal part sits in;
- :func:`shading_screen`: the faces another part can shade. The thermal
  model assumes no shading (decision T-06); this tells the user where that
  assumption is wrong.

Numpy only.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..model3d import model as model3d
from ..model3d import raycast

_COPLANAR_M = 2.0e-3  # [m] two faces closer than this are in contact
_OPPOSED_COS = -0.9995  # [-] normals within about 1.8 deg of opposite
_SHADED_FRACTION = 0.01  # [-] a face shaded by more than 1 % in some direction counts
_SCREEN_DIRECTIONS = 32
_SCREEN_SAMPLES = 24


@dataclass(frozen=True)
class ThermalFacet:
    """One flat outer face in the body frame: ``part`` and ``face`` as the
    model names them, the face ``group`` ("+x", "sides", ...), area,
    outward unit normal and centroid."""

    part: str
    face: str
    group: str
    area_m2: float  # [m^2]
    normal_b: np.ndarray  # [-]
    centroid_b: np.ndarray  # [m]

    @property
    def key(self) -> str:
        """``"part:face"``, as the thermal section names a face."""
        return f"{self.part}:{self.face}"


@dataclass
class Geometry:
    """The derived model and its thermal facets, built once per model."""

    derived: model3d.DerivedModel
    facets: list[ThermalFacet]
    surface_parts: set = field(default_factory=set)  # parts with faces in the surface model
    _contacts: list | None = None
    _covered: dict = field(default_factory=dict)  # facet index -> [m^2] covered by a touching part

    def covered_m2(self, index: int) -> float:
        """The area [m^2] of facet ``index`` another part covers (face to
        face): it neither sees space nor the Sun (:func:`contacts`)."""
        contacts(self)
        return min(self._covered.get(index, 0.0), self.facets[index].area_m2)


def _split(name: str, part_names: list[str]) -> tuple[str, str]:
    """``("part", "face")`` of a derived face name ``"part: face"``; the
    longest part name that prefixes it wins (a part name may hold ": ")."""
    best = max((p for p in part_names if name.startswith(p + ": ")), key=len)
    return best, name[len(best) + 2:]


def build(model, base_dir=None, derived: model3d.DerivedModel | None = None) -> Geometry:
    """The :class:`Geometry` of a :class:`SpacecraftModelConfig` as
    deployed."""
    derived = derived if derived is not None else model3d.derive(model, base_dir=base_dir)
    names = [p.name for p in model.parts]
    facets = []
    for face in derived.faces:
        part, face_name = _split(face.name, names)
        facets.append(ThermalFacet(part, face_name, face.group, float(face.area_m2),
                                   np.asarray(face.normal, dtype=float), np.asarray(face.centroid_m, dtype=float)))
    return Geometry(derived, facets, {f.part for f in facets})


def facets(model, base_dir=None) -> list[ThermalFacet]:
    """The thermal facets of ``model`` (module docstring)."""
    return build(model, base_dir).facets


# --- contacts -------------------------------------------------------------------


@dataclass(frozen=True)
class Contact:
    """Two parts that touch over ``area_m2`` [m^2], face to face."""

    a: str
    b: str
    area_m2: float


def _triangles(mesh):
    a, b, c = mesh.corners()
    cross = np.cross(b - a, c - a)
    norm = np.linalg.norm(cross, axis=1)
    keep = norm > 1.0e-14
    normals = cross[keep] / norm[keep, None]
    return a[keep], b[keep], c[keep], normals, np.einsum("ij,ij->i", normals, a[keep])


def _clip(polygon: np.ndarray, edge_a: np.ndarray, edge_b: np.ndarray) -> np.ndarray:
    """``polygon`` (k, 2) clipped to the left of the edge a -> b
    (Sutherland-Hodgman, one edge)."""
    if len(polygon) == 0:
        return polygon
    d = edge_b - edge_a
    side = d[0] * (polygon[:, 1] - edge_a[1]) - d[1] * (polygon[:, 0] - edge_a[0])
    out = []
    for i in range(len(polygon)):
        j = (i + 1) % len(polygon)
        p, q, sp, sq = polygon[i], polygon[j], side[i], side[j]
        if sp >= 0.0:
            out.append(p)
        if (sp >= 0.0) != (sq >= 0.0):
            out.append(p + (q - p) * (sp / (sp - sq)))
    return np.asarray(out).reshape(-1, 2)


def _area(polygon: np.ndarray) -> float:
    if len(polygon) < 3:
        return 0.0
    x, y = polygon[:, 0], polygon[:, 1]
    return 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def _ccw(triangle: np.ndarray) -> np.ndarray:
    (x0, y0), (x1, y1), (x2, y2) = triangle
    return triangle if (x1 - x0) * (y2 - y0) - (y1 - y0) * (x2 - x0) >= 0.0 else triangle[::-1]


def overlap_area(tri_a: np.ndarray, tri_b: np.ndarray, normal: np.ndarray) -> float:
    """The area [m^2] two coplanar triangles (3, 3) share, in the plane of
    ``normal``."""
    u = np.cross(normal, [1.0, 0.0, 0.0])
    if np.linalg.norm(u) < 0.1:
        u = np.cross(normal, [0.0, 1.0, 0.0])
    u /= np.linalg.norm(u)
    v = np.cross(normal, u)
    pa = _ccw(np.column_stack([tri_a @ u, tri_a @ v]))
    pb = _ccw(np.column_stack([tri_b @ u, tri_b @ v]))
    polygon = pa
    for i in range(3):
        polygon = _clip(polygon, pb[i], pb[(i + 1) % 3])
    return _area(polygon)


def _pair_contact(mesh_a, mesh_b) -> tuple[float, list, list]:
    """The touching area of two meshes, and per side ``(normal, area)`` of
    each touching triangle's share."""
    a0, a1, a2, na, da = _triangles(mesh_a)
    b0, b1, b2, nb, db = _triangles(mesh_b)
    if not len(na) or not len(nb):
        return 0.0, [], []
    opposed = (na @ nb.T) < _OPPOSED_COS
    coplanar = np.abs(da[:, None] + db[None, :]) < _COPLANAR_M
    total, side_a, side_b = 0.0, [], []
    for i, j in zip(*np.nonzero(opposed & coplanar), strict=True):
        tri_a = np.vstack([a0[i], a1[i], a2[i]])
        tri_b = np.vstack([b0[j], b1[j], b2[j]])
        if (tri_a.max(0) < tri_b.min(0) - _COPLANAR_M).any() or (tri_b.max(0) < tri_a.min(0) - _COPLANAR_M).any():
            continue
        shared = overlap_area(tri_a, tri_b, na[i])
        if shared > 0.0:
            total += shared
            side_a.append((na[i], shared))
            side_b.append((nb[j], shared))
    return total, side_a, side_b


def contacts(geometry: Geometry) -> list[Contact]:
    """Every pair of parts whose outer surfaces touch face to face
    (opposite normals, within 2 mm of the same plane), with the touching
    area: a box bolted flat on the bus, a panel against a wall. The area is
    the exact overlap of the touching triangles."""
    if geometry._contacts is not None:
        return geometry._contacts
    built = [p for p in geometry.derived.parts if p.mesh is not None and len(p.mesh.triangles)]
    bounds = {p.name: (p.mesh.vertices.min(0) - _COPLANAR_M, p.mesh.vertices.max(0) + _COPLANAR_M) for p in built}
    by_part: dict[str, list[int]] = {}
    for index, facet in enumerate(geometry.facets):
        by_part.setdefault(facet.part, []).append(index)

    def cover(part: str, pieces: list) -> None:
        for normal, area in pieces:
            best = max(by_part.get(part, []), key=lambda k: float(geometry.facets[k].normal_b @ normal), default=None)
            if best is not None and float(geometry.facets[best].normal_b @ normal) > 0.99:
                geometry._covered[best] = geometry._covered.get(best, 0.0) + area

    found = []
    for i, first in enumerate(built):
        for second in built[i + 1:]:
            low_a, high_a = bounds[first.name]
            low_b, high_b = bounds[second.name]
            if (high_a < low_b).any() or (high_b < low_a).any():
                continue
            area, side_a, side_b = _pair_contact(first.mesh, second.mesh)
            if area > 1.0e-6:
                found.append(Contact(first.name, second.name, area))
                cover(first.name, side_a)
                cover(second.name, side_b)
    geometry._contacts = found
    return found


def enclosures(model, geometry: Geometry) -> dict[str, str]:
    """``{internal part: the part it sits in}``: for each part out of the
    surface model, the smallest surface part whose bounding box holds its
    centre (decision T-25)."""
    boxes = {p.name: (p.mesh.vertices.min(0), p.mesh.vertices.max(0))
             for p in geometry.derived.parts if p.mesh is not None and len(p.mesh.vertices)}
    result = {}
    for part in model.parts:
        if part.name in geometry.surface_parts or part.name not in boxes:
            continue
        centre = 0.5 * (boxes[part.name][0] + boxes[part.name][1])
        holders = [(float(np.prod(high - low)), name) for name, (low, high) in boxes.items()
                   if name != part.name and name in geometry.surface_parts
                   and (low <= centre).all() and (centre <= high).all()]
        if holders:
            result[part.name] = min(holders)[1]
    return result


def mounting_area_m2(geometry: Geometry, part: str) -> float:
    """The area [m^2] an internal part is taken to be mounted by: its
    largest flat face (a unit bolted on its base)."""
    derived = next((p for p in geometry.derived.parts if p.name == part), None)
    if derived is None or derived.mesh is None or not len(derived.mesh.triangles):
        return 0.0
    _a, _b, _c, normals, _d = _triangles(derived.mesh)
    a, b, c = derived.mesh.corners()
    areas = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    areas = areas[areas > 0.5e-14]
    keys = np.round(normals, 3)
    _unique, inverse = np.unique(keys, axis=0, return_inverse=True)
    return float(np.bincount(inverse.ravel(), weights=areas).max())


# --- shading screen --------------------------------------------------------------


@dataclass(frozen=True)
class ShadedFace:
    """A face that ``by`` (other parts) shade by up to ``fraction`` of its
    light, over the screened directions."""

    part: str
    face: str
    fraction: float
    by: tuple


def shading_screen(model, geometry: Geometry, directions: int = _SCREEN_DIRECTIONS,
                   samples: int = _SCREEN_SAMPLES) -> list[ShadedFace]:
    """The faces another part can shade from some direction (light from
    ``directions`` spread over the sphere, ``samples`` rays per face):
    where the thermal model's no-shading assumption (T-06) is wrong. Empty
    for a model of one convex part."""
    if len(geometry.surface_parts) < 2:
        return []
    scene = raycast.scene_from_model(model, derived=geometry.derived)
    sky = raycast.shapes._fibonacci_directions(directions)
    found = []
    for facet in geometry.facets:
        worst, by = 0.0, set()
        for direction in sky:
            if float(facet.normal_b @ direction) <= 0.05:
                continue
            shading = scene.face_shading(facet.part, facet.face, direction, samples)
            if shading.shaded_fraction > _SHADED_FRACTION:
                worst = max(worst, shading.shaded_fraction)
                by.update(name for name, share in shading.by_part.items() if share > 0.0)
        if worst > 0.0:
            found.append(ShadedFace(facet.part, facet.face, worst, tuple(sorted(by))))
    return found
