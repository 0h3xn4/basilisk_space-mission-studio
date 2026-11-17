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
"""The look of the thermal plots on screen (Run › Thermal, decision T-40)
as the ``style`` that ``thermal.plots`` takes: the theme's surface and
text colours, its grid and frame lines, Inter for the text and JetBrains
Mono for the numbers at the type scale's sizes, the categorical palette
in order, and the operating and survival bands in the normal and caution
status colours (a band is a limit: in it is normal, out of it is not;
each band has its name in the legend, so colour is never the only cue).
The exported files keep their own fixed look (T-31)."""

from __future__ import annotations

from .palettes import categorical
from .tokens import tokens
from .typography import MONO_FONT_FAMILY, SIZE, UI_FONT_FAMILY, WEIGHT


def svg_plot_style(mode: str) -> dict:
    """The plot style of theme ``mode`` (``thermal.plots.STYLE_KEYS``)."""
    t = tokens(mode)
    return {
        "background": t["bg.surface"], "text": t["text.primary"], "muted": t["text.secondary"],
        "grid": t["border.subtle"], "frame": t["border.strong"], "font": UI_FONT_FAMILY, "mono": MONO_FONT_FAMILY,
        "size": SIZE["small"], "title_size": SIZE["section"], "title_weight": WEIGHT["semibold"],
        "colours": categorical(mode), "operating": t["status.normal"], "survival": t["status.caution"],
    }
