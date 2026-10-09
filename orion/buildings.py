"""Initial building balance. Rules are data so costs and capacities are easy to tune."""

from dataclasses import dataclass

BUILDING_SLOTS = {"Tiny": 4, "Small": 6, "Medium": 8, "Large": 10, "Huge": 12}
MINERAL_FACTORS = {"Poor": .5, "Average": 1.0, "Rich": 1.5, "Ultra-rich": 3.0}


@dataclass(frozen=True)
class BuildingSpec:
    id: str
    name: str
    description: str
    credit_cost: int
    work_cost: int
    industry: int = 0
    income: int = 0
    research: int = 0
    mineral_scaled: bool = False
    food: int = 0
    training: int = 0
    garrison_limit: int = 0
    defence_bonus: int = 0
    unique: bool = False
    industry_per_worker: float = 0
    research_per_scientist: int = 0
    food_per_farmer: int = 0
    income_per_population: float = 0
    maintenance: int = 0

    def worker_bonus(self, richness):
        return self.industry_per_worker*(MINERAL_FACTORS[richness] if self.mineral_scaled else 1)

    def workforce_text(self, richness):
        parts = []
        if self.industry_per_worker:
            parts.append(f"+{self.worker_bonus(richness):g} IND/worker")
        if self.research_per_scientist:
            parts.append(f"+{self.research_per_scientist} RP/scientist")
        if self.food_per_farmer:
            parts.append(f"+{self.food_per_farmer} food/farmer")
        if self.income_per_population:
            parts.append(f"+{self.income_per_population:g} CR/pop")
        return " · ".join(parts)

    def yields(self, richness):
        factor = MINERAL_FACTORS[richness] if self.mineral_scaled else 1
        return (int(self.industry*factor), self.income, self.research)

    def effect_text(self, richness):
        if self.training:
            return f"+{self.training} garrison troop / turn · trains up to {self.garrison_limit}"
        if self.defence_bonus:
            return f"+{self.defence_bonus}% defending firepower"
        industry, income, research = self.yields(richness)
        parts = []
        if industry:
            parts.append(f"+{industry} industry")
        if income:
            parts.append(f"+{income} {'credit' if income == 1 else 'credits'}")
        if research:
            parts.append(f"+{research} research")
        if self.food:
            parts.append(f"+{self.food} food")
        return " · ".join(parts) + " / turn"


BUILDINGS = {
    "factory": BuildingSpec("factory", "Factory", "Base industry plus better output from every industrial worker.", 45, 24,
                            industry=4, industry_per_worker=1, maintenance=2),
    "mine": BuildingSpec("mine", "Mining complex", "Base and worker industry scale with mineral richness.", 30, 18,
                         industry=2, income=1, mineral_scaled=True, industry_per_worker=.5, maintenance=1),
    "trade_center": BuildingSpec("trade_center", "Trade centre", "Base credits plus income from every population unit.", 40, 24,
                                 income=4, income_per_population=.5, maintenance=1),
    "research_lab": BuildingSpec("research_lab", "Research lab", "Base research plus better output from every scientist.", 50, 30,
                                 research=4, research_per_scientist=1, maintenance=2),
    "hydroponic_farm": BuildingSpec("hydroponic_farm", "Hydroponic farm", "Base food plus better output from every farmer.", 30, 18,
                                    food=4, food_per_farmer=1, maintenance=1),
    "barracks": BuildingSpec("barracks", "Barracks", "Trains a local garrison and enables troop transport construction. One per colony.",
                             50, 30, training=1, garrison_limit=8, unique=True, maintenance=1),
    "fortifications": BuildingSpec("fortifications", "Fortifications", "Bunkers give all defending troops 50% more firepower. One per colony.",
                                   60, 36, defence_bonus=50, unique=True, maintenance=2),
}


@dataclass(frozen=True)
class WorkforceBonuses:
    industry: float
    food: int
    research: int
    income: float


def workforce_bonuses(planet):
    """Add bonuses from completed buildings; fractions are rounded after summing."""
    buildings = [BUILDINGS[b] for b in planet.buildings] if planet.colonized else []
    return WorkforceBonuses(sum(b.worker_bonus(planet.richness) for b in buildings),
                           sum(b.food_per_farmer for b in buildings),
                           sum(b.research_per_scientist for b in buildings),
                           sum(b.income_per_population for b in buildings))
