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

"""Whether a case of a Monte Carlo batch can run again (plan A3, decision
MC-17), without Basilisk: the window asks before it clears the shown run's
views, on the GUI thread, and ``engine.monte_carlo.case_parameters`` asks
the same before it builds the case.

A case is refused when the folder has no record of the batch's scenario,
when the scenario's SHA-256 is not the one the batch recorded, when the
batch has no such case, or when the case's ``run<N>.json`` is missing or
cannot be read. Each refusal says why and what to do."""

from __future__ import annotations

import json
from pathlib import Path

from .. import output_provenance


def batch_scenario_hash(archive_dir: Path) -> tuple[str, str] | str:
    """(the batch's ``scenario_sha256``, its ``scenario_file`` or "") from
    the folder's ``archive.provenance.json``, or the refusal's text."""
    path = archive_dir / "archive.provenance.json"
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return (f"{archive_dir} has no archive.provenance.json, so the scenario of its batch is not known and a "
                "case cannot be checked against it. Choose the folder of a finished batch.")
    except (OSError, ValueError) as exc:
        return f"could not read {path}: {exc}"
    digest = record.get("scenario_sha256") if isinstance(record, dict) else None
    if not isinstance(digest, str) or not digest:
        return f"{path} does not record the scenario's SHA-256, so a case cannot be checked against the scenario."
    name = record.get("scenario_file")
    return digest, name if isinstance(name, str) else ""


def batch_seed(archive_dir: str | Path) -> int | None:
    """The batch seed (``monte_carlo_seed``) the folder's
    ``archive.provenance.json`` records, or None: a batch without one
    (Basilisk's own seeding), made before it was recorded (2.14.2 and
    earlier), or a record that cannot be read (decision MC-20)."""
    try:
        record = json.loads((Path(archive_dir) / "archive.provenance.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    seed = record.get("monte_carlo_seed") if isinstance(record, dict) else None
    return seed if isinstance(seed, int) and not isinstance(seed, bool) else None


def read_case(scenario, archive_dir: str | Path, case: int) -> tuple[dict, str] | str:
    """(the entries of ``run<case>.json``, the batch's scenario SHA-256) when
    ``case`` of the batch in ``archive_dir`` can run again with
    ``scenario``, else the refusal's text (module docstring)."""
    archive_dir = Path(archive_dir)
    found = batch_scenario_hash(archive_dir)
    if isinstance(found, str):
        return found
    batch_digest, batch_file = found
    digest = output_provenance.scenario_sha256(scenario)
    if digest != batch_digest:
        named = f" ({batch_file})" if batch_file else ""
        return (f"Case {case} was not run: the scenario changed since the batch in {archive_dir} (scenario SHA-256 "
                f"{digest} now, {batch_digest} at the batch). With a changed scenario the same case would be a "
                f"different case. Open the batch's own scenario{named} as it was when the batch ran, then run the "
                "case again.")
    runs = scenario.monte_carlo.num_runs
    if isinstance(case, bool) or not isinstance(case, int) or not 0 <= case < runs:
        return f"the batch has no case {case}: its cases are 0 to {runs - 1}"
    path = archive_dir / f"run{case}.json"
    try:
        params = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return (f"{archive_dir} has no run{case}.json: case {case} did not start in this batch (a cancelled batch "
                "keeps only the cases it started)")
    except (OSError, ValueError) as exc:
        return f"could not read {path}: {exc}"
    if not isinstance(params, dict):
        return f"{path} is not the parameter file of a case"
    return params, batch_digest


def case_refusal(scenario, archive_dir: str | Path, case: int) -> str:
    """Why ``case`` of the batch in ``archive_dir`` cannot run again with
    ``scenario``, or "" when it can."""
    found = read_case(scenario, archive_dir, case)
    return found if isinstance(found, str) else ""
