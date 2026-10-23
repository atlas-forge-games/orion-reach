"""Race-first, two-step expedition setup."""

import pygame as pg

from .model import GALAXY_SIZES
from .empires import MAX_RIVALS
from .race_art import draw_race_portrait
from .races import SETUP_RACES as RACES
from .personalities import PERSONALITIES
from .victory import CONDITIONS, CONDITION_NAMES
from .ui import GOLD, INK, MUTED, panel, paragraph, text


def draw_race_select(app):
    surface = app.canvas
    app.chrome("NEW EXPEDITION · 1 / 2", lambda: app.go("menu"))
    text(surface, "Choose your civilization.", (64, 191), 42, INK, "title")
    text(surface, f"{len(RACES)-1} civilizations to lead. Or choose The Observer and watch them play.", (66, 254), 15, MUTED)
    for i, race in enumerate(RACES.values()):
        x, y = 64+(i % 3)*270, 290+(i // 3)*100
        selected = app.race_id == race.id
        rect = pg.Rect(x, y, 254, 92)
        button = app.button("race_"+race.id, "", rect, lambda rid=race.id: app.choose_race(rid), "hotspot")
        panel(surface, rect, (23, 37, 45) if selected or app.is_active(button) else (12, 23, 32),
              race.color if selected else (38, 57, 68))
        draw_race_portrait(surface, race.id, (x+10, y+10, 72, 72))
        paragraph(surface, race.name, (x+94, y+10), 152, 14, race.color if selected else INK, 17)
        paragraph(surface, race.focus, (x+94, y+46), 152, 10, MUTED, 14)
        if selected:
            text(surface, "SELECTED", (x+94, y+78), 9, race.color, "mono", 1)
    race = RACES[app.race_id]
    panel(surface, (890, 290, 486, 510), border=race.color)
    draw_race_portrait(surface, race.id, (1033, 306, 200, 200))
    text(surface, race.name, (912, 520), 32, race.color, "title")
    text(surface, "Detached · Patient · Non-intervening" if race.id == "observer" else PERSONALITIES[race.id].traits, (914, 562), 12, INK)
    y = paragraph(surface, race.description, (914, 590), 436, 13, MUTED, 19)+12
    for trait in race.traits:
        y = paragraph(surface, "• "+trait, (914, y), 436, 11, race.color, 16)+4
    text(surface, "Next: galaxy options, rivals and victory conditions.", (66, 835), 14, MUTED)
    if race.id != 'observer':
        from .environments import race_caption
        text(surface, race_caption(race.id), (66, 803), 13, race.color)
    app.button("setup_next", "Continue → Galaxy options", (966, 815, 410, 57),
               lambda: app.go("setup"), "primary")


def draw_setup(app):
    surface = app.canvas
    race = RACES[app.race_id]
    observer = race.id == "observer"
    app.chrome("NEW EXPEDITION · 2 / 2", lambda: app.go("race_select"))
    text(surface, "Watch a galaxy unfold." if observer else "Chart your expedition.", (64, 191), 42, INK, "title")
    text(surface, "Every empire is computer-controlled. You decide when the next turn begins." if observer else "Set the stage for your civilization's first journey.", (66, 254), 15, MUTED)
    panel(surface, (64, 300, 338, 492), border=race.color)
    draw_race_portrait(surface, race.id, (115, 320, 236, 236))
    text(surface, race.name, (86, 578), 29, race.color, "title")
    text(surface, race.focus, (88, 620), 13, INK)
    text(surface, "Full galaxy visibility" if observer else f"Home system: {race.home_system}", (88, 654), 14, MUTED)
    text(surface, "No homeworld or fleet" if observer else f"Homeworld: {race.homeworld}", (88, 681), 14, MUTED)
    if not observer:
        from .environments import NATIVE_HOMES
        environment = 'Mobile habitat' if race.id == 'wanderers' else NATIVE_HOMES.get(race.id, 'Terran')
        text(surface, f"Home environment: {environment}", (88, 708), 12, race.color)
    app.button("setup_back", "← Change race", (86, 733, 294, 42), lambda: app.go("race_select"))
    app.input_box("empire", "OBSERVATION NAME" if observer else "EMPIRE NAME", app.empire, (430, 325, 586, 55), "Your civilization")
    app.input_box("seed", "GALAXY SEED · OPTIONAL", app.seed, (1034, 325, 342, 55), "Random")
    text(surface, "Reuse a seed and the same settings to repeat this galaxy and its starting positions.", (431, 400), 13, MUTED)
    text(surface, "GALAXY SIZE", (430, 443), 11, GOLD, "mono", 1)
    for i, (size, count) in enumerate(GALAXY_SIZES.items()):
        x = 430+i*320
        app.button("size_"+size, f"{size} · {count} systems", (x, 469, 306, 49), lambda s=size: app.choose_size(s))
        if app.size == size:
            pg.draw.line(surface, GOLD, (x, 518), (x+306, 518), 2)
    app.button("fog_of_war", ("AI fog of war: " if observer else "Fog of war: ")+("ON" if app.fog_of_war else "OFF"),
               (430, 534, 306, 43), app.toggle_fog_of_war)
    app.button("neutral_encounters", "Pirate encounters: "+("ON" if app.with_encounters else "OFF"),
               (750, 534, 306, 43), app.toggle_encounters)
    text(surface, "Pirates, searches & raids", (1071, 549), 13, MUTED)
    text(surface, "You see everything; AI explores." if observer and app.fog_of_war else
         "Explore to reveal planets and fleets." if app.fog_of_war else "All systems and fleets are visible.",
         (432, 583), 10, MUTED)
    text(surface, "COMPUTER EMPIRES" if observer else "NUMBER OF RIVALS", (430, 600), 11, GOLD, "mono", 1)
    for count in range(MAX_RIVALS+1):
        x = 430+count*160
        app.button(f"rival_count_{count}", "0 · Solo" if count == 0 else str(count),
                   (x, 622, 146, 43), lambda n=count: app.choose_rival_count(n), enabled=not observer or count >= 2)
        if app.rival_count == count:
            pg.draw.line(surface, GOLD, (x, 665), (x+146, 665), 2)
    paragraph(surface, "Choose 2–5 computer empires. Random races and starting locations. Battles resolve automatically." if observer else
              "Random rival races and starting locations. Every empire begins with its own fleet and economy.",
              (431, 682), 930, 13, MUTED, 18)
    text(surface, "VICTORY CONDITIONS", (430, 721), 11, GOLD, "mono", 1)
    text(surface, "All off = open-ended play", (1376, 721), 12, MUTED, right=True)
    captions = ("Last surviving empire", "Win the galactic election", "Each civilization has a unique goal")
    for i, condition in enumerate(CONDITIONS):
        x = 430+i*240
        enabled = condition in app.victory_conditions
        app.button("victory_"+condition, f"{CONDITION_NAMES[condition]}: {'ON' if enabled else 'OFF'}",
                   (x, 745, 226, 43), lambda c=condition: app.toggle_victory_condition(c))
        if enabled:
            pg.draw.line(surface, GOLD, (x, 788), (x+226, 788), 2)
        paragraph(surface, captions[i], (x+2, 797), 224, 11, MUTED, 15)
    starting = ("Start: two scouts and a mothership · Convoy range: 25 ly" if race.id == "wanderers" else
                "Start: 2 scouts, 1 frigate, 2 troop transports · Range: 10.5 ly" if race.id == "varkesh" else
                "Start: two scouts and one colony ship · Base fuel range: 7 ly")
    footer = ("No victory limit. Losing all your colonies still ends your campaign." if not app.victory_conditions and not observer else
              "Watch. Advance turns. Save and return whenever you like." if observer else starting)
    text(surface, footer, (65, 842), 13, MUTED)
    app.button("launch", "Begin observation" if observer else "Begin expedition", (966, 831, 410, 48), app.start_game, "primary")
