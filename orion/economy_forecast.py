"""Construction forecasts share resources in the same order as real turns."""

from dataclasses import replace
from . import economy, population, raiding


def queue_estimates(game, planet, additional=None):
    from .model import ConstructionProject
    if not planet.colonized:
        return []
    colonies = [(s.id, p) for s in game.systems for p in s.worlds if p.owner == planet.owner]
    target = next((i for i, (_, p) in enumerate(colonies)
                   if p is planet or (p.id == planet.id and p.name == planet.name)), None)
    if target is None:
        return []
    bonuses = game.bonuses_for(planet.owner)
    bank = game.resources_for(planet.owner)
    # A cache is runtime-only, excluded from dataclass serialization. It is
    # invalidated by jobs, queues, power switches, research, bank or turn changes.
    signature = (repr(colonies), repr(bonuses), bank, game.turn, game.seed, repr(game.designs))
    if getattr(game, "_forecast_signature", None) != signature:
        game._forecast_signature, game._forecast_cache = signature, {}
    key = (target, repr(additional))
    if key in game._forecast_cache:
        return list(game._forecast_cache[key])
    worlds = [(sid, replace(p, buildings=p.buildings.copy(), disabled_buildings=p.disabled_buildings.copy(),
                            construction_queue=[replace(q) for q in p.construction_queue])) for sid, p in colonies]
    focus = worlds[target][1]
    if additional is not None:
        project = (replace(additional) if isinstance(additional, ConstructionProject) else
                   ConstructionProject(additional, resource_cost=game.project_price(additional, planet.owner),
                                       design=game.design_for(additional)))
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

    for elapsed in range(1, 2001):
        if not focus.construction_queue:
            break
        bank += sum(economy.mining_output(p, bonuses) for _, p in worlds)
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
