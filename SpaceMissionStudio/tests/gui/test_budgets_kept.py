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
"""The window keeps a spacecraft's ``budgets`` section (SRS-F-31): no form
of the spacecraft editor edits it yet (the Budgets area comes in phase
1's second part), so editing a spacecraft must not drop it."""

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import budgets_fixtures as fx  # noqa: E402


def test_the_spacecraft_editor_keeps_the_budgets_section(qtbot):
    """A spacecraft with a section comes back from the spacecraft editor
    with the same section, and one without it with none."""
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog

    for template in (fx.STARTER, fx.MODEL_TEMPLATE):
        sc = fx.scenario(template=template).spacecraft[0]
        dialog = SpacecraftEditorDialog(config=copy.deepcopy(sc))
        qtbot.addWidget(dialog)
        config = dialog.to_dataclass()
        assert config.budgets == sc.budgets and config.budgets is not sc.budgets
    from spacemissionstudio.schema import load_scenario

    plain = SpacecraftEditorDialog(config=load_scenario(fx.STARTER).spacecraft[0])
    qtbot.addWidget(plain)
    assert plain.to_dataclass().budgets is None


def test_a_problem_in_the_section_has_a_place_in_the_editor(qtbot):
    """Decision B-15: the Power tab shows a read-only summary of the
    section (items, modes, buses), only when there is one; a problem in
    the section opens it."""
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog
    from spacemissionstudio.schema import load_scenario

    dialog = SpacecraftEditorDialog(config=fx.scenario().spacecraft[0])
    qtbot.addWidget(dialog)
    assert dialog.field_widget("budgets") is dialog.budgets_group
    assert dialog.field_widget("budgets.equipment[OBC].mass_kg") is dialog.budgets_group
    assert not dialog.budgets_group.isHidden()
    assert [w.text() for w in (dialog.budgets_items, dialog.budgets_modes, dialog.budgets_buses)] == ["3", "2", "1"]
    plain = SpacecraftEditorDialog(config=load_scenario(fx.STARTER).spacecraft[0])
    qtbot.addWidget(plain)
    assert plain.budgets_group.isHidden()
