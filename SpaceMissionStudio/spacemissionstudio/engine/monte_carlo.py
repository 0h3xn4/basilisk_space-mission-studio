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

r"""
Phase 3: Monte Carlo batch execution, wrapping the real, already-native
``Basilisk.utilities.MonteCarlo`` framework (``Controller``,
``Dispersions``, ``RetentionPolicy``) -- this module does not reimplement
any dispersion math or batch-execution logic; it only translates
:class:`schema.scenario.MonteCarloConfig`/``DispersionConfig`` into calls
against that framework, matching the pattern already `.md` documented in
``src/utilities/MonteCarlo/README.md`` and exercised end-to-end in
``examples/scenarioMonteCarloAttRW.py``.

Why ``SimulationService.build(initialize=False)``
---------------------------------------------------
``Controller`` calls, per run: creation function (no args, returns a
``SimBaseClass``) -> apply dispersions (mutating attributes directly on
that returned sim object, via dotted/indexed/zero-arg-method path strings
-- see ``Controller.SimulationExecutor.getNestedAttr``/``setNestedAttr``)
-> configure function (optional) -> execution function. Basilisk's
``InitializeSimulation()`` calls ``Reset()`` on every module using
whatever attribute values are set AT THAT MOMENT -- if it already ran
(which ``SimulationService.build()`` always used to do, Phase 0 through
Phase 2), a dispersion applied afterward would silently have no effect,
since Reset() already latched in the un-dispersed nominal values. So the
creation function here calls ``service.build(initialize=False)`` and the
execution function finishes the job AFTER the Controller has applied every
dispersion: ``SimulationService.initialize()`` (the same start-up as a
plain run), then the scenario's Mission Sequence (``MissionEngine``) when
it has one, else the set duration. Each run therefore flies what
``spacemissionstudio run`` flies.

A ``dry_mass_kg`` dispersion writes directly to ``hub.mHub`` (see
``_QUANTITY_PATHS`` below), which survives ``Reset()`` fine (no module's
``Reset()`` touches ``hub.mHub``) -- but a real bug, found by audit and
fixed in ``engine.orbit_maintenance``, used to silently UNDO it on the
first tick for any spacecraft with ``station_keeping``/``constant_thrust``
configured: those controllers used to recompute ``hub.mHub`` from their
own construction-time-captured, undispersed ``dry_mass_kg`` every tick,
discarding whatever this dispersion had just set. See
``engine.orbit_maintenance``'s "Shared mass bookkeeping" docstring note --
those controllers now read ``hub.mHub`` back and only subtract what they
themselves burn, so a dispersion applied here is preserved correctly.

A second, DIFFERENT ``dry_mass_kg`` bug (also found by audit, also fixed):
Basilisk's dispersion classes write their generated value ABSOLUTELY to
the target path, with no way to add anything on top -- but
``schema.scenario.SpacecraftConfig.dry_mass_kg`` is documented as the
mass WITHOUT station-keeping/constant-thrust propellant, while
``hub.mHub`` (this dispersion's actual target) is ``dry_mass_kg +
propellant`` (see ``service.py``'s own ``initial_mass_kg`` computation).
Applying a plain ``UniformDispersion``/``NormalDispersion`` straight to
``hub.mHub`` under the name "dry_mass_kg" would therefore silently
disperse the TOTAL mass under that name for any spacecraft with
``station_keeping``/``constant_thrust`` configured -- bounds the user
picked to disperse just the dry mass would actually disperse dry mass +
propellant, quietly shrinking the effective dry-mass spread by exactly
the propellant amount. Fixed with
:class:`_DryMassPlusPropellantUniformDispersion`/
:class:`_DryMassPlusPropellantNormalDispersion`, which add that
spacecraft's configured propellant back on top of the generated
dry-mass value before it's written to ``hub.mHub``.

Dispersed quantities
--------------------
Each ``schema.scenario.DISPERSION_QUANTITIES`` entry uses one of
Basilisk's own ``Dispersions`` classes, unmodified:

* ``dry_mass_kg``: ``UniformDispersion``/``NormalDispersion`` on
  ``hub.mHub``, plus the propellant (below).
* ``attitude_sigma_bn``: ``UniformEulerAngleMRPDispersion``.
* ``orbit_elements``: ``OrbitalElementDispersion`` on ``hub.r_CN_NInit``
  and ``hub.v_CN_NInit``. It draws every element absolutely and sets one
  with no entry to zero, so each element gets an entry: the nominal value
  (:func:`nominal_elements`, from the same state the service starts the
  run in) with the configured spread, or none.
* ``inertia_kg_m2``: ``InertiaTensorDispersion``, which adds a normal
  offset to each diagonal element and rotates the tensor by small random
  angles. Without bounds it clips each offset to [-1, 1] kg*m^2, so this
  module passes infinite bounds unless the scenario sets its own.
* ``angular_rate_bn_b``: ``NormalVectorCartDispersion``/
  ``UniformVectorCartDispersion``, which draw an absolute vector; the
  subclasses here add the nominal rate back, so the spread is a
  perturbation (deg/s in the scenario, rad/s in Basilisk).
* ``drag_coeff``/``srp_coeff``: ``UniformDispersion``/``NormalDispersion``
  on the sphere ``dragDynamicEffector``'s ``coreParams.dragCoeff`` or the
  ``radiationPressure`` effector's ``coefficientReflection``, reached
  through ``sim.get_drag_<name>()``/``sim.get_srp_<name>()`` (below).

Dispersion path resolution
---------------------------
Basilisk's dispersion path strings resolve via attribute access, integer
indexing, and zero-argument method calls ONLY -- no string-keyed lookups
(confirmed by reading ``Controller._parseAttributePath``/``_resolvePathPart``
directly: a path segment is either ``.name``, ``[int]``, or ``name()``).
Since a scenario can have several spacecraft, and there is no
string-keyed way to reach "the sc_object for spacecraft named X" from the
sim object, the creation function attaches one dynamically-named,
zero-argument accessor method per spacecraft directly onto the returned
sim object (``sim.get_spacecraft_<sanitized name>()`` -> that spacecraft's
``spacecraft.Spacecraft`` instance) -- a dispersion path like
``"get_spacecraft_sat_1().hub.mHub"`` then resolves exactly per the rules
above. This is not a Basilisk API; it is this module's own bridge, built
entirely from the documented, verified path-resolution rules.

Retained data
-------------
V1 scope: every run retains each spacecraft's position/velocity
(``r_BN_N``/``v_BN_N`` off its ``scStateOutMsg`` recorder, via
``sim.msgRecList`` + one ``RetentionPolicy.addMessageLog`` call per
spacecraft -- both documented, verified mechanisms, see
``MonteCarlo/README.md``'s "Retain simulation data" section). There is no
per-run custom retention selection in the schema yet (e.g. "also retain
attitude" or "also retain a specific sensor") -- a reasonable v1 scope
given position/velocity dispersion spread is the headline Monte Carlo
question for a mission-analysis tool, extendable later without a schema
break (``MonteCarloConfig`` is a dataclass like everything else here).

Each run also retains its outcomes (Monte Carlo plan A1, decision MC-2):
the headline figures of Results › Overview for a single run
(``engine.run_summary.overview_figures``), computed by
:func:`_execute_sim` from the ``ResultSet`` the run returns and handed to
the Controller by a retention function (:func:`_retained_outcomes`,
``RetentionPolicy.addRetentionFunction``), which Basilisk puts in the run's
retained ``custom`` data, in the same ``run<N>.data`` file. A figure is
there only when the run recorded its source, as for a single run.

Running one case again
----------------------
:func:`replay_case` (Monte Carlo plan A3, decisions MC-7 and MC-17) runs one
case of a batch again as a plain run, with every series, the events and
the Overview: it builds the run as :func:`_create_sim` does, applies each
entry of the case's ``run<N>.json`` (JSON, written by the Controller
before the case ran; never the pickles, S-04) in the file's order with the
Controller's own setter, ``SimulationExecutor.applyModification``, then
starts and flies it as :func:`_execute_sim` does. The entries hold the
case's draws and the RNG seeds the Controller gave every model, so the
run is the batch's case. It is refused when the scenario's hash differs
from the batch's (``archive.provenance.json``, ``scenario_sha256``): the
same case number would then be a different case. It is also refused when
a reference data file the case uses (``SimulationService._data_files``:
the space weather, the Earth orientation files, the SPICE kernels, ...)
is not the one the case used in the batch (decision MC-19): each run keeps
the SHA-256 of its data files in the batch summary (``data_files``).

Batch seed
----------
Before each run Basilisk's worker seeds NumPy's legacy global generator
and Python's ``random`` with the run index times 10, then calls the
creation function, then draws every model's ``RNGSeed`` (``random``) and
every dispersion (NumPy), in that order (Basilisk 2.12.0,
``Controller.SimulationExecutor.__call__``). Without
``monte_carlo.seed`` nothing else happens: two batches of one scenario draw
the same values (SRelD K-24). With a seed, the creation function first
reseeds both generators (:func:`_reseed`) from the batch seed and the run
index, which it reads back from the state Basilisk's seeding just left
(Monte Carlo plan B1, decision MC-20): another seed gives other draws,
the same seed the same draws. A case run again (:func:`prepare_case`)
does not reseed: its draws and seeds come from its ``run<N>.json``.

Thread count
------------
``Controller.setThreadCount(n)`` for ``n > 1`` uses ``multiprocessing.Pool``
(confirmed by reading ``Controller.py`` directly). Python's
``multiprocessing`` needs the worker's target callables to be importable
(pickle-based "spawn"/"forkserver" start methods) or merely needs the
parent process state duplicated (fork). This module's creation/execution
functions are plain module-level functions (not closures) specifically so
they pickle cleanly either way, but the SCENARIO itself is threaded through
via ``functools.partial`` (also picklable, since :class:`Scenario` is a
plain dataclass tree of built-in types). It is exercised with
``thread_count > 1`` by this project's own tests against a real Basilisk
build; :data:`schema.scenario.MonteCarloConfig.thread_count` still defaults
to ``1``.

A worker process imports the engine again, so the folders the engine reads
reference data from (module-level settings such as
``spaceweather.DEFAULT_CACHE_DIR``, computed from the home folder at
import) would be the worker's own. :func:`run_monte_carlo` therefore keeps
them (:func:`data_folders`) and the creation function sets them in the
worker before it builds (:func:`apply_data_folders`, decision MC-19): every
case resolves its data as the process that starts the batch does.
"""

from __future__ import annotations

import dataclasses
import functools
import gc
import gzip
import json
import logging
import pickle  # noqa: S403 -- reads back only the archive this same call wrote (security analysis S-04)
import random
import re
from pathlib import Path

import math

import numpy as np

from Basilisk.utilities import orbitalMotion, simIncludeGravBody
from Basilisk.utilities.MonteCarlo.Controller import Controller, SimulationExecutor
from Basilisk.utilities.MonteCarlo.Dispersions import (
    InertiaTensorDispersion,
    NormalDispersion,
    NormalVectorCartDispersion,
    OrbitalElementDispersion,
    UniformDispersion,
    UniformEulerAngleMRPDispersion,
    UniformVectorCartDispersion,
)
from Basilisk.utilities.MonteCarlo.RetentionPolicy import RetentionPolicy

from .. import output_provenance
from ..config import models, registry
from ..schema.command import runs_sequence, script_blocks
from ..schema.scenario import DispersionConfig, MonteCarloConfig, Scenario, SimSettings, usable_thread_count
from . import monte_carlo_case, monte_carlo_results, monte_carlo_statistics
from .solar_arrays import hub_mass_offset_kg
from .service import SimulationService, _orbit_ic_to_rv

_logger = logging.getLogger(__name__)

# spacecraft.name -> attribute path suffix on that spacecraft's sc_object,
# rooted after the "get_spacecraft_<name>()." accessor -- see module
# docstring. Kept in lock-step with schema.scenario.DISPERSION_QUANTITIES.
_QUANTITY_PATHS = {
    "dry_mass_kg": "hub.mHub",
    "attitude_sigma_bn": "hub.sigma_BNInit",
    "inertia_kg_m2": "hub.IHubPntBc_B",
    "angular_rate_bn_b": "hub.omega_BN_BInit",
    # rooted after the drag/SRP effector accessor instead (_EFFECTOR_ACCESSORS)
    "drag_coeff": "coreParams.dragCoeff",
    "srp_coeff": "coefficientReflection",
}
# Effector accessor prefix for the coefficient quantities (see _create_sim).
_EFFECTOR_ACCESSORS = {"drag_coeff": "get_drag_", "srp_coeff": "get_srp_"}
# OrbitalElementDispersion's element names for each element_spread key,
# and the factor from the key's unit (km, [-], deg) to Basilisk's (m, rad).
_ELEMENT_KEYS = {
    "semi_major_axis_km": ("a", 1000.0),
    "eccentricity": ("e", 1.0),
    "inclination_deg": ("i", math.pi / 180.0),
    "raan_deg": ("Omega", math.pi / 180.0),
    "arg_periapsis_deg": ("omega", math.pi / 180.0),
    "true_anomaly_deg": ("f", math.pi / 180.0),
}


# The module-level folders the engine reads reference data from (decision
# MC-19): (module of spacemissionstudio.engine, attribute). tests/conftest.py
# and tests/golden_capture.py set the same ones.
_DATA_FOLDER_SETTINGS = (
    ("spaceweather", "DEFAULT_CACHE_DIR"),
    ("earth_orientation", "DEFAULT_DIR"),
    ("earth_orientation", "SYSTEM_DIR"),
    ("small_bodies", "DEFAULT_DIR"),
    ("small_bodies", "SYSTEM_DIR"),
    ("gaseous_attenuation", "DEFAULT_DIR"),
    ("gaseous_attenuation", "SYSTEM_DIR"),
)


def _data_folder_modules() -> dict:
    from . import earth_orientation, gaseous_attenuation, small_bodies, spaceweather

    return {"spaceweather": spaceweather, "earth_orientation": earth_orientation, "small_bodies": small_bodies,
            "gaseous_attenuation": gaseous_attenuation}


def data_folders() -> dict[str, str]:
    """The folders this process reads reference data from, as
    ``{"<module>.<attribute>": path}`` (:data:`_DATA_FOLDER_SETTINGS`): plain
    text, so it pickles with the creation function into a worker process,
    where :func:`apply_data_folders` sets them again (decision MC-19)."""
    modules = _data_folder_modules()
    return {f"{module}.{name}": str(getattr(modules[module], name)) for module, name in _DATA_FOLDER_SETTINGS}


def apply_data_folders(folders: dict[str, str] | None) -> None:
    """Set the folders of :func:`data_folders` in this process, so a worker
    resolves reference data (space weather, Earth orientation, small-body
    kernels, ITU-R P.676-13) as the process that started the batch. None
    changes nothing. In that process itself the values are already the same."""
    if not folders:
        return
    modules = _data_folder_modules()
    for module, name in _DATA_FOLDER_SETTINGS:
        value = folders.get(f"{module}.{name}")
        if value is not None:
            setattr(modules[module], name, Path(value))


class MonteCarloError(Exception):
    """Raised for anything that prevents building or running the Monte
    Carlo batch -- always a specific, actionable message.
    """


def _accessor_name(spacecraft_name: str) -> str:
    """A valid, unique-enough Python identifier for
    ``sim.get_spacecraft_<...>()`` -- see module docstring. Uniqueness
    relies on ``schema.scenario.Scenario.validate()`` already requiring
    spacecraft names to be unique; two names that only differ by
    non-identifier characters (e.g. ``"sat 1"`` and ``"sat-1"``) would
    collide here, which is a real but narrow edge case worth knowing about
    rather than silently mishandling -- callers with such names should
    rename them.
    """
    safe = re.sub(r"\W+", "_", spacecraft_name)
    if not safe or safe[0].isdigit():
        safe = f"sc_{safe}"
    return f"get_spacecraft_{safe}"


def _propellant_offset_kg(sc_config) -> float:
    """How much MORE than ``dry_mass_kg`` ``engine.service.build()`` itself
    puts in ``hub.mHub`` for this spacecraft at t=0 -- the shared
    ``engine.solar_arrays.hub_mass_offset_kg`` both use: the station-keeping,
    GEO station-keeping and constant-thrust propellant, less any flexible
    arrays (their own state effectors). It used to leave out the GEO
    station-keeping propellant that service.py adds."""
    return hub_mass_offset_kg(sc_config)


class _DryMassPlusPropellantUniformDispersion(UniformDispersion):
    """A ``dry_mass_kg`` dispersion writes its generated value ABSOLUTELY
    to ``hub.mHub`` (Basilisk's dispersion framework has no notion of
    "add this on top of whatever's already there" -- see
    ``Controller.applyModification``/``setNestedAttr``). But
    ``hub.mHub`` is not the dry mass for a spacecraft with
    ``station_keeping``/``constant_thrust`` configured -- it's
    ``dry_mass_kg + propellant`` (``service.py``'s own
    ``initial_mass_kg``). Without this adjustment, a
    ``dry_mass_kg`` dispersion on such a spacecraft would silently
    disperse the TOTAL mass under that name instead: bounds the user
    picked to disperse just the dry mass would actually disperse dry
    mass + propellant, quietly shrinking the effective dry-mass spread
    by exactly the propellant amount on every run. ``generate()``'s
    ``self.magnitude``/percent-of-bounds bookkeeping (from the base
    class) still reflects the DRY-mass draw, since only the final
    returned value gets the offset added.
    """

    def __init__(self, varName, bounds, propellant_offset_kg: float):
        super().__init__(varName, bounds=bounds)
        self._propellant_offset_kg = propellant_offset_kg

    def generate(self, sim):
        return super().generate(sim) + self._propellant_offset_kg


class _DryMassPlusPropellantNormalDispersion(NormalDispersion):
    """Same adjustment as :class:`_DryMassPlusPropellantUniformDispersion`,
    for ``kind="normal"`` dispersions."""

    def __init__(self, varName, mean, stdDeviation, bounds, propellant_offset_kg: float):
        super().__init__(varName, mean=mean, stdDeviation=stdDeviation, bounds=bounds)
        self._propellant_offset_kg = propellant_offset_kg

    def generate(self, sim):
        return super().generate(sim) + self._propellant_offset_kg


class _AddedToNominalNormalRate(NormalVectorCartDispersion):
    """``NormalVectorCartDispersion`` draws an absolute vector; the initial
    body rate is dispersed around its nominal value instead."""

    def __init__(self, varName, stdDeviation, nominal):
        super().__init__(varName, mean=0.0, stdDeviation=stdDeviation)
        self._nominal = np.asarray(nominal, dtype=float)

    def generate(self, sim=None):
        return list(self._nominal + np.asarray(super().generate(sim), dtype=float))


class _AddedToNominalUniformRate(UniformVectorCartDispersion):
    """Same as :class:`_AddedToNominalNormalRate`, uniform per axis."""

    def __init__(self, varName, bounds, nominal):
        super().__init__(varName, bounds=bounds)
        self._nominal = np.asarray(nominal, dtype=float)

    def generate(self, sim=None):
        return list(self._nominal + np.asarray(super().generate(sim), dtype=float))


def _central_body_mu(scenario: Scenario) -> float:
    """[m^3/s^2] the central body's mu, from the same gravity factory the
    service builds the run with."""
    body = scenario.gravity.central_body
    return simIncludeGravBody.gravBodyFactory().createBodies([body])[body].mu


def nominal_elements(scenario: Scenario, sc_config):
    """The spacecraft's initial orbit as Basilisk ``ClassicElements`` in the
    simulation frame, from the same position and velocity the service
    gives the run (so any orbit type, frame or anomaly works)."""
    mu = _central_body_mu(scenario)
    r_n, v_n = _orbit_ic_to_rv(mu, sc_config.orbit, scenario.epoch_utc)
    return orbitalMotion.rv2elem(mu, np.asarray(r_n, dtype=float), np.asarray(v_n, dtype=float))


def _orbit_dispersion(dispersion: DispersionConfig, scenario: Scenario, sc_config, accessor: str):
    """``OrbitalElementDispersion`` around the nominal elements: each one is
    drawn from N(nominal, spread) or U(nominal - spread, nominal + spread);
    elements with no spread keep their nominal value (the Basilisk class
    would otherwise set them to zero)."""
    oe = nominal_elements(scenario, sc_config)
    spread = dispersion.element_spread or {}
    table = {"mu": _central_body_mu(scenario)}
    for key, (element, factor) in _ELEMENT_KEYS.items():
        nominal = float(getattr(oe, element))
        width = float(spread.get(key, 0.0)) * factor
        if dispersion.kind == "normal":
            table[element] = ["normal", nominal, width]
        else:
            table[element] = ["uniform", nominal - width, nominal + width]
    return OrbitalElementDispersion(f"{accessor}().hub.r_CN_NInit", f"{accessor}().hub.v_CN_NInit", table)


def _build_dispersion(dispersion: DispersionConfig, scenario: Scenario):
    accessor = _accessor_name(dispersion.spacecraft)
    sc_config = next((sc for sc in scenario.spacecraft if sc.name == dispersion.spacecraft), None)
    if dispersion.quantity in _EFFECTOR_ACCESSORS:
        effector_accessor = accessor.replace("get_spacecraft_", _EFFECTOR_ACCESSORS[dispersion.quantity], 1)
        path = f"{effector_accessor}().{_QUANTITY_PATHS[dispersion.quantity]}"
        if dispersion.kind == "uniform":
            return UniformDispersion(path, bounds=dispersion.bounds)
        return NormalDispersion(path, mean=dispersion.mean, stdDeviation=dispersion.std_deviation,
                                bounds=dispersion.bounds)
    if dispersion.quantity in ("orbit_elements", "angular_rate_bn_b") and sc_config is None:
        raise MonteCarloError(
            f"dispersion.spacecraft {dispersion.spacecraft!r} is not one of this scenario's spacecraft")
    if dispersion.quantity == "orbit_elements":
        return _orbit_dispersion(dispersion, scenario, sc_config, accessor)
    path = f"{accessor}().{_QUANTITY_PATHS[dispersion.quantity]}"
    if dispersion.quantity == "inertia_kg_m2":
        bounds = dispersion.bounds if dispersion.bounds is not None else [-math.inf, math.inf]
        return InertiaTensorDispersion(path, stdDiag=dispersion.std_deviation, boundsDiag=bounds,
                                       stdAngle=math.radians(dispersion.angle_std_deg or 0.0))
    if dispersion.quantity == "angular_rate_bn_b":
        nominal = sc_config.omega_bn_b_init_rad_s  # [rad/s]
        if dispersion.kind == "normal":
            return _AddedToNominalNormalRate(path, math.radians(dispersion.std_deviation), nominal)
        return _AddedToNominalUniformRate(path, [math.radians(b) for b in dispersion.bounds], nominal)

    if dispersion.quantity == "dry_mass_kg":
        # scenario.validate() (the caller's responsibility -- see
        # run_monte_carlo()'s docstring) already requires
        # dispersion.spacecraft to name a real spacecraft in this
        # scenario, so this lookup cannot fail in practice; the
        # MonteCarloError below is defensive, matching this module's own
        # "always a specific, actionable message" discipline rather than
        # a bare StopIteration/IndexError if that contract is ever violated.
        if sc_config is None:
            raise MonteCarloError(
                f"dispersion.spacecraft {dispersion.spacecraft!r} is not one of this scenario's spacecraft"
            )
        propellant_offset_kg = _propellant_offset_kg(sc_config)
        if dispersion.kind == "uniform":
            return _DryMassPlusPropellantUniformDispersion(
                path, bounds=dispersion.bounds, propellant_offset_kg=propellant_offset_kg)
        if dispersion.kind == "normal":
            return _DryMassPlusPropellantNormalDispersion(
                path, mean=dispersion.mean, stdDeviation=dispersion.std_deviation, bounds=dispersion.bounds,
                propellant_offset_kg=propellant_offset_kg)
    if dispersion.quantity == "attitude_sigma_bn" and dispersion.kind == "uniform_euler_mrp":
        return UniformEulerAngleMRPDispersion(path, bounds=dispersion.bounds)

    # unreachable if DispersionConfig.validate() passed (schema.scenario.DISPERSION_KINDS_BY_QUANTITY
    # is the single source of truth for which (quantity, kind) pairings exist)
    raise MonteCarloError(
        f"no engine.monte_carlo builder for dispersion kind {dispersion.kind!r} on quantity "
        f"{dispersion.quantity!r} (spacecraft {dispersion.spacecraft!r})"
    )


# NumPy's legacy MT19937 state right after ``numpy.random.seed(<int>)``:
# the integer is the state's first key and every key is unused.
_MT19937_KEYS = 624


def basilisk_run_index() -> int:
    """The index of the run Basilisk's worker has just seeded the global
    generators for: it seeds NumPy's legacy generator with the index times
    10 just before it calls the creation function (Basilisk 2.12.0,
    ``SimulationExecutor.__call__``). The index is read back from that
    state, whose first key is the seed while no number has been drawn.
    Raises :class:`MonteCarloError` when the state is not freshly seeded
    so (another Basilisk order): a seeded batch must not draw from a state
    it cannot name."""
    name, keys, position = np.random.get_state()[:3]
    if name != "MT19937" or len(keys) != _MT19937_KEYS or position != _MT19937_KEYS or int(keys[0]) % 10:
        raise MonteCarloError("monte_carlo.seed: the run's generators were not seeded by Basilisk's Controller just "
                              "before the run was built, so the run index is not known; this Basilisk version "
                              "seeds its runs in another way (Monte Carlo plan risk R1)")
    return int(keys[0]) // 10


def _seed_words(seed: int, index: int) -> np.ndarray:
    """Four 32-bit words for run ``index`` of a batch with ``seed``: NumPy's
    ``SeedSequence`` with the batch seed as its entropy and the run index
    as its spawn key, so each run's stream is its own and independent of
    the others (NumPy's way to derive parallel streams)."""
    return np.random.SeedSequence(entropy=int(seed), spawn_key=(int(index),)).generate_state(4)


def _reseed(seed: int) -> int:
    """Reseed NumPy's legacy global generator and Python's ``random`` for
    the run Basilisk is building (:func:`basilisk_run_index`) from the
    batch ``seed`` and that run's index (:func:`_seed_words`), before the
    Controller draws the run's RNG seeds and dispersions (decision MC-20).
    Returns the run index."""
    index = basilisk_run_index()
    words = _seed_words(seed, index)
    np.random.seed(words)
    random.seed(int.from_bytes(words.astype("<u4").tobytes(), "little"))
    return index


def _create_sim(scenario: Scenario, folders: dict[str, str] | None = None, seed: int | None = None):
    """Monte Carlo creation function (see module docstring for why
    ``initialize=False``). Module-level + ``functools.partial``-bound
    (never a closure) so it stays picklable for ``thread_count > 1``.
    ``folders`` (:func:`data_folders` of the process that starts the batch)
    are set first, so a worker process reads the same reference data.
    With the batch ``seed`` (``monte_carlo.seed``), the global generators
    are reseeded first (:func:`_reseed`); a case run again passes none.
    """
    if seed is not None:
        _reseed(seed)
    apply_data_folders(folders)
    service = SimulationService(scenario)
    service.build(initialize=False)
    sim = service.scSim

    for name, handle in service.spacecraft_handles.items():
        sc_object = handle.sc_object
        accessor = _accessor_name(name)
        setattr(sim, accessor, (lambda sc_object=sc_object: sc_object))
        # The coefficient dispersions write to the drag/SRP effector itself.
        for quantity, prefix in _EFFECTOR_ACCESSORS.items():
            effector = handle.drag_effector if quantity == "drag_coeff" else handle.srp_effector
            if effector is not None:
                setattr(sim, accessor.replace("get_spacecraft_", prefix, 1), (lambda effector=effector: effector))

    sim.msgRecList = {f"{name}.scState": handle.recorder for name, handle in service.spacecraft_handles.items()}
    sim._spacemissionstudio_service = service  # stashed for _execute_sim to finish init/configure/execute
    return sim


def _execute_sim(sim, allow_scripts: bool = False) -> None:
    """Monte Carlo execution function: finishes what ``_create_sim`` left
    undone, AFTER the Controller has applied every dispersion to ``sim``
    (see module docstring) -- the same start-up as a plain run
    (``SimulationService.initialize``: momentum dumping's primed reset),
    then the Mission Sequence when the scenario has one, as ``run`` does,
    else the set duration. Module-level (with ``allow_scripts`` bound by
    ``functools.partial``) so it pickles for ``thread_count > 1``.
    """
    service = sim._spacemissionstudio_service
    # As built, before the flight: what prepare_case compares when the case runs again (MC-19).
    sim._spacemissionstudio_data_files = data_file_hashes(getattr(service, "_data_files", {}))
    service.initialize()
    result, _summary = _fly(service, allow_scripts)
    sim._spacemissionstudio_outcomes = _outcomes_or_none(result)


def _fly(service, allow_scripts: bool = False) -> tuple:
    """(the ``ResultSet``, the Mission Sequence's ``CommandSummary`` or None)
    of an initialized service: the scenario's Mission Sequence when it has
    one, as ``run`` does, else the set duration."""
    from .mission_engine import MissionEngine

    if runs_sequence(service.scenario.mission_sequence):
        returned = MissionEngine(service.scenario, service=service, allow_scripts=allow_scripts).run()
        return returned if isinstance(returned, tuple) else (returned, None)
    return service.run(), None


# The keys of the outcomes a run retains in its custom data (RetentionPolicy).
OUTCOMES_KEY = "spacemissionstudio_outcomes"
OUTCOME_UNITS_KEY = "spacemissionstudio_outcome_units"
# ... and of its reference data files (decision MC-19).
DATA_FILES_KEY = "spacemissionstudio_data_files"


def data_file_hashes(data_files: dict) -> dict[str, dict[str, str]]:
    """The path and SHA-256 of each reference data file of a run
    (``SimulationService._data_files``, ``dependencies.file_record``), by
    kind; a file that was missing or could not be read has no SHA-256."""
    hashes: dict[str, dict[str, str]] = {}
    for kind, record in data_files.items():
        if not isinstance(record, dict):
            continue
        entry = {"path": str(record.get("path", ""))}
        if isinstance(record.get("sha256"), str):
            entry["sha256"] = record["sha256"]
        hashes[str(kind)] = entry
    return hashes


def run_outcomes(result) -> tuple[dict[str, float], dict[str, str]]:
    """A run's outcomes and their units (decision MC-2): the figures of
    ``engine.run_summary.overview_figures`` by key, ``"<spacecraft>.<outcome>"``
    (``schema.scenario.MONTE_CARLO_OUTCOMES``) or ``"run_length"``. A run
    whose altitude does not vary has one figure, the altitude; it is kept
    as both the lowest and the highest altitude, so every run has the same
    keys."""
    from . import run_summary

    values: dict[str, float] = {}
    units: dict[str, str] = {}
    for figure in run_summary.overview_figures(result):
        owner, _, name = figure.key.rpartition(".")
        keys = [f"{owner}.lowest_altitude", f"{owner}.highest_altitude"] if name == "altitude" else [figure.key]
        for key in keys:
            values[key] = float(figure.value)
            units[key] = figure.unit
    return values, units


def _outcomes_or_none(result) -> tuple[dict, dict]:
    """:func:`run_outcomes` of ``result``; none (logged) when it cannot be
    read: the run itself succeeded, and a requirement then counts it "not
    evaluated" rather than losing the run."""
    if result is None:
        return {}, {}
    try:
        return run_outcomes(result)
    except Exception:  # noqa: BLE001 -- a figure that cannot be read must not fail a run that succeeded
        _logger.exception("Monte Carlo run finished, but its outcomes could not be read")
        return {}, {}


def _retained_outcomes(sim) -> dict:
    """The retention function (``RetentionPolicy.addRetentionFunction``):
    the outcomes :func:`_execute_sim` stored on ``sim``, and the run's data
    files (:func:`data_file_hashes`, decision MC-19). Module-level, so it
    pickles for ``thread_count > 1``."""
    values, units = getattr(sim, "_spacemissionstudio_outcomes", ({}, {}))
    files = getattr(sim, "_spacemissionstudio_data_files", {})
    return {OUTCOMES_KEY: dict(values), OUTCOME_UNITS_KEY: dict(units), DATA_FILES_KEY: dict(files)}


def _default_retention_policy(scenario: Scenario) -> RetentionPolicy:
    policy = RetentionPolicy()
    for sc in scenario.spacecraft:
        policy.addMessageLog(f"{sc.name}.scState", ["r_BN_N", "v_BN_N"])
    policy.addRetentionFunction(_retained_outcomes)
    return policy


def _check_script_consent(scenario: Scenario, allow_scripts: bool) -> None:
    """Script blocks run only with the user's consent (SRS-S-03)."""
    blocks = script_blocks(scenario.mission_sequence)
    if blocks and not allow_scripts:
        raise MonteCarloError(
            f"{', '.join(path for path, _ in blocks)}: script_block runs unrestricted Python from the scenario "
            "file, so it runs only with your explicit consent -- check the code, then use --allow-scripts (CLI) "
            "or confirm when asked (GUI)")


def run_monte_carlo(scenario: Scenario, mc_config: MonteCarloConfig, archive_dir: str | Path,
                    allow_scripts: bool = False, overwrite: bool = False,
                    scenario_file: dict | None = None) -> list[int]:
    """Runs ``mc_config.num_runs`` dispersed executions of ``scenario`` via
    ``Basilisk.utilities.MonteCarlo.Controller``, archiving retained
    position/velocity data (JSON per-run parameter files plus the
    Controller's own pickled archive) to ``archive_dir``. Returns the list
    of FAILED run indices, exactly as ``Controller.executeSimulations()``
    does (empty list == every run succeeded).

    Afterwards it reads those run files back (:func:`collect_batch`) and
    writes the pickle-free summary of ``engine.monte_carlo_results``
    (``batch_results.npz``/``.json``) next to them, which the GUI's Monte
    Carlo tab and ``spacemissionstudio monte-carlo`` show. A failure there
    is logged and does not fail the batch. Last, it writes the batch's
    provenance, ``archive.provenance.json`` (:func:`archive_record`), with
    ``scenario_file``: the record of the file the scenario was loaded from
    (``output_provenance.scenario_file_record``), when it is that file
    unchanged.

    ``scenario`` must already be valid (``scenario.validate()`` -- this
    function does not re-validate it, since :func:`SimulationService.build`
    inside each run's creation function does, and a validation failure
    there surfaces as a per-run failure rather than an upfront one).

    Each run resolves its reference data from the folders of this process
    (:func:`data_folders`, also in a worker process; decision MC-19) and
    keeps the SHA-256 of its data files in the summary (``data_files``).

    Each run executes the scenario's Mission Sequence when it has one, as
    ``spacemissionstudio run`` does; its script blocks need
    ``allow_scripts`` (the user's consent, SRS-S-03). ``archive_dir`` must
    be empty or hold an earlier batch, which ``overwrite`` replaces: a
    reused folder must never show the previous batch as this one.
    """
    if not mc_config.enabled:
        raise MonteCarloError("monte_carlo.enabled is False -- set it True before calling run_monte_carlo()")
    if scenario.sim_settings.duration_days > SimSettings._MAX_SINGLE_RUN_DAYS:
        raise MonteCarloError(f"Monte Carlo runs at most {SimSettings._MAX_SINGLE_RUN_DAYS:g} days per run "
                              "(sim_settings.duration_days) -- shorten the run")

    _check_script_consent(scenario, allow_scripts)

    archive_dir = Path(archive_dir)
    if archive_dir.exists() and not archive_dir.is_dir():
        raise MonteCarloError(f"could not create Monte Carlo archive directory {archive_dir}: it is a file")
    state = monte_carlo_results.folder_state(archive_dir)
    if state == "other":
        raise MonteCarloError(f"{archive_dir} is not empty and holds no earlier Monte Carlo batch: choose an "
                              "empty folder")
    if state == "batch":
        if not overwrite:
            raise MonteCarloError(f"{archive_dir} holds an earlier Monte Carlo batch; choose another folder or "
                                  "replace it (--overwrite)")
        try:
            for path in monte_carlo_results.batch_files(archive_dir):
                path.unlink()
        except OSError as exc:
            raise MonteCarloError(f"could not remove the earlier batch in {archive_dir}: {exc}") from exc
    try:
        archive_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        # e.g. archive_dir already exists as a plain file, or is
        # unwritable -- without this, the raw OSError would escape
        # run_monte_carlo() as something other than MonteCarloError, so
        # cli.py's cmd_monte_carlo() (which only catches MonteCarloError)
        # would let it surface as an uncaught traceback instead of this
        # module's usual "ERROR: ..." + specific exit code convention.
        raise MonteCarloError(f"could not create Monte Carlo archive directory {archive_dir}: {exc}") from exc

    controller = Controller()
    controller.setSimulationFunction(functools.partial(_create_sim, scenario, data_folders(), mc_config.seed))
    controller.setExecutionFunction(functools.partial(_execute_sim, allow_scripts=allow_scripts))
    controller.setExecutionCount(mc_config.num_runs)
    controller.setShouldDisperseSeeds(True)
    threads = usable_thread_count(mc_config.thread_count)
    if threads < mc_config.thread_count:
        _logger.warning("Monte Carlo: %d processes asked for, %d used (one per CPU)", mc_config.thread_count, threads)
    controller.setThreadCount(threads)
    controller.setVerbose(mc_config.verbose)
    controller.setArchiveDir(str(archive_dir))

    for dispersion in mc_config.dispersions:
        controller.addDispersion(_build_dispersion(dispersion, scenario))

    controller.addRetentionPolicy(_default_retention_policy(scenario))

    # The Controller forks its data writer and worker processes from this
    # one. A Basilisk simulation left uncollected here (an earlier run's,
    # in a reference cycle) would be destroyed by the garbage collector in
    # a child, where SimModel's destructor waits forever on thread state
    # copied from this process: the batch hangs. Collect it here first.
    gc.collect()
    try:
        failures = controller.executeSimulations()
    except Exception as exc:  # noqa: BLE001 -- report ANY batch-level failure with a specific message
        raise MonteCarloError(f"Monte Carlo batch execution failed: {exc}") from exc
    try:
        batch = collect_batch(scenario, archive_dir, mc_config.num_runs, failures, mc_config.seed)
        if batch.runs:
            monte_carlo_results.save(batch, archive_dir)
    except Exception:  # noqa: BLE001 -- the batch itself ran; a summary problem must not lose that
        _logger.exception("Monte Carlo batch finished, but its summary could not be written")
    try:
        output_provenance.write_sidecar(archive_dir / "archive", archive_record(scenario, scenario_file,
                                                                             mc_config.seed, mc_config))
    except OSError as exc:
        raise MonteCarloError(f"could not write the batch's provenance in {archive_dir}: {exc}") from exc
    return failures


ARCHIVE_SEEDS_NOTE = ("each run's own: Basilisk's Monte Carlo Controller draws them (setShouldDisperseSeeds) and "
                      "writes them to that run's run<N>.json")
# ... and with a batch seed (decision MC-20).
ARCHIVE_SEEDED_NOTE = ("each run's own: Basilisk's Monte Carlo Controller draws them (setShouldDisperseSeeds) and "
                       "writes them to that run's run<N>.json, after the batch seed (monte_carlo_seed) and the run "
                       "index reseeded the run's generators")


# Keys of the nominal run's record left out of a batch's: the versions and
# hash already at its top, and what only a run that was flown has (its
# start time, its seeds; a batch's are each run's own).
_NOT_NOMINAL = {"spacemissionstudio_version", "basilisk_version", "qualified_basilisk_version",
                "basilisk_qualified", "dependency_versions", "scenario_sha256", "scenario_file",
                "scenario_file_sha256", "scenario_file_migrations", "run_started_utc", "rng_seed", "rng_seed_note",
                "rng_seeds"}


# The settings a batch can take from somewhere other than its scenario (the command line's --runs and
# --processes, Monte Carlo plan B7): each is recorded with both values when it differs.
OVERRIDABLE_SETTINGS = ("num_runs", "thread_count")


def batch_settings(scenario: Scenario, mc_config: MonteCarloConfig) -> dict:
    """What a batch ran with (``archive.provenance.json``
    ``monte_carlo_settings``, decision MC-33): the runs and processes asked
    for, the processes used (one per CPU at most), the batch seed, the
    dispersions as the scenario file writes them, and ``overrides``: each
    of :data:`OVERRIDABLE_SETTINGS` whose value is not the scenario's, as
    ``{"scenario": ..., "batch": ...}`` (empty when none is)."""
    return {"num_runs": mc_config.num_runs, "thread_count": mc_config.thread_count,
            "processes_used": usable_thread_count(mc_config.thread_count), "seed": mc_config.seed,
            "dispersions": [dataclasses.asdict(dispersion) for dispersion in mc_config.dispersions],
            "overrides": {key: {"scenario": getattr(scenario.monte_carlo, key), "batch": getattr(mc_config, key)}
                          for key in OVERRIDABLE_SETTINGS
                          if getattr(scenario.monte_carlo, key) != getattr(mc_config, key)}}


def archive_record(scenario: Scenario, scenario_file: dict | None = None, seed: int | None = None,
                   mc_config: MonteCarloConfig | None = None) -> dict:
    """The provenance of a batch of ``scenario`` (transparency audit,
    Phase 2g): the tool and Basilisk versions, the scenario's hash (its
    dispersions included), the file it came from (``scenario_file``: its
    name, the SHA-256 of its bytes and what loading it changed, else empty)
    and the time; and as
    ``nominal_run`` what every run shares, from the record a run of it
    would carry (:meth:`.SimulationService.nominal_provenance`: integrator,
    tolerances, task rates, central body, frames, time system, data files).
    The seeds are each run's own: see :data:`ARCHIVE_SEEDS_NOTE`; the batch
    seed is ``monte_carlo_seed`` (None: Basilisk's own seeding, decision
    MC-20). As ``monte_carlo_settings``, what the batch ran with
    (:func:`batch_settings` of ``mc_config``, by default the scenario's own
    settings). As
    ``models``, the models in effect for the batch's results
    (``config.models``: the spread's statistic).

    Built after the batch, never before it: the Controller forks its
    workers from this process, where a Basilisk simulation left over can
    hang them (see :func:`run_monte_carlo`). A nominal build that fails is
    recorded as its error."""
    record = dict(output_provenance.scenario_record(scenario), scenario_file="", scenario_file_sha256="",
                  scenario_file_migrations=[])
    record.update(scenario_file or {})
    try:
        nominal = SimulationService(scenario).nominal_provenance().to_dict()
    except Exception as exc:  # noqa: BLE001 -- the batch ran; its record says what could not be built
        _logger.exception("Monte Carlo batch finished, but its nominal run could not be built for the provenance")
        nominal = {"error": f"{type(exc).__name__}: {exc}"}
    record["nominal_run"] = {key: value for key, value in nominal.items() if key not in _NOT_NOMINAL}
    record["rng_seeds"] = ARCHIVE_SEEDS_NOTE if seed is None else ARCHIVE_SEEDED_NOTE
    record["monte_carlo_seed"] = seed
    record["monte_carlo_settings"] = batch_settings(scenario, scenario.monte_carlo if mc_config is None else mc_config)
    record["models"] = models.records(scenario, "monte_carlo")
    return record


# Readable labels for the drawn values of each dispersed quantity, by the
# last part of the Controller's parameter name (see _QUANTITY_PATHS).
_ELEMENT_LABELS = {
    "semi_major_axis_km": "semi-major axis [km]",
    "eccentricity": "eccentricity [-]",
    "inclination_deg": "inclination [deg]",
    "raan_deg": "RAAN [deg]",
    "arg_periapsis_deg": "argument of periapsis [deg]",
    "true_anomaly_deg": "true anomaly [deg]",
}


def _elements_deg(oe) -> dict[str, float]:
    """Basilisk ``ClassicElements`` in the element_spread keys' units."""
    return {"semi_major_axis_km": oe.a / 1e3, "eccentricity": oe.e,
            "inclination_deg": math.degrees(oe.i), "raan_deg": math.degrees(oe.Omega),
            "arg_periapsis_deg": math.degrees(oe.omega), "true_anomaly_deg": math.degrees(oe.f)}


def _drawn_values(params: dict[str, str], scenario: Scenario, mu: float) -> dict[str, float]:
    """One run's drawn values (``runN.json``: Controller parameter name ->
    value as text), keyed by readable labels."""
    by_accessor = {_accessor_name(sc.name): sc for sc in scenario.spacecraft}
    spread_keys = {d.spacecraft: list(d.element_spread or {}) for d in scenario.monte_carlo.dispersions
                   if d.quantity == "orbit_elements"}
    drawn: dict[str, float] = {}
    for key, text in params.items():
        accessor, _, path = key.partition("().")
        for prefix in _EFFECTOR_ACCESSORS.values():
            if accessor.startswith(prefix):
                accessor = accessor.replace(prefix, "get_spacecraft_", 1)
        sc = by_accessor.get(accessor)
        if sc is None:
            continue  # e.g. the RNG seeds
        value = np.asarray(json.loads(text), dtype=float)
        if path == "hub.mHub":
            drawn[f"{sc.name} dry mass [kg]"] = float(value) - _propellant_offset_kg(sc)
        elif path == "coreParams.dragCoeff":
            drawn[f"{sc.name} drag coefficient [-]"] = float(value)
        elif path == "coefficientReflection":
            drawn[f"{sc.name} SRP coefficient [-]"] = float(value)
        elif path == "hub.IHubPntBc_B":
            for axis, inertia in zip(("xx", "yy", "zz"), np.diag(value.reshape(3, 3))):
                drawn[f"{sc.name} I{axis} [kg m^2]"] = float(inertia)
        elif path == "hub.omega_BN_BInit":
            for axis, rate in zip("xyz", value.ravel()):
                drawn[f"{sc.name} rate {axis} [deg/s]"] = math.degrees(float(rate))
        elif path == "hub.sigma_BNInit":
            for index, component in enumerate(value.ravel(), start=1):
                drawn[f"{sc.name} attitude MRP {index} [-]"] = float(component)
        elif path == "hub.r_CN_NInit":
            velocity = params.get(key.replace("r_CN_NInit", "v_CN_NInit"))
            if velocity is None:
                continue
            elements = _elements_deg(orbitalMotion.rv2elem(
                mu, value.ravel(), np.asarray(json.loads(velocity), dtype=float).ravel()))
            nominal = _elements_deg(nominal_elements(scenario, sc))
            for element in spread_keys.get(sc.name) or list(elements):
                drawn_value = elements[element]
                if element.endswith("_deg"):  # within 180 deg of the nominal, so 0 +/- 0.1 is not 359.9
                    drawn_value = nominal[element] + (drawn_value - nominal[element] + 180.0) % 360.0 - 180.0
                drawn[f"{sc.name} {_ELEMENT_LABELS[element]}"] = float(drawn_value)
    return drawn


def _run_params(archive_dir: Path, run: int) -> dict:
    """A run's ``run<N>.json`` (JSON, written by the Controller before the
    run starts: its draws and seeds), or {} when it has none or cannot be read."""
    path = archive_dir / f"run{run}.json"
    try:
        params = json.loads(path.read_text()) if path.is_file() else {}
    except (OSError, ValueError):
        return {}
    return params if isinstance(params, dict) else {}


def collect_batch(scenario: Scenario, archive_dir: str | Path, num_runs: int,
                  failures: list[int], seed: int | None = None) -> monte_carlo_results.MonteCarloBatch:
    """Every successful run's retained position and velocity, on a shared,
    strided time grid, the values it drew and its outcomes (:func:`run_outcomes`)
    -- read back from the files :func:`run_monte_carlo` has just had the
    Controller write into ``archive_dir``. Only ever called on that call's own
    output: the run files are pickles (security analysis S-04). Each such run
    also keeps its data files (:func:`data_file_hashes`, decision MC-19).

    A run that did not finish is failed; what it drew is kept from its
    ``run<N>.json`` (JSON, never a pickle) as ``failed_drawn`` (Monte Carlo
    plan A4). The batch keeps the scenario's requirements (A2), the models
    of its statistics and its ``seed`` (B1)."""
    archive_dir = Path(archive_dir)
    mu = _central_body_mu(scenario)
    names = [sc.name for sc in scenario.spacecraft]
    runs, raw, drawn, outcomes, units, data_files = [], [], [], [], {}, []
    for run in range(num_runs):
        data_path = archive_dir / f"run{run}.data"
        if run in failures or not data_path.is_file():
            continue
        try:
            with gzip.open(data_path) as handle:
                retained = pickle.load(handle)  # noqa: S301 -- written by this call (see docstring)
            messages = retained["messages"]
        except (OSError, EOFError, pickle.UnpicklingError, KeyError):
            continue  # cut short by a cancelled batch (audit G3): counted as not finished
        raw.append({name: (np.asarray(messages[f"{name}.scState.r_BN_N"], dtype=float),
                           np.asarray(messages[f"{name}.scState.v_BN_N"], dtype=float)) for name in names})
        drawn.append(_drawn_values(_run_params(archive_dir, run), scenario, mu))
        custom = retained.get("custom") or {}
        outcomes.append({str(key): float(value) for key, value in (custom.get(OUTCOMES_KEY) or {}).items()})
        units.update({str(key): str(unit) for key, unit in (custom.get(OUTCOME_UNITS_KEY) or {}).items()})
        data_files.append(data_file_hashes(custom.get(DATA_FILES_KEY) or {}))
        runs.append(run)
    failed = sorted(set(failures) | {run for run in range(num_runs) if run not in runs})
    failed_drawn = {run: _drawn_values(_run_params(archive_dir, run), scenario, mu) for run in failed}
    statistic = registry.value(monte_carlo_results.SPREAD_CHOICE, scenario)
    extra = {"outcomes": outcomes if any(outcomes) else [], "outcome_units": units, "failed_drawn": failed_drawn,
             "data_files": data_files if any(data_files) else [],
             "requirements": [dataclasses.asdict(r) for r in scenario.monte_carlo.requirements],
             "probability_bound": registry.value(monte_carlo_results.BOUND_CHOICE, scenario), "seed": seed,
             **monte_carlo_statistics.choices(scenario)}
    if not runs:
        return monte_carlo_results.MonteCarloBatch(scenario.name, scenario.gravity.central_body, np.zeros(0),
                                                   [], failed, {}, {}, [], scenario.epoch_utc, statistic, **extra)
    samples = min(rv[0].shape[0] for run_data in raw for rv in run_data.values())
    stride = monte_carlo_results.stride_for(samples)
    rows = slice(0, samples, stride)
    time_s = raw[0][names[0]][0][rows, 0] / 1e9  # [s] Basilisk records nanoseconds
    positions = {name: np.stack([run_data[name][0][rows, 1:4] for run_data in raw]) for name in names}
    velocities = {name: np.stack([run_data[name][1][rows, 1:4] for run_data in raw]) for name in names}
    return monte_carlo_results.MonteCarloBatch(scenario.name, scenario.gravity.central_body, time_s, runs,
                                               failed, positions, velocities, drawn, scenario.epoch_utc, statistic,
                                               **extra)


# -- One case again (Monte Carlo plan A3) -------------------------------------


class MonteCarloCaseRefused(MonteCarloError):
    """A case is not run again: the scenario changed since the batch, the
    folder has no record of the batch's scenario, the batch has no such
    case, or a reference data file is not the one the case used in the
    batch. The message says why and what to do."""


# The record of the batch a case run comes from (RunProvenance.rng_seed_note).
CASE_SEEDS_NOTE = ("a Monte Carlo case run again: every model's RNGSeed is the case's own, from the batch's "
                   "run<N>.json (monte_carlo_case.rng_seeds)")


def case_parameters(scenario: Scenario, archive_dir: str | Path, case: int) -> tuple[dict, dict]:
    """(the entries of ``run<case>.json`` in the file's order, the record of the
    case for the run's provenance, ``monte_carlo_case``): the batch folder,
    the case number, the batch's scenario hash, the case's RNG seeds and,
    when the batch had one, its seed (``batch_seed``).

    Refused (:class:`MonteCarloCaseRefused`) when the scenario's SHA-256
    differs from the one the batch recorded (decision MC-17, the owner's
    answer to Q3), naming both hashes and what to do; when the batch has
    no such case; or when its file is missing or cannot be read."""
    archive_dir = Path(archive_dir)
    found = monte_carlo_case.read_case(scenario, archive_dir, case)  # the window's check too
    if isinstance(found, str):
        raise MonteCarloCaseRefused(found)
    params, batch_digest = found
    seeds = {}
    for name, value in params.items():
        if name.endswith(".RNGSeed"):
            try:
                seeds[name] = int(value)
            except (TypeError, ValueError):
                seeds[name] = str(value)
    record = {"archive_dir": str(archive_dir.resolve()), "case": case, "scenario_sha256": batch_digest,
              "rng_seeds": seeds}
    seed = monte_carlo_case.batch_seed(archive_dir)
    if seed is not None:  # written only when the batch had one (decision MC-20)
        record["batch_seed"] = seed
    return params, record


# What a changed data file of each kind is called in a refusal, and the
# usual cause (decision MC-19). A kind "<prefix>:<file>" names its file.
_DATA_FILE_KINDS = {
    "space_weather": ("the space weather", "a newer download, or another file"),
    "space_weather_forecast": ("the space-weather forecast (MSFC)", "another prediction table"),
    "earth_orientation": ("the Earth orientation file", "Earth orientation files installed, updated or removed"),
    "spice": ("the SPICE kernel", "another support-data download"),
    "gravity_field": ("the gravity field", "another support-data download"),
    "magnetic_field": ("the magnetic field model", "another support-data download"),
    "atmosphere_table": ("the atmosphere table", "another support-data download"),
    "albedo_map": ("the albedo map", "another support-data download"),
    "shape_model": ("the shape model", "another file"),
    "itu_p676_part1": ("ITU-R P.676-13 Part 1", "another file installed"),
}


def _data_file_label(kind: str) -> tuple[str, str]:
    """(what the file of ``kind`` is called, its usual cause of change)."""
    prefix, _, name = kind.partition(":")
    label, cause = _DATA_FILE_KINDS.get(prefix, (f"the data file {prefix!r}", "another file"))
    return (f"{label} {name}" if name else label), cause


def data_file_refusal(batch_files: dict, files_now: dict, archive_dir, case: int) -> str:
    """Why ``case`` cannot run again with the data files ``files_now`` (by
    kind, :func:`data_file_hashes`) when the batch's case used
    ``batch_files``, or "" when each file has the SHA-256 it had in the
    batch. A file used now and not then, or then and not now, or missing
    now, is refused as well: the case would fly with other data."""
    changes = []
    for kind in sorted(set(batch_files) | set(files_now)):
        then, now = batch_files.get(kind), files_now.get(kind)
        then_hash = (then or {}).get("sha256")
        now_hash = (now or {}).get("sha256")
        if then is not None and now is not None and then_hash == now_hash:
            continue
        label, cause = _data_file_label(kind)
        if then is None:
            changes.append(f"{label} is used now (SHA-256 {now_hash}) and was not used in the batch ({cause})")
        elif now is None:
            changes.append(f"{label} is not used now and was used in the batch (SHA-256 {then_hash}; {cause})")
        elif now_hash is None:
            changes.append(f"{label} is missing now ({now.get('path', '')}; SHA-256 {then_hash} at the batch)")
        else:
            changes.append(f"{label} changed since the batch ({cause}): SHA-256 {now_hash} now, {then_hash} at "
                           "the batch")
    if not changes:
        return ""
    return (f"Case {case} was not run again: {'; '.join(changes)}. With other reference data the case would not "
            f"be the case of the batch in {archive_dir}. To run it again, use the batch's data files (put them back, "
            "or roll back the download in Reference data), or run the batch again.")


def prepare_case(scenario: Scenario, archive_dir: str | Path, case: int):
    """(an initialized ``SimulationService`` of ``case``, the record of the
    case): the run the batch's creation function builds (:func:`_create_sim`),
    each entry of ``run<case>.json`` applied in the file's order with the
    Controller's own setter (``SimulationExecutor.applyModification``,
    Basilisk 2.12.0), then the same start-up as the batch's run
    (``SimulationService.initialize``). The caller flies it
    (:func:`replay_case`, or the GUI's run worker) and marks the result
    with :func:`mark_case`. Refused as :func:`case_parameters` says, and
    when the service, once built, does not use the data files the case used
    in the batch (:func:`data_file_refusal`, decision MC-19). A summary
    without that record (a batch made before it was kept) is not checked."""
    params, record = case_parameters(scenario, archive_dir, case)
    sim = _create_sim(scenario)
    batch_files = monte_carlo_results.case_data_files(archive_dir, case)
    if batch_files is not None:
        refusal = data_file_refusal(batch_files, data_file_hashes(sim._spacemissionstudio_service._data_files),
                                    archive_dir, case)
        if refusal:
            raise MonteCarloCaseRefused(refusal)
    for name, value in params.items():
        SimulationExecutor.applyModification(sim, name, value)
    service = sim._spacemissionstudio_service
    service.initialize()
    return service, record


def mark_case(result, record: dict):
    """``result`` with the case's record in its provenance
    (``monte_carlo_case``) and the note that its seeds are the case's."""
    if result is not None and getattr(result, "provenance", None) is not None:
        result.provenance = dataclasses.replace(result.provenance, monte_carlo_case=dict(record),
                                                rng_seed_note=CASE_SEEDS_NOTE)
    return result


def replay_case(scenario: Scenario, archive_dir: str | Path, case: int, allow_scripts: bool = False) -> tuple:
    """Run case ``case`` of the batch in ``archive_dir`` again as a plain run
    (Monte Carlo plan A3): (the ``ResultSet``, the Mission Sequence's
    ``CommandSummary`` or None). The run is the batch's case: the same
    draws, seeds, start-up and flight (:func:`prepare_case`, :func:`_fly`),
    so its outcomes are the batch's. Its provenance names the batch
    (``monte_carlo_case``).

    A case that crashed in the batch raises its own error here, as it did
    there. Refused (:class:`MonteCarloCaseRefused`) when the scenario changed
    since the batch, when the batch has no such case, and when a reference
    data file is not the one the case used in the batch."""
    _check_script_consent(scenario, allow_scripts)
    service, record = prepare_case(scenario, archive_dir, case)
    result, summary = _fly(service, allow_scripts)
    return mark_case(result, record), summary
