"""Radiant stars with steady cores, slow halos and survey-aware ownership rings."""

from functools import lru_cache
from math import cos, exp, pi, sin, sqrt
import pygame as pg

from .display import Canvas

MARKER_BOX = 44


def star_zoom_scale(zoom):
    """Grow more slowly than system distances, without changing UI text or ships."""
    return min(2.0, max(.75, sqrt(max(0, zoom))))


def star_hit_radius(zoom):
    return round(18*star_zoom_scale(zoom))


def pulse_alpha(star_id, time, animated=True):
    if not animated:
        return 220
    period = 4+(star_id*17 % 21)/10
    phase = star_id*2.39996323
    return round(220*(1+.15*sin(2*pi*time/period+phase)))


@lru_cache(maxsize=256)
def glow_sprite(color, known=True, pixels=MARKER_BOX, variant=0):
    """Cache geometry only; changing a halo's opacity never creates a new sprite."""
    samples = 3
    size = pixels*samples
    scale = size/MARKER_BOX
    center = (size//2, size//2)
    image = pg.Surface((size, size), pg.SRCALPHA)
    brightness = 1.0 if known else .85
    tint = tuple(round(c*brightness) for c in color)
    for radius in range(round(21*scale), 0, -1):
        r = radius/scale
        alpha = round(108*exp(-(r/6.5)**2)+18*exp(-(r/11.5)**2))
        pg.draw.circle(image, (*tint, alpha), center, radius)
    ray_color = tuple(round((c*.45+255*.55)*brightness) for c in color)
    rays = pg.Surface((size, size), pg.SRCALPHA)
    for index in range(12):
        angle = index*pi/6+((index*5+variant*3) % 7-3)*.025
        length = (13+(index*7+variant*3) % 5)*scale
        width = max(1, round((.35 if index % 3 else .55)*scale))
        dx, dy = cos(angle), sin(angle)
        for distance in range(round(length), round(3*scale), -1):
            alpha = round((100 if index % 3 else 170)*exp(-((distance/scale)/7.5)**2))
            start = (center[0]+dx*(distance-1), center[1]+dy*(distance-1))
            end = (center[0]+dx*distance, center[1]+dy*distance)
            pg.draw.line(rays, (*ray_color, alpha), start, end, width)
    image.blit(rays, (0, 0))
    return pg.transform.smoothscale(image, (pixels, pixels))


@lru_cache(maxsize=384)
def star_sprite(color, known=True, owners=(), selection=None, outpost=None, pixels=MARKER_BOX):
    # Supersample the small curves once per cached style/scale, not the map.
    samples = 3
    size = pixels*samples
    scale = size/MARKER_BOX
    center = (size//2, size//2)
    image = pg.Surface((size, size), pg.SRCALPHA)
    brightness = 1.0 if known else .85
    for radius in range(round(4.2*scale), 0, -1):
        r = radius/scale
        tint = min(1, (r/4.2)**2)*.35
        core = tuple(round(c*tint+255*(1-tint)) for c in color)
        alpha = round(255*brightness*exp(-(r/3.1)**4))
        pg.draw.circle(image, (*core, alpha), center, radius)

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
    sprite = pg.transform.smoothscale(image, (pixels, pixels))
    # Smoothscale may turn opaque alpha into 254. Keep the white centre fully
    # opaque so the changing light layer cannot flicker through it.
    pg.draw.circle(sprite, (255, 255, 255, 255), (pixels//2, pixels//2),
                   max(1, round(1.2*pixels/MARKER_BOX)))
    return sprite


def draw_atlas_star(surface, center, color, known=True, owners=(), selection=None, outpost=None,
                    *, zoom=1, time=0, star_id=0, animated=True):
    scale = surface.scale if isinstance(surface, Canvas) else 1
    pixels = max(1, round(MARKER_BOX*scale*star_zoom_scale(zoom)))
    glow = glow_sprite(tuple(color), known, pixels, star_id % 5)
    glow.set_alpha(pulse_alpha(star_id, time, animated))
    sprite = star_sprite(tuple(color), known, tuple(owners), selection, outpost,
                         pixels)
    position = surface.point(center) if isinstance(surface, Canvas) else center
    # Both layers already have their final display size. Keep the core and rings steady.
    pg.Surface.blit(surface, glow, glow.get_rect(center=position))
    pg.Surface.blit(surface, sprite, sprite.get_rect(center=position))
