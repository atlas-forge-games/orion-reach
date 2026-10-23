"""Derived ship budgets, shared equipment, save compatibility and battle pacing."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from orion import ai, balance, combat, ship_scaling
from orion.balance_document import BalanceDocument
from orion.combat_sandbox import Scenario, build_game, preset, PRESETS
from orion.designs import HULLS, ShipDesign, standard_design
from orion.model import Ship, new_game
from orion.production import SHIP_TYPES
from orion.storage import Storage
from scenarios import research_to


class ShipScalingTests(unittest.TestCase):
    def setUp(self):
        self.previous = balance.active_profile()
        self.configured = balance._configured_path
        balance._configured_path = None
        balance.activate(balance.default_profile())
        self.addCleanup(lambda: balance.activate(self.previous))
        self.addCleanup(lambda: setattr(balance, '_configured_path', self.configured))
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def campaign(self, with_ai=False):
        return new_game(seed=2408, with_ai=with_ai, with_guardians=False,
                        with_tombs=False, with_encounters=False, with_black_holes=False,
                        random_starts=False, fog_of_war=False)

    def test_approved_frame_and_upkeep_scale(self):
        expected = {'scout': (20, 50, 1), 'frigate': (40, 110, 2),
                    'destroyer': (120, 360, 6), 'cruiser': (240, 770, 12),
                    'carrier': (400, 1350, 20), 'battleship': (500, 1720, 25),
                    'titan': (1600, 6200, 80)}
        for kind, (hull, frame, upkeep) in expected.items():
            with self.subTest(kind=kind):
                self.assertEqual(SHIP_TYPES[kind].maintenance, upkeep)
                chassis = HULLS.get(kind, SHIP_TYPES[kind])
                self.assertEqual((chassis.hull, chassis.resource_cost), (hull, frame))

    def test_standard_catalogue_campaign_and_combat_share_custom_equipment(self):
        game = self.campaign()
        for kind, modules in ship_scaling.STANDARD_LOADOUTS.items():
            with self.subTest(kind=kind):
                spec = SHIP_TYPES[kind]
                custom = ShipDesign('design_1', 'Equivalent', kind, modules)
                ship = Ship(999, kind, 0)
                tactical = combat.battle_ship(game, ship)
                for field in ('hull', 'damage', 'resource_cost', 'work_cost', 'maintenance', 'drone_bays'):
                    self.assertEqual(getattr(spec, field), getattr(custom, field), field)
                self.assertEqual(game.project_price(kind), spec.resource_cost)
                self.assertEqual(tactical.weapons,
                                 tuple((m.weapon, m.damage, m.range) for m in custom.specs if m.damage))
                self.assertEqual(tactical.max_hull, custom.hull)
                self.assertEqual(game.ship_attack(ship), custom.damage)

    def test_size_change_recalculates_frames_modules_stock_and_upkeep(self):
        profile = balance.default_profile()
        profile['data']['ship_sizes']['titan']['size'] = 90
        profile['data']['modules']['laser']['damage'] = 7
        balance.activate(profile)
        design = standard_design('titan')
        self.assertEqual((design.hull, design.maintenance), (1800, 90))
        self.assertEqual(HULLS['titan'].module_scale, 4500)
        self.assertEqual(SHIP_TYPES['titan'].damage, 2*315+2*450)
        self.assertEqual(SHIP_TYPES['titan'].resource_cost, design.resource_cost)
        self.assertEqual(balance.active_profile()['data']['ships']['titan']['damage'], design.damage)

    def test_editor_recalculates_and_undo_restores_all_dependent_values(self):
        doc = BalanceDocument(self.root/'balance.json')
        original = deepcopy(doc.profile)
        doc.set('ship_sizes', 'frigate', ('size',), 4)
        self.assertEqual(doc.entry('hulls', 'frigate')['hull'], 80)
        self.assertEqual(doc.entry('ships', 'frigate')['damage'], 20)
        self.assertTrue(doc.is_derived('ships', 'frigate', ('maintenance',)))
        with self.assertRaises(ValueError):
            doc.set('ships', 'frigate', ('hull',), 123)
        doc.undo()
        self.assertEqual(doc.profile, original)
        doc.redo()
        self.assertEqual(doc.entry('ships', 'frigate')['maintenance'], 4)
        doc.set('rules', 'ship_scaling', ('ENABLED',), False)
        doc.set('ships', 'frigate', ('maintenance',), 9)
        balance.activate(doc.profile)
        self.assertEqual(SHIP_TYPES['frigate'].maintenance, 9)

    def test_invalid_sizes_and_derived_overflow_cannot_mutate_catalogues(self):
        for value in (0, -1, 101, True, 1.5, float('inf')):
            profile = balance.default_profile()
            profile['data']['ship_sizes']['titan']['size'] = value
            with self.subTest(value=value), self.assertRaises(balance.BalanceError):
                balance.activate(profile)
            self.assertEqual(SHIP_TYPES['titan'].hull, 1600)
        profile = balance.default_profile()
        profile['data']['modules']['torpedo']['resource_cost'] = 100000
        with self.assertRaises(balance.BalanceError):
            balance.activate(profile)
        self.assertEqual(SHIP_TYPES['titan'].resource_cost, 11320)

    def test_reload_and_multiple_shots_are_not_double_counted(self):
        design = ShipDesign('design_1', 'Reload test', 'frigate', ('pulse', 'mirv', 'disruptor'))
        self.assertEqual(design.damage, 8+21+40)
        self.assertEqual(design.sustained_damage, 8+21+20)

    def test_standard_loadouts_keep_support_roles_and_use_paid_point_defense(self):
        game = self.campaign()
        titan = combat.battle_ship(game, Ship(1, 'titan', 0))
        escort = combat.battle_ship(game, Ship(2, 'destroyer', 0))
        self.assertIn(('command_accuracy', 12, 4), combat.fleet_support.auras(titan))
        self.assertIn(('escort_interception', 25, 2), combat.fleet_support.auras(escort))
        self.assertEqual(escort.design.interception, 30)
        bare = ShipDesign('design_1', 'No PD', 'destroyer', ('torpedo', 'torpedo', 'escort_array'))
        self.assertGreater(escort.design.resource_cost, bare.resource_cost)

    def test_live_stock_titan_volley_matches_catalogue_including_projectile_arrival(self):
        game = self.campaign(with_ai=True)
        target_design = ShipDesign('design_1', 'Unprotected target', 'titan', ('laser',))
        game.ships = [Ship(1, 'titan', 0), Ship(2, 'titan', 0, owner='rival', design=target_design)]
        game.next_ship_id = 3
        game.start_combat(0)
        attacker, target = game.combat.ship(1), game.combat.ship(2)
        attacker.x, attacker.y, target.x, target.y = 3, 4, 9, 4
        game.combat.accuracy = False
        self.assertEqual(game.combat_fire(1, 2), 400)
        for _ in range(6):
            game.combat_end_turn()
            game.combat_end_turn('rival')
        self.assertEqual(target.initial_hull-target.hull, SHIP_TYPES['titan'].damage)

    def test_ai_respects_capital_maintenance_and_actual_equipment_prices(self):
        game = self.campaign(with_ai=True)
        game.opponent.resources = 100000
        research_to(game, 'titan_hulls', owner='rival')
        for income in (4, 8, 15, 30, 100):
            with self.subTest(income=income), patch('orion.ai.projected_income', return_value=income):
                choice = ai.warship_choice(game, 'rival')
                self.assertLessEqual(SHIP_TYPES[choice].maintenance, income-1)
                self.assertLessEqual(game.project_price(choice, 'rival'), game.opponent.resources)
                self.assertEqual(ai.can_maintain_ship(game, 'rival', 'titan'), income >= 81)

    def test_stock_hulls_and_equipment_still_require_research_for_construction(self):
        game = self.campaign()
        system, planet = next((s, p) for s, p in game.settlements() if p.owner == 'player')
        self.assertIsNotNone(game.ship_build_error(system.id, planet.id, 'titan'))
        research_to(game, 'titan_hulls')
        self.assertIsNone(game.ship_build_error(system.id, planet.id, 'titan'))

    def test_paid_partial_standard_order_and_damage_survive_save_load(self):
        game = self.campaign()
        game.resources = 100000
        system, planet = next((s, p) for s, p in game.settlements() if p.owner == 'player')
        game.queue_ship(system.id, planet.id, 'frigate')
        project = planet.construction_queue[0]
        self.assertTrue(game.fund_project(project, 'player'))
        project.progress = 17
        research_to(game, 'titan_hulls')
        ship = Ship(game.next_ship_id, 'titan', system.id)
        ship.hull = 1001
        game.next_ship_id += 1
        game.ships.append(ship)
        original = game.to_dict()
        store = Storage(self.root)
        path = store.save(game)
        balance.activate(balance.legacy_profile())
        restored, _ = store.load(path)
        self.assertEqual(restored.to_dict(), original)
        self.assertEqual(restored.ships[-1].max_hull, 1600)
        self.assertEqual(restored.ships[-1].maintenance, 80)
        self.assertEqual(restored.planet_at(system.id, planet.id).construction_queue[0].spec.work_cost, 82)

    def test_v16_profiles_keep_old_ship_and_queue_values(self):
        old = balance.legacy_profile()
        # Keep the modern research tree, but use the prior ship economy.
        old['data']['technologies'] = balance.default_profile()['data']['technologies']
        balance.activate(old)
        game = self.campaign()
        game.resources = 1000
        system, planet = next((s, p) for s, p in game.settlements() if p.owner == 'player')
        game.queue_ship(system.id, planet.id, 'frigate')
        game.fund_project(planet.construction_queue[0], 'player')
        planet.construction_queue[0].progress = 10
        game.ships.append(Ship(game.next_ship_id, 'titan', system.id, hull=77))
        game.next_ship_id += 1
        before = game.to_dict()
        store = Storage(self.root)
        path = store.save(game)
        data = json.loads(path.read_text())
        profile = data['balance']
        profile['version'] = 16
        profile['data'].pop('ship_sizes')
        profile['data']['rules'].pop('ship_scaling')
        path.write_text(json.dumps(data))
        balance.activate(balance.default_profile())
        restored, _ = store.load(path)
        self.assertEqual(restored.to_dict(), before)
        self.assertFalse(ship_scaling.ENABLED)
        self.assertEqual((restored.ships[-1].max_hull, restored.ships[-1].maintenance), (125, 12))
        self.assertEqual(restored.planet_at(system.id, planet.id).construction_queue[0].spec.work_cost, 36)

    def test_scaled_carrier_wings_survive_midbattle_save(self):
        game = self.campaign(with_ai=True)
        research_to(game, 'drone_carriers')
        research_to(game, 'titan_hulls', owner='rival')
        game.ships = [Ship(1, 'carrier', 0), Ship(2, 'titan', 0, owner='rival')]
        game.next_ship_id = 3
        game.start_combat(0)
        carrier = game.combat.fleet('player')[0]
        drones = game.combat_launch_drones(carrier.id)
        self.assertTrue(drones)
        wing = game.combat.ship(drones[0])
        self.assertEqual((wing.hull, wing.damage), (60, 30))
        store = Storage(self.root)
        restored, _ = store.load(store.save(game))
        self.assertEqual(restored.combat.ship(drones[0]).hull, 60)
        self.assertEqual(restored.combat.ship(drones[0]).damage, 30)

    def test_dockyard_repairs_scale_but_never_exceed_maximum(self):
        game = self.campaign()
        system, _ = next((s, p) for s, p in game.settlements() if p.owner == 'player')
        ship = Ship(game.next_ship_id, 'titan', system.id, hull=1500)
        game.next_ship_id += 1
        game.ships.append(ship)
        game.advance_turn()
        self.assertEqual(ship.hull, 1580)
        game.advance_turn()
        self.assertEqual(ship.hull, 1600)

    def test_standard_presets_finish_without_hull_scaling_stalemates(self):
        for index, name in enumerate(PRESETS):
            with self.subTest(preset=name):
                game = build_game(preset(index))
                for _ in range(15000):
                    if game.combat.status != 'active':
                        break
                    self.assertLessEqual(game.combat.round, 150)
                    game.combat_ai_action()
                self.assertNotEqual(game.combat.status, 'active')


if __name__ == '__main__':
    unittest.main()
