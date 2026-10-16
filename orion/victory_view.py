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
    game, surface = app.game, app.canvas
    enabled = "race" in game.victory_conditions
    goal = race_goal(game)
    panel(surface, (64, 286, 1312, 154))
    draw_race_portrait(surface, game.race_id, (88, 310, 82, 104))
    text(surface, RACES[game.race_id].name.upper(), (190, 307), 12, GOLD, "mono")
    text(surface, goal.title if goal else "No race-specific goal defined yet", (190, 334), 26, INK, "title")
    paragraph(surface, goal.description if goal else
              "Race victories currently have a Wanderer goal. Other civilizations can pursue the enabled standard victories.",
              (192, 377), 866, 14, MUTED, 22)
    if goal:
        text(surface, f"{goal.current} / {goal.total} routes", (1110, 309), 23, CYAN)
        progress(surface, (1110, 349, 242, 5), goal.current/max(1, goal.total))
        text(surface, "VICTORY ENABLED" if enabled else "DISABLED IN SETUP", (1110, 369), 10, GOLD, "mono")
        from .motherships import homes
        home = next(iter(homes(game, "player")), None)
        app.button("objectives_hyperlanes", "Hyperlane research →", (1110, 397, 242, 31),
                   lambda: app.open_hyperlane(home.system_id if home else game.selected_system))
    else:
        text(surface, "ON" if enabled else "OFF", (1352, 317), 18, CYAN if enabled else MUTED, right=True)
    text(surface, "EMPIRES YOU HAVE MET", (64, 462), 12, GOLD, "mono", 1)
    text(surface, "VICTORY PROGRESS" if enabled else "PROGRESS TRACKED · RACE VICTORY DISABLED", (1376, 462), 11, MUTED, right=True)
    rows = known_race_goals(game)
    for i, (owner, other) in enumerate(rows):
        y = 494+i*60
        race = RACES[game._empire(owner).race_id]
        panel(surface, (64, y, 1312, 54))
        draw_race_portrait(surface, race.id, (76, y+5, 44, 44))
        text(surface, shorten(game.empire_name_for(owner), 260, 16), (136, y+7), 16, INK)
        active = bool(colonies(game, owner))
        text(surface, "Active empire" if active else "Eliminated", (137, y+33), 10, CYAN if active else MUTED)
        text(surface, race.name, (415, y+18), 15, GOLD)
        text(surface, other.title if other else "No race-specific goal defined yet", (590, y+17), 14, INK if other else MUTED)
        if other:
            text(surface, f"{other.current} / {other.total} routes", (1086, y+8), 15, CYAN)
            text(surface, f"{100*other.current/max(1,other.total):.0f}%", (1352, y+8), 15, CYAN, right=True)
            progress(surface, (1086, y+38, 266, 4), other.current/max(1,other.total))
        else:
            text(surface, "—", (1352, y+17), 15, MUTED, right=True)
    if not rows:
        paragraph(surface, "Meet other empires to see their race goals and progress here.", (88, 523), 1200, 22, MUTED, 30)
    text(surface, "Progress is shared after contact. Hidden route locations and destinations stay private.", (66, 801), 12, MUTED)
    app.button("objectives_pause", "Menu", (64, 834, 126, 45), app.pause)
    app.button("objectives_save", "Save · F5", (204, 834, 172, 45), app.save_game)
    app.button("objectives_end_turn", "End turn · E", (1081, 824, 295, 55), app.advance_turn, "primary")


def draw_objectives(app):
    surface, game = app.canvas, app.game
    state = game.technology
    app.chrome("CAMPAIGN OBJECTIVES")
    app.button("objectives_back", "← Back · V", (64, 124, 195, 46), app.close_objectives, "ghost")
    app.button("objectives_galaxy", "Galaxy map", (274, 124, 182, 46), lambda: app.go("galaxy"), "ghost")
    text(surface, f"YEAR {game.year} · TURN {game.turn}", (1376, 141), 12, GOLD, "mono", right=True)
    enabled = game.victory_conditions
    racial = app.objectives_tab == "race"
    text(surface, "Race-specific victory" if racial else "Campaign victory conditions" if enabled else "An open-ended galaxy", (64, 190), 43, INK, "title")
    text(surface, "Enabled: "+" · ".join(CONDITION_NAMES[c] for c in enabled) if enabled else
         "No victory limit. Losing all your colonies still ends your campaign.", (66, 251), 14, MUTED)
    app.button("objectives_race", "Standard goals →" if racial else "Race-specific goals →", (1030, 192, 346, 45),
               lambda: setattr(app, "objectives_tab", "overview" if racial else "race"), "primary" if racial else "normal")
    goal = race_goal(game)
    caption = ("Race victory disabled in setup" if "race" not in enabled else
               f"Your progress: {goal.current} / {goal.total} hyperlanes" if goal else "View goals and progress of known empires")
    text(surface, caption, (1376, 251), 12, CYAN if "race" in enabled else MUTED, right=True)
    if racial:
        draw_race_objectives(app)
        return

    panel(surface, (64, 286, 410, 284))
    text(surface, "01 / CONQUEST", (88, 309), 11, GOLD, "mono", 2)
    text(surface, "ON" if "conquest" in enabled else "OFF", (449, 309), 11, CYAN if "conquest" in enabled else MUTED, right=True)
    own, rival = len(colonies(game, "player")), sum(len(colonies(game, owner)) for owner in game.opponents)
    conquest = (f"{len(known_rival_colonies(game))} known rival colonies" if game.fog_of_war else
                f"{rival} rival colonies remain")
    text(surface, "Disabled in setup" if "conquest" not in enabled else conquest if game.opponent else "No rival in this campaign",
         (87, 344), 23, INK, "title")
    text(surface, f"Your empire controls {own} colonies.", (89, 384), 13, CYAN)
    paragraph(surface, "Build troop transports, clear enemy ships and defenses from orbit, then invade. "
              "The last empire with colonies wins." if "conquest" in enabled else
              "Invasions and elimination still work. Defeating the last rival does not automatically end this campaign.",
              (89, 421), 360, 14, MUTED, 23)
    paragraph(surface, "Losing every colony eliminates an empire, even if its ships survive.",
              (89, 515), 360, 12, GOLD, 18)

    panel(surface, (486, 286, 450, 284))
    text(surface, "02 / SCIENCE", (510, 309), 11, GOLD, "mono", 2)
    text(surface, "ON" if "science" in enabled else "OFF", (911, 309), 11, CYAN if "science" in enabled else MUTED, right=True)
    text(surface, f"{state.finished_branches} / {len(state.required_branches)} branches completed" if "science" in enabled else
         "Disabled in setup", (509, 344), 23, INK, "title")
    goal = ("Research other technologies as usual. Ascension Theory and the Ascension Gate are unavailable." if "science" not in enabled else
            "Original campaign goal retained; later expansion tiers are optional." if state.legacy_arsenal or state.legacy_fuel else
            f"Complete every tier in all {len(state.required_branches)} required branches. Either choice counts.")
    paragraph(surface, goal, (511, 383), 397, 12, MUTED, 18)
    if "science" in enabled:
        progress(surface, (511, 428, 397, 4), state.finished_branches/len(state.required_branches))
    theory = TECHNOLOGIES["ascension_theory"]
    known = theory.id in state.completed
    active = state.active == theory.id
    caption = ("Fleet, economic and defense research remain available." if "science" not in enabled else
               "Ascension Theory discovered. Gate unlocked." if known else
               f"Ascension Theory: {state.progress:,} / {theory.cost:,} RP" if active else
               f"Ascension Theory costs {theory.cost:,} RP.")
    text(surface, caption, (511, 451), 13, CYAN if known or active else MUTED)
    reason = game.research_error(theory.id)
    label = "Science victory disabled" if "science" not in enabled else "Theory discovered" if known else "Researching theory" if active else "Research Ascension Theory"
    app.button("research_ascension", label, (510, 490, 264, 44),
               lambda: app.research_request(theory.id), enabled=reason is None)
    app.technology_info_region(theory.id, (510, 444, 400, 35))
    app.technology_info_region(theory.id, (510, 490, 264, 44))
    app.button("objectives_research", "Research →", (785, 490, 128, 44), app.open_research)
    if state.active and not active:
        text(surface, "Switching research transfers all invested RP.", (511, 546), 11, MUTED)

    panel(surface, (948, 286, 428, 284))
    text(surface, "03 / GALACTIC COUNCIL", (972, 309), 11, GOLD, "mono", 2)
    text(surface, "ON" if "council" in enabled else "OFF", (1351, 309), 11, CYAN if "council" in enabled else MUTED, right=True)
    text(surface, "Emperor of the Universe" if "council" in enabled else "Disabled in setup", (971, 344), 23, INK, "title")
    paragraph(surface, "One colonized world gives one vote. Half of all votes, with a unique lead, elects the emperor. "
              "Unsuccessful elections repeat every 50 turns." if "council" in enabled else
              "No council is formed and no elections are called. Diplomacy, treaties and first contact remain available.",
              (973, 384), 378, 13, MUTED, 20)
    paragraph(surface, council_summary(game), (973, 452), 378, 12, CYAN, 17)
    app.button("objectives_council", "View Galactic Council →", (972, 490, 380, 44), app.open_council, enabled="council" in enabled)
    if "council" in enabled:
        text(surface, "You can defy a foreign emperor and face war.", (973, 546), 11, GOLD)

    panel(surface, (64, 590, 1312, 209))
    gate_icon(surface, (146, 682), 43)
    site = gate_site(game)
    rows = sorted(colonies(game, "player"), key=lambda row: (-game.planet_yields(row[1])[0], row[0].id, row[1].id))
    app.gate_colony_index = min(max(0, app.gate_colony_index), max(0, len(rows)-1))
    selected = site or (rows[app.gate_colony_index] if rows else None)
    text(surface, "ASCENSION GATE", (223, 609), 11, GOLD, "mono", 2)
    if "science" not in enabled:
        text(surface, "Science victory is disabled", (222, 646), 27, INK, "title")
        paragraph(surface, "Ascension research, gate construction and charging are disabled for every empire. "
                  "Victory conditions are chosen when starting a new expedition.", (224, 700), 1060, 16, MUTED, 25)
    elif selected:
        system, planet = selected
        text(surface, shorten(f"{planet.name} · {system.name}", 760, 25, "title"), (222, 635), 25, INK, "title")
        if site:
            if planet.ascension_gate:
                blocked = gate_blocked(game, system.id, "player")
                powered = game.planet_energy(planet).gate_powered
                caption = f"Charging {planet.gate_charge} / {production_balance.GATE_CHARGE_TURNS} turns" + (" · Paused: needs 10 energy" if not powered else " · Paused by opposing ships in orbit" if blocked else " · Powered, orbit clear")
                text(surface, caption, (224, 678), 14, GOLD if blocked or not powered else CYAN)
                progress(surface, (224, 707, 776, 5), planet.gate_charge/production_balance.GATE_CHARGE_TURNS)
                text(surface, "Charging requires 10 local energy and clear orbit. Capture destroys the gate.", (224, 734), 12, MUTED)
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
            text(surface, f"500 RES · 300 work · 10 energy/turn · {eta} turns to build + 5 to charge", (224, 679), 13, CYAN)
            text(surface, shorten(reason or "One gate per empire. Opposing ships pause charging; capture destroys it.", 794, 12), (224, 710), 12, GOLD if reason else MUTED)
            text(surface, f"{game.resources:,} Resources available · Select a colony using Previous / Next", (224, 745), 12, MUTED)
            app.button("gate_previous", "← Previous", (1054, 621, 143, 39), lambda: app.change_gate_colony(-1), enabled=app.gate_colony_index>0)
            app.button("gate_next", "Next →", (1211, 621, 139, 39), lambda: app.change_gate_colony(1), enabled=app.gate_colony_index<len(rows)-1)
            app.button("gate_build", "Build Ascension Gate", (1054, 683, 296, 46),
                       lambda: app.gate_request(system.id, planet.id), enabled=reason is None)

    app.button("objectives_pause", "Menu", (64, 834, 126, 45), app.pause)
    app.button("objectives_save", "Save · F5", (204, 834, 172, 45), app.save_game)
    if game.opponent and "science" in enabled:
        if game.fog_of_war:
            sites = [(s, p) for s, p in known_rival_colonies(game) if p.ascension_gate or
                     any(q.item_id == ASCENSION_GATE.id for q in p.construction_queue)]
            caption = f"Last-known rival gate: {sites[0][1].name}" if sites else "Rival research and gate location are unknown. Explore to locate its worlds."
        else:
            selected = app.selected_rival_id()
            enemy_gate = gate_site(game, selected)
            enemy = game._empire(selected).technology
            caption = f"{game.empire_name_for(selected)}: {enemy.finished_branches}/{len(enemy.required_branches)} branches · "
            if enemy_gate:
                caption += f"Gate at {enemy_gate[1].name}: " + (f"charging {enemy_gate[1].gate_charge}/5" if enemy_gate[1].ascension_gate else "under construction")
            else:
                caption += "Ascension Theory discovered" if "ascension_theory" in enemy.completed else "researching Ascension Theory" if enemy.active == "ascension_theory" else "no gate yet"
        text(surface, shorten(caption, 652, 12), (400, 835), 12, RIVAL_COLOR)
        text(surface, "Every rival can win. Gates activating together share a scientific victory.", (400, 857), 11, FAINT)
    app.button("objectives_end_turn", "End turn · E", (1081, 824, 295, 55), app.advance_turn, "primary")


def draw_result(app):
    surface, game = app.canvas, app.game
    result = game.result
    won, draw = result.winner == "player", result.winner is None and result.condition != "elimination"
    color = GOLD if won else CYAN if draw else RIVAL_COLOR
    if game.is_observer:
        color = GOLD
    app.chrome("CAMPAIGN COMPLETE")
    title = "A shared ascension" if draw and result.condition == "science" else "Draw" if draw else "Victory" if won else "Defeat"
    if game.is_observer:
        title = "A shared ascension" if draw and result.condition == "science" else "Campaign complete"
    text(surface, title, (92, 187), 66, color, "title")
    subtitle = "Race-specific victory" if result.condition == "race" else "Council victory" if result.condition == "council" else "Scientific victory" if result.condition == "science" else "Empire eliminated" if result.condition == "elimination" else "Conquest victory"
    text(surface, f"{subtitle.upper()}  /  YEAR {game.year}  /  TURN {result.turn}", (96, 280), 12, MUTED, "mono", 2)
    panel(surface, (92, 331, 1256, 225))
    if result.condition == "elimination":
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
        message = (f"{game.empire_name_for(result.winner)} discovered all {goal.total} forgotten hyperlanes. "
                   "The Wanderers have restored their lost paths between the stars.")
    else:
        message = f"{game.empire_name_for(result.winner)} is the last empire with colonies. The campaign is complete."
    paragraph(surface, message, (122, 370), 870, 24, INK, 38)
    if result.condition == "science":
        gate_icon(surface, (1200, 441), 65, color)
    elif result.condition == "race":
        from .hyperlane_art import draw_portal
        draw_portal(surface, (1200, 441), 80, True)
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
