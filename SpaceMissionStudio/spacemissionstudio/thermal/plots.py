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
"""The thermal analysis's plots as SVG text (decisions T-31 and T-40): the
temperatures of a case with a node's operating and survival bands, and a
node's heat flows by kind. Plain SVG, written here, so the same content is
on screen (Run › Thermal shows it), in an exported SVG and, rendered by Qt,
in an exported PNG; no plotting library and no browser are needed, and the
command line can write it too.

The defaults (900 x 420, white, DejaVu Sans, :data:`COLOURS`) make the
exported files. The screen copy passes its own size and a ``style``
(:data:`STYLE_KEYS`; the GUI takes it from its theme), so the same plot is
drawn at the view's size and in the theme's colours and fonts."""

from __future__ import annotations

import math
from html import escape

import numpy as np

# Colour-blind safe categorical colours (Okabe and Ito), then greys.
COLOURS = ("#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9", "#F0E442", "#000000", "#999999",
           "#666666")
_OPERATING = "#009E73"
_SURVIVAL = "#D55E00"
_FLOW_KINDS = ("solar", "albedo", "infrared", "emitted", "conduction", "heat pipes", "radiation", "dissipation",
               "heater")
_FONT = "font-family='DejaVu Sans, Arial, sans-serif'"
#: What a ``style`` gives: the background, the text, the secondary text
#: (ticks and axis titles), the grid and the plot frame colours; the text
#: and number font families; the text and title sizes [px] and the title's
#: weight; the series colours in order; the operating and survival band
#: colours.
STYLE_KEYS = ("background", "text", "muted", "grid", "frame", "font", "mono", "size", "title_size", "title_weight",
              "colours", "operating", "survival")


# The time axis: "h" (the default, the exported files' axis) or "s" (the
# screen copy with Settings > Plot units "As recorded"): (seconds per unit,
# axis title).
TIME_UNITS = {"h": (3600.0, "Time from the run's start [h]"), "s": (1.0, "Time from the run's start [s]")}


def _ticks(low: float, high: float, count: int = 6) -> list[float]:
    """Round tick values covering [low, high]."""
    if not math.isfinite(low) or not math.isfinite(high) or high <= low:
        return [low]
    raw = (high - low) / max(count - 1, 1)
    magnitude = 10.0 ** math.floor(math.log10(raw))
    step = next(m * magnitude for m in (1.0, 2.0, 2.5, 5.0, 10.0) if m * magnitude >= raw)
    first = math.ceil(low / step) * step
    return [first + i * step for i in range(int((high - first) / step + 1e-9) + 1)]


def _number(value: float) -> str:
    return f"{value:g}" if abs(value) >= 1e-9 else "0"


class _Axes:
    """A plot area, its scales and the SVG drawn into it."""

    def __init__(self, width: int, height: int, x: tuple[float, float], y: tuple[float, float], title: str,
                 x_label: str, y_label: str, legend: int, style: dict | None = None):
        self.width, self.height = width, height
        self.left, self.right, self.top = 64, 16 + (170 if legend else 0), 34
        self.bottom = 46
        self.x0, self.x1 = x
        self.y0, self.y1 = y
        self.style = style
        if style is None:  # the exported files: exactly as before (T-31)
            self.grid_colour, self.frame_colour, self.secondary = "#e3e3e3", "#555555", ""
            self.parts = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' "
                          f"viewBox='0 0 {width} {height}' {_FONT} font-size='12'>",
                          f"<rect width='{width}' height='{height}' fill='#ffffff'/>",
                          f"<text x='{self.left}' y='20' font-size='14' font-weight='bold'>{escape(title)}</text>"]
        else:  # the screen copy, in the given style (T-40)
            self.grid_colour, self.frame_colour = style["grid"], style["frame"]
            self.secondary = f" fill='{style['muted']}'"
            self.parts = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' "
                          f"viewBox='0 0 {width} {height}' font-family='{escape(style['font'])}' "
                          f"font-size='{style['size']}' fill='{style['text']}'>",
                          f"<rect width='{width}' height='{height}' fill='{style['background']}'/>",
                          f"<text x='{self.left}' y='20' font-size='{style['title_size']}' "
                          f"font-weight='{style['title_weight']}'>{escape(title)}</text>"]
        self._grid(x_label, y_label)
        self._legend_y = self.top

    @property
    def plot_width(self) -> float:
        return self.width - self.left - self.right

    @property
    def plot_height(self) -> float:
        return self.height - self.top - self.bottom

    def px(self, x: float) -> float:
        return self.left + (x - self.x0) / (self.x1 - self.x0) * self.plot_width

    def py(self, y: float) -> float:
        return self.top + (self.y1 - y) / (self.y1 - self.y0) * self.plot_height

    def _grid(self, x_label: str, y_label: str) -> None:
        bottom = self.top + self.plot_height
        grid, secondary = self.grid_colour, self.secondary
        number = secondary if self.style is None else f" font-family='{escape(self.style['mono'])}'{secondary}"
        for tick in _ticks(self.x0, self.x1):
            x = self.px(tick)
            self.parts.append(f"<line x1='{x:.1f}' y1='{self.top}' x2='{x:.1f}' y2='{bottom:.1f}' stroke='{grid}'/>")
            self.parts.append(f"<text x='{x:.1f}' y='{bottom + 16:.1f}' text-anchor='middle'{number}>"
                              f"{_number(tick)}</text>")
        for tick in _ticks(self.y0, self.y1):
            y = self.py(tick)
            self.parts.append(f"<line x1='{self.left}' y1='{y:.1f}' x2='{self.left + self.plot_width:.1f}' "
                              f"y2='{y:.1f}' stroke='{grid}'/>")
            self.parts.append(f"<text x='{self.left - 6}' y='{y + 4:.1f}' text-anchor='end'{number}>"
                              f"{_number(tick)}</text>")
        self.parts.append(f"<rect x='{self.left}' y='{self.top}' width='{self.plot_width:.1f}' "
                          f"height='{self.plot_height:.1f}' fill='none' stroke='{self.frame_colour}'/>")
        self.parts.append(f"<text x='{self.left + self.plot_width / 2:.1f}' y='{self.height - 8}' "
                          f"text-anchor='middle'{secondary}>{escape(x_label)}</text>")
        self.parts.append(f"<text transform='translate(16 {self.top + self.plot_height / 2:.1f}) rotate(-90)' "
                          f"text-anchor='middle'{secondary}>{escape(y_label)}</text>")

    def band(self, low: float, high: float, colour: str, opacity: float) -> None:
        low, high = max(low, self.y0), min(high, self.y1)
        if high <= low:
            return
        self.parts.append(f"<rect x='{self.left}' y='{self.py(high):.1f}' width='{self.plot_width:.1f}' "
                          f"height='{self.py(low) - self.py(high):.1f}' fill='{colour}' fill-opacity='{opacity}'/>")

    def line(self, x: np.ndarray, y: np.ndarray, colour: str, dash: str = "", width: float = 1.6) -> None:
        points = " ".join(f"{self.px(a):.1f},{self.py(b):.1f}" for a, b in zip(x, y, strict=True))
        dashed = f" stroke-dasharray='{dash}'" if dash else ""
        self.parts.append(f"<polyline points='{points}' fill='none' stroke='{colour}' stroke-width='{width}'"
                          f"{dashed}/>")

    def legend(self, label: str, colour: str, kind: str = "line") -> None:
        x = self.width - self.right + 12
        y = self._legend_y + 8
        if kind == "band":
            self.parts.append(f"<rect x='{x}' y='{y - 6}' width='18' height='10' fill='{colour}' "
                              "fill-opacity='0.25'/>")
        else:
            self.parts.append(f"<line x1='{x}' y1='{y}' x2='{x + 18}' y2='{y}' stroke='{colour}' "
                              "stroke-width='2'/>")
        self.parts.append(f"<text x='{x + 24}' y='{y + 4}'>{escape(label)}</text>")
        self._legend_y += 18

    def text(self) -> str:
        return "\n".join(self.parts + ["</svg>"]) + "\n"


def _decimated(time_s: np.ndarray, values: np.ndarray, most: int = 1500) -> tuple[np.ndarray, np.ndarray]:
    """At most ``most`` points, keeping every sample's minimum and maximum
    within a stride (so a peak is never lost)."""
    n = len(time_s)
    if n <= most:
        return time_s, values
    stride = math.ceil(n / (most / 2))
    keep = []
    for start in range(0, n, stride):
        block = values[start:start + stride]
        keep += sorted({start + int(np.argmin(block)), start + int(np.argmax(block))})
    keep = np.array(keep)
    return time_s[keep], values[keep]


def temperature_svg(case, nodes: list[str] | None = None, band_node: str | None = None, width: int = 900,
                    height: int = 420, title: str | None = None, style: dict | None = None,
                    time_unit: str = "h") -> str:
    """The temperatures of ``case`` (a ``thermal.results.CaseResult``)
    against hours, one line per node of ``nodes`` (all by default), with
    ``band_node``'s operating (green) and survival (orange) ranges.
    ``style`` (:data:`STYLE_KEYS`) draws it in other colours and fonts;
    ``time_unit`` "s" (:data:`TIME_UNITS`) against seconds."""
    names = nodes if nodes else list(case.network.names)
    seconds, time_title = TIME_UNITS[time_unit]
    hours = case.time_s / seconds
    columns = [case.temperature_c(n) for n in names]
    summary = {s.name: s for s in case.summary}
    lows = [float(np.min(c)) for c in columns]
    highs = [float(np.max(c)) for c in columns]
    bands = summary[band_node] if band_node in summary else None
    for limits in ((bands.operating_c, bands.survival_c) if bands else ()):
        if limits:
            lows.append(float(limits[0]))
            highs.append(float(limits[1]))
    low, high = min(lows), max(highs)
    pad = max(2.0, 0.06 * (high - low))
    axes = _Axes(width, height, (float(hours[0]), float(hours[-1]) if hours[-1] > hours[0] else float(hours[0]) + 1),
                 (low - pad, high + pad), title or f"Temperatures, {case.name} case", time_title,
                 "Temperature [°C]", legend=True, style=style)
    colours = COLOURS if style is None else style["colours"]
    operating, survival = (_OPERATING, _SURVIVAL) if style is None else (style["operating"], style["survival"])
    if bands is not None:
        if bands.survival_c:
            axes.band(*bands.survival_c, survival, 0.10)
            axes.legend(f"{band_node} survival", survival, "band")
        if bands.operating_c:
            axes.band(*bands.operating_c, operating, 0.18)
            axes.legend(f"{band_node} operating", operating, "band")
    for index, (name, column) in enumerate(zip(names, columns, strict=True)):
        colour = colours[index % len(colours)]
        dash = "" if index < len(colours) else "6 3"
        axes.line(*_decimated(hours, column), colour, dash, 2.4 if name == band_node else 1.6)
        axes.legend(name, colour)
    return axes.text()


def heat_flow_svg(case, node: str, width: int = 900, height: int = 420, title: str | None = None,
                  style: dict | None = None, time_unit: str = "h") -> str:
    """The heat flows into ``node`` by kind against hours (positive in);
    kinds that stay zero are left out. ``style`` and ``time_unit`` as for
    :func:`temperature_svg`."""
    flows = case.flows[node]
    seconds, time_title = TIME_UNITS[time_unit]
    hours = case.time_s / seconds
    kinds = [k for k in _FLOW_KINDS if k in flows and np.any(np.abs(flows[k]) > 1e-9)]
    values = [flows[k] for k in kinds] or [np.zeros(len(hours))]
    low = min(0.0, min(float(np.min(v)) for v in values))
    high = max(0.0, max(float(np.max(v)) for v in values))
    pad = max(1.0, 0.06 * (high - low))
    axes = _Axes(width, height, (float(hours[0]), float(hours[-1]) if hours[-1] > hours[0] else float(hours[0]) + 1),
                 (low - pad, high + pad), title or f"Heat flows into {node}, {case.name} case",
                 time_title, "Heat in [W]", legend=True, style=style)
    colours = COLOURS if style is None else style["colours"]
    for index, kind in enumerate(kinds):
        colour = colours[index % len(colours)]
        dash = "" if index < len(colours) else "6 3"
        axes.line(*_decimated(hours, flows[kind]), colour, dash)
        axes.legend(kind, colour)
    return axes.text()
