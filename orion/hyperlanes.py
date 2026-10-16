"""Private Wanderer navigation research and permanent, bidirectional shortcuts."""

from dataclasses import dataclass
import random

from . import black_holes, motherships, monsters
from .navigation import hostile

RESEARCH_COST = 300
TRAVEL_TURNS = 1


@dataclass(frozen=True)
class HiddenHyperlane:
    first: int
    second: int

    @property
    def pair(self):
        return self.first, self.second


def generate_network(game):
    """Sample geometric endpoint degrees, then join them into a simple graph.

    P(desired degree >= n) = 0.5**n. Pairing may trim an impossible degree
    sequence; isolated selected endpoints are repaired. No home is privileged.
    A separate RNG leaves planets, guardians and ordinary campaign rolls alone.
    """
    rng = random.Random(f"{game.seed}:forgotten-network:v1")
    stars = [s.id for s in game.systems if s.kind != black_holes.KIND]
    degrees = {}
    for sid in stars:
        degree = 0
        while degree < len(stars)-1 and rng.random() < .5:
            degree += 1
        if degree:
            degrees[sid] = degree
    if len(stars) >= 2 and len(degrees) < 2:
        # Avoid a vacuous or impossible exploration objective in tiny galaxies.
        for sid in rng.sample([sid for sid in stars if sid not in degrees], 2-len(degrees)):
            degrees[sid] = 1
    nodes = list(degrees)
    rng.shuffle(nodes)
    rank = {sid: i for i, sid in enumerate(nodes)}
    remaining = {sid: min(degree, len(nodes)-1) for sid, degree in degrees.items()}
    if sum(remaining.values()) % 2:
        largest = max(nodes, key=lambda sid: (remaining[sid], rank[sid]))
        remaining[largest] += -1 if remaining[largest] > 1 else 1
    pairs = set()
    while remaining:
        source = max(remaining, key=lambda sid: (remaining[sid], rank[sid]))
        degree = remaining.pop(source)
        targets = sorted(remaining, key=lambda sid: (-remaining[sid], rank[sid]))[:degree]
        for destination in targets:
            pairs.add(tuple(sorted((source, destination))))
            remaining[destination] -= 1
        remaining = {sid: degree for sid, degree in remaining.items() if degree > 0}
    connected = {sid for pair in pairs for sid in pair}
    for sid in nodes:
        if sid not in connected:
            destination = rng.choice([other for other in nodes if other != sid])
            pairs.add(tuple(sorted((sid, destination))))
            connected.update((sid, destination))
    return [HiddenHyperlane(*pair) for pair in sorted(pairs)]


def seed_network(game):
    game.hidden_hyperlanes = generate_network(game)
    survey_stationed(game)


def survey_stationed(game, owner=None):
    """Remember inspected systems without revealing their undiscovered endpoints."""
    for empire in game.owners if owner is None else (owner,):
        if not motherships.is_wanderer(game, empire):
            continue
        known = set(game.hyperlane_surveys.get(empire, []))
        known.update(s.system_id for s in motherships.homes(game, empire)
                     if not s.has_course and work_error(game, s.system_id, empire) is None)
        game.hyperlane_surveys[empire] = sorted(known)


def discovery_count(game, owner="player"):
    return len({tuple(sorted((p.system_id, p.destination))) for p in game.hyperlane_projects
                if p.owner == owner and p.complete})


@dataclass
class HyperlaneProject:
    owner: str
    system_id: int
    destination: int
    cost: int = RESEARCH_COST
    progress: int = 0
    allocation: int = 50
    paused: bool = False
    started_turn: int = 1
    completed_turn: int = 0
    news_read: bool = False

    @property
    def complete(self):
        return self.progress == self.cost


def project_at(game, system_id, owner="player"):
    projects = [p for p in game.hyperlane_projects if p.owner == owner and p.system_id == system_id]
    return next((p for p in projects if not p.complete), projects[-1] if projects else None)


def connections(game, system_id, owner="player"):
    if not motherships.is_wanderer(game, owner):
        return []
    return sorted(p.destination if p.system_id == system_id else p.system_id
                  for p in game.hyperlane_projects if p.owner == owner and p.complete
                  and system_id in (p.system_id, p.destination))


def connects(game, origin, destination, owner="player"):
    return destination in connections(game, origin, owner)


def visible_routes(game):
    return [p for p in game.hyperlane_projects if p.complete and (game.is_observer or p.owner == "player")]


def stationed_homes(game, system_id, owner):
    return [s for s in motherships.homes(game, owner) if s.system_id == system_id and not s.has_course]


def work_error(game, system_id, owner="player"):
    from . import encounters
    if not motherships.is_wanderer(game, owner):
        return "Only the Wanderers can decipher forgotten hyperlanes."
    if game.systems[system_id].kind == black_holes.KIND:
        return "Research requires an ordinary star system."
    if not stationed_homes(game, system_id, owner):
        return "Station a mothership here without a departure order to conduct research."
    if monsters.alive_at(game, system_id):
        return "Defeat the system guardian before researching its hyperlane."
    if encounters.blockade(game, system_id):
        return "Pirate ships are blocking hyperlane research."
    if any(hostile(game, owner, s.owner) and (s.damage or s.drone_bays)
           for s in game.ships if not s.in_transit and s.system_id == system_id):
        return "Hostile armed ships are blocking research."
    return None


def candidates(game, system_id, owner):
    # Reserve unfinished destinations too: pausing cannot create duplicate links.
    linked = {p.destination if p.system_id == system_id else p.system_id
              for p in game.hyperlane_projects if p.owner == owner
              and system_id in (p.system_id, p.destination)}
    return sorted(p.second if p.first == system_id else p.first for p in game.hidden_hyperlanes
                  if system_id in p.pair and (p.second if p.first == system_id else p.first) not in linked)


def start_error(game, system_id, owner="player"):
    if reason := game.strategy_error(owner):
        return reason
    if type(system_id) is not int or not 0 <= system_id < len(game.systems):
        return "Choose a star system."
    project = project_at(game, system_id, owner)
    if project is not None and not project.complete:
        return "Research one forgotten hyperlane at a time in this system."
    if reason := work_error(game, system_id, owner):
        return reason
    if not candidates(game, system_id, owner):
        return "No undiscovered, unreserved forgotten hyperlanes remain in this system."
    return None


def start(game, system_id, owner="player"):
    from .model import RuleError
    if reason := start_error(game, system_id, owner):
        raise RuleError(reason)
    survey_stationed(game, owner)
    rng = random.Random(f"{game.seed}:forgotten-hyperlane:{owner}:{system_id}:{len(game.hyperlane_projects)}")
    destination = rng.choice(candidates(game, system_id, owner))
    project = HyperlaneProject(owner, system_id, destination, started_turn=game.turn)
    game.hyperlane_projects.append(project)
    return project


def configure(game, system_id, *, allocation=None, paused=None, owner="player"):
    from .model import RuleError
    game._require_strategy(owner)
    project = project_at(game, system_id, owner)
    if project is None or project.complete:
        raise RuleError("There is no unfinished hyperlane research here.")
    if allocation is not None and (type(allocation) is not int or not 0 <= allocation <= 100):
        raise RuleError("Choose a research contribution from 0 to 100 percent.")
    if paused is not None and type(paused) is not bool:
        raise RuleError("Invalid research setting.")
    if allocation is not None:
        project.allocation = allocation
    if paused is not None:
        project.paused = paused


def local_research(game, system_id, owner="player"):
    return sum(game.planet_yields(s.habitat)[2] for s in stationed_homes(game, system_id, owner))


def contribution(game, project):
    if project.complete or project.paused or not project.allocation or work_error(game, project.system_id, project.owner):
        return 0
    points = local_research(game, project.system_id, project.owner)
    return min(project.cost-project.progress, max(1, points*project.allocation//100)) if points else 0


def allocations(game, owner):
    frozen = getattr(game, "_turn_hyperlanes", None)
    if frozen is not None:
        return {sid: amount for (o, sid), amount in frozen.items() if o == owner}
    return {p.system_id: contribution(game, p) for p in game.hyperlane_projects if p.owner == owner and not p.complete}


def freeze(game):
    game._turn_hyperlanes = {(p.owner, p.system_id): contribution(game, p)
                            for p in game.hyperlane_projects if not p.complete}


def complete(game, project):
    project.completed_turn = game.turn
    message = (f"Forgotten hyperlane discovered: {game.systems[project.system_id].name} ↔ "
               f"{game.systems[project.destination].name} · 1 turn in either direction")
    if project.owner != "player":
        game.rival_event(message, owner=project.owner)
    return message


def finish_work(game):
    messages = []
    for project in game.hyperlane_projects:
        if project.complete:
            continue
        project.progress += getattr(game, "_turn_hyperlanes", {}).get((project.owner, project.system_id), 0)
        if project.complete:
            message = complete(game, project)
            if project.owner == "player":
                messages.append(message)
    return messages


def invest(game, system_id, owner="player"):
    """Voluntarily spend banked RP; completed technology progress is never refunded."""
    from .model import RuleError
    game._require_strategy(owner)
    project = project_at(game, system_id, owner)
    if project is None or project.complete:
        raise RuleError("There is no unfinished hyperlane research here.")
    if reason := work_error(game, system_id, owner):
        raise RuleError(reason)
    empire = game._empire(owner)
    amount = min(empire.research, project.cost-project.progress)
    if not amount:
        raise RuleError("No banked research points are available.")
    empire.research -= amount
    project.progress += amount
    message = complete(game, project) if project.complete else f"Invested {amount} RP in forgotten hyperlane research."
    if project.complete:
        game.check_victory(convene=False)
    return message


def ai_orders(game, owner):
    if not motherships.is_wanderer(game, owner):
        return
    survey_stationed(game, owner)
    for sid in sorted({s.system_id for s in motherships.homes(game, owner) if not s.has_course}):
        if start_error(game, sid, owner) is None and local_research(game, sid, owner) > 0:
            start(game, sid, owner)
            game.rival_event(f"Researching a forgotten hyperlane at {game.systems[sid].name}.", owner=owner)


def load(game, data, version):
    from .model import _integer
    if version >= 48:
        network = data["hidden_hyperlanes"]
        if not isinstance(network, list) or len(network) > len(game.systems)*(len(game.systems)-1)//2:
            raise ValueError("Invalid hidden hyperlane network")
        pairs = set()
        for row in network:
            if not isinstance(row, dict) or set(row) != {"first", "second"}:
                raise ValueError("Invalid hidden hyperlane")
            a, b = row["first"], row["second"]
            if (not _integer(a, 0, len(game.systems)-1) or not _integer(b, 0, len(game.systems)-1)
                    or a >= b or (a, b) in pairs
                    or any(game.systems[sid].kind == black_holes.KIND for sid in (a, b))):
                raise ValueError("Invalid hidden hyperlane endpoints")
            pairs.add((a, b))
            game.hidden_hyperlanes.append(HiddenHyperlane(a, b))
        if len([s for s in game.systems if s.kind != black_holes.KIND]) >= 2 and not pairs:
            raise ValueError("Empty hidden hyperlane network")
        surveys = data["hyperlane_surveys"]
        if not isinstance(surveys, dict):
            raise ValueError("Invalid hyperlane surveys")
        for owner, systems in surveys.items():
            if (not motherships.is_wanderer(game, owner) or not isinstance(systems, list)
                    or any(not _integer(sid, 0, len(game.systems)-1)
                           or game.systems[sid].kind == black_holes.KIND for sid in systems)
                    or len(set(systems)) != len(systems)):
                raise ValueError("Invalid hyperlane survey")
            game.hyperlane_surveys[owner] = systems.copy()
    else:
        game.hidden_hyperlanes = generate_network(game)
    rows = data["hyperlane_projects"] if version >= 46 else []
    limit = len(game.systems)*(len(game.systems)-1)//2*len(game.owners)
    if not isinstance(rows, list) or len(rows) > limit:
        raise ValueError("Invalid hyperlane research")
    sources, pairs = set(), set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(HyperlaneProject.__dataclass_fields__):
            raise ValueError("Invalid hyperlane project")
        p = HyperlaneProject(**row)
        if (not isinstance(p.owner, str) or not motherships.is_wanderer(game, p.owner)
                or not _integer(p.system_id, 0, len(game.systems)-1)
                or not _integer(p.destination, 0, len(game.systems)-1) or p.system_id == p.destination
                or any(game.systems[sid].kind == black_holes.KIND for sid in (p.system_id, p.destination))
                or not _integer(p.cost, 1, 1_000_000_000) or not _integer(p.progress, 0, p.cost)
                or not _integer(p.allocation, 0, 100) or type(p.paused) is not bool
                or type(p.news_read) is not bool or (p.news_read and not p.complete)
                or not _integer(p.started_turn, 1, game.turn)
                or not _integer(p.completed_turn, p.started_turn if p.complete else 0, game.turn if p.complete else 0)):
            raise ValueError("Invalid hyperlane research progress")
        source = (p.owner, p.system_id)
        pair = (p.owner, *sorted((p.system_id, p.destination)))
        if (not p.complete and source in sources) or pair in pairs:
            raise ValueError("Duplicate hyperlane research")
        if not p.complete:
            sources.add(source)
        pairs.add(pair)
        lane = HiddenHyperlane(*pair[1:])
        if lane not in game.hidden_hyperlanes:
            if version >= 48:
                raise ValueError("Project is not part of the hidden network")
            game.hidden_hyperlanes.append(lane)
        if version < 48:
            visited = game.hyperlane_surveys.setdefault(p.owner, [])
            if p.system_id not in visited:
                visited.append(p.system_id)
        game.hyperlane_projects.append(p)
    if version < 48:
        game.hidden_hyperlanes.sort(key=lambda lane: lane.pair)
    for ship in game.ships:
        if ship.hyperlane and not connects(game, ship.system_id, ship.destination, ship.owner):
            raise ValueError("Ship using an undiscovered hyperlane")
