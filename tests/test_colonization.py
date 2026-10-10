from scenarios import legacy_economy
"""Ship production, travel, settlement, migration, and the playable UI loop."""

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
from orion.model import ConstructionProject, GameState, RuleError, SaveError, Ship
from scenarios import empty_fleet_game as new_game, place_near, use_nearby_system
from functools import partial

# Keep the original single-empire regression fixtures isolated from AI turns.
new_game = partial(new_game, with_ai=False, fog_of_war=False)
from orion.production import MAX_QUEUE, travel_turns
from orion.storage import SAVE_VERSION, Storage


def remote_world(game):
    system, planet = min(((s, p) for s in game.systems[1:] for p in s.worlds
                          if p.habitability > 0),
                         key=lambda row: (travel_turns(game.systems[0], row[0]), row[0].id, row[1].id))
    use_nearby_system(game, system.id)
    return system, planet


class ColonizationRulesTests(unittest.TestCase):
    def setUp(self):
        self.game = new_game(seed=2408)
        self.earth = self.game.systems[0].worlds[2]

    def test_shared_queue_overflow_forecast_and_no_building_slot_for_ships(self):
        self.game.credits = self.game.resources = 1000
        self.game.queue_building(0, 2, "factory")
        self.game.queue_ship(0, 2)
        self.game.queue_building(0, 2, "mine")
        before = self.game.to_dict()
        self.assertEqual(self.earth.used_slots, 2)
        self.assertEqual(self.earth.queue_estimates(), [4, 7, 8])
        self.assertEqual(self.game.to_dict(), before)
        for _ in range(7):
            self.game.advance_turn()
        self.assertEqual(self.earth.buildings, ["factory"])
        self.assertEqual(self.earth.construction_queue[0].progress, 6)
        self.assertEqual(self.game.ships, [Ship(1, "colony_ship", 0)])
        self.game.advance_turn()
        self.assertEqual(self.earth.buildings, ["factory", "mine"])
        self.assertEqual(self.game.next_ship_id, 2)

    def test_full_planet_can_build_ships_and_queue_limit_is_atomic(self):
        self.earth.buildings = ["factory"]*8
        self.game.credits = self.game.resources = 10000
        for _ in range(MAX_QUEUE):
            self.game.queue_ship(0, 2)
        self.assertEqual(self.earth.free_slots, 0)
        self.assertEqual(summarize_empire(self.game).used_slots, 8)
        self.assertEqual(len(colony_rows(self.game, "building")), 1)
        before = self.game.to_dict()
        with self.assertRaisesRegex(RuleError, "queue"):
            self.game.queue_ship(0, 2)
        self.assertEqual(self.game.to_dict(), before)
        self.assertEqual(GameState.from_dict(before), self.game)

    def test_ship_refunds_and_invalid_build_orders(self):
        for system, planet, kind in ((0, 3, "colony_ship"), (0, 2, "unknown"), (-1, 2, "colony_ship")):
            before = self.game.to_dict()
            with self.assertRaises(RuleError):
                self.game.queue_ship(system, planet, kind)
            self.assertEqual(self.game.to_dict(), before)
        self.game.queue_ship(0, 2)
        self.assertEqual(self.game.credits, 120)
        self.assertEqual(self.game.cancel_construction(0, 2, 0), "0 RES")
        self.game.queue_ship(0, 2)
        self.game.advance_turn()
        self.assertEqual(self.game.cancel_construction(0, 2, 0), "68 RES")
        self.assertEqual((self.game.credits, self.game.resources), (128, 110))
        self.assertEqual(self.game.ships, [])

    def test_distance_travel_arrival_and_no_early_or_duplicate_arrival(self):
        source, target = self.game.systems[:2]
        source.x, source.y, target.x, target.y = .1, .1, .1+10/140, .1
        self.game.technology.completed.append("lightweight_alloys")  # A 10 ly voyage needs improved tanks.
        self.game.ships = [Ship(1, "colony_ship", 0)]
        self.game.next_ship_id = 2
        self.assertEqual(self.game.send_ship(1, 1), 5)
        for remaining in (4, 3, 2, 1):
            report = self.game.advance_turn()
            self.assertEqual(report.arrivals, [])
            self.assertEqual(self.game.ships[0].turns_remaining, remaining)
            self.assertEqual(self.game.colony_ships_at(0), [])
            self.assertEqual(self.game.colony_ships_at(1), [])
        report = self.game.advance_turn()
        self.assertEqual(len(report.arrivals), 1)
        self.assertEqual(self.game.ships[0], Ship(1, "colony_ship", 1))
        self.assertEqual(self.game.advance_turn().arrivals, [])

    def test_invalid_travel_cannot_mutate_a_ship(self):
        self.game.ships = [Ship(1, "colony_ship", 0)]
        for ship_id, destination in ((1, 0), (1, -1), (1, True), (99, 2), (True, 2)):
            before = self.game.to_dict()
            with self.assertRaises(RuleError):
                self.game.send_ship(ship_id, destination)
            self.assertEqual(self.game.to_dict(), before)
        place_near(self.game, 1)
        self.game.send_ship(1, 1)
        self.game.ship_at(1).departure_pending = False  # Lock an actual flight, not a pending course.
        before = self.game.to_dict()
        with self.assertRaises(RuleError):
            self.game.send_ship(1, 3)
        self.assertEqual(self.game.to_dict(), before)

    def test_settlement_consumes_one_ship_and_adds_productive_colony(self):
        self.game.ships = [Ship(1, "colony_ship", 0), Ship(2, "colony_ship", 0)]
        self.game.next_ship_id = 3
        mars = self.game.colonize(1, 0, 3)
        self.assertTrue(mars.colonized)
        self.assertEqual(mars.population, 1)
        self.assertEqual(mars.yields_per_turn, (1, 1, 0))
        self.assertEqual(self.earth.population, 8)
        self.assertEqual(self.game.ships, [Ship(2, "colony_ship", 0)])
        self.assertEqual(self.game.credits, 120)
        self.assertEqual(summarize_empire(self.game).colonies, 2)
        self.assertEqual(self.game.advance_turn().income, 9)
        self.game.queue_building(0, 3, "mine")
        self.game.queue_ship(0, 3)
        self.assertEqual(mars.used_slots, 1)
        self.assertEqual(GameState.from_dict(self.game.to_dict()), self.game)
        before = self.game.to_dict()
        with self.assertRaises(RuleError):
            self.game.colonize(2, 0, 3)
        self.assertEqual(self.game.to_dict(), before)

    def test_settlement_requires_suitable_world_and_a_local_arrived_ship(self):
        for biome in ("Terran", "Ocean", "Desert", "Tundra", "Barren", "Volcanic"):
            with self.subTest(biome=biome):
                game = new_game(seed=2408)
                game.systems[0].worlds[3].biome = biome
                game.ships = [Ship(1, "colony_ship", 0)]
                before = game.to_dict()
                if biome in ("Barren", "Volcanic"):
                    with self.assertRaises(RuleError):
                        game.colonize(1, 0, 3)
                    self.assertEqual(game.to_dict(), before)
                else:
                    game.colonize(1, 0, 3)
                    self.assertEqual(game.ships, [])
        self.game.ships = [Ship(1, "colony_ship", 0)]
        system, planet = remote_world(self.game)
        for moving in (False, True):
            if moving:
                self.game.send_ship(1, system.id)
            before = self.game.to_dict()
            with self.assertRaises(RuleError):
                self.game.colonize(1, system.id, planet.id)
            self.assertEqual(self.game.to_dict(), before)

    def test_ids_remain_unique_after_settlement_and_new_construction(self):
        self.game.credits = self.game.resources = 1000
        self.earth.buildings = ["factory"]*8
        for _ in range(2):
            self.game.queue_ship(0, 2)
        for _ in range(3):
            self.game.advance_turn()
        self.assertEqual([s.id for s in self.game.ships], [1, 2])
        self.game.colonize(1, 0, 3)
        self.game.queue_ship(0, 2)
        for _ in range(2):
            self.game.advance_turn()
        self.assertEqual([s.id for s in self.game.ships], [2, 3])
        self.assertEqual(self.game.next_ship_id, 4)

    def test_round_trip_mid_route_and_mid_construction_then_settle(self):
        self.game.queue_ship(0, 2)
        for _ in range(7):
            self.game.advance_turn()
        target, planet = remote_world(self.game)
        self.game.send_ship(1, target.id)
        self.game.queue_building(0, 2, "factory")
        self.game.advance_turn()
        with tempfile.TemporaryDirectory() as folder:
            store = Storage(folder)
            restored, _ = store.load(store.save(self.game))
            self.assertEqual(restored, self.game)
            for _ in range(max(8, self.game.ship_at(1).turns_remaining)):
                self.assertEqual(restored.advance_turn(), self.game.advance_turn())
            restored.colonize(1, target.id, planet.id)
            self.game.colonize(1, target.id, planet.id)
            self.assertEqual(restored, self.game)
            self.assertEqual(store.load(store.save(restored))[0], restored)

    def test_v3_save_migrates_building_queue_without_rewriting_source(self):
        self.game.queue_building(0, 2, "factory")
        self.game.advance_turn()
        self.game.research = 12
        self.game.planet_at(0, 2).growth_progress = 0  # Legacy field defaults to zero.
        legacy_economy(self.game)
        with tempfile.TemporaryDirectory() as folder:
            store = Storage(folder)
            path = store.save(self.game)
            payload = json.loads(path.read_text())
            payload["version"] = 3
            payload["game"].pop("ships")
            payload["game"].pop("next_ship_id")
            for system in payload["game"]["systems"]:
                for planet in system["worlds"]:
                    for project in planet["construction_queue"]:
                        project["building_id"] = project.pop("item_id")
            path.write_text(json.dumps(payload))
            original = path.read_bytes()
            restored, _ = store.load(path)
            self.assertEqual(restored, self.game)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(json.loads(store.save(restored).read_text())["version"], SAVE_VERSION)

    def test_invalid_fleet_and_production_saves_are_rejected(self):
        self.game.ships = [Ship(1, "colony_ship", 0)]
        self.game.next_ship_id = 2
        corrupt = [
            {"id": True}, {"kind": "warship"}, {"system_id": -1}, {"destination": 0},
            {"destination": 999}, {"turns_remaining": 1}, {"travel_total": 1},
            {"turns_remaining": True}, {"destination": 1, "turns_remaining": 0, "travel_total": 2},
            {"destination": 1, "turns_remaining": 999, "travel_total": 999},
        ]
        for mutation in corrupt:
            with self.subTest(mutation=mutation):
                data = self.game.to_dict()
                data["ships"][0].update(mutation)
                with self.assertRaises(SaveError):
                    GameState.from_dict(data)
        for key, value in (("ships", {}), ("ships", self.game.to_dict()["ships"]*2), ("next_ship_id", 1), ("next_ship_id", True)):
            data = self.game.to_dict()
            data[key] = value
            with self.assertRaises(SaveError):
                GameState.from_dict(data)
        for queue in ([{"item_id": "unknown", "progress": 0}],
                      [{"item_id": "colony_ship", "progress": 42}],
                      [{"item_id": "colony_ship", "progress": 0}]*(MAX_QUEUE+1)):
            data = self.game.to_dict()
            data["systems"][0]["worlds"][2]["construction_queue"] = queue
            with self.assertRaises(SaveError):
                GameState.from_dict(data)


class ColonizationInterfaceTests(unittest.TestCase):
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

    def key(self, key):
        self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=key, mod=0))
        self.app.render()

    def test_build_travel_reload_arrive_and_settle_through_real_controls(self):
        self.app.window = pg.display.set_mode((980, 900), pg.RESIZABLE)
        self.app.present()
        self.click("star_0")
        self.click("galaxy_world_2")
        self.click("surface_shipyard")
        self.click("build_colony_ship")
        self.assertEqual(self.app.game.credits, 120)
        for _ in range(7):
            self.key(pg.K_e)
        self.click("shipyard_fleets")
        self.assertEqual(len(self.app.game.ships), 1)
        target, planet = remote_world(self.app.game)
        self.click("ship_send_1")
        self.click(f"star_{target.id}")
        self.assertEqual(self.app.screen, "galaxy")
        self.assertIsNone(self.app.game.ships[0].destination)
        self.click("send_course")
        self.assertEqual(self.app.screen, "fleets")
        self.key(pg.K_e)
        self.key(pg.K_F5)
        path = next(p for p in self.app.storage.saves_dir.glob("*.json") if p.name != "autosave.json")
        self.app.load_game(path)
        self.key(pg.K_f)
        while self.app.game.ships[0].in_transit:
            self.key(pg.K_e)
        self.click("ship_view_1")
        self.click(f"world_{planet.id}")
        self.click("colonize_planet")
        self.assertIsNotNone(self.app.dialog)
        self.click("dialog_cancel")
        self.assertFalse(self.app.game.systems[target.id].worlds[planet.id].colonized)
        self.click("colonize_planet")
        self.click("dialog_ok")
        self.assertEqual(self.app.screen, "planet")
        self.assertEqual(self.app.game.ships, [])
        self.assertEqual(self.app.game.systems[target.id].worlds[planet.id].population, 1)
        self.click("planet_change")
        self.click("production_build_mine")
        self.key(pg.K_i)
        rows = [b for b in self.app.buttons if b.key.startswith("empire_colony_")]
        self.assertEqual(len(rows), 2)
        saved, _ = self.app.storage.load(self.app.storage.saves_dir/"autosave.json")
        self.assertEqual(saved, self.app.game)

    def test_building_slot_cancellation_uses_mixed_queue_indices(self):
        self.app.game.credits = 1000
        self.app.open_shipyard(0, 2)
        self.click("build_colony_ship")
        self.click("tab_colony")
        self.click("build_factory")
        self.click("build_mine")
        self.click("cancel_construction")
        earth = self.app.game.systems[0].worlds[2]
        self.assertEqual([p.item_id for p in earth.construction_queue], ["colony_ship", "factory"])
        self.click("colony_slot_0")
        self.click("cancel_construction")
        self.assertEqual([p.item_id for p in earth.construction_queue], ["colony_ship"])
        self.assertEqual(earth.used_slots, 0)
        self.click("tab_shipyard")
        self.click("queue_cancel_0")
        self.assertEqual(earth.construction_queue, [])
        self.assertEqual(self.app.game.credits, 1000)

    def test_cancel_course_never_issues_order_and_returns_to_shipyard(self):
        self.app.game.ships = [Ship(1, "colony_ship", 0)]
        self.app.game.next_ship_id = 2
        self.app.open_shipyard(0, 2)
        self.key(pg.K_f)
        self.click("ship_send_1")
        self.click("star_1")
        self.key(pg.K_ESCAPE)
        self.assertIsNone(self.app.route_ship_id)
        self.assertEqual(self.app.game.ships[0], Ship(1, "colony_ship", 0))
        self.key(pg.K_f)
        self.assertEqual(self.app.screen, "shipyard")
        self.assertEqual((self.app.game.selected_system, self.app.game.selected_planet), (0, 2))
        self.click("shipyard_pause")
        self.click("settings")
        self.click("settings_done")
        self.click("resume")
        self.assertEqual(self.app.screen, "shipyard")

    def test_unsuitable_world_and_missing_ship_disable_settlement(self):
        self.app.open_system(0)
        self.app.open_planet(3)
        self.app.render()
        self.assertFalse(next(b for b in self.app.buttons if b.key == "colonize_planet").enabled)
        self.app.game.ships = [Ship(1, "colony_ship", 0)]
        self.app.game.next_ship_id = 2
        self.app.open_planet(0)
        self.app.render()
        before = self.app.game.to_dict()
        self.click("colonize_planet")
        self.assertIsNone(self.app.dialog)
        self.assertEqual(self.app.game.to_dict(), before)
        self.app.open_shipyard(0, 0)
        self.app.render()
        self.assertFalse(next(b for b in self.app.buttons if b.key == "build_colony_ship").enabled)

    def test_queue_and_fleet_pagination_and_visible_keyboard_selection(self):
        self.app.game.credits = 10000
        for _ in range(6):
            self.app.game.queue_ship(0, 2)
        self.app.open_shipyard(0, 2)
        self.click("queue_next")
        self.assertEqual(self.app.shipyard_page, 1)
        self.click("queue_cancel_5")
        self.assertEqual(self.app.shipyard_page, 0)
        self.app.game.ships = [Ship(i, "colony_ship", 0) for i in range(1, 6)]
        self.app.game.next_ship_id = 6
        self.key(pg.K_f)
        self.key(pg.K_PAGEDOWN)
        self.assertEqual(self.app.fleet_page, 1)
        self.key(pg.K_RETURN)
        self.assertEqual(self.app.route_ship_id, 5)
        self.key(pg.K_ESCAPE)
        self.assertEqual(self.app.screen, "fleets")
        self.click("fleets_pause")
        self.click("main_menu")
        self.click("resume")
        self.assertEqual(self.app.screen, "fleets")


if __name__ == "__main__":
    unittest.main()
