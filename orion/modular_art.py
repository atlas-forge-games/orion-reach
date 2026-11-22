"""One loadout-based ship illustration for the designer, fleets and combat.

Artwork remains in its original PNG files. Atlas cells are extracted only in
memory. Mount coordinates are measured on those same images, so the equipment
and the designer's hit regions cannot drift apart when the window is resized.
"""

from functools import lru_cache
import pygame as pg

from .designs import HULLS, MODULES, DRONE_BAYS
from .ship_fitting import arrange
from .ui import ASSETS

ROOT = ASSETS / "ships" / "modular"
KINDS = ("frigate", "destroyer", "cruiser", "battleship", "carrier", "titan")

# Rectangles use the original PNG coordinates, including the capital atlas.
# The atlas crop excludes the catalogue labels; all input bytes are unchanged.
SOURCES = {
    "frigate": ("frigate-v1.png", None),
    "destroyer": ("destroyer-v1.png", None),
    "cruiser": ("cruiser-v1.png", None),
    "battleship": ("capital-hulls-v1.png", (0, 0, 650, 830)),
    "carrier": ("capital-hulls-v1.png", (660, 0, 450, 830)),
    "titan": ("capital-hulls-v1.png", (1110, 0, 664, 830)),
}
LAYOUTS = {
    "frigate": {
        "weapon": ((441, 690, 47, 64), (765, 690, 47, 64),
                   (383, 777, 47, 68), (824, 777, 47, 68)),
        "core": ((589, 514, 76, 181),),
        "engine": ((485, 976, 113, 207), (655, 976, 113, 207)),
        "armor": ((566, 212, 39, 140), (649, 212, 39, 140)),
        "plating": (617, 196),
    },
    "destroyer": {
        "weapon": ((198, 408, 94, 318), (439, 408, 94, 318),
                   (125, 1027, 65, 96), (537, 1027, 65, 96)),
        "core": ((329, 1087, 73, 194),),
        "engine": ((105, 1720, 180, 347), (439, 1720, 180, 347)),
        "armor": ((224, 284, 57, 98), (446, 284, 57, 98)),
        "plating": (274, 245),
    },
    "cruiser": {
        "weapon": ((354, 497, 91, 91), (584, 497, 91, 91),
                   (354, 728, 91, 91), (584, 728, 91, 91)),
        "core": ((490, 477, 45, 88), (485, 593, 55, 124),
                 (485, 752, 55, 116)),
        "engine": ((307, 1261, 85, 133), (457, 1287, 111, 167), (635, 1261, 85, 133)),
        "armor": ((371, 343, 43, 117), (613, 343, 43, 117)),
        "plating": (513, 198),
    },
    "battleship": {
        "weapon": ((246, 223, 48, 48), (382, 223, 48, 48),
                   (209, 329, 48, 48), (414, 329, 48, 48),
                   (108, 542, 48, 48), (516, 542, 48, 48)),
        "core": ((320, 323, 36, 67), (320, 516, 36, 70)),
        "engine": ((175, 737, 58, 71), (251, 747, 61, 77),
                   (370, 747, 61, 77), (447, 737, 58, 71)),
        "armor": ((267, 139, 29, 69), (381, 139, 29, 69)),
        "plating": (340, 120),
    },
    "carrier": {
        "weapon": ((711, 277, 35, 41), (1024, 277, 35, 41),
                   (704, 569, 36, 39), (1040, 569, 36, 39)),
        "core": ((869, 458, 32, 73),),
        "hangar": ((763, 277, 64, 375), (944, 277, 64, 375)),
        "engine": ((741, 719, 52, 76), (817, 743, 53, 80),
                   (906, 743, 53, 80), (980, 719, 52, 76)),
        "armor": ((786, 179, 27, 58), (958, 179, 27, 58)),
        "plating": (887, 171),
    },
    "titan": {
        "weapon": ((1325, 244, 44, 44), (1480, 244, 44, 44),
                   (1295, 382, 44, 44), (1516, 382, 44, 44),
                   (1233, 561, 44, 44), (1571, 561, 44, 44)),
        "core": ((1410, 212, 33, 82), (1410, 326, 33, 69),
                 (1410, 634, 33, 81)),
        "engine": ((1258, 745, 51, 73), (1328, 745, 51, 73),
                   (1398, 745, 56, 73), (1472, 745, 51, 73), (1544, 745, 51, 73)),
        "armor": ((1367, 132, 20, 74), (1463, 132, 20, 74)),
        "plating": (1460, 170),
    },
}


@lru_cache(maxsize=8)
def image_file(filename):
    try:
        return pg.image.load(str(ROOT / filename))
    except (OSError, pg.error):
        return None


@lru_cache(maxsize=6)
def source(kind):
    """Return a cropped hull and its bounds in the original source file."""
    filename, crop = SOURCES[kind]
    image = image_file(filename)
    if image is None:
        return None, None
    region = pg.Rect(crop) if crop else image.get_rect()
    cell = image.subsurface(region)
    bounds = cell.get_bounding_rect(min_alpha=32)
    if not bounds.w or not bounds.h:
        return None, None
    return cell.subsurface(bounds).copy(), bounds.move(region.topleft)


def counts(kind):
    hull = HULLS[kind]
    return hull.external_mounts, hull.internal_bays, hull.hangar_bays


def fitting(kind, design=None):
    """Resolve stock and old immutable snapshots without modifying game data."""
    if kind not in KINDS:
        return (), ()
    if design is not None:
        return arrange(kind, design.modules, design.mounts)[0], counts(kind)
    from .ship_scaling import STANDARD_LOADOUTS
    return arrange(kind, STANDARD_LOADOUTS[kind])[0], counts(kind)


def mapped_rect(kind, rect, body):
    _, bounds = source(kind)
    if bounds is None:
        return pg.Rect(body)
    x, y, w, h = rect
    return pg.Rect(round(body.x+(x-bounds.x)*body.w/bounds.w),
                   round(body.y+(y-bounds.y)*body.h/bounds.h),
                   max(1, round(w*body.w/bounds.w)), max(1, round(h*body.h/bounds.h)))


def mount_rects(kind, body, limits=None):
    """Exact drawn sockets, shared by sprite assembly and designer input."""
    limits = limits or counts(kind)
    layout, result = LAYOUTS[kind], {}
    for group, total in zip(("weapon", "core", "hangar"), limits):
        locations = layout.get(group, ())
        for i in range(total):
            if i < len(locations):
                rect = mapped_rect(kind, locations[i], body)
            else:
                # Balance-editor profiles may add bays beyond the stock art.
                # Use additional deck locations, without moving existing slots.
                x = (.37 if i % 2 == 0 else .63) if group == "weapon" else .5
                y = .34 if group == "weapon" else (.62 if i == 1 else .74)
                rect = pg.Rect(0, 0, max(15, round(body.w*.13)), max(24, round(body.h*.075)))
                rect.center = (round(body.x+x*body.w), round(body.y+y*body.h))
            result[f"{group}_{i+1}"] = rect
    engines = [mapped_rect(kind, r, body) for r in layout["engine"]]
    result["engine"] = engines[0].unionall(engines[1:])
    x, y = layout["plating"]
    result["armor"] = mapped_rect(kind, (x-14, y-14, 28, 28), body)
    return result


@lru_cache(maxsize=12)
def component(index):
    sheet = image_file("components-v1.png")
    if sheet is None:
        return None
    col, row = index % 4, index // 4
    left, top = col*sheet.get_width()//4, row*sheet.get_height()//3
    right, bottom = (col+1)*sheet.get_width()//4, (row+1)*sheet.get_height()//3
    cell = sheet.subsurface((left, top, right-left, bottom-top))
    bounds = cell.get_bounding_rect(min_alpha=32)
    return cell.subsurface(bounds).copy() if bounds.w and bounds.h else None


def component_index(identifier):
    if identifier == "bay_cover": return 11
    if identifier == "armor": return 9
    if identifier == "reinforced_armor": return 10
    if identifier == "engine": return 8
    if identifier in DRONE_BAYS: return 7
    if identifier in ("point_defense", "flak"): return 2
    if identifier in ("shield", "regenerative_shield", "hardened_shield"): return 4
    if identifier == "damage_control": return 5
    if identifier in ("command_relay", "flag_bridge"): return 6
    if identifier in ("scanner", "ecm_projector", "escort_array"): return 3
    if MODULES[identifier].damage:
        from .weapons import BEAMS
        return 1 if BEAMS[MODULES[identifier].weapon].projectile else 0
    return None


@lru_cache(maxsize=256)
def component_sprite(identifier, width, height, stretch=False):
    index = component_index(identifier)
    image = component(index) if index is not None else None
    if image is None:
        return None
    size = (max(1, width), max(1, height))
    if not stretch:
        size = image.get_rect().fit((0, 0, *size)).size
    return pg.transform.smoothscale(image, size)


def put_component(surface, identifier, rect, *, stretch=False):
    rect = pg.Rect(rect)
    sprite = component_sprite(identifier, rect.w, rect.h, stretch)
    if sprite is not None:
        surface.blit(sprite, sprite.get_rect(center=rect.center))
    else:
        # A missing optional component image must not make fitting invisible.
        pg.draw.rect(surface, (111, 121, 126), rect, border_radius=max(1, rect.w//7))
        pg.draw.rect(surface, (61, 87, 96), rect.inflate(-4, -4), 2)


@lru_cache(maxsize=48)
def assembled(kind, placements, limits, cutaway=False):
    """Cached exterior or designer cutaway, independent of design name/ID."""
    original, _ = source(kind)
    if original is None:
        return None
    # Bound cache memory, retaining enough detail for the enlarged designer.
    height = min(1024, original.get_height())
    image = pg.transform.smoothscale(original, (round(original.get_width()*height/original.get_height()), height))
    body, layout = image.get_rect(), LAYOUTS[kind]
    rects, installed = mount_rects(kind, body, limits), dict(placements)
    if armor := installed.get("armor"):
        for raw in layout["armor"]:
            put_component(image, armor, mapped_rect(kind, raw, body), stretch=True)
    # Every internal bay is closed during play, including unoccupied bays.
    # Extra access trays in the source art remain closed unless configured.
    for i, raw in enumerate(layout["core"]):
        slot = f"core_{i+1}"
        r = mapped_rect(kind, raw, body)
        if not cutaway or slot not in rects:
            put_component(image, "bay_cover", r.inflate(4, 4), stretch=True)
    for i, raw in enumerate(layout["weapon"]):
        if i >= limits[0]:
            put_component(image, "bay_cover", mapped_rect(kind, raw, body), stretch=True)
    for slot, identifier in placements:
        if slot not in rects:
            continue
        r = rects[slot]
        if slot.startswith("weapon_"):
            part = component(component_index(identifier))
            width = round(r.w*1.08)
            height = round(width*part.get_height()/part.get_width()) if part is not None else r.h
            weapon = pg.Rect(0, 0, width, min(height, r.h*2))
            weapon.midbottom = r.midbottom
            put_component(image, identifier, weapon)
        elif slot.startswith("core_") and cutaway:
            put_component(image, identifier, r, stretch=True)
        elif slot.startswith("core_") and int(slot.split("_")[1]) > len(layout["core"]):
            put_component(image, "bay_cover", r, stretch=True)
        elif slot.startswith("hangar_"):
            for fraction in (.22, .50, .78):
                drone = pg.Rect(0, 0, max(1, round(r.w*.70)), max(1, round(r.h*.18)))
                drone.center = (r.centerx, round(r.y+r.h*fraction))
                put_component(image, identifier, drone)
        elif slot == "engine":
            for raw in layout["engine"]:
                put_component(image, identifier, mapped_rect(kind, raw, body), stretch=True)
    return image


def ship_image(kind, design=None, *, cutaway=False, placements=None):
    if kind not in KINDS:
        return None
    fitted, limits = fitting(kind, design)
    return assembled(kind, tuple(placements) if placements is not None else fitted, limits, cutaway)


@lru_cache(maxsize=192)
def scaled(kind, placements, limits, width, height, cutaway=False):
    image = assembled(kind, placements, limits, cutaway)
    if image is None:
        return None
    target = image.get_rect().fit((0, 0, max(1, width), max(1, height)))
    return pg.transform.smoothscale(image, target.size)


def draw(surface, kind, rect, *, design=None, cutaway=False, placements=None):
    """Draw once in native pixels and return the same bounds in layout units."""
    target = surface.rect(rect) if hasattr(surface, "logical_rect") else pg.Rect(rect)
    fitted, limits = fitting(kind, design)
    sprite = scaled(kind, tuple(placements) if placements is not None else fitted, limits,
                    target.w, target.h, cutaway)
    if sprite is None:
        return None
    bounds = sprite.get_rect(center=target.center)
    pg.Surface.blit(surface, sprite, bounds)
    return surface.logical_rect(bounds) if hasattr(surface, "logical_rect") else bounds
