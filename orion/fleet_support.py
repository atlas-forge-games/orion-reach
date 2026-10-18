"""Passive fleet cooperation, derived from living ships and current positions.

No actions, timers or stored aura state: movement and casualties take effect
immediately, including when a battle is resumed from a save.
"""

import math
from .designs import HULLS, MODULES
from . import flagships

ESCORT_CAP = 50
DRONE_ESCORT_CAP = 40
TOTAL_INTERCEPTION_CAP = 90
STOCK_SUPPORT = {"destroyer": "escort_array", "titan": "flag_bridge"}
EFFECTS = ("escort_interception", "command_accuracy", "jamming")


def equipment(ship):
    if ship.design:
        return tuple(m for m in ship.design.specs if any(getattr(m, key) for key in EFFECTS))
    identifier = STOCK_SUPPORT.get(ship.kind)
    return (MODULES[identifier],) if identifier else ()


def auras(ship):
    if ship.hull <= 0:
        return ()
    return tuple((effect, getattr(module, effect), module.support_range)
                 for module in equipment(ship) for effect in EFFECTS
                 if getattr(module, effect) and module.support_range)


def eligible(ship, effect):
    # Autonomous strike craft and planetary batteries have their own fire control.
    return effect != "command_accuracy" or ship.kind in HULLS or ship.kind == "mothership"


def sources(state, target, effect):
    if state is None or target.hull <= 0 or not eligible(target, effect):
        return ()
    found = []
    for ship in state.fleet(target.owner):
        if ship.id == target.id:
            continue
        strength = max((value for key, value, radius in auras(ship)
                        if key == effect and math.dist(ship.position, target.position) <= radius), default=0)
        if strength:
            found.append((ship, strength))
    return tuple(found)


def strongest(state, target, effect):
    return max((value for _, value in sources(state, target, effect)), default=0)


def command_accuracy(state, target):
    """Equipment and innate flagship command share the strongest-source rule."""
    return max(strongest(state, target, "command_accuracy"),
               flagships.ACCURACY if flagships.source(state, target) else 0)


def screen_sources(state, target):
    if state is None or target is None or target.hull <= 0:
        return ()
    identifiers = [s.id for s, _ in sources(state, target, "escort_interception")]
    identifiers.extend(s.id for s in state.fleet(target.owner) if s.drone_role == "interceptor"
                       and s.id != target.id and math.dist(s.position, target.position) <= 2)
    return tuple(dict.fromkeys(identifiers))


def interception_breakdown(state, target):
    local = target.design.interception if target.design else 0
    escorts = sum(value for _, value in sources(state, target, "escort_interception"))
    drones = min(DRONE_ESCORT_CAP, 20*sum(
        s.drone_role == "interceptor" and s.id != target.id
        and math.dist(s.position, target.position) <= 2
        for s in state.fleet(target.owner))) if state and target.hull > 0 else 0
    shared = min(ESCORT_CAP, escorts+drones)
    return {"local": local, "destroyers": escorts, "drones": drones,
            "shared": shared, "total": min(TOTAL_INTERCEPTION_CAP, local+shared)}


def providing_text(ship):
    names = {"escort_interception": "Escort", "command_accuracy": "Command", "jamming": "ECM"}
    parts = []
    for key, value, radius in auras(ship):
        amount = f"{value}%" if key == "escort_interception" else f"{'−' if key == 'jamming' else '+'}{value} aim"
        parts.append(f"{names[key]} {amount} / {radius} cells")
    return " · ".join(parts)


def receiving_text(state, ship, *, accuracy=True):
    screen = interception_breakdown(state, ship)["shared"]
    command = command_accuracy(state, ship) if accuracy else 0
    jam = strongest(state, ship, "jamming") if accuracy else 0
    evasion = flagships.evasion(state, ship) if accuracy else 0
    return f"Allies: PD +{screen}% · aim +{command} · evade +{evasion} · ECM {jam}"


def anchor_for(state, ship):
    """An AI support ship follows a combatant, never another pure escort loop."""
    if flagships.is_flagship(state, ship):
        return None
    effects = auras(ship)
    if not effects:
        return None
    escort = any(key == "escort_interception" for key, _, _ in effects)
    candidates = []
    for ally in state.fleet(ship.owner):
        if ally.id == ship.id or ally.kind in ("combat_drone", "missile_base"):
            continue
        own_effects = auras(ally)
        if escort:
            # Capital ships (including a flagship) lead their smaller screen.
            if ally.kind not in ("cruiser", "battleship", "carrier", "titan", "mothership", "colony_ship", "troop_transport"):
                continue
        elif own_effects or not (ally.damage or ally.drone_bays):
            continue
        candidates.append(ally)
    if not candidates:
        return None
    return min(candidates, key=lambda ally: (
        -int(ally.kind in ("battleship", "carrier", "titan", "mothership")),
        math.dist(ship.position, ally.position), -ally.max_hull, ally.id))
