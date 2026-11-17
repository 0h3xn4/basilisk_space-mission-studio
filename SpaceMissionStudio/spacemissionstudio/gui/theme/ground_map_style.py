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
"""The look of the live 2D map (``gui/ground_map_widget.py``), as data:
the colours of what it depicts (the same in both themes, as the 3D
View's), each spacecraft's colour (the categorical palette, in order),
the theme's surfaces and text for its labels, legend and margins, and
its line widths and marker sizes. The map's module holds no colour or
size of its own."""

from __future__ import annotations

from .palettes import (LINE_OF_SIGHT_COLOUR, MAP_GRID_COLOUR, NIGHT_COLOUR, STATION_COLOUR, STATION_OUTLINE_COLOUR,
                       categorical)
from .tokens import tokens
from .typography import BORDER, RADIUS, SPACE

_GRID_ALPHA = 0.35  # [-] the latitude and longitude lines over the image
_NIGHT_ALPHA = 0.45  # [-] the night side's shade
_FUTURE_ALPHA = 0.75  # [-] a ground track still to come (dashed)
_RING_ALPHA = 0.55  # [-] a visibility circle with no spacecraft in view
_TRACK_PX = 2  # [px] a ground track's width
_RING_PX = 1  # [px] a visibility circle's width; doubled while a spacecraft is in view
_LINK_PX = 2  # [px] a station's line to the spacecraft it sees
_MARKER_PX = 12  # [px] a spacecraft's marker (diameter)
_GLYPH_PX = 14  # [px] a station's glyph (height), as on the globe
_DASH = (3.0, 2.0)  # [-] dash and gap of a future track, in line widths (Qt's dash pattern)


def ground_map_style(mode: str) -> dict:
    """Everything the map draws with, for theme ``mode``."""
    t = tokens(mode)
    return {
        "mode": mode, "crafts": categorical(mode), "station": STATION_COLOUR, "station_outline": STATION_OUTLINE_COLOUR,
        "link": LINE_OF_SIGHT_COLOUR, "grid": MAP_GRID_COLOUR, "grid_alpha": _GRID_ALPHA, "night": NIGHT_COLOUR,
        "night_alpha": _NIGHT_ALPHA, "future_alpha": _FUTURE_ALPHA, "ring_alpha": _RING_ALPHA,
        "margin": t["bg.canvas"], "panel": t["bg.raised"], "panel_border": t["border.subtle"],
        "text": t["text.primary"], "text_secondary": t["text.secondary"],
        "track_px": _TRACK_PX, "ring_px": _RING_PX, "link_px": _LINK_PX, "marker_px": _MARKER_PX,
        "glyph_px": _GLYPH_PX, "dash": _DASH, "border_px": BORDER, "radius_px": RADIUS["control"],
        "pad_px": SPACE["xs"], "gap_px": SPACE["sm"],
    }
