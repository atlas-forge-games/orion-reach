"""Fleet composition and scenario browser for the standalone simulator."""

import pygame as pg

from .combat_sandbox import MAX_BASES, MAX_SHIPS, PRESETS, UPGRADES, ScenarioError, unit_preview
from .fleet_art import ship_icon
from .production import SHIP_TYPES
from .races import RACES
from .ui import CYAN, GOLD, INK, LINE, MUTED, RED, RIVAL_COLOR, panel, paragraph, shorten, text


def ship_name(scenario, identifier):
    design = scenario.design(identifier)
    return design.name if design else SHIP_TYPES[identifier].name


def draw_fleet(app, side, x):
    surface, scenario = app.canvas, app.scenario
    fleet = scenario.fleet(side)
    color = CYAN if side == "player" else RIVAL_COLOR
    panel(surface, (x, 210, 390, 518), border=color)
    text(surface, "YOUR FLEET" if side == "player" else "ENEMY FLEET", (x+20, 229), 13, color, "mono", 1)
    app.button(f"sim_clear_{side}", "Clear", (x+304, 221, 66, 29), lambda: app.clear_fleet(side))
    app.button(f"sim_race_prev_{side}", "←", (x+20, 264, 36, 30), lambda: app.cycle_race(side, -1))
    text(surface, shorten(RACES[fleet.race].name, 267, 15), (x+67, 271), 15, INK)
    app.button(f"sim_race_next_{side}", "→", (x+334, 264, 36, 30), lambda: app.cycle_race(side, 1))
    app.button(f"sim_upgrades_{side}", UPGRADES[fleet.upgrades][0], (x+20, 305, 350, 32),
               lambda: app.cycle_upgrades(side))
    entries = list(fleet.ships.items())
    last = (max(1, len(entries))-1)//6
    app.fleet_pages[side] = min(last, app.fleet_pages[side])
    page = app.fleet_pages[side]
    for index, (identifier, count) in enumerate(entries[page*6:page*6+6]):
        y = 353+index*45
        text(surface, shorten(ship_name(scenario, identifier), 225, 14), (x+20, y+9), 14, INK)
        app.button(f"sim_remove_{side}_{identifier}", "−", (x+254, y, 32, 32),
                   lambda s=side, k=identifier: app.change_ship(s, k, -1))
        text(surface, str(count), (x+300, y+9), 14, color, "mono")
        app.button(f"sim_more_{side}_{identifier}", "+", (x+338, y, 32, 32),
                   lambda s=side, k=identifier: app.change_ship(s, k, 1), enabled=fleet.count < MAX_SHIPS)
    if not entries:
        paragraph(surface, "Choose ships from the catalogue, or add planetary defenses below.",
                  (x+24, 380), 332, 16, MUTED, 28)
    app.button(f"sim_fleet_prev_{side}", "←", (x+20, 636, 44, 30),
               lambda: app.page_fleet(side, -1), enabled=page > 0)
    text(surface, f"{fleet.count}/{MAX_SHIPS} ships  ·  {page+1}/{last+1}", (x+83, 644), 12, color, "mono")
    app.button(f"sim_fleet_next_{side}", "→", (x+326, 636, 44, 30),
               lambda: app.page_fleet(side, 1), enabled=page < last)
    pg.draw.line(surface, LINE, (x+20, 674), (x+370, 674))
    text(surface, "Planetary missile bases", (x+20, 691), 13, MUTED)
    app.button(f"sim_base_minus_{side}", "−", (x+254, 682, 32, 30), lambda: app.change_bases(side, -1), enabled=fleet.bases > 0)
    text(surface, str(fleet.bases), (x+300, 691), 14, color, "mono")
    app.button(f"sim_base_plus_{side}", "+", (x+338, 682, 32, 30), lambda: app.change_bases(side, 1), enabled=fleet.bases < MAX_BASES)


def draw_catalogue(app):
    surface, scenario = app.canvas, app.scenario
    panel(surface, (442, 210, 556, 518))
    text(surface, "SHIP CATALOGUE", (462, 229), 13, GOLD, "mono", 1)
    app.button("sim_stock", "Standard ships", (462, 264, 247, 32), lambda: app.switch_catalogue("stock"),
               "tab_active" if app.catalogue_tab == "stock" else "tab")
    app.button("sim_custom", "Custom designs", (721, 264, 257, 32), lambda: app.switch_catalogue("custom"),
               "tab_active" if app.catalogue_tab == "custom" else "tab")
    rows = app.catalogue()
    last = (max(1, len(rows))-1)//6
    app.catalogue_page = min(app.catalogue_page, last)
    for index, identifier in enumerate(rows[app.catalogue_page*6:app.catalogue_page*6+6]):
        unit = unit_preview(scenario, identifier)
        y = 311+index*51
        selected = app.catalogue_selected == identifier
        app.button(f"sim_select_{identifier}", "", (453, y-3, 335, 48),
                   lambda k=identifier: setattr(app, "catalogue_selected", k), "hotspot")
        if selected:
            pg.draw.line(surface, GOLD, (453, y), (453, y+36), 3)
        ship_icon(surface, (477, y+18), .48, color=GOLD if selected else CYAN, kind=unit.kind, facing=1)
        text(surface, shorten(ship_name(scenario, identifier), 270, 15), (502, y), 15, INK)
        text(surface, f"Hull {unit.max_hull} · Shield {unit.max_shields} · Volley {unit.damage}", (502, y+25), 10, MUTED)
        app.button(f"sim_add_player_{identifier}", "+ Yours", (797, y+2, 85, 35),
                   lambda k=identifier: app.change_ship("player", k, 1), enabled=scenario.player.count < MAX_SHIPS)
        app.button(f"sim_add_rival_{identifier}", "+ Enemy", (891, y+2, 87, 35),
                   lambda k=identifier: app.change_ship("rival", k, 1), enabled=scenario.rival.count < MAX_SHIPS)
    if not rows:
        paragraph(surface, "Create a blueprint in the ship designer. All hulls and equipment are available, including late-game weapons and drone bays.",
                  (478, 362), 470, 17, MUTED, 29)
    app.button("sim_catalogue_prev", "←", (462, 636, 44, 30), lambda: app.page_catalogue(-1), enabled=app.catalogue_page > 0)
    text(surface, f"{app.catalogue_page+1}/{last+1}", (527, 645), 12, MUTED, "mono")
    app.button("sim_catalogue_next", "→", (586, 636, 44, 30), lambda: app.page_catalogue(1), enabled=app.catalogue_page < last)
    text(surface, "Stock stats shown before research", (648, 646), 10, MUTED)
    app.button("sim_design_new", "New custom design", (462, 682, 247, 32), lambda: app.open_designer())
    from .designs import HULLS
    can_edit = app.catalogue_selected in HULLS or scenario.design(app.catalogue_selected) is not None
    app.button("sim_design_edit", "Edit / customize selected", (721, 682, 257, 32),
               lambda: app.open_designer(app.catalogue_selected), enabled=can_edit)


def draw_setup(app):
    surface, scenario = app.canvas, app.scenario
    app.chrome()
    text(surface, "Build a battle", (32, 127), 34, INK, "title")
    text(surface, "Choose both fleets, experiment with loadouts, and replay the same fight.", (34, 176), 15, MUTED)
    app.input_box("scenario_name", "SCENARIO NAME", app.scenario_name, (1018, 143, 390, 49), "Name this battle")
    draw_fleet(app, "player", 32)
    draw_catalogue(app)
    draw_fleet(app, "rival", 1018)
    app.input_box("seed", "BATTLE SEED", app.seed, (32, 769, 200, 49), "2408")
    for x, label in ((250, "FIRST MOVE"), (478, "HIT CHANCES"), (704, "QUICK SCENARIO")):
        text(surface, label, (x, 738), 12, MUTED, "mono", 1)
    app.button("sim_first", "Your fleet first" if scenario.first == "player" else "Enemy fleet first", (250, 769, 212, 49),
               lambda: setattr(scenario, "first", "rival" if scenario.first == "player" else "player"))
    app.button("sim_accuracy", "Normal accuracy" if scenario.accuracy else "Every shot hits", (478, 769, 210, 49),
               lambda: setattr(scenario, "accuracy", not scenario.accuracy))
    app.button("sim_preset", PRESETS[app.preset_index]+" →", (704, 769, 274, 49), app.cycle_preset)
    app.button("sim_apply_preset", "Apply", (990, 769, 112, 49), app.apply_preset)
    app.button("sim_mirror", "Copy yours → enemy", (1114, 769, 294, 49), app.mirror_fleet)
    error = None
    try:
        scenario.validate(battle=True)
    except ScenarioError as exc:
        error = str(exc)
    app.button("sim_quit", "Quit", (32, 844, 108, 42), app.quit_request)
    text(surface, shorten(error or "Save named setups · R rematches · F1 opens help", 800, 13), (164, 858), 13, RED if error else MUTED)
    app.button("sim_launch_manual", "Fight manually", (992, 840, 196, 46), lambda: app.launch(False), "primary", enabled=error is None)
    app.button("sim_launch_auto", "Watch AI vs AI", (1200, 840, 208, 46), lambda: app.launch(True), "primary", enabled=error is None)


def draw_scenarios(app):
    surface = app.canvas
    app.chrome()
    text(surface, "Saved combat scenarios", (64, 130), 34, INK, "title")
    text(surface, "Load a fleet setup and its custom designs. Battles use the currently loaded balance profile.", (66, 181), 15, MUTED)
    panel(surface, (64, 224, 1312, 528))
    files = app.scenario_files
    for index, path in enumerate(files[app.scenario_page*8:app.scenario_page*8+8]):
        y = 243+index*60
        label = app.scenario_label(path)
        app.button(f"sim_load_row_{index}", label, (84, y, 1268, 47), lambda p=path: app.load_selected_scenario(p))
    if not files:
        paragraph(surface, "No saved scenarios yet. Return to fleet setup, choose a name, then select Save scenario or press F5.",
                  (95, 270), 1160, 18, MUTED, 32)
    text(surface, shorten(str(app.scenarios_dir), 1280, 12), (66, 772), 12, MUTED)
    last = (max(1, len(files))-1)//8
    app.button("sim_load_prev", "←", (64, 802, 60, 36), lambda: app.page_scenarios(-1), enabled=app.scenario_page > 0)
    text(surface, f"{app.scenario_page+1}/{last+1}", (153, 812), 12, MUTED)
    app.button("sim_load_next", "→", (217, 802, 60, 36), lambda: app.page_scenarios(1), enabled=app.scenario_page < last)
    app.button("sim_load_back", "← Fleet setup", (64, 850, 235, 38), lambda: app.go("sim_setup"), "ghost")
