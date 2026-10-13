"""Cached portraits for named specialists; absent artwork uses a quiet monogram."""
from functools import lru_cache
import pygame as pg
from .ui import ASSETS, CYAN, LINE, panel, text

PORTRAITS = {"mara_voss": "mara_voss-v1.png", "orun_basalt": "orun_basalt-v1.png"}


@lru_cache(maxsize=2)
def load_portrait(identifier):
    if identifier not in PORTRAITS:
        return None
    try:
        return pg.image.load(str(ASSETS / "specialists" / PORTRAITS[identifier]))
    except (OSError, pg.error):
        return None


@lru_cache(maxsize=32)
def scaled_portrait(identifier, size):
    image = load_portrait(identifier)
    return pg.transform.smoothscale(image, size) if image is not None else None


def draw_portrait(surface, spec, rect):
    rect = pg.Rect(rect)
    portrait = scaled_portrait(spec.id, rect.size)
    if portrait is not None:
        surface.blit(portrait, rect)
        pg.draw.rect(surface, LINE, rect, 1)
    else:
        panel(surface, rect, (17, 35, 45))
        initials = "".join(word[0] for word in spec.name.split()[:2])
        size = max(12, rect.w//3)
        text(surface, initials, (rect.x+rect.w//5, rect.y+(rect.h-size)//2), size, CYAN, "mono")
