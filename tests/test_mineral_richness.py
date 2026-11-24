"""Mineral scarcity, zero-extraction colonies, AI and saved-profile continuity."""

from collections import Counter
from copy import deepcopy
from pathlib import Path
import json
import random
import tempfile
import unittest
from unittest.mock import patch

from orion import ai, balance, economy, exploration, monsters
from orion.buildings import FACILITY_FAMILIES, MINERAL_FACTORS, MINERAL_WEIGHTS
from orion.model import GameState, StarSystem, generate_planets, new_game, random_richness
from orion.production_breakdown import describe
from orion.storage import SAVE_VERSION, Storage


class MineralRichnessTests(unittest.TestCase):
    def setUp(self):
        previous, configured = balance.active_profile(), balance._configured_path
        self.addCleanup(lambda: balance.activate(previous))
        self.addCleanup(lambda: setattr(balance, '_configured_path', configured))
        balance._configured_path = None
        balance.activate(balance.default_profile())

    def game(self, **changes):
        settings = dict(seed=2408, with_ai=False, with_guardians=False,
                        with_black_holes=False, with_tombs=False, with_encounters=False,
                        random_starts=False)
        settings.update(changes)
        return new_game(**settings)

    def test_real_colony_mining_at_all_five_richness_levels(self):
        game = self.game()
        planet = game.headquarters()[1]
        planet.buildings = ['mine']
        game.set_workforce(0, planet.id, 2, 0, 4)
        for richness, output in [('Void', 0), ('Poor', 6), ('Average', 16), ('Rich', 58), ('Ultra-rich', 142)]:
            with self.subTest(richness=richness):
                planet.richness = richness
                self.assertEqual(game.planet_resources(planet), output)
                report = describe(game, planet, 'mining')
                self.assertEqual(report.total, output)
                after = next(line for line in report.lines if line.startswith('After strain:'))
                self.assertEqual(float(after.rsplit(' = ', 1)[1]), output)

    def test_void_blocks_base_mines_workers_and_flat_bonuses(self):
        game = self.game()
        planet = game.headquarters()[1]
        planet.richness = 'Void'
        for buildings in ([], ['mine'], ['mine', 'mine', 'deep_core_mine', 'automated_refinery']):
            with self.subTest(buildings=buildings):
                planet.buildings = buildings
                planet.miners = 4
                bonuses = {'colony_resources': 21, 'mine_resources': 9, 'colony_energy': 100}
                self.assertEqual(economy.miner_output(planet, bonuses), 0)
                self.assertEqual(economy.mining_output(planet, bonuses), 0)
        self.assertTrue(any('all mining bonuses' in line for line in describe(game, planet, 'mining').lines))

    def test_other_colony_outputs_are_independent_of_minerals(self):
        game = self.game()
        planet = game.headquarters()[1]
        planet.buildings = ['factory', 'research_lab', 'hydroponic_farm', 'trade_center']
        game.set_workforce(0, planet.id, 2, 2, 0)
        expected = game.planet_yields(planet), game.population_report(planet).produced
        for richness in MINERAL_FACTORS:
            planet.richness = richness
            self.assertEqual((game.planet_yields(planet), game.population_report(planet).produced), expected)

    def test_void_can_use_shared_resources_to_finish_construction(self):
        game = self.game()
        planet = game.headquarters()[1]
        planet.richness = 'Void'
        game.resources = 1000
        game.queue_building(0, planet.id, 'factory')
        project = planet.construction_queue[0]
        self.assertTrue(game.fund_project(project))
        project.progress = project.spec.work_cost-1
        game.advance_turn()
        self.assertIn('factory', planet.buildings)
        self.assertEqual(game.planet_resources(planet), 0)

    def test_void_backup_power_still_consumes_imported_resources(self):
        profile = balance.default_profile()
        profile['data']['rules']['economy']['BASE_ENERGY'] = 0
        balance.activate(profile)
        game = self.game()
        planet = game.headquarters()[1]
        planet.richness = 'Void'
        planet.buildings = ['factory', 'thermal_plant']
        game.resources = 100
        power = game.planet_energy(planet)
        self.assertGreater(power.fuel_used, 0)
        self.assertEqual(game.planet_resources(planet), -power.fuel_used)
        self.assertEqual(describe(game, planet, 'mining').total, -power.fuel_used)

    def test_generation_distribution_includes_rare_ultra_rich_worlds(self):
        rng = random.Random(81425)
        counts = Counter()
        for sid in range(1, 2001):
            system = StarSystem(sid, 'Test', .5, .5, 'Yellow dwarf', 7, 'Terran', random_richness(rng))
            worlds = generate_planets(system, sid, player_home=False)
            self.assertEqual(worlds[0].richness, system.richness)
            counts.update(p.richness for p in worlds)
        total = counts.total()
        for name, share in [('Void', .40), ('Poor', .30), ('Average', .20), ('Rich', .08), ('Ultra-rich', .02)]:
            self.assertAlmostEqual(counts[name]/total, share, delta=.012 if name != 'Ultra-rich' else .004)
        self.assertLess(counts['Ultra-rich'], counts['Rich']/3)

    def test_generation_weights_reach_all_random_planet_paths(self):
        profile = balance.default_profile()
        for name, entry in profile['data']['minerals'].items():
            entry['generation_weight'] = 1 if name == 'Void' else 0
        balance.activate(profile)
        game = self.game(race_id='skirr')
        for system in game.systems:
            for planet in system.worlds:
                if planet.colonized or planet.is_gas_giant:
                    self.assertEqual(planet.richness, 'Average')
                else:
                    self.assertEqual(planet.richness, 'Void')
        self.assertEqual(MINERAL_WEIGHTS['Void'], 1)

    def test_mineral_weights_do_not_move_stars_or_change_other_planet_traits(self):
        with patch('orion.model.random_richness', side_effect=lambda rng: rng.choice(('Poor', 'Average', 'Rich'))):
            previous = self.game()
        current = self.game()
        def physical_map(game):
            return [(s.id, s.x, s.y, s.kind, s.planets,
                     [(p.biome, p.size, p.gravity, p.orbit_au) for p in s.worlds]) for s in game.systems]
        self.assertEqual(physical_map(previous), physical_map(current))

    def test_every_start_mode_gives_rivals_average_homeworlds(self):
        for randomized, count in [(False, 1), (True, 1), (True, 3)]:
            with self.subTest(randomized=randomized, count=count):
                game = self.game(with_ai=True, random_starts=randomized, rival_count=count)
                for owner in game.owners:
                    self.assertEqual(game.headquarters(owner)[1].richness, 'Average')

    def test_new_games_and_save_roundtrips_are_deterministic(self):
        first, second = self.game(), self.game()
        self.assertEqual(first.systems, second.systems)
        home = first.headquarters()[1]
        self.assertEqual(home.richness, 'Average')
        home.richness = 'Void'
        exploration.refresh(first)
        restored = GameState.from_dict(first.to_dict())
        self.assertEqual(restored, first)
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(Path(folder))
            path = storage.save(first)
            self.assertEqual(json.loads(path.read_text())['version'], SAVE_VERSION)
            self.assertEqual(storage.load(path)[0], first)

    def test_guarded_worlds_keep_their_deliberate_rewards(self):
        game = self.game(with_guardians=True)
        self.assertTrue(game.guardians)
        for guardian in game.guardians:
            expected = monsters.PRIZE_WORLDS[guardian.kind]
            ids = monsters.prize_ids(game.systems[guardian.system_id], guardian)
            self.assertEqual([game.planet_at(guardian.system_id, pid).richness for pid in ids],
                             [richness for _, _, richness in expected])
        guardian = monsters.Guardian(1, 0, 'crystal_guardian', 80)
        self.assertEqual(monsters.prize_details(guardian), 'Mining output ×10')

    def test_ai_avoids_void_mines_but_can_develop_other_facilities(self):
        planet = self.game().headquarters()[1]
        planet.richness = 'Void'
        self.assertIsNone(ai.development_choice(planet, available=set(FACILITY_FAMILIES['mine'])))
        self.assertEqual(ai.development_choice(planet, available={'mine', 'research_lab'}), 'research_lab')

    def test_ai_does_not_assign_miners_on_void_colonies(self):
        game = self.game(with_ai=True, rival_race_id='kharuun')
        planet = game.headquarters('rival')[1]
        planet.richness, planet.miners = 'Void', 2
        game.opponent.resources = 20
        ai.run_ai(game, 'rival')
        self.assertEqual(planet.miners, 0)
        self.assertFalse(any(q.item_id in FACILITY_FAMILIES['mine'] for q in planet.construction_queue))

    def test_profile_upgrade_preserves_old_and_custom_multipliers(self):
        profile = balance.default_profile()
        profile['version'] = 22
        profile['data']['minerals'] = {name: {'multiplier': value} for name, value in
                                      [('Poor', .5), ('Average', 1.0), ('Rich', 1.5), ('Ultra-rich', 3.0)]}
        for poor in (.5, .7):
            profile['data']['minerals']['Poor']['multiplier'] = poor
            original = deepcopy(profile)
            upgraded = balance.upgrade_profile(profile)
            self.assertEqual(profile, original)
            self.assertFalse(balance.validate(upgraded))
            for name, values in original['data']['minerals'].items():
                self.assertEqual(upgraded['data']['minerals'][name]['multiplier'], values['multiplier'])
            self.assertEqual(upgraded['data']['minerals']['Void'], {'multiplier': 0.0, 'generation_weight': 40})
            balance.activate(upgraded)
            self.assertEqual(MINERAL_FACTORS['Poor'], poor)
        self.assertEqual(balance.default_profile()['data']['minerals']['Rich']['multiplier'], 4.0)

    def test_editor_accepts_zero_and_rejects_invalid_generation_weights(self):
        self.assertFalse(balance.validate(balance.default_profile()))
        for value in (-1, True, .1, float('nan')):
            with self.subTest(value=value):
                profile = balance.default_profile()
                profile['data']['minerals']['Rich']['generation_weight'] = value
                self.assertTrue(balance.validate(profile))
        profile = balance.default_profile()
        for entry in profile['data']['minerals'].values():
            entry['generation_weight'] = 0
        self.assertTrue(any('generation weight' in error for error in balance.validate(profile)))
        profile = balance.default_profile()
        profile['data']['minerals']['Void']['multiplier'] = -1
        self.assertTrue(balance.validate(profile))


if __name__ == '__main__':
    unittest.main()
