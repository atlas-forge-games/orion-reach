"""Exploration log and survey-aware map intelligence."""

import pygame as pg

from .exploration import DISCOVERIES
from .fleet_art import ship_icon
from .planet_art import draw_star
from . import monsters
from .ui import CYAN, FAINT, GOLD, INK, LINE, MUTED, RED, RIVAL_COLOR, panel, paragraph, shorten, text

FINDS_PER_PAGE = 5
STAR_COLORS = {"Yellow dwarf": (230, 207, 141), "Blue star": (113, 181, 231),
               "Red dwarf": (221, 124, 108), "White star": (217, 228, 239), "Orange dwarf": (235, 170, 106)}


def draw_system_intelligence(app, star):
    from . import black_holes, black_hole_view
    if star.kind == black_holes.KIND:
        black_hole_view.draw_panel(app, star)
        return
    surface, game = app.canvas, app.game
    r = app.galaxy_layout.inspector
    x, width = r.x+16, r.w-32
    known = game.known_system(star.id)
    live = game.system_visible(star.id)
    panel(surface, r)
    heading = "SYSTEM INTELLIGENCE" if live else "LAST KNOWN SURVEY" if known else "UNCHARTED SYSTEM"
    text(surface, heading, (x, r.y+23), 10, GOLD, "mono", 1)
    text(surface, game.system_name(star.id), (x, r.y+65), 31, INK, "title")
    text(surface, star.kind, (x, r.y+110), 14, MUTED)
    guardian_status = monsters.known_status(game, star.id)
    guardian = monsters.at(game, star.id) if guardian_status else None
    if guardian:
        ship_icon(surface, (r.centerx, r.y+186), 1.2, kind=guardian.kind)
        text(surface, guardian.spec.name, (x, r.y+234), 17, RED if guardian_status == "alive" else CYAN)
        text(surface, monsters.reward_caption(guardian, defeated=guardian_status == "defeated"), (x, r.y+261), 12, GOLD)
    else:
        draw_star(surface, (r.centerx, r.y+205), 26, STAR_COLORS[star.kind])
    if known is None:
        text(surface, "SURVEY REQUIRED", (x, r.y+276), 11, CYAN, "mono", 1)
        paragraph(surface, "The star is on your charts. Its planets, resources and inhabitants are unknown until a ship arrives.",
                  (x, r.y+312), width, 15, MUTED, 25)
        text(surface, "Scouts can also recover discoveries.", (x, r.y+446), 12, GOLD)
    else:
        owners = {owner for p in known.worlds for owner in (p.owner, p.outpost_owner) if owner}
        allegiance = ("Shared system" if len(owners)>1 else "Your empire" if "player" in owners else
                      " / ".join(game.empire_name_for(o) for o in game.opponents if o in owners) or "Unclaimed")
        survey = game.exploration.survey(star.id)
        label = "LIVE INTELLIGENCE" if live else f"OBSERVED ON TURN {survey.last_seen}"
        text(surface, label, (x, r.y+282), 10, CYAN if live else GOLD, "mono", 1)
        rows = [("Planets", str(known.planets)), ("Primary world", known.biome if known.planets else "None"),
                ("Minerals", known.richness if known.planets else "—"), ("Allegiance", allegiance)]
        for index, (key, value) in enumerate(rows):
            y = r.y+320+index*44
            text(surface, key, (x, y), 13, MUTED)
            text(surface, value, (r.right-16, y), 13, INK, right=True)
            pg.draw.line(surface, LINE, (x, y+30), (r.right-16, y+30))
        scan = "Scout survey complete" if star.id in game.exploration.scanned_player else "A scout can search for discoveries"
        if guardian:
            scan = ("Guardian attacks on arrival" if live else "Last seen guarded · Revisit to update") if guardian_status == "alive" else "Guardian defeated · Worlds accessible"
        text(surface, scan, (x, r.bottom-82), 11, RED if guardian_status == "alive" else MUTED)


def draw_unsurveyed_system(app, system):
    surface = app.canvas
    app.chrome("UNSURVEYED SYSTEM")
    text(surface, app.game.system_name(system.id), (64, 191), 52, INK, "title")
    text(surface, f"{system.kind} · Planetary data unknown", (67, 260), 16, MUTED)
    panel(surface, (64, 308, 1312, 439))
    draw_star(surface, (291, 483), 72, STAR_COLORS[system.kind])
    text(surface, "Beyond your charts", (519, 352), 34, INK, "title")
    paragraph(surface, "Send a ship to this star to reveal its planets and colonies. A scout can also recover abandoned supplies, ancient records or a derelict probe.",
              (522, 419), 738, 18, MUTED, 31)
    paragraph(surface, "On the galaxy map, click a fleet, select ships, choose a destination, then click this star. Surveys complete automatically on arrival.",
              (522, 538), 738, 16, MUTED, 27)
    app.button("unexplored_fleets", "Open fleets", (522, 644, 261, 48), app.open_fleets)
    app.button("unexplored_scout", "Build a scout", (801, 644, 293, 48), app.open_scout_shipyard,
               enabled=app.game.headquarters() is not None)
    app.button("system_pause", "Menu", (64, 832, 127, 46), app.pause)
    app.button("system_save", "Save game · F5", (206, 832, 222, 46), app.save_game)
    app.button("system_previous", "← Previous system", (64, 124, 220, 46), lambda: app.cycle_system(-1))
    app.button("system_next", "Next system →", (298, 124, 220, 46), lambda: app.cycle_system(1))


def draw_exploration(app):
    surface, game = app.canvas, app.game
    app.chrome("EXPLORATION LOG")
    app.button("exploration_back", "←  Back · X", (64, 124, 215, 46), app.close_exploration, "ghost")
    text(surface, f"YEAR {game.year} · TURN {game.turn}", (1376, 141), 12, GOLD, "mono", right=True)
    text(surface, "The unexplored frontier", (64, 190), 42, INK, "title")
    text(surface, "Chart new systems. Recover forgotten knowledge. Find your next home.", (66, 251), 15, MUTED)
    finds = sorted((d for d in game.exploration.discoveries if d.owner == "player"), key=lambda d: (d.turn, d.system_id), reverse=True)
    charted = sum(game.system_explored(s.id) for s in game.systems)
    stats = [("SYSTEMS CHARTED", f"{charted} / {len(game.systems)}"),
             ("SCOUT SURVEYS", str(len(game.exploration.scanned_player))), ("DISCOVERIES RECOVERED", str(len(finds)))]
    for index, (label, value) in enumerate(stats):
        x = 64+index*446
        panel(surface, (x, 289, 420, 84))
        text(surface, label, (x+19, 303), 10, MUTED, "mono", 1)
        text(surface, value, (x+18, 328), 27, CYAN)
    text(surface, "DISCOVERY LOG", (64, 399), 11, GOLD, "mono", 2)
    last = max(0, (len(finds)-1)//FINDS_PER_PAGE)
    app.exploration_page = min(max(0, app.exploration_page), last)
    start = app.exploration_page*FINDS_PER_PAGE
    for index, discovery in enumerate(finds[start:start+FINDS_PER_PAGE]):
        system, spec = game.systems[discovery.system_id], DISCOVERIES[discovery.kind]
        y = 433+index*69
        panel(surface, (64, y, 864, 61))
        text(surface, f"T{discovery.turn:03}", (82, y+12), 11, GOLD, "mono")
        text(surface, f"{system.name} · {spec.name}", (146, y+8), 17, INK)
        text(surface, spec.reward+" · "+spec.description, (147, y+37), 11, MUTED)
        app.button(f"discovery_system_{system.id}", "View", (804, y+13, 103, 36), lambda sid=system.id: app.open_system(sid))
    if not finds:
        panel(surface, (64, 433, 864, 282))
        ship_icon(surface, (157, 551), 1.55, kind="scout")
        text(surface, "Your first discovery is out there.", (258, 471), 26, INK, "title")
        paragraph(surface, "Build a scout and send it to another star. Some systems contain a one-time discovery. The first empire to recover it receives credits or research.",
                  (260, 521), 611, 16, MUTED, 28)
    panel(surface, (952, 399, 424, 419))
    text(surface, "FOG OF WAR: ON" if game.fog_of_war else "FOG OF WAR: OFF", (976, 422), 11, GOLD, "mono", 1)
    paragraph(surface, "Ships reveal planets when they arrive. Last-known surveys remain after departure. Live enemy activity requires a ship or colony in the system."
              if game.fog_of_war else "The entire map is revealed. Scouts can still recover discoveries; revealing the map does not collect their rewards.",
              (977, 464), 373, 15, MUTED, 25)
    paragraph(surface, "Scouts are unarmed: 25 Resources, 12 work and 8 hull. Travel speed matches your other ships. They cannot settle worlds or invade colonies.",
              (977, 597), 373, 14, MUTED, 24)
    app.button("exploration_build_scout", "Open scout shipyard", (976, 736, 376, 57), app.open_scout_shipyard,
               "primary", enabled=game.headquarters() is not None)
    text(surface, f"PAGE {app.exploration_page+1} / {last+1}", (65, 797), 10, FAINT, "mono")
    app.button("exploration_previous", "← Prev", (648, 781, 130, 37), lambda: app.change_exploration_page(-1), enabled=app.exploration_page>0)
    app.button("exploration_next", "Next →", (792, 781, 136, 37), lambda: app.change_exploration_page(1), enabled=app.exploration_page<last)
    app.button("exploration_pause", "Menu", (64, 834, 126, 45), app.pause)
    app.button("exploration_save", "Save · F5", (204, 834, 172, 45), app.save_game)
    text(surface, shorten("Discoveries are recovered automatically and saved with the campaign.", 413, 12, "sans"), (400, 845), 12, MUTED)
