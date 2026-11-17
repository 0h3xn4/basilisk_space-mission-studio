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
"""Targets, windows, passes and eclipses (operations.targets,
operations.opportunities; decision O-17): file import, polygon sampling,
window edges and geometry checked against independent computations,
masks raising the minimum elevation, AOS/LOS interpolated. No Basilisk."""

import json
import math

import numpy as np
import operations_fixtures as fixtures
import pytest

from spacemissionstudio.operations import geometry, opportunities, targets
from spacemissionstudio.operations.timebase import TimeBase
from spacemissionstudio.schema.operations import StationPlanningConfig, TargetConfig


def test_targets_read_from_csv_and_geojson():
    """CSV rows and GeoJSON features become targets; GeoJSON's longitude,
    latitude order is respected and the closing vertex dropped; errors name
    the row or feature."""
    text = ("name,latitude_deg,longitude_deg,priority,activity,max_off_nadir_deg,sun_min_deg,acquisitions\n"
            "a,51.9,4.5,1,image,30,10,2\nb,48.1,11.6,2,image,25,,\n")
    rows = targets.read_csv(text)
    assert [(t.name, t.priority, t.acquisitions, t.sun_elevation_deg) for t in rows] == [
        ("a", 1, 2, [10.0, 90.0]), ("b", 2, 1, None)]
    with pytest.raises(targets.TargetFileError, match="no 'priority' column"):
        targets.read_csv("name,latitude_deg,longitude_deg\n")
    with pytest.raises(targets.TargetFileError, match="row 2: latitude_deg 'x'"):
        targets.read_csv(text.replace("51.9", "x"))
    collection = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [4.48, 51.92]},
         "properties": {"name": "p", "priority": 1, "activity": "image", "max_off_nadir_deg": 30}},
        {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[5, 52], [6, 52], [6, 53], [5, 52]]]},
         "properties": {"name": "q", "priority": 2, "activity": "image", "max_off_nadir_deg": 20, "cell_km": 5}}]}
    point, polygon = targets.read_geojson(json.dumps(collection))
    assert (point.latitude_deg, point.longitude_deg) == (51.92, 4.48)
    assert polygon.kind == "polygon" and polygon.vertices_deg == [[52.0, 5.0], [52.0, 6.0], [53.0, 6.0]]
    with pytest.raises(targets.TargetFileError, match="feature 0: geometry 'LineString'"):
        targets.read_geojson(json.dumps({"type": "FeatureCollection", "features": [
            {"geometry": {"type": "LineString", "coordinates": []}, "properties": {}}]}))


def test_a_polygon_is_sampled_at_cell_centres_inside_it():
    """A 1 deg x 1 deg square at 52 N sampled every 10 km: about 111 x 68
    km, so 11 x 6 to 7 points, all inside; the centroid is the square's
    centre within a cell."""
    square = TargetConfig("sq", 1, "image", 20.0, kind="polygon",
                          vertices_deg=[[52.0, 5.0], [52.0, 6.0], [53.0, 6.0], [53.0, 5.0]], cell_km=10.0)
    sample = targets.sample(square)
    assert 60 <= len(sample.latitude_deg) <= 80
    assert np.all((sample.latitude_deg > 52.0) & (sample.latitude_deg < 53.0))
    assert sample.centroid[0] == pytest.approx(52.5, abs=0.1) and sample.centroid[1] == pytest.approx(5.5, abs=0.15)
    triangle = TargetConfig("tri", 1, "image", 20.0, kind="polygon",
                            vertices_deg=[[52.0, 5.0], [52.0, 6.0], [53.0, 5.0]], cell_km=10.0)
    assert len(targets.sample(triangle).latitude_deg) == pytest.approx(len(sample.latitude_deg) / 2.0, rel=0.25)


def test_runs_interpolate_their_edges():
    """A margin crossing zero between samples gives the interpolated
    time; a run touching the grid's ends keeps the end."""
    t = np.arange(0.0, 60.0, 10.0)
    margin = np.array([-1.0, 1.0, 3.0, 1.0, -3.0, 2.0])
    assert opportunities.runs(margin, t) == [(5.0, 32.5, 1, 3), (46.0, 50.0, 5, 5)]


def test_masks_raise_the_minimum_elevation_and_wrap():
    """Linear in azimuth between the mask's points, wrapping at 360 deg,
    never below the station's own minimum."""
    mask = [[0.0, 5.0], [90.0, 15.0], [270.0, 5.0]]
    values = opportunities.mask_elevation(np.array([0.0, 45.0, 90.0, 180.0, 315.0, 359.0]), 8.0, mask)
    assert values == pytest.approx([8.0, 10.0, 15.0, 10.0, 8.0, 8.0])
    assert opportunities.mask_elevation(np.array([10.0]), 3.0, []) == pytest.approx([3.0])


@pytest.fixture(scope="module")
def planning():
    scenario = fixtures.scenario(horizon={"start_utc": "2030-01-01T08:30:00Z", "end_utc": "2030-01-03T08:30:00Z"})
    geo = geometry.build(scenario)
    return scenario, geo, opportunities.find(scenario, geo, TimeBase(scenario.epoch_utc))


def test_target_windows_keep_every_limit_and_their_geometry_is_independent(planning):
    """Inside a window the off-nadir angle, the elevation and the Sun meet
    the target's limits; the off-nadir angle and elevation agree with a
    spherical-Earth computation from the range (law of cosines)."""
    scenario, geo, found = planning
    windows = found.windows_of("munich")
    assert windows
    for window in windows:
        inside = (window.time_s >= window.start_s) & (window.time_s <= window.end_s)
        assert np.all(window.off_nadir_deg[inside] <= 45.0 + 1e-9) and np.all(window.elevation_deg[inside] >= 0.0)
        k = int(np.argmin(np.where(inside, window.off_nadir_deg, np.inf)))
        r_sc = np.linalg.norm(geo.tracks["eo-sat"].position_n[geo.time_s.searchsorted(window.time_s[k])])
        rho = window.range_m[k]
        r_t = np.linalg.norm(geo.site(48.14, 11.58, 0.0)[0][0])
        eta = math.degrees(math.acos((r_sc ** 2 + rho ** 2 - r_t ** 2) / (2.0 * r_sc * rho)))
        assert window.off_nadir_deg[k] == pytest.approx(eta, abs=0.2)  # the ellipsoid's normal vs the radius
        assert window.end_s > window.start_s
    # the Sun's limit holds for rotterdam's windows (10 deg minimum)
    for window in found.windows_of("rotterdam"):
        inside = (window.time_s >= window.start_s) & (window.time_s <= window.end_s)
        assert np.all(window.sun_elevation_deg[inside] >= 10.0 - 1e-9)


def test_passes_with_a_mask_are_shorter_and_their_edges_interpolated(planning):
    """The mask (15 deg to the south) shortens passes against the bare 10
    deg minimum; AOS and LOS lie where elevation minus the mask crosses
    zero; the predicted margin is the link budget's."""
    scenario, geo, found = planning
    station = scenario.ground_stations[0]
    bare = opportunities.station_passes(geo, station, None, "eo-sat")
    masked = found.passes_of("eo-sat", "berlin-gs")
    assert len(masked) <= len(bare) and sum(p.duration_s for p in masked) < sum(p.duration_s for p in bare)
    for item in masked:
        for edge in (item.aos_s, item.los_s):
            if edge in (geo.time_s[0], geo.time_s[-1]):
                continue  # a pass cut by the horizon
            elevation = np.interp(edge, item.time_s, item.elevation_deg)
            azimuth = np.interp(edge, item.time_s, np.unwrap(np.radians(item.azimuth_deg)))
            limit = opportunities.mask_elevation(np.degrees(azimuth) % 360.0, 10.0,
                                                 scenario.operations.stations[0].azimuth_mask)
            assert elevation == pytest.approx(float(limit), abs=0.3)
        assert item.max_elevation_deg >= np.max(item.elevation_deg) - 1e-9
        assert math.isfinite(item.margin_db[0]) and item.margin_db[1] >= item.margin_db[0]


def test_eclipses_and_polygon_coverage(planning):
    """Eclipses come once per orbit (about 35 min at 550 km in January);
    a polygon's windows carry the share of its points the field of view
    covers."""
    scenario, geo, found = planning
    eclipses = found.eclipses["eo-sat"]
    assert 28 <= len(eclipses) <= 32 and all(1800.0 < b - a < 2400.0 for a, b in eclipses[1:-1])
    polygon = TargetConfig("polder", 1, "image", 45.0, kind="polygon", cell_km=5.0,
                           vertices_deg=[[48.0, 11.4], [48.0, 11.8], [48.3, 11.8], [48.3, 11.4]])
    windows = opportunities.target_windows(geo, polygon, ["eo-sat"], TimeBase(scenario.epoch_utc),
                                           field_of_view_deg=6.0)
    assert windows and all(w.coverage is not None for w in windows)
    best = max(float(np.max(w.coverage)) for w in windows)
    assert 0.0 < best <= 1.0
    narrow = opportunities.target_windows(geo, polygon, ["eo-sat"], TimeBase(scenario.epoch_utc),
                                          field_of_view_deg=0.5)
    assert max(float(np.max(w.coverage)) for w in narrow) < best


def test_station_settings_none_and_validity(planning):
    """Without planning settings a station uses its own minimum; a
    target's validity window removes windows outside it."""
    scenario, geo, _found = planning
    t0 = scenario.operations.targets[1]
    base = TimeBase(scenario.epoch_utc)
    every = opportunities.target_windows(geo, t0, ["eo-sat"], base)
    limited = TargetConfig(**{**t0.__dict__, "valid_utc": ["2030-01-02T00:00:00Z", "2030-01-03T08:30:00Z"]})
    later = opportunities.target_windows(geo, limited, ["eo-sat"], base)
    cut = base.to_sim("2030-01-02T00:00:00Z")
    assert all(w.start_s >= cut - 1e-6 for w in later) and len(later) <= len(every)
    assert StationPlanningConfig("berlin-gs").capacity == 1
