"""Fleet-only sensor observations, limited intelligence and persistent last sightings."""

from collections import Counter
from dataclasses import dataclass, replace
import math

from .fleets import group_fleets
from .navigation import hostile, position
from . import black_holes

CONTACT_LIFETIME = 20
ARRAY_RANGE = 5
MAX_CONTACTS_PER_EMPIRE = 200
MAX_REPORTS = 200


@dataclass
class Contact:
    observer: str
    anchor: int
    owner: str
    x: float
    y: float
    seen_turn: int
    near_system: int
    level: int
    count: int | None = None
    classes: list[str] = None
    heading: float | None = None
    active: bool = True

    def __post_init__(self):
        if self.classes is None:
            self.classes = []


@dataclass(frozen=True)
class SensorReport:
    id: int
    turn: int
    observer: str
    owner: str
    system_id: int
    count: int | None


def centers(game, owner="player"):
    radius = game.bonuses_for(owner).get("sensor_range", 0)
    if not radius:
        return []
    return [(s, radius+(ARRAY_RANGE if any(p.owner == owner and game.building_operational(p, "sensor_array") for p in s.worlds) else 0))
            for s in game.colony_systems(owner)]


def distance(x, y, system):
    return math.hypot((x-system.x)*140, (y-system.y)*100)


def detection_level(game, ship, owner="player", coverage=None):
    if not black_holes.fleet_charted(game, ship, owner):
        return 0
    if ship.owner == owner or not game.fog_of_war:
        return 3
    if not ship.in_transit and game.system_visible(ship.system_id, owner):
        return 3
    x, y = position(game, ship)
    if any(distance(x, y, s) <= radius+1e-9 for s, radius in (centers(game, owner) if coverage is None else coverage)):
        return game.bonuses_for(owner).get("sensor_level", 0)
    return 0


def observed(game, owner="player"):
    result = []
    colonies = game.colony_systems(owner)
    if not colonies:
        return result
    coverage = centers(game, owner)
    for ships in group_fleets(game.ships):
        ship = ships[0]
        if ship.owner == owner:
            continue
        level = detection_level(game, ship, owner, coverage)
        if not level:
            continue
        x, y = position(game, ship)
        near = min(colonies, key=lambda s: (distance(x, y, s), s.id))
        classes = [f"{kind.replace('_', ' ').title()} × {count}" for kind, count in sorted(Counter(s.kind for s in ships).items())] if level >= 3 else []
        heading = None
        if level >= 3 and ship.in_transit:
            target, origin = game.systems[ship.destination], game.systems[ship.system_id]
            heading = math.degrees(math.atan2((target.y-origin.y)*100, (target.x-origin.x)*140))%360
        result.append(Contact(owner, ship.id, ship.owner, x, y, game.turn, near.id, level,
                              len(ships) if level >= 2 else None, classes, heading))
    return result


def contacts(game, owner="player"):
    if not game.fog_of_war:
        return []
    current = {c.anchor: c for c in observed(game, owner)}
    rows = [replace(c, active=False) for c in game.sensor_contacts if c.observer == owner
            and c.anchor not in current and game.turn-c.seen_turn <= CONTACT_LIFETIME]
    rows.extend(current.values())
    return sorted(rows, key=lambda c: (not c.active, -c.seen_turn, c.anchor))


def refresh(game):
    if not game.fog_of_war:
        return
    saved = {(c.observer, c.anchor): c for c in game.sensor_contacts}
    updated = []
    for owner in game.owners:
        current = observed(game, owner)
        active = {c.anchor for c in current}
        for contact in current:
            old = saved.get((owner, contact.anchor))
            if hostile(game, owner, contact.owner) and (old is None or (not old.active and old.seen_turn < game.turn)):
                game.sensor_reports.append(SensorReport(game.next_sensor_report_id, game.turn, owner,
                                                        contact.owner, contact.near_system, contact.count))
                game.next_sensor_report_id += 1
        history = [replace(c, active=False) for c in game.sensor_contacts if c.observer == owner
                   and c.anchor not in active and game.turn-c.seen_turn <= CONTACT_LIFETIME]
        updated.extend(sorted(current+history, key=lambda c: (not c.active, -c.seen_turn, c.anchor))[:MAX_CONTACTS_PER_EMPIRE])
    game.sensor_contacts = updated
    game.sensor_reports = game.sensor_reports[-MAX_REPORTS:]


def load(game, data):
    from .model import _integer
    contacts_data, reports_data = data["sensor_contacts"], data["sensor_reports"]
    if not isinstance(contacts_data, list) or len(contacts_data) > len(game.owners)*MAX_CONTACTS_PER_EMPIRE:
        raise ValueError("Invalid sensor contacts")
    rows, keys = [], set()
    for row in contacts_data:
        if not isinstance(row, dict) or set(row) != set(Contact.__dataclass_fields__):
            raise ValueError("Invalid sensor contact")
        c = Contact(**row)
        key = c.observer, c.anchor
        if (c.observer not in game.owners or c.owner not in game.owners or c.observer == c.owner or key in keys
                or not _integer(c.anchor, 1, game.next_ship_id-1) or not _integer(c.seen_turn, 1, game.turn)
                or not _integer(c.near_system, 0, len(game.systems)-1) or not _integer(c.level, 1, 3)
                or type(c.active) is not bool or (c.active and c.seen_turn != game.turn)
                or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in (c.x, c.y))
                or (c.count is not None and not _integer(c.count, 1, 10000))
                or (c.level == 1 and c.count is not None) or (c.level >= 2 and c.count is None)
                or not isinstance(c.classes, list) or len(c.classes) > 10
                or any(not isinstance(v, str) or not 1 <= len(v) <= 60 or not v.isprintable() for v in c.classes)
                or (c.heading is not None and (type(c.heading) not in (int, float) or not math.isfinite(c.heading) or not 0 <= c.heading < 360))
                or (c.level < 3 and (c.classes or c.heading is not None))):
            raise ValueError("Invalid sensor observation")
        keys.add(key)
        rows.append(c)
    if not isinstance(reports_data, list) or len(reports_data) > MAX_REPORTS:
        raise ValueError("Invalid sensor reports")
    reports, previous = [], 0
    for row in reports_data:
        if not isinstance(row, dict) or set(row) != set(SensorReport.__dataclass_fields__):
            raise ValueError("Invalid sensor report")
        r = SensorReport(**row)
        if (not _integer(r.id, previous+1, 1_000_000_000) or not _integer(r.turn, 1, game.turn)
                or r.observer not in game.owners or r.owner not in game.owners or r.owner == r.observer
                or not _integer(r.system_id, 0, len(game.systems)-1)
                or (r.count is not None and not _integer(r.count, 1, 10000))):
            raise ValueError("Invalid sensor dispatch")
        reports.append(r)
        previous = r.id
    if (not _integer(data["next_sensor_report_id"], previous+1, 1_000_000_000)
            or not _integer(data["sensor_news_read"], 0, data["next_sensor_report_id"]-1)):
        raise ValueError("Invalid sensor news cursor")
    game.sensor_contacts, game.sensor_reports = rows, reports
    game.next_sensor_report_id, game.sensor_news_read = data["next_sensor_report_id"], data["sensor_news_read"]
