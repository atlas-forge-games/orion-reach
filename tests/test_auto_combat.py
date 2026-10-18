"""Automatic player orders, animated handover, pausing and battle continuity."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame as pg
from orion.app import App
from orion.model import PLAYER, RIVAL
from test_combat import encounter
from test_starships import carrier_battle
from test_black_holes import campaign, fleet, research


class AutoCombatTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.app = App(Path(self.folder.name), capture=True)
        self.app.window = pg.display.set_mode((980, 900), pg.RESIZABLE)
        self.app.present()
        self.use_battle(encounter())

    def tearDown(self):
        self.app.audio.close()
        pg.quit()
        self.folder.cleanup()

    def use_battle(self, game):
        self.app.game = game
        self.app.reset_combat_view()
        self.app.go("combat")
        self.app.render()
        return game

    def button(self, key):
        self.app.render()
        return next(b for b in self.app.buttons if b.key == key)

    def click(self, key):
        button = self.button(key)
        self.assertTrue(button.enabled, key)
        x, y = button.rect.center
        viewport = self.app.viewport
        pos = (round(viewport.x+x*viewport.w/1440), round(viewport.y+y*viewport.h/900))
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, button=1, pos=pos))
            self.app.render()

    def key(self, key):
        self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=key, mod=0))
        self.app.render()

    def tick(self, seconds=2, render=False):
        self.app.time += seconds
        self.app.update_combat()
        if render:
            self.app.render()

    def finish_battle(self):
        for _ in range(1500):
            if self.app.game.combat.status != "active" and self.app.combat_animation is None:
                self.app.render()
                return
            self.tick()
        self.fail("Automatic battle did not finish")

    def test_scaled_button_and_shortcut_handover_preserve_the_current_move(self):
        app, battle = self.app, self.app.game.combat
        before = app.game.to_dict()
        self.assertFalse(app.combat_auto)
        self.click("combat_auto")
        self.assertEqual(app.game.to_dict(), before)
        self.assertEqual(self.button("combat_auto").label, "Take control · A")
        self.tick(.2)
        self.assertEqual(app.game.to_dict(), before)
        self.tick(.3, render=True)
        animation = app.combat_animation
        self.assertEqual(animation.kind, "move")
        self.assertEqual(app.combat_ship_id, animation.ship_id)
        after_move = app.game.to_dict()
        for key in ("combat_fire", "combat_next", "combat_hold", "combat_end_turn", "combat_retreat", "combat_ship_1"):
            self.assertFalse(self.button(key).enabled, key)
        self.assertFalse(any(b.key.startswith("combat_cell_") for b in app.buttons))
        app.move_combat_ship(8, 4)
        app.select_combat_ship(RIVAL, 2)
        app.retreat_request()
        for action in ("fire", "launch", "hold", "retreat", "end_turn"):
            app.combat_action(action)
        for key in (pg.K_e, pg.K_n):
            self.key(key)
        self.assertEqual(app.game.to_dict(), after_move)
        self.key(pg.K_a)
        self.assertFalse(app.combat_auto)
        self.assertIs(app.combat_animation, animation)
        self.assertFalse(app.combat_input_ready())
        self.tick()
        self.tick(10)
        self.assertEqual(app.game.to_dict(), after_move)
        self.assertTrue(app.combat_input_ready())
        self.assertFalse(battle.can_move(battle.ship(1)))
        self.assertTrue(battle.can_fire(battle.ship(1)))
        self.assertEqual(self.button("combat_auto").label, "Auto combat · A")

    def test_handover_during_a_shot_cannot_repeat_its_damage(self):
        app, game = self.app, self.app.game
        self.key(pg.K_a)
        self.tick()  # Move.
        self.tick()  # Finish moving.
        self.tick()  # Fire.
        shot = app.combat_animation
        self.assertEqual(shot.kind, "fire")
        self.assertEqual(app.combat_target_id, shot.target_id)
        before = game.to_dict()
        self.click("combat_auto")
        app.combat_action("fire")
        self.tick()
        app.combat_action("fire")
        self.tick()
        self.assertEqual(game.to_dict(), before)
        self.assertFalse(game.combat.can_fire(game.combat.ship(shot.ship_id)))

    def test_enabling_after_manual_orders_does_not_reuse_spent_actions(self):
        app, game = self.app, self.app.game
        app.move_combat_ship(7, 4)
        self.tick()
        app.combat_action("fire")
        shots, target_hull = game.combat.shots_fired, game.combat.ship(2).hull
        self.key(pg.K_a)
        self.tick()  # Finish the manual shot.
        self.tick()  # End the player's already-spent turn.
        self.assertEqual(game.combat.active_owner, RIVAL)
        self.assertEqual(game.combat.shots_fired, shots)
        self.assertEqual(game.combat.ship(2).hull, target_hull)

    def test_toggle_during_enemy_turn_keeps_enemy_playing_and_can_resume_ours(self):
        app, game = self.app, self.app.game
        app.combat_action("end_turn")
        self.click("combat_auto")
        self.tick()
        self.assertEqual(app.combat_animation.kind, "move")
        self.click("combat_auto")
        for _ in range(20):
            self.tick()
            if game.combat.active_owner == PLAYER and app.combat_animation is None:
                break
        self.assertEqual(game.combat.active_owner, PLAYER)
        self.assertFalse(app.combat_auto)
        self.assertTrue(game.combat.can_move(game.combat.ship(1)))
        before = game.to_dict()
        self.tick(10)
        self.assertEqual(game.to_dict(), before)
        app.combat_action("end_turn")
        self.key(pg.K_a)
        for _ in range(20):
            self.tick()
            effect = app.combat_animation
            if effect and game.combat.ship(effect.ship_id).owner == PLAYER:
                break
        self.assertTrue(app.combat_auto)
        self.assertIsNotNone(effect)
        self.assertEqual(game.combat.ship(effect.ship_id).owner, PLAYER)

    def test_pause_settings_info_and_dialog_freeze_auto_actions_and_effects(self):
        app = self.app
        self.click("combat_auto")
        self.tick()
        self.tick(.1)
        effect = app.combat_animation
        before, age = app.game.to_dict(), effect.elapsed
        app.pause()
        self.tick(5)
        app.show_settings()
        self.tick(5)
        for section in ('graphics', 'sound', 'gameplay', 'interface'):
            self.click('settings_category_'+section)
            self.tick(5)
        app.go("combat")
        app.open_info()
        self.tick(5)
        app.close_info()
        app.quit_request()
        self.tick(5)
        self.key(pg.K_a)
        self.assertTrue(app.combat_auto)
        self.assertEqual(effect.elapsed, age)
        self.assertEqual(app.game.to_dict(), before)
        app.cancel_dialog()
        self.tick(.1)
        self.assertAlmostEqual(effect.elapsed, age+.1)
        self.tick()
        before = app.game.to_dict()
        app.open_info()
        self.tick(20)
        app.close_info()
        self.tick(.2)
        self.assertEqual(app.game.to_dict(), before)
        self.tick(1)
        self.assertEqual(app.combat_animation.kind, "fire")

    def test_save_load_restores_manual_control_without_replaying_orders(self):
        app = self.app
        self.click("combat_auto")
        self.tick()
        self.assertIsNotNone(app.combat_animation)
        before = app.game.to_dict()
        self.key(pg.K_F5)
        saved = next(p for p in app.storage.saves_dir.glob("*.json") if p.name != "autosave.json")
        app.load_game(saved)
        self.assertEqual(app.screen, "combat")
        self.assertFalse(app.combat_auto)
        self.assertIsNone(app.combat_animation)
        self.tick(20)
        self.assertEqual(app.game.to_dict(), before)
        self.assertFalse(app.game.combat.can_move(app.game.combat.ship(1)))
        self.assertTrue(app.combat_input_ready())

    def test_carriers_launch_drones_and_command_them_with_normal_animations(self):
        game = self.use_battle(carrier_battle(enemy="cruiser"))
        app, battle = self.app, game.combat
        carrier = battle.ship(1)
        reserve = carrier.drone_reserve
        self.click("combat_auto")
        self.tick()
        self.assertTrue(battle.drones(carrier))
        self.assertLess(carrier.drone_reserve, reserve)
        for _ in range(150):
            self.tick()
            effect = app.combat_animation
            if effect and effect.kind == "fire" and battle.ship(effect.ship_id).kind == "combat_drone":
                break
        self.assertIsNotNone(effect)
        self.assertEqual(effect.kind, "fire")
        self.assertEqual(battle.ship(effect.ship_id).kind, "combat_drone")
        self.assertEqual(app.combat_ship_id, effect.ship_id)
        self.assertEqual(app.storage.load(app.storage.saves_dir/"autosave.json")[0], game)

    @patch("orion.combat.accuracy_breakdown", new=lambda *_: {"chance": 100})
    def test_victory_and_defeat_stop_at_results_without_advancing_the_campaign(self):
        for own, enemy, expected in ((('frigate',)*2, ('frigate',), "player_victory"),
                                     (('frigate',), ('cruiser',)*2, "rival_victory")):
            with self.subTest(result=expected):
                game = self.use_battle(encounter(own=own, enemy=enemy))
                strategic = (game.turn, game.credits, game.resources, game.research)
                self.click("combat_auto")
                self.finish_battle()
                self.assertEqual(game.combat.status, expected)
                self.assertFalse(self.app.combat_auto)
                self.assertEqual(self.app.screen, "combat")
                self.assertTrue(self.button("combat_continue").enabled)
                self.assertNotIn("combat_auto", [b.key for b in self.app.buttons])
                self.assertEqual((game.turn, game.credits, game.resources, game.research), strategic)
                self.assertEqual(self.app.storage.load(self.app.storage.saves_dir/"autosave.json")[0], game)
                before = game.to_dict()
                self.key(pg.K_a)
                self.tick(100)
                self.assertEqual(game.to_dict(), before)
                self.click("combat_continue")
                self.assertIsNone(game.combat)
                self.assertFalse(self.app.combat_auto)
        self.use_battle(encounter())
        self.assertFalse(self.app.combat_auto)

    def test_unarmed_survivors_retreat_once_when_a_safe_destination_exists(self):
        game = encounter(own=("scout",), start=False)
        game.start_combat(0, RIVAL)
        game.combat_end_turn(RIVAL)
        self.use_battle(game)
        self.click("combat_auto")
        self.tick()
        self.assertEqual(game.combat.status, "player_retreat")
        self.assertTrue(game.ship_at(1).in_transit)
        self.assertFalse(self.app.combat_auto)
        self.assertIsNone(self.app.combat_animation)
        before = game.to_dict()
        self.tick(100)
        self.assertEqual(game.to_dict(), before)
        self.click("combat_continue")
        self.assertIsNone(game.combat)
        self.assertEqual(game.turn, 1)

    def test_black_hole_guardian_auto_victory_collects_exactly_one_relic(self):
        game = campaign()
        research(game)
        site = game.black_holes.sites[0]
        fleet(game, site.system_id)
        game.start_combat(site.system_id)
        self.use_battle(game)
        self.click("combat_auto")
        self.finish_battle()
        self.assertEqual(game.combat.status, "player_victory")
        self.assertFalse(self.app.combat_auto)
        self.assertEqual(site.claimed_by, PLAYER)
        self.assertEqual(sum(s.claimed_by == PLAYER for s in game.black_holes.sites), 1)
        before = game.to_dict()
        self.tick(100)
        self.assertEqual(game.to_dict(), before)
        self.assertEqual(self.app.storage.load(self.app.storage.saves_dir/"autosave.json")[0], game)


if __name__ == "__main__":
    unittest.main()
