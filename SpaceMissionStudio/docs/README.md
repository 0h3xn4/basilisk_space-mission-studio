# SpaceMissionStudio documentation

All SpaceMissionStudio documents, in groups. If you are new, start with
[Getting started](getting-started.md).

## Start here

| Page | Use it to |
|---|---|
| [Getting started](getting-started.md) | Install on Linux or Windows, check the installation, do a first run |
| [FAQ](faq.md) | Get short answers: systems, internet, accuracy, data exchange, licence |
| [Troubleshooting](troubleshooting.md) | Find what to do for each error message |
| [Glossary](glossary.md) | Find the meaning of a term or an abbreviation |

## Use the app

| Page | Use it to |
|---|---|
| [How-to guides](user-manual/README.md) | Do one task: one short page for each task and each feature |
| [User Manual](../USER_MANUAL.md) | Learn the full app. It is also in the app (**Help**, `F1`). |
| [Template catalog](../spacemissionstudio/scenarios/templates/README.md) | Select a template: 47 missions in nine categories, from simple to advanced |
| [Tips](tips.md) | Learn the shortcuts and good habits; see each file that the app reads and writes |
| [Python examples](../examples/README.md) | Use the engine from Python: five scripts |

## Reference

| Page | Use it to |
|---|---|
| [Use the command line](user-manual/command-line.md) | See each `spacemissionstudio` command |
| [The Python API](api.md) | Use `spacemissionstudio.api` from a script: load, check, run, lifetime, budgets, Monte Carlo and more |
| [Models, rules and assumptions](models/README.md) | See how each model calculates, each rule with its value, unit and source, and its assumptions |
| [Feature access](reference/feature-access.md) | See where each feature is in the app (menu, palette, keys), its manual section, its test, and what is still hidden |
| [Capabilities and verification](reference/capabilities.md) | See what the app can do, which Basilisk module does it, and what is verified |
| [Template coverage](reference/template-coverage.md) | See which templates show each feature |
| [Known limitations](reference/limitations.md) | See what the app does not do, and why |
| [Network use, offline mode and telemetry](reference/network.md) | See what can use the network, offline mode, and how the app enforces and logs it |
| [Data, standards and the offline policy](reference/data-and-standards.md) | See the qualified Basilisk version, CCSDS, Earth orientation and space weather |
| [The definition of done](definition-of-done.md) | See how each transparency criterion is checked |
| [Transparency audit](transparency_audit.md) | See each hard-coded value and hidden assumption, with file and line ([all numeric literals](transparency_audit_constants.csv)) |
| [Packaging](../packaging/README.md) | See how the installers are built and checked |
| [Compliance records](../compliance/README.md) | See the ECSS and CCSDS requirements, design, verification and compliance matrix |
| [Changelog](../CHANGELOG.md) | See what changed in each release |
| [Changes to results](changes.md) | See each fix that changed a calculated value, with the values before and after |

## Develop the app

| Page | Use it to |
|---|---|
| [Contributing](../CONTRIBUTING.md) | Propose a change |
| [Developer guide](developer/README.md) | Prepare a development environment, run the tests and the linter, make the generated files |
| [Writing style](developer/writing-style.md) | Write documentation: the rules (ASD-STE100 principles), the term list, the check |
| [Architecture](developer/architecture.md) | See the layers, the flow of a run, and where things are |
| [Design system](DESIGN.md) | See the colour tokens, type, layout, components and the rules for GUI code |
| [UX/UI standard](ux-standard.md) and [UX audit](ux-audit.md) | See the goals for the interface, and the findings and changes |
| [UI overhaul brief](ui/UI_OVERHAUL.md), [plan](ui/UI_OVERHAUL_PLAN.md), [before and after](ui/BEFORE_AFTER.md) | See the 1.3.0 interface work |
| [Decisions](DECISIONS.md) | See the choices made where a brief or a plan said nothing, each with its reason |
| [Third-party assets](THIRD_PARTY_ASSETS.md) | See the fonts, icons and libraries of the GUI, with their licences |
| [IDM-CIC import: design](developer/idm-cic-integration.md) | See how the IDM-CIC reader and import work |
| [The JSON page as a code editor](developer/json-editor.md) | See how the JSON page marks, completes, explains and changes the text |
| [Analyses built on the 3D model: design](developer/model-analyses-design.md) | See the design of the equipment, design checks and model analyses ([decisions](developer/model-analyses-decisions.md), [progress](developer/model-analyses-progress.md), [sources](developer/model-analyses-sources.md)) |
| [System budgets: merge plan](developer/system-budget-merge-design.md) and [phase 1 design](developer/system-budget-phase1-design.md) | See how the budgets of System Budget Studio came into the app ([decisions](developer/system-budget-decisions.md)) |
| [Monte Carlo: plan](developer/monte-carlo-plan.md) | See what a Monte Carlo batch does, its gaps, and phases A, B and C |
| [Releasing](developer/releasing.md) | Make a release: version numbers, checks, packages |
| [Keeping up with upstream Basilisk](developer/upstream-sync.md) | Merge upstream Basilisk; update the upstream part of the root README |
| [Development log](../HISTORY.md) | See why each change was made |
| [Documentation audit](DOCS_AUDIT.md) | See the audit of this documentation set, and what changed |

## Upstream Basilisk documentation

SpaceMissionStudio is in a fork of
[Basilisk](https://github.com/AVSLab/basilisk). The Basilisk
documentation is not changed:

| Page | Use it to |
|---|---|
| [Basilisk documentation online](https://avslab.github.io/basilisk/) | Install Basilisk, and read about its modules and examples |
| [Original Basilisk README](../../README.md#original-basilisk-readme) | Read the upstream README, in the root README |
| [`docs/source/`](../../docs/source/) | Read the Sphinx sources of the Basilisk documentation |
| [Basilisk's contributing guide](../../CONTRIBUTING.md) | Contribute to Basilisk itself |

---

**Next:** [Getting started](getting-started.md) ·
[How-to guides](user-manual/README.md)
