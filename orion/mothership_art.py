"""A scalable habitat ring and city spine, legible from map badge to home view."""

import math
from functools import lru_cache
import pygame as pg


@lru_cache(maxsize=48)
def sprite(size, color, facing=0):
    # Draw at a fixed large resolution and downsample for clean map silhouettes.
    canvas = pg.Surface((400, 440), pg.SRCALPHA)
    brass, light, dark = (184, 151, 91), (236, 218, 170), (26, 38, 45)
    for x in (148, 200, 252):
        pg.draw.polygon(canvas, (*color, 65), [(x-13, 338), (x+13, 338), (x, 419)])
        pg.draw.polygon(canvas, (153, 224, 233), [(x-5, 338), (x+5, 338), (x, 386)])
    # Structural spokes sit below the living ring.
    for a in range(0, 360, 45):
        r = math.radians(a)
        point = (round(200+145*math.cos(r)), round(215+105*math.sin(r)))
        pg.draw.line(canvas, dark, (200, 215), point, 19)
        pg.draw.line(canvas, brass, (200, 215), point, 4)
    pg.draw.ellipse(canvas, dark, (30, 87, 340, 256), 45)
    pg.draw.ellipse(canvas, brass, (30, 87, 340, 256), 8)
    pg.draw.ellipse(canvas, light, (69, 118, 262, 194), 3)
    pg.draw.ellipse(canvas, color, (48, 101, 304, 228), 3)
    for a in range(0, 360, 30):
        r = math.radians(a)
        x, y = round(200+145*math.cos(r)), round(215+107*math.sin(r))
        rect = pg.Rect(x-17, y-19, 34, 38)
        pg.draw.rect(canvas, (55, 65, 65), rect, border_radius=5)
        pg.draw.rect(canvas, brass, rect, 2, border_radius=5)
        for dx in (-8, 0, 8):
            pg.draw.line(canvas, light, (x+dx, y-10), (x+dx, y+10), 2)
    spine = [(200, 24), (224, 65), (224, 296), (241, 340), (159, 340), (176, 296), (176, 65)]
    pg.draw.polygon(canvas, (38, 53, 63), spine)
    pg.draw.polygon(canvas, light, spine, 3)
    for y in range(98, 290, 24):
        pg.draw.rect(canvas, (57, 78, 82), (181, y, 38, 15), border_radius=2)
        pg.draw.line(canvas, color, (187, y+6), (213, y+6), 3)
    pg.draw.polygon(canvas, brass, [(200, 48), (211, 70), (211, 84), (189, 84), (189, 70)])
    pg.draw.circle(canvas, (29, 53, 57), (200, 211), 32)
    pg.draw.circle(canvas, light, (200, 211), 32, 3)
    pg.draw.circle(canvas, color, (200, 211), 20, 3)
    pg.draw.circle(canvas, light, (200, 211), 6)
    image = pg.transform.smoothscale(canvas, (max(1, round(size*400/440)), max(1, size)))
    return pg.transform.rotate(image, -90*facing) if facing else image


def draw(surface, center, scale=1, color=(210, 181, 125), facing=0):
    image = sprite(max(1, round(76*scale)), tuple(color), facing)
    surface.blit(image, image.get_rect(center=center))
