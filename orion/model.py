"""Game data and galaxy generation, independent of pygame and the UI."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
import random
from uuid import uuid4

GALAXY_SIZES = {"Compact": 24, "Standard": 48, "Expansive": 72}
STAR_TYPES = ("Yellow dwarf", "Blue star", "Red dwarf", "White star", "Orange dwarf")
BIOMES = ("Terran", "Ocean", "Desert", "Tundra", "Barren", "Volcanic")
RICHNESSES = ("Poor", "Average", "Rich")
PLANET_SIZES = ("Tiny", "Small", "Medium", "Large", "Huge")
GRAVITIES = ("Low", "Normal", "High")
HABITABILITY = {"Terran": 100, "Ocean": 80, "Desert": 40,
                "Tundra": 35, "Barren": 0, "Volcanic": 0}
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
class Planet:
    id: int
    name: str
    biome: str
    size: str
    richness: str
    gravity: str
    orbit_au: float
    population: int = 0  # Billions; a static preview until colony simulation exists.
    colonized: bool = False

    @property
    def habitability(self):
        return HABITABILITY[self.biome]

    @classmethod
    def from_dict(cls, data, expected_id):
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
        return cls(**data)


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
            Planet(2, "Earth", "Terran", "Medium", "Average", "Normal", 1.0, 8, True),
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

    def advance_turn(self):
        """Prototype rule only: one year and eight credits per turn."""
        self.turn += 1
        self.year += 1
        self.credits += 8

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data, *, legacy=False):
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
                record = dict(s)
                world_data = record.pop("worlds", None)
                system = StarSystem(**record)
                if legacy:
                    system.worlds = generate_planets(system, data["seed"])
                else:
                    if not isinstance(world_data, list) or len(world_data) != system.planets:
                        raise ValueError
                    system.worlds = [Planet.from_dict(p, j) for j, p in enumerate(world_data)]
                    if any(a.orbit_au >= b.orbit_au for a, b in zip(system.worlds, system.worlds[1:])):
                        raise ValueError
                systems.append(system)
            selected = data.get("selected_system", 0)
            if not _integer(selected, 0, len(systems) - 1):
                raise ValueError
            planet = None if legacy else data.get("selected_planet")
            if planet is not None and not _integer(planet, 0, systems[selected].planets - 1):
                raise ValueError
            return cls(campaign, data["empire_name"], size, data["seed"],
                       data["turn"], data["year"], data["credits"], systems, selected, planet)
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
    for system in systems:
        system.worlds = generate_planets(system, seed)
    return GameState(uuid4().hex, empire_name.strip(), galaxy_size, seed, 1, 2300, 120, systems)
