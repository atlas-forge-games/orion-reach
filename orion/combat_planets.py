"""Planet-bound missile batteries; presentation only, using existing world art."""

import pygame as pg

from .defenses import base_planet
from .planet_art import draw_planet
from .system_views import visual_seed
from .ui import INK

DIAMETER = 40


def planet_for(game, unit):
    return base_planet(game, unit.id) if unit and unit.kind == "missile_base" else None


def unit_name(game, unit):
    planet = planet_for(game, unit)
    return f"{planet.name} · Missile base" if planet else unit.name


def surface_anchor(center, facing, diameter=DIAMETER):
    """Launcher muzzle on the forward hemisphere, in display coordinates."""
    x, y = center
    return round(x+diameter*.32*facing), round(y-diameter*.12)


def draw_base(surface, game, unit, center, color, facing, *, diameter=DIAMETER, destroyed=False):
    planet = planet_for(game, unit)
    if planet is None:
        return
    # Leave space on the forward limb for a battery anchored to the terrain.
    x, y = center
    globe_center = (round(x-diameter*.12*facing), y)
    draw_planet(surface, planet, globe_center, diameter,
                visual_seed(game, game.systems[game.combat.system_id], planet))
    muzzle = surface_anchor(center, facing, diameter)
    scale = diameter/DIAMETER

    def point(dx, dy):
        return round(muzzle[0]+dx*scale*facing), round(muzzle[1]+dy*scale)

    if destroyed:
        pg.draw.circle(surface, (34, 29, 27), point(-5, 0), max(2, round(5*scale)))
        for dx, dy in ((-7, -2), (-3, 1), (-6, 3)):
            pg.draw.circle(surface, (182, 89, 43), point(dx, dy), max(1, round(scale)))
        return
    foundation = [point(-13, -5), point(-5, -6), point(-2, 4), point(-12, 6)]
    pg.draw.polygon(surface, (29, 40, 48), foundation)
    pg.draw.polygon(surface, color, foundation, max(1, round(scale)))
    for dy in (-3, 0, 3):
        pg.draw.line(surface, (53, 66, 77), point(-9, dy), point(0, dy), max(2, round(3*scale)))
        pg.draw.line(surface, INK, point(-8, dy-1), point(0, dy-1), max(1, round(scale)))
        pg.draw.circle(surface, (255, 188, 79), point(0, dy), max(1, round(scale)))
