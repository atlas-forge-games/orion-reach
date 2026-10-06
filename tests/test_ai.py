"""Two-empire economy, AI expansion, ownership boundaries and save continuity."""

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

from orion.empire import colony_rows, summarize_empire
from orion.model import GameState, PLAYER, RIVAL, RuleError, SaveError, Ship, new_game
from orion.storage import Storage


class AIRulesTests(unittest.TestCase):
    def test_start_is_distant_deterministic_and_preserves_generated_worlds(self):
        peaceful = new_game(seed=2408, with_ai=False)
        game = new_game(seed=2408)
        expected = peaceful.opponent_home()
        home = game.planet_at(game.opponent.home_system, game.opponent.home_planet)
        self.assertEqual((game.opponent.home_system, home.id), (expected[0].id, expected[1].id))
        self.assertNotEqual(game.opponent.home_system, 0)
        self.assertEqual((home.population, home.yields_per_turn, game.opponent.credits), (8, (6, 8, 0), 120))
        self.assertEqual(game.systems[0], peaceful.systems[0])
        self.assertEqual(game.empire_rates, (8, 0))
        peaceful.add_opponent()
        self.assertEqual(game.systems, peaceful.systems)
        self.assertEqual(game.opponent, peaceful.opponent)
        before = game.to_dict()
        with self.assertRaises(RuleError):
            game.add_opponent()
        self.assertEqual(game.to_dict(), before)

    def test_separate_banks_equal_costs_local_work_and_refunds(self):
        game = new_game(seed=2408)
        sid, pid = game.opponent.home_system, game.opponent.home_planet
        home = game.planet_at(sid, pid)
        game.queue_building(sid, pid, "factory", owner=RIVAL)
        game.queue_building(0, 2, "factory")
        self.assertEqual((game.credits, game.opponent.credits), (75, 75))
        report = game.advance_turn()
        self.assertEqual((game.credits, game.opponent.credits), (83, 83))
        self.assertEqual(home.construction_queue, game.planet_at(0, 2).construction_queue)
        self.assertEqual((report.income, report.research, report.completed), (8, 0, []))
        self.assertEqual(game.cancel_construction(sid, pid, 0, owner=RIVAL), 33)
        self.assertEqual(game.credits, 83)
        self.assertEqual(game.opponent.credits, 116)
        home.buildings = ["research_lab"]
        game.opponent.credits = 0  # AI cannot place another project before income.
        game.advance_turn()
        self.assertEqual((game.research, game.opponent.research), (0, 4))
        self.assertEqual(summarize_empire(game).research, 0)
        self.assertEqual(summarize_empire(game, owner=RIVAL).research, 4)

    def test_every_mutating_order_rejects_the_other_empires_assets_atomically(self):
        game = new_game(seed=2408)
        sid, pid = game.opponent.home_system, game.opponent.home_planet
        home = game.planet_at(sid, pid)
        home.buildings = ["factory"]
        game.queue_ship(sid, pid, owner=RIVAL)
        game.ships = [Ship(1, "colony_ship", 0, owner=RIVAL), Ship(2, "colony_ship", 0)]
        game.next_ship_id = 3
        actions = [
            lambda: game.queue_building(sid, pid, "mine"),
            lambda: game.queue_ship(sid, pid),
            lambda: game.cancel_construction(sid, pid, 0),
            lambda: game.demolish_building(sid, pid, 0),
            lambda: game.send_ship(1, 1),
            lambda: game.colonize(1, 0, 3),
            lambda: game.queue_building(0, 2, "mine", owner=RIVAL),
            lambda: game.queue_ship(0, 2, owner=RIVAL),
            lambda: game.cancel_construction(0, 2, 0, owner=RIVAL),
            lambda: game.demolish_building(0, 2, 0, owner=RIVAL),
            lambda: game.send_ship(2, 1, owner=RIVAL),
            lambda: game.colonize(2, 0, 3, owner=RIVAL),
        ]
        for action in actions:
            before = game.to_dict()
            with self.assertRaises(RuleError):
                action()
            self.assertEqual(game.to_dict(), before)
        self.assertEqual([s.id for s in game.colony_ships_at(0)], [2])
        self.assertEqual([s.id for s in game.colony_ships_at(0, owner=RIVAL)], [1])

    def test_rival_expands_across_systems_and_develops_over_many_turns(self):
        for seed, size in ((1, "Compact"), (42, "Standard"), (2408, "Expansive")):
            with self.subTest(seed=seed, size=size):
                game = new_game(seed=seed, galaxy_size=size)
                for _ in range(100):
                    game.advance_turn()
                    self.assertGreaterEqual(game.opponent.credits, 0)
                    self.assertEqual(GameState.from_dict(game.to_dict()), game)
                rows = colony_rows(game, owner=RIVAL)
                self.assertGreaterEqual(len(rows), 4)
                self.assertGreater(len({s.id for s, _ in rows}), 1)
                self.assertTrue(any("factory" in p.buildings and "trade_center" in p.buildings for _, p in rows))
                self.assertGreater(game.opponent.research, 0)
                self.assertEqual(game.credits, 920)  # Only Earth's 8 CR for 100 turns.
                self.assertEqual(summarize_empire(game).colonies, 1)
                self.assertTrue(all(p.used_slots <= p.building_capacity for s in game.systems for p in s.worlds))

    def test_save_resume_preserves_decisions_routes_production_and_ids(self):
        game = new_game(seed=2408)
        game.queue_ship(0, 2)
        for _ in range(34):
            game.advance_turn()
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            restored, _ = storage.load(storage.save(game))
            for _ in range(45):
                self.assertEqual(game.advance_turn(), restored.advance_turn())
                self.assertEqual(game, restored)
                self.assertEqual(len({s.id for s in game.ships}), len(game.ships))
                self.assertTrue(all(s.id < game.next_ship_id for s in game.ships))
            self.assertLessEqual(len(game.opponent.events), 12)
            self.assertTrue(all(event.turn <= game.turn for event in game.opponent.events))
            self.assertEqual(storage.load(storage.save(restored))[0], game)

    def test_completed_ships_inherit_owner_and_reports_only_show_player_results(self):
        game = new_game(seed=2408)
        sid, pid = game.opponent.home_system, game.opponent.home_planet
        game.queue_ship(0, 2)
        game.queue_ship(sid, pid, owner=RIVAL)
        for _ in range(7):
            report = game.advance_turn()
        self.assertEqual(len(game.ships), 2)
        self.assertEqual({s.owner for s in game.ships}, {PLAYER, RIVAL})
        self.assertEqual(report.completed, ["Colony ship on Earth"])
        self.assertEqual(len(game.ships_owned_by()), 1)
        self.assertEqual(game.next_ship_id, 3)

    def test_player_claim_during_flight_is_preserved_and_rival_reroutes(self):
        game = new_game(seed=2408)
        home = game.opponent.home_system
        target, planet = next((s, p) for s in game.systems if s.id not in (0, home)
                              for p in s.worlds if p.habitability > 0)
        for other in target.worlds:
            if other is not planet:
                other.biome = "Barren"
        game.ships = [Ship(1, "colony_ship", home, owner=RIVAL), Ship(2, "colony_ship", target.id)]
        game.next_ship_id = 3
        duration = game.send_ship(1, target.id, owner=RIVAL)
        game.colonize(2, target.id, planet.id)
        for _ in range(duration):
            game.advance_turn()
        ship = game.ship_at(1, owner=RIVAL)
        self.assertFalse(ship.in_transit)
        game.advance_turn()
        self.assertTrue(ship.in_transit or ship.system_id != target.id)
        self.assertEqual((planet.owner, planet.population), (PLAYER, 1))

    def test_rival_avoids_sending_two_ships_to_a_single_available_world(self):
        game = new_game(seed=2408)
        home = game.opponent.home_system
        for s in game.systems:
            for p in s.worlds:
                if not p.colonized:
                    p.biome = "Barren"
        targets = [s for s in game.systems if s.id not in (0, home) and s.worlds][:2]
        for s in targets:
            s.worlds[0].biome = "Terran"
        game.ships = [Ship(i, "colony_ship", home, owner=RIVAL) for i in (1, 2)]
        game.next_ship_id = 3
        game.advance_turn()
        destinations = {s.destination if s.in_transit else s.system_id for s in game.ships}
        self.assertEqual(destinations, {s.id for s in targets})

    def test_exhausted_galaxy_keeps_idle_ships_and_develops_without_new_ship_orders(self):
        game = new_game(seed=2408)
        for s in game.systems:
            for p in s.worlds:
                if not p.colonized:
                    p.biome = "Barren"
        game.ships = [Ship(1, "colony_ship", game.opponent.home_system, owner=RIVAL)]
        game.next_ship_id = 2
        for _ in range(35):
            game.advance_turn()
        self.assertEqual(len(game.ships), 1)
        self.assertFalse(game.ships[0].in_transit)
        self.assertEqual(summarize_empire(game, owner=RIVAL).colonies, 1)
        self.assertGreater(game.opponent.research, 0)
        self.assertEqual(game.next_ship_id, 2)

    def test_no_starting_world_rejects_addition_without_mutation(self):
        game = new_game(seed=2408, with_ai=False)
        for s in game.systems[1:]:
            for p in s.worlds:
                p.biome = "Barren"
        before = game.to_dict()
        with self.assertRaisesRegex(RuleError, "No unclaimed"):
            game.add_opponent()
        self.assertEqual(game.to_dict(), before)

    def test_v4_migration_preserves_player_assets_and_waits_for_explicit_rival(self):
        game = new_game(seed=2408, with_ai=False)
        game.queue_ship(0, 2)
        for _ in range(7):
            game.advance_turn()
        game.send_ship(1, 1)
        game.queue_building(0, 2, "mine")
        game.advance_turn()
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            path = storage.save(game)
            payload = json.loads(path.read_text())
            payload["version"] = 4
            payload["game"].pop("opponent")
            for s in payload["game"]["systems"]:
                for p in s["worlds"]:
                    p.pop("owner")
            for s in payload["game"]["ships"]:
                s.pop("owner")
            path.write_text(json.dumps(payload))
            before = path.read_bytes()
            restored, _ = storage.load(path)
            self.assertEqual(restored, game)
            self.assertEqual(path.read_bytes(), before)
            restored.add_opponent()
            self.assertEqual(restored.ships, game.ships)
            self.assertEqual(restored.credits, game.credits)
            self.assertEqual(restored.systems[0], game.systems[0])
            self.assertEqual(storage.load(storage.save(restored))[0], restored)

    def test_invalid_ownership_and_rival_save_records_are_rejected(self):
        game = new_game(seed=2408)
        game.ships = [Ship(1, "colony_ship", 0)]
        game.next_ship_id = 2
        mutations = [
            lambda d: d["systems"][0]["worlds"][2].update(owner=None),
            lambda d: d["systems"][0]["worlds"][3].update(owner=PLAYER),
            lambda d: d["systems"][0]["worlds"][2].update(owner="unknown"),
            lambda d: d["ships"][0].update(owner="unknown"),
            lambda d: d["ships"][0].pop("owner"),
            lambda d: d.update(opponent=None),
            lambda d: d.pop("opponent"),
            lambda d: d["opponent"].update(credits=-1),
            lambda d: d["opponent"].update(research=True),
            lambda d: d["opponent"].update(home_system=0, home_planet=2),
            lambda d: d["opponent"].update(name=""),
            lambda d: d["opponent"]["events"][0].update(turn=2),
            lambda d: d["opponent"]["events"][0].update(message="x\ny"),
            lambda d: d["opponent"].update(events=[{"turn": 1, "message": "Event"}]*13),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                data = copy.deepcopy(game.to_dict())
                mutate(data)
                with self.assertRaises(SaveError):
                    GameState.from_dict(data)


class AIInterfaceTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.tmp.name), capture=True)
        self.app.game = new_game(seed=2408)
        self.app.go("galaxy")
        self.app.render()
        self.app.present()

    def click(self, key):
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        x, y = button.rect.center
        v = self.app.viewport
        pos = (v.x+round(x*v.w/1440), v.y+round(y*v.h/900))
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, button=1, pos=pos))
            self.app.render()

    def test_add_rival_to_old_campaign_and_advance_through_real_controls(self):
        self.app.game = new_game(seed=2408, with_ai=False)
        self.click("open_empire")
        self.click("empire_rival")
        self.assertEqual(self.app.screen, "rival")
        self.click("add_rival")
        self.assertIsNotNone(self.app.game.opponent)
        restored, _ = self.app.storage.load(self.app.storage.saves_dir/"autosave.json")
        self.assertEqual(restored, self.app.game)
        self.click("rival_end_turn")
        rival = self.app.game.opponent
        home = self.app.game.planet_at(rival.home_system, rival.home_planet)
        self.assertEqual(home.construction_queue[0].progress, 6)
        self.assertEqual(self.app.game.credits, 128)
        self.click("rival_pause")
        self.click("resume")
        self.assertEqual(self.app.screen, "rival")
        self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_ESCAPE, mod=0))
        self.assertEqual(self.app.screen, "empire")
        self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_i, mod=0))
        self.assertEqual(self.app.screen, "galaxy")

    def test_rival_survey_disables_build_cancel_demolish_and_ship_controls(self):
        game = self.app.game
        rival = game.opponent
        home = game.planet_at(rival.home_system, rival.home_planet)
        home.buildings = ["factory"]
        game.queue_building(rival.home_system, rival.home_planet, "mine", owner=RIVAL)
        self.click("open_empire")
        self.assertEqual([b.key for b in self.app.buttons if b.key.startswith("empire_colony_")], ["empire_colony_0_2"])
        self.click("empire_rival")
        self.click(f"rival_colony_{rival.home_system}_{rival.home_planet}")
        self.assertEqual(self.app.screen, "planet")
        self.assertFalse(any(b.key == "colonize_planet" for b in self.app.buttons))
        self.click("tab_colony")
        before = game.to_dict()
        for key in ("build_factory", "build_mine", "build_trade_center", "build_research_lab"):
            self.assertFalse(next(b for b in self.app.buttons if b.key == key).enabled)
            self.click(key)
        self.click("colony_slot_0")
        self.assertFalse(next(b for b in self.app.buttons if b.key == "demolish_building").enabled)
        self.click("demolish_building")
        self.assertIsNone(self.app.dialog)
        self.click("colony_slot_1")
        self.assertFalse(next(b for b in self.app.buttons if b.key == "cancel_construction").enabled)
        self.click("cancel_construction")
        self.click("tab_shipyard")
        for key in ("build_colony_ship", "queue_cancel_0"):
            self.assertFalse(next(b for b in self.app.buttons if b.key == key).enabled)
            self.click(key)
        self.assertEqual(game.to_dict(), before)

    def test_fleet_directory_and_pagination_only_expose_player_ships(self):
        game = self.app.game
        game.ships = [Ship(i, "colony_ship", 0, owner=RIVAL if i % 2 else PLAYER) for i in range(1, 12)]
        game.next_ship_id = 12
        self.click("open_fleets")
        visible = lambda: [b.key for b in self.app.buttons if b.key.startswith("ship_send_")]
        self.assertEqual(visible(), ["ship_send_2", "ship_send_4", "ship_send_6", "ship_send_8"])
        self.click("fleets_next")
        self.assertEqual(visible(), ["ship_send_10"])
        self.assertFalse(next(b for b in self.app.buttons if b.key == "fleets_next").enabled)
        self.assertEqual(self.app.focus, "ship_send_10")


if __name__ == "__main__":
    unittest.main()
