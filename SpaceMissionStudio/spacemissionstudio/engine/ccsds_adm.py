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
"""CCSDS Attitude Ephemeris Messages (AEM), version 2.0, in KVN
(CCSDS 504.0-B-2, Attitude Data Messages, January 2024; decision O-20).

Written and read back by this tool: a header (``CCSDS_AEM_VERS = 2.0``,
``CREATION_DATE``, ``ORIGINATOR``, optional ``MESSAGE_ID`` and
``COMMENT`` lines), then segments of ``META_START`` ... ``META_STOP``
(``OBJECT_NAME``, ``OBJECT_ID``, ``CENTER_NAME``, ``REF_FRAME_A``,
``REF_FRAME_B``, ``TIME_SYSTEM``, ``START_TIME``, ``USEABLE_START_TIME``,
``USEABLE_STOP_TIME``, ``STOP_TIME``, ``ATTITUDE_TYPE``,
``INTERPOLATION_METHOD``, ``INTERPOLATION_DEGREE``) and ``DATA_START``
... ``DATA_STOP`` with one epoch and quaternion per line, components
``Q1 Q2 Q3 QC`` (scalar last; version 2 has no ``QUATERNION_TYPE`` or
``ATTITUDE_DIR``). The keywords and the order were taken from the CCSDS
NDM/XML 4.0.0 schema for AEM 2.0; the rotation is written as the
transformation from frame A (EME2000) to frame B (the body, SC_BODY_1),
the Euler parameters of ``[BN]`` (Schaub and Junkins), and each segment
says so in a ``COMMENT``.

Only ``ATTITUDE_TYPE = QUATERNION`` is written or read.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, UTC

import numpy as np

VERSION = "2.0"
ATTITUDE_TYPE = "QUATERNION"
_METADATA = ("OBJECT_NAME", "OBJECT_ID", "CENTER_NAME", "REF_FRAME_A", "REF_FRAME_B", "TIME_SYSTEM", "START_TIME",
             "USEABLE_START_TIME", "USEABLE_STOP_TIME", "STOP_TIME", "ATTITUDE_TYPE", "INTERPOLATION_METHOD",
             "INTERPOLATION_DEGREE")
_REQUIRED_METADATA = ("OBJECT_NAME", "OBJECT_ID", "REF_FRAME_A", "REF_FRAME_B", "TIME_SYSTEM", "START_TIME",
                      "STOP_TIME", "ATTITUDE_TYPE")
_KVN = re.compile(r"^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$")


class AdmError(ValueError):
    """An AEM cannot be written or read; the message says where."""


def dcm_to_quaternion(dcm: np.ndarray) -> np.ndarray:
    """Euler parameters ``(b0, b1, b2, b3)`` of each ``[BN]`` (n, 3, 3),
    Shepperd's method (Schaub and Junkins), b0 >= 0."""
    dcm = np.asarray(dcm, dtype=float).reshape(-1, 3, 3)
    out = np.empty((len(dcm), 4))
    for k, c in enumerate(dcm):
        trace = np.trace(c)
        squares = np.array([(1.0 + trace) / 4.0, (1.0 + 2.0 * c[0, 0] - trace) / 4.0,
                            (1.0 + 2.0 * c[1, 1] - trace) / 4.0, (1.0 + 2.0 * c[2, 2] - trace) / 4.0])
        i = int(np.argmax(squares))
        b = np.empty(4)
        b[i] = math.sqrt(squares[i])
        if i == 0:
            b[1], b[2], b[3] = ((c[1, 2] - c[2, 1]) / 4.0 / b[0], (c[2, 0] - c[0, 2]) / 4.0 / b[0],
                                (c[0, 1] - c[1, 0]) / 4.0 / b[0])
        elif i == 1:
            b[0], b[2], b[3] = ((c[1, 2] - c[2, 1]) / 4.0 / b[1], (c[0, 1] + c[1, 0]) / 4.0 / b[1],
                                (c[2, 0] + c[0, 2]) / 4.0 / b[1])
        elif i == 2:
            b[0], b[1], b[3] = ((c[2, 0] - c[0, 2]) / 4.0 / b[2], (c[0, 1] + c[1, 0]) / 4.0 / b[2],
                                (c[1, 2] + c[2, 1]) / 4.0 / b[2])
        else:
            b[0], b[1], b[2] = ((c[0, 1] - c[1, 0]) / 4.0 / b[3], (c[2, 0] + c[0, 2]) / 4.0 / b[3],
                                (c[1, 2] + c[2, 1]) / 4.0 / b[3])
        out[k] = b if b[0] >= 0.0 else -b
    return out


def quaternion_to_dcm(q: np.ndarray) -> np.ndarray:
    """``[BN]`` (n, 3, 3) of Euler parameters ``(b0, b1, b2, b3)``."""
    q = np.asarray(q, dtype=float).reshape(-1, 4)
    b0, b1, b2, b3 = q.T
    return np.stack([
        np.stack([b0 ** 2 + b1 ** 2 - b2 ** 2 - b3 ** 2, 2 * (b1 * b2 + b0 * b3), 2 * (b1 * b3 - b0 * b2)], 1),
        np.stack([2 * (b1 * b2 - b0 * b3), b0 ** 2 - b1 ** 2 + b2 ** 2 - b3 ** 2, 2 * (b2 * b3 + b0 * b1)], 1),
        np.stack([2 * (b1 * b3 + b0 * b2), 2 * (b2 * b3 - b0 * b1), b0 ** 2 - b1 ** 2 - b2 ** 2 + b3 ** 2], 1)], 1)


def _time(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%S.%f")


def _line(keyword: str, value: str) -> str:
    return f"{keyword:<20s} = {value}"


def write_aem(segments: Sequence[dict], *, originator: str = "SPACEMISSIONSTUDIO", comments: Sequence[str] = (),
              creation: datetime | None = None, message_id: str | None = None) -> str:
    """An AEM. Each segment: ``object_name``, ``object_id``, ``epochs``
    (UTC datetimes), ``dcm_bn`` (n, 3, 3) and optional ``center_name``,
    ``ref_frame_a`` (EME2000), ``ref_frame_b`` (SC_BODY_1),
    ``interpolation`` and ``interpolation_degree``, ``comments``."""
    lines = [_line("CCSDS_AEM_VERS", VERSION)]
    lines += [f"COMMENT {c}" for c in comments]
    lines.append(_line("CREATION_DATE", _time(creation or datetime.now(UTC).replace(tzinfo=None, microsecond=0))))
    lines.append(_line("ORIGINATOR", originator))
    if message_id:
        lines.append(_line("MESSAGE_ID", message_id))
    for segment in segments:
        epochs = list(segment["epochs"])
        if not epochs:
            raise AdmError(f"AEM segment for {segment['object_name']}: no attitudes to write")
        quaternions = dcm_to_quaternion(segment["dcm_bn"])
        for k in range(1, len(quaternions)):  # continuous in sign, as an interpolator needs
            if np.dot(quaternions[k], quaternions[k - 1]) < 0.0:
                quaternions[k] = -quaternions[k]
        lines += ["", "META_START", _line("OBJECT_NAME", str(segment["object_name"])),
                  _line("OBJECT_ID", str(segment["object_id"]))]
        if segment.get("center_name"):
            lines.append(_line("CENTER_NAME", str(segment["center_name"]).upper()))
        lines += [_line("REF_FRAME_A", segment.get("ref_frame_a", "EME2000")),
                  _line("REF_FRAME_B", segment.get("ref_frame_b", "SC_BODY_1")),
                  _line("TIME_SYSTEM", "UTC"), _line("START_TIME", _time(epochs[0])),
                  _line("USEABLE_START_TIME", _time(epochs[0])), _line("USEABLE_STOP_TIME", _time(epochs[-1])),
                  _line("STOP_TIME", _time(epochs[-1])), _line("ATTITUDE_TYPE", ATTITUDE_TYPE)]
        if segment.get("interpolation"):
            lines += [_line("INTERPOLATION_METHOD", str(segment["interpolation"]).upper()),
                      _line("INTERPOLATION_DEGREE", str(int(segment.get("interpolation_degree", 1))))]
        lines.append("META_STOP")
        lines += ["", "DATA_START"]
        lines += [f"COMMENT {c}" for c in segment.get("comments", ())]
        lines.append("COMMENT the quaternion of the rotation from REF_FRAME_A to REF_FRAME_B ([BN]), scalar last")
        for epoch, q in zip(epochs, quaternions):
            lines.append(" ".join([_time(epoch)] + [f"{float(x):.12f}" for x in (q[1], q[2], q[3], q[0])]))
        lines.append("DATA_STOP")
    text = "\n".join(lines) + "\n"
    read(text)  # what is written reads back
    return text


@dataclass
class AemSegment:
    metadata: dict
    epochs: list = field(default_factory=list)
    quaternions: np.ndarray | None = None  # (n, 4) b0, b1, b2, b3 (scalar first, as Schaub and Junkins)
    comments: list = field(default_factory=list)

    @property
    def dcm_bn(self) -> np.ndarray:
        return quaternion_to_dcm(self.quaternions)


@dataclass
class AemMessage:
    header: dict
    segments: list
    comments: list = field(default_factory=list)


def read(text: str) -> AemMessage:
    """An AEM 2.0 in KVN; refuses anything else with the line number."""
    lines = text.splitlines()
    header, comments, segments = {}, [], []
    state, current, data = "header", None, []
    for number, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("COMMENT"):
            (current.comments if current is not None else comments).append(line[7:].strip())
            continue
        if line in ("META_START", "META_STOP", "DATA_START", "DATA_STOP"):
            if line == "META_START":
                if state not in ("header", "after_data"):
                    raise AdmError(f"line {number}: META_START out of place")
                current, state = AemSegment({}), "meta"
            elif line == "META_STOP":
                if state != "meta":
                    raise AdmError(f"line {number}: META_STOP out of place")
                missing = [k for k in _REQUIRED_METADATA if k not in current.metadata]
                if missing:
                    raise AdmError(f"line {number}: metadata misses {missing[0]}")
                if current.metadata["ATTITUDE_TYPE"] != ATTITUDE_TYPE:
                    raise AdmError(f"line {number}: ATTITUDE_TYPE {current.metadata['ATTITUDE_TYPE']} is not read "
                                   "(QUATERNION only)")
                state = "between"
            elif line == "DATA_START":
                if state != "between":
                    raise AdmError(f"line {number}: DATA_START out of place")
                state, data = "data", []
            else:
                if state != "data":
                    raise AdmError(f"line {number}: DATA_STOP out of place")
                current.quaternions = np.array([[q[3], q[0], q[1], q[2]] for _e, q in data]) if data \
                    else np.zeros((0, 4))
                current.epochs = [e for e, _q in data]
                segments.append(current)
                state = "after_data"
            continue
        match = _KVN.match(line)
        if state == "header":
            if not match:
                raise AdmError(f"line {number}: expected KEYWORD = value")
            header[match.group(1)] = match.group(2)
        elif state == "meta":
            if not match or match.group(1) not in _METADATA:
                raise AdmError(f"line {number}: {line.split('=')[0].strip()!r} is not AEM 2.0 metadata")
            current.metadata[match.group(1)] = match.group(2)
        elif state == "data":
            parts = line.split()
            if len(parts) != 5:
                raise AdmError(f"line {number}: a quaternion line has an epoch and four numbers")
            try:
                epoch = datetime.strptime(parts[0].rstrip("Z"), "%Y-%m-%dT%H:%M:%S.%f")
                q = [float(v) for v in parts[1:]]
            except ValueError:
                raise AdmError(f"line {number}: cannot read {line!r}") from None
            if abs(math.sqrt(sum(v * v for v in q)) - 1.0) > 1e-6:
                raise AdmError(f"line {number}: the quaternion is not of unit norm")
            data.append((epoch, q))
        else:
            raise AdmError(f"line {number}: {line!r} outside a segment")
    if header.get("CCSDS_AEM_VERS") != VERSION:
        raise AdmError(f"CCSDS_AEM_VERS is {header.get('CCSDS_AEM_VERS')!r}; this reads {VERSION}")
    for keyword in ("CREATION_DATE", "ORIGINATOR"):
        if keyword not in header:
            raise AdmError(f"the header misses {keyword}")
    if state != "after_data" or not segments:
        raise AdmError("the message ends inside a segment, or has none")
    return AemMessage(header, segments, comments)


def aem_from_result(result, epoch_utc: str, spacecraft: Sequence[str], stride: int = 1, **kwargs) -> dict[str, str]:
    """One AEM per spacecraft from a run's ``attitude_sigma_BN`` (MRP), UTC
    epochs from the run's TDB time."""
    from ..analyses.run_geometry import mrp_to_dcm
    from . import time_system as ts

    messages = {}
    for name in spacecraft:
        series = result.series.get(f"{name}.attitude_sigma_BN")
        if series is None or not len(series.time_s):
            raise AdmError(f"{name}: the run recorded no attitude, so there is no AEM to write")
        index = np.arange(0, len(series.time_s), max(1, int(stride)))
        epochs = ts.elapsed_to_utc(epoch_utc, series.time_s[index])
        segment = {"object_name": name, "object_id": "UNKNOWN", "center_name": "EARTH", "epochs": list(epochs),
                   "dcm_bn": mrp_to_dcm(np.asarray(series.data)[index]), "interpolation": "LINEAR",
                   "interpolation_degree": 1, "comments": ["Produced by a SpaceMissionStudio (Basilisk) simulation; "
                                                           "EME2000 is SPICE J2000"]}
        header = dict(kwargs)
        provenance = getattr(result, "provenance", None)
        if provenance is not None and "comments" not in header:
            header["comments"] = provenance.summary_lines()
        messages[name] = write_aem([segment], **header)
    return messages
