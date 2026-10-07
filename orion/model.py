"""Game data and galaxy generation, independent of pygame and the UI."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
import math
import random
from uuid import uuid4

from .buildings import BUILDINGS, BUILDING_SLOTS
from .production import MAX_QUEUE, PROJECTS, SHIP_TYPES, STARTING_COLONISTS, travel_turns
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

    @property
    def in_transit(self):
        return self.destination is not None

    @property
    def name(self):
        return f"{SHIP_TYPES[self.kind].name} {self.id:03}"

    @classmethod
    def from_dict(cls, data, systems, *, version=7):
        if not isinstance(data, dict) or not _integer(data["id"], 1, 1_000_000):
            raise ValueError
        if not isinstance(data["kind"], str) or data["kind"] not in SHIP_TYPES:
            raise ValueError
        if not _integer(data["system_id"], 0, len(systems)-1):
            raise ValueError
        destination = data["destination"]
        remaining, total = data["turns_remaining"], data["travel_total"]
        speed_bonus = data["speed_bonus"] if version >= 7 else 0
        if type(speed_bonus) is not int or speed_bonus not in (0, 25, 50, 75):
            raise ValueError
        if destination is None:
            if not _integer(remaining, 0, 0) or not _integer(total, 0, 0) or speed_bonus:
                raise ValueError
        else:
            if not _integer(destination, 0, len(systems)-1) or destination == data["system_id"]:
                raise ValueError
            expected = travel_turns(systems[data["system_id"]], systems[destination], speed_bonus)
            if not _integer(total, expected, expected) or not _integer(remaining, 1, total):
                raise ValueError
        record = dict(data)
        record["speed_bonus"] = speed_bonus
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
    def from_dict(cls, data, systems, turn, *, version=7):
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
        if worlds[data["home_planet"]].owner != RIVAL:
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


@dataclass
class Planet:
    id: int
    name: str
    biome: str
    size: str
    richness: str
    gravity: str
    orbit_au: float
    population: int = 0  # Billions; population growth is not yet simulated.
    colonized: bool = False
    buildings: list[str] = field(default_factory=list)
    construction_queue: list[ConstructionProject] = field(default_factory=list)
    owner: str | None = None

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
        industry, income, research = 6, self.population, 0
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
                if project.reserves_slot:
                    self.buildings.append(project.item_id)
                completed.append(project.item_id)
                self.construction_queue.pop(0)
        return completed

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
            estimates.extend([turns]*len(forecast.advance_construction(bonuses)))
        return estimates

    @classmethod
    def from_dict(cls, data, expected_id, *, version=7):
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
        if version < 5:
            record["owner"] = PLAYER if data["colonized"] else None
        if record["owner"] not in (None, PLAYER, RIVAL):
            raise ValueError
        if data["colonized"] != (record["owner"] is not None):
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
            if not _integer(item["progress"], 0, cost-1) or (i>0 and item["progress"] != 0):
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
            Planet(2, "Earth", "Terran", "Medium", "Average", "Normal", 1.0, 8, True, owner=PLAYER),
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

    def research_state(self, owner=PLAYER):
        return self._empire(owner).technology

    def bonuses_for(self, owner=PLAYER):
        return self.research_state(owner).bonuses if owner is not None else {}

    def research_error(self, identifier, *, owner=PLAYER):
        return self.research_state(owner).choice_error(identifier)

    def choose_research(self, identifier, *, owner=PLAYER):
        error = self.research_error(identifier, owner=owner)
        if error:
            raise RuleError(error)
        self.research_state(owner).active = identifier
        return self.advance_research(owner)

    def advance_research(self, owner=PLAYER):
        empire = self._empire(owner)
        empire.research, discovered = empire.technology.spend(empire.research)
        if discovered and owner == RIVAL:
            self.rival_event(f"Discovered {discovered.name}.", turn=self.turn)
        return discovered

    def planet_yields(self, planet):
        return colony_yields(planet, self.bonuses_for(planet.owner))

    def building_yields(self, definition, planet):
        return building_yields(definition, planet.richness, self.bonuses_for(planet.owner or PLAYER))

    def queue_estimates(self, planet, additional=None):
        return planet.queue_estimates(additional, bonuses=self.bonuses_for(planet.owner))

    def project_price(self, item_id, owner=PLAYER):
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
        if self.opponent is not None:
            return "A rival empire is already active."
        if self.opponent_home() is None:
            return "No unclaimed habitable world outside your systems is available."
        return None

    def add_opponent(self, race_id=None):
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
        self.rival_event(f"Established its homeworld on {planet.name}.", turn=self.turn)
        return planet

    def planet_at(self, system_id, planet_id):
        if not _integer(system_id, 0, len(self.systems)-1):
            raise RuleError("Unknown solar system.")
        worlds = self.systems[system_id].worlds
        if not _integer(planet_id, 0, len(worlds)-1):
            raise RuleError("Unknown planet.")
        return worlds[planet_id]

    def build_error(self, system_id, planet_id, building_id, *, owner=PLAYER):
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

    def ship_build_error(self, system_id, planet_id, kind="colony_ship", *, owner=PLAYER):
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
        ship = self.ship_at(ship_id, owner=owner)
        if ship.in_transit:
            raise RuleError("This ship is already travelling. Wait until it arrives.")
        if not _integer(destination, 0, len(self.systems)-1):
            raise RuleError("Unknown destination system.")
        if destination == ship.system_id:
            raise RuleError("The ship is already in this system.")
        duration = self.travel_turns(self.systems[ship.system_id], self.systems[destination], owner)
        ship.speed_bonus = self.bonuses_for(owner).get("ship_speed", 0)
        ship.destination = destination
        ship.turns_remaining = ship.travel_total = duration
        return duration

    def colony_ships_at(self, system_id, *, owner=PLAYER):
        return [s for s in self.ships if s.owner == owner and s.kind == "colony_ship"
                and not s.in_transit and s.system_id == system_id]

    def colonize_error(self, system_id, planet_id, *, owner=PLAYER):
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
        self.ships.remove(ship)
        return planet

    def cancel_construction(self, system_id, planet_id, queue_index, *, owner=PLAYER):
        planet = self.planet_at(system_id, planet_id)
        self._require_colony(planet, owner)
        if not _integer(queue_index, 0, len(planet.construction_queue)-1):
            raise RuleError("That construction project is no longer in the queue.")
        project = planet.construction_queue.pop(queue_index)
        self._empire(owner).credits += project.refund
        return project.refund

    def demolish_building(self, system_id, planet_id, building_index, *, owner=PLAYER):
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
        advance_diplomacy(self)
        if self.opponent is not None:
            from .ai import run_ai
            run_ai(self)
        income, research = self.empire_rates
        rival_income, rival_research = self.empire_rates_for(RIVAL)
        arrivals = []
        for ship in self.ships:
            if ship.in_transit:
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
        self.turn += 1
        self.year += 1
        self.credits += income
        self.research += research
        discovered = self.advance_research()
        if self.opponent is not None:
            self.opponent.credits += rival_income
            self.opponent.research += rival_research
            self.advance_research(RIVAL)
        return TurnReport(income, research, completed, arrivals,
                          [discovered.name] if discovered else [])

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data, *, version=7):
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
            return cls(campaign, data["empire_name"], size, data["seed"],
                       data["turn"], data["year"], data["credits"], systems, selected, planet,
                       research, ships, next_ship, opponent, race_id, diplomacy, technology)
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise SaveError("This save contains invalid game data.") from exc


def new_game(empire_name="Terran Union", galaxy_size="Standard", seed=None, *, with_ai=True,
             race_id="terran", rival_race_id=None):
    if not _name(empire_name) or galaxy_size not in GALAXY_SIZES:
        raise SaveError("Enter an empire name and choose a galaxy size.")
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
    game = GameState(uuid4().hex, empire_name.strip(), galaxy_size, seed, 1, 2300, 120, systems, race_id=race_id)
    if with_ai and game.opponent_start_error() is None:
        game.add_opponent(rival_race_id)
    return game
