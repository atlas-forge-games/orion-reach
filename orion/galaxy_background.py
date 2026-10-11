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


def draw_galaxy_background(surface, rect, enabled=True):
    """Retain the plain map when disabled or when the optional image is absent."""
    panel(surface, rect, MAP_COLOR)
    if enabled:
        interior = pg.Rect(rect).inflate(-4, -4)
        image = map_artwork(interior.size)
        if image is not None:
            surface.blit(image, interior)
