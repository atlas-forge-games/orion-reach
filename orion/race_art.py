"""Cached race portraits with scalable diplomatic seals as a fallback."""

from functools import lru_cache
import math
import pygame as pg

from .races import SETUP_RACES as RACES
from .ui import ASSETS


@lru_cache(maxsize=len(RACES))
def _load_portrait(race_id):
    # Resolve beside the source, so launching from another directory also works.
    try:
        return pg.image.load(str(ASSETS / "portraits" / f"{race_id}-v1.png"))
    except (OSError, pg.error):
        return None


@lru_cache(maxsize=64)
def _scaled_portrait(race_id, size):
    portrait = _load_portrait(race_id)
    if portrait is None:
        return None
    fitted = portrait.get_rect().fit(pg.Rect((0, 0), size))
    frame = pg.Surface(size)
    frame.fill((5, 12, 20))
    frame.blit(pg.transform.smoothscale(portrait, fitted.size), fitted)
    return frame


def draw_race_portrait(surface, race_id, rect):
    """Fit a portrait without stretching; missing or damaged PNGs use a seal."""
    rect = pg.Rect(rect)
    portrait = _scaled_portrait(race_id, rect.size)
    if portrait is None:
        pg.draw.rect(surface, (5, 12, 20), rect)
        draw_race_emblem(surface, race_id, rect.center, round(min(rect.size)*.36))
    else:
        surface.blit(portrait, rect)
    pg.draw.rect(surface, RACES[race_id].color, rect, 1)


def draw_race_emblem(surface, race_id, center, radius=50):
    x, y = center
    color = RACES[race_id].color
    dim = tuple(c//4 for c in color)
    def pt(a, b):
        return round(x+a*radius), round(y+b*radius)
    width = max(1, round(radius/24))
    pg.draw.circle(surface, dim, (int(x), int(y)), round(radius), 1)
    pg.draw.circle(surface, tuple(c//12 for c in color), (int(x), int(y)), round(radius*.85))
    if race_id == "observer":
        pg.draw.ellipse(surface, color, (x-radius*.75, y-radius*.36, radius*1.5, radius*.72), width)
        pg.draw.circle(surface, color, (int(x), int(y)), round(radius*.24), width)
        pg.draw.circle(surface, color, (int(x), int(y)), max(2, round(radius*.08)))
    elif race_id == "terran":
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
    elif race_id == "aelari":
        pg.draw.lines(surface, color, False, [pt(-.58, .30), pt(-.33, -.02), pt(0, -.69),
                                             pt(.33, -.02), pt(.58, .30)], width)
        for offset in (.22, .45, .68):
            points = [pt(t/10, offset+.065*math.sin(t*math.pi/5)) for t in range(-6, 7)]
            pg.draw.lines(surface, color, False, points, width)
        pg.draw.circle(surface, color, pt(0, -.08), round(radius*.12), width)
        for a, b in ((-.55, -.52), (.55, -.52)):
            pg.draw.circle(surface, color, pt(a, b), max(2, round(radius*.04)))
    elif race_id == "lithar":
        for a, b, r in ((-.34, .28, .27), (.28, .3, .32), (0, -.3, .4)):
            vertices = [pt(a+r*math.cos(i*math.tau/5), b+r*math.sin(i*math.tau/5)) for i in range(5)]
            pg.draw.polygon(surface, color, vertices, width)
    elif race_id == "varkesh":
        pg.draw.polygon(surface, color, [pt(0, -.5), pt(.4, 0), pt(0, .6), pt(-.4, 0)], width)
        for sign in (-1, 1):
            pg.draw.lines(surface, color, False, [pt(sign*.25, .1), pt(sign*.7, -.15), pt(sign*.55, -.6)], width)
    elif race_id == "wanderers":
        pg.draw.polygon(surface, color, [pt(0, -.75), pt(.55, .55), pt(0, .27), pt(-.55, .55)], width)
        pg.draw.line(surface, color, pt(-.72, 0), pt(.72, 0), width)
    elif race_id == "xenonflora":
        pg.draw.line(surface, color, pt(0, .7), pt(0, -.6), width)
        for sign in (-1, 1):
            for height in (-.35, .15):
                pg.draw.lines(surface, color, False, [pt(0, height+.3), pt(sign*.5, height), pt(sign*.3, height-.3)], width)
    elif race_id == "nexus":
        nodes = [pt(math.cos(i*math.tau/3)*.6, math.sin(i*math.tau/3)*.6) for i in range(3)]
        pg.draw.polygon(surface, color, nodes, width)
        for cx, cy in nodes:
            pg.draw.rect(surface, color, (cx-radius*.16, cy-radius*.16, radius*.32, radius*.32), width)
    elif race_id == "aetheri":
        for offset in (-.17, .17):
            pg.draw.ellipse(surface, color, (x+radius*(offset-.4), y-radius*.65, radius*.8, radius*1.3), width)
    elif race_id == "concord":
        # Distinct organisms subordinated to one central collective mind.
        for a in (-.5, 0, .5):
            for b in (-.5, 0, .5):
                pg.draw.line(surface, dim, pt(a, b), pt(0, 0), width)
                cx, cy = pt(a, b)
                r = radius*(.16 if (a, b) == (0, 0) else .1)
                pg.draw.rect(surface, color, (cx-r, cy-r, 2*r, 2*r), width)
        pg.draw.rect(surface, color, (*pt(-.75, -.75), 1.5*radius, 1.5*radius), width)
    else:  # Remnant: a broken halo and the last light beneath it.
        pg.draw.arc(surface, color, (x-radius*.6, y-radius*.65, radius*1.2, radius*1.2), .25, math.pi*1.8, width)
        pg.draw.polygon(surface, color, [pt(0, -.3), pt(.17, .5), pt(-.17, .5)], width)
