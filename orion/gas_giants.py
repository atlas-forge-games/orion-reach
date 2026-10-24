"""Uninhabitable outer-system gas giants, seeded only in new campaigns."""

import random
from dataclasses import dataclass, replace

from .frame_cache import cached_in_frame

BIOME = 'Gas Giant'
SETTLEMENT_ERROR = 'Gas giants cannot be colonized: no solid surface.'
OUTPOST_ERROR = 'Gas giants cannot support surface outposts.'

STATION_HULL = 60
ASSEMBLY_TURNS = 2
REPAIR = 4


@dataclass(frozen=True)
class StationSpec:
    name: str
    resources: int
    credits: int
    output: int
    upkeep: int
    unit: str
    art: str


STATIONS = {
    'refinery': StationSpec('Gas refinery', 80, 20, 6, 1, 'CR', 'mine'),
    'energy': StationSpec('Energy platform', 120, 30, 8, 2, 'energy', 'fusion_plant'),
    'research': StationSpec('Research station', 100, 40, 4, 2, 'RP', 'research_lab'),
}
# One stable property per giant; derived without changing the galaxy RNG.
TRAITS = {
    'ordinary': ('Ordinary atmosphere', 'Standard construction and output.'),
    'gas_rich': ('Gas-rich atmosphere', '+25% refinery output.'),
    'magnetic': ('Strong magnetic field', '+25% energy output.'),
    'storms': ('Extreme storms', '+25% research; +25% construction cost; +1 CR upkeep.'),
    'calm': ('Calm atmosphere', 'Construction costs 20% less.'),
}


@dataclass
class OrbitalStation:
    kind: str
    owner: str
    hull: int = STATION_HULL
    ready_turn: int = 0
    last_attacked: int = 0

    @classmethod
    def from_dict(cls, row, owners, turn=1_000_000):
        if (not isinstance(row, dict) or set(row) != {'kind', 'owner', 'hull', 'ready_turn', 'last_attacked'}
                or row['kind'] not in STATIONS or row['owner'] not in owners
                or any(type(row[k]) is not int for k in ('hull', 'ready_turn', 'last_attacked'))
                or not 1 <= row['hull'] <= STATION_HULL
                or not 0 <= row['ready_turn'] <= turn+ASSEMBLY_TURNS
                or not 0 <= row['last_attacked'] <= turn):
            raise ValueError('Invalid gas giant orbital station')
        return cls(**row)


def trait(game, system_id, planet_id):
    rng = random.Random(f'orion-gas-properties-v1:{game.seed}:{system_id}:{planet_id}')
    return rng.choices(tuple(TRAITS), weights=(4, 2, 2, 1, 2))[0]


def specification(game, system_id, planet_id, kind):
    base = STATIONS[kind]
    prop = trait(game, system_id, planet_id)
    cost = 125 if prop == 'storms' else 80 if prop == 'calm' else 100
    bonus = (prop, kind) in (('gas_rich', 'refinery'), ('magnetic', 'energy'), ('storms', 'research'))
    return replace(base, resources=(base.resources*cost+99)//100,
                   credits=(base.credits*cost+99)//100,
                   output=base.output*(125 if bonus else 100)//100,
                   upkeep=base.upkeep+(prop == 'storms'))


def installations(game, owner=None):
    return [(s, p) for s in game.systems for p in s.worlds
            if p.orbital_station and (owner is None or p.orbital_station.owner == owner)]


@cached_in_frame
def blockaded(game, system_id, owner):
    from . import monsters, encounters
    from .navigation import hostile
    return (monsters.alive_at(game, system_id) or encounters.blockade(game, system_id)
            or any(hostile(game, s.owner, owner) and (s.damage or s.drone_bays)
                   for s in game.ships if not s.in_transit and s.system_id == system_id))


def operating(game, system_id, planet):
    station = planet.orbital_station
    return bool(station and game.turn >= station.ready_turn and not blockaded(game, system_id, station.owner))


def status(game, system_id, planet):
    if blockaded(game, system_id, planet.orbital_station.owner):
        return 'Blockaded · output suspended'
    remaining = planet.orbital_station.ready_turn-game.turn
    return f'Assembly · {remaining} turns remaining' if remaining > 0 else 'Operational'


@cached_in_frame
def income(game, owner):
    """Gross Credits, RP, upkeep. Upkeep continues during assembly/blockade."""
    credits = research = upkeep = 0
    for system, planet in installations(game, owner):
        station = planet.orbital_station
        spec = specification(game, system.id, planet.id, station.kind)
        upkeep += spec.upkeep
        if operating(game, system.id, planet):
            credits += spec.output if station.kind == 'refinery' else 0
            research += spec.output if station.kind == 'research' else 0
    return credits, research, upkeep


@cached_in_frame
def power_supply(game, owner):
    result = {}
    for system, planet in installations(game, owner):
        if planet.orbital_station.kind == 'energy' and operating(game, system.id, planet):
            result[system.id] = result.get(system.id, 0)+specification(game, system.id, planet.id, 'energy').output
    return result


def dispatch_power(game, owner, colonies, bonuses, resources, *, supply=None):
    """One finite system pool, allocated to deficits before backup fuel.

    Colonies are (system ID, planet) pairs, including forecast copies. Mobile
    habitats receive power only while anchored in the system, never in transit.
    """
    from . import economy
    supply = dict(power_supply(game, owner) if supply is None else supply)
    result = {}
    travelling = {s.habitat.id for s in game.ships if s.habitat and s.in_transit}
    for sid, planet in colonies:
        base = economy.energy_report(planet, dict(bonuses))
        allocation = (min(supply.get(sid, 0), max(0, base.demand-base.base_generated))
                      if planet.id not in travelling and not base.unlimited else 0)
        supply[sid] = supply.get(sid, 0)-allocation
        local = dict(bonuses)
        local['colony_energy'] = local.get('colony_energy', 0)+allocation
        report = economy.energy_report(planet, local, fuel_budget=resources)
        result[id(planet)] = replace(report, orbital_generated=allocation)
        resources -= report.fuel_used
    return result


def builders(game, system_id, owner='player'):
    return [s for s in game.fleet_at(system_id, owner) if s.kind == 'outpost_ship' and not s.has_course]


def build_error(game, system_id, planet_id, kind, owner='player'):
    from . import defenses
    if reason := game.strategy_error(owner):
        return reason
    planet = game.planet_at(system_id, planet_id)
    if not planet.is_gas_giant or kind not in STATIONS:
        return 'Choose a gas giant and a station specialization.'
    if planet.orbital_station:
        return 'Only one main station may orbit each gas giant.'
    if not game.system_visible(system_id, owner):
        return 'Send a ship to refresh this survey first.'
    if blockaded(game, system_id, owner):
        return 'Clear hostile fleets and guardians before construction.'
    if any(p.owner != owner for p in defenses.bases(game, system_id)):
        return 'Clear opposing missile bases before construction.'
    if not game.settlements_at(system_id, owner) and not builders(game, system_id, owner):
        return 'Requires a local colony or an idle outpost ship.'
    spec = specification(game, system_id, planet_id, kind)
    if game.resources_for(owner) < spec.resources or game._empire(owner).credits < spec.credits:
        return f'Requires {spec.resources} Resources and {spec.credits} Credits.'
    return None


def build(game, system_id, planet_id, kind, owner='player'):
    from .model import RuleError
    from .exploration import refresh
    if reason := build_error(game, system_id, planet_id, kind, owner):
        raise RuleError(reason)
    spec = specification(game, system_id, planet_id, kind)
    # An established colony supplies construction crews; remote sites consume
    # the outpost ship as a prefabricated orbital foundation.
    if not game.settlements_at(system_id, owner):
        game.ships.remove(builders(game, system_id, owner)[0])
    game._empire(owner).resources -= spec.resources
    game._empire(owner).credits -= spec.credits
    planet = game.planet_at(system_id, planet_id)
    planet.orbital_station = OrbitalStation(kind, owner, ready_turn=game.turn+ASSEMBLY_TURNS)
    refresh(game)
    return planet.orbital_station


def attack_error(game, system_id, planet_id, owner='player', *, capture=False):
    from . import defenses, diplomacy
    from .victory import troop_transports
    if reason := game.strategy_error(owner):
        return reason
    planet = game.planet_at(system_id, planet_id)
    station = planet.orbital_station
    if not station or station.owner == owner:
        return 'Choose an opposing orbital station.'
    if not game.system_visible(system_id, owner):
        return 'Send ships to the station first.'
    if reason := diplomacy.aggression_error(game, owner, station.owner):
        return reason
    if (blockaded(game, system_id, owner) or game.foreign_fleet(system_id, owner)
            or any(p.owner != owner for p in defenses.bases(game, system_id))):
        return 'Defeat opposing ships and missile bases first.'
    if not defenses.bombardment_fleet(game, system_id, owner):
        return 'Bring armed ships that have not bombarded this turn.'
    if capture:
        if station.hull > STATION_HULL//2:
            return f'Damage the station to {STATION_HULL//2} hull or less before capture.'
        if not any(not s.has_course for s in troop_transports(game, system_id, owner)):
            return 'Capture consumes one idle troop transport for the occupation crew.'
    return None


def attack(game, system_id, planet_id, owner='player', *, capture=False):
    from . import defenses
    from .model import RuleError
    from .victory import record_ground_hostility, troop_transports
    from .exploration import refresh, record_survey
    if reason := attack_error(game, system_id, planet_id, owner, capture=capture):
        raise RuleError(reason)
    planet = game.planet_at(system_id, planet_id)
    station = planet.orbital_station
    defender = station.owner
    name = STATIONS[station.kind].name
    if capture:
        ship = next(s for s in troop_transports(game, system_id, owner) if not s.has_course)
        game.ships.remove(ship)
        station.owner = owner
        station.ready_turn = max(station.ready_turn, game.turn+1)
        message = f'{name} at {planet.name} captured; occupation crew deployed.'
    else:
        damage = min(station.hull, sum(d for d, _ in defenses.bombardment_attacks(game, system_id, owner)))
        station.hull -= damage
        message = f'{name} at {planet.name}: {damage} damage; {station.hull}/{STATION_HULL} hull.'
        if station.hull == 0:
            planet.orbital_station = None
            message = f'{name} at {planet.name} destroyed.'
    station.last_attacked = game.turn
    for ship in defenses.bombardment_fleet(game, system_id, owner):
        ship.bombarded_turn = game.turn
        if ship.departure_pending:
            game._clear_course(ship)
    record_ground_hostility(game, owner, defender, message)
    record_survey(game, system_id, defender)
    refresh(game)
    return message


def dismantle(game, system_id, planet_id, owner='player'):
    from .model import RuleError
    from .exploration import refresh, record_survey
    game._require_strategy(owner)
    planet = game.planet_at(system_id, planet_id)
    if not planet.orbital_station or planet.orbital_station.owner != owner:
        raise RuleError('Choose your own orbital station.')
    planet.orbital_station = None
    record_survey(game, system_id, owner)
    refresh(game)
    return f'Station at {planet.name} dismantled. No refund.'


def advance(game):
    for system, planet in installations(game):
        station = planet.orbital_station
        if not blockaded(game, system.id, station.owner) and station.last_attacked < game.turn-1:
            station.hull = min(STATION_HULL, station.hull+REPAIR)


def ai_orders(game, owner):
    from .navigation import hostile
    messages = []
    for system, planet in list(installations(game)):
        if hostile(game, owner, planet.orbital_station.owner) and game.system_visible(system.id, owner):
            capture = attack_error(game, system.id, planet.id, owner, capture=True) is None
            if capture or attack_error(game, system.id, planet.id, owner) is None:
                message = attack(game, system.id, planet.id, owner, capture=capture)
                if game.system_visible(system.id) or 'player' == owner:
                    messages.append(message)
    if game._empire(owner).credits < 100 or game.resources_for(owner) < 200:
        return messages
    candidates = []
    for system in game.systems:
        if not game.system_visible(system.id, owner):
            continue
        colonies = game.settlements_at(system.id, owner)
        # Keep remote outpost ships on their refuelling-expansion orders.
        if not colonies:
            continue
        deficit = sum(max(0, -game.planet_energy(p).balance) for p in colonies)
        for planet in system.worlds:
            if not planet.is_gas_giant or planet.orbital_station:
                continue
            kind = 'energy' if deficit >= 4 else 'research' if trait(game, system.id, planet.id) == 'storms' and game.empire_rates_for(owner)[0] > 6 else 'refinery'
            if build_error(game, system.id, planet.id, kind, owner) is None:
                candidates.append((deficit if kind == 'energy' else 0, system.id, planet.id, kind))
    if candidates:
        _, sid, pid, kind = max(candidates)
        build(game, sid, pid, kind, owner)
        game.rival_event(f'Commissioned {STATIONS[kind].name} at {game.planet_at(sid, pid).name}.', owner=owner)
    return messages


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
