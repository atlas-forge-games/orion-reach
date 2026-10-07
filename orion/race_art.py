"""Scalable diplomatic seals, drawn with the game's existing pygame artwork."""

import math
import pygame as pg

from .races import RACES


def draw_race_emblem(surface, race_id, center, radius=50):
    x, y = center
    color = RACES[race_id].color
    dim = tuple(c//4 for c in color)
    def pt(a, b):
        return round(x+a*radius), round(y+b*radius)
    width = max(1, round(radius/24))
    pg.draw.circle(surface, dim, (int(x), int(y)), round(radius), 1)
    pg.draw.circle(surface, tuple(c//12 for c in color), (int(x), int(y)), round(radius*.85))
    if race_id == "terran":
        pg.draw.circle(surface, color, (int(x), int(y)), round(radius*.55), width)
        pg.draw.ellipse(surface, color, (x-radius*.24, y-radius*.55, radius*.48, radius*1.1), width)
        pg.draw.line(surface, color, pt(-.55, 0), pt(.55, 0), width)
        pg.draw.arc(surface, color, (x-radius*.79, y-radius*.37, radius*1.58, radius*.74),
                    math.pi*.15, math.pi*1.4, width)
        pg.draw.circle(surface, color, pt(.74, -.14), max(2, round(radius*.055)))
    elif race_id == "kharuun":
        vertices = [pt(0, -.75), pt(.56, -.26), pt(.43, .48), pt(0, .73), pt(-.43, .48), pt(-.56, -.26)]
        pg.draw.polygon(surface, dim, vertices)
        pg.draw.polygon(surface, color, vertices, width)
        for vertex in vertices:
            pg.draw.line(surface, color, pt(0, -.04), vertex, width)
        pg.draw.line(surface, color, pt(-.43, .48), pt(.43, .48), width)
    else:
        pg.draw.lines(surface, color, False, [pt(-.58, .30), pt(-.33, -.02), pt(0, -.69),
                                             pt(.33, -.02), pt(.58, .30)], width)
        for offset in (.22, .45, .68):
            points = [pt(t/10, offset+.065*math.sin(t*math.pi/5)) for t in range(-6, 7)]
            pg.draw.lines(surface, color, False, points, width)
        pg.draw.circle(surface, color, pt(0, -.08), round(radius*.12), width)
        for a, b in ((-.55, -.52), (.55, -.52)):
            pg.draw.circle(surface, color, pt(a, b), max(2, round(radius*.04)))
