"""Right-click inspection must not execute building actions or reveal hidden state."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
import pygame as pg

from orion import balance, exploration
from orion.app import App
from orion.model import ConstructionProject, new_game


class BuildingInfoTests(unittest.TestCase):
    def setUp(self):
        old, configured = balance.active_profile(), balance._configured_path
        self.addCleanup(lambda: balance.activate(old))
        self.addCleanup(lambda: setattr(balance, '_configured_path', configured))
        balance._configured_path = None
        balance.activate(balance.default_profile())
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.app = App(Path(tmp.name), capture=True)
        self.addCleanup(pg.quit)
        self.addCleanup(self.app.audio.close)
        self.app.game = self.game = new_game(seed=2408, random_starts=False, with_ai=True,
            with_guardians=False, with_tombs=False, with_black_holes=False, with_encounters=False)
        self.planet = self.game.planet_at(0, 2)
        self.planet.buildings = ['factory', 'space_hub', 'solar_array']
        self.app.open_planet(2)
        self.app.render()
        self.app.present()

    def click(self, key, button=3):
        self.app.render()
        target = next(b for b in self.app.buttons if b.key == key)
        x, y = target.rect.center
        view = self.app.viewport
        pos = (round(view.x+x*view.w/1440), round(view.y+y*view.h/900))
        for event in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(event, button=button, pos=pos))
        self.app.render()

    def body(self):
        return '\n'.join(body for _, body in self.app.dialog['building_info'].sections)

    def test_scaled_right_click_shows_effects_and_preserves_orders_then_left_click_still_manages(self):
        self.app.viewport = pg.Rect(71, 39, 960, 600)
        self.app.focus = 'surface_factory'
        before = self.game.to_dict()
        self.click('surface_factory')
        self.assertEqual(self.app.screen, 'planet')
        self.assertEqual(self.app.dialog['building_info'].title, 'Factory')
        self.assertIn('+4 industry', self.body())
        self.assertIn('+1 IND/worker', self.body())
        self.assertIn('2 Credits / turn · 3 energy demand', self.body())
        self.assertEqual(self.game.to_dict(), before)
        self.click('dialog_close', button=1)
        self.assertIsNone(self.app.dialog)
        self.assertEqual(self.app.focus, 'surface_factory')
        self.click('surface_factory', button=1)
        self.assertEqual((self.app.screen, self.app.colony_slot), ('colony', 0))

    def test_special_landmarks_queued_and_disabled_buildings_are_read_only(self):
        self.planet.disabled_buildings = [0]
        self.planet.construction_queue = [ConstructionProject('frigate'), ConstructionProject('mine')]
        self.app.render()
        before = self.game.to_dict()
        with patch.object(self.app, 'save_game', side_effect=AssertionError('Inspection must not save')):
            for key, expected in [('surface_headquarters', 'administrative centre'),
                                  ('surface_shipyard', '1 ship projects queued'),
                                  ('surface_space_hub', 'specialist'),
                                  ('surface_mine', '1 queued (no effects until completed)'),
                                  ('surface_factory', '1 disabled')]:
                self.click(key)
                self.assertIn(expected, self.body())
                self.assertEqual(self.app.screen, 'planet')
                self.assertEqual(self.game.to_dict(), before)
                # A second right-click dismisses without activating the target below.
                self.app.handle_event(pg.event.Event(pg.MOUSEBUTTONUP, button=3, pos=(0, 0)))
                self.assertIsNone(self.app.dialog)

    def test_stale_enemy_building_uses_survey_and_never_queries_live_bonuses(self):
        enemy = self.game.opponent
        sid, pid = enemy.home_system, enemy.home_planet
        world = self.game.planet_at(sid, pid)
        world.buildings = ['factory']
        exploration.record_survey(self.game, sid, 'player')
        world.buildings = ['research_lab']
        self.game.selected_system = sid
        self.app.open_planet(pid)
        self.assertFalse(self.game.system_visible(sid))
        self.app.render()
        before = self.game.to_dict()
        target = next(b for b in self.app.buttons if b.key == 'surface_factory')
        x, y = target.rect.center
        view = self.app.viewport
        pos = (round(view.x+x*view.w/1440), round(view.y+y*view.h/900))
        with patch.object(self.game, 'bonuses_for', side_effect=AssertionError('Hidden live bonuses')):
            self.app.handle_event(pg.event.Event(pg.MOUSEBUTTONUP, button=3, pos=pos))
        self.app.render()
        self.assertEqual(self.app.dialog['building_info'].identifier, 'factory')
        self.assertIn('Last observed; current operating status unknown.', self.body())
        self.assertEqual(self.game.to_dict(), before)
        self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_ESCAPE))
        self.assertIsNone(self.app.dialog)

    def test_mothership_modules_show_info_and_empty_bays_do_not_open_build_orders(self):
        self.app.game = self.game = new_game(seed=2408, random_starts=False, race_id='wanderers',
            with_ai=False, with_guardians=False, with_tombs=False, with_black_holes=False)
        home = next(s for s in self.game.ships if s.habitat)
        home.habitat.buildings = ['factory']
        home.habitat.construction_queue = []
        self.app.open_mothership(home.id)
        before = self.game.to_dict()
        self.click('mothership_module_0')
        self.assertEqual(self.app.dialog['building_info'].title, 'Industry module')
        self.assertTrue(self.app.dialog['building_info'].habitat)
        self.assertEqual(self.game.to_dict(), before)
        self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_ESCAPE))
        self.click('mothership_module_1')
        self.assertIsNone(self.app.dialog)
        self.assertEqual(self.app.screen, 'planet')
        self.assertEqual(self.game.to_dict(), before)


if __name__ == '__main__':
    unittest.main()
