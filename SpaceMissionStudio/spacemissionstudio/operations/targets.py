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
"""Targets: reading them from CSV or GeoJSON (RFC 7946) and sampling a
polygon (decision O-17).

CSV: one target per row, a header naming the columns; ``name``,
``latitude_deg``, ``longitude_deg``, ``priority``, ``activity`` and
``max_off_nadir_deg`` are required; ``acquisitions``, ``altitude_m``,
``min_elevation_deg``, ``sun_min_deg``, ``sun_max_deg``,
``valid_from_utc`` and ``valid_to_utc`` are optional. Points only.

GeoJSON: a FeatureCollection of Point and Polygon features (longitude,
latitude order, WGS-84, as RFC 7946 says); each feature's ``properties``
carries the target's fields (``name``, ``priority``, ``activity``,
``max_off_nadir_deg``, and for a polygon ``cell_km``, optionally
``min_coverage``...). A polygon's first ring is its outline; holes are
not read.
"""

from __future__ import annotations

import csv
import io
import json
import math
from dataclasses import dataclass, fields

import numpy as np

from ..schema.operations import TargetConfig

_KM_PER_DEG = 111.32  # [km] per degree of latitude (and of longitude at the equator), mean sphere
_REQUIRED = ("name", "latitude_deg", "longitude_deg", "priority", "activity", "max_off_nadir_deg")
_NUMBERS = {"latitude_deg", "longitude_deg", "max_off_nadir_deg", "altitude_m", "min_elevation_deg", "cell_km",
            "min_coverage", "sun_min_deg", "sun_max_deg"}
_INTEGERS = {"priority", "acquisitions"}
_TARGET_FIELDS = {f.name for f in fields(TargetConfig)}


class TargetFileError(ValueError):
    """A target file cannot be read; the message names the row or feature."""


def _target(values: dict, where: str) -> TargetConfig:
    values = {k: v for k, v in values.items() if v not in (None, "")}
    for name in list(values):
        try:
            if name in _NUMBERS:
                values[name] = float(values[name])
            elif name in _INTEGERS:
                values[name] = int(values[name])
        except (TypeError, ValueError):
            raise TargetFileError(f"{where}: {name} {values[name]!r} is not a number") from None
    low, high = values.pop("sun_min_deg", None), values.pop("sun_max_deg", None)
    if low is not None or high is not None:
        values["sun_elevation_deg"] = [low if low is not None else -90.0, high if high is not None else 90.0]
    first, last = values.pop("valid_from_utc", None), values.pop("valid_to_utc", None)
    if first is not None or last is not None:
        if first is None or last is None:
            raise TargetFileError(f"{where}: give valid_from_utc and valid_to_utc together")
        values["valid_utc"] = [first, last]
    unknown = sorted(set(values) - _TARGET_FIELDS)
    if unknown:
        raise TargetFileError(f"{where}: unknown field {unknown[0]!r}")
    missing = [name for name in ("name", "priority", "activity", "max_off_nadir_deg") if name not in values]
    if missing:
        raise TargetFileError(f"{where}: missing {missing[0]!r}")
    return TargetConfig(**values)


def read_csv(text: str) -> list[TargetConfig]:
    """Point targets from CSV text (module docstring)."""
    reader = csv.DictReader(io.StringIO(text))
    header = reader.fieldnames or []
    missing = [name for name in _REQUIRED if name not in header]
    if missing:
        raise TargetFileError(f"the CSV header has no {missing[0]!r} column")
    return [_target(dict(row), f"row {index + 2}") for index, row in enumerate(reader)]


def read_geojson(text: str) -> list[TargetConfig]:
    """Point and polygon targets from GeoJSON text (module docstring)."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TargetFileError(f"not JSON: {exc}") from None
    features = data.get("features") if isinstance(data, dict) and data.get("type") == "FeatureCollection" else None
    if not isinstance(features, list):
        raise TargetFileError("a GeoJSON FeatureCollection is needed")
    targets = []
    for index, feature in enumerate(features):
        where = f"feature {index}"
        geometry = (feature or {}).get("geometry") or {}
        values = dict((feature or {}).get("properties") or {})
        kind = geometry.get("type")
        coordinates = geometry.get("coordinates")
        try:
            if kind == "Point":
                values["longitude_deg"], values["latitude_deg"] = float(coordinates[0]), float(coordinates[1])
                values.setdefault("kind", "point")
            elif kind == "Polygon":
                ring = coordinates[0]
                if len(ring) > 3 and ring[0] == ring[-1]:
                    ring = ring[:-1]  # RFC 7946 closes the ring
                values["vertices_deg"] = [[float(p[1]), float(p[0])] for p in ring]
                values["kind"] = "polygon"
            else:
                raise TargetFileError(f"{where}: geometry {kind!r} is not a Point or a Polygon")
        except TargetFileError:
            raise
        except (TypeError, ValueError, IndexError):
            raise TargetFileError(f"{where}: its coordinates cannot be read") from None
        targets.append(_target(values, where))
    return targets


def read(path) -> list[TargetConfig]:
    """Targets from a ``.csv`` or ``.geojson``/``.json`` file."""
    from pathlib import Path

    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".csv":
        return read_csv(text)
    return read_geojson(text)


@dataclass(frozen=True)
class Sample:
    """A polygon's sample points and its centroid (degrees)."""

    latitude_deg: np.ndarray
    longitude_deg: np.ndarray
    centroid: tuple  # (latitude, longitude) [deg]


def _inside(lat: np.ndarray, lon: np.ndarray, vertices: np.ndarray) -> np.ndarray:
    """Even-odd rule in the latitude-longitude plane."""
    inside = np.zeros(lat.shape, dtype=bool)
    count = len(vertices)
    for k in range(count):
        y1, x1 = vertices[k]
        y2, x2 = vertices[(k + 1) % count]
        crosses = (y1 > lat) != (y2 > lat)
        with np.errstate(divide="ignore", invalid="ignore"):
            x_at = (x2 - x1) * (lat - y1) / (y2 - y1) + x1
        inside ^= crosses & (lon < x_at)
    return inside


def sample(target: TargetConfig) -> Sample:
    """Points inside a polygon target every ``cell_km`` (cell centres of a
    latitude-longitude grid, the longitude step widened by 1/cos(lat)); at
    least the centroid when the polygon is smaller than a cell."""
    vertices = np.asarray(target.vertices_deg, dtype=float)
    lat_c = float(vertices[:, 0].mean())
    step_lat = target.cell_km / _KM_PER_DEG  # [deg]
    step_lon = target.cell_km / (_KM_PER_DEG * max(math.cos(math.radians(lat_c)), 1e-3))  # [deg]
    lats = np.arange(vertices[:, 0].min() + step_lat / 2.0, vertices[:, 0].max(), step_lat)
    lons = np.arange(vertices[:, 1].min() + step_lon / 2.0, vertices[:, 1].max(), step_lon)
    grid_lat, grid_lon = np.meshgrid(lats, lons, indexing="ij")
    keep = _inside(grid_lat, grid_lon, vertices)
    lat, lon = grid_lat[keep], grid_lon[keep]
    if len(lat) == 0:
        lat, lon = np.array([lat_c]), np.array([float(vertices[:, 1].mean())])
    return Sample(lat, lon, (float(lat.mean()), float(lon.mean())))


def aim_point(target: TargetConfig) -> tuple[float, float, float]:
    """``(latitude, longitude, altitude)`` the spacecraft points at: the
    point itself, or a polygon's sample centroid."""
    if target.kind == "point":
        return float(target.latitude_deg), float(target.longitude_deg) % 360.0, float(target.altitude_m)
    centre = sample(target).centroid
    return centre[0], centre[1] % 360.0, float(target.altitude_m)
