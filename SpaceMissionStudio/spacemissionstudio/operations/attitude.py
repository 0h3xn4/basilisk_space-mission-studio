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
"""The attitude each pointing mode asks for, as the guidance the executor
flies computes it (decision O-09), and how long a slew takes (O-08).

* ``nadir``: ``hillPoint``, the body frame on the Hill frame (x radial
  out, z along the orbit normal, y completing);
* ``sun``, ``target``, ``station``: an axis on a direction, the rotation
  about it the smallest from the attitude before (the eigen-axis error of
  ``sunSafePoint`` and ``locationPointing``);
* ``inertial``: ``inertial3D``'s fixed reference.

Slew time from the controller (``source "controller"``): the time the
spacecraft's own MRP feedback (``L = -K sigma - P omega``, Schaub and
Junkins; gains as ``engine.fsw`` sets them) takes to bring an eigen-axis
error below ``results.pointing_converged_deg``, on the largest principal
inertia, with the reaction wheels' torque and momentum limits when it
has wheels. From limits (``"limits"``): rest-to-rest bang-coast-bang
(B. Wie, Space Vehicle Dynamics and Control, 2nd ed.).
"""

from __future__ import annotations

import math

import numpy as np

from ..analyses.run_geometry import mrp_to_dcm

_SETTLE_GRID_DEG = np.linspace(0.0, 180.0, 181)  # [deg] slew angles the controller model is integrated for
_STEP_S = 0.05  # [s] integration step of the controller model (RK4)
_MAX_SLEW_S = 7200.0  # [s] a slew that has not settled by then is reported as this long


def unit(vectors: np.ndarray) -> np.ndarray:
    vectors = np.asarray(vectors, dtype=float)
    return vectors / np.linalg.norm(vectors, axis=-1, keepdims=True)


def hill_dcm(position_n: np.ndarray, velocity_n: np.ndarray) -> np.ndarray:
    """``[BN]`` of ``hillPoint`` (n, 3, 3): rows are the radial, along-track
    and orbit-normal unit vectors."""
    r = unit(np.atleast_2d(position_n))
    h = unit(np.cross(np.atleast_2d(position_n), np.atleast_2d(velocity_n)))
    theta = np.cross(h, r)
    return np.stack([r, theta, h], axis=1)


def inertial_dcm(sigma_rn) -> np.ndarray:
    """``[BN]`` of ``inertial3D``'s reference (an MRP)."""
    return mrp_to_dcm(np.asarray(sigma_rn, dtype=float))[0]


def _rotation(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """The smallest rotation (3, 3) taking unit vector ``a`` onto ``b``
    (both in the same frame): ``R a = b``. Plain floats: it runs for every
    sample of every pointed activity, where NumPy's per-call cost on a
    3-vector was most of the scheduler's time."""
    a0, a1, a2 = float(a[0]), float(a[1]), float(a[2])
    b0, b1, b2 = float(b[0]), float(b[1]), float(b[2])
    x, y, z = a1 * b2 - a2 * b1, a2 * b0 - a0 * b2, a0 * b1 - a1 * b0  # a x b
    s = math.sqrt(x * x + y * y + z * z)
    c = min(1.0, max(-1.0, a0 * b0 + a1 * b1 + a2 * b2))
    if s < 1e-12:
        if c > 0.0:
            return np.eye(3)
        other = np.array([1.0, 0.0, 0.0]) if abs(a0) < 0.9 else np.array([0.0, 1.0, 0.0])
        axis = unit(np.cross(a, other))
        return 2.0 * np.outer(axis, axis) - np.eye(3)  # 180 deg about a perpendicular axis
    k0, k1, k2 = x / s, y / s, z / s
    skew = np.array([[0.0, -k2, k1], [k2, 0.0, -k0], [-k1, k0, 0.0]])
    return np.eye(3) + s * skew + (1.0 - c) * (skew @ skew)


def _unit3(v) -> tuple[float, float, float]:
    x, y, z = float(v[0]), float(v[1]), float(v[2])
    norm = math.sqrt(x * x + y * y + z * z)
    return x / norm, y / norm, z / norm


def point_axis(dcm_bn: np.ndarray, axis_b, direction_n) -> np.ndarray:
    """``[BN]`` after the smallest rotation that puts body ``axis_b`` on
    inertial ``direction_n``, starting from ``dcm_bn``."""
    axis_n = np.array(_unit3(dcm_bn.T @ np.array(_unit3(axis_b))))
    rotation = _rotation(axis_n, np.array(_unit3(direction_n)))
    return orthonormal(dcm_bn @ rotation.T)


def orthonormal(dcm: np.ndarray) -> np.ndarray:
    """``dcm`` with its rows made orthonormal again (Gram-Schmidt), so
    chained rotations do not drift."""
    x0, x1, x2 = _unit3(dcm[0])
    r0, r1, r2 = float(dcm[1, 0]), float(dcm[1, 1]), float(dcm[1, 2])
    d = r0 * x0 + r1 * x1 + r2 * x2
    y0, y1, y2 = _unit3((r0 - d * x0, r1 - d * x1, r2 - d * x2))
    return np.array([[x0, x1, x2], [y0, y1, y2],
                     [x1 * y2 - x2 * y1, x2 * y0 - x0 * y2, x0 * y1 - x1 * y0]])


def angle_deg(dcm_a: np.ndarray, dcm_b: np.ndarray) -> float:
    """The principal rotation angle [deg] between two attitudes."""
    cosine = (float(np.trace(dcm_a @ dcm_b.T)) - 1.0) / 2.0
    return math.degrees(math.acos(min(1.0, max(-1.0, cosine))))


def axis_angle_deg(dcm_bn: np.ndarray, axis_b, direction_n) -> float:
    """The angle [deg] between body ``axis_b`` and inertial ``direction_n``:
    the slew to point one at the other with the smallest rotation."""
    axis_n = dcm_bn.T @ unit(np.asarray(axis_b, dtype=float))
    cosine = float(np.dot(axis_n, unit(np.asarray(direction_n, dtype=float))))
    return math.degrees(math.acos(min(1.0, max(-1.0, cosine))))


class SlewModel:
    """``time_s(angle_deg)``: how long a slew of a principal angle takes."""

    def __init__(self, times_s: np.ndarray, description: str):
        self._times = np.asarray(times_s, dtype=float)
        self.description = description

    scale = 1.0  # [-] robustness: slews that take longer (or shorter) than modelled

    def time_s(self, angle: float) -> float:
        return self.scale * float(np.interp(min(max(angle, 0.0), 180.0), _SETTLE_GRID_DEG, self._times))

    @classmethod
    def from_limits(cls, max_rate_deg_s: float, max_acceleration_deg_s2: float) -> SlewModel:
        """Rest-to-rest bang-coast-bang (Wie)."""
        w, a = max_rate_deg_s, max_acceleration_deg_s2
        theta = _SETTLE_GRID_DEG
        times = np.where(theta <= w * w / a, 2.0 * np.sqrt(theta / a), theta / w + w / a)
        return cls(times, f"bang-coast-bang, {w:g} deg/s and {a:g} deg/s^2")

    @classmethod
    def from_controller(cls, inertia_kg_m2: float, k: float, p: float, settle_deg: float,
                        max_torque_nm: float | None = None, max_momentum_nms: float | None = None) -> SlewModel:
        """The closed-loop MRP PD response about one axis (module docstring),
        integrated for every grid angle at once (RK4)."""
        theta = np.radians(_SETTLE_GRID_DEG).copy()  # [rad] the error, from each start angle
        rate = np.zeros_like(theta)  # [rad/s]
        settle = math.radians(settle_deg)
        times = np.where(theta <= settle, 0.0, np.nan)
        rate_cap = (max_momentum_nms / inertia_kg_m2) if max_momentum_nms else None  # [rad/s]

        def accel(angle, speed):
            torque = -k * np.tan(angle / 4.0) - p * speed  # [N*m] mrpFeedback, sigma = tan(theta/4)
            if max_torque_nm is not None:
                torque = np.clip(torque, -max_torque_nm, max_torque_nm)
            return torque / inertia_kg_m2

        t = 0.0
        while t < _MAX_SLEW_S and np.isnan(times).any():
            k1v, k1a = rate, accel(theta, rate)
            k2v, k2a = rate + 0.5 * _STEP_S * k1a, accel(theta + 0.5 * _STEP_S * k1v, rate + 0.5 * _STEP_S * k1a)
            k3v, k3a = rate + 0.5 * _STEP_S * k2a, accel(theta + 0.5 * _STEP_S * k2v, rate + 0.5 * _STEP_S * k2a)
            k4v, k4a = rate + _STEP_S * k3a, accel(theta + _STEP_S * k3v, rate + _STEP_S * k3a)
            theta = theta + _STEP_S / 6.0 * (k1v + 2 * k2v + 2 * k3v + k4v)
            rate = rate + _STEP_S / 6.0 * (k1a + 2 * k2a + 2 * k3a + k4a)
            if rate_cap is not None:
                rate = np.clip(rate, -rate_cap, rate_cap)
            t += _STEP_S
            # settled: inside the tolerance and not moving out of it again (slowing down)
            done = np.isnan(times) & (np.abs(theta) <= settle) & (np.abs(rate) * 10.0 <= settle + np.abs(theta))
            times[done] = t
        times[np.isnan(times)] = _MAX_SLEW_S
        times = np.maximum.accumulate(times)  # a larger slew never takes less time
        limits = []
        if max_torque_nm is not None:
            limits.append(f"{max_torque_nm:.3g} N*m")
        if max_momentum_nms is not None:
            limits.append(f"{max_momentum_nms:.3g} N*m*s")
        return cls(times, f"MRP feedback K {k:.4g}, P {p:.4g} on {inertia_kg_m2:.4g} kg*m^2"
                          + (f", wheels {' and '.join(limits)}" if limits else "")
                          + f", settled within {settle_deg:g} deg")


def wheel_limits(sc) -> tuple[float | None, float | None]:
    """The reaction wheels' torque [N*m] and momentum [N*m*s] about the
    weakest body axis (sum of |g_i . e| times each wheel's limit), or None
    without wheels or limits."""
    wheels = [a for a in sc.actuators if a.kind == "reaction_wheel"]
    if not wheels:
        return None, None
    torques, momenta = [], []
    for axis in np.eye(3):
        torque = momentum = 0.0
        for wheel in wheels:
            g = unit(np.asarray(wheel.params.get("gsHat_B", [0.0, 0.0, 1.0]), dtype=float))
            share = abs(float(np.dot(g, axis)))
            torque += share * float(wheel.params.get("u_max", math.inf) or math.inf)
            momentum += share * float(wheel.params.get("maxMomentum", math.inf) or math.inf)
        torques.append(torque)
        momenta.append(momentum)
    torque, momentum = min(torques), min(momenta)
    return (torque if math.isfinite(torque) else None), (momentum if math.isfinite(momentum) else None)


#: The planner's slews settle to this fraction of the convergence threshold
#: the verification checks (decision O-25): the one-axis model ignores the
#: three-axis coupling and a moving target, which left flown slews 0.7 to
#: 0.9 deg beyond the threshold at the activity's start (template 35).
_SETTLE_FRACTION = 0.5


def slew_model(sc, agility, scenario=None) -> SlewModel:
    """The :class:`SlewModel` of a spacecraft's planning ``agility``."""
    if agility.source == "limits":
        return SlewModel.from_limits(agility.max_rate_deg_s, agility.max_acceleration_deg_s2)
    from ..config import registry
    from ..engine.control_gains import default_mrp_gains_for_inertia
    from ..engine.solar_arrays import fsw_inertia_kg_m2

    inertia = fsw_inertia_kg_m2(sc)
    gains = default_mrp_gains_for_inertia(inertia)
    params = sc.control_params or {}
    k, p = float(params.get("K", gains["K"])), float(params.get("P", gains["P"]))
    largest = float(np.max(np.linalg.eigvalsh(np.asarray(inertia, dtype=float).reshape(3, 3))))
    torque, momentum = wheel_limits(sc)
    settle = _SETTLE_FRACTION * float(registry.value("results.pointing_converged_deg", scenario))
    return SlewModel.from_controller(largest, k, p, settle, torque, momentum)
