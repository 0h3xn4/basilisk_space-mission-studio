# The Python API

`spacemissionstudio.api` is the stable way to script SpaceMissionStudio:
load and check a scenario, run it, and compute what the app computes from
it. It uses the same engine as the app and the command line, so a number
from a script is the number the app shows.

The examples below are run by the tests (`tests/test_api.py`) exactly as
written, so they work with this version.

## Stability

`API_VERSION` is 1. Every name in `api.__all__` keeps its name, arguments
and meaning within an API version; a change that breaks a script raises
the version and is listed in the changelog. The objects the functions
return are the engine's own (`Scenario`, `ResultSet`, `EndOfLife`,
`Budget`, ...): their documented fields are part of the API, the ones
whose names start with `_` are not.

Without Basilisk, `template`, `load`, `validate`, `assumptions`,
`compare` and `design_checks` work; the others need it.

## The functions

| Function | Returns | Does |
|---|---|---|
| `template(name)` | `Path` | A shipped template's file, by name |
| `load(path)` | `Scenario` | Reads and validates a scenario file, with its project configuration file |
| `validate(scenario)` | warnings | The pre-run checks (each a `Finding` with its `rule_id`); raises `ScenarioValidationError` when the scenario cannot run |
| `assumptions(scenario=None)` | `{name: value}` | Every named parameter with the value in effect |
| `run(scenario, out_dir=None, allow_scripts=False)` | `ResultSet` | Runs it (its Mission Sequence when it has one); with `out_dir`, writes the CSVs and `provenance.json`; `allow_scripts=True` runs its `script_block` commands (unrestricted Python: only for files you trust) |
| `summary(result)` | `[Figure]` | The headline figures (Results > Overview), each with its `trace` |
| `lifetime(scenario, spacecraft=None, result=None, **options)` | `EndOfLife` | The orbital lifetime (End of Life); from the end of `result` when given. Options: `deorbit_perigee_km`, `max_years`, `forecast_percentile`, `drag_coeff`, `propellant_kg` |
| `budget(scenario, spacecraft=None, result=None)` | `Budget` | The delta-V and propellant budget (ESA AD10) |
| `launch_delays(scenario, spacecraft=None, result=None)` | `LaunchDelaySweep` | The budget for launches up to five years late |
| `altitude_trade(scenario, spacecraft=None, altitudes_km=None, result=None)` | `AltitudeTrade` | The sweep at each altitude, against the tank |
| `monte_carlo(scenario, archive_dir, allow_scripts=False, overwrite=False)` | `MonteCarloBatch` | The scenario's Monte Carlo batch, archived with its provenance; raises `MonteCarloError` when it has none; `overwrite=True` replaces an earlier batch in `archive_dir` |
| `compare(a_scenario, a_result, b_scenario, b_result)` | `Comparison` | Two runs side by side (Results > Compare) |
| `design_checks(scenario, spacecraft=None, samples=None, base_dir=None)` | `DesignReport` | The 3D model's design checks: field-of-view obstruction, thruster authority and plumes, mass budget, launcher envelope, and their `findings()` |
| `model_analyses(scenario, result, spacecraft=None, base_dir=None)` | `RunReport` | A run's model analyses: the disturbance-torque budget, blinding, antenna obstruction, array shading, exposure and brightness; `base_dir` resolves the model's relative mesh paths (default: the scenario file's folder) |
| `reentry(scenario, spacecraft=None, population_density_per_km2=None, base_dir=None)` | `ReentryEstimate` | The preliminary re-entry casualty estimate from the 3D model |
| `thermal(scenario, result, spacecraft=None, cases=None, base_dir=None, size_heaters=True)` | `ThermalAnalysis` | The thermal analysis after a run, for a spacecraft with a `thermal` section: per case the node temperatures, heat flows, the summary against the limits, heaters with their sized power, radiators, limit events and the energy balance |
| `thermal_model(scenario, spacecraft=None, base_dir=None)` | `Generated` | A starting thermal model from the spacecraft's 3D model (one node per part, contact conductors) and the notes on how it was built |
| `thermal_sweep(scenario, result, path, values, spacecraft=None, case="nominal", base_dir=None)` | list of `SweepPoint` | A thermal case at each value of one parameter (`faces[radiator].absorptance`...), with every node's summary |
| `thermal_sensitivity(scenario, result, paths=None, relative=0.1, spacecraft=None, case="nominal", base_dir=None)` | `(rows, notes)` | One-at-a-time sensitivity: each parameter up and down by `relative`, the change of every node's extremes, ranked |
| `thermal_monte_carlo(scenario, result, spacecraft=None, folder=None, base_dir=None)` | `MonteCarloBatch` | The thermal Monte Carlo of `thermal.monte_carlo` (seeded), saved in `folder` for the Monte Carlo view |
| `plan_opportunities(scenario, result=None)` | `Planning` | The geometry and the opportunities of the scenario's `operations` section: target windows, station passes (AOS, LOS, predicted margin), eclipses; from `result` when given, else as `geometry.source` says |
| `plan_schedule(scenario, result=None)` | `Planning` | A plan (`planning.plan`): the activities, the requests not placed with their reasons, the resource profiles, the score and the provenance; the same inputs and seed give the same plan |
| `plan_fly(scenario, plan)` | `ResultSet` | Flies the plan in the simulation, with the plan executor switching pointing and devices; adds the `<spacecraft>.plan.*` series |
| `plan_verify(scenario, plan, result=None)` | `(Verification, ResultSet)` | The plan against the simulation (pointing at each activity's start, geometry, state of charge, memory) and its flags; flies the plan first unless `result` flew it |
| `plan_export(planning, folder, verification=None)` | list of `Path` | Every operations product: passes (CSV, iCalendar), activities (CSV, JSON), the command schedule, pointing predictions, OEM and AEM per spacecraft, the report |
| `plan_load(path)` | `Plan` | A plan file (`spacemissionstudio-plan` JSON) |
| `plan_replan(scenario, plan, from_utc, events=None, result=None)` | `Planning` | Plans again from `from_utc`: activities started before it are kept, the `what_if` events (or `events`) applied |
| `plan_robustness(scenario, plan, runs=20, seed=0, result=None, **settings)` | `(draws, MonteCarloBatch)` | A seeded robustness batch: lost passes, link margin offset, slew time factor, initial state of charge |
| `plan_compare(a, b)` | `dict` | Two plans side by side: the requests each holds, and per spacecraft the activities, contact time, lowest state of charge and data lost |
| `record(scenario, analysis, spacecraft=None, result=None)` | `dict` | A lifetime's, budget's, sweep's, trade's, design report's, model analyses' or re-entry estimate's JSON record, as `--out` writes it; `result` is the run the analysis took its inputs from |
| `write(path, data)` | `Path` | Writes a record as JSON |

## Load, check and run

```python
from spacemissionstudio import api

scenario = api.load(api.template("22_starter_first_leo_satellite"))
for warning in api.validate(scenario):
    print(warning.rule_id, warning)

scenario.sim_settings.duration_days = 0.05  # [day] a short run for the example
result = api.run(scenario, out_dir="starter_results")
for figure in api.summary(result):
    print(f"{figure.label}: {figure.text()} {figure.unit}")
print(result.provenance.scenario_sha256)
```

`out_dir` holds one CSV per series (SI units, elapsed TDB seconds since
the epoch) and `provenance.json`, as `spacemissionstudio run --out-dir`
writes them.

## Change an assumption

A project configuration file sets the parameters
([Change a parameter](user-manual/project-configuration.md)); a script can
read the values in effect:

```python
from spacemissionstudio import api

values = api.assumptions(api.load(api.template("22_starter_first_leo_satellite")))
print(values["lifetime.zero_debris_years"], values["propellant_budget.residual_fraction"])
```

## Analyses and their records

```python
from spacemissionstudio import api

scenario = api.load(api.template("22_starter_first_leo_satellite"))
scenario.space_weather.atmosphere_model = "exponential"  # fast for the example; the default is NRLMSISE-00
end = api.lifetime(scenario, max_years=5.0)
print(end.lifetime.reentered, end.lifetime.lifetime_years)
trace = end.traces["lifetime"]
print(trace.equation, [(q.name, q.value, q.unit, q.source) for q in trace.inputs])
api.write("lifetime.json", api.record(scenario, end))
```

The record holds the inputs, the model and its rules, the results with
how each was computed, the decay curve, the warnings and the provenance:
the same file `spacemissionstudio lifetime --out` writes.

`api.design_checks(scenario)` needs no run and no Basilisk: it checks the
first spacecraft's 3D model and returns a `DesignReport`. Its `fov`,
`authority`, `plumes`, `mass` and `launcher` hold each check's results,
`findings()` what the Problems panel lists, and `api.record(scenario,
report)` the record `spacemissionstudio check-design --out` writes.
Pass `base_dir` (the scenario file's folder) when the model reads mesh
files by relative path.

`api.model_analyses(scenario, result)` reads a run's model analyses (set
in the spacecraft's `model_analyses`) from the run `api.run` returned, and
`api.reentry(scenario, population_density_per_km2=...)` gives the
preliminary re-entry estimate; `api.record` turns either into the record
`spacemissionstudio model-analyses --out` or `reentry --out` writes.

## Compare two runs

```python
from spacemissionstudio import api

scenario = api.load(api.template("22_starter_first_leo_satellite"))
scenario.sim_settings.duration_days = 0.02  # [day]
first = api.run(scenario)
heavier = api.load(api.template("22_starter_first_leo_satellite"))
heavier.sim_settings.duration_days = 0.02  # [day]
heavier.spacecraft[0].dry_mass_kg += 10.0  # [kg]
second = api.run(heavier)
comparison = api.compare(scenario, first, heavier, second)
for path, a, b in comparison.scenario:
    print(path, a, "->", b)
api.write("comparison.json", comparison.to_dict())
```

The command line does the same for runs kept in the run store:
`spacemissionstudio run scenario.json --save`, `spacemissionstudio runs`,
`spacemissionstudio compare 1 2 --out comparison.json`.

---

**See also:** [Use the command line](user-manual/command-line.md) ·
[Documentation index](README.md)
