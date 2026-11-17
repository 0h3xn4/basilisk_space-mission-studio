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


# The panels an icon sits on: Ubuntu's dark dock and top bar (#303030,
# #1D1D1D, #242424) and light panels (#FAFAFA, #EBEBEB)
# (docs/developer/windows-views-design.md, section 5).
_DARK_PANELS = ("#303030", "#1D1D1D", "#242424")
_LIGHT_PANELS = ("#FAFAFA", "#EBEBEB")


def _hex(image, x, y):
    from PySide6.QtGui import QColor

    colour = QColor(image.pixel(x, y))
    assert colour.alpha() == 255, f"pixel ({x}, {y}) is not opaque"
    return colour.name().upper()


@pytest.mark.parametrize("size", [16, 22, 24, 32, 48, 64, 128, 256, 512])
def test_the_icon_plate_and_rim_stand_out_on_dark_and_light_panels(qapp, size):
    """2.12.0 defect: the plate-less glyph was barely visible on Ubuntu's
    panels (the blue panels 2.55 : 1 on #303030, the gold body 1.86 : 1 on
    #FAFAFA). The outline of the icon is its rim and the plate inside it:
    against every dark and light panel one of the two has 3 : 1 or more
    (WCAG 2.2 1.4.11, graphics), measured on the rendered pixels at each
    size. The rim alone carries it on dark panels, the plate on light ones."""
    from spacemissionstudio.gui.icons import plate_geometry, _render
    from spacemissionstudio.gui.theme.palettes import APP_ICON
    from spacemissionstudio.gui.theme.tokens import contrast

    image = _render(size).toImage()
    outer, rim, _radius = plate_geometry(size)
    top = int(outer.top())
    rim_colour = _hex(image, size // 2, top)  # the middle of the top edge
    plate_colour = _hex(image, int(size * 0.3), top + int(rim) + 1)  # inside it, top left: no glyph there
    assert (rim_colour, plate_colour) == (APP_ICON["rim"].upper(), APP_ICON["plate"].upper())
    for panel in _DARK_PANELS:
        assert contrast(rim_colour, panel) >= 3.0, (size, panel, contrast(rim_colour, panel))
    for panel in _LIGHT_PANELS:
        assert contrast(plate_colour, panel) >= 3.0, (size, panel, contrast(plate_colour, panel))
    for panel in _DARK_PANELS + _LIGHT_PANELS:
        assert max(contrast(rim_colour, panel), contrast(plate_colour, panel)) >= 3.0


def test_the_glyph_stands_out_on_its_plate(qapp):
    """The solar panels (and the antenna drawn in their colour) and the gold
    body have 3 : 1 or more against the plate, and the panel grid lines,
    drawn in the plate colour, 3 : 1 against the panels."""
    from spacemissionstudio.gui.theme.palettes import APP_ICON
    from spacemissionstudio.gui.theme.tokens import contrast

    assert contrast(APP_ICON["panel"], APP_ICON["plate"]) >= 3.0
    assert contrast(APP_ICON["body"], APP_ICON["plate"]) >= 3.0
    assert contrast(APP_ICON["rim"], APP_ICON["plate"]) >= 3.0


def test_the_icon_theme_has_every_hicolor_size_and_the_scalable_svg(qapp, tmp_path):
    """write_icon_theme (the .deb and install.sh) writes a PNG of each size
    from 16 to 512 px at that size, and scalable/apps/spacemissionstudio.svg,
    an SVG of 512 user units that draws the same plate."""
    import xml.etree.ElementTree as ET

    from PySide6.QtGui import QImage

    from spacemissionstudio.gui.icons import ICON_THEME_SIZES, write_icon_theme
    from spacemissionstudio.gui.theme.palettes import APP_ICON

    written = write_icon_theme(tmp_path / "hicolor")
    assert ICON_THEME_SIZES[0] == 16 and ICON_THEME_SIZES[-1] == 512
    assert {16, 22, 24, 32, 48, 64, 128, 256, 512} <= set(ICON_THEME_SIZES)
    for size in ICON_THEME_SIZES:
        path = tmp_path / "hicolor" / f"{size}x{size}" / "apps" / "spacemissionstudio.png"
        assert path in written
        image = QImage(str(path))
        assert (image.width(), image.height()) == (size, size), path
    svg = tmp_path / "hicolor" / "scalable" / "apps" / "spacemissionstudio.svg"
    assert svg in written
    root = ET.parse(svg).getroot()
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert (root.get("width"), root.get("height"), root.get("viewBox")) == ("512", "512", "0 0 512 512")
    text = svg.read_text(encoding="utf-8").lower()
    for colour in ("plate", "rim", "panel", "body"):
        assert APP_ICON[colour].lower() in text, colour


def test_write_icon_theme_replaces_an_older_icon(qapp, tmp_path):
    """Unlike ensure_icon_file, the theme is written again: an install over
    an older one (install.sh) gets the new icon."""
    from spacemissionstudio.gui.icons import write_icon_theme

    old = tmp_path / "256x256" / "apps" / "spacemissionstudio.png"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"an older icon")
    write_icon_theme(tmp_path)
    assert old.read_bytes().startswith(b"\x89PNG")


def test_the_windows_icon_file_is_the_current_icon(qapp):
    """packaging/windows/spacemissionstudio.ico (the setup program, its
    shortcuts, install.ps1) is generated from gui/icons.py and committed.
    Each of its sizes must still match a fresh render; after a change to the
    icon, run ``python packaging/make_ico.py --from-app
    packaging/windows/spacemissionstudio.ico``."""
    import importlib.util
    from pathlib import Path

    from PySide6.QtGui import QImage

    from spacemissionstudio.gui.icons import _render

    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("make_ico", root / "packaging" / "make_ico.py")
    make_ico = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(make_ico)

    entries = make_ico.read_ico((root / "packaging" / "windows" / "spacemissionstudio.ico").read_bytes())
    assert [size for size, _kind, _rgba in entries] == list(make_ico.ICO_SIZES)
    for size, _kind, rgba in entries:
        fresh = _render(size).toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        expected = bytes(fresh.constBits())[:size * size * 4]
        # Mean difference per channel: 0 when generated with the same Qt;
        # a little room for another Qt version's anti-aliasing.
        difference = sum(abs(a - b) for a, b in zip(rgba, expected)) / len(expected)
        assert difference < 2.0, f"{size} px differs from the icon by {difference:.2f} on average"
