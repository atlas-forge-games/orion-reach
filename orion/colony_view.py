"""Colony management: building capacity, projects, costs and visible turn yields."""

import pygame as pg

from .buildings import BUILDINGS, BUILDING_GROUPS, MINERAL_FACTORS
from . import economy
from .building_art import draw_building_art
from .habitat_modules import display_name
from .model import PLAYER
from .research import TECHNOLOGIES, building_maintenance
from .planet_art import draw_planet
from .ui import CYAN, FAINT, GOLD, INK, LINE, MUTED, PANEL, RED, panel, shorten, text


def draw_planet_tabs(app, active):
    for key, label, x, screen in (("tab_overview", "Overview", 818, "planet"),
                                   ("tab_colony", "Modules" if app.selected_habitat() else "Colony", 1008, "colony"),
                                   ("tab_shipyard", "Shipyard", 1198, "shipyard")):
        app.button(key, label, (x, 201, 178, 49), lambda s=screen: app.go(s),
                   enabled=screen=="planet" or bool(app.selected_habitat()) or app.game.system_visible(app.game.selected_system))
        if screen == active:
            pg.draw.line(app.canvas, GOLD, (x, 250), (x+178, 250), 3)


def compact_yields(game, definition, planet):
    benefits = game.bonuses_for(planet.owner)
    if definition.id == "planetary_shield":
        return f"{max(100, benefits.get('shield_capacity', 0))} shield points · +25/peaceful turn"
    if definition.id == "interdictor":
        return f"{max(25, benefits.get('interdiction_slow', 0))}% hostile slowdown within {max(5, benefits.get('interdiction_range', 0))} ly"
    if definition.energy_per_resource:
        return f"0–{definition.energy_output} ENERGY · 1 RES/{definition.energy_per_resource} energy · backup only"
    if definition.special_effect:
        return definition.special_effect
    if definition.training:
        return f"+{definition.training} TROOP · CAP {definition.garrison_limit}"
    if definition.defence_bonus:
        return f"+{definition.defence_bonus+game.bonuses_for(planet.owner).get('fortification_bonus', 0)}% DEFENCE"
    values = game.building_yields(definition, planet)
    parts = [f"+{v} {unit}" for v, unit in zip(values, ("IND", "CR", "RP")) if v]
    if definition.food:
        parts.append(f"+{definition.food} FOOD")
    if definition.resources:
        amount = int(definition.resources*MINERAL_FACTORS[planet.richness])+benefits.get("mine_resources", 0)
        parts.append(f"+{amount} RES")
    if definition.energy_output:
        parts.append(f"+{definition.energy_output} ENERGY")
    for value, label in ((definition.growth_bonus, '% growth'), (definition.capacity_bonus, '% capacity'),
                         (definition.adaptation, '% environment penalty removed'), (definition.strain_relief, ' points strain relief')):
        if value:
            parts.append(f'+{value}{label}')
    if definition.shield_capacity:
        parts.append(f'{definition.shield_capacity} shield points')
    if definition.interdiction_slow:
        parts.append(f'{definition.interdiction_slow}% hostile slowdown within {definition.interdiction_range} ly')
    return " · ".join(parts)


def building_effect(game, definition, planet):
    if definition.training:
        return f"+{definition.training} troop / turn · limit {definition.garrison_limit}"
    effect = compact_yields(game, definition, planet)
    bonus = definition.workforce_text(planet.richness)
    return effect+(" · "+bonus if bonus else "")


def turn_label(count):
    return "Supply needed" if count is None else f"{count} {'turn' if count == 1 else 'turns'}"


def draw_colony(app):
    surface, game = app.canvas, app.game
    system = game.systems[game.selected_system]
    planet = game.planet_at(system.id, game.selected_planet)
    app.chrome("MODULE MANAGEMENT" if planet.habitat else "COLONY MANAGEMENT")
    app.button("colony_back", "←  Mothership overview" if planet.habitat else "←  Planet overview", (64, 124, 246, 47), lambda: app.go("planet"), "ghost")
    text(surface, shorten(f"{system.name.upper()}  /  {planet.name.upper()}", 580, 11, "mono"),
         (347, 143), 11, MUTED, "mono", 1)
    text(surface, f"YEAR {game.year} · TURN {game.turn} · {game.credits:,} CR", (1376, 141), 12, GOLD, "mono", right=True)

    text(surface, shorten(planet.name, 620, 43, "title"), (64, 185), 43, INK, "title")
    status = f"{planet.workforce} B · {game.empire_name_for(planet.owner)}" if planet.colonized else "Uncolonized"
    text(surface, f"Mobile habitat · 50 B capacity · {status}" if planet.habitat else f"{planet.biome}  ·  {planet.size} world  ·  {status}", (66, 249), 14, MUTED)
    if planet.habitat:
        from .mothership_art import draw
        draw(surface, (756, 222), .9, app.empire_color(planet.owner))
    else:
        draw_planet(surface, planet, (756, 222), 60, f"{game.seed}:{system.id}:{planet.id}")
    draw_planet_tabs(app, "colony")

    industry, income, science = game.planet_yields(planet)
    food = game.population_report(planet)
    text(surface, f"Environment: {food.environment_percent}% growth efficiency", (818, 266), 12, MUTED)
    food_color = RED if food.balance < 0 else GOLD if food.balance == 0 else CYAN
    stats = [("INDUSTRY / TURN", f"{industry} IND", "Construction aboard this home" if planet.habitat else "Construction on this world", CYAN),
             ("NET INCOME / TURN", f"{income:+} CR", f"{income+game.planet_maintenance(planet)} gross − {game.planet_maintenance(planet)} upkeep", RED if income < 0 else INK),
             ("RESEARCH / TURN", f"+{science} RP", "Empire research project", CYAN),
             ("FOOD / CONSUMED", f"{food.produced} / {food.consumed}", f"{food.balance:+} food / turn · local", food_color),
             ("NATIVE / SLAVES" if planet.slaves else "POPULATION / LIMIT",
              f"{planet.population} / {planet.slaves if planet.slaves else food.capacity} B", food.growth_caption, CYAN)]
    for i, (label, value, caption, color) in enumerate(stats):
        x = 64+i*267
        panel(surface, (x, 287, 244, 84))
        text(surface, label, (x+17, 300), 9, MUTED, "mono", 1)
        text(surface, value, (x+17, 319), 22, color)
        text(surface, caption, (x+17, 349), 10, MUTED)

    text(surface, "MODULE BAYS" if planet.habitat else "BUILDING SLOTS", (64, 385), 11, GOLD, "mono", 2)
    building_projects = planet.building_projects
    text(surface, f"{len(planet.buildings)} built + {len(building_projects)} reserved / {planet.building_capacity}",
         (727, 385), 11, MUTED, "mono", right=True)
    for page_index, key, label in ((0, "colony_economy", "Economy"),
                                    (1, "colony_infrastructure", "Infrastructure"),
                                    (2, "colony_power", "Power"),
                                    (3, "colony_advanced", "Advanced")):
        app.button(key, label, (751+page_index*158, 378, 151, 26),
                   lambda i=page_index: (setattr(app, "colony_build_page", i), setattr(app, 'colony_catalog_page', 0)),
                   "primary" if app.colony_build_page == page_index else "normal")
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
            draw_building_art(surface, building_id, (x+6, y+5, 44, 34), habitat=planet.habitat)
            status = economy.building_status(planet, index, game.bonuses_for(planet.owner))
            text(surface, status, (x+52, y+20), 8, MUTED if status == "STANDBY" else RED if status in ("NO FUEL", "NO POWER", "DISABLED") else CYAN, "mono")
            text(surface, shorten(display_name(definition, planet.habitat), 134, 13), (x+12, y+42), 13, INK)
            text(surface, shorten(compact_yields(game, definition, planet), 136, 9), (x+12, y+63), 9, MUTED)
        elif index < planet.used_slots:
            queue_index, project = building_projects[index-len(planet.buildings)]
            definition = BUILDINGS[project.item_id]
            draw_building_art(surface, project.item_id, (x+6, y+5, 44, 34), alpha=130, habitat=planet.habitat)
            label = "PAUSED" if planet.trade_goods else "BUILDING" if queue_index==0 else f"QUEUED {queue_index+1}"
            text(surface, label, (x+52, y+11), 8, GOLD, "mono")
            text(surface, "Trade Goods active" if planet.trade_goods else turn_label(estimates[queue_index]), (x+52, y+27), 10, MUTED)
            text(surface, shorten(display_name(definition, planet.habitat), 134, 13), (x+12, y+46), 13, INK)
            pg.draw.rect(surface, LINE, (x+12, y+72, 134, 3))
            pg.draw.rect(surface, GOLD, (x+12, y+72, int(134*project.progress/definition.work_cost), 3))
        else:
            pg.draw.line(surface, FAINT, (x+19, y+25), (x+35, y+25))
            pg.draw.line(surface, FAINT, (x+27, y+17), (x+27, y+33))
            text(surface, "Available" if planet.colonized else "Undeveloped", (x+12, y+46), 13, MUTED)
            text(surface, "Choose a module" if planet.habitat else "Choose a building" if planet.colonized else "Colony required", (x+12, y+65), 10, FAINT)
        app.button(f"colony_slot_{index}", "", rect, lambda i=index: app.select_colony_slot(i), "hotspot")

    page = [BUILDINGS[b] for b in BUILDING_GROUPS[app.colony_build_page]
            if game.build_error(system.id, planet.id, b) is None]
    per_page = 5 if app.colony_build_page == 2 else 6
    pages = max(1, (len(page)+per_page-1)//per_page)
    app.colony_catalog_page = min(app.colony_catalog_page, pages-1)
    page = page[app.colony_catalog_page*per_page:(app.colony_catalog_page+1)*per_page]
    if not page:
        text(surface, "No available modules in this category." if planet.habitat else "No available buildings in this category.", (769, 427), 15, MUTED)
    for i, definition in enumerate(page):
        x, y = 751, 410+i*57
        panel(surface, (x, y, 625, 53))
        draw_building_art(surface, definition.id, (x+7, y+4, 54, 45), habitat=planet.habitat)
        text(surface, display_name(definition, planet.habitat), (x+70, y+3), 15, INK)
        text(surface, shorten(building_effect(game, definition, planet), 410, 10), (x+70, y+23), 10, CYAN)
        estimate = game.queue_estimates(planet, additional=definition.id)
        eta = turn_label(estimate[-1]) if estimate else "Requires colony"
        price = game.project_price(definition.id, planet.owner or PLAYER)
        upkeep = building_maintenance(definition.id, game.bonuses_for(planet.owner))
        cost_line = f"{price} RES · {definition.work_cost} work · {eta} · {upkeep} CR + {definition.energy_use} energy/turn"
        if definition.energy_output:
            unlock = TECHNOLOGIES[definition.technology].name if definition.technology else "Basic technology"
            cost_line = f"{price} RES · {definition.work_cost} work · {upkeep} CR/turn · {unlock}"
        text(surface, shorten(cost_line, 410, 10), (x+70, y+38), 10, MUTED)
        reason = game.build_error(system.id, planet.id, definition.id)
        label, hint = ("Queue", "Await resources") if game.resources < price else ("Build", "1 per home" if planet.habitat else "1 per colony")
        app.button(f"build_{definition.id}", label, (x+492, y+3, 117, 28),
                   lambda b=definition.id: app.queue_building(b), enabled=reason is None)
        text(surface, hint, (x+510, y+36), 9, FAINT, "mono")

    if pages > 1:
        page_y = 699 if app.colony_build_page == 2 else 767
        app.button('colony_catalog_previous', '←', (751, page_y, 48, 28),
                   lambda: setattr(app, 'colony_catalog_page', app.colony_catalog_page-1), enabled=app.colony_catalog_page > 0)
        text(surface, f'{app.colony_catalog_page+1} / {pages}', (814, page_y+8), 11, MUTED)
        app.button('colony_catalog_next', '→', (892, page_y, 48, 28),
                   lambda: setattr(app, 'colony_catalog_page', app.colony_catalog_page+1), enabled=app.colony_catalog_page < pages-1)

    if app.colony_build_page == 2:
        power = game.planet_energy(planet)
        panel(surface, (951, 705, 425, 101))
        text(surface, "LOCAL POWER DISPATCH", (967, 718), 10, GOLD, "mono", 1)
        text(surface, f"{power.base_generated} steady + {power.backup_generated} backup / {power.demand} demand", (967, 738), 14, INK)
        text(surface, f"Backup fuel: {power.fuel_used} RES/turn · {game.resources_for(planet.owner):,} stored", (967, 763), 11, CYAN)
        text(surface, "Steady sources first; backup burns fuel only when needed.", (967, 785), 10, MUTED)

    # Inspect an existing building or queued project, with reversible queue cancellation.
    panel(surface, (64, 711, 662, 82))
    slot = app.colony_slot
    if slot is not None and 0 <= slot < len(planet.buildings):
        definition = BUILDINGS[planet.buildings[slot]]
        text(surface, display_name(definition, planet.habitat), (82, 724), 18, INK)
        detail = building_effect(game, definition, planet)
        if definition.energy_output:
            output, fuel = next(((output, fuel) for i, output, fuel in game.planet_energy(planet).plants if i == slot), (0, 0))
            detail = f"{output} energy now / {definition.energy_output} capacity · {fuel} RES fuel/turn"
        text(surface, shorten(detail, 451, 11), (82, 750), 11, CYAN)
        text(surface, f"Upkeep {building_maintenance(definition.id, game.bonuses_for(planet.owner))} CR/turn · Power {definition.energy_use} · {economy.building_status(planet, slot, game.bonuses_for(planet.owner)).lower()}", (82, 774), 10, MUTED)
        app.button("toggle_building", "Enable" if slot in planet.disabled_buildings else "Disable", (549, 719, 156, 31),
                   lambda i=slot: app.toggle_building(i), enabled=planet.owner == PLAYER)
        app.button("demolish_building", "Dismantle" if planet.habitat else "Demolish", (549, 755, 156, 31),
                   lambda i=slot: app.demolish_request(i), enabled=planet.owner == PLAYER)
        if definition.id == "space_hub" and planet.owner == PLAYER and not game.is_observer:
            app.button("colony_space_hub", "Visit Space Hub →", (64, 797, 244, 26), app.open_specialists)
    elif slot is not None and len(planet.buildings) <= slot < planet.used_slots:
        index, project = building_projects[slot-len(planet.buildings)]
        definition = BUILDINGS[project.item_id]
        text(surface, display_name(definition, planet.habitat), (82, 724), 18, INK)
        text(surface, f"{project.progress}/{definition.work_cost} work · Ready in {turn_label(estimates[index])}",
             (82, 754), 12, GOLD)
        app.button("cancel_construction", "Cancel", (549, 718, 156, 43),
                   lambda i=index: app.cancel_construction(i), enabled=planet.owner == PLAYER)
        text(surface, f"Refund: {project.refund_text}", (553, 772), 10, MUTED)
    else:
        title = f"This mothership has {planet.building_capacity} module bays." if planet.habitat else f"{planet.size} worlds support {planet.building_capacity} buildings."
        message = "Modules reserve bays. The Shipyard tab shows the full production queue." if planet.habitat else "Buildings reserve slots. The Shipyard tab shows the full production queue."
        if not planet.colonized:
            title = "This planet needs a colony first."
            message = "Bring a colony ship here, then settle this world from its Overview tab."
        elif planet.owner != PLAYER:
            title = "Rival mothership · inspect only" if planet.habitat else "Rival colony · survey only"
            message = f"{game.empire_name_for(planet.owner)} chooses construction here."
        text(surface, title, (82, 725), 17, INK)
        text(surface, message, (82, 756), 12, MUTED)

    app.button("colony_pause", "Menu", (64, 828, 126, 51), app.pause)
    app.button("colony_save", "Save · F5", (204, 828, 172, 51), app.save_game)
    text(surface, f"Resources: {game.resources:,} · {game.planet_resources(planet):+}/turn here, after {game.planet_energy(planet).fuel_used} RES fuel.", (399, 828), 11, MUTED)
    power = game.planet_energy(planet)
    priority = "Farming and extraction modules have priority." if planet.habitat else "Farms and mines have priority."
    power_text = f"Power: ∞ / {power.demand} needed. Empire-wide Dyson grid; no fuel consumed." if power.unlimited else f"Power: {power.generated}/{power.demand} needed. {priority}"
    text(surface, power_text, (399, 850), 11, FAINT)
    app.button("colony_end_turn", "End turn · E", (1081, 816, 295, 63), app.advance_turn, "primary")
