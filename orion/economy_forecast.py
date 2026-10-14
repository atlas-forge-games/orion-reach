"""Construction forecasts share resources in the same order as real turns."""

from dataclasses import replace
from . import economy, population, raiding, specialists, administration


def queue_estimates(game, planet, additional=None):
    from .model import ConstructionProject
    from . import megastructures
    if not planet.colonized:
        return []
    if planet.trade_goods and additional is None:
        return [None]*len(planet.construction_queue)
    if megastructures.has_projects(game, planet.owner):
        return megastructure_estimates(game, planet, additional)
    colonies = [(s.id, p) for s in game.systems for p in s.worlds if p.owner == planet.owner]
    target = next((i for i, (_, p) in enumerate(colonies)
                   if p is planet or (p.id == planet.id and p.name == planet.name)), None)
    if target is None:
        return []
    base_bonuses = dict(game.bonuses_for(planet.owner))
    bank = game.resources_for(planet.owner)
    # A cache is runtime-only, excluded from dataclass serialization. It is
    # invalidated by jobs, queues, power switches, research, bank or turn changes.
    signature = (repr(colonies), repr(base_bonuses), bank, game.turn, game.seed, repr(game.designs),
                 repr(specialists.employed(game, planet.owner)), repr(game.system_integration),
                 tuple((s.id, s.x, s.y) for s in game.systems))
    if getattr(game, "_forecast_signature", None) != signature:
        game._forecast_signature, game._forecast_cache = signature, {}
    key = (target, repr(additional))
    if key in game._forecast_cache:
        return list(game._forecast_cache[key])
    worlds = [(sid, replace(p, buildings=p.buildings.copy(), disabled_buildings=p.disabled_buildings.copy(),
                            construction_queue=[replace(q) for q in p.construction_queue])) for sid, p in colonies]
    focus = worlds[target][1]
    if additional is not None:
        focus.trade_goods = False
        if isinstance(additional, ConstructionProject):
            project = replace(additional)
        else:
            design = game.production_design(additional, planet.owner)
            project = ConstructionProject(design.id if design else additional,
                                          resource_cost=game.project_price(additional, planet.owner), design=design)
        focus.construction_queue.append(project)
    estimates = []
    count = len(focus.construction_queue)

    def fund(project):
        nonlocal bank
        if project.needs_resources > bank:
            return False
        bank -= project.needs_resources
        project.paid_resources = project.resource_cost
        return True

    administration_context = administration.Context(game, planet.owner)
    for elapsed in range(1, 2001):
        if not focus.construction_queue:
            break
        dispatch = economy.dispatch_power([p for _, p in worlds], base_bonuses, bank)
        local = {id(copy): {**specialists.colony_effects(game, original, elapsed-1),
                           **administration_context.effects(copy, turns=elapsed-1)}
                 for (_, original), (_, copy) in zip(colonies, worlds)}
        bonuses = economy.PowerBonuses(base_bonuses, lambda p: dispatch[id(p)], lambda p: local[id(p)])
        bank += sum(economy.mining_output(p, bonuses)-dispatch[id(p)].fuel_used for _, p in worlds)
        starts = [population.report(p, bonuses) for _, p in worlds]
        for (sid, p), food in zip(worlds, starts):
            complete = p.advance_construction(bonuses, fund=fund)
            if p is focus:
                estimates.extend([elapsed]*len(complete))
            population.advance(p, food)
            if p.slaves:
                p.slaves -= raiding.deaths(game, sid, p.id, p.owner, p.slaves, turn=game.turn+elapsed)
                population.clamp_workforce(p)
    estimates.extend([None]*(count-len(estimates)))
    game._forecast_cache[key] = tuple(estimates)
    return estimates


def megastructure_estimates(game, planet, additional):
    """Simulate the shared construction budget and evolving structure stages."""
    from copy import deepcopy
    from . import megastructures
    from .model import ConstructionProject
    sid = next(s.id for s in game.systems if any(p is planet for p in s.worlds))
    signature = (repr(game.systems), repr(game.ships), repr(game.guardians), game.turn,
                 game.resources_for(planet.owner), repr(game._base_bonuses(planet.owner)),
                 repr(game.specialists), repr(game.system_integration), repr(game.designs),
                 repr(game.diplomacy), repr(game.other_diplomacy), repr(megastructures.MEGASTRUCTURES),
                 megastructures.REPAIR_WORK, megastructures.REPAIR_RESOURCES)
    if getattr(game, "_mega_forecast_signature", None) != signature:
        game._mega_forecast_signature, game._mega_forecast_cache = signature, {}
    key = (sid, planet.id, repr(additional))
    if key in game._mega_forecast_cache:
        return list(game._mega_forecast_cache[key])
    # Copy persistent state only: callbacks inside runtime caches refer to live planets.
    from dataclasses import fields
    shadow = type(game)(**{f.name: deepcopy(getattr(game, f.name)) for f in fields(game)})
    focus = shadow.planet_at(sid, planet.id)
    if additional is not None:
        focus.trade_goods = False
        if isinstance(additional, ConstructionProject):
            project = replace(additional)
        else:
            design = game.production_design(additional, planet.owner)
            project = ConstructionProject(design.id if design else additional,
                                          resource_cost=game.project_price(additional, planet.owner), design=design)
        focus.construction_queue.append(project)
    count, estimates = len(focus.construction_queue), []
    for elapsed in range(1, 2001):
        if not focus.construction_queue:
            break
        plan = megastructures.make_plan(shadow, planet.owner)
        shadow._turn_megastructures = {planet.owner: plan}
        shadow._empire(planet.owner).resources += plan.net_resources
        worlds = [(s.id, p) for s in shadow.systems for p in s.worlds if p.owner == planet.owner]
        starts = [population.report(p, plan.bonuses) for _, p in worlds]
        for (system_id, p), food in zip(worlds, starts):
            complete = p.advance_construction(plan.bonuses, fund=lambda q: shadow.fund_project(q, planet.owner))
            if p is focus:
                estimates.extend([elapsed]*len(complete))
            population.advance(p, food)
            if p.slaves:
                p.slaves -= raiding.deaths(shadow, system_id, p.id, p.owner, p.slaves, turn=shadow.turn+1)
                population.clamp_workforce(p)
        megastructures.finish_work(shadow)
        shadow.turn += 1
        specialists.advance_employed(shadow)
        shadow.__dict__.pop("_turn_megastructures", None)
    estimates.extend([None]*(count-len(estimates)))
    game._mega_forecast_cache[key] = tuple(estimates)
    return estimates
