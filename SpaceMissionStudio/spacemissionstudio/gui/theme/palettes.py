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
back to a slot already in use. It was searched for in OKLCH (UI audit B10,
``docs/DECISIONS.md``) and is checked by ``tests/gui/test_theme.py``:

* **every pair of the first six slots** (:data:`SHOWN_TOGETHER`: a plot's
  x, y and z, a quaternion's four parts, the event timeline's six kinds)
  is at least CIEDE2000 Delta E 18 apart with normal vision and at least
  10 under simulated protanopia and deuteranopia and 7.5 under
  tritanopia (Machado, Oliveira and Fernandes 2009, severity 1). The
  first three slots (x, y, z) are at least 30 apart, and 20 under each
  simulation. Measured: normal 25.1 (light) and 19.1 (dark), protan and
  deutan 12.3 and 10.4, tritan 10.3 and 8.1;
* neighbouring slots of all eight are at least OKLab Delta E 15 apart;
* the data-visualisation validator passes in both themes, for adjacent
  pairs (all eight) and for all pairs of the first six;
* every colour is at least 3:1 against ``bg.surface`` (light #FFFFFF, dark
  #111418), inside the validator's lightness band and chroma floor;
* every colour is at least OKLab Delta E 9 from every status colour (icon
  and text values) and from the accent, and one closer than 15 has a hue
  at least 15 degrees away, so a series is never read as a status.

Each slot keeps its hue family in both themes: indigo, olive, brick,
teal, magenta, violet, plum, orchid. Slots 7 and 8 are checked for
adjacent pairs only; a plot with more than six series keeps its legend,
so colour is never the only cue.

What is drawn on black space or on the Earth's image (Results › 3D View,
the live map) takes the dark theme's steps in both themes
(:func:`depicted`): the light steps are made for a white surface.
"""

from __future__ import annotations


# Hue order (OKLCH h): indigo 280, olive 120, brick 30, teal 190, magenta
# 345, violet 295, plum 310, orchid 330.
CATEGORICAL: dict[str, list[str]] = {
    "light": ["#4C32D4", "#839A0D", "#922116", "#0AA39C", "#B40677", "#9780F7", "#7D4E9D", "#D042C9"],
    "dark": ["#5B4AEA", "#929D03", "#9D4B46", "#15A8AE", "#BE1099", "#B76CE9", "#72579D", "#C642D0"],
}
# The most series a standard plot shows together, each in its own colour:
# every pair of these first slots is checked, not only neighbours.
SHOWN_TOGETHER = 6


def categorical(mode: str) -> list[str]:
    """The categorical palette of ``mode``: a copy."""
    return list(CATEGORICAL[mode])


def depicted() -> list[str]:
    """The categorical palette for things drawn on black space or the
    Earth's image (the 3D View, the live map), in both themes: the dark
    steps, made for a dark surface. A copy."""
    return list(CATEGORICAL["dark"])


# The application icon (gui/icons.py): a mission scene on a dark
# rounded-square plate with a light rim. The Earth, its orbit, a satellite
# on the orbit with a link beam to a ground station, and the Sun. One icon
# for both themes: the taskbar's background is the platform's, not ours.
# The plate gives the icon 3 : 1 or more against light panels, the rim
# against dark panels (Windows 10 and 11, Ubuntu's dock and top bar)
# (docs/developer/windows-views-design.md, section 5; tests/gui/test_icons.py).
APP_ICON = {
    "plate": "#1A2C57",  # the plate: flat at the top, deepening to plate_bottom
    "plate_bottom": "#0A1128",  # the plate's lower part; the satellite's outline
    "rim": "#5B7FC7",  # the plate's rim
    "ocean": "#1A4FA6",  # the Earth when its texture is missing
    "atmosphere": "#9CC7FF",  # the Earth's limb
    "orbit": "#E8EEF8",  # the orbit track
    "sun": "#F2B705",  # the Sun (SUN_COLOUR of the 3D view)
    "panel": "#60A5FA",  # solar panels
    "body": "#CFB87C",  # the satellite's body: gold multi-layer insulation
    "beam": "#5BD27A",  # the link beam (LINE_OF_SIGHT_COLOUR of the 3D view)
    "station": "#F4F5F7",  # the ground station (STATION_COLOUR of the 3D view)
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
# A ground station's glyph (a triangle on a mast, on the globe and the 2D
# map) is outlined in this dark colour, so it reads on clouds, ice, sea and
# the night side alike (2.12.0, decision "Ground tracks, stations and the
# live map"). Its visibility circle takes the station's colour, and the
# line-of-sight colour while a spacecraft is in view: depicted things, not
# status, the same in both themes.
STATION_OUTLINE_COLOUR = "#0B0D10"
# The live 2D map (gui/ground_map_widget.py), over NASA's Blue Marble in
# both themes: the night side's shade (drawn translucent) and the latitude
# and longitude grid (drawn translucent).
NIGHT_COLOUR = "#000814"
MAP_GRID_COLOUR = "#FFFFFF"

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
