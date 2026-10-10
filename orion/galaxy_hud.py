"""Illustrated empire resources and the galaxy's bottom command bar."""

from functools import lru_cache

import pygame as pg

from .command_buttons import command_icon
from .empire import summarize_empire
from . import news
from .research import TECHNOLOGIES
from .ui import ASSETS, CYAN, GOLD, INK, LINE, MUTED, RED, emblem, font, panel, shorten, text

RESOURCE_RECTS = ((388, 22, 318, 100), (718, 22, 318, 100), (1048, 22, 328, 100))
FOOD_GREEN = (157, 199, 132)
NAVIGATION = (
    ("open_empire", "Empire", "open_empire", "empire", "I"),
    ("open_diplomacy", "Diplomacy", "open_diplomacy", "diplomacy", "D"),
    ("open_research", "Research", "open_research", "research", "R"),
    ("pause", "Menu", "pause", "menu", "Esc"),
    ("open_fleets", "Fleets", "open_fleets", "fleets", "F"),
    ("open_objectives", "Objectives", "open_objectives", "objectives", "V"),
    ("open_news", "Turn news", "open_news", "news", "N"),
)


@lru_cache(maxsize=3)
def resource_art(kind):
    try:
        original = pg.image.load(str(ASSETS / "resources" / f"{kind}-v1.png"))
        return pg.transform.smoothscale(original, (86, 86))
    except (OSError, pg.error):
        # Older installs remain usable if the optional images have not arrived.
        icon = {"credits": "empire", "research": "research", "food": "system"}[kind]
        return command_icon(icon, 86, CYAN)


def resource_card(surface, rect, kind, title, value, detail, footnote, accent, *, detail_color=MUTED):
    r = pg.Rect(rect)
    panel(surface, r, (9, 20, 29))
    surface.blit(resource_art(kind), (r.x+7, r.y+7))
    pg.draw.line(surface, LINE, (r.x+100, r.y+13), (r.x+100, r.bottom-13))
    x, width = r.x+113, r.w-126
    text(surface, title, (x, r.y+8), 10, accent, "mono", 1)
    size = 23
    while size > 13 and font(size, "mono").size(value)[0] > width:
        size -= 1
    text(surface, shorten(value, width, size, "mono"), (x, r.y+27), size, accent, "mono")
    text(surface, shorten(detail, width, 11), (x, r.y+61), 11, detail_color)
    text(surface, shorten(footnote, width, 10), (x, r.y+80), 10, MUTED)


def draw_galaxy_header(app):
    game, surface = app.game, app.canvas
    report = summarize_empire(game)
    emblem(surface, 80, 65, .72)
    text(surface, "ORION REACH", (115, 44), 19, INK, spacing=2)
    text(surface, "GALAXY COMMAND", (116, 75), 10, MUTED, "mono", 2)
    resource_card(surface, RESOURCE_RECTS[0], "credits", "CREDITS", f"{game.credits:,} CR",
                  f"{report.income:+,} CR net / turn", f"Building upkeep: {report.maintenance:,} CR / turn",
                  GOLD, detail_color=RED if report.income < 0 else MUTED)
    active = game.research_state().active
    resource_card(surface, RESOURCE_RECTS[1], "research", "RESEARCH", f"{game.research:,} RP",
                  f"{report.research:+,} RP / turn",
                  TECHNOLOGIES[active].name if active else "No active project", CYAN)
    shortage = report.food_shortages
    food_note = f"Local food · {shortage} {'colony' if shortage == 1 else 'colonies'} short" if shortage else "Local food · All colonies supplied"
    resource_card(surface, RESOURCE_RECTS[2], "food", "FOOD SURPLUS",
                  f"{report.food_produced-report.food_consumed:+,} / turn",
                  f"{report.food_produced:,} produced · {report.food_consumed:,} used", food_note,
                  RED if shortage else FOOD_GREEN)
    pg.draw.line(surface, LINE, (64, 129), (1376, 129))
    text(surface, shorten(game.empire_name, 550, 26, "title"), (64, 140), 26, INK, "title")
    text(surface, f"YEAR {game.year}   /   TURN {game.turn}", (718, 150), 12, CYAN, "mono")
    colonies = "COLONY" if report.colonies == 1 else "COLONIES"
    text(surface, f"{report.colonies} {colonies} · {report.population:,} B POPULATION",
         (1376, 151), 10, MUTED, "mono", right=True)


def draw_galaxy_commands(app):
    game = app.game
    pg.draw.line(app.canvas, LINE, (64, 801), (1376, 801))
    unread = news.unread_count(game)
    for index, (key, label, method, icon, shortcut) in enumerate(NAVIGATION):
        badge = (str(min(unread, 99))+("+" if unread > 99 else "")) if key == "open_news" and unread else ""
        if key == "pause" and (app.fleet_popup or app.map_order_ids or app.route_ship_id is not None or app.sensor_contact_id is not None):
            shortcut = "P"  # Escape closes the active map selection first.
        app.button(key, label, (64+index*144, 813, 132, 61), getattr(app, method),
                   "command_dock", icon=icon, shortcut=shortcut, badge=badge)
    app.button("end_turn", "End turn", (1081, 813, 295, 61), app.advance_turn, "command_primary",
               subtitle=f"Turn {game.turn+1} · Year {game.year+1}", icon="turn", shortcut="E")
