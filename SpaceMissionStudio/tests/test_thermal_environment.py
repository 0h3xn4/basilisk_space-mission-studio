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
"""Incident environmental flux per facet (thermal.environment): the
plate-to-sphere view factor against direct numerical integration,
direct sunlight with distance and eclipse, Basilisk's albedo module run
stand-alone per facet normal, the orbit period, inclination and beta,
and the refusals."""

import math

import numpy as np
import pytest
import thermal_fixtures as fixtures

from spacemissionstudio.constants import ASTRONOMICAL_UNIT_M, EARTH_EQUATORIAL_RADIUS_M, SOLAR_FLUX_1AU_W_M2
from spacemissionstudio.thermal import environment
from spacemissionstudio.thermal.geometry import ThermalFacet


def _numerical_view_factor(cos_lambda: float, h: float, n: int = 1200) -> float:
    """``F = 1/pi * integral(cos(t1) cos(t2) / d^2 dA)`` over the sphere's
    surface the plate sees, on a fine latitude-longitude grid (unit
    sphere, plate at distance ``h`` on the +z axis, tilted by lambda)."""
    lam = math.acos(cos_lambda)
    normal = np.array([math.sin(lam), 0.0, -math.cos(lam)])  # lambda from nadir (-z)
    plate = np.array([0.0, 0.0, h])
    theta = (np.arange(n) + 0.5) * math.pi / n
    phi = (np.arange(2 * n) + 0.5) * math.pi / n
    th, ph = np.meshgrid(theta, phi, indexing="ij")
    pts = np.stack([np.sin(th) * np.cos(ph), np.sin(th) * np.sin(ph), np.cos(th)], axis=-1)
    area = np.sin(th) * (math.pi / n) ** 2
    d = pts - plate
    dist = np.linalg.norm(d, axis=-1)
    cos_plate = (d @ normal) / dist
    cos_sphere = -np.einsum("ijk,ijk->ij", pts, d) / dist
    seen = (cos_plate > 0) & (cos_sphere > 0)
    return float(np.sum(np.where(seen, cos_plate * cos_sphere / dist ** 2 * area, 0.0)) / math.pi)


@pytest.mark.parametrize("h", [1.08, 1.5, 3.0])
@pytest.mark.parametrize("lam_deg", [0.0, 30.0, 60.0, 80.0, 95.0, 110.0, 150.0])
def test_view_factor_matches_direct_integration(h, lam_deg):
    """The closed forms (full disk, partial, none) against integrating the
    definition over the sphere, within 0.5 % of the nadir value."""
    cos_l = math.cos(math.radians(lam_deg))
    closed = float(environment.plate_sphere_view_factor(np.array([cos_l]), np.array([h]))[0])
    assert closed == pytest.approx(_numerical_view_factor(cos_l, h), abs=5.0e-3 / h ** 2)


def test_view_factor_is_continuous_at_its_two_boundaries():
    h = 1.2
    for edge in (math.acos(1.0 / h), math.pi / 2 + math.asin(1.0 / h)):
        below, above = environment.plate_sphere_view_factor(np.cos([edge - 1e-7, edge + 1e-7]), np.full(2, h))
        assert below == pytest.approx(above, abs=1e-5)


def _facets():
    """Six faces of a 1 m cube, as the thermal geometry gives them."""
    normals = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
    names = ["+x", "-x", "+y", "-y", "+z", "-z"]
    return [ThermalFacet("cube", name, name, 1.0, np.array(n, float), 0.5 * np.array(n, float))
            for name, n in zip(names, normals, strict=True)]


def test_sunlight_per_facet_follows_the_cosine_the_distance_and_the_eclipse():
    """Inertially fixed cube, Sun along +x at 1 AU: +x gets S_1AU in
    sunlight and nothing in eclipse; the other faces nothing (but the parallax); at 0.98 AU
    the flux scales with 1/r^2."""
    run = fixtures.circular_run(orbits=1.0)
    env = environment.build(run, "sat", "earth", _facets())
    solar = env.solar()
    lit = env.illumination > 0.5
    assert solar[lit, 0] == pytest.approx(SOLAR_FLUX_1AU_W_M2, rel=1e-4)
    assert np.all(solar[~lit] == 0.0) and (~lit).any()
    # the Sun's direction from the spacecraft, 6900 km off the Earth's centre, leans by r/AU: < 0.1 W/m^2
    assert np.all(solar[:, 1:] == pytest.approx(0.0, abs=0.1))
    near = environment.build(fixtures.circular_run(orbits=0.2, sun_distance_m=0.98 * ASTRONOMICAL_UNIT_M),
                             "sat", "earth", _facets())
    assert near.solar(1414.0)[0, 0] == pytest.approx(1414.0 / 0.98 ** 2, rel=1e-4)


def test_planetary_infrared_on_a_nadir_cube():
    """Nadir-pointed cube: the +z face sees the whole Earth (F = 1/h^2 to
    the top of the atmosphere), -z sees nothing, the sides the partial
    form; the default OLR is the guideline's mean for a low inclination."""
    run = fixtures.circular_run(altitude_m=500.0e3, orbits=0.3, attitude="nadir")
    env = environment.build(run, "sat", "earth", _facets())
    infrared = env.infrared()
    h = (EARTH_EQUATORIAL_RADIUS_M + 500.0e3) / (EARTH_EQUATORIAL_RADIUS_M + 30.0e3)
    assert env.band == "low" and env.default_olr_w_m2() == 246.0
    assert infrared[:, 4] == pytest.approx(246.0 / h ** 2, rel=1e-6)
    assert infrared[:, 5] == pytest.approx(0.0, abs=1e-9)
    side = float(environment.plate_sphere_view_factor(np.array([0.0]), np.array([h]))[0])
    assert infrared[:, 0] == pytest.approx(246.0 * side, rel=1e-6)
    assert env.infrared(275.0)[0, 4] == pytest.approx(275.0 / h ** 2, rel=1e-6)


def test_orbit_period_inclination_and_beta():
    run = fixtures.circular_run(altitude_m=500.0e3, beta_deg=40.0, orbits=1.5, attitude="nadir")
    env = environment.build(run, "sat", "earth", _facets())
    r = EARTH_EQUATORIAL_RADIUS_M + 500.0e3
    expected = 2 * math.pi * math.sqrt(r ** 3 / 398600.436e9)
    assert env.period_s == pytest.approx(expected, rel=1e-4)
    assert env.inclination_deg == pytest.approx(0.0, abs=1e-6)
    assert env.beta_deg == pytest.approx(40.0, abs=1e-6)


@pytest.mark.requires_basilisk
def test_albedo_from_basilisk_per_facet_normal():
    """Basilisk's albedo module, stand-alone: a nadir face under the
    subsolar point gets about the most (Basilisk's 5 deg patches put the
    peak within a few percent of it), and less toward the terminator; a
    zenith face none; the constant model is linear in its coefficient and
    follows the solar constant; faces sharing a normal share one
    instrument."""
    run = fixtures.circular_run(altitude_m=500.0e3, orbits=0.25, step_s=120.0, attitude="nadir", eclipse=False)
    facets = _facets() + [ThermalFacet("cube", "+z bis", "+z", 0.5, np.array([0.0, 0.0, 1.0]), np.zeros(3))]
    env = environment.build(run, "sat", "earth", facets)
    assert len(env.distinct_normals) == 6
    reflected = env.fluxes(albedo=0.3, albedo_model="average")[1]
    assert reflected[0, 4] > 250.0 and reflected[0, 4] == pytest.approx(reflected[0, 6])
    assert np.all(reflected[:, 5] == 0.0)
    assert reflected[0, 4] > 0.95 * reflected[:, 4].max() and reflected[-1, 4] < 0.5 * reflected[0, 4]
    double = env.fluxes(albedo=0.6, albedo_model="average")[1]
    assert double[0, 4] == pytest.approx(2.0 * reflected[0, 4], rel=1e-9)
    hot = env.fluxes(solar_flux_w_m2=1414.0, albedo=0.3, albedo_model="average")[1]
    assert hot[0, 4] == pytest.approx(reflected[0, 4] * 1414.0 / 1361.0, rel=1e-9)


def test_the_run_must_have_what_the_fluxes_need():
    run = fixtures.circular_run(orbits=0.1)
    with pytest.raises(environment.ThermalEnvironmentError, match="Earth and Mars"):
        environment.build(run, "sat", "moon", _facets())
    del run.series["sat.attitude_sigma_BN"]
    with pytest.raises(environment.ThermalEnvironmentError, match="did not record the attitude"):
        environment.build(run, "sat", "earth", _facets())
    run = fixtures.circular_run(orbits=0.1)
    del run.series["ephemeris.earth.position_N"]
    with pytest.raises(environment.ThermalEnvironmentError, match="positions; run it again"):
        environment.build(run, "sat", "earth", _facets())
