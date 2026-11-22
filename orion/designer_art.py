"""Designer overlays on the same modular ships used everywhere else."""

import pygame as pg

from . import modular_art
from .designs import HULLS, MODULES
from .ship_fitting import mounts_for
from .ui import CYAN, GOLD, INK, text, shorten, font

HULL_ORDER = modular_art.KINDS


def centered(surface, value, pos, size=14, color=INK, family="sans"):
    text(surface, value, (pos[0]-font(size, family).size(value)[0]//2, pos[1]), size, color, family)


def hull(surface, kind, rect):
    bounds = modular_art.draw(surface, kind, rect, cutaway=True, placements=())
    if bounds is not None:
        return bounds
    from .fleet_art import load_ship_art
    image = load_ship_art(kind)
    target = surface.rect(rect) if hasattr(surface, "logical_rect") else pg.Rect(rect)
    if image is not None:
        bounds = image.get_rect().fit(target)
        pg.Surface.blit(surface, pg.transform.smoothscale(image, bounds.size), bounds)
    else:
        bounds = pg.Rect(0, 0, target.h//2, target.h)
        bounds.center = target.center
        pg.draw.polygon(surface, (64, 79, 88), [bounds.midtop, bounds.midright,
                        bounds.bottomright, bounds.bottomleft, bounds.midleft])
    return surface.logical_rect(bounds) if hasattr(surface, "logical_rect") else bounds


def equipment(surface, identifier, rect):
    target = surface.rect(rect) if hasattr(surface, "logical_rect") else pg.Rect(rect)
    sprite = modular_art.component_sprite(identifier, max(1, target.w), max(1, target.h))
    if sprite is not None:
        pg.Surface.blit(surface, sprite, sprite.get_rect(center=target.center))


def positions(kind, body):
    return modular_art.mount_rects(kind, body)


def mount_frame(surface, rect, color, filled=True):
    r = pg.Rect(rect)
    corner = min(9, r.w//4, r.h//4)
    points = [(r.x+corner, r.y), (r.right-corner, r.y), (r.right, r.y+corner), (r.right, r.bottom-corner),
              (r.right-corner, r.bottom), (r.x+corner, r.bottom), (r.x, r.bottom-corner), (r.x, r.y+corner)]
    if filled:
        pg.draw.polygon(surface, (8, 21, 29), points)
    pg.draw.lines(surface, color, True, points, 2)


def draw_ship(app, preview):
    from .designer_controls import select
    surface = app.canvas
    for x in range(300, 950, 32):
        pg.draw.line(surface, (15, 32, 43), (x, 166), (x, 714))
    for y in range(170, 715, 32):
        pg.draw.line(surface, (15, 32, 43), (298, y), (950, y))
    proposed = dict(preview.mounts) if preview.fit_version == 3 else app.design_mounts
    body = modular_art.draw(surface, app.design_kind, (422, 160, 400, 552),
                            cutaway=True, placements=tuple(proposed.items()))
    if body is None:
        body = hull(surface, app.design_kind, (422, 160, 400, 552))
    rects = positions(app.design_kind, body)
    # Visible equipment uses exact artwork bounds. Click targets can be slightly
    # larger for small sockets; neither the sprite nor its mounting point moves.
    hits = {key: r.inflate(max(0, 30-r.w), max(0, 30-r.h)) for key, r in rects.items()}
    app.design_mount_rects = hits
    app.design_art_rects = rects
    for mount in mounts_for(app.design_kind):
        r, hit = rects[mount.id], hits[mount.id]
        installed, identifier = app.design_mounts.get(mount.id), proposed.get(mount.id)
        selected = mount.id == app.design_mount
        button = app.button("design_mount_"+mount.id, mount.name, hit,
                            lambda s=mount.id: select(app, s), "hotspot")
        active = app.is_active(button)
        color = GOLD if selected else INK if active else CYAN
        if mount.category == "armor":
            pg.draw.circle(surface, color, r.center, 7, 2)
        else:
            # Outlines leave the original hull and installed component visible.
            mount_frame(surface, r.inflate(4, 4), color, filled=False)
            if not identifier and mount.category not in ("engine",):
                cx, cy = r.center
                pg.draw.line(surface, color, (cx-4, cy), (cx+4, cy), 1)
                pg.draw.line(surface, color, (cx, cy-4), (cx, cy+4), 1)
        if installed:
            app.module_info_region(installed, hit)
        if mount.category == "weapon":
            left = int(mount.id.split("_")[1]) % 2 == 1
            label_rect = pg.Rect(300 if left else 805, r.centery-14, 143, 28)
            if left:
                label_rect.width = max(45, min(label_rect.width, r.left-13-label_rect.left))
            else:
                label_rect.left = max(label_rect.left, r.right+13)
                label_rect.width = max(45, min(label_rect.width, 948-label_rect.left))
            caption = MODULES[identifier].name if identifier else "Empty mount"
            pg.draw.line(surface, color, label_rect.midright if left else label_rect.midleft,
                         r.midleft if left else r.midright, 1)
            pg.draw.rect(surface, (7, 19, 27), label_rect)
            pg.draw.rect(surface, color if selected or active else (51, 87, 102), label_rect, 1)
            centered(surface, shorten(caption, label_rect.w-12, 12), (label_rect.centerx, label_rect.y+5), 12, INK)
            app.button("design_mount_label_"+mount.id, caption, label_rect,
                       lambda s=mount.id: select(app, s), "hotspot")
        elif mount.category in ("core", "hangar"):
            # Keep these outside the cutaway, rather than painting over modules.
            label = "BAY" if mount.category == "core" else "HANGAR"
            if mount.category == "core" and HULLS[app.design_kind].internal_bays > 1:
                label += " "+mount.id.rsplit("_", 1)[-1]
            centered(surface, label, (r.centerx, r.y-14), 10, color, "mono")
    for slot_id, label, label_rect in (("armor", "Hull plating", pg.Rect(788, 189, 152, 30)),
                                     ("engine", "Engine", pg.Rect(788, 674, 152, 30))):
        r = rects[slot_id]
        color = GOLD if app.design_mount == slot_id else CYAN
        pg.draw.line(surface, color, r.midright, label_rect.midleft, 1)
        pg.draw.rect(surface, (7, 19, 27), label_rect)
        pg.draw.rect(surface, color, label_rect, 1)
        centered(surface, label, (label_rect.centerx, label_rect.y+6), 13, INK)
        app.button("design_mount_label_"+slot_id, label, label_rect,
                   lambda s=slot_id: select(app, s), "hotspot")
    if proposed != app.design_mounts:
        centered(surface, "MODULE PREVIEW", (824, 132), 11, GOLD, "mono")
