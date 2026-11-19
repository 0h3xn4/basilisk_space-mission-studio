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
"""UI audit batch B4, the window's strings, read from the source (no Qt):
no double hyphen where a dash is meant (UI-34), and no unit in the code's
ASCII spelling ("deg", "W*h", "kg*m^2", "W/m^2") written by hand (UI-35):
the window shows units through ``gui/units.py`` ("°", "Wh", "kg·m²",
"W/m²"). As UI-43's test in ``tests/test_value_rows.py``, docstrings and
logging calls are not shown text and are skipped; comments are not
strings. Field names, JSON keys, the command line and the files keep
their spelling.
"""

import ast
import re
from pathlib import Path

_TOOL = Path(__file__).resolve().parent.parent
_GUI = _TOOL / "spacemissionstudio" / "gui"
_LOG_CALLS = {"debug", "info", "warning", "error", "exception", "log", "critical"}

# A double hyphen used as a dash: between spaces, or at a string's end after a space.
_DOUBLE_HYPHEN = re.compile(r"(?:^| )--(?: |$)")
# The code's ASCII spellings of units. A unit in a bracket ("Inclination [deg]") is a form label
# the form typesets (``widgets.units_into_fields``) or a table heading the table typesets
# (``units.label``), so brackets are left out of the search.
_ASCII_UNIT = re.compile(r"\bdeg(?:/s|C)?\b|\^[0-9]|\b(?:N|kg|W|A|J)\*(?:m|h|hr|s|K)\b|\bkg m\^|\bW\*hr?\b")
_BRACKET = re.compile(r"\[[^\[\]]*\]")
# A string that is only a unit (" deg", "kg*m^2") is data for units.py, unless it is joined
# into shown text or set as a suffix by hand.
_UNIT_ONLY = re.compile(r"^\s*[\w*^/()·.-]+\s*\.?$")


def _strings(path: Path):
    """(line, text, parent node) of each string constant of ``path`` that is
    not a docstring or in a logging call."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skipped, parents = set(), {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                skipped.add(id(first.value))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _LOG_CALLS:
            skipped.update(id(sub) for sub in ast.walk(node))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skipped:
            yield node.lineno, node.value, parents.get(id(node))


def _gui_modules():
    return sorted(_GUI.rglob("*.py"))


def test_no_double_hyphen_in_the_window_s_text():
    """UI-34: "--" where a dash is meant (" -- ", "SpaceMissionStudio --
    untitled", the dashboard's "--" for no value) is an en dash; the
    window's comments and docstrings are left alone."""
    found = [f"{path.name}:{line}: {text[:80]!r}" for path in _gui_modules()
             for line, text, _parent in _strings(path) if _DOUBLE_HYPHEN.search(text) or text == "--"]
    assert found == []


def test_the_manual_has_no_double_hyphen_outside_code():
    """UI-34: the user manual (and its copy in the help) writes an en dash;
    a command line in a code span or block keeps its "--" flags."""
    for manual in (_TOOL / "USER_MANUAL.md", _TOOL / "spacemissionstudio" / "help" / "USER_MANUAL.md"):
        fenced, found = False, []
        for number, line in enumerate(manual.read_text(encoding="utf-8").splitlines(), start=1):
            if re.match(r"^\s*(```|~~~)", line):
                fenced = not fenced
                continue
            prose = re.sub(r"`[^`]*`", "", line)
            if not fenced and _DOUBLE_HYPHEN.search(prose):
                found.append(f"{manual.name}:{number}: {line[:80]}")
        assert found == []


def test_no_unit_in_its_ascii_spelling_in_the_window_s_text():
    """UI-35: "0 deg = equatorial", "{x:.2f} deg", "kg m^2 on each
    diagonal element", "{capacity} W*h" read "0° = equatorial", "°",
    "kg·m²", "Wh". A unit alone is data for units.py, unless it is joined
    into shown text or is a suffix set by hand. units.py itself holds the
    spellings."""
    found = []
    for path in _gui_modules():
        if path.name == "units.py":
            continue
        for line, text, parent in _strings(path):
            if not _ASCII_UNIT.search(_BRACKET.sub("", text)):
                continue
            if _UNIT_ONLY.match(text):
                call = parent if isinstance(parent, ast.Call) else None
                name = call is not None and getattr(call.func, "attr", getattr(call.func, "id", ""))
                if not isinstance(parent, (ast.JoinedStr, ast.BinOp)) and name != "setSuffix":
                    continue
            found.append(f"{path.name}:{line}: {text[:80]!r}")
    assert found == []


def test_a_suffix_made_from_a_unit_goes_through_units():
    """UI-35: a spin box's suffix from a unit held in a variable (" deg" in
    a helper's argument) is ``units.suffix(unit)``, never the unit as it is
    (``box.setSuffix(suffix)``, ``setSuffix(f" {unit}")``); a constant
    suffix may be written (" km")."""
    found = []
    for path in _gui_modules():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not (isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "setSuffix" and node.args):
                continue
            arg = node.args[0]
            if isinstance(arg, ast.Constant):
                continue
            through_units = (isinstance(arg, ast.Call) and getattr(arg.func, "attr", getattr(arg.func, "id", ""))
                             in ("suffix", "display", "shown"))
            if not through_units:
                found.append(f"{path.name}:{node.lineno}: {ast.unparse(node)[:80]}")
    assert found == []
