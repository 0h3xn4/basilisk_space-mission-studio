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
"""Case sets: a preset environment and parameter overrides on top of a
spacecraft's thermal section (design 2.8; decision T-13).

Presets, Earth (NASA/TM-2001-211221, the "combined" engineering-extreme
albedo and OLR pairs at 90-minute averaging, by inclination band; the
solar constant of section 4.1):

- ``nominal``: 1367 W/m^2, the albedo map, the band's mean OLR;
- ``hot``: 1414 W/m^2 and the hot combined pair;
- ``cold``: 1322 W/m^2 and the cold combined pair.

The guideline gives the albedo at a solar zenith angle of 0; its orbital
average adds the correction of Table 4.2.1-1 by beta angle, applied for
the run's mean beta (decision T-27).

Mars has no sourced extremes: its presets keep the planet's map and its
infrared, and say so (T-17).

:func:`apply` sets parameters by path (``nodes[battery].capacitance_j_k``,
``faces[bus:+x].absorptance``, ``environment.solar_flux_w_m2``) on a copy;
cases, sweeps, sensitivity and Monte Carlo all use it.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

import numpy as np

from ..schema.scenario import resolve_value_path
from ..schema.thermal import ThermalCaseConfig, ThermalContext, ThermalEnvironmentConfig
from .environment import EARTH_MEAN_OLR_W_M2, GUIDELINE

SOLAR_W_M2 = {"hot": 1414.0, "nominal": 1367.0, "cold": 1322.0}  # [W/m^2] at 1 AU, section 4.1
#: Tables 4.2.3-1 to -3, "combined" columns, 90-minute averaging: (albedo, OLR [W/m^2]).
COMBINED_90_MIN = {
    "hot": {"low": (0.24, 275.0), "medium": (0.26, 257.0), "high": (0.26, 244.0)},
    "cold": {"low": (0.14, 228.0), "medium": (0.19, 218.0), "high": (0.19, 218.0)},
}
#: Table 4.2.1-1: orbital-average albedo correction by beta angle [deg].
ALBEDO_CORRECTION = ((0.0, 0.04), (10.0, 0.04), (20.0, 0.05), (30.0, 0.06), (40.0, 0.07), (50.0, 0.09),
                     (60.0, 0.12), (70.0, 0.16), (80.0, 0.22), (90.0, 0.31))
DEFAULT_CASES = ("nominal", "hot", "cold")


class CaseError(ValueError):
    """An override that names no parameter or gives a value it cannot take."""


def albedo_correction(beta_deg: float) -> float:
    """Table 4.2.1-1's orbital-average correction for ``|beta|``."""
    betas, values = zip(*ALBEDO_CORRECTION, strict=True)
    return float(np.interp(abs(beta_deg), betas, values))


@dataclass
class CaseEnvironment:
    """The environment a case sets, and where each value comes from."""

    environment: ThermalEnvironmentConfig
    notes: list[str] = field(default_factory=list)


def preset_environment(preset: str, central_body: str, band: str, mean_beta_deg: float) -> CaseEnvironment:
    """The environment of preset ``preset`` (module docstring)."""
    if not preset:
        return CaseEnvironment(ThermalEnvironmentConfig(), ["the run's environment (1361 W/m^2 at 1 AU)"])
    if central_body != "earth":
        return CaseEnvironment(ThermalEnvironmentConfig(),
                               [f"{preset}: no sourced extremes for {central_body}; the planet's map and its "
                                "infrared from radiative balance (decision T-17)"])
    solar = SOLAR_W_M2[preset]
    if preset == "nominal":
        return CaseEnvironment(ThermalEnvironmentConfig(solar_flux_w_m2=solar, albedo_model="map",
                                                        planet_ir_w_m2=EARTH_MEAN_OLR_W_M2[band]),
                               [f"nominal: S {solar:g} W/m^2, the CERES albedo map, mean OLR "
                                f"{EARTH_MEAN_OLR_W_M2[band]:g} W/m^2 ({band} inclination; {GUIDELINE})"])
    albedo, olr = COMBINED_90_MIN[preset][band]
    correction = albedo_correction(mean_beta_deg)
    return CaseEnvironment(ThermalEnvironmentConfig(solar_flux_w_m2=solar, albedo=round(albedo + correction, 4),
                                                    planet_ir_w_m2=olr, albedo_model="average"),
                           [f"{preset}: S {solar:g} W/m^2; combined {preset} pair at 90-minute averaging, "
                            f"albedo {albedo:g} + {correction:g} (orbit average at beta {abs(mean_beta_deg):.0f} "
                            f"deg) and OLR {olr:g} W/m^2 ({band} inclination; {GUIDELINE}, Tables 4.2.1-1 "
                            "and 4.2.3); beginning-of-life optics (no sourced end-of-life values in the library, "
                            "T-24)"])


def _typed(old, value, path: str):
    if isinstance(old, bool) or isinstance(value, bool):
        if not isinstance(value, bool) or not (isinstance(old, bool) or old is None):
            raise CaseError(f"{path}: {value!r} is not true or false")
        return value
    if isinstance(old, (int, float)) or old is None:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value) if not isinstance(old, int) or isinstance(value, float) else int(value)
        if old is None and (isinstance(value, (str, list)) or value is None):
            return value
        raise CaseError(f"{path}: {value!r} is not a number")
    if isinstance(old, str):
        if not isinstance(value, str):
            raise CaseError(f"{path}: {value!r} is not text")
        return value
    if isinstance(old, list):
        if not isinstance(value, list):
            raise CaseError(f"{path}: {value!r} is not a list")
        return list(value)
    raise CaseError(f"{path}: cannot be overridden")


def apply(thermal, overrides: dict):
    """A copy of ``thermal`` with each ``{path: value}`` of ``overrides``
    set (T-13). Raises :class:`CaseError` naming the path."""
    changed = copy.deepcopy(thermal)
    for path, value in overrides.items():
        try:
            record, name = resolve_value_path(changed, path)
        except ValueError as exc:
            raise CaseError(f"override {path!r}: {exc}") from exc
        setattr(record, name, _typed(getattr(record, name), value, path))
    return changed


@dataclass
class Case:
    """A case ready to solve: its name, the thermal section with its
    environment and overrides applied, and notes on where its values come
    from."""

    name: str
    thermal: object
    notes: list[str]


def resolve(thermal, case: ThermalCaseConfig, central_body: str, band: str, mean_beta_deg: float,
            context: ThermalContext | None = None, where: str = "") -> Case:
    """The :class:`Case` of ``case``: the preset's environment (where the
    section's own environment does not set a value), then the overrides,
    then validation (with ``context``)."""
    env = preset_environment(case.preset, central_body, band, mean_beta_deg)
    base = copy.deepcopy(thermal)
    own = thermal.environment
    preset = env.environment
    base.environment = ThermalEnvironmentConfig(
        solar_flux_w_m2=own.solar_flux_w_m2 if own.solar_flux_w_m2 is not None else preset.solar_flux_w_m2,
        albedo=own.albedo if own.albedo is not None else preset.albedo,
        planet_ir_w_m2=own.planet_ir_w_m2 if own.planet_ir_w_m2 is not None else preset.planet_ir_w_m2,
        albedo_model=preset.albedo_model if own.albedo_model == "map" else own.albedo_model)
    changed = apply(base, case.overrides)
    if context is not None:
        changed.validate(where or "case", context)
    notes = list(env.notes)
    notes += [f"{path} = {value!r}" for path, value in case.overrides.items()]
    return Case(case.name, changed, notes)


def cases_of(thermal) -> list[ThermalCaseConfig]:
    """The section's cases, or the three presets when it names none."""
    return list(thermal.cases) or [ThermalCaseConfig(name, preset=name) for name in DEFAULT_CASES]
