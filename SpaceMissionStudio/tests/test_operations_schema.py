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
"""The scenario's ``operations`` section (schema.operations, decision
O-06): reading, validation against the scenario, saving only what is
set, renames following, recording for the planner. No Basilisk."""

import copy

import operations_fixtures as fixtures
import pytest

from spacemissionstudio.engine.series_names import expected_series_names
from spacemissionstudio.schema import operations as ops
from spacemissionstudio.schema.references import (find_ground_station_references, find_spacecraft_references,
                                                  rename_ground_station, rename_spacecraft)
from spacemissionstudio.schema.scenario import Scenario, ScenarioValidationError


def _invalid(match: str, **changes):
    with pytest.raises(ScenarioValidationError, match=match):
        fixtures.scenario(**changes)


def test_the_section_reads_validates_and_saves_only_what_it_sets():
    """A scenario with the section loads, validates, and saves it without
    the values left at their defaults; loading the saved form gives the
    same section. A scenario without one saves no 'operations' key."""
    scenario = fixtures.scenario()
    section = scenario.operations
    assert isinstance(section, ops.OperationsConfig) and section.version == ops.OPERATIONS_VERSION
    assert [t.name for t in section.targets] == ["rotterdam", "munich"]
    assert section.planned("eo-sat").agility.source == "controller"
    saved = scenario.to_dict()["operations"]
    assert saved["geometry"] == {"source": "analytic"}  # step_s left at its convention
    assert "scheduler" not in saved and "verification" not in saved
    assert "kind" not in saved["targets"][0] and "acquisitions" not in saved["targets"][0]
    assert saved["spacecraft"] == [{"spacecraft": "eo-sat", "contact_activity": "downlink", "min_soc": 0.3}]
    again = Scenario.from_dict(copy.deepcopy(scenario.to_dict()))
    again.validate()
    assert again.operations == section
    plain = fixtures.base_dict()
    assert "operations" not in Scenario.from_dict(plain).to_dict()


@pytest.mark.parametrize("changes, match", [
    ({"version": 2}, "version 2 is not one this version reads"),
    ({"horizon": {"start_utc": "2029-12-31T00:00:00Z", "end_utc": "2030-01-02T00:00:00Z"}}, "before the scenario"),
    ({"horizon": {"start_utc": "2030-01-01T09:00:00Z", "end_utc": "2030-06-01T00:00:00Z"}}, "longer than 104"),
    ({"horizon": {"start_utc": "2030-01-02T09:00:00Z", "end_utc": "2030-01-01T10:00:00Z"}}, "start before it ends"),
    ({"spacecraft": []}, "at least one spacecraft"),
    ({"spacecraft": [{"spacecraft": "nobody"}]}, "'nobody' is not in the scenario"),
    ({"stations": [{"station": "nowhere"}]}, "'nowhere' is not a ground station"),
    ({"stations": [{"station": "berlin-gs", "azimuth_mask": [[90.0, 5.0], [10.0, 5.0]]}]}, "increasing azimuths"),
    ({"geometry": {"source": "guess"}}, "source 'guess'"),
])
def test_bad_sections_are_refused_with_the_place_named(changes, match):
    """Version, horizon, spacecraft, stations and masks are checked against
    the scenario."""
    _invalid(match, **changes)


def test_targets_activity_types_and_requests_are_checked():
    """A target needs an acquisition type, a polygon its cell size and a
    field of view, a contact a minimum duration, a target pointing a
    boresight, an instrument that exists; a maneuver a fixed time; no
    mission value has a default (O-07)."""
    base = fixtures.operations_dict()
    targets = copy.deepcopy(base["targets"])
    targets[0]["activity"] = "downlink"
    _invalid("is not an acquisition type", targets=targets)
    targets = copy.deepcopy(base["targets"])
    targets.append({"name": "polder", "kind": "polygon", "priority": 2, "activity": "image",
                    "max_off_nadir_deg": 20.0, "vertices_deg": [[52.0, 5.0], [52.5, 5.0], [52.5, 5.8]]})
    _invalid("cell_km is needed", targets=targets)
    targets[-1]["cell_km"] = 2.0
    _invalid("needs the imager's field of view", targets=targets)
    targets[-1]["vertices_deg"] = [[0.0, 170.0], [1.0, -170.0 + 360.0 - 10.0], [1.0, -175.0]]
    _invalid("antimeridian|field of view", targets=targets)
    types = copy.deepcopy(base["activity_types"])
    del types[1]["min_duration_s"]
    _invalid("min_duration_s is needed", activity_types=types)
    types = copy.deepcopy(base["activity_types"])
    del types[0]["boresight_b"]
    _invalid("needs equipment or boresight_b", activity_types=types)
    types = copy.deepcopy(base["activity_types"])
    types[0]["instruments"] = ["lidar"]
    _invalid("instrument 'lidar' is not in its data_handling", activity_types=types)
    types = copy.deepcopy(base["activity_types"])
    del types[0]["duration_s"]
    _invalid("duration_s is needed", activity_types=types)
    types = copy.deepcopy(base["activity_types"])
    types.append({"name": "raise", "kind": "maneuver", "pointing": "sun", "duration_s": 60.0,
                  "delta_v_m_s": [0.1, 0.0, 0.0]})
    requests = copy.deepcopy(base["requests"]) + [{"name": "burn", "activity": "raise", "spacecraft": "eo-sat",
                                                  "priority": 1}]
    _invalid("a maneuver needs at_utc", activity_types=types, requests=requests)
    requests[-1]["at_utc"] = "2030-01-03T00:00:00Z"
    _invalid("at_utc is outside the horizon", activity_types=types, requests=requests)


def test_planned_spacecraft_settings_are_checked_against_the_spacecraft():
    """'controller' agility needs attitude control, a minimum state of
    charge a power budget; a planned spacecraft cannot also have
    comms_pointing; contingency pairs come together."""
    data = fixtures.scenario_dict()
    data["spacecraft"][0]["power"] = None
    data["spacecraft"][0]["data_handling"] = None  # it draws power
    with pytest.raises(ScenarioValidationError, match="min_soc needs a power budget"):
        Scenario.from_dict(data).validate()
    _invalid("give safe_mode_soc and recover_soc together",
             spacecraft=[{"spacecraft": "eo-sat", "contingency": {"safe_mode_soc": 0.2}}])
    _invalid("recover_soc must be above", spacecraft=[{"spacecraft": "eo-sat", "contingency": {
        "safe_mode_soc": 0.4, "recover_soc": 0.3}}])
    _invalid("max_rate_deg_s is needed", spacecraft=[{"spacecraft": "eo-sat", "agility": {"source": "limits"}}])
    data = fixtures.scenario_dict()
    data["spacecraft"][0]["fsw_mode"] = None
    data["spacecraft"][0]["actuators"] = []
    data["spacecraft"][0]["magnetic_momentum_management"] = None
    with pytest.raises(ScenarioValidationError, match="agility 'controller' needs fsw_mode"):
        Scenario.from_dict(data).validate()


def test_renaming_a_spacecraft_or_station_follows_into_the_section():
    """Renames reach the planned spacecraft, requests, locked activities,
    station settings and what-if events; the references are listed so a
    deletion is refused while they exist."""
    scenario = fixtures.scenario(locked=[{"id": "l1", "spacecraft": "eo-sat", "activity": "downlink",
                                          "station": "berlin-gs", "start_utc": "2030-01-01T10:00:00Z",
                                          "end_utc": "2030-01-01T10:05:00Z"}],
                                 what_if=[{"kind": "lost_pass", "station": "berlin-gs", "spacecraft": "eo-sat",
                                           "at_utc": "2030-01-01T10:00:00Z"}])
    paths = [r.path for r in find_spacecraft_references(scenario, "eo-sat")]
    assert "operations.spacecraft[0].spacecraft" in paths and "operations.requests 'cal-1'.spacecraft" in paths
    assert "operations.locked[0].spacecraft" in paths and "operations.what_if[0].spacecraft" in paths
    rename_spacecraft(scenario, "eo-sat", "eo-2")
    rename_ground_station(scenario, "berlin-gs", "bln")
    section = scenario.operations
    assert section.spacecraft[0].spacecraft == "eo-2" and section.requests[0].spacecraft == "eo-2"
    assert section.locked[0].spacecraft == "eo-2" and section.locked[0].station == "bln"
    assert section.stations[0].station == "bln" and section.what_if[0].station == "bln"
    assert [r.path for r in find_ground_station_references(scenario, "bln")][:1] == ["operations.stations[0].station"]
    scenario.validate()


def test_a_run_records_the_earth_orientation_and_the_sun_for_the_planner():
    """The series the planner reads from a run (decision O-04) are in the
    prediction of a run's series."""
    names = expected_series_names(fixtures.scenario())
    assert "ephemeris.earth.dcm_PN" in names and "ephemeris.sun.position_N" in names
    assert "berlin-gs.access_to_eo-sat.elevation" in names


def test_what_if_events_name_what_they_change():
    """Each what-if kind asks for what it needs; names must exist."""
    _invalid("needs station", what_if=[{"kind": "lost_pass", "spacecraft": "eo-sat",
                                        "at_utc": "2030-01-01T10:00:00Z"}])
    _invalid("'ghost' is not a target or request", what_if=[{"kind": "extra_request", "name": "ghost"}])
    _invalid("needs delay_s", what_if=[{"kind": "delayed_maneuver", "name": "cal-1"}])
    scenario = fixtures.scenario(what_if=[{"kind": "station_outage", "station": "berlin-gs",
                                           "at_utc": "2030-01-01T10:00:00Z", "until_utc": "2030-01-01T12:00:00Z"}])
    assert scenario.operations.what_if[0].kind == "station_outage"
