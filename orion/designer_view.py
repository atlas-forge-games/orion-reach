"""Visual hull-first fitting with shared internal bays and live previews."""

import math
import pygame as pg
from . import designer_controls as controls
from .designer_controls import draft
from .designer_art import centered, draw_ship, equipment, hull as draw_hull, mount_frame
from .designs import HULLS, MODULES, fitted_module, missing_research
from .ship_fitting import mounts_for
from .weapons import BEAMS
from .research import TECHNOLOGIES
from .console_theme import console_panel
from .ui import CYAN, GOLD, INK, LINE, MUTED, RED, font, paragraph, shorten, text


def module_detail(identifier, module):
    if module.escort_interception:
        return f"Destroyer · allies within {module.support_range} cells: +{module.escort_interception}% interception"
    if module.command_accuracy:
        return f"Allies within {module.support_range} cells: +{module.command_accuracy} aim · strongest only"
    if module.jamming:
        return f"Allies within {module.support_range} cells: incoming aim −{module.jamming} · strongest only"
    if module.damage:
        beam = BEAMS[module.weapon]
        parts = [f"{module.damage} volley", f"range {module.range}"]
        if beam.shots > 1: parts.append(f"{beam.shots} shots")
        if beam.projectile: parts.append("interceptable")
        if beam.shield_multiplier > 1: parts.append(f"×{beam.shield_multiplier} vs shields")
        if beam.shield_bypass: parts.append(f"{beam.shield_bypass}% shield bypass")
        if beam.slows: parts.append("slows target")
        if beam.reload: parts.append(f"reload {beam.reload} turn")
        if module.weapon == "siege": parts.append("×3 vs bases")
        return " · ".join(parts)
    if module.hull_bonus:
        return f"+{module.hull_bonus} hull · {module.movement_bonus:+} movement (minimum 1)"
    if module.shields:
        return (f"+{module.shields} shields"+(f" · regenerate {module.shield_regeneration}/turn" if module.shield_regeneration else "")
                +(f" · {module.shield_hardening}% hardening" if module.shield_hardening else ""))
    if module.repair_rate:
        return f"Repair {module.repair_rate} hull/turn · {module.repair_capacity} reserve/battle"
    if module.interception:
        return f"{module.interception}% interception · cap {module.interception_cap}%"
    if module.range_bonus: return f"+{module.range_bonus} range · one scanner per ship"
    if module.movement_bonus: return f"{module.movement_bonus:+} tactical movement"
    return module.description



def module_name(app, identifier):
    if identifier is None:
        return "Standard engine" if app.design_mount == "engine" else "Standard plating"
    return MODULES[identifier].name


def option_description(app, identifier):
    if identifier is None:
        return (f"{HULLS[app.design_kind].movement} base movement · included in hull" if app.design_mount == "engine"
                else "Base hull protection · no movement penalty")
    return module_detail(identifier, fitted_module(app.design_kind, identifier))


def draw_hulls_and_library(app, design):
    surface, game = app.canvas, app.game
    console_panel(surface, (24, 112, 244, 644))
    text(surface, "HULL", (42, 130), 14, GOLD, "mono", 1)
    for index, (kind, spec) in enumerate(HULLS.items()):
        r = pg.Rect(38, 159+index*43, 216, 38)
        button = app.button("design_hull_"+kind, spec.name, r,
                            lambda k=kind: app.choose_design_hull(k), "hotspot")
        selected = kind == design.kind
        mount_frame(surface, r, GOLD if selected else CYAN if app.is_active(button) else (55, 77, 89))
        if selected:
            pg.draw.rect(surface, (48, 42, 29), r.inflate(-5, -5))
        draw_hull(surface, kind, (49, r.y+3, 37, 32))
        text(surface, spec.name, (97, r.y+8), 17, INK)
    text(surface, "BLUEPRINTS", (42, 438), 13, GOLD, "mono", 1)
    app.button("design_new", "+ New blueprint", (40, 467, 212, 31), app.new_design)
    count = controls.DESIGNS_PER_PAGE
    last = max(0, (len(game.designs)-1)//count)
    app.design_page = min(app.design_page, last)
    for index, item in enumerate(game.designs[app.design_page*count:app.design_page*count+count]):
        r = pg.Rect(40, 512+index*47, 212, 41)
        button = app.button("design_load_"+item.id, item.name, r, lambda d=item: app.load_design(d), "hotspot")
        mount_frame(surface, r, GOLD if item.id == app.design_id else CYAN if app.is_active(button) else LINE)
        text(surface, shorten(item.name, 192, 14), (r.x+9, r.y+4), 14, INK)
        planned = () if getattr(app, "combat_simulator", False) else missing_research(
            item.kind, item.modules, game.technology.completed, legacy_hulls=game.technology.legacy_starships)
        caption = HULLS[item.kind].name + (" · Planned" if planned else "")
        text(surface, caption, (r.x+9, r.y+23), 10, GOLD if planned else MUTED)
    if not game.designs:
        paragraph(surface, "Start with a hull, fit its modules, then save your blueprint.", (44, 522), 200, 14, MUTED, 23)
    app.button("design_prev", "←", (40, 658, 42, 29), lambda: app.design_page_change(-1), enabled=app.design_page > 0)
    centered(surface, f"{app.design_page+1} / {last+1}", (146, 666), 12, MUTED)
    app.button("design_next", "→", (210, 658, 42, 29), lambda: app.design_page_change(1), enabled=app.design_page < last)
    if getattr(app, "combat_simulator", False):
        text(surface, "ADD SAVED DESIGN", (43, 703), 10, GOLD, "mono")
        unchanged = game.design_for(app.design_id) == design
        app.button("design_add_player", "+ Yours", (40, 722, 101, 28), lambda: app.add_design_to("player"),
                   enabled=unchanged and app.scenario.player.count < 60)
        app.button("design_add_rival", "+ Enemy", (151, 722, 101, 28), lambda: app.add_design_to("rival"),
                   enabled=unchanged and app.scenario.rival.count < 60)
    else:
        colony = app.design_colony()
        text(surface, "BUILD AT", (43, 700), 10, GOLD, "mono")
        app.button("design_colony_prev", "←", (40, 721, 31, 27), lambda: app.cycle_design_colony(-1), enabled=colony is not None)
        centered(surface, shorten(colony[1].name if colony else "No colony", 125, 13), (146, 728), 13, INK)
        app.button("design_colony_next", "→", (221, 721, 31, 27), lambda: app.cycle_design_colony(1), enabled=colony is not None)


def draw_options(app, design):
    surface = app.canvas
    console_panel(surface, (982, 112, 434, 644))
    if app.design_mount == "unplaced":
        text(surface, "UNPLACED EQUIPMENT", (1003, 134), 19, GOLD, "title")
        paragraph(surface, "This hull cannot carry all the previous equipment. Fit it into a compatible mount, change hull, or remove it here.",
                  (1004, 171), 386, 13, MUTED, 21)
        first = app.design_module_page*controls.OPTIONS_PER_PAGE
        for index, identifier in enumerate(app.design_unplaced[first:first+controls.OPTIONS_PER_PAGE]):
            y = 268+index*90
            equipment(surface, identifier, (1005, y, 61, 65))
            text(surface, shorten(MODULES[identifier].name, 226, 16), (1078, y+8), 16, INK)
            app.module_info_region(identifier, (1003, y, 292, 68))
            app.button(f"design_unplaced_remove_{first+index}", "Remove", (1295, y+15, 99, 34),
                       lambda i=first+index: controls.discard_unplaced(app, i))
        draw_option_pages(app, len(app.design_unplaced))
        app.button("design_unplaced_clear", "Remove all unplaced", (1003, 699, 392, 40),
                   lambda: controls.discard_unplaced(app))
        return design
    slot = next(s for s in mounts_for(design.kind) if s.id == app.design_mount)
    text(surface, slot.name.upper(), (1003, 133), 23, GOLD, "title")
    caption = {"weapon": "Weapons and point defense share these mounts.",
               "core": "Choose one module for this shared bay.",
               "engine": "Replace the drive to change tactical movement.",
               "armor": "Choose protection for the whole hull.",
               "hangar": "Choose the drones carried in this hangar."}[slot.category]
    text(surface, caption, (1005, 171), 13, MUTED)
    current = app.design_mounts.get(slot.id)
    installed = module_name(app, current) if current or slot.category in ("armor", "engine") else "Empty"
    text(surface, shorten("Installed: "+installed, 388, 13), (1005, 194), 13, CYAN)
    choices = controls.choices(app)
    start = app.design_module_page*controls.OPTIONS_PER_PAGE
    hover = None
    for index, identifier in enumerate(choices[start:start+controls.OPTIONS_PER_PAGE]):
        r = pg.Rect(1003, 226+index*119, 392, 108)
        key = "design_option_"+(identifier or "standard")
        button = app.button(key, module_name(app, identifier), r,
                            lambda m=identifier: controls.choose_module(app, m), "hotspot")
        selected = identifier == app.design_candidate
        active = app.is_active(button)
        mount_frame(surface, r, GOLD if selected else CYAN if active else (53, 79, 94))
        if selected:
            pg.draw.rect(surface, (39, 36, 28), r.inflate(-6, -6))
        equipment(surface, identifier or ("engine" if slot.category == "engine" else "armor"), (1014, r.y+17, 68, 76))
        text(surface, shorten(module_name(app, identifier), 286, 18), (1093, r.y+12), 18, INK)
        detail = option_description(app, identifier)
        paragraph(surface, detail, (1093, r.y+42), 279, 12, CYAN if selected else MUTED, 18)
        if identifier:
            fitted = fitted_module(design.kind, identifier)
            locked = (not getattr(app, "combat_simulator", False) and fitted.technology
                      and fitted.technology not in app.game.technology.completed)
            caption = f"{fitted.resource_cost} RES" + (" · Research needed" if locked else "")
            text(surface, caption, (1093, r.bottom-21), 11, GOLD if locked else MUTED)
            app.module_info_region(identifier, r)
        if active and not app.keyboard_mode and not app.dialog:
            hover = (identifier,)
    draw_option_pages(app, len(choices))
    chosen, error = controls.candidate(app)
    changed = app.design_mounts.get(slot.id) != app.design_candidate
    selected_module = MODULES.get(app.design_candidate)
    locked = (not getattr(app, "combat_simulator", False) and selected_module and selected_module.technology
              and selected_module.technology not in app.game.technology.completed)
    if error:
        paragraph(surface, error, (1005, 635), 384, 12, RED, 18)
    elif locked:
        tech = TECHNOLOGIES[selected_module.technology].name
        text(surface, shorten("Requires "+tech, 384, 13), (1005, 638), 13, GOLD)
    else:
        text(surface, "Hover to compare · Right-click for details", (1005, 638), 12, MUTED)
    requirements = missing_research(design.kind, design.modules, app.game.technology.completed,
                                   legacy_hulls=app.game.technology.legacy_starships)
    if requirements and not getattr(app, "combat_simulator", False):
        app.button("design_requirements", "View blueprint research requirements", (1003, 662, 392, 25),
                   app.show_design_requirements, "ghost")
    app.button("design_install", "Plan module" if locked else "Replace module" if current else "Install module",
               (1003, 700, 258, 39), lambda: controls.install(app), "primary", enabled=changed and error is None)
    app.button("design_remove", "Reset" if slot.category in ("armor", "engine") else "Remove",
               (1272, 700, 123, 39), lambda: controls.remove(app), enabled=current is not None)
    if hover is not None:
        preview, hover_error = controls.candidate(app, module=hover[0])
        return design if hover_error else preview
    return design if error else chosen


def draw_option_pages(app, count):
    last = max(0, (count-1)//controls.OPTIONS_PER_PAGE)
    app.design_module_page = min(last, app.design_module_page)
    app.button("design_modules_prev", "←", (1004, 595, 45, 29),
               lambda: app.design_module_page_change(-1), enabled=app.design_module_page > 0)
    centered(app.canvas, f"{app.design_module_page+1} / {last+1}", (1198, 602), 12, MUTED)
    app.button("design_modules_next", "→", (1349, 595, 45, 29),
               lambda: app.design_module_page_change(1), enabled=app.design_module_page < last)


def draw_statistics(app, current, preview):
    surface = app.canvas
    console_panel(surface, (24, 768, 1392, 47))
    discount = app.game.bonuses_for().get("ship_discount", 0)
    cost = lambda d: max(1, math.ceil(d.resource_cost*(100-discount)/100))
    entries = (("HULL", current.hull, preview.hull, "", True),
               ("SHIELDS", current.shields, preview.shields, "", True),
               ("VOLLEY", current.damage, preview.damage, "", True),
               ("MOVEMENT", current.movement, preview.movement, " cells", True),
               ("BUILD COST", cost(current), cost(preview), " RES", False),
               ("UPKEEP", current.maintenance, preview.maintenance, " CR / turn", False))
    for index, (label, before, after, suffix, higher) in enumerate(entries):
        x = 44+index*232
        text(surface, label, (x, 775), 10, MUTED, "mono", 1)
        value = f"{before:,}"+(f" → {after:,}" if before != after else "")+suffix
        color = INK if before == after else CYAN if (after > before) == higher else RED
        text(surface, value, (x, 790), 15, color)


def draw_designer(app):
    game, surface = app.game, app.canvas
    design = draft(app)
    spec = HULLS[design.kind]
    simulator = getattr(app, "combat_simulator", False)
    console_panel(surface, (24, 20, 1392, 78))
    text(surface, "AGE OF THE STARS", (45, 38), 22, GOLD, "title")
    text(surface, "COMBAT SIMULATOR" if simulator else "SHIPYARD", (47, 72), 11, MUTED, "mono", 1)
    centered(surface, "SHIP DESIGNER", (626, 34), 32, INK, "title")
    centered(surface, f"{spec.name} · {spec.external_mounts} mounts · {spec.internal_bays} internal "
             +("bay" if spec.internal_bays == 1 else "bays"), (626, 77), 12, CYAN)
    app.input_box("design_name", "BLUEPRINT NAME", app.design_name, (998, 49, 398, 44), "Name your ship")
    draw_hulls_and_library(app, design)
    console_panel(surface, (282, 112, 682, 644))
    text(surface, "FIT EQUIPMENT DIRECTLY ON THE HULL", (302, 132), 11, MUTED, "mono", 1)
    preview = draw_options(app, design)
    draw_ship(app, preview)
    if app.design_unplaced:
        text(surface, "Some equipment needs another position or a larger hull.", (302, 716), 12, GOLD)
        app.button("design_review_unplaced", f"Review unplaced ({len(app.design_unplaced)})", (302, 734, 278, 19),
                   lambda: controls.select(app, "unplaced"), "ghost")
    else:
        text(surface, "Click a mount to fit or replace equipment.", (302, 730), 13, MUTED)
    app.button("design_auto_fit", "Auto fit", (816, 720, 132, 29), app.auto_fit_design)
    draw_statistics(app, design, preview)
    saved = game.design_for(app.design_id)
    unchanged = saved == design
    error = controls.error(app)
    app.button("designer_back", "← Return", (24, 831, 124, 43), lambda: app.go(app.designer_return), "ghost")
    app.button("design_copy", "Save as new", (160, 831, 168, 43), lambda: app.save_ship_design(copy=True),
               enabled=saved is not None and not error and bool(design.name))
    app.button("design_save", "Update design" if saved else "Save design", (340, 831, 198, 43), app.save_ship_design,
               "primary", enabled=not error and bool(design.name) and not unchanged)
    colony = app.design_colony()
    build_error = None if simulator else game.ship_build_error(colony[0].id, colony[1].id, saved.id) if colony and saved else "Save a blueprint first."
    app.button("design_build", "Fleet setup" if simulator else "Queue ship", (550, 831, 252, 43),
               (lambda: app.go("sim_setup")) if simulator else app.build_ship_design,
               enabled=simulator or unchanged and build_error is None)
    status = error or ("Name the blueprint before saving." if not design.name else
                      build_error if unchanged and build_error else
                      "Existing ships and queued orders retain their equipment.")
    if saved and saved.fit_version < 3 and not unchanged:
        status = error or "Refit preview · Existing ships and queued orders retain their equipment."
    text(surface, shorten(status, 1360, 11), (30, 882), 11, GOLD if error else MUTED)
