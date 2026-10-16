"""Neutral pirate fleets, deliberate scout searches and telegraphed frontier raids."""

from dataclasses import dataclass, field
import random

PIRATES = "pirates"
COLOR = (243, 132, 99)
SEARCH_TURNS = 2
WARNING_TURNS = 3
RAID_DURATION = 5
FIRST_RAID_TURN = 20
RAID_INTERVAL = 10
MAX_ENCOUNTERS = 10000
BOUNTIES = {"planet": (80, 40), "ambush": (40, 20), "raid": (60, 20)}
SITE_KINDS = ("ambush", "salvage", "archive")


@dataclass
class PirateFleet:
    id: int
    system_id: int
    kind: str
    hulls: list[int]
    created_turn: int
    arrival_turn: int
    planet_id: int | None = None
    target_owner: str | None = None
    expires_turn: int = 0
    defeated_turn: int = 0
    departed: bool = False
    raided: bool = False
    loot: int = 0
    known: dict[str, str] = field(default_factory=dict)

    def unit_id(self, index):
        return -100000-self.id*8-index

    @property
    def alive(self):
        return any(self.hulls) and not self.departed

    @property
    def name(self):
        return {"planet": "Pirate planet guards", "ambush": "Hidden pirate flotilla", "raid": "Pirate raiders"}[self.kind]


@dataclass
class SearchSite:
    system_id: int
    kind: str
    claimed_by: str | None = None
    claimed_turn: int = 0


@dataclass
class ScoutSearch:
    owner: str
    system_id: int
    ship_id: int
    started_turn: int
    progress: int = 0
    completed_turn: int = 0


@dataclass
class EncounterNews:
    id: int
    turn: int
    owner: str
    system_id: int
    message: str


@dataclass
class EncounterState:
    enabled: bool = False
    fleets: list[PirateFleet] = field(default_factory=list)
    sites: list[SearchSite] = field(default_factory=list)
    searches: list[ScoutSearch] = field(default_factory=list)
    events: list[EncounterNews] = field(default_factory=list)
    next_id: int = 1
    next_event_id: int = 1
    news_read: int = 0


def at(game, identifier):
    return next((e for e in game.encounters.fleets if e.id == identifier), None)


def active(game, fleet):
    return fleet.alive and game.turn >= fleet.arrival_turn


def status(game, fleet):
    return "departed" if fleet.departed else "defeated" if not any(fleet.hulls) else "incoming" if game.turn < fleet.arrival_turn else "active"


def known_status(game, fleet, owner="player"):
    # Hidden battle results are not visible through stale map markers.
    if game.is_observer or (game.system_visible(fleet.system_id, owner) and game.turn >= fleet.arrival_turn):
        return status(game, fleet)
    return fleet.known.get(owner)


def known_at(game, system_id, owner="player"):
    return [e for e in game.encounters.fleets if e.system_id == system_id and known_status(game, e, owner)]


def observe(game):
    if not game.encounters.enabled:
        return
    for fleet in game.encounters.fleets:
        if game.turn < fleet.arrival_turn:
            continue
        for owner in game.owners:
            if game.system_visible(fleet.system_id, owner):
                if owner not in fleet.known and active(game, fleet):
                    location = game.systems[fleet.system_id]
                    message = (f"Pirate guards detected at {location.worlds[fleet.planet_id].name}. They defend this planet; other worlds remain accessible."
                               if fleet.kind == "planet" else
                               f"Hostile pirates detected at {location.name}. Fleets entering this system must fight or retreat.")
                    report(game, owner, fleet.system_id, message)
                fleet.known[owner] = status(game, fleet)


def report(game, owner, system_id, message):
    state = game.encounters
    state.events.append(EncounterNews(state.next_event_id, game.turn, owner, system_id, message))
    state.next_event_id += 1
    state.events = state.events[-5000:]
    if owner != "player":
        game.rival_event(message, turn=game.turn, owner=owner)


def news(game):
    return [e for e in game.encounters.events if game.is_observer or e.owner == "player"]


def create(game, system_id, kind, *, planet_id=None, target_owner=None, count=1):
    from .production import SHIP_TYPES
    state = game.encounters
    if len(state.fleets) >= MAX_ENCOUNTERS:
        return None
    arrival = game.turn+WARNING_TURNS if kind == "raid" else game.turn
    fleet = PirateFleet(state.next_id, system_id, kind, [SHIP_TYPES["frigate"].hull]*count,
                        game.turn, arrival, planet_id, target_owner,
                        arrival+RAID_DURATION if kind == "raid" else 0)
    state.next_id += 1
    state.fleets.append(fleet)
    if target_owner:
        fleet.known[target_owner] = "incoming"
        report(game, target_owner, system_id,
               f"Pirate warning: {count} raider{'s' if count != 1 else ''} approaching {game.systems[system_id].name} in {WARNING_TURNS} turns. Prepare defenders or move vulnerable ships.")
    return fleet


def seed(game, enabled):
    """Placement is fixed at creation, independent of other galaxy random rolls."""
    from . import black_holes, monsters
    from .production import distance_ly
    game.encounters = EncounterState(enabled=enabled)
    if not enabled:
        return
    homes = [s for owner in game.owners for s in game.colony_systems(owner)]
    eligible = [s for s in game.systems if s.kind != black_holes.KIND and s.worlds
                and not monsters.at(game, s.id) and not any(p.colonized for p in s.worlds)
                and all(distance_ly(s, home) >= 18 for home in homes)]
    rng = random.Random(f"{game.seed}:neutral-encounters:v1")
    rng.shuffle(eligible)
    count = {"Compact": 1, "Standard": 2, "Expansive": 3}[game.galaxy_size]
    for system in eligible[:count]:
        planet = rng.choice(system.worlds)
        create(game, system.id, "planet", planet_id=planet.id, count=1)
    for system in eligible[count:]:
        roll = rng.random()
        kind = "ambush" if roll < .20 else "salvage" if roll < .45 else "archive" if roll < .60 else None
        if kind:
            game.encounters.sites.append(SearchSite(system.id, kind))


def planet_guard(game, system_id, planet_id):
    return next((e for e in game.encounters.fleets if active(game, e) and e.kind == "planet"
                 and (e.system_id, e.planet_id) == (system_id, planet_id)), None)


def blockade(game, system_id):
    return next((e for e in game.encounters.fleets if e.system_id == system_id
                 and e.kind != "planet" and active(game, e)), None)


def settlement_error(game, system_id, planet_id):
    if planet_guard(game, system_id, planet_id):
        return "Defeat the pirates guarding this planet first. Other planets in this system remain accessible."
    if blockade(game, system_id):
        return "Clear the pirate fleet from this system first."
    return None


def search_at(game, system_id, owner="player"):
    return next((s for s in game.encounters.searches if s.owner == owner and s.system_id == system_id), None)


def reserved(game, ship):
    return any(s.ship_id == ship.id and s.owner == ship.owner and not s.completed_turn
               and s.system_id == ship.system_id and not ship.has_course
               for s in game.encounters.searches)


def available_scouts(game, system_id, owner):
    return [s for s in game.fleet_at(system_id, owner) if s.kind == "scout" and not s.has_course
            and not s.disabled_turns and (not reserved(game, s) or
                any(p.ship_id == s.id and p.system_id == system_id for p in game.encounters.searches))]


def work_error(game, system_id, owner="player"):
    from . import black_holes, monsters
    from .navigation import hostile
    if game.systems[system_id].kind == black_holes.KIND:
        return "Search an ordinary star system. Black holes have their own expeditions."
    if monsters.alive_at(game, system_id):
        return "Defeat the system guardian before searching."
    if blockade(game, system_id):
        return "Clear the pirate fleet before searching."
    if any(hostile(game, owner, s.owner) and (s.damage or s.drone_bays) for s in game.foreign_fleet(system_id, owner)):
        return "Hostile armed ships prevent the search."
    return None


def search_error(game, system_id, owner="player"):
    if reason := game.strategy_error(owner):
        return reason
    if not game.encounters.enabled:
        return "Neutral encounters were disabled for this campaign."
    if type(system_id) is not int or not 0 <= system_id < len(game.systems):
        return "Choose a star system."
    current = search_at(game, system_id, owner)
    if current and current.completed_turn:
        return "Your scouts have already searched this system."
    if reason := work_error(game, system_id, owner):
        return reason
    if not available_scouts(game, system_id, owner):
        return "Station a scout here without a departure order. An armed escort is recommended."
    if current and current.ship_id in {s.id for s in available_scouts(game, system_id, owner)}:
        return "A scout is already searching this system."
    return None


def start_search(game, system_id, owner="player"):
    from .model import RuleError
    if reason := search_error(game, system_id, owner):
        raise RuleError(reason)
    scout = available_scouts(game, system_id, owner)[0]
    current = search_at(game, system_id, owner)
    if current:
        current.ship_id = scout.id
    else:
        current = ScoutSearch(owner, system_id, scout.id, game.turn)
        game.encounters.searches.append(current)
    return current


def ready_searches(game):
    ready = []
    ships = {s.id: s for s in game.ships}
    for search in game.encounters.searches:
        ship = ships.get(search.ship_id)
        if (not search.completed_turn and ship and ship.owner == search.owner and ship.kind == "scout"
                and ship.system_id == search.system_id and not ship.has_course
                and work_error(game, search.system_id, search.owner) is None):
            ready.append((search.owner, search.system_id))
    return ready


def finish_searches(game, ready):
    for owner, sid in ready:
        search = search_at(game, sid, owner)
        search.progress += 1
        if search.progress < SEARCH_TURNS:
            continue
        search.completed_turn = game.turn
        site = next((s for s in game.encounters.sites if s.system_id == sid), None)
        if site is None or site.claimed_by is not None:
            message = "Search complete: no unclaimed discoveries remain."
        else:
            site.claimed_by, site.claimed_turn = owner, game.turn
            empire = game._empire(owner)
            if site.kind == "ambush":
                fleet = create(game, sid, "ambush")
                if fleet:
                    fleet.known[owner] = "active"
                message = ("Search uncovered a hidden pirate flotilla! Your fleet can fight or retreat." if fleet else
                           "Search complete: the pirates have abandoned this hideout.")
            elif site.kind == "salvage":
                credits, resources = min(60, 1_000_000_000-empire.credits), min(40, 1_000_000_000-empire.resources)
                empire.credits += credits
                empire.resources += resources
                message = f"Recovered a derelict supply cache: +{credits} CR and +{resources} RES."
            else:
                points = min(80, 1_000_000_000-empire.research)
                empire.research += points
                message = f"Recovered navigation archives: +{points} RP."
        report(game, owner, sid, f"{game.systems[sid].name}: {message}")


def schedule_raid(game):
    from . import black_holes, monsters
    if (game.turn < FIRST_RAID_TURN or game.turn % RAID_INTERVAL
            or any(e.kind == "raid" and e.alive for e in game.encounters.fleets)):
        return
    rng = random.Random(f"{game.seed}:pirate-raid:{game.turn}")
    if rng.random() >= .35:
        return
    homes = {game.headquarters(o)[0].id for o in game.owners if game.settlements(o)}
    occupied = {e.system_id for e in game.encounters.fleets if e.alive}
    choices = sorted({(s.id, owner) for owner in game.owners for s in game.colony_systems(owner)
                      if s.kind != black_holes.KIND and s.id not in occupied and game.settlements_at(s.id, owner)
                      and (game.turn >= 60 or s.id not in homes) and not monsters.alive_at(game, s.id)})
    if choices:
        sid, owner = rng.choice(choices)
        create(game, sid, "raid", target_owner=owner, count=1 if game.turn < 80 else 2)


def finish_turn(game, ready):
    if not game.encounters.enabled:
        return
    from . import combat, defenses
    finish_searches(game, ready)
    for fleet in game.encounters.fleets:
        if fleet.kind != "raid" or not fleet.alive:
            continue
        owner, sid = fleet.target_owner, fleet.system_id
        if game.turn >= fleet.expires_turn:
            fleet.departed = True
            fleet.known[owner] = "departed"
            report(game, owner, sid, f"The pirate raiders have withdrawn from {game.systems[sid].name}.")
        elif game.turn == fleet.arrival_turn:
            fleet.known[owner] = "active"
            report(game, owner, sid, f"Pirate raiders arrived at {game.systems[sid].name}. They attack fleets and may steal credits from an undefended settlement.")
        if (active(game, fleet) and not fleet.raided and game.settlements_at(sid, owner)
                and not combat.combat_fleet(game, sid, owner) and not defenses.bases(game, sid, owner)):
            empire = game._empire(owner)
            stolen = min(60, max(0, empire.credits)//10)
            empire.credits -= stolen
            fleet.loot += stolen
            fleet.raided = True
            report(game, owner, sid, f"Pirates raided {game.systems[sid].name}: {stolen} CR stolen. Defeat them before they leave to recover the loot and claim a bounty.")
    schedule_raid(game)
    observe(game)


def engagement_error(game, identifier, owner="player", *, intercept=False):
    from . import combat, defenses
    if reason := game.strategy_error(owner):
        return reason
    fleet = at(game, identifier)
    if fleet is None or not active(game, fleet):
        return "No active pirate fleet is available."
    own = combat.combat_fleet(game, fleet.system_id, owner)
    bases = defenses.bases(game, fleet.system_id, owner) if fleet.kind != "planet" else []
    if not own and not bases:
        return "Bring a fleet to this system first."
    if not intercept and not bases and not any(s.damage or s.drone_bays for s in own):
        return "Bring armed ships to challenge the pirates."
    return None


def commit_battle(game, battle):
    fleet = at(game, battle.encounter_id)
    was_alive = any(fleet.hulls)
    for i in range(len(fleet.hulls)):
        unit = battle.ship(fleet.unit_id(i))
        if unit:
            fleet.hulls[i] = unit.hull
    owner = battle.initiator
    if was_alive and not any(fleet.hulls):
        fleet.defeated_turn = game.turn
        credits, resources = BOUNTIES[fleet.kind]
        empire = game._empire(owner)
        credits = min(credits+fleet.loot, 1_000_000_000-empire.credits)
        resources = min(resources, 1_000_000_000-empire.resources)
        empire.credits += credits
        empire.resources += resources
        message = f"{fleet.name} defeated: +{credits} CR and +{resources} RES in bounty and recovered stores."
        report(game, owner, fleet.system_id, message)
        battle.record(message)
    fleet.known[owner] = status(game, fleet)
    observe(game)


def intercept(game):
    from . import combat
    if not game.encounters.enabled or game.combat or game.result:
        return False
    for owner in ("player", *game.opponents):
        if owner not in game.owners:
            continue
        for fleet in game.encounters.fleets:
            if fleet.kind == "planet" or not active(game, fleet):
                continue
            if engagement_error(game, fleet.id, owner, intercept=True) is not None:
                continue
            combat.begin_pirate_combat(game, fleet.id, owner, intercept=True)
            if owner == "player":
                return True
            combat.autoresolve(game)
            if game.combat:
                game.finish_combat()
    return False


def ai_orders(game, owner):
    from . import combat
    if not game.encounters.enabled:
        return
    for sid in sorted({s.system_id for s in game.ships_owned_by(owner) if s.kind == "scout" and not s.has_course}):
        if search_error(game, sid, owner) is None:
            start_search(game, sid, owner)
    for fleet in game.encounters.fleets:
        if fleet.kind != "planet" or known_status(game, fleet, owner) != "active":
            continue
        own = combat.combat_fleet(game, fleet.system_id, owner)
        if sum(s.hull for s in own if s.damage or s.drone_bays) < 1.5*sum(fleet.hulls):
            continue
        if engagement_error(game, fleet.id, owner) is None:
            combat.begin_pirate_combat(game, fleet.id, owner)
            combat.autoresolve(game)
            if game.combat:
                game.finish_combat()


def load(game, data, version):
    """Old campaigns retain their previous neutral-threat rules."""
    from .model import _integer, _name
    from .production import SHIP_TYPES
    from .black_holes import KIND
    if version < 49:
        return
    raw = data["encounters"]
    if not isinstance(raw, dict) or set(raw) != set(EncounterState.__dataclass_fields__):
        raise ValueError("Invalid encounters")
    if type(raw["enabled"]) is not bool:
        raise ValueError("Invalid encounter setting")
    state = EncounterState(enabled=raw["enabled"])
    def rows(key, cls, limit):
        values = raw[key]
        if not isinstance(values, list) or len(values) > limit:
            raise ValueError("Invalid encounter records")
        for row in values:
            if not isinstance(row, dict) or set(row) != set(cls.__dataclass_fields__):
                raise ValueError("Invalid encounter fields")
            yield cls(**row)
    def system(sid):
        return _integer(sid, 0, len(game.systems)-1) and game.systems[sid].kind != KIND
    def owner(value):
        return isinstance(value, str) and value in game.owners
    for e in rows("fleets", PirateFleet, MAX_ENCOUNTERS):
        if (not _integer(e.id, 1, MAX_ENCOUNTERS) or e.id != len(state.fleets)+1 or not system(e.system_id)
                or not isinstance(e.kind, str) or e.kind not in BOUNTIES
                or not isinstance(e.hulls, list) or not 1 <= len(e.hulls) <= 2
                or any(not _integer(h, 0, SHIP_TYPES["frigate"].hull) for h in e.hulls)
                or not _integer(e.created_turn, 1, game.turn)
                or e.arrival_turn != e.created_turn+(WARNING_TURNS if e.kind == "raid" else 0)
                or not _integer(e.arrival_turn, 1, game.turn+WARNING_TURNS)
                or type(e.departed) is not bool or type(e.raided) is not bool
                or not _integer(e.loot, 0, 60) or (e.loot and not e.raided)
                or not _integer(e.defeated_turn, 0, game.turn)
                or bool(e.defeated_turn) == bool(any(e.hulls))
                or (e.defeated_turn and e.defeated_turn < e.arrival_turn)):
            raise ValueError("Invalid pirate fleet")
        if (e.kind == "planet" and (not _integer(e.planet_id, 0, len(game.systems[e.system_id].worlds)-1))) or (e.kind != "planet" and e.planet_id is not None):
            raise ValueError("Invalid guarded planet")
        if e.kind == "raid":
            if (not owner(e.target_owner) or not _integer(e.expires_turn, 1, game.turn+WARNING_TURNS+RAID_DURATION)
                    or e.expires_turn != e.arrival_turn+RAID_DURATION
                    or (e.departed and game.turn < e.expires_turn)
                    or (e.raided and game.turn < e.arrival_turn)):
                raise ValueError("Invalid pirate raid")
        elif e.target_owner is not None or e.expires_turn or e.departed or e.raided or e.loot:
            raise ValueError("Unexpected raid state")
        if (not isinstance(e.known, dict) or any(not owner(o) or s not in ("incoming", "active", "defeated", "departed")
                or (s == "incoming" and e.kind != "raid") or (s == "active" and game.turn < e.arrival_turn)
                or (s == "defeated" and not e.defeated_turn) or (s == "departed" and not e.departed)
                for o, s in e.known.items())):
            raise ValueError("Invalid pirate knowledge")
        state.fleets.append(e)
    for site in rows("sites", SearchSite, len(game.systems)):
        if (not system(site.system_id) or site.system_id in {s.system_id for s in state.sites}
                or not isinstance(site.kind, str) or site.kind not in SITE_KINDS
                or not _integer(site.claimed_turn, 0, game.turn)
                or (not owner(site.claimed_by) if site.claimed_turn else site.claimed_by is not None)):
            raise ValueError("Invalid hidden search site")
        state.sites.append(site)
    for s in rows("searches", ScoutSearch, len(game.systems)*len(game.owners)):
        if (not owner(s.owner) or not system(s.system_id)
                or (s.owner, s.system_id) in {(p.owner, p.system_id) for p in state.searches}
                or not _integer(s.ship_id, 1, game.next_ship_id-1)
                or not _integer(s.started_turn, 1, game.turn) or not _integer(s.progress, 0, SEARCH_TURNS)
                or s.progress > game.turn-s.started_turn
                or not _integer(s.completed_turn, s.started_turn+SEARCH_TURNS if s.progress == SEARCH_TURNS else 0,
                                game.turn if s.progress == SEARCH_TURNS else 0)):
            raise ValueError("Invalid scout search")
        state.searches.append(s)
    if any(site.claimed_by is not None and not any(
            s.owner == site.claimed_by and s.system_id == site.system_id and s.completed_turn == site.claimed_turn
            for s in state.searches) for site in state.sites):
        raise ValueError("Search site claimed without a completed search")
    for e in rows("events", EncounterNews, 5000):
        if (not _integer(e.id, 1, 100_000_000) or (state.events and e.id <= state.events[-1].id)
                or not _integer(e.turn, 1, game.turn) or not owner(e.owner)
                or not system(e.system_id) or not _name(e.message, 300)):
            raise ValueError("Invalid encounter news")
        state.events.append(e)
    if (not _integer(raw["next_id"], 1, MAX_ENCOUNTERS+1) or raw["next_id"] != len(state.fleets)+1
            or not _integer(raw["next_event_id"], 1, 100_000_001)
            or raw["next_event_id"] != (state.events[-1].id+1 if state.events else 1)
            or not _integer(raw["news_read"], 0, raw["next_event_id"]-1)):
        raise ValueError("Invalid encounter sequence")
    state.next_id, state.next_event_id, state.news_read = raw["next_id"], raw["next_event_id"], raw["news_read"]
    if not state.enabled and (state.fleets or state.sites or state.searches or state.events):
        raise ValueError("Disabled encounters contain activity")
    game.encounters = state
