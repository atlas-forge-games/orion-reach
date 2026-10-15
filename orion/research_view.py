"""Ten research fields at a glance, with browsable paired technology tiers."""

import math
import pygame as pg

from .fleet_art import ship_icon
from .production import HULL_TECHNOLOGIES
from .research import BRANCHES, TECHNOLOGIES, TIER_NAMES, branch_tiers, choices
from . import hyperlanes
from .ui import CYAN, FAINT, GOLD, INK, LINE, MUTED, PANEL, panel, paragraph, shorten, text, wrapped_lines


def draw_research(app):
    if app.research_overview:
        draw_field_overview(app)
    else:
        draw_branch_detail(app)


def project_eta(game, technology, rate):
    state = game.technology
    cost = state.project_cost if state.active == technology.id else technology.cost
    remaining = max(0, cost - state.progress - game.research)
    if not remaining:
        return "Ready now"
    if not rate:
        return "No RP output"
    turns = math.ceil(remaining / rate)
    return f"{turns} {'turn' if turns == 1 else 'turns'}"


def output_caption(game):
    diverted = sum(hyperlanes.allocations(game, "player").values())
    return f"after {diverted} RP to hyperlanes" if diverted else "per turn"


def draw_project_summary(app, rate):
    surface, game = app.canvas, app.game
    state = game.technology
    panel(surface, (64, 190, 1312, 96))
    text(surface, "CURRENT PROJECT", (84, 201), 9, MUTED, "mono", 1)
    if state.active:
        active = TECHNOLOGIES[state.active]
        text(surface, active.name, (83, 222), 23, INK)
        text(surface, f"{state.progress} / {state.project_cost} RP · {project_eta(game, active, rate)}",
             (84, 255), 12, CYAN)
        app.button("research_show_active", "View", (732, 219, 102, 40),
                   lambda: app.show_research_technology(state.active))
        app.technology_info_region(active.id, (83, 219, 751, 56))
        pg.draw.rect(surface, LINE, (84, 278, 610, 3))
        pg.draw.rect(surface, CYAN, (84, 278, round(610*state.progress/state.project_cost), 3))
    else:
        available = any(state.status(t) == "available" and (t != "ascension_theory" or "science" in game.victory_conditions)
                        for t in TECHNOLOGIES)
        text(surface, "Choose your next discovery" if available else "Research complete", (83, 222), 23, GOLD)
        caption = (f"Latest discovery: {TECHNOLOGIES[state.completed[-1]].name}" if state.completed else
                   "Select a technology below. Unused research points are banked.")
        text(surface, shorten(caption, 716, 12), (84, 255), 12, MUTED)
    for x, label, value, caption in (
        (886, "RESEARCH OUTPUT", f"+{rate} RP", output_caption(game)),
        (1130, "BANKED POINTS", f"{game.research:,} RP", "applied when you choose"),
    ):
        pg.draw.line(surface, LINE, (x-20, 207), (x-20, 271))
        text(surface, label, (x, 201), 9, MUTED, "mono", 1)
        text(surface, shorten(value, 224, 23), (x, 222), 23, CYAN)
        text(surface, caption, (x, 257), 11, MUTED)


def draw_choice_row(app, technology, rect):
    """Left-click selects immediately; right-click inspects any technology."""
    surface, game = app.canvas, app.game
    r = pg.Rect(rect)
    status = game.technology.status(technology.id)
    disabled = technology.id == "ascension_theory" and "science" not in game.victory_conditions
    label = {"active": "Researching", "discovered": "Discovered", "excluded": "Not chosen",
             "locked": "Complete all branches" if technology.id == "ascension_theory" else "Locked",
             "available": "Switch →" if game.technology.active else "Choose →"}[status]
    if disabled:
        label = "Disabled in setup"
    color = GOLD if status == "active" else CYAN if status in ("available", "discovered") else FAINT
    if disabled:
        color = FAINT
    button = app.button(f"research_choose_{technology.id}", "", r,
                        lambda: app.research_request(technology.id), "hotspot",
                        enabled=game.research_error(technology.id) is None)
    app.technology_info_region(technology.id, r)
    if app.is_active(button) and button.enabled:
        pg.draw.rect(surface, (25, 46, 55), r.inflate(-2, -2), border_radius=2)
    text(surface, technology.name, (r.x+10, r.y+3), 16, color)
    text(surface, label, (r.right-10, r.y+6), 10, color, right=True)


def draw_field_overview(app):
    surface, game = app.canvas, app.game
    state = game.technology
    app.chrome("RESEARCH DIRECTORATE")
    app.button("research_back", "← Back · R", (64, 124, 195, 46), app.close_research, "ghost")
    text(surface, "Research fields", (290, 128), 32, INK, "title")
    text(surface, f"YEAR {game.year} · TURN {game.turn}", (1376, 141), 12, GOLD, "mono", right=True)
    rate = game.empire_rates[1]
    draw_project_summary(app, rate)
    for index, branch in enumerate((*BRANCHES.values(), None)):
        x, y, width, height = 64+(index % 2)*668, 302+(index // 2)*104, 644, 96
        if branch is None:
            options = (TECHNOLOGIES["ascension_theory"],)
            complete = options[0].id in state.completed
            name, tier_label = "Ascension", "FINALE"
            key, action = "research_branch_ascension", app.open_objectives
        else:
            tier, tiers = state.next_tier(branch.id), branch_tiers(branch.id)
            options = choices(branch.id, tier)
            complete = len(state.completed_tiers(branch.id)) == len(tiers)
            name, tier_label = branch.name, f"TIER {TIER_NAMES[tier-1]} / {TIER_NAMES[tiers[-1]-1]}"
            key, action = f"research_branch_{branch.id}", lambda b=branch.id: app.select_research_branch(b)
        active = next((t for t in options if t.id == state.active), None)
        panel(surface, (x, y, width, height), (10, 24, 32), GOLD if active else LINE)
        pg.draw.rect(surface, (24, 39, 47), (x+1, y+1, width-2, 32))
        text(surface, name, (x+14, y+7), 18, GOLD if active else INK)
        text(surface, tier_label, (x+324, y+12), 9, MUTED, "mono")
        candidate = active or options[0]
        cost = state.project_cost if active else candidate.cost
        budget = ("DISABLED" if branch is None and "science" not in game.victory_conditions else
                  "COMPLETE" if complete else f"{cost} RP · {project_eta(game, candidate, rate)}")
        text(surface, budget, (x+width-14, y+11), 11, CYAN if complete else MUTED, right=True)
        app.button(key, "", (x+1, y+1, width-2, 32), action, "hotspot")
        for row, technology in enumerate(options):
            draw_choice_row(app, technology, (x+7, y+38+row*27, width-14, 25))
        if branch is None:
            text(surface, "Science victory disabled for this campaign · View objectives →" if "science" not in game.victory_conditions else
                 f"{state.finished_branches}/{len(state.required_branches)} required branches complete · View objectives →",
                 (x+17, y+71), 11, MUTED)
            app.button("research_ascension_objectives", "", (x+7, y+65, width-14, 25), app.open_objectives, "hotspot")

    app.button("research_save", "Save · F5", (64, 835, 172, 44), app.save_game)
    app.button("research_pause", "Menu", (250, 835, 132, 44), app.pause)
    text(surface, "Left-click to choose or switch · Right-click a technology for information", (409, 830), 12, MUTED)
    text(surface, "Invested RP transfers · Only completed choices are permanent", (409, 853), 11, FAINT)
    app.button("research_end_turn", "End turn · E", (1081, 824, 295, 55), app.advance_turn, "primary")


def draw_branch_detail(app):
    surface, game = app.canvas, app.game
    state = game.technology
    rate = game.empire_rates[1]
    branch = BRANCHES[app.research_branch]
    tiers = branch_tiers(branch.id)
    app.research_tier = min(app.research_tier, tiers[-1])
    selected_tier = app.research_tier
    app.chrome("RESEARCH DIRECTORATE")
    app.button("research_back", "← Back · R", (64, 124, 195, 46), app.close_research, "ghost")
    app.button("research_fields", "All fields", (274, 124, 182, 46), app.show_research_overview, "ghost")
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
        app.technology_info_region(active.id, (85, 317, 755, 64))
    else:
        done = "ascension_theory" in state.completed
        capstone = "science" in game.victory_conditions and state.finished_branches == len(state.required_branches) and not done
        text(surface, "Ascension Theory discovered" if done else "Ascension Theory available" if capstone else "Choose a technology below", (85, 321), 23, INK)
        caption = (f"Latest discovery: {TECHNOLOGIES[state.completed[-1]].name}." if state.completed else
                   "Build a research lab on a colony to generate research points.")
        text(surface, caption, (86, 361), 12, MUTED)
        if capstone or done:
            app.button("research_objectives", "View", (740, 326, 100, 40), app.open_objectives)
    for x, label, value, caption in (
        (885, "RESEARCH OUTPUT", f"+{rate} RP", output_caption(game)),
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
    pitch = min(196, 968/len(tiers))
    for tier in tiers:
        x = round(408+(tier-1)*pitch)
        width = round(pitch)-10
        options = choices(branch.id, tier)
        completed = tier in state.completed_tiers(branch.id)
        active = state.active in {t.id for t in options}
        available = any(state.status(t.id) == "available" for t in options)
        label = "Complete" if completed else "Researching" if active else "Available" if available else "Locked"
        if len(tiers) > 5:
            label = "Done" if completed else "Active" if active else "Open" if available else "Locked"
        app.button(f"research_tier_{tier}", f"{TIER_NAMES[tier-1]} · {label}", (x, 482, width, 40),
                   lambda t=tier: app.select_research_tier(t), "tab_active" if tier == selected_tier else "tab")
        if tier < tiers[-1]:
            pg.draw.line(surface, LINE, (x+width, 501), (x+round(pitch)-2, 501), 2)

    text(surface, f"TIER {TIER_NAMES[selected_tier-1]} / CHOOSE ONE", (409, 539), 10, GOLD, "mono", 1)
    for index, technology in enumerate(choices(branch.id, selected_tier)):
        x, y = 408+index*496, 564
        status = state.status(technology.id)
        color = CYAN if status == "discovered" else GOLD if status == "active" else LINE
        panel(surface, (x, y, 472, 236), (14, 29, 38) if status in ("active", "discovered") else PANEL, color)
        app.technology_info_region(technology.id, (x, y, 472, 236))
        text(surface, technology.name, (x+18, y+18), 20, MUTED if status == "excluded" else INK)
        hull = next((kind for kind, tech in HULL_TECHNOLOGIES.items() if tech == technology.id), None)
        detail_width = 318 if hull else 432
        size = 13 if len(wrapped_lines(technology.description, detail_width, 14)) > 4 else 14
        paragraph(surface, technology.description, (x+19, y+59), detail_width, size, MUTED, 20)
        if hull:
            ship_icon(surface, (x+397, y+101), 1.35, kind=hull)
        label = {"discovered": "Discovered", "active": "Researching", "excluded": "Not chosen",
                 "locked": "Earlier tiers required", "available": "Switch technology" if state.active else "Choose technology"}[status]
        reason = game.research_error(technology.id)
        app.button(f"research_choose_{technology.id}", label, (x+18, y+163, 254, 40),
                   lambda identifier=technology.id: app.research_request(identifier), enabled=reason is None)
        cost = state.project_cost if status == "active" else technology.cost
        text(surface, f"{cost} RP", (x+453, y+177), 12, CYAN, "mono", right=True)
        caption = ("Completed choice is permanent" if status in ("discovered", "excluded") else
                   "Switch until discovery · All invested RP transfers" if status in ("active", "available") else
                   "Either choice opens the next tier")
        if selected_tier == tiers[-1] and status == "available":
            caption = "Either choice completes this branch"
        text(surface, caption, (x+19, y+216), 10, FAINT)

    app.button("research_save", "Save · F5", (64, 835, 172, 44), app.save_game)
    app.button("research_pause", "Menu", (250, 835, 132, 44), app.pause)
    text(surface, "Finish all required branches to unlock Ascension Theory." if "science" in game.victory_conditions else
         "Science victory disabled · All other technologies remain available.", (409, 828), 12, MUTED)
    text(surface, "PgUp / PgDn: browse tiers · Right-click a technology for information", (409, 851), 10, FAINT)
    app.button("research_end_turn", "End turn · E", (1081, 824, 295, 55), app.advance_turn, "primary")


def draw_technology_info(app, identifier):
    """Read-only details for available, active, locked and completed projects."""
    surface, game = app.canvas, app.game
    state, technology = game.technology, TECHNOLOGIES[identifier]
    status = state.status(identifier)
    cost = state.project_cost if status == "active" else technology.cost
    alternative = next((t for t in choices(technology.branch, technology.tier) if t.id != identifier), None)
    notes = []
    from .megastructures import MEGASTRUCTURES
    for spec in MEGASTRUCTURES.values():
        if technology.branch == spec.branch and technology.tier == spec.tier:
            notes.append(f"Either choice in this tier unlocks the {spec.name} system project.")
    if identifier == "ascension_theory" and "science" not in game.victory_conditions:
        notes.append("Science victory was disabled in galaxy setup. Ascension Theory and the gate are unavailable in this campaign.")
    elif status == "available":
        available = game.research+state.progress
        notes.append(f"Selecting this project applies {min(cost, available)} RP: "
                     f"{state.progress} RP invested in your current project and {game.research} banked RP are available.")
        if available >= cost:
            notes.append(f"It will be discovered immediately; {available-cost} RP will remain banked.")
        else:
            notes.append("You can change projects until discovery. All invested RP transfers to your new choice.")
    elif status == "active":
        notes.append(f"{state.progress} / {cost} RP invested. You can change projects until discovery; all invested RP transfers.")
    elif status == "discovered":
        notes.append("Already discovered. Its effects are active and this completed choice cannot be changed.")
    else:
        notes.append(state.choice_error(identifier))
    if alternative and status in ("active", "available", "locked"):
        notes.append(f"Choosing this technology excludes normal research of {alternative.name}. A Research Array may later recover it.")
    name = BRANCHES[technology.branch].name if technology.branch in BRANCHES else "Ascension"
    tier = "FINALE" if technology.branch == "ascension" else f"TIER {TIER_NAMES[technology.tier-1]}"
    description_height = 26*len(wrapped_lines(technology.description, 784, 17))
    notes_height = sum(23*len(wrapped_lines(note, 784, 15))+12 for note in notes)
    height = max(400, 254+description_height+notes_height)
    x, y = 292, (900-height)//2
    panel(surface, (x, y, 856, height), PANEL, GOLD)
    text(surface, f"{name.upper()} · {tier}", (x+30, y+23), 10, GOLD, "mono", 1)
    text(surface, technology.name, (x+29, y+48), 28, INK, "title")
    label = {"available": "Available", "active": "Researching", "discovered": "Discovered",
             "excluded": "Not chosen", "locked": "Locked"}[status]
    if identifier == "ascension_theory" and "science" not in game.victory_conditions:
        label = "Disabled in setup"
    text(surface, f"{cost} RP · {label}", (x+30, y+96), 14, CYAN)
    bottom = paragraph(surface, technology.description, (x+30, y+132), 784, 17, INK, 26)
    pg.draw.line(surface, LINE, (x+30, bottom+14), (x+826, bottom+14))
    bottom += 32
    for note in notes:
        bottom = paragraph(surface, note, (x+30, bottom), 784, 15, MUTED, 23)+12
    text(surface, "Information only · No research orders are changed", (x+30, y+height-51), 11, FAINT)
    app.button("dialog_close", "Close · Esc", (x+616, y+height-71, 210, 45), app.cancel_dialog)
