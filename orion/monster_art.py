"""Small procedural guardian illustrations, sized for tactical cells and surveys."""

import math
import pygame as pg

from .monsters import MONSTERS


def draw_guardian_symbol(surface, center, kind, size=18):
    """Distinct silhouettes stay legible at map scale, including without colour."""
    x, y = center
    scale = size/20
    color = MONSTERS[kind].color
    dark = tuple(c//3 for c in color)
    def points(values):
        return [(round(x+a*scale), round(y+b*scale)) for a, b in values]
    width = max(1, round(2*scale))
    if kind == "space_serpent":
        pg.draw.lines(surface, color, False, points([(6, -6), (1, -8), (-5, -5), (-5, -1),
                      (5, 2), (5, 6), (-1, 8), (-7, 5)]), width)
        pg.draw.polygon(surface, color, points([(3, -8), (9, -5), (2, -3)]))
    elif kind == "crystal_guardian":
        diamond = points([(0, -9), (7, -1), (0, 9), (-7, -1)])
        pg.draw.polygon(surface, dark, diamond)
        pg.draw.polygon(surface, color, diamond, width)
        pg.draw.lines(surface, color, False, points([(-7, -1), (0, 1), (7, -1)]), 1)
        pg.draw.line(surface, color, *points([(0, -9), (0, 9)]), 1)
    elif kind == "ancient_sentinel":
        shield = points([(-8, -7), (8, -7), (8, 4), (0, 9), (-8, 4)])
        pg.draw.polygon(surface, dark, shield)
        pg.draw.polygon(surface, color, shield, width)
        pg.draw.line(surface, color, *points([(-5, -1), (5, -1)]), width)
        pg.draw.line(surface, color, *points([(0, -4), (0, 4)]), width)
    elif kind == "void_leviathan":
        pg.draw.polygon(surface, color, points([(-9, -8), (-4, -4), (0, -7), (4, -4), (9, -8),
                        (7, 2), (0, 9), (-7, 2)]))
        pg.draw.polygon(surface, (9, 17, 28), points([(-5, -1), (0, 4), (5, -1), (0, 1)]))


def draw_monster(surface, center, kind, scale=1.0, facing=-1):
    x, y = center
    direction = -1 if facing == 1 else 1
    def point(a, b):
        return round(x+a*scale*direction), round(y+b*scale)
    def polygon(vertices, fill, outline=None):
        points = [point(*p) for p in vertices]
        pg.draw.polygon(surface, fill, points)
        if outline:
            pg.draw.polygon(surface, outline, points, max(1, round(scale)))
    if kind == "space_serpent":
        # A coiled tail, plated body and a broad, horned head facing the enemy.
        curve = [(29, -24), (37, -12), (30, 1), (11, 4), (4, 17), (21, 24),
                 (32, 14), (15, -4), (-7, -10), (-22, -3)]
        for index in range(len(curve)-1):
            width = max(2, round((3+index*.8)*scale))
            pg.draw.line(surface, (26, 68, 59), point(*curve[index]), point(*curve[index+1]), width+2)
            pg.draw.line(surface, (72, 155, 111), point(*curve[index]), point(*curve[index+1]), width)
        for a, b in curve[3:-1]:
            polygon([(a-3, b-3), (a+5, b-13), (a+6, b)], (53, 122, 96), (112, 213, 153))
        polygon([(-13, -12), (-24, -21), (-24, -10), (-38, -5), (-30, 7), (-13, 11), (-7, 1)],
                (53, 124, 91), (142, 239, 170))
        polygon([(-27, -3), (-20, -4), (-24, 0)], (239, 217, 111))
        pg.draw.line(surface, (17, 47, 40), point(-36, 1), point(-20, 5), max(1, round(2*scale)))
        polygon([(-29, 5), (-26, 11), (-24, 5)], (201, 241, 192))
    elif kind == "crystal_guardian":
        # Separate facets surround a bright, asymmetric crystalline core.
        for index in range(7):
            angle = index*math.tau/7+.18
            a, b = math.cos(angle), math.sin(angle)
            inner, outer = 19, 34+(index%3)*3
            polygon([(a*inner, b*inner), (a*outer-b*5, b*outer+a*5),
                     (a*(outer+4), b*(outer+4)), (a*outer+b*5, b*outer-a*5)],
                    (29, 75, 115), (108, 205, 244))
        polygon([(-19, -7), (-7, -26), (12, -18), (23, 3), (8, 25), (-15, 16)],
                (43, 112, 157), (164, 232, 255))
        polygon([(-19, -7), (-7, -26), (0, -3), (-15, 16)], (58, 150, 184))
        polygon([(-7, -26), (12, -18), (0, -3)], (158, 225, 240))
        polygon([(0, -3), (23, 3), (8, 25)], (31, 83, 130))
        for a, b in ((-19, -7), (-7, -26), (23, 3), (8, 25), (-15, 16)):
            pg.draw.line(surface, (126, 218, 251), point(0, -3), point(a, b), max(1, round(scale)))
        pg.draw.circle(surface, (228, 253, 255), point(0, -3), max(2, round(4*scale)))
    elif kind == "ancient_sentinel":
        # A mechanical relic: four armoured pylons surround an ancient reactor eye.
        for side in (-1, 1):
            for top in (-1, 1):
                polygon([(side*11, top*7), (side*34, top*13), (side*37, top*27),
                         (side*23, top*24), (side*16, top*14)], (83, 72, 58), (199, 167, 108))
                pg.draw.line(surface, (255, 218, 142), point(side*25, top*17), point(side*34, top*21), max(1, round(3*scale)))
        polygon([(-22, -13), (-10, -26), (13, -22), (24, -7), (24, 13),
                 (10, 26), (-12, 21), (-24, 5)], (69, 74, 79), (224, 188, 114))
        polygon([(-22, -13), (-10, -26), (13, -22), (-2, -4)], (127, 124, 108))
        polygon([(-2, -4), (24, -7), (24, 13), (10, 26)], (42, 47, 56))
        pg.draw.circle(surface, (29, 30, 35), point(-2, 0), max(1, round(12*scale)))
        pg.draw.circle(surface, (247, 181, 82), point(-2, 0), max(1, round(9*scale)), max(1, round(2*scale)))
        pg.draw.circle(surface, (255, 237, 170), point(-2, 0), max(1, round(4*scale)))
        pg.draw.line(surface, (246, 207, 126), point(-22, 0), point(-35, 0), max(1, round(3*scale)))
    elif kind == "void_leviathan":
        # Broad organic armour, a forked tail, horns and a luminous violet maw.
        polygon([(13, -4), (35, -25), (28, -6), (39, 9), (26, 7), (18, 17)],
                (53, 37, 91), (157, 111, 224))
        polygon([(-20, -14), (1, -25), (22, -11), (26, 7), (7, 21), (-20, 13), (-35, 1)],
                (60, 45, 93), (181, 139, 240))
        polygon([(-16, -10), (-22, -29), (-5, -16), (11, -21), (6, -9)], (119, 87, 164), (204, 166, 255))
        polygon([(-16, 12), (-20, 29), (-3, 19), (9, 20), (4, 10)], (86, 62, 128), (177, 130, 230))
        for a in (-2, 7, 16):
            pg.draw.lines(surface, (148, 104, 204), False, [point(a, -12), point(a+5, 0), point(a, 13)], max(1, round(2*scale)))
        polygon([(-35, 1), (-24, -6), (-11, 0), (-23, 8)], (17, 14, 34), (207, 164, 255))
        polygon([(-30, 0), (-23, -2), (-20, 5)], (226, 204, 255))
        pg.draw.circle(surface, (243, 164, 255), point(-21, -9), max(1, round(3*scale)))
