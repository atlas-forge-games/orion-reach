"""Galaxy name styling based only on the player's current or stored survey."""

import pygame as pg

from .empires import DEFAULT_PALETTE, EMPIRE_IDS, empire_color
from .ui import FAINT, INK, MUTED, font, text_image
from . import black_holes

LABEL_SIZE = 13
LABEL_FAMILY = "mono_bold"


def system_label(game, system):
    name = system.name.upper()
    if system.kind == black_holes.KIND:
        return name
    return name if game.known_system(system.id) is not None else f"({name})"


def known_owners(game, system):
    survey = game.known_system(system.id)
    owners = {owner for p in survey.worlds for owner in (p.owner, p.outpost_owner) if owner} if survey else set()
    return tuple(owner for owner in EMPIRE_IDS if owner in owners)


def label_bands(game, system, selected=False, palette=DEFAULT_PALETTE):
    """Return text and (pixel start, pixel end, colour) runs in stable empire order.

    Share whole letters as evenly as possible. When a very short name has more
    owners than letters, share its pixels so every known owner still appears.
    """
    label = system_label(game, system)
    owners = known_owners(game, system)
    face = font(LABEL_SIZE, LABEL_FAMILY)
    width = face.size(label)[0]
    if site := black_holes.at(game, system.id):
        return label, ((0, width, black_holes.SITES[site.kind][2]),)
    if not owners:
        color = INK if selected else FAINT if label.startswith("(") else MUTED
        return label, ((0, width, color),)
    count = len(owners)
    if count <= len(label):
        length, remainder = divmod(len(label), count)
        offsets = [i*length+min(i, remainder) for i in range(count+1)]
        edges = [face.size(label[:offset])[0] for offset in offsets]
    else:
        edges = [i*width//count for i in range(count+1)]
    return label, tuple((edges[i], edges[i+1], empire_color(owner, palette)) for i, owner in enumerate(owners))


def draw_system_label(surface, game, system, pos, selected=False, palette=DEFAULT_PALETTE):
    label, bands = label_bands(game, system, selected, palette)
    x, y = pos
    for left, right, color in bands:
        rendered = text_image(label, LABEL_SIZE, color, LABEL_FAMILY)
        surface.blit(rendered, (x+left, y), pg.Rect(left, 0, right-left, rendered.get_height()))
