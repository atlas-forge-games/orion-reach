"""Per-empire surveys, local visibility and once-only scout discoveries."""

from dataclasses import asdict, dataclass, field, replace
import random
from . import black_holes
from .frame_cache import cached_in_frame

@dataclass(frozen=True)
class DiscoverySpec:
    name: str
    description: str
    credits: int = 0
    research: int = 0

    @property
    def reward(self):
        return " · ".join(f"+{amount} {unit}" for amount, unit in
                          ((self.credits, "CR"), (self.research, "RP")) if amount)


DISCOVERIES = {
    "supply_cache": DiscoverySpec("Abandoned supply cache", "Salvaged supplies can support your next expedition.", credits=40),
    "ancient_archive": DiscoverySpec("Ancient archive", "Recovered records contribute to your current research.", research=30),
    "derelict_probe": DiscoverySpec("Derelict probe", "A silent probe yields useful components and scientific data.", credits=20, research=15),
}


@dataclass
class Survey:
    owner: str
    system_id: int
    first_visit: int
    last_seen: int
    worlds: list[dict]
    megastructure: dict | None = None


@dataclass(frozen=True)
class Discovery:
    system_id: int
    owner: str
    kind: str
    turn: int


@dataclass
class ExplorationState:
    surveys: list[Survey] = field(default_factory=list)
    scanned_player: list[int] = field(default_factory=list)
    scanned_rival: list[int] = field(default_factory=list)
    discoveries: list[Discovery] = field(default_factory=list)
    scanned_others: dict[str, list[int]] = field(default_factory=dict)

    def survey(self, system_id, owner="player"):
        return next((s for s in self.surveys if s.system_id == system_id and s.owner == owner), None)

    def scanned(self, owner="player"):
        if owner == "player":
            return self.scanned_player
        if owner == "rival":
            return self.scanned_rival
        return self.scanned_others.setdefault(owner, [])

    @classmethod
    def from_dict(cls, data, game, *, version=42):
        from .model import Planet, _integer
        if version < 20 and isinstance(data, dict):
            data = {k: v for k, v in data.items() if k != "scanned_others"}
        fields = {"surveys", "scanned_player", "scanned_rival", "discoveries"}
        if version >= 20:
            fields.add("scanned_others")
        if not isinstance(data, dict) or set(data) != fields:
            raise ValueError("Invalid exploration data")
        count = len(game.systems)
        if not isinstance(data["surveys"], list) or len(data["surveys"]) > count*len(game.owners):
            raise ValueError
        surveys, keys = [], set()
        for row in data["surveys"]:
            expected = {"owner", "system_id", "first_visit", "last_seen", "worlds"}
            if version >= 42:
                expected.add("megastructure")
            if version < 42 and isinstance(row, dict):
                row = {k: v for k, v in row.items() if k != "megastructure"}
            if not isinstance(row, dict) or set(row) != expected:
                raise ValueError
            owner, sid = row["owner"], row["system_id"]
            if owner not in game.owners or not _integer(sid, 0, count-1):
                raise ValueError
            if (owner, sid) in keys or not _integer(row["first_visit"], 1, game.turn) or not _integer(row["last_seen"], row["first_visit"], game.turn):
                raise ValueError
            worlds = row["worlds"]
            if not isinstance(worlds, list) or len(worlds) != game.systems[sid].planets:
                raise ValueError
            normalized_worlds = []
            for index, world in enumerate(worlds):
                parsed = Planet.from_dict(world, index, version=version)
                if parsed.bombarded_turn > row["last_seen"]:
                    raise ValueError("Survey contains future bombardment")
                actual = game.systems[sid].worlds[index]
                if any(getattr(parsed, key) != getattr(actual, key) for key in
                       ("name", "biome", "size", "richness", "gravity", "orbit_au")):
                    raise ValueError("Survey does not match this world")
                if parsed.owner is not None and parsed.owner not in game.owners:
                    raise ValueError
                if parsed.outpost_owner is not None and parsed.outpost_owner not in game.owners:
                    raise ValueError("Unknown outpost owner in survey")
                normalized_worlds.append(asdict(parsed))
            if sum(p["outpost_owner"] is not None for p in normalized_worlds) > 1:
                raise ValueError("Multiple outposts in a system survey")
            if row.get("megastructure") is not None:
                from .megastructures import Megastructure
                Megastructure.from_dict(row["megastructure"], game.owners, row["last_seen"])
            surveys.append(Survey(**{**row, "worlds": normalized_worlds}))
            keys.add((owner, sid))
        extras = data["scanned_others"] if version >= 20 else {}
        if not isinstance(extras, dict) or set(extras) != set(game.other_opponents):
            raise ValueError("Invalid scout observers")
        scanned = {"player": data["scanned_player"], "rival": data["scanned_rival"], **extras}
        for owner, ids in scanned.items():
            if (not isinstance(ids, list) or len(ids) > count or any(not _integer(i, 0, count-1) for i in ids)
                    or len(set(ids)) != len(ids) or (owner not in game.owners and ids)):
                raise ValueError
            if game.fog_of_war and any((owner, sid) not in keys for sid in ids):
                raise ValueError("Scout scan has no survey")
        if not isinstance(data["discoveries"], list) or len(data["discoveries"]) > count:
            raise ValueError
        discoveries, claimed = [], set()
        for row in data["discoveries"]:
            if not isinstance(row, dict) or set(row) != {"system_id", "owner", "kind", "turn"}:
                raise ValueError
            sid, owner = row["system_id"], row["owner"]
            if (not _integer(sid, 0, count-1) or owner not in game.owners or sid in claimed
                    or not isinstance(row["kind"], str) or row["kind"] not in DISCOVERIES
                    or not _integer(row["turn"], 1, game.turn)
                    or sid not in scanned[owner] or row["kind"] != discovery_at(game, sid)):
                raise ValueError("Invalid discovery claim")
            discoveries.append(Discovery(**row))
            claimed.add(sid)
        return cls(surveys, scanned["player"].copy(), scanned["rival"].copy(), discoveries,
                   {owner: ids.copy() for owner, ids in extras.items()})


def observed_systems(game, owner="player"):
    """Live intelligence comes from colonies, outposts or ships in orbit."""
    return {s.id for s in game.supply_systems(owner)} | {
        s.system_id for s in game.ships if s.owner == owner and not s.in_transit}


@cached_in_frame
def is_visible(game, system_id, owner="player"):
    system = game.systems[system_id]
    if game.is_observer and owner == "player":
        return True
    if system.kind == black_holes.KIND:
        if not black_holes.can_detect(game, owner):
            return False
    elif not game.fog_of_war:
        return True
    # Query this location directly instead of scanning every world's supply on
    # every lookup. Anchored motherships count as ships; travelling homes do not.
    return (any(p.owner == owner or p.outpost_owner == owner for p in system.worlds)
            or any(s.owner == owner and s.system_id == system_id and not s.in_transit for s in game.ships))


def is_explored(game, system_id, owner="player"):
    return is_visible(game, system_id, owner) or game.exploration.survey(system_id, owner) is not None


def ship_visible(game, ship, owner="player"):
    if not black_holes.fleet_charted(game, ship, owner):
        return False
    # No interstellar sensors in this first version: enemy voyages remain hidden.
    return (game.is_observer and owner == "player") or ship.owner == owner or not game.fog_of_war or (
        not ship.in_transit and is_visible(game, ship.system_id, owner))


@cached_in_frame
def known_system(game, system_id, owner="player"):
    """A live system, a last-observed snapshot, or no planetary information."""
    from .model import Planet
    system = game.systems[system_id]
    if is_visible(game, system_id, owner):
        return system
    survey = game.exploration.survey(system_id, owner)
    if survey is None:
        return None
    from .megastructures import Megastructure
    mega = Megastructure.from_dict(survey.megastructure, game.owners, survey.last_seen) if survey.megastructure else None
    return replace(system, worlds=[Planet.from_dict(world, index)
                                   for index, world in enumerate(survey.worlds)], megastructure=mega)


def record_survey(game, system_id, owner):
    if not game.fog_of_war and game.systems[system_id].kind != black_holes.KIND:
        return False
    survey = game.exploration.survey(system_id, owner)
    worlds = [asdict(p) for p in game.systems[system_id].worlds]
    m = game.systems[system_id].megastructure
    mega = asdict(m) if m else None
    if survey is None:
        game.exploration.surveys.append(Survey(owner, system_id, game.turn, game.turn, worlds, mega))
        return True
    survey.last_seen, survey.worlds = game.turn, worlds
    survey.megastructure = mega
    return False


def discovery_at(game, system_id):
    # The contents depend only on the galaxy seed, even if a rival is added later.
    if system_id == 0 or game.systems[system_id].kind == black_holes.KIND:
        return None
    rng = random.Random(f"orion-discovery-v1:{game.seed}:{system_id}")
    return rng.choice(tuple(DISCOVERIES)) if rng.random() < .35 else None


def refresh(game, *, recover=False):
    """Snapshot observed worlds; scouts can claim an encounter only once globally."""
    from .monsters import alive_at, observe
    from . import sensors, first_contact, encounters
    sensors.refresh(game)
    messages = []
    for owner in game.owners:
        for sid in observed_systems(game, owner):
            observe(game, sid, owner)
        for sid in sorted(observed_systems(game, owner)):
            if game.fog_of_war or game.systems[sid].kind == black_holes.KIND:
                if record_survey(game, sid, owner) and owner == "player":
                    system = game.systems[sid]
                    messages.append(f"Surveyed {system.name}: {system.planets} planets")
    first_contact.refresh(game)
    encounters.observe(game)
    if not recover:
        return messages
    claimed = {d.system_id for d in game.exploration.discoveries}
    # Existing ship IDs provide stable resolution for simultaneous arrivals.
    for ship in sorted(game.ships, key=lambda s: s.id):
        if ship.kind != "scout" or ship.in_transit:
            continue
        if alive_at(game, ship.system_id):
            continue
        scanned = game.exploration.scanned(ship.owner)
        if ship.system_id in scanned:
            continue
        scanned.append(ship.system_id)
        if ship.system_id in {0, *(r.home_system for r in game.opponents.values())}:
            continue  # Starting homeworlds have already been searched.
        kind = discovery_at(game, ship.system_id)
        if kind is None or ship.system_id in claimed:
            continue
        claimed.add(ship.system_id)
        definition = DISCOVERIES[kind]
        empire = game._empire(ship.owner)
        empire.credits += definition.credits
        empire.research += definition.research
        game.exploration.discoveries.append(Discovery(ship.system_id, ship.owner, kind, game.turn))
        message = f"{game.systems[ship.system_id].name}: {definition.name} ({definition.reward})"
        if ship.owner == "player":
            messages.append(message)
        else:
            game.rival_event(f"Recovered {message}", turn=game.turn, owner=ship.owner)
    return messages


def known_rival_colonies(game, owner=None):
    return ([(known, planet) for system in game.systems
             if (known := known_system(game, system.id)) is not None
             for planet in known.worlds if planet.owner in game.opponents and (owner is None or planet.owner == owner)]
            + [(game.systems[ship.system_id], ship.habitat) for ship in game.visible_ships()
               if ship.habitat is not None and ship.owner in game.opponents and (owner is None or ship.owner == owner)])


def gate_location(game, system_id, planet):
    return planet.name if is_visible(game, system_id) else "an unobserved system"
