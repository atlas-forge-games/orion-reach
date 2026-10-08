"""Empire-wide economy and a sortable, paginated colony directory."""

import pygame as pg

from .production import PROJECTS
from .colony_view import turn_label
from .empire import COLONIES_PER_PAGE, FILTERS, colony_rows, summarize_empire
from .planet_art import draw_planet
from .races import RACES
from .ui import CYAN, FAINT, GOLD, INK, LINE, MUTED, PANEL, arrow, panel, shorten, text


def draw_empire(app):
    surface, game = app.canvas, app.game
    summary = summarize_empire(game)
    rows = colony_rows(game, app.empire_filter, app.empire_sort, app.empire_descending)
    last_page = max(0, (len(rows)-1)//COLONIES_PER_PAGE)
    app.empire_page = min(max(0, app.empire_page), last_page)
    start = app.empire_page*COLONIES_PER_PAGE
    visible = rows[start:start+COLONIES_PER_PAGE]

    app.chrome("EMPIRE OVERVIEW")
    back_name = {"galaxy": "Galaxy map", "system": "System overview", "shipyard": "Shipyard", "fleets": "Fleets",
                 "planet": "Planet overview", "colony": "Colony", "rival": "Rival report", "diplomacy": "Diplomacy", "research": "Research", "objectives": "Objectives"}[app.empire_return]
    app.button("empire_back", f"←  {back_name} · I", (64, 124, 282, 46),
               app.close_empire, "ghost")
    if app.empire_return != "galaxy":
        app.button("empire_galaxy", "Galaxy map", (361, 124, 172, 46), lambda: app.go("galaxy"), "ghost")
    app.button("empire_rival", "Rival report", (556, 124, 213, 46), app.open_rival)
    text(surface, f"YEAR {game.year}   ·   TURN {game.turn}", (1376, 141), 12, GOLD, "mono", right=True)
    text(surface, shorten(game.empire_name, 930, 43, "title"), (64, 190), 43, INK, "title")
    text(surface, f"{RACES[game.race_id].name} · Your colonies, economy and construction at a glance.", (66, 251), 14, MUTED)
    text(surface, f"{summary.projects} PROJECT{'S' if summary.projects != 1 else ''} IN QUEUE",
         (1376, 215), 11, GOLD, "mono", 1, right=True)
    text(surface, f"{summary.idle} idle {'colonies' if summary.idle != 1 else 'colony'}", (1376, 248), 13, MUTED, right=True)

    stats = [
        ("COLONIES", str(summary.colonies), f"{summary.population:,} B inhabitants", INK),
        ("TREASURY", f"{game.credits:,} CR", f"+{summary.income:,} CR / turn", GOLD),
        ("TOTAL INDUSTRY", f"{summary.industry:,} IND", "Per turn · used locally", CYAN),
        ("RESEARCH STORED", f"{game.research:,} RP", f"+{summary.research:,} RP / turn", CYAN),
        ("BUILDING SLOTS", f"{summary.used_slots} / {summary.capacity}",
         f"{summary.capacity-summary.used_slots} free · queued slots included", INK),
    ]
    for i, (label, value, caption, color) in enumerate(stats):
        x = 64+i*267
        panel(surface, (x, 284, 244, 91))
        text(surface, label, (x+17, 295), 9, MUTED, "mono", 1)
        text(surface, value, (x+17, 316), 24, color)
        text(surface, shorten(caption, 211, 11), (x+17, 352), 11, MUTED)

    text(surface, "COLONY DIRECTORY", (64, 402), 11, GOLD, "mono", 2)
    text(surface, f"{len(rows)} of {summary.colonies} {'colonies' if summary.colonies != 1 else 'colony'}", (338, 402), 12, MUTED)
    for i, key in enumerate(FILTERS):
        x = 816+i*143
        app.button(f"empire_filter_{key}", key.capitalize(), (x, 391, 131, 36),
                   lambda f=key: app.set_empire_filter(f))
        if app.empire_filter == key:
            pg.draw.line(surface, GOLD, (x, 427), (x+131, 427), 2)

    headings = [
        ("name", "COLONY / SYSTEM", 78, 286),
        ("population", "POPULATION", 387, 114),
        ("industry", "INDUSTRY", 508, 101),
        ("income", "INCOME", 619, 92),
        ("research", "RESEARCH", 722, 104),
        ("slots", "SLOTS", 839, 96),
    ]
    for key, label, x, width in headings:
        app.button(f"empire_sort_{key}", "", (x-5, 436, width, 28),
                   lambda k=key: app.sort_empire(k), "hotspot")
        active = app.empire_sort == key
        suffix = (" ↓" if app.empire_descending else " ↑") if active else ""
        text(surface, label+suffix, (x, 445), 9, GOLD if active else MUTED, "mono")
    text(surface, "CONSTRUCTION / COMPLETION", (950, 445), 9, MUTED, "mono")

    for index, (system, planet) in enumerate(visible):
        y = 474+index*60
        rect = pg.Rect(64, y, 1312, 54)
        panel(surface, rect, PANEL)
        button = app.button(f"empire_colony_{system.id}_{planet.id}", "", rect,
                            lambda s=system.id, p=planet.id: app.open_empire_colony(s, p), "hotspot")
        active = app.is_active(button)
        draw_planet(surface, planet, (95, y+27), 34, f"{game.seed}:{system.id}:{planet.id}")
        text(surface, shorten(planet.name, 244, 16), (125, y+7), 16, GOLD if active else INK)
        text(surface, shorten(f"{system.name} · {planet.size}", 244, 11), (125, y+31), 11, MUTED)
        industry, income, research = game.planet_yields(planet)
        for value, right, color in ((f"{planet.population} B", 485, INK),
                                    (str(industry), 593, CYAN), (f"+{income}", 698, INK),
                                    (f"+{research}", 813, CYAN)):
            text(surface, value, (right, y+17), 16, color, right=True)
        text(surface, f"{planet.used_slots} / {planet.building_capacity}", (918, y+6), 15, INK, right=True)
        text(surface, "Full" if not planet.free_slots else f"{planet.free_slots} free",
             (918, y+31), 10, GOLD if not planet.free_slots else MUTED, right=True)
        if planet.construction_queue:
            project = planet.construction_queue[0]
            definition = PROJECTS[project.item_id]
            eta = game.queue_estimates(planet)[0]
            text(surface, definition.name, (950, y+7), 15, INK)
            text(surface, turn_label(eta), (1318, y+8), 12, GOLD, right=True)
            waiting = len(planet.construction_queue)-1
            caption = f"{project.progress} / {definition.work_cost} work"
            if waiting:
                caption += f" · {waiting} waiting"
            text(surface, caption, (950, y+30), 10, MUTED)
            pg.draw.rect(surface, LINE, (950, y+48, 368, 2))
            pg.draw.rect(surface, GOLD, (950, y+48, int(368*project.progress/definition.work_cost), 2))
        else:
            text(surface, "Idle", (950, y+7), 15, MUTED)
            text(surface, "No free building slots" if not planet.free_slots else "Choose a project in the colony",
                 (950, y+31), 10, FAINT)
        arrow(surface, (1346, y+27), GOLD if active else MUTED)

    if not visible:
        panel(surface, (64, 474, 1312, 173))
        text(surface, "No colonies yet." if not summary.colonies else "No colonies match this filter.",
             (90, 501), 24, INK, "title")
        text(surface, "Explore the galaxy map." if not summary.colonies else "Choose All to return to the complete colony list.",
             (91, 544), 14, MUTED)
        if summary.colonies:
            app.button("empire_clear_filter", "Show all colonies", (91, 582, 230, 43),
                       lambda: app.set_empire_filter("all"))
    elif len(rows) == 1 and summary.colonies == 1:
        text(surface, "One colony. The beginning of your empire.", (82, 559), 15, MUTED)
        text(surface, "Open your colony to choose buildings and develop your economy.", (82, 585), 12, FAINT)

    text(surface, "Click a colony to manage it. Click a column heading to sort.", (65, 798), 12, MUTED)
    text(surface, f"PAGE {app.empire_page+1} / {last_page+1}", (1096, 798), 10, FAINT, "mono", right=True)
    app.button("empire_previous", "← Prev", (1117, 785, 122, 36), lambda: app.change_empire_page(-1),
               enabled=app.empire_page>0)
    app.button("empire_next", "Next →", (1254, 785, 122, 36), lambda: app.change_empire_page(1),
               enabled=app.empire_page<last_page)
    app.button("empire_pause", "Menu", (64, 834, 126, 45), app.pause)
    app.button("empire_save", "Save · F5", (204, 834, 172, 45), app.save_game)
    caption = (f"Agreements included: +{summary.agreement_income} CR, +{summary.agreement_research} RP / turn."
               if summary.agreement_income or summary.agreement_research else "All output rates are per turn. Industry stays on its planet.")
    text(surface, caption, (400, 835), 12, MUTED)
    text(surface, "Page Up / Down or mouse wheel: browse colonies", (400, 857), 11, FAINT)
    app.button("empire_end_turn", "End turn · E", (1081, 834, 295, 45), app.advance_turn)
