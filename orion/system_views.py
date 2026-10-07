"""Solar-system and planet screens. UI-only; persistent planet data lives in model.py."""

import pygame as pg

from .planet_art import draw_planet, draw_star
from .colony_view import draw_planet_tabs
from .colony_scene import draw_colony_scene, is_headquarters
from .model import PLAYER, RIVAL
from .ui import CYAN, FAINT, GOLD, INK, LINE, MUTED, RIVAL_COLOR, panel, paragraph, shorten, text

STAR_COLORS = {"Yellow dwarf": (230, 207, 141), "Blue star": (113, 181, 231),
               "Red dwarf": (221, 124, 108), "White star": (217, 228, 239), "Orange dwarf": (235, 170, 106)}
BIOME_NOTES = {
    "Terran": "Temperate land, open water and a breathable atmosphere make this world a natural home for your civilization.",
    "Ocean": "Deep oceans cover most of the surface. Settlements must make room for a world shaped by water.",
    "Desert": "Dry continents and exposed mineral deposits dominate the surface. Water would be the central challenge for settlement.",
    "Tundra": "Long winters and frozen ground leave only a narrow habitable region. Colonies need protection from the cold.",
    "Barren": "A cratered, lifeless surface offers little natural support for a colony. Habitats would need a controlled environment.",
    "Volcanic": "Intense geological activity reshapes the surface. Heat and hostile conditions would make settlement demanding.",
}
DIAMETERS = {"Tiny": 29, "Small": 39, "Medium": 49, "Large": 59, "Huge": 69}


def visual_seed(game, system, planet):
    return f"{game.seed}:{system.id}:{planet.id}"


def system_layout(worlds):
    """Fixed diagram positions keep click targets still and support zero to eight worlds."""
    layout = []
    count = len(worlds)
    for i, world in enumerate(worlds):
        x = 374 + (i+1)*895/(count+1)
        y = 405 + (40 if i%2 == 0 else -35)
        factor = 1.7 if count <= 4 else 1.35 if count <= 6 else 1.0
        diameter = round(DIAMETERS[world.size]*factor)
        # Include the planet's caption in its accessible hit target.
        width = 116 if count <= 6 else 88
        hit = pg.Rect(int(x-width/2), int(y-diameter/2-18), width, int(diameter+105))
        layout.append((world, (x, y), diameter, hit))
    return layout


def draw_system(app):
    surface = app.canvas
    game = app.game
    system = game.systems[game.selected_system]
    app.chrome("SYSTEM OVERVIEW")
    app.button("system_back", "←  Galaxy map", (64, 124, 205, 48), lambda: app.go("galaxy"), "ghost")
    text(surface, f"GALAXY  /  {system.name.upper()}", (300, 143), 11, MUTED, "mono", 1)
    text(surface, f"YEAR {game.year}   ·   {game.credits:,} CR   ·   {game.research:,} RP", (1376, 140), 13, GOLD, "mono", right=True)

    text(surface, shorten(system.name, 860, 52, "title"), (64, 191), 52, INK, "title")
    text(surface, f"{system.kind}   /   {len(system.worlds)} planets", (67, 260), 16, MUTED)
    ships, rivals = len(game.fleet_at(system.id)), len(game.fleet_at(system.id, RIVAL))
    label = f"ORBIT: {ships} YOUR SHIPS · {rivals} RIVAL SHIPS" if ships or rivals else "YOUR HOME SYSTEM" if system.id == 0 else "SYSTEM SURVEY"
    text(surface, label, (1376, 211), 11, CYAN, "mono", 1, right=True)
    if ships and rivals:
        reason = game.engagement_error(system.id)
        app.button("system_engage", "Engage opposing fleet", (1100, 247, 276, 43),
                   lambda: app.engage_request(system.id), enabled=reason is None)
        if reason:
            text(surface, "Frigate required to engage", (1080, 262), 11, MUTED, right=True)

    panel(surface, (64, 308, 1312, 311), (6, 16, 24))
    text(surface, "ORBITAL OVERVIEW", (88, 329), 10, GOLD, "mono", 2)
    text(surface, "SCHEMATIC · NOT TO SCALE", (1352, 329), 10, FAINT, "mono", right=True)
    if system.worlds:
        pg.draw.line(surface, LINE, (287, 420), (1325, 420), 1)
    draw_star(surface, (224, 434), 45, STAR_COLORS[system.kind])
    text(surface, system.name.upper(), (191, 528), 13, GOLD, "mono", 1)
    text(surface, "PRIMARY STAR", (171, 555), 10, FAINT, "mono", 1)

    layout = system_layout(system.worlds)
    for world, center, diameter, hit in layout:
        x, y = center
        # An arc segment evokes an orbital track without using misleading distance scaling.
        radius = x-224
        old_clip = surface.get_clip()
        surface.set_clip((331, 363, 1017, 231))
        pg.draw.ellipse(surface, (20, 39, 49), (224-radius, 434-radius*.45, radius*2, radius*.9), 1)
        surface.set_clip(old_clip)
    for world, center, diameter, hit in layout:
        x, y = center
        button = app.button(f"world_{world.id}", "", hit, lambda p=world.id: app.open_planet(p), "hotspot")
        active = app.is_active(button) or world.id == game.selected_planet
        draw_planet(surface, world, center, diameter, visual_seed(game, system, world), selected=active)
        label_size = 13 if len(system.worlds) <= 5 else 11
        text(surface, shorten(world.name, hit.w-4, label_size), (hit.x+2, y+diameter/2+22), label_size,
             GOLD if active else INK)
        text(surface, world.biome.upper(), (hit.x+2, y+diameter/2+45), 9, MUTED, "mono")
        if world.colonized:
            pg.draw.circle(surface, CYAN if world.owner == PLAYER else RIVAL_COLOR,
                           (int(x+diameter/2+9), int(y-diameter/2-2)), 3)

    if not system.worlds:
        text(surface, "No planets detected.", (479, 408), 29, INK, "title")
        paragraph(surface, "This system contains only its central star. Return to the galaxy map to survey another system.",
                  (480, 458), 619, 16, MUTED, 27)

    colonies = sum(p.colonized for p in system.worlds)
    habitable = sum(p.habitability >= 35 for p in system.worlds)
    population = sum(p.population for p in system.worlds)
    summaries = [("WORLDS", str(len(system.worlds)), "Surveyed planets"),
                 ("HABITABLE", str(habitable), "At least 35% suitability"),
                 ("COLONIES", str(colonies), "Established settlements"),
                 ("POPULATION", f"{population} B", "Current inhabitants")]
    for i, (label, value, caption) in enumerate(summaries):
        x = 64+i*334
        panel(surface, (x, 645, 310, 122))
        text(surface, label, (x+21, 663), 10, MUTED, "mono", 1)
        text(surface, value, (x+20, 688), 29, CYAN if i==2 else INK)
        text(surface, caption, (x+21, 735), 11, MUTED)
    hint = "Click a planet to survey it. Cyan: your colony · Orange: rival colony" if system.worlds else "Use Previous / Next to survey another system."
    text(surface, hint, (65, 792), 14, MUTED)
    app.button("system_pause", "Menu", (64, 832, 127, 46), app.pause)
    app.button("system_save", "Save game · F5", (206, 832, 222, 46), app.save_game)
    app.button("system_previous", "← Previous system", (846, 832, 249, 46), lambda: app.cycle_system(-1))
    app.button("system_next", "Next system →", (1109, 832, 267, 46), lambda: app.cycle_system(1))


def draw_planet_overview(app):
    surface = app.canvas
    game = app.game
    system = game.systems[game.selected_system]
    planet = system.worlds[game.selected_planet]
    app.chrome("PLANET OVERVIEW")
    app.button("planet_back", f"←  {shorten(system.name, 138, 15)} system", (64, 124, 270, 48), lambda: app.go("system"), "ghost")
    text(surface, shorten(f"GALAXY  /  {system.name.upper()}  /  {planet.name.upper()}", 760, 11, "mono"),
         (363, 143), 11, MUTED, "mono")
    app.button("planet_galaxy", "Galaxy map", (1214, 124, 162, 46), lambda: app.go("galaxy"))
    text(surface, shorten(planet.name, 620, 48, "title"), (64, 193), 48, INK, "title")
    text(surface, f"{planet.biome} world   /   {system.name} system   /   Orbit {planet.id+1:02}",
         (66, 258), 15, MUTED)
    draw_planet_tabs(app, "planet")
    draw_planet(surface, planet, (756, 222), 60, visual_seed(game, system, planet))

    draw_colony_scene(app, (64, 308, 928, 473), game, system, planet)

    panel(surface, (1016, 308, 360, 227))
    text(surface, "WORLD CHARACTERISTICS", (1036, 326), 10, GOLD, "mono", 1)
    entries = [("ENVIRONMENT", planet.biome), ("SIZE", planet.size), ("GRAVITY", planet.gravity),
               ("MINERALS", planet.richness), ("HABITABILITY", f"{planet.habitability}%"), ("ORBIT", f"{planet.orbit_au:.2f} AU")]
    for i, (label, value) in enumerate(entries):
        x = 1037+(i%2)*170
        y = 363+(i//2)*54
        text(surface, label, (x, y), 9, MUTED, "mono", 1)
        text(surface, value, (x, y+20), 19, CYAN if label=="HABITABILITY" else INK)

    panel(surface, (1016, 554, 360, 227))
    text(surface, "COLONY STATUS", (1036, 575), 10, GOLD, "mono", 2)
    status = "No colony established"
    if planet.colonized:
        status = "Headquarters" if is_headquarters(game, system.id, planet) else "Established colony"
        if planet.owner == RIVAL:
            status = "Rival headquarters" if is_headquarters(game, system.id, planet) else "Rival colony · survey only"
    text(surface, status, (1036, 602), 21, INK)
    if planet.colonized:
        text(surface, shorten(game.empire_name_for(planet.owner), 318, 13), (1037, 639), 13,
             CYAN if planet.owner == PLAYER else RIVAL_COLOR)
        text(surface, f"{planet.population} B inhabitants · {game.planet_yields(planet)[0]} IND / turn", (1037, 665), 12, INK)
        paragraph(surface, BIOME_NOTES[planet.biome], (1037, 696), 318, 12, MUTED, 18)
    else:
        reason = game.colonize_error(system.id, planet.id)
        app.button("colonize_planet", "Colonize", (1037, 637, 318, 40), app.colonize_request, enabled=reason is None)
        caption = reason or f"{game.colony_ships_at(system.id)[0].name} ready · {game.starting_colonists()} B starting colonists"
        paragraph(surface, caption, (1037, 690), 318, 13, MUTED if reason else CYAN, 21)

    hint = "Click buildings to manage them. E: end turn." if planet.colonized else "A colony ship is consumed when this world is settled."
    if planet.owner == RIVAL:
        hint = "Inspect the rival's buildings and production in the Colony and Shipyard tabs."
    text(surface, f"{planet.size} worlds have {planet.building_capacity} building slots. {hint}",
         (65, 795), 13, MUTED)
    app.button("planet_pause", "Menu", (64, 832, 127, 46), app.pause)
    app.button("planet_save", "Save game · F5", (206, 832, 222, 46), app.save_game)
    text(surface, f"PLANET {planet.id+1} OF {len(system.worlds)}", (593, 848), 10, FAINT, "mono", 1)
    app.button("planet_previous", "← Previous planet", (846, 832, 249, 46), lambda: app.cycle_planet(-1),
               enabled=len(system.worlds)>1)
    app.button("planet_next", "Next planet →", (1109, 832, 267, 46), lambda: app.cycle_planet(1),
               enabled=len(system.worlds)>1)
