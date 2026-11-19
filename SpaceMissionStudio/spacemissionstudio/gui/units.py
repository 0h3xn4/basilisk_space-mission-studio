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
"""Units as a field shows them (UI overhaul M4a): the code's ASCII
spelling ("m^2", "kg*m^2", "deg") as the suffix a number field carries
("m²", "kg·m²", "°").

Only the display changes. Field names in files, messages naming a field
("Drag area [m^2]", ``gui.field_text``) and every exported unit keep
their spelling.
"""

from __future__ import annotations

import re

# The units a form label may carry, and how a field shows each. A unit
# not listed here is left in its label: a bracket can hold other things
# (a JSON key, "lo, hi").
_DISPLAY = {
    "-": "",  # dimensionless: no suffix
    "deg": "°", "deg/s": "°/s", "rad": "rad", "rad/s": "rad/s", "rad/s^2": "rad/s²",
    "m": "m", "km": "km", "m^2": "m²", "m^3": "m³", "km^2": "km²",
    "m/s": "m/s", "km/s": "km/s", "m/s^2": "m/s²", "km/s^2": "km/s²", "m/s^1.5": "m/s^1.5",
    "s": "s", "ms": "ms", "min": "min", "h": "h", "hr": "h", "day": "days", "days": "days", "y": "years",
    "kg": "kg", "g": "g", "kg m^2": "kg·m²", "kg*m^2": "kg·m²", "kg/s": "kg/s",
    "N": "N", "mN": "mN", "N*m": "N·m", "N m": "N·m", "N*m*s": "N·m·s", "N m s": "N·m·s",
    "W": "W", "W/m^2": "W/m²", "W*hr": "Wh", "W*h": "Wh", "Wh": "Wh", "V": "V", "A": "A", "A*m^2": "A·m²", "A m^2": "A·m²",
    "T": "T", "nT": "nT", "K": "K", "degC": "°C", "deg C": "°C",
    "1/(N*m*s^2)": "1/(N·m·s²)",
    "Hz": "Hz", "GHz": "GHz", "MHz": "MHz", "1/s": "1/s", "1/s^2": "1/s²",
    "dB": "dB", "dBi": "dBi", "dBW": "dBW", "dB-Hz": "dB-Hz", "dBm": "dBm",
    "bit": "bit", "kbit/s": "kbit/s", "Mbit/s": "Mbit/s", "Gbit": "Gbit",
    "px": "px", "%": "%", "RPM": "RPM", "steps": "steps",
    "m^2/s^3 per kg": "m²/s³ per kg",
    "g/m^3": "g/m³", "m per (m^2/kg)": "m per (m²/kg)",
    "kW*h": "kWh", "g*cm^2": "g·cm²", "mN*m": "mN·m", "mN*m*s": "mN·m·s",
}

# "Name [unit]" or "Name [unit] (more)": the unit and the rest around it.
_LABEL_UNIT = re.compile(r"^(?P<name>.*?)\s*\[(?P<unit>[^\[\]]+)\]\s*(?P<rest>.*)$")


def display(unit: str) -> str | None:
    """How a field shows ``unit`` ("" for a dimensionless one), or None
    for a unit not known here."""
    return _DISPLAY.get(unit.strip())


def shown(unit: str) -> str:
    """``unit`` as the window shows it beside a value: its display form
    ("W*h" -> "Wh"), or the unit itself when it is not known here."""
    known = display(unit)
    return unit.strip() if known is None else known


def display_rows(rows) -> list[tuple[str, str, str]]:
    """The core's (label, value, unit) rows with each unit as shown, for a
    ``value_sheet.ValueSheet``."""
    return [(label, value, shown(unit)) for label, value, unit in rows]


def suffix(unit: str) -> str:
    """The suffix a number field carries for ``unit`` (by its display):
    "" for none, "°" right after the number, " km" after a space."""
    shown = display(unit)
    if shown is None:
        shown = unit.strip()
    if not shown:
        return ""
    return shown if shown in ("°", "°/s", "%") else f" {shown}"


def plot_unit(unit: str) -> str:
    """A plot's unit as its axis title and the readout show it: the display
    form ("deg" as "°", "N*m" as "N·m"), with "-" (dimensionless) kept, so
    an axis without a name still says "[-]"."""
    return unit if unit.strip() in ("", "-") else shown(unit)


def axis_title(name: str, unit: str) -> str | None:
    """A plot's value axis title: "Semi-major axis [km]", "[-]" without a name, or
    None with neither."""
    if name:
        return f"{name} [{plot_unit(unit)}]"
    return f"[{plot_unit(unit)}]" if unit else None


_BRACKETED = re.compile(r"\s*\[(?P<unit>[^\[\]]+)\]")


def label(text: str) -> str:
    """A heading or label as the window shows it: each "[unit]" of a known
    unit in its display form ("Field of view [deg]" -> "Field of view [°]",
    "Off-nadir [deg]" in a table's header), a dimensionless "[-]" left out.
    A bracket that is not a unit ("[deg, dBi]") stays as it is."""
    def shown_unit(match: re.Match) -> str:
        known = display(match.group("unit"))
        if known is None:
            return match.group(0)
        return f" [{known}]" if known else ""

    return _BRACKETED.sub(shown_unit, text)


def split_label(text: str) -> tuple[str, str | None]:
    """("Name (more)", "unit") for a label "Name [unit] (more)" with a known
    unit, else (text, None)."""
    match = _LABEL_UNIT.match(text)
    if match is None or display(match.group("unit")) is None:
        return text, None
    name, rest = match.group("name").strip(), match.group("rest").strip()
    return (f"{name} {rest}" if rest else name), match.group("unit").strip()


# -- the plots' units (transparency plan, Phase 8a) -----------------------------------------------

PLOT_UNITS_KEY = "appearance/plot_units"
# "Display units": altitudes, semi-major axes and distances in km, position in m and velocity and delta-V in
# m/s (the owner's rule, HISTORY "per-category unit policy"), angles in degrees, time in hours.
PLOT_UNITS = (("display", "Display units (altitudes in km, °, h)"), ("recorded", "As recorded (SI, as the CSV exports)"))


def _settings():
    from pathlib import Path

    from PySide6.QtCore import QSettings

    # The app's own settings file, as the appearance settings' (gui.theme.apply).
    return QSettings(str(Path.home() / ".spacemissionstudio" / "settings.ini"), QSettings.Format.IniFormat)


def plot_units() -> str:
    """"display" (the default) or "recorded": the units the plots show
    (``plot_categories.shown``)."""
    value = str(_settings().value(PLOT_UNITS_KEY, "display"))
    return value if value in dict(PLOT_UNITS) else "display"


def set_plot_units(value: str) -> None:
    if value not in dict(PLOT_UNITS):
        raise ValueError(f"plot units: one of {', '.join(dict(PLOT_UNITS))}, got {value!r}")
    settings = _settings()
    settings.setValue(PLOT_UNITS_KEY, value)
    settings.sync()
