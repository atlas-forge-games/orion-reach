"""Research-gated singularities, deliberate expeditions and one-time relic claims."""

from dataclasses import dataclass, field
import random

from .encyclopedia_artifacts import ARTIFACT_CONCEPTS
from .production import distance_ly
from .frame_cache import cached_in_frame

KIND = "Black hole"
SITES = {
    "maw": ("The Maw", "ashen_leviathan", (255, 194, 113),
            "An amber accretion disk burns around a starless abyss."),
    "silent_eye": ("The Silent Eye", "horizon_warden", (201, 178, 255),
                   "A pale ring bends distant starlight around absolute darkness."),
    "broken_crown": ("The Broken Crown", "crown_sentinel", (236, 207, 151),
                     "Ancient wreckage circles a fractured crown of light."),
}
RELICS = {relic.id: relic for relic in ARTIFACT_CONCEPTS}


@dataclass
class BlackHole:
    system_id: int
    kind: str
    relic_id: str
    claimed_by: str | None = None
    recovered_turn: int = 0


@dataclass
class BlackHoleEvent:
    id: int
    owner: str
    system_id: int
    turn: int
    kind: str
    ships: int = 0


@dataclass
class BlackHoleState:
    sites: list[BlackHole] = field(default_factory=list)
    events: list[BlackHoleEvent] = field(default_factory=list)
    news_read: int = 0


def at(game, system_id):
    return next((site for site in game.black_holes.sites if site.system_id == system_id), None)


@cached_in_frame
def can_detect(game, owner="player"):
    return ((game.is_observer and owner == "player") or
            (owner in game.owners and bool(game.bonuses_for(owner).get("black_hole_detection"))))


def can_explore(game, owner="player"):
    return owner in game.owners and bool(game.bonuses_for(owner).get("black_hole_navigation"))


def charted(game, system, owner="player"):
    return system.kind != KIND or can_detect(game, owner)


def chart_systems(game, owner="player"):
    return [system for system in game.systems if charted(game, system, owner)]


def fleet_charted(game, ship, owner="player"):
    """A visible fleet route must not disclose an undiscovered singularity."""
    return (ship.owner == owner or
            all(game.systems[sid].kind != KIND for sid in (ship.system_id, ship.destination) if sid is not None)
            or can_detect(game, owner))


def risk(game, destination, owner="player"):
    if at(game, destination) and can_detect(game, owner) and not can_explore(game, owner):
        return ("Without Event Horizon Navigation, every ship in this expedition will be lost "
                "on arrival. Research safe navigation before departing.")
    return None


def order_error(game, destination, owner, accept_risk=False):
    if at(game, destination):
        if not can_detect(game, owner):
            return "Research Gravitic Mapping to locate black holes first."
        if not accept_risk:
            return risk(game, destination, owner)
    return None


def record(game, owner, site, kind, ships=0):
    event = BlackHoleEvent(len(game.black_holes.events)+1, owner, site.system_id,
                           game.turn, kind, ships)
    game.black_holes.events.append(event)
    return event


def report_mapping(game, owner):
    if not can_detect(game, owner):
        return
    reported = {event.system_id for event in game.black_holes.events
                if event.owner == owner and event.kind == "mapped"}
    for site in game.black_holes.sites:
        if site.system_id not in reported:
            record(game, owner, site, "mapped")


def resolve_arrivals(game, alerts):
    """Only fleets actually arriving at a singularity are at risk; routes are safe."""
    lost = set()
    for site in game.black_holes.sites:
        for owner in game.owners:
            fleet = game.fleet_at(site.system_id, owner)
            if fleet and not can_explore(game, owner):
                lost.update(ship.id for ship in fleet)
                record(game, owner, site, "lost", len(fleet))
                message = f"{len(fleet)} ships lost at {game.systems[site.system_id].name}: unsafe black-hole approach."
                if owner == "player":
                    alerts.append(message)
                else:
                    game.rival_event(message, turn=game.turn, owner=owner)
    game.ships[:] = [ship for ship in game.ships if ship.id not in lost]


def claim(game, site, owner):
    """Only the guardian's living-to-defeated transition calls this operation."""
    if site.claimed_by is not None:
        return None
    site.claimed_by, site.recovered_turn = owner, game.turn
    record(game, owner, site, "recovered")
    return f"Recovered {RELICS[site.relic_id].name}. Added to the empire's relic collection."


def collection(game, owner="player"):
    return [site for site in game.black_holes.sites if site.claimed_by == owner]


def events(game):
    return [event for event in game.black_holes.events if game.is_observer or event.owner == "player"]


def headline(game, event):
    name = game.systems[event.system_id].name
    return {"mapped": f"Black hole located: {name}", "lost": f"Expedition lost at {name}",
            "recovered": f"Legendary relic recovered at {name}"}[event.kind]


def detail(game, event):
    if event.kind == "mapped":
        return "Gravitic Mapping reveals this singularity. Event Horizon Navigation is required for a safe expedition."
    if event.kind == "lost":
        return f"{event.ships} ships were destroyed during an unsafe approach. Ordinary routes past black holes remain safe."
    site = at(game, event.system_id)
    return (f"{game.empire_name_for(event.owner)} recovered {RELICS[site.relic_id].name}. "
            "View the collection in Info → Legendary artifacts. Placement and bonuses remain planned.")


def seed_sites(game):
    """Use independent randomness and keep homes, normal guardians and IDs intact."""
    from . import monsters
    homes = [system for system in game.systems if any(p.colonized for p in system.worlds)]
    candidates = [s for s in game.systems if s.id != 0 and s not in homes and monsters.at(game, s.id) is None]
    rng = random.Random(f"orion-black-holes-v1:{game.seed}")
    rng.shuffle(candidates)
    # Empty systems are preferred; populated or guarded systems are never converted.
    candidates.sort(key=lambda s: (bool(s.worlds), -min((distance_ly(s, h) for h in homes), default=0)))
    relics = list(RELICS)
    rng.shuffle(relics)
    kinds = list(SITES)
    rng.shuffle(kinds)
    for kind, relic_id in zip(kinds[:2 if game.galaxy_size == "Compact" else 3], relics):
        distant = [s for s in candidates if all(distance_ly(s, h) >= 18 for h in homes)
                   and all(distance_ly(s, game.systems[b.system_id]) >= 18 for b in game.black_holes.sites)]
        system = (distant or candidates)[0]
        candidates.remove(system)
        system.name, guardian_kind, _, _ = SITES[kind]
        system.kind, system.planets, system.worlds = KIND, 0, []
        system.biome, system.richness = "Barren", "Poor"
        game.black_holes.sites.append(BlackHole(system.id, kind, relic_id))
        game.guardians.append(monsters.Guardian(system.id, -1, guardian_kind, monsters.MONSTERS[guardian_kind].hull))


def load(game, data, version):
    from .model import _integer
    if version < 34:
        return  # Existing campaigns keep their original systems and planets.
    state = data["black_holes"]
    if not isinstance(state, dict) or set(state) != {"sites", "events", "news_read"}:
        raise ValueError("Invalid black-hole state")
    rows = state["sites"]
    if not isinstance(rows, list) or len(rows) > 3:
        raise ValueError("Invalid black-hole sites")
    sites, identifiers, kinds, relics = [], set(), set(), set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"system_id", "kind", "relic_id", "claimed_by", "recovered_turn"}:
            raise ValueError("Invalid black-hole site")
        sid, kind, relic, owner, turn = (row[k] for k in ("system_id", "kind", "relic_id", "claimed_by", "recovered_turn"))
        if (not _integer(sid, 1, len(game.systems)-1) or sid in identifiers or
                not isinstance(kind, str) or kind not in SITES or kind in kinds or
                not isinstance(relic, str) or relic not in RELICS or relic in relics or
                (owner is not None and (not isinstance(owner, str) or owner not in game.owners)) or
                not _integer(turn, 0 if owner is None else 1, 0 if owner is None else game.turn)):
            raise ValueError("Invalid black-hole identity or claim")
        system = game.systems[sid]
        if system.kind != KIND or system.worlds or system.planets or system.name != SITES[kind][0]:
            raise ValueError("Black-hole site does not match its map location")
        sites.append(BlackHole(**row))
        identifiers.add(sid); kinds.add(kind); relics.add(relic)
    if identifiers != {s.id for s in game.systems if s.kind == KIND}:
        raise ValueError("Black-hole map sites are missing")
    game.black_holes.sites = sites
    rows = state["events"]
    if not isinstance(rows, list) or len(rows) > 100_000:
        raise ValueError("Invalid black-hole events")
    parsed, mapped, recovered, last_turn = [], set(), set(), 0
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict) or set(row) != {"id", "owner", "system_id", "turn", "kind", "ships"}:
            raise ValueError("Invalid black-hole event")
        if (not _integer(row["id"], index, index) or not isinstance(row["owner"], str) or row["owner"] not in game.owners or
                not _integer(row["system_id"], 1, len(game.systems)-1) or row["system_id"] not in identifiers or
                not _integer(row["turn"], max(1, last_turn), game.turn) or row["kind"] not in ("mapped", "lost", "recovered") or
                not _integer(row["ships"], 1 if row["kind"] == "lost" else 0, 10_000 if row["kind"] == "lost" else 0)):
            raise ValueError("Invalid black-hole event data")
        site = at(game, row["system_id"])
        if row["kind"] == "recovered":
            if site.system_id in recovered or (site.claimed_by, site.recovered_turn) != (row["owner"], row["turn"]):
                raise ValueError("Invalid relic recovery")
            recovered.add(site.system_id)
        if row["kind"] == "mapped":
            key = (row["owner"], row["system_id"])
            if key in mapped:
                raise ValueError("Duplicate mapping report")
            mapped.add(key)
        parsed.append(BlackHoleEvent(**row)); last_turn = row["turn"]
    if recovered != {site.system_id for site in sites if site.claimed_by is not None}:
        raise ValueError("Relic recovery report is missing")
    if not _integer(state["news_read"], 0, len(parsed)):
        raise ValueError("Invalid black-hole news marker")
    game.black_holes.events, game.black_holes.news_read = parsed, state["news_read"]


def validate_guardians(game):
    from .monsters import at as guardian_at
    for site in game.black_holes.sites:
        guardian = guardian_at(game, site.system_id)
        if (guardian is None or guardian.kind != SITES[site.kind][1] or guardian.planet_id != -1 or
                guardian.alive != (site.claimed_by is None)):
            raise ValueError("Black-hole guardian and relic claim disagree")
