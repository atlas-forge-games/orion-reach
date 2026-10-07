"""Eight branches, two tiers and visible mutually exclusive technology choices."""

import math
import pygame as pg

from .research import BRANCHES, TECHNOLOGIES, choices
from .ui import CYAN, FAINT, GOLD, INK, LINE, MUTED, PANEL, panel, paragraph, shorten, text


def draw_research(app):
    surface, game = app.canvas, app.game
    state = game.technology
    rate = game.empire_rates[1]
    branch = BRANCHES[app.research_branch]
    app.chrome("RESEARCH DIRECTORATE")
    app.button("research_back", "← Back · R", (64, 124, 195, 46), app.close_research, "ghost")
    text(surface, f"YEAR {game.year} · TURN {game.turn}", (1376, 141), 12, GOLD, "mono", right=True)
    text(surface, "Research & discovery", (64, 190), 43, INK, "title")
    text(surface, "Choose your empire's path. One technology per tier, one project at a time.",
         (66, 251), 14, MUTED)

    panel(surface, (64, 284, 1312, 113))
    text(surface, "CURRENT PROJECT", (85, 298), 9, MUTED, "mono", 1)
    if state.active:
        active = TECHNOLOGIES[state.active]
        text(surface, active.name, (85, 317), 23, INK)
        remaining = active.cost-state.progress
        turns = math.ceil(remaining/rate) if rate else None
        eta = f"{turns} {'turn' if turns == 1 else 'turns'} at current output" if rate else "Build a research lab to make progress"
        text(surface, f"{state.progress} / {active.cost} RP · {eta}", (86, 352), 12, CYAN if rate else GOLD)
        pg.draw.rect(surface, LINE, (86, 379, 624, 4))
        pg.draw.rect(surface, CYAN, (86, 379, round(624*state.progress/active.cost), 4))
        app.button("research_show_active", "View", (740, 326, 100, 40),
                   lambda: app.select_research_branch(active.branch))
    else:
        done = len(state.completed) == 16
        text(surface, "Research programme complete" if done else "Choose a technology below", (85, 321), 23, INK)
        caption = (f"Latest discovery: {TECHNOLOGIES[state.completed[-1]].name}." if state.completed else
                   "Build a research lab on a colony to generate research points.")
        text(surface, caption, (86, 361), 12, MUTED)
    for x, label, value, caption in (
        (885, "RESEARCH OUTPUT", f"+{rate} RP", "per turn"),
        (1082, "BANKED POINTS", f"{game.research:,} RP", "applied when you choose"),
    ):
        pg.draw.line(surface, LINE, (x-22, 307), (x-22, 378))
        text(surface, label, (x, 303), 9, MUTED, "mono", 1)
        text(surface, value, (x, 327), 25, CYAN)
        text(surface, caption, (x, 365), 11, MUTED)

    for index, item in enumerate(BRANCHES.values()):
        y = 419+index*49
        selected = item.id == branch.id
        panel(surface, (64, y, 318, 43), (21, 38, 47) if selected else PANEL, GOLD if selected else LINE)
        if selected:
            pg.draw.rect(surface, GOLD, (64, y, 3, 43))
        count = sum(TECHNOLOGIES[t].branch == item.id for t in state.completed)
        text(surface, f"{index+1:02}", (79, y+13), 10, GOLD if selected else FAINT, "mono")
        text(surface, item.name, (110, y+10), 15, INK if selected else MUTED)
        text(surface, f"{count}/2", (365, y+13), 10, CYAN if count else FAINT, "mono", right=True)
        app.button(f"research_branch_{item.id}", "", (64, y, 318, 43),
                   lambda identifier=item.id: app.select_research_branch(identifier), "hotspot")

    text(surface, branch.name, (408, 414), 25, INK, "title")
    text(surface, branch.description, (409, 452), 13, MUTED)
    for tier in (1, 2):
        y = 502+(tier-1)*174
        options = choices(branch.id, tier)
        text(surface, f"TIER {'I' if tier == 1 else 'II'}  /  CHOOSE ONE", (409, y-25), 10, GOLD, "mono", 1)
        text(surface, f"{options[0].cost} RP", (1375, y-25), 11, CYAN, "mono", right=True)
        for index, technology in enumerate(options):
            x = 408+index*496
            status = state.status(technology.id)
            color = CYAN if status == "discovered" else GOLD if status == "active" else LINE
            panel(surface, (x, y, 472, 126), (14, 29, 38) if status in ("active", "discovered") else PANEL, color)
            text(surface, technology.name, (x+18, y+11), 19, MUTED if status == "excluded" else INK)
            paragraph(surface, technology.description, (x+19, y+41), 434, 13, MUTED, 19)
            label = {"discovered": "Discovered", "active": "Researching", "excluded": "Not chosen",
                     "locked": "Tier I required", "available": "Project active" if state.active else "Choose technology"}[status]
            reason = game.research_error(technology.id)
            app.button(f"research_choose_{technology.id}", label, (x+18, y+84, 217, 32),
                       lambda identifier=technology.id: app.research_request(identifier), enabled=reason is None)
            caption = "Permanent choice" if status in ("active", "discovered", "excluded") else f"{technology.cost} RP"
            text(surface, caption, (x+453, y+95), 10, color if color != LINE else FAINT, "mono", right=True)

    app.button("research_save", "Save · F5", (64, 835, 172, 44), app.save_game)
    app.button("research_pause", "Menu", (250, 835, 132, 44), app.pause)
    text(surface, "Choices are permanent. The other technology in that tier becomes unavailable.", (409, 828), 12, MUTED)
    text(surface, "Bonuses stack. Discounts add; new order prices round up. Unused research is banked.", (409, 851), 10, FAINT)
    app.button("research_end_turn", "End turn · E", (1081, 824, 295, 55), app.advance_turn, "primary")
