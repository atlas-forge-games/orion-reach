"""Debt costs and compulsory bankruptcy, independent of optional victory goals."""

INTEREST_PERCENT = 10
BANKRUPTCY_LIMIT = -10_000


def interest(credits):
    """Whole credits, rounded up: even a one-credit debt has a carrying cost."""
    return (max(0, -credits)*INTEREST_PERCENT+99)//100


def bankrupt(game, owner="player"):
    return owner in game.owners and game.treasury_for(owner) <= BANKRUPTCY_LIMIT


def eliminate_bankrupt_opponents(game):
    """Abandon a bankrupt AI's assets once; keep its identity and final treasury."""
    from . import first_contact, raiding, specialists, species, motherships
    messages = []
    changed = False
    for owner in game.opponents:
        if not bankrupt(game, owner):
            continue
        worlds = [p for s in game.systems for p in s.worlds if p.owner == owner]
        ships = game.ships_owned_by(owner)
        if not worlds and not ships:
            continue
        for planet in worlds:
            raiding.abandon(planet)
        game.ships[:] = [ship for ship in game.ships if ship.owner != owner]
        message = f"{game.empire_name_for(owner)} is bankrupt at {game.treasury_for(owner):,} CR; its empire has collapsed."
        game.rival_event(message, turn=game.turn, owner=owner)
        if game.is_observer or not game.fog_of_war or first_contact.known(game, "player", owner):
            messages.append(message)
        changed = True
    if changed:
        game.eliminate_defeated()
        species.normalize(game)
        motherships.relocate_specialists(game)
        specialists.normalize(game)
        # A watched mobile home may have disappeared with its bankrupt empire.
        if game.selected_planet is not None and game.selected_planet < 0:
            if not any(s.habitat and s.habitat.id == game.selected_planet for s in game.ships):
                game.selected_planet = None
    return messages
