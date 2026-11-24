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
"""A scale on the atmospheric density that drag reads (Monte Carlo plan
C1, decision MC-37).

**Why a module of its own.** Basilisk 2.12.0 has no density scale that
every atmosphere model of the app takes: ``AtmosphereBase`` has none;
``ExponentialAtmosphere`` has ``baseDensity`` and ``TabularAtmosphere`` a
density list, but ``MsisAtmosphere`` (NRLMSISE-00, the default) has
neither; the drag effector's ``densityCorrection`` is a state of the
dynamics (a stochastic integrator's), not a parameter. So
:class:`DensityScale` sits between the atmosphere and the drag: it reads
each spacecraft's ``AtmoPropsMsg`` from the atmosphere model and writes a
copy whose ``neutralDensity`` is ``scale`` times the model's. The
temperature is passed on unchanged. The same works for the three models
and for the sphere and the facet drag (both read ``atmoDensInMsg``). No
change to Basilisk.

The service builds it only for a Monte Carlo run whose scenario disperses
the density (``SimulationService(density_scale=True)``); every other run
is built as before. The Controller sets ``scale`` (the dispersion's path
``get_density_scale().scale``, ``engine.monte_carlo``) before the run
starts.
"""

from __future__ import annotations

import math

from Basilisk.architecture import messaging, sysModel

#: Task priority: after the atmosphere models (390), before the drag effectors (100).
PRIORITY = 385


class DensityScale(sysModel.SysModel):
    """Writes, per spacecraft with drag, a copy of the atmosphere's output
    whose density is ``scale`` times the model's (``scale`` >= 0, no unit)."""

    def __init__(self, name: str = "densityScale"):
        super().__init__()
        self.ModelTag = name
        self.scale = 1.0  # [-] the factor on the density; the Monte Carlo dispersion sets it
        self.atmoInMsgs: list = []
        self.atmoOutMsgs: list = []

    def add(self, atmo_out_msg):
        """Read ``atmo_out_msg`` (an atmosphere model's ``envOutMsgs[i]``);
        returns the scaled message the drag effector subscribes to."""
        reader = messaging.AtmoPropsMsgReader()
        reader.subscribeTo(atmo_out_msg)
        out = messaging.AtmoPropsMsg()
        self.atmoInMsgs.append(reader)
        self.atmoOutMsgs.append(out)
        return out

    def Reset(self, CurrentSimNanos):
        scale = self.scale
        if isinstance(scale, bool) or not isinstance(scale, (int, float)) or not math.isfinite(scale) or scale < 0:
            raise ValueError(f"the atmospheric density scale must be a finite number >= 0, got {scale!r}")
        self.scale = float(scale)
        if all(reader.isWritten() for reader in self.atmoInMsgs):
            self.UpdateState(CurrentSimNanos)

    def UpdateState(self, CurrentSimNanos):
        for reader, out in zip(self.atmoInMsgs, self.atmoOutMsgs):
            given = reader()
            payload = messaging.AtmoPropsMsgPayload()
            payload.neutralDensity = given.neutralDensity * self.scale  # [kg/m^3]
            payload.localTemp = given.localTemp  # [K]
            out.write(payload, CurrentSimNanos, self.moduleID)


def attach(sim, task_name: str) -> DensityScale:
    """Add a :class:`DensityScale` to ``task_name``; the caller adds each
    spacecraft's atmosphere message with :meth:`DensityScale.add`."""
    module = DensityScale()
    sim.AddModelToTask(task_name, module, PRIORITY)
    return module
