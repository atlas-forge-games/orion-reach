"""Construction economy, turn timing, and compatibility of persistent colonies."""

import json
import tempfile
import unittest

from orion.buildings import BUILDING_SLOTS
from orion.model import GameState, RuleError, SaveError, new_game
from functools import partial

# Keep the original single-empire regression fixtures isolated from AI turns.
new_game = partial(new_game, with_ai=False, fog_of_war=False)
from orion.storage import SAVE_VERSION, Storage


class ColonyRulesTests(unittest.TestCase):
    def setUp(self):
        self.game = new_game(seed=2408)
        self.earth = self.game.systems[0].worlds[2]

    def test_size_caps_include_completed_and_reserved_slots(self):
        expected = {"Tiny": 4, "Small": 6, "Medium": 8, "Large": 10, "Huge": 12}
        self.assertEqual(BUILDING_SLOTS, expected)
        for size, capacity in expected.items():
            with self.subTest(size=size):
                game = new_game(seed=2408)
                planet = game.systems[0].worlds[2]
                planet.size = size
                game.credits = 1000
                for _ in range(capacity):
                    game.queue_building(0, 2, "factory")
                for _ in range(4):
                    game.advance_turn()
                self.assertEqual(len(planet.buildings), 1)
                self.assertEqual(planet.free_slots, 0)
                before = game.to_dict()
                with self.assertRaisesRegex(RuleError, "slots"):
                    game.queue_building(0, 2, "mine")
                self.assertEqual(game.to_dict(), before)
                game.demolish_building(0, 2, 0)
                game.queue_building(0, 2, "mine")
                self.assertEqual(planet.used_slots, capacity)

    def test_rejected_orders_never_spend_credits_or_reserve_slots(self):
        for system, planet, building in ((0, 2, "unknown"), (0, 3, "factory"),
                                        (-1, 2, "factory"), (0, -1, "factory"),
                                        (0, True, "factory"), (0, 2, [])):
            with self.subTest(order=(system, planet, building)):
                before = self.game.to_dict()
                with self.assertRaises(RuleError):
                    self.game.queue_building(system, planet, building)
                self.assertEqual(self.game.to_dict(), before)
        self.game.credits = 44
        before = self.game.to_dict()
        with self.assertRaisesRegex(RuleError, "credits"):
            self.game.queue_building(0, 2, "factory")
        self.assertEqual(self.game.to_dict(), before)

    def test_forecast_overflow_and_factory_output_start_next_turn(self):
        for building in ("factory", "factory", "mine"):
            self.game.queue_building(0, 2, building)
        before = self.game.to_dict()
        self.assertEqual(self.earth.queue_estimates(), [4, 7, 8])
        self.assertEqual(self.earth.queue_estimates("research_lab"), [4, 7, 8, 10])
        self.assertEqual(self.game.to_dict(), before)
        for _ in range(4):
            self.game.advance_turn()
        self.assertEqual(self.earth.buildings, ["factory"])
        self.assertEqual(self.earth.construction_queue[0].progress, 0)
        for _ in range(2):
            self.game.advance_turn()
        self.assertEqual(self.earth.construction_queue[0].progress, 20)
        self.game.advance_turn()
        self.assertEqual(self.earth.buildings, ["factory", "factory"])
        self.assertEqual(self.earth.construction_queue[0].progress, 6)
        report = self.game.advance_turn()
        self.assertEqual(self.earth.buildings, ["factory", "factory", "mine"])
        self.assertEqual(self.earth.construction_queue, [])
        self.assertEqual(report.income, 8)
        self.assertEqual(self.earth.yields_per_turn, (16, 9, 0))
        self.assertEqual(self.game.advance_turn().income, 9)

    def test_cancel_refunds_unspent_work_and_releases_the_slot(self):
        self.game.queue_building(0, 2, "factory")
        self.game.queue_building(0, 2, "trade_center")
        self.assertEqual(self.game.cancel_construction(0, 2, 1), 40)
        self.game.advance_turn()
        self.assertEqual(self.earth.construction_queue[0].refund, 33)
        self.assertEqual(self.game.cancel_construction(0, 2, 0), 33)
        self.assertEqual(self.game.credits, 116)
        self.assertEqual(self.earth.free_slots, 8)
        before = self.game.to_dict()
        with self.assertRaises(RuleError):
            self.game.cancel_construction(0, 2, 0)
        self.assertEqual(self.game.to_dict(), before)

    def test_demolition_stops_output_without_refunding_cost(self):
        self.game.queue_building(0, 2, "factory")
        for _ in range(4):
            self.game.advance_turn()
        self.game.queue_building(0, 2, "mine")
        credits = self.game.credits
        self.assertEqual(self.game.demolish_building(0, 2, 0), "factory")
        self.assertEqual(self.game.credits, credits)
        self.game.advance_turn()
        self.assertEqual(self.earth.construction_queue[0].progress, 6)
        self.assertEqual(self.earth.used_slots, 1)
        with self.assertRaises(RuleError):
            self.game.demolish_building(0, 2, 0)

    def test_minerals_only_scale_mining_industry(self):
        self.earth.buildings = ["factory", "mine", "trade_center", "research_lab"]
        for richness, expected_industry in (("Poor", 11), ("Average", 12), ("Rich", 13)):
            self.earth.richness = richness
            self.assertEqual(self.earth.yields_per_turn, (expected_industry, 13, 4))
        self.assertEqual(self.game.empire_rates, (13, 4))
        self.assertEqual(self.game.systems[0].worlds[3].yields_per_turn, (0, 0, 0))

    def test_income_and_research_begin_after_completion(self):
        self.game.queue_building(0, 2, "trade_center")
        self.game.queue_building(0, 2, "research_lab")
        for _ in range(4):
            report = self.game.advance_turn()
            self.assertEqual((report.income, report.research), (8, 0))
        self.assertEqual(self.earth.buildings, ["trade_center"])
        for _ in range(5):
            report = self.game.advance_turn()
            self.assertEqual((report.income, report.research), (12, 0))
        self.assertEqual(self.earth.buildings, ["trade_center", "research_lab"])
        report = self.game.advance_turn()
        self.assertEqual((report.income, report.research), (12, 4))
        self.assertEqual(self.game.research, 4)

    def test_partial_queue_and_research_survive_save_and_continue_identically(self):
        self.game.queue_building(0, 2, "research_lab")
        for _ in range(5):
            self.game.advance_turn()
        self.game.queue_building(0, 2, "factory")
        self.game.advance_turn()
        self.game.selected_planet = 2
        self.assertEqual(self.game.research, 4)
        self.assertEqual(self.earth.construction_queue[0].progress, 6)
        with tempfile.TemporaryDirectory() as folder:
            store = Storage(folder)
            restored, _ = store.load(store.save(self.game))
        self.assertEqual(restored, self.game)
        for _ in range(5):
            self.assertEqual(restored.advance_turn(), self.game.advance_turn())
            self.assertEqual(restored, self.game)

    def test_v2_migration_keeps_planets_and_does_not_rewrite_source(self):
        self.game.selected_planet = 2
        self.earth.population = 9
        self.earth.richness = "Rich"
        with tempfile.TemporaryDirectory() as folder:
            store = Storage(folder)
            path = store.save(self.game)
            payload = json.loads(path.read_text())
            payload["version"] = 2
            payload["game"].pop("research")
            for system in payload["game"]["systems"]:
                for planet in system["worlds"]:
                    planet.pop("buildings")
                    planet.pop("construction_queue")
            path.write_text(json.dumps(payload))
            before = path.read_bytes()
            restored, _ = store.load(path)
            self.assertEqual(restored, self.game)
            self.assertEqual(path.read_bytes(), before)
            new_path = store.save(restored)
            self.assertEqual(json.loads(new_path.read_text())["version"], SAVE_VERSION)

    def test_malformed_colony_saves_are_rejected(self):
        invalid_planets = [
            {"buildings": ["unknown"]},
            {"buildings": [None]},
            {"buildings": "factory"},
            {"buildings": ["factory"]*9},
            {"buildings": ["factory"]*8, "construction_queue": [{"item_id": "mine", "progress": 0}]},
            {"construction_queue": {}},
            {"construction_queue": [{"item_id": "factory", "progress": -1}]},
            {"construction_queue": [{"item_id": "factory", "progress": 24}]},
            {"construction_queue": [{"item_id": "factory", "progress": True}]},
            {"construction_queue": [{"item_id": "unknown", "progress": 0}]},
            {"construction_queue": [{"item_id": "factory", "progress": 0}, {"item_id": "mine", "progress": 1}]},
            {"colonized": False, "population": 0, "buildings": ["mine"]},
        ]
        for invalid in invalid_planets:
            with self.subTest(invalid=invalid):
                data = self.game.to_dict()
                data["systems"][0]["worlds"][2].update(invalid)
                with self.assertRaises(SaveError):
                    GameState.from_dict(data)
        for value in (-1, True, "4"):
            data = self.game.to_dict()
            data["research"] = value
            with self.assertRaises(SaveError):
                GameState.from_dict(data)


if __name__ == "__main__":
    unittest.main()
