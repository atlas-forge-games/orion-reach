"""Small procedural colony transports, suitable for cards and map markers."""

import pygame as pg

from .ui import CYAN, INK


def ship_icon(surface, center, scale=1.0, color=CYAN):
    x, y = center
    def points(values):
        return [(round(x+a*scale), round(y+b*scale)) for a, b in values]
    hull = points([(0, -27), (11, -5), (11, 20), (-11, 20), (-11, -5)])
    pg.draw.polygon(surface, (14, 35, 47), hull)
    pg.draw.polygon(surface, color, hull, max(1, round(scale)))
    for side in (-1, 1):
        wing = points([(side*11, -1), (side*24, 11), (side*24, 22), (side*11, 17)])
        pg.draw.polygon(surface, (26, 47, 57), wing)
        pg.draw.polygon(surface, color, wing, max(1, round(scale)))
        pg.draw.line(surface, INK, points([(side*6, 22)])[0], points([(side*6, 28)])[0], max(1, round(2*scale)))
    pg.draw.line(surface, INK, points([(0, -12)])[0], points([(0, 13)])[0], max(1, round(scale)))
