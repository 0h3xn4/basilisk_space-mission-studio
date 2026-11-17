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
"""Results › 3D View's ground tracks, ground stations and live 2D map:
the map's geometry, its worker, Globe | Map | Both, the globe's track and
stations, a live run and the map's own window (2.12.0,
``docs/developer/windows-views-design.md`` section 3, decision "Ground
tracks, stations and the live map"). In detail:

* the map's geometry (projection, date line, visibility circle,
  terminator) against independent formulas;
* the map painted by its worker, in step with the playback, quick to
  draw on the GUI thread;
* Globe, Map or Both, remembered, with keys and View menu commands;
* the globe's ground track on by default (solid flown, dashed to come),
  each station's glyph and visibility ring, kept over a WebGL context
  loss;
* a live run drained once (``gui.live_scene.LiveScene``), extended off
  the GUI thread, drawn by the globe and the map;
* the map in its own window (``gui.breakout``, view "map")."""

import json
import math
import threading
import time
import warnings
from pathlib import Path

import numpy as np
import pytest

pytestmark = pytest.mark.requires_gui

_RADIUS_M = 7000e3  # [m]
_EARTH_KM = 6378.137  # [km] for the geometry tests only
_GUI_THREAD_MS = 50.0  # [ms] CLAUDE.md "Never freeze"


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    """A home of its own (the views' settings) and no real autosave."""
    from spacemissionstudio.gui import autosave

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setattr(autosave, "_AUTOSAVE_DIR", tmp_path / "autosave")
    monkeypatch.setattr(autosave, "_RECOVERY_FILE", tmp_path / "autosave" / "recovery.json")


def _run(stations: bool = True, inclination_deg: float = 0.0):
    """Template 01, one invented orbit (as tests/gui/test_mission_view.py),
    and with ``stations`` one ground station at 0 deg, 0 deg."""
    from spacemissionstudio import api
    from spacemissionstudio.engine.results import ResultSet, TimeSeries
    from spacemissionstudio.schema.scenario import GroundStationConfig

    scenario = api.load(api.template("01_two_body_circular_orbit"))
    if stations:
        scenario.ground_stations = [GroundStationConfig(name="equator-gs", latitude_deg=0.0, longitude_deg=0.0)]
    name = scenario.spacecraft[0].name
    t = np.linspace(0.0, 5800.0, 300)
    angle = 2.0 * math.pi * t / 5800.0
    inclination = math.radians(inclination_deg)
    result = ResultSet(scenario_name=scenario.name)
    result.add(TimeSeries(f"{name}.position_N", t, ("x", "y", "z"),
                          np.column_stack([_RADIUS_M * np.cos(angle), _RADIUS_M * np.sin(angle) * math.cos(inclination),
                                           _RADIUS_M * np.sin(angle) * math.sin(inclination)]), units="m"))
    return scenario, result


def _js(qtbot, view, script):
    out = []
    view.web_view.page().runJavaScript(script, 0, out.append)
    qtbot.waitUntil(lambda: bool(out), timeout=20000)
    return out[0]


def _state(qtbot, view):
    return json.loads(_js(qtbot, view, "JSON.stringify(MV.state())"))


def _view(qtbot, layout: str = "both"):
    from spacemissionstudio.gui.mission_view_widget import MissionViewWidget
    from spacemissionstudio.gui.time_cursor import TimeCursor

    view = MissionViewWidget()
    qtbot.addWidget(view)
    view.set_time_cursor(TimeCursor())
    view.resize(1400, 600)  # [px]
    view.set_layout(layout)
    view.show()
    qtbot.waitExposed(view)
    return view


def _drawn(qtbot, view) -> None:
    qtbot.waitUntil(lambda: view.scene is not None and view._page_ready, timeout=60000)
    qtbot.waitUntil(lambda: _js(qtbot, view, "MV.ready === true && MV.style !== null") is True, timeout=60000)
    qtbot.waitUntil(lambda: _js(qtbot, view, "MV.dirty") is False, timeout=10000)


def _mapped(qtbot, view) -> None:
    qtbot.waitUntil(lambda: view.ground_map.image() is not None and view.ground_map.is_up_to_date(), timeout=20000)


# -- the geometry ------------------------------------------------------------------------------------------

def test_the_projection_is_equirectangular_two_to_one():
    """Longitude -180 deg at the left edge, latitude 90 deg at the top, 2 : 1; and back."""
    from spacemissionstudio.gui.ground_map_widget import from_pixels, to_pixels

    x, y = to_pixels([90.0, -90.0, 0.0, 45.0], [-180.0, 180.0, 0.0, 90.0], 2000.0, 1000.0)
    np.testing.assert_allclose(x, [0.0, 2000.0, 1000.0, 1500.0])
    np.testing.assert_allclose(y, [0.0, 1000.0, 500.0, 250.0])
    lat, lon = from_pixels(x, y, 2000.0, 1000.0)
    np.testing.assert_allclose(lat, [90.0, -90.0, 0.0, 45.0])
    np.testing.assert_allclose(lon, [-180.0, 180.0, 0.0, 90.0])


def test_a_track_is_cut_at_the_date_line_at_the_latitude_it_crosses():
    """Eastward and westward crossings end on one edge and go on from the other, at the crossing's latitude."""
    from spacemissionstudio.gui.ground_map_widget import wrap_segments

    east = wrap_segments([0.0, 1.0, 2.0, 3.0], [170.0, 179.0, -179.0, -170.0])
    assert len(east) == 2
    np.testing.assert_allclose(east[0][-1], [1.5, 180.0])  # half way between 179 and 181
    np.testing.assert_allclose(east[1][0], [1.5, -180.0])
    np.testing.assert_allclose(east[1][-1], [3.0, -170.0])
    west = wrap_segments([10.0, 12.0], [-178.0, 178.0])
    assert len(west) == 2
    np.testing.assert_allclose(west[0][-1], [11.0, -180.0])
    np.testing.assert_allclose(west[1][0], [11.0, 180.0])
    (whole,) = wrap_segments([0.0, 10.0, 20.0], [-10.0, 0.0, 10.0])
    assert whole.shape == (3, 2)
    assert wrap_segments([], []) == []


@pytest.mark.parametrize("altitude_km, elevation_deg", [(400.0, 0.0), (622.0, 10.0), (800.0, 5.0),
                                                         (20200.0, 10.0), (35786.0, 5.0)])
def test_the_visibility_angle_is_wertz_and_larson_s(altitude_km, elevation_deg):
    """lambda = acos(R/(R+h) cos eps) - eps against SMAD's other form
    (section 5.2): sin rho = R/(R+h), sin eta = sin rho cos eps,
    lambda = 90 deg - eps - eta."""
    from spacemissionstudio.gui.ground_map_widget import visibility_angle_deg

    rho = math.asin(_EARTH_KM / (_EARTH_KM + altitude_km))
    eta = math.asin(math.sin(rho) * math.cos(math.radians(elevation_deg)))
    expected = 90.0 - elevation_deg - math.degrees(eta)  # [deg]
    assert visibility_angle_deg(altitude_km, elevation_deg, _EARTH_KM) == pytest.approx(expected, abs=1e-9)


def test_no_visibility_circle_without_an_altitude():
    """No altitude, or none above the surface: no circle."""
    from spacemissionstudio.gui.ground_map_widget import visibility_angle_deg

    assert visibility_angle_deg(None, 10.0, _EARTH_KM) == 0.0
    assert visibility_angle_deg(0.0, 10.0, _EARTH_KM) == 0.0
    assert visibility_angle_deg(-5.0, 0.0, _EARTH_KM) == 0.0


def _central_angle_deg(lat1, lon1, lat2, lon2):
    """Haversine central angle [deg] (independent of small_circle's formula)."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dl = np.radians(np.asarray(lon2) - lon1)
    h = np.sin((p2 - p1) / 2.0) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2.0) ** 2
    return np.degrees(2.0 * np.arcsin(np.sqrt(h)))


@pytest.mark.parametrize("lat, lon, angle", [(0.0, 0.0, 20.0), (67.9, 21.1, 25.0), (-35.4, 149.0, 12.0),
                                             (10.0, 175.0, 30.0)])
def test_every_point_of_a_visibility_circle_is_the_angle_away(lat, lon, angle):
    """Each point's haversine distance from the station is the circle's angle, also over the date line."""
    from spacemissionstudio.gui.ground_map_widget import small_circle

    lats, lons = small_circle(lat, lon, angle)
    np.testing.assert_allclose(_central_angle_deg(lat, lon, lats, lons), angle, atol=1e-6)
    assert np.all(lons >= -180.0) and np.all(lons < 180.0)


@pytest.mark.parametrize("sun_lat, sun_lon", [(23.4, 0.0), (-23.4, 120.0), (5.0, -75.0), (0.0, 30.0)])
def test_the_night_side_is_bounded_by_the_terminator(sun_lat, sun_lon):
    """Each terminator point is 90 deg from the subsolar point; the closing
    pole is on the night side."""
    from spacemissionstudio.gui.ground_map_widget import night_polygon

    polygon = night_polygon(sun_lat, sun_lon)
    edge, poles = polygon[:-2], polygon[-2:]
    np.testing.assert_allclose(_central_angle_deg(sun_lat, sun_lon, edge[:, 0], edge[:, 1]), 90.0, atol=0.01)
    assert edge[0, 1] == -180.0 and edge[-1, 1] == 180.0
    assert np.all(_central_angle_deg(sun_lat, sun_lon, poles[:, 0], poles[:, 1]) >= 90.0 - 1e-6)


def test_the_track_is_split_at_the_time_shown():
    """Track points flown at a time: all of them while following a live run or without times."""
    from types import SimpleNamespace

    from spacemissionstudio.gui.ground_map_widget import _track_split

    craft = SimpleNamespace(path_times_s=np.array([0.0, 10.0, 20.0, 30.0]))
    assert _track_split(craft, 4, None) == 4  # following a live run: all flown
    assert _track_split(craft, 4, 0.0) == 1
    assert _track_split(craft, 4, 15.0) == 2
    assert _track_split(craft, 4, 30.0) == 4
    assert _track_split(SimpleNamespace(path_times_s=None), 4, 15.0) == 4


def test_the_map_style_comes_from_the_theme():
    """Spacecraft colours from the categorical palette, panels and text from the tokens, depicted colours from the palettes."""
    from spacemissionstudio.gui.theme.ground_map_style import ground_map_style
    from spacemissionstudio.gui.theme.palettes import (LINE_OF_SIGHT_COLOUR, STATION_COLOUR, STATION_OUTLINE_COLOUR,
                                                       categorical)
    from spacemissionstudio.gui.theme.tokens import tokens

    for mode in ("light", "dark"):
        style = ground_map_style(mode)
        assert style["crafts"] == categorical(mode) and style["panel"] == tokens(mode)["bg.raised"]
        assert style["text"] == tokens(mode)["text.primary"]
        assert (style["station"], style["station_outline"], style["link"]) == (
            STATION_COLOUR, STATION_OUTLINE_COLOUR, LINE_OF_SIGHT_COLOUR)
        assert style["glyph_px"] == 14


# -- the map in the 3D View ----------------------------------------------------------------------------------

def test_without_a_run_the_map_shows_an_empty_state(qtbot):
    """An EmptyState says what to do; the map alone makes no web view."""
    from spacemissionstudio.gui.budgets_area import EmptyState

    view = _view(qtbot, "map")
    assert isinstance(view.ground_map.stack.currentWidget(), EmptyState)
    assert view.ground_map.empty.title_label.text() == "No ground track yet"
    assert "Run a scenario" in view.ground_map.empty.text_label.text()
    assert view.web_view is None  # the map alone makes no web view


def test_globe_map_or_both_by_the_control_and_the_keys_and_remembered(qtbot):
    """The segmented control and G, M, B switch the layout; the globe's own controls hide with it; the choice is kept."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from spacemissionstudio.gui.mission_view_widget import LAYOUTS, MissionViewWidget

    view = _view(qtbot, "globe")
    assert [b.text() for b in view.layout_buttons.values()] == [text for _key, text, _keys in LAYOUTS]
    for key, _text, keys in LAYOUTS:
        assert f"({keys})" in view.layout_buttons[key].toolTip() and view.layout_buttons[key].accessibleName()
    assert view.stack.isVisible() and not view.map_slot.isVisible()
    view.layout_buttons["map"].click()
    assert view.layout_mode() == "map" and view.map_slot.isVisible() and not view.stack.isVisible()
    assert not view.view_combo.isVisible() and not view.show_button.isVisible()  # the globe's own controls
    view.slider.setFocus()
    with warnings.catch_warnings():  # Qt's own active window, which the shortcut map checks (as test_breakout.py)
        warnings.simplefilter("ignore", DeprecationWarning)
        QApplication.setActiveWindow(view)
    qtbot.keyClick(view.slider, Qt.Key.Key_B)
    assert view.layout_mode() == "both" and view.map_slot.isVisible() and view.stack.isVisible()
    assert view.layout_buttons["both"].isChecked()
    qtbot.keyClick(view.slider, Qt.Key.Key_G)
    assert view.layout_mode() == "globe" and not view.map_slot.isVisible()
    view.set_layout("both")
    again = MissionViewWidget()
    qtbot.addWidget(again)
    assert again.layout_mode() == "both"


def test_the_map_is_painted_in_a_worker_and_follows_the_playback(qtbot, monkeypatch):
    """The worker paints the image (not the GUI thread), at the map's
    size in device pixels, 2 : 1; the frame shown is the globe's."""
    from spacemissionstudio.gui import ground_map_widget

    threads = []
    paint = ground_map_widget.render_map

    def recording(request, cache):
        threads.append(threading.get_ident())
        return paint(request, cache)

    monkeypatch.setattr(ground_map_widget, "render_map", recording)
    view = _view(qtbot)
    view.set_run(*_run())
    _drawn(qtbot, view)
    _mapped(qtbot, view)
    gmap = view.ground_map
    assert gmap.scene is view.scene and gmap.stack.currentWidget() is gmap.canvas
    assert threads and threading.get_ident() not in threads
    image, rect = gmap.image(), gmap.map_rect()
    ratio = gmap.canvas.devicePixelRatioF()
    assert image.width() == round(rect.width() * ratio) and image.height() == image.width() // 2
    view.show_frame(150)
    assert gmap.frame == 150
    qtbot.waitUntil(gmap.is_up_to_date, timeout=10000)
    view.toggle_play()
    qtbot.waitUntil(lambda: gmap.frame > 150, timeout=10000)
    view.pause()
    assert gmap.frame == view.slider.value()


def test_the_map_s_own_paint_is_quick(qtbot):
    """What the GUI thread draws (the worker's image, markers, circles,
    labels, legend) takes a few ms."""
    from PySide6.QtGui import QImage, QPainter

    view = _view(qtbot, "map")
    view.set_run(*_run())
    qtbot.waitUntil(lambda: view.scene is not None, timeout=30000)
    _mapped(qtbot, view)
    gmap = view.ground_map
    target = QImage(gmap.canvas.size(), QImage.Format.Format_ARGB32_Premultiplied)
    took = []
    for frame in range(0, 300, 15):
        gmap.frame = frame
        painter = QPainter(target)
        start = time.perf_counter()
        gmap.paint_map(painter)
        took.append(1000.0 * (time.perf_counter() - start))
        painter.end()
    assert float(np.median(took)) < 10.0 and max(took) < _GUI_THREAD_MS, took


def test_the_map_s_show_menu_is_remembered_and_repaints(qtbot):
    """Each Show item repaints the map in the worker and is kept for the next map."""
    from spacemissionstudio.gui.ground_map_widget import TOGGLES, GroundMapWidget

    view = _view(qtbot, "map")
    view.set_run(*_run())
    qtbot.waitUntil(lambda: view.scene is not None, timeout=30000)
    _mapped(qtbot, view)
    gmap = view.ground_map
    assert [a.text() for a in gmap.toggle_actions.values()] == [text for _key, text in TOGGLES]
    assert gmap.shows() == {key for key, _text in TOGGLES}  # everything on at first
    before = gmap.image()
    gmap.toggle_actions["tracks"].setChecked(False)
    qtbot.waitUntil(lambda: gmap.is_up_to_date() and gmap.image() is not before, timeout=10000)
    assert gmap.image() != before
    again = GroundMapWidget()
    qtbot.addWidget(again)
    assert not again.toggle_actions["tracks"].isChecked() and again.toggle_actions["stations"].isChecked()


def test_the_map_says_its_latitude_is_geocentric_and_credits_the_image(qtbot):
    """The geocentric-latitude note with the 0.19 deg bound, and NASA's credit in the tooltip."""
    view = _view(qtbot, "map")
    gmap = view.ground_map
    assert "geocentric latitude" in gmap.note_label.text()
    assert "0.19" in gmap.note_label.toolTip()
    assert "NASA" in gmap.canvas.toolTip() and gmap.canvas.accessibleName() == "Ground track map"


# -- the globe: the ground track and the stations -------------------------------------------------------------

def test_the_ground_track_is_on_by_default_flown_solid_and_to_come_dashed(qtbot):
    """On by default (Q1): solid up to the frame shown, dashed after it; the split moves with the frame."""
    view = _view(qtbot, "globe")
    assert view.toggle_actions["groundTrack"].isChecked()
    view.set_run(*_run(inclination_deg=50.0))
    _drawn(qtbot, view)
    view.show_frame(100)
    qtbot.waitUntil(lambda: _js(qtbot, view, "MV.frame") == 100, timeout=10000)
    qtbot.waitUntil(lambda: _js(qtbot, view, "MV.dirty") is False, timeout=10000)
    craft = _state(qtbot, view)["crafts"][0]
    assert craft["track"] is True and craft["trackFuture"] is True and craft["trackDashed"] is True
    flown, to_come = craft["trackSplit"]
    assert flown > 0 and to_come > 0
    view.show_frame(250)
    qtbot.waitUntil(lambda: _state(qtbot, view)["crafts"][0]["trackSplit"][0] > flown, timeout=10000)
    view.toggle_actions["groundTrack"].setChecked(False)
    qtbot.waitUntil(lambda: _state(qtbot, view)["crafts"][0]["track"] is False, timeout=10000)
    assert _state(qtbot, view)["crafts"][0]["trackFuture"] is False


def test_a_station_has_a_glyph_and_a_visibility_ring_stronger_in_contact(qtbot):
    """The station's glyph is 14 px at any zoom, outlined; its ring's
    radius is the visibility angle at the spacecraft's altitude; in
    contact, glyph and ring take the line-of-sight colour."""
    from spacemissionstudio.gui.ground_map_widget import visibility_angle_deg
    from spacemissionstudio.gui.theme.mission_view_style import mission_view_style
    from spacemissionstudio.gui.theme.palettes import LINE_OF_SIGHT_COLOUR, STATION_COLOUR

    view = _view(qtbot, "globe")
    view.set_run(*_run())
    _drawn(qtbot, view)
    scene = view.scene
    visible = scene.station_visible[0, 0]
    style = mission_view_style("light")
    for frame in (int(np.argmax(visible)), int(np.argmin(visible))):
        view.show_frame(frame)
        qtbot.waitUntil(lambda frame=frame: _js(qtbot, view, "MV.frame") == frame, timeout=10000)
        _js(qtbot, view, "const s = MV.stationWorld(0); MV.camera.position.set(3 * s[0], 3 * s[1], 3 * s[2]); "
                         "MV.camera.lookAt(0, 0, 0); MV.dirty = true; 1")  # the station on the near side
        qtbot.waitUntil(lambda: _js(qtbot, view, "MV.dirty") is False, timeout=10000)
        state = _state(qtbot, view)
        (station,) = state["stations"]
        assert station["name"] == "equator-gs" and station["glyph"] is True
        assert station["size"] == [14, 14]
        (ring,) = state["rings"]
        expected = visibility_angle_deg(float(scene.crafts[0].altitude_km[frame]),
                                        scene.station_min_elevation_deg[0], scene.body_radius_km)
        assert ring["visible"] is True and ring["lambda"] == pytest.approx(expected, abs=0.02)
        contact = bool(visible[frame])
        assert station["contact"] is contact
        assert ring["colour"].upper() == (LINE_OF_SIGHT_COLOUR if contact else STATION_COLOUR)
        assert ring["opacity"] == (style["ring_contact_opacity"] if contact else style["ring_opacity"])
    view.toggle_actions["stations"].setChecked(False)
    qtbot.waitUntil(lambda: _state(qtbot, view)["rings"][0]["visible"] is False, timeout=10000)
    assert _state(qtbot, view)["stations"][0]["glyph"] is False


def test_tracks_and_rings_survive_a_lost_webgl_context(qtbot):
    """MV.recover makes a new renderer for the same scene: the track lines
    and the station rings are the same objects, still drawn."""
    view = _view(qtbot, "globe")
    view.set_run(*_run())
    _drawn(qtbot, view)
    _js(qtbot, view, "window.KEEP = [MV.crafts[0].track, MV.crafts[0].trackFuture, MV.rings[0].line]; "
                     "window.LOSE = MV.renderer.getContext().getExtension('WEBGL_lose_context'); "
                     "LOSE.loseContext(); 1")
    qtbot.waitUntil(lambda: _js(qtbot, view, "MV.contextLost") is True, timeout=10000)
    _js(qtbot, view, "LOSE.restoreContext(); 1")
    qtbot.waitUntil(lambda: _js(qtbot, view, "MV.recoveries") == 1, timeout=10000)
    assert _js(qtbot, view, "MV.crafts[0].track === KEEP[0] && MV.crafts[0].trackFuture === KEEP[1] "
                            "&& MV.rings[0].line === KEEP[2] && MV.earthGroup.children.includes(KEEP[2])") is True
    view.show_frame(10)
    qtbot.waitUntil(lambda: _state(qtbot, view)["frame"] == 10, timeout=10000)
    state = _state(qtbot, view)
    assert state["crafts"][0]["track"] is True and state["rings"][0]["visible"] is True


# -- a live run ------------------------------------------------------------------------------------------------

def _feed_samples(feed, start: int, stop: int, period_s: float = 5800.0, step_s: float = 20.0) -> None:
    for n in range(start, stop):
        t = n * step_s  # [s]
        angle = 2.0 * math.pi * t / period_s  # [rad]
        speed = 2.0 * math.pi * _RADIUS_M / period_s  # [m/s]
        feed.push(t, [(_RADIUS_M * math.cos(angle), _RADIUS_M * math.sin(angle), 0.0)],
                  [(-speed * math.sin(angle), speed * math.cos(angle), 0.0)], [(0.0, 0.0, math.tan(angle / 4.0))])


def _live(qtbot, layout: str = "both"):
    from spacemissionstudio import api
    from spacemissionstudio.engine.live_view import LiveFeed
    from spacemissionstudio.schema.scenario import GroundStationConfig

    scenario = api.load(api.template("01_two_body_circular_orbit"))
    scenario.ground_stations = [GroundStationConfig(name="equator-gs", latitude_deg=0.0, longitude_deg=0.0)]
    feed = LiveFeed(duration_s=5800.0)
    feed.start([scenario.spacecraft[0].name], [True], _RADIUS_M)
    feed.interval_used_s = 20.0  # [s]
    view = _view(qtbot, layout)
    view.start_live(scenario, feed)
    assert view.ground_map.empty.title_label.text() == "Waiting for the run's first state..."
    return view, feed


def test_a_live_run_is_drained_once_extended_off_the_gui_thread_and_drawn_twice(qtbot, monkeypatch):
    """LiveScene is the feed's one consumer; extend_scene runs in its
    worker; the globe's page and the map get the same frames."""
    from spacemissionstudio.engine import scene3d

    threads = []
    extend = scene3d.extend_scene

    def recording(*args, **kwargs):
        threads.append(threading.get_ident())
        return extend(*args, **kwargs)

    monkeypatch.setattr(scene3d, "extend_scene", recording)
    view, feed = _live(qtbot)
    _feed_samples(feed, 0, 30)
    _drawn(qtbot, view)
    _feed_samples(feed, 30, 150)
    qtbot.waitUntil(lambda: _state(qtbot, view)["frames"] == 150, timeout=20000)
    assert not feed.pending()  # all of it drained, by the one consumer
    assert threads and threading.get_ident() not in threads
    gmap = view.ground_map
    assert gmap.scene is view.scene and view.live_scene.scene is view.scene
    assert len(view.scene.crafts[0].ground_track_deg) == 150 and len(view.scene.crafts[0].path_times_s) == 150
    assert gmap.frame == 149 and gmap.live and gmap.following and gmap.live_label.isVisibleTo(gmap)
    _mapped(qtbot, view)
    np.testing.assert_allclose(json.loads(_js(qtbot, view, "JSON.stringify(MV.data.crafts[0].tt)")),
                               np.arange(150) * 20.0)
    view.slider.setValue(20)  # scrubbed back: the map follows, without LIVE
    assert gmap.frame == 20 and not gmap.following and not gmap.live_label.isVisibleTo(gmap)
    view.go_live()
    assert gmap.frame == 149 and gmap.following


def test_a_live_run_shown_on_the_map_only_needs_no_web_view(qtbot):
    """A live run on the map alone makes no web view; the globe shown later gets the frames so far."""
    view, feed = _live(qtbot, "map")
    _feed_samples(feed, 0, 60)
    qtbot.waitUntil(lambda: view.scene is not None and len(view.scene.times_s) == 60, timeout=20000)
    _mapped(qtbot, view)
    assert view.web_view is None and view.ground_map.frame == 59
    view.set_layout("globe")  # the globe made now, with the frames so far
    _drawn(qtbot, view)
    qtbot.waitUntil(lambda: _state(qtbot, view)["frames"] == 60, timeout=20000)


def test_the_live_scene_extends_a_copy_and_leaves_the_shown_scene_whole():
    """live_frames on a snapshot leaves the scene the GUI thread holds as it was."""
    from spacemissionstudio import api
    from spacemissionstudio.engine import scene3d
    from spacemissionstudio.engine.live_view import LiveFeed
    from spacemissionstudio.gui.live_scene import live_batch, snapshot
    from spacemissionstudio.gui.mission_view_widget import live_frames, live_scene

    scenario = api.load(api.template("01_two_body_circular_orbit"))
    feed = LiveFeed(duration_s=5800.0)
    feed.start([scenario.spacecraft[0].name], [True], _RADIUS_M)
    feed.interval_used_s = 20.0  # [s]
    _feed_samples(feed, 0, 10)
    scene = live_scene(scenario, feed, feed.drain(live_batch(feed)))
    _feed_samples(feed, 10, 25)
    grown = live_frames(snapshot(scene), feed, feed.drain(live_batch(feed)))
    assert len(scene.times_s) == 10 and len(scene.crafts[0].path_km) == 10
    assert len(scene.crafts[0].ground_track_deg) == 10 and scene.station_visible.shape[-1] == 10
    assert len(grown.times_s) == 25 and len(grown.crafts[0].ground_track_deg) == 25
    np.testing.assert_allclose(grown.crafts[0].path_times_s, np.arange(25) * 20.0)
    assert isinstance(grown, scene3d.Scene) and grown is not scene


# -- the map in its own window ------------------------------------------------------------------------------------

@pytest.fixture
def window(qtbot, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    w = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(w)
    w.resize(1280, 720)  # [px]
    w.show()
    qtbot.waitExposed(w)
    w.on_new()
    return w


def test_the_view_menu_and_the_palette_switch_globe_map_and_both(window):
    """View > 3D View and the palette have Show Globe, Show Map and Show Globe and Map."""
    view = window.mission_view_widget
    menu = window.menus["3D View"]
    assert menu.menuAction() in window.menus["View"].actions()
    assert [a.text() for a in menu.actions()] == ["Show Globe", "Show Map", "Show Globe and Map"]
    labels = {entry.label for entry in window.palette_entries()}
    assert {"3D View > Show Globe", "3D View > Show Map", "3D View > Show Globe and Map"} <= labels
    window.commands.action("view.3d_view.map").trigger()
    assert view.layout_mode() == "map" and window.shell.current_area() == "results"
    window.commands.action("view.3d_view.both").trigger()
    assert view.layout_mode() == "both"


def test_the_map_opens_in_its_own_window_and_comes_back_beside_the_globe(window, qtbot):
    """The map in its own window has Play and the time, follows the playback, and comes back beside the globe."""
    from spacemissionstudio.gui.breakout import BreakoutButton

    view, gmap = window.mission_view_widget, window.mission_view_widget.ground_map
    view.set_layout("globe")
    view.set_run(*_run())
    window.show_view(view)
    qtbot.waitUntil(lambda: view.scene is not None, timeout=30000)
    (button,) = [b for b in gmap.findChildren(BreakoutButton) if b.view_id == "map"]
    assert button.accessibleName() == "Open in Own Window: Map"
    window.breakouts.detach("map")
    assert gmap.isWindow() and gmap.isVisible() and window.breakouts.is_detached("map")
    assert gmap.play_button.isVisibleTo(gmap) and gmap.time_label.isVisibleTo(gmap)  # its own playback
    assert gmap.time_label.text() == view.time_label.text()
    _mapped(qtbot, view)
    view.show_frame(42)
    assert gmap.frame == 42
    gmap.play_button.click()
    assert view.is_playing()
    view.pause()
    window.breakouts.attach("map")
    assert not gmap.isWindow() and view.map_slot.isAncestorOf(gmap)
    assert view.layout_mode() == "both" and gmap.isVisible()  # brought back where it can be seen
    assert not gmap.play_button.isVisibleTo(gmap)
