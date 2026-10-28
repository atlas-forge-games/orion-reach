"""Empire-wide economy and a sortable, paginated colony directory."""

import pygame as pg
from .habitat_modules import display_name

from .production import PROJECTS
from .colony_view import turn_label
from .empire import COLONIES_PER_PAGE, FILTERS, colony_rows, summarize_empire
from .planet_art import draw_planet
from .races import RACES
from .treasury import BANKRUPTCY_LIMIT
from .ui import CYAN, FAINT, GOLD, INK, LINE, MUTED, PANEL, RED, arrow, panel, shorten, text


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
                 "planet": "Planet overview", "colony": "Colony", "rival": "Rival report", "diplomacy": "Diplomacy", "research": "Research", "objectives": "Objectives",
                 "fleet": "Fleet overview", "exploration": "Exploration", "news": "Turn news"}.get(app.empire_return, "Galaxy map")
    app.button("empire_back", f"←  {back_name} · I", (64, 124, 282, 46),
               app.close_empire, "ghost")
    if app.empire_return != "galaxy":
        app.button("empire_galaxy", "Galaxy map", (361, 124, 172, 46), lambda: app.go("galaxy"), "ghost")
    app.button("empire_rival", "Rival report", (556, 124, 213, 46), app.open_rival)
    app.button("empire_specialists", "Specialists", (784, 124, 213, 46), app.open_specialists)
    text(surface, f"YEAR {game.year}   ·   TURN {game.turn}", (1376, 141), 12, GOLD, "mono", right=True)
    text(surface, shorten(game.empire_name, 930, 43, "title"), (64, 190), 43, INK, "title")
    text(surface, f"{RACES[game.race_id].name} · Your colonies, economy and construction at a glance.", (66, 251), 14, MUTED)
    text(surface, f"{summary.projects} PROJECT{'S' if summary.projects != 1 else ''} IN QUEUE",
         (1376, 215), 11, GOLD, "mono", 1, right=True)
    text(surface, f"{summary.idle} idle {'colonies' if summary.idle != 1 else 'colony'}", (1376, 248), 13, MUTED, right=True)

    stats = [
        ("COLONIES", str(summary.colonies), f"{summary.population:,} B · {summary.slaves} enslaved" if summary.slaves else f"{summary.population:,} B inhabitants", INK),
        ("TREASURY", f"{game.credits:,} CR", f"{summary.income:+,} CR net / turn", RED if game.credits < 0 else GOLD),
        ("TOTAL INDUSTRY", f"{summary.industry:,} IND", "Per turn · used locally", CYAN),
        ("RESEARCH STORED", f"{game.research:,} RP", f"+{summary.research:,} RP / turn", CYAN),
        ("BUILDING SLOTS", f"{summary.used_slots} / {summary.capacity}",
         f"{summary.capacity-summary.used_slots} free · queued slots included", INK),
        ("FOOD / CONSUMED", f"{summary.food_produced} / {summary.food_consumed}",
         f"{summary.food_shortages} shortages · supplies local", RED if summary.food_shortages else CYAN),
        ("RESOURCES", f"{game.resources:,} RES", f"{summary.resources:+} / turn · net", GOLD),
        ("ENERGY", "∞" if game.bonuses_for().get("unlimited_energy") else f"{summary.energy_generated}/{summary.energy_demand}",
         "Dyson grid · empire-wide" if game.bonuses_for().get("unlimited_energy") else f"{summary.energy_shortages} shortages · local", RED if summary.energy_shortages else CYAN),
    ]
    for i, (label, value, caption, color) in enumerate(stats):
        x = 64+i*166
        panel(surface, (x, 284, 150, 91))
        text(surface, label, (x+10, 295), 8, MUTED, "mono")
        text(surface, value, (x+10, 316), 18, color)
        text(surface, shorten(caption, 134, 9), (x+10, 352), 9, MUTED)

    debt_note = (f"Debt interest: {summary.interest:,} CR/turn (10%) · Bankruptcy at {BANKRUPTCY_LIMIT:,} CR · "
                 f"Projected treasury: {game.credits+summary.income:,} CR" if game.credits < 0 else
                 f"Negative credits cost 10% interest per turn. Bankruptcy at {BANKRUPTCY_LIMIT:,} CR.")
    text(surface, debt_note, (66, 380), 11, RED if game.credits+summary.income <= BANKRUPTCY_LIMIT else MUTED)
    text(surface, "COLONY DIRECTORY", (64, 402), 11, GOLD, "mono", 2)
    text(surface, f"{len(rows)} of {summary.colonies} {'colonies' if summary.colonies != 1 else 'colony'}", (338, 402), 12, MUTED)
    for i, key in enumerate(FILTERS):
        x = 782+i*120
        app.button(f"empire_filter_{key}", key.capitalize(), (x, 391, 114, 36),
                   lambda f=key: app.set_empire_filter(f))
        if app.empire_filter == key:
            pg.draw.line(surface, GOLD, (x, 427), (x+114, 427), 2)

    headings = [
        ("name", "COLONY / SYSTEM", 78, 250),
        ("population", "POP / LIMIT", 342, 104),
        ("food", "FOOD NET", 464, 88),
        ("industry", "INDUSTRY", 569, 77),
        ("income", "NET CR", 658, 77),
        ("research", "RESEARCH", 745, 81),
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
        if planet.habitat:
            from .mothership_art import draw
            draw(surface, (95, y+27), .5, app.empire_color(planet.owner))
        else:
            draw_planet(surface, planet, (95, y+27), 34, f"{game.seed}:{system.id}:{planet.id}")
        text(surface, shorten(planet.name, 202, 16), (125, y+7), 16, GOLD if active else INK)
        text(surface, shorten(f"{system.name} · Habitat" if planet.habitat else f"{system.name} · {planet.size}", 202, 11), (125, y+31), 11, MUTED)
        industry, income, research = game.planet_yields(planet)
        food = game.population_report(planet)
        pop = f"{planet.population}+{planet.slaves} S" if planet.slaves else f"{planet.population}/{food.capacity} B"
        text(surface, pop, (440, y+7), 15, INK, right=True)
        growth = f"Growth {food.progress}%" if food.growth_rate else "Limit reached" if planet.population>=food.capacity else "Growth paused"
        power = game.planet_energy(planet)
        text(surface, f"Power {power.balance}" if power.balance < 0 else growth, (440, y+31), 9, RED if power.balance < 0 else MUTED, right=True)
        text(surface, f"{food.balance:+}", (545, y+7), 16, RED if food.balance<0 else CYAN, right=True)
        text(surface, f"{food.produced} / {food.consumed} used", (545, y+31), 9, MUTED, right=True)
        for value, right, color in ((str(industry), 635, CYAN),
                                    (f"+{research}", 813, CYAN)):
            text(surface, value, (right, y+17), 16, color, right=True)
        text(surface, f"{income:+}", (721, y+7), 16, RED if income < 0 else INK, right=True)
        text(surface, f"{game.planet_maintenance(planet)} upkeep", (721, y+31), 9, MUTED, right=True)
        text(surface, f"{planet.used_slots} / {planet.building_capacity}", (918, y+6), 15, INK, right=True)
        text(surface, "Full" if not planet.free_slots else f"{planet.free_slots} free",
             (918, y+31), 10, GOLD if not planet.free_slots else MUTED, right=True)
        if planet.trade_goods:
            text(surface, "Trade Goods", (950, y+7), 15, INK)
            text(surface, f"+{game.trade_goods_income(planet)} CR/turn", (1318, y+8), 12, GOLD, right=True)
            text(surface, "Ongoing · after industry and credit strain", (950, y+31), 10, MUTED)
        elif planet.construction_queue:
            project = planet.construction_queue[0]
            definition = project.spec
            eta = game.queue_estimates(planet)[0]
            text(surface, shorten(display_name(definition, planet.habitat), 250, 15), (950, y+7), 15, INK)
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
    from .specialists import salaries
    interest_note = f" − {summary.interest} interest" if summary.interest else ""
    caption = f"Budget: {summary.gross_income} gross − {summary.maintenance} upkeep{interest_note} = {summary.income:+} CR/turn"
    text(surface, shorten(caption, 650, 12), (400, 835), 12, MUTED)
    fleet, pay = game.fleet_maintenance(), salaries(game)
    from .accession import upkeep
    outreach = upkeep(game)
    from .gas_giants import income as station_income
    orbital = station_income(game, 'player')[2]
    text(surface, f"Upkeep: {summary.maintenance-fleet-pay-outreach-orbital} facilities · {orbital} orbital · {fleet} ships · {pay} salaries · {outreach} outreach (CR/turn)",
         (400, 857), 11, FAINT)
    app.button("empire_end_turn", "End turn · E", (1081, 834, 295, 45), app.advance_turn)
