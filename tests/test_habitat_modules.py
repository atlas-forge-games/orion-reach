"""Real mouse paths through module construction, management and Hub recruitment."""
import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from orion import motherships, specialists, production_breakdown
from orion.model import GameState
from test_motherships import campaign


class HabitatModuleFlowTests(unittest.TestCase):
    def setUp(self):
        import pygame as pg
        from orion.app import App
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(folder.name), capture=True)
        self.addCleanup(self.app.audio.close)
        self.app.game = self.game = campaign()
        self.ship = motherships.homes(self.game)[0]
        self.home = self.ship.habitat
        self.home.buildings = ['hydroponic_farm', 'factory', 'research_lab', 'mine', 'solar_array']
        self.home.construction_queue.clear()
        self.home.trade_goods = True
        self.game.credits = self.game.resources = 10000
        self.app.open_mothership(self.ship.id)
        self.app.present()

    def click(self, key):
        import pygame as pg
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        self.assertTrue(button.enabled, key)
        v = self.app.viewport
        x, y = button.rect.center
        pos = (round(v.x+x*v.w/1440), round(v.y+y*v.h/900))
        for event in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(event, button=1, pos=pos))
            self.app.render()

    def drawn_text(self):
        from orion.ui import text_image
        with patch('orion.ui.text_image', wraps=text_image) as drawn:
            self.app.render()
        return '\n'.join(str(c.args[0]) for c in drawn.call_args_list)

    def test_bays_open_construction_queue_and_existing_module_controls(self):
        self.click('mothership_module_5')
        self.assertEqual(self.app.screen, 'production')
        self.assertIn('MODULES', self.drawn_text())
        self.click('production_build_trade_center')
        self.assertEqual(self.home.construction_queue[-1].item_id, 'trade_center')
        self.assertIn('Commerce module', self.drawn_text())
        self.click('production_return')
        self.click('mothership_module_5')
        self.assertEqual((self.app.screen, self.app.colony_slot), ('colony', 5))
        self.click('cancel_construction')
        self.assertFalse(self.home.construction_queue)
        self.click('colony_back')
        self.click('mothership_module_1')
        self.assertIn('Industry module', self.drawn_text())
        before = self.game.planet_yields(self.home)[0]
        self.click('toggle_building')
        self.assertIn(1, self.home.disabled_buildings)
        self.assertLess(self.game.planet_yields(self.home)[0], before)
        self.click('toggle_building')
        self.assertEqual(self.game.planet_yields(self.home)[0], before)

    def test_built_hub_opens_hiring_and_assigns_leader_to_home(self):
        self.game.queue_building(self.ship.system_id, self.home.id, 'space_hub')
        self.game.buy_construction(self.ship.system_id, self.home.id)
        specialists.advance_visitors(self.game)
        self.assertIn((self.ship.system_id, self.home.id), specialists.hubs(self.game))
        leader = next(p for p in specialists.visitors(self.game) if p.spec.role == 'leader')
        self.click('mothership_module_5')
        self.assertEqual(self.app.screen, 'specialists')
        self.click('specialist_select_'+leader.id)
        credits = self.game.credits
        self.click('specialist_hire')
        self.assertEqual(self.game.credits, credits-leader.spec.hiring_fee)
        self.click(f'specialist_assign_{self.ship.system_id}_{self.home.id}')
        self.assertEqual((leader.owner, leader.planet_id), ('player', self.home.id))
        self.assertTrue(specialists.colony_effects(self.game, self.home))
        self.app.close_specialists()
        self.assertEqual((self.app.screen, self.game.selected_planet), ('planet', self.home.id))
        loaded = GameState.from_dict(self.game.to_dict())
        self.assertEqual(specialists.person(loaded, leader.id).planet_id, self.home.id)
        self.assertIn((self.ship.system_id, self.home.id), specialists.hubs(loaded))
        self.click('mothership_facilities')
        self.click('colony_slot_5')
        self.click('toggle_building')
        self.assertNotIn((self.ship.system_id, self.home.id), specialists.hubs(self.game))
        self.click('colony_space_hub')
        self.assertEqual(self.app.screen, 'specialists')
        self.assertFalse(specialists.visitors(self.game))
        self.app.close_specialists()
        self.assertEqual(self.app.screen, 'colony')

    def test_existing_ids_saves_and_economy_survive_display_change(self):
        self.game.queue_building(self.ship.system_id, self.home.id, 'trade_center')
        saved = self.game.to_dict()
        self.app.game = self.game = GameState.from_dict(saved)
        self.home = self.game.planet_at(self.ship.system_id, self.home.id)
        for screen in ('planet', 'colony', 'production', 'shipyard', 'empire'):
            self.app.go(screen)
            drawn = self.drawn_text()
            self.assertIn('Commerce module', drawn)
        for kind, name in (('industry', 'Industry module'), ('research', 'Research module'),
                           ('mining', 'Extraction module'), ('food', 'Farming module')):
            self.assertIn(name, '\n'.join(production_breakdown.describe(self.game, self.home, kind).lines))
        self.assertEqual(self.game.to_dict(), saved)
        self.app.game = campaign(race_id='terran')
        self.app.game.selected_system, self.app.game.selected_planet = 0, 2
        self.app.go('colony')
        drawn = self.drawn_text()
        self.assertIn('COLONY MANAGEMENT', drawn)
        self.assertIn('Factory', drawn)
        self.assertNotIn('Industry module', drawn)


if __name__ == '__main__':
    unittest.main()
