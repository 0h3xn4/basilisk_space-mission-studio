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
"""Tests for gui.icons."""

import pytest

pytestmark = pytest.mark.requires_gui


def test_app_icon_returns_a_non_null_icon(qapp):
    """The app icon exists in at least one size."""
    from spacemissionstudio.gui.icons import app_icon

    icon = app_icon()
    assert not icon.isNull()
    assert len(icon.availableSizes()) > 0


def test_app_icon_pixmap_is_not_blank(qapp):
    """Regression test: an earlier version of the icon-drawing code
    reused ``painter.pen()`` for the orbit ring after having just set
    ``Qt.PenStyle.NoPen`` for the central body -- setColor()/setWidthF()
    don't change a pen's STYLE, so the ring silently never drew, and only
    the two dots rendered. Checking for more than 2 distinct non
    -transparent colors catches that class of bug without pinning down
    exact pixel values (which would break on any legitimate color tweak).
    """
    from PySide6.QtGui import QColor

    from spacemissionstudio.gui.icons import _render

    pixmap = _render(64)
    image = pixmap.toImage()
    colors = set()
    for x in range(0, image.width(), 2):
        for y in range(0, image.height(), 2):
            pixel = QColor(image.pixel(x, y))
            if pixel.alpha() > 0:
                colors.add((pixel.red(), pixel.green(), pixel.blue()))
    assert len(colors) >= 3, f"expected at least 3 distinct colors (body/ring/satellite), got {colors}"


def test_large_icon_includes_the_gold_body_color(qapp):
    """Regression guard for the current (satellite-glyph) design: real
    user feedback on the ORIGINAL design ("refine it to read clearer at
    small sizes") led to a full redesign, not a parameter tweak -- see
    icons.py's own module docstring for why. This pins the one part of
    that redesign a generic "at least N colors" check (the test above)
    wouldn't catch regressing: the body is specifically gold (chosen for
    light/dark-background contrast, not just aesthetics), not the
    original design's near-black.
    """
    from PySide6.QtGui import QColor

    from spacemissionstudio.gui.icons import _GOLD, _render

    pixmap = _render(256)
    image = pixmap.toImage()
    gold = QColor(_GOLD)
    colors = {
        (QColor(image.pixel(x, y)).red(), QColor(image.pixel(x, y)).green(), QColor(image.pixel(x, y)).blue())
        for x in range(0, image.width(), 2)
        for y in range(0, image.height(), 2)
        if QColor(image.pixel(x, y)).alpha() > 0
    }
    assert (gold.red(), gold.green(), gold.blue()) in colors


def test_small_icon_omits_fine_detail_that_would_render_illegibly(qapp):
    """The antenna and panel/body grid-line detail are omitted below
    their own size thresholds (found by rendering both and comparing --
    see icons.py's module docstring) rather than drawn at a thickness
    that anti-aliases away to noise. A 16px render should have
    meaningfully fewer distinct colors than a 256px one as a result.
    """
    from PySide6.QtGui import QColor

    from spacemissionstudio.gui.icons import _render

    def distinct_colors(size):
        image = _render(size).toImage()
        return {
            (QColor(image.pixel(x, y)).red(), QColor(image.pixel(x, y)).green(), QColor(image.pixel(x, y)).blue())
            for x in range(image.width())
            for y in range(image.height())
            if QColor(image.pixel(x, y)).alpha() > 0
        }

    assert len(distinct_colors(16)) < len(distinct_colors(256))


def test_ensure_icon_file_creates_a_real_png(qapp, tmp_path):
    """ensure_icon_file writes a PNG file."""
    from spacemissionstudio.gui.icons import ensure_icon_file

    target = tmp_path / "icons" / "spacemissionstudio.png"
    result = ensure_icon_file(target)

    assert result == target
    assert target.exists()
    assert target.stat().st_size > 0
    assert target.read_bytes().startswith(b"\x89PNG")


def test_ensure_icon_file_does_not_overwrite_an_existing_file(qapp, tmp_path):
    """ensure_icon_file leaves an existing file as it is."""
    from spacemissionstudio.gui.icons import ensure_icon_file

    target = tmp_path / "spacemissionstudio.png"
    target.write_bytes(b"not a real png, just a marker")

    result = ensure_icon_file(target)

    assert result == target
    assert target.read_bytes() == b"not a real png, just a marker"


def _contrast(colour_a, colour_b):
    """The WCAG 2.2 contrast ratio of two ``#RRGGBB`` colours."""

    def luminance(colour):
        channels = [int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    high, low = sorted((luminance(colour_a), luminance(colour_b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


# Taskbar and dock backgrounds the icon is seen on: Windows 11 and 10 dark
# taskbars, Ubuntu's dark dock and a black panel; Windows and Ubuntu light.
_DARK_TASKBARS = ("#202020", "#101010", "#2C2C2C", "#000000")
_LIGHT_TASKBARS = ("#F3F3F3", "#FAFAFA")


def test_the_tile_stands_out_on_dark_and_light_taskbars():
    """The tile's outline reaches the WCAG 3:1 for graphical objects on
    every dark taskbar (the rim; the navy tile alone is 1.0-1.5:1 there),
    and the tile itself on every light one."""
    from spacemissionstudio.gui.theme.palettes import APP_ICON

    for taskbar in _DARK_TASKBARS:
        assert _contrast(APP_ICON["tile_rim"], taskbar) >= 3.0, taskbar
    for taskbar in _LIGHT_TASKBARS:
        assert _contrast(APP_ICON["tile_rim"], taskbar) >= 3.0, taskbar
        assert _contrast(APP_ICON["tile_top"], taskbar) >= 3.0, taskbar


def test_the_rim_is_drawn_at_every_size(qapp):
    """The rim colour is on the tile's edge (the middle of its left side)
    at every registered size, down to 16 px."""
    from PySide6.QtGui import QColor

    from spacemissionstudio.gui.icons import _render
    from spacemissionstudio.gui.theme.palettes import APP_ICON

    rim = QColor(APP_ICON["tile_rim"])
    for size in (16, 24, 32, 48, 64, 128, 256):
        image = _render(size).toImage()
        x = round(size * 12 / 256)  # the tile's left edge on the 256 grid
        pixel = image.pixelColor(x, size // 2)
        distance = abs(pixel.red() - rim.red()) + abs(pixel.green() - rim.green()) + abs(pixel.blue() - rim.blue())
        assert pixel.alpha() == 255 and distance < 30, (size, pixel.name())


def test_the_earth_shows_land_not_only_ocean(qapp):
    """The Earth is the Blue Marble texture, not a plain blue disc: a
    good share of the Earth's pixels are land (red at least as strong as
    blue: desert and vegetation), which no ocean or tile pixel is."""
    from PySide6.QtGui import QColor

    from spacemissionstudio.gui import icons

    assert icons._earth_layer() is not None, "the bundled Earth texture did not load"
    image = icons._render(256).toImage()
    land = earth = 0
    for x in range(20, 180, 2):
        for y in range(160, 240, 2):
            if (x - 60) ** 2 + (y - 272) ** 2 > 130 ** 2:
                continue  # outside the Earth's disc
            pixel = QColor(image.pixel(x, y))
            earth += 1
            land += pixel.red() >= pixel.blue() + 10
    assert land / earth > 0.25, f"only {land} of {earth} Earth pixels look like land"


def test_ensure_icon_file_overwrites_when_asked(qapp, tmp_path):
    """With ``overwrite=True`` (the installers' call) an icon an earlier
    version installed is replaced."""
    from spacemissionstudio.gui.icons import ensure_icon_file

    target = tmp_path / "spacemissionstudio.png"
    target.write_bytes(b"the previous version's icon")

    ensure_icon_file(target, overwrite=True)

    assert target.read_bytes().startswith(b"\x89PNG")


def _ico_directory(data):
    """The ``(size, offset, length)`` entries of an ICO file's directory."""
    import struct

    reserved, kind, count = struct.unpack_from("<HHH", data, 0)
    assert (reserved, kind) == (0, 1), "not an icon file"
    entries = []
    for i in range(count):
        width, height, _, _, planes, bits, length, offset = struct.unpack_from("<BBBBHHII", data, 6 + 16 * i)
        assert width == height and planes == 1 and bits == 32
        assert offset + length <= len(data)
        entries.append((width or 256, offset, length))
    return entries


def test_write_ico_writes_every_size_readable_by_qt(qapp, tmp_path):
    """write_ico writes a valid ICO with each of ICO_SIZES; Qt reads each
    image back at its size, opaque in the middle and transparent in the
    corner (the tile's rounded corner)."""
    from PySide6.QtGui import QImageReader

    from spacemissionstudio.gui.icons import ICO_SIZES, write_ico

    path = write_ico(tmp_path / "app.ico")

    assert sorted(size for size, _, _ in _ico_directory(path.read_bytes())) == sorted(ICO_SIZES)
    reader = QImageReader(str(path))
    assert reader.imageCount() == len(ICO_SIZES)
    for index in range(reader.imageCount()):
        reader.jumpToImage(index)
        image = reader.read()
        assert image.width() in ICO_SIZES
        assert image.pixelColor(image.width() // 2, image.height() // 2).alpha() == 255
        assert image.pixelColor(0, 0).alpha() == 0


def test_the_committed_icon_files_are_valid():
    """The files scripts/build_app_icon_files.py writes are in place: the
    Windows setup program's .ico with 16 to 256 px, the 256 px PNG, and
    the banner with the icon embedded between its markers."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    ico = (root / "packaging" / "windows" / "spacemissionstudio.ico").read_bytes()
    sizes = {size for size, _, _ in _ico_directory(ico)}
    assert {16, 32, 48, 256} <= sizes
    assert (root / "docs" / "images" / "app_icon.png").read_bytes().startswith(b"\x89PNG")
    banner = (root / "docs" / "images" / "banner.svg").read_text(encoding="utf-8")
    assert '<!-- app-icon -->\n  <image x="46" y="16" width="128" height="128" href="data:image/png;base64,' in banner
