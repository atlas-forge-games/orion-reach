"""Public reference articles, independent of campaign state and fog of war."""

from dataclasses import dataclass
from functools import lru_cache
from . import GAME_TITLE

from .races import RACES
from .race_victory import LEGACIES, PROJECT_RACES
from .buildings import BUILDINGS
from . import council as council_balance
from . import specialists as specialist_rules
from . import administration as administration_rules
from .designs import HULLS, MODULES
from .encyclopedia_artifacts import ARTIFACT_CONCEPTS
from .personalities import PERSONALITIES
from .production import ASCENSION_GATE, SHIP_TYPES
from . import production as production_balance
from . import ship_scaling
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


def megastructure_research(kind):
    from .megastructures import MEGASTRUCTURES, required_technology
    spec, identifier = MEGASTRUCTURES[kind], required_technology(kind)
    return (TECHNOLOGIES[identifier].name if identifier else
            f'{BRANCHES[spec.branch].name} tier {spec.tier} (any choice)')


def guides():
    return (
        Article("gas_stations", "economy", "Gas giant orbital stations", "Atmospheric industry without colonies", (
            ("CONSTRUCTION", "Gas giants remain uncolonizable for every civilization. Open a gas giant's overview and choose one main installation. A local colony or anchored mothership provides crews; otherwise one idle outpost ship is consumed. Pay Resources and Credits up front. Assembly takes two turns and upkeep begins immediately. Stations observe their system but do not extend fuel range or count as colonies. Dismantling frees the slot without a refund."),
            ("SPECIALIZATIONS", "Gas refinery: 80 Resources + 20 Credits; 6 gross Credits/turn, 1 Credit upkeep. Energy platform: 120 Resources + 30 Credits; 8 shared system energy, 2 Credits upkeep. Research station: 100 Resources + 40 Credits; 4 RP/turn, 2 Credits upkeep. These base values are modified by the atmosphere. Energy fills owned local colony deficits in system/planet order before backup fuel is burned. Surplus is unused; travelling motherships and other star systems receive none."),
            ("ATMOSPHERES", "Ordinary giants have standard values. Gas-rich atmospheres add 25% refinery output. Strong magnetic fields add 25% energy. Extreme storms add 25% research, but cost 25% more to build and add 1 Credit upkeep. Calm atmospheres reduce construction costs by 20%. Output rounds down; construction costs round up. Properties are deterministic for existing and new campaigns."),
            ("MILITARY CONTROL", "Stations are unarmed and have 60 hull. Hostile armed fleets, guardians and pirate blockades suspend output while upkeep continues. Defeat orbital defenders before bombarding or capturing. Capture requires 30 hull or less, an unused armed escort and one idle troop transport, which supplies the occupation crew and is consumed. Captured output is suspended until at least the next turn. Bombardment spends each participating ship's normal once-per-turn action; zero hull destroys the station. Peaceful stations recover 4 hull/turn after the bombardment recovery delay. Diplomatic pacts protect them like outposts."),
        )),
        Article("neutral_encounters", "combat", "Pirates and scout searches", "Four ways to meet a neutral threat", (
            ("ARRIVAL AND PLANET GUARDS", "Existing system guardians attack ships entering their systems. Pirate planet guards protect only their named planet: you can visit the star, search it and settle other worlds. Open System overview → Encounters & search to challenge the guards with armed ships. Their defeat opens the planet for colonization or an outpost and awards 80 CR and 40 RES."),
            ("SCOUT SEARCHES", "Assign a stationary scout for two full turns. Bring an armed escort: the search may uncover a pirate frigate that immediately attacks. Other possible results are a supply cache worth 60 CR and 40 RES, an archive worth 80 RP, or no useful discovery. Sites are fixed at campaign creation. The first empire to finish claims the site; each empire may search each system once. Moving or losing the assigned scout pauses progress; a replacement can resume it. Search has no credit or research cost."),
            ("PIRATE RAIDS", "Rare events send pirates toward a settled system. Its owner receives three turns of warning in Turn News. Raiders attack fleets, remain for five turns, then depart. They can steal 10% of an undefended target empire's treasury, capped at 60 CR, once per raid. They do not capture colonies. Defeating them recovers this loot, plus a 60 CR and 20 RES bounty. One frigate arrives early in a campaign; two may arrive from turn 80. Headquarters are protected before turn 60."),
            ("COMBAT AND SETTINGS", "Pirates use ordinary tactical ship combat. Surviving pirates keep hull damage; rewards are paid only once. Hidden search ambushes yield 40 CR and 20 RES when defeated. Fighting pirates does not change diplomatic relations or declare war. The new-game Pirate encounters toggle controls planetary pirates, scout searches and timed raids. Existing guardian encounters remain available. Campaigns saved before v0.68 keep the new encounters disabled."),
        )),
        Article("megastructures", "economy", "Megastructures", "Four staged system projects", (
            ("CONSTRUCTION", "Open Megastructures from a surveyed solar system. Each civilization may commission each type once per campaign, even if it is later destroyed. Only one structure may occupy a solar system. You must be its only settled civilization to start, repair or advance construction; other civilizations' outposts do not count. Shared settlements or hostile armed ships pause work without losing progress. Choose 0–100% of local industry; materials are paid progressively and unused industry returns to colony queues. Four stages cost one, two, three and four times the listed stage-one budget."),
            ("DYSON SPHERE", f"{megastructure_research('dyson_sphere')}. Early sections add steady energy across the empire. The completed sphere supplies unlimited energy to all owned colonies: all enabled buildings and gates can operate and backup power plants consume no fuel. Statistics show finite actual supply, while energy screens show infinity."),
            ("STELLAR FORGE", f"{megastructure_research('stellar_forge')}. Ship-only acceleration for every colony queue in its system: 4x, 7x, 10x, then 13x ship work at the standard balance. Material prices are unchanged. Buildings, Trade Goods, population assembly and megastructure construction receive no extra industry."),
            ("RESEARCH ARRAY", f"{megastructure_research('research_array')}. Each completed section adds a 1% discovery chance per turn, up to 4%. A success grants one unknown technology, including skipped tiers and previously omitted choices. No ordinary research points are generated. Discovering the active project or its alternative refunds its progress; research can then be selected again."),
            ("ASTEROID MINING NETWORK", f"{megastructure_research('asteroid_network')}. Each section delivers 150 resources per turn directly to the imperial reserve, up to 600. Orbital extraction is separate from planetary mining and is unaffected by planetary mineral richness or administrative strain."),
            ("CONTROL AND DAMAGE", "Completed sections function while their owner retains a settlement and the system is not blockaded, including when new shared settlements pause construction. Lose all settlements and a sole new settler inherits the structure with work paused. Captured duplicates do not stack. Clear orbital defenders to attack using the normal once-per-turn bombardment allowance. Damage is repaired before construction resumes, spending industry and resources. Construction settings do not turn off completed sections."),
        )),
        Article("administration", "economy", "Administrative strain", "Empire size, integration and capital distance", (
            ("SETTLED SYSTEMS", f"Every settled system beyond your first adds {administration_rules.SYSTEM_STRAIN}% strain to all your colonies. Multiple planets in one system count once. Outposts do not count. Losing your last colony in a system removes that system's contribution."),
            ("INTEGRATION", f"Each newly settled or conquered system adds another {administration_rules.INTEGRATION_STRAIN}% empire-wide strain for {administration_rules.INTEGRATION_TURNS} production turns. Another planet in an already owned system does not restart integration. The founding capital and existing colonies in older saves begin integrated."),
            ("LOCAL DISTANCE", f"Only planets in the distant system receive its distance penalty: {administration_rules.DISTANCE_STRAIN}% per {administration_rules.DISTANCE_UNIT_LY:g} light-years beyond the first {administration_rules.DISTANCE_UNIT_LY:g} ly from the capital. Distances are continuous, using the same physical scale as fleet travel. Outposts provide fuel, not administration. The capital is the system containing the headquarters palace; if lost, headquarters falls back to the first remaining colony in system/planet order, and returns to the original homeworld when recovered."),
            ("PRODUCTION", f"Add size, integration and local distance, then cap the total at {administration_rules.MAX_STRAIN}%. Output sensitivities: research {administration_rules.RESEARCH_SENSITIVITY}%, credits {administration_rules.CREDITS_SENSITIVITY}%, industry {administration_rules.INDUSTRY_SENSITIVITY}%, mining {administration_rules.MINING_SENSITIVITY}% and food {administration_rules.FOOD_SENSITIVITY}%. Apply to positive colony production after bonuses, before upkeep, fuel use or food consumption. Whole-unit outputs round down; construction retains its existing minimum of one industry. Energy and maintenance are unchanged."),
            ("TRADE AND INFORMATION", "Trade Goods convert reduced industry, then pay local credit strain; all production screens display the final payout. Diplomatic agreements, raid loot and one-time exploration rewards are not colony output and are unaffected. The planet overview displays the breakdown; the settlement confirmation previews expansion costs. Queue estimates include integration expiry. Powered administration centres reduce local strain by 15 percentage points, to a minimum of zero. Other colonies are unaffected."),
        )),
        Article("specialists", "colonies", "Space Hubs and specialists", "Unique leaders and explorers", (
            ("RECRUIT", f"Build a Space Hub, then open Specialists from the Empire overview, your planet or the Hub building. An operational first Hub welcomes a leader and an explorer when available. Later arrivals are checked every {specialist_rules.VISIT_INTERVAL} turns per empire. Terran and Dominion attract more visitors; Remnant, Nexus and Varkesh attract fewer. Additional Hubs do not multiply the arrival rate. Visitors depart after {specialist_rules.VISIT_DURATION} turns."),
            ("UNIQUE PEOPLE", f"The galaxy shares {len(specialist_rules.SPECIALISTS)} named characters with distinct starting skills. Each exists only once. You may employ {specialist_rules.MAX_EMPLOYED} at a time. Hiring costs the displayed fee; every hired turn costs the salary, even while in reserve. Salaries reduce net income and follow normal treasury debt rules. Dismissal ends the salary immediately, without refunding the fee. Experience is retained if another empire later hires the character."),
            ("LEADERS", "Assign one leader to each colony. Their skill values add fixed industry, research, credit, food or mining output before applicable empire modifiers. They do not multiply population output. Several leaders may serve different colonies; no Hub is needed at their assigned colony. Losing a colony returns its leader to reserve."),
            ("EXPLORERS", "Assign an explorer to a system with your colony and no foreign colonies. First they survey, then the discovered site's required skill determines recovery speed. Hacking opens sealed stations, Salvaging recovers rare minerals, and Archaeology reconstructs ancient research. Foreign fleets pause expeditions. Each system has one finite site and pays its reward once; progress survives reassignment and conquest."),
            ("EXPERIENCE", f"Hired specialists gain {specialist_rules.XP_PER_TURN} XP per turn, including time in reserve. Each new level adds one to every starting skill; missing skills remain zero. Maximum level is {specialist_rules.MAX_LEVEL}. New levels apply after that turn's work. Hiring fees and salaries do not rise with level. Assignments take effect immediately; this first version has no specialist travel time."),
        )),
        Article("welcome", "basics", f"Welcome to {GAME_TITLE}", "Your first turns", (
            ("EXPLORE", "Select a star on the galaxy map. Its planets appear on the right. Send scouts to reveal unknown systems and search for discoveries."),
            ("BUILD A COLONY", "Open a planet to assign farmers, industrial workers, researchers and miners. Balance food and power before adding more buildings or ships."),
            ("CHOOSE A DISCOVERY", "Click the Research card at the top of the galaxy map, or press R. Research unlocks new economic options, defenses, hulls and equipment."),
            ("ADVANCE THE GALAXY", "End turn applies production, movement and the other empires' actions. Check Turn news for discoveries, completed projects and important events."),
        )),
        Article("black_holes", "basics", "Black-hole expeditions", "Hidden sites and legendary relics", (
            ("FIND THE SINGULARITIES", "New campaigns contain two black holes in a Compact galaxy, or three in Standard and Expansive galaxies. Gravitic Mapping reveals their names and locations. They stay hidden even with fog of war disabled. The Observer can see them from the start. Earlier campaigns keep their original worlds and gain no black holes."),
            ("APPROACH SAFELY", "Event Horizon Navigation, Computers tier VII, allows a safe approach and also includes detection if you chose the other tier VI technology. Without it, every ship that arrives at a black hole is lost. Unsafe orders require confirmation; pending departures can be cancelled before End Turn. Normal routes crossing the area are safe. Ordinary colony-based fuel range still applies."),
            ("DEFEAT THE GUARDIAN", "A prepared fleet approaches an ancient site outside the event horizon and fights its legendary guardian using normal tactical combat. Damage persists between expeditions. Retreat or defeat earns no relic. The first empire to defeat the guardian recovers the site's unique relic; revisiting cannot award another."),
            ("YOUR COLLECTION", "Recovery is saved with the campaign and announced in Turn news. Info → Legendary artifacts marks your recovered relics. Flagship/capital placement, bonuses and special powers remain proposed; collection does not activate them yet."),
        )),
        Article("map", "basics", "Reading the galaxy map", "Names, colors and intelligence", (
            ("ZOOM AND PAN", "Use the mouse wheel over the map to zoom from 100% to 400% around the cursor, or use the minus/plus buttons. Hold the right or middle mouse button and drag in any direction. Shift + arrow keys also pan continuously; horizontal wheel scrolling pans sideways and Shift + wheel pans vertically. Names and fleet badges keep their readable size."),
            ("FIND YOUR WAY", "Fit, 0 or Home restores the full map. Center or C brings the selected system into view. Keyboard + / minus changes zoom. Ordinary arrow keys still navigate controls and systems. The view is retained across screen visits and resets when starting or loading a campaign."),
            ("FLEET ORDERS", "You can zoom and pan while choosing a destination. Dragging never issues movement orders: left-click the destination as usual. Scrolling over the side panel still pages through its planets or fleet manifest."),
            ("SYSTEM NAMES", "Parentheses mark systems you have not surveyed. Gray names are neutral. Colonized names use their known owners' colors; shared systems split the name between those colors."),
            ("INFORMATION", "Explored systems may show a stored survey rather than a live view. A survey does not reveal later enemy movement or changes until you observe the system again."),
            ("COLORS", "Saturated blue is your default empire color. Settings → Galaxy colors offers saturated turquoise. Ownership rings and fleet markers follow the same preference."),
            ("SENSORS", "Sensor research detects enemy fleets within range of your colonies. Operational sensor arrays extend that local range. Press S on the galaxy map to show sensor coverage."),
        )),
        Article("controls", "basics", "Controls and saving", "Keyboard reference", (
            ("GALAXY SHORTCUTS", "I: Empire\nD: Diplomacy\nR: Research\nF: Fleets\nV: Objectives\nN: Turn news\nS: Sensor coverage\nE: End turn\nP: Menu\nF1: Encyclopedia"),
            ("COMBAT SHORTCUTS", "A: Auto combat / Take control\nE: End tactical turn\nN: Next ship\nWheel or + / minus: Zoom battlefield\nMiddle-drag or Shift + arrows: Pan\n0 or Home: Reset zoom\nPage Up / Page Down: Scroll the battlefield\nEscape: Pause\nF5: Save"),
            ("SAVING", "Choose Menu → Save game, or press F5 in a campaign view. Saving and returning to the main menu are separate actions."),
            ("NAVIGATION", "Tab or Up/Down moves between controls; Enter activates one. Escape returns or closes the current selection. F11 toggles fullscreen."),
            ("READING THIS GUIDE", "Choose a category and an article. Previous/Next, Left/Right, or the mouse wheel over the article list changes its page. Scroll the text with the wheel, Page Up/Page Down, or its arrow buttons. Back, Escape or F1 returns to your previous screen."),
        )),
        Article("settlement", "colonies", "Settling new worlds", "Colony ships and habitability", (
            ("COLONIZATION", "Send a colony ship to an unclaimed, habitable planet within reach. Arriving does not settle automatically: select the planet and choose colonization. The colony ship is consumed."),
            ("HABITABILITY", "Planet biome, your civilization and researched technology determine which worlds can be settled. A new colony becomes a supply point for future voyages."),
            ("GAS GIANTS", "Large atmospheric worlds appear in outer orbits. They can be explored but cannot be colonized by any species, including Lithar, Nexus and Aetheri. No current technology unlocks settlement. They have no population capacity, building slots or surface outposts. Their cloud decks are shown in an atmospheric survey. Shipboard habitats remain separate from planets."),
            ("ENVIRONMENT", "Growth efficiency depends on species and terrain. The planet overview shows the prospective factor before colonization. This scales food-driven growth, machine assembly and passive growth after existing race traits. It does not remove food or technology requirements. Richness, size, travel distance and empire strain still matter."),
            ("TOXIC WORLDS", "Corrosive worlds are difficult for most biological species. Skirr thrive here and obtain six natural food from native toxic biota at a fully Skirr colony; mixed colonies receive a population-weighted share. New Skirr games start on Toxic worlds, Nexus on Ice and Aelari on Ocean. Existing homeworlds are preserved."),
            ("EXCEPTIONS", "The Varkesh cannot colonize. They raid for slaves and credits. The Observer controls no colonies and watches the computer empires instead."),
        )),
        Article("population", "colonies", "Population and assignments", "Farmers, workers, scientists and miners", (
            ("JOBS", "Farmers produce food, industrial workers build projects, scientists generate research, and miners produce Resources. Buildings can add both base output and bonuses to assigned population."),
            ("MOVE A GROUP", "In a population row, click an icon to select it and the icons to its right. Then click the destination job to move the selected group. The displayed selection shows how many people will move."),
            ("GROWTH", "Food balance, planet capacity and racial abilities affect population growth. Machine and energy civilizations have different food and growth rules; see Civilizations for their traits."),
        )),
        Article("resources", "economy", "The six resources", "What the top bar tells you", (
            ("CREDITS", "Credits pay building and ship maintenance, specialist hiring fees and salaries, and diplomatic expenses. The top bar shows your treasury and net income per turn. Buildings, habitat modules and the Ascension Gate cannot be bought; ship production can still be rushed."),
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
            ("BUILDING CONSTRUCTION", "Buildings, mothership modules and the Ascension Gate must be completed with local industry. Credits cannot finish them instantly. The Buy button is available only for ships and still requires their Resources."),
            ("QUEUE EDITING", "Queue adds each project at the end and keeps the production screen open. Click an existing queued project to make it current. Return to colony or Escape finishes editing. End Turn opens colonies without production orders; leaving an empty colony or building screen selects Trade Goods."),
            ("TRADE GOODS", "This ongoing production mode converts 30% of available industry to credits, rounded down separately for each colony each turn. It uses no Resources or building slots. Existing queued projects keep their progress while paused. Add a project or click one in the queue to resume construction. Trade Goods colonies do not trigger idle reminders."),
            ("ONGOING COSTS", "Buildings can require credit maintenance and energy after construction. A larger economy must support both the new building and the jobs it is intended to improve."),
            ("FLEET UPKEEP", "Every owned ship pays credit maintenance by hull class, both in orbit and in transit. Custom designs pay the same as their standard class. Queued ships cost no upkeep; normal completions start paying next turn. Mothership hull upkeep is additional to onboard modules. Destroyed or consumed ships stop costing upkeep. Deficits follow the usual treasury debt rules."),
            ("REFERENCE VALUES", "Catalog entries show base values. Racial traits, research, mineral richness and current operating conditions can change the results shown on a colony or in a shipyard."),
        )),
        Article("research_guide", "research", "How research works", "Sequential tiers and exclusive choices", (
            ("FIELDS AND TIERS", f"The research overview has {len(BRANCHES)} fields. Civilization legacies are tracked in Objectives. Finish tiers in order within a branch. New campaigns offer three exclusive technologies per tier; completing one closes both alternatives. Older campaigns retain their original choices."),
            ("CHANGING YOUR MIND", "Click a technology to select it immediately. Until it is completed, you can switch projects and transfer invested RP. Completed choices remain fixed."),
            ("INSPECT", "Right-click a technology in the research screen to read its details. If you finish a turn without an active project and research choices remain, the research screen opens."),
            ("REFERENCE CATALOG", "The encyclopedia lists the complete public technology catalog, including technologies you have not researched. Reading an entry never selects or unlocks it."),
            ("WANDERER SYSTEM RESEARCH", "Forgotten hyperlanes are separate 300 RP projects available from the solar-system overview. A chosen share of stationary mothership research funds the local project; remaining RP goes to technology. Banked RP can also be invested. The displayed empire research rate is after these allocations."),
        )),
        Article("motherships", "ships", "Wanderer motherships", "Cities that travel between stars", (
            ("MOBILE HOMES", "Wanderers start with a mothership and two scouts. They inhabit no planets. Each mothership holds up to 50 B population and has its own workforce, growth, facilities and construction queue. Click it in the solar-system overview or system sidebar, or use Home in its galaxy fleet popup. An anchored home gives its system the empire's ownership color."),
            ("RELOCATION", "Motherships travel at one quarter of normal fleet speed. Ships sent with a mothership share that speed and arrive together. A selected mothership adds 15 ly fuel range to its convoy: initially 25 ly with standard Wanderer bonuses. Fuel research increases this further; multiple motherships do not stack the bonus. Ordinary fleets retain their usual range. Supply and sensors follow the home's actual position; it no longer observes its former system after departure."),
            ("ONBOARD MODULES", "Motherships have 12 module bays. Farming, industry, extraction, research and other modules share the costs, outputs, power requirements and research unlocks of their planetary equivalents. Click an installed module to manage it, a queued module to inspect it, or an empty bay to choose construction. Click the Space Hub module to hire specialists; leaders can be assigned to the home. Existing saves automatically use module names and artwork."),
            ("ONBOARD ECONOMY", "Food, research, industry, credits and resources continue during travel. Ship construction waits until arrival, and Ascension Gates charge only while anchored. Planetary missile bases, shields, fortifications, jump gates and interdictors cannot be built aboard."),
            ("FORGOTTEN HYPERLANES", "The hidden network is fixed at galaxy creation. Roughly 50% of ordinary systems have at least one route, 25% at least two, 12.5% at least three, and so on. Station a mothership to inspect local signals, then spend 300 RP per route, one at a time per system. Destinations are revealed on completion. Allocate local research or invest banked RP; leaving pauses progress. Private two-way routes bypass fuel limits and take one turn, including for motherships. They use no megastructure slot. Guardians and hostile fleets still defend the exit."),
            ("WANDERER VICTORY", "When Race-specific victory is enabled in new-game setup, discover every unique forgotten hyperlane with your own empire to win. Each two-way connection counts once. Objectives → Race-specific goals shows your discovery count and the goals and progress of empires you have met, without revealing their routes. Other races have no special goal yet. With this victory disabled, discovery and travel remain available. Older campaigns retain their original victory settings."),
            ("EXPANSION AND DEFENSE", "Only Wanderers can build new motherships. Each includes initial settlers; base construction costs 1200 Resources and 600 work before racial discounts. Motherships start with 180 hull, defensive lasers and a 12-point shield generator. Space defeat disables a home for three turns. Clear its escorts, then open the habitat to board, raid or destroy it. Any empire may operate a captured home; only Wanderers build new ones. Losing the last home ends the empire. Wanderers cannot settle or occupy planets."),
            ("BOARDING AND LOOT", "Boarding and raiding require troop transports. Habitat decks add 25% defending firepower; transports are lost only with their troops. Capture preserves population and facilities. Raids take credits and resources from actual empire stocks, with a ten-turn cooldown; Varkesh also take up to a quarter of the population as slaves, leaving at least one inhabitant. Destroying a disabled home requires an armed ship and recovers 10% of its base hull and facility Resource costs."),
            ("OLDER CAMPAIGNS", "Existing Wanderer colonies move into motherships on loading, preserving their population, compatible facilities and queued work. Existing colony ships become mobile homes. An unfinished battle is resolved before this conversion occurs."),
        )),
        Article("travel", "ships", "Fleet movement and fuel", "Range is different from speed", (
            ("RANGE", f"The base fuel range is {production_balance.BASE_FUEL_RANGE} light-years from an owned colony or outpost. The map shows the combined supply area with one outer boundary. Scouts do not extend supply. Civilization traits and researched fuel tanks can extend it."),
            ("SCOUTS", "Scouts have twice the normal fuel range, including civilization and research bonuses. This applies to a single scout or a fleet consisting entirely of scouts. Adding an ordinary ship restores the normal fleet range; a mothership convoy keeps its existing reserve bonus. The map boundary and route preview follow the selected ships. Scouts do not create supply points or travel faster."),
            ("SPEED", "Drive research reduces voyage time. Fuel tanks extend reach without speeding up a voyage. Navigation networks and jump gates can improve travel between your colonies; enemy interdiction can slow an approach."),
            ("ORDERS", "Click a fleet marker, select ships, then choose a destination. Queued departures can be changed before End turn. Ships already in transit continue their ordered voyage."),
        )),
        Article("space_combat", "combat", "Space combat", "Movement, weapons and drones", (
            ("ENGAGEMENT", "Opposing fleets and orbital defenses are resolved in turn-based combat. Select a ship, move to a reachable cell and fire a ready weapon at a target in range."),
            ("PLANETARY BATTERIES", "Missile bases appear on the surface of their own planets. Click a friendly planet to command its battery, or an enemy planet to target its base. Planet names identify each defense; the hull bar belongs to the base. Missiles launch from the installation and incoming shots hit it. Destroying a base leaves the planet and its colony intact; conquest still requires a ground invasion."),
            ("AUTO COMBAT", "Choose Auto combat or press A to let the computer move your ships, choose targets, fire weapons, launch drones and end tactical turns. Battles remain animated and use the same rules, including guardian battles. A fleet that can no longer attack retreats if a safe destination is available."),
            ("TAKING CONTROL", "Choose Take control or press A again to resume manual orders. An action already underway finishes; spent movement and weapons stay spent. If it is the enemy's turn, wait for your next turn. Menus and this guide pause the battle. Auto combat stops at the result screen; new battles and loaded games start with manual control."),
            ("BATTLEFIELD CAMERA", "Use the mouse wheel over the battlefield, or + / minus, to zoom from 50% to 300%. Middle-drag or Shift + arrows pans the view. Shift + wheel and Page Up / Page Down scroll vertically. Click the percentage button, press 0 or Home to return to 100% and reveal your selected ship. The sidebar stays fixed; zoom changes no combat distances or actions. The standalone simulator uses the same controls, and right-click ship inspection works at every zoom level."),
            ("APPROACH AND TORPEDOES", "Fleets begin farther apart, leaving room to approach and organize escorts. Torpedoes and missiles home toward their target at five cells per round, advancing at the start of the firing side's next turn. Damage occurs on arrival; nearby escorts and point defense apply then. Torpedoes and missiles bypass ship shields. Aim is locked at launch. An eight-cell shot takes two advances against a stationary target. Projectiles expire after six advances, or when their target is destroyed or the battle ends. Beams hit immediately."),
            ("WEAPON CHOICES", "Beams, torpedoes and other weapons differ in damage, range, accuracy and special effects. Ship shields absorb beam weapons; missiles and torpedoes bypass them. Point defense reduces projectile damage, including bomber torpedoes, but does not reduce drone beams. Armor adds hull against damage that gets through. Research and Ship equipment describe the available upgrades."),
            ("FLAGSHIPS", "Each fleet automatically chooses its strongest surviving ship and places it at the centre of its starting formation. A small flag and faint empire-coloured aura mark it. Other crewed fleetmates in range gain +8 accuracy and +5 evasion: 2 cells for scouts/frigates, 3 for destroyers and civilian transports, 4 for cruisers, 5 for carriers, 6 for battleships, and 8 for titans/motherships. The strongest command accuracy source applies without stacking. Damage and reloading do not transfer command; destruction promotes the next strongest survivor in place. Drones, bases and monsters are excluded. The flagship does not buff itself. Every shot hits disables aim/evasion effects. Simulator inspection shows the source and radius."),
            ("FLEET SUPPORT", "Support works automatically without spending actions. Standard destroyers carry escort arrays; standard titans carry flag bridges. Custom ships must fit their own support equipment. Destroyer arrays protect other allies within 2 cells from missiles and torpedoes. Command relays on cruisers or titans coordinate nearby ships; titan flag bridges offer greater reach and accuracy. Cruiser ECM projectors reduce the accuracy of attacks against nearby allies. Select a provider to see its range and covered allies. Links show who supports the selected ship; the sidebar lists received protection and command. Right-click modules in the designer for active balance values and research requirements."),
            ("FORMATION AND SIZE", "Support never affects its own provider. Command and ECM use only the strongest nearby source; escort protection is capped. Movement and destruction immediately change coverage. Beams bypass interception, so escorts cannot stop every threat. New battles use real hull footprints: frigates/scouts/drones 1x1, destroyers 2x1, cruisers 2x2, battleships/carriers 3x2, titans 3x3 and motherships 4x3. Moves must clear the whole footprint. Ship orientation remains fixed. Older saved battles keep their one-cell layouts until the next battle. Large mounts retain their tracking penalties against small ships. Beams require a clear firing line and cannot pass through friendly or enemy ships. A blocked shot is unavailable; mixed volleys can still launch their guided torpedoes. The AI seeks open firing lanes. Weapon ranges use nearest hull cells; support radii use ship centres."),
            ("COMBAT SOUND", "Lasers, heavy beams, missile launches, shield hits, hull impacts and explosions have distinct sound cues. Incoming ordnance makes its impact sound when it arrives. Settings → Sound → Sound effects controls these cues and interface tones independently of music."),
            ("CARRIERS", "Carriers fitted with drone bays can launch drones. Bays limit active drones and launches per battle. Interceptor and bomber research unlock specialized drone types."),
            ("DESIGNS", "Plan and save any hull and equipment before research; construction requires every hull and module technology. Each module fills one offensive, defensive or support slot. Hull size scales output and cost. Large weapons track small targets poorly. Right-click equipment in the designer for details. Existing ships retain their blueprints."),
        )),
        Article("ground_combat", "combat", "Ground combat and raiding", "Transport troops and colony defenses", (
            ("INVASION", f"Clear hostile orbital defenses and bring troop transports. Each transport supplies {production_balance.TROOP_STRENGTH} invasion attack before modifiers. Defenders include colony militia and trained garrison troops."),
            ("DEFENSE", "Barracks train garrisons; defensive buildings improve resistance. Planetary shields also protect against attacks from orbit. Inspect the invasion preview before committing troops."),
            ("VARKESH RAIDS", "A successful Varkesh raid steals credits and enslaves population instead of establishing a new colony. Their slaves work at their homeworld and suffer attrition."),
        )),
        Article("diplomacy", "affairs", "First contact and diplomacy", "Relations, treaties and shared scanners", (
            ("CONTACT", "Meeting another civilization unlocks its diplomatic channel and a greeting shaped by its attitude. Without fog of war, introductions can happen immediately."),
            ("RELATIONS", "Shared values set new relationships: autonomy, openness, restraint, innovation and stewardship. Diplomacy shows a clickable portrait strip with signed relation scores, the race matrix and Values & history. Treaties and conflict change history; alignment is not added every turn."),
            ("TRADE", "All races accept trade at +10 relations. Each partner earns 25% of the geometric mean of both empires' gross colony credit output, plus its own trade bonuses, divided by 1 + capital distance / 50 light-years and rounded to whole credits. Trade income is excluded from economic strength. An active pact adds +1 relations each turn."),
            ("FRIENDSHIP", "Non-aggression is accepted at +0, blocks attacks, raids and bombardment, and adds +1 relations each turn. Friendship is accepted at +30 and includes trade, non-aggression and both partners' direct scanner output at its original detail level. It grants no planet surveys or onward sharing from friends of friends. Research agreements remain available separately."),
            ("WAR AND TERMINATION", "Declare war to end all agreements and set relations to -100. A non-aggression partner cannot be attacked until the pact ends. Ending friendship removes its bundled trade, protection and live scanner feed; last sightings remain dated. Treaty offers share a three-turn cooldown. Gifts and envoys are no longer diplomatic actions."),
            ("COALITIONS", "Open Coalitions & tribute to propose an agreement against a mutually known third empire. Shared wars, nearby holdings and racial interests determine willingness. Members gain mutual non-aggression and +1 relations per turn. Target aggression calls partners into defence; offensive wars do not. Joining an existing war requires explicit confirmation. Leaving is a broken promise; elimination dissolves the agreement without penalty."),
            ("FEAR AND TRIBUTE", "Fear is separate from relations and uses observed fleets, proximity, recent defeats, allied protection and racial resolve. AI empires pay valid tribute at fear 75. Demand money (three turns of gross colony income, capped by treasury) or, as Varkesh, one population unit as slaves. A colony cannot be emptied. Every issued demand uses a 100-turn global cooldown, including refusals. Demands harm relations and encourage coalitions, but do not automatically start war. Human recipients explicitly accept or refuse in Diplomacy or Turn news."),
            ("RACIAL PRIORITIES", "The eleven profiles guide treaty selection and coalition interests. Lithar remember broken promises permanently, while Kharuun favour profitable trade and Aelari/Nexus value research cooperation. Broken promises raise acceptance thresholds except for trade, which stays at +10. No direct resource or technology trading is available. Access, mediation and historical claims are preferences rather than separate diplomatic actions."),
            ("STATISTICS", "The Statistics button beside Rival report graphs population, industry, food, mining, energy generation and net credits per turn. New campaigns record every turn from turn 1. Contact reveals the other empire's full recorded history. Hover to inspect values; click civilization names to hide or show lines. Older saves start recording at their load turn."),
        )),
        Article("victory", "affairs", "Victory conditions", "Conquest, science, council and race goals", (
            ("CAMPAIGN SETUP", "Choose enabled victories on the second new-game screen. Turn all off for open-ended play. A human empire is still defeated if it loses all colonies."),
            ("CONQUEST", "When conquest is enabled, the last empire with colonies wins. Objectives summarizes your progress."),
            ("RACE-SPECIFIC", "An independent setup toggle enables racial goals. Wanderers win by personally discovering every unique forgotten hyperlane in the fixed galaxy network. Other races have no special goal yet. Objectives → Race-specific goals displays your goal and progress, plus portraits, goals and progress for empires you have met. Hidden destinations remain private. Turning this victory off preserves research and travel. Simultaneous final discoveries share the win."),
            ("CIVILIZATION LEGACIES", "Each race has its own goal in Objectives. Planetary civilizations unlock a legacy installation after eight technologies, then sustain all requirements for five consecutive turns. Wanderers win by recovering every forgotten hyperlane. Ascension Gate victory has been replaced."),
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
    for rid, spec in LEGACIES.items():
        result.append(Article("legacy_"+rid, "affairs", spec.title, RACES[rid].name,
            (("GOAL", spec.description), ("METHOD", spec.method),
             ("INSTALLATION", f"{spec.name}: unlocked after eight technologies. Construct through ordinary colony production. View exact targets and status in Objectives."),
             ("FINALE", "Satisfy all requirements for five consecutive turns. Blockade, bombardment, starvation and power loss can interrupt operation. Capture destroys a legacy installation. Targets scale with galaxy size and available content."))))
    for spec in sorted((b for b in BUILDINGS.values() if b.enabled), key=lambda s: s.name):
        sections = [("PURPOSE", spec.description),
                    ("BASE COST", f"{spec.resource_cost} Resources · {spec.work_cost} construction work"),
                    ("PER TURN", f"Maintenance: {spec.maintenance} CR · Energy demand: {spec.energy_use}"),
                    ("BASE EFFECT", spec.effect_text("Average"))]
        if spec.workforce_text("Average"):
            sections.append(("WORKFORCE BONUS", spec.workforce_text("Average")))
        sections += [("RESEARCH REQUIRED", f"Eight technologies · {RACES[PROJECT_RACES[spec.id]].name} only" if spec.id in PROJECT_RACES else building_research(spec.technology)),
                     ("NOTES", "One per colony, including queued orders. Values use Average mineral richness, before empire bonuses. Benefits require the building to operate.")]
        result.append(Article("building_"+spec.id, "buildings", spec.name, "Building · base values", tuple(sections)))
    for spec in sorted(TECHNOLOGIES.values(), key=lambda s: (s.branch, s.tier, s.name)):
        if spec.id == "ascension_theory" or not spec.enabled:
            continue
        finale = False
        branch = "Ascension" if finale else BRANCHES[spec.branch].name
        tier = "Finale" if finale else "Tier "+TIER_NAMES[spec.tier-1]
        alternatives = [t.name for t in TECHNOLOGIES.values() if t.enabled and t.branch == spec.branch and t.tier == spec.tier and t.id != spec.id]
        sections = [("FIELD", branch+" · "+tier), ("RESEARCH COST", f"{spec.cost:,} RP"), ("EFFECT", spec.description),
                    ("PREREQUISITE", "Complete all research required for your campaign; science victory must be enabled." if finale else
                     "Complete the preceding tiers in this branch." if spec.tier > 1 else "The first tier in this branch.")]
        if alternatives:
            sections.append(("EXCLUSIVE ALTERNATIVES", "; ".join(alternatives)+". Completing one technology closes the other choices in this tier. Any completed choice opens the next tier."))
        result.append(Article("technology_"+spec.id, "research", spec.name, f"{tier} · {spec.cost:,} RP", tuple(sections)))
    roles = {"colony_ship": "Establish a new colony on a suitable, unclaimed world. Consumed on settlement.",
             "outpost_ship": "Establish an unarmed refuelling outpost on any uncolonized solid-surface planet, regardless of habitability. Surface outposts exclude gas giants; an outpost ship can instead supply an orbital station foundation there for an additional construction payment. Consumes the ship. Only one outpost may exist per solar system, across all empires. Outposts extend fuel range and observe the local system, but have no population, production or upkeep. An owned outpost can be replaced by a colony using a colony ship. Enemy armed ships can attack it from the planet overview after defeating orbital defenders; destruction removes its fuel coverage.",
             "mothership": "A mobile city with 50 B population capacity, defensive lasers and a 12-point shield generator. Defeated homes can be boarded, raided or destroyed. Only Wanderers construct them; any empire can operate captured ones.",
             "scout": "Explore systems and search for discoveries. Twice the normal fuel range, including civilization and research bonuses, when travelling alone or with other scouts. Unarmed.",
             "troop_transport": "Carry troops for planetary invasions or raids. Unarmed.",
             "frigate": "Small, agile warship with fast-tracking mounts. Useful against small attackers and exposed support ships.",
             "destroyer": "Small warship suited to escorts or torpedo attacks. Standard ships include an escort array; custom designs need to fit one to protect nearby allies.",
             "cruiser": "Medium combat hull that can fit a command relay or defensive ECM projector. Support equipment competes with other support modules.",
             "battleship": "Heavy firepower against large ships and defenses. Large mounts struggle to track small ships; nearby escorts can protect it from projectiles and drones.",
             "titan": "Heavy capital hull; an automatically chosen titan flagship has an 8-cell aura granting allies +8 aim and +5 evasion. Standard titans also include a flag bridge; custom designs can fit one for +12 aim within 4 cells. Command uses the strongest accuracy source and never buffs its own provider.",
             "carrier": "A warship with drone bays. Can launch combat drones during a battle."}
    for spec in SHIP_TYPES.values():
        sections = [("ROLE", roles.get(spec.id, "An armed warship. Standard ships or custom blueprints can be built after unlocking this hull.")),
                    ("STANDARD SHIP", f"Equipped cost: {spec.resource_cost} Resources · {spec.work_cost} work\nHull: {spec.hull} · Nominal volley: {spec.damage}"),
                    ("MAINTENANCE", f"{spec.maintenance} CR per turn per ship, including custom designs of this hull class."),
                    ("RESEARCH REQUIRED", technology_name(spec.technology))]
        if spec.id in HULLS:
            hull = HULLS[spec.id]
            sections.append(("CUSTOM DESIGN SLOTS", f"Offense: {hull.offensive_slots} · Defense: {hull.defensive_slots} · Support: {hull.support_slots}\n{hull.module_size.title()} modules: {hull.module_scale}% output and cost.\nTracking penalty: {hull.tracking_penalty} percentage points per smaller target size.\nModule costs are added to the bare hull cost."))
            if ship_scaling.ENABLED:
                sections.append(("ENGINEERING BUDGET", f"Size index: {ship_scaling.SIZES[spec.id]}. Bare frame: {hull.hull} hull, {hull.resource_cost} Resources and {hull.work_cost} work. "
                                 "Standard warships are predefined equipment fits using the same calculations as custom designs. Research unlocks new equipment; fit it in the designer to use it."))
                sections.append(("STANDARD EQUIPMENT", ', '.join(MODULES[m].name for m in ship_scaling.STANDARD_LOADOUTS[spec.id])))
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
        if spec.id != 'observer':
            from .environments import BIOMES, PREFERENCES
            sections.append(("GROWTH ENVIRONMENTS", '\n'.join(f'{biome}: {PREFERENCES[spec.id][biome]}%' for biome in BIOMES)
                             +'\n100% is the usual rate. Mixed colonies weight resident species; mobile habitats use 100%.'))
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
