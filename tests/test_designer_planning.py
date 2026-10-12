"""Future blueprints stay editable; only researched equipment reaches construction."""

import copy
from dataclasses import replace
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame as pg

from orion.app import App
from orion.auto_designs import auto_design
from orion.designer_info import module_sections, research_sections
from orion.designs import HULLS, MODULES, fitted_module, loadout_error, missing_research
from orion.model import ConstructionProject, GameState, RuleError, SaveError, Ship
from orion.research import TECHNOLOGIES
from orion.storage import Storage
from scenarios import empty_fleet_game


def campaign():
    game = empty_fleet_game(seed=2408, with_ai=False, with_guardians=False, fog_of_war=False)
    game.resources = game.credits = 10000
    return game


def discover(game, *identifiers):
    for identifier in identifiers:
        game.research += TECHNOLOGIES[identifier].cost
        game.choose_research(identifier)


class BlueprintPlanningTests(unittest.TestCase):
    def test_future_carrier_survives_save_and_unlocks_only_after_all_research(self):
        game = campaign()
        design = game.save_design("Future carrier", "carrier", ["laser", "laser", "drone_bay", "shield"])
        self.assertEqual(missing_research(design.kind, design.modules, []), ("drone_carriers", "radiation_shields"))
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            game, _ = storage.load(storage.save(game))
        self.assertEqual(game.designs[0], design)
        before = game.to_dict()
        for method in (game.queue_ship, game.queue_project, game.change_production):
            with self.assertRaisesRegex(RuleError, "Drone Carriers"):
                method(0, 2, design.id)
            self.assertEqual(game.to_dict(), before)
        discover(game, "destroyer_hulls", "cruiser_hulls", "drone_carriers")
        with self.assertRaisesRegex(RuleError, "Radiation Shields"):
            game.queue_ship(0, 2, design.id)
        discover(game, "radiation_shields")
        self.assertIsNone(game.ship_build_error(0, 2, design.id))
        game.queue_ship(0, 2, design.id)
        game.buy_construction(0, 2)
        self.assertEqual(game.ships[-1].design, design)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_revision_can_plan_unknown_equipment_without_changing_paid_orders(self):
        game = campaign()
        original = game.save_design("Scout hunter", "frigate", ["laser"])
        game.queue_ship(0, 2, original.id)
        planned = game.save_design("Future hunter", "carrier", ["drone_bay", "quantum"], original.id)
        resumed = GameState.from_dict(game.to_dict())
        self.assertEqual(resumed.designs[0], planned)
        self.assertEqual(resumed.planet_at(0, 2).construction_queue[0].design, original)
        resumed.buy_construction(0, 2)
        self.assertEqual(resumed.ships[-1].design, original)
        with self.assertRaises(RuleError):
            resumed.queue_ship(0, 2, planned.id)

    def test_planning_does_not_allow_forged_unresearched_ships_or_orders(self):
        game = campaign()
        planned = game.save_design("Later", "frigate", ["quantum"])
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        forged = copy.deepcopy(game)
        forged.ships = [Ship(1, "frigate", 0, design=planned)]
        forged.next_ship_id = 2
        forged_ship = forged.to_dict()
        with self.assertRaises(SaveError) as caught:
            GameState.from_dict(forged_ship)
        self.assertEqual(str(caught.exception.__cause__), "Undiscovered ship equipment")
        game.planet_at(0, 2).construction_queue = [ConstructionProject(planned.id, design=planned)]
        with self.assertRaises(SaveError) as caught:
            GameState.from_dict(game.to_dict())
        self.assertEqual(str(caught.exception.__cause__), "Undiscovered ship equipment")

    def test_planning_autofit_does_not_unlock_research_or_change_ai(self):
        for kind in HULLS:
            with self.subTest(kind=kind):
                completed = ()
                plan = auto_design(kind, completed, planning=True)
                self.assertIsNotNone(plan)
                self.assertIsNone(loadout_error(kind, plan.modules))
                self.assertEqual(completed, ())
                if kind != "frigate":
                    self.assertIsNone(auto_design(kind, completed))
                else:
                    self.assertIsNotNone(auto_design(kind, completed))
        self.assertIn("drone_bay", auto_design("carrier", (), planning=True).modules)

    def test_equipment_help_uses_scaled_stats_and_explains_effects_and_exclusions(self):
        game = campaign()
        small = " ".join(body for _, body in module_sections("frigate", "laser", game.technology))
        heavy = " ".join(body for _, body in module_sections("titan", "laser", game.technology))
        self.assertIn("5 total damage", small)
        self.assertIn("12 resources", small)
        self.assertIn("no accuracy penalty", small)
        self.assertIn("20 total damage", heavy)
        self.assertIn("70 vs small hulls", heavy)
        self.assertIn("Titan", heavy)
        with patch.dict(MODULES, {"laser": replace(MODULES["laser"], damage=9, resource_cost=23)}):
            fitted_module.cache_clear()
            changed = " ".join(body for _, body in module_sections("cruiser", "laser", game.technology))
            self.assertIn("18 total damage", changed)
            self.assertIn("46 resources", changed)
        fitted_module.cache_clear()
        discover(game, "destroyer_hulls", "cruiser_hulls", "drone_carriers")
        requirements = " ".join(body for _, body in research_sections("battleship", ("laser",), game.technology))
        self.assertIn("Excluded", requirements)
        for identifier, expected in (("ion", "4 times"), ("phased", "50%"), ("graviton", "next turn"),
                                     ("mirv", "Ignores 50%"), ("damage_control", "12 repair points"),
                                     ("interceptor_bay", "within 2 cells")):
            with self.subTest(module=identifier):
                details = " ".join(body for _, body in module_sections("frigate", identifier, game.technology))
                self.assertIn(expected, details)


class BlueprintPlanningUITests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.app = App(Path(self.folder.name), capture=True)
        self.app.game = campaign()
        self.app.open_designer()
        self.app.present()

    def tearDown(self):
        self.app.audio.close()
        pg.quit()
        self.folder.cleanup()

    def click(self, key):
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        self.assertTrue(button.enabled, key)
        self.mouse(button.rect.center, 1)

    def mouse(self, logical, button):
        v = self.app.viewport
        pos = (round(v.x+logical[0]*v.w/1440), round(v.y+logical[1]*v.h/900))
        for event in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(event, button=button, pos=pos))
        self.app.render()

    def test_locked_carrier_can_remove_add_autofit_save_and_build_after_research(self):
        self.click("design_hull_carrier")
        self.click("design_remove_laser")
        self.click("design_add_laser")
        self.click("design_add_laser")
        self.assertEqual(self.app.design_modules.count("laser"), 2)
        self.click("design_add_shield")
        self.click("design_auto_fit")
        self.assertIn("drone_bay", self.app.design_modules)
        self.app.design_name = "Future Hive"
        self.click("design_save")
        self.assertFalse(next(b for b in self.app.buttons if b.key == "design_build").enabled)
        self.click("design_requirements")
        self.assertEqual(self.app.dialog["modules"], tuple(self.app.design_modules))
        self.click("dialog_close")
        saved, _ = self.app.storage.load(self.app.storage.saves_dir/"autosave.json")
        self.assertEqual(saved, self.app.game)
        discover(self.app.game, "destroyer_hulls", "cruiser_hulls", "drone_carriers")
        self.click("design_build")
        self.assertEqual(self.app.game.planet_at(0, 2).construction_queue[0].design, self.app.game.designs[0])

    def test_right_click_basic_and_locked_modules_preserves_draft_and_name_input(self):
        self.app.viewport = pg.Rect(90, 80, 960, 600)
        self.app.design_name = "Untouched"
        self.app.field = "design_name"
        self.app.focus = "design_name"
        for identifier in ("laser", "shield"):
            self.app.render()
            before = (self.app.game.to_dict(), self.app.design_name, list(self.app.design_modules))
            rect = next(r for m, r in self.app.module_regions if m == identifier)
            self.mouse(rect.center, 3)
            self.assertEqual(self.app.dialog["module"], identifier)
            self.assertTrue(all(b.key.startswith("dialog_") for b in self.app.buttons))
            self.app.handle_event(pg.event.Event(pg.TEXTINPUT, text="x"))
            self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_BACKSPACE, mod=0))
            self.assertEqual((self.app.game.to_dict(), self.app.design_name, self.app.design_modules), before)
            self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_ESCAPE, mod=0))
            self.assertIsNone(self.app.dialog)
            self.assertEqual(self.app.focus, "design_name")
        self.app.render()
        rect = next(r for m, r in self.app.module_regions if m == "laser")
        self.mouse(rect.center, 3)
        self.mouse(rect.center, 3)
        self.assertIsNone(self.app.dialog)

    def test_all_equipment_details_paginate_within_screen_and_preserve_research(self):
        self.app.design_kind = "titan"
        before = self.app.game.to_dict()
        saw_pages = False
        for identifier in MODULES:
            self.app.show_designer_info(module=identifier)
            self.app.render()
            for _ in range(10):
                self.assertTrue(all(self.app.canvas.get_rect().contains(b.rect) for b in self.app.buttons))
                if not next(b for b in self.app.buttons if b.key == "dialog_info_next").enabled:
                    break
                saw_pages = True
                self.click("dialog_info_next")
            else:
                self.fail("Equipment popup did not reach its final page")
            self.click("dialog_close")
        self.assertTrue(saw_pages)
        self.assertEqual(self.app.game.to_dict(), before)


if __name__ == "__main__":
    unittest.main()
