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
"""Operations products (operations.exports, engine.ccsds_adm): the pass
schedule in RFC 5545 iCalendar, the activity and command schedules, the
station pointing predictions against the access analysis, OEM 3.0 and
AEM 2.0 structure and round trip, the report, provenance on each."""

import json

import numpy as np
import operations_fixtures as fixtures
import pytest

from spacemissionstudio.engine import ccsds_adm, ccsds_odm
from spacemissionstudio.operations import analysis, exports, geometry

_HORIZON = {"start_utc": "2030-01-01T08:30:00Z", "end_utc": "2030-01-02T08:30:00Z"}


@pytest.fixture(scope="module")
def planning():
    return analysis.plan(fixtures.scenario(horizon=_HORIZON))


def test_the_ics_file_follows_rfc_5545(planning):
    """CRLF line ends, no line over 75 octets, a VCALENDAR with VERSION 2.0
    and PRODID, one VEVENT per planned contact with UID, DTSTAMP and UTC
    DTSTART/DTEND, text escaped; with every pass, one per pass."""
    plan = planning.plan
    text = exports.passes_ics(plan, planning.opportunities, planning.timebase)
    assert text.endswith("\r\n") and "\n" not in text.replace("\r\n", "")
    lines = text.split("\r\n")[:-1]
    assert all(len(line.encode("utf-8")) <= 75 for line in lines)
    unfolded = text.replace("\r\n ", "").split("\r\n")[:-1]
    assert unfolded[:3] == ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//SpaceMissionStudio//Operations planning//EN"]
    assert unfolded[-1] == "END:VCALENDAR"
    events = [k for k, line in enumerate(unfolded) if line == "BEGIN:VEVENT"]
    contacts = [a for a in plan.activities if a.kind == "contact"]
    assert len(events) == len(contacts) > 0
    event = unfolded[events[0]:unfolded.index("END:VEVENT", events[0])]
    keys = {line.split(":", 1)[0] for line in event}
    assert {"UID", "DTSTAMP", "DTSTART", "DTEND", "SUMMARY"} <= keys
    start = next(line for line in event if line.startswith("DTSTART:")).split(":", 1)[1]
    assert len(start) == 16 and start.endswith("Z") and start[8] == "T"
    assert "\\," in next(line for line in event if line.startswith("DESCRIPTION:"))
    every = exports.passes_ics(plan, planning.opportunities, planning.timebase, all_passes=True)
    assert every.count("BEGIN:VEVENT") == len(planning.opportunities.passes)
    assert "X-SPACEMISSIONSTUDIO-PROVENANCE" in text


def test_the_activity_timeline_and_command_schedule(planning, tmp_path):
    """The activity JSON lists every activity with its predicted geometry
    and the unscheduled requests with their reasons; the command schedule
    is in release order, labelled a planning product, each activity's
    devices switched on and off around it."""
    plan, timebase = planning.plan, planning.timebase
    data = exports.activities_json(plan, timebase)
    assert data["format"] == "spacemissionstudio-activities" and len(data["activities"]) == len(plan.activities)
    assert all(a["start_utc"].endswith("Z") for a in data["activities"])
    assert data["provenance"]["note"].startswith("a planning product")
    schedule = exports.commands_json(plan, planning.scenario, timebase)
    times = [c["release_time_utc"] for c in schedule["requests"]]
    assert times == sorted(times) and "not telecommands" in schedule["terminology"]
    image = next(a for a in plan.activities if a.kind == "acquisition")
    mine = [c for c in schedule["requests"] if c["activity"] == image.id]
    assert [c["command"] for c in mine][:1] == ["SET_POINTING"] and mine[-1]["command"] == "SET_POINTING"
    on = next(c for c in mine if c["command"] == "INSTRUMENT_ON")
    off = next(c for c in mine if c["command"] == "INSTRUMENT_OFF")
    assert on["release_time_utc"] == image.start_utc and off["release_time_utc"] == image.end_utc
    paths = exports.write_all(tmp_path, planning)
    assert {p.name for p in paths} >= {"passes.csv", "passes.ics", "activities.csv", "activities.json",
                                       "commands.json", "commands.csv", "pointing.csv", "eo-sat.oem", "eo-sat.aem",
                                       "report.md"}
    for name in ("passes.csv", "activities.csv", "commands.csv", "pointing.csv"):
        sidecar = json.loads((tmp_path / f"{name}.provenance.json").read_text())
        assert sidecar["scenario_sha256"] == plan.provenance["scenario_sha256"] and sidecar["plan_sha256"]
    report = (tmp_path / "report.md").read_text()
    assert "## Not scheduled" in report and "planning product" in report


def test_the_oem_and_aem_are_ccsds_and_round_trip(planning):
    """The OEM of the planned trajectory validates as OEM 3.0; the AEM
    reads back (version 2.0, Q1 Q2 Q3 QC) to the planned attitude within
    1e-11; quaternions are unit and continuous."""
    plan = planning.plan
    text = exports.oem(plan, planning.geometry, planning.timebase, stride=6)["eo-sat"]
    assert not [i for i in ccsds_odm.validate(text) if i.level == "error"]
    assert ccsds_odm.read(text).kind == "OEM" and "CCSDS_OEM_VERS" in text and "= 3.0" in text.splitlines()[0]
    aem = exports.aem(plan, planning, stride=6)["eo-sat"]
    message = ccsds_adm.read(aem)
    assert message.header["CCSDS_AEM_VERS"] == "2.0" and len(message.segments) == 1
    segment = message.segments[0]
    assert segment.metadata["REF_FRAME_A"] == "EME2000" and segment.metadata["REF_FRAME_B"] == "SC_BODY_1"
    assert "QUATERNION_TYPE" not in aem and "ATTITUDE_DIR" not in aem
    q = segment.quaternions
    assert np.allclose(np.linalg.norm(q, axis=1), 1.0, atol=1e-11)
    assert np.all(np.einsum("ni,ni->n", q[1:], q[:-1]) > 0.0)
    from spacemissionstudio.operations.resources import SpacecraftModel, attitude_series

    model = SpacecraftModel(planning.scenario, planning.scenario.spacecraft[0], planning.geometry,
                            planning.scenario.operations, planning.slew_models["eo-sat"])
    planned = attitude_series(model, sorted(plan.of("eo-sat"), key=lambda a: a.start_s))
    index = np.arange(0, len(planning.geometry.time_s), 6)
    assert np.allclose(segment.dcm_bn[:len(index)], planned[index], atol=1e-11)
    with pytest.raises(ccsds_adm.AdmError, match="CCSDS_AEM_VERS"):
        ccsds_adm.read(aem.replace("= 2.0", "= 1.0", 1))
    with pytest.raises(ccsds_adm.AdmError, match="not AEM 2.0 metadata"):
        ccsds_adm.read(aem.replace("ATTITUDE_TYPE        = QUATERNION", "ATTITUDE_DIR = A2B\nATTITUDE_TYPE = QUATERNION"))


def test_quaternions_match_basilisk_s_euler_parameters():
    """dcm_to_quaternion against Basilisk's RigidBodyKinematics C2EP."""
    from Basilisk.utilities import RigidBodyKinematics as rbk

    rng = np.random.default_rng(4)
    for _ in range(50):
        sigma = rng.uniform(-1.0, 1.0, 3)
        sigma *= rng.uniform(0.0, 1.0) / np.linalg.norm(sigma)
        dcm = np.array(rbk.MRP2C(sigma))
        expected = np.array(rbk.C2EP(dcm))
        expected = expected if expected[0] >= 0.0 else -expected
        assert np.allclose(ccsds_adm.dcm_to_quaternion(dcm)[0], expected, atol=1e-12)


def test_pointing_predictions_match_the_access_analysis():
    """From a run's geometry, the predicted azimuth, elevation and range of
    each contact are the recorded access analysis's; the range rate is the
    range's derivative."""
    scenario = fixtures.scenario(horizon={"start_utc": "2030-01-01T08:30:00Z", "end_utc": "2030-01-01T09:00:00Z"})
    result = geometry.propagate(scenario, 1800.0 + 20.0, 10.0)
    planning = analysis.plan(scenario, result)
    rows = exports.pointing_rows(planning.plan, scenario, planning.opportunities, planning.timebase,
                                 planning.geometry)
    assert rows
    elevation = result.series["berlin-gs.access_to_eo-sat.elevation"]
    for row in rows[::7]:
        t = planning.timebase.to_sim(row[3])
        expected = np.degrees(np.interp(t, elevation.time_s, elevation.data[:, 0]))
        assert float(row[5]) == pytest.approx(expected, abs=1e-3)
    distance = np.array([float(r[6]) for r in rows])
    rate = np.array([float(r[7]) for r in rows])
    assert np.sign(rate[0]) < 0 < np.sign(rate[-1]) and np.all(np.abs(np.diff(distance)) < 80e3)
