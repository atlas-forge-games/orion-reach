"""Clickable galaxy fleets, their ship manifest, and destination previews."""

from functools import lru_cache
import pygame as pg

from .colony_view import turn_label
from .fleet_art import ship_icon
from .monster_art import draw_guardian_symbol
from .fleets import group_fleets
from .model import PLAYER, RIVAL
from .galaxy_labels import LABEL_FAMILY, LABEL_SIZE, system_label
from . import monsters, navigation, black_holes
from .black_hole_view import hit_rect
from .production import SHIP_TYPES
from . import production as production_balance
from .designs import HULLS
from .ui import CYAN, FAINT, GOLD, INK, LINE, MUTED, RED, RIVAL_COLOR, font, panel, paragraph, shorten, text

FLEET_SHIPS_PER_PAGE = 6


def draw_fuel_range(app, map_rect):
    """Own colony supply circles only; their union is the set of valid destinations."""
    game = app.game
    if not (app.map_order_ids or app.route_ship_id is not None):
        return
    radius = game.fuel_range()/100
    rx, ry = radius*(map_rect.w-80)/1.4, radius*(map_rect.h-64)
    overlay = pg.Surface(map_rect.size, pg.SRCALPHA)
    for system in game.colony_systems():
        x, y = app.star_pos(system)
        ellipse = pg.Rect(round(x-map_rect.x-rx), round(y-map_rect.y-ry), round(rx*2), round(ry*2))
        pg.draw.ellipse(overlay, (*app.empire_color(PLAYER), 19), ellipse)
        pg.draw.ellipse(overlay, (*app.empire_color(PLAYER), 90), ellipse, 1)
    app.canvas.blit(overlay, map_rect.topleft)
    speed = 100*production_balance.SHIP_SPEED*(1+game.ship_speed_bonus()/100)
    text(app.canvas, f"FUEL RANGE {game.fuel_range()} LY  ·  SPEED {speed:g} LY/TURN",
         (map_rect.right-18, map_rect.y+18), 10, CYAN, "mono", right=True)


@lru_cache(maxsize=1)
def marker_offsets():
    # A nearby free badge keeps dense clusters and newly departed ships clickable.
    return sorted(((x*8, y*8) for x in range(-120, 121) for y in range(-72, 73)),
                  key=lambda p: (p[0]**2+p[1]**2, p[1], p[0]))


@lru_cache(maxsize=8)
def marker_layout(bounds, star_obstacles, preferred_rects, padding=4):
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
        else:
            # A map with fleets at nearly every star can need gaps between the
            # coarse grid positions. Search those gaps before accepting overlap.
            best_distance = float("inf")
            for y in range(bounds.top, bounds.bottom-rect.h+1, 2):
                for x in range(bounds.left, bounds.right-rect.w+1, 2):
                    distance = (x-preferred[0])**2+(y-preferred[1])**2
                    if distance >= best_distance:
                        continue
                    candidate = pg.Rect(x, y, rect.w, rect.h)
                    if candidate.collidelist(obstacles) == -1:
                        rect, best_distance = candidate, distance
        obstacles.append(rect.inflate(padding, padding))
        result.append(tuple(rect))
    return tuple(result)


def star_label_rects(app, map_rect):
    """Keep names inside the rectangular map and clear of nearby stars and names."""
    systems = black_holes.chart_systems(app.game)
    obstacles = [hit_rect(app.star_pos(s)) if s.kind == black_holes.KIND else
                 pg.Rect(round(app.star_pos(s)[0])-15, round(app.star_pos(s)[1])-15, 30, 30)
                 for s in systems]
    obstacles += [pg.Rect(map_rect.x, map_rect.y, map_rect.w, 34), guardian_legend_rect(map_rect)]
    preferred = []
    for system in systems:
        x, y = app.star_pos(system)
        width, height = font(LABEL_SIZE, LABEL_FAMILY).size(system_label(app.game, system))
        preferred.append((round(x)+(34 if system.kind == black_holes.KIND else 17), round(y)-9, width, height))
    rectangles = marker_layout(tuple(map_rect.inflate(-10, -10)),
                               tuple(tuple(r) for r in obstacles), tuple(preferred))
    return {s.id: pg.Rect(rect) for s, rect in zip(systems, rectangles)}


def star_obstacles(app, map_rect, radius=21):
    obstacles = []
    for system in black_holes.chart_systems(app.game):
        x, y = app.star_pos(system)
        obstacles.append(hit_rect((x, y)) if system.kind == black_holes.KIND else
                         pg.Rect(int(x)-radius, int(y)-radius, radius*2, radius*2))
    # Label bounds include the bold glyphs; keep a one-pixel gap on each side.
    obstacles.extend(rect.inflate(2, 2) for rect in star_label_rects(app, map_rect).values())
    return obstacles


def known_guardian_kinds(game):
    seen = {g.kind for g in game.guardians if monsters.known_status(game, g.system_id) is not None}
    return [kind for kind in monsters.MONSTERS if kind in seen]


def guardian_legend_rect(map_rect):
    return pg.Rect(map_rect.x+12, map_rect.bottom-34, map_rect.w-24, 24)


def guardian_markers(app, map_rect):
    """Known threats have their own symbol and hit target; hidden deaths stay private."""
    guardians = [g for g in app.game.guardians if monsters.known_status(app.game, g.system_id) == "alive"]
    obstacles = star_obstacles(app, map_rect)+[guardian_legend_rect(map_rect).inflate(4, 4)]
    anchors = [app.star_pos(app.game.systems[g.system_id]) for g in guardians]
    preferred = [(round(x)-34, round(y)-33, 24, 24) for x, y in anchors]
    rectangles = marker_layout(tuple(map_rect.inflate(-8, -8)), tuple(tuple(r) for r in obstacles), tuple(preferred))
    return [(g, pg.Rect(rect), anchor) for g, rect, anchor in zip(guardians, rectangles, anchors)]


def draw_map_guardians(app, map_rect):
    old_clip = app.canvas.get_clip()
    app.canvas.set_clip(map_rect)
    for guardian, rect, anchor in guardian_markers(app, map_rect):
        color = guardian.spec.color
        pg.draw.line(app.canvas, tuple(c//3 for c in color), anchor, rect.center, 1)
        panel(app.canvas, rect, (9, 17, 28), color)
        draw_guardian_symbol(app.canvas, rect.center, guardian.kind, 18)
        app.button(f"guardian_{guardian.system_id}", "", rect,
                   lambda sid=guardian.system_id: app.select_star(sid), "hotspot")
    kinds = known_guardian_kinds(app.game)
    if kinds:
        rect = guardian_legend_rect(map_rect)
        panel(app.canvas, rect, (9, 17, 28))
        text(app.canvas, "GUARDIANS", (rect.x+10, rect.y+7), 9, MUTED, "mono")
        entries = [(kind, monsters.MONSTERS[kind].name) for kind in kinds if kind in monsters.PRIZE_WORLDS]
        if any(kind not in monsters.PRIZE_WORLDS for kind in kinds):
            entries.append(("crown_sentinel", "Legendary guardian"))
        spacing = (rect.w-130)//max(4, len(entries))
        for index, (kind, name) in enumerate(entries):
            x, y = rect.x+119+index*spacing, rect.centery
            draw_guardian_symbol(app.canvas, (x, y), kind, 15)
            text(app.canvas, name, (x+17, y-6), 10 if len(entries)>4 else 11, monsters.MONSTERS[kind].color)
    app.canvas.set_clip(old_clip)


def fleet_markers(app, map_rect):
    """Visible fleet badges avoid stars, guardian symbols and their legend."""
    # Reserve each star's full click target; extra halo padding can consume the
    # last free badge positions on a 72-system map with multiple fleets per star.
    obstacles = star_obstacles(app, map_rect, radius=18)
    obstacles.extend(rect.inflate(4, 4) for _, rect, _ in guardian_markers(app, map_rect))
    if known_guardian_kinds(app.game):
        obstacles.append(guardian_legend_rect(map_rect).inflate(4, 4))
    bounds = map_rect.inflate(-8, -8)
    anchors, preferred_rects = [], []
    groups = sorted(group_fleets(app.game.visible_ships()), key=lambda ships: (ships[0].has_course, ships[0].id))
    for ships in groups:
        ship = ships[0]
        nx, ny = navigation.position(app.game, ship)
        x, y = map_rect.x+40+nx*(map_rect.w-80), map_rect.y+32+ny*(map_rect.h-64)
        preferred = (x+12, y+12) if ship.has_course else (x+18, y+23)
        width = max(44, 32+font(11, "mono_bold").size(str(len(ships)))[0])
        anchors.append((x, y))
        preferred_rects.append(tuple(pg.Rect(*preferred, width, 23)))
    rectangles = marker_layout(tuple(bounds), tuple(tuple(r) for r in obstacles), tuple(preferred_rects), padding=2)
    return [(ships, pg.Rect(rect), anchor) for ships, rect, anchor in zip(groups, rectangles, anchors)]


def draw_map_fleets(app, map_rect):
    surface, game = app.canvas, app.game
    clip = surface.get_clip()
    surface.set_clip(map_rect)
    markers = fleet_markers(app, map_rect)
    for ships, _, _ in markers:
        ship = ships[0]
        if ship.has_course:
            color = app.empire_color(ship.owner)
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
            keeping = ship.departure_pending and target == ship.destination
            blocked = target != ship.system_id and not keeping and not game.within_fuel_range(target)
            pg.draw.line(surface, RED if blocked else GOLD, origin, end, 2)
    for ships, rect, anchor in markers:
        color = app.empire_color(ships[0].owner)
        selected = any(s.id in order_ids for s in ships)
        if selected:
            color = GOLD
        pg.draw.line(surface, tuple(c//2 for c in color), anchor, rect.center, 1)
        pg.draw.circle(surface, color, (int(anchor[0]), int(anchor[1])), 2)
        panel(surface, rect, (11, 27, 36), color)
        ship_icon(surface, (rect.x+14, rect.centery), .24, color, kind=ships[0].kind)
        text(surface, str(len(ships)), (rect.x+28, rect.y+5), 11, color, "mono_bold")
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
    rect = pg.Rect(x, y, width, bottom-y+150)
    app.fleet_popup_rect = rect
    panel(surface, rect, (10, 24, 34), app.empire_color(first.owner))
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
              if first.in_transit else f"Departure queued · {turn_label(first.turns_remaining)} to {game.systems[first.destination].name}" if first.departure_pending else
              "Select ships, then click a destination" if own else "Computer fleet · inspection only" if game.is_observer else "Rival fleet · inspection only")
    text(surface, shorten(status, 289, 12), (x+18, y+51), 12, GOLD if first.departure_pending else MUTED)
    if editable:
        app.button("fleet_select_all", "All", (x+18, y+78, 85, 29), app.select_fleet_ships)
        app.button("fleet_select_none", "Clear", (x+114, y+78, 95, 29), lambda: app.select_fleet_ships(False))
    else:
        text(surface, shorten(game.empire_name_for(first.owner), 288, 13), (x+18, y+85), 13, app.empire_color(first.owner))
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
        ship_icon(surface, (x+63, top+20), .37, app.empire_color(first.owner), kind=ship.kind)
        text(surface, ship.name, (x+88, top+4), 14, INK)
        text(surface, f"{ship.hull}/{ship.max_hull} hull", (x+89, top+24), 10, MUTED)
        if editable:
            app.button(f"fleet_select_{ship.id}", "", row, lambda sid=ship.id: app.toggle_fleet_ship(sid), "hotspot")
    pages = max(1, (len(ships)+FLEET_SHIPS_PER_PAGE-1)//FLEET_SHIPS_PER_PAGE)
    text(surface, f"PAGE {app.manifest_page+1}/{pages}", (x+18, bottom+12), 10, FAINT, "mono")
    app.button("fleet_page_previous", "←", (x+203, bottom+4, 47, 27), lambda: app.change_manifest_page(-1), enabled=app.manifest_page>0)
    app.button("fleet_page_next", "→", (x+262, bottom+4, 47, 27), lambda: app.change_manifest_page(1), enabled=app.manifest_page<pages-1)
    text(surface, f"{len(app.fleet_selected_ids)} / {len(ships)} selected" if editable else f"{len(ships)} ships · Read only",
         (x+18, bottom+43), 12, app.empire_color(first.owner))
    danger = False
    if editable:
        target = game.systems[app.fleet_route_target()]
        keeping = first.departure_pending and target.id == first.destination
        outside = not game.within_fuel_range(target.id)
        blocked = target.id != origin.id and not keeping and outside
        duration = first.turns_remaining if keeping else game.travel_turns(origin, target)
        destination = (f"To {target.name} · {turn_label(duration)}"
                       if target.id != origin.id else f"At {origin.name}")
        text(surface, shorten(destination, 290, 13), (x+18, bottom+66), 13, RED if blocked else INK)
        distance = game.supply_distance(target.id)
        fuel = ("Saved course kept · outside current range" if keeping and outside else
                f"{'Out of range' if blocked else 'Fuel range'} · {distance:.1f} / {game.fuel_range()} ly from colony")
        route, radius, slow = ((first.route_bonus, first.approach_range, first.approach_slow) if keeping else
                               navigation.route_modifiers(game, origin, target, PLAYER))
        if not blocked and not outside and (route or slow):
            fuel = f"Route speed +{route}%"+(f" · Final {radius:g} ly: −{slow:g}%" if slow else " · In fuel range")
        text(surface, shorten(fuel, 290, 11), (x+18, bottom+90), 11, RED if blocked else CYAN)
        hint = ("Colonize closer worlds or research fuel tanks." if blocked else
                f"Click {origin.name} to cancel before End Turn." if first.departure_pending
                else "Select at least one ship to give orders." if not app.fleet_selected_ids
                else "Planets unknown until arrival." if not game.system_explored(target.id)
                else "Click a star to set the selected ships' course.")
        danger = not blocked and monsters.known_status(game, target.id) == "alive"
        if danger:
            hint = f"Danger: {monsters.at(game, target.id).spec.name} · combat on arrival"
        if black_holes.risk(game, target.id):
            danger, hint = True, "FATAL APPROACH · All selected ships will be lost"
        elif black_holes.at(game, target.id) and not keeping and not danger:
            hint = "Black-hole expedition · Guardian combat possible"
    else:
        if own and (first.route_bonus or first.approach_slow):
            details = f"Route +{first.route_bonus}% · Approach −{first.approach_slow:g}%"
            text(surface, details, (x+18, bottom+90), 11, CYAN)
        text(surface, "Orders are locked during flight." if own else "Only your empire's ships accept orders.", (x+18, bottom+66), 12, MUTED)
        hint = "Escape or × closes this popup."
    text(surface, shorten(hint, 290, 11), (x+18, bottom+116), 11, RED if danger else GOLD if first.departure_pending else MUTED)


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
         app.empire_color(first.owner), right=True)
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
        ship_icon(surface, (139, y+31), .55, app.empire_color(first.owner), kind=ship.kind)
        text(surface, ship.name, (190, y+8), 19, INK)
        role = ("Survey & discovery · Unarmed" if ship.kind == "scout" else
                f"{game.ship_attack(ship)} damage / volley" if ship.damage else f"{production_balance.TROOP_STRENGTH} invasion attack · Unarmed"
                if ship.kind == "troop_transport" else f"{game.starting_colonists(first.owner)} B colonists · Unarmed")
        if ship.drone_bays:
            role = f"{ship.drone_bays*2} active drones · {ship.drone_bays*4} launches/battle"
        text(surface, role, (191, y+36), 12, MUTED)
        text(surface, f"{ship.hull} / {ship.max_hull} hull", (918, y+11), 13, INK, right=True)
        pg.draw.rect(surface, LINE, (774, y+39, 144, 4), border_radius=2)
        pg.draw.rect(surface, app.empire_color(first.owner), (774, y+39, round(144*ship.hull/ship.max_hull), 4), border_radius=2)
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
    for index, (kind, spec) in enumerate({**SHIP_TYPES, **HULLS}.items()):
        count = sum(s.kind == kind for s in selected)
        x, y = 991+(index//5)*190, 406+(index%5)*19
        text(surface, shorten(spec.name, 142, 11), (x, y), 11, MUTED)
        text(surface, str(count), (x+171, y), 11, CYAN, right=True)
    pg.draw.line(surface, LINE, (990, 524), (1352, 524))
    text(surface, f"{sum(s.hull for s in selected)} hull · {sum(game.ship_attack(s) for s in selected)} damage / volley", (991, 540), 14, INK)
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
    for index, (kind, spec) in enumerate({**SHIP_TYPES, **HULLS}.items()):
        count = sum(s.kind == kind for s in ships)
        text(surface, shorten(f"{count} × {spec.name}", 133, 11), (1075+(index//5)*146, 325+(index%5)*18), 11, MUTED)
    pg.draw.line(surface, LINE, (1075, 431), (1352, 431))
    text(surface, "DESTINATION PREVIEW", (1075, 453), 10, GOLD, "mono")
    text(surface, target.name if duration else "Choose a star", (1075, 486), 26, INK, "title")
    if duration:
        text(surface, f"Arrival in {turn_label(duration)}", (1075, 530), 16, CYAN)
        blocked = not game.within_fuel_range(target.id)
        text(surface, f"{'Out of range' if blocked else 'In range'} · {game.supply_distance(target.id):.1f} / {game.fuel_range()} ly",
             (1075, 588), 12, RED if blocked else CYAN)
        known = game.known_system(target.id)
        enemy_count = len(game.foreign_fleet(target.id)) if game.system_visible(target.id) else 0
        targets = sum(not p.colonized and game.can_settle(p) for p in known.worlds) if known else 0
        detail = ("Unsurveyed · Planets unknown" if known is None else
                  "Last survey · Activity unknown" if not game.system_visible(target.id) else
                  f"{enemy_count} rival ships in orbit" if enemy_count else f"{targets} worlds available to settle")
        if black_holes.at(game, target.id):
            detail = "FATAL APPROACH · Fleet will be lost" if black_holes.risk(game, target.id) else "Black-hole expedition · Guardian site"
        text(surface, detail, (1075, 565), 13, RED if black_holes.risk(game, target.id) else MUTED)
    else:
        text(surface, "Ships are still in orbit.", (1075, 530), 15, MUTED)
    paragraph(surface, "Click a destination star to send. Hover to preview travel time. Escape returns to ship selection.",
              (1075, 610), 277, 14, MUTED, 23)
    app.button("edit_fleet_selection", "←  Change selection", (1075, 692, 277, 43), app.cancel_map_order)
