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

"""The application icon, drawn in code with :class:`QPainter` rather
than shipped as a bitmap, so there is no binary file to keep in sync
with the palette. ``app.py`` uses it as the window icon;
:func:`write_icon_theme` writes every hicolor size and an SVG for Linux
(``install.sh``, the ``.deb``), :func:`ensure_icon_file` one PNG, and
``packaging/make_ico.py --from-app`` the Windows ``.ico``.

**What it shows.** A mission scene on a dark rounded-square plate, one
element for each thing the tool analyses:

* the real Earth in the lower-left corner: the 3D view's Blue Marble
  texture (NASA) projected onto a lit globe, with Africa, the
  Mediterranean and Europe in view (gravity, the central body, ground
  coverage);
* an orbit around it, solid where the satellite has flown and dashed
  ahead of it (the simulated trajectory and its prediction);
* a satellite on the orbit, gold body and blue solar panels (the
  spacecraft, its pointing and power);
* a beam from the satellite to a ground station on the limb (ground
  passes and the radio link);
* the Sun in the upper-left corner (power, eclipses, solar pressure).

The second design, a satellite alone, showed hardware but not a
mission: no orbit, no Earth, no ground segment. A flat blue disc or
drawn blob continents read as "a blue ball", not the Earth; the texture
makes it recognisable even at 16 px (a green and sand-coloured globe).

**What it must not look like.** The first design, a disc inside a
centred orbit ring with a dot on it, read as a cartoon eye at 16-32 px
(pupil and iris), and tuning stroke widths made it worse. This design
keeps that lesson: the planet sits off-centre and is cut by the plate's
corner, and the orbit is an open arc, so there is no ring around a disc.

**The plate** (2.12.0, ``docs/developer/windows-views-design.md``,
section 5): a rounded square with a light rim. The plate is far from
every light panel, the rim from every dark one (Windows 10 and 11,
Ubuntu's dock and top bar); ``tests/gui/test_icons.py`` measures both.
The plate is flat at the top and deepens towards the bottom.

**Small sizes.** Below 48 px the orbit is one solid arc (dashes blur
into a grey line); below 32 px the Sun's glow and the atmosphere rim are
left out, and the Sun and satellite are drawn larger; below 24 px the
beam is left out. Each threshold was found by rendering 512 down to
16 px on light and dark backgrounds and comparing.

**Colours** are ``theme.palettes.APP_ICON``; the Earth's come from its
texture. The body's gold is the gold foil (multi-layer insulation) of
real satellites.
"""

from __future__ import annotations

import functools
import math
import re
from pathlib import Path

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import (QColor, QGuiApplication, QIcon, QImage, QLinearGradient, QPainter, QPainterPath,
                           QPainterPathStroker, QPen, QPixmap, QRadialGradient)

from .theme.palettes import APP_ICON

_GOLD = APP_ICON["body"]  # satellite body -- see module docstring for why gold, not decorative

ICON_NAME = "spacemissionstudio"

# The hicolor icon theme sizes write_icon_theme writes (px).
ICON_THEME_SIZES = (16, 22, 24, 32, 48, 64, 128, 256, 512)

# The plate, as fractions of the icon's size: the margin around it (none
# below 24 px), the rim's width and the corner radius.
_PLATE_MARGIN = 2 / 64
_RIM_WIDTH = 2 / 64
_PLATE_RADIUS = 12 / 64
_PLATE_FLAT = 0.25  # the plate's flat top, as a fraction of its height

# The scene's design grid: 256 x 256 units; the square _SCENE is mapped
# onto the inside of the plate.
_GRID = 256.0
_SCENE = QRectF(12, 12, 232, 232)
_PLANET_CENTRE = QPointF(60, 272)
_PLANET_RADIUS = 136
# The Earth's surface: the 3D view's Blue Marble texture (NASA, public
# domain; gui/assets/mission_view/NASA_IMAGES.txt), seen from above
# (longitude, latitude) in degrees: Africa, the Mediterranean and Europe
# fill the visible cap.
_EARTH_TEXTURE = Path(__file__).resolve().parent / "assets" / "mission_view" / "earth_day_2k.jpg"
_EARTH_VIEW = (20.0, -20.0)  # [deg]
_EARTH_LAYER_PX = 512  # the layer's resolution: 2x the largest icon
_EARTH_LIGHT = (0.15, 0.9, 0.42)  # direction to the Sun in the view frame (x right, y up, z out) [-]
_EARTH_AMBIENT, _EARTH_GAIN = 0.15, 0.9  # [-]
# The orbit: an ellipse around the planet's centre (semi-axes, tilt in
# degrees), drawn from _ORBIT_START to _ORBIT_END (degrees of its
# parameter); the satellite at _SATELLITE_AT.
_ORBIT_A, _ORBIT_B, _ORBIT_TILT = 212, 186, -8
_ORBIT_START, _ORBIT_END = 110, -40
_SATELLITE_AT = 52
_SUN_CENTRE, _SUN_RADIUS = QPointF(40, 56), 18  # clear of the plate's top edge and the orbit
_SUN_GLOW = 40

# Below these sizes (px) the detail is left out or simplified -- see the
# module docstring.
_FINE_MIN_SIZE = 32  # Sun glow, atmosphere rim, normal Sun and satellite size
_BEAM_MIN_SIZE = 24
_DASH_MIN_SIZE = 48


def _ensure_application() -> None:
    """``QPixmap``/``QPainter`` need a ``QGuiApplication`` instance to
    already exist in the process -- constructing one before it does is a
    silent no-op in Qt (a stderr warning, not a raised exception): the
    resulting pixmap is null and ``.save()`` just returns ``False``, so a
    caller that doesn't check that return value (``app_icon()`` doesn't;
    :func:`ensure_icon_file` does, see below) would appear to succeed
    while producing nothing. Every caller in THIS module runs inside
    ``gui/app.py``'s already-running ``QApplication`` except
    ``packaging/install.sh``'s standalone icon-render step, which imports
    only this module -- so this constructs a minimal, display-less
    ``QGuiApplication`` there rather than trusting every future call site
    to remember to.
    """
    if QGuiApplication.instance() is None:
        QGuiApplication([])


def plate_geometry(size: int) -> tuple[QRectF, float, float]:
    """The plate's outer rectangle, its rim width and its corner radius,
    in pixels, for an icon of ``size`` pixels."""
    margin = 0.0 if size < 24 else round(size * _PLATE_MARGIN)
    rim = max(1.0, size * _RIM_WIDTH)
    outer = QRectF(margin, margin, size - 2 * margin, size - 2 * margin)
    return outer, rim, size * _PLATE_RADIUS


def _orbit_point(degrees: float) -> QPointF:
    """The point of the orbit ellipse at parameter ``degrees``, on the design grid."""
    t = math.radians(degrees)
    x, y = _ORBIT_A * math.cos(t), -_ORBIT_B * math.sin(t)
    c, s = math.cos(math.radians(_ORBIT_TILT)), math.sin(math.radians(_ORBIT_TILT))
    return QPointF(_PLANET_CENTRE.x() + x * c - y * s, _PLANET_CENTRE.y() + x * s + y * c)


def _orbit_arc(start: float, end: float, steps: int = 120) -> QPainterPath:
    """The orbit from parameter ``start`` to ``end`` (degrees) as a polyline."""
    path = QPainterPath(_orbit_point(start))
    for i in range(1, steps + 1):
        path.lineTo(_orbit_point(start + (end - start) * i / steps))
    return path


def _colour(key: str, alpha: int = 255) -> QColor:
    """The ``APP_ICON`` colour ``key`` with opacity ``alpha`` (0-255)."""
    colour = QColor(APP_ICON[key])
    colour.setAlpha(alpha)
    return colour


def _texture_array(path: Path):
    """The image at ``path`` as an ``(height, width, 3)`` uint8 array, or
    ``None`` when it cannot be read."""
    import numpy as np

    image = QImage(str(path))
    if image.isNull():
        return None
    image = image.convertToFormat(QImage.Format.Format_RGB888)
    rows = np.frombuffer(image.constBits(), np.uint8).reshape(image.height(), image.bytesPerLine())
    return rows[:, :image.width() * 3].reshape(image.height(), image.width(), 3).copy()


@functools.lru_cache(maxsize=1)
def _earth_layer() -> QImage | None:
    """The Earth as a lit globe on the whole design grid, at
    ``_EARTH_LAYER_PX``: the bundled Blue Marble texture of the 3D view
    in orthographic projection, centred on ``_EARTH_VIEW`` and lit from
    the Sun's side. Transparent outside the disc. ``None`` when the
    texture is missing; the icon then shows a plain ocean. Made once
    and reused for every size; only the part inside the tile is
    computed."""
    import numpy as np

    texture = _texture_array(_EARTH_TEXTURE)
    if texture is None:
        return None
    res = _EARTH_LAYER_PX
    scale = res / _GRID
    # Only the part of the disc inside the tile is ever seen.
    top = max(0, math.floor((_PLANET_CENTRE.y() - _PLANET_RADIUS) * scale))
    bottom = min(res, math.ceil(_SCENE.bottom() * scale))
    left = max(0, math.floor(_SCENE.left() * scale))
    right = min(res, math.ceil((_PLANET_CENTRE.x() + _PLANET_RADIUS) * scale))
    rows, cols = np.mgrid[top:bottom, left:right].astype(np.float64)
    x = ((cols + 0.5) / scale - _PLANET_CENTRE.x()) / _PLANET_RADIUS
    y = -((rows + 0.5) / scale - _PLANET_CENTRE.y()) / _PLANET_RADIUS
    r2 = x * x + y * y
    z = np.sqrt(np.clip(1.0 - r2, 0.0, 1.0))  # towards the viewer

    # Turn the view frame into the Earth's: tilt by the view's latitude
    # about x, then read the longitude about the polar axis.
    lon0, lat0 = (math.radians(v) for v in _EARTH_VIEW)
    north = y * math.cos(lat0) + z * math.sin(lat0)
    front = -y * math.sin(lat0) + z * math.cos(lat0)
    lat = np.arcsin(np.clip(north, -1.0, 1.0))
    lon = lon0 + np.arctan2(x, front)
    height, width, _ = texture.shape
    u = (((lon / (2 * math.pi) + 0.5) % 1.0) * (width - 1)).astype(np.intp)
    v = ((0.5 - lat / math.pi) * (height - 1)).astype(np.intp)
    rgb = texture[v, u].astype(np.float64)

    # Lambert light from the Sun's side, never fully black.
    sx, sy, sz = _EARTH_LIGHT
    norm = math.sqrt(sx * sx + sy * sy + sz * sz)
    lit = np.clip((x * sx + y * sy + z * sz) / norm, 0.0, 1.0)
    rgb *= (_EARTH_AMBIENT + _EARTH_GAIN * lit ** 0.8)[..., None]

    pixels = np.zeros((res, res, 4), np.uint8)
    region = pixels[top:bottom, left:right]
    region[..., :3] = np.clip(rgb, 0, 255)
    # Anti-aliased edge: alpha falls off over about one layer pixel.
    edge = (1.0 - np.sqrt(r2)) * _PLANET_RADIUS * scale
    region[..., 3] = (np.clip(edge + 0.5, 0.0, 1.0) * 255).astype(np.uint8)
    return QImage(pixels.data, res, res, res * 4, QImage.Format.Format_RGBA8888).copy()


def _fill(painter: QPainter, path: QPainterPath, brush, clip: QPainterPath) -> None:
    """Fills ``path`` cut to ``clip``. The scene cuts its shapes itself,
    rather than with a clip path, because the SVG of
    :func:`render_svg` (``QSvgGenerator``) leaves clip paths out."""
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(brush)
    painter.drawPath(path.intersected(clip))


def _stroke(painter: QPainter, path: QPainterPath, pen: QPen, clip: QPainterPath) -> None:
    """Strokes ``path`` with ``pen`` (dashes included), cut to ``clip``."""
    _fill(painter, QPainterPathStroker(pen).createStroke(path), pen.brush(), clip)


def _ellipse(centre: QPointF, radius: float) -> QPainterPath:
    path = QPainterPath()
    path.addEllipse(centre, radius, radius)
    return path


def _draw_earth(painter: QPainter, device_px: int, unit_px: float, fine: bool, clip: QPainterPath) -> None:
    """The Earth (see :func:`_earth_layer`) on the design grid, drawn at
    ``device_px`` pixels for the grid's 256 units and masked to ``clip``,
    and, at fine sizes, its limb."""
    layer = _earth_layer()
    if layer is not None:
        image = layer.scaled(device_px, device_px, Qt.AspectRatioMode.IgnoreAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
        image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        mask = QPainter(image)
        mask.setRenderHint(QPainter.RenderHint.Antialiasing)
        mask.scale(device_px / _GRID, device_px / _GRID)
        outside = QPainterPath()
        outside.addRect(QRectF(0, 0, _GRID, _GRID))
        mask.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        mask.fillPath(outside.subtracted(clip), QColor(0, 0, 0))
        mask.end()
        painter.drawImage(QRectF(0, 0, _GRID, _GRID), image)
    else:
        _fill(painter, _ellipse(_PLANET_CENTRE, _PLANET_RADIUS), _colour("ocean"), clip)
    if fine:
        _stroke(painter, _ellipse(_PLANET_CENTRE, _PLANET_RADIUS), QPen(_colour("atmosphere"), max(4.0, unit_px)), clip)


def _paint(painter: QPainter, size: int, detail: int | None = None) -> None:
    """Paints the icon at ``size`` pixels: the rim and the plate, then
    the scene inside the plate. ``detail`` is the size whose detail is
    drawn; by default ``size`` (the scalable SVG asks for full detail).
    See the module docstring for what each element means."""
    detail = size if detail is None else detail
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    fine = detail >= _FINE_MIN_SIZE

    # The plate: the rim colour as the outer rounded square, the plate
    # inside it, flat at the top and deepening towards the bottom.
    outer, rim, radius = plate_geometry(size)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_colour("rim"))
    painter.drawRoundedRect(outer, radius, radius)
    inner = outer.adjusted(rim, rim, -rim, -rim)
    inner_radius = max(0.0, radius - rim)
    plate_fill = QLinearGradient(0, inner.top(), 0, inner.bottom())
    plate_fill.setColorAt(0, _colour("plate"))
    plate_fill.setColorAt(_PLATE_FLAT, _colour("plate"))
    plate_fill.setColorAt(1, _colour("plate_bottom"))
    plate = QPainterPath()
    plate.addRoundedRect(inner, inner_radius, inner_radius)
    painter.fillPath(plate, plate_fill)

    # The scene, on its design grid mapped onto the plate's inside.
    painter.save()
    painter.setClipPath(plate)
    scale = inner.width() / _SCENE.width()
    painter.translate(inner.left(), inner.top())
    painter.scale(scale, scale)
    painter.translate(-_SCENE.left(), -_SCENE.top())
    unit_px = 1.0 / scale  # one device pixel in grid units
    clip = painter.transform().inverted()[0].map(plate)  # the plate's inside on the grid
    painter.setPen(Qt.PenStyle.NoPen)

    # The Sun, with a soft glow.
    if fine:
        glow = QRadialGradient(_SUN_CENTRE, _SUN_GLOW)
        glow.setColorAt(0, _colour("sun", 80))
        glow.setColorAt(1, _colour("sun", 0))
        _fill(painter, _ellipse(_SUN_CENTRE, _SUN_GLOW), glow, clip)
    sun_radius = _SUN_RADIUS if fine else 20
    _fill(painter, _ellipse(_SUN_CENTRE, sun_radius), _colour("sun"), clip)

    _draw_earth(painter, round(_GRID / unit_px), unit_px, fine, clip)

    satellite = _orbit_point(_SATELLITE_AT)

    # The link beam to a ground station straight below the satellite.
    if detail >= _BEAM_MIN_SIZE:
        dx, dy = satellite.x() - _PLANET_CENTRE.x(), satellite.y() - _PLANET_CENTRE.y()
        length = math.hypot(dx, dy)
        ux, uy = dx / length, dy / length
        station = QPointF(_PLANET_CENTRE.x() + ux * _PLANET_RADIUS, _PLANET_CENTRE.y() + uy * _PLANET_RADIUS)
        half_width = 20
        beam = QPainterPath(satellite)
        beam.lineTo(station.x() - uy * half_width, station.y() + ux * half_width)
        beam.lineTo(station.x() + uy * half_width, station.y() - ux * half_width)
        beam.closeSubpath()
        beam_fill = QLinearGradient(satellite, station)
        beam_fill.setColorAt(0, _colour("beam", 40))
        beam_fill.setColorAt(1, _colour("beam", 150))
        _fill(painter, beam, beam_fill, clip)
        _fill(painter, _ellipse(station, 6), _colour("station"), clip)

    # The orbit: flown track solid, predicted track dashed.
    track = QPen(_colour("orbit"), max(9.0, 1.5 * unit_px))
    track.setCapStyle(Qt.PenCapStyle.RoundCap)
    if detail >= _DASH_MIN_SIZE:
        _stroke(painter, _orbit_arc(_ORBIT_START, _SATELLITE_AT + 6), track, clip)
        track.setDashPattern([1.2, 2.0])
        _stroke(painter, _orbit_arc(_SATELLITE_AT - 14, _ORBIT_END), track, clip)
    else:
        _stroke(painter, _orbit_arc(_ORBIT_START, _ORBIT_END), track, clip)

    # The satellite, its panels along the track, outlined in the plate's
    # dark so it separates from the track under it.
    ahead, behind = _orbit_point(_SATELLITE_AT + 0.5), _orbit_point(_SATELLITE_AT - 0.5)
    painter.save()
    painter.translate(satellite)
    painter.rotate(math.degrees(math.atan2(behind.y() - ahead.y(), behind.x() - ahead.x())))
    scale = 1.0 if detail >= _DASH_MIN_SIZE else 1.3
    panel_w, panel_h, gap, body = 26 * scale, 40 * scale, 4 * scale, 24 * scale
    left_panel = QRectF(-body / 2 - gap - panel_w, -panel_h / 2, panel_w, panel_h)
    right_panel = QRectF(body / 2 + gap, -panel_h / 2, panel_w, panel_h)
    body_rect = QRectF(-body / 2, -body / 2, body, body)
    outline = QPainterPath()
    outline.addRoundedRect(left_panel, 3, 3)
    outline.addRoundedRect(right_panel, 3, 3)
    outline.addRoundedRect(body_rect, 5, 5)
    painter.setPen(QPen(_colour("plate_bottom"), max(8.0, 1.5 * unit_px)))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(outline.simplified())
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_colour("panel"))
    painter.drawRoundedRect(left_panel, 3, 3)
    painter.drawRoundedRect(right_panel, 3, 3)
    painter.setBrush(_colour("body"))
    painter.drawRoundedRect(body_rect, 5, 5)
    painter.restore()

    painter.restore()


def _render(size: int) -> QPixmap:
    """The icon as a ``size`` x ``size`` pixmap on a transparent background."""
    _ensure_application()
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    _paint(painter, size)
    painter.end()
    return pixmap


_SVG_SIZE = 512


def render_svg() -> str:
    """The icon as SVG text (the same painter code through ``QSvgGenerator``),
    512 x 512 user units with full detail: the hicolor theme's
    ``scalable/apps`` icon, which software centres also show."""
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    from PySide6.QtSvg import QSvgGenerator

    _ensure_application()
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    generator = QSvgGenerator()
    generator.setOutputDevice(buffer)
    generator.setSize(QSize(_SVG_SIZE, _SVG_SIZE))
    generator.setViewBox(QRect(0, 0, _SVG_SIZE, _SVG_SIZE))
    generator.setTitle("SpaceMissionStudio")
    generator.setDescription("The SpaceMissionStudio application icon")
    painter = QPainter(generator)
    _paint(painter, _SVG_SIZE)
    painter.end()
    buffer.close()
    text = bytes(data.data()).decode("utf-8")
    # QSvgGenerator gives the size in millimetres from its resolution; an
    # icon is sized in user units.
    return re.sub(r'(<svg\b[^>]*?)\swidth="[^"]*"\s+height="[^"]*"', rf'\1 width="{_SVG_SIZE}" height="{_SVG_SIZE}"',
                  text, count=1)


def write_icon_theme(hicolor_dir: str | Path) -> list[Path]:
    """Writes the icon into the hicolor icon theme folder ``hicolor_dir``
    (for example ``/usr/share/icons/hicolor``): a PNG of each of
    :data:`ICON_THEME_SIZES` in ``<n>x<n>/apps/`` and the SVG in
    ``scalable/apps/``. Existing files are replaced. Returns the files
    written.

    Raises :class:`OSError` if a render or save fails (see
    :func:`ensure_icon_file`).
    """
    root = Path(hicolor_dir)
    written: list[Path] = []
    for size in ICON_THEME_SIZES:
        path = root / f"{size}x{size}" / "apps" / f"{ICON_NAME}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        if not _render(size).save(str(path), "PNG"):
            raise OSError(f"could not render/save the app icon to {path}")
        written.append(path)
    svg = root / "scalable" / "apps" / f"{ICON_NAME}.svg"
    svg.parent.mkdir(parents=True, exist_ok=True)
    svg.write_text(render_svg(), encoding="utf-8")
    written.append(svg)
    return written


def app_icon() -> QIcon:
    """A multi-resolution :class:`QIcon` -- Qt picks the best size for
    each context (window titlebar, taskbar, alt-tab switcher, ...) from
    whichever sizes are registered.
    """
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(_render(size))
    return icon


def ensure_icon_file(path: str | Path, size: int = 256) -> Path:
    """Renders the icon to a PNG at ``path`` (creating parent directories
    as needed) if it doesn't already exist, and returns the path. Used by
    ``packaging/`` for the ``.desktop`` entry's ``Icon=`` target, which
    needs a real file, not an in-memory :class:`QIcon`.

    Raises :class:`OSError` if the render/save fails (e.g. no usable Qt
    platform plugin) -- ``QPixmap.save()`` only returns ``False`` on
    failure rather than raising, which would otherwise let
    ``install.sh``'s calling ``python3 -c ...`` exit 0 having silently
    written nothing, and its shell ``if`` guard report success anyway.
    """
    path = Path(path)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        if not _render(size).save(str(path), "PNG"):
            raise OSError(f"could not render/save the app icon to {path}")
    return path


def toolbar_icon(name: str) -> QIcon:
    """One of the app's toolbar and menu icons (a Lucide icon, ``theme.icons.ACTION_ICONS``),
    tinted from the theme and following a theme change."""
    from .theme import action_icon

    return action_icon(name)


def step_icon(kind: str) -> QIcon:
    """A Mission Sequence step kind's icon; an empty icon for an unknown kind."""
    from .theme import step_icon as _step_icon

    return _step_icon(kind)
