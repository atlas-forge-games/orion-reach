"""Procedural transports and frigates for cards, battle formations and map markers."""

import pygame as pg

from .ui import CYAN, INK
from .monster_art import draw_monster
from .monsters import MONSTERS


def ship_icon(surface, center, scale=1.0, color=CYAN, kind="colony_ship", facing=0):
    if kind in MONSTERS:
        draw_monster(surface, center, kind, scale, facing)
        return
    x, y = center
    def points(values):
        if facing:
            values = [(-b*facing, a*facing) for a, b in values]
        return [(round(x+a*scale), round(y+b*scale)) for a, b in values]
    if kind == "missile_base":
        pg.draw.polygon(surface, (31, 49, 61), points([(-25, -15), (0, -29), (25, -15), (25, 15), (0, 29), (-25, 15)]))
        pg.draw.polygon(surface, color, points([(-25, -15), (0, -29), (25, -15), (25, 15), (0, 29), (-25, 15)]), max(1, round(scale)))
        pg.draw.circle(surface, color, (round(x), round(y)), max(2, round(12*scale)), max(1, round(2*scale)))
        for offset in (-17, 0, 17):
            pg.draw.line(surface, INK, points([(offset, -7)])[0], points([(offset, -25)])[0], max(2, round(3*scale)))
        return
    if kind in ("cruiser", "battleship"):
        heavy = kind == "battleship"
        width = 17 if heavy else 12
        hull = points([(0, -35), (width, -18), (width, 24), (-width, 24), (-width, -18)])
        pg.draw.polygon(surface, (31, 49, 61), hull)
        pg.draw.polygon(surface, color, hull, max(1, round(scale)))
        for side in (-1, 1):
            wing = points([(side*width, -20 if heavy else -3), (side*29, -9 if heavy else 7),
                           (side*29, 25), (side*width, 19)])
            pg.draw.polygon(surface, (46, 63, 74), wing)
            pg.draw.polygon(surface, color, wing, max(1, round(scale)))
            for top in ((-13, 3, 17) if heavy else (4, 19)):
                pg.draw.circle(surface, INK, points([(side*22, top)])[0], max(1, round(2*scale)))
            pg.draw.line(surface, color, points([(side*10, 27)])[0], points([(side*10, 34)])[0], max(1, round(4*scale)))
        pg.draw.lines(surface, INK, False, points([(-6, -12), (0, -22), (6, -12), (0, 10), (-6, -12)]), max(1, round(scale)))
        return
    if kind == "scout":
        hull = points([(0, -30), (8, -8), (6, 18), (0, 25), (-6, 18), (-8, -8)])
        pg.draw.polygon(surface, (22, 46, 56), hull)
        pg.draw.polygon(surface, color, hull, max(1, round(scale)))
        for side in (-1, 1):
            pg.draw.lines(surface, color, False, points([(side*7, 0), (side*21, 9), (side*21, -7)]), max(1, round(scale)))
            pg.draw.circle(surface, INK, points([(side*21, -9)])[0], max(1, round(3*scale)), max(1, round(scale)))
        pg.draw.line(surface, color, points([(0, 26)])[0], points([(0, 34)])[0], max(1, round(3*scale)))
        return
    if kind == "troop_transport":
        hull = points([(-13, -29), (13, -29), (19, -14), (19, 22), (-19, 22), (-19, -14)])
        pg.draw.polygon(surface, (31, 49, 61), hull)
        pg.draw.polygon(surface, color, hull, max(1, round(scale)))
        for offset in (-10, 10):
            pod = points([(offset-5, -9), (offset+5, -9), (offset+5, 16), (offset-5, 16)])
            pg.draw.polygon(surface, (57, 74, 81), pod)
            pg.draw.polygon(surface, INK, pod, max(1, round(scale)))
            pg.draw.line(surface, color, points([(offset, 25)])[0], points([(offset, 33)])[0], max(1, round(3*scale)))
        pg.draw.line(surface, INK, points([(-7, -20)])[0], points([(7, -20)])[0], max(1, round(2*scale)))
        return
    if kind == "frigate":
        hull = points([(0, -34), (10, -15), (10, 17), (6, 25), (-6, 25), (-10, 17), (-10, -15)])
        pg.draw.polygon(surface, (31, 49, 61), hull)
        pg.draw.polygon(surface, color, hull, max(1, round(scale)))
        for side in (-1, 1):
            wing = points([(side*9, -7), (side*23, 2), (side*26, 23), (side*10, 17)])
            pg.draw.polygon(surface, (42, 57, 66), wing)
            pg.draw.polygon(surface, color, wing, max(1, round(scale)))
            pg.draw.line(surface, INK, points([(side*20, -17)])[0], points([(side*20, 11)])[0], max(1, round(2*scale)))
            pg.draw.line(surface, color, points([(side*6, 27)])[0], points([(side*6, 33)])[0], max(1, round(3*scale)))
        pg.draw.line(surface, INK, points([(0, -20)])[0], points([(0, 13)])[0], max(1, round(2*scale)))
        return
    hull = points([(0, -27), (11, -5), (11, 20), (-11, 20), (-11, -5)])
    pg.draw.polygon(surface, (14, 35, 47), hull)
    pg.draw.polygon(surface, color, hull, max(1, round(scale)))
    for side in (-1, 1):
        wing = points([(side*11, -1), (side*24, 11), (side*24, 22), (side*11, 17)])
        pg.draw.polygon(surface, (26, 47, 57), wing)
        pg.draw.polygon(surface, color, wing, max(1, round(scale)))
        pg.draw.line(surface, INK, points([(side*6, 22)])[0], points([(side*6, 28)])[0], max(1, round(2*scale)))
    pg.draw.line(surface, INK, points([(0, -12)])[0], points([(0, 13)])[0], max(1, round(scale)))
