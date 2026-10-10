"""One sequence of paired technology choices for each research branch."""

import math
import pygame as pg

from .fleet_art import ship_icon
from .production import HULL_TECHNOLOGIES
from .research import BRANCHES, TECHNOLOGIES, TIER_NAMES, branch_tiers, choices
from .ui import CYAN, FAINT, GOLD, INK, LINE, MUTED, PANEL, panel, paragraph, shorten, text


def draw_research(app):
    surface, game = app.canvas, app.game
    state = game.technology
    rate = game.empire_rates[1]
    branch = BRANCHES[app.research_branch]
    tiers = branch_tiers(branch.id)
    app.research_tier = min(app.research_tier, tiers[-1])
    selected_tier = app.research_tier
    app.chrome("RESEARCH DIRECTORATE")
    app.button("research_back", "← Back · R", (64, 124, 195, 46), app.close_research, "ghost")
    text(surface, f"YEAR {game.year} · TURN {game.turn}", (1376, 141), 12, GOLD, "mono", right=True)
    text(surface, "Research & discovery", (64, 190), 43, INK, "title")
    text(surface, "Choose one technology at each tier. Complete it to unlock both choices in the next tier.",
         (66, 251), 14, MUTED)

    panel(surface, (64, 284, 1312, 113))
    text(surface, "CURRENT PROJECT", (85, 298), 9, MUTED, "mono", 1)
    if state.active:
        active, cost = TECHNOLOGIES[state.active], state.project_cost
        text(surface, active.name, (85, 317), 23, INK)
        remaining = cost-state.progress
        turns = math.ceil(remaining/rate) if rate else None
        eta = f"{turns} {'turn' if turns == 1 else 'turns'} at current output" if rate else "Build a research lab to make progress"
        text(surface, f"{state.progress} / {cost} RP · {eta}", (86, 352), 12, CYAN if rate else GOLD)
        pg.draw.rect(surface, LINE, (86, 379, 624, 4))
        pg.draw.rect(surface, CYAN, (86, 379, round(624*state.progress/cost), 4))
        app.button("research_show_active", "View", (740, 326, 100, 40),
                   lambda identifier=active.id: app.show_research_technology(identifier))
    else:
        done = "ascension_theory" in state.completed
        capstone = state.finished_branches == len(state.required_branches) and not done
        text(surface, "Ascension Theory discovered" if done else "Ascension Theory available" if capstone else "Choose a technology below", (85, 321), 23, INK)
        caption = (f"Latest discovery: {TECHNOLOGIES[state.completed[-1]].name}." if state.completed else
                   "Build a research lab on a colony to generate research points.")
        text(surface, caption, (86, 361), 12, MUTED)
        if capstone or done:
            app.button("research_objectives", "View", (740, 326, 100, 40), app.open_objectives)
    for x, label, value, caption in (
        (885, "RESEARCH OUTPUT", f"+{rate} RP", "per turn"),
        (1082, "BANKED POINTS", f"{game.research:,} RP", "applied when you choose"),
    ):
        pg.draw.line(surface, LINE, (x-22, 307), (x-22, 378))
        text(surface, label, (x, 303), 9, MUTED, "mono", 1)
        text(surface, value, (x, 327), 25, CYAN)
        text(surface, caption, (x, 365), 11, MUTED)

    for index, item in enumerate(BRANCHES.values()):
        y = 419+index*44
        selected = item.id == branch.id
        panel(surface, (64, y, 318, 39), (21, 38, 47) if selected else PANEL, GOLD if selected else LINE)
        if selected:
            pg.draw.rect(surface, GOLD, (64, y, 3, 39))
        count, total = len(state.completed_tiers(item.id)), len(branch_tiers(item.id))
        text(surface, f"{index+1:02}", (79, y+13), 10, GOLD if selected else FAINT, "mono")
        text(surface, item.name, (110, y+10), 15, INK if selected else MUTED)
        text(surface, f"{count}/{total}", (365, y+13), 10, CYAN if count else FAINT, "mono", right=True)
        app.button(f"research_branch_{item.id}", "", (64, y, 318, 39),
                   lambda identifier=item.id: app.select_research_branch(identifier), "hotspot")

    text(surface, branch.name, (408, 414), 25, INK, "title")
    text(surface, f"{len(tiers)} TIERS", (1375, 428), 10, FAINT, "mono", right=True)
    text(surface, shorten(branch.description, 950, 13), (409, 452), 13, MUTED)
    for tier in tiers:
        x = 408+(tier-1)*196
        options = choices(branch.id, tier)
        completed = tier in state.completed_tiers(branch.id)
        active = state.active in {t.id for t in options}
        available = any(state.status(t.id) == "available" for t in options)
        label = "Complete" if completed else "Researching" if active else "Available" if available else "Locked"
        app.button(f"research_tier_{tier}", f"{TIER_NAMES[tier-1]} · {label}", (x, 482, 184, 40),
                   lambda t=tier: app.select_research_tier(t), "primary" if tier == selected_tier else "normal")
        if tier < tiers[-1]:
            pg.draw.line(surface, LINE, (x+184, 501), (x+194, 501), 2)

    text(surface, f"TIER {TIER_NAMES[selected_tier-1]} / CHOOSE ONE", (409, 539), 10, GOLD, "mono", 1)
    for index, technology in enumerate(choices(branch.id, selected_tier)):
        x, y = 408+index*496, 564
        status = state.status(technology.id)
        color = CYAN if status == "discovered" else GOLD if status == "active" else LINE
        panel(surface, (x, y, 472, 236), (14, 29, 38) if status in ("active", "discovered") else PANEL, color)
        text(surface, technology.name, (x+18, y+18), 20, MUTED if status == "excluded" else INK)
        hull = next((kind for kind, tech in HULL_TECHNOLOGIES.items() if tech == technology.id), None)
        paragraph(surface, technology.description, (x+19, y+59), 318 if hull else 432, 14, MUTED, 22)
        if hull:
            ship_icon(surface, (x+397, y+101), 1.35, kind=hull)
        label = {"discovered": "Discovered", "active": "Researching", "excluded": "Not chosen",
                 "locked": "Earlier tiers required", "available": "Project active" if state.active else "Choose technology"}[status]
        reason = game.research_error(technology.id)
        app.button(f"research_choose_{technology.id}", label, (x+18, y+163, 254, 40),
                   lambda identifier=technology.id: app.research_request(identifier), enabled=reason is None)
        cost = state.project_cost if status == "active" else technology.cost
        text(surface, f"{cost} RP", (x+453, y+177), 12, CYAN, "mono", right=True)
        caption = "Permanent choice" if status in ("active", "discovered", "excluded") else "Either choice opens the next tier"
        if selected_tier == tiers[-1] and status == "available":
            caption = "Either choice completes this branch"
        text(surface, caption, (x+19, y+216), 10, FAINT)

    app.button("research_save", "Save · F5", (64, 835, 172, 44), app.save_game)
    app.button("research_pause", "Menu", (250, 835, 132, 44), app.pause)
    text(surface, "Finish all required branches to unlock Ascension Theory.", (409, 828), 12, MUTED)
    text(surface, "PgUp / PgDn: browse tiers · Unused points are banked.", (409, 851), 10, FAINT)
    app.button("research_end_turn", "End turn · E", (1081, 824, 295, 55), app.advance_turn, "primary")
