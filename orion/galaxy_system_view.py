"""Survey-aware system overview and direct planet links beside the galaxy map."""

import pygame as pg

from . import monsters, defenses, motherships, hyperlanes
from .galaxy_labels import known_owners
from .planet_art import draw_planet, draw_star
from .system_views import STAR_COLORS, visual_seed
from .ui import CYAN, FAINT, GOLD, INK, LINE, MUTED, RED, arrow, panel, paragraph, shorten, text

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
    r = app.galaxy_layout.inspector
    x, right, width = r.x+15, r.right-15, r.w-30
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
    text(surface, "SYSTEM OVERVIEW", (x, r.y+14), 14, GOLD, "mono", 1)
    survey = game.exploration.survey(star.id)
    status = "LIVE" if live else f"SEEN T{survey.last_seen}" if known else "UNCHARTED"
    text(surface, status, (right, r.y+14), 14, CYAN if live else MUTED, "mono", right=True)
    text(surface, shorten(game.system_name(star.id), width-58, 29, "title"), (x, r.y+42), 29, INK, "title")
    draw_star(surface, (right-19, r.y+61), 13, STAR_COLORS[star.kind])
    if known is None:
        text(surface, star.kind, (x, r.y+84), 14, MUTED)
        pg.draw.line(surface, LINE, (x, r.y+120), (right, r.y+120))
        draw_star(surface, (r.centerx, r.y+202), 32, STAR_COLORS[star.kind])
        text(surface, "SURVEY REQUIRED", (x, r.y+276), 14, CYAN, "mono", 1)
        paragraph(surface, "Send a ship to reveal this system's planets, resources and inhabitants.",
                  (x, r.y+308), width, 15, MUTED, 24)
        paragraph(surface, "A scout can also search for discoveries.", (x, r.bottom-173), width, 14, GOLD, 20)
        app.button("galaxy_build_scout", "Build a scout", (x, r.bottom-120, width, 38), app.open_scout_shipyard,
                   "command", icon="fleets", enabled=game.headquarters() is not None)
        routes = hyperlanes.connections(game, star.id)
        button_w = (width-8)//2 if routes else width
        app.button("open_system", "System view" if routes else "Full system view", (x, r.bottom-50, button_w, 36),
                   lambda: app.open_system(star.id), "command", icon="system")
        if routes:
            text(surface, f"{len(routes)} forgotten hyperlane{'s' if len(routes) != 1 else ''} · 1-turn passages",
                 (x, r.bottom-76), 14, CYAN)
            app.button("galaxy_hyperlanes", "Hyperlanes", (x+button_w+8, r.bottom-50, width-button_w-8, 36),
                       lambda: app.go("hyperlane"), "command")
        return

    owners = known_owners(game, known)
    owner_color = app.empire_color(next(iter(owners))) if len(owners) == 1 else MUTED
    text(surface, shorten(star.kind+" · "+allegiance(game, known), width, 14), (x, r.y+84), 14, owner_color)
    colonies = sum(p.colonized for p in entries)
    unit = ("home" if colonies == 1 else "homes") if has_homes else ("colony" if colonies == 1 else "colonies")
    strip = pg.Rect(x, r.y+113, width, 56)
    panel(surface, strip, (13, 27, 36))
    text(surface, f"{len(worlds)} worlds · {sum(p.habitability >= 35 for p in worlds)} habitable",
         (x+10, strip.y+6), 15, INK)
    text(surface, f"{colonies} {unit} · {sum(p.workforce for p in entries)} B population",
         (x+10, strip.y+30), 14, MUTED)

    guardian_status = monsters.known_status(game, star.id)
    guardian = monsters.at(game, star.id) if guardian_status else None
    prizes = monsters.prize_ids(known, guardian) if guardian else ()
    start = app.galaxy_planet_page*PLANETS_PER_PAGE
    text(surface, "MOTHERSHIPS & PLANETS" if has_homes else "PLANETS · INNER TO OUTER", (x, r.y+188), 14, GOLD, "mono")
    for index, world in enumerate(entries[start:start+PLANETS_PER_PAGE]):
        row = pg.Rect(x, r.y+214+index*52, width, 47)
        action = (lambda sid=-world.id: app.open_mothership(sid)) if world.habitat else (lambda pid=world.id: app.open_planet(pid))
        button = app.button(entry_key(world), "", row, action, "hotspot")
        active = app.is_active(button)
        selected = world.id == game.selected_planet
        panel(surface, row, (23, 43, 53) if active else (16, 32, 42) if selected else (9, 22, 31),
              GOLD if active else (58, 90, 103) if selected else LINE)
        draw_planet(surface, world, (row.x+23, row.centery), 35, visual_seed(game, known, world))
        visible_owner = world.owner or world.outpost_owner or (world.orbital_station.owner if world.orbital_station else None)
        color = app.empire_color(visible_owner) if visible_owner else MUTED
        if world.colonized or world.outpost_owner or world.orbital_station:
            pg.draw.circle(surface, color, (row.x+37, row.y+12), 3)
        left = row.x+48
        text(surface, shorten(world.name, row.w-102, 14), (left, row.y+4), 14, GOLD if active else INK)
        if world.habitat:
            value = "HOME"
        elif world.colonized:
            value = f"{world.workforce} B"
        elif world.orbital_station:
            value = "STN"
        elif world.outpost_owner:
            value = "BASE"
        elif world.id in prizes:
            value = "RUINS" if guardian.kind == "ancient_sentinel" else "PRIZE"
        else:
            value = "GAS" if world.is_gas_giant else f"{world.habitability}%"
        text(surface, value, (row.right-9, row.y+4), 14, color, right=True)
        detail = "Mobile habitat · Quarter-speed travel" if world.habitat else "Gas Giant · Deep atmosphere" if world.is_gas_giant else f"{world.biome} · {world.size} · {world.richness}"
        text(surface, shorten(detail, row.w-58, 14),
             (left, row.y+25), 14, MUTED)
        owner = ("Orbital station · "+game.empire_name_for(world.orbital_station.owner) if world.orbital_station else game.empire_name_for(world.owner) if world.colonized else
                 "Outpost · "+game.empire_name_for(world.outpost_owner) if world.outpost_owner else "Not colonizable" if world.is_gas_giant else "Uncolonized")
        if world.id in prizes:
            owner += " · Ancient ruins" if guardian.kind == "ancient_sentinel" else " · Prize world"
        surface.text_regions.append((row, f"{world.name} · {detail} · {owner}"))

    if not entries:
        draw_star(surface, (r.centerx, r.y+250), 30, STAR_COLORS[star.kind])
        text(surface, "No planets detected", (x, r.y+310), 20, INK, "title")
        paragraph(surface, "This system contains only its central star.", (x, r.y+352), width, 13, MUTED, 23)
    if last:
        text(surface, f"{start+1}–{min(start+PLANETS_PER_PAGE,len(entries))} OF {len(entries)} "+("LOCATIONS" if has_homes else "WORLDS"), (x, r.y+433), 10, MUTED, "mono")
        for name, delta, bx, enabled in (("previous", -1, right-82, start > 0), ("next", 1, right-37, app.galaxy_planet_page < last)):
            button = app.button(f"galaxy_planets_{name}", "", (bx, r.y+426, 37, 28),
                                lambda step=delta: app.change_galaxy_planet_page(step), "hotspot", enabled=enabled)
            panel(surface, button.rect, (16, 31, 41), GOLD if enabled and app.is_active(button) else LINE)
            arrow(surface, button.rect.center, GOLD if enabled else FAINT, back=delta < 0)

    ships = len(game.fleet_at(star.id))
    rivals = len(game.foreign_fleet(star.id)) if live else 0
    from . import encounters
    pirates = [e for e in encounters.known_at(game, star.id) if encounters.known_status(game, e) in ("active", "incoming")]
    orbit = f"Orbit: {rivals} ships · Computer-controlled" if game.is_observer else f"Orbit: {ships} yours · {rivals} rival ships"
    if guardian:
        note = (("GUARDED" if live else "LAST SEEN GUARDED")+" · "+guardian.spec.name
                if guardian_status == "alive" else "Guardian defeated · Worlds accessible")
        text(surface, shorten(note, width, 11), (x, r.bottom-104), 11, RED if guardian_status == "alive" else CYAN)
        scan = orbit if live else "Stored survey · Enemy activity unknown"
    elif pirates:
        text(surface, "PIRATE ACTIVITY · Inspect the orange flag", (x, r.bottom-104), 11, encounters.COLOR)
        scan = orbit if live else "Last known pirate contact"
    else:
        note = orbit if live else "Stored survey · Enemy activity unknown"
        text(surface, note, (x, r.bottom-104), 11, CYAN if live else MUTED)
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
        text(surface, shorten("Target: "+game.empire_name_for(target), width-39, 10), (x, r.bottom-80), 10, app.empire_color(target))
        button = app.button("galaxy_target_next", "", (right-28, r.bottom-84, 28, 24),
                            lambda: app.change_rival(1, star.id), "hotspot")
        arrow(surface, button.rect.center, GOLD)
    else:
        text(surface, shorten(reason or scan, width, 9), (x, r.bottom-80), 9, MUTED)
    show_pirates = bool(pirates) and not can_face
    show_hyperlane = not can_face and not show_pirates and motherships.is_wanderer(game)
    full_width = (width-8)//2 if can_face or show_hyperlane or show_pirates else width
    app.button("open_system", "System view" if can_face or show_hyperlane or show_pirates else "Full system view", (x, r.bottom-50, full_width, 36),
               lambda: app.open_system(star.id), "command")
    if can_face:
        app.button("galaxy_engage", "Face guardian" if guardian_status == "alive" else "Engage defenses" if enemy_bases else "Engage fleet",
                   (x+full_width+8, r.bottom-50, width-full_width-8, 36), lambda: app.engage_request(star.id, target), "command", enabled=reason is None)
    elif show_pirates:
        app.button("galaxy_pirates", "Pirates", (x+full_width+8, r.bottom-50, width-full_width-8, 36), lambda: app.open_encounters(star.id), "command")
    elif show_hyperlane:
        app.button("galaxy_hyperlanes", "Hyperlanes", (x+full_width+8, r.bottom-50, width-full_width-8, 36), lambda: app.go("hyperlane"), "command")
