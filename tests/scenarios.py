"""Explicit empty-fleet scenarios for production, economics and legacy-save tests.

New-campaign starting fleets are tested through the real new_game entry point in
test_starting_fleets.py. Older tests often construct their own ships or assert
the output of a shipyard in isolation, so their setup deliberately clears units.
"""

from orion.model import new_game as make_game


def fixed_start_game(*args, **kwargs):
    kwargs.setdefault("random_starts", False)
    kwargs.setdefault("with_tombs", False)
    # These fixtures isolate earlier features. Black-hole tests use new_game directly.
    kwargs.setdefault("with_black_holes", False)
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


def research_to(game, *identifiers, owner='player'):
    """Fund the requested choices and any missing earlier tiers in the active tree."""
    from orion.research import TECHNOLOGIES, choices
    state = game.research_state(owner)
    picks = {(TECHNOLOGIES[t].branch, TECHNOLOGIES[t].tier): t
             for t in identifiers if t != 'ascension_theory'}
    for branch in dict.fromkeys(b for b, _ in picks):
        for tier in range(1, max(t for b, t in picks if b == branch)+1):
            selected = picks.get((branch, tier), choices(branch, tier)[0].id)
            if tier in state.completed_tiers(branch):
                if (branch, tier) in picks and selected not in state.completed:
                    raise AssertionError('Conflicting requested discoveries')
                continue
            game._empire(owner).research += TECHNOLOGIES[selected].cost
            game.choose_research(selected, owner=owner)
    if 'ascension_theory' in identifiers:
        game._empire(owner).research += TECHNOLOGIES['ascension_theory'].cost
        game.choose_research('ascension_theory', owner=owner)


def use_research_layout(test_case, *, legacy=False):
    """Research fixtures explicitly choose their era and restore the prior profile."""
    from orion import balance
    previous = balance.active_profile()
    balance.activate(balance.legacy_profile() if legacy else balance.default_profile())
    test_case.addCleanup(lambda: balance.activate(previous))


def set_idle_trade_goods(game):
    """Choose ongoing production in UI scenarios testing other turn reminders."""
    if not game.strategy_error("player"):
        for system in game.systems:
            for planet in system.worlds:
                if planet.owner == "player" and planet.production_idle:
                    game.set_trade_goods(system.id, planet.id)
    return game


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
        state = game.research_state(owner)
        state.legacy_count = len(state.completed)
        state.legacy_active = state.active is not None
        state.legacy_starships = True
        state.legacy_arsenal = True
        state.legacy_fuel = True
        state.legacy_black_holes = True
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


def migrated_statistics(game):
    """Expected pre-v38 migration: start a new history at the loaded turn."""
    import copy
    from orion.statistics import sample
    expected = copy.deepcopy(game)
    expected.statistics = {owner: [sample(expected, owner)] for owner in expected.owners}
    return expected


def legacy_research_payload(data):
    """Represent research in pre-v28 fixtures using their real three-field schema."""
    if isinstance(data, dict):
        if {"completed", "active", "progress", "legacy_count", "legacy_active"} <= set(data):
            data.pop("legacy_black_holes", None)
            data.pop("legacy_fuel", None)
            data.pop("legacy_arsenal", None)
            data.pop("legacy_starships", None)
            data.pop("legacy_count")
            data.pop("legacy_active")
        else:
            if {"initial_hull", "weapon", "owner"} <= set(data):
                for key in ("cooldowns", "graviton_slow", "repair_remaining", "drone_role"):
                    data.pop(key, None)
                data.pop("carrier_id", None)
                data.pop("launched_drones", None)
            for value in data.values():
                legacy_research_payload(value)
    elif isinstance(data, list):
        for value in data:
            legacy_research_payload(value)
    return data
