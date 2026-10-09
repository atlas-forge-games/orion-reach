"""Colony landscape, visual production totals, workers and compact construction."""

import math
import pygame as pg

from .building_art import draw_building_art
from .buildings import BUILDINGS, workforce_bonuses
from .colony_scene import draw_colony_scene
from .colony_view import building_effect, compact_yields
from .ground_combat import forces, training_limit
from .fleet_art import ship_icon
from .model import PLAYER, RIVAL
from .empires import empire_color
from .planet_art import draw_planet
from .population import BASE_FOOD, WORKER_ROLES, farmer_output
from .production import ASCENSION_GATE, PROJECTS, SHIP_TYPES
from .designs import HULLS
from . import raiding
from .ui import CYAN, FAINT, GOLD, INK, LINE, MUTED, PANEL, RED, RIVAL_COLOR, panel, paragraph, shorten, text

GREEN = (154, 200, 133)
SCIENCE = (165, 172, 232)
ROLE_COLORS = {"farmers": GREEN, "workers": GOLD, "scientists": SCIENCE}
SURFACE_RECT = (24, 314, 1392, 526)


def resource_icon(surface, kind, center, color, scale=1):
    x, y = center
    def pts(points):
        return [(round(x+a*scale), round(y+b*scale)) for a, b in points]
    line = max(1, round(2*scale))
    if kind == "credits":
        for dy in (7, 2, -3):
            pg.draw.ellipse(surface, color, (x-11*scale, y+(dy-5)*scale, 22*scale, 10*scale), line)
        pg.draw.line(surface, color, pts([(0, -7)])[0], pts([(0, 0)])[0], line)
    elif kind == "food":
        pg.draw.line(surface, color, pts([(0, 12)])[0], pts([(0, -12)])[0], line)
        for dy in (-6, 1, 8):
            for sign in (-1, 1):
                pg.draw.polygon(surface, color, pts([(0, dy+2), (sign*8, dy-5), (sign*9, dy+1), (0, dy+5)]))
    elif kind == "industry":
        pg.draw.line(surface, color, pts([(-7, 11)])[0], pts([(6, -5)])[0], max(2, round(5*scale)))
        pg.draw.polygon(surface, color, pts([(-3, -10), (3, -15), (15, -5), (9, 1)]))
    else:
        outline = pts([(-5, -13), (5, -13), (5, -3), (12, 10), (10, 13), (-10, 13), (-12, 10), (-5, -3)])
        pg.draw.polygon(surface, color, outline, line)
        pg.draw.line(surface, color, pts([(-7, 5)])[0], pts([(7, 5)])[0], line)


def worker_icon(surface, x, y, color):
    pg.draw.circle(surface, color, (x, y+4), 3)
    pg.draw.line(surface, color, (x, y+8), (x, y+15), 4)
    pg.draw.line(surface, color, (x-5, y+10), (x+5, y+10), 2)
    pg.draw.line(surface, color, (x, y+15), (x-4, y+22), 2)
    pg.draw.line(surface, color, (x, y+15), (x+4, y+22), 2)


def project_art(surface, item_id, rect, design=None):
    rect = pg.Rect(rect)
    if item_id in BUILDINGS:
        draw_building_art(surface, item_id, rect)
    elif item_id in SHIP_TYPES or design:
        ship_icon(surface, rect.center, min(rect.w/64, rect.h/74), kind=design.kind if design else item_id)
    else:
        pg.draw.ellipse(surface, CYAN, rect.inflate(-rect.w//3, -8), 4)
        pg.draw.ellipse(surface, GOLD, rect.inflate(-rect.w//2, -18), 2)


def system_panel(app, game, system, planet, live):
    panel(app.canvas, (24, 54, 248, 244))
    text(app.canvas, shorten(system.name.upper(), 174, 17), (38, 65), 17, GOLD)
    text(app.canvas, f"{len(system.worlds)} WORLDS", (258, 72), 9, MUTED, "mono", right=True)
    row_height = min(44, 192//max(1, len(system.worlds)))
    for index, world in enumerate(system.worlds):
        y = 95+index*row_height
        button = app.button(f"planet_world_{world.id}", "", (33, y-3, 230, row_height-2),
                            lambda pid=world.id: app.open_planet(pid), "hotspot")
        selected = world.id == planet.id
        if selected or app.is_active(button):
            pg.draw.rect(app.canvas, (24, 43, 50), button.rect)
        draw_planet(app.canvas, world, (46, y+(14 if row_height>=30 else 8)), 23 if row_height>=30 else 17, f"{game.seed}:{system.id}:{world.id}")
        color = empire_color(world.owner) if world.owner else MUTED
        label = world.name if row_height>=30 else f"{world.name} · {world.biome}"
        text(app.canvas, shorten(label, 155, 12 if row_height>=30 else 10), (64, y), 12 if row_height>=30 else 10, GOLD if selected else color)
        if row_height>=30:
            text(app.canvas, f"{world.biome} · {world.size} · {world.richness}", (64, y+18), 9, MUTED)
        basic = f"{world.workforce} B" if world.colonized else world.size[:1]
        text(app.canvas, basic, (255, y+1), 10, color, right=True)
    if len(system.worlds) <= 4:
        text(app.canvas, "COLORS IDENTIFY EACH EMPIRE", (38, 272), 9, MUTED, "mono")


def workforce_panel(app, game, planet, live):
    surface = app.canvas
    owned = live and planet.owner == PLAYER
    panel(surface, (286, 54, 774, 244))
    text(surface, "COLONY PRODUCTION / TURN", (302, 66), 10, GOLD, "mono", 1)
    industry, credits, research = game.planet_yields(planet) if live else (None, None, None)
    food = game.population_report(planet) if live else None
    counts = (f"{planet.population} NATIVE + {planet.slaves} SLAVES" if planet.slaves else
              f"{planet.population} WORKERS / {food.capacity if food else '—'} B LIMIT")
    text(surface, counts, (1043, 66), 10, INK, "mono", right=True)
    needs_food = game.bonuses_for(planet.owner or PLAYER).get("food_use_percent", 0) > -100
    upkeep = planet.maintenance_per_turn
    outputs = [("credits", "NET CREDITS", f"{credits:+}" if live else "—",
                f"{credits+upkeep} gross · {upkeep} upkeep" if live else "last survey", RED if live and credits < 0 else GOLD),
               ("food", "FOOD / USED", f"{food.produced} / {food.consumed}" if live else "—",
                (f"{food.balance:+} surplus" if needs_food else "not required") if live else "last survey", RED if live and food.balance < 0 else GREEN),
               ("industry", "INDUSTRY", str(industry) if live else "—",
                f"{food.assembly_industry} to assembly" if food and food.assembly_industry else "construction", CYAN),
               ("research", "RESEARCH", f"+{research}" if live else "—", "research points", SCIENCE)]
    for index, (kind, label, value, caption, color) in enumerate(outputs):
        x = 302+index*186
        panel(surface, (x, 86, 182, 57), (15, 28, 37))
        resource_icon(surface, kind, (x+20, 115), color, .8)
        text(surface, label, (x+40, 91), 9, MUTED, "mono")
        text(surface, value, (x+40, 109), 21, color)
        text(surface, caption, (x+174, 124), 9, MUTED, right=True)
    staff = workforce_bonuses(planet)
    details = {"farmers": f"{farmer_output(planet)} food each" if needs_food else "food not required",
               "workers": f"{1+staff.industry:g} base IND each", "scientists": f"{2+staff.research} base RP each"}
    for index, role in enumerate(WORKER_ROLES):
        y = 150+index*41
        count = getattr(planet, role)
        color = ROLE_COLORS[role]
        button = app.button("worker_"+role, "", (302, y, 742, 34), lambda job=role: app.select_worker_role(job),
                            "hotspot", enabled=owned and (count > 0 or app.worker_source is not None)
                            and (role != "farmers" or needs_food or count > 0))
        active = app.is_active(button)
        if active or app.worker_source == role:
            panel(surface, button.rect, (23, 38, 45), color)
        text(surface, role.upper(), (314, y+10), 10, color, "mono")
        text(surface, str(count), (440, y+6), 17, INK, right=True)
        for i in range(min(count, 24)):
            worker_icon(surface, 465+i*17, y+5, color)
        if count > 24:
            text(surface, f"+{count-24}", (883, y+9), 11, color)
        text(surface, details[role] if live else "last observed", (1032, y+10), 10, MUTED, right=True)
    if not live:
        caption = f"Stored survey · {planet.workforce} B inhabitants last observed. Current production is unknown."
    elif not planet.colonized:
        caption = f"{BASE_FOOD[planet.biome]} natural food · Establish a colony to assign workers."
    elif not owned:
        caption = "Foreign colony · Worker assignments are read-only."
    elif app.worker_source:
        caption = f"Move one of your {app.worker_source}: choose a different row. Click the same row to cancel."
    else:
        caption = f"Click a worker row, then its new job.  ·  {food.growth_caption}"
    text(surface, shorten(caption, 742, 11), (302, 279), 11, MUTED)


def construction_panel(app, game, system, planet, live):
    surface = app.canvas
    panel(surface, (1074, 54, 342, 244))
    text(surface, "CURRENT PROJECT", (1090, 66), 10, GOLD, "mono", 1)
    owned = live and planet.owner == PLAYER
    queue = planet.construction_queue
    if queue:
        project = queue[0]
        spec = project.spec
        text(surface, shorten(spec.name, 307, 20), (1090, 91), 20, INK)
        project_art(surface, project.item_id, (1095, 122, 93, 85), project.design)
        turns = game.queue_estimates(planet)[0] if live else None
        text(surface, f"{turns} {'turn' if turns == 1 else 'turns'}" if live else "Last observed", (1205, 131), 22, CYAN)
        text(surface, f"{project.progress} / {spec.work_cost} work", (1205, 169), 12, MUTED)
        pg.draw.rect(surface, LINE, (1090, 216, 310, 6))
        pg.draw.rect(surface, CYAN, (1090, 216, round(310*project.progress/spec.work_cost), 6))
        text(surface, f"{len(queue)-1} waiting · {project.remaining_work} work remaining", (1090, 232), 11, MUTED)
    else:
        text(surface, "No project observed" if not live else "Choose production" if owned else "No active project" if planet.colonized else "Unsettled world", (1090, 97), 22, INK)
        paragraph(surface, "Send a ship to refresh this survey." if not live else
                  "Build a structure or launch a ship from this colony." if owned else
                  "Production can be changed by this colony's owner." if planet.colonized else
                  "The Varkesh cannot colonize. Raid inhabited worlds for captives and credits." if raiding.is_varkesh(game) else
                  f"{planet.biome} · {planet.size} · {planet.richness} minerals. Bring a colony ship to settle here.",
                  (1090, 143), 306, 14, MUTED, 25)
    if owned:
        cost = game.buy_construction_cost(system.id, planet.id)
        app.button("planet_change", "Change", (1090, 257, 146, 29), app.open_production)
        app.button("planet_buy", f"Buy · {cost} CR" if queue else "Buy", (1246, 257, 154, 29), app.buy_production_request,
                   enabled=game.buy_construction_error(system.id, planet.id) is None)
    elif not live:
        text(surface, f"SURVEY: TURN {game.exploration.survey(system.id).last_seen}", (1090, 268), 11, MUTED, "mono")
    elif planet.owner in game.opponents:
        app.button("invade_planet", "Plan colony raid" if raiding.is_varkesh(game) else "Plan ground invasion", (1090, 257, 310, 29), app.invade_request,
                   enabled=game.invasion_error(system.id, planet.id) is None)
    else:
        reason = game.colonize_error(system.id, planet.id)
        app.button("colonize_planet", "Colonize", (1090, 257, 310, 29), app.colonize_request, enabled=reason is None)
        if reason:
            text(surface, shorten(reason, 310, 10), (1090, 232), 10, MUTED)


def draw_planet_overview(app):
    game, surface = app.game, app.canvas
    system = game.known_system(game.selected_system)
    planet = system.worlds[game.selected_planet]
    live = game.system_visible(system.id)
    text(surface, shorten(f"Colony of {planet.name}" if planet.colonized else planet.name, 780, 28, "title"),
         (24, 12), 28, INK, "title")
    text(surface, f"TURN {game.turn} · YEAR {game.year}     TREASURY {game.credits:,} CR", (1416, 22), 12, GOLD, "mono", right=True)
    system_panel(app, game, system, planet, live)
    workforce_panel(app, game, planet, live)
    construction_panel(app, game, system, planet, live)
    draw_colony_scene(app, SURFACE_RECT, game, system, planet, framed=False)
    # Planet facts sit over the landscape, leaving the city as the principal view.
    facts = f"{planet.biome} · {planet.size} · {planet.gravity} gravity · {planet.richness} minerals"
    panel(surface, (40, 330, 700, 34), (10, 23, 30))
    text(surface, facts, (52, 339), 13, INK)
    if planet.slaves or (raiding.is_varkesh(game, planet.owner) and (system.id, planet.id) == raiding.home_location(game, planet.owner)):
        panel(surface, (40, 372, 700, 62), (10, 23, 30))
        text(surface, f"SLAVE POPULATION: {planet.slaves} / 100 · NATIVE: {planet.population} B", (52, 383), 13, GOLD)
        text(surface, "Normal worker output and food use · 5% death chance per unit each turn", (52, 409), 12, MUTED)
    if planet.ascension_gate and live:
        app.button("planet_objectives", f"Ascension Gate · {planet.gate_charge}/5", (1110, 330, 288, 34), app.open_objectives)
    if planet.colonized:
        defence = forces(planet)
        caption = (f"{len(planet.buildings)} buildings · {len(planet.building_projects)} reserved / {planet.building_capacity} slots"
                   f"    GROUND: {defence.garrison} garrison + {defence.militia} militia · +{defence.defence_bonus}% firepower")
        if not live:
            caption += " · Last observed"
        elif training_limit(planet):
            caption += f" · Barracks +1/turn, limit {training_limit(planet)}"
        text(surface, shorten(caption, 1162, 12), (24, 854), 12, CYAN)
    else:
        text(surface, f"{planet.building_capacity} building slots · {planet.habitability}% habitability · {planet.orbit_au:.2f} AU", (24, 854), 12, MUTED)
    text(surface, "Click buildings to inspect · E: End turn · R: Research · I: Empire · P: Menu · F5: Save", (24, 877), 11, MUTED)
    app.button("planet_return", "Return", (1210, 851, 206, 42), lambda: app.go("system"), "primary")


def draw_production(app):
    game, surface = app.game, app.canvas
    sid, pid = game.selected_system, game.selected_planet
    planet = game.planet_at(sid, pid)
    text(surface, shorten(f"{planet.name} · Choose production", 1030, 35, "title"), (40, 28), 35, INK, "title")
    text(surface, f"{game.credits:,} CR AVAILABLE", (1400, 45), 15, GOLD, "mono", right=True)
    text(surface, "Start a new first project, or prioritize one in the queue. Paused projects keep their progress.", (40, 83), 15, MUTED)
    identifiers = list(BUILDINGS)+list(SHIP_TYPES)
    if "ascension_theory" in game.technology.completed:
        identifiers.append(ASCENSION_GATE.id)
    identifiers.extend(d.id for d in game.designs)
    catalog_pages = max(1, math.ceil(len(identifiers)/10))
    app.catalog_page = min(app.catalog_page, catalog_pages-1)
    for i, item_id in enumerate(identifiers[app.catalog_page*10:app.catalog_page*10+10]):
        spec = game.project_spec(item_id)
        design = game.design_for(item_id)
        x, y = 40+(i%2)*446, 125+(i//2)*135
        panel(surface, (x, y, 428, 120))
        project_art(surface, item_id, (x+10, y+14, 65, 72), design)
        text(surface, shorten(spec.name, 330, 18), (x+85, y+12), 18, INK)
        price = game.project_price(item_id)
        upkeep = getattr(spec, "maintenance", 0)
        cost = f"{price} CR · {spec.work_cost} work"+(f" · Upkeep {upkeep} CR/turn" if upkeep else "")
        text(surface, cost, (x+85, y+42), 10, GOLD)
        reason = game.project_error(sid, pid, item_id)
        detail = building_effect(game, spec, planet) if item_id in BUILDINGS else f"{spec.hull} hull · {game.beam_for(item_id).damage} attack" if item_id in SHIP_TYPES else "Unlock a scientific victory"
        if design:
            detail = f"{HULLS[design.kind].name} · {design.hull} hull · {design.damage} volley · {design.shields} shields"
        if item_id in BUILDINGS:
            text(surface, compact_yields(game, spec, planet), (x+85, y+62), 10, CYAN)
            text(surface, spec.workforce_text(planet.richness), (x+85, y+78), 10, CYAN)
        else:
            text(surface, shorten(detail, 327, 11), (x+85, y+64), 11, CYAN)
        app.button("production_build_"+item_id, "Start", (x+312, y+85, 100, 26),
                   lambda chosen=item_id: app.choose_production(chosen), enabled=reason is None)
        text(surface, shorten(reason or "Previous work is retained", 294, 10), (x+13, y+94), 10, MUTED)
    app.button("catalog_previous", "←", (40, 793, 64, 30), lambda: setattr(app, "catalog_page", app.catalog_page-1), enabled=app.catalog_page > 0)
    text(surface, f"Projects {app.catalog_page+1} / {catalog_pages}", (120, 801), 12, MUTED)
    app.button("catalog_next", "→", (334, 793, 64, 30), lambda: setattr(app, "catalog_page", app.catalog_page+1), enabled=app.catalog_page < catalog_pages-1)
    app.button("production_designer", "Ship designer →", (620, 793, 294, 30), app.open_designer)
    panel(surface, (944, 125, 456, 660))
    queue = planet.construction_queue
    text(surface, f"CONSTRUCTION QUEUE · {len(queue)}/20", (960, 143), 12, GOLD, "mono")
    pages = max(1, math.ceil(len(queue)/6))
    app.production_page = min(app.production_page, pages-1)
    estimates = game.queue_estimates(planet)
    for i in range(app.production_page*6, min(len(queue), (app.production_page+1)*6)):
        project = queue[i]
        spec = project.spec
        y = 180+(i%6)*82
        button = app.button(f"production_priority_{i}", "", (960, y, 370, 70),
                            lambda index=i: app.prioritize_production(index), "hotspot")
        panel(surface, button.rect, (18, 32, 41), GOLD if app.is_active(button) else LINE)
        text(surface, shorten(f"{i+1}. {spec.name}", 340, 15), (974, y+9), 15, INK)
        text(surface, f"{project.progress}/{spec.work_cost} work · completes in {estimates[i]} turns", (974, y+33), 11, CYAN)
        text(surface, "Current project" if i == 0 else "Click to make current", (974, y+52), 10, MUTED)
        app.button(f"production_cancel_{i}", "×", (1338, y, 46, 34), lambda index=i: app.cancel_construction(index))
        text(surface, f"+{project.refund}", (1362, y+47), 10, MUTED, right=True)
    if not queue:
        paragraph(surface, "Nothing queued. Choose a building or ship to begin production.", (971, 203), 393, 18, MUTED, 30)
    app.button("production_previous", "←", (960, 690, 68, 33), lambda: app.change_production_page(-1), enabled=app.production_page > 0)
    app.button("production_next", "→", (1316, 690, 68, 33), lambda: app.change_production_page(1), enabled=app.production_page < pages-1)
    text(surface, f"Page {app.production_page+1} / {pages}", (1116, 700), 12, MUTED)
    text(surface, "× cancels and refunds unspent work.", (960, 750), 12, MUTED)
    app.button("production_return", "Return to colony", (1122, 833, 278, 48), lambda: app.go("planet"), "primary")
