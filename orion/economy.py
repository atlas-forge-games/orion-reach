"""Shared construction resources and independent, deterministic colony grids."""

from dataclasses import dataclass
from .buildings import BUILDINGS, MINERAL_FACTORS

STARTING_RESOURCES = 120
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

    @property
    def balance(self):
        return self.generated-self.demand


def energy_report(planet, bonuses=None):
    """Farms and mines have priority; other loads follow building-slot order.

    Generation has no energy input. A shortage suspends whole buildings, so
    every economic and military effect has the same unambiguous on/off state.
    Demand includes automatically suspended loads, but excludes manual stops.
    """
    if not planet.colonized:
        return EnergyReport()
    bonuses = bonuses or {}
    enabled = [i for i in range(len(planet.buildings)) if i not in planet.disabled_buildings]
    generated = BASE_ENERGY+bonuses.get("colony_energy", 0)
    generated += sum(BUILDINGS[planet.buildings[i]].energy_output for i in enabled)
    demand = sum(BUILDINGS[planet.buildings[i]].energy_use for i in enabled)
    demand += GATE_ENERGY if planet.ascension_gate else 0
    priority = {"hydroponic_farm": 0, "mine": 1}
    used, active, offline = 0, [], []
    for i in sorted(enabled, key=lambda i: (priority.get(planet.buildings[i], 2), i)):
        cost = BUILDINGS[planet.buildings[i]].energy_use
        if used+cost <= generated:
            active.append(i)
            used += cost
        else:
            offline.append(i)
    gate_powered = planet.ascension_gate and used+GATE_ENERGY <= generated
    if gate_powered:
        used += GATE_ENERGY
    return EnergyReport(generated, demand, used, tuple(sorted(active)), tuple(sorted(offline)), gate_powered)


def active_buildings(planet, bonuses=None):
    return [planet.buildings[i] for i in energy_report(planet, bonuses).active]


def operational(planet, identifier, bonuses=None):
    return identifier in active_buildings(planet, bonuses)


def miner_output(planet, bonuses=None):
    extra = sum(BUILDINGS[b].resources_per_miner for b in active_buildings(planet, bonuses))
    return (2+extra)*MINERAL_FACTORS[planet.richness]


def mining_output(planet, bonuses=None):
    if not planet.colonized:
        return 0
    bonuses = bonuses or {}
    buildings = active_buildings(planet, bonuses)
    base = sum(BUILDINGS[b].resources for b in buildings)*MINERAL_FACTORS[planet.richness]
    return (BASE_EXTRACTION+int(base+planet.miners*miner_output(planet, bonuses))
            +buildings.count("mine")*bonuses.get("mine_resources", 0))


def building_status(planet, index, bonuses=None):
    if index in planet.disabled_buildings:
        return "DISABLED"
    return "NO POWER" if index in energy_report(planet, bonuses).offline else "OPERATIONAL"


def remove_building(planet, index):
    identifier = planet.buildings.pop(index)
    planet.disabled_buildings = [i-(i > index) for i in planet.disabled_buildings if i != index]
    return identifier
