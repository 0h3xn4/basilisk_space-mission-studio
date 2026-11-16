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
"""A synthetic run for the thermal tests: a circular orbit around the
Earth with the Sun in the orbit plane (beta 0) or out of it, an attitude
held fixed or pointing +z at nadir, and the eclipse factor of a
cylindrical shadow. No Basilisk run: the series a real run records,
written directly, so the analytical cases can be set exactly."""

from __future__ import annotations

import numpy as np

from spacemissionstudio.constants import ASTRONOMICAL_UNIT_M, EARTH_EQUATORIAL_RADIUS_M, EARTH_GM_M3_S2
from spacemissionstudio.engine.results import ResultSet, TimeSeries


def _dcm_to_mrp(dcm: np.ndarray) -> np.ndarray:
    """MRPs of [BN] matrices (n, 3, 3), via the quaternion (Shepperd's
    method's largest-component branch is not needed for these cases)."""
    out = []
    for c in dcm:
        q0 = 0.5 * np.sqrt(max(1.0 + np.trace(c), 1.0e-15))
        q = np.array([q0, (c[1, 2] - c[2, 1]) / (4 * q0), (c[2, 0] - c[0, 2]) / (4 * q0),
                      (c[0, 1] - c[1, 0]) / (4 * q0)])
        out.append(q[1:] / (1.0 + q[0]))
    return np.array(out)


def circular_run(altitude_m: float = 500.0e3, beta_deg: float = 0.0, orbits: float = 2.0, step_s: float = 30.0,
                 attitude: str = "inertial", eclipse: bool = True, sc: str = "sat",
                 sun_distance_m: float = ASTRONOMICAL_UNIT_M) -> ResultSet:
    """A run of ``orbits`` circular equatorial orbits at ``altitude_m``,
    the Sun at ``beta_deg`` above the orbit plane. ``attitude``:
    ``inertial`` (body = inertial axes) or ``nadir`` (+z toward the Earth,
    +x along the velocity)."""
    r = EARTH_EQUATORIAL_RADIUS_M + altitude_m
    n = np.sqrt(EARTH_GM_M3_S2 / r ** 3)
    period = 2.0 * np.pi / n
    t = np.arange(0.0, orbits * period + step_s / 2, step_s)
    pos = np.column_stack([r * np.cos(n * t), r * np.sin(n * t), np.zeros_like(t)])
    vel = np.column_stack([-r * n * np.sin(n * t), r * n * np.cos(n * t), np.zeros_like(t)])
    b = np.radians(beta_deg)
    sun_dir = np.array([np.cos(b), 0.0, np.sin(b)])
    sun = np.tile(sun_dir * sun_distance_m, (len(t), 1))
    if eclipse:
        along = pos @ sun_dir
        perp = np.linalg.norm(pos - np.outer(along, sun_dir), axis=1)
        light = np.where((along < 0) & (perp < EARTH_EQUATORIAL_RADIUS_M), 0.0, 1.0)
    else:
        light = np.ones(len(t))
    if attitude == "inertial":
        sigma = np.zeros((len(t), 3))
    else:
        z = -pos / np.linalg.norm(pos, axis=1)[:, None]
        x = vel / np.linalg.norm(vel, axis=1)[:, None]
        y = np.cross(z, x)
        sigma = _dcm_to_mrp(np.stack([x, y, z], axis=1))
    result = ResultSet("synthetic")
    result.add(TimeSeries(f"{sc}.position_N", t, ("x", "y", "z"), pos, "m"))
    result.add(TimeSeries(f"{sc}.velocity_N", t, ("x", "y", "z"), vel, "m/s"))
    result.add(TimeSeries(f"{sc}.attitude_sigma_BN", t, ("s1", "s2", "s3"), sigma, "-"))
    result.add(TimeSeries(f"{sc}.eclipse.illumination_factor", t, ("factor",), light[:, None], "-"))
    result.add(TimeSeries("ephemeris.sun.position_N", t, ("x", "y", "z"), sun, "m"))
    result.add(TimeSeries("ephemeris.earth.position_N", t, ("x", "y", "z"), np.zeros((len(t), 3)), "m"))
    result.add(TimeSeries("ephemeris.earth.dcm_PN", t, tuple(f"c{i}{j}" for i in range(3) for j in range(3)),
                          np.tile(np.eye(3).ravel(), (len(t), 1)), "-"))
    return result
