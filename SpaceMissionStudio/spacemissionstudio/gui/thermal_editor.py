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
"""The spacecraft editor's Thermal model group (3D model tab): the
spacecraft's ``thermal`` section (``schema.thermal.ThermalConfig``) as one
table per kind of record, built on the 3D model (decision T-32).

Each table edits a list of records of one dataclass; a cell holds text and
is read by its column's kind (a number, an optional number, a list of names
"a, b", a range "low, high", JSON). The environment and the solver are
one-row tables. **Generate from the 3D model** fills the tables with a
node per part, its faces and the conductors between parts in contact
(``thermal.generate``); **Conductance** computes the selected conductor's
value from its inputs (``thermal.conductors``). The JSON view edits the
same section. Checked: the spacecraft keeps a thermal model; unchecked:
none."""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Callable

from PySide6.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..schema import thermal as thermal_schema
from .theme import set_role
from .widgets import TabWidget

# Column kinds: "s" text, "f" number, "f?" number or blank, "i" whole number, "b" yes/no, "L" names "a, b",
# "R?" a range "low, high" or blank, "R" a range, "J" JSON or blank.
_NODE = (("name", "Name", "s"), ("parts", "Parts", "L"), ("capacitance_j_k", "Capacitance [J/K]", "f?"),
         ("mass_kg", "Mass [kg]", "f?"), ("specific_heat_j_kg_k", "Specific heat [J/(kg·K)]", "f?"),
         ("material", "Material", "s"), ("specific_heat_table", "cp table [[°C, J/(kg·K)], ...]", "J"),
         ("operating_c", "Operating [°C]", "R?"),
         ("survival_c", "Survival [°C]", "R?"), ("initial_c", "Initial [°C]", "f?"))
_FACE = (("part", "Part", "s"), ("face", "Face", "s"), ("node", "Node", "s"), ("coating", "Coating", "s"),
         ("absorptance", "Absorptance", "f?"), ("emissivity", "Emissivity", "f?"),
         ("mli_effective_emittance", "MLI e*", "f?"), ("radiator", "Radiator", "b"))
_CONDUCTOR = (("name", "Name", "s"), ("a", "Node a", "s"), ("b", "Node b", "s"), ("kind", "Kind", "s"),
              ("conductance_w_k", "Conductance [W/K]", "f?"), ("material", "Material", "s"),
              ("conductivity_w_m_k", "k [W/(m·K)]", "f?"), ("length_m", "Length [m]", "f?"),
              ("section_m2", "Section [m²]", "f?"), ("contact_area_m2", "Contact area [m²]", "f?"),
              ("contact_coefficient_w_m2_k", "Contact h [W/(m²·K)]", "f?"),
              ("conductivity_table", "k table [[°C, W/(m·K)], ...]", "J"))
_HEAT_PIPE = (("name", "Name", "s"), ("a", "Node a", "s"), ("b", "Node b", "s"),
              ("conductance_w_k", "Conductance [W/K]", "f"), ("operating_c", "Operating [°C]", "R"),
              ("off_conductance_w_k", "Outside it [W/K]", "f"))
_LINK = (("name", "Name", "s"), ("a", "Node a", "s"), ("b", "Node b", "s"),
         ("effective_area_m2", "ε·A·F [m²]", "f"))
_DISSIPATION = (("name", "Name", "s"), ("node", "Node", "s"), ("power_w", "Power [W]", "f?"),
                ("source", "Power-budget load", "s"))
_HEATER = (("name", "Name", "s"), ("node", "Node", "s"), ("power_w", "Power [W]", "f"), ("on_c", "On below [°C]", "f"),
           ("off_c", "Off above [°C]", "f"), ("enabled", "Enabled", "b"))
_CASE = (("name", "Name", "s"), ("preset", "Preset", "s"), ("overrides", "Overrides (JSON)", "J"))
_ENVIRONMENT = (("solar_flux_w_m2", "Solar flux at 1 AU [W/m²]", "f?"), ("albedo", "Albedo", "f?"),
                ("planet_ir_w_m2", "Planet IR [W/m²]", "f?"), ("albedo_model", "Albedo model", "s"))
_MONTE_CARLO = (("runs", "Runs", "i"), ("seed", "Seed", "i"), ("case", "Case", "s"))
_DISPERSION = (("path", "Parameter path", "s"), ("sigma", "Sigma (normal) or half-width (uniform)", "f"),
               ("distribution", "Distribution", "s"), ("relative", "Relative", "b"))
_SOLVER = (("time_step_s", "Time step [s]", "f"), ("start", "Start", "s"), ("tolerance_k", "Periodic tolerance [K]", "f"),
           ("max_orbits", "Max orbits", "i"), ("initial_c", "Initial [°C]", "f?"))

TABLES = (("nodes", "Nodes", thermal_schema.ThermalNodeConfig, _NODE),
          ("faces", "Faces", thermal_schema.ThermalFaceConfig, _FACE),
          ("conductors", "Conductors", thermal_schema.ThermalConductorConfig, _CONDUCTOR),
          ("heat_pipes", "Heat pipes", thermal_schema.ThermalHeatPipeConfig, _HEAT_PIPE),
          ("radiative_links", "Radiative links", thermal_schema.ThermalRadiativeLinkConfig, _LINK),
          ("dissipations", "Dissipation", thermal_schema.ThermalDissipationConfig, _DISSIPATION),
          ("heaters", "Heaters", thermal_schema.ThermalHeaterConfig, _HEATER),
          ("cases", "Cases", thermal_schema.ThermalCaseConfig, _CASE))
_TIPS = {
    "nodes": "One isothermal node per row: the parts it is made of, and its capacitance (or mass and specific heat, "
             "or the material's). Ranges are 'lowest, highest'.",
    "faces": "Optics per face ('part', face blank for all of the part's faces): a coating from the library or the "
             "model, or absorptance and emissivity; MLI e* puts a blanket on it; a radiator is reported.",
    "conductors": "Kind 'value' (the conductance), 'material' (k, length, section: k·A/L) or 'contact' (area × "
                  "coefficient). Select a row and press Conductance to see the value.",
    "heat_pipes": "High conductance within its operating range, the small one outside it.",
    "radiative_links": "An optional radiative exchange between two nodes (effective area, view factor included).",
    "dissipations": "Heat a node dissipates: a constant power, or a load of the power budget by name.",
    "heaters": "Thermostatic heaters: on below 'on', off above 'off'. Run › Thermal sizes them for the cold case.",
    "cases": "Cases with a preset (nominal, hot, cold) and overrides by path, e.g. {\"environment.albedo\": 0.3}. "
             "None: nominal, hot and cold.",
}


def _text(value, kind: str) -> str:
    if value is None:
        return ""
    if kind == "b":
        return "yes" if value else "no"
    if kind in ("L", "R", "R?"):
        return ", ".join(_number(v) for v in value)
    if kind == "J":
        return "" if value in ({}, []) else json.dumps(value)
    return _number(value)


def _number(value) -> str:
    """Floats as the shortest text that reads back the same (an edit
    round-trips every value exactly)."""
    if isinstance(value, float):
        return repr(int(value)) if value.is_integer() and abs(value) < 1e15 else repr(value)
    return str(value)


def _read(text: str, kind: str, where: str):
    text = text.strip()
    try:
        if kind == "s":
            return text
        if kind == "b":
            if text.lower() in ("yes", "true", "1", "on"):
                return True
            if text.lower() in ("", "no", "false", "0", "off"):
                return False
            raise ValueError(f"'{text}' is not yes or no")
        if kind == "L":
            return [name.strip() for name in text.split(",") if name.strip()]
        if kind == "J":
            return json.loads(text) if text else None
        if not text:
            if kind.endswith("?"):
                return None
            raise ValueError("a value is needed")
        if kind == "i":
            return int(text)
        if kind in ("R", "R?"):
            values = [float(v) for v in text.split(",")]
            if len(values) != 2:
                raise ValueError("give 'lowest, highest'")
            return values
        return float(text)
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"thermal.{where}: {exc}") from exc


def _note(text: str) -> QLabel:
    label = set_role(QLabel(text), tone="secondary")
    label.setWordWrap(True)
    return label


class RecordTable(QTableWidget):
    """A list of records of one dataclass, a row each."""

    def __init__(self, cls, columns, records=(), fixed_rows: bool = False, parent=None):
        super().__init__(0, len(columns), parent)
        self.cls, self.columns, self.fixed_rows = cls, columns, fixed_rows
        self.setHorizontalHeaderLabels([label for _name, label, _kind in columns])
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setStretchLastSection(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.set_records(records)

    def set_records(self, records) -> None:
        self.setRowCount(0)
        for record in records:
            self.add_record(record)

    def add_record(self, record=None) -> None:
        row = self.rowCount()
        self.insertRow(row)
        for column, (name, _label, kind) in enumerate(self.columns):
            value = getattr(record, name) if record is not None else None
            self.setItem(row, column, QTableWidgetItem(_text(value, kind)))

    def records(self, where: str) -> list:
        out = []
        for row in range(self.rowCount()):
            values = {}
            for column, (name, _label, kind) in enumerate(self.columns):
                item = self.item(row, column)
                value = _read(item.text() if item else "", kind, f"{where}[{row}].{name}")
                if value is not None or kind.endswith("?"):  # blank JSON: the field's default
                    values[name] = value
            try:
                out.append(self.cls(**values))
            except TypeError as exc:
                raise ValueError(f"thermal.{where}[{row}]: {exc}") from exc
        return out


class ThermalGroup(QGroupBox):
    """The thermal model of one spacecraft."""

    def __init__(self, config: thermal_schema.ThermalConfig | None,
                 spacecraft_provider: Callable[[], object] | None = None,
                 base_dir_provider: Callable[[], object] | None = None, parent=None):
        super().__init__("Thermal model", parent)
        self.setCheckable(True)
        self.setChecked(config is not None)
        self.setToolTip("A lumped-parameter thermal model on the 3D model's parts, solved after a run in "
                        "Run › Thermal (user manual, section 6, \"Thermal analysis\").")
        self._spacecraft_provider = spacecraft_provider
        self._base_dir_provider = base_dir_provider
        self._version = config.version if config is not None else thermal_schema.THERMAL_VERSION
        c = config or thermal_schema.ThermalConfig()
        layout = QVBoxLayout(self)
        buttons = QHBoxLayout()
        self.generate_button = QPushButton("Generate from the 3D model")
        self.generate_button.setToolTip("A node per part with its mass, every face with its material's optics, and "
                                        "a contact conductor between parts that touch (thermal.generate).")
        self.generate_button.clicked.connect(self._on_generate)
        buttons.addWidget(self.generate_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.tabs = TabWidget()
        self.tables: dict[str, RecordTable] = {}
        for key, title, cls, columns in TABLES:
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.addWidget(_note(_TIPS[key]))
            table = RecordTable(cls, columns, getattr(c, key))
            page_layout.addWidget(table)
            row = QHBoxLayout()
            add = QPushButton("Add")
            add.clicked.connect(lambda _checked=False, t=table: t.add_record())
            remove = QPushButton("Remove")
            remove.clicked.connect(lambda _checked=False, t=table: t.removeRow(t.currentRow())
                                   if t.currentRow() >= 0 else None)
            row.addWidget(add)
            row.addWidget(remove)
            if key == "conductors":
                self.conductance_button = QPushButton("Conductance")
                self.conductance_button.setToolTip("The selected conductor's conductance from its inputs")
                self.conductance_button.clicked.connect(self._on_conductance)
                row.addWidget(self.conductance_button)
                self.conductance_label = set_role(QLabel(""), tone="secondary")
                row.addWidget(self.conductance_label, 1)
            row.addStretch(1)
            page_layout.addLayout(row)
            self.tabs.addTab(page, title)
            self.tables[key] = table
        settings = QWidget()
        settings_layout = QVBoxLayout(settings)
        settings_layout.addWidget(_note("Environment (blank: the run's own, by the central body and the orbit's "
                                        "inclination band)"))
        self.environment_table = RecordTable(thermal_schema.ThermalEnvironmentConfig, _ENVIRONMENT, [c.environment],
                                             fixed_rows=True)
        settings_layout.addWidget(self.environment_table)
        settings_layout.addWidget(_note("Solver: start 'periodic' (repeats orbits until they repeat) or 'fixed' "
                                        "(from the initial temperatures)"))
        self.solver_table = RecordTable(thermal_schema.ThermalSolverConfig, _SOLVER, [c.solver], fixed_rows=True)
        settings_layout.addWidget(self.solver_table)
        settings_layout.addStretch(1)
        self.tabs.addTab(settings, "Environment and solver")
        studies = QWidget()
        studies_layout = QVBoxLayout(studies)
        studies_layout.addWidget(_note("Thermal Monte Carlo (Run › Thermal › Monte Carlo...): the runs, the seed (the "
                                       "same seed, the same draws), the case, and the parameters it draws by path. "
                                       "No dispersion: no Monte Carlo."))
        mc = c.monte_carlo or thermal_schema.ThermalMonteCarloConfig()
        self.monte_carlo_table = RecordTable(thermal_schema.ThermalMonteCarloConfig, _MONTE_CARLO, [mc],
                                             fixed_rows=True)
        studies_layout.addWidget(self.monte_carlo_table)
        self.dispersion_table = RecordTable(thermal_schema.ThermalDispersionConfig, _DISPERSION, mc.dispersions)
        studies_layout.addWidget(self.dispersion_table)
        row = QHBoxLayout()
        add = QPushButton("Add")
        add.clicked.connect(lambda: self.dispersion_table.add_record(
            thermal_schema.ThermalDispersionConfig("", 0.1, "normal", True)))
        remove = QPushButton("Remove")
        remove.clicked.connect(lambda: self.dispersion_table.removeRow(self.dispersion_table.currentRow())
                               if self.dispersion_table.currentRow() >= 0 else None)
        row.addWidget(add)
        row.addWidget(remove)
        row.addStretch(1)
        studies_layout.addLayout(row)
        studies_layout.addStretch(1)
        self.tabs.addTab(studies, "Monte Carlo")
        layout.addWidget(self.tabs)
        self.status_label = set_role(QLabel(""), tone="secondary")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    def field_widget(self, name: str) -> QWidget | None:
        """The table holding the field ``name`` ("nodes"), shown, or None."""
        key = name.split("[")[0].split(".")[0]
        table = self.tables.get(key) or {"environment": self.environment_table, "solver": self.solver_table,
                                         "monte_carlo": self.dispersion_table}.get(key)
        if table is None:
            return None
        self.tabs.setCurrentWidget(table.parentWidget())
        return table

    def set_config(self, config: thermal_schema.ThermalConfig) -> None:
        self.setChecked(True)
        self._version = config.version
        for key, table in self.tables.items():
            table.set_records(getattr(config, key))
        self.environment_table.set_records([config.environment])
        self.solver_table.set_records([config.solver])
        mc = config.monte_carlo or thermal_schema.ThermalMonteCarloConfig()
        self.monte_carlo_table.set_records([mc])
        self.dispersion_table.set_records(mc.dispersions)

    def to_config(self) -> thermal_schema.ThermalConfig | None:
        """The thermal model, or None when the group is off. A cell that
        does not read is refused with its place (``thermal.nodes[1].mass_kg``)."""
        if not self.isChecked():
            return None
        values = {key: table.records(key) for key, table in self.tables.items()}
        environment = self.environment_table.records("environment")
        solver = self.solver_table.records("solver")
        dispersions = self.dispersion_table.records("monte_carlo.dispersions")
        monte_carlo = None
        if dispersions:
            monte_carlo = self.monte_carlo_table.records("monte_carlo")[0]
            monte_carlo.dispersions = dispersions
        return thermal_schema.ThermalConfig(
            version=self._version, **values,
            environment=environment[0] if environment else thermal_schema.ThermalEnvironmentConfig(),
            solver=solver[0] if solver else thermal_schema.ThermalSolverConfig(), monte_carlo=monte_carlo)

    def _on_generate(self) -> None:
        from ..thermal import generate

        spacecraft = self._spacecraft_provider() if self._spacecraft_provider else None
        if spacecraft is None or getattr(spacecraft, "model", None) is None:
            self.status_label.setText("Generate needs a 3D model: build or open one first.")
            return
        has_records = any(table.rowCount() for table in self.tables.values())
        if has_records and QMessageBox.question(
                self, "Replace the thermal model?",
                "Generating replaces the nodes, faces and conductors with ones from the 3D model; heat pipes, "
                "heaters, dissipation and cases are kept.") != QMessageBox.StandardButton.Yes:
            return
        try:
            generated = generate.generate(spacecraft, self._base_dir_provider() if self._base_dir_provider else None)
        except (ValueError, OSError) as exc:
            self.status_label.setText(f"Could not generate: {exc}")
            return
        kept = self.to_config() if has_records else None
        model = generated.thermal
        if kept is not None:
            model = dataclasses.replace(model, heat_pipes=kept.heat_pipes, radiative_links=kept.radiative_links,
                                        dissipations=kept.dissipations, heaters=kept.heaters, cases=kept.cases,
                                        environment=kept.environment, solver=kept.solver)
        self.set_config(model)
        self.status_label.setText(f"Generated {len(model.nodes)} nodes, {len(model.faces)} face entries and "
                                  f"{len(model.conductors)} conductors. " + " ".join(generated.notes))

    def _on_conductance(self) -> None:
        from ..thermal import conductors

        table = self.tables["conductors"]
        row = table.currentRow()
        if row < 0:
            self.conductance_label.setText("Select a conductor.")
            return
        try:
            record = table.records("conductors")[row]
            spacecraft = self._spacecraft_provider() if self._spacecraft_provider else None
            materials = getattr(getattr(spacecraft, "model", None), "materials", ()) or ()
            value = conductors.conductance(record, materials)
        except (ValueError, TypeError, conductors.ConductorError) as exc:
            self.conductance_label.setText(f"{exc}")
            return
        self.conductance_label.setText(f"{record.name}: {value.value_w_k:.4g} W/K ({value.how})")
