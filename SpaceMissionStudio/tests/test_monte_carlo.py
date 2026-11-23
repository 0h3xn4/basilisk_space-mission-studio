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
"""Tests for spacemissionstudio.engine.monte_carlo.run_monte_carlo(). Needs a
Basilisk build to import (Basilisk.utilities.MonteCarlo.* at module level);
see tests/conftest.py for the auto-skip behavior in this development
sandbox, which does not have one.
"""

import math

import pytest

from spacemissionstudio.schema import GravityConfig, MonteCarloConfig, OrbitIC, Scenario, SpacecraftConfig
from spacemissionstudio.schema.command import Command
from spacemissionstudio.schema.scenario import ConstantThrustConfig, DispersionConfig, StationKeepingConfig

pytestmark = pytest.mark.requires_basilisk


def _scenario(**spacecraft_overrides):
    return Scenario(
        name="mc test scenario",
        epoch_utc="2030-01-01T00:00:00",
        gravity=GravityConfig(central_body="earth", central_body_degree=0),
        spacecraft=[SpacecraftConfig(
            name="sat-1", dry_mass_kg=100.0,
            orbit=OrbitIC(type="cartesian", position_km=[7000.0, 0.0, 0.0], velocity_km_s=[0.0, 7.5, 0.0]),
            **spacecraft_overrides,
        )],
        monte_carlo=MonteCarloConfig(enabled=True, num_runs=1),
    )


def test_run_monte_carlo_reports_a_clean_error_when_archive_dir_is_a_file(tmp_path):
    """Regression test for an audit finding: archive_dir.mkdir(...) used to
    sit outside run_monte_carlo()'s own try/except (which only wrapped
    controller.executeSimulations()), so pointing --archive-dir at a path
    that already exists as a plain file raised a bare FileExistsError
    instead of this module's usual MonteCarloError.
    """
    from spacemissionstudio.engine.monte_carlo import MonteCarloError, run_monte_carlo

    archive_dir = tmp_path / "already_a_file"
    archive_dir.write_text("not a directory")

    with pytest.raises(MonteCarloError, match="could not create Monte Carlo archive directory"):
        run_monte_carlo(_scenario(), MonteCarloConfig(enabled=True, num_runs=1), archive_dir)


def test_propellant_offset_kg_sums_station_keeping_and_constant_thrust():
    """The propellant added to the dry mass is station keeping's plus constant
    thrust's."""
    from spacemissionstudio.engine.monte_carlo import _propellant_offset_kg

    sc = SpacecraftConfig(
        name="s", orbit=OrbitIC(type="cartesian", position_km=[7000, 0, 0], velocity_km_s=[0, 7.5, 0]),
        station_keeping=StationKeepingConfig(
            target_altitude_km=500, deadband_km=1, thrust_n=0.1, isp_s=200, propellant_kg=10.0),
        constant_thrust=ConstantThrustConfig(propellant_kg=2.0),
    )
    assert _propellant_offset_kg(sc) == 12.0


def test_propellant_offset_kg_is_zero_with_neither_configured():
    """Without either, no propellant is added."""
    from spacemissionstudio.engine.monte_carlo import _propellant_offset_kg

    sc = SpacecraftConfig(name="s", orbit=OrbitIC(type="cartesian", position_km=[7000, 0, 0],
                                                    velocity_km_s=[0, 7.5, 0]))
    assert _propellant_offset_kg(sc) == 0.0


def test_dry_mass_dispersion_adds_propellant_offset_on_top():
    """Regression test for an audit finding: Basilisk's dispersion classes
    write their generated value ABSOLUTELY to hub.mHub, with no way to add
    anything on top -- but hub.mHub is dry_mass_kg + propellant for a
    spacecraft with station_keeping/constant_thrust configured (see
    service.py's own initial_mass_kg computation), not just dry_mass_kg.
    A plain dispersion on "dry_mass_kg" would therefore silently disperse
    the TOTAL mass under that name instead of just the dry mass.
    """
    from spacemissionstudio.engine.monte_carlo import _build_dispersion

    scenario = _scenario(station_keeping=StationKeepingConfig(
        target_altitude_km=500, deadband_km=1, thrust_n=0.1, isp_s=200, propellant_kg=10.0))
    dispersion = DispersionConfig(spacecraft="sat-1", quantity="dry_mass_kg", kind="uniform", bounds=[90.0, 110.0])

    disp = _build_dispersion(dispersion, scenario)
    for _ in range(50):
        value = disp.generate(sim=None)
        assert 100.0 <= value <= 120.0  # [90, 110] dry-mass bounds + 10 kg propellant offset


def test_dry_mass_dispersion_with_no_propellant_is_unshifted():
    """Without propellant, a uniform dry-mass dispersion stays within its
    bounds."""
    from spacemissionstudio.engine.monte_carlo import _build_dispersion

    scenario = _scenario()  # no station_keeping/constant_thrust
    dispersion = DispersionConfig(spacecraft="sat-1", quantity="dry_mass_kg", kind="uniform", bounds=[90.0, 110.0])

    disp = _build_dispersion(dispersion, scenario)
    for _ in range(50):
        value = disp.generate(sim=None)
        assert 90.0 <= value <= 110.0


def test_dry_mass_normal_dispersion_adds_propellant_offset_on_top():
    """A normal dry-mass dispersion adds the 5 kg of propellant to its mean."""
    from spacemissionstudio.engine.monte_carlo import _build_dispersion

    scenario = _scenario(constant_thrust=ConstantThrustConfig(propellant_kg=5.0))
    dispersion = DispersionConfig(spacecraft="sat-1", quantity="dry_mass_kg", kind="normal",
                                   mean=100.0, std_deviation=0.001)

    disp = _build_dispersion(dispersion, scenario)
    value = disp.generate(sim=None)
    assert value == pytest.approx(105.0, abs=0.1)  # mean 100 + 5 kg propellant offset


def test_build_dispersion_unknown_spacecraft_raises_clear_error():
    """A dispersion on a spacecraft the scenario does not have is refused,
    naming it."""
    from spacemissionstudio.engine.monte_carlo import MonteCarloError, _build_dispersion

    scenario = _scenario()
    dispersion = DispersionConfig(spacecraft="does-not-exist", quantity="dry_mass_kg", kind="uniform",
                                   bounds=[90.0, 110.0])

    with pytest.raises(MonteCarloError, match="does-not-exist"):
        _build_dispersion(dispersion, scenario)


# -- The orbit, inertia, body-rate and coefficient dispersions -----------------

_TEMPLATE_07 = "07_attitude_pointing_with_adcs_hardware.json"


def _template_07_with(dispersions, num_runs=3, duration_s=120.0):
    """Template 07 (full attitude, sphere drag and SRP), shortened."""
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates" / _TEMPLATE_07
    data = json.loads(path.read_text(encoding="utf-8"))
    name = data["spacecraft"][0]["name"]
    data["sim_settings"]["duration_days"] = duration_s / 86400.0
    data["monte_carlo"].update(enabled=True, num_runs=num_runs,
                               dispersions=[dict(d, spacecraft=name) for d in dispersions])
    scenario = Scenario.from_dict(data)
    scenario.validate()
    return scenario


def _draw(dispersion, scenario):
    """One draw of ``dispersion``, as the Controller makes it: {path: value}."""
    import ast

    from spacemissionstudio.engine.monte_carlo import _build_dispersion, _create_sim

    sim = _create_sim(scenario)
    disp = _build_dispersion(dispersion, scenario)
    try:
        return {disp.getName(): ast.literal_eval(disp.generateString(sim))}
    except TypeError:  # OrbitalElementDispersion: two co-dependent paths
        disp.generate()
        return {disp.getName(i): ast.literal_eval(disp.generateString(i, sim)) for i in (1, 2)}


def test_an_orbit_dispersion_moves_only_the_elements_it_spreads():
    """OrbitalElementDispersion around the nominal orbit: a 1 km spread on the
    semi-major axis changes a, while inclination and RAAN stay nominal (the
    Basilisk class would set an element with no entry to zero)."""
    import numpy as np
    from Basilisk.utilities import orbitalMotion

    from spacemissionstudio.engine.monte_carlo import _central_body_mu, nominal_elements

    scenario = _template_07_with([{"quantity": "orbit_elements", "kind": "uniform",
                                   "element_spread": {"semi_major_axis_km": 1.0}}])
    nominal = nominal_elements(scenario, scenario.spacecraft[0])
    values = list(_draw(scenario.monte_carlo.dispersions[0], scenario).values())
    oe = orbitalMotion.rv2elem(_central_body_mu(scenario), np.array(values[0]), np.array(values[1]))
    assert 0.0 < abs(oe.a - nominal.a) <= 1000.0 + 1e-6  # [m]
    assert oe.i == pytest.approx(nominal.i, abs=1e-12)
    assert oe.Omega == pytest.approx(nominal.Omega, abs=1e-12)


def test_the_body_rate_spread_is_added_to_the_nominal_rate():
    """The vector Cartesian classes draw an absolute vector; the rate is
    dispersed around template 07's own nominal rate instead (deg/s spread)."""
    import math

    import numpy as np

    scenario = _template_07_with([{"quantity": "angular_rate_bn_b", "kind": "uniform", "bounds": [-0.1, 0.1]}])
    nominal = np.array(scenario.spacecraft[0].omega_bn_b_init_rad_s)  # [rad/s]
    for _ in range(5):
        (rate,) = _draw(scenario.monte_carlo.dispersions[0], scenario).values()
        assert np.all(np.abs(np.array(rate) - nominal) <= math.radians(0.1) + 1e-12)


def test_an_inertia_dispersion_is_not_clipped_to_one_kg_m2_by_default():
    """InertiaTensorDispersion clips each diagonal offset to [-1, 1] kg*m^2
    unless given bounds; with no bounds set here, a 5 kg*m^2 spread is kept."""
    import numpy as np

    scenario = _template_07_with([{"quantity": "inertia_kg_m2", "kind": "normal", "std_deviation": 5.0}])
    nominal = np.array(scenario.spacecraft[0].inertia_kg_m2).reshape(3, 3)
    offsets = []
    for _ in range(10):
        (inertia,) = _draw(scenario.monte_carlo.dispersions[0], scenario).values()
        offsets += list(np.diag(np.array(inertia) - nominal))
    assert max(abs(o) for o in offsets) > 1.0  # [kg*m^2]


def test_a_batch_disperses_every_new_quantity_in_every_run(tmp_path):
    """Three runs through Basilisk's Controller: each run's archived
    parameters hold its own orbit, inertia, rate, Cd and Cr, within bounds."""
    import json

    scenario = _template_07_with([
        {"quantity": "orbit_elements", "kind": "normal", "element_spread": {"semi_major_axis_km": 0.5}},
        {"quantity": "inertia_kg_m2", "kind": "normal", "std_deviation": 0.5, "angle_std_deg": 1.0},
        {"quantity": "angular_rate_bn_b", "kind": "normal", "std_deviation": 0.05},
        {"quantity": "drag_coeff", "kind": "uniform", "bounds": [2.0, 3.0]},
        {"quantity": "srp_coeff", "kind": "uniform", "bounds": [1.2, 1.5]},
    ])
    from spacemissionstudio.engine.monte_carlo import run_monte_carlo

    assert run_monte_carlo(scenario, scenario.monte_carlo, tmp_path) == []
    runs = [json.loads((tmp_path / f"run{i}.json").read_text()) for i in range(3)]
    drag = [float(next(v for k, v in run.items() if k.endswith("dragCoeff"))) for run in runs]
    srp = [float(next(v for k, v in run.items() if k.endswith("coefficientReflection"))) for run in runs]
    assert len(set(drag)) == 3 and all(2.0 <= cd <= 3.0 for cd in drag)
    assert all(1.2 <= cr <= 1.5 for cr in srp)
    for suffix in ("r_CN_NInit", "v_CN_NInit", "IHubPntBc_B", "omega_BN_BInit"):
        assert len({next(v for k, v in run.items() if k.endswith(suffix)) for run in runs}) == 3, suffix


def test_a_batch_leaves_a_pickle_free_summary_of_every_run(tmp_path):
    """After the batch, run_monte_carlo reads back the run files it just
    wrote and saves batch_results.npz/.json (security analysis S-04): every
    run's trajectory and its drawn values under readable labels, matching
    what the Controller recorded in runN.json."""
    import json

    from spacemissionstudio.engine import monte_carlo_results as mcr
    from spacemissionstudio.engine.monte_carlo import run_monte_carlo

    scenario = _template_07_with([
        {"quantity": "orbit_elements", "kind": "normal",
         "element_spread": {"semi_major_axis_km": 0.5, "true_anomaly_deg": 0.1}},
        {"quantity": "drag_coeff", "kind": "uniform", "bounds": [2.0, 3.0]},
        {"quantity": "inertia_kg_m2", "kind": "normal", "std_deviation": 0.5},
    ])
    assert run_monte_carlo(scenario, scenario.monte_carlo, tmp_path) == []
    batch = mcr.load(tmp_path)
    name = scenario.spacecraft[0].name
    assert batch.runs == [0, 1, 2] and batch.failed == []
    assert batch.positions[name].shape == (3, batch.time_s.size, 3)
    assert batch.time_s[-1] == pytest.approx(120.0)  # [s] the shortened run
    for k, drawn in enumerate(batch.drawn):
        params = json.loads((tmp_path / f"run{k}.json").read_text())
        cd = float(next(v for key, v in params.items() if key.endswith("dragCoeff")))
        assert drawn[f"{name} drag coefficient [-]"] == pytest.approx(cd)
        assert set(drawn) >= {f"{name} semi-major axis [km]", f"{name} true anomaly [deg]", f"{name} Ixx [kg m^2]"}
        assert drawn[f"{name} semi-major axis [km]"] == pytest.approx(6928.0, abs=5.0)  # [km] nominal +/- 10 sigma
        assert abs(drawn[f"{name} true anomaly [deg]"]) < 1.0  # [deg] near the nominal 0, not 359.9
    assert len({drawn[f"{name} drag coefficient [-]"] for drawn in batch.drawn}) == 3
    # the starting positions differ along track, as the true-anomaly spread says
    assert mcr.offsets(batch.positions[name], batch.velocities[name])[:, 0, 1].std() > 100.0  # [m]


# -- Every run flies what `run` flies (audit H1, M10) -------------------------


def _short(scenario, duration_s=60.0, **monte_carlo):
    scenario.sim_settings.duration_days = duration_s / 86400.0  # [day]
    scenario.sim_settings.dynamics_task_rate_s = 10.0  # [s]
    for key, value in monte_carlo.items():
        setattr(scenario.monte_carlo, key, value)
    return scenario


def test_each_run_starts_like_a_plain_run_and_flies_the_mission_sequence(monkeypatch):
    """_execute_sim used to call InitializeSimulation() and propagate the set
    duration only: no momentum-dumping priming (SimulationService.initialize)
    and no Mission Sequence. It now does both, as `spacemissionstudio run`."""
    from spacemissionstudio.engine import mission_engine, monte_carlo

    calls = []

    class FakeService:
        def __init__(self, scenario):
            self.scenario = scenario

        def initialize(self):
            calls.append("initialize")

        def run(self):
            calls.append("run")

    class FakeEngine:
        def __init__(self, scenario, service, allow_scripts):
            calls.append(("engine", allow_scripts))

        def run(self):
            calls.append("sequence")

    monkeypatch.setattr(mission_engine, "MissionEngine", FakeEngine)
    plain = type("Sim", (), {})()
    plain._spacemissionstudio_service = FakeService(_scenario())
    monte_carlo._execute_sim(plain)
    assert calls == ["initialize", "run"]

    calls.clear()
    scenario = _scenario()
    scenario.mission_sequence = [Command(kind="propagate", params={"duration_days": 0.001})]
    sequenced = type("Sim", (), {})()
    sequenced._spacemissionstudio_service = FakeService(scenario)
    monte_carlo._execute_sim(sequenced, allow_scripts=True)
    assert calls == ["initialize", ("engine", True), "sequence"]


def test_a_batch_flies_the_mission_sequence_burns(tmp_path):
    """Template 08 raises its orbit with a maneuver. Every Monte Carlo run used
    to stay on the starting orbit (max radius 6778.7 km) while `run` reached
    6957.6 km; now every run reaches the raised orbit."""
    import json
    from pathlib import Path

    import numpy as np

    from spacemissionstudio.engine import monte_carlo_results as mcr
    from spacemissionstudio.engine.monte_carlo import run_monte_carlo

    path = Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates" / \
        "08_mission_sequence_orbit_raise.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    name = data["spacecraft"][0]["name"]
    data["monte_carlo"] = {"enabled": True, "num_runs": 2, "dispersions": [
        {"spacecraft": name, "quantity": "dry_mass_kg", "kind": "uniform",
         "bounds": [data["spacecraft"][0]["dry_mass_kg"] * 0.999, data["spacecraft"][0]["dry_mass_kg"] * 1.001]}]}
    scenario = Scenario.from_dict(data)
    scenario.validate()
    assert run_monte_carlo(scenario, scenario.monte_carlo, tmp_path / "batch") == []
    batch = mcr.load(tmp_path / "batch")
    radius_km = np.linalg.norm(batch.positions[name], axis=2).max(axis=1) / 1e3  # [km] per run
    assert radius_km.min() > 6900.0  # [km] the maneuver was flown in every run


def test_a_batch_records_what_its_runs_share_and_where_their_seeds_are(tmp_path):
    """Transparency audit, Phase 2g: a batch's provenance had the versions
    and the scenario's hash only. It now names the file the scenario came
    from and, as ``nominal_run``, what every run shares (integrator,
    tolerances, data files); the seeds are each run's own, in its
    run<N>.json, so the nominal run's are not given."""
    import json

    from spacemissionstudio.engine.monte_carlo import ARCHIVE_SEEDS_NOTE, run_monte_carlo

    scenario = _short(_scenario())
    file_record = {"scenario_file": "s.json", "scenario_file_sha256": "cd" * 32, "scenario_file_migrations": []}
    assert run_monte_carlo(scenario, scenario.monte_carlo, tmp_path, scenario_file=file_record) == []
    record = json.loads((tmp_path / "archive.provenance.json").read_text(encoding="utf-8"))
    assert (record["scenario_file"], record["scenario_file_sha256"]) == ("s.json", "cd" * 32)
    nominal = record["nominal_run"]
    assert nominal["integrator"] and nominal["integrator_relative_tolerance"] > 0.0
    assert "spice:naif0012.tls" in nominal["data_files"]
    assert not {"rng_seeds", "rng_seed", "run_started_utc", "scenario_sha256"} & set(nominal)
    assert record["rng_seeds"] == ARCHIVE_SEEDS_NOTE
    assert "RNGSeed" in next(iter(json.loads((tmp_path / "run0.json").read_text())))


def test_script_blocks_in_a_batch_need_consent(tmp_path):
    """A batch with script blocks is refused without explicit consent and
    creates no folder."""
    from spacemissionstudio.engine.monte_carlo import MonteCarloError, run_monte_carlo

    scenario = _scenario()
    scenario.mission_sequence = [Command(kind="script_block", params={"code": "pass"})]
    with pytest.raises(MonteCarloError, match="explicit consent"):
        run_monte_carlo(scenario, scenario.monte_carlo, tmp_path / "batch")
    assert not (tmp_path / "batch").exists()


def test_a_folder_holding_other_files_is_refused(tmp_path):
    """A folder holding files other than an earlier batch is refused, even with
    overwrite, and left unchanged."""
    from spacemissionstudio.engine.monte_carlo import MonteCarloError, run_monte_carlo

    (tmp_path / "notes.txt").write_text("mine", encoding="utf-8")
    with pytest.raises(MonteCarloError, match="holds no earlier Monte Carlo batch"):
        run_monte_carlo(_short(_scenario()), MonteCarloConfig(enabled=True, num_runs=1), tmp_path, overwrite=True)
    assert (tmp_path / "notes.txt").read_text(encoding="utf-8") == "mine"


def test_an_earlier_batch_is_replaced_only_with_overwrite(tmp_path):
    """A reused folder used to keep the earlier summary when every new run
    failed, so the GUI showed the old batch as the new one."""
    from spacemissionstudio.engine import monte_carlo_results as mcr
    from spacemissionstudio.engine.monte_carlo import MonteCarloError, run_monte_carlo

    scenario = _short(_scenario(), num_runs=2)
    assert run_monte_carlo(scenario, scenario.monte_carlo, tmp_path) == []
    assert mcr.folder_state(tmp_path) == "batch"
    with pytest.raises(MonteCarloError, match="holds an earlier Monte Carlo batch"):
        run_monte_carlo(scenario, scenario.monte_carlo, tmp_path)
    smaller = _short(_scenario(), num_runs=1)
    assert run_monte_carlo(smaller, smaller.monte_carlo, tmp_path, overwrite=True) == []
    assert not (tmp_path / "run1.data").exists()  # nothing of the larger earlier batch is left
    assert mcr.load(tmp_path).runs == [0]


def test_a_batch_runs_in_several_processes(tmp_path):
    """thread_count > 1 pickles the creation and execution functions into a
    process pool (Controller.setThreadCount)."""
    from spacemissionstudio.engine import monte_carlo_results as mcr
    from spacemissionstudio.engine.monte_carlo import run_monte_carlo

    scenario = _short(_scenario(), num_runs=2, thread_count=2)
    assert run_monte_carlo(scenario, scenario.monte_carlo, tmp_path) == []
    assert mcr.load(tmp_path).runs == [0, 1]


def test_an_earlier_simulation_left_as_garbage_is_collected_before_the_batch_forks(tmp_path, monkeypatch):
    """Audit H5: a Basilisk simulation left in a reference cycle by an earlier run hung
    the batch: the Controller's forked data writer collected it, and
    SimModel's destructor waited forever on thread state copied from the
    parent. run_monte_carlo now collects such garbage before the Controller
    forks."""
    import gc
    import weakref

    from Basilisk.utilities.MonteCarlo.Controller import Controller

    from spacemissionstudio.engine.monte_carlo import run_monte_carlo
    from spacemissionstudio.engine.service import SimulationService

    scenario = _short(_scenario(), num_runs=1)
    alive_at_fork = []
    monkeypatch.setattr(Controller, "executeSimulations", lambda self: alive_at_fork.append(earlier() is not None) or [])
    gc.disable()
    try:
        service = SimulationService(scenario)
        service.build()
        cycle = [service]
        cycle.append(cycle)
        earlier = weakref.ref(service)
        del service, cycle
        assert earlier() is not None  # garbage, not yet collected
        run_monte_carlo(scenario, scenario.monte_carlo, tmp_path)
    finally:
        gc.enable()
    assert alive_at_fork == [False]


def test_a_batch_uses_and_records_the_statistic_its_configuration_chooses(tmp_path):
    """Transparency plan, Phase 6a: a project configuration that chooses
    the sample standard deviation gives a batch that keeps it, and the
    batch's provenance names the model (``models``)."""
    import json

    from spacemissionstudio.config.registry import Configuration
    from spacemissionstudio.engine import monte_carlo_results as mcr
    from spacemissionstudio.engine.monte_carlo import run_monte_carlo

    scenario = _short(_scenario(), num_runs=2)
    scenario.configuration = Configuration(overrides={"monte_carlo.spread_statistic": "sample"})
    assert run_monte_carlo(scenario, scenario.monte_carlo, tmp_path) == []
    batch = mcr.load(tmp_path)
    assert batch.spread_statistic == "sample"
    rel = mcr.offsets(batch.positions["sat-1"], batch.velocities["sat-1"])[:, -1, :]
    assert mcr.final_spread(batch, "sat-1").radial_m == pytest.approx(rel.std(axis=0, ddof=1)[0], abs=1e-12)
    record = json.loads((tmp_path / "archive.provenance.json").read_text(encoding="utf-8"))
    assert record["models"]["monte_carlo.spread_statistic"]["model"] == "sample"
    assert record["models"]["monte_carlo.spread_statistic"]["title"] == "Sample standard deviation"


# -- Outcomes per run (Monte Carlo plan A1) and the draws of crashed runs (A4) --


_TEMPLATE_25 = "25_monte_carlo_orbit_and_drag_dispersions.json"


def _template_25(num_runs=2, duration_days=0.05, **monte_carlo):
    from pathlib import Path

    from spacemissionstudio.schema import load_scenario

    templates = Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates"
    scenario = load_scenario(templates / _TEMPLATE_25)
    scenario.sim_settings.duration_days = duration_days  # [day]
    scenario.monte_carlo.num_runs = num_runs
    scenario.monte_carlo.thread_count = 1
    for key, value in monte_carlo.items():
        setattr(scenario.monte_carlo, key, value)
    return scenario


def _plain_run_of_case(scenario, archive_dir, case):
    """A plain run of ``case``'s draws, made here for the test: the run the
    batch's creation function builds, each entry of run<case>.json applied in
    the file's order with Basilisk's own setter (SimulationExecutor), then
    the same start-up and run (Monte Carlo plan A3 makes this a feature)."""
    import json

    from Basilisk.utilities.MonteCarlo.Controller import SimulationExecutor

    from spacemissionstudio.engine import monte_carlo

    sim = monte_carlo._create_sim(scenario)
    for name, value in json.loads((archive_dir / f"run{case}.json").read_text()).items():
        SimulationExecutor.applyModification(sim, name, value)
    service = sim._spacemissionstudio_service
    service.initialize()
    return service.run()


def test_each_run_keeps_the_overview_figures_of_a_plain_run_of_its_draws(tmp_path):
    """A1's acceptance: a 2-run batch of template 25 (0.05 days) keeps, per
    run, the figures run_summary.overview_figures gives a plain run of that
    case's draws: the same keys, values and units ("altitude" as the lowest
    and the highest altitude)."""
    from spacemissionstudio.engine import monte_carlo_results as mcr
    from spacemissionstudio.engine import run_summary
    from spacemissionstudio.engine.monte_carlo import run_monte_carlo

    scenario = _template_25()
    assert run_monte_carlo(scenario, scenario.monte_carlo, tmp_path) == []
    batch = mcr.load(tmp_path)
    assert batch.runs == [0, 1] and len(batch.outcomes) == 2
    for k, run in enumerate(batch.runs):
        figures = run_summary.overview_figures(_plain_run_of_case(scenario, tmp_path, run))
        expected = {}
        for figure in figures:
            owner, _, name = figure.key.rpartition(".")
            for key in ([f"{owner}.lowest_altitude", f"{owner}.highest_altitude"] if name == "altitude"
                        else [figure.key]):
                expected[key] = (figure.value, figure.unit)
        assert set(batch.outcomes[k]) == set(expected)
        for key, (value, unit) in expected.items():
            assert batch.outcomes[k][key] == pytest.approx(value, rel=1e-9), key
            assert batch.outcome_units[key] == unit
    assert {"run_length", "sat-1.lowest_altitude", "sat-1.highest_altitude", "sat-1.orbital_period"} \
        <= set(batch.outcomes[0])
    assert batch.outcomes[0]["sat-1.lowest_altitude"] != batch.outcomes[1]["sat-1.lowest_altitude"]  # draws differ
    labels, rows = mcr.run_table(batch, outcomes=True)
    assert "sat-1 lowest altitude [km]" in labels and len(rows) == 2
    assert mcr.run_table(batch)[0] == labels[:len(mcr.run_table(batch)[0])]  # the default: as before


def test_a_runs_outcomes_reach_the_summary_from_several_processes(tmp_path):
    """The retention function pickles into the process pool
    (thread_count > 1) and every run's outcomes come back."""
    from spacemissionstudio.engine import monte_carlo_results as mcr
    from spacemissionstudio.engine.monte_carlo import run_monte_carlo

    scenario = _short(_scenario(), num_runs=2, thread_count=2)
    assert run_monte_carlo(scenario, scenario.monte_carlo, tmp_path) == []
    batch = mcr.load(tmp_path)
    assert [row["run_length"] for row in batch.outcomes] == [pytest.approx(60.0 / 3600.0)] * 2  # [h]
    assert batch.outcome_units["sat-1.lowest_altitude"] == "km"


def test_a_steady_altitude_is_kept_as_the_lowest_and_the_highest(monkeypatch):
    """When the altitude does not vary, Overview shows one figure,
    "altitude"; the run keeps it as both its lowest and its highest
    altitude, so every run has the same keys. A run without a result keeps
    none, and one whose figures cannot be read keeps none (logged): the run
    itself succeeded."""
    from spacemissionstudio.engine import monte_carlo, run_summary
    from spacemissionstudio.engine.run_summary import Figure

    figures = [Figure("run_length", "Run length", "h", 2.0, 2), Figure("sat-1.altitude", "Altitude", "km", 500.0, 1)]
    monkeypatch.setattr(run_summary, "overview_figures", lambda result: figures)
    values, units = monte_carlo.run_outcomes(object())
    assert values == {"run_length": 2.0, "sat-1.lowest_altitude": 500.0, "sat-1.highest_altitude": 500.0}
    assert units == {"run_length": "h", "sat-1.lowest_altitude": "km", "sat-1.highest_altitude": "km"}
    assert monte_carlo._outcomes_or_none(None) == ({}, {})

    def broken(result):
        raise ValueError("no figures")

    monkeypatch.setattr(run_summary, "overview_figures", broken)
    assert monte_carlo._outcomes_or_none(object()) == ({}, {})


def _second_run_crashes(monkeypatch):
    """Makes the batch's second run raise: thread_count 1 runs each case in
    this process, so the execution function is this module's."""
    from spacemissionstudio.engine import monte_carlo

    real = monte_carlo._execute_sim
    calls = []

    def execute(sim, allow_scripts=False):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("forced crash of the second run")
        return real(sim, allow_scripts=allow_scripts)

    monkeypatch.setattr(monte_carlo, "_execute_sim", execute)


def test_a_crashed_run_keeps_what_it_drew(tmp_path, monkeypatch):
    """A4: a crashed run's draws are read from its run<N>.json (JSON, not
    the pickles) and kept as failed_drawn; the Runs table lists it with its
    draws and the status "crashed", no outcomes; run_table's default is as
    before; and it counts as not meeting a requirement (decision MC-6)."""
    import json

    from spacemissionstudio.engine import monte_carlo_requirements as req
    from spacemissionstudio.engine import monte_carlo_results as mcr
    from spacemissionstudio.engine.monte_carlo import run_monte_carlo
    from spacemissionstudio.schema import MonteCarloRequirementConfig

    scenario = _template_25(duration_days=0.01)
    scenario.monte_carlo.requirements = [MonteCarloRequirementConfig(
        "R-ALT", "sat-1", "lowest_altitude", at_least=0.0, confidence=0.9, max_probability=0.5)]
    _second_run_crashes(monkeypatch)
    assert run_monte_carlo(scenario, scenario.monte_carlo, tmp_path) == [1]
    batch = mcr.load(tmp_path)
    assert batch.runs == [0] and batch.failed == [1] and list(batch.failed_drawn) == [1]
    params = json.loads((tmp_path / "run1.json").read_text())
    cd = float(next(value for key, value in params.items() if key.endswith("dragCoeff")))
    assert batch.failed_drawn[1]["sat-1 drag coefficient [-]"] == pytest.approx(cd)
    assert set(batch.failed_drawn[1]) == set(batch.drawn[0])

    default_labels, default_rows = mcr.run_table(batch)
    assert [row[0] for row in default_rows] == [0.0] and mcr.STATUS_LABEL not in default_labels
    labels, rows = mcr.run_table(batch, outcomes=True)
    assert [row[0] for row in rows] == [0.0, 1.0]
    status = labels.index(mcr.STATUS_LABEL)
    assert [row[status] for row in rows] == ["succeeded", "crashed"]
    crashed = rows[1]
    assert crashed[labels.index("sat-1 drag coefficient [-]")] == pytest.approx(cd)
    assert all(math.isnan(crashed[labels.index(label)]) for label in labels
               if label.endswith(("offset [km]", "altitude [km]")))

    (result,) = req.evaluate(batch)
    assert (result.evaluated, result.not_met, result.crashed) == (2, 1, 1)
    assert result.verdict == req.NOT_SHOWN  # bound(1 of 2 at 90 %) = 0.95 > 0.5


def test_a_cancelled_batch_does_not_show_its_unfinished_cases_as_crashed(tmp_path):
    """A cancelled batch's unfinished cases did not fail (A4): its summary,
    written by the GUI's summary child, has no failed runs and no draws of
    crashed runs."""
    from spacemissionstudio.engine import monte_carlo_results as mcr
    from spacemissionstudio.engine.monte_carlo import run_monte_carlo
    from spacemissionstudio.gui import monte_carlo_process

    scenario = _short(_scenario(), num_runs=2)
    assert run_monte_carlo(scenario, scenario.monte_carlo, tmp_path) == []
    (tmp_path / "run1.data").unlink()  # as if case 1 had not finished when the batch was cancelled
    monte_carlo_process._summary_child(scenario, str(tmp_path), 2)
    batch = mcr.load(tmp_path)
    assert batch.runs == [0] and batch.failed == [] and batch.failed_drawn == {}


# -- One case again (Monte Carlo plan A3) -------------------------------------


def _position_at_kept_samples(result, name, time_s):
    """The run's position at the batch summary's kept samples (its times)."""
    import numpy as np

    series = result.series[f"{name}.position_N"]
    index = np.searchsorted(series.time_s, time_s)
    assert np.allclose(series.time_s[index], time_s, rtol=0.0, atol=1e-6)  # [s] the same samples
    return np.asarray(series.data)[index]


@pytest.mark.parametrize("thread_count", [1, 2])
def test_a_case_run_again_is_the_batchs_case(tmp_path, thread_count):
    """A3's acceptance: each case of a 2-run batch of template 25 (0.05
    days), run again from its run<N>.json, agrees with the batch summary's
    position at every kept sample to 1e-6 m and has the batch's outcomes,
    with one process and with two. Its provenance names the batch, the case
    and the batch's scenario hash, and its seeds are the case's."""
    import json

    import numpy as np

    from spacemissionstudio import output_provenance
    from spacemissionstudio.engine import monte_carlo
    from spacemissionstudio.engine import monte_carlo_results as mcr

    scenario = _template_25(thread_count=thread_count)
    assert monte_carlo.run_monte_carlo(scenario, scenario.monte_carlo, tmp_path) == []
    batch = mcr.load(tmp_path)
    assert batch.runs == [0, 1]
    for k, case in enumerate(batch.runs):
        result, summary = monte_carlo.replay_case(scenario, tmp_path, case)
        assert summary is None  # template 25 has no Mission Sequence
        position = _position_at_kept_samples(result, "sat-1", batch.time_s)
        assert np.max(np.abs(position - batch.positions["sat-1"][k])) <= 1e-6  # [m]
        values, units = monte_carlo.run_outcomes(result)
        assert set(values) == set(batch.outcomes[k])
        for key, value in values.items():
            assert value == pytest.approx(batch.outcomes[k][key], rel=1e-9, abs=1e-12), key
            assert units[key] == batch.outcome_units[key]
        record = result.provenance.monte_carlo_case
        params = json.loads((tmp_path / f"run{case}.json").read_text())
        assert record["case"] == case and record["archive_dir"] == str(tmp_path.resolve())
        assert record["scenario_sha256"] == output_provenance.scenario_sha256(scenario)
        assert record["rng_seeds"] == {key: int(value) for key, value in params.items() if key.endswith(".RNGSeed")}
        assert record["rng_seeds"] and result.provenance.rng_seed_note == monte_carlo.CASE_SEEDS_NOTE
        assert result.provenance.to_dict()["monte_carlo_case"] == record
    assert batch.positions["sat-1"][0, -1, 1] != batch.positions["sat-1"][1, -1, 1]  # two different cases


def test_a_case_flown_in_chunks_is_the_batchs_case_too(tmp_path):
    """The GUI's run worker flies a case in chunks (run_live, for its
    progress and Cancel): the same positions as the batch, to 1e-6 m."""
    import numpy as np

    from spacemissionstudio.engine import monte_carlo
    from spacemissionstudio.engine import monte_carlo_results as mcr

    scenario = _template_25()
    assert monte_carlo.run_monte_carlo(scenario, scenario.monte_carlo, tmp_path) == []
    batch = mcr.load(tmp_path)
    service, record = monte_carlo.prepare_case(scenario, tmp_path, 1)
    fractions = []
    result = monte_carlo.mark_case(service.run_live(lambda partial, fraction: fractions.append(fraction)), record)
    assert len(fractions) > 2 and fractions[-1] == 1.0
    position = _position_at_kept_samples(result, "sat-1", batch.time_s)
    assert np.max(np.abs(position - batch.positions["sat-1"][1])) <= 1e-6  # [m]
    assert result.provenance.monte_carlo_case["case"] == 1


def _batch_folder(tmp_path, scenario, digest=None, cases=(0,)):
    """A batch folder as run_monte_carlo leaves it, for the checks made
    before anything is built: archive.provenance.json and run<N>.json."""
    import json

    from spacemissionstudio import output_provenance

    record = {"scenario_sha256": output_provenance.scenario_sha256(scenario) if digest is None else digest,
              "scenario_file": "orbit_batch.json"}
    (tmp_path / "archive.provenance.json").write_text(json.dumps(record))
    for case in cases:
        (tmp_path / f"run{case}.json").write_text(json.dumps({"TaskList[0].TaskModels[0].RNGSeed": "7"}))
    return tmp_path


def test_a_case_of_a_changed_scenario_is_refused_with_both_hashes(tmp_path):
    """Decision MC-17 (the owner's answer to Q3, provisional): a case is not
    run again when the scenario changed since the batch. The message names
    the scenario's hash now and the batch's, says why, and says how to make
    it work: open the batch's own scenario (its file named)."""
    from spacemissionstudio import output_provenance
    from spacemissionstudio.engine.monte_carlo import MonteCarloCaseRefused, MonteCarloError, replay_case

    scenario = _short(_scenario(), num_runs=2)
    folder = _batch_folder(tmp_path, scenario)
    batch_digest = output_provenance.scenario_sha256(scenario)
    scenario.spacecraft[0].dry_mass_kg = 101.0  # [kg] edited since the batch
    with pytest.raises(MonteCarloCaseRefused) as refused:
        replay_case(scenario, folder, 0)
    message = str(refused.value)
    assert batch_digest in message and output_provenance.scenario_sha256(scenario) in message
    assert "the scenario changed since the batch" in message
    assert "Open the batch's own scenario (orbit_batch.json)" in message
    assert isinstance(refused.value, MonteCarloError)  # the CLI and the GUI catch it as the batch's errors


def test_a_case_the_batch_does_not_have_is_refused(tmp_path):
    """No run<N>.json (a cancelled batch's unstarted case), a case out of
    the batch's range, a folder without the batch's record, and script
    blocks without consent: each refused with what to do."""
    from spacemissionstudio.engine.monte_carlo import MonteCarloCaseRefused, MonteCarloError, replay_case

    scenario = _short(_scenario(), num_runs=2)
    folder = _batch_folder(tmp_path, scenario, cases=(0,))
    with pytest.raises(MonteCarloCaseRefused, match=r"has no run1\.json: case 1 did not start"):
        replay_case(scenario, folder, 1)
    with pytest.raises(MonteCarloCaseRefused, match="the batch has no case 2: its cases are 0 to 1"):
        replay_case(scenario, folder, 2)
    (folder / "archive.provenance.json").unlink()
    with pytest.raises(MonteCarloCaseRefused, match="has no archive.provenance.json"):
        replay_case(scenario, folder, 0)
    _batch_folder(tmp_path, scenario, digest="")
    with pytest.raises(MonteCarloCaseRefused, match="does not record the scenario's SHA-256"):
        replay_case(scenario, folder, 0)

    scripted = _short(_scenario(), num_runs=2)
    scripted.mission_sequence = [Command(kind="script_block", params={"code": "pass"})]
    with pytest.raises(MonteCarloError, match="explicit consent"):
        replay_case(scripted, _batch_folder(tmp_path, scripted), 0)


def test_a_crashed_case_run_again_raises_its_own_error(tmp_path, monkeypatch):
    """A3: a case that crashed in the batch raises its own error when it is
    run again; the other case runs. The crash is forced by the case's own
    draw: the drag coefficient case 1 drew (read from its run1.json, which
    the controller writes before the case runs)."""
    import json

    from spacemissionstudio.engine import monte_carlo
    from spacemissionstudio.engine import monte_carlo_results as mcr

    real = monte_carlo._fly

    def crashes_on_case_1s_draw(service, allow_scripts=False):
        path = tmp_path / "run1.json"
        if path.is_file():
            params = json.loads(path.read_text())
            drawn = float(next(value for key, value in params.items() if key.endswith("dragCoeff")))
            flown = service.spacecraft_handles["sat-1"].drag_effector.coreParams.dragCoeff
            if flown == drawn:
                raise RuntimeError(f"forced crash at drag coefficient {flown!r}")
        return real(service, allow_scripts)

    monkeypatch.setattr(monte_carlo, "_fly", crashes_on_case_1s_draw)
    scenario = _template_25(duration_days=0.01)
    assert monte_carlo.run_monte_carlo(scenario, scenario.monte_carlo, tmp_path) == [1]
    assert mcr.load(tmp_path).failed == [1]
    with pytest.raises(RuntimeError, match="forced crash at drag coefficient"):
        monte_carlo.replay_case(scenario, tmp_path, 1)
    result, _summary = monte_carlo.replay_case(scenario, tmp_path, 0)
    assert result.provenance.monte_carlo_case["case"] == 0


# -- The batch's data files in the workers and in a case run again (MC-19) ------


def _template_25_in_observed_days(**monte_carlo):
    """Template 25 (NRLMSISE-00, bundled space weather) at an epoch in the
    observed days of the shipped SW-All, so a different SW-All changes the
    drag of the run."""
    scenario = _template_25(**monte_carlo)
    scenario.epoch_utc = "2024-06-01T00:00:00"
    return scenario


def _newer_space_weather(scenario):
    """A downloaded SW-All.csv in the space-weather cache of this process
    (tests/conftest.py puts it in the test's tmp_path), as
    spaceweather.real_data_path("bundled") picks it: the shipped file's
    days from 2024, each one observed, so its last observed day is later
    than the shipped file's, with F10.7 30 sfu higher around the run."""
    import dataclasses
    from datetime import date, timedelta

    from spacemissionstudio.engine import spaceweather

    start = date.fromisoformat(scenario.epoch_utc[:10])
    shipped = spaceweather.load_celestrak(spaceweather.BUNDLED_DATA_PATH)
    days = {}
    for day, record in shipped.days.items():
        if day < date(2024, 1, 1) or record.kind == "monthly_forecast":
            continue
        if abs(day - start) <= timedelta(days=30):
            record = dataclasses.replace(record, f107_obs=record.f107_obs + 30.0,
                                         f107_center81=record.f107_center81 + 30.0)  # [sfu]
        days[day] = record
    path = spaceweather._write_basilisk_csv(days, spaceweather.DEFAULT_CACHE_DIR / "SW-All.csv")
    assert spaceweather.real_data_path("bundled") == path
    return path


def test_the_workers_resolve_reference_data_as_the_process_that_starts_the_batch(tmp_path):
    """Decision MC-19, the CI failure of PR #307: the worker processes of a
    batch (thread_count 2) import the engine again, so their data folders
    were computed from the HOME of the worker, not taken from the process
    that starts the batch. Here a newer SW-All sits only in the space-weather
    cache of this process (in the test's tmp_path, so no worker without the
    fix can see it, whatever the real HOME holds). Each case run again in
    this process must still agree with the batch to 1e-6 m."""
    import numpy as np

    from spacemissionstudio.engine import monte_carlo
    from spacemissionstudio.engine import monte_carlo_results as mcr

    scenario = _template_25_in_observed_days(thread_count=2, duration_days=0.02)
    newer = _newer_space_weather(scenario)
    batch_dir = tmp_path / "batch"
    assert monte_carlo.run_monte_carlo(scenario, scenario.monte_carlo, batch_dir) == []
    batch = mcr.load(batch_dir)
    assert batch.runs == [0, 1]
    for k, case in enumerate(batch.runs):
        result, _summary = monte_carlo.replay_case(scenario, batch_dir, case)
        position = _position_at_kept_samples(result, "sat-1", batch.time_s)
        assert np.max(np.abs(position - batch.positions["sat-1"][k])) <= 1e-6  # [m]
        assert batch.data_files[k]["space_weather"]["path"] == str(newer)


def test_the_data_folders_are_kept_and_given_back(tmp_path, monkeypatch):
    """The snapshot of the data folders (monte_carlo.data_folders) names each
    folder the engine reads reference data from, pickles with the creation
    function, and apply_data_folders sets them again; None changes nothing."""
    import functools
    import pickle

    from spacemissionstudio.engine import (earth_orientation, gaseous_attenuation, monte_carlo, small_bodies,
                                           spaceweather)

    settings = [(spaceweather, "DEFAULT_CACHE_DIR"), (earth_orientation, "DEFAULT_DIR"),
                (earth_orientation, "SYSTEM_DIR"), (small_bodies, "DEFAULT_DIR"), (small_bodies, "SYSTEM_DIR"),
                (gaseous_attenuation, "DEFAULT_DIR"), (gaseous_attenuation, "SYSTEM_DIR")]
    folders = monte_carlo.data_folders()
    assert folders == {f"{module.__name__.rpartition('.')[2]}.{name}": str(getattr(module, name))
                       for module, name in settings}
    creation = functools.partial(monte_carlo._create_sim, _scenario(), folders)
    assert pickle.loads(pickle.dumps(creation)).args[1] == folders
    for module, name in settings:
        monkeypatch.setattr(module, name, tmp_path / "elsewhere")
    monte_carlo.apply_data_folders(None)
    assert all(getattr(module, name) == tmp_path / "elsewhere" for module, name in settings)
    monte_carlo.apply_data_folders(folders)
    assert monte_carlo.data_folders() == folders
    assert all(isinstance(getattr(module, name), type(tmp_path)) for module, name in settings)


def test_the_refusal_names_each_data_file_that_is_not_the_batchs():
    """data_file_refusal (MC-19): "" when every file has the batch's
    SHA-256 (the paths may differ); else each changed, missing, added or
    left-out file by its kind, with its hashes, and what to do."""
    from spacemissionstudio.engine.monte_carlo import data_file_hashes, data_file_refusal

    then = data_file_hashes({"space_weather": {"path": "/a/SW-All.txt", "size_bytes": 3, "sha256": "1" * 64},
                             "earth_orientation:earth_latest_high_prec.bpc": {"path": "/a/e.bpc", "sha256": "2" * 64},
                             "gravity_field": {"path": "/a/GGM03S.txt", "sha256": "3" * 64}})
    assert then["space_weather"] == {"path": "/a/SW-All.txt", "sha256": "1" * 64}
    moved = {kind: dict(record, path="/b/" + record["path"][3:]) for kind, record in then.items()}
    assert data_file_refusal(then, moved, "/batch", 4) == ""
    now = dict(then, space_weather={"path": "/a/SW-All.csv", "sha256": "9" * 64},
               gravity_field={"path": "/a/GGM03S.txt"}, **{"spice:pck00011.tpc": {"path": "/a/p", "sha256": "4" * 64}})
    del now["earth_orientation:earth_latest_high_prec.bpc"]
    message = data_file_refusal(then, now, "/batch", 4)
    assert message.startswith("Case 4 was not run again: ")
    assert f"the space weather changed since the batch (a newer download, or another file): SHA-256 {'9' * 64} " \
           f"now, {'1' * 64} at the batch" in message
    assert f"the Earth orientation file earth_latest_high_prec.bpc is not used now and was used in the batch " \
           f"(SHA-256 {'2' * 64}" in message
    assert f"the gravity field is missing now (/a/GGM03S.txt; SHA-256 {'3' * 64} at the batch)" in message
    assert f"the SPICE kernel pck00011.tpc is used now (SHA-256 {'4' * 64}) and was not used in the batch" in message
    assert message.endswith("use the batch's data files (put them back, or roll back the download in Reference "
                            "data), or run the batch again.")


def test_a_case_whose_data_changed_since_the_batch_is_refused_with_both_hashes(tmp_path):
    """Decision MC-19: a case runs again only with the batch's data files.
    A newer SW-All downloaded after the batch would fly the case with other
    space weather: refused, with the kind of file, both SHA-256 and what to
    do. Without the newer file the case runs. A summary written before the
    batch kept its data files (no data_files key) is not refused for this."""
    import json

    from spacemissionstudio import dependencies
    from spacemissionstudio.engine import monte_carlo, spaceweather
    from spacemissionstudio.engine import monte_carlo_results as mcr

    scenario = _template_25_in_observed_days(duration_days=0.01)
    batch_dir = tmp_path / "batch"
    assert monte_carlo.run_monte_carlo(scenario, scenario.monte_carlo, batch_dir) == []
    batch = mcr.load(batch_dir)
    used = batch.data_files[0]["space_weather"]
    assert used["path"] == str(spaceweather.BUNDLED_DATA_PATH)
    assert used["sha256"] == dependencies.file_record(spaceweather.BUNDLED_DATA_PATH)["sha256"]
    assert mcr.case_data_files(batch_dir, 1) == batch.data_files[1]

    newer = _newer_space_weather(scenario)
    now = dependencies.file_record(newer)["sha256"]
    with pytest.raises(monte_carlo.MonteCarloCaseRefused) as refused:
        monte_carlo.replay_case(scenario, batch_dir, 0)
    message = str(refused.value)
    assert used["sha256"] in message and now in message
    assert "the space weather changed since the batch (a newer download" in message
    assert "use the batch's data files" in message and "run the batch again" in message

    summary = batch_dir / mcr.SUMMARY_JSON
    meta = json.loads(summary.read_text(encoding="utf-8"))
    del meta["data_files"]  # as a batch made before MC-19 wrote it
    summary.write_text(json.dumps(meta), encoding="utf-8")
    assert mcr.case_data_files(batch_dir, 0) is None
    result, _summary = monte_carlo.replay_case(scenario, batch_dir, 0)
    assert result.provenance.data_files["space_weather"]["path"] == str(newer)

    newer.unlink()
    summary.write_text(json.dumps(dict(meta, data_files=batch.data_files)), encoding="utf-8")
    result, _summary = monte_carlo.replay_case(scenario, batch_dir, 0)
    assert result.provenance.monte_carlo_case["case"] == 0


def test_the_case_check_imports_no_basilisk():
    """The window checks a case on the GUI thread before it clears the shown
    run (plan A3): ``engine.monte_carlo_case`` must not import Basilisk, a
    heavy first import (SRelD K-44)."""
    import subprocess
    import sys

    code = ("import sys; import spacemissionstudio.engine.monte_carlo_case as m; "
            "print(sorted(n for n in sys.modules if n.split('.')[0] == 'Basilisk'))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout
    assert out.strip() == "[]"


# -- The batch seed (Monte Carlo plan B1, decision MC-20; SRelD K-24) --------------------------


def _draws(archive_dir, runs=2) -> list[dict]:
    """Each run's run<N>.json: its drawn values and every model's RNG seed."""
    import json

    return [json.loads((archive_dir / f"run{run}.json").read_text()) for run in range(runs)]


def test_without_a_seed_the_creation_function_leaves_basilisks_seeding_alone():
    """No seed: the creation function draws nothing from NumPy's or Python's
    global generator and does not reseed them, so the Controller draws from
    the state its own seeding (the run index times 10) left: today's draws.
    With a seed, it reads the run index back from that state and reseeds
    both from the seed and the index (Basilisk 2.12.0's order: seed,
    create, disperse, Controller.py SimulationExecutor.__call__)."""
    import random

    import numpy as np

    from spacemissionstudio.engine import monte_carlo

    scenario = _template_25()
    np.random.seed(70)
    random.seed(70)
    numpy_state, python_state = np.random.get_state(), random.getstate()
    sim = monte_carlo._create_sim(scenario)
    after = np.random.get_state()
    assert after[2] == numpy_state[2] and np.array_equal(after[1], numpy_state[1])
    assert random.getstate() == python_state
    del sim
    np.random.seed(70)
    random.seed(70)
    assert monte_carlo.basilisk_run_index() == 7
    sim = monte_carlo._create_sim(scenario, seed=5)
    expected = monte_carlo._seed_words(5, 7)
    assert not np.array_equal(np.random.get_state()[1], numpy_state[1])
    probe = np.random.get_state()
    np.random.seed(expected)
    assert np.array_equal(np.random.get_state()[1], probe[1])
    del sim
    np.random.rand()  # a state already drawn from: its run index cannot be named
    with pytest.raises(monte_carlo.MonteCarloError, match="the run index is not known"):
        monte_carlo._reseed(5)


def test_a_batch_seed_gives_other_draws_and_the_same_draws_again(tmp_path):
    """B1's acceptance: two seeds give different draws, one seed gives the
    same draws twice (with one process and with two), and no seed gives the
    draws Basilisk's own seeding gives (a batch without a seed draws the
    same twice, and the golden files of templates 09 and 25 are unchanged).
    The summary keeps the seed (optional key ``seed``) and the batch's
    provenance records it (``monte_carlo_seed``) and says how the seeds
    were drawn."""
    import json

    import numpy as np

    from spacemissionstudio.engine import monte_carlo
    from spacemissionstudio.engine import monte_carlo_results as mcr

    def batch(folder, seed, thread_count=1):
        scenario = _template_25(duration_days=0.01, seed=seed, thread_count=thread_count)
        assert monte_carlo.run_monte_carlo(scenario, scenario.monte_carlo, tmp_path / folder) == []
        return _draws(tmp_path / folder)

    plain, plain_again = batch("plain", None), batch("plain_again", None)
    five, five_again, five_two = batch("five", 5), batch("five_again", 5), batch("five_two", 5, thread_count=2)
    six = batch("six", 6)
    assert plain == plain_again
    assert five == five_again == five_two
    for run in range(2):
        assert five[run] != plain[run] and five[run] != six[run]
        assert {key for key in five[run]} == {key for key in plain[run]}  # the same draws, other values
    assert five[0] != five[1]  # each run its own stream
    assert np.array_equal(mcr.load(tmp_path / "five").positions["sat-1"],
                          mcr.load(tmp_path / "five_two").positions["sat-1"])
    assert mcr.load(tmp_path / "five").seed == 5 and mcr.load(tmp_path / "plain").seed is None
    assert "seed" not in json.loads((tmp_path / "plain" / mcr.SUMMARY_JSON).read_text())
    record = json.loads((tmp_path / "five" / "archive.provenance.json").read_text(encoding="utf-8"))
    assert record["monte_carlo_seed"] == 5 and record["rng_seeds"] == monte_carlo.ARCHIVE_SEEDED_NOTE
    record = json.loads((tmp_path / "plain" / "archive.provenance.json").read_text(encoding="utf-8"))
    assert record["monte_carlo_seed"] is None and record["rng_seeds"] == monte_carlo.ARCHIVE_SEEDS_NOTE


def test_a_case_of_a_seeded_batch_runs_again_as_the_batch_ran(tmp_path):
    """Run This Case (A3) on a seeded batch: each case, run again from its
    run<N>.json, agrees with the batch summary's position at every kept
    sample to 1e-6 m and has the batch's outcomes; its provenance names the
    batch seed. The global generators are not reseeded for it (MC-18)."""
    import random

    import numpy as np

    from spacemissionstudio.engine import monte_carlo
    from spacemissionstudio.engine import monte_carlo_results as mcr

    scenario = _template_25(seed=2026)
    assert monte_carlo.run_monte_carlo(scenario, scenario.monte_carlo, tmp_path) == []
    batch = mcr.load(tmp_path)
    assert batch.runs == [0, 1] and batch.seed == 2026
    for k, case in enumerate(batch.runs):
        numpy_state, python_state = np.random.get_state(), random.getstate()
        result, _summary = monte_carlo.replay_case(scenario, tmp_path, case)
        assert np.array_equal(np.random.get_state()[1], numpy_state[1]) and random.getstate() == python_state
        position = _position_at_kept_samples(result, "sat-1", batch.time_s)
        assert np.max(np.abs(position - batch.positions["sat-1"][k])) <= 1e-6  # [m]
        values, _units = monte_carlo.run_outcomes(result)
        for key, value in values.items():
            assert value == pytest.approx(batch.outcomes[k][key], rel=1e-9, abs=1e-12), key
        assert result.provenance.monte_carlo_case["batch_seed"] == 2026
    other = _template_25(seed=2027)  # another seed is another scenario: its cases are not this batch's
    with pytest.raises(monte_carlo.MonteCarloCaseRefused, match="the scenario changed since the batch"):
        monte_carlo.replay_case(other, tmp_path, 0)
