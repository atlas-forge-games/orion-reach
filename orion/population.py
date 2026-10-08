"""Local food balances and deterministic population growth, independent of the UI."""

from dataclasses import dataclass

from .buildings import BUILDINGS

POPULATION_LIMITS = {"Tiny": 8, "Small": 12, "Medium": 16, "Large": 20, "Huge": 24}
BASE_FOOD = {"Terran": 6, "Ocean": 4, "Desert": 0, "Tundra": 0, "Barren": 0, "Volcanic": 0}
FARMER_OUTPUT = {"Terran": 2, "Ocean": 2, "Desert": 2, "Tundra": 2, "Barren": 1, "Volcanic": 1}
WORKER_ROLES = ("farmers", "workers", "scientists")
GROWTH_THRESHOLD = 100


@dataclass(frozen=True)
class PopulationReport:
    population: int
    capacity: int
    produced: int
    progress: int
    colonized: bool

    @property
    def consumed(self):
        return self.population if self.colonized else 0

    @property
    def balance(self):
        return self.produced-self.consumed

    @property
    def growth_rate(self):
        if not self.colonized or not 0 < self.population < self.capacity:
            return 0
        return max(0, min(25, 5*self.balance))

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
        if not self.balance:
            return "Needs food surplus"
        return "Growing"

    @property
    def growth_caption(self):
        turns = self.turns_to_growth
        if turns is not None:
            return f"{self.progress}% · +1 B in {turns} {'turn' if turns == 1 else 'turns'}"
        return self.status


def report(planet, bonuses=None):
    produced = 0
    if planet.colonized:
        produced = BASE_FOOD[planet.biome] + (bonuses or {}).get("colony_food", 0)
        produced += planet.farmers * FARMER_OUTPUT[planet.biome]
        produced += sum(BUILDINGS[b].food for b in planet.buildings)
    return PopulationReport(planet.population, POPULATION_LIMITS[planet.size], produced,
                            planet.growth_progress, planet.colonized)


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
    planet.population += 1
    planet.growth_progress -= GROWTH_THRESHOLD
    if planet.population >= start.capacity:
        planet.growth_progress = 0
    return True
