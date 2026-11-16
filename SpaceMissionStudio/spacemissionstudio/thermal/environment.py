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
"""Incident environmental flux on every thermal facet over a run
(design 2.5), from the run's recorded position, attitude, Sun, central
body and eclipse factor:

- direct sunlight ``S(r) * illum * max(0, n . s)``, with
  ``S(r) = S_1AU (1 AU / r)^2``;
- albedo from Basilisk's ``albedo`` module per facet normal
  (``thermal.albedo``), the planet's map or a constant coefficient;
- planetary infrared ``OLR * F``, with ``F`` the view factor from a flat
  plate to a sphere (:func:`plate_sphere_view_factor`).

Fluxes are incident, before the facet's optics. They are stored as
factors, so a case's solar constant and OLR scale them without a new
computation; only a new albedo coefficient runs Basilisk's module again
(cached). A self-shadowing factor per facet and time would multiply the
solar term in :meth:`Environment.fluxes` (decision T-06).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..analyses.run_geometry import RunGeometry, nearest_sample, run_geometry
from ..constants import ASTRONOMICAL_UNIT_M, SOLAR_FLUX_1AU_W_M2
from . import albedo as albedo_module

#: The OLR and albedo references are at the top of the atmosphere, 30 km
#: above the surface (NASA/TM-2001-211221, Tables 4.2.3-1 to -3).
EARTH_TOP_OF_ATMOSPHERE_M = 30.0e3  # [m]
#: NASA/TM-2001-211221's mean OLR [W/m^2] and albedo by inclination band
#: (low < 30 deg, medium 30 to 60 deg, high > 60 deg; Tables 4.2.3-1 to -3).
EARTH_MEAN_OLR_W_M2 = {"low": 246.0, "medium": 234.0, "high": 211.0}
EARTH_MEAN_ALBEDO = {"low": 0.18, "medium": 0.22, "high": 0.23}
GUIDELINE = ("B. J. Anderson, C. G. Justus, G. W. Batts, Guidelines for the Selection of Near-Earth Thermal "
             "Environment Parameters for Spacecraft Design, NASA/TM-2001-211221, 2001")
#: Mars: Basilisk's average albedo (``albedo.getAlbedoAverage("mars barycenter")``), and the planet's
#: infrared from radiative balance, (1 - a) S / 4 (an estimate, design section 4).
MARS_AVERAGE_ALBEDO = 0.16  # [-]


class ThermalEnvironmentError(ValueError):
    """A run the thermal model cannot be solved on, saying why."""


def plate_sphere_view_factor(cos_lambda: np.ndarray, h: np.ndarray) -> np.ndarray:
    """View factor from a flat plate to a sphere, as an array: ``h`` the
    distance from the sphere's centre in its radii (> 1), ``cos_lambda``
    the cosine of the angle between the plate's normal and the direction
    to the centre. The plate sees the whole disk when ``lambda <=
    acos(1/h)`` (``cos(lambda) / h^2``), none of it when ``lambda >=
    pi/2 + asin(1/h)``, and in between the partial form (Gilmore,
    Spacecraft Thermal Control Handbook, ch. 2; the catalogue form for a
    plane element and a sphere)."""
    cos_l = np.clip(np.asarray(cos_lambda, dtype=float), -1.0, 1.0)
    h = np.broadcast_to(np.asarray(h, dtype=float), cos_l.shape)
    lam = np.arccos(cos_l)
    edge = np.arccos(1.0 / h)
    full = lam <= edge
    none = lam >= np.pi / 2.0 + np.arcsin(1.0 / h)
    result = np.where(full, cos_l / h ** 2, 0.0)
    part = ~full & ~none
    if part.any():
        hp, lp, cp = h[part], lam[part], cos_l[part]
        root = np.sqrt(hp * hp - 1.0)
        sin_l = np.sin(lp)
        term1 = 0.5 - np.arcsin(np.clip(root / (hp * sin_l), -1.0, 1.0)) / np.pi
        cot = cp / sin_l
        term2 = (cp * np.arccos(np.clip(-root * cot, -1.0, 1.0))
                 - root * np.sqrt(np.clip(1.0 - hp * hp * cp * cp, 0.0, None))) / (np.pi * hp * hp)
        result[part] = np.clip(term1 + term2, 0.0, None)
    return result


def inclination_band(inclination_deg: float) -> str:
    """The guideline's band: ``low`` below 30 deg, ``medium`` to 60 deg,
    ``high`` above (retrograde orbits by their supplement)."""
    i = min(inclination_deg, 180.0 - inclination_deg)
    return "low" if i < 30.0 else ("medium" if i <= 60.0 else "high")


@dataclass
class Environment:
    """A run's incident environment on the thermal facets of one
    spacecraft (module docstring), on the run's recorded times."""

    spacecraft: str
    central_body: str
    time_s: np.ndarray  # (n,) [s]
    solar_factor: np.ndarray  # (n, f) [-] (1 AU / r)^2 * illum * max(0, n.s): times S_1AU gives W/m^2
    view_factor: np.ndarray  # (n, f) [-] plate to planet: times OLR gives W/m^2
    illumination: np.ndarray  # (n,) [-] the run's eclipse factor
    sun_distance_m: np.ndarray  # (n,) [m]
    beta_deg: np.ndarray  # (n,) [deg] Sun elevation above the orbit plane
    inclination_deg: float  # [deg] to the central body's equator
    period_s: float  # [s] of the orbit
    normals_b: np.ndarray  # (f, 3)
    normal_index: np.ndarray  # (f,) facet -> distinct normal
    distinct_normals: np.ndarray  # (k, 3)
    albedo_inputs: dict  # what Basilisk's module needs again for another coefficient
    _albedo: dict = field(default_factory=dict)  # key -> (n, k) W/m^2 at 1361 W/m^2 at 1 AU
    warnings: list = field(default_factory=list)

    @property
    def band(self) -> str:
        return inclination_band(self.inclination_deg)

    def default_olr_w_m2(self) -> np.ndarray | float:
        """The planet's mean infrared: the guideline's mean OLR of the
        orbit's inclination band (Earth), or radiative balance (Mars)."""
        if self.central_body == "earth":
            return EARTH_MEAN_OLR_W_M2[self.band]
        solar = SOLAR_FLUX_1AU_W_M2 * (ASTRONOMICAL_UNIT_M / self.sun_distance_m) ** 2
        return (1.0 - MARS_AVERAGE_ALBEDO) * solar / 4.0

    def albedo(self, coefficient: float | None) -> np.ndarray:
        """``(n, f)`` albedo flux [W/m^2] at Basilisk's 1361 W/m^2 at 1 AU:
        the planet's map (``coefficient`` None) or a constant coefficient,
        computed once per coefficient."""
        key = "map" if coefficient is None else round(float(coefficient), 6)
        if key not in self._albedo:
            inputs = dict(self.albedo_inputs)
            if coefficient is not None:
                inputs["coefficient"] = float(coefficient)
            distinct = albedo_module.albedo_flux(normals_b=self.distinct_normals, **inputs)
            self._albedo[key] = distinct
        return self._albedo[key][:, self.normal_index]

    def solar(self, solar_flux_w_m2: float | None = None, shading: np.ndarray | None = None) -> np.ndarray:
        """``(n, f)`` direct sunlight [W/m^2] with ``solar_flux_w_m2`` at
        1 AU (None: 1361). ``shading`` (n, f) is the lit fraction of each
        facet (1 without self-shadowing, T-06)."""
        s_1au = SOLAR_FLUX_1AU_W_M2 if solar_flux_w_m2 is None else float(solar_flux_w_m2)
        solar = s_1au * self.solar_factor
        return solar if shading is None else solar * shading

    def reflected(self, solar_flux_w_m2: float | None = None, albedo: float | None = None,
                  albedo_model: str = "map") -> np.ndarray:
        """``(n, f)`` albedo flux [W/m^2]: a constant ``albedo``
        coefficient, else the planet's map (``albedo_model`` "map") or its
        mean (``"average"``), with the Sun at ``solar_flux_w_m2`` at 1 AU."""
        s_1au = SOLAR_FLUX_1AU_W_M2 if solar_flux_w_m2 is None else float(solar_flux_w_m2)
        if albedo is None and (albedo_model == "average" or self.albedo_inputs.get("map_path") is None):
            albedo = MARS_AVERAGE_ALBEDO if self.central_body != "earth" else EARTH_MEAN_ALBEDO[self.band]
        return self.albedo(albedo) * (s_1au / albedo_module.BASILISK_SOLAR_FLUX_W_M2)

    def infrared(self, planet_ir_w_m2: float | None = None) -> np.ndarray:
        """``(n, f)`` planetary infrared [W/m^2] with the planet's OLR at the
        top of the atmosphere (None: its mean, :meth:`default_olr_w_m2`)."""
        olr = np.asarray(self.default_olr_w_m2() if planet_ir_w_m2 is None else float(planet_ir_w_m2), dtype=float)
        return self.view_factor * (olr[:, None] if olr.ndim else olr)

    def fluxes(self, solar_flux_w_m2: float | None = None, albedo: float | None = None,
               planet_ir_w_m2: float | None = None, albedo_model: str = "map",
               shading: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """``(solar, albedo, infrared)`` incident flux [W/m^2], each (n, f),
        in the environment a case sets (None: the run's)."""
        return (self.solar(solar_flux_w_m2, shading), self.reflected(solar_flux_w_m2, albedo, albedo_model),
                self.infrared(planet_ir_w_m2))


def _orbit(geometry: RunGeometry, velocity: np.ndarray, pole_n: np.ndarray):
    """``(period [s], inclination [deg], beta [deg] per time)``."""
    r = geometry.position_n - geometry.central_n
    h = np.cross(r, velocity)
    h_hat = h / np.linalg.norm(h, axis=1)[:, None]
    mean_normal = h_hat.mean(axis=0)
    mean_normal /= np.linalg.norm(mean_normal)
    inclination = float(np.degrees(np.arccos(np.clip(mean_normal @ pole_n, -1.0, 1.0))))
    u = np.cross(pole_n, mean_normal)
    if np.linalg.norm(u) < 1.0e-9:
        u = np.array([1.0, 0.0, 0.0]) - mean_normal[0] * mean_normal
    u /= np.linalg.norm(u)
    v = np.cross(mean_normal, u)
    angle = np.unwrap(np.arctan2(r @ v, r @ u))
    span = angle[-1] - angle[0]
    duration = geometry.time_s[-1] - geometry.time_s[0]
    period = float(2.0 * np.pi * duration / span) if span > 1.0e-6 else float("inf")
    if geometry.sun_n is None:
        beta = np.zeros(len(r))
    else:
        to_sun = geometry.sun_n - geometry.central_n
        to_sun /= np.linalg.norm(to_sun, axis=1)[:, None]
        beta = np.degrees(np.arcsin(np.clip(np.einsum("ij,ij->i", to_sun, h_hat), -1.0, 1.0)))
    return period, inclination, beta


def albedo_map_path(central_body: str):
    """The installed albedo map of ``central_body`` (the one the coarse sun
    sensors use), or None when it is not installed; never downloads."""
    from Basilisk.utilities.supportDataTools.dataFetcher import DataFile

    from ..engine import kernels
    from ..schema.scenario import ALBEDO_MAPS

    try:
        return kernels.cached_path(getattr(DataFile.AlbedoData, ALBEDO_MAPS[central_body]))
    except (kernels.KernelError, KeyError, AttributeError, ImportError):
        return None


def build(result, sc_name: str, central_body: str, facets, map_path=None) -> Environment:
    """The :class:`Environment` of spacecraft ``sc_name`` in a finished
    run ``result`` (a ResultSet), on ``facets`` (``geometry.facets``).
    ``map_path`` is the central body's albedo data file (the map's).
    Raises :class:`ThermalEnvironmentError` when the run lacks what the
    fluxes need."""
    if central_body not in ("earth", "mars barycenter"):
        raise ThermalEnvironmentError(f"the thermal model supports Earth and Mars as central bodies, "
                                      f"not {central_body!r} (decision T-17)")
    geometry = run_geometry(result, sc_name, central_body)
    if geometry is None:
        raise ThermalEnvironmentError(f"{sc_name}: the run did not record the attitude; the thermal model needs it "
                                      "(set an FSW mode or full attitude) and the position")
    if geometry.sun_n is None or f"ephemeris.{central_body}.position_N" not in result.series:
        raise ThermalEnvironmentError(f"{sc_name}: the run did not record the Sun's and {central_body}'s "
                                      "positions; run it again with this version (decision T-16)")
    velocity_series = result.series.get(f"{sc_name}.velocity_N")
    if velocity_series is None:
        raise ThermalEnvironmentError(f"{sc_name}: the run did not record the velocity")
    t = geometry.time_s
    velocity = np.column_stack([np.interp(t, velocity_series.time_s, np.asarray(velocity_series.data)[:, k])
                                for k in range(3)])
    dcm_series = result.series.get(f"ephemeris.{central_body}.dcm_PN")
    if dcm_series is not None:
        index = nearest_sample(np.asarray(dcm_series.time_s, float), t)
        dcm_pn = np.asarray(dcm_series.data, dtype=float)[index].reshape(-1, 3, 3)
        pole_n = dcm_pn[0][2]
    else:
        dcm_pn, pole_n = None, np.array([0.0, 0.0, 1.0])
    warnings = []
    if map_path is None:
        map_path = albedo_map_path(central_body)
        if map_path is None:
            warnings.append(f"{central_body}'s albedo map is not installed: the mean albedo is used "
                            "(download it from the Reference data dialog)")
    if dcm_pn is None:
        warnings.append(f"{central_body}'s orientation was not recorded: the albedo map is read as if the planet "
                        "did not turn; use a constant albedo coefficient")
    normals = np.array([f.normal_b for f in facets], dtype=float).reshape(-1, 3)
    sun_b, sun_distance = geometry.unit_body(geometry.sun_n)
    cosines = np.clip(sun_b @ normals.T, 0.0, None)
    solar_factor = (ASTRONOMICAL_UNIT_M / sun_distance)[:, None] ** 2 * geometry.sunlight[:, None] * cosines
    nadir_b, centre_distance = geometry.unit_body(geometry.central_n)
    radius = geometry.central_radius_m + (EARTH_TOP_OF_ATMOSPHERE_M if central_body == "earth" else 0.0)
    h = np.maximum(centre_distance / radius, 1.0 + 1.0e-9)
    view = plate_sphere_view_factor(nadir_b @ normals.T, h[:, None])
    attitude = result.series[f"{sc_name}.attitude_sigma_BN"]
    sigma = np.asarray(attitude.data, dtype=float)[nearest_sample(np.asarray(attitude.time_s, float), t)]
    rounded = np.round(normals, 6)
    distinct, inverse = np.unique(rounded, axis=0, return_inverse=True)
    period, inclination, beta = _orbit(geometry, velocity, pole_n)
    inputs = dict(planet=central_body, times_s=t, position_n=geometry.position_n, sigma_bn=sigma,
                  sun_n=geometry.sun_n, planet_n=geometry.central_n, dcm_pn=dcm_pn, map_path=map_path)
    return Environment(sc_name, central_body, t, solar_factor, view, geometry.sunlight, sun_distance, beta,
                       inclination, period, normals, inverse.ravel(), distinct, inputs, warnings=warnings)
