"""Construction catalogue and initial colonization balance."""

from dataclasses import dataclass
import math

from .buildings import BUILDINGS


@dataclass(frozen=True)
class ShipSpec:
    id: str
    name: str
    credit_cost: int
    work_cost: int
    hull: int
    damage: int = 0


SHIP_TYPES = {
    "colony_ship": ShipSpec("colony_ship", "Colony ship", 80, 42, hull=12),
    "frigate": ShipSpec("frigate", "Frigate", 60, 36, hull=20, damage=5),
    "troop_transport": ShipSpec("troop_transport", "Troop transport", 80, 42, hull=16),
}


@dataclass(frozen=True)
class SpecialProject:
    id: str
    name: str
    credit_cost: int
    work_cost: int


ASCENSION_GATE = SpecialProject("ascension_gate", "Ascension Gate", 500, 300)
PROJECTS = {**BUILDINGS, **SHIP_TYPES, ASCENSION_GATE.id: ASCENSION_GATE}
MAX_QUEUE = 20
SHIP_SPEED = .18  # Weighted galaxy-map distance per turn.
STARTING_COLONISTS = 1  # Billions, included in the ship cost in this prototype.
REPAIR_PER_TURN = 4
TROOP_STRENGTH = 8
GATE_CHARGE_TURNS = 5


def travel_turns(origin, destination, speed_bonus=0):
    if origin.id == destination.id:
        return 0
    distance = math.hypot((destination.x-origin.x)*1.4, destination.y-origin.y)
    return max(1, math.ceil(distance/(SHIP_SPEED*(1+speed_bonus/100))))
