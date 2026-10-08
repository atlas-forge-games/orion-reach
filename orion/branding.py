"""Studio branding using the supplied Atlas Forge logo, without altering the asset."""

import pygame as pg

from .art import SIZE
from .ui import ASSETS, GOLD, INK, MUTED, text, text_image

STUDIO_NAME = "Atlas Forge Games"
SPLASH_SECONDS = 2.5
FADE_SECONDS = .25


def centered(surface, value, y, size, color=INK, family="sans", spacing=0):
    label = text_image(value, size, color, family, spacing)
    surface.blit(label, label.get_rect(midtop=(surface.get_width()//2, y)))


class StudioBrand:
    def __init__(self):
        try:
            self.logo = pg.image.load(str(ASSETS / "branding" / "atlas-forge-logo.jpg")).convert()
        except (OSError, pg.error):
            self.logo = None
        self.scaled = {}
        self.splash = pg.Surface(SIZE).convert()
        self.splash.fill((0, 0, 0))
        centered(self.splash, "A GAME BY", 55, 12, GOLD, "mono", 3)
        logo = self.fitted_logo((660, 660))
        if logo is not None:
            self.splash.blit(logo, (390, 98))
        else:
            centered(self.splash, "ATLAS FORGE", 379, 52, INK, "title", 3)
            centered(self.splash, "GAMES", 462, 21, GOLD, "sans", 6)
        centered(self.splash, STUDIO_NAME.upper(), 782, 19, INK, "sans", 3)
        centered(self.splash, "Click or press any key to continue", 846, 12, MUTED)

    def fitted_logo(self, size):
        if self.logo is None:
            return None
        if size not in self.scaled:
            frame = pg.Surface(size).convert()
            frame.fill((0, 0, 0))
            fitted = self.logo.get_rect().fit(frame.get_rect())
            frame.blit(pg.transform.smoothscale(self.logo, fitted.size), fitted)
            self.scaled[size] = frame
        return self.scaled[size]

    def draw_splash(self, surface, elapsed, animated=True):
        surface.fill((0, 0, 0))
        opacity = min(1, max(0, elapsed/FADE_SECONDS), max(0, (SPLASH_SECONDS-elapsed)/FADE_SECONDS))
        self.splash.set_alpha(round(255*opacity) if animated else 255)
        surface.blit(self.splash, (0, 0))

    def draw_menu_credit(self, surface):
        logo = self.fitted_logo((48, 48))
        if logo is not None:
            surface.blit(logo, (527, 842))
        text(surface, "A GAME BY", (589, 846), 8, MUTED, "mono", 2)
        text(surface, STUDIO_NAME, (588, 861), 13, INK)
