"""Default pacing, advanced facilities and frozen campaign research layouts."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')

from scenarios import finish_building_next_turn
from orion import ai, balance
from orion.balance_document import BalanceDocument
from orion.buildings import ADVANCED_FACILITIES, BUILDINGS, FACILITY_FAMILIES
from orion.economy import energy_report, mining_output
from orion.model import GameState, RuleError, new_game
from orion.research import TECHNOLOGIES, choices, gross_colony_yields
from orion.storage import Storage


def discover(game, *identifiers, owner='player'):
    picks = {(TECHNOLOGIES[t].branch, TECHNOLOGIES[t].tier): t for t in identifiers}
    state = game.research_state(owner)
    for branch in dict.fromkeys(b for b, _ in picks):
        last = max(tier for b, tier in picks if b == branch)
        for tier in range(1, last+1):
            selected = picks.get((branch, tier), choices(branch, tier)[0].id)
            if tier in state.completed_tiers(branch):
                if (branch, tier) in picks and selected not in state.completed:
                    raise AssertionError('Conflicting research fixture')
                continue
            game._empire(owner).research = TECHNOLOGIES[selected].cost
            game.choose_research(selected, owner=owner)


class ProgressionTests(unittest.TestCase):
    def setUp(self):
        previous, configured = balance.active_profile(), balance._configured_path
        balance._configured_path = None
        balance.activate(balance.default_profile())
        self.addCleanup(lambda: balance.activate(previous))
        self.addCleanup(lambda: setattr(balance, '_configured_path', configured))
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def game(self, **kwargs):
        return new_game(seed=2408, with_ai=kwargs.pop('with_ai', False), with_guardians=False,
                        with_tombs=False, with_black_holes=False, random_starts=False, **kwargs)

    def test_beams_start_early_and_hulls_and_economy_have_staged_unlocks(self):
        weapons = ('pulse_beams', 'ion_beams', 'quantum_optics', 'plasma_beams',
                   'graviton_beams', 'particle_beams', 'disruptor_beams')
        self.assertEqual([TECHNOLOGIES[t].tier for t in weapons], list(range(2, 9)))
        self.assertEqual([TECHNOLOGIES[t].tier for t in ('destroyer_hulls', 'cruiser_hulls',
                         'drone_carriers', 'battleship_hulls', 'titan_hulls')], [1, 2, 3, 4, 6])
        self.assertEqual(TECHNOLOGIES['deep_space_radar'].tier, 2)
        self.assertEqual(TECHNOLOGIES['fusion_torpedoes'].tier, 2)
        self.assertEqual(TECHNOLOGIES['antimatter_torpedoes'].tier, 6)
        for family in FACILITY_FAMILIES.values():
            self.assertIsNone(BUILDINGS[family[0]].technology)
            first, last = (TECHNOLOGIES[BUILDINGS[b].technology].tier for b in family[1:])
            self.assertGreaterEqual(first, 3)
            self.assertGreater(last, first)

    def test_every_facility_requires_research_reserves_a_slot_and_rejects_duplicates(self):
        for identifier in ADVANCED_FACILITIES:
            with self.subTest(facility=identifier):
                game = self.game()
                planet = game.planet_at(0, 2)
                game.resources = game.credits = 10000
                self.assertIsNotNone(game.build_error(0, 2, identifier))
                discover(game, BUILDINGS[identifier].technology)
                self.assertIsNone(game.build_error(0, 2, identifier))
                before = planet.free_slots
                game.queue_building(0, 2, identifier)
                self.assertEqual(planet.free_slots, before-1)
                with self.assertRaises(RuleError): game.queue_building(0, 2, identifier)
                restored = GameState.from_dict(game.to_dict())
                self.assertEqual(restored, game)
                finish_building_next_turn(game)
                self.assertIn(identifier, planet.buildings)
                with self.assertRaises(RuleError): game.queue_building(0, 2, identifier)
                self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_research_and_industry_include_all_family_and_staff_bonuses(self):
        planet = self.game().planet_at(0, 2)
        planet.population, planet.farmers, planet.miners, planet.scientists = 8, 0, 0, 2
        for family, output, base in (('factory', 0, planet.workers), ('research_lab', 2, 2*planet.scientists)):
            values = []
            for identifier in FACILITY_FAMILIES[family]:
                planet.buildings = [identifier]
                bonuses = {'factory_industry': 3, 'lab_research': 3, 'colony_energy': 100}
                spec = BUILDINGS[identifier]
                expected = (base + spec.industry + int(spec.industry_per_worker*planet.workers) + 3
                            if family == 'factory' else base + spec.research + spec.research_per_scientist*planet.scientists + 3)
                value = gross_colony_yields(planet, bonuses)[output]
                self.assertEqual(value, expected)
                values.append(value)
                self.assertEqual(planet.maintenance_per_turn, spec.maintenance)
            self.assertEqual(values, sorted(set(values)))

    def test_mine_families_scale_with_richness_and_keep_flat_research_bonuses(self):
        planet = self.game().planet_at(0, 2)
        planet.miners = 2
        planet.buildings = list(FACILITY_FAMILIES['mine'])
        bonuses = {'mine_resources': 3, 'colony_energy': 100}
        # (2+4+7) base extraction and (2+1+2+3)*2 miners, scaled together.
        for richness, factor in (('Poor', .5), ('Average', 1), ('Rich', 1.5), ('Ultra-rich', 3)):
            planet.richness = richness
            self.assertEqual(mining_output(planet, bonuses), 2+int(29*factor)+9)

    def test_power_shortage_and_disabling_remove_new_facility_output(self):
        planet = self.game().planet_at(0, 2)
        planet.miners, planet.scientists = 2, 2
        planet.buildings = ['quantum_research_lab', 'deep_core_mine']
        report = energy_report(planet)
        self.assertEqual(report.active, (1,))  # Mines retain priority over labs.
        self.assertEqual(report.offline, (0,))
        self.assertEqual(gross_colony_yields(planet, {})[2], 4)
        self.assertEqual(planet.maintenance_per_turn, 10)
        planet.disabled_buildings = [1]
        self.assertEqual(energy_report(planet).active, (0,))
        self.assertEqual(gross_colony_yields(planet, {})[2], 24)
        self.assertEqual(mining_output(planet), 2+int(4*{'Poor': .5, 'Average': 1, 'Rich': 1.5, 'Ultra-rich': 3}[planet.richness]))

    def test_ai_prefers_researched_facilities_and_queues_them_with_normal_rules(self):
        game = self.game(with_ai=True)
        owner = 'rival'
        system, planet = game.headquarters(owner)
        planet.population, planet.farmers, planet.scientists, planet.miners = 16, 0, 0, 0
        planet.buildings = ['trade_center', 'solar_array']
        discover(game, 'planetary_automation', owner=owner)
        available = {b for b in BUILDINGS if game.build_error(system.id, planet.id, b, owner=owner) is None}
        self.assertEqual(ai.development_choice(planet, 'kharuun', available), 'robotic_factory')
        self.assertTrue(ai.queue_building(game, system, planet, 'robotic_factory', owner))
        self.assertEqual(planet.construction_queue[-1].item_id, 'robotic_factory')
        self.assertFalse(ai.queue_building(game, system, planet, 'nanofactory', owner))

    def test_editor_changes_new_facilities_and_swaps_new_tree_cells(self):
        doc = BalanceDocument(self.root/'balance.json')
        doc.set('buildings', 'quantum_research_lab', ('research',), 23)
        doc.set('buildings', 'deep_core_mine', ('resources_per_miner',), 4)
        doc.move_technology('pulse_beams', 'physics', 4, 0)
        self.assertEqual(doc.choices('physics', 2)[0], 'quantum_optics')
        self.assertEqual(doc.choices('physics', 4)[0], 'pulse_beams')
        self.assertFalse(balance.validate(doc.profile))
        balance.write_profile(doc.path, doc.profile)
        balance.activate(balance.read_profile(doc.path))
        self.assertEqual(BUILDINGS['quantum_research_lab'].research, 23)
        self.assertEqual(BUILDINGS['deep_core_mine'].resources_per_miner, 4)

    def test_real_v055_profile_keeps_choices_prices_and_active_research_when_loaded(self):
        old = json.loads((Path(__file__).parent/'fixtures/v055_balance.json').read_text())
        old['data']['research_costs']['5']['cost'] = 1234
        original = copy.deepcopy(old)
        balance.activate(old)
        game = self.game()
        discover(game, 'siege_weapons')
        game.research = 1000
        game.choose_research('pulse_beams')
        store = Storage(self.root)
        path = store.save(game)
        payload = json.loads(path.read_text())
        payload['balance'] = old
        path.write_text(json.dumps(payload))
        raw = path.read_bytes()
        balance.activate(balance.default_profile())
        restored, _ = store.load(path)
        self.assertEqual((TECHNOLOGIES['pulse_beams'].tier, restored.technology.progress,
                          restored.technology.project_cost), (5, 1000, 1234))
        for section, table in original['data'].items():
            for identifier, entry in table.items():
                if section == 'ships':
                    entry = {**entry, 'maintenance': balance.legacy_profile()['data']['ships'][identifier]['maintenance']}
                if section == 'modules':
                    entry = {**entry, 'support_range': 0, 'escort_interception': 0, 'command_accuracy': 0, 'jamming': 0}
                if section == 'ships' and identifier == 'colony_ship':
                    entry = {**entry, 'resource_cost': 800, 'work_cost': 420}
                if section == 'races':
                    entry = {k: v for k, v in entry.items() if k not in ('trade_threshold', 'envoy_bonus')}
                if section == 'personalities':
                    entry = {k: v for k, v in entry.items() if k not in ('envoy', 'gift')}
                if identifier == 'concord':
                    if section == 'races':
                        entry = {**entry, 'name': 'Dominion of One', 'default_empire': 'Dominion of One'}
                    elif section == 'personalities':
                        entry = {**entry, 'greeting': balance.default_profile()['data'][section][identifier]['greeting']}
                if section == 'rules' and identifier == 'diplomacy':
                    retired = {'ENVOY_COST', 'ENVOY_RELATIONS', 'ENVOY_COOLDOWN', 'GIFT_COST',
                               'GIFT_RELATIONS', 'GIFT_COOLDOWN', 'TRADE_INCOME'}
                    entry = {k: v for k, v in entry.items() if k not in retired}
                    entry.update(TRADE_THRESHOLD=10, NON_AGGRESSION_THRESHOLD=0,
                                 FRIENDSHIP_THRESHOLD=30, TRADE_SHARE_PERCENT=25, TRADE_DISTANCE_LY=50)
                self.assertEqual(balance.profile_for(restored)['data'][section][identifier], entry)
        self.assertTrue(set(ADVANCED_FACILITIES) <= set(balance.profile_for(restored)['data']['buildings']))
        self.assertEqual(old, original)
        self.assertEqual(path.read_bytes(), raw)
        self.assertEqual(store.load(store.save(restored))[0], restored)

    def test_pre_profile_save_keeps_old_tree_and_rejects_corrupt_sequence(self):
        balance.activate(balance.legacy_profile())
        game = self.game()
        discover(game, 'ion_beams')
        store = Storage(self.root)
        path = store.save(game)
        payload = json.loads(path.read_text())
        payload['version'] = 35
        payload.pop('balance')
        payload['game'].pop('statistics')
        path.write_text(json.dumps(payload))
        balance.activate(balance.default_profile())
        restored, _ = store.load(path)
        self.assertEqual(TECHNOLOGIES['ion_beams'].tier, 6)
        self.assertEqual(restored.technology.completed, game.technology.completed)
        self.assertIsNone(restored.research_error('particle_beams'))
        self.assertEqual(store.load(store.save(restored))[0], restored)
        payload['game']['technology']['completed'].append('graviton_beams')
        path.write_text(json.dumps(payload))
        from orion.model import SaveError
        with self.assertRaises(SaveError): store.load(path)

    def test_facilities_render_in_colony_catalogue_and_surface_and_hide_when_queued(self):
        import pygame as pg
        from orion.app import App
        app = App(self.root, capture=True)
        self.addCleanup(pg.quit)
        self.addCleanup(app.audio.close)
        app.game = self.game()
        discover(app.game, *(BUILDINGS[b].technology for b in ADVANCED_FACILITIES))
        app.open_planet(2)
        app.go('colony')
        app.colony_build_page = 3
        app.render()
        buttons = {b.key: b for b in app.buttons}
        for identifier in ADVANCED_FACILITIES:
            self.assertIn('build_'+identifier, buttons)
            self.assertLessEqual(buttons['build_'+identifier].rect.bottom, 806)
        app.game.resources = app.game.credits = 10000
        app.game.queue_building(0, 2, 'advanced_research_lab')
        app.render()
        self.assertNotIn('build_advanced_research_lab', {b.key for b in app.buttons})
        finish_building_next_turn(app.game)
        app.go('planet')
        app.render()
        self.assertIn('surface_advanced_research_lab', {b.key for b in app.buttons})


if __name__ == '__main__':
    unittest.main()
