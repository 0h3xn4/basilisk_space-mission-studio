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
"""The ``thermal`` section of a spacecraft: a lumped-parameter (nodal)
thermal model built on the spacecraft's 3D model and solved after a run
(``spacemissionstudio.thermal``; ``docs/developer/thermal-design.md``).

Nodes own the external faces of the model's parts; ``faces`` entries give
a face (or a whole part) its optics, move it to another node, cover it with
MLI or flag it as a radiator. Optics not given here come from the face's or
the part's material in the model (decision T-02). Every entry with a
``name`` (and every face, as ``"part:face"``) is reachable by a parameter
path such as ``nodes[battery].capacitance_j_k`` (T-13).

The section has its own ``version`` so it can change without moving the
scenario's schema version; it is optional and written only when set, so a
scenario without it saves and hashes as before. Without numpy, Basilisk
or the GUI, like the rest of the schema.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import NamedTuple

THERMAL_VERSION = 1
CONDUCTOR_KINDS = ("value", "material", "contact")
START_MODES = ("periodic", "steady", "fixed")
ALBEDO_MODELS = ("map", "average")
CASE_PRESETS = ("", "nominal", "hot", "cold")
#: Central bodies with an albedo and a planetary infrared model (T-17).
THERMAL_CENTRAL_BODIES = ("earth", "mars barycenter")
#: The power-budget loads a dissipation can follow (T-11); instruments are
#: ``instrument:<name>``.
POWER_LOADS = ("bus", "comms", "transmitter")

_ABSOLUTE_ZERO_C = -273.15  # [degC]
_MAX_TEMPERATURE_C = 2000.0  # [degC] a plausibility ceiling for limits and setpoints
_MAX_POWER_W = 1.0e5  # [W] well above any unit of this size class
_MAX_CONDUCTANCE_W_K = 1.0e6  # [W/K]


def _fail(message: str) -> None:
    from .scenario import ScenarioValidationError

    raise ScenarioValidationError(message)


def _require(condition: bool, message: str) -> None:
    if not condition:
        _fail(message)


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _optional_range(value, where: str, name: str, low: float, high: float, closed_low: bool = True) -> None:
    if value is None:
        return
    ok = _number(value) and (value >= low if closed_low else value > low) and value <= high
    _require(ok, f"{where}: {name} must be in {'[' if closed_low else '('}{low:g}, {high:g}]")


def _limits(value, where: str, name: str) -> None:
    if value is None:
        return
    _require(isinstance(value, list) and len(value) == 2 and all(_number(v) for v in value)
             and _ABSOLUTE_ZERO_C < value[0] < value[1] <= _MAX_TEMPERATURE_C,
             f"{where}: {name} must be [lowest, highest] in degC, lowest below highest and above -273.15")


def _name(value, where: str, what: str) -> None:
    _require(isinstance(value, str) and value.strip() == value and bool(value) and "]" not in value
             and "." not in value, f"{where}: a {what} needs a name without '.', ']' or surrounding spaces")


@dataclass
class ThermalNodeConfig:
    """A node: one temperature with a heat capacity. It owns the external
    faces of ``parts`` (less those a ``faces`` entry moves elsewhere); a
    node with none is internal. The capacity is ``capacitance_j_k``, or
    ``mass_kg`` (else its parts' mass) times ``specific_heat_j_kg_k``
    (else its ``material``'s, else its parts' material's, else
    aluminium's, T-05), or that mass times a ``specific_heat_table`` of
    temperature (Phase 2: the solver then integrates the enthalpy)."""

    name: str
    parts: list = field(default_factory=list)  # names of the model's parts
    capacitance_j_k: float | None = None  # [J/K]
    mass_kg: float | None = None  # [kg]
    specific_heat_j_kg_k: float | None = None  # [J/(kg*K)]
    material: str = ""  # a library or model material, for its specific heat
    specific_heat_table: list | None = None  # [[degC, J/(kg*K)], ...] temperature-dependent (Phase 2)
    operating_c: list | None = None  # [degC] [lowest, highest]
    survival_c: list | None = None  # [degC] [lowest, highest]
    initial_c: float | None = None  # [degC] for start "fixed"

    def validate(self, where: str) -> None:
        _name(self.name, where, "node")
        if self.specific_heat_table is not None:
            _table(self.specific_heat_table, f"{where}: node {self.name!r}", "specific_heat_table")
            _require(self.capacitance_j_k is None and self.specific_heat_j_kg_k is None,
                     f"{where}: node {self.name!r}: give specific_heat_table, or capacitance_j_k or "
                     "specific_heat_j_kg_k, not both")
        where = f"{where}: node {self.name!r}"
        _require(isinstance(self.parts, list) and all(isinstance(p, str) and p for p in self.parts)
                 and len(set(self.parts)) == len(self.parts), f"{where}: parts must be a list of distinct part names")
        _optional_range(self.capacitance_j_k, where, "capacitance_j_k", 0.0, 1.0e9, closed_low=False)
        _optional_range(self.mass_kg, where, "mass_kg", 0.0, 1.0e5, closed_low=False)
        _optional_range(self.specific_heat_j_kg_k, where, "specific_heat_j_kg_k", 0.0, 1.0e5, closed_low=False)
        _limits(self.operating_c, where, "operating_c")
        _limits(self.survival_c, where, "survival_c")
        if self.operating_c is not None and self.survival_c is not None:
            _require(self.survival_c[0] <= self.operating_c[0] and self.operating_c[1] <= self.survival_c[1],
                     f"{where}: operating_c must lie within survival_c")
        _optional_range(self.initial_c, where, "initial_c", _ABSOLUTE_ZERO_C, _MAX_TEMPERATURE_C, closed_low=False)


@dataclass
class ThermalFaceConfig:
    """A face of a part (``face`` "" for every face of the part, or a face
    group such as "sides"): its optics, the node it belongs to when not its
    part's node, MLI and the radiator flag. A thin panel's two sides are
    its faces "+z" and "-z"."""

    part: str
    face: str = ""
    node: str = ""  # "" for the node owning the part
    coating: str = ""  # a library or model material giving absorptance and emissivity
    absorptance: float | None = None  # [-] solar
    emissivity: float | None = None  # [-] infrared, hemispherical
    mli_effective_emittance: float | None = None  # [-] e* of an MLI blanket on the face (T-09)
    radiator: bool = False

    @property
    def name(self) -> str:
        """``"part:face"`` (or the part's name for every face): the key a
        parameter path uses, ``faces[bus:+x].absorptance``."""
        return f"{self.part}:{self.face}" if self.face else self.part

    def validate(self, where: str) -> None:
        _require(isinstance(self.part, str) and bool(self.part), f"{where}: a face entry needs a part")
        _require(isinstance(self.face, str), f"{where}: {self.part}: face must be a face name or \"\"")
        where = f"{where}: face {self.name!r}"
        _optional_range(self.absorptance, where, "absorptance", 0.0, 1.0)
        _optional_range(self.emissivity, where, "emissivity", 0.0, 1.0)
        _optional_range(self.mli_effective_emittance, where, "mli_effective_emittance", 0.0, 1.0, closed_low=False)
        _require(isinstance(self.radiator, bool), f"{where}: radiator must be true or false")
        _require(not (self.radiator and self.mli_effective_emittance is not None),
                 f"{where}: a radiator face cannot be covered with MLI")


@dataclass
class ThermalConductorConfig:
    """A linear conductance between two nodes [W/K]. ``kind`` says how it
    is given, so the value can be traced (``thermal.conductors``):
    ``value`` (``conductance_w_k``), ``material`` (``conductivity_w_m_k``,
    or the material's, times ``section_m2`` over ``length_m``) or
    ``contact`` (``contact_area_m2`` times ``contact_coefficient_w_m2_k``)."""

    name: str
    a: str
    b: str
    kind: str = "value"
    conductance_w_k: float | None = None  # [W/K]
    material: str = ""
    conductivity_w_m_k: float | None = None  # [W/(m*K)]
    length_m: float | None = None  # [m]
    section_m2: float | None = None  # [m^2]
    contact_area_m2: float | None = None  # [m^2]
    contact_coefficient_w_m2_k: float | None = None  # [W/(m^2*K)]
    conductivity_table: list | None = None  # [[degC, W/(m*K)], ...] Phase 2, for kind "material"

    def validate(self, where: str) -> None:
        _name(self.name, where, "conductor")
        where = f"{where}: conductor {self.name!r}"
        _require(self.a != self.b, f"{where}: a and b must be different nodes")
        _require(self.kind in CONDUCTOR_KINDS, f"{where}: kind must be one of {list(CONDUCTOR_KINDS)}")
        _optional_range(self.conductance_w_k, where, "conductance_w_k", 0.0, _MAX_CONDUCTANCE_W_K)
        _optional_range(self.conductivity_w_m_k, where, "conductivity_w_m_k", 0.0, 1.0e4, closed_low=False)
        _optional_range(self.length_m, where, "length_m", 0.0, 100.0, closed_low=False)
        _optional_range(self.section_m2, where, "section_m2", 0.0, 100.0, closed_low=False)
        _optional_range(self.contact_area_m2, where, "contact_area_m2", 0.0, 100.0, closed_low=False)
        _optional_range(self.contact_coefficient_w_m2_k, where, "contact_coefficient_w_m2_k", 0.0, 1.0e6,
                        closed_low=False)
        if self.kind == "value":
            _require(self.conductance_w_k is not None, f"{where}: kind \"value\" needs conductance_w_k")
        elif self.kind == "material":
            _require(self.length_m is not None and self.section_m2 is not None,
                     f"{where}: kind \"material\" needs length_m and section_m2")
            _require(self.conductivity_w_m_k is not None or self.material or self.conductivity_table,
                     f"{where}: kind \"material\" needs conductivity_w_m_k, a material or a conductivity_table")
        else:
            _require(self.contact_area_m2 is not None and self.contact_coefficient_w_m2_k is not None,
                     f"{where}: kind \"contact\" needs contact_area_m2 and contact_coefficient_w_m2_k")
        if self.conductivity_table is not None:
            _table(self.conductivity_table, where, "conductivity_table")


def _table(table, where: str, name: str) -> None:
    _require(isinstance(table, list) and len(table) >= 2
             and all(isinstance(row, list) and len(row) == 2 and all(_number(v) for v in row) for row in table)
             and all(table[k][0] < table[k + 1][0] for k in range(len(table) - 1))
             and all(row[1] > 0 for row in table) and table[0][0] > _ABSOLUTE_ZERO_C,
             f"{where}: {name} must be at least two [degC, value] rows, temperatures increasing, values > 0")


@dataclass
class ThermalHeatPipeConfig:
    """A heat pipe as a high conductance between two nodes while its
    hotter end is within ``operating_c``, and ``off_conductance_w_k``
    outside (an approximation, decision T-08)."""

    name: str
    a: str
    b: str
    conductance_w_k: float  # [W/K] while operating
    operating_c: list = field(default_factory=lambda: [-40.0, 80.0])  # [degC] [lowest, highest]
    off_conductance_w_k: float = 0.01  # [W/K] frozen or dried out

    def validate(self, where: str) -> None:
        _name(self.name, where, "heat pipe")
        where = f"{where}: heat pipe {self.name!r}"
        _require(self.a != self.b, f"{where}: a and b must be different nodes")
        _optional_range(self.conductance_w_k, where, "conductance_w_k", 0.0, _MAX_CONDUCTANCE_W_K, closed_low=False)
        _optional_range(self.off_conductance_w_k, where, "off_conductance_w_k", 0.0, _MAX_CONDUCTANCE_W_K)
        _require(_number(self.conductance_w_k), f"{where}: conductance_w_k must be a number")
        _require(_number(self.off_conductance_w_k) and self.off_conductance_w_k <= self.conductance_w_k,
                 f"{where}: off_conductance_w_k must not exceed conductance_w_k")
        _require(self.operating_c is not None, f"{where}: operating_c is needed")
        _limits(self.operating_c, where, "operating_c")


@dataclass
class ThermalRadiativeLinkConfig:
    """Radiation between two nodes, ``sigma * eA * (Ta^4 - Tb^4)`` with
    ``effective_area_m2`` = eA given by the user (T-10)."""

    name: str
    a: str
    b: str
    effective_area_m2: float  # [m^2] emittance times area, view factor included

    def validate(self, where: str) -> None:
        _name(self.name, where, "radiative link")
        where = f"{where}: radiative link {self.name!r}"
        _require(self.a != self.b, f"{where}: a and b must be different nodes")
        _optional_range(self.effective_area_m2, where, "effective_area_m2", 0.0, 1000.0, closed_low=False)
        _require(_number(self.effective_area_m2), f"{where}: effective_area_m2 must be a number")


@dataclass
class ThermalDissipationConfig:
    """Heat a unit dissipates in a node: ``power_w``, or the power of the
    power-budget load ``source`` names (``bus``, ``comms``,
    ``transmitter``, ``instrument:<name>``; T-11)."""

    name: str
    node: str
    power_w: float | None = None  # [W]
    source: str = ""

    def validate(self, where: str) -> None:
        _name(self.name, where, "dissipation")
        where = f"{where}: dissipation {self.name!r}"
        _require((self.power_w is None) != (self.source == ""),
                 f"{where}: give either power_w or source (a power-budget load), not both")
        _optional_range(self.power_w, where, "power_w", 0.0, _MAX_POWER_W)


@dataclass
class ThermalHeaterConfig:
    """A thermostatic heater: on below ``on_c``, off above ``off_c``
    (hysteresis), ``power_w`` while on. Sizing finds the least power that
    holds the node at or above ``on_c`` (T-12)."""

    name: str
    node: str
    power_w: float  # [W]
    on_c: float  # [degC]
    off_c: float  # [degC]
    enabled: bool = True

    def validate(self, where: str) -> None:
        _name(self.name, where, "heater")
        where = f"{where}: heater {self.name!r}"
        _optional_range(self.power_w, where, "power_w", 0.0, _MAX_POWER_W)
        _require(_number(self.power_w), f"{where}: power_w must be a number")
        _require(_number(self.on_c) and _number(self.off_c) and _ABSOLUTE_ZERO_C < self.on_c < self.off_c
                 <= _MAX_TEMPERATURE_C, f"{where}: on_c must be below off_c (degC, above -273.15)")
        _require(isinstance(self.enabled, bool), f"{where}: enabled must be true or false")


@dataclass
class ThermalEnvironmentConfig:
    """The environment the base model is solved in; None takes the run's
    (the solar flux at the spacecraft's distance from 1361 W/m^2 at 1 AU,
    the central body's albedo map and its mean infrared). Cases override
    these (``thermal.cases``)."""

    solar_flux_w_m2: float | None = None  # [W/m^2] at 1 AU
    albedo: float | None = None  # [-] a constant albedo coefficient (the map's otherwise)
    planet_ir_w_m2: float | None = None  # [W/m^2] outgoing longwave radiation at the top of the atmosphere
    albedo_model: str = "map"  # "map" (Basilisk's CERES/TES data) or "average"

    def validate(self, where: str) -> None:
        where = f"{where}: environment"
        _optional_range(self.solar_flux_w_m2, where, "solar_flux_w_m2", 0.0, 1.0e5, closed_low=False)
        _optional_range(self.albedo, where, "albedo", 0.0, 1.0)
        _optional_range(self.planet_ir_w_m2, where, "planet_ir_w_m2", 0.0, 2000.0)
        _require(self.albedo_model in ALBEDO_MODELS, f"{where}: albedo_model must be one of {list(ALBEDO_MODELS)}")


@dataclass
class ThermalSolverConfig:
    """How the network is solved (T-07): the time step, independent of
    the run's recording; the start (``periodic``: the first orbit repeated
    until no node changes by more than ``tolerance_k`` over an orbit;
    ``steady``: the orbit-average steady state; ``fixed``: each node's
    ``initial_c``, else ``initial_c`` here)."""

    time_step_s: float = 30.0  # [s]
    start: str = "periodic"
    tolerance_k: float = 0.01  # [K]
    max_orbits: int = 50
    initial_c: float | None = None  # [degC]

    def validate(self, where: str) -> None:
        where = f"{where}: solver"
        _optional_range(self.time_step_s, where, "time_step_s", 0.1, 3600.0)
        _require(_number(self.time_step_s), f"{where}: time_step_s must be a number")
        _require(self.start in START_MODES, f"{where}: start must be one of {list(START_MODES)}")
        _optional_range(self.tolerance_k, where, "tolerance_k", 0.0, 10.0, closed_low=False)
        _require(isinstance(self.max_orbits, int) and not isinstance(self.max_orbits, bool)
                 and 1 <= self.max_orbits <= 1000, f"{where}: max_orbits must be an integer from 1 to 1000")
        _optional_range(self.initial_c, where, "initial_c", _ABSOLUTE_ZERO_C, _MAX_TEMPERATURE_C, closed_low=False)


@dataclass
class ThermalCaseConfig:
    """A named case: a preset (``nominal``, ``hot``, ``cold``; section 4
    of the design) and parameter overrides ``{path: value}`` on top of it,
    paths into the thermal section (T-13)."""

    name: str
    preset: str = ""
    overrides: dict = field(default_factory=dict)

    def validate(self, where: str) -> None:
        _name(self.name, where, "case")
        where = f"{where}: case {self.name!r}"
        _require(self.preset in CASE_PRESETS, f"{where}: preset must be one of {list(CASE_PRESETS)}")
        _require(isinstance(self.overrides, dict) and all(isinstance(k, str) and k for k in self.overrides),
                 f"{where}: overrides must map parameter paths to values")


DISTRIBUTIONS = ("normal", "uniform")


@dataclass
class ThermalDispersionConfig:
    """One parameter a thermal Monte Carlo draws (Phase 2, T-36): its
    ``path`` (as an override's), and ``sigma``, the 1-sigma of a normal
    draw or the half-width of a uniform one, in the parameter's unit or,
    ``relative``, as a fraction of its value."""

    path: str
    sigma: float
    distribution: str = "normal"
    relative: bool = False

    def validate(self, where: str) -> None:
        _require(isinstance(self.path, str) and self.path.strip(), f"{where}: a dispersion needs a path")
        where = f"{where}: dispersion {self.path!r}"
        _require(self.distribution in DISTRIBUTIONS, f"{where}: distribution must be one of {list(DISTRIBUTIONS)}")
        _require(_number(self.sigma) and self.sigma > 0, f"{where}: sigma must be a number above 0")
        _require(isinstance(self.relative, bool), f"{where}: relative must be true or false")


@dataclass
class ThermalMonteCarloConfig:
    """A thermal Monte Carlo on one run (Phase 2, T-36): ``runs`` draws of
    the ``dispersions``, from ``seed``, each solved in ``case``."""

    runs: int = 50
    seed: int = 1
    case: str = "nominal"
    dispersions: list = field(default_factory=list)  # list[ThermalDispersionConfig]

    def validate(self, where: str) -> None:
        where = f"{where}: monte_carlo"
        _require(isinstance(self.runs, int) and not isinstance(self.runs, bool) and 2 <= self.runs <= 10000,
                 f"{where}: runs must be an integer from 2 to 10000")
        _require(isinstance(self.seed, int) and not isinstance(self.seed, bool) and 0 <= self.seed < 2 ** 32,
                 f"{where}: seed must be an integer from 0 to 2^32 - 1")
        _require(isinstance(self.case, str) and self.case, f"{where}: case must name a case or a preset")
        _require(bool(self.dispersions), f"{where}: give at least one dispersion")
        for item in self.dispersions:
            item.validate(where)
        paths = [item.path for item in self.dispersions]
        _require(len(set(paths)) == len(paths), f"{where}: each path is dispersed once")


@dataclass
class ThermalConfig:
    """A spacecraft's thermal model (module docstring)."""

    version: int = THERMAL_VERSION
    nodes: list = field(default_factory=list)  # list[ThermalNodeConfig]
    faces: list = field(default_factory=list)  # list[ThermalFaceConfig]
    conductors: list = field(default_factory=list)  # list[ThermalConductorConfig]
    heat_pipes: list = field(default_factory=list)  # list[ThermalHeatPipeConfig]
    radiative_links: list = field(default_factory=list)  # list[ThermalRadiativeLinkConfig]
    dissipations: list = field(default_factory=list)  # list[ThermalDissipationConfig]
    heaters: list = field(default_factory=list)  # list[ThermalHeaterConfig]
    environment: ThermalEnvironmentConfig = field(default_factory=ThermalEnvironmentConfig)
    solver: ThermalSolverConfig = field(default_factory=ThermalSolverConfig)
    cases: list = field(default_factory=list)  # list[ThermalCaseConfig]
    monte_carlo: ThermalMonteCarloConfig | None = None  # Phase 2 (T-36)

    def node_names(self) -> list[str]:
        return [node.name for node in self.nodes]

    def validate(self, where: str, context: ThermalContext) -> None:
        """Check the section against the spacecraft: every name it uses
        exists, every reference resolves (``context``)."""
        where = f"{where}: thermal"
        _require(self.version == THERMAL_VERSION,
                 f"{where}: version {self.version!r} is not one this version reads (it reads {THERMAL_VERSION})")
        _require(bool(self.nodes), f"{where}: a thermal model needs at least one node")
        for group in ("nodes", "conductors", "heat_pipes", "radiative_links", "dissipations", "heaters", "cases"):
            items = getattr(self, group)
            for item in items:
                item.validate(where)
            names = [item.name for item in items]
            duplicates = sorted({n for n in names if names.count(n) > 1})
            _require(not duplicates, f"{where}: {group} names must be unique ({', '.join(duplicates)} repeated)")
        if self.monte_carlo is not None:
            _require(isinstance(self.monte_carlo, ThermalMonteCarloConfig), f"{where}: monte_carlo must be an object")
            self.monte_carlo.validate(where)
            known = {case.name for case in self.cases} if self.cases else set(CASE_PRESETS) - {""}
            _require(self.monte_carlo.case in known,
                     f"{where}: monte_carlo: case {self.monte_carlo.case!r} is not one of {sorted(known)}")
        nodes = set(self.node_names())
        owner: dict[str, str] = {}
        for node in self.nodes:
            for part in node.parts:
                _require(part in context.parts, f"{where}: node {node.name!r}: part {part!r} is not in the 3D model")
                _require(part not in owner, f"{where}: part {part!r} belongs to nodes {owner.get(part)!r} and "
                                            f"{node.name!r}; a part belongs to one node (move faces with 'faces')")
                owner[part] = node.name
            _require(not node.material or node.material in context.materials,
                     f"{where}: node {node.name!r}: material {node.material!r} is not in the library or the model")
        keys = []
        for entry in self.faces:
            entry.validate(where)
            _require(entry.part in context.parts, f"{where}: face {entry.name!r}: part {entry.part!r} is not in "
                                                  "the 3D model")
            allowed = context.parts[entry.part]
            _require(entry.face == "" or allowed is None or entry.face in allowed,
                     f"{where}: face {entry.name!r}: {entry.face!r} is not a face of {entry.part!r}"
                     + (f" ({_shown(allowed)})" if allowed else " (an imported mesh takes optics per part, T-03)"))
            _require(entry.node == "" or entry.node in nodes,
                     f"{where}: face {entry.name!r}: node {entry.node!r} is not a node of the thermal model")
            _require(entry.node != "" or entry.part in owner,
                     f"{where}: face {entry.name!r}: part {entry.part!r} belongs to no node; name one with 'node'")
            _require(not entry.coating or entry.coating in context.materials,
                     f"{where}: face {entry.name!r}: coating {entry.coating!r} is not in the library or the model")
            keys.append(entry.name)
        repeated = sorted({k for k in keys if keys.count(k) > 1})
        _require(not repeated, f"{where}: faces {', '.join(repeated)} are given more than once")
        for group, what in (("conductors", "conductor"), ("heat_pipes", "heat pipe"),
                            ("radiative_links", "radiative link")):
            for item in getattr(self, group):
                for end in (item.a, item.b):
                    _require(end in nodes, f"{where}: {what} {item.name!r}: {end!r} is not a node")
                if group == "conductors" and item.material:
                    _require(item.material in context.materials,
                             f"{where}: conductor {item.name!r}: material {item.material!r} is not in the library "
                             "or the model")
        for item in self.dissipations:
            _require(item.node in nodes, f"{where}: dissipation {item.name!r}: {item.node!r} is not a node")
            _require(item.source == "" or item.source in context.power_loads,
                     f"{where}: dissipation {item.name!r}: {item.source!r} is not a power-budget load of this "
                     f"spacecraft ({_shown(context.power_loads) or 'it has none'})")
        for item in self.heaters:
            _require(item.node in nodes, f"{where}: heater {item.name!r}: {item.node!r} is not a node")
        self.environment.validate(where)
        self.solver.validate(where)


def _shown(names) -> str:
    names = list(names)
    return ", ".join(names[:12]) + (", ..." if len(names) > 12 else "")


class ThermalContext(NamedTuple):
    """What a thermal section is checked against: each part's face names
    (None for an imported mesh, which takes optics per part), the material
    names and the power-budget loads."""

    parts: dict  # part name -> tuple of face and face-group names, or None
    materials: set
    power_loads: tuple


def shape_face_names(part) -> tuple | None:
    """The face names and face groups of a model part (``model3d.shapes``),
    or None for an imported mesh."""
    from .scenario import MODEL_SHAPE_FACES

    shape = part.shape
    groups = tuple(MODEL_SHAPE_FACES.get(shape, ()))
    if shape == "mesh":
        return None
    if shape == "prism":
        count = int(part.sides)
    elif shape in ("cylinder", "cone"):
        count = int(part.segments)
    elif shape == "sphere":
        return tuple(f"face {k + 1}" for k in range(max(2 * int(part.segments), 8)))
    else:
        return groups
    return groups + tuple(f"side {k + 1}" for k in range(count))


def power_loads(spacecraft) -> tuple:
    """The power-budget loads of ``spacecraft`` a dissipation can follow."""
    loads = []
    if spacecraft.power is not None:
        loads.append("bus")
    if spacecraft.comms_pointing is not None and spacecraft.comms_pointing.comms_power_w > 0:
        loads.append("comms")
    handling = spacecraft.data_handling
    if handling is not None:
        if handling.transmitter_power_w > 0:
            loads.append("transmitter")
        loads += [f"instrument:{i.name}" for i in handling.instruments if i.power_w > 0]
    return tuple(loads)


def context_for(spacecraft) -> ThermalContext:
    """The :class:`ThermalContext` of a spacecraft."""
    from ..config.materials import MATERIALS

    model = spacecraft.model
    parts = {} if model is None else {part.name: shape_face_names(part) for part in model.parts}
    materials = set(MATERIALS) | ({m.name for m in model.materials} if model is not None else set())
    return ThermalContext(parts, materials, power_loads(spacecraft))


_LISTS = (("nodes", ThermalNodeConfig), ("faces", ThermalFaceConfig), ("conductors", ThermalConductorConfig),
          ("heat_pipes", ThermalHeatPipeConfig), ("radiative_links", ThermalRadiativeLinkConfig),
          ("dissipations", ThermalDissipationConfig), ("heaters", ThermalHeaterConfig),
          ("cases", ThermalCaseConfig))


def from_dict(data, where: str, record, records, fields_of) -> ThermalConfig:
    """The section read from its JSON object, with the scenario loader's
    record builders (so every structural error reads the same)."""
    data = fields_of(data, where)
    for name, cls in _LISTS:
        data[name] = records(cls, data.pop(name, []), f"{where}.{name}")
    for name, cls in (("environment", ThermalEnvironmentConfig), ("solver", ThermalSolverConfig)):
        data[name] = record(cls, data[name], f"{where}.{name}") if data.get(name) is not None else cls()
    if data.get("monte_carlo") is not None:
        section = fields_of(data["monte_carlo"], f"{where}.monte_carlo")
        section["dispersions"] = records(ThermalDispersionConfig, section.pop("dispersions", []),
                                         f"{where}.monte_carlo.dispersions")
        data["monte_carlo"] = record(ThermalMonteCarloConfig, section, f"{where}.monte_carlo")
    return record(ThermalConfig, data, where)


def compact(section: dict) -> dict:
    """The saved form of a section (``dataclasses.asdict``): None values
    and empty lists left out, so a section saves only what it sets."""
    out: dict = {"version": section["version"]}
    for name, _cls in _LISTS:
        items = [{k: v for k, v in item.items() if v is not None and v != "" and v != {}}
                 for item in section.get(name, [])]
        if items:
            out[name] = items
    for name in ("environment", "solver"):
        defaults = (ThermalEnvironmentConfig if name == "environment" else ThermalSolverConfig)().__dict__
        changed = {k: v for k, v in section[name].items() if v is not None and v != defaults.get(k)}
        if changed:
            out[name] = changed
    if section.get("monte_carlo") is not None:
        out["monte_carlo"] = dict(section["monte_carlo"])
    return out
