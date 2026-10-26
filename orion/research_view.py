"""Six research fields with three choices per tier; classic campaign support."""

import math
import pygame as pg

from .fleet_art import ship_icon
from .production import HULL_TECHNOLOGIES
from .research import BRANCHES, TECHNOLOGIES, TIER_NAMES, branch_tiers, choices
from .research_fields import is_modern
from .buildings import BUILDINGS
from .building_art import draw_building_art
from . import hyperlanes, race_victory
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


def research_rate(game):
    return max(0, game.empire_rates[1]-race_victory.research_reservation(game))


def output_caption(game):
    reserved = race_victory.research_reservation(game)
    if reserved:
        return f"after up to {reserved} RP to legacy"
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
        available = any(state.status(t) == "available" and t != "ascension_theory"
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
    if is_modern(BRANCHES):
        return draw_six_fields(app)
    surface, game = app.canvas, app.game
    state = game.technology
    app.chrome("RESEARCH DIRECTORATE")
    app.button("research_back", "← Back · R", (64, 124, 195, 46), app.close_research, "ghost")
    text(surface, "Research fields", (290, 128), 32, INK, "title")
    text(surface, f"YEAR {game.year} · TURN {game.turn}", (1376, 141), 12, GOLD, "mono", right=True)
    rate = research_rate(game)
    draw_project_summary(app, rate)
    for index, branch in enumerate((*BRANCHES.values(), None)):
        x, y, width, height = 64+(index % 2)*668, 302+(index // 2)*104, 644, 96
        if branch is None:
            from .race_victory import spec_for, PROJECT_TECHS
            from .victory import race_goal
            goal, spec = race_goal(game), spec_for(game)
            panel(surface, (x, y, width, height), (10, 24, 32), LINE)
            text(surface, "Civilization legacy", (x+14, y+8), 18, GOLD)
            text(surface, "ON" if "race" in game.victory_conditions else "OFF", (x+width-14, y+11), 11, CYAN, right=True)
            text(surface, goal.title if goal else "Race-specific objectives", (x+17, y+40), 16, INK)
            caption = f"Unlock installation after {PROJECT_TECHS} technologies · Objectives →" if spec else "Discover every forgotten hyperlane · Objectives →"
            text(surface, caption, (x+17, y+71), 11, MUTED)
            app.button("research_legacy_objectives", "", (x+1, y+1, width-2, height-2), app.open_objectives, "hotspot")
            continue
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

    app.button("research_save", "Save · F5", (64, 835, 172, 44), app.save_game)
    app.button("research_pause", "Menu", (250, 835, 132, 44), app.pause)
    text(surface, "Left-click to choose or switch · Right-click a technology for information", (409, 830), 12, MUTED)
    text(surface, "Invested RP transfers · Only completed choices are permanent", (409, 853), 11, FAINT)
    app.button("research_end_turn", "End turn · E", (1081, 824, 295, 55), app.advance_turn, "primary")


def technology_kind(identifier):
    if any(b.enabled and b.technology == identifier for b in BUILDINGS.values()):
        return 'BUILDING'
    if identifier in HULL_TECHNOLOGIES.values():
        return 'HULL'
    from .megastructures import MEGASTRUCTURES, required_technology
    if any(required_technology(key) == identifier for key in MEGASTRUCTURES):
        return 'SYSTEM PROJECT'
    from .designs import MODULES
    if any(m.technology == identifier for m in MODULES.values()):
        return 'SHIP MODULE'
    return 'EMPIRE IMPROVEMENT'


def draw_six_fields(app):
    surface, game = app.canvas, app.game
    state = game.technology
    app.chrome('RESEARCH DIRECTORATE')
    app.button('research_back', '← Back · R', (64, 124, 195, 46), app.close_research, 'ghost')
    text(surface, 'Six fields of discovery', (290, 128), 32, INK, 'title')
    draw_project_summary(app, research_rate(game))
    for index, branch in enumerate(BRANCHES.values()):
        x, y, width, height = 64+(index % 2)*668, 304+(index // 2)*168, 644, 158
        tier, tiers = state.next_tier(branch.id), branch_tiers(branch.id)
        options = choices(branch.id, tier)
        active = state.active in {t.id for t in options}
        panel(surface, (x, y, width, height), (10, 24, 32), GOLD if active else LINE)
        pg.draw.rect(surface, (24, 39, 47), (x+1, y+1, width-2, 37))
        text(surface, branch.name, (x+15, y+9), 21, GOLD if active else INK)
        text(surface, f'TIER {TIER_NAMES[tier-1]} / {TIER_NAMES[tiers[-1]-1]}', (x+width-15, y+15), 10, CYAN, 'mono', right=True)
        app.button('research_branch_'+branch.id, '', (x+1, y+1, width-2, 37),
                   lambda b=branch.id: app.select_research_branch(b), 'hotspot')
        text(surface, branch.description, (x+15, y+44), 11, MUTED)
        for row, technology in enumerate(options):
            draw_choice_row(app, technology, (x+7, y+65+row*28, width-14, 27))
    app.button('research_save', 'Save · F5', (64, 835, 172, 44), app.save_game)
    app.button('research_pause', 'Menu', (250, 835, 132, 44), app.pause)
    text(surface, 'Choose one of three · Completion unlocks the next tier', (409, 831), 12, MUTED)
    text(surface, 'Field heading: details · Right-click: information · Invested RP transfers', (409, 855), 10, FAINT)
    text(surface, '3 OPTIONS · CHOOSE 1', (1376, 146), 11, GOLD, 'mono', right=True)
    app.button('research_end_turn', 'End turn · E', (1081, 824, 295, 55), app.advance_turn, 'primary')


def draw_branch_detail(app):
    surface, game = app.canvas, app.game
    state = game.technology
    rate = research_rate(game)
    branch = BRANCHES[app.research_branch]
    tiers = branch_tiers(branch.id)
    app.research_tier = min(app.research_tier, tiers[-1])
    selected_tier = app.research_tier
    app.chrome("RESEARCH DIRECTORATE")
    app.button("research_back", "← Back · R", (64, 124, 195, 46), app.close_research, "ghost")
    app.button("research_fields", "All fields", (274, 124, 182, 46), app.show_research_overview, "ghost")
    text(surface, f"YEAR {game.year} · TURN {game.turn}", (1376, 141), 12, GOLD, "mono", right=True)
    text(surface, "Research & discovery", (64, 190), 43, INK, "title")
    text(surface, "Choose one technology per tier. Completing it unlocks all choices in the next tier.",
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
        text(surface, "Choose a technology below", (85, 321), 23, INK)
        caption = f"Latest discovery: {TECHNOLOGIES[state.completed[-1]].name}." if state.completed else "Build a research lab to generate research points."
        text(surface, caption, (86, 361), 12, MUTED)
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
    options = choices(branch.id, selected_tier)
    card_pitch = 968/len(options)
    for index, technology in enumerate(options):
        width = round(card_pitch)-12
        x, y = round(408+index*card_pitch), 559
        status = state.status(technology.id)
        color = CYAN if status == "discovered" else GOLD if status == "active" else LINE
        panel(surface, (x, y, width, 246), (14, 29, 38) if status in ("active", "discovered") else PANEL, color)
        app.technology_info_region(technology.id, (x, y, width, 246))
        text(surface, technology_kind(technology.id), (x+15, y+12), 9, GOLD, 'mono')
        for line, title in enumerate(wrapped_lines(technology.name, width-30, 18)[:2]):
            text(surface, title, (x+15, y+33+line*21), 18, MUTED if status == 'excluded' else INK)
        hull = next((kind for kind, tech in HULL_TECHNOLOGIES.items() if tech == technology.id), None)
        building = next((b for b in BUILDINGS.values() if b.enabled and b.technology == technology.id), None)
        if building:
            draw_building_art(surface, building.id, (x+width-96, y+74, 80, 64))
        elif hull:
            ship_icon(surface, (x+width-52, y+106), .95, kind=hull)
        # Art and short effect preview are separate from the complete right-click details.
        detail_width = width-120 if building or hull else width-30
        lines = wrapped_lines(technology.description, detail_width, 12)
        for line, content in enumerate(lines[:6]):
            if line == 5 and len(lines) > 6:
                content = shorten(content+' …', detail_width, 12)
            text(surface, content, (x+15, y+82+line*17), 12, MUTED)
        label = {"discovered": "Discovered", "active": "Researching", "excluded": "Not chosen",
                 "locked": "Earlier tiers required", "available": "Switch technology" if state.active else "Choose technology"}[status]
        reason = game.research_error(technology.id)
        app.button(f"research_choose_{technology.id}", label, (x+15, y+183, width-30, 35),
                   lambda identifier=technology.id: app.research_request(identifier), enabled=reason is None)
        cost = state.project_cost if status == "active" else technology.cost
        text(surface, f"{cost} RP", (x+width-15, y+12), 10, CYAN, "mono", right=True)
        caption = ("Completed choice is permanent" if status in ("discovered", "excluded") else
                   "Switch freely until discovery" if status in ("active", "available") else
                   "Any choice opens the next tier")
        if selected_tier == tiers[-1] and status == "available":
            caption = "Any choice completes this field"
        text(surface, caption, (x+15, y+228), 10, FAINT)

    app.button("research_save", "Save · F5", (64, 835, 172, 44), app.save_game)
    app.button("research_pause", "Menu", (250, 835, 132, 44), app.pause)
    text(surface, "Your civilization legacy is tracked in Objectives.", (409, 828), 12, MUTED)
    text(surface, "PgUp / PgDn: browse tiers · Right-click a technology for information", (409, 851), 10, FAINT)
    app.button("research_end_turn", "End turn · E", (1081, 824, 295, 55), app.advance_turn, "primary")


def draw_technology_info(app, identifier):
    """Read-only, paginated details for every choice, including both alternatives."""
    surface, game = app.canvas, app.game
    state, technology = game.technology, TECHNOLOGIES[identifier]
    status = state.status(identifier)
    cost = state.project_cost if status == 'active' else technology.cost
    alternatives = [t.name for t in choices(technology.branch, technology.tier) if t.id != identifier]
    notes = [technology.description]
    buildings = [b for b in BUILDINGS.values() if b.enabled and b.technology == identifier]
    for building in buildings:
        notes.append(f'BUILD: {building.name} · {building.resource_cost} Resources · {building.work_cost} work · one slot.')
        notes.append(building.effect_text('Average') + f' · {building.energy_use} energy · {building.maintenance} CR upkeep.')
        if building.workforce_text('Average'):
            notes.append(building.workforce_text('Average'))
    if buildings:
        notes.append('Research unlocks construction. Benefits begin only when the facility is completed and operating. Existing buildings remain unchanged.')
    from .megastructures import MEGASTRUCTURES, required_technology
    for spec in MEGASTRUCTURES.values():
        required = required_technology(spec.id)
        if required == identifier:
            notes.append(f'Unlocks the {spec.name} system project.')
        elif not required and technology.branch == spec.branch and technology.tier == spec.tier:
            notes.append(f'Any choice in this tier unlocks the {spec.name} system project.')
    if identifier == 'ascension_theory' and 'science' not in game.victory_conditions:
        notes.append('Ascension Theory is retired and replaced by civilization legacies.')
    elif status == 'available':
        available = game.research+state.progress
        notes.append(f'Selecting applies up to {min(cost, available)} RP: {state.progress} invested and {game.research} banked.')
        if available >= cost:
            notes.append(f'Discovered immediately; {available-cost} RP remains banked.')
        else:
            notes.append('Until discovery, switching transfers all invested RP to the new choice.')
    elif status == 'active':
        notes.append(f'{state.progress} / {cost} RP invested. Switching transfers all invested RP.')
    elif status == 'discovered':
        notes.append('Already discovered. This completed choice is permanent.')
    else:
        notes.append(state.choice_error(identifier))
    if alternatives:
        notes.append('Other choices in this tier: ' + '; '.join(alternatives) + '.')
        notes.append('Completing one choice excludes normal research of the others. A Research Array may later recover an omitted discovery.')
    if technology.branch in BRANCHES:
        notes.append('Any completed choice opens the next tier. Tier access has no specific prerequisites; equipment still needs a compatible hull.')
    name = BRANCHES[technology.branch].name if technology.branch in BRANCHES else 'Ascension'
    tier = 'FINALE' if technology.branch == 'ascension' else f'TIER {TIER_NAMES[technology.tier-1]}'
    x, y, width, height = 240, 75, 960, 750
    panel(surface, (x, y, width, height), PANEL, GOLD)
    text(surface, f'{name.upper()} · {tier} · {technology_kind(identifier)}', (x+30, y+23), 10, GOLD, 'mono')
    text(surface, shorten(technology.name, 700, 28, 'title'), (x+29, y+48), 28, INK, 'title')
    label = {'available': 'Available', 'active': 'Researching', 'discovered': 'Discovered', 'excluded': 'Not chosen', 'locked': 'Locked'}[status]
    text(surface, f'{cost} RP · {label}', (x+30, y+96), 14, CYAN)
    if buildings:
        draw_building_art(surface, buildings[0].id, (x+777, y+40, 145, 95))
    rows = []
    for note in notes:
        rows.extend(wrapped_lines(note, width-60, 15))
        rows.append('')
    per_page = 21
    pages = max(1, (len(rows)+per_page-1)//per_page)
    page = min(pages-1, max(0, app.dialog.get('technology_page', 0)))
    for row, line in enumerate(rows[page*per_page:(page+1)*per_page]):
        text(surface, line, (x+30, y+150+row*23), 15, MUTED if not line.startswith('BUILD:') else CYAN)
    if pages > 1:
        app.button('technology_info_previous', '←', (x+30, y+653, 52, 35), lambda: app.dialog.update(technology_page=page-1), enabled=page > 0)
        text(surface, f'{page+1} / {pages}', (x+97, y+664), 12, MUTED)
        app.button('technology_info_next', '→', (x+155, y+653, 52, 35), lambda: app.dialog.update(technology_page=page+1), enabled=page < pages-1)
    text(surface, 'Information only · Research orders are unchanged', (x+30, y+710), 11, FAINT)
    app.button('dialog_close', 'Close · Esc', (x+720, y+690, 210, 40), app.cancel_dialog)
