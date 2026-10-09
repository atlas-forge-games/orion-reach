"""Varkesh raids, captive labor and deterministic individual mortality rolls."""

from dataclasses import dataclass
import random

from . import exploration, ground_combat, population, victory

SLAVE_CAPACITY = 100
MORTALITY_CHANCE = 20  # Each slave has one chance in twenty per completed turn.
CREDITS_PER_POPULATION = 10
MAX_RAID_NEWS = 100


@dataclass(frozen=True)
class RaidEvent:
    id: int
    turn: int
    system_id: int
    planet_id: int
    attacker: str
    defender: str
    successful: bool
    slaves_taken: int
    credits_stolen: int
    colony_razed: bool
    observers: list[str]


def is_varkesh(game, owner="player"):
    return owner in game.owners and game._empire(owner).race_id == "varkesh"


def home_location(game, owner="player"):
    empire = game._empire(owner)
    return (0, 2) if owner == "player" else (empire.home_system, empire.home_planet)


def homeworld(game, owner="player"):
    planet = game.planet_at(*home_location(game, owner))
    return planet if planet.owner == owner else None


def capacity_left(game, owner="player"):
    planet = homeworld(game, owner)
    return max(0, min(SLAVE_CAPACITY-planet.slaves, 200-planet.workforce)) if planet else 0


def expected_loot(game, planet, owner="player"):
    return min(planet.workforce, capacity_left(game, owner)), planet.workforce*CREDITS_PER_POPULATION


def abandon(planet):
    planet.owner, planet.colonized = None, False
    planet.population = planet.slaves = planet.garrison = planet.militia_losses = 0
    planet.farmers = planet.scientists = planet.growth_progress = 0
    planet.ascension_gate, planet.gate_charge = False, 0
    planet.buildings.clear()
    planet.construction_queue.clear()


def raid(game, system_id, planet_id, owner="player"):
    from .model import RuleError
    if not is_varkesh(game, owner):
        raise RuleError("Only the Varkesh can launch slave raids.")
    error = victory.invasion_error(game, system_id, planet_id, owner)
    if error:
        raise RuleError(error)
    planet, home = game.planet_at(system_id, planet_id), homeworld(game, owner)
    defender = planet.owner
    observers = [empire for empire in game.owners
                 if empire in (owner, defender) or game.system_visible(system_id, empire)]
    transports = victory.troop_transports(game, system_id, owner)
    attack = len(transports)*victory.TROOP_STRENGTH
    defending = ground_combat.forces(planet)
    outcome = ground_combat.resolve(attack, defending)
    for ship in transports:
        game.ships.remove(ship)
    victory.apply_ground_casualties(planet, defending, outcome.defenders)
    captives = credits = 0
    razed = False
    if outcome.captured:
        captives, maximum = expected_loot(game, planet, owner)
        credits = min(maximum, max(0, game.treasury_for(defender)), max(0, 1_000_000_000-game.treasury_for(owner)))
        game._empire(defender).credits -= credits
        game._empire(owner).credits += credits
        # Existing captives transfer first. Everyone uses the same population unit.
        transferred = min(captives, planet.slaves)
        planet.slaves -= transferred
        planet.population -= captives-transferred
        home.slaves += captives
        home.garrison = min(ground_combat.MAX_GARRISON, home.garrison+outcome.attackers)
        # The expedition brings its captives home immediately; no occupation colony.
        population.clamp_workforce(planet)
        home.farmers = population.farmers_needed(home, game.bonuses_for(owner), surplus=1)
        population.clamp_workforce(home)
        if not planet.workforce:
            abandon(planet)
            razed = True
        else:
            planet.militia_losses = 4+planet.population
        message = f"{game.empire_name_for(owner)} raided {planet.name}: {captives} slaves taken, {credits} CR stolen."
    else:
        message = f"{game.empire_name_for(owner)} raid on {planet.name} was repelled."
    victory.record_ground_hostility(game, owner, defender, message)
    game.raid_events.append(RaidEvent(game.next_raid_id, game.turn, system_id, planet_id, owner, defender,
                                      outcome.captured, captives, credits, razed, observers))
    game.next_raid_id += 1
    game.raid_events[:] = game.raid_events[-MAX_RAID_NEWS:]
    exploration.record_survey(game, home_location(game, owner)[0], owner)
    for participant in (owner, defender):
        exploration.record_survey(game, system_id, participant)
    game.eliminate_defeated()
    game.check_victory()
    return victory.InvasionReport(owner, system_id, planet_id, attack, defending.strength,
                                   len(transports), outcome.captured, defender, defending.militia,
                                   defending.garrison, defending.defence_bonus, outcome.attackers,
                                   outcome.defenders, outcome.rounds, "raid", captives, credits, razed)


def deaths(game, system_id, planet_id, owner, count, *, turn=None):
    turn = game.turn if turn is None else turn
    rng = random.Random(f"orion-varkesh-mortality-v1:{game.seed}:{turn}:{system_id}:{planet_id}:{owner}")
    return sum(rng.randrange(MORTALITY_CHANCE) == 0 for _ in range(count))


def advance_mortality(game, starting):
    messages = []
    for (sid, pid), (owner, count) in starting.items():
        planet = game.planet_at(sid, pid)
        if planet.owner != owner or not is_varkesh(game, owner):
            continue
        lost = deaths(game, sid, pid, owner, min(count, planet.slaves))
        if not lost:
            continue
        planet.slaves -= lost
        population.clamp_workforce(planet)
        message = f"{planet.name}: {lost} slave {'unit died' if lost == 1 else 'units died'}; {planet.slaves}/{SLAVE_CAPACITY} remain"
        if owner == "player":
            messages.append(message)
        else:
            game.rival_event(message+".", turn=game.turn, owner=owner)
    return messages


def news(game, owner="player"):
    return [event for event in reversed(game.raid_events) if owner in event.observers]


def headline(game, event):
    planet = game.planet_at(event.system_id, event.planet_id)
    verb = "successfully raided" if event.successful else "failed to raid"
    return f"{game.empire_name_for(event.attacker)} {verb} {planet.name}."


def outcome_text(game, event):
    if not event.successful:
        return "The defenders held their colony. No population or credits were taken."
    status = "The emptied colony was abandoned." if event.colony_razed else "The colony remains with its original empire."
    return f"{event.slaves_taken} slave units taken to the raiders' homeworld; {event.credits_stolen} CR stolen. {status}"


def load_state(game, data):
    from .model import _integer
    for system in game.systems:
        for planet in system.worlds:
            if planet.slaves and (not is_varkesh(game, planet.owner)
                                  or (system.id, planet.id) != home_location(game, planet.owner)):
                raise ValueError("Slaves can only live on a Varkesh homeworld")
    rows = data["raid_events"]
    if not isinstance(rows, list) or len(rows) > MAX_RAID_NEWS:
        raise ValueError("Invalid raid news")
    fields = set(RaidEvent.__dataclass_fields__)
    previous_id, previous_turn = 0, 1
    events = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != fields:
            raise ValueError("Invalid raid event")
        if (not _integer(row["id"], previous_id+1, 1_000_000)
                or not _integer(row["turn"], previous_turn, game.turn)
                or not _integer(row["system_id"], 0, len(game.systems)-1)
                or not _integer(row["planet_id"], 0, len(game.systems[row["system_id"]].worlds)-1)
                or not is_varkesh(game, row["attacker"]) or row["defender"] not in game.owners
                or row["attacker"] == row["defender"]
                or type(row["successful"]) is not bool or type(row["colony_razed"]) is not bool
                or not _integer(row["slaves_taken"], 0, SLAVE_CAPACITY)
                or not _integer(row["credits_stolen"], 0, 200*CREDITS_PER_POPULATION)):
            raise ValueError("Invalid raid outcome")
        if not row["successful"] and (row["slaves_taken"] or row["credits_stolen"] or row["colony_razed"]):
            raise ValueError("Repelled raid has loot")
        observers = row["observers"]
        if (not isinstance(observers, list) or len(observers) > len(game.owners)
                or any(owner not in game.owners for owner in observers) or len(set(observers)) != len(observers)
                or row["attacker"] not in observers or row["defender"] not in observers):
            raise ValueError("Invalid raid observers")
        events.append(RaidEvent(**{**row, "observers": observers.copy()}))
        previous_id, previous_turn = row["id"], row["turn"]
    if (not _integer(data["next_raid_id"], previous_id+1, previous_id+1)
            or not _integer(data["raid_news_read"], 0, previous_id)):
        raise ValueError("Invalid raid news cursor")
    game.raid_events, game.next_raid_id, game.raid_news_read = events, data["next_raid_id"], data["raid_news_read"]
