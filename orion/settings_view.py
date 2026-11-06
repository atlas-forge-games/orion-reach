"""Categorized preferences, using the existing settings and immediate saving."""

import pygame as pg

from .empires import PLAYER_PALETTES
from .galaxy_style import map_style
from .display import UI_SCALES
from .ui import CYAN, GOLD, INK, LINE, MUTED, arrow, font, panel, paragraph, text


SECTIONS = {
    "graphics": ("Graphics", "Display mode and animated backgrounds.", "fullscreen"),
    "sound": ("Sound", "Music, volume and sound effects.", "music"),
    "gameplay": ("Gameplay", "Autosaving and campaign preferences.", "autosave"),
    "interface": ("Interface", "Text size, galaxy map style and colors.", "ui_scale_100"),
}


def toggle(app, key, label, description, y):
    panel(app.canvas, (352, y, 1024, 104))
    text(app.canvas, label, (380, y+18), 21, INK)
    paragraph(app.canvas, description, (380, y+54), 760, 15, MUTED, 22)
    app.button(key, "ON" if app.settings[key] else "OFF", (1192, y+28, 156, 48),
               lambda: app.toggle_setting(key))
    if app.settings[key]:
        pg.draw.circle(app.canvas, CYAN, (1326, y+52), 4)


def draw_overview(app):
    settings = app.settings
    summaries = {
        "graphics": "Fullscreen" if settings["fullscreen"] else "Windowed display",
        "sound": (f"Music on · {settings['music_volume']}%" if settings["music"] and
                  settings["music_volume"] else "Music muted"),
        "gameplay": "Autosave on" if settings["autosave"] else "Autosave off · Save manually",
        "interface": map_style(app).title()+" map · "+("Saturated blue" if settings["galaxy_palette"] == "blue" else "Saturated turquoise"),
    }
    for index, (key, (label, description, _)) in enumerate(SECTIONS.items()):
        x, y = 64+(index % 2)*668, 320+(index // 2)*190
        panel(app.canvas, (x, y, 644, 166))
        text(app.canvas, label, (x+28, y+24), 28, INK, "title")
        text(app.canvas, description, (x+28, y+72), 17, MUTED)
        text(app.canvas, summaries[key], (x+28, y+122), 14, CYAN)
        arrow(app.canvas, (x+604, y+46), GOLD)
        app.button("settings_category_"+key, label, (x+1, y+1, 642, 164),
                   lambda section=key: app.select_settings_section(section), "hotspot")


def draw_sidebar(app):
    panel(app.canvas, (64, 320, 256, 360))
    text(app.canvas, "CATEGORIES", (86, 340), 11, GOLD, "mono", 1)
    for index, (key, (label, _, _)) in enumerate(SECTIONS.items()):
        app.button("settings_category_"+key, label, (80, 374+index*72, 224, 56),
                   lambda section=key: app.select_settings_section(section),
                   "tab_active" if app.settings_section == key else "tab")


def draw_graphics(app):
    toggle(app, "fullscreen", "Fullscreen", "Use the entire display. F11 also toggles this setting.", 320)
    toggle(app, "animated_background", "Animated effects", "Moving backgrounds and gently pulsing map stars.", 436)
    toggle(app, "galaxy_background", "Galaxy background", "Nebula artwork behind the galaxy map.", 552)


def draw_sound(app):
    toggle(app, "music", "Background music", app.audio.music_description, 320)
    toggle(app, "sound", "Sound effects", "Interface tones, weapons, shield hits and explosions.", 436)
    volume = app.settings["music_volume"]
    muted = not app.settings["music"] or volume == 0
    panel(app.canvas, (352, 552, 1024, 132))
    text(app.canvas, "Music volume"+(" · Muted" if muted else ""), (380, 572), 21, INK)
    text(app.canvas, "Use − / + to adjust in 10% steps.", (380, 614), 15, MUTED)
    app.button("music_quieter", "−", (1040, 592, 52, 46),
               lambda: app.change_music_volume(-10), enabled=volume > 0)
    label = f"{volume}%"
    text(app.canvas, label, (1194-font(23).size(label)[0]//2, 601), 23, CYAN)
    app.button("music_louder", "+", (1296, 592, 52, 46),
               lambda: app.change_music_volume(10), enabled=volume < 100)
    pg.draw.rect(app.canvas, LINE, (380, 657, 968, 4))
    if volume:
        pg.draw.rect(app.canvas, MUTED if muted else CYAN, (380, 657, round(968*volume/100), 4))


def draw_gameplay(app):
    toggle(app, "autosave", "Autosave", "Automatically save campaign progress. When off, save manually.", 320)
    panel(app.canvas, (352, 452, 1024, 230))
    text(app.canvas, "SAVING YOUR CAMPAIGN", (380, 476), 11, GOLD, "mono", 1)
    paragraph(app.canvas, "F5 and Save game always create a manual snapshot, even when autosave is off.",
              (380, 505), 940, 17, INK, 28)
    text(app.canvas, "NEW GAME OPTIONS", (380, 570), 11, GOLD, "mono", 1)
    paragraph(app.canvas, "Choose galaxy size, opponents, fog of war, encounters and victory conditions "
              "when starting a new game.", (380, 599), 940, 17, MUTED, 28)


def draw_interface(app):
    panel(app.canvas, (352, 320, 1024, 156))
    text(app.canvas, "Interface size", (380, 335), 21, INK)
    for index, scale in enumerate(UI_SCALES):
        x = 380+index*150
        app.button("ui_scale_"+str(scale), f"{scale}%", (x, 373, 138, 42),
                   lambda value=scale: app.set_ui_scale(value))
        if app.settings.get("ui_scale", 100) == scale:
            pg.draw.line(app.canvas, GOLD, (x, 414), (x+138, 414), 3)
    text(app.canvas, "Ctrl + / Ctrl − changes size · Ctrl 0 resets to 100%.", (380, 426), 16, MUTED)
    text(app.canvas, "Larger screens: drag scrollbars or use Shift + mouse wheel to move around.", (380, 451), 16, MUTED)

    panel(app.canvas, (352, 488, 1024, 126))
    text(app.canvas, "Galaxy map style", (380, 500), 21, INK)
    for index, (style, label) in enumerate((("clean", "Star Atlas"), ("classic", "Classic"))):
        x = 380+index*496
        app.button("galaxy_style_"+style, label, (x, 538, 472, 40),
                   lambda value=style: app.set_galaxy_style(value),
                   "tab_active" if map_style(app) == style else "tab")
    text(app.canvas, "Star Atlas: bright names, ownership rings and compact ships. Classic: colored names and counts.",
         (380, 588), 16, MUTED)

    panel(app.canvas, (352, 626, 1024, 126))
    text(app.canvas, "Galaxy colors", (380, 638), 21, INK)
    for index, (palette, label) in enumerate((("blue", "Saturated blue"), ("turquoise", "Saturated turquoise"))):
        x = 380+index*496
        app.button("galaxy_palette_"+palette, label, (x, 676, 472, 40),
                   lambda value=palette: app.set_galaxy_palette(value),
                   "tab_active" if app.settings["galaxy_palette"] == palette else "tab")
        pg.draw.line(app.canvas, PLAYER_PALETTES[palette], (x+12, 720), (x+460, 720), 3)
    text(app.canvas, "Your empire's ownership markers and fleet accents.", (380, 729), 16, MUTED)
    text(app.canvas, "Tab / ↑ ↓ + Enter · Esc goes back · F11 toggles fullscreen", (380, 772), 16, MUTED)
    text(app.canvas, "Hover over an abbreviated label to read its full text.", (380, 796), 14, MUTED)


def draw_settings(app):
    section = app.settings_section
    app.chrome("PREFERENCES", app.back_from_settings)
    text(app.canvas, "SETTINGS"+(" / "+SECTIONS[section][0].upper() if section else ""),
         (64, 176), 11, GOLD, "mono", 2)
    text(app.canvas, SECTIONS[section][0] if section else "Settings", (60, 204), 42, INK, "title")
    text(app.canvas, SECTIONS[section][1] if section else "Choose a category to customize your game.",
         (64, 266), 17, MUTED)
    if section:
        draw_sidebar(app)
        {"graphics": draw_graphics, "sound": draw_sound, "gameplay": draw_gameplay,
         "interface": draw_interface}[section](app)
    else:
        draw_overview(app)
    text(app.canvas, "Changes apply immediately and are saved automatically.", (64, 817), 15, MUTED)
    text(app.canvas, "Esc: "+("all settings" if section else "back"), (64, 847), 13, MUTED)
    app.button("settings_done", "Done", (1125, 817, 251, 52),
               lambda: app.go(app.settings_return), "primary")
