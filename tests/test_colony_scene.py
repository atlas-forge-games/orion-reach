"""Surface graphics follow real ownership, construction and selection state."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame as pg

from orion import building_art
from orion.buildings import BUILDINGS
from orion.colony_scene import PALETTES, is_headquarters, scene_buildings
from orion.model import PLAYER, RIVAL
from scenarios import fixed_start_game as new_game
from functools import partial

# Preserve these pre-exploration scenarios; fog-on rules have their own tests.
new_game = partial(new_game, fog_of_war=False)


class SceneDataTests(unittest.TestCase):
    def test_headquarters_belong_only_to_each_empires_homeworld(self):
        game = new_game(seed=2408)
        earth, mars = game.systems[0].worlds[2:4]
        rival = game.opponent
        home = game.planet_at(rival.home_system, rival.home_planet)
        self.assertTrue(is_headquarters(game, 0, earth))
        self.assertTrue(is_headquarters(game, rival.home_system, home))
        self.assertEqual(scene_buildings(game, 0, mars), [])
        mars.colonized, mars.owner, mars.population = True, PLAYER, 1
        self.assertFalse(is_headquarters(game, 0, mars))
        self.assertEqual([item.asset_id for item in scene_buildings(game, 0, mars)], ["shipyard"])

    def test_duplicates_and_mixed_queue_map_to_the_correct_existing_slots(self):
        game = new_game(seed=2408, with_ai=False)
        earth = game.systems[0].worlds[2]
        earth.buildings = ["research_lab", "factory", "factory"]
        game.credits = 1000
        game.queue_ship(0, 2)
        game.queue_building(0, 2, "mine")
        game.queue_building(0, 2, "factory")
        before = game.to_dict()
        items = {item.asset_id: item for item in scene_buildings(game, 0, earth)}
        self.assertEqual((items["factory"].completed, items["factory"].queued, items["factory"].slot), (2, 1, 1))
        self.assertEqual((items["mine"].completed, items["mine"].queued, items["mine"].slot), (0, 1, 3))
        self.assertEqual(items["shipyard"].queued, 1)
        self.assertEqual(game.to_dict(), before)


class SceneInterfaceTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.tmp.name), capture=True)
        self.app.game = new_game(seed=2408, with_ai=False)
        self.app.open_planet(2)
        self.app.render()
        self.app.present()

    def click(self, key):
        self.app.render()
        button = next(button for button in self.app.buttons if button.key == key)
        x, y = button.rect.center
        v = self.app.viewport
        pos = (v.x+round(x*v.w/1440), v.y+round(y*v.h/900))
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, button=1, pos=pos))
            self.app.render()

    def surface_keys(self):
        return {button.key for button in self.app.buttons if button.key.startswith("surface_")}

    def test_surface_updates_through_build_completion_demolition_and_scaled_clicks(self):
        self.app.window = pg.display.set_mode((980, 900), pg.RESIZABLE)
        self.app.present()
        self.assertEqual(self.surface_keys(), {"surface_headquarters", "surface_shipyard"})
        self.click("planet_change")
        self.click("production_build_factory")
        self.click("surface_factory")
        self.assertEqual(self.app.screen, "colony")
        self.assertEqual(self.app.colony_slot, 0)
        self.click("cancel_construction")
        self.click("tab_overview")
        self.assertNotIn("surface_factory", self.surface_keys())
        self.click("planet_change")
        self.click("production_build_factory")
        for _ in range(4):
            self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_e, mod=0))
            self.app.render()
        self.assertEqual(self.app.game.systems[0].worlds[2].buildings, ["factory"])
        self.click("surface_factory")
        self.click("demolish_building")
        self.click("dialog_ok")
        self.click("tab_overview")
        self.assertNotIn("surface_factory", self.surface_keys())
        self.click("surface_shipyard")
        self.assertEqual(self.app.screen, "shipyard")
        self.click("shipyard_back")
        self.click("surface_headquarters")
        self.assertEqual(self.app.screen, "empire")
        self.app.close_empire()
        self.assertEqual(self.app.screen, "planet")

    def test_surface_queue_click_keeps_ship_and_building_indices_separate(self):
        game = self.app.game
        game.credits = 1000
        game.systems[0].worlds[2].buildings = ["trade_center"]
        game.queue_ship(0, 2)
        game.queue_building(0, 2, "factory")
        game.queue_building(0, 2, "mine")
        self.click("surface_mine")
        self.assertEqual(self.app.colony_slot, 2)
        self.click("cancel_construction")
        self.assertEqual([p.item_id for p in game.systems[0].worlds[2].construction_queue], ["colony_ship", "factory"])

    def test_rival_surface_inspection_preserves_ownership_and_back_navigation(self):
        game = self.app.game = new_game(seed=2408)
        rival = game.opponent
        planet = game.planet_at(rival.home_system, rival.home_planet)
        planet.buildings = ["factory"]
        game.queue_building(rival.home_system, rival.home_planet, "mine", owner=RIVAL)
        game.selected_system, game.selected_planet = rival.home_system, rival.home_planet
        before = game.to_dict()
        self.app.go("planet")
        self.click("surface_headquarters")
        self.click("rival_back")
        self.assertEqual(self.app.screen, "planet")
        self.click("surface_factory")
        self.assertFalse(next(b for b in self.app.buttons if b.key == "demolish_building").enabled)
        self.click("tab_overview")
        self.click("surface_mine")
        self.assertFalse(next(b for b in self.app.buttons if b.key == "cancel_construction").enabled)
        self.click("tab_overview")
        self.click("surface_shipyard")
        self.assertFalse(next(b for b in self.app.buttons if b.key == "build_colony_ship").enabled)
        self.assertEqual(game.to_dict(), before)

    def test_full_colony_all_biomes_and_save_load_keep_scene_read_only(self):
        game = self.app.game
        earth = game.systems[0].worlds[2]
        earth.size = "Huge"
        earth.buildings = (list(BUILDINGS)*3)[:earth.building_capacity]
        for biome in PALETTES:
            earth.biome = biome
            before = game.to_dict()
            self.app.render()
            self.assertEqual(game.to_dict(), before)
            self.assertEqual(len(self.surface_keys()), min(len(BUILDINGS), earth.building_capacity)+2)
            buttons = [b for b in self.app.buttons if b.key.startswith("surface_")]
            for i, a in enumerate(buttons):
                self.assertTrue(pg.Rect(24, 314, 1392, 526).contains(a.rect))
                for b in buttons[i+1:]:
                    self.assertFalse(a.rect.colliderect(b.rect), (a.key, b.key))
        earth.biome = "Terran"
        expected = scene_buildings(game, 0, earth)
        self.app.save_game(autosave=True)
        restored, _ = self.app.storage.load(self.app.storage.saves_dir/"autosave.json")
        self.assertEqual(scene_buildings(restored, 0, restored.systems[0].worlds[2]), expected)

    def test_missing_and_corrupt_building_images_keep_controls_usable(self):
        assets = Path(self.tmp.name)/"missing_art"
        (assets/"buildings").mkdir(parents=True)
        (assets/"buildings/factory-v1.png").write_bytes(b"broken PNG")
        self.app.game.systems[0].worlds[2].buildings = list(BUILDINGS)
        try:
            with patch.object(building_art, "ASSETS", assets):
                building_art.load_building_art.cache_clear()
                building_art.building_sprite.cache_clear()
                self.app.render()
                for asset_id in building_art.BUILDING_ART_IDS:
                    self.assertIsNone(building_art.load_building_art(asset_id))
                self.assertEqual(len(self.surface_keys()), len(BUILDINGS)+2)
                self.click("surface_factory")
                self.assertEqual(self.app.colony_slot, 0)
        finally:
            building_art.load_building_art.cache_clear()
            building_art.building_sprite.cache_clear()


if __name__ == "__main__":
    unittest.main()
