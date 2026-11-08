"""Shared construction resources and independent, deterministic colony grids."""

from dataclasses import dataclass
from math import floor
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
    unlimited: bool = False
    orbital_generated: int = 0
    efficiency: float = 1

    @property
    def balance(self):
        return self.generated-self.demand

    @property
    def efficiency_label(self):
        return f"{round(100*self.efficiency, 1):g}%"

    def rate(self, building, slot=None):
        """Operating fraction, checking the slot when it may be disabled."""
        if slot is not None and slot not in self.active:
            return 0
        return self.efficiency if building.energy_use else 1


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
    """Share available power proportionally between enabled building loads.

    Steady generation runs first, then fuel-backed generation. A legacy
    Ascension Gate can charge only from ten whole units left after buildings.
    """
    if not planet.colonized:
        return EnergyReport()
    if isinstance(bonuses, PowerBonuses):
        return bonuses.power(planet)
    bonuses = bonuses or {}
    enabled = [i for i in range(len(planet.buildings)) if i not in planet.disabled_buildings]
    plants = [(i, BUILDINGS[planet.buildings[i]]) for i in enabled if BUILDINGS[planet.buildings[i]].energy_output]
    base_generated = max(0, BASE_ENERGY+bonuses.get("colony_energy", 0)
                         +sum(b.energy_output for _, b in plants if not b.energy_per_resource))
    backup = [(i, b) for i, b in plants if b.energy_per_resource]
    building_demand = sum(BUILDINGS[planet.buildings[i]].energy_use for i in enabled)
    demand = building_demand+(GATE_ENERGY if planet.ascension_gate else 0)
    if bonuses.get("unlimited_energy"):
        # Store finite supplied energy for saves/statistics; display the flag as ∞.
        return EnergyReport(generated=max(base_generated, demand), demand=demand, used=demand,
                            active=tuple(enabled), gate_powered=planet.ascension_gate,
                            base_generated=max(base_generated, demand),
                            backup_capacity=sum(b.energy_output for _, b in backup),
                            plants=tuple((i, 0 if b.energy_per_resource else b.energy_output, 0) for i, b in plants),
                            unlimited=True)
    gate_powered = False
    if planet.ascension_gate:
        available, fuel = base_generated, max(0, fuel_budget)
        for _, building in backup:
            output = min(building.energy_output, fuel*building.energy_per_resource)
            available += output
            fuel -= (output+building.energy_per_resource-1)//building.energy_per_resource
        gate_powered = available >= demand
    target = demand if gate_powered else building_demand
    needed, remaining_fuel, fuel_used = max(0, target-base_generated), max(0, fuel_budget), 0
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
    backup_generated = max(0, target-base_generated)-needed
    generated = base_generated+backup_generated
    efficiency = generated/building_demand if generated < building_demand else 1
    offline = tuple(i for i in enabled if generated == 0 and BUILDINGS[planet.buildings[i]].energy_use)
    return EnergyReport(generated=generated, demand=demand, used=min(target, generated),
                        active=tuple(i for i in enabled if i not in offline), offline=offline,
                        gate_powered=gate_powered, base_generated=base_generated,
                        backup_capacity=sum(b.energy_output for _, b in backup),
                        backup_generated=backup_generated, fuel_used=fuel_used, plants=tuple(outputs),
                        efficiency=efficiency)


def operating_facilities(planet, bonuses=None):
    """Installed, active facilities and the share of each one's rated output."""
    if getattr(bonuses, 'facility_planet', None) == id(planet):
        return bonuses.facilities
    report = energy_report(planet, bonuses)
    specs = (BUILDINGS[planet.buildings[i]] for i in report.active)
    return [(spec, report.rate(spec)) for spec in specs]


def active_buildings(planet, bonuses=None):
    return [spec.id for spec, rate in operating_facilities(planet, bonuses)]


def facility_bonus_sources(planet, bonuses=None):
    """One operating copy of each type supplies its colony-wide bonuses."""
    sources = {}
    for spec, rate in operating_facilities(planet, bonuses):
        if spec.id not in sources or rate > sources[spec.id][1]:
            sources[spec.id] = (spec, rate)
    return list(sources.values())


def building_efficiency(planet, identifier, bonuses=None):
    if identifier not in planet.buildings:
        return 0
    report = energy_report(planet, bonuses)
    if any(planet.buildings[i] == identifier for i in report.active):
        return report.rate(BUILDINGS[identifier])
    return 0


def operational(planet, identifier, bonuses=None):
    return building_efficiency(planet, identifier, bonuses) > 0


def whole_output(value):
    """Truncate whole game units after summing fractional facility output."""
    return floor(value+1e-9)


def miner_output(planet, bonuses=None):
    extra = sum(b.resources_per_miner*rate for b, rate in facility_bonus_sources(planet, bonuses))
    return (MINER_RESOURCES+extra)*MINERAL_FACTORS[planet.richness]


def mining_output(planet, bonuses=None):
    from .administration import reduced_output
    if not planet.colonized:
        return 0
    bonuses = local_bonuses(planet, bonuses)
    buildings = operating_facilities(planet, bonuses)
    base = sum(b.resources*rate for b, rate in buildings)*MINERAL_FACTORS[planet.richness]
    upgrades = sum(rate for b, rate in buildings if facility_family(b.id) == "mine")*bonuses.get("mine_resources", 0)
    raw = BASE_EXTRACTION+bonuses.get("colony_resources", 0)+whole_output(base+planet.miners*miner_output(planet, bonuses)+upgrades)
    return reduced_output(raw, bonuses, "mining")


def local_bonuses(planet, bonuses):
    if getattr(bonuses, 'facility_planet', None) == id(planet):
        return bonuses
    source = getattr(bonuses, 'facility_source', bonuses)
    values = source.at(planet) if isinstance(source, PowerBonuses) else (source or {})
    result = PowerBonuses(values, values.power) if isinstance(values, PowerBonuses) else FacilityBonuses(values)
    result.facility_source, result.facility_planet = source, id(planet)
    result.facilities = operating_facilities(planet, values)
    facilities = facility_bonus_sources(planet, result)
    result['facility_growth'] = sum(b.growth_bonus*rate for b, rate in facilities)
    result['facility_capacity'] = sum(b.capacity_bonus*rate for b, rate in facilities)
    result['facility_adaptation'] = min(80, sum(b.adaptation*rate for b, rate in facilities))
    relief = sum(b.strain_relief*rate for b, rate in facilities)
    result['administrative_strain'] = max(0, result.get('administrative_strain', 0)-relief)
    result['facility_strain_relief'] = relief
    return result


class FacilityBonuses(dict):
    """Runtime-only marker prevents nested yield calculations adding facilities twice."""


def building_status(planet, index, bonuses=None):
    if index in planet.disabled_buildings:
        return "DISABLED"
    report = energy_report(planet, bonuses)
    if BUILDINGS[planet.buildings[index]].energy_per_resource:
        output = next((output for slot, output, _ in report.plants if slot == index), 0)
        return "BACKUP ON" if output else "NO FUEL" if report.balance < 0 else "STANDBY"
    if index in report.offline:
        return "NO POWER"
    if report.rate(BUILDINGS[planet.buildings[index]]) < 1:
        return f"{report.efficiency_label} POWER"
    return "OPERATIONAL"


def remove_building(planet, index):
    from .colony_layout import remove_site
    remove_site(planet, index)
    identifier = planet.buildings.pop(index)
    if BUILDINGS[identifier].training and not any(BUILDINGS[b].training for b in planet.buildings):
        planet.training_progress = 0
    planet.disabled_buildings = [i-(i > index) for i in planet.disabled_buildings if i != index]
    return identifier
