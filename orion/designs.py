"""Immutable ship blueprints. Existing orders and ships retain their own blueprint."""

from dataclasses import dataclass
from .research import TECHNOLOGIES

MAX_DESIGNS = 24


@dataclass(frozen=True)
class Hull:
    name: str
    hull: int
    capacity: int
    weapon: int
    defense: int
    support: int
    movement: int
    credit_cost: int
    work_cost: int


HULLS = {
    "frigate": Hull("Frigate", 20, 4, 3, 2, 1, 4, 30, 18),
    "cruiser": Hull("Cruiser", 42, 8, 5, 4, 2, 3, 70, 42),
    "battleship": Hull("Battleship", 75, 12, 8, 6, 2, 2, 130, 78),
}


@dataclass(frozen=True)
class Module:
    name: str
    category: str
    space: int
    credit_cost: int
    work_cost: int
    description: str
    technology: str | None = None
    weapon: str = "none"
    damage: int = 0
    range: int = 0


MODULES = {
    "laser": Module("Laser cannon", "weapon", 1, 12, 8, "5 damage · range 6", weapon="laser", damage=5, range=6),
    "torpedo": Module("Torpedo launcher", "weapon", 2, 22, 14, "10 damage · range 8 · countered by point defense", weapon="torpedo", damage=10, range=8),
    "quantum": Module("Quantum battery", "weapon", 2, 32, 20, "14 damage · range 7", "quantum_optics", "quantum", 14, 7),
    "siege": Module("Siege cannon", "weapon", 2, 30, 20, "8 damage · range 6 · triple damage to bases and planetary shields", "siege_weapons", "siege", 8, 6),
    "armor": Module("Armor plate", "defense", 1, 10, 6, "+8 hull · -1 tactical movement (minimum 1)"),
    "shield": Module("Shield generator", "defense", 1, 18, 12, "+12 shields · restored at the start of each battle", "radiation_shields"),
    "point_defense": Module("Point defense", "defense", 1, 12, 8, "-30% incoming torpedo damage (maximum -60%)"),
    "engine": Module("Maneuvering thruster", "support", 1, 14, 10, "+1 tactical movement · does not change travel speed", "ion_drives"),
    "scanner": Module("Combat scanner", "support", 1, 16, 10, "+1 weapon range · one scanner per ship", "research_networks"),
}


def loadout_error(kind, modules, completed=None, *, require_weapon=True):
    if not isinstance(kind, str) or kind not in HULLS:
        return "Choose a combat hull."
    if not isinstance(modules, (tuple, list)) or len(modules) > 12 or any(
            not isinstance(m, str) or m not in MODULES for m in modules):
        return "Unknown or excessive modules."
    specs, hull = [MODULES[m] for m in modules], HULLS[kind]
    if sum(m.space for m in specs) > hull.capacity:
        return "The loadout exceeds this hull's total capacity."
    for category in ("weapon", "defense", "support"):
        if sum(m.space for m in specs if m.category == category) > getattr(hull, category):
            return f"This hull has insufficient {category} capacity."
    if modules.count("scanner") > 1:
        return "Only one combat scanner can be fitted."
    if completed is not None:
        for m in specs:
            if m.technology and m.technology not in completed:
                return f"Requires {TECHNOLOGIES[m.technology].name}."
    if require_weapon and not any(m.damage for m in specs):
        return "Fit at least one weapon before saving."
    return None


@dataclass(frozen=True)
class ShipDesign:
    id: str
    name: str
    kind: str
    modules: tuple[str, ...]

    @property
    def specs(self):
        return tuple(MODULES[m] for m in self.modules)

    @property
    def hull(self):
        return HULLS[self.kind].hull+8*self.modules.count("armor")

    @property
    def shields(self):
        return 12*self.modules.count("shield")

    @property
    def interception(self):
        return min(60, 30*self.modules.count("point_defense"))

    @property
    def movement(self):
        return max(1, HULLS[self.kind].movement-self.modules.count("armor")+self.modules.count("engine"))

    @property
    def damage(self):
        return sum(m.damage for m in self.specs)

    @property
    def weapon(self):
        return next((m.weapon for m in self.specs if m.damage), "none")

    @property
    def weapon_range(self):
        return max((m.range+self.modules.count("scanner") for m in self.specs if m.damage), default=0)

    @property
    def credit_cost(self):
        return HULLS[self.kind].credit_cost+sum(m.credit_cost for m in self.specs)

    @property
    def work_cost(self):
        return HULLS[self.kind].work_cost+sum(m.work_cost for m in self.specs)

    def volley(self, distance):
        return tuple(m for m in self.specs if m.damage and distance <= m.range+self.modules.count("scanner"))

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or set(data) != {"id", "name", "kind", "modules"}:
            raise ValueError("Invalid ship design")
        identifier, name = data["id"], data["name"]
        if (not isinstance(identifier, str) or identifier not in {f"design_{i}" for i in range(1, MAX_DESIGNS+1)}
                or not isinstance(name, str) or not 1 <= len(name) <= 28 or name != name.strip()
                or not all(c.isprintable() for c in name) or loadout_error(data["kind"], data["modules"])):
            raise ValueError("Invalid ship blueprint")
        return cls(identifier, name, data["kind"], tuple(data["modules"]))
