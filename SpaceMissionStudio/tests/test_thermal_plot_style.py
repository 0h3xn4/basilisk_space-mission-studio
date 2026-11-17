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
"""The thermal plots' two looks (decisions T-31 and T-40) and the 3D
scene's part per triangle (T-42): the exported SVG text stays the 2.11.0
picture byte for byte; a ``style`` and a size give the screen copy, in
the theme's colours and fonts at the view's size; each triangle of a
spacecraft's mesh names its 3D model part."""

import hashlib
import xml.etree.ElementTree as ET
from types import SimpleNamespace as NS

import numpy as np
import pytest

from spacemissionstudio import api
from spacemissionstudio.engine import scene3d
from spacemissionstudio.thermal import plots

_SVG = "{http://www.w3.org/2000/svg}"
_PERIOD_S = 5800.0  # [s] an invented orbit period


def _case():
    """An invented case: three nodes over three orbits, 2,400 samples (so
    the lines are decimated), the battery with operating and survival
    ranges, and four heat flows."""
    t = np.linspace(0.0, 3 * _PERIOD_S, 2400)
    names = ["bus", "battery", "radiator"]
    temperatures = np.column_stack([10 + 15 * np.sin(2 * np.pi * t / _PERIOD_S + k) + 5 * k for k in range(3)])
    flows = {n: {"solar": 40 * np.clip(np.sin(2 * np.pi * t / _PERIOD_S), 0, None), "emitted": -30 + 0 * t,
                 "albedo": 0 * t, "conduction": 5 * np.cos(2 * np.pi * t / _PERIOD_S)} for n in names}
    summary = [NS(name="battery", operating_c=[0.0, 30.0], survival_c=[-10.0, 40.0]),
               NS(name="bus", operating_c=None, survival_c=None), NS(name="radiator", operating_c=None, survival_c=None)]
    return NS(name="nominal", time_s=t, network=NS(names=names), summary=summary, flows=flows,
              temperature_c=lambda n: temperatures[:, names.index(n)])


_STYLE = {"background": "#111418", "text": "#E6E8EB", "muted": "#A1A7B0", "grid": "#2A2F36", "frame": "#4A515B",
          "font": "Inter", "mono": "JetBrains Mono", "size": 12, "title_size": 15, "title_weight": 600,
          "colours": ["#CA4ED3", "#B36C0D", "#8B63B6"], "operating": "#00A45D", "survival": "#E5A50A"}


def test_the_exported_plots_are_the_2_11_pictures_byte_for_byte():
    """SHA-256 of the default SVG text (900 x 420, white, DejaVu Sans, the
    Okabe-Ito colours), taken from 2.11.0's code before the style
    argument existed: all nodes, one node with its bands, its heat flows."""
    case = _case()
    texts = (plots.temperature_svg(case), plots.temperature_svg(case, ["battery"], "battery"),
             plots.heat_flow_svg(case, "battery"))
    assert [hashlib.sha256(t.encode()).hexdigest() for t in texts] == [
        "f41e54a24123177086e1c496b875f52831bd137bc9f1ffdd7b7726acad6f99f1",
        "03aa226a086da462f14ab8cfa79652bb4d0032bebddf3bc0bbe08bbe71259907",
        "751b881e2c926ed2846fa3bb1878fb4c2c1fbcbc13b55189d83137dc619e8b07"]


def test_a_style_and_a_size_make_the_screen_copy():
    """At the size asked (no fixed 900 x 420), on the style's background,
    in its fonts and colours; the same lines, bands and legend as the
    file; no colour of the file's own left."""
    case = _case()
    text = plots.temperature_svg(case, ["battery"], "battery", 1312, 512, style=_STYLE)
    root = ET.fromstring(text)
    assert (root.get("width"), root.get("height"), root.get("viewBox")) == ("1312", "512", "0 0 1312 512")
    assert root.get("font-family") == "Inter" and root.get("fill") == "#E6E8EB"
    assert root.find(f"{_SVG}rect").get("fill") == "#111418"
    numbers = [e for e in root.iter(f"{_SVG}text") if e.get("font-family") == "JetBrains Mono"]
    assert numbers and all(e.get("fill") == "#A1A7B0" for e in numbers)  # the tick labels
    title = root.find(f"{_SVG}text")
    assert (title.get("font-size"), title.get("font-weight")) == ("15", "600")
    assert "battery operating" in text and "battery survival" in text
    assert "#00A45D" in text and "#E5A50A" in text and "#CA4ED3" in text
    for colour in ("#ffffff", "#e3e3e3", "#555555", "#0072B2", "#009E73", "#D55E00", "DejaVu"):
        assert colour not in text
    default = ET.fromstring(plots.temperature_svg(case, ["battery"], "battery"))
    assert len(root.findall(f"{_SVG}polyline")) == len(default.findall(f"{_SVG}polyline"))
    flows = ET.fromstring(plots.heat_flow_svg(case, "battery", 700, 300, style=_STYLE))
    assert flows.get("viewBox") == "0 0 700 300"
    assert [p.get("stroke") for p in flows.findall(f"{_SVG}polyline")] == ["#CA4ED3", "#B36C0D", "#8B63B6"]


def test_more_series_than_colours_are_dashed_not_cycled():
    """Past the style's colours a series is dashed, so two lines never
    look the same."""
    case = _case()
    style = dict(_STYLE, colours=["#CA4ED3", "#B36C0D"])
    root = ET.fromstring(plots.temperature_svg(case, style=style))
    dashes = [p.get("stroke-dasharray") for p in root.findall(f"{_SVG}polyline")]
    assert dashes == [None, None, "6 3"]


def test_each_triangle_of_the_scene_names_its_part():
    """Template 33's microsatellite: the scene's mesh keeps, per triangle,
    which visible part of the 3D model it belongs to, in the mesh's order;
    the four values of spacecraft_mesh are unchanged."""
    path = api.template("33_microsat_thermal")
    sc = api.load(path).spacecraft[0]
    vertices, triangles, colours, notes, names, owner = scene3d.spacecraft_mesh_parts(sc, path.parent)
    assert [a.tolist() if hasattr(a, "tolist") else a for a in scene3d.spacecraft_mesh(sc, path.parent)] == \
        [vertices.tolist(), triangles.tolist(), colours, notes]
    assert len(owner) == len(triangles) and owner.min() == 0 and owner.max() == len(names) - 1
    assert set(names) == {p.name for p in sc.model.parts if p.visible}
    assert np.all(np.diff(owner) >= 0)  # the parts' triangles in turn
    start = 0
    for index, part in enumerate(names):
        count = int(np.sum(owner == index))
        assert len(set(colours[start:start + count])) == 1  # one part, one colour
        start += count


def test_a_spacecraft_without_a_model_has_no_parts():
    sc = api.load(api.template("01_two_body_circular_orbit")).spacecraft[0]
    *_mesh, names, owner = scene3d.spacecraft_mesh_parts(sc)
    assert names == [] and owner.tolist() == [-1] * 12


def test_the_temperature_scale_is_plotly_s_rdbu_reversed():
    """theme.palettes' scale is the one the Thermal page's 3D model takes
    by name, so the two views agree colour for colour."""
    pytest.importorskip("PySide6")
    from plotly.colors import sample_colorscale

    from spacemissionstudio.gui.theme.palettes import temperature_rgb

    for fraction in np.linspace(0.0, 1.0, 41):
        expected = [float(v) for v in sample_colorscale("RdBu_r", [fraction])[0][4:-1].split(",")]
        np.testing.assert_allclose(temperature_rgb(fraction), expected, atol=0.51)
    assert temperature_rgb(np.array([[-1.0, 2.0]])).shape == (1, 2, 3)  # clipped, any shape
