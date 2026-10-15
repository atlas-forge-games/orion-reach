"""System-wide Wanderer research, private endpoints and direct route controls."""

import math
import pygame as pg

from . import hyperlanes as rules, motherships
from .hyperlane_art import draw_art, draw_portal, LANE_COLOR
from .model import RuleError
from .ui import CYAN, FAINT, GOLD, INK, LINE, MUTED, panel, paragraph, shorten, text

CONNECTIONS_PER_PAGE = 3


def perform(app, action):
    try:
        message = action()
        app.save_game(autosave=True)
        app.toast(message if isinstance(message, str) else "Hyperlane research updated")
    except RuleError as exc:
        app.toast(exc, True)


def plot(app, destination):
    ships = app.game.fleet_at(app.game.selected_system)
    if not ships:
        app.toast("Bring a fleet to this endpoint to use the hyperlane.", True)
        return
    app.open_map_fleet(ships[0].id)
    app.game.selected_system = destination
    app.ensure_map_system(destination)
    app.mouse = (-1, -1)


def draw_system_portal(app, system):
    if not motherships.is_wanderer(app.game):
        return
    project = rules.project_at(app.game, system.id)
    destinations = rules.connections(app.game, system.id)
    if project is None and not destinations:
        return
    draw_portal(app.canvas, (313, 469), 25, bool(destinations))
    app.button("system_hyperlane_portal", "", (283, 439, 60, 60), lambda: app.go("hyperlane"), "hotspot")
    caption = f"{len(destinations)} HYPERLANE{'S' if len(destinations) != 1 else ''}" if destinations else f"HYPERLANE · {project.progress}/{project.cost} RP"
    text(app.canvas, caption, (88, 590), 10, LANE_COLOR, "mono")


def draw_hyperlane(app):
    game, surface = app.game, app.canvas
    system = game.systems[game.selected_system]
    app.chrome("FORGOTTEN HYPERLANES")
    app.button("hyperlane_back", "← Solar system", (64, 126, 220, 46), lambda: app.go("system"))
    text(surface, "WANDERER NAVIGATION QUEST", (1376, 142), 11, GOLD, "mono", right=True)
    text(surface, shorten(system.name+" · Forgotten hyperlanes", 1300, 37, "title"), (64, 193), 37, INK, "title")
    text(surface, "System research · Random destination · Permanent two-way passage · Only your empire can use it", (67, 251), 14, MUTED)
    if not motherships.is_wanderer(game):
        paragraph(surface, "Only the Wanderers can decipher these ancient navigation paths.", (64, 319), 800, 24, MUTED, 34)
        return
    panel(surface, (64, 290, 722, 389), (6, 17, 26))
    draw_art(surface, (76, 302, 698, 343))
    text(surface, "ANCIENT PATHS BETWEEN DISTANT STARS", (85, 653), 10, GOLD, "mono", 1)
    panel(surface, (810, 290, 566, 389))
    project = rules.project_at(game, system.id)
    points = rules.local_research(game, system.id)
    destinations = rules.connections(game, system.id)
    editable = game.strategy_error() is None
    if project is None:
        text(surface, f"{rules.RESEARCH_COST} RP", (832, 314), 35, LANE_COLOR, "title")
        paragraph(surface, "Recover a forgotten route to a random star system. The destination is revealed when research finishes.", (832, 373), 518, 18, INK, 28)
        paragraph(surface, "Station a mothership here. Pool local research from every stationary home, or invest banked RP. This leaves the megastructure slot available.", (832, 465), 518, 14, MUTED, 23)
        reason = rules.start_error(game, system.id)
        text(surface, f"Local research available: {points} RP / turn", (832, 555), 14, CYAN)
        app.button("hyperlane_start", f"Start research · {rules.RESEARCH_COST} RP", (832, 594, 518, 43),
                   lambda: perform(app, lambda: rules.start(game, system.id)), "primary", enabled=reason is None)
        if reason:
            text(surface, shorten(reason, 518, 11), (832, 651), 11, MUTED)
    elif project.complete:
        text(surface, "HYPERLANE RECOVERED", (832, 316), 12, GOLD, "mono", 1)
        text(surface, shorten(game.systems[project.destination].name, 514, 33, "title"), (832, 357), 33, INK, "title")
        text(surface, "1 TURN · BOTH DIRECTIONS", (832, 415), 17, LANE_COLOR, "mono")
        paragraph(surface, "Every ship in your empire can use this passage, including motherships and their escorts. Normal fuel range and travel speed do not limit the jump.", (832, 461), 518, 15, MUTED, 25)
        paragraph(surface, "The route remains available after your homes leave. It reveals no planets or fleets before arrival; guardians and hostile fleets still defend the destination.", (832, 559), 518, 13, MUTED, 22)
        text(surface, f"Completed on turn {project.completed_turn} · {project.cost} RP invested", (832, 650), 11, GOLD)
    else:
        contribution = rules.contribution(game, project)
        text(surface, f"{project.progress} / {project.cost} RP", (832, 315), 31, INK, "title")
        pg.draw.rect(surface, LINE, (832, 363, 518, 7))
        pg.draw.rect(surface, LANE_COLOR, (832, 363, round(518*project.progress/project.cost), 7))
        text(surface, "Destination unknown until completion", (832, 388), 14, MUTED)
        eta = math.ceil((project.cost-project.progress)/contribution) if contribution else None
        text(surface, f"Local output: {points} RP · Assigned: {contribution} RP / turn"+(f" · {eta} turns" if eta else ""), (832, 425), 13, CYAN)
        text(surface, "SHARE OF THIS SYSTEM'S RESEARCH", (832, 463), 10, GOLD, "mono", 1)
        for index, value in enumerate((0, 25, 50, 75, 100)):
            app.button(f"hyperlane_allocation_{value}", f"{value}%", (832+index*106, 486, 94, 34),
                       lambda n=value: perform(app, lambda: rules.configure(game, system.id, allocation=n)),
                       "primary" if project.allocation == value else "normal", enabled=editable)
        amount = min(game.research, project.cost-project.progress)
        reason = rules.work_error(game, system.id)
        app.button("hyperlane_pause", "Resume" if project.paused else "Pause", (832, 540, 142, 38),
                   lambda: perform(app, lambda: rules.configure(game, system.id, paused=not project.paused)), enabled=editable)
        app.button("hyperlane_invest", f"Invest reserve · {amount} RP", (986, 540, 364, 38),
                   lambda: perform(app, lambda: rules.invest(game, system.id)), enabled=editable and amount > 0 and reason is None)
        status = reason or ("Research paused; progress is retained." if project.paused else
                            "Assign scientists aboard the mothership to produce RP." if not points else
                            "Choose a research share to resume progress." if not project.allocation else
                            "Assigned RP funds this project; the rest supports ordinary research.")
        paragraph(surface, status, (832, 599), 518, 13, MUTED, 21)
    if app.hyperlane_system != system.id:
        app.hyperlane_system, app.hyperlane_page = system.id, 0
    last = max(0, (len(destinations)-1)//CONNECTIONS_PER_PAGE)
    app.hyperlane_page = min(app.hyperlane_page, last)
    text(surface, "KNOWN CONNECTIONS FROM THIS SYSTEM", (66, 704), 11, GOLD, "mono", 1)
    if last:
        for name, step, x, enabled in (("previous", -1, 1260, app.hyperlane_page > 0), ("next", 1, 1320, app.hyperlane_page < last)):
            app.button("hyperlane_"+name, "←" if step < 0 else "→", (x, 695, 50, 28),
                       lambda delta=step: setattr(app, "hyperlane_page", app.hyperlane_page+delta), enabled=enabled)
    start = app.hyperlane_page*CONNECTIONS_PER_PAGE
    for i, sid in enumerate(destinations[start:start+CONNECTIONS_PER_PAGE]):
        x = 64+i*445
        panel(surface, (x, 737, 422, 103), border=LANE_COLOR)
        draw_portal(surface, (x+25, 763), 15)
        text(surface, shorten(game.systems[sid].name, 335, 21), (x+53, 752), 21, INK)
        app.button(f"hyperlane_view_{sid}", "View endpoint", (x+15, 798, 177, 34), lambda target=sid: app.open_system(target))
        app.button(f"hyperlane_plot_{sid}", "Plot course · 1 turn", (x+207, 798, 199, 34), lambda target=sid: plot(app, target),
                   enabled=editable and bool(game.fleet_at(system.id)))
    if not destinations:
        text(surface, "No recovered connections here yet. Research opens one permanent route.", (66, 759), 16, MUTED)
    text(surface, "One discovery per system · Incoming routes also work in reverse · No research points are spent on travel", (66, 871), 12, MUTED)
    app.button("hyperlane_end_turn", "End turn · E", (1100, 851, 276, 40), app.advance_turn, enabled=editable)
