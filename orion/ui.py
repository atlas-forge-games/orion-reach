"""Small reusable drawing helpers, with explicit focus and hit regions."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable
import pygame as pg

ASSETS = Path(__file__).resolve().parents[1] / "assets"
INK = (232, 235, 228)
MUTED = (133, 151, 160)
FAINT = (77, 98, 112)
GOLD = (215, 182, 125)
CYAN = (119, 194, 207)
LINE = (38, 57, 68)
PANEL = (10, 20, 29)
RED = (235, 140, 130)


@lru_cache(maxsize=64)
def font(size, family="sans"):
    filename = {"sans": "DejaVuSans.ttf", "mono": "DejaVuSansMono.ttf", "title": "DejaVuSerif.ttf"}[family]
    return pg.font.Font(str(ASSETS / "fonts" / filename), size)


@lru_cache(maxsize=768)
def text_image(value, size, color, family="sans", spacing=0):
    f = font(size, family)
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


def text(surface, value, pos, size=18, color=INK, family="sans", spacing=0, right=False):
    img = text_image(str(value),size,tuple(color),family,spacing)
    x, y = pos
    if right:
        x -= img.get_width()
    surface.blit(img,(int(x),int(y)))
    return img.get_rect(topleft=(int(x),int(y)))


def shorten(value, width, size=18, family="sans"):
    value = str(value)
    f = font(size,family)
    if f.size(value)[0] <= width:
        return value
    while value and f.size(value+"…")[0] > width:
        value=value[:-1]
    return value+"…"


def paragraph(surface, value, pos, width, size=18, color=MUTED, leading=30):
    x,y=pos
    line=""
    for word in value.split():
        attempt=(line+" "+word).strip()
        if font(size).size(attempt)[0] > width and line:
            text(surface,line,(x,y),size,color)
            y+=leading
            line=word
        else:
            line=attempt
    if line:
        text(surface,line,(x,y),size,color)
        y+=leading
    return y


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

    def draw(self,surface,active=False):
        r=self.rect
        color=INK if self.enabled else FAINT
        if self.style=="hotspot":
            if active and self.enabled:
                pg.draw.rect(surface,GOLD,r,1,border_radius=4)
            return
        if self.style=="primary":
            pg.draw.rect(surface,(233,205,153) if active else GOLD,r,border_radius=2)
            text(surface,self.label,(r.x+24,r.y+16),20,(17,27,32))
            arrow(surface,(r.right-28,r.centery),(17,27,32))
        elif self.style=="menu":
            if active:
                pg.draw.rect(surface,(18,33,42),r,border_radius=2)
            pg.draw.line(surface,LINE,(r.left,r.bottom),(r.right,r.bottom))
            text(surface,self.label,(r.x+24,r.y+12),23,GOLD if active else color)
            if self.subtitle:
                text(surface,self.subtitle,(r.x+24,r.y+42),12,MUTED)
            arrow(surface,(r.right-28,r.centery),GOLD if active else FAINT)
        elif self.style=="ghost":
            text(surface,self.label,(r.x+14,r.y+13),15,GOLD if active else color)
            if active:
                pg.draw.line(surface,GOLD,(r.x+14,r.bottom-7),(r.right-14,r.bottom-7))
        else:
            panel(surface,r,(23,38,46) if active else PANEL,GOLD if active else LINE)
            text(surface,self.label,(r.x+18,r.y+(r.h-25)//2),17,GOLD if active else color)
        if active and self.enabled:
            pg.draw.rect(surface,GOLD,r.inflate(6,6),1,border_radius=3)
