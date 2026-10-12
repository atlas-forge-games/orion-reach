"""Hull-sized modules, shared targeting, old blueprints and the production layout."""
import copy
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')

import pygame as pg
from orion import balance, combat
from orion.app import App
from orion.auto_designs import auto_design
from orion.balance_document import BalanceDocument
from orion.buildings import BUILDINGS
from orion.designs import HULLS, MODULES, ShipDesign, fitted_module, loadout_error
from orion.model import GameState, PLAYER, RIVAL, RuleError, Ship, SaveError
from orion.research import TECHNOLOGIES
from orion.storage import Storage
from scenarios import empty_fleet_game
from test_arsenal import campaign, discover, duel


class HullModuleTests(unittest.TestCase):
    def test_four_graviton_weapons_fit_every_hull_and_a_fifth_is_rejected_atomically(self):
        for kind, damage, price, work in (('frigate',64,230,146), ('destroyer',64,245,155),
                                        ('cruiser',128,470,298), ('carrier',128,500,316),
                                        ('battleship',192,730,462), ('titan',256,1020,644)):
            with self.subTest(kind=kind):
                game = campaign()
                game.technology.completed = list(TECHNOLOGIES)
                design = game.save_design('Four mounts', kind, ['graviton']*4)
                self.assertEqual((design.damage, design.resource_cost, design.work_cost), (damage,price,work))
                before = game.to_dict()
                with self.assertRaisesRegex(RuleError, 'weapon slots'):
                    game.save_design('Too many', kind, ['graviton']*5)
                self.assertEqual(game.to_dict(), before)
        modules = ['laser']*4+['armor','point_defense','engine']
        self.assertIsNone(loadout_error('frigate', modules, list(TECHNOLOGIES)))
        self.assertIsNotNone(loadout_error('frigate', modules+['armor']))
        self.assertIsNotNone(loadout_error('frigate', modules+['engine']))
        self.assertIsNotNone(loadout_error('frigate', ['graviton']*4, []))

    def test_each_weapon_takes_one_slot_even_the_formerly_large_modules(self):
        for identifier, module in MODULES.items():
            if module.category == 'weapon':
                self.assertIsNone(loadout_error('frigate', [identifier]*4, list(TECHNOLOGIES)), identifier)
        self.assertIsNotNone(loadout_error('carrier', ['drone_bay']*3))
        self.assertIsNone(loadout_error('carrier', ['drone_bay']*2+['damage_control'], list(TECHNOLOGIES)))

    def test_armor_shields_repair_and_cost_scale_but_percentages_and_range_do_not(self):
        design = ShipDesign('design_1','Capital','titan',('laser','armor','regenerative_shield','flak','damage_control','scanner'))
        self.assertEqual((design.hull,design.damage,design.shields,design.shield_regeneration), (157,20,32,8))
        self.assertEqual((design.repair_rate,design.repair_capacity,design.interception,design.weapon_range), (12,48,45,7))
        self.assertEqual(design.movement,1)
        legacy = replace(design, fit_version=1)
        self.assertEqual((legacy.hull,legacy.damage,legacy.shields,legacy.repair_capacity), (133,5,8,12))

    def test_large_weapons_struggle_with_small_targets_but_hit_capitals_and_bases(self):
        game = campaign()
        target = combat.CombatShip(2,'frigate',RIVAL,20,20,x=8,y=4)
        chances = {}
        for kind in ('frigate','cruiser','battleship','titan'):
            design = ShipDesign('design_1','Aim',kind,('graviton',))
            attacker = combat.CombatShip(1,kind,PLAYER,design.hull,design.hull,x=5,y=4,design=design)
            chances[kind] = combat.accuracy_breakdown(game,attacker,target,'graviton')['chance']
        self.assertEqual(chances, {'frigate':72,'cruiser':42,'battleship':12,'titan':5})
        for kind in ('titan','missile_base','ancient_sentinel'):
            target.kind = kind
            values = combat.accuracy_breakdown(game,attacker,target,'graviton')
            self.assertEqual(values['tracking'],0)
            self.assertGreaterEqual(values['chance'],80)
        target.kind = 'combat_drone'
        self.assertEqual(combat.accuracy_breakdown(game,attacker,target,'graviton')['chance'],5)
        attacker.design = replace(attacker.design,fit_version=1)
        self.assertEqual(combat.accuracy_breakdown(game,attacker,target,'graviton')['tracking'],0)

    def test_scaled_weapons_fire_real_volleys_and_keep_special_effects(self):
        for weapon, damage, shots in (('pulse',24,2),('plasma',72,1),('particle',60,1),
                                     ('heavy_beam',90,1),('mirv',63,3),('disruptor',120,1)):
            with self.subTest(weapon=weapon):
                game = duel([weapon], defense=('laser','reinforced_armor'), fit_version=2)
                self.assertEqual(game.combat_fire(1,2),damage)
                self.assertEqual(game.combat.shots_fired,shots)
                self.assertEqual(GameState.from_dict(game.to_dict()),game)
        game = duel(['ion'], defense=('laser','shield','shield'), fit_version=2)
        self.assertEqual(game.combat_fire(1,2),0)
        self.assertEqual(game.combat.ship(2).shields,0)  # 24 ion damage strips 96 shields.
        game = duel(['graviton'], fit_version=2)
        self.assertEqual(game.combat_fire(1,2),48)
        self.assertTrue(game.combat.ship(2).graviton_slow)
        game = duel(['antimatter','laser'], defense=('laser','reinforced_armor'), fit_version=2)
        game.combat_fire(1,2)
        game.combat_end_turn(PLAYER); game.combat_end_turn(RIVAL)
        self.assertEqual(game.combat.ship(1).ready_damage,15)
        self.assertEqual(game.combat.ship(1).cooldowns,{'antimatter':1})

    def test_ai_damage_estimates_use_tracking_and_autofit_obeys_slots(self):
        game = campaign()
        attacker_design = ShipDesign('design_1','Aim','titan',('graviton',))
        attacker = combat.CombatShip(1,'titan',PLAYER,125,125,x=5,y=4,design=attacker_design)
        small = combat.CombatShip(2,'frigate',RIVAL,20,20,x=8,y=4)
        capital = combat.CombatShip(3,'titan',RIVAL,125,125,x=8,y=4)
        self.assertLess(combat.expected_volley(game,attacker,small),combat.expected_volley(game,attacker,capital)/10)
        game.combat = combat.CombatState(0,PLAYER,[attacker,small,capital])
        with patch('orion.combat.fire',return_value=0) as fired:
            action = combat.ai_action(game,PLAYER)
        self.assertEqual((action['kind'],action['target_id']),('fire',3))
        for kind in HULLS:
            design = auto_design(kind,tuple(sorted(TECHNOLOGIES)))
            self.assertEqual(design.fit_version,2)
            self.assertIsNone(loadout_error(kind,design.modules,list(TECHNOLOGIES)))
            self.assertEqual(sum(MODULES[m].category=='weapon' for m in design.modules),4)

    def test_ai_builds_slot_fitted_ships_from_the_start_and_pays_for_the_modules(self):
        game = campaign()
        design = game.production_design('frigate',RIVAL)
        self.assertEqual((design.fit_version,design.damage),(2,20))
        system, planet = game.headquarters(RIVAL)
        before = game.resources_for(RIVAL)
        price = game.project_price('frigate',RIVAL)
        game.queue_ship(system.id,planet.id,'frigate',owner=RIVAL)
        self.assertEqual(planet.construction_queue[-1].design,design)
        game.buy_construction(system.id,planet.id,owner=RIVAL)
        self.assertEqual(game.resources_for(RIVAL),before-price)
        self.assertEqual(game.ships[-1].design,design)
        self.assertEqual(GameState.from_dict(game.to_dict()),game)

    def test_v36_profiles_blueprints_orders_and_active_combat_migrate_without_stat_changes(self):
        game = duel(['torpedo']*4+['armor']*4)  # Legacy capacity layout.
        game.combat = None
        game.queue_ship(0,2,game.designs[0].id)
        game.start_combat(0)
        game.combat.ship(1).x, game.combat.ship(2).x = 5,8
        game.combat.ship(1).y = game.combat.ship(2).y = 4
        expected = (game.ships[0].design.hull,game.ships[0].design.damage,
                    game.planet_at(0,2).construction_queue[0].resource_cost)
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            path = storage.save(game)
            payload = json.loads(path.read_text())
            payload['version'] = 36
            profile = payload['balance']; profile['version'] = 1
            for hull in profile['data']['hulls'].values():
                for key in ('offensive_slots','defensive_slots','support_slots','module_size','module_scale','tracking_penalty'):
                    hull.pop(key)
            def old_designs(value):
                if isinstance(value,dict):
                    value.pop('fit_version',None)
                    for item in value.values(): old_designs(item)
                elif isinstance(value,list):
                    for item in value: old_designs(item)
            old_designs(payload['game'])
            path.write_text(json.dumps(payload))
            original = path.read_bytes()
            restored,_ = storage.load(path)
            self.assertEqual(path.read_bytes(),original)
            self.assertEqual((restored.ships[0].design.hull,restored.ships[0].design.damage,
                              restored.planet_at(0,2).construction_queue[0].resource_cost),expected)
            self.assertEqual(restored.ships[0].design.fit_version,1)
            restored.combat_fire(1,2)
            self.assertEqual(storage.load(storage.save(restored))[0],restored)
            restored.combat = None
            previous_ship = restored.ships[0].design
            revised = restored.save_design('Refitted','battleship',['torpedo']*4,'design_1')
            self.assertEqual(revised.damage,120)
            self.assertEqual(restored.ships[0].design,previous_ship)
            self.assertEqual(restored.planet_at(0,2).construction_queue[0].design,previous_ship)

    def test_editor_controls_scaling_tracking_and_slots_and_migrates_custom_profiles(self):
        previous = balance.active_profile()
        self.addCleanup(lambda:balance.activate(previous))
        profile = balance.default_profile()
        profile['data']['hulls']['frigate'].update(offensive_slots=2,module_scale=150,tracking_penalty=20,module_size='medium')
        balance.activate(profile)
        self.assertEqual(fitted_module('frigate','graviton').damage,24)
        self.assertIsNotNone(loadout_error('frigate',['laser']*3))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'custom.json'
            balance.write_profile(path,profile)
            doc = BalanceDocument(path)
            paths = [p for p,_ in doc.fields('hulls','frigate')]
            self.assertIn(('offensive_slots',),paths)
            self.assertIn(('tracking_penalty',),paths)
            self.assertNotIn(('capacity',),paths)
            self.assertEqual(doc.options('hulls',('module_size',)), [('small','Small'),('medium','Medium'),('heavy','Heavy')])
            old = balance.default_profile(); old['version']=1
            old['data']['research_costs']['1']['cost']=77
            old['data']['modules']['graviton']['damage']=19
            for hull in old['data']['hulls'].values():
                for key in ('offensive_slots','defensive_slots','support_slots','module_size','module_scale','tracking_penalty'):
                    hull.pop(key)
            path.write_text(json.dumps(old))
            doc = BalanceDocument(path)
            self.assertEqual(doc.entry('research_costs','1')['cost'],77)
            self.assertEqual(doc.entry('modules','graviton')['damage'],19)
            self.assertEqual(doc.entry('hulls','frigate')['offensive_slots'],4)
            doc.save()
            self.assertEqual(json.loads(path.read_text())['version'],2)


class ProductionLayoutTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.folder.name), capture=True)
        self.addCleanup(self.app.audio.close)
        self.game = self.app.game = empty_fleet_game(seed=2408,with_ai=False)
        self.game.choose_research('automated_factories')
        self.app.go('galaxy')
        self.game.selected_planet = 2

    def test_columns_remain_separate_and_page_independently_while_queueing(self):
        for i in range(8): self.game.save_design(f'Scout killer {i}','frigate',['laser'])
        self.app.open_production(); self.app.render()
        first_buildings = {b.key for b in self.app.buttons if b.key.startswith('production_build_') and b.key.removeprefix('production_build_') in BUILDINGS}
        for b in self.app.buttons:
            if b.key in first_buildings: self.assertLess(b.rect.right,486)
            if b.key == 'production_build_frigate': self.assertGreaterEqual(b.rect.left,944)
        next(b for b in self.app.buttons if b.key=='ship_catalog_next').action()
        self.app.render()
        self.assertEqual(self.app.ship_catalog_page,1)
        self.assertEqual(first_buildings,{b.key for b in self.app.buttons if b.key in first_buildings})
        self.app.choose_production('factory'); self.app.choose_production('design_1'); self.app.render()
        self.assertEqual(self.app.screen,'production')
        self.assertEqual(self.app.ship_catalog_page,1)
        for b in self.app.buttons:
            if b.key.startswith('production_priority_'):
                self.assertGreaterEqual(b.rect.left,486); self.assertLessEqual(b.rect.right,914)
            self.assertTrue(self.app.canvas.get_rect().contains(b.rect),b.key)
        self.assertEqual([q.item_id for q in self.game.planet_at(0,2).construction_queue],['factory','design_1'])

    def test_end_turn_is_silent_but_autosaves_and_save_errors_remain_visible(self):
        self.game.set_trade_goods(0,2)
        self.app.notice=''; self.app.notice_until=0
        turn = self.game.turn
        self.app.advance_turn()
        self.assertEqual(self.game.turn,turn+1)
        self.assertEqual(self.app.notice,'')
        self.assertEqual(self.app.storage.load(self.app.storage.saves_dir/'autosave.json')[0],self.game)
        with patch.object(self.app.storage,'save',side_effect=SaveError('Disk full')):
            self.app.advance_turn()
        self.assertEqual(self.app.notice,'Disk full')
        self.assertTrue(self.app.notice_error)


if __name__ == '__main__':
    unittest.main()
