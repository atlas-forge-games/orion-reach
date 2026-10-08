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
