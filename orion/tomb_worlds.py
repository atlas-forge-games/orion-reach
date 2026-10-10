"""Hidden Remnant vaults, once-only awakenings and per-empire turn news."""

from dataclasses import dataclass, field
import random

from .empires import CAMPAIGN_RIVAL_IDS, PLAYER
from . import exploration, ground_combat, population, victory
from .races import RACES

TOMB_CHANCE = 10  # One in ten worlds, rolled only when creating a campaign.
AWAKENING_CHANCE = 200  # One in two hundred per dormant world per completed turn.
AWAKENED_TROOPS = 16
AWAKENED_POPULATION = 2


@dataclass
class TombWorld:
    system_id: int
    planet_id: int
    awakened_turn: int | None = None
    outcome: str | None = None
    remnant_owner: str | None = None
    defender: str | None = None
    notified_owners: list[str] = field(default_factory=list)


def seed_worlds(game):
    # Independent, per-world streams leave galaxy layouts and race picks intact.
    game.tomb_worlds = [TombWorld(s.id, p.id) for s in game.systems for p in s.worlds
                        if random.Random(f"orion-tombs-v1:{game.seed}:{s.id}:{p.id}").randrange(TOMB_CHANCE) == 0]


def awakening_due(game, tomb):
    # Reloading before End Turn cannot reroll an awakening.
    return random.Random(f"orion-awakening-v1:{game.seed}:{game.turn}:{tomb.system_id}:{tomb.planet_id}").randrange(AWAKENING_CHANCE) == 0


def remnant_empire(game):
    if game.race_id == "remnant":
        return PLAYER
    return next((owner for owner, empire in game.opponents.items() if empire.race_id == "remnant"), None)


def establish_empire(game, tomb):
    owner = remnant_empire(game)
    if owner is None:
        owner = next(owner for owner in CAMPAIGN_RIVAL_IDS if owner not in game.owners)
        game._register_opponent(owner, "remnant", game.systems[tomb.system_id],
                                game.planet_at(tomb.system_id, tomb.planet_id), RACES["remnant"].default_empire)
    return owner


def headline(game, tomb):
    name = game.planet_at(tomb.system_id, tomb.planet_id).name
    return f"Tomb world {name} has awakened as a tomb world of the Remnant."


def outcome_text(game, tomb):
    name = game.empire_name_for(tomb.remnant_owner) if tomb.remnant_owner else "The Remnant"
    if tomb.outcome == "founded":
        return f"A new colony has joined {name}. Its buried army now guards the surface."
    if tomb.outcome == "reinforced":
        return f"The colony already belongs to {name}. Its awakened troops reinforce the garrison."
    defender = game.empire_name_for(tomb.defender)
    if tomb.outcome == "captured":
        return f"Awakened Remnant troops defeated {defender} in ground combat and captured the colony."
    return f"The colony's defenders repelled the awakened Remnant. {defender} retained control."


def news(game, owner=PLAYER):
    return sorted((t for t in game.tomb_worlds if t.awakened_turn is not None and owner in t.notified_owners),
                  key=lambda t: (t.awakened_turn, t.system_id, t.planet_id), reverse=True)


def unread_count(game):
    return sum(t.awakened_turn > game.news_read_turn for t in news(game))


def awaken(game, tomb):
    """Resolve one vault. The turn coordinator checks victory after all vaults."""
    if tomb.awakened_turn is not None:
        return None
    planet = game.planet_at(tomb.system_id, tomb.planet_id)
    aware = [owner for owner in game.owners if game.system_explored(tomb.system_id, owner)]
    owner, defender = remnant_empire(game), planet.owner
    report = None
    if defender is None:
        owner = establish_empire(game, tomb)
        planet.colonized, planet.owner, planet.population = True, owner, AWAKENED_POPULATION
        # The buried habitat supports life even on Barren and Volcanic worlds.
        planet.buildings = ["hydroponic_farm"]
        planet.garrison = AWAKENED_TROOPS
        planet.farmers = population.farmers_needed(planet, game.bonuses_for(owner), surplus=1)
        tomb.outcome = "founded"
    elif defender == owner:
        planet.garrison = min(ground_combat.MAX_GARRISON, planet.garrison+AWAKENED_TROOPS)
        tomb.outcome = "reinforced"
    else:
        defending = ground_combat.forces(planet, game.bonuses_for(planet.owner))
        outcome = ground_combat.resolve(AWAKENED_TROOPS, defending)
        if outcome.captured:
            owner = establish_empire(game, tomb)
        victory.apply_ground_outcome(planet, owner, defending, outcome)
        tomb.outcome = "captured" if outcome.captured else "repelled"
        message = f"Awakened Remnant troops {'captured' if outcome.captured else 'were repelled on'} {planet.name}."
        if owner is not None:
            victory.record_ground_hostility(game, owner, defender, message)
        report = victory.InvasionReport(owner, tomb.system_id, tomb.planet_id, AWAKENED_TROOPS,
                                         defending.strength, 0, outcome.captured, defender,
                                         defending.militia, defending.garrison, defending.defence_bonus,
                                         outcome.attackers, outcome.defenders, outcome.rounds, "tomb")
        # Both combatants know the outcome even if they lost their only observer.
        exploration.record_survey(game, tomb.system_id, defender)
    tomb.awakened_turn, tomb.remnant_owner, tomb.defender = game.turn, owner, defender
    if owner is not None and planet.owner == owner:
        if owner not in aware:
            aware.append(owner)
        exploration.record_survey(game, tomb.system_id, owner)
        if owner != PLAYER:
            game.rival_event(f"Remnant vaults awakened on {planet.name}: {tomb.outcome}.", turn=game.turn, owner=owner)
    tomb.notified_owners = aware
    # A remote news dispatch does not refresh a stale survey or reveal other worlds.
    return report


def advance(game, alerts, ground_reports):
    changed = False
    for tomb in game.tomb_worlds:
        if tomb.awakened_turn is not None or not awakening_due(game, tomb):
            continue
        report = awaken(game, tomb)
        changed = True
        if PLAYER in tomb.notified_owners:
            alerts.append(headline(game, tomb))
        if report and PLAYER in (report.attacker, report.defender):
            ground_reports.append(report)
    if changed:
        game.eliminate_defeated()


def parse(data, game):
    from .model import _integer
    if not isinstance(data, list) or len(data) > sum(s.planets for s in game.systems):
        raise ValueError("Invalid tomb worlds")
    fields = {"system_id", "planet_id", "awakened_turn", "outcome", "remnant_owner", "defender", "notified_owners"}
    tombs, seen = [], set()
    for row in data:
        if not isinstance(row, dict) or set(row) != fields:
            raise ValueError("Invalid tomb world record")
        sid, pid = row["system_id"], row["planet_id"]
        if (not _integer(sid, 0, len(game.systems)-1)
                or not _integer(pid, 0, len(game.systems[sid].worlds)-1) or (sid, pid) in seen):
            raise ValueError("Invalid tomb world location")
        turn, owner, defender = row["awakened_turn"], row["remnant_owner"], row["defender"]
        observers = row["notified_owners"]
        if (not isinstance(observers, list) or len(observers) > len(game.owners)
                or any(o not in game.owners for o in observers) or len(set(observers)) != len(observers)):
            raise ValueError("Invalid tomb world observers")
        if turn is None:
            if any(row[key] is not None for key in ("outcome", "remnant_owner", "defender")) or observers:
                raise ValueError("Dormant tomb has an awakening outcome")
        else:
            if not _integer(turn, 1, game.turn) or row["outcome"] not in ("founded", "captured", "repelled", "reinforced"):
                raise ValueError("Invalid awakening outcome")
            if owner is not None and (owner not in game.owners or game._empire(owner).race_id != "remnant"):
                raise ValueError("Awakening belongs to a non-Remnant empire")
            if row["outcome"] != "repelled" and owner is None:
                raise ValueError("Successful awakening needs an empire")
            if row["outcome"] == "founded":
                if defender is not None:
                    raise ValueError("New tomb colony was already occupied")
            elif defender not in game.owners:
                raise ValueError("Missing tomb world defender")
            elif (defender == owner) != (row["outcome"] == "reinforced"):
                raise ValueError("Invalid tomb world combatants")
        seen.add((sid, pid))
        tombs.append(TombWorld(**{**row, "notified_owners": observers.copy()}))
    return tombs
