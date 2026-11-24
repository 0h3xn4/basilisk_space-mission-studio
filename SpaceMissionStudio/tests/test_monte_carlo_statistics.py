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

"""A Monte Carlo batch's outcome statistics and sensitivity (Monte Carlo
plan B3 and B2, decisions MC-26 to MC-28): the rank correlation against
synthetic inputs and a case computed by hand, ties, pairs left out, the
percentiles against NumPy's, the empirical distribution, the choices a
batch keeps; and the trust check of plan B6 on the dispersions
(decision MC-29). Basilisk-free."""

import json
import math
from pathlib import Path

import numpy as np
import pytest

from spacemissionstudio.config import models, registry
from spacemissionstudio.config.registry import Configuration
from spacemissionstudio.engine import monte_carlo_results as mcr
from spacemissionstudio.engine import monte_carlo_statistics as mcs
from spacemissionstudio.engine import scenario_checks
from spacemissionstudio.schema import load_scenario

_TEMPLATES = Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates"
_R_M = 6778.0e3  # [m] orbit radius
_N_RAD_S = math.sqrt(3.986004415e14 / _R_M ** 3)  # [rad/s] mean motion


def _batch(drawn, outcomes=(), units=None, failed=()):
    """A synthetic orbit batch of len(drawn) runs: circular orbits run k
    ``1e-4 k`` rad ahead along track, drawing ``drawn[k]``, with
    ``outcomes[k]`` as its Overview figures."""
    runs = len(drawn)
    t = np.linspace(0.0, 3000.0, 10)  # [s]
    phase = np.arange(runs) * 1e-4  # [rad]
    u = _N_RAD_S * t[None, :] + phase[:, None]
    r = np.stack([_R_M * np.cos(u), _R_M * np.sin(u), np.zeros_like(u)], axis=-1)
    v = np.stack([-_R_M * _N_RAD_S * np.sin(u), _R_M * _N_RAD_S * np.cos(u), np.zeros_like(u)], axis=-1)
    return mcr.MonteCarloBatch("synthetic", "earth", t, list(range(runs)), list(failed), {"sat-1": r}, {"sat-1": v},
                               [dict(row) for row in drawn], "2030-01-01T00:00:00",
                               outcomes=[dict(row) for row in outcomes], outcome_units=dict(units or {}))


# -- the rank correlation (B2) ----------------------------------------------------------------------

def test_monotonic_and_unrelated_inputs_give_plus_one_minus_one_and_zero():
    """An outcome that grows with the drawn value (not on a straight line)
    gives +1, one that falls gives -1, one unrelated to it a value near 0
    (500 seeded draws: about 1/sqrt(499) = 0.045 is its spread)."""
    rng = np.random.default_rng(26)
    x = rng.normal(size=500)
    assert mcs.correlation(x, np.exp(x))[0] == pytest.approx(1.0, abs=1e-12)
    assert mcs.correlation(x, -x ** 3)[0] == pytest.approx(-1.0, abs=1e-12)
    unrelated, n = mcs.correlation(x, rng.normal(size=500))
    assert abs(unrelated) < 0.15 and n == 500


def test_a_small_case_equals_the_hand_computed_value():
    """x = 1..5 and y = (1, 2, 3, 4, 100): the ranks agree everywhere, so
    Spearman's correlation is 1; Pearson's is 200 / sqrt(10 * 7610) =
    20 / sqrt(761), worked out by hand (the means 3 and 22, the sums of
    products and squares 200, 10 and 7610). With y = (2, 1, 4, 3, 5):
    sum d^2 = 4, so 1 - 6 * 4 / (5 * 24) = 0.8."""
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    assert mcs.correlation(x, np.array([1.0, 2.0, 3.0, 4.0, 100.0]), "spearman") == (1.0, 5)
    value, n = mcs.correlation(x, np.array([1.0, 2.0, 3.0, 4.0, 100.0]), "pearson")
    assert value == pytest.approx(20.0 / math.sqrt(761.0), rel=1e-12) and n == 5
    assert mcs.correlation(x, np.array([2.0, 1.0, 4.0, 3.0, 5.0]), "spearman")[0] == pytest.approx(0.8, rel=1e-12)


def test_ties_get_their_mean_rank():
    """Tied values share the mean of their ranks; with ties, Spearman's
    correlation is Pearson's of those ranks: x = (1, 2, 2, 3) ranks
    (1, 2.5, 2.5, 4), y = (1, 3, 2, 4) ranks itself, and the correlation is
    4.5 / sqrt(4.5 * 5) = sqrt(0.9), by hand."""
    assert mcs.average_ranks(np.array([10.0, 20.0, 20.0, 30.0])).tolist() == [1.0, 2.5, 2.5, 4.0]
    assert mcs.average_ranks(np.array([30.0, 10.0, 30.0, 30.0])).tolist() == [3.0, 1.0, 3.0, 3.0]
    assert mcs.average_ranks(np.array([5.0, 5.0, 5.0])).tolist() == [2.0, 2.0, 2.0]
    value, _n = mcs.correlation(np.array([1.0, 2.0, 2.0, 3.0]), np.array([1.0, 3.0, 2.0, 4.0]))
    assert value == pytest.approx(math.sqrt(0.9), rel=1e-12)


def test_pearson_measures_a_straight_line_and_spearman_any_monotonic_one():
    """A straight line is +1 for both; a curve that only grows is +1 for
    the rank correlation and less for Pearson's."""
    x = np.linspace(1.0, 10.0, 50)
    assert mcs.correlation(x, 3.0 * x - 2.0, "pearson")[0] == pytest.approx(1.0, abs=1e-12)
    assert mcs.correlation(x, x ** 6, "spearman")[0] == pytest.approx(1.0, abs=1e-12)
    assert mcs.correlation(x, x ** 6, "pearson")[0] < 0.9
    with pytest.raises(ValueError, match="unknown sensitivity measure"):
        mcs.correlation(x, x, "kendall")


def test_runs_without_a_value_are_left_out_of_that_pair_only():
    """A NaN (a run without that outcome) leaves the run out of the pair
    that needs it, and N says how many runs the pair used; a column that
    does not vary, or fewer than 3 runs, gives no value (None), never NaN."""
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    assert mcs.correlation(x, np.array([1.0, np.nan, 3.0, 4.0, 5.0])) == (1.0, 4)
    assert mcs.correlation(x, np.full(5, 7.0)) == (None, 5)
    assert mcs.correlation(np.full(5, 2.2), x, "pearson") == (None, 5)
    assert mcs.correlation(x, np.array([1.0, 2.0, np.nan, np.nan, np.nan])) == (None, 2)


def test_the_table_is_sorted_by_size_and_pairs_without_a_value_come_last():
    """Every drawn value against every outcome, the largest correlation
    first whatever its sign; a column that does not vary last. The
    precomputed ranks of complete columns give what the pairwise path
    gives."""
    rng = np.random.default_rng(1)
    a = rng.normal(size=40)
    inputs = [mcs.Column("a [kg]", a), mcs.Column("constant [-]", np.full(40, 2.2))]
    falling = -a + 0.3 * rng.normal(size=40)
    outputs = [mcs.Column("weak [km]", 0.2 * a + rng.normal(size=40)), mcs.Column("falling [km]", falling),
               mcs.Column("gappy [h]", np.where(np.arange(40) % 5 == 0, np.nan, a ** 3))]
    rows = mcs.sensitivities(inputs, outputs)
    assert [(row.input_label, row.outcome_label) for row in rows[:3]] == [
        ("a [kg]", "gappy [h]"), ("a [kg]", "falling [km]"), ("a [kg]", "weak [km]")]
    assert rows[0].value == pytest.approx(1.0) and rows[0].n == 32 and rows[1].value < -0.8
    assert [row.value for row in rows[3:]] == [None, None, None]
    for row in rows:
        x = next(c for c in inputs if c.label == row.input_label).values
        y = next(c for c in outputs if c.label == row.outcome_label).values
        assert mcs.correlation(x, y) == pytest.approx((row.value, row.n)) if row.value is not None else \
            mcs.correlation(x, y)[0] is None


# -- the outcome statistics (B3) ---------------------------------------------------------------------

def test_the_percentiles_are_numpys_by_the_method():
    """Each model of monte_carlo.percentile_method gives
    numpy.percentile(values, percentiles, method=<its name>) over the
    finite values; the minimum, the maximum and N are those of the runs
    that recorded the outcome."""
    rng = np.random.default_rng(3)
    values = rng.lognormal(size=37)
    values[[4, 9]] = np.nan
    finite = values[np.isfinite(values)]
    for method in models.names(mcs.PERCENTILE_CHOICE):
        stat = mcs.outcome_statistics(mcs.Column("sat-1 lowest altitude [km]", values), (95, 1, 50, 5, 99, 50), method)
        assert stat.percentiles == (1.0, 5.0, 50.0, 95.0, 99.0)
        assert stat.values == pytest.approx(tuple(np.percentile(finite, [1, 5, 50, 95, 99], method=method)),
                                            rel=0, abs=0)
        assert (stat.n, stat.minimum, stat.maximum) == (35, finite.min(), finite.max())
        assert (stat.name, stat.unit) == ("sat-1 lowest altitude", "km")
    empty = mcs.outcome_statistics(mcs.Column("x [-]", np.full(3, np.nan)), (50,))
    assert (empty.n, empty.minimum, empty.values, empty.maximum) == (0, None, (None,), None)


def test_the_empirical_distribution_steps_up_to_one():
    """F(x) is the fraction of runs at or below x: it rises at each
    distinct value by its share of the runs (a tie counts twice) and its
    last value is exactly 1."""
    x, fraction = mcs.ecdf(np.array([3.0, 1.0, 2.0, 2.0, np.nan, 5.0]))
    assert x.tolist() == [1.0, 2.0, 3.0, 5.0]
    assert fraction.tolist() == pytest.approx([0.2, 0.6, 0.8, 1.0])
    assert fraction[-1] == 1.0
    rng = np.random.default_rng(7)
    assert mcs.ecdf(rng.normal(size=999))[1][-1] == 1.0
    assert [a.size for a in mcs.ecdf(np.array([np.nan]))] == [0, 0]


# -- a batch -----------------------------------------------------------------------------------------

def test_a_batchs_columns_are_its_draws_and_outcomes():
    """The inputs are the drawn values; the outcomes are where each run
    ended (the Runs table's offsets) and its Overview figures. A run that
    did not record a figure has NaN there; the crashed runs are not in the
    columns (they have no outcome)."""
    drawn = [{"sat-1 drag coefficient [-]": 2.0 + 0.1 * k, "sat-1 dry mass [kg]": 100.0} for k in range(6)]
    outcomes = [{"sat-1.lowest_altitude": 400.0 - k} for k in range(5)] + [{}]
    batch = _batch(drawn, outcomes, {"sat-1.lowest_altitude": "km"}, failed=[6])
    inputs = mcs.input_columns(batch)
    assert [c.label for c in inputs] == ["sat-1 drag coefficient [-]", "sat-1 dry mass [kg]"]
    outputs = mcs.outcome_columns(batch)
    assert [c.label for c in outputs] == ["sat-1 final radial offset [km]", "sat-1 final along-track offset [km]",
                                          "sat-1 final cross-track offset [km]", "sat-1 lowest altitude [km]"]
    labels, rows = mcr.run_table(batch)
    assert outputs[1].values == pytest.approx([row[labels.index("sat-1 final along-track offset [km]")]
                                               for row in rows], rel=0, abs=5e-7)  # to the millimetre
    assert outputs[0].values.tolist() == [0.0] * 6  # the radial offsets: rounding noise below 1 mm
    assert np.isnan(outputs[3].values[5]) and outputs[3].values[:5].tolist() == [400.0, 399.0, 398.0, 397.0, 396.0]
    found = mcs.insight(batch)
    first = found.sensitivity[0]
    assert {first.input_label, first.outcome_label} <= {"sat-1 drag coefficient [-]",
                                                        "sat-1 final along-track offset [km]",
                                                        "sat-1 lowest altitude [km]"}
    altitude = next(row for row in found.sensitivity if row.outcome_label == "sat-1 lowest altitude [km]"
                    and row.input_label.endswith("[-]"))
    assert (altitude.value, altitude.n) == (pytest.approx(-1.0), 5)
    assert all(row.value is None for row in found.sensitivity if row.input_label == "sat-1 dry mass [kg]")
    assert [s.n for s in found.statistics] == [6, 6, 6, 5]


def test_a_thermal_and_an_operations_batchs_outcomes():
    """A thermal batch's outcomes are each node's lowest and highest
    temperature; an operations batch's are its drawn "outcome: ..." values
    and each profile's lowest and highest value, and those are not inputs."""
    temperatures = np.array([[10.0, 20.0], [12.0, 25.0], [9.0, 30.0]])
    thermal = mcr.MonteCarloBatch("t", "earth", np.array([0.0, 1.0]), [0, 1, 2], [], {}, {},
                                  [{"absorptance": a} for a in (0.2, 0.3, 0.4)], kind="thermal",
                                  temperatures_c={"radiator": temperatures})
    assert [(c.label, c.values.tolist()) for c in mcs.outcome_columns(thermal)] == [
        ("radiator min [degC]", [10.0, 12.0, 9.0]), ("radiator max [degC]", [20.0, 25.0, 30.0])]
    assert mcs.insight(thermal).sensitivity[0].value == pytest.approx(1.0)  # max grows with the absorptance
    operations = mcr.MonteCarloBatch("o", "earth", np.array([0.0, 1.0]), [0, 1, 2], [], {}, {},
                                     [{"lost passes [-]": float(k), "outcome: data lost [Gbit]": 2.0 * k}
                                      for k in range(3)], kind="operations",
                                     profiles={"sat-1 memory": np.array([[1.0, 2.0], [0.5, 3.0], [0.0, 4.0]])},
                                     profile_units={"sat-1 memory": "Gbit"})
    assert [c.label for c in mcs.input_columns(operations)] == ["lost passes [-]"]
    assert [c.label for c in mcs.outcome_columns(operations)] == [
        "data lost [Gbit]", "sat-1 memory lowest [Gbit]", "sat-1 memory highest [Gbit]"]


def test_a_batch_reads_with_the_choices_it_was_run_with(tmp_path):
    """The three choices come from the scenario's project configuration
    (monte_carlo.sensitivity_measure, .percentile_method, .percentiles);
    the summary keeps them and the batch is read with them; a summary
    written before them reads with the defaults, and an unknown model or a
    percentile outside 0 to 100 is refused."""
    class _Scenario:
        configuration = Configuration({"monte_carlo.sensitivity_measure": "pearson",
                                       "monte_carlo.percentile_method": "linear",
                                       "monte_carlo.percentiles": [10, 90]})

    chosen = mcs.choices(_Scenario())
    assert chosen == {"sensitivity_measure": "pearson", "percentile_method": "linear", "percentiles": [10.0, 90.0]}
    assert mcs.choices() == {"sensitivity_measure": "spearman", "percentile_method": "linear",
                             "percentiles": [1.0, 5.0, 50.0, 95.0, 99.0]}
    assert registry.default(mcs.PERCENTILES) == (1.0, 5.0, 50.0, 95.0, 99.0)
    drawn = [{"sat-1 drag coefficient [-]": 2.0 + 0.1 * k} for k in range(4)]
    batch = _batch(drawn, [{"sat-1.lowest_altitude": 400.0 - k ** 3} for k in range(4)], {"sat-1.lowest_altitude": "km"})
    for key, value in chosen.items():
        setattr(batch, key, value)
    mcr.save(batch, tmp_path)
    loaded = mcr.load(tmp_path)
    assert (loaded.sensitivity_measure, loaded.percentile_method, loaded.percentiles) == ("pearson", "linear",
                                                                                          [10.0, 90.0])
    found = mcs.insight(loaded)
    assert found.percentiles == (10.0, 90.0) and found.measure == "pearson"
    altitude = next(row for row in found.sensitivity if row.outcome_label == "sat-1 lowest altitude [km]")
    assert -1.0 < altitude.value < -0.9  # Pearson's: a cubic, not a straight line
    meta = json.loads((tmp_path / mcr.SUMMARY_JSON).read_text(encoding="utf-8"))
    for key in ("sensitivity_measure", "percentile_method", "percentiles"):
        del meta[key]
    (tmp_path / mcr.SUMMARY_JSON).write_text(json.dumps(meta), encoding="utf-8")
    old = mcr.load(tmp_path)
    assert (old.sensitivity_measure, old.percentile_method, old.percentiles) == ("spearman", "linear",
                                                                                 [1.0, 5.0, 50.0, 95.0, 99.0])
    for key, value, message in (("sensitivity_measure", "kendall", "unknown sensitivity measure 'kendall'"),
                                ("percentile_method", "nearest", "unknown percentile method 'nearest'"),
                                ("percentiles", [5, 101], "percentiles is not a list")):
        (tmp_path / mcr.SUMMARY_JSON).write_text(json.dumps({**meta, key: value}), encoding="utf-8")
        with pytest.raises(mcr.MonteCarloResultsError, match=message):
            mcr.load(tmp_path)


def test_a_large_batch_is_worked_out_in_seconds_at_most():
    """100 000 runs, 4 drawn values and 6 outcomes (one with a run
    missing): the whole insight takes well under the time a worker is
    given (the GUI works it out off its thread, gui.monte_carlo_insight)."""
    import time

    rng = np.random.default_rng(5)
    runs = 100_000
    inputs = [mcs.Column(f"in {k} [-]", rng.normal(size=runs)) for k in range(4)]
    outputs = [mcs.Column(f"out {k} [km]", inputs[k % 4].values + rng.normal(size=runs)) for k in range(6)]
    outputs[0].values[17] = np.nan
    start = time.perf_counter()
    rows = mcs.sensitivities(inputs, outputs)
    stats = [mcs.outcome_statistics(column, (1, 5, 50, 95, 99)) for column in outputs]
    took = time.perf_counter() - start
    assert len(rows) == 24 and all(row.value is not None for row in rows) and stats[0].n == runs - 1
    assert took < 10.0, took


# -- the trust check of the dispersions (B6) -----------------------------------------------------------

def _findings(scenario) -> list[str]:
    return [w for w in scenario_checks.plausibility_warnings(scenario)
            if getattr(w, "rule_id", "") == "monte_carlo.nominal_outside"]


def test_a_dispersion_that_does_not_contain_the_spacecrafts_value_is_a_finding():
    """Template 09 draws the dry mass around 500 kg (normal); template 25 the
    drag coefficient from 2.2 to 3.0 (uniform). Each is a finding once the
    spacecraft's value is edited away from it, naming the field (the Problems
    panel takes the reader there), and none while Monte Carlo is off."""
    scenario = load_scenario(next(_TEMPLATES.glob("09_*.json")))
    assert _findings(scenario) == []
    scenario.spacecraft[0].dry_mass_kg = 520.0
    (finding,) = _findings(scenario)
    assert finding.startswith("sat-1: dry_mass_kg 520 kg is not the mean 500 kg of its Monte Carlo dispersion")
    assert (finding.actual, finding.limit) == ("520 kg", "mean 500 kg")
    scenario.monte_carlo.enabled = False
    assert _findings(scenario) == []
    scenario = load_scenario(next(_TEMPLATES.glob("25_*.json")))
    assert _findings(scenario) == []  # 3.0 is on the upper bound: inside
    scenario.spacecraft[0].drag_coeff = 3.2
    (finding,) = _findings(scenario)
    assert finding.startswith("sat-1: drag_coeff 3.2 is outside its Monte Carlo dispersion's bounds 2.2 to 3")
    from spacemissionstudio.gui.problem_location import locate

    assert locate(finding, ["sat-1"]).path == "drag_coeff"


def test_the_srp_coefficient_and_a_normal_dispersions_bounds_are_checked_too():
    """A normal dispersion with bounds must contain the value in its bounds
    as well; the SRP coefficient is checked as the drag coefficient. The
    quantities spread around the spacecraft's own value are not checked."""
    from spacemissionstudio.schema.scenario import DispersionConfig

    scenario = load_scenario(next(_TEMPLATES.glob("25_*.json")))
    scenario.monte_carlo.dispersions.append(DispersionConfig("sat-1", "srp_coeff", "normal", bounds=[1.0, 1.2],
                                                             mean=1.3, std_deviation=0.05))
    (finding,) = _findings(scenario)
    assert "srp_coeff 1.3 is outside its Monte Carlo dispersion's bounds 1 to 1.2" in finding
    scenario.monte_carlo.dispersions[-1].bounds = None
    assert _findings(scenario) == []


def test_no_template_has_a_false_finding():
    """Every template, with Monte Carlo on as it is saved: no dispersion
    is reported against its spacecraft's value."""
    paths = sorted(_TEMPLATES.glob("[0-9][0-9]_*.json"))
    assert len(paths) == 42
    for path in paths:
        scenario = load_scenario(path)
        assert _findings(scenario) == [], path.name
        scenario.monte_carlo.enabled = True
        assert _findings(scenario) == [], path.name
