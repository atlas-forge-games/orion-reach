"""Shared research accounting, real fitted upgrades, frozen orders and UI flows."""

from dataclasses import asdict
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
import pygame as pg

from orion import ai, balance, improvements
from orion.app import App
from orion.designs import ShipDesign
from orion.designer_controls import draft
from orion.model import GameState, RuleError, SaveError, Ship, new_game
from orion.research import TECHNOLOGIES, choices
from orion.storage import Storage


def discover(game, identifier, owner='player'):
    tech, state = TECHNOLOGIES[identifier], game.research_state(owner)
    for tier in range(1, tech.tier+1):
        if tier in state.completed_tiers(tech.branch):
            continue
        pick = identifier if tier == tech.tier else choices(tech.branch, tier)[0].id
        game._empire(owner).research += TECHNOLOGIES[pick].cost
        game.choose_research(pick, owner=owner)


class ImprovementCase(unittest.TestCase):
    def setUp(self):
        previous, configured = balance.active_profile(), balance._configured_path
        self.addCleanup(lambda: balance.activate(previous))
        self.addCleanup(lambda: setattr(balance, '_configured_path', configured))
        balance._configured_path = None
        balance.activate(balance.default_profile())

    def game(self, with_ai=False):
        game = new_game(seed=2408, random_starts=False, with_ai=with_ai,
                        with_guardians=False, with_black_holes=False, with_tombs=False,
                        with_encounters=False, fog_of_war=False, victory_conditions=())
        game.resources = game.credits = 100000
        game.ships = []
        game.next_ship_id = 1
        return game

    def finish(self, game, key, owner='player'):
        game._empire(owner).research += improvements.project(game.research_state(owner), key).cost
        return game.choose_improvement(key, owner=owner)


class EquipmentImprovementTests(ImprovementCase):
    def test_diminishing_independent_benefits_and_rising_costs(self):
        game = self.game()
        for level, damage, discount, cost in [(1, .10, .06, 100), (2, .17, .102, 160),
                                             (3, .219, .1314, 256), (4, .2533, .15198, 410),
                                             (5, .27731, .166386, 655)]:
            with self.subTest(level=level):
                self.assertAlmostEqual(improvements.benefit(level, 'power'), damage)
                self.assertAlmostEqual(improvements.benefit(level, 'manufacturing'), discount)
                self.assertEqual(improvements.project(game.technology, 'laser:power').cost, cost)
                self.finish(game, 'laser:power')
                self.assertNotIn('laser:manufacturing', game.technology.improvements)
        self.assertLessEqual(improvements.benefit(100, 'power'), 1/3+1e-12)
        self.assertLessEqual(improvements.benefit(100, 'manufacturing'), .2+1e-12)

    def test_switching_between_discoveries_and_improvements_conserves_points(self):
        game = self.game()
        game.research = 37
        game.choose_research('civil_engineering')
        for _ in range(3):
            game.choose_improvement('laser:power')
            self.assertIsNone(game.technology.active)
            self.assertEqual(game.technology.progress, 37)
            self.assertEqual(game.research, 0)
            game.choose_research('civil_engineering')
            self.assertIsNone(game.technology.active_improvement)
            self.assertEqual(game.technology.progress, 37)
        game.research = 70
        completed = game.choose_improvement('laser:power')
        self.assertEqual((completed.level, game.research, game.technology.progress), (1, 7, 0))
        self.assertEqual(game.technology.completed, [])
        self.assertEqual(game.technology.completed_tiers('construction'), set())
        self.assertEqual(game.technology.finished_branches, 0)
        self.assertIsNone(game.technology.project)

    def test_improving_does_not_unlock_excluded_equipment_or_advance_tiers(self):
        game = self.game()
        discover(game, 'radiation_shields')
        before = list(game.technology.completed)
        self.finish(game, 'shield:power')
        self.assertEqual(game.technology.completed, before)
        self.assertIsNone(game.improvement_error('shield:manufacturing'))
        before = game.to_dict()
        for key in ('quantum:power', 'nope:power', 'laser:nope', None, [], 'laser'):
            with self.subTest(key=key):
                with self.assertRaises(RuleError):
                    game.choose_improvement(key)
                self.assertEqual(game.to_dict(), before)

    def test_unfinished_research_has_no_effect_and_persists_exactly(self):
        game = self.game()
        game.research = 49
        game.choose_improvement('laser:manufacturing')
        self.assertEqual(game.technology.improvements, {})
        restored = GameState.from_dict(game.to_dict())
        self.assertEqual(restored, game)
        for state in (game, restored):
            state.research = 51
            state.advance_research()
        self.assertEqual(restored, game)
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(Path(directory))
            self.assertEqual(storage.load(storage.save(game))[0], game)

    def test_existing_ships_receive_only_the_matching_empire_weapon_upgrade(self):
        game = self.game(with_ai=True)
        design = game.save_design('Mixed', 'frigate', ['laser', 'torpedo', 'armor'])
        game.ships = [Ship(1, 'frigate', 0, design=design), Ship(2, 'frigate', 0, owner='rival', design=design)]
        game.next_ship_id = 3
        own, rival = game.ships
        before = tuple(m.damage for m in own.design.specs)
        self.finish(game, 'laser:power')
        after = tuple(m.damage for m in own.design.specs)
        self.assertGreater(after[0], before[0])
        self.assertEqual(after[1:], before[1:])
        self.assertEqual(tuple(m.damage for m in rival.design.specs), before)
        self.assertEqual(game.design_for(design.id), own.design)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_armor_increases_added_hull_without_repairing_existing_damage(self):
        game = self.game()
        design = game.save_design('Armored', 'frigate', ['laser', 'armor'])
        ship = Ship(1, 'frigate', 0, design=design)
        game.ships, game.next_ship_id = [ship], 2
        ship.hull -= 7
        old_max = ship.max_hull
        self.finish(game, 'armor:power')
        self.assertGreater(ship.max_hull, old_max)
        self.assertEqual(ship.max_hull-ship.hull, 7)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_manufacturing_changes_only_new_matching_orders_and_preserves_refunds(self):
        game = self.game()
        design = game.save_design('Laser ship', 'frigate', ['laser', 'laser', 'armor'])
        other = game.save_design('Torpedo ship', 'frigate', ['torpedo', 'armor'])
        other_price = game.project_price(other.id)
        game.queue_ship(0, 2, design.id)
        old = game.planet_at(0, 2).construction_queue[0]
        game.fund_project(old)
        old.progress = 3
        fixed = old.resource_cost, old.spec.work_cost, old.progress, old.paid_resources, old.resource_refund
        self.finish(game, 'laser:manufacturing')
        game.queue_ship(0, 2, design.id)
        new = game.planet_at(0, 2).construction_queue[1]
        self.assertEqual((old.resource_cost, old.spec.work_cost, old.progress, old.paid_resources, old.resource_refund), fixed)
        self.assertLess(new.resource_cost, old.resource_cost)
        self.assertLess(new.spec.work_cost, old.spec.work_cost)
        self.assertEqual(game.project_price(other.id), other_price)
        self.finish(game, 'laser:power')
        self.assertEqual((old.resource_cost, old.spec.work_cost, old.progress, old.paid_resources, old.resource_refund), fixed)
        self.assertGreater(old.design.damage, design.damage)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_standard_new_orders_include_researched_improvements(self):
        game = self.game()
        before = game.project_spec('frigate')
        self.finish(game, 'laser:power')
        self.finish(game, 'laser:manufacturing')
        after = game.project_spec('frigate')
        self.assertGreater(after.damage, before.damage)
        self.assertLess(after.resource_cost, before.resource_cost)
        game.queue_ship(0, 2, 'frigate')
        self.assertEqual(game.planet_at(0, 2).construction_queue[0].design, after)

    def test_real_combat_uses_improved_damage_and_shields_and_roundtrips(self):
        game = self.game(with_ai=True)
        discover(game, 'radiation_shields')
        left = game.save_design('Shielded', 'frigate', ['laser', 'shield'])
        right = ShipDesign('design_2', 'Target', 'frigate', ('laser',))
        game.ships = [Ship(1, 'frigate', 0, design=left), Ship(2, 'frigate', 0, owner='rival', design=right)]
        game.next_ship_id = 3
        self.finish(game, 'laser:power')
        self.finish(game, 'shield:power')
        game.start_combat(0)
        attacker, target = game.combat.ship(1), game.combat.ship(2)
        self.assertGreater(attacker.shields, left.shields)
        self.assertGreater(attacker.damage, left.damage)
        attacker.x, attacker.y, target.x, target.y = 5, 4, 8, 4
        game.combat.accuracy = False
        self.assertEqual(game.combat_fire(1, 2), attacker.damage)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_ai_uses_its_own_points_and_keeps_an_active_improvement(self):
        game = self.game(with_ai=True)
        for identifier in ('civil_engineering', 'ion_drives', 'research_instruments'):
            discover(game, identifier, 'rival')
        game.ships = [Ship(1, 'frigate', game.opponent.home_system, owner='rival')]
        game.next_ship_id = 2
        game.opponent.research = 31
        ai.research_choice(game, 'rival')
        self.assertIsNotNone(game.opponent.technology.active_improvement)
        self.assertEqual(game.opponent.technology.progress, 31)
        self.assertEqual(game.opponent.research, 0)
        self.assertEqual(game.technology.improvements, {})
        before = game.to_dict()
        ai.research_choice(game, 'rival')
        self.assertEqual(game.to_dict(), before)

    def test_invalid_saved_levels_projects_and_fitted_levels_are_rejected(self):
        game = self.game()
        for key, level in [('laser:power', -1), ('laser:power', True), ('laser:power', 1.5),
                           ('laser:power', 101), ('shield:power', 1), ('laser:unknown', 1)]:
            with self.subTest(key=key, level=level):
                data = game.to_dict()
                data['technology']['improvements'] = {key: level}
                with self.assertRaises(SaveError):
                    GameState.from_dict(data)
        game.choose_improvement('laser:power')
        data = game.to_dict()
        data['technology']['active'] = 'civil_engineering'
        with self.assertRaises(SaveError):
            GameState.from_dict(data)
        data = game.to_dict()
        data['technology']['progress'] = 100
        with self.assertRaises(SaveError):
            GameState.from_dict(data)
        design = asdict(ShipDesign('design_1', 'Test', 'frigate', ('laser',)))
        design['improvements'] = [('torpedo:power', 1)]
        with self.assertRaises(ValueError):
            ShipDesign.from_dict(design)

    def test_normal_turn_output_finishes_an_improvement_and_banks_overflow(self):
        game = self.game()
        game.set_workforce(0, 2, 2, 3, 0)
        rate = game.empire_rates[1]
        self.assertGreater(rate, 0)
        game.research = 99
        game.choose_improvement('laser:power')
        report = game.advance_turn()
        self.assertEqual(game.technology.improvements, {'laser:power': 1})
        self.assertEqual(game.research, rate-1)
        self.assertTrue(any('Weapon power 1' in message for message in report.discoveries))
        self.assertEqual(game.technology.completed, [])
        self.assertEqual(GameState.from_dict(game.to_dict()), game)


class ImprovementInterfaceTests(ImprovementCase):
    def test_real_clicks_switch_modes_transfer_progress_and_update_designer(self):
        with tempfile.TemporaryDirectory() as directory:
            app = App(Path(directory), capture=True)
            self.addCleanup(pg.quit)
            self.addCleanup(app.audio.close)
            app.game = game = self.game()
            design = game.save_design('Laser ship', 'frigate', ['laser', 'armor'])
            game.research = 37
            game.choose_research('civil_engineering')
            app.go('galaxy')
            app.open_research()

            def click(key):
                app.render()
                button = next(b for b in app.buttons if b.key == key)
                self.assertTrue(button.enabled, key)
                pos = app.window_pos(button.rect.center)
                for event in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
                    app.handle_event(pg.event.Event(event, button=1, pos=pos))
                app.render()

            for size in ((980, 900), (1280, 800), (1920, 1080)):
                app.window = pg.display.set_mode(size, pg.RESIZABLE)
                app.present()
                click('research_mode_improvements')
                click('improvement_target_laser')
                self.assertTrue(all(app.canvas.get_rect().contains(b.rect) for b in app.buttons))
                click('research_mode_new')
            click('research_mode_improvements')
            click('improvement_choose_power')
            self.assertEqual((game.technology.progress, game.technology.active_improvement), (37, 'laser:power'))
            self.assertFalse(app.needs_research_choice())
            click('research_mode_new')
            click('research_show_active')
            self.assertEqual(app.research_mode, 'improvements')
            game.research = 63
            game.advance_research()
            app.load_design(game.design_for(design.id))
            self.assertGreater(draft(app).damage, design.damage)
            self.assertEqual(draft(app), game.design_for(design.id))
            self.assertEqual(GameState.from_dict(game.to_dict()), game)


if __name__ == '__main__':
    unittest.main()
