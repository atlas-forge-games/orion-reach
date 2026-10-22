"""Real launch, flight and impact rendering must follow state without mutating it."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
import pygame as pg

from orion import combat_camera as camera, projectile_art
from orion.combat_simulator import CombatSimulator
from test_arsenal import duel


class ProjectilePositionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.app = CombatSimulator(Path(self.folder.name), capture=True)
        self.app.game = duel(['torpedo'])
        self.app.game.combat.ship(2).x = 13
        self.app.go('combat')
        self.app.combat_ship_id, self.app.combat_target_id = 1, 2
        self.app.combat_action('fire')

    def tearDown(self):
        self.app.audio.close()
        pg.quit()
        self.folder.cleanup()

    def positions(self):
        before = self.app.game.to_dict()
        with patch.object(projectile_art, 'draw', wraps=projectile_art.draw) as drawn:
            self.app.render()
        self.assertEqual(self.app.game.to_dict(), before)
        return [call.args[1] for call in drawn.call_args_list]

    def advance(self):
        self.app.game.combat_end_turn()
        flights = self.app.game.combat_end_turn('rival')
        self.app.after_combat_action({'kind': 'end_turn', 'flights': flights})
        return flights

    def test_launch_shows_one_rocket_at_saved_position_without_false_forward_jump(self):
        shot = self.app.game.combat.projectiles[0]
        for age in (0, .1, .3):
            self.app.combat_animation.elapsed = age
            self.assertEqual(self.positions(), [camera.view(self.app).project(shot.position)])

    def test_flight_interpolates_then_remains_visible_at_end_and_after_animation(self):
        flight, = self.advance()
        self.assertFalse(flight['impact'])
        for zoom in (.5, 1.0, 3.0):
            self.app.combat_zoom = zoom
            camera.reveal(self.app, (flight['start'], flight['end']))
            self.app.combat_animation.elapsed = .2
            view = camera.view(self.app)
            start, end = view.project(flight['start']), view.project(flight['end'])
            middle = tuple(round((a+b)/2) for a, b in zip(start, end))
            self.assertEqual(self.positions(), [middle])
            self.app.combat_animation.elapsed = .65
            self.assertEqual(self.positions(), [end])
        self.app.combat_animation = None
        self.assertEqual(self.positions(), [camera.view(self.app).project(flight['end'])])

    def test_impact_removes_the_projectile_after_arrival(self):
        self.advance()
        flight, = self.advance()
        self.assertTrue(flight['impact'])
        self.app.combat_animation.elapsed = .2
        self.assertEqual(len(self.positions()), 1)
        self.app.combat_animation.elapsed = .6
        self.assertEqual(self.positions(), [])

    def test_expired_projectile_disappears_at_end_of_its_last_segment(self):
        self.app.game.combat.projectiles[0].age = 5
        flight, = self.advance()
        self.assertFalse(flight['impact'])
        self.assertFalse(self.app.game.combat.projectiles)
        self.app.combat_animation.elapsed = .2
        self.assertEqual(len(self.positions()), 1)
        self.app.combat_animation.elapsed = .65
        self.assertEqual(self.positions(), [])


if __name__ == '__main__':
    unittest.main()
