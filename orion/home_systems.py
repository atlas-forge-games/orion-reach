"""Starting-system generation and names; existing worlds are kept on save loading."""

import random
from .races import RACES

ORBIT_NUMERALS = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII")


def player_home_planet_id(system):
    """Keep the home in the third orbit, or the last orbit in smaller systems."""
    return min(2, len(system.worlds)-1)


def randomize_player_home(system, galaxy_seed, race_id):
    """Replace Sol's neighbors while preserving the player's starting homeworld."""
    from .model import GENERATED_BIOMES, RICHNESSES, generate_planets
    if race_id == "terran":
        return
    home = system.worlds[player_home_planet_id(system)]
    rng = random.Random(f"orion-home-worlds-v1:{galaxy_seed}:{race_id}")
    system.planets = rng.randint(1, 7)
    system.biome = rng.choice(GENERATED_BIOMES)
    system.richness = rng.choice(RICHNESSES[:-1])
    system.worlds = generate_planets(system, galaxy_seed, player_home=False)
    home.id = player_home_planet_id(system)
    scale = home.orbit_au/system.worlds[home.id].orbit_au
    for planet in system.worlds:
        planet.orbit_au = round(planet.orbit_au*scale, 2)
        if planet.id != home.id and rng.random() < .12:
            planet.biome = "Toxic"
    system.worlds[home.id] = home
    # The general gas-giant seeder protects occupied systems. An alien home
    # can still have a giant in an existing outer orbit, without adding planets.
    outer = system.worlds[-1]
    if outer.id > home.id and rng.random() < .35:
        outer.biome, outer.size, outer.richness, outer.gravity = "Gas Giant", "Huge", "Average", "High"
    system.biome, system.richness = system.worlds[0].biome, system.worlds[0].richness


def name_home(game, system, homeworld, race_id):
    """Name a starting colony and its neighbors without changing their properties."""
    race = RACES[race_id]
    used_systems = {s.name for s in game.systems if s.id != system.id}
    used_planets = {p.name for s in game.systems if s.id != system.id for p in s.worlds}
    # A configured rival can share the player's race. Keep the whole name set
    # together, and avoid collisions with any previously named worlds.
    number = 1
    while True:
        suffix = "" if number == 1 else f" {number}"
        system_name = race.home_system+suffix
        neighbors = iter(race.home_neighbors)
        names = []
        for planet in system.worlds:
            if planet.id == homeworld.id:
                name = race.homeworld+suffix
            elif (neighbor := next(neighbors, None)) is not None:
                name = neighbor+suffix
            else:
                name = f"{system_name} {ORBIT_NUMERALS[planet.id]}"
            names.append(name)
        if system_name not in used_systems and not used_planets.intersection(names):
            break
        number += 1
    system.name = system_name
    for planet, name in zip(system.worlds, names):
        planet.name = name
    # Adding a rival to an existing solo game can name an already surveyed
    # system. Update names alone, keeping stale population and ownership private.
    for survey in game.exploration.surveys:
        if survey.system_id == system.id:
            for world, name in zip(survey.worlds, names):
                world["name"] = name
