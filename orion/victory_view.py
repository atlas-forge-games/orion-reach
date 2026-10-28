"""Victory progress, gate construction and final campaign results."""

import math
import pygame as pg

from .building_art import draw_building_art, load_building_art
from .production import ASCENSION_GATE
from . import production as production_balance
from .research import TECHNOLOGIES
from .council_view import council_summary
from .victory import CONDITION_NAMES, colonies, gate_blocked, gate_site, race_goal, known_race_goals
from .race_art import draw_race_portrait
from .races import RACES
from .exploration import known_rival_colonies
from .ui import CYAN, FAINT, GOLD, INK, LINE, MUTED, RIVAL_COLOR, panel, paragraph, shorten, text


def gate_icon(surface, center, radius=64, color=CYAN):
    x, y = center
    if load_building_art("ascension_gate") is not None:
        extent = radius+18
        draw_building_art(surface, "ascension_gate", (x-extent, y-extent, extent*2, extent*2))
        return
    for size, shade in ((radius+18, LINE), (radius, color), (radius-9, MUTED)):
        pg.draw.circle(surface, shade, (x, y), size, 2)
    for index in range(8):
        angle = index*math.tau/8
        points = [(x+math.cos(angle)*r, y+math.sin(angle)*r) for r in (radius-5, radius+12)]
        pg.draw.line(surface, GOLD, *points, 4)
    pg.draw.circle(surface, color, (x, y), 5)
    pg.draw.line(surface, color, (x-23, y), (x+23, y), 1)
    pg.draw.line(surface, color, (x, y-23), (x, y+23), 1)


def progress(surface, rect, fraction, color=CYAN):
    pg.draw.rect(surface, LINE, rect)
    pg.draw.rect(surface, color, (*rect[:2], round(rect[2]*min(1, fraction)), rect[3]))


def draw_race_objectives(app):
    from . import race_victory as legacy
    game, surface = app.game, app.canvas
    enabled = "race" in game.victory_conditions
    goal, spec = race_goal(game), legacy.spec_for(game)
    panel(surface, (64, 286, 754, 513))
    draw_race_portrait(surface, game.race_id, (83, 307, 64, 81))
    text(surface, RACES[game.race_id].name.upper(), (165, 306), 11, GOLD, "mono")
    text(surface, shorten(goal.title, 620, 25, "title"), (165, 329), 25, INK, "title")
    text(surface, (f"{goal.current}% complete" if goal.unit == "%" else f"{goal.current} / {goal.total} routes") + (" · ENABLED" if enabled else " · DISABLED IN SETUP"), (165, 367), 12, CYAN if enabled else MUTED)
    paragraph(surface, spec.method if spec else goal.description, (86, 407), 710, 14, MUTED, 22)
    if spec:
        for i, requirement in enumerate(goal.requirements):
            y = 492+i*34
            text(surface, shorten(requirement.label, 560, 14), (86, y), 14, INK)
            text(surface, f"{requirement.current} / {requirement.target}", (794, y), 14, CYAN if requirement.complete else GOLD, right=True)
            progress(surface, (86, y+23, 708, 3), min(1, requirement.current/max(1, requirement.target)) if requirement.target else 1)
        text(surface, f"FINAL STAGE · {goal.final_turns}/{legacy.FINAL_TURNS} consecutive turns", (86, 681), 12, GOLD, "mono")
        progress(surface, (86, 708, 708, 5), goal.final_turns/legacy.FINAL_TURNS)
        worlds = colonies(game, "player")
        app.gate_colony_index = min(max(0, app.gate_colony_index), max(0, len(worlds)-1))
        if worlds:
            system, planet = worlds[app.gate_colony_index]
            text(surface, shorten(planet.name, 250, 14), (86, 734), 14, INK)
            site = next((s for s, p in legacy.sites(game, "player") if p is planet), None)
            status = (legacy.site_error(game, site, planet) or f"Operating · {site.age} turns") if site else "Manage installation in colony production"
            text(surface, shorten(status, 470, 12), (86, 763), 12, MUTED)
            app.button("legacy_previous", "←", (570, 738, 43, 38), lambda: app.change_gate_colony(-1), enabled=app.gate_colony_index > 0)
            app.button("legacy_next", "→", (620, 738, 43, 38), lambda: app.change_gate_colony(1), enabled=app.gate_colony_index < len(worlds)-1)
            app.button("legacy_colony", "Colony →", (670, 738, 124, 38), lambda: app.open_empire_colony(system.id, planet.id))
    else:
        progress(surface, (86, 516, 708, 7), goal.current/max(1, goal.total))
        from .motherships import homes
        home = next(iter(homes(game, "player")), None)
        app.button("objectives_hyperlanes", "Hyperlane research →", (86, 562, 330, 46), lambda: app.open_hyperlane(home.system_id if home else game.selected_system))
    panel(surface, (842, 286, 534, 513))
    text(surface, "EMPIRES YOU HAVE MET", (862, 307), 12, GOLD, "mono")
    rows = known_race_goals(game)
    for i, (owner, other) in enumerate(rows):
        y = 344+i*37
        active = bool(colonies(game, owner))
        label = game.empire_name_for(owner) if active else game.empire_name_for(owner)+" · Eliminated"
        text(surface, shorten(label, 360, 13), (862, y), 13, INK if active else MUTED)
        if other:
            text(surface, f"{other.current}%" if other.unit == "%" else f"{other.current}/{other.total} routes", (1356, y), 12, CYAN, right=True)
            text(surface, shorten(other.title, 486, 10), (862, y+17), 10, MUTED)
    if not rows:
        paragraph(surface, "Meet other civilizations to see their goals and aggregate progress.", (862, 352), 486, 16, MUTED, 26)
    text(surface, "Only known empires are shown. Hidden colony locations remain private.", (66, 806), 11, MUTED)
    app.button("objectives_pause", "Menu", (64, 834, 126, 45), app.pause)
    app.button("objectives_save", "Save · F5", (204, 834, 172, 45), app.save_game)
    app.button("objectives_end_turn", "End turn · E", (1081, 824, 295, 55), app.advance_turn, "primary")


def draw_objectives(app):
    surface, game = app.canvas, app.game
    app.chrome("CAMPAIGN OBJECTIVES")
    app.button("objectives_back", "← Back · V", (64, 124, 195, 46), app.close_objectives, "ghost")
    app.button("objectives_galaxy", "Galaxy map", (274, 124, 182, 46), lambda: app.go("galaxy"), "ghost")
    text(surface, f"YEAR {game.year} · TURN {game.turn}", (1376, 141), 12, GOLD, "mono", right=True)
    enabled = game.victory_conditions
    racial = app.objectives_tab == "race"
    text(surface, "Your civilization legacy" if racial else "Campaign victory conditions", (64, 190), 43, INK, "title")
    text(surface, "Enabled: "+" · ".join(CONDITION_NAMES[c] for c in enabled) if enabled else "Open-ended campaign · Losing every colony still ends your campaign.", (66, 251), 14, MUTED)
    app.button("objectives_race", "Standard goals →" if racial else "Your race objectives →", (1030, 192, 346, 45), lambda: setattr(app, "objectives_tab", "overview" if racial else "race"), "primary")
    if racial:
        draw_race_objectives(app)
        return
    own = len(colonies(game, "player"))
    entries = (
        ("conquest", "Conquest", f"Your empire controls {own} colonies.", "The last empire with inhabited colonies wins. Use fleets, bombardment and troop transports to defeat opposing empires."),
        ("council", "Galactic Council", "Win the galactic election.", "Build diplomatic support and population, then secure the council's vote. Rivals may reject the election and continue the conflict."),
        ("race", "Civilization legacy", race_goal(game).title, "Complete your civilization's unique goals. Open Your race objectives for exact requirements, live progress and known rivals."),
    )
    for i, (condition, title, subtitle, description) in enumerate(entries):
        x = 64+i*446
        panel(surface, (x, 286, 420, 420))
        text(surface, title.upper(), (x+23, 312), 13, GOLD, "mono")
        text(surface, "ON" if condition in enabled else "OFF", (x+395, 312), 12, CYAN if condition in enabled else MUTED, right=True)
        paragraph(surface, subtitle, (x+23, 362), 374, 25, INK, 34)
        paragraph(surface, description, (x+23, 470), 374, 17, MUTED, 27)
        if condition == "council":
            app.button("objectives_council", "Open council →", (x+23, 630, 374, 46), app.open_council, enabled=condition in enabled)
        elif condition == "race":
            app.button("objectives_details", "View your legacy →", (x+23, 630, 374, 46), lambda: setattr(app, "objectives_tab", "race"), "primary")
    text(surface, "Negative credits cost 10% interest per turn. Bankruptcy at -10,000 CR always ends your campaign.", (66, 753), 13, MUTED)
    app.button("objectives_pause", "Menu", (64, 834, 126, 45), app.pause)
    app.button("objectives_save", "Save · F5", (204, 834, 172, 45), app.save_game)
    app.button("objectives_end_turn", "End turn · E", (1081, 824, 295, 55), app.advance_turn, "primary")


def draw_result(app):
    surface, game = app.canvas, app.game
    result = game.result
    won, draw = result.winner == "player", result.winner is None and result.condition not in ("elimination", "bankruptcy")
    color = GOLD if won else CYAN if draw else RIVAL_COLOR
    if game.is_observer:
        color = GOLD
    app.chrome("CAMPAIGN COMPLETE")
    title = "A shared ascension" if draw and result.condition == "science" else "Draw" if draw else "Victory" if won else "Defeat"
    if game.is_observer:
        title = "A shared ascension" if draw and result.condition == "science" else "Campaign complete"
    text(surface, title, (92, 187), 66, color, "title")
    subtitle = "Bankruptcy" if result.condition == "bankruptcy" else "Race-specific victory" if result.condition == "race" else "Council victory" if result.condition == "council" else "Scientific victory" if result.condition == "science" else "Empire eliminated" if result.condition == "elimination" else "Conquest victory"
    text(surface, f"{subtitle.upper()}  /  YEAR {game.year}  /  TURN {result.turn}", (96, 280), 12, MUTED, "mono", 2)
    panel(surface, (92, 331, 1256, 225))
    if result.condition == "bankruptcy":
        message = (f"Your treasury has fallen to {game.credits:,} CR. At -10,000 CR or below, your empire "
                   "can no longer finance its obligations. The campaign ends in bankruptcy.")
    elif result.condition == "elimination":
        message = "Your final colony has fallen. Your empire has been eliminated; other civilizations still remain in the galaxy."
    elif draw:
        message = "Multiple empires completed the victory conditions together. The campaign ends in a draw."
    elif result.condition == "council":
        election = game.council.election
        message = (f"{game.empire_name_for(result.winner)} was elected Emperor of the Universe with "
                   f"{election.tally[result.winner]} of {election.total_votes} council votes. "
                   "The galaxy recognizes its new ruler.")
    elif result.condition == "science":
        message = f"{game.empire_name_for(result.winner)} completed the Ascension Gate and charged it for five clear-orbit turns. A new age begins."
    elif result.condition == "race":
        goal = race_goal(game, result.winner)
        from .race_victory import spec_for
        spec = spec_for(game, result.winner)
        message = (f"{game.empire_name_for(result.winner)} completed {goal.title}. "+spec.ending if spec else
                   f"{game.empire_name_for(result.winner)} discovered all {goal.total} forgotten hyperlanes. The Wanderers have restored their lost paths between the stars.")
    else:
        message = f"{game.empire_name_for(result.winner)} is the last empire with colonies. The campaign is complete."
    paragraph(surface, message, (122, 370), 870, 24, INK, 38)
    if result.condition == "science":
        gate_icon(surface, (1200, 441), 65, color)
    elif result.condition == "race":
        if result.winner is not None:
            draw_race_portrait(surface, game._empire(result.winner).race_id, (1125, 350, 150, 180))
    else:
        for radius in (74, 49, 24):
            pg.draw.circle(surface, color, (1200, 441), radius, 2)
        pg.draw.line(surface, color, (1109, 441), (1291, 441), 2)
        pg.draw.line(surface, color, (1200, 350), (1200, 532), 2)
    profiles = ("player", result.winner if result.winner in game.opponents else next(iter(game.opponents), "rival"))
    if game.is_observer:
        profiles = sorted(game.owners, key=lambda o: (o != result.winner, -len(colonies(game, o)), o))[:2]
    for i, owner in enumerate(profiles):
        if owner == "rival" and game.opponent is None:
            continue
        x = 92+i*641
        panel(surface, (x, 578, 615, 122))
        text(surface, game.empire_name_for(owner), (x+22, 594), 22, INK)
        population = sum(p.workforce for _, p in colonies(game, owner))
        count = len(colonies(game, owner))
        text(surface, f"{count} {'colony' if count == 1 else 'colonies'} · {population} B inhabitants · {len(game.ships_owned_by(owner))} ships", (x+23, 634), 14, MUTED)
        text(surface, f"{len(game.research_state(owner).completed)} technologies discovered", (x+23, 667), 12, CYAN)
    text(surface, "This campaign is complete. Save a final snapshot or start a new campaign.", (95, 739), 15, MUTED)
    app.button("result_save", "Save final snapshot", (92, 802, 291, 57), app.save_game)
    app.button("result_menu", "Main menu", (404, 802, 249, 57), app.to_menu)
    app.button("result_news", "Turn news · N", (674, 802, 291, 57), app.open_news)
    app.button("result_new", "New campaign →", (1016, 802, 332, 57), lambda: app.go("race_select"), "primary")
