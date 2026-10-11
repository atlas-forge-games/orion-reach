"""Planetary defense infrastructure and once-per-ship strategic bombardment."""

from dataclasses import dataclass
from fractions import Fraction
from . import ground_combat, monsters
from .navigation import hostile

BASE_HULL = 40


def base_id(system_id, planet_id):
    return -(10_000+system_id*8+planet_id)


def base_planet(game, identifier):
    if type(identifier) is not int or identifier > -10_000:
        return None
    system_id, planet_id = divmod(-identifier-10_000, 8)
    if 0 <= system_id < len(game.systems) and 0 <= planet_id < len(game.systems[system_id].worlds):
        return game.systems[system_id].worlds[planet_id]
    return None


def bases(game, system_id, owner=None):
    return [p for p in game.systems[system_id].worlds if p.colonized and game.building_operational(p, "missile_base")
            and (owner is None or p.owner == owner)]


def shield_capacity(game, planet):
    return max(100, game.bonuses_for(planet.owner).get("shield_capacity", 0)) if "planetary_shield" in planet.buildings and planet.owner else 0


def effective_shield(game, planet):
    return planet.shield_points if game.building_operational(planet, "planetary_shield") else 0


def commissioned(game, planet, identifier):
    if identifier == "planetary_shield":
        planet.shield_points = shield_capacity(game, planet)
    if identifier == "missile_base":
        planet.battery_hull = BASE_HULL


def normalize(planet):
    if "planetary_shield" not in planet.buildings:
        planet.shield_points = 0
    if "missile_base" not in planet.buildings:
        planet.battery_hull = 0


def advance(game):
    for system in game.systems:
        for planet in system.worlds:
            normalize(planet)
            if not planet.owner:
                continue
            blocked = any(hostile(game, s.owner, planet.owner) and (s.damage or s.drone_bays) and not s.in_transit and s.system_id == system.id
                          for s in game.ships)
            if not blocked and planet.bombarded_turn < game.turn-1:
                if game.building_operational(planet, "planetary_shield"):
                    planet.shield_points = min(shield_capacity(game, planet), planet.shield_points+25)
                if game.building_operational(planet, "missile_base"):
                    planet.battery_hull = min(BASE_HULL, (planet.battery_hull or BASE_HULL)+4)


def bombardment_fleet(game, system_id, owner):
    return [s for s in game.fleet_at(system_id, owner) if s.damage and s.bombarded_turn != game.turn]


def bombardment_error(game, system_id, planet_id, owner="player"):
    if game.strategy_error(owner):
        return game.strategy_error(owner)
    planet = game.planet_at(system_id, planet_id)
    if planet.owner is None or planet.owner == owner:
        return "Choose an opposing colony."
    if monsters.alive_at(game, system_id):
        return "Defeat the system guardian before bombardment."
    if game.foreign_fleet(system_id, owner) or any(p.owner != owner for p in bases(game, system_id)):
        return "Defeat the opposing ships and missile bases before bombardment."
    if not bombardment_fleet(game, system_id, owner):
        return "Bring armed ships that have not bombarded this turn."
    if effective_shield(game, planet) == 0 and ground_combat.forces(planet).troops == 0:
        return "The shield and ground defenses are already suppressed."
    return None


def bombardment_attacks(game, system_id, owner="player"):
    attacks = []
    for ship in bombardment_fleet(game, system_id, owner):
        if ship.design:
            from .weapons import BEAMS
            attacks.extend((m.damage, 3 if m.weapon == "siege" else BEAMS[m.weapon].shield_multiplier)
                           for m in ship.design.specs if m.damage)
        else:
            from .combat import BEAMS, weapon_for
            damage = BEAMS[weapon_for(game, ship.kind, owner)].damage
            attacks.append((damage*(2 if game.bonuses_for(owner).get("siege_bonus") else 1), 1))
    return attacks


def bombardment_power(game, system_id, owner="player"):
    """Maximum shield damage, before accounting for an already depleted shield."""
    return sum(damage*multiplier for damage, multiplier in bombardment_attacks(game, system_id, owner))


def bombardment_forecast(game, system_id, planet_id, owner="player"):
    planet = game.planet_at(system_id, planet_id)
    shield, ground_damage = effective_shield(game, planet), Fraction(0)
    for damage, multiplier in bombardment_attacks(game, system_id, owner):
        absorbed = min(shield, damage*multiplier)
        shield -= absorbed
        # Shield-specific siege/ion amplification never increases ground damage.
        ground_damage += damage-Fraction(absorbed, multiplier)
    troops = ground_combat.forces(planet, game.bonuses_for(planet.owner))
    return effective_shield(game, planet)-shield, min(troops.troops, ground_damage//5)


@dataclass(frozen=True)
class BombardmentReport:
    shield_damage: int
    troop_losses: int
    message: str


def bombard(game, system_id, planet_id, owner="player"):
    from .model import RuleError
    from .victory import apply_ground_casualties, record_ground_hostility
    from .exploration import refresh
    error = bombardment_error(game, system_id, planet_id, owner)
    if error:
        raise RuleError(error)
    planet = game.planet_at(system_id, planet_id)
    absorbed, losses = bombardment_forecast(game, system_id, planet_id, owner)
    planet.shield_points -= absorbed
    troops = ground_combat.forces(planet, game.bonuses_for(planet.owner))
    apply_ground_casualties(planet, troops, troops.troops-losses)
    planet.bombarded_turn = game.turn
    for ship in bombardment_fleet(game, system_id, owner):
        ship.bombarded_turn = game.turn
        if ship.departure_pending:
            game._clear_course(ship)
    message = f"Bombardment of {planet.name}: {absorbed} shield points and {losses} defending troops lost."
    record_ground_hostility(game, owner, planet.owner, message)
    refresh(game)
    return BombardmentReport(absorbed, losses, message)
