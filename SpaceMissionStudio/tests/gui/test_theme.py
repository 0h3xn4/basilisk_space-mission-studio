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
"""The theme package (gui/theme/): the token table, the bundled fonts and
icons, the generated style sheet, the Plotly template and the live theme
switch (docs/ui/UI_OVERHAUL.md, "Tokens"; docs/DECISIONS.md)."""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.requires_gui

_ROOT = Path(__file__).resolve().parents[2]
_BRIEF = _ROOT / "docs" / "ui" / "UI_OVERHAUL.md"
_DECISIONS = _ROOT / "docs" / "DECISIONS.md"



def test_the_tokens_are_the_briefs_table_or_a_recorded_adjustment():
    """Every row of the brief's token table is a token of the same value,
    except where tokens.ADJUSTED changes it to pass WCAG AA, and each
    adjusted token is named in docs/DECISIONS.md."""
    from spacemissionstudio.gui.theme import tokens

    table = re.findall(r"^\| ([a-z]+\.[a-z]+|accent) \| (#[0-9A-F]{6})[^|]*\| (#[0-9A-F]{6})[^|]*\|$",
                       _BRIEF.read_text(encoding="utf-8"), re.MULTILINE)
    assert len(table) == 10  # bg.selected is derived; the other ten rows carry values
    decisions = _DECISIONS.read_text(encoding="utf-8")
    for name, dark, light in table:
        assert tokens.BRIEF["dark"][name] == dark and tokens.BRIEF["light"][name] == light, name
        for mode in tokens.MODES:
            value = tokens.tokens(mode)[name]
            assert value == tokens.ADJUSTED[mode].get(name, tokens.BRIEF[mode][name]), (mode, name)
    for mode, changed in tokens.ADJUSTED.items():
        for name, value in changed.items():
            assert f"`{name}`" in decisions and value in decisions, (mode, name, value)
    status = dict(re.findall(r"(critical|serious|caution|normal|standby) (#[0-9A-F]{6})",
                             _BRIEF.read_text(encoding="utf-8")))
    assert status == tokens.STATUS_BRIEF


def test_both_themes_have_the_same_tokens_and_the_selected_tint():
    """Light and dark define the same token names; bg.selected is the
    accent at 10 % (light) and 16 % (dark) over the surface."""
    from spacemissionstudio.gui.theme import tokens

    light, dark = tokens.tokens("light"), tokens.tokens("dark")
    assert set(light) == set(dark)
    for mode, values in (("light", light), ("dark", dark)):
        assert values["bg.selected"] == tokens.mix(values["accent"], values["bg.surface"],
                                                   tokens.SELECTED_SHARE[mode])
    assert tokens.SELECTED_SHARE == {"light": 0.10, "dark": 0.16}
    with pytest.raises(ValueError):
        tokens.tokens("sepia")


def test_the_bundled_fonts_register_and_are_the_application_font(restored_theme):
    """Inter (400, 500, 600) and JetBrains Mono (400, 500) ship in the
    package with their OFL texts, register with Qt from there, and Inter
    at the 13 px body size is the application font. CI runs this on
    Linux, Windows and macOS."""
    from PySide6.QtGui import QFontDatabase

    from spacemissionstudio.gui.theme import FONTS_DIR, MONO_FONT_FAMILY, UI_FONT_FAMILY, apply_theme, load_fonts

    assert sorted(p.relative_to(FONTS_DIR).as_posix() for p in FONTS_DIR.rglob("*.ttf")) == [
        "inter/Inter-Medium.ttf", "inter/Inter-Regular.ttf", "inter/Inter-SemiBold.ttf",
        "jetbrains-mono/JetBrainsMono-Medium.ttf", "jetbrains-mono/JetBrainsMono-Regular.ttf"]
    for family in ("inter", "jetbrains-mono"):
        assert "SIL OPEN FONT LICENSE" in (FONTS_DIR / family / "OFL.txt").read_text(encoding="utf-8").upper()
    families = load_fonts()
    assert UI_FONT_FAMILY in families and MONO_FONT_FAMILY in families
    assert {"Regular", "Medium", "SemiBold"} <= set(QFontDatabase.styles(UI_FONT_FAMILY))
    apply_theme(restored_theme, "light")
    assert restored_theme.font().family() == UI_FONT_FAMILY
    assert restored_theme.font().pixelSize() == 13  # [px] the brief's body size


def test_no_ibm_plex_or_carbon_remains_in_the_gui():
    """The Carbon restyle is gone: no IBM Plex file and no Carbon name in
    the GUI package's code (docs/DECISIONS.md records the change)."""
    gui = _ROOT / "spacemissionstudio" / "gui"
    assert not [p for p in gui.rglob("*") if "plex" in p.name.lower()]
    named = [p.name for p in gui.rglob("*.py") if re.search(r"\bCarbon\b|IBM Plex", p.read_text(encoding="utf-8"))]
    assert named == []


def test_numeric_columns_get_tabular_figures(qapp):
    """Numbers in tables use Inter's tabular figures where Qt supports font
    features, JetBrains Mono otherwise."""
    from PySide6.QtGui import QFont

    from spacemissionstudio.gui.theme import MONO_FONT_FAMILY, numeric_font, tabular_figures_supported

    font = numeric_font()
    if tabular_figures_supported():
        assert font.featureValue(QFont.Tag("tnum")) == 1
    else:
        assert font.family() == MONO_FONT_FAMILY


def test_every_icon_the_app_uses_is_bundled_with_its_licence():
    """The toolbar and step icons, the style sheet's glyphs and every icon
    the GUI code names (``icon("...")``) are Lucide icons in the package,
    with Lucide's ISC licence."""
    import re
    from pathlib import Path

    from spacemissionstudio.gui.theme import icons

    gui = Path(icons.__file__).resolve().parents[1]
    named = {name for path in gui.rglob("*.py")
             for name in re.findall(r"""\bicon\(\s*["']([a-z0-9-]+)["']""", path.read_text(encoding="utf-8"))}
    assert "sliders-horizontal" in named  # the 3D View's Show button
    names = set(icons.ACTION_ICONS.values()) | set(icons.STEP_ICONS.values()) | named | {
        "chevron-down", "chevron-up", "chevron-right", "check"}
    assert sorted(name for name in names if not icons.available(name)) == []
    assert "ISC License" in (icons.ICONS_DIR / "LICENSE").read_text(encoding="utf-8")
    for path in icons.ICONS_DIR.glob("*.svg"):
        assert "currentColor" in path.read_text(encoding="utf-8"), path.name  # tintable


def test_icons_follow_the_theme(restored_theme):
    """An icon is drawn in its token's colour of the theme in use: the same
    QIcon changes colour when the theme does."""
    from spacemissionstudio.gui.theme import TOKENS, apply_theme, icon

    def ink(qicon):
        image = qicon.pixmap(64, 64).toImage()
        pixels = [image.pixelColor(x, y) for x in range(64) for y in range(64)]
        return max(pixels, key=lambda c: c.alpha()).name().upper()

    play = icon("play", "accent")
    apply_theme(restored_theme, "light")
    light = ink(play)
    assert light == TOKENS["accent"]
    apply_theme(restored_theme, "dark")
    assert ink(play) == TOKENS["accent"] != light


def test_every_command_button_has_an_icon(qtbot):
    """Every command button of the top bar and of the area headers (where
    the toolbars' commands now are) has an icon, except the run-mode
    drop-downs."""
    from PySide6.QtWidgets import QToolButton

    from spacemissionstudio.gui.main_window import MainWindow

    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    buttons = window.top_bar.findChildren(QToolButton)
    for area in window.shell.page_areas():
        buttons += list(area.page.buttons.values())
    assert len(buttons) > 10  # the check covers the commands
    for button in buttons:
        if button is window.run_mode_button:
            continue  # the run mode picker beside Run: a text drop-down, like a combo box (U-18)
        assert not button.icon().isNull(), button.text()


def test_apply_theme_sets_the_palette_and_one_sheet(restored_theme):
    """Applying a theme sets the palette from the tokens (Mid, used for
    muted hint text, is text.secondary: Qt's computed default was
    unreadable) and a style sheet; applying it twice changes nothing."""
    from PySide6.QtGui import QPalette

    from spacemissionstudio.gui.theme import TOKENS, apply_theme

    for mode in ("light", "dark"):
        apply_theme(restored_theme, mode)
        palette = restored_theme.palette()
        assert palette.color(QPalette.ColorRole.Window).name().upper() == TOKENS["bg.canvas"]
        assert palette.color(QPalette.ColorRole.Base).name().upper() == TOKENS["bg.surface"]
        assert palette.color(QPalette.ColorRole.Mid).name().upper() == TOKENS["text.secondary"]
        sheet = restored_theme.styleSheet()
        apply_theme(restored_theme, mode)
        assert restored_theme.styleSheet() == sheet != ""


def test_a_live_switch_restyles_once(restored_theme, monkeypatch):
    """A theme switch does not set the Fusion style again: with a sheet set,
    app.style() is Qt's style-sheet style, whose name() is empty, and
    setting Fusion on every switch restyled every widget a second time."""
    from PySide6.QtWidgets import QApplication

    from spacemissionstudio.gui.theme import apply_theme

    apply_theme(restored_theme, "light")
    assert restored_theme.styleSheet()
    calls = []
    original = QApplication.setStyle
    monkeypatch.setattr(QApplication, "setStyle", staticmethod(lambda style: calls.append(style) or original(style)))
    apply_theme(restored_theme, "dark")
    apply_theme(restored_theme, "light")
    assert calls == []


def test_every_file_the_style_sheet_references_exists(restored_theme):
    """The combo and spin arrows and the tick are tinted icon files: a
    missing one would silently bring back arrow-less combo boxes."""
    from spacemissionstudio.gui.theme import apply_theme

    for mode in ("light", "dark"):
        apply_theme(restored_theme, mode)
        referenced = re.findall(r"url\(([^)]+)\)", restored_theme.styleSheet())
        assert referenced
        assert [path for path in referenced if not Path(path).is_file()] == []


def test_the_style_sheet_parses_without_qt_warnings(qtbot, restored_theme):
    """No Qt style sheet warning while the main window, a scenario and
    the editor dialogs are shown in either theme (the brief's
    "no warnings from Qt about stylesheets")."""
    from PySide6.QtCore import qInstallMessageHandler

    from spacemissionstudio.gui.main_window import MainWindow
    from spacemissionstudio.gui.theme import apply_theme

    messages = []
    previous = qInstallMessageHandler(lambda _mode, _context, text: messages.append(text))
    try:
        templates = _ROOT / "spacemissionstudio" / "scenarios" / "templates"
        for mode in ("light", "dark"):
            apply_theme(restored_theme, mode)
            window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
            qtbot.addWidget(window)
            window.show()
            assert window.open_path(next(templates.glob("19_*.json")))
            window.scenario_editor.show_spacecraft(0)
            for area in window.shell.page_areas():
                window.shell.show_area(area.id)
                restored_theme.processEvents()
    finally:
        qInstallMessageHandler(previous)
    assert [m for m in messages if "style" in m.lower() or "parse" in m.lower()] == []


def test_the_plotly_template_comes_from_the_tokens():
    """Plots: Inter, transparent backgrounds over the surface, gridlines in
    border.subtle, axis text in text.secondary, the categorical palette as
    the colourway."""
    from spacemissionstudio.gui.theme import palettes, plotly_template, tokens

    for mode in tokens.MODES:
        t = tokens.tokens(mode)
        layout = plotly_template.layout(t, palettes.categorical(mode))
        assert layout["paper_bgcolor"] == layout["plot_bgcolor"] == plotly_template.TRANSPARENT
        assert layout["font"]["family"].startswith("'Inter'")
        assert layout["xaxis"]["gridcolor"] == t["border.subtle"]
        assert layout["yaxis"]["tickfont"]["color"] == t["text.secondary"]
        assert layout["colorway"] == palettes.CATEGORICAL[mode]
        assert t["bg.surface"] in plotly_template.page_css(t)
        assert "@font-face" in plotly_template.font_faces()


def _oklab(colour):
    r, g, b = (int(colour[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
    r, g, b = (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b))
    lms = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b,
           0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b,
           0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    lo, m, s = (v ** (1 / 3) for v in lms)
    return (0.2104542553 * lo + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * lo - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * lo + 0.7827717662 * m - 0.8086757660 * s)


def test_the_categorical_palette_is_distinct_and_readable():
    """Eight colours per theme, each at least 3:1 against the surface and
    at least Delta E 8 (OKLab x 100) from every status colour and the
    accent; neighbouring slots at least Delta E 15 apart (the full
    colour-vision-deficiency check is the validator run recorded in
    docs/DECISIONS.md)."""
    from spacemissionstudio.gui.theme import palettes, tokens

    def delta_e(a, b):
        return 100 * sum((x - y) ** 2 for x, y in zip(_oklab(a), _oklab(b))) ** 0.5

    for mode in tokens.MODES:
        t = tokens.tokens(mode)
        series = palettes.CATEGORICAL[mode]
        assert len(series) == len(set(series)) == 8
        reserved = [t["accent"]] + [t[f"status.{name}{part}"] for name in tokens.STATUSES[:-1]
                                    for part in ("", ".text")]
        for colour in series:
            assert tokens.contrast(colour, t["bg.surface"]) >= 3.0, (mode, colour)
            assert min(delta_e(colour, other) for other in reserved) >= 8.0, (mode, colour)
        assert min(delta_e(a, b) for a, b in zip(series, series[1:])) >= 15.0, mode


# Machado, Oliveira and Fernandes (2009), severity 1.0, on linear sRGB.
_CVD = {
    "protan": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
    "deutan": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881)),
    "tritan": ((1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602), (0.004733, 0.691367, 0.303900)),
}


def _cielab(colour, cvd=None):
    """CIE L*a*b* (D65) of ``colour``, seen with the colour-vision
    deficiency ``cvd`` (a key of _CVD) or normal vision."""
    import math

    rgb = [int(colour[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
    rgb = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    if cvd is not None:
        rgb = [min(1.0, max(0.0, sum(m * c for m, c in zip(row, rgb)))) for row in _CVD[cvd]]
    xyz = [sum(m * c for m, c in zip(row, rgb)) / white for row, white in zip(
        ((0.4124564, 0.3575761, 0.1804375), (0.2126729, 0.7151522, 0.0721750), (0.0193339, 0.1191920, 0.9503041)),
        (0.95047, 1.0, 1.08883))]
    f = [math.cbrt(v) if v > (6 / 29) ** 3 else v / (3 * (6 / 29) ** 2) + 4 / 29 for v in xyz]
    return 116.0 * f[1] - 16.0, 500.0 * (f[0] - f[1]), 200.0 * (f[1] - f[2])


def _ciede2000(lab1, lab2):
    """CIEDE2000 colour difference (Sharma, Wu and Dalal 2005)."""
    import math

    (l1, a1, b1), (l2, a2, b2) = lab1, lab2
    c_mean = (math.hypot(a1, b1) + math.hypot(a2, b2)) / 2.0
    g = 0.5 * (1.0 - math.sqrt(c_mean ** 7 / (c_mean ** 7 + 25.0 ** 7)))
    a1, a2 = (1.0 + g) * a1, (1.0 + g) * a2
    c1, c2 = math.hypot(a1, b1), math.hypot(a2, b2)
    h1 = math.degrees(math.atan2(b1, a1)) % 360.0 if c1 else 0.0
    h2 = math.degrees(math.atan2(b2, a2)) % 360.0 if c2 else 0.0
    dh = 0.0 if c1 * c2 == 0 else (h2 - h1 if abs(h2 - h1) <= 180 else h2 - h1 - 360 if h2 > h1 else h2 - h1 + 360)
    d_l, d_c = l2 - l1, c2 - c1
    d_h = 2.0 * math.sqrt(c1 * c2) * math.sin(math.radians(dh / 2.0))
    l_mean, c_mean = (l1 + l2) / 2.0, (c1 + c2) / 2.0
    if c1 * c2 == 0:
        h_mean = h1 + h2
    elif abs(h1 - h2) <= 180:
        h_mean = (h1 + h2) / 2.0
    else:
        h_mean = (h1 + h2 + 360.0) / 2.0 if h1 + h2 < 360 else (h1 + h2 - 360.0) / 2.0
    t = (1 - 0.17 * math.cos(math.radians(h_mean - 30)) + 0.24 * math.cos(math.radians(2 * h_mean))
         + 0.32 * math.cos(math.radians(3 * h_mean + 6)) - 0.20 * math.cos(math.radians(4 * h_mean - 63)))
    s_l = 1 + 0.015 * (l_mean - 50) ** 2 / math.sqrt(20 + (l_mean - 50) ** 2)
    s_c, s_h = 1 + 0.045 * c_mean, 1 + 0.015 * c_mean * t
    r_t = (-math.sin(math.radians(60 * math.exp(-(((h_mean - 275) / 25) ** 2))))
           * 2 * math.sqrt(c_mean ** 7 / (c_mean ** 7 + 25.0 ** 7)))
    return math.sqrt((d_l / s_l) ** 2 + (d_c / s_c) ** 2 + (d_h / s_h) ** 2 + r_t * (d_c / s_c) * (d_h / s_h))


def test_ciede2000_matches_the_published_test_data():
    """Three pairs of Sharma, Wu and Dalal's (2005) test data, so the
    palette test below measures what it says."""
    assert _ciede2000((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485)) == pytest.approx(2.0425, abs=1e-4)
    assert _ciede2000((50.0, 2.5, 0.0), (73.0, 25.0, -18.0)) == pytest.approx(27.1492, abs=1e-4)
    assert _ciede2000((2.0776, 0.0795, -1.1350), (0.9033, -0.0636, -0.5514)) == pytest.approx(0.9082, abs=1e-4)


def test_the_series_a_plot_shows_together_differ_in_every_pair():
    """UI audit UI-12: a position plot drew x and z in two near-identical
    purples. Every pair of the first six slots (the most series a standard
    plot shows: x, y, z, a quaternion's four parts, the timeline's six
    event kinds) differs by CIEDE2000 Delta E 18 or more, and still by 10
    with protanopia or deuteranopia and 7.5 with tritanopia; x, y and z by
    30, and 20 with each deficiency. Each is 3:1 or more against the plot
    background, in both themes."""
    import itertools

    from spacemissionstudio.gui.theme import palettes, tokens

    assert palettes.SHOWN_TOGETHER == 6
    floors = {None: (18.0, 30.0), "protan": (10.0, 20.0), "deutan": (10.0, 20.0), "tritan": (7.5, 20.0)}
    for mode in tokens.MODES:
        series = palettes.CATEGORICAL[mode][:palettes.SHOWN_TOGETHER]
        surface = tokens.tokens(mode)["bg.surface"]
        for colour in series:
            assert tokens.contrast(colour, surface) >= 3.0, (mode, colour)
        for cvd, (floor, xyz_floor) in floors.items():
            for (i, a), (j, b) in itertools.combinations(enumerate(series), 2):
                difference = _ciede2000(_cielab(a, cvd), _cielab(b, cvd))
                assert difference >= (xyz_floor if j < 3 else floor), (mode, cvd or "normal", i, j, round(difference, 1))


def test_what_is_drawn_on_space_takes_the_dark_steps():
    """The 3D View and the live map draw spacecraft on black space or the
    Earth's image in both themes, so they take the dark steps, made for a
    dark surface: each at least 3:1 against black."""
    from spacemissionstudio.gui.theme import palettes, tokens
    from spacemissionstudio.gui.theme.ground_map_style import ground_map_style
    from spacemissionstudio.gui.theme.mission_view_style import mission_view_style

    for mode in tokens.MODES:
        assert mission_view_style(mode)["crafts"] == ground_map_style(mode)["crafts"] == palettes.depicted()
    assert palettes.depicted() == palettes.CATEGORICAL["dark"]
    assert all(tokens.contrast(colour, palettes.SPACE_COLOUR) >= 3.0 for colour in palettes.depicted())


def test_the_charts_share_the_live_series_colours(restored_theme):
    """Plots and the event timeline read the theme's categorical palette,
    one slot per event kind, and follow a theme change."""
    from spacemissionstudio.engine import events
    from spacemissionstudio.gui import event_timeline_widget, results_widget
    from spacemissionstudio.gui.theme import SERIES_COLORS, apply_theme, palettes

    for mode in ("light", "dark"):
        apply_theme(restored_theme, mode)
        assert results_widget._SERIES_COLORS == SERIES_COLORS == palettes.CATEGORICAL[mode]
        assert [event_timeline_widget.kind_colour(kind) for kind in events.KINDS] == SERIES_COLORS[:len(events.KINDS)]


def test_set_role_restyles_a_shown_widget(qtbot, restored_theme):
    """A label's tone set after it is shown takes effect at once."""
    from PySide6.QtWidgets import QLabel

    from spacemissionstudio.gui.theme import TOKENS, apply_theme, set_role

    apply_theme(restored_theme, "light")
    label = QLabel("value")
    qtbot.addWidget(label)
    label.show()
    restored_theme.processEvents()
    set_role(label, tone="critical")
    assert label.palette().color(label.foregroundRole()).name().upper() == TOKENS["status.critical.text"]
    set_role(label, tone=None)
    assert label.palette().color(label.foregroundRole()).name().upper() == TOKENS["text.primary"]


def test_the_primary_run_button_draws_its_icon_on_the_fill(qtbot, restored_theme):
    """The Run button is filled with the accent, so its icon is drawn in
    text.on_accent: the action's accent icon would vanish on the fill. It
    stays so after the action changes."""
    from PySide6.QtWidgets import QToolButton

    from spacemissionstudio.gui.main_window import MainWindow
    from spacemissionstudio.gui.theme import TOKENS, apply_theme

    apply_theme(restored_theme, "light")
    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    button = window.findChild(QToolButton, "primaryToolButton")
    window.run_action.setToolTip("changed")  # an action change copies the action's icon onto the button
    qtbot.wait(10)
    image = button.icon().pixmap(32, 32).toImage()
    ink = max((image.pixelColor(x, y) for x in range(32) for y in range(32)), key=lambda c: c.alpha())
    assert ink.name().upper() == TOKENS["text.on_accent"]
