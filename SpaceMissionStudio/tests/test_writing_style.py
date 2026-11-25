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
"""The writing standard (``docs/developer/writing-style.md``, decision
DOC-1): the documents in :data:`CHECKED` pass ``scripts/check_writing.py``
(sentence length, paragraph length, the words not to use, "›" in paths).

A later rewrite adds its documents to :data:`CHECKED`, a group at a time.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_TOOL = Path(__file__).resolve().parent.parent
_REPO = _TOOL.parent

# Group 1, the first-contact documents (decision DOC-1). Paths relative to
# the SpaceMissionStudio folder; the root README is checked down to its
# "Original Basilisk README" heading.
GROUP_1 = (
    "../README.md",
    "README.md",
    "GETTING_STARTED.md",
    "docs/getting-started.md",
    "docs/faq.md",
    "docs/tips.md",
    "docs/troubleshooting.md",
    "docs/glossary.md",
    "docs/README.md",
    "docs/developer/writing-style.md",
    "examples/README.md",
    "spacemissionstudio/scenarios/templates/README.md",
    "packaging/README.md",
    "spacemissionstudio/data/spaceweather/README.md",
)
CHECKED = GROUP_1


def _checker():
    spec = importlib.util.spec_from_file_location("check_writing", _TOOL / "scripts" / "check_writing.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look the module up
    spec.loader.exec_module(module)
    return module


check_writing = _checker()


@pytest.mark.parametrize("document", CHECKED)
def test_the_document_follows_the_writing_standard(document):
    """Each checked document has no sentence over the limits, no paragraph
    of more than six sentences, no word of the "do not use" list and no
    path written with ">"."""
    findings = check_writing.check_file(_TOOL / document)
    assert [str(finding) for finding in findings] == []


def test_the_standard_lists_the_words_not_to_use():
    """The check reads its word list from the standard's table, with each
    variant on its own."""
    words = check_writing.banned_words()
    assert words["sidebar"] == "navigation rail" and words["nav bar"] == "navigation rail"
    assert "e.g." in words and "click on" in words


def test_the_check_finds_long_sentences_banned_words_and_arrow_paths(tmp_path):
    """A procedure step of 21 words, a description of 26 words, a banned
    word and a ">" path are each reported, on their line."""
    step = "1. " + " ".join(["Click"] + ["word"] * 20) + "."
    description = " ".join(["The"] + ["value"] * 25) + "."
    page = tmp_path / "page.md"
    page.write_text(f"# Title\n\n{step}\n\n{description}\n\nOpen the sidebar.\n\nGo to **Settings > About**.\n",
                    encoding="utf-8")
    messages = [(finding.line, finding.message.split(" (")[0].split(":")[0]) for finding in
                check_writing.check_file(page)]
    assert messages == [(3, "procedure sentence of 21 words"), (5, "description sentence of 26 words"),
                        (7, '"sidebar"'), (9, 'a path written with ">"')]


def test_the_check_skips_code_tables_quotes_links_and_the_basilisk_readme(tmp_path):
    """Code blocks, code spans, tables, block quotes, link-only lines, the
    lines between the off and on markers and the text under "# Original
    Basilisk README" are not checked."""
    long = " ".join(["word"] * 40) + "."
    page = tmp_path / "page.md"
    page.write_text("\n".join([
        "# Title", "", "```text", long, "```", "", f"| {long} | x |", "", f"> {long} sidebar", "",
        "**Next:** [One](one.md) · [Two](two.md)", "", "Use `a > b` and `e.g.` in code.", "",
        "<!-- check-writing: off -->", long, "<!-- check-writing: on -->", "",
        "# Original Basilisk README", "", long, "Open the sidebar.", ""]), encoding="utf-8")
    assert check_writing.check_file(page) == []


def test_abbreviations_and_version_numbers_do_not_end_a_sentence(tmp_path):
    """Abbreviations with a full stop and version numbers such as 2.16.0
    stay in their sentence; a full stop after a possessive version ends
    one."""
    page = tmp_path / "page.md"
    page.write_text("The guideline Sec. 5.9 and EUPL v. 1.2 and Dr. T.S. Kelso and 2.16.0 are here.\n",
                    encoding="utf-8")
    sentences = check_writing._sentences(page.read_text(encoding="utf-8"), at_semicolons=True)
    assert len(sentences) == 1
    assert len(check_writing._sentences("It is 2.14.1's. The next one.", at_semicolons=True)) == 2


def test_the_root_readme_keeps_the_basilisk_readme_below_its_heading():
    """The check stops at the Basilisk part of the root README, which stays
    as upstream wrote it."""
    lines = check_writing._checked_lines(_REPO / "README.md")
    text = (_REPO / "README.md").read_text(encoding="utf-8")
    assert "# Original Basilisk README" in text
    assert "<!-- BEGIN UPSTREAM README -->" not in lines
