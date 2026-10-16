"""Solar-system and planet screens. UI-only; persistent planet data lives in model.py."""

import pygame as pg

from .planet_art import draw_planet, draw_star
from .model import PLAYER, RIVAL
from . import monsters, defenses, motherships, encounters
from .fleet_art import ship_icon
from .exploration_view import draw_unsurveyed_system
from .hyperlane_view import draw_system_portal
from .ui import CYAN, FAINT, GOLD, INK, LINE, MUTED, RED, RIVAL_COLOR, panel, paragraph, shorten, text

STAR_COLORS = {"Yellow dwarf": (230, 207, 141), "Blue star": (113, 181, 231),
               "Red dwarf": (221, 124, 108), "White star": (217, 228, 239), "Orange dwarf": (235, 170, 106)}
DIAMETERS = {"Tiny": 29, "Small": 39, "Medium": 49, "Large": 59, "Huge": 69}
MOTHERSHIPS_PER_PAGE = 4


def visual_seed(game, system, planet):
    return f"{game.seed}:{system.id}:{planet.id}"


def system_layout(worlds, *, with_motherships=False):
    """Fixed diagram positions keep click targets still and support zero to eight worlds."""
    layout = []
    count = len(worlds)
    for i, world in enumerate(worlds):
        x = 374 + (i+1)*895/(count+1)
        y = 405 + (40 if i%2 == 0 else -35)
        factor = 1.7 if count <= 4 else 1.35 if count <= 6 else 1.0
        if with_motherships:
            y = 391 + (24 if i%2 == 0 else -26)
            factor = min(factor, 1.15)
        diameter = round(DIAMETERS[world.size]*factor)
        # Include the planet's caption in its accessible hit target.
        width = 116 if count <= 6 else 88
        hit = pg.Rect(int(x-width/2), int(y-diameter/2-18), width, int(diameter+(90 if with_motherships else 105)))
        layout.append((world, (x, y), diameter, hit))
    return layout


def draw_motherships(app, system, ships):
    if not ships:
        return
    if app.system_mothership_system != system.id:
        app.system_mothership_system = system.id
        selected = next((i for i, s in enumerate(ships) if s.habitat.id == app.game.selected_planet), 0)
        app.system_mothership_page = selected//MOTHERSHIPS_PER_PAGE
    last = (len(ships)-1)//MOTHERSHIPS_PER_PAGE
    app.system_mothership_page = min(app.system_mothership_page, last)
    start = app.system_mothership_page*MOTHERSHIPS_PER_PAGE
    text(app.canvas, "MOTHERSHIPS IN ORBIT · CLICK TO OPEN", (356, 534), 9, GOLD, "mono")
    if last:
        text(app.canvas, f"{app.system_mothership_page+1}/{last+1}", (1257, 534), 10, MUTED, right=True)
        for key, label, step, x, enabled in (("previous", "←", -1, 1274, start > 0),
                                            ("next", "→", 1, 1316, app.system_mothership_page < last)):
            app.button("system_motherships_"+key, label, (x, 527, 32, 22),
                       lambda delta=step: setattr(app, "system_mothership_page", app.system_mothership_page+delta),
                       enabled=enabled)
    for index, ship in enumerate(ships[start:start+MOTHERSHIPS_PER_PAGE]):
        rect = pg.Rect(356+index*238, 553, 226, 55)
        button = app.button(f"system_mothership_{ship.id}", "", rect,
                            lambda sid=ship.id: app.open_mothership(sid), "hotspot")
        active = app.is_active(button) or ship.habitat.id == app.game.selected_planet
        color = app.empire_color(ship.owner)
        panel(app.canvas, rect, (20, 37, 47) if active else (10, 24, 33), GOLD if active else color)
        ship_icon(app.canvas, (rect.x+27, rect.centery), .6, color, kind="mothership")
        text(app.canvas, shorten(ship.name, 158, 14), (rect.x+57, rect.y+8), 14, GOLD if active else INK)
        text(app.canvas, f"{ship.habitat.population} / 50 B · {ship.hull} hull", (rect.x+58, rect.y+32), 10, color)


def draw_system(app):
    from .black_holes import KIND
    if app.game.systems[app.game.selected_system].kind == KIND:
        app.draw_galaxy()
        return
    surface = app.canvas
    game = app.game
    system = game.known_system(game.selected_system)
    if system is None:
        draw_unsurveyed_system(app, game.systems[game.selected_system])
        from .hyperlanes import connections
        if connections(game, game.selected_system):
            app.button("system_hyperlanes", "Forgotten hyperlanes", (810, 124, 256, 48), lambda: app.go("hyperlane"))
        return
    live = game.system_visible(system.id)
    homes = motherships.visible_at(game, system.id)
    app.chrome("SYSTEM OVERVIEW")
    app.button("system_back", "←  Galaxy map", (64, 124, 205, 48), lambda: app.go("galaxy"), "ghost")
    text(surface, shorten(f"GALAXY / {system.name.upper()}", 240, 11, "mono"), (300, 143), 11, MUTED, "mono", 1)
    text(surface, f"YEAR {game.year}   ·   {game.credits:,} CR   ·   {game.research:,} RP", (1376, 140), 13, GOLD, "mono", right=True)

    text(surface, shorten(system.name, 860, 52, "title"), (64, 191), 52, INK, "title")
    text(surface, f"{system.kind}   /   {len(system.worlds)} planets"+
         (f"   /   {len(homes)} mothership{'s' if len(homes) != 1 else ''}" if homes else ""), (67, 260), 16, MUTED)
    app.button("system_megastructures", "Megastructures", (570, 124, 224, 48), lambda: app.go("megastructure"))
    if motherships.is_wanderer(game):
        app.button("system_hyperlanes", "Forgotten hyperlanes", (810, 124, 256, 48), lambda: app.go("hyperlane"))
    ships, rivals = len(game.fleet_at(system.id)), len(game.foreign_fleet(system.id)) if live else 0
    guardian_status = monsters.known_status(game, system.id)
    guardian = monsters.at(game, system.id) if guardian_status else None
    label = f"ORBIT: {ships} YOUR SHIPS · {rivals} RIVAL SHIPS" if ships or rivals else "YOUR HOME SYSTEM" if system.id == 0 else "SYSTEM SURVEY"
    if not live:
        label = f"LAST OBSERVED: TURN {game.exploration.survey(system.id).last_seen} · ACTIVITY UNKNOWN"
    if guardian:
        label = ("GUARDED" if live else "LAST SEEN GUARDED")+" · "+guardian.spec.name.upper() if guardian_status == "alive" else "GUARDIAN DEFEATED · WORLDS ACCESSIBLE"
        ship_icon(surface, (997, 240), .9, kind=guardian.kind)
    text(surface, label, (1376, 211), 11, RED if guardian_status == "alive" else CYAN, "mono", 1, right=True)
    own_bases = len(defenses.bases(game, system.id, "player")) if live else 0
    enemy_bases = sum(p.owner != "player" for p in defenses.bases(game, system.id)) if live else 0
    if live and (ships or own_bases) and (rivals or enemy_bases or guardian_status == "alive"):
        opponents = game.opponents_at(system.id)
        if len(opponents) > 1 and guardian_status != "alive":
            if app.rival_id not in opponents:
                app.rival_id = opponents[0]
            text(surface, shorten("Target: "+game.empire_name_for(app.rival_id), 268, 12), (765, 263), 12, app.empire_color(app.rival_id))
            app.button("system_target_next", "→", (1046, 247, 42, 43), lambda: app.change_rival(1, system.id))
        reason = game.engagement_error(system.id)
        app.button("system_engage", "Face guardian" if guardian_status == "alive" else "Engage orbital defenses" if enemy_bases else "Engage opposing fleet", (1100, 247, 276, 43),
                   lambda: app.engage_request(system.id), enabled=reason is None)
        if reason:
            text(surface, "Frigate required to engage", (1080, 262), 11, MUTED, right=True)

    panel(surface, (64, 308, 1312, 311), (6, 16, 24))
    text(surface, "ORBITAL OVERVIEW", (88, 329), 10, GOLD, "mono", 2)
    text(surface, "SCHEMATIC · NOT TO SCALE", (1352, 329), 10, FAINT, "mono", right=True)
    if system.worlds:
        pg.draw.line(surface, LINE, (287, 420), (1325, 420), 1)
    draw_star(surface, (224, 434), 45, STAR_COLORS[system.kind])
    if system.megastructure and system.megastructure.kind == "dyson_sphere":
        from .megastructure_view import draw_art
        m = system.megastructure
        draw_art(surface, m.kind, (108, 343, 232, 181), stage=m.stage,
                 progress=m.progress/m.stage_work if m.stage_work else 0)
    text(surface, system.name.upper(), (191, 528), 13, GOLD, "mono", 1)
    text(surface, "PRIMARY STAR", (171, 555), 10, FAINT, "mono", 1)

    layout = system_layout(system.worlds, with_motherships=bool(homes))
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
        if guardian and world.id in monsters.prize_ids(system, guardian):
            text(surface, "ANCIENT RUINS" if guardian.kind == "ancient_sentinel" else "PRIZE WORLD",
                 (hit.x+2, y+diameter/2+60), 9, GOLD, "mono")
        if any(e.planet_id == world.id and encounters.known_status(game, e) == "active"
               for e in encounters.known_at(game, system.id) if e.kind == "planet"):
            text(surface, "PIRATE GUARD", (hit.x+2, y+diameter/2+60), 9, encounters.COLOR, "mono")
        if world.colonized:
            pg.draw.circle(surface, app.empire_color(world.owner),
                           (int(x+diameter/2+9), int(y-diameter/2-2)), 3)
        elif world.outpost_owner:
            color = app.empire_color(world.outpost_owner)
            pg.draw.rect(surface, color, (round(x+diameter/2+5), round(y-diameter/2-5), 9, 7), 1)
            text(surface, "OUTPOST", (hit.x+2, y+diameter/2+60), 9, color, "mono")

    if not system.worlds:
        text(surface, "No planets detected.", (479, 408), 29, INK, "title")
        paragraph(surface, "Mothership habitats are anchored around this star." if homes else
                  "This system contains only its central star. Return to the galaxy map to survey another system.",
                  (480, 458), 619, 16, MUTED, 27)

    draw_motherships(app, system, homes)
    draw_system_portal(app, system)
    colonies = sum(p.colonized for p in system.worlds)
    habitable = sum(p.habitability >= 35 for p in system.worlds)
    population = sum(p.workforce for p in system.worlds)+sum(s.habitat.workforce for s in homes)
    summaries = [("WORLDS", str(len(system.worlds)), "Surveyed planets"),
                 ("HABITABLE", str(habitable), "At least 35% suitability"),
                 ("SETTLEMENTS" if homes and colonies else "HABITATS" if homes else "COLONIES",
                  str(colonies+len(homes)), "Planets and mobile homes" if homes and colonies else "Anchored motherships" if homes else "Established settlements"),
                 ("POPULATION", f"{population} B", "Current inhabitants" if live else "Last known inhabitants")]
    for i, (label, value, caption) in enumerate(summaries):
        x = 64+i*334
        panel(surface, (x, 645, 310, 122))
        text(surface, label, (x+21, 663), 10, MUTED, "mono", 1)
        text(surface, value, (x+20, 688), 29, CYAN if i==2 else INK)
        text(surface, caption, (x+21, 735), 11, MUTED)
    if system.megastructure:
        from .megastructure_view import draw_ribbon
        draw_ribbon(app, system, live)
    hint = "Click a planet to survey it. Colony and fleet colors identify each empire." if system.worlds else "Use Previous / Next to survey another system."
    if homes:
        hint = "Click a mothership to open its habitat. Colors identify each empire's planets and mobile homes."
    if not live:
        hint = "Stored survey. Send a ship to refresh colony ownership, population and activity."
    if guardian:
        benefit = monsters.prize_details(guardian, defeated=guardian_status == "defeated")
        hint = f"{monsters.reward_caption(guardian, defeated=guardian_status == 'defeated')} · {benefit}. " + ("Defeat its guardian to colonize." if guardian_status == "alive" else "Guardian defeated.")
    text(surface, shorten(hint, 1310, 14), (65, 792), 14, MUTED)
    app.button("system_pause", "Menu", (64, 832, 127, 46), app.pause)
    app.button("system_save", "Save game · F5", (206, 832, 222, 46), app.save_game)
    if game.encounters.enabled:
        app.button("system_encounters", "Encounters & search", (444, 832, 300, 46), lambda: app.open_encounters(system.id))
    app.button("system_previous", "← Previous system", (846, 832, 249, 46), lambda: app.cycle_system(-1))
    app.button("system_next", "Next system →", (1109, 832, 267, 46), lambda: app.cycle_system(1))
