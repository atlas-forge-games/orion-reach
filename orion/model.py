"""Game data and galaxy generation, independent of pygame and the UI."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import random
from uuid import uuid4

GALAXY_SIZES = {"Compact": 24, "Standard": 48, "Expansive": 72}
STAR_TYPES = ("Yellow dwarf", "Blue star", "Red dwarf", "White star", "Orange dwarf")
BIOMES = ("Terran", "Ocean", "Desert", "Tundra", "Barren", "Volcanic")
RICHNESSES = ("Poor", "Average", "Rich")
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


def _integer(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


def _name(value, maximum=28):
    return (isinstance(value, str) and 0 < len(value) <= maximum and bool(value.strip())
            and all(c.isprintable() for c in value))


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

    def advance_turn(self):
        """Prototype rule only: one year and eight credits per turn."""
        self.turn += 1
        self.year += 1
        self.credits += 8

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
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
                systems.append(StarSystem(**s))
            selected = data.get("selected_system", 0)
            if not _integer(selected, 0, len(systems) - 1):
                raise ValueError
            return cls(campaign, data["empire_name"], size, data["seed"],
                       data["turn"], data["year"], data["credits"], systems, selected)
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise SaveError("This save contains invalid game data.") from exc


def new_game(empire_name="Terran Union", galaxy_size="Standard", seed=None):
    if not _name(empire_name) or galaxy_size not in GALAXY_SIZES:
        raise SaveError("Enter an empire name and choose a galaxy size.")
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
    return GameState(uuid4().hex, empire_name.strip(), galaxy_size, seed, 1, 2300, 120, systems)
