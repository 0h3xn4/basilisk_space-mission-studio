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

"""What a Monte Carlo batch produced, in a form the GUI and CLI can show.

Basilisk's ``MonteCarlo.Controller`` archives each run as a gzipped
pickle. Loading a pickle runs code, so the tool never reads an archive
it did not just write (security analysis S-04): at the end of a batch,
``engine.monte_carlo.run_monte_carlo`` reads back the files that same
call wrote and saves this module's pickle-free summary next to them --
``batch_results.npz`` (positions and velocities, ``numpy.savez``, read
with ``allow_pickle=False``) and ``batch_results.json`` (the values each
run drew). Everything here works on that summary only, with no Basilisk
import.

The spread is measured against the batch's mean, along the orbit rather
than in straight lines (a straight-line frame would turn a large
along-track spread into a false radial one, as the orbit curves away
from it): at each sample, R points from the central body to the runs'
mean position, W along the mean orbit's angular momentum, and S = W x R.
A run's radial offset is its distance from the central body minus the
runs' mean distance; its along-track offset is the arc, at that mean
distance, by which it leads (+) or trails (-) R in the R-S plane; its
cross-track offset is the arc out of that plane.

The spread is the standard deviation of those offsets over the runs: the
population one by default, or the sample one, as the scenario's project
configuration chooses (``monte_carlo.spread_statistic``, the models in
``config.models``). A batch keeps the statistic it was run with
(``spread_statistic``), so it reads the same later.

Optional keys of the summary (format 1 still, decision MC-3; a summary
without them opens as before, and an older version ignores them):

* ``outcomes`` and ``outcome_units``: each successful run's headline
  figures (``engine.run_summary.overview_figures``), keyed
  ``"<spacecraft>.<outcome>"`` (``schema.scenario.MONTE_CARLO_OUTCOMES``);
* ``failed_drawn``: what each crashed run drew, by run (its
  ``run<N>.json``);
* ``requirements`` and ``probability_bound``: the requirements the batch
  was run with and the model of their bound; the verdicts are computed when
  the batch is read (``engine.monte_carlo_requirements``);
* ``data_files``: each successful run's reference data files, by kind, with
  their path and SHA-256 (``engine.monte_carlo.data_file_hashes``), so a
  case runs again only with the same data (decision MC-19);
* ``seed``: the batch seed (``monte_carlo.seed``, Monte Carlo plan B1,
  decision MC-20), written only when the batch had one;
* ``node_limits`` (a thermal batch): each node's operating and survival
  range judged on the runs (plan B4, decisions MC-22 and MC-23; rows of
  ``engine.monte_carlo_requirements.NodeLimitResult.to_dict``), with
  ``probability_bound``, the model of their bound;
* ``sensitivity_measure``, ``percentile_method`` and ``percentiles``: the
  choices the batch's outcome statistics and sensitivity are read with
  (plan B2 and B3, ``engine.monte_carlo_statistics``); a summary without
  them reads with the defaults.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ..config import models
from .constellation import CENTRAL_BODY_EQUATORIAL_RADIUS_KM
from .results import ResultSet, TimeSeries

SUMMARY_NPZ = "batch_results.npz"
SUMMARY_JSON = "batch_results.json"
SUMMARY_FORMAT = 1
# The summary keeps at most this many samples per run (evenly strided), so
# a long or finely recorded batch of many runs still fits in memory.
MAX_SAMPLES = 2000
# Per-run curves are plotted for at most this many runs; the spread
# series always covers every run.
MAX_PLOTTED_RUNS = 100
OFFSET_COMPONENTS = ("radial", "along_track", "cross_track")
SPREAD_CHOICE = "monte_carlo.spread_statistic"
BOUND_CHOICE = "monte_carlo.probability_bound"  # engine.monte_carlo_requirements
# numpy.std's ddof of each model of SPREAD_CHOICE: the divisor is N - ddof.
SPREAD_DDOF = {"population": 0, "sample": 1}
# The thermal and operations batches' band around the mean (decision MC-27, plan Q8): the runs' mean
# plus or minus three of their standard deviations at each sample, by the batch's spread statistic. It
# assumes no distribution, so it is no probability bound; its label says both.
MEAN_MINUS_3_SD = "mean - 3 standard deviations (not a probability bound)"
MEAN_PLUS_3_SD = "mean + 3 standard deviations (not a probability bound)"
SENSITIVITY_CHOICE = "monte_carlo.sensitivity_measure"  # engine.monte_carlo_statistics
PERCENTILE_CHOICE = "monte_carlo.percentile_method"
PERCENTILES = "monte_carlo.percentiles"


class MonteCarloResultsError(Exception):
    """A batch summary that is missing, of another format, or inconsistent."""


@dataclass
class MonteCarloBatch:
    """Every successful run of one batch on a shared time grid.

    ``positions[sc]``/``velocities[sc]`` have shape (runs, samples, 3), in
    m and m/s in the simulation's inertial frame; row ``k`` is run
    ``runs[k]``. ``drawn[k]`` holds the values that run drew, keyed by a
    readable label ("sat-1 drag coefficient [-]").
    """

    scenario_name: str
    central_body: str
    time_s: np.ndarray
    runs: list[int]
    failed: list[int]
    positions: dict[str, np.ndarray]
    velocities: dict[str, np.ndarray]
    drawn: list[dict[str, float]] = field(default_factory=list)
    epoch_utc: str = ""  # the scenario's epoch, so plots can show dates
    spread_statistic: str = "population"  # the model of SPREAD_CHOICE the batch was run with
    # A thermal Monte Carlo (thermal.sweeps.monte_carlo, decision T-36): no orbits, but each node's
    # temperature [degC] per run, shape (runs, samples), in the case named.
    kind: str = "orbit"  # "orbit", "thermal" or "operations"
    temperatures_c: dict = field(default_factory=dict)
    case: str = ""
    # An operations robustness batch (operations.robustness, decision O-18): no orbits, but per item
    # (a spacecraft's state of charge, its memory) a profile per run, shape (runs, samples), in its unit.
    profiles: dict = field(default_factory=dict)
    profile_units: dict = field(default_factory=dict)
    # Per-run outcomes (Monte Carlo plan A1): outcomes[k] holds run runs[k]'s headline figures,
    # {"<spacecraft>.<outcome>": value}, in outcome_units' units; empty for a summary without them.
    outcomes: list = field(default_factory=list)
    outcome_units: dict = field(default_factory=dict)
    # What each crashed run drew (A4): {run: {label: value}}, as ``drawn``.
    failed_drawn: dict = field(default_factory=dict)
    # The requirements the batch was run with (A2), as dicts of
    # schema.scenario.MonteCarloRequirementConfig, and the model of their bound.
    requirements: list = field(default_factory=list)
    probability_bound: str = "clopper_pearson"
    # Each successful run's data files (MC-19): data_files[k] is run runs[k]'s
    # {kind: {"path": ..., "sha256": ...}}; empty for a summary without them.
    data_files: list = field(default_factory=list)
    # The batch seed (B1): None for Basilisk's own seeding (and for a summary without it).
    seed: int | None = None
    # A thermal batch against its nodes' limits (B4): rows of
    # engine.monte_carlo_requirements.NodeLimitResult.to_dict; empty without them.
    node_limits: list = field(default_factory=list)
    # How the outcome statistics and the sensitivity are read (B2, B3): the models of
    # SENSITIVITY_CHOICE and PERCENTILE_CHOICE, and the percentiles shown [%] (PERCENTILES).
    sensitivity_measure: str = "spearman"
    percentile_method: str = "linear"
    percentiles: list = field(default_factory=lambda: [1.0, 5.0, 50.0, 95.0, 99.0])

    @property
    def spacecraft(self) -> list[str]:
        return list(self.positions)

    @property
    def items(self) -> list[str]:
        """What the batch is shown by: its spacecraft, or a thermal batch's nodes."""
        if self.kind == "operations":
            return list(self.profiles)
        return list(self.temperatures_c) if self.kind == "thermal" else self.spacecraft


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise MonteCarloResultsError(message)


def save(batch: MonteCarloBatch, folder: str | Path) -> Path:
    """Write the summary into ``folder``; returns the JSON file's path."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    arrays = {"time_s": np.asarray(batch.time_s, dtype=float)}
    for index, name in enumerate(batch.spacecraft):
        arrays[f"r_{index}"] = np.asarray(batch.positions[name], dtype=float)
        arrays[f"v_{index}"] = np.asarray(batch.velocities[name], dtype=float)
    for index, name in enumerate(batch.temperatures_c):
        arrays[f"t_{index}"] = np.asarray(batch.temperatures_c[name], dtype=float)
    for index, name in enumerate(batch.profiles):
        arrays[f"p_{index}"] = np.asarray(batch.profiles[name], dtype=float)
    np.savez_compressed(folder / SUMMARY_NPZ, **arrays)
    meta = {
        "format": SUMMARY_FORMAT,
        "scenario_name": batch.scenario_name,
        "central_body": batch.central_body,
        "epoch_utc": batch.epoch_utc,
        "spacecraft": batch.spacecraft,
        "runs": [int(run) for run in batch.runs],
        "failed": [int(run) for run in batch.failed],
        "drawn": batch.drawn,
        "spread_statistic": batch.spread_statistic,
        "sensitivity_measure": batch.sensitivity_measure,
        "percentile_method": batch.percentile_method,
        "percentiles": [float(p) for p in batch.percentiles],
    }
    if batch.outcomes:
        meta.update(outcomes=batch.outcomes, outcome_units=dict(batch.outcome_units))
    if batch.failed_drawn:
        meta["failed_drawn"] = {str(int(run)): drawn for run, drawn in sorted(batch.failed_drawn.items())}
    if batch.requirements:
        meta.update(requirements=batch.requirements, probability_bound=batch.probability_bound)
    if batch.data_files:
        meta["data_files"] = batch.data_files
    if batch.seed is not None:
        meta["seed"] = int(batch.seed)
    if batch.node_limits:
        meta.update(node_limits=batch.node_limits, probability_bound=batch.probability_bound)
    if batch.kind == "thermal":
        meta.update(kind=batch.kind, nodes=list(batch.temperatures_c), case=batch.case)
    elif batch.kind == "operations":
        meta.update(kind=batch.kind, profiles=list(batch.profiles), profile_units=dict(batch.profile_units),
                    case=batch.case)
    path = folder / SUMMARY_JSON
    path.write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return path


def has_summary(folder: str | Path) -> bool:
    folder = Path(folder)
    return (folder / SUMMARY_JSON).is_file() and (folder / SUMMARY_NPZ).is_file()


# What Basilisk's Controller and this tool write into a batch folder: its
# archive, the provenance sidecar, the summary, and per-run and per-message
# files; its data writer also writes one file per key of the runs' custom
# data (engine.monte_carlo's outcomes: spacemissionstudio_outcomes.data and
# spacemissionstudio_outcome_units.data; its data files:
# spacemissionstudio_data_files.data).
BATCH_FILE_PATTERNS = ("MonteCarlo.data", "archive.provenance.json", SUMMARY_JSON, SUMMARY_NPZ,
                       "run*.data", "run*.json", "*.scState.*.data", "spacemissionstudio_outcome*.data",
                       "spacemissionstudio_data_files.data")


def batch_files(folder: str | Path) -> list[Path]:
    """The files of an earlier batch in ``folder`` (none when it holds none)."""
    folder = Path(folder)
    if not folder.is_dir():
        return []
    found = {path for pattern in BATCH_FILE_PATTERNS for path in folder.glob(pattern) if path.is_file()}
    return sorted(found)


# Entries the operating system or file manager adds by itself (.DS_Store,
# Windows Thumbs.db and desktop.ini, any hidden file): they do
# not make a folder "hold other files".
_SYSTEM_CLUTTER = {"thumbs.db", "desktop.ini"}


def _is_clutter(path: Path) -> bool:
    return path.name.startswith(".") or path.name.casefold() in _SYSTEM_CLUTTER


def finished_cases(folder: str | Path) -> int:
    """How many of a running batch's cases have finished: Basilisk's
    Controller writes a case's ``run<i>.data`` when the case ends (the
    earlier batch's files are removed before a batch starts), so the GUI can
    show "37 of 200 cases" without a hook into the Controller."""
    folder = Path(folder)
    return sum(1 for _ in folder.glob("run*.data")) if folder.is_dir() else 0


def folder_state(folder: str | Path) -> str:
    """``"empty"`` (or missing), ``"batch"`` (only an earlier batch's files)
    or ``"other"`` (anything else: not a folder, or other files in it).
    Hidden files and the operating system's own clutter are ignored."""
    folder = Path(folder)
    if not folder.exists():
        return "empty"
    if not folder.is_dir():
        return "other"
    entries = {entry for entry in folder.iterdir() if not _is_clutter(entry)}
    if not entries:
        return "empty"
    return "batch" if (folder / "MonteCarlo.data").is_file() and entries <= set(batch_files(folder)) else "other"


def load(folder: str | Path) -> MonteCarloBatch:
    """Read a summary written by :func:`save`. Never unpickles anything."""
    folder = Path(folder)
    _require(has_summary(folder), f"{folder} has no Monte Carlo results ({SUMMARY_JSON} and {SUMMARY_NPZ}); "
             "run the batch with this version of SpaceMissionStudio to create them")
    try:
        meta = json.loads((folder / SUMMARY_JSON).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise MonteCarloResultsError(f"could not read {folder / SUMMARY_JSON}: {exc}") from exc
    _require(isinstance(meta, dict) and meta.get("format") == SUMMARY_FORMAT,
             f"{folder / SUMMARY_JSON} is not a format-{SUMMARY_FORMAT} Monte Carlo summary")
    try:
        with np.load(folder / SUMMARY_NPZ, allow_pickle=False) as data:
            arrays = {key: data[key] for key in data.files}
    except (OSError, ValueError) as exc:
        raise MonteCarloResultsError(f"could not read {folder / SUMMARY_NPZ}: {exc}") from exc
    names = list(meta.get("spacecraft", []))
    runs = [int(run) for run in meta.get("runs", [])]
    time_s = arrays.get("time_s")
    _require(time_s is not None and time_s.ndim == 1, f"{SUMMARY_NPZ} has no time axis")
    positions, velocities = {}, {}
    for index, name in enumerate(names):
        r, v = arrays.get(f"r_{index}"), arrays.get(f"v_{index}")
        shape = (len(runs), time_s.shape[0], 3)
        _require(r is not None and v is not None and r.shape == shape and v.shape == shape,
                 f"{SUMMARY_NPZ}: the arrays for {name!r} do not match {len(runs)} runs of {time_s.shape[0]} samples")
        positions[name], velocities[name] = r, v
    kind = meta.get("kind", "orbit")
    _require(kind in ("orbit", "thermal", "operations"), f"{SUMMARY_JSON}: unknown kind {kind!r}")
    temperatures = {}
    for index, name in enumerate(meta.get("nodes", []) if kind == "thermal" else []):
        values = arrays.get(f"t_{index}")
        _require(values is not None and values.shape == (len(runs), time_s.shape[0]),
                 f"{SUMMARY_NPZ}: the temperatures of {name!r} do not match {len(runs)} runs of "
                 f"{time_s.shape[0]} samples")
        temperatures[str(name)] = values
    profiles = {}
    for index, name in enumerate(meta.get("profiles", []) if kind == "operations" else []):
        values = arrays.get(f"p_{index}")
        _require(values is not None and values.shape == (len(runs), time_s.shape[0]),
                 f"{SUMMARY_NPZ}: the profile {name!r} does not match {len(runs)} runs of {time_s.shape[0]} samples")
        profiles[str(name)] = values
    _require(kind != "thermal" or temperatures, f"{SUMMARY_JSON}: a thermal batch without nodes")
    _require(kind != "operations" or profiles, f"{SUMMARY_JSON}: an operations batch without profiles")
    drawn = meta.get("drawn") or [{} for _ in runs]
    _require(len(drawn) == len(runs), f"{SUMMARY_JSON}: {len(drawn)} drawn-value rows for {len(runs)} runs")
    statistic = meta.get("spread_statistic", "population")  # a summary written before the choice: population
    _require(statistic in SPREAD_DDOF, f"{SUMMARY_JSON}: unknown spread statistic {statistic!r}")
    outcomes = meta.get("outcomes") or []  # a summary written before the outcomes (A1) has none
    _require(isinstance(outcomes, list) and (not outcomes or len(outcomes) == len(runs))
             and all(isinstance(row, dict) for row in outcomes),
             f"{SUMMARY_JSON}: {len(outcomes)} outcome rows for {len(runs)} runs")
    failed_drawn = meta.get("failed_drawn") or {}
    _require(isinstance(failed_drawn, dict) and all(isinstance(row, dict) for row in failed_drawn.values()),
             f"{SUMMARY_JSON}: failed_drawn is not a table of drawn values by run")
    requirements = meta.get("requirements") or []
    _require(isinstance(requirements, list) and all(isinstance(r, dict) and {"name", "spacecraft", "outcome",
                                                                              "confidence"} <= set(r)
                                                    for r in requirements),
             f"{SUMMARY_JSON}: requirements is not a list of requirements")
    data_files = meta.get("data_files") or []  # a summary written before MC-19 has none
    _require(_is_data_file_table(data_files, len(runs)),
             f"{SUMMARY_JSON}: data_files is not a table of data files for each of the {len(runs)} runs")
    bound = str(meta.get("probability_bound", "clopper_pearson"))
    _require(bound in models.names(BOUND_CHOICE), f"{SUMMARY_JSON}: unknown probability bound {bound!r}")
    seed = meta.get("seed")  # a summary without a batch seed (B1) has none
    _require(seed is None or (isinstance(seed, int) and not isinstance(seed, bool)),
             f"{SUMMARY_JSON}: seed is not a whole number")
    node_limits = meta.get("node_limits") or []  # a thermal summary written before B4 has none
    _require(isinstance(node_limits, list) and all(_is_node_limit(row) for row in node_limits),
             f"{SUMMARY_JSON}: node_limits is not a table of node limits")
    measure = str(meta.get("sensitivity_measure", "spearman"))  # a summary written before B2: the default
    _require(measure in models.names(SENSITIVITY_CHOICE), f"{SUMMARY_JSON}: unknown sensitivity measure {measure!r}")
    method = str(meta.get("percentile_method", "linear"))
    _require(method in models.names(PERCENTILE_CHOICE), f"{SUMMARY_JSON}: unknown percentile method {method!r}")
    percentiles = meta.get("percentiles", [1.0, 5.0, 50.0, 95.0, 99.0])
    _require(isinstance(percentiles, list) and all(isinstance(p, (int, float)) and not isinstance(p, bool)
                                                   and 0.0 <= p <= 100.0 for p in percentiles),
             f"{SUMMARY_JSON}: percentiles is not a list of percentiles from 0 to 100")
    return MonteCarloBatch(str(meta.get("scenario_name", "")), str(meta.get("central_body", "earth")), time_s,
                           runs, [int(run) for run in meta.get("failed", [])], positions, velocities,
                           [{str(k): float(v) for k, v in row.items()} for row in drawn],
                           str(meta.get("epoch_utc", "")), statistic, kind, temperatures, str(meta.get("case", "")),
                           profiles, {str(k): str(v) for k, v in (meta.get("profile_units") or {}).items()},
                           [{str(k): float(v) for k, v in row.items()} for row in outcomes],
                           {str(k): str(v) for k, v in (meta.get("outcome_units") or {}).items()},
                           {int(run): {str(k): float(v) for k, v in row.items()} for run, row in failed_drawn.items()},
                           [dict(r) for r in requirements], bound,
                           [{str(kind): {str(k): str(v) for k, v in record.items()} for kind, record in row.items()}
                            for row in data_files], seed, [dict(row) for row in node_limits],
                           measure, method, [float(p) for p in percentiles])


def _is_node_limit(row) -> bool:
    """``row`` reads as a node limit's result (``NodeLimitResult.from_dict``)."""
    from .monte_carlo_requirements import NodeLimitResult

    if not isinstance(row, dict):
        return False
    try:
        NodeLimitResult.from_dict(row)
    except (KeyError, TypeError, ValueError):
        return False
    return True


def _is_data_file_table(data_files, runs: int) -> bool:
    """``data_files`` is empty or one {kind: {"path", "sha256"}} per run."""
    return isinstance(data_files, list) and (not data_files or len(data_files) == runs) and all(
        isinstance(row, dict) and all(isinstance(record, dict) for record in row.values()) for row in data_files)


def case_data_files(folder: str | Path, case: int) -> dict | None:
    """The data files ``case`` of the batch in ``folder`` used, by kind (the
    summary's ``data_files``), or None when the summary does not record
    them: a batch made before decision MC-19, a case that did not succeed,
    or no summary that can be read. Reads only the JSON file."""
    try:
        meta = json.loads((Path(folder) / SUMMARY_JSON).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(meta, dict):
        return None
    runs, data_files = meta.get("runs"), meta.get("data_files")
    if not isinstance(runs, list) or not data_files or not _is_data_file_table(data_files, len(runs)):
        return None
    try:
        index = [int(run) for run in runs].index(int(case))
    except (TypeError, ValueError):
        return None
    return {str(kind): dict(record) for kind, record in data_files[index].items()}


def stride_for(samples: int) -> int:
    """Every how many samples :data:`MAX_SAMPLES` keeps."""
    return max(1, -(-samples // MAX_SAMPLES))


def offsets(positions: np.ndarray, velocities: np.ndarray) -> np.ndarray:
    """(runs, samples, 3) radial, along-track and cross-track offsets [m] of
    each run from the batch's mean, curvilinear (see the module docstring)."""
    mean_r = positions.mean(axis=0)  # (samples, 3)
    mean_v = velocities.mean(axis=0)
    radial = mean_r / np.linalg.norm(mean_r, axis=1, keepdims=True)
    normal = np.cross(mean_r, mean_v)
    normal /= np.linalg.norm(normal, axis=1, keepdims=True)
    along = np.cross(normal, radial)
    distance = np.linalg.norm(positions, axis=2)  # (runs, samples)
    mean_distance = distance.mean(axis=0)
    unit = positions / distance[:, :, None]
    in_plane = np.arctan2(np.einsum("rtk,tk->rt", unit, along), np.einsum("rtk,tk->rt", unit, radial))
    out_of_plane = np.arcsin(np.clip(np.einsum("rtk,tk->rt", unit, normal), -1.0, 1.0))
    return np.stack([distance - mean_distance, mean_distance * in_plane, mean_distance * out_of_plane], axis=-1)


def spread(offsets_m: np.ndarray, statistic: str = "population") -> np.ndarray:
    """The standard deviation over the runs (axis 0) of ``offsets_m``, by
    ``statistic`` (:data:`SPREAD_DDOF`); zeros for a single run."""
    if offsets_m.shape[0] < 2:
        return np.zeros_like(offsets_m[0])
    return offsets_m.std(axis=0, ddof=SPREAD_DDOF[statistic])


def spread_model(batch: MonteCarloBatch) -> models.Model:
    """The model of the batch's spread (``config.models``)."""
    return models.model(SPREAD_CHOICE, batch.spread_statistic)


def statistic_line(batch: MonteCarloBatch) -> str:
    """The statistic of the spread, as the command line names it."""
    model = spread_model(batch)
    return f"1-sigma: the {model.title.lower()} of the {len(batch.runs)} run(s) ({SPREAD_CHOICE}: {model.name})"


def _equatorial_radius_m(central_body: str) -> float:
    return CENTRAL_BODY_EQUATORIAL_RADIUS_KM.get(central_body, 0.0) * 1e3


def to_result_set(batch: MonteCarloBatch) -> ResultSet:
    """The batch as plottable series, per spacecraft:

    * ``<sc>.monte_carlo.altitude`` [m]: distance above the central body's
      equatorial radius, one column per run;
    * ``<sc>.monte_carlo.radial_offset``, ``.along_track_offset``,
      ``.cross_track_offset`` [m]: each run against the batch mean;
    * ``<sc>.monte_carlo.spread`` [m]: the 1-sigma of the three offsets
      over all runs, by the batch's statistic (:func:`spread`).

    Per-run series hold the first :data:`MAX_PLOTTED_RUNS` runs.
    """
    result = ResultSet(scenario_name=f"{batch.scenario_name} (Monte Carlo)")
    shown = min(len(batch.runs), MAX_PLOTTED_RUNS)
    columns = [f"run_{run}" for run in batch.runs[:shown]]
    if batch.kind == "operations":  # each profile: every run's, and the runs' mean, spread and extremes
        for name, values in batch.profiles.items():
            unit = batch.profile_units.get(name, "-")
            result.add(TimeSeries(f"operations_monte_carlo.{name}.value", batch.time_s, columns, values[:shown].T,
                                  unit))
            sigma = spread(values, batch.spread_statistic)
            mean = values.mean(axis=0)
            result.add(TimeSeries(f"operations_monte_carlo.{name}.spread", batch.time_s,
                                  ["mean", MEAN_MINUS_3_SD, MEAN_PLUS_3_SD, "lowest run", "highest run"],
                                  np.column_stack([mean, mean - 3 * sigma, mean + 3 * sigma, values.min(axis=0),
                                                   values.max(axis=0)]), unit))
        return result
    if batch.kind == "thermal":  # each node: every run's temperature, and the runs' mean and spread
        for name, values in batch.temperatures_c.items():
            result.add(TimeSeries(f"thermal_monte_carlo.{name}.temperature", batch.time_s, columns,
                                  values[:shown].T, "degC"))
            sigma = spread(values, batch.spread_statistic)
            mean = values.mean(axis=0)
            result.add(TimeSeries(f"thermal_monte_carlo.{name}.spread", batch.time_s,
                                  ["mean", MEAN_MINUS_3_SD, MEAN_PLUS_3_SD, "coldest run", "hottest run"],
                                  np.column_stack([mean, mean - 3 * sigma, mean + 3 * sigma, values.min(axis=0),
                                                   values.max(axis=0)]), "degC"))
        return result
    radius_m = _equatorial_radius_m(batch.central_body)
    for name in batch.spacecraft:
        r, v = batch.positions[name], batch.velocities[name]
        altitude = np.linalg.norm(r, axis=2) - radius_m  # (runs, samples)
        result.add(TimeSeries(f"{name}.monte_carlo.altitude", batch.time_s, columns, altitude[:shown].T, "m"))
        rel = offsets(r, v)
        for index, component in enumerate(OFFSET_COMPONENTS):
            result.add(TimeSeries(f"{name}.monte_carlo.{component}_offset", batch.time_s, columns,
                                  rel[:shown, :, index].T, "m"))
        result.add(TimeSeries(f"{name}.monte_carlo.spread", batch.time_s, list(OFFSET_COMPONENTS),
                              spread(rel, batch.spread_statistic), "m"))
    return result


@dataclass(frozen=True)
class SpreadSummary:
    """The 1-sigma offsets [m] at the end of the batch, and the altitude range [m]."""

    radial_m: float
    along_track_m: float
    cross_track_m: float
    altitude_min_m: float
    altitude_max_m: float


@dataclass(frozen=True)
class NodeSpread:
    """A thermal batch's node over the runs [degC]: the coldest and
    hottest any run reached, and the 1-sigma of the runs' minima and
    maxima (by the batch's statistic)."""

    coldest_c: float
    hottest_c: float
    sigma_min_k: float
    sigma_max_k: float


def node_spread(batch: MonteCarloBatch, node: str) -> NodeSpread:
    """A thermal node's (or an operations profile's, in its own unit)
    extremes over the runs and the 1-sigma of each run's minimum and
    maximum."""
    values = batch.profiles[node] if batch.kind == "operations" else batch.temperatures_c[node]
    lows, highs = values.min(axis=1), values.max(axis=1)
    ddof = SPREAD_DDOF[batch.spread_statistic]
    sigma_min = float(lows.std(ddof=ddof)) if len(lows) > 1 else 0.0
    sigma_max = float(highs.std(ddof=ddof)) if len(highs) > 1 else 0.0
    return NodeSpread(float(lows.min()), float(highs.max()), sigma_min, sigma_max)


def final_spread(batch: MonteCarloBatch, spacecraft: str) -> SpreadSummary:
    rel = offsets(batch.positions[spacecraft], batch.velocities[spacecraft])[:, -1, :]
    sigma = spread(rel, batch.spread_statistic)
    altitude = np.linalg.norm(batch.positions[spacecraft][:, -1, :], axis=1) - _equatorial_radius_m(batch.central_body)
    return SpreadSummary(float(sigma[0]), float(sigma[1]), float(sigma[2]),
                         float(altitude.min()), float(altitude.max()))


def outcome_label(key: str, unit: str) -> str:
    """A run table's column for outcome ``key``: ``"sat-1 lowest altitude
    [km]"`` for ``"sat-1.lowest_altitude"``."""
    from ..schema.scenario import MONTE_CARLO_OUTCOME_TITLES

    spacecraft, _, outcome = key.rpartition(".")
    title = MONTE_CARLO_OUTCOME_TITLES.get(outcome, outcome.replace("_", " "))
    if not spacecraft:
        return f"{title} [{unit}]"
    return f"{spacecraft} {title[0].lower()}{title[1:]} [{unit}]"


STATUS_LABEL = "Status"
MEETS_ALL_LABEL = "Meets all requirements"
SUCCEEDED, CRASHED = "succeeded", "crashed"
FAILED = "failed"  # a thermal run whose draw the model refused (thermal.sweeps.monte_carlo)


def _outcome_keys(batch: MonteCarloBatch, spacecraft: str) -> list[str]:
    """The outcome keys of the run's and of ``spacecraft``, in the order
    of schema.scenario.MONTE_CARLO_OUTCOMES."""
    from ..schema.scenario import MONTE_CARLO_OUTCOMES, monte_carlo_outcome_key

    found = {key for row in batch.outcomes for key in row}
    return [key for key in (monte_carlo_outcome_key(spacecraft, outcome) for outcome in MONTE_CARLO_OUTCOMES)
            if key in found]


def run_table(batch: MonteCarloBatch, spacecraft: str | None = None, outcomes: bool = False):
    """(column labels, rows): per run its index, every drawn value, and
    where it ended against the batch mean [km] (for ``spacecraft``, by
    default the first).

    ``outcomes`` (a thermal batch): also the failed runs whose draws the
    summary keeps (``failed_drawn``), with their draws and no temperatures,
    and then a "Status" column (``"succeeded"`` or ``"failed"``), so the
    failed runs are found in the table (Monte Carlo plan B8).

    ``outcomes`` (an orbit batch): also each run's outcomes of the run and
    of ``spacecraft`` (Monte Carlo plan A1), when the summary has them; the
    crashed runs whose draws the summary keeps (A4), with their draws, no
    offsets and no outcomes; then a "Status" column (``"succeeded"`` or
    ``"crashed"``) when it lists any; and with requirements, "Meets all
    requirements" (``engine.monte_carlo_requirements.run_verdicts``). The
    status and verdict cells are text, every other cell a float (NaN when
    there is no value). By default the columns are as before."""
    drawn_rows = list(batch.drawn) + (list(batch.failed_drawn.values()) if outcomes else [])
    drawn_labels: list[str] = []
    for row in drawn_rows:
        drawn_labels += [label for label in row if label not in drawn_labels]
    if batch.kind == "operations":  # ``spacecraft`` names a profile; the outcomes are among the drawn values
        item = spacecraft or batch.items[0]
        values = batch.profiles[item]
        unit = batch.profile_units.get(item, "-")
        rows = [[float(run)] + [(batch.drawn[k] if k < len(batch.drawn) else {}).get(label, float("nan"))
                                for label in drawn_labels] + [float(values[k].min()), float(values[k].max())]
                for k, run in enumerate(batch.runs)]
        return ["Run"] + drawn_labels + [f"{item} lowest [{unit}]", f"{item} highest [{unit}]"], rows
    if batch.kind == "thermal":  # ``spacecraft`` names a node
        node = spacecraft or batch.items[0]
        values = batch.temperatures_c[node]
        rows = [[float(run)] + [(batch.drawn[k] if k < len(batch.drawn) else {}).get(label, float("nan"))
                                for label in drawn_labels]
                + [float(values[k].min()), float(values[k].max()), float(values[k].mean())]
                for k, run in enumerate(batch.runs)]
        labels = ["Run"] + drawn_labels + [f"{node} min [degC]", f"{node} max [degC]", f"{node} mean [degC]"]
        failed = sorted(run for run in batch.failed_drawn if run in set(batch.failed)) if outcomes else []
        if failed:
            nan = float("nan")
            rows += [[float(run)] + [batch.failed_drawn[run].get(label, nan) for label in drawn_labels] + [nan] * 3
                     for run in failed]
            rows.sort(key=lambda row: row[0])
            labels.append(STATUS_LABEL)
            for row in rows:
                row.append(FAILED if int(row[0]) in failed else SUCCEEDED)
        return labels, rows
    spacecraft = spacecraft or batch.spacecraft[0]
    final = offsets(batch.positions[spacecraft], batch.velocities[spacecraft])[:, -1, :] / 1e3  # [km]
    outcome_labels = [f"{spacecraft} final {c.replace('_', '-')} offset [km]" for c in OFFSET_COMPONENTS]
    rows = []
    for k, run in enumerate(batch.runs):
        drawn = batch.drawn[k] if k < len(batch.drawn) else {}
        rows.append([float(run)] + [drawn.get(label, float("nan")) for label in drawn_labels]
                    + [float(value) for value in final[k]])
    labels = ["Run"] + drawn_labels + outcome_labels
    if not outcomes:
        return labels, rows
    from .monte_carlo_requirements import run_verdicts

    keys = _outcome_keys(batch, spacecraft)
    labels += [outcome_label(key, batch.outcome_units.get(key, "-")) for key in keys]
    for k, row in enumerate(rows):
        values = batch.outcomes[k] if k < len(batch.outcomes) else {}
        row += [float(values.get(key, float("nan"))) for key in keys]
    nan = float("nan")
    crashed = sorted(run for run in batch.failed_drawn if run in set(batch.failed))
    for run in crashed:
        drawn = batch.failed_drawn[run]
        rows.append([float(run)] + [drawn.get(label, nan) for label in drawn_labels] + [nan] * (3 + len(keys)))
    rows.sort(key=lambda row: row[0])
    if crashed:
        labels.append(STATUS_LABEL)
        for row in rows:
            row.append(CRASHED if int(row[0]) in crashed else SUCCEEDED)
    verdicts = run_verdicts(batch)
    if verdicts:
        labels.append(MEETS_ALL_LABEL)
        for row in rows:
            row.append(verdicts.get(int(row[0]), ""))
    return labels, rows


def outcome_ranges(batch: MonteCarloBatch) -> list[tuple[str, float, float, str]]:
    """Each outcome's lowest and highest value over the successful runs that
    recorded it: (label, lowest, highest, unit), in the order of
    schema.scenario.MONTE_CARLO_OUTCOMES, the run's first, then each
    spacecraft's (the command line's short table)."""
    import math

    keys = []
    for name in batch.spacecraft or [""]:
        keys += [key for key in _outcome_keys(batch, name) if key not in keys]
    ranges = []
    for key in keys:
        values = [row[key] for row in batch.outcomes if key in row and math.isfinite(row[key])]
        if values:
            unit = batch.outcome_units.get(key, "-")
            ranges.append((outcome_label(key, unit).rsplit(" [", 1)[0], min(values), max(values), unit))
    return ranges


def format_km(value_m: float) -> str:
    """A distance [m] as km to 3 significant figures; under a millimetre
    (rounding noise, e.g. runs that do not differ at all) as 0."""
    return "0 km" if abs(value_m) < 1e-3 else f"{value_m / 1e3:.3g} km"


def summary_lines(batch: MonteCarloBatch) -> list[str]:
    """A few lines for the CLI and the log."""
    days = float(batch.time_s[-1]) / 86400.0 if batch.time_s.size else 0.0
    lines = [f"{len(batch.runs)} run(s) summarized over {days:.3g} day(s); failed: {batch.failed or 'none'}"]
    if batch.kind == "operations":
        for name in batch.items:
            s = node_spread(batch, name)
            unit = batch.profile_units.get(name, "-")
            lines.append(f"{name}: {s.coldest_c:.4g} to {s.hottest_c:.4g} {unit} over the runs; 1-sigma of the "
                         f"lowest {s.sigma_min_k:.3g} {unit}")
        return lines
    if batch.kind == "thermal":
        for name in batch.items:
            s = node_spread(batch, name)
            lines.append(f"{name}: {s.coldest_c:.1f} to {s.hottest_c:.1f} degC over the runs; 1-sigma of the "
                         f"minimum {s.sigma_min_k:.2f} K, of the maximum {s.sigma_max_k:.2f} K")
        return lines
    for name in batch.spacecraft:
        s = final_spread(batch, name)
        lines.append(f"{name}: 1-sigma at the end -- along-track {format_km(s.along_track_m)}, "
                     f"radial {format_km(s.radial_m)}, cross-track {format_km(s.cross_track_m)}")
    return lines
