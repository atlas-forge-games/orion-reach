"""Standalone battle fixtures using the real combat rules, never campaign saves."""

from dataclasses import asdict, dataclass, field
from pathlib import Path
import json

from . import balance, defenses, exploration, motherships, species
from .combat import battle_ship
from .designs import MAX_DESIGNS, ShipDesign
from .model import GameState, Opponent, Planet, Ship, StarSystem
from .diplomacy import DiplomacyState
from .production import SHIP_TYPES
from .races import RACES
from .research import ResearchState
from .storage import atomic_json

FORMAT = "orion-reach-combat-scenario"
VERSION = 1
MAX_SHIPS = 60
MAX_BASES = 3
ROUND_LIMIT = 300
SIDES = ("player", "rival")
UPGRADES = {
    "none": ("No combat upgrades", ()),
    "targeting": ("Targeting computers", ("targeting_computers",)),
    "advanced": ("Advanced combat upgrades", (
        "precision_beam_optics", "electronic_countermeasures", "quantum_optics",
        "torpedo_guidance", "quantum_targeting")),
}
UPGRADE_DETAILS = {
    "none": "Base accuracy; standard ship weapons. Custom equipment is always available.",
    "targeting": "Targeting Computers research. Custom equipment is always available.",
    "advanced": "Quantum Targeting, Electronic Countermeasures, Precision Beam Optics, Quantum Optics and Advanced Torpedo Guidance.",
}


class ScenarioError(ValueError):
    """A scenario cannot be edited, loaded or launched as requested."""


def integer(value, lower, upper):
    return type(value) is int and lower <= value <= upper


@dataclass
class FleetSetup:
    race: str = "terran"
    upgrades: str = "none"
    ships: dict[str, int] = field(default_factory=lambda: {"frigate": 3, "destroyer": 1})
    bases: int = 0

    @property
    def count(self):
        return sum(self.ships.values())


@dataclass
class Scenario:
    name: str = "Fleet skirmish"
    seed: int = 2408
    first: str = "player"
    accuracy: bool = True
    player: FleetSetup = field(default_factory=FleetSetup)
    rival: FleetSetup = field(default_factory=FleetSetup)
    designs: list[ShipDesign] = field(default_factory=list)

    def fleet(self, side):
        return getattr(self, side)

    def design(self, identifier):
        return next((d for d in self.designs if d.id == identifier), None)

    def validate(self, *, battle=False):
        if (not isinstance(self.name, str) or not 1 <= len(self.name) <= 28
                or self.name != self.name.strip() or not self.name.isprintable()):
            raise ScenarioError("Choose a scenario name of 1–28 printable characters.")
        if not integer(self.seed, 0, 999_999_999):
            raise ScenarioError("Use a seed between 0 and 999999999.")
        if not isinstance(self.first, str) or self.first not in SIDES or type(self.accuracy) is not bool:
            raise ScenarioError("Choose the starting side and accuracy mode.")
        if not isinstance(self.designs, list) or len(self.designs) > MAX_DESIGNS:
            raise ScenarioError("A scenario supports up to 24 custom designs.")
        identifiers, names = set(), set()
        for design in self.designs:
            if not isinstance(design, ShipDesign):
                raise ScenarioError("Invalid custom ship design.")
            try:
                ShipDesign.from_dict(asdict(design))
            except (ValueError, TypeError, KeyError) as exc:
                raise ScenarioError(f"Invalid design: {design.name}.") from exc
            if design.id in identifiers or design.name.casefold() in names:
                raise ScenarioError("Custom designs need unique names and identifiers.")
            identifiers.add(design.id)
            names.add(design.name.casefold())
        catalogue = set(SHIP_TYPES) | identifiers
        for side in SIDES:
            fleet = self.fleet(side)
            if not isinstance(fleet, FleetSetup):
                raise ScenarioError("Invalid fleet setup.")
            if not isinstance(fleet.race, str) or fleet.race not in RACES:
                raise ScenarioError("Choose a playable race for each fleet.")
            if not isinstance(fleet.upgrades, str) or fleet.upgrades not in UPGRADES:
                raise ScenarioError("Unknown combat upgrade selection.")
            if not integer(fleet.bases, 0, MAX_BASES):
                raise ScenarioError(f"Each fleet can have 0–{MAX_BASES} planetary missile bases.")
            if (not isinstance(fleet.ships, dict) or len(fleet.ships) > len(catalogue)
                    or any(not isinstance(k, str) or k not in catalogue
                           or not integer(v, 1, MAX_SHIPS) for k, v in fleet.ships.items())
                    or fleet.count > MAX_SHIPS):
                raise ScenarioError(f"Choose known ships, up to {MAX_SHIPS} per side.")
            if battle and not fleet.count and not fleet.bases:
                raise ScenarioError("Add at least one ship or missile base to each side.")
        if battle:
            initiating = self.fleet(self.first)
            armed = initiating.bases or any(
                (self.design(k).damage or self.design(k).drone_bays) if self.design(k)
                else (SHIP_TYPES[k].damage or SHIP_TYPES[k].drone_bays) for k in initiating.ships)
            if not armed:
                raise ScenarioError("The side moving first needs a weapon, carrier or missile base.")

    def change(self, side, identifier, amount):
        fleet = self.fleet(side)
        if identifier not in SHIP_TYPES and self.design(identifier) is None:
            raise ScenarioError("Choose a ship from the catalogue.")
        count = max(0, fleet.ships.get(identifier, 0)+amount)
        if fleet.count-fleet.ships.get(identifier, 0)+count > MAX_SHIPS:
            raise ScenarioError(f"The simulator supports {MAX_SHIPS} ships per side.")
        if count:
            fleet.ships[identifier] = count
        else:
            fleet.ships.pop(identifier, None)

    @classmethod
    def from_dict(cls, data):
        try:
            if not isinstance(data, dict) or set(data) != {"name", "seed", "first", "accuracy", "player", "rival", "designs"}:
                raise ScenarioError("Invalid combat scenario fields.")
            if not isinstance(data["designs"], list) or len(data["designs"]) > MAX_DESIGNS:
                raise ScenarioError("Invalid custom design list.")
            fleets = {}
            for side in SIDES:
                value = data[side]
                if not isinstance(value, dict) or set(value) != {"race", "upgrades", "ships", "bases"}:
                    raise ScenarioError("Invalid fleet fields.")
                fleets[side] = FleetSetup(**value)
            result = cls(**{k: data[k] for k in ("name", "seed", "first", "accuracy")},
                         **fleets, designs=[ShipDesign.from_dict(d) for d in data["designs"]])
            result.validate()
            return result
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            if isinstance(exc, ScenarioError):
                raise
            raise ScenarioError("Invalid combat scenario or ship design.") from exc


def load_scenario(path):
    path = Path(path)
    try:
        if path.stat().st_size > 1_000_000:
            raise ScenarioError("This combat scenario is too large.")
        data = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(data, dict) or data.get("format") != FORMAT
                or type(data.get("version")) is not int or data["version"] != VERSION):
            raise ScenarioError("Choose a supported combat scenario JSON file.")
        return Scenario.from_dict(data.get("scenario"))
    except (OSError, ValueError, RecursionError) as exc:
        if isinstance(exc, ScenarioError):
            raise
        raise ScenarioError(f"Could not load {path.name}: {exc}") from exc


def save_scenario(path, scenario):
    scenario.validate()
    atomic_json(path, {"format": FORMAT, "version": VERSION,
                       "scenario": asdict(scenario)})


def build_game(scenario, *, start=True):
    """Three local systems provide a battle arena and safe retreat anchorages.

    No galaxy generation, research progression, save loading or strategic turns
    run here. The ordinary engine creates units and resolves all battle damage.
    """
    scenario.validate(battle=start)
    systems = []
    for sid, name, x in ((0, "Proving Ground", .5), (1, "Blue Anchorage", .48), (2, "Red Anchorage", .52)):
        worlds = [Planet(i, f"Test world {i+1}", "Terran", "Medium", "Average", "Normal", 1.0+i)
                  for i in range(6 if sid == 0 else 1)]
        systems.append(StarSystem(sid, name, x, .5, "Yellow dwarf", len(worlds), "Terran", "Average", worlds))
    game = GameState("combat-simulator", "Your fleet", "Compact", scenario.seed, 1, 2300, 10000,
                     systems, race_id=scenario.player.race, fog_of_war=False,
                     opponent=Opponent("Enemy fleet", 2, 0, race_id=scenario.rival.race),
                     diplomacy=DiplomacyState(relations=-100, contact_turn=1, introduced=True),
                     victory_conditions=(), designs=list(scenario.designs))
    for index, side in enumerate(SIDES):
        fleet = scenario.fleet(side)
        game._empire(side).technology = ResearchState(completed=list(UPGRADES[fleet.upgrades][1]))
        home = systems[index+1].worlds[0]
        home.colonized, home.owner, home.population = True, side, 5
        for number in range(fleet.bases):
            world = systems[0].worlds[index*MAX_BASES+number]
            world.name = f"{'Blue' if side == 'player' else 'Red'} battery {number+1}"
            world.colonized, world.owner, world.population = True, side, 5
            world.buildings = ["fusion_plant", "missile_base"]
            defenses.commissioned(game, world, "missile_base")
        for identifier, count in sorted(fleet.ships.items()):
            design = scenario.design(identifier)
            for _ in range(count):
                if identifier == "mothership":
                    motherships.create(game, 0, side)
                else:
                    game.ships.append(Ship(game.next_ship_id, design.kind if design else identifier,
                                           0, owner=side, design=design))
                    game.next_ship_id += 1
    species.normalize(game)
    exploration.refresh(game)
    balance.tag_game(game)
    if start:
        game.start_combat(0, owner=scenario.first, target="rival" if scenario.first == "player" else "player")
        game.combat.accuracy = scenario.accuracy
    return game


def unit_preview(scenario, identifier):
    """Equipment statistics only; upgrade-dependent stock beams are labelled separately."""
    design = scenario.design(identifier)
    ship = Ship(1, design.kind if design else identifier, 0, design=design)
    # weapon_for only needs the race-independent baseline bonuses here.
    class Preview:
        def bonuses_for(self, owner):
            return {}
    return battle_ship(Preview(), ship)


def battle_report(game):
    battle = game.combat
    result = {"status": battle.status, "rounds": battle.round, "shots": battle.shots_fired, "seed": game.seed}
    for side in SIDES:
        units = [s for s in battle.fleet(side, alive=False) if s.kind not in ("combat_drone", "missile_base")]
        result[side] = {"started": len(units), "survived": sum(s.hull > 0 for s in units),
                        "hull_remaining": sum(s.hull for s in units),
                        "hull_started": sum(s.initial_hull for s in units)}
    return result


PRESETS = ("Fleet skirmish", "Carrier clash", "Capital duel", "Shield laboratory", "Planetary assault", "Convoy interception")


def preset(index=0):
    result = Scenario(name=PRESETS[index])
    if index == 1:
        result.player.ships = {"carrier": 2, "frigate": 3}
        result.rival.ships = {"cruiser": 2, "destroyer": 3}
    elif index == 2:
        result.player.ships = {"titan": 1}
        result.rival.ships = {"battleship": 2}
    elif index == 3:
        result.designs = [
            ShipDesign("design_1", "Ion testbed", "cruiser", ("ion", "laser", "shield", "scanner")),
            ShipDesign("design_2", "Shield testbed", "cruiser", ("laser", "laser", "regenerative_shield", "hardened_shield")),
        ]
        result.player.ships = {"design_1": 2}
        result.rival.ships = {"design_2": 2}
    elif index == 4:
        result.designs = [ShipDesign("design_1", "Siege testbed", "cruiser", ("siege", "laser", "armor", "scanner"))]
        result.player.ships = {"design_1": 2, "frigate": 2}
        result.rival.ships, result.rival.bases = {"frigate": 2}, 2
    elif index == 5:
        result.player.ships = {"frigate": 3, "colony_ship": 2, "troop_transport": 1}
        result.rival.ships = {"destroyer": 2, "frigate": 2}
        result.first = "rival"
    result.validate(battle=True)
    return result
