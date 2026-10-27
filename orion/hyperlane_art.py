"""Project illustration and precise, scalable navigation symbols."""

from functools import lru_cache
from pathlib import Path
import math
import pygame as pg

from . import hyperlanes
from .galaxy_style import clean_map

LANE_COLOR = (160, 172, 255)
ART = Path(__file__).resolve().parents[1]/"assets"/"hyperlanes"/"forgotten_hyperlane-v1.png"


@lru_cache(maxsize=8)
def artwork(width, height):
    original = pg.image.load(str(ART)).convert()
    scale = min(width/original.get_width(), height/original.get_height())
    return pg.transform.smoothscale(original, (round(original.get_width()*scale), round(original.get_height()*scale)))


def draw_art(surface, rect):
    area = pg.Rect(rect)
    image = artwork(area.w, area.h)
    surface.blit(image, image.get_rect(center=area.center))


def draw_portal(surface, center, radius=16, active=True):
    x, y = map(round, center)
    color = LANE_COLOR if active else (79, 91, 118)
    rect = pg.Rect(x-radius, y-round(radius*.75), radius*2, round(radius*1.5))
    pg.draw.ellipse(surface, color, rect, max(1, radius//8))
    pg.draw.ellipse(surface, (87, 205, 231) if active else (47, 70, 89), rect.inflate(-6, -4), 1)
    for angle in (45, 135, 225, 315):
        a = math.radians(angle)
        tip = (round(x+radius*math.cos(a)), round(y+radius*.75*math.sin(a)))
        pg.draw.circle(surface, (211, 180, 125) if active else (102, 91, 73), tip, max(1, radius//9))


def draw_network(app, map_rect):
    routes = hyperlanes.visible_routes(app.game)
    if not routes:
        return
    layer = pg.Surface(map_rect.size, pg.SRCALPHA)
    endpoints = set()
    compact = clean_map(app)
    for route in routes:
        endpoints.update((route.system_id, route.destination))
        if compact:
            continue
        first, last = (app.star_pos(app.game.systems[sid]) for sid in (route.system_id, route.destination))
        x1, y1 = first[0]-map_rect.x, first[1]-map_rect.y
        x2, y2 = last[0]-map_rect.x, last[1]-map_rect.y
        length = max(1, math.hypot(x2-x1, y2-y1))
        bend = min(28, length*.12)
        cx, cy = (x1+x2)/2-(y2-y1)*bend/length, (y1+y2)/2+(x2-x1)*bend/length
        points = []
        for i in range(33):
            t = i/32
            points.append(((1-t)**2*x1+2*(1-t)*t*cx+t*t*x2,
                           (1-t)**2*y1+2*(1-t)*t*cy+t*t*y2))
        pg.draw.lines(layer, (*LANE_COLOR, 25), False, points, 7)
        pg.draw.lines(layer, (*LANE_COLOR, 120), False, points, 2)
        for i in (8, 16, 24):
            pg.draw.circle(layer, (159, 223, 255, 220), tuple(map(round, points[i])), 2)
    app.canvas.blit(layer, map_rect.topleft)
    for sid in endpoints:
        point = app.star_pos(app.game.systems[sid])
        if map_rect.collidepoint(point):
            draw_portal(app.canvas, point, 11 if compact else 16)
