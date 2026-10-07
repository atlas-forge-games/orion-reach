"""Campaign setup with player and rival race selection."""

import pygame as pg

from .model import GALAXY_SIZES
from .race_art import draw_race_emblem
from .races import RACES
from .ui import GOLD, INK, MUTED, panel, paragraph, text


def draw_setup(app):
    surface = app.canvas
    app.chrome("NEW EXPEDITION", lambda: app.go("menu"))
    text(surface, "Every empire starts somewhere.", (64, 191), 42, INK, "title")
    text(surface, "Choose your civilization, name your empire, and chart a new galaxy.", (66, 254), 15, MUTED)
    app.input_box("empire", "EMPIRE NAME", app.empire, (64, 331, 536, 57), "Your civilization")
    app.input_box("seed", "GALAXY SEED · OPTIONAL", app.seed, (621, 331, 274, 57), "Random")
    paragraph(surface, "The same seed and size create the same stars. Every race starts on Earth in this prototype.",
              (925, 334), 427, 14, MUTED, 23)
    text(surface, "GALAXY SIZE", (64, 418), 11, MUTED, "mono", 1)
    for i, (size, count) in enumerate(GALAXY_SIZES.items()):
        x = 64+i*181
        app.button("size_"+size, size, (x, 447, 174, 42), lambda s=size: app.choose_size(s))
        if app.size == size:
            pg.draw.line(surface, GOLD, (x, 489), (x+174, 489), 2)
    text(surface, f"{GALAXY_SIZES[app.size]} star systems", (638, 461), 14, MUTED)
    text(surface, "YOUR RACE", (64, 520), 11, GOLD, "mono", 2)
    text(surface, "Races shape diplomacy; colony production and construction costs stay the same.", (1376, 520), 12, MUTED, right=True)
    for i, race in enumerate(RACES.values()):
        x = 64+i*446
        rect = pg.Rect(x, 549, 420, 221)
        selected = app.race_id == race.id
        panel(surface, rect, border=race.color if selected else (38, 57, 68))
        app.button("race_"+race.id, "", rect, lambda rid=race.id: app.choose_race(rid), "hotspot")
        draw_race_emblem(surface, race.id, (x+49, 600), 31)
        text(surface, race.name, (x+98, 573), 27, race.color if selected else INK, "title")
        text(surface, race.focus, (x+100, 614), 13, MUTED)
        paragraph(surface, race.description, (x+23, 651), 374, 14, MUTED, 23)
        text(surface, race.trait, (x+23, 740), 12, race.color)
        if selected:
            pg.draw.circle(surface, race.color, (x+396, 570), 4)
    text(surface, "RIVAL RACE", (64, 800), 10, MUTED, "mono", 1)
    for i, race in enumerate(RACES.values()):
        x = 64+i*153
        app.button("rival_race_"+race.id, race.name, (x, 823, 142, 43), lambda rid=race.id: app.choose_rival_race(rid))
        if app.rival_race_id == race.id:
            pg.draw.line(surface, race.color, (x, 866), (x+142, 866), 2)
    text(surface, "One rival empire: Helios Directorate", (548, 839), 13, MUTED)
    app.button("launch", "Begin expedition", (966, 815, 410, 57), app.start_game, "primary")
