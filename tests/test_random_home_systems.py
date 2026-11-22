"""Random alien neighbors preserve homeworlds, fleets, raids and saved galaxies."""

from collections import Counter
from dataclasses import asdict
import unittest
from unittest.mock import patch

from orion import balance, environments, raiding
from orion.home_systems import randomize_player_home
from orion.model import GameState, StarSystem, generate_planets, new_game
from orion.races import RACES


class RandomHomeSystemTests(unittest.TestCase):
    def setUp(self):
        old, configured = balance.active_profile(), balance._configured_path
        self.addCleanup(lambda: balance.activate(old))
        self.addCleanup(lambda: setattr(balance, '_configured_path', configured))
        balance._configured_path = None
        balance.activate(balance.default_profile())

    def game(self, race='terran', **options):
        settings = dict(seed=2408, race_id=race, random_starts=False, with_ai=False,
                        with_guardians=False, with_tombs=False, with_black_holes=False,
                        with_encounters=False)
        settings.update(options)
        return new_game(**settings)

    def test_terran_sol_keeps_all_four_original_worlds(self):
        expected = [('Mercury', 'Barren', 'Tiny', 'Rich', 'Low', .39),
                    ('Venus', 'Volcanic', 'Medium', 'Average', 'Normal', .72),
                    ('Earth', 'Terran', 'Medium', 'Average', 'Normal', 1.0),
                    ('Mars', 'Desert', 'Small', 'Average', 'Low', 1.52)]
        for seed in (0, 1, 42, 2408):
            for random_starts in (False, True):
                with self.subTest(seed=seed, random_starts=random_starts):
                    game = self.game(seed=seed, random_starts=random_starts)
                    system = game.systems[0]
                    self.assertEqual((system.name, system.planets), ('Sol', 4))
                    self.assertEqual([(p.name, p.biome, p.size, p.richness, p.gravity, p.orbit_au)
                                      for p in system.worlds], expected)
                    self.assertEqual(game.headquarters()[1].id, 2)

    def test_each_alien_race_varies_planet_count_and_neighbor_types_with_seed(self):
        for race in RACES:
            if race == 'terran':
                continue
            counts, biomes = set(), set()
            for seed in range(96):
                system = StarSystem(0, 'Sol', .35, .55, 'Yellow dwarf', 4, 'Terran', 'Average')
                system.worlds = generate_planets(system, seed)
                original = asdict(system.worlds[2])
                randomize_player_home(system, seed, race)
                counts.add(system.planets)
                home = next(p for p in system.worlds if p.colonized)
                original['id'] = home.id
                self.assertEqual(asdict(home), original)
                self.assertEqual(system.planets, len(system.worlds))
                self.assertEqual([p.id for p in system.worlds], list(range(system.planets)))
                self.assertTrue(all(a.orbit_au < b.orbit_au for a, b in zip(system.worlds, system.worlds[1:])))
                biomes.update(p.biome for p in system.worlds if p is not home)
            with self.subTest(race=race):
                self.assertEqual(counts, set(range(1, 8)))
                self.assertTrue({'Terran', 'Ocean', 'Desert', 'Ice', 'Barren', 'Volcanic', 'Toxic', 'Gas Giant'} <= biomes)

    def test_all_races_keep_native_home_properties_population_jobs_and_fleets(self):
        for race in RACES:
            for random_starts in (False, True):
                with self.subTest(race=race, random_starts=random_starts):
                    game = self.game(race, random_starts=random_starts)
                    system = game.systems[0]
                    physical_home = next(p for p in system.worlds if p.name == RACES[race].homeworld)
                    self.assertEqual((physical_home.biome, physical_home.size, physical_home.richness,
                                      physical_home.gravity, physical_home.orbit_au),
                                     (environments.NATIVE_HOMES.get(race, 'Terran'), 'Medium', 'Average', 'Normal', 1.0))
                    home = game.headquarters()[1]
                    self.assertEqual((home.population, home.species), (8, {race: 8}))
                    self.assertGreaterEqual(game.population_report(home).balance, 0)
                    self.assertEqual(home.farmers+home.workers+home.scientists+home.miners, home.workforce)
                    expected = ({'scout': 2, 'frigate': 1, 'troop_transport': 2} if race == 'varkesh'
                                else {'scout': 2, 'mothership': 1} if race == 'wanderers'
                                else {'scout': 2, 'colony_ship': 1})
                    self.assertEqual(Counter(s.kind for s in game.ships_owned_by()), expected)
                    self.assertTrue(all(s.system_id == 0 for s in game.ships_owned_by()))
                    self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_random_start_setting_only_changes_star_positions(self):
        for race in RACES:
            with self.subTest(race=race):
                fixed = self.game(race, random_starts=False)
                moved = self.game(race, random_starts=True)
                self.assertEqual(fixed.systems[0].worlds, moved.systems[0].worlds)
                self.assertNotEqual((fixed.systems[0].x, fixed.systems[0].y),
                                    (moved.systems[0].x, moved.systems[0].y))

    def test_home_randomization_does_not_change_other_systems_or_ai_starts(self):
        for race in ('skirr', 'varkesh', 'wanderers'):
            with self.subTest(race=race):
                with patch('orion.model.randomize_player_home'):
                    before = self.game(race, random_starts=True, rival_count=5)
                after = self.game(race, random_starts=True, rival_count=5)
                self.assertEqual([(s.x, s.y, s.kind) for s in before.systems],
                                 [(s.x, s.y, s.kind) for s in after.systems])
                self.assertEqual(before.systems[1:], after.systems[1:])
                self.assertEqual(before.opponents, after.opponents)

    def test_seeded_campaigns_and_save_continuation_are_identical(self):
        for race in ('skirr', 'nexus', 'varkesh', 'wanderers'):
            with self.subTest(race=race):
                first = self.game(race, with_ai=True, rival_count=3, random_starts=True)
                second = self.game(race, with_ai=True, rival_count=3, random_starts=True)
                a, b = first.to_dict(), second.to_dict()
                a.pop('campaign_id')
                b.pop('campaign_id')
                self.assertEqual(a, b)
                with patch('orion.model.randomize_player_home', side_effect=AssertionError('Save rerolled planets')):
                    restored = GameState.from_dict(first.to_dict())
                self.assertEqual(restored, first)
                for _ in range(3):
                    self.assertEqual(restored.advance_turn(), first.advance_turn())
                    self.assertEqual(restored, first)

    def test_old_fixed_alien_systems_load_without_being_regenerated(self):
        with patch('orion.model.randomize_player_home'):
            game = self.game('varkesh')
        game.headquarters()[1].slaves = 3
        with patch('orion.model.randomize_player_home', side_effect=AssertionError('Save rerolled planets')):
            restored = GameState.from_dict(game.to_dict())
        self.assertEqual(restored, game)
        self.assertEqual(raiding.home_location(restored), (0, 2))

    def test_small_varkesh_systems_return_raid_captives_to_the_actual_home(self):
        seeds = {}
        for seed in range(40):
            game = self.game('varkesh', seed=seed)
            seeds.setdefault(len(game.systems[0].worlds), seed)
        for count in (1, 2):
            with self.subTest(planets=count):
                game = self.game('varkesh', seed=seeds[count], with_ai=True, rival_race_id='terran')
                system, home = game.headquarters()
                self.assertEqual(raiding.home_location(game), (system.id, home.id))
                self.assertIs(raiding.homeworld(game), home)
                enemy_system, enemy = game.headquarters('rival')
                game.ships = game.ships_owned_by()  # The raid starts after clearing the defenders.
                for ship in game.ships_owned_by():
                    ship.system_id = enemy_system.id
                report = game.invade(enemy_system.id, enemy.id)
                self.assertTrue(report.captured)
                self.assertGreater(report.slaves_taken, 0)
                self.assertEqual(home.slaves, report.slaves_taken)
                self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_wanderer_mothership_keeps_its_population_in_one_planet_system(self):
        game = next(g for seed in range(40) if len((g := self.game('wanderers', seed=seed)).systems[0].worlds) == 1)
        home = game.headquarters()[1]
        self.assertTrue(home.habitat)
        self.assertEqual((home.name, home.population, game.population_report(home).capacity), ('Haven Ark', 8, 50))
        self.assertTrue(all(not p.colonized for p in game.systems[0].worlds))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)


if __name__ == '__main__':
    unittest.main()
