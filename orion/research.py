"""The technology catalogue and exclusive, sequential research choices."""

from dataclasses import dataclass, field
from functools import lru_cache
from .buildings import BUILDINGS
from .population import LUSH_BIOMES, assembly_work


@dataclass(frozen=True)
class Branch:
    id: str
    name: str
    description: str


BRANCHES = {b.id: b for b in (
    Branch("construction", "Construction", "Build productive colonies and efficient shipyards."),
    Branch("power", "Power & Propulsion", "Choose faster voyages or stronger planetary power grids."),
    Branch("physics", "Physics", "Advance research instruments and beam weapons."),
    Branch("fields", "Force Fields", "Protect settlements and work in hostile environments."),
    Branch("materials", "Materials & Chemistry", "Improve extraction, fuel tanks and construction materials."),
    Branch("biology", "Biology", "Support larger expeditions and more prosperous colonies."),
    Branch("computers", "Computers", "Connect laboratories, automate industry and optimize trade."),
    Branch("society", "Society", "Strengthen administration, commerce and cooperation."),
)}


@dataclass(frozen=True)
class Technology:
    id: str
    branch: str
    tier: int
    name: str
    description: str
    effects: tuple[tuple[str, int], ...]

    @property
    def cost(self):
        return (40, 100, 500)[self.tier-1]


def tech(identifier, branch, tier, name, description, **effects):
    return Technology(identifier, branch, tier, name, description, tuple(effects.items()))


TECHNOLOGIES = {t.id: t for t in (
    tech("automated_factories", "construction", 1, "Automated Factories", "+2 industry per factory.", factory_industry=2),
    tech("civil_engineering", "construction", 1, "Civil Engineering", "+2 industry per colony.", colony_industry=2),
    tech("prefabricated_structures", "construction", 2, "Prefabricated Structures", "New building orders cost 20% fewer credits.", building_discount=20),
    tech("orbital_assembly", "construction", 2, "Orbital Assembly", "New ship orders cost 20% fewer credits.", ship_discount=20),
    tech("ion_drives", "power", 1, "Ion Drives", "+25% ship speed on newly ordered voyages. Unlock maneuvering thrusters in the ship designer.", ship_speed=25),
    tech("compact_reactors", "power", 1, "Compact Reactors", "+1 industry and +1 credit per colony.", colony_industry=1, colony_income=1),
    tech("fusion_drives", "power", 2, "Fusion Drives", "+50% ship speed on newly ordered voyages.", ship_speed=50),
    tech("fusion_grids", "power", 2, "Fusion Grids", "+2 industry per factory.", factory_industry=2),
    tech("research_instruments", "physics", 1, "Research Instruments", "+2 research per laboratory.", lab_research=2),
    tech("field_laboratories", "physics", 1, "Field Laboratories", "+1 research per colony.", colony_research=1),
    tech("planetary_observatories", "physics", 2, "Planetary Observatories", "+3 research per colony.", colony_research=3),
    tech("quantum_optics", "physics", 2, "Quantum Optics", "+3 research per laboratory. Standard frigates gain 7-damage beams. Unlock 14-damage quantum batteries for new designs.", lab_research=3, beam_level=1),
    tech("radiation_shields", "fields", 1, "Radiation Shields", "Colony ships can settle barren worlds. Unlock ship shield generators (+12 shields per module).", barren=1),
    tech("habitat_shields", "fields", 1, "Habitat Shields", "+2 credits per desert or tundra colony.", rough_income=2),
    tech("thermal_barriers", "fields", 2, "Thermal Barriers", "Colony ships can settle volcanic worlds.", volcanic=1),
    tech("industrial_force_fields", "fields", 2, "Industrial Force Fields", "+2 industry per mine, regardless of mineral richness.", mine_industry=2),
    tech("deep_core_drills", "materials", 1, "Deep Core Drills", "+2 industry per mine, regardless of mineral richness.", mine_industry=2),
    tech("lightweight_alloys", "materials", 1, "Lightweight Alloys", "Lighter fuel tanks: +10 ly range. New ships cost 10% fewer credits.", ship_discount=10, fuel_range=10),
    tech("superconductors", "materials", 2, "Superconductors", "+1 industry per colony and +2 research per laboratory.", colony_industry=1, lab_research=2),
    tech("composite_structures", "materials", 2, "Composite Structures", "Advanced fuel tanks: +15 ly range. New buildings cost 15% fewer credits.", building_discount=15, fuel_range=15),
    tech("colony_biospheres", "biology", 1, "Colony Biospheres", "New colonies start with 1 billion additional inhabitants.", colonists=1),
    tech("symbiotic_farming", "biology", 1, "Symbiotic Farming", "+2 food and +2 credits per colony.", colony_food=2, colony_income=2),
    tech("colony_biogenesis", "biology", 2, "Colony Biogenesis", "New colonies start with 2 billion additional inhabitants.", colonists=2),
    tech("ecology_networks", "biology", 2, "Ecology Networks", "+1 credit per 2 billion inhabitants on each colony.", income_per_two_pop=1),
    tech("research_networks", "computers", 1, "Research Networks", "+1 research per colony and per laboratory. Unlock combat scanners (+1 weapon range).", colony_research=1, lab_research=1),
    tech("trade_algorithms", "computers", 1, "Trade Algorithms", "+2 credits per trade center.", trade_income=2),
    tech("distributed_computing", "computers", 2, "Distributed Computing", "+2 research per colony.", colony_research=2),
    tech("planetary_automation", "computers", 2, "Planetary Automation", "+1 industry per factory and per mine.", factory_industry=1, mine_industry=1),
    tech("colonial_administration", "society", 1, "Colonial Administration", "+2 credits per colony.", colony_income=2),
    tech("scientific_institutes", "society", 1, "Scientific Institutes", "+1 research per colony.", colony_research=1),
    tech("commerce_guilds", "society", 2, "Commerce Guilds", "+3 credits per trade center.", trade_income=3),
    tech("cultural_exchange", "society", 2, "Cultural Exchange", "Your active trade pact earns +3 credits; your research pact earns +3 research.", pact_income=3, pact_research=3),
    tech("ascension_theory", "ascension", 3, "Ascension Theory", "Unlock the Ascension Gate and a scientific victory."),
)}


def choices(branch, tier):
    return tuple(t for t in TECHNOLOGIES.values() if t.branch == branch and t.tier == tier)


@lru_cache(maxsize=512)
def _bonuses(completed):
    result = {}
    for identifier in completed:
        for effect, amount in TECHNOLOGIES[identifier].effects:
            result[effect] = result.get(effect, 0)+amount
    return result


@dataclass
class ResearchState:
    completed: list[str] = field(default_factory=list)
    active: str | None = None
    progress: int = 0

    @property
    def bonuses(self):
        return _bonuses(tuple(sorted(self.completed))).copy()

    def status(self, identifier):
        technology = TECHNOLOGIES[identifier]
        if identifier in self.completed:
            return "discovered"
        if identifier == self.active:
            return "active"
        if identifier == "ascension_theory":
            return "available" if self.finished_branches == len(BRANCHES) else "locked"
        committed = self.completed + ([self.active] if self.active else [])
        if any(TECHNOLOGIES[t].branch == technology.branch and
               TECHNOLOGIES[t].tier == technology.tier for t in committed):
            return "excluded"
        if technology.tier > 1 and not any(
                TECHNOLOGIES[t].branch == technology.branch and
                TECHNOLOGIES[t].tier == technology.tier-1 for t in self.completed):
            return "locked"
        return "available"

    @property
    def finished_branches(self):
        return sum(TECHNOLOGIES[t].tier == 2 for t in self.completed)

    def choice_error(self, identifier):
        if not isinstance(identifier, str) or identifier not in TECHNOLOGIES:
            return "Unknown technology."
        status = self.status(identifier)
        if status == "discovered":
            return "This technology has already been discovered."
        if status == "excluded":
            return "You chose the other technology in this tier."
        if status == "locked":
            if identifier == "ascension_theory":
                return "Complete tier II in all eight research branches first."
            return "Complete the previous tier in this branch first."
        if self.active:
            return "Finish your current research project first."
        return None

    def spend(self, bank):
        """Apply banked points to one committed project; retain all overflow."""
        if self.active is None:
            return bank, None
        technology = TECHNOLOGIES[self.active]
        used = min(bank, technology.cost-self.progress)
        self.progress += used
        if self.progress < technology.cost:
            return bank-used, None
        self.completed.append(self.active)
        self.active, self.progress = None, 0
        return bank-used, technology

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or set(data) != {"completed", "active", "progress"}:
            raise ValueError("Invalid research state")
        completed, active, progress = data["completed"], data["active"], data["progress"]
        if not isinstance(completed, list) or len(completed) > 17:
            raise ValueError("Invalid discoveries")
        state = cls()
        for identifier in completed:
            if state.choice_error(identifier):
                raise ValueError("Invalid technology sequence")
            state.completed.append(identifier)
        if type(progress) is not int or progress < 0:
            raise ValueError("Invalid research progress")
        if active is None:
            if progress != 0:
                raise ValueError("Progress without a project")
        elif state.choice_error(active) or progress >= TECHNOLOGIES[active].cost:
            raise ValueError("Invalid active technology")
        state.active, state.progress = active, progress
        return state


def building_yields(definition, richness, bonuses):
    industry, income, research = definition.yields(richness)
    industry += bonuses.get({"factory": "factory_industry", "mine": "mine_industry"}.get(definition.id), 0)
    income += bonuses.get("trade_income", 0) if definition.id == "trade_center" else 0
    research += bonuses.get("lab_research", 0) if definition.id == "research_lab" else 0
    return industry, income, research


def scaled_output(value, percent):
    """Round bonuses up and penalties down; do not create output from zero."""
    return (value*(100+percent)+(99 if percent > 0 else 0))//100


def gross_colony_yields(planet, bonuses):
    if not planet.colonized:
        return 0, 0, 0
    industry = max(1, planet.workers)+bonuses.get("colony_industry", 0)
    income = planet.workforce+bonuses.get("colony_income", 0)
    research = 2*planet.scientists+bonuses.get("colony_research", 0)
    for identifier in planet.buildings:
        extra = building_yields(BUILDINGS[identifier], planet.richness, bonuses)
        industry, income, research = industry+extra[0], income+extra[1], research+extra[2]
    income += (planet.workforce//2)*bonuses.get("income_per_two_pop", 0)
    if planet.biome in ("Desert", "Tundra"):
        income += bonuses.get("rough_income", 0)
    industry_percent = bonuses.get("industry_percent", 0)
    if planet.biome not in LUSH_BIOMES:
        industry_percent += bonuses.get("harsh_industry_percent", 0)
    return (max(1, scaled_output(industry, industry_percent)),
            scaled_output(income, bonuses.get("income_percent", 0)),
            scaled_output(research, bonuses.get("research_percent", 0)))


def colony_yields(planet, bonuses):
    industry, income, research = gross_colony_yields(planet, bonuses)
    return industry-assembly_work(planet, industry, bonuses), income, research
