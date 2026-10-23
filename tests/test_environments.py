"""Environmental preferences affect real growth, settlement choices and saves."""

from copy import deepcopy
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')

from orion import balance, environments, exploration, population
from orion.ai import world_quality
from orion.model import BIOMES, GameState, PLAYER, Ship, new_game
from orion.production_breakdown import describe
from orion.races import RACES
from orion.storage import SAVE_VERSION, Storage


class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        old, configured = balance.active_profile(), balance._configured_path
        self.addCleanup(lambda: balance.activate(old))
        self.addCleanup(lambda: setattr(balance, '_configured_path', configured))
        balance._configured_path = None
        balance.activate(balance.default_profile())
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.storage = Storage(Path(self.tmp.name))

    def game(self, race_id='terran', **options):
        settings = dict(seed=2408, race_id=race_id, with_ai=False, with_guardians=False,
                        with_black_holes=False, with_tombs=False, with_encounters=False,
                        random_starts=False, fog_of_war=False)
        settings.update(options)
        return new_game(**settings)

    def test_complete_preference_table_and_soft_growth_penalties(self):
        self.assertEqual(set(environments.PREFERENCES), set(RACES))
        for values in environments.PREFERENCES.values():
            self.assertEqual(set(values), {*BIOMES, 'toxic_food'})
            self.assertTrue(all(10 <= values[b] <= 200 for b in BIOMES))

    def test_terran_growth_is_slower_on_ice_with_equal_food_surplus(self):
        game = self.game()
        world = game.headquarters()[1]
        terran = game.population_report(world)
        world.biome = 'Ice'
        world.farmers += 3  # Compensate exactly for lost natural food.
        icy = game.population_report(world)
        self.assertEqual(terran.balance, icy.balance)
        self.assertEqual((terran.growth_rate, icy.growth_rate), (10, 5))
        world.growth_progress = 95
        self.assertTrue(population.advance(world, icy))
        self.assertEqual(world.population, 9)

    def test_assembly_efficiency_changes_without_free_industry_or_food(self):
        game = self.game('nexus')
        world = game.headquarters()[1]
        ice = game.population_report(world)
        ice_industry = game.planet_yields(world)[0]
        world.biome = 'Terran'
        terran = game.population_report(world)
        self.assertTrue(ice.assembly)
        self.assertEqual(ice.assembly_industry, terran.assembly_industry)
        self.assertEqual(game.planet_yields(world)[0], ice_industry)
        self.assertEqual((ice.consumed, terran.consumed), (0, 0))
        self.assertEqual((ice.environment_percent, terran.environment_percent), (150, 60))
        self.assertGreater(ice.growth_rate, terran.growth_rate)

    def test_passive_growth_is_environment_sensitive_and_full_colonies_stop(self):
        game = self.game('aetheri')
        world = game.headquarters()[1]
        world.biome = 'Volcanic'
        self.assertEqual(game.population_report(world).growth_rate, 15)
        world.biome = 'Ice'
        self.assertEqual(game.population_report(world).growth_rate, 6)
        world.population = game.population_report(world).capacity
        self.assertEqual(game.population_report(world).growth_rate, 0)

    def test_native_homes_and_food_allocations_for_players_and_ai(self):
        for race_id, biome in environments.NATIVE_HOMES.items():
            with self.subTest(race=race_id):
                player = self.game(race_id)
                home = player.headquarters()[1]
                self.assertEqual(home.biome, biome)
                self.assertGreater(player.population_report(home).growth_rate, 0)
                self.assertGreaterEqual(player.population_report(home).balance, 0)
                rival = self.game(with_ai=True, rival_race_id=race_id, random_starts=True)
                self.assertEqual(rival.headquarters('rival')[1].biome, biome)

    def test_toxic_food_is_species_specific_and_visible_in_breakdown(self):
        game = self.game('skirr')
        world = game.headquarters()[1]
        self.assertEqual(environments.native_food(world), 6)
        report = describe(game, world, 'food')
        self.assertEqual(report.total, game.population_report(world).produced)
        self.assertTrue(any('toxic biota' in line for line in report.lines))
        world.species = {'terran': world.population}
        self.assertEqual(environments.native_food(world), 0)
        self.assertEqual(game.population_report(world).produced, report.total-6)

    def test_mixed_residents_keep_their_adaptation_and_survive_government_changes(self):
        game = self.game('serevan')
        world = game.headquarters()[1]
        world.biome = 'Ice'
        world.species = {'nexus': 4, 'terran': 4}
        before = deepcopy(world.species)
        self.assertEqual(game.population_report(world).environment_percent, 100)
        self.assertEqual(world.species, before)
        game.race_id = 'concord'
        self.assertEqual(game.population_report(world).environment_percent, 100)
        world.biome = 'Toxic'
        world.species = {'skirr': 4, 'terran': 4}
        self.assertEqual(environments.native_food(world), 3)
        self.assertEqual(environments.growth_factor(world), 87)

    def test_mobile_habitats_are_independent_of_orbited_terrain(self):
        game = self.game('wanderers')
        world = next(ship.habitat for ship in game.ships if ship.habitat is not None)
        world.species = {'skirr': world.population}
        for biome in BIOMES:
            world.biome = biome
            self.assertEqual(environments.growth_factor(world), 100)
            self.assertEqual(environments.native_food(world), 0)

    def test_positive_affinity_does_not_bypass_existing_settlement_rules(self):
        game = self.game()
        world = game.planet_at(0, 0)
        world.biome = 'Volcanic'
        self.assertGreater(environments.growth_factor(world, 'terran'), 0)
        self.assertFalse(game.can_settle(world))
        world.biome = 'Toxic'
        self.assertTrue(game.can_settle(world))
        self.assertEqual(environments.growth_factor(world, 'terran'), 25)
        game.race_id = 'varkesh'
        self.assertFalse(game.can_settle(world))

    def test_toxic_settlement_uses_the_real_colonization_action(self):
        game = self.game('skirr')
        world = game.planet_at(0, 3)
        world.biome = 'Toxic'
        ship = next(ship for ship in game.ships if ship.kind == 'colony_ship')
        game.colonize(ship.id, 0, world.id)
        self.assertEqual(world.species, {'skirr': 2})
        self.assertEqual(game.population_report(world).environment_percent, 150)
        self.assertGreaterEqual(game.population_report(world).balance, 0)

    def test_ai_weights_preferences_size_and_minerals_together(self):
        world = self.game().planet_at(0, 3)
        terran = replace(world, biome='Terran', size='Medium', richness='Average')
        ice = replace(terran, biome='Ice')
        toxic = replace(terran, biome='Toxic')
        self.assertGreater(world_quality(terran, 'terran'), world_quality(ice, 'terran'))
        self.assertGreater(world_quality(ice, 'nexus'), world_quality(terran, 'nexus'))
        self.assertGreater(world_quality(toxic, 'skirr'), world_quality(terran, 'skirr'))
        rich = replace(ice, size='Huge', richness='Ultra-rich')
        poor = replace(terran, size='Tiny', richness='Poor')
        self.assertGreater(world_quality(rich, 'terran'), world_quality(poor, 'terran'))

    def test_toxic_generation_and_campaign_continuation_are_deterministic(self):
        first = self.game('skirr', random_starts=True)
        second = self.game('skirr', random_starts=True)
        terrain = lambda game: [(s.id, p.id, p.biome) for s in game.systems for p in s.worlds]
        self.assertEqual(terrain(first), terrain(second))
        self.assertTrue(any(p.biome == 'Toxic' and not p.colonized for s in first.systems for p in s.worlds))
        path = self.storage.save(first)
        loaded, metadata = self.storage.load(path)
        self.assertEqual(metadata['version'], SAVE_VERSION)
        self.assertEqual(first.to_dict(), loaded.to_dict())
        first.advance_turn()
        loaded.advance_turn()
        self.assertEqual(first.to_dict(), loaded.to_dict())

    def test_v54_balance_upgrade_preserves_existing_worlds_and_custom_values(self):
        game = self.game('skirr')
        world = game.headquarters()[1]
        world.biome = 'Terran'
        exploration.refresh(game)
        path = self.storage.save(game)
        payload = json.loads(path.read_text())
        payload['version'] = 54
        old = payload['balance']
        old['version'] = 18
        del old['data']['environments']
        del old['data']['biomes']['Toxic']
        old['data']['biomes']['Ice']['habitability'] = 47
        path.write_text(json.dumps(payload))
        original = path.read_bytes()
        loaded, _ = self.storage.load(path)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(loaded.headquarters()[1].biome, 'Terran')
        profile = balance.profile_for(loaded)
        self.assertEqual(profile['data']['biomes']['Ice']['habitability'], 47)
        self.assertEqual(profile['data']['environments']['skirr']['Toxic'], 150)

    def test_custom_environment_settings_are_validated_and_saved_per_campaign(self):
        profile = balance.default_profile()
        profile['data']['environments']['nexus']['Ice'] = 120
        balance.activate(profile)
        game = self.game('nexus')
        self.assertEqual(game.population_report(game.headquarters()[1]).environment_percent, 120)
        path = self.storage.save(game)
        balance.activate(balance.default_profile())
        restored, _ = self.storage.load(path)
        self.assertEqual(restored.population_report(restored.headquarters()[1]).environment_percent, 120)
        profile['data']['environments']['nexus']['Ice'] = 0
        self.assertTrue(balance.validate(profile))


if __name__ == '__main__':
    unittest.main()
