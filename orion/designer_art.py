"""Bare hull and equipment sprites, composed at the designer's clickable positions."""

from functools import lru_cache
import pygame as pg

from .designs import HULLS, MODULES, DRONE_BAYS
from .ship_fitting import mounts_for
from .ui import ASSETS, CYAN, GOLD, INK, MUTED, text, shorten, font

HULL_ORDER = ("frigate", "destroyer", "cruiser", "battleship", "carrier", "titan")


def centered(surface, value, pos, size=14, color=INK, family="sans"):
    text(surface, value, (pos[0]-font(size, family).size(value)[0]//2, pos[1]), size, color, family)


@lru_cache(maxsize=2)
def sheet(name):
    try:
        return pg.image.load(str(ASSETS / "designer" / f"{name}-v1.png"))
    except (OSError, pg.error):
        return None


@lru_cache(maxsize=24)
def asset(name, index):
    image = sheet(name)
    if image is None:
        return None
    columns, rows = 3, 2 if name == "hulls" else 3
    x, y = index % columns, index // columns
    left, top = image.get_width()*x//columns, image.get_height()*y//rows
    right, bottom = image.get_width()*(x+1)//columns, image.get_height()*(y+1)//rows
    if name == "hulls":
        # The lower row starts just above the geometric midpoint (Titan bow).
        if y == 0:
            bottom = round(image.get_height()*.47)
        else:
            top = round(image.get_height()*.47)
    cell = image.subsurface((left, top, right-left, bottom-top))
    bounds = cell.get_bounding_rect(min_alpha=32)
    return cell.subsurface(bounds).copy() if bounds.w and bounds.h else None


@lru_cache(maxsize=256)
def fitted_sprite(name, index, width, height):
    image = asset(name, index)
    if image is None:
        return None
    fit = image.get_rect().fit((0, 0, width, height))
    return pg.transform.smoothscale(image, fit.size)


def hull(surface, kind, rect):
    target = pg.Rect(rect)
    drawn = draw_asset(surface, "hulls", HULL_ORDER.index(kind), target)
    if drawn is not None:
        return drawn
    sprite = None
    if sprite is None:
        from .fleet_art import ship_sprite
        sprite = ship_sprite(kind, target.h)
    if sprite is not None:
        bounds = sprite.get_rect(center=target.center)
        surface.blit(sprite, bounds)
        return bounds
    bounds = pg.Rect(0, 0, target.h//2, target.h)
    bounds.center = target.center
    pg.draw.polygon(surface, (64, 79, 88), [(bounds.centerx, bounds.y), bounds.midright,
                    bounds.bottomright, bounds.bottomleft, bounds.midleft])
    return bounds


def draw_asset(surface, name, index, rect):
    """Fit in actual pixels, then map the same bounds back for the hit regions."""
    target = surface.rect(rect) if hasattr(surface, "logical_rect") else pg.Rect(rect)
    sprite = fitted_sprite(name, index, max(1, target.w), max(1, target.h))
    if sprite is None:
        return None
    bounds = sprite.get_rect(center=target.center)
    pg.Surface.blit(surface, sprite, bounds)
    return surface.logical_rect(bounds) if hasattr(surface, "logical_rect") else bounds


def module_index(identifier):
    if identifier in DRONE_BAYS:
        return 8
    if identifier in ("point_defense", "flak"):
        return 2
    if identifier in ("shield", "regenerative_shield", "hardened_shield"):
        return 3
    if identifier == "damage_control":
        return 4
    if identifier in ("command_relay", "flag_bridge"):
        return 5
    if identifier == "engine":
        return 6
    if identifier in ("scanner", "ecm_projector", "escort_array"):
        return 7
    if MODULES[identifier].damage:
        from .weapons import BEAMS
        return 1 if BEAMS[MODULES[identifier].weapon].projectile else 0
    return None


def equipment(surface, identifier, rect):
    target = pg.Rect(rect)
    index = module_index(identifier)
    drawn = draw_asset(surface, "modules", index, target) if index is not None else None
    if drawn is None:
        # Armor is a material selection, represented by layered metal plates.
        for offset in (8, 4, 0):
            r = target.inflate(-14, -16).move(-offset//2, offset)
            color = (126, 135, 139) if identifier == "armor" else (180, 155, 111)
            pg.draw.polygon(surface, (41, 51, 60), [r.midtop, r.topright, r.bottomright, r.midbottom, r.topleft])
            pg.draw.polygon(surface, color, [r.midtop, r.topright, r.bottomright, r.midbottom, r.topleft], 2)


def positions(kind, body):
    """Both drawing and input use these rectangles, including large-hull extra bays."""
    spec = HULLS[kind]
    positions = {}
    pairs = (spec.external_mounts+1)//2
    levels = ((.35, .70) if pairs <= 2 else (.35, .56, .77))
    for i in range(spec.external_mounts):
        x = .12 if i % 2 == 0 else .88
        y = levels[i//2]
        width = min(66, round(body.w*.20)) if kind == "carrier" else 66
        rect = pg.Rect(0, 0, width, 76)
        rect.center = (round(body.x+x*body.w), round(body.y+y*body.h))
        positions[f"weapon_{i+1}"] = rect
    core_y = (.51,) if spec.internal_bays == 1 else (.43, .61) if spec.internal_bays == 2 else (.36, .53, .70)
    if kind == "carrier":
        core_y = (.40,) if spec.internal_bays == 1 else (.39, .61) if spec.internal_bays == 2 else (.35, .52, .69)
    for i, y in enumerate(core_y):
        rect = pg.Rect(0, 0, 76, 82 if spec.internal_bays < 3 else 74)
        rect.center = (body.centerx, round(body.y+y*body.h))
        positions[f"core_{i+1}"] = rect
    for i in range(spec.hangar_bays):
        rect = pg.Rect(0, 0, min(48, round(body.w*.13)), 84)
        rect.center = (round(body.x+(.29 if i == 0 else .71)*body.w), round(body.y+.63*body.h))
        positions[f"hangar_{i+1}"] = rect
    positions["engine"] = pg.Rect(body.centerx-49, round(body.y+.88*body.h), 98, 55)
    positions["armor"] = pg.Rect(round(body.centerx+body.w*.13)-12, round(body.y+.19*body.h)-12, 24, 24)
    return positions


def mount_frame(surface, rect, color, filled=True):
    r = pg.Rect(rect)
    points = [(r.x+9, r.y), (r.right-9, r.y), (r.right, r.y+9), (r.right, r.bottom-9),
              (r.right-9, r.bottom), (r.x+9, r.bottom), (r.x, r.bottom-9), (r.x, r.y+9)]
    if filled:
        pg.draw.polygon(surface, (8, 21, 29), points)
    pg.draw.lines(surface, color, True, points, 2)


def draw_ship(app, preview):
    from .designer_controls import select
    surface = app.canvas
    # A restrained construction grid leaves the vessel as the strongest element.
    for x in range(300, 950, 32):
        pg.draw.line(surface, (15, 32, 43), (x, 166), (x, 714))
    for y in range(170, 715, 32):
        pg.draw.line(surface, (15, 32, 43), (298, y), (950, y))
    body = hull(surface, app.design_kind, (422, 160, 400, 552))
    rects = positions(app.design_kind, body)
    app.design_mount_rects = rects
    proposed = dict(preview.mounts) if preview.fit_version == 3 else app.design_mounts
    for mount in mounts_for(app.design_kind):
        r = rects[mount.id]
        installed = app.design_mounts.get(mount.id)
        identifier = proposed.get(mount.id) if mount.id == app.design_mount else installed
        selected = mount.id == app.design_mount
        button = app.button("design_mount_"+mount.id, mount.name, r,
                            lambda s=mount.id: select(app, s), "hotspot")
        active = app.is_active(button)
        color = GOLD if selected else INK if active else CYAN
        if mount.category == "armor":
            pg.draw.circle(surface, color, r.center, 7, 2)
            if installed:
                # Extra plating visibly follows the upper shoulder of the hull.
                for side in (-1, 1):
                    x = body.centerx+side*body.w*.18
                    pg.draw.line(surface, GOLD if installed == "reinforced_armor" else (155, 175, 185),
                                 (x, body.y+body.h*.16), (x+side*body.w*.12, body.y+body.h*.30), 4)
        else:
            mount_frame(surface, r, color, mount.category not in ("engine",))
            if identifier:
                equipment(surface, identifier, r.inflate(-7, -8))
            elif mount.category != "engine":
                center = r.center
                pg.draw.line(surface, color, (center[0]-10, center[1]), (center[0]+10, center[1]), 3)
                pg.draw.line(surface, color, (center[0], center[1]-10), (center[0], center[1]+10), 3)
            if mount.category in ("core", "hangar"):
                label = "BAY" if mount.category == "core" else "HANGAR"
                if mount.category == "core" and HULLS[app.design_kind].internal_bays > 1:
                    label += " "+mount.id.rsplit("_", 1)[-1]
                pg.draw.rect(surface, (8, 21, 29), (r.x+2, r.y+2, r.w-4, 15))
                centered(surface, label, (r.centerx, r.y+2), 10, color, "mono")
            if selected and identifier != installed:
                pg.draw.rect(surface, (8, 21, 29), (r.x+2, r.bottom-15, r.w-4, 13))
                centered(surface, "PREVIEW", (r.centerx, r.bottom-15), 9, GOLD, "mono")
        if installed:
            app.module_info_region(installed, r)
        if mount.category == "weapon":
            left = int(mount.id.split("_")[1]) % 2 == 1
            label_rect = pg.Rect(300 if left else 805, r.centery-14, 143, 28)
            # Keep wide hulls' labels outside the mounting pad.
            if left:
                label_rect.width = min(label_rect.width, r.left-13-label_rect.left)
            else:
                label_rect.left = max(label_rect.left, r.right+13)
                label_rect.width = min(label_rect.width, 948-label_rect.left)
            caption = MODULES[installed].name if installed else "Empty mount"
            pg.draw.line(surface, color, label_rect.midright if left else label_rect.midleft,
                         r.midleft if left else r.midright, 1)
            pg.draw.rect(surface, (7, 19, 27), label_rect)
            pg.draw.rect(surface, color if selected or active else (51, 87, 102), label_rect, 1)
            centered(surface, shorten(caption, label_rect.w-12, 12), (label_rect.centerx, label_rect.y+5), 12, INK)
            app.button("design_mount_label_"+mount.id, caption, label_rect,
                       lambda s=mount.id: select(app, s), "hotspot")
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
