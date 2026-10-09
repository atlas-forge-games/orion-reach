"""Real campaign starts and reversible orders before the strategic turn advances."""

from collections import Counter
import json
from pathlib import Path
import tempfile
import unittest

from orion.exploration import refresh
from orion.fleets import fleet_containing
from orion.model import GameState, PLAYER, RIVAL, RuleError, SaveError, Ship
from scenarios import fixed_start_game as new_game, use_nearby_system
from orion.races import RACES
from orion.storage import SAVE_VERSION, Storage


class StartingFleetTests(unittest.TestCase):
    def test_every_race_starts_with_two_scouts_and_one_colony_ship_at_home(self):
        for race in RACES:
            for fog in (True, False):
                with self.subTest(race=race, fog=fog):
                    game = new_game(seed=2408, race_id=race, fog_of_war=fog)
                    for owner, home in ((PLAYER, 0), (RIVAL, game.opponent.home_system)):
                        ships = game.ships_owned_by(owner)
                        self.assertEqual(Counter(s.kind for s in ships), {"scout": 2, "colony_ship": 1})
                        self.assertTrue(all(s.system_id == home and not s.has_course and s.hull == s.max_hull for s in ships))
                        self.assertEqual(game.treasury_for(owner), 120)
                    self.assertEqual([s.id for s in game.ships], list(range(1, 7)))
                    self.assertEqual(game.next_ship_id, 7)
                    self.assertTrue(all(not p.construction_queue for s in game.systems for p in s.worlds))
                    self.assertEqual(GameState.from_dict(game.to_dict()), game)
                    if fog:
                        self.assertEqual([s.id for s in game.systems if game.system_visible(s.id)], [0])
                        self.assertEqual([s.owner for s in game.visible_ships()], [PLAYER]*3)

    def test_solo_start_and_adding_a_rival_create_each_fleet_only_once(self):
        game = new_game(seed=2408, with_ai=False)
        self.assertEqual(len(game.ships), 3)
        game.add_opponent()
        self.assertEqual(len(game.ships), 6)
        before = game.to_dict()
        with self.assertRaises(RuleError):
            game.add_opponent()
        self.assertEqual(game.to_dict(), before)
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            for _ in range(3):
                game = storage.load(storage.save(game))[0]
                self.assertEqual(game.to_dict(), before)

    def test_starting_colony_ship_can_settle_immediately_and_ai_uses_its_scouts(self):
        game = new_game(seed=172)  # Naturally has two reachable rival destinations.
        game.colonize(3, 0, 3)
        self.assertEqual(game.planet_at(0, 3).owner, PLAYER)
        self.assertEqual([s.kind for s in game.ships_owned_by()], ["scout", "scout"])
        home = game.opponent.home_system
        scouts = [s.id for s in game.ships_owned_by(RIVAL) if s.kind == "scout"]
        game.advance_turn()
        explorers = [game.ship_at(i, owner=RIVAL) for i in scouts]
        self.assertTrue(all(s.system_id != home or s.has_course for s in explorers))
        self.assertEqual(len({s.destination if s.has_course else s.system_id for s in explorers}), 2)
        self.assertTrue(any(p.owner == RIVAL and (s.id, p.id) != (home, game.opponent.home_planet)
                            for s in game.systems for p in s.worlds)
                        or any(s.kind == "colony_ship" and s.has_course for s in game.ships_owned_by(RIVAL)))
        self.assertEqual(len({s.id for s in game.ships}), len(game.ships))


class PendingDepartureTests(unittest.TestCase):
    def setUp(self):
        self.game = new_game(seed=2408, with_ai=False, with_guardians=False)
        use_nearby_system(self.game, 1)
        self.target = max((s for s in self.game.systems[1:] if self.game.within_fuel_range(s.id)),
                          key=lambda s: self.game.travel_turns(self.game.systems[0], s)).id

    def test_selection_can_be_redirected_and_cancelled_without_advancing_time(self):
        game = self.game
        original = game.to_dict()
        duration = game.send_ships([1, 3], self.target)
        self.assertGreater(duration, 1)
        self.assertEqual([s.id for s in game.fleet_at(0)], [1, 2, 3])
        self.assertTrue(all(game.ship_at(i).departure_pending and not game.ship_at(i).in_transit for i in (1, 3)))
        game.send_ships([1, 3], 1)
        self.assertTrue(all(game.ship_at(i).destination == 1 for i in (1, 3)))
        self.assertEqual(game.cancel_departures([1, 3]), 2)
        self.assertEqual(game.to_dict(), original)
        game.advance_turn()
        self.assertTrue(all(s.system_id == 0 and not s.has_course for s in game.ships))

    def test_cancel_subset_merges_it_into_orbit_and_only_other_ships_depart(self):
        game = self.game
        duration = game.send_ships([1, 2], self.target)
        game.cancel_departures([1])
        self.assertEqual([s.id for s in fleet_containing(game.ships, 1)], [1, 3])
        self.assertEqual([s.id for s in fleet_containing(game.ships, 2)], [2])
        game.advance_turn()
        self.assertEqual([s.id for s in game.fleet_at(0)], [1, 3])
        self.assertTrue(game.ship_at(2).in_transit)
        self.assertFalse(game.ship_at(2).departure_pending)
        self.assertEqual(game.ship_at(2).turns_remaining, duration-1)

    def test_cancellation_and_redirection_are_locked_after_the_first_travel_step(self):
        game = self.game
        game.send_ship(1, self.target)
        game.advance_turn()
        for action in (lambda: game.cancel_departures([1]), lambda: game.send_ship(1, 0),
                       lambda: game.send_ship(1, 1)):
            before = game.to_dict()
            with self.assertRaises(RuleError):
                action()
            self.assertEqual(game.to_dict(), before)

    def test_even_one_turn_routes_can_be_cancelled_before_departure(self):
        game = self.game
        from scenarios import place_near
        target = place_near(game, 1, distance=1).id  # Artificially close systems exercise the one-turn boundary.
        self.assertEqual(game.send_ship(1, target), 1)
        game.cancel_departures([1])
        self.assertFalse(game.ship_at(1).has_course)
        game.send_ship(1, target)
        game.advance_turn()
        self.assertEqual(game.ship_at(1).system_id, target)
        self.assertFalse(game.ship_at(1).has_course or game.ship_at(1).departure_pending)

    def test_invalid_members_never_cancel_part_of_the_selection(self):
        game = self.game
        game.send_ships([1, 2], self.target)
        for ids, owner in (([], PLAYER), ([1, 99], PLAYER), ([1, 1], PLAYER), ([1, True], PLAYER),
                           ([1, 3], PLAYER), ([1], RIVAL), ([1], "unknown")):
            before = game.to_dict()
            with self.assertRaises(RuleError):
                game.cancel_departures(ids, owner=owner)
            self.assertEqual(game.to_dict(), before)
        game.ship_at(2).departure_pending = False  # A committed/legacy voyage at zero progress.
        before = game.to_dict()
        with self.assertRaises(RuleError):
            game.cancel_departures([1, 2])
        self.assertEqual(game.to_dict(), before)

    def test_save_load_retains_cancellation_until_end_turn(self):
        game = self.game
        game.send_ships([1, 3], self.target)
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            restored, _ = storage.load(storage.save(game))
            self.assertEqual(restored, game)
            restored.cancel_departures([3])
            resumed, _ = storage.load(storage.save(restored))
            resumed.advance_turn()
            restored.advance_turn()
            self.assertEqual(resumed, restored)
            self.assertEqual(resumed.ship_at(3).system_id, 0)
            self.assertFalse(resumed.ship_at(3).has_course)
            self.assertTrue(resumed.ship_at(1).in_transit)

    def test_v13_saves_keep_existing_fleets_and_committed_journeys_without_gifts(self):
        game = new_game(seed=2408, with_ai=False, with_guardians=False)
        use_nearby_system(game, self.target)
        game.ships = [Ship(41, "frigate", 0, hull=13)]
        game.next_ship_id = 42
        game.send_ship(41, self.target)
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            path = storage.save(game)
            payload = json.loads(path.read_text())
            payload["version"] = 13
            for ship in payload["game"]["ships"]:
                ship.pop("departure_pending")
            path.write_text(json.dumps(payload))
            before = path.read_bytes()
            restored, _ = storage.load(path)
            self.assertEqual([(s.id, s.hull) for s in restored.ships], [(41, 13)])
            self.assertEqual(restored.next_ship_id, 42)
            self.assertFalse(restored.ship_at(41).departure_pending)
            self.assertTrue(restored.ship_at(41).in_transit)
            with self.assertRaises(RuleError):
                restored.cancel_departures([41])
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(storage.load(storage.save(restored))[0], restored)
            self.assertEqual(SAVE_VERSION, 21)

    def test_pending_flag_is_strictly_validated(self):
        game = self.game
        game.send_ship(1, self.target)
        for change in (lambda s: s.update(departure_pending=1), lambda s: s.update(departure_pending=None),
                       lambda s: s.update(turns_remaining=s["travel_total"]-1),
                       lambda s: s.pop("departure_pending")):
            data = game.to_dict()
            change(data["ships"][0])
            with self.assertRaises(SaveError):
                GameState.from_dict(data)
        data = game.to_dict()
        data["ships"][1]["departure_pending"] = True
        with self.assertRaises(SaveError):
            GameState.from_dict(data)

    def test_pending_scout_keeps_visibility_until_the_turn_begins(self):
        game = self.game
        scout = game.ship_at(1)
        scout.system_id = self.target
        refresh(game)
        self.assertTrue(game.system_visible(self.target))
        game.send_ship(1, 0)
        self.assertTrue(game.system_visible(self.target))
        game.cancel_departures([1])
        self.assertTrue(game.system_visible(self.target))
        game.send_ship(1, 0)
        game.advance_turn()
        self.assertFalse(game.system_visible(self.target))
        self.assertIsNotNone(game.known_system(self.target))

    def test_hostile_encounter_cancels_pending_orders_and_retreat_cannot_be_revoked(self):
        game = new_game(seed=2408)
        use_nearby_system(game, self.target)
        game.ships.append(Ship(7, "frigate", 0, owner=RIVAL))
        game.next_ship_id = 8
        game.diplomacy.relations = -100
        game.send_ships([1, 2, 3], self.target)
        game.advance_turn()
        self.assertEqual(game.turn, 1)
        self.assertEqual(game.combat.status, "active")
        self.assertTrue(all(not s.has_course for s in game.ships_owned_by()))
        before = game.to_dict()
        with self.assertRaisesRegex(RuleError, "battle"):
            game.cancel_departures([1])
        self.assertEqual(game.to_dict(), before)
        game.combat_end_turn(RIVAL)
        game.combat_retreat()
        self.assertTrue(all(s.in_transit and not s.departure_pending for s in game.ships_owned_by()))
        data = game.to_dict()
        data["ships"][0]["departure_pending"] = True
        with self.assertRaises(SaveError):
            GameState.from_dict(data)
        game.finish_combat()
        with self.assertRaises(RuleError):
            game.cancel_departures([1, 2, 3])


if __name__ == "__main__":
    unittest.main()
