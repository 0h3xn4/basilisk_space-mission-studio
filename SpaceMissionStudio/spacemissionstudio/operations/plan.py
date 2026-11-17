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
"""The plan: its activities, the requests it could not place and why, its
resource profiles and its provenance; the plan file (JSON, design 2.8,
``docs/models/operations.md``).

Times are simulation seconds inside (TDB since the scenario's epoch) and
UTC strings in the file, both written (decision O-05).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

PLAN_FORMAT = "spacemissionstudio-plan"
PLAN_VERSION = 1

#: Why a request was not scheduled (decision O-13), in the order they are checked.
REASONS = {
    "no_opportunity": "no window: the geometry never meets the target's limits in the horizon",
    "outside_validity": "its windows are outside its validity",
    "conflict": "another activity takes the spacecraft at every window",
    "slew": "no time to slew from or to the activities around it",
    "station_busy": "the station serves other spacecraft at every pass",
    "battery": "the battery would fall below the planned minimum",
    "memory": "the memory would overflow",
    "per_orbit": "the per-orbit activity limit is reached",
    "per_day": "the per-day activity or contact limit is reached",
    "exclusion": "an exclusion window or an outage covers every chance",
    "star_tracker": "no star tracker would be clear of the Sun, Earth and Moon",
    "too_short": "every window or pass is shorter than the activity",
    "lost_pass": "the pass is lost (a what-if event or a robustness draw)",
}


@dataclass
class Activity:
    """One planned activity. ``start_s``/``end_s`` bound the activity itself;
    the spacecraft is taken from ``start_s - setup_s`` to ``end_s +
    teardown_s`` (and by the slew before it)."""

    id: str
    spacecraft: str
    type: str  # the activity type's name
    kind: str  # its kind (schema.operations.ACTIVITY_KINDS)
    start_s: float  # [s] simulation time
    end_s: float  # [s]
    start_utc: str = ""
    end_utc: str = ""
    setup_s: float = 0.0  # [s]
    teardown_s: float = 0.0  # [s]
    pointing: str = "sun"
    target: str = ""
    station: str = ""
    request: str = ""
    priority: int | None = None
    locked: bool = False
    predicted: dict = field(default_factory=dict)  # off_nadir_deg, sun_elevation_deg, gsd_m, slew_deg, slew_s, ...

    @property
    def occupied(self) -> tuple[float, float]:
        return self.start_s - self.setup_s, self.end_s + self.teardown_s

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s


@dataclass
class Unscheduled:
    """A request (a target's acquisition, a request's occurrence) the plan
    does not hold, with the reason (the most frequent over the chances
    tried) and the count per reason."""

    request: str
    spacecraft: str
    kind: str
    priority: int
    reason: str  # a key of REASONS
    counts: dict = field(default_factory=dict)
    needed: int = 1
    placed: int = 0

    @property
    def text(self) -> str:
        return REASONS.get(self.reason, self.reason)


@dataclass
class Plan:
    """A plan and how it was made."""

    epoch_utc: str
    start_s: float  # [s] the horizon
    end_s: float  # [s]
    start_utc: str = ""
    end_utc: str = ""
    activities: list = field(default_factory=list)  # list[Activity], by start
    unscheduled: list = field(default_factory=list)  # list[Unscheduled]
    score: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)
    # spacecraft -> {"time_s", "soc", "memory_bit", ...} (decimated); each value is the state at its time_s,
    # the end of the planner's step it closes
    resources: dict = field(default_factory=dict)
    contention: list = field(default_factory=list)  # contested passes and who got them
    notes: list = field(default_factory=list)

    def of(self, spacecraft: str) -> list[Activity]:
        return [a for a in self.activities if a.spacecraft == spacecraft]

    def find(self, activity_id: str) -> Activity | None:
        return next((a for a in self.activities if a.id == activity_id), None)

    def sort(self) -> None:
        self.activities.sort(key=lambda a: (a.start_s, a.spacecraft, a.id))

    def to_dict(self) -> dict:
        data = asdict(self)
        return {"format": PLAN_FORMAT, "version": PLAN_VERSION, **data}

    @staticmethod
    def from_dict(data: dict) -> Plan:
        if not isinstance(data, dict) or data.get("format") != PLAN_FORMAT:
            raise ValueError("not a SpaceMissionStudio plan file (format 'spacemissionstudio-plan')")
        if data.get("version") != PLAN_VERSION:
            raise ValueError(f"plan file version {data.get('version')!r}; this version reads {PLAN_VERSION}")
        data = {k: v for k, v in data.items() if k not in ("format", "version")}
        data["activities"] = [Activity(**a) for a in data.get("activities", [])]
        data["unscheduled"] = [Unscheduled(**u) for u in data.get("unscheduled", [])]
        return Plan(**data)

    def save(self, path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=1, allow_nan=False, default=_plain) + "\n",
                        encoding="utf-8")
        return path

    @staticmethod
    def load(path) -> Plan:
        return Plan.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def _plain(value):
    """numpy scalars and arrays as plain JSON values."""
    import numpy as np

    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"{type(value).__name__} is not JSON serialisable")
