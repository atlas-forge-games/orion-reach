"""Clickable galaxy fleets, their ship manifest, and destination previews."""

from functools import lru_cache
import pygame as pg

from .colony_view import turn_label
from .fleet_art import ship_icon
from .fleets import group_fleets
from .model import PLAYER, RIVAL
from .production import SHIP_TYPES, TROOP_STRENGTH
from .ui import CYAN, FAINT, GOLD, INK, LINE, MUTED, RIVAL_COLOR, font, panel, paragraph, shorten, text

FLEET_SHIPS_PER_PAGE = 6


@lru_cache(maxsize=1)
def marker_offsets():
    # A nearby free badge keeps dense clusters and newly departed ships clickable.
    return sorted(((x*8, y*8) for x in range(-120, 121) for y in range(-72, 73)),
                  key=lambda p: (p[0]**2+p[1]**2, p[1], p[0]))


@lru_cache(maxsize=8)
def marker_layout(bounds, star_obstacles, preferred_rects):
    """Only recompute placement when fleet positions or membership change."""
    bounds = pg.Rect(bounds)
    obstacles = [pg.Rect(rect) for rect in star_obstacles]
    result = []
    for preferred in preferred_rects:
        rect = pg.Rect(preferred).clamp(bounds)
        for dx, dy in marker_offsets():
            candidate = pg.Rect(preferred).move(dx, dy)
            if bounds.contains(candidate) and candidate.collidelist(obstacles) == -1:
                rect = candidate
                break
        obstacles.append(rect.inflate(4, 4))
        result.append(tuple(rect))
    return tuple(result)


def fleet_markers(app, map_rect):
    """Return visible, non-overlapping hit regions, clear of stars and their labels."""
    obstacles = []
    for system in app.game.systems:
        x, y = app.star_pos(system)
        obstacles.append(pg.Rect(int(x)-21, int(y)-21, 42, 42))
        obstacles.append(pg.Rect(int(x)+10, int(y)-11, font(11, "mono").size(system.name.upper())[0]+4, 18))
    bounds = map_rect.inflate(-8, -8)
    anchors, preferred_rects = [], []
    groups = sorted(group_fleets(app.game.visible_ships()), key=lambda ships: (ships[0].has_course, ships[0].id))
    for ships in groups:
        ship = ships[0]
        x, y = app.star_pos(app.game.systems[ship.system_id])
        if ship.has_course:
            end = app.star_pos(app.game.systems[ship.destination])
            progress = 1-ship.turns_remaining/ship.travel_total
            x, y = x+(end[0]-x)*progress, y+(end[1]-y)*progress
            preferred = (x+12, y+12)
        else:
            preferred = (x+18, y+23)
        width = max(44, 32+font(11, "mono").size(str(len(ships)))[0])
        anchors.append((x, y))
        preferred_rects.append(tuple(pg.Rect(*preferred, width, 23)))
    rectangles = marker_layout(tuple(bounds), tuple(tuple(r) for r in obstacles), tuple(preferred_rects))
    return [(ships, pg.Rect(rect), anchor) for ships, rect, anchor in zip(groups, rectangles, anchors)]


def draw_map_fleets(app, map_rect):
    surface, game = app.canvas, app.game
    clip = surface.get_clip()
    surface.set_clip(map_rect)
    markers = fleet_markers(app, map_rect)
    for ships, _, _ in markers:
        ship = ships[0]
        if ship.has_course:
            color = CYAN if ship.owner == PLAYER else RIVAL_COLOR
            origin = app.star_pos(game.systems[ship.system_id])
            end = app.star_pos(game.systems[ship.destination])
            pg.draw.line(surface, tuple(c//3 for c in color), origin, end, 1)
    order_ids = app.map_order_ids or ((app.route_ship_id,) if app.route_ship_id is not None else ())
    if order_ids:
        ship = next((s for s in game.ships if s.id == order_ids[0]), None)
        if ship:
            origin = app.star_pos(game.systems[ship.system_id])
            target = app.fleet_route_target() if app.map_order_ids else game.selected_system
            end = app.star_pos(game.systems[target])
            pg.draw.line(surface, GOLD, origin, end, 2)
    for ships, rect, anchor in markers:
        color = CYAN if ships[0].owner == PLAYER else RIVAL_COLOR
        selected = any(s.id in order_ids for s in ships)
        if selected:
            color = GOLD
        pg.draw.line(surface, tuple(c//2 for c in color), anchor, rect.center, 1)
        pg.draw.circle(surface, color, (int(anchor[0]), int(anchor[1])), 2)
        panel(surface, rect, (11, 27, 36), color)
        ship_icon(surface, (rect.x+14, rect.centery), .24, color, kind=ships[0].kind)
        text(surface, str(len(ships)), (rect.x+28, rect.y+5), 11, color, "mono")
        app.button(f"map_fleet_{ships[0].id}", "", rect,
                   lambda sid=ships[0].id: app.open_map_fleet(sid), "hotspot")
    surface.set_clip(clip)


def draw_fleet_popup(app):
    """A compact ship selector beside the map; stars remain directly clickable."""
    surface, game = app.canvas, app.game
    ships = app.sync_fleet_selection()
    if not ships:
        app.close_fleet_popup()
        return
    first = ships[0]
    own = first.owner == PLAYER
    editable = own and not first.in_transit and game.strategy_error() is None
    app.map_order_ids = tuple(sorted(app.fleet_selected_ids)) if editable else ()
    start = app.manifest_page*FLEET_SHIPS_PER_PAGE
    visible = ships[start:start+FLEET_SHIPS_PER_PAGE]
    x, y, width = 1051, 180, 325
    bottom = y+120+len(visible)*48
    rect = pg.Rect(x, y, width, bottom-y+126)
    app.fleet_popup_rect = rect
    panel(surface, rect, (10, 24, 34), CYAN if own else RIVAL_COLOR)
    app.button("fleet_popup_panel", "", rect, lambda: None, "hotspot")
    origin = game.systems[first.system_id]
    title = "Fleet in transit" if first.in_transit else f"Fleet at {origin.name}"
    text(surface, shorten(title, 241, 22), (x+18, y+17), 22, INK)
    close = pg.Rect(x+278, y+13, 31, 31)
    app.button("fleet_popup_close", "", close, app.close_fleet_popup)
    cx, cy = close.center
    pg.draw.line(surface, INK, (cx-4, cy-4), (cx+4, cy+4), 1)
    pg.draw.line(surface, INK, (cx-4, cy+4), (cx+4, cy-4), 1)
    status = (f"To {game.systems[first.destination].name} · {turn_label(first.turns_remaining)} remaining"
              if first.in_transit else "Departure queued · waiting for End Turn" if first.departure_pending else
              "Select ships, then click a destination" if own else "Rival fleet · inspection only")
    text(surface, shorten(status, 289, 12), (x+18, y+51), 12, GOLD if first.departure_pending else MUTED)
    if editable:
        app.button("fleet_select_all", "All", (x+18, y+78, 85, 29), app.select_fleet_ships)
        app.button("fleet_select_none", "Clear", (x+114, y+78, 95, 29), lambda: app.select_fleet_ships(False))
    else:
        text(surface, shorten(game.empire_name_for(first.owner), 288, 13), (x+18, y+85), 13, CYAN if own else RIVAL_COLOR)
    for index, ship in enumerate(visible):
        top = y+120+index*48
        selected = ship.id in app.fleet_selected_ids
        row = pg.Rect(x+16, top, 293, 42)
        panel(surface, row, (18, 39, 48) if selected else (8, 19, 27), CYAN if selected else LINE)
        if editable:
            box = pg.Rect(x+26, top+13, 15, 15)
            pg.draw.rect(surface, CYAN if selected else FAINT, box, 1)
            if selected:
                pg.draw.lines(surface, CYAN, False, [(x+29, top+20), (x+32, top+24), (x+38, top+16)], 2)
        ship_icon(surface, (x+63, top+20), .37, CYAN if own else RIVAL_COLOR, kind=ship.kind)
        text(surface, ship.name, (x+88, top+4), 14, INK)
        text(surface, f"{ship.hull}/{ship.max_hull} hull", (x+89, top+24), 10, MUTED)
        if editable:
            app.button(f"fleet_select_{ship.id}", "", row, lambda sid=ship.id: app.toggle_fleet_ship(sid), "hotspot")
    pages = max(1, (len(ships)+FLEET_SHIPS_PER_PAGE-1)//FLEET_SHIPS_PER_PAGE)
    text(surface, f"PAGE {app.manifest_page+1}/{pages}", (x+18, bottom+12), 10, FAINT, "mono")
    app.button("fleet_page_previous", "←", (x+203, bottom+4, 47, 27), lambda: app.change_manifest_page(-1), enabled=app.manifest_page>0)
    app.button("fleet_page_next", "→", (x+262, bottom+4, 47, 27), lambda: app.change_manifest_page(1), enabled=app.manifest_page<pages-1)
    text(surface, f"{len(app.fleet_selected_ids)} / {len(ships)} selected" if editable else f"{len(ships)} ships · Read only",
         (x+18, bottom+43), 12, CYAN if own else RIVAL_COLOR)
    if editable:
        target = game.systems[app.fleet_route_target()]
        destination = (f"To {target.name} · {turn_label(game.travel_turns(origin, target))}"
                       if target.id != origin.id else f"At {origin.name}")
        text(surface, shorten(destination, 290, 13), (x+18, bottom+66), 13, INK)
        hint = (f"Click {origin.name} to cancel before End Turn." if first.departure_pending
                else "Select at least one ship to give orders." if not app.fleet_selected_ids
                else "Planets unknown until arrival." if not game.system_explored(target.id)
                else "Click a star to set the selected ships' course.")
    else:
        text(surface, "Orders are locked during flight." if own else "Only your empire's ships accept orders.", (x+18, bottom+66), 12, MUTED)
        hint = "Escape or × closes this popup."
    text(surface, shorten(hint, 290, 11), (x+18, bottom+92), 11, GOLD if first.departure_pending else MUTED)


def draw_fleet(app):
    surface, game = app.canvas, app.game
    ships = app.sync_fleet_selection()
    app.chrome("FLEET OVERVIEW")
    app.button("fleet_back", "←  Galaxy map · Esc", (64, 124, 246, 46), lambda: app.go("galaxy"), "ghost")
    text(surface, f"YEAR {game.year} · TURN {game.turn}", (1376, 141), 12, GOLD, "mono", right=True)
    if not ships:
        text(surface, "This fleet is no longer here.", (64, 206), 36, INK, "title")
        text(surface, "Return to the galaxy map to select another fleet.", (66, 266), 17, MUTED)
        return
    first = ships[0]
    own = first.owner == PLAYER
    commandable = own and not first.in_transit and game.strategy_error() is None
    origin = game.systems[first.system_id]
    title = "Fleet in transit" if first.in_transit else f"Fleet at {origin.name}"
    text(surface, shorten(title, 960, 40, "title"), (64, 190), 40, INK, "title")
    location = (f"{origin.name} → {game.systems[first.destination].name} · Arrives in {turn_label(first.turns_remaining)}"
                if first.in_transit else f"{origin.name} orbit · {'Select the ships you want to send' if own else 'Rival fleet · Inspection only'}")
    text(surface, location, (66, 246), 15, MUTED)
    text(surface, shorten(game.empire_name_for(first.owner), 415, 16), (1376, 250), 16,
         CYAN if own else RIVAL_COLOR, right=True)
    app.button("fleet_select_all", "Select all", (64, 289, 155, 37), app.select_fleet_ships, enabled=commandable)
    app.button("fleet_select_none", "Clear", (233, 289, 123, 37), lambda: app.select_fleet_ships(False), enabled=commandable)
    caption = f"{len(app.fleet_selected_ids)} of {len(ships)} selected" if commandable else f"{len(ships)} ships · Read only"
    text(surface, caption, (382, 299), 13, CYAN if commandable else MUTED)
    start = app.manifest_page*FLEET_SHIPS_PER_PAGE
    for index, ship in enumerate(ships[start:start+FLEET_SHIPS_PER_PAGE]):
        y = 346+index*70
        rect = pg.Rect(64, y, 876, 62)
        selected = ship.id in app.fleet_selected_ids
        panel(surface, rect, (15, 33, 43) if selected else (10, 20, 29), CYAN if selected else LINE)
        if commandable:
            box = pg.Rect(83, y+22, 18, 18)
            pg.draw.rect(surface, CYAN if selected else FAINT, box, 1, border_radius=2)
            if selected:
                pg.draw.lines(surface, CYAN, False, [(86, y+30), (91, y+35), (98, y+25)], 2)
        ship_icon(surface, (139, y+31), .55, CYAN if own else RIVAL_COLOR, kind=ship.kind)
        text(surface, ship.name, (190, y+8), 19, INK)
        role = ("Survey & discovery · Unarmed" if ship.kind == "scout" else
                f"{game.beam_for(ship.kind, ship.owner).damage} damage / shot" if ship.damage else f"{TROOP_STRENGTH} invasion attack · Unarmed"
                if ship.kind == "troop_transport" else f"{game.starting_colonists(first.owner)} B colonists · Unarmed")
        text(surface, role, (191, y+36), 12, MUTED)
        text(surface, f"{ship.hull} / {ship.max_hull} hull", (918, y+11), 13, INK, right=True)
        pg.draw.rect(surface, LINE, (774, y+39, 144, 4), border_radius=2)
        pg.draw.rect(surface, CYAN if own else RIVAL_COLOR, (774, y+39, round(144*ship.hull/ship.max_hull), 4), border_radius=2)
        if commandable:
            app.button(f"fleet_select_{ship.id}", "", rect, lambda sid=ship.id: app.toggle_fleet_ship(sid), "hotspot")
    last = max(0, (len(ships)-1)//FLEET_SHIPS_PER_PAGE)
    text(surface, f"PAGE {app.manifest_page+1} / {last+1}", (65, 790), 10, FAINT, "mono")
    app.button("fleet_page_previous", "← Prev", (660, 778, 130, 37), lambda: app.change_manifest_page(-1), enabled=app.manifest_page>0)
    app.button("fleet_page_next", "Next →", (804, 778, 136, 37), lambda: app.change_manifest_page(1), enabled=app.manifest_page<last)

    panel(surface, (966, 289, 410, 526))
    text(surface, "SELECTED FOR DEPARTURE" if commandable else "FLEET MANIFEST", (990, 312), 11, GOLD, "mono", 1)
    selected = [s for s in ships if s.id in app.fleet_selected_ids] if commandable else ships
    text(surface, f"{len(selected)} {'ship' if len(selected)==1 else 'ships'}", (990, 348), 35, INK, "title")
    for index, spec in enumerate(SHIP_TYPES.values()):
        count = sum(s.kind == spec.id for s in selected)
        y = 406+index*28
        text(surface, spec.name, (991, y), 14, MUTED)
        text(surface, str(count), (1352, y), 15, CYAN, right=True)
    pg.draw.line(surface, LINE, (990, 524), (1352, 524))
    text(surface, f"{sum(s.hull for s in selected)} hull · {sum(game.beam_for(s.kind, s.owner).damage for s in selected)} damage / volley", (991, 540), 14, INK)
    description = ("Choose a destination, then click a star on the map to send the selected ships. Unchecked ships stay in orbit."
                   if commandable else "These ships are travelling together. Advance turns to reach their destination; courses cannot be changed in flight."
                   if first.in_transit else "You can inspect this fleet, but only its empire can issue movement orders.")
    paragraph(surface, description, (991, 586), 351, 15, MUTED, 24)
    if commandable:
        app.button("fleet_choose_destination", "Choose destination", (990, 720, 362, 58), app.plot_fleet_course,
                   "primary" if selected else "normal", enabled=bool(selected))
    else:
        destination = first.destination if first.in_transit else first.system_id
        app.button("fleet_view_system", "View destination" if first.in_transit else "View system",
                   (990, 720, 362, 58), lambda sid=destination: app.open_system(sid))
    app.button("fleet_pause", "Menu", (64, 834, 126, 45), app.pause)
    app.button("fleet_save", "Save · F5", (204, 834, 172, 45), app.save_game)
    text(surface, "Ships sharing an orbit form a fleet. Send a selection to split it.", (400, 845), 12, MUTED)
    app.button("fleet_end_turn", "End turn · E", (1081, 834, 295, 45), app.advance_turn)


def draw_order_panel(app, target):
    surface, game = app.canvas, app.game
    ships = [s for s in game.ships if s.id in app.map_order_ids]
    if not ships:
        return
    origin = game.systems[ships[0].system_id]
    duration = game.travel_turns(origin, target)
    panel(surface, (1051, 180, 325, 573), border=GOLD)
    text(surface, "CHOOSE DESTINATION", (1075, 203), 10, GOLD, "mono", 1)
    text(surface, f"{len(ships)} {'ship' if len(ships)==1 else 'ships'} selected", (1075, 245), 25, INK, "title")
    text(surface, f"Departing {origin.name}", (1075, 289), 14, CYAN)
    for index, spec in enumerate(SHIP_TYPES.values()):
        count = sum(s.kind == spec.id for s in ships)
        text(surface, f"{count} × {spec.name}", (1075, 325+index*26), 14, MUTED)
    pg.draw.line(surface, LINE, (1075, 431), (1352, 431))
    text(surface, "DESTINATION PREVIEW", (1075, 453), 10, GOLD, "mono")
    text(surface, target.name if duration else "Choose a star", (1075, 486), 26, INK, "title")
    if duration:
        text(surface, f"Arrival in {turn_label(duration)}", (1075, 530), 16, CYAN)
        known = game.known_system(target.id)
        enemy_count = len(game.fleet_at(target.id, RIVAL)) if game.system_visible(target.id) else 0
        targets = sum(not p.colonized and game.can_settle(p) for p in known.worlds) if known else 0
        detail = ("Unsurveyed · Planets unknown" if known is None else
                  "Last survey · Activity unknown" if not game.system_visible(target.id) else
                  f"{enemy_count} rival ships in orbit" if enemy_count else f"{targets} worlds available to settle")
        text(surface, detail, (1075, 565), 13, MUTED)
    else:
        text(surface, "Ships are still in orbit.", (1075, 530), 15, MUTED)
    paragraph(surface, "Click a destination star to send. Hover to preview travel time. Escape returns to ship selection.",
              (1075, 610), 277, 14, MUTED, 23)
    app.button("edit_fleet_selection", "←  Change selection", (1075, 692, 277, 43), app.cancel_map_order)
