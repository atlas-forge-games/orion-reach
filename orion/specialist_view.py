"""Space Hub recruitment and assignments, with explicit fees and skill effects."""
import pygame as pg
from . import specialists as rules
from .specialist_art import draw_portrait
from .ui import CYAN, GOLD, INK, MUTED, RED, LINE, panel, paragraph as ui_paragraph, shorten, text

PAGE_SIZE = 5
ASSIGNMENTS_PER_PAGE = 3


def paragraph(surface, value, rect, size, color):
    return ui_paragraph(surface, value, rect[:2], rect[2], size, color, size+8)


def location(game, p):
    if p.system_id is None:
        return "In reserve"
    if p.planet_id is not None:
        return game.planet_at(p.system_id, p.planet_id).name
    return game.systems[p.system_id].name


def rows(app):
    if app.specialist_tab == "visitors":
        return rules.visitors(app.game)
    if app.specialist_tab == "sites":
        # Lost, unfinished sites can be worked by another empire. Do not expose
        # that private progress; your own completed discoveries remain history.
        return [s for s in app.game.specialists.sites if "player" in s.known_by
                and (s.recovered_by == "player" or rules.eligible_system(app.game, s.system_id, "player"))]
    return rules.employed(app.game)


def assignments(game, p):
    if p.spec.role == "leader":
        return [(s.id, world.id) for s, world in game.settlements("player")]
    return [(s.id, None) for s in game.systems if rules.eligible_system(game, s.id, "player")]


def draw_specialists(app):
    game, surface = app.game, app.canvas
    app.chrome("EMPIRE · SPECIALISTS")
    app.button("specialists_back", "← Back · Esc", (64, 124, 210, 46), app.close_specialists, "ghost")
    app.button("specialists_empire", "Empire overview", (289, 124, 210, 46), app.open_empire, "ghost")
    text(surface, "Specialists", (64, 195), 38, INK, "title")
    text(surface, "Recruit at Space Hubs. Assign leaders to colonies or motherships, explorers to your systems.", (66, 247), 14, MUTED)
    staff, wages = rules.employed(game), rules.salaries(game)
    text(surface, f"{len(staff)}/{rules.MAX_EMPLOYED} HIRED   ·   {wages} CR/TURN SALARIES", (1376, 201), 13, GOLD, "mono", right=True)
    text(surface, f"Treasury {game.credits:,} CR   ·   Net income {game.empire_rates[0]:+,} CR/turn", (1376, 226), 13, MUTED, right=True)
    panel(surface, (64, 286, 346, 535))
    panel(surface, (434, 286, 942, 535))
    for i, (key, label) in enumerate((("visitors", "Visitors"), ("hired", "Hired"), ("sites", "Discoveries"))):
        app.button("specialists_tab_"+key, label, (76+i*109, 300, 105, 37),
                   lambda k=key: app.specialist_set_tab(k), "tab_active" if app.specialist_tab == key else "tab")
    items = rows(app)
    app.specialist_page = min(app.specialist_page, max(0, (len(items)-1)//PAGE_SIZE))
    selected = app.specialist_selected
    identifiers = [str(item.system_id) if app.specialist_tab == "sites" else item.id for item in items]
    if selected not in identifiers:
        selected = identifiers[0] if identifiers else None
        app.specialist_selected = selected
    for i, item in enumerate(items[app.specialist_page*PAGE_SIZE:(app.specialist_page+1)*PAGE_SIZE]):
        y = 352+i*80
        identifier = str(item.system_id) if app.specialist_tab == "sites" else item.id
        button = app.button("specialist_select_"+identifier, "", (76, y, 322, 71),
                            lambda k=identifier: app.specialist_select(k), "hotspot")
        panel(surface, button.rect, (23, 41, 51) if identifier == selected else (13, 26, 35), GOLD if identifier == selected else LINE)
        if app.specialist_tab == "sites":
            left, width = 88, 298
            name = game.systems[item.system_id].name
            caption = item.spec.name if item.surveyed >= rules.SURVEY_WORK else "Survey in progress"
            detail = "RECOVERED" if item.recovered_by else "UNFINISHED"
        else:
            draw_portrait(surface, item.spec, (84, y+8, 55, 55))
            left, width = 149, 239
            name = item.spec.name
            caption = f"{rules.ROLES[item.spec.role]} · Level {item.level}"
            detail = f"Visiting {location(game, item)}" if item.visitor else location(game, item)
        text(surface, shorten(name, width, 18), (left, y+9), 18, INK)
        text(surface, shorten(caption, width, 12), (left, y+34), 12, CYAN)
        text(surface, shorten(detail, width, 11), (left, y+51), 11, MUTED)
    if not items:
        paragraph(surface, "No visitors at present." if app.specialist_tab == "visitors" else "No hired specialists yet." if app.specialist_tab == "hired" else "No expeditions started yet.", (88, 365, 295, 100), 19, INK)
    app.button("specialist_prev", "←", (76, 771, 66, 32), lambda: app.specialist_change_page(-1), enabled=app.specialist_page > 0)
    app.button("specialist_next", "→", (332, 771, 66, 32), lambda: app.specialist_change_page(1), enabled=(app.specialist_page+1)*PAGE_SIZE < len(items))
    text(surface, f"{app.specialist_page+1} / {max(1,(len(items)+PAGE_SIZE-1)//PAGE_SIZE)}", (215, 780), 12, MUTED, "mono")
    if not items:
        draw_empty(app)
    elif app.specialist_tab == "sites":
        draw_site(app, next(s for s in items if str(s.system_id) == selected))
    else:
        draw_person(app, rules.person(game, selected))
    text(surface, f"{rules.XP_PER_TURN} XP per hired turn, including reserve · Each level: +1 to every starting skill · Maximum level {rules.MAX_LEVEL}", (66, 843), 13, CYAN)
    text(surface, "Salaries are charged every turn while hired. Dismissal ends salary immediately and preserves experience.", (66, 870), 12, MUTED)


def draw_empty(app):
    game, surface = app.game, app.canvas
    text(surface, "A meeting place on the frontier", (462, 321), 29, INK, "title")
    if rules.hubs(game):
        message = "Your Space Hub is operational. Specialists arrive as turns advance; your first Hub welcomes a leader and an explorer if available. Use Visitors to review arrivals and hire them."
    elif any('space_hub' in p.buildings for _, p in game.settlements('player')):
        message = "Your Space Hub is offline. Enable it in facility management and supply enough energy to attract visitors. Motherships use Manage modules for these controls."
    else:
        message = "Build a Space Hub on a colony or a Space Hub module aboard a mothership. Once operational, your first Hub welcomes a leader and an explorer if available. More specialists visit over time."
    paragraph(surface, message, (464, 380, 810, 100), 18, MUTED)
    details = [
        f"Operational Hubs: {len(rules.hubs(game))} · Visitor chance: {rules.visit_chance(game, 'player')}% every {rules.VISIT_INTERVAL} turns.",
        f"Visitors stay {rules.VISIT_DURATION} turns. Extra Hubs provide more meeting places; arrivals stay capped per empire.",
        f"Up to {rules.MAX_EMPLOYED} hires per empire. One leader per colony or mothership, one explorer per system.",
        "Hiring and salaries cost credits. Leaders can work at colonies or motherships without a Hub.",
        "Explorers survey first, then use Hacking, Salvaging or Archaeology to recover a finite reward.",
    ]
    for i, line in enumerate(details):
        paragraph(surface, line, (464, 502+i*52, 858, 48), 15, INK if i == 0 else MUTED)


def draw_person(app, p):
    game, surface = app.game, app.canvas
    spec = p.spec
    draw_portrait(surface, spec, (464, 306, 112, 112))
    text(surface, shorten(spec.name, 480, 29, "title"), (594, 306), 29, INK, "title")
    text(surface, f"{rules.ROLES[spec.role]} · Level {p.level}", (596, 346), 14, CYAN)
    next_xp = rules.level_xp(p.level+1) if p.level < rules.MAX_LEVEL else None
    text(surface, f"{p.xp}/{next_xp} XP to next level" if next_xp is not None else f"{p.xp} XP · Maximum level", (1348, 349), 12, MUTED, right=True)
    paragraph(surface, spec.description, (596, 376, 518, 55), 15, MUTED)
    text(surface, f"{spec.hiring_fee} CR hire · {spec.salary} CR/turn", (1348, 315), 13, GOLD, right=True)
    if p.visitor:
        reason = rules.hire_error(game, p.id)
        app.button("specialist_hire", f"Hire · {spec.hiring_fee} CR", (1156, 386, 192, 38), lambda: app.specialist_action("hire", p.id), "primary", enabled=reason is None)
        caption = reason or f"At {location(game,p)} · leaves at start of turn {p.expires}"
    else:
        app.button("specialist_dismiss", "Dismiss", (1190, 386, 158, 36), lambda: app.specialist_dismiss(p.id), "ghost")
        caption = "Fixed colony output before empire modifiers; no population multiplier." if spec.role == "leader" else "Skill value = work per turn. Missing skills stay at zero when levelling."
    text(surface, shorten(caption, 882, 12), (464, 440), 12, RED if p.visitor and reason else MUTED)
    for i, (key, value) in enumerate(p.skills.items()):
        x = 464+i*176
        panel(surface, (x, 469, 164, 63))
        text(surface, rules.SKILLS[key][0].upper(), (x+10, 480), 10, MUTED, "mono")
        unit = rules.SKILLS[key][1] if spec.role == "leader" else "work/turn"
        text(surface, f"+{value} {unit}" if spec.role == "leader" else f"{value} {unit}", (x+10, 501), 16, CYAN)
    if p.visitor:
        paragraph(surface, "Hire this specialist to choose an assignment. Leaders improve a single colony; explorers reveal one recoverable site in each of your systems. Every character is unique across all empires.", (464, 572, 840, 100), 18, INK)
        paragraph(surface, f"Current income after hiring: {game.empire_rates[0]-spec.salary:+} CR/turn, before assignment bonuses. Salary stays {spec.salary} CR/turn as this specialist gains levels. Hired specialists remain with you if a Space Hub closes.", (464, 698, 840, 84), 15, MUTED)
    else:
        draw_assignments(app, p)


def draw_assignments(app, p):
    game, surface = app.game, app.canvas
    current = location(game, p)
    status = rules.expedition_status(game, p) if p.spec.role == "explorer" else "One leader per colony"
    text(surface, shorten(f"ASSIGNMENT: {current}", 648, 13), (464, 552), 13, GOLD)
    text(surface, shorten(status, 692, 12), (464, 577), 12, MUTED)
    if p.system_id is not None:
        app.button("specialist_unassign", "Return to reserve", (1144, 549, 204, 34), lambda: app.specialist_action("unassign", p.id))
    locations = assignments(game, p)
    app.specialist_assignment_page = min(app.specialist_assignment_page, max(0, (len(locations)-1)//ASSIGNMENTS_PER_PAGE))
    page = app.specialist_assignment_page
    for i, (sid, pid) in enumerate(locations[page*ASSIGNMENTS_PER_PAGE:(page+1)*ASSIGNMENTS_PER_PAGE]):
        y = 611+i*49
        name = game.planet_at(sid, pid).name if pid is not None else game.systems[sid].name
        reason = rules.assignment_error(game, p.id, sid, pid)
        same = (p.system_id, p.planet_id) == (sid, pid)
        subtitle = reason or ("Currently assigned" if same else "Available colony" if pid is not None else "Unsurveyed system")
        site = rules.site_at(game, sid)
        if pid is None and site and not reason:
            if site.surveyed >= rules.SURVEY_WORK:
                subtitle = f"{site.spec.name} · needs {rules.SKILLS[site.spec.skill][0]} {site.spec.difficulty} · {site.spec.reward}"
            else:
                subtitle = f"Survey progress {site.surveyed}/{rules.SURVEY_WORK}"
        text(surface, shorten(name, 580, 16), (464, y), 16, INK)
        text(surface, shorten(subtitle, 674, 11), (464, y+24), 11, MUTED)
        app.button(f"specialist_assign_{sid}_{pid}", "Assigned" if same else "Assign", (1190, y+1, 158, 35),
                   lambda s=sid, w=pid: app.specialist_action("assign", p.id, s, w), enabled=reason is None and not same)
    if not locations:
        text(surface, "No eligible locations. Explorers require a system without foreign colonies.", (464, 626), 14, MUTED)
    app.button("specialist_assign_prev", "←", (1190, 774, 70, 28), lambda: app.specialist_assignment_page_by(-1), enabled=page > 0)
    app.button("specialist_assign_next", "→", (1278, 774, 70, 28), lambda: app.specialist_assignment_page_by(1), enabled=(page+1)*ASSIGNMENTS_PER_PAGE < len(locations))
    text(surface, f"Locations {page+1}/{max(1,(len(locations)+ASSIGNMENTS_PER_PAGE-1)//ASSIGNMENTS_PER_PAGE)}", (464, 782), 11, MUTED)


def draw_site(app, site):
    surface, game = app.canvas, app.game
    revealed = site.surveyed >= rules.SURVEY_WORK
    text(surface, game.systems[site.system_id].name, (464, 319), 29, INK, "title")
    text(surface, site.spec.name if revealed else "Uncharted expedition site", (464, 367), 23, CYAN)
    paragraph(surface, site.spec.description if revealed else "An explorer must complete the survey before the site's requirements and reward become known.", (464, 420, 832, 92), 18, MUTED)
    text(surface, f"SURVEY: {site.surveyed}/{rules.SURVEY_WORK}", (464, 535), 16, GOLD)
    if revealed:
        text(surface, f"RECOVERY: {site.progress}/{site.spec.work} · Requires {rules.SKILLS[site.spec.skill][0]} {site.spec.difficulty}", (464, 580), 16, INK)
        text(surface, f"ONE-TIME REWARD: {site.spec.reward}", (464, 627), 20, GOLD)
    if site.recovered_by:
        caption = "Recovered. This site cannot be collected again."
    else:
        explorer = next((p for p in rules.employed(game) if p.spec.role == "explorer" and p.system_id == site.system_id), None)
        caption = f"{explorer.spec.name}: {rules.expedition_status(game,explorer)}" if explorer else "Assign an explorer from the Hired tab to continue. Progress is retained."
    paragraph(surface, caption, (464, 707, 840, 85), 17, CYAN)
