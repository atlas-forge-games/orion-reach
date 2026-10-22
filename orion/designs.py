"""Immutable ship blueprints. Existing orders and ships retain their own blueprint."""

from dataclasses import dataclass, replace
from functools import lru_cache
from .research import TECHNOLOGIES
from .production import HULL_TECHNOLOGIES

MAX_DESIGNS = 24
DRONE_BAYS = {"drone_bay": "assault", "interceptor_bay": "interceptor", "bomber_bay": "bomber"}
SUPPORT_HULLS = {
    "escort_array": ("destroyer",),
    "command_relay": ("cruiser", "titan"),
    "flag_bridge": ("titan",),
    "ecm_projector": ("cruiser",),
}


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
    # The original capacities above only validate pre-v0.53 blueprints.
    offensive_slots: int = 4
    defensive_slots: int = 2
    support_slots: int = 2
    module_size: str = "small"
    module_scale: int = 100
    tracking_penalty: int = 0


HULLS = {
    "frigate": Hull("Frigate", 20, 4, 3, 2, 1, 4, 30, 18, support_slots=1),
    "destroyer": Hull("Destroyer", 30, 6, 4, 3, 2, 4, 45, 27),
    "cruiser": Hull("Cruiser", 42, 8, 5, 4, 2, 3, 70, 42, defensive_slots=3,
                    module_size="medium", module_scale=200, tracking_penalty=30),
    "battleship": Hull("Battleship", 75, 12, 8, 6, 2, 2, 130, 78, defensive_slots=3,
                       module_size="heavy", module_scale=300, tracking_penalty=30),
    "carrier": Hull("Carrier", 55, 10, 3, 4, 6, 2, 100, 60, support_slots=3,
                    module_size="medium", module_scale=200, tracking_penalty=30),
    "titan": Hull("Titan", 125, 18, 12, 9, 3, 1, 220, 132, defensive_slots=3,
                  module_size="heavy", module_scale=400, tracking_penalty=35),
}

MODULE_SIZES = {"small": 1, "medium": 2, "heavy": 3}
SLOT_FIELDS = {"weapon": "offensive_slots", "defense": "defensive_slots", "support": "support_slots"}


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
    hull_bonus: int = 0
    shields: int = 0
    shield_regeneration: int = 0
    shield_hardening: int = 0
    repair_rate: int = 0
    repair_capacity: int = 0
    interception: int = 0
    interception_cap: int = 0
    movement_bonus: int = 0
    range_bonus: int = 0
    support_range: int = 0
    escort_interception: int = 0
    command_accuracy: int = 0
    jamming: int = 0


MODULES = {
    "laser": Module("Laser cannon", "weapon", 1, 12, 8, "5 damage · range 6", weapon="laser", damage=5, range=6),
    "torpedo": Module("Torpedo launcher", "weapon", 2, 22, 14, "10 damage · range 8 · countered by point defense", weapon="torpedo", damage=10, range=8),
    "quantum": Module("Quantum battery", "weapon", 2, 32, 20, "14 damage · range 7", "quantum_optics", "quantum", 14, 7),
    "siege": Module("Siege cannon", "weapon", 2, 30, 20, "8 damage · range 6 · triple damage to bases and planetary shields", "siege_weapons", "siege", 8, 6),
    "armor": Module("Armor plate", "defense", 1, 10, 6, "+8 hull · -1 tactical movement (minimum 1)"),
    "shield": Module("Shield generator", "defense", 1, 18, 12, "+12 shields · restored at the start of each battle", "radiation_shields"),
    "point_defense": Module("Point defense", "defense", 1, 12, 8, "-30% missile and torpedo damage (maximum -60%)"),
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
    "escort_array": Module("Escort array", "support", 1, 24, 16,
        "Destroyer · protects allies within 2 cells · +25% interception", support_range=2, escort_interception=25),
    "command_relay": Module("Command relay", "support", 1, 24, 16,
        "Cruiser / Titan · allies within 3 cells gain +8 aim · strongest only", "research_networks",
        support_range=3, command_accuracy=8),
    "flag_bridge": Module("Flag bridge", "support", 1, 36, 24,
        "Titan · allies within 4 cells gain +12 aim · strongest only", "titan_hulls",
        support_range=4, command_accuracy=12),
    "ecm_projector": Module("ECM projector", "support", 1, 28, 18,
        "Cruiser · attacks against allies within 3 cells lose 8 aim · strongest only", "electronic_countermeasures",
        support_range=3, jamming=8),
}

for _identifier, _effects in {
    "armor": {"hull_bonus": 8, "movement_bonus": -1},
    "reinforced_armor": {"hull_bonus": 14, "movement_bonus": -1},
    "shield": {"shields": 12},
    "regenerative_shield": {"shields": 8, "shield_regeneration": 2},
    "hardened_shield": {"shields": 12, "shield_hardening": 75},
    "point_defense": {"interception": 30, "interception_cap": 60},
    "flak": {"interception": 45, "interception_cap": 75},
    "damage_control": {"repair_rate": 3, "repair_capacity": 12},
    "engine": {"movement_bonus": 1}, "scanner": {"range_bonus": 1},
}.items():
    MODULES[_identifier] = replace(MODULES[_identifier], **_effects)

# Save-era identifiers must not depend on the editable/current tree positions.
ARSENAL_TECHNOLOGIES = frozenset((
    "pulse_beams", "plasma_beams", "ion_beams", "graviton_beams", "particle_beams",
    "heavy_beam_mounts", "phased_beams", "disruptor_beams", "fusion_torpedoes",
    "reinforced_armor", "mirv_torpedoes", "antimatter_torpedoes", "regenerative_shields",
    "hardened_shields", "interceptor_drones", "advanced_flak", "bomber_drones", "automated_damage_control",
))


@lru_cache(maxsize=512)
def fitted_module(kind, identifier, fit_version=2):
    """One module occupies one category slot; its physical size follows the hull."""
    module = MODULES[identifier]
    if fit_version == 1:
        return module
    hull = HULLS[kind]
    scaled = {key: max(1, (getattr(module, key)*hull.module_scale+99)//100) if getattr(module, key) else 0
              for key in ("damage", "hull_bonus", "shields", "shield_regeneration",
                          "repair_rate", "repair_capacity", "resource_cost", "work_cost")}
    name = module.name.removeprefix("Heavy ") if identifier == "heavy_beam" else module.name
    return replace(module, name=f"{hull.module_size.title()} {name}", space=1, **scaled)


def missing_research(kind, modules, completed, *, legacy_hulls=False):
    """Ordered research requirements for a structurally valid blueprint."""
    hull_tech = HULL_TECHNOLOGIES[kind]
    requirements = ([] if legacy_hulls and kind in ("cruiser", "battleship") else [hull_tech])
    requirements += [MODULES[m].technology for m in modules]
    return tuple(dict.fromkeys(t for t in requirements if t and t not in completed))


def loadout_error(kind, modules, completed=None, *, require_weapon=True, legacy_hulls=False, fit_version=2):
    if not isinstance(kind, str) or kind not in HULLS:
        return "Choose a combat hull."
    if type(fit_version) is not int or fit_version not in (1, 2):
        return "Unknown blueprint rules."
    limit = max(max(h.capacity, h.offensive_slots+h.defensive_slots+h.support_slots) for h in HULLS.values())
    if not isinstance(modules, (tuple, list)) or len(modules) > limit or any(
            not isinstance(m, str) or m not in MODULES for m in modules):
        return "Unknown or excessive modules."
    specs, hull = [MODULES[m] for m in modules], HULLS[kind]
    if fit_version == 1 and sum(m.space for m in specs) > hull.capacity:
        return "The loadout exceeds this hull's total capacity."
    for category in ("weapon", "defense", "support"):
        used = sum(m.space if fit_version == 1 else 1 for m in specs if m.category == category)
        if used > getattr(hull, category if fit_version == 1 else SLOT_FIELDS[category]):
            return f"This hull has insufficient {category} {'capacity' if fit_version == 1 else 'slots'}."
    if modules.count("scanner") > 1:
        return "Only one combat scanner can be fitted."
    for identifier, hulls in SUPPORT_HULLS.items():
        if identifier in modules and kind not in hulls:
            return f"{MODULES[identifier].name} requires a {' or '.join(HULLS[k].name for k in hulls)} hull."
        if modules.count(identifier) > 1:
            return f"Only one {MODULES[identifier].name.lower()} can be fitted."
    if sum(m in ("command_relay", "flag_bridge") for m in modules) > 1:
        return "Fit one command module per ship."
    if any(m in DRONE_BAYS for m in modules) and kind != "carrier":
        return "Drone bays require a carrier hull."
    if fit_version == 2 and sum(m in DRONE_BAYS for m in modules) > 2:
        return "A carrier can fit at most two drone bays."
    if completed is not None:
        missing = missing_research(kind, modules, completed, legacy_hulls=legacy_hulls)
        if missing:
            return f"Requires {TECHNOLOGIES[missing[0]].name}."
    if require_weapon and not any(m.damage for m in specs) and not any(m in DRONE_BAYS for m in modules):
        return "Fit at least one weapon or drone bay before saving."
    return None


@dataclass(frozen=True)
class ShipDesign:
    id: str
    name: str
    kind: str
    modules: tuple[str, ...]
    fit_version: int = 2

    @property
    def specs(self):
        return tuple(fitted_module(self.kind, m, self.fit_version) for m in self.modules)

    @property
    def maintenance(self):
        from .production import SHIP_TYPES
        return SHIP_TYPES[self.kind].maintenance

    @property
    def hull(self):
        return HULLS[self.kind].hull+sum(m.hull_bonus for m in self.specs)

    @property
    def shields(self):
        return sum(m.shields for m in self.specs)

    @property
    def shield_regeneration(self):
        return sum(m.shield_regeneration for m in self.specs)

    @property
    def shield_hardening(self):
        return max((m.shield_hardening for m in self.specs), default=0)

    @property
    def repair_rate(self):
        return sum(m.repair_rate for m in self.specs)

    @property
    def repair_capacity(self):
        return sum(m.repair_capacity for m in self.specs)

    @property
    def interception(self):
        return min(max((m.interception_cap for m in self.specs), default=0), sum(m.interception for m in self.specs))

    @property
    def movement(self):
        return max(1, HULLS[self.kind].movement+sum(m.movement_bonus for m in self.specs))

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
        return max((m.range+sum(s.range_bonus for s in self.specs) for m in self.specs if m.damage), default=0)

    @property
    def resource_cost(self):
        return HULLS[self.kind].resource_cost+sum(m.resource_cost for m in self.specs)

    @property
    def work_cost(self):
        return HULLS[self.kind].work_cost+sum(m.work_cost for m in self.specs)

    def volley(self, distance):
        return tuple(m for m in self.specs if m.damage and distance <= m.range+sum(s.range_bonus for s in self.specs))

    @classmethod
    def from_dict(cls, data, *, version=37):
        current = {"id", "name", "kind", "modules", "fit_version"}
        if not isinstance(data, dict) or set(data) not in (current, current-{"fit_version"} if version < 37 else current):
            raise ValueError("Invalid ship design")
        identifier, name = data["id"], data["name"]
        fit_version = data.get("fit_version", 1)
        if (not isinstance(identifier, str) or identifier not in {f"design_{i}" for i in range(1, MAX_DESIGNS+1)}
                or not isinstance(name, str) or not 1 <= len(name) <= 28 or name != name.strip()
                or not all(c.isprintable() for c in name)
                or loadout_error(data["kind"], data["modules"], fit_version=fit_version)):
            raise ValueError("Invalid ship blueprint")
        return cls(identifier, name, data["kind"], tuple(data["modules"]), fit_version)
