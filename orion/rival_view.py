"""A read-only view of the rival economy, colonies and recent decisions."""

from .empire import colony_rows, summarize_empire
from .model import RIVAL
from .production import PROJECTS
from .races import RACES
from .research import TECHNOLOGIES
from .ui import FAINT, GOLD, INK, MUTED, RIVAL_COLOR, panel, paragraph, shorten, text


def draw_rival(app):
    surface, game = app.canvas, app.game
    app.chrome("RIVAL INTELLIGENCE")
    back_name = {"diplomacy": "Diplomacy", "planet": "Planet overview"}.get(app.rival_return, "Empire overview")
    app.button("rival_back", f"←  {back_name}", (64, 124, 269, 46), lambda: app.go(app.rival_return), "ghost")
    app.button("rival_galaxy", "Galaxy map", (349, 124, 172, 46), lambda: app.go("galaxy"), "ghost")
    app.button("rival_diplomacy", "Diplomacy · D", (537, 124, 226, 46), app.open_diplomacy)
    text(surface, f"YEAR {game.year} · TURN {game.turn}", (1376, 141), 12, GOLD, "mono", right=True)
    rival = game.opponent
    text(surface, rival.name if rival else "A rival on the horizon", (64, 190), 43, INK, "title")
    race_name = RACES[rival.race_id].name.upper() if rival else "AI EMPIRE"
    text(surface, f"{race_name}  /  EXPANSION & DEVELOPMENT", (66, 255), 11, RIVAL_COLOR, "mono", 1)
    if rival is None:
        panel(surface, (64, 309, 1312, 439))
        text(surface, "This campaign has no rival yet.", (94, 343), 29, INK, "title")
        paragraph(surface, "Add the Helios Directorate to an unclaimed habitable world far from your colonies. "
                  "It starts with one homeworld, 8 B inhabitants and 120 credits, and makes its first decisions when you end the turn.",
                  (96, 407), 1112, 19, MUTED, 32)
        paragraph(surface, "The rival builds its own economy and races you to settle worlds. "
                  "Its colonies and ships appear in orange. Diplomacy opens when contact is established.",
                  (96, 539), 1112, 16, MUTED, 28)
        reason = game.opponent_start_error()
        app.button("add_rival", "Add rival", (95, 663, 283, 52), app.add_rival, "primary", enabled=reason is None)
        home = game.opponent_home()
        caption = reason or f"Starting world: {home[1].name} · {home[0].name} system"
        text(surface, shorten(caption, 928, 14), (405, 683), 14, RIVAL_COLOR)
    else:
        summary = summarize_empire(game, owner=RIVAL)
        ships = game.ships_owned_by(RIVAL)
        stats = [
            ("COLONIES", str(summary.colonies), f"{summary.population} B inhabitants"),
            ("TREASURY", f"{rival.credits:,} CR", f"+{summary.income} CR / turn"),
            ("TOTAL INDUSTRY", f"{summary.industry} IND", "Per turn · used locally"),
            ("RESEARCH STORED", f"{rival.research:,} RP", f"+{summary.research} RP / turn"),
            ("COLONY SHIPS", str(len(ships)), f"{sum(s.in_transit for s in ships)} travelling"),
        ]
        for i, (label, value, caption) in enumerate(stats):
            x = 64+i*267
            panel(surface, (x, 291, 244, 92))
            text(surface, label, (x+17, 304), 9, MUTED, "mono", 1)
            text(surface, value, (x+17, 325), 24, RIVAL_COLOR)
            text(surface, caption, (x+17, 360), 11, MUTED)

        panel(surface, (64, 407, 739, 371))
        text(surface, "RECENT ACTIVITY", (87, 427), 11, GOLD, "mono", 2)
        for i, event in enumerate(reversed(rival.events[-6:])):
            y = 472+i*47
            text(surface, f"T{event.turn:03}", (88, y), 11, RIVAL_COLOR, "mono")
            text(surface, shorten(event.message, 616, 13), (157, y-1), 13, INK)
        text(surface, "Acts on End Turn · Same costs, industry and travel rules", (88, 751), 11, MUTED)

        panel(surface, (827, 407, 549, 371))
        rows = colony_rows(game, owner=RIVAL)
        last = max(0, (len(rows)-1)//5)
        app.rival_page = min(max(0, app.rival_page), last)
        text(surface, "RIVAL COLONIES", (849, 427), 11, GOLD, "mono", 2)
        for i, (system, planet) in enumerate(rows[app.rival_page*5:app.rival_page*5+5]):
            y = 464+i*50
            name = planet.name + (" · Home" if (system.id, planet.id) == (rival.home_system, rival.home_planet) else "")
            text(surface, shorten(name, 349, 15), (849, y), 15, INK)
            project = PROJECTS[planet.construction_queue[0].item_id].name if planet.construction_queue else "Idle"
            text(surface, f"{len(planet.buildings)} buildings · {project}", (850, y+24), 11, MUTED)
            app.button(f"rival_colony_{system.id}_{planet.id}", "Survey", (1228, y, 126, 37),
                       lambda sid=system.id, pid=planet.id: app.survey_rival_colony(sid, pid))
        text(surface, f"{app.rival_page+1} / {last+1}", (850, 750), 11, FAINT, "mono")
        app.button("rival_previous", "← Prev", (1090, 730, 126, 34), lambda: app.change_rival_page(-1), enabled=app.rival_page>0)
        app.button("rival_next", "Next →", (1228, 730, 126, 34), lambda: app.change_rival_page(1), enabled=app.rival_page<last)
        text(surface, "Race to settle unclaimed worlds. Rival colonies can be surveyed; they cannot be managed or captured.",
             (65, 798), 13, MUTED)
    app.button("rival_pause", "Menu", (64, 834, 126, 45), app.pause)
    app.button("rival_save", "Save · F5", (204, 834, 172, 45), app.save_game)
    if rival:
        state = rival.technology
        project = TECHNOLOGIES[state.active] if state.active else None
        caption = f"Research: {project.name} · {state.progress}/{project.cost} RP" if project else "Research points are being banked."
        text(surface, shorten(caption, 650, 12), (400, 835), 12, MUTED)
        text(surface, f"{len(state.completed)} technologies discovered · Same research rules as your empire", (400, 857), 11, FAINT)
    else:
        text(surface, "Income includes agreements · Open Diplomacy to negotiate", (400, 848), 12, MUTED)
    app.button("rival_end_turn", "End turn · E", (1081, 834, 295, 45), app.advance_turn, "primary")
