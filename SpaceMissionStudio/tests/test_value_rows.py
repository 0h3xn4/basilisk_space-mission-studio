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
"""UI audit batch B5, the core's part: values as rows of (label, value,
unit) for the window to lay out as value sheets, not sentences of numbers
(UI-14), and the orbit figures of Results › Overview (UI-20). The text
forms the command line prints stay as they were. No Basilisk, no Qt."""

import ast
import math
import re
from pathlib import Path

import numpy as np
import pytest

from spacemissionstudio.constants import EARTH_EQUATORIAL_RADIUS_M, EARTH_GM_M3_S2
from spacemissionstudio.engine import control_gains, run_summary, scenario_explainer
from spacemissionstudio.engine.results import ResultSet, RunProvenance, TimeSeries
from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.scenario import GravityConfig, OrbitIC, Scenario, SpacecraftConfig

_PACKAGE = Path(__file__).resolve().parent.parent / "spacemissionstudio"
_TEMPLATES = _PACKAGE / "scenarios" / "templates"


def _numbers(rows) -> bool:
    """Every value is one number or one word: no sentence, no list."""
    return all("," not in value and ";" not in value for _label, value, _unit in rows)


# -- UI-14: control gains -------------------------------------------------------------------------

def test_the_default_gains_are_rows_with_units():
    """The gains applied when K and P are unticked, each a row with its
    unit; the sentence stays for whoever reads it."""
    inertia = [10.0, 0.0, 0.0, 0.0, 12.0, 0.0, 0.0, 0.0, 14.0]  # [kg*m^2]
    rows = control_gains.default_gains_rows(inertia)
    values = {label: (value, unit) for label, value, unit in rows}
    assert values["Attitude gain K"] == ("0.04667", "N*m")
    assert values["Rate gain P"] == ("0.4", "N*m*s")
    assert values["Integral feedback"] == ("off", "")
    assert values["Mean inertia"] == ("12", "kg*m^2")
    assert values["Reference inertia"] == ("900", "kg*m^2")
    assert _numbers(rows)
    assert control_gains.describe_default_gains(inertia).startswith("Unticked: K 0.04667, P 0.4, integral off.")


def test_without_an_inertia_the_rows_give_the_reference_gains():
    rows = control_gains.default_gains_rows(None)
    assert [label for label, _value, _unit in rows] == ["Attitude gain K", "Rate gain P", "Integral feedback"]
    assert rows[0][1:] == ("3.5", "N*m") and rows[1][1:] == ("30", "N*m*s")


# -- UI-14: the Overview's orbit tile -------------------------------------------------------------

def test_the_orbit_tile_comes_as_rows_too():
    """Template 01's tile "Classical 97.03 deg, 400 km alt" is a sentence of
    numbers; the rows give the kind, the inclination and the altitude. The
    tile's text is unchanged (the golden files hold it)."""
    scenario = load_scenario(_TEMPLATES / "01_two_body_circular_orbit.json")
    rows = scenario_explainer.orbit_rows(scenario)
    assert rows == [("Orbit", "Classical", ""), ("Inclination", "97.03", "deg"), ("Altitude", "400", "km")]
    tiles = {tile.label: tile.value for tile in scenario_explainer.explain(scenario).stat_tiles}
    assert tiles["Orbit"] == "Classical 97.03 deg, 400 km alt"


def test_the_orbit_rows_follow_the_orbit_and_its_body():
    moon = Scenario(name="moon", epoch_utc="2030-01-01T00:00:00", gravity=GravityConfig(central_body="moon"),
                    spacecraft=[SpacecraftConfig(name="lunar", orbit=OrbitIC(
                        type="classical_elements", semi_major_axis_km=1837.4, eccentricity=0.0,
                        inclination_deg=90.0, raan_deg=0.0, arg_periapsis_deg=0.0, true_anomaly_deg=0.0))])
    assert scenario_explainer.orbit_rows(moon)[2] == ("Altitude", "100", "km")
    sso = Scenario(name="sso", epoch_utc="2030-01-01T00:00:00",
                   gravity=GravityConfig(central_body="earth", central_body_degree=2),
                   spacecraft=[SpacecraftConfig(name="sat", orbit=OrbitIC(
                       type="classical_elements", semi_major_axis_km=6878.1366, eccentricity=0.0,
                       inclination_deg=97.40, raan_deg=0.0, arg_periapsis_deg=0.0, true_anomaly_deg=0.0))])
    assert scenario_explainer.orbit_rows(sso)[0] == ("Orbit", "SSO", "")
    cartesian = Scenario(name="c", epoch_utc="2030-01-01T00:00:00", spacecraft=[SpacecraftConfig(
        name="sat", orbit=OrbitIC(type="cartesian", position_km=[7000.0, 0.0, 0.0], velocity_km_s=[0.0, 7.5, 0.0]))])
    assert scenario_explainer.orbit_rows(cartesian) == [("Orbit", "Cartesian state", "")]
    two = load_scenario(_TEMPLATES / "05_formation_flying_phasing.json")
    assert scenario_explainer.orbit_rows(two) == []  # the spacecraft table has each orbit


@pytest.mark.parametrize("path", sorted(_TEMPLATES.glob("*.json")), ids=lambda p: p.stem)
def test_every_templates_orbit_rows_are_values_not_sentences(path):
    assert _numbers(scenario_explainer.orbit_rows(load_scenario(path)))


# -- UI-14: the IDM-CIC import preview ------------------------------------------------------------

def test_the_import_summary_gives_rows_and_findings(tmp_path):
    """The preview's facts as rows (mass in kg), its findings one per line;
    lines() for the command line is unchanged."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from idm_fixtures import write_idm

    from spacemissionstudio import idm, idm_import

    plan = idm_import.plan(idm.load(write_idm(tmp_path / "demosat.idm")))
    summary = plan.summary
    rows = {label: (value, unit) for label, value, unit in summary.rows()}
    assert rows["Model version"] == ("3.4.1.1", "")
    assert rows["Body element"] == ("Bus", "")
    assert rows["Parts"] == ("8", "") and rows["Point masses"] == ("3", "") and rows["Generated meshes"] == ("4", "")
    assert rows["Mass imported"] == ("38.7", "kg") and rows["Propellant"] == ("6", "kg")
    findings = summary.findings()
    assert any(f.startswith("Left out: element Ground jig") for f in findings)
    assert any(f.startswith("Approximated (1): Boolean operations") for f in findings)
    assert summary.lines()[4].startswith("  8 part(s), 3 point mass(es), 4 generated mesh(es); 38.7 kg imported")


# -- UI-20: Results › Overview's orbit figures ----------------------------------------------------

def _orbit_run(perigee_km: float, apogee_km: float, provenance=None) -> ResultSet:
    radius_km = EARTH_EQUATORIAL_RADIUS_M / 1e3  # [km]
    a_m = (perigee_km + apogee_km + 2.0 * radius_km) / 2.0 * 1e3  # [m]
    e = (apogee_km - perigee_km) * 1e3 / (2.0 * a_m)  # [-]
    period_s = 2.0 * math.pi * math.sqrt(a_m ** 3 / EARTH_GM_M3_S2)  # [s]
    t = np.linspace(0.0, 2.0 * period_s, 2001)  # [s]
    mean_anomaly = 2.0 * math.pi * t / period_s
    eccentric = mean_anomaly.copy()
    for _ in range(30):
        eccentric = mean_anomaly + e * np.sin(eccentric)
    r = a_m * (1.0 - e * np.cos(eccentric))  # [m]
    nu = 2.0 * np.arctan2(math.sqrt(1 + e) * np.sin(eccentric / 2), math.sqrt(1 - e) * np.cos(eccentric / 2))
    result = ResultSet("orbit", provenance=provenance)
    result.add(TimeSeries("sat.position_N", t, ("x", "y", "z"),
                          np.column_stack([r * np.cos(nu), r * np.sin(nu), 0 * t]), "m"))
    result.add(TimeSeries("sat.orbit_elements.semi_major_axis", t, ("semi_major_axis",), np.full(t.size, a_m), "m"))
    return result


def test_the_overview_adds_the_period_and_the_altitudes():
    """Template 01's run had one card, its length. The overview also gives
    the orbital period and the altitude, from the recorded orbit."""
    figures = run_summary.by_key(run_summary.overview_figures(_orbit_run(400.0, 400.0)))
    assert list(figures)[:3] == ["run_length", "sat.orbital_period", "sat.altitude"]
    assert figures["sat.orbital_period"].unit == "min"
    assert math.isclose(figures["sat.orbital_period"].value, 92.56, abs_tol=0.01)
    assert figures["sat.altitude"].label == "Altitude" and math.isclose(figures["sat.altitude"].value, 400.0,
                                                                            abs_tol=0.1)
    assert figures["sat.orbital_period"].trace is not None and figures["sat.altitude"].trace is not None
    # Compare, run --explain and the golden files read summarize(): it gains no figure.
    assert [figure.key for figure in run_summary.summarize(_orbit_run(400.0, 400.0))] == ["run_length"]


def test_an_elliptical_orbit_gives_the_lowest_and_highest_altitude():
    """At perigee and apogee: the lowest and highest distance over the run."""
    figures = run_summary.by_key(run_summary.overview_figures(_orbit_run(300.0, 1500.0)))
    assert "sat.altitude" not in figures
    assert figures["sat.lowest_altitude"].label == "Lowest altitude"
    assert math.isclose(figures["sat.lowest_altitude"].value, 300.0, abs_tol=0.5)
    assert math.isclose(figures["sat.highest_altitude"].value, 1500.0, abs_tol=0.5)


def test_the_altitude_is_above_the_runs_own_central_body():
    provenance = RunProvenance(spacemissionstudio_version="test", basilisk_version="test", run_started_utc="-",
                               integrator="rkf78", dynamics_task_rate_s=30.0, central_body="moon",
                               central_body_mu_m3_s2=4.9028e12)
    result = ResultSet("moon", provenance=provenance)
    t = np.linspace(0.0, 20000.0, 401)  # [s]
    result.add(TimeSeries("lunar.position_N", t, ("x", "y", "z"),
                          np.column_stack([np.full(t.size, 1837.4e3), 0 * t, 0 * t]), "m"))
    figures = run_summary.by_key(run_summary.overview_figures(result))
    assert math.isclose(figures["lunar.altitude"].value, 100.0, abs_tol=1e-6)


# -- UI-43: no repository path in the window's text -----------------------------------------------

_REPO_PATH = re.compile(r"docs/|HISTORY\.md|examples/|README\.md|[\w-]+/[\w./-]*\.md\b|\b\w+\.md\b")
_LOG_CALLS = {"debug", "info", "warning", "error", "exception", "log", "critical"}


def _shown_strings(path: Path):
    """The string constants of ``path`` that are not docstrings, not in a
    logging call and not a bare file name (a constant like "USER_MANUAL.md")."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skipped = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                skipped.add(id(first.value))
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _LOG_CALLS):
            skipped.update(id(sub) for sub in ast.walk(node))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skipped
                and not re.fullmatch(r"[\w.-]+", node.value)):
            yield node.lineno, node.value


def test_the_window_names_the_manual_not_a_file_of_the_repository():
    """UI-43: text the window shows named files of the source tree
    (docs/models/reentry.md, SpaceMissionStudio/README.md), which an
    installed app does not have; it names the user manual's section."""
    paths = sorted((_PACKAGE / "gui").rglob("*.py")) + [_PACKAGE / "network.py", _PACKAGE / "engine" / "kernels.py"]
    found = [f"{path.name}:{line}: {text[:80]!r}" for path in paths for line, text in _shown_strings(path)
             if _REPO_PATH.search(text)]
    assert found == []
