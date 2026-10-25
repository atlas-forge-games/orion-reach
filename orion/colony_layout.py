"""Stable, saved surface sites; pure geometry independent of the renderer."""

from functools import lru_cache
import math

from .buildings import BUILDINGS, ADVANCED_FACILITIES, facility_family

WIDTH, HEIGHT = 1392, 406
MIN_BOTTOM = 180

PLACEMENTS = {
    "space_hub": (508, 341, 138, 90),
    "research_lab": (212, 280, 174, 142),
    "headquarters": (378, 280, 177, 169),
    "factory": (545, 280, 218, 145),
    "hydroponic_farm": (711, 280, 157, 144),
    "mine": (238, 402, 168, 146),
    "trade_center": (460, 402, 187, 146),
    "shipyard": (681, 402, 248, 148),
    "barracks": (348, 341, 140, 58),
    "fortifications": (565, 341, 124, 58),
    "missile_base": (160, 333, 84, 86),
    "planetary_shield": (292, 333, 86, 87),
    "sensor_array": (444, 334, 88, 90),
    "jump_gate": (639, 336, 82, 94),
    "interdictor": (752, 337, 85, 94),
    "solar_array": (164, 392, 115, 85),
    "fusion_plant": (768, 402, 105, 111),
    "geothermal_plant": (375, 406, 105, 100),
    "thermal_plant": (560, 409, 110, 100),
    "singularity_plant": (712, 413, 112, 105),
}
from .race_victory import PROJECT_RACES
for _identifier in PROJECT_RACES:
    PLACEMENTS[_identifier] = (460, 380, 150, 120)

PLACEMENTS.update({identifier: PLACEMENTS[facility_family(identifier)] for identifier in ADVANCED_FACILITIES})


def preferred(identifier):
    x, bottom, width, height = PLACEMENTS[identifier]
    scale = HEIGHT / 473
    if identifier not in ('headquarters', 'shipyard'):
        # Leave room for the entire normal colony from its first building.
        # Landmarks retain their original size and anchor points.
        scale = min(scale, 155/width, 90/height)
        bottom = MIN_BOTTOM if bottom < 360 else HEIGHT-38
    else:
        bottom = round(bottom * scale)
    return round(x * WIDTH / 928), bottom, round(width * scale), round(height * scale)


def footprint(site):
    x, bottom, width, height = site
    return x-width//2-12, bottom-height, width+24, height+38


def overlap(a, b):
    ax, ay, aw, ah = footprint(a)
    bx, by, bw, bh = footprint(b)
    return ax < bx+bw and bx < ax+aw and ay < by+bh and by < ay+ah


def inside(site):
    x, y, width, height = footprint(site)
    return x >= 0 and y >= 36 and x+width <= WIDTH and y+height <= HEIGHT and site[1] >= MIN_BOTTOM


def at_point(identifier, point):
    _, _, width, height = preferred(identifier)
    x, bottom = point
    return (round(max(width//2+12, min(WIDTH-(width+1)//2-12, x))),
            round(max(MIN_BOTTOM, height+36, min(HEIGHT-38, bottom))), width, height)


def available(site, occupied):
    return inside(site) and not any(overlap(site, other) for other in occupied)


def automatic_site(identifier, occupied):
    preferred_site = preferred(identifier)
    if available(preferred_site, occupied):
        return preferred_site
    cx, bottom, width, height = preferred_site
    rows = [(x, y) for y in (MIN_BOTTOM, HEIGHT-38) for x in range(24, WIDTH-23, 16)]
    rows += [(cx, y) for y in (MIN_BOTTOM, HEIGHT-38)]
    gaps = [(x, y) for y in range(MIN_BOTTOM, HEIGHT-37, 12) for x in range(24, WIDTH-23, 16)]
    for points in (rows, gaps):
        points.sort(key=lambda point: (point[0]-cx)**2 + (point[1]-bottom)**2)
    # Only a new structure may need a smaller footprint in a crowded colony.
    # Existing structures retain their saved position AND size.
    for factor in (1, .9, .8, .7, .6, .5, .4, .3, .2):
        w, h = max(24, round(width*factor)), max(18, round(height*factor))
        for x, y in rows + gaps:
            site = (x, y, w, h)
            if available(site, occupied):
                return site
    raise ValueError("No free surface site remains. Free space before adding another building.")


@lru_cache(maxsize=256)
def _layout(identifiers, saved):
    previous = dict(saved)
    result = {key: previous[key] for key in identifiers if key in previous}
    for key in identifiers:
        if key not in result:
            try:
                result[key] = automatic_site(key, tuple(result.values()))
            except ValueError:
                # Keep even impossible, over-capacity debug scenes inspectable.
                result[key] = at_point(key, preferred(key)[:2])
    return tuple(result.items())


def layout(identifiers, saved):
    """Return a new mapping without modifying the planet or the cached result."""
    return {key: list(site) for key, site in _layout(tuple(identifiers),
            tuple(sorted((key, tuple(site)) for key, site in saved.items())))}


def identifiers(game, system_id, planet):
    if not planet.colonized or planet.habitat:
        return []
    home = game.headquarters(planet.owner)
    headquarters = bool(home and (system_id, planet.id) == (home[0].id, home[1].id))
    present = set(planet.buildings) | {p.item_id for _, p in planet.building_projects}
    return (["headquarters"] if headquarters else []) + ["shipyard"] + [key for key in BUILDINGS if key in present]


def freeze(game, system_id, planet):
    if planet.colonized and not planet.habitat:
        planet.surface_layout = layout(identifiers(game, system_id, planet), planet.surface_layout)


def reserve(game, system_id, planet, identifier, point=None):
    """Prepare a site before queuing an order, leaving failures fully atomic."""
    existing = layout(identifiers(game, system_id, planet), planet.surface_layout)
    if point is None:
        site = automatic_site(identifier, tuple(existing.values()))
    else:
        if (not isinstance(point, (list, tuple)) or len(point) != 2
                or any(type(n) not in (int, float) or not math.isfinite(n) for n in point)
                or not 0 <= point[0] <= WIDTH or not MIN_BOTTOM <= point[1] <= HEIGHT):
            raise ValueError("Choose a construction site on the foreground.")
        site = at_point(identifier, point)
        if not available(site, tuple(existing.values())):
            raise ValueError("That site overlaps another building or its inspection area. Choose open ground.")
    return {**existing, identifier: list(site)}


def validate(record, version):
    saved = record.get('surface_layout', {}) if version >= 58 else {}
    if (not isinstance(saved, dict) or len(saved) > len(PLACEMENTS)
            or any(key not in PLACEMENTS or not isinstance(site, (list, tuple)) or len(site) != 4
                   or any(type(n) is not int for n in site)
                   or not 1 <= site[2] <= WIDTH or not 1 <= site[3] <= HEIGHT or not inside(site)
                   for key, site in saved.items())):
        raise ValueError("Invalid colony surface layout")
    if saved and (not record['colonized'] or record.get('habitat')):
        raise ValueError("Only surface colonies have building sites")
    sites = list(saved.values())
    if any(overlap(a, b) for i, a in enumerate(sites) for b in sites[i+1:]):
        raise ValueError("Overlapping colony building sites")
    record['surface_layout'] = {key: list(site) for key, site in saved.items()}

