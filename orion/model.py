"""Game data and galaxy generation, independent of pygame and the UI."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
import math
import random
from uuid import uuid4

from .buildings import BUILDINGS, BUILDING_SLOTS
from .designs import HULLS, MAX_DESIGNS, ShipDesign, loadout_error
from .production import ASCENSION_GATE, BASE_FUEL_RANGE, GATE_CHARGE_TURNS, LEGACY_SHIP_SPEED, MAX_QUEUE, PROJECTS, REPAIR_PER_TURN, SHIP_SPEED, SHIP_TYPES, STARTING_COLONISTS, distance_ly, travel_turns
from . import combat as combat_rules
from . import victory as victory_rules
from . import exploration as exploration_rules
from . import population as population_rules
from . import monsters as monster_rules
from . import ground_combat as ground_rules
from . import tomb_worlds as tomb_rules
from . import raiding as raid_rules
from . import defenses as defense_rules
from . import navigation
from . import sensors
from . import first_contact
from . import economy
from .races import RACES, default_rival_race
from .home_systems import name_home
from .empires import EMPIRE_IDS, RIVAL_IDS, CAMPAIGN_RIVAL_IDS, MAX_RIVALS, relation_key
from .research import TECHNOLOGIES, ResearchState, building_yields, colony_yields, colony_maintenance
from .diplomacy import (DiplomacyState, action_error, advance_diplomacy,
                        agreement_yields, make_contact, take_action)

GALAXY_SIZES = {"Compact": 24, "Standard": 48, "Expansive": 72}
GALAXY_BOUNDS = (.02, .98, .04, .96)
MIN_STAR_DISTANCE = 6  # ly; keeps stars distinct and clickable.
STAR_TYPES = ("Yellow dwarf", "Blue star", "Red dwarf", "White star", "Orange dwarf")
BIOMES = ("Terran", "Ocean", "Desert", "Tundra", "Barren", "Volcanic", "Gaia")
RICHNESSES = ("Poor", "Average", "Rich", "Ultra-rich")
PLANET_SIZES = ("Tiny", "Small", "Medium", "Large", "Huge")
GRAVITIES = ("Low", "Normal", "High")
HABITABILITY = {"Terran": 100, "Ocean": 80, "Desert": 40,
                "Tundra": 35, "Barren": 0, "Volcanic": 0, "Gaia": 100}
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
    design: ShipDesign | None = None
    resource_cost: int | None = None
    paid_resources: int = 0

    def __post_init__(self):
        if self.paid_credits is None:
            self.paid_credits = 0
        if self.resource_cost is None:
            self.resource_cost = 0 if self.paid_credits else self.spec.resource_cost
            if self.progress and not self.paid_credits:
                self.paid_resources = self.resource_cost

    @property
    def needs_resources(self):
        return self.resource_cost-self.paid_resources

    @property
    def resource_refund(self):
        return self.paid_resources*self.remaining_work//self.spec.work_cost

    @property
    def refund_text(self):
        parts = []
        if self.refund:
            parts.append(f"{self.refund} CR")
        if self.resource_refund:
            parts.append(f"{self.resource_refund} RES")
        return " + ".join(parts) or "0 RES"

    @property
    def spec(self):
        return self.design or PROJECTS[self.item_id]

    @property
    def is_ship(self):
        return self.design is not None or self.item_id in SHIP_TYPES

    @property
    def remaining_work(self):
        return self.spec.work_cost-self.progress

    @property
    def refund(self):
        definition = self.spec
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
    speed_bonus: int | float = 0  # Snapshot at departure; discoveries never alter a voyage in flight.
    hull: int | None = None
    departure_pending: bool = False
    cruise_speed: float = SHIP_SPEED  # Snapshot so balance updates do not change saved flights.
    design: ShipDesign | None = None
    route_bonus: int = 0
    approach_range: float = 0.0
    approach_slow: float = 0
    bombarded_turn: int = 0

    def __post_init__(self):
        if self.hull is None:
            self.hull = self.max_hull

    @property
    def max_hull(self):
        return self.design.hull if self.design else SHIP_TYPES[self.kind].hull

    @property
    def damage(self):
        return self.design.damage if self.design else SHIP_TYPES[self.kind].damage

    @property
    def drone_bays(self):
        return self.design.drone_bays if self.design else SHIP_TYPES[self.kind].drone_bays

    @property
    def in_transit(self):
        return self.destination is not None and not self.departure_pending

    @property
    def has_course(self):
        return self.destination is not None

    @property
    def name(self):
        return f"{self.design.name if self.design else SHIP_TYPES[self.kind].name} {self.id:03}"

    @classmethod
    def from_dict(cls, data, systems, *, version=29):
        if not isinstance(data, dict) or not _integer(data["id"], 1, 1_000_000):
            raise ValueError
        design = ShipDesign.from_dict(data["design"]) if version >= 18 and data["design"] is not None else None
        if (not isinstance(data["kind"], str) or data["kind"] not in (HULLS if design else SHIP_TYPES)
                or (design and design.kind != data["kind"])):
            raise ValueError
        hull = data["hull"] if version >= 8 else SHIP_TYPES[data["kind"]].hull
        if not _integer(hull, 1, design.hull if design else SHIP_TYPES[data["kind"]].hull):
            raise ValueError
        if not _integer(data["system_id"], 0, len(systems)-1):
            raise ValueError
        destination = data["destination"]
        remaining, total = data["turns_remaining"], data["travel_total"]
        speed_bonus = data["speed_bonus"] if version >= 7 else 0
        pending = data["departure_pending"] if version >= 14 else False
        cruise_speed = (data["cruise_speed"] if version >= 15 else
                        data.get("cruise_speed", LEGACY_SHIP_SPEED if destination is not None else SHIP_SPEED))
        if type(cruise_speed) is not float or cruise_speed not in (SHIP_SPEED, LEGACY_SHIP_SPEED):
            raise ValueError
        if type(pending) is not bool:
            raise ValueError
        speeds = (0, 25, 50, 75, 87.5, 125, 162.5) if version >= 23 else (0, 25, 50, 75)
        if type(speed_bonus) not in (int, float) or speed_bonus not in speeds:
            raise ValueError
        route = {key: data[key] if version >= 25 else default for key, default in
                 (("route_bonus", 0), ("approach_range", 0.0), ("approach_slow", 0), ("bombarded_turn", 0))}
        if (type(route["route_bonus"]) is not int or route["route_bonus"] not in (0, 25, 50)
                or type(route["approach_range"]) not in (int, float) or not math.isfinite(route["approach_range"])
                or not 0 <= route["approach_range"] <= 8
                or type(route["approach_slow"]) not in (int, float) or route["approach_slow"] not in (0, 12.5, 20, 25, 40)
                or bool(route["approach_slow"]) != bool(route["approach_range"])
                or not _integer(route["bombarded_turn"], 0, 1_000_000)):
            raise ValueError("Invalid voyage modifiers")
        if destination is None:
            if (not _integer(remaining, 0, 0) or not _integer(total, 0, 0) or speed_bonus or pending or cruise_speed != SHIP_SPEED
                    or route["route_bonus"] or route["approach_range"] or route["approach_slow"]):
                raise ValueError
        else:
            if not _integer(destination, 0, len(systems)-1) or destination == data["system_id"]:
                raise ValueError
            if route["approach_range"] > distance_ly(systems[data["system_id"]], systems[destination])+1e-9:
                raise ValueError("Interdiction range exceeds the voyage")
            expected = navigation.duration(systems[data["system_id"]], systems[destination], speed_bonus, cruise_speed=cruise_speed,
                                           **{k: v for k, v in route.items() if k != "bombarded_turn"})
            if not _integer(total, expected, expected) or not _integer(remaining, 1, total):
                raise ValueError
            if pending and remaining != total:
                raise ValueError
        record = dict(data)
        record.update(route)
        record["design"] = design
        record["hull"] = hull
        record["speed_bonus"] = speed_bonus
        record["departure_pending"] = pending
        record["cruise_speed"] = cruise_speed
        if version < 5:
            record["owner"] = PLAYER
        if record["owner"] not in EMPIRE_IDS:
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
    resources: int = economy.STARTING_RESOURCES

    @classmethod
    def from_dict(cls, data, systems, turn, *, version=29):
        if not isinstance(data, dict) or not _name(data["name"]):
            raise ValueError
        for key in ("credits", "research"):
            minimum = -1_000_000_000 if key == "credits" and version >= 24 else 0
            if not _integer(data[key], minimum, 1_000_000_000):
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
        technology = ResearchState.from_dict(data["technology"], version=version) if version >= 7 else ResearchState(legacy_starships=True)
        resources = data["resources"] if version >= 27 else economy.STARTING_RESOURCES
        if not _integer(resources, 0, 1_000_000_000):
            raise ValueError("Invalid resource stockpile")
        return cls(**{**data, "events": parsed, "race_id": race_id, "technology": technology, "resources": resources})


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
    ground_battles: list[victory_rules.InvasionReport] = field(default_factory=list)
    resources: int = 0


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
    garrison: int = 0
    militia_losses: int = 0
    slaves: int = 0  # Population units; work and consume food exactly like citizens.
    shield_points: int = 0
    battery_hull: int = 0
    bombarded_turn: int = 0
    miners: int = 0
    disabled_buildings: list[int] = field(default_factory=list)

    @property
    def workforce(self):
        return self.population+self.slaves

    @property
    def workers(self):
        return self.workforce-self.farmers-self.scientists-self.miners

    @property
    def population_capacity(self):
        return population_rules.population_capacity(self)

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
        return colony_yields(self, {})

    @property
    def maintenance_per_turn(self):
        return colony_maintenance(self)

    @property
    def industry_per_turn(self):
        return self.yields_per_turn[0]

    def advance_construction(self, bonuses=None, *, projects=False, fund=None):
        """Use this turn's starting industry, carrying overflow into queued projects."""
        work = colony_yields(self, bonuses or {})[0]
        completed = []
        while work > 0 and self.construction_queue:
            project = self.construction_queue[0]
            if project.needs_resources and (fund is None or not fund(project)):
                break
            applied = min(work, project.remaining_work)
            project.progress += applied
            work -= applied
            if project.remaining_work == 0:
                completed.append(self.finish_current_project(project=projects))
        return completed

    def finish_current_project(self, *, project=False):
        completed = self.construction_queue.pop(0)
        if completed.reserves_slot:
            self.buildings.append(completed.item_id)
        elif completed.item_id == ASCENSION_GATE.id:
            self.ascension_gate, self.gate_charge = True, 0
        return completed if project else completed.item_id

    def queue_estimates(self, additional=None, *, bonuses=None, mortality=None):
        """Industry-only forecast; the campaign forecast also models material supply."""
        if not self.colonized:
            return []
        forecast = replace(self, buildings=self.buildings.copy(),
                           construction_queue=[replace(p) for p in self.construction_queue])
        if additional is not None:
            forecast.construction_queue.append(replace(additional) if isinstance(additional, ConstructionProject) else ConstructionProject(additional))
        turns, estimates = 0, []
        while forecast.construction_queue:
            turns += 1
            food = population_rules.report(forecast, bonuses)
            estimates.extend([turns]*len(forecast.advance_construction(bonuses, fund=lambda p: True)))
            population_rules.advance(forecast, food)
            if mortality and forecast.slaves:
                forecast.slaves -= mortality(forecast.slaves, turns)
                population_rules.clamp_workforce(forecast)
        return estimates

    @classmethod
    def from_dict(cls, data, expected_id, *, version=29):
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
        if type(data["colonized"]) is not bool or not _integer(data["population"], 0, 200 if version >= 23 else 100):
            raise ValueError
        if not data["colonized"] and data["population"] != 0:
            raise ValueError
        record = dict(data)
        for key, maximum in (("shield_points", 200), ("battery_hull", 40), ("bombarded_turn", 1_000_000)):
            if version < 25:
                record[key] = 0
            if not _integer(record[key], 0, maximum):
                raise ValueError("Invalid planetary defenses")
        if ((record["shield_points"] and "planetary_shield" not in record.get("buildings", []))
                or (record["battery_hull"] and "missile_base" not in record.get("buildings", []))):
            raise ValueError("Defense health without a building")
        if version < 23:
            record["slaves"] = 0
        if (not _integer(record["slaves"], 0, raid_rules.SLAVE_CAPACITY)
                or record["slaves"]+data["population"] > 200
                or (not data["colonized"] and record["slaves"])):
            raise ValueError("Invalid slave population")
        if version < 21:
            record["garrison"] = 0
            record["militia_losses"] = 0
        if (not _integer(record["garrison"], 0, ground_rules.MAX_GARRISON)
                or (not data["colonized"] and record["garrison"] != 0)):
            raise ValueError("Invalid planetary garrison")
        if (not _integer(record["militia_losses"], 0, max(104, 4+data["population"]) if version >= 23 else 104)
                or (not data["colonized"] and record["militia_losses"] != 0)):
            raise ValueError("Invalid militia casualties")
        if version < 12:
            record["farmers"] = min(2, data["population"])
            record["scientists"] = 0
        if version < 27:
            record["miners"] = 0
            record["disabled_buildings"] = []
        workforce = data["population"]+record["slaves"]
        if (not _integer(record["farmers"], 0, workforce)
                or not _integer(record["scientists"], 0, workforce)
                or not _integer(record["miners"], 0, workforce)
                or record["farmers"]+record["scientists"]+record["miners"] > workforce):
            raise ValueError("Invalid worker allocation")
        if version < 11:
            record["growth_progress"] = 0
        if (not _integer(record["growth_progress"], 0, population_rules.GROWTH_THRESHOLD-1)
                or (not data["colonized"] and record["growth_progress"] != 0)):
            raise ValueError
        if version < 5:
            record["owner"] = PLAYER if data["colonized"] else None
        if record["owner"] not in (None, *EMPIRE_IDS):
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
        disabled = record["disabled_buildings"]
        if (not isinstance(disabled, list) or any(not _integer(i, 0, len(buildings)-1) for i in disabled)
                or disabled != sorted(set(disabled))):
            raise ValueError("Invalid disabled buildings")
        projects = []
        for i, item in enumerate(queued):
            if not isinstance(item, dict):
                raise ValueError
            item = dict(item)
            if version < 4:
                item["item_id"] = item.pop("building_id")
                if item["item_id"] not in BUILDINGS:
                    raise ValueError
            design = ShipDesign.from_dict(item["design"]) if version >= 18 and item["design"] is not None else None
            item["design"] = design
            if (not isinstance(item["item_id"], str) or
                    (item["item_id"] != design.id if design else item["item_id"] not in PROJECTS)):
                raise ValueError
            spec = design or PROJECTS[item["item_id"]]
            cost, price = spec.work_cost, spec.resource_cost
            if version < 7:
                item["paid_credits"] = price
            if not _integer(item["paid_credits"], 0 if version >= 27 else 1, price):
                raise ValueError
            if version < 27:
                # Old orders already paid their full price in credits.
                item["resource_cost"], item["paid_resources"] = 0, 0
            if (not _integer(item["resource_cost"], 0, price)
                    or not _integer(item["paid_resources"], 0, item["resource_cost"])
                    or item["paid_resources"] not in (0, item["resource_cost"])
                    or (item["resource_cost"] == 0 and item["paid_credits"] == 0)
                    or (item["resource_cost"] and item["paid_credits"])
                    or (item["progress"] and item["paid_resources"] != item["resource_cost"])):
                raise ValueError("Invalid construction resource reservation")
            if not _integer(item["progress"], 0, cost-1) or (version < 12 and i>0 and item["progress"] != 0):
                raise ValueError
            projects.append(ConstructionProject(**item))
        if len(buildings)+sum(p.reserves_slot for p in projects) > BUILDING_SLOTS[data["size"]]:
            raise ValueError
        for identifier, spec in BUILDINGS.items():
            if spec.unique and buildings.count(identifier)+sum(p.item_id == identifier for p in projects) > 1:
                raise ValueError("Duplicate military building")
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
        biome = system.biome if i == 0 else rng.choice(BIOMES[:-1])
        richness = system.richness if i == 0 else rng.choice(RICHNESSES[:-1])
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
    guardians: list[monster_rules.Guardian] = field(default_factory=list)
    designs: list[ShipDesign] = field(default_factory=list)
    other_opponents: dict[str, Opponent] = field(default_factory=dict)
    other_diplomacy: dict[str, DiplomacyState] = field(default_factory=dict)
    tomb_worlds: list[tomb_rules.TombWorld] = field(default_factory=list)
    news_read_turn: int = 0
    raid_events: list[raid_rules.RaidEvent] = field(default_factory=list)
    next_raid_id: int = 1
    raid_news_read: int = 0
    sensor_contacts: list[sensors.Contact] = field(default_factory=list)
    sensor_reports: list[sensors.SensorReport] = field(default_factory=list)
    next_sensor_report_id: int = 1
    sensor_news_read: int = 0
    resources: int = economy.STARTING_RESOURCES

    @property
    def opponents(self):
        return ({RIVAL: self.opponent} if self.opponent is not None else {}) | self.other_opponents

    @property
    def owners(self):
        return (PLAYER, *self.opponents)

    def diplomacy_between(self, first=PLAYER, second=RIVAL):
        if first == second or first not in self.owners or second not in self.owners:
            raise RuleError("Choose two different existing empires.")
        if {first, second} == {PLAYER, RIVAL}:
            return self.diplomacy
        return self.other_diplomacy[relation_key(first, second)]

    def foreign_fleet(self, system_id, owner=PLAYER):
        return [s for s in self.ships if s.owner != owner and not s.in_transit and s.system_id == system_id]

    def opponents_at(self, system_id, owner=PLAYER):
        return [enemy for enemy in self.owners if enemy != owner and
                (self.fleet_at(system_id, enemy) or defense_rules.bases(self, system_id, enemy))]

    def eliminate_defeated(self):
        defeated = {owner for owner in self.owners if not self.colony_systems(owner)}
        if len(self.owners)-len(defeated) > 1:
            self.ships[:] = [ship for ship in self.ships if ship.owner not in defeated]
        for i, owner in enumerate(self.owners):
            for enemy in self.owners[i+1:]:
                if owner in defeated or enemy in defeated:
                    state = self.diplomacy_between(owner, enemy)
                    state.trade_active = state.research_active = False

    def design_for(self, identifier):
        return next((d for d in self.designs if d.id == identifier), None)

    def save_design(self, name, kind, modules, identifier=None):
        self._require_strategy()
        name = name.strip() if isinstance(name, str) else name
        if not _name(name):
            raise RuleError("Choose a name of 1–28 printable characters.")
        error = loadout_error(kind, modules, self.technology.completed, legacy_hulls=self.technology.legacy_starships)
        if error:
            raise RuleError(error)
        if identifier is not None and self.design_for(identifier) is None:
            raise RuleError("Choose an existing design to update.")
        if any(d.name.casefold() == name.casefold() and d.id != identifier for d in self.designs):
            raise RuleError("Another design already uses this name.")
        if identifier is None:
            if len(self.designs) >= MAX_DESIGNS:
                raise RuleError("All 24 design slots are occupied. Update an existing design.")
            identifier = f"design_{len(self.designs)+1}"
        design = ShipDesign(identifier, name, kind, tuple(modules))
        self.designs = [design if d.id == identifier else d for d in self.designs] if self.design_for(identifier) else self.designs+[design]
        return design

    def project_spec(self, identifier):
        return self.design_for(identifier) or PROJECTS[identifier]

    def ship_attack(self, ship):
        return ship.design.damage if ship.design else self.beam_for(ship.kind, ship.owner).damage

    def military_strength(self, ship):
        return self.ship_attack(ship)+ship.drone_bays*combat_rules.DRONES_PER_BAY*combat_rules.DRONE_SPEC.damage

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
        empire = self._empire(owner)
        preferred = (0, 2) if owner == PLAYER else (empire.home_system, empire.home_planet)
        rows = victory_rules.colonies(self, owner)
        return next((row for row in rows if (row[0].id, row[1].id) == preferred), rows[0] if rows else None)

    def invasion_error(self, system_id, planet_id, *, owner=PLAYER):
        return victory_rules.invasion_error(self, system_id, planet_id, owner)

    def invade(self, system_id, planet_id, *, owner=PLAYER):
        defender = self.planet_at(system_id, planet_id).owner
        result = victory_rules.invade(self, system_id, planet_id, owner)
        # Both sides know the outcome even if their last observing unit was lost.
        for empire in (owner, defender):
            exploration_rules.record_survey(self, system_id, empire)
        return result

    def gate_error(self, system_id, planet_id, *, owner=PLAYER):
        return victory_rules.gate_error(self, system_id, planet_id, owner)

    def queue_gate(self, system_id, planet_id, *, owner=PLAYER):
        error = self.gate_error(system_id, planet_id, owner=owner)
        if error:
            raise RuleError(error)
        self.planet_at(system_id, planet_id).construction_queue.append(ConstructionProject(ASCENSION_GATE.id))

    def fleet_at(self, system_id, owner=PLAYER):
        return [s for s in self.ships if s.owner == owner and not s.in_transit and s.system_id == system_id]

    def engagement_error(self, system_id, owner=PLAYER, target=None):
        return combat_rules.engagement_error(self, system_id, owner, target)

    def beam_for(self, kind, owner=PLAYER):
        return combat_rules.BEAMS[combat_rules.weapon_for(self, kind, owner)]

    def start_combat(self, system_id, owner=PLAYER, target=None):
        return combat_rules.begin_combat(self, system_id, owner, target)

    def combat_fire(self, ship_id, target_id, owner=PLAYER):
        return combat_rules.fire(self, ship_id, target_id, owner)

    def combat_launch_drones(self, ship_id, owner=PLAYER):
        return combat_rules.launch_drones(self, ship_id, owner)

    def combat_hold(self, ship_id, owner=PLAYER):
        return combat_rules.hold(self, ship_id, owner)

    def combat_move(self, ship_id, x, y, owner=PLAYER):
        return combat_rules.move(self, ship_id, x, y, owner)

    def combat_end_turn(self, owner=PLAYER):
        return combat_rules.end_turn(self, owner)

    def combat_retreat(self, owner=PLAYER):
        return combat_rules.retreat(self, owner)

    def combat_ai_action(self):
        return combat_rules.ai_action(self, self.combat.active_owner if self.combat else RIVAL)

    def finish_combat(self):
        if self.combat is None or self.combat.status == "active":
            raise RuleError("Finish the battle before returning to the system.")
        system_id = self.combat.system_id
        self.combat = None
        return system_id

    def can_repair(self, ship):
        return (not ship.has_course and any(p.owner == ship.owner for p in self.systems[ship.system_id].worlds)
                and not self.foreign_fleet(ship.system_id, ship.owner))

    def research_state(self, owner=PLAYER):
        return self._empire(owner).technology

    def bonuses_for(self, owner=PLAYER):
        if owner is None:
            return {}
        empire = self._empire(owner)
        bonuses = empire.technology.bonuses.copy()
        for key, value in RACES[empire.race_id].effects:
            bonuses[key] = bonuses.get(key, 0)+value
        return economy.PowerBonuses(bonuses, lambda planet: self._power_report(planet, bonuses))

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
        if discovered and owner != PLAYER:
            self.rival_event(f"Discovered {discovered.name}.", turn=self.turn, owner=owner)
        if discovered:
            exploration_rules.refresh(self)
        return discovered

    def planet_yields(self, planet):
        return colony_yields(planet, self.bonuses_for(planet.owner))

    def planet_maintenance(self, planet):
        return colony_maintenance(planet, self.bonuses_for(planet.owner))

    def bombardment_error(self, system_id, planet_id, owner=PLAYER):
        return defense_rules.bombardment_error(self, system_id, planet_id, owner)

    def bombard(self, system_id, planet_id, owner=PLAYER):
        return defense_rules.bombard(self, system_id, planet_id, owner)

    def population_report(self, planet):
        return population_rules.report(planet, self.bonuses_for(planet.owner or PLAYER))

    def set_workforce(self, system_id, planet_id, farmers, scientists, miners=None, *, owner=PLAYER):
        self._require_strategy()
        planet = self.planet_at(system_id, planet_id)
        self._require_colony(planet, owner)
        miners = planet.miners if miners is None else miners
        if (not _integer(farmers, 0, planet.workforce)
                or not _integer(scientists, 0, planet.workforce)
                or not _integer(miners, 0, planet.workforce)
                or farmers+scientists+miners > planet.workforce):
            raise RuleError("Each population unit can have only one job.")
        planet.farmers, planet.scientists, planet.miners = farmers, scientists, miners

    def move_worker(self, system_id, planet_id, source, destination, *, count=1, owner=PLAYER):
        """Move a whole selected group atomically, retaining one-worker callers."""
        self._require_strategy()
        planet = self.planet_at(system_id, planet_id)
        self._require_colony(planet, owner)
        if source not in population_rules.WORKER_ROLES or destination not in population_rules.WORKER_ROLES or source == destination:
            raise RuleError("Choose two different worker roles.")
        counts = {role: getattr(planet, role) for role in population_rules.WORKER_ROLES}
        if counts[source] < 1:
            raise RuleError("There is no worker in that role to move.")
        if not _integer(count, 1, counts[source]):
            raise RuleError(f"Choose between 1 and {counts[source]} workers from that role.")
        counts[source] -= count
        counts[destination] += count
        self.set_workforce(system_id, planet_id, counts["farmers"], counts["scientists"], counts["miners"], owner=owner)

    def building_yields(self, definition, planet):
        return building_yields(definition, planet.richness, self.bonuses_for(planet.owner or PLAYER))

    def queue_estimates(self, planet, additional=None):
        from .economy_forecast import queue_estimates
        return queue_estimates(self, planet, additional)

    def resource_rate(self, owner=PLAYER):
        return sum(self.planet_resources(p) for s in self.systems for p in s.worlds if p.owner == owner)

    def resources_for(self, owner=PLAYER):
        return self._empire(owner).resources

    def planet_resources(self, planet):
        bonuses = self.bonuses_for(planet.owner)
        return economy.mining_output(planet, bonuses)-economy.energy_report(planet, bonuses).fuel_used

    def planet_energy(self, planet):
        return economy.energy_report(planet, self.bonuses_for(planet.owner))

    def _power_report(self, planet, bonuses):
        frozen = getattr(self, "_turn_power", {})
        if id(planet) in frozen:
            return frozen[id(planet)]
        # Most colonies have no fuel-burning plant; their grid stays fully local.
        if not any(BUILDINGS[b].energy_per_resource for b in planet.buildings):
            return economy.energy_report(planet, bonuses)
        worlds = [p for s in self.systems for p in s.worlds if p.colonized and p.owner == planet.owner]
        if not any(p is planet for p in worlds):
            # AI projected colonies are evaluated conservatively on steady power.
            return economy.energy_report(planet, bonuses)
        bank = self.resources_for(planet.owner)
        signature = (bank, tuple(sorted(bonuses.items())), tuple(
            (id(p), tuple(p.buildings), tuple(p.disabled_buildings), p.ascension_gate) for p in worlds))
        cache = getattr(self, "_power_cache", {})
        if planet.owner not in cache or cache[planet.owner][0] != signature:
            cache[planet.owner] = (signature, economy.dispatch_power(worlds, bonuses, bank))
            self._power_cache = cache
        return cache[planet.owner][1][id(planet)]

    def _settle_power(self):
        self._turn_power = {}
        for owner in self.owners:
            worlds = [p for s in self.systems for p in s.worlds if p.colonized and p.owner == owner]
            self._turn_power.update(economy.dispatch_power(worlds, dict(self.bonuses_for(owner)), self.resources_for(owner)))

    def building_operational(self, planet, identifier):
        return economy.operational(planet, identifier, self.bonuses_for(planet.owner))

    def fund_project(self, project, owner=PLAYER):
        empire = self._empire(owner)
        if project.needs_resources > empire.resources:
            return False
        empire.resources -= project.needs_resources
        project.paid_resources = project.resource_cost
        return True

    def construction_status(self, planet):
        if not planet.construction_queue:
            return "No project queued"
        missing = planet.construction_queue[0].needs_resources-self.resources_for(planet.owner)
        return f"Waiting for {missing} resources" if missing > 0 else "Resources ready" if planet.construction_queue[0].needs_resources else "Resources reserved"

    def toggle_building(self, system_id, planet_id, index, *, owner=PLAYER):
        self._require_strategy()
        planet = self.planet_at(system_id, planet_id)
        self._require_colony(planet, owner)
        if not _integer(index, 0, len(planet.buildings)-1):
            raise RuleError("Choose an existing building.")
        if index in planet.disabled_buildings:
            planet.disabled_buildings.remove(index)
        else:
            planet.disabled_buildings.append(index)
            planet.disabled_buildings.sort()
        exploration_rules.refresh(self)

    def project_price(self, item_id, owner=PLAYER):
        if item_id == ASCENSION_GATE.id:
            return ASCENSION_GATE.resource_cost
        key = "building_discount" if item_id in BUILDINGS else "ship_discount"
        discount = self.bonuses_for(owner).get(key, 0)
        return max(1, math.ceil(self.project_spec(item_id).resource_cost*(100-discount)/100))

    def travel_turns(self, origin, destination, owner=PLAYER):
        bonus, radius, slow = navigation.route_modifiers(self, origin, destination, owner)
        return navigation.duration(origin, destination, self.ship_speed_bonus(owner),
                                   route_bonus=bonus, approach_range=radius, approach_slow=slow)

    def ship_speed_bonus(self, owner=PLAYER):
        bonuses = self.bonuses_for(owner)
        value = (100+bonuses.get("ship_speed", 0))*(100+bonuses.get("ship_speed_percent", 0))/100-100
        return int(value) if value.is_integer() else value

    def fuel_range(self, owner=PLAYER):
        bonuses = self.bonuses_for(owner)
        value = (BASE_FUEL_RANGE+bonuses.get("fuel_range", 0))*(100+bonuses.get("fuel_range_percent", 0))/100
        return int(value) if value.is_integer() else value

    def colony_systems(self, owner=PLAYER):
        return [s for s in self.systems if any(p.owner == owner for p in s.worlds)]

    def supply_distance(self, destination, owner=PLAYER):
        """Distance to the nearest real colony; exploration never extends supply."""
        target = self.systems[destination]
        return min((distance_ly(s, target) for s in self.colony_systems(owner)), default=math.inf)

    def within_fuel_range(self, destination, owner=PLAYER):
        return self.supply_distance(destination, owner) <= self.fuel_range(owner)+1e-9

    def fuel_range_error(self, destination, owner=PLAYER):
        if not self.within_fuel_range(destination, owner):
            advice = "Research fuel tanks to extend your raiding range." if raid_rules.is_varkesh(self, owner) else "Colonize closer worlds or research fuel tanks."
            return (f"Out of fuel range: {self.systems[destination].name} is "
                    f"{self.supply_distance(destination, owner):.1f} ly from your nearest colony "
                    f"(range {self.fuel_range(owner)} ly). {advice}")
        return None

    def can_settle(self, planet, owner=PLAYER):
        if raid_rules.is_varkesh(self, owner):
            return False
        return planet.habitability > 0 or bool(self.bonuses_for(owner).get(planet.biome.lower(), 0))

    def starting_colonists(self, owner=PLAYER):
        return STARTING_COLONISTS+self.bonuses_for(owner).get("colonists", 0)

    def diplomacy_error(self, action, target=RIVAL):
        return action_error(self, action, target)

    def diplomacy_action(self, action, target=RIVAL):
        return take_action(self, action, target)

    def diplomatic_yields(self, owner=PLAYER):
        return agreement_yields(self, owner)

    def _empire(self, owner):
        if owner == PLAYER:
            return self
        if owner in self.opponents:
            return self.opponents[owner]
        raise RuleError("Unknown empire.")

    def treasury_for(self, owner=PLAYER):
        return self._empire(owner).credits

    def research_for(self, owner=PLAYER):
        return self._empire(owner).research

    def empire_name_for(self, owner):
        if owner is None:
            return "Unclaimed"
        if owner == monster_rules.MONSTER:
            return "System guardian"
        return self.empire_name if owner == PLAYER else self._empire(owner).name

    def ships_owned_by(self, owner=PLAYER):
        return [ship for ship in self.ships if ship.owner == owner]

    def _require_colony(self, planet, owner):
        self._empire(owner)
        if planet.owner != owner:
            raise RuleError("You can only manage colonies belonging to your empire.")

    def rival_event(self, message, *, turn=None, owner=RIVAL):
        empire = self._empire(owner)
        # Orders occur now; an invasion can end this turn before the year advances.
        empire.events.append(AIEvent(self.turn if turn is None else turn, message))
        empire.events = empire.events[-12:]

    def opponent_home(self):
        """Choose a habitable home far from every existing player colony."""
        occupied = [s for s in self.systems if any(p.owner == PLAYER for p in s.worlds)]
        candidates = [(s, p) for s in self.systems if s not in occupied and monster_rules.at(self, s.id) is None
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
        self._place_opponent(RIVAL, race_id, system, planet, "Helios Directorate")
        exploration_rules.refresh(self)
        return planet

    def _place_opponent(self, owner, race_id, system, planet, name):
        name_home(self, system, planet, race_id)
        self._register_opponent(owner, race_id, system, planet, name)
        planet.colonized, planet.owner, planet.population = True, owner, 8
        planet.farmers, planet.scientists, planet.miners = 2, 0, 2
        if not population_rules.food_required(8, self.bonuses_for(owner)):
            planet.farmers = 0
        self._starting_fleet(owner, system.id)
        self.rival_event(f"Established its homeworld on {planet.name}.", turn=self.turn, owner=owner)

    def _register_opponent(self, owner, race_id, system, planet, name):
        """Register an empire without granting starting ships or changing its world."""
        previous = self.owners
        empire = Opponent(name, system.id, planet.id, race_id=race_id,
                          research=RACES[race_id].starting_research)
        if owner == RIVAL:
            self.opponent = empire
            self.diplomacy = make_contact(self.turn, name, race_id)
        else:
            self.other_opponents[owner] = empire
            self.exploration.scanned_others[owner] = []
            for first in previous:
                self.other_diplomacy[relation_key(first, owner)] = make_contact(self.turn, name, race_id)

    def _starting_fleet(self, owner, system_id):
        """One initial exploration and settlement fleet, created with the empire."""
        kinds = (("scout", "scout", "frigate", "troop_transport", "troop_transport")
                 if raid_rules.is_varkesh(self, owner) else ("scout", "scout", "colony_ship"))
        for kind in kinds:
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
        technology = BUILDINGS[building_id].technology
        if technology and not self.research_state(owner).has_unlock(technology):
            from .research import TECHNOLOGIES
            return "Requires "+TECHNOLOGIES[technology].name+"."
        if BUILDINGS[building_id].unique and (building_id in planet.buildings or
                any(p.item_id == building_id for p in planet.construction_queue)):
            return "Only one of this building is allowed per colony."
        if len(planet.construction_queue) >= MAX_QUEUE:
            return "The construction queue is full."
        if planet.free_slots <= 0:
            return f"All {planet.building_capacity} building slots are occupied or reserved."
        return None

    def queue_building(self, system_id, planet_id, building_id, *, owner=PLAYER):
        error = self.build_error(system_id, planet_id, building_id, owner=owner)
        if error:
            raise RuleError(error)
        planet = self.planet_at(system_id, planet_id)
        price = self.project_price(building_id, owner)
        planet.construction_queue.append(ConstructionProject(building_id, resource_cost=price))

    def project_error(self, system_id, planet_id, item_id, *, owner=PLAYER):
        if not isinstance(item_id, str):
            return "Unknown construction project."
        if item_id in BUILDINGS:
            return self.build_error(system_id, planet_id, item_id, owner=owner)
        if item_id in SHIP_TYPES or self.design_for(item_id):
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
        elif item_id in SHIP_TYPES or self.design_for(item_id):
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
        if planet.construction_queue[0].needs_resources > self.resources_for(owner):
            return "Not enough resources to finish this project."
        if self.treasury_for(owner) < self.buy_construction_cost(system_id, planet_id):
            return "Not enough credits to finish this project."
        return None

    def buy_construction(self, system_id, planet_id, *, owner=PLAYER):
        error = self.buy_construction_error(system_id, planet_id, owner=owner)
        if error:
            raise RuleError(error)
        planet = self.planet_at(system_id, planet_id)
        self.fund_project(planet.construction_queue[0], owner)
        self._empire(owner).credits -= self.buy_construction_cost(system_id, planet_id)
        project = planet.finish_current_project(project=True)
        defense_rules.commissioned(self, planet, project.item_id)
        self._complete_ship(project, system_id, owner)
        return project.item_id

    def _complete_ship(self, project, system_id, owner):
        if project.is_ship:
            kind = project.design.kind if project.design else project.item_id
            self.ships.append(Ship(self.next_ship_id, kind, system_id, owner=owner, design=project.design))
            self.next_ship_id += 1

    def ship_build_error(self, system_id, planet_id, kind="colony_ship", *, owner=PLAYER):
        if self.strategy_error():
            return self.strategy_error()
        planet = self.planet_at(system_id, planet_id)
        design = self.design_for(kind) if isinstance(kind, str) and owner == PLAYER else None
        if not isinstance(kind, str) or (kind not in SHIP_TYPES and design is None):
            return "Unknown ship type."
        if design and loadout_error(design.kind, design.modules, self.technology.completed,
                                    legacy_hulls=self.technology.legacy_starships):
            return "This design requires undiscovered technology."
        if not design and not self.research_state(owner).hull_unlocked(kind):
            return f"Requires {TECHNOLOGIES[SHIP_TYPES[kind].technology].name}."
        if not planet.colonized:
            return "Ships can only be built at an established colony."
        if planet.owner != owner:
            return "This colony belongs to another empire."
        if kind == "troop_transport" and not self.building_operational(planet, "barracks"):
            return "Build and power barracks on this colony to train transport troops."
        if kind == "colony_ship" and raid_rules.is_varkesh(self, owner):
            return "The Varkesh cannot colonize. Build a raiding fleet instead."
        if len(planet.construction_queue) >= MAX_QUEUE:
            return "The construction queue is full."
        return None

    def queue_ship(self, system_id, planet_id, kind="colony_ship", *, owner=PLAYER):
        error = self.ship_build_error(system_id, planet_id, kind, owner=owner)
        if error:
            raise RuleError(error)
        planet = self.planet_at(system_id, planet_id)
        price = self.project_price(kind, owner)
        planet.construction_queue.append(ConstructionProject(kind, resource_cost=price, design=self.design_for(kind)))

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
        error = self.fuel_range_error(destination, owner)
        if error:
            raise RuleError(error)
        for ship in ships:
            duration = self._dispatch_ship(ship, destination, pending=True)
        return duration

    @staticmethod
    def _clear_course(ship):
        ship.destination = None
        ship.turns_remaining = ship.travel_total = ship.speed_bonus = 0
        ship.departure_pending = False
        ship.cruise_speed = SHIP_SPEED
        ship.route_bonus, ship.approach_range, ship.approach_slow = 0, 0.0, 0

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
        ship.speed_bonus = self.ship_speed_bonus(ship.owner)
        ship.route_bonus, ship.approach_range, ship.approach_slow = navigation.route_modifiers(
            self, self.systems[ship.system_id], self.systems[destination], ship.owner)
        ship.cruise_speed = SHIP_SPEED
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
        if raid_rules.is_varkesh(self, owner):
            return "The Varkesh cannot colonize. Raid inhabited worlds for captives and credits."
        planet = self.planet_at(system_id, planet_id)
        if planet.colonized:
            return "This planet is already colonized."
        guardian = monster_rules.alive_at(self, system_id)
        if guardian:
            return f"Defeat the {guardian.spec.name} guarding this system first."
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
        planet.farmers = 0
        planet.farmers = population_rules.farmers_needed(planet, self.bonuses_for(owner), surplus=1)
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
        self._empire(owner).resources += project.resource_refund
        return project.refund_text

    def demolish_building(self, system_id, planet_id, building_index, *, owner=PLAYER):
        self._require_strategy()
        planet = self.planet_at(system_id, planet_id)
        self._require_colony(planet, owner)
        if not _integer(building_index, 0, len(planet.buildings)-1):
            raise RuleError("That building is no longer on this planet.")
        identifier = economy.remove_building(planet, building_index)
        defense_rules.normalize(planet)
        return identifier

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
        try:
            return self._advance_turn()
        finally:
            self.__dict__.pop("_turn_power", None)

    def _advance_turn(self):
        """AI orders, starting yields, travel and local production, then bank income."""
        self._require_strategy()
        exploration_rules.refresh(self)
        if monster_rules.intercept(self):
            return TurnReport(0, 0, [])
        if combat_rules.intercept(self):
            return TurnReport(0, 0, [])
        # End Turn commits existing orders before the AI plans against current positions.
        for ship in self.ships:
            ship.departure_pending = False
        exploration_rules.refresh(self)
        repairable = {ship.id for ship in self.ships if self.can_repair(ship)}
        alerts, ground_battles = [], []
        slave_start = {(s.id, p.id): (p.owner, p.slaves) for s in self.systems for p in s.worlds if p.slaves}
        from .ai import run_ai
        for owner in self.opponents:
            if not self.colony_systems(owner):
                continue
            alerts.extend(run_ai(self, owner, ground_reports=ground_battles))
            if self.result is not None:
                return TurnReport(0, 0, [], alerts=alerts, ground_battles=ground_battles)
        advance_diplomacy(self)
        self._settle_power()
        gates = [(s.id, p.id, p.owner) for s in self.systems for p in s.worlds if p.ascension_gate and self.planet_energy(p).gate_powered]
        income, research = self.empire_rates
        rival_rates = {owner: self.empire_rates_for(owner) for owner in self.opponents}
        population_start = [(p, self.population_report(p)) for s in self.systems
                            for p in s.worlds if p.colonized]
        # Newly completed barracks begin training on the following turn.
        for planet, _ in population_start:
            ground_rules.train(planet, self.bonuses_for(planet.owner))
        arrivals = []
        for ship in self.ships:
            if ship.has_course:
                ship.departure_pending = False
                ship.turns_remaining -= 1
                if ship.turns_remaining == 0:
                    ship.system_id = ship.destination
                    self._clear_course(ship)
                    message = f"{ship.name} at {self.systems[ship.system_id].name}"
                    if ship.owner == PLAYER:
                        arrivals.append(message)
                    else:
                        self.rival_event(f"Arrived: {message}.", owner=ship.owner)
        resource_rates = {owner: self.resource_rate(owner) for owner in self.owners}
        for owner, amount in resource_rates.items():
            self._empire(owner).resources += amount
        for planet, _ in population_start:
            if planet.owner == PLAYER and self.planet_energy(planet).balance < 0:
                report = self.planet_energy(planet)
                affected = f"{len(report.offline)} buildings offline"
                if planet.ascension_gate and not report.gate_powered:
                    affected += "; Ascension Gate unpowered"
                alerts.append(f"Energy shortage on {planet.name}: {affected}")
        completed = []
        for system in self.systems:
            for planet in system.worlds:
                for project in planet.advance_construction(self.bonuses_for(planet.owner), projects=True,
                        fund=lambda project: self.fund_project(project, planet.owner)):
                    defense_rules.commissioned(self, planet, project.item_id)
                    item_id = project.item_id
                    self._complete_ship(project, system.id, planet.owner)
                    message = f"{project.spec.name} on {planet.name}"
                    if planet.owner == PLAYER:
                        completed.append(message)
                    else:
                        self.rival_event(f"Completed: {message}.", owner=planet.owner)
                        if item_id == ASCENSION_GATE.id:
                            location = exploration_rules.gate_location(self, system.id, planet)
                            alerts.append(f"Rival gate completed at {location}: five charging turns remain")
        for planet, _ in population_start:
            if planet.owner == PLAYER and planet.construction_queue and planet.construction_queue[0].needs_resources > self.resources:
                alerts.append(f"{planet.name}: {self.construction_status(planet)}")
        self.turn += 1
        self.year += 1
        defense_rules.advance(self)
        self.credits += income
        if income < 0:
            alerts.append(f"Budget deficit: {income} CR/turn after building maintenance")
        if self.credits < 0:
            alerts.append(f"Treasury debt: {-self.credits} CR; future income repays it")
        self.research += research
        population = []
        for planet, start in population_start:
            if population_rules.advance(planet, start):
                message = f"{planet.name} grew to {planet.population} B"
                if planet.owner == PLAYER:
                    population.append(message)
                else:
                    self.rival_event(message+".", turn=self.turn, owner=planet.owner)
        population.extend(raid_rules.advance_mortality(self, slave_start))
        exploration = exploration_rules.refresh(self, recover=True)
        discovered = self.advance_research()
        for owner, empire in self.opponents.items():
            empire.credits += rival_rates[owner][0]
            empire.research += rival_rates[owner][1]
            self.advance_research(owner)
        for ship in self.ships:
            if ship.id in repairable and self.can_repair(ship):
                ship.hull = min(ship.max_hull, ship.hull+REPAIR_PER_TURN)
        victory_rules.advance_gates(self, gates)
        for owner in self.opponents:
            rival_gate = victory_rules.gate_site(self, owner)
            if (rival_gate and rival_gate[1].gate_charge == GATE_CHARGE_TURNS-1
                    and not victory_rules.gate_blocked(self, rival_gate[0].id, owner)):
                location = exploration_rules.gate_location(self, rival_gate[0].id, rival_gate[1])
                alerts.append(f"{self.empire_name_for(owner)} gate at {location} will activate next turn unless blocked")
        self.__dict__.pop("_turn_power", None)
        tomb_rules.advance(self, alerts, ground_battles)
        exploration_rules.refresh(self)
        monster_rules.intercept(self)
        self.check_victory()
        combat_rules.intercept(self)
        return TurnReport(income, research, completed, arrivals,
                          [discovered.name] if discovered else [], alerts, exploration, population, ground_battles, resource_rates.get(PLAYER, 0))

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data, *, version=29):
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
            if not _integer(data["credits"], -1_000_000_000 if version >= 24 else 0, 1_000_000_000):
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
                diplomacy = DiplomacyState.from_dict(data["diplomacy"], data["turn"], version=version) if data["diplomacy"] is not None else None
                if (opponent is None) != (diplomacy is None):
                    raise ValueError
            else:
                diplomacy = make_contact(data["turn"], opponent.name, opponent.race_id) if opponent else None
            technology = ResearchState.from_dict(data["technology"], version=version) if version >= 7 else ResearchState(legacy_starships=True)
            game = cls(campaign, data["empire_name"], size, data["seed"],
                       data["turn"], data["year"], data["credits"], systems, selected, planet,
                       research, ships, next_ship, opponent, race_id, diplomacy, technology)
            game.resources = data["resources"] if version >= 27 else economy.STARTING_RESOURCES
            if not _integer(game.resources, 0, 1_000_000_000):
                raise ValueError("Invalid resource stockpile")
            if version >= 20:
                extras, relations = data["other_opponents"], data["other_diplomacy"]
                roster = CAMPAIGN_RIVAL_IDS if version >= 22 else RIVAL_IDS
                if (not isinstance(extras, dict) or len(extras) >= len(roster)
                        or set(extras) != set(roster[1:len(extras)+1]) or (extras and opponent is None)):
                    raise ValueError("Invalid rival roster")
                game.other_opponents = {owner: Opponent.from_dict(extras[owner], systems, game.turn, version=version)
                                        for owner in roster[1:len(extras)+1]}
                keys = {relation_key(a, b) for i, a in enumerate(game.owners) for b in game.owners[i+1:]
                        if {a, b} != {PLAYER, RIVAL}}
                if not isinstance(relations, dict) or set(relations) != keys:
                    raise ValueError("Invalid diplomatic relationships")
                game.other_diplomacy = {key: DiplomacyState.from_dict(row, game.turn, version=version) for key, row in relations.items()}
            if (any(p.owner is not None and p.owner not in game.owners for s in systems for p in s.worlds)
                    or any(s.owner not in game.owners for s in ships)):
                raise ValueError("Unknown empire owns a colony or ship")
            if version >= 23:
                raid_rules.load_state(game, data)
            if version >= 18:
                if not isinstance(data["designs"], list) or len(data["designs"]) > MAX_DESIGNS:
                    raise ValueError("Invalid design library")
                game.designs = [ShipDesign.from_dict(d) for d in data["designs"]]
                if ([d.id for d in game.designs] != [f"design_{i+1}" for i in range(len(game.designs))]
                        or len({d.name.casefold() for d in game.designs}) != len(game.designs)):
                    raise ValueError("Duplicate ship designs")
                snapshots = game.designs+[s.design for s in ships if s.design and s.owner == PLAYER]
                snapshots += [p.design for s in systems for w in s.worlds if w.owner == PLAYER for p in w.construction_queue if p.design]
                if any(loadout_error(d.kind, d.modules, technology.completed,
                                     legacy_hulls=technology.legacy_starships) for d in snapshots):
                    raise ValueError("Undiscovered ship equipment")
            if version >= 22:
                game.tomb_worlds = tomb_rules.parse(data["tomb_worlds"], game)
                if not _integer(data["news_read_turn"], 0, game.turn):
                    raise ValueError("Invalid news read turn")
                game.news_read_turn = data["news_read_turn"]
                if "rival_6" in game.opponents and (
                        game.opponents["rival_6"].race_id != "remnant"
                        or not any(t.remnant_owner == "rival_6" for t in game.tomb_worlds)):
                    raise ValueError("The extra rival must be an awakened Remnant enclave")
            if version >= 16:
                game.guardians = monster_rules.parse_guardians(data["guardians"], game, version=version)
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
            if version >= 25:
                sensors.load(game, data)
                if (any(s.bombarded_turn > game.turn for s in game.ships)
                        or any(p.bombarded_turn > game.turn for s in game.systems for p in s.worlds)):
                    raise ValueError("Bombardment timestamp is in the future")
            if version < 26:
                first_contact.migrate(game)
            return game
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise SaveError("This save contains invalid game data.") from exc


def new_game(empire_name="Terran Union", galaxy_size="Standard", seed=None, *, with_ai=True,
             race_id="terran", rival_race_id=None, fog_of_war=True, with_guardians=True,
             rival_count=None, random_starts=True, with_tombs=True):
    if not _name(empire_name) or galaxy_size not in GALAXY_SIZES:
        raise SaveError("Enter an empire name and choose a galaxy size.")
    if type(fog_of_war) is not bool:
        raise SaveError("Fog of war must be on or off.")
    if type(with_guardians) is not bool:
        raise SaveError("Guardians must be on or off.")
    if not isinstance(race_id, str) or race_id not in RACES:
        raise SaveError("Choose a valid player race.")
    if rival_race_id is not None and (not isinstance(rival_race_id, str) or rival_race_id not in RACES):
        raise SaveError("Choose a valid rival race.")
    count_rivals = (1 if with_ai else 0) if rival_count is None else rival_count
    if not _integer(count_rivals, 0, MAX_RIVALS):
        raise SaveError(f"Choose between 0 and {MAX_RIVALS} rivals.")
    if type(random_starts) is not bool:
        raise SaveError("Random starts must be on or off.")
    if seed is None:
        seed = random.SystemRandom().randrange(1_000_000_000)
    if not _integer(seed, 0, 999_999_999):
        raise SaveError("Seed must be a whole number between 0 and 999999999.")
    rng = random.Random(seed)
    names = NAMES.copy()
    rng.shuffle(names)
    systems = [StarSystem(0, "Sol", .35, .55, "Yellow dwarf", 4, "Terran", "Average")]
    starts = random.Random(f"orion-starts-v1:{seed}")
    left, right, top, bottom = GALAXY_BOUNDS
    if random_starts:
        # Keep the starting world's properties, but place its system anywhere.
        systems[0].x, systems[0].y = starts.uniform(left, right), starts.uniform(top, bottom)
    count = GALAXY_SIZES[galaxy_size]
    for i in range(1, count):
        for _ in range(2000):
            x, y = rng.uniform(left, right), rng.uniform(top, bottom)
            if all(100*math.hypot((x-s.x)*1.4, y-s.y) >= MIN_STAR_DISTANCE for s in systems):
                break
        else:
            raise SaveError("Could not place this galaxy. Please try a different seed.")
        systems.append(StarSystem(i, names[i-1], x, y, rng.choice(STAR_TYPES),
                                  rng.randint(0, 7), rng.choice(BIOMES[:-1]), rng.choice(RICHNESSES[:-1])))
    for system in systems:
        system.worlds = generate_planets(system, seed)
    game = GameState(uuid4().hex, empire_name.strip(), galaxy_size, seed, 1, 2300, 120, systems,
                     race_id=race_id, fog_of_war=fog_of_war)
    name_home(game, systems[0], systems[0].worlds[2], race_id)
    game.research = RACES[race_id].starting_research
    if not population_rules.food_required(8, game.bonuses_for()):
        game.planet_at(0, 2).farmers = 0
    game.planet_at(0, 2).miners = 2
    game._starting_fleet(PLAYER, 0)
    if not random_starts and count_rivals <= 1:
        if count_rivals and game.opponent_start_error() is None:
            game.add_opponent(rival_race_id)
    else:
        races = [rid for rid in RACES if rid != race_id and rid != rival_race_id]
        starts.shuffle(races)
        if rival_race_id:
            races.insert(0, rival_race_id)
        homes = [systems[0]]
        for owner, rid in zip(RIVAL_IDS[:count_rivals], races):
            candidates = [s for s in systems if s not in homes and s.worlds]
            separated = [s for s in candidates if all(distance_ly(s, h) >= 20 for h in homes)]
            system = starts.choice(separated) if separated else max(candidates, key=lambda s: min(distance_ly(s, h) for h in homes))
            # Equal foundations: race traits, rather than a lucky starting biome, set the opening economy.
            planet = starts.choice(system.worlds)
            planet.biome, planet.size, planet.richness, planet.gravity = "Terran", "Medium", "Average", "Normal"
            if planet.id == 0:
                system.biome, system.richness = planet.biome, planet.richness
            game._place_opponent(owner, rid, system, planet, RACES[rid].default_empire)
            homes.append(system)
    if with_guardians:
        monster_rules.seed_guardians(game)
    if with_tombs:
        tomb_rules.seed_worlds(game)
    exploration_rules.refresh(game)
    return game
