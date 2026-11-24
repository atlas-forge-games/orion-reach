"""Repeatable equipment research, separate from exclusive discoveries."""

from dataclasses import dataclass, replace
import math

POWER_STEP = .10
MANUFACTURING_STEP = .06
BENEFIT_RETENTION = .70
COST_GROWTH = 1.60
BASE_COST = 100
TECH_COST_FRACTION = .25
# Far beyond playable research budgets; bounds imported/save-file integers.
MAX_LEVEL = 100
TRACKS = ('power', 'manufacturing')


def targets():
    from .designs import MODULES
    return {key: module for key, module in MODULES.items()
            if module.damage or module.shields or module.hull_bonus}


def key_for(module, track):
    return f'{module}:{track}'


def split_key(key):
    if not isinstance(key, str):
        raise ValueError('Unknown equipment improvement')
    parts = key.split(':')
    if len(parts) != 2 or parts[0] not in targets() or parts[1] not in TRACKS:
        raise ValueError('Unknown equipment improvement')
    return tuple(parts)


def benefit(level, track):
    step = POWER_STEP if track == 'power' else MANUFACTURING_STEP
    return step*(1-BENEFIT_RETENTION**level)/(1-BENEFIT_RETENTION)


def track_name(module, track):
    if track == 'manufacturing':
        return 'Manufacturing efficiency'
    spec = targets()[module]
    return 'Weapon power' if spec.damage else 'Shield capacity' if spec.shields else 'Armor strength'


def unlocked(state, module):
    spec = targets().get(module)
    return spec is not None and (spec.technology is None or state.has_unlock(spec.technology))


def available_targets(state):
    return tuple(key for key in targets() if unlocked(state, key))


def cost(module, level):
    from .research import TECHNOLOGIES
    technology = targets()[module].technology
    base = max(BASE_COST, math.ceil(TECHNOLOGIES[technology].cost*TECH_COST_FRACTION)) if technology else BASE_COST
    return max(1, math.floor(base*COST_GROWTH**(level-1)+.5))


@dataclass(frozen=True)
class Improvement:
    id: str
    module: str
    track: str
    level: int
    cost: int

    @property
    def name(self):
        return f'{targets()[self.module].name} · {track_name(self.module, self.track)} {self.level}'


def project(state, key):
    module, track = split_key(key)
    level = state.improvements.get(key, 0)+1
    return Improvement(key, module, track, level, cost(module, level))


def choice_error(state, key):
    try:
        module, _ = split_key(key)
    except ValueError:
        return 'Choose an existing weapon, shield or armor improvement.'
    if not unlocked(state, module):
        return 'Discover this equipment technology first.'
    if state.improvements.get(key, 0) >= MAX_LEVEL:
        return 'This improvement has reached its limit.'
    if state.active_improvement == key:
        return 'This improvement is already being researched.'
    return None


def validate_levels(levels, *, state=None, modules=None):
    if not isinstance(levels, dict) or len(levels) > len(targets())*len(TRACKS):
        raise ValueError('Invalid equipment improvements')
    for key, level in levels.items():
        module, _ = split_key(key)
        if type(level) is not int or not 1 <= level <= MAX_LEVEL:
            raise ValueError('Invalid equipment improvement level')
        if state is not None and not unlocked(state, module):
            raise ValueError('Improvement without its equipment technology')
        if modules is not None and module not in modules:
            raise ValueError('Improvement without its fitted equipment')


def module_spec(spec, identifier, levels):
    """Apply percentages before rounding to the game's whole-unit statistics."""
    power = benefit(levels.get(key_for(identifier, 'power'), 0), 'power')
    discount = benefit(levels.get(key_for(identifier, 'manufacturing'), 0), 'manufacturing')
    if not power and not discount:
        return spec
    changes = {}
    for field in ('damage', 'hull_bonus', 'shields'):
        value = getattr(spec, field)
        if value and power:
            changes[field] = max(1, math.floor(value*(1+power)+.5))
    for field in ('resource_cost', 'work_cost'):
        value = getattr(spec, field)
        if value and discount:
            changes[field] = max(1, math.floor(value*(1-discount)+.5))
    return replace(spec, **changes)


def fitted_module(kind, identifier, state, fit_version=2):
    from .designs import fitted_module as base_module
    return module_spec(base_module(kind, identifier, fit_version), identifier, state.improvements)


def design_cost(design, field):
    """Combine fractional equipment savings before rounding the whole order."""
    from .designs import HULLS, fitted_module as base_module
    levels = dict(design.improvements)
    total = getattr(HULLS[design.kind], field)
    for identifier in design.modules:
        spec = base_module(design.kind, identifier, design.fit_version)
        discount = benefit(levels.get(key_for(identifier, 'manufacturing'), 0), 'manufacturing')
        total += getattr(spec, field)*(1-discount)
    return max(0, math.floor(total+.5))


def improve_design(design, levels, *, performance_only=False):
    if design is None:
        return None
    result = dict(design.improvements) if performance_only else {}
    for key, level in levels.items():
        module, track = split_key(key)
        if module in design.modules and (not performance_only or track == 'power'):
            result[key] = max(level, result.get(key, 0)) if performance_only else level
    values = tuple(sorted(result.items()))
    return replace(design, improvements=values) if values != design.improvements else design


def refresh_equipment(game, owner):
    """Upgrade fitted performance, preserving damage and existing order prices/work."""
    levels = game.research_state(owner).improvements
    if owner == 'player':
        game.designs = [improve_design(design, levels) for design in game.designs]
    for ship in game.ships_owned_by(owner):
        old_max = ship.max_hull
        ship.design = improve_design(ship.design, levels, performance_only=True)
        ship.hull += ship.max_hull-old_max
    for _, planet in game.settlements(owner):
        for order in planet.construction_queue:
            order.design = improve_design(order.design, levels, performance_only=True)


def ai_choice(game, owner, *, exhausted=False):
    """Occasionally refine equipment the fleet actually uses, without a free bonus."""
    state = game.research_state(owner)
    if not exhausted and sum(state.improvements.values()) >= len(state.completed)//3:
        return None
    fitted = {module for ship in game.ships_owned_by(owner) if ship.design for module in ship.design.modules}
    options = [project(state, key_for(module, track))
               for module in available_targets(state) if module in fitted for track in TRACKS
               if choice_error(state, key_for(module, track)) is None]
    return min(options, key=lambda item: (item.cost, item.track != 'power', item.module), default=None)
