"""Seeded globe illustrations drawn with pygame; no new runtime dependency."""

from functools import lru_cache
import math
import random
import pygame as pg

COLORS = {
    "Gaia": ((18, 106, 133), (78, 171, 107), (137, 240, 210)),
    "Terran": ((25, 87, 125), (80, 128, 98), (117, 192, 226)),
    "Ocean": ((18, 93, 156), (59, 131, 125), (99, 194, 245)),
    "Desert": ((167, 98, 54), (216, 153, 83), (231, 181, 113)),
    "Tundra": ((105, 148, 166), (192, 217, 221), (177, 228, 243)),
    "Barren": ((113, 116, 124), (151, 150, 144), (143, 160, 182)),
    "Volcanic": ((63, 55, 62), (103, 77, 68), (242, 139, 76)),
}
SIZE = 384


@lru_cache(maxsize=1)
def lighting():
    """Sphere lighting calculated once, then multiplied into each globe."""
    small = pg.Surface((128, 128), pg.SRCALPHA)
    small.fill((0, 0, 0, 0))
    pixels = pg.PixelArray(small)
    for x in range(128):
        nx = (x - 63.5) / 62
        for y in range(128):
            ny = (y - 63.5) / 62
            r2 = nx*nx + ny*ny
            if r2 <= 1:
                nz = math.sqrt(1-r2)
                sun = max(0, -.57*nx - .49*ny + .66*nz)
                level = int(min(255, 22 + 233*sun**.65))
                pixels[x, y] = (level, level, level, 255)
    del pixels
    return pg.transform.smoothscale(small, (SIZE, SIZE))


@lru_cache(maxsize=48)
def globe(biome, seed):
    rng = random.Random(seed)
    base, terrain, atmosphere = COLORS[biome]
    result = pg.Surface((SIZE, SIZE), pg.SRCALPHA)
    result.fill((*base, 255))
    if biome in ("Terran", "Ocean", "Tundra", "Gaia"):
        count = 22 if biome in ("Terran", "Gaia") else 8 if biome == "Ocean" else 34
        for _ in range(count):
            x, y = rng.randrange(SIZE), rng.randrange(SIZE)
            radius = rng.uniform(12, 53) if biome != "Ocean" else rng.uniform(4, 17)
            points = []
            for i in range(22):
                angle = i*math.tau/22
                r = radius*rng.uniform(.5, 1.35)
                points.append((x+math.cos(angle)*r, y+math.sin(angle)*r*.75))
            shade = tuple(max(0, min(255, c+rng.randrange(-13, 14))) for c in terrain)
            pg.draw.polygon(result, shade, points)
        # Icecaps and wispy cloud bands.
        for y in (0, SIZE-16):
            pg.draw.ellipse(result, (205, 224, 225), (66, y-14, 248, 48))
        clouds = pg.Surface((SIZE, SIZE), pg.SRCALPHA)
        for _ in range(26):
            x, y = rng.randrange(-45, SIZE), rng.randrange(SIZE)
            pg.draw.arc(clouds, (214, 235, 234, rng.randrange(50, 133)),
                        (x, y, rng.randrange(55, 160), rng.randrange(20, 70)),
                        .2, 2.3, rng.randrange(2, 5))
        result.blit(clouds, (0, 0))
    elif biome == "Desert":
        for i in range(36):
            y = i*11 + rng.randrange(-10, 11)
            shade = tuple(max(0, min(255, c+rng.randrange(-22, 17))) for c in terrain)
            points = [(x, y+math.sin(x/75+i*.7)*11) for x in range(-20, SIZE+20, 5)]
            pg.draw.lines(result, shade, False, points, rng.randrange(1, 5))
    else:
        for _ in range(95):
            x, y, r = rng.randrange(SIZE), rng.randrange(SIZE), rng.randrange(3, 21)
            pg.draw.circle(result, tuple(max(0, c-21) for c in base), (x, y), r)
            pg.draw.arc(result, terrain, (x-r, y-r, 2*r, 2*r), .4, 3.5, 1)
        if biome == "Volcanic":
            for _ in range(18):
                x, y = rng.randrange(SIZE), rng.randrange(SIZE)
                points = [(x, y)]
                for _ in range(rng.randrange(5, 12)):
                    x += rng.randrange(-15, 17)
                    y += rng.randrange(3, 15)
                    points.append((x, y))
                pg.draw.lines(result, (126, 52, 30), False, points, 5)
                pg.draw.lines(result, (247, 122, 43), False, points, 2)
    result.blit(lighting(), (0, 0), special_flags=pg.BLEND_RGBA_MULT)
    return result


@lru_cache(maxsize=96)
def planet_image(biome, seed, diameter):
    return pg.transform.smoothscale(globe(biome, seed), (diameter, diameter))


def draw_planet(surface, planet, center, diameter, seed, selected=False):
    x, y = center
    atmosphere = COLORS[planet.biome][2]
    radius = diameter//2
    pg.draw.circle(surface, tuple(c//12 for c in atmosphere), (int(x), int(y)), radius+7)
    pg.draw.circle(surface, tuple(c//6 for c in atmosphere), (int(x), int(y)), radius+3)
    image = planet_image(planet.biome, seed, diameter)
    surface.blit(image, (int(x-diameter/2), int(y-diameter/2)))
    if selected:
        pg.draw.circle(surface, (215, 182, 125), (int(x), int(y)), radius+13, 1)


def draw_star(surface, center, radius, color):
    x, y = map(int, center)
    for factor, denominator in ((2.0, 18), (1.65, 12), (1.32, 7), (1.12, 3)):
        pg.draw.circle(surface, tuple(c//denominator for c in color), (x, y), int(radius*factor))
    for r in range(radius, 0, -2):
        warmth = 1-r/radius
        shade = tuple(int(c+(255-c)*warmth*.83) for c in color)
        pg.draw.circle(surface, shade, (x, y), r)
