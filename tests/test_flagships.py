"""Flagship selection, live command coverage, deployment and save continuity."""

from copy import deepcopy
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from orion import combat, flagships, fleet_support, combat_camera
from orion.combat_effects import CombatAnimation
from orion.combat_sandbox import FleetSetup, Scenario, build_game
from orion.combat_simulator import CombatSimulator
from orion.combat_view import draw_flagship_auras
from orion.model import GameState
from test_combat import encounter
from test_fleet_support import arena, unit

import pygame as pg


class FlagshipTests(unittest.TestCase):
    def test_strongest_ship_commands_each_fleet_and_rating_ignores_current_condition(self):
        game = encounter(own=('frigate', 'destroyer', 'titan', 'carrier'),
                         enemy=('frigate', 'battleship'), close=False)
        battle = game.combat
        leader = flagships.select(battle, 'player')
        self.assertEqual((leader.id, flagships.select(battle, 'rival').id), (3, 6))
        leader.hull = 1
        leader.shields = 0
        leader.cooldowns[leader.weapon] = 2
        battle.acted.append(leader.id); battle.moved.append(leader.id)
        self.assertIs(flagships.select(battle, 'player'), leader)
        leader.cooldowns.clear()
        leader.hull = 0
        successor = flagships.select(battle, 'player')
        self.assertIsNotNone(successor)
        self.assertNotEqual(successor.id, leader.id)
        self.assertEqual(flagships.select(GameState.from_dict(game.to_dict()).combat, 'player').id,
                         successor.id)

    def test_loadout_carrier_capacity_and_deterministic_ties_affect_selection(self):
        light = unit(1, 'destroyer', modules=('laser',))
        armed = unit(2, 'destroyer', modules=('torpedo', 'torpedo'))
        battle = arena(light, armed).combat
        self.assertIs(flagships.select(battle, 'player'), armed)
        carrier = unit(3, 'carrier', modules=('drone_bay',))
        battle.ships = [carrier, unit(4)]
        self.assertIs(flagships.select(battle, 'player'), carrier)
        carrier.launched_drones = 4
        self.assertIs(flagships.select(battle, 'player'), carrier)
        first, second = unit(8), unit(9)
        battle.ships = [second, first]
        self.assertIs(flagships.select(battle, 'player'), first)

    def test_civilian_convoys_have_a_leader_but_bases_drones_and_monsters_do_not(self):
        game = encounter(own=('frigate',), enemy=('colony_ship', 'outpost_ship'), close=False)
        self.assertIsNotNone(flagships.select(game.combat, 'rival'))
        for kind in ('missile_base', 'combat_drone', next(iter(combat.MONSTERS))):
            battle = arena(unit(1, kind)).combat
            self.assertIsNone(flagships.select(battle, 'player'))
        battle = arena(unit(1), unit(2, 'missile_base'), unit(3, 'combat_drone')).combat
        self.assertEqual(flagships.select(battle, 'player').id, 1)
        for ship in battle.ships:
            self.assertIsNone(flagships.source(battle, ship))

    def test_flagship_starts_at_the_centre_for_small_and_multi_column_fleets(self):
        for count in (1, 7, 15, 45, 81):
            with self.subTest(count=count):
                fleet = ('frigate',)*(count-1)+('titan',)
                battle = encounter(own=fleet, enemy=fleet, close=False).combat
                self.assertEqual(len({s.position for s in battle.ships}), count*2)
                for side in battle.sides:
                    leader = flagships.select(battle, side)
                    ships = battle.fleet(side)
                    centre = ((min(s.x for s in ships)+max(s.x for s in ships))/2,
                              (battle.rows-1)/2)
                    self.assertLessEqual(math.dist(leader.position, centre), .71)
                    self.assertTrue(all(0 <= s.x < combat.BOARD_COLUMNS and 0 <= s.y < battle.rows
                                        for s in ships))

    def test_planets_keep_their_defensive_line_when_flagships_deploy(self):
        game = build_game(Scenario(player=FleetSetup(ships={'frigate': 6, 'titan': 1}, bases=3),
                                   rival=FleetSetup(ships={'destroyer': 2}, bases=2)))
        battle = game.combat
        self.assertEqual(len({s.position for s in battle.ships}), len(battle.ships))
        for side, x in (('player', 8), ('rival', 15)):
            self.assertTrue(all(s.x == x for s in battle.fleet(side) if s.kind == 'missile_base'))
            self.assertEqual(flagships.select(battle, side).y, 6)

    def test_hull_radius_uses_euclidean_distance_and_excludes_self_and_enemies(self):
        for kind, radius in (('frigate', 2), ('destroyer', 3), ('cruiser', 4),
                             ('carrier', 5), ('battleship', 6), ('titan', 8)):
            with self.subTest(kind=kind):
                leader = unit(1, kind, pos=(5, 4))
                ally = unit(2, pos=(5+radius, 4))
                enemy = unit(3, owner='rival', pos=(6, 4))
                battle = arena(leader, ally, enemy).combat
                self.assertIs(flagships.source(battle, ally), leader)
                self.assertIsNone(flagships.source(battle, leader))
                self.assertIsNone(flagships.source(battle, enemy))
                ally.y += 1
                self.assertIsNone(flagships.source(battle, ally))

    def test_real_moves_and_casualties_change_bonuses_without_spending_extra_actions(self):
        leader = unit(1, 'destroyer', pos=(5, 4))
        ally = unit(2, pos=(8, 4))
        game = arena(leader, ally, unit(3, owner='rival', pos=(15, 4)))
        self.assertEqual((fleet_support.command_accuracy(game.combat, ally),
                          flagships.evasion(game.combat, ally)), (8, 5))
        combat.move(game, 1, 4, 4)
        self.assertEqual((fleet_support.command_accuracy(game.combat, ally),
                          flagships.evasion(game.combat, ally)), (0, 0))
        self.assertEqual((game.combat.moved, game.combat.acted), ([1], []))
        leader.hull = 0
        self.assertIs(flagships.select(game.combat, 'player'), ally)
        self.assertIsNone(flagships.source(game.combat, ally))

    def test_promotion_can_reduce_coverage_and_does_not_redeploy_survivors(self):
        leader, successor, ally = unit(1, 'titan'), unit(2, 'destroyer', pos=(6, 4)), unit(3, pos=(11, 4))
        battle = arena(leader, successor, ally).combat
        self.assertEqual(flagships.evasion(battle, ally), 5)
        positions = [s.position for s in battle.ships]
        leader.hull = 0
        self.assertIs(flagships.select(battle, 'player'), successor)
        self.assertEqual(flagships.evasion(battle, ally), 0)
        self.assertEqual([s.position for s in battle.ships], positions)

    def test_accuracy_and_evasion_reach_actual_forecasts_without_stacking_command(self):
        leader, ally = unit(1, 'titan', pos=(2, 4)), unit(2, pos=(7, 4))
        target = unit(3, owner='rival', pos=(10, 4))
        enemy_leader = unit(4, 'battleship', 'rival', (12, 4))
        game = arena(leader, ally, target, enemy_leader)
        values = combat.accuracy_breakdown(game, ally, target, 'laser')
        self.assertEqual((values['command'], values['formation'], values['chance']), (8, 5, 75))
        self.assertAlmostEqual(combat.expected_volley(game, ally, target), ally.damage*.75)
        leader.x = 4  # Inside the fitted flag bridge: +12 wins over innate +8.
        self.assertEqual(combat.accuracy_breakdown(game, ally, target, 'laser')['command'], 12)
        game.combat.accuracy = False
        values = combat.accuracy_breakdown(game, ally, target, 'laser')
        self.assertEqual((values['command'], values['formation'], values['chance']), (0, 0, 100))
        self.assertEqual(combat.expected_volley(game, ally, target), ally.damage)

    def test_projectile_command_rolls_remain_locked_across_promotion_and_reload(self):
        game = encounter(own=('frigate', 'titan', 'destroyer'),
                         enemy=('frigate', 'battleship'), close=False)
        battle = game.combat
        for ship, position in zip(battle.ships, ((0, 6), (1, 6), (3, 6), (11, 6), (13, 6))):
            ship.x, ship.y = position
        expected = combat.accuracy_breakdown(game, battle.ship(3), battle.ship(4), 'torpedo')['chance']
        game.combat_fire(3, 4)
        self.assertEqual(battle.projectiles[0].chance, expected)
        battle.ship(2).hull = 0
        combat.check_losses(game)
        loaded = GameState.from_dict(game.to_dict())
        self.assertEqual(loaded.combat.projectiles[0].chance, expected)
        for _ in range(2):
            for current in (game, loaded):
                current.combat_end_turn(); current.combat_end_turn('rival')
            self.assertEqual(game, loaded)

    def test_legacy_positions_and_manual_orders_are_preserved(self):
        game = encounter(own=('frigate', 'titan'), close=True)
        original = deepcopy(game.to_dict())
        restored = GameState.from_dict(original)
        self.assertEqual(restored.to_dict(), original)
        self.assertEqual(flagships.select(restored.combat, 'player').id, 2)
        restored.combat_move(1, 7, 4)
        self.assertEqual(restored.combat.moved, [1])
        self.assertEqual(restored.combat.acted, [])


class FlagshipViewTests(unittest.TestCase):
    def test_zoomed_aura_follows_moving_flagship_and_inspector_is_read_only(self):
        with tempfile.TemporaryDirectory() as folder:
            app = CombatSimulator(Path(folder), capture=True)
            try:
                app.game = encounter(own=('frigate', 'titan'), enemy=('frigate', 'destroyer'), close=False)
                app.go('combat')
                battle = app.game.combat
                leader = flagships.select(battle, 'player')
                app.combat_ship_id = leader.id
                app.combat_animation = CombatAnimation('move', leader.id, (leader.position, (4, 6)), elapsed=.14)
                before = app.game.to_dict()
                for zoom in (.5, 1, 3):
                    app.combat_zoom = zoom
                    combat_camera.clamp(app)
                    camera = combat_camera.view(app)
                    with patch('orion.combat_view.pg.draw.circle', wraps=pg.draw.circle) as draw:
                        ids = draw_flagship_auras(app, battle, camera)
                    self.assertEqual(ids, {2, 4})
                    cx, cy = camera.project(app.combat_animation.moving_position())
                    self.assertTrue(any(call.args[2] == (cx-combat_camera.BOARD.x, cy-combat_camera.BOARD.y)
                                        and call.args[3] == round(8*camera.cell_size) for call in draw.call_args_list))
                    app.render()
                    self.assertEqual(app.game.to_dict(), before)
                app.combat_animation = None
                app.dialog = {'combat_ship_info': leader.id}
                with patch('orion.combat_inspector.text') as label:
                    app.render()
                self.assertTrue(any('FLAGSHIP' in str(call.args[1]) and '8-cell' in str(call.args[1])
                                    for call in label.call_args_list))
                self.assertEqual(app.game.to_dict(), before)
            finally:
                app.audio.close()
                pg.quit()


if __name__ == '__main__':
    unittest.main()
