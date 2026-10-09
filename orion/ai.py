"""Deterministic expansion AI. All orders use the same rules as player orders."""

from .model import RIVAL, RICHNESSES
from .production import PROJECTS, TROOP_STRENGTH
from .races import RACES
from .research import BRANCHES, choices
from .combat import HOSTILE_BELOW
from .exploration import gate_location
from .population import farmers_needed, food_required
from . import monsters
from . import raiding
from .ground_combat import forces, resolve, transports_needed
from .victory import colonies as empire_colonies, gate_site, invasion_strength, troop_transports


def event(game, owner, message, **kwargs):
    game.rival_event(message, owner=owner, **kwargs)


def available_worlds(game, system, owner=RIVAL):
    if monsters.known_status(game, system.id, owner) == "alive":
        return []
    known = game.known_system(system.id, owner)
    return [p for p in known.worlds if not p.colonized and game.can_settle(p, owner)] if known else []


def known_enemy_colonies(game, owner=RIVAL):
    return [(known, p) for s in game.systems if (known := game.known_system(s.id, owner)) is not None
            for p in known.worlds if p.owner is not None and p.owner != owner]


def enemies(game, owner):
    if raiding.is_varkesh(game, owner):
        return {other for other in game.owners if other != owner and game.colony_systems(other)
                and not game.diplomacy_between(owner, other).trade_active
                and not game.diplomacy_between(owner, other).research_active}
    return {other for other in game.owners if other != owner
            and game.diplomacy_between(owner, other).relations < HOSTILE_BELOW}


def scouting_orders(game, owner=RIVAL):
    if not game.fog_of_war:
        return
    incoming = {s.destination for s in game.ships_owned_by(owner) if s.has_course and s.kind == "scout"}
    for ship in sorted(game.ships_owned_by(owner), key=lambda s: s.id):
        if ship.kind != "scout" or ship.has_course:
            continue
        candidates = [s for s in game.systems if s.id != ship.system_id and s.id not in incoming
                      and monsters.known_status(game, s.id, owner) != "alive"
                      and s.id not in game.exploration.scanned(owner) and game.within_fuel_range(s.id, owner)]
        if not candidates:
            continue
        origin = game.systems[ship.system_id]
        target = min(candidates, key=lambda s: (game.system_explored(s.id, owner),
                                                game.travel_turns(origin, s, owner), s.id))
        game.send_ship(ship.id, target.id, owner=owner)
        incoming.add(target.id)
        event(game, owner, f"Sent {ship.name} to explore {target.name}.")


def research_choice(game, owner=RIVAL):
    """A stable preference order, using ordinary points and exclusive choices."""
    state = game.research_state(owner)
    if state.active or game._empire(owner).research == 0:
        return
    # Extend an exhausted frontier using the same exclusive tank upgrades as the player.
    unknown = [s for s in game.systems if not game.system_explored(s.id, owner)]
    raid_targets = known_enemy_colonies(game, owner) if raiding.is_varkesh(game, owner) else []
    if ((unknown and not any(game.within_fuel_range(s.id, owner) for s in unknown))
            or (raid_targets and not any(game.within_fuel_range(s.id, owner) for s, _ in raid_targets))):
        for identifier in ("lightweight_alloys", "composite_structures"):
            if game.research_error(identifier, owner=owner) is None:
                game.choose_research(identifier, owner=owner)
                return
    race = game._empire(owner).race_id
    priority = RACES[race].research_priority
    branches = priority + tuple(b for b in BRANCHES if b not in priority)
    # Each tuple follows catalogue branch order, with one option per tier.
    preferences = {
        "terran": ((1, 0, 1, 0, 0, 0, 0, 0), (0, 0, 0, 0, 0, 1, 1, 1)),
        "kharuun": ((0, 0, 0, 0, 0, 1, 1, 0), (1, 0, 1, 0, 1, 0, 1, 0)),
        "aelari": ((1, 1, 0, 0, 0, 0, 0, 1), (0, 0, 1, 0, 0, 1, 0, 1)),
    }.get(race, ((1, 0, 1, 0, 0, 0, 0, 0), (0, 0, 0, 0, 0, 1, 1, 1)))
    for tier in (1, 2):
        for branch in branches:
            index = tuple(BRANCHES).index(branch)
            technology = choices(branch, tier)[preferences[tier-1][index]]
            if game.research_error(technology.id, owner=owner) is None:
                game.choose_research(technology.id, owner=owner)
                return
    if game.research_error("ascension_theory", owner=owner) is None:
        game.choose_research("ascension_theory", owner=owner)


def world_quality(planet):
    return planet.habitability, planet.building_capacity, RICHNESSES.index(planet.richness), -planet.id


def development_choice(planet, race_id="kharuun"):
    for item in RACES[race_id].development:
        if item not in planet.buildings:
            return item
    # Keep adding a mix of industry, income and research on larger worlds.
    return ("factory", "trade_center", "research_lab")[(len(planet.buildings)-4) % 3]


def announce_raid(game, owner, defender, system):
    """A committed raid is hostile, so orbiting defenders can intercept it."""
    state = game.diplomacy_between(owner, defender)
    if state.relations >= HOSTILE_BELOW:
        state.relations = -100
        state.offer_ready_turn = game.turn+3
        state.record(game.turn, f"{game.empire_name_for(owner)} sent a raid against {system.name}. Relations are now -100.")


def military_orders(game, reserved=(), owner=RIVAL):
    """Assemble escorted invasion groups when hostile; otherwise guard colonies."""
    ships = sorted((s for s in game.ships_owned_by(owner) if s.kind == "frigate" and s.id not in reserved), key=lambda s: s.id)
    colonies = [s for s in game.systems if any(p.owner == owner for p in s.worlds)]
    colonies.sort(key=lambda s: (s.id != game._empire(owner).home_system, s.id))
    if not colonies:
        return
    hostile = enemies(game, owner)
    targets = [s for s in game.systems if game.system_visible(s.id, owner)
               and any(ship.owner in hostile for ship in game.foreign_fleet(s.id, owner))
               and game.within_fuel_range(s.id, owner)] if hostile else []
    worlds = [(s, p) for s, p in known_enemy_colonies(game, owner)
              if p.owner in hostile and game.within_fuel_range(s.id, owner)]
    ordered = set()
    staging, _ = max(empire_colonies(game, owner), key=lambda row: (game.planet_yields(row[1])[0], row[1].population, -row[0].id, -row[1].id))
    for system in game.systems:
        troops = [s for s in troop_transports(game, system.id, owner) if not s.has_course]
        escorts = [s for s in ships if not s.has_course and s.system_id == system.id]
        if not troops:
            continue
        candidates = [(s, p) for s, p in worlds if resolve(len(troops)*TROOP_STRENGTH, forces(p)).captured]
        if game.foreign_fleet(system.id, owner):
            if raiding.is_varkesh(game, owner) and escorts:
                for destination, planet in candidates:
                    if destination.id == system.id:
                        announce_raid(game, owner, planet.owner, destination)
            continue
        if candidates and escorts:
            if raiding.is_varkesh(game, owner):
                destination, planet = min(candidates, key=lambda row: (game.travel_turns(system, row[0], owner),
                                                                      -row[1].workforce, row[0].id, row[1].id))
                announce_raid(game, owner, planet.owner, destination)
            else:
                destination, _ = min(candidates, key=lambda row: (
                    not row[1].ascension_gate, game.travel_turns(system, row[0], owner), row[1].population, row[0].id, row[1].id))
            for ship in troops+escorts:
                ordered.add(ship.id)
                if ship.system_id != destination.id:
                    game.send_ship(ship.id, destination.id, owner=owner)
            action = "raiding" if raiding.is_varkesh(game, owner) else "invasion"
            event(game, owner, f"Sent a {action} group toward {destination.name}.")
        elif system.id != staging.id:
            for ship in troops:
                game.send_ship(ship.id, staging.id, owner=owner)
    gate = gate_site(game, owner)
    for index, ship in enumerate(ships):
        if ship.id in ordered or ship.has_course or game.foreign_fleet(ship.system_id, owner):
            continue
        if ship.hull < ship.max_hull and game.can_repair(ship):
            continue
        origin = game.systems[ship.system_id]
        if gate and index == 0:
            destination = gate[0]
        elif hostile and worlds:
            # Keep escorts with newly built transports until the group is ready.
            destination = staging
            if not troop_transports(game, staging.id, owner) and targets:
                destination = min(targets, key=lambda s: (game.travel_turns(origin, s, owner), s.id))
        else:
            destination = colonies[index % len(colonies)]
        if destination.id != ship.system_id:
            game.send_ship(ship.id, destination.id, owner=owner)
            event(game, owner, f"Sent {ship.name} to guard {destination.name}." if not hostile else
                             f"Sent {ship.name} toward opposing ships at {destination.name}.")


def invasion_orders(game, owner=RIVAL, *, ground_reports=None):
    messages = []
    hostile = enemies(game, owner)
    if not hostile:
        return messages
    for system in game.systems:
        if not game.system_visible(system.id, owner):
            continue
        candidates = [p for p in system.worlds if p.owner in hostile and game.invasion_error(system.id, p.id, owner=owner) is None
                      and resolve(invasion_strength(game, system.id, p.id, owner)[0], forces(p)).captured]
        if not candidates:
            continue
        planet = (max(candidates, key=lambda p: (p.workforce, -p.id)) if raiding.is_varkesh(game, owner) else
                  min(candidates, key=lambda p: (not p.ascension_gate, p.population, p.id)))
        report = game.invade(system.id, planet.id, owner=owner)
        if ground_reports is not None and "player" in (report.attacker, report.defender):
            ground_reports.append(report)
        if "player" in (report.attacker, report.defender) or game.system_visible(system.id):
            if report.cause == "raid":
                messages.append(f"{game.empire_name_for(owner)} raided {planet.name}: {report.slaves_taken} slaves, {report.credits_stolen} CR")
            else:
                messages.append(f"{game.empire_name_for(owner)} captured {planet.name}")
        if game.result is not None:
            break
    return messages


def run_ai(game, owner=RIVAL, *, ground_reports=None):
    """Place orders before this turn's shared travel, production and income phase."""
    invasions = invasion_orders(game, owner, ground_reports=ground_reports)
    if game.result is not None:
        return invasions
    research_choice(game, owner)
    scouting_orders(game, owner)
    military_orders(game, monsters.ai_orders(game, owner), owner)
    for ship in sorted(game.ships_owned_by(owner), key=lambda s: s.id):
        if ship.has_course or ship.kind != "colony_ship" or raiding.is_varkesh(game, owner):
            continue
        local = available_worlds(game, game.systems[ship.system_id], owner)
        if local:
            planet = max(local, key=world_quality)
            game.colonize(ship.id, ship.system_id, planet.id, owner=owner)
            event(game, owner, f"Settled {planet.name} with {planet.population} B colonists.")
            continue
        incoming = {}
        for other in game.ships_owned_by(owner):
            if other.has_course and other.kind == "colony_ship":
                incoming[other.destination] = incoming.get(other.destination, 0)+1
        targets = [s for s in game.systems if game.within_fuel_range(s.id, owner)
                   and len(available_worlds(game, s, owner)) > incoming.get(s.id, 0)]
        if not targets:
            unknown = [s for s in game.systems if not game.system_explored(s.id, owner) and not incoming.get(s.id)
                       and monsters.known_status(game, s.id, owner) != "alive"
                       and game.within_fuel_range(s.id, owner)]
            if unknown:
                target = min(unknown, key=lambda s: (game.travel_turns(game.systems[ship.system_id], s, owner), s.id))
                game.send_ship(ship.id, target.id, owner=owner)
            continue
        origin = game.systems[ship.system_id]
        target = min(targets, key=lambda s: (
            game.travel_turns(origin, s, owner),
            tuple(-value for value in world_quality(max(available_worlds(game, s, owner), key=world_quality))), s.id))
        duration = game.send_ship(ship.id, target.id, owner=owner)
        event(game, owner, f"Sent {ship.name} to {target.name}; {duration} turns in transit.")

    colonies = [(s, p) for s in game.systems for p in s.worlds if p.owner == owner]
    for system, planet in colonies:
        farmers = farmers_needed(planet, game.bonuses_for(owner))
        remaining = planet.workforce-farmers
        scientists = min(2, remaining//4) if "research_lab" in planet.buildings else 0
        game.set_workforce(system.id, planet.id, farmers, scientists, owner=owner)
    colonies.sort(key=lambda row: (-game.planet_yields(row[1])[0], -row[1].population, row[0].id, row[1].id))
    if "ascension_theory" in game._empire(owner).technology.completed and not gate_site(game, owner):
        for system, planet in colonies:
            if game.gate_error(system.id, planet.id, owner=owner) is None:
                game.queue_gate(system.id, planet.id, owner=owner)
                event(game, owner, f"Started the Ascension Gate on {planet.name}.")
                invasions.append(f"Rival started an Ascension Gate at {gate_location(game, system.id, planet)}")
                break
        # Save credits for the gate before placing further construction orders.
        if not gate_site(game, owner):
            return invasions
    unclaimed = sum(len(available_worlds(game, s, owner)) for s in game.systems)
    fleet_size = sum(s.kind == "colony_ship" for s in game.ships_owned_by(owner)) + sum(
        project.item_id == "colony_ship" for _, p in colonies for project in p.construction_queue)
    warships = sum(s.kind == "frigate" for s in game.ships_owned_by(owner)) + sum(
        project.item_id == "frigate" for _, p in colonies for project in p.construction_queue)
    military_limit = min(3, max(1, len(colonies)//2))
    guarded = [g for g in game.guardians if monsters.known_status(game, g.system_id, owner) == "alive"
               and game.within_fuel_range(g.system_id, owner)]
    if guarded:
        # Reserve enough hull for the strongest known guardian (up to 9 frigates).
        military_limit = max(military_limit, max((g.spec.hull*5+79)//80 for g in guarded))
    transports = sum(s.kind == "troop_transport" for s in game.ships_owned_by(owner)) + sum(
        project.item_id == "troop_transport" for _, p in colonies for project in p.construction_queue)
    hostile = enemies(game, owner)
    troop_limit = max((transports_needed(p, TROOP_STRENGTH) for s, p in known_enemy_colonies(game, owner)
                       if p.owner in hostile and game.within_fuel_range(s.id, owner)), default=0)
    unknown = sum(not game.system_explored(s.id, owner) for s in game.systems)
    fleet_limit = min(unclaimed+bool(unknown), 3, 1+len(colonies)//2)
    if raiding.is_varkesh(game, owner):
        fleet_limit = 0
    scouts = sum(s.kind == "scout" for s in game.ships_owned_by(owner)) + sum(
        q.item_id == "scout" for _, p in colonies for q in p.construction_queue)
    for index, (system, planet) in enumerate(colonies):
        if planet.construction_queue:
            continue
        food = game.population_report(planet)
        farm_food = PROJECTS["hydroponic_farm"].food
        full_consumption = food_required(food.capacity+planet.slaves, game.bonuses_for(owner))
        farms_needed = max(0, (full_consumption-food.produced+farm_food-1)//farm_food)
        needs_food = food.consumed > 0 and (food.produced < min(full_consumption, food.consumed+2)
                      or planet.farmers > 2
                      or 0 < planet.free_slots <= farms_needed)
        if needs_food and planet.free_slots > 0:
            if game.build_error(system.id, planet.id, "hydroponic_farm", owner=owner) is None:
                game.queue_building(system.id, planet.id, "hydroponic_farm", owner=owner)
                event(game, owner, f"Started a hydroponic farm on {planet.name}.")
            continue
        # Reserve local defence before peaceful development fills every slot.
        # The main shipyard needs barracks to recruit expeditionary troops.
        military_building = None
        if "barracks" not in planet.buildings and (hostile or len(planet.buildings) >= 2):
            military_building = "barracks"
        elif hostile and "fortifications" not in planet.buildings and "barracks" in planet.buildings:
            military_building = "fortifications"
        if (military_building == "barracks" and index == 0 and hostile and transports < troop_limit
                and planet.free_slots == 0
                and game.treasury_for(owner) >= game.project_price("barracks", owner)):
            # Older, fully developed colonies need room for the new troop facility.
            # Preserve farms and the last research lab; prefer redundant industry.
            replaceable = [i for i, b in enumerate(planet.buildings) if b in ("factory", "mine", "trade_center")]
            if replaceable:
                slot = max(replaceable, key=lambda i: (planet.buildings.count(planet.buildings[i]), i))
                game.demolish_building(system.id, planet.id, slot, owner=owner)
        if military_building and planet.free_slots > 0:
            if game.build_error(system.id, planet.id, military_building, owner=owner) is None:
                game.queue_building(system.id, planet.id, military_building, owner=owner)
                event(game, owner, f"Started {PROJECTS[military_building].name} on {planet.name}.")
            continue
        # The strongest colony supplies ships. Other worlds build their economies.
        # Expansion raises the shipyard's development target, preventing stagnation.
        target_buildings = min(planet.building_capacity, 2+len(colonies)//2)
        produce_ship = index == 0 and fleet_size < fleet_limit and len(planet.buildings) >= target_buildings
        produce_frigate = (index == 0 and game.turn >= 12 and len(planet.buildings) >= 2
                          and warships < military_limit)
        produce_transport = (index == 0 and bool(enemies(game, owner))
                             and warships > 0 and transports < troop_limit)
        produce_scout = (game.fog_of_war and index == 0 and len(game.exploration.scanned(owner)) < len(game.systems)
                         and scouts < min(2, 1+len(colonies)//3))
        if produce_scout:
            if game.ship_build_error(system.id, planet.id, "scout", owner=owner) is None:
                game.queue_ship(system.id, planet.id, "scout", owner=owner)
                scouts += 1
                event(game, owner, f"Queued a scout on {planet.name}.")
        elif produce_frigate:
            if game.ship_build_error(system.id, planet.id, "frigate", owner=owner) is None:
                game.queue_ship(system.id, planet.id, "frigate", owner=owner)
                warships += 1
                event(game, owner, f"Started a frigate on {planet.name}.")
        elif produce_transport:
            if game.ship_build_error(system.id, planet.id, "troop_transport", owner=owner) is None:
                game.queue_ship(system.id, planet.id, "troop_transport", owner=owner)
                transports += 1
                event(game, owner, f"Started a troop transport on {planet.name}.")
        elif produce_ship:
            if game.ship_build_error(system.id, planet.id, owner=owner) is None:
                game.queue_ship(system.id, planet.id, owner=owner)
                fleet_size += 1
                event(game, owner, f"Started a colony ship on {planet.name}.")
        elif planet.free_slots > 0:
            item = development_choice(planet, game._empire(owner).race_id)
            if game.build_error(system.id, planet.id, item, owner=owner) is None:
                game.queue_building(system.id, planet.id, item, owner=owner)
                event(game, owner, f"Started {PROJECTS[item].name} on {planet.name}.")
    return invasions
