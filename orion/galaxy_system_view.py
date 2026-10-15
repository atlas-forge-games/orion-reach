"""Survey-aware system overview and direct planet links beside the galaxy map."""

import pygame as pg

from . import monsters, defenses
from .planet_art import draw_planet, draw_star
from .system_views import STAR_COLORS, visual_seed
from .ui import CYAN, FAINT, GOLD, INK, LINE, MUTED, RED, arrow, panel, paragraph, shorten, text

SYSTEM_PANEL = pg.Rect(1051, 180, 325, 573)
PLANETS_PER_PAGE = 4


def allegiance(game, system):
    owners = {owner for p in system.worlds for owner in (p.owner, p.outpost_owner) if owner}
    homes = [s for s in game.visible_ships() if s.habitat and not s.in_transit and s.system_id == system.id]
    owners.update(s.owner for s in homes)
    if homes and len(owners) == 1:
        return "Wanderer anchorage"
    if len(owners) > 1:
        return "Shared system"
    if "player" in owners:
        return "Your empire" if any(p.owner == "player" for p in system.worlds) else "Your refuelling outpost"
    return next((game.empire_name_for(owner) for owner in game.opponents if owner in owners), "Unclaimed")


def draw_system_panel(app, star):
    from . import black_holes, black_hole_view
    if star.kind == black_holes.KIND:
        black_hole_view.draw_panel(app, star)
        return
    surface, game = app.canvas, app.game
    r = SYSTEM_PANEL
    x, right, width = r.x+24, r.right-24, r.w-48
    known = game.known_system(star.id)
    live = game.system_visible(star.id)
    if app.galaxy_page_system != star.id:
        app.galaxy_page_system = star.id
        app.galaxy_planet_page = (game.selected_planet or 0)//PLANETS_PER_PAGE
    worlds = known.worlds if known else []
    last = max(0, (len(worlds)-1)//PLANETS_PER_PAGE)
    app.galaxy_planet_page = min(app.galaxy_planet_page, last)
    panel(surface, r)
    text(surface, "SYSTEM OVERVIEW", (x, 201), 10, GOLD, "mono", 1)
    survey = game.exploration.survey(star.id)
    status = "LIVE" if live else f"SEEN T{survey.last_seen}" if known else "UNCHARTED"
    text(surface, status, (right, 202), 9, CYAN if live else MUTED, "mono", right=True)
    text(surface, shorten(star.name, width-58, 29, "title"), (x, 227), 29, INK, "title")
    text(surface, star.kind, (x, 267), 12, MUTED)
    draw_star(surface, (right-21, 254), 13, STAR_COLORS[star.kind])

    if known is None:
        text(surface, "Planetary data unknown", (x, 290), 11, FAINT)
        pg.draw.line(surface, LINE, (x, 318), (right, 318))
        draw_star(surface, (r.centerx, 392), 32, STAR_COLORS[star.kind])
        text(surface, "SURVEY REQUIRED", (x, 462), 11, CYAN, "mono", 1)
        paragraph(surface, "Send a ship to reveal this system's planets, resources and inhabitants.",
                  (x, 493), width, 14, MUTED, 24)
        paragraph(surface, "A scout can also search for discoveries.", (x, 579), width, 12, GOLD, 20)
        app.button("galaxy_build_scout", "Build a scout", (x, 628, width, 39), app.open_scout_shipyard,
                   "command", icon="fleets", enabled=game.headquarters() is not None)
        app.button("open_system", "Full system view", (x, 705, width, 32),
                   lambda: app.open_system(star.id), "command", icon="system")
        return

    owners = {owner for world in known.worlds for owner in (world.owner, world.outpost_owner) if owner}
    owner_color = app.empire_color(next(iter(owners))) if len(owners) == 1 else MUTED
    text(surface, shorten(allegiance(game, known), width, 11), (x, 290), 11, owner_color)
    summaries = [("WORLDS", len(worlds)), ("HABITABLE", sum(p.habitability >= 35 for p in worlds)),
                 ("COLONIES", sum(p.colonized for p in worlds)), ("POPULATION", f"{sum(p.workforce for p in worlds)} B")]
    strip = pg.Rect(x-6, 313, width+12, 43)
    panel(surface, strip, (13, 27, 36))
    cell = strip.w/4
    for i, (label, value) in enumerate(summaries):
        left = round(strip.x+i*cell)+7
        text(surface, label, (left, 319), 8, MUTED, "mono")
        text(surface, str(value), (left, 332), 17, CYAN if i == 2 else INK)
        if i:
            pg.draw.line(surface, LINE, (left-8, 322), (left-8, 348))

    guardian_status = monsters.known_status(game, star.id)
    guardian = monsters.at(game, star.id) if guardian_status else None
    prizes = monsters.prize_ids(known, guardian) if guardian else ()
    start = app.galaxy_planet_page*PLANETS_PER_PAGE
    text(surface, "PLANETS · INNER TO OUTER", (x, 370), 9, GOLD, "mono")
    for index, world in enumerate(worlds[start:start+PLANETS_PER_PAGE]):
        row = pg.Rect(x-4, 389+index*60, width+8, 55)
        button = app.button(f"galaxy_world_{world.id}", "", row,
                            lambda pid=world.id: app.open_planet(pid), "hotspot")
        active = app.is_active(button)
        selected = world.id == game.selected_planet
        panel(surface, row, (23, 43, 53) if active else (16, 32, 42) if selected else (9, 22, 31),
              GOLD if active else (58, 90, 103) if selected else LINE)
        draw_planet(surface, world, (row.x+23, row.centery), 35, visual_seed(game, known, world))
        color = app.empire_color(world.owner or world.outpost_owner) if world.owner or world.outpost_owner else MUTED
        if world.colonized or world.outpost_owner:
            pg.draw.circle(surface, color, (row.x+37, row.y+12), 3)
        left = row.x+48
        text(surface, shorten(world.name, row.w-102, 14), (left, row.y+4), 14, GOLD if active else INK)
        value = f"{world.workforce} B" if world.colonized else "BASE" if world.outpost_owner else f"{world.habitability}%"
        text(surface, value, (row.right-9, row.y+6), 10, color, right=True)
        text(surface, shorten(f"{world.biome} · {world.size} · {world.richness}", row.w-58, 10),
             (left, row.y+24), 10, MUTED)
        owner = (game.empire_name_for(world.owner) if world.colonized else
                 "Outpost · "+game.empire_name_for(world.outpost_owner) if world.outpost_owner else "Uncolonized")
        if world.id in prizes:
            owner += " · Ancient ruins" if guardian.kind == "ancient_sentinel" else " · Prize world"
        text(surface, shorten(owner, row.w-58, 9), (left, row.y+40), 9, color)

    if not worlds:
        draw_star(surface, (r.centerx, 441), 30, STAR_COLORS[star.kind])
        text(surface, "No planets detected", (x, 512), 20, INK, "title")
        paragraph(surface, "This system contains only its central star.", (x, 551), width, 13, MUTED, 23)
    if last:
        text(surface, f"{start+1}–{min(start+PLANETS_PER_PAGE,len(worlds))} OF {len(worlds)} WORLDS", (x, 645), 10, MUTED, "mono")
        for name, delta, bx, enabled in (("previous", -1, right-82, start > 0), ("next", 1, right-37, app.galaxy_planet_page < last)):
            button = app.button(f"galaxy_planets_{name}", "", (bx, 635, 37, 28),
                                lambda step=delta: app.change_galaxy_planet_page(step), "hotspot", enabled=enabled)
            panel(surface, button.rect, (16, 31, 41), GOLD if enabled and app.is_active(button) else LINE)
            arrow(surface, button.rect.center, GOLD if enabled else FAINT, back=delta < 0)
    elif worlds:
        text(surface, "Click a planet to open it", (x, 645), 11, MUTED)

    ships = len(game.fleet_at(star.id))
    rivals = len(game.foreign_fleet(star.id)) if live else 0
    orbit = f"Orbit: {rivals} ships · Computer-controlled" if game.is_observer else f"Orbit: {ships} yours · {rivals} rival ships"
    if guardian:
        note = (("GUARDED" if live else "LAST SEEN GUARDED")+" · "+guardian.spec.name
                if guardian_status == "alive" else "Guardian defeated · Worlds accessible")
        text(surface, shorten(note, width, 11), (x, 670), 11, RED if guardian_status == "alive" else CYAN)
        scan = orbit if live else "Stored survey · Enemy activity unknown"
    else:
        note = orbit if live else "Stored survey · Enemy activity unknown"
        text(surface, note, (x, 670), 11, CYAN if live else MUTED)
        scan = "Scout survey complete" if star.id in game.exploration.scanned_player else "A scout can search for discoveries"
    own_bases = len(defenses.bases(game, star.id, "player")) if live else 0
    enemy_bases = sum(p.owner != "player" for p in defenses.bases(game, star.id)) if live else 0
    if own_bases or enemy_bases:
        scan = f"Missile bases: {own_bases} yours · {enemy_bases} opposing"
    if game.is_observer:
        scan = f"{rivals} ships in orbit · {enemy_bases} missile bases · Read only"
    if known.megastructure and not (own_bases or enemy_bases):
        m = known.megastructure
        scan = f"{m.spec.name} · stage {m.stage}/4"+(" · last seen" if not live else "")
    opponents = game.opponents_at(star.id) if live else []
    can_face = live and (ships or own_bases) and (rivals or enemy_bases or guardian_status == "alive")
    target = app.rival_id if app.rival_id in opponents else opponents[0] if opponents else None
    reason = game.engagement_error(star.id, target=target) if can_face else None
    if can_face and len(opponents) > 1 and guardian_status != "alive":
        text(surface, shorten("Target: "+game.empire_name_for(target), width-39, 10), (x, 687), 10, app.empire_color(target))
        button = app.button("galaxy_target_next", "", (right-28, 682, 28, 21),
                            lambda: app.change_rival(1, star.id), "hotspot")
        arrow(surface, button.rect.center, GOLD)
    else:
        text(surface, shorten(reason or scan, width, 9), (x, 687), 9, MUTED)
    full_width = 127 if can_face else width
    app.button("open_system", "System view" if can_face else "Full system view", (x, 707, full_width, 30),
               lambda: app.open_system(star.id), "command")
    if can_face:
        app.button("galaxy_engage", "Face guardian" if guardian_status == "alive" else "Engage defenses" if enemy_bases else "Engage fleet",
                   (x+136, 707, width-136, 30), lambda: app.engage_request(star.id, target), "command", enabled=reason is None)
