"""Neutral system guardians, valuable worlds, and private encounter knowledge."""

from dataclasses import dataclass, field
import random

from .production import distance_ly
from . import black_holes

MONSTER = "monster"
EMPIRES = ("player", "rival")


@dataclass(frozen=True)
class MonsterSpec:
    name: str
    hull: int
    movement: int
    weapon: str
    color: tuple[int, int, int]
    reward: str
    research_reward: int = 0


MONSTERS = {
    "space_serpent": MonsterSpec("Space Serpent", 48, 4, "plasma_breath", (109, 235, 161), "Huge Gaia world"),
    "crystal_guardian": MonsterSpec("Crystal Guardian", 80, 1, "crystal_ray", (111, 208, 255), "Large ultra-rich world"),
    "ancient_sentinel": MonsterSpec("Ancient Sentinel", 96, 2, "ancient_lance", (255, 198, 104), "Ancient ruins + 120 RP", 120),
    "void_leviathan": MonsterSpec("Void Leviathan", 140, 3, "void_ray", (196, 143, 255), "Three exceptional worlds"),
    "ashen_leviathan": MonsterSpec("Ashen Leviathan", 280, 3, "plasma", (255, 194, 113), "Unique legendary relic"),
    "horizon_warden": MonsterSpec("Horizon Warden", 260, 2, "graviton", (201, 178, 255), "Unique legendary relic"),
    "crown_sentinel": MonsterSpec("Crown Sentinel", 320, 2, "heavy_beam", (236, 207, 151), "Unique legendary relic"),
}

# Secondary prize IDs are fixed by orbital order; no planet IDs are added or moved.
PRIZE_WORLDS = {
    "space_serpent": (("Gaia", "Huge", "Rich"),),
    "crystal_guardian": (("Terran", "Large", "Ultra-rich"),),
    "ancient_sentinel": (("Terran", "Large", "Rich"),),
    "void_leviathan": (("Gaia", "Huge", "Rich"), ("Terran", "Large", "Ultra-rich"), ("Ocean", "Large", "Rich")),
}


@dataclass
class Guardian:
    system_id: int
    planet_id: int
    kind: str
    hull: int
    known_player: str = "unknown"
    known_rival: str = "unknown"
    known_others: dict[str, str] = field(default_factory=dict)

    @property
    def alive(self):
        return self.hull > 0

    @property
    def spec(self):
        return MONSTERS[self.kind]

    @property
    def combat_id(self):
        return -self.system_id-1


def at(game, system_id):
    return next((g for g in game.guardians if g.system_id == system_id), None)


def alive_at(game, system_id):
    guardian = at(game, system_id)
    return guardian if guardian and guardian.alive else None


def known_status(game, system_id, owner="player"):
    if not black_holes.charted(game, game.systems[system_id], owner):
        return None
    guardian = at(game, system_id)
    if guardian is None:
        return None
    if game.system_visible(system_id, owner):
        return "alive" if guardian.alive else "defeated"
    status = getattr(guardian, "known_"+owner) if owner in EMPIRES else guardian.known_others.get(owner, "unknown")
    return status if status != "unknown" else None


def observe(game, system_id, owner):
    guardian = at(game, system_id)
    if guardian:
        status = "alive" if guardian.alive else "defeated"
        if owner in EMPIRES:
            setattr(guardian, "known_"+owner, status)
        else:
            guardian.known_others[owner] = status


def prize_ids(system, guardian):
    if guardian.kind not in PRIZE_WORLDS:
        return []
    others = [p.id for p in system.worlds if p.id != guardian.planet_id]
    return [guardian.planet_id] + others[:len(PRIZE_WORLDS[guardian.kind])-1]


def prize_details(guardian, *, defeated=False):
    if guardian.kind not in PRIZE_WORLDS:
        return "Relic recovered" if defeated else "Defeat the guardian to recover one legendary relic"
    if guardian.kind == "space_serpent":
        return "28 B capacity · abundant food · faster growth"
    if guardian.kind == "crystal_guardian":
        return "Mines produce 6 industry each"
    if guardian.kind == "ancient_sentinel":
        return "Large rich world · Ruins already recovered" if defeated else "Large rich world · +120 RP to the victor, once"
    return "Huge Gaia · Large ultra-rich Terran · Large rich Ocean"


def reward_caption(guardian, *, defeated=False):
    if defeated and guardian.kind not in PRIZE_WORLDS:
        return "Relic recovered"
    if defeated and guardian.kind == "ancient_sentinel":
        return "Ruins recovered · Rich world"
    return guardian.spec.reward


def commit_battle_result(game, guardian, hull, owner):
    """Commit damage and award ruins once, on the living-to-defeated transition."""
    was_alive = guardian.alive
    guardian.hull = hull
    if was_alive and not guardian.alive and (site := black_holes.at(game, guardian.system_id)):
        return black_holes.claim(game, site, owner)
    if was_alive and not guardian.alive and guardian.spec.research_reward:
        game._empire(owner).research += guardian.spec.research_reward
        planet = game.planet_at(guardian.system_id, guardian.planet_id)
        return f"Recovered ancient ruins on {planet.name}: +{guardian.spec.research_reward} RP."
    return None


def seed_guardians(game):
    """A separate RNG preserves ordinary generation and keeps both homes safe."""
    homes = [] if game.is_observer else [game.systems[0]]
    homes.extend(game.systems[r.home_system] for r in game.opponents.values())
    candidates = [s for s in game.systems if s.worlds and not any(p.colonized for p in s.worlds)
                  and all(distance_ly(s, home) >= 28 for home in homes)]
    rng = random.Random(f"orion-guardians-v2:{game.seed}")
    rng.shuffle(candidates)
    kinds = list(PRIZE_WORLDS)
    rng.shuffle(kinds)
    kinds = kinds[:2] if game.galaxy_size == "Compact" else kinds
    # Place the three-world prize first, while it has the widest choice of sites.
    kinds.sort(key=lambda kind: -len(PRIZE_WORLDS[kind]))
    for kind in kinds:
        system = next((s for s in candidates if len(s.worlds) >= len(PRIZE_WORLDS[kind])
                       and all(distance_ly(s, game.systems[g.system_id]) >= 18 for g in game.guardians)), None)
        if system is None:
            continue
        planet = max(system.worlds, key=lambda p: (p.habitability, p.building_capacity, -p.id))
        guardian = Guardian(system.id, planet.id, kind, MONSTERS[kind].hull)
        for pid, (biome, size, richness) in zip(prize_ids(system, guardian), PRIZE_WORLDS[kind]):
            prize = system.worlds[pid]
            prize.biome, prize.size, prize.richness, prize.gravity = biome, size, richness, "Normal"
            if pid == 0:
                system.biome, system.richness = biome, richness
        game.guardians.append(guardian)


def parse_guardians(data, game, *, version=20):
    from .model import _integer
    if not isinstance(data, list) or len(data) > len(game.systems):
        raise ValueError("Invalid guardians")
    parsed, occupied = [], set()
    for row in data:
        if version < 20 and isinstance(row, dict):
            row = {k: v for k, v in row.items() if k != "known_others"}
        fields = {"system_id", "planet_id", "kind", "hull", "known_player", "known_rival"}
        if version >= 20:
            fields.add("known_others")
        if not isinstance(row, dict) or set(row) != fields:
            raise ValueError("Invalid guardian record")
        sid, pid, kind = row["system_id"], row["planet_id"], row["kind"]
        if (not _integer(sid, 1, len(game.systems)-1) or sid in occupied
                or not isinstance(kind, str) or kind not in MONSTERS
                or not _integer(pid, -1 if kind not in PRIZE_WORLDS else 0, len(game.systems[sid].worlds)-1)
                or not _integer(row["hull"], 0, MONSTERS[kind].hull)):
            raise ValueError("Invalid guardian location or health")
        site = black_holes.at(game, sid)
        if kind not in PRIZE_WORLDS and (site is None or pid != -1 or black_holes.SITES[site.kind][1] != kind):
            raise ValueError("Legendary guardian requires its black-hole site")
        awakened = {t.planet_id for t in game.tomb_worlds if t.system_id == sid
                    and t.outcome in ("founded", "captured", "reinforced")}
        if any(r.home_system == sid and r.home_planet not in awakened for r in game.opponents.values()):
            raise ValueError("Homeworld cannot be guarded")
        for owner in EMPIRES:
            status = row["known_"+owner]
            if status not in ("unknown", "alive", "defeated") or (status == "defeated" and row["hull"] > 0):
                raise ValueError("Invalid guardian knowledge")
            if owner == "rival" and not game.opponent and status != "unknown":
                raise ValueError("Unknown observer")
        extras = row.get("known_others", {})
        if (not isinstance(extras, dict) or not set(extras) <= set(game.other_opponents)
                or any(status not in ("unknown", "alive", "defeated")
                       or (status == "defeated" and row["hull"] > 0) for status in extras.values())):
            raise ValueError("Invalid guardian observers")
        system = game.systems[sid]
        if row["hull"] and any(p.colonized and p.id not in awakened for p in system.worlds):
            raise ValueError("Living guardian cannot share a colony system")
        guardian = Guardian(**row)
        ids = prize_ids(system, guardian)
        if len(ids) != len(PRIZE_WORLDS.get(kind, ())):
            raise ValueError("Guardian prize worlds are missing")
        for planet_id, reward in zip(ids, PRIZE_WORLDS.get(kind, ())):
            planet = system.worlds[planet_id]
            if (planet.biome, planet.size, planet.richness) != reward:
                raise ValueError("Guardian prize does not match its world")
        occupied.add(sid)
        parsed.append(guardian)
    return parsed


def intercept(game):
    """Human encounters pause the turn; AI encounters use identical tactical rules."""
    from . import combat
    if game.combat or game.result:
        return False
    for guardian in game.guardians:
        if (guardian.alive and game.fleet_at(guardian.system_id, "player") and
                (not black_holes.at(game, guardian.system_id) or black_holes.can_explore(game))):
            combat.begin_guardian_combat(game, guardian.system_id, "player")
            return True
    for guardian in game.guardians:
        for owner in game.opponents:
            if not guardian.alive or not game.fleet_at(guardian.system_id, owner):
                continue
            if black_holes.at(game, guardian.system_id) and not black_holes.can_explore(game, owner):
                continue
            combat.begin_guardian_combat(game, guardian.system_id, owner)
            combat.autoresolve(game)
            if game.combat:
                game.finish_combat()
    return False


def ai_orders(game, owner="rival"):
    """Gather a sufficient escort at a colony before attacking a known guardian."""
    if owner not in game.opponents or any(game.diplomacy_between(owner, other).relations < -30
                                         and not game.diplomacy_between(owner, other).non_aggression_active
                                         for other in game.owners if other != owner):
        return set()
    targets = [g for g in game.guardians if (known_status(game, g.system_id, owner) == "alive" or
               (black_holes.at(game, g.system_id) and black_holes.can_explore(game, owner)
                and known_status(game, g.system_id, owner) is None))
               and (not black_holes.at(game, g.system_id) or black_holes.can_explore(game, owner))
               and game.within_fuel_range(g.system_id, owner)]
    ships = [s for s in game.ships_owned_by(owner) if game.military_strength(s) > 0 and not s.has_course]
    colonies = game.colony_systems(owner)
    if not targets or not ships or not colonies:
        return set()
    staging = max(colonies, key=lambda s: (sum(ship.system_id == s.id for ship in ships), -s.id))
    target = min(targets, key=lambda g: (g.spec.hull, distance_ly(staging, game.systems[g.system_id]), g.system_id))
    ready = [s for s in ships if s.system_id == staging.id]
    attack = sum(s.hull for s in ready) >= target.spec.hull*1.25 and len(ready) >= 3
    for ship in ships:
        destination = target.system_id if attack and ship in ready else staging.id
        if ship.system_id != destination:
            game.send_ship(ship.id, destination, owner=owner)
    return {s.id for s in ships}
