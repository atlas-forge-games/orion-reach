"""Explicit empty-fleet scenarios for production, economics and legacy-save tests.

New-campaign starting fleets are tested through the real new_game entry point in
test_starting_fleets.py. Older tests often construct their own ships or assert
the output of a shipyard in isolation, so their setup deliberately clears units.
"""

from orion.model import new_game as make_game


def fixed_start_game(*args, **kwargs):
    kwargs.setdefault("random_starts", False)
    kwargs.setdefault("with_tombs", False)
    game = make_game(*args, **kwargs)
    # These established-colony fixtures retain their historical job allocation.
    # Resource/power tests exercise the real new-game allocation directly.
    for system in game.systems:
        for planet in system.worlds:
            planet.miners = 0
    from orion.exploration import refresh
    refresh(game)
    # Established-campaign fixtures predate the new introductory transmissions.
    # Dedicated first-contact tests use model.new_game directly.
    from orion.first_contact import pending, acknowledge
    for owner in pending(game):
        acknowledge(game, owner)
    return game


new_game = fixed_start_game


def empty_fleet_game(*args, **kwargs):
    # Legacy and isolated economic scenarios predate system guardians.
    kwargs.setdefault("with_guardians", False)
    game = new_game(*args, **kwargs)
    game.ships.clear()
    game.next_ship_id = 1
    return game


def place_near(game, system_id, anchor=0, distance=6):
    """Position a specific regression encounter inside the colony supply radius."""
    origin, target = game.systems[anchor], game.systems[system_id]
    offset = distance/140
    target.x = origin.x+offset if origin.x+offset <= .94 else origin.x-offset
    target.y = origin.y
    return target


def use_nearby_system(game, system_id, *, excluding=()):
    """Give a named test destination a reachable position without crowding the map."""
    import math
    from orion.model import GALAXY_BOUNDS
    from orion.production import distance_ly
    target = game.systems[system_id]
    if game.within_fuel_range(system_id):
        return target
    near = min((s for s in game.systems[1:] if s.id not in excluding and game.within_fuel_range(s.id)),
               key=lambda s: distance_ly(game.systems[0], s), default=None)
    if near is not None:
        target.x, target.y, near.x, near.y = near.x, near.y, target.x, target.y
        return target
    # Movement/UI tests explicitly need a reachable destination. Natural starts
    # can be isolated, so create this fixture only when the test requests it.
    origin = game.systems[0]
    left, right, top, bottom = GALAXY_BOUNDS
    positions = [(origin.x+6.5*math.cos(i*math.pi/16)/140,
                  origin.y+6.5*math.sin(i*math.pi/16)/100) for i in range(32)]
    target.x, target.y = max(
        ((x, y) for x, y in positions if left <= x <= right and top <= y <= bottom),
        key=lambda xy: min(math.hypot((xy[0]-s.x)*1.4, xy[1]-s.y)
                           for s in game.systems if s.id not in (0, target.id)))
    return target


def legacy_economy(game):
    """Prepare credit-paid economic records when constructing pre-v27 fixtures.

    Historical-version tests must not relabel resource-paid projects as old
    saves. Keep their other targeted legacy fields and stale surveys intact.
    A separate fixture from the actual v0.35.1 executable checks real migration.
    """
    for owner in game.owners:
        game._empire(owner).resources = 120
    for system in game.systems:
        for planet in system.worlds:
            planet.miners = 0
            planet.disabled_buildings = []
            for q in planet.construction_queue:
                q.paid_credits = q.paid_credits or q.resource_cost
                q.resource_cost = q.paid_resources = 0
    for survey in game.exploration.surveys:
        for world in survey.worlds:
            world["miners"], world["disabled_buildings"] = 0, []
            for q in world["construction_queue"]:
                q["paid_credits"] = q["paid_credits"] or q["resource_cost"]
                q["resource_cost"] = q["paid_resources"] = 0
