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

"""Packs the application icon into a Windows ``.ico`` file: the setup
program's icon, its shortcuts and its entry under Apps
(``packaging/windows/spacemissionstudio.iss``) and the Start Menu
shortcut of ``packaging/install.ps1``.

The icon is drawn by ``spacemissionstudio/gui/icons.py``; the ``.ico`` is
generated from it and committed, because the setup program is built on
Windows from the repository. To make it again after a change to the
icon, from the ``SpaceMissionStudio`` folder (needs PySide6)::

    QT_QPA_PLATFORM=offscreen python packaging/make_ico.py --from-app packaging/windows/spacemissionstudio.ico

Or from PNG files of the sizes wanted::

    python packaging/make_ico.py OUT.ico icon16.png icon32.png ... icon256.png

Entries below 256 px are 32-bit bitmaps with an alpha channel, the 256 px
entry is the PNG itself: the layout every Windows version since Vista
reads, and the one tools that edit resources (Inno Setup) expect.

Standard library only, apart from ``--from-app``.
"""

from __future__ import annotations

import argparse
import struct
import sys
import tempfile
import zlib
from pathlib import Path

#: The sizes of the committed ``.ico``.
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class IconError(ValueError):
    """A PNG or ICO this module cannot read or write."""


def _png_chunks(data: bytes):
    if not data.startswith(_PNG_SIGNATURE):
        raise IconError("not a PNG file")
    position = len(_PNG_SIGNATURE)
    while position < len(data):
        length, kind = struct.unpack(">I4s", data[position:position + 8])
        yield kind, data[position + 8:position + 8 + length]
        position += 12 + length


def png_size(data: bytes) -> tuple[int, int]:
    """Width and height of a PNG, from its header."""
    kind, header = next(_png_chunks(data))
    if kind != b"IHDR":
        raise IconError("the PNG does not start with IHDR")
    return struct.unpack(">II", header[:8])


def decode_png(data: bytes) -> tuple[int, int, bytes]:
    """Width, height and RGBA pixels (straight alpha, top row first) of an
    8-bit RGB or RGBA PNG that is not interlaced (as Qt writes them)."""
    header = b""
    compressed = bytearray()
    for kind, body in _png_chunks(data):
        if kind == b"IHDR":
            header = body
        elif kind == b"IDAT":
            compressed += body
        elif kind == b"IEND":
            break
    width, height, depth, colour, _compression, _filter, interlace = struct.unpack(">IIBBBBB", header)
    if depth != 8 or colour not in (2, 6) or interlace:
        raise IconError(f"unsupported PNG (bit depth {depth}, colour type {colour}, interlace {interlace})")
    channels = 4 if colour == 6 else 3
    stride = width * channels
    raw = zlib.decompress(bytes(compressed))
    pixels = bytearray()
    previous = bytearray(stride)
    for row in range(height):
        start = row * (stride + 1)
        kind = raw[start]
        line = bytearray(raw[start + 1:start + 1 + stride])
        for i in range(stride):
            left = line[i - channels] if i >= channels else 0
            up = previous[i]
            upper_left = previous[i - channels] if i >= channels else 0
            if kind == 1:
                line[i] = (line[i] + left) & 0xFF
            elif kind == 2:
                line[i] = (line[i] + up) & 0xFF
            elif kind == 3:
                line[i] = (line[i] + ((left + up) >> 1)) & 0xFF
            elif kind == 4:
                estimate = left + up - upper_left
                pa, pb, pc = abs(estimate - left), abs(estimate - up), abs(estimate - upper_left)
                predictor = left if pa <= pb and pa <= pc else (up if pb <= pc else upper_left)
                line[i] = (line[i] + predictor) & 0xFF
            elif kind != 0:
                raise IconError(f"unknown PNG filter {kind}")
        previous = line
        if channels == 4:
            pixels += line
        else:
            for i in range(0, stride, 3):
                pixels += line[i:i + 3] + b"\xff"
    return width, height, bytes(pixels)


def _bitmap_entry(width: int, height: int, rgba: bytes) -> bytes:
    """An ICO bitmap entry: a BITMAPINFOHEADER (height doubled for the
    mask), BGRA rows bottom-up, then the 1-bit mask (set = transparent)."""
    header = struct.pack("<IiiHHIIiiII", 40, width, 2 * height, 1, 32, 0, 0, 0, 0, 0, 0)
    rows = []
    mask_rows = []
    mask_stride = ((width + 31) // 32) * 4
    for y in range(height - 1, -1, -1):
        row = bytearray()
        mask = bytearray(mask_stride)
        for x in range(width):
            r, g, b, a = rgba[(y * width + x) * 4:(y * width + x) * 4 + 4]
            row += bytes((b, g, r, a))
            if a == 0:
                mask[x // 8] |= 0x80 >> (x % 8)
        rows.append(bytes(row))
        mask_rows.append(bytes(mask))
    return header + b"".join(rows) + b"".join(mask_rows)


def build_ico(pngs: list[bytes]) -> bytes:
    """The ``.ico`` holding each PNG (square, at most 256 px), smallest first."""
    entries = []
    for data in pngs:
        width, height = png_size(data)
        if width != height or not 1 <= width <= 256:
            raise IconError(f"an icon entry must be square and 1 to 256 px, not {width} x {height}")
        if width == 256:
            entries.append((width, data))
        else:
            entries.append((width, _bitmap_entry(*decode_png(data))))
    entries.sort(key=lambda entry: entry[0])
    out = bytearray(struct.pack("<HHH", 0, 1, len(entries)))
    offset = 6 + 16 * len(entries)
    for size, data in entries:
        out += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    for _size, data in entries:
        out += data
    return bytes(out)


def read_ico(data: bytes) -> list[tuple[int, str, bytes]]:
    """The entries of an ``.ico``: (size, ``"png"`` or ``"bmp"``, RGBA
    pixels top row first). Reads what :func:`build_ico` writes."""
    reserved, kind, count = struct.unpack("<HHH", data[:6])
    if reserved != 0 or kind != 1 or count == 0:
        raise IconError("not an icon file")
    entries = []
    for i in range(count):
        width, _height, _colours, _reserved, _planes, _bits, length, offset = struct.unpack(
            "<BBBBHHII", data[6 + 16 * i:22 + 16 * i])
        size = width or 256
        body = data[offset:offset + length]
        if body.startswith(_PNG_SIGNATURE):
            _w, _h, rgba = decode_png(body)
            entries.append((size, "png", rgba))
            continue
        header_size, bmp_width, bmp_height, _planes, bits = struct.unpack("<IiiHH", body[:16])
        if bits != 32 or bmp_width != size or bmp_height != 2 * size:
            raise IconError(f"entry {i}: only 32-bit {size} px bitmaps are read")
        pixels = body[header_size:header_size + 4 * size * size]
        rgba = bytearray()
        for y in range(size - 1, -1, -1):
            for x in range(size):
                b, g, r, a = pixels[(y * size + x) * 4:(y * size + x) * 4 + 4]
                rgba += bytes((r, g, b, a))
        entries.append((size, "bmp", bytes(rgba)))
    return entries


def render_app_pngs(folder: Path, sizes=ICO_SIZES) -> list[Path]:
    """Renders the application icon (``spacemissionstudio.gui.icons``,
    needs PySide6) as one PNG per size into ``folder``."""
    from spacemissionstudio.gui.icons import _render

    paths = []
    for size in sizes:
        path = folder / f"spacemissionstudio-{size}.png"
        if not _render(size).save(str(path), "PNG"):
            raise OSError(f"could not render the icon at {size} px")
        paths.append(path)
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("output", type=Path, help="the .ico file to write")
    parser.add_argument("pngs", type=Path, nargs="*", help="square PNG files, 256 px at most")
    parser.add_argument("--from-app", action="store_true",
                        help=f"render the application icon at {', '.join(map(str, ICO_SIZES))} px instead")
    args = parser.parse_args(argv)
    if args.from_app == bool(args.pngs):
        parser.error("give either PNG files or --from-app")
    with tempfile.TemporaryDirectory() as folder:
        paths = render_app_pngs(Path(folder)) if args.from_app else args.pngs
        data = build_ico([path.read_bytes() for path in paths])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    print(f"{args.output}: {len(data)} bytes, {len(paths)} sizes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
