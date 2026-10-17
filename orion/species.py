"""Civilian species survive changes of government; counts are in billions."""

from .races import RACES

# Local physiology and productivity, never fleets, diplomacy or settlement rights.
LOCAL_EFFECTS = frozenset(("capacity_percent", "food_use_percent", "growth_percent",
    "lush_food", "lush_growth_percent", "harsh_industry_percent", "assembly_percent",
    "passive_growth", "industry_percent", "research_percent", "income_percent"))


def composition(planet, fallback="terran"):
    if not planet.colonized or not planet.population:
        return {}
    counts = {rid: n for rid, n in planet.species.items() if rid in RACES and n > 0}
    if not counts:
        return {fallback: planet.population}
    total = sum(counts.values())
    if total == planet.population:
        return dict(counts)
    # Largest remainders preserve the total after casualties or liberation.
    result = {rid: n*planet.population//total for rid, n in counts.items()}
    order = sorted(counts, key=lambda rid: (-(counts[rid]*planet.population % total), rid))
    for rid in order[:planet.population-sum(result.values())]:
        result[rid] += 1
    return {rid: n for rid, n in result.items() if n}


def normalize(game):
    worlds = [p for s in game.systems for p in s.worlds]
    worlds += [s.habitat for s in game.ships if s.habitat is not None]
    for planet in worlds:
        fallback = game._empire(planet.owner).race_id if planet.owner in game.owners else "terran"
        planet.species = composition(planet, fallback)


def local_effects(game, planet):
    if not planet.colonized or game._empire(planet.owner).race_id != "serevan":
        return {}
    counts = composition(planet, "serevan")
    effects = {}
    for rid, count in counts.items():
        if rid == "serevan":
            continue
        for key, value in RACES[rid].effects:
            if key in LOCAL_EFFECTS:
                effects[key] = effects.get(key, 0)+value*count
    return {key: round(value/max(1, planet.population)) for key, value in effects.items()}


def caption(planet, fallback="terran"):
    return ", ".join(f"{RACES[rid].name}: {n} B" for rid, n in sorted(composition(planet, fallback).items()))


def advance_swarm(game, alerts):
    normalize(game)
    if game.turn % 2:
        return
    for _, planet in game.settlements():
        if game._empire(planet.owner).race_id != "skirr" or game.population_report(planet).balance < 0:
            continue
        others = [rid for rid in planet.species if rid != "skirr"]
        if not others:
            continue
        original = max(others, key=lambda rid: (planet.species[rid], rid))
        planet.species = dict(planet.species)
        planet.species[original] -= 1
        if not planet.species[original]:
            del planet.species[original]
        planet.species["skirr"] = planet.species.get("skirr", 0)+1
        message = f"{planet.name}: Skirr broods replaced 1 B inhabitants; {planet.species['skirr']}/{planet.population} B are Skirr."
        if planet.owner == "player":
            alerts.append(message)
        else:
            game.rival_event(message, owner=planet.owner)


def validate(record, version):
    if version < 50:
        record["species"] = {}
        record["loyalty_until"] = 0
        return
    counts = record.setdefault("species", {})
    if (not isinstance(counts, dict) or len(counts) > len(RACES)
            or any(rid not in RACES or type(n) is not int or not 1 <= n <= 200 for rid, n in counts.items())
            or (counts and sum(counts.values()) != record["population"])):
        raise ValueError("Invalid civilian species counts")
    until = record.setdefault("loyalty_until", 0)
    if type(until) is not int or not 0 <= until <= 1_000_008:
        raise ValueError("Invalid civic investment duration")
