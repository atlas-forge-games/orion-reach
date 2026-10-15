from scenarios import legacy_research_payload
"""Workforce productivity, recurring costs, debt, AI budgets and save continuity."""

import json
from pathlib import Path
import tempfile
import unittest

from orion import ai, raiding
from orion.empire import summarize_empire
from orion.model import ConstructionProject, GameState, RuleError, SaveError, Ship
from orion.population import farmer_output, farmers_needed
from orion.research import gross_colony_yields
from orion.storage import Storage
from scenarios import fixed_start_game


def scenario(**kwargs):
    kwargs.setdefault("with_ai", False)
    kwargs.setdefault("fog_of_war", False)
    kwargs.setdefault("with_guardians", False)
    return fixed_start_game(seed=2408, **kwargs)


class BuildingEconomyTests(unittest.TestCase):
    def test_reassigning_people_moves_building_productivity_between_roles(self):
        game = scenario()
        planet = game.planet_at(0, 2)
        planet.buildings = ["factory", "research_lab", "hydroponic_farm"]
        self.assertEqual((game.planet_yields(planet), game.population_report(planet).produced), ((16, 3, 4), 16))
        game.move_worker(0, 2, "workers", "scientists")
        self.assertEqual(game.planet_yields(planet), (14, 3, 7))
        game.move_worker(0, 2, "workers", "farmers")
        self.assertEqual((game.planet_yields(planet), game.population_report(planet).produced), ((12, 3, 7), 19))

    def test_buildings_keep_their_base_output_without_relevant_staff(self):
        game = scenario()
        planet = game.planet_at(0, 2)
        planet.buildings = ["factory", "mine", "research_lab", "hydroponic_farm"]
        game.set_workforce(0, 2, 0, 8)
        # Minimum one construction industry, plus the two buildings' fixed output.
        self.assertEqual(game.planet_yields(planet), (5, 2, 28))
        self.assertEqual(game.population_report(planet).produced, 10)
        game.set_workforce(0, 2, 8, 0)
        self.assertEqual(game.planet_yields(planet)[2], 4)

    def test_mines_scale_both_base_and_worker_output_and_round_after_stacking(self):
        game = scenario()
        planet = game.planet_at(0, 2)
        planet.population, planet.farmers = 1, 0
        planet.buildings = ["mine", "mine"]
        planet.miners = 1
        for richness, resources in (("Poor", 6), ("Average", 10), ("Rich", 14), ("Ultra-rich", 26)):
            planet.richness = richness
            self.assertEqual(game.planet_resources(planet), resources)
            self.assertEqual(game.planet_yields(planet), (1, -1, 0))
        planet.richness, planet.buildings = "Average", ["trade_center", "trade_center"]
        # Two half-credit population bonuses sum to one before rounding.
        self.assertEqual(game.planet_yields(planet)[1], 8)

    def test_trade_and_workforce_bonuses_include_slaves_on_the_same_terms(self):
        game = scenario(race_id="varkesh")
        planet = game.planet_at(0, 2)
        planet.slaves, planet.scientists = 10, 3
        planet.buildings = ["factory", "mine", "trade_center", "research_lab", "hydroponic_farm"]
        self.assertEqual(game.planet_yields(planet), (30, 24, 10))
        self.assertEqual((planet.maintenance_per_turn, farmer_output(planet)), (7, 3))

    def test_farming_assignments_include_all_completed_farm_bonuses(self):
        game = scenario()
        planet = game.planet_at(0, 2)
        planet.population, planet.biome = 16, "Desert"
        planet.buildings = ["hydroponic_farm", "hydroponic_farm"]
        self.assertEqual((farmer_output(planet), farmers_needed(planet, game.bonuses_for())), (4, 2))
        game.set_workforce(0, 2, 2, 0)
        self.assertEqual(game.population_report(planet).balance, 0)
        game.demolish_building(0, 2, 0)
        self.assertEqual(farmers_needed(planet, game.bonuses_for()), 4)

    def test_upkeep_follows_completed_buildings_not_queues_and_demolition_stops_it(self):
        game = scenario()
        planet = game.planet_at(0, 2)
        game.queue_building(0, 2, "factory")
        game.queue_building(0, 2, "research_lab")
        planet.construction_queue[0].progress = 18
        self.assertEqual(planet.maintenance_per_turn, 0)
        self.assertEqual(game.advance_turn().income, 8)
        self.assertEqual(planet.maintenance_per_turn, 2)
        self.assertEqual(game.advance_turn().income, 6)
        game.demolish_building(0, 2, 0)
        game.cancel_construction(0, 2, 0)
        self.assertEqual(game.advance_turn().income, 8)

    def test_racial_modifiers_apply_to_output_before_fixed_maintenance(self):
        game = scenario(race_id="concord")
        planet = game.planet_at(0, 2)
        planet.population, planet.buildings = 16, ["research_lab"]*5
        self.assertEqual(gross_colony_yields(planet, game.bonuses_for())[1], 14)
        self.assertEqual((planet.maintenance_per_turn, game.planet_yields(planet)[1]), (10, 4))
        planet.ascension_gate = True
        self.assertEqual((planet.maintenance_per_turn, game.planet_yields(planet)[1]), (15, -1))

    def test_nexus_assembly_uses_improved_industry_and_foodless_farms_still_cost_upkeep(self):
        game = scenario(race_id="nexus")
        planet = game.planet_at(0, 2)
        planet.buildings = ["factory"]
        self.assertEqual(gross_colony_yields(planet, game.bonuses_for())[0], 25)
        self.assertEqual((game.population_report(planet).assembly_industry, game.planet_yields(planet)[0]), (5, 20))
        planet.buildings.append("hydroponic_farm")
        self.assertEqual((game.population_report(planet).produced, game.planet_yields(planet)[1]), (0, 5))

    def test_deficits_create_debt_and_surpluses_repay_it_without_stopping_paid_projects(self):
        game = scenario()
        planet = game.planet_at(0, 2)
        planet.population, planet.farmers, planet.scientists = 1, 0, 1
        planet.buildings = ["research_lab"]*8
        planet.construction_queue = [ConstructionProject("scout", progress=11)]
        game.credits = 0
        report = game.advance_turn()
        self.assertEqual((report.income, game.credits), (-15, -15))
        self.assertTrue(any("debt" in message for message in report.alerts))
        self.assertTrue(any(ship.kind == "scout" for ship in game.ships))
        game.queue_ship(0, 2, "scout")  # Debt does not prevent resource-funded construction.
        with self.assertRaises(RuleError):
            game.buy_construction(0, 2)
        for _ in range(8):
            game.demolish_building(0, 2, 0)
        self.assertEqual(game.advance_turn().income, 1)
        self.assertEqual(game.credits, -14)
        self.assertEqual(game, GameState.from_dict(game.to_dict()))

    def test_budget_report_reconciles_gross_income_maintenance_and_treaties(self):
        game = scenario(with_ai=True)
        game.planet_at(0, 2).buildings = ["factory", "research_lab", "trade_center"]
        game.diplomacy.trade_active = True
        summary = summarize_empire(game)
        trade = game.diplomatic_yields()[0]
        self.assertEqual((summary.gross_income, summary.maintenance, summary.income), (16+trade, 5, 11+trade))
        self.assertEqual(game.empire_rates[0], summary.income)
        before = game.credits
        self.assertEqual(game.advance_turn().income, summary.income)
        self.assertEqual(game.credits, before+summary.income)

    def test_raids_cannot_steal_a_negative_treasury(self):
        game = scenario(with_ai=True, race_id="varkesh")
        game.opponent.credits = -70
        sid, pid = game.opponent.home_system, game.opponent.home_planet
        game.ships = [Ship(1, "troop_transport", sid), Ship(2, "troop_transport", sid)]
        game.next_ship_id = 3
        before = game.credits
        report = game.invade(sid, pid)
        self.assertEqual((report.credits_stolen, game.credits, game.opponent.credits), (0, before, -70))
        self.assertEqual(game, GameState.from_dict(game.to_dict()))

    def test_debt_still_allows_free_trade_negotiation_to_restore_income(self):
        game = scenario(with_ai=True)
        game.credits = -15
        game.diplomacy.relations = 100
        self.assertIsNone(game.diplomacy_error("trade"))
        game.diplomacy_action("trade")
        self.assertTrue(game.diplomacy.trade_active)
        self.assertEqual(game.credits, -15)
        self.assertEqual(game.empire_rates[0], 8+game.diplomatic_yields()[0])
        self.assertIsNotNone(game.diplomacy_error("gift"))

    def test_ai_accounts_for_paid_queues_and_recovers_an_insolvent_colony(self):
        game = scenario(with_ai=True)
        system, planet = game.headquarters("rival")
        planet.construction_queue = [ConstructionProject("research_lab") for _ in range(3)]
        self.assertEqual(ai.projected_income(game, "rival"), 2)
        self.assertTrue(ai.queue_building(game, system, planet, "factory", "rival"))
        self.assertEqual(planet.construction_queue[-1].item_id, "solar_array")
        planet.construction_queue.clear()
        planet.buildings = ["research_lab"]*8
        game.opponent.credits = -5
        for _ in range(30):
            game.advance_turn()
            if game.empire_rates_for("rival")[0] > 0:
                break
        self.assertGreater(game.empire_rates_for("rival")[0], 0)
        self.assertGreaterEqual(game.population_report(planet).balance, 0)
        self.assertTrue(any(b in ("solar_array", "fusion_plant") for b in planet.buildings))
        self.assertEqual(game, GameState.from_dict(game.to_dict()))

    def test_debt_save_roundtrip_and_old_versions_still_reject_negative_banks(self):
        game = scenario(with_ai=True)
        game.credits, game.opponent.credits = -15, -4
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            path = storage.save(game)
            original = path.read_bytes()
            self.assertEqual(json.loads(original)["version"], 46)
            self.assertEqual(storage.load(path)[0], game)
            self.assertEqual(path.read_bytes(), original)
        with self.assertRaises(SaveError):
            GameState.from_dict(legacy_research_payload(game.to_dict()), version=23)
        for value in (-1_000_000_001, True, -.5):
            data = game.to_dict()
            data["credits"] = value
            with self.assertRaises(SaveError):
                GameState.from_dict(data)


if __name__ == "__main__":
    unittest.main()
