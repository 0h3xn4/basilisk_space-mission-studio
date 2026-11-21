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

"""Every dialog fits a 1280 x 720 screen (UI audit batch B1).

On a 1280 x 720 screen the 3D model editor asked for 967 px and the
IDM-CIC import for 820 px: OK and Cancel were off the screen (UI-01,
UI-02). ``gui.theme.dialogs`` now limits a dialog to the screen, and tall
content scrolls. These tests open every dialog of the GUI on a screen of
that size and check its minimum size and its size. A new dialog class
must get an entry in :data:`_FACTORIES`, so it is checked too.

The tests also check the other B1 defects: the model editor's part form
(UI-28) and Equipment tab (UI-29), the SIL dialog (UI-46) and the
Customize dialog (UI-47).
"""

import importlib
import pkgutil
from pathlib import Path

import pytest

pytestmark = pytest.mark.requires_gui

_TEMPLATES = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"
_SCREEN = (1280, 720)  # [px] the smallest screen the GUI supports


def _template(name):
    from spacemissionstudio.schema import load_scenario

    return load_scenario(next(_TEMPLATES.glob(f"{name}_*.json")))


def _sensor_dialog(_tmp_path):
    from spacemissionstudio.gui.sensor_actuator_editor import _ItemEditorDialog
    from spacemissionstudio.schema.scenario import SUPPORTED_SENSOR_KINDS, SensorConfig

    return _ItemEditorDialog(SensorConfig, SUPPORTED_SENSOR_KINDS)


def _orbit_switch(_tmp_path):
    from spacemissionstudio.gui.orbit_ic_widget import OrbitSwitchDialog
    from spacemissionstudio.schema.scenario import OrbitIC

    elements = OrbitIC(type="classical_elements", semi_major_axis_km=7000.0, eccentricity=0.001,
                       inclination_deg=97.5, raan_deg=10.0, arg_periapsis_deg=0.0, true_anomaly_deg=0.0)
    converted = OrbitIC(type="cartesian", position_km=[-1197.805, -1598.774, 6628.610],  # [km]
                        velocity_km_s=[1.092724, 7.253268, 1.952497])  # [km/s]
    return OrbitSwitchDialog(None, "Classical elements", "Cartesian state", elements, converted, converted, "")


def _model_editor(_tmp_path):
    from spacemissionstudio.gui.model_editor_dialog import ModelEditorDialog

    spacecraft = _template("33").spacecraft[0]
    return ModelEditorDialog(spacecraft.model, spacecraft_name=spacecraft.name, devices=spacecraft)


def _spacecraft_editor(_tmp_path):
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog

    scenario = _template("19")
    return SpacecraftEditorDialog(scenario.spacecraft[0],
                                  ground_station_names=[gs.name for gs in scenario.ground_stations])


def _propagation(_tmp_path):
    from spacemissionstudio.gui.propagation_setup_dialog import PropagationSetupDialog

    scenario = _template("02")
    return PropagationSetupDialog(scenario.gravity, scenario.sim_settings, scenario.space_weather)


def _formation(module, cls):
    def make(_tmp_path):
        scenario = _template("05")
        dialog_cls = getattr(importlib.import_module(f"spacemissionstudio.gui.{module}"), cls)
        return dialog_cls([sc.name for sc in scenario.spacecraft], spacecraft=scenario.spacecraft)
    return make


def _wizard(template):
    def make(_tmp_path):
        from spacemissionstudio.gui.template_wizard import TemplateCustomizeWizard, get_wizard_spec

        path = next(_TEMPLATES.glob(f"{template}_*.json"))
        return TemplateCustomizeWizard(_template(template), get_wizard_spec(path.name))
    return make


def _simple(module, cls, *args):
    def make(_tmp_path):
        return getattr(importlib.import_module(f"spacemissionstudio.gui.{module}"), cls)(*args)
    return make


def _idm_import(tmp_path):
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/, for idm_fixtures
    from idm_fixtures import write_idm
    from spacemissionstudio.gui.idm_import_dialog import IdmImportDialog

    return IdmImportDialog(write_idm(tmp_path / "demosat.idm"))


# Every QDialog class of the GUI: "module.Class" -> a factory taking tmp_path.
_FACTORIES = {
    "help_dialog.ManualDialog": _simple("help_dialog", "ManualDialog"),
    "mission_sequence_editor._CommandEditorDialog": lambda _p: importlib.import_module(
        "spacemissionstudio.gui.mission_sequence_editor")._CommandEditorDialog(spacecraft_names=["sat-1"]),
    "command_palette.CommandPalette": _simple("command_palette", "CommandPalette", []),
    "ccsds_dialogs.OemOptionsDialog": _simple("ccsds_dialogs", "OemOptionsDialog", 10),
    "ccsds_dialogs.CcsdsCheckDialog": lambda p: importlib.import_module(
        "spacemissionstudio.gui.ccsds_dialogs").CcsdsCheckDialog(p / "missing.oem"),
    "orbit_ic_widget.OrbitSwitchDialog": _orbit_switch,
    "phasing_formation_dialog.PhasingFormationDialog": _formation("phasing_formation_dialog",
                                                                  "PhasingFormationDialog"),
    "licences_dialog.LicencesDialog": _simple("licences_dialog", "LicencesDialog"),
    "about_dialog.AboutDialog": _simple("about_dialog", "AboutDialog"),
    "change_history_dialog.ChangeHistoryDialog": lambda p: importlib.import_module(
        "spacemissionstudio.gui.change_history_dialog").ChangeHistoryDialog(p / "scenario.json"),
    "provenance_view.ProvenanceDialog": _simple("provenance_view", "ProvenanceDialog", "a run", None),
    "model_editor_dialog._ImportOptionsDialog": lambda p: importlib.import_module(
        "spacemissionstudio.gui.model_editor_dialog")._ImportOptionsDialog(p / "part.obj", True),
    "model_editor_dialog.ModelEditorDialog": _model_editor,
    "monte_carlo_editor._DispersionEditorDialog": _simple("monte_carlo_editor", "_DispersionEditorDialog",
                                                          ["sat-1"]),
    "monte_carlo_editor._RequirementEditorDialog": lambda _p: importlib.import_module(
        "spacemissionstudio.gui.monte_carlo_editor")._RequirementEditorDialog(
            ["sat-1"], importlib.import_module("spacemissionstudio.schema").MonteCarloRequirementConfig(
                "R-1", "sat-1", "lowest_altitude")),
    "startup_fetch_dialog.StartupFetchDialog": _simple("startup_fetch_dialog", "StartupFetchDialog"),
    "sensor_actuator_editor._ItemEditorDialog": _sensor_dialog,
    "facet_editor.BoxFacetDialog": _simple("facet_editor", "BoxFacetDialog"),
    "spacecraft_template_dialog.SpacecraftTemplateDialog": _simple("spacecraft_template_dialog",
                                                                   "SpacecraftTemplateDialog"),
    "roe_formation_dialog.RoeFormationDialog": _formation("roe_formation_dialog", "RoeFormationDialog"),
    "template_wizard.TemplateCustomizeWizard": _wizard("33"),
    "spacecraft_editor.SpacecraftEditorDialog": _spacecraft_editor,
    "ground_station_editor.GroundStationEditorDialog": lambda _p: importlib.import_module(
        "spacemissionstudio.gui.ground_station_editor").GroundStationEditorDialog(_template("19").ground_stations[0]),
    "constellation_dialog.WalkerConstellationDialog": _simple("constellation_dialog", "WalkerConstellationDialog",
                                                              ["sat-1"]),
    "propagation_setup_dialog.PropagationSetupDialog": _propagation,
    "sil_dialog.SilRunDialog": _simple("sil_dialog", "SilRunDialog", "sat-1"),
    "idm_import_dialog.IdmImportDialog": _idm_import,
}


def _dialog_classes() -> set[str]:
    """Every QDialog subclass defined in ``spacemissionstudio.gui``."""
    from PySide6.QtWidgets import QDialog

    import spacemissionstudio.gui as gui

    for module in pkgutil.walk_packages(gui.__path__, "spacemissionstudio.gui."):
        importlib.import_module(module.name)
    found, todo = set(), list(QDialog.__subclasses__())
    while todo:
        cls = todo.pop()
        todo += cls.__subclasses__()
        if cls.__module__.startswith("spacemissionstudio.gui."):
            found.add(f"{cls.__module__.removeprefix('spacemissionstudio.gui.')}.{cls.__qualname__}")
    return found


@pytest.fixture
def screen_1280(monkeypatch, restored_theme):
    """The application's theme (it fits every dialog as Qt polishes it) on
    a 1280 x 720 screen; returns the room a window has there."""
    from PySide6.QtCore import QRect

    from spacemissionstudio.gui.theme import apply_theme, dialogs

    apply_theme(restored_theme, "light")
    monkeypatch.setattr(dialogs, "available", lambda _widget: QRect(0, 0, *_SCREEN))
    yield dialogs.room(None)
    restored_theme.setStyle("Fusion")


def _shown(qtbot, dialog):
    from PySide6.QtWidgets import QApplication

    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)
    for _ in range(3):
        QApplication.processEvents()
    return dialog


def test_every_dialog_class_is_checked():
    """A dialog added to the GUI gets an entry in _FACTORIES."""
    assert _dialog_classes() == set(_FACTORIES)


@pytest.mark.parametrize("name", sorted(_FACTORIES))
def test_every_dialog_fits_a_1280_by_720_screen(qtbot, tmp_path, screen_1280, name):
    """Its minimum size fits the screen less the title bar, and it opens
    no larger than that, so its buttons are on the screen."""
    dialog = _shown(qtbot, _FACTORIES[name](tmp_path))
    if hasattr(dialog, "busy"):  # the IDM-CIC import: its file read and planned, its tables filled
        qtbot.waitUntil(lambda: not dialog.busy(), timeout=30000)
    minimum = dialog.minimumSize().expandedTo(dialog.minimumSizeHint())
    assert minimum.width() <= screen_1280.width() and minimum.height() <= screen_1280.height(), (
        f"{name}: minimum {minimum.toTuple()} px, room {screen_1280.toTuple()} px")
    assert dialog.width() <= screen_1280.width() and dialog.height() <= screen_1280.height(), (
        f"{name}: opens at {dialog.size().toTuple()} px, room {screen_1280.toTuple()} px")


def test_the_model_editor_part_form_needs_no_sideways_scrolling(qtbot, screen_1280):
    """UI-28: at its size on a 1280 x 720 screen the part form fits its
    column: every Position and Rotation field, the Shown box and every
    face's box with its label are in view, with no horizontal scroll bar."""
    dialog = _shown(qtbot, _model_editor(None))
    area = dialog._form_area
    assert area.widget().minimumSizeHint().width() <= area.viewport().width()
    assert not area.horizontalScrollBar().isVisible()
    widgets = dialog.part_widgets
    viewport = area.viewport()
    boxes = [*widgets["position_b_m"], *widgets["rotation_deg"], widgets["visible"],
             *(box for key, box in widgets.items() if key.startswith("face:"))]
    for box in boxes:
        right = box.mapTo(viewport, box.rect().topRight()).x()
        assert right <= viewport.width(), box.text() if hasattr(box, "text") else type(box).__name__
        assert box.width() >= box.minimumSizeHint().width()
    assert widgets["visible"].width() >= widgets["visible"].sizeHint().width()  # "Shown" in full


def test_the_equipment_tab_shows_an_empty_state_without_a_selection(qtbot):
    """UI-29: with nothing to select, the Equipment tab says so (an empty
    state with Add) instead of a disabled form; the form comes back when
    an item is added."""
    from spacemissionstudio.gui.model_equipment_tabs import EquipmentTab
    from spacemissionstudio.schema.scenario import ModelPartConfig, SpacecraftModelConfig

    model = SpacecraftModelConfig(parts=[ModelPartConfig(name="bus", shape="box", mass_kg=50.0,
                                                         dimensions_m={"x": 1.0, "y": 1.0, "z": 1.0})])
    tab = EquipmentTab(model)
    qtbot.addWidget(tab)
    tab.show()
    assert tab.empty_state.isVisible() and not tab.form_widget.isVisible()
    assert tab.empty_state.button.isVisible() and tab.empty_state.button.menu() is tab.add_button.menu()
    tab.add_item("camera")
    assert tab.form_widget.isVisible() and tab.form_widget.isEnabled() and not tab.empty_state.isVisible()
    tab.delete_item()
    assert tab.empty_state.isVisible() and not tab.form_widget.isVisible()


def test_the_sil_dialog_opens_without_an_error(qtbot, screen_1280, tmp_path):
    """UI-46: no red error before the user typed anything, no empty
    SHA-256 row, and the field shows its whole placeholder. A program
    that is not there is reported as before."""
    from spacemissionstudio.gui.sil_dialog import SilRunDialog

    dialog = _shown(qtbot, SilRunDialog("sat-1"))
    assert dialog.problem_label.text() == "" and not dialog.problem_label.isVisible()
    assert not dialog.hash_label.isVisible() and not dialog.run_button.isEnabled()
    edit = dialog.path_edit
    assert edit.fontMetrics().horizontalAdvance(edit.placeholderText()) < edit.contentsRect().width()
    edit.setText(str(tmp_path / "fsw_host"))
    assert dialog.problem_label.isVisible() and dialog.problem_label.text()
    edit.setText("")
    assert not dialog.problem_label.isVisible() and not dialog.hash_label.isVisible()


@pytest.mark.parametrize("template", ["19", "33"])
def test_the_customize_dialog_lines_up_its_labels(qtbot, screen_1280, template):
    """UI-47: the contents list has rows of the theme's height and its
    first heading in full; every section's labels share one width."""
    from spacemissionstudio.gui.theme import ROW_HEIGHT

    wizard = _shown(qtbot, _wizard(template)(None))
    sections = wizard._sections
    first = sections.visualItemRect(sections.item(0))
    assert first.top() >= 0 and first.height() >= ROW_HEIGHT
    assert all(sections.visualItemRect(sections.item(row)).height() >= ROW_HEIGHT for row in range(sections.count()))
    widths = {label.width() for page in wizard._field_pages for label in page.labels() if label.isVisible()}
    assert len(widths) == 1, sorted(widths)
