"""Food deficits must affect real turns, forecasts, jobs and saved populations."""

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from orion import balance, population
from orion.model import new_game
from orion.population_info import describe, growth_millions
from orion.storage import Storage


class StarvationTests(unittest.TestCase):
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

    def test_deficits_remove_population_on_real_turns_for_food_dependent_races(self):
        for race in ('terran', 'skirr', 'lithar', 'xenonflora', 'wanderers'):
            with self.subTest(race=race):
                game = self.game(race)
                world = game.headquarters()[1]
                world.farmers, world.biome, world.growth_progress = 0, 'Barren', 75
                report = game.population_report(world)
                self.assertLess(report.balance, 0)
                self.assertEqual(report.starvation_loss, 1)
                self.assertEqual(report.growth_rate, 0)
                self.assertIsNone(report.turns_to_growth)
                self.assertEqual(report.growth_caption, 'Food shortage: -1 B / turn')
                result = game.advance_turn()
                self.assertEqual((world.population, world.growth_progress), (7, 0))
                self.assertEqual(world.species, {race: 7})
                self.assertIn(f'Food shortage on {world.name}: 1 B inhabitants lost', result.alerts)

    def test_starvation_stops_when_lower_population_can_be_fed(self):
        game = self.game()
        world = game.headquarters()[1]
        world.farmers, world.growth_progress = 0, 90  # Six food for eight people.
        for expected in (7, 6, 6):
            game.advance_turn()
            self.assertEqual((world.population, world.growth_progress), (expected, 0))
        self.assertEqual(game.population_report(world).balance, 0)
        world.farmers = 1
        rate = game.population_report(world).growth_rate
        self.assertGreater(rate, 0)
        game.advance_turn()
        self.assertEqual((world.population, world.growth_progress), (6, rate))

    def test_starvation_precedes_capacity_limit(self):
        game = self.game()
        world = game.headquarters()[1]
        world.size, world.farmers, world.growth_progress = 'Tiny', 0, 75
        self.assertEqual(world.population, game.population_report(world).capacity)
        self.assertEqual(describe(game, world, live=True).rate_millions, -1000)
        game.advance_turn()
        self.assertEqual((world.population, world.growth_progress), (7, 0))

    def test_last_billion_survives_and_empty_worlds_do_not_gain_population(self):
        game = self.game()
        world = game.headquarters()[1]
        world.biome, world.farmers = 'Barren', 0
        for count in (0, 1):
            with self.subTest(population=count):
                world.population, world.growth_progress = count, 75
                for _ in range(3):
                    report = game.population_report(world)
                    self.assertEqual(growth_millions(report), 0)
                    self.assertFalse(population.advance(world, report))
                    self.assertEqual(world.population, count)
                if count:
                    self.assertEqual(world.growth_progress, 0)
        empty = next(p for s in game.systems for p in s.worlds if not p.colonized)
        before = deepcopy(empty)
        self.assertFalse(population.advance(empty, game.population_report(empty)))
        self.assertEqual(empty, before)

    def test_no_food_civilizations_continue_their_normal_growth(self):
        for race in ('nexus', 'aetheri'):
            with self.subTest(race=race):
                game = self.game(race)
                world = game.headquarters()[1]
                world.biome, world.farmers, world.growth_progress = 'Barren', 0, 0
                report = game.population_report(world)
                self.assertEqual((report.produced, report.consumed, report.starvation_loss), (0, 0, 0))
                self.assertGreater(report.growth_rate, 0)
                game.advance_turn()
                self.assertEqual((world.population, world.growth_progress), (8, report.growth_rate))

    def test_mixed_populations_cannot_grow_through_a_food_deficit(self):
        for other in ('nexus', 'aetheri'):
            with self.subTest(species=other):
                game = self.game('serevan')
                world = game.headquarters()[1]
                world.species = {'terran': 4, other: 4}
                world.biome, world.farmers = 'Barren', 0
                report = game.population_report(world)
                self.assertTrue(report.assembly or report.passive_growth)
                self.assertLess(report.balance, 0)
                self.assertEqual((report.base_growth_rate, report.growth_rate), (0, 0))
                game.advance_turn()
                self.assertEqual((world.population, world.growth_progress), (7, 0))
                self.assertEqual(sum(world.species.values()), 7)
                self.assertEqual(set(world.species), {'terran', other})

    def test_population_loss_keeps_jobs_valid_and_saves_resume_identically(self):
        game = self.game()
        world = game.headquarters()[1]
        world.biome, world.farmers, world.scientists, world.miners = 'Barren', 0, 4, 4
        game.advance_turn()
        self.assertEqual((world.population, world.scientists, world.miners, world.workers), (7, 4, 3, 0))
        self.assertEqual(world.species, {'terran': 7})
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(Path(folder))
            restored, _ = storage.load(storage.save(game))
            self.assertEqual(restored, game)
            for _ in range(8):
                self.assertEqual(restored.advance_turn(), game.advance_turn())
                self.assertEqual(restored, game)
        self.assertEqual((world.population, world.scientists, world.miners, world.workers), (1, 1, 0, 0))

    def test_new_farm_prevents_losses_from_the_following_turn(self):
        game = self.game()
        world = game.headquarters()[1]
        world.farmers = 0
        game.queue_building(0, world.id, 'hydroponic_farm')
        project = world.construction_queue[0]
        self.assertTrue(game.fund_project(project))
        project.progress = project.spec.work_cost-1
        result = game.advance_turn()
        self.assertIn('Hydroponic farm on Earth', result.completed)
        self.assertEqual((world.population, world.growth_progress), (7, 0))
        self.assertGreater(game.population_report(world).balance, 0)
        game.advance_turn()
        self.assertEqual(world.population, 7)
        self.assertGreater(world.growth_progress, 0)

    def test_construction_forecast_accounts_for_starvation_without_mutation(self):
        game = self.game()
        world = game.headquarters()[1]
        world.biome, world.farmers = 'Barren', 0
        game.resources = 10000
        game.queue_ship(0, world.id, 'scout')
        before = deepcopy(game.to_dict())
        estimate = game.queue_estimates(world)[0]
        self.assertEqual(game.to_dict(), before)
        self.assertIsNotNone(estimate)
        for _ in range(estimate-1):
            game.advance_turn()
            self.assertTrue(world.construction_queue)
        game.advance_turn()
        self.assertFalse(world.construction_queue)
        self.assertLess(world.population, 8)

    def test_opponents_follow_same_starvation_rule_and_keep_their_own_alerts(self):
        game = self.game(with_ai=True, rival_race_id='terran')
        world = game.headquarters('rival')[1]
        world.biome, world.farmers = 'Barren', 0
        with patch('orion.ai.run_ai', return_value=[]):
            result = game.advance_turn()
        self.assertEqual(world.population, 7)
        message = f'Food shortage on {world.name}: 1 B inhabitants lost'
        self.assertNotIn(message, result.alerts)
        self.assertIn(message+'.', [event.message for event in game.opponent.events])


if __name__ == '__main__':
    unittest.main()
