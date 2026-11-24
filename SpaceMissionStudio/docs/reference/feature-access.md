# Feature access: where each feature is in the app

Every feature of SpaceMissionStudio, where a user of the app finds it, the
User Manual section that describes it, the test that follows its path in
the app, and its status. The owner asked on 2026-11-24: "Make sure that no
feature is hidden and that the users can actually use them." This page is
the result of that audit, and the tests keep it true (decision FA-1).

**Contents**

- [How to read this page](#how-to-read-this-page)
- [Summary](#summary)
- [Scenario](#scenario)
- [Spacecraft](#spacecraft)
- [3D model](#3d-model)
- [Budgets](#budgets)
- [Thermal](#thermal)
- [Operations](#operations)
- [Run](#run)
- [Results](#results)
- [Monte Carlo](#monte-carlo)
- [Import and export](#import-and-export)
- [Settings](#settings)
- [Help](#help)
- [Window and keyboard](#window-and-keyboard)
- [CLI](#cli)
- [Scenario fields without a form](#scenario-fields-without-a-form)
- [What the tests check](#what-the-tests-check)

## How to read this page

- **GUI path**: the menu, then the item (`View › Problems`), the command's
  id in the action registry (`view.problems`) and its keys (`Ctrl+J`). A
  command is also in the command palette (`Ctrl+K`) under its menu
  category and name. A path without a menu is an area of the navigation
  rail and its page (**Run › Thermal**).
- **Manual**: the section of the [User Manual](../../USER_MANUAL.md) (in
  the app: **Help**, `F1`) or the how-to page.
- **Test**: the test that follows the path in the app (offscreen, with
  pytest-qt) or, for the command line, runs the command.
- **Status**:
  - **OK**: reachable and usable; nothing changed.
  - **Fixed**: hidden or incomplete before; this change made it reachable
    (the decision in brackets, [`docs/DECISIONS.md`](../DECISIONS.md)).
  - **Backlog**: still hidden; it is in [`BACKLOG.md`](../../BACKLOG.md)
    under "Next release" with its hours and the reason.
  - **CLI only**: a command-line feature without a counterpart in the app,
    on purpose; the reason is given.

## Summary

The counts of the tables below (`tests/test_feature_access.py` checks
them):

| Status | Rows |
|---|---|
| OK | 173 |
| Fixed | 18 |
| Backlog | 5 |
| CLI only | 2 |
| All | 198 |

Fixed in this audit: the six pointing-budget commands (menu, palette, two
shortcuts), the six Spacecraft and Ground stations commands, two run
exports in the File menu, every export in the palette, the empty states of
eight run views, and the manual's menu and area lists.

## Scenario

| Feature | GUI path | Manual | Test | Status |
|---|---|---|---|---|
| New scenario | File › New Scenario (`file.new`, `Ctrl+N`) | [§3](../../USER_MANUAL.md#3-starting-the-app) | `tests/gui/test_menu_bar.py::test_menu_items_follow_their_commands_state` | OK |
| Open a scenario file | File › Open... (`file.open`, `Ctrl+O`) | [§3](../../USER_MANUAL.md#3-starting-the-app) | `tests/gui/test_main_window.py` | OK |
| Open a recent file | File › Open Recent; Home's recent list | [§3](../../USER_MANUAL.md#3-starting-the-app) | `tests/gui/test_menu_bar.py::test_open_recent_lists_the_recent_files_and_opens_one` | OK |
| Save | File › Save (`file.save`, `Ctrl+S`) | [§8](../../USER_MANUAL.md#8-saving-your-work) | `tests/gui/test_main_window.py` | OK |
| Save as | File › Save As... (`file.save_as`, `Ctrl+Shift+S`) | [§8](../../USER_MANUAL.md#8-saving-your-work) | `tests/gui/test_main_window.py` | OK |
| Change history | File › Change History... (`file.change_history`) | [Change history](../user-manual/change-history.md) | `tests/gui/test_feature_access_gui.py::test_every_command_is_in_the_palette_and_runs_from_it` | OK |
| Undo | Edit › Undo (`edit.undo`, `Ctrl+Z`) | [§6](../../USER_MANUAL.md#6-a-tour-of-the-scenario-editor) | `tests/gui/test_undo_history.py` | OK |
| Redo | Edit › Redo (`edit.redo`, `Ctrl+Y`) | [§6](../../USER_MANUAL.md#6-a-tour-of-the-scenario-editor) | `tests/gui/test_undo_history.py` | OK |
| Templates by category, with a filter | **Home** (category list and text filter); palette "Open template" | [§4](../../USER_MANUAL.md#which-template-next) | `tests/gui/test_home_categories.py` | OK |
| Customize a template | **Home** › a template › Customize... | [§5](../../USER_MANUAL.md#5-tweaking-a-template-without-the-full-editor) | `tests/gui/test_template_wizard.py` | OK |
| General settings (name, epoch, duration, mode) | **Scenario › General** | [§6](../../USER_MANUAL.md#6-a-tour-of-the-scenario-editor) | `tests/gui/test_scenario_editor.py` | OK |
| Environment (gravity, space weather, atmosphere) | **Scenario › Environment** | [§6](../../USER_MANUAL.md#6-a-tour-of-the-scenario-editor) | `tests/gui/test_propagation_setup_dialog.py` | OK |
| Mission sequence | **Scenario › Mission sequence** | [Mission sequence](../user-manual/mission-sequence.md) | `tests/gui/test_mission_sequence_editor.py` | OK |
| Ground stations | **Scenario › Ground stations** | [§6](../../USER_MANUAL.md#6-a-tour-of-the-scenario-editor) | `tests/gui/test_ground_station_editor.py` | OK |
| Add a ground station | Tools › Scenario › Add Ground Station (`scenario.add_ground_station`) | [§3](../../USER_MANUAL.md#3-starting-the-app) | `tests/gui/test_feature_access_gui.py::test_the_scenario_commands_click_the_pages_buttons` | Fixed (FA-3) |
| Project configuration and parameters | **Scenario › Assumptions** | [Project configuration](../user-manual/project-configuration.md) | `tests/gui/test_assumptions_page.py` | OK |
| Plugins loaded | **Scenario › Assumptions** (the plugins line) | [Plugins](../user-manual/plugins.md) | `tests/gui/test_assumptions_page.py` | OK |
| The scenario as text (code editor) | **Scenario** › Form · JSON; palette "Go to › Scenario › JSON" | [§6](../../USER_MANUAL.md#6-a-tour-of-the-scenario-editor) | `tests/gui/test_json_editor.py` | OK |
| What the scenario does | View › Explain (`view.explain`); **Scenario › Overview** | [§7](../../USER_MANUAL.md#7-reading-the-results) | `tests/gui/test_scenario_explainer_widget.py` | OK |
| Problems of the scenario | View › Problems (`view.problems`, `Ctrl+J`) | [§3](../../USER_MANUAL.md#3-starting-the-app) | `tests/gui/test_panels.py` | OK |
| The field in focus: value, range, help | View › Inspector (`view.inspector`, `Ctrl+I`) | [§3](../../USER_MANUAL.md#3-starting-the-app) | `tests/gui/test_workspace.py` | OK |
| How a number was computed | View › Calculation (`view.calculation`) | [§7](../../USER_MANUAL.md#7-reading-the-results) | `tests/gui/test_calculation_panel.py` | OK |
| Operations section: activities, requests, scheduler, what-if, verification | **Scenario › JSON** only | [Operations planning](../../USER_MANUAL.md#operations-planning) | `tests/gui/test_plan_page.py::test_the_editor_keeps_the_operations_section_and_its_names_follow` | Backlog: a form for the section is about 24 hours |

## Spacecraft

| Feature | GUI path | Manual | Test | Status |
|---|---|---|---|---|
| Add a spacecraft | Tools › Scenario › Add Spacecraft (`scenario.add_spacecraft`); **Scenario › Spacecraft** › Add | [§6](../../USER_MANUAL.md#building-your-own-scenario-step-by-step) | `tests/gui/test_feature_access_gui.py::test_the_scenario_commands_click_the_pages_buttons` | Fixed (FA-3) |
| A spacecraft from a ready-made one | Tools › Scenario › New Spacecraft from Template... (`scenario.spacecraft_from_template`) | [§6](../../USER_MANUAL.md#building-your-own-scenario-step-by-step) | `tests/gui/test_spacecraft_template_dialog.py` | Fixed (FA-3) |
| Walker constellation | Tools › Scenario › Generate Walker Constellation... (`scenario.generate_constellation`) | [Orbit keeping and formations](../user-manual/orbit-keeping-and-formations.md) | `tests/gui/test_constellation_dialog.py` | Fixed (FA-3) |
| Phasing formation | Tools › Scenario › Generate Phasing Formation... (`scenario.generate_phasing_formation`) | [§6](../../USER_MANUAL.md#formation-control-laws) | `tests/gui/test_phasing_formation_dialog.py` | Fixed (FA-3) |
| ROE formation | Tools › Scenario › Generate ROE Formation... (`scenario.generate_roe_formation`) | [§6](../../USER_MANUAL.md#formations-in-relative-orbital-elements) | `tests/gui/test_roe_formation_dialog.py` | Fixed (FA-3) |
| Orbit (Keplerian, Cartesian, TLE, mean elements) | **Scenario › Spacecraft › (name) › Orbit / mass** | [§6](../../USER_MANUAL.md#6-a-tour-of-the-scenario-editor) | `tests/gui/test_orbit_ic_widget.py` | OK |
| Orbit from a CCSDS OPM or OMM | **Orbit / mass** › Import... | [Orbit files](../user-manual/orbit-files.md) | `tests/gui/test_ccsds_gui.py::test_an_import_on_a_spacecraft_page_reaches_the_scenario` | OK |
| Sensors and actuators, faults | **Sensors / actuators** | [Attitude and hardware](../user-manual/attitude-and-hardware.md) | `tests/gui/test_sensor_actuator_editor.py` | OK |
| Attitude control and the flight software mode | **Attitude control** | [Attitude and hardware](../user-manual/attitude-and-hardware.md) | `tests/gui/test_spacecraft_editor.py` | OK |
| Navigation error | **Attitude control** › Navigation error | [§6](../../USER_MANUAL.md#navigation-error) | `tests/gui/test_spacecraft_editor.py` | OK |
| Power, propulsion, RF link, antenna pattern | **Power / propulsion / link budget** | [Power, link and data](../user-manual/power-link-and-data.md) | `tests/gui/test_spacecraft_editor.py` | OK |
| Data handling and downlink | **Power / propulsion / link budget** › Data handling | [§6](../../USER_MANUAL.md#data-handling-and-the-downlink) | `tests/gui/test_data_handling_editor.py` | OK |
| Flexible solar arrays | **Orbit / mass** › Flexible solar arrays | [§6](../../USER_MANUAL.md#flexible-solar-arrays) | `tests/gui/test_solar_array_editor.py` | OK |
| Station keeping and formation control | **Orbit / mass** (optional groups) | [§6](../../USER_MANUAL.md#formation-control-laws) | `tests/gui/test_roe_formation_editor.py` | OK |
| Optical navigation | **Attitude control** › Optical navigation | [§6](../../USER_MANUAL.md#optical-navigation) | `tests/gui/test_optical_navigation_editor.py` | OK |
| Small bodies and landmarks | **Scenario › Environment**; **Attitude control** | [§6](../../USER_MANUAL.md#small-bodies-and-landmark-navigation) | `tests/gui/test_small_body_editors.py` | OK |
| AD10 budget inputs | **Budget (AD10)** | [Lifetime and budget](../user-manual/lifetime-and-budget.md) | `tests/gui/test_budget_widget.py` | OK |

## 3D model

| Feature | GUI path | Manual | Test | Status |
|---|---|---|---|---|
| The 3D model editor | Tools › 3D Model... (`tools.model_3d`); **Scenario** header › 3D Model... | [§6](../../USER_MANUAL.md#a-3d-model-of-the-spacecraft) | `tests/gui/test_model_editor.py` | OK |
| Parts, meshes (.obj), materials, faces | 3D Model... › its tabs | [3D model](../user-manual/3d-model.md) | `tests/gui/test_model_editor_window.py` | OK |
| Mounted equipment | 3D Model... › Equipment | [Model analyses](../user-manual/model-analyses.md) | `tests/gui/test_model_analyses_pages.py` | OK |
| Apply the model's mass properties | **3D model** › Apply the model | [§6](../../USER_MANUAL.md#a-3d-model-of-the-spacecraft) | `tests/gui/test_model_editor.py` | OK |
| Export the model as .obj | 3D Model... › Export .obj...; palette "Export › 3D model" | [3D model](../user-manual/3d-model.md) | `tests/gui/test_export_files.py` | OK |
| IDM-CIC import | 3D Model... › Import IDM-CIC... | [IDM-CIC](../user-manual/idm-cic.md) | `tests/gui/test_idm_import_dialog.py` | OK |
| Design checks | Run › Design Checks (`analyses.design_checks`) | [§6](../../USER_MANUAL.md#analyses-built-on-the-3d-model) | `tests/gui/test_design_checks_page.py` | OK |
| Model analyses (shading, exposure, brightness, ...) | **3D model** › Model analyses; **Results › Model Analyses** after a run | [Model analyses](../user-manual/model-analyses.md) | `tests/gui/test_model_analyses_pages.py` | OK |

## Budgets

| Feature | GUI path | Manual | Test | Status |
|---|---|---|---|---|
| The Budgets area | Go › Go to Budgets (`go.budgets`, `Ctrl+5`) | [Budgets](../user-manual/budgets.md) | `tests/gui/test_budgets_area.py` | OK |
| Add an equipment item | Tools › Budgets › Add Equipment Item (`budgets.add_item`, `Ctrl+Shift+N`) | [Budgets](../user-manual/budgets.md) | `tests/gui/test_budgets_area.py` | OK |
| Remove an equipment item | Tools › Budgets › Remove Equipment Item (`budgets.remove_item`, `Ctrl+Del`) | [Budgets](../user-manual/budgets.md) | `tests/gui/test_budgets_area.py` | OK |
| Copy a budget as CSV | Tools › Budgets › Copy as CSV (`budgets.copy_csv`, `Ctrl+Shift+C`) | [Budgets](../user-manual/budgets.md) | `tests/gui/test_budgets_area.py` | OK |
| Power budget per system mode | **Budgets › Power** | [Budgets](../user-manual/budgets.md) | `tests/gui/test_budgets_area.py` | OK |
| Mass budget | **Budgets › Mass** | [Budgets](../user-manual/budgets.md) | `tests/gui/test_budgets_area.py` | OK |
| Add a pointing budget | Tools › Budgets › Add Pointing Budget (`budgets.pointing.add_budget`) | [§6](../../USER_MANUAL.md#the-pointing-error-budget) | `tests/gui/test_feature_access_gui.py::test_the_pointing_commands_show_the_page_and_act` | Fixed (FA-2) |
| Add a pointing requirement | Tools › Budgets › Add Pointing Requirement (`budgets.pointing.add_requirement`, `Ctrl+Shift+E`) | [§6](../../USER_MANUAL.md#the-pointing-error-budget) | `tests/gui/test_feature_access_gui.py::test_the_pointing_commands_show_the_page_and_act` | Fixed (FA-2) |
| Remove a pointing requirement | Tools › Budgets › Remove Pointing Requirement (`budgets.pointing.remove_requirement`) | [§6](../../USER_MANUAL.md#the-pointing-error-budget) | `tests/gui/test_feature_access_gui.py::test_every_command_is_in_the_palette_and_runs_from_it` | Fixed (FA-2) |
| Add a pointing contributor | Tools › Budgets › Add Pointing Contributor (`budgets.pointing.add_contributor`, `Ctrl+Shift+T`) | [§6](../../USER_MANUAL.md#the-pointing-error-budget) | `tests/gui/test_feature_access_gui.py::test_the_pointing_commands_show_the_page_and_act` | Fixed (FA-2) |
| Remove a pointing contributor | Tools › Budgets › Remove Pointing Contributor (`budgets.pointing.remove_contributor`) | [§6](../../USER_MANUAL.md#the-pointing-error-budget) | `tests/gui/test_feature_access_gui.py::test_every_command_is_in_the_palette_and_runs_from_it` | Fixed (FA-2) |
| The scenario's sensors as contributors | Tools › Budgets › Add Scenario Sensors to Pointing Budget (`budgets.pointing.add_sensors`) | [§6](../../USER_MANUAL.md#the-pointing-error-budget) | `tests/gui/test_budgets_pointing.py` | Fixed (FA-2) |
| Delta-V and propellant budget | Run › Budget (`analyses.budget`); **Budgets › Propellant** | [Lifetime and budget](../user-manual/lifetime-and-budget.md) | `tests/gui/test_budget_widget.py` | OK |
| Launch delays and altitude trade | **Budgets › Propellant** › Launch delays, Altitude trade | [Lifetime and budget](../user-manual/lifetime-and-budget.md) | `tests/gui/test_budget_widget.py` | OK |
| Budgets in a window of its own | View › Own Windows › Open Budgets in Own Window (`view.window.budgets`) | [§3](../../USER_MANUAL.md#open-a-view-in-its-own-window) | `tests/gui/test_own_windows.py` | OK |

## Thermal

| Feature | GUI path | Manual | Test | Status |
|---|---|---|---|---|
| The thermal model (nodes, faces, conductors, heaters, cases) | **Scenario › Spacecraft › (name) › 3D model** › Thermal model | [§6](../../USER_MANUAL.md#thermal-analysis) | `tests/gui/test_thermal_pages.py::test_the_group_round_trips_the_section_exactly` | OK |
| Generate the thermal model from the 3D model | Thermal model › Generate from the 3D model | [Thermal](../user-manual/thermal.md) | `tests/gui/test_thermal_pages.py::test_generate_fills_the_tables_from_the_3d_model_and_keeps_the_rest` | OK |
| Solve on the last run | Run › Thermal (`analyses.thermal`) › Solve | [§6](../../USER_MANUAL.md#thermal-analysis) | `tests/gui/test_thermal_pages.py::test_run_thermal_solves_shows_and_saves` | OK |
| Sweep, sensitivity, thermal Monte Carlo | **Run › Thermal** › Studies | [Thermal](../user-manual/thermal.md) | `tests/gui/test_thermal_views.py` | OK |
| Temperatures on the 3D View | **Run › Thermal** › Show on 3D View | [§6](../../USER_MANUAL.md#thermal-analysis) | `tests/gui/test_thermal_views.py` | OK |
| Thermal in a window of its own | View › Own Windows › Open Thermal in Own Window (`view.window.thermal`) | [§3](../../USER_MANUAL.md#open-a-view-in-its-own-window) | `tests/gui/test_own_windows.py` | OK |

## Operations

| Feature | GUI path | Manual | Test | Status |
|---|---|---|---|---|
| Plan the operations | Run › Plan (`analyses.plan`) › Plan | [§6](../../USER_MANUAL.md#operations-planning) | `tests/gui/test_plan_page.py::test_the_page_plans_and_shows_the_plan` | OK |
| Lock, unlock, delete, move an activity | **Run › Plan** › Lock, Unlock, Delete; drag in the chart | [Operations](../user-manual/operations.md) | `tests/gui/test_plan_page.py::test_lock_unlock_delete_and_move` | OK |
| Lose a pass, replan, compare plans | **Run › Plan** › Lose this pass, Replan, Compare with... | [Operations](../user-manual/operations.md) | `tests/gui/test_plan_page.py::test_lose_a_pass_replans_and_compares` | OK |
| Fly and verify | **Run › Plan** › Fly and verify | [Operations](../user-manual/operations.md) | `tests/gui/test_plan_page.py::test_fly_and_verify_from_the_page` | OK |
| Robustness batch, export, save and open a plan | **Run › Plan** › Run robustness, Export..., Save plan..., Open plan... | [Operations](../user-manual/operations.md) | `tests/gui/test_plan_page.py::test_robustness_export_save_and_open` | OK |
| A scenario without an operations section | **Run › Plan**: the empty state's Open Template 35 | [§6](../../USER_MANUAL.md#operations-planning) | `tests/gui/test_empty_states.py::test_the_plan_page_says_what_a_plan_is_and_offers_the_template` | OK |
| Edit the activities, requests, scheduler and what-if events | **Scenario › JSON** only | [§6](../../USER_MANUAL.md#operations-planning) | `tests/gui/test_json_editor.py` | Backlog: the same form as under Scenario (about 24 hours) |

## Run

| Feature | GUI path | Manual | Test | Status |
|---|---|---|---|---|
| Run | Run › Run (`run.run`, `Ctrl+R`); the top bar's Run | [§4](../../USER_MANUAL.md#4-your-first-simulation-in-five-minutes) | `tests/gui/test_home_palette_run.py` | OK |
| Cancel a run | Run › Cancel Run (`run.cancel`, `Esc`) | [§9](../../USER_MANUAL.md#while-it-runs) | `tests/gui/test_run_feedback.py` | OK |
| Single run | Run › Run Mode › Single run (`run.mode.single`) | [§3](../../USER_MANUAL.md#3-starting-the-app) | `tests/gui/test_run_page.py` | OK |
| Monte Carlo batch | Run › Run Mode › Monte Carlo (`run.mode.monte_carlo`) | [§10](../../USER_MANUAL.md#10-monte-carlo-running-many-variations-at-once) | `tests/gui/test_run_page.py` | OK |
| Software in the loop | Run › Run Mode › SIL (`run.mode.sil`) | [§6](../../USER_MANUAL.md#running-the-flight-software-in-the-loop) | `tests/gui/test_sil_widgets.py` | OK |
| Live plot while running | Run › Live plot (`run.live_plot`) | [§9](../../USER_MANUAL.md#while-it-runs) | `tests/gui/test_run_page.py` | OK |
| The 3D View while running | **Run › Run** › Show in 3D View while running | [§9](../../USER_MANUAL.md#while-it-runs) | `tests/gui/test_live_run_3d.py` | OK |
| Reference data check | Tools › Check Reference Data (`run.check_data`) | [Reference data](../user-manual/reference-data.md) | `tests/gui/test_data_panel_widget.py` | OK |
| Reference data downloads and imports | Tools › Reference Data... (`tools.reference_data`) | [Reference data](../user-manual/reference-data.md) | `tests/gui/test_data_panel_widget.py` | OK |
| End of life: lifetime and deorbit | Run › End of Life (`analyses.end_of_life`) | [Lifetime and budget](../user-manual/lifetime-and-budget.md) | `tests/gui/test_lifetime_widget.py` | OK |
| Re-entry casualty estimate | **Run › End of Life › Re-entry casualty (preliminary)** | [§6](../../USER_MANUAL.md#analyses-built-on-the-3d-model) | `tests/gui/test_lifetime_widget.py` | OK |
| Every run, failed ones too | **Run › History** | [§7](../../USER_MANUAL.md#7-reading-the-results) | `tests/gui/test_run_record.py` | OK |
| The session's log | **Run › Log** | [§3](../../USER_MANUAL.md#3-starting-the-app) | `tests/gui/test_run_messages.py` | OK |

## Results

| Feature | GUI path | Manual | Test | Status |
|---|---|---|---|---|
| Headline figures and provenance | Go › Go to Results (`go.results`, `Ctrl+4`) › **Overview** | [§7](../../USER_MANUAL.md#7-reading-the-results) | `tests/gui/test_results_overview.py` | OK |
| Every recorded series as a plot | **Results › Plots**; palette "Show series" | [§7](../../USER_MANUAL.md#7-reading-the-results) | `tests/gui/test_command_palette.py::test_the_palette_shows_a_series_of_the_result` | OK |
| Run from an empty run view | **Results › Plots**, **3D View**, the map, **Timeline**, **Compare**, **Dashboard**: the empty state's Run | [§7](../../USER_MANUAL.md#7-reading-the-results) | `tests/gui/test_feature_access_gui.py::test_the_run_views_empty_states_lead_to_their_action` | Fixed (FA-6) |
| 3D View | **Results › 3D View** | [§9](../../USER_MANUAL.md#9-3d-visualization) | `tests/gui/test_mission_view.py` | OK |
| Show the globe | View › 3D View › Show Globe (`view.3d_view.globe`) | [§9](../../USER_MANUAL.md#the-2d-map) | `tests/gui/test_ground_map.py` | OK |
| Show the 2D map | View › 3D View › Show Map (`view.3d_view.map`) | [§9](../../USER_MANUAL.md#the-2d-map) | `tests/gui/test_ground_map.py` | OK |
| Show the globe and the map | View › 3D View › Show Globe and Map (`view.3d_view.both`) | [§9](../../USER_MANUAL.md#the-2d-map) | `tests/gui/test_ground_map.py` | OK |
| The 3D View in its own window | View › Own Windows › Open 3D View in Own Window (`view.window.3d_view`) | [§3](../../USER_MANUAL.md#open-a-view-in-its-own-window) | `tests/gui/test_own_windows.py` | OK |
| The map in its own window | View › Own Windows › Open Map in Own Window (`view.window.map`) | [§3](../../USER_MANUAL.md#open-a-view-in-its-own-window) | `tests/gui/test_own_windows.py` | OK |
| Live status readouts | **Results › Dashboard**; empty: Run, Open Template 19 | [§7](../../USER_MANUAL.md#7-reading-the-results) | `tests/gui/test_mission_dashboard_widget.py` | Fixed (FA-6) |
| Mission output (Report steps) | **Results › Output**; empty: Go to Mission Sequence | [§7](../../USER_MANUAL.md#7-reading-the-results) | `tests/gui/test_feature_access_gui.py::test_the_run_views_empty_states_lead_to_their_action` | Fixed (FA-6) |
| Compare runs | **Results › Compare** | [§7](../../USER_MANUAL.md#7-reading-the-results) | `tests/gui/test_compare_tab.py` | OK |
| Events: passes, eclipses, burns | Go › Go to Timeline (`go.timeline`, `Ctrl+6`) | [§7](../../USER_MANUAL.md#7-reading-the-results) | `tests/gui/test_event_timeline_widget.py` | OK |
| Results shown are from an older scenario | the banner over the run views, with Run again | [§7](../../USER_MANUAL.md#7-reading-the-results) | `tests/gui/test_stale_results_and_window_size.py` | OK |
| Next sample | Go › Time Cursor › Next Sample (`cursor.next_sample`, `Alt+Right`) | [§7](../../USER_MANUAL.md#7-reading-the-results) | `tests/gui/test_keyboard_cursor.py` | OK |
| Previous sample | Go › Time Cursor › Previous Sample (`cursor.previous_sample`, `Alt+Left`) | [§7](../../USER_MANUAL.md#7-reading-the-results) | `tests/gui/test_keyboard_cursor.py` | OK |
| Ten samples on | Go › Time Cursor › Ten Samples On (`cursor.ten_samples_on`, `Alt+Shift+Right`) | [§7](../../USER_MANUAL.md#7-reading-the-results) | `tests/gui/test_keyboard_cursor.py` | OK |
| Ten samples back | Go › Time Cursor › Ten Samples Back (`cursor.ten_samples_back`, `Alt+Shift+Left`) | [§7](../../USER_MANUAL.md#7-reading-the-results) | `tests/gui/test_keyboard_cursor.py` | OK |
| Next event | Go › Time Cursor › Next Event (`cursor.next_event`, `Alt+PgDown`) | [§7](../../USER_MANUAL.md#7-reading-the-results) | `tests/gui/test_keyboard_cursor.py` | OK |
| Previous event | Go › Time Cursor › Previous Event (`cursor.previous_event`, `Alt+PgUp`) | [§7](../../USER_MANUAL.md#7-reading-the-results) | `tests/gui/test_keyboard_cursor.py` | OK |
| Start of the run | Go › Time Cursor › Start of the Run (`cursor.start_of_the_run`, `Alt+Home`) | [§7](../../USER_MANUAL.md#7-reading-the-results) | `tests/gui/test_keyboard_cursor.py` | OK |
| End of the run | Go › Time Cursor › End of the Run (`cursor.end_of_the_run`, `Alt+End`) | [§7](../../USER_MANUAL.md#7-reading-the-results) | `tests/gui/test_keyboard_cursor.py` | OK |
| Clear the time cursor | Go › Time Cursor › Clear Time Cursor (`run.clear_cursor`, `Alt+Backspace`) | [§7](../../USER_MANUAL.md#7-reading-the-results) | `tests/gui/test_results_cursor.py` | OK |

## Monte Carlo

| Feature | GUI path | Manual | Test | Status |
|---|---|---|---|---|
| Dispersions, runs, processes, seed, requirements | **Scenario › Monte Carlo** | [§10](../../USER_MANUAL.md#10-monte-carlo-running-many-variations-at-once) | `tests/gui/test_monte_carlo_editor.py` | OK |
| Run the batch | Run › Run Mode › Monte Carlo, then Run | [§10](../../USER_MANUAL.md#10-monte-carlo-running-many-variations-at-once) | `tests/gui/test_run_page.py` | OK |
| Open a saved batch | Run › Open Monte Carlo Results... (`run.open_monte_carlo`) | [§10](../../USER_MANUAL.md#10-monte-carlo-running-many-variations-at-once) | `tests/gui/test_monte_carlo_results_widget.py::test_a_saved_batch_shows_tiles_plots_and_a_sortable_run_table` | OK |
| Run one case again | Run › Run This Case (`run.monte_carlo_case`, `Ctrl+Shift+R`) | [§10](../../USER_MANUAL.md#10-monte-carlo-running-many-variations-at-once) | `tests/gui/test_monte_carlo_results_widget.py::test_the_main_window_runs_a_case_again_or_says_why_not` | OK |
| Requirements, statistics, sensitivity | **Results › Monte Carlo** › Requirements, Statistics, Sensitivity | [§10](../../USER_MANUAL.md#10-monte-carlo-running-many-variations-at-once) | `tests/gui/test_monte_carlo_results_widget.py::test_the_sensitivity_tab_sorts_the_correlations_by_size` | OK |
| The batch report and the runs table | **Results › Monte Carlo** › Export report..., Export table CSV... | [§10](../../USER_MANUAL.md#10-monte-carlo-running-many-variations-at-once) | `tests/gui/test_monte_carlo_results_widget.py::test_export_report_asks_for_the_file_and_its_format` | OK |

## Import and export

| Feature | GUI path | Manual | Test | Status |
|---|---|---|---|---|
| Every export in one table | Go › Go to Reports (`go.reports`, `Ctrl+7`) › **Exports** | [§3](../../USER_MANUAL.md#3-starting-the-app) | `tests/gui/test_reports_and_settings.py::test_a_row_opens_the_view_that_makes_it` | OK |
| Every export by name in the palette | palette "Export › (name)": the view that makes it | [§3](../../USER_MANUAL.md#3-starting-the-app) | `tests/gui/test_feature_access_gui.py::test_every_page_settings_section_and_export_of_the_palette_opens` | Fixed (FA-5) |
| Plot data, images, every shown plot | **Results › Plots** › Export CSV..., Save PNG..., Save SVG..., Export all... | [§7](../../USER_MANUAL.md#7-reading-the-results) | `tests/gui/test_export_files.py` | OK |
| Reproduction bundle | File › Export Reproduction Bundle... (`file.export_bundle`); **Results › Plots** › Export all... | [§7](../../USER_MANUAL.md#7-reading-the-results) | `tests/gui/test_feature_access_gui.py::test_the_run_exports_are_in_the_file_menu_while_a_run_is_shown` | Fixed (FA-4) |
| Ephemeris as CCSDS OEM | File › Export Ephemeris as CCSDS OEM... (`file.export_oem`); **Results › Plots** › Export all... | [Orbit files](../user-manual/orbit-files.md) | `tests/gui/test_ccsds_gui.py::test_the_shown_run_exports_its_ephemeris_as_oem` | Fixed (FA-4) |
| Starting orbits as CCSDS OPM or OMM | File › Export Orbits as CCSDS... (`tools.ccsds_export`) | [Orbit files](../user-manual/orbit-files.md) | `tests/gui/test_ccsds_gui.py::test_export_orbits_writes_a_conforming_opm_per_spacecraft` | OK |
| Check a CCSDS file | Tools › Check a CCSDS File... (`tools.ccsds_check`) | [Orbit files](../user-manual/orbit-files.md) | `tests/gui/test_ccsds_gui.py::test_the_check_dialog_lists_each_issue` | OK |
| Events, mission output | **Timeline** › Export CSV...; **Results › Output** › Export CSV... | [§7](../../USER_MANUAL.md#7-reading-the-results) | `tests/gui/test_export_files.py` | OK |
| Flight software project | Tools › Flight Software (`tools.flight_software`) › Export... | [§6](../../USER_MANUAL.md#exporting-the-flight-software) | `tests/gui/test_fsw_workbench_widget.py` | OK |
| A run comparison as JSON | none (the command line's `compare --out`) | [§7](../../USER_MANUAL.md#7-reading-the-results) | `tests/test_cli.py` | Backlog: about 1.5 hours; its Exports row changes a test's count (FA-9) |

## Settings

| Feature | GUI path | Manual | Test | Status |
|---|---|---|---|---|
| The Settings area | Edit › Settings... (`edit.settings`, `Ctrl+,`) | [§3](../../USER_MANUAL.md#3-starting-the-app) | `tests/gui/test_menu_bar.py::test_edit_settings_opens_the_settings_area` | OK |
| Theme: system | View › Theme: System (`view.theme.system`); **Settings › Appearance** | [§3](../../USER_MANUAL.md#3-starting-the-app) | `tests/gui/test_settings_page.py::test_the_theme_is_a_segmented_control` | OK |
| Theme: light | View › Theme: Light (`view.theme.light`) | [§3](../../USER_MANUAL.md#3-starting-the-app) | `tests/gui/test_settings_page.py::test_the_theme_is_a_segmented_control` | OK |
| Theme: dark | View › Theme: Dark (`view.theme.dark`) | [§3](../../USER_MANUAL.md#3-starting-the-app) | `tests/gui/test_dark_theme.py` | OK |
| UI scale, reduce motion, plot units | **Settings › Appearance** | [§3](../../USER_MANUAL.md#3-starting-the-app) | `tests/gui/test_reports_and_settings.py::test_the_ui_scale_is_kept_for_the_next_start` | OK |
| Work offline, the network log | **Settings › Network**; `SPACEMISSIONSTUDIO_OFFLINE` | [Network](network.md) | `tests/gui/test_network_gui.py` | OK |
| The change history's author | **Settings › Change history** | [Change history](../user-manual/change-history.md) | `tests/gui/test_settings_page.py` | OK |
| Reference data | **Settings › Reference data** | [Reference data](../user-manual/reference-data.md) | `tests/gui/test_data_panel_widget.py` | OK |
| Layout check boxes | **Settings › Layout** | [§3](../../USER_MANUAL.md#3-starting-the-app) | `tests/gui/test_settings_page.py::test_a_layout_check_box_follows_its_command` | OK |
| Reset the layout | View › Reset Layout (`view.reset_layout`) | [§3](../../USER_MANUAL.md#3-starting-the-app) | `tests/gui/test_panels.py` | OK |
| Plugins off | `SPACEMISSIONSTUDIO_PLUGINS=0` (no setting: it is for an administrator) | [Plugins](../user-manual/plugins.md) | `tests/test_plugins.py` | OK |

## Help

| Feature | GUI path | Manual | Test | Status |
|---|---|---|---|---|
| The User Manual, offline | Help › User Manual (`help.manual`, `F1`); the rail's Help | [§13](../../USER_MANUAL.md#13-where-to-go-next) | `tests/gui/test_help.py` | OK |
| Keyboard shortcuts | Help › Keyboard Shortcuts (`help.shortcuts`, `Ctrl+/`) | [§3](../../USER_MANUAL.md#3-starting-the-app) | `tests/gui/test_settings_page.py::test_the_keyboard_table_fills_the_width` | OK |
| The command palette | View › Command Palette... (`help.palette`, `Ctrl+K`) | [§3](../../USER_MANUAL.md#3-starting-the-app) | `tests/gui/test_command_palette.py` | OK |
| About | Help › About SpaceMissionStudio (`help.about`) | [§3](../../USER_MANUAL.md#3-starting-the-app) | `tests/gui/test_feature_access_gui.py::test_every_command_is_in_the_palette_and_runs_from_it` | OK |
| Third-party licences | Help › Third-Party Licences... (`help.licences`) | [§3](../../USER_MANUAL.md#3-starting-the-app) | `tests/gui/test_licences_dialog.py` | OK |
| A field's help | the Inspector; hover in **Scenario › JSON** | [§6](../../USER_MANUAL.md#6-a-tour-of-the-scenario-editor) | `tests/gui/test_json_editor.py` | OK |

## Window and keyboard

| Feature | GUI path | Manual | Test | Status |
|---|---|---|---|---|
| Home | Go › Go to Home (`go.home`, `Ctrl+1`) | [§3](../../USER_MANUAL.md#3-starting-the-app) | `tests/gui/test_shell.py` | OK |
| Scenario | Go › Go to Scenario (`go.scenario`, `Ctrl+2`) | [§3](../../USER_MANUAL.md#3-starting-the-app) | `tests/gui/test_shell.py` | OK |
| Run | Go › Go to Run (`go.run`, `Ctrl+3`) | [§3](../../USER_MANUAL.md#3-starting-the-app) | `tests/gui/test_shell.py` | OK |
| The view shown in its own window | View › Own Windows › Open in Own Window (`view.breakout`, `Ctrl+Shift+D`) | [§3](../../USER_MANUAL.md#open-a-view-in-its-own-window) | `tests/gui/test_breakout.py` | OK |
| The menu bar shown or hidden | View › Menu Bar (`view.menu_bar`) | [§3](../../USER_MANUAL.md#3-starting-the-app) | `tests/gui/test_menu_bar.py::test_the_menu_bar_can_be_hidden_and_the_choice_is_kept` | OK |
| Every status-bar entry | View › Status Bar: All Details (`view.status_details`) | [§3](../../USER_MANUAL.md#3-starting-the-app) | `tests/gui/test_shell_chrome.py` | OK |
| The rail as icons only | View › Navigation: Icons Only (`view.rail_icons`) | [§3](../../USER_MANUAL.md#3-starting-the-app) | `tests/gui/test_shell.py` | OK |
| Quit | File › Quit (`file.quit`; the platform's keys) | [§3](../../USER_MANUAL.md#3-starting-the-app) | `tests/gui/test_main_window.py` | OK |
| Every command runs from the palette | `Ctrl+K`, then its name | [§3](../../USER_MANUAL.md#3-starting-the-app) | `tests/gui/test_feature_access_gui.py::test_every_command_is_in_the_palette_and_runs_from_it` | OK |

## CLI

Each `spacemissionstudio` command, every one of its flags, and where a
user of the app does the same
([Use the command line](../user-manual/command-line.md)). A command is
"CLI only" when it serves scripts, batch jobs or an administrator and the
app has the result another way.

| Command | Flags | GUI counterpart | Test | Status |
|---|---|---|---|---|
| `validate` | `--explain` | The Problems panel (`Ctrl+J`); a problem's rule in its tooltip | `tests/test_cli.py` | OK |
| `run` | `--out-dir` `--oem` `--oem-stride` `--oem-interpolation` `--allow-scripts` `--bundle` `--explain` `--save` `--store` | Run (`Ctrl+R`); Results › Plots › Export all... (CSV, bundle, OEM with its stride and interpolation); the run's script steps ask first; Show calculation; every run is kept (Run › History). `--store` (another run store) is for scripts | `tests/test_cli.py` | OK |
| `runs` | `--store` | **Run › History** | `tests/test_cli.py` | OK |
| `compare` | `--store` `--out` | **Results › Compare**; `--out` (JSON) has no counterpart | `tests/test_cli.py` | Backlog: the JSON file, about 1.5 hours (FA-9) |
| `assumptions` | `--area` `--changed` `--yaml` | **Scenario › Assumptions** (the areas, the changed ones in bold, New... writes a configuration file) | `tests/test_cli.py` | OK |
| `reproduce` | `--out-dir` `--rtol` `--allow-scripts` | none: open the bundle's `scenario_as_run.json`, Run, then Results › Compare | `tests/test_reproduction.py` | Backlog: Reports › Reproduce a Bundle..., about 6 hours |
| `monte-carlo` | `--archive-dir` `--overwrite` `--allow-scripts` `--case` `--out-dir` `--runs` `--processes` `--summarize` `--csv` `--report` | Run Mode › Monte Carlo (archive folder on **Run › Run**, runs and processes in **Scenario › Monte Carlo**); Run This Case; Open Monte Carlo Results...; Export table CSV..., Export report... | `tests/test_monte_carlo_report.py` | OK |
| `lifetime` | `--spacecraft` `--deorbit-perigee-km` `--max-years` `--forecast-percentile` `--drag-coeff` `--out` `--explain` | **Run › End of Life**: its fields, Export JSON..., Show calculation | `tests/test_lifetime.py` | OK |
| `model` | `--spacecraft` `--apply` `--export-obj` | Tools › 3D Model...; Apply the model; Export .obj... | `tests/test_model3d.py` | OK |
| `check-design` | `--spacecraft` `--samples` `--explain` `--out` `--tables` | **Run › Design Checks**: Check, Save...; each finding's rule; the samples are the parameter in **Scenario › Assumptions** | `tests/test_design_checks.py` | OK |
| `budgets` | `--spacecraft` `--csv` `--explain` `--pointing` | **Budgets › Power**, **Mass**, **Pointing**; Copy as CSV; the findings with their rules | `tests/test_budgets_import_and_cli.py` | OK |
| `model-analyses` | `--spacecraft` `--out` `--tables` | **Results › Model Analyses** › Save... | `tests/test_run_analyses.py` | OK |
| `thermal` | `--spacecraft` `--case` `--no-sizing` `--out` `--tables` `--generate` `--replace` `--sweep` `--sensitivity` `--relative` `--monte-carlo` | **Run › Thermal**: the case, Size the heaters, Save..., Studies; Thermal model › Generate from the 3D model | `tests/test_thermal_studies.py` | OK |
| `plan opportunities` | `--geometry` `--from-run` `--csv` | **Run › Plan** › Plan (Geometry from the last run); the windows on the Timeline and in Export... | `tests/test_operations_opportunities.py` | OK |
| `plan schedule` | `--geometry` `--from-run` `--seed` `--iterations` `--plan-out` `--out` | **Run › Plan** › Plan, Save plan..., Export...; the seed and iterations are in the section (Scenario › JSON) | `tests/test_operations_scheduler.py` | OK |
| `plan verify` | `--geometry` `--from-run` `--strict` `--out` | **Run › Plan** › Fly and verify; the flags in Problems | `tests/test_operations_flight.py` | OK |
| `plan export` | `--geometry` `--from-run` `--out` | **Run › Plan** › Export... | `tests/test_operations_exports.py` | OK |
| `plan replan` | `--from` `--plan-out` `--geometry` `--from-run` `--out` | **Run › Plan** › Replan, Lose this pass | `tests/test_operations_phase3.py` | OK |
| `plan robustness` | `--runs` `--seed` `--lost-pass-probability` `--margin-sigma-db` `--slew-spread` `--soc-range` `--replan` `--out` | **Run › Plan** › Robustness: its fields, Run robustness, Save batch... | `tests/test_operations_phase3.py` | OK |
| `plan compare` | `--out` | **Run › Plan** › Compare with... | `tests/test_operations_phase3.py` | OK |
| `reentry` | `--spacecraft` `--population-density` `--out` | **Run › End of Life › Re-entry casualty (preliminary)**: Population density, Save... | `tests/test_reentry.py` | OK |
| `budget` | `--spacecraft` `--run` `--launch-delays` `--altitudes` `--out` `--explain` | **Budgets › Propellant**: Compute budget (after a run for orbit control), Launch delays, Altitude trade, Show calculation, Copy as CSV. `--out` (JSON) is for scripts | `tests/test_propellant_budget.py` | OK |
| `link-budget` | `--spacecraft` `--station` `--range-km` `--elevation-deg` `--pointing-deg` `--explain` `--out` | none at a chosen range: the app shows the link margin over a run (Results › Dashboard, Show calculation) | `tests/test_link_budget.py` | CLI only: a what-if at one geometry for scripts; the app gives the run's own geometry |
| `network` | `--offline` | **Settings › Network** › Work offline | `tests/test_network.py` | OK |
| `kernels-status` | none | Tools › Check Reference Data; Tools › Reference Data... › Download... | `tests/test_cli.py` | OK |
| `earth-orientation` | `--fetch` `--import` `--rollback` | Tools › Reference Data... › Download..., Import..., Roll back | `tests/gui/test_data_panel_widget.py` | OK |
| `plugins` | none | **Scenario › Assumptions** (the plugins loaded) | `tests/test_plugins.py` | OK |
| `history` | `--spacecraft` `--field` | File › Change History... (its spacecraft and field filters) | `tests/test_history.py` | OK |
| `small-bodies` | `--fetch` `--import` | Tools › Reference Data... › Download..., Import... | `tests/gui/test_data_panel_widget.py` | OK |
| `gaseous-attenuation` | `--fetch` `--import` | Tools › Reference Data... › Download..., Import... | `tests/test_gaseous_attenuation.py` | OK |
| `ccsds-validate` | none | Tools › Check a CCSDS File... | `tests/test_ccsds_files.py` | OK |
| `ccsds-export` | `--out` | File › Export Orbits as CCSDS... | `tests/test_ccsds_files.py` | OK |
| `ccsds-import` | `--spacecraft` `--set-epoch` `--out` | **Orbit / mass** › Import... (asks before it moves the scenario epoch) | `tests/gui/test_ccsds_gui.py` | OK |
| `idm-info` | `--configuration` `--body-element` | 3D Model... › Import IDM-CIC... (the dialog lists the elements and configurations) | `tests/test_idm_import.py` | OK |
| `idm-import` | `--spacecraft` `--configuration` `--stowed-configuration` `--body-element` `--apply-facets` `--origin` `--devices` `--bus-load` `--solar-panels` `--property-map` `--battery` `--budgets` `--out` | 3D Model... › Import IDM-CIC...: each option in the dialog | `tests/gui/test_idm_import_dialog.py` | OK |
| `export-fsw` | `--spacecraft` `--out` `--steps` `--overwrite` `--record` | **Reports › Flight Software** › Export... (recorded in the scenario) | `tests/gui/test_fsw_workbench_widget.py` | OK |
| `fsw-status` | none | **Reports › Flight Software**: each card's status (up to date, stale) | `tests/gui/test_fsw_workbench_widget.py` | OK |
| `sil` | `--spacecraft` `--binary` `--transport` `--deadline-ms` `--step-timeout` `--handshake-timeout` `--report` `--residuals-csv` `--max-error` | Run Mode › SIL; **Run › Run** (spacecraft, program, options); Reports › Flight Software › Save report... | `tests/gui/test_sil_widgets.py` | OK |
| `spaceweather-resolve` | none | none before a run: the run's provenance (Results › Overview) names the file used | `tests/test_spaceweather.py` | CLI only: a check before a batch job; the app shows the file each run used |
| `spaceweather-download` | `--dataset` | Tools › Reference Data... › Download... › Space weather (the full file) | `tests/test_spaceweather.py` | OK |
| `generate-constellation` | `--out` `--template-spacecraft` `--total-satellites` `--planes` `--phasing-factor` `--altitude-km` `--inclination-deg` `--pattern` `--eccentricity` `--arg-periapsis-deg` `--raan-offset-deg` `--name-prefix` `--phasing-keeping` `--phasing-control-law` `--append` | Tools › Scenario › Generate Walker Constellation...: each option in the dialog | `tests/gui/test_constellation_dialog.py` | OK |
| `generate-phasing-formation` | `--out` `--chief` `--follower-name` `--template-spacecraft` `--radial-km` `--along-track-km` `--cross-track-km` `--reconfiguration-interval-days` `--tolerance-fraction` `--restore-tolerance-fraction` `--correction-window-days` `--max-drift-days` `--max-delta-semi-major-axis-km` `--station-keeping-target-altitude-km` `--station-keeping-deadband-km` `--thrust-n` `--isp-s` `--propellant-kg` `--eclipse-sunlit-threshold` `--min-on-time-s` `--eccentricity-neutral-burns` `--control-law` | Tools › Scenario › Generate Phasing Formation...: each option in the dialog | `tests/gui/test_phasing_formation_dialog.py` | OK |
| `generate-roe-formation` | `--out` `--chief` `--follower-name` `--template-spacecraft` `--roe` `--safe` `--control-law` | Tools › Scenario › Generate ROE Formation...: each option in the dialog | `tests/gui/test_roe_formation_dialog.py` | OK |
| `gui` | none | the app itself | `tests/gui/test_app.py` | OK |

Flags that only a script needs are named in the row: `run --store` and
`runs --store` (another run store than the app's), `budget --out` (the
budget as JSON), `spaceweather-download --dataset SW-Last5Years` (the
smaller file). The rest of `--out` and `--out-dir` flags are the app's
file dialogs.

## Scenario fields without a form

Every field of the scenario file has a form field, or is on this list
with its reason (`tests/test_feature_access.py` keeps the list and the
code in step):

| Field | Why it has no form field | Status |
|---|---|---|
| `operations.activity_types`, `operations.requests`, `operations.scheduler` (`objective`, `weights`, `priority_weights`, `improvement_iterations`), `operations.what_if`, `operations.verification` (`soc_points`, `memory_fraction`, `sun_elevation_deg`) | No form yet: edited in **Scenario › JSON**, with completion and help; Run › Plan edits the locks | Backlog: about 24 hours |
| `fsw_exports[].config_digest`, `exported_utc`, `basilisk_revision` | Written by Reports › Flight Software › Export...; a record, not an input | OK |
| `navigation_error.*_step_*`, `*_bound_*` | The Navigation error group makes its fields from the channel list, so the names are not in the code | OK |

## What the tests check

- `tests/gui/test_feature_access_gui.py`: every command of the window has its
  palette entry and runs from it (dialogs answered at once); the palette's
  pages, settings and exports open; this page names every command with
  the keys it has; the new paths work end to end.
- `tests/test_feature_access.py`: every command-line command and flag has
  its row in [CLI](#cli); each manual link and each test this page names
  exists; the status counts of [Summary](#summary) are right; every
  scenario field is named in the GUI code or listed in
  [Scenario fields without a form](#scenario-fields-without-a-form).
- `tests/gui/test_menu_bar.py`: every command is in exactly one menu.

---

**Next:** [Capabilities and verification](capabilities.md) ·
[Use the command line](../user-manual/command-line.md) ·
[Documentation index](../README.md)
