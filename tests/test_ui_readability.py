"""Native text, zoomed input, responsive pages and settings persistence."""
import json
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')

import pygame as pg
from orion.display import Canvas, DisplayView, UI_SCALES
from orion.storage import Storage
from orion.ui import ASSETS, INK, MUTED, CYAN, PANEL, text, font, text_image


class NativeDrawingTests(unittest.TestCase):
    def setUp(self):
        pg.display.init()
        pg.font.init()
        pg.display.set_mode((640, 480))
        font.cache_clear()
        text_image.cache_clear()
        DisplayView()
        self.addCleanup(pg.quit)

    def test_native_text_matches_direct_font_rasterization(self):
        canvas = Canvas((320, 160), 1.5)
        canvas.fill((0, 0, 0))
        text(canvas, 'Treasury: 439 CR', (12, 16), 18, INK)
        expected = pg.Surface((480, 240))
        expected.fill((0, 0, 0))
        face = pg.font.Font(str(ASSETS/'fonts'/'DejaVuSans.ttf'), 27)
        expected.blit(face.render('Treasury: 439 CR', True, INK), (18, 24))
        self.assertEqual(pg.image.tobytes(canvas, 'RGB'), pg.image.tobytes(expected, 'RGB'))

    def test_regular_surface_rendering_is_unchanged(self):
        canvas, ordinary = Canvas((160, 100)), pg.Surface((160, 100))
        for surface in (canvas, ordinary):
            surface.fill((0, 0, 0))
            pg.draw.rect(surface, INK, (10, 12, 90, 62), 2, border_radius=5)
            pg.draw.circle(surface, CYAN, (40, 40), 13, 2)
            pg.draw.lines(surface, MUTED, False, [(11, 90), (75, 85), (140, 90)], 2)
            text(surface, 'Native', (85, 22), 14)
        self.assertEqual(pg.image.tobytes(canvas, 'RGB'), pg.image.tobytes(ordinary, 'RGB'))

    def test_clipping_scales_with_text_and_primitives(self):
        canvas = Canvas((160, 100), 1.5)
        canvas.fill((0, 0, 0))
        canvas.set_clip((20, 20, 60, 40))
        pg.draw.rect(canvas, CYAN, (0, 0, 160, 100))
        text(canvas, 'This text crosses the clipping boundary', (8, 30), 18)
        raw = canvas
        self.assertEqual(pg.Surface.get_at(raw, (29, 45))[:3], (0, 0, 0))
        self.assertEqual(pg.Surface.get_at(raw, (120, 45))[:3], (0, 0, 0))
        self.assertEqual(pg.Surface.get_at(raw, (40, 32))[:3], CYAN)

    def test_panel_text_colors_have_at_least_45_to_1_contrast(self):
        def luminance(rgb):
            v = [n/255 for n in rgb]
            v = [n/12.92 if n <= .04045 else ((n+.055)/1.055)**2.4 for n in v]
            return .2126*v[0]+.7152*v[1]+.0722*v[2]
        for color in (INK, MUTED, CYAN):
            self.assertGreaterEqual((luminance(color)+.05)/(luminance(PANEL)+.05), 4.5)


class ReadabilityInterfaceTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        from orion.model import new_game
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.folder.name), capture=True)
        self.addCleanup(self.app.audio.close)
        self.app.game = new_game(seed=12, random_starts=False, with_ai=False,
                                  with_guardians=False, with_black_holes=False,
                                  with_tombs=False, with_encounters=False, fog_of_war=False)
        self.app.settings['autosave'] = False
        self.app.go('empire')

    def frame(self):
        self.app.render()
        self.app.present()

    def click(self, key):
        self.frame()
        button = next(b for b in self.app.buttons if b.key == key)
        self.app.display_view.ensure_visible(button.rect)
        self.frame()
        x, y = self.app.canvas.point(button.rect.center)
        pos = (x+self.app.viewport.x, y+self.app.viewport.y)
        self.assertTrue(self.app.window.get_rect().collidepoint(pos))
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, button=1, pos=pos))
            self.frame()

    def test_sizes_reflow_without_losing_controls_or_changing_game(self):
        before = self.app.game.to_dict()
        for size in ((1280, 800), (1440, 900), (1920, 1080)):
            self.app.window = pg.display.set_mode(size)
            for scale in UI_SCALES:
                with self.subTest(size=size, scale=scale):
                    self.app.settings['ui_scale'] = scale
                    self.frame()
                    controls = self.app.buttons
                    for i, button in enumerate(controls):
                        self.assertTrue(self.app.canvas.get_rect().contains(button.rect), button.key)
                        self.assertEqual(button.rect.collidelist([b.rect for b in controls[i+1:]]), -1, button.key)
                    self.assertLessEqual(self.app.canvas.pixel_size[0], size[0]+1)
                    self.assertTrue(any(b.key == 'end_turn' for b in controls))
                    self.assertEqual(self.app.game.to_dict(), before)

    def test_every_colony_is_reachable_once_after_resizing_and_sorting(self):
        colonies = [(s, p) for s in self.app.game.systems for p in s.worlds][:20]
        for i, (_, planet) in enumerate(colonies):
            planet.owner, planet.colonized = 'player', True
            planet.population = i+1
        self.app.sort_empire('population')
        expected = [f'empire_colony_{s.id}_{p.id}' for s, p in reversed(colonies)]
        for scale in UI_SCALES:
            with self.subTest(scale=scale):
                self.app.settings['ui_scale'] = scale
                self.app.empire_scroll.reset()
                self.app.focus = expected[0]
                self.app.keyboard_mode = True
                self.frame()
                collected = []
                for key in expected:
                    self.assertEqual(self.app.focus, key)
                    row = next(b for b in self.app.buttons if b.key == key)
                    self.assertTrue(self.app.empire_scroll.rect.contains(row.rect))
                    self.assertEqual(row.rect.h, self.app.empire_scroll.row_height-8)
                    collected.append(key)
                    self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_DOWN, mod=0))
                    self.frame()
                self.assertEqual(collected, expected)
                self.assertEqual(self.app.focus, 'galaxy_map')
                self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_TAB, mod=pg.KMOD_SHIFT))
                self.frame()
                self.assertEqual(self.app.focus, expected[-1])
                self.assertEqual(self.app.display_view.maximum, [0, 0])

    def test_scrolled_scaled_click_opens_the_correct_colony(self):
        self.app.settings['ui_scale'] = 175
        self.frame()
        row = next(b for b in self.app.buttons if b.key.startswith('empire_colony_'))
        _, _, system, planet = row.key.split('_')
        self.click(row.key)
        self.assertEqual(self.app.screen, 'planet')
        self.assertEqual((self.app.game.selected_system, self.app.game.selected_planet), (int(system), int(planet)))

    def test_footer_stays_visible_and_zoom_reset_works(self):
        self.app.settings['ui_scale'] = 175
        self.app.focus = 'end_turn'
        self.app.keyboard_mode = True
        self.frame()
        self.assertEqual(self.app.display_view.offset, [0, 0])
        button = next(b for b in self.app.buttons if b.key == self.app.focus)
        screen_rect = self.app.canvas.rect(button.rect).move(self.app.viewport.topleft)
        self.assertTrue(self.app.window.get_rect().contains(screen_rect))
        self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_0, mod=pg.KMOD_CTRL))
        self.frame()
        self.assertEqual(self.app.settings['ui_scale'], 100)

    def test_scale_settings_button_persists_and_load_preserves_campaign(self):
        before = self.app.game.to_dict()
        self.app.show_settings('empire')
        self.app.select_settings_section('interface')
        self.click('ui_scale_150')
        self.assertEqual(Storage(Path(self.folder.name)).load_settings()['ui_scale'], 150)
        self.assertEqual(self.app.game.to_dict(), before)
        self.click('ui_scale_100')
        self.assertEqual(self.app.settings['ui_scale'], 100)

    def test_scrollbar_drag_and_wheel_reach_bottom_without_clicking_colonies(self):
        for system in self.app.game.systems[:8]:
            for planet in system.worlds:
                planet.owner, planet.colonized, planet.population = 'player', True, 1
        self.app.settings['ui_scale'] = 175
        self.frame()
        view = self.app.empire_scroll
        track, thumb = view.scrollbar()
        start = self.app.window_pos(thumb.center)
        end = self.app.window_pos((thumb.centerx, track.bottom-2))
        self.app.handle_event(pg.event.Event(pg.MOUSEBUTTONDOWN, button=1, pos=start))
        self.app.handle_event(pg.event.Event(pg.MOUSEMOTION, pos=end))
        # Releasing over a colony must not open it.
        self.frame()
        row = next(b for b in self.app.buttons if b.key.startswith('empire_colony_'))
        self.app.handle_event(pg.event.Event(pg.MOUSEBUTTONUP, button=1,
                                            pos=self.app.window_pos(row.rect.center)))
        self.frame()
        self.assertEqual(view.offset, view.maximum)
        self.assertEqual(self.app.screen, 'empire')
        self.assertIsNone(view.drag)
        previous = view.offset
        self.app.handle_event(pg.event.Event(pg.MOUSEWHEEL, x=0, y=1))
        self.frame()
        self.assertLess(view.offset, previous)
        self.assertEqual(self.app.display_view.offset, [0, 0])

    def test_legacy_screens_zoom_and_keep_controls_accessible(self):
        self.app.settings['ui_scale'] = 175
        for screen, control in (('galaxy', 'open_empire'), ('research', 'open_fleets'), ('settings', 'settings_done')):
            self.app.go(screen)
            self.frame()
            target = next(b for b in self.app.buttons if b.key == control)
            self.app.keyboard_mode = True
            self.app.focus = control
            self.frame()
            physical = self.app.canvas.rect(target.rect).move(self.app.viewport.topleft)
            self.assertTrue(self.app.window.get_rect().contains(physical), screen)


class ScalePreferencesTests(unittest.TestCase):
    def test_missing_and_invalid_values_keep_safe_default(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Storage(Path(directory))
            self.assertEqual(store.load_settings()['ui_scale'], 100)
            for value in (True, 1.5, '175', 0, 101, 9999, None):
                (Path(directory)/'settings.json').write_text(json.dumps({'ui_scale': value}))
                self.assertEqual(store.load_settings()['ui_scale'], 100)
            for value in UI_SCALES:
                store.save_settings({'ui_scale': value})
                self.assertEqual(store.load_settings()['ui_scale'], value)


if __name__ == '__main__':
    unittest.main()
