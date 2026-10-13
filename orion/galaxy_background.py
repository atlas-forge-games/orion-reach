"""Cached, purely decorative artwork behind the galaxy map."""

from functools import lru_cache
from math import ceil

import pygame as pg

from .ui import ASSETS, panel

BACKGROUND_PATH = ASSETS / "backgrounds" / "galaxy-v1.png"
MAP_COLOR = (7, 17, 25)


@lru_cache(maxsize=4)
def map_artwork(size):
    """Cover the map without stretching; load and dim only once per size."""
    try:
        source = pg.image.load(str(BACKGROUND_PATH)).convert_alpha()
    except (OSError, pg.error):
        return None
    scale = max(size[0] / source.get_width(), size[1] / source.get_height())
    scaled = pg.transform.smoothscale(source, (ceil(source.get_width() * scale),
                                              ceil(source.get_height() * scale)))
    scaled.set_alpha(205)
    result = pg.Surface(size).convert()
    result.fill(MAP_COLOR)
    result.blit(scaled, scaled.get_rect(center=result.get_rect().center))
    return result


@lru_cache(maxsize=1)
def camera_artwork(size, zoom, offset_x, offset_y):
    image = map_artwork(size)
    if image is None:
        return None
    width, height = size
    source = pg.Rect(round(width/2-(width/2+offset_x)/zoom),
                     round(height/2-(height/2+offset_y)/zoom),
                     max(1, round(width/zoom)), max(1, round(height/zoom)))
    source.clamp_ip(image.get_rect())
    return pg.transform.smoothscale(image.subsurface(source), size)


def draw_galaxy_background(surface, rect, enabled=True, camera=None):
    """Retain the plain map when disabled or when the optional image is absent."""
    panel(surface, rect, MAP_COLOR)
    if enabled:
        interior = pg.Rect(rect).inflate(-4, -4)
        zoomed = camera is not None and camera.zoom > 1
        image = (camera_artwork(rect.size, camera.zoom, camera.offset_x, camera.offset_y) if zoomed else
                 map_artwork(interior.size))
        if image is not None:
            clip = surface.get_clip()
            surface.set_clip(clip.clip(interior))
            surface.blit(image, rect if zoomed else interior)
            surface.set_clip(clip)
