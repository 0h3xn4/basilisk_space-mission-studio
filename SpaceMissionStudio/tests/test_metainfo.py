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

"""The AppStream metadata of the .deb (packaging/metainfo.py and its
template packaging/linux/io.github._0h3xn4.SpaceMissionStudio.metainfo.xml.in):
rendered for the current version, it is well-formed, has what software
centres need, lists the CHANGELOG's releases and points at screenshots
that exist."""

import importlib.util
import re
import shutil
import struct
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("metainfo", _ROOT / "packaging" / "metainfo.py")
metainfo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(metainfo)

_REPOSITORY = "https://github.com/0h3xn4/basilisk_space-mission-studio"
_RAW = "https://raw.githubusercontent.com/0h3xn4/basilisk_space-mission-studio"


@pytest.fixture(scope="module")
def version():
    return metainfo.current_version()


@pytest.fixture(scope="module")
def changelog():
    return (_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def rendered(version, changelog):
    return metainfo.render(version, changelog, metainfo.TEMPLATE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def component(rendered):
    return ET.fromstring(rendered.encode("utf-8"))


def test_the_metadata_is_well_formed_and_complete(rendered, component, version):
    """Well-formed XML, every placeholder filled, and the tags a software
    centre needs: the id of the owner's answer Q4, name, summary, the
    metadata and project licences, developer, description, the desktop
    entry it launches, the command it provides, homepage and bug tracker,
    the age rating and the releases."""
    assert not re.search(r"@[A-Z]+@", rendered)
    assert component.tag == "component" and component.get("type") == "desktop-application"
    assert component.findtext("id") == "io.github._0h3xn4.SpaceMissionStudio" == metainfo.COMPONENT_ID
    assert component.findtext("name") == "SpaceMissionStudio"
    summary = component.findtext("summary")
    assert summary and len(summary) <= 80 and not summary.endswith(".")
    assert component.findtext("metadata_license") == "CC0-1.0"
    assert component.findtext("project_license") == "EUPL-1.2"
    developer = component.find("developer")
    assert developer is not None and developer.get("id") and developer.findtext("name")
    paragraphs = component.findall("description/p")
    assert len(paragraphs) >= 2 and all(len(p.text.split()) >= 10 for p in paragraphs)
    assert component.find("content_rating").get("type") == "oars-1.1"
    assert list(component.find("content_rating")) == []  # no content of any kind: every attribute "none"
    urls = {url.get("type"): url.text for url in component.findall("url")}
    assert urls["homepage"] == _REPOSITORY and urls["bugtracker"] == f"{_REPOSITORY}/issues"
    assert component.find("releases") is not None


def test_the_licence_is_the_eupl_as_the_licence_file_says():
    """project_license is EUPL-1.2, the licence of LICENSE and pyproject.toml."""
    template = metainfo.TEMPLATE.read_text(encoding="utf-8")
    assert "<project_license>EUPL-1.2</project_license>" in template
    assert (_ROOT / "LICENSE").read_text(encoding="utf-8").startswith("EUROPEAN UNION PUBLIC LICENCE v. 1.2")
    assert re.search(r'^license = "EUPL-1.2"', (_ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.MULTILINE)


def test_it_launches_the_desktop_entry_and_provides_the_command(component):
    """The launchable is the .deb's desktop entry (the name gui/app.py sets
    and dock favourites store); the binary is the .deb's command."""
    launchable = component.find("launchable")
    assert launchable.get("type") == "desktop-id"
    assert (_ROOT / "packaging" / "deb" / "usr" / "share" / "applications" / launchable.text).is_file()
    binary = component.findtext("provides/binary")
    assert (_ROOT / "packaging" / "deb" / "usr" / "bin" / binary).is_file()


def test_the_releases_are_the_newest_changelog_sections(component, changelog):
    """The release list is the newest CHANGELOG sections, in order, with
    their dates, each with its summary's first paragraph as plain text and
    a link to its release page."""
    headings = re.findall(r"^## (\d+\.\d+\.\d+) \((\d{4}-\d{2}-\d{2})\)$", changelog, re.MULTILINE)
    releases = component.findall("releases/release")
    assert [(r.get("version"), r.get("date")) for r in releases] == headings[:metainfo.RELEASES_SHOWN]
    assert len(releases) == min(len(headings), metainfo.RELEASES_SHOWN) >= 1
    for release in releases:
        text = release.findtext("description/p")
        assert text and len(text.split()) >= 10
        assert not re.search(r"\*\*|`|\]\(", text), text  # no Markdown left
        section = changelog.split(f"## {release.get('version')} (", 1)[1]
        assert text.split()[0] in section.split("\n\n", 1)[1]
        assert release.findtext("url") == f"{_REPOSITORY}/releases/tag/spacemissionstudio-v{release.get('version')}"


def test_an_unreleased_section_is_left_out(version):
    """Entries not yet released are not a release."""
    changelog = "# Changelog\n\n## Unreleased\n\n- Next.\n\n## 1.1.0 (2026-01-02)\n\nA summary of eleven words that says what this release brings.\n"
    out = metainfo.render(version, changelog, "<releases>\n@RELEASES@\n</releases>")
    assert '<release version="1.1.0" date="2026-01-02">' in out and "Unreleased" not in out


def _png_size(path):
    with path.open("rb") as handle:
        head = handle.read(24)
    assert head.startswith(b"\x89PNG\r\n\x1a\n"), path
    return struct.unpack(">II", head[16:24])


def test_the_screenshots_exist_and_are_pinned_to_the_release_tag(component, version):
    """3 to 5 screenshots, one the default, each with a caption, at the
    release's tag on raw.githubusercontent.com, of a file that exists in
    docs/images with the width and height the file has."""
    screenshots = component.findall("screenshots/screenshot")
    assert 3 <= len(screenshots) <= 5
    assert [s.get("type") for s in screenshots].count("default") == 1
    prefix = f"{_RAW}/spacemissionstudio-v{version}/SpaceMissionStudio/"
    for screenshot in screenshots:
        caption = screenshot.findtext("caption")
        assert caption and not caption.endswith(".")
        image = screenshot.find("image")
        assert image.text.startswith(prefix), image.text
        path = _ROOT / image.text.removeprefix(prefix)
        assert path.parent == _ROOT / "docs" / "images" and path.is_file(), path
        assert _png_size(path) == (int(image.get("width")), int(image.get("height")))


def test_the_metainfo_file_name_is_the_component_id():
    """AppStream finds the file by the id: <id>.metainfo.xml in /usr/share/metainfo."""
    assert metainfo.INSTALLED_PATH == "usr/share/metainfo/io.github._0h3xn4.SpaceMissionStudio.metainfo.xml"
    build_deb = (_ROOT / "packaging" / "build_deb.sh").read_text(encoding="utf-8")
    assert f'"$staging/{metainfo.INSTALLED_PATH}"' in build_deb
    assert 'metainfo.py" --version "$version"' in build_deb


def test_the_command_line_writes_the_file(tmp_path, version):
    out = tmp_path / "x" / "app.metainfo.xml"
    assert metainfo.main(["--out", str(out)]) == 0
    assert ET.parse(out).getroot().findtext("id") == metainfo.COMPONENT_ID
    assert f"spacemissionstudio-v{version}/" in out.read_text(encoding="utf-8")
    with pytest.raises(ValueError):
        metainfo.render("2.x", "", "")


@pytest.mark.skipif(shutil.which("appstreamcli") is None, reason="appstreamcli is not installed (CI runs it)")
def test_appstreamcli_accepts_it(tmp_path, rendered):
    """appstreamcli validate --no-net passes (it fails on a warning)."""
    path = tmp_path / f"{metainfo.COMPONENT_ID}.metainfo.xml"
    path.write_text(rendered, encoding="utf-8")
    result = subprocess.run(["appstreamcli", "validate", "--no-net", "--explain", str(path)],  # noqa: S603, S607
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
