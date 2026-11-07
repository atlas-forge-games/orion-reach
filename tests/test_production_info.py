"""Production inspection is read-only, including scaled cards and active modes."""
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
from orion.model import new_game
from orion.production import TRADE_GOODS_PERCENT
from scenarios import use_research_layout


class ProductionInfoTests(unittest.TestCase):
    def setUp(self):
        use_research_layout(self)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.app = App(Path(tmp.name), capture=True)
        self.addCleanup(pg.quit)
        self.addCleanup(self.app.audio.close)
        self.app.settings['animated_background'] = self.app.settings['autosave'] = False
        self.app.game = new_game(seed=12, random_starts=False, with_ai=False,
                                 with_guardians=False, with_black_holes=False,
                                 with_tombs=False, with_encounters=False, fog_of_war=False)
        self.planet = self.app.game.planet_at(0, 2)
        self.app.open_planet(2)
        self.app.open_production()
        self.frame()

    def frame(self):
        self.app.render()
        self.app.present()

    def click_rect(self, rect, button=3):
        self.app.display_view.ensure_visible(rect)
        self.frame()
        pos = self.app.window_pos(rect.center)
        self.assertTrue(self.app.window.get_rect().collidepoint(pos))
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, button=button, pos=pos))
        self.frame()

    def click_button(self, key, button=1):
        self.frame()
        self.click_rect(next(b.rect for b in self.app.buttons if b.key == key), button)

    def inspect(self, identifier):
        self.frame()
        self.click_rect(next(rect for item, rect in self.app.production_info_regions if item == identifier))

    def dismiss(self, key=pg.K_ESCAPE):
        self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=key, mod=0))
        self.frame()
        self.assertIsNone(self.app.dialog)

    def test_card_and_queue_button_inspection_preserve_orders_at_both_scales(self):
        for size, scale in (((1920, 1080), 100), ((1280, 800), 175)):
            with self.subTest(size=size, scale=scale):
                self.app.window = pg.display.set_mode(size)
                self.app.settings['ui_scale'] = scale
                self.frame()
                self.app.focus = 'production_build_factory'
                before = self.app.game.to_dict()
                with patch.object(self.app, 'save_game', side_effect=AssertionError('Inspection saved')):
                    self.inspect('factory')
                    info = self.app.dialog['building_info']
                    body = ' '.join(text for _, text in info.sections)
                    self.assertEqual(info.title, 'Factory')
                    self.assertIn('+4 IND', body)
                    self.assertIn('+1 IND/worker', body)
                    self.assertIn('3 energy demand', body)
                    self.assertIn('45 Resources', body)
                    self.assertEqual(self.app.game.to_dict(), before)
                    self.assertEqual(self.app.display_view.maximum, [0, 0])
                    self.assertEqual(self.app.display_view.offset, [0, 0])
                    for button in self.app.buttons:
                        physical = self.app.canvas.rect(button.rect).move(self.app.viewport.topleft)
                        self.assertTrue(self.app.window.get_rect().contains(physical))
                    self.dismiss()
                    self.assertEqual(self.app.focus, 'production_build_factory')
                    self.click_button('production_build_factory', button=3)
                    self.assertIn('building_info', self.app.dialog)
                    self.app.handle_event(pg.event.Event(pg.MOUSEBUTTONUP, button=3, pos=(0, 0)))
                    self.frame()
                    self.assertIsNone(self.app.dialog)
                    self.assertEqual(self.app.game.to_dict(), before)

    def test_queued_building_can_be_inspected_without_prioritizing_or_cancelling(self):
        self.click_button('production_build_factory')
        self.click_button('production_build_mine')
        self.assertEqual([p.item_id for p in self.planet.construction_queue], ['factory', 'mine'])
        before = self.app.game.to_dict()
        self.click_button('production_priority_1', button=3)
        self.assertEqual(self.app.dialog['building_info'].identifier, 'mine')
        self.assertEqual(self.app.game.to_dict(), before)
        self.dismiss()
        self.click_button('production_priority_1')
        self.assertEqual(self.planet.construction_queue[0].item_id, 'mine')

    def test_trade_goods_details_are_available_even_when_active_and_keep_progress(self):
        self.click_button('production_build_factory')
        self.planet.construction_queue[0].progress = 7
        for active in (False, True):
            with self.subTest(active=active):
                self.app.window = pg.display.set_mode((1280, 800))
                self.app.settings['ui_scale'] = 175
                before = self.app.game.to_dict()
                self.inspect('trade_goods')
                self.assertEqual(self.app.dialog['title'], 'Trade Goods')
                self.assertIn(f'{TRADE_GOODS_PERCENT}%', self.app.dialog['body'])
                self.assertIn('Queued projects keep their progress', self.app.dialog['body'])
                self.assertEqual(self.app.game.to_dict(), before)
                self.dismiss()
                if not active:
                    self.click_button('production_build_trade_goods')
                    self.assertTrue(self.planet.trade_goods)
                    self.assertEqual(self.planet.construction_queue[0].progress, 7)
                else:
                    self.click_button('production_build_trade_goods', button=3)
                    self.assertEqual(self.app.dialog['production_info'], 'trade_goods')
                    self.app.handle_event(pg.event.Event(pg.MOUSEBUTTONUP, button=3, pos=(0, 0)))
                    self.frame()
                    self.assertIsNone(self.app.dialog)
                    self.assertTrue(self.planet.trade_goods)

    def test_paged_card_hit_regions_follow_the_visible_building(self):
        previous = {item for item, _ in self.app.production_info_regions if item != 'trade_goods'}
        self.click_button('catalog_next')
        current = {item for item, _ in self.app.production_info_regions if item != 'trade_goods'}
        self.assertTrue(current)
        self.assertFalse(current & previous)
        item = next(iter(current))
        before = self.app.game.to_dict()
        self.inspect(item)
        self.assertEqual(self.app.dialog['building_info'].identifier, item)
        self.assertEqual(self.app.game.to_dict(), before)

    def test_mothership_card_uses_module_name_and_keeps_picker_open(self):
        self.app.game = new_game(seed=12, random_starts=False, race_id='wanderers', with_ai=False,
                                 with_guardians=False, with_black_holes=False,
                                 with_tombs=False, with_encounters=False)
        home = next(ship for ship in self.app.game.ships if ship.habitat)
        home.habitat.buildings = []
        home.habitat.construction_queue = []
        self.app.open_mothership(home.id)
        self.app.open_production()
        self.frame()
        before = self.app.game.to_dict()
        self.inspect('factory')
        info = self.app.dialog['building_info']
        self.assertEqual(info.title, 'Industry module')
        self.assertTrue(info.habitat)
        self.assertEqual(self.app.game.to_dict(), before)
        self.dismiss()
        self.assertEqual(self.app.screen, 'production')


if __name__ == '__main__':
    unittest.main()
