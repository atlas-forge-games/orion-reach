# Building information — v0.81.1

Right-click a building in the planetary overview to open its description without
leaving the planet or executing its normal action. Close with Esc, right-click
again, or use Close. The previous keyboard focus is restored.

The panel shows the building's purpose, base effects at that world's mineral
richness, workforce bonuses, base Credit upkeep and energy demand. Base values
are explicitly labelled as preceding empire bonuses and administration. Live
operating status distinguishes operational, disabled, unpowered and backup
facilities. Queued buildings explain that their effects begin after completion.
Duplicate facilities show their individual status counts.

Headquarters and shipyards describe their roles and do not invent separate
building costs. Mothership modules use their module names and existing artwork;
right-clicking an empty bay does nothing. Normal left-click actions, including
Space Hub recruitment, continue to work.

For a stored survey, the inspector uses the previously observed building list
and mineral richness. It does not query current enemy bonuses or reveal current
operating state. Inspection does not modify assignments, construction, ownership,
ship orders or saved campaign data.

## Validation

39 focused tests and 12 subtests passed, covering the actual App's building
inspection, scaled viewport input, closing/focus restoration, ordinary left-click
management, queued/disabled structures, special landmarks, stale enemy surveys,
mothership modules, existing output pop-ups and research/designer dialogs.

```sh
python -m pytest -q tests/test_building_info.py tests/test_colony_scene.py \
  tests/test_planet_overview.py::PlanetOverviewInterfaceTests \
  tests/test_production_breakdown.py tests/test_habitat_modules.py \
  tests/test_research_overview.py \
  tests/test_designer_planning.py::BlueprintPlanningUITests
```

An initial run including all planetary-overview gameplay tests also encountered
three old ship-purchase/legacy-save fixture failures. The same three failed in
the unchanged baseline; no gameplay code was modified for this update.
Factory and Space Hub dialogs were rendered for layout review at 1440×900.
Python compilation passed. Save format 57 and balance format 20 are unchanged.
