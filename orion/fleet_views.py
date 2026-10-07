"""Shipyard queue and fleet operations screens."""

import pygame as pg

from .colony_view import draw_planet_tabs, turn_label
from .building_art import draw_building_art
from .fleet_art import ship_icon
from .production import MAX_QUEUE, PROJECTS, SHIP_TYPES
from .model import PLAYER
from .ui import CYAN, FAINT, GOLD, INK, LINE, MUTED, RIVAL_COLOR, panel, paragraph, shorten, text

FLEETS_PER_PAGE = 4
QUEUE_PER_PAGE = 5


def draw_shipyard(app):
    surface, game = app.canvas, app.game
    system = game.systems[game.selected_system]
    planet = system.worlds[game.selected_planet]
    app.chrome("PLANETARY SHIPYARD")
    app.button("shipyard_back", "←  Planet overview", (64, 124, 246, 47), lambda: app.go("planet"), "ghost")
    text(surface, shorten(f"{system.name.upper()} / {planet.name.upper()}", 530, 11, "mono"),
         (347, 143), 11, MUTED, "mono")
    text(surface, f"YEAR {game.year} · {game.treasury_for(planet.owner or PLAYER):,} CR", (1376, 141), 12, GOLD, "mono", right=True)
    text(surface, shorten(planet.name, 720, 43, "title"), (64, 185), 43, INK, "title")
    text(surface, f"Shipyard · {game.planet_yields(planet)[0]} industry / turn · {game.empire_name_for(planet.owner)}",
         (66, 249), 14, MUTED)
    draw_planet_tabs(app, "shipyard")

    spec = SHIP_TYPES["colony_ship"]
    estimates = game.queue_estimates(planet)
    forecast = game.queue_estimates(planet, "colony_ship")
    panel(surface, (64, 306, 585, 327))
    text(surface, "COLONIZATION PROGRAMME", (88, 327), 11, GOLD, "mono", 1)
    draw_building_art(surface, "shipyard", (88, 359, 166, 110))
    text(surface, "Colony ship", (277, 378), 29, INK, "title")
    text(surface, f"Transport · {game.starting_colonists(planet.owner or PLAYER)} B colonists", (279, 426), 14, CYAN)
    paragraph(surface, "Settle habitable worlds. Force Fields research unlocks barren and volcanic colonies. The ship becomes the settlement.",
              (89, 475), 523, 15, MUTED, 24)
    eta = f"Ready in {turn_label(forecast[-1])}" if forecast else "Requires a colony"
    text(surface, f"{game.project_price(spec.id, planet.owner or PLAYER)} CR · {spec.work_cost} work · {eta}", (89, 537), 14, INK)
    reason = game.ship_build_error(system.id, planet.id)
    app.button("build_colony_ship", "Build colony ship", (88, 574, 306, 43), app.queue_colony_ship,
               enabled=reason is None)
    text(surface, "No building slot needed", (414, 590), 11, MUTED)
    if reason:
        text(surface, shorten(reason, 570, 12), (65, 648), 12, GOLD)

    panel(surface, (64, 680, 585, 113))
    ready = len(game.colony_ships_at(system.id))
    text(surface, f"Your colony ships in this system: {ready}", (88, 695), 17, INK)
    text(surface, "Assign destinations and track arrivals in Fleets.", (89, 723), 12, MUTED)
    app.button("shipyard_fleets", "Open fleets →", (88, 750, 235, 33), app.open_fleets)

    panel(surface, (674, 306, 702, 487))
    text(surface, "SHARED CONSTRUCTION QUEUE", (697, 328), 11, GOLD, "mono", 1)
    text(surface, f"{len(planet.construction_queue)} / {MAX_QUEUE} projects", (1353, 328), 11, MUTED, "mono", right=True)
    text(surface, "Ships and buildings use the same local industry.", (698, 355), 13, MUTED)
    last = max(0, (len(planet.construction_queue)-1)//QUEUE_PER_PAGE)
    app.shipyard_page = min(max(0, app.shipyard_page), last)
    start = app.shipyard_page*QUEUE_PER_PAGE
    for index in range(start, min(start+QUEUE_PER_PAGE, len(planet.construction_queue))):
        project = planet.construction_queue[index]
        definition = PROJECTS[project.item_id]
        y = 394+(index-start)*65
        panel(surface, (697, y, 656, 58), (8, 18, 26))
        text(surface, f"{index+1:02}", (711, y+12), 11, GOLD, "mono")
        text(surface, definition.name, (748, y+7), 16, INK)
        text(surface, turn_label(estimates[index]), (1178, y+9), 12, CYAN, right=True)
        text(surface, f"{project.progress}/{definition.work_cost} work · Refund {project.refund} CR", (749, y+32), 11, MUTED)
        app.button(f"queue_cancel_{index}", "Cancel", (1210, y+9, 128, 38),
                   lambda i=index: app.cancel_construction(i), enabled=planet.owner == PLAYER)
        pg.draw.rect(surface, LINE, (749, y+51, 429, 2))
        pg.draw.rect(surface, GOLD, (749, y+51, int(429*project.progress/definition.work_cost), 2))
    if not planet.construction_queue:
        text(surface, "No projects queued.", (699, 419), 23, INK, "title")
        message = ("The rival chooses its own projects when you end the turn."
                   if planet.owner not in (None, PLAYER) else
                   "Build a colony ship here, or choose buildings in the Colony tab.")
        paragraph(surface, message, (700, 462), 608, 15, MUTED, 25)
    text(surface, f"PAGE {app.shipyard_page+1} / {last+1}", (699, 754), 10, FAINT, "mono")
    app.button("queue_previous", "← Prev", (1080, 739, 126, 39), lambda: app.change_shipyard_page(-1), enabled=app.shipyard_page>0)
    app.button("queue_next", "Next →", (1220, 739, 133, 39), lambda: app.change_shipyard_page(1), enabled=app.shipyard_page<last)
    app.button("shipyard_pause", "Menu", (64, 834, 126, 45), app.pause)
    app.button("shipyard_save", "Save · F5", (204, 834, 172, 45), app.save_game)
    text(surface, "Build → Plot course in Fleets → End Turn → Colonize a planet", (400, 840), 12, MUTED)
    app.button("shipyard_end_turn", "End turn · E", (1081, 824, 295, 55), app.advance_turn, "primary")


def draw_fleets(app):
    surface, game = app.canvas, app.game
    ships = game.ships_owned_by()
    app.chrome("FLEET OPERATIONS")
    app.button("fleets_back", "←  Back · F", (64, 124, 190, 46), app.close_fleets, "ghost")
    app.button("fleets_galaxy", "Galaxy map", (269, 124, 174, 46), lambda: app.go("galaxy"), "ghost")
    text(surface, f"YEAR {game.year} · TURN {game.turn}", (1376, 141), 12, GOLD, "mono", right=True)
    text(surface, "Colony fleet", (64, 190), 43, INK, "title")
    text(surface, "Build at a colony. Travel between stars. Found a new world.", (66, 251), 14, MUTED)
    ready = sum(not s.in_transit for s in ships)
    queued = sum(p.item_id in SHIP_TYPES for system in game.systems for planet in system.worlds
                 if planet.owner == PLAYER for p in planet.construction_queue)
    stats = [("READY IN ORBIT", ready), ("IN TRANSIT", len(ships)-ready), ("UNDER CONSTRUCTION", queued)]
    for i, (label, value) in enumerate(stats):
        x = 64+i*446
        panel(surface, (x, 289, 420, 84))
        text(surface, label, (x+19, 303), 10, MUTED, "mono", 1)
        text(surface, str(value), (x+18, 327), 28, CYAN)
    text(surface, "YOUR SHIPS", (64, 396), 11, GOLD, "mono", 2)
    text(surface, "Arrival is automatic. Settlement is your choice.", (1376, 397), 12, MUTED, right=True)
    last = max(0, (len(ships)-1)//FLEETS_PER_PAGE)
    app.fleet_page = min(max(0, app.fleet_page), last)
    start = app.fleet_page*FLEETS_PER_PAGE
    for i, ship in enumerate(ships[start:start+FLEETS_PER_PAGE]):
        y = 429+i*87
        panel(surface, (64, y, 1312, 76))
        ship_icon(surface, (100, y+38), .67)
        text(surface, ship.name, (142, y+12), 18, INK)
        text(surface, f"{game.starting_colonists()} B colonists · consumed on settlement", (143, y+43), 11, MUTED)
        origin = game.systems[ship.system_id]
        location = f"{origin.name} → {game.systems[ship.destination].name}" if ship.in_transit else f"{origin.name} orbit"
        text(surface, shorten(location, 467, 18), (473, y+12), 18, CYAN)
        caption = f"Arrives in {turn_label(ship.turns_remaining)}" if ship.in_transit else "Ready to travel or settle a planet here"
        text(surface, caption, (474, y+43), 12, MUTED)
        if ship.in_transit:
            pg.draw.rect(surface, LINE, (474, y+65, 454, 2))
            pg.draw.rect(surface, GOLD, (474, y+65, int(454*(1-ship.turns_remaining/ship.travel_total)), 2))
        target = ship.destination if ship.in_transit else ship.system_id
        app.button(f"ship_view_{ship.id}", "View system", (966, y+18, 172, 42), lambda s=target: app.open_system(s))
        app.button(f"ship_send_{ship.id}", "In transit" if ship.in_transit else "Plot course", (1152, y+18, 200, 42),
                   lambda sid=ship.id: app.plot_course(sid), enabled=not ship.in_transit)
    if not ships:
        panel(surface, (64, 429, 1312, 248))
        ship_icon(surface, (144, 526), 1.6)
        text(surface, "Your next colony starts with a ship.", (248, 467), 28, INK, "title")
        paragraph(surface, "Open a colony's Shipyard tab and build a colony ship. Once construction finishes, it appears here in orbit.",
                  (250, 515), 995, 16, MUTED, 27)
        home = next(((s, p) for s in game.systems for p in s.worlds if p.owner == PLAYER), None)
        if home:
            s, p = home
            app.button("fleet_build_first", "Open colony shipyard", (250, 596, 327, 48),
                       lambda sid=s.id, pid=p.id: app.open_shipyard(sid, pid))
    text(surface, "Open a planet in the ship's system to settle it.", (64, 798), 13, MUTED)
    text(surface, f"PAGE {app.fleet_page+1} / {last+1}", (1069, 798), 10, FAINT, "mono", right=True)
    app.button("fleets_previous", "← Prev", (1100, 785, 129, 37), lambda: app.change_fleet_page(-1), enabled=app.fleet_page>0)
    app.button("fleets_next", "Next →", (1243, 785, 133, 37), lambda: app.change_fleet_page(1), enabled=app.fleet_page<last)
    app.button("fleets_pause", "Menu", (64, 834, 126, 45), app.pause)
    app.button("fleets_save", "Save · F5", (204, 834, 172, 45), app.save_game)
    text(surface, "F: fleets · I: empire · E: advance travel and construction", (400, 845), 12, MUTED)
    app.button("fleets_end_turn", "End turn · E", (1081, 834, 295, 45), app.advance_turn)


def draw_map_fleets(app, map_rect):
    """Routes and ship locations share the galaxy's exact star coordinates."""
    surface, game = app.canvas, app.game
    clip = surface.get_clip()
    surface.set_clip(map_rect)
    idle = {}
    for ship in game.ships:
        origin = app.star_pos(game.systems[ship.system_id])
        color = CYAN if ship.owner == PLAYER else RIVAL_COLOR
        if ship.in_transit:
            end = app.star_pos(game.systems[ship.destination])
            pg.draw.line(surface, tuple(c//3 for c in color), origin, end, 1)
            progress = 1-ship.turns_remaining/ship.travel_total
            position = (origin[0]+(end[0]-origin[0])*progress, origin[1]+(end[1]-origin[1])*progress)
            ship_icon(surface, position, .24, color)
        else:
            key = ship.owner, ship.system_id
            idle[key] = idle.get(key, 0)+1
    for (owner, system_id), count in idle.items():
        x, y = app.star_pos(game.systems[system_id])
        y += 24 if owner == PLAYER else 41
        color = CYAN if owner == PLAYER else RIVAL_COLOR
        ship_icon(surface, (x+22, y), .22, color)
        text(surface, str(count), (x+32, y-6), 10, color)
    if app.route_ship_id is not None:
        ship = game.ship_at(app.route_ship_id)
        origin = app.star_pos(game.systems[ship.system_id])
        end = app.star_pos(game.systems[game.selected_system])
        pg.draw.line(surface, GOLD, origin, end, 2)
    surface.set_clip(clip)
