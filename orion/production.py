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


SHIP_TYPES = {"colony_ship": ShipSpec("colony_ship", "Colony ship", 80, 42)}
PROJECTS = {**BUILDINGS, **SHIP_TYPES}
MAX_QUEUE = 20
SHIP_SPEED = .18  # Weighted galaxy-map distance per turn.
STARTING_COLONISTS = 1  # Billions, included in the ship cost in this prototype.


def travel_turns(origin, destination, speed_bonus=0):
    if origin.id == destination.id:
        return 0
    distance = math.hypot((destination.x-origin.x)*1.4, destination.y-origin.y)
    return max(1, math.ceil(distance/(SHIP_SPEED*(1+speed_bonus/100))))
