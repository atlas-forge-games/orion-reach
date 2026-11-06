"""Small luminous stars and survey-aware ownership rings at native resolution."""

from functools import lru_cache
from math import exp, pi
import pygame as pg

from .display import Canvas

MARKER_BOX = 44


@lru_cache(maxsize=384)
def star_sprite(color, known=True, owners=(), selection=None, outpost=None, pixels=MARKER_BOX):
    # Supersample the small curves once per cached style/scale, not the map.
    samples = 3
    size = pixels*samples
    scale = size/MARKER_BOX
    center = (size//2, size//2)
    image = pg.Surface((size, size), pg.SRCALPHA)
    brightness = 1.0 if known else .85
    tint = tuple(round(c*brightness) for c in color)
    for radius in range(round(11*scale), 0, -1):
        alpha = round(90*exp(-((radius/scale)/5.0)**2))
        pg.draw.circle(image, (*tint, alpha), center, radius)
    pg.draw.circle(image, (*tint, 245), center, round(3.5*scale))
    core = tuple(round((c*.3+255*.7)*brightness) for c in color)
    pg.draw.circle(image, core, center, round(2.4*scale))
    pg.draw.circle(image, tuple(round(255*brightness) for _ in range(3)), center, round(1.3*scale))

    radius, stroke = round(11*scale), max(1, round(1.3*scale))
    ring = pg.Rect(0, 0, radius*2, radius*2)
    ring.center = center
    if len(owners) == 1:
        pg.draw.circle(image, owners[0], center, radius, stroke)
    elif owners:
        sweep = 2*pi/len(owners)
        gap = min(.10, sweep*.15)
        for index, owner in enumerate(owners):
            start = pi/2+index*sweep
            pg.draw.arc(image, owner, ring, start+gap/2, start+sweep-gap/2, stroke)
    if outpost:
        rect = pg.Rect(0, 0, round(7*scale), round(5*scale))
        rect.midtop = (center[0], center[1]+round(14*scale))
        pg.draw.rect(image, outpost, rect, max(1, round(scale)))
    if selection:
        outer, inner = round(18*scale), round(12*scale)
        for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            corner = (center[0]+dx*outer, center[1]+dy*outer)
            points = [(center[0]+dx*inner, corner[1]), corner,
                      (corner[0], center[1]+dy*inner)]
            pg.draw.lines(image, selection, False, points, max(1, round(1.2*scale)))
    return pg.transform.smoothscale(image, (pixels, pixels))


def draw_atlas_star(surface, center, color, known=True, owners=(), selection=None, outpost=None):
    scale = surface.scale if isinstance(surface, Canvas) else 1
    sprite = star_sprite(tuple(color), known, tuple(owners), selection, outpost,
                         max(1, round(MARKER_BOX*scale)))
    position = surface.point(center) if isinstance(surface, Canvas) else center
    # The sprite already has its final display size. Bypass Canvas's image scaling.
    pg.Surface.blit(surface, sprite, sprite.get_rect(center=position))
