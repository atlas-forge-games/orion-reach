"""Real pointer/keyboard controls and tactical actions through the zoomed camera."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
import pygame as pg

from orion.app import App
from orion import combat_camera as camera
from orion import combat_geometry as geometry
from orion.combat_simulator import CombatSimulator
from orion.model import GameState
from test_combat import encounter


class CombatZoomTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.app = CombatSimulator(Path(self.folder.name), capture=True)
        self.app.window = pg.display.set_mode((980, 690), pg.RESIZABLE)
        self.app.present()
        self.app.game = encounter()
        self.app.go('combat')
        self.app.render()

    def tearDown(self):
        self.app.audio.close()
        pg.quit()
        self.folder.cleanup()

    def physical(self, point):
        v = self.app.viewport
        return (round(v.x+point[0]*v.w/1440), round(v.y+point[1]*v.h/900))

    def mouse(self, kind, point, button=1):
        self.app.handle_event(pg.event.Event(kind, pos=self.physical(point), button=button))

    def click(self, point):
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.mouse(kind, point)
        self.app.render()

    def click_button(self, key):
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        self.assertTrue(button.enabled, key)
        self.click(button.rect.center)

    def key(self, key, mod=0):
        self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=key, mod=mod))
        self.app.render()

    def test_multicell_ship_selects_and_inspects_from_its_last_cell(self):
        self.app.game = encounter(own=('battleship', 'frigate'), enemy=('titan',), close=False)
        self.app.reset_combat_view()
        ship = self.app.game.combat.ship(1)
        width, height = geometry.size(ship)
        for zoom in (.5, 1.0, 2.0):
            self.app.combat_zoom = zoom
            camera.reveal(self.app, geometry.cells(ship))
            self.app.render()
            point = camera.view(self.app).project((ship.x+width-1, ship.y+height-1))
            self.click(point)
            self.assertEqual(self.app.combat_ship_id, ship.id)
            self.mouse(pg.MOUSEBUTTONDOWN, point, 3)
            self.assertEqual(self.app.dialog['combat_ship_info'], ship.id)
            self.app.cancel_dialog()

    def test_wheel_preserves_cursor_anchor_and_limits_zoom_without_changing_combat(self):
        before = self.app.game.to_dict()
        point = (470, 440)
        self.app.mouse = point
        world = camera.view(self.app).unproject(point)
        self.app.handle_event(pg.event.Event(pg.MOUSEWHEEL, y=2, x=0))
        self.assertEqual(self.app.combat_zoom, 1.5)
        self.assertAlmostEqual(camera.view(self.app).unproject(point)[0], world[0])
        self.assertAlmostEqual(camera.view(self.app).unproject(point)[1], world[1])
        self.app.zoom_combat(100)
        self.assertEqual(self.app.combat_zoom, 3)
        self.app.zoom_combat(-100)
        self.assertEqual(self.app.combat_zoom, .5)
        self.assertEqual(camera.view(self.app).project((11.5, 6)), camera.BOARD.center)
        self.app.mouse = (1250, 450)  # Sidebar wheels do not change the battlefield.
        self.app.handle_event(pg.event.Event(pg.MOUSEWHEEL, y=1, x=0))
        self.assertEqual(self.app.combat_zoom, .5)
        self.assertEqual(self.app.game.to_dict(), before)
        self.assertEqual(GameState.from_dict(before), self.app.game)

    def test_buttons_keyboard_pan_and_reset_work_in_the_campaign_too(self):
        self.app.audio.close()
        self.app = App(Path(self.folder.name)/'campaign', capture=True)
        self.app.game = encounter(own=('frigate',)*100, enemy=('frigate',)*100, close=False)
        self.app.go('combat'); self.app.present(); self.app.render()
        before = self.app.game.to_dict()
        self.click_button('combat_zoom_in')
        self.assertEqual(self.app.combat_zoom, 1.25)
        self.key(pg.K_KP_PLUS)
        self.assertEqual(self.app.combat_zoom, 1.5)
        old_x = self.app.combat_camera_col
        self.key(pg.K_RIGHT, pg.KMOD_SHIFT)
        self.assertGreater(self.app.combat_camera_col, old_x)
        self.key(pg.K_PAGEDOWN)
        self.assertGreater(self.app.combat_camera_row, 0)
        self.key(pg.K_0)
        self.assertEqual(self.app.combat_zoom, 1)
        self.assertEqual(self.app.combat_camera_col, 0)
        self.assertEqual(self.app.game.to_dict(), before)

    def test_middle_drag_pans_and_focus_loss_releases_it(self):
        self.app.zoom_combat(3)
        before = self.app.game.to_dict()
        x, y = self.app.combat_camera_col, self.app.combat_camera_row
        self.mouse(pg.MOUSEBUTTONDOWN, (500, 420), 2)
        self.mouse(pg.MOUSEMOTION, (420, 370))
        self.assertGreater(self.app.combat_camera_col, x)
        self.assertGreater(self.app.combat_camera_row, y)
        self.app.handle_event(pg.event.Event(pg.WINDOWFOCUSLOST))
        stopped = (self.app.combat_camera_col, self.app.combat_camera_row)
        self.mouse(pg.MOUSEMOTION, (600, 450))
        self.assertEqual((self.app.combat_camera_col, self.app.combat_camera_row), stopped)
        self.assertEqual(self.app.game.to_dict(), before)

    @patch('orion.combat.accuracy_breakdown', new=lambda *_: {'chance': 100})
    def test_zoomed_move_target_and_fire_use_world_cells_and_keep_animation_alignment(self):
        self.app.zoom_combat(2, camera.view(self.app).project((4, 4)))
        self.app.render()
        self.click(camera.view(self.app).project((7, 4)))
        self.assertEqual(self.app.game.combat.ship(1).position, (7, 4))
        effect = self.app.combat_animation
        self.assertEqual(effect.path[0], (4, 4))
        self.app.time += 2; self.app.update_combat(); self.app.render()
        self.click(camera.view(self.app).project((13, 4)))
        self.assertEqual(self.app.combat_target_id, 2)
        self.click_button('combat_fire')
        self.assertEqual(self.app.game.combat.ship(2).hull, 15)
        effect = self.app.combat_animation
        elapsed = effect.elapsed
        before = self.app.game.to_dict()
        self.app.zoom_combat(3)
        camera.reveal(self.app, effect.path)
        with patch.object(effect, 'draw', wraps=effect.draw) as draw:
            self.app.render()
        self.assertEqual(draw.call_args.kwargs['target'], camera.view(self.app).project((13, 4)))
        self.assertEqual((effect.elapsed, self.app.game.to_dict()), (elapsed, before))
        self.assertTrue(all(camera.BOARD.contains(b.rect) for b in self.app.buttons
                            if b.key.startswith(('combat_cell_', 'combat_ship_'))))

    def test_enemy_inspection_and_moving_ship_inspection_follow_the_zoomed_camera(self):
        self.app.zoom_combat(5)
        camera.reveal(self.app, ((13, 4),))
        self.app.render()
        before = self.app.game.to_dict()
        self.mouse(pg.MOUSEBUTTONDOWN, camera.view(self.app).project((13, 4)), 3)
        self.app.render()
        self.assertEqual(self.app.dialog['combat_ship_info'], 2)
        zoom = self.app.combat_zoom
        self.key(pg.K_MINUS)
        self.assertEqual(self.app.combat_zoom, zoom)
        self.app.time += 20; self.app.update_combat()
        self.assertEqual(self.app.game.to_dict(), before)
        self.key(pg.K_ESCAPE)
        self.app.reset_combat_camera()
        self.app.move_combat_ship(7, 4)
        effect = self.app.combat_animation
        effect.elapsed = effect.duration/2
        self.app.zoom_combat(2, camera.view(self.app).project(effect.moving_position()))
        self.app.render()
        self.mouse(pg.MOUSEBUTTONDOWN, camera.view(self.app).project(effect.moving_position()), 3)
        self.assertEqual(self.app.dialog['combat_ship_info'], 1)
        elapsed = effect.elapsed
        self.app.time += 20; self.app.update_combat()
        self.assertEqual(effect.elapsed, elapsed)

    def test_camera_change_discards_stale_movement_hitboxes_and_next_ship_reveals_both_axes(self):
        before = self.app.game.to_dict()
        old_destination = camera.view(self.app).project((7, 4))
        self.app.zoom_combat(3)
        self.click(old_destination)  # No render between the camera change and click.
        self.assertEqual(self.app.game.to_dict(), before)
        self.app.game = encounter(own=('frigate',)*100, enemy=('frigate',)*100, close=False)
        self.app.reset_combat_view(); self.app.go('combat')
        self.app.zoom_combat(5)
        self.app.pan_combat(100, dx=100)
        self.app.next_combat_ship()
        ship = self.app.game.combat.ship(self.app.combat_ship_id)
        self.assertTrue(camera.BOARD.contains(camera.view(self.app).cell_rect(ship.position)))

    def test_each_zoom_level_renders_planets_ordnance_and_clipped_click_targets(self):
        from tools.preview_planetary_combat import scenario
        self.app.game, earth, mars = scenario()
        self.app.reset_combat_view(); self.app.go('combat')
        base = next(s for s in self.app.game.combat.ships if s.kind == 'missile_base' and s.owner == 'player')
        target = next(s for s in self.app.game.combat.ships if s.kind == 'missile_base' and s.owner == 'rival')
        self.app.combat_ship_id, self.app.combat_target_id = base.id, target.id
        self.app.combat_action('fire')
        self.app.game.combat_end_turn()
        flights = self.app.game.combat_end_turn('rival')
        self.app.after_combat_action({'kind': 'end_turn', 'flights': flights})
        effect = self.app.combat_animation
        before = self.app.game.to_dict()
        for level in camera.ZOOM_LEVELS:
            self.app.combat_zoom = level
            camera.clamp(self.app)
            with patch.object(effect, 'draw', wraps=effect.draw) as draw:
                self.app.render()
            self.assertIn(base.id, draw.call_args.kwargs['anchors'])
            self.assertEqual(draw.call_args.kwargs['planet_explosion_scale'], .35*level)
            self.assertEqual(self.app.game.to_dict(), before)
            self.assertTrue(all(camera.BOARD.contains(b.rect) for b in self.app.buttons
                                if b.key.startswith(('combat_cell_', 'combat_ship_'))))


if __name__ == '__main__':
    unittest.main()
