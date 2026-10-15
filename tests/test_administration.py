"""Administration's effects on real settlement, economy, turns and persistence."""
from copy import deepcopy
import math
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from orion import administration as admin, balance, economy, population, statistics
from orion.model import new_game, Ship, GameState, SaveError
from orion.research import gross_colony_yields
from orion.storage import Storage


def campaign(**kwargs):
    return new_game(seed=12, galaxy_size="Compact", random_starts=False, with_guardians=False,
                    with_tombs=False, with_black_holes=False, **kwargs)


def settle(game, sid, pid=0, ly=None, owner="player"):
    system = game.systems[sid]
    if ly is not None:
        capital = game.headquarters(owner)[0]
        system.x, system.y = capital.x+ly/140, capital.y
    planet = system.worlds[pid]
    planet.biome = "Terran"
    ship = Ship(game.next_ship_id, "colony_ship", sid, owner=owner)
    game.next_ship_id += 1
    game.ships.append(ship)
    game.colonize(ship.id, sid, pid, owner=owner)
    return planet


class AdministrationTests(unittest.TestCase):
    def setUp(self):
        previous = balance.active_profile()
        balance.activate(balance.default_profile())
        self.addCleanup(lambda: balance.activate(previous))
        self.game = campaign(with_ai=False)
        self.home = self.game.planet_at(0, 2)
        self.ids = [s.id for s in self.game.systems[1:] if s.worlds]

    def test_home_is_integrated_and_production_unchanged(self):
        self.assertEqual(self.game.strain_report(self.home).total, 0)
        self.assertEqual(self.game.planet_yields(self.home), (4, 8, 0))
        self.assertEqual(self.game.system_integration, {})

    def test_first_new_system_adds_eight_points_everywhere(self):
        colony = settle(self.game, self.ids[0], ly=7)
        self.assertEqual(self.game.strain_report(self.home).total, 8)
        report = self.game.strain_report(colony)
        self.assertAlmostEqual(report.total, 8)
        self.assertEqual(report.integration_remaining, 8)

    def test_additional_planet_counts_once_and_does_not_restart_timer(self):
        sid = next(s.id for s in self.game.systems[1:] if len(s.worlds) >= 2)
        first = settle(self.game, sid, ly=14)
        self.game.advance_turn()
        second = settle(self.game, sid, pid=1)
        a, b = self.game.strain_report(first), self.game.strain_report(second)
        self.assertEqual((a.systems, a.integration_remaining), (2, 7))
        self.assertEqual(a, b)
        self.assertEqual(self.game.system_integration["player"][str(sid)], 9)

    def test_planet_in_home_system_adds_nothing(self):
        colony = settle(self.game, 0)
        self.assertEqual(self.game.strain_report(colony).total, 0)
        self.assertEqual(self.game.system_integration, {})

    def test_distance_is_continuous_physical_and_local(self):
        colony = settle(self.game, self.ids[0], ly=10.5)
        self.assertAlmostEqual(self.game.strain_report(colony).distance, 9)
        self.assertAlmostEqual(self.game.strain_report(colony).total, 17)
        self.assertEqual(self.game.strain_report(self.home).distance, 0)
        self.assertEqual(self.game.strain_report(self.home).total, 8)
        self.game.technology.completed.append("lightweight_alloys")
        self.assertAlmostEqual(self.game.strain_report(colony).distance, 9)

    def test_distance_table_and_cap_apply_after_adding_components(self):
        colony = settle(self.game, self.ids[0], ly=7)
        system = self.game.systems[self.ids[0]]
        for ly, distance in ((0, 0), (7, 0), (14, 18), (21, 36), (28, 54), (35, 72), (42, 90)):
            system.x = self.game.systems[0].x+ly/140
            report = self.game.strain_report(colony)
            self.assertAlmostEqual(report.distance, distance)
            self.assertAlmostEqual(report.total, min(90, 8+distance))

    def test_agreed_six_system_example(self):
        colonies = [settle(self.game, sid, ly=7+i*3) for i, sid in enumerate(self.ids[:5])]
        self.game.system_integration["player"] = {str(sid): 9 for sid in self.ids[2:5]}
        system = self.game.systems[self.ids[4]]
        system.x = self.game.systems[0].x+28/140
        report = self.game.strain_report(colonies[-1])
        self.assertEqual((report.systems, report.integrating, report.empire, report.integration), (6, 3, 20, 12))
        self.assertAlmostEqual(report.total, 86)
        self.assertAlmostEqual(report.loss("industry"), 43)
        self.assertAlmostEqual(report.loss("food"), 21.5)
        self.assertEqual(self.game.strain_report(self.home).total, 32)

    def test_exactly_eight_production_turns_then_timer_expires(self):
        colony = settle(self.game, self.ids[0], ly=7)
        for remaining in range(8, 0, -1):
            self.assertEqual(self.game.strain_report(colony).integration_remaining, remaining)
            expected = self.game.empire_rates
            result = self.game.advance_turn()
            self.assertEqual((result.income, result.research), expected)
        self.assertEqual(self.game.turn, 9)
        self.assertEqual(self.game.system_integration, {})
        self.assertAlmostEqual(self.game.strain_report(colony).total, 4)

    def test_outposts_do_not_add_strain_or_reduce_capital_distance(self):
        from orion import outposts
        colony = settle(self.game, self.ids[0], ly=28)
        report = self.game.strain_report(colony)
        sid = self.ids[1]
        ship = Ship(self.game.next_ship_id, "outpost_ship", sid)
        self.game.next_ship_id += 1
        self.game.ships.append(ship)
        outposts.deploy(self.game, ship.id, sid, 0)
        self.assertEqual(self.game.strain_report(colony), report)
        self.assertEqual(self.game.strain_report(self.game.planet_at(sid, 0)).total, 0)

    def test_all_outputs_before_consumption_and_upkeep(self):
        colony = settle(self.game, self.ids[0], ly=14)
        colony.population = 16
        colony.farmers, colony.scientists, colony.miners = 3, 3, 4
        colony.buildings = ["factory", "research_lab", "mine"]
        base = dict(self.game.bonuses_for())
        raw = gross_colony_yields(colony, base)
        raw_food = population.report(colony, base).produced
        raw_mining = economy.mining_output(colony, base)
        upkeep = self.game.planet_maintenance(colony)
        industry, credits, research = self.game.planet_yields(colony)
        self.assertEqual(industry, math.floor(raw[0]*.87+1e-9))
        self.assertEqual(credits, math.floor(raw[1]*.74+1e-9)-upkeep)
        self.assertEqual(research, math.floor(raw[2]*.74+1e-9))
        self.assertEqual(self.game.population_report(colony).produced, math.floor(raw_food*.935+1e-9))
        self.assertEqual(self.game.population_report(colony).consumed, 16)
        self.assertEqual(self.game.planet_resources(colony), math.floor(raw_mining*.87+1e-9))
        self.assertEqual(self.game.planet_energy(colony), economy.energy_report(colony, base))

    def test_farmer_assignment_accounts_for_corruption(self):
        colony = settle(self.game, self.ids[0], ly=35)
        colony.population = 16
        colony.size = "Medium"
        bonuses = self.game.bonuses_for()
        farmers = population.farmers_needed(colony, bonuses)
        colony.farmers = farmers
        self.assertGreaterEqual(self.game.population_report(colony).produced, 16)
        colony.farmers -= 1
        self.assertLess(self.game.population_report(colony).produced, 16)

    def test_trade_goods_payout_is_shared_by_simulation_and_ui(self):
        colony = settle(self.game, self.ids[0], ly=14)
        colony.population = 24
        colony.buildings = ["factory"]
        initial = self.game.planet_yields(colony)
        expected = math.floor(math.floor(initial[0]*.30)*.74+1e-9)
        colony.trade_goods = True
        self.assertEqual(self.game.trade_goods_income(colony), expected)
        self.assertEqual(self.game.planet_yields(colony)[1]-initial[1], expected)

    def test_statistics_match_effective_live_outputs(self):
        settle(self.game, self.ids[0], ly=28)
        row = statistics.sample(self.game, "player")
        worlds = [p for s in self.game.systems for p in s.worlds if p.owner == "player"]
        self.assertEqual(row[2], sum(self.game.planet_yields(p)[0] for p in worlds))
        self.assertEqual(row[3], sum(self.game.population_report(p).produced for p in worlds))
        self.assertEqual(row[4], self.game.resource_rate())
        self.assertEqual(row[6], self.game.empire_rates[0])

    def test_forecast_crosses_integration_expiry_and_matches_real_completion(self):
        colony = settle(self.game, self.ids[0], ly=14)
        colony.population, colony.farmers, colony.miners = 16, 6, 4
        colony.size = "Medium"
        self.game.resources = 1000
        self.game.queue_ship(self.ids[0], 0, "colony_ship")
        eta = self.game.queue_estimates(colony)[0]
        self.assertGreater(eta, 8)
        for _ in range(eta-1):
            self.game.advance_turn()
            self.assertTrue(colony.construction_queue)
        self.game.advance_turn()
        self.assertFalse(colony.construction_queue)
        self.assertTrue(any(s.kind == "colony_ship" and s.system_id == self.ids[0] for s in self.game.ships))

    def test_capital_relocation_and_lost_system_remove_their_effects(self):
        from orion.raiding import abandon
        colony = settle(self.game, self.ids[0], ly=28)
        abandon(self.home)
        self.game.eliminate_defeated()
        report = self.game.strain_report(colony)
        self.assertEqual((report.systems, report.empire, report.distance), (1, 0, 0))
        abandon(colony)
        self.game.eliminate_defeated()
        self.assertEqual(self.game.system_integration, {})

    def test_conquest_starts_integration_for_attacker_only(self):
        game = campaign()
        sid, pid = game.opponent.home_system, game.opponent.home_planet
        game.ships = [Ship(i, "troop_transport", sid) for i in range(1, 7)]
        game.next_ship_id = 7
        self.assertTrue(game.invade(sid, pid).captured)
        self.assertEqual(game.system_integration, {"player": {str(sid): 9}})

    def test_new_remnant_capital_is_exempt_but_second_awakening_integrates(self):
        from orion import tomb_worlds
        game = self.game
        first, second = self.ids[:2]
        tomb1 = tomb_worlds.TombWorld(first, 0)
        tomb2 = tomb_worlds.TombWorld(second, 0)
        game.tomb_worlds = [tomb1, tomb2]
        tomb_worlds.awaken(game, tomb1)
        owner = game.planet_at(first, 0).owner
        self.assertNotIn(owner, game.system_integration)
        tomb_worlds.awaken(game, tomb2)
        self.assertEqual(game.system_integration[owner], {str(second): 9})

    def test_rival_uses_own_capital_and_has_independent_integration(self):
        game = campaign()
        sid = next(sid for sid in self.ids if sid != game.opponent.home_system)
        colony = settle(game, sid, owner="rival", ly=14)
        self.assertAlmostEqual(game.strain_report(colony).total, 26)
        self.assertEqual(game.strain_report(game.planet_at(0, 2)).total, 0)

    def test_nexus_has_no_food_penalty_and_assembly_uses_reduced_industry(self):
        game = campaign(with_ai=False, race_id="nexus")
        colony = settle(game, self.ids[0], ly=28)
        colony.population = 8
        food = game.population_report(colony)
        self.assertEqual((food.produced, food.consumed, colony.farmers), (0, 0, 0))
        gross = gross_colony_yields(colony, game.bonuses_for())
        self.assertEqual(food.assembly_industry+game.planet_yields(colony)[0], gross[0])

    def test_save_roundtrip_retains_remaining_turns(self):
        colony = settle(self.game, self.ids[0], ly=14)
        self.game.advance_turn()
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            restored, metadata = storage.load(storage.save(self.game))
        self.assertEqual(metadata["version"], 46)
        self.assertEqual(restored.system_integration, self.game.system_integration)
        self.assertEqual(restored.strain_report(restored.planet_at(self.ids[0], 0)), self.game.strain_report(colony))

    def test_old_save_has_no_invented_integration_and_preserves_history(self):
        settle(self.game, self.ids[0], ly=14)
        payload = self.game.to_dict()
        del payload["system_integration"]
        restored = GameState.from_dict(payload, version=40)
        self.assertEqual(restored.system_integration, {})
        self.assertEqual(restored.statistics, self.game.statistics)
        self.assertAlmostEqual(restored.strain_report(restored.planet_at(self.ids[0], 0)).total, 22)

    def test_invalid_timers_rejected(self):
        settle(self.game, self.ids[0], ly=14)
        valid = self.game.to_dict()
        for record in ({"unknown": {}}, {"player": {"01": 9}}, {"player": {str(self.ids[1]): 9}},
                       {"player": {str(self.ids[0]): True}}, {"player": {str(self.ids[0]): 100}},
                       {"player": {str(self.ids[0]): -1}}, {"player": []}):
            with self.subTest(record=record):
                payload = deepcopy(valid)
                payload["system_integration"] = record
                with self.assertRaises(SaveError):
                    GameState.from_dict(payload)

    def test_balance_upgrade_and_editable_controls(self):
        from orion.balance_document import BalanceDocument
        old = balance.default_profile()
        old["version"] = 5
        del old["data"]["rules"]["administration"]
        old["data"]["ships"]["colony_ship"]["resource_cost"] = 900
        upgraded = balance.upgrade_profile(old)
        self.assertEqual(balance.validate(upgraded), [])
        self.assertEqual(upgraded["data"]["ships"]["colony_ship"]["resource_cost"], 900)
        self.assertEqual(upgraded["data"]["rules"]["administration"]["DISTANCE_UNIT_LY"], 7)
        with tempfile.TemporaryDirectory() as folder:
            document = BalanceDocument(Path(folder)/"balance.json")
            document.set("rules", "administration", ("DISTANCE_UNIT_LY",), 10.5)
            document.save()
            with balance.using_profile(document.profile):
                colony = settle(self.game, self.ids[0], ly=21)
                self.assertAlmostEqual(self.game.strain_report(colony).distance, 18)
        bad = balance.default_profile()
        bad["data"]["rules"]["administration"]["DISTANCE_UNIT_LY"] = 0
        self.assertTrue(balance.validate(bad))

    def test_settlement_preview_includes_global_and_local_costs(self):
        sid = self.ids[0]
        self.game.systems[sid].x = self.game.systems[0].x+14/140
        self.game.systems[sid].y = self.game.systems[0].y
        self.assertIn("+4 points, plus +4 for 8 turns", admin.settlement_preview(self.game, sid))
        self.assertIn("26.0%", admin.settlement_preview(self.game, sid))
        self.assertIn("no additional", admin.settlement_preview(self.game, 0))

    def test_ai_consolidates_while_new_system_integrates(self):
        from orion.ai import run_ai
        from orion.exploration import refresh
        game = campaign(fog_of_war=False)
        sid = next(sid for sid in self.ids if sid != game.opponent.home_system)
        settle(game, sid, owner="rival", ly=7)
        home_sid = game.opponent.home_system
        ship = Ship(game.next_ship_id, "colony_ship", home_sid, owner="rival")
        game.next_ship_id += 1
        game.ships.append(ship)
        refresh(game)
        run_ai(game)
        self.assertEqual(len(game.colony_systems("rival")), 2)
        if ship in game.ships and ship.has_course:
            self.assertIn(ship.destination, {sid, home_sid})


class AdministrationInterfaceTests(unittest.TestCase):
    def setUp(self):
        import pygame as pg
        from orion.app import App
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(folder.name), capture=True)
        self.addCleanup(self.app.audio.close)
        self.game = self.app.game = campaign(fog_of_war=False)

    def test_settlement_confirmation_is_read_only_until_accepted(self):
        game, app = self.game, self.app
        system = next(s for s in game.systems[1:] if s.worlds and s.id != game.opponent.home_system)
        system.x, system.y = game.systems[0].x+14/140, game.systems[0].y
        system.worlds[0].biome = "Terran"
        ship = Ship(game.next_ship_id, "colony_ship", system.id)
        game.next_ship_id += 1
        game.ships.append(ship)
        game.selected_system = system.id
        app.open_planet(0)
        before = game.to_dict()
        app.colonize_request()
        self.assertIn("+4 points, plus +4 for 8 turns", app.dialog["body"])
        self.assertIn("26.0%", app.dialog["body"])
        app.render()
        app.cancel_dialog()
        self.assertEqual(game.to_dict(), before)
        app.colonize_request()
        app.accept_dialog()
        self.assertEqual(game.system_integration, {"player": {str(system.id): 9}})
        self.assertEqual(app.screen, "planet")
        app.render()

    def test_breakdown_is_private_and_keeps_building_controls_clear(self):
        import pygame as pg
        from unittest.mock import patch
        from orion.planet_view import text
        from orion.buildings import BUILDINGS
        game, app = self.game, self.app
        home = game.planet_at(0, 2)
        home.size = "Huge"
        app.open_planet(2)
        layouts = (["factory", "research_lab", "mine", "trade_center", "hydroponic_farm",
                    "barracks", "fortifications", "solar_array", "fusion_plant", "space_hub"],
                   list(BUILDINGS)[:home.building_capacity])
        for buildings in layouts:
            home.buildings = buildings
            with patch("orion.planet_view.text", wraps=text) as drawn:
                app.render()
                self.assertTrue(any("ADMINISTRATION" in str(call.args[1]) for call in drawn.call_args_list))
            footer = pg.Rect(40, 728, 900, 100)
            buttons = [b for b in app.buttons if b.key.startswith("surface_")]
            for i, button in enumerate(buttons):
                self.assertFalse(button.rect.colliderect(footer), button.key)
                for other in buttons[i+1:]:
                    self.assertFalse(button.rect.colliderect(other.rect), (button.key, other.key))
        game.selected_system = game.opponent.home_system
        app.open_planet(game.opponent.home_planet)
        with patch.object(game, "strain_report", side_effect=AssertionError("Private enemy breakdown")):
            app.render()


if __name__ == "__main__":
    unittest.main()
