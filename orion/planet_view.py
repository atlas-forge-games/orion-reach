"""Colony landscape, visual production totals, workers and compact construction."""

import math
import pygame as pg

from .building_art import draw_building_art
from .buildings import BUILDINGS, workforce_bonuses
from .colony_scene import draw_colony_scene
from .colony_view import building_effect, compact_yields, turn_label
from .ground_combat import forces, training_limit
from .fleet_art import ship_icon
from .model import PLAYER, RIVAL
from .planet_art import draw_planet
from .population import BASE_FOOD, WORKER_ROLES, farmer_output
from .production import ASCENSION_GATE, PROJECTS, SHIP_TYPES, TRADE_GOODS
from .research import building_maintenance
from .designs import HULLS
from . import raiding, defenses, economy
from . import production as production_balance, research as research_balance
from .ui import CYAN, FAINT, GOLD, INK, LINE, MUTED, PANEL, RED, RIVAL_COLOR, panel, paragraph, shorten, text

GREEN = (154, 200, 133)
SCIENCE = (165, 172, 232)
ROLE_COLORS = {"farmers": GREEN, "workers": GOLD, "scientists": SCIENCE, "miners": (204, 163, 122)}
ROLE_LABELS = {"farmers": "FARMING", "workers": "INDUSTRY", "scientists": "RESEARCH", "miners": "MINING"}
MAX_WORKER_ICONS = 24
SURFACE_RECT = (24, 314, 1392, 526)


def worker_row_rect(role):
    return pg.Rect(302, 148+WORKER_ROLES.index(role)*31, 742, 29)


def worker_icon_layout(count):
    # Show the rightmost workers: even large captive populations have an exact
    # clickable tail. The preceding hidden group gets its own +N indicator.
    return (507, 15) if count > MAX_WORKER_ICONS else (465, 17)


def worker_selection_count(count, x=None):
    """A worker or the gap before it picks everyone from that point rightward."""
    if not count:
        return 0
    if x is None:
        return 1  # Keyboard activation starts with one; arrows adjust quantity.
    if x < (498 if count > MAX_WORKER_ICONS else 454):
        return count
    first, step = worker_icon_layout(count)
    visible = min(count, MAX_WORKER_ICONS)
    index = max(0, min(visible-1, math.ceil((x-first-5)/step)))
    return visible-index


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
    elif kind == "resources":
        pg.draw.polygon(surface, color, pts([(-12, 6), (-8, -8), (1, -13), (12, -4), (10, 10), (-2, 13)]), line)
        for a, b in (((-8,-8),(2,2)), ((12,-4),(2,2)), ((-2,13),(2,2))):
            pg.draw.line(surface, color, pts([a])[0], pts([b])[0], line)
    elif kind == "energy":
        pg.draw.polygon(surface, color, pts([(2,-14), (-10,3), (-1,3), (-4,15), (11,-4), (3,-4)]))
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


def empire_stockpile(app, rect):
    """Keep the player's shared reserves distinct from this colony's yields."""
    game, surface = app.game, app.canvas
    rect = pg.Rect(rect)
    panel(surface, rect)
    text(surface, "EMPIRE", (rect.x+10, rect.y+6), 9, MUTED, "mono")
    text(surface, "STOCKPILE", (rect.x+10, rect.y+21), 9, MUTED, "mono")
    income, research = game.empire_rates
    items = (("credits", "Credits", game.credits, income, GOLD),
             ("resources", "Resources", game.resources, game.resource_rate(), ROLE_COLORS["miners"]),
             ("research", "Research", game.research, research, SCIENCE))
    width = (rect.w-100)//len(items)
    for index, (kind, label, amount, rate, color) in enumerate(items):
        x = rect.x+100+index*width
        pg.draw.line(surface, LINE, (x, rect.y+6), (x, rect.bottom-6))
        resource_icon(surface, kind, (x+15, rect.y+19), color, .45)
        text(surface, f"{label} {amount:,}", (x+30, rect.y+3), 12, RED if amount < 0 else color)
        text(surface, f"{rate:+,} / turn"+(" net" if kind != "research" else ""),
             (x+30, rect.y+22), 9, RED if rate < 0 else MUTED)


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
        color = app.empire_color(world.owner or world.outpost_owner) if world.owner or world.outpost_owner else MUTED
        label = world.name if row_height>=30 else f"{world.name} · {world.biome}"
        text(app.canvas, shorten(label, 155, 12 if row_height>=30 else 10), (64, y), 12 if row_height>=30 else 10, GOLD if selected else color)
        if row_height>=30:
            text(app.canvas, f"{world.biome} · {world.size} · {world.richness}", (64, y+18), 9, MUTED)
        basic = f"{world.workforce} B" if world.colonized else "BASE" if world.outpost_owner else world.size[:1]
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
    upkeep = game.planet_maintenance(planet)
    outputs = [("credits", "NET CREDITS", f"{credits:+}" if live else "—",
                f"{credits+upkeep} gross · {upkeep} upkeep" if live else "last survey", RED if live and credits < 0 else GOLD),
               ("food", "FOOD / USED", f"{food.produced} / {food.consumed}" if live else "—",
                (f"{food.balance:+} surplus" if needs_food else "not required") if live else "last survey", RED if live and food.balance < 0 else GREEN),
               ("industry", "INDUSTRY", str(industry) if live else "—",
                f"{food.assembly_industry} to assembly" if food and food.assembly_industry else "Trade Goods" if planet.trade_goods else "construction", CYAN),
               ("research", "RESEARCH", f"+{research}" if live else "—", "research points", SCIENCE)]
    energy = game.planet_energy(planet) if live else None
    outputs += [("resources", "RESOURCES", f"{game.planet_resources(planet):+}" if live else "—",
                 f"{game.resources:,} stored" if owned else "mined / turn", ROLE_COLORS["miners"]),
                ("energy", "ENERGY", (f"∞ / {energy.demand}" if energy.unlimited else f"{energy.generated}/{energy.demand}") if live else "—",
                 ("Dyson grid · no fuel" if energy.unlimited else f"{energy.fuel_used} RES fuel/turn" if energy.fuel_used else f"{energy.balance:+} surplus") if live else "last survey", RED if live and energy.balance < 0 else GOLD)]
    for index, (kind, label, value, caption, color) in enumerate(outputs):
        x = 302+index*124
        panel(surface, (x, 86, 120, 57), (15, 28, 37))
        resource_icon(surface, kind, (x+14, 114), color, .6)
        text(surface, label, (x+7, 91), 8, MUTED, "mono")
        text(surface, value, (x+32, 105), 19, color)
        text(surface, shorten(caption, 108, 8), (x+7, 130), 8, MUTED)
    benefits = game.bonuses_for(planet.owner) if live else {}
    staff = workforce_bonuses(planet, benefits)
    details = {"farmers": f"{farmer_output(planet, benefits)} base food each" if needs_food else "food not required",
               "workers": f"{research_balance.WORKER_INDUSTRY+staff.industry:g} base IND each", "scientists": f"{research_balance.SCIENTIST_RESEARCH+staff.research} base RP each",
               "miners": f"{economy.miner_output(planet, benefits):g} base RES each"}
    preview = None
    for role in WORKER_ROLES:
        rect = worker_row_rect(role)
        y = rect.y
        count = getattr(planet, role)
        color = ROLE_COLORS[role]
        button = app.button("worker_"+role, "", rect, lambda job=role: app.select_worker_role(job),
                            "hotspot", enabled=owned and (count > 0 or app.worker_source is not None)
                            and (role != "farmers" or needs_food or count > 0))
        active = button.enabled and app.is_active(button)
        selected = min(count, app.worker_count) if app.worker_source == role else 0
        if active and not app.worker_source:
            selected = worker_selection_count(count, None if app.keyboard_mode else app.mouse[0])
            preview = role, selected
        if active or app.worker_source == role:
            panel(surface, button.rect, (23, 38, 45), color)
        text(surface, ROLE_LABELS[role], (314, y+9), 10, color, "mono")
        text(surface, str(count), (440, y+4), 17, INK, right=True)
        first, step = worker_icon_layout(count)
        visible = min(count, MAX_WORKER_ICONS)
        selected_visible = min(selected, visible)
        if selected_visible:
            left = first+(visible-selected_visible)*step-7
            right = first+(visible-1)*step+8
            panel(surface, (left, y+1, right-left, 27), tuple(c//4 for c in color), color)
        for i in range(visible):
            worker_icon(surface, first+i*step, y+2, INK if i >= visible-selected_visible else color)
        if count > visible:
            hidden = count-visible
            selected_hidden = max(0, selected-visible)
            if selected_hidden:
                panel(surface, (454, y+1, 44, 27), tuple(c//4 for c in color), color)
            label = f"{selected_hidden}/{hidden}" if 0 < selected_hidden < hidden else f"+{hidden}"
            text(surface, label, (459, y+9), 9, INK if selected_hidden else color)
        text(surface, details[role] if live else "last observed", (1032, y+9), 10, MUTED, right=True)
    if not live:
        caption = f"Stored survey · {planet.workforce} B inhabitants last observed. Current production is unknown."
    elif not planet.colonized:
        caption = f"{BASE_FOOD[planet.biome]} natural food · Establish a colony to assign workers."
    elif not owned:
        caption = "Foreign colony · Worker assignments are read-only."
    elif app.worker_source:
        caption = f"{app.worker_count} selected from {ROLE_LABELS[app.worker_source].lower()} · Click destination · ←/→ quantity · Same row / Esc cancels"
    elif preview:
        caption = f"Select {preview[1]} from {ROLE_LABELS[preview[0]].lower()} · Click here, then click the destination job."
    else:
        caption = f"Click a worker or gap to select everyone to its right, then a new job. · {food.growth_caption}"
    text(surface, shorten(caption, 742, 11), (302, 279), 11, MUTED)


def construction_panel(app, game, system, planet, live):
    surface = app.canvas
    panel(surface, (1074, 54, 342, 244))
    text(surface, "CURRENT PROJECT", (1090, 66), 10, GOLD, "mono", 1)
    if planet.outpost_owner:
        from . import outposts
        text(surface, "Refuelling outpost", (1090, 97), 22, INK)
        text(surface, shorten(game.empire_name_for(planet.outpost_owner), 306, 14), (1090, 135), 14, CYAN)
        text(surface, f"Hull {planet.outpost_hull}/{outposts.OUTPOST_HULL} · No population", (1090, 164), 13, INK)
        paragraph(surface, "Extends ship range. No production or upkeep. Unarmed; protect it with a fleet.",
                  (1090, 188), 306, 12, MUTED, 18)
        if live and not game.is_observer and planet.outpost_owner != PLAYER:
            reason = outposts.attack_error(game, system.id, planet.id)
            app.button("attack_outpost", "Attack outpost", (1090, 257, 310, 29), app.attack_outpost_request, enabled=reason is None)
            if reason:
                text(surface, shorten(reason, 310, 10), (1090, 235), 10, MUTED)
        elif live and not game.is_observer:
            reason = game.colonize_error(system.id, planet.id)
            app.button("colonize_planet", "Upgrade to colony", (1090, 257, 310, 29), app.colonize_request, enabled=reason is None)
            text(surface, shorten(reason or "Consumes a colony ship; replaces the outpost.", 310, 10), (1090, 235), 10, MUTED)
        else:
            text(surface, "OBSERVING" if live else "LAST OBSERVED OUTPOST", (1090, 268), 11, MUTED, "mono")
        return
    owned = live and planet.owner == PLAYER
    queue = planet.construction_queue
    visible = owned or game.is_observer or not live or planet.owner not in game.opponents
    if planet.trade_goods and visible:
        text(surface, "Trade Goods", (1090, 91), 22, INK)
        project_art(surface, "trade_center", (1095, 122, 93, 85))
        rate = game.trade_goods_income(planet) if live else None
        text(surface, f"+{rate} CR / turn" if live else "Last observed", (1200, 134), 19, GOLD)
        text(surface, "Ongoing production", (1200, 171), 12, CYAN)
        text(surface, f"{production_balance.TRADE_GOODS_PERCENT}% of industry, then credit strain", (1090, 213), 12, MUTED)
        text(surface, f"{len(queue)} projects paused · Progress kept" if queue else "No resource cost or building slot", (1090, 236), 11, MUTED)
    elif queue and visible:
        project = queue[0]
        spec = project.spec
        text(surface, shorten(spec.name, 307, 20), (1090, 91), 20, INK)
        project_art(surface, project.item_id, (1095, 122, 93, 85), project.design)
        turns = game.queue_estimates(planet)[0] if live else None
        text(surface, turn_label(turns) if live else "Last observed", (1205, 131), 22, CYAN)
        text(surface, f"{project.progress} / {spec.work_cost} work", (1205, 169), 12, MUTED)
        pg.draw.rect(surface, LINE, (1090, 216, 310, 6))
        pg.draw.rect(surface, CYAN, (1090, 216, round(310*project.progress/spec.work_cost), 6))
        text(surface, shorten(game.construction_status(planet) if owned or game.is_observer else "Last observed project", 310, 11), (1090, 232), 11, GOLD)
    else:
        text(surface, "No project observed" if not live else "Choose production" if owned else "No active project" if planet.colonized else "Unsettled world", (1090, 97), 22, INK)
        paragraph(surface, "Send a ship to refresh this survey." if not live else
                  "This civilization chooses its own construction and worker assignments." if game.is_observer and planet.colonized else
                  "An unsettled world. Watch which civilization reaches it first." if game.is_observer else
                  "Build a structure or launch a ship from this colony." if owned else
                  f"Active shield: {defenses.effective_shield(game, planet)} points. Clear orbital defenders before landing troops." if planet.colonized else
                  "The Varkesh cannot colonize. Raid inhabited worlds for captives and credits." if raiding.is_varkesh(game) else
                  "A colony ship settles this world. An outpost ship builds a refuelling base on any biome.",
                  (1090, 143), 306, 14, MUTED, 25)
    if game.is_observer:
        if planet.colonized:
            app.button("observer_planet_empire", "Inspect civilization", (1090, 257, 310, 29),
                       lambda: app.open_observed_empire(planet.owner))
        else:
            text(surface, "OBSERVING · NO ORDERS", (1090, 268), 11, MUTED, "mono")
    elif owned:
        cost = game.buy_construction_cost(system.id, planet.id)
        app.button("planet_change", "Change", (1090, 257, 146, 29), app.open_production)
        app.button("planet_buy", f"Buy · {cost} CR" if queue and not planet.trade_goods else "Buy", (1246, 257, 154, 29), app.buy_production_request,
                   enabled=game.buy_construction_error(system.id, planet.id) is None)
    elif not live:
        text(surface, f"SURVEY: TURN {game.exploration.survey(system.id).last_seen}", (1090, 268), 11, MUTED, "mono")
    elif planet.owner in game.opponents:
        app.button("bombard_planet", "Bombard defenses", (1090, 220, 310, 29), app.bombard_request,
                   enabled=game.bombardment_error(system.id, planet.id) is None)
        app.button("invade_planet", "Plan colony raid" if raiding.is_varkesh(game) else "Plan ground invasion", (1090, 257, 310, 29), app.invade_request,
                   enabled=game.invasion_error(system.id, planet.id) is None)
    else:
        from . import outposts
        reason = game.colonize_error(system.id, planet.id)
        outpost_reason = outposts.deployment_error(game, system.id, planet.id)
        app.button("colonize_planet", "Colonize", (1090, 257, 146, 29), app.colonize_request, enabled=reason is None)
        app.button("establish_outpost", "Build outpost", (1246, 257, 154, 29), app.outpost_request, enabled=outpost_reason is None)
        if outpost_reason and outposts.ships_at(game, system.id):
            text(surface, shorten(outpost_reason, 310, 10), (1090, 213), 10, MUTED)
        if reason:
            text(surface, shorten(reason, 310, 10), (1090, 232), 10, MUTED)


def draw_planet_overview(app):
    game, surface = app.game, app.canvas
    system = game.known_system(game.selected_system)
    planet = system.worlds[game.selected_planet]
    live = game.system_visible(system.id)
    text(surface, shorten(f"Colony of {planet.name}" if planet.colonized else planet.name, 780 if game.is_observer else 460, 28, "title"),
         (24, 12), 28, INK, "title")
    if game.is_observer:
        text(surface, f"TURN {game.turn} · YEAR {game.year}     OBSERVER · READ ONLY",
             (1416, 22), 12, GOLD, "mono", right=True)
    else:
        text(surface, f"TURN {game.turn}", (654, 12), 10, MUTED, "mono", right=True)
        text(surface, f"YEAR {game.year}", (654, 29), 10, MUTED, "mono", right=True)
        empire_stockpile(app, (676, 8, 740, 38))
    system_panel(app, game, system, planet, live)
    workforce_panel(app, game, planet, live)
    construction_panel(app, game, system, planet, live)
    show_administration = live and planet.colonized and (planet.owner == PLAYER or game.is_observer)
    scene_rect = (24, 314, 1392, 406) if show_administration else SURFACE_RECT
    draw_colony_scene(app, scene_rect, game, system, planet, framed=False)
    if show_administration:
        from .administration import MAX_STRAIN
        strain = game.strain_report(planet)
        panel(surface, (40, 728, 900, 100), (10, 23, 30))
        text(surface, f"ADMINISTRATION · {strain.total:.1f}% STRAIN · {strain.systems} settled systems",
             (52, 740), 12, GOLD, "mono")
        text(surface, f"Empire {strain.empire:g}% + integration {strain.integration:g}% + local distance {strain.distance:.1f}% · cap {MAX_STRAIN:g}%",
             (52, 763), 12, INK)
        text(surface, f"Output loss: RP {strain.loss('research'):.1f}% · CR {strain.loss('credits'):.1f}% · IND {strain.loss('industry'):.1f}% · RES {strain.loss('mining'):.1f}% · food {strain.loss('food'):.1f}%",
             (52, 784), 12, MUTED)
        location = f"Capital: {strain.capital} · {strain.distance_ly:.1f} ly away"
        location += f" · This system integrates in {strain.integration_remaining} turns" if strain.integration_remaining else " · This system integrated"
        text(surface, shorten(location, 876, 11), (52, 806), 11, CYAN)
    if planet.owner == PLAYER and live:
        from . import specialists
        leader = next((p for p in specialists.employed(game) if p.spec.role == "leader"
                       and (p.system_id, p.planet_id) == (system.id, planet.id)), None)
        panel(surface, (954, 728, 444, 50), (10, 23, 30))
        caption = f"Leader: {leader.spec.name} · Level {leader.level}" if leader else "Leader: none assigned"
        if leader:
            from .specialist_art import draw_portrait
            draw_portrait(surface, leader.spec, (960, 733, 40, 40))
        text(surface, shorten(caption, 374 if leader else 420, 13), (1012 if leader else 966, 748), 13, CYAN if leader else MUTED)
        count = len(specialists.visitors(game))
        app.button("planet_specialists", f"Specialists · {count} visitors", (1104, 788, 294, 39), app.open_specialists)
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
    if "planetary_shield" in planet.buildings or "missile_base" in planet.buildings:
        panel(surface, (770, 321, 628, 45), (10, 23, 30))
        cap = str(defenses.shield_capacity(game, planet)) if live else "?"
        shield = f"SHIELD {planet.shield_points}/{cap}" if "planetary_shield" in planet.buildings else "NO SHIELD"
        battery = f"MISSILE BASE {planet.battery_hull or defenses.BASE_HULL}/{defenses.BASE_HULL}" if "missile_base" in planet.buildings else "NO BASE"
        if live and "planetary_shield" in planet.buildings and not game.building_operational(planet, "planetary_shield"):
            shield += " OFFLINE"
        if live and "missile_base" in planet.buildings and not game.building_operational(planet, "missile_base"):
            battery += " OFFLINE"
        text(surface, shield+" · "+battery, (784, 327), 12, CYAN)
        text(surface, f"Peaceful recovery: +{defenses.SHIELD_RECOVERY} shield, +{defenses.BASE_RECOVERY} base hull/turn" if live else "Defense status at last survey", (784, 348), 11, MUTED)
    if planet.colonized:
        defence = forces(planet, game.bonuses_for(planet.owner) if live else {})
        caption = (f"{len(planet.buildings)} buildings · {len(planet.building_projects)} reserved / {planet.building_capacity} slots"
                   f"    GROUND: {defence.garrison} garrison + {defence.militia} militia · +{defence.defence_bonus}% firepower")
        if not live:
            caption += " · Last observed"
        elif training_limit(planet, game.bonuses_for(planet.owner) if live else {}):
            caption += f" · Barracks +1/turn, limit {training_limit(planet, game.bonuses_for(planet.owner) if live else {})}"
        text(surface, shorten(caption, 1162, 12), (24, 854), 12, CYAN)
    else:
        text(surface, f"{planet.building_capacity} building slots · {planet.habitability}% habitability · {planet.orbit_au:.2f} AU", (24, 854), 12, MUTED)
    text(surface, "Click buildings to inspect · E: End turn · R: Research · I: Empire · P: Menu · F5: Save", (24, 877), 11, MUTED)
    app.button("planet_return", "Galaxy map" if app.planet_return=="galaxy" else "System view",
               (1210, 851, 206, 42), app.close_planet, "primary")


def production_catalog(app, identifiers, *, x, width, page_field, key, title):
    """An independently paged column, keeping buildings and ships in fixed places."""
    game, surface = app.game, app.canvas
    planet = game.planet_at(game.selected_system, game.selected_planet)
    identifiers = [item for item in identifiers
                   if game.project_error(game.selected_system, game.selected_planet, item) is None]
    pages = max(1, math.ceil(len(identifiers)/5))
    page = max(0, min(getattr(app, page_field), pages-1))
    setattr(app, page_field, page)
    text(surface, title, (x, 119), 12, GOLD, "mono", 1)
    if not identifiers:
        panel(surface, (x, 146, width, 631))
        paragraph(surface, "No available "+title.lower()+". Research more options, or free a place in the queue.",
                  (x+20, 180), width-40, 17, MUTED, 27)
    for i, item_id in enumerate(identifiers[page*5:page*5+5]):
        spec = game.project_spec(item_id)
        design = game.design_for(item_id)
        y = 146+i*128
        panel(surface, (x, y, width, 119))
        project_art(surface, item_id, (x+10, y+14, 65, 72), design)
        text(surface, shorten(spec.name, width-100, 18), (x+85, y+12), 18, INK)
        price = game.project_price(item_id)
        upkeep = building_maintenance(item_id, game.bonuses_for()) if item_id in BUILDINGS else getattr(spec, "maintenance", 0)
        cost = f"{price} RES · {spec.work_cost} work"+(f" · {upkeep} CR/turn" if upkeep else "")
        text(surface, shorten(cost, width-100, 10), (x+85, y+42), 10, GOLD)
        if item_id in BUILDINGS:
            text(surface, shorten(compact_yields(game, spec, planet), width-100, 10), (x+85, y+62), 10, CYAN)
            details = [spec.workforce_text(planet.richness)]
            if spec.energy_use:
                details.append(f"Uses {spec.energy_use} energy")
            text(surface, shorten(" · ".join(part for part in details if part), width-100, 10), (x+85, y+78), 10, CYAN)
        else:
            detail = (f"{design.hull} hull · {design.damage} volley · {design.shields} shields" if design
                      else f"{spec.hull} hull · {game.beam_for(item_id).damage} attack" if item_id in SHIP_TYPES
                      else "Unlock a scientific victory")
            if getattr(spec, "drone_bays", 0):
                detail = f"{spec.hull} hull · {spec.drone_bays*2} active drones · {spec.drone_bays*4} launches"
            if item_id == "outpost_ship":
                detail = "Establish a planetary refuelling outpost · Unarmed"
            elif item_id == "colony_ship":
                detail = f"Found a colony with {game.starting_colonists()} B population · Unarmed"
            text(surface, shorten(detail, width-100, 11), (x+85, y+64), 11, CYAN)
        app.button("production_build_"+item_id, "Queue", (x+width-116, y+85, 100, 26),
                   lambda chosen=item_id: app.choose_production(chosen))
        text(surface, shorten("Resources reserved when work starts", width-139, 10), (x+13, y+94), 10, MUTED)
    app.button(key+"_previous", "←", (x, 793, 64, 30),
               lambda: setattr(app, page_field, page-1), enabled=page > 0)
    text(surface, f"Page {page+1} / {pages}", (x+width//2-33, 801), 12, MUTED)
    app.button(key+"_next", "→", (x+width-64, 793, 64, 30),
               lambda: setattr(app, page_field, page+1), enabled=page < pages-1)


def draw_production(app):
    game, surface = app.game, app.canvas
    sid, pid = game.selected_system, game.selected_planet
    planet = game.planet_at(sid, pid)
    text(surface, shorten(f"{planet.name} · Choose production", 604, 35, "title"), (40, 28), 35, INK, "title")
    empire_stockpile(app, (676, 28, 724, 38))
    text(surface, "Available projects only · One of each building per planet · Click a queued project to build it first.", (40, 83), 15, MUTED)
    buildings = list(BUILDINGS)
    if "ascension_theory" in game.technology.completed:
        buildings.append(ASCENSION_GATE.id)
    production_catalog(app, buildings, x=40, width=428, page_field="catalog_page", key="catalog", title="BUILDINGS")
    production_catalog(app, [*SHIP_TYPES, *(d.id for d in game.designs)], x=944, width=456,
                       page_field="ship_catalog_page", key="ship_catalog", title="SHIPS")
    app.button("production_designer", "Ship designer →", (1170, 108, 230, 30), app.open_designer)
    panel(surface, (486, 146, 428, 631))
    queue = planet.construction_queue
    text(surface, f"CONSTRUCTION QUEUE · {len(queue)}/20", (502, 164), 12, GOLD, "mono")
    from .economy import local_bonuses
    modifiers = local_bonuses(planet, game.bonuses_for(planet.owner))
    if not planet.trade_goods:
        multiplier = modifiers.get("ship_work_multiplier", 1)
        contribution = modifiers.get("megastructure_work", 0)
        caption = f"Stellar Forge: {multiplier}× ship work" if multiplier > 1 else f"{contribution} industry / turn to megastructure" if contribution else ""
        if caption:
            text(surface, caption, (502, 187), 11, CYAN)
    if planet.trade_goods and queue:
        text(surface, "TRADE GOODS ACTIVE · Click a project to resume", (502, 187), 10, CYAN)
    pages = max(1, math.ceil(len(queue)/6))
    app.production_page = min(app.production_page, pages-1)
    estimates = game.queue_estimates(planet)
    for i in range(app.production_page*6, min(len(queue), (app.production_page+1)*6)):
        project = queue[i]
        spec = project.spec
        y = 213+(i%6)*76
        button = app.button(f"production_priority_{i}", "", (502, y, 330, 67),
                            lambda index=i: app.prioritize_production(index), "hotspot")
        panel(surface, button.rect, (18, 32, 41), GOLD if app.is_active(button) else LINE)
        text(surface, shorten(f"{i+1}. {spec.name}", 304, 15), (515, y+8), 15, INK)
        eta = "Paused" if planet.trade_goods else turn_label(estimates[i])
        text(surface, f"{project.progress}/{spec.work_cost} work · {eta}", (515, y+30), 11, CYAN)
        status = "Click to resume construction" if planet.trade_goods else game.construction_status(planet) if i == 0 else "Click to make current"
        text(surface, shorten(status, 304, 10), (515, y+49), 10, MUTED)
        app.button(f"production_cancel_{i}", "×", (842, y, 56, 32), lambda index=i: app.cancel_construction(index))
        text(surface, shorten(project.refund_text, 64, 9), (898, y+47), 9, MUTED, right=True)
    if not queue:
        message = (f"Trade Goods · +{game.trade_goods_income(planet)} CR each turn. Add a project to resume construction."
                   if planet.trade_goods else "Nothing queued. Add buildings on the left or ships on the right. Leaving an empty queue selects Trade Goods automatically.")
        paragraph(surface, message, (510, 224), 380, 18, MUTED, 30)
    app.button("production_previous", "←", (502, 701, 64, 30), lambda: app.change_production_page(-1), enabled=app.production_page > 0)
    app.button("production_next", "→", (834, 701, 64, 30), lambda: app.change_production_page(1), enabled=app.production_page < pages-1)
    text(surface, f"Page {app.production_page+1} / {pages}", (667, 709), 12, MUTED)
    text(surface, "× refunds unused construction payments.", (502, 748), 11, MUTED)
    panel(surface, (40, 836, 876, 54))
    rate = game.trade_goods_income(planet)
    text(surface, f"Trade Goods · +{rate} CR / turn", (56, 844), 17, GOLD)
    text(surface, f"{production_balance.TRADE_GOODS_PERCENT}% of industry, then local credit strain · Rounded down · Queued projects keep their progress", (56, 871), 11, MUTED)
    app.button("production_build_trade_goods", "Active" if planet.trade_goods else "Trade Goods", (718, 844, 182, 38),
               lambda: app.choose_production(TRADE_GOODS.id), enabled=not planet.trade_goods and game.project_error(sid, pid, TRADE_GOODS.id) is None)
    app.button("production_return", "Return to colony", (1122, 833, 278, 48), lambda: app.go("planet"), "primary")
