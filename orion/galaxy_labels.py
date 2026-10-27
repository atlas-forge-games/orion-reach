"""Galaxy name styling based only on the player's current or stored survey."""

import pygame as pg

from .empires import DEFAULT_PALETTE, EMPIRE_IDS, empire_color
from .ui import FAINT, INK, MUTED, font, text_image
from . import black_holes, motherships

LABEL_SIZE = 13
LABEL_FAMILY = "mono_bold"


def label_font(style="classic"):
    return (11, "sans") if style == "clean" else (LABEL_SIZE, LABEL_FAMILY)


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
    label, bands = label_bands(game, system, selected, palette, style)
    size, family = label_font(style)
    x, y = pos
    for left, right, color in bands:
        rendered = text_image(label, size, color, family)
        surface.blit(rendered, (x+left, y), pg.Rect(left, 0, right-left, rendered.get_height()))
