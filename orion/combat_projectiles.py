"""Persistent homing ordnance; launch and impact are separate combat actions."""

from dataclasses import dataclass
import math

from .weapons import BEAMS

SPEED = 5
MAX_FLIGHT_ROUNDS = 6


@dataclass
class Projectile:
    id: int
    source_id: int
    target_id: int
    owner: str
    weapon: str
    strength: int
    chance: int
    roll: int
    x: float
    y: float
    age: int = 0

    @property
    def position(self):
        return self.x, self.y


def eta(projectile, target):
    return max(1, math.ceil(math.dist(projectile.position, target.position)/SPEED))


def load(rows, state):
    """Validate flight snapshots against the actual ships and their equipment."""
    from .combat import BOARD_COLUMNS, shot_strengths
    from .model import _integer
    if not isinstance(rows, list) or len(rows) > min(1_000_000, state.shots_fired):
        raise ValueError("Invalid projectile list")
    if rows and state.status != "active":
        raise ValueError("Resolved combat has ordnance in flight")
    result, identifiers = [], set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(Projectile.__dataclass_fields__):
            raise ValueError("Invalid projectile fields")
        source, target = state.ship(row["source_id"]), state.ship(row["target_id"])
        if (source is None or target is None or target.hull <= 0 or source.owner == target.owner
                or row["owner"] != source.owner or not isinstance(row["weapon"], str)
                or row["weapon"] not in BEAMS or not BEAMS[row["weapon"]].projectile):
            raise ValueError("Invalid projectile participants or weapon")
        if (not _integer(row["id"], 0, state.shots_fired-1) or row["id"] in identifiers
                or not _integer(row["age"], 0, MAX_FLIGHT_ROUNDS-1)
                or not _integer(row["chance"], 0, 100) or not _integer(row["roll"], 0, 99)
                or type(row["strength"]) is not int
                or not any(row["weapon"] == weapon and row["strength"] in shot_strengths(weapon, strength)
                           for weapon, strength, _ in source.weapons)):
            raise ValueError("Invalid projectile payload")
        if any(type(row[key]) not in (int, float) or not 0 <= row[key] <= limit or not math.isfinite(row[key])
               for key, limit in (("x", BOARD_COLUMNS-1), ("y", state.rows-1))):
            raise ValueError("Projectile outside the battlefield")
        identifiers.add(row["id"])
        result.append(Projectile(**row))
    return result


def advance(game, owner):
    """Move this side's volleys at the start of its next turn, once per round.

    Every launch gives the opposing side a turn to respond. Aim is fixed at
    launch; current shields and nearby interceptors resolve damage on arrival.
    Returned snapshots drive presentation only and never reapply damage.
    """
    from .combat import hit_damage, check_losses
    from .fleet_support import screen_sources
    state = game.combat
    remaining, events = [], []
    for shot in state.projectiles:
        target = state.ship(shot.target_id)
        if target is None or target.hull <= 0:
            continue
        if shot.owner != owner:
            remaining.append(shot)
            continue
        start = shot.position
        distance = math.dist(start, target.position)
        fraction = min(1.0, SPEED/distance) if distance else 1.0
        shot.x += (target.x-shot.x)*fraction
        shot.y += (target.y-shot.y)*fraction
        shot.age += 1
        event = {"id": shot.id, "source_id": shot.source_id, "target_id": target.id,
                 "weapon": shot.weapon, "start": start, "end": shot.position,
                 "launch": shot.age == 1, "impact": distance <= SPEED, "damage": 0, "absorbed": 0,
                 "destroyed": False, "missed": False, "escorts": ()}
        if event["impact"]:
            event["missed"] = shot.roll >= shot.chance
            if not event["missed"]:
                event["escorts"] = tuple(state.ship(i).position for i in screen_sources(state, target))
                hit, blocked = hit_damage(state, target, shot.weapon, shot.strength)
                target.hull -= hit
                target.shields = target.shields-blocked if target.hull else 0
                event.update(damage=hit, absorbed=blocked, destroyed=target.hull == 0)
                state.record(f"{BEAMS[shot.weapon].name} hit {target.name}: {hit} hull damage, "
                             f"{blocked} shield damage."+(" Escort screen engaged." if event["escorts"] else "")
                             +(" Destroyed." if target.hull == 0 else ""))
            else:
                state.record(f"{BEAMS[shot.weapon].name} missed {target.name}.")
        elif shot.age >= MAX_FLIGHT_ROUNDS:
            state.record(f"{BEAMS[shot.weapon].name} ran out of fuel pursuing {target.name}.")
        else:
            remaining.append(shot)
        events.append(event)
    state.projectiles = remaining
    check_losses(game)
    return events
