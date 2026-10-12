from scenarios import legacy_economy
"""Research decisions, real gameplay effects, migrations and screen interaction."""

import copy
import json
import os
import tempfile
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame as pg

from orion.buildings import BUILDINGS
from orion.empire import summarize_empire
from orion.model import GameState, PLAYER, RIVAL, RuleError, SaveError, Ship
from scenarios import empty_fleet_game as new_game, place_near
from functools import partial

# Preserve these pre-exploration scenarios; fog-on rules have their own tests.
new_game = partial(new_game, fog_of_war=False)
from orion.production import travel_turns
from orion.research import BRANCHES, TECHNOLOGIES, branch_tiers, choices
from orion.storage import SAVE_VERSION, Storage


def discover(game, identifier, owner=PLAYER):
    """Fund an ordinary choice, including its prerequisite, for effect fixtures."""
    technology = TECHNOLOGIES[identifier]
    state = game.research_state(owner)
    if technology.tier == 2 and state.status(identifier) == "locked":
        discover(game, choices(technology.branch, 1)[0].id, owner)
    game._empire(owner).research += technology.cost
    return game.choose_research(identifier, owner=owner)


class ResearchRulesTests(unittest.TestCase):
    def test_two_exclusive_choices_and_sequential_unlocks_in_nine_branches(self):
        self.assertEqual((len(BRANCHES), len(TECHNOLOGIES)), (9, 89))  # Two new paired Computers tiers.
        for branch in BRANCHES:
            game = new_game(seed=2408, with_ai=False)
            state = game.technology
            first, second = choices(branch, 1)
            advanced = choices(branch, 2)
            self.assertEqual((len(choices(branch, 1)), len(advanced)), (2, 2))
            for invalid in (advanced[0].id, "missing", [], None):
                before = game.to_dict()
                with self.assertRaises(RuleError):
                    game.choose_research(invalid)
                self.assertEqual(game.to_dict(), before)
            game.choose_research(first.id)
            self.assertEqual(state.status(second.id), "available")
            for invalid in (first.id, advanced[0].id):
                with self.assertRaises(RuleError):
                    game.choose_research(invalid)
            game.choose_research(second.id)
            game.choose_research(first.id)
            game.research = first.cost
            game.advance_research()
            self.assertEqual(state.status(second.id), "excluded")
            self.assertEqual(state.status(advanced[0].id), "available")
            discover(game, advanced[1].id)
            self.assertEqual(state.status(advanced[0].id), "excluded")
            self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_banked_points_overflow_and_new_effects_start_after_completion(self):
        game = new_game(seed=2408, with_ai=False)
        earth = game.planet_at(0, 2)
        earth.buildings = ["research_lab"]
        game.queue_building(0, 2, "factory")
        game.research = TECHNOLOGIES["civil_engineering"].cost-3
        credits = game.credits
        self.assertIsNone(game.choose_research("civil_engineering"))
        self.assertEqual((game.research, game.technology.progress, game.credits), (0, TECHNOLOGIES["civil_engineering"].cost-3, credits))
        report = game.advance_turn()
        self.assertEqual((report.research, report.discoveries), (4, ["Civil Engineering"]))
        self.assertEqual((game.research, game.technology.active, game.technology.progress), (1, None, 0))
        self.assertEqual(earth.construction_queue[0].progress, 6)
        self.assertEqual(game.planet_yields(earth)[0], 8)
        game.advance_turn()
        self.assertEqual((earth.construction_queue[0].progress, game.research), (14, 5))
        game.research = TECHNOLOGIES["orbital_assembly"].cost+50
        self.assertEqual(game.choose_research("orbital_assembly").name, "Orbital Assembly")
        self.assertEqual(game.research, 50)

    def test_project_waits_for_laboratory_and_switch_replaces_the_active_project(self):
        game = new_game(seed=2408, with_ai=False)
        game.choose_research("ion_drives")
        game.choose_research("civil_engineering")
        self.assertEqual(game.technology.active, "civil_engineering")
        self.assertEqual(game.technology.completed, [])
        game.queue_building(0, 2, "research_lab")
        for _ in range(5):
            game.advance_turn()
        self.assertEqual(game.technology.progress, 0)
        game.advance_turn()
        self.assertEqual((game.technology.progress, game.research), (4, 0))

    def test_building_and_colony_bonuses_stack_and_remain_owned(self):
        game = new_game(seed=2408)
        earth = game.planet_at(0, 2)
        home = game.planet_at(game.opponent.home_system, game.opponent.home_planet)
        earth.buildings = ["solar_array", "research_lab", "research_lab", "factory", "mine", "trade_center"]
        home.buildings = earth.buildings.copy()
        home.richness = earth.richness
        for identifier in ("research_instruments", "research_networks", "superconductors"):
            discover(game, identifier)
        self.assertEqual(game.planet_yields(earth), (17, 7, 19))
        self.assertEqual(game.planet_yields(home), (16, 7, 8))
        self.assertEqual(game.building_yields(BUILDINGS["research_lab"], earth), (0, 0, 9))
        summary = summarize_empire(game)
        self.assertEqual((summary.industry, summary.income, summary.research), (17, 7, 19))
        self.assertEqual(game.empire_rates, (7, 19))
        self.assertEqual(game.planet_yields(game.planet_at(0, 3)), (0, 0, 0))

    def test_forecasts_match_shared_production_with_researched_factory_output(self):
        game = new_game(seed=2408, with_ai=False)
        discover(game, "automated_factories")
        discover(game, "planetary_automation")
        game.credits = game.resources = 500
        earth = game.planet_at(0, 2)
        game.queue_building(0, 2, "factory")
        game.queue_building(0, 2, "trade_center")
        game.queue_ship(0, 2)
        before = game.to_dict()
        forecast = game.queue_estimates(earth, "mine")
        self.assertEqual(forecast[0], 4)
        self.assertEqual(game.to_dict(), before)
        game.queue_building(0, 2, "mine")
        actual = []
        for turn in range(1, forecast[-1]+1):
            report = game.advance_turn()
            actual.extend([turn]*len(report.completed))
        self.assertEqual(actual, forecast)

    def test_discounts_and_refunds_use_original_payment_even_after_discoveries(self):
        game = new_game(seed=2408, with_ai=False)
        earth = game.planet_at(0, 2)
        game.queue_building(0, 2, "factory")
        game.fund_project(earth.construction_queue[0])
        discover(game, "prefabricated_structures")
        discover(game, "composite_structures")
        self.assertEqual(game.project_price("factory"), 30)
        self.assertEqual(game.cancel_construction(0, 2, 0), "45 RES")
        game.queue_building(0, 2, "factory")
        self.assertEqual(earth.construction_queue[0].resource_cost, 30)
        game.advance_turn()
        restored = GameState.from_dict(game.to_dict())
        self.assertEqual(restored.cancel_construction(0, 2, 0), "22 RES")
        self.assertEqual(game.cancel_construction(0, 2, 0), "22 RES")
        ships = new_game(seed=2408, with_ai=False)
        discover(ships, "orbital_assembly")
        discover(ships, "lightweight_alloys")
        ships.resources = 56
        ships.queue_ship(0, 2)
        ships.fund_project(ships.planet_at(0, 2).construction_queue[0])
        self.assertEqual(ships.resources, 0)
        self.assertEqual(ships.cancel_construction(0, 2, 0), "56 RES")

    def test_speed_applies_to_new_voyages_and_in_flight_save_keeps_departure_speed(self):
        game = new_game(seed=2408, with_ai=False)
        origin = game.systems[0]
        destination = place_near(game, 1, distance=7)
        game.ships = [Ship(1, "colony_ship", 0), Ship(2, "colony_ship", 0)]
        game.next_ship_id = 3
        original = game.send_ship(1, destination.id)
        discover(game, "ion_drives")
        discover(game, "fusion_drives")
        faster = game.send_ship(2, destination.id)
        self.assertLess(faster, original)
        self.assertEqual(game.ships[0].travel_total, original)
        self.assertEqual(game.ships[1].speed_bonus, 75)
        restored = GameState.from_dict(game.to_dict())
        for _ in range(original):
            self.assertEqual(game.advance_turn(), restored.advance_turn())
            self.assertEqual(game, restored)
        self.assertTrue(all(s.speed_bonus == 0 and not s.in_transit for s in game.ships))

    def test_hostile_worlds_and_starting_population_unlock_only_for_researching_empire(self):
        game = new_game(seed=2408)
        game.ships = [Ship(1, "colony_ship", 0), Ship(2, "colony_ship", 0)]
        game.next_ship_id = 3
        self.assertIn("Radiation Shields", game.colonize_error(0, 0))
        self.assertIn("Thermal Barriers", game.colonize_error(0, 1))
        discover(game, "radiation_shields")
        self.assertIsNone(game.colonize_error(0, 0))
        self.assertFalse(game.can_settle(game.planet_at(0, 0), RIVAL))
        discover(game, "thermal_barriers")
        discover(game, "colony_biospheres")
        discover(game, "colony_biogenesis")
        self.assertEqual(game.colonize(1, 0, 0).population, 4)
        self.assertEqual(game.colonize(2, 0, 1).population, 4)
        self.assertEqual(game.planet_at(0, 2).population, 8)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_habitat_population_trade_and_treaty_effects_use_real_outputs(self):
        game = new_game(seed=2408, race_id="aelari", rival_race_id="kharuun")
        earth = game.planet_at(0, 2)
        earth.buildings = ["trade_center"]
        earth.biome = "Desert"
        for identifier in ("habitat_shields", "symbiotic_farming", "ecology_networks", "trade_algorithms"):
            discover(game, identifier)
        self.assertEqual(game.planet_yields(earth), (6, 25, 0))  # 8 + trade 6+4 + habitat 2 + farming 2 + ecology 4 - upkeep 1
        discover(game, "cultural_exchange")
        self.assertEqual(game.diplomatic_yields(), (0, 0))
        game.diplomacy.trade_active = game.diplomacy.research_active = True
        self.assertEqual(game.diplomatic_yields(), (8, 7))
        self.assertEqual(game.diplomatic_yields(RIVAL), (6, 3))
        self.assertEqual(game.empire_rates, (35, 7))  # Colonial Administration adds another 2 CR.


class ResearchSaveTests(unittest.TestCase):
    def test_v6_migration_preserves_banks_orders_and_routes_and_spends_old_points(self):
        game = new_game(seed=2408)
        game.research, game.opponent.research = 123, 57
        game.queue_building(0, 2, "factory")
        game.planet_at(0, 2).advance_construction()
        game.ships = [Ship(1, "colony_ship", 0)]
        game.next_ship_id = 2
        place_near(game, 1)
        game.send_ship(1, 1)
        legacy_economy(game)
        with tempfile.TemporaryDirectory() as folder:
            game.ship_at(1).departure_pending = False  # Legacy course snapshot.
            storage = Storage(folder)
            path = storage.save(game)
            payload = json.loads(path.read_text())
            payload["version"] = 6
            data = payload["game"]
            data.pop("technology")
            data["opponent"].pop("technology")
            for system in data["systems"]:
                for planet in system["worlds"]:
                    for project in planet["construction_queue"]:
                        project.pop("paid_credits")
            for ship in data["ships"]:
                ship.pop("speed_bonus")
            path.write_text(json.dumps(payload))
            restored, _ = storage.load(path)
            self.assertEqual(restored, game)
            restored.choose_research("civil_engineering")
            self.assertEqual((restored.research, restored.technology.progress, restored.opponent.research), (0, 123, 57))
            self.assertEqual(json.loads(storage.save(restored).read_text())["version"], SAVE_VERSION)

    def test_invalid_locks_prerequisites_progress_and_snapshot_costs_are_rejected(self):
        game = new_game(seed=2408)
        invalid = [
            {"completed": ["civil_engineering", "automated_factories"], "active": None, "progress": 0},
            {"completed": ["civil_engineering", "civil_engineering"], "active": None, "progress": 0},
            {"completed": ["fusion_drives"], "active": None, "progress": 0},
            {"completed": [], "active": "missing", "progress": 0},
            {"completed": [], "active": [], "progress": 0},
            {"completed": [], "active": "ion_drives", "progress": 40},
            {"completed": [], "active": "ion_drives", "progress": True},
            {"completed": [], "active": "ion_drives", "progress": -1},
            {"completed": [], "active": None, "progress": 1},
        ]
        for owner in (PLAYER, RIVAL):
            for technology in invalid:
                data = game.to_dict()
                target = data if owner == PLAYER else data["opponent"]
                target["technology"] = dict(copy.deepcopy(technology), legacy_count=0, legacy_active=False)
                with self.subTest(owner=owner, technology=technology), self.assertRaises(SaveError):
                    GameState.from_dict(data)
        game.queue_building(0, 2, "factory")
        for payment in (True, -1, 46):
            data = game.to_dict()
            data["systems"][0]["worlds"][2]["construction_queue"][0]["paid_credits"] = payment
            with self.assertRaises(SaveError):
                GameState.from_dict(data)
        game.ships = [Ship(1, "colony_ship", 0)]
        game.next_ship_id = 2
        place_near(game, 1)
        game.send_ship(1, 1)
        for speed in (True, -1, 100, "25"):
            data = game.to_dict()
            data["ships"][0]["speed_bonus"] = speed
            with self.assertRaises(SaveError):
                GameState.from_dict(data)

    def test_active_projects_and_ai_choices_continue_identically_after_save(self):
        game = new_game(seed=2408, rival_race_id="aelari")
        game.planet_at(0, 2).buildings = ["research_lab"]
        game.choose_research("research_instruments")
        for _ in range(3):
            game.advance_turn()
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            restored, _ = storage.load(storage.save(game))
            for _ in range(100):
                if game.result is not None:
                    break
                self.assertEqual(game.advance_turn(), restored.advance_turn())
                self.assertEqual(game, restored)
            self.assertGreater(len(game.opponent.technology.completed), 0)
            self.assertEqual(game.technology.completed, ["research_instruments"])
            self.assertEqual(GameState.from_dict(game.to_dict()), game)


class ResearchScreenTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        self.folder = tempfile.TemporaryDirectory()
        self.app = App(self.folder.name, capture=True)
        self.app.game = new_game(seed=2408)
        self.app.game.selected_planet = 2
        self.app.go("galaxy")
        self.app.window = pg.display.set_mode((980, 900), pg.RESIZABLE)
        self.app.present()
        self.app.render()

    def tearDown(self):
        pg.quit()
        self.folder.cleanup()

    def key(self, key):
        self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=key, mod=0))
        self.app.render()

    def click(self, key):
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        self.assertTrue(button.enabled, key)
        x, y = button.rect.center
        viewport = self.app.viewport
        position = (round(viewport.x+x*viewport.w/1440), round(viewport.y+y*viewport.h/900))
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, pos=position, button=1))
            self.app.render()

    def test_navigation_branches_pause_and_other_overviews_preserve_game_selection(self):
        for origin in ("galaxy", "system", "planet", "colony", "shipyard", "empire", "fleets", "rival", "diplomacy"):
            with self.subTest(origin=origin):
                self.app.go(origin)
                before = self.app.game.to_dict()
                if origin == "planet":
                    self.key(pg.K_r)
                else:
                    self.click("open_research")
                self.assertEqual(self.app.screen, "research")
                for branch in BRANCHES:
                    self.click(f"research_branch_{branch}")
                self.key(pg.K_LEFT)
                self.key(pg.K_RIGHT)
                self.key(pg.K_ESCAPE)
                self.assertEqual(self.app.screen, origin)
                self.assertEqual(self.app.game.to_dict(), before)
        self.key(pg.K_r)
        for other in ("empire", "fleets", "diplomacy"):
            self.click(f"open_{other}")
            self.key(pg.K_ESCAPE)
            self.assertEqual(self.app.screen, "research")
        self.click("research_pause")
        self.click("settings")
        self.click("settings_done")
        self.click("resume")
        self.assertEqual(self.app.screen, "research")

    def test_immediate_selection_switching_completion_and_autosave_with_real_clicks(self):
        game = self.app.game
        progress = TECHNOLOGIES["civil_engineering"].cost-3
        game.research = progress
        game.planet_at(0, 2).buildings = ["research_lab"]
        self.click("open_research")
        self.click("research_choose_civil_engineering")
        self.assertIsNone(self.app.dialog)
        self.assertEqual(game.technology.progress, progress)
        self.assertTrue(next(b for b in self.app.buttons if b.key == "research_choose_automated_factories").enabled)
        self.click("research_choose_automated_factories")
        self.assertEqual(game.technology.progress, progress)
        self.click("research_choose_civil_engineering")
        self.assertEqual(game.technology.progress, progress)
        self.click("research_end_turn")
        self.assertIn("Discovered: Civil Engineering", self.app.notice)
        self.assertTrue(next(b for b in self.app.buttons if b.key == "research_choose_orbital_assembly").enabled)
        restored, _ = self.app.storage.load(self.app.storage.saves_dir/"autosave.json")
        self.assertEqual(restored, game)


if __name__ == "__main__":
    unittest.main()
