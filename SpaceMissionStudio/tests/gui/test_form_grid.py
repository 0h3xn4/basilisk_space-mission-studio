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

"""One form grid and one page inset (UI audit B6), measured in a shown
1280 x 720 window with the app's theme:

- UI-04: the Monte Carlo page's lines sit at the top, not in the middle;
- UI-13: the 3D model's thermal editor: its tab row fits, its tables are
  model/view grids without grid lines, and nothing scrolls sideways;
- UI-16: every page of every area starts its content at one inset;
- UI-18: the Scenario tree shows its longest node whole;
- UI-26: on each Scenario page and Run › End of Life the fields start at
  one x, and no drop-down list or number field is wider than its limit;
- UI-42: a disabled input on the main pages says why in its tooltip;
- UI-52: the Scenario area's first form is "General", and its content
  starts at the inset from the tree;
- UI-53: the third bodies are check boxes in the form, not a framed box.

Sizes are read from widgets that are shown and laid out (a hidden widget
is never laid out, and Qt's default size differs between platforms);
widths that depend on text leave room for wider fonts."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.requires_gui

_TEMPLATES = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"


@pytest.fixture(scope="module")
def _shared_window(qapp, tmp_path_factory):
    """One 1280 x 720 main window with the app's theme for the module (as
    tests/gui/test_forms.py: the theme is applied once), in a home of its
    own, without the Inspector and Problems panels: the default of a new
    window on a screen narrower than 1600 px."""
    with pytest.MonkeyPatch.context() as patch:
        home = tmp_path_factory.mktemp("home")
        patch.setattr(Path, "home", lambda: home)
        yield from _made_shared_window(qapp)


def _made_shared_window(qapp):
    import gc

    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication

    from spacemissionstudio.gui.main_window import MainWindow
    from spacemissionstudio.gui.theme import apply_theme, state

    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    gc.collect()
    saved = (qapp.font(), qapp.palette(), qapp.styleSheet())
    apply_theme(qapp, "light")
    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    window._confirm_discard_unsaved = lambda: True
    window.resize(1280, 720)  # [px]
    window.show()
    window.side_dock.hide()
    window.problems_dock.hide()
    QApplication.processEvents()
    yield window
    window._mark_clean()
    window.close()
    window.deleteLater()
    QApplication.processEvents()
    state.select("light")
    qapp.setStyleSheet(saved[2])
    qapp.setPalette(saved[1])
    qapp.setFont(saved[0])


@pytest.fixture
def window(_shared_window):
    """The module's window, its scenario discarded after the test."""
    yield _shared_window
    _shared_window._mark_clean()


def _settle(qtbot, widget=None, ms: int = 30) -> None:
    """Let the layouts settle (the form grid lines up on the next turn of
    the event loop)."""
    from PySide6.QtWidgets import QApplication

    if widget is not None:
        qtbot.waitUntil(widget.isVisible, timeout=5000)
    for _ in range(3):
        QApplication.processEvents()
        qtbot.wait(ms)


def _open(window, qtbot, name: str) -> None:
    assert window.open_path(_TEMPLATES / name)
    window.shell.show_area("scenario")
    _settle(qtbot)


def _tree_pages(window, qtbot):
    """Every page of the Scenario tree, shown in turn: yields (path, page)."""
    tree = window.scenario_editor.page_tree
    for path, item in tree.paths():
        window._show_tree_item(item)
        page = tree.stack.currentWidget()
        _settle(qtbot, page)
        yield path, page


def _area_pages(window, qtbot):
    """Every page of every area but Scenario's tree: each tab of a tabbed
    area, or the area's content. Yields (name, page)."""
    from PySide6.QtWidgets import QTabWidget

    for area in window.shell.page_areas():
        if area.id == "scenario":
            continue
        window.shell.show_area(area.id)
        content = area.page.content
        if isinstance(content, QTabWidget):
            for index in range(content.count()):
                content.setCurrentIndex(index)
                page = content.widget(index)
                _settle(qtbot, page)
                yield f"{area.label} › {content.tabText(index)}", page
        else:
            _settle(qtbot, content)
            yield area.label, content


# -- UI-16: one page inset ---------------------------------------------------------------------

def _content_widgets(page):
    """What a page shows: its leaves (labels, buttons, fields, views, tab
    rows), titled groups, cards and empty states, looked for through the
    containers and the page's own frameless scroll area."""
    from PySide6.QtWidgets import (QAbstractButton, QAbstractScrollArea, QAbstractSlider, QAbstractSpinBox, QComboBox,
                                   QFrame, QGroupBox, QLabel, QLineEdit, QProgressBar, QScrollArea, QScrollBar,
                                   QSizeGrip, QSplitterHandle, QTabBar, QWidget)

    from spacemissionstudio.gui.widgets import EmptyState

    leaves = (QLabel, QAbstractButton, QAbstractSpinBox, QComboBox, QLineEdit, QTabBar, QProgressBar, QAbstractSlider,
              EmptyState)
    found, pending = [], [page]
    while pending:
        widget = pending.pop()
        for child in widget.children():
            if (not isinstance(child, QWidget) or child.isWindow() or not child.isVisible()
                    or isinstance(child, (QScrollBar, QSizeGrip, QSplitterHandle))
                    or child.width() <= 1 or child.height() <= 1):
                continue
            if isinstance(child, QScrollArea) and child.frameShape() == QFrame.Shape.NoFrame and child.widget():
                pending.append(child.widget())
            elif (isinstance(child, leaves) or (isinstance(child, QGroupBox) and child.title())
                  or (isinstance(child, QAbstractScrollArea) and not isinstance(child, QScrollArea))
                  or child.property("role") == "card" or "WebEngineView" in type(child).__name__):
                found.append(child)
            else:
                pending.append(child)
    return found


def _content_start(page):
    """(x, y) [px] of the top-left of what ``page`` shows, in its coordinates."""
    from PySide6.QtCore import QPoint

    points = [widget.mapTo(page, QPoint(0, 0)) for widget in _content_widgets(page)]
    return (min(p.x() for p in points), min(p.y() for p in points)) if points else None


def test_every_page_of_every_area_starts_its_content_at_one_inset(window, qtbot):
    """Each tab of Run, Results, Budgets and Reports, Home, Timeline and
    Settings, each page of the Scenario tree and the JSON page start their
    content at theme.PAGE_INSET from the page's left and top edges (Output,
    JSON and Flight Software had none, others 9, 12, 24 or 25 px)."""
    from spacemissionstudio.gui.theme import PAGE_INSET

    _open(window, qtbot, "07_attitude_pointing_with_adcs_hardware.json")
    starts = {name: _content_start(page) for name, page in _area_pages(window, qtbot)}
    window.shell.show_area("scenario")
    starts.update({f"Scenario › {path}": _content_start(page) for path, page in _tree_pages(window, qtbot)})
    editor = window.scenario_editor
    editor.set_json_mode(True)
    _settle(qtbot, editor.json_page)
    starts["Scenario › JSON"] = _content_start(editor.json_page)
    editor.set_json_mode(False)
    assert len(starts) > 30
    assert {name: start for name, start in starts.items() if start != (PAGE_INSET, PAGE_INSET)} == {}


# -- UI-52: General ----------------------------------------------------------------------------

def test_the_scenario_areas_first_form_is_general_and_starts_at_the_inset(window, qtbot):
    """The node is General: "Scenario" is the area's title and the
    breadcrumb's first word, not the node's or a group's too. The form
    starts at the page inset from the tree, not 4 px from it."""
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QGroupBox, QLabel

    from spacemissionstudio.gui.theme import PAGE_INSET

    _open(window, qtbot, "01_two_body_circular_orbit.json")
    editor = window.scenario_editor
    tree = editor.page_tree
    assert editor.scenario_item.text(0) == "General"
    assert "General" in dict(tree.paths())
    editor.show_scenario_page()
    _settle(qtbot, editor.scenario_page)
    assert window.top_bar.breadcrumb_label.text() == "Scenario › General"
    page = editor.scenario_page
    shown = [w.text() for w in page.findChildren(QLabel) if w.isVisible()]
    shown += [w.title() for w in page.findChildren(QGroupBox) if w.isVisible()]
    assert "Scenario" not in shown
    area = window.shell.page("scenario")
    tree_right = tree.tree.mapTo(area, QPoint(tree.tree.width(), 0)).x()
    name_label = next(w for w in page.findChildren(QLabel) if w.text() == "Name")
    assert name_label.mapTo(area, QPoint(0, 0)).x() - tree_right >= PAGE_INSET


# -- UI-18: the tree's width -------------------------------------------------------------------

def test_the_scenario_tree_shows_its_longest_node_whole(window, qtbot):
    """At 1280 x 720 every node of the tree, the sections of a spacecraft
    ("Power / propulsion / link budget") included, has room for its whole
    name; the tree stays narrower than a third of the window."""
    from PySide6.QtWidgets import QTreeWidgetItemIterator

    _open(window, qtbot, "07_attitude_pointing_with_adcs_hardware.json")
    tree = window.scenario_editor.page_tree.tree
    tree.expandAll()
    _settle(qtbot, tree)
    metrics = tree.fontMetrics()
    cut = []
    iterator = QTreeWidgetItemIterator(tree)
    while iterator.value() is not None:
        item = iterator.value()
        rect = tree.visualItemRect(item)
        # the item's padding (theme/qss.py) on each side of the text
        if rect.x() + metrics.horizontalAdvance(item.text(0)) + 12 > tree.viewport().width():
            cut.append(item.text(0))
        iterator += 1
    assert cut == []
    assert tree.width() < 1280 / 3


# -- UI-26: one field column, fields at their widths -------------------------------------------

def _field_columns(page):
    """{x: [label, ...]} [px]: where the fields of ``page``'s form rows
    start, in its coordinates. Rows whose field wrapped under its label,
    and forms inside another form's field, are left out."""
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QCheckBox, QFormLayout, QLabel, QWidget

    from spacemissionstudio.gui.widgets import form_rows, grid_forms

    columns = {}
    for form in grid_forms(page):
        for roles in form_rows(form).values():
            label, field = roles.get(QFormLayout.ItemRole.LabelRole), roles.get(QFormLayout.ItemRole.FieldRole)
            if (not isinstance(label, (QLabel, QCheckBox)) or not label.isVisible() or not label.text()
                    or field is None):
                continue
            if isinstance(field, QWidget):
                if not field.isVisible():
                    continue
                corner = field.mapTo(page, QPoint(0, 0))
            else:
                if field.geometry().width() <= 0:
                    continue
                corner = form.parentWidget().mapTo(page, field.geometry().topLeft())
            if corner.y() >= label.mapTo(page, QPoint(0, label.height())).y():
                continue  # wrapped under its label
            columns.setdefault(corner.x(), []).append(label.text())
    return columns


def _too_wide(page):
    """Shown drop-down lists and number fields wider than their limits, and
    buttons stretched past their own width."""
    from PySide6.QtWidgets import QAbstractSpinBox, QComboBox, QPushButton

    from spacemissionstudio.gui.theme import FIELD_WIDTH

    found = [f"choice {box.currentText()!r} {box.width()} px" for box in page.findChildren(QComboBox)
             if box.isVisible() and box.width() > FIELD_WIDTH["choice"]]
    found += [f"number {box.text()!r} {box.width()} px" for box in page.findChildren(QAbstractSpinBox)
              if box.isVisible() and box.width() > FIELD_WIDTH["number"]]
    found += [f"button {button.text()!r} {button.width()} px" for button in page.findChildren(QPushButton)
              if button.isVisible() and button.width() > button.sizeHint().width() + 2 * 16 + 1]
    return found


@pytest.mark.parametrize("name", ["07_attitude_pointing_with_adcs_hardware.json", "23_starter_complete_small_satellite.json",
                                  "33_microsat_thermal.json"], ids=["07", "23", "33"])
def test_the_fields_of_a_page_start_at_one_x(window, qtbot, name):
    """On each page of the Scenario tree the fields of every form start at
    one x, whatever group or section holds them; a drop-down list is at
    most FIELD_WIDTH["choice"] (it was 770-960 px), a number field at most
    FIELD_WIDTH["number"] ("Look ahead" was 820 px, the LTAN 435 px), and a
    button keeps its own width (one was 880 px)."""
    from PySide6.QtWidgets import QScrollArea

    _open(window, qtbot, name)
    problems = []
    for path, page in _tree_pages(window, qtbot):
        body = page.widget() if isinstance(page, QScrollArea) and page.widget() else page
        columns = _field_columns(body)
        if len(columns) > 1:
            problems.append(f"{path}: fields at {sorted(columns.items())}")
        problems += [f"{path}: {what}" for what in _too_wide(body)]
    assert problems == []


def test_the_end_of_life_fields_start_at_one_x_and_are_number_fields(window, qtbot):
    """Run › End of Life: one field column, its choices at most
    FIELD_WIDTH["choice"], and its numbers number fields (their unit as a
    suffix, right-aligned, at most FIELD_WIDTH["number"])."""
    from spacemissionstudio.gui.widgets import NumberField

    _open(window, qtbot, "01_two_body_circular_orbit.json")
    page = window.lifetime_widget
    window.show_view(page)
    _settle(qtbot, page)
    assert len(_field_columns(page)) == 1
    assert _too_wide(page) == []
    assert all(isinstance(box, NumberField) for box in (page.horizon_spin, page.deorbit_perigee_spin,
                                                         page.propellant_spin))
    assert page.horizon_spin.suffix() == " years" and page.deorbit_perigee_spin.suffix() == " km"


# -- UI-42: a disabled input says why ----------------------------------------------------------

def _says_why(widget, page) -> bool:
    """Whether hovering ``widget`` shows a tooltip from it or from the
    disabled widget that holds it (a tooltip event goes up to the parent
    when the widget has none)."""
    while widget is not None and widget is not page:
        if widget.toolTip().strip():
            return True
        widget = widget.parentWidget()
        if widget is not None and widget.isEnabled():
            return False
    return False


def _silent_disabled(page):
    """Shown, disabled inputs under ``page`` whose hover says nothing."""
    from PySide6.QtWidgets import (QAbstractButton, QAbstractItemView, QAbstractSpinBox, QComboBox, QHeaderView,
                                   QLineEdit)

    found = []
    inputs = (QAbstractButton, QAbstractSpinBox, QComboBox, QLineEdit, QAbstractItemView)
    for widget in [w for kind in inputs for w in page.findChildren(kind)]:
        if not widget.isVisible() or widget.isEnabledTo(page) or _says_why(widget, page):
            continue
        if isinstance(widget, QHeaderView) or (isinstance(widget, QLineEdit) and isinstance(
                widget.parentWidget(), (QAbstractSpinBox, QComboBox))):
            continue  # a part of a table or of a field
        name = widget.text() if isinstance(widget, QAbstractButton) else widget.accessibleName()
        found.append(f"{type(widget).__name__} {name!r}")
    return found


@pytest.mark.parametrize("name", ["07_attitude_pointing_with_adcs_hardware.json", "30_mars_optical_navigation.json",
                                  "28_octagonal_bus_3d_model.json"], ids=["07", "30", "28"])
def test_every_disabled_input_on_the_main_pages_says_why(window, qtbot, name):
    """Every disabled input on the Scenario tree's pages and the tabs of the
    Run and Reports areas has a tooltip: why it is off and what turns it on
    (Pace, Degree/order, Gravity from the shape model, Dry mass and the
    re-entry Estimate had none)."""
    _open(window, qtbot, name)
    problems = [f"Scenario › {path}: {what}" for path, page in _tree_pages(window, qtbot)
                for what in _silent_disabled(page)]
    problems += [f"{area}: {what}" for area, page in _area_pages(window, qtbot)
                 if area.startswith(("Run", "Reports")) for what in _silent_disabled(page)]
    assert problems == [], "\n".join(problems)


def test_the_named_inputs_say_why_they_are_off(qtbot):
    """The five of the audit: each tooltip starts with "Off:" and names
    what turns the input on."""
    from spacemissionstudio.gui.lifetime_widget import LifetimeWidget
    from spacemissionstudio.gui.propagation_setup_dialog import PropagationSetupDialog
    from spacemissionstudio.gui.run_page import RunPage
    from spacemissionstudio.schema.scenario import GravityConfig, SimSettings, SpaceWeatherConfig

    run_page = RunPage()
    qtbot.addWidget(run_page)
    run_page.live_view_check.setChecked(False)
    assert not run_page.pacing_combo.isEnabled()
    assert run_page.pacing_combo.toolTip().startswith("Off:") and "Show in 3D View" in run_page.pacing_combo.toolTip()
    run_page.live_view_check.setChecked(True)
    assert run_page.pacing_combo.isEnabled() and not run_page.pacing_combo.toolTip().startswith("Off:")

    dialog = PropagationSetupDialog(GravityConfig(central_body="earth", central_body_degree=0), SimSettings(),
                                    SpaceWeatherConfig())
    qtbot.addWidget(dialog)
    degree, shape = dialog.central_body_degree_spin, dialog.polyhedral_gravity_check
    assert not degree.isEnabled() and "Enable spherical-harmonics gravity" in degree.toolTip()
    assert not shape.isEnabled() and shape.toolTip().startswith("Off:") and "Eros" in shape.toolTip()
    dialog.enable_harmonics_check.setChecked(True)
    assert degree.isEnabled() and not degree.toolTip().startswith("Off:")

    eol = LifetimeWidget()
    qtbot.addWidget(eol)
    estimate = eol.reentry_section.compute_button
    assert not estimate.isEnabled() and estimate.toolTip().startswith("Off:") and "3D Model" in estimate.toolTip()


def test_a_dry_mass_the_model_gives_says_why_it_is_off(qtbot):
    """A spacecraft whose 3D model applies its mass properties: Dry mass is
    off, and its tooltip says the model gives it and how to type it."""
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog
    from spacemissionstudio.schema.scenario import load_scenario

    spacecraft = load_scenario(_TEMPLATES / "28_octagonal_bus_3d_model.json").spacecraft[0]
    assert spacecraft.model is not None and spacecraft.model.apply_mass_properties
    dialog = SpacecraftEditorDialog(config=spacecraft)
    qtbot.addWidget(dialog)
    assert not dialog.dry_mass_kg.isEnabled()
    assert dialog.dry_mass_kg.toolTip().startswith("Off: the 3D model gives this value")


# -- UI-04: Monte Carlo at the top -------------------------------------------------------------

def test_the_monte_carlo_page_keeps_its_lines_at_the_top(window, qtbot):
    """Monte Carlo off: its switch and the line on what it does sit at the
    top of the page, one under the other (the line floated in the middle
    of the page)."""
    from PySide6.QtCore import QPoint

    from spacemissionstudio.gui.theme import PAGE_INSET, SPACE

    _open(window, qtbot, "01_two_body_circular_orbit.json")
    editor = window.scenario_editor
    group = editor.monte_carlo_group
    assert not group.enabled_check.isChecked()
    window._show_tree_item(editor.monte_carlo_item)
    page = editor.monte_carlo_page
    _settle(qtbot, group.off_label)
    check_bottom = group.enabled_check.mapTo(page, QPoint(0, group.enabled_check.height())).y()
    label_top = group.off_label.mapTo(page, QPoint(0, 0)).y()
    assert 0 <= label_top - check_bottom <= SPACE["lg"]
    assert label_top < 6 * PAGE_INSET  # [px] near the top of a page about 540 px tall


# -- UI-13: the thermal editor -----------------------------------------------------------------

def test_the_thermal_editor_fits_the_page(window, qtbot):
    """Template 33's 3D model section at 1280 x 720: the thermal editor's
    tab row shows every tab whole (it was cut at "Mon"), its tables are
    model/view grids without grid lines, as tall as their rows, and
    neither the page nor a table scrolls sideways."""
    from PySide6.QtWidgets import QScrollArea, QTableView, QTableWidget

    from spacemissionstudio.gui.thermal_editor import TAB_TITLES

    _open(window, qtbot, "33_microsat_thermal.json")
    editor = window.scenario_editor
    tree = editor.page_tree
    window._show_tree_item(dict(tree.paths())["Spacecraft > microsat-1 > 3D model"])
    group = editor._spacecraft_nodes[0].form.thermal_group
    _settle(qtbot, group)
    bar = group.tabs.tabBar()
    assert [group.tabs.tabText(i) for i in range(group.tabs.count())] == list(TAB_TITLES)
    assert bar.sizeHint().width() <= bar.width()  # no tab cut, no scroll buttons
    assert group.findChildren(QTableWidget) == []
    for index in range(group.tabs.count()):
        group.tabs.setCurrentIndex(index)
        _settle(qtbot)
        for view in group.tabs.currentWidget().findChildren(QTableView):
            if not view.isVisible():
                continue
            assert not view.showGrid()
            assert view.horizontalHeader().length() <= view.viewport().width()
            assert view.verticalScrollBar().maximum() == 0  # as tall as its rows
        sideways = [area for area in window.scenario_editor.findChildren(QScrollArea)
                    if area.isVisible() and area.horizontalScrollBar().maximum() > 0]
        assert sideways == [], group.tabs.tabText(index)


def test_the_thermal_tables_edit_in_place_and_keep_each_record(qtbot):
    """A cell edited in place is what the section reads; Add and Remove add
    and remove a row; a list without a row shows its empty state with Add."""
    from spacemissionstudio.gui.thermal_editor import ThermalGroup
    from spacemissionstudio.schema.scenario import load_scenario

    thermal = load_scenario(_TEMPLATES / "33_microsat_thermal.json").spacecraft[0].thermal
    group = ThermalGroup(thermal)
    qtbot.addWidget(group)
    group.show()
    nodes = group.tables["nodes"]
    column = [name for name, _label, _kind in nodes.columns].index("initial_c")
    nodes.set_cell(0, column, "12.5")
    assert group.to_config().nodes[0].initial_c == 12.5
    count = nodes.row_count()
    nodes.add_record()
    assert nodes.row_count() == count + 1
    nodes.set_current_row(count)
    nodes.remove_current()
    assert nodes.row_count() == count
    heat_pipes = group.stacks["heat_pipes"]
    assert group.tables["heat_pipes"].row_count() == len(thermal.heat_pipes)
    if not thermal.heat_pipes:
        assert heat_pipes.showing_empty()
        heat_pipes.empty.button.click()
        assert group.tables["heat_pipes"].row_count() == 1 and not heat_pipes.showing_empty()


# -- UI-53: the third bodies -------------------------------------------------------------------

def test_the_third_bodies_are_check_boxes_in_the_form(window, qtbot):
    """No framed box in the form: the list has no frame and the form's
    background, a row per body at the table-row height, and no scroll bar
    (it is as tall as its rows)."""
    from PySide6.QtCore import Qt

    from spacemissionstudio.gui.theme import ROW_HEIGHT

    _open(window, qtbot, "30_mars_optical_navigation.json")
    editor = window.scenario_editor
    window._show_tree_item(editor.environment_item)
    bodies = editor._environment_form.third_body_list
    _settle(qtbot, bodies)
    assert bodies.frameWidth() == 0 and bodies.property("role") == "checklist"
    assert bodies.count() > 3
    assert all(bodies.visualItemRect(bodies.item(i)).height() >= ROW_HEIGHT for i in range(bodies.count()))
    assert bodies.verticalScrollBar().maximum() == 0
    assert bodies.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    last = bodies.visualItemRect(bodies.item(bodies.count() - 1))
    assert last.bottom() < bodies.viewport().height()
