"""Automatic fleet command, derived from surviving ships rather than saved buffs."""

import math
from . import combat_geometry as geometry

ACCURACY = 8
EVASION = 5
RADII = {"scout": 2, "frigate": 2, "destroyer": 3, "cruiser": 4,
         "carrier": 5, "battleship": 6, "titan": 8, "mothership": 8,
         "colony_ship": 3, "outpost_ship": 3, "troop_transport": 3}


def power(ship):
    """Full-strength rating: damage, endurance and a carrier's strike capacity.

    Current damage, cooldowns and remaining drone launches cannot transfer
    command. Armed ships lead civilian convoys; equal ratings use the lower ID.
    """
    rating = ship.max_hull + ship.max_shields + 4*ship.damage + 12*ship.drone_bays
    return bool(ship.damage or ship.drone_bays), rating, -ship.id


def select(state, owner):
    if state is None:
        return None
    return max((ship for ship in state.fleet(owner) if ship.kind in RADII),
               key=power, default=None)


def radius(ship):
    return RADII.get(ship.kind, 0)


def is_flagship(state, ship):
    return ship is not None and select(state, ship.owner) is ship


def source(state, target):
    """Other crewed ships receive command; drones and surface bases do not."""
    if target is None or target.hull <= 0 or target.kind not in RADII:
        return None
    leader = select(state, target.owner)
    if leader is None or leader.id == target.id:
        return None
    return leader if math.dist(geometry.center(leader), geometry.center(target)) <= radius(leader) else None


def evasion(state, target):
    return EVASION if source(state, target) else 0


def description(state, ship):
    if is_flagship(state, ship):
        return (f"FLAGSHIP · {radius(ship)}-cell radius · Nearby fleetmates: "
                f"+{ACCURACY} aim / +{EVASION} evasion")
    leader = source(state, ship)
    if leader:
        return f"Flagship support: {leader.name} · +{ACCURACY} aim / +{EVASION} evasion"
    return "Outside flagship coverage" if ship.hull > 0 and ship.kind in RADII else ""
