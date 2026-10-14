"""Validated balance profiles shared by the desktop editor and game saves.

One running campaign uses one profile. Catalogues retain their dictionary
identity; consumers read scalar rules from their owning module at use time.
Profiles contain data only and never execute code or select arbitrary modules.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict, fields, replace
from functools import lru_cache
from pathlib import Path
import importlib
import json
import math
import os
import sys
import tempfile

FORMAT = 'orion-reach-balance'
VERSION = 9
DEFAULT_PATH = Path(__file__).resolve().parents[1] / 'balance.json'
CATALOGUES = {
    'alignment': ('alignment', 'PROFILES'),
    'megastructures': ('megastructures', 'MEGASTRUCTURES'),
    'buildings': ('buildings', 'BUILDINGS'),
    'ships': ('production', 'SHIP_TYPES'),
    'hulls': ('designs', 'HULLS'),
    'modules': ('designs', 'MODULES'),
    'weapons': ('weapons', 'BEAMS'),
    'races': ('races', 'RACES'),
    'technologies': ('research', 'TECHNOLOGIES'),
    'branches': ('research', 'BRANCHES'),
    'guardians': ('monsters', 'MONSTERS'),
    'personalities': ('personalities', 'PERSONALITIES'),
    'specialists': ('specialists', 'SPECIALISTS'),
    'expedition_sites': ('specialists', 'SITES'),
}
# Explicit allowlist: UI geometry, save limits and identifiers are not balance.
RULES = {
    'alignment': ('alignment', ('REFERENCE_DISTANCE', 'MAX_MODIFIER')),
    'megastructures': ('megastructures', ('REPAIR_WORK', 'REPAIR_RESOURCES')),
    'administration': ('administration', ('SYSTEM_STRAIN', 'INTEGRATION_STRAIN', 'INTEGRATION_TURNS',
                         'DISTANCE_STRAIN', 'DISTANCE_UNIT_LY', 'MAX_STRAIN', 'RESEARCH_SENSITIVITY',
                         'CREDITS_SENSITIVITY', 'INDUSTRY_SENSITIVITY', 'MINING_SENSITIVITY', 'FOOD_SENSITIVITY')),
    'outposts': ('outposts', ('OUTPOST_HULL', 'OUTPOST_RECOVERY')),
    'specialists': ('specialists', ('XP_PER_TURN', 'XP_PER_LEVEL', 'MAX_LEVEL', 'MAX_EMPLOYED', 'MAX_VISITORS', 'VISIT_INTERVAL', 'VISIT_DURATION', 'SURVEY_WORK', 'SOCIAL_VISIT_CHANCE', 'NORMAL_VISIT_CHANCE', 'ISOLATED_VISIT_CHANCE')),
    'economy': ('economy', ('STARTING_CREDITS', 'STARTING_RESOURCES', 'STARTING_POPULATION', 'BASE_EXTRACTION', 'MINER_RESOURCES', 'BASE_ENERGY', 'GATE_ENERGY')),
    'production': ('production', ('SHIP_SPEED', 'BASE_FUEL_RANGE', 'STARTING_COLONISTS', 'REPAIR_PER_TURN', 'TROOP_STRENGTH', 'GATE_CHARGE_TURNS', 'TRADE_GOODS_PERCENT')),
    'population': ('population', ('GROWTH_THRESHOLD', 'GROWTH_LIMIT', 'GAIA_GROWTH_LIMIT', 'GROWTH_PER_FOOD', 'ASSEMBLY_GROWTH_LIMIT', 'GROWTH_PER_INDUSTRY', 'GAIA_CAPACITY')),
    'workers': ('research', ('WORKER_INDUSTRY', 'SCIENTIST_RESEARCH', 'POPULATION_INCOME')),
    'defenses': ('defenses', ('BASE_HULL', 'SHIELD_CAPACITY', 'SHIELD_RECOVERY', 'BASE_RECOVERY')),
    'diplomacy': ('diplomacy', ('OFFER_COOLDOWN', 'RESEARCH_INCOME', 'BREAK_PENALTY',
                             'TRADE_THRESHOLD', 'NON_AGGRESSION_THRESHOLD', 'FRIENDSHIP_THRESHOLD',
                             'TRADE_SHARE_PERCENT', 'TRADE_DISTANCE_LY')),
    'tomb_worlds': ('tomb_worlds', ('TOMB_CHANCE', 'AWAKENING_CHANCE', 'AWAKENED_TROOPS', 'AWAKENED_POPULATION')),
    'raiding': ('raiding', ('SLAVE_CAPACITY', 'MORTALITY_CHANCE', 'CREDITS_PER_POPULATION')),
    'council': ('council', ('ELECTION_INTERVAL',)),
    'combat': ('combat', ('DRONE_HULL', 'DRONES_PER_BAY', 'LAUNCHES_PER_BAY')),
    'navigation': ('navigation', ('GATE_SPEED_BONUS', 'INTERDICTION_SLOW', 'INTERDICTION_RANGE')),
    'sensors': ('sensors', ('ARRAY_RANGE', 'CONTACT_LIFETIME')),
    'galaxy': ('model', ('MIN_STAR_DISTANCE',)),
}
LABELS = {
    'alignment': 'Diplomatic values',
    'megastructures': 'Megastructures',
    'buildings': 'Buildings', 'ships': 'Standard ships', 'hulls': 'Designer hulls',
    'modules': 'Ship modules', 'weapons': 'Weapons', 'races': 'Races',
    'technologies': 'Technologies', 'branches': 'Research branches',
    'guardians': 'Guardians', 'personalities': 'AI personalities',
    'specialists': 'Specialists', 'expedition_sites': 'Expedition sites',
    'projects': 'Special projects', 'world_sizes': 'Planet sizes',
    'biomes': 'Planet biomes', 'minerals': 'Mineral richness',
    'rules': 'Global rules', 'research_costs': 'Research costs', 'drones': 'Drone roles', 'galaxy_sizes': 'Galaxy sizes',
}
_configured_path = None
_active = None


class BalanceError(ValueError):
    pass


def module(name):
    return importlib.import_module('.'+name, __package__)


def json_value(value):
    return json.loads(json.dumps(value, allow_nan=False))


@lru_cache(maxsize=1)
def _defaults():
    data = {}
    for section, (owner, attribute) in CATALOGUES.items():
        data[section] = {}
        for identifier, spec in getattr(module(owner), attribute).items():
            entry = json_value(asdict(spec))
            entry.pop('id', None)
            for key in {'races': ('trade_threshold', 'envoy_bonus'), 'personalities': ('envoy', 'gift')}.get(section, ()):
                entry.pop(key, None)
            if 'effects' in entry:
                entry['effects'] = dict(entry['effects'])
            data[section][identifier] = entry
    p, b, pop, r = module('production'), module('buildings'), module('population'), module('research')
    data['projects'] = {'ascension_gate': {k: v for k, v in asdict(p.ASCENSION_GATE).items() if k != 'id'}}
    data['world_sizes'] = {size: {'building_slots': b.BUILDING_SLOTS[size], 'population_limit': pop.POPULATION_LIMITS[size]} for size in b.BUILDING_SLOTS}
    model = module('model')
    data['biomes'] = {biome: {'base_food': pop.BASE_FOOD[biome], 'farmer_output': pop.FARMER_OUTPUT[biome], 'habitability': model.HABITABILITY[biome]} for biome in pop.BASE_FOOD}
    data['galaxy_sizes'] = {key: {'star_count': value} for key,value in model.GALAXY_SIZES.items()}
    for key,entry in data['ships'].items():
        entry['movement'] = module('combat').MOVEMENT[key]
    data['minerals'] = {name: {'multiplier': float(value)} for name, value in b.MINERAL_FACTORS.items()}
    data['rules'] = {group: {key: getattr(module(owner), key) for key in keys} for group, (owner, keys) in RULES.items()}
    data['research_costs'] = {str(tier): {'cost': cost} for tier, cost in enumerate(r.TIER_COSTS, 1)}
    data['research_costs']['ascension'] = {'cost': r.ASCENSION_COST}
    data['drones'] = {name: dict(zip(('name', 'weapon', 'movement'), values)) for name, values in module('weapons').DRONE_ROLES.items()}
    return {'format': FORMAT, 'version': VERSION, 'name': 'Standard balance',
            'branch_order': list(r.BRANCHES), 'data': data}


def default_profile():
    return deepcopy(_defaults())


def legacy_profile():
    """Preserve the research choices of campaigns without a saved profile."""
    from .legacy_research import PRE_REBALANCE_TIERS
    profile = default_profile()
    for branch, tiers in PRE_REBALANCE_TIERS.items():
        for tier, pair in enumerate(tiers, 1):
            for order, identifier in enumerate(pair):
                profile['data']['technologies'][identifier].update(branch=branch, tier=tier, order=order)
    return profile


def active_profile():
    return deepcopy(_active if _active is not None else _defaults())


def effect_keys():
    data = _defaults()['data']
    return sorted({key for section in ('races', 'technologies') for entry in data[section].values() for key in entry['effects']})


def numeric_bounds(section, field):
    if field in ('TRADE_THRESHOLD', 'NON_AGGRESSION_THRESHOLD', 'FRIENDSHIP_THRESHOLD'): return -30, 100
    if field == 'TRADE_SHARE_PERCENT': return 0, 100
    if field == 'TRADE_DISTANCE_LY': return 1, 200
    if section == 'alignment': return -2, 2
    if field == 'REFERENCE_DISTANCE': return 0.1, 20
    if field == 'MAX_MODIFIER': return 0, 25
    if field in ('REPAIR_WORK', 'REPAIR_RESOURCES'): return 1, 1000
    if field == 'discovery_chance_per_stage': return 0, 25
    if field == 'ship_speed_per_stage': return 0, 50
    if field == 'DISTANCE_UNIT_LY': return .1, 200
    if field == 'MAX_STRAIN': return 0, 99
    if field in ('SYSTEM_STRAIN', 'INTEGRATION_STRAIN', 'DISTANCE_STRAIN') or field.endswith('_SENSITIVITY'): return 0, 100
    if field == 'INTEGRATION_TURNS': return 0, 10000
    if field in ('SOCIAL_VISIT_CHANCE', 'NORMAL_VISIT_CHANCE', 'ISOLATED_VISIT_CHANCE'): return 0, 100
    if field in ('MAX_LEVEL', 'MAX_EMPLOYED', 'MAX_VISITORS'): return 1, 18
    if field in ('XP_PER_LEVEL', 'VISIT_INTERVAL', 'VISIT_DURATION', 'SURVEY_WORK', 'difficulty', 'work'): return 1, 10000
    if section == 'specialists' and field in module('specialists').SKILLS: return 0, 100
    if field in ('offensive_slots', 'defensive_slots', 'support_slots'): return 1 if field == 'offensive_slots' else 0, 12
    if field == 'module_scale': return 1, 1000
    if field == 'tracking_penalty': return 0, 100
    if field == 'tier': return 1, 8
    if field in ('accuracy', 'shield_bypass', 'interception_piercing', 'shield_hardening', 'interception', 'interception_cap', 'TRADE_GOODS_PERCENT'): return 0, 100
    if field in ('work_cost', 'space', 'hull', 'DRONE_HULL', 'OUTPOST_HULL', 'cost', 'shots', 'shield_multiplier', 'versus_drones', 'versus_capitals'): return 1, 100000
    if field == 'resource_cost': return 1, 100000
    if field == 'building_slots': return 1, 12
    if field == 'population_limit': return 1, 100
    if field == 'STARTING_POPULATION': return 1, 100
    if field == 'habitability': return 0, 100
    if field == 'star_count': return 24, 72
    if field == 'MIN_STAR_DISTANCE': return 1, 8
    if field == 'SHIP_SPEED': return .001, 1.0
    if field == 'BASE_FUEL_RANGE': return 1, 200
    if field == 'INTERDICTION_SLOW': return 0, 95
    if field == 'INTERDICTION_RANGE': return 1, 200
    if field in ('GROWTH_THRESHOLD', 'ELECTION_INTERVAL', 'MORTALITY_CHANCE', 'TOMB_CHANCE', 'AWAKENING_CHANCE', 'GATE_CHARGE_TURNS'): return 1, 10000
    if field in ('STARTING_COLONISTS', 'AWAKENED_POPULATION', 'SLAVE_CAPACITY'): return 1, 100
    if field in ('capacity', 'weapon', 'defense', 'support') and section == 'hulls': return 1 if field in ('capacity','weapon') else 0, 24
    if field == 'movement': return 0, 20
    if field == 'range': return 0, 50
    if field in ('movement_bonus', 'envoy', 'gift', 'envoy_bonus', 'trade_bonus', 'research_bonus'): return -100, 100
    if field in ('trade_threshold','research_threshold'): return -100, 100
    if field in ('DRONES_PER_BAY', 'LAUNCHES_PER_BAY', 'drone_bays'): return 0, 8
    if field == 'multiplier': return .1, 10
    return 0, 100000


def _number(value, template, section, field, path, errors):
    expected = (int, float) if type(template) is float or field in ('industry_per_worker', 'income_per_population') else (int,)
    low, high = numeric_bounds(section, field)
    if type(value) not in expected or not math.isfinite(value) or not low <= value <= high:
        errors.append(f'{path}: use {"a number" if float in expected else "a whole number"} from {low:g} to {high:g}.')


def validate(profile):
    errors = []
    base = _defaults()
    if not isinstance(profile, dict) or set(profile) != set(base):
        return ['Not a complete Orion Reach balance profile.']
    if profile['format'] != FORMAT or type(profile['version']) is not int or profile['version'] != VERSION:
        return ['Unsupported balance profile format or version.']
    if not isinstance(profile['name'], str) or not 1 <= len(profile['name'].strip()) <= 80 or not profile['name'].isprintable():
        errors.append('Profile name must contain 1–80 printable characters.')
    order = profile['branch_order']
    if not isinstance(order, list) or any(type(v) is not str for v in order) or sorted(order) != sorted(base['branch_order']):
        errors.append('Branch order must contain each research branch exactly once.')
    data = profile['data']
    if not isinstance(data, dict) or set(data) != set(base['data']):
        return errors+['The catalogue sections do not match this editor version.']
    for section, defaults in base['data'].items():
        table = data[section]
        if not isinstance(table, dict) or set(table) != set(defaults):
            errors.append(f'{section}: keep the existing item identifiers.')
            continue
        for identifier, original in defaults.items():
            entry, prefix = table[identifier], f'{section}.{identifier}'
            if not isinstance(entry, dict) or set(entry) != set(original):
                errors.append(prefix+': missing or unknown fields.')
                continue
            for key, template in original.items():
                value, path = entry[key], prefix+'.'+key
                if key == 'effects':
                    if not isinstance(value, dict) or set(value)-set(effect_keys()):
                        errors.append(path+': unknown effect names.')
                        continue
                    for effect, amount in value.items():
                        lower = -90 if effect in ('industry_percent','research_percent','income_percent','capacity_percent','ship_speed_percent','fuel_range_percent') else -100 if effect in ('growth_percent','lush_growth_percent','harsh_industry_percent','food_use_percent') else 0
                        upper = 100 if effect in ('building_discount','ship_discount','assembly_percent','targeting_accuracy','torpedo_guidance','evasion','beam_precision') else 95 if effect == 'interdiction_slow' else 3 if effect == 'sensor_level' else 1000
                        if type(amount) is not int or not lower <= amount <= upper:
                            errors.append(path+'.'+effect+f': use a whole number from {lower} to {upper}.')
                elif section == 'megastructures' and key == 'branch':
                    if type(value) is not str or value not in base['branch_order']:
                        errors.append(path+': choose a research branch.')
                elif section == 'specialists' and key == 'role':
                    if type(value) is not str or value not in ('leader', 'explorer'):
                        errors.append(path+': choose leader or explorer.')
                elif section == 'expedition_sites' and key == 'skill':
                    if type(value) is not str or value not in ('hacking', 'extraction', 'archaeology'):
                        errors.append(path+': choose hacking, extraction or archaeology.')
                elif key == 'module_size':
                    if type(value) is not str or value not in module('designs').MODULE_SIZES:
                        errors.append(path+': choose small, medium or heavy.')
                elif key in ('technology', 'branch', 'category', 'weapon') and (template is None or type(template) is str):
                    options = set(base['data']['technologies'])|{None} if key == 'technology' else set(base['branch_order'])|{'ascension'} if key == 'branch' else {'weapon','defense','support'} if key == 'category' else set(base['data']['weapons'])
                    if type(value) not in (str,type(None)) or value not in options:
                        errors.append(path+': choose a valid reference.')
                elif type(template) is bool:
                    if type(value) is not bool: errors.append(path+': use true or false.')
                elif type(template) in (int, float):
                    _number(value, template, section, key, path, errors)
                elif type(template) is str:
                    maximum = 2000 if key in ('description','summary','greeting','special_effect') else 120
                    if key in ('default_empire','home_system'): maximum = 24
                    elif key == 'homeworld': maximum = 34
                    elif key == 'name': maximum = 60
                    required = key in ('name','default_empire','home_system','homeworld')
                    if not isinstance(value, str) or len(value) > maximum or (value and not value.isprintable()) or (required and (not value.strip() or value != value.strip())):
                        errors.append(path+f': use printable text (up to {maximum} characters).')
                elif type(template) is list:
                    if not isinstance(value,list) or len(value) != len(template):
                        errors.append(path+': keep the existing number of entries.')
                    elif key == 'color':
                        if any(type(v) is not int or not 0 <= v <= 255 for v in value): errors.append(path+': RGB values must be 0–255.')
                    elif any(not isinstance(v,str) or not v.isprintable() or len(v)>180 for v in value):
                        errors.append(path+': invalid text list.')
                    elif key == 'home_neighbors' and any(not v.strip() or v != v.strip() or len(v)>34 for v in value):
                        errors.append(path+': world names need 1–34 characters without surrounding spaces.')
                    elif key in ('development','research_priority'):
                        allowed = base['data']['buildings'] if key == 'development' else base['branch_order']
                        if len(set(value)) != len(value) or any(v not in allowed for v in value): errors.append(path+': choose distinct existing items.')
    if errors:
        return errors
    for key, entry in data['technologies'].items():
        if (key == 'ascension_theory') != (entry['branch'] == 'ascension'):
            errors.append('Ascension Theory must remain the separate finale; other technologies belong to a branch.')
    for branch in base['branch_order']:
        items = [v for v in data['technologies'].values() if v['branch'] == branch]
        tiers = sorted({v['tier'] for v in items})
        if not tiers or tiers != list(range(1, max(tiers)+1)):
            errors.append(f'{branch}: tiers must start at 1 with no empty tiers between them.')
        for tier in tiers:
            if sum(v['tier'] == tier for v in items) > 2:
                errors.append(f'{branch}, tier {tier}: at most two alternatives fit the current game. Swap a technology instead.')
    for identifier, hull in data['hulls'].items():
        if any(hull[k] > hull['capacity'] for k in ('weapon','defense','support')):
            errors.append(f'hulls.{identifier}: category capacity cannot exceed total capacity.')
    for identifier, entry in data['modules'].items():
        if entry['damage'] and (entry['weapon'] == 'none' or entry['range'] < 1):
            errors.append(f'modules.{identifier}: damaging modules need a weapon and positive range.')
    for identifier, entry in data['weapons'].items():
        if entry['damage'] and entry['range'] < 1:
            errors.append(f'weapons.{identifier}: damaging weapons need positive range.')
    max_size = max(v['population_limit'] for v in data['world_sizes'].values())+data['rules']['population']['GAIA_CAPACITY']
    extra_capacity = sum(v['effects'].get('capacity_percent',0) for v in data['technologies'].values())
    if any(max_size*(100+extra_capacity+v['effects'].get('capacity_percent',0))//100 > 100 for v in data['races'].values()):
        errors.append('Planet size and race capacity bonuses must keep population at or below the engine limit of 100 B.')
    if data['rules']['combat']['LAUNCHES_PER_BAY'] < data['rules']['combat']['DRONES_PER_BAY']:
        errors.append('Drone launches per bay must cover the number of active drones per bay.')
    effects = [v['effects'] for v in data['technologies'].values()]
    racial = [v['effects'] for v in data['races'].values()]
    for key in ('industry_percent','income_percent','research_percent','capacity_percent','ship_speed_percent','fuel_range_percent','food_use_percent'):
        minimum = sum(min(0,e.get(key,0)) for e in effects)+min(e.get(key,0) for e in racial)
        if minimum < -100 or (key == 'ship_speed_percent' and minimum == -100):
            errors.append(f'Combined {key} penalties cannot exceed 100%.')
    if max(e.get('interdiction_slow',0) for e in effects)+max(e.get('interdiction_slow',0) for e in racial) >= 100:
        errors.append('Combined interdiction slowdown must stay below 100%.')
    if data['rules']['production']['STARTING_COLONISTS']+sum(e.get('colonists',0) for e in effects)+max(e.get('colonists',0) for e in racial)>100:
        errors.append('Starting colonists plus researched/racial bonuses cannot exceed 100 B.')
    names = [entry['name'].casefold() for entry in data['specialists'].values()]
    if len(set(names)) != len(names):
        errors.append('Specialists must have unique names.')
    skills = module('specialists').SKILLS
    profiles = []
    for identifier, entry in data['specialists'].items():
        allowed = ('industry', 'research', 'income', 'food', 'mining') if entry['role'] == 'leader' else ('survey', 'hacking', 'extraction', 'archaeology')
        if any(entry[key] for key in skills if key not in allowed) or not any(entry[key] for key in allowed):
            errors.append('specialists.'+identifier+': choose skills belonging to this role.')
        if entry['role'] == 'explorer' and not entry['survey']:
            errors.append('specialists.'+identifier+': explorers need a positive Surveying skill.')
        profiles.append(tuple(entry[key] for key in skills))
    if len(set(profiles)) != len(profiles):
        errors.append('Specialists must have distinct starting skill profiles.')
    return errors


def require_valid(profile):
    errors = validate(profile)
    if errors:
        raise BalanceError('\n'.join(errors[:12]))


def upgrade_profile(profile):
    """Add new controls/facilities without replacing saved values or tree layouts."""
    if isinstance(profile, dict) and profile.get('format') == FORMAT and profile.get('version') == 1:
        profile = deepcopy(profile)
        hulls = profile.get('data', {}).get('hulls', {}) if isinstance(profile.get('data'), dict) else {}
        if isinstance(hulls, dict):
            for identifier, defaults in _defaults()['data']['hulls'].items():
                if isinstance(hulls.get(identifier), dict):
                    for key in ('offensive_slots', 'defensive_slots', 'support_slots',
                                'module_size', 'module_scale', 'tracking_penalty'):
                        hulls[identifier].setdefault(key, defaults[key])
        profile['version'] = 2
    if isinstance(profile, dict) and profile.get('format') == FORMAT and profile.get('version') == 2:
        from .buildings import ADVANCED_FACILITIES
        profile = deepcopy(profile)
        buildings = profile.get('data', {}).get('buildings', {}) if isinstance(profile.get('data'), dict) else {}
        if isinstance(buildings, dict):
            for identifier in ADVANCED_FACILITIES:
                buildings.setdefault(identifier, deepcopy(_defaults()['data']['buildings'][identifier]))
        profile['version'] = 3
    if isinstance(profile, dict) and profile.get('format') == FORMAT and profile.get('version') == 3:
        profile = deepcopy(profile)
        data = profile.get('data')
        if isinstance(data, dict):
            for section in ('specialists', 'expedition_sites'):
                data.setdefault(section, deepcopy(_defaults()['data'][section]))
            if isinstance(data.get('buildings'), dict):
                data['buildings'].setdefault('space_hub', deepcopy(_defaults()['data']['buildings']['space_hub']))
            if isinstance(data.get('rules'), dict):
                data['rules'].setdefault('specialists', deepcopy(_defaults()['data']['rules']['specialists']))
        profile['version'] = 4
    if isinstance(profile, dict) and profile.get('format') == FORMAT and profile.get('version') == 4:
        profile = deepcopy(profile)
        data = profile.get('data')
        if isinstance(data, dict):
            if isinstance(data.get('ships'), dict):
                data['ships'].setdefault('outpost_ship', deepcopy(_defaults()['data']['ships']['outpost_ship']))
                colony = data['ships'].get('colony_ship')
                # Migrate the former standard price; retain deliberate editor overrides.
                if isinstance(colony, dict):
                    if colony.get('resource_cost') == 80:
                        colony['resource_cost'] = 800
                    if colony.get('work_cost') == 42:
                        colony['work_cost'] = 420
            if isinstance(data.get('rules'), dict):
                data['rules'].setdefault('outposts', deepcopy(_defaults()['data']['rules']['outposts']))
        profile['version'] = 5
    if isinstance(profile, dict) and profile.get('format') == FORMAT and profile.get('version') == 5:
        profile = deepcopy(profile)
        data = profile.get('data')
        if isinstance(data, dict) and isinstance(data.get('rules'), dict):
            data['rules'].setdefault('administration', deepcopy(_defaults()['data']['rules']['administration']))
        profile['version'] = 6
    if isinstance(profile, dict) and profile.get('format') == FORMAT and profile.get('version') == 6:
        profile = deepcopy(profile)
        data = profile.get('data')
        if isinstance(data, dict) and isinstance(data.get('rules'), dict):
            data.setdefault('megastructures', deepcopy(_defaults()['data']['megastructures']))
            data['rules'].setdefault('megastructures', deepcopy(_defaults()['data']['rules']['megastructures']))
        profile['version'] = 7
    if isinstance(profile, dict) and profile.get('format') == FORMAT and profile.get('version') == 7:
        profile = deepcopy(profile)
        data = profile.get('data')
        if isinstance(data, dict):
            data.setdefault('alignment', deepcopy(_defaults()['data']['alignment']))
            if isinstance(data.get('rules'), dict):
                data['rules'].setdefault('alignment', deepcopy(_defaults()['data']['rules']['alignment']))
        profile['version'] = 8
    if isinstance(profile, dict) and profile.get('format') == FORMAT and profile.get('version') == 8:
        profile = deepcopy(profile)
        data = profile.get('data')
        if isinstance(data, dict):
            for section, keys in (('races', ('trade_threshold', 'envoy_bonus')), ('personalities', ('envoy', 'gift'))):
                if isinstance(data.get(section), dict):
                    for entry in data[section].values():
                        if isinstance(entry, dict):
                            for key in keys:
                                entry.pop(key, None)
            rules = data.get('rules', {}).get('diplomacy') if isinstance(data.get('rules'), dict) else None
            if isinstance(rules, dict):
                for key in ('ENVOY_COST', 'ENVOY_RELATIONS', 'ENVOY_COOLDOWN', 'GIFT_COST', 'GIFT_RELATIONS', 'GIFT_COOLDOWN', 'TRADE_INCOME'):
                    rules.pop(key, None)
                for key, value in _defaults()['data']['rules']['diplomacy'].items():
                    rules.setdefault(key, value)
        profile['version'] = VERSION
    return profile


def read_profile(path=DEFAULT_PATH, *, missing_ok=False):
    path = Path(path).expanduser()
    if missing_ok and not path.exists():
        return default_profile()
    try:
        if path.stat().st_size > 2_000_000:
            raise BalanceError('Balance profile exceeds 2 MB.')
        def unique_pairs(pairs):
            result = {}
            for k,v in pairs:
                if k in result: raise BalanceError('Duplicate profile field: '+k)
                result[k] = v
            return result
        profile = upgrade_profile(json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique_pairs))
        require_valid(profile)
        return profile
    except (OSError, ValueError, RecursionError) as exc:
        if isinstance(exc, BalanceError): raise
        raise BalanceError(f'Cannot read balance profile {path}: {exc}') from exc


def atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as file:
            temporary = Path(file.name)
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None: temporary.unlink(missing_ok=True)


def write_profile(path, profile, *, expected=None):
    require_valid(profile)
    path = Path(path).expanduser()
    current = path.read_text(encoding='utf-8') if path.exists() else ''
    if expected is not None and current != expected:
        raise BalanceError('This file changed outside the editor. Open it again or use Save as.')
    if current:
        atomic_write(path.with_suffix(path.suffix+'.bak'), current)
    content = json.dumps(profile, indent=2, ensure_ascii=False, allow_nan=False)+'\n'
    atomic_write(path, content)
    return content


def activate(profile):
    global _active
    profile = upgrade_profile(profile)
    require_valid(profile)  # Validate everything before changing any catalogue.
    data = profile['data']
    for section, (owner, attribute) in CATALOGUES.items():
        catalogue = getattr(module(owner), attribute)
        specs = {}
        for identifier, entry in data[section].items():
            values = deepcopy(entry)
            if section == 'ships': values.pop('movement')
            for key, value in values.items():
                if key == 'effects': values[key] = tuple(value.items())
                elif isinstance(value, list): values[key] = tuple(value)
            specs[identifier] = replace(catalogue[identifier], **values)
        catalogue.clear()
        catalogue.update(specs)
    r, p, b, pop = module('research'), module('production'), module('buildings'), module('population')
    ordered = {key: r.BRANCHES[key] for key in profile['branch_order']}
    r.BRANCHES.clear()
    r.BRANCHES.update(ordered)
    # Some modules import the special project object directly, so retain it.
    for key, value in data['projects']['ascension_gate'].items():
        object.__setattr__(p.ASCENSION_GATE, key, value)
    p.PROJECTS.clear()
    p.PROJECTS.update({**b.BUILDINGS, **p.SHIP_TYPES, p.ASCENSION_GATE.id:p.ASCENSION_GATE})
    p.HULL_TECHNOLOGIES.update({key: p.SHIP_TYPES[key].technology for key in p.HULL_TECHNOLOGIES})
    for size, entry in data['world_sizes'].items():
        b.BUILDING_SLOTS[size], pop.POPULATION_LIMITS[size] = entry['building_slots'], entry['population_limit']
    for biome, entry in data['biomes'].items():
        pop.BASE_FOOD[biome], pop.FARMER_OUTPUT[biome] = entry['base_food'], entry['farmer_output']
        module('model').HABITABILITY[biome] = entry['habitability']
    module('model').GALAXY_SIZES.update({key:v['star_count'] for key,v in data['galaxy_sizes'].items()})
    b.MINERAL_FACTORS.update({key: v['multiplier'] for key,v in data['minerals'].items()})
    for group, (owner, keys) in RULES.items():
        for key in keys:
            value = data['rules'][group][key]
            setattr(module(owner), key, float(value) if key == 'SHIP_SPEED' else value)
    r.TIER_COSTS = tuple(data['research_costs'][str(t)]['cost'] for t in r.TIERS)
    r.ASCENSION_COST = data['research_costs']['ascension']['cost']
    r._bonuses.cache_clear()
    module('auto_designs').auto_design.cache_clear()
    module('designs').fitted_module.cache_clear()
    w, c, d = module('weapons'), module('combat'), module('designs')
    w.DRONE_ROLES.update({key: tuple(v[k] for k in ('name','weapon','movement')) for key,v in data['drones'].items()})
    c.BASE_SPEC = replace(c.BASE_SPEC, hull=module('defenses').BASE_HULL,
                          damage=w.BEAMS['missile'].damage, name=b.BUILDINGS['missile_base'].name)
    c.DRONE_SPEC = replace(c.DRONE_SPEC, hull=c.DRONE_HULL, damage=w.BEAMS['drone_beam'].damage)
    c.COMBAT_TYPES.clear()
    c.COMBAT_TYPES.update({**p.SHIP_TYPES, **module('monsters').MONSTERS, 'missile_base':c.BASE_SPEC, 'combat_drone':c.DRONE_SPEC})
    c.MOVEMENT.update({key: v['movement'] for key,v in data['ships'].items()})
    c.MOVEMENT.update({key: v.movement for key,v in module('monsters').MONSTERS.items()})
    races = module('races')
    races.SETUP_RACES.update({key: spec for key, spec in races.RACES.items() if key in races.SETUP_RACES})
    if (encyclopedia := sys.modules.get('orion.encyclopedia')) is not None:
        encyclopedia.articles.cache_clear()
    _active = deepcopy(profile)


@contextmanager
def using_profile(profile):
    previous = active_profile()
    activate(profile)
    try:
        yield
    finally:
        activate(previous)


def configure(path=DEFAULT_PATH):
    global _configured_path
    profile = read_profile(path, missing_ok=True)
    activate(profile)
    _configured_path = Path(path).expanduser()


def prepare_new_game():
    if _configured_path is not None:
        activate(read_profile(_configured_path, missing_ok=True))


def tag_game(game, profile=None):
    game._balance_profile = deepcopy(upgrade_profile(profile) if profile is not None else active_profile())
    return game


def profile_for(game):
    return deepcopy(getattr(game, '_balance_profile', _defaults()))
