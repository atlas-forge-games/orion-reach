"""The technology catalogue and exclusive, sequential research choices."""

from dataclasses import dataclass, field
from functools import lru_cache
from .buildings import BUILDINGS, workforce_bonuses
from .production import ASCENSION_GATE, HULL_TECHNOLOGIES
from .population import LUSH_BIOMES, assembly_work
from .economy import active_buildings
from .legacy_research import LEGACY_TECHNOLOGIES, validate_legacy


TIERS = (1, 2, 3, 4, 5)
TIER_NAMES = ("I", "II", "III", "IV", "V")


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
    Branch("starships", "Starship Engineering", "Research new hull classes or specialize fleet production and range."),
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
        return 500 if self.id == "ascension_theory" else (40, 100, 120, 220, 360)[self.tier-1]


def tech(identifier, branch, tier, name, description, **effects):
    return Technology(identifier, branch, tier, name, description, tuple(effects.items()))


TECHNOLOGIES = {t.id: t for t in (
    tech("automated_factories", "construction", 1, "Automated Factories", "+2 industry per factory.", factory_industry=2),
    tech("civil_engineering", "construction", 1, "Civil Engineering", "+2 industry per colony.", colony_industry=2),
    tech("prefabricated_structures", "construction", 2, "Prefabricated Structures", "New building orders cost 20% fewer resources.", building_discount=20),
    tech("orbital_assembly", "construction", 2, "Orbital Assembly", "New ship orders cost 20% fewer resources.", ship_discount=20),
    tech("ion_drives", "power", 1, "Ion Drives", "+25% ship speed on newly ordered voyages. Unlock maneuvering thrusters in the ship designer.", ship_speed=25),
    tech("compact_reactors", "power", 1, "Compact Reactors", "+1 industry, +1 credit and +4 energy per colony.", colony_industry=1, colony_income=1, colony_energy=4),
    tech("fusion_drives", "power", 2, "Fusion Drives", "+50% ship speed on newly ordered voyages.", ship_speed=50),
    tech("fusion_grids", "power", 2, "Fusion Grids", "+2 industry per factory and +8 energy per colony. Unlock thermal backup plants: up to 24 energy; burn Resources only when needed.", factory_industry=2, colony_energy=8),
    tech("research_instruments", "physics", 1, "Research Instruments", "+2 research per laboratory.", lab_research=2),
    tech("field_laboratories", "physics", 1, "Field Laboratories", "+1 research per colony.", colony_research=1),
    tech("planetary_observatories", "physics", 2, "Planetary Observatories", "+3 research per colony.", colony_research=3),
    tech("quantum_optics", "physics", 2, "Quantum Optics", "+3 research per laboratory. Standard frigates and carriers gain 7-damage beams. Unlock 14-damage quantum batteries for new designs.", lab_research=3, beam_level=1),
    tech("radiation_shields", "fields", 1, "Radiation Shields", "Colony ships can settle barren worlds. Unlock ship shield generators (+12 shields per module).", barren=1),
    tech("habitat_shields", "fields", 1, "Habitat Shields", "+2 credits per desert or tundra colony.", rough_income=2),
    tech("thermal_barriers", "fields", 2, "Thermal Barriers", "Colony ships can settle volcanic worlds.", volcanic=1),
    tech("industrial_force_fields", "fields", 2, "Industrial Force Fields", "+2 resources per operational mine, regardless of mineral richness.", mine_resources=2),
    tech("deep_core_drills", "materials", 1, "Deep Core Drills", "+2 resources per operational mine, regardless of richness. Unlock geothermal plants: +20 energy, 2 CR/turn upkeep.", mine_resources=2),
    tech("lightweight_alloys", "materials", 1, "Lightweight Alloys", "Lighter fuel tanks: +10 ly range. New ships cost 10% fewer resources.", ship_discount=10, fuel_range=10),
    tech("superconductors", "materials", 2, "Superconductors", "+1 industry per colony and +2 research per laboratory.", colony_industry=1, lab_research=2),
    tech("composite_structures", "materials", 2, "Composite Structures", "Advanced fuel tanks: +15 ly range. New buildings cost 15% fewer resources.", building_discount=15, fuel_range=15),
    tech("colony_biospheres", "biology", 1, "Colony Biospheres", "New colonies start with 1 billion additional inhabitants.", colonists=1),
    tech("symbiotic_farming", "biology", 1, "Symbiotic Farming", "+2 food and +2 credits per colony.", colony_food=2, colony_income=2),
    tech("colony_biogenesis", "biology", 2, "Colony Biogenesis", "New colonies start with 2 billion additional inhabitants.", colonists=2),
    tech("ecology_networks", "biology", 2, "Ecology Networks", "+1 credit per 2 billion inhabitants on each colony.", income_per_two_pop=1),
    tech("research_networks", "computers", 1, "Research Networks", "+1 research per colony and per laboratory. Unlock combat scanners (+1 weapon range).", colony_research=1, lab_research=1),
    tech("trade_algorithms", "computers", 1, "Trade Algorithms", "+2 credits per trade center.", trade_income=2),
    tech("distributed_computing", "computers", 2, "Distributed Computing", "+2 research per colony.", colony_research=2),
    tech("planetary_automation", "computers", 2, "Planetary Automation", "+1 industry per factory and +1 resource per operational mine.", factory_industry=1, mine_resources=1),
    tech("colonial_administration", "society", 1, "Colonial Administration", "+2 credits per colony.", colony_income=2),
    tech("scientific_institutes", "society", 1, "Scientific Institutes", "+1 research per colony.", colony_research=1),
    tech("commerce_guilds", "society", 2, "Commerce Guilds", "+3 credits per trade center.", trade_income=3),
    tech("cultural_exchange", "society", 2, "Cultural Exchange", "Your active trade pact earns +3 credits; your research pact earns +3 research.", pact_income=3, pact_research=3),
    tech("ascension_theory", "ascension", 3, "Ascension Theory", "Unlock the Ascension Gate and a scientific victory."),
    tech("advanced_fortifications", "construction", 3, "Advanced Fortifications", "Fortifications gain +25 percentage points of defending firepower.", fortification_bonus=25),
    tech("fusion_power", "power", 3, "Fusion Power", "Unlock fusion plants: +30 local energy per plant, with 3 CR/turn upkeep."),
    tech("colonial_navigation", "power", 3, "Colonial Navigation Network", "+25% travel speed between your own colonized systems.", colony_speed=25),
    tech("jump_gates", "power", 4, "Jump Gates", "Unlock jump gates. Gates at both endpoints give +50% internal travel speed, replacing any navigation bonus."),
    tech("field_stabilization", "power", 4, "Field Stabilization", "Halve hostile interdiction slowdown. Unlock singularity plants: +50 energy with 5 CR/turn upkeep and no Resource fuel.", field_stabilization=1),
    tech("orbital_defense_systems", "construction", 3, "Orbital Defense Systems", "Unlock missile bases: immobile defenders in fleet battles, with 40 hull and 10-damage missiles."),
    tech("precision_beam_optics", "physics", 3, "Precision Beam Optics", "Halve the accuracy penalty for firing beam weapons at long range.", beam_precision=1),
    tech("siege_weapons", "physics", 4, "Siege Weapons", "Unlock siege cannons: triple damage to planetary shields and missile bases. Standard warships gain double bombardment damage.", siege_bonus=100),
    tech("torpedo_guidance", "physics", 4, "Advanced Torpedo Guidance", "Halve target evasion against torpedoes and missiles. Point defense still intercepts successful hits.", torpedo_guidance=1),
    tech("planetary_shielding", "fields", 3, "Planetary Shielding", "Unlock 100-point planetary shield generators. Suppress the shield before landing troops.", shield_capacity=100),
    tech("gravity_wells", "fields", 3, "Gravity-Well Generators", "Unlock interdiction generators: hostile final approaches slow by 25% within 5 ly.", interdiction_slow=25, interdiction_range=5),
    tech("barrier_fields", "fields", 4, "Barrier Fields", "Unlock or upgrade planetary generators to 200 shield points, with 6 CR/turn upkeep.", shield_capacity=200, shield_upkeep=2),
    tech("subspace_interdiction", "fields", 4, "Subspace Interdiction", "Unlock or upgrade interdiction generators: 40% slowdown within 8 ly, with 5 CR/turn upkeep.", interdiction_slow=40, interdiction_range=8, interdiction_upkeep=2),
    tech("electronic_countermeasures", "physics", 3, "Electronic Countermeasures", "Your ships gain 10 percentage points of evasion.", evasion=10),
    tech("deep_space_radar", "computers", 3, "Deep-Space Radar", "Detect fleet positions and owners within 5 ly of colonies. Unlock sensor arrays (+5 ly locally).", sensor_range=5, sensor_level=1),
    tech("targeting_computers", "computers", 3, "Targeting Computers", "+10 percentage points to weapon hit chance from targeting computers.", targeting_accuracy=10),
    tech("long_range_sensors", "computers", 4, "Long-Range Sensors", "Detect fleets within 10 ly and reveal ship counts. Unlock sensor arrays. Replaces earlier sensor range.", sensor_range=10, sensor_level=2),
    tech("predictive_fire_control", "computers", 4, "Predictive Fire Control", "+20 percentage points to weapon hit chance from targeting computers. Replaces earlier targeting bonuses.", targeting_accuracy=20),
    tech("subspace_scanners", "computers", 5, "Subspace Scanners", "Detect fleets within 20 ly; reveal classes and movement direction. Unlock sensor arrays. Replaces earlier sensor range.", sensor_range=20, sensor_level=3),
    tech("quantum_targeting", "computers", 5, "Quantum Targeting", "+30 percentage points to weapon hit chance from targeting computers. Replaces earlier targeting bonuses.", targeting_accuracy=30),
    tech("destroyer_hulls", "starships", 1, "Destroyer Hulls", "Unlock destroyers: agile torpedo warships. Build the standard class or create a custom design."),
    tech("modular_spaceframes", "starships", 1, "Modular Spaceframes", "New ships cost 10% fewer Resources. Does not unlock destroyers.", ship_discount=10),
    tech("cruiser_hulls", "starships", 2, "Cruiser Hulls", "Unlock cruisers: versatile warships with eight module spaces. Does not unlock skipped hull classes."),
    tech("deep_space_logistics", "starships", 2, "Deep-Space Logistics", "+5 ly fuel range for your fleets. Does not unlock cruisers.", fuel_range=5),
    tech("battleship_hulls", "starships", 3, "Battleship Hulls", "Unlock battleships: heavy gun platforms with twelve module spaces. Drone carriers are the alternative choice."),
    tech("drone_carriers", "starships", 3, "Drone Carriers", "Unlock carrier hulls and drone bays. Each bay supports two active drones and four launches per battle. Battleships are the alternative choice."),
    tech("titan_hulls", "starships", 4, "Titan Hulls", "Unlock titans: massive capital ships with eighteen module spaces. Does not unlock skipped hull classes."),
    tech("mass_ship_production", "starships", 4, "Mass Ship Production", "New ships cost 20% fewer Resources. Does not unlock titans.", ship_discount=20),
)}


def branch_tiers(branch):
    return tuple(sorted({t.tier for t in TECHNOLOGIES.values() if t.branch == branch}))


def choices(branch, tier):
    return tuple(t for t in TECHNOLOGIES.values() if t.branch == branch and t.tier == tier)


@lru_cache(maxsize=512)
def _bonuses(completed):
    result = {}
    upgrades = {"shield_capacity", "sensor_range", "sensor_level", "interdiction_slow",
                "interdiction_range", "targeting_accuracy"}
    for identifier in completed:
        for effect, amount in TECHNOLOGIES[identifier].effects:
            result[effect] = max(result.get(effect, 0), amount) if effect in upgrades else result.get(effect, 0)+amount
    if "targeting_accuracy" in result:
        result["accuracy"] = result.get("accuracy", 0)+result.pop("targeting_accuracy")
    return result


@dataclass
class ResearchState:
    completed: list[str] = field(default_factory=list)
    active: str | None = None
    progress: int = 0
    # The validated old discovery prefix may contain both choices or skipped tiers.
    legacy_count: int = 0
    legacy_active: bool = False
    # Earlier campaigns keep cruiser/battleship access and their eight-branch victory goal.
    legacy_starships: bool = False

    @property
    def bonuses(self):
        return _bonuses(tuple(sorted(self.completed))).copy()

    @property
    def project_cost(self):
        if self.active is None:
            return 0
        return LEGACY_TECHNOLOGIES[self.active][2] if self.legacy_active else TECHNOLOGIES[self.active].cost

    def has_unlock(self, identifier):
        upgrades = {
            "planetary_shielding": ("barrier_fields",),
            "gravity_wells": ("subspace_interdiction",),
            "deep_space_radar": ("long_range_sensors", "subspace_scanners"),
        }
        return any(t in self.completed for t in (identifier, *upgrades.get(identifier, ())))

    def hull_unlocked(self, kind):
        technology = HULL_TECHNOLOGIES.get(kind)
        return (technology is None or technology in self.completed
                or (self.legacy_starships and kind in ("cruiser", "battleship")))

    @property
    def required_branches(self):
        return tuple(b for b in BRANCHES if not (self.legacy_starships and b == "starships"))

    def completed_tiers(self, branch):
        return {TECHNOLOGIES[t].tier for t in self.completed if TECHNOLOGIES[t].branch == branch}

    def next_tier(self, branch):
        if self.active and TECHNOLOGIES[self.active].branch == branch:
            return TECHNOLOGIES[self.active].tier
        completed = self.completed_tiers(branch)
        tiers = branch_tiers(branch)
        return next((tier for tier in tiers if tier not in completed), tiers[-1])

    def status(self, identifier):
        technology = TECHNOLOGIES[identifier]
        if identifier in self.completed:
            return "discovered"
        if identifier == self.active:
            return "active"
        if identifier == "ascension_theory":
            return "available" if self.finished_branches == len(self.required_branches) else "locked"
        committed = self.completed + ([self.active] if self.active else [])
        if any(TECHNOLOGIES[t].branch == technology.branch and
               TECHNOLOGIES[t].tier == technology.tier for t in committed):
            return "excluded"
        if not set(range(1, technology.tier)) <= self.completed_tiers(technology.branch):
            return "locked"
        return "available"

    @property
    def finished_branches(self):
        return sum(set(branch_tiers(branch)) <= self.completed_tiers(branch) for branch in self.required_branches)

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
                return f"Complete every tier in all {len(self.required_branches)} required research branches first."
            return "Complete the earlier tiers in this branch first."
        if self.active:
            return "Finish your current research project first."
        return None

    def spend(self, bank):
        """Apply banked points to one committed project; retain all overflow."""
        if self.active is None:
            return bank, None
        technology = TECHNOLOGIES[self.active]
        cost = self.project_cost
        used = min(bank, cost-self.progress)
        self.progress += used
        if self.progress < cost:
            return bank-used, None
        self.completed.append(self.active)
        if self.legacy_active:
            self.legacy_count += 1
            self.legacy_active = False
        self.active, self.progress = None, 0
        return bank-used, technology

    @classmethod
    def from_dict(cls, data, *, version=29):
        keys = {"completed", "active", "progress"}
        if version >= 28:
            keys |= {"legacy_count", "legacy_active"}
        if version >= 29:
            keys.add("legacy_starships")
        if not isinstance(data, dict) or set(data) != keys:
            raise ValueError("Invalid research state")
        completed, active, progress = data["completed"], data["active"], data["progress"]
        if version < 28:
            validate_legacy(completed, active, progress)
            return cls(completed.copy(), active, progress, len(completed), active is not None, True)
        if not isinstance(completed, list) or len(completed) > len(TECHNOLOGIES):
            raise ValueError("Invalid discoveries")
        count, legacy_active = data["legacy_count"], data["legacy_active"]
        if type(count) is not int or not 0 <= count <= len(completed) or type(legacy_active) is not bool:
            raise ValueError("Invalid legacy research")
        validate_legacy(completed[:count])
        legacy_starships = data["legacy_starships"] if version >= 29 else True
        if type(legacy_starships) is not bool:
            raise ValueError("Invalid legacy hull access")
        state = cls(completed[:count], legacy_count=count, legacy_starships=legacy_starships)
        for identifier in completed[count:]:
            if state.choice_error(identifier):
                raise ValueError("Invalid technology sequence")
            state.completed.append(identifier)
        if type(progress) is not int or progress < 0:
            raise ValueError("Invalid research progress")
        if legacy_active:
            if active is None or count != len(completed):
                raise ValueError("Invalid legacy project")
            validate_legacy(completed, active, progress)
        elif active is None:
            if progress != 0:
                raise ValueError("Progress without a project")
        elif state.choice_error(active) or progress >= TECHNOLOGIES[active].cost:
            raise ValueError("Invalid active technology")
        state.active, state.progress = active, progress
        state.legacy_active = legacy_active
        return state


def building_yields(definition, richness, bonuses):
    industry, income, research = definition.yields(richness)
    industry += bonuses.get("factory_industry", 0) if definition.id == "factory" else 0
    income += bonuses.get("trade_income", 0) if definition.id == "trade_center" else 0
    research += bonuses.get("lab_research", 0) if definition.id == "research_lab" else 0
    return industry, income, research


def scaled_output(value, percent):
    """Round bonuses up and penalties down; do not create output from zero."""
    return (value*(100+percent)+(99 if percent > 0 else 0))//100


def gross_colony_yields(planet, bonuses):
    if not planet.colonized:
        return 0, 0, 0
    staff = workforce_bonuses(planet, bonuses)
    industry = max(1, planet.workers)+int(planet.workers*staff.industry)+bonuses.get("colony_industry", 0)
    income = planet.workforce+int(planet.workforce*staff.income)+bonuses.get("colony_income", 0)
    research = (2+staff.research)*planet.scientists+bonuses.get("colony_research", 0)
    for identifier in active_buildings(planet, bonuses):
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


def building_maintenance(identifier, bonuses=None):
    bonuses = bonuses or {}
    extra = bonuses.get("shield_upkeep", 0) if identifier == "planetary_shield" else bonuses.get("interdiction_upkeep", 0) if identifier == "interdictor" else 0
    return BUILDINGS[identifier].maintenance+extra


def colony_maintenance(planet, bonuses=None):
    if not planet.colonized:
        return 0
    return sum(building_maintenance(b, bonuses) for b in planet.buildings)+(ASCENSION_GATE.maintenance if planet.ascension_gate else 0)


def colony_yields(planet, bonuses):
    industry, income, research = gross_colony_yields(planet, bonuses)
    return industry-assembly_work(planet, industry, bonuses), income-colony_maintenance(planet, bonuses), research
