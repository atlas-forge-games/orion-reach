from scenarios import legacy_research_payload
from scenarios import legacy_economy
"""Colony-based supply, slower travel, AI boundaries and real map controls."""

import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame as pg

from orion.ai import military_orders, research_choice, scouting_orders
from orion.combat import retreat_destination
from orion.exploration import refresh
from orion.model import GameState, PLAYER, RIVAL, RuleError, SaveError, Ship
from scenarios import fixed_start_game as new_game
from orion.production import BASE_FUEL_RANGE, LEGACY_SHIP_SPEED, SHIP_SPEED, distance_ly, travel_turns
from orion.storage import Storage
from orion.research import TECHNOLOGIES
from scenarios import place_near, use_nearby_system


class FuelRulesTests(unittest.TestCase):
    def setUp(self):
        from scenarios import use_research_layout
        use_research_layout(self)

    def test_ten_light_years_take_five_turns_and_propulsion_only_changes_speed(self):
        origin = SimpleNamespace(id=0, x=.2, y=.4)
        target = SimpleNamespace(id=1, x=.2+10/140, y=.4)
        self.assertAlmostEqual(distance_ly(origin, target), 10)
        self.assertEqual(travel_turns(origin, target), 5)
        self.assertEqual(travel_turns(origin, target, 25), 4)
        self.assertEqual(travel_turns(origin, target, 75), 3)
        self.assertEqual(travel_turns(origin, origin), 0)
        game = new_game(seed=2408)
        nearby = place_near(game, 1, distance=7)
        self.assertEqual(game.travel_turns(game.systems[0], nearby), 4)
        self.assertEqual(BASE_FUEL_RANGE, 7)
        game.research = TECHNOLOGIES["ion_drives"].cost
        game.choose_research("ion_drives")
        self.assertEqual(game.fuel_range(), BASE_FUEL_RANGE)

    def test_radius_boundary_and_fog_setting_never_bypass_range(self):
        for fog in (True, False):
            game = new_game(seed=2408, fog_of_war=fog)
            target = place_near(game, 1, distance=7)
            self.assertTrue(game.within_fuel_range(target.id))
            self.assertEqual(game.send_ships([1, 2, 3], target.id), 4)
            game.cancel_departures([1, 2, 3])
            place_near(game, 1, distance=7.001)
            before = game.to_dict()
            with self.assertRaisesRegex(RuleError, "fuel range"):
                game.send_ships([1, 2, 3], target.id)
            self.assertEqual(game.to_dict(), before)

    def test_scouts_and_enemy_worlds_do_not_extend_range_but_colonization_does(self):
        game = new_game(seed=2408)
        frontier = next(s for s in game.systems[1:] if s.id != game.opponent.home_system
                        and any(not p.colonized and game.can_settle(p) for p in s.worlds))
        place_near(game, frontier.id, distance=6)
        remote = next(s for s in game.systems[1:] if s.id not in (frontier.id, game.opponent.home_system))
        place_near(game, remote.id, distance=10)
        game.ship_at(1).system_id = frontier.id
        refresh(game)
        self.assertLess(distance_ly(frontier, remote), game.fuel_range())
        self.assertFalse(game.within_fuel_range(remote.id))
        with self.assertRaisesRegex(RuleError, "fuel range"):
            game.send_ship(1, remote.id)
        place_near(game, game.opponent.home_system, distance=10)
        self.assertFalse(game.within_fuel_range(remote.id))
        game.ship_at(3).system_id = frontier.id
        world = next(p for p in frontier.worlds if not p.colonized and game.can_settle(p))
        game.colonize(3, frontier.id, world.id)
        self.assertTrue(game.within_fuel_range(remote.id))
        self.assertAlmostEqual(game.supply_distance(remote.id), 4)
        game.send_ship(1, remote.id)
        self.assertTrue(game.ship_at(1).departure_pending)

    def test_tank_upgrades_are_exclusive_additive_and_empire_specific(self):
        game = new_game(seed=2408)
        place_near(game, 1, distance=16)
        self.assertFalse(game.within_fuel_range(1))
        game.research = sum(TECHNOLOGIES[t].cost for t in ("lightweight_alloys", "composite_structures"))
        game.choose_research("lightweight_alloys")
        self.assertEqual(game.fuel_range(), 17)
        self.assertTrue(game.within_fuel_range(1))
        self.assertEqual(game.technology.status("superconductors"), "excluded")
        from scenarios import research_to
        research_to(game, "composite_structures")
        self.assertEqual(game.fuel_range(), 32)
        self.assertEqual(game.fuel_range(RIVAL), 7)
        self.assertEqual(game.bonuses_for(PLAYER).get("ship_speed", 0), 0)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_rejected_redirection_preserves_existing_order_and_cancel_still_works(self):
        game = new_game(seed=2408, with_ai=False)
        place_near(game, 1)
        game.send_ships([1, 3], 1)
        far = next(s.id for s in game.systems if not game.within_fuel_range(s.id))
        before = game.to_dict()
        with self.assertRaisesRegex(RuleError, "fuel range"):
            game.send_ships([1, 3], far)
        self.assertEqual(game.to_dict(), before)
        game.cancel_departures([1, 3])
        game.advance_turn()
        self.assertTrue(all(s.system_id == 0 and not s.has_course for s in game.ships))

    def test_a_ship_outside_supply_can_return_to_its_own_colony(self):
        game = new_game(seed=2408, with_ai=False)
        remote = max(game.systems, key=lambda s: game.supply_distance(s.id))
        game.ship_at(1).system_id = remote.id  # A ship from an older unrestricted campaign.
        self.assertFalse(game.within_fuel_range(remote.id))
        duration = game.send_ship(1, 0)
        self.assertGreater(duration, 5)
        self.assertEqual(game.ship_at(1).destination, 0)

    def test_ai_scans_only_reachable_stars_and_researches_tanks_at_a_closed_frontier(self):
        game = new_game(seed=172)  # Naturally has two reachable rival destinations.
        scouting_orders(game)
        destinations = [s.destination for s in game.ships_owned_by(RIVAL) if s.kind == "scout"]
        self.assertEqual(len(set(destinations)), 2)
        self.assertTrue(all(game.within_fuel_range(sid, RIVAL) for sid in destinations))
        # Survey its current supply area, leaving unknown stars beyond it.
        for system in game.systems:
            if game.within_fuel_range(system.id, RIVAL):
                scout = game.ships_owned_by(RIVAL)[0]
                game._clear_course(scout)
                scout.system_id = system.id
                refresh(game)
        game.opponent.research = TECHNOLOGIES["lightweight_alloys"].cost
        research_choice(game)
        self.assertIn("lightweight_alloys", game.opponent.technology.completed)
        self.assertEqual(game.fuel_range(RIVAL), 17)

    def test_hostile_ai_and_retreat_destinations_respect_colony_range(self):
        game = new_game(seed=2408, fog_of_war=False)
        place_near(game, 1)
        home = game.opponent.home_system
        game.diplomacy.relations = -100
        game.ships = [Ship(1, "frigate", home, owner=RIVAL), Ship(2, "troop_transport", home, owner=RIVAL),
                      Ship(3, "frigate", 0)]
        game.next_ship_id = 4
        self.assertFalse(game.within_fuel_range(0, RIVAL))
        military_orders(game)
        self.assertTrue(all(not s.has_course for s in game.ships))
        game.ships[0].system_id = 0
        game.start_combat(0)
        destination = retreat_destination(game)
        self.assertIsNotNone(destination)
        self.assertTrue(game.within_fuel_range(destination.id))
        self.assertNotEqual(destination.id, 0)


class TravelSaveTests(unittest.TestCase):
    def test_v14_fast_and_pending_voyages_keep_eta_and_can_be_cancelled_or_resumed(self):
        from scenarios import migrated_statistics
        for pending in (False, True):
            game = new_game(seed=2408, with_ai=False, with_guardians=False)
            destination = max(game.systems, key=lambda s: game.supply_distance(s.id)).id
            ship = game.ship_at(1)
            ship.destination = destination
            ship.travel_total = travel_turns(game.systems[0], game.systems[destination], cruise_speed=LEGACY_SHIP_SPEED)
            ship.turns_remaining = ship.travel_total if pending else ship.travel_total-1
            ship.departure_pending = pending
            ship.cruise_speed = LEGACY_SHIP_SPEED
            legacy_economy(game)
            with tempfile.TemporaryDirectory() as folder:
                storage = Storage(folder)
                path = storage.save(game)
                payload = json.loads(path.read_text())
                payload["version"] = 14
                legacy_research_payload(payload)
                for record in payload["game"]["ships"]:
                    record.pop("cruise_speed")
                path.write_text(json.dumps(payload))
                original = path.read_bytes()
                restored, _ = storage.load(path)
                self.assertEqual(restored, migrated_statistics(game))
                self.assertEqual(path.read_bytes(), original)
                self.assertEqual(storage.load(storage.save(restored))[0], restored)
                if pending:
                    cancelled = GameState.from_dict(restored.to_dict())
                    cancelled.cancel_departures([1])
                    self.assertEqual(cancelled.ship_at(1).cruise_speed, SHIP_SPEED)
                    self.assertFalse(cancelled.ship_at(1).has_course)
                remaining = restored.ship_at(1).turns_remaining
                for _ in range(remaining):
                    restored.advance_turn()
                self.assertEqual(restored.ship_at(1).system_id, destination)
                self.assertEqual(restored.ship_at(1).cruise_speed, SHIP_SPEED)

    def test_new_speed_snapshot_round_trips_and_rejects_invalid_values(self):
        game = new_game(seed=2408, with_ai=False)
        place_near(game, 1)
        game.send_ships([1, 3], 1)
        game.advance_turn()
        resumed = GameState.from_dict(game.to_dict())
        self.assertEqual(resumed, game)
        for value in (None, True, 0, -.02, .05, float("nan"), "0.02"):
            data = game.to_dict()
            data["ships"][0]["cruise_speed"] = value
            with self.assertRaises(SaveError):
                GameState.from_dict(data)
        data = game.to_dict()
        data["ships"][0].pop("cruise_speed")
        with self.assertRaises(SaveError):
            GameState.from_dict(data)


class FuelInterfaceTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.tmp.name), capture=True)
        self.addCleanup(self.app.audio.close)
        self.app.game = new_game(seed=2408, with_ai=False)
        use_nearby_system(self.app.game, 11)
        self.app.go("galaxy")
        self.app.render()
        self.app.present()

    def click(self, key):
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        x, y = button.rect.center
        v = self.app.viewport
        pos = (round(v.x+x*v.w/1440), round(v.y+y*v.h/900))
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, button=1, pos=pos))
            self.app.render()

    def test_popup_blocks_remote_orders_then_allows_nearby_course_and_cancellation(self):
        app, game = self.app, self.app.game
        far = next(s for s in game.systems if not game.within_fuel_range(s.id))
        self.click("map_fleet_1")
        self.click("fleet_select_2")
        self.click("fleet_select_3")
        before = game.to_dict()
        self.click(f"star_{far.id}")
        self.assertEqual(game.to_dict(), before)
        self.assertTrue(app.fleet_popup)
        self.assertEqual(app.fleet_selected_ids, {1})
        from orion.ui import text
        app.keyboard_mode = True
        game.selected_system = far.id
        with patch("orion.galaxy_fleet_view.text", wraps=text) as drawn:
            app.render()
        labels = " ".join(str(call.args[1]) for call in drawn.call_args_list)
        self.assertIn("Out of range", labels)
        self.assertIn("7 ly", labels)
        self.click("star_11")
        self.assertEqual(game.ship_at(1).turns_remaining, 4)
        self.click("star_0")
        self.click("end_turn")
        self.assertFalse(game.ship_at(1).has_course)
        self.assertEqual(game.ship_at(1).system_id, 0)

    def test_individual_course_button_disables_unreachable_destination(self):
        app, game = self.app, self.app.game
        far = next(s.id for s in game.systems if not game.within_fuel_range(s.id))
        app.plot_course(1)
        app.select_star(far)
        app.render()
        button = next(b for b in app.buttons if b.key == "send_course")
        self.assertFalse(button.enabled)
        self.assertEqual(button.label, "Out of fuel range")
        before = game.to_dict()
        self.click("send_course")
        self.assertEqual(game.to_dict(), before)
        app.select_star(11)
        app.render()
        button = next(b for b in app.buttons if b.key == "send_course")
        self.assertTrue(button.enabled)
        self.assertIn("4 turns", button.label)

    def test_reclicking_an_old_queued_course_keeps_its_actual_eta_until_redirected(self):
        game = self.app.game
        ship = game.ship_at(1)
        destination = max(game.systems, key=lambda s: game.supply_distance(s.id)).id
        ship.destination = destination
        ship.cruise_speed = LEGACY_SHIP_SPEED
        ship.turns_remaining = ship.travel_total = travel_turns(game.systems[0], game.systems[destination], cruise_speed=LEGACY_SHIP_SPEED)
        ship.departure_pending = True
        self.click("map_fleet_1")
        before = ship.__dict__.copy()
        self.click(f"star_{destination}")
        self.assertEqual(ship.__dict__, before)
        from orion.ui import text
        with patch("orion.galaxy_fleet_view.text", wraps=text) as drawn:
            self.app.render()
        labels = " ".join(str(call.args[1]) for call in drawn.call_args_list)
        self.assertIn(f"{ship.turns_remaining} turns", labels)
        self.assertIn("Saved course kept", labels)
        self.click("star_11")
        self.assertEqual(ship.turns_remaining, 4)
        self.assertEqual(ship.cruise_speed, SHIP_SPEED)


if __name__ == "__main__":
    unittest.main()
