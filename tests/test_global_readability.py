"""Readable legacy labels, fitting controls, hover details and screen coverage."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
import pygame as pg
from orion.display import Canvas, DisplayView
from orion import ui


class TypographyTests(unittest.TestCase):
    def setUp(self):
        pg.display.init()
        pg.font.init()
        pg.display.set_mode((640, 480))
        ui.font.cache_clear()
        ui.text_image.cache_clear()
        DisplayView()
        self.addCleanup(pg.quit)

    def test_legacy_labels_measure_and_render_at_the_same_readable_size(self):
        for size in range(8, 15):
            with self.subTest(size=size):
                self.assertEqual(ui.font(size).size('Research'), ui.font(14).size('Research'))
                self.assertEqual(ui.text_image('Research', size, ui.INK).get_size(),
                                 ui.text_image('Research', 14, ui.INK).get_size())
                value = ui.shorten('A long research project', 130, size)
                self.assertLessEqual(ui.font(size).size(value)[0], 130)
                self.assertEqual(value.full_text, 'A long research project')

    def test_floor_is_not_applied_again_to_native_pixel_fonts(self):
        for scale in (.5, 8/9, 1.2, 1.75):
            with self.subTest(scale=scale):
                canvas = Canvas((320, 160), scale)
                canvas.fill((0, 0, 0))
                ui.text(canvas, 'Food 16 / 12', (12, 16), 9, ui.INK)
                expected = pg.Surface(canvas.pixel_size)
                expected.fill((0, 0, 0))
                face = pg.font.Font(str(ui.ASSETS/'fonts'/'DejaVuSans.ttf'), round(14*scale))
                expected.blit(face.render('Food 16 / 12', True, ui.INK), (round(12*scale), round(16*scale)))
                self.assertEqual(pg.image.tobytes(canvas, 'RGB'), pg.image.tobytes(expected, 'RGB'))

    def test_small_controls_keep_visible_labels_inside_their_hit_regions(self):
        canvas = Canvas((320, 160))
        for label, width, height in (('←', 36, 28), ('+', 32, 32), ('−', 40, 28),
                                      ('+ Enemy', 87, 35), ('Infrastructure', 151, 26)):
            button = ui.Button('control', label, pg.Rect(10, 10, width, height), lambda: None)
            drawn = []
            original = ui.text
            def record(*args, **kwargs):
                rect = original(*args, **kwargs)
                drawn.append((args[1], rect))
                return rect
            with patch('orion.ui.text', side_effect=record):
                button.draw(canvas)
            self.assertTrue(drawn[0][0], label)
            self.assertEqual(drawn[0][0], label)
            self.assertTrue(button.rect.contains(drawn[0][1]), (label, drawn))

    def test_wrapping_handles_long_identifiers_and_minimum_line_height(self):
        value = 'A '+('VeryLongUnbrokenName'*10)+' ends here'
        lines = ui.wrapped_lines(value, 180, 9)
        self.assertTrue(all(ui.font(14).size(line)[0] <= 180 for line in lines))
        canvas = Canvas((240, 600))
        end = ui.paragraph(canvas, value, (10, 10), 180, size=9, leading=11)
        self.assertGreaterEqual(end-10, len(lines)*(ui.font(14).get_linesize()+2))

    def test_repeated_shortening_retains_full_text_and_clipped_hover_region(self):
        original = 'A complete project name with more details'
        value = ui.shorten(original, 160, 14)
        value = ui.shorten(value, 180, 14)
        canvas = Canvas((240, 120))
        canvas.text_regions = []
        canvas.set_clip((0, 0, 90, 120))
        ui.text(canvas, value, (10, 20), 14)
        rect, full = canvas.text_regions[0]
        self.assertEqual(full, original)
        self.assertLessEqual(rect.right, 90)


class AllScreenTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.folder.name), capture=True)
        self.addCleanup(self.app.audio.close)

    def test_every_screen_and_dialog_renders_at_native_and_enlarged_sizes(self):
        from orion.app import GAME_SCREENS
        from tools.preview_all_screens import screen_states
        visited = set()
        for name in screen_states(self.app):
            for window, scale in (((1440, 900), 100), ((1280, 800), 175), ((1920, 1080), 125)):
                with self.subTest(screen=name, window=window, scale=scale):
                    self.app.window = pg.display.set_mode(window)
                    self.app.settings['ui_scale'] = scale
                    economy = (self.app.game.turn, self.app.game.credits, self.app.game.resources, self.app.game.research)
                    self.app.render()
                    self.app.present()
                    visited.add(self.app.screen)
                    self.assertEqual(economy, (self.app.game.turn, self.app.game.credits, self.app.game.resources, self.app.game.research))
                    self.assertIsInstance(self.app.canvas, Canvas)
                    self.assertEqual(self.app.canvas.pixel_size, self.app.viewport.size)
                    self.assertGreaterEqual(self.app.viewport.w, window[0]-1)
                    self.assertGreaterEqual(self.app.viewport.h, window[1]-1)
        self.assertFalse(set(GAME_SCREENS)-visited)

    def test_hover_reveals_full_label_inside_a_scrolled_zoomed_view(self):
        from tools.preview_all_screens import campaign
        app = self.app
        app.game = campaign()
        app.game.empire_name = 'W'*32
        app.go('galaxy')
        app.window = pg.display.set_mode((1280, 800))
        app.settings['ui_scale'] = 175
        app.keyboard_mode = False
        app.render()
        region, original = next((r, value) for r, value in app.canvas.text_regions if value == app.game.empire_name)
        app.display_view.ensure_visible(region)
        app.render()
        app.present()
        pos = app.canvas.rect(region).move(app.viewport.topleft).center
        app.handle_event(pg.event.Event(pg.MOUSEMOTION, pos=pos))
        app.time = 1
        app.render()
        self.assertIsNone(app.text_tooltip_rect)
        buttons = [(b.key, b.rect.copy()) for b in app.buttons]
        before = app.game.to_dict()
        app.time = 1.5
        app.render()
        self.assertIsNotNone(app.text_tooltip_rect)
        physical = app.canvas.rect(app.text_tooltip_rect).move(app.viewport.topleft)
        self.assertTrue(app.window.get_rect().contains(physical))
        self.assertEqual(app.text_hover[0][1], original)
        self.assertEqual(buttons, [(b.key, b.rect) for b in app.buttons])
        self.assertEqual(before, app.game.to_dict())
        app.mouse = (-1, -1)
        app.render()
        self.assertIsNone(app.text_tooltip_rect)


class UtilityScreenTests(unittest.TestCase):
    def test_editor_resizes_without_resampling_and_keeps_click_coordinates(self):
        from orion.balance_editor import BalanceEditor
        with tempfile.TemporaryDirectory() as folder:
            editor = BalanceEditor(Path(folder)/'balance.json')
            try:
                for window in ((1280, 800), (1920, 1080)):
                    editor.window = pg.display.set_mode(window)
                    editor.draw()
                    editor.present()
                    self.assertIsInstance(editor.canvas, Canvas)
                    self.assertEqual(editor.canvas.pixel_size, editor.viewport.size)
                    _, rect, _, _ = next(b for b in editor.buttons if b[0] == 'tree')
                    point = editor.canvas.point(rect.center)
                    pos = (point[0]+editor.viewport.x, point[1]+editor.viewport.y)
                    mapped = editor.coordinates(pos)
                    self.assertAlmostEqual(mapped[0], rect.centerx, delta=1)
                    self.assertAlmostEqual(mapped[1], rect.centery, delta=1)
                editor.tree_mode()
                editor.draw()
            finally:
                pg.quit()


if __name__ == '__main__':
    unittest.main()
