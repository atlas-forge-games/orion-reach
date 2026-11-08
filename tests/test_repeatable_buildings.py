"""Repeatable production, non-stacking staff bonuses and distinct saved sites."""
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

from orion import ai, colony_layout, economy, exploration, research
from orion.buildings import BUILDINGS, workforce_bonuses
from orion.building_info import describe_project
from orion.model import GameState, RuleError, SaveError, new_game
from orion.production_breakdown import describe as breakdown
from orion.storage import SAVE_VERSION, Storage
from scenarios import use_research_layout


def campaign(**kwargs):
    return new_game(seed=24, random_starts=False, with_ai=False, with_guardians=False,
                    with_black_holes=False, with_tombs=False, with_encounters=False,
                    fog_of_war=False, **kwargs)


class RepeatableBuildingTests(unittest.TestCase):
    def setUp(self):
        use_research_layout(self)
        self.game = campaign()
        self.planet = self.game.planet_at(0, 2)
        self.planet.farmers, self.planet.scientists, self.planet.miners = 2, 1, 1
        self.planet.trade_goods = False

    def test_extra_copies_add_only_base_output_and_charge_full_upkeep_and_power(self):
        g, p = self.game, self.planet
        for identifier, expected in [('factory', (4, 0, 0, 0, 0)),
                                     ('mine', (0, 0, 0, 0, 2)),
                                     ('research_lab', (0, 0, 4, 0, 0)),
                                     ('hydroponic_farm', (0, 0, 0, 4, 0)),
                                     ('trade_center', (0, 4, 0, 0, 0))]:
            with self.subTest(building=identifier):
                def outputs():
                    return (*research.gross_colony_yields(p, g.bonuses_for()),
                            g.population_report(p).produced, g.planet_resources(p))
                p.buildings = [identifier]
                before = outputs()
                staff, miner = workforce_bonuses(p), economy.miner_output(p)
                p.buildings.append(identifier)
                self.assertEqual(tuple(b-a for a, b in zip(before, outputs())), expected)
                self.assertEqual(workforce_bonuses(p), staff)
                self.assertEqual(economy.miner_output(p), miner)
                self.assertEqual(p.used_slots, 2)
                self.assertEqual(g.planet_maintenance(p), 2*BUILDINGS[identifier].maintenance)
                self.assertEqual(g.planet_energy(p).demand, 2*BUILDINGS[identifier].energy_use)

    def test_distinct_types_keep_their_bonus_but_repeat_growth_and_capacity_do_not_stack(self):
        g, p = self.game, self.planet
        with patch.object(economy, 'BASE_ENERGY', 100):
            p.buildings = ['factory']*2+['advanced_factory']*2
            self.assertEqual(workforce_bonuses(p).industry, 2)
            self.assertEqual(g.planet_yields(p)[0], 32)
            p.buildings = ['ecology_centre']*2
            self.assertEqual(economy.local_bonuses(p, {})['facility_capacity'], 10)
            self.assertEqual(g.population_report(p).produced, 18)  # 6 natural + 4 farmers + 8 fixed.
            self.assertFalse(BUILDINGS['medical_centre'].repeatable)
            self.assertFalse(BUILDINGS['space_hub'].repeatable)

    def test_shortages_and_disabling_use_one_remaining_powered_bonus(self):
        g, p = self.game, self.planet
        p.buildings = ['factory']*5
        self.assertEqual(g.planet_energy(p).efficiency, .8)
        self.assertAlmostEqual(workforce_bonuses(p, g.bonuses_for()).industry, .8)
        self.assertEqual(g.planet_yields(p)[0], 23)  # 4 workers + 0.8*(20 fixed + 4 bonus).
        self.assertEqual(breakdown(g, p, 'industry').total, 23)
        p.buildings = ['research_lab']*2
        g.toggle_building(0, 2, 0)
        self.assertEqual(workforce_bonuses(p, g.bonuses_for()).research, 1)
        self.assertEqual(g.planet_yields(p)[2], 7)
        self.assertEqual(g.planet_maintenance(p), 4)
        g.toggle_building(0, 2, 1)
        self.assertEqual(workforce_bonuses(p, g.bonuses_for()).research, 0)
        self.assertEqual(g.planet_yields(p)[2], 2)
        g.toggle_building(0, 2, 0)
        self.assertEqual(g.planet_yields(p)[2], 7)

    def test_mining_richness_and_breakdown_use_one_miner_bonus(self):
        g, p = self.game, self.planet
        p.buildings = ['mine']*2
        for richness, expected in [('Poor', 5), ('Average', 9), ('Rich', 12), ('Ultra-rich', 23)]:
            with self.subTest(richness=richness):
                p.richness = richness
                self.assertEqual(g.planet_resources(p), expected)
                info = breakdown(g, p, 'mining')
                self.assertEqual(info.total, expected)
                self.assertTrue(any('2 base + 1 facilities' in line for line in info.lines))

    def test_repeat_orders_use_slots_pause_without_bonus_and_finish_at_the_forecast(self):
        g, p = self.game, self.planet
        g.resources = 1000
        for _ in range(2):
            g.queue_building(0, 2, 'factory')
        before = g.planet_yields(p)
        g.set_trade_goods(0, 2)
        self.assertEqual(workforce_bonuses(p).industry, 0)
        self.assertEqual(p.used_slots, 2)
        self.assertEqual(g.planet_maintenance(p), 0)
        self.assertEqual(g.planet_energy(p).demand, 0)
        g.prioritize_construction(0, 2, 0)
        self.assertEqual(g.planet_yields(p), before)
        expected = g.queue_estimates(p)
        completed = []
        for turn in range(1, 31):
            count = len(p.buildings)
            g.advance_turn()
            completed.extend([turn]*(len(p.buildings)-count))
            if not p.construction_queue:
                break
        self.assertEqual(completed, expected)
        self.assertEqual(p.buildings, ['factory', 'factory'])
        self.assertEqual(workforce_bonuses(p).industry, 1)

    def test_slots_and_research_still_limit_repeated_orders(self):
        g, p = self.game, self.planet
        self.assertIn('Requires', g.build_error(0, 2, 'advanced_factory'))
        for _ in range(p.building_capacity):
            g.queue_building(0, 2, 'factory')
        before = g.to_dict()
        with self.assertRaisesRegex(RuleError, 'slots'):
            g.queue_building(0, 2, 'factory')
        self.assertEqual(g.to_dict(), before)
        self.assertEqual(len({tuple(site) for site in p.surface_layout.values()}), p.building_capacity+2)
        self.assertEqual(GameState.from_dict(g.to_dict()), g)

    def test_sites_follow_reordered_completed_cancelled_and_demolished_copies(self):
        g, p = self.game, self.planet
        g.resources = 1000
        g.queue_building(0, 2, 'factory', surface_site=(145, 200))
        g.queue_ship(0, 2, 'scout')
        g.queue_building(0, 2, 'factory', surface_site=(820, 200))
        first, second = deepcopy(p.surface_layout['factory']), deepcopy(p.surface_layout['factory:2'])
        g.fund_project(p.construction_queue[0])
        p.construction_queue[0].progress = 3
        g.prioritize_construction(0, 2, 2)
        self.assertEqual((p.surface_layout['factory'], p.surface_layout['factory:2']), (second, first))
        self.assertEqual(p.construction_queue[1].progress, 3)
        g.fund_project(p.construction_queue[0])
        p.finish_current_project()
        self.assertEqual((p.surface_layout['factory'], p.surface_layout['factory:2']), (second, first))
        g.cancel_construction(0, 2, 0)
        self.assertEqual(p.surface_layout['factory'], second)
        self.assertNotIn('factory:2', p.surface_layout)
        g.queue_building(0, 2, 'factory', surface_site=(145, 200))
        g.demolish_building(0, 2, 0)
        self.assertEqual(p.surface_layout['factory'], first)
        self.assertNotIn('factory:2', p.surface_layout)
        self.assertEqual(GameState.from_dict(g.to_dict()), g)

    def test_change_production_preserves_each_copys_site_and_invalid_placement_is_atomic(self):
        g, p = self.game, self.planet
        g.queue_building(0, 2, 'factory', surface_site=(145, 200))
        first = p.surface_layout['factory'].copy()
        before = g.to_dict()
        with self.assertRaisesRegex(RuleError, 'overlaps'):
            g.queue_building(0, 2, 'factory', surface_site=(145, 200))
        self.assertEqual(g.to_dict(), before)
        g.change_production(0, 2, 'factory')
        self.assertEqual(p.surface_layout['factory:2'], first)
        self.assertNotEqual(p.surface_layout['factory'], first)

    def test_individual_copies_survive_save_and_legacy_sites_keep_the_first_position(self):
        g, p = self.game, self.planet
        for _ in range(2):
            g.queue_building(0, 2, 'mine')
            g.fund_project(p.construction_queue[0])
            p.finish_current_project()
        g.toggle_building(0, 2, 1)
        with tempfile.TemporaryDirectory() as folder:
            store = Storage(folder)
            restored, metadata = store.load(store.save(g))
        self.assertEqual(metadata['version'], SAVE_VERSION)
        self.assertEqual(restored, g)
        legacy = g.to_dict()
        first = p.surface_layout['mine'].copy()
        del legacy['systems'][0]['worlds'][2]['surface_layout']['mine:2']
        old = GameState.from_dict(legacy, version=62)
        world = old.planet_at(0, 2)
        colony_layout.freeze(old, 0, world)
        self.assertEqual(world.surface_layout['mine'], first)
        self.assertNotEqual(world.surface_layout['mine:2'], first)
        self.assertEqual(GameState.from_dict(old.to_dict()), old)
        for key in ('mine:1', 'mine:02', 'mine:13', 'headquarters:2', 'unknown:2'):
            with self.subTest(key=key):
                damaged = deepcopy(g.to_dict())
                sites = damaged['systems'][0]['worlds'][2]['surface_layout']
                sites[key] = sites.pop('mine:2')
                with self.assertRaises(SaveError):
                    GameState.from_dict(damaged)

    def test_mothership_modules_and_ai_use_the_same_non_stacking_rule(self):
        g = campaign(race_id='wanderers')
        ship = next(s for s in g.ships if s.habitat)
        p = ship.habitat
        for _ in range(2):
            g.queue_building(ship.system_id, p.id, 'factory')
            g.fund_project(p.construction_queue[0])
            p.finish_current_project()
        self.assertEqual(workforce_bonuses(p).industry, 1)
        self.assertEqual(p.surface_layout, {})
        self.assertEqual(GameState.from_dict(g.to_dict()), g)
        self.assertEqual(ai.development_choice(p, 'wanderers', {'factory'}), 'factory')

    def test_stale_foreign_survey_preserves_separate_copies_without_live_information(self):
        g = new_game(seed=24, random_starts=False, with_ai=True, with_guardians=False,
                     with_black_holes=False, with_tombs=False, with_encounters=False)
        enemy = g.opponent
        sid, pid = enemy.home_system, enemy.home_planet
        p = g.planet_at(sid, pid)
        for _ in range(2):
            g.queue_building(sid, pid, 'factory', owner='rival')
        exploration.record_survey(g, sid, 'player')
        observed = deepcopy(g.known_system(sid).worlds[pid].surface_layout)
        self.assertIn('factory:2', observed)
        g.cancel_construction(sid, pid, 0, owner='rival')
        self.assertEqual(g.known_system(sid).worlds[pid].surface_layout, observed)
        restored = GameState.from_dict(g.to_dict())
        self.assertEqual(restored.known_system(sid).worlds[pid].surface_layout, observed)


class RepeatableBuildingInterfaceTests(unittest.TestCase):
    def test_repeated_catalogue_orders_and_surface_copies_have_independent_controls(self):
        from orion.app import App
        use_research_layout(self)
        with tempfile.TemporaryDirectory() as folder:
            app = App(Path(folder), capture=True)
            self.addCleanup(pg.quit)
            self.addCleanup(app.audio.close)
            app.settings['autosave'] = app.settings['animated_background'] = False
            app.window = pg.display.set_mode((1900, 984))
            app.game = g = campaign()
            p = g.planet_at(0, 2)
            app.open_planet(2)
            app.open_production()
            def click(key, button=1):
                app.render(); app.present()
                control = next(b for b in app.buttons if b.key == key)
                app.display_view.ensure_visible(control.rect)
                app.render(); app.present()
                pos = app.window_pos(control.rect.center)
                for event in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
                    app.handle_event(pg.event.Event(event, button=button, pos=pos))
                app.render(); app.present()
            click('production_build_factory')
            click('production_build_factory')
            self.assertEqual([q.item_id for q in p.construction_queue], ['factory']*2)
            self.assertIn('Once per operating building type', str(describe_project(g, p, 'factory').sections))
            g.resources = 1000
            for _ in range(2):
                g.fund_project(p.construction_queue[0])
                p.finish_current_project()
            g.toggle_building(0, 2, 1)
            app.open_planet(2)
            app.render(); app.present()
            copies = [b for b in app.buttons if b.key in ('surface_factory', 'surface_factory:2')]
            self.assertEqual(len(copies), 2)
            self.assertFalse(copies[0].rect.colliderect(copies[1].rect))
            before = g.to_dict()
            click('surface_factory:2', button=3)
            self.assertIn('1 disabled', str(app.dialog['building_info'].sections))
            self.assertEqual(g.to_dict(), before)
            click('dialog_close')
            click('surface_factory:2')
            self.assertEqual((app.screen, app.colony_slot), ('colony', 1))

