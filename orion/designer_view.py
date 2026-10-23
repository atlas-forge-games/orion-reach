"""Ship blueprints: hull, equipment, live statistics and local construction."""

from collections import Counter
import math
import pygame as pg
from .designs import HULLS, MODULES, ShipDesign, fitted_module, loadout_error, missing_research
from .weapons import BEAMS
from .fleet_art import ship_icon
from .research import TECHNOLOGIES
from .ui import CYAN, GOLD, INK, LINE, MUTED, RED, panel, paragraph, shorten, text, wrapped_lines


def draft(app):
    return ShipDesign(app.design_id or "design_1", app.design_name.strip(), app.design_kind, tuple(app.design_modules))


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


def draw_designer(app):
    game, surface = app.game, app.canvas
    simulator = getattr(app, "combat_simulator", False)
    app.chrome("SHIP DESIGNER")
    text(surface, "Ship designer", (64, 124), 36, INK, "title")
    text(surface, "All equipment unlocked. Save a loadout, then add it to either test fleet." if simulator else
         "Fit one module per slot. Larger hulls carry larger weapons: more damage, slower tracking against small targets.", (66, 173), 15, MUTED)
    design = draft(app)
    hull = HULLS[design.kind]
    error = loadout_error(design.kind, design.modules)
    missing = () if simulator else missing_research(design.kind, design.modules, game.technology.completed,
                               legacy_hulls=game.technology.legacy_starships)
    saved = game.design_for(app.design_id)
    unchanged = saved == design

    panel(surface, (64, 214, 268, 589))
    text(surface, "SAVED DESIGNS", (82, 233), 11, GOLD, "mono", 1)
    app.button("design_new", "+ New blueprint", (82, 262, 232, 38), app.new_design)
    last = max(0, (len(game.designs)-1)//7)
    app.design_page = min(app.design_page, last)
    for index, item in enumerate(game.designs[app.design_page*7:app.design_page*7+7]):
        y = 314+index*51
        b = app.button(f"design_load_{item.id}", "", (82, y, 232, 46), lambda d=item: app.load_design(d), "hotspot")
        panel(surface, b.rect, (16, 32, 43), GOLD if item.id == app.design_id else LINE)
        text(surface, shorten(item.name, 213, 16), (91, y+4), 16, INK)
        planned = () if simulator else missing_research(item.kind, item.modules, game.technology.completed,
                                   legacy_hulls=game.technology.legacy_starships)
        label = f"{HULLS[item.kind].name} · {game.project_price(item.id)} RES"+(" · Planned" if planned else "")
        text(surface, shorten(label, 213, 10), (92, y+27), 10, GOLD if planned else MUTED)
    if not game.designs:
        paragraph(surface, "Your saved blueprints appear here. Select one to revise its future production orders.", (83, 328), 231, 14, MUTED, 25)
    app.button("design_prev", "←", (82, 677, 54, 30), lambda: app.design_page_change(-1), enabled=app.design_page > 0)
    text(surface, f"{app.design_page+1} / {last+1}", (180, 684), 11, MUTED)
    app.button("design_next", "→", (260, 677, 54, 30), lambda: app.design_page_change(1), enabled=app.design_page < last)
    colony = app.design_colony()
    if simulator:
        text(surface, "ADD SAVED DESIGN TO", (82, 727), 10, GOLD, "mono")
        app.button("design_add_player", "+ Yours", (82, 751, 111, 33), lambda: app.add_design_to("player"),
                   enabled=unchanged and app.scenario.player.count < 60)
        app.button("design_add_rival", "+ Enemy", (203, 751, 111, 33), lambda: app.add_design_to("rival"),
                   enabled=unchanged and app.scenario.rival.count < 60)
    else:
        text(surface, "BUILD AT COLONY", (82, 727), 10, GOLD, "mono")
        label = shorten(colony[1].name, 150, 14) if colony else "No owned colony"
        app.button("design_colony_prev", "←", (82, 751, 38, 33), lambda: app.cycle_design_colony(-1), enabled=colony is not None)
        text(surface, label, (128, 759), 14, INK)
        app.button("design_colony_next", "→", (276, 751, 38, 33), lambda: app.cycle_design_colony(1), enabled=colony is not None)

    panel(surface, (352, 214, 610, 589))
    for index, (kind, spec) in enumerate(HULLS.items()):
        app.button(f"design_hull_{kind}", spec.name, (368+(index%3)*196, 231+(index//3)*39, 184, 32),
                   lambda k=kind: app.choose_design_hull(k), "primary" if kind == design.kind else "normal")
    counts = Counter(m.category for m in design.specs)
    for index, (category, label, limit) in enumerate((("weapon", "OFFENSE", hull.offensive_slots),
                                                   ("defense", "DEFENSE", hull.defensive_slots),
                                                   ("support", "SUPPORT", hull.support_slots))):
        text(surface, f"{label} {counts[category]}/{limit}", (369+index*196, 313), 12,
             RED if counts[category] > limit else CYAN, "mono")
    tracking = f"−{hull.tracking_penalty} aim per smaller target size" if hull.tracking_penalty else "Fast tracking"
    text(surface, f"{hull.module_size.title()} modules · {hull.module_scale}% output / cost · {tracking}", (369, 337), 11, MUTED)
    categories = (("all", "All equipment"), ("weapon", "Weapons"), ("defense", "Defense"), ("support", "Support"))
    for index, (category, label) in enumerate(categories):
        app.button("design_filter_"+category, label, (369+index*146, 358, 137, 29),
                   lambda c=category: app.filter_design_modules(c),
                   "tab_active" if category == app.design_module_filter else "tab")
    equipment = [(identifier, module) for identifier, module in MODULES.items()
                 if app.design_module_filter == "all" or module.category == app.design_module_filter]
    module_last = max(0, (len(equipment)-1)//8)
    app.design_module_page = min(app.design_module_page, module_last)
    for index, (identifier, module) in enumerate(equipment[app.design_module_page*8:app.design_module_page*8+8]):
        module = fitted_module(design.kind, identifier)
        y = 400+index*44
        locked = not simulator and module.technology and module.technology not in game.technology.completed
        text(surface, shorten(module.name, 290, 15), (369, y), 15, MUTED if locked else INK)
        text(surface, f"1 slot · {module.resource_cost} RES", (785, y+3), 10, GOLD, right=True)
        detail = module_detail(identifier, module)
        text(surface, shorten(detail, 424, 11), (369, y+26), 11, MUTED if locked else CYAN)
        app.module_info_region(identifier, (369, y, 574, 43))
        app.button("design_remove_"+identifier, "−", (802, y, 37, 36), lambda m=identifier: app.change_design_module(m, -1), enabled=identifier in design.modules)
        text(surface, str(design.modules.count(identifier)), (854, y+10), 14, INK)
        addition = loadout_error(design.kind, [*design.modules, identifier], require_weapon=False)
        app.button("design_add_"+identifier, "+", (895, y, 48, 36), lambda m=identifier: app.change_design_module(m, 1), enabled=addition is None)
    app.button("design_modules_prev", "←", (369, 761, 47, 29), lambda: app.design_module_page_change(-1), enabled=app.design_module_page > 0)
    text(surface, f"{app.design_module_page+1} / {module_last+1}", (440, 770), 11, MUTED)
    app.button("design_modules_next", "→", (506, 761, 47, 29), lambda: app.design_module_page_change(1), enabled=app.design_module_page < module_last)
    text(surface, "Right-click equipment for details", (566, 770), 10, MUTED)
    app.button("design_auto_fit", "Auto fit", (825, 758, 118, 34), app.auto_fit_design)

    panel(surface, (984, 214, 392, 589))
    app.input_box("design_name", "BLUEPRINT NAME", app.design_name, (1002, 255, 356, 55), "Name your ship")
    ship_icon(surface, (1180, 391), 2.1, kind=design.kind, facing=1)
    text(surface, f"{hull.name.upper()} · {hull.module_size.upper()} MODULES", (1003, 329), 10, GOLD, "mono", 1)
    text(surface, f"LIVE PREVIEW · UPKEEP {design.maintenance} CR/TURN", (1003, 444), 10, MUTED, "mono", 1)
    discount = game.bonuses_for().get("ship_discount", 0)
    cost = max(1, math.ceil(design.resource_cost*(100-discount)/100))
    support_labels = [f"{label} {getattr(module, key)}%" for module in design.specs
                      for key, label in (("escort_interception", "Escort"), ("command_accuracy", "Aim"), ("jamming", "ECM"))
                      if getattr(module, key)]
    values = (("Hull / shields", f"{design.hull} / {design.shields}"),
              ("Volley / max range", f"{design.damage} / {design.weapon_range}"),
              ("Tactical movement", f"{design.movement} cells"),
              ("Own point defense", f"{design.interception}%"),
              ("Build cost / work", f"{cost} RES / {design.work_cost}"),
              ("Support for allies", " / ".join(support_labels)) if support_labels else
              ("Drones active / launches", f"{design.drone_bays*2} / {design.drone_bays*4}"))
    for index, (label, value) in enumerate(values):
        y = 471+index*29
        text(surface, label, (1003, y), 13, MUTED)
        text(surface, value, (1357, y), 13, CYAN, right=True)
    text(surface, f"Sustained: {design.sustained_damage:g} / turn before aim and defenses", (1003, 638), 11, MUTED)
    caption = " · ".join(f"{count}× {MODULES[m].name}" for m, count in Counter(design.modules).items()) or "No modules fitted."
    lines = wrapped_lines(caption, 350, 12)
    for index, line in enumerate(lines[:3]):
        text(surface, shorten(line+(' …' if index == 2 and len(lines) > 3 else ''), 350, 12), (1003, 654+index*18), 12, INK)
    if missing:
        names = ", ".join(TECHNOLOGIES[t].name for t in missing)
        reason = ("Planned · Save now; build after research." if not unchanged else "Planned · Research needed to build.")
        text(surface, error or reason, (1003, 715), 12, RED if error else GOLD)
        text(surface, shorten("Requires "+names, 350, 12), (1003, 737), 12, MUTED)
        app.button("design_requirements", "View research requirements", (1003, 758, 350, 28),
                   app.show_design_requirements, "ghost")
    else:
        reason = error or ("Name this design before saving." if not design.name else
                           "Saved design ready for either test fleet." if simulator and unchanged else
                           "Save changes, then add this design to a fleet." if simulator else
                           "Saved blueprint ready to build." if unchanged else "Save changes to use this loadout in new orders.")
        paragraph(surface, reason, (1003, 718), 350, 12, GOLD if not error else RED, 20)
    text(surface, "Updating a design changes both test fleets on their next launch. Save scenario to keep your blueprints." if simulator else
         "Legacy blueprint: saving refits it to slots. Existing ships and orders keep their equipment."
         if saved and saved.fit_version == 1 else "Existing ships and queued orders keep their equipment.", (66, 815), 12, MUTED)
    app.button("designer_back", "← Return", (64, 847, 177, 36), lambda: app.go(app.designer_return), "ghost")
    app.button("design_copy", "Save as new", (746, 838, 216, 45), lambda: app.save_ship_design(copy=True), enabled=saved is not None and not error and bool(design.name))
    app.button("design_save", "Update" if saved else "Save design", (984, 838, 184, 45), app.save_ship_design, "primary", enabled=not error and bool(design.name) and not unchanged)
    build_error = None if simulator else game.ship_build_error(colony[0].id, colony[1].id, saved.id) if colony and saved else "Save a blueprint first."
    app.button("design_build", "Fleet setup" if simulator else "Queue ship", (1180, 838, 196, 45),
               (lambda: app.go("sim_setup")) if simulator else app.build_ship_design,
               enabled=simulator or unchanged and build_error is None)
    if not simulator and unchanged and build_error:
        text(surface, shorten(build_error, 380, 11), (1376, 813), 11, GOLD, right=True)
