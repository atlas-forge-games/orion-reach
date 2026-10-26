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
    # Retained for old save/profile validation. All new orders are one per colony.
    unique: bool = False
    industry_per_worker: float = 0
    research_per_scientist: int = 0
    food_per_farmer: int = 0
    income_per_population: float = 0
    resources: int = 0
    resources_per_miner: int = 0
    energy_use: int = 0
    energy_output: int = 0
    energy_per_resource: int = 0
    maintenance: int = 0
    technology: str | None = None
    special_effect: str = ""
    enabled: bool = True
    growth_bonus: int = 0
    capacity_bonus: int = 0
    adaptation: int = 0
    strain_relief: int = 0
    shield_capacity: int = 0
    interdiction_slow: int = 0
    interdiction_range: int = 0

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
            parts.append(f"up to {self.energy_output} backup energy · 1 RES/{self.energy_per_resource} energy" if self.energy_per_resource else f"+{self.energy_output} energy")
        parts = [" · ".join(parts) + " / turn"] if parts else []
        if self.growth_bonus:
            parts.append(f"+{self.growth_bonus}% local growth (all population types)")
        if self.capacity_bonus:
            parts.append(f"+{self.capacity_bonus}% local population capacity")
        if self.adaptation:
            parts.append(f"remove {self.adaptation}% of environmental growth penalty")
        if self.strain_relief:
            parts.append(f"-{self.strain_relief} percentage points of local strain")
        if self.shield_capacity:
            parts.append(f"{self.shield_capacity} planetary shield points")
        if self.interdiction_slow:
            parts.append(f"{self.interdiction_slow}% hostile slowdown within {self.interdiction_range} ly")
        return " · ".join(parts)


BUILDINGS = {
    "factory": BuildingSpec("factory", "Factory", "Base industry plus better output from every industrial worker.", 45, 24,
                            industry=4, industry_per_worker=1, energy_use=3, maintenance=2),
    "mine": BuildingSpec("mine", "Mining complex", "Base resource extraction and miner bonuses scale with mineral richness.", 30, 18,
                         resources=2, resources_per_miner=1, energy_use=2, maintenance=1),
    "trade_center": BuildingSpec("trade_center", "Trade centre", "Base credits plus income from every population unit.", 40, 24,
                                 income=4, income_per_population=.5, energy_use=1, maintenance=1),
    "research_lab": BuildingSpec("research_lab", "Research lab", "Base research plus better output from every scientist.", 50, 30,
                                 research=4, research_per_scientist=1, energy_use=4, maintenance=2),
    "robotic_factory": BuildingSpec("robotic_factory", "Robotic factory", "Automated production lines provide more industry and double the basic factory's worker bonus. Occupies its own slot; stacks with other factories.", 110, 66,
                                    industry=8, industry_per_worker=2, energy_use=6, maintenance=4, technology="planetary_automation"),
    "nanofactory": BuildingSpec("nanofactory", "Nanofactory", "Molecular assembly provides advanced industry and worker output at high power and credit cost. Occupies its own slot; stacks with other factories.", 230, 138,
                               industry=14, industry_per_worker=3, energy_use=10, maintenance=7, technology="nanostructured_materials"),
    "deep_core_mine": BuildingSpec("deep_core_mine", "Deep-core mine", "Deep shafts double the basic mine's extraction and miner bonus. Output scales with richness. Occupies its own slot; stacks with other mines.", 90, 54,
                                  resources=4, resources_per_miner=2, energy_use=5, maintenance=3, technology="deep_core_drills"),
    "automated_refinery": BuildingSpec("automated_refinery", "Automated refinery", "High-capacity mineral processing boosts extraction and every miner. Output scales with richness. Occupies its own slot; stacks with other mines.", 180, 108,
                                      resources=7, resources_per_miner=3, energy_use=8, maintenance=5, technology="automated_refineries"),
    "advanced_research_lab": BuildingSpec("advanced_research_lab", "Advanced research lab", "Precision instruments double the basic lab's research and scientist bonus. Occupies its own slot; stacks with other laboratories.", 120, 72,
                                         research=8, research_per_scientist=2, energy_use=7, maintenance=4, technology="planetary_observatories"),
    "quantum_research_lab": BuildingSpec("quantum_research_lab", "Quantum research lab", "Quantum simulations deliver advanced research and scientist output at high power and credit cost. Occupies its own slot; stacks with other laboratories.", 240, 144,
                                        research=14, research_per_scientist=3, energy_use=11, maintenance=7, technology="quantum_research_archives"),
    "hydroponic_farm": BuildingSpec("hydroponic_farm", "Hydroponic farm", "Base food plus better output from every farmer.", 30, 18,
                                    food=4, food_per_farmer=1, energy_use=2, maintenance=1),
    "barracks": BuildingSpec("barracks", "Barracks", "Trains a local garrison and enables troop transport construction. One per colony.",
                             50, 30, training=1, garrison_limit=8, unique=True, energy_use=1, maintenance=1),
    "fortifications": BuildingSpec("fortifications", "Fortifications", "Bunkers give all defending troops 50% more firepower. One per colony.",
                                   60, 36, defence_bonus=50, unique=True, energy_use=0, maintenance=2),
    "missile_base": BuildingSpec("missile_base", "Missile base", "A planetary surface battery defending orbit with 40 hull, range 8 and 10 missile damage. One per colony.",
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
    "geothermal_plant": BuildingSpec("geothermal_plant", "Geothermal plant", "Deep thermal wells provide steady local power without consuming Resources.", 55, 36,
                                    energy_output=20, maintenance=2, technology="deep_core_drills"),
    "thermal_plant": BuildingSpec("thermal_plant", "Thermal backup plant", "Burns Resources only when other generators cannot cover working buildings. Last to run; 1 Resource per 4 energy, rounded up per plant.", 35, 24,
                                 energy_output=24, energy_per_resource=4, maintenance=1, technology="fusion_grids"),
    "singularity_plant": BuildingSpec("singularity_plant", "Singularity plant", "A stabilized micro-singularity provides high continuous power without consuming Resources.", 140, 84,
                                     energy_output=50, maintenance=5, technology="field_stabilization"),
    "space_hub": BuildingSpec("space_hub", "Space Hub", "A meeting place for travelling specialists. Operational Hubs attract unique colony leaders and explorers; hire and assign them from Specialists.", 60, 36,
                              energy_use=2, maintenance=2, unique=True, special_effect="Attracts specialist visitors · empire-wide visitor limit"),
}

# Legacy buildings share normal slots, funding, power and maintenance.
from .race_victory import LEGACIES, PROJECT_RACES
for _spec in LEGACIES.values():
    BUILDINGS[_spec.building] = BuildingSpec(_spec.building, _spec.name,
        _spec.description, 300, 180, unique=True, energy_use=6, maintenance=4,
        special_effect="Civilization legacy · view Objectives for requirements")

CLASSIC_BUILDINGS = BUILDINGS.copy()
from .advanced_buildings import install as _install_facilities, NEW_BUILDINGS
_install_facilities(BuildingSpec, BUILDINGS)

BUILDING_GROUPS = (
    ("factory", "mine", "trade_center", "research_lab", "hydroponic_farm", "barracks", "fortifications"),
    ("space_hub", "missile_base", "planetary_shield", "sensor_array", "jump_gate", "interdictor", *PROJECT_RACES),
    ("solar_array", "geothermal_plant", "fusion_plant", "thermal_plant", "singularity_plant"),
    ("robotic_factory", "nanofactory", "deep_core_mine", "automated_refinery", "advanced_research_lab", "quantum_research_lab"),
)
_groups = [list(group) for group in BUILDING_GROUPS]
for _key in NEW_BUILDINGS:
    if BUILDINGS[_key].energy_output:
        _group = 2
    elif _key in ('advanced_planetary_shield', 'advanced_interdictor', 'planetary_fortress', 'administration_centre'):
        _group = 1
    else:
        _group = 3
    _groups[_group].append(_key)
BUILDING_GROUPS = tuple(tuple(group) for group in _groups)

# Facility families share research bonuses, power priority and AI preferences.
# Each distinct facility still occupies a slot and can be built once per colony.
FACILITY_FAMILIES = {
    "factory": ("factory", "advanced_factory", "construction_bureau", "robotic_factory", "superconducting_foundry", "nanofactory"),
    "mine": ("mine", "deep_core_mine", "mineral_processor", "automated_refinery"),
    "research_lab": ("research_lab", "field_lab", "analysis_lab", "scientific_institute", "research_network_hub", "advanced_research_lab", "data_centre", "data_archive", "relic_research_centre", "quantum_research_lab"),
    "hydroponic_farm": ("hydroponic_farm", "symbiotic_farm", "ecology_centre", "biosphere_restorer"),
    "trade_center": ("trade_center", "commercial_exchange", "commercial_complex"),
}
ADVANCED_FACILITIES = ("robotic_factory", "nanofactory", "deep_core_mine", "automated_refinery", "advanced_research_lab", "quantum_research_lab")


def facility_family(identifier):
    return next((base for base, family in FACILITY_FAMILIES.items() if identifier in family), identifier)


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
