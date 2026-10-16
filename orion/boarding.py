"""Assault disabled mobile cities using the existing ground combat rules."""

from dataclasses import replace
from . import ground_combat, motherships, victory

DISABLED_TURNS = 3
RAID_COOLDOWN = 10
DECK_DEFENCE = 25
STOCKPILE_LIMIT = 1_000_000_000


def disable(game, ship):
    ship.hull = 1
    ship.disabled_turns = DISABLED_TURNS
    game._clear_course(ship)


def advance(game):
    for ship in motherships.homes(game):
        if ship.disabled_turns:
            ship.disabled_turns -= 1
            if not ship.disabled_turns:
                ship.hull = max(ship.hull, max(1, ship.max_hull//10))


def defending_forces(game, ship):
    forces = ground_combat.forces(ship.habitat, game.bonuses_for(ship.owner))
    return replace(forces, defence_bonus=forces.defence_bonus+DECK_DEFENCE)


def target(game, ship_id):
    return next((s for s in game.ships if s.id == ship_id and s.habitat), None)


def error(game, ship_id, mode="capture", owner="player"):
    from . import defenses, diplomacy, monsters
    if mode not in ("capture", "raid", "destroy"):
        return "Choose boarding, a raid or destruction."
    if game.strategy_error(owner):
        return game.strategy_error(owner)
    ship = target(game, ship_id)
    if ship is None or ship.owner == owner or ship.in_transit:
        return "Choose an opposing mothership anchored in a system."
    if diplomacy.aggression_error(game, owner, ship.owner):
        return diplomacy.aggression_error(game, owner, ship.owner)
    if not ship.disabled_turns:
        return "Defeat the mothership's space defenses first."
    if monsters.alive_at(game, ship.system_id):
        return "Defeat the system guardian first."
    from .navigation import hostile
    opponents = {ship.owner} | {o for o in game.owners if o != owner and hostile(game, owner, o)}
    if any(s.owner in opponents and not s.disabled_turns for s in game.foreign_fleet(ship.system_id, owner)):
        return "Clear the defending fleet before approaching the mothership."
    if any(p.owner in opponents for p in defenses.bases(game, ship.system_id)):
        return "Destroy the defending missile bases first."
    if mode == "destroy":
        if not any(game.military_strength(s) for s in game.fleet_at(ship.system_id, owner)):
            return "An operational armed ship must be present to destroy the mothership."
    elif not victory.troop_transports(game, ship.system_id, owner):
        return "Bring troop transports into orbit to board the mothership."
    elif ship.assaulted_turn == game.turn:
        return "This mothership has already faced a boarding assault this turn."
    elif mode == "raid" and ship.raided_turn and game.turn < ship.raided_turn+RAID_COOLDOWN:
        return f"Stores can be raided again in {ship.raided_turn+RAID_COOLDOWN-game.turn} turns."
    return None


def loot(game, ship, owner="player"):
    from . import raiding
    home = ship.habitat
    victim, attacker = game._empire(ship.owner), game._empire(owner)
    credits = min(home.population*10+len(home.buildings)*20, max(0, victim.credits), max(0, STOCKPILE_LIMIT-attacker.credits))
    resources = min(home.population*3+len(home.buildings)*10, max(0, victim.resources), max(0, STOCKPILE_LIMIT-attacker.resources))
    slaves = min(max(0, home.population-1), home.population//4, raiding.capacity_left(game, owner)) if raiding.is_varkesh(game, owner) else 0
    return credits, resources, slaves


def salvage(game, ship, owner="player"):
    from .buildings import BUILDINGS
    from .production import SHIP_TYPES
    value = (SHIP_TYPES[ship.kind].resource_cost+sum(BUILDINGS[b].resource_cost for b in ship.habitat.buildings))//10
    return min(value, max(0, STOCKPILE_LIMIT-game._empire(owner).resources))


def dispatch(game, participants, message):
    # Loot is private to the combatants; snapshots remain valid if the home is gone.
    if game.is_observer or "player" in participants:
        from .coalitions import notify
        notify(game, participants, message[:240])


def normalize(game, previous_systems):
    from . import administration, coalitions, exploration, specialists, tribute
    motherships.relocate_specialists(game)
    specialists.normalize(game)
    coalitions.normalize(game)
    tribute.normalize(game)
    administration.ownership_changed(game, previous_systems)
    exploration.refresh(game)
    game.eliminate_defeated()
    game.check_victory()


def assault(game, ship_id, mode="capture", owner="player"):
    from . import administration, population, raiding
    from .model import RuleError
    problem = error(game, ship_id, mode, owner)
    if problem:
        raise RuleError(problem)
    ship = target(game, ship_id)
    home, defender = ship.habitat, ship.owner
    previous_systems = administration.snapshot(game)
    if mode == "destroy":
        recovered = salvage(game, ship, owner)
        game._empire(owner).resources += recovered
        game.ships.remove(ship)
        message = f"{game.empire_name_for(owner)} destroyed {home.name} at {game.systems[ship.system_id].name}; recovered {recovered} RES in salvage."
        victory.record_ground_hostility(game, owner, defender, message)
        dispatch(game, (owner, defender), message)
        normalize(game, previous_systems)
        return recovered
    transports = victory.troop_transports(game, ship.system_id, owner)
    attack = len(transports)*victory.production_balance.TROOP_STRENGTH
    defending = defending_forces(game, ship)
    outcome = ground_combat.resolve(attack, defending)
    ship.assaulted_turn = game.turn
    lost, ground_troops = victory.transport_losses(len(transports), outcome.attackers)
    for transport in transports[:lost]:
        game.ships.remove(transport)
    credits = resources = slaves = 0
    if mode == "capture":
        victory.apply_ground_outcome(home, owner, defending, outcome)
        if outcome.captured:
            ship.owner = owner
            home.garrison = ground_troops
            # Foreign empires can operate the prize, but cannot build new arks.
            if not motherships.is_wanderer(game, owner):
                for project in home.construction_queue[:]:
                    if project.item_id == "mothership":
                        game._empire(owner).credits = min(STOCKPILE_LIMIT, game._empire(owner).credits+project.refund)
                        game._empire(owner).resources = min(STOCKPILE_LIMIT, game._empire(owner).resources+project.resource_refund)
                        home.construction_queue.remove(project)
    else:
        victory.apply_ground_casualties(home, defending, outcome.defenders)
        if outcome.captured:
            credits, resources, slaves = loot(game, ship, owner)
            game._empire(defender).credits -= credits
            game._empire(owner).credits += credits
            game._empire(defender).resources -= resources
            game._empire(owner).resources += resources
            ship.raided_turn = game.turn
            if slaves:
                home.population -= slaves
                prison = raiding.homeworld(game, owner)
                prison.slaves += slaves
                prison.farmers = population.farmers_needed(prison, game.bonuses_for(owner), surplus=1)
                population.clamp_workforce(prison)
            # Partial surviving squads return to a friendly settlement, if any.
            destination = next((p for _, p in game.settlements(owner)), None)
            if destination:
                destination.garrison = min(ground_combat.MAX_GARRISON, destination.garrison+ground_troops)
    population.clamp_workforce(home)
    from .diplomacy import record_defeat
    record_defeat(game, defender if outcome.captured else owner, owner if outcome.captured else defender)
    action = ("captured" if mode == "capture" else "raided") if outcome.captured else "failed to board"
    message = f"{game.empire_name_for(owner)} {action} {home.name}: {lost} transports lost."
    if mode == "raid" and outcome.captured:
        message += f" Loot: {credits} CR, {resources} RES, {slaves} slave units."
    victory.record_ground_hostility(game, owner, defender, message)
    dispatch(game, (owner, defender), message)
    normalize(game, previous_systems)
    return victory.InvasionReport(owner, ship.system_id, home.id, attack, defending.strength, len(transports),
                                  outcome.captured, defender, defending.militia, defending.garrison,
                                  defending.defence_bonus, outcome.attackers, outcome.defenders, outcome.rounds,
                                  cause="boarding" if mode == "capture" else "mothership_raid",
                                  slaves_taken=slaves, credits_stolen=credits, resources_stolen=resources, target_name=home.name)


def ai_orders(game, owner, ground_reports=None):
    from . import raiding
    from .navigation import hostile
    messages = []
    for ship in list(motherships.homes(game)):
        if game.result or ship.owner == owner or not ship.disabled_turns or not hostile(game, owner, ship.owner):
            continue
        mode = "raid" if raiding.is_varkesh(game, owner) and not error(game, ship.id, "raid", owner) else "capture"
        if error(game, ship.id, mode, owner) is None:
            attack = len(victory.troop_transports(game, ship.system_id, owner))*victory.production_balance.TROOP_STRENGTH
            if ground_combat.resolve(attack, defending_forces(game, ship)).captured:
                report = assault(game, ship.id, mode, owner)
                if ground_reports is not None and report.defender == "player":
                    ground_reports.append(report)
                messages.append(f"{game.empire_name_for(owner)} boarded {ship.name}.")
                continue
        if error(game, ship.id, "destroy", owner) is None:
            assault(game, ship.id, "destroy", owner)
            messages.append(f"{game.empire_name_for(owner)} destroyed {ship.name}.")
    return messages
