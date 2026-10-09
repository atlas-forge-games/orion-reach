"""Local food, deterministic growth, production timing, AI and save continuity."""

import copy
import json
import os
from pathlib import Path
import tempfile
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame as pg

from orion.ai import run_ai
from orion.empire import colony_rows, summarize_empire
from orion.exploration import refresh
from orion.model import GameState, PLAYER, RIVAL, RuleError, SaveError, Ship
from scenarios import empty_fleet_game as new_game
from orion.population import BASE_FOOD, FARMER_OUTPUT, POPULATION_LIMITS
from orion.storage import SAVE_VERSION, Storage
from orion.victory import CampaignResult


class PopulationRulesTests(unittest.TestCase):
    def setUp(self):
        self.game = new_game(seed=2408, with_ai=False)
        self.earth = self.game.planet_at(0, 2)

    def test_limits_and_food_follow_size_and_biome_without_mutation(self):
        for size, capacity in POPULATION_LIMITS.items():
            for biome, food in BASE_FOOD.items():
                self.earth.size, self.earth.biome = size, biome
                before = self.game.to_dict()
                info = self.game.population_report(self.earth)
                expected_capacity = capacity+(4 if biome == "Gaia" else 0)
                self.assertEqual((info.capacity, info.produced, info.consumed), (expected_capacity, food+2*FARMER_OUTPUT[biome], 8))
                self.assertEqual(self.earth.population_capacity, expected_capacity)
                summarize_empire(self.game)
                colony_rows(self.game, sort_by="food")
                self.assertEqual(self.game.to_dict(), before)
        mars = self.game.planet_at(0, 3)
        info = self.game.population_report(mars)
        self.assertEqual((info.produced, info.consumed, info.growth_rate), (0, 0, 0))
        self.assertEqual(info.status, "Uncolonized")

    def test_initial_growth_forecast_and_taxes_change_on_the_following_turn(self):
        self.assertEqual(self.game.population_report(self.earth).turns_to_growth, 10)
        for _ in range(9):
            self.assertEqual(self.game.advance_turn().population, [])
        self.assertEqual((self.earth.population, self.earth.growth_progress), (8, 90))
        self.assertEqual(self.game.population_report(self.earth).turns_to_growth, 1)
        result = self.game.advance_turn()
        self.assertEqual((result.income, result.population), (8, ["Earth grew to 9 B"]))
        self.assertEqual((self.earth.population, self.earth.growth_progress, self.game.credits), (9, 0, 200))
        self.assertEqual(self.game.population_report(self.earth).turns_to_growth, 20)
        self.assertEqual(self.game.advance_turn().income, 9)
        self.assertEqual(self.game.credits, 209)

    def test_surplus_rate_is_capped_and_birth_carries_progress(self):
        self.earth.population, self.earth.growth_progress = 1, 90
        self.earth.farmers = 0
        self.assertEqual(self.game.population_report(self.earth).growth_rate, 25)
        self.game.advance_turn()
        self.assertEqual((self.earth.population, self.earth.growth_progress), (2, 15))

    def test_capacity_stops_growth_and_preserves_legacy_over_capacity_population(self):
        self.earth.size, self.earth.population, self.earth.growth_progress = "Tiny", 7, 95
        self.game.advance_turn()
        self.assertEqual((self.earth.population, self.earth.growth_progress), (8, 0))
        self.assertEqual(self.game.population_report(self.earth).status, "At population limit")
        self.earth.population, self.earth.growth_progress = 20, 75
        self.game = GameState.from_dict(self.game.to_dict())
        self.earth = self.game.planet_at(0, 2)
        self.game.advance_turn()
        self.assertEqual((self.earth.population, self.earth.growth_progress), (20, 0))

    def test_zero_and_negative_food_pause_growth_without_losing_people_or_progress(self):
        for population, status in ((10, "Needs food surplus"), (11, "Food shortage")):
            with self.subTest(population=population):
                self.earth.population, self.earth.growth_progress = population, 90
                self.assertEqual(self.game.population_report(self.earth).status, status)
                self.assertIsNone(self.game.population_report(self.earth).turns_to_growth)
                for _ in range(3):
                    self.game.advance_turn()
                self.assertEqual((self.earth.population, self.earth.growth_progress), (population, 90))
        self.earth.buildings = ["hydroponic_farm"]
        self.game.advance_turn()
        self.assertEqual((self.earth.population, self.earth.growth_progress), (12, 5))

    def test_food_is_local_even_when_empire_has_a_net_surplus(self):
        mars = self.game.planet_at(0, 3)
        mars.colonized, mars.owner, mars.population = True, PLAYER, 5
        mars.farmers = 2
        mars.growth_progress = 45
        totals = summarize_empire(self.game)
        self.assertEqual((totals.food_produced, totals.food_consumed, totals.food_shortages), (14, 13, 1))
        for _ in range(4):
            self.game.advance_turn()
        self.assertEqual((mars.population, mars.growth_progress), (5, 45))
        self.assertEqual(self.earth.growth_progress, 40)
        self.assertEqual([p.name for _, p in colony_rows(self.game, sort_by="food")], ["Mars", "Earth"])

    def test_farm_uses_normal_cost_queue_slot_and_starts_food_next_turn(self):
        self.game.queue_building(0, 2, "hydroponic_farm")
        self.assertEqual((self.game.credits, self.earth.used_slots), (90, 1))
        self.assertEqual(self.game.queue_estimates(self.earth), [3])
        for _ in range(3):
            result = self.game.advance_turn()
        self.assertEqual(result.completed, ["Hydroponic farm on Earth"])
        self.assertEqual((self.earth.population, self.earth.growth_progress), (8, 30))
        self.assertEqual(self.game.population_report(self.earth).produced, 14)
        self.game.advance_turn()
        self.assertEqual(self.earth.growth_progress, 55)
        self.assertEqual(self.game.demolish_building(0, 2, 0), "hydroponic_farm")
        self.assertEqual(self.game.population_report(self.earth).produced, 10)
        self.game.queue_building(0, 2, "hydroponic_farm")
        self.game.advance_turn()
        self.assertEqual(self.game.cancel_construction(0, 2, 0), 20)
        self.assertEqual(self.earth.used_slots, 0)

    def test_farming_technology_preserves_income_and_applies_food_next_turn(self):
        self.earth.population = 10
        self.earth.buildings = ["research_lab"]
        self.game.research = 36
        self.game.choose_research("symbiotic_farming")
        result = self.game.advance_turn()
        self.assertEqual(result.discoveries, ["Symbiotic Farming"])
        self.assertEqual((self.earth.growth_progress, result.income), (0, 10))
        self.assertEqual(self.game.population_report(self.earth).produced, 12)
        self.assertEqual(self.game.advance_turn().income, 12)
        self.assertEqual(self.earth.growth_progress, 10)

    def test_new_colonies_use_biology_colonists_and_begin_at_zero_progress(self):
        for tech in ("colony_biospheres", "colony_biogenesis", "radiation_shields"):
            self.game.research += 100
            self.game.choose_research(tech)
        self.game.ships = [Ship(1, "colony_ship", 0)]
        self.game.next_ship_id = 2
        mercury = self.game.planet_at(0, 0)
        self.game.colonize(1, 0, 0)
        self.assertEqual((mercury.population, mercury.growth_progress), (4, 0))
        self.assertEqual(self.game.population_report(mercury).balance, 0)
        self.game.advance_turn()
        self.assertEqual((mercury.population, mercury.growth_progress), (4, 0))

    def test_ai_pays_for_farms_then_grows_under_the_same_rules(self):
        game = new_game(seed=2408, fog_of_war=False)
        home = game.planet_at(game.opponent.home_system, game.opponent.home_planet)
        home.size, home.biome = "Medium", "Tundra"
        for _ in range(10):
            game.advance_turn()
        self.assertEqual(home.buildings, ["hydroponic_farm"]*2)
        self.assertEqual((game.opponent.credits, home.population, home.growth_progress), (140, 9, 0))
        game.advance_turn()
        self.assertEqual(home.growth_progress, 15)
        self.assertEqual(game.planet_at(0, 2).growth_progress, 5)
        self.assertEqual(game.credits, 209)  # Rival farms do not spend player credits.

    def test_ai_reserves_remaining_slots_to_support_future_population(self):
        game = new_game(seed=2408, fog_of_war=False)
        home = game.planet_at(game.opponent.home_system, game.opponent.home_planet)
        home.size, home.biome, home.population = "Medium", "Terran", 8
        home.buildings = ["research_lab"]*6
        self.assertEqual(game.population_report(home).balance, 2)
        run_ai(game)
        self.assertEqual(home.construction_queue[0].item_id, "hydroponic_farm")

    def test_capture_preserves_progress_and_farms_but_food_bonus_follows_owner(self):
        game = new_game(seed=2408, fog_of_war=False)
        sid, pid = game.opponent.home_system, game.opponent.home_planet
        home = game.planet_at(sid, pid)
        home.growth_progress, home.buildings = 65, ["hydroponic_farm"]
        game.opponent.research = 40
        game.choose_research("symbiotic_farming", owner=RIVAL)
        produced = game.population_report(home).produced
        game.ships = [Ship(i, "troop_transport", sid) for i in (1, 2)]
        game.next_ship_id = 3
        self.assertTrue(game.invade(sid, pid).captured)
        self.assertEqual((home.population, home.growth_progress, home.buildings), (8, 65, ["hydroponic_farm"]))
        self.assertEqual(game.population_report(home).produced, produced-2)

    def test_combat_and_finished_campaign_lock_growth(self):
        game = new_game(seed=2408)
        earth = game.planet_at(0, 2)
        earth.growth_progress = 95
        game.ships = [Ship(1, "frigate", 0), Ship(2, "frigate", 0, owner=RIVAL)]
        game.next_ship_id = 3
        game.start_combat(0)
        with self.assertRaises(RuleError):
            game.advance_turn()
        self.assertEqual((earth.population, earth.growth_progress), (8, 95))
        self.game.result = CampaignResult(PLAYER, "science", self.game.turn)
        with self.assertRaises(RuleError):
            self.game.advance_turn()
        self.assertEqual((self.earth.population, self.earth.growth_progress), (8, 0))

    def test_growth_and_food_changes_do_not_leak_through_a_stale_survey(self):
        game = new_game(seed=2408)
        sid, pid = game.opponent.home_system, game.opponent.home_planet
        home = game.planet_at(sid, pid)
        home.biome, home.size, home.growth_progress = "Terran", "Medium", 95
        game.ships = [Ship(1, "scout", sid)]
        game.next_ship_id = 2
        refresh(game)
        game.send_ship(1, 0)
        game.advance_turn()
        self.assertEqual((home.population, home.growth_progress), (9, 5))
        known = game.known_system(sid).worlds[pid]
        self.assertEqual((known.population, known.growth_progress), (8, 95))
        restored = GameState.from_dict(game.to_dict())
        self.assertEqual(restored.known_system(sid).worlds[pid], known)
        game.ships = [Ship(1, "scout", sid)]
        refresh(game)
        self.assertEqual(game.known_system(sid).worlds[pid], home)


class PopulationSaveTests(unittest.TestCase):
    def test_growth_and_farm_queue_roundtrip_and_resume_deterministically(self):
        game = new_game(seed=2408)
        game.queue_building(0, 2, "hydroponic_farm")
        game.advance_turn()
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            restored, _ = storage.load(storage.save(game))
            for _ in range(20):
                self.assertEqual(restored.advance_turn(), game.advance_turn())
                self.assertEqual(restored, game)
            self.assertEqual(storage.load(storage.save(restored))[0], game)

    def test_v10_migrates_planets_and_surveys_without_rewriting_or_losing_fields(self):
        game = new_game(seed=2408)
        home = game.opponent.home_system
        game.ships = [Ship(1, "scout", home)]
        game.next_ship_id = 2
        refresh(game)
        game.send_ship(1, 0)
        game.queue_building(0, 2, "factory")
        game.advance_turn()
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            path = storage.save(game)
            payload = json.loads(path.read_text())
            payload["version"] = 10
            records = payload["game"]["systems"] + payload["game"]["exploration"]["surveys"]
            for record in records:
                for planet in record["worlds"]:
                    planet.pop("growth_progress")
            path.write_text(json.dumps(payload))
            original = path.read_bytes()
            restored, _ = storage.load(path)
            self.assertEqual(path.read_bytes(), original)
            expected = copy.deepcopy(payload["game"])
            for record in expected["systems"] + expected["exploration"]["surveys"]:
                for planet in record["worlds"]:
                    planet["growth_progress"] = 0
                    planet["farmers"], planet["scientists"] = min(2, planet["population"]), 0
            self.assertEqual(restored.to_dict(), expected)
            self.assertEqual(json.loads(storage.save(restored).read_text())["version"], SAVE_VERSION)
            self.assertEqual(SAVE_VERSION, 21)

    def test_invalid_growth_progress_in_planets_and_surveys_is_rejected(self):
        game = new_game(seed=2408)
        for source in ("systems", "surveys"):
            for value in (-1, 100, 1.5, True, None, "25", "missing"):
                with self.subTest(source=source, value=value):
                    data = game.to_dict()
                    records = data["systems"] if source == "systems" else data["exploration"]["surveys"]
                    earth = next(p for r in records for p in r["worlds"] if p["name"] == "Earth")
                    if value == "missing":
                        earth.pop("growth_progress")
                    else:
                        earth["growth_progress"] = value
                    with self.assertRaises(SaveError):
                        GameState.from_dict(data)
        data = game.to_dict()
        data["systems"][0]["worlds"][3]["growth_progress"] = 1
        with self.assertRaises(SaveError):
            GameState.from_dict(data)


class PopulationInterfaceTests(unittest.TestCase):
    def test_farm_controls_growth_and_food_sort_work_in_a_resized_window(self):
        from orion.app import App
        with tempfile.TemporaryDirectory() as folder:
            app = App(Path(folder), capture=True)
            self.addCleanup(pg.quit)
            app.window = pg.display.set_mode((980, 900), pg.RESIZABLE)
            app.game = new_game(seed=2408, with_ai=False)
            app.open_planet(2)

            def click(key):
                app.render()
                app.present()
                button = next(b for b in app.buttons if b.key == key)
                self.assertTrue(button.enabled, key)
                x, y = button.rect.center
                view = app.viewport
                pos = view.x+round(x*view.w/1440), view.y+round(y*view.h/900)
                for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
                    app.handle_event(pg.event.Event(kind, button=1, pos=pos))
                    app.render()

            click("planet_change")
            click("production_build_hydroponic_farm")
            earth = app.game.planet_at(0, 2)
            self.assertEqual(earth.construction_queue[0].item_id, "hydroponic_farm")
            for _ in range(6):
                app.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_e, mod=0))
                app.render()
            self.assertEqual((earth.population, earth.growth_progress), (9, 5))
            self.assertEqual(app.game.population_report(earth).produced, 14)
            click("surface_hydroponic_farm")
            self.assertEqual((app.screen, app.colony_slot), ("colony", 0))
            restored, _ = app.storage.load(app.storage.save(app.game))
            self.assertEqual(restored, app.game)
            app.open_empire()
            click("empire_sort_food")
            self.assertEqual(app.empire_sort, "food")
            click("empire_colony_0_2")
            self.assertEqual(app.screen, "planet")


if __name__ == "__main__":
    unittest.main()
