"""Native-resolution planet backgrounds, separate from clickable buildings."""

from functools import lru_cache

import pygame as pg

from .ui import ASSETS


SURFACE_FILES = {
    biome: f"{biome.lower()}-v1.png"
    for biome in ("Terran", "Gaia", "Ocean", "Desert", "Ice", "Barren", "Volcanic", "Toxic")
}
SURFACE_FILES['Gas Giant'] = 'gas-giant-v1.png'


@lru_cache(maxsize=9)
def load_surface_art(biome):
    """Keep the original pixels; missing optional art uses the seeded fallback."""
    filename = SURFACE_FILES.get(biome)
    if filename is None:
        return None
    try:
        return pg.image.load(str(ASSETS / "planet_surfaces" / filename))
    except (OSError, pg.error):
        return None


def cover_crop(source_size, target_size):
    """Crop centrally to the viewport ratio without stretching the landscape."""
    width, height = source_size
    target_width, target_height = target_size
    scale = max(target_width / width, target_height / height)
    crop = pg.Rect(0, 0, max(1, round(target_width / scale)),
                   max(1, round(target_height / scale)))
    crop.center = width // 2, height // 2
    return crop.clip(pg.Rect(0, 0, width, height))


@lru_cache(maxsize=27)
def surface_background(biome, size):
    """Scale once from the source, sharing cached backgrounds between colonies."""
    original = load_surface_art(biome)
    if original is None:
        return None
    crop = cover_crop(original.get_size(), size)
    return pg.transform.smoothscale(original.subsurface(crop), size)
