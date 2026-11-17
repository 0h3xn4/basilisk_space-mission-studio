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

"""The application icon -- drawn procedurally with :class:`QPainter`
(a satellite glyph: a gold body between two blue solar panels, plus an
antenna at larger sizes, matching ``theme.py``'s accent color for the
panels) rather than shipped as a bitmap asset, so there is no binary
file to keep in sync with the theme and no new packaging step
(``packaging/build_wheel.sh``/the installer's ``.desktop`` entry already
just point at whatever :func:`app_icon`/:func:`window_icon_path`
produce). Used as both the ``QApplication``/``QMainWindow`` window icon
(see ``app.py``) and, cached to a PNG on disk, the ``.desktop`` entry's
``Icon=`` target (see ``packaging/``) -- a ``.desktop`` file needs a
real file path, not an in-memory ``QIcon``.

Real user feedback, with a rendered side-by-side comparison, on the
FIRST design this module drew (a dark central body inside a thin
inclined orbit ellipse, with a small dot on the ring): "refine it to
read clearer at small sizes" -- at 16-32px (window titlebar/taskbar,
where this icon is actually seen most) it read as a cartoon eye, not
an orbit. Root cause, confirmed by rendering variants and comparing
them side by side rather than guessing: "a filled circle centered
inside a surrounding ring" is essentially the universal flat-icon glyph
for an eye (pupil + iris), and no amount of stroke-width/dot-size
tuning on that same structure fixed it -- several tuning passes made it
read MORE eye-like, not less (a bigger, lighter dot became an
eye-catchlight). Fixing it needed a structurally different silhouette,
not parameter tweaks on the same one.

Replaced with an angular satellite glyph (body + two solar-panel
wings), which stays legible at every size tested (256 down to 16px)
specifically because it has no closed ring-around-a-disc shape to be
mistaken for an eye, and reads clearly as spacecraft hardware instead --
also a better thematic fit for a *mission-analysis* tool than a single
orbit-and-dot, which only depicts one specific orbit rather than the
domain generally. The body's gold color is not arbitrary: real
satellites commonly use gold-foil (multi-layer insulation) thermal
blankets, so a gold body next to blue solar panels is representationally
accurate, not just decorative -- and it was ALSO found (by rendering the
icon against both light and dark backgrounds, not assumed) to be the
fix for a real contrast bug the first gold-free attempt had: this
module's original near-black body color is nearly invisible against a
dark-mode taskbar, where a gold body stays clearly visible against both
light and dark surfaces.

2.12.0: the glyph alone was still barely visible on Ubuntu's panels
(measured: 86 % of it below 3 : 1 on #303030 at 64 px, the gold body
1.6 to 1.9 on light panels). The same glyph and colours now sit on a
dark rounded-square plate with a light rim
(``docs/developer/windows-views-design.md``, section 5): the plate is
far from every light panel, the rim from every dark one, and the glyph
fills about 80 % of the plate. ``tests/gui/test_icons.py`` measures it.
"""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPen, QPixmap

from .theme.palettes import APP_ICON

_ACCENT = APP_ICON["panel"]  # solar panels
_ACCENT_DARK = APP_ICON["panel_line"]  # antenna
_GOLD = APP_ICON["body"]  # satellite body -- see module docstring for why gold, not decorative
_GOLD_DARK = APP_ICON["body_line"]  # body centerline detail
_PLATE = APP_ICON["plate"]  # the plate behind the glyph, and the panel grid lines
_RIM = APP_ICON["rim"]  # the plate's rim

#: The file name (without suffix) of the icon in an icon theme: the
#: ``Icon=`` key of the ``.desktop`` entries.
ICON_NAME = "spacemissionstudio"

#: The bitmap sizes installed into the hicolor icon theme (``packaging/build_deb.sh``,
#: ``packaging/install.sh``), next to ``scalable/apps/spacemissionstudio.svg``.
ICON_THEME_SIZES = (16, 22, 24, 32, 48, 64, 128, 256, 512)

# Below these sizes the corresponding detail is omitted entirely rather
# than drawn illegibly thin -- confirmed by rendering both thresholds
# and comparing (the antenna line/dot were already invisible by 24px;
# the panel grid lines by 40px), not guessed.
_ANTENNA_MIN_SIZE = 40
_GRID_MIN_SIZE = 56

# The plate, on a 64-unit grid: a margin of 2 (none below 24 px, where
# half a pixel only blurs the edge), a rim of 2 (at least 1 px) and a
# corner radius of 12. The glyph's turned outline (200 x 175 units of the
# 256 design grid; the antenna stays inside it) fills _GLYPH_FILL of the
# width inside the rim; more at 32 px and below, where every pixel of shape
# counts (chosen by rendering 0.80 to 1.0 side by side at 16 to 48 px).
_PLATE_MARGIN = 2 / 64
_RIM_WIDTH = 2 / 64
_PLATE_RADIUS = 12 / 64
_GLYPH_EXTENT = 200.0
_GLYPH_FILL = 0.85
_GLYPH_FILL_SMALL = 0.95
_SMALL_SIZE = 32


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


def _paint(painter: QPainter, size: int, detail: int | None = None) -> None:
    """Paints the icon at ``size`` pixels: the plate, then the glyph.
    ``detail`` is the size whose detail (antenna, grid lines) is drawn;
    by default ``size`` (the scalable SVG asks for full detail).

    See module docstring for why this is a satellite glyph (body +
    two solar panels + an antenna at larger sizes) and not the earlier
    orbit-ellipse design. ``scale``/rotation/proportions below were
    tuned by rendering actual candidates side by side at 256 down to
    16px and comparing them, not picked once and trusted -- an earlier
    tuning pass that only adjusted the old design's stroke width/dot
    size made it read MORE like an eye, not less, which is why this is
    a different silhouette entirely rather than a parameter change.
    """
    detail = size if detail is None else detail
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # The plate: the rim colour as the outer rounded square, the plate
    # colour inside it.
    outer, rim, radius = plate_geometry(size)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(_RIM))
    painter.drawRoundedRect(outer, radius, radius)
    inner = outer.adjusted(rim, rim, -rim, -rim)
    painter.setBrush(QColor(_PLATE))
    painter.drawRoundedRect(inner, max(0.0, radius - rim), max(0.0, radius - rim))

    painter.translate(size / 2.0, size / 2.0)
    painter.rotate(-32.0)

    # s: the 256px design grid, scaled so the glyph's turned outline fills
    # its share of the plate's inside.
    fill = _GLYPH_FILL_SMALL if size <= _SMALL_SIZE else _GLYPH_FILL
    s = inner.width() * fill / _GLYPH_EXTENT

    panel_w, panel_h = 58 * s, 96 * s
    gap = 7 * s
    body_w, body_h = 46 * s, 46 * s
    left_panel = QRectF(-body_w / 2 - gap - panel_w, -panel_h / 2, panel_w, panel_h)
    right_panel = QRectF(body_w / 2 + gap, -panel_h / 2, panel_w, panel_h)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(_ACCENT))
    painter.drawRoundedRect(left_panel, 5 * s, 5 * s)
    painter.drawRoundedRect(right_panel, 5 * s, 5 * s)

    if detail >= _GRID_MIN_SIZE:
        grid_pen = QPen(QColor(_PLATE))
        grid_pen.setWidthF(max(1.0, 1.5 * s))
        painter.setPen(grid_pen)
        for panel in (left_panel, right_panel):
            for frac in (0.33, 0.66):
                y = panel.top() + panel.height() * frac
                painter.drawLine(QPointF(panel.left() + 2 * s, y), QPointF(panel.right() - 2 * s, y))

    body_rect = QRectF(-body_w / 2, -body_h / 2, body_w, body_h)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(_GOLD))
    painter.drawRoundedRect(body_rect, 9 * s, 9 * s)
    if detail >= _GRID_MIN_SIZE:
        centerline_pen = QPen(QColor(_GOLD_DARK))
        centerline_pen.setWidthF(max(1.0, 1.4 * s))
        painter.setPen(centerline_pen)
        painter.drawLine(QPointF(-body_w / 2 + 3 * s, 0), QPointF(body_w / 2 - 3 * s, 0))

    if detail >= _ANTENNA_MIN_SIZE:
        antenna_pen = QPen(QColor(_ACCENT))
        antenna_pen.setWidthF(max(4 * s, 1.8))
        antenna_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(antenna_pen)
        antenna_tip = QPointF(0, -body_h / 2 - 22 * s)
        painter.drawLine(QPointF(0, -body_h / 2), antenna_tip)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(_ACCENT))
        painter.drawEllipse(antenna_tip, max(5 * s, 2.2), max(5 * s, 2.2))


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
