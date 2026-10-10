"""Initial building balance. Rules are data so costs and capacities are easy to tune."""

from dataclasses import dataclass

BUILDING_SLOTS = {"Tiny": 4, "Small": 6, "Medium": 8, "Large": 10, "Huge": 12}
MINERAL_FACTORS = {"Poor": .5, "Average": 1.0, "Rich": 1.5, "Ultra-rich": 3.0}


@dataclass(frozen=True)
class BuildingSpec:
    id: str
    name: str
    description: str
    resource_cost: int
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
    resources: int = 0
    resources_per_miner: int = 0
    energy_use: int = 0
    energy_output: int = 0
    maintenance: int = 0
    technology: str | None = None
    special_effect: str = ""

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
        if self.resources_per_miner:
            parts.append(f"+{self.resources_per_miner*MINERAL_FACTORS[richness]:g} RES/miner")
        if self.income_per_population:
            parts.append(f"+{self.income_per_population:g} CR/pop")
        return " · ".join(parts)

    def yields(self, richness):
        factor = MINERAL_FACTORS[richness] if self.mineral_scaled else 1
        return (int(self.industry*factor), self.income, self.research)

    def effect_text(self, richness):
        if self.special_effect:
            return self.special_effect
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
        if self.resources:
            parts.append(f"+{self.resources*MINERAL_FACTORS[richness]:g} resources")
        if self.energy_output:
            parts.append(f"+{self.energy_output} energy")
        return " · ".join(parts) + " / turn"


BUILDINGS = {
    "factory": BuildingSpec("factory", "Factory", "Base industry plus better output from every industrial worker.", 45, 24,
                            industry=4, industry_per_worker=1, energy_use=3, maintenance=2),
    "mine": BuildingSpec("mine", "Mining complex", "Base resource extraction and miner bonuses scale with mineral richness.", 30, 18,
                         resources=2, resources_per_miner=1, energy_use=2, maintenance=1),
    "trade_center": BuildingSpec("trade_center", "Trade centre", "Base credits plus income from every population unit.", 40, 24,
                                 income=4, income_per_population=.5, energy_use=1, maintenance=1),
    "research_lab": BuildingSpec("research_lab", "Research lab", "Base research plus better output from every scientist.", 50, 30,
                                 research=4, research_per_scientist=1, energy_use=4, maintenance=2),
    "hydroponic_farm": BuildingSpec("hydroponic_farm", "Hydroponic farm", "Base food plus better output from every farmer.", 30, 18,
                                    food=4, food_per_farmer=1, energy_use=2, maintenance=1),
    "barracks": BuildingSpec("barracks", "Barracks", "Trains a local garrison and enables troop transport construction. One per colony.",
                             50, 30, training=1, garrison_limit=8, unique=True, energy_use=1, maintenance=1),
    "fortifications": BuildingSpec("fortifications", "Fortifications", "Bunkers give all defending troops 50% more firepower. One per colony.",
                                   60, 36, defence_bonus=50, unique=True, energy_use=0, maintenance=2),
    "missile_base": BuildingSpec("missile_base", "Missile base", "An immobile orbital defender with 40 hull, range 8 and 10 missile damage. One per colony.",
                                100, 60, unique=True, energy_use=3, maintenance=3, technology="orbital_defense_systems", special_effect="40 hull · 10 missile damage · range 8"),
    "planetary_shield": BuildingSpec("planetary_shield", "Planetary shield", "Blocks hostile landings while charged. Regenerates 25 points each peaceful turn. Barrier Fields improves capacity and upkeep.",
                                    120, 70, unique=True, energy_use=8, maintenance=4, technology="planetary_shielding", special_effect="100 shield points · 25 recovery/turn"),
    "sensor_array": BuildingSpec("sensor_array", "Sensor array", "Extends this system's researched detection radius by 5 ly. Multiple arrays in one system do not stack.",
                                60, 36, unique=True, energy_use=3, maintenance=2, technology="deep_space_radar", special_effect="+5 ly local sensor range"),
    "jump_gate": BuildingSpec("jump_gate", "Jump gate", "Connect two of your colonies for +50% travel speed on new orders. Replaces the navigation network bonus.",
                             140, 84, unique=True, energy_use=8, maintenance=4, technology="jump_gates", special_effect="+50% speed between friendly gates"),
    "interdictor": BuildingSpec("interdictor", "Interdiction generator", "Slows hostile approaches within 5 ly by 25%. Subspace Interdiction improves the radius and strength.",
                               110, 66, unique=True, energy_use=8, maintenance=3, technology="gravity_wells", special_effect="25% hostile slowdown within 5 ly"),
    "solar_array": BuildingSpec("solar_array", "Solar array", "Generates local power without fuel or assigned workers.", 30, 18,
                               energy_output=12, maintenance=1),
    "fusion_plant": BuildingSpec("fusion_plant", "Fusion plant", "A compact reactor supplies substantial local power. No fuel resource required.", 80, 48,
                                energy_output=30, maintenance=3, technology="fusion_power"),
}


@dataclass(frozen=True)
class WorkforceBonuses:
    industry: float
    food: int
    research: int
    income: float


def workforce_bonuses(planet, bonuses=None):
    """Add bonuses from completed buildings; fractions are rounded after summing."""
    from .economy import active_buildings
    buildings = [BUILDINGS[b] for b in active_buildings(planet, bonuses)]
    return WorkforceBonuses(sum(b.worker_bonus(planet.richness) for b in buildings),
                           sum(b.food_per_farmer for b in buildings),
                           sum(b.research_per_scientist for b in buildings),
                           sum(b.income_per_population for b in buildings))
