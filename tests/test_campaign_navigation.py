"""Campaign navigation stays consistent without bypassing simulation decisions."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')

import pygame as pg
from orion.app import App, GAME_SCREENS
from orion import campaign_navigation as navigation
from tools.preview_all_screens import campaign, screen_states


class CampaignNavigationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.folder.name), capture=True)
        self.addCleanup(self.app.audio.close)
        self.app.window = pg.display.set_mode((1440, 900))
        self.app.settings['autosave'] = self.app.settings['animated_background'] = False
        self.app.game = campaign()
        self.app.game.selected_system, self.app.game.selected_planet = 0, 2

    def frame(self):
        self.app.render()
        self.app.present()

    def button(self, key):
        return next(b for b in self.app.buttons if b.key == key)

    def click(self, key):
        self.frame()
        button = self.button(key)
        self.app.display_view.ensure_visible(button.rect)
        self.frame()
        pos = self.app.canvas.point(button.rect.center)
        pos = (pos[0]+self.app.viewport.x, pos[1]+self.app.viewport.y)
        self.assertTrue(self.app.window.get_rect().collidepoint(pos))
        for event_type in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(event_type, button=1, pos=pos))

    def key(self, key, **kwargs):
        self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=key, mod=0, **kwargs))

    def test_all_campaign_views_have_one_unobstructed_pair(self):
        visited = set()
        for name in screen_states(self.app):
            for window, scale in (((1440, 900), 100), ((1280, 800), 175)):
                with self.subTest(screen=name, window=window, scale=scale):
                    self.app.window = pg.display.set_mode(window)
                    self.app.settings['ui_scale'] = scale
                    self.frame()
                    controls = self.app.buttons
                    keys = [b.key for b in controls]
                    if self.app.dialog or not navigation.available(self.app):
                        self.assertNotIn('galaxy_map', keys)
                        continue
                    visited.add(self.app.screen)
                    self.assertEqual(keys.count('galaxy_map'), 1)
                    self.assertEqual(keys.count('end_turn'), 1)
                    galaxy, end = self.button('galaxy_map'), self.button('end_turn')
                    self.assertEqual((galaxy.label, end.label), ('Galaxy map', 'End turn'))
                    self.assertEqual((galaxy.shortcut, end.shortcut), ('G', 'E'))
                    self.assertEqual(galaxy.rect.bottom, end.rect.bottom)
                    self.assertLess(galaxy.rect.right, end.rect.left)
                    for button in (galaxy, end):
                        self.assertTrue(self.app.canvas.get_rect().contains(button.rect))
                        collisions = [b.key for b in controls if b is not button and b.rect.colliderect(button.rect)]
                        self.assertFalse(collisions, (button.key, collisions))
        self.assertEqual(visited, set(GAME_SCREENS)-{'galaxy'})

    def test_galaxy_retains_its_existing_end_turn_control(self):
        self.app.screen = 'galaxy'
        self.frame()
        button = self.button('end_turn')
        self.assertEqual(button.rect, pg.Rect(1081, 813, 295, 61))
        self.assertEqual(button.style, 'command_primary')
        self.assertEqual(button.subtitle, 'Turn 2 · Year 2301')
        self.assertNotIn('galaxy_map', [b.key for b in self.app.buttons])

    def test_map_click_and_shortcut_keep_selection_and_local_back_history(self):
        app = self.app
        home = app.game.planet_at(0, 2)
        home.trade_goods = True
        for screen in ('empire', 'planet', 'research', 'production', 'designer'):
            for scale in (100, 175):
                with self.subTest(screen=screen, scale=scale):
                    app.planet_return, app.empire_return = 'system', 'planet'
                    app.screen, app.settings['ui_scale'] = screen, scale
                    turn = app.game.turn
                    self.click('galaxy_map')
                    self.assertEqual(app.screen, 'galaxy')
                    self.assertEqual((app.game.selected_system, app.game.selected_planet), (0, 2))
                    self.assertEqual((app.planet_return, app.empire_return), ('system', 'planet'))
                    self.assertEqual(app.game.turn, turn)
                    self.assertEqual(app.focus, 'galaxy_world_2')
            app.screen = screen
            self.frame()
            self.key(pg.K_g)
            self.assertEqual(app.screen, 'galaxy')
        app.screen = 'planet'
        self.click('planet_return')
        self.assertEqual(app.screen, 'system')

    def test_leaving_idle_colony_uses_the_existing_housekeeping(self):
        app = self.app
        home = app.game.planet_at(0, 2)
        self.assertTrue(home.production_idle)
        app.go('planet')
        self.click('galaxy_map')
        self.assertEqual(app.screen, 'galaxy')
        self.assertTrue(home.trade_goods)
        self.assertEqual(app.game.turn, 1)

    def test_end_turn_uses_existing_production_prompt_then_advances_once(self):
        app = self.app
        from orion import first_contact
        for owner in first_contact.pending(app.game):
            first_contact.acknowledge(app.game, owner)
        app.screen = 'empire'
        turn = app.game.turn
        self.click('end_turn')
        self.assertEqual(app.game.turn, turn)
        self.assertEqual(app.screen, 'planet')
        self.click('end_turn')
        self.assertEqual(app.game.turn, turn+1)
        self.assertTrue(app.game.planet_at(0, 2).trade_goods)

    def test_required_decisions_cannot_be_bypassed_by_footer_or_g(self):
        checked = set()
        for name in screen_states(self.app):
            if name not in ('contact', 'result', 'council_vote', 'combat'):
                continue
            with self.subTest(screen=name):
                app = self.app
                self.frame()
                reason = navigation.blocked_reason(app)
                self.assertIsNotNone(reason)
                before, screen = app.game.to_dict(), app.screen
                for key in ('galaxy_map', 'end_turn'):
                    self.assertFalse(self.button(key).enabled)
                    app.activate(self.button(key))
                self.key(pg.K_g)
                self.assertEqual(app.screen, screen)
                self.assertEqual(app.game.to_dict(), before)
                checked.add(app.screen)
        self.assertEqual(checked, {'contact', 'result', 'council', 'combat'})

    def test_pending_ground_reports_and_busy_turn_disable_navigation(self):
        app = self.app
        app.screen = 'empire'
        for state in ('ground_reports', 'turn_busy'):
            with self.subTest(state=state):
                setattr(app, state, [object()] if state == 'ground_reports' else True)
                self.frame()
                self.assertFalse(self.button('galaxy_map').enabled)
                self.assertFalse(self.button('end_turn').enabled)
                self.key(pg.K_g)
                self.assertEqual(app.screen, 'empire')
                setattr(app, state, [] if state == 'ground_reports' else False)

    def test_leaving_a_landing_plan_clears_it_without_launching_an_assault(self):
        app = self.app
        system, planet = app.game.headquarters('rival')
        app.screen, app.ground_target = 'ground', (system.id, planet.id)
        app.game.planet_at(0, 2).trade_goods = True
        before = app.game.to_dict()
        self.frame()
        self.assertFalse(self.button('end_turn').enabled)
        self.assertTrue(self.button('galaxy_map').enabled)
        self.click('galaxy_map')
        self.assertEqual(app.screen, 'galaxy')
        self.assertIsNone(app.ground_target)
        self.assertEqual(app.game.to_dict(), before)

    def test_repeated_activation_and_dialog_shortcuts_do_not_advance(self):
        app = self.app
        app.screen, app.keyboard_mode, app.focus = 'empire', True, 'end_turn'
        with patch.object(app, 'advance_turn') as advance:
            self.frame()
            self.key(pg.K_RETURN, repeat=True)
            self.key(pg.K_e, repeat=True)
            advance.assert_not_called()
            self.key(pg.K_RETURN)
            advance.assert_called_once_with()
        app.confirm('Test decision', 'Keep this decision open.', 'Confirm', lambda: None)
        self.frame()
        self.key(pg.K_g)
        self.key(pg.K_e)
        self.assertIsNotNone(app.dialog)
        self.assertEqual(app.screen, 'empire')

    def test_simulator_does_not_get_campaign_actions(self):
        self.app.screen = 'designer'
        # Render the real simulator separately; its designer carries a game too.
        from orion.combat_simulator import CombatSimulator
        sim = CombatSimulator(Path(self.folder.name)/'simulator', capture=True)
        self.addCleanup(sim.audio.close)
        sim.go('designer')
        sim.render()
        self.assertFalse(navigation.available(sim))
        self.assertFalse({'galaxy_map', 'end_turn'} & {b.key for b in sim.buttons})


if __name__ == '__main__':
    unittest.main()
