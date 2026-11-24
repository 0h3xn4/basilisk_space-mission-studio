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
"""Results › 3D View's 2D map: the ground tracks, the ground stations and
where each spacecraft is, on a flat map of the Earth, live while a run
runs and in step with the playback and the time cursor after it (2.12.0,
``docs/developer/windows-views-design.md`` section 3, decision "Ground
tracks, stations and the live map").

* **Projection:** equirectangular, 2 : 1, longitude -180 to 180 degrees
  left to right, latitude 90 to -90 degrees top to bottom
  (:func:`to_pixels`): ``x = (lon + 180) / 360 W``, ``y = (90 - lat) / 180
  H``. The latitude is geocentric, as the 3D View's ground track
  (``engine.scene3d.ground_track_deg``); it differs from the geodetic
  latitude by at most about 0.19 degrees. The map says so.
* **Image:** NASA's Blue Marble (``gui/assets/mission_view/``, the 3D
  View's own, public domain; the credit is in the map's tooltip), the 2k
  image, or the 4k image on a map wider than 2048 device pixels.
* **Ground tracks:** each spacecraft's, in its categorical colour, as on
  the globe: solid where it has flown, dashed where it is still to fly. A
  track that crosses the date line is cut there, at the latitude where it
  crosses (:func:`wrap_segments`).
* **Ground stations:** the globe's glyph (a triangle on a mast), the
  name, a line to each spacecraft in view (``scene.station_visible``), and
  the visibility circle of each spacecraft at its altitude now: the
  footprint of the station's elevation mask, Earth central angle
  ``lambda = acos(R / (R + h) cos eps) - eps`` (Wertz and Larson, *Space
  Mission Analysis and Design*, 3rd ed., section 5.2;
  :func:`visibility_angle_deg`), in the line-of-sight colour while that
  spacecraft is in view.
* **Day and night:** the night side shaded, from the Sun's direction at
  the time shown (:func:`night_polygon`).

**Off the GUI thread.** :class:`MapRenderer` paints the image, the grid,
the night side and the tracks into a ``QImage`` in one serial worker
(:func:`render_map`); a live run adds only the new segments to a layer
the worker keeps, and so does playback going forward. The worker draws a
long line in pieces of :data:`POLYLINE_POINTS` points: each Qt call holds
the interpreter lock, and short calls leave it free for the window
(measured: about 1.5 ms a call). The GUI thread draws that image and, on
top, the markers, the circles, the labels and the legend (a few ms).
A resize waits :data:`RESIZE_DEBOUNCE_MS` before the worker paints again;
a theme change repaints. A hidden map does no work and catches up when
shown.

The map takes its data from :class:`gui.mission_view_widget.MissionViewWidget`
(the same scene as the globe, and the same live run through
``gui.live_scene.LiveScene``) and follows its playback. It can open in
its own window (``gui.breakout``, view "map").
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, QPointF, QRectF, QSettings, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QColor, QImage, QKeySequence, QPainter, QPainterPath, QPen, QPolygonF, QShortcut
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMenu, QPushButton, QSizePolicy, QStackedWidget, QToolButton,
                               QVBoxLayout, QWidget)

from ..engine import scene3d
from .background_threads import worker_pool
from .theme import SPACE, current_theme, icon, mono_font, on_change, set_role, ui_font
from .theme.ground_map_style import ground_map_style
from .widgets import EmptyState

ASSETS = Path(__file__).resolve().parent / "assets" / "mission_view"
TEXTURE_2K = ASSETS / "earth_day_2k.jpg"  # 2048 x 1024, -180 to 180 degrees
TEXTURE_4K = ASSETS / "earth_day_4k.jpg"  # 4096 x 2048
_TEXTURE_2K_WIDTH = 2048  # [px] a map wider than this (device pixels) takes the 4k image
RESIZE_DEBOUNCE_MS = 120  # [ms] after the last resize, the worker paints the map at its new size
POLYLINE_POINTS = 256  # [-] points per Qt call when a line is drawn (each call holds the interpreter lock)
_TEXTURE_STRIPS = 16  # [-] the image is scaled in this many strips, one short Qt call each
GRID_STEP_DEG = 30  # [deg] the latitude and longitude lines
_NARROW_PX = 600  # [px] a map narrower than this labels every other meridian
CIRCLE_POINTS = 181  # [-] points of a visibility circle
TERMINATOR_POINTS = 361  # [-] points of the day-night line
LEGEND_ROWS = 8  # [-] spacecraft named in the legend; more are counted
_MIN_SUN_LAT_DEG = 1e-3  # [deg] the Sun's latitude is kept at least this far from 0 (the terminator's tangent)
_SETTINGS_GROUP = "ground_map"
#: What the map's Show menu switches, in its order: key, menu text.
TOGGLES = (("tracks", "Ground tracks"), ("stations", "Ground stations and visibility circles"),
           ("night", "Day and night"), ("grid", "Latitude and longitude grid"), ("labels", "Labels"))
CREDIT = ("Earth image: NASA Blue Marble, NASA Goddard Space Flight Center Scientific Visualization Studio "
          "(public domain; Blue Marble data courtesy of Reto Stöckli, NASA/GSFC).")
PROJECTION_NOTE = "Equirectangular map, geocentric latitude"
# A station's glyph in a 14 x 14 box (as the globe's): a triangle on a mast, on a foot.
_GLYPH_BOX = 14.0  # [-] the box the glyph's coordinates are in
_GLYPH_POLYGONS = (((7.0, 1.0), (12.5, 8.5), (1.5, 8.5)), ((6.0, 8.5), (8.0, 8.5), (8.0, 12.0), (6.0, 12.0)),
                   ((3.5, 12.0), (10.5, 12.0), (10.5, 13.5), (3.5, 13.5)))


def _settings() -> QSettings:
    return QSettings(str(Path.home() / ".spacemissionstudio" / "settings.ini"), QSettings.Format.IniFormat)


def _as_bool(value) -> bool:
    return value is True or str(value).lower() == "true"


# -- the projection and the geometry (plain functions, tested on their own) ------------------------------
def to_pixels(lat_deg, lon_deg, width: float, height: float) -> tuple[np.ndarray, np.ndarray]:
    """``(x, y)`` of geocentric latitude and longitude [deg] on an
    equirectangular map ``width`` x ``height`` (2 : 1): longitude -180 at
    the left edge, latitude 90 at the top."""
    lat = np.asarray(lat_deg, dtype=float)
    lon = np.asarray(lon_deg, dtype=float)
    return (lon + 180.0) / 360.0 * width, (90.0 - lat) / 180.0 * height


def from_pixels(x, y, width: float, height: float) -> tuple[np.ndarray, np.ndarray]:
    """Latitude and longitude [deg] of the point ``(x, y)`` of the map."""
    return 90.0 - np.asarray(y, dtype=float) / height * 180.0, np.asarray(x, dtype=float) / width * 360.0 - 180.0


def wrap_segments(lat_deg, lon_deg) -> list[np.ndarray]:
    """The pieces ``(n, 2)`` (latitude, longitude [deg]) of a path on the
    map: cut where it crosses the date line (two points more than 180
    degrees apart in longitude), each piece ending on the edge, and the
    next starting on the other edge, at the latitude where the path
    crosses (linear between the two points)."""
    lat = np.asarray(lat_deg, dtype=float)
    lon = np.asarray(lon_deg, dtype=float)
    if len(lat) == 0:
        return []
    jumps = np.nonzero(np.abs(np.diff(lon)) > 180.0)[0]
    pieces, start, head = [], 0, None
    for j in jumps:
        east = lon[j + 1] < lon[j]  # 179 -> -179: eastwards over +180
        edge = 180.0 if east else -180.0  # [deg]
        far = lon[j + 1] + (360.0 if east else -360.0)  # [deg] the next point, unwrapped
        span = far - lon[j]
        t = (edge - lon[j]) / span if span else 0.0
        crossing = lat[j] + t * (lat[j + 1] - lat[j])  # [deg]
        piece = np.column_stack([lat[start:j + 1], lon[start:j + 1]])
        if head is not None:
            piece = np.vstack([head, piece])
        pieces.append(np.vstack([piece, [[crossing, edge]]]))
        head = np.array([[crossing, -edge]])
        start = j + 1
    piece = np.column_stack([lat[start:], lon[start:]])
    if head is not None:
        piece = np.vstack([head, piece])
    pieces.append(piece)
    return [piece for piece in pieces if len(piece) >= 2]


def visibility_angle_deg(altitude_km: float | None, min_elevation_deg: float, radius_km: float) -> float:
    """The Earth central angle [deg] from a station to the edge of what it
    sees at or above ``min_elevation_deg``, for a spacecraft at
    ``altitude_km`` above a sphere of ``radius_km``: ``lambda = acos(R / (R
    + h) cos eps) - eps`` (Wertz and Larson, *Space Mission Analysis and
    Design*, 3rd ed., section 5.2). 0 without an altitude above the surface."""
    if altitude_km is None or not altitude_km > 0.0 or not radius_km > 0.0:
        return 0.0
    eps = math.radians(min_elevation_deg)
    angle = math.acos(min(1.0, radius_km / (radius_km + altitude_km) * math.cos(eps))) - eps
    return max(0.0, math.degrees(angle))


def small_circle(lat_deg: float, lon_deg: float, angle_deg: float,
                 points: int = CIRCLE_POINTS) -> tuple[np.ndarray, np.ndarray]:
    """Latitudes and longitudes [deg] of the points ``angle_deg`` from
    ``(lat_deg, lon_deg)`` on a sphere, all round (the first point again at
    the end), longitudes in [-180, 180)."""
    phi0, angle = math.radians(lat_deg), math.radians(angle_deg)
    theta = np.linspace(0.0, 2.0 * math.pi, points)
    lat = np.arcsin(np.clip(math.sin(phi0) * math.cos(angle) + math.cos(phi0) * math.sin(angle) * np.cos(theta),
                            -1.0, 1.0))
    lon = lon_deg + np.degrees(np.arctan2(np.sin(theta) * math.sin(angle) * math.cos(phi0),
                                          math.cos(angle) - math.sin(phi0) * np.sin(lat)))
    return np.degrees(lat), np.mod(lon + 180.0, 360.0) - 180.0


def night_polygon(sun_lat_deg: float, sun_lon_deg: float, points: int = TERMINATOR_POINTS) -> np.ndarray:
    """The night side as a polygon ``(n, 2)`` (latitude, longitude [deg]):
    the terminator, ``lat = atan(-cos(lon - lon_sun) / tan(lat_sun))``, from
    -180 to 180 degrees, closed over the pole in the dark."""
    phi = math.radians(sun_lat_deg)
    if abs(phi) < math.radians(_MIN_SUN_LAT_DEG):
        phi = math.copysign(math.radians(_MIN_SUN_LAT_DEG), phi or 1.0)
    lon = np.linspace(-180.0, 180.0, points)
    lat = np.degrees(np.arctan(-np.cos(np.radians(lon - sun_lon_deg)) / math.tan(phi)))
    pole = -90.0 if phi > 0.0 else 90.0  # [deg] the pole without the Sun
    return np.vstack([np.column_stack([lat, lon]), [[pole, 180.0], [pole, -180.0]]])


def subpoint_deg(position_km: np.ndarray, rotation_rad: float) -> tuple[float, float]:
    """Geocentric latitude and longitude [deg] under ``position_km`` (frame N)."""
    lat, lon = scene3d.ground_track_deg(np.asarray(position_km, dtype=float).reshape(1, 3),
                                        np.array([float(rotation_rad)]))[0]
    return float(lat), float(lon)


def _polygon(xy: np.ndarray) -> QPolygonF:
    """``xy`` (n, 2) as a ``QPolygonF``, copied straight into its memory."""
    xy = np.ascontiguousarray(xy, dtype=np.float64)
    polygon = QPolygonF()
    polygon.resize(len(xy))
    try:
        import shiboken6

        memory = shiboken6.VoidPtr(polygon.data(), len(xy) * 16, True)
        np.frombuffer(memoryview(memory), dtype=np.float64).reshape(-1, 2)[:] = xy
    except Exception:  # noqa: BLE001 -- the plain way, point by point
        polygon = QPolygonF([QPointF(x, y) for x, y in xy.tolist()])
    return polygon


def _draw_path(painter: QPainter, lat, lon, width: float, height: float) -> None:
    """A path on the map, cut at the date line, in short Qt calls."""
    for piece in wrap_segments(lat, lon):
        x, y = to_pixels(piece[:, 0], piece[:, 1], width, height)
        xy = np.column_stack([x, y])
        for start in range(0, len(xy) - 1, POLYLINE_POINTS):
            painter.drawPolyline(_polygon(xy[start:start + POLYLINE_POINTS + 1]))


def _colour(text: str, alpha: float = 1.0) -> QColor:
    colour = QColor(text)
    colour.setAlphaF(alpha)
    return colour


# -- the worker's painting ------------------------------------------------------------------------------
@dataclass(eq=False)
class MapRequest:
    """What the worker paints: the map's size in device pixels, the
    theme's style, the scene (``token``: which scene), the frame shown,
    the time the tracks are split at (None: all flown) and the toggles on."""

    width: int
    height: int
    ratio: float
    style: dict
    scene: object
    token: int
    frame: int
    split_s: float | None
    show: frozenset


def _texture(width: int, cache: dict) -> QImage:
    path = TEXTURE_4K if width > _TEXTURE_2K_WIDTH else TEXTURE_2K
    images = cache.setdefault("textures", {})
    if path not in images:
        image = QImage(str(path))
        images[path] = image.convertToFormat(QImage.Format.Format_RGB32) if not image.isNull() else image
    return images[path]


def _base_image(request: MapRequest, cache: dict) -> QImage:
    """The Earth image at the map's size, with the grid."""
    width, height, style = request.width, request.height, request.style
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(style["night"]))
    texture = _texture(width, cache)
    painter = QPainter(image)
    if not texture.isNull():
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        for k in range(_TEXTURE_STRIPS):  # short calls (each holds the interpreter lock)
            source = QRectF(0.0, texture.height() * k / _TEXTURE_STRIPS, texture.width(),
                            texture.height() / _TEXTURE_STRIPS)
            painter.drawImage(QRectF(0.0, height * k / _TEXTURE_STRIPS, width, height / _TEXTURE_STRIPS), texture,
                              source)
    if "grid" in request.show:
        painter.setPen(QPen(_colour(style["grid"], style["grid_alpha"]), max(1.0, request.ratio)))
        for lat in range(-90 + GRID_STEP_DEG, 90, GRID_STEP_DEG):
            y = (90.0 - lat) / 180.0 * height
            painter.drawLine(QPointF(0.0, y), QPointF(width, y))
        for lon in range(-180 + GRID_STEP_DEG, 180, GRID_STEP_DEG):
            x = (lon + 180.0) / 360.0 * width
            painter.drawLine(QPointF(x, 0.0), QPointF(x, height))
    painter.end()
    return image


def _track_split(craft, count: int, split_s: float | None) -> int:
    """Track points flown at ``split_s`` (all of them with None, or without times)."""
    times = getattr(craft, "path_times_s", None)
    if split_s is None or times is None or len(times) < count:
        return count
    return int(np.searchsorted(np.asarray(times[:count]), split_s, side="right"))


def render_map(request: MapRequest, cache: dict) -> QImage:
    """The map's image for ``request``: the Earth, the grid, the night side
    and the tracks. ``cache`` keeps the scaled image and the tracks already
    drawn between calls (one caller at a time: the worker)."""
    width, height, style, scene = request.width, request.height, request.style, request.scene
    base_key = (width, height, style["mode"], "grid" in request.show)
    if cache.get("base_key") != base_key:
        cache["base"] = _base_image(request, cache)
        cache["base_key"] = base_key
    image = cache["base"].copy()
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    frames = 0 if scene is None else len(scene.times_s)
    frame = min(max(request.frame, 0), frames - 1) if frames else 0
    if frames and "night" in request.show and scene.sun_direction_N is not None and \
            scene.body_rotation_rad is not None:
        sun_lat, sun_lon = subpoint_deg(scene.sun_direction_N[frame], scene.body_rotation_rad[frame])
        night = night_polygon(sun_lat, sun_lon)
        x, y = to_pixels(night[:, 0], night[:, 1], width, height)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_colour(style["night"], style["night_alpha"]))
        painter.drawPolygon(_polygon(np.column_stack([x, y])))
    if scene is not None and "tracks" in request.show:
        _draw_tracks(painter, request, cache)
    painter.end()
    image.setDevicePixelRatio(request.ratio)
    return image


def _draw_tracks(painter: QPainter, request: MapRequest, cache: dict) -> None:
    """Flown (solid) on a layer kept and only added to while the split
    moves forward or the tracks grow; still to come (dashed) on top."""
    width, height, style, scene = request.width, request.height, request.style, request.scene
    colours = style["crafts"]
    tracks = [craft.ground_track_deg for craft in scene.crafts]
    counts = [0 if track is None else len(track) for track in tracks]
    splits = [_track_split(craft, count, request.split_s) for craft, count in zip(scene.crafts, counts)]
    key = (width, height, style["mode"], request.token)
    drawn = cache.get("flown_drawn")
    if cache.get("flown_key") != key or drawn is None or len(drawn) != len(counts) or \
            any(done > split for done, split in zip(drawn, splits)):
        layer = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
        layer.fill(Qt.GlobalColor.transparent)
        cache["flown"], cache["flown_key"], drawn = layer, key, [0] * len(counts)
    layer = cache["flown"]
    pen_width = style["track_px"] * request.ratio
    flown = QPainter(layer)
    flown.setRenderHint(QPainter.RenderHint.Antialiasing)
    for k, track in enumerate(tracks):
        if track is None or splits[k] <= drawn[k]:
            continue
        pen = QPen(QColor(colours[k % len(colours)]), pen_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        flown.setPen(pen)
        first = max(drawn[k] - 1, 0)
        _draw_path(flown, track[first:splits[k], 0], track[first:splits[k], 1], width, height)
        drawn[k] = splits[k]
    flown.end()
    cache["flown_drawn"] = drawn
    painter.drawImage(0, 0, layer)
    for k, track in enumerate(tracks):
        if track is None or splits[k] >= counts[k]:
            continue
        pen = QPen(_colour(colours[k % len(colours)], style["future_alpha"]), pen_width)
        pen.setDashPattern(list(style["dash"]))
        painter.setPen(pen)
        first = max(splits[k] - 1, 0)
        _draw_path(painter, track[first:, 0], track[first:, 1], width, height)


class MapRenderer(QObject):
    """Paints the map in one serial worker. A request made while one is
    being painted waits; a newer one replaces it (the newest wins).
    ``rendered(image, request)`` arrives on the GUI thread."""

    rendered = Signal(object, object)
    _done = Signal(object, object)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._pool = worker_pool(self)
        self._cache: dict = {}  # the worker's own: only one job runs at a time
        self._busy = False
        self._pending: MapRequest | None = None
        self.failures = 0  # [-] requests that raised (the map keeps its last image)
        self._done.connect(self._on_done)

    def request(self, request: MapRequest) -> None:
        if self._busy:
            self._pending = request
            return
        self._start(request)

    def busy(self) -> bool:
        return self._busy or self._pending is not None

    def wait(self) -> None:
        self._pool.waitForDone()

    def _start(self, request: MapRequest) -> None:
        self._busy = True
        self._pool.start(lambda: self._paint(request))

    def _paint(self, request: MapRequest) -> None:
        try:
            image = render_map(request, self._cache)
        except Exception:  # noqa: BLE001 -- the map keeps its last image; the run is not affected
            self._cache.clear()
            image = None
        try:
            self._done.emit(image, request)
        except RuntimeError:  # the map was closed meanwhile
            pass

    def _on_done(self, image, request) -> None:
        self._busy = False
        if image is None:
            self.failures += 1
        else:
            self.rendered.emit(image, request)
        if self._pending is not None:
            request, self._pending = self._pending, None
            self._start(request)


# -- the widget -----------------------------------------------------------------------------------------
class _Canvas(QWidget):
    """Where the map is drawn (by :meth:`GroundMapWidget.paint_map`)."""

    def __init__(self, owner: GroundMapWidget):
        super().__init__(owner)
        self._owner = owner
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(4 * SPACE["xxl"], 2 * SPACE["xxl"])
        self.setAccessibleName("Ground track map")
        self.setToolTip(f"{PROJECTION_NOTE}: solid where a spacecraft has flown, dashed where it is still to "
                        f"fly.\n{CREDIT}")

    def paintEvent(self, _event) -> None:  # noqa: N802 -- Qt's name
        painter = QPainter(self)
        try:
            self._owner.paint_map(painter)
        finally:
            painter.end()

    def resizeEvent(self, event) -> None:  # noqa: N802 -- Qt's name
        super().resizeEvent(event)
        self._owner.resized()


class GroundMapWidget(QWidget):
    """The live 2D map. :meth:`set_scene`, :meth:`extend` and
    :meth:`set_frame` give it the scene and the time shown; ``play_requested``
    and ``live_requested`` ask its owner's playback (Space, End)."""

    play_requested = Signal()
    live_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.scene: scene3d.Scene | None = None
        self.frame = 0
        self.live = False  # a run shown as it is computed
        self.following = False  # ... showing its newest state
        self.map_style = ground_map_style(current_theme())
        self._token = 0  # which scene the worker's layer is of
        self._image: QImage | None = None
        self._dirty = True  # the worker must paint again before the map is up to date
        self._circles: dict = {}  # (station, angle, size) -> pieces of the visibility circle [px]
        self._stations: list[tuple[str, float, float, float]] = []  # name, latitude, longitude [deg], minimum elevation

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE["xs"])
        bar = QHBoxLayout()
        bar.setContentsMargins(SPACE["md"], SPACE["xs"], SPACE["md"], 0)
        bar.setSpacing(SPACE["sm"])
        self.play_button = QPushButton(icon("play"), "Play")
        self.play_button.setToolTip("Play the run (Space)")
        self.play_button.clicked.connect(self.play_requested)
        bar.addWidget(self.play_button)
        self.live_label = set_role(QLabel("LIVE"), badge="critical")
        self.live_label.setToolTip("The map shows the run as it is computed")
        bar.addWidget(self.live_label)
        self.time_label = QLabel()
        self.time_label.setFont(mono_font())
        self.time_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        bar.addWidget(self.time_label)
        self.note_label = set_role(QLabel(PROJECTION_NOTE), tone="secondary")
        self.note_label.setToolTip("Latitudes on this map are geocentric (from the Earth's centre), as on the "
                                   "3D View; geodetic latitude differs by at most about 0.19°.")
        bar.addWidget(self.note_label)
        bar.addStretch(1)
        self.show_button = QToolButton()
        self.show_button.setText("Show")
        self.show_button.setIcon(icon("sliders-horizontal"))
        self.show_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.show_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.show_button.setToolTip("What the map draws")
        self.show_menu = QMenu(self.show_button)
        self.toggle_actions: dict[str, QAction] = {}
        settings = _settings()
        for key, text in TOGGLES:
            action = self.show_menu.addAction(text)
            action.setCheckable(True)
            action.setChecked(_as_bool(settings.value(f"{_SETTINGS_GROUP}/{key}", True)))
            action.toggled.connect(lambda on, key=key: self._on_toggle(key, on))
            self.toggle_actions[key] = action
        self.show_button.setMenu(self.show_menu)
        bar.addWidget(self.show_button)
        self._bar = bar
        layout.addLayout(bar)

        self.stack = QStackedWidget()
        self.empty = EmptyState("No ground track yet",
                                "Run a scenario: each spacecraft's ground track, the ground stations and what "
                                "they see are drawn here, live while the run runs (Show in 3D View while running).")
        self.stack.addWidget(self.empty)
        self.canvas = _Canvas(self)
        self.stack.addWidget(self.canvas)
        layout.addWidget(self.stack, 1)

        for keys, slot in (("Space", self.play_requested.emit), ("End", self.live_requested.emit)):
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(slot)

        self.renderer = MapRenderer(self)
        self.renderer.rendered.connect(self._on_rendered)
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(RESIZE_DEBOUNCE_MS)
        self._resize_timer.timeout.connect(self._request)
        self._set_window_controls()
        on_change(self._on_theme_changed)

    def add_tool_button(self, button: QWidget) -> None:
        """A button of the window's at the end of the map's bar (Open in
        Own Window: it moves with the map, gui.breakout)."""
        self._bar.addWidget(button)

    # -- the data --------------------------------------------------------------------------------------
    def set_scene(self, scene, live: bool = False, following: bool = False) -> None:
        """A new scene (a finished run, or a live run's first frames)."""
        self.scene = scene
        self.live, self.following = bool(live), bool(following)
        self._token += 1
        self._circles.clear()
        self._stations = []
        if scene is not None:
            for (name, point), minimum in zip(scene.stations, scene.station_min_elevation_deg):
                lat, lon = subpoint_deg(point, 0.0)
                self._stations.append((name, lat, lon, float(minimum)))
            self.frame = min(self.frame, len(scene.times_s) - 1) if len(scene.times_s) else 0
            self.stack.setCurrentWidget(self.canvas)
        self._set_window_controls()
        self._changed()

    def extend(self, scene, _start: int = 0, _stop: int = 0) -> None:
        """A live run's scene with new frames (the same run: the worker
        adds the new segments)."""
        self.scene = scene
        self._changed()

    def clear(self, title: str = "No ground track yet", text: str | None = None) -> None:
        self.scene = None
        self.live = self.following = False
        self._token += 1
        self._image = None
        self._stations = []
        self._circles.clear()
        self.empty.set_text(title, text if text is not None else self.empty.text_label.text())
        self.stack.setCurrentWidget(self.empty)
        self.time_label.clear()
        self._set_window_controls()

    def set_frame(self, frame: int, following: bool | None = None) -> None:
        """The frame shown (the owner's playback)."""
        self.frame = int(frame)
        if following is not None:
            self.following = bool(following)
        self._changed()

    def set_live(self, live: bool, following: bool) -> None:
        self.live, self.following = bool(live), bool(following)
        self._set_window_controls()
        self._changed()

    def set_time_text(self, text: str) -> None:
        self.time_label.setText(text)

    def set_playing(self, playing: bool) -> None:
        self.play_button.setText("Pause" if playing else "Play")
        self.play_button.setToolTip("Pause (Space)" if playing else "Play the run (Space)")

    def image(self) -> QImage | None:
        """The worker's newest image of the map (for the tests)."""
        return self._image

    def is_up_to_date(self) -> bool:
        """The worker has painted everything asked for."""
        return not self._dirty and not self.renderer.busy()

    def wait(self) -> None:
        """Until the worker is idle (closing the window)."""
        self._resize_timer.stop()
        self.renderer.wait()

    # -- the worker --------------------------------------------------------------------------------------
    def map_rect(self) -> QRectF:
        """The map's rectangle on the canvas: the largest 2 : 1 one, centred."""
        width, height = float(self.canvas.width()), float(self.canvas.height())
        if width <= 0.0 or height <= 0.0:
            return QRectF()
        if width / 2.0 <= height:
            map_width, map_height = width, width / 2.0
        else:
            map_width, map_height = 2.0 * height, height
        return QRectF((width - map_width) / 2.0, (height - map_height) / 2.0, map_width, map_height)

    def shows(self) -> frozenset:
        return frozenset(key for key, action in self.toggle_actions.items() if action.isChecked())

    def _split_s(self) -> float | None:
        scene = self.scene
        if scene is None or not len(scene.times_s) or (self.live and self.following):
            return None
        return float(scene.times_s[min(self.frame, len(scene.times_s) - 1)])

    def _changed(self) -> None:
        """Something the map draws changed: the worker paints it when the
        map is on screen; the markers are drawn now."""
        self._dirty = True
        if self.canvas.isVisible():
            self._request()
            self.canvas.update()

    def _request(self) -> None:
        rect = self.map_rect()
        if rect.isEmpty() or not self.canvas.isVisible():
            return
        ratio = float(self.canvas.devicePixelRatioF()) or 1.0
        width = max(2, int(round(rect.width() * ratio)))
        self._dirty = False
        self.renderer.request(MapRequest(width=width, height=max(1, width // 2), ratio=ratio, style=self.map_style,
                                         scene=self.scene, token=self._token, frame=self.frame,
                                         split_s=self._split_s(), show=self.shows()))

    def _on_rendered(self, image: QImage, _request) -> None:
        self._image = image
        self.canvas.update()

    def resized(self) -> None:
        self._circles.clear()
        self._resize_timer.start()

    def showEvent(self, event) -> None:  # noqa: N802 -- Qt's name
        super().showEvent(event)
        self._set_window_controls()
        if self._dirty or self._image is None:
            QTimer.singleShot(0, self._request)

    def _set_window_controls(self) -> None:
        """Play and the time only while the map is a window of its own (in
        the 3D View the view's own controls have them); LIVE while it
        shows a run's newest state."""
        alone = self.isWindow()
        self.play_button.setVisible(alone and self.scene is not None)
        self.time_label.setVisible(alone)
        self.live_label.setVisible(self.live and self.following)

    def _on_toggle(self, key: str, on: bool) -> None:
        _settings().setValue(f"{_SETTINGS_GROUP}/{key}", bool(on))
        self._changed()

    def _on_theme_changed(self, mode: str) -> None:
        self.map_style = ground_map_style(mode)
        self._changed()

    # -- the GUI thread's painting: the image, then what moves -------------------------------------------
    def paint_map(self, painter: QPainter) -> None:
        style = self.map_style
        painter.fillRect(self.canvas.rect(), QColor(style["margin"]))
        rect = self.map_rect()
        if rect.isEmpty():
            return
        if self._image is not None:
            painter.drawImage(rect, self._image)
        scene = self.scene
        if scene is None or not len(scene.times_s):
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        frame = min(max(self.frame, 0), len(scene.times_s) - 1)
        crafts = self._crafts_now(scene, frame)
        painter.save()
        painter.setClipRect(rect)
        shows = self.shows()
        if "stations" in shows:
            self._paint_stations(painter, rect, scene, frame, crafts, "labels" in shows)
        self._paint_crafts(painter, rect, crafts)
        painter.restore()
        if "grid" in shows:
            self._paint_grid_labels(painter, rect)
        self._paint_legend(painter, rect, scene)

    def _crafts_now(self, scene, frame: int) -> list[tuple[float, float, float | None]]:
        """Each spacecraft's latitude, longitude [deg] and altitude [km] at ``frame``."""
        found = []
        rotation = 0.0 if scene.body_rotation_rad is None else float(scene.body_rotation_rad[frame])
        for craft in scene.crafts:
            lat, lon = subpoint_deg(craft.position_km[frame], rotation)
            altitude = None if craft.altitude_km is None else float(craft.altitude_km[frame])
            found.append((lat, lon, altitude))
        return found

    def _point(self, rect: QRectF, lat: float, lon: float) -> QPointF:
        x, y = to_pixels(lat, lon, rect.width(), rect.height())
        return QPointF(rect.left() + float(x), rect.top() + float(y))

    def _paint_stations(self, painter: QPainter, rect: QRectF, scene, frame: int, crafts: list,
                        labels: bool) -> None:
        style = self.map_style
        for s, (name, lat, lon, minimum) in enumerate(self._stations):
            seen = [scene.station_visible is not None and bool(scene.station_visible[s, k, frame])
                    for k in range(len(crafts))]
            # The visibility circle at each spacecraft's altitude (one for spacecraft at the same height).
            angles: dict[float, bool] = {}
            for k, (_lat, _lon, altitude) in enumerate(crafts):
                angle = round(visibility_angle_deg(altitude, minimum, scene.body_radius_km), 1)
                if angle > 0.0:
                    angles[angle] = angles.get(angle, False) or seen[k]
            for angle, contact in angles.items():
                colour = _colour(style["link"]) if contact else _colour(style["station"], style["ring_alpha"])
                painter.setPen(QPen(colour, style["ring_px"] * (2 if contact else 1)))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                for piece in self._circle(s, lat, lon, angle, rect):
                    painter.drawPolyline(piece)
            # A line to each spacecraft in view, the short way round.
            origin = self._point(rect, lat, lon)
            painter.setPen(QPen(_colour(style["link"]), style["link_px"]))
            for k, (craft_lat, craft_lon, _altitude) in enumerate(crafts):
                if not seen[k]:
                    continue
                step = (craft_lon - lon + 180.0) % 360.0 - 180.0  # [deg]
                end = self._point(rect, craft_lat, lon + step)
                for shift in (-rect.width(), 0.0, rect.width()):
                    painter.drawLine(origin + QPointF(shift, 0.0), end + QPointF(shift, 0.0))
            self._paint_glyph(painter, origin, any(seen))
            if labels:
                self._paint_chip(painter, name, origin + QPointF(style["glyph_px"] / 2.0 + style["pad_px"],
                                                                 -style["glyph_px"]), style["text"])

    def _circle(self, station: int, lat: float, lon: float, angle: float, rect: QRectF) -> list[QPolygonF]:
        key = (station, angle, rect.width(), rect.height(), rect.left(), rect.top())
        if key not in self._circles:
            lats, lons = small_circle(lat, lon, angle)
            pieces = []
            for piece in wrap_segments(lats, lons):
                x, y = to_pixels(piece[:, 0], piece[:, 1], rect.width(), rect.height())
                pieces.append(_polygon(np.column_stack([x + rect.left(), y + rect.top()])))
            self._circles[key] = pieces
        return self._circles[key]

    def _paint_glyph(self, painter: QPainter, foot: QPointF, contact: bool) -> None:
        """A station's glyph, its foot on the station: as the globe's."""
        style = self.map_style
        scale = style["glyph_px"] / _GLYPH_BOX
        path = QPainterPath()
        for polygon in _GLYPH_POLYGONS:
            path.addPolygon(QPolygonF([QPointF(foot.x() + (x - _GLYPH_BOX / 2.0) * scale,
                                               foot.y() + (y - 13.5) * scale) for x, y in polygon]))
            path.closeSubpath()
        painter.setPen(QPen(QColor(style["station_outline"]), style["border_px"]))
        painter.setBrush(QColor(style["link"] if contact else style["station"]))
        painter.drawPath(path)

    def _paint_crafts(self, painter: QPainter, rect: QRectF, crafts: list) -> None:
        """Each spacecraft where it is: its colour, ringed light and dark,
        readable on land, sea, cloud and night."""
        style = self.map_style
        radius = style["marker_px"] / 2.0
        colours = style["crafts"]
        for k, (lat, lon, _altitude) in enumerate(crafts):
            centre = self._point(rect, lat, lon)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(style["station"]))
            painter.drawEllipse(centre, radius + style["border_px"], radius + style["border_px"])
            painter.setPen(QPen(QColor(style["station_outline"]), style["border_px"]))
            painter.setBrush(QColor(colours[k % len(colours)]))
            painter.drawEllipse(centre, radius - style["border_px"], radius - style["border_px"])

    def _paint_chip(self, painter: QPainter, text: str, top_left: QPointF, ink: str, mono: bool = False) -> QRectF:
        """``text`` in a small raised panel (the theme's), its top left at ``top_left``."""
        style = self.map_style
        font = mono_font("caption") if mono else ui_font("caption", "medium")
        painter.setFont(font)
        metrics = painter.fontMetrics()
        box = QRectF(top_left.x(), top_left.y(), metrics.horizontalAdvance(text) + 2 * style["pad_px"],
                     metrics.height())
        painter.setPen(QPen(QColor(style["panel_border"]), style["border_px"]))
        painter.setBrush(QColor(style["panel"]))
        painter.drawRoundedRect(box, style["radius_px"], style["radius_px"])
        painter.setPen(QColor(ink))
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, text)
        return box

    def _paint_grid_labels(self, painter: QPainter, rect: QRectF) -> None:
        style = self.map_style
        pad = style["pad_px"]
        for lat in range(-90 + GRID_STEP_DEG, 90, GRID_STEP_DEG):
            text = f"{abs(lat)}°{'N' if lat > 0 else 'S' if lat < 0 else ''}"
            y = rect.top() + (90.0 - lat) / 180.0 * rect.height()
            painter.setFont(mono_font("caption"))
            half = painter.fontMetrics().height() / 2.0
            self._paint_chip(painter, text, QPointF(rect.left() + pad, y - half), style["text_secondary"], mono=True)
        step = GRID_STEP_DEG * (2 if rect.width() < _NARROW_PX else 1)
        for lon in range(-180 + step, 180, step):
            text = f"{abs(lon)}°{'E' if lon > 0 else 'W' if lon < 0 else ''}"
            x = rect.left() + (lon + 180.0) / 360.0 * rect.width()
            painter.setFont(mono_font("caption"))
            metrics = painter.fontMetrics()
            width = metrics.horizontalAdvance(text) + 2 * pad
            self._paint_chip(painter, text, QPointF(x - width / 2.0, rect.bottom() - metrics.height() - pad),
                             style["text_secondary"], mono=True)

    def _paint_legend(self, painter: QPainter, rect: QRectF, scene) -> None:
        """Each spacecraft's colour and name; solid flown, dashed still to fly."""
        style = self.map_style
        if not scene.crafts:
            return
        names = [craft.name for craft in scene.crafts[:LEGEND_ROWS]]
        if len(scene.crafts) > LEGEND_ROWS:
            names.append(f"and {len(scene.crafts) - LEGEND_ROWS} more")
        painter.setFont(ui_font("caption", "medium"))
        metrics = painter.fontMetrics()
        pad, gap, sample = style["pad_px"], style["gap_px"], 3 * style["gap_px"]
        row = metrics.height()
        key_rows = 1 if self._split_s() is None else 2
        width = sample + gap + max(metrics.horizontalAdvance(text) for text in names + ["still to fly"]) + 2 * gap
        height = row * (len(names) + key_rows) + 2 * pad
        box = QRectF(rect.right() - width - pad, rect.top() + pad, width, height)  # top right: the grid's labels
        # are on the left and bottom edges
        painter.setPen(QPen(QColor(style["panel_border"]), style["border_px"]))
        painter.setBrush(QColor(style["panel"]))
        painter.drawRoundedRect(box, style["radius_px"], style["radius_px"])
        colours = style["crafts"]
        for k, text in enumerate(names):
            y = box.top() + pad + row * k + row / 2.0
            if k < LEGEND_ROWS:
                painter.setPen(QPen(QColor(colours[k % len(colours)]), style["track_px"] + 1))
                painter.drawLine(QPointF(box.left() + gap, y), QPointF(box.left() + gap + sample, y))
            painter.setPen(QColor(style["text"]))
            painter.drawText(QRectF(box.left() + 2 * gap + sample, y - row / 2.0, width, row),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
        keys = [("flown", Qt.PenStyle.SolidLine)] + ([("still to fly", Qt.PenStyle.DashLine)] if key_rows == 2 else [])
        for j, (text, pen_style) in enumerate(keys):
            y = box.top() + pad + row * (len(names) + j) + row / 2.0
            pen = QPen(QColor(style["text_secondary"]), style["track_px"])
            pen.setStyle(pen_style)
            painter.setPen(pen)
            painter.drawLine(QPointF(box.left() + gap, y), QPointF(box.left() + gap + sample, y))
            painter.setPen(QColor(style["text_secondary"]))
            painter.drawText(QRectF(box.left() + 2 * gap + sample, y - row / 2.0, width, row),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
