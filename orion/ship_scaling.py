"""Shared engineering assumptions, in abstract game units rather than SI units.

Size is usable displacement, not the number of tactical board cells. Modules
occupy fixed UI slots, but each mount carries proportionally more equipment.
"""
import math

ENABLED = True
HULL_PER_SIZE = 20
FRAME_RES_PER_SIZE = 50
FRAME_COST_EXPONENT = 1.1
WORK_PER_RESOURCE = 0.6
UPKEEP_PER_SIZE = 1.0
REPAIR_PERCENT = 5
SIZES = {"scout": 1, "frigate": 2, "destroyer": 6, "cruiser": 12,
         "carrier": 20, "battleship": 25, "titan": 80}
HULL_TECHNOLOGIES = {
    "frigate": None, "destroyer": "destroyer_hulls", "cruiser": "cruiser_hulls",
    "battleship": "battleship_hulls", "carrier": "drone_carriers", "titan": "titan_hulls",
}
STANDARD_LOADOUTS = {
    "frigate": ("laser", "laser"),
    "destroyer": ("torpedo", "torpedo", "point_defense", "escort_array"),
    "cruiser": ("laser", "laser", "torpedo", "point_defense"),
    "battleship": ("laser", "laser", "torpedo", "torpedo", "point_defense"),
    "carrier": ("laser", "point_defense", "drone_bay", "drone_bay"),
    "titan": ("laser", "laser", "torpedo", "torpedo", "point_defense", "point_defense", "flag_bridge"),
}


def scaled(value, percent):
    return math.ceil(value * percent / 100) if value else 0


def hull_values(size, rules=None):
    rules = rules or globals()
    # Round frames to the nearest 10 RES; round labour upward only once.
    cost = max(10, 10 * math.floor(rules["FRAME_RES_PER_SIZE"] * size ** rules["FRAME_COST_EXPONENT"] / 10 + .5))
    return {"hull": size * rules["HULL_PER_SIZE"], "resource_cost": cost,
            "work_cost": max(1, math.ceil(cost * rules["WORK_PER_RESOURCE"])),
            "module_scale": size * 50}


def derive(data):
    """Recalculate a profile's dependent fields without touching active globals."""
    rules = data['rules']['ship_scaling']
    if not rules['ENABLED']:
        return
    for kind, dimensions in data['ship_sizes'].items():
        size = dimensions['size']
        frame = hull_values(size, rules)
        ship = data['ships'][kind]
        ship.update({k: v for k, v in frame.items() if k != 'module_scale'})
        ship['maintenance'] = math.ceil(size * rules['UPKEEP_PER_SIZE'])
        ship['damage'] = ship['drone_bays'] = 0
        if kind not in STANDARD_LOADOUTS:
            continue
        data['hulls'][kind].update(frame)
        ship['movement'] = data['hulls'][kind]['movement']
        for identifier in STANDARD_LOADOUTS[kind]:
            component = data['modules'][identifier]
            for target, source in (('resource_cost', 'resource_cost'), ('work_cost', 'work_cost'),
                                   ('hull', 'hull_bonus'), ('damage', 'damage')):
                ship[target] += scaled(component[source], frame['module_scale'])
            ship['movement'] += component['movement_bonus']
            ship['drone_bays'] += identifier in ('drone_bay', 'interceptor_bay', 'bomber_bay')
        ship['movement'] = max(1, ship['movement'])


def derived_field(section, identifier, field):
    if section == 'ships' and identifier in SIZES:
        return field in ('hull', 'resource_cost', 'work_cost', 'damage', 'drone_bays', 'maintenance') or (
            identifier in STANDARD_LOADOUTS and field == 'movement')
    return section == 'hulls' and field in ('hull', 'resource_cost', 'work_cost', 'module_scale')


def loadout_errors(data):
    if not data['rules']['ship_scaling']['ENABLED']:
        return []
    errors = []
    for kind, loadout in STANDARD_LOADOUTS.items():
        for category, slots in (('weapon', 'offensive_slots'), ('defense', 'defensive_slots'), ('support', 'support_slots')):
            used = sum(data['modules'][m]['category'] == category for m in loadout)
            if used > data['hulls'][kind][slots]:
                errors.append(f'hulls.{kind}.{slots}: the standard loadout requires at least {used} slots; disable ship scaling for manual presets.')
    return errors


def repair_amount(max_hull, minimum):
    return max(minimum, math.ceil(max_hull * REPAIR_PERCENT / 100)) if ENABLED else minimum
