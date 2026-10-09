"""Movement, beam technology, tactical saves and time-driven battle effects."""

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

from orion.combat import BEAMS, ai_action, in_range, reachable
from orion.combat_view import BOARD, cell_center
from orion.model import GameState, PLAYER, RIVAL, RuleError, SaveError
from orion.storage import SAVE_VERSION, Storage
from test_combat import encounter


class TacticalRulesTests(unittest.TestCase):
    def test_deployment_is_unique_and_large_fleets_extend_the_map(self):
        game = encounter(own=("frigate",)*45, enemy=("scout",)*81)
        battle = game.combat
        self.assertEqual(battle.rows, 21)
        self.assertEqual(len({s.position for s in battle.ships}), 126)
        self.assertTrue(all(0 <= s.x < 18 and 0 <= s.y < 21 for s in battle.ships))
        self.assertEqual((battle.ship(1).movement, battle.ship(46).movement), (3, 5))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_move_is_atomic_respects_obstacles_range_types_and_one_move_limit(self):
        game = encounter(own=("frigate", "scout"))
        ship, friend = game.combat.ship(1), game.combat.ship(2)
        for cell in (ship.position, friend.position, (8, 4), (-1, 4), (18, 4), (4, 10),
                     (True, 4), (7.0, 4), (7, None)):
            before = game.to_dict()
            with self.assertRaises(RuleError, msg=str(cell)):
                game.combat_move(1, *cell)
            self.assertEqual(game.to_dict(), before)
        path = game.combat_move(1, 7, 4)
        self.assertEqual((path[0], path[-1], len(path)), ((4, 4), (7, 4), 4))
        self.assertTrue(game.combat.can_fire(ship))
        with self.assertRaises(RuleError):
            game.combat_move(1, 8, 4)
        before = game.to_dict()
        with self.assertRaises(RuleError):
            game.combat_move(3, 12, 4, RIVAL)
        self.assertEqual(game.to_dict(), before)

    def test_paths_route_around_ships_and_do_not_cut_occupied_corners(self):
        game = encounter(own=("frigate", "colony_ship"))
        ship, block = game.combat.ship(1), game.combat.ship(2)
        block.x, block.y = 5, 4
        paths = reachable(game.combat, ship)
        self.assertNotIn((5, 4), paths)
        self.assertEqual(len(paths[(5, 5)]), 3)  # Cannot squeeze past the corner in one step.
        self.assertEqual(len(paths[(6, 3)]), 4)
        for path in paths.values():
            self.assertNotIn(block.position, path)
        block.hull = 0
        self.assertEqual(len(reachable(game.combat, ship)[(5, 4)]), 2)

    def test_fire_requires_range_and_allows_one_move_after_a_shot(self):
        game = encounter()
        before = game.to_dict()
        with self.assertRaisesRegex(RuleError, "range"):
            game.combat_fire(1, 2)
        self.assertEqual(game.to_dict(), before)
        game.combat.ship(2).x = 10  # Exactly six cells, including the boundary.
        self.assertEqual(game.combat_fire(1, 2), 5)
        self.assertEqual(game.combat.active_owner, PLAYER)
        game.combat_move(1, 5, 4)
        self.assertEqual(game.combat.ready(PLAYER), [])
        for action in (lambda: game.combat_fire(1, 2), lambda: game.combat_move(1, 6, 4),
                       lambda: game.combat_hold(1)):
            before = game.to_dict()
            with self.assertRaises(RuleError):
                action()
            self.assertEqual(game.to_dict(), before)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)  # Waiting for End Turn is valid.

    def test_side_turns_reset_both_orders_and_work_when_rival_initiates(self):
        game = encounter(start=False)
        game.start_combat(0, RIVAL)
        game.combat_move(2, 10, 4, RIVAL)
        game.combat_fire(2, 1, RIVAL)
        game.combat_end_turn(RIVAL)
        self.assertEqual((game.combat.round, game.combat.active_owner), (1, PLAYER))
        game.combat_fire(1, 2)
        game.combat_end_turn()
        self.assertEqual((game.combat.round, game.combat.active_owner), (2, RIVAL))
        self.assertEqual((game.combat.moved, game.combat.acted), ([], []))
        self.assertEqual(game.turn, 1)

    def test_quantum_optics_gives_both_empires_the_same_coloured_beam(self):
        game = encounter(own=("frigate", "scout"), start=False)
        game.technology.completed = ["research_instruments", "quantum_optics"]
        game.opponent.technology.completed = ["field_laboratories", "quantum_optics"]
        game.start_combat(0)
        for identifier in (1, 3):
            ship = game.combat.ship(identifier)
            self.assertEqual((ship.weapon, ship.damage, ship.weapon_range), ("quantum", 7, 7))
        self.assertNotEqual(BEAMS["laser"].color, BEAMS["quantum"].color)
        self.assertEqual(game.combat.ship(2).weapon, "none")
        game.combat_move(1, 6, 4)
        self.assertEqual(game.combat_fire(1, 3), 7)
        self.assertEqual(game.bonuses_for(PLAYER)["lab_research"], 5)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_ai_moves_and_fires_legally_and_resumes_deterministically(self):
        game = encounter(own=("frigate", "frigate", "scout"), enemy=("frigate", "frigate", "troop_transport"))
        restored = GameState.from_dict(game.to_dict())
        kinds = set()
        for _ in range(180):
            if game.combat.status != "active":
                break
            owner = game.combat.active_owner
            before = copy.deepcopy(game.combat)
            event = ai_action(game, owner)
            self.assertEqual(ai_action(restored, owner), event)
            self.assertEqual(restored, game)
            kinds.add(event["kind"])
            if event["kind"] == "fire":
                attacker, target = before.ship(event["ship_id"]), before.ship(event["target_id"])
                self.assertTrue(in_range(attacker, target))
                self.assertNotIn(attacker.id, before.acted)
            elif event["kind"] == "move":
                ship = before.ship(event["ship_id"])
                self.assertEqual(reachable(before, ship)[event["path"][-1]], event["path"])
            self.assertEqual(GameState.from_dict(game.to_dict()), game)
        self.assertNotEqual(game.combat.status, "active")
        self.assertTrue({"move", "fire", "end_turn"} <= kinds)

    def test_mid_move_and_mid_firing_turn_saves_keep_exact_remaining_orders(self):
        game = encounter()
        game.combat_move(1, 7, 4)
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            restored, _ = storage.load(storage.save(game))
            self.assertEqual(restored, game)
            with self.assertRaises(RuleError):
                restored.combat_move(1, 8, 4)
            game.combat_fire(1, 2)
            restored.combat_fire(1, 2)
            self.assertEqual(restored, game)
            resumed, _ = storage.load(storage.save(restored))
            with self.assertRaises(RuleError):
                resumed.combat_fire(1, 2)
            self.assertEqual(resumed.combat.ship(2).hull, 15)

    def test_v12_battle_migration_preserves_damage_actions_and_source_bytes(self):
        game = encounter(own=("frigate", "colony_ship"))
        game.combat_move(1, 7, 4)
        game.combat_fire(1, 3)
        game.combat_end_turn()
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            path = storage.save(game)
            data = json.loads(path.read_text())
            data["version"] = 12
            old = data["game"]["combat"]
            old.pop("moved")
            for ship in old["ships"]:
                for field in ("x", "y", "weapon", "design", "shields"):
                    ship.pop(field)
            path.write_text(json.dumps(data))
            original = path.read_bytes()
            restored, _ = storage.load(path)
            battle = restored.combat
            self.assertEqual((battle.ship(3).hull, battle.active_owner, battle.round), (15, RIVAL, 1))
            self.assertEqual((battle.acted, battle.moved), ([1], [1]))
            self.assertEqual((battle.ship(1).position, battle.ship(3).position), ((4, 4), (13, 4)))
            self.assertEqual(restored.ships, game.ships)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(storage.load(storage.save(restored))[0], restored)
        self.assertEqual(SAVE_VERSION, 24)

    def test_invalid_coordinates_weapons_or_action_flags_are_rejected(self):
        game = encounter()
        mutations = [lambda b: b["ships"][0].update(x=True), lambda b: b["ships"][0].update(y=-1),
                     lambda b: b["ships"][0].update(x=18), lambda b: b["ships"][0].update(y=10),
                     lambda b: b["ships"][0].update(x=13, y=4),
                     lambda b: b["ships"][0].update(weapon="quantum"),
                     lambda b: b["ships"][0].update(weapon="missile"),
                     lambda b: b["ships"][0].pop("x"), lambda b: b.update(moved=[1, 1]),
                     lambda b: b.update(moved=[0]), lambda b: b.update(moved=[True]),
                     lambda b: b.pop("moved")]
        for change in mutations:
            data = game.to_dict()
            change(data["combat"])
            with self.assertRaises(SaveError):
                GameState.from_dict(data)


class TacticalAnimationTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        self.temp = tempfile.TemporaryDirectory()
        self.app = App(Path(self.temp.name), capture=True)
        self.app.game = encounter()
        self.app.go("combat")
        self.app.window = pg.display.set_mode((980, 900), pg.RESIZABLE)
        self.app.present()
        self.app.render()

    def tearDown(self):
        pg.quit()
        self.temp.cleanup()

    def click(self, key):
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        self.assertTrue(button.enabled, key)
        x, y = button.rect.center
        v = self.app.viewport
        position = (round(v.x+x*v.w/1440), round(v.y+y*v.h/900))
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, button=1, pos=position))
            self.app.render()

    def tick(self, seconds):
        self.app.time += seconds
        self.app.update_combat()
        self.app.render()

    def test_click_move_interpolates_and_blocks_rapid_duplicate_commands(self):
        self.click("combat_cell_7_4")
        effect = self.app.combat_animation
        self.assertEqual(effect.kind, "move")
        self.assertEqual(effect.moving_position(), (4, 4))
        before = self.app.game.to_dict()
        self.app.move_combat_ship(8, 4)
        self.app.combat_action("end_turn")
        self.assertEqual(self.app.game.to_dict(), before)
        self.tick(effect.duration/2)
        self.assertEqual(effect.moving_position(), (5.5, 4))
        self.tick(effect.duration/2+.01)
        self.assertIsNone(self.app.combat_animation)
        self.click("combat_ship_2")
        self.assertEqual(self.app.game.combat.ship(2).hull, 15)
        self.assertEqual(self.app.combat_animation.kind, "fire")
        self.tick(.15)
        # The laser's red halo is visible between the ships, within the letterboxed canvas.
        a, b = cell_center((7, 4)), cell_center((13, 4))
        red = self.app.canvas.get_at(((a[0]+b[0])//2, a[1]+2))
        self.assertGreater(red.r, red.b*2)
        self.assertEqual(self.app.storage.load(self.app.storage.saves_dir/"autosave.json")[0], self.app.game)

    def test_last_ship_explodes_before_result_and_reload_never_repeats_damage(self):
        game = encounter(start=False)
        game.ships[1].hull = 5
        game.start_combat(0)
        self.app.game = game
        self.app.reset_combat_view()
        self.app.go("combat")
        self.click("combat_cell_7_4")
        self.tick(1)
        self.click("combat_ship_2")
        self.assertEqual(game.combat.status, "player_victory")
        self.assertTrue(self.app.combat_animation.destroyed)
        self.assertNotIn("combat_continue", [b.key for b in self.app.buttons])
        self.app.finish_combat()
        self.assertIsNotNone(game.combat)
        self.tick(.4)
        x, y = cell_center((13, 4))
        impact = self.app.canvas.get_at((x, y))
        self.assertGreater(impact.r, 100)
        self.assertNotIn("combat_ship_2", [b.key for b in self.app.buttons])
        state = game.to_dict()
        self.tick(1)
        self.assertIn("combat_continue", [b.key for b in self.app.buttons])
        self.assertEqual(game.to_dict(), state)
        save = self.app.storage.saves_dir/"autosave.json"
        self.app.load_game(save)
        self.assertIsNone(self.app.combat_animation)
        self.assertEqual(self.app.game.to_dict(), state)
        self.click("combat_continue")
        self.assertEqual(self.app.screen, "system")
        self.assertEqual([s.id for s in self.app.game.ships], [1])

    def test_animation_and_ai_freeze_in_pause_settings_and_dialogs(self):
        self.click("combat_cell_7_4")
        self.tick(.15)
        animation = self.app.combat_animation
        age = animation.elapsed
        state = self.app.game.to_dict()
        self.app.pause()
        self.tick(5)
        self.assertEqual(animation.elapsed, age)
        self.app.show_settings()
        self.tick(5)
        self.assertEqual(self.app.game.to_dict(), state)
        self.app.go("combat")
        self.app.quit_request()
        self.tick(5)
        self.assertEqual(animation.elapsed, age)
        self.app.cancel_dialog()
        self.tick(.1)
        self.assertAlmostEqual(animation.elapsed, age+.1)

    def test_enemy_moves_before_firing_and_player_ship_also_explodes(self):
        game = encounter(start=False)
        game.ships[0].hull = 5
        game.start_combat(0, RIVAL)
        self.app.game = game
        self.app.reset_combat_view()
        self.app.go("combat")
        self.tick(1)
        self.assertEqual(self.app.combat_animation.kind, "move")
        self.assertEqual(game.combat.ship(1).hull, 5)
        self.tick(1)
        self.tick(.4)
        self.assertEqual(game.combat.status, "rival_victory")
        self.assertEqual(self.app.combat_animation.target_id, 1)
        self.assertTrue(self.app.combat_animation.destroyed)
        self.assertNotIn("combat_continue", [b.key for b in self.app.buttons])
        self.tick(1.4)
        self.assertIn("combat_continue", [b.key for b in self.app.buttons])

    def test_large_fleets_can_be_selected_and_scrolled_without_losing_ships(self):
        self.app.game = encounter(own=("frigate",)*100, enemy=("frigate",)*100)
        self.app.reset_combat_view()
        self.app.go("combat")
        found = set()
        for _ in range(100):
            found.add(self.app.combat_ship_id)
            self.app.next_combat_ship()
            selected = self.app.game.combat.ship(self.app.combat_ship_id)
            self.assertTrue(self.app.combat_camera_row <= selected.y < self.app.combat_camera_row+10)
        self.assertEqual(found, set(range(1, 101)))
        before = self.app.game.to_dict()
        self.app.pan_combat(100)
        self.app.render()
        self.assertEqual(self.app.combat_camera_row, 15)
        self.assertTrue(all(BOARD.contains(b.rect) for b in self.app.buttons if b.key.startswith("combat_ship_")))
        self.app.handle_event(pg.event.Event(pg.MOUSEWHEEL, y=2, x=0))
        self.assertEqual(self.app.combat_camera_row, 11)
        self.assertEqual(self.app.game.to_dict(), before)

    def test_attack_camera_keeps_shooter_and_offscreen_target_visible(self):
        game = encounter(enemy=("frigate",)*81)
        game.combat.ship(1).x, game.combat.ship(1).y = 7, 5
        game.combat.ship(2).x, game.combat.ship(2).y = 7, 11
        self.app.game = game
        self.app.reset_combat_view()
        self.app.go("combat")
        self.assertEqual(self.app.combat_camera_row, 0)
        self.app.combat_action("fire")
        self.assertEqual(game.combat.ship(2).hull, 15)
        self.assertLessEqual(self.app.combat_camera_row, 5)
        self.assertLess(11, self.app.combat_camera_row+10)


if __name__ == "__main__":
    unittest.main()
