# Age of the Stars — v0.97.4 food-shortage update

Food deficits now reduce the population of every food-dependent colony.
Previously this happened only to the Skirr; other colonies merely stopped
growing when they ran out of food.

## Rules

- A negative local food balance costs **1 billion inhabitants per turn** and
  resets accumulated growth progress. The existing **1-billion minimum** remains.
- Starvation applies at the population limit, to AI colonies and to mothership
  habitats. Species counts and worker assignments shrink with the population.
- Exactly meeting food demand prevents losses. Ordinary growth resumes once
  food production exceeds demand, subject to the usual environment and capacity
  rules. Surplus food on another colony cannot cover the deficit.
- Civilizations that need no food retain their normal assembly or passive growth.
  Mixed populations that still consume food cannot grow during a shortage.
- Food supply is taken from the start of the turn. Farms completed during that
  turn start protecting the colony on the following turn.

The population display shows **-1,000 million / turn** while inhabitants are
being lost. Its explanation and the in-game encyclopedia describe starvation,
and the turn report identifies affected colonies. Construction estimates use
the same population losses as actual turns.

## Installation

Extract this ZIP into the existing game repository, beside `orion/`, `tests/`
and `docs/`, and allow the included files to be replaced. Restart the game.
This is an incremental update based on v0.97.2 (commit `86068a9`); it preserves
the restored title screen and galaxy-map appearance.

Existing saves work without conversion. The new rule applies on the next turn.
Save format remains 65; no new dependencies or artwork are required.

## Validation

New regression tests cover actual starvation turns, the minimum population,
recovery, races that need no food, mixed populations, mothership habitats,
worker assignments, species counts, save/load continuation, farm completion,
construction forecasts and AI-owned colonies. Population display tests also
cover negative rates, balanced food and the minimum-population explanation.

The 19 starvation and population-inspector tests pass. The broader focused run
passed 141 tests; its 14 failures also reproduce on the unchanged v0.97.2 base.
Those existing failures concern older research, save, UI, pricing and economy
expectations and were not changed in this update. The rendered colony screen
and population explanation were also checked.

Run the focused checks from the repository root:

```bash
python -m unittest discover -s tests -p test_starvation.py
python -m unittest discover -s tests -p test_population_info.py
```

## Commit commands

```bash
git status
git add README.md docs/population-display.md orion/__init__.py orion/encyclopedia.py orion/model.py orion/population.py orion/population_info.py tests/test_population.py tests/test_population_info.py tests/test_starvation.py
git commit -m "Apply food-shortage population losses to all food-dependent colonies"
git push
```
