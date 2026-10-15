"""Visibility equivalence, fresh frames, and rapid input through the real UI."""
from contextlib import nullcontext
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame as pg
from orion import black_holes, exploration, motherships
from orion.app import App
from orion.frame_cache import frame_queries
from orion.model import new_game
from test_motherships import campaign, target


def previous_visibility(game, system_id, owner='player'):
    """Pre-optimization rules, for comparison during real simulation turns."""
    if game.systems[system_id].kind == black_holes.KIND:
        return ((game.is_observer and owner == 'player') or
                (black_holes.can_detect(game, owner) and system_id in exploration.observed_systems(game, owner)))
    return (game.is_observer and owner == 'player') or not game.fog_of_war or system_id in exploration.observed_systems(game, owner)


class VisibilityPerformanceTests(unittest.TestCase):
    def test_direct_checks_match_existing_visibility_for_every_empire_and_system(self):
        for race in ('wanderers', 'terran', 'observer'):
            game = new_game(seed=12, race_id=race, rival_count=3)
            for fog in (True, False):
                game.fog_of_war = fog
                for detected in (False, True):
                    if detected:
                        for owner in game.owners:
                            game.research_state(owner).completed.append('gravitic_mapping')
                    with frame_queries(game):
                        for owner in dict.fromkeys(('player', *game.owners)):
                            for system in game.systems:
                                self.assertEqual(game.system_visible(system.id, owner),
                                                 previous_visibility(game, system.id, owner),
                                                 (race, fog, detected, owner, system.id))
                    if detected:
                        for owner in game.owners:
                            game.research_state(owner).completed.remove('gravitic_mapping')

    def test_simulation_outcomes_match_previous_visibility_with_multiple_ai_empires(self):
        for race, fog in (('wanderers', True), ('terran', False), ('observer', True)):
            with self.subTest(race=race, fog=fog):
                game = new_game(seed=31, race_id=race, rival_count=3, fog_of_war=fog)
                reference = copy.deepcopy(game)
                for _ in range(5):
                    result = game.advance_turn()
                    with patch('orion.exploration.is_visible', previous_visibility):
                        expected = reference.advance_turn()
                    self.assertEqual(result, expected)
                    self.assertEqual(game.to_dict(), reference.to_dict())

    def test_visibility_does_not_scan_every_supply_system_for_a_local_question(self):
        game = campaign()
        with patch.object(game, 'supply_systems', side_effect=AssertionError('Full galaxy scan')):
            self.assertTrue(game.system_visible(0))
            self.assertFalse(game.system_visible(1))

    def test_new_frames_follow_departure_arrival_outposts_ownership_and_fog(self):
        game = campaign(with_ai=True, rival_race_id='terran')
        destination = target(game)
        home = motherships.homes(game, 'player')[0]
        game.ships = [s for s in game.ships if s.owner != 'player' or s is home]

        def observed(origin, dest):
            with frame_queries(game):
                self.assertEqual(game.system_visible(0), origin)
                self.assertEqual(game.system_visible(destination.id), dest)
                self.assertEqual([s.id for s in game.visible_ships()],
                                 [s.id for s in game.ships if exploration.ship_visible(game, s)])
                centers = game.supply_centers()
                self.assertEqual(centers, game.supply_centers.__wrapped__(game))
            self.assertFalse(hasattr(game, '_frame_queries'))

        observed(True, False)
        game.send_ship(home.id, destination.id)
        observed(True, False)  # A pending departure still occupies its origin.
        home.departure_pending = False
        observed(False, False)
        home.system_id = destination.id
        home.destination, home.turns_remaining, home.travel_total = None, 0, 0
        observed(False, True)
        planet = game.systems[0].worlds[0]
        planet.outpost_owner = 'player'
        observed(True, True)
        planet.outpost_owner = None
        planet.owner = 'rival'
        observed(False, True)
        planet.owner = 'player'
        observed(True, True)
        planet.owner = None
        game.fog_of_war = False
        observed(True, True)

    def test_last_survey_does_not_leak_new_ownership_until_a_ship_returns(self):
        game = campaign()
        destination = next(s for s in game.systems[1:] if s.worlds)
        exploration.record_survey(game, destination.id, 'player')
        world = destination.worlds[0]
        world.owner, world.colonized = 'rival', True
        with frame_queries(game):
            self.assertIsNone(game.known_system(destination.id).worlds[0].owner)
        scout = next(s for s in game.ships if s.kind == 'scout')
        scout.system_id = destination.id
        with frame_queries(game):
            self.assertEqual(game.known_system(destination.id).worlds[0].owner, 'rival')

    def test_frame_cache_is_discarded_on_failure_and_never_saved(self):
        game = campaign()
        before = game.to_dict()
        with self.assertRaisesRegex(RuntimeError, 'drawing failed'):
            with frame_queries(game):
                game.visible_ships()
                game.supply_centers()
                self.assertEqual(game.to_dict(), before)
                raise RuntimeError('drawing failed')
        self.assertFalse(hasattr(game, '_frame_queries'))
        self.assertEqual(game.to_dict(), before)


class InputPerformanceTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.folder.name), capture=True)
        self.addCleanup(self.app.audio.close)
        self.app.game = campaign()
        for _, planet in self.app.game.settlements('player'):
            planet.trade_goods = True
        self.app.settings['autosave'] = False
        self.app.go('galaxy')
        self.app.render()
        self.app.present()
        pg.event.clear()

    def clicks(self, key):
        button = next(b for b in self.app.buttons if b.key == key)
        return self.click_at(button.rect.center)

    def click_at(self, point):
        vp = self.app.viewport
        pos = (round(vp.x+point[0]*vp.w/1440), round(vp.y+point[1]*vp.h/900))
        return [pg.event.Event(kind, button=1, pos=pos) for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP)]

    def key(self, key, **extra):
        return pg.event.Event(pg.KEYDOWN, key=key, mod=0, **extra)

    def test_render_reuses_fleet_scan_and_produces_identical_pixels(self):
        app = self.app
        with patch('orion.exploration.ship_visible', wraps=exploration.ship_visible) as scan:
            app.render()
            self.assertLessEqual(scan.call_count, 2*len(app.game.ships))
        expected = pg.image.tobytes(app.canvas, 'RGB')
        with patch('orion.app.frame_queries', lambda game: nullcontext()):
            app.render()
        self.assertEqual(pg.image.tobytes(app.canvas, 'RGB'), expected)
        self.assertFalse(hasattr(app.game, '_frame_queries'))

    def test_many_motion_events_only_require_the_final_frame(self):
        app = self.app
        events = [pg.event.Event(pg.MOUSEMOTION, pos=(300+i, 300)) for i in range(60)]
        with patch.object(app, 'render', wraps=app.render) as drawing:
            app.process_events(events)
            app.render()
            self.assertEqual(drawing.call_count, 1)
        self.assertEqual(app.mouse, app.logical_pos(events[-1].pos))

    def test_screen_transition_refreshes_click_targets_within_the_same_batch(self):
        app = self.app
        app.pause()
        app.render()
        settings = self.clicks('settings')
        app.show_settings('pause')
        app.render()
        toggle = self.clicks('autosave')
        app.go('pause')
        app.render()
        app.process_events(settings+toggle)
        self.assertEqual(app.screen, 'settings')
        self.assertIs(app.settings['autosave'], True)

    def test_camera_drag_refreshes_targets_before_a_following_click(self):
        app = self.app
        app.zoom_map(5)
        app.render()
        start, end = (550, 400), (630, 440)
        events = [pg.event.Event(pg.MOUSEBUTTONDOWN, button=3, pos=start),
                  pg.event.Event(pg.MOUSEMOTION, pos=end),
                  pg.event.Event(pg.MOUSEBUTTONUP, button=3, pos=end)]
        # Find the expected target after this exact pan, then restore the camera.
        camera = copy.copy(app.map_camera)
        for event in events:
            app.handle_event(event)
        app.render()
        star = next(b for b in app.buttons if b.key.startswith('star_') and b.key != 'star_0')
        destination, click = int(star.key[5:]), self.click_at(star.rect.center)
        app.map_camera = camera
        app.render()
        app.process_events(events+click)
        self.assertEqual(app.game.selected_system, destination)

    def test_burst_of_end_turn_keys_and_clicks_advances_once_and_next_press_works(self):
        app = self.app
        before = app.game.turn
        app.process_events(self.clicks('end_turn')*3+[self.key(pg.K_e)]*3)
        self.assertEqual(app.game.turn, before+1)
        self.assertFalse(app.turn_busy)
        # A fresh, intentional press after the completed frame can advance again.
        app.go('galaxy')
        app.render()
        app.process_events([self.key(pg.K_e)])
        self.assertEqual(app.game.turn, before+2)

    def test_duplicate_turn_commands_cannot_skip_an_idle_colony_prompt(self):
        app = self.app
        home = app.game.headquarters()[1]
        home.trade_goods = False
        app.process_events([self.key(pg.K_e)]*4)
        self.assertEqual(app.game.turn, 1)
        self.assertFalse(home.trade_goods)
        self.assertEqual(app.screen, 'planet')

    def test_progress_is_presented_before_simulation_and_stale_input_is_removed(self):
        app, game = self.app, self.app.game
        advance = game.advance_turn
        frames = []

        def simulate():
            self.assertTrue(app.turn_busy)
            self.assertEqual(frames[-1], (True, game.turn))
            app.advance_turn()  # Re-entrant commands cannot advance another turn.
            pg.event.post(self.key(pg.K_e))
            for event in self.clicks('end_turn'):
                pg.event.post(event)
            pg.event.post(pg.event.Event(pg.KEYUP, key=pg.K_LSHIFT))
            pg.event.post(pg.event.Event(pg.QUIT))
            return advance()

        with patch.object(app, 'present', side_effect=lambda: frames.append((app.turn_busy, game.turn))), \
                patch.object(game, 'advance_turn', side_effect=simulate) as turning:
            app.advance_turn()
            turning.assert_called_once()
        self.assertEqual(frames, [(True, 1), (False, 2)])
        events = pg.event.get()
        self.assertEqual({event.type for event in events}, {pg.KEYUP, pg.QUIT})
        app.process_events(events)
        self.assertIsNotNone(app.dialog)

    def test_held_turn_key_does_not_repeat_and_failures_release_busy_state(self):
        app = self.app
        app.focus = 'end_turn'
        app.process_events([self.key(pg.K_e, repeat=True), self.key(pg.K_RETURN, repeat=True)])
        self.assertEqual(app.game.turn, 1)
        with patch.object(app.game, 'advance_turn', side_effect=RuntimeError('turn failed')):
            with self.assertRaisesRegex(RuntimeError, 'turn failed'):
                app.advance_turn()
        self.assertFalse(app.turn_busy)
        self.assertFalse(hasattr(app.game, '_frame_queries'))
        app.advance_turn()
        self.assertEqual(app.game.turn, 2)


if __name__ == '__main__':
    unittest.main()
