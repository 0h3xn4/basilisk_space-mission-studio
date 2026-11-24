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
"""Shared data of the budgets tests: a small ``budgets`` section (the
design note's example, invented values) and a template carrying a
section, saved to a file. The SBS ``microsat_250kg_clean`` example's
section is the file ``tests/data/budgets/sbs_microsat_250kg_clean.json``."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from spacemissionstudio.schema.scenario import Scenario

TEMPLATES = Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates"
STARTER = TEMPLATES / "22_starter_first_leo_satellite.json"
MODEL_TEMPLATE = TEMPLATES / "32_smallsat_design_checks.json"
SBS_CLEAN = Path(__file__).resolve().parent / "data" / "budgets" / "sbs_microsat_250kg_clean.json"


def sourced(value, source: str = "data sheet rev B") -> dict:
    return {"value": value, "source": source}


SECTION = {
    "version": 2,
    "buses": [{"name": "main", "converter_efficiency": sourced(0.9, "PCDU data sheet")}],
    "distribution_loss": sourced(0.02, "harness estimate"),
    "power_margins": [
        {"maturity": "estimated", "percent": sourced(20, "company rule 4.2")},
        {"maturity": "existing", "percent": sourced(5, "company rule 4.2")},
    ],
    "system_power_margin_percent": sourced(10, "company rule 4.3"),
    "equipment": [
        {"name": "OBC", "subsystem": "DHS", "mass_column": "electronics", "bus": "main", "maturity": "existing",
         "mass_kg": sourced(1.2),
         "power_modes": [{"name": "on", "average_w": sourced(4.0), "peak_w": sourced(5.5)},
                         {"name": "off", "average_w": sourced(0.0, "switched off")}]},
        {"name": "camera", "subsystem": "PL", "bus": "main", "maturity": "estimated", "mass_kg": sourced(3.0),
         "power_modes": [{"name": "imaging", "average_w": sourced(12.0), "peak_w": sourced(15.0),
                          "duty_cycle": 0.5},
                         {"name": "off", "average_w": sourced(0.0, "switched off")}]},
        {"name": "harness", "subsystem": "STRUCT", "mass_column": "wire_harness", "maturity": "estimated",
         "mass_kg": sourced(None, "TBD")},
    ],
    "modes": [
        {"name": "nominal", "duty_cycle": 0.8, "units": {"OBC": "on", "camera": "off"}},
        {"name": "imaging", "duty_cycle": 0.2, "units": {"OBC": "on", "camera": "imaging"}},
    ],
}


def section(**changes) -> dict:
    """A copy of :data:`SECTION` with top-level keys replaced."""
    data = copy.deepcopy(SECTION)
    data.update(copy.deepcopy(changes))
    return data


def scenario_data(budgets=None, template: Path = STARTER) -> dict:
    """The template's JSON with ``budgets`` on its first spacecraft."""
    data = json.loads(template.read_text(encoding="utf-8"))
    data["spacecraft"][0]["budgets"] = copy.deepcopy(SECTION if budgets is None else budgets)
    return data


def scenario(budgets=None, template: Path = STARTER) -> Scenario:
    """The template's scenario with ``budgets`` on its first spacecraft, validated."""
    result = Scenario.from_dict(scenario_data(budgets, template))
    result.validate()
    return result


def sbs_clean_section() -> dict:
    """The SBS microsat_250kg_clean example as a budgets section."""
    return json.loads(SBS_CLEAN.read_text(encoding="utf-8"))
