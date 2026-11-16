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
"""Albedo flux per facet normal from Basilisk's ``albedo`` module, run
stand-alone on a finished run's recorded states (design 2.5).

The module is used through its public API only, as
``engine.fsw.build_albedo`` uses it in a run: one instrument per distinct
facet normal with a 90 degree half-angle (a plate sees a hemisphere),
the planet's measured map (CERES for Earth, TES for Mars) or a constant
albedo coefficient. Each recorded time, stand-alone messages carry the
spacecraft's position and attitude, the Sun's position and the planet's
position and orientation; ``UpdateState`` evaluates it and
``AfluxAtInstrument`` is read [W/m^2]. Basilisk scales the Sun's flux
with distance from 1361 W/m^2 at 1 AU. Nothing of Basilisk is changed.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

_GRID_LATITUDES = 36  # [-] the constant-albedo model's grid, the 5 x 5 deg maps'
_GRID_LONGITUDES = 72  # [-]
BASILISK_SOLAR_FLUX_W_M2 = 1361.0  # [W/m^2] Basilisk's SOLAR_FLUX_EARTH at 1 AU


def _payload(messaging, kind: str, **fields):
    payload = getattr(messaging, f"{kind}MsgPayload")()
    for name, value in fields.items():
        setattr(payload, name, value)
    return payload


def albedo_flux(planet: str, normals_b: np.ndarray, times_s: np.ndarray, position_n: np.ndarray,
                sigma_bn: np.ndarray, sun_n: np.ndarray, planet_n: np.ndarray, dcm_pn: np.ndarray | None,
                map_path: str | Path | None = None, coefficient: float | None = None) -> np.ndarray:
    """``(n_times, n_normals)`` albedo flux [W/m^2] on plates of the body-
    frame unit ``normals_b`` (k, 3). ``map_path`` is the planet's albedo
    data file (used when ``coefficient`` is None); ``coefficient`` uses
    Basilisk's constant-albedo model instead. ``dcm_pn`` (n, 3, 3) is the
    planet's orientation, needed by a map."""
    from Basilisk.architecture import messaging
    from Basilisk.simulation import albedo

    module = albedo.Albedo()
    module.ModelTag = "thermal_albedo"
    planet_msg = messaging.SpicePlanetStateMsg()
    sun_msg = messaging.SpicePlanetStateMsg()
    sc_msg = messaging.SCStatesMsg()
    first = dict(PositionVector=list(map(float, planet_n[0])), PlanetName=planet,
                 J20002Pfix=(np.eye(3) if dcm_pn is None else dcm_pn[0]).tolist())
    planet_msg.write(_payload(messaging, "SpicePlanetState", **first))
    sun_msg.write(_payload(messaging, "SpicePlanetState", PositionVector=list(map(float, sun_n[0])),
                           PlanetName="sun"))
    sc_msg.write(_payload(messaging, "SCStates", r_BN_N=list(map(float, position_n[0])),
                          sigma_BN=list(map(float, sigma_bn[0]))))
    if coefficient is None:
        path = Path(map_path)
        module.addPlanetandAlbedoDataModel(planet_msg, str(path.parent), path.name)
    else:
        module.addPlanetandAlbedoAverageModel(planet_msg, float(coefficient), _GRID_LATITUDES, _GRID_LONGITUDES)
    for normal in np.asarray(normals_b, dtype=float):
        module.addInstrumentConfig(np.pi / 2.0, [float(v) for v in normal], [0.0, 0.0, 0.0])
    module.spacecraftStateInMsg.subscribeTo(sc_msg)
    module.sunPositionInMsg.subscribeTo(sun_msg)
    module.Reset(0)
    out = np.zeros((len(times_s), len(normals_b)))
    for k, t in enumerate(times_s):
        nanos = int(round(float(t) * 1.0e9))
        orientation = (np.eye(3) if dcm_pn is None else dcm_pn[k]).tolist()
        planet_msg.write(_payload(messaging, "SpicePlanetState", PositionVector=list(map(float, planet_n[k])),
                                  PlanetName=planet, J20002Pfix=orientation), nanos)
        sun_msg.write(_payload(messaging, "SpicePlanetState", PositionVector=list(map(float, sun_n[k])),
                               PlanetName="sun"), nanos)
        sc_msg.write(_payload(messaging, "SCStates", r_BN_N=list(map(float, position_n[k])),
                              sigma_BN=list(map(float, sigma_bn[k]))), nanos)
        module.UpdateState(nanos)
        out[k] = [module.albOutMsgs[i].read().AfluxAtInstrument for i in range(len(normals_b))]
    return out
