"""Civilization identities and shared player/AI racial rules."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RaceSpec:
    id: str
    name: str
    focus: str
    description: str
    default_empire: str
    color: tuple[int, int, int]
    trade_threshold: int
    research_threshold: int
    envoy_bonus: int = 0
    trade_bonus: int = 0
    research_bonus: int = 0
    development: tuple[str, ...] = ("factory", "trade_center", "research_lab", "mine")
    effects: tuple[tuple[str, int], ...] = ()
    abilities: tuple[str, ...] = ()
    research_priority: tuple[str, ...] = ("computers", "construction", "society")
    starting_research: int = 0

    @property
    def trait(self):
        if self.abilities:
            return self.focus
        if self.envoy_bonus:
            return f"Envoys: +{self.envoy_bonus} extra relations"
        if self.trade_bonus:
            return f"Trade pact: +{self.trade_bonus} extra credit / turn"
        return f"Research pact: +{self.research_bonus} extra RP / turn"

    @property
    def traits(self):
        return self.abilities or (self.trait, "Standard population, food and colony output.")


RACES = {
    "terran": RaceSpec(
        "terran", "Terrans", "Adaptable diplomats",
        "Human explorers whose diverse societies value negotiation, exchange and new frontiers.",
        "Terran Union", (119, 194, 207), 20, 30, envoy_bonus=4),
    "kharuun": RaceSpec(
        "kharuun", "Kharuun", "Crystalline builders",
        "Mineral-bodied engineers who measure trust through reliable exchange and lasting works.",
        "Kharuun Assembly", (231, 150, 100), 15, 45, trade_bonus=1,
        development=("factory", "trade_center", "mine", "research_lab"),
        research_priority=("construction", "materials", "physics")),
    "aelari": RaceSpec(
        "aelari", "Aelari", "Amphibious scholars",
        "Ocean-born archivists who build alliances around shared discovery and patient inquiry.",
        "Aelari Concord", (164, 163, 229), 30, 15, research_bonus=1,
        development=("factory", "research_lab", "trade_center", "mine"),
        research_priority=("physics", "computers", "biology")),
    "lithar": RaceSpec(
        "lithar", "Lithar", "Patient living stone",
        "Ancient stone organisms that endure hostile worlds and measure their future in geological ages.",
        "Lithar Continuum", (188, 179, 150), 25, 40,
        effects=(("capacity_percent", 100), ("food_use_percent", -50), ("growth_percent", -75),
                 ("barren", 1), ("volcanic", 1)),
        abilities=("Settle every biome; double population limits.",
                   "Half food consumption, rounded up.", "Population grows at one quarter of the usual rate."),
        development=("mine", "factory", "research_lab", "trade_center"),
        research_priority=("materials", "construction", "biology")),
    "varkesh": RaceSpec(
        "varkesh", "Varkesh", "Raiding clans",
        "Fast raiding fleets bring plunder and captive labor back to a single crowded stronghold.",
        "Varkesh Clans", (216, 127, 89), 40, 50,
        effects=(("ship_discount", 20), ("capacity_percent", 50), ("research_percent", -20),
                 ("ship_speed_percent", 50), ("fuel_range_percent", 50)),
        abilities=("Cannot colonize; ship speed and range +50%.",
                   "Raids steal credits and slaves; home limit 100.",
                   "Slaves: normal output, 5% mortality each turn.",
                   "Ships −20% cost; native capacity +50%; research −20%."),
        development=("factory", "research_lab", "mine", "trade_center"),
        research_priority=("physics", "construction", "power")),
    "wanderers": RaceSpec(
        "wanderers", "Wanderers", "Nomadic navigators",
        "Travel-worn navigators whose shipbuilding traditions and long-range fleets keep distant horizons within reach.",
        "Wanderer Flotillas", (210, 181, 125), 15, 30,
        effects=(("fuel_range", 3), ("ship_discount", 15), ("industry_percent", -15)),
        abilities=("Ships reach 3 light-years farther from colonies.", "All ships cost 15% fewer credits.",
                   "Colony industry output is 15% lower."),
        development=("factory", "research_lab", "trade_center", "mine"),
        research_priority=("power", "materials", "construction")),
    "xenonflora": RaceSpec(
        "xenonflora", "Xenonflora", "Living ecosystems",
        "Interwoven plant minds that flourish on living worlds, growing cities as extensions of their own bodies.",
        "Xenonflora Bloom", (137, 194, 111), 25, 25,
        effects=(("lush_food", 3), ("lush_growth_percent", 50), ("harsh_industry_percent", -25)),
        abilities=("Terran, Ocean and Gaia colonies produce +3 food.", "Population grows 50% faster on those worlds.",
                   "Industry is 25% lower on all other biomes."),
        development=("hydroponic_farm", "factory", "research_lab", "trade_center"),
        research_priority=("biology", "fields", "construction")),
    "nexus": RaceSpec(
        "nexus", "Nexus", "Machine collective",
        "Linked machine minds that assemble new citizens in industrial foundries and work without organic sustenance.",
        "Nexus Collective", (113, 203, 219), 25, 20,
        effects=(("food_use_percent", -100), ("industry_percent", 25), ("assembly_percent", 20),
                 ("barren", 1), ("volcanic", 1)),
        abilities=("Settle every biome; no food required.", "Gross industry output is 25% higher.",
                   "20% of industry assembles population until full."),
        development=("factory", "mine", "research_lab", "trade_center"),
        research_priority=("computers", "construction", "materials")),
    "aetheri": RaceSpec(
        "aetheri", "Aetheri", "Luminous energy beings",
        "Patient currents of sentient energy whose insight outpaces their ability to shape solid matter.",
        "Aetheri Resonance", (176, 156, 238), 30, 15,
        effects=(("food_use_percent", -100), ("passive_growth", 10), ("research_percent", 25),
                 ("industry_percent", -20), ("barren", 1), ("volcanic", 1)),
        abilities=("Settle every biome; no food required.", "Population grows by 10% of a billion per turn.",
                   "Colony research +25%; colony industry -20%."),
        research_priority=("physics", "fields", "power")),
    "concord": RaceSpec(
        "concord", "The Concord", "Symbiotic diplomats",
        "Distinct organisms joined in mutual dependence, extending their partnership into trade and shared discovery.",
        "Symbiotic Concord", (123, 196, 171), 10, 20,
        envoy_bonus=2, trade_bonus=3, research_bonus=1,
        effects=(("income_percent", -10),),
        abilities=("Trade pacts: +3 CR; research agreements: +1 RP.", "Envoys improve relations by 2 extra points.",
                   "Colony credit income is 10% lower."),
        development=("trade_center", "factory", "research_lab", "mine"),
        research_priority=("society", "computers", "biology")),
    "remnant": RaceSpec(
        "remnant", "The Remnant", "Keepers of lost glory",
        "Proud, patient survivors of a magnificent civilization, carrying fragments of knowledge and a quiet sense of loss.",
        "Remnant Enclave", (179, 185, 208), 35, 20,
        effects=(("research_percent", 25), ("industry_percent", -20)), starting_research=80,
        abilities=("Begin with 80 research points to spend.", "Research +25%; industry −20%.",
                   "Awakened tomb worlds join your empire."),
        development=("research_lab", "factory", "mine", "trade_center"),
        research_priority=("physics", "computers", "society")),
}


def default_rival_race(player_race):
    return "aelari" if player_race == "kharuun" else "kharuun"
