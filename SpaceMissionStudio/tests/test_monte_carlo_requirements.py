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

"""Requirements on a Monte Carlo batch's outcomes (Monte Carlo plan A2,
decisions MC-4 to MC-6): the exact one-sided Clopper-Pearson upper bound
on the probability of not meeting one, checked against its closed form and
against the bound's other form (the regularized incomplete beta function,
computed exactly in rational numbers); the counts with crashed runs and
runs that did not record the outcome; the summary's round trip; and the
outcome list kept in step with ``engine.run_summary`` (Basilisk-free)."""

import math
import re
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from spacemissionstudio.engine import monte_carlo_requirements as req
from spacemissionstudio.engine import monte_carlo_results as mcr
from spacemissionstudio.schema.scenario import (
    MONTE_CARLO_OUTCOME_TITLES,
    MONTE_CARLO_OUTCOME_UNITS,
    MONTE_CARLO_OUTCOMES,
    RUN_OUTCOMES,
)

_RUN_SUMMARY = Path(__file__).resolve().parents[1] / "spacemissionstudio" / "engine" / "run_summary.py"


# -- the bound ----------------------------------------------------------------------------------

@pytest.mark.parametrize("n", [1, 5, 20, 100, 1000])
@pytest.mark.parametrize("confidence", [0.5, 0.9, 0.95, 0.99])
def test_the_bound_for_no_failure_is_the_closed_form(n, confidence):
    """For k = 0 the binomial sum is (1 - p)^N, so the bound is
    1 - (1 - C)^(1/N); the bisection finds it (20 runs at 95 %: 0.139,
    the plan's risk R5)."""
    expected = 1.0 - (1.0 - confidence) ** (1.0 / n)
    assert req.clopper_pearson_upper(0, n, confidence) == pytest.approx(expected, rel=1e-12, abs=1e-15)
    assert req.clopper_pearson_upper(0, 20, 0.95) == pytest.approx(0.1391083, abs=1e-7)


def _beta_cdf_exact(x: Fraction, a: int, b: int) -> Fraction:
    """The regularized incomplete beta function I_x(a, b) for whole a, b >= 1,
    exactly: the integral of t^(a-1) (1 - t)^(b-1) from 0 to x, with
    (1 - t)^(b-1) expanded by the binomial theorem and each power
    integrated, over B(a, b) = (a-1)! (b-1)! / (a+b-1)!. A method other than
    the code's (which sums the binomial terms by bisection in floats)."""
    integral = sum(Fraction(math.comb(b - 1, j) * (-1) ** j) * x ** (a + j) / (a + j) for j in range(b))
    beta = Fraction(math.factorial(a - 1) * math.factorial(b - 1), math.factorial(a + b - 1))
    return integral / beta


@pytest.mark.parametrize("k, n, confidence", [(0, 20, 0.95), (1, 20, 0.95), (2, 10, 0.9), (3, 50, 0.9),
                                              (5, 30, 0.99), (12, 40, 0.8), (7, 9, 0.5)])
def test_the_bound_agrees_with_the_beta_integral_computed_exactly(k, n, confidence):
    """Clopper and Pearson's upper limit is also the C quantile of the beta
    distribution Beta(k + 1, N - k): the incomplete beta function at the
    bound, I_p(k + 1, N - k), is C. Computed exactly (rational numbers) at
    the float the code returns, it is C to 1e-10."""
    bound = req.clopper_pearson_upper(k, n, confidence)
    assert 0.0 < bound < 1.0
    assert float(_beta_cdf_exact(Fraction(bound), k + 1, n - k)) == pytest.approx(confidence, abs=1e-10)


@pytest.mark.parametrize("k, n, p", [(0, 20, 0.1), (3, 20, 0.05), (3, 20, 0.5), (10, 50, 0.1), (10, 50, 0.4),
                                     (49, 50, 0.99), (60, 200, 0.2), (5, 200, 0.6)])
def test_the_binomial_sum_is_the_exact_one(k, n, p):
    """The sum the bisection works on, against the same sum in rational
    numbers: from both sides of the binomial's mode, and far from it."""
    q = Fraction(p)
    exact = float(sum(math.comb(n, i) * q ** i * (1 - q) ** (n - i) for i in range(k + 1)))
    assert req.binomial_cdf(k, n, p) == pytest.approx(exact, rel=1e-11, abs=1e-300)


def test_the_bound_grows_with_failures_and_confidence():
    """More failures or more confidence give a higher bound; N failures
    of N give 1; the bound is never below the estimate k/N for C >= 0.5;
    a large batch is quick (no table, no SciPy)."""
    n = 50
    by_k = [req.clopper_pearson_upper(k, n, 0.95) for k in range(n + 1)]
    assert all(low < high for low, high in zip(by_k, by_k[1:]))
    assert by_k[-1] == 1.0 and all(bound >= k / n for k, bound in enumerate(by_k))
    by_c = [req.clopper_pearson_upper(3, n, c) for c in (0.5, 0.8, 0.9, 0.95, 0.99, 0.999)]
    assert all(low < high for low, high in zip(by_c, by_c[1:]))
    assert 0.0 < req.clopper_pearson_upper(5000, 100_000, 0.999) < 0.06
    with pytest.raises(ValueError, match="confidence"):
        req.clopper_pearson_upper(0, 10, 1.0)
    with pytest.raises(ValueError, match="0 <= k <= n"):
        req.clopper_pearson_upper(11, 10, 0.9)


# -- a batch judged ------------------------------------------------------------------------------

def _batch(lowest_km, failed=(), requirements=(), bound="clopper_pearson"):
    """A batch of len(lowest_km) successful runs (None: the run did not
    record its altitude) and the crashed runs ``failed``."""
    runs = list(range(len(lowest_km)))
    t = np.linspace(0.0, 60.0, 3)  # [s]
    n_rad_s = math.sqrt(3.986004415e14 / 6778.0e3 ** 3)  # [rad/s] circular orbits, 0.1 mrad apart
    u = n_rad_s * t[None, :] + 1e-4 * np.arange(len(runs))[:, None]
    r = 6778.0e3 * np.stack([np.cos(u), np.sin(u), np.zeros_like(u)], axis=-1)  # [m]
    v = 6778.0e3 * n_rad_s * np.stack([-np.sin(u), np.cos(u), np.zeros_like(u)], axis=-1)  # [m/s]
    outcomes = [{"run_length": 1.0} | ({} if value is None else {"sat-1.lowest_altitude": value})
                for value in lowest_km]
    return mcr.MonteCarloBatch("synthetic", "earth", t, runs, list(failed), {"sat-1": r}, {"sat-1": v},
                               [{} for _ in runs], outcomes=outcomes,
                               outcome_units={"run_length": "h", "sat-1.lowest_altitude": "km"},
                               requirements=list(requirements), probability_bound=bound)


def _altitude(name="R-ALT", at_least=400.0, confidence=0.9, max_probability=None):
    return {"name": name, "spacecraft": "sat-1", "outcome": "lowest_altitude", "at_least": at_least,
            "at_most": None, "confidence": confidence, "max_probability": max_probability}


def test_a_crashed_run_counts_as_not_met_and_is_shown_apart():
    """Decision MC-6: a crashed run has no outcome and counts as not
    meeting every requirement, in N and in k, and the table says how many
    of the k crashed (owner's answer Q1, confirmed)."""
    batch = _batch([410.0, 395.0, 405.0, 420.0], failed=[4, 5], requirements=[_altitude()])
    (result,) = req.evaluate(batch)
    assert (result.evaluated, result.not_met, result.crashed, result.not_evaluated) == (6, 3, 2, 0)
    assert result.not_met_runs == (1, 4, 5)
    assert result.estimate == pytest.approx(0.5)
    assert result.upper_bound == pytest.approx(req.clopper_pearson_upper(3, 6, 0.9))
    assert result.verdict == ""  # no allowed probability: no verdict
    row = req.table_rows([result], several_spacecraft=False)[0]
    assert row[:7] == ("R-ALT", "Lowest altitude", "at least 400 km", "6", "3", "2", "0")
    assert row[-1] == "no allowed probability"


def test_a_run_without_the_outcome_is_not_evaluated():
    """A successful run that did not record the outcome is left out of N
    and counted on its own (risk R2: else the reader sees a too-small N)."""
    batch = _batch([410.0, None, 405.0], requirements=[_altitude(at_least=400.0)])
    (result,) = req.evaluate(batch)
    assert (result.evaluated, result.not_met, result.crashed, result.not_evaluated) == (2, 0, 0, 1)
    assert result.upper_bound == pytest.approx(1.0 - 0.1 ** 0.5)
    assert req.run_verdicts(batch) == {0: req.YES, 1: req.NOT_EVALUATED, 2: req.YES}


def test_the_verdict_against_the_allowed_probability():
    """Met when the upper bound is at or below the allowed probability,
    else not shown (the estimate alone is never enough); "at most" limits
    a value from above; with no run to judge, not shown."""
    passing = _batch([410.0] * 20, requirements=[_altitude(confidence=0.95, max_probability=0.15)])
    (met,) = req.evaluate(passing)
    assert met.estimate == 0.0 and met.upper_bound == pytest.approx(0.1391, abs=1e-4) and met.verdict == req.MET
    strict = _batch([410.0] * 20, requirements=[_altitude(confidence=0.95, max_probability=0.1)])
    assert req.evaluate(strict)[0].verdict == req.NOT_SHOWN
    assert [r.name for r in req.not_shown_met(req.evaluate(strict))] == ["R-ALT"]
    ceiling = dict(_altitude(name="R-LOW", at_least=None, max_probability=0.5), at_most=400.0)
    (below,) = req.evaluate(_batch([410.0, 390.0], requirements=[ceiling]))
    assert below.not_met_runs == (0,) and below.limit_text() == "at most 400 km"
    (empty,) = req.evaluate(_batch([None], requirements=[_altitude(max_probability=0.5)]))
    assert empty.evaluated == 0 and empty.upper_bound is None and empty.verdict == req.NOT_SHOWN


def test_each_runs_verdict_on_all_requirements():
    """The Runs table's "Meets all requirements": yes, no (one not met, or
    crashed) or not evaluated."""
    batch = _batch([410.0, 395.0, None], failed=[3], requirements=[_altitude(), _altitude("R-2", at_least=0.0)])
    assert req.run_verdicts(batch) == {0: req.YES, 1: req.NO, 2: req.NOT_EVALUATED, 3: req.NO}
    assert req.run_verdicts(_batch([410.0])) == {}  # no requirement: no column


def test_the_summary_keeps_the_requirements_and_reads_the_verdicts_again(tmp_path):
    """The summary keeps the outcomes, the crashed runs' draws, the
    requirements and the bound's model (optional keys of format 1); the
    verdicts read from a saved batch are those of the batch."""
    batch = _batch([410.0, 395.0], failed=[2], requirements=[_altitude(max_probability=0.5)])
    batch.failed_drawn = {2: {"sat-1 drag coefficient [-]": 2.4}}
    mcr.save(batch, tmp_path)
    loaded = mcr.load(tmp_path)
    assert loaded.outcomes == batch.outcomes and loaded.outcome_units == batch.outcome_units
    assert loaded.failed_drawn == {2: {"sat-1 drag coefficient [-]": 2.4}}
    assert loaded.requirements == batch.requirements and loaded.probability_bound == "clopper_pearson"
    assert req.evaluate(loaded) == req.evaluate(batch)


def test_a_batch_reads_its_bound_and_refuses_one_it_does_not_know(tmp_path):
    """The choice monte_carlo.probability_bound: each of its models is the
    bound a batch kept is judged with; a summary naming another is
    refused, and one written before the choice reads as Clopper-Pearson."""
    import json

    from spacemissionstudio.config import models

    for name in models.names(req.BOUND_CHOICE):
        batch = _batch([410.0, 395.0], requirements=[_altitude()], bound=name)
        mcr.save(batch, tmp_path)
        assert mcr.load(tmp_path).probability_bound == name
        assert req.evaluate(mcr.load(tmp_path))[0].upper_bound == pytest.approx(
            req.clopper_pearson_upper(1, 2, 0.9))
    meta = json.loads((tmp_path / mcr.SUMMARY_JSON).read_text(encoding="utf-8"))
    del meta["probability_bound"]
    (tmp_path / mcr.SUMMARY_JSON).write_text(json.dumps(meta), encoding="utf-8")
    assert mcr.load(tmp_path).probability_bound == "clopper_pearson"
    meta["probability_bound"] = "wald"
    (tmp_path / mcr.SUMMARY_JSON).write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(mcr.MonteCarloResultsError, match="unknown probability bound 'wald'"):
        mcr.load(tmp_path)


# -- the outcomes ----------------------------------------------------------------------------------

def test_the_outcomes_are_the_run_summarys_figures():
    """schema.scenario.MONTE_CARLO_OUTCOMES, their titles and units are the
    figures engine.run_summary adds (read from its source), with
    "altitude" kept as the lowest and the highest altitude."""
    source = _RUN_SUMMARY.read_text(encoding="utf-8")
    found = {key: (title, unit) for key, title, unit in
             re.findall(r'add\((?:sc|""), "(\w+)", "([^"]+)", "([^"]+)"', source)}
    for key, title, _value, _word in re.findall(r'\("(\w+_altitude)", "([^"]+)", (\w+), "(\w+)"\)', source):
        found[key] = (title, "km")  # the loop of orbit_figures: add(sc, key, label, "km", ...)
    assert found.pop("altitude") == ("Altitude", "km")
    assert set(found) == set(MONTE_CARLO_OUTCOMES)
    for key, (title, unit) in found.items():
        assert MONTE_CARLO_OUTCOME_UNITS[key] == unit and MONTE_CARLO_OUTCOME_TITLES[key] == title, key
    assert RUN_OUTCOMES == ("run_length",) and 'add("", "run_length"' in source


def test_the_run_table_adds_outcomes_and_crashed_runs_only_when_asked():
    """run_table's default is as before (the golden files read it); with
    outcomes=True it adds the outcomes, the crashed runs with their draws,
    a status and the verdict on all requirements."""
    batch = _batch([410.0, 395.0], failed=[2], requirements=[_altitude()])
    batch.drawn = [{"sat-1 drag coefficient [-]": 2.0}, {"sat-1 drag coefficient [-]": 2.2}]
    batch.failed_drawn = {2: {"sat-1 drag coefficient [-]": 2.4}}
    labels, rows = mcr.run_table(batch)
    assert labels == ["Run", "sat-1 drag coefficient [-]", "sat-1 final radial offset [km]",
                      "sat-1 final along-track offset [km]", "sat-1 final cross-track offset [km]"]
    assert [row[0] for row in rows] == [0.0, 1.0]
    labels, rows = mcr.run_table(batch, outcomes=True)
    assert labels[5:] == ["Run length [h]", "sat-1 lowest altitude [km]", mcr.STATUS_LABEL, mcr.MEETS_ALL_LABEL]
    assert [row[0] for row in rows] == [0.0, 1.0, 2.0]
    assert rows[2][1] == 2.4 and all(math.isnan(value) for value in rows[2][2:7])
    assert [row[-2:] for row in rows] == [["succeeded", "yes"], ["succeeded", "no"], ["crashed", "no"]]
    assert mcr.outcome_ranges(batch) == [("Run length", 1.0, 1.0, "h"), ("sat-1 lowest altitude", 395.0, 410.0, "km")]


# -- a thermal batch against its nodes' limits (Monte Carlo plan B4) ----------------------------

def _thermal_extremes():
    """Ten runs of two nodes with known extremes [degC]: the battery leaves
    its operating range [0, 30] in runs 2, 5 and 7 (above 30 or below 0)
    and its survival range [-10, 40] in run 7 only; the bus never leaves
    either. Runs are numbered 0 to 11, runs 3 and 9 failed."""
    runs = [0, 1, 2, 4, 5, 6, 7, 8, 10, 11]
    battery = {run: (10.0, 25.0) for run in runs}
    battery.update({2: (10.0, 30.5), 5: (-0.1, 20.0), 7: (-12.0, 41.0)})
    battery[4] = (0.0, 30.0)  # on the limits: inside (a run leaves a range only beyond it)
    limits = {"battery": {"operating": [0.0, 30.0], "survival": [-10.0, 40.0]},
              "bus": {"operating": [-20.0, 50.0], "survival": None},
              "radiator": {"operating": None, "survival": None}}
    extremes = {"battery": [battery[run] for run in runs], "bus": [(5.0, 15.0)] * len(runs),
                "radiator": [(-80.0, 20.0)] * len(runs)}
    return limits, extremes, runs, [3, 9]


def test_a_thermal_batch_counts_the_runs_outside_each_node_range():
    """B4's acceptance: a synthetic batch with known exceedances gives the
    expected counts, the estimate k/N and the A2 bound at the confidence
    given. A failed run counts as leaving every range, shown apart (MC-23);
    a range not set is not judged; a run on a limit is inside."""
    limits, extremes, runs, failed = _thermal_extremes()
    results = req.node_limits(limits, extremes, runs, failed, 0.9)
    assert [(r.node, r.range) for r in results] == [("battery", "operating"), ("battery", "survival"),
                                                     ("bus", "operating")]
    operating, survival, bus = results
    assert (operating.evaluated, operating.outside, operating.failed) == (12, 5, 2)
    assert operating.outside_runs == (2, 3, 5, 7, 9)
    assert operating.estimate == pytest.approx(5 / 12)
    assert operating.upper_bound == req.clopper_pearson_upper(5, 12, 0.9)
    assert (survival.outside, survival.outside_runs) == (3, (3, 7, 9))
    assert survival.upper_bound == req.clopper_pearson_upper(3, 12, 0.9)
    assert (bus.outside, bus.outside_runs, bus.estimate) == (2, (3, 9), pytest.approx(2 / 12))
    assert (operating.low_c, operating.high_c, operating.confidence) == (0.0, 30.0, 0.9)
    rows = req.node_limit_rows(results)
    assert rows[0] == ("battery", "operating", "0", "30", "12", "5", "2", f"{5 / 12:.4g}",
                       f"{req.clopper_pearson_upper(5, 12, 0.9):.4g}", "0.9")
    assert len(req.NODE_LIMITS_HEADER) == len(rows[0])


def test_without_a_confidence_the_node_limits_give_counts_and_the_estimate_only():
    """No confidence in the thermal Monte Carlo: no bound (no default, as a
    requirement's, MC-13); the counts and the estimate are the same."""
    limits, extremes, runs, _failed = _thermal_extremes()
    results = req.node_limits(limits, extremes, runs, [], None)
    assert all(r.upper_bound is None and r.confidence is None for r in results)
    assert (results[0].evaluated, results[0].outside, results[0].estimate) == (10, 3, pytest.approx(0.3))
    assert req.node_limit_rows(results)[0][-2:] == ("", "")


def test_the_node_limits_round_trip_through_the_thermal_summary(tmp_path):
    """The thermal summary keeps the node limits (optional key
    ``node_limits``, format 1 still) and reads them back; a thermal summary
    without them (saved before B4) opens with none; a broken row is
    refused."""
    import json

    limits, extremes, runs, failed = _thermal_extremes()
    results = req.node_limits(limits, extremes, runs, failed, 0.95)
    t = np.linspace(0.0, 100.0, 5)
    batch = mcr.MonteCarloBatch("Thermal", "earth", t, runs, failed, {}, {}, [{} for _ in runs], kind="thermal",
                                temperatures_c={"battery": np.zeros((len(runs), t.size))}, case="hot",
                                node_limits=[r.to_dict() for r in results])
    mcr.save(batch, tmp_path / "a")
    meta = json.loads((tmp_path / "a" / mcr.SUMMARY_JSON).read_text())
    assert meta["format"] == 1 and meta["probability_bound"] == "clopper_pearson" and len(meta["node_limits"]) == 3
    loaded = mcr.load(tmp_path / "a")
    assert [req.NodeLimitResult.from_dict(row) for row in loaded.node_limits] == results
    mcr.save(mcr.MonteCarloBatch("Thermal", "earth", t, runs, failed, {}, {}, [{} for _ in runs], kind="thermal",
                                 temperatures_c={"battery": np.zeros((len(runs), t.size))}), tmp_path / "b")
    assert "node_limits" not in json.loads((tmp_path / "b" / mcr.SUMMARY_JSON).read_text())
    assert mcr.load(tmp_path / "b").node_limits == []
    meta["node_limits"][0].pop("outside")
    (tmp_path / "a" / mcr.SUMMARY_JSON).write_text(json.dumps(meta))
    with pytest.raises(mcr.MonteCarloResultsError, match="node_limits is not a table of node limits"):
        mcr.load(tmp_path / "a")
