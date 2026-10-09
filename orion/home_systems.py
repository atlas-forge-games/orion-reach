"""Civilization names for newly founded home systems; no changes on save loading."""

from .races import RACES

ORBIT_NUMERALS = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII")


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
