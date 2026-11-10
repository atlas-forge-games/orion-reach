"""Compact faction-colored fleets, drawn at their final pixel size."""

from functools import lru_cache
import math
import pygame as pg

from .ui import ASSETS
from .model import PLAYER
from .display import Canvas

ICON_BOX = 28
# Keep the generous click target while reducing the visible artwork by 30%.
ART_SIZE = 24 * .7


def visible_course(app, ship):
    """Keep map lines and icon placement from revealing queued enemy orders."""
    return ship.has_course and (ship.owner == PLAYER or app.game.is_observer or not app.game.fog_of_war)


def flight_heading(app, ship):
    """Clockwise degrees from north, measured in the displayed map coordinates."""
    if not visible_course(app, ship):
        return 0.0
    start = app.star_pos(app.game.systems[ship.system_id])
    end = app.star_pos(app.game.systems[ship.destination])
    return math.degrees(math.atan2(end[0]-start[0], start[1]-end[1])) % 360


@lru_cache(maxsize=2)
def icon_master(habitat=False):
    path = ASSETS / ("ships/mothership-v1.png" if habitat else "map/fleet-icon-v1.png")
    try:
        image = pg.image.load(str(path))
        bounds = image.get_bounding_rect(min_alpha=32)
        if not bounds.w or not bounds.h:
            return None
        image = image.subsurface(bounds).copy()
        scale = 256/max(image.get_size())
        return pg.transform.smoothscale(image, (max(1, round(image.get_width()*scale)),
                                               max(1, round(image.get_height()*scale))))
    except (OSError, pg.error):
        return None


def fallback_art(color, habitat):
    """Keep fleets visible even if an installation is missing its PNG files."""
    image = pg.Surface((32, 40), pg.SRCALPHA)
    points = ([(16, 2), (28, 14), (30, 30), (16, 36), (2, 30), (4, 14)] if habitat else
              [(16, 1), (21, 19), (29, 31), (19, 28), (19, 38),
               (13, 38), (13, 28), (3, 31), (11, 19)])
    pg.draw.polygon(image, color, points)
    return image


@lru_cache(maxsize=32)
def accented_master(color, habitat=False):
    master = icon_master(habitat)
    if master is None:
        return fallback_art(color, habitat)
    master = master.copy()
    # Tint the entire hull: engine lights alone vanish at galaxy-map scale.
    # Retain the source shading and a little neutral specular light so both
    # ordinary ships and motherships keep their illustrated details.
    for x in range(master.get_width()):
        for y in range(master.get_height()):
            r, g, b, alpha = master.get_at((x, y))
            if alpha:
                light = max(r, g, b)/255
                highlight = max(0, (light-.82)/.18)*.18
                tint = tuple(round((channel*(1-highlight)+255*highlight)*light) for channel in color)
                master.set_at((x, y), (*tint, alpha))
    if not habitat:
        # Keep the two aft lights legible after reduction to a compact icon.
        width, height = master.get_size()
        for fraction in (.42, .62):
            center = (round(width*fraction), round(height*.95))
            pg.draw.circle(master, color, center, max(1, round(height*.035)))
            light = tuple(round(channel*.5+127) for channel in color)
            pg.draw.circle(master, light, center, max(1, round(height*.012)))
    return master


@lru_cache(maxsize=384)
def icon_sprite(color, habitat=False, heading=0, pixels=ICON_BOX):
    master = accented_master(color, habitat)
    rotated = pg.transform.rotozoom(master, -heading, 1)
    bounds = rotated.get_bounding_rect(min_alpha=32)
    if bounds.w and bounds.h:
        rotated = rotated.subsurface(bounds).copy()
    scale = (ART_SIZE*pixels/ICON_BOX)/max(rotated.get_size())
    size = (max(1, round(rotated.get_width()*scale)), max(1, round(rotated.get_height()*scale)))
    artwork = pg.transform.smoothscale(rotated, size)
    sprite = pg.Surface((pixels, pixels), pg.SRCALPHA)
    rect = artwork.get_rect(center=(pixels//2, pixels//2))
    sprite.blit(artwork, rect)
    return sprite


def draw_map_ship(surface, center, color, habitat=False, heading=0):
    # One-degree bins avoid new cache entries from floating-point zoom roundoff.
    scale = surface.scale if isinstance(surface, Canvas) else 1
    sprite = icon_sprite(tuple(color), habitat, round(heading) % 360,
                         max(1, round(ICON_BOX*scale)))
    position = surface.point(center) if isinstance(surface, Canvas) else center
    pg.Surface.blit(surface, sprite, sprite.get_rect(center=position))
