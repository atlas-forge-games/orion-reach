"""Public reference articles, independent of campaign state and fog of war."""

from dataclasses import dataclass
from functools import lru_cache

from .buildings import BUILDINGS
from . import council as council_balance
from .designs import HULLS, MODULES
from .encyclopedia_artifacts import ARTIFACT_CONCEPTS
from .personalities import PERSONALITIES
from .production import ASCENSION_GATE, SHIP_TYPES
from . import production as production_balance
from .races import SETUP_RACES
from .research import BRANCHES, TECHNOLOGIES, TIER_NAMES, ResearchState


CATEGORIES = {
    "basics": "Getting started", "colonies": "Colonies", "economy": "Economy & energy",
    "buildings": "Buildings", "research": "Research", "ships": "Ships",
    "equipment": "Ship equipment", "artifacts": "Legendary artifacts",
    "combat": "Combat", "civilizations": "Civilizations",
    "affairs": "Diplomacy & victory",
}


@dataclass(frozen=True)
class Article:
    id: str
    category: str
    title: str
    subtitle: str
    sections: tuple[tuple[str, str], ...]
    image: str | None = None
    image_caption: str = ""
    planned: bool = False


def technology_name(identifier):
    return TECHNOLOGIES[identifier].name if identifier else "No research prerequisite"


def building_research(identifier):
    if identifier is None:
        return technology_name(None)
    # Building unlocks also accept later sensor, shield and interdiction
    # research. Ask the public rule instead of duplicating its upgrade table.
    return " or ".join(spec.name for spec in sorted(TECHNOLOGIES.values(), key=lambda t: t.tier)
                       if ResearchState(completed=[spec.id]).has_unlock(identifier))


def guides():
    return (
        Article("welcome", "basics", "Welcome to Orion Reach", "Your first turns", (
            ("EXPLORE", "Select a star on the galaxy map. Its planets appear on the right. Send scouts to reveal unknown systems and search for discoveries."),
            ("BUILD A COLONY", "Open a planet to assign farmers, industrial workers, researchers and miners. Balance food and power before adding more buildings or ships."),
            ("CHOOSE A DISCOVERY", "Click the Research card at the top of the galaxy map, or press R. Research unlocks new economic options, defenses, hulls and equipment."),
            ("ADVANCE THE GALAXY", "End turn applies production, movement and the other empires' actions. Check Turn news for discoveries, completed projects and important events."),
        )),
        Article("black_holes", "basics", "Black-hole expeditions", "Hidden sites and legendary relics", (
            ("FIND THE SINGULARITIES", "New campaigns contain two black holes in a Compact galaxy, or three in Standard and Expansive galaxies. Gravitic Mapping, Computers tier VI, reveals their names and locations. They stay hidden even with fog of war disabled. The Observer can see them from the start. Earlier campaigns keep their original worlds and gain no black holes."),
            ("APPROACH SAFELY", "Event Horizon Navigation, Computers tier VII, allows a safe approach and also includes detection if you chose the other tier VI technology. Without it, every ship that arrives at a black hole is lost. Unsafe orders require confirmation; pending departures can be cancelled before End Turn. Normal routes crossing the area are safe. Ordinary colony-based fuel range still applies."),
            ("DEFEAT THE GUARDIAN", "A prepared fleet approaches an ancient site outside the event horizon and fights its legendary guardian using normal tactical combat. Damage persists between expeditions. Retreat or defeat earns no relic. The first empire to defeat the guardian recovers the site's unique relic; revisiting cannot award another."),
            ("YOUR COLLECTION", "Recovery is saved with the campaign and announced in Turn news. Info → Legendary artifacts marks your recovered relics. Flagship/capital placement, bonuses and special powers remain proposed; collection does not activate them yet."),
        )),
        Article("map", "basics", "Reading the galaxy map", "Names, colors and intelligence", (
            ("SYSTEM NAMES", "Parentheses mark systems you have not surveyed. Gray names are neutral. Colonized names use their known owners' colors; shared systems split the name between those colors."),
            ("INFORMATION", "Explored systems may show a stored survey rather than a live view. A survey does not reveal later enemy movement or changes until you observe the system again."),
            ("COLORS", "Saturated blue is your default empire color. Settings → Galaxy colors offers saturated turquoise. Ownership rings and fleet markers follow the same preference."),
            ("SENSORS", "Sensor research detects enemy fleets within range of your colonies. Operational sensor arrays extend that local range. Press S on the galaxy map to show sensor coverage."),
        )),
        Article("controls", "basics", "Controls and saving", "Keyboard reference", (
            ("GALAXY SHORTCUTS", "I: Empire\nD: Diplomacy\nR: Research\nF: Fleets\nV: Objectives\nN: Turn news\nS: Sensor coverage\nE: End turn\nP: Menu\nF1: Encyclopedia"),
            ("COMBAT SHORTCUTS", "A: Auto combat / Take control\nE: End tactical turn\nN: Next ship\nPage Up / Page Down: Scroll the battlefield\nEscape: Pause\nF5: Save"),
            ("SAVING", "Choose Menu → Save game, or press F5 in a campaign view. Saving and returning to the main menu are separate actions."),
            ("NAVIGATION", "Tab or Up/Down moves between controls; Enter activates one. Escape returns or closes the current selection. F11 toggles fullscreen."),
            ("READING THIS GUIDE", "Choose a category and an article. Previous/Next, Left/Right, or the mouse wheel over the article list changes its page. Scroll the text with the wheel, Page Up/Page Down, or its arrow buttons. Back, Escape or F1 returns to your previous screen."),
        )),
        Article("settlement", "colonies", "Settling new worlds", "Colony ships and habitability", (
            ("COLONIZATION", "Send a colony ship to an unclaimed, habitable planet within reach. Arriving does not settle automatically: select the planet and choose colonization. The colony ship is consumed."),
            ("HABITABILITY", "Planet biome, your civilization and researched technology determine which worlds can be settled. A new colony becomes a supply point for future voyages."),
            ("EXCEPTIONS", "The Varkesh cannot colonize. They raid for slaves and credits. The Observer controls no colonies and watches the computer empires instead."),
        )),
        Article("population", "colonies", "Population and assignments", "Farmers, workers, scientists and miners", (
            ("JOBS", "Farmers produce food, industrial workers build projects, scientists generate research, and miners produce Resources. Buildings can add both base output and bonuses to assigned population."),
            ("MOVE A GROUP", "In a population row, click an icon to select it and the icons to its right. Then click the destination job to move the selected group. The displayed selection shows how many people will move."),
            ("GROWTH", "Food balance, planet capacity and racial abilities affect population growth. Machine and energy civilizations have different food and growth rules; see Civilizations for their traits."),
        )),
        Article("resources", "economy", "The six resources", "What the top bar tells you", (
            ("CREDITS", "Credits pay building maintenance and diplomatic expenses. The top bar shows your treasury and net income per turn."),
            ("RESEARCH", "Research points fund discoveries. Unused RP is banked until you select a project."),
            ("RESOURCES", "Resources are a shared empire stockpile produced by miners and mines. Construction spends Resources; thermal backup plants can also consume them as fuel."),
            ("INDUSTRY", "Industry supplies construction work locally. Buildings and ships require both Resources and enough completed work."),
            ("FOOD", "Food is used locally. The empire-wide surplus summarizes your colonies; a surplus elsewhere does not feed a starving colony."),
            ("ENERGY", "Energy is produced and consumed locally. Power on one world cannot run buildings on another. Click the Energy card to inspect colony power balances."),
        )),
        Article("power", "economy", "Keeping buildings powered", "Steady generation and backup fuel", (
            ("LOCAL SUPPLY", "Buildings consume energy. Power plants add local generation; research can improve the supply and unlock new plant types."),
            ("BACKUP LAST", "Steady power is used first. Thermal backup plants run only when needed and burn Resources for the energy they supply. Without enough fuel, they cannot cover the remaining demand."),
            ("SHORTAGES", "Insufficient power shuts down affected buildings' output and bonuses. Check the colony's operating status and power balance before expanding demand."),
            ("PLANT CATALOG", "Open Buildings to compare solar arrays, geothermal, fusion, thermal backup and singularity plants, including their research requirements and maintenance."),
        )),
        Article("construction", "economy", "Construction and upkeep", "Base costs and local production", (
            ("COSTS", "Orders enter a construction queue. A project spends its Resources when construction begins; insufficient Resources delay the work. Local industry completes the project over subsequent turns. Building slots limit how much a planet can accommodate."),
            ("QUEUE EDITING", "Queue adds each project at the end and keeps the production screen open. Click an existing queued project to make it current. Return to colony or Escape finishes editing. End Turn opens colonies without production orders; leaving an empty colony or building screen selects Trade Goods."),
            ("TRADE GOODS", "This ongoing production mode converts 30% of available industry to credits, rounded down separately for each colony each turn. It uses no Resources or building slots. Existing queued projects keep their progress while paused. Add a project or click one in the queue to resume construction. Trade Goods colonies do not trigger idle reminders."),
            ("ONGOING COSTS", "Buildings can require credit maintenance and energy after construction. A larger economy must support both the new building and the jobs it is intended to improve."),
            ("REFERENCE VALUES", "Catalog entries show base values. Racial traits, research, mineral richness and current operating conditions can change the results shown on a colony or in a shipyard."),
        )),
        Article("research_guide", "research", "How research works", "Sequential tiers and exclusive choices", (
            ("FIELDS AND TIERS", f"The research overview has {len(BRANCHES)} branches plus Ascension. Finish tiers in order within a branch. Ordinary tiers offer two exclusive technologies; completing one closes its alternative."),
            ("CHANGING YOUR MIND", "Click a technology to select it immediately. Until it is completed, you can switch projects and transfer invested RP. Completed choices remain fixed."),
            ("INSPECT", "Right-click a technology in the research screen to read its details. If you finish a turn without an active project and research choices remain, the research screen opens."),
            ("REFERENCE CATALOG", "The encyclopedia lists the complete public technology catalog, including technologies you have not researched. Reading an entry never selects or unlocks it."),
        )),
        Article("travel", "ships", "Fleet movement and fuel", "Range is different from speed", (
            ("RANGE", f"The base fuel range is {production_balance.BASE_FUEL_RANGE} light-years from an owned colony. Scouts do not extend that supply range. Civilization traits and researched fuel tanks can extend it."),
            ("SPEED", "Drive research reduces voyage time. Fuel tanks extend reach without speeding up a voyage. Navigation networks and jump gates can improve travel between your colonies; enemy interdiction can slow an approach."),
            ("ORDERS", "Click a fleet marker, select ships, then choose a destination. Queued departures can be changed before End turn. Ships already in transit continue their ordered voyage."),
        )),
        Article("space_combat", "combat", "Space combat", "Movement, weapons and drones", (
            ("ENGAGEMENT", "Opposing fleets and orbital defenses are resolved in turn-based combat. Select a ship, move to a reachable cell and fire a ready weapon at a target in range."),
            ("PLANETARY BATTERIES", "Missile bases appear on the surface of their own planets. Click a friendly planet to command its battery, or an enemy planet to target its base. Planet names identify each defense; the hull bar belongs to the base. Missiles launch from the installation and incoming shots hit it. Destroying a base leaves the planet and its colony intact; conquest still requires a ground invasion."),
            ("AUTO COMBAT", "Choose Auto combat or press A to let the computer move your ships, choose targets, fire weapons, launch drones and end tactical turns. Battles remain animated and use the same rules, including guardian battles. A fleet that can no longer attack retreats if a safe destination is available."),
            ("TAKING CONTROL", "Choose Take control or press A again to resume manual orders. An action already underway finishes; spent movement and weapons stay spent. If it is the enemy's turn, wait for your next turn. Menus and this guide pause the battle. Auto combat stops at the result screen; new battles and loaded games start with manual control."),
            ("WEAPON CHOICES", "Beams, torpedoes and other weapons differ in damage, range, accuracy and special effects. Shields, armor and interception offer different defenses. Research and Ship equipment describe the available upgrades."),
            ("CARRIERS", "Carriers fitted with drone bays can launch drones. Bays limit active drones and launches per battle. Interceptor and bomber research unlock specialized drone types."),
            ("DESIGNS", "Plan and save any hull and equipment before research; construction requires every hull and module technology. Each module fills one offensive, defensive or support slot. Hull size scales output and cost. Large weapons track small targets poorly. Right-click equipment in the designer for details. Existing ships retain their blueprints."),
        )),
        Article("ground_combat", "combat", "Ground combat and raiding", "Transport troops and colony defenses", (
            ("INVASION", f"Clear hostile orbital defenses and bring troop transports. Each transport supplies {production_balance.TROOP_STRENGTH} invasion attack before modifiers. Defenders include colony militia and trained garrison troops."),
            ("DEFENSE", "Barracks train garrisons; defensive buildings improve resistance. Planetary shields also protect against attacks from orbit. Inspect the invasion preview before committing troops."),
            ("VARKESH RAIDS", "A successful Varkesh raid steals credits and enslaves population instead of establishing a new colony. Their slaves work at their homeworld and suffer attrition."),
        )),
        Article("diplomacy", "affairs", "First contact and diplomacy", "Attitudes, envoys and agreements", (
            ("CONTACT", "Meeting another civilization unlocks its diplomatic channel and a greeting shaped by its attitude. Without fog of war, introductions can happen immediately."),
            ("RELATIONS", "Envoys and gifts can improve relations, subject to costs and cooldowns. Civilizations have different preferences and treaty requirements."),
            ("AGREEMENTS", "Trade and research pacts provide income while active. Attacking an empire breaks agreements and makes relations hostile. The diplomacy screen shows current terms and recent exchanges."),
        )),
        Article("victory", "affairs", "Victory conditions", "Conquest, science and the council", (
            ("CAMPAIGN SETUP", "Choose enabled victories on the second new-game screen. Turn all off for open-ended play. A human empire is still defeated if it loses all colonies."),
            ("CONQUEST", "When conquest is enabled, the last empire with colonies wins. Objectives summarizes your progress."),
            ("SCIENCE", f"Complete the required research, discover Ascension Theory ({TECHNOLOGIES['ascension_theory'].cost:,} RP), then build and charge an Ascension Gate. Its base cost is {ASCENSION_GATE.resource_cost} Resources and {ASCENSION_GATE.work_cost} work. Charging requires {production_balance.GATE_CHARGE_TURNS} powered turns with a clear orbit. Older campaigns can retain earlier research requirements."),
            ("GALACTIC COUNCIL", f"When at least half the systems are settled and two empires remain, the enabled council can form. Each colonized world gives one vote. At least half the eligible votes and a unique lead elect an emperor; a tie elects nobody. Unsuccessful votes repeat every {council_balance.ELECTION_INTERVAL} turns."),
            ("DEFIANCE", "If another empire wins the election, the human player can accept or defy the ruling. Defiance ends treaties and makes all surviving computer empires declare war."),
        )),
        Article("tombs", "affairs", "Tomb worlds", "The Remnant awakens", (
            ("AWAKENING", "If tomb worlds are enabled, hidden tombs can awaken during a campaign. An uncolonized world becomes a Remnant colony; an occupied world faces a ground battle."),
            ("DISCOVERY", "News reports awakenings in systems you have already surveyed. This encyclopedia describes the rule without revealing hidden tomb locations."),
        )),
    )


@lru_cache(maxsize=1)
def articles():
    result = list(guides())
    for spec in sorted(BUILDINGS.values(), key=lambda s: s.name):
        sections = [("PURPOSE", spec.description),
                    ("BASE COST", f"{spec.resource_cost} Resources · {spec.work_cost} construction work"),
                    ("PER TURN", f"Maintenance: {spec.maintenance} CR · Energy demand: {spec.energy_use}"),
                    ("BASE EFFECT", spec.effect_text("Average"))]
        if spec.workforce_text("Average"):
            sections.append(("WORKFORCE BONUS", spec.workforce_text("Average")))
        sections += [("RESEARCH REQUIRED", building_research(spec.technology)),
                     ("NOTES", "One per colony, including queued orders. Values use Average mineral richness, before empire bonuses. Benefits require the building to operate.")]
        result.append(Article("building_"+spec.id, "buildings", spec.name, "Building · base values", tuple(sections)))
    for spec in sorted(TECHNOLOGIES.values(), key=lambda s: (s.branch, s.tier, s.name)):
        finale = spec.id == "ascension_theory"
        branch = "Ascension" if finale else BRANCHES[spec.branch].name
        tier = "Finale" if finale else "Tier "+TIER_NAMES[spec.tier-1]
        alternative = next((t.name for t in TECHNOLOGIES.values() if t.branch == spec.branch and t.tier == spec.tier and t.id != spec.id), None)
        sections = [("FIELD", branch+" · "+tier), ("RESEARCH COST", f"{spec.cost:,} RP"), ("EFFECT", spec.description),
                    ("PREREQUISITE", "Complete all research required for your campaign; science victory must be enabled." if finale else
                     "Complete the preceding tiers in this branch." if spec.tier > 1 else "The first tier in this branch.")]
        if alternative:
            sections.append(("EXCLUSIVE ALTERNATIVE", alternative+". Completing either technology closes the other choice in this tier."))
        result.append(Article("technology_"+spec.id, "research", spec.name, f"{tier} · {spec.cost:,} RP", tuple(sections)))
    roles = {"colony_ship": "Establish a new colony on a suitable, unclaimed world. Consumed on settlement.",
             "scout": "Explore systems and search for discoveries. Unarmed.",
             "troop_transport": "Carry troops for planetary invasions or raids. Unarmed.",
             "carrier": "A warship with drone bays. Can launch combat drones during a battle."}
    for spec in SHIP_TYPES.values():
        sections = [("ROLE", roles.get(spec.id, "An armed warship. Standard ships or custom blueprints can be built after unlocking this hull.")),
                    ("STANDARD SHIP", f"Base cost: {spec.resource_cost} Resources · {spec.work_cost} work\nBase hull: {spec.hull}"),
                    ("RESEARCH REQUIRED", technology_name(spec.technology))]
        if spec.id in HULLS:
            hull = HULLS[spec.id]
            sections.append(("CUSTOM DESIGN SLOTS", f"Offense: {hull.offensive_slots} · Defense: {hull.defensive_slots} · Support: {hull.support_slots}\n{hull.module_size.title()} modules: {hull.module_scale}% output and cost.\nTracking penalty: {hull.tracking_penalty} percentage points per smaller target size.\nModule costs are added to the bare hull cost."))
        if spec.id == "troop_transport":
            sections.append(("TRAINING REQUIRED", "The colony needs operational barracks to train transport troops."))
        sections.append(("NOTES", "Queue ships in an owned colony's shipyard. Research and racial bonuses can change new orders. Unlocking a later hull does not unlock classes skipped in earlier research tiers."))
        result.append(Article("ship_"+spec.id, "ships", spec.name, "Ship class", tuple(sections)))
    for identifier, spec in sorted(MODULES.items(), key=lambda item: (item[1].category, item[1].name)):
        result.append(Article("module_"+identifier, "equipment", spec.name, spec.category.title()+" module", (
            ("EFFECT", spec.description), ("MODULE SLOT", f"One {spec.category} slot. Hull size scales damage, armor, shields, repair and cost; range and percentage effects stay unchanged."),
            ("BASE COST", f"{spec.resource_cost} Resources · {spec.work_cost} work, added to the blueprint"),
            ("RESEARCH REQUIRED", technology_name(spec.technology)),
        )))
    for spec in SETUP_RACES.values():
        sections = [("CIVILIZATION", spec.description), ("TRAITS", "\n".join(spec.traits))]
        if spec.home_system:
            sections.append(("HOME", spec.home_system+" · "+spec.homeworld))
        if spec.id in PERSONALITIES:
            personality = PERSONALITIES[spec.id]
            sections.append(("ATTITUDE", personality.traits+"\n"+personality.summary))
        result.append(Article("race_"+spec.id, "civilizations", spec.name, spec.focus, tuple(sections)))
    for concept in ARTIFACT_CONCEPTS:
        result.append(Article("artifact_"+concept.id, "artifacts", concept.name,
                              "Proposed use · "+concept.placement, (
            ("LEGEND", concept.lore),
            ("PROPOSED BONUS", concept.bonus),
            ("PROPOSED SPECIAL POWER", concept.power),
        ), image="artifacts/"+concept.id+"-v1.png",
            image_caption="Proposed use: "+concept.placement.lower(), planned=True))
    return tuple(result)


def category_articles(category):
    return tuple(article for article in articles() if article.category == category)
