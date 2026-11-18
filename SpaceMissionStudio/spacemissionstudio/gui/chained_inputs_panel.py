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
"""What an analysis takes from the last run, shown before it computes
(the transparency plan, Phase 8b, ``engine.chained_inputs``): a value
sheet titled with where the values come from, the run's start time in
ISO 8601 UTC with Z, then each value with its unit, its source in the
tooltip, and a caution when the scenario has changed since the run.
Never a sentence of numbers (UI audit UI-14)."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from . import units
from .run_history_view import parse_utc, utc_text
from .theme import set_role
from .value_sheet import ValueSheet

_SHOWN_CHANGES = 5  # the changes named in the caution's text; the tooltip has them all
STARTED = "Run started"  # the sheet's first row: when the run started


def _value_and_unit(quantity) -> tuple[str, str]:
    """``quantity``'s value as shown and its unit as shown ("" for none)."""
    value, unit = quantity.value, quantity.unit.strip("[]")
    if isinstance(value, str):
        return value, ""
    shown = units.display(unit)
    return f"{value:,.6g}", (shown if shown is not None else ("" if unit in ("", "-") else unit))


def started_text(started: str) -> str:
    """A run's start ("2026-11-17T18:49:48.737253+00:00") as ISO 8601 UTC
    with Z, to the second; the text as it is when it does not parse."""
    moment = parse_utc(started)
    return utc_text(moment) if moment is not None else str(started)


class ChainedInputsPanel(QWidget):
    """A sheet titled "From the end of the last run": when the run started,
    a caution when the scenario changed since, and one row per value."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.caution = set_role(QLabel(""), tone="caution")
        self.caution.setWordWrap(True)
        self.sheet = ValueSheet()
        layout.addWidget(self.sheet)
        layout.addWidget(self.caution)
        self.rows: dict[str, tuple[str, str]] = {}  # quantity name -> (value, unit) as shown
        self.setVisible(False)

    def show_inputs(self, heading: str, quantities, changes=(), error: str = "", started: str = "",
                    note: str = "") -> None:
        """``quantities`` (``engine.trace.Quantity``) under the title
        ``heading``, after the run's start time ``started`` (the
        provenance's ``run_started_utc``); ``note`` under them; ``changes``
        (path, as run, now) make the caution; ``error`` stands for the
        values when they cannot be read."""
        self.rows = {}
        if error:
            self.caution.setText(error)
            self.caution.setToolTip("")
        elif changes:
            named = ", ".join(path for path, _then, _now in list(changes)[:_SHOWN_CHANGES])
            more = f" and {len(changes) - _SHOWN_CHANGES} more" if len(changes) > _SHOWN_CHANGES else ""
            self.caution.setText(f"The scenario has changed since that run ({len(changes)} value"
                                 f"{'s' if len(changes) != 1 else ''}: {named}{more}): run it again for its "
                                 "results to be of this scenario.")
            self.caution.setToolTip("\n".join(f"{path}: {then!r} then, {now!r} now" for path, then, now in changes))
        else:
            self.caution.setText("")
            self.caution.setToolTip("")
        self.caution.setVisible(bool(self.caution.text()))
        rows, tips = ([(STARTED, started_text(started), "")], [""]) if started else ([], [])
        for quantity in quantities if not error else ():
            value, unit = _value_and_unit(quantity)
            rows.append((quantity.name[:1].upper() + quantity.name[1:], value, unit))
            tips.append(quantity.source)
            self.rows[quantity.name] = (value, unit)
        self.sheet.title_label.setText(heading)
        self.sheet.title_label.setVisible(bool(heading))
        self.sheet.note_label.setText(note)
        self.sheet.note_label.setVisible(bool(note))
        self.sheet.set_rows(rows, tips)
        self.setVisible(True)

    def value_text(self, name: str) -> str:
        """The value shown for quantity ``name`` with its unit ("0.1 kg"),
        "" when there is none."""
        value, unit = self.rows.get(name, ("", ""))
        return f"{value} {unit}".strip()

    def names(self) -> list[str]:
        """The names the sheet shows, in order."""
        return [name for name, _value, _unit in self.sheet.rows]

    def clear(self) -> None:
        self.setVisible(False)
