"""Layered title artwork and real menu controls for Age of the Stars."""

from functools import lru_cache
import math
import pygame as pg

from . import __version__
from .art import SIZE
from .ui import ASSETS, GOLD, INK, MUTED, arrow, emblem, text, text_image

ART_DIR = ASSETS / "title"
LOGO_RECT = pg.Rect(50, 32, 550, 400)
FLEET_RECT = pg.Rect(1055, 607, 355, 200)


@lru_cache(maxsize=3)
def artwork(name):
    try:
        source = pg.image.load(str(ART_DIR / f"{name}-v1.png"))
        return source.convert() if name == "background" else source.convert_alpha()
    except (OSError, pg.error):
        return None


@lru_cache(maxsize=8)
def fitted_artwork(name, size):
    source = artwork(name)
    if source is None:
        return None
    if name == "background":
        # Cover the 16:10 game canvas without stretching the spherical planet.
        scale = max(size[0]/source.get_width(), size[1]/source.get_height())
        target = tuple(math.ceil(edge*scale) for edge in source.get_size())
    else:
        target = source.get_rect().fit(pg.Rect((0, 0), size)).size
    return pg.transform.smoothscale(source, target)


class TitleArt:
    def __init__(self):
        self.sparkles = pg.Surface(SIZE, pg.SRCALPHA)

    def draw(self, app):
        surface = app.canvas
        background = fitted_artwork("background", SIZE)
        if background is None:
            app.backdrop.draw(surface, app.time, app.settings["animated_background"], True)
        else:
            surface.blit(background, (0, 0))
        animated = app.settings["animated_background"]
        t = app.time if animated else 0.0
        self.sparkles.fill((0, 0, 0, 0))
        for index, (x, y) in enumerate(((44, 114), (540, 95), (645, 174), (586, 372),
                                       (35, 682), (644, 559), (561, 814))):
            alpha = round(70+45*math.sin(t*.45+index*1.7))
            drift = math.sin(t*.07+index)*1.5 if animated else 0
            pg.draw.circle(self.sparkles, (176, 207, 244, alpha), (round(x+drift), y), 1)
        surface.blit(self.sparkles, (0, 0))
        fleet = fitted_artwork("fleet", FLEET_RECT.size)
        if fleet is not None:
            position = fleet.get_rect(center=FLEET_RECT.center)
            if animated:
                position.move_ip(round(-8*math.sin(t*.09)), round(-4*math.sin(t*.11)))
            surface.blit(fleet, position)
        logo = fitted_artwork("logo", LOGO_RECT.size)
        if logo is not None:
            surface.blit(logo, logo.get_rect(center=LOGO_RECT.center))
        else:
            emblem(surface, LOGO_RECT.centerx, 160, 2.5)
            for label, y, size, spacing in (("AGE OF THE", 269, 25, 6), ("STARS", 312, 64, 7)):
                title = text_image(label, size, INK, "title", spacing)
                surface.blit(title, title.get_rect(midtop=(LOGO_RECT.centerx, y)))


@lru_cache(maxsize=12)
def button_fill(size, primary, active, pressed):
    fill = pg.Surface(size, pg.SRCALPHA)
    if primary:
        for y in range(size[1]):
            highlight = max(0, 1-abs(y/(size[1]-1)-.30))
            strength = 12 if pressed else 26 if active else 19
            fill.fill((round(42+highlight*strength), round(32+highlight*strength*.7),
                       round(20+highlight*strength*.3), 225), (0, y, size[0], 1))
    elif active:
        fill.fill((32, 39, 48, 208 if not pressed else 245))
    return fill


def draw_title_button(button, surface, active=False, pressed=False):
    r = button.rect
    active = active and button.enabled
    primary = button.style == "title_primary"
    surface.blit(button_fill(r.size, primary, active, pressed), r)
    if primary:
        pg.draw.rect(surface, (255, 226, 172) if active else GOLD, r, 1, border_radius=2)
        pg.draw.line(surface, (113, 90, 56), (r.x+2, r.y+2), (r.right-3, r.y+2))
    else:
        pg.draw.line(surface, (82, 82, 77), (r.left, r.bottom-1), (r.right, r.bottom-1))
    color = GOLD if active else INK if button.enabled else MUTED
    label = text_image(button.label, 27, color, "title")
    offset = 1 if pressed else 0
    surface.blit(label, (r.x+30, r.centery-label.get_height()//2+offset))
    arrow(surface, (r.right-29, r.centery+offset), color if primary or active else MUTED)
    if active:
        pg.draw.rect(surface, GOLD, r.inflate(6, 6), 1, border_radius=3)


def draw_menu(app):
    if app.title_art is None:
        app.title_art = TitleArt()
    app.title_art.draw(app)
    actions = [("new", "New Game", lambda: app.go("race_select")),
               ("load", "Load Game", lambda: app.go("load")),
               ("settings", "Settings", lambda: app.show_settings()),
               ("quit", "Quit", app.quit_request)]
    if app.game:
        actions.insert(0, ("resume", "Continue", lambda: app.go(app.campaign_view)))
    top, height, step = (446, 58, 67) if app.game else (462, 66, 80)
    for index, (key, label, action) in enumerate(actions):
        app.button(key, label, (94, top+index*step, 442, height), action,
                   "title_primary" if index == 0 else "title_menu")
    text(app.canvas, f"PROTOTYPE  /  {__version__}", (1398, 24), 10, MUTED, "mono", 1, right=True)
    pg.draw.line(app.canvas, (101, 109, 115), (32, 837), (1408, 837))
    app.brand.draw_menu_credit(app.canvas)
    text(app.canvas, "MOUSE / ↑ ↓ + ENTER", (635, 860), 9, MUTED, "mono", 1)
    app.button("about", "About the prototype", (1174, 844, 234, 42), lambda: app.go("about"), "ghost")
