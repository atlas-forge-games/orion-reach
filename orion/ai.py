"""Deterministic expansion AI. All orders use the same rules as player orders."""

from .model import RIVAL, RICHNESSES
from .production import PROJECTS, travel_turns
from .races import RACES


def available_worlds(system):
    return [p for p in system.worlds if not p.colonized and p.habitability > 0]


def world_quality(planet):
    return planet.habitability, planet.building_capacity, RICHNESSES.index(planet.richness), -planet.id


def development_choice(planet, race_id="kharuun"):
    for item in RACES[race_id].development:
        if item not in planet.buildings:
            return item
    # Keep adding a mix of industry, income and research on larger worlds.
    return ("factory", "trade_center", "research_lab")[(len(planet.buildings)-4) % 3]


def run_ai(game):
    """Place orders before this turn's shared travel, production and income phase."""
    for ship in sorted(game.ships_owned_by(RIVAL), key=lambda s: s.id):
        if ship.in_transit:
            continue
        local = available_worlds(game.systems[ship.system_id])
        if local:
            planet = max(local, key=world_quality)
            game.colonize(ship.id, ship.system_id, planet.id, owner=RIVAL)
            game.rival_event(f"Settled {planet.name} with 1 B colonists.")
            continue
        incoming = {}
        for other in game.ships_owned_by(RIVAL):
            if other.in_transit:
                incoming[other.destination] = incoming.get(other.destination, 0)+1
        targets = [s for s in game.systems if len(available_worlds(s)) > incoming.get(s.id, 0)]
        if not targets:
            continue
        origin = game.systems[ship.system_id]
        target = min(targets, key=lambda s: (
            travel_turns(origin, s),
            tuple(-value for value in world_quality(max(available_worlds(s), key=world_quality))), s.id))
        duration = game.send_ship(ship.id, target.id, owner=RIVAL)
        game.rival_event(f"Sent {ship.name} to {target.name}; {duration} turns in transit.")

    colonies = [(s, p) for s in game.systems for p in s.worlds if p.owner == RIVAL]
    colonies.sort(key=lambda row: (-row[1].industry_per_turn, -row[1].population, row[0].id, row[1].id))
    unclaimed = sum(len(available_worlds(s)) for s in game.systems)
    fleet_size = len(game.ships_owned_by(RIVAL)) + sum(
        project.item_id == "colony_ship" for _, p in colonies for project in p.construction_queue)
    fleet_limit = min(unclaimed, 3, 1+len(colonies)//2)
    for index, (system, planet) in enumerate(colonies):
        if planet.construction_queue:
            continue
        # The strongest colony supplies ships. Other worlds build their economies.
        # Expansion raises the shipyard's development target, preventing stagnation.
        target_buildings = min(planet.building_capacity, 2+len(colonies)//2)
        produce_ship = index == 0 and fleet_size < fleet_limit and len(planet.buildings) >= target_buildings
        if produce_ship:
            if game.ship_build_error(system.id, planet.id, owner=RIVAL) is None:
                game.queue_ship(system.id, planet.id, owner=RIVAL)
                fleet_size += 1
                game.rival_event(f"Started a colony ship on {planet.name}.")
        elif planet.free_slots > 0:
            item = development_choice(planet, game.opponent.race_id)
            if game.build_error(system.id, planet.id, item, owner=RIVAL) is None:
                game.queue_building(system.id, planet.id, item, owner=RIVAL)
                game.rival_event(f"Started {PROJECTS[item].name} on {planet.name}.")
