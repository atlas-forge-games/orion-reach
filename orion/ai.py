"""Deterministic expansion AI. All orders use the same rules as player orders."""

from .model import RIVAL, RICHNESSES
from .production import PROJECTS
from .races import RACES
from .research import BRANCHES, choices
from .combat import HOSTILE_BELOW


def available_worlds(game, system):
    return [p for p in system.worlds if not p.colonized and game.can_settle(p, RIVAL)]


def research_choice(game):
    """A stable preference order, using ordinary points and exclusive choices."""
    state = game.research_state(RIVAL)
    if state.active or game.opponent.research == 0:
        return
    race = game.opponent.race_id
    priority = {
        "terran": ("computers", "construction", "society"),
        "kharuun": ("construction", "materials", "physics"),
        "aelari": ("physics", "computers", "biology"),
    }[race]
    branches = priority + tuple(b for b in BRANCHES if b not in priority)
    # Each tuple follows catalogue branch order, with one option per tier.
    preferences = {
        "terran": ((1, 0, 1, 0, 0, 0, 0, 0), (0, 0, 0, 0, 0, 1, 1, 1)),
        "kharuun": ((0, 0, 0, 0, 0, 1, 1, 0), (1, 0, 1, 0, 1, 0, 1, 0)),
        "aelari": ((1, 1, 0, 0, 0, 0, 0, 1), (0, 0, 1, 0, 0, 1, 0, 1)),
    }[race]
    for tier in (1, 2):
        for branch in branches:
            index = tuple(BRANCHES).index(branch)
            technology = choices(branch, tier)[preferences[tier-1][index]]
            if game.research_error(technology.id, owner=RIVAL) is None:
                game.choose_research(technology.id, owner=RIVAL)
                return


def world_quality(planet):
    return planet.habitability, planet.building_capacity, RICHNESSES.index(planet.richness), -planet.id


def development_choice(planet, race_id="kharuun"):
    for item in RACES[race_id].development:
        if item not in planet.buildings:
            return item
    # Keep adding a mix of industry, income and research on larger worlds.
    return ("factory", "trade_center", "research_lab")[(len(planet.buildings)-4) % 3]


def military_orders(game):
    """Guard colonies in peacetime; pursue opposing fleets when hostile."""
    ships = sorted((s for s in game.ships_owned_by(RIVAL) if s.kind == "frigate"), key=lambda s: s.id)
    colonies = [s for s in game.systems if any(p.owner == RIVAL for p in s.worlds)]
    colonies.sort(key=lambda s: (s.id != game.opponent.home_system, s.id))
    hostile = game.diplomacy.relations < HOSTILE_BELOW
    targets = [s for s in game.systems if game.fleet_at(s.id)] if hostile else []
    for index, ship in enumerate(ships):
        if ship.in_transit or game.fleet_at(ship.system_id):
            continue
        if ship.hull < ship.max_hull and game.can_repair(ship):
            continue
        origin = game.systems[ship.system_id]
        destination = (min(targets, key=lambda s: (game.travel_turns(origin, s, RIVAL), s.id))
                       if targets else colonies[index % len(colonies)])
        if destination.id != ship.system_id:
            game.send_ship(ship.id, destination.id, owner=RIVAL)
            game.rival_event(f"Sent {ship.name} to guard {destination.name}." if not hostile else
                             f"Sent {ship.name} toward opposing ships at {destination.name}.")


def run_ai(game):
    """Place orders before this turn's shared travel, production and income phase."""
    research_choice(game)
    military_orders(game)
    for ship in sorted(game.ships_owned_by(RIVAL), key=lambda s: s.id):
        if ship.in_transit or ship.kind != "colony_ship":
            continue
        local = available_worlds(game, game.systems[ship.system_id])
        if local:
            planet = max(local, key=world_quality)
            game.colonize(ship.id, ship.system_id, planet.id, owner=RIVAL)
            game.rival_event(f"Settled {planet.name} with {planet.population} B colonists.")
            continue
        incoming = {}
        for other in game.ships_owned_by(RIVAL):
            if other.in_transit and other.kind == "colony_ship":
                incoming[other.destination] = incoming.get(other.destination, 0)+1
        targets = [s for s in game.systems if len(available_worlds(game, s)) > incoming.get(s.id, 0)]
        if not targets:
            continue
        origin = game.systems[ship.system_id]
        target = min(targets, key=lambda s: (
            game.travel_turns(origin, s, RIVAL),
            tuple(-value for value in world_quality(max(available_worlds(game, s), key=world_quality))), s.id))
        duration = game.send_ship(ship.id, target.id, owner=RIVAL)
        game.rival_event(f"Sent {ship.name} to {target.name}; {duration} turns in transit.")

    colonies = [(s, p) for s in game.systems for p in s.worlds if p.owner == RIVAL]
    colonies.sort(key=lambda row: (-game.planet_yields(row[1])[0], -row[1].population, row[0].id, row[1].id))
    unclaimed = sum(len(available_worlds(game, s)) for s in game.systems)
    fleet_size = sum(s.kind == "colony_ship" for s in game.ships_owned_by(RIVAL)) + sum(
        project.item_id == "colony_ship" for _, p in colonies for project in p.construction_queue)
    warships = sum(s.kind == "frigate" for s in game.ships_owned_by(RIVAL)) + sum(
        project.item_id == "frigate" for _, p in colonies for project in p.construction_queue)
    military_limit = min(3, max(1, len(colonies)//2))
    fleet_limit = min(unclaimed, 3, 1+len(colonies)//2)
    for index, (system, planet) in enumerate(colonies):
        if planet.construction_queue:
            continue
        # The strongest colony supplies ships. Other worlds build their economies.
        # Expansion raises the shipyard's development target, preventing stagnation.
        target_buildings = min(planet.building_capacity, 2+len(colonies)//2)
        produce_ship = index == 0 and fleet_size < fleet_limit and len(planet.buildings) >= target_buildings
        produce_frigate = (index == 0 and game.turn >= 12 and len(planet.buildings) >= 2
                          and warships < military_limit)
        if produce_frigate:
            if game.ship_build_error(system.id, planet.id, "frigate", owner=RIVAL) is None:
                game.queue_ship(system.id, planet.id, "frigate", owner=RIVAL)
                warships += 1
                game.rival_event(f"Started a frigate on {planet.name}.")
        elif produce_ship:
            if game.ship_build_error(system.id, planet.id, owner=RIVAL) is None:
                game.queue_ship(system.id, planet.id, owner=RIVAL)
                fleet_size += 1
                game.rival_event(f"Started a colony ship on {planet.name}.")
        elif planet.free_slots > 0:
            item = development_choice(planet, game.opponent.race_id)
            if game.build_error(system.id, planet.id, item, owner=RIVAL) is None:
                game.queue_building(system.id, planet.id, item, owner=RIVAL)
                game.rival_event(f"Started {PROJECTS[item].name} on {planet.name}.")
