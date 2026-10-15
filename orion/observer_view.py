"""Read-only galaxy totals and computer empire reports for spectator campaigns."""

import pygame as pg

from .empire import summarize_empire
from .first_contact import known
from .fleets import group_fleets
from .galaxy_hud import RESOURCE_RECTS, draw_galaxy_commands
from .personalities import PERSONALITIES
from .race_art import draw_race_portrait
from .races import RACES, OBSERVER
from .research import TECHNOLOGIES
from .victory import CONDITION_NAMES, colonies, gate_site
from .ui import CYAN, GOLD, INK, LINE, MUTED, RED, panel, shorten, text

TABS = {"empires": "Empires", "diplomacy": "Diplomacy", "research": "Research",
        "fleets": "Fleets", "objectives": "Objectives"}
ROWS_PER_PAGE = 6


def draw_observer_header(app):
    game, surface = app.game, app.canvas
    worlds = [p for _, p in game.settlements()]
    alive = sum(bool(game.colony_systems(o)) for o in game.owners)
    draw_race_portrait(surface, "observer", (64, 22, 88, 100))
    text(surface, "THE", (165, 38), 11, MUTED, "mono", 2)
    text(surface, "OBSERVER", (165, 58), 14, INK, "mono")
    text(surface, "WATCHING", (165, 94), 9, CYAN, "mono", 1)
    stats = (("EMPIRES", str(alive), f"{len(game.owners)} civilizations recorded"),
             ("COLONIES", str(len(worlds)), "Across the whole galaxy"),
             ("POPULATION", f"{sum(p.workforce for p in worlds):,} B", "All inhabited worlds"),
             ("SHIPS", str(len(game.ships)), f"{sum(s.in_transit for s in game.ships)} in transit"),
             ("TECHNOLOGIES · R", str(sum(len(game.research_state(o).completed) for o in game.owners)),
              "View research reports"))
    for rect, (label, value, caption) in zip(RESOURCE_RECTS, stats):
        x, y, w, h = rect
        panel(surface, rect, (9, 20, 29))
        text(surface, label, (x+16, y+12), 10, GOLD, "mono", 1)
        text(surface, value, (x+15, y+34), 28, OBSERVER.color, "mono")
        text(surface, caption, (x+16, y+78), 10, MUTED)
    app.button("open_research", "", RESOURCE_RECTS[4], app.open_research, "hotspot")
    pg.draw.line(surface, LINE, (64, 129), (1376, 129))
    text(surface, shorten(game.empire_name, 590, 26, "title"), (64, 140), 26, INK, "title")
    text(surface, f"YEAR {game.year}   /   TURN {game.turn}", (718, 150), 12, CYAN, "mono")
    text(surface, "ALL EMPIRES UNDER COMPUTER CONTROL", (1376, 151), 10, MUTED, "mono", right=True)


def report_rows(app):
    """Columns and rows share one width definition to keep long names contained."""
    game, tab = app.game, app.observer_tab
    rows = []
    if tab == "diplomacy":
        columns = (("CIVILIZATION", 86, 295), ("OTHER CIVILIZATION", 395, 295),
                   ("CONTACT", 710, 150), ("RELATIONS", 880, 175), ("AGREEMENTS", 1075, 275))
        for i, first in enumerate(game.owners):
            for second in game.owners[i+1:]:
                state = game.diplomacy_between(first, second)
                contacted = known(game, first, second)
                active = bool(game.colony_systems(first) and game.colony_systems(second))
                pacts = (["Friendship"] if state.friendship_active else
                         [label for flag, label in ((state.trade_active, "Trade"), (state.non_aggression_active, "Non-aggression")) if flag])
                if state.research_active:
                    pacts.append("Research")
                if state.coalition_target:
                    pacts.append('Coalition vs '+game.empire_name_for(state.coalition_target))
                values = (game.empire_name_for(first), game.empire_name_for(second),
                          "Eliminated" if not active else "Established" if contacted else "No contact",
                          f"{state.attitude} {state.relations:+}" if contacted and active else "—",
                          " + ".join(pacts) or "None")
                rows.append((values, "Computer empires discover and negotiate with each other independently.",
                             RED if state.relations < -30 and active else MUTED, None))
    elif tab == "fleets":
        columns = (("CIVILIZATION", 86, 295), ("SHIPS", 395, 80), ("LOCATION / ORIGIN", 495, 275),
                   ("DESTINATION", 790, 285), ("ARRIVAL", 1095, 255))
        for ships in group_fleets(game.ships):
            first = ships[0]
            values = (game.empire_name_for(first.owner), str(len(ships)), game.systems[first.system_id].name,
                      game.systems[first.destination].name if first.has_course else "In orbit",
                      f"{first.turns_remaining} turns" if first.has_course else "—")
            detail = " · ".join(f"{sum(s.kind == k for s in ships)} {next(s for s in ships if s.kind == k).name.rsplit(' ', 1)[0]}"
                                for k in dict.fromkeys(s.kind for s in ships))
            rows.append((values, detail, app.empire_color(first.owner),
                         lambda sid=first.id: app.open_map_fleet(sid)))
    else:
        columns = {
            "empires": (("CIVILIZATION", 86, 285), ("COLONIES", 390, 85), ("POPULATION", 495, 110),
                        ("CREDITS", 625, 150), ("RESOURCES", 795, 145), ("IND / TURN", 960, 105),
                        ("RP / TURN", 1085, 105), ("SHIPS", 1210, 140)),
            "research": (("CIVILIZATION", 86, 285), ("DISCOVERED", 390, 120), ("BANKED RP", 530, 130),
                         ("RP / TURN", 680, 130), ("ACTIVE PROJECT", 830, 300), ("PROGRESS", 1150, 200)),
            "objectives": (("CIVILIZATION", 86, 285), ("STATUS", 390, 140), ("COLONIES", 550, 120),
                           ("BRANCHES", 690, 125), ("ASCENSION GATE", 835, 305), ("CHARGE", 1160, 190)),
        }[tab]
        for owner, empire in game.opponents.items():
            summary = summarize_empire(game, owner=owner)
            state, color = empire.technology, app.empire_color(owner)
            if tab == "empires":
                values = (empire.name, str(summary.colonies), f"{summary.population} B", f"{empire.credits:,}",
                          f"{empire.resources:,}", str(summary.industry), str(summary.research), str(len(game.ships_owned_by(owner))))
                detail = (f"{RACES[empire.race_id].name} · {PERSONALITIES[empire.race_id].traits} · "
                          f"{summary.income:+} CR/turn · {summary.resources:+} RES/turn · Click to inspect") if summary.colonies else "Eliminated"
            elif tab == "research":
                project = TECHNOLOGIES[state.active] if state.active else None
                values = (empire.name, str(len(state.completed)), f"{empire.research:,}", str(summary.research),
                          project.name if project else "Banking research", f"{state.progress}/{project.cost} RP" if project else "—")
                recent = ", ".join(TECHNOLOGIES[t].name for t in state.completed[-3:])
                detail = f"{state.finished_branches}/{len(state.required_branches)} branches complete · Recent: {recent or 'No discoveries yet'}"
            else:
                site = gate_site(game, owner)
                values = (empire.name, "Active" if summary.colonies else "Eliminated", str(summary.colonies),
                          f"{state.finished_branches}/{len(state.required_branches)}",
                          site[1].name if site else "Not built", f"{site[1].gate_charge}/5" if site and site[1].ascension_gate else "Building" if site else "—")
                detail = "Ascension Theory discovered" if "ascension_theory" in state.completed else "Complete every research branch, discover Ascension Theory, then build and charge a gate."
                if "science" not in game.victory_conditions:
                    values = (*values[:4], "Disabled", "—")
                    detail = "Science victory is disabled for every empire in this campaign."
            rows.append((values, detail, color, lambda oid=owner: app.open_observed_empire(oid)))
    return columns, rows


def draw_observer(app):
    game, surface = app.game, app.canvas
    draw_race_portrait(surface, "observer", (64, 28, 58, 58))
    text(surface, "ORION REACH", (140, 35), 20, INK, spacing=2)
    text(surface, "OBSERVER · READ-ONLY REPORTS", (142, 69), 11, MUTED, "mono", 1)
    text(surface, "EVERY EMPIRE. EVERY DECISION.", (1376, 56), 11, OBSERVER.color, "mono", right=True)
    pg.draw.line(surface, LINE, (64, 107), (1376, 107))
    app.button("observer_back", "← Galaxy map · Esc", (64, 124, 270, 46), lambda: app.go("galaxy"), "ghost")
    app.button("open_research", "Research · R", (354, 124, 190, 46), app.open_research, "ghost")
    app.button("observer_statistics", "Statistics", (564, 124, 185, 46), app.open_statistics)
    text(surface, f"YEAR {game.year} · TURN {game.turn}", (1376, 141), 12, GOLD, "mono", right=True)
    text(surface, f"Galaxy {TABS[app.observer_tab].lower()}", (64, 188), 40, INK, "title")
    text(surface, "Every civilization makes its own decisions. You observe the consequences.", (66, 245), 15, MUTED)
    columns, rows = report_rows(app)
    for label, x, width in columns:
        text(surface, label, (x, 287), 10, GOLD, "mono")
    last = max(0, (len(rows)-1)//ROWS_PER_PAGE)
    app.observer_page = min(max(0, app.observer_page), last)
    start = app.observer_page*ROWS_PER_PAGE
    for index, (values, detail, color, action) in enumerate(rows[start:start+ROWS_PER_PAGE]):
        y = 313+index*63
        rect = (64, y, 1312, 56)
        button = app.button(f"observer_row_{start+index}", "", rect, action, "hotspot") if action else None
        panel(surface, rect, (22, 38, 48) if button and app.is_active(button) else (9, 22, 31), color if button and app.is_active(button) else LINE)
        for value, (_, x, width) in zip(values, columns):
            text(surface, shorten(value, width, 15), (x, y+9), 15, color if x == 86 else INK)
        text(surface, shorten(detail, 1248, 11), (86, y+35), 11, MUTED)
    if not rows:
        text(surface, "No fleets remain.", (86, 340), 25, INK, "title")
    text(surface, f"PAGE {app.observer_page+1} / {last+1} · {len(rows)} RECORDS", (86, 713), 11, MUTED, "mono")
    app.button("observer_previous", "← Prev", (1081, 704, 139, 36), lambda: app.change_observer_page(-1), enabled=app.observer_page>0)
    app.button("observer_next", "Next →", (1233, 704, 143, 36), lambda: app.change_observer_page(1), enabled=app.observer_page<last)
    if app.observer_tab == "objectives":
        app.button("observer_council", "Galactic Council →", (1081, 753, 295, 39), app.open_council,
                   enabled="council" in game.victory_conditions)
    victories = "Enabled victories: "+" · ".join(CONDITION_NAMES[c] for c in game.victory_conditions) if game.victory_conditions else "Open-ended observation: no victory conditions are enabled."
    note = (victories if app.observer_tab == "objectives" else
            "Click a fleet to inspect its ships and route." if app.observer_tab == "fleets" else
            "The Observer has no diplomatic relationships and cannot affect negotiations." if app.observer_tab == "diplomacy" else
            "Click an empire to inspect its economy, colonies and recent activity.")
    text(surface, note, (66, 766), 13, CYAN)
    draw_galaxy_commands(app)
