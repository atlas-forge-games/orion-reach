"""Deterministic expansion AI. All orders use the same rules as player orders."""

from .model import RIVAL, RICHNESSES
from .production import PROJECTS, TROOP_STRENGTH
from .races import RACES
from .research import BRANCHES, choices
from .combat import HOSTILE_BELOW
from .victory import colonies as empire_colonies, gate_site, invasion_strength, troop_transports


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
    if game.research_error("ascension_theory", owner=RIVAL) is None:
        game.choose_research("ascension_theory", owner=RIVAL)


def world_quality(planet):
    return planet.habitability, planet.building_capacity, RICHNESSES.index(planet.richness), -planet.id


def development_choice(planet, race_id="kharuun"):
    for item in RACES[race_id].development:
        if item not in planet.buildings:
            return item
    # Keep adding a mix of industry, income and research on larger worlds.
    return ("factory", "trade_center", "research_lab")[(len(planet.buildings)-4) % 3]


def military_orders(game):
    """Assemble escorted invasion groups when hostile; otherwise guard colonies."""
    ships = sorted((s for s in game.ships_owned_by(RIVAL) if s.kind == "frigate"), key=lambda s: s.id)
    colonies = [s for s in game.systems if any(p.owner == RIVAL for p in s.worlds)]
    colonies.sort(key=lambda s: (s.id != game.opponent.home_system, s.id))
    if not colonies:
        return
    hostile = game.diplomacy.relations < HOSTILE_BELOW
    targets = [s for s in game.systems if game.fleet_at(s.id)] if hostile else []
    worlds = empire_colonies(game, "player") if hostile else []
    ordered = set()
    staging, _ = max(empire_colonies(game, RIVAL), key=lambda row: (game.planet_yields(row[1])[0], row[1].population, -row[0].id, -row[1].id))
    for system in game.systems:
        troops = troop_transports(game, system.id, RIVAL)
        escorts = [s for s in ships if not s.in_transit and s.system_id == system.id]
        if not troops or game.fleet_at(system.id):
            continue
        candidates = [(s, p) for s, p in worlds if len(troops)*TROOP_STRENGTH > 4+p.population]
        if candidates and escorts:
            destination, _ = min(candidates, key=lambda row: (
                not row[1].ascension_gate, game.travel_turns(system, row[0], RIVAL), row[1].population, row[0].id, row[1].id))
            for ship in troops+escorts:
                ordered.add(ship.id)
                if ship.system_id != destination.id:
                    game.send_ship(ship.id, destination.id, owner=RIVAL)
            game.rival_event(f"Sent an invasion group toward {destination.name}.")
        elif system.id != staging.id:
            for ship in troops:
                game.send_ship(ship.id, staging.id, owner=RIVAL)
    gate = gate_site(game, RIVAL)
    for index, ship in enumerate(ships):
        if ship.id in ordered or ship.in_transit or game.fleet_at(ship.system_id):
            continue
        if ship.hull < ship.max_hull and game.can_repair(ship):
            continue
        origin = game.systems[ship.system_id]
        if gate and index == 0:
            destination = gate[0]
        elif hostile and worlds:
            # Keep escorts with newly built transports until the group is ready.
            destination = staging
            if not troop_transports(game, staging.id, RIVAL) and targets:
                destination = min(targets, key=lambda s: (game.travel_turns(origin, s, RIVAL), s.id))
        else:
            destination = colonies[index % len(colonies)]
        if destination.id != ship.system_id:
            game.send_ship(ship.id, destination.id, owner=RIVAL)
            game.rival_event(f"Sent {ship.name} to guard {destination.name}." if not hostile else
                             f"Sent {ship.name} toward opposing ships at {destination.name}.")


def invasion_orders(game):
    messages = []
    if game.diplomacy.relations >= HOSTILE_BELOW:
        return messages
    for system in game.systems:
        candidates = [p for p in system.worlds if game.invasion_error(system.id, p.id, owner=RIVAL) is None
                      and invasion_strength(game, system.id, p.id, RIVAL)[0] > 4+p.population]
        if not candidates:
            continue
        planet = min(candidates, key=lambda p: (not p.ascension_gate, p.population, p.id))
        game.invade(system.id, planet.id, owner=RIVAL)
        messages.append(f"Rival captured {planet.name}")
        if game.result is not None:
            break
    return messages


def run_ai(game):
    """Place orders before this turn's shared travel, production and income phase."""
    invasions = invasion_orders(game)
    if game.result is not None:
        return invasions
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
    if "ascension_theory" in game.opponent.technology.completed and not gate_site(game, RIVAL):
        for system, planet in colonies:
            if game.gate_error(system.id, planet.id, owner=RIVAL) is None:
                game.queue_gate(system.id, planet.id, owner=RIVAL)
                game.rival_event(f"Started the Ascension Gate on {planet.name}.")
                invasions.append(f"Rival started an Ascension Gate on {planet.name}")
                break
        # Save credits for the gate before placing further construction orders.
        if not gate_site(game, RIVAL):
            return invasions
    unclaimed = sum(len(available_worlds(game, s)) for s in game.systems)
    fleet_size = sum(s.kind == "colony_ship" for s in game.ships_owned_by(RIVAL)) + sum(
        project.item_id == "colony_ship" for _, p in colonies for project in p.construction_queue)
    warships = sum(s.kind == "frigate" for s in game.ships_owned_by(RIVAL)) + sum(
        project.item_id == "frigate" for _, p in colonies for project in p.construction_queue)
    military_limit = min(3, max(1, len(colonies)//2))
    transports = sum(s.kind == "troop_transport" for s in game.ships_owned_by(RIVAL)) + sum(
        project.item_id == "troop_transport" for _, p in colonies for project in p.construction_queue)
    troop_limit = max(((4+p.population)//TROOP_STRENGTH+1 for _, p in empire_colonies(game, "player")), default=0)
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
        produce_transport = (index == 0 and game.diplomacy.relations < HOSTILE_BELOW
                             and warships > 0 and transports < troop_limit)
        if produce_frigate:
            if game.ship_build_error(system.id, planet.id, "frigate", owner=RIVAL) is None:
                game.queue_ship(system.id, planet.id, "frigate", owner=RIVAL)
                warships += 1
                game.rival_event(f"Started a frigate on {planet.name}.")
        elif produce_transport:
            if game.ship_build_error(system.id, planet.id, "troop_transport", owner=RIVAL) is None:
                game.queue_ship(system.id, planet.id, "troop_transport", owner=RIVAL)
                transports += 1
                game.rival_event(f"Started a troop transport on {planet.name}.")
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
    return invasions
