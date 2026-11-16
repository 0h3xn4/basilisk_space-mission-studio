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
"""The thermal view of the material library (thermal Phase 2, T-38):
every coating's optics within [0, 1] with its source, each UV-aged
coating no less absorbing than the coating it ages, the thermal model
reading a coating's optics with that source, and the doc's table listing
every key with the code's values. No Basilisk."""

import re
from pathlib import Path

import pytest

from spacemissionstudio.config import materials
from spacemissionstudio.thermal import library

_DOC = Path(__file__).resolve().parents[1] / "docs" / "models" / "materials.md"


def test_every_coating_has_sourced_optics_within_their_range():
    coatings = [m for m in materials.MATERIALS.values() if m.solar_absorptance is not None]
    assert len(coatings) == 38  # 12 in Phase 1, 26 added in Phase 2
    for m in coatings:
        assert 0.0 <= m.solar_absorptance.value <= 1.0 and 0.0 <= m.emissivity.value <= 1.0, m.name
        assert m.solar_absorptance.source and m.emissivity.source == m.solar_absorptance.source


@pytest.mark.parametrize(("aged", "base"), [("white_paint_a276_uv_1036esh", "white_paint_a276"),
                                            ("white_paint_z202_uv_1000esh", "white_paint_z202"),
                                            ("kapton_al_siox_1mil_uv_2400esh", "kapton_al_siox_1mil")])
def test_a_uv_aged_coating_absorbs_at_least_as_much(aged, base):
    a, b = materials.MATERIALS[aged], materials.MATERIALS[base]
    assert a.solar_absorptance.value > b.solar_absorptance.value
    assert a.emissivity.value == b.emissivity.value


def test_the_thermal_model_reads_a_coating_with_its_source():
    found = library.absorptance("second_surface_mirror_silver")
    assert found.value == 0.07 and "RP-1121" in found.source and "Composite Coatings" in found.source
    assert library.conductivity("aluminium_6061_t6") is None  # not sourced (T-38): given per conductor


def test_the_doc_table_lists_every_key_with_its_values():
    rows = {match.group(1): match.group(0) for match in re.finditer(r"^\| `([a-z0-9_]+)` \|.*$",
                                                                    _DOC.read_text(encoding="utf-8"), re.M)}
    assert set(rows) == set(materials.MATERIALS)
    for m in materials.MATERIALS.values():
        if m.solar_absorptance is not None:
            assert f"| {m.solar_absorptance.value:g} [" in rows[m.name], m.name
