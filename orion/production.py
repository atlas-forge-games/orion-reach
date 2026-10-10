"""Construction catalogue and initial colonization balance."""

from dataclasses import dataclass
import math

from .buildings import BUILDINGS


@dataclass(frozen=True)
class ShipSpec:
    id: str
    name: str
    resource_cost: int
    work_cost: int
    hull: int
    damage: int = 0


SHIP_TYPES = {
    "colony_ship": ShipSpec("colony_ship", "Colony ship", 80, 42, hull=12),
    "frigate": ShipSpec("frigate", "Frigate", 60, 36, hull=20, damage=5),
    "troop_transport": ShipSpec("troop_transport", "Troop transport", 80, 42, hull=16),
    "scout": ShipSpec("scout", "Scout", 25, 12, hull=8),
}


@dataclass(frozen=True)
class SpecialProject:
    id: str
    name: str
    resource_cost: int
    work_cost: int
    maintenance: int = 0


ASCENSION_GATE = SpecialProject("ascension_gate", "Ascension Gate", 500, 300, maintenance=5)
PROJECTS = {**BUILDINGS, **SHIP_TYPES, ASCENSION_GATE.id: ASCENSION_GATE}
MAX_QUEUE = 20
SHIP_SPEED = .02  # 2 light-years per turn; travel time depends on the generated distance.
LEGACY_SHIP_SPEED = .18  # Preserve voyages ordered before v0.19.
BASE_FUEL_RANGE = 7  # Light-years from any owned colony, not from a scout's position.
STARTING_COLONISTS = 1  # Billions, included in the ship cost in this prototype.
REPAIR_PER_TURN = 4
TROOP_STRENGTH = 8
GATE_CHARGE_TURNS = 5


def distance_ly(origin, destination):
    return 100*math.hypot((destination.x-origin.x)*1.4, destination.y-origin.y)


def travel_turns(origin, destination, speed_bonus=0, *, cruise_speed=SHIP_SPEED):
    if origin.id == destination.id:
        return 0
    return max(1, math.ceil(distance_ly(origin, destination)/(100*cruise_speed*(1+speed_bonus/100))-1e-10))
