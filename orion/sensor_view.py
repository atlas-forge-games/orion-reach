"""Redacted fleet contacts and colony sensor coverage on the strategic map."""

import math
import pygame as pg

from . import sensors
from .galaxy_fleet_view import fleet_markers, guardian_markers, marker_layout, pirate_markers, star_obstacles
from .galaxy_style import clean_map
from .ui import CYAN, FAINT, GOLD, INK, LINE, MUTED, panel, paragraph, shorten, text


def draw_coverage(app, rect):
    if not app.show_sensors:
        return
    layer = pg.Surface(rect.size, pg.SRCALPHA)
    for system, radius in sensors.centers(app.game):
        x, y = app.star_pos(system)
        rx, ry = app.map_camera.radii(radius, rect)
        area = pg.Rect(round(x-rect.x-rx), round(y-rect.y-ry), round(2*rx), round(2*ry))
        pg.draw.ellipse(layer, (115, 191, 164, 25), area)
        if not clean_map(app):
            pg.draw.ellipse(layer, (137, 217, 181, 110), area, 1)
    app.canvas.blit(layer, rect.topleft)


def map_contacts(app):
    # Full fleet markers already show ships directly observed in orbit.
    visible = {s.id for s in app.game.visible_ships()}
    return [c for c in sensors.contacts(app.game) if not (c.active and c.anchor in visible)]


def contact_markers(app, rect):
    contacts = [c for c in map_contacts(app) if rect.collidepoint(app.map_pos(c.x, c.y))]
    obstacles = star_obstacles(app, rect)
    obstacles += [r.inflate(4, 4) for _, r, _ in fleet_markers(app, rect)+guardian_markers(app, rect)]
    anchors = [app.map_pos(c.x, c.y) for c in contacts]
    if clean_map(app):
        obstacles += [r.inflate(4, 4) for _, r, _ in pirate_markers(app, rect)]
        preferred = [(round(x)-11, round(y)-11, 22, 22) for x, y in anchors]
    else:
        preferred = [(round(x)+12, round(y)-12, 52, 23) for x, y in anchors]
    layout = marker_layout(tuple(rect.inflate(-8, -8)), tuple(tuple(r) for r in obstacles), tuple(preferred))
    return [(c, pg.Rect(r), anchor) for c, r, anchor in zip(contacts, layout, anchors)]


def draw_contacts(app, rect):
    for contact, badge, anchor in contact_markers(app, rect):
        color = app.empire_color(contact.owner) if contact.active else FAINT
        if clean_map(app):
            cx, cy = badge.center
            pg.draw.polygon(app.canvas, color,
                            [(cx, cy-6), (cx+5, cy), (cx, cy+6), (cx-5, cy)], 1)
            if contact.active:
                pg.draw.circle(app.canvas, color, badge.center, 2)
            if contact.anchor == app.sensor_contact_id:
                pg.draw.circle(app.canvas, GOLD, badge.center, 10, 1)
            app.map_button(f"sensor_contact_{contact.anchor}", badge,
                           lambda identifier=contact.anchor: app.open_sensor_contact(identifier))
            continue
        pg.draw.line(app.canvas, color, anchor, badge.center, 1)
        pg.draw.circle(app.canvas, color, (round(anchor[0]), round(anchor[1])), 4, 1)
        if contact.heading is not None and contact.active:
            angle = math.radians(contact.heading)
            end = anchor[0]+math.cos(angle)*17, anchor[1]+math.sin(angle)*17
            pg.draw.line(app.canvas, color, anchor, end, 2)
        panel(app.canvas, badge, (9, 22, 30), GOLD if contact.anchor == app.sensor_contact_id else color)
        text(app.canvas, str(contact.count) if contact.count is not None else "?", (badge.x+8, badge.y+5), 11, color, "mono")
        text(app.canvas, "◉" if contact.active else "·", (badge.right-18, badge.y+3), 13, color)
        app.map_button(f"sensor_contact_{contact.anchor}", badge,
                       lambda identifier=contact.anchor: app.open_sensor_contact(identifier))


def draw_contact_panel(app):
    surface, game = app.canvas, app.game
    r = app.galaxy_layout.inspector
    contact = next((c for c in sensors.contacts(game) if c.anchor == app.sensor_contact_id), None)
    panel(surface, r)
    x, width = r.x+16, r.w-32
    text(surface, "SENSOR CONTACT", (x, r.y+24), 10, GOLD, "mono", 1)
    if contact is None:
        paragraph(surface, "This contact has expired. Last sightings are retained for 20 turns.", (x, r.y+82), width, 17, MUTED, 27)
    else:
        color = app.empire_color(contact.owner)
        paragraph(surface, game.empire_name_for(contact.owner), (x, r.y+60), width, 23, color, 29)
        text(surface, "LIVE TRACK" if contact.active else f"LAST SEEN · TURN {contact.seen_turn}", (x, r.y+140), 12, CYAN if contact.active else GOLD, "mono")
        nearby = game.systems[contact.near_system]
        text(surface, shorten("Near "+game.system_name(nearby.id), width, 16), (x, r.y+171), 16, INK)
        pg.draw.line(surface, LINE, (x, r.y+207), (r.right-16, r.y+207))
        text(surface, f"FLEET SIZE: {contact.count if contact.count is not None else 'UNKNOWN'}", (x, r.y+230), 12, INK, "mono")
        if contact.classes:
            paragraph(surface, " · ".join(contact.classes), (x, r.y+265), width, 14, MUTED, 22)
        else:
            paragraph(surface, "Improve sensors to identify ship classes.", (x, r.y+269), width, 14, MUTED, 23)
        heading = f"Heading {contact.heading:.0f}° clockwise from east" if contact.heading is not None else "Heading unavailable"
        text(surface, heading, (x, r.y+382), 11, CYAN if contact.active else MUTED)
        paragraph(surface, "Destination orders and planet details are not revealed by sensors.", (x, r.y+416), width, 12, MUTED, 21)
        if not contact.active:
            paragraph(surface, "Position and composition may have changed.", (x, r.bottom-103), width, 12, GOLD, 19)
    app.button("sensor_close", "Close contact · Esc", (x, r.bottom-49, width, 32), app.close_sensor_contact)
