"""Shipyard queue and fleet operations screens."""

import pygame as pg

from .colony_view import draw_planet_tabs, turn_label
from .fleet_art import ship_icon
from .production import MAX_QUEUE, PROJECTS, SHIP_TYPES, TROOP_STRENGTH
from .model import PLAYER, RIVAL
from .ui import CYAN, FAINT, GOLD, INK, LINE, MUTED, panel, paragraph, shorten, text

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
    app.button("shipyard_fleets", "Open fleets →", (924, 124, 190, 46), app.open_fleets)
    text(surface, f"YEAR {game.year} · {game.treasury_for(planet.owner or PLAYER):,} CR", (1376, 141), 12, GOLD, "mono", right=True)
    text(surface, shorten(planet.name, 720, 43, "title"), (64, 185), 43, INK, "title")
    text(surface, f"Shipyard · {game.planet_yields(planet)[0]} industry / turn · {game.empire_name_for(planet.owner)}",
         (66, 249), 14, MUTED)
    draw_planet_tabs(app, "shipyard")

    estimates = game.queue_estimates(planet)
    for index, spec in enumerate(SHIP_TYPES.values()):
        y = 306+index*164
        panel(surface, (64, y, 585, 158))
        ship_icon(surface, (119, y+64), .9, kind=spec.id)
        text(surface, spec.name, (170, y+8), 25, INK, "title")
        description = (f"{game.starting_colonists(planet.owner or PLAYER)} B colonists · {spec.hull} hull · Unarmed"
                       if spec.id == "colony_ship" else f"{spec.hull} hull · {TROOP_STRENGTH} invasion attack · Unarmed"
                       if spec.id == "troop_transport" else f"{spec.hull} hull · {spec.damage} damage per shot")
        text(surface, description, (171, y+45), 12, CYAN)
        captions = {"colony_ship": "Consumed when settling a world.", "frigate": "Engage opposing fleets in the same system.",
                    "troop_transport": "Consumed in invasions. Escort with frigates."}
        text(surface, captions[spec.id], (171, y+67), 12, MUTED)
        forecast = game.queue_estimates(planet, spec.id)
        eta = f"Ready in {turn_label(forecast[-1])}" if forecast else "Requires a colony"
        text(surface, f"{game.project_price(spec.id, planet.owner or PLAYER)} CR · {spec.work_cost} work · {eta}",
             (171, y+93), 12, INK)
        reason = game.ship_build_error(system.id, planet.id, spec.id)
        app.button(f"build_{spec.id}", f"Build {spec.name.lower()}", (88, y+119, 270, 31),
                   lambda kind=spec.id: app.queue_ship(kind), enabled=reason is None)
        text(surface, shorten(reason or "No building slot needed", 250, 11), (376, y+129), 11, GOLD if reason else MUTED)

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
                   "Build ships here, or choose buildings in the Colony tab.")
        paragraph(surface, message, (700, 462), 608, 15, MUTED, 25)
    text(surface, f"PAGE {app.shipyard_page+1} / {last+1}", (699, 754), 10, FAINT, "mono")
    app.button("queue_previous", "← Prev", (1080, 739, 126, 39), lambda: app.change_shipyard_page(-1), enabled=app.shipyard_page>0)
    app.button("queue_next", "Next →", (1220, 739, 133, 39), lambda: app.change_shipyard_page(1), enabled=app.shipyard_page<last)
    app.button("shipyard_pause", "Menu", (64, 834, 126, 45), app.pause)
    app.button("shipyard_save", "Save · F5", (204, 834, 172, 45), app.save_game)
    text(surface, "Fleets · F: travel and fight. Planet overview: settle or invade.", (400, 840), 12, MUTED)
    app.button("shipyard_end_turn", "End turn · E", (1081, 824, 295, 55), app.advance_turn, "primary")


def draw_fleets(app):
    surface, game = app.canvas, app.game
    ships = game.ships_owned_by()
    app.chrome("FLEET OPERATIONS")
    app.button("fleets_back", "←  Back · F", (64, 124, 190, 46), app.close_fleets, "ghost")
    app.button("fleets_galaxy", "Galaxy map", (269, 124, 174, 46), lambda: app.go("galaxy"), "ghost")
    text(surface, f"YEAR {game.year} · TURN {game.turn}", (1376, 141), 12, GOLD, "mono", right=True)
    text(surface, "Fleet operations", (64, 190), 43, INK, "title")
    text(surface, "Explore, settle and defend. Ships in the same system fight together.", (66, 251), 14, MUTED)
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
        ship_icon(surface, (100, y+38), .67, kind=ship.kind)
        text(surface, ship.name, (142, y+12), 18, INK)
        role = (f"{game.starting_colonists()} B colonists · Unarmed" if ship.kind == "colony_ship" else
                f"{TROOP_STRENGTH} invasion attack · Unarmed" if ship.kind == "troop_transport" else f"{ship.damage} damage / shot")
        text(surface, f"{ship.hull}/{ship.max_hull} hull · {role}", (143, y+43), 11, MUTED)
        origin = game.systems[ship.system_id]
        location = f"{origin.name} → {game.systems[ship.destination].name}" if ship.in_transit else f"{origin.name} orbit"
        text(surface, shorten(location, 467, 18), (473, y+12), 18, CYAN)
        encounter = not ship.in_transit and bool(game.fleet_at(ship.system_id, RIVAL))
        caption = (f"Arrives in {turn_label(ship.turns_remaining)}" if ship.in_transit else
                   "Opposing fleet here · Engage to begin combat" if encounter else
                   "Repairing +4 hull / turn" if ship.hull < ship.max_hull and game.can_repair(ship) else "Ready for orders")
        text(surface, caption, (474, y+43), 12, MUTED)
        if ship.in_transit:
            pg.draw.rect(surface, LINE, (474, y+65, 454, 2))
            pg.draw.rect(surface, GOLD, (474, y+65, int(454*(1-ship.turns_remaining/ship.travel_total)), 2))
        target = ship.destination if ship.in_transit else ship.system_id
        app.button(f"ship_view_{ship.id}", "System", (966, y+18, 109, 42), lambda s=target: app.open_system(s))
        app.button(f"ship_send_{ship.id}", "In transit" if ship.in_transit else "Course", (1087, y+18, 137, 42),
                   lambda sid=ship.id: app.plot_course(sid), enabled=not ship.in_transit)
        app.button(f"ship_engage_{ship.id}", "Engage", (1236, y+18, 116, 42),
                   lambda sid=ship.system_id: app.engage_request(sid),
                   enabled=not ship.in_transit and game.engagement_error(ship.system_id) is None)
    if not ships:
        panel(surface, (64, 429, 1312, 248))
        ship_icon(surface, (144, 526), 1.6)
        text(surface, "Your fleet starts at a shipyard.", (248, 467), 28, INK, "title")
        paragraph(surface, "Build colony ships to settle, frigates to fight, or troop transports to invade. Finished ships appear here in orbit.",
                  (250, 515), 995, 16, MUTED, 27)
        home = next(((s, p) for s in game.systems for p in s.worlds if p.owner == PLAYER), None)
        if home:
            s, p = home
            app.button("fleet_build_first", "Open colony shipyard", (250, 596, 327, 48),
                       lambda sid=s.id, pid=p.id: app.open_shipyard(sid, pid))
    text(surface, "Frigates fight. Colony ships settle worlds. Engage commits every ship in that system.", (64, 798), 12, MUTED)
    text(surface, f"PAGE {app.fleet_page+1} / {last+1}", (1069, 798), 10, FAINT, "mono", right=True)
    app.button("fleets_previous", "← Prev", (1100, 785, 129, 37), lambda: app.change_fleet_page(-1), enabled=app.fleet_page>0)
    app.button("fleets_next", "Next →", (1243, 785, 133, 37), lambda: app.change_fleet_page(1), enabled=app.fleet_page<last)
    app.button("fleets_pause", "Menu", (64, 834, 126, 45), app.pause)
    app.button("fleets_save", "Save · F5", (204, 834, 172, 45), app.save_game)
    text(surface, "+4 hull / turn at friendly colonies with no opposing ships in orbit.", (400, 845), 12, MUTED)
    app.button("fleets_end_turn", "End turn · E", (1081, 834, 295, 45), app.advance_turn)
