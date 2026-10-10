"""First-contact transmissions using the game's original civilization portraits."""

import math
import pygame as pg

from . import first_contact
from .personalities import PERSONALITIES
from .race_art import draw_race_emblem, draw_race_portrait
from .races import RACES
from .ui import FAINT, INK, MUTED, panel, paragraph, shorten, text


def draw_contact(app):
    surface, game = app.canvas, app.game
    owner = app.contact_owner
    race = RACES[game._empire(owner).race_id]
    nature = PERSONALITIES[race.id]
    state = game.diplomacy_between("player", owner)
    accent = race.color
    collective = race.id == "concord"
    t = app.time if app.settings["animated_background"] else 0
    shade = pg.Surface((1440, 900), pg.SRCALPHA)
    shade.fill((2, 7, 13, 200))
    surface.blit(shade, (0, 0))
    # Racial geometry and a quiet signal animation frame the ambassador.
    draw_race_emblem(surface, race.id, (1209, 357), 224)
    panel(surface, (66, 134, 628, 668), (8, 16, 23), accent)
    for i in range(8):
        y = 158+i*88
        pg.draw.line(surface, tuple(c//5 for c in accent), (48, y), (78, y), 1)
        pg.draw.line(surface, tuple(c//5 for c in accent), (682, y), (712, y), 1)
    text(surface, "DIPLOMATIC TRANSMISSION", (68, 55), 12, accent, "mono", 3)
    text(surface, "First contact" if not app.contact_replay else "Transmission archive", (66, 79), 32, INK, "title")
    text(surface, f"TURN {state.contact_turn:03}", (1374, 85), 13, MUTED, "mono", right=True)
    text(surface, "COLLECTIVE UPLINK" if collective else "VISUAL CHANNEL ESTABLISHED", (96, 157), 10, accent, "mono", 2)
    draw_race_portrait(surface, race.id, (96, 191, 568, 568))
    for i in range(36):
        height = round(3+10*abs(math.sin(i*.7+t*2))*abs(math.cos(i*.27-t)))
        pg.draw.line(surface, accent, (108+i*7, 780-height), (108+i*7, 780+height), 2)
    text(surface, "ONE WILL · MANY VOICES" if collective else "TRANSLATION LINK STABLE", (646, 777), 9, MUTED, "mono", right=True)
    # Opaque message field preserves legibility over the larger racial seal.
    panel(surface, (728, 191, 646, 574), (9, 17, 25), tuple(c//4 for c in accent))
    text(surface, race.name.upper(), (758, 212), 12, accent, "mono", 2)
    text(surface, shorten(game.empire_name_for(owner), 582, 35, "title"), (756, 244), 35, INK, "title")
    paragraph(surface, nature.traits, (759, 310), 574, 16, accent, 24)
    pg.draw.line(surface, tuple(c//3 for c in accent), (759, 357), (1340, 357), 1)
    paragraph(surface, f'“{nature.greeting}”', (759, 382), 574, 27, INK, 39)
    text(surface, "CIVILIZATION DISPOSITION", (759, 609), 10, accent, "mono", 2)
    paragraph(surface, nature.summary, (759, 633), 574, 15, MUTED, 23)
    text(surface, f"RELATIONS  {state.attitude.upper()}  {state.relations:+}", (759, 731), 11, accent, "mono", 1)
    remaining = len(first_contact.pending(game))
    if app.contact_replay:
        app.button("contact_continue", "Return to diplomacy", (1014, 820, 360, 54), app.finish_contact, "primary")
        text(surface, "ARCHIVED GREETING · ESC TO RETURN", (68, 844), 11, FAINT, "mono", 1)
    else:
        text(surface, f"{remaining} TRANSMISSION{'S' if remaining != 1 else ''} AWAITING ACKNOWLEDGEMENT", (68, 840), 10, MUTED, "mono", 1)
        if remaining > 1:
            app.button("contact_skip", "Skip remaining introductions", (692, 820, 306, 54), app.skip_contacts, "ghost")
        app.button("contact_continue", "Acknowledge · Enter", (1014, 820, 360, 54), app.finish_contact, "primary")
