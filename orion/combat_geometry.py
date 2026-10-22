"""Tactical hull footprints and unobstructed direct-fire geometry.

Ship x/y are the top-left occupied cell. Rectangles are fixed in orientation;
there is no rotation action. Old battles retain their saved one-cell layout.
"""

import math


FOOTPRINTS = {
    "destroyer": (2, 1), "cruiser": (2, 2),
    "battleship": (3, 2), "carrier": (3, 2), "titan": (3, 3),
    "mothership": (4, 3), "colony_ship": (2, 1), "troop_transport": (2, 1),
    "space_serpent": (2, 2), "crystal_guardian": (2, 2),
    "ancient_sentinel": (3, 2), "void_leviathan": (3, 3),
    "ashen_leviathan": (3, 3), "horizon_warden": (3, 3), "crown_sentinel": (3, 3),
}


def size(ship):
    return FOOTPRINTS.get(ship.kind, (1, 1)) if ship.large_hull else (1, 1)


def cells(ship, position=None):
    x, y = ship.position if position is None else position
    width, height = size(ship)
    return tuple((x+dx, y+dy) for dx in range(width) for dy in range(height))


def center(ship, position=None):
    x, y = ship.position if position is None else position
    width, height = size(ship)
    return x+(width-1)/2, y+(height-1)/2


def nearest(ship, point, position=None):
    """Nearest occupied cell-centre coordinate (continuous along a hull)."""
    x, y = ship.position if position is None else position
    width, height = size(ship)
    return max(x, min(x+width-1, point[0])), max(y, min(y+height-1, point[1]))


def firing_points(attacker, target, position=None):
    start = nearest(attacker, center(target), position)
    end = nearest(target, start)
    return start, end


def distance(attacker, target, position=None):
    return math.dist(*firing_points(attacker, target, position))


def occupied(state, exclude=None):
    return {cell for ship in state.ships if ship.hull > 0 and ship.id != exclude
            for cell in cells(ship)}


def fits(ship, position, blocked, columns, rows):
    x, y = position
    width, height = size(ship)
    return (0 <= x and x+width <= columns and 0 <= y and y+height <= rows
            and not any(cell in blocked for cell in cells(ship, position)))


def intersects(start, end, ship):
    """Closed segment / hull rectangle test, including diagonal corner contact."""
    width, height = size(ship)
    lower, upper = 0.0, 1.0
    for a, b, lo, hi in zip(start, end,
                            (ship.x-.5, ship.y-.5),
                            (ship.x+width-.5, ship.y+height-.5)):
        delta = b-a
        if abs(delta) < 1e-12:
            if a < lo or a > hi:
                return False
        else:
            enter, leave = sorted(((lo-a)/delta, (hi-a)/delta))
            lower, upper = max(lower, enter), min(upper, leave)
            if lower > upper:
                return False
    return True


def blocker(state, attacker, target, position=None):
    start, end = firing_points(attacker, target, position)
    obstructing = [ship for ship in state.ships
                   if ship.hull > 0 and ship.id not in (attacker.id, target.id)
                   and intersects(start, end, ship)]
    return min(obstructing, key=lambda ship: math.dist(start, center(ship)), default=None)


def clear_line(state, attacker, target, position=None):
    return state is None or blocker(state, attacker, target, position) is None
