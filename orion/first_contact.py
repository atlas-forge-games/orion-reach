"""Confirmed bilateral contact, independent of map omniscience or UI state."""

from .personalities import PERSONALITIES


def known(game, first, second):
    return (first != second and first in game.owners and second in game.owners
            and (not game.fog_of_war or game.diplomacy_between(first, second).contact_turn > 0))


def known_opponents(game):
    if game.is_observer:
        return list(game.opponents)
    return [owner for owner in game.opponents if known(game, "player", owner)]


def pending(game):
    if game.is_observer:
        return []
    return sorted((owner for owner in known_opponents(game)
                   if not game.diplomacy_between("player", owner).introduced and game.colony_systems(owner)),
                  key=lambda owner: (game.diplomacy_between("player", owner).contact_turn, owner))


def establish(game, first, second, *, notify=True):
    if first == second or first not in game.owners or second not in game.owners:
        return
    state = game.diplomacy_between(first, second)
    if state.contact_turn:
        return
    state.contact_turn = game.turn if notify or not state.events else state.events[0].turn
    state.introduced = not notify or "player" not in (first, second)
    other = second if first == "player" else first
    if notify and "player" in (first, second):
        race = game._empire(other).race_id
        state.record(game.turn, f"First contact: {game.empire_name_for(other)}.")
        state.record(game.turn, PERSONALITIES[race].greeting)


def refresh(game, *, historic=False, notify=True):
    """Either side identifying a ship or colony establishes a shared channel.

    Sensors establish identity without granting planet surveys or revealing homes.
    Historical sightings are used only when migrating campaigns without contacts.
    """
    from .exploration import observed_systems
    sightings = set()
    for observer in game.owners:
        if not game.fog_of_war:
            sightings.update((observer, other) for other in game.owners if other != observer)
            continue
        visible = observed_systems(game, observer)
        for sid in visible:
            sightings.update((observer, p.owner) for p in game.systems[sid].worlds if p.owner is not None)
        sightings.update((observer, s.owner) for s in game.ships if not s.in_transit and s.system_id in visible)
        sightings.update((observer, c.owner) for c in game.sensor_contacts
                         if c.observer == observer and (c.active or historic))
        if historic:
            for survey in game.exploration.surveys:
                if survey.owner == observer:
                    sightings.update((observer, p["owner"]) for p in survey.worlds if p["owner"] is not None)
            for other in game.owners:
                if observer != other:
                    state = game.diplomacy_between(observer, other)
                    if state.trade_active or state.research_active or state.relations != 0:
                        sightings.add((observer, other))
    for first, second in sorted(sightings):
        establish(game, first, second, notify=notify)
    for tomb in game.tomb_worlds:
        if tomb.awakened_turn and tomb.remnant_owner:
            for observer in tomb.notified_owners:
                establish(game, observer, tomb.remnant_owner, notify=notify)


def acknowledge(game, owner):
    if known(game, "player", owner):
        game.diplomacy_between("player", owner).introduced = True


def migrate(game):
    # Existing confirmed contacts remain available without replaying introductions.
    refresh(game, historic=True, notify=False)
