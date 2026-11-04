"""Illustrated empire resources and the galaxy's bottom command bar."""

from functools import lru_cache

import pygame as pg

from .command_buttons import command_icon
from .display import Canvas
from .empire import summarize_empire
from . import news
from .research import TECHNOLOGIES
from . import hyperlanes
from .treasury import BANKRUPTCY_LIMIT, INTEREST_PERCENT
from .ui import ASSETS, CYAN, GOLD, INK, MUTED, RED, panel, shorten, text

FOOD_GREEN = (157, 199, 132)
NAVIGATION = (
    ("open_empire", "Empire", "open_empire", "empire", "I"),
    ("open_diplomacy", "Diplomacy", "open_diplomacy", "diplomacy", "D"),
    ("open_info", "Info", "open_info", "info", "F1"),
    ("pause", "Menu", "pause", "menu", "Esc"),
    ("open_fleets", "Fleets", "open_fleets", "fleets", "F"),
    ("open_objectives", "Objectives", "open_objectives", "objectives", "V"),
    ("open_news", "Turn news", "open_news", "news", "N"),
)


@lru_cache(maxsize=5)
def resource_art(kind):
    try:
        original = pg.image.load(str(ASSETS / "resources" / f"{kind}-v1.png"))
        return pg.transform.smoothscale(original, (256, 256))
    except (OSError, pg.error):
        # Older installs remain usable if the optional images have not arrived.
        if kind in ("resources", "energy"):
            from .planet_view import resource_icon
            art = pg.Surface((58, 58), pg.SRCALPHA)
            resource_icon(art, kind, (29, 29), GOLD if kind == "energy" else (204, 163, 122), 1.7)
            return art
        icon = {"credits": "empire", "research": "research", "food": "system"}[kind]
        return command_icon(icon, 64, CYAN)


@lru_cache(maxsize=60)
def scaled_resource_art(kind, pixels):
    return pg.transform.smoothscale(resource_art(kind), (pixels, pixels))


def resource_card(surface, r, kind, title, value, detail, accent, *, detail_color=MUTED):
    panel(surface, r, (9, 20, 29))
    x, width = r.x+11, r.w-22
    detail_width = width
    if kind:
        # On narrow cards leave the entire bottom line available for alerts.
        compact = r.w < 220
        size = 40 if compact else 56
        icon = pg.Rect(r.right-8-size, r.y+5 if compact else r.centery-size//2, size, size)
        width = icon.left-x-8
        if not compact:
            detail_width = width
        if isinstance(surface, Canvas):
            surface.blit_native(scaled_resource_art(kind, max(1, round(size*surface.scale))), icon.topleft)
        else:
            surface.blit(scaled_resource_art(kind, size), icon.topleft)
    text(surface, shorten(title, width, 14, "mono"), (x, r.y+4), 14, accent, "mono")
    text(surface, shorten(value, width, 21, "mono"), (x, r.y+22), 21, INK, "mono")
    text(surface, shorten(detail, detail_width, 14), (x, r.y+49), 14, detail_color)


def card_action(app, key, rect, action, hint):
    button = app.button(key, "", rect, action, "hotspot")
    if app.is_active(button):
        pg.draw.rect(app.canvas, CYAN, rect, 1, border_radius=3)
    app.canvas.text_regions.append((rect, hint))


def draw_identity(app, caption):
    r = app.galaxy_layout.identity
    game, surface = app.game, app.canvas
    x = r.x+4
    text(surface, shorten(game.empire_name, r.w-8, 23, "title"), (x, r.y+1), 23, INK, "title")
    text(surface, f"Year {game.year} · Turn {game.turn}", (x, r.y+30), 14, CYAN)
    text(surface, shorten(caption, r.w-8, 14), (x, r.y+50), 14, MUTED)


def draw_galaxy_header(app):
    game, surface = app.game, app.canvas
    report = summarize_empire(game)
    credits, research, food, resources, energy = app.galaxy_layout.cards
    unit = "mothership" if game.race_id == "wanderers" else "colony"
    plural = "motherships" if game.race_id == "wanderers" else "colonies"
    draw_identity(app, f"{report.colonies} {unit if report.colonies == 1 else plural} · {report.population:,} B population")

    bankrupt = game.credits+report.income <= BANKRUPTCY_LIMIT
    income = f"{report.income:+,} CR net / turn"
    resource_card(surface, credits, "credits", "CREDITS · DEBT" if game.credits < 0 else "CREDITS", f"{game.credits:,} CR",
                  "Bankruptcy next turn!" if bankrupt else income, RED if game.credits < 0 else GOLD,
                  detail_color=RED if bankrupt or report.income < 0 else MUTED)
    budget = (f"{report.gross_income:,} CR gross income. Upkeep {report.maintenance:,} CR, including "
              f"{game.fleet_maintenance():,} CR for ships. Interest {report.interest:,} CR. {income}.")
    if game.credits < 0:
        budget += f" Debt costs {INTEREST_PERCENT}% per turn. Bankruptcy at {BANKRUPTCY_LIMIT:,} CR."
    card_action(app, "credit_report", credits, lambda: app.show_resource_detail("Credit budget", budget, "credit_report"),
                "Open the credit budget and upkeep breakdown.")

    active = game.research_state().active
    idle = active is None and any(game.technology.status(t)=="available" for t in TECHNOLOGIES)
    rate = f"{report.research:+,} RP / turn"
    resource_card(surface, research, "research", "RESEARCH · R", f"{game.research:,} RP",
                  ("Idle · " if idle else "")+rate, CYAN, detail_color=GOLD if idle else MUTED)
    diverted = sum(hyperlanes.allocations(game, "player").values())
    project = TECHNOLOGIES[active].name if active else "No active project"
    card_action(app, "open_research", research, app.open_research, project+(f" · {diverted} RP to hyperlanes" if diverted else ""))
    if active:
        app.technology_info_region(active, research)
    if idle:
        pg.draw.rect(surface, GOLD, research, 1, border_radius=3)

    def shortage(count):
        return f"{count} local shortage"+("s" if count != 1 else "")
    supply = f"{report.food_produced:,} made / {report.food_consumed:,} used"
    resource_card(surface, food, "food", "FOOD SURPLUS", f"{report.food_produced-report.food_consumed:+,} / turn",
                  shortage(report.food_shortages) if report.food_shortages else supply, FOOD_GREEN,
                  detail_color=RED if report.food_shortages else MUTED)
    local = shortage(report.food_shortages) if report.food_shortages else "All colonies supplied"
    food_detail = f"{supply} per turn. {local}. Food is supplied locally."
    card_action(app, "food_report", food, lambda: app.show_resource_detail("Food supply", food_detail, "food_report"),
                "View food production, consumption and local shortages.")
    net = f"{report.resources:+,} RES / turn"
    resource_card(surface, resources, "resources", "RESOURCES", f"{game.resources:,} RES", net, (204, 163, 122))
    stocks = f"{game.resources:,} RES stored. {net} after fuel used for power generation."
    card_action(app, "resource_report", resources, lambda: app.show_resource_detail("Resource stockpile", stocks, "resource_report"),
                "View resource reserves and net production.")
    resource_card(surface, energy, "energy", "LOCAL ENERGY", f"{report.energy_generated:,}/{report.energy_demand:,}",
                  shortage(report.energy_shortages) if report.energy_shortages else "Generated / needed", GOLD,
                  detail_color=RED if report.energy_shortages else MUTED)
    def show_energy():
        app.open_empire()
        app.empire_filter = "power" if report.energy_shortages else "all"
    card_action(app, "energy_report", energy, show_energy, "Open the colony energy report.")


def draw_galaxy_commands(app, *, compact=False):
    game = app.game
    # The observer's separate report shares the actions but has its own footer.
    if compact:
        rects = tuple(pg.Rect(64+i*104, 813, 100, 61) for i in range(7))
    else:
        rects = app.galaxy_layout.commands
    unread = news.unread_count(game)
    for index, (key, label, method, icon, shortcut) in enumerate(NAVIGATION):
        if game.is_observer and key == "open_empire":
            label = "Empires"
        badge = (str(min(unread, 99))+("+" if unread > 99 else "")) if key == "open_news" and unread else ""
        if key == "pause" and (app.fleet_popup or app.map_order_ids or app.route_ship_id is not None or app.sensor_contact_id is not None):
            shortcut = "P"  # Escape closes the active map selection first.
        rect = rects[index]
        app.button(key, label, rect, getattr(app, method),
                   "command_dock", icon=icon, shortcut=shortcut, badge=badge)
    if not compact and app.galaxy_layout.galaxy_link is None:
        end = app.galaxy_layout.end_turn
        subtitle = f"Turn {game.turn+1} · Year {game.year+1}" if end.w >= 225 else ""
        app.button("end_turn", "End turn", end, app.advance_turn, "command_primary",
                   subtitle=subtitle, icon="turn" if end.w >= 220 else "", shortcut="E" if end.w >= 157 else "")
