"""Colony management: building capacity, projects, costs and visible turn yields."""

import pygame as pg

from .buildings import BUILDINGS
from .building_art import draw_building_art
from .production import MAX_QUEUE
from .model import PLAYER
from .planet_art import draw_planet
from .ui import CYAN, FAINT, GOLD, INK, LINE, MUTED, PANEL, panel, shorten, text


def draw_planet_tabs(app, active):
    for key, label, x, screen in (("tab_overview", "Overview", 818, "planet"),
                                   ("tab_colony", "Colony", 1008, "colony"),
                                   ("tab_shipyard", "Shipyard", 1198, "shipyard")):
        app.button(key, label, (x, 201, 178, 49), lambda s=screen: app.go(s),
                   enabled=screen=="planet" or app.game.system_visible(app.game.selected_system))
        if screen == active:
            pg.draw.line(app.canvas, GOLD, (x, 250), (x+178, 250), 3)


def compact_yields(game, definition, planet):
    values = game.building_yields(definition, planet)
    return " · ".join(f"+{v} {unit}" for v, unit in zip(values, ("IND", "CR", "RP")) if v)


def turn_label(count):
    return f"{count} {'turn' if count == 1 else 'turns'}"


def draw_colony(app):
    surface, game = app.canvas, app.game
    system = game.systems[game.selected_system]
    planet = system.worlds[game.selected_planet]
    app.chrome("COLONY MANAGEMENT")
    app.button("colony_back", "←  Planet overview", (64, 124, 246, 47), lambda: app.go("planet"), "ghost")
    text(surface, shorten(f"{system.name.upper()}  /  {planet.name.upper()}", 580, 11, "mono"),
         (347, 143), 11, MUTED, "mono", 1)
    text(surface, f"YEAR {game.year}   ·   TURN {game.turn}", (1376, 141), 12, GOLD, "mono", right=True)

    text(surface, shorten(planet.name, 620, 43, "title"), (64, 185), 43, INK, "title")
    status = f"{planet.population} B · {game.empire_name_for(planet.owner)}" if planet.colonized else "Uncolonized"
    text(surface, f"{planet.biome}  ·  {planet.size} world  ·  {status}", (66, 249), 14, MUTED)
    draw_planet(surface, planet, (756, 222), 60, f"{game.seed}:{system.id}:{planet.id}")
    draw_planet_tabs(app, "colony")

    industry, income, science = game.planet_yields(planet)
    stats = [("INDUSTRY / TURN", f"{industry} IND"), ("INCOME / TURN", f"+{income} CR"),
             ("RESEARCH / TURN", f"+{science} RP"), ("EMPIRE TREASURY", f"{game.treasury_for(planet.owner or PLAYER):,} CR"),
             ("RESEARCH STORED", f"{game.research_for(planet.owner or PLAYER):,} RP")]
    for i, (label, value) in enumerate(stats):
        x = 64+i*267
        panel(surface, (x, 287, 244, 76))
        text(surface, label, (x+17, 300), 9, MUTED, "mono", 1)
        text(surface, value, (x+17, 324), 22, GOLD if i==3 else CYAN if i in (0, 2, 4) else INK)

    text(surface, "BUILDING SLOTS", (64, 385), 11, GOLD, "mono", 2)
    building_projects = planet.building_projects
    text(surface, f"{len(planet.buildings)} built + {len(building_projects)} reserved / {planet.building_capacity}",
         (727, 385), 11, MUTED, "mono", right=True)
    text(surface, "CONSTRUCTION CATALOGUE", (751, 385), 11, GOLD, "mono", 2)
    estimates = game.queue_estimates(planet)
    for index in range(12):
        x, y = 64+(index%4)*168, 414+(index//4)*94
        rect = pg.Rect(x, y, 158, 84)
        available = index < planet.building_capacity
        selected = index == app.colony_slot
        panel(surface, rect, (13, 27, 36) if selected else PANEL,
              GOLD if selected else LINE if available else (21, 34, 43))
        text(surface, f"{index+1:02}", (x+133, y+9), 9, FAINT, "mono")
        if not available:
            pg.draw.rect(surface, FAINT, (x+18, y+20, 17, 15), 1, border_radius=2)
            pg.draw.arc(surface, FAINT, (x+21, y+12, 11, 16), 0, 3.14, 1)
            text(surface, "Size limit", (x+12, y+46), 13, FAINT)
            continue
        if index < len(planet.buildings):
            building_id = planet.buildings[index]
            definition = BUILDINGS[building_id]
            draw_building_art(surface, building_id, (x+6, y+5, 44, 34))
            text(surface, "OPERATIONAL", (x+52, y+20), 8, CYAN, "mono")
            text(surface, definition.name, (x+12, y+42), 13, INK)
            text(surface, compact_yields(game, definition, planet), (x+12, y+63), 10, MUTED)
        elif index < planet.used_slots:
            queue_index, project = building_projects[index-len(planet.buildings)]
            definition = BUILDINGS[project.item_id]
            draw_building_art(surface, project.item_id, (x+6, y+5, 44, 34), alpha=130)
            label = "BUILDING" if queue_index==0 else f"QUEUED {queue_index+1}"
            text(surface, label, (x+52, y+11), 8, GOLD, "mono")
            text(surface, turn_label(estimates[queue_index]), (x+52, y+27), 10, MUTED)
            text(surface, definition.name, (x+12, y+46), 13, INK)
            pg.draw.rect(surface, LINE, (x+12, y+72, 134, 3))
            pg.draw.rect(surface, GOLD, (x+12, y+72, int(134*project.progress/definition.work_cost), 3))
        else:
            pg.draw.line(surface, FAINT, (x+19, y+25), (x+35, y+25))
            pg.draw.line(surface, FAINT, (x+27, y+17), (x+27, y+33))
            text(surface, "Available" if planet.colonized else "Undeveloped", (x+12, y+46), 13, MUTED)
            text(surface, "Choose a building" if planet.colonized else "Colony required", (x+12, y+65), 10, FAINT)
        app.button(f"colony_slot_{index}", "", rect, lambda i=index: app.select_colony_slot(i), "hotspot")

    # Four initial buildings; repeat copies are allowed, constrained by slots and credits.
    for i, definition in enumerate(BUILDINGS.values()):
        x, y = 751, 414+i*97
        panel(surface, (x, y, 625, 87))
        draw_building_art(surface, definition.id, (x+7, y+8, 56, 66))
        text(surface, definition.name, (x+70, y+10), 18, INK)
        text(surface, compact_yields(game, definition, planet)+" / turn", (x+70, y+36), 12, CYAN)
        estimate = game.queue_estimates(planet, additional=definition.id)
        eta = turn_label(estimate[-1]) if estimate else "Requires colony"
        price = game.project_price(definition.id, planet.owner or PLAYER)
        text(surface, f"{price} CR   ·   {definition.work_cost} work   ·   {eta}",
             (x+70, y+61), 11, MUTED)
        reason = game.build_error(system.id, planet.id, definition.id)
        label = "Build"
        hint = "1 slot"
        if not planet.colonized:
            label, hint = "Locked", "Uncolonized"
        elif planet.owner != PLAYER:
            label, hint = "Rival", "Survey only"
        elif planet.free_slots <= 0:
            label, hint = "Full", "No free slots"
        elif len(planet.construction_queue) >= MAX_QUEUE:
            label, hint = "Full", "Queue limit"
        elif game.credits < price:
            label, hint = "Funds", f"Need {price} CR"
        app.button(f"build_{definition.id}", label, (x+506, y+12, 103, 42),
                   lambda b=definition.id: app.queue_building(b), enabled=reason is None)
        text(surface, hint, (x+510, y+62), 9, FAINT, "mono")

    # Inspect an existing building or queued project, with reversible queue cancellation.
    panel(surface, (64, 711, 662, 82))
    slot = app.colony_slot
    if slot is not None and 0 <= slot < len(planet.buildings):
        definition = BUILDINGS[planet.buildings[slot]]
        text(surface, definition.name, (82, 724), 18, INK)
        text(surface, compact_yields(game, definition, planet)+" / turn", (82, 754), 13, CYAN)
        app.button("demolish_building", "Demolish", (549, 729, 156, 45),
                   lambda i=slot: app.demolish_request(i), enabled=planet.owner == PLAYER)
    elif slot is not None and len(planet.buildings) <= slot < planet.used_slots:
        index, project = building_projects[slot-len(planet.buildings)]
        definition = BUILDINGS[project.item_id]
        text(surface, definition.name, (82, 724), 18, INK)
        text(surface, f"{project.progress}/{definition.work_cost} work · Ready in {turn_label(estimates[index])}",
             (82, 754), 12, GOLD)
        app.button("cancel_construction", "Cancel", (549, 718, 156, 43),
                   lambda i=index: app.cancel_construction(i), enabled=planet.owner == PLAYER)
        text(surface, f"Refund: {project.refund} CR", (553, 772), 10, MUTED)
    else:
        title = f"{planet.size} worlds support {planet.building_capacity} buildings."
        message = "Buildings reserve slots. The Shipyard tab shows the full production queue."
        if not planet.colonized:
            title = "This planet needs a colony first."
            message = "Bring a colony ship here, then settle this world from its Overview tab."
        elif planet.owner != PLAYER:
            title = "Rival colony · survey only"
            message = "The Helios Directorate chooses construction on this world."
        text(surface, title, (82, 725), 17, INK)
        text(surface, message, (82, 756), 12, MUTED)

    app.button("colony_pause", "Menu", (64, 828, 126, 51), app.pause)
    app.button("colony_save", "Save · F5", (204, 828, 172, 51), app.save_game)
    text(surface, "Pay when queued. Output starts the turn after completion.", (399, 828), 12, MUTED)
    text(surface, "Research · R: choose technologies to improve your empire.", (399, 850), 11, FAINT)
    app.button("colony_end_turn", "End turn · E", (1081, 816, 295, 63), app.advance_turn, "primary")
