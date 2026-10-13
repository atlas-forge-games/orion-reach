"""Unpopulated planetary refuelling bases, separate from colonies and their yields."""

from . import defenses, monsters, black_holes
from .navigation import hostile
from .production import distance_ly

OUTPOST_HULL = 30
OUTPOST_RECOVERY = 4


def at(game, system_id):
    return next((p for p in game.systems[system_id].worlds if p.outpost_owner), None)


def ships_at(game, system_id, owner="player"):
    return [s for s in game.fleet_at(system_id, owner) if s.kind == "outpost_ship"]


def clear(planet):
    planet.outpost_owner, planet.outpost_hull = None, 0


def deployment_error(game, system_id, planet_id, owner="player"):
    if game.strategy_error(owner):
        return game.strategy_error(owner)
    planet = game.planet_at(system_id, planet_id)
    if planet.colonized:
        return "Choose an uncolonized planet for the outpost."
    if at(game, system_id):
        return "Only one outpost may exist in each solar system."
    if monsters.alive_at(game, system_id):
        return "Defeat the system guardian before establishing an outpost."
    if game.foreign_fleet(system_id, owner) or any(p.owner != owner for p in defenses.bases(game, system_id)):
        return "Clear opposing ships and missile bases before establishing an outpost."
    if not ships_at(game, system_id, owner):
        return "Bring an outpost ship to this system first."
    return None


def deploy(game, ship_id, system_id, planet_id, owner="player"):
    from .model import RuleError
    from .exploration import refresh
    ship = game.ship_at(ship_id, owner=owner)
    if ship not in ships_at(game, system_id, owner):
        raise RuleError("An outpost ship must be in orbit in this system.")
    error = deployment_error(game, system_id, planet_id, owner)
    if error:
        raise RuleError(error)
    planet = game.planet_at(system_id, planet_id)
    planet.outpost_owner, planet.outpost_hull = owner, OUTPOST_HULL
    game.ships.remove(ship)
    refresh(game)
    return planet


def attack_error(game, system_id, planet_id, owner="player"):
    if game.strategy_error(owner):
        return game.strategy_error(owner)
    planet = game.planet_at(system_id, planet_id)
    if planet.outpost_owner in (None, owner):
        return "Choose an opposing outpost."
    if monsters.alive_at(game, system_id):
        return "Defeat the system guardian first."
    if game.foreign_fleet(system_id, owner) or any(p.owner != owner for p in defenses.bases(game, system_id)):
        return "Defeat opposing ships and missile bases before attacking the outpost."
    if not defenses.bombardment_fleet(game, system_id, owner):
        return "Bring armed ships that have not bombarded this turn."
    return None


def attack_damage(game, system_id, planet_id, owner="player"):
    # Shield-specific weapon multipliers do not amplify damage to an unshielded base.
    return min(game.planet_at(system_id, planet_id).outpost_hull,
               sum(damage for damage, _ in defenses.bombardment_attacks(game, system_id, owner)))


def attack(game, system_id, planet_id, owner="player"):
    from .model import RuleError
    from .victory import record_ground_hostility
    from .exploration import refresh, record_survey
    error = attack_error(game, system_id, planet_id, owner)
    if error:
        raise RuleError(error)
    planet = game.planet_at(system_id, planet_id)
    defender = planet.outpost_owner
    damage = attack_damage(game, system_id, planet_id, owner)
    planet.outpost_hull -= damage
    planet.bombarded_turn = game.turn
    for ship in defenses.bombardment_fleet(game, system_id, owner):
        ship.bombarded_turn = game.turn
        if ship.departure_pending:
            game._clear_course(ship)
    message = f"Outpost on {planet.name}: {damage} hull damage; {planet.outpost_hull}/{OUTPOST_HULL} remaining."
    if not planet.outpost_hull:
        clear(planet)
        message = f"Outpost on {planet.name} destroyed. Its refuelling coverage is lost."
    record_ground_hostility(game, owner, defender, message)
    # The owner receives the final dispatch even after losing its local observer.
    record_survey(game, system_id, defender)
    refresh(game)
    return message


def advance(game):
    for system in game.systems:
        for planet in system.worlds:
            if not planet.outpost_owner:
                continue
            blocked = any(hostile(game, ship.owner, planet.outpost_owner) and (ship.damage or ship.drone_bays)
                          for ship in game.ships if not ship.in_transit and ship.system_id == system.id)
            if not blocked and planet.bombarded_turn < game.turn-1:
                planet.outpost_hull = min(OUTPOST_HULL, planet.outpost_hull+OUTPOST_RECOVERY)


def expansion_targets(game, owner):
    """Use only surveyed worlds; build bases that add reachable destinations."""
    reachable = {s.id for s in game.systems if game.within_fuel_range(s.id, owner)}
    result = []
    for system in game.systems:
        if system.id not in reachable or system in game.supply_systems(owner):
            continue
        known = game.known_system(system.id, owner)
        if (not known or not any(not p.colonized for p in known.worlds)
                or any(p.outpost_owner for p in known.worlds)
                or monsters.known_status(game, system.id, owner) == "alive"):
            continue
        if game.system_visible(system.id, owner) and (game.foreign_fleet(system.id, owner)
                or any(p.owner != owner for p in defenses.bases(game, system.id))):
            continue
        gain = sum(s.id not in reachable and s.kind != black_holes.KIND
                   and distance_ly(system, s) <= game.fuel_range(owner) for s in game.systems)
        if gain:
            result.append((gain, system))
    return sorted(result, key=lambda row: (-row[0], row[1].id))


def ai_orders(game, owner, enemies):
    messages = []
    for system in game.systems:
        planet = at(game, system.id)
        if (planet and planet.outpost_owner in enemies and game.system_visible(system.id, owner)
                and attack_error(game, system.id, planet.id, owner) is None):
            defender = planet.outpost_owner
            message = attack(game, system.id, planet.id, owner)
            if "player" in (owner, defender) or game.system_visible(system.id):
                messages.append(message)
    claimed = {s.destination for s in game.ships_owned_by(owner) if s.kind == "outpost_ship" and s.has_course}
    for ship in list(game.ships_owned_by(owner)):
        if ship.kind != "outpost_ship" or ship.has_course:
            continue
        targets = expansion_targets(game, owner)
        # An arriving ship may deploy even if another base extended range meanwhile.
        local = game.systems[ship.system_id]
        if local not in game.colony_systems(owner):
            planet = next((p for p in local.worlds if deployment_error(game, local.id, p.id, owner) is None), None)
            if planet:
                deploy(game, ship.id, local.id, planet.id, owner)
                game.rival_event(f"Established a refuelling outpost on {planet.name}.", owner=owner)
                continue
        target = next((s for _, s in targets if s.id not in claimed and s.id != ship.system_id), None)
        if target:
            game.send_ship(ship.id, target.id, owner=owner)
            claimed.add(target.id)
    return messages
