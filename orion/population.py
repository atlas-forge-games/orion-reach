"""Local food balances and deterministic population growth, independent of the UI."""

from dataclasses import dataclass

from .buildings import BUILDINGS, workforce_bonuses
from .economy import active_buildings

POPULATION_LIMITS = {"Tiny": 8, "Small": 12, "Medium": 16, "Large": 20, "Huge": 24}
BASE_FOOD = {"Terran": 6, "Ocean": 4, "Desert": 0, "Tundra": 0, "Barren": 0, "Volcanic": 0, "Gaia": 12}
FARMER_OUTPUT = {"Terran": 2, "Ocean": 2, "Desert": 2, "Tundra": 2, "Barren": 1, "Volcanic": 1, "Gaia": 3}
WORKER_ROLES = ("farmers", "workers", "scientists", "miners")
GROWTH_THRESHOLD = 100
GROWTH_LIMIT = 25
GAIA_GROWTH_LIMIT = 35
GROWTH_PER_FOOD = 5
ASSEMBLY_GROWTH_LIMIT = 25
GROWTH_PER_INDUSTRY = 5
GAIA_CAPACITY = 4
LUSH_BIOMES = ("Terran", "Ocean", "Gaia")


def population_capacity(planet, bonuses=None):
    base = POPULATION_LIMITS[planet.size] + (GAIA_CAPACITY if planet.biome == "Gaia" else 0)
    return base*(100+(bonuses or {}).get("capacity_percent", 0))//100


def food_required(population, bonuses=None):
    return (population*(100+(bonuses or {}).get("food_use_percent", 0))+99)//100


def assembly_work(planet, industry, bonuses):
    if planet.population >= population_capacity(planet, bonuses):
        return 0
    # Reserve at least one industry for construction, even on new outposts.
    return min(max(0, industry-1), (industry*bonuses.get("assembly_percent", 0)+99)//100)


def farmer_output(planet, bonuses=None):
    return FARMER_OUTPUT[planet.biome]+workforce_bonuses(planet, bonuses).food


def farmers_needed(planet, bonuses, surplus=2):
    if not food_required(planet.workforce, bonuses):
        return 0
    food = report(planet, bonuses)
    output = farmer_output(planet, bonuses)
    passive = food.produced-planet.farmers*output
    # Fractional consumption can equal the final limit a billion early (Lithar).
    # Keep a surplus until actually full, while preserving ordinary allocations.
    room = max(1, food_required(food.capacity+planet.slaves, bonuses)-food.consumed)
    target = food.consumed+(min(surplus, room) if planet.population < food.capacity else 0)
    return min(planet.workforce, max(0, (target-passive+output-1)//output))


def clamp_workforce(planet):
    """Remove unavailable workers while preserving food production where possible."""
    planet.farmers = min(planet.farmers, planet.workforce)
    planet.scientists = min(planet.scientists, planet.workforce-planet.farmers)
    planet.miners = min(planet.miners, planet.workforce-planet.farmers-planet.scientists)


def liberate(planet):
    """A conquered stronghold's captives become ordinary, non-decaying citizens."""
    planet.population += planet.slaves
    planet.slaves = 0


@dataclass(frozen=True)
class PopulationReport:
    population: int
    capacity: int
    produced: int
    progress: int
    colonized: bool
    growth_limit: int = 25
    food_required: int | None = None
    growth_percent: int = 100
    assembly: bool = False
    assembly_industry: int = 0
    passive_growth: int = 0

    @property
    def consumed(self):
        return (self.population if self.food_required is None else self.food_required) if self.colonized else 0

    @property
    def balance(self):
        return self.produced-self.consumed

    @property
    def growth_rate(self):
        if not self.colonized or not 0 < self.population < self.capacity:
            return 0
        if self.assembly:
            return min(ASSEMBLY_GROWTH_LIMIT, GROWTH_PER_INDUSTRY*self.assembly_industry)
        if self.passive_growth:
            return self.passive_growth
        base = max(0, min(self.growth_limit, GROWTH_PER_FOOD*self.balance))
        return max(1, base*self.growth_percent//100) if base else 0

    @property
    def turns_to_growth(self):
        rate = self.growth_rate
        return (GROWTH_THRESHOLD-self.progress+rate-1)//rate if rate else None

    @property
    def status(self):
        if not self.colonized:
            return "Uncolonized"
        if not self.population:
            return "No inhabitants"
        if self.balance < 0:
            return "Food shortage"
        if self.population >= self.capacity:
            return "At population limit"
        if self.assembly:
            return "Assembling" if self.assembly_industry else "Needs more industry to assemble population"
        if self.passive_growth:
            return "Growing"
        if not self.balance:
            return "Needs food surplus"
        return "Growing"

    @property
    def growth_caption(self):
        turns = self.turns_to_growth
        if turns is not None:
            prefix = f"Assembly: {self.assembly_industry} industry · " if self.assembly else ""
            return f"{prefix}{self.progress*100//GROWTH_THRESHOLD}% · +1 B in {turns} {'turn' if turns == 1 else 'turns'}"
        return self.status


def report(planet, bonuses=None):
    bonuses = bonuses or {}
    produced = 0
    needs_food = 100+bonuses.get("food_use_percent", 0) > 0
    if planet.colonized and needs_food:
        produced = BASE_FOOD[planet.biome] + bonuses.get("colony_food", 0)
        if planet.biome in LUSH_BIOMES:
            produced += bonuses.get("lush_food", 0)
        produced += planet.farmers * farmer_output(planet, bonuses)
        produced += sum(BUILDINGS[b].food for b in active_buildings(planet, bonuses))
    growth = 100+bonuses.get("growth_percent", 0)
    if planet.biome in LUSH_BIOMES:
        growth += bonuses.get("lush_growth_percent", 0)
    reserved = 0
    if bonuses.get("assembly_percent") and planet.colonized:
        from .research import gross_colony_yields
        reserved = assembly_work(planet, gross_colony_yields(planet, bonuses)[0], bonuses)
    return PopulationReport(planet.population, population_capacity(planet, bonuses), produced,
                            planet.growth_progress, planet.colonized, GAIA_GROWTH_LIMIT if planet.biome == "Gaia" else GROWTH_LIMIT,
                            food_required(planet.workforce, bonuses), growth,
                            bool(bonuses.get("assembly_percent")), reserved, bonuses.get("passive_growth", 0))


def advance(planet, start):
    """Use starting food; new farms and technologies take effect next turn."""
    if not planet.colonized:
        return False
    if planet.population >= start.capacity:
        planet.growth_progress = 0
        return False
    planet.growth_progress += start.growth_rate
    if planet.growth_progress < GROWTH_THRESHOLD:
        return False
    gained, planet.growth_progress = divmod(planet.growth_progress, GROWTH_THRESHOLD)
    planet.population = min(start.capacity, planet.population+gained)
    if planet.population >= start.capacity:
        planet.growth_progress = 0
    return True
