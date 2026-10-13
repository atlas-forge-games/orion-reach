"""Reusable, cached building sprites; original PNGs remain untouched."""

from functools import lru_cache
import pygame as pg

from .ui import ASSETS
from .buildings import BUILDINGS, FACILITY_FAMILIES, facility_family

BUILDING_ART_IDS = ("headquarters", "shipyard", *BUILDINGS, "ascension_gate")


@lru_cache(maxsize=32)
def load_building_art(building_id):
    if building_id not in BUILDING_ART_IDS:
        raise ValueError(f"Unknown building artwork: {building_id}")
    try:
        image = pg.image.load(str(ASSETS / "buildings" / f"{building_id}-v1.png"))
        # Exclude faint transparent margins when aligning each foundation.
        bounds = image.get_bounding_rect(min_alpha=32)
        if not bounds.w or not bounds.h:
            return None
        return image.subsurface(bounds).copy()
    except (OSError, pg.error):
        family = facility_family(building_id)
        return load_building_art(family) if family != building_id else None


def fallback_building(building_id):
    """Keep buildings recognizable and selectable when an asset is unavailable."""
    building_id = facility_family(building_id)
    image = pg.Surface((120, 110), pg.SRCALPHA)
    if building_id == "space_hub":
        pg.draw.polygon(image, (51, 75, 88), [(4, 80), (59, 56), (116, 80), (61, 108)])
        for x, y in ((18, 48), (76, 48)):
            pg.draw.rect(image, (98, 119, 137), (x, y, 26, 36), border_radius=5)
            pg.draw.ellipse(image, (136, 162, 175), (x-2, y-8, 30, 17))
            for offset in (7, 17):
                pg.draw.line(image, (236, 186, 106), (x+offset, y+7), (x+offset, y+26), 3)
        pg.draw.rect(image, (42, 73, 94), (44, 39, 32, 49), border_radius=5)
        pg.draw.ellipse(image, (91, 209, 221), (40, 25, 40, 24))
        pg.draw.ellipse(image, (183, 246, 236), (46, 30, 28, 11), 2)
        pg.draw.line(image, (235, 208, 142), (61, 27), (61, 10), 3)
        pg.draw.circle(image, (192, 240, 245), (61, 8), 4)
        return image
    if building_id in ("geothermal_plant", "thermal_plant", "singularity_plant"):
        pg.draw.polygon(image, (59, 84, 98), [(5, 78), (60, 55), (115, 78), (60, 107)])
        pg.draw.polygon(image, (33, 51, 66), [(5, 78), (60, 107), (115, 78), (115, 86), (60, 110), (5, 86)])
        if building_id == "singularity_plant":
            pg.draw.rect(image, (91, 114, 137), (25, 65, 70, 20), border_radius=5)
            pg.draw.circle(image, (98, 76, 145), (60, 42), 33, 8)
            pg.draw.circle(image, (167, 134, 236), (60, 42), 24, 3)
            pg.draw.circle(image, (9, 15, 30), (60, 42), 16)
            pg.draw.arc(image, (108, 223, 234), (16, 24, 88, 37), 0, 5.1, 4)
            for x in (20, 90):
                pg.draw.rect(image, (147, 165, 176), (x, 37, 10, 43))
        elif building_id == "geothermal_plant":
            for x, y in ((19, 45), (52, 27), (83, 43)):
                pg.draw.rect(image, (79, 113, 121), (x, y, 18, 45), border_radius=5)
                pg.draw.ellipse(image, (131, 187, 173), (x-3, y-8, 24, 15))
                pg.draw.line(image, (218, 155, 87), (x+9, y+10), (x+9, y+37), 4)
            pg.draw.lines(image, (167, 192, 184), False, [(29, 87), (29, 95), (92, 81), (92, 72)], 5)
        else:
            pg.draw.rect(image, (73, 91, 105), (23, 49, 72, 39))
            for x in (33, 70):
                pg.draw.rect(image, (139, 146, 145), (x, 15, 15, 46))
                pg.draw.rect(image, (219, 153, 71), (x-2, 13, 19, 7))
            for x in (32, 55, 78):
                pg.draw.rect(image, (238, 150, 64), (x, 64, 10, 17))
                pg.draw.line(image, (255, 220, 134), (x+4, 68), (x+4, 77), 2)
        return image
    if building_id in ("solar_array", "fusion_plant"):
        pg.draw.polygon(image, (59, 84, 98), [(5, 78), (60, 55), (115, 78), (60, 107)])
        if building_id == "solar_array":
            for x, y in ((9, 29), (47, 15), (45, 59)):
                pg.draw.line(image, (134, 153, 160), (x+18, y+19), (x+18, y+39), 4)
                pg.draw.polygon(image, (34, 86, 139), [(x, y), (x+35, y-9), (x+57, y+10), (x+21, y+21)])
                pg.draw.polygon(image, (129, 197, 231), [(x, y), (x+35, y-9), (x+57, y+10), (x+21, y+21)], 2)
                for offset in (10, 21, 32):
                    pg.draw.line(image, (76, 143, 190), (x+offset, y-2), (x+offset+19, y+16), 1)
        else:
            pg.draw.rect(image, (59, 86, 104), (32, 29, 56, 52))
            pg.draw.ellipse(image, (111, 152, 175), (32, 13, 56, 32))
            for y in (35, 48, 61):
                pg.draw.ellipse(image, (94, 217, 235), (29, y, 62, 22), 3)
            pg.draw.ellipse(image, (197, 244, 252), (43, 18, 34, 18))
            pg.draw.rect(image, (190, 167, 111), (52, 75, 16, 15))
        return image
    if building_id in ("missile_base", "planetary_shield", "sensor_array", "jump_gate", "interdictor"):
        metal, light, dark = (78, 107, 124), (126, 215, 224), (24, 46, 60)
        pg.draw.polygon(image, metal, [(5, 78), (61, 55), (115, 78), (60, 106)])
        pg.draw.polygon(image, dark, [(5, 78), (60, 98), (115, 78), (115, 86), (60, 110), (5, 86)])
        if building_id == "planetary_shield":
            pg.draw.rect(image, metal, (47, 46, 26, 43))
            pg.draw.arc(image, (*light, 200), (11, 14, 98, 109), 0, 3.14, 4)
            pg.draw.arc(image, light, (34, 14, 52, 109), 0, 3.14, 2)
            pg.draw.ellipse(image, light, (11, 68, 98, 28), 2)
            pg.draw.circle(image, (228, 211, 151), (60, 46), 9)
        elif building_id == "sensor_array":
            pg.draw.line(image, metal, (56, 80), (66, 34), 12)
            pg.draw.arc(image, light, (26, 8, 75, 65), 3.14, 6.28, 10)
            pg.draw.line(image, light, (64, 43), (87, 15), 3)
            pg.draw.circle(image, (233, 208, 147), (87, 15), 4)
        elif building_id == "jump_gate":
            pg.draw.ellipse(image, metal, (28, 5, 64, 91), 10)
            pg.draw.ellipse(image, light, (36, 12, 48, 76), 3)
            for y in (24, 44, 64):
                pg.draw.line(image, (55, 118, 143), (46, y), (75, y+8), 2)
        elif building_id == "interdictor":
            pg.draw.polygon(image, metal, [(36, 88), (54, 16), (66, 16), (86, 88)])
            for y in (30, 46, 62):
                pg.draw.ellipse(image, (195, 143, 225), (17, y, 88, 20), 3)
            pg.draw.circle(image, light, (60, 14), 7)
        else:
            for x, y in ((22, 43), (47, 55), (72, 39)):
                pg.draw.rect(image, metal, (x, y, 22, 31))
                pg.draw.polygon(image, light, [(x, y), (x+11, y-25), (x+22, y)])
        return image
    if building_id in ("barracks", "fortifications"):
        pg.draw.polygon(image, (50, 65, 69), [(4, 74), (57, 41), (117, 68), (65, 109)])
        if building_id == "barracks":
            for x, y in ((12, 54), (43, 36), (72, 52)):
                pg.draw.rect(image, (72, 93, 100), (x, y, 30, 34))
                pg.draw.polygon(image, (119, 145, 148), [(x-2, y), (x+15, y-10), (x+32, y), (x+15, y+8)])
                pg.draw.rect(image, (22, 40, 47), (x+11, y+15, 9, 19))
                pg.draw.rect(image, (140, 214, 204), (x+3, y+10, 5, 4))
            pg.draw.line(image, (180, 195, 185), (64, 14), (64, 60), 2)
            pg.draw.polygon(image, (214, 173, 92), [(65, 15), (91, 20), (65, 28)])
        else:
            pg.draw.polygon(image, (83, 100, 107), [(12, 69), (59, 45), (107, 68), (107, 86), (61, 104), (12, 85)])
            for x, y in ((12, 51), (44, 31), (81, 49)):
                pg.draw.rect(image, (98, 116, 121), (x, y, 23, 35))
                pg.draw.rect(image, (148, 163, 164), (x-3, y-5, 29, 12))
                pg.draw.rect(image, (29, 47, 55), (x+6, y+13, 11, 6))
                pg.draw.line(image, (187, 167, 122), (x+12, y+1), (x+28, y-9), 5)
            pg.draw.rect(image, (25, 40, 48), (48, 79, 19, 22))
        return image
    if building_id == "hydroponic_farm":
        pg.draw.polygon(image, (64, 88, 88), [(5, 66), (62, 37), (116, 61), (60, 103)])
        pg.draw.polygon(image, (36, 54, 64), [(5, 66), (60, 103), (60, 109), (5, 73)])
        pg.draw.polygon(image, (24, 43, 55), [(60, 103), (116, 61), (116, 69), (60, 109)])
        for x, y in ((15, 37), (44, 25), (72, 12)):
            pg.draw.rect(image, (55, 117, 106), (x, y+17, 24, 43))
            pg.draw.ellipse(image, (108, 181, 170), (x, y, 24, 36))
            for offset in (7, 18, 29):
                pg.draw.line(image, (44, 79, 93), (x+2, y+21+offset), (x+22, y+21+offset), 2)
                pg.draw.line(image, (142, 181, 91), (x+5, y+24+offset), (x+19, y+24+offset), 2)
            pg.draw.line(image, (165, 207, 191), (x+12, y+3), (x+12, y+57), 2)
        return image
    roof = [(13, 56), (65, 36), (110, 53), (58, 74)]
    pg.draw.polygon(image, (122, 139, 147), roof)
    pg.draw.polygon(image, (62, 81, 94), [(13, 56), (58, 74), (58, 103), (13, 85)])
    pg.draw.polygon(image, (43, 62, 75), [(58, 74), (110, 53), (110, 82), (58, 103)])
    for x, y in ((22, 68), (38, 74), (67, 78), (84, 71), (100, 65)):
        pg.draw.rect(image, (119, 194, 207), (x, y, 5, 8))
    if building_id in ("headquarters", "mine"):
        pg.draw.rect(image, (151, 167, 170), (53, 9, 19, 55))
        pg.draw.line(image, (119, 194, 207), (62, 13), (62, 56), 3)
    elif building_id == "factory":
        for x in (48, 73):
            pg.draw.rect(image, (140, 151, 156), (x, 17, 10, 40))
    elif building_id == "research_lab":
        pg.draw.circle(image, (107, 164, 193), (62, 43), 24)
    elif building_id == "shipyard":
        pg.draw.rect(image, (14, 30, 42), (64, 73, 26, 18))
    return image


@lru_cache(maxsize=96)
def building_sprite(building_id, size):
    source = load_building_art(building_id)
    if source is None:
        source = fallback_building(building_id)
    fit = source.get_rect().fit(pg.Rect((0, 0), size))
    sprite = pg.transform.smoothscale(source, fit.size)
    family = facility_family(building_id)
    if family != building_id:
        # Small lit plates distinguish higher facility levels at every icon size.
        level = FACILITY_FAMILIES[family].index(building_id)
        color = (102, 218, 233) if level == 1 else (227, 186, 97)
        width, height = sprite.get_size()
        plate = max(3, width//10)
        for i in range(level+1):
            pg.draw.rect(sprite, color, (width//2+(i-level/2)*(plate+2), height*.72, plate, max(3, height//15)))
    return sprite


def draw_building_art(surface, building_id, rect, *, alpha=255):
    rect = pg.Rect(rect)
    sprite = building_sprite(building_id, rect.size)
    if alpha != 255:
        sprite = sprite.copy()
        sprite.set_alpha(alpha)
    placed = sprite.get_rect(midbottom=rect.midbottom)
    surface.blit(sprite, placed)
    return placed
