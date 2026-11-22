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

"""Monte Carlo editor: :class:`DispersionListWidget` (one
:class:`schema.scenario.DispersionConfig` per row, referencing a
spacecraft by name), :class:`RequirementListWidget` (one
:class:`schema.scenario.MonteCarloRequirementConfig` per row: a limit on
one outcome of every run, Monte Carlo plan A2) and
:class:`MonteCarloGroupWidget` (the enable/num_runs/thread_count/verbose
settings plus those lists) -- composed into ``scenario_editor.py`` the
same way the space-weather/ground-station groups are.

A requirement's limit and confidence have no default (decision MC-5): a
new requirement starts with both "Not set", and the scenario is not valid
until they are given (the Problems panel says which).

The dispersion editor dialog needs to know which spacecraft NAMES exist in
the scenario being edited right now (a dispersion references one by name),
so :class:`DispersionListWidget`/:class:`MonteCarloGroupWidget` expose
``set_spacecraft_names()``; ``ScenarioEditorWidget`` calls it whenever the
spacecraft list changes, same live-refresh pattern as the third-body
-perturber checklist reacting to the central-body combo.
"""

from __future__ import annotations

import os

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..schema.scenario import (
    SPREAD_ONLY_DISPERSION_QUANTITIES,
    DISPERSION_KINDS_BY_QUANTITY,
    DISPERSION_QUANTITIES,
    MAX_MONTE_CARLO_RUNS,
    MAX_MONTE_CARLO_THREADS,
    MONTE_CARLO_OUTCOME_TITLES,
    MONTE_CARLO_OUTCOME_UNITS,
    MONTE_CARLO_OUTCOMES,
    ORBIT_ELEMENT_SPREAD_KEYS,
    DispersionConfig,
    MonteCarloConfig,
    MonteCarloRequirementConfig,
)
from . import units
from .feedback import report, show_dialog_error, show_toast
from .field_text import field_title, labelled
from .theme import set_role
from .inline_form import InlineForm
from .widgets import ComboBox, EmptyStack, EmptyState, PreciseDoubleSpinBox, SpinBox, finish_form, layout_widgets


def _spin(minimum: float, maximum: float, decimals: int = 4, step: float = 1.0, value: float = 0.0) -> QDoubleSpinBox:
    box = PreciseDoubleSpinBox()
    box.setRange(minimum, maximum)
    box.setDecimals(decimals)
    box.setSingleStep(step)
    box.setValue(value)
    return box


# What the numbers below mean for each quantity (DispersionConfig field comments).
_UNITS = {
    "dry_mass_kg": "kg",
    "attitude_sigma_bn": "rad, as Euler angles",
    "orbit_elements": "a spread on each element of the initial orbit",
    "inertia_kg_m2": "kg·m² on each diagonal element, added to the inertia",
    "angular_rate_bn_b": "°/s on each axis, added to the initial rate",
    "drag_coeff": "drag coefficient Cd [-]",
    "srp_coeff": "radiation-pressure coefficient Cr [-]",
}
# The unit the mean, standard deviation and bounds fields carry for each
# quantity (orbit_elements has a field per element, with its own unit).
_FIELD_UNITS = {
    "dry_mass_kg": "kg", "attitude_sigma_bn": "rad", "inertia_kg_m2": "kg*m^2", "angular_rate_bn_b": "deg/s",
    "drag_coeff": "-", "srp_coeff": "-",
}
_ELEMENT_LABELS = {
    "semi_major_axis_km": "Semi-major axis [km]",
    "eccentricity": "Eccentricity [-]",
    "inclination_deg": "Inclination [deg]",
    "raan_deg": "RAAN [deg]",
    "arg_periapsis_deg": "Argument of periapsis [deg]",
    "true_anomaly_deg": "True anomaly [deg]",
}


# Quantities whose dispersion is the value itself (written absolutely, as
# engine.monte_carlo does), so a new one starts at the spacecraft's own.
SCALAR_DISPERSION_QUANTITIES = ("dry_mass_kg", "drag_coeff", "srp_coeff")


class _DispersionEditorDialog(QDialog):
    def __init__(self, spacecraft_names: list, item: DispersionConfig | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Edit dispersion" if item is not None else "New dispersion")

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.spacecraft_combo = ComboBox()
        for name in spacecraft_names:
            self.spacecraft_combo.addItem(name, userData=name)
        if item is not None:
            index = self.spacecraft_combo.findData(item.spacecraft)
            if index >= 0:
                self.spacecraft_combo.setCurrentIndex(index)
            else:
                # item.spacecraft doesn't match any current spacecraft name
                # (e.g. renamed or removed since this dispersion was saved).
                # Silently falling back to index 0 would re-target this
                # dispersion at whichever spacecraft happens to be first --
                # wrong, and invisible to the user. Surface the stale name
                # as its own selectable entry instead (userData carries the
                # real name; the label just flags it), so to_dataclass()
                # still round-trips it unless the user explicitly retargets
                # this dispersion.
                self.spacecraft_combo.addItem(f"{item.spacecraft} (not found in this scenario)",
                                               userData=item.spacecraft)
                self.spacecraft_combo.setCurrentIndex(self.spacecraft_combo.count() - 1)
        form.addRow("Spacecraft", self.spacecraft_combo)

        self.quantity_combo = ComboBox()
        self.quantity_combo.setToolTip(
            "Which quantity gets randomized, independently, on each Monte Carlo run – e.g. a "
            "real uncertainty in orbit insertion, mass properties, initial attitude or rate, or "
            "the drag and radiation-pressure coefficients. Every other dispersion on this "
            "spacecraft (if any) varies independently alongside it. See User Manual, section 10."
        )
        self.quantity_combo.addItems(DISPERSION_QUANTITIES)
        self.quantity_combo.currentTextChanged.connect(self._refresh_kind_choices)
        self.quantity_combo.currentTextChanged.connect(lambda _text: self._refresh_rows())
        form.addRow("Quantity", self.quantity_combo)

        self.kind_combo = ComboBox()
        self.kind_combo.setToolTip(
            "The probability distribution each run's random draw is taken from – 'uniform' "
            "needs Bounds below (every value in range equally likely); 'normal' needs Mean/Std "
            "deviation below (a bell curve centered on Mean)."
        )
        self.kind_combo.currentTextChanged.connect(self._on_kind_changed)
        form.addRow("Kind", self.kind_combo)

        self.bounds_lo_spin = _spin(-1.0e9, 1.0e9, decimals=6, value=0.0)
        self.bounds_hi_spin = _spin(-1.0e9, 1.0e9, decimals=6, value=1.0)
        _bounds_tip = "The [low, high] range each run's uniformly-random draw is taken from, inclusive."
        self.bounds_lo_spin.setToolTip(_bounds_tip)
        self.bounds_hi_spin.setToolTip(_bounds_tip)
        self._bounds_row = QHBoxLayout()
        self._bounds_row.addWidget(self.bounds_lo_spin)
        self._bounds_row.addWidget(self.bounds_hi_spin)
        form.addRow("Bounds [lo, hi]", self._bounds_row)

        self.mean_spin = _spin(-1.0e9, 1.0e9, decimals=6, value=0.0)
        self.mean_spin.setToolTip("The center of the normal (bell-curve) distribution each run draws from.")
        form.addRow("Mean", self.mean_spin)
        self.std_spin = _spin(0.0, 1.0e9, decimals=6, value=1.0)
        self.std_spin.setToolTip(
            "The spread of the normal distribution – about 68% of runs land within one std "
            "deviation of the mean, ~95% within two."
        )
        form.addRow("Std deviation", self.std_spin)
        self.units_label = QLabel()
        self.units_label.setWordWrap(True)
        form.addRow("Units", self.units_label)
        # "orbit_elements": one spread per element (1-sigma for normal,
        # half-width for uniform); 0 leaves the element at its nominal value.
        self.element_spins = {}
        for key in ORBIT_ELEMENT_SPREAD_KEYS:
            spin = _spin(0.0, 1.0e6, decimals=6, value=0.0)
            spin.setToolTip("Spread around this spacecraft's initial value: 1-sigma for 'normal', half-width "
                            "for 'uniform'. 0 keeps the element as configured. For a near-circular orbit put "
                            "an along-track spread on the true anomaly only.")
            self.element_spins[key] = spin
            form.addRow(_ELEMENT_LABELS[key], spin)
        self.angle_std_spin = _spin(0.0, 180.0, decimals=4, value=0.0)
        self.angle_std_spin.setToolTip("1-sigma of a small random rotation of the inertia tensor, which mixes "
                                       "in off-diagonal (product-of-inertia) terms. 0 disperses the diagonal only.")
        form.addRow("Off-diagonal angle 1-sigma [deg]", self.angle_std_spin)
        self._form = form

        layout.addLayout(form)

        if item is not None:
            index = self.quantity_combo.findText(item.quantity)
            if index >= 0:
                self.quantity_combo.setCurrentIndex(index)
        self._refresh_kind_choices(self.quantity_combo.currentText())
        if item is not None:
            index = self.kind_combo.findText(item.kind)
            if index >= 0:
                self.kind_combo.setCurrentIndex(index)
            if item.bounds:
                self.bounds_lo_spin.setValue(item.bounds[0])
                self.bounds_hi_spin.setValue(item.bounds[1])
            if item.mean is not None:
                self.mean_spin.setValue(item.mean)
            if item.std_deviation is not None:
                self.std_spin.setValue(item.std_deviation)
            for key, value in (item.element_spread or {}).items():
                if key in self.element_spins:
                    self.element_spins[key].setValue(value)
            if item.angle_std_deg is not None:
                self.angle_std_spin.setValue(item.angle_std_deg)
        # _on_kind_changed already ran (connected above, and both
        # _refresh_kind_choices()/setCurrentIndex() fire
        # currentTextChanged as they go) -- one more explicit call in
        # case the final kind ended up the SAME as whatever the combo
        # happened to default to, which fires no signal at all, and
        # would otherwise leave the row visibility out of sync with the
        # real selection.
        self._on_kind_changed(self.kind_combo.currentText())

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # See constellation_dialog.py's identical fix for why this is
        # needed: Qt can size a freshly-constructed QDialog smaller than
        # its own sizeHint() on first show() on a real desktop, a gap
        # this project's own offscreen test rendering doesn't reproduce.
        finish_form(self)  # units in the fields, optional groups collapse (M4a)
        self.resize(self.sizeHint())

    def start_at(self, nominal: float) -> None:
        """A new dispersion starts at ``nominal``, the spacecraft's own value,
        with no spread: bounds [nominal, nominal], mean nominal, deviation 0.
        Transparency audit 3.7: it started at bounds [0, 1] and mean 0, which
        for the dry mass, written absolutely, made every run a 0 to 1 kg
        spacecraft."""
        self.bounds_lo_spin.setValue(nominal)
        self.bounds_hi_spin.setValue(nominal)
        self.mean_spin.setValue(nominal)
        self.std_spin.setValue(0.0)

    def _refresh_kind_choices(self, quantity: str) -> None:
        current = self.kind_combo.currentText()
        self.kind_combo.clear()
        kinds = DISPERSION_KINDS_BY_QUANTITY.get(quantity, ())
        self.kind_combo.addItems(kinds)
        index = self.kind_combo.findText(current)
        if index >= 0:
            self.kind_combo.setCurrentIndex(index)

    def _on_kind_changed(self, kind: str) -> None:
        """Real user-facing bug this fixes: Bounds/Mean/Std-deviation
        were ALL shown and editable at once regardless of Kind, but
        to_dataclass() only ever uses the pair that matches the
        currently-selected kind (see its own field-by-field ``if kind
        == ...`` logic) -- a value typed into whichever row doesn't
        match was silently discarded with no indication anything was
        ignored. Hiding the irrelevant row(s) makes the dialog show
        only what will actually be used.
        """
        self._refresh_rows()

    def _refresh_rows(self) -> None:
        """Only the fields the selected quantity and kind use are shown."""
        quantity, kind = self.quantity_combo.currentText(), self.kind_combo.currentText()
        orbit = quantity == "orbit_elements"
        self._set_row_visible(self._bounds_row, kind in ("uniform", "uniform_euler_mrp") and not orbit)
        self._set_row_visible(self.mean_spin, kind == "normal" and quantity not in SPREAD_ONLY_DISPERSION_QUANTITIES)
        self._set_row_visible(self.std_spin, kind == "normal" and not orbit)
        for spin in self.element_spins.values():
            self._set_row_visible(spin, orbit)
        self._set_row_visible(self.angle_std_spin, quantity == "inertia_kg_m2")
        self.units_label.setText(_UNITS.get(quantity, ""))
        for spin in (self.mean_spin, self.std_spin, self.bounds_lo_spin, self.bounds_hi_spin):
            spin.setSuffix(units.suffix(_FIELD_UNITS.get(quantity, "-")))

    def _set_row_visible(self, field, visible: bool) -> None:
        label = self._form.labelForField(field)
        if label is not None:
            label.setVisible(visible)
        if isinstance(field, QHBoxLayout):
            for widget in layout_widgets(field):  # its widgets as QObjects (widgets.layout_widgets)
                widget.setVisible(visible)
        else:
            field.setVisible(visible)

    def _on_accept(self) -> None:
        try:
            self.to_dataclass()
        except ValueError as exc:
            show_dialog_error(self, f"This dispersion is not valid: {exc}")
            return
        self.accept()

    def to_dataclass(self) -> DispersionConfig:
        if not self.spacecraft_combo.count():
            raise ValueError("this scenario has no spacecraft to disperse yet – add one first")
        kind = self.kind_combo.currentText()
        quantity = self.quantity_combo.currentText()
        orbit = quantity == "orbit_elements"
        config = DispersionConfig(
            spacecraft=self.spacecraft_combo.currentData(),
            quantity=quantity,
            kind=kind,
            bounds=[self.bounds_lo_spin.value(), self.bounds_hi_spin.value()]
            if kind in ("uniform", "uniform_euler_mrp") and not orbit else None,
            mean=self.mean_spin.value() if kind == "normal" and quantity not in SPREAD_ONLY_DISPERSION_QUANTITIES else None,
            std_deviation=self.std_spin.value() if kind == "normal" and not orbit else None,
            element_spread={key: spin.value() for key, spin in self.element_spins.items() if spin.value() > 0}
            if orbit else None,
            angle_std_deg=self.angle_std_spin.value() if quantity == "inertia_kg_m2" else None,
        )
        config.validate()
        return config


class DispersionListWidget(QWidget):
    """A list of :class:`DispersionConfig`, with Add and Remove; the
    selected dispersion's form is under the list and applies its edits as
    they are made (UI overhaul M4b) -- as
    :class:`gui.sensor_actuator_editor.SensorActuatorListWidget`.
    """

    changed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._items: list = []
        self._spacecraft_names: list = []
        self._nominals: dict = {}  # {spacecraft: {quantity: its own value}}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        button_row = QHBoxLayout()
        self.add_button = QPushButton("Add")
        self.add_button.setToolTip("Add a dispersion of the first spacecraft's first quantity: its form opens below.")
        self.remove_button = QPushButton("Remove")
        button_row.addWidget(self.add_button)
        button_row.addWidget(self.remove_button)
        button_row.addStretch(1)  # buttons at their own width, not a third of a wide page each
        layout.addLayout(button_row)
        self.inline = InlineForm(self.list_widget, self._form_for, lambda form, _row: form.to_dataclass())
        self.inline.applied.connect(self._on_applied)
        layout.addWidget(self.inline)

        self.add_button.clicked.connect(self._on_add)
        self.remove_button.clicked.connect(self._on_remove)
        self.list_widget.itemDoubleClicked.connect(lambda _item: self._focus_form())

    def set_spacecraft_names(self, names: list, nominals: dict | None = None) -> None:
        """The spacecraft a dispersion can name, and their own values of the
        scalar quantities (``{name: {quantity: value}}``), where a new
        dispersion starts."""
        self._nominals = dict(nominals or {})
        if list(names) == self._spacecraft_names:
            return
        self.inline.flush()
        self._spacecraft_names = list(names)
        if self.inline.form is not None:
            self.inline.show_row(self.inline.row)  # its spacecraft choice lists the new names

    def _refresh_list(self) -> None:
        # Quiet while the rows are rebuilt (as the device list's).
        blocked = self.list_widget.blockSignals(True)
        try:
            self.list_widget.clear()
            for item in self._items:
                self.list_widget.addItem(QListWidgetItem(self._text(item)))
        finally:
            self.list_widget.blockSignals(blocked)

    @staticmethod
    def _text(item: DispersionConfig) -> str:
        return f"{item.spacecraft}: {item.quantity} ({item.kind})"

    def _on_add(self) -> None:
        """Add a dispersion with the form's defaults and open its form (no
        dialog first, M4b): Remove or Undo take back one not wanted."""
        self.inline.flush()
        dialog = _DispersionEditorDialog(self._spacecraft_names, parent=self)
        nominal = self._nominals.get(dialog.spacecraft_combo.currentData(), {}).get(dialog.quantity_combo.currentText())
        if nominal is not None:
            dialog.start_at(nominal)
        try:
            item = dialog.to_dataclass()
        except ValueError as exc:  # no spacecraft yet
            report(self, f"Not added: {exc}", kind="warning")
            return
        finally:
            dialog.deleteLater()
        self._items.append(item)
        self._refresh_list()
        self.list_widget.setCurrentRow(len(self._items) - 1)
        show_toast(self.window(), f"Added dispersion: {item.spacecraft}: {item.quantity}"
                   + (f", at its own {nominal:g} with no spread yet: widen its bounds" if nominal is not None else ""))
        self.changed.emit()
        self._focus_form()

    def _form_for(self, row: int) -> _DispersionEditorDialog:
        return _DispersionEditorDialog(self._spacecraft_names, item=self._items[row], parent=self)

    def _on_applied(self, row: int, item) -> None:
        if not 0 <= row < len(self._items) or item == self._items[row]:
            return
        self._items[row] = item
        self.list_widget.item(row).setText(self._text(item))
        self.changed.emit()

    def _focus_form(self) -> None:
        if self.inline.form is not None:
            self.inline.form.quantity_combo.setFocus()

    def _on_remove(self) -> None:
        row = self.list_widget.currentRow()
        if row < 0:
            return
        self.inline.discard()  # its row goes: an edit it holds goes with it
        item = self._items[row]
        del self._items[row]
        self._refresh_list()
        show_toast(self.window(), f"Removed dispersion: {item.spacecraft}: {item.quantity}", kind="info")
        self.changed.emit()

    def to_list(self) -> list:
        return list(self._items)

    def from_list(self, items: list) -> None:
        self.inline.discard()  # another scenario's dispersions
        self._items = list(items)
        self._refresh_list()


_NOT_SET = "Not set"
_LIMIT_RANGE = 1.0e9  # the limit field's range [outcome's unit]; its lowest value shows "Not set"
_LIMIT_KINDS = (("at_least", "At least"), ("at_most", "At most"))


class _RequirementEditorDialog(QDialog):
    """One requirement's form (shown under the list, :class:`InlineForm`)."""

    def __init__(self, spacecraft_names: list, item: MonteCarloRequirementConfig, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Edit requirement")
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit(item.name)
        self.name_edit.setToolTip("The requirement's label, unique in the list, e.g. its identifier in your "
                                  "requirements document.")
        form.addRow("Name", self.name_edit)

        self.spacecraft_combo = ComboBox()
        for name in spacecraft_names:
            self.spacecraft_combo.addItem(name, userData=name)
        index = self.spacecraft_combo.findData(item.spacecraft)
        if index < 0:  # renamed or removed since: kept, and shown so (as a dispersion's)
            self.spacecraft_combo.addItem(f"{item.spacecraft} (not found in this scenario)", userData=item.spacecraft)
            index = self.spacecraft_combo.count() - 1
        self.spacecraft_combo.setCurrentIndex(index)
        form.addRow("Spacecraft", self.spacecraft_combo)

        self.outcome_combo = ComboBox()
        for key in MONTE_CARLO_OUTCOMES:
            unit = MONTE_CARLO_OUTCOME_UNITS[key]
            self.outcome_combo.addItem(f"{MONTE_CARLO_OUTCOME_TITLES[key]} [{unit}]", userData=key)
        self.outcome_combo.setToolTip("The run's figure the requirement limits: the same as Results › Overview "
                                      "shows for one run. A run that does not record it is not evaluated.")
        self.outcome_combo.setCurrentIndex(max(0, self.outcome_combo.findData(item.outcome)))
        self.outcome_combo.currentIndexChanged.connect(lambda _index: self._show_unit())
        form.addRow("Outcome", self.outcome_combo)

        self.limit_kind_combo = ComboBox()
        for key, text in _LIMIT_KINDS:
            self.limit_kind_combo.addItem(text, userData=key)
        self.limit_kind_combo.setCurrentIndex(1 if item.at_most is not None and item.at_least is None else 0)
        self.limit_spin = PreciseDoubleSpinBox()
        self.limit_spin.setRange(-_LIMIT_RANGE, _LIMIT_RANGE)
        self.limit_spin.setDecimals(6)
        self.limit_spin.setSpecialValueText(_NOT_SET)
        limit = item.at_least if item.at_least is not None else item.at_most
        self.limit_spin.setValue(-_LIMIT_RANGE if limit is None else limit)
        self.limit_spin.setToolTip("A run meets the requirement with its outcome at or above (At least) or at or "
                                   "below (At most) this value, in the outcome's unit.")
        limit_row = QHBoxLayout()
        limit_row.addWidget(self.limit_kind_combo)
        limit_row.addWidget(self.limit_spin, 1)
        self._limit_row = limit_row
        form.addRow("Limit", limit_row)

        self.confidence_spin = PreciseDoubleSpinBox()
        self.confidence_spin.setRange(0.0, 0.999999)
        self.confidence_spin.setDecimals(6)
        self.confidence_spin.setSingleStep(0.01)
        self.confidence_spin.setSpecialValueText(_NOT_SET)
        self.confidence_spin.setValue(0.0 if item.confidence is None else item.confidence)
        self.confidence_spin.setToolTip("The confidence of the upper bound on the probability of not meeting the "
                                        "requirement, between 0 and 1. You choose it: there is no default.")
        form.addRow("Confidence [-]", self.confidence_spin)

        self.allowed_check = QCheckBox("Judge against an allowed probability")
        self.allowed_check.setToolTip("With it, the batch says \"met\" when the upper bound is at or below the "
                                      "allowed probability of not meeting the requirement, else \"not shown\".")
        self.allowed_check.setChecked(item.max_probability is not None)
        form.addRow(self.allowed_check)
        self.allowed_spin = PreciseDoubleSpinBox()
        self.allowed_spin.setRange(0.0, 0.999999)
        self.allowed_spin.setDecimals(6)
        self.allowed_spin.setSingleStep(0.01)
        self.allowed_spin.setValue(0.0 if item.max_probability is None else item.max_probability)
        self.allowed_spin.setToolTip("The allowed probability of not meeting the requirement, from 0 up to 1.")
        form.addRow("Allowed probability [-]", self.allowed_spin)
        self.allowed_check.toggled.connect(self._show_allowed)
        self._form = form
        layout.addLayout(form)
        self._show_unit()
        self._show_allowed(self.allowed_check.isChecked())
        finish_form(self)
        self.resize(self.sizeHint())

    def _show_unit(self) -> None:
        self.limit_spin.setSuffix(units.suffix(MONTE_CARLO_OUTCOME_UNITS.get(self.outcome_combo.currentData(), "-")))

    def _show_allowed(self, on: bool) -> None:
        self.allowed_spin.setVisible(on)
        label = self._form.labelForField(self.allowed_spin)
        if label is not None:
            label.setVisible(on)

    def to_dataclass(self) -> MonteCarloRequirementConfig:
        """The requirement in the form. Its limit and confidence may still
        be "Not set" (None): the scenario's check refuses that, naming the
        field, so a user can fill the form in any order."""
        name = self.name_edit.text().strip()
        if not name:
            raise ValueError("a requirement needs a name")
        limit = None if self.limit_spin.value() <= self.limit_spin.minimum() else self.limit_spin.value()
        kind = self.limit_kind_combo.currentData()
        confidence = self.confidence_spin.value()
        return MonteCarloRequirementConfig(
            name=name, spacecraft=self.spacecraft_combo.currentData(), outcome=self.outcome_combo.currentData(),
            at_least=limit if kind == "at_least" else None, at_most=limit if kind == "at_most" else None,
            confidence=None if confidence <= self.confidence_spin.minimum() else confidence,
            max_probability=self.allowed_spin.value() if self.allowed_check.isChecked() else None)


def requirement_text(item: MonteCarloRequirementConfig) -> str:
    """A requirement's line in the list: what it limits, and what is still missing."""
    title = MONTE_CARLO_OUTCOME_TITLES.get(item.outcome, item.outcome).lower()
    unit = MONTE_CARLO_OUTCOME_UNITS.get(item.outcome, "-")
    limit = item.at_least if item.at_least is not None else item.at_most
    word = "≥" if item.at_least is not None else "≤"
    missing = [field for field, value in (("limit", limit), ("confidence", item.confidence)) if value is None]
    text = f"{item.name}: {item.spacecraft} {title}"
    if limit is not None:
        text += f" {word} {limit:g}" + ("" if unit == "-" else f" {unit}")
    if missing:
        return text + f" ({' and '.join(missing)} not set)"
    return text + f", confidence {item.confidence:g}"


class RequirementListWidget(QWidget):
    """A list of :class:`MonteCarloRequirementConfig`, with Add and Remove
    and the selected requirement's form under it (as the dispersions'), or
    its empty state with Add while there is none (UI audit UI-05)."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._items: list = []
        self._spacecraft_names: list = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.list_widget = QListWidget()
        self.empty_state = EmptyState("No requirements", "A requirement limits one outcome of every run (the "
                                      "lowest altitude, the lowest battery charge, ...); the batch counts the runs "
                                      "that do not meet it and bounds the probability.", "Add requirement",
                                      compact=True)
        self.empty_state.button.clicked.connect(self._on_add)
        self.list_stack = EmptyStack(self.list_widget, self.empty_state, fit_rows=True)
        layout.addWidget(self.list_stack)
        button_row = QHBoxLayout()
        self.add_button = QPushButton("Add")
        self.add_button.setToolTip("Add a requirement on the first spacecraft: its form opens below; set its limit "
                                   "and confidence.")
        self.remove_button = QPushButton("Remove")
        button_row.addWidget(self.add_button)
        button_row.addWidget(self.remove_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)
        self.inline = InlineForm(self.list_widget, self._form_for, lambda form, _row: form.to_dataclass())
        self.inline.applied.connect(self._on_applied)
        layout.addWidget(self.inline)
        self.add_button.clicked.connect(self._on_add)
        self.remove_button.clicked.connect(self._on_remove)
        # The empty state's Add stands in for these while there is no requirement (one Add on the page, UI-05).
        self.list_stack.hide_while_empty(self.add_button, self.remove_button)

    def set_spacecraft_names(self, names: list) -> None:
        if list(names) == self._spacecraft_names:
            return
        self.inline.flush()
        self._spacecraft_names = list(names)
        if self.inline.form is not None:
            self.inline.show_row(self.inline.row)

    def _refresh_list(self) -> None:
        blocked = self.list_widget.blockSignals(True)
        try:
            self.list_widget.clear()
            for item in self._items:
                self.list_widget.addItem(QListWidgetItem(requirement_text(item)))
        finally:
            self.list_widget.blockSignals(blocked)

    def _on_add(self) -> None:
        """A requirement on the first spacecraft's lowest altitude, its limit
        and confidence not set (no default, decision MC-5); its form opens."""
        self.inline.flush()
        if not self._spacecraft_names:
            report(self, "Not added: this scenario has no spacecraft yet – add one first", kind="warning")
            return
        names = {item.name for item in self._items}
        number = len(self._items) + 1
        while f"R-{number}" in names:
            number += 1
        item = MonteCarloRequirementConfig(name=f"R-{number}", spacecraft=self._spacecraft_names[0],
                                           outcome="lowest_altitude")
        self._items.append(item)
        self._refresh_list()
        self.list_widget.setCurrentRow(len(self._items) - 1)
        show_toast(self.window(), f"Added requirement {item.name}: set its limit and confidence")
        self.changed.emit()
        if self.inline.form is not None:
            self.inline.form.limit_spin.setFocus()

    def _form_for(self, row: int) -> _RequirementEditorDialog:
        return _RequirementEditorDialog(self._spacecraft_names, self._items[row], parent=self)

    def _on_applied(self, row: int, item) -> None:
        if not 0 <= row < len(self._items) or item == self._items[row]:
            return
        self._items[row] = item
        self.list_widget.item(row).setText(requirement_text(item))
        self.changed.emit()

    def _on_remove(self) -> None:
        row = self.list_widget.currentRow()
        if row < 0:
            return
        self.inline.discard()
        item = self._items.pop(row)
        self._refresh_list()
        show_toast(self.window(), f"Removed requirement {item.name}", kind="info")
        self.changed.emit()

    def to_list(self) -> list:
        return list(self._items)

    def from_list(self, items: list) -> None:
        self.inline.discard()
        self._items = list(items)
        self._refresh_list()


class MonteCarloGroupWidget(QGroupBox):
    """Composed directly into ``scenario_editor.py``, same pattern as its
    other ``_build_*_group()`` sections.
    """

    changed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__("Monte Carlo", parent)
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.enabled_check = QCheckBox("Enabled")
        self.enabled_check.setToolTip(
            "Checking this ON lets Run, in Monte Carlo mode (the run mode beside Run), run this scenario "
            "repeatedly (Number of runs below), each time with a fresh random draw for every dispersion "
            "configured below, instead of a single run – for statistically characterizing how "
            "sensitive the outcome is to real initial-condition uncertainty."
        )
        self.enabled_check.toggled.connect(self.changed)
        layout.addWidget(self.enabled_check)
        # Off: only the switch and what it does; on: the batch's settings
        # (M4a, optional groups collapse their fields when off).
        self.off_label = QLabel("Off: Run makes one run. On: Run, in Monte Carlo mode, runs the scenario many times, "
                                "each with a fresh draw of the dispersions.")
        self.off_label.setWordWrap(True)
        set_role(self.off_label, tone="secondary")
        layout.addWidget(self.off_label)
        self.body = QWidget()
        body = QVBoxLayout(self.body)
        body.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.body)

        self.num_runs_spin = SpinBox()
        self.num_runs_spin.setRange(1, MAX_MONTE_CARLO_RUNS)
        self.num_runs_spin.setValue(10)
        self.num_runs_spin.setToolTip(
            "How many independent randomized runs to execute. More runs give a statistically "
            "better-characterized spread of outcomes, at a roughly proportional cost in total "
            "run time."
        )
        self.num_runs_spin.valueChanged.connect(self.changed)
        form.addRow("Number of runs", self.num_runs_spin)

        self.thread_count_spin = SpinBox()
        self.thread_count_spin.setRange(1, MAX_MONTE_CARLO_THREADS)
        self.thread_count_spin.setValue(1)
        self.thread_count_spin.setToolTip(
            "How many runs go at once, each in its own process. The batch uses at most one "
            f"process per CPU ({os.cpu_count() or 1} here)."
        )
        self.thread_count_spin.valueChanged.connect(self.changed)
        form.addRow("Thread count", self.thread_count_spin)

        self.verbose_check = QCheckBox("Verbose")
        self.verbose_check.toggled.connect(self.changed)
        form.addRow(self.verbose_check)
        body.addLayout(form)

        body.addWidget(QLabel("Dispersions"))
        self.dispersion_list = DispersionListWidget()
        self.dispersion_list.changed.connect(self.changed)
        body.addWidget(self.dispersion_list)
        body.addWidget(QLabel("Requirements"))
        self.requirement_list = RequirementListWidget()
        self.requirement_list.changed.connect(self.changed)
        body.addWidget(self.requirement_list)
        self.enabled_check.toggled.connect(self._show_enabled)
        self._show_enabled(self.enabled_check.isChecked())
        finish_form(self)  # units in the fields, optional groups collapse (M4a)

    def _show_enabled(self, enabled: bool) -> None:
        self.body.setVisible(enabled)
        self.off_label.setVisible(not enabled)


    # Where a MonteCarloConfig field's widget is (a message's field).
    _FIELD_WIDGETS = {"monte_carlo.enabled": "enabled_check", "monte_carlo.num_runs": "num_runs_spin",
                      "monte_carlo.thread_count": "thread_count_spin", "monte_carlo.verbose": "verbose_check"}

    def field_title(self, code: str) -> str:
        """The form's title for the field ``code`` names ("Monte Carlo:
        Number of runs" for "monte_carlo.num_runs"), or ""."""
        attribute = self._FIELD_WIDGETS.get(code)
        return field_title(getattr(self, attribute)) if attribute else ""

    def problem_text(self, message: str) -> str:
        """``message`` with its field codes as this form's titles."""
        return labelled(message, self.field_title)
    def set_spacecraft_names(self, names: list, nominals: dict | None = None) -> None:
        self.dispersion_list.set_spacecraft_names(names, nominals)
        self.requirement_list.set_spacecraft_names(names)

    def to_dataclass(self) -> MonteCarloConfig:
        """The settings as edited. The batch's settings and dispersions are
        checked here; the requirements with the scenario (one may be
        incomplete while it is typed, decision MC-5)."""
        config = MonteCarloConfig(
            enabled=self.enabled_check.isChecked(),
            num_runs=self.num_runs_spin.value(),
            thread_count=self.thread_count_spin.value(),
            verbose=self.verbose_check.isChecked(),
            dispersions=self.dispersion_list.to_list(),
            requirements=self.requirement_list.to_list(),
        )
        config.validate_settings()
        return config

    def from_dataclass(self, config: MonteCarloConfig) -> None:
        self.enabled_check.setChecked(config.enabled)
        self.num_runs_spin.setValue(config.num_runs)
        self.thread_count_spin.setValue(config.thread_count)
        self.verbose_check.setChecked(config.verbose)
        self.dispersion_list.from_list(config.dispersions)
        self.requirement_list.from_list(config.requirements)
