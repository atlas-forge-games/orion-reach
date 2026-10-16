"""Deterministic expansion AI. All orders use the same rules as player orders."""

from dataclasses import replace

from .buildings import BUILDINGS, FACILITY_FAMILIES, ADVANCED_FACILITIES, facility_family
from .economy import energy_report
from .model import RIVAL, RICHNESSES
from .production import PROJECTS, SHIP_TYPES
from . import production as production_balance
from .races import RACES
from .research import BRANCHES, TIERS, FUEL_TANK_TECHNOLOGIES, choices
from .combat import HOSTILE_BELOW
from .exploration import gate_location
from .population import farmers_needed, food_required
from . import monsters, defenses, sensors, black_holes, outposts, administration
from . import raiding
from . import first_contact
from . import coalitions, tribute
from .personalities import personality
from .ground_combat import forces, resolve, transports_needed
from .victory import colonies as empire_colonies, gate_site, invasion_strength, troop_transports


def event(game, owner, message, **kwargs):
    game.rival_event(message, owner=owner, **kwargs)


def available_worlds(game, system, owner=RIVAL):
    if monsters.known_status(game, system.id, owner) == "alive":
        return []
    known = game.known_system(system.id, owner)
    return [p for p in known.worlds if not p.colonized and p.outpost_owner in (None, owner) and game.can_settle(p, owner)] if known else []


def known_enemy_colonies(game, owner=RIVAL):
    worlds = [(known, p) for s in game.systems if (known := game.known_system(s.id, owner)) is not None
              for p in known.worlds if p.owner is not None and p.owner != owner]
    worlds.extend((game.systems[s.system_id], s.habitat) for s in game.visible_ships(owner)
                  if s.habitat and s.owner != owner and not s.in_transit)
    return worlds


def enemies(game, owner):
    if raiding.is_varkesh(game, owner):
        return {other for other in game.owners if other != owner and game.colony_systems(other)
                and not game.diplomacy_between(owner, other).trade_active
                and not game.diplomacy_between(owner, other).research_active
                and not game.diplomacy_between(owner, other).coalition_target
                and not game.diplomacy_between(owner, other).non_aggression_active}
    return {other for other in game.owners if other != owner
            and game.diplomacy_between(owner, other).relations < HOSTILE_BELOW
            and not game.diplomacy_between(owner, other).coalition_target
            and not game.diplomacy_between(owner, other).non_aggression_active}


def diplomatic_orders(game, owner):
    """Consider one conquest using confirmed, observable intelligence only."""
    nature = personality(game, owner)
    if not nature.conquest_ratio or game.turn < 12 or game.turn % 6 or enemies(game, owner):
        return []
    armed = [s for s in game.ships_owned_by(owner) if game.military_strength(s) > 0]
    if len(armed) < 2:
        return []
    strength = sum(s.hull for s in armed)
    candidates = []
    for system, world in known_enemy_colonies(game, owner):
        target = world.owner
        state = game.diplomacy_between(owner, target)
        if (not first_contact.known(game, owner, target) or state.trade_active or state.research_active
                or state.non_aggression_active or state.coalition_target
                or not game.within_fuel_range(system.id, owner)
                or state.relations >= (25 if game._empire(owner).race_id == "concord" else 0)):
            continue
        # An unobserved navy is uncertain; never query its hidden strength.
        observed = sum(s.hull for s in game.visible_ships(owner) if s.owner == target and game.military_strength(s) > 0)
        resistance = max(40, observed+40*sum("missile_base" in p.buildings for p in system.worlds if p.owner == target))
        if strength*100 >= resistance*nature.conquest_ratio:
            candidates.append((resistance, system.id, target))
    if not candidates:
        return []
    _, _, target = min(candidates)
    state = game.diplomacy_between(owner, target)
    from .diplomacy import start_war
    start_war(game, owner, target)
    goal = "announced an assimilation campaign against" if game._empire(owner).race_id == "concord" else "declared war on"
    message = f"{game.empire_name_for(owner)} {goal} {game.empire_name_for(target)}."
    state.record(game.turn, message)
    event(game, owner, message)
    return [message] if target == "player" else []


def scouting_orders(game, owner=RIVAL):
    if not game.fog_of_war:
        return
    incoming = {s.destination for s in game.ships_owned_by(owner) if s.has_course and s.kind == "scout"}
    for ship in sorted(game.ships_owned_by(owner), key=lambda s: s.id):
        if ship.kind != "scout" or ship.has_course:
            continue
        candidates = [s for s in game.systems if s.kind != black_holes.KIND and s.id != ship.system_id and s.id not in incoming
                      and monsters.known_status(game, s.id, owner) != "alive"
                      and s.id not in game.exploration.scanned(owner) and game.can_reach(s.id, owner, ships=[ship])]
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
    unknown = [s for s in game.systems if s.kind != black_holes.KIND and not game.system_explored(s.id, owner)]
    raid_targets = known_enemy_colonies(game, owner) if raiding.is_varkesh(game, owner) else []
    if ((unknown and not any(game.within_fuel_range(s.id, owner) for s in unknown))
            or (raid_targets and not any(game.within_fuel_range(s.id, owner) for s, _ in raid_targets))):
        for identifier in FUEL_TANK_TECHNOLOGIES:
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
    military = race in ("kharuun", "varkesh", "remnant")
    preferred = {
        "gravitic_mapping", "event_horizon_navigation",
        "destroyer_hulls", "cruiser_hulls", "titan_hulls",
        "battleship_hulls" if military else "drone_carriers",
        "orbital_defense_systems", "fusion_power", "jump_gates", "planetary_shielding",
        "barrier_fields" if military else "subspace_interdiction",
        "precision_beam_optics" if military else "electronic_countermeasures",
        "siege_weapons" if military else "torpedo_guidance",
        "plasma_beams" if military else "pulse_beams",
        "graviton_beams" if military else "ion_beams",
        "heavy_beam_mounts" if military else "particle_beams",
        "disruptor_beams" if military else "phased_beams",
        "fusion_torpedoes" if military else "reinforced_armor",
        "antimatter_torpedoes" if military else "mirv_torpedoes",
        "hardened_shields" if military else "regenerative_shields",
        "interceptor_drones" if state.hull_unlocked("carrier") and not military else "advanced_flak",
        "bomber_drones" if state.hull_unlocked("carrier") and not military else "automated_damage_control",
        *( ("targeting_computers", "predictive_fire_control", "quantum_targeting") if military
           else ("deep_space_radar", "long_range_sensors", "subspace_scanners") ),
    }
    for tier in TIERS:
        for branch in branches:
            options = choices(branch, tier)
            if ("science" in game.victory_conditions and "ascension_theory" not in state.completed
                    and tier not in state.required_tiers(branch)):
                continue
            if tier <= 2 and branch != "starships":
                index = tuple(BRANCHES).index(branch)
                options = sorted(options, key=lambda t: t != options[preferences[tier-1][index]])
            else:
                options = sorted(options, key=lambda t: t.id not in preferred)
            for technology in options:
                if game.research_error(technology.id, owner=owner) is None:
                    game.choose_research(technology.id, owner=owner)
                    return
    if game.research_error("ascension_theory", owner=owner) is None:
        game.choose_research("ascension_theory", owner=owner)


def warship_choice(game, owner):
    """Build researched hulls when affordable, keeping carriers in a mixed fleet."""
    state = game.research_state(owner)
    available = [kind for kind, spec in SHIP_TYPES.items() if kind != "mothership" and (spec.damage or spec.drone_bays)
                 and state.hull_unlocked(kind) and game.project_price(kind, owner) <= game.resources_for(owner)]
    if "carrier" in available:
        fleet = [s for s in game.ships_owned_by(owner) if game.military_strength(s)]
        if sum(s.drone_bays > 0 for s in fleet)*3 <= len(fleet):
            return "carrier"
    return max(available, key=lambda kind: game.project_spec(kind, owner).hull+3*game.project_spec(kind, owner).damage,
               default="frigate")


def world_quality(planet):
    return planet.habitability, planet.building_capacity, RICHNESSES.index(planet.richness), -planet.id


def development_choice(planet, race_id="kharuun", available=None):
    existing = set(planet.buildings) | {q.item_id for q in planet.construction_queue}
    for item in (*RACES[race_id].development, "factory", "trade_center", "research_lab", "mine"):
        candidates = reversed(FACILITY_FAMILIES.get(item, (item,))) if available is not None else (item,)
        for candidate in candidates:
            if candidate not in existing and (available is None or candidate in available):
                return candidate
    return None


def projected_colony(planet, extra=None):
    """A copy with all queued buildings, plus an optional proposed order, complete."""
    buildings = planet.buildings+[q.item_id for q in planet.construction_queue if q.item_id in BUILDINGS]
    if extra is not None:
        buildings = buildings+[extra]
    return replace(planet, buildings=buildings,
                   ascension_gate=planet.ascension_gate or any(q.item_id == "ascension_gate" for q in planet.construction_queue))


def projected_income(game, owner, extra=None):
    """Budget for all queued building orders as well as the proposed next one."""
    income = game.diplomatic_yields(owner)[0]
    for system, planet in empire_colonies(game, owner):
        item = extra[2] if extra and extra[:2] == (system.id, planet.id) else None
        income += game.planet_yields(projected_colony(planet, item))[1]
    return income


def steady_power_plant(game, planet, owner):
    """Choose the largest unlocked steady source the colony can maintain."""
    existing = set(planet.buildings) | {q.item_id for q in planet.construction_queue}
    candidates = [b for b in BUILDINGS.values() if b.energy_output and not b.energy_per_resource
                  and b.id not in existing
                  and (not b.technology or game.research_state(owner).has_unlock(b.technology))]
    income = game.planet_yields(projected_colony(planet))[1]
    affordable = [b for b in candidates if b.maintenance < income]
    fallback = [b for b in candidates if b.id == "solar_array"]
    choice = max(affordable or fallback, key=lambda b: b.energy_output, default=None)
    return choice.id if choice else None


def queue_building(game, system, planet, item, owner):
    """Cover future upkeep before committing to more expensive infrastructure."""
    if item is None or game.build_error(system.id, planet.id, item, owner=owner) is not None:
        return False
    if (game.planet_yields(projected_colony(planet, item))[1] < 0
            or projected_income(game, owner, (system.id, planet.id, item)) < 1):
        item = "trade_center"
    future = projected_colony(planet, item)
    if energy_report(future, game.bonuses_for(owner)).balance < 0 and not BUILDINGS[item].energy_output:
        item = steady_power_plant(game, planet, owner)
    if item is None or game.build_error(system.id, planet.id, item, owner=owner) is not None:
        return False
    game.queue_building(system.id, planet.id, item, owner=owner)
    event(game, owner, f"Started {PROJECTS[item].name} on {planet.name}.")
    return True


def recover_budget(game, owner):
    """Prioritize revenue, or retire unaffordable buildings while preserving food."""
    target = 1  # Retain a small surplus so a depleted treasury can recover.
    if game.empire_rates_for(owner)[0] >= target or projected_income(game, owner) >= target:
        return
    colonies = empire_colonies(game, owner)
    for system, planet in colonies:
        if game.build_error(system.id, planet.id, "trade_center", owner=owner) is None:
            queue_building(game, system, planet, "trade_center", owner)
            return
    while game.empire_rates_for(owner)[0] < target:
        options = []
        for system, planet in colonies:
            for index, item in enumerate(planet.buildings):
                future = replace(planet, buildings=planet.buildings[:index]+planet.buildings[index+1:],
                                 disabled_buildings=[i-(i > index) for i in planet.disabled_buildings if i != index])
                future.farmers = farmers_needed(future, game.bonuses_for(owner))
                future.scientists = min(future.scientists, future.workforce-future.farmers)
                future.miners = min(future.miners, future.workforce-future.farmers-future.scientists)
                if game.population_report(future).balance < 0:
                    continue
                saving = game.planet_yields(future)[1]-game.planet_yields(planet)[1]
                if saving > 0:
                    options.append((item == "hydroponic_farm", item == "barracks", facility_family(item) == "research_lab",
                                    -saving, system.id, planet.id, index, future))
        if not options:
            return
        *_, sid, pid, index, future = min(options, key=lambda row: row[:-1])
        item = game.demolish_building(sid, pid, index, owner=owner)
        game.set_workforce(sid, pid, future.farmers, future.scientists, future.miners, owner=owner)
        event(game, owner, f"Retired {PROJECTS[item].name} on {future.name} to restore the budget.")


def recover_power(game, owner):
    """Provide capacity for existing/queued loads, including full older colonies."""
    for system, planet in empire_colonies(game, owner):
        if energy_report(projected_colony(planet), game.bonuses_for(owner)).balance >= 0:
            continue
        queued = next((i for i, q in enumerate(planet.construction_queue)
                       if q.item_id in BUILDINGS and BUILDINGS[q.item_id].energy_output), None)
        if queued is not None:
            game.prioritize_construction(system.id, planet.id, queued, owner=owner)
            continue
        item = steady_power_plant(game, planet, owner)
        if item is None:
            continue
        if not planet.free_slots:
            disposable = [i for i, b in enumerate(planet.buildings) if facility_family(b) in ("research_lab", "factory", "trade_center")]
            if not disposable:
                continue
            index = max(disposable, key=lambda i: (planet.buildings.count(planet.buildings[i]), i))
            game.demolish_building(system.id, planet.id, index, owner=owner)
        if game.build_error(system.id, planet.id, item, owner=owner) is None:
            game.change_production(system.id, planet.id, item, owner=owner)
            event(game, owner, f"Restoring power on {planet.name} with {BUILDINGS[item].name}.")


def announce_raid(game, owner, defender, system):
    """A committed raid is hostile, so orbiting defenders can intercept it."""
    state = game.diplomacy_between(owner, defender)
    if state.relations >= HOSTILE_BELOW:
        from .diplomacy import start_war
        start_war(game, owner, defender)
        state.record(game.turn, f"{game.empire_name_for(owner)} sent a raid against {system.name}. Relations are now -100.")


def military_orders(game, reserved=(), owner=RIVAL):
    """Assemble escorted invasion groups when hostile; otherwise guard colonies."""
    ships = sorted((s for s in game.ships_owned_by(owner) if not s.habitat and game.military_strength(s) > 0 and s.id not in reserved), key=lambda s: s.id)
    colonies = game.colony_systems(owner)
    colonies.sort(key=lambda s: (s.id != game._empire(owner).home_system, s.id))
    if not colonies:
        return
    hostile = enemies(game, owner)
    targets = [s for s in game.systems if game.system_visible(s.id, owner)
               and any(ship.owner in hostile for ship in game.foreign_fleet(s.id, owner))] if hostile else []
    targets += [s for s in game.systems if (known := game.known_system(s.id, owner)) is not None
                and any(p.outpost_owner in hostile for p in known.worlds)]
    worlds = [(s, p) for s, p in known_enemy_colonies(game, owner)
              if p.owner in hostile]
    def target_forces(system, planet):
        defending = forces(planet, game.bonuses_for(planet.owner) if game.system_visible(system.id, owner) else {})
        if planet.habitat:
            from .boarding import DECK_DEFENCE
            defending = replace(defending, defence_bonus=defending.defence_bonus+DECK_DEFENCE)
        return defending
    ordered = set()
    staging, _ = max(empire_colonies(game, owner), key=lambda row: (game.planet_yields(row[1])[0], row[1].population, -row[0].id, -row[1].id))
    for system in game.systems:
        troops = [s for s in troop_transports(game, system.id, owner) if not s.has_course]
        escorts = [s for s in ships if not s.has_course and s.system_id == system.id]
        if not troops:
            continue
        candidates = [(s, p) for s, p in worlds if game.can_reach(s.id, owner, ships=troops+escorts)
                      and resolve(len(troops)*production_balance.TROOP_STRENGTH, target_forces(s, p)).captured]
        if game.foreign_fleet(system.id, owner):
            if raiding.is_varkesh(game, owner) and escorts:
                for destination, planet in candidates:
                    if destination.id == system.id:
                        announce_raid(game, owner, planet.owner, destination)
            continue
        if candidates and escorts:
            if raiding.is_varkesh(game, owner):
                destination, planet = min(candidates, key=lambda row: (row[1].owner not in coalitions.targets(game, owner),
                                                                      game.travel_turns(system, row[0], owner),
                                                                      -row[1].workforce, row[0].id, row[1].id))
                announce_raid(game, owner, planet.owner, destination)
            else:
                destination, _ = min(candidates, key=lambda row: (
                    row[1].owner not in coalitions.targets(game, owner), not row[1].ascension_gate,
                    game.travel_turns(system, row[0], owner), row[1].population, row[0].id, row[1].id))
            for ship in troops+escorts:
                ordered.add(ship.id)
                if ship.system_id != destination.id:
                    game.send_ship(ship.id, destination.id, owner=owner)
            action = "raiding" if raiding.is_varkesh(game, owner) else "invasion"
            event(game, owner, f"Sent a {action} group toward {destination.name}.")
        elif system.id != staging.id and game.can_reach(staging.id, owner, ships=troops):
            for ship in troops:
                game.send_ship(ship.id, staging.id, owner=owner)
    threats = [c for c in sensors.contacts(game, owner) if c.active and c.owner in hostile]
    threatened = sorted({c.near_system for c in threats
                         if sensors.distance(c.x, c.y, game.systems[c.near_system]) <= 12})
    gate = gate_site(game, owner)
    for index, ship in enumerate(ships):
        if ship.id in ordered or ship.has_course or game.foreign_fleet(ship.system_id, owner) or ship.bombarded_turn == game.turn:
            continue
        if ship.hull < ship.max_hull and game.can_repair(ship):
            continue
        origin = game.systems[ship.system_id]
        reachable_targets = [s for s in targets if game.can_reach(s.id, owner, ships=[ship])]
        reachable_worlds = [(s, p) for s, p in worlds if game.can_reach(s.id, owner, ships=[ship])]
        reachable_threats = [game.systems[sid] for sid in threatened if game.can_reach(sid, owner, ships=[ship])]
        if gate and index == 0 and game.can_reach(gate[0].id, owner, ships=[ship]):
            destination = gate[0]
        elif reachable_threats:
            destination = min(reachable_threats, key=lambda s: (game.travel_turns(origin, s, owner), s.id))
        elif hostile and reachable_worlds:
            # Keep escorts with newly built transports until the group is ready.
            destination = staging
            if not troop_transports(game, staging.id, owner) and reachable_targets:
                destination = min(reachable_targets, key=lambda s: (game.travel_turns(origin, s, owner), s.id))
        elif reachable_targets:
            destination = min(reachable_targets, key=lambda s: (game.travel_turns(origin, s, owner), s.id))
        else:
            destination = colonies[index % len(colonies)]
        if destination.id != ship.system_id and game.can_reach(destination.id, owner, ships=[ship]):
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
        for planet in system.worlds:
            if planet.owner not in hostile or game.bombardment_error(system.id, planet.id, owner) is not None:
                continue
            attack = len(troop_transports(game, system.id, owner))*production_balance.TROOP_STRENGTH
            defending = forces(planet, game.bonuses_for(planet.owner))
            if defenses.effective_shield(game, planet) or (attack and not resolve(attack, defending).captured):
                report = game.bombard(system.id, planet.id, owner)
                if planet.owner == "player" or game.system_visible(system.id):
                    messages.append(report.message)
        candidates = [p for p in system.worlds if p.owner in hostile and game.invasion_error(system.id, p.id, owner=owner) is None
                      and resolve(invasion_strength(game, system.id, p.id, owner)[0], forces(p, game.bonuses_for(p.owner))).captured]
        if not candidates:
            continue
        planet = (max(candidates, key=lambda p: (p.owner in coalitions.targets(game, owner), p.workforce, -p.id)) if raiding.is_varkesh(game, owner) else
                  min(candidates, key=lambda p: (p.owner not in coalitions.targets(game, owner), not p.ascension_gate, p.population, p.id)))
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
    nature = personality(game, owner)
    from . import motherships
    nomadic = motherships.is_wanderer(game, owner)
    motherships.ai_orders(game, owner)
    if nomadic:
        from .hyperlanes import ai_orders as hyperlane_orders
        hyperlane_orders(game, owner)
    coalitions.ai_orders(game, owner)
    tribute.ai_orders(game, owner)
    from .diplomacy import ai_treaty_orders
    ai_treaty_orders(game, owner)
    invasions = diplomatic_orders(game, owner)
    invasions.extend(outposts.ai_orders(game, owner, enemies(game, owner)))
    from . import boarding
    invasions.extend(boarding.ai_orders(game, owner, ground_reports))
    if game.result is not None:
        return invasions
    invasions.extend(invasion_orders(game, owner, ground_reports=ground_reports))
    if game.result is not None:
        return invasions
    research_choice(game, owner)
    from .megastructures import ai_orders as megastructure_orders
    megastructure_orders(game, owner)
    scouting_orders(game, owner)
    military_orders(game, monsters.ai_orders(game, owner), owner)
    for ship in sorted(game.ships_owned_by(owner), key=lambda s: s.id):
        if ship.has_course or ship.kind != "colony_ship" or raiding.is_varkesh(game, owner):
            continue
        incoming = {}
        for other in game.ships_owned_by(owner):
            if other.has_course and other.kind == "colony_ship":
                incoming[other.destination] = incoming.get(other.destination, 0)+1
        targets = [s for s in game.systems if game.within_fuel_range(s.id, owner)
                   and len(available_worlds(game, s, owner)) > incoming.get(s.id, 0)]
        context = administration.Context(game, owner)
        integrating = any(until > game.turn for until in context.timers.values())
        # Consolidate while a new system integrates or the treasury is shrinking.
        # Existing-system planets remain useful and incur no extra shared strain.
        if integrating or game.empire_rates_for(owner)[0] < 0:
            targets = [s for s in targets if s.id in context.systems]
        frontier = [s for s in targets if not any(p.owner == owner for p in game.known_system(s.id, owner).worlds)]
        local = available_worlds(game, game.systems[ship.system_id], owner)
        # Secure an initial foothold, then consider local administrative costs.
        if len(context.systems) == 1 and frontier:
            targets = frontier
        origin = game.systems[ship.system_id]
        target = min(targets, key=lambda s: (
            context.report(s.id, acquiring=True).total, game.travel_turns(origin, s, owner),
            tuple(-value for value in world_quality(max(available_worlds(game, s, owner), key=world_quality))), s.id), default=None)
        if local and target is not None and target.id == ship.system_id:
            planet = max(local, key=world_quality)
            if game.colonize_error(ship.system_id, planet.id, owner=owner) is None:
                game.colonize(ship.id, ship.system_id, planet.id, owner=owner)
                event(game, owner, f"Settled {planet.name} with {planet.population} B colonists.")
            continue
        if not targets:
            unknown = [s for s in game.systems if s.kind != black_holes.KIND and not game.system_explored(s.id, owner) and not incoming.get(s.id)
                       and monsters.known_status(game, s.id, owner) != "alive"
                       and game.within_fuel_range(s.id, owner)]
            if unknown and not integrating:
                target = min(unknown, key=lambda s: (game.travel_turns(game.systems[ship.system_id], s, owner), s.id))
                game.send_ship(ship.id, target.id, owner=owner)
            continue
        duration = game.send_ship(ship.id, target.id, owner=owner)
        event(game, owner, f"Sent {ship.name} to {target.name}; {duration} turns in transit.")

    colonies = game.settlements(owner)
    for system, planet in colonies:
        farmers = farmers_needed(planet, game.bonuses_for(owner))
        remaining = planet.workforce-farmers
        scientists = min(2, remaining//4) if "research_lab" in planet.buildings else 0
        available = remaining-scientists
        resource_target = max(250, game.project_price("colony_ship", owner)) if not raiding.is_varkesh(game, owner) else 250
        miners = min(max(0, available-1), max(1, available//3)) if game.resources_for(owner) < resource_target else 0
        game.set_workforce(system.id, planet.id, farmers, scientists, miners, owner=owner)
    recover_power(game, owner)
    recover_budget(game, owner)
    from .specialists import ai_orders as specialist_orders
    specialist_orders(game, owner)
    colonies.sort(key=lambda row: (-game.planet_yields(row[1])[0], -row[1].population, row[0].id, row[1].id))
    if ("science" in game.victory_conditions and "ascension_theory" in game._empire(owner).technology.completed
            and not gate_site(game, owner)):
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
    warships = sum(not s.habitat and game.military_strength(s) > 0 for s in game.ships_owned_by(owner)) + sum(
        project.is_ship and project.item_id != "mothership" and (project.spec.damage or project.spec.drone_bays) > 0
        for _, p in colonies for project in p.construction_queue)
    military_limit = min(6, max(1, len(colonies)//2)+nature.fleet_bonus)
    guarded = [g for g in game.guardians if monsters.known_status(game, g.system_id, owner) == "alive"
               and game.within_fuel_range(g.system_id, owner)]
    if guarded:
        # Reserve enough hull for the strongest known guardian (up to 9 frigates).
        military_limit = max(military_limit, max((g.spec.hull*5+79)//80 for g in guarded))
    transports = sum(s.kind == "troop_transport" for s in game.ships_owned_by(owner)) + sum(
        project.item_id == "troop_transport" for _, p in colonies for project in p.construction_queue)
    hostile = enemies(game, owner)
    known_bases = max((sum("missile_base" in p.buildings for p in s.worlds if p.owner in hostile)
                       for s in (game.known_system(s.id, owner) for s in game.systems) if s), default=0)
    military_limit = max(military_limit, min(12, 3+known_bases*3) if known_bases else 0)
    troop_limit = max((transports_needed(p, production_balance.TROOP_STRENGTH, game.bonuses_for(p.owner) if game.system_visible(s.id, owner) else {}) for s, p in known_enemy_colonies(game, owner)
                       if p.owner in hostile and game.within_fuel_range(s.id, owner)), default=0)
    unknown = sum(not game.system_explored(s.id, owner) for s in game.systems if s.kind != black_holes.KIND)
    fleet_limit = min(unclaimed+bool(unknown), 3, 1+len(colonies)//2)
    if raiding.is_varkesh(game, owner) or nomadic:
        fleet_limit = 0
    if nomadic:
        troop_limit = 0
    scouts = sum(s.kind == "scout" for s in game.ships_owned_by(owner)) + sum(
        q.item_id == "scout" for _, p in colonies for q in p.construction_queue)
    outpost_ships = sum(s.kind == "outpost_ship" for s in game.ships_owned_by(owner)) + sum(
        q.item_id == "outpost_ship" for _, p in colonies for q in p.construction_queue)
    outpost_count = sum(p.outpost_owner == owner for s in game.systems for p in s.worlds)
    want_outpost = outpost_count < max(1, 2*len(colonies)) and bool(outposts.expansion_targets(game, owner))
    for index, (system, planet) in enumerate(colonies):
        if planet.construction_queue:
            if planet.trade_goods:
                # A captured colony may have a paused queue from its former owner.
                game.prioritize_construction(system.id, planet.id, 0, owner=owner)
            continue
        food = game.population_report(planet)
        farm_food = PROJECTS["hydroponic_farm"].food+planet.farmers*PROJECTS["hydroponic_farm"].food_per_farmer
        full_consumption = food_required(food.capacity+planet.slaves, game.bonuses_for(owner))
        farm_tech = BUILDINGS["hydroponic_farm"].technology
        farm_available = ("hydroponic_farm" not in planet.buildings and farm_food > 0
                          and (not farm_tech or game.research_state(owner).has_unlock(farm_tech)))
        farms_needed = int(farm_available and full_consumption > food.produced)
        needs_food = farm_available and food.consumed > 0 and (food.produced < min(full_consumption, food.consumed+2)
                      or planet.farmers > 2
                      or 0 < planet.free_slots <= farms_needed)
        if needs_food and planet.free_slots == 0:
            disposable = [i for i, b in enumerate(planet.buildings) if facility_family(b) in ("research_lab", "factory", "trade_center")]
            if disposable:
                index_to_remove = max(disposable, key=lambda i: (planet.buildings.count(planet.buildings[i]), i))
                game.demolish_building(system.id, planet.id, index_to_remove, owner=owner)
        if needs_food and planet.free_slots > 0:
            if queue_building(game, system, planet, "hydroponic_farm", owner):
                continue
        if planet.free_slots > 0 and "mine" not in planet.buildings and game.resources_for(owner) < 90 and planet.miners:
            if queue_building(game, system, planet, "mine", owner):
                continue
        # Reserve local defence before peaceful development fills every slot.
        # The main shipyard needs barracks to recruit expeditionary troops.
        military_building = None
        if "barracks" not in planet.buildings and (hostile or len(planet.buildings) >= 2):
            military_building = "barracks"
        elif (hostile or (nature.protective and len(colonies) >= 3)) and "fortifications" not in planet.buildings and "barracks" in planet.buildings:
            military_building = "fortifications"
        if (military_building == "barracks" and index == 0 and hostile and transports < troop_limit
                and planet.free_slots == 0
                and game.resources_for(owner) >= game.project_price("barracks", owner)):
            # Older, fully developed colonies need room for the new troop facility.
            # Preserve farms and the last research lab; prefer redundant industry.
            replaceable = [i for i, b in enumerate(planet.buildings) if facility_family(b) in ("factory", "mine", "trade_center")]
            if replaceable:
                slot = max(replaceable, key=lambda i: (planet.buildings.count(planet.buildings[i]), i))
                game.demolish_building(system.id, planet.id, slot, owner=owner)
        if military_building and planet.free_slots > 0:
            if queue_building(game, system, planet, military_building, owner):
                continue
        infrastructure = []
        if hostile or nature.protective:
            infrastructure += ["missile_base", "planetary_shield", "interdictor"]
        if len(game.colony_systems(owner)) > 1:
            infrastructure.append("jump_gate")
        infrastructure.append("sensor_array")
        infrastructure_item = None
        if planet.free_slots > max(0, farms_needed) and len(planet.buildings) >= 2 and (hostile or nature.protective or len(colonies) >= 4):
            infrastructure_item = next((b for b in infrastructure if game.build_error(system.id, planet.id, b, owner=owner) is None), None)
        # The strongest colony supplies ships. Other worlds build their economies.
        # Expansion raises the shipyard's development target, preventing stagnation.
        target_buildings = min(planet.building_capacity, 2+len(colonies)//2)
        # Fund an initial research base before repeated expansion consumes all
        # spare credits, especially for slow-growing civilizations.
        research_ready = game.empire_rates_for(owner)[1] > 0 or len(colonies) == 1 or planet.free_slots == 0
        produce_ship = index == 0 and fleet_size < fleet_limit and len(planet.buildings) >= target_buildings and research_ready
        produce_outpost = index == 0 and not outpost_ships and want_outpost and len(planet.buildings) >= 2
        produce_warship = (index == 0 and game.turn >= nature.military_turn and len(planet.buildings) >= 2
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
        elif produce_warship:
            kind = warship_choice(game, owner)
            if game.ship_build_error(system.id, planet.id, kind, owner=owner) is None:
                game.queue_ship(system.id, planet.id, kind, owner=owner)
                warships += 1
                event(game, owner, f"Started a {SHIP_TYPES[kind].name.lower()} on {planet.name}.")
        elif produce_transport:
            if game.ship_build_error(system.id, planet.id, "troop_transport", owner=owner) is None:
                game.queue_ship(system.id, planet.id, "troop_transport", owner=owner)
                transports += 1
                event(game, owner, f"Started a troop transport on {planet.name}.")
        elif produce_outpost:
            if game.ship_build_error(system.id, planet.id, "outpost_ship", owner=owner) is None:
                game.queue_ship(system.id, planet.id, "outpost_ship", owner=owner)
                outpost_ships += 1
                event(game, owner, f"Started an outpost ship on {planet.name}.")
        elif (nomadic and planet.population >= 15 and len(planet.buildings) >= 3
              and len(colonies) < 8 and not any(q.item_id == "mothership" for _, p in colonies for q in p.construction_queue)
              and game.ship_build_error(system.id, planet.id, "mothership", owner=owner) is None):
            game.queue_ship(system.id, planet.id, "mothership", owner=owner)
            event(game, owner, f"Started a new mothership at {planet.name}.")
        elif produce_ship:
            if game.ship_build_error(system.id, planet.id, owner=owner) is None:
                game.queue_ship(system.id, planet.id, owner=owner)
                fleet_size += 1
                event(game, owner, f"Started a colony ship on {planet.name}.")
        elif infrastructure_item is not None:
            queue_building(game, system, planet, infrastructure_item, owner)
        elif planet.free_slots > 0:
            available = {b for b in BUILDINGS if game.build_error(system.id, planet.id, b, owner=owner) is None}
            available = {b for b in available if b not in ADVANCED_FACILITIES
                         or (game.planet_yields(projected_colony(planet, b))[1] >= 0
                             and projected_income(game, owner, (system.id, planet.id, b)) >= 1)}
            item = development_choice(planet, game._empire(owner).race_id, available)
            queue_building(game, system, planet, item, owner)
        if not planet.construction_queue:
            game.set_trade_goods(system.id, planet.id, owner=owner)
    return invasions
