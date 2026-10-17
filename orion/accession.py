"""Visible, gradual Union outreach and defensive civic investment."""

from dataclasses import dataclass

from . import administration, coalitions, exploration, first_contact, species

START_COST, UPKEEP, CIVIC_COST, CIVIC_TURNS = 30, 5, 40, 8
MAX_MISSIONS = 2


def upkeep(game, owner="player"):
    return UPKEEP*sum(m.owner == owner for m in game.union_missions)


@dataclass
class Mission:
    owner: str
    target: str
    system_id: int
    planet_id: int
    started: int
    progress: int = 0


def mission_at(game, sid, pid):
    return next((m for m in game.union_missions if (m.system_id, m.planet_id) == (sid, pid)), None)


def protected(game, planet):
    home = game.headquarters(planet.owner)
    return planet.habitat or (home is not None and home[1] is planet)


def eligibility(game, owner, sid, pid):
    if owner not in game.owners or game._empire(owner).race_id != "serevan":
        return "Only the Serevan Union can sponsor accession."
    if not game.system_visible(sid, owner):
        return "Maintain a ship or shared scanners here to conduct outreach."
    planet = game.planet_at(sid, pid)
    if not planet.colonized or planet.owner == owner:
        return "Choose an inhabited foreign colony."
    if not first_contact.known(game, owner, planet.owner):
        return "Establish diplomatic contact first."
    if protected(game, planet):
        return "Capitals and mobile homeworlds cannot join through outreach."
    if game._empire(planet.owner).race_id in ("concord", "skirr", "nexus"):
        return "This collective does not permit an independent colony vote."
    state = game.diplomacy_between(owner, planet.owner)
    if state.at_war or state.relations < 0:
        return "Outreach requires peace and non-negative relations."
    if not game.within_fuel_range(sid, owner):
        return "This colony is outside your logistical range."
    return None


def support(game, mission):
    if error := eligibility(game, mission.owner, mission.system_id, mission.planet_id):
        return -8, error
    planet = game.planet_at(mission.system_id, mission.planet_id)
    if planet.owner != mission.target:
        return -8, "The colony changed ownership."
    if planet.loyalty_until >= game.turn:
        return -12, f"Civic investment protects loyalty until turn {planet.loyalty_until}."
    strain = game.strain_report(planet).total
    hungry = game.population_report(planet).balance < 0
    if strain < 20 and not hungry:
        return -8, "Content colony: keep strain below 20% and food in surplus."
    state = game.diplomacy_between(mission.owner, mission.target)
    if game.empire_rates_for(mission.owner)[0] < 0:
        return -4, "Union budget deficits undermine confidence."
    breaches = sum(game.diplomacy_between(mission.owner, other).broken_promises.get(mission.owner, 0)
                   for other in game.owners if other != mission.owner)
    rate = max(1, 6+min(6, int(strain)//10-2)+3*hungry+2*state.friendship_active
               +state.trade_active-min(8, breaches*2))
    return rate, f"Strain {strain:.0f}%"+("; food shortage" if hungry else "")+"; local support grows."


def start_error(game, owner, sid, pid):
    if error := game.strategy_error(owner):
        return error
    if error := eligibility(game, owner, sid, pid):
        return error
    if mission_at(game, sid, pid):
        return "An outreach mission is already active here."
    if sum(m.owner == owner for m in game.union_missions) >= MAX_MISSIONS:
        return f"At most {MAX_MISSIONS} missions can operate at once."
    if game._empire(owner).credits < START_COST:
        return f"Opening a mission costs {START_COST} CR."
    return None


def start(game, sid, pid, owner="player"):
    from .model import RuleError
    if error := start_error(game, owner, sid, pid):
        raise RuleError(error)
    planet = game.planet_at(sid, pid)
    game._empire(owner).credits -= START_COST
    mission = Mission(owner, planet.owner, sid, pid, game.turn)
    game.union_missions.append(mission)
    coalitions.notify(game, (owner, planet.owner),
        f"{game.empire_name_for(owner)} opened accession talks on {planet.name}. Civic investment can protect its loyalty.")
    return mission


def cancel(game, sid, pid, owner="player"):
    from .model import RuleError
    if error := game.strategy_error(owner):
        raise RuleError(error)
    mission = mission_at(game, sid, pid)
    if mission is None or mission.owner != owner:
        raise RuleError("This is not your mission.")
    game.union_missions.remove(mission)


def civic_error(game, sid, pid, owner="player"):
    if error := game.strategy_error(owner):
        return error
    planet = game.planet_at(sid, pid)
    if planet.owner != owner:
        return "Civic investment is available only on your colonies."
    if planet.loyalty_until >= game.turn:
        return f"Investment remains active until turn {planet.loyalty_until}."
    if game._empire(owner).credits < CIVIC_COST:
        return f"Civic investment costs {CIVIC_COST} CR."
    return None


def invest(game, sid, pid, owner="player"):
    from .model import RuleError
    if error := civic_error(game, sid, pid, owner):
        raise RuleError(error)
    game._empire(owner).credits -= CIVIC_COST
    game.planet_at(sid, pid).loyalty_until = game.turn+CIVIC_TURNS


def advance(game, alerts):
    from .production import ASCENSION_GATE
    for mission in list(game.union_missions):
        planet = game.planet_at(mission.system_id, mission.planet_id)
        if planet.owner != mission.target or not game.colony_systems(mission.owner):
            game.union_missions.remove(mission)
            continue
        empire = game._empire(mission.owner)
        if empire.credits < 0:
            mission.progress = max(0, mission.progress-8)
            continue
        rate, reason = support(game, mission)
        mission.progress = max(0, min(100, mission.progress+rate))
        if mission.progress < 100:
            continue
        before = administration.snapshot(game)
        species.normalize(game)
        planet.owner = mission.owner
        planet.garrison = planet.militia_losses = 0
        planet.ascension_gate, planet.gate_charge = False, 0
        planet.construction_queue[:] = [q for q in planet.construction_queue if q.item_id != ASCENSION_GATE.id]
        game.union_missions.remove(mission)
        administration.ownership_changed(game, before)
        game.diplomacy_between(mission.owner, mission.target).improve(-12)
        message = f"{planet.name} voted to join {game.empire_name_for(mission.owner)}. Its people retain their species and local traits."
        coalitions.notify(game, (mission.owner, mission.target), message)
        if "player" in (mission.owner, mission.target):
            alerts.append(message)
        exploration.refresh(game)


def ai_orders(game, owner):
    for mission in list(game.union_missions):
        if mission.target == owner and mission.progress >= 35 and civic_error(game, mission.system_id, mission.planet_id, owner) is None:
            invest(game, mission.system_id, mission.planet_id, owner)
    if game._empire(owner).race_id != "serevan" or game.turn % 4:
        return
    for system in game.systems:
        if not game.system_visible(system.id, owner):
            continue
        for planet in system.worlds:
            if start_error(game, owner, system.id, planet.id) is None:
                probe = Mission(owner, planet.owner, system.id, planet.id, game.turn)
                if support(game, probe)[0] > 0:
                    start(game, system.id, planet.id, owner)
                    return


def load(game, data, version):
    if version < 50:
        return
    records = data.get("union_missions", [])
    if not isinstance(records, list) or len(records) > MAX_MISSIONS*len(game.owners):
        raise ValueError("Invalid Union missions")
    occupied, counts = set(), {}
    for row in records:
        if not isinstance(row, dict) or set(row) != {"owner", "target", "system_id", "planet_id", "started", "progress"}:
            raise ValueError("Invalid Union mission record")
        m = Mission(**row)
        if (m.owner not in game.owners or m.target not in game.owners or m.owner == m.target
                or game._empire(m.owner).race_id != "serevan"
                or type(m.system_id) is not int or not 0 <= m.system_id < len(game.systems)
                or type(m.planet_id) is not int or not 0 <= m.planet_id < len(game.systems[m.system_id].worlds)
                or type(m.started) is not int or not 1 <= m.started <= game.turn
                or type(m.progress) is not int or not 0 <= m.progress < 100):
            raise ValueError("Invalid Union mission state")
        key = m.system_id, m.planet_id
        counts[m.owner] = counts.get(m.owner, 0)+1
        if key in occupied or counts[m.owner] > MAX_MISSIONS:
            raise ValueError("Duplicate or excessive Union missions")
        occupied.add(key)
        game.union_missions.append(m)
