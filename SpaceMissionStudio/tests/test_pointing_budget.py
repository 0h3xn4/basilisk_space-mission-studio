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
"""The pointing error budget's computation (engine.pointing_budget;
``docs/developer/pointing-error-budget-design.md`` 3.2, decisions PE-4 to
PE-15, SRS-F-32): each row of the selection table with a case computed by
hand, the sum (means linearly, independent deviations root-sum-square,
correlated groups linearly), the probability factor and the margin, the
line-of-sight rule, the periodic window share, "TBD" carried through, the
one unit conversion, the scenario's sensors as contributors, the command
line and the API. No Basilisk, no Qt.

The hand values: ``k(0.95) = 1.959963985`` (two-sided normal);
``sqrt(-2 ln 0.05) = 2.447746831``; ``1 arcsec = pi / 648000 rad``."""

import csv
import io
import json
import math

import pytest

import budgets_fixtures as fx
from spacemissionstudio import api, cli
from spacemissionstudio.engine import pointing_budget as pb
from spacemissionstudio.schema.budgets import PointingContributorConfig, SourcedValue

K95 = 1.959963985  # [-] the two-sided standard-normal factor of 0.95
CONE95 = 2.447746831  # [-] sqrt(-2 ln(1 - 0.95))
ARCSEC = math.pi / 648000.0  # [rad]


def _contributor(name, behaviour="random", spread=None, mean=None, kind="performance", distribution="gaussian",
                 period_s=None, group=""):
    """An engine contributor; angles in arcsec here, radians inside."""
    return pb.Contributor(name, kind, behaviour, distribution,
                          {axis: pb.arcsec_to_rad(v) for axis, v in (mean or {}).items()},
                          {axis: pb.arcsec_to_rad(v) for axis, v in (spread or {}).items()}, period_s, group)


def _requirement(index="absolute", axis="x", limit=100.0, probability=0.95, kind="performance", window_s=None,
                 stability_s=None, interpretation="temporal"):
    return pb.Requirement("R", index, kind, axis, pb.arcsec_to_rad(limit), probability, interpretation, window_s,
                          stability_s)


def _arcsec(value):
    return pb.rad_to_arcsec(value)


# -- the selection table (design note 6: a hand case per row) --------------------------------------------------

# Window 50 s, period 100 s: r = 0.5. Mean share 1 / (pi 0.5) = 0.636619772; relative share
# sqrt(1 + 4 / pi^2) = 1.185447061; drift and reproducibility twice the mean share, 1.273239545.
_SELECTION_CASES = [
    ("bias", {"absolute": 1.0, "mean": 1.0, "relative": 0.0, "drift": 0.0, "reproducibility": 0.0}),
    ("random", {"absolute": 1.0, "mean": 0.0, "relative": 1.0, "drift": 0.0, "reproducibility": 0.0}),
    ("periodic", {"absolute": 1.0, "mean": 0.636619772, "relative": 1.185447061, "drift": 1.273239545,
                  "reproducibility": 1.273239545}),
    ("drift", {"absolute": 1.0, "mean": 1.0, "relative": 0.0, "drift": 1.0, "reproducibility": 1.0}),
    ("transient", {"absolute": 1.0, "mean": 1.0, "relative": 1.0, "drift": 0.0, "reproducibility": 0.0}),
]


@pytest.mark.parametrize(("behaviour", "index", "share"),
                         [(b, index, share) for b, shares in _SELECTION_CASES for index, share in shares.items()])
def test_each_behaviour_enters_each_index_by_the_table(behaviour, index, share):
    """A contributor of mean 2 and spread 6 arcsec (gaussian) about x: in
    an index it enters by share s, the value at 0.95 is
    s * (2 + 1.959963985 * 6) = s * 13.75978391 arcsec; an index it does
    not enter has no contributor."""
    contributor = _contributor("c", behaviour, spread={"x": 6.0}, mean={"x": 2.0}, period_s=100.0)
    result = pb.evaluate(_requirement(index, window_s=50.0), [contributor])
    if share == 0.0:
        assert result.terms == () and result.status == pb.NO_CONTRIBUTOR
        return
    (term,) = result.terms
    assert term.share == pytest.approx(share, rel=1e-6)
    assert _arcsec(result.value_rad) == pytest.approx(share * 13.75978391, rel=1e-6)
    assert result.status == pb.MET and term.rule == pb.RULES[behaviour]


def test_the_table_has_a_row_per_behaviour_and_a_column_per_index():
    from spacemissionstudio.schema.budgets import POINTING_BEHAVIOURS, POINTING_INDICES

    assert set(pb.SELECTION) == set(POINTING_BEHAVIOURS) == set(pb.RULES)
    assert all(set(row) == set(POINTING_INDICES) for row in pb.SELECTION.values())


# -- the sum ----------------------------------------------------------------------------------------------------

def _summed():
    """About x: A random (mean 1, spread 3), B bias (mean -4, spread 4), and
    the correlated group "thermal": C random (mean 0.5, spread 1) and D
    bias (spread 2)."""
    return [_contributor("A", "random", spread={"x": 3.0}, mean={"x": 1.0}),
            _contributor("B", "bias", spread={"x": 4.0}, mean={"x": -4.0}),
            _contributor("C", "random", spread={"x": 1.0}, mean={"x": 0.5}, group="thermal"),
            _contributor("D", "bias", spread={"x": 2.0}, group="thermal")]


def test_means_add_linearly_deviations_root_sum_square_and_a_group_linearly():
    """Absolute about x: mean 1 - 4 + 0.5 = -2.5; the group's deviation
    1 + 2 = 3; std sqrt(3^2 + 4^2 + 3^2) = sqrt(34) = 5.830951895; value
    2.5 + 1.959963985 * 5.830951895 = 13.92845571 arcsec."""
    result = pb.evaluate(_requirement("absolute"), _summed())
    (axis,) = result.sums
    assert _arcsec(axis.mean_rad) == pytest.approx(-2.5)
    assert _arcsec(axis.std_rad) == pytest.approx(math.sqrt(34.0))
    assert _arcsec(result.mean_rad) == pytest.approx(2.5)  # its size: the sign does not matter
    assert _arcsec(result.value_rad) == pytest.approx(13.92845571, rel=1e-8)


def test_without_the_group_the_same_deviations_add_root_sum_square():
    """The same four, independent: sqrt(9 + 16 + 1 + 4) = sqrt(30)."""
    independent = [pb.Contributor(c.name, c.kind, c.behaviour, c.distribution, c.mean_rad, c.spread_rad, c.period_s,
                                  "") for c in _summed()]
    result = pb.evaluate(_requirement("absolute"), independent)
    assert _arcsec(result.std_rad) == pytest.approx(math.sqrt(30.0))


def test_the_relative_index_takes_only_what_enters_it():
    """Relative about x: the random A and C only, C alone in its group:
    mean 1.5, std sqrt(3^2 + 1^2) = sqrt(10)."""
    result = pb.evaluate(_requirement("relative"), _summed())
    assert [t.contributor for t in result.terms] == ["A", "C"]
    assert _arcsec(result.mean_rad) == pytest.approx(1.5)
    assert _arcsec(result.std_rad) == pytest.approx(math.sqrt(10.0))


@pytest.mark.parametrize(("distribution", "spread"), [("gaussian", 1.0), ("uniform", math.sqrt(3.0)),
                                                       ("sinusoidal", math.sqrt(2.0))])
def test_a_spread_is_turned_into_its_standard_deviation(distribution, spread):
    """A 1-sigma; a half-width over sqrt(3); an amplitude over sqrt(2)."""
    result = pb.evaluate(_requirement(), [_contributor("c", spread={"x": spread}, distribution=distribution)])
    assert _arcsec(result.std_rad) == pytest.approx(1.0)


def test_only_contributors_of_the_requirement_s_kind_enter():
    """A knowledge requirement takes knowledge and "both" contributors, not
    performance ones."""
    contributors = [_contributor("p", spread={"x": 3.0}), _contributor("k", spread={"x": 5.0}, kind="knowledge"),
                    _contributor("b", spread={"x": 12.0}, kind="both")]
    result = pb.evaluate(_requirement(kind="knowledge"), contributors)
    assert [t.contributor for t in result.terms] == ["k", "b"]
    assert _arcsec(result.std_rad) == pytest.approx(13.0)


def test_the_interpretation_is_recorded_and_does_not_change_the_sum():
    """PE-14: temporal, ensemble and mixed give the same numbers."""
    values = {pb.evaluate(_requirement(interpretation=name), _summed()).value_rad
              for name in ("temporal", "ensemble", "mixed")}
    assert len(values) == 1
    assert pb.evaluate(_requirement(interpretation="ensemble"), _summed()).interpretation == "ensemble"


# -- the probability factor and the margin ---------------------------------------------------------------------

@pytest.mark.parametrize(("probability", "factor"), [(0.95, K95), (0.6826894921, 1.0), (0.9973002039, 3.0),
                                                     (0.5, 0.6744897502)])
def test_the_probability_factor_is_the_two_sided_normal_one(probability, factor):
    assert pb.probability_factor(probability) == pytest.approx(factor, rel=1e-8)


@pytest.mark.parametrize("probability", [0.0, 1.0, -0.1, 1.5])
def test_a_probability_outside_zero_to_one_is_refused(probability):
    with pytest.raises(ValueError, match="in \\(0, 1\\)"):
        pb.probability_factor(probability)
    with pytest.raises(ValueError, match="in \\(0, 1\\)"):
        pb.cone_factor(probability)


def test_the_margin_is_the_limit_minus_the_value_and_says_met_or_not():
    """Value 13.92845571 arcsec (above): limit 15 leaves 1.07154429 and is
    met; limit 13 is short by 0.92845571 and is not met."""
    met = pb.evaluate(_requirement(limit=15.0), _summed())
    assert _arcsec(met.margin_rad) == pytest.approx(1.07154429, rel=1e-7) and met.status == pb.MET
    short = pb.evaluate(_requirement(limit=13.0), _summed())
    assert _arcsec(short.margin_rad) == pytest.approx(-0.92845571, rel=1e-7) and short.status == pb.NOT_MET
    exact = pb.Requirement("R", "absolute", "performance", "x", met.value_rad, 0.95)
    assert pb.evaluate(exact, _summed()).margin_rad == 0.0
    assert pb.evaluate(exact, _summed()).status == pb.MET  # a margin of 0 is met


# -- the line of sight -----------------------------------------------------------------------------------------

def test_the_line_of_sight_value_comes_from_the_two_axes_across_it():
    """Line of sight along z: E has means 3 and 4 about x and y (length 5)
    and spreads 2 and 1, so the larger is 2; F about z only does not move
    the line of sight. At 0.95: 5 + 2 * 2.447746831 = 9.895493662 arcsec."""
    contributors = [_contributor("E", "bias", spread={"x": 2.0, "y": 1.0}, mean={"x": 3.0, "y": 4.0}),
                    _contributor("F", "random", spread={"z": 100.0})]
    result = pb.evaluate(_requirement(axis="line_of_sight", limit=10.0), contributors, "z")
    assert [s.axis for s in result.sums] == ["x", "y"]
    assert {t.contributor for t in result.terms} == {"E"}
    assert result.factor == pytest.approx(CONE95, rel=1e-9)
    assert _arcsec(result.mean_rad) == pytest.approx(5.0) and _arcsec(result.std_rad) == pytest.approx(2.0)
    assert _arcsec(result.value_rad) == pytest.approx(9.895493662, rel=1e-9) and result.status == pb.MET
    along_x = pb.evaluate(_requirement(axis="line_of_sight", limit=10.0), contributors, "x")
    assert [s.axis for s in along_x.sums] == ["y", "z"] and _arcsec(along_x.std_rad) == pytest.approx(100.0)


@pytest.mark.parametrize("probability", [0.5, 0.9, 0.95, 0.9973])
def test_the_cone_factor_holds_the_probability_of_a_circular_gaussian(probability):
    """With equal deviations and no mean the rule is exact: the radius
    c sigma holds 1 - exp(-c^2 / 2) of a circular Gaussian."""
    factor = pb.cone_factor(probability)
    assert 1.0 - math.exp(-factor * factor / 2.0) == pytest.approx(probability, rel=1e-12)


def test_the_line_of_sight_without_its_axis_is_tbd():
    result = pb.evaluate(_requirement(axis="line_of_sight"), [_contributor("c", spread={"x": 1.0})], "")
    assert result.value_rad is None and result.status == pb.TBD
    assert any("line of sight's body axis is not stated" in note for note in result.notes)


# -- the periodic window share (PE-7, PE-11, PE-12) -------------------------------------------------------------

@pytest.mark.parametrize(("ratio", "mean", "relative"), [
    (0.25, 1.0, None),  # pi / 4 < 1: the whole amplitude in the mean
    (0.5, 2.0 / math.pi, math.sqrt(1.0 + 4.0 / math.pi ** 2)),
    (1.0, 1.0 / math.pi, 1.0),
    (1.5, 1.0 / (1.5 * math.pi), 1.0 + 1.0 / (1.5 * math.pi)),
    (2.0, 1.0 / (2.0 * math.pi), 1.0),
])
def test_the_window_shares_of_a_sinusoid(ratio, mean, relative):
    assert pb.mean_share(ratio) == pytest.approx(mean, rel=1e-12)
    if relative is not None:
        assert pb.relative_share(ratio) == pytest.approx(relative, rel=1e-6)
    assert pb.periodic_share("drift", 100.0, 100.0 * ratio) == pytest.approx(2.0 * mean, rel=1e-12)
    assert pb.periodic_share("reproducibility", 100.0, 100.0 * ratio) == pytest.approx(2.0 * mean, rel=1e-12)
    assert pb.periodic_share("absolute", 100.0, 100.0 * ratio) == 1.0


@pytest.mark.parametrize("ratio", [0.05, 0.1, 0.25, 0.4, 0.75, 0.9])
def test_the_relative_share_is_the_largest_distance_from_the_window_mean(ratio):
    """Checked against a direct search: unit sinusoids over a window of
    ``ratio`` periods at 720 phases, sampled at 4001 instants."""
    width = 2.0 * math.pi * ratio
    largest = 0.0
    for k in range(720):
        start = 2.0 * math.pi * k / 720
        values = [math.sin(start + width * j / 4000) for j in range(4001)]
        mean = (math.cos(start) - math.cos(start + width)) / width
        largest = max(largest, max(abs(v - mean) for v in values))
    assert pb.relative_share(ratio) == pytest.approx(largest, rel=2e-4)
    assert pb.relative_share(ratio) <= math.pi * ratio + 1e-12  # never above its slope bound


def test_a_short_window_sees_little_of_a_slow_sinusoid():
    """Far below a period the relative share goes as pi r, and the mean of
    the window holds the whole amplitude."""
    assert pb.relative_share(0.001) == pytest.approx(math.pi * 0.001, rel=1e-5)
    assert pb.mean_share(0.001) == 1.0


def test_the_mean_share_never_falls_to_zero_at_whole_periods():
    """PE-11: the bound 1 / (pi r), not the exact |sin(pi r)| / (pi r)."""
    assert pb.mean_share(3.0) == pytest.approx(1.0 / (3.0 * math.pi))
    assert abs(math.sin(math.pi * 3.0)) / (3.0 * math.pi) < 1e-15


def test_a_periodic_contributor_in_a_relative_index_takes_the_stability_time():
    """Window 1000 s, stability 50 s, period 100 s: the relative share is
    that of r = 0.5, 1.185447061; without the stability time, r = 10."""
    contributor = _contributor("p", "periodic", spread={"x": 2.0}, distribution="sinusoidal", period_s=100.0)
    with_stability = pb.evaluate(_requirement("relative", window_s=1000.0, stability_s=50.0), [contributor])
    assert with_stability.terms[0].share == pytest.approx(1.185447061, rel=1e-6)
    assert _arcsec(with_stability.std_rad) == pytest.approx(1.185447061 * math.sqrt(2.0), rel=1e-6)
    window_only = pb.evaluate(_requirement("relative", window_s=1000.0), [contributor])
    assert window_only.terms[0].share == pytest.approx(1.0 + abs(math.sin(10.0 * math.pi)) / (10.0 * math.pi))


@pytest.mark.parametrize(("period", "window", "note"), [(None, 50.0, "the period of p is TBD"),
                                                         (100.0, None, "observation period of R is TBD")])
def test_a_periodic_share_without_its_period_or_window_is_tbd(period, window, note):
    contributor = _contributor("p", "periodic", spread={"x": 2.0}, period_s=period)
    result = pb.evaluate(_requirement("mean", window_s=window), [contributor])
    assert result.terms[0].share is None and result.value_rad is None and result.status == pb.TBD
    assert any(note in text for text in result.notes)
    assert pb.evaluate(_requirement("absolute"), [contributor]).status == pb.MET  # absolute needs neither


# -- "TBD" carried through (PE-8) -------------------------------------------------------------------------------

def test_a_placeholder_makes_the_indices_it_enters_tbd_and_no_other():
    """A placeholder spread about x: the absolute index about x is TBD,
    never zero; about y it is computed; the mean index, which this random
    contributor does not enter, is not touched."""
    contributors = [_contributor("known", spread={"x": 3.0, "y": 3.0}),
                    pb.Contributor("unknown", "performance", "random", "gaussian", {},
                                   {"x": None, "y": pb.arcsec_to_rad(4.0)})]
    about_x = pb.evaluate(_requirement(), contributors)
    assert about_x.std_rad is None and about_x.value_rad is None and about_x.margin_rad is None
    assert about_x.status == pb.TBD and "unknown: a value about x is TBD" in about_x.notes
    about_y = pb.evaluate(_requirement(axis="y"), contributors)
    assert _arcsec(about_y.std_rad) == pytest.approx(5.0) and about_y.status == pb.MET
    assert pb.evaluate(_requirement("mean"), contributors).status == pb.NO_CONTRIBUTOR


def test_a_placeholder_of_another_kind_does_not_reach_the_requirement():
    contributors = [_contributor("p", spread={"x": 3.0}),
                    pb.Contributor("k", "knowledge", "random", "gaussian", {}, {"x": None})]
    assert pb.evaluate(_requirement(), contributors).status == pb.MET


def test_a_tbd_probability_leaves_the_sum_and_makes_the_value_tbd():
    result = pb.evaluate(_requirement(probability=None), _summed())
    assert _arcsec(result.std_rad) == pytest.approx(math.sqrt(34.0))
    assert result.factor is None and result.value_rad is None and result.status == pb.TBD
    assert "the probability of R is TBD" in result.notes


def test_a_tbd_limit_leaves_the_value_and_makes_the_margin_tbd():
    result = pb.evaluate(_requirement(limit=None), _summed())
    assert _arcsec(result.value_rad) == pytest.approx(13.92845571, rel=1e-8)
    assert result.margin_rad is None and result.status == pb.TBD


def test_a_tbd_mean_makes_the_value_tbd_but_keeps_the_deviation():
    contributor = pb.Contributor("c", "performance", "bias", "gaussian", {"x": None}, {"x": pb.arcsec_to_rad(2.0)})
    result = pb.evaluate(_requirement(), [contributor])
    assert result.mean_rad is None and _arcsec(result.std_rad) == pytest.approx(2.0) and result.value_rad is None


# -- the unit conversion (one boundary) -------------------------------------------------------------------------

def test_arcsec_and_radians_convert_at_the_boundary():
    assert pb.ARCSEC_RAD == ARCSEC == pytest.approx(4.84813681109536e-06, rel=1e-15)
    assert pb.arcsec_to_rad(3600.0) == pytest.approx(math.radians(1.0), rel=1e-15)
    assert pb.rad_to_arcsec(math.radians(1.0)) == pytest.approx(3600.0, rel=1e-15)
    assert pb.rad_to_arcsec(pb.arcsec_to_rad(12.3456)) == pytest.approx(12.3456, rel=1e-15)
    assert pb.arcsec_to_rad(None) is None and pb.rad_to_arcsec(None) is None


def _section_with_pointing(pointing: dict, template=fx.STARTER, budgets=None):
    data = fx.section() if budgets is None else budgets
    data["pointing"] = pointing
    return fx.scenario(data, template)


_POINTING = {
    "line_of_sight": "z",
    "requirements": [
        {"name": "APE x", "limit_arcsec": fx.sourced(30.0, "mission requirement MR-12"),
         "probability": fx.sourced(0.95, "mission requirement MR-12")},
        {"name": "APE cone", "axis": "line_of_sight", "limit_arcsec": fx.sourced(60.0, "MR-13"),
         "probability": fx.sourced(0.95, "MR-13"), "modes": ["imaging"]},
    ],
    "contributors": [
        {"name": "star tracker", "kind": "both", "spread_arcsec": {a: fx.sourced(8.0) for a in "xyz"}},
        {"name": "misalignment", "behaviour": "bias", "mean_arcsec": {"x": fx.sourced(10.0, "alignment report")},
         "spread_arcsec": {"x": fx.sourced(6.0, "alignment report"), "y": fx.sourced(6.0, "alignment report")}},
    ],
}


def test_the_section_s_arcsec_are_turned_to_radians_once_and_back_for_the_rows():
    """The engine sees radians (30 arcsec = 30 pi / 648000 rad); the rows
    give arcsec again. APE x: mean 10, std sqrt(8^2 + 6^2) = 10, value
    10 + 1.959963985 * 10 = 29.59963985 arcsec, margin 0.40036015."""
    sc = _section_with_pointing(json.loads(json.dumps(_POINTING))).spacecraft[0]
    line_of_sight, requirements, contributors = pb.inputs(sc.budgets.pointing)
    assert line_of_sight == "z"
    assert requirements[0].limit_rad == pytest.approx(30.0 * ARCSEC, rel=1e-15)
    assert contributors[1].mean_rad == {"x": pytest.approx(10.0 * ARCSEC, rel=1e-15)}
    budget = pb.pointing_budget(sc)
    row = budget.rows()[0]
    assert row["limit_arcsec"] == pytest.approx(30.0, rel=1e-15)
    assert row["value_arcsec"] == pytest.approx(29.59963985, rel=1e-9)
    assert row["margin_arcsec"] == pytest.approx(0.40036015, rel=1e-7) and row["status"] == pb.MET
    cone = budget.rows()[1]  # x: mean 10, std 10; y: mean 0, std 10: 10 + 10 * 2.447746831
    assert cone["value_arcsec"] == pytest.approx(34.47746831, rel=1e-9) and cone["axis"] == "line_of_sight"
    assert budget.complete and budget.contributors == 2


def test_a_spacecraft_without_a_pointing_budget_has_an_empty_one():
    budget = pb.pointing_budget(fx.scenario().spacecraft[0])
    assert budget.results == [] and budget.complete


# -- the scenario's sensors (option B, PE-15) -------------------------------------------------------------------

def _sensor_spacecraft():
    """Template 32's spacecraft (st-1 at 5 arcsec, imu-1 at 1e-5 rad/s,
    css-1 without a noise) with three more: a star tracker and a sun sensor
    whose names name catalog products, at the products' values, a star
    tracker that names a product at another value, and a magnetometer."""
    data = fx.scenario_data(template=fx.MODEL_TEMPLATE)
    data["spacecraft"][0]["sensors"] += [
        {"kind": "star_tracker", "name": "ASTRO APS main", "params": {"noise_arcsec": 8.0}},
        {"kind": "coarse_sun_sensor", "name": "SS200 +x", "params": {"nHat_B": [1.0, 0.0, 0.0], "noise_std": 0.004}},
        {"kind": "star_tracker", "name": "ASTRO APS spare", "params": {"noise_arcsec": 6.0}},
        {"kind": "magnetometer", "name": "mtm-1", "params": {}},
    ]
    data["spacecraft"][0]["budgets"]["pointing"] = {
        "contributors": [{"name": "st-1 noise", "spread_arcsec": {"x": fx.sourced(1.0)}}]}
    from spacemissionstudio.schema.scenario import Scenario

    scenario = Scenario.from_dict(data)
    scenario.validate()
    return scenario.spacecraft[0]


def test_the_scenario_s_sensors_become_knowledge_contributors_with_their_sources():
    sc = _sensor_spacecraft()
    added = pb.sensor_contributors(sc, sc.budgets.pointing)
    by_sensor = {c.sensor: c for c in added}
    assert list(by_sensor) == ["st-1", "imu-1", "css-1", "ASTRO APS main", "SS200 +x", "ASTRO APS spare"]
    assert all(c.kind == "knowledge" and c.behaviour == "random" and c.distribution == "gaussian" for c in added)
    assert all(set(c.spread_arcsec) == {"x", "y", "z"} and not c.mean_arcsec for c in added)
    # The scenario's own value: its place in the scenario is the source.
    st = by_sensor["st-1"]
    assert st.name == "st-1 noise 2"  # "st-1 noise" was taken
    assert st.spread_arcsec["x"] == SourcedValue(5.0, f"scenario: {sc.name}.sensors[st-1].params.noise_arcsec")
    # The name names a catalog product and the value is the product's: the catalog is the source.
    aps = by_sensor["ASTRO APS main"].spread_arcsec["y"]
    assert aps.value == 8.0 and aps.source == ("catalog: Jena-Optronik ASTRO APS (Germany), "
                                               "https://www.jena-optronik.de/products/star-sensors/astro-aps.html")
    # A product's name at another value: the scenario's value, not the catalog's.
    assert by_sensor["ASTRO APS spare"].spread_arcsec["z"].source.startswith("scenario: ")
    # A sun sensor's output noise as an angle at 45 deg: 0.004 / sin(45 deg) = 0.005656854 rad = 1166.809946 arcsec.
    css = by_sensor["SS200 +x"].spread_arcsec["x"]
    assert css.value == pytest.approx(1166.809946, rel=1e-9) and not css.placeholder
    assert css.source.startswith("catalog: Hyperion Technologies SS200 (Netherlands), ") and "sin(45 deg)" in css.source
    # No noise in the scenario: TBD, never zero; a gyro's rate noise: TBD with the rate in the source.
    assert by_sensor["css-1"].spread_arcsec["x"].placeholder
    assert "noise_std is not given" in by_sensor["css-1"].spread_arcsec["x"].source
    gyro = by_sensor["imu-1"].spread_arcsec["x"]
    assert gyro.placeholder and gyro.value is None
    assert gyro.source.startswith("TBD: rate noise 1e-05 rad/s (scenario: ") and "between attitude fixes" in gyro.source


def test_a_sensor_already_in_the_list_is_not_added_again():
    sc = _sensor_spacecraft()
    pointing = sc.budgets.pointing
    pointing.contributors += pb.sensor_contributors(sc, pointing)
    assert pb.sensor_contributors(sc, pointing) == []
    sc.budgets.validate(sc.name, sc)  # what it added validates


def test_a_sensor_contributor_enters_a_knowledge_requirement():
    """Star tracker st-1 (5 arcsec) about x, alone: at 0.95 the value is
    1.959963985 * 5 = 9.799819925 arcsec."""
    sc = _sensor_spacecraft()
    st = next(c for c in pb.sensor_contributors(sc, sc.budgets.pointing) if c.sensor == "st-1")
    sc.budgets.pointing.contributors = [st]
    from spacemissionstudio.schema.budgets import PointingRequirementConfig

    sc.budgets.pointing.requirements = [PointingRequirementConfig(
        "AKE", SourcedValue(20.0, "MR-14"), SourcedValue(0.95, "MR-14"), kind="knowledge")]
    (row,) = pb.pointing_budget(sc).rows()
    assert row["value_arcsec"] == pytest.approx(9.799819925, rel=1e-9)
    assert pb.sensor_contributor(sc, sc.sensors[0]) is not None
    assert isinstance(st, PointingContributorConfig)


# -- the command line, the report and the API -------------------------------------------------------------------

def _pointing_file(tmp_path, pointing=None):
    data = fx.scenario_data()
    data["spacecraft"][0]["budgets"]["pointing"] = json.loads(json.dumps(_POINTING if pointing is None else pointing))
    path = tmp_path / "pointing.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_the_budgets_command_prints_the_pointing_budget(tmp_path, capsys):
    path = _pointing_file(tmp_path)
    assert cli.main(["budgets", str(path), "--pointing"]) == 0
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert lines[0] == "my-sat: pointing error budget, 2 requirement(s), 2 contributor(s)"
    assert lines[1] == "  line of sight along body z"
    assert lines[2].split() == ["Requirement", "Index", "Kind", "Axis", "Probability", "[-]", "Mean", "[arcsec]",
                                "Std", "[arcsec]", "Value", "[arcsec]", "Limit", "[arcsec]", "Margin", "[arcsec]",
                                "Status"]
    assert lines[3].split() == ["APE", "x", "absolute", "performance", "x", "0.95", "10", "10", "29.6", "30",
                                "0.4004", "met"]
    assert "line of sight" in lines[4] and lines[4].split()[-1] == "met"
    assert "    misalignment about x: share 1, mean 10 arcsec, std 6 arcsec (constant: enters absolute and mean; " \
           "no relative, drift or reproducibility)" in lines
    assert cli.main(["budgets", str(path)]) == 0  # without --pointing: the power budget, as before
    assert capsys.readouterr().out.startswith("my-sat: power budget, 2 system mode(s)")


def test_the_budgets_command_prints_the_pointing_budget_as_csv(tmp_path, capsys):
    assert cli.main(["budgets", str(_pointing_file(tmp_path)), "--pointing", "--csv"]) == 0
    text = capsys.readouterr().out
    results, terms = text.split("\n\n")
    rows = list(csv.DictReader(io.StringIO(results)))
    assert [r["requirement"] for r in rows] == ["APE x", "APE cone"]
    assert float(rows[0]["value_arcsec"]) == pytest.approx(29.59963985, rel=1e-9) and rows[0]["status"] == "met"
    term_rows = list(csv.DictReader(io.StringIO(terms)))
    assert {(r["requirement"], r["contributor"], r["axis"]) for r in term_rows} >= {
        ("APE x", "star tracker", "x"), ("APE x", "misalignment", "x"), ("APE cone", "misalignment", "y")}


def test_a_tbd_shows_as_tbd_on_the_command_line(tmp_path, capsys):
    pointing = json.loads(json.dumps(_POINTING))
    pointing["requirements"][0]["probability"] = fx.sourced(None, "TBD")
    assert cli.main(["budgets", str(_pointing_file(tmp_path, pointing)), "--pointing"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0].endswith("; incomplete (TBD below)")
    assert out.splitlines()[3].split()[5:] == ["TBD", "10", "10", "TBD", "30", "TBD", "TBD"]
    assert "    TBD: the probability of APE x is TBD" in out.splitlines()


def test_the_budgets_command_says_when_there_is_no_pointing_budget(tmp_path, capsys):
    path = tmp_path / "plain.json"
    path.write_text(json.dumps(fx.scenario_data()), encoding="utf-8")
    assert cli.main(["budgets", str(path), "--pointing"]) == 1
    assert "my-sat has no pointing budget (budgets.pointing;" in capsys.readouterr().err


def test_the_api_returns_the_pointing_budget(tmp_path):
    budget = api.pointing_budget(api.load(_pointing_file(tmp_path)))
    assert [r.requirement for r in budget.results] == ["APE x", "APE cone"]
    assert budget.term_rows()[0]["contributor"] == "star tracker"
    assert "pointing_budget" in api.__all__


def test_the_user_manual_s_pointing_example_is_valid(tmp_path, capsys):
    """docs/user-manual/budgets.md: its ``pointing`` example is a valid
    subsection, and the command prints a budget for it."""
    import re
    from pathlib import Path

    page = (Path(__file__).resolve().parents[1] / "docs" / "user-manual" / "budgets.md").read_text(encoding="utf-8")
    pointing = json.loads("{" + re.search(r"```json\n(\"pointing\".*?)```", page, re.S).group(1) + "}")["pointing"]
    path = _pointing_file(tmp_path, pointing)
    assert cli.main(["budgets", str(path), "--pointing"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("my-sat: pointing error budget, 1 requirement(s), 2 contributor(s)")
    assert "    st-1 noise about x: share 1, mean 0 arcsec, std 5 arcsec" not in out  # a knowledge contributor
    assert "    thermal distortion about x: share 1, mean 0 arcsec, std 2.828 arcsec" in out  # 4 / sqrt(2)
