"""Uninhabitable outer-system gas giants, seeded only in new campaigns."""

import random

BIOME = 'Gas Giant'
SETTLEMENT_ERROR = 'Gas giants cannot be colonized: no solid surface.'
OUTPOST_ERROR = 'Gas giants cannot support surface outposts.'


def seed(game):
    """Append a giant without replacing terrestrial worlds or advancing their RNG."""
    from .home_systems import ORBIT_NUMERALS
    from .model import Planet
    homes = {system.id for system, _ in game.settlements()}
    for system in game.systems:
        if (system.id in homes or not system.worlds or len(system.worlds) >= 8
                or any(p.is_gas_giant for p in system.worlds)):
            continue
        rng = random.Random(f'orion-gas-giants-v1:{game.seed}:{system.id}')
        if rng.random() >= .35:
            continue
        orbit = round(system.worlds[-1].orbit_au*rng.uniform(1.6, 2.0), 2)
        if orbit > 500:
            continue
        index = len(system.worlds)
        system.worlds.append(Planet(index, f'{system.name} {ORBIT_NUMERALS[index]}',
                                    BIOME, 'Huge', 'Average', 'High', orbit))
        system.planets = len(system.worlds)
