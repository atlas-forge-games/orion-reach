"""Snapshot colony corridors and local interdiction when a voyage is ordered."""

import math
from .production import distance_ly
from . import production as production_balance

GATE_SPEED_BONUS = 50
INTERDICTION_SLOW = 25
INTERDICTION_RANGE = 5


def modifier_limits():
    """Upper bounds for saved orders, including earlier discoveries in a profile."""
    from .research import TECHNOLOGIES
    from .races import RACES
    tech = [dict(t.effects) for t in TECHNOLOGIES.values()]
    races = [dict(r.effects) for r in RACES.values()]
    def racial(key):
        return max((r.get(key, 0) for r in races), default=0)
    return (max(GATE_SPEED_BONUS, sum(t.get("colony_speed", 0) for t in tech)+racial("colony_speed")),
            max(INTERDICTION_RANGE, max((t.get("interdiction_range", 0) for t in tech), default=0)+racial("interdiction_range")),
            max(INTERDICTION_SLOW, max((t.get("interdiction_slow", 0) for t in tech), default=0)+racial("interdiction_slow")))


def hostile(game, first, second):
    if first == second or first not in game.owners or second not in game.owners:
        return False
    relation = game.diplomacy_between(first, second)
    return relation.at_war


def route_modifiers(game, origin, destination, owner):
    own_origin = game.settlements_at(origin.id, owner)
    own_target = game.settlements_at(destination.id, owner)
    bonus = 0
    if own_origin and own_target:
        bonus = game.bonuses_for(owner).get("colony_speed", 0)
        if all(any(game.building_operational(p, "jump_gate") for p in group) for group in (own_origin, own_target)):
            bonus = GATE_SPEED_BONUS
    fields = []
    for p in destination.worlds:
        if not game.building_operational(p, "interdictor") or not hostile(game, owner, p.owner):
            continue
        benefits = game.bonuses_for(p.owner)
        fields.append((max(INTERDICTION_SLOW, benefits.get("interdiction_slow", 0)), max(INTERDICTION_RANGE, benefits.get("interdiction_range", 0))))
    slow, radius = max(fields, default=(0, 0))
    if game.bonuses_for(owner).get("field_stabilization"):
        slow /= 2
    return bonus, float(min(radius, distance_ly(origin, destination))), slow


def duration(origin, destination, speed_bonus=0, *, cruise_speed=None,
             route_bonus=0, approach_range=0, approach_slow=0):
    if cruise_speed is None:
        cruise_speed = production_balance.SHIP_SPEED
    if origin.id == destination.id:
        return 0
    distance = distance_ly(origin, destination)
    speed = 100*cruise_speed*(1+speed_bonus/100)*(1+route_bonus/100)
    protected = min(distance, approach_range)
    time = (distance-protected)/speed+protected/(speed*(1-approach_slow/100))
    return max(1, math.ceil(time-1e-10))


def position(game, ship):
    origin = game.systems[ship.system_id]
    if not ship.in_transit:
        return origin.x, origin.y
    destination = game.systems[ship.destination]
    progress = 1-ship.turns_remaining/ship.travel_total
    if ship.approach_slow:
        distance = distance_ly(origin, destination)
        free = distance-ship.approach_range
        # Normalize the two physical speed segments to whole game turns.
        scaled_time = progress*(free+ship.approach_range/(1-ship.approach_slow/100))
        travelled = min(scaled_time, free)+max(0, scaled_time-free)*(1-ship.approach_slow/100)
        progress = travelled/distance
    return origin.x+(destination.x-origin.x)*progress, origin.y+(destination.y-origin.y)*progress
