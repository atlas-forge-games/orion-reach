"""Small reusable drawing helpers, with explicit focus and hit regions."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable
import pygame as pg

ASSETS = Path(__file__).resolve().parents[1] / "assets"
INK = (242, 247, 251)
MUTED = (194, 207, 217)
FAINT = (162, 180, 194)
GOLD = (236, 199, 137)
CYAN = (112, 211, 255)
RIVAL_COLOR = (250, 168, 111)
LINE = (50, 72, 88)
PANEL = (12, 24, 35)
RED = (255, 157, 145)

# All screens, including older views, share a readable lower bound. Pixel fonts
# are kept separate: a 14px logical label can rasterize at 12px in a small window.
MIN_TEXT_SIZE = 14
TEXT_SMALL = 16
TEXT_BODY = 18
TEXT_LABEL = 17
TEXT_VALUE = 28


@lru_cache(maxsize=128)
def _pixel_font(size, family="sans"):
    filename = {"sans": "DejaVuSans.ttf", "mono": "DejaVuSansMono.ttf",
                "mono_bold": "DejaVuSansMono.ttf", "title": "DejaVuSerif.ttf"}[family]
    face = pg.font.Font(str(ASSETS / "fonts" / filename), size)
    face.set_bold(family == "mono_bold")
    return face


def font(size, family="sans"):
    return _pixel_font(max(MIN_TEXT_SIZE, round(size)), family)


font.cache_clear = _pixel_font.cache_clear


@lru_cache(maxsize=768)
def _pixel_text_image(value, size, color, family="sans", spacing=0):
    f = _pixel_font(size, family)
    if not spacing:
        return f.render(value, True, color)
    pieces = [f.render(c, True, color) for c in value]
    width = sum(p.get_width() for p in pieces) + max(0,len(pieces)-1)*spacing
    img = pg.Surface((max(1,width), f.get_linesize()), pg.SRCALPHA)
    x = 0
    for piece in pieces:
        img.blit(piece,(x,0))
        x += piece.get_width()+spacing
    return img


def text_image(value, size, color, family="sans", spacing=0):
    return _pixel_text_image(str(value), max(MIN_TEXT_SIZE, round(size)), tuple(color),
                             family, min(spacing, 1) if size < MIN_TEXT_SIZE else spacing)


text_image.cache_clear = _pixel_text_image.cache_clear


class ShortenedText(str):
    """Keep the original label available when a narrow column needs an ellipsis."""
    def __new__(cls, value, full_text):
        result = super().__new__(cls, value)
        result.full_text = full_text
        return result


def text(surface, value, pos, size=18, color=INK, family="sans", spacing=0, right=False):
    from .display import Canvas
    if size < MIN_TEXT_SIZE:
        spacing = min(spacing, 1)
    size = max(MIN_TEXT_SIZE, round(size))
    img = text_image(str(value),size,tuple(color),family,spacing)
    x, y = pos
    if right:
        x -= img.get_width()
    if isinstance(surface, Canvas):
        native = _pixel_text_image(str(value), max(1, round(size*surface.scale)), tuple(color),
                                   family, round(spacing*surface.scale))
        if right:
            # Align by the actual native glyph width, avoiding rounding drift.
            native_pos = surface.point(pos)
            pg.Surface.blit(surface, native, (native_pos[0]-native.get_width(), native_pos[1]))
        else:
            surface.blit_native(native, (x, y))
    else:
        surface.blit(img,(int(x),int(y)))
    rect = img.get_rect(topleft=(int(x),int(y)))
    if isinstance(value, ShortenedText) and hasattr(surface, 'text_regions'):
        visible = rect.clip(surface.get_clip())
        if visible.w and visible.h:
            surface.text_regions.append((visible, value.full_text))
    return rect


def shorten(value, width, size=18, family="sans"):
    supplied = value
    original = getattr(value, 'full_text', str(value))
    value = str(value)
    f = font(size,family)
    if f.size(value)[0] <= width:
        return supplied if isinstance(supplied, ShortenedText) else value
    while value and f.size(value+"…")[0] > width:
        value=value[:-1]
    return ShortenedText(value+"…" if f.size("…")[0] <= width else "", original)


def wrapped_lines(value, width, size=18):
    lines=[]
    line=""
    f=font(size)
    words=[]
    for token in value.split():
        # Long names and numeric identifiers must also stay inside their column.
        while token and f.size(token)[0] > width:
            lo,hi=1,len(token)
            while lo < hi:
                mid=(lo+hi+1)//2
                if f.size(token[:mid])[0] <= width:
                    lo=mid
                else:
                    hi=mid-1
            words.append(token[:lo])
            token=token[lo:]
        if token:
            words.append(token)
    for word in words:
        attempt=(line+" "+word).strip()
        if f.size(attempt)[0] > width and line:
            lines.append(line)
            line=word
        else:
            line=attempt
    if line:
        lines.append(line)
    return lines


def paragraph(surface, value, pos, width, size=18, color=MUTED, leading=30):
    x,y=pos
    leading=max(leading,font(size).get_linesize()+2)
    for line in wrapped_lines(value,width,size):
        text(surface,line,(x,y),size,color)
        y+=leading
    return y


def draw_text_tooltip(app):
    """Reveal abbreviated labels after a short hover, inside the visible view."""
    app.text_tooltip_rect = None
    target = next(((tuple(rect), value) for rect, value in reversed(app.canvas.text_regions)
                   if rect.collidepoint(app.mouse)), None)
    if app.keyboard_mode or target is None:
        app.text_hover = None
        return
    previous = getattr(app, 'text_hover', None)
    if previous is None or previous[0] != target:
        app.text_hover = (target, app.time)
        return
    if app.time-previous[1] < .4:
        return
    scale = app.canvas.scale
    visible = pg.Rect(-app.viewport.x/scale, -app.viewport.y/scale,
                      app.window.get_width()/scale, app.window.get_height()/scale)
    visible = visible.clip(app.canvas.get_rect()).inflate(-24, -24)
    width = min(520, visible.w-24)
    lines = wrapped_lines(target[1], width, TEXT_SMALL)
    height = len(lines)*22+20
    rect = pg.Rect(app.mouse[0]+16, app.mouse[1]+24, width+24, height)
    if rect.bottom > visible.bottom:
        rect.bottom = app.mouse[1]-12
    rect.clamp_ip(visible)
    panel(app.canvas, rect, PANEL, GOLD)
    for i, line in enumerate(lines):
        text(app.canvas, line, (rect.x+12, rect.y+10+i*22), TEXT_SMALL)
    app.text_tooltip_rect = rect


def panel(surface, rect, fill=PANEL, border=LINE):
    pg.draw.rect(surface,fill,rect,border_radius=3)
    pg.draw.rect(surface,border,rect,1,border_radius=3)


def arrow(surface, pos, color=GOLD, back=False):
    x,y=pos
    sign=-1 if back else 1
    pg.draw.line(surface,color,(x-8*sign,y),(x+8*sign,y),1)
    pg.draw.lines(surface,color,False,[(x+3*sign,y-5),(x+8*sign,y),(x+3*sign,y+5)],1)


def emblem(surface, x, y, scale=1.0, color=GOLD):
    points=[(0,-17),(12,8),(0,3),(-12,8)]
    pg.draw.polygon(surface,color,[(x+px*scale,y+py*scale) for px,py in points],1)
    pg.draw.circle(surface,color,(int(x),int(y)),int(24*scale),1)
    pg.draw.line(surface,color,(x,y-29*scale),(x,y-21*scale),1)
    pg.draw.line(surface,color,(x,y+21*scale),(x,y+29*scale),1)


@dataclass
class Button:
    key: str
    label: str
    rect: pg.Rect
    action: Callable
    subtitle: str = ""
    style: str = "normal"
    enabled: bool = True
    icon: str = ""
    shortcut: str = ""
    badge: str = ""

    def draw(self,surface,active=False,pressed=False):
        if self.style in ("title_primary", "title_menu"):
            from .title_screen import draw_title_button
            draw_title_button(self,surface,active,pressed)
            return
        if self.style in ("command", "command_primary", "command_dock"):
            from .command_buttons import draw_command_button
            draw_command_button(self,surface,active,pressed)
            return
        r=self.rect
        color=INK if self.enabled else FAINT
        if self.style=="hotspot":
            if active and self.enabled:
                pg.draw.rect(surface,GOLD,r,1,border_radius=4)
            return
        if self.style in ("tab", "tab_active"):
            selected=self.style=="tab_active"
            panel(surface,r,(27,43,51) if selected or active else PANEL,GOLD if selected or active else LINE)
            size=11 if r.h < 24 else 13 if r.h < 36 else 16
            label=shorten(self.label,r.w-12,size)
            shade=GOLD if selected or active else color
            text(surface,label,(r.centerx-font(size).size(label)[0]//2,r.centery-font(size).get_height()//2),size,shade)
        elif self.style=="primary":
            pg.draw.rect(surface,(233,205,153) if active else GOLD,r,border_radius=2)
            if r.h < 48:
                text(surface,shorten(self.label,r.w-55,14),(r.x+14,r.centery-font(14).get_height()//2),14,(17,27,32))
            else:
                text(surface,shorten(self.label,r.w-76,20),(r.x+24,r.centery-font(20).get_height()//2),20,(17,27,32))
            arrow(surface,(r.right-28,r.centery),(17,27,32))
        elif self.style=="menu":
            if active:
                pg.draw.rect(surface,(18,33,42),r,border_radius=2)
            pg.draw.line(surface,LINE,(r.left,r.bottom),(r.right,r.bottom))
            text(surface,shorten(self.label,r.w-76,23),(r.x+24,r.y+12),23,GOLD if active else color)
            if self.subtitle:
                text(surface,shorten(self.subtitle,r.w-76,14),(r.x+24,r.y+42),14,MUTED)
            arrow(surface,(r.right-28,r.centery),GOLD if active else FAINT)
        elif self.style=="ghost":
            text(surface,shorten(self.label,r.w-28,15),(r.x+14,r.centery-font(15).get_height()//2),15,GOLD if active else color)
            if active:
                pg.draw.line(surface,GOLD,(r.x+14,r.bottom-7),(r.right-14,r.bottom-7))
        else:
            panel(surface,r,(23,38,46) if active else PANEL,GOLD if active else LINE)
            size = 14 if r.h < 32 or r.w < 120 else 17
            padding = 6 if r.w < 80 else 10 if r.w < 140 else 12 if r.h < 32 else 18
            label = shorten(self.label,r.w-2*padding,size)
            left = r.centerx-font(size).size(label)[0]//2 if r.w < 80 else r.x+padding
            text(surface,label,(left,r.centery-font(size).get_height()//2),size,GOLD if active else color)
        if active and self.enabled:
            pg.draw.rect(surface,GOLD,r.inflate(6,6),1,border_radius=3)
