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
"""Hand-calculated reference cases of the static power budget
(analyses.power_budget, SRS-F-31): System Budget Studio's cases 01 to 17
(its ``tests/regression/test_static_power.py``, decision D-040) with the
same inputs, the same expected numbers and the same tolerance, relative
1e-12 (double-precision arithmetic, no iteration).

The port's conventions (``docs/developer/system-budget-decisions.md``):
SBS's maturity classes m1 and m2 are the categories ``estimated`` and
``layout`` (B-05); its margin ratios are percent here (B-07: 0.10 is
10 %); modes and rows keep the file's order, not SBS's sorted ids (B-10,
case 15). Then the SBS example ``microsat_250kg_clean`` (its section is
``tests/data/budgets/sbs_microsat_250kg_clean.json``): its five mode
totals are pinned as SBS 2.15.1 computes them."""

from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest

import budgets_fixtures as fx
from spacemissionstudio.analyses.power_budget import (ModePower, effective_power_w, power_budget, source_power_w,
                                                      with_margin_w)
from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.budgets import (BudgetBusConfig, BudgetEquipmentConfig, BudgetModeConfig,
                                               BudgetPowerModeConfig, BudgetsConfig, PowerMarginConfig, SourcedValue)

REL = 1e-12
SRC = "hand calculation"
MATURITY = {"m1": "estimated", "m2": "layout"}  # SBS class -> S-120 category (B-05)

# item -> (subsystem, bus, SBS class, {mode: (average_w, peak_w, duty)})
ItemSpec = tuple[str, str, str, dict[str, tuple[float, float, float]]]


def s(value: float | None, source: str = SRC) -> SourcedValue:
    return SourcedValue(value, source)


def spacecraft(items: dict[str, ItemSpec], margins: dict[str, float | None] | None = None,
               system: float | None = 0.0, eta: dict[str, float | None] | None = None, loss: float | None = 0.0,
               modes: tuple[str, ...] = ("nominal",), settings: bool = True):
    """SBS's ``project()`` as a spacecraft with a ``budgets`` section:
    ``margins`` and ``system`` in percent; ``settings`` False is SBS's
    project without configuration files (no margins, efficiencies or
    loss). Validated as a scenario's spacecraft."""
    buses = list(dict.fromkeys(spec[1] for spec in items.values()))
    margins = margins if margins is not None else {"m1": 0.0, "m2": 0.0}
    eta = eta if eta is not None else {b: 1.0 for b in buses}
    equipment = [BudgetEquipmentConfig(name, subsystem=sub, bus=bus, maturity=MATURITY[cls], mass_kg=s(1.0),
                                       power_modes=[BudgetPowerModeConfig(m, s(a), s(p), d)
                                                    for m, (a, p, d) in power.items()])
                 for name, (sub, bus, cls, power) in items.items()]

    def pick(item: BudgetEquipmentConfig, mode: str) -> str:
        names = [m.name for m in item.power_modes]
        return mode if mode in names else names[0]

    section = BudgetsConfig(
        buses=[BudgetBusConfig(b, s(eta[b]) if settings else None) for b in buses],
        distribution_loss=s(loss) if settings else None,
        power_margins=[PowerMarginConfig(MATURITY[k], s(v)) for k, v in margins.items()] if settings else [],
        system_power_margin_percent=s(system) if settings else None,
        equipment=equipment,
        modes=[BudgetModeConfig(m, units={item.name: pick(item, m) for item in equipment}) for m in modes])
    sc = copy.deepcopy(load_scenario(fx.STARTER).spacecraft[0])
    sc.budgets = section
    sc.validate()
    return sc


def mode_result(sc, mode: str = "nominal") -> ModePower:
    return power_budget(sc).mode(mode)


def row(m: ModePower, name: str):  # noqa: ANN201 -- an ItemPower
    return next(r for r in m.rows if r.item == name)


# ---- scalar steps (cases 1-4) ----------------------------------------------------------------------------------

def test_case01_effective_power_is_avg_times_duty():
    assert effective_power_w(2.0, 0.5) == pytest.approx(1.0, rel=REL)
    assert effective_power_w(7.3, 0.0) == 0.0
    assert effective_power_w(7.3, 1.0) == pytest.approx(7.3, rel=REL)


def test_case02_margin_is_multiplicative():
    """SBS's ratios 0.2 and 0 are 20 % and 0 % (B-07)."""
    assert with_margin_w(10.0, 20.0) == pytest.approx(12.0, rel=REL)
    assert with_margin_w(10.0, 0.0) == pytest.approx(10.0, rel=REL)


def test_case03_source_power_divides_by_efficiency_and_distribution():
    assert source_power_w(9.0, 0.9, 0.0) == pytest.approx(10.0, rel=REL)
    assert source_power_w(9.0, 1.0, 0.1) == pytest.approx(10.0, rel=REL)  # 9 / 0.9
    assert source_power_w(5.0, 0.9, 0.02) == pytest.approx(5.0 / 0.882, rel=REL)


def test_case04_missing_inputs_give_none_not_zero():
    assert with_margin_w(10.0, None) is None
    assert source_power_w(9.0, None, 0.0) is None
    assert source_power_w(9.0, 0.9, None) is None
    assert effective_power_w(None, 1.0) is None and with_margin_w(None, 10.0) is None
    with pytest.raises(ValueError, match="efficiency must be in"):
        source_power_w(9.0, 0.0, 0.0)


# ---- full chain (cases 5-9) ------------------------------------------------------------------------------------

THREE = {
    "u1": ("A", "main", "m1", {"nominal": (2.0, 3.0, 0.5)}),
    "u2": ("B", "main", "m2", {"nominal": (4.0, 5.0, 1.0)}),
    "u3": ("A", "aux", "m1", {"nominal": (1.0, 1.5, 1.0)}),
}


@pytest.fixture
def three() -> ModePower:
    return mode_result(spacecraft(THREE, margins={"m1": 10.0, "m2": 20.0}, system=5.0, eta={"main": 0.9, "aux": 0.8},
                                  loss=0.02))


def test_case05_unit_rows(three):
    u1 = row(three, "u1")
    assert u1.effective_w == pytest.approx(1.0, rel=REL)
    assert u1.margin_percent == 10.0
    assert u1.margined_w == pytest.approx(1.1, rel=REL)
    assert row(three, "u2").margined_w == pytest.approx(4.0 * 1.2, rel=REL)


def test_case06_totals_with_unit_and_system_margin(three):
    t = three.average
    assert t.load_w == pytest.approx(1.0 + 4.0 + 1.0, rel=REL)
    assert t.unit_margined_w == pytest.approx(1.1 + 4.8 + 1.1, rel=REL)
    assert t.system_margined_w == pytest.approx((1.1 + 4.8 + 1.1) * 1.05, rel=REL)


def test_case07_bus_source_power(three):
    main = next(b for b in three.buses if b.bus == "main")
    aux = next(b for b in three.buses if b.bus == "aux")
    assert main.average.load_w == pytest.approx(5.0, rel=REL)
    assert main.average.source_w == pytest.approx(5.0 / (0.9 * 0.98), rel=REL)
    assert main.average.source_margined_w == pytest.approx((1.1 + 4.8) * 1.05 / (0.9 * 0.98), rel=REL)
    assert aux.average.source_w == pytest.approx(1.0 / (0.8 * 0.98), rel=REL)
    t = three.average
    assert t.source_w == pytest.approx(5.0 / (0.9 * 0.98) + 1.0 / (0.8 * 0.98), rel=REL)
    assert t.source_margined_w == pytest.approx((1.1 + 4.8) * 1.05 / (0.9 * 0.98) + 1.1 * 1.05 / (0.8 * 0.98),
                                                rel=REL)


def test_case08_peak_is_sum_of_unit_peaks_with_same_chain(three):
    p = three.peak
    assert p.load_w == pytest.approx(3.0 + 5.0 + 1.5, rel=REL)
    assert p.system_margined_w == pytest.approx((3.3 + 6.0 + 1.65) * 1.05, rel=REL)
    assert p.source_margined_w == pytest.approx((3.3 + 6.0) * 1.05 / (0.9 * 0.98) + 1.65 * 1.05 / (0.8 * 0.98),
                                                rel=REL)


def test_case09_subsystem_subtotals(three):
    a = next(x for x in three.subsystems if x.subsystem == "A")
    b = next(x for x in three.subsystems if x.subsystem == "B")
    assert a.effective_w == pytest.approx(1.0 + 1.0, rel=REL)
    assert a.margined_w == pytest.approx(1.1 + 1.1, rel=REL)
    assert b.peak_w == pytest.approx(5.0, rel=REL)
    assert [x.subsystem for x in three.subsystems] == ["A", "B"]


# ---- edge cases (cases 10-14) ----------------------------------------------------------------------------------

def test_case10_zero_duty_unit_contributes_nothing():
    m = mode_result(spacecraft({"u": ("A", "main", "m1", {"nominal": (50.0, 60.0, 0.0)})}))
    assert m.average.load_w == 0.0 and m.peak.load_w == 60.0  # the peak ignores the duty cycle (D-040)


def test_case11_placeholder_margin_gives_none_but_nominal_is_computed():
    m = mode_result(spacecraft(THREE, margins={"m1": None, "m2": 20.0}, system=5.0, eta={"main": 0.9, "aux": 0.8},
                               loss=0.02))
    assert row(m, "u1").margined_w is None
    assert row(m, "u2").margined_w == pytest.approx(4.8, rel=REL)
    assert m.average.load_w == pytest.approx(6.0, rel=REL)
    assert m.average.unit_margined_w is None and m.average.system_margined_w is None
    assert m.average.source_w == pytest.approx(5.0 / (0.9 * 0.98) + 1.0 / (0.8 * 0.98), rel=REL)


def test_case12_tbd_source_is_a_placeholder_even_with_a_value():
    sc = spacecraft(THREE, margins={"m1": 10.0, "m2": 20.0}, system=5.0, loss=0.02)
    sc.budgets.margin("estimated").percent = SourcedValue(10.0, "TBD")
    assert row(mode_result(sc), "u1").margin_percent is None


def test_case13_missing_settings_give_none_margins_and_sources():
    """SBS's project without its configuration files: no margins, no
    system margin, no efficiencies, no distribution loss."""
    m = mode_result(spacecraft(THREE, settings=False))
    assert m.average.load_w == pytest.approx(6.0, rel=REL)
    assert m.average.system_margined_w is None and m.average.source_w is None


def test_case14_unit_off_in_a_mode():
    items = {
        "a": ("A", "main", "m1", {"nominal": (2.0, 2.0, 1.0), "off": (0.0, 0.0, 1.0)}),
        "b": ("A", "main", "m1", {"nominal": (3.0, 3.0, 1.0), "off": (0.0, 0.0, 1.0)}),
    }
    result = power_budget(spacecraft(items, modes=("nominal", "off")))
    assert result.mode("nominal").average.load_w == pytest.approx(5.0, rel=REL)
    assert result.mode("off").average.load_w == 0.0


def test_case15_modes_and_rows_follow_the_file_order():
    """SBS sorts its modes and rows by id (["alpha", "nominal"]). The port
    keeps the file's order instead (decision B-10), so this case checks
    the file's order: "nominal" before "alpha", the items as listed."""
    result = power_budget(spacecraft(THREE, modes=("nominal", "alpha")))
    assert [m.mode for m in result.modes] == ["nominal", "alpha"]
    assert [r.item for r in result.modes[0].rows] == ["u1", "u2", "u3"]
    shuffled = spacecraft({k: THREE[k] for k in ("u3", "u1", "u2")}, modes=("alpha", "nominal"))
    assert [m.mode for m in power_budget(shuffled).modes] == ["alpha", "nominal"]
    assert [r.item for r in power_budget(shuffled).modes[0].rows] == ["u3", "u1", "u2"]
    assert [b.bus for b in power_budget(shuffled).modes[0].buses] == ["aux", "main"]  # first use


def test_case16_missing_inputs_become_findings_not_zero():
    """Only ``budget.placeholder`` findings (SBS: only RESULT_INCOMPLETE).
    Their texts name each missing input: the estimated (m1) margin, the
    system margin, the distribution loss, bus main's efficiency; not the
    layout (m2) margin or bus aux, which are given. The port names a field
    by its path ("system_power_margin_percent" for SBS's "system margin")."""
    sc = spacecraft(THREE, margins={"m1": None, "m2": 20.0}, system=None, eta={"main": None, "aux": 0.8}, loss=None)
    found = power_budget(sc).findings
    assert found and {f.rule_id for f in found} == {"budget.placeholder"}
    text = " ".join(found)
    for needle in ("estimated", "system_power_margin", "distribution", "main"):
        assert needle in text, needle
    assert "layout" not in text and "aux" not in text  # only what is actually missing
    assert all(f.startswith(f"{sc.name}: budgets.") for f in found)


def test_case17_result_is_deterministic():
    sc = spacecraft(THREE, margins={"m1": 10.0, "m2": 20.0}, system=5.0, loss=0.02)
    assert power_budget(sc) == power_budget(sc)


# ---- the SBS example microsat_250kg_clean ----------------------------------------------------------------------

#: mode -> (load, system-margined, source-margined) [W], as SBS 2.15.1 computes them (rounded to 6 decimals).
SBS_CLEAN_TOTALS = {
    "charging": (49.3, 58.553, 67.071019),
    "downlink": (135.1, 162.206, 185.802978),
    "imaging": (100.7, 124.487, 142.596793),
    "nominal": (52.3, 62.073, 71.103093),
    "safe": (31.85, 37.7685, 43.262887),
}


@pytest.fixture(scope="module")
def clean():
    return power_budget(fx.scenario(fx.sbs_clean_section()).spacecraft[0])


def test_the_sbs_clean_example_gives_its_five_mode_totals(clean):
    """Every mode's load, system-margined load and source power with
    margins; both buses have efficiency 0.9 and the loss is 0.03, so the
    source power is also the system-margined load / (0.9 * 0.97)."""
    assert [m.mode for m in clean.modes] == list(SBS_CLEAN_TOTALS)
    for name, (load, system, source) in SBS_CLEAN_TOTALS.items():
        total = clean.mode(name).average
        assert total.load_w == pytest.approx(load, rel=REL), name
        assert total.system_margined_w == pytest.approx(system, rel=REL), name
        assert total.source_margined_w == pytest.approx(source, abs=5e-7), name
        assert total.source_margined_w == pytest.approx(system / (0.9 * 0.97), rel=REL), name
    assert clean.complete and clean.findings == []


def test_the_sbs_clean_example_s_imaging_mode_by_bus_and_subsystem(clean):
    """SBS's pinned imaging values (its compare_microsat_250kg_eps.csv and
    the study's section 2.6): the two buses and the subsystems."""
    imaging = clean.mode("imaging")
    main, payload = (next(b for b in imaging.buses if b.bus == name) for name in ("main", "payload"))
    assert (main.average.load_w, main.average.system_margined_w) == (pytest.approx(55.7, rel=REL),
                                                                     pytest.approx(66.077, rel=REL))
    assert main.average.source_margined_w == pytest.approx(75.689576, abs=5e-7)
    assert payload.average.load_w == pytest.approx(45.0, rel=REL)
    assert payload.average.unit_margined_w == pytest.approx(53.1, rel=REL)
    assert payload.average.system_margined_w == pytest.approx(58.41, rel=REL)
    assert payload.average.source_margined_w == pytest.approx(66.907216, abs=5e-7)
    subsystems = {x.subsystem: (x.effective_w, x.margined_w) for x in imaging.subsystems}
    expected = {"ADCS": (24.7, 27.17), "DH": (21.0, 22.5), "EPS": (12.0, 12.6), "PL": (36.0, 43.2),
                "THERM": (1.0, 1.1), "TTC": (6.0, 6.6), "STRUCT": (0.0, 0.0)}
    assert list(subsystems) == ["STRUCT", "ADCS", "EPS", "PL", "THERM", "DH", "TTC"]  # first use (B-10)
    for name, (effective, margined) in expected.items():
        assert subsystems[name] == (pytest.approx(effective, rel=REL, abs=1e-15),
                                    pytest.approx(margined, rel=REL, abs=1e-15)), name
    assert row(imaging, "adcs").margined_w == pytest.approx(7.7, rel=REL)


def test_the_peak_totals_of_the_sbs_clean_example(clean):
    """The peaks as SBS computes them: every item at its peak, with its
    margin and the system margin, at the source."""
    peaks = {"charging": (105.3, 125.873, 144.184422), "downlink": (216.3, 260.018, 297.844215),
             "imaging": (207.3, 257.873, 295.387171), "nominal": (108.3, 129.393, 148.216495),
             "safe": (63.5, 75.845, 86.87858)}
    for name, (load, system, source) in peaks.items():
        peak = clean.mode(name).peak
        assert peak.load_w == pytest.approx(load, rel=REL), name
        assert peak.system_margined_w == pytest.approx(system, rel=REL), name
        assert peak.source_margined_w == pytest.approx(source, abs=5e-7), name


# ---- what the port adds: unknowns, the duty-cycle average, the export rows -------------------------------------

def test_an_item_a_mode_does_not_list_is_unknown_not_zero():
    """Decision B-09: the item's row has no power mode and no power, and
    the totals that need it are unknown; a finding names it."""
    sc = spacecraft(THREE, margins={"m1": 10.0, "m2": 20.0}, system=5.0, loss=0.02)
    del sc.budgets.modes[0].units["u2"]
    result = power_budget(sc)
    m = result.mode("nominal")
    assert row(m, "u2").power_mode == "" and row(m, "u2").effective_w is None
    assert m.average.load_w is None and m.peak.load_w is None
    aux = next(b for b in m.buses if b.bus == "aux")
    assert aux.average.load_w == pytest.approx(1.0, rel=REL)  # the other bus is still known
    assert [f.rule_id for f in result.findings] == ["budget.unit_not_in_mode"]
    assert "u2" in result.findings[0] and not result.complete


def test_an_item_without_power_modes_is_not_in_the_power_budget():
    """Decision B-16: a mass-only item has no row and needs no bus."""
    data = fx.section()
    result = power_budget(fx.scenario(data).spacecraft[0])
    assert all(r.item != "harness" for m in result.modes for r in m.rows)


def test_a_placeholder_power_makes_the_mode_unknown():
    sc = spacecraft(THREE, margins={"m1": 10.0, "m2": 20.0}, system=5.0, loss=0.02)
    sc.budgets.item("u3").power_modes[0].average_w = SourcedValue(1.0, "TBD")
    result = power_budget(sc)
    assert result.mode("nominal").average.load_w is None
    assert result.mode("nominal").peak.load_w == pytest.approx(9.5, rel=REL)  # the peak is given
    assert any(f.rule_id == "budget.placeholder" and "u3 (nominal)" in f for f in result.findings)


def test_the_duty_cycle_average_needs_duty_cycles_that_add_up_to_one():
    """As idm.power.duty_cycle_average: the time-weighted mean of the modes
    when every mode has a duty cycle and they add up to 1 within 1e-6."""
    sc = fx.scenario().spacecraft[0]
    result = power_budget(sc)
    nominal, imaging = result.mode("nominal").average, result.mode("imaging").average
    average = result.duty_cycle_average()
    assert average.load_w == pytest.approx(0.8 * nominal.load_w + 0.2 * imaging.load_w, rel=REL)
    assert average.source_margined_w == pytest.approx(0.8 * nominal.source_margined_w
                                                      + 0.2 * imaging.source_margined_w, rel=REL)
    sc.budgets.modes[1].duty_cycle = 0.3
    assert power_budget(sc).duty_cycle_average() is None
    assert [f.rule_id for f in power_budget(sc).findings].count("budget.mode_duty_sum") == 1


def test_the_design_note_s_example_by_hand():
    """The design note's OBC and a camera: nominal 4.0 W at 5 %, imaging
    4.0 + 6.0 W, with 10 % system margin, 0.9 efficiency and 2 % loss."""
    result = power_budget(fx.scenario().spacecraft[0])
    nominal, imaging = result.mode("nominal"), result.mode("imaging")
    assert nominal.average.load_w == pytest.approx(4.0, rel=REL)
    assert nominal.average.unit_margined_w == pytest.approx(4.0 * 1.05, rel=REL)
    assert nominal.average.source_margined_w == pytest.approx(4.0 * 1.05 * 1.1 / (0.9 * 0.98), rel=REL)
    assert imaging.average.load_w == pytest.approx(4.0 + 12.0 * 0.5, rel=REL)
    assert imaging.average.unit_margined_w == pytest.approx(4.0 * 1.05 + 6.0 * 1.2, rel=REL)
    assert imaging.peak.load_w == pytest.approx(5.5 + 15.0, rel=REL)


def test_the_export_rows():
    result = power_budget(fx.scenario().spacecraft[0])
    assert [(r["mode"], r["item"], r["power_mode"]) for r in result.rows()] == [
        ("nominal", "OBC", "on"), ("nominal", "camera", "off"), ("imaging", "OBC", "on"),
        ("imaging", "camera", "imaging")]
    totals = result.mode_rows()
    assert [r["mode"] for r in totals] == ["nominal", "imaging"] and totals[0]["load_w"] == pytest.approx(4.0)
    assert set(totals[0]) == {"mode", "duty_cycle", "load_w", "unit_margined_w", "system_margined_w", "source_w",
                              "source_margined_w", "peak_load_w", "peak_unit_margined_w", "peak_system_margined_w",
                              "peak_source_w", "peak_source_margined_w"}
    assert [(r["mode"], r["bus"]) for r in result.bus_rows()] == [("nominal", "main"), ("imaging", "main")]
    assert [(r["mode"], r["subsystem"]) for r in result.subsystem_rows()] == [
        ("nominal", "DHS"), ("nominal", "PL"), ("imaging", "DHS"), ("imaging", "PL")]
    assert [i.state for i in result.inputs] == ["given"] * 5


def test_no_section_is_an_empty_budget():
    sc = SimpleNamespace(name="x", budgets=None)
    assert power_budget(sc).modes == [] and power_budget(sc).findings == []
