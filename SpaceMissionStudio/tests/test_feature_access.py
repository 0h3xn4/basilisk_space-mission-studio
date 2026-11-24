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

"""The feature-access page (``docs/reference/feature-access.md``, decision
FA-1) stays true without the GUI: every command-line command and flag has
its row, every link and test it names exists, its counts are right, and
every scenario field has a form field or a reason on the page's list
(FA-7). ``tests/gui/test_feature_access_gui.py`` checks the commands."""

import argparse
import dataclasses
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_PAGE = _ROOT / "docs" / "reference" / "feature-access.md"
_STATUSES = ("OK", "Fixed", "Backlog", "CLI only")

# Scenario fields whose names are not in the GUI code, each with its reason (the page's table
# "Scenario fields without a form" says the same to a reader).
_WITHOUT_FORM = {
    # The operations section is edited in Scenario › JSON (backlog: a form, about 24 hours).
    ("OperationsConfig", "activity_types"), ("OperationsConfig", "requests"), ("OperationsConfig", "scheduler"),
    ("OperationsConfig", "what_if"), ("SchedulerConfig", "objective"), ("SchedulerConfig", "weights"),
    ("SchedulerConfig", "priority_weights"), ("SchedulerConfig", "improvement_iterations"),
    ("VerificationConfig", "soc_points"), ("VerificationConfig", "memory_fraction"),
    ("VerificationConfig", "sun_elevation_deg"),
    # A record the flight-software export writes, not an input.
    ("FswExportRecord", "config_digest"), ("FswExportRecord", "exported_utc"),
    ("FswExportRecord", "basilisk_revision"),
    # The Navigation error group makes its fields from the channel list (schema.scenario._NAV_CHANNELS).
    ("NavigationErrorConfig", "attitude_step_deg"), ("NavigationErrorConfig", "rate_step_deg_s"),
    ("NavigationErrorConfig", "sun_step_deg"), ("NavigationErrorConfig", "sun_bound_deg"),
    ("NavigationErrorConfig", "position_step_m"), ("NavigationErrorConfig", "position_bound_m"),
    ("NavigationErrorConfig", "velocity_step_m_s"), ("NavigationErrorConfig", "velocity_bound_m_s"),
}


def _sections() -> dict[str, list[list[str]]]:
    """Each "## " section's table rows, as lists of cells (no header, no rule)."""
    sections: dict[str, list[list[str]]] = {}
    title = ""
    for line in _PAGE.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            title = line[3:].strip()
            sections[title] = []
            header = True
        elif line.startswith("| ") and title:
            if line.startswith("|---"):
                continue
            if header:
                header = False
                continue
            sections[title].append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return sections


def _cli_commands() -> dict[str, list[str]]:
    """Every command (and ``plan`` action) of the command line with its ``--`` flags."""
    from spacemissionstudio import cli

    def subcommands(parser):
        return next((a.choices for a in parser._actions if isinstance(a, argparse._SubParsersAction)), {})

    def flags(parser):
        return [o for a in parser._actions for o in a.option_strings if o.startswith("--") and o != "--help"]

    found = {}
    for name, parser in subcommands(cli.build_parser()).items():
        inner = subcommands(parser)
        for action, sub in inner.items():
            found[f"{name} {action}"] = flags(sub)
        if not inner:
            found[name] = flags(parser)
    return found


def test_every_command_line_command_and_flag_has_its_row():
    """A new command, or a new flag, needs its place on the page: where a
    user of the app does the same, or why it is for the command line only."""
    rows = {row[0].strip("`"): row for row in _sections()["CLI"]}
    commands = _cli_commands()
    assert sorted(set(commands) - set(rows)) == []
    assert sorted(set(rows) - set(commands)) == []
    for command, flags in commands.items():
        listed = re.findall(r"`(--[a-z0-9-]+)`", rows[command][1])
        assert sorted(listed) == sorted(flags), command
        assert rows[command][2], command  # the app's counterpart, or "none" with the reason


def _table_rows():
    return [(title, row) for title, rows in _sections().items() for row in rows
            if title not in ("Summary", "How to read this page")]


def test_each_row_has_a_known_status_and_the_counts_add_up():
    """Every row's status is one of OK, Fixed, Backlog or CLI only (a
    Backlog or CLI only row says why), and the Summary counts them."""
    counts = dict.fromkeys(_STATUSES, 0)
    for title, row in _table_rows():
        status = row[-1]
        kind = next((s for s in _STATUSES if status.startswith(s)), None)
        assert kind is not None, (title, row[0])
        if kind in ("Backlog", "CLI only"):
            assert ":" in status, (title, row[0])
        if title != "Scenario fields without a form":
            counts[kind] += 1
    summary = {row[0]: int(row[1]) for row in _sections()["Summary"]}
    assert summary == counts | {"All": sum(counts.values())}


def _anchors(path: Path) -> set[str]:
    anchors = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        heading = re.match(r"^#{1,6} (.*)", line)
        if heading:
            text = re.sub(r"[^\w\- ]", "", heading.group(1).strip().lower())
            anchors.add(text.replace(" ", "-"))
    return anchors


def test_every_link_and_every_test_named_exists():
    """The manual sections and pages the page links to exist, with their
    headings; each test it names is there (``file::function``)."""
    text = _PAGE.read_text(encoding="utf-8")
    for target in re.findall(r"\]\(([^)]+)\)", text):
        if target.startswith(("http", "#")):
            continue
        file, _, anchor = target.partition("#")
        path = (_PAGE.parent / file).resolve()
        assert path.exists(), target
        if anchor:
            assert anchor in _anchors(path), target
    for name in set(re.findall(r"`(tests/[^`\s]+)`", text)):
        file, _, function = name.partition("::")
        path = _ROOT / file
        assert path.is_file(), name
        if function:
            assert re.search(rf"^def {re.escape(function)}\(", path.read_text(encoding="utf-8"), re.MULTILINE), name


def _gui_code() -> str:
    return "\n".join(path.read_text(encoding="utf-8")
                     for path in sorted((_ROOT / "spacemissionstudio" / "gui").rglob("*.py")))


def _scenario_fields():
    """(record, field) of every record the scenario file can hold, from ``Scenario`` down."""
    from spacemissionstudio.schema import fields as schema_fields
    from spacemissionstudio.schema.scenario import Scenario

    seen, found = set(), []

    def walk(cls):
        if cls in seen:
            return
        seen.add(cls)
        for field in dataclasses.fields(cls):
            found.append((cls.__name__, field.name))
            items = schema_fields.LIST_ITEMS.get((cls.__name__, field.name))
            for sub in (schema_fields.field_record(cls, field.name), schema_fields.record(items) if items else None):
                if sub is not None and dataclasses.is_dataclass(sub):
                    walk(sub)

    walk(Scenario)
    return found


def test_every_scenario_field_has_a_form_field_or_a_reason():
    """A field of the scenario file the GUI code never names has no form
    field: it is on the reasoned list, or it is a hidden feature. A field
    on the list that the GUI names now comes off it. (The GUI names a field
    as a string or an attribute: ``"dry_mass_kg"`` or ``.dry_mass_kg``.)"""
    code = _gui_code()
    named = {(record, field) for record, field in _scenario_fields()
             if re.search(r"[\"'.]" + re.escape(field) + r"\b", code)}
    without = {key for key in _scenario_fields() if key not in named}
    assert sorted(without - _WITHOUT_FORM) == []
    assert sorted(_WITHOUT_FORM - without) == []
    page = _PAGE.read_text(encoding="utf-8")
    for record, field in _WITHOUT_FORM:
        if record != "NavigationErrorConfig":  # named by its pattern on the page
            assert field in page, field
