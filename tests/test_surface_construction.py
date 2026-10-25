"""Stable city geometry, explicit placement and saved/surveyed site positions."""

from copy import deepcopy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
import pygame as pg

from orion import balance, colony_layout, exploration, motherships, raiding
from orion.app import App
from orion.colony_scene import scene_buildings
from orion.model import GameState, RuleError, SaveError, new_game
from orion.storage import SAVE_VERSION, Storage


class SurfaceFixture(unittest.TestCase):
    def setUp(self):
        old, configured = balance.active_profile(), balance._configured_path
        self.addCleanup(lambda: balance.activate(old))
        self.addCleanup(lambda: setattr(balance, '_configured_path', configured))
        balance._configured_path = None
        balance.activate(balance.default_profile())
        self.game = new_game(seed=2408, random_starts=False, with_ai=True,
            with_guardians=False, with_tombs=False, with_black_holes=False, with_encounters=False)
        self.world = self.game.planet_at(0, 2)

    def sites(self, world=None, sid=0):
        world = world or self.world
        return colony_layout.layout([b.asset_id for b in scene_buildings(self.game, sid, world)], world.surface_layout)


class SurfaceLayoutTests(SurfaceFixture):
    def test_existing_position_and_size_survive_queuing_prioritizing_completion_and_removal(self):
        initial = self.sites()
        self.game.queue_building(0, 2, 'factory')
        factory = self.sites()
        self.assertEqual({k: factory[k] for k in initial}, initial)
        self.game.queue_building(0, 2, 'mine')
        self.game.prioritize_construction(0, 2, 1)
        queued = self.sites()
        self.assertEqual({k: queued[k] for k in factory}, factory)
        self.world.finish_current_project()
        self.assertEqual(self.sites(), queued)
        self.game.cancel_construction(0, 2, 0)
        remaining = self.sites()
        self.assertEqual(remaining, {k: v for k, v in queued.items() if k != 'factory'})
        self.game.demolish_building(0, 2, 0)
        self.assertEqual(self.sites(), initial)

    def test_player_site_in_front_of_left_trees_survives_save_reload_and_construction(self):
        self.game.queue_building(0, 2, 'factory', surface_site=(145, 340))
        chosen = self.world.surface_layout['factory'].copy()
        self.assertEqual(chosen[:2], [145, 340])
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(Path(folder))
            restored, metadata = storage.load(storage.save(self.game))
        self.assertEqual(metadata['version'], SAVE_VERSION)
        self.assertEqual(restored.to_dict(), self.game.to_dict())
        self.assertEqual(restored.planet_at(0, 2).surface_layout['factory'], chosen)
        self.game.opponents.clear()
        for _ in range(6):
            self.game.advance_turn()
        self.assertIn('factory', self.world.buildings)
        self.assertEqual(self.sites()['factory'], chosen)

    def test_invalid_or_occupied_site_rejects_order_without_mutation(self):
        before = self.game.to_dict()
        for point in [(567, 240), (-10, 300), (200, 0), (300, float('nan')), 'invalid']:
            with self.subTest(point=point):
                with self.assertRaises(RuleError):
                    self.game.queue_building(0, 2, 'factory', surface_site=point)
                self.assertEqual(self.game.to_dict(), before)

    def test_old_saves_migrate_without_rewriting_source_and_surveys_keep_observed_sites(self):
        legacy = self.game.to_dict()
        for system in legacy['systems']:
            for planet in system['worlds']:
                planet.pop('surface_layout', None)
        before = deepcopy(legacy)
        restored = GameState.from_dict(legacy, version=57)
        self.assertEqual(legacy, before)
        old_world = restored.planet_at(0, 2)
        sites = deepcopy(old_world.surface_layout)
        restored.queue_building(0, 2, 'factory')
        self.assertEqual({k: old_world.surface_layout[k] for k in sites}, sites)
        enemy = self.game.opponent
        world = self.game.planet_at(enemy.home_system, enemy.home_planet)
        self.game.queue_building(enemy.home_system, enemy.home_planet, 'factory', owner='rival', surface_site=(145, 340))
        exploration.record_survey(self.game, enemy.home_system, 'player')
        observed = self.game.known_system(enemy.home_system).worlds[enemy.home_planet].surface_layout.copy()
        world.surface_layout['factory'] = [250, 340, *world.surface_layout['factory'][2:]]
        self.assertEqual(self.game.known_system(enemy.home_system).worlds[enemy.home_planet].surface_layout, observed)
        self.assertEqual(GameState.from_dict(self.game.to_dict()).known_system(enemy.home_system).worlds[enemy.home_planet].surface_layout, observed)

    def test_malformed_layouts_are_rejected_and_abandonment_and_habitats_clear_sites(self):
        for sites in ({'factory': [True, 300, 100, 80]}, {'factory': [100, 300, 0, 80]},
                      {'factory': [100, 500, 100, 80]}, {'unknown': [100, 300, 100, 80]},
                      {'factory': [150, 300, 100, 80], 'mine': [150, 300, 100, 80]}):
            data = self.game.to_dict()
            data['systems'][0]['worlds'][2]['surface_layout'] = sites
            with self.subTest(sites=sites), self.assertRaises(SaveError):
                GameState.from_dict(data)
        cloned = deepcopy(self.world)
        raiding.abandon(cloned)
        self.assertEqual(cloned.surface_layout, {})
        self.game.race_id = 'wanderers'
        ship = motherships.create(self.game, 0, 'player', self.world)
        self.assertEqual(ship.habitat.surface_layout, {})
        self.assertEqual(self.world.surface_layout, {})


class SurfacePlacementUITests(SurfaceFixture):
    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.app = App(Path(tmp.name), capture=True)
        self.addCleanup(pg.quit)
        self.addCleanup(self.app.audio.close)
        self.app.game = self.game
        self.app.open_planet(2)
        self.app.render()
        self.app.viewport = pg.Rect(71, 39, 960, 600)

    def click(self, pos, button=1):
        view = self.app.viewport
        screen_pos = (round(view.x+pos[0]*view.w/1440), round(view.y+pos[1]*view.h/900))
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, button=button, pos=screen_pos))
        self.app.render()

    def click_key(self, key, button=1):
        self.click(next(b.rect.center for b in self.app.buttons if b.key == key), button)

    def test_build_here_previews_then_confirms_at_selected_site_without_moving_landmarks(self):
        initial = {b.key: b.rect.copy() for b in self.app.buttons if b.key.startswith('surface_')}
        before = self.game.to_dict()
        self.click((169, 654))  # 145, 340 on the landscape, in front of the left trees.
        self.assertEqual(self.app.screen, 'production')
        self.click_key('production_build_factory')
        self.assertEqual(self.app.screen, 'planet')
        self.assertEqual(self.app.surface_build_preview['identifier'], 'factory')
        self.assertEqual(self.game.to_dict(), before)
        self.click((169, 654))
        self.assertIsNone(self.app.surface_build_preview)
        self.assertEqual([p.item_id for p in self.world.construction_queue], ['factory'])
        x, y = self.world.surface_layout['factory'][:2]
        self.assertLessEqual(abs(x-145), 1)
        self.assertLessEqual(abs(y-340), 1)
        current = {b.key: b.rect for b in self.app.buttons if b.key.startswith('surface_')}
        self.assertEqual({k: current[k] for k in initial}, initial)
        self.click_key('surface_factory', button=3)
        self.assertEqual(self.app.dialog['building_info'].identifier, 'factory')
        self.app.cancel_dialog()
        self.app.render()
        self.click_key('surface_factory')
        self.assertEqual(self.app.screen, 'colony')
        self.assertEqual(self.app.colony_slot, 0)

    def test_blocked_placement_and_escape_or_right_click_cancel_do_not_build_or_save(self):
        before = self.game.to_dict()
        with patch.object(self.app, 'save_game', side_effect=AssertionError('Preview saved state')):
            for cancel in ('escape', 'right-click'):
                self.click((169, 654))
                self.click_key('production_build_factory')
                self.click((591, 554))  # Headquarters anchor.
                self.assertIsNotNone(self.app.surface_build_preview)
                self.assertIn('overlaps', self.app.notice)
                if cancel == 'escape':
                    self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_ESCAPE))
                    self.app.render()
                else:
                    self.click((169, 654), button=3)
                self.assertIsNone(self.app.surface_build_preview)
                self.assertEqual(self.game.to_dict(), before)

    def test_other_planets_do_not_inherit_a_pending_site_and_surveys_are_read_only(self):
        self.click((169, 654))
        self.assertIsNotNone(self.app.surface_build_request)
        self.app.open_planet(3)
        self.app.render()
        self.assertIsNone(self.app.surface_build_request)
        with patch.object(self.app, 'open_production', side_effect=AssertionError('Unowned building order')):
            self.click((169, 654))
            enemy = self.game.opponent
            exploration.record_survey(self.game, enemy.home_system, 'player')
            self.game.selected_system = enemy.home_system
            self.app.open_planet(enemy.home_planet)
            self.app.render()
            self.click((169, 654))
        self.assertIsNone(self.app.surface_build_request)


if __name__ == '__main__':
    unittest.main()
