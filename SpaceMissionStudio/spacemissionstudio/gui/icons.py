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
with the palette and no extra packaging step. ``app.py`` uses it as the
window icon; :func:`ensure_icon_file` saves it as a PNG for the Linux
``.desktop`` entry, and :func:`write_ico` as the ``.ico`` of the Windows
shortcuts; both need a real file.

**What it shows.** A mission scene on a deep-space tile, one element for
each thing the tool analyses:

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
keeps that lesson: the planet sits off-centre and is cut by the tile's
corner, and the orbit is an open arc, so there is no ring around a disc.

**Small sizes.** Below 32 px the Sun's glow and the atmosphere rim are
left out, and the Sun and satellite are drawn larger; below 24 px the
beam is left out; below 48 px the orbit is one solid arc (dashes blur
into a grey line). Each threshold was found by rendering 256 down to
16 px on light and dark backgrounds and comparing.

**Colours** are ``theme.palettes.APP_ICON``; the Earth's come from its
texture. The dark tile separates the icon from light taskbars, and a
light rim around it from dark ones (Windows, Ubuntu); the body's gold is
the gold foil (multi-layer insulation) of real satellites.
"""

from __future__ import annotations

import functools
import math
import struct
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QGuiApplication, QIcon, QImage, QLinearGradient, QPainter, QPainterPath, QPen,
                           QPixmap, QRadialGradient)

from .theme.palettes import APP_ICON

_GOLD = APP_ICON["body"]  # satellite body -- see module docstring for why gold, not decorative

# The design grid: 256 x 256 units, scaled to the requested size.
_GRID = 256.0
_TILE = QRectF(12, 12, 232, 232)
_TILE_RADIUS = 52
_RIM_WIDTH = 5  # the tile's rim, at least one device pixel
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
_SUN_CENTRE, _SUN_RADIUS = QPointF(62, 58), 18

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
    bottom = min(res, math.ceil(_TILE.bottom() * scale))
    left = max(0, math.floor(_TILE.left() * scale))
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


def _draw_earth(painter: QPainter, size: int, unit_px: float, fine: bool) -> None:
    """The Earth (see :func:`_earth_layer`) and, at fine sizes, its limb."""
    layer = _earth_layer()
    if layer is not None:
        scaled = layer.scaled(size, size, Qt.AspectRatioMode.IgnoreAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
        painter.drawImage(QRectF(0, 0, _GRID, _GRID), scaled)
    else:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_colour("ocean"))
        painter.drawEllipse(_PLANET_CENTRE, _PLANET_RADIUS, _PLANET_RADIUS)
    if fine:
        painter.setPen(QPen(_colour("atmosphere"), max(4.0, unit_px)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(_PLANET_CENTRE, _PLANET_RADIUS, _PLANET_RADIUS)


def _render(size: int) -> QPixmap:
    """The icon at ``size`` x ``size`` px. See the module docstring for
    what each element means and why detail drops out at small sizes."""
    _ensure_application()
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / _GRID, size / _GRID)
    unit_px = _GRID / size  # one device pixel in grid units
    fine = size >= _FINE_MIN_SIZE

    # The tile and its rim on whole device pixels, so the rim stays crisp
    # (not smeared over two half-lit pixels) at small sizes.
    margin = round(_TILE.left() / unit_px) * unit_px
    tile_rect = QRectF(margin, margin, _GRID - 2 * margin, _GRID - 2 * margin)
    tile = QPainterPath()
    tile.addRoundedRect(tile_rect, _TILE_RADIUS, _TILE_RADIUS)
    tile_fill = QLinearGradient(0, tile_rect.top(), 0, tile_rect.bottom())
    tile_fill.setColorAt(0, _colour("tile_top"))
    tile_fill.setColorAt(1, _colour("tile_bottom"))
    painter.fillPath(tile, tile_fill)
    painter.setClipPath(tile)
    painter.setPen(Qt.PenStyle.NoPen)

    # The Sun, with a soft glow.
    if fine:
        glow = QRadialGradient(_SUN_CENTRE, 48)
        glow.setColorAt(0, _colour("sun", 80))
        glow.setColorAt(1, _colour("sun", 0))
        painter.setBrush(glow)
        painter.drawEllipse(_SUN_CENTRE, 48, 48)
    sun_radius = _SUN_RADIUS if fine else 24
    painter.setBrush(_colour("sun"))
    painter.drawEllipse(_SUN_CENTRE, sun_radius, sun_radius)

    _draw_earth(painter, size, unit_px, fine)

    satellite = _orbit_point(_SATELLITE_AT)

    # The link beam to a ground station straight below the satellite.
    if size >= _BEAM_MIN_SIZE:
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
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(beam_fill)
        painter.drawPath(beam)
        painter.setBrush(_colour("station"))
        painter.drawEllipse(station, 6, 6)

    # The orbit: flown track solid, predicted track dashed.
    track = QPen(_colour("orbit"), max(9.0, 1.5 * unit_px))
    track.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(track)
    if size >= _DASH_MIN_SIZE:
        painter.drawPath(_orbit_arc(_ORBIT_START, _SATELLITE_AT + 6))
        track.setDashPattern([1.2, 2.0])
        painter.setPen(track)
        painter.drawPath(_orbit_arc(_SATELLITE_AT - 14, _ORBIT_END))
    else:
        painter.drawPath(_orbit_arc(_ORBIT_START, _ORBIT_END))

    # The satellite, its panels along the track, outlined in the tile's
    # dark so it separates from the track under it.
    ahead, behind = _orbit_point(_SATELLITE_AT + 0.5), _orbit_point(_SATELLITE_AT - 0.5)
    painter.save()
    painter.translate(satellite)
    painter.rotate(math.degrees(math.atan2(behind.y() - ahead.y(), behind.x() - ahead.x())))
    scale = 1.0 if size >= _DASH_MIN_SIZE else 1.3
    panel_w, panel_h, gap, body = 26 * scale, 40 * scale, 4 * scale, 24 * scale
    left_panel = QRectF(-body / 2 - gap - panel_w, -panel_h / 2, panel_w, panel_h)
    right_panel = QRectF(body / 2 + gap, -panel_h / 2, panel_w, panel_h)
    body_rect = QRectF(-body / 2, -body / 2, body, body)
    outline = QPainterPath()
    outline.addRoundedRect(left_panel, 3, 3)
    outline.addRoundedRect(right_panel, 3, 3)
    outline.addRoundedRect(body_rect, 5, 5)
    painter.setPen(QPen(_colour("tile_bottom"), max(8.0, 1.5 * unit_px)))
    painter.drawPath(outline.simplified())
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_colour("panel"))
    painter.drawRoundedRect(left_panel, 3, 3)
    painter.drawRoundedRect(right_panel, 3, 3)
    painter.setBrush(_colour("body"))
    painter.drawRoundedRect(body_rect, 5, 5)
    painter.restore()

    # The rim, inside the tile's edge, so the tile stands out on dark
    # taskbars (see palettes.APP_ICON).
    painter.setClipping(False)
    rim_width = max(1, round(_RIM_WIDTH / unit_px)) * unit_px
    inset = rim_width / 2
    painter.setPen(QPen(_colour("tile_rim"), rim_width))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(tile_rect.adjusted(inset, inset, -inset, -inset), _TILE_RADIUS - inset, _TILE_RADIUS - inset)

    painter.end()
    return pixmap


def app_icon() -> QIcon:
    """A multi-resolution :class:`QIcon` -- Qt picks the best size for
    each context (window titlebar, taskbar, alt-tab switcher, ...) from
    whichever sizes are registered.
    """
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(_render(size))
    return icon


def ensure_icon_file(path: str | Path, size: int = 256, overwrite: bool = False) -> Path:
    """Renders the icon to a PNG at ``path`` (creating parent directories
    as needed) if it doesn't already exist, or always with ``overwrite``,
    and returns the path. Used by ``packaging/`` for the ``.desktop``
    entry's ``Icon=`` target, which needs a real file, not an in-memory
    :class:`QIcon`. The installers pass ``overwrite=True``, so an upgrade
    replaces the icon an earlier version installed.

    Raises :class:`OSError` if the render/save fails (e.g. no usable Qt
    platform plugin) -- ``QPixmap.save()`` only returns ``False`` on
    failure rather than raising, which would otherwise let
    ``install.sh``'s calling ``python3 -c ...`` exit 0 having silently
    written nothing, and its shell ``if`` guard report success anyway.
    """
    path = Path(path)
    if overwrite or not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        if not _render(size).save(str(path), "PNG"):
            raise OSError(f"could not render/save the app icon to {path}")
    return path


# The sizes of the Windows icon file: the shell's small and large icons
# at 100-200 % display scaling, and 256 for the largest views.
ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 256)


def _ico_bitmap(image: QImage) -> bytes:
    """``image`` as an ICO bitmap entry: a 32-bit BGRA DIB, rows bottom
    up, followed by an all-zero AND mask (the alpha channel decides)."""
    image = image.convertToFormat(QImage.Format.Format_ARGB32)
    width, height = image.width(), image.height()
    header = struct.pack("<IiiHHIIiiII", 40, width, 2 * height, 1, 32, 0, width * height * 4, 0, 0, 0, 0)
    stride = image.bytesPerLine()
    data = bytes(image.constBits())
    rows = b"".join(data[y * stride:y * stride + width * 4] for y in reversed(range(height)))
    mask_stride = ((width + 31) // 32) * 4
    return header + rows + bytes(mask_stride * height)


def write_ico(path: str | Path, sizes: tuple[int, ...] = ICO_SIZES) -> Path:
    """Writes the icon as a Windows ``.ico`` file with ``sizes`` and
    returns its path. A Windows shortcut (``.lnk``) and Inno Setup need a
    real ``.ico``; a PNG does not work there. Sizes up to 64 are 32-bit
    bitmaps and larger ones PNG, the layout every Windows version since
    Vista and Inno Setup read.

    Raises :class:`OSError` if an image cannot be encoded.
    """
    path = Path(path)
    entries = []
    for size in sizes:
        image = _render(size).toImage()
        if size > 64:
            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            if not image.save(buffer, "PNG"):
                raise OSError(f"could not encode the {size} px icon as PNG")
            entries.append((size, bytes(buffer.data())))
        else:
            entries.append((size, _ico_bitmap(image)))
    offset = 6 + 16 * len(entries)
    directory = struct.pack("<HHH", 0, 1, len(entries))
    for size, data in entries:
        side = 0 if size >= 256 else size  # 0 means 256 in an ICO directory
        directory += struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(directory + b"".join(data for _, data in entries))
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
