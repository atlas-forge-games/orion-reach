"""Reusable, cached building sprites; original PNGs remain untouched."""

from functools import lru_cache
import pygame as pg

from .ui import ASSETS

BUILDING_ART_IDS = ("headquarters", "factory", "shipyard", "research_lab", "trade_center", "mine")


@lru_cache(maxsize=6)
def load_building_art(building_id):
    if building_id not in BUILDING_ART_IDS:
        raise ValueError(f"Unknown building artwork: {building_id}")
    try:
        image = pg.image.load(str(ASSETS / "buildings" / f"{building_id}-v1.png"))
        # Exclude faint transparent margins when aligning each foundation.
        bounds = image.get_bounding_rect(min_alpha=32)
        if not bounds.w or not bounds.h:
            return None
        return image.subsurface(bounds).copy()
    except (OSError, pg.error):
        return None


def fallback_building(building_id):
    """Keep buildings recognizable and selectable when an asset is unavailable."""
    image = pg.Surface((120, 110), pg.SRCALPHA)
    roof = [(13, 56), (65, 36), (110, 53), (58, 74)]
    pg.draw.polygon(image, (122, 139, 147), roof)
    pg.draw.polygon(image, (62, 81, 94), [(13, 56), (58, 74), (58, 103), (13, 85)])
    pg.draw.polygon(image, (43, 62, 75), [(58, 74), (110, 53), (110, 82), (58, 103)])
    for x, y in ((22, 68), (38, 74), (67, 78), (84, 71), (100, 65)):
        pg.draw.rect(image, (119, 194, 207), (x, y, 5, 8))
    if building_id in ("headquarters", "mine"):
        pg.draw.rect(image, (151, 167, 170), (53, 9, 19, 55))
        pg.draw.line(image, (119, 194, 207), (62, 13), (62, 56), 3)
    elif building_id == "factory":
        for x in (48, 73):
            pg.draw.rect(image, (140, 151, 156), (x, 17, 10, 40))
    elif building_id == "research_lab":
        pg.draw.circle(image, (107, 164, 193), (62, 43), 24)
    elif building_id == "shipyard":
        pg.draw.rect(image, (14, 30, 42), (64, 73, 26, 18))
    return image


@lru_cache(maxsize=96)
def building_sprite(building_id, size):
    source = load_building_art(building_id)
    if source is None:
        source = fallback_building(building_id)
    fit = source.get_rect().fit(pg.Rect((0, 0), size))
    return pg.transform.smoothscale(source, fit.size)


def draw_building_art(surface, building_id, rect, *, alpha=255):
    rect = pg.Rect(rect)
    sprite = building_sprite(building_id, rect.size)
    if alpha != 255:
        sprite = sprite.copy()
        sprite.set_alpha(alpha)
    placed = sprite.get_rect(midbottom=rect.midbottom)
    surface.blit(sprite, placed)
    return placed
