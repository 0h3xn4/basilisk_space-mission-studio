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
"""Scenarios for the operations planner's tests: the 150 kg Earth
observation template (26) with an ``operations`` section. Mission values
here are test inputs, not defaults."""

import copy
import json

from spacemissionstudio import api
from spacemissionstudio.schema.scenario import Scenario

EPOCH = "2030-01-01T08:30:00"


def base_dict() -> dict:
    with open(api.template("26_earth_observation_data_downlink.json"), encoding="utf-8") as stream:
        return json.load(stream)


def operations_dict(**changes) -> dict:
    """A small operations section: two point targets, a camera
    acquisition, a downlink on berlin-gs, a calibration request."""
    section = {
        "version": 1,
        "horizon": {"start_utc": "2030-01-01T08:30:00Z", "end_utc": "2030-01-02T08:30:00Z"},
        "geometry": {"source": "analytic", "step_s": 10.0},
        "targets": [
            {"name": "rotterdam", "priority": 1, "activity": "image", "max_off_nadir_deg": 45.0,
             "latitude_deg": 51.92, "longitude_deg": 4.48, "sun_elevation_deg": [10.0, 90.0]},
            {"name": "munich", "priority": 2, "activity": "image", "max_off_nadir_deg": 45.0,
             "latitude_deg": 48.14, "longitude_deg": 11.58},
        ],
        "activity_types": [
            {"name": "image", "kind": "acquisition", "pointing": "target", "duration_s": 20.0, "setup_s": 10.0,
             "boresight_b": [-1.0, 0.0, 0.0], "instruments": ["camera"], "power_w": 5.0},
            {"name": "downlink", "kind": "contact", "pointing": "station", "min_duration_s": 120.0,
             "setup_s": 30.0, "boresight_b": [-1.0, 0.0, 0.0], "transmitter": True},
            {"name": "star cal", "kind": "calibration", "pointing": "inertial", "duration_s": 300.0,
             "sigma_rn": [0.0, 0.0, 0.0]},
        ],
        "requests": [
            {"name": "cal-1", "activity": "star cal", "spacecraft": "eo-sat", "priority": 3},
        ],
        "stations": [{"station": "berlin-gs", "azimuth_mask": [[0.0, 5.0], [180.0, 15.0]], "setup_s": 60.0}],
        "spacecraft": [{"spacecraft": "eo-sat", "contact_activity": "downlink", "min_soc": 0.3}],
    }
    section.update(changes)
    return section


def scenario_dict(**changes) -> dict:
    data = base_dict()
    data["spacecraft"][0]["name"] = "eo-sat"
    data["spacecraft"][0]["comms_pointing"] = None
    data["operations"] = operations_dict(**changes)
    return data


def scenario(**changes) -> Scenario:
    built = Scenario.from_dict(copy.deepcopy(scenario_dict(**changes)))
    built.validate()
    return built
