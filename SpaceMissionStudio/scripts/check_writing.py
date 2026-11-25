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
"""Check Markdown files against the writing standard
(``docs/developer/writing-style.md``, decision DOC-1).

For each file it reports:

* a sentence that is too long: a procedure sentence (in a numbered list,
  or one that starts with an imperative verb) over 20 words, any other
  sentence over 25 words;
* a paragraph of more than six sentences;
* a word of the standard's "Words not to use" table;
* a path in the app written with ">" instead of "›".

It does not check code blocks, code spans, tables (for length), headings
(for length), HTML lines, block quotes (quoted text), lines that hold only
links, the lines between ``<!-- check-writing: off -->`` and
``<!-- check-writing: on -->`` (examples of what not to write), and a
file's text from the heading "# Original Basilisk README" down
(Basilisk's README in the root README).

Usage::

    python scripts/check_writing.py FILE.md [FILE.md ...]

The exit status is 1 when it finds a problem, else 0.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

STANDARD = Path(__file__).resolve().parent.parent / "docs" / "developer" / "writing-style.md"
PROCEDURE_LIMIT = 20  # [words]
DESCRIPTION_LIMIT = 25  # [words]
PARAGRAPH_LIMIT = 6  # [sentences]
STOP_HEADING = "# Original Basilisk README"
OFF, ON = "<!-- check-writing: off -->", "<!-- check-writing: on -->"

# Verbs that start a step. A sentence that starts with one is a procedure sentence.
IMPERATIVES = frozenset("""
add allow open click close choose copy download double-click drag enter fetch find go install
press put read remove rename run save see select set start stop switch tick type use write
activate build change check clear connect delete do edit export import keep leave let look make
move pick quit replace report restart show sort take try turn update upgrade wait
""".split())
# Abbreviations whose full stop does not end a sentence.
ABBREVIATIONS = frozenset({"e.g", "i.e", "etc", "vs", "sec", "no", "fig", "dr", "approx", "cf", "eq", "art",
                           "st", "mr", "ms", "v"})

_FENCE = re.compile(r"^\s*(```|~~~)")
_CODE_SPAN = re.compile(r"`[^`]*`")
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_REF_LINK = re.compile(r"\[([^\]]*)\]\[[^\]]*\]")
_AUTOLINK = re.compile(r"<https?://[^>]*>")
_BARE_URL = re.compile(r"https?://\S+")
_LIST_ITEM = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+")
_NUMBERED = re.compile(r"^\s*\d+[.)]\s+")
_WORD = re.compile(r"[A-Za-z0-9]")
_ARROW_PATH = re.compile(r"\S\s>\s\S")


@dataclass(frozen=True)
class Finding:
    """One problem: the file, its line (1-based) and what is wrong."""

    path: Path
    line: int
    message: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.message}"


def banned_words(standard: Path = STANDARD) -> dict[str, str]:
    """The "Words not to use" table of the standard: each variant (lower
    case) with what to use instead."""
    text = standard.read_text(encoding="utf-8")
    section = text.split("\n## Words not to use\n", 1)[1].split("\n## ", 1)[0].split("\n---", 1)[0]
    words: dict[str, str] = {}
    for line in section.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 2 or cells[0] in ("Do not use", "") or set(cells[0]) <= {"-"}:
            continue
        for variant in cells[0].split(","):
            if variant.strip():
                words[variant.strip().lower()] = cells[1]
    return words


def _plain(text: str) -> str:
    """The text as read: links as their text, code spans as one word, no
    emphasis marks."""
    text = _IMAGE.sub(" ", text)
    text = _CODE_SPAN.sub("CODE", text)
    text = _LINK.sub(r"\1", text)
    text = _REF_LINK.sub(r"\1", text)
    text = _AUTOLINK.sub("URL", text)
    text = _BARE_URL.sub("URL", text)
    return text.replace("**", "").replace("__", "").replace("*", "")


def _without_code(text: str) -> str:
    """The text with its code spans and link targets removed, for the
    word checks."""
    text = _CODE_SPAN.sub(" ", text)
    text = _IMAGE.sub(" ", text)
    text = _LINK.sub(r" \1 ", text)
    text = _AUTOLINK.sub(" ", text)
    return _BARE_URL.sub(" ", text)


def _sentences(text: str, *, at_semicolons: bool) -> list[str]:
    """Split plain text into sentences at ".", "?", "!" followed by a
    space (and at ";" when asked), not after an abbreviation or a single
    capital letter."""
    sentences, start = [], 0
    marks = ".?!;" if at_semicolons else ".?!"
    for match in re.finditer(r"[" + re.escape(marks) + r"](?=[\s)\"'*]|$)", text):
        end = match.end()
        if match.group() == ".":
            before = re.search(r"(?<![\w'’])([A-Za-z.]+)\.$", text[start:end])
            word = before.group(1) if before else ""
            if (word.lower() in ABBREVIATIONS or re.fullmatch(r"[A-Z]", word)
                    or re.fullmatch(r"([A-Za-z]\.)+[A-Za-z]", word)):
                continue
        sentences.append(text[start:end].strip())
        start = end
    rest = text[start:].strip()
    if rest:
        sentences.append(rest)
    return [sentence for sentence in sentences if _WORD.search(sentence)]


def _word_count(sentence: str) -> int:
    return sum(1 for token in sentence.split() if _WORD.search(token))


def _is_procedure(sentence: str, numbered: bool) -> bool:
    if numbered:
        return True
    first = re.sub(r"^[^A-Za-z]+", "", sentence).split(" ", 1)[0].lower().strip(",:")
    return first in IMPERATIVES


def _link_only(line: str) -> bool:
    """A line of links and separators only ("**Next:** [A](a.md) · [B](b.md)")."""
    rest = _AUTOLINK.sub(" ", _LINK.sub(" ", _IMAGE.sub(" ", line)))
    rest = re.sub(r"\*\*Next:\*\*|[·|*_:;,.()\s-]", " ", rest)
    return _word_count(rest) <= 1


def _blocks(lines: list[str]):
    """(first line number, numbered, [lines]) of each prose block: a
    paragraph or a list item with its continuation lines."""
    block: list[str] = []
    first, numbered, fenced = 0, False, False

    def flush():
        nonlocal block
        if block:
            yield first, numbered, block
        block = []

    for number, raw in enumerate(lines, start=1):
        line = raw.rstrip()
        if _FENCE.match(line):
            yield from flush()
            fenced = not fenced
            continue
        stripped = line.strip()
        if fenced or not stripped:
            yield from flush()
            continue
        if (stripped.startswith(("#", "|", ">", "<", "![", "[![")) or set(stripped) <= {"-", "=", "*", "_"}
                or _link_only(stripped) or raw.startswith("    ") and not block):
            yield from flush()
            continue
        if _LIST_ITEM.match(line):
            yield from flush()
            first, numbered = number, bool(_NUMBERED.match(line))
            block = [_LIST_ITEM.sub("", line)]
            continue
        if not block:
            first, numbered = number, False
        block.append(stripped)
    yield from flush()


def _checked_lines(path: Path) -> list[str]:
    """The file's lines up to the Basilisk README, if it has one, with the
    lines between ``<!-- check-writing: off -->`` and
    ``<!-- check-writing: on -->`` blanked (examples of what not to write)."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if STOP_HEADING in lines:
        lines = lines[:lines.index(STOP_HEADING)]
    checked, on = [], True
    for line in lines:
        if line.strip() == OFF:
            on = False
        elif line.strip() == ON:
            on = True
        checked.append(line if on else "")
    return checked


def _word_findings(path: Path, lines: list[str], words: dict[str, str]) -> list[Finding]:
    """Banned words and ">" paths, in every line but code and block quotes."""
    findings, fenced = [], False
    patterns = {word: re.compile(r"(?<![\w-])" + re.escape(word).replace(r"\ ", r"\s+") + r"(?![\w-])",
                                 re.IGNORECASE) for word in words}
    for number, raw in enumerate(lines, start=1):
        if _FENCE.match(raw):
            fenced = not fenced
            continue
        if fenced or raw.lstrip().startswith((">", "<")):
            continue
        text = _without_code(raw)
        for word, pattern in patterns.items():
            if pattern.search(text):
                findings.append(Finding(path, number, f'"{word}": use {words[word]}'))
        if _ARROW_PATH.search(text.replace("->", " ")):
            findings.append(Finding(path, number, 'a path written with ">": write "›", as the app does'))
    return findings


def check_file(path: Path, words: dict[str, str] | None = None) -> list[Finding]:
    """Every problem of one Markdown file."""
    path = Path(path)
    words = banned_words() if words is None else words
    lines = _checked_lines(path)
    findings = _word_findings(path, lines, words)
    for first, numbered, block in _blocks(lines):
        text = _plain(" ".join(block))
        for sentence in _sentences(text, at_semicolons=True):
            count = _word_count(sentence)
            procedure = _is_procedure(sentence, numbered)
            limit = PROCEDURE_LIMIT if procedure else DESCRIPTION_LIMIT
            if count > limit:
                kind = "procedure" if procedure else "description"
                findings.append(Finding(path, first, f"{kind} sentence of {count} words (limit {limit}): "
                                                     f'"{sentence[:70]}..."'))
        count = len(_sentences(text, at_semicolons=False))
        if count > PARAGRAPH_LIMIT:
            findings.append(Finding(path, first, f"paragraph of {count} sentences (limit {PARAGRAPH_LIMIT})"))
    return sorted(findings, key=lambda finding: finding.line)


def main(argv: list[str] | None = None) -> int:
    paths = [Path(arg) for arg in (sys.argv[1:] if argv is None else argv)]
    if not paths:
        print(__doc__)
        return 2
    words = banned_words()
    findings = [finding for path in paths for finding in check_file(path, words)]
    for finding in findings:
        print(finding)
    print(f"{len(findings)} problem(s) in {len(paths)} file(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
