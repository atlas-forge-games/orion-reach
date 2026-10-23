"""Survey-aware system overview and direct planet links beside the galaxy map."""

import pygame as pg

from . import monsters, defenses, motherships, hyperlanes
from .galaxy_labels import known_owners
from .planet_art import draw_planet, draw_star
from .system_views import STAR_COLORS, visual_seed
from .ui import CYAN, FAINT, GOLD, INK, LINE, MUTED, RED, arrow, panel, paragraph, shorten, text

SYSTEM_PANEL = pg.Rect(1051, 180, 325, 573)
PLANETS_PER_PAGE = 4


def system_entries(game, system):
    return [s.habitat for s in motherships.visible_at(game, system.id)]+list(system.worlds)


def entry_key(world):
    return f"galaxy_mothership_{-world.id}" if world.habitat else f"galaxy_world_{world.id}"


def allegiance(game, system):
    owners = set(known_owners(game, system))
    homes = motherships.visible_at(game, system.id)
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
    worlds = known.worlds if known else []
    entries = system_entries(game, known) if known else []
    has_homes = any(p.habitat for p in entries)
    if app.galaxy_page_system != star.id:
        app.galaxy_page_system = star.id
        selected = next((i for i, p in enumerate(entries) if p.id == game.selected_planet), 0)
        app.galaxy_planet_page = selected//PLANETS_PER_PAGE
    last = max(0, (len(entries)-1)//PLANETS_PER_PAGE)
    app.galaxy_planet_page = max(0, min(app.galaxy_planet_page, last))
    panel(surface, r)
    text(surface, "SYSTEM OVERVIEW", (x, 201), 10, GOLD, "mono", 1)
    survey = game.exploration.survey(star.id)
    status = "LIVE" if live else f"SEEN T{survey.last_seen}" if known else "UNCHARTED"
    text(surface, status, (right, 202), 9, CYAN if live else MUTED, "mono", right=True)
    text(surface, shorten(game.system_name(star.id), width-58, 29, "title"), (x, 227), 29, INK, "title")
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
        routes = hyperlanes.connections(game, star.id)
        app.button("open_system", "System view" if routes else "Full system view", (x, 705, 127 if routes else width, 32),
                   lambda: app.open_system(star.id), "command", icon="system")
        if routes:
            text(surface, f"{len(routes)} forgotten hyperlane{'s' if len(routes) != 1 else ''} · 1-turn passages", (x, 682), 11, CYAN)
            app.button("galaxy_hyperlanes", "Hyperlanes", (x+136, 705, width-136, 32), lambda: app.go("hyperlane"), "command")
        return

    owners = known_owners(game, known)
    owner_color = app.empire_color(next(iter(owners))) if len(owners) == 1 else MUTED
    text(surface, shorten(allegiance(game, known), width, 11), (x, 290), 11, owner_color)
    summaries = [("WORLDS", len(worlds)), ("HABITABLE", sum(p.habitability >= 35 for p in worlds)),
                 ("HOMES" if has_homes else "COLONIES", sum(p.colonized for p in entries)),
                 ("POPULATION", f"{sum(p.workforce for p in entries)} B")]
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
    text(surface, "MOTHERSHIPS & PLANETS" if has_homes else "PLANETS · INNER TO OUTER", (x, 370), 9, GOLD, "mono")
    for index, world in enumerate(entries[start:start+PLANETS_PER_PAGE]):
        row = pg.Rect(x-4, 389+index*60, width+8, 55)
        action = (lambda sid=-world.id: app.open_mothership(sid)) if world.habitat else (lambda pid=world.id: app.open_planet(pid))
        button = app.button(entry_key(world), "", row, action, "hotspot")
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
        value = "HOME" if world.habitat else "GAS" if world.is_gas_giant else f"{world.workforce} B" if world.colonized else "BASE" if world.outpost_owner else f"{world.habitability}%"
        text(surface, value, (row.right-9, row.y+6), 10, color, right=True)
        detail = "Mobile habitat · Quarter-speed travel" if world.habitat else "Gas Giant · Deep atmosphere" if world.is_gas_giant else f"{world.biome} · {world.size} · {world.richness}"
        text(surface, shorten(detail, row.w-58, 10),
             (left, row.y+24), 10, MUTED)
        owner = (game.empire_name_for(world.owner) if world.colonized else
                 "Outpost · "+game.empire_name_for(world.outpost_owner) if world.outpost_owner else "Not colonizable" if world.is_gas_giant else "Uncolonized")
        if world.id in prizes:
            owner += " · Ancient ruins" if guardian.kind == "ancient_sentinel" else " · Prize world"
        text(surface, shorten(owner, row.w-58, 9), (left, row.y+40), 9, color)

    if not entries:
        draw_star(surface, (r.centerx, 441), 30, STAR_COLORS[star.kind])
        text(surface, "No planets detected", (x, 512), 20, INK, "title")
        paragraph(surface, "This system contains only its central star.", (x, 551), width, 13, MUTED, 23)
    if last:
        text(surface, f"{start+1}–{min(start+PLANETS_PER_PAGE,len(entries))} OF {len(entries)} "+("LOCATIONS" if has_homes else "WORLDS"), (x, 645), 10, MUTED, "mono")
        for name, delta, bx, enabled in (("previous", -1, right-82, start > 0), ("next", 1, right-37, app.galaxy_planet_page < last)):
            button = app.button(f"galaxy_planets_{name}", "", (bx, 635, 37, 28),
                                lambda step=delta: app.change_galaxy_planet_page(step), "hotspot", enabled=enabled)
            panel(surface, button.rect, (16, 31, 41), GOLD if enabled and app.is_active(button) else LINE)
            arrow(surface, button.rect.center, GOLD if enabled else FAINT, back=delta < 0)
    elif entries:
        text(surface, "Click a planet or mothership" if has_homes else "Click a planet to open it", (x, 645), 11, MUTED)

    ships = len(game.fleet_at(star.id))
    rivals = len(game.foreign_fleet(star.id)) if live else 0
    from . import encounters
    pirates = [e for e in encounters.known_at(game, star.id) if encounters.known_status(game, e) in ("active", "incoming")]
    orbit = f"Orbit: {rivals} ships · Computer-controlled" if game.is_observer else f"Orbit: {ships} yours · {rivals} rival ships"
    if guardian:
        note = (("GUARDED" if live else "LAST SEEN GUARDED")+" · "+guardian.spec.name
                if guardian_status == "alive" else "Guardian defeated · Worlds accessible")
        text(surface, shorten(note, width, 11), (x, 670), 11, RED if guardian_status == "alive" else CYAN)
        scan = orbit if live else "Stored survey · Enemy activity unknown"
    elif pirates:
        text(surface, "PIRATE ACTIVITY · Inspect the orange flag", (x, 670), 11, encounters.COLOR)
        scan = orbit if live else "Last known pirate contact"
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
    if routes := hyperlanes.connections(game, star.id):
        scan = f"{len(routes)} forgotten hyperlane{'s' if len(routes) != 1 else ''} · 1-turn passages"
    elif project := hyperlanes.project_at(game, star.id):
        scan = f"Hyperlane research · {project.progress}/{project.cost} RP"
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
    show_pirates = bool(pirates) and not can_face
    show_hyperlane = not can_face and not show_pirates and motherships.is_wanderer(game)
    full_width = 127 if can_face or show_hyperlane or show_pirates else width
    app.button("open_system", "System view" if can_face or show_hyperlane or show_pirates else "Full system view", (x, 707, full_width, 30),
               lambda: app.open_system(star.id), "command")
    if can_face:
        app.button("galaxy_engage", "Face guardian" if guardian_status == "alive" else "Engage defenses" if enemy_bases else "Engage fleet",
                   (x+136, 707, width-136, 30), lambda: app.engage_request(star.id, target), "command", enabled=reason is None)
    elif show_pirates:
        app.button("galaxy_pirates", "Pirates", (x+136, 707, width-136, 30), lambda: app.open_encounters(star.id), "command")
    elif show_hyperlane:
        app.button("galaxy_hyperlanes", "Hyperlanes", (x+136, 707, width-136, 30), lambda: app.go("hyperlane"), "command")
