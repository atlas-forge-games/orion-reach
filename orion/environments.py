"""Species-specific growth efficiency; settlement rights remain separate."""

import random

BIOMES = ('Terran', 'Ocean', 'Desert', 'Ice', 'Barren', 'Volcanic', 'Toxic', 'Gaia')
# Percent of the existing food/assembly/passive growth rate, not percentage points.
_ROWS = {
    'terran':     (100, 90, 70, 50, 40, 25, 25, 125),
    'kharuun':    (100, 60, 120, 90, 150, 130, 60, 110),
    'aelari':     (100, 150, 40, 50, 35, 25, 25, 125),
    'lithar':     (100, 60, 120, 110, 140, 150, 85, 110),
    'varkesh':    (100, 75, 75, 55, 50, 60, 40, 110),
    'wanderers':  (100, 100, 100, 100, 100, 100, 100, 100),
    'xenonflora': (100, 110, 50, 30, 25, 20, 10, 150),
    'nexus':      (60, 50, 110, 150, 130, 85, 110, 75),
    'aetheri':    (100, 90, 100, 60, 85, 150, 100, 110),
    'concord':    (100, 90, 75, 70, 55, 50, 35, 125),
    'serevan':    (100, 90, 70, 60, 40, 30, 25, 125),
    'skirr':      (80, 70, 100, 40, 60, 55, 150, 100),
    'remnant':    (100, 90, 70, 65, 45, 40, 30, 125),
}
PREFERENCES = {rid: {**dict(zip(BIOMES, values)), 'toxic_food': 6 if rid == 'skirr' else 0}
               for rid, values in _ROWS.items()}
NATIVE_HOMES = {'skirr': 'Toxic', 'nexus': 'Ice', 'aelari': 'Ocean'}


def _weighted(planet, key):
    from .species import composition
    counts = composition(planet)
    total = sum(counts.values())
    if not total:
        return PREFERENCES['terran'][key]
    return sum(PREFERENCES[rid][key]*count for rid, count in counts.items())//total


def growth_factor(planet, race_id=None):
    """Actual residents for colonies; an explicit prospective race for surveys/AI."""
    if planet.habitat:
        return 100
    if race_id is not None:
        return PREFERENCES.get(race_id, PREFERENCES['terran'])[planet.biome]
    return _weighted(planet, planet.biome)


def native_food(planet):
    """Toxic biota sustain adapted residents, not every visiting civilization."""
    return _weighted(planet, 'toxic_food') if planet.colonized and not planet.habitat and planet.biome == 'Toxic' else 0


def prepare_home(system, planet, race_id, *, surveys=()):
    """Initialize a native home and keep previously charted terrain consistent."""
    if race_id in NATIVE_HOMES:
        planet.biome = NATIVE_HOMES[race_id]
        if planet.id == 0:
            system.biome = planet.biome
        # A rival may be added to a solo campaign after this world was surveyed.
        # Change only the physical terrain, not stale ownership or population.
        for survey in surveys:
            if survey.system_id == system.id:
                survey.worlds[planet.id]['biome'] = planet.biome


def seed_toxic_worlds(game):
    """Use a separate RNG so new biomes do not rearrange existing star positions."""
    rng = random.Random(f'orion-toxic-worlds-v1:{game.seed}')
    homes = {s.id for s in game.systems if any(p.colonized for p in s.worlds)}
    for system in game.systems:
        if system.id in homes:
            continue
        for planet in system.worlds:
            if planet.biome != 'Gaia' and rng.random() < .12:
                planet.biome = 'Toxic'
                if planet.id == 0:
                    system.biome = 'Toxic'


def race_caption(race_id):
    values = PREFERENCES[race_id]
    best = sorted(BIOMES, key=lambda biome: (-values[biome], BIOMES.index(biome)))[:2]
    return 'Growth: ' + ' · '.join(f'{biome} {values[biome]}%' for biome in best)
