# Planet surfaces and Ice migration validation — v0.77

The v0.77 patch was checked against a source snapshot of v0.76.1 taken before
the changes. The test environment uses Python 3.12, pygame-ce and SDL dummy
video/audio drivers.

Run the targeted checks from the project root:

```bash
python -m unittest discover -s tests -p "test_ice_planets.py" -v
python -m unittest discover -s tests -p "test_planet_surface_art.py" -v
python -m unittest discover -s tests -p "test_colony_scene.py" -v
python -m unittest discover -s tests -p "test_outposts.py" -v
```

The broader selection covered colony scenes, planet overviews, colonies,
population, races, colonization, tomb worlds, civilization legacies, race
victories, the balance editor, research, planetary combat, outposts,
exploration and production breakdowns, plus the new Ice/art tests.
It ran 236 tests: 231 passed, four failed and one errored. A subsequent final
colony-scene run passed all eight tests, including the additional placement
regression check. The outpost suite was rerun after removing its oval base.

The same five failing test identities occur in the unchanged baseline:

| Test | Existing issue |
| --- | --- |
| `test_planet_overview.ProductionTests.test_buy_uses_remaining_work_completes_now_and_preserves_next_project` | Expects an older ship work cost: 60 versus 164. |
| `test_planet_overview.ProductionTests.test_buying_ships_commissions_once_with_unique_ids_and_owner` | Expects old scout hull values: 8 versus 20. |
| `test_planet_overview.WorkforceSaveTests.test_v11_migrates_both_current_worlds_and_stale_surveys_and_preserves_source` | Its synthetic old save fails existing ship validation. |
| `test_population.PopulationSaveTests.test_v10_migrates_planets_and_surveys_without_rewriting_or_losing_fields` | Hard-codes save version 52; the baseline already uses 53 and v0.77 uses 54. |
| `test_races.RaceSetupTests.test_all_portraits_and_fallback_seals_render_and_foodless_workers_are_clear` | The reconstructed test workspace lacks the original Terran portrait PNG. |

Legacy fixture JSON files were left untouched. The new migration test loads a
format-53 save containing Tundra worlds and stored surveys, verifies that the
source file and returned source data remain unchanged, preserves custom biome
numbers and user-defined names, then saves/reloads a current-format Ice game.

Render the actual overview for every biome with:

```bash
python tools/preview_planet_surfaces.py
```

The previews use the installed building artwork through the normal loader.
The reconstructed workspace lacks six original building PNGs, so those use
the existing fallback sprites during visual QA. This patch does not replace
building art; complete installations retain their detailed building sprites.

The visual review included both overview aspect ratios, Ocean shoreline
placement, dense Ice colonies, faded queued buildings and their captions.
The image loader preserves aspect ratio, scales from original pixels, caches
per biome/viewport and falls back when an optional image cannot be loaded.
