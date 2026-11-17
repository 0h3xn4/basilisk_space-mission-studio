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

"""The Windows icon file (packaging/make_ico.py, packaging/windows/
spacemissionstudio.ico): the ICO layout, the PNG reader and the
committed file's sizes. tests/gui/test_icons.py checks that the
committed file is the current icon."""

import importlib.util
import struct
import zlib
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("make_ico", _ROOT / "packaging" / "make_ico.py")
make_ico = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(make_ico)


def _paeth(left, up, upper_left):
    estimate = left + up - upper_left
    pa, pb, pc = abs(estimate - left), abs(estimate - up), abs(estimate - upper_left)
    return left if pa <= pb and pa <= pc else (up if pb <= pc else upper_left)


def _png(width, height, rgba):
    """An 8-bit RGBA PNG whose rows use the filters 0 to 4 in turn, so the
    reader meets each of them."""
    stride = width * 4
    raw = bytearray()
    previous = bytes(stride)
    for row in range(height):
        line = rgba[row * stride:(row + 1) * stride]
        kind = row % 5
        out = bytearray()
        for i in range(stride):
            left = line[i - 4] if i >= 4 else 0
            up = previous[i]
            upper_left = previous[i - 4] if i >= 4 else 0
            predictor = (0, left, up, (left + up) >> 1, _paeth(left, up, upper_left))[kind]
            out.append((line[i] - predictor) & 0xFF)
        raw += bytes([kind]) + out
        previous = line

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(bytes(raw))) + chunk(b"IEND", b"")


def _pattern(size):
    """Pixels with every channel varying, some fully transparent."""
    return bytes(
        value
        for y in range(size)
        for x in range(size)
        for value in ((x * 37) % 256, (y * 53) % 256, (x * y) % 256, 0 if (x + y) % 7 == 0 else (x * 11 + y) % 256)
    )


def test_the_png_reader_undoes_every_filter():
    """decode_png gives back the pixels of a PNG that uses each row filter."""
    pixels = _pattern(13)
    assert make_ico.decode_png(_png(13, 13, pixels)) == (13, 13, pixels)


def test_an_icon_round_trips_bitmaps_below_256_px_and_the_png_at_256():
    """build_ico writes 32-bit bitmaps with their mask below 256 px and the
    PNG itself at 256 px, smallest first; read_ico gives the pixels back."""
    sizes = (48, 16, 256, 32)
    pngs = {size: _png(size, size, _pattern(size)) for size in sizes}
    data = make_ico.build_ico([pngs[size] for size in sizes])
    reserved, kind, count = struct.unpack("<HHH", data[:6])
    assert (reserved, kind, count) == (0, 1, 4)
    entries = make_ico.read_ico(data)
    assert [(size, kind) for size, kind, _rgba in entries] == [(16, "bmp"), (32, "bmp"), (48, "bmp"), (256, "png")]
    for size, _kind, rgba in entries:
        assert rgba == _pattern(size), size
    # The 256 px entry is stored with size byte 0, and holds the PNG as it was.
    width, height, _colours, _reserved, _planes, bits, length, offset = struct.unpack("<BBBBHHII", data[54:70])
    assert (width, height, bits) == (0, 0, 32) and data[offset:offset + length] == pngs[256]
    # A fully transparent pixel is set in the bitmap's mask.
    width16, _h, _c, _r, _p, _b, length16, offset16 = struct.unpack("<BBBBHHII", data[6:22])
    mask = data[offset16 + 40 + 16 * 16 * 4:offset16 + length16]
    top_row_mask = mask[15 * 4:15 * 4 + 4]  # rows are stored bottom-up
    assert top_row_mask[0] & 0x80  # pixel (0, 0): x + y = 0, transparent


@pytest.mark.parametrize("bad", [(17, 16), (300, 300)])
def test_an_icon_entry_must_be_square_and_at_most_256_px(bad):
    width, height = bad
    with pytest.raises(make_ico.IconError):
        make_ico.build_ico([_png(width, height, bytes(width * height * 4))])


def test_the_committed_windows_icon_has_every_size_from_16_to_256_px():
    """The setup program's icon file holds 16, 24, 32, 48, 64, 128 and 256 px,
    and the Inno Setup script and install.ps1 use it."""
    data = (_ROOT / "packaging" / "windows" / "spacemissionstudio.ico").read_bytes()
    entries = make_ico.read_ico(data)
    assert [size for size, _kind, _rgba in entries] == [16, 24, 32, 48, 64, 128, 256]
    for size, _kind, rgba in entries:
        assert len(rgba) == size * size * 4
        assert any(rgba[i + 3] == 255 for i in range(0, len(rgba), 4)), f"{size} px is blank"
    iss = (_ROOT / "packaging" / "windows" / "spacemissionstudio.iss").read_text(encoding="utf-8")
    assert "SetupIconFile=spacemissionstudio.ico" in iss
    assert "UninstallDisplayIcon={app}\\spacemissionstudio.ico" in iss
    assert 'Source: "spacemissionstudio.ico"; DestDir: "{app}"' in iss
    assert iss.count('IconFilename: "{app}\\spacemissionstudio.ico"') == 2
    assert "python.exe\"; Tasks" not in iss and 'IconFilename: "{app}\\python' not in iss
    install_ps1 = (_ROOT / "packaging" / "install.ps1").read_text(encoding="utf-8")
    assert 'windows\\spacemissionstudio.ico' in install_ps1 and "$Shortcut.IconLocation" in install_ps1
