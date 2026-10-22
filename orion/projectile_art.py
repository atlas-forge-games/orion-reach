"""Zoom-aware ordnance silhouettes, centred on the actual flight position."""

from functools import lru_cache
import math

import pygame as pg

from .weapons import BEAMS


def body_length(weapon, zoom):
    return max(10, round((14 if weapon in ("missile", "bomber_torpedo") else 18)*zoom))


@lru_cache(maxsize=384)
def sprite(weapon, length, heading):
    """Draw at double resolution, then rotate and downsample once."""
    scale = length/16
    canvas = pg.Surface((math.ceil(80*scale), math.ceil(40*scale)), pg.SRCALPHA)
    cx, cy = canvas.get_rect().center
    shade = BEAMS[weapon].color
    dark, metal, light = (9, 17, 26), (151, 173, 185), (235, 242, 238)

    def points(vertices):
        return [(round(cx+x*scale), round(cy+y*scale)) for x, y in vertices]

    def polygon(vertices, fill, outline=dark):
        pg.draw.polygon(canvas, fill, points(vertices))
        if outline:
            pg.draw.polygon(canvas, outline, points(vertices), max(1, round(1.2*scale)))

    if weapon == "missile":
        for side in (-1, 1):
            polygon([(-14, side*2), (-14, side*9), (-5, side*3)], metal)
        polygon([(-15, -3), (7, -3), (16, 0), (7, 3), (-15, 3)], light)
        polygon([(6, -3), (16, 0), (6, 3)], shade)
        pg.draw.line(canvas, metal, *points([(-11, 0), (5, 0)]), max(1, round(scale)))
    else:
        for side in (-1, 1):
            polygon([(-14, side*3), (-12, side*7), (-4, side*4)], metal)
        polygon([(-15, -4), (9, -4), (16, -1), (16, 1), (9, 4), (-15, 4)], metal)
        polygon([(-12, -3), (8, -3), (12, -1), (-12, -1)], light, None)
        polygon([(7, -4), (14, -2), (16, 0), (14, 2), (7, 4)], shade)
        for x in ((-6, 0) if weapon == "mirv" else (-5,)):
            pg.draw.line(canvas, dark, *points([(x, -3), (x, 3)]), max(1, round(scale)))
        if weapon in ("fusion_torpedo", "antimatter"):
            pg.draw.line(canvas, shade, *points([(-10, 2), (4, 2)]), max(1, round(scale)))
    pg.draw.line(canvas, shade, *points([(-15, -2), (-15, 2)]), max(1, round(2*scale)))
    return pg.transform.rotozoom(canvas, -heading, .5)


def draw(surface, position, direction, weapon, *, zoom=1.0, phase=0.0):
    """Draw a rocket or torpedo and exhaust without shifting its position."""
    angle = math.atan2(direction[1], direction[0])
    dx, dy = math.cos(angle), math.sin(angle)
    length = body_length(weapon, zoom)
    unit = length/32
    shade = BEAMS[weapon].color
    pulse = 2*math.sin(phase)

    def point(x, y=0):
        return (round(position[0]+(dx*x-dy*y)*unit),
                round(position[1]+(dy*x+dx*y)*unit))

    pg.draw.polygon(surface, tuple(c//3 for c in shade),
                    [point(-13, -4), point(-36-pulse), point(-13, 4)])
    pg.draw.polygon(surface, shade,
                    [point(-13, -2), point(-29-pulse), point(-13, 2)])
    pg.draw.line(surface, (255, 246, 218), point(-14), point(-21-pulse), max(1, round(zoom)))
    image = sprite(weapon, length, round(math.degrees(angle)/3)*3 % 360)
    rect = image.get_rect(center=(round(position[0]), round(position[1])))
    surface.blit(image, rect)
    return rect
