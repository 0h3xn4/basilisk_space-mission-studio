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

"""The template catalog (``spacemissionstudio/scenarios/catalog.py``,
decision TC-1): every template file in the folder has exactly one entry,
every entry names a file that is there, and the two lists of the
templates in the documentation (the catalog in ``templates/README.md`` and
the User Manual's "Which template next?") follow its categories and order.
"""

import re
from pathlib import Path

from spacemissionstudio.scenarios import catalog

_ROOT = Path(__file__).resolve().parent.parent
_README = catalog.TEMPLATES_DIR / "README.md"
_MANUAL = _ROOT / "USER_MANUAL.md"


def test_every_template_file_has_exactly_one_catalog_entry():
    """A template file without an entry fails here, with what to do."""
    names = [entry.file_name for entry in catalog.entries()]
    files = [path.name for path in catalog.template_files()]
    missing = [name for name in files if name not in names]
    assert not missing, (f"Template file(s) {missing} have no catalog entry: add each one to "
                         "spacemissionstudio/scenarios/catalog.py, in the files of its category, at its place "
                         "from simple to advanced (docs/DECISIONS.md, TC-1).")
    twice = sorted({name for name in names if names.count(name) > 1})
    assert not twice, f"Template file(s) {twice} have more than one entry in spacemissionstudio/scenarios/catalog.py."


def test_every_catalog_entry_names_an_existing_template_file():
    """An entry for a file that is not in the folder (a typing error, a
    renamed or removed template) fails here."""
    files = {path.name for path in catalog.template_files()}
    unknown = [entry.file_name for entry in catalog.entries() if entry.file_name not in files]
    assert not unknown, (f"spacemissionstudio/scenarios/catalog.py names {unknown}, which are not in "
                         f"{catalog.TEMPLATES_DIR}: correct or remove the entries.")


def test_the_templates_folder_holds_only_scenarios():
    """The loaders read every ``*.json`` file in the folder as a template:
    the catalog is Python, not a file there, and the folder holds the
    templates and their README only."""
    others = sorted(path.name for path in catalog.TEMPLATES_DIR.iterdir()
                    if path.suffix != ".json" and path.name != "README.md" and path.name != "__pycache__")
    assert others == []
    assert all(re.fullmatch(r"\d{2}_[a-z0-9_]+\.json", path.name) for path in catalog.template_files())


def test_the_categories_have_a_title_a_line_and_templates():
    """The categories: each with a unique key and title, a one-line
    description that ends with a full stop, and at least one template."""
    keys = [category.key for category in catalog.CATEGORIES]
    titles = [category.title for category in catalog.CATEGORIES]
    assert len(set(keys)) == len(keys) and len(set(titles)) == len(titles)
    assert titles[0] == "Getting started"
    for category in catalog.CATEGORIES:
        assert category.files, category.title
        assert "\n" not in category.description and category.description.endswith("."), category.title
        assert len(category.description) <= 90, category.title  # one line on Home
    assert catalog.OTHER.key not in keys


def test_order_and_groups_follow_the_catalog_and_put_unknown_files_last(tmp_path):
    """:func:`catalog.ordered` and :func:`catalog.grouped` give the catalog
    order whatever order the files come in; a file with no entry is last,
    in the "Other templates" group."""
    files = [tmp_path / name for name in ("99_new_template.json", "01_two_body_circular_orbit.json",
                                          "31_eros_landmark_navigation.json", "22_starter_first_leo_satellite.json")]
    assert [path.name[:2] for path in catalog.ordered(files)] == ["22", "01", "31", "99"]
    groups = catalog.grouped(files)
    assert [category.title for category, _paths in groups] == [
        "Getting started", "Deep space and navigation", "Other templates"]
    assert [[path.name[:2] for path in paths] for _category, paths in groups] == [["22", "01"], ["31"], ["99"]]
    assert catalog.category_of("99_new_template.json") is catalog.OTHER
    assert catalog.entry("22_starter_first_leo_satellite.json").number == "22"
    assert catalog.entry("22_starter_first_leo_satellite.json").position == 0


def _readme_catalog() -> list[tuple[str, str, list[str]]]:
    """``(heading, its line, [file names in its table])`` for each "###"
    heading of the README's "## Catalog" section, in order."""
    text = _README.read_text(encoding="utf-8")
    section = text.split("\n## Catalog\n", 1)[1].split("\n## ", 1)[0]
    groups = []
    for block in section.split("\n### ")[1:]:
        lines = block.splitlines()
        description = next(line for line in lines[1:] if line.strip())
        files = re.findall(r"^\| (\d{2}) \| `([^`]+\.json)` \|", block, flags=re.MULTILINE)
        assert all(file_name.startswith(number + "_") for number, file_name in files), lines[0]
        groups.append((lines[0].strip(), description.strip(), [file_name for _number, file_name in files]))
    return groups


def test_the_readme_catalog_is_grouped_and_ordered_as_the_catalog():
    """The README's catalog has a heading per category, in order, with the
    category's line under it and a table of its templates in its order
    (the numbers kept), and nothing else."""
    expected = [(category.title, category.description, list(category.files)) for category in catalog.CATEGORIES]
    assert _readme_catalog() == expected, ("spacemissionstudio/scenarios/templates/README.md's catalog does not "
                                           "follow spacemissionstudio/scenarios/catalog.py: give each category its "
                                           "heading, its line and its templates in the catalog's order.")


def test_the_manuals_template_table_follows_the_catalog():
    """The User Manual's "Which template next?" table lists the categories
    in order, each with its templates' numbers in the catalog's order."""
    text = _MANUAL.read_text(encoding="utf-8")
    section = text.split("### Which template next?", 1)[1].split("\n#", 1)[0]
    rows = re.findall(r"^\| ([^|]+?) \| ([0-9, ]+) \|", section, flags=re.MULTILINE)
    expected = [(category.title, [catalog.template_number(name) for name in category.files])
                for category in catalog.CATEGORIES]
    assert [(title, numbers.split(", ")) for title, numbers in rows] == expected
