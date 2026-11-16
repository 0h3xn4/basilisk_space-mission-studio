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
"""UTC in the plan's files, simulation time inside (decision O-05).

Simulation time is TDB seconds since the scenario's epoch, the time of
every recorded series. The only conversions are ``engine.time_system``'s
(ERFA): leap seconds from ERFA's table, the periodic TDB - TT term kept.
"""

from __future__ import annotations

from datetime import datetime, timedelta, UTC

import numpy as np

from ..engine import time_system
from ..schema.epochs import parse_epoch_utc


def _naive(moment) -> datetime:
    if isinstance(moment, str):
        moment = parse_epoch_utc(moment)
    if moment.tzinfo is not None:
        moment = moment.astimezone(UTC).replace(tzinfo=None)
    return moment


class TimeBase:
    """The scenario's epoch and the conversions between UTC and simulation
    time."""

    def __init__(self, epoch_utc):
        self.epoch = _naive(epoch_utc)

    def to_sim(self, moment) -> float:
        """Simulation seconds [s TDB since the epoch] of a UTC instant (a
        string or a datetime)."""
        return float(time_system.tdb_seconds_between(self.epoch, _naive(moment)))

    def to_utc(self, seconds) -> list[datetime]:
        """The UTC instants of simulation times [s], microsecond resolution."""
        values = np.atleast_1d(np.asarray(seconds, dtype=float))
        stamps = time_system.elapsed_to_utc(self.epoch, values)
        return [s.astype("datetime64[us]").astype(datetime) if isinstance(s, np.datetime64) else s
                for s in np.atleast_1d(stamps)]

    def text(self, seconds: float) -> str:
        """``2030-01-01T08:30:00.000Z`` for a simulation time, to the
        nearest millisecond."""
        return self.texts([seconds])[0]

    def texts(self, seconds) -> list[str]:
        return [format_utc(m) for m in self.to_utc(seconds)]


def format_utc(moment: datetime) -> str:
    """ISO 8601 UTC with ``Z``, rounded to the millisecond."""
    moment = moment + timedelta(microseconds=500)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"
