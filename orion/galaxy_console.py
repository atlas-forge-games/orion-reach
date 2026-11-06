"""Native-resolution console furniture for the galaxy workspace.

Frames are drawn at their final pixel size and cached. The transparent chart
frame occupies the existing gutter; it never resamples the map or its labels.
"""

from functools import lru_cache

import pygame as pg

from .command_buttons import command_icon
from .display import Canvas
from .ui import CYAN, FAINT, GOLD, INK, MUTED, font, shorten, text

DIVIDER = (55, 75, 85)


def _outline(rect, cut):
    x, y, w, h = rect
    right, bottom = x+w-1, y+h-1
    cut = min(cut, max(0, w//3), max(0, h//3))
    return [(x+cut, y), (right-cut, y), (right, y+cut),
            (right, bottom-cut), (right-cut, bottom), (x+cut, bottom),
            (x, bottom-cut), (x, y+cut)]


def _gradient(surface, rect, top, bottom):
    for y in range(rect.h):
        blend = y/max(1, rect.h-1)
        color = tuple(round(a+(b-a)*blend) for a, b in zip(top, bottom))
        pg.draw.line(surface, color, (rect.x, rect.y+y), (rect.right-1, rect.y+y))


@lru_cache(maxsize=32)
def _frame_image(size, scale, filled, accent, primary, active, enabled, compact):
    image = pg.Surface(size, pg.SRCALPHA)
    r = image.get_rect()
    unit = lambda value: max(1, round(value*scale))
    cut, rim = unit(5 if compact else 13), unit(2 if compact else 5)
    points = _outline(r, cut)
    metal_top = (243, 208, 145) if primary else (96, 116, 127) if active else (67, 84, 94)
    metal_bottom = (117, 82, 33) if primary else (32, 49, 60)
    if not enabled:
        metal_top, metal_bottom = (47, 62, 72), (24, 36, 45)
    _gradient(image, r, metal_top, metal_bottom)
    mask = pg.Surface(size, pg.SRCALPHA)
    pg.draw.polygon(mask, (255, 255, 255, 255), points)
    image.blit(mask, (0, 0), special_flags=pg.BLEND_RGBA_MULT)
    pg.draw.aalines(image, (151, 173, 183) if active else (85, 105, 116), True, points)
    inner = r.inflate(-2*rim, -2*rim)
    inner_points = _outline(inner, max(unit(2), cut-rim))
    if filled:
        face = pg.Surface(size, pg.SRCALPHA)
        if primary:
            top, bottom = ((255, 224, 163), (200, 153, 79)) if active else ((240, 204, 139), (175, 126, 59))
        else:
            top, bottom = ((29, 52, 64), (11, 27, 38)) if active else ((19, 35, 45), (6, 17, 25))
        if not enabled:
            top, bottom = (19, 27, 32), (9, 17, 23)
        _gradient(face, inner, top, bottom)
        mask.fill((0, 0, 0, 0))
        pg.draw.polygon(mask, (255, 255, 255, 255), inner_points)
        face.blit(mask, (0, 0), special_flags=pg.BLEND_RGBA_MULT)
        image.blit(face, (0, 0))
    else:
        pg.draw.polygon(image, (0, 0, 0, 0), inner_points)
    pg.draw.aalines(image, (14, 23, 29) if not primary else (97, 70, 34), True, inner_points)
    # A narrow lit bevel reads as metal, with two restrained corner lights.
    pg.draw.line(image, (191, 208, 214) if not primary else (255, 234, 186),
                 (cut, unit(1)), (r.right-cut-unit(1), unit(1)))
    if enabled:
        color = GOLD if primary else accent
        length = min(unit(24), max(unit(4), r.w//7))
        inset = unit(2)
        pg.draw.lines(image, color, False,
                      [(inset, cut+length), (inset, cut), (cut, inset), (cut+length, inset)], unit(1))
        if not compact:
            pg.draw.lines(image, color, False,
                          [(r.right-cut-length, r.bottom-inset-1),
                           (r.right-cut-1, r.bottom-inset-1),
                           (r.right-inset-1, r.bottom-cut-1)], unit(1))
    return image


def console_frame(surface, rect, *, filled=True, accent=CYAN, primary=False,
                  active=False, enabled=True, compact=False):
    r = pg.Rect(rect)
    native = surface.rect(r) if isinstance(surface, Canvas) else r
    if native.w <= 0 or native.h <= 0:
        return
    scale = surface.scale if isinstance(surface, Canvas) else 1.0
    image = _frame_image(native.size, scale, filled, tuple(accent), primary, active, enabled, compact)
    pg.Surface.blit(surface, image, native.topleft)


def console_panel(surface, rect, *, accent=CYAN):
    console_frame(surface, pg.Rect(rect).inflate(10, 10), accent=accent)


def header_plate(surface, rect, label, *, color=GOLD, size=14):
    """An angled title plate with enough room for separate status/close controls."""
    r = pg.Rect(rect)
    width = min(r.w, font(size, "sans_bold").size(label)[0]+28)
    points = [(r.x+8, r.y), (r.x+width, r.y), (r.x+width-10, r.bottom), (r.x, r.bottom), (r.x, r.y+8)]
    pg.draw.polygon(surface, (37, 34, 26), points)
    pg.draw.lines(surface, (128, 112, 76), False, points[:4], 1)
    text(surface, shorten(label, width-24, size, "sans_bold"),
         (r.x+12, r.centery-font(size, "sans_bold").get_height()//2), size, color, "sans_bold")


def console_row(surface, rect, *, active=False, selected=False, owner=None):
    r = pg.Rect(rect)
    if active or selected:
        pg.draw.rect(surface, (24, 48, 59) if active else (14, 35, 46), r)
    pg.draw.line(surface, DIVIDER, (r.x, r.bottom-1), (r.right, r.bottom-1))
    if owner is not None:
        pg.draw.line(surface, owner, (r.x+1, r.y+7), (r.x+1, r.bottom-8), 3)
    if active:
        pg.draw.line(surface, CYAN, (r.x, r.y), (r.right, r.y))


def _icon(surface, name, pos, size, color):
    scale = surface.scale if isinstance(surface, Canvas) else 1.0
    image = command_icon(name, max(1, round(size*scale)), tuple(color))
    if isinstance(surface, Canvas):
        surface.blit_native(image, pos)
    else:
        surface.blit(image, pos)


def draw_console_button(button, surface, active=False, pressed=False):
    r = button.rect
    active = button.enabled and (active or button.style == "console_active")
    if button.style == "console_hotspot":
        if active:
            pg.draw.line(surface, CYAN, (r.x+10, r.bottom-1), (r.right-10, r.bottom-1), 2)
        return
    primary = button.style == "console_primary"
    compact = r.h < 45
    console_frame(surface, r, primary=primary, active=active,
                  enabled=button.enabled, compact=compact,
                  accent=CYAN if active or button.style == "console_dock" else (69, 128, 150))
    shift = 1 if pressed and button.enabled else 0
    color = FAINT if not button.enabled else (24, 25, 22) if primary else INK
    icon_color = color if primary else (89, 229, 255) if button.enabled else (90, 112, 124)
    if button.style == "console_dock":
        horizontal = r.w >= 145
        icon_size = 26 if horizontal else 22
        icon_pos = (r.x+13, r.centery-6+shift) if horizontal else (r.centerx-icon_size//2, r.y+7+shift)
        _icon(surface, button.icon, icon_pos, icon_size, icon_color)
        size, family = 14, "sans_bold"
        label = shorten(button.label, r.w-(54 if horizontal else 14), size, family)
        left = r.x+46 if horizontal else r.centerx-font(size, family).size(label)[0]//2
        text(surface, label, (left, r.y+(29 if horizontal else 33)+shift), size, color, family)
    elif primary:
        left = r.x+14
        if button.icon:
            _icon(surface, button.icon, (left, r.centery-14+shift), 28, icon_color)
            left += 39
        size = 21 if r.h >= 48 else 14
        room = r.right-left-(38 if button.shortcut else 12)
        label = shorten(button.label, room, size, "sans_bold")
        top = r.y+9 if button.subtitle else r.centery-font(size, "sans_bold").get_height()//2
        text(surface, label, (left, top+shift), size, color, "sans_bold")
        if button.subtitle:
            text(surface, shorten(button.subtitle, room, 14), (left, r.bottom-23+shift), 14, color)
    else:
        size, family = 14, "sans" if button.style in ("console_tool", "console_active") else "sans_bold"
        padding = 4 if r.w < 80 else 6 if compact else 12
        left = r.x+padding
        if button.icon:
            _icon(surface, button.icon, (left, r.centery-10+shift), 20, icon_color)
            left += 29
        label = shorten(button.label, r.right-left-padding, size, family)
        if not button.icon:
            left = r.centerx-font(size, family).size(label)[0]//2
        text(surface, label, (left, r.centery-font(size, family).get_height()//2+shift), size, color, family)
    if button.shortcut:
        text(surface, button.shortcut, (r.right-12, r.y+7+shift), 14,
             color if primary else MUTED, "mono", right=True)
    if button.badge:
        width = font(14, "sans_bold").size(button.badge)[0]+10
        badge = pg.Rect(r.x+7, r.y+4, width, 19)
        pg.draw.rect(surface, GOLD, badge, border_radius=3)
        text(surface, button.badge, (badge.x+5, badge.y), 14, (24, 25, 22), "sans_bold")
