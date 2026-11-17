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
"""The look of Results › 3D View's page (``gui/assets/mission_view/``),
as data the page applies with ``MV.setStyle``: the colours of what it
depicts (the same in both themes), each spacecraft's colour (the
categorical palette, in order), and the CSS of its overlays (the
time/speed panel and the labels), which take the theme's surfaces, text
colours, fonts, sizes and radii. The page itself holds no colour, font
or size of its own."""

from __future__ import annotations

from .palettes import (ATMOSPHERE_COLOUR, AXIS_COLOURS, LINE_OF_SIGHT_COLOUR, NADIR_COLOUR, PLAIN_BODY_COLOUR,
                       SPACE_COLOUR, STATION_COLOUR, STATION_OUTLINE_COLOUR, SUN_COLOUR, VELOCITY_COLOUR, categorical)
from .plotly_template import font_faces
from .tokens import tokens
from .typography import BORDER, RADIUS, SIZE, SPACE, WEB_FONT_STACK, WEB_MONO_STACK, WEIGHT

_CONE_OPACITY = 0.22  # [-] a field of view or a plume
_PATH_OPACITY = 0.45  # [-] the whole path, under the trail
_STATION_MARKER_PX = 14  # [px] a station's glyph (a triangle on a mast), its height on screen at any zoom
_SUN_GLOW_PX = 96  # [px] the Sun's glow
_RING_OPACITY = 0.5  # [-] a station's visibility circle with no spacecraft in view
_RING_CONTACT_OPACITY = 0.95  # [-] the same, while the spacecraft is in view
_TRACK_OPACITY = 0.9  # [-] the ground track flown
_FUTURE_TRACK_OPACITY = 0.6  # [-] the ground track still to come (dashed)
_TRACK_DASH_PX = (6, 4)  # [px] dash and gap of the track still to come, on screen


def overlay_css(t: dict[str, str]) -> str:
    """The CSS of the page's overlays: the time panel (``#hud``), the
    labels (``.label``) and the live badge, on the theme's raised surface."""
    panel = (f"background: {t['bg.raised']}; color: {t['text.primary']}; border: {BORDER}px solid "
             f"{t['border.subtle']}; border-radius: {RADIUS['panel']}px;")
    return (f"{font_faces()} "
            f"html, body {{ margin: 0; height: 100%; overflow: hidden; background: {SPACE_COLOUR}; "
            f"font-family: {WEB_FONT_STACK}; font-size: {SIZE['small']}px; }} "
            f"#view {{ position: absolute; inset: 0; }} "
            f"#hud {{ position: absolute; left: {SPACE['md']}px; top: {SPACE['md']}px; {panel} "
            f"padding: {SPACE['sm']}px {SPACE['md']}px; font-family: {WEB_MONO_STACK}; "
            f"font-size: {SIZE['small']}px; line-height: {SIZE['small'] + SPACE['xs'] + SPACE['xs']}px; "
            f"pointer-events: none; white-space: pre; }} "
            f"#hud .muted {{ color: {t['text.secondary']}; }} "
            f"#live {{ display: none; margin-left: {SPACE['sm']}px; padding: 0 {SPACE['xs']}px; "
            f"border-radius: {RADIUS['control']}px; background: {t['status.critical.soft']}; "
            f"color: {t['text.primary']}; font-family: {WEB_FONT_STACK}; font-weight: {WEIGHT['semibold']}; }} "
            f".label {{ position: absolute; transform: translate({SPACE['sm']}px, -50%); {panel} "
            f"padding: 0 {SPACE['xs']}px; font-size: {SIZE['caption']}px; font-weight: {WEIGHT['medium']}; "
            f"pointer-events: none; white-space: nowrap; }} "
            f".label .dot {{ display: inline-block; width: {SPACE['sm']}px; height: {SPACE['sm']}px; "
            f"border-radius: 50%; margin-right: {SPACE['xs']}px; }} "
            # A ground station: its glyph's foot on the station, its name in a panel to the right.
            f".label.station {{ background: none; border: 0; padding: 0; transform: none; width: 0; height: 0; }} "
            f".label.station .glyph {{ position: absolute; left: -{_STATION_MARKER_PX // 2}px; "
            f"top: -{_STATION_MARKER_PX}px; width: {_STATION_MARKER_PX}px; height: {_STATION_MARKER_PX}px; "
            f"overflow: visible; }} "
            f".label.station .glyph path {{ fill: {STATION_COLOUR}; stroke: {STATION_OUTLINE_COLOUR}; "
            f"stroke-width: {BORDER}px; stroke-linejoin: round; paint-order: stroke; }} "
            f".label.station.contact .glyph path {{ fill: {LINE_OF_SIGHT_COLOUR}; }} "
            f".label.station .name {{ position: absolute; left: {_STATION_MARKER_PX // 2 + SPACE['xs']}px; "
            f"top: -{_STATION_MARKER_PX + SPACE['xs']}px; {panel} padding: 0 {SPACE['xs']}px; }}")


def mission_view_style(mode: str) -> dict:
    """Everything ``MV.setStyle`` takes for theme ``mode``."""
    t = tokens(mode)
    return {
        "mode": mode, "css": overlay_css(t), "space": SPACE_COLOUR, "crafts": categorical(mode),
        "sun": SUN_COLOUR, "plain": PLAIN_BODY_COLOUR, "atmosphere": ATMOSPHERE_COLOUR,
        "axes": list(AXIS_COLOURS), "nadir": NADIR_COLOUR, "velocity": VELOCITY_COLOUR,
        "station": STATION_COLOUR, "link": LINE_OF_SIGHT_COLOUR, "fov": t["accent"], "plume": t["status.caution"],
        "cone_opacity": _CONE_OPACITY, "path_opacity": _PATH_OPACITY, "station_px": _STATION_MARKER_PX,
        "sun_px": _SUN_GLOW_PX, "station_outline": STATION_OUTLINE_COLOUR, "ring_opacity": _RING_OPACITY,
        "ring_contact_opacity": _RING_CONTACT_OPACITY, "track_opacity": _TRACK_OPACITY,
        "future_track_opacity": _FUTURE_TRACK_OPACITY, "track_dash_px": list(_TRACK_DASH_PX),
    }
