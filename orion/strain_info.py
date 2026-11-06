"""On-demand explanation of a colony's current administrative strain."""

from . import administration
from .production_breakdown import Breakdown


def describe(game, planet):
    report = game.strain_report(planet)
    lines = [
        f"TOTAL STRAIN: {report.total:.1f}%",
        f"Empire size: {report.empire:g}% · {report.systems} settled system{'s' if report.systems != 1 else ''}.",
        f"Integration: {report.integration:g}% · {report.integrating} systems integrating.",
        f"Local distance: {report.distance:.1f}% · {report.distance_ly:.1f} ly from capital {report.capital}.",
        f"Combined before cap: {report.uncapped:.1f}% · Cap: {administration.MAX_STRAIN:g}%.",
        f"Facility relief: {report.relief:g} percentage points from powered administration buildings, after the cap.",
        (f"This system finishes integration in {report.integration_remaining} turns."
         if report.integration_remaining else "This system is fully integrated."),
        "OUTPUT REDUCTIONS",
        f"Research: {report.loss('research'):.1f}% · Credits: {report.loss('credits'):.1f}%",
        f"Industry: {report.loss('industry'):.1f}% · Resources: {report.loss('mining'):.1f}% · Food: {report.loss('food'):.1f}%",
        "Energy is unaffected by strain.",
        "Empire size and integration affect all colonies. Distance affects this colony only.",
        "Reductions apply before upkeep and consumption. Whole-unit rounding and minimum output rules still apply.",
    ]
    return Breakdown("Administrative strain — "+planet.name, tuple(lines), report.total)


def draw(app):
    import pygame as pg
    from .ui import panel, text, shorten, wrapped_lines, INK, MUTED, GOLD, PANEL

    data, surface = app.dialog["strain_info"], app.canvas
    rect = pg.Rect(0, 0, min(960, surface.get_width()-48), min(690, surface.get_height()-48))
    rect.center = surface.get_rect().center
    width = rect.w-48
    lines = [part for line in data.lines for part in wrapped_lines(line, width, 16)]
    per_page = max(1, (rect.h-172)//26)
    pages = max(1, (len(lines)+per_page-1)//per_page)
    page = max(0, min(app.dialog.get("info_page", 0), pages-1))
    app.dialog["info_page"] = page
    panel(surface, rect, PANEL, GOLD)
    text(surface, shorten(data.title, width, 28, "title"), (rect.x+24, rect.y+24), 28, INK, "title")
    text(surface, shorten("CURRENT COLONY · administration and output losses", width, 12),
         (rect.x+24, rect.y+68), 12, MUTED)
    for i, line in enumerate(lines[page*per_page:(page+1)*per_page]):
        text(surface, line, (rect.x+24, rect.y+100+i*26), 16,
             GOLD if line.startswith("TOTAL ") or line == "OUTPUT REDUCTIONS" else INK)
    footer_y = rect.bottom-64
    if pages > 1:
        app.button("dialog_strain_previous", "←", (rect.x+24, footer_y, 44, 40),
                   lambda: app.dialog.update(info_page=page-1), enabled=page > 0)
        app.button("dialog_strain_next", "→", (rect.x+76, footer_y, 44, 40),
                   lambda: app.dialog.update(info_page=page+1), enabled=page+1 < pages)
        text(surface, f"{page+1} / {pages}", (rect.x+136, footer_y+12), 12, MUTED)
    else:
        text(surface, "Right-click or Esc to close", (rect.x+24, footer_y+12), 12, MUTED)
    close_width = max(128, rect.w//4)
    app.button("dialog_cancel", "Close", (rect.right-24-close_width, footer_y, close_width, 40),
               app.cancel_dialog, "primary")
