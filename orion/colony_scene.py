"""Planet landscapes and a clickable city derived from existing colony data."""

from dataclasses import dataclass
from functools import lru_cache
import math
import random
import pygame as pg

from .building_art import draw_building_art
from .buildings import BUILDINGS
from .economy import building_status
from .model import PLAYER, RIVAL
from .empires import empire_color
from .production import SHIP_TYPES
from .ui import CYAN, GOLD, INK, MUTED, RIVAL_COLOR, panel, text, text_image


@dataclass(frozen=True)
class SceneBuilding:
    asset_id: str
    label: str
    completed: int = 0
    queued: int = 0
    slot: int | None = None


def is_headquarters(game, system_id, planet):
    if not planet.colonized or not game.system_visible(system_id):
        return False
    home = game.headquarters(planet.owner)
    return bool(home and (system_id, planet.id) == (home[0].id, home[1].id))


def scene_buildings(game, system_id, planet):
    """One display per type; counts and selection indices reflect real buildings."""
    if not planet.colonized:
        return []
    items = []
    if is_headquarters(game, system_id, planet):
        items.append(SceneBuilding("headquarters", "Headquarters palace", 1))
    ships = sum(project.is_ship for project in planet.construction_queue)
    items.append(SceneBuilding("shipyard", "Shipyard", 1, ships))
    projects = planet.building_projects
    for building_id, spec in BUILDINGS.items():
        built = [i for i, value in enumerate(planet.buildings) if value == building_id]
        queued = [i for i, (_, project) in enumerate(projects) if project.item_id == building_id]
        if built or queued:
            slot = built[0] if built else len(planet.buildings)+queued[0]
            items.append(SceneBuilding(building_id, spec.name, len(built), len(queued), slot))
    return items


# Sky, horizon, distant ridge, ground, foreground. No new gameplay biome rules.
PALETTES = {
    "Terran": ((31, 64, 87), (143, 179, 181), (58, 90, 92), (63, 85, 64), (29, 47, 42)),
    "Gaia": ((21, 81, 101), (164, 214, 191), (52, 122, 111), (60, 128, 80), (23, 69, 51)),
    "Ocean": ((27, 66, 102), (139, 190, 206), (49, 103, 130), (35, 91, 123), (17, 47, 72)),
    "Desert": ((72, 71, 83), (211, 174, 125), (126, 104, 83), (155, 123, 79), (87, 72, 52)),
    "Tundra": ((54, 81, 108), (194, 213, 220), (111, 144, 162), (167, 186, 190), (93, 121, 137)),
    "Barren": ((12, 19, 34), (67, 75, 94), (57, 62, 72), (90, 90, 91), (48, 51, 62)),
    "Volcanic": ((41, 26, 35), (148, 82, 59), (82, 52, 53), (70, 59, 58), (32, 34, 42)),
}


def blend(a, b, value):
    return tuple(round(x+(y-x)*value) for x, y in zip(a, b))


@lru_cache(maxsize=24)
def landscape(biome, seed, size, settled):
    """A seeded backdrop, cached independently from buildings and queue state."""
    if size != (928, 473):
        return pg.transform.smoothscale(landscape(biome, seed, (928, 473), settled), size)
    width, height = size
    image = pg.Surface(size)
    rng = random.Random(seed)
    sky, horizon, ridge, ground, foreground = PALETTES[biome]
    skyline = round(height*.34)
    for y in range(height):
        color = (blend(sky, horizon, min(1, y/skyline)) if y < skyline
                 else blend(ground, foreground, (y-skyline)/(height-skyline)))
        pg.draw.line(image, color, (0, y), (width, y))
    # Distant world silhouettes and a soft atmospheric light source.
    if biome not in ("Barren", "Volcanic"):
        glow = pg.Surface(size, pg.SRCALPHA)
        for radius in range(36, 3, -2):
            pg.draw.circle(glow, (*horizon, 4+round(36-radius)), (round(width*.83), 77), radius)
        image.blit(glow, (0, 0))
    else:
        for _ in range(40):
            pg.draw.circle(image, (128, 141, 156), (rng.randrange(width), rng.randrange(18, 90)), 1)
    for layer in range(3):
        points = [(0, skyline+28+layer*13)]
        for x in range(0, width+61, 60):
            points.append((x, skyline+layer*14-rng.randrange(10, 62-layer*13)))
        points.extend([(width, skyline+57), (0, skyline+57)])
        pg.draw.polygon(image, blend(horizon, ridge, .4+layer*.22), points)
    # Fine surface texture stays quiet behind the imported architecture.
    for _ in range(1100):
        x, y = rng.randrange(width), rng.randrange(skyline+28, height)
        shade = blend(ground, foreground, rng.random())
        pg.draw.line(image, shade, (x, y), (x+rng.randrange(1, 5), y))
    if biome == "Ocean":
        for y in range(skyline+33, height, 15):
            for _ in range(8):
                x = rng.randrange(width)
                pg.draw.line(image, (68, 121, 143), (x, y), (x+rng.randrange(8, 48), y))
        if settled:
            pg.draw.polygon(image, (68, 82, 86), [(35, 190), (width-60, 186), (width, height), (0, height)])
            pg.draw.lines(image, (135, 153, 153), False, [(0, height-1), (35, 190), (width-60, 186)], 3)
    if biome == "Volcanic":
        for start in (80, width-180):
            points = [(start+math.sin(i*1.6)*32, skyline+35+i*24) for i in range(13)]
            pg.draw.lines(image, (137, 69, 47), False, points, 4)
            pg.draw.lines(image, (215, 119, 60), False, points, 1)
    elif biome in ("Barren", "Desert"):
        for _ in range(14):
            x, y = rng.randrange(width), rng.randrange(skyline+28, height)
            pg.draw.ellipse(image, blend(ground, foreground, .55), (x, y, rng.randrange(14, 58), 7), 1)
    if settled:
        # Service roads connect the colony's developed areas.
        for bottom in (216, 404):
            points = [(165, bottom-4), (464, bottom-4), (762, bottom-4)]
            pg.draw.lines(image, (70, 77, 76), False, points, 19)
            pg.draw.lines(image, (44, 52, 54), False, points, 11)
            for x in range(191, 754, 52):
                pg.draw.line(image, (136, 151, 146), (x, bottom-4), (x+14, bottom-4), 1)
        pg.draw.line(image, (70, 77, 76), (464, 211), (464, height), 24)
        pg.draw.line(image, (44, 52, 54), (464, 211), (464, height), 16)
    if biome in ("Terran", "Gaia"):
        for _ in range(36):
            x = rng.choice((rng.randrange(4, 41), rng.randrange(width-38, width-3)))
            y = rng.randrange(skyline+50, height-10)
            pg.draw.line(image, (56, 58, 44), (x, y), (x, y+9), 2)
            pg.draw.polygon(image, (40, 65, 48), [(x-6, y+2), (x, y-13), (x+6, y+2)])
    return image


# Positions match the road foundations; sprites stay large enough to read.
PLACEMENTS = {
    "research_lab": (130, 211, 174, 142),
    "headquarters": (354, 211, 177, 169),
    "factory": (579, 211, 218, 145),
    "hydroponic_farm": (803, 211, 157, 144),
    "mine": (165, 399, 168, 146),
    "trade_center": (464, 399, 187, 146),
    "shipyard": (762, 399, 248, 148),
    "barracks": (314, 305, 140, 58),
    "fortifications": (606, 305, 124, 58),
    "missile_base": (60, 292, 84, 86),
    "planetary_shield": (238, 292, 86, 87),
    "sensor_array": (443, 294, 88, 90),
    "jump_gate": (706, 297, 82, 94),
    "interdictor": (859, 299, 85, 94),
    "solar_array": (65, 383, 115, 85),
    "fusion_plant": (880, 398, 105, 111),
}


def draw_colony_scene(app, rect, game, system, planet, *, framed=True):
    surface = app.canvas
    rect = pg.Rect(rect)
    old_clip = surface.get_clip()
    surface.set_clip(rect.clip(old_clip))
    seed = f"{game.seed}:{system.id}:{planet.id}"
    surface.blit(landscape(planet.biome, seed, rect.size, planet.colonized), rect)
    if framed:
        pg.draw.rect(surface, (10, 20, 29), (rect.x, rect.y, rect.w, 35))
        text(surface, "PLANET SURFACE", (rect.x+18, rect.y+12), 10, GOLD, "mono", 2)
    summary = (f"{len(planet.buildings)} built · {len(planet.building_projects)} queued / {planet.building_capacity} slots"
               if planet.colonized else f"{planet.biome.upper()} · UNSETTLED")
    if framed:
        text(surface, summary, (rect.right-18, rect.y+11), 11, INK, "mono", right=True)
    items = sorted(scene_buildings(game, system.id, planet), key=lambda item: PLACEMENTS[item.asset_id][1])
    expanded = any(item.asset_id in ("missile_base", "planetary_shield", "sensor_array", "jump_gate", "interdictor") for item in items)
    for index, item in enumerate(items):
        cx, bottom, width, height = ((88+index%5*188, 163+index//5*130, 128, 90) if expanded else PLACEMENTS[item.asset_id])
        scale = min(rect.w/928, rect.h/473)
        cx, bottom = round(cx*rect.w/928), round(bottom*rect.h/473)
        width, height = round(width*scale), round(height*scale)
        target = pg.Rect(rect.x+cx-width//2, rect.y+bottom-height, width, height)
        hit = target.inflate(24, 0)
        hit.h += 38
        if item.asset_id == "headquarters":
            action = app.open_empire if planet.owner == PLAYER else app.open_rival
            caption = "Empire overview" if planet.owner == PLAYER else "Rival report"
        elif item.asset_id == "shipyard":
            action = lambda: app.open_shipyard(system.id, planet.id)
            caption = f"{item.queued} {'ship' if item.queued == 1 else 'ships'} queued" if item.queued else "Open shipyard"
        else:
            action = lambda slot=item.slot: app.inspect_surface_building(slot)
            caption = f"{item.queued} queued" if item.queued else "Click to inspect"
        live = game.system_visible(system.id)
        if item.completed and item.slot is not None and live:
            status = building_status(planet, item.slot, game.bonuses_for(planet.owner))
            if status != "OPERATIONAL":
                caption = status
        if not live:
            caption = "Last observed"
        button = app.button("surface_"+item.asset_id, "", hit, action, "hotspot", enabled=live)
        active = app.is_active(button)
        color = GOLD if active or not item.completed else empire_color(planet.owner)
        pg.draw.ellipse(surface, (29, 39, 41), (target.x+5, target.bottom-19, target.w-10, 23))
        if not item.completed:
            pg.draw.ellipse(surface, GOLD, (target.x, target.bottom-24, target.w, 29), 1)
        draw_building_art(surface, item.asset_id, target, alpha=255 if item.completed else 115)
        label = item.label+(f" ×{item.completed}" if item.completed > 1 else "")
        name_image = text_image(label, 12, INK)
        caption_image = text_image(caption, 10, color)
        label_width = max(name_image.get_width(), caption_image.get_width())+18
        label_box = pg.Rect(0, 0, label_width, 34)
        label_box.midtop = target.centerx, target.bottom+3
        if framed or active or item.queued:
            panel(surface, label_box, (11, 24, 31), color if active else (48, 64, 69))
            surface.blit(name_image, name_image.get_rect(midtop=(target.centerx, label_box.y+3)))
            surface.blit(caption_image, caption_image.get_rect(midtop=(target.centerx, label_box.y+19)))
        elif item.completed > 1:
            text(surface, f"×{item.completed}", (target.centerx-10, target.bottom+5), 16, INK)
    if not planet.colonized:
        left, top = rect.centerx-226, rect.y+round(rect.h*.51)
        panel(surface, (left, top, 452, 94), (15, 29, 38))
        text(surface, "No colony established", (left+23, top+16), 25, INK, "title")
        hint = "Bring a colony ship to settle this world." if game.can_settle(planet) else "Research protective habitats to settle this world."
        text(surface, hint, (left+23, top+64), 13, MUTED)
    if framed:
        pg.draw.rect(surface, (10, 20, 29), (rect.x, rect.bottom-35, rect.w, 35))
    footer = "Palace and shipyard use no building slots. Repeated building types show a count."
    if planet.owner in game.opponents:
        footer = "Rival colony · survey only. Click a building to inspect its production."
    elif not planet.colonized:
        footer = "Survey the environment, then use Colonize when a colony ship is ready."
    if not game.system_visible(system.id):
        footer = "Stored survey · Buildings and ownership reflect the last observation. Send a ship to update."
    if framed:
        text(surface, footer, (rect.x+18, rect.bottom-24), 12, INK)
    pg.draw.rect(surface, (38, 57, 68), rect, 1)
    surface.set_clip(old_clip)
