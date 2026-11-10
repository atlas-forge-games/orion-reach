"""Galaxy name styling based only on the player's current or stored survey."""

from functools import lru_cache
from math import ceil
import pygame as pg

from .empires import DEFAULT_PALETTE, EMPIRE_IDS, empire_color
from .ui import FAINT, INK, MUTED, _pixel_font, font, text
from .display import Canvas
from . import black_holes, motherships

LABEL_SIZE = 13
LABEL_FAMILY = "mono_bold"
ATLAS_LABEL_SIZE = 16 * .7


def label_font(style="classic"):
    return (ATLAS_LABEL_SIZE, "sans_bold") if style == "clean" else (LABEL_SIZE, LABEL_FAMILY)


@lru_cache(maxsize=512)
def atlas_label(label, pixels):
    """Rasterize type and its quiet dark outline directly at the display size."""
    glyphs = _pixel_font(pixels, "sans_bold").render(label, True, INK)
    edge = max(1, round(pixels/ATLAS_LABEL_SIZE))
    image = pg.Surface((glyphs.get_width()+2*edge, glyphs.get_height()+2*edge), pg.SRCALPHA)
    shadow = glyphs.copy()
    shadow.fill((3, 6, 10, 255), special_flags=pg.BLEND_RGBA_MULT)
    for dx, dy in ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)):
        image.blit(shadow, (edge+dx*edge, edge+dy*edge))
    image.blit(glyphs, (edge, edge))
    return image


def label_size(label, style="classic", scale=1):
    if style == "clean":
        image = atlas_label(label, max(1, round(ATLAS_LABEL_SIZE*scale)))
        return tuple(ceil(n/scale) for n in image.get_size())
    return font(*label_font(style)).size(label)


def system_label(game, system, style="classic"):
    """Only discovered names belong on the map; unknown stars stay clickable."""
    if not (game.system_explored(system.id)
            or system.kind == black_holes.KIND and black_holes.charted(game, system)):
        return ""
    name = game.system_name(system.id)
    return name if style == "clean" else name.upper()


def known_owners(game, system):
    survey = game.known_system(system.id)
    owners = {owner for p in survey.worlds for owner in (p.owner, p.outpost_owner, p.orbital_station.owner if p.orbital_station else None) if owner} if survey else set()
    owners.update(s.owner for s in motherships.visible_at(game, system.id))
    return tuple(owner for owner in EMPIRE_IDS if owner in owners)


def label_bands(game, system, selected=False, palette=DEFAULT_PALETTE, style="classic"):
    """Return text and (pixel start, pixel end, colour) runs in stable empire order.

    Share whole letters as evenly as possible. When a very short name has more
    owners than letters, share its pixels so every known owner still appears.
    """
    label = system_label(game, system, style)
    if not label:
        return "", ()
    if style == "clean":
        return label, ((0, label_size(label, style)[0], INK),)
    owners = known_owners(game, system)
    face = font(*label_font(style))
    width = face.size(label)[0]
    if site := black_holes.at(game, system.id):
        return label, ((0, width, black_holes.SITES[site.kind][2]),)
    if not owners:
        color = INK if selected else FAINT if not game.system_explored(system.id) else MUTED
        return label, ((0, width, color),)
    count = len(owners)
    if count <= len(label):
        length, remainder = divmod(len(label), count)
        offsets = [i*length+min(i, remainder) for i in range(count+1)]
        edges = [face.size(label[:offset])[0] for offset in offsets]
    else:
        edges = [i*width//count for i in range(count+1)]
    return label, tuple((edges[i], edges[i+1], empire_color(owner, palette)) for i, owner in enumerate(owners))


def draw_system_label(surface, game, system, pos, selected=False, palette=DEFAULT_PALETTE, style="classic"):
    if style == "clean":
        label = system_label(game, system, style)
        if label:
            scale = surface.scale if isinstance(surface, Canvas) else 1
            image = atlas_label(label, max(1, round(ATLAS_LABEL_SIZE*scale)))
            position = surface.point(pos) if isinstance(surface, Canvas) else pos
            pg.Surface.blit(surface, image, position)
        return
    label, bands = label_bands(game, system, selected, palette, style)
    size, family = label_font(style)
    x, y = pos
    clip = surface.get_clip()
    for left, right, color in bands:
        surface.set_clip(clip.clip(pg.Rect(x+left, y, right-left, font(size, family).get_height())))
        text(surface, label, (x, y), size, color, family)
    surface.set_clip(clip)
