"""A small fuel depot placed on its actual planet landscape."""
import pygame as pg
from .building_art import draw_building_art
from .ui import CYAN, INK, MUTED, panel, shorten, text
from . import outposts


def draw_surface_outpost(app, rect, game, system, planet):
    surface = app.canvas
    cx, bottom = rect.centerx, round(rect.y+rect.h*.71)
    scale = min(rect.w/928, rect.h/473)
    width, height = round(260*scale), round(160*scale)
    pad = pg.Rect(cx-width//2-50, bottom-20, width+100, 34)
    pg.draw.ellipse(surface, (39, 49, 54), pad)
    pg.draw.ellipse(surface, (91, 107, 114), pad, 2)
    draw_building_art(surface, "shipyard", (cx-width//2, bottom-height, width, height))
    draw_building_art(surface, "sensor_array", (cx+width//3, bottom-height//2-30, round(84*scale), round(92*scale)))
    color = app.empire_color(planet.outpost_owner)
    panel(surface, (cx-224, bottom+29, 448, 72), (10, 23, 30), color)
    text(surface, "REFUELLING OUTPOST", (cx-206, bottom+40), 18, color)
    text(surface, shorten(game.empire_name_for(planet.outpost_owner), 416, 13), (cx-206, bottom+69), 13, INK)
    live = game.system_visible(system.id)
    caption = (f"{planet.outpost_hull}/{outposts.OUTPOST_HULL} hull · Repairs +{outposts.OUTPOST_RECOVERY}/peaceful turn"
               if live else "Stored survey · Current status unknown")
    text(surface, caption, (cx-218, bottom+115), 12, CYAN if live else MUTED)
    pg.draw.rect(surface, (38, 57, 68), rect, 1)
