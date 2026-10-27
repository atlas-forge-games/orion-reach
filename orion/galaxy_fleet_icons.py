"""Cached illustrated map icons with faction rims and arbitrary flight headings."""

from functools import lru_cache
import math
import pygame as pg

from .ui import ASSETS

ICON_BOX = 22
ART_SIZE = 18


def flight_heading(app, ship):
    """Clockwise degrees from north, measured in the displayed map coordinates."""
    if not ship.in_transit or ship.destination is None:
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
        scale = 128/max(image.get_size())
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


@lru_cache(maxsize=384)
def icon_sprite(color, habitat=False, heading=0):
    master = icon_master(habitat)
    if master is None:
        master = fallback_art(color, habitat)
    rotated = pg.transform.rotozoom(master, -heading, 1)
    bounds = rotated.get_bounding_rect(min_alpha=32)
    if bounds.w and bounds.h:
        rotated = rotated.subsurface(bounds).copy()
    scale = ART_SIZE/max(rotated.get_size())
    size = (max(1, round(rotated.get_width()*scale)), max(1, round(rotated.get_height()*scale)))
    artwork = pg.transform.smoothscale(rotated, size)
    outline = pg.mask.from_surface(artwork, 32).to_surface(
        setcolor=(*color, 255), unsetcolor=(0, 0, 0, 0))
    sprite = pg.Surface((ICON_BOX, ICON_BOX), pg.SRCALPHA)
    rect = artwork.get_rect(center=(ICON_BOX//2, ICON_BOX//2))
    for offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        sprite.blit(outline, rect.move(offset))
    sprite.blit(artwork, rect)
    return sprite


def draw_map_ship(surface, center, color, habitat=False, heading=0):
    # One-degree bins avoid new cache entries from floating-point zoom roundoff.
    sprite = icon_sprite(tuple(color), habitat, round(heading) % 360)
    surface.blit(sprite, sprite.get_rect(center=center))
