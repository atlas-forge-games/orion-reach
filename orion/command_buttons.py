"""Beveled command controls and scalable, code-drawn navigation icons."""

from functools import lru_cache
import math

import pygame as pg

from .ui import CYAN, FAINT, GOLD, INK, MUTED, font, shorten, text


def blend(a, b, amount):
    return tuple(round(x+(y-x)*amount) for x, y in zip(a, b))


def bevel_points(rect, cut=7):
    r = pg.Rect(rect)
    return [(r.left, r.top), (r.right-cut-1, r.top), (r.right-1, r.top+cut),
            (r.right-1, r.bottom-1), (r.left+cut, r.bottom-1), (r.left, r.bottom-cut-1)]


@lru_cache(maxsize=128)
def command_frame(size, primary, active, pressed, enabled):
    """Cache the gradients and bevels; only text and focus change each frame."""
    width, height = size
    frame = pg.Surface((width, height), pg.SRCALPHA)
    if not enabled:
        top, bottom, edge = (20, 30, 37), (10, 18, 25), (45, 60, 69)
    elif primary:
        top, bottom, edge = (225, 195, 141), (177, 132, 76), (243, 216, 164)
        if active:
            top, bottom, edge = (245, 220, 171), (204, 161, 102), (255, 234, 195)
    else:
        top, bottom, edge = (29, 46, 58), (12, 24, 33), (64, 88, 101)
        if active:
            top, bottom, edge = (40, 66, 79), (18, 39, 51), GOLD
    if pressed and enabled:
        top, bottom = blend(bottom, (4, 10, 15), .15), blend(top, bottom, .65)
    cut = 8 if height >= 50 else 6
    points = bevel_points(frame.get_rect(), cut)
    # A white alpha mask clips the gradient without changing its colours.
    for y in range(height):
        pg.draw.line(frame, (*blend(top, bottom, y/max(1, height-1)), 255), (0, y), (width-1, y))
    mask = pg.Surface((width, height), pg.SRCALPHA)
    pg.draw.polygon(mask, (255, 255, 255, 255), points)
    frame.blit(mask, (0, 0), special_flags=pg.BLEND_RGBA_MULT)
    pg.draw.polygon(frame, edge, points, 1)
    inset = bevel_points(pg.Rect(2, 2, width-4, height-4), max(3, cut-2))
    pg.draw.lines(frame, blend(top, edge, .25), False, inset[:3], 1)
    pg.draw.lines(frame, blend(bottom, (0, 0, 0), .5), False, inset[3:]+[inset[0]], 1)
    # Fine edge marks give the controls the same instrument-panel vocabulary.
    rail = (79, 64, 41) if primary and enabled else GOLD if active and enabled else (89, 134, 149) if enabled else FAINT
    pg.draw.line(frame, rail, (12, height-2), (min(width-16, 43), height-2), 2)
    return frame


@lru_cache(maxsize=128)
def command_icon(name, size, color):
    """Draw at 3× resolution for clean small icons without new bitmap assets."""
    scale = 3
    canvas = pg.Surface((size*scale, size*scale), pg.SRCALPHA)
    unit = size*scale/32

    def point(xy):
        return tuple(round(v*unit) for v in xy)

    def line(points, closed=False, width=1.5, tint=color):
        pg.draw.lines(canvas, tint, closed, [point(p) for p in points], max(1, round(width*unit)))

    def circle(center, radius, width=1.5, tint=color):
        pg.draw.circle(canvas, tint, point(center), round(radius*unit), max(0, round(width*unit)))

    def filled(points, tint=color):
        pg.draw.polygon(canvas, tint, [point(p) for p in points])

    if name == "research":
        circle((16, 16), 2.3, 0)
        for angle in (0, math.pi/3, -math.pi/3):
            points = []
            for i in range(49):
                phase = i*math.tau/48
                x, y = 13*math.cos(phase), 5*math.sin(phase)
                points.append((16+x*math.cos(angle)-y*math.sin(angle), 16+x*math.sin(angle)+y*math.cos(angle)))
            line(points, width=1.15)
        circle((27, 16), 1.8, 0)
    elif name == "fleets":
        for x, y, length in ((16, 3, 19), (6, 15, 12), (26, 15, 12)):
            half = length*.29
            line([(x, y), (x+half, y+length), (x, y+length*.76), (x-half, y+length)], True)
    elif name == "diplomacy":
        line([(4, 7), (13, 7), (13, 15), (8, 18), (8, 15), (4, 15)], True)
        line([(19, 17), (28, 17), (28, 25), (24, 25), (24, 28), (19, 25)], True)
        line([(19, 6), (25, 6), (28, 9), (28, 12)])
        line([(25, 10), (28, 13), (30, 10)])
        line([(13, 26), (7, 26), (4, 23), (4, 20)])
        line([(2, 22), (4, 19), (7, 22)])
    elif name == "empire":
        line([(5, 28), (5, 16), (11, 16), (11, 28)])
        line([(13, 28), (13, 10), (19, 10), (19, 28)])
        line([(22, 28), (22, 19), (28, 19), (28, 28)])
        line([(2, 29), (30, 29)])
        line([(16, 9), (16, 2), (23, 4), (16, 6)])
    elif name == "objectives":
        circle((15, 17), 11)
        circle((15, 17), 6)
        circle((15, 17), 1.7, 0)
        line([(15, 17), (28, 4)])
        line([(22, 4), (28, 4), (28, 10)])
    elif name == "exploration":
        circle((16, 16), 11)
        line([(16, 1), (16, 5)])
        line([(16, 27), (16, 31)])
        line([(1, 16), (5, 16)])
        line([(27, 16), (31, 16)])
        filled([(22, 9), (19, 19), (9, 23), (13, 13)])
        line([(13, 13), (19, 19)], tint=(16, 29, 38))
    elif name == "info":
        line([(16, 8), (11, 5), (3, 5), (3, 25), (11, 25), (16, 28),
              (21, 25), (29, 25), (29, 5), (21, 5), (16, 8)], True)
        line([(16, 8), (16, 28)])
        for y in (11, 16, 21):
            line([(6, y), (11, y+1)], width=1.1)
            line([(21, y+1), (26, y)], width=1.1)
    elif name == "news":
        line([(5, 4), (23, 4), (23, 28), (5, 28)], True)
        line([(23, 10), (28, 10), (28, 26), (26, 28), (23, 28)])
        line([(9, 9), (19, 9)], width=2)
        line([(9, 14), (19, 14)])
        line([(9, 19), (19, 19)])
        line([(9, 23), (16, 23)])
    elif name == "save":
        line([(5, 4), (23, 4), (28, 9), (28, 28), (5, 28)], True)
        line([(10, 4), (10, 12), (22, 12), (22, 4)])
        line([(10, 28), (10, 19), (23, 19), (23, 28)])
        line([(19, 6), (19, 10)])
    elif name == "menu":
        for y in (8, 16, 24):
            circle((5, y), 1.5, 0)
            line([(11, y), (28, y)], width=1.7)
    elif name == "close":
        line([(8, 8), (24, 24)], width=1.8)
        line([(24, 8), (8, 24)], width=1.8)
    elif name == "turn":
        filled([(8, 6), (8, 26), (20, 16)])
        line([(21, 6), (30, 16), (21, 26)], width=2)
    elif name == "system":
        circle((16, 16), 4, 0)
        circle((16, 16), 11, 1)
        circle((25, 9), 2.5, 0)
        line([(3, 29), (11, 23)])
    elif name == "course":
        line([(3, 25), (11, 25), (20, 8), (28, 8)])
        circle((3, 25), 2)
        line([(23, 3), (28, 8), (23, 13)])
    return pg.transform.smoothscale(canvas, (size, size))


def draw_command_button(button, surface, active=False, pressed=False):
    r = button.rect
    enabled = button.enabled
    active, pressed = active and enabled, pressed and enabled
    primary = button.style == "command_primary"
    pg.draw.polygon(surface, (3, 9, 14), bevel_points(r.move(0, 3)))
    surface.blit(command_frame(r.size, primary, active, pressed, enabled), r)
    if active:
        pg.draw.polygon(surface, GOLD, bevel_points(r.inflate(4, 4)), 1)

    offset = 1 if pressed else 0
    if button.style == "command_dock":
        color = GOLD if active else INK if enabled else FAINT
        accent = GOLD if active else CYAN if enabled else FAINT
        surface.blit(command_icon(button.icon, 23, accent), (r.centerx-11, r.y+7+offset))
        label = shorten(button.label, r.w-14, 14)
        text(surface, label, (r.centerx-font(14).size(label)[0]//2, r.y+36+offset), 14, color)
        if button.shortcut:
            text(surface, button.shortcut, (r.right-10, r.y+8+offset), 9,
                 GOLD if active else MUTED if enabled else FAINT, "mono", right=True)
        if button.badge:
            width = max(20, font(9, "mono").size(button.badge)[0]+9)
            badge = pg.Rect(r.x+8, r.y+7+offset, width, 19)
            pg.draw.rect(surface, GOLD if enabled else FAINT, badge, border_radius=5)
            text(surface, button.badge, (badge.centerx-font(9, "mono").size(button.badge)[0]//2,
                                         badge.y+3), 9, (28, 29, 28), "mono")
        return
    dark_ink = (28, 29, 28)
    label_color = dark_ink if primary and enabled else INK if enabled else FAINT
    accent = dark_ink if primary and enabled else GOLD if active else CYAN if enabled else FAINT
    icon_size = 29 if primary else 27 if r.h >= 50 else 22
    icon_x = r.x+(21 if primary else 14)
    icon_y = r.centery-icon_size//2+offset
    if button.icon:
        if r.h >= 50:
            well = pg.Rect(icon_x-6, r.centery-21+offset, icon_size+12, 42)
            fill = (166, 126, 72) if primary and enabled else (12, 24, 32)
            border = (192, 152, 94) if primary and enabled else (43, 65, 78)
            pg.draw.polygon(surface, fill, bevel_points(well, 5))
            pg.draw.polygon(surface, border, bevel_points(well, 5), 1)
        surface.blit(command_icon(button.icon, icon_size, accent), (icon_x, icon_y))
    left = icon_x+icon_size+(18 if primary else 12) if button.icon else r.x+16
    right = r.right-14
    if button.shortcut:
        key_width = max(23, font(10, "mono").size(button.shortcut)[0]+12)
        key = pg.Rect(right-key_width, r.centery-11+offset, key_width, 22)
        pg.draw.rect(surface, (235, 204, 153) if primary and enabled else (9, 20, 28), key, border_radius=3)
        pg.draw.rect(surface, (108, 81, 49) if primary and enabled else (72, 92, 103) if active else (45, 67, 80), key, 1, border_radius=3)
        text(surface, button.shortcut, (key.x+(key.w-font(10, "mono").size(button.shortcut)[0])//2, key.y+4),
             10, dark_ink if primary and enabled else GOLD if active else MUTED if enabled else FAINT, "mono")
        right = key.left-10
    if button.badge:
        value = button.badge
        badge_width = max(22, font(10, "mono").size(value)[0]+12)
        badge = pg.Rect(right-badge_width, r.centery-11+offset, badge_width, 22)
        pg.draw.rect(surface, GOLD if enabled else FAINT, badge, border_radius=6)
        text(surface, value, (badge.x+(badge.w-font(10, "mono").size(value)[0])//2, badge.y+4), 10, dark_ink, "mono")
        right = badge.left-8
    size = 21 if primary else 15 if r.h >= 50 else 14
    top = r.y+10 if button.subtitle else r.centery-font(size).get_height()//2
    text(surface, shorten(button.label, max(1, right-left), size), (left, top+offset), size, label_color)
    if button.subtitle:
        text(surface, shorten(button.subtitle, max(1, right-left), 10), (left, r.bottom-23+offset), 10,
             dark_ink if primary and enabled else MUTED if enabled else FAINT)
