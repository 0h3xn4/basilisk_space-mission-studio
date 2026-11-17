# System Budget Studio in SpaceMissionStudio: merge plan

**Status:** a proposal for the owner's review (2026-11-17). The owner
answered the open questions on 2026-11-17 (section 7). No code moves
until the owner accepts this plan.

System Budget Studio (`0h3xn4/system-budget-studio`, Apache-2.0, last
release 2.15.1) is an offline tool for the system budgets of a satellite:
power, mass, link, thermal, delta-v, pointing and slews, each with
margins and a source for every number. SpaceMissionStudio covers a much
larger part of mission analysis, and several of its models overlap with
System Budget Studio. The owner decided (2026-11-17) to stop the two-tool
approach: System Budget Studio becomes a feature of SpaceMissionStudio.

## 1. The owner's decisions

1. **One tool.** The budgets move into SpaceMissionStudio.
2. **SpaceMissionStudio wins every overlap.** Where both tools compute
   the same thing, the SpaceMissionStudio model stays and the System
   Budget Studio model is not ported. System Budget Studio brings only
   what SpaceMissionStudio does not have. That part is built on the data
   structures of SpaceMissionStudio, not next to them.
3. **Licence.** Code that moves becomes EUPL-1.2, the same as the rest of
   the app (section 6).
4. **Existing projects open.** A one-way import reads a System Budget
   Studio project folder into a SpaceMissionStudio scenario (phase 6).
5. **System Budget Studio is frozen at 2.15.1.** It gets fixes only, and
   no new features, until the merge is done. It is then retired (phase 7).

## 2. Why

- **High-precision propagation (HPOP).** A tester of System Budget Studio
  2.11.0 asked for it. System Budget Studio uses SGP4 only, and its spec
  says "do not write your own propagator". SpaceMissionStudio propagates
  with Basilisk: spherical harmonics, NRLMSISE-00 drag, SRP and third
  bodies. The merge solves this request with no new propagator.
- **One set of inputs.** Today the orbit, the passes and the eclipses are
  typed twice, or are passed through an interim CSV format (System
  Budget Studio D-055). That format was never checked against real
  SpaceMissionStudio output, which has no `orbit.csv`, `eclipse.csv` or
  `passes_*.csv`.
- **The budgets complete SpaceMissionStudio.** SpaceMissionStudio has no
  equipment list of its own with power and mass per unit, power modes
  only through the IDM-CIC import (which reduces them to one bus load),
  no static power budget, no Eb/N0 tables per modulation and coding, no "TBD"
  placeholder state, and no PDF or XLSX report.

## 3. Inventory and overlap

"SMS" is SpaceMissionStudio, "SBS" is System Budget Studio. Paths are
relative to `SpaceMissionStudio/spacemissionstudio/` or to
`system-budget-studio/src/`.

| Domain | SpaceMissionStudio today | System Budget Studio today | Decision |
| --- | --- | --- | --- |
| Orbit propagation | Basilisk numerical (`engine/service.py`); a TLE gives only the initial state (`engine/tle.py`) | SGP4 on mean elements or a TLE (`budget_core/environment/elements.py`) | **SMS.** Not ported. |
| Orbit design | Orbit set-up with sun-synchronous options (`gui/orbit_ic_widget.py`, `config/parameters.py`) | Orbit designer: sun-synchronous, repeat track, frozen (`budget_core/orbit_design.py`) | **SMS.** Port only a missing design helper, if the check in phase 1 finds one. |
| Eclipses, passes | Basilisk `eclipse` and `groundLocation`, `engine/shadows.py`, `engine/events.py` | Own geometry on SGP4 (`environment/`) | **SMS.** Not ported. |
| Data volume | Basilisk data chain (`engine/data_handling.py`, `engine/data_budget.py`) | Volume per pass from the link rates (`budget_core/link/`) | **SMS.** Not ported. |
| Power, time domain | Basilisk panel, sink and battery; a constant bus load plus the instrument and transmitter powers (`schema/scenario.py` `PowerConfig`). The IDM-CIC import reads each unit's power modes and the system modes with their duty cycles (`idm/power.py`, since 2.3.0) and writes their duty-cycle average as the bus load (`idm_import.py` `PowerPlan`) | Load per mode from the equipment list, modes switched by scenario rules (eclipse, pass, site), battery and array model (`budget_core/power/`) | **SMS** for the battery, the array and the solver. **Port:** the equipment list and the power modes, built on the IDM-CIC import's power modes (owner, 2026-11-17): one equipment list and one power-mode model, which the IDM-CIC import and the System Budget Studio import both fill; fed into the Basilisk power sinks (phase 2). |
| Power, static budget | Not found | Orbit-average power per subsystem and per mode, with margins (`power/static_budget.py`) | **Port** (phase 1). |
| Mass budget | Dry mass, growth allowance per maturity (AIAA S-120), system margin, launch mass and limit (`analyses/mass_budget.py`) | The same quantities, from the equipment list (`mass/static_mass.py`) | **SMS.** Not ported. The SBS equipment list feeds the SMS mass budget. |
| Mass properties | `model3d/mass_properties.py` | `mass/mass_properties.py` | **SMS.** Not ported. |
| Margin policy | Mass only (`config/materials.py` `MassMarginPolicy`) | Mass and power ratio per maturity class, each with a source (`config/margin_policy.yaml`) | **SMS** policy, **extended** with a power margin per class (phase 1). |
| Link budget | Eb/N0 from EIRP, FSPL, pointing loss, optional ITU-R P.676 gas loss and G/T against one `required_ebno_db` (`engine/link_budget.py`) | The same chain, plus an Eb/N0 table per modulation and coding with target BER or FER, and an attenuation table (`link/`, `config/ebn0_table.yaml`, `config/attenuation_table.yaml`) | **SMS** chain. **Port:** the Eb/N0 table and the attenuation table as sourced inputs to it (phase 3). |
| Thermal | Nodal solver with hot, cold and nominal cases and sweeps (`thermal/`) | Static and steady-state single node, beta sweep (`thermal/`) | **SMS.** Not ported. |
| Propellant, delta-v | ESA AD10 propellant budget from the run (`engine/propellant_budget.py`) | Delta-v budget per manoeuvre with the rocket equation (`propulsion/budget.py`) | **SMS.** Not ported. |
| Pointing | Basilisk FSW modes, planner slews (`engine/fsw.py`, `operations/attitude.py`) | Hold power and accuracy per pointing mode, slew time against actuator torque (`pointing/budget.py`) | **SMS** for the attitude. **Port:** the hold power per pointing mode into the power modes (phase 4). |
| Mode and timeline logic | Mission sequence and operations planner (`schema/command.py`, `operations/`) | Scenario rules with conditions and pointing layers (`scenario/timeline.py`, D-275) | **SMS.** Not ported. The power modes follow the SMS mission sequence. |
| IDM-CIC import | `idm/`, `idm_import.py` | `budget_core/idm/` | **SMS.** Not ported. |
| Sourced values | `ValueMark` with value, source and reason; parameter registry with a source (`schema/scenario.py`, `config/registry.py`) | Every number has `value` and `source`; unknown is `source: TBD`, a placeholder that blocks a result | **SMS** structure, **extended** with the placeholder state (phase 1, open question Q5). |
| Reports | CSV, JSON, PNG and SVG, CCSDS, Markdown, each with provenance | PDF, DOCX, XLSX and CSV budget reports | **SMS** formats first. PDF, XLSX and DOCX only if the owner accepts the dependencies (Q2). |
| Problems | Problems panel, `validate_all` | Problem catalogue; messages never contain project values (D-207) | **SMS.** The budget problems follow SpaceMissionStudio's style and may show values (owner, 2026-11-17, Q6); D-207 is not carried over. |

## 4. What moves, and how

The code does not move as a package. System Budget Studio uses pydantic,
ruamel.yaml, pint, openpyxl, reportlab and python-docx; SpaceMissionStudio
uses dataclasses, PyYAML and NumPy, and its rule is "prefer no new
dependency". So each feature is **re-implemented** in the SpaceMissionStudio
structure. The System Budget Studio code, its tests and its reference
cases are the specification. Each reference test of System Budget Studio
that covers a ported feature is ported with it, with the same numbers.

The scenario gets one new optional section, `budgets`, in schema
version 5 with a migration from 4. An empty or missing section changes no
result, so the 36 golden files stay the same.

```json
"budgets": {
  "equipment": [ { "id": "obc", "subsystem": "dhs", "maturity": "off_the_shelf",
                   "mass_kg": {"value": 1.2, "source": "data sheet"},
                   "power_w": {"nominal": {"value": 4.0, "source": "data sheet"}} } ],
  "power_modes": { "nominal": { "units": { "obc": 1.0 } } },
  "margin_policy": "aiaa_s120_2006",
  "link_tables": { "ebn0": [], "attenuation": [] }
}
```

The shape above is a sketch for the review, not the final format. Phase 1
fixes it, and `compliance/docs/ICD_scenario_fields.md` is regenerated
from it. The equipment list is related to the mounted equipment of the 3D
model (`MountedEquipmentConfig`). Phase 1 decides whether it extends that
type or refers to it by id, so a unit is never typed twice.

## 5. Phases

Each phase is one or more SpaceMissionStudio releases. Each phase has its
own decisions entry, CHANGELOG lines, user manual pages and tests, and
leaves the golden files unchanged.

| Phase | Content | Depends on |
| --- | --- | --- |
| 0 | This plan accepted. The "UI only during the overhaul" hard rule in `SpaceMissionStudio/CLAUDE.md` is replaced by a rule for the merge (Q4). System Budget Studio gets a note in its README: frozen, continues in SpaceMissionStudio. | — |
| 1 | **Equipment list and static budgets.** The `budgets` section (schema 5). The equipment list with sourced mass and power per mode, the placeholder state, the power margin per maturity class. The static power budget per subsystem and per mode. The equipment list feeds the existing mass budget. A **Budgets** area in the navigation rail (Q3), with an Equipment grid and a Power page. | 0 |
| 2 | **Power modes in the run.** The power mode load becomes a Basilisk power sink, switched by the mission sequence. The battery and the array stay Basilisk's. The Power page shows the energy balance of the run. | 1 |
| 3 | **Link tables.** The Eb/N0 table per modulation and coding with target BER or FER, and the attenuation table, as sourced inputs to `engine/link_budget.py`. One `required_ebno_db` stays valid as before. | 1 |
| 4 | **Pointing load.** The hold power of each attitude mode adds to the power mode it runs in. | 2 |
| 5 | **Budget report.** One budget report in CSV and Markdown with provenance. PDF and XLSX only if Q2 is accepted. | 1–4 |
| 6 | **Import of a System Budget Studio project.** `spacemissionstudio import-sbs <folder>` and a menu entry. It reads the YAML files read-only with PyYAML, maps the orbit, the sites, the equipment, the modes, the links and the tables, and writes a list of what it cannot map. It never guesses a missing number: a missing value becomes a placeholder. The five System Budget Studio example projects are the test cases. | 1–3 |
| 7 | **Retire System Budget Studio.** A last release (2.16.0) that points to SpaceMissionStudio, then the repository is archived. | 6 |

**Size.** Phases 1 and 2 are the large ones. Each is about the size of a
thermal milestone. Phases 3, 4, 5 and 7 are small. Phase 6 is medium.

## 6. Licence

- System Budget Studio is Apache-2.0, with one licensor: the owner.
  SpaceMissionStudio is EUPL-1.2 (ISC up to 2.6.0). Basilisk is ISC.
- The owner holds the copyright of both tools. The ported code is
  re-implemented in SpaceMissionStudio files, and it is published under
  EUPL-1.2 with the usual SPDX header (`pkg/legal.py`). No Apache-2.0
  file is copied, so no Apache NOTICE is needed. If a file is ever copied
  as it is, it keeps its Apache-2.0 header and goes in
  `THIRD_PARTY_NOTICES`.
- The released versions of System Budget Studio stay Apache-2.0.
- The decision goes into `docs/DECISIONS.md` in phase 0.

## 7. Open questions: the owner's answers (2026-11-17)

| # | Question | Recommendation | Owner's answer |
| --- | --- | --- | --- |
| Q1 | Licence of the moved code | EUPL-1.2, as in section 6. | **EUPL-1.2** (decision 3). |
| Q2 | PDF, XLSX and DOCX reports need reportlab, openpyxl and python-docx (BSD and MIT). | Not in phases 1–4. CSV and Markdown first. Decide in phase 5. | **As recommended:** CSV and Markdown in phases 1–4; PDF, XLSX and DOCX are decided in phase 5. |
| Q3 | Where the budgets live in the window | A new **Budgets** area in the navigation rail, between Results and Timeline. It holds Equipment, Power, Mass (the existing mass budget), Link and Propellant (the existing Run › Budget tab moves there). | **As recommended.** |
| Q4 | The hard rule "UI only during the overhaul" in `SpaceMissionStudio/CLAUDE.md` forbids changes to the engine and the file formats. | Replace it: engine and format changes are allowed for the merge, with a schema migration, unchanged golden files, and a decisions entry. | **Replace it** (phase 0): engine and format changes are allowed, each with a schema migration, unchanged golden files for existing scenarios and a decisions entry. Basilisk stays untouched. |
| Q5 | The "TBD" placeholder state | Add it to the sourced values of the `budgets` section only. A budget with a placeholder shows "unknown", never zero. | **As recommended:** in the `budgets` section only. A budget with a placeholder shows "unknown" and a problem; a run never starts with a placeholder in an input it uses. |
| Q6 | The System Budget Studio rule "problem messages never contain project values" (D-207) | Keep it for the new budget problems. | **No.** The budget problems follow SpaceMissionStudio's style and may show values, as the rest of the app does. |
| Q7 | Raised in review: SpaceMissionStudio already has power modes, through the IDM-CIC import (`idm/power.py`). | Build phase 1 on them. | **As recommended:** one equipment list and one power-mode model, filled by the IDM-CIC import and by the System Budget Studio import (section 3). |

## 8. Not ported, and why

SGP4 propagation, the eclipse and pass geometry, the orbit designer
(unless phase 1 finds a missing helper), the single-node thermal model and
the beta sweep, the delta-v budget, the mass properties, the scenario
rules and the pointing layers, the IDM-CIC importer, and the interim CSV
adapter. SpaceMissionStudio has a model for each of them, and the owner
decided that SpaceMissionStudio wins every overlap. A System Budget
Studio user who needs one of these results gets it from the
SpaceMissionStudio model after the import.

From the 2.11.0 tester feedback, the requests that were still open are
handled like this:
- HPOP comes with the merge.
- ITU-R P.618 rain attenuation is discarded (the owner, 2026-11-17).
- The DVB-S2 Eb/N0 values, the 3D plot and the tester's IDM-CIC file are
  set aside for now. The Eb/N0 table of phase 3 can later hold the DVB-S2
  values, once a sourced copy of ETSI EN 302 307-1 is available.
