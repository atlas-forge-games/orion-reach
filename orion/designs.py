"""Immutable ship blueprints. Existing orders and ships retain their own blueprint."""

from dataclasses import dataclass
from .research import TECHNOLOGIES, LEGACY_TIER_LIMITS
from .production import HULL_TECHNOLOGIES

MAX_DESIGNS = 24
DRONE_BAYS = {"drone_bay": "assault", "interceptor_bay": "interceptor", "bomber_bay": "bomber"}


@dataclass(frozen=True)
class Hull:
    name: str
    hull: int
    capacity: int
    weapon: int
    defense: int
    support: int
    movement: int
    resource_cost: int
    work_cost: int


HULLS = {
    "frigate": Hull("Frigate", 20, 4, 3, 2, 1, 4, 30, 18),
    "destroyer": Hull("Destroyer", 30, 6, 4, 3, 2, 4, 45, 27),
    "cruiser": Hull("Cruiser", 42, 8, 5, 4, 2, 3, 70, 42),
    "battleship": Hull("Battleship", 75, 12, 8, 6, 2, 2, 130, 78),
    "carrier": Hull("Carrier", 55, 10, 3, 4, 6, 2, 100, 60),
    "titan": Hull("Titan", 125, 18, 12, 9, 3, 1, 220, 132),
}


@dataclass(frozen=True)
class Module:
    name: str
    category: str
    space: int
    resource_cost: int
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
    "point_defense": Module("Point defense", "defense", 1, 12, 8, "-30% torpedo and drone damage (maximum -60%)"),
    "engine": Module("Maneuvering thruster", "support", 1, 14, 10, "+1 tactical movement · does not change travel speed", "ion_drives"),
    "scanner": Module("Combat scanner", "support", 1, 16, 10, "+1 weapon range · one scanner per ship", "research_networks"),
    "drone_bay": Module("Drone bay", "support", 3, 30, 18, "Carrier only · 2 active drones · 4 launches/battle", "drone_carriers"),
    "pulse": Module("Pulse cannon", "weapon", 1, 24, 16, "2 × 4 damage · range 6 · +15 accuracy", "pulse_beams", "pulse", 8, 6),
    "plasma": Module("Plasma cannon", "weapon", 2, 48, 30, "24 damage · range 4", "plasma_beams", "plasma", 24, 4),
    "ion": Module("Ion cannon", "weapon", 2, 44, 28, "8 hull / up to 32 shield damage · range 6", "ion_beams", "ion", 8, 6),
    "graviton": Module("Graviton beam", "weapon", 2, 50, 32, "16 damage · range 6 · slow target 1 cell (no stacking)", "graviton_beams", "graviton", 16, 6),
    "particle": Module("Particle lance", "weapon", 3, 62, 40, "20 damage · range 10", "particle_beams", "particle", 20, 10),
    "heavy_beam": Module("Heavy beam battery", "weapon", 4, 82, 52, "30 damage · range 9", "heavy_beam_mounts", "heavy_beam", 30, 9),
    "phased": Module("Phased beam", "weapon", 2, 65, 42, "16 damage · range 7 · 50% bypasses ship shields", "phased_beams", "phased", 16, 7),
    "disruptor": Module("Disruptor", "weapon", 3, 88, 56, "40 damage · range 5 · recharge 1 turn after firing", "disruptor_beams", "disruptor", 40, 5),
    "fusion_torpedo": Module("Fusion launcher", "weapon", 2, 42, 26, "18 damage · range 9 · intercepted by point defense", "fusion_torpedoes", "fusion_torpedo", 18, 9),
    "mirv": Module("MIRV launcher", "weapon", 3, 62, 40, "3 × 7 damage · range 8 · ignores half of interception", "mirv_torpedoes", "mirv", 21, 8),
    "antimatter": Module("Antimatter launcher", "weapon", 3, 78, 50, "36 damage · range 9 · reload 1 turn after firing", "antimatter_torpedoes", "antimatter", 36, 9),
    "reinforced_armor": Module("Reinforced armor", "defense", 1, 26, 16, "+14 hull · -1 tactical movement (minimum 1)", "reinforced_armor"),
    "regenerative_shield": Module("Regenerative shield", "defense", 1, 32, 20, "+8 shields · recover 2 at the start of each turn", "regenerative_shields"),
    "hardened_shield": Module("Hardened shield", "defense", 1, 34, 22, "+12 shields · reduce shield penetration by 75%", "hardened_shields"),
    "flak": Module("Advanced flak", "defense", 1, 28, 18, "45% interception · shipboard cap 75%", "advanced_flak"),
    "damage_control": Module("Damage control", "support", 1, 32, 20, "Repair 3 hull/turn · reserve 12/battle · battle damage only", "automated_damage_control"),
    "interceptor_bay": Module("Interceptor bay", "support", 3, 45, 28, "Carrier · 2 active / 4 launches · protect allies within 2 cells", "interceptor_drones"),
    "bomber_bay": Module("Bomber bay", "support", 3, 48, 30, "Carrier · 2 active / 4 launches · double damage to capitals", "bomber_drones"),
}

ARSENAL_TECHNOLOGIES = frozenset(t.id for t in TECHNOLOGIES.values()
                               if t.branch in LEGACY_TIER_LIMITS and t.tier > LEGACY_TIER_LIMITS[t.branch])


def loadout_error(kind, modules, completed=None, *, require_weapon=True, legacy_hulls=False):
    if not isinstance(kind, str) or kind not in HULLS:
        return "Choose a combat hull."
    if not isinstance(modules, (tuple, list)) or len(modules) > max(h.capacity for h in HULLS.values()) or any(
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
    if any(m in DRONE_BAYS for m in modules) and kind != "carrier":
        return "Drone bays require a carrier hull."
    if completed is not None:
        technology = HULL_TECHNOLOGIES[kind]
        if (technology and technology not in completed
                and not (legacy_hulls and kind in ("cruiser", "battleship"))):
            return f"Requires {TECHNOLOGIES[technology].name}."
        for m in specs:
            if m.technology and m.technology not in completed:
                return f"Requires {TECHNOLOGIES[m.technology].name}."
    if require_weapon and not any(m.damage for m in specs) and not any(m in DRONE_BAYS for m in modules):
        return "Fit at least one weapon or drone bay before saving."
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
        return HULLS[self.kind].hull+8*self.modules.count("armor")+14*self.modules.count("reinforced_armor")

    @property
    def shields(self):
        return 12*(self.modules.count("shield")+self.modules.count("hardened_shield"))+8*self.modules.count("regenerative_shield")

    @property
    def shield_regeneration(self):
        return 2*self.modules.count("regenerative_shield")

    @property
    def shield_hardening(self):
        return 75 if "hardened_shield" in self.modules else 0

    @property
    def repair_rate(self):
        return 3*self.modules.count("damage_control")

    @property
    def repair_capacity(self):
        return 12*self.modules.count("damage_control")

    @property
    def interception(self):
        return min(75 if "flak" in self.modules else 60,
                   30*self.modules.count("point_defense")+45*self.modules.count("flak"))

    @property
    def movement(self):
        return max(1, HULLS[self.kind].movement-self.modules.count("armor")
                   -self.modules.count("reinforced_armor")+self.modules.count("engine"))

    @property
    def damage(self):
        return sum(m.damage for m in self.specs)

    @property
    def drone_bays(self):
        return sum(self.modules.count(m) for m in DRONE_BAYS)

    @property
    def drone_bay_counts(self):
        return {role: self.modules.count(m) for m, role in DRONE_BAYS.items() if m in self.modules}

    @property
    def weapon(self):
        return next((m.weapon for m in self.specs if m.damage), "none")

    @property
    def weapon_range(self):
        return max((m.range+self.modules.count("scanner") for m in self.specs if m.damage), default=0)

    @property
    def resource_cost(self):
        return HULLS[self.kind].resource_cost+sum(m.resource_cost for m in self.specs)

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
