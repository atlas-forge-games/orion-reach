"""Initial building balance. Rules are data so costs and capacities are easy to tune."""

from dataclasses import dataclass

BUILDING_SLOTS = {"Tiny": 4, "Small": 6, "Medium": 8, "Large": 10, "Huge": 12}
MINERAL_FACTORS = {"Poor": .5, "Average": 1.0, "Rich": 1.5}


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

    def yields(self, richness):
        factor = MINERAL_FACTORS[richness] if self.mineral_scaled else 1
        return (int(self.industry*factor), self.income, self.research)

    def effect_text(self, richness):
        industry, income, research = self.yields(richness)
        parts = []
        if industry:
            parts.append(f"+{industry} industry")
        if income:
            parts.append(f"+{income} {'credit' if income == 1 else 'credits'}")
        if research:
            parts.append(f"+{research} research")
        return " · ".join(parts) + " / turn"


BUILDINGS = {
    "factory": BuildingSpec("factory", "Factory", "Speeds up all future construction.", 45, 24, industry=4),
    "mine": BuildingSpec("mine", "Mining complex", "Industry scales with mineral richness.", 30, 18,
                         industry=2, income=1, mineral_scaled=True),
    "trade_center": BuildingSpec("trade_center", "Trade centre", "Provides a steady flow of credits.", 40, 24, income=4),
    "research_lab": BuildingSpec("research_lab", "Research lab", "Stores research for a future technology tree.", 50, 30, research=4),
}
