"""Colony invasions, the science endgame and immutable campaign outcomes."""

from dataclasses import dataclass

from .production import ASCENSION_GATE, GATE_CHARGE_TURNS, MAX_QUEUE, TROOP_STRENGTH
from .ground_combat import GroundRound, forces, resolve

@dataclass(frozen=True)
class CampaignResult:
    winner: str | None
    condition: str
    turn: int


@dataclass(frozen=True)
class InvasionReport:
    attacker: str | None
    system_id: int
    planet_id: int
    attack: int
    defence: int
    transports: int
    captured: bool
    defender: str
    militia: int
    garrison: int
    defence_bonus: int
    attacker_survivors: int
    defender_survivors: int
    rounds: tuple[GroundRound, ...]
    cause: str = "invasion"


def colonies(game, owner):
    return [(s, p) for s in game.systems for p in s.worlds if p.owner == owner]


def troop_transports(game, system_id, owner="player"):
    return [s for s in game.fleet_at(system_id, owner) if s.kind == "troop_transport"]


def invasion_strength(game, system_id, planet_id, owner="player"):
    return (len(troop_transports(game, system_id, owner))*TROOP_STRENGTH,
            forces(game.planet_at(system_id, planet_id)).strength)


def invasion_error(game, system_id, planet_id, owner="player"):
    if game.strategy_error():
        return game.strategy_error()
    if owner not in game.owners or not game.opponents:
        return "No opposing empire is available."
    planet = game.planet_at(system_id, planet_id)
    if planet.owner is None or planet.owner == owner:
        return "Choose a colony belonging to the opposing empire."
    if game.foreign_fleet(system_id, owner):
        return "Clear all opposing ships from this system before invading."
    if not troop_transports(game, system_id, owner):
        return "Bring troop transports into orbit first."
    return None


def invade(game, system_id, planet_id, owner="player"):
    from .model import RuleError
    error = invasion_error(game, system_id, planet_id, owner)
    if error:
        raise RuleError(error)
    planet = game.planet_at(system_id, planet_id)
    defender = planet.owner
    transports = troop_transports(game, system_id, owner)
    attack, defence = invasion_strength(game, system_id, planet_id, owner)
    defending = forces(planet)
    outcome = resolve(attack, defending)
    captured = outcome.captured
    for ship in transports:
        game.ships.remove(ship)
    apply_ground_outcome(planet, owner, defending, outcome)
    record_ground_hostility(game, owner, defender,
                           f"{game.empire_name_for(owner)} {'captured' if captured else 'failed to capture'} {planet.name}: "
                           f"{attack-outcome.attackers} attacking and {defending.troops-outcome.defenders} defending troops lost. "
                           f"{len(transports)} transports consumed.")
    game.eliminate_defeated()
    game.check_victory()
    return InvasionReport(owner, system_id, planet_id, attack, defence, len(transports), captured,
                          defender, defending.militia, defending.garrison, defending.defence_bonus,
                          outcome.attackers, outcome.defenders, outcome.rounds)


def apply_ground_outcome(planet, owner, defending, outcome):
    """Transport invasions and buried armies have identical occupation rules."""
    if outcome.captured:
        planet.owner = owner
        planet.garrison = outcome.attackers
        planet.militia_losses = 4+planet.population
        # Populations, buildings and normal paid projects survive occupation.
        # The gate is bound to its original empire and cannot be inherited.
        planet.ascension_gate, planet.gate_charge = False, 0
        planet.construction_queue[:] = [p for p in planet.construction_queue if p.item_id != ASCENSION_GATE.id]
    else:
        # Trained troops fight at the front. Civilian population is unchanged;
        # militia losses recover one troop per turn, trained losses need barracks.
        casualties = defending.troops-outcome.defenders
        planet.militia_losses += max(0, casualties-planet.garrison)
        planet.garrison = max(0, planet.garrison-casualties)


def record_ground_hostility(game, owner, defender, message):
    state = game.diplomacy_between(owner, defender)
    state.trade_active = state.research_active = False
    state.relations, state.offer_ready_turn = -100, game.turn+3
    state.record(game.turn, message)
    for participant in (owner, defender):
        if participant != "player":
            game.rival_event(message, turn=game.turn, owner=participant)


def gate_site(game, owner="player"):
    return next(((s, p) for s, p in colonies(game, owner)
                 if p.ascension_gate or any(q.item_id == ASCENSION_GATE.id for q in p.construction_queue)), None)


def gate_blocked(game, system_id, owner):
    return bool(game.foreign_fleet(system_id, owner))


def gate_error(game, system_id, planet_id, owner="player"):
    if game.strategy_error():
        return game.strategy_error()
    planet = game.planet_at(system_id, planet_id)
    if planet.owner != owner:
        return "Choose one of your colonies."
    if "ascension_theory" not in game.research_state(owner).completed:
        return "Discover Ascension Theory first."
    if gate_site(game, owner):
        return "Your empire already has an Ascension Gate built or queued."
    if len(planet.construction_queue) >= MAX_QUEUE:
        return "The construction queue is full."
    if game.treasury_for(owner) < ASCENSION_GATE.credit_cost:
        return f"Requires {ASCENSION_GATE.credit_cost} credits."
    return None


def advance_gates(game, eligible):
    """Charge only gates that existed at turn start; arrivals can blockade them."""
    for system_id, planet_id, owner in eligible:
        planet = game.planet_at(system_id, planet_id)
        if (planet.owner == owner and planet.ascension_gate
                and not gate_blocked(game, system_id, owner)):
            planet.gate_charge = min(GATE_CHARGE_TURNS, planet.gate_charge+1)


def current_result(game):
    if game.opponents:
        alive = [owner for owner in game.owners if colonies(game, owner)]
        if len(alive) < 2:
            return CampaignResult(alive[0] if alive else None, "conquest", game.turn)
        if "player" not in alive:
            return CampaignResult(None, "elimination", game.turn)
    ascended = {p.owner for s in game.systems for p in s.worlds
                if p.ascension_gate and p.gate_charge == GATE_CHARGE_TURNS}
    if ascended:
        # Production is simultaneous: two gates finishing together is a draw.
        return CampaignResult(next(iter(ascended)) if len(ascended) == 1 else None, "science", game.turn)
    return None


def validate(game, data):
    """Validate terminal outcomes and projects against actual campaign state."""
    from .model import _integer
    for owner in game.owners:
        sites = []
        for system, planet in colonies(game, owner):
            queued = [p for p in planet.construction_queue if p.item_id == ASCENSION_GATE.id]
            if len(queued) > 1 or (queued and planet.ascension_gate):
                raise ValueError("Duplicate Ascension Gate")
            if queued or planet.ascension_gate:
                sites.append((system, planet))
        if len(sites) > 1 or (sites and "ascension_theory" not in game.research_state(owner).completed):
            raise ValueError("Gate does not match research or empire limit")
    expected = current_result(game)
    if data is None:
        if expected is not None:
            raise ValueError("Missing campaign result")
        return None
    if (not isinstance(data, dict) or set(data) != {"winner", "condition", "turn"}
            or data["winner"] not in (*game.owners, None)
            or data["condition"] not in ("conquest", "science", "elimination")
            or not _integer(data["turn"], game.turn, game.turn)):
        raise ValueError("Invalid campaign result")
    result = CampaignResult(**data)
    if result != expected or game.combat is not None:
        raise ValueError("Campaign result does not match the world")
    return result
