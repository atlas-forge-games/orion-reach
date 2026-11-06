"""Geometry shared by the strategic chart, its controls and pointer input."""
from dataclasses import dataclass

import pygame as pg


def split_row(left, top, width, height, count, gap):
    usable = width-gap*(count-1)
    return tuple(pg.Rect(left+i*gap+round(usable*i/count), top,
                         round(usable*(i+1)/count)-round(usable*i/count), height)
                 for i in range(count))


@dataclass(frozen=True)
class GalaxyLayout:
    size: tuple
    identity: pg.Rect
    cards: tuple
    chart: pg.Rect
    inspector: pg.Rect | None
    commands: tuple
    end_turn: pg.Rect
    galaxy_link: pg.Rect | None

    @classmethod
    def fit(cls, available, *, collapsed=False, system_view=False):
        width, height = available
        margin, gap, card_h = 18, 10, 72
        inner = width-2*margin
        columns = 6 if width >= 1150 else 3 if width >= 640 else 2
        slots = []
        for row in range(6//columns):
            slots.extend(split_row(margin, 10+row*(card_h+6), inner, card_h, columns, gap))
        top = slots[-1].bottom+gap
        stacked = width < 1120 and not collapsed
        double_dock = inner < (1230 if system_view else 950)
        dock_h = 116 if double_dock else 58
        panel_w = 338
        chart_w = inner if stacked or collapsed else inner-panel_w-gap
        # Give a stacked map enough height to plot a readable full galaxy.
        extra = 574+gap if stacked else 0
        if stacked:
            min_chart_h = max(375, round(chart_w*.52))
        else:
            min_chart_h = 375 if collapsed else 565
        footer = max(height-12-dock_h, top+min_chart_h+extra+gap)
        chart = pg.Rect(margin, top, chart_w, footer-gap-top-extra)
        inspector = None
        if stacked:
            inspector = pg.Rect(margin, footer-gap-574, inner, 574)
        elif not collapsed:
            inspector = pg.Rect(chart.right+gap, top, panel_w, footer-gap-top)
        if double_dock:
            first = 5 if system_view else 4
            dock = split_row(margin, footer, inner, 54, first, 6)
            second_y = footer+62
            if system_view:
                # Keep both destination names legible at the largest text size.
                end = pg.Rect(width-margin-160, second_y, 160, 54)
                back = pg.Rect(end.x-156, second_y, 150, 54)
                dock += split_row(margin, second_y, back.x-margin-6, 54, 2, 6)+(back, end)
            else:
                dock += split_row(margin, second_y, inner, 54, 4, 6)
        else:
            end_w = min(255, inner//5)
            end = pg.Rect(width-margin-end_w, footer, end_w, dock_h)
            main_w = inner-end_w-gap
            if system_view:
                back = pg.Rect(end.x-gap-179, footer, 179, dock_h)
                main_w -= back.w+gap
            dock = split_row(margin, footer, main_w, dock_h, 7, 7)
            dock += (back, end) if system_view else (end,)
        return cls((width, footer+dock_h+12), slots[0], tuple(slots[1:]), chart,
                   inspector, dock[:7], dock[-1], dock[-2] if system_view else None)

    @property
    def camera_tools(self):
        r = self.chart
        return pg.Rect(r.x+8, r.y+8, 247, 33)

    @property
    def panel_toggle(self):
        r = self.chart
        return pg.Rect(r.right-116, r.y+8, 108, 33)

    @property
    def sensors(self):
        toggle = self.panel_toggle
        return pg.Rect(toggle.x-108, toggle.y, 102, toggle.h)

    @property
    def order_strip(self):
        r = self.chart
        return pg.Rect(r.x+8, r.bottom-52, min(r.w-16, 595), 44)


DEFAULT_LAYOUT = GalaxyLayout.fit((1440, 900))
