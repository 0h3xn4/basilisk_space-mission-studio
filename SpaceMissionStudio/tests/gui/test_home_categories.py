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

"""Home's templates in groups by category (decision TC-1, TC-2): the
headings in catalog order, each group's cards under its heading, the
category and text filters combined, the count, the empty state, and a
template opened from a group. The command palette lists the templates in
the same order (TC-3)."""

import pytest

from spacemissionstudio.scenarios.catalog import CATEGORIES

pytestmark = pytest.mark.requires_gui


@pytest.fixture
def home(qtbot):
    from spacemissionstudio.gui.load_scenario_widget import LoadScenarioWidget

    widget = LoadScenarioWidget()
    qtbot.addWidget(widget)
    widget.resize(1600, 900)  # [px]
    widget.show()
    qtbot.waitUntil(lambda: widget.grid.columns() > 0)
    return widget


def _top(widget, home) -> int:
    return widget.mapTo(home, widget.rect().topLeft()).y()


def test_home_shows_the_category_headings_in_catalog_order(home):
    """A heading per category, in the catalog's order, each with its line;
    the cards of a category sit below its heading and above the next one,
    in the catalog's order; a heading is not a Tab stop."""
    from PySide6.QtCore import Qt

    from spacemissionstudio.scenarios import catalog

    headings = home.grid.visible_headings()
    assert [heading.text() for heading in headings] == [category.title for category in catalog.CATEGORIES]
    assert [heading.description_label.text() for heading in headings] == [
        category.description for category in catalog.CATEGORIES]
    assert all(heading.isVisible() for heading in headings)
    tops = [_top(heading, home) for heading in headings]
    assert tops == sorted(tops) and len(set(tops)) == len(tops)
    assert [card.path.name for card in home.grid.cards] == [entry.file_name for entry in catalog.entries()]
    for index, heading in enumerate(headings):
        cards = [card for card in home.grid.cards if home.grid.heading_of(card) is heading]
        assert [card.path.name for card in cards] == list(heading.category.files)
        below = tops[index + 1] if index + 1 < len(tops) else 10 ** 6
        assert all(tops[index] < _top(card, home) < below for card in cards), heading.text()
    assert all(heading.focusPolicy() == Qt.FocusPolicy.NoFocus for heading in home.grid.headings)
    assert home.grid.cards[0].path.name == "22_starter_first_leo_satellite.json"  # the one Tab stop: the first shown
    assert home.grid.current() is home.grid.cards[0]


def test_the_category_filter_lists_every_category_after_all(home):
    """The category list: "All categories", then every category in order."""
    from spacemissionstudio.gui.load_scenario_widget import ALL_CATEGORIES
    from spacemissionstudio.scenarios import catalog

    combo = home.category_combo
    assert [combo.itemText(i) for i in range(combo.count())] == [ALL_CATEGORIES] + [
        category.title for category in catalog.CATEGORIES]
    assert home.selected_category() is None
    assert combo.accessibleName() == "Template category"


def test_the_category_and_text_filters_combine(home):
    """A card shows only when it is in the category picked and has every
    word typed: the cards shown are those both filters let through, and
    only their heading shows."""
    home.set_category("attitude")
    category_only = {card.path.name for card in home.grid.visible_cards()}
    attitude = next(category for category in CATEGORIES if category.key == "attitude")
    assert category_only == set(attitude.files)
    assert [heading.text() for heading in home.grid.visible_headings()] == ["Attitude and control"]
    home.set_category(None)
    home.filter_edit.setText("wheel")
    text_only = {card.path.name for card in home.grid.visible_cards()}
    assert text_only - category_only  # "wheel" is found in other categories too
    home.set_category("attitude")
    both = {card.path.name for card in home.grid.visible_cards()}
    assert both == category_only & text_only and both
    assert [card.path.name for card in home.grid.visible_cards()] == [
        card.path.name for card in home.grid.cards if card.path.name in both]  # still in catalog order
    assert home.templates_count.text() == f"{len(both)} of {len(home.grid.cards)}"
    home.filter_edit.clear()
    assert {card.path.name for card in home.grid.visible_cards()} == category_only
    home.set_category(None)
    assert len(home.grid.visible_cards()) == len(home.grid.cards)
    assert len(home.grid.visible_headings()) == len(CATEGORIES)


def test_the_count_follows_the_templates_folder(home):
    """The count beside "Templates" is the number of template files in the
    folder; with a filter, "shown of all"."""
    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR

    files = len(list(TEMPLATES_DIR.glob("*.json")))
    assert files == sum(len(category.files) for category in CATEGORIES)
    assert home.templates_count.text() == str(files)
    assert len(home.cards) == len(home.grid.cards) == files
    home.set_category("deep-space")
    assert home.templates_count.text() == f"2 of {files}"


def test_the_empty_state_shows_when_the_filters_match_nothing(home):
    """No template in the category picked has the word typed: no card and
    no heading show, the empty state does, and its action clears both
    filters."""
    from spacemissionstudio.gui.load_scenario_widget import ALL_CATEGORIES, FILTER_EMPTY

    home.set_category("deep-space")
    home.filter_edit.setText("wheel")
    assert home.grid.visible_cards() == [] and home.grid.visible_headings() == []
    assert home.grid.empty_label.isVisible()
    assert home.grid.empty_label.text().splitlines()[0] == FILTER_EMPTY[0]
    assert home.grid.empty_label.button.isVisible() and home.grid.empty_label.button.text() == FILTER_EMPTY[2]
    assert home.templates_count.text() == f"0 of {len(home.grid.cards)}"
    home.grid.empty_label.button.click()
    assert home.filter_edit.text() == "" and home.category_combo.currentText() == ALL_CATEGORIES
    assert len(home.grid.visible_cards()) == len(home.grid.cards) and not home.grid.empty_label.isVisible()


def test_opening_a_template_from_a_group_opens_its_file(home, qtbot):
    """The first card of a later group, selected and opened with Enter,
    double-click or Open template, hands on that template's own file."""
    from PySide6.QtCore import Qt

    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR

    opened = []
    home.path_chosen.connect(opened.append)
    heading = next(heading for heading in home.grid.headings if heading.text() == "Deep space and navigation")
    card = next(card for card in home.grid.cards if home.grid.heading_of(card) is heading)
    card.setFocus()
    qtbot.waitUntil(lambda: home.selected_card() is card)
    qtbot.keyClick(card, Qt.Key.Key_Return)
    home.open_template_button.click()
    qtbot.mouseDClick(card, Qt.MouseButton.LeftButton)
    assert opened == [TEMPLATES_DIR / "30_mars_optical_navigation.json"] * 3
    assert home.description_title.text() == "30 - Mars orbit: optical navigation from the planet's disk"


def test_opening_a_template_from_a_group_in_the_window(qtbot):
    """In the window, Open template on a card of a group opens that file."""
    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR
    from spacemissionstudio.gui.main_window import MainWindow

    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    window._confirm_discard_unsaved = lambda: True
    home = window.load_scenario_widget
    home.set_category("monte-carlo")
    card = home.grid.visible_cards()[1]
    home.select(card.name)
    home.open_template_button.click()
    assert window._current_path == TEMPLATES_DIR / "25_monte_carlo_orbit_and_drag_dispersions.json"
    assert window.scenario_editor.to_scenario().name == card.name
    window._mark_clean()


def test_up_and_down_cross_the_headings_by_a_row(home, qtbot):
    """Down from the last row of a group goes to the first row of the next
    group, in the same column when it has a card there; Up goes back."""
    from PySide6.QtCore import Qt

    grid = home.grid
    first_group = [card for card in grid.cards if grid.heading_of(card) is grid.headings[0]]
    second_group = [card for card in grid.cards if grid.heading_of(card) is grid.headings[1]]
    columns = grid.columns()
    last_row_start = (len(first_group) - 1) // columns * columns
    start = first_group[last_row_start]
    assert grid.move(start, Qt.Key.Key_Down) is second_group[0]
    assert grid.move(second_group[0], Qt.Key.Key_Up) is start
    assert grid.move(grid.cards[0], Qt.Key.Key_Up) is None
    assert grid.move(grid.cards[-1], Qt.Key.Key_Down) is None


def test_the_palette_lists_the_templates_in_catalog_order_with_their_category(qtbot):
    """Ctrl+K's "Open template" entries follow the catalog, each with its
    category, and still start with the template's number and name."""
    from spacemissionstudio.gui.main_window import MainWindow
    from spacemissionstudio.scenarios import catalog

    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    labels = [entry.label for entry in window.palette_entries() if entry.label.startswith("Open template > ")]
    expected = [f"Open template > {name[:-5].replace('_', ' ')} ({entry.category.title})"
                for entry in catalog.entries() for name in [entry.file_name]]
    assert labels == expected
