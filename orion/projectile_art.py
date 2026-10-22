"""Zoom-aware ordnance silhouettes, centred on the actual flight position."""

from functools import lru_cache
from collections import deque
import math

import pygame as pg

from .weapons import BEAMS
from .ui import ASSETS


# Filename, rear of body, nose, and engine/nose centreline in the original PNG.
# Exhaust must not influence the position or scale of the projectile body.
PROJECTILE_ART = {
    "torpedo": ("standard_torpedo.png", 78, 533, 78),
    "fusion_torpedo": ("fusion_torpedo.png", 83, 537, 78),
    "mirv": ("mirv_torpedo.png", 75, 542, 78),
    "antimatter": ("antimatter_torpedo.png", 78, 533, 90),
    "bomber_torpedo": ("bomber_drone_torpedo.png", 88, 537, 90),
    "missile": ("defense_missile.png", 127, 526, 90),
}


def _transparent_art(image, rear):
    """Key the supplied navy backdrop, retaining enclosed dark hull details.

    The source pack has opaque RGBA PNGs. Flooding only navy pixels connected
    to the border avoids punching transparent holes into the machinery. The
    engine plume is unmatted separately so its soft blue edge remains soft.
    Original files are never altered, and already transparent replacements
    are used as supplied.
    """
    if any(image.get_at(p).a < 255 for p in ((0, 0), (image.get_width()-1, 0),
                                           (0, image.get_height()-1))):
        return image
    width, height = image.get_size()
    output = image.copy()
    queue = deque([(x, y) for x in range(width) for y in (0, height-1)] +
                  [(x, y) for y in range(height) for x in (0, width-1)])
    seen = set()
    while queue:
        x, y = queue.popleft()
        if (x, y) in seen or not (0 <= x < width and 0 <= y < height):
            continue
        seen.add((x, y))
        r, g, b, _ = image.get_at((x, y))
        if r <= 18 and g <= 40 and b <= 72 and g-r >= 5 and b-r >= 10:
            output.set_at((x, y), (0, 0, 0, 0))
            queue.extend(((x-1, y), (x+1, y), (x, y-1), (x, y+1)))
    for x in range(rear):
        top, bottom = image.get_at((x, 0)), image.get_at((x, height-1))
        backdrop = tuple((top[i]+bottom[i])/2 for i in range(3))
        for y in range(height):
            pixel = image.get_at((x, y))
            alpha = max(0, *(max(0, pixel[i]-backdrop[i])/(255-backdrop[i]) for i in range(3)))
            if alpha < .025:
                output.set_at((x, y), (0, 0, 0, 0))
            else:
                color = [max(0, min(255, round(backdrop[i]+(pixel[i]-backdrop[i])/alpha)))
                         for i in range(3)]
                output.set_at((x, y), (*color, round(alpha*255)))
    return output


@lru_cache(maxsize=8)
def load_projectile_art(weapon):
    """Return native artwork centred on the hull, and its native body length."""
    spec = PROJECTILE_ART.get(weapon)
    if spec is None:
        return None
    filename, rear, nose, axis_y = spec
    try:
        image = pg.image.load(str(ASSETS / "projectiles" / filename))
        if not (0 <= rear < nose < image.get_width() and 0 <= axis_y < image.get_height()):
            return None
        image = _transparent_art(image, rear)
        pivot_x = round((rear+nose)/2)
        half_w = max(pivot_x, image.get_width()-pivot_x)
        half_h = max(axis_y, image.get_height()-axis_y)
        centred = pg.Surface((half_w*2, half_h*2), pg.SRCALPHA)
        centred.blit(image, (half_w-pivot_x, half_h-axis_y))
        return centred, nose-rear
    except (OSError, pg.error):
        return None


def body_length(weapon, zoom):
    return max(10, round((14 if weapon in ("missile", "bomber_torpedo") else 18)*zoom))


@lru_cache(maxsize=384)
def sprite(weapon, length, heading):
    """Rotate at native resolution, then filter down to the requested size."""
    art = load_projectile_art(weapon)
    if art is not None:
        image, native_length = art
        # Downscaling with rotozoom's bilinear filter alone aliases the fine
        # metal panels at combat sizes. Area filtering keeps small sprites clear.
        rotated = pg.transform.rotate(image, -heading) if heading else image
        scale = length/native_length
        size = tuple(max(1, round(n*scale)) for n in rotated.get_size())
        return pg.transform.smoothscale(rotated, size)
    return _procedural_sprite(weapon, length, heading)


def _procedural_sprite(weapon, length, heading):
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

    if load_projectile_art(weapon) is None:
        pg.draw.polygon(surface, tuple(c//3 for c in shade),
                        [point(-13, -4), point(-36-pulse), point(-13, 4)])
        pg.draw.polygon(surface, shade,
                        [point(-13, -2), point(-29-pulse), point(-13, 2)])
        pg.draw.line(surface, (255, 246, 218), point(-14), point(-21-pulse), max(1, round(zoom)))
    image = sprite(weapon, length, round(math.degrees(angle)/3)*3 % 360)
    rect = image.get_rect(center=(round(position[0]), round(position[1])))
    surface.blit(image, rect)
    return rect
