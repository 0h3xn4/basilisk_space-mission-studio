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
"""Chart palettes, generated for each theme.

:data:`CATEGORICAL` is the 8-colour categorical palette of every plot and
diagram, in a fixed order: series take slots in order and never cycle
back to a slot already in use. It was searched for in OKLCH and checked
with the data-visualisation validator (``docs/DECISIONS.md``):

* light, on ``bg.surface`` #FFFFFF: worst adjacent colour-vision-deficiency
  separation Delta E 14.3 (protan), worst adjacent normal-vision Delta E
  20.8, every colour at least 3:1 against the surface;
* dark, on ``bg.surface`` #111418: worst adjacent CVD Delta E 14.8
  (deutan), normal-vision 15.2, every colour at least 3:1;
* every colour at least Delta E 8 from every status colour (icon and text
  values) and from the accent, so a series is never read as a status.

It is validated for adjacent pairs (lines, bars, stacks: every chart in
the GUI today). With all 28 pairs side by side (a scatter of eight
groups) two pairs fall below the floors in each theme, which is why every
chart keeps a legend: colour is never the only cue.
"""

from __future__ import annotations


# Hue order (OKLCH h): orchid 325, brown 65, purple 305, green 135, teal
# 185, blue 265, crimson 10, ocean 225.
CATEGORICAL: dict[str, list[str]] = {
    "light": ["#AE59B4", "#8A3600", "#6C25A4", "#236400", "#00A596", "#5283FE", "#B80040", "#005F93"],
    "dark": ["#CA4ED3", "#B36C0D", "#8B63B6", "#458604", "#00A794", "#3163F1", "#DA185B", "#007CB1"],
}


def categorical(mode: str) -> list[str]:
    """The categorical palette of ``mode``: a copy."""
    return list(CATEGORICAL[mode])

# The application icon (gui/icons.py): blue solar panels in the light
# theme's accent, a gold (multi-layer insulation) body. One icon for both
# themes: the taskbar's background is the platform's, not ours.
APP_ICON = {
    "panel": "#2563EB",  # the light accent
    "panel_line": "#1E3A8A",  # antenna and panel grid lines
    "body": "#CFB87C",
    "body_line": "#A88F53",  # the body's centre line
}

# The axes of the 3D model view: x, y, z in the red, green, blue order
# every 3D tool uses. They draw geometry, not status.
AXIS_COLOURS = ("#D62728", "#2CA02C", "#1F77B4")

# The 3D mission view (gui/mission_view_widget.py): depicted things, not
# status, so the same in both themes. Space is black behind the stars;
# the Sun's glow and arrow; a body without a texture (the Moon, Mars);
# the Earth's atmosphere rim; the nadir and velocity arrows; a ground
# station's marker and its line of sight to a spacecraft it sees.
PLAIN_BODY_COLOUR = "#8A8F98"
SUN_COLOUR = "#F2B705"
SPACE_COLOUR = "#000000"
ATMOSPHERE_COLOUR = "#5A9BE8"
NADIR_COLOUR = "#C9CED6"
VELOCITY_COLOUR = "#35C2E0"
STATION_COLOUR = "#F4F5F7"
LINE_OF_SIGHT_COLOUR = "#5BD27A"

# Temperatures on a 3D model (Run › Thermal's 3D model and Results › 3D
# View): ColorBrewer's diverging "RdBu" (Brewer, colorbrewer2.org),
# reversed, so cold is blue and hot is red; the same stops as Plotly's
# "RdBu_r", which the Thermal page's 3D model takes by name. It stays
# readable with red-green colour-vision deficiency. Data, not status, and
# the same in both themes; every view that uses it shows a colour bar with
# the values and the unit, so colour is never the only cue. A part in no
# thermal node is a neutral grey.
TEMPERATURE_STOPS = ("#053061", "#2166AC", "#4393C3", "#92C5DE", "#D1E5F0", "#F7F7F7", "#FDDBC7", "#F4A582",
                     "#D6604D", "#B2182B", "#67001F")
NO_TEMPERATURE_COLOUR = "#A0A0A0"


def temperature_rgb(fraction):
    """The colour at ``fraction`` (0 coldest to 1 hottest, clipped; a
    number or an array) of :data:`TEMPERATURE_STOPS`, linear between
    stops, as 0 to 255 sRGB floats (shape ``fraction.shape + (3,)``)."""
    import numpy as np

    stops = np.array([[int(c[i:i + 2], 16) for i in (1, 3, 5)] for c in TEMPERATURE_STOPS], dtype=float)
    position = np.clip(np.asarray(fraction, dtype=float), 0.0, 1.0) * (len(stops) - 1)
    low = np.minimum(np.floor(position).astype(int), len(stops) - 2)
    weight = (position - low)[..., None]
    return stops[low] * (1.0 - weight) + stops[low + 1] * weight


def ink_on(colour: str) -> str:
    """Black or white, whichever reads on a fill of ``colour`` (a colour
    the user picked, such as a 3D part's)."""
    r, g, b = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
    return "#000000" if (r * 299 + g * 587 + b * 114) > 128000 else "#FFFFFF"


def swatch_style(colour: str) -> str:
    """The style sheet of a button that shows a colour the user picked
    (``#RRGGBB``), labelled in ink that reads on it."""
    return f"background-color: {colour}; color: {ink_on(colour)};"
