"""Colony invasions, the science endgame and immutable campaign outcomes."""

from dataclasses import dataclass

from .production import ASCENSION_GATE, MAX_QUEUE
from . import production as production_balance
from .ground_combat import GroundRound, forces, resolve
from .population import liberate

CONDITIONS = ("conquest", "science", "council")
CONDITION_NAMES = {"conquest": "Conquest", "science": "Science", "council": "Galactic Council"}


def parse_conditions(values):
    """Keep setup and save options explicit, unique and in a stable order."""
    if (not isinstance(values, (list, tuple))
            or any(not isinstance(value, str) or value not in CONDITIONS for value in values)
            or len(set(values)) != len(values)):
        raise ValueError("Choose valid victory conditions.")
    return tuple(condition for condition in CONDITIONS if condition in values)


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
    slaves_taken: int = 0
    credits_stolen: int = 0
    colony_razed: bool = False


def colonies(game, owner):
    return [(s, p) for s in game.systems for p in s.worlds if p.owner == owner]


def troop_transports(game, system_id, owner="player"):
    return [s for s in game.fleet_at(system_id, owner) if s.kind == "troop_transport"]


def transport_losses(count, survivors):
    """Return lost hulls and leftover troops after full squads re-embark.

    Casualties are concentrated into transport loads, rounding hull losses up.
    Full surviving squads stay aboard; the remainder becomes a local garrison.
    """
    remaining, ground_troops = divmod(survivors, production_balance.TROOP_STRENGTH)
    return max(0, count-remaining), ground_troops


def invasion_strength(game, system_id, planet_id, owner="player"):
    return (len(troop_transports(game, system_id, owner))*production_balance.TROOP_STRENGTH,
            forces(game.planet_at(system_id, planet_id), game.bonuses_for(game.planet_at(system_id, planet_id).owner)).strength)


def invasion_error(game, system_id, planet_id, owner="player"):
    from .defenses import bases, effective_shield
    from .raiding import is_varkesh, homeworld
    if game.strategy_error(owner):
        return game.strategy_error(owner)
    if owner not in game.owners or not game.opponents:
        return "No opposing empire is available."
    planet = game.planet_at(system_id, planet_id)
    if planet.owner is None or planet.owner == owner:
        return "Choose a colony belonging to the opposing empire."
    from .diplomacy import aggression_error
    if aggression_error(game, owner, planet.owner):
        return aggression_error(game, owner, planet.owner)
    if game.foreign_fleet(system_id, owner):
        return "Clear all opposing ships from this system before invading."
    if any(p.owner != owner for p in bases(game, system_id)):
        return "Destroy the opposing missile bases before landing troops."
    if effective_shield(game, planet):
        return f"Suppress the planetary shield by bombardment first ({planet.shield_points} points remain)."
    if not troop_transports(game, system_id, owner):
        return "Bring troop transports into orbit first."
    if is_varkesh(game, owner) and homeworld(game, owner) is None:
        return "Raids require your original homeworld to receive captives and returning troops."
    return None


def invade(game, system_id, planet_id, owner="player"):
    from . import administration
    from .model import RuleError
    from .raiding import is_varkesh, raid
    if is_varkesh(game, owner):
        return raid(game, system_id, planet_id, owner)
    error = invasion_error(game, system_id, planet_id, owner)
    if error:
        raise RuleError(error)
    planet = game.planet_at(system_id, planet_id)
    defender = planet.owner
    transports = troop_transports(game, system_id, owner)
    attack, defence = invasion_strength(game, system_id, planet_id, owner)
    defending = forces(planet, game.bonuses_for(planet.owner))
    outcome = resolve(attack, defending)
    captured = outcome.captured
    lost, ground_troops = transport_losses(len(transports), outcome.attackers)
    for ship in transports[:lost]:
        game.ships.remove(ship)
    previous_systems = administration.snapshot(game)
    apply_ground_outcome(planet, owner, defending, outcome)
    if captured:
        planet.garrison = ground_troops
    administration.ownership_changed(game, previous_systems)
    action = ("assimilated" if game._empire(owner).race_id == "concord" else "captured") if captured else "failed to capture"
    record_ground_hostility(game, owner, defender,
                           f"{game.empire_name_for(owner)} {action} {planet.name}: "
                           f"{attack-outcome.attackers} attacking and {defending.troops-outcome.defenders} defending troops lost. "
                           f"{lost} transports lost; {len(transports)-lost} returned to orbit.")
    game.eliminate_defeated()
    game.check_victory()
    return InvasionReport(owner, system_id, planet_id, attack, defence, len(transports), captured,
                          defender, defending.militia, defending.garrison, defending.defence_bonus,
                          outcome.attackers, outcome.defenders, outcome.rounds)


def apply_ground_outcome(planet, owner, defending, outcome):
    """Transport invasions and buried armies have identical occupation rules."""
    if outcome.captured:
        liberate(planet)
        planet.owner = owner
        planet.shield_points = 0
        planet.garrison = outcome.attackers
        planet.militia_losses = 4+planet.population
        # Populations, buildings and normal paid projects survive occupation.
        # The gate is bound to its original empire and cannot be inherited.
        planet.ascension_gate, planet.gate_charge = False, 0
        planet.construction_queue[:] = [p for p in planet.construction_queue if p.item_id != ASCENSION_GATE.id]
    else:
        # Trained troops fight at the front. Civilian population is unchanged;
        # militia losses recover one troop per turn, trained losses need barracks.
        apply_ground_casualties(planet, defending, outcome.defenders)


def apply_ground_casualties(planet, defending, survivors):
    casualties = defending.troops-survivors
    planet.militia_losses += max(0, casualties-planet.garrison)
    planet.garrison = max(0, planet.garrison-casualties)


def record_ground_hostility(game, owner, defender, message):
    from .first_contact import establish
    establish(game, owner, defender)
    state = game.diplomacy_between(owner, defender)
    from .diplomacy import start_war
    start_war(game, owner, defender)
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
    if game.strategy_error(owner):
        return game.strategy_error(owner)
    if "science" not in game.victory_conditions:
        return "Science victory is disabled for this campaign."
    planet = game.planet_at(system_id, planet_id)
    if planet.owner != owner:
        return "Choose one of your colonies."
    if "ascension_theory" not in game.research_state(owner).completed:
        return "Discover Ascension Theory first."
    if gate_site(game, owner):
        return "Your empire already has an Ascension Gate built or queued."
    if len(planet.construction_queue) >= MAX_QUEUE:
        return "The construction queue is full."
    return None


def advance_gates(game, eligible):
    """Charge only gates that existed at turn start; arrivals can blockade them."""
    if "science" not in game.victory_conditions:
        return
    for system_id, planet_id, owner in eligible:
        planet = game.planet_at(system_id, planet_id)
        if (planet.owner == owner and planet.ascension_gate
                and not gate_blocked(game, system_id, owner) and game.planet_energy(planet).gate_powered):
            planet.gate_charge = min(production_balance.GATE_CHARGE_TURNS, planet.gate_charge+1)


def current_result(game):
    if game.opponents:
        alive = [owner for owner in game.owners if colonies(game, owner)]
        if "conquest" in game.victory_conditions and len(alive) < 2:
            return CampaignResult(alive[0] if alive else None, "conquest", game.turn)
        if not game.is_observer and "player" not in alive:
            return CampaignResult(None, "elimination", game.turn)
    ascended = {p.owner for s in game.systems for p in s.worlds
                if p.ascension_gate and p.gate_charge == production_balance.GATE_CHARGE_TURNS}
    if "science" in game.victory_conditions and ascended:
        # Production is simultaneous: two gates finishing together is a draw.
        return CampaignResult(next(iter(ascended)) if len(ascended) == 1 else None, "science", game.turn)
    election = game.council.election
    if "council" in game.victory_conditions and election is not None and election.status == "accepted":
        return CampaignResult(election.winner, "council", game.turn)
    return None


def validate(game, data):
    """Validate terminal outcomes and projects against actual campaign state."""
    from .model import _integer
    for owner in game.owners:
        research = game.research_state(owner)
        if "science" not in game.victory_conditions and (research.active == "ascension_theory" or "ascension_theory" in research.completed):
            raise ValueError("Disabled science victory cannot have Ascension research")
        sites = []
        for system, planet in colonies(game, owner):
            queued = [p for p in planet.construction_queue if p.item_id == ASCENSION_GATE.id]
            if len(queued) > 1 or (queued and planet.ascension_gate):
                raise ValueError("Duplicate Ascension Gate")
            if queued or planet.ascension_gate:
                sites.append((system, planet))
        if (len(sites) > 1 or (sites and ("science" not in game.victory_conditions
                                       or "ascension_theory" not in game.research_state(owner).completed))):
            raise ValueError("Gate does not match research or empire limit")
    expected = current_result(game)
    if data is None:
        if expected is not None:
            raise ValueError("Missing campaign result")
        return None
    if (not isinstance(data, dict) or set(data) != {"winner", "condition", "turn"}
            or data["winner"] not in (*game.owners, None)
            or data["condition"] not in ("conquest", "science", "elimination", "council")
            or not _integer(data["turn"], game.turn, game.turn)):
        raise ValueError("Invalid campaign result")
    result = CampaignResult(**data)
    if result != expected or game.combat is not None:
        raise ValueError("Campaign result does not match the world")
    return result
