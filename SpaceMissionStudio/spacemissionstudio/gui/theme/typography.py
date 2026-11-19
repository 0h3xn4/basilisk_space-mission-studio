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
"""Type, spacing and shape: the brief's scale, in pixels.

Inter for the interface, JetBrains Mono for numbers in tables, IDs, code
and logs. Sizes and weights are the only ones the GUI uses; spacing is on
a 4 px grid.
"""

from __future__ import annotations

UI_FONT_FAMILY = "Inter"
MONO_FONT_FAMILY = "JetBrains Mono"
# The CSS font stack of web views (plots): the bundled faces first.
WEB_FONT_STACK = "'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif"
WEB_MONO_STACK = "'JetBrains Mono', ui-monospace, 'Cascadia Mono', monospace"

# Sizes [px].
SIZE = {
    "caption": 11,  # [px]
    "small": 12,  # [px] small text and table cells
    "body": 13,  # [px] the base size
    "section": 15,  # [px] section titles
    "page": 18,  # [px] page titles
    "display": 22,  # [px] rare
}
# Weights: regular, medium, semibold. Nothing else.
WEIGHT = {"regular": 400, "medium": 500, "semibold": 600}

# Spacing, the 4 px grid [px].
SPACE = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "xxl": 32}  # [px]
CONTROL_HEIGHT = {"compact": 28, "default": 32}  # [px]
ROW_HEIGHT = 26  # [px] table rows
RADIUS = {"control": 6, "panel": 8}  # [px] controls; panels, popovers and dialogs
FOCUS_RING = 2  # [px]
BORDER = 1  # [px]
ICON_SIZE = {"ui": 16, "rail": 20}  # [px]
# An area's header (its title and commands, gui.shell.AreaPage): one row of
# controls with a small inset above and below, the same in every area, so
# the tab rows under it start at one height (UI audit UI-17).
AREA_HEADER_HEIGHT = CONTROL_HEIGHT["default"] + 2 * SPACE["sm"]  # [px]
# The top bar narrower than this: its search field shows its icon and key
# only, so the subtitle keeps room for the save state (UI audit UI-36).
# About a scenario name, the state and the commands with the whole search
# field. The top bar spans the window (UI audit UI-06), so only a window
# narrower than this shows the short search field.
TOP_BAR_COMPACT_BELOW = 1040  # [px]
# The Inspector (UI audit UI-06, UI-56): the width it opens at, enough for
# its labels and a wrapped line of help, and the narrowest window it opens
# in by itself. A narrower new window starts without it (Ctrl+I shows it),
# so it never squeezes a 1280 px window.
INSPECTOR_WIDTH = 320  # [px]
INSPECTOR_MIN_WINDOW_PX = 1440  # [px]
# A dock's title bar (UI audit UI-39): its title and its Float and Close
# buttons, icons of the interface size on compact buttons.
DOCK_TITLE_HEIGHT = CONTROL_HEIGHT["compact"] + SPACE["xs"]  # [px]
# Toasts (UI audit UI-54): at most this wide, the margin from the edge of
# the area they sit in, and the gap between two.
TOAST = {"max_width": 360, "margin": SPACE["lg"], "gap": SPACE["sm"]}  # [px]
# Motion: hover, panel open/close and toasts. Never data values or plots.
MOTION_MS = {"fast": 120, "slow": 180}  # [ms]

# The widest a form, a list editor or a page of reading text grows: at
# 2560 px its fields and buttons stretched to 1500 px, labels and values a
# head-turn apart. Plots, tables and the JSON view keep the full width.
CONTENT_MAX_WIDTH_PX = 960  # [px]

# Where a page's content starts: the same inset from the page's edges on
# every page of every area, under a tab row or beside the Scenario tree, as
# the area header's title is inset (UI audit UI-16, UI-52). The tab rows and
# the Scenario tree stay flush: they are navigation, not content.
PAGE_INSET = SPACE["lg"]  # [px]

# The widest a form's field grows (UI audit UI-26): a number sits beside
# its label (one of several in a row: "vector"; shrinking to "vector_min"
# on a narrow page) and a choice is as wide as a long entry, never across
# the page. Text fields (a name, a path) keep the form's width.
FIELD_WIDTH = {"number": 224, "vector": 128, "vector_min": 72, "choice": 320}  # [px]
# The widest a form's label column grows (UI audit UI-26): a longer label
# wraps onto a second line, so one long name does not push every field of
# the page to the right.
LABEL_COLUMN_MAX_PX = 224  # [px]

# The Scenario tree's width (UI audit UI-18): at least "min"; as wide as its
# longest node needs, up to "max" (a longer one is elided, whole on hover).
PAGE_TREE_WIDTH = {"min": 170, "start": 220, "max": 340}  # [px]
