# Age of the Stars — v0.98.2 mineral scarcity

Rare mineral-rich worlds now provide much stronger mining output. Void worlds
contain no extractable minerals, but can still support other colony activities
and use Resources from the shared empire stockpile.

| Mineral class | Mining multiplier | Ordinary generation chance |
| --- | ---: | ---: |
| Void | ×0 | 10% |
| Poor | ×0.3 | 30% |
| Average | ×1 | 50% |
| Rich | ×4 | 9% |
| Ultra-rich | ×10 | 1% |

These chances apply to ordinary generated worlds. Homeworlds start at Average;
Sol's named neighbors and guardian prize worlds retain their fixed classes.
Galaxy positions and planet terrain remain stable for a given seed. The AI
avoids mining facilities and miner assignments on worlds with no minerals.

## Install

Extract this incremental ZIP into your existing repository beside `orion/`,
`assets/`, `tests/` and `docs/`, replacing the included files. Restart the game.
The required base is **v0.98.1**, commit `6a301da`. No new dependencies are needed.

Fresh standard games use the new values. Existing campaigns keep their saved
mineral multipliers and planet classes. If you use a saved `balance.json`, reset
its Mineral richness entries in the balance editor before starting a new game
to adopt these defaults. The editor now also exposes generation weights.

Campaign save format is **67**. Previous saves remain readable. Newly written
saves require this version or later. Balance profile format is **23**.

See [mineral rules and examples](docs/mineral-richness.md) and
[the balance editor guide](docs/balance-editor.md).

## Validation

The 15 focused mineral tests pass. They exercise actual colony production,
Void bonuses and fuel use, construction with imported Resources, weighted
generation, stable seeded maps, Average homeworlds, AI behavior, profile
validation and save round-trips. Existing mining regressions use the new values.

A save produced by unmodified v0.98.1 loaded without changing its campaign data
or saved multipliers and round-tripped through the new format. The balance
editor and Void production breakdown were rendered and visually inspected.

The broader run passed 140 tests and 165 subtests. Its 30 failing cases also
fail on unmodified v0.98.1; there are no new failing cases in these suites.
Run the focused checks for this update:

```bash
python -m pytest tests/test_mineral_richness.py -q
```

## Commit commands

```bash
git status
git add README.md docs/mineral-richness.md docs/balance-editor.md docs/planet-environments.md
git add orion/__init__.py orion/buildings.py orion/model.py orion/home_systems.py
git add orion/economy.py orion/production_breakdown.py orion/ai.py
git add orion/balance.py orion/storage.py orion/encyclopedia.py orion/monsters.py
git add tests/test_mineral_richness.py tests/test_building_economy.py tests/test_repeatable_buildings.py
git add tests/test_research_progression.py tests/test_resources_energy.py
git diff --cached --stat
git commit -m "Add mineral scarcity and stronger rare-world mining bonuses (v0.98.2)"
git push
```
