"""Continuous credit production and idle-colony workflow through real controls."""

import copy
import json
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame as pg

from orion.app import App
from orion.buildings import BUILDINGS
from orion.empire import colony_rows, summarize_empire
from orion.model import GameState, PLAYER, RIVAL, RuleError, SaveError, Ship
from orion.production import MAX_QUEUE
from orion.research import TECHNOLOGIES, colony_yields
from orion.storage import Storage
from scenarios import empty_fleet_game


class TradeGoodsTests(unittest.TestCase):
    def setUp(self):
        self.game = empty_fleet_game(seed=2408, with_ai=False)
        self.planet = self.game.planet_at(0, 2)

    def test_every_building_blocks_completed_queued_and_paused_duplicates(self):
        self.game.technology.completed = list(TECHNOLOGIES)
        for item in BUILDINGS:
            with self.subTest(building=item):
                self.planet.buildings.clear()
                self.planet.construction_queue.clear()
                self.game.queue_building(0, 2, item)
                self.game.set_trade_goods(0, 2)
                before = self.game.to_dict()
                with self.assertRaisesRegex(RuleError, "Only one"):
                    self.game.queue_project(0, 2, item)
                self.assertEqual(self.game.to_dict(), before)
                self.game.cancel_construction(0, 2, 0)
                self.assertIsNone(self.game.build_error(0, 2, item))
                self.planet.buildings.append(item)
                before = self.game.to_dict()
                with self.assertRaisesRegex(RuleError, "Only one"):
                    self.game.queue_building(0, 2, item)
                self.assertEqual(self.game.to_dict(), before)
                self.game.demolish_building(0, 2, 0)
                self.assertIsNone(self.game.build_error(0, 2, item))

    def test_uniqueness_is_per_planet_applies_to_ai_and_does_not_limit_ships(self):
        game = empty_fleet_game(seed=2408)
        mars = game.planet_at(0, 3)
        mars.colonized, mars.owner, mars.population = True, PLAYER, 1
        home_system, home = game.headquarters(RIVAL)
        for sid, pid, owner in ((0, 2, PLAYER), (0, 3, PLAYER), (home_system.id, home.id, RIVAL)):
            game.queue_building(sid, pid, "factory", owner=owner)
            with self.assertRaisesRegex(RuleError, "Only one"):
                game.queue_building(sid, pid, "factory", owner=owner)
            game.queue_ship(sid, pid, "scout", owner=owner)
            game.queue_ship(sid, pid, "scout", owner=owner)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_old_duplicate_buildings_and_paid_orders_survive_save_loading(self):
        self.planet.buildings = ["factory", "factory"]
        from orion.model import ConstructionProject
        self.planet.construction_queue = [ConstructionProject("mine", progress=3), ConstructionProject("mine")]
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            restored, _ = storage.load(storage.save(self.game))
        self.assertEqual(restored, self.game)
        for item in ("factory", "mine"):
            with self.assertRaisesRegex(RuleError, "Only one"):
                restored.queue_project(0, 2, item)

    def test_credits_floor_each_colonys_available_industry_without_bonus_scaling(self):
        self.planet.farmers = self.planet.scientists = self.planet.miners = 0
        for industry in (1, 3, 4, 9, 10, 13, 20):
            self.planet.population = industry
            for bonuses in ({}, {"industry_percent": 25, "income_percent": 100},
                            {"assembly_percent": 50}):
                self.planet.trade_goods = False
                before = colony_yields(self.planet, bonuses)
                self.game.set_trade_goods(0, 2)
                after = colony_yields(self.planet, bonuses)
                self.assertEqual(after, (before[0], before[1]+before[0]*3//10, before[2]))

    def test_turn_pays_once_and_does_not_finish_buildings_spend_materials_or_advance_paused_work(self):
        self.game.queue_building(0, 2, "factory")
        self.game.advance_turn()
        self.game.queue_project(0, 2, "research_lab")
        queue = copy.deepcopy(self.planet.construction_queue)
        self.game.set_trade_goods(0, 2)
        slots = self.planet.used_slots
        for _ in range(3):
            credits, resources = self.game.credits, self.game.resources
            expected_income = self.game.empire_rates[0]
            expected_resources = self.game.resource_rate()
            report = self.game.advance_turn()
            self.assertEqual(self.game.credits-credits, expected_income)
            self.assertEqual(report.income, expected_income)
            self.assertEqual(self.game.resources-resources, expected_resources)
            self.assertEqual(self.planet.construction_queue, queue)
            self.assertEqual(self.planet.used_slots, slots)
            self.assertFalse(report.completed)
            self.assertTrue(self.planet.trade_goods)

    def test_queue_order_pause_resume_and_forecasts_preserve_paid_progress(self):
        self.game.queue_project(0, 2, "factory")
        self.game.advance_turn()
        original = copy.deepcopy(self.planet.construction_queue[0])
        self.game.queue_project(0, 2, "mine")
        self.game.queue_project(0, 2, "scout")
        self.assertEqual([p.item_id for p in self.planet.construction_queue], ["factory", "mine", "scout"])
        self.game.queue_project(0, 2, "trade_goods")
        self.assertEqual(self.game.queue_estimates(self.planet), [None]*3)
        self.assertEqual(self.planet.queue_estimates(), [None]*3)
        before = self.game.to_dict()
        self.assertTrue(all(t is not None for t in self.game.queue_estimates(self.planet, "scout")))
        self.assertEqual(self.game.to_dict(), before)
        self.game.prioritize_construction(0, 2, 0)
        self.assertFalse(self.planet.trade_goods)
        self.assertEqual(self.planet.construction_queue[0], original)
        self.game.set_trade_goods(0, 2)
        self.game.queue_ship(0, 2, "scout")
        self.assertFalse(self.planet.trade_goods)
        self.assertEqual(self.planet.construction_queue[0], original)

    def test_trade_goods_needs_no_slots_resources_or_queue_space_and_cannot_be_bought(self):
        self.planet.buildings = ["solar_array"]*self.planet.building_capacity
        for _ in range(MAX_QUEUE):
            self.game.queue_ship(0, 2, "scout")
        self.game.resources = self.game.credits = 0
        self.game.set_trade_goods(0, 2)
        self.assertEqual(self.game.project_price("trade_goods"), 0)
        self.assertEqual(self.game.buy_construction_cost(0, 2), 0)
        before = self.game.to_dict()
        with self.assertRaises(RuleError):
            self.game.buy_construction(0, 2)
        with self.assertRaises(RuleError):
            self.game.queue_ship(0, 2, "scout")
        self.assertEqual(self.game.to_dict(), before)

    def test_no_trade_goods_income_on_the_turn_a_normal_queue_finishes(self):
        self.game.queue_ship(0, 2, "scout")
        self.game.advance_turn()
        expected = self.game.empire_rates[0]
        report = self.game.advance_turn()
        self.assertTrue(report.completed)
        self.assertEqual(report.income, expected)
        self.assertTrue(self.planet.production_idle)
        self.game.set_trade_goods(0, 2)
        self.assertFalse(self.planet.production_idle)
        self.assertEqual(summarize_empire(self.game).idle, 0)
        self.assertEqual(colony_rows(self.game, "idle"), [])

    def test_owner_rules_and_abandonment(self):
        game = empty_fleet_game(seed=2408)
        sid, pid = game.opponent.home_system, game.opponent.home_planet
        for s, p in ((sid, pid), (0, 3)):
            before = game.to_dict()
            with self.assertRaises(RuleError):
                game.set_trade_goods(s, p)
            self.assertEqual(game.to_dict(), before)
        game.set_trade_goods(sid, pid, owner=RIVAL)
        self.assertTrue(game.planet_at(sid, pid).trade_goods)
        from orion.raiding import abandon
        abandon(game.planet_at(sid, pid))
        self.assertFalse(game.planet_at(sid, pid).trade_goods)
        game.ships = [Ship(1, "frigate", 0), Ship(2, "frigate", 0, owner=RIVAL)]
        game.next_ship_id = 3
        game.start_combat(0)
        with self.assertRaises(RuleError):
            game.set_trade_goods(0, 2)

    def test_save_roundtrip_and_real_v34_schema_migration_include_surveys(self):
        self.game.queue_building(0, 2, "factory")
        self.game.advance_turn()
        self.game.set_trade_goods(0, 2)
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            path = storage.save(self.game)
            self.assertEqual(json.loads(path.read_text())["version"], 44)
            self.assertEqual(storage.load(path)[0], self.game)
        legacy = self.game.to_dict()
        for row in legacy["systems"]+legacy["exploration"]["surveys"]:
            for planet in row["worlds"]:
                planet.pop("trade_goods")
        before = copy.deepcopy(legacy)
        restored = GameState.from_dict(legacy, version=34)
        self.assertEqual(legacy, before)
        self.assertFalse(restored.planet_at(0, 2).trade_goods)
        self.assertEqual(restored.planet_at(0, 2).construction_queue, self.planet.construction_queue)
        self.assertEqual(GameState.from_dict(restored.to_dict()), restored)

    def test_malformed_trade_mode_is_rejected_in_worlds_and_surveys(self):
        for source in ("systems", "surveys"):
            for value in (1, "yes", None):
                payload = self.game.to_dict()
                rows = payload["systems"] if source == "systems" else payload["exploration"]["surveys"]
                world = next(p for row in rows for p in row["worlds"] if p["name"] == "Earth")
                world["trade_goods"] = value
                with self.assertRaises(SaveError):
                    GameState.from_dict(payload)
        payload = self.game.to_dict()
        payload["systems"][0]["worlds"][3]["trade_goods"] = True
        with self.assertRaises(SaveError):
            GameState.from_dict(payload)


class ProductionInterfaceTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.folder.name), capture=True)
        self.app.game = empty_fleet_game(seed=2408, with_ai=False)
        self.game = self.app.game
        self.planet = self.game.planet_at(0, 2)
        self.game.choose_research("automated_factories")
        self.app.go("galaxy")

    def click(self, key):
        self.app.render()
        self.app.present()
        button = next(b for b in self.app.buttons if b.key == key)
        self.assertTrue(button.enabled, key)
        x, y = button.rect.center
        v = self.app.viewport
        pos = v.x+round(x*v.w/1440), v.y+round(y*v.h/900)
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, button=1, pos=pos))
            self.app.render()

    def test_multiple_clicks_append_and_reprioritize_without_leaving_picker(self):
        self.app.open_planet(2)
        self.click("planet_change")
        for kind in ("factory", "mine", "research_lab"):
            self.click("production_build_"+kind)
            self.assertEqual(self.app.screen, "production")
        self.assertEqual([p.item_id for p in self.planet.construction_queue], ["factory", "mine", "research_lab"])
        self.click("production_priority_1")
        self.assertEqual(self.app.screen, "production")
        self.assertEqual(self.planet.construction_queue[0].item_id, "mine")
        self.click("production_return")
        self.assertFalse(self.planet.trade_goods)
        self.assertEqual(self.app.storage.load(self.app.storage.saves_dir/"autosave.json")[0], self.game)

    def catalogue(self):
        self.app.catalog_page = 0
        keys = set()
        while True:
            self.app.render()
            keys.update(b.key.removeprefix("production_build_") for b in self.app.buttons
                        if b.key.startswith("production_build_") and b.enabled)
            if not next(b for b in self.app.buttons if b.key == "catalog_next").enabled:
                break
            self.click("catalog_next")
        return keys

    def test_picker_filters_research_slots_and_duplicates_and_restores_cancelled_choices(self):
        from test_research_expansion import discover
        self.app.open_planet(2)
        self.click("planet_change")
        self.assertIn("solar_array", self.catalogue())
        self.assertNotIn("fusion_plant", self.catalogue())
        self.game.research = self.game.technology.project_cost
        self.game.advance_research()
        discover(self.game, "fusion_power")
        self.assertIn("fusion_plant", self.catalogue())
        self.planet.buildings = ["mine"]
        self.app.catalog_page = 0
        self.click("production_build_factory")
        self.assertNotIn("factory", self.catalogue())
        self.assertNotIn("mine", self.catalogue())
        self.click("production_cancel_0")
        self.assertIn("factory", self.catalogue())
        self.planet.buildings = list(BUILDINGS)[:self.planet.building_capacity]
        self.assertFalse(self.catalogue() & BUILDINGS.keys())
        self.assertIn("scout", self.catalogue())
        self.assertIn("trade_goods", self.catalogue())
        self.planet.buildings.clear()
        for _ in range(MAX_QUEUE):
            self.game.queue_ship(0, 2, "scout")
        self.app.catalog_page = 99
        self.assertEqual(self.catalogue(), {"trade_goods"})
        self.assertEqual(self.app.catalog_page, 0)
        self.click("production_cancel_0")
        self.assertIn("factory", self.catalogue())

    def test_cancel_last_order_then_escape_defaults_to_trade_goods_and_autosaves(self):
        self.app.open_planet(2)
        self.click("planet_change")
        self.click("production_build_factory")
        self.click("production_cancel_0")
        self.assertTrue(self.planet.production_idle)
        self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_ESCAPE, mod=0))
        self.assertEqual(self.app.screen, "planet")
        self.assertTrue(self.planet.trade_goods)
        self.app.render()
        self.assertFalse(next(b for b in self.app.buttons if b.key == "planet_buy").enabled)
        self.assertEqual(self.app.storage.load(self.app.storage.saves_dir/"autosave.json")[0], self.game)

    def test_explicit_trade_goods_stays_open_and_build_button_resumes_queue(self):
        self.app.open_planet(2)
        self.click("planet_change")
        self.click("production_build_factory")
        self.click("production_build_trade_goods")
        self.assertTrue(self.planet.trade_goods)
        self.assertEqual(self.app.screen, "production")
        self.click("production_build_mine")
        self.assertFalse(self.planet.trade_goods)
        self.assertEqual([p.item_id for p in self.planet.construction_queue], ["factory", "mine"])

    def test_end_turn_reviews_multiple_idle_worlds_before_advancing(self):
        mars = self.game.planet_at(0, 3)
        mars.colonized, mars.owner, mars.population = True, PLAYER, 1
        from orion.exploration import refresh
        refresh(self.game)
        self.app.advance_turn()
        self.assertEqual((self.app.screen, self.game.selected_planet, self.game.turn), ("planet", 2, 1))
        self.click("planet_return")
        self.assertTrue(self.planet.trade_goods)
        self.assertEqual((self.app.screen, self.game.selected_planet, self.game.turn), ("planet", 3, 1))
        self.click("planet_return")
        self.assertTrue(mars.trade_goods)
        self.assertEqual(self.app.screen, "galaxy")
        self.app.advance_turn()
        self.assertEqual((self.game.turn, self.app.screen), (2, "galaxy"))

    def test_end_turn_from_review_accepts_trade_goods_without_repeated_prompts(self):
        self.app.advance_turn()
        self.assertEqual(self.game.turn, 1)
        self.app.advance_turn()
        self.assertEqual(self.game.turn, 2)
        self.assertTrue(self.planet.trade_goods)

    def test_finished_queue_opens_planet_and_remaining_queue_does_not(self):
        self.game.queue_ship(0, 2, "scout")
        self.game.queue_ship(0, 2, "scout")
        self.app.advance_turn()
        self.app.advance_turn()
        self.assertEqual(self.app.screen, "galaxy")
        self.app.advance_turn()
        self.app.advance_turn()
        self.assertEqual((self.app.screen, self.game.selected_planet), ("planet", 2))
        self.assertTrue(self.planet.production_idle)

    def test_idle_after_research_completion_waits_until_research_screen_closes(self):
        self.game.technology.active = None
        self.game.queue_ship(0, 2, "scout")
        self.game.advance_turn()
        self.app.advance_turn()
        self.assertEqual(self.app.screen, "research")
        self.app.close_research()
        self.assertEqual((self.app.screen, self.game.selected_planet), ("planet", 2))

    def test_finished_queue_in_open_picker_is_reviewed_after_research(self):
        self.game.technology.active = None
        self.game.queue_ship(0, 2, "scout")
        self.game.advance_turn()
        self.app.open_planet(2)
        self.app.open_production()
        self.app.advance_turn()
        self.assertEqual(self.app.screen, "research")
        self.app.close_research()
        self.assertEqual(self.app.screen, "planet")
        self.assertTrue(self.planet.production_idle)
        self.assertIsNotNone(self.app.idle_colony_review)

    def test_pause_info_and_render_do_not_change_production_but_switching_worlds_does(self):
        self.app.open_planet(2)
        before = self.game.to_dict()
        self.app.open_info()
        self.app.close_info()
        self.app.pause()
        self.app.resume()
        self.app.render()
        self.assertEqual(self.game.to_dict(), before)
        self.app.open_planet(3)
        self.assertTrue(self.planet.trade_goods)
        self.assertFalse(self.game.planet_at(0, 3).trade_goods)

    def test_observer_does_not_prompt_or_change_colony_production(self):
        from orion.model import new_game
        self.app.game = new_game(seed=2408, race_id="observer", rival_count=2)
        self.app.reset_fleet_view()
        self.app.go("galaxy")
        self.app.advance_turn()
        self.assertEqual(self.app.screen, "galaxy")
        self.assertEqual(self.app.game.turn, 2)


if __name__ == "__main__":
    unittest.main()
