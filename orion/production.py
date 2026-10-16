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
    technology: str | None = None
    drone_bays: int = 0


HULL_TECHNOLOGIES = {
    "frigate": None, "destroyer": "destroyer_hulls", "cruiser": "cruiser_hulls",
    "battleship": "battleship_hulls", "carrier": "drone_carriers", "titan": "titan_hulls",
}


SHIP_TYPES = {
    "mothership": ShipSpec("mothership", "Mothership", 1200, 600, hull=180, damage=5),
    "colony_ship": ShipSpec("colony_ship", "Colony ship", 800, 420, hull=12),
    "frigate": ShipSpec("frigate", "Frigate", 60, 36, hull=20, damage=5),
    "troop_transport": ShipSpec("troop_transport", "Troop transport", 80, 42, hull=16),
    "scout": ShipSpec("scout", "Scout", 25, 12, hull=8),
    "outpost_ship": ShipSpec("outpost_ship", "Outpost ship", 80, 42, hull=12),
    "destroyer": ShipSpec("destroyer", "Destroyer", 90, 54, hull=30, damage=10, technology="destroyer_hulls"),
    "cruiser": ShipSpec("cruiser", "Cruiser", 150, 90, hull=42, damage=12, technology="cruiser_hulls"),
    "battleship": ShipSpec("battleship", "Battleship", 260, 156, hull=75, damage=18, technology="battleship_hulls"),
    "carrier": ShipSpec("carrier", "Drone carrier", 210, 126, hull=55, damage=5, technology="drone_carriers", drone_bays=2),
    "titan": ShipSpec("titan", "Titan", 420, 252, hull=125, damage=26, technology="titan_hulls"),
}


@dataclass(frozen=True)
class SpecialProject:
    id: str
    name: str
    resource_cost: int
    work_cost: int
    maintenance: int = 0


ASCENSION_GATE = SpecialProject("ascension_gate", "Ascension Gate", 500, 300, maintenance=5)
# An ongoing production mode, not a finite construction project or building.
TRADE_GOODS = SpecialProject("trade_goods", "Trade Goods", 0, 0)
PROJECTS = {**BUILDINGS, **SHIP_TYPES, ASCENSION_GATE.id: ASCENSION_GATE}
MAX_QUEUE = 20
SHIP_SPEED = .02  # 2 light-years per turn; travel time depends on the generated distance.
LEGACY_SHIP_SPEED = .18  # Preserve voyages ordered before v0.19.
BASE_FUEL_RANGE = 7  # Light-years from any owned colony or planetary outpost.
STARTING_COLONISTS = 1  # Billions, included in the ship cost in this prototype.
REPAIR_PER_TURN = 4
TROOP_STRENGTH = 8
GATE_CHARGE_TURNS = 5
TRADE_GOODS_PERCENT = 30


def trade_goods_credits(industry):
    """Convert the configured share of industry, flooring once per colony."""
    return max(0, industry)*TRADE_GOODS_PERCENT//100


def distance_ly(origin, destination):
    return 100*math.hypot((destination.x-origin.x)*1.4, destination.y-origin.y)


def travel_turns(origin, destination, speed_bonus=0, *, cruise_speed=None):
    if cruise_speed is None:
        cruise_speed = SHIP_SPEED
    if origin.id == destination.id:
        return 0
    return max(1, math.ceil(distance_ly(origin, destination)/(100*cruise_speed*(1+speed_bonus/100))-1e-10))
