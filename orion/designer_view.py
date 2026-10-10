"""Ship blueprints: hull, equipment, live statistics and local construction."""

from collections import Counter
import math
import pygame as pg
from .designs import HULLS, MODULES, ShipDesign, loadout_error
from .fleet_art import ship_icon
from .research import TECHNOLOGIES
from .ui import CYAN, GOLD, INK, LINE, MUTED, RED, panel, paragraph, shorten, text


def draft(app):
    return ShipDesign(app.design_id or "design_1", app.design_name.strip(), app.design_kind, tuple(app.design_modules))


def draw_designer(app):
    game, surface = app.game, app.canvas
    app.chrome("SHIP DESIGNER")
    text(surface, "Ship designer", (64, 124), 36, INK, "title")
    text(surface, "Choose a hull, fit modules, and save a blueprint for your colonies.", (66, 173), 15, MUTED)
    design = draft(app)
    hull = HULLS[design.kind]
    error = loadout_error(design.kind, design.modules, game.technology.completed)
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
        text(surface, f"{HULLS[item.kind].name} · {game.project_price(item.id)} CR", (92, y+27), 10, MUTED)
    if not game.designs:
        paragraph(surface, "Your saved blueprints appear here. Select one to revise its future production orders.", (83, 328), 231, 14, MUTED, 25)
    app.button("design_prev", "←", (82, 677, 54, 30), lambda: app.design_page_change(-1), enabled=app.design_page > 0)
    text(surface, f"{app.design_page+1} / {last+1}", (180, 684), 11, MUTED)
    app.button("design_next", "→", (260, 677, 54, 30), lambda: app.design_page_change(1), enabled=app.design_page < last)
    text(surface, "BUILD AT COLONY", (82, 727), 10, GOLD, "mono")
    colony = app.design_colony()
    label = shorten(colony[1].name, 150, 14) if colony else "No owned colony"
    app.button("design_colony_prev", "←", (82, 751, 38, 33), lambda: app.cycle_design_colony(-1), enabled=colony is not None)
    text(surface, label, (128, 759), 14, INK)
    app.button("design_colony_next", "→", (276, 751, 38, 33), lambda: app.cycle_design_colony(1), enabled=colony is not None)

    panel(surface, (352, 214, 610, 589))
    for index, (kind, spec) in enumerate(HULLS.items()):
        app.button(f"design_hull_{kind}", spec.name, (368+index*193, 231, 181, 40),
                   lambda k=kind: app.choose_design_hull(k), "primary" if kind == design.kind else "normal")
    used = sum(m.space for m in design.specs)
    text(surface, f"CAPACITY {used}/{hull.capacity}", (369, 289), 12, CYAN, "mono")
    text(surface, f"Limits: weapons {hull.weapon} · defense {hull.defense} · support {hull.support}", (946, 290), 11, MUTED, right=True)
    text(surface, "Category limits share the total capacity. Unused space is allowed.", (369, 314), 11, MUTED)
    for index, (identifier, module) in enumerate(MODULES.items()):
        y = 340+index*52
        locked = module.technology and module.technology not in game.technology.completed
        text(surface, module.name, (369, y), 16, MUTED if locked else INK)
        text(surface, f"{module.space} {module.category} · {module.credit_cost} CR", (785, y+3), 10, GOLD, right=True)
        detail = f"Requires {TECHNOLOGIES[module.technology].name}" if locked else module.description
        text(surface, shorten(detail, 424, 11), (369, y+26), 11, MUTED if locked else CYAN)
        app.button("design_remove_"+identifier, "−", (802, y, 37, 36), lambda m=identifier: app.change_design_module(m, -1), enabled=identifier in design.modules)
        text(surface, str(design.modules.count(identifier)), (854, y+10), 14, INK)
        addition = loadout_error(design.kind, [*design.modules, identifier], game.technology.completed, require_weapon=False)
        app.button("design_add_"+identifier, "+", (895, y, 48, 36), lambda m=identifier: app.change_design_module(m, 1), enabled=addition is None)

    panel(surface, (984, 214, 392, 589))
    app.input_box("design_name", "BLUEPRINT NAME", app.design_name, (1002, 255, 356, 55), "Name your ship")
    ship_icon(surface, (1180, 391), 1.85, kind=design.kind)
    text(surface, hull.name.upper(), (1003, 329), 10, GOLD, "mono", 1)
    text(surface, "LIVE PREVIEW", (1003, 444), 10, MUTED, "mono", 1)
    discount = game.bonuses_for().get("ship_discount", 0)
    cost = max(1, math.ceil(design.credit_cost*(100-discount)/100))
    values = (("Hull / shields", f"{design.hull} / {design.shields}"),
              ("Volley / max range", f"{design.damage} / {design.weapon_range}"),
              ("Tactical movement", f"{design.movement} cells"),
              ("Torpedo interception", f"{design.interception}%"),
              ("Build cost / work", f"{cost} CR / {design.work_cost}"))
    for index, (label, value) in enumerate(values):
        y = 471+index*29
        text(surface, label, (1003, y), 13, MUTED)
        text(surface, value, (1357, y), 13, CYAN, right=True)
    caption = " · ".join(f"{count}× {MODULES[m].name}" for m, count in Counter(design.modules).items()) or "No modules fitted."
    paragraph(surface, caption, (1003, 629), 350, 12, INK, 20)
    reason = error or ("Name this design before saving." if not design.name else "Saved blueprint ready to build." if unchanged else "Save changes to use this loadout in new orders.")
    paragraph(surface, reason, (1003, 718), 350, 12, GOLD if not error else RED, 20)
    text(surface, "Existing ships and queued orders keep their equipment.", (66, 815), 12, MUTED)
    app.button("designer_back", "← Return", (64, 847, 177, 36), lambda: app.go(app.designer_return), "ghost")
    app.button("design_copy", "Save as new", (746, 838, 216, 45), lambda: app.save_ship_design(copy=True), enabled=saved is not None and not error and bool(design.name))
    app.button("design_save", "Update" if saved else "Save design", (984, 838, 184, 45), app.save_ship_design, "primary", enabled=not error and bool(design.name) and not unchanged)
    build_error = game.ship_build_error(colony[0].id, colony[1].id, saved.id) if colony and saved else "Save a blueprint first."
    app.button("design_build", "Queue ship", (1180, 838, 196, 45), app.build_ship_design, enabled=unchanged and build_error is None)
    if unchanged and build_error:
        text(surface, shorten(build_error, 380, 11), (1376, 813), 11, GOLD, right=True)
