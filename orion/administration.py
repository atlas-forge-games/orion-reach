"""Shared empire administration, local capital distance and integration rules."""

from dataclasses import dataclass
import math

from .production import distance_ly

SYSTEM_STRAIN = 4
INTEGRATION_STRAIN = 4
INTEGRATION_TURNS = 8
DISTANCE_STRAIN = 18
DISTANCE_UNIT_LY = 7.0
MAX_STRAIN = 90
RESEARCH_SENSITIVITY = 100
CREDITS_SENSITIVITY = 100
INDUSTRY_SENSITIVITY = 50
MINING_SENSITIVITY = 50
FOOD_SENSITIVITY = 25


def sensitivity(kind):
    return {"research": RESEARCH_SENSITIVITY, "credits": CREDITS_SENSITIVITY,
            "industry": INDUSTRY_SENSITIVITY, "mining": MINING_SENSITIVITY,
            "food": FOOD_SENSITIVITY}[kind]


def reduced_output(value, bonuses, kind):
    """Apply after output bonuses, before upkeep. Keep whole-unit rounding local."""
    strain = (bonuses or {}).get("administrative_strain", 0)
    return max(0, math.floor(value*(1-strain*sensitivity(kind)/10000)+1e-9))


def settled_systems(game, owner):
    return {s.id for s in game.systems if any(p.colonized and p.owner == owner for p in s.worlds)}


def snapshot(game):
    return {owner: settled_systems(game, owner) for owner in game.owners}


def normalize(game):
    """Discard expired timers and those belonging to lost or destroyed colonies."""
    cleaned = {}
    for owner, timers in game.system_integration.items():
        if owner not in game.owners:
            continue
        owned = settled_systems(game, owner)
        active = {sid: until for sid, until in timers.items()
                  if int(sid) in owned and until > game.turn}
        if active:
            cleaned[owner] = active
    game.system_integration = cleaned


def ownership_changed(game, before):
    """Acquiring a second planet cannot restart integration of its system."""
    normalize(game)
    if not INTEGRATION_TURNS:
        return
    for owner in game.owners:
        old = before.get(owner, set())
        new = settled_systems(game, owner)-old
        if not old:
            # An empire's founding capital is mature, including awakened Remnants.
            headquarters = game.headquarters(owner)
            if headquarters:
                new.discard(headquarters[0].id)
        for sid in new:
            game.system_integration.setdefault(owner, {})[str(sid)] = game.turn+INTEGRATION_TURNS


@dataclass(frozen=True)
class StrainReport:
    systems: int = 0
    integrating: int = 0
    capital: str = "No capital"
    distance_ly: float = 0
    empire: float = 0
    integration: float = 0
    distance: float = 0
    integration_remaining: int = 0

    @property
    def uncapped(self):
        return self.empire+self.integration+self.distance

    @property
    def total(self):
        return min(MAX_STRAIN, self.uncapped)

    def loss(self, kind):
        return self.total*sensitivity(kind)/100


class Context:
    """One economic snapshot, also usable for copies and future queue estimates."""
    def __init__(self, game, owner):
        self.owner, self.turn = owner, game.turn
        self.systems = settled_systems(game, owner) if owner in game.owners else set()
        headquarters = game.headquarters(owner) if self.systems else None
        self.capital = headquarters[0] if headquarters else None
        self.locations = {(p.id, p.name): s.id for s in game.systems for p in s.worlds}
        self.distances = {s.id: distance_ly(self.capital, s) if self.capital else 0 for s in game.systems}
        self.timers = {int(sid): until for sid, until in game.system_integration.get(owner, {}).items()
                       if int(sid) in self.systems}

    def report(self, system_id, *, turns=0, acquiring=False):
        new = acquiring and system_id not in self.systems
        count = len(self.systems)+int(new)
        turn = self.turn+turns
        integrating = sum(until > turn for until in self.timers.values())
        adding_timer = new and bool(self.systems) and INTEGRATION_TURNS > turns
        integrating += int(adding_timer)
        distance = self.distances[system_id] if self.capital else 0
        return StrainReport(count, integrating, self.capital.name if self.capital else "New capital",
                            distance, SYSTEM_STRAIN*max(0, count-1), INTEGRATION_STRAIN*integrating,
                            DISTANCE_STRAIN*max(0, distance/DISTANCE_UNIT_LY-1),
                            max(0, (self.turn+INTEGRATION_TURNS if adding_timer else self.timers.get(system_id, turn))-turn))

    def effects(self, planet, *, turns=0):
        if not planet.colonized or planet.owner != self.owner:
            return {}
        sid = self.locations.get((planet.id, planet.name))
        return {"administrative_strain": self.report(sid, turns=turns).total} if sid is not None else {}


def report(game, planet):
    if not planet.colonized or planet.owner not in game.owners:
        return StrainReport()
    context = Context(game, planet.owner)
    sid = context.locations.get((planet.id, planet.name))
    return context.report(sid) if sid is not None else StrainReport()


def settlement_preview(game, system_id, owner="player"):
    context = Context(game, owner)
    current = context.report(system_id)
    future = context.report(system_id, acquiring=True)
    size = future.empire-current.empire
    temporary = future.integration-current.integration
    if size or temporary:
        change = (f"Empire strain +{size:g} points, plus +{temporary:g} for {INTEGRATION_TURNS} turns. ")
    else:
        change = "Existing settled system: no additional empire or integration strain. "
    return (change+f"This system: {future.distance_ly:.1f} ly from {future.capital}; "
            f"distance strain {future.distance:.1f}%. Combined colony strain {future.total:.1f}% "
            f"(cap {MAX_STRAIN:g}%).")


def load(game, data, version):
    # Old campaigns have no trustworthy acquisition dates. Preserve their history
    # and apply size/distance now, treating their existing colonies as integrated.
    if version < 41:
        game.system_integration = {}
        return
    records = data["system_integration"]
    if not isinstance(records, dict) or set(records)-set(game.owners):
        raise ValueError("Invalid integration empires")
    parsed = {}
    for owner, timers in records.items():
        if not isinstance(timers, dict) or len(timers) > len(game.systems):
            raise ValueError("Invalid integration systems")
        owned = settled_systems(game, owner)
        parsed[owner] = {}
        for sid, until in timers.items():
            if (not isinstance(sid, str) or not sid.isascii() or not sid.isdecimal()
                    or len(sid) > 3 or str(int(sid)) != sid or int(sid) not in owned
                    or type(until) is not int or not 1 <= until <= game.turn+INTEGRATION_TURNS):
                raise ValueError("Invalid integration timer")
            parsed[owner][sid] = until
    game.system_integration = parsed
    normalize(game)
