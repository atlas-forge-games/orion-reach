"""Black-hole map sprites and expedition intelligence, with private relic claims."""

from functools import lru_cache
import math
import pygame as pg

from . import black_holes, monsters
from .ui import ASSETS, CYAN, GOLD, INK, LINE, MUTED, RED, panel, paragraph, shorten, text


@lru_cache(maxsize=12)
def artwork(kind, width, height):
    try:
        source = pg.image.load(str(ASSETS / "black_holes" / f"{kind}-v1.png"))
        return pg.transform.smoothscale(source, (width, height))
    except (OSError, pg.error):
        return None


def hit_rect(center):
    return pg.Rect(round(center[0])-28, round(center[1])-21, 56, 42)


def draw_art(surface, kind, rect):
    rect = pg.Rect(rect)
    color = black_holes.SITES[kind][2]
    # An opaque core keeps stars behind the transparent sprite from shining through.
    pg.draw.circle(surface, (1, 3, 6), rect.center, max(4, rect.h//5))
    picture = artwork(kind, rect.w, rect.h)
    if picture is not None:
        surface.blit(picture, rect)
    else:
        ring = rect.inflate(-rect.w//5, -rect.h//3)
        pg.draw.ellipse(surface, color, ring, max(1, rect.w//140))
        pg.draw.circle(surface, (1, 3, 6), rect.center, max(4, rect.h//5))


def draw_marker(app, star, selected=False):
    site = black_holes.at(app.game, star.id)
    x, y = app.star_pos(star)
    rect = hit_rect((x, y))
    draw_art(app.canvas, site.kind, pg.Rect(round(x)-30, round(y)-20, 60, 40))
    if selected:
        pg.draw.ellipse(app.canvas, GOLD, rect.inflate(6, 8), 1)
    elif app.settings.get("animated_background", True):
        angle = (app.time*.16) % math.tau
        pg.draw.arc(app.canvas, black_holes.SITES[site.kind][2], rect.inflate(2, 2), angle, angle+.6, 1)
    app.map_button(f"star_{star.id}", rect, lambda: app.select_star(star.id))


def open_guide(app, relic_id=None):
    app.open_info()
    app.select_info_category("artifacts" if relic_id else "basics")
    app.select_info_article("artifact_"+relic_id if relic_id else "black_holes")


def open_navigation(app):
    app.open_research()
    app.select_research_branch("computers")
    app.select_research_tier(7)


def draw_panel(app, star):
    game, surface = app.game, app.canvas
    site = black_holes.at(game, star.id)
    if site is None or not black_holes.charted(game, star):
        return
    x, width = 1075, 277
    color = black_holes.SITES[site.kind][2]
    panel(surface, (1051, 180, 325, 573))
    text(surface, "BLACK HOLE", (x, 203), 10, color, "mono", 1)
    text(surface, shorten(star.name, width, 28, "title"), (x, 236), 28, INK, "title")
    draw_art(surface, site.kind, (1067, 278, 293, 195))
    paragraph(surface, black_holes.SITES[site.kind][3], (x, 466), width, 13, MUTED, 21)
    pg.draw.line(surface, LINE, (x, 522), (x+width, 522))
    status = monsters.known_status(game, star.id)
    own_relic = site.claimed_by == "player"
    live = game.system_visible(star.id)
    recovered = own_relic or status == "defeated"
    safe = black_holes.can_explore(game) or game.is_observer
    if recovered:
        heading, tint = "RELIC RECOVERED", GOLD
        detail = (f"{black_holes.RELICS[site.relic_id].name}. "
                  + ("In your collection." if own_relic else f"Held by {game.empire_name_for(site.claimed_by)}.")) if own_relic or live else "The guardian was defeated. The relic is no longer available."
    elif not safe:
        heading, tint = "UNSAFE APPROACH", RED
        detail = "All arriving ships will be lost. Research Event Horizon Navigation for a safe approach."
    elif status == "alive":
        heading, tint = "LEGENDARY GUARDIAN", color
        guardian = monsters.at(game, star.id)
        detail = f"{guardian.spec.name}. Defeat it to recover the relic from the ancient site outside the horizon."
    else:
        heading, tint = "EXPEDITION READY", CYAN
        detail = "Send a strong fleet to explore the ancient site outside the horizon. Expect a legendary guardian."
    text(surface, heading, (x, 540), 11, tint, "mono_bold")
    paragraph(surface, detail, (x, 568), width, 14, MUTED, 22)
    if app.route_ship_id is not None:
        return  # The existing course confirmation occupies the bottom of this panel.
    if own_relic or (recovered and live):
        app.button("black_hole_relic", "View recovered relic", (x, 657, width, 37),
                   lambda: open_guide(app, site.relic_id), "command", icon="info")
    elif not safe:
        app.button("black_hole_navigation", "Research safe navigation", (x, 657, width, 37),
                   lambda: open_navigation(app), "command", icon="research")
    elif not game.is_observer:
        app.button("black_hole_fleets", "Choose an expedition fleet", (x, 657, width, 37),
                   app.open_fleets, "command", icon="fleets")
    app.button("black_hole_guide", "Expedition guide", (x, 706, width, 31),
               lambda: open_guide(app), "command", icon="info")
