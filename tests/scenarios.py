"""Explicit empty-fleet scenarios for production, economics and legacy-save tests.

New-campaign starting fleets are tested through the real new_game entry point in
test_starting_fleets.py. Older tests often construct their own ships or assert
the output of a shipyard in isolation, so their setup deliberately clears units.
"""

from orion.model import new_game


def empty_fleet_game(*args, **kwargs):
    game = new_game(*args, **kwargs)
    game.ships.clear()
    game.next_ship_id = 1
    return game


def place_near(game, system_id, anchor=0, distance=10):
    """Position a specific regression encounter inside the colony supply radius."""
    origin, target = game.systems[anchor], game.systems[system_id]
    offset = distance/140
    target.x = origin.x+offset if origin.x+offset <= .94 else origin.x-offset
    target.y = origin.y
    return target
