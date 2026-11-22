"""Physical fitting, immutable saves, and actual mouse clicks on ship mounts."""
from dataclasses import asdict
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame as pg
from orion import balance, designer_controls as controls
from orion.app import App
from orion.auto_designs import auto_design
from orion.combat_sandbox import Scenario, build_game, load_scenario, save_scenario
from orion.designs import HULLS, ShipDesign, loadout_error, standard_design, is_standard_design
from orion.model import GameState, RuleError, new_game
from orion.research import TECHNOLOGIES
from orion.ship_fitting import build_design, mounts_for, placement_error
from orion.storage import Storage, SAVE_VERSION


class VisualDesignerTests(unittest.TestCase):
    def setUp(self):
        self.previous, self.configured = balance.active_profile(), balance._configured_path
        balance._configured_path = None
        balance.activate(balance.default_profile())
        self.addCleanup(lambda: balance.activate(self.previous))
        self.addCleanup(lambda: setattr(balance, "_configured_path", self.configured))
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(pg.quit)
        self.root = Path(self.tmp.name)
        self.app = App(self.root, capture=True)
        self.addCleanup(self.app.audio.close)
        self.app.game = new_game(seed=13, race_id="terran", with_ai=False, with_guardians=False,
                                 with_tombs=False, with_encounters=False, with_black_holes=False)
        self.app.settings["autosave"] = False
        self.app.open_designer()
        self.app.present()

    def click(self, key):
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        self.assertTrue(button.enabled, key)
        pos = self.app.window_pos(button.rect.center)
        for event in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(event, button=1, pos=pos))
            self.app.render()

    def fit(self, slot, identifier):
        self.click("design_mount_"+slot)
        self.app.design_module_page = controls.choices(self.app).index(identifier)//controls.OPTIONS_PER_PAGE
        self.click("design_option_"+(identifier or "standard"))
        self.click("design_install")

    def test_blank_hull_preview_replacement_and_default_engine_armor(self):
        app = self.app
        self.assertEqual(app.design_modules, [])
        self.assertIsNotNone(controls.error(app))
        self.fit("weapon_1", "laser")
        self.fit("core_1", "shield")
        before = controls.draft(app)
        self.click("design_option_damage_control")
        preview, error = controls.candidate(app)
        self.assertIsNone(error)
        self.assertEqual(controls.draft(app), before)
        self.assertEqual(preview.shields, 0)
        self.assertGreater(preview.repair_rate, 0)
        self.click("design_install")
        self.assertNotIn("shield", app.design_modules)
        self.fit("core_1", "command_relay")
        self.assertNotIn("damage_control", app.design_modules)
        base_speed = controls.draft(app).movement
        self.fit("engine", "engine")
        self.assertEqual(controls.draft(app).movement, base_speed+1)
        self.fit("armor", "armor")
        self.assertEqual(controls.draft(app).movement, base_speed)
        self.fit("armor", "reinforced_armor")
        self.assertNotIn("armor", app.design_modules)
        self.fit("engine", None)
        self.assertNotIn("engine", app.design_modules)

    def test_shared_bays_and_external_defenses_are_enforced_by_model(self):
        game = self.app.game
        for modules in (("laser", "shield", "damage_control"), ("laser",)*4+("point_defense",),
                        ("laser", "armor", "reinforced_armor"), ("laser", "engine", "engine")):
            with self.subTest(modules=modules), self.assertRaises(RuleError):
                game.save_design("Does not fit", "frigate", modules)
        design = game.save_design("Support frigate", "frigate", ["laser", "command_relay"])
        self.assertEqual(design.fit_version, 3)
        self.assertIn(("core_1", "command_relay"), design.mounts)
        cruiser = game.save_design("Self sufficient", "cruiser", ["laser", "shield", "damage_control"])
        self.assertGreater(cruiser.shields, 0)
        self.assertGreater(cruiser.repair_rate, 0)
        with self.assertRaises(RuleError):
            game.save_design("Too much", "cruiser", ["laser", "shield", "damage_control", "command_relay"])

    def test_empty_positions_and_paid_orders_survive_save_update_and_production(self):
        app, game = self.app, self.app.game
        self.fit("weapon_4", "torpedo")
        self.fit("armor", "armor")
        app.design_name = "Fourth mount"
        self.click("design_save")
        original = game.designs[0]
        self.assertNotIn("weapon_1", dict(original.mounts))
        self.assertEqual(dict(original.mounts)["weapon_4"], "torpedo")
        game.resources = game.credits = 10000
        self.click("design_build")
        queue = game.planet_at(0, 2).construction_queue
        self.fit("weapon_1", "laser")
        self.click("design_save")
        self.assertEqual(queue[0].design, original)
        self.assertNotEqual(game.designs[0], original)
        store = Storage(self.root)
        restored, _ = store.load(store.save(game))
        self.assertEqual(restored, game)
        self.assertEqual(restored.planet_at(0, 2).construction_queue[0].design.mounts, original.mounts)
        restored.buy_construction(0, 2)
        self.assertEqual(restored.ships[-1].design, original)
        self.assertEqual(GameState.from_dict(restored.to_dict()), restored)
        self.assertEqual(SAVE_VERSION, 66)

    def test_hull_changes_keep_excess_equipment_for_explicit_review(self):
        app = self.app
        app.choose_design_hull("titan")
        controls.set_modules(app, ["laser"]*6+["shield", "damage_control", "command_relay", "engine", "armor"])
        previous = sorted(app.design_modules)
        app.choose_design_hull("frigate")
        self.assertEqual(sorted(app.design_modules), previous)
        self.assertEqual(len(app.design_unplaced), 4)
        self.assertIsNotNone(controls.error(app))
        app.choose_design_hull("titan")
        self.assertFalse(app.design_unplaced)
        self.assertEqual(sorted(app.design_modules), previous)
        app.choose_design_hull("frigate")
        self.click("design_unplaced_clear")
        self.assertFalse(app.design_unplaced)
        self.assertIsNone(controls.error(app))

    def test_legacy_library_is_unchanged_until_refitting_and_rename_reorders_safely(self):
        app = self.app
        legacy = ShipDesign("design_1", "Old shield", "frigate", ("laser", "armor", "shield", "engine"))
        app.game.designs = [legacy]
        app.load_design(legacy)
        self.assertEqual(controls.draft(app), legacy)
        app.render()
        self.assertEqual(app.game.designs[0], legacy)
        app.design_name = "Refitted shield"
        app.save_ship_design()
        updated = app.game.designs[0]
        self.assertEqual(updated.fit_version, 3)
        self.assertEqual(sorted(updated.modules), sorted(legacy.modules))
        self.assertEqual((updated.hull, updated.shields, updated.movement),
                         (legacy.hull, legacy.shields, legacy.movement))
        crowded = ShipDesign("design_2", "Old combined systems", "frigate", ("laser", "shield", "damage_control"))
        app.load_design(crowded)
        self.assertEqual(controls.draft(app), crowded)
        self.assertEqual(app.design_unplaced, ["damage_control"])
        self.assertEqual(ShipDesign.from_dict(asdict(crowded)), crowded)
        repeated = ShipDesign("design_3", "Twin shields", "frigate", ("laser", "shield", "shield"))
        app.load_design(repeated)
        controls.install(app)  # Re-selecting an installed shield must not consume the excess copy.
        self.assertEqual(app.design_unplaced, ["shield"])
        self.assertEqual(controls.draft(app), repeated)
        for kind in HULLS:
            modern = standard_design(kind)
            old = ShipDesign(modern.id, modern.name, kind, modern.modules)
            self.assertTrue(is_standard_design(old))

    def test_corrupt_mappings_are_rejected_and_positions_do_not_change_combat_stats(self):
        first = build_design("design_1", "Left", "frigate", ("laser",), (("weapon_1", "laser"),))
        last = build_design("design_2", "Right", "frigate", ("laser",), (("weapon_4", "laser"),))
        self.assertEqual((first.damage, first.hull, first.movement), (last.damage, last.hull, last.movement))
        cases = [[pair] for pair in (("weapon_5", "laser"), ("core_1", "laser"), ("engine", "laser"),
                 ("weapon_1", "unknown"), (None, "laser"))]
        cases += [(first.mounts[0], first.mounts[0]), [], "weapon_1"]
        for mounts in cases:
            data = asdict(first); data["mounts"] = mounts
            with self.subTest(mounts=mounts), self.assertRaises(ValueError):
                ShipDesign.from_dict(data)

    def test_every_hull_autofit_uses_same_physical_rules_as_player(self):
        for kind in HULLS:
            with self.subTest(kind=kind):
                for design in (standard_design(kind), auto_design(kind, tuple(TECHNOLOGIES))):
                    self.assertEqual(design.fit_version, 3)
                    self.assertIsNone(loadout_error(kind, design.modules, fit_version=3))
                    self.assertIsNone(placement_error(kind, design.modules, design.mounts))
                    self.assertEqual(ShipDesign.from_dict(asdict(design)), design)

    def test_physical_blueprints_work_in_saved_combat_scenarios(self):
        design = build_design("design_1", "Repair cruiser", "cruiser", ["laser", "shield", "damage_control", "engine"])
        scenario = Scenario(designs=[design])
        scenario.player.ships = {design.id: 1}
        path = self.root/"scenario.json"
        save_scenario(path, scenario)
        restored = load_scenario(path)
        self.assertEqual(restored.designs, [design])
        game = build_game(restored)
        ship = next(s for s in game.combat.fleet("player") if s.design == design)
        self.assertEqual(ship.shields, design.shields)
        self.assertGreater(design.repair_rate, 0)
        self.assertEqual(ship.design.mounts, design.mounts)

    def test_old_balance_profiles_gain_mount_counts_without_changing_existing_values(self):
        profile = balance.default_profile()
        profile["version"] = 21
        profile["data"]["hulls"]["frigate"]["movement"] = 7
        for row in profile["data"]["hulls"].values():
            for key in ("external_mounts", "internal_bays", "hangar_bays"):
                row.pop(key)
        balance.activate(profile)
        self.assertEqual(HULLS["frigate"].movement, 7)
        self.assertEqual(HULLS["frigate"].internal_bays, 1)
        self.assertEqual(HULLS["titan"].external_mounts, 6)
        self.assertEqual(HULLS["carrier"].hangar_bays, 2)

    def test_clickable_mounts_and_module_options_at_multiple_window_sizes(self):
        for size in ((980, 900), (1280, 800), (1920, 1080)):
            self.app.window = pg.display.set_mode(size, pg.RESIZABLE)
            self.app.render(); self.app.present()
            for kind in HULLS:
                with self.subTest(size=size, kind=kind):
                    self.click("design_hull_"+kind)
                    for slot in mounts_for(kind):
                        self.click("design_mount_"+slot.id)
                        self.assertEqual(self.app.design_mount, slot.id)
                    self.assertTrue(all(self.app.canvas.get_rect().contains(b.rect) for b in self.app.buttons))
                    self.assertTrue(all(self.app.canvas.get_rect().contains(r) for r in self.app.design_mount_rects.values()))


if __name__ == "__main__":
    unittest.main()
