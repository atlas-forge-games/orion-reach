"""Shared construction resources and independent, deterministic colony grids."""

from dataclasses import dataclass
from .buildings import BUILDINGS, MINERAL_FACTORS, facility_family

STARTING_RESOURCES = 120
STARTING_CREDITS = 120
STARTING_POPULATION = 8
MINER_RESOURCES = 2
BASE_EXTRACTION = 2
BASE_ENERGY = 12
GATE_ENERGY = 10


@dataclass(frozen=True)
class EnergyReport:
    generated: int = 0
    demand: int = 0
    used: int = 0
    active: tuple[int, ...] = ()
    offline: tuple[int, ...] = ()
    gate_powered: bool = False
    base_generated: int = 0
    backup_capacity: int = 0
    backup_generated: int = 0
    fuel_used: int = 0
    # Slot, actual generation, Resource use; includes standby generators.
    plants: tuple[tuple[int, int, int], ...] = ()

    @property
    def balance(self):
        return self.generated-self.demand


class PowerBonuses(dict):
    """Ordinary modifiers with a runtime-only colony grid lookup.

    All yield, food and military calculations share the same funded dispatch.
    The context is not an effect, never enters saved research, and survives an
    empty modifier dictionary being passed through `bonuses or {}`.
    """
    def __init__(self, bonuses, power, local=None):
        super().__init__(bonuses)
        self.power = power
        self.local = local

    def at(self, planet):
        if self.local is None:
            return self
        values = dict(self)
        for key, value in self.local(planet).items():
            values[key] = values.get(key, 0)+value
        return PowerBonuses(values, self.power)

    def __bool__(self):
        return True


def dispatch_power(planets, bonuses, resources):
    """Allocate an empire's existing fuel once, in system/planet order."""
    result = {}
    for planet in planets:
        report = energy_report(planet, dict(bonuses), fuel_budget=resources)
        result[id(planet)] = report
        resources -= report.fuel_used
    return result


def energy_report(planet, bonuses=None, *, fuel_budget=0):
    """Farms and mines have priority; other loads follow building-slot order.

    Steady sources run first. Backup burns only enough fuel for loads which
    can actually operate; it never spends fuel on unusable partial power.
    A shortage suspends whole buildings, so
    every economic and military effect has the same unambiguous on/off state.
    Demand includes automatically suspended loads, but excludes manual stops.
    """
    if not planet.colonized:
        return EnergyReport()
    if isinstance(bonuses, PowerBonuses):
        return bonuses.power(planet)
    bonuses = bonuses or {}
    enabled = [i for i in range(len(planet.buildings)) if i not in planet.disabled_buildings]
    generated = BASE_ENERGY+bonuses.get("colony_energy", 0)
    plants = [(i, BUILDINGS[planet.buildings[i]]) for i in enabled if BUILDINGS[planet.buildings[i]].energy_output]
    generated += sum(b.energy_output for _, b in plants if not b.energy_per_resource)
    base_generated = generated
    backup = [(i, b) for i, b in plants if b.energy_per_resource]
    remaining_fuel = max(0, fuel_budget)
    for _, building in backup:
        output = min(building.energy_output, remaining_fuel*building.energy_per_resource)
        generated += output
        remaining_fuel -= (output+building.energy_per_resource-1)//building.energy_per_resource
    demand = sum(BUILDINGS[planet.buildings[i]].energy_use for i in enabled)
    demand += GATE_ENERGY if planet.ascension_gate else 0
    priority = {"hydroponic_farm": 0, "mine": 1}
    used, active, offline = 0, [], []
    for i in sorted(enabled, key=lambda i: (priority.get(facility_family(planet.buildings[i]), 2), i)):
        cost = BUILDINGS[planet.buildings[i]].energy_use
        if used+cost <= generated:
            active.append(i)
            used += cost
        else:
            offline.append(i)
    gate_powered = planet.ascension_gate and used+GATE_ENERGY <= generated
    if gate_powered:
        used += GATE_ENERGY
    needed, remaining_fuel, fuel_used = max(0, used-base_generated), max(0, fuel_budget), 0
    outputs = []
    for i, building in plants:
        if building.energy_per_resource:
            output = min(needed, building.energy_output, remaining_fuel*building.energy_per_resource)
            fuel = (output+building.energy_per_resource-1)//building.energy_per_resource
            needed -= output
            remaining_fuel -= fuel
            fuel_used += fuel
        else:
            output, fuel = building.energy_output, 0
        outputs.append((i, output, fuel))
    backup_generated = max(0, used-base_generated)
    return EnergyReport(base_generated+backup_generated, demand, used, tuple(sorted(active)), tuple(sorted(offline)), gate_powered,
                        base_generated, sum(b.energy_output for _, b in backup), backup_generated, fuel_used, tuple(outputs))


def active_buildings(planet, bonuses=None):
    return [planet.buildings[i] for i in energy_report(planet, bonuses).active]


def operational(planet, identifier, bonuses=None):
    return identifier in active_buildings(planet, bonuses)


def miner_output(planet, bonuses=None):
    extra = sum(BUILDINGS[b].resources_per_miner for b in active_buildings(planet, bonuses))
    return (MINER_RESOURCES+extra)*MINERAL_FACTORS[planet.richness]


def mining_output(planet, bonuses=None):
    if not planet.colonized:
        return 0
    bonuses = local_bonuses(planet, bonuses)
    buildings = active_buildings(planet, bonuses)
    base = sum(BUILDINGS[b].resources for b in buildings)*MINERAL_FACTORS[planet.richness]
    return (BASE_EXTRACTION+bonuses.get("colony_resources", 0)+int(base+planet.miners*miner_output(planet, bonuses))
            +sum(facility_family(b) == "mine" for b in buildings)*bonuses.get("mine_resources", 0))


def local_bonuses(planet, bonuses):
    return bonuses.at(planet) if isinstance(bonuses, PowerBonuses) else (bonuses or {})


def building_status(planet, index, bonuses=None):
    if index in planet.disabled_buildings:
        return "DISABLED"
    report = energy_report(planet, bonuses)
    if BUILDINGS[planet.buildings[index]].energy_per_resource:
        output = next((output for slot, output, _ in report.plants if slot == index), 0)
        return "BACKUP ON" if output else "NO FUEL" if report.balance < 0 else "STANDBY"
    return "NO POWER" if index in report.offline else "OPERATIONAL"


def remove_building(planet, index):
    identifier = planet.buildings.pop(index)
    planet.disabled_buildings = [i-(i > index) for i in planet.disabled_buildings if i != index]
    return identifier
