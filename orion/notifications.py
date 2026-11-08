"""Quiet manual-save feedback; routine action confirmations have no overlay."""

import pygame as pg

from .ui import CYAN, PANEL, font, panel, text


def draw_saved(app):
    """A small, temporary status inside the visible view, away from the HUD."""
    if app.canvas.layout:
        with app.canvas.native_space():
            draw_saved(app)
        return
    visible = app.canvas.logical_rect(app.window.get_rect().move(-app.viewport.x, -app.viewport.y))
    visible = visible.clip(app.canvas.get_rect())
    label = "Saved ✓"
    width = font(14).size(label)[0]+24
    rect = pg.Rect(visible.left+18, visible.bottom-26, width, 24)
    if app.on_galaxy_chart() and not app.dialog:
        chart = app.galaxy_layout.chart.clip(visible)
        if chart.w >= width+16 and chart.h >= 40:
            rect.topleft = (chart.left+12, chart.bottom-36)
    rect.clamp_ip(visible)
    panel(app.canvas, rect, PANEL, CYAN)
    text(app.canvas, label, (rect.x+12, rect.y+3), 14, CYAN)
