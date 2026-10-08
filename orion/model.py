"""Game data and galaxy generation, independent of pygame and the UI."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
import math
import random
from uuid import uuid4

from .buildings import BUILDINGS, BUILDING_SLOTS
from .production import ASCENSION_GATE, GATE_CHARGE_TURNS, MAX_QUEUE, PROJECTS, REPAIR_PER_TURN, SHIP_TYPES, STARTING_COLONISTS, travel_turns
from . import combat as combat_rules
from . import victory as victory_rules
from . import exploration as exploration_rules
from . import population as population_rules
from .races import RACES, default_rival_race
from .research import ResearchState, building_yields, colony_yields
from .diplomacy import (DiplomacyState, action_error, advance_diplomacy,
                        agreement_yields, make_contact, take_action)

GALAXY_SIZES = {"Compact": 24, "Standard": 48, "Expansive": 72}
STAR_TYPES = ("Yellow dwarf", "Blue star", "Red dwarf", "White star", "Orange dwarf")
BIOMES = ("Terran", "Ocean", "Desert", "Tundra", "Barren", "Volcanic")
RICHNESSES = ("Poor", "Average", "Rich")
PLANET_SIZES = ("Tiny", "Small", "Medium", "Large", "Huge")
GRAVITIES = ("Low", "Normal", "High")
HABITABILITY = {"Terran": 100, "Ocean": 80, "Desert": 40,
                "Tundra": 35, "Barren": 0, "Volcanic": 0}
PLAYER, RIVAL = "player", "rival"
NAMES = (
    "Vega Altair Deneb Sirius Rigel Arcturus Antares Procyon Spica Pollux "
    "Aldebaran Capella Bellatrix Alhena Mirach Alcor Mizar Polaris Thuban "
    "Achernar Alkaid Castor Caph Diphda Elnath Enif Errai Gacrux Hamal "
    "Izar Kochab Maia Markab Menkar Merak Mintaka Nashira Nunki Rasalas "
    "Saiph Schedar Shaula Skat Talitha Tarazed Wasat Zaniah Zosma Zuben "
    "Asterion Carina Cygnus Elara Fomalhaut Hyperion Iona Janus Kepler "
    "Lyra Mira Nereid Oberon Pallas Rhea Selene Tethys Umbra Vela Zenith "
    "Eos Halcyon Ishtar Lorien Nysa Orpheus Phoenix Pyxis Vesper"
).split()


class SaveError(ValueError):
    """A readable save/configuration error that the UI may display."""


class RuleError(ValueError):
    """An invalid player action, safe for the interface to explain."""


def _integer(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


def _name(value, maximum=28):
    return (isinstance(value, str) and 0 < len(value) <= maximum and bool(value.strip())
            and all(c.isprintable() for c in value))


@dataclass
class ConstructionProject:
    item_id: str
    progress: int = 0
    paid_credits: int | None = None

    def __post_init__(self):
        if self.paid_credits is None:
            self.paid_credits = PROJECTS[self.item_id].credit_cost

    @property
    def remaining_work(self):
        return PROJECTS[self.item_id].work_cost-self.progress

    @property
    def refund(self):
        definition = PROJECTS[self.item_id]
        return self.paid_credits*self.remaining_work//definition.work_cost

    @property
    def reserves_slot(self):
        return self.item_id in BUILDINGS


@dataclass
class Ship:
    id: int
    kind: str
    system_id: int
    destination: int | None = None
    turns_remaining: int = 0
    travel_total: int = 0
    owner: str = PLAYER
    speed_bonus: int = 0  # Snapshot at departure; discoveries never alter a voyage in flight.
    hull: int | None = None
    departure_pending: bool = False

    def __post_init__(self):
        if self.hull is None:
            self.hull = self.max_hull

    @property
    def max_hull(self):
        return SHIP_TYPES[self.kind].hull

    @property
    def damage(self):
        return SHIP_TYPES[self.kind].damage

    @property
    def in_transit(self):
        return self.destination is not None and not self.departure_pending

    @property
    def has_course(self):
        return self.destination is not None

    @property
    def name(self):
        return f"{SHIP_TYPES[self.kind].name} {self.id:03}"

    @classmethod
    def from_dict(cls, data, systems, *, version=14):
        if not isinstance(data, dict) or not _integer(data["id"], 1, 1_000_000):
            raise ValueError
        if not isinstance(data["kind"], str) or data["kind"] not in SHIP_TYPES:
            raise ValueError
        hull = data["hull"] if version >= 8 else SHIP_TYPES[data["kind"]].hull
        if not _integer(hull, 1, SHIP_TYPES[data["kind"]].hull):
            raise ValueError
        if not _integer(data["system_id"], 0, len(systems)-1):
            raise ValueError
        destination = data["destination"]
        remaining, total = data["turns_remaining"], data["travel_total"]
        speed_bonus = data["speed_bonus"] if version >= 7 else 0
        pending = data["departure_pending"] if version >= 14 else False
        if type(pending) is not bool:
            raise ValueError
        if type(speed_bonus) is not int or speed_bonus not in (0, 25, 50, 75):
            raise ValueError
        if destination is None:
            if not _integer(remaining, 0, 0) or not _integer(total, 0, 0) or speed_bonus or pending:
                raise ValueError
        else:
            if not _integer(destination, 0, len(systems)-1) or destination == data["system_id"]:
                raise ValueError
            expected = travel_turns(systems[data["system_id"]], systems[destination], speed_bonus)
            if not _integer(total, expected, expected) or not _integer(remaining, 1, total):
                raise ValueError
            if pending and remaining != total:
                raise ValueError
        record = dict(data)
        record["hull"] = hull
        record["speed_bonus"] = speed_bonus
        record["departure_pending"] = pending
        if version < 5:
            record["owner"] = PLAYER
        if record["owner"] not in (PLAYER, RIVAL):
            raise ValueError
        return cls(**record)


@dataclass
class AIEvent:
    turn: int
    message: str


@dataclass
class Opponent:
    name: str
    home_system: int
    home_planet: int
    credits: int = 120
    research: int = 0
    events: list[AIEvent] = field(default_factory=list)
    race_id: str = "kharuun"
    technology: ResearchState = field(default_factory=ResearchState)

    @classmethod
    def from_dict(cls, data, systems, turn, *, version=9):
        if not isinstance(data, dict) or not _name(data["name"]):
            raise ValueError
        for key in ("credits", "research"):
            if not _integer(data[key], 0, 1_000_000_000):
                raise ValueError
        if not _integer(data["home_system"], 0, len(systems)-1):
            raise ValueError
        worlds = systems[data["home_system"]].worlds
        if not _integer(data["home_planet"], 0, len(worlds)-1):
            raise ValueError
        if version < 9 and worlds[data["home_planet"]].owner != RIVAL:
            raise ValueError
        events = data["events"]
        if not isinstance(events, list) or len(events) > 12:
            raise ValueError
        parsed = []
        for event in events:
            if (not isinstance(event, dict) or not _integer(event["turn"], 1, turn)
                    or not _name(event["message"], 180)):
                raise ValueError
            parsed.append(AIEvent(**event))
        if any(a.turn > b.turn for a, b in zip(parsed, parsed[1:])):
            raise ValueError
        race_id = data["race_id"] if version >= 6 else "kharuun"
        if not isinstance(race_id, str) or race_id not in RACES:
            raise ValueError
        technology = ResearchState.from_dict(data["technology"]) if version >= 7 else ResearchState()
        return cls(**{**data, "events": parsed, "race_id": race_id, "technology": technology})


@dataclass
class TurnReport:
    income: int
    research: int
    completed: list[str]
    arrivals: list[str] = field(default_factory=list)
    discoveries: list[str] = field(default_factory=list)
    alerts: list[str] = field(default_factory=list)
    exploration: list[str] = field(default_factory=list)
    population: list[str] = field(default_factory=list)


@dataclass
class Planet:
    id: int
    name: str
    biome: str
    size: str
    richness: str
    gravity: str
    orbit_au: float
    population: int = 0  # Billions; each completed growth cycle adds one.
    colonized: bool = False
    buildings: list[str] = field(default_factory=list)
    construction_queue: list[ConstructionProject] = field(default_factory=list)
    owner: str | None = None
    ascension_gate: bool = False
    gate_charge: int = 0
    growth_progress: int = 0
    farmers: int = 0
    scientists: int = 0

    @property
    def workers(self):
        return self.population-self.farmers-self.scientists

    @property
    def population_capacity(self):
        return population_rules.POPULATION_LIMITS[self.size]

    @property
    def habitability(self):
        return HABITABILITY[self.biome]

    @property
    def building_capacity(self):
        return BUILDING_SLOTS[self.size]

    @property
    def used_slots(self):
        return len(self.buildings)+sum(p.reserves_slot for p in self.construction_queue)

    @property
    def building_projects(self):
        """Queue indices paired with building projects, excluding ship construction."""
        return [(i, project) for i, project in enumerate(self.construction_queue) if project.reserves_slot]

    @property
    def free_slots(self):
        return self.building_capacity-self.used_slots

    @property
    def yields_per_turn(self):
        if not self.colonized:
            return (0, 0, 0)
        industry, income, research = max(1, self.workers), self.population, 2*self.scientists
        for building_id in self.buildings:
            extra = BUILDINGS[building_id].yields(self.richness)
            industry += extra[0]
            income += extra[1]
            research += extra[2]
        return industry, income, research

    @property
    def industry_per_turn(self):
        return self.yields_per_turn[0]

    def advance_construction(self, bonuses=None):
        """Use this turn's starting industry, carrying overflow into queued projects."""
        work = colony_yields(self, bonuses or {})[0]
        completed = []
        while work > 0 and self.construction_queue:
            project = self.construction_queue[0]
            applied = min(work, project.remaining_work)
            project.progress += applied
            work -= applied
            if project.remaining_work == 0:
                completed.append(self.finish_current_project())
        return completed

    def finish_current_project(self):
        project = self.construction_queue.pop(0)
        if project.reserves_slot:
            self.buildings.append(project.item_id)
        elif project.item_id == ASCENSION_GATE.id:
            self.ascension_gate, self.gate_charge = True, 0
        return project.item_id

    def queue_estimates(self, additional=None, *, bonuses=None):
        """Exact turns until completion, assuming no future player changes."""
        if not self.colonized:
            return []
        forecast = replace(self, buildings=self.buildings.copy(),
                           construction_queue=[replace(p) for p in self.construction_queue])
        if additional is not None:
            forecast.construction_queue.append(ConstructionProject(additional))
        turns, estimates = 0, []
        while forecast.construction_queue:
            turns += 1
            food = population_rules.report(forecast, bonuses)
            estimates.extend([turns]*len(forecast.advance_construction(bonuses)))
            population_rules.advance(forecast, food)
        return estimates

    @classmethod
    def from_dict(cls, data, expected_id, *, version=12):
        if not isinstance(data, dict) or not _integer(data["id"], expected_id, expected_id):
            raise ValueError
        if not _name(data["name"], 40):
            raise ValueError
        if data["biome"] not in BIOMES or data["size"] not in PLANET_SIZES:
            raise ValueError
        if data["richness"] not in RICHNESSES or data["gravity"] not in GRAVITIES:
            raise ValueError
        orbit = data["orbit_au"]
        if type(orbit) not in (int, float) or not math.isfinite(orbit) or not 0 < orbit <= 500:
            raise ValueError
        if type(data["colonized"]) is not bool or not _integer(data["population"], 0, 100):
            raise ValueError
        if not data["colonized"] and data["population"] != 0:
            raise ValueError
        record = dict(data)
        if version < 12:
            record["farmers"] = min(2, data["population"])
            record["scientists"] = 0
        if (not _integer(record["farmers"], 0, data["population"])
                or not _integer(record["scientists"], 0, data["population"])
                or record["farmers"]+record["scientists"] > data["population"]):
            raise ValueError("Invalid worker allocation")
        if version < 11:
            record["growth_progress"] = 0
        if (not _integer(record["growth_progress"], 0, population_rules.GROWTH_THRESHOLD-1)
                or (not data["colonized"] and record["growth_progress"] != 0)):
            raise ValueError
        if version < 5:
            record["owner"] = PLAYER if data["colonized"] else None
        if record["owner"] not in (None, PLAYER, RIVAL):
            raise ValueError
        if data["colonized"] != (record["owner"] is not None):
            raise ValueError
        if version < 9:
            record["ascension_gate"], record["gate_charge"] = False, 0
        if (type(record["ascension_gate"]) is not bool
                or not _integer(record["gate_charge"], 0, GATE_CHARGE_TURNS)
                or (record["ascension_gate"] and not data["colonized"])
                or (record["gate_charge"] and not record["ascension_gate"])):
            raise ValueError
        if version < 3:
            record["buildings"] = []
            record["construction_queue"] = []
        buildings = record["buildings"]
        queued = record["construction_queue"]
        if not isinstance(buildings, list) or not isinstance(queued, list):
            raise ValueError
        if len(queued) > MAX_QUEUE:
            raise ValueError
        if any(not isinstance(b, str) or b not in BUILDINGS for b in buildings):
            raise ValueError
        projects = []
        for i, item in enumerate(queued):
            if not isinstance(item, dict):
                raise ValueError
            item = dict(item)
            if version < 4:
                item["item_id"] = item.pop("building_id")
                if item["item_id"] not in BUILDINGS:
                    raise ValueError
            if not isinstance(item["item_id"], str) or item["item_id"] not in PROJECTS:
                raise ValueError
            cost = PROJECTS[item["item_id"]].work_cost
            price = PROJECTS[item["item_id"]].credit_cost
            if version < 7:
                item["paid_credits"] = price
            if not _integer(item["paid_credits"], 1, price):
                raise ValueError
            if not _integer(item["progress"], 0, cost-1) or (version < 12 and i>0 and item["progress"] != 0):
                raise ValueError
            projects.append(ConstructionProject(**item))
        if len(buildings)+sum(p.reserves_slot for p in projects) > BUILDING_SLOTS[data["size"]]:
            raise ValueError
        if not data["colonized"] and (buildings or projects):
            raise ValueError
        record["construction_queue"] = projects
        return cls(**record)


@dataclass
class StarSystem:
    id: int
    name: str
    x: float
    y: float
    kind: str
    planets: int
    biome: str
    richness: str
    worlds: list[Planet] = field(default_factory=list)


def generate_planets(system, galaxy_seed):
    """Stable planet data, using a separate RNG so galaxy positions never change."""
    rng = random.Random(f"orion-worlds-v1:{galaxy_seed}:{system.id}")
    if system.id == 0:
        # Sol intentionally models four inner worlds at this prototype stage.
        home = [
            Planet(0, "Mercury", "Barren", "Tiny", "Rich", "Low", .39),
            Planet(1, "Venus", "Volcanic", "Medium", "Average", "Normal", .72),
            Planet(2, "Earth", "Terran", "Medium", "Average", "Normal", 1.0, 8, True, owner=PLAYER, farmers=2),
            Planet(3, "Mars", "Desert", "Small", "Average", "Low", 1.52),
        ]
    else:
        home = []
    worlds = []
    orbit = rng.uniform(.25, .7)
    for i in range(system.planets):
        if i < len(home):
            worlds.append(home[i])
            orbit = home[i].orbit_au * 1.6
            continue
        roman = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII")[i]
        # Keep the old system-level primary-world information on the first world.
        biome = system.biome if i == 0 else rng.choice(BIOMES)
        richness = system.richness if i == 0 else rng.choice(RICHNESSES)
        size = rng.choice(PLANET_SIZES)
        gravity = "Low" if size == "Tiny" else "High" if size == "Huge" else "Normal"
        worlds.append(Planet(i, f"{system.name} {roman}", biome, size,
                             richness, gravity, round(orbit, 2)))
        orbit *= rng.uniform(1.45, 1.9)
    return worlds


@dataclass
class GameState:
    campaign_id: str
    empire_name: str
    galaxy_size: str
    seed: int
    turn: int
    year: int
    credits: int
    systems: list[StarSystem]
    selected_system: int = 0
    selected_planet: int | None = None
    research: int = 0
    ships: list[Ship] = field(default_factory=list)
    next_ship_id: int = 1
    opponent: Opponent | None = None
    race_id: str = "terran"
    diplomacy: DiplomacyState | None = None
    technology: ResearchState = field(default_factory=ResearchState)
    combat: combat_rules.CombatState | None = None
    result: victory_rules.CampaignResult | None = None
    fog_of_war: bool = False
    exploration: exploration_rules.ExplorationState = field(default_factory=exploration_rules.ExplorationState)

    def system_visible(self, system_id, owner=PLAYER):
        return exploration_rules.is_visible(self, system_id, owner)

    def system_explored(self, system_id, owner=PLAYER):
        return exploration_rules.is_explored(self, system_id, owner)

    def known_system(self, system_id, owner=PLAYER):
        return exploration_rules.known_system(self, system_id, owner)

    def visible_ships(self, owner=PLAYER):
        return [ship for ship in self.ships if exploration_rules.ship_visible(self, ship, owner)]

    def strategy_error(self):
        if self.result is not None:
            return "This campaign has ended. Start a new campaign to play again."
        if self.combat is not None:
            return "Resolve the current battle before issuing strategic orders."
        return None

    def _require_strategy(self):
        if self.strategy_error():
            raise RuleError(self.strategy_error())

    def check_victory(self):
        if self.result is None and self.combat is None:
            self.result = victory_rules.current_result(self)
        return self.result

    def headquarters(self, owner=PLAYER):
        preferred = (0, 2) if owner == PLAYER else (self.opponent.home_system, self.opponent.home_planet)
        rows = victory_rules.colonies(self, owner)
        return next((row for row in rows if (row[0].id, row[1].id) == preferred), rows[0] if rows else None)

    def invasion_error(self, system_id, planet_id, *, owner=PLAYER):
        return victory_rules.invasion_error(self, system_id, planet_id, owner)

    def invade(self, system_id, planet_id, *, owner=PLAYER):
        result = victory_rules.invade(self, system_id, planet_id, owner)
        # Both sides know the outcome even if their last observing unit was lost.
        for empire in (PLAYER, RIVAL):
            exploration_rules.record_survey(self, system_id, empire)
        return result

    def gate_error(self, system_id, planet_id, *, owner=PLAYER):
        return victory_rules.gate_error(self, system_id, planet_id, owner)

    def queue_gate(self, system_id, planet_id, *, owner=PLAYER):
        error = self.gate_error(system_id, planet_id, owner=owner)
        if error:
            raise RuleError(error)
        self._empire(owner).credits -= ASCENSION_GATE.credit_cost
        self.planet_at(system_id, planet_id).construction_queue.append(ConstructionProject(ASCENSION_GATE.id))

    def fleet_at(self, system_id, owner=PLAYER):
        return [s for s in self.ships if s.owner == owner and not s.in_transit and s.system_id == system_id]

    def engagement_error(self, system_id, owner=PLAYER):
        return combat_rules.engagement_error(self, system_id, owner)

    def beam_for(self, kind, owner=PLAYER):
        return combat_rules.BEAMS[combat_rules.weapon_for(self, kind, owner)]

    def start_combat(self, system_id, owner=PLAYER):
        return combat_rules.begin_combat(self, system_id, owner)

    def combat_fire(self, ship_id, target_id, owner=PLAYER):
        return combat_rules.fire(self, ship_id, target_id, owner)

    def combat_hold(self, ship_id, owner=PLAYER):
        return combat_rules.hold(self, ship_id, owner)

    def combat_move(self, ship_id, x, y, owner=PLAYER):
        return combat_rules.move(self, ship_id, x, y, owner)

    def combat_end_turn(self, owner=PLAYER):
        return combat_rules.end_turn(self, owner)

    def combat_retreat(self, owner=PLAYER):
        return combat_rules.retreat(self, owner)

    def combat_ai_action(self):
        return combat_rules.ai_action(self)

    def finish_combat(self):
        if self.combat is None or self.combat.status == "active":
            raise RuleError("Finish the battle before returning to the system.")
        system_id = self.combat.system_id
        self.combat = None
        return system_id

    def can_repair(self, ship):
        return (not ship.has_course and any(p.owner == ship.owner for p in self.systems[ship.system_id].worlds)
                and not self.fleet_at(ship.system_id, combat_rules.other(ship.owner)))

    def research_state(self, owner=PLAYER):
        return self._empire(owner).technology

    def bonuses_for(self, owner=PLAYER):
        return self.research_state(owner).bonuses if owner is not None else {}

    def research_error(self, identifier, *, owner=PLAYER):
        if self.strategy_error():
            return self.strategy_error()
        return self.research_state(owner).choice_error(identifier)

    def choose_research(self, identifier, *, owner=PLAYER):
        error = self.research_error(identifier, owner=owner)
        if error:
            raise RuleError(error)
        self.research_state(owner).active = identifier
        return self.advance_research(owner)

    def advance_research(self, owner=PLAYER):
        self._require_strategy()
        empire = self._empire(owner)
        empire.research, discovered = empire.technology.spend(empire.research)
        if discovered and owner == RIVAL:
            self.rival_event(f"Discovered {discovered.name}.", turn=self.turn)
        return discovered

    def planet_yields(self, planet):
        return colony_yields(planet, self.bonuses_for(planet.owner))

    def population_report(self, planet):
        return population_rules.report(planet, self.bonuses_for(planet.owner))

    def set_workforce(self, system_id, planet_id, farmers, scientists, *, owner=PLAYER):
        self._require_strategy()
        planet = self.planet_at(system_id, planet_id)
        self._require_colony(planet, owner)
        if (not _integer(farmers, 0, planet.population)
                or not _integer(scientists, 0, planet.population)
                or farmers+scientists > planet.population):
            raise RuleError("Assign exactly one job to each billion inhabitants.")
        planet.farmers, planet.scientists = farmers, scientists

    def move_worker(self, system_id, planet_id, source, destination, *, owner=PLAYER):
        self._require_strategy()
        planet = self.planet_at(system_id, planet_id)
        self._require_colony(planet, owner)
        if source not in population_rules.WORKER_ROLES or destination not in population_rules.WORKER_ROLES or source == destination:
            raise RuleError("Choose two different worker roles.")
        counts = {role: getattr(planet, role) for role in population_rules.WORKER_ROLES}
        if counts[source] < 1:
            raise RuleError("There is no worker in that role to move.")
        counts[source] -= 1
        counts[destination] += 1
        self.set_workforce(system_id, planet_id, counts["farmers"], counts["scientists"], owner=owner)

    def building_yields(self, definition, planet):
        return building_yields(definition, planet.richness, self.bonuses_for(planet.owner or PLAYER))

    def queue_estimates(self, planet, additional=None):
        return planet.queue_estimates(additional, bonuses=self.bonuses_for(planet.owner))

    def project_price(self, item_id, owner=PLAYER):
        if item_id == ASCENSION_GATE.id:
            return ASCENSION_GATE.credit_cost
        key = "building_discount" if item_id in BUILDINGS else "ship_discount"
        discount = self.bonuses_for(owner).get(key, 0)
        return max(1, math.ceil(PROJECTS[item_id].credit_cost*(100-discount)/100))

    def travel_turns(self, origin, destination, owner=PLAYER):
        return travel_turns(origin, destination, self.bonuses_for(owner).get("ship_speed", 0))

    def can_settle(self, planet, owner=PLAYER):
        return planet.habitability > 0 or bool(self.bonuses_for(owner).get(planet.biome.lower(), 0))

    def starting_colonists(self, owner=PLAYER):
        return STARTING_COLONISTS+self.bonuses_for(owner).get("colonists", 0)

    def diplomacy_error(self, action):
        return action_error(self, action)

    def diplomacy_action(self, action):
        return take_action(self, action)

    def diplomatic_yields(self, owner=PLAYER):
        return agreement_yields(self, owner)

    def _empire(self, owner):
        if owner == PLAYER:
            return self
        if owner == RIVAL and self.opponent is not None:
            return self.opponent
        raise RuleError("Unknown empire.")

    def treasury_for(self, owner=PLAYER):
        return self._empire(owner).credits

    def research_for(self, owner=PLAYER):
        return self._empire(owner).research

    def empire_name_for(self, owner):
        if owner is None:
            return "Unclaimed"
        return self.empire_name if owner == PLAYER else self._empire(owner).name

    def ships_owned_by(self, owner=PLAYER):
        return [ship for ship in self.ships if ship.owner == owner]

    def _require_colony(self, planet, owner):
        self._empire(owner)
        if planet.owner != owner:
            raise RuleError("You can only manage colonies belonging to your empire.")

    def rival_event(self, message, *, turn=None):
        self.opponent.events.append(AIEvent(self.turn+1 if turn is None else turn, message))
        self.opponent.events = self.opponent.events[-12:]

    def opponent_home(self):
        """Choose a habitable home far from every existing player colony."""
        occupied = [s for s in self.systems if any(p.owner == PLAYER for p in s.worlds)]
        candidates = [(s, p) for s in self.systems if s not in occupied
                      for p in s.worlds if not p.colonized and p.habitability > 0]
        def score(row):
            s, p = row
            distance = min((((s.x-home.x)*1.4)**2+(s.y-home.y)**2 for home in occupied), default=0)
            return distance, p.habitability, p.building_capacity, -s.id, -p.id
        return max(candidates, key=score, default=None)

    def opponent_start_error(self):
        if self.strategy_error():
            return self.strategy_error()
        if self.opponent is not None:
            return "A rival empire is already active."
        if self.opponent_home() is None:
            return "No unclaimed habitable world outside your systems is available."
        return None

    def add_opponent(self, race_id=None):
        self._require_strategy()
        race_id = default_rival_race(self.race_id) if race_id is None else race_id
        if not isinstance(race_id, str) or race_id not in RACES:
            raise RuleError("Unknown rival race.")
        error = self.opponent_start_error()
        if error:
            raise RuleError(error)
        system, planet = self.opponent_home()
        self.opponent = Opponent("Helios Directorate", system.id, planet.id, race_id=race_id)
        self.diplomacy = make_contact(self.turn, self.opponent.name, race_id)
        planet.colonized, planet.owner, planet.population = True, RIVAL, 8
        planet.farmers, planet.scientists = 2, 0
        self._starting_fleet(RIVAL, system.id)
        self.rival_event(f"Established its homeworld on {planet.name}.", turn=self.turn)
        exploration_rules.refresh(self)
        return planet

    def _starting_fleet(self, owner, system_id):
        """One initial exploration and settlement fleet, created with the empire."""
        for kind in ("scout", "scout", "colony_ship"):
            self.ships.append(Ship(self.next_ship_id, kind, system_id, owner=owner))
            self.next_ship_id += 1

    def planet_at(self, system_id, planet_id):
        if not _integer(system_id, 0, len(self.systems)-1):
            raise RuleError("Unknown solar system.")
        worlds = self.systems[system_id].worlds
        if not _integer(planet_id, 0, len(worlds)-1):
            raise RuleError("Unknown planet.")
        return worlds[planet_id]

    def build_error(self, system_id, planet_id, building_id, *, owner=PLAYER):
        if self.strategy_error():
            return self.strategy_error()
        planet = self.planet_at(system_id, planet_id)
        if not isinstance(building_id, str) or building_id not in BUILDINGS:
            return "Unknown building."
        if not planet.colonized:
            return "Establish a colony before constructing buildings."
        if planet.owner != owner:
            return "This colony belongs to another empire."
        if len(planet.construction_queue) >= MAX_QUEUE:
            return "The construction queue is full."
        if planet.free_slots <= 0:
            return f"All {planet.building_capacity} building slots are occupied or reserved."
        if self.treasury_for(owner) < self.project_price(building_id, owner):
            return "Not enough credits to start this project."
        return None

    def queue_building(self, system_id, planet_id, building_id, *, owner=PLAYER):
        error = self.build_error(system_id, planet_id, building_id, owner=owner)
        if error:
            raise RuleError(error)
        planet = self.planet_at(system_id, planet_id)
        price = self.project_price(building_id, owner)
        self._empire(owner).credits -= price
        planet.construction_queue.append(ConstructionProject(building_id, paid_credits=price))

    def project_error(self, system_id, planet_id, item_id, *, owner=PLAYER):
        if not isinstance(item_id, str):
            return "Unknown construction project."
        if item_id in BUILDINGS:
            return self.build_error(system_id, planet_id, item_id, owner=owner)
        if item_id in SHIP_TYPES:
            return self.ship_build_error(system_id, planet_id, item_id, owner=owner)
        if item_id == ASCENSION_GATE.id:
            return self.gate_error(system_id, planet_id, owner=owner)
        return "Unknown construction project."

    def change_production(self, system_id, planet_id, item_id, *, owner=PLAYER):
        """Start a new first project, retaining the previous queue and its paid work."""
        error = self.project_error(system_id, planet_id, item_id, owner=owner)
        if error:
            raise RuleError(error)
        if item_id in BUILDINGS:
            self.queue_building(system_id, planet_id, item_id, owner=owner)
        elif item_id in SHIP_TYPES:
            self.queue_ship(system_id, planet_id, item_id, owner=owner)
        else:
            self.queue_gate(system_id, planet_id, owner=owner)
        queue = self.planet_at(system_id, planet_id).construction_queue
        queue.insert(0, queue.pop())

    def prioritize_construction(self, system_id, planet_id, index, *, owner=PLAYER):
        self._require_strategy()
        planet = self.planet_at(system_id, planet_id)
        self._require_colony(planet, owner)
        if not _integer(index, 0, len(planet.construction_queue)-1):
            raise RuleError("Choose an existing queued project.")
        planet.construction_queue.insert(0, planet.construction_queue.pop(index))

    def buy_construction_cost(self, system_id, planet_id):
        queue = self.planet_at(system_id, planet_id).construction_queue
        return 2*queue[0].remaining_work if queue else 0

    def buy_construction_error(self, system_id, planet_id, *, owner=PLAYER):
        if self.strategy_error():
            return self.strategy_error()
        planet = self.planet_at(system_id, planet_id)
        if planet.owner != owner:
            return "You can only buy production on your own colony."
        if not planet.construction_queue:
            return "Choose a construction project first."
        if self.treasury_for(owner) < self.buy_construction_cost(system_id, planet_id):
            return "Not enough credits to finish this project."
        return None

    def buy_construction(self, system_id, planet_id, *, owner=PLAYER):
        error = self.buy_construction_error(system_id, planet_id, owner=owner)
        if error:
            raise RuleError(error)
        planet = self.planet_at(system_id, planet_id)
        self._empire(owner).credits -= self.buy_construction_cost(system_id, planet_id)
        item_id = planet.finish_current_project()
        if item_id in SHIP_TYPES:
            self.ships.append(Ship(self.next_ship_id, item_id, system_id, owner=owner))
            self.next_ship_id += 1
        return item_id

    def ship_build_error(self, system_id, planet_id, kind="colony_ship", *, owner=PLAYER):
        if self.strategy_error():
            return self.strategy_error()
        planet = self.planet_at(system_id, planet_id)
        if not isinstance(kind, str) or kind not in SHIP_TYPES:
            return "Unknown ship type."
        if not planet.colonized:
            return "Ships can only be built at an established colony."
        if planet.owner != owner:
            return "This colony belongs to another empire."
        if len(planet.construction_queue) >= MAX_QUEUE:
            return "The construction queue is full."
        if self.treasury_for(owner) < self.project_price(kind, owner):
            return "Not enough credits to build this ship."
        return None

    def queue_ship(self, system_id, planet_id, kind="colony_ship", *, owner=PLAYER):
        error = self.ship_build_error(system_id, planet_id, kind, owner=owner)
        if error:
            raise RuleError(error)
        planet = self.planet_at(system_id, planet_id)
        price = self.project_price(kind, owner)
        self._empire(owner).credits -= price
        planet.construction_queue.append(ConstructionProject(kind, paid_credits=price))

    def ship_at(self, ship_id, *, owner=PLAYER):
        ship = next((s for s in self.ships if type(ship_id) is int and s.id == ship_id), None)
        if ship is None:
            raise RuleError("That ship is no longer available.")
        self._empire(owner)
        if ship.owner != owner:
            raise RuleError("You can only command ships belonging to your empire.")
        return ship

    def send_ship(self, ship_id, destination, *, owner=PLAYER):
        return self.send_ships([ship_id], destination, owner=owner)

    def send_ships(self, ship_ids, destination, *, owner=PLAYER):
        """Set a course for the next End Turn; pending orders may be redirected."""
        self._require_strategy()
        identifiers = list(ship_ids)
        if not identifiers:
            raise RuleError("Select at least one ship to send.")
        ships = [self.ship_at(identifier, owner=owner) for identifier in identifiers]
        if len({ship.id for ship in ships}) != len(ships):
            raise RuleError("Each ship can only be selected once.")
        if any(ship.in_transit for ship in ships):
            raise RuleError("This ship is already travelling. Wait until it arrives.")
        if any(ship.system_id != ships[0].system_id for ship in ships):
            raise RuleError("Selected ships must be in orbit at the same system.")
        if not _integer(destination, 0, len(self.systems)-1):
            raise RuleError("Unknown destination system.")
        if destination == ships[0].system_id:
            raise RuleError("The selected ships are already in this system.")
        for ship in ships:
            duration = self._dispatch_ship(ship, destination, pending=True)
        return duration

    @staticmethod
    def _clear_course(ship):
        ship.destination = None
        ship.turns_remaining = ship.travel_total = ship.speed_bonus = 0
        ship.departure_pending = False

    def cancel_departures(self, ship_ids, *, owner=PLAYER):
        """Cancel a whole selection atomically, only before its first travel step."""
        self._require_strategy()
        identifiers = list(ship_ids)
        if not identifiers:
            raise RuleError("Select at least one ship.")
        ships = [self.ship_at(identifier, owner=owner) for identifier in identifiers]
        if len({s.id for s in ships}) != len(ships):
            raise RuleError("Each ship can only be selected once.")
        if any(not s.departure_pending for s in ships):
            raise RuleError("Only departures awaiting End Turn can be cancelled.")
        if any(s.system_id != ships[0].system_id for s in ships):
            raise RuleError("Selected ships must be at the same system.")
        for ship in ships:
            self._clear_course(ship)
        exploration_rules.refresh(self)
        return len(ships)

    def _dispatch_ship(self, ship, destination, *, pending=False):
        """Route an order; battle retreats are already committed and cannot be cancelled."""
        exploration_rules.refresh(self)
        duration = self.travel_turns(self.systems[ship.system_id], self.systems[destination], ship.owner)
        ship.speed_bonus = self.bonuses_for(ship.owner).get("ship_speed", 0)
        ship.destination = destination
        ship.turns_remaining = ship.travel_total = duration
        ship.departure_pending = pending
        return duration

    def colony_ships_at(self, system_id, *, owner=PLAYER):
        return [s for s in self.ships if s.owner == owner and s.kind == "colony_ship"
                and not s.in_transit and s.system_id == system_id]

    def colonize_error(self, system_id, planet_id, *, owner=PLAYER):
        if self.strategy_error():
            return self.strategy_error()
        planet = self.planet_at(system_id, planet_id)
        if planet.colonized:
            return "This planet is already colonized."
        if not self.can_settle(planet, owner):
            technology = "Radiation Shields" if planet.biome == "Barren" else "Thermal Barriers"
            return f"Research {technology} to settle this world."
        if not self.colony_ships_at(system_id, owner=owner):
            return "Bring a colony ship to this system first."
        return None

    def colonize(self, ship_id, system_id, planet_id, *, owner=PLAYER):
        ship = self.ship_at(ship_id, owner=owner)
        if ship.kind != "colony_ship" or ship.in_transit or ship.system_id != system_id:
            raise RuleError("A colony ship must be in orbit in this system.")
        error = self.colonize_error(system_id, planet_id, owner=owner)
        if error:
            raise RuleError(error)
        planet = self.planet_at(system_id, planet_id)
        planet.colonized = True
        planet.owner = owner
        planet.population = self.starting_colonists(owner)
        planet.growth_progress = 0
        # New settlements first supply their inhabitants, then assign industry.
        passive = population_rules.BASE_FOOD[planet.biome]+self.bonuses_for(owner).get("colony_food", 0)
        rate = population_rules.FARMER_OUTPUT[planet.biome]
        planet.farmers = min(planet.population, max(0, (planet.population+1-passive+rate-1)//rate))
        planet.scientists = 0
        self.ships.remove(ship)
        return planet

    def cancel_construction(self, system_id, planet_id, queue_index, *, owner=PLAYER):
        self._require_strategy()
        planet = self.planet_at(system_id, planet_id)
        self._require_colony(planet, owner)
        if not _integer(queue_index, 0, len(planet.construction_queue)-1):
            raise RuleError("That construction project is no longer in the queue.")
        project = planet.construction_queue.pop(queue_index)
        self._empire(owner).credits += project.refund
        return project.refund

    def demolish_building(self, system_id, planet_id, building_index, *, owner=PLAYER):
        self._require_strategy()
        planet = self.planet_at(system_id, planet_id)
        self._require_colony(planet, owner)
        if not _integer(building_index, 0, len(planet.buildings)-1):
            raise RuleError("That building is no longer on this planet.")
        return planet.buildings.pop(building_index)

    @property
    def empire_rates(self):
        return self.empire_rates_for(PLAYER)

    def empire_rates_for(self, owner):
        income, research = self.diplomatic_yields(owner)
        for system in self.systems:
            for planet in system.worlds:
                if planet.owner != owner:
                    continue
                _, credits, points = self.planet_yields(planet)
                income += credits
                research += points
        return income, research

    def advance_turn(self):
        """AI orders, starting yields, travel and local production, then bank income."""
        self._require_strategy()
        exploration_rules.refresh(self)
        encounter = combat_rules.hostile_encounter(self)
        if encounter is not None:
            self.start_combat(encounter, RIVAL)
            return TurnReport(0, 0, [])
        # End Turn commits existing orders before the AI plans against current positions.
        for ship in self.ships:
            ship.departure_pending = False
        exploration_rules.refresh(self)
        repairable = {ship.id for ship in self.ships if self.can_repair(ship)}
        gates = [(s.id, p.id, p.owner) for s in self.systems for p in s.worlds if p.ascension_gate]
        alerts = []
        if self.opponent is not None:
            from .ai import run_ai
            alerts = run_ai(self)
            if self.result is not None:
                return TurnReport(0, 0, [], alerts=alerts)
        advance_diplomacy(self)
        income, research = self.empire_rates
        rival_income, rival_research = self.empire_rates_for(RIVAL)
        population_start = [(p, self.population_report(p)) for s in self.systems
                            for p in s.worlds if p.colonized]
        arrivals = []
        for ship in self.ships:
            if ship.has_course:
                ship.departure_pending = False
                ship.turns_remaining -= 1
                if ship.turns_remaining == 0:
                    ship.system_id = ship.destination
                    ship.destination = None
                    ship.travel_total = ship.speed_bonus = 0
                    message = f"{ship.name} at {self.systems[ship.system_id].name}"
                    if ship.owner == PLAYER:
                        arrivals.append(message)
                    else:
                        self.rival_event(f"Arrived: {message}.")
        completed = []
        for system in self.systems:
            for planet in system.worlds:
                for item_id in planet.advance_construction(self.bonuses_for(planet.owner)):
                    if item_id in SHIP_TYPES:
                        self.ships.append(Ship(self.next_ship_id, item_id, system.id, owner=planet.owner))
                        self.next_ship_id += 1
                    message = f"{PROJECTS[item_id].name} on {planet.name}"
                    if planet.owner == PLAYER:
                        completed.append(message)
                    else:
                        self.rival_event(f"Completed: {message}.")
                        if item_id == ASCENSION_GATE.id:
                            location = exploration_rules.gate_location(self, system.id, planet)
                            alerts.append(f"Rival gate completed at {location}: five charging turns remain")
        self.turn += 1
        self.year += 1
        self.credits += income
        self.research += research
        population = []
        for planet, start in population_start:
            if population_rules.advance(planet, start):
                message = f"{planet.name} grew to {planet.population} B"
                if planet.owner == PLAYER:
                    population.append(message)
                else:
                    self.rival_event(message+".", turn=self.turn)
        exploration = exploration_rules.refresh(self, recover=True)
        discovered = self.advance_research()
        if self.opponent is not None:
            self.opponent.credits += rival_income
            self.opponent.research += rival_research
            self.advance_research(RIVAL)
        for ship in self.ships:
            if ship.id in repairable and self.can_repair(ship):
                ship.hull = min(ship.max_hull, ship.hull+REPAIR_PER_TURN)
        victory_rules.advance_gates(self, gates)
        rival_gate = victory_rules.gate_site(self, RIVAL)
        if (rival_gate and rival_gate[1].gate_charge == GATE_CHARGE_TURNS-1
                and not victory_rules.gate_blocked(self, rival_gate[0].id, RIVAL)):
            location = exploration_rules.gate_location(self, rival_gate[0].id, rival_gate[1])
            alerts.append(f"Rival gate at {location} will activate next turn unless blocked")
        exploration_rules.refresh(self)
        self.check_victory()
        encounter = combat_rules.hostile_encounter(self)
        if encounter is not None:
            self.start_combat(encounter, RIVAL)
        return TurnReport(income, research, completed, arrivals,
                          [discovered.name] if discovered else [], alerts, exploration, population)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data, *, version=14):
        """Validate all values used by rendering; never execute save contents."""
        try:
            if not isinstance(data, dict):
                raise ValueError
            campaign = data["campaign_id"]
            if not (isinstance(campaign, str) and len(campaign) == 32
                    and all(c in "0123456789abcdef" for c in campaign)):
                raise ValueError
            if not _name(data["empire_name"]):
                raise ValueError
            size = data["galaxy_size"]
            if size not in GALAXY_SIZES:
                raise ValueError
            if not _integer(data["seed"], 0, 999_999_999):
                raise ValueError
            if not _integer(data["turn"], 1, 1_000_000):
                raise ValueError
            if data["year"] != 2299 + data["turn"] or type(data["year"]) is not int:
                raise ValueError
            if not _integer(data["credits"], 0, 1_000_000_000):
                raise ValueError
            research = data["research"] if version >= 3 else 0
            if not _integer(research, 0, 1_000_000_000):
                raise ValueError
            records = data["systems"]
            if not isinstance(records, list) or len(records) != GALAXY_SIZES[size]:
                raise ValueError
            systems = []
            for i, s in enumerate(records):
                if not isinstance(s, dict) or not _integer(s["id"], i, i) or not _name(s["name"]):
                    raise ValueError
                for axis in ("x", "y"):
                    if type(s[axis]) not in (int, float) or not math.isfinite(s[axis]) or not 0 <= s[axis] <= 1:
                        raise ValueError
                if s["kind"] not in STAR_TYPES or s["biome"] not in BIOMES or s["richness"] not in RICHNESSES:
                    raise ValueError
                if not _integer(s["planets"], 0, 8):
                    raise ValueError
                record = dict(s)
                world_data = record.pop("worlds", None)
                system = StarSystem(**record)
                if version == 1:
                    system.worlds = generate_planets(system, data["seed"])
                else:
                    if not isinstance(world_data, list) or len(world_data) != system.planets:
                        raise ValueError
                    system.worlds = [Planet.from_dict(p, j, version=version) for j, p in enumerate(world_data)]
                    if any(a.orbit_au >= b.orbit_au for a, b in zip(system.worlds, system.worlds[1:])):
                        raise ValueError
                systems.append(system)
            selected = data.get("selected_system", 0)
            if not _integer(selected, 0, len(systems) - 1):
                raise ValueError
            planet = None if version == 1 else data.get("selected_planet")
            if planet is not None and not _integer(planet, 0, systems[selected].planets - 1):
                raise ValueError
            ships, next_ship = [], 1
            if version >= 4:
                if not isinstance(data["ships"], list) or len(data["ships"]) > 10000:
                    raise ValueError
                ships = [Ship.from_dict(record, systems, version=version) for record in data["ships"]]
                if len({ship.id for ship in ships}) != len(ships):
                    raise ValueError
                next_ship = data["next_ship_id"]
                if not _integer(next_ship, max((ship.id for ship in ships), default=0)+1, 1_000_001):
                    raise ValueError
            opponent = None
            if version >= 5 and data["opponent"] is not None:
                opponent = Opponent.from_dict(data["opponent"], systems, data["turn"], version=version)
            if opponent is None and (any(p.owner == RIVAL for s in systems for p in s.worlds)
                                     or any(s.owner == RIVAL for s in ships)):
                raise ValueError
            race_id = data["race_id"] if version >= 6 else "terran"
            if not isinstance(race_id, str) or race_id not in RACES:
                raise ValueError
            if version >= 6:
                diplomacy = DiplomacyState.from_dict(data["diplomacy"], data["turn"]) if data["diplomacy"] is not None else None
                if (opponent is None) != (diplomacy is None):
                    raise ValueError
            else:
                diplomacy = make_contact(data["turn"], opponent.name, opponent.race_id) if opponent else None
            technology = ResearchState.from_dict(data["technology"]) if version >= 7 else ResearchState()
            game = cls(campaign, data["empire_name"], size, data["seed"],
                       data["turn"], data["year"], data["credits"], systems, selected, planet,
                       research, ships, next_ship, opponent, race_id, diplomacy, technology)
            if version >= 8 and data["combat"] is not None:
                game.combat = combat_rules.CombatState.from_dict(data["combat"], game, version=version)
            if version >= 9:
                game.result = victory_rules.validate(game, data["result"])
            if version >= 10:
                if type(data["fog_of_war"]) is not bool:
                    raise ValueError("Invalid fog setting")
                game.fog_of_war = data["fog_of_war"]
                game.exploration = exploration_rules.ExplorationState.from_dict(data["exploration"], game, version=version)
            # Older games retain the completely revealed map they started with.
            return game
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise SaveError("This save contains invalid game data.") from exc


def new_game(empire_name="Terran Union", galaxy_size="Standard", seed=None, *, with_ai=True,
             race_id="terran", rival_race_id=None, fog_of_war=True):
    if not _name(empire_name) or galaxy_size not in GALAXY_SIZES:
        raise SaveError("Enter an empire name and choose a galaxy size.")
    if type(fog_of_war) is not bool:
        raise SaveError("Fog of war must be on or off.")
    if not isinstance(race_id, str) or race_id not in RACES:
        raise SaveError("Choose a valid player race.")
    if rival_race_id is not None and (not isinstance(rival_race_id, str) or rival_race_id not in RACES):
        raise SaveError("Choose a valid rival race.")
    if seed is None:
        seed = random.SystemRandom().randrange(1_000_000_000)
    if not _integer(seed, 0, 999_999_999):
        raise SaveError("Seed must be a whole number between 0 and 999999999.")
    rng = random.Random(seed)
    names = NAMES.copy()
    rng.shuffle(names)
    systems = [StarSystem(0, "Sol", .35, .55, "Yellow dwarf", 4, "Terran", "Average")]
    count = GALAXY_SIZES[galaxy_size]
    for i in range(1, count):
        for _ in range(2000):
            x, y = rng.uniform(.06, .94), rng.uniform(.08, .92)
            if ((x - .5) / .48) ** 2 + ((y - .5) / .47) ** 2 > 1:
                continue
            if all(math.hypot((x-s.x)*1.4, y-s.y) > .085 for s in systems):
                break
        else:
            raise SaveError("Could not place this galaxy. Please try a different seed.")
        systems.append(StarSystem(i, names[i-1], x, y, rng.choice(STAR_TYPES),
                                  rng.randint(0, 7), rng.choice(BIOMES), rng.choice(RICHNESSES)))
    for system in systems:
        system.worlds = generate_planets(system, seed)
    game = GameState(uuid4().hex, empire_name.strip(), galaxy_size, seed, 1, 2300, 120, systems,
                     race_id=race_id, fog_of_war=fog_of_war)
    game._starting_fleet(PLAYER, 0)
    if with_ai and game.opponent_start_error() is None:
        game.add_opponent(rival_race_id)
    exploration_rules.refresh(game)
    return game
