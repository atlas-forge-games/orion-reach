"""Victory progress, gate construction and final campaign results."""

import math
import pygame as pg

from .production import ASCENSION_GATE, GATE_CHARGE_TURNS
from .research import TECHNOLOGIES
from .victory import colonies, gate_blocked, gate_site
from .exploration import known_rival_colonies
from .ui import CYAN, FAINT, GOLD, INK, LINE, MUTED, RIVAL_COLOR, panel, paragraph, shorten, text


def gate_icon(surface, center, radius=64, color=CYAN):
    x, y = center
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


def draw_objectives(app):
    surface, game = app.canvas, app.game
    state = game.technology
    app.chrome("CAMPAIGN OBJECTIVES")
    app.button("objectives_back", "← Back · V", (64, 124, 195, 46), app.close_objectives, "ghost")
    app.button("objectives_galaxy", "Galaxy map", (274, 124, 182, 46), lambda: app.go("galaxy"), "ghost")
    text(surface, f"YEAR {game.year} · TURN {game.turn}", (1376, 141), 12, GOLD, "mono", right=True)
    text(surface, "Two paths to victory", (64, 190), 43, INK, "title")
    text(surface, "Conquer your rival's colonies or lead your civilization through the Ascension Gate.", (66, 251), 14, MUTED)

    panel(surface, (64, 286, 623, 284))
    text(surface, "01 / CONQUEST", (88, 309), 11, GOLD, "mono", 2)
    own, rival = len(colonies(game, "player")), len(colonies(game, "rival"))
    conquest = (f"{len(known_rival_colonies(game))} known rival colonies" if game.fog_of_war else
                f"{rival} rival {'colony remains' if rival == 1 else 'colonies remain'}")
    text(surface, conquest if game.opponent else "No rival in this campaign",
         (87, 344), 29, INK, "title")
    text(surface, f"Your empire controls {own} {'colony' if own == 1 else 'colonies'}.", (89, 389), 14, CYAN)
    paragraph(surface, "Build troop transports, clear enemy ships from orbit, then invade from the planet overview. "
              "Each transport brings 8 attack; colonies defend with 4 + population. Attack must exceed defence.",
              (89, 424), 566, 14, MUTED, 23)
    text(surface, "Losing every colony ends an empire, even if its ships survive.", (89, 540), 12, GOLD)

    panel(surface, (709, 286, 667, 284))
    text(surface, "02 / SCIENCE", (733, 309), 11, GOLD, "mono", 2)
    text(surface, f"{state.finished_branches} / 8 branches completed", (732, 344), 29, INK, "title")
    text(surface, "Complete tier II in every branch. Either technology choice counts.", (734, 390), 13, MUTED)
    progress(surface, (734, 418, 616, 4), state.finished_branches/8)
    theory = TECHNOLOGIES["ascension_theory"]
    known = theory.id in state.completed
    active = state.active == theory.id
    caption = ("Ascension Theory discovered. Your gate is unlocked." if known else
               f"Ascension Theory: {state.progress} / {theory.cost} RP" if active else
               f"Next: Ascension Theory · {theory.cost} RP · uses your normal research output")
    text(surface, caption, (734, 444), 13, CYAN if known or active else MUTED)
    reason = game.research_error(theory.id)
    label = "Theory discovered" if known else "Researching theory" if active else "Research Ascension Theory"
    app.button("research_ascension", label, (733, 490, 331, 44),
               lambda: app.research_request(theory.id), enabled=reason is None)
    app.button("objectives_research", "Research tree →", (1080, 490, 270, 44), app.open_research)
    if state.active and not active:
        text(surface, "Finish your current research project first.", (734, 546), 11, MUTED)

    panel(surface, (64, 590, 1312, 209))
    gate_icon(surface, (146, 682), 43)
    site = gate_site(game)
    rows = sorted(colonies(game, "player"), key=lambda row: (-game.planet_yields(row[1])[0], row[0].id, row[1].id))
    app.gate_colony_index = min(max(0, app.gate_colony_index), max(0, len(rows)-1))
    selected = site or (rows[app.gate_colony_index] if rows else None)
    text(surface, "ASCENSION GATE", (223, 609), 11, GOLD, "mono", 2)
    if selected:
        system, planet = selected
        text(surface, shorten(f"{planet.name} · {system.name}", 760, 25, "title"), (222, 635), 25, INK, "title")
        if site:
            if planet.ascension_gate:
                blocked = gate_blocked(game, system.id, "player")
                caption = f"Charging {planet.gate_charge} / {GATE_CHARGE_TURNS} turns" + (" · Paused by opposing ships in orbit" if blocked else " · Orbit clear")
                text(surface, caption, (224, 678), 14, GOLD if blocked else CYAN)
                progress(surface, (224, 707, 776, 5), planet.gate_charge/GATE_CHARGE_TURNS)
                text(surface, "Capture destroys the gate. Charging resumes when opposing ships leave.", (224, 734), 12, MUTED)
            else:
                index, project = next((i, q) for i, q in enumerate(planet.construction_queue) if q.item_id == ASCENSION_GATE.id)
                eta = game.queue_estimates(planet)[index]
                text(surface, f"Under construction · {project.progress}/{ASCENSION_GATE.work_cost} work · Ready in {eta} turns", (224, 678), 14, CYAN)
                progress(surface, (224, 707, 776, 5), project.progress/ASCENSION_GATE.work_cost)
                text(surface, "Then charge for five clear-orbit turns. Manage or cancel this project in the Shipyard.", (224, 734), 12, MUTED)
            app.button("gate_visit", "Open gate colony →", (1054, 683, 296, 46),
                       lambda: app.open_empire_colony(system.id, planet.id))
        else:
            reason = game.gate_error(system.id, planet.id)
            eta = game.queue_estimates(planet, ASCENSION_GATE.id)[-1]
            text(surface, f"500 CR · 300 work · {eta} construction turns + 5 charging turns · No building slot", (224, 679), 13, CYAN)
            text(surface, shorten(reason or "One gate per empire. Opposing ships pause charging; capture destroys it.", 794, 12), (224, 710), 12, GOLD if reason else MUTED)
            text(surface, f"{game.credits:,} CR available · Select a colony using Previous / Next", (224, 745), 12, MUTED)
            app.button("gate_previous", "← Previous", (1054, 621, 143, 39), lambda: app.change_gate_colony(-1), enabled=app.gate_colony_index>0)
            app.button("gate_next", "Next →", (1211, 621, 139, 39), lambda: app.change_gate_colony(1), enabled=app.gate_colony_index<len(rows)-1)
            app.button("gate_build", "Build Ascension Gate", (1054, 683, 296, 46),
                       lambda: app.gate_request(system.id, planet.id), enabled=reason is None)

    app.button("objectives_pause", "Menu", (64, 834, 126, 45), app.pause)
    app.button("objectives_save", "Save · F5", (204, 834, 172, 45), app.save_game)
    if game.opponent:
        enemy_gate = gate_site(game, "rival")
        enemy = game.opponent.technology
        caption = f"Rival: {enemy.finished_branches}/8 branches · "
        if enemy_gate:
            caption += f"Gate at {enemy_gate[1].name}: " + (f"charging {enemy_gate[1].gate_charge}/5" if enemy_gate[1].ascension_gate else "under construction")
        else:
            caption += "Ascension Theory discovered" if "ascension_theory" in enemy.completed else "researching Ascension Theory" if enemy.active == "ascension_theory" else "no gate yet"
        if game.fog_of_war:
            sites = [(s, p) for s, p in known_rival_colonies(game) if p.ascension_gate or
                     any(q.item_id == ASCENSION_GATE.id for q in p.construction_queue)]
            caption = f"Last-known rival gate: {sites[0][1].name}" if sites else "Rival research and gate location are unknown. Explore to locate its worlds."
        text(surface, shorten(caption, 652, 12), (400, 835), 12, RIVAL_COLOR)
        text(surface, "The AI can win by either path. Both gates activating together is a draw.", (400, 857), 11, FAINT)
    app.button("objectives_end_turn", "End turn · E", (1081, 824, 295, 55), app.advance_turn, "primary")


def draw_result(app):
    surface, game = app.canvas, app.game
    result = game.result
    won, draw = result.winner == "player", result.winner is None
    color = GOLD if won else CYAN if draw else RIVAL_COLOR
    app.chrome("CAMPAIGN COMPLETE")
    title = "A shared ascension" if draw and result.condition == "science" else "Draw" if draw else "Victory" if won else "Defeat"
    text(surface, title, (92, 187), 66, color, "title")
    subtitle = "Scientific victory" if result.condition == "science" else "Conquest victory"
    text(surface, f"{subtitle.upper()}  /  YEAR {game.year}  /  TURN {result.turn}", (96, 280), 12, MUTED, "mono", 2)
    panel(surface, (92, 331, 1256, 225))
    if draw:
        message = "Both empires activated their Ascension Gates in the same turn. The campaign ends in a draw."
    elif result.condition == "science":
        message = f"{game.empire_name_for(result.winner)} completed the Ascension Gate and charged it for five clear-orbit turns. A new age begins."
    else:
        message = f"{game.empire_name_for(result.winner)} captured every opposing colony. The rival empire has fallen, and the campaign is complete."
    paragraph(surface, message, (122, 370), 870, 24, INK, 38)
    if result.condition == "science":
        gate_icon(surface, (1200, 441), 65, color)
    else:
        for radius in (74, 49, 24):
            pg.draw.circle(surface, color, (1200, 441), radius, 2)
        pg.draw.line(surface, color, (1109, 441), (1291, 441), 2)
        pg.draw.line(surface, color, (1200, 350), (1200, 532), 2)
    for i, owner in enumerate(("player", "rival")):
        if owner == "rival" and game.opponent is None:
            continue
        x = 92+i*641
        panel(surface, (x, 578, 615, 122))
        text(surface, game.empire_name_for(owner), (x+22, 594), 22, INK)
        population = sum(p.population for _, p in colonies(game, owner))
        count = len(colonies(game, owner))
        text(surface, f"{count} {'colony' if count == 1 else 'colonies'} · {population} B inhabitants · {len(game.ships_owned_by(owner))} ships", (x+23, 634), 14, MUTED)
        text(surface, f"{len(game.research_state(owner).completed)} technologies discovered", (x+23, 667), 12, CYAN)
    text(surface, "This campaign is complete. Save a final snapshot or start a new campaign.", (95, 739), 15, MUTED)
    app.button("result_save", "Save final snapshot", (92, 802, 291, 57), app.save_game)
    app.button("result_menu", "Main menu", (404, 802, 249, 57), app.to_menu)
    app.button("result_new", "New campaign →", (1016, 802, 332, 57), lambda: app.go("setup"), "primary")
