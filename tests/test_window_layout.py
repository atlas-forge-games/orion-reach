"""Window fitting, spatial geometry and actual input after panels wrap."""
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')

import pygame as pg
from orion.app import App, MAP
from orion.combat_camera import BOARD
from orion.galaxy_system_view import SYSTEM_PANEL
from orion.window_layout import reference_layout
from tools.preview_all_screens import campaign, screen_states


class WindowLayoutTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(folder.name), capture=True)
        self.addCleanup(self.app.audio.close)
        self.app.settings['autosave'] = self.app.settings['animated_background'] = False
        self.app.game = campaign()

    def frame(self):
        self.app.render()
        self.app.present()

    def click(self, key):
        app = self.app
        button = next(b for b in app.buttons if b.key == key)
        self.assertTrue(button.enabled)
        app.display_view.ensure_visible(button.rect)
        self.frame()
        pos = app.canvas.rect(button.rect).move(app.viewport.topleft).center
        self.assertTrue(app.window.get_rect().collidepoint(pos))
        for kind in (pg.MOUSEBUTTONDOWN,pg.MOUSEBUTTONUP):
            app.handle_event(pg.event.Event(kind,button=1,pos=pos))
        self.frame()

    def test_all_widescreen_views_fill_window_and_hit_their_painted_buttons(self):
        self.app.window = pg.display.set_mode((1920,1080))
        for name in screen_states(self.app):
            with self.subTest(view=name):
                self.frame()
                self.assertEqual(self.app.viewport.w, 1920)
                self.assertEqual(self.app.viewport.x, 0)
                for button in self.app.buttons:
                    visible = self.app.canvas.rect(button.rect).move(self.app.viewport.topleft)
                    if self.app.window.get_rect().contains(visible):
                        self.assertTrue(button.rect.collidepoint(self.app.logical_pos(visible.center)), button.key)

    def test_galaxy_sidebar_wraps_and_actual_planet_and_footer_clicks_work(self):
        app = self.app
        app.window = pg.display.set_mode((1080,720))
        app.settings['ui_scale'] = 175
        app.go('galaxy')
        self.frame()
        self.assertEqual(app.display_view.maximum[0], 0)
        self.assertGreaterEqual(app.canvas.rect(SYSTEM_PANEL).top, app.canvas.rect(MAP).bottom)
        self.click('galaxy_world_2')
        self.assertIn(app.screen,('planet','colony'))
        self.assertEqual(app.game.selected_planet, 2)
        self.click('galaxy_map')
        self.assertEqual(app.screen,'galaxy')

    def test_map_distances_and_combat_cells_have_one_scale_on_both_axes(self):
        for screen, bounds in (('galaxy',MAP), ('combat',BOARD)):
            for size in ((2133,900),(1440,1700),(823,514)):
                with self.subTest(screen=screen,size=size):
                    layout = reference_layout((1440,900),size,screen)
                    x,y = bounds.center
                    center = layout.place((x,y))
                    dx = layout.place((x+42,y))[0]-center[0]
                    dy = layout.place((x,y+42))[1]-center[1]
                    self.assertAlmostEqual(dx,dy,delta=.1)
                    self.assertAlmostEqual(layout.unplace(center)[0], x)
                    self.assertAlmostEqual(layout.unplace(center)[1], y)

    def test_large_text_research_choices_and_galaxy_shortcut_after_resize(self):
        app = self.app
        app.go('research')
        app.settings['ui_scale'] = 175
        app.window = pg.display.set_mode((1280,800))
        self.frame()
        branch = next(b.key for b in app.buttons if b.key.startswith('research_branch_'))
        self.click(branch)
        self.assertFalse(app.research_overview)
        app.window = pg.display.set_mode((1920,1080))
        app.settings['ui_scale'] = 100
        self.frame()
        self.click('galaxy_map')
        self.assertEqual(app.screen,'galaxy')
        self.assertEqual(app.canvas.pixel_size,(1920,1080))

    def test_confirmation_keeps_its_page_layout_and_scroll_position(self):
        app = self.app
        app.window = pg.display.set_mode((1080,720))
        app.settings['ui_scale'] = 175
        app.go('galaxy')
        self.frame()
        app.display_view.scroll(dy=400)
        self.frame()
        page, scroll = app.canvas, tuple(app.display_view.offset)
        app.confirm('Leave?', 'Return to the menu?', 'Return', app.to_menu)
        self.frame()
        self.assertIs(app.page_canvas,page)
        self.assertIsNot(app.canvas,page)
        self.assertEqual(app.canvas.pixel_size,app.window.get_size())
        self.click('dialog_cancel')
        self.assertIsNone(app.dialog)
        self.assertIs(app.canvas,page)
        self.assertEqual(tuple(app.display_view.offset),scroll)

    def test_portrait_window_wraps_the_map_and_uses_the_same_type_scale_on_empire(self):
        app = self.app
        app.window = pg.display.set_mode((900,1200))
        app.go('galaxy')
        self.frame()
        scale = app.canvas.scale
        self.assertGreaterEqual(app.canvas.rect(SYSTEM_PANEL).top, app.canvas.rect(MAP).bottom)
        self.assertEqual(app.viewport.w, 900)
        app.go('empire')
        self.frame()
        self.assertEqual(app.canvas.scale, scale)
        self.assertEqual(app.viewport.w, 900)
