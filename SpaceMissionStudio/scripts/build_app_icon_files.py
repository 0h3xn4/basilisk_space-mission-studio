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
"""Write the app icon's committed files from ``gui/icons.py``.

The app draws its icon at run time; these copies are for places that
need a file before the app runs:

* ``packaging/windows/spacemissionstudio.ico``: the Windows setup
  program's shortcuts, its own icon and its uninstall entry;
* ``docs/images/app_icon.png``: the icon at 256 px for the documentation;
* ``docs/images/banner.svg``: the README banner, which carries the icon
  as an embedded PNG between its ``app-icon`` markers (an image the SVG
  links to would not show on GitHub).

``tests/gui/test_icons.py`` checks that the files exist and are valid.
Run this script after a change to the icon.

Usage::

    QT_QPA_PLATFORM=offscreen python scripts/build_app_icon_files.py
"""

from __future__ import annotations

import base64
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QBuffer, QIODevice  # noqa: E402

from spacemissionstudio.gui.icons import _render, write_ico  # noqa: E402

ICO = ROOT / "packaging" / "windows" / "spacemissionstudio.ico"
PNG = ROOT / "docs" / "images" / "app_icon.png"
BANNER = ROOT / "docs" / "images" / "banner.svg"
BANNER_ICON_PX = 256  # rendered size, shown at 128 for sharp high-DPI display
BANNER_MARKERS = re.compile(r"(<!-- app-icon -->).*?(<!-- /app-icon -->)", re.DOTALL)


def png_bytes(size: int) -> bytes:
    """The icon at ``size`` px as PNG data."""
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not _render(size).save(buffer, "PNG"):
        raise OSError(f"could not encode the {size} px icon")
    return bytes(buffer.data())


def main() -> int:
    write_ico(ICO)
    PNG.write_bytes(png_bytes(256))
    banner = BANNER.read_text(encoding="utf-8")
    if not BANNER_MARKERS.search(banner):
        raise SystemExit(f"{BANNER} has no <!-- app-icon --> markers")
    data = base64.b64encode(png_bytes(BANNER_ICON_PX)).decode("ascii")
    image = f'<image x="46" y="16" width="128" height="128" href="data:image/png;base64,{data}"/>'
    BANNER.write_text(BANNER_MARKERS.sub(lambda m: f"{m.group(1)}\n  {image}\n  {m.group(2)}", banner),
                      encoding="utf-8")
    for path in (ICO, PNG, BANNER):
        print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
