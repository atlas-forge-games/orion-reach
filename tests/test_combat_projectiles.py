"""Travel, defense timing, deterministic saves and real starting separation."""

import copy
import math
import unittest
from unittest.mock import patch

from orion import combat, combat_projectiles as ordnance
from orion.model import GameState, SaveError
from test_arsenal import duel
from scenarios import place_near
from test_combat import encounter
from test_fleet_support import arena, unit


def cycle(game):
    combat.end_turn(game)
    combat.end_turn(game, "rival")


class ProjectileTests(unittest.TestCase):
    def test_fleets_start_outside_weapon_range_on_a_wider_board(self):
        game = encounter(close=False)
        a, b = game.combat.ships
        self.assertEqual((a.position, b.position), ((3, 6), (20, 6)))
        self.assertEqual(math.dist(a.position, b.position), 17)
        self.assertFalse(combat.in_range(a, b))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_three_round_flight_and_reload_are_identical_to_uninterrupted_play(self):
        game = duel(['torpedo']); game.combat.ship(2).x = 13
        before = game.combat.ship(2).hull
        self.assertEqual(game.combat_fire(1, 2), 0)
        self.assertEqual(game.combat.shots_fired, 1)
        loaded = GameState.from_dict(game.to_dict())
        for tick in range(1, 4):
            cycle(game); cycle(loaded)
            self.assertEqual(game, loaded)
            self.assertEqual(game.combat.ship(2).hull, before if tick < 3 else before-10)
            self.assertEqual(len(game.combat.projectiles), int(tick < 3))
            loaded = GameState.from_dict(loaded.to_dict())
        self.assertEqual(game.combat.shots_fired, 1)

    def test_mixed_volley_damages_with_beams_then_with_torpedoes(self):
        game = duel(['laser', 'torpedo'])
        before = game.combat.ship(2).hull
        self.assertEqual(game.combat_fire(1, 2), 5)
        self.assertEqual(game.combat.ship(2).hull, before-5)
        cycle(game)
        self.assertEqual(game.combat.ship(2).hull, before-15)
        self.assertEqual(game.combat.shots_fired, 2)

    def test_each_owner_gets_a_response_turn_and_flights_home_on_current_positions(self):
        game = duel(['torpedo'], ['torpedo'])
        a, b = game.combat.ships; b.x = 12
        game.combat_fire(1, 2)
        game.combat_end_turn()
        self.assertEqual(game.combat.projectiles[0].position, a.position)
        game.combat_move(2, 12, 5, 'rival')
        game.combat_fire(2, 1, 'rival')
        game.combat_end_turn('rival')
        first, second = game.combat.projectiles
        self.assertAlmostEqual(math.dist(first.position, a.position), ordnance.SPEED)
        self.assertGreater(first.y, 4)
        self.assertEqual((first.age, second.age), (1, 0))
        game.combat_end_turn()
        self.assertEqual((first.age, second.age), (1, 1))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_shields_and_escorts_are_evaluated_at_arrival(self):
        attacker = unit(1, 'destroyer', pos=(7, 4), modules=('torpedo',))
        target = unit(2, 'battleship', 'rival', (9, 4))
        escort = unit(3, 'destroyer', 'rival', (17, 4))
        game = arena(attacker, target, escort); game.combat.accuracy = False
        before = target.hull
        combat.fire(game, 1, 2)
        escort.x = 10  # A screen moves into position after the launch.
        cycle(game)
        self.assertEqual(before-target.hull, 8)
        self.assertIn('Escort screen', game.combat.log[-1])
        game = duel(['torpedo'], ['laser', 'shield'])
        target = game.combat.ship(2); before = target.hull
        game.combat_fire(1, 2)
        target.shields = 0  # Another volley stripped the shield before arrival.
        cycle(game)
        self.assertEqual(before-target.hull, 10)

    def test_aim_is_locked_at_launch_and_mirv_warheads_survive_reload(self):
        game = duel(['mirv']); game.combat.accuracy = True
        with patch('orion.combat.accuracy_breakdown', return_value={'chance': 0}):
            game.combat_fire(1, 2)
        self.assertEqual(len({s.id for s in game.combat.projectiles}), 3)
        loaded = GameState.from_dict(game.to_dict())
        with patch('orion.combat.accuracy_breakdown', return_value={'chance': 100}):
            cycle(game); cycle(loaded)
        self.assertEqual(game, loaded)
        self.assertEqual(game.combat.ship(2).hull, game.combat.ship(2).initial_hull)
        self.assertFalse(game.combat.projectiles)

    def test_destroyed_launcher_does_not_cancel_its_flight_but_dead_target_does(self):
        attacker = unit(1, 'destroyer', pos=(7, 4), modules=('torpedo',))
        friend = unit(2, pos=(6, 5))
        target = unit(3, 'battleship', 'rival', (9, 4))
        game = arena(attacker, friend, target); game.combat.accuracy = False
        combat.fire(game, 1, 3); attacker.hull = 0
        combat.check_losses(game)
        self.assertEqual(len(game.combat.projectiles), 1)
        before = target.hull; cycle(game)
        self.assertLess(target.hull, before)
        game = duel(['torpedo'])
        game.combat_fire(1, 2); game.combat.ship(2).hull = 0
        combat.check_losses(game)
        self.assertEqual(game.combat.status, 'player_victory')
        self.assertFalse(game.combat.projectiles)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_fuel_expires_after_six_flight_steps(self):
        attacker = unit(1, 'destroyer', pos=(5, 4), modules=('torpedo',))
        target = unit(2, 'scout', 'rival', (13, 4))
        game = arena(attacker, target); game.combat.accuracy = False
        combat.fire(game, 1, 2)
        for point in ((18, 4), (23, 7), (23, 12), (18, 12), (13, 12), (8, 12)):
            combat.end_turn(game)
            combat.move(game, 2, *point, "rival")
            combat.end_turn(game, "rival")
        self.assertEqual(target.hull, target.initial_hull)
        self.assertFalse(game.combat.projectiles)
        self.assertIn('ran out of fuel', game.combat.log[-1])

    def test_retreat_discards_flights(self):
        game = duel(['torpedo']); game.combat_fire(1, 2)
        place_near(game, 1)
        game.combat_retreat()
        self.assertFalse(game.combat.projectiles)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_legacy_battle_preserves_coordinates_and_has_no_invented_flights(self):
        game = encounter()
        raw = game.to_dict(); raw['combat'].pop('projectiles')
        loaded = GameState.from_dict(raw, version=51)
        self.assertEqual([s.position for s in loaded.combat.ships], [(4, 4), (13, 4)])
        self.assertEqual(loaded, game)

    def test_malformed_flight_saves_are_rejected(self):
        game = duel(['torpedo']); game.combat_fire(1, 2)
        original = game.to_dict()
        for field, value in [('owner', 'rival'), ('source_id', True), ('target_id', 1),
                             ('weapon', 'laser'), ('strength', 999), ('chance', 101),
                             ('age', 6), ('roll', -1), ('x', float('nan')),
                             ('x', 10**400), ('y', -1), ('id', 1)]:
            with self.subTest(field=field, value=str(value)[:20]):
                raw = copy.deepcopy(original); raw['combat']['projectiles'][0][field] = value
                with self.assertRaises(SaveError):
                    GameState.from_dict(raw)
        raw = copy.deepcopy(original)
        raw['combat']['shots_fired'] = 2
        raw['combat']['projectiles'] *= 2
        with self.assertRaises(SaveError):
            GameState.from_dict(raw)


if __name__ == '__main__':
    unittest.main()
