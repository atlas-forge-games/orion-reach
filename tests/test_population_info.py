"""Displayed growth must match turn resolution and respect survey visibility."""

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

from orion import balance, exploration, population
from orion.app import App
from orion.model import new_game
from orion.population_info import POPULATION_RECT, describe, growth_millions, summary
from orion.ui import text


class PopulationInfoFixture(unittest.TestCase):
    def setUp(self):
        old, configured = balance.active_profile(), balance._configured_path
        self.addCleanup(lambda: balance.activate(old))
        self.addCleanup(lambda: setattr(balance, '_configured_path', configured))
        balance._configured_path = None
        balance.activate(balance.default_profile())

    def game(self, race='terran', **options):
        settings = dict(seed=2408, random_starts=False, race_id=race, with_ai=False,
                        with_guardians=False, with_tombs=False, with_black_holes=False,
                        with_encounters=False)
        settings.update(options)
        return new_game(**settings)


class PopulationInfoTests(PopulationInfoFixture):
    def test_displayed_rates_match_population_advance_for_each_growth_method(self):
        cases = [('terran', 'Terran', 2, 100, 16), ('terran', 'Ice', 5, 50, 16),
                 ('lithar', 'Terran', 2, 60, 32), ('xenonflora', 'Gaia', 2, 780, 20),
                 ('nexus', 'Ice', 0, 150, 16), ('aetheri', 'Volcanic', 0, 150, 16)]
        for race, biome, farmers, rate, capacity in cases:
            with self.subTest(race=race, biome=biome):
                game = self.game(race)
                world = game.headquarters()[1]
                world.biome, world.farmers, world.growth_progress = biome, farmers, 95
                before = game.to_dict()
                report = game.population_report(world)
                info = describe(game, world, live=True)
                self.assertEqual(info.rate_millions, rate)
                self.assertEqual(summary(world, report), f'8 billion (+{rate} mil / turn) / {capacity} billion max')
                self.assertEqual(game.to_dict(), before)
                future = deepcopy(world)
                population.advance(future, report)
                gained = (future.population-world.population)*1000
                gained += (future.growth_progress-world.growth_progress)*1000/population.GROWTH_THRESHOLD
                self.assertEqual(gained, rate)

    def test_capacity_and_food_shortage_show_zero_without_losing_existing_people(self):
        game = self.game()
        world = game.headquarters()[1]
        world.population = game.population_report(world).capacity
        self.assertEqual(describe(game, world, live=True).rate_millions, 0)
        self.assertIn('Population limit reached', '\n'.join(describe(game, world, live=True).lines))
        world.population, world.farmers, world.growth_progress = 8, 0, 75
        info = describe(game, world, live=True)
        self.assertEqual(info.rate_millions, 0)
        self.assertIn('progress are retained', '\n'.join(info.lines))
        population.advance(world, game.population_report(world))
        self.assertEqual((world.population, world.growth_progress), (8, 75))

    def test_swarm_starvation_overrides_growth_and_respects_one_billion_floor(self):
        game = self.game('skirr')
        world = game.headquarters()[1]
        world.biome, world.farmers, world.growth_progress = 'Barren', 0, 75
        info = describe(game, world, live=True)
        self.assertEqual(info.rate_millions, -1000)
        self.assertIn('(-1,000 mil / turn)', summary(world, game.population_report(world)))
        self.assertIn('growth progress resets', '\n'.join(info.lines))
        population.advance(world, game.population_report(world))
        self.assertEqual((world.population, world.growth_progress), (7, 0))
        world.population = 1
        self.assertEqual(growth_millions(game.population_report(world)), 0)
        population.advance(world, game.population_report(world))
        self.assertEqual(world.population, 1)

    def test_disabled_farms_and_mixed_species_use_real_local_effects(self):
        game = self.game()
        world = game.headquarters()[1]
        world.buildings = ['hydroponic_farm']
        self.assertEqual(describe(game, world, live=True).rate_millions, 250)
        world.disabled_buildings = [0]
        info = describe(game, world, live=True)
        self.assertEqual(info.rate_millions, 100)
        self.assertIn('Disabled or unpowered food facilities: Hydroponic farm.', '\n'.join(info.lines))
        game.race_id = 'serevan'
        world.biome, world.species = 'Ice', {'terran': 4, 'nexus': 4}
        info = describe(game, world, live=True)
        body = '\n'.join(info.lines)
        self.assertIn('Ice environment: 100%', body)
        self.assertIn('4 billion at 50% suitability', body)
        self.assertIn('4 billion at 150% suitability', body)
        self.assertIn('Assembly: 10%', body)
        self.assertEqual(info.rate_millions, game.population_report(world).growth_rate*10)

    def test_slaves_and_uncolonized_worlds_are_not_reported_as_native_growth(self):
        game = self.game('varkesh')
        world = game.headquarters()[1]
        world.slaves = 4
        info = describe(game, world, live=True)
        self.assertIn('4 billion slaves are additional workers', '\n'.join(info.lines))
        self.assertTrue(summary(world, game.population_report(world)).startswith('8 billion'))
        empty = next(p for p in game.systems[0].worlds if not p.colonized and not p.is_gas_giant)
        info = describe(game, empty, live=True)
        self.assertEqual(info.rate_millions, 0)
        self.assertIn('Establish a colony', '\n'.join(info.lines))


class PopulationInfoUITests(PopulationInfoFixture):
    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.app = App(Path(tmp.name), capture=True)
        self.addCleanup(pg.quit)
        self.addCleanup(self.app.audio.close)
        self.app.game = self.game(with_ai=True)
        self.world = self.app.game.planet_at(0, 2)
        self.app.open_planet(2)
        self.app.render()

    def click_population(self):
        x, y = pg.Rect(POPULATION_RECT).center
        view = self.app.viewport
        pos = (round(view.x+x*view.w/1440), round(view.y+y*view.h/900))
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, button=3, pos=pos))

    def test_population_header_refreshes_and_scaled_right_click_is_read_only(self):
        self.app.viewport = pg.Rect(71, 39, 960, 600)
        self.app.focus = 'worker_workers'
        self.app.worker_source, self.app.worker_count = 'workers', 2
        before = self.app.game.to_dict()
        with patch.object(self.app, 'save_game', side_effect=AssertionError('Inspection saved state')):
            self.click_population()
            self.assertEqual(self.app.dialog['population_info'].rate_millions, 100)
            self.app.render()
            self.click_population()
            self.assertIsNone(self.app.dialog)
            self.assertEqual(self.app.focus, 'worker_workers')
        self.assertEqual((self.app.worker_source, self.app.worker_count), ('workers', 2))
        self.assertEqual(self.app.game.to_dict(), before)
        self.world.farmers = 3
        with patch('orion.planet_view.text', wraps=text) as render_text:
            self.app.render()
            labels = [str(call.args[1]) for call in render_text.call_args_list]
        self.assertIn('8 billion (+200 mil / turn) / 16 billion max', labels)

    def test_stored_survey_never_reads_hidden_population_or_bonuses(self):
        game = self.app.game
        enemy = game.opponent
        sid, pid = enemy.home_system, enemy.home_planet
        world = game.planet_at(sid, pid)
        world.population = 8
        exploration.record_survey(game, sid, 'player')
        world.population = 15
        game.selected_system = sid
        self.app.open_planet(pid)
        self.assertFalse(game.system_visible(sid))
        with patch('orion.planet_view.text', wraps=text) as render_text:
            self.app.render()
            labels = [str(call.args[1]) for call in render_text.call_args_list]
        self.assertIn('8 billion (growth unknown) / max unknown', labels)
        before = game.to_dict()
        with (patch.object(game, 'bonuses_for', side_effect=AssertionError('Hidden bonuses')),
              patch.object(game, 'population_report', side_effect=AssertionError('Hidden population'))):
            self.click_population()
        info = self.app.dialog['population_info']
        self.assertFalse(info.live)
        self.assertIsNone(info.rate_millions)
        self.assertIn('Last observed population: 8 billion.', info.lines)
        self.assertEqual(game.to_dict(), before)
        self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_ESCAPE))
        self.assertIsNone(self.app.dialog)

    def test_mothership_uses_its_own_population_and_gas_giants_have_no_growth_control(self):
        self.app.game = game = self.game('wanderers')
        home = next(ship for ship in game.ships if ship.habitat)
        home.habitat.population = 12
        home.habitat.farmers = 4
        self.app.open_mothership(home.id)
        self.app.render()
        before = game.to_dict()
        self.click_population()
        info = self.app.dialog['population_info']
        self.assertIn('Population: 12 billion / 50 billion maximum · Growing', info.lines)
        self.assertIn('Habitat environment: 100%', '\n'.join(info.lines))
        self.assertEqual(game.to_dict(), before)
        self.app.cancel_dialog()
        self.app.game = game = self.game(fog_of_war=False)
        system, gas = next((s, p) for s in game.systems for p in s.worlds if p.is_gas_giant)
        game.selected_system = system.id
        self.app.open_planet(gas.id)
        self.app.render()
        self.assertFalse(any(b.key == 'population_info' for b in self.app.buttons))
        self.click_population()
        self.assertIsNone(self.app.dialog)

    def test_keyboard_activation_paging_and_close_restore_focus(self):
        self.app.game = game = self.game('varkesh')
        world = game.headquarters()[1]
        world.slaves = 4
        self.app.open_planet(world.id)
        self.app.render()
        self.app.focus, self.app.keyboard_mode = 'population_info', True
        self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_RETURN, mod=0))
        self.app.render()
        self.assertIsNotNone(self.app.dialog)
        next_page = next(b for b in self.app.buttons if b.key == 'dialog_output_next')
        self.app.activate(next_page)
        self.app.render()
        self.assertEqual(self.app.dialog['info_page'], 1)
        self.app.activate(next(b for b in self.app.buttons if b.key == 'dialog_cancel'))
        self.assertIsNone(self.app.dialog)
        self.assertEqual(self.app.focus, 'population_info')


if __name__ == '__main__':
    unittest.main()
