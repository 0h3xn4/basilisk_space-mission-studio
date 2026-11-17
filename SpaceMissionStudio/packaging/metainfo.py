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

"""Writes the AppStream metadata of the ``.deb``
(``/usr/share/metainfo/io.github._0h3xn4.SpaceMissionStudio.metainfo.xml``)
from its template, ``packaging/linux/<id>.metainfo.xml.in``.

``packaging/build_deb.sh`` runs it::

    python3 packaging/metainfo.py --version 2.12.0 --out <file>

It fills ``@VERSION@`` (the screenshot addresses point at the release's
tag) and ``@RELEASES@``: the newest :data:`RELEASES_SHOWN` sections
``## X.Y.Z (YYYY-MM-DD)`` of ``CHANGELOG.md``, each with the first
paragraph of its summary as plain text and a link to its release page.
An ``## Unreleased`` section is left out.

Software centres read the file; SpaceMissionStudio never does. Standard
library only: the build runs it with the system's Python.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
COMPONENT_ID = "io.github._0h3xn4.SpaceMissionStudio"
TEMPLATE = ROOT / "packaging" / "linux" / f"{COMPONENT_ID}.metainfo.xml.in"
#: Where the .deb installs the file.
INSTALLED_PATH = f"usr/share/metainfo/{COMPONENT_ID}.metainfo.xml"
#: How many releases the file lists, newest first.
RELEASES_SHOWN = 5

_HEADING = re.compile(r"^## (\d+\.\d+\.\d+) \((\d{4}-\d{2}-\d{2})\)\s*$", re.MULTILINE)


def _release_notes():
    spec = importlib.util.spec_from_file_location("release_notes", Path(__file__).with_name("release_notes.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def changelog_releases(changelog: str) -> list[tuple[str, str]]:
    """(version, date) of each ``## X.Y.Z (date)`` section, newest first."""
    return _HEADING.findall(changelog)


def plain_text(markdown: str) -> str:
    """Markdown inline markup as plain text: links keep their text,
    emphasis and code marks go."""
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", markdown)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"(?<![\w*])\*([^*\s][^*]*)\*(?![\w*])", r"\1", text)
    return " ".join(text.split())


def release_summary(changelog: str, version: str) -> str:
    """The first paragraph of the summary of ``version``'s CHANGELOG section, as plain text."""
    summary = _release_notes().changelog_section(changelog, version)["summary"]
    return plain_text(summary.split("\n\n")[0])


def releases_xml(changelog: str, shown: int = RELEASES_SHOWN) -> str:
    """The ``<release>`` elements of the newest ``shown`` releases."""
    repository = _release_notes().REPOSITORY_URL
    out = []
    for version, date in changelog_releases(changelog)[:shown]:
        summary = release_summary(changelog, version)
        out.append(
            f'    <release version="{version}" date="{date}">\n'
            f'      <url type="details">{repository}/releases/tag/spacemissionstudio-v{version}</url>\n'
            f"      <description>\n"
            f"        <p>{escape(summary)}</p>\n"
            f"      </description>\n"
            f"    </release>")
    return "\n".join(out)


def render(version: str, changelog: str, template: str) -> str:
    """The metadata for ``version``."""
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError(f"not a version X.Y.Z: {version!r}")
    return template.replace("@VERSION@", version).replace("@RELEASES@", releases_xml(changelog))


def current_version(root: Path = ROOT) -> str:
    """``__version__`` of the checkout, read from ``spacemissionstudio/__init__.py``."""
    text = (root / "spacemissionstudio" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__ = "([^"]+)"', text, re.MULTILINE)
    if match is None:
        raise ValueError("no __version__ in spacemissionstudio/__init__.py")
    return match.group(1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the AppStream metadata of the .deb.")
    parser.add_argument("--version", help="the release (default: the checkout's __version__)")
    parser.add_argument("--out", type=Path, required=True, help="the file to write")
    args = parser.parse_args(argv)
    version = args.version or current_version()
    text = render(version, (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), TEMPLATE.read_text(encoding="utf-8"))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
