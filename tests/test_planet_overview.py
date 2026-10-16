from scenarios import legacy_research_payload
from scenarios import legacy_economy
from scenarios import finish_building_next_turn
"""Workforce decisions, buying/prioritizing projects, migration and real UI flows."""

import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame as pg

from orion.exploration import refresh
from orion.model import GameState, PLAYER, RIVAL, RuleError, SaveError, Ship
from scenarios import empty_fleet_game as new_game
from orion.population import WORKER_ROLES
from orion.storage import Storage


class WorkforceTests(unittest.TestCase):
    def setUp(self):
        self.game = new_game(seed=2408, with_ai=False)
        self.earth = self.game.planet_at(0, 2)

    def test_one_job_per_billion_and_moves_change_real_yields_immediately(self):
        self.assertEqual((self.earth.farmers, self.earth.workers, self.earth.scientists), (2, 6, 0))
        self.assertEqual(self.game.planet_yields(self.earth), (6, 8, 0))
        self.assertEqual(self.game.population_report(self.earth).produced, 10)
        self.game.move_worker(0, 2, "workers", "scientists")
        self.assertEqual(self.game.planet_yields(self.earth), (5, 8, 2))
        self.assertEqual(self.game.credits, 120)
        result = self.game.advance_turn()
        self.assertEqual((result.income, result.research, self.game.research), (8, 2, 2))
        self.game.move_worker(0, 2, "farmers", "scientists")
        self.assertEqual(self.game.population_report(self.earth).balance, 0)
        self.assertEqual(self.game.planet_yields(self.earth), (5, 8, 4))
        self.assertEqual(sum(getattr(self.earth, role) for role in WORKER_ROLES), 8)

    def test_all_scientists_keep_minimum_industry_but_pause_growth_for_food(self):
        self.game.set_workforce(0, 2, 0, 8)
        self.assertEqual(self.game.planet_yields(self.earth), (1, 8, 16))
        self.assertEqual(self.game.population_report(self.earth).balance, -2)
        self.game.queue_building(0, 2, "hydroponic_farm")
        self.game.advance_turn()
        self.assertEqual((self.earth.population, self.earth.growth_progress), (8, 0))
        self.assertEqual(self.earth.construction_queue[0].progress, 1)

    def test_invalid_moves_and_allocation_fail_without_changing_anything(self):
        actions = [lambda: self.game.set_workforce(0, 2, 5, 4),
                   lambda: self.game.set_workforce(0, 2, True, 0),
                   lambda: self.game.set_workforce(0, 2, -1, 0),
                   lambda: self.game.set_workforce(0, 2, 1.5, 0),
                   lambda: self.game.move_worker(0, 2, "scientists", "workers"),
                   lambda: self.game.move_worker(0, 2, "workers", "workers"),
                   lambda: self.game.move_worker(0, 2, "workers", "unknown"),
                   lambda: self.game.move_worker(0, 3, "workers", "farmers")]
        for action in actions:
            before = self.game.to_dict()
            with self.assertRaises(RuleError):
                action()
            self.assertEqual(self.game.to_dict(), before)

    def test_growth_adds_an_industrial_worker_and_forecast_includes_future_growth(self):
        self.game.set_workforce(0, 2, 2, 5)
        self.earth.growth_progress = 95
        self.game.credits = 1000
        self.game.queue_building(0, 2, "research_lab")
        self.game.queue_ship(0, 2, "frigate")
        before = self.game.to_dict()
        estimates = self.game.queue_estimates(self.earth)
        self.assertEqual(self.game.to_dict(), before)
        completed = []
        for turn in range(1, estimates[-1]+1):
            report = self.game.advance_turn()
            completed.extend([turn]*len(report.completed))
            if turn == 1:
                self.assertEqual((self.earth.population, self.earth.farmers, self.earth.scientists, self.earth.workers), (9, 2, 5, 2))
        self.assertEqual(completed, estimates)

    def test_colonization_allocates_food_and_capture_preserves_jobs(self):
        self.game.ships = [Ship(1, "colony_ship", 0)]
        self.game.next_ship_id = 2
        mars = self.game.colonize(1, 0, 3)
        self.assertEqual((mars.population, mars.farmers, mars.workers, mars.scientists), (1, 1, 0, 0))
        self.assertEqual(self.game.population_report(mars).balance, 1)
        game = new_game(seed=2408, fog_of_war=False)
        sid, pid = game.opponent.home_system, game.opponent.home_planet
        game.set_workforce(sid, pid, 3, 2, owner=RIVAL)
        game.ships = [Ship(i, "troop_transport", sid) for i in (1, 2)]
        game.next_ship_id = 3
        self.assertTrue(game.invade(sid, pid).captured)
        world = game.planet_at(sid, pid)
        self.assertEqual((world.owner, world.farmers, world.workers, world.scientists), (PLAYER, 3, 3, 2))


class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.game = new_game(seed=2408, with_ai=False)
        self.earth = self.game.planet_at(0, 2)

    def test_buy_uses_remaining_work_completes_now_and_preserves_next_project(self):
        self.game.queue_ship(0, 2, "frigate")
        self.game.queue_building(0, 2, "hydroponic_farm")
        self.game.advance_turn()
        next_project = copy.deepcopy(self.earth.construction_queue[1])
        before = self.game.to_dict()
        self.assertEqual(self.game.buy_construction_cost(0, 2), 60)
        item = self.game.buy_construction(0, 2)
        self.assertEqual(item, "frigate")
        self.assertEqual(self.game.credits, before["credits"]-60)
        self.assertEqual(self.game.turn, before["turn"])
        self.assertEqual(self.earth.growth_progress, 10)
        self.assertEqual(self.earth.buildings, [])
        self.assertEqual([s.kind for s in self.game.ships], ["frigate"])
        self.assertEqual(self.earth.construction_queue, [next_project])
        self.assertEqual(self.game.population_report(self.earth).produced, 10)

    def test_buying_ships_commissions_once_with_unique_ids_and_owner(self):
        game = new_game(seed=2408, fog_of_war=False)
        game.credits = game.opponent.credits = 1000
        for owner, sid, pid in ((PLAYER, 0, 2), (RIVAL, game.opponent.home_system, game.opponent.home_planet)):
            game.queue_ship(sid, pid, "scout", owner=owner)
            game.buy_construction(sid, pid, owner=owner)
        self.assertEqual([(s.id, s.owner, s.hull) for s in game.ships], [(1, PLAYER, 8), (2, RIVAL, 8)])
        self.assertEqual(game.next_ship_id, 3)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        before = game.to_dict()
        with self.assertRaises(RuleError):
            game.buy_construction(0, 2)
        self.assertEqual(game.to_dict(), before)

    def test_gate_requires_industry_then_five_more_turns_of_charging(self):
        from orion.research import BRANCHES, TECHNOLOGIES, branch_tiers, choices
        self.game.credits = self.game.resources = 2000
        self.game.research = sum(choices(b, t)[0].cost for b in BRANCHES for t in branch_tiers(b))+TECHNOLOGIES["ascension_theory"].cost
        for branch in BRANCHES:
            for tier in branch_tiers(branch):
                self.game.choose_research(choices(branch, tier)[0].id)
        self.game.choose_research("ascension_theory")
        self.game.change_production(0, 2, "ascension_gate")
        before = self.game.to_dict()
        with self.assertRaisesRegex(RuleError, "industry"):
            self.game.buy_construction(0, 2)
        self.assertEqual(self.game.to_dict(), before)
        finish_building_next_turn(self.game)
        self.assertEqual((self.game.turn, self.earth.ascension_gate, self.earth.gate_charge), (2, True, 0))
        self.assertEqual(GameState.from_dict(self.game.to_dict()), self.game)
        for _ in range(4):
            self.game.advance_turn()
            self.assertIsNone(self.game.result)
        self.game.advance_turn()
        self.assertEqual((self.game.result.winner, self.game.result.condition), (PLAYER, "science"))

    def test_change_and_prioritize_retain_paid_progress_across_save_load(self):
        self.game.queue_building(0, 2, "factory")
        self.game.advance_turn()
        original = copy.deepcopy(self.earth.construction_queue[0])
        self.game.change_production(0, 2, "scout")
        self.assertEqual(self.earth.construction_queue[1], original)
        self.assertEqual(self.game.credits, 128)
        restored = GameState.from_dict(self.game.to_dict())
        self.assertEqual(restored, self.game)
        self.game.prioritize_construction(0, 2, 1)
        self.assertEqual(self.earth.construction_queue[0], original)
        self.assertEqual(self.game.cancel_construction(0, 2, 0), "33 RES")
        self.assertEqual(self.earth.construction_queue[0].item_id, "scout")

    def test_buy_and_changes_reject_insufficient_funds_full_slots_and_invalid_indices(self):
        self.game.queue_building(0, 2, "factory")
        self.game.credits = 1
        for action in (lambda: self.game.buy_construction(0, 2),
                       lambda: self.game.change_production(0, 2, []),
                       lambda: self.game.prioritize_construction(0, 2, True),
                       lambda: self.game.prioritize_construction(0, 2, 7)):
            before = self.game.to_dict()
            with self.assertRaises(RuleError):
                action()
            self.assertEqual(self.game.to_dict(), before)
        self.game.credits = 1000
        self.earth.buildings = ["factory"]*(self.earth.building_capacity-1)
        before = self.game.to_dict()
        with self.assertRaises(RuleError):
            self.game.change_production(0, 2, "mine")
        self.assertEqual(self.game.to_dict(), before)

    def test_enemy_assets_and_active_combat_block_every_new_order(self):
        game = new_game(seed=2408)
        sid, pid = game.opponent.home_system, game.opponent.home_planet
        game.queue_building(sid, pid, "mine", owner=RIVAL)
        game.queue_building(0, 2, "mine")
        for s, p in ((sid, pid), (0, 2)):
            if s == 0:
                game.ships = [Ship(1, "frigate", 0), Ship(2, "frigate", 0, owner=RIVAL)]
                game.next_ship_id = 3
                game.start_combat(0)
            for action in (lambda: game.set_workforce(s, p, 1, 1),
                           lambda: game.buy_construction(s, p),
                           lambda: game.change_production(s, p, "scout"),
                           lambda: game.prioritize_construction(s, p, 0)):
                before = game.to_dict()
                with self.assertRaises(RuleError):
                    action()
                self.assertEqual(game.to_dict(), before)


class WorkforceSaveTests(unittest.TestCase):
    def test_v11_migrates_both_current_worlds_and_stale_surveys_and_preserves_source(self):
        game = new_game(seed=2408)
        sid = game.opponent.home_system
        game.ships = [Ship(1, "scout", sid)]
        game.next_ship_id = 2
        refresh(game)
        game.send_ship(1, 0)
        game.queue_building(0, 2, "mine")
        game.ship_at(1).departure_pending = False  # Legacy course snapshot.
        game.planet_at(0, 2).growth_progress = 65
        legacy_economy(game)
        with tempfile.TemporaryDirectory() as folder:
            store = Storage(folder)
            path = store.save(game)
            payload = json.loads(path.read_text())
            payload["version"] = 11
            legacy_research_payload(payload)
            for row in payload["game"]["systems"]+payload["game"]["exploration"]["surveys"]:
                for world in row["worlds"]:
                    world.pop("farmers")
                    world.pop("scientists")
            path.write_text(json.dumps(payload))
            original = path.read_bytes()
            restored, _ = store.load(path)
            self.assertEqual(path.read_bytes(), original)
            expected = payload["game"]
            expected["victory_conditions"] = tuple(expected["victory_conditions"])
            for row in expected["systems"]+expected["exploration"]["surveys"]:
                for world in row["worlds"]:
                    world["farmers"], world["scientists"] = min(2, world["population"]), 0
            expected.update(sensor_contacts=[], sensor_reports=[], next_sensor_report_id=1, sensor_news_read=0)
            expected["diplomacy"]["introduced"] = True  # Old confirmed contacts do not replay introductions.
            for empire in [expected, expected["opponent"], *expected["other_opponents"].values()]:
                state = empire["technology"]
                state.update(legacy_count=len(state["completed"]), legacy_active=state["active"] is not None, legacy_starships=True, legacy_arsenal=True, legacy_fuel=True, legacy_black_holes=True)
            from scenarios import migrated_statistics
            history_source = copy.deepcopy(game)
            for system in history_source.systems:
                for planet in system.worlds:
                    planet.farmers, planet.scientists = min(2, planet.population), 0
            expected["statistics"] = migrated_statistics(history_source).statistics
            self.assertEqual(restored.to_dict(), expected)
            restored.move_worker(0, 2, "workers", "scientists")
            resumed = store.load(store.save(restored))[0]
            for _ in range(12):
                self.assertEqual(restored.advance_turn(), resumed.advance_turn())
                self.assertEqual(restored, resumed)

    def test_malformed_worker_counts_are_rejected_in_live_and_survey_data(self):
        game = new_game(seed=2408)
        for source in ("systems", "surveys"):
            for values in ({"farmers": True}, {"farmers": -1}, {"scientists": 1.5},
                           {"farmers": 5, "scientists": 4}, {"scientists": 9}, {"farmers": None}):
                with self.subTest(source=source, values=values):
                    data = game.to_dict()
                    rows = data["systems"] if source == "systems" else data["exploration"]["surveys"]
                    earth = next(p for row in rows for p in row["worlds"] if p["name"] == "Earth")
                    earth.update(values)
                    with self.assertRaises(SaveError):
                        GameState.from_dict(data)
        data = game.to_dict()
        data["systems"][0]["worlds"][3]["farmers"] = 1
        with self.assertRaises(SaveError):
            GameState.from_dict(data)


class PlanetOverviewInterfaceTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.tmp.name), capture=True)
        self.app.window = pg.display.set_mode((980, 900), pg.RESIZABLE)
        self.app.game = new_game(seed=2408, with_ai=False)
        self.app.open_planet(2)

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

    def test_worker_clicks_change_production_save_and_do_not_create_or_lose_workers(self):
        self.click("worker_workers")
        self.assertEqual(self.app.worker_source, "workers")
        self.click("worker_scientists")
        earth = self.app.game.planet_at(0, 2)
        self.assertEqual((earth.farmers, earth.workers, earth.scientists), (2, 5, 1))
        self.assertEqual(self.app.game.planet_yields(earth), (5, 8, 2))
        self.assertIsNone(self.app.worker_source)
        self.assertEqual(self.app.storage.load(self.app.storage.saves_dir/"autosave.json")[0], self.app.game)
        before = self.app.game.to_dict()
        self.click("worker_farmers")
        self.click("worker_farmers")
        self.assertEqual(self.app.game.to_dict(), before)
        from orion import planet_view
        with patch.object(planet_view, "text", wraps=planet_view.text) as drawn:
            self.app.render()
        strings = [str(call.args[1]) for call in drawn.call_args_list]
        for expected in ("NET CREDITS", "FOOD / USED", "INDUSTRY", "RESEARCH", "+2", "10 / 8", "5"):
            self.assertIn(expected, strings)

    def test_building_has_no_buy_control_but_normal_completion_opens_inspection(self):
        self.click("planet_change")
        self.assertEqual(self.app.screen, "production")
        self.click("production_build_factory")
        self.assertEqual(self.app.screen, "production")
        self.click("production_return")
        self.assertEqual(self.app.screen, "planet")
        self.assertFalse(any(b.key == "planet_buy" for b in self.app.buttons))
        finish_building_next_turn(self.app.game)
        self.app.render()
        self.assertEqual(self.app.game.planet_at(0, 2).buildings, ["factory"])
        self.assertEqual(self.app.game.credits, 128)
        self.assertEqual(self.app.game.turn, 2)
        self.assertFalse(any(b.key == "planet_buy" for b in self.app.buttons))
        self.click("surface_factory")
        self.assertEqual(self.app.screen, "colony")
        self.click("tab_overview")
        bottom = [b.key for b in self.app.buttons if b.rect.top >= 840]
        self.assertEqual(bottom, ["planet_return"])
        self.click("planet_world_3")
        self.assertEqual(self.app.game.selected_planet, 3)
        self.click("planet_return")
        self.assertEqual((self.app.screen, self.app.game.selected_system), ("system", 0))

    def test_queue_pagination_priority_and_cancel_keep_paused_work(self):
        game = self.app.game
        game.credits = 1000
        game.queue_building(0, 2, "factory")
        game.advance_turn()
        for _ in range(7):
            game.queue_ship(0, 2, "scout")
        self.click("planet_change")
        self.click("production_next")
        self.click("production_priority_7")
        self.assertEqual(game.planet_at(0, 2).construction_queue[1].progress, 6)
        self.assertEqual(self.app.screen, "production")
        self.click("production_cancel_0")
        self.assertEqual(game.planet_at(0, 2).construction_queue[0].progress, 6)
        self.assertEqual(self.app.storage.load(self.app.storage.saves_dir/"autosave.json")[0], game)

    def test_all_eight_planets_fit_the_system_panel_and_switch_without_orders(self):
        system = self.app.game.systems[0]
        for index in range(4, 8):
            world = copy.deepcopy(system.worlds[3])
            world.id, world.name = index, f"Sol {index+1}"
            system.worlds.append(world)
        system.planets = 8
        self.app.render()
        rows = [b for b in self.app.buttons if b.key.startswith("planet_world_")]
        self.assertEqual(len(rows), 8)
        for index, row in enumerate(rows):
            self.assertTrue(pg.Rect(24, 54, 248, 244).contains(row.rect))
            self.assertTrue(all(not row.rect.colliderect(other.rect) for other in rows[index+1:]))
        before = copy.deepcopy(system.worlds)
        self.click("planet_world_7")
        self.assertEqual((self.app.screen, self.app.game.selected_planet), ("planet", 7))
        before[2].trade_goods = True
        self.assertEqual(system.worlds, before)
        self.assertFalse(any(b.key in ("planet_change", "planet_buy") for b in self.app.buttons))


if __name__ == "__main__":
    unittest.main()
