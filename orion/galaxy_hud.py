"""Illustrated empire resources and the galaxy's bottom command bar."""

from functools import lru_cache

import pygame as pg

from .command_buttons import command_icon
from .empire import summarize_empire
from . import news
from .research import TECHNOLOGIES
from .ui import ASSETS, CYAN, GOLD, INK, LINE, MUTED, RED, emblem, font, panel, shorten, text

RESOURCE_RECTS = tuple((270+i*223, 22, 213, 100) for i in range(5))
FOOD_GREEN = (157, 199, 132)
NAVIGATION = (
    ("open_empire", "Empire", "open_empire", "empire", "I"),
    ("open_diplomacy", "Diplomacy", "open_diplomacy", "diplomacy", "D"),
    ("pause", "Menu", "pause", "menu", "Esc"),
    ("open_fleets", "Fleets", "open_fleets", "fleets", "F"),
    ("open_objectives", "Objectives", "open_objectives", "objectives", "V"),
    ("open_news", "Turn news", "open_news", "news", "N"),
)
COMMAND_RECTS = ((64, 813, 204, 61), (280, 813, 204, 61),
                 (496, 813, 132, 61), (640, 813, 132, 61),
                 (784, 813, 132, 61), (928, 813, 132, 61))


@lru_cache(maxsize=5)
def resource_art(kind):
    try:
        original = pg.image.load(str(ASSETS / "resources" / f"{kind}-v1.png"))
        return pg.transform.smoothscale(original, (58, 58))
    except (OSError, pg.error):
        # Older installs remain usable if the optional images have not arrived.
        if kind in ("resources", "energy"):
            from .planet_view import resource_icon
            art = pg.Surface((58, 58), pg.SRCALPHA)
            resource_icon(art, kind, (29, 29), GOLD if kind == "energy" else (204, 163, 122), 1.7)
            return art
        icon = {"credits": "empire", "research": "research", "food": "system"}[kind]
        return command_icon(icon, 58, CYAN)


def resource_card(surface, rect, kind, title, value, detail, footnote, accent, *, detail_color=MUTED):
    r = pg.Rect(rect)
    panel(surface, r, (9, 20, 29))
    surface.blit(resource_art(kind), (r.x+5, r.y+28))
    pg.draw.line(surface, LINE, (r.x+66, r.y+13), (r.x+66, r.bottom-13))
    x, width = r.x+75, r.w-82
    text(surface, title, (x, r.y+8), 9, accent, "mono", 1)
    size = 20
    while size > 13 and font(size, "mono").size(value)[0] > width:
        size -= 1
    text(surface, shorten(value, width, size, "mono"), (x, r.y+27), size, accent, "mono")
    text(surface, shorten(detail, width, 10), (x, r.y+61), 10, detail_color)
    text(surface, shorten(footnote, width, 9), (x, r.y+80), 9, MUTED)


def draw_galaxy_header(app):
    game, surface = app.game, app.canvas
    report = summarize_empire(game)
    emblem(surface, 225, 61, .46)
    text(surface, "ORION", (65, 36), 24, INK, spacing=3)
    text(surface, "REACH", (65, 66), 24, INK, spacing=3)
    text(surface, "GALAXY COMMAND", (66, 106), 9, MUTED, "mono", 1)
    resource_card(surface, RESOURCE_RECTS[0], "credits", "CREDITS", f"{game.credits:,} CR",
                  f"{report.income:+,} CR net / turn", f"Upkeep {report.maintenance:,} CR/turn",
                  GOLD, detail_color=RED if report.income < 0 else MUTED)
    active = game.research_state().active
    resource_card(surface, RESOURCE_RECTS[1], "research", "RESEARCH · R", f"{game.research:,} RP",
                  f"{report.research:+,} RP / turn",
                  TECHNOLOGIES[active].name if active else "No active project", CYAN)
    app.button("open_research", "", RESOURCE_RECTS[1], app.open_research, "hotspot")
    if active:
        app.technology_info_region(active, RESOURCE_RECTS[1])
    if active is None and any(game.technology.status(t)=="available" for t in TECHNOLOGIES):
        pg.draw.rect(surface, GOLD, RESOURCE_RECTS[1], 1, border_radius=3)
    shortage = report.food_shortages
    food_note = f"{shortage} local shortage"+("s" if shortage != 1 else "") if shortage else "Local · All supplied"
    resource_card(surface, RESOURCE_RECTS[2], "food", "FOOD SURPLUS",
                  f"{report.food_produced-report.food_consumed:+,} / turn",
                  f"{report.food_produced:,} made / {report.food_consumed:,} used", food_note,
                  RED if shortage else FOOD_GREEN)
    resource_card(surface, RESOURCE_RECTS[3], "resources", "RESOURCES", f"{game.resources:,} RES",
                  f"{report.resources:+,} RES / turn", "Net after power fuel", (204, 163, 122))
    resource_card(surface, RESOURCE_RECTS[4], "energy", "LOCAL ENERGY",
                  f"{report.energy_generated:,}/{report.energy_demand:,}", "Generated / needed",
                  f"{report.energy_shortages} shortages · View" if report.energy_shortages else "All supplied · View",
                  RED if report.energy_shortages else GOLD)
    def show_energy():
        app.open_empire()
        app.empire_filter = "power" if report.energy_shortages else "all"
    app.button("energy_report", "", RESOURCE_RECTS[4], show_energy, "hotspot")
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
        if game.is_observer and key == "open_empire":
            label = "Empires"
        badge = (str(min(unread, 99))+("+" if unread > 99 else "")) if key == "open_news" and unread else ""
        if key == "pause" and (app.fleet_popup or app.map_order_ids or app.route_ship_id is not None or app.sensor_contact_id is not None):
            shortcut = "P"  # Escape closes the active map selection first.
        app.button(key, label, COMMAND_RECTS[index], getattr(app, method),
                   "command_dock", icon=icon, shortcut=shortcut, badge=badge)
    app.button("end_turn", "End turn", (1081, 813, 295, 61), app.advance_turn, "command_primary",
               subtitle=f"Turn {game.turn+1} · Year {game.year+1}", icon="turn", shortcut="E")
