# Age of the Stars — v0.97.5 randomized home systems

Every non-Terran player now starts in a seeded system of **1–7 planets**.
The homeworld keeps its existing properties and starting population; neighboring
planets have random types, sizes, minerals and orbits. Terrans retain Sol's
Mercury, Venus, Earth and Mars layout.

## Rules

- Planet count includes the homeworld. A one-planet system contains just that
  world; larger systems have independently generated neighbors.
- Native homes remain intact: Skirr keep a Toxic home, Nexus keep an Ice home,
  Aelari keep an Ocean home, and other races retain their existing home biome.
- Neighboring worlds can include Toxic planets and an outer Gas Giant.
- Using the same race and galaxy seed reproduces the same starting system.
  The random-start-position option still controls the star's location only.
- Starting populations, workforce allocation and fleets retain their existing
  rules. Wanderers keep their populated mothership and its 50-billion limit.
- Varkesh raids return captives to the correct original homeworld even in a
  one- or two-planet system.

AI home systems already use generated planets and keep that behavior. The new
player-system generator uses separate random state, preserving the galaxy's
star positions and rival placement for the same settings.

## Installation

Extract this ZIP into the existing game repository, beside `orion/`, `tests/`
and `docs/`, and allow the included files to be replaced. Restart the game.
This is an incremental update based on v0.97.4 (commit `b5a11ab`).

**Start a new game to get a randomized home system.** Existing saves retain
their current planets and work without conversion.
Save format remains 65; no new dependencies or artwork are required.

## Validation

The generation tests check 96 seeds for each of the 12 non-Terran races,
alongside actual campaign starts, preserved homeworld properties, Terran Sol,
fleets, Varkesh raids, motherships, repeatability and save continuation.

The focused generation, naming, environment, faction, starvation and population
checks passed **61 tests and 118 subtests**. Broader starting-fleet, Varkesh,
mothership, full-roster and observer checks passed another **92 tests and 87
subtests**. Five older tests fail identically on v0.97.4: two expect save version
52, one expects pre-starvation raid loot, and two exercise older save migrations.
No additional test failures were observed.

Real start-game, system, colony, ship-designer and save/load flows were checked
for Nexus, Kharuun, Varkesh, Wanderers and Terrans, including one-planet starts.

Run the focused checks from the repository root:

```bash
python -m unittest discover -s tests -p test_random_home_systems.py
python -m unittest discover -s tests -p test_home_systems.py
```

## Commit commands

```bash
git status
git add README.md orion/__init__.py orion/home_systems.py orion/model.py orion/raiding.py orion/system_views.py tests/scenarios.py tests/test_environments.py tests/test_home_systems.py tests/test_random_home_systems.py
git commit -m "Randomize non-Terran starting systems while preserving homeworlds"
git push
```
