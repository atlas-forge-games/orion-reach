"""Ice worlds preserve legacy economies, surveys and save validation."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from orion import balance, exploration, population, race_victory, research
from orion.model import BIOMES, HABITABILITY, GameState, SaveError
from orion.storage import SAVE_VERSION, Storage
from scenarios import fixed_start_game


def old_biomes(value):
    """Build a historical payload without changing user-supplied names."""
    if isinstance(value, dict):
        return {key: 'Tundra' if key == 'biome' and item == 'Ice' else old_biomes(item)
                for key, item in value.items()}
    if isinstance(value, list):
        return [old_biomes(item) for item in value]
    return value


class IcePlanetTests(unittest.TestCase):
    def setUp(self):
        previous, configured = balance.active_profile(), balance._configured_path
        self.addCleanup(lambda: balance.activate(previous))
        self.addCleanup(lambda: setattr(balance, '_configured_path', configured))
        balance._configured_path = None
        balance.activate(balance.default_profile())
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.storage = Storage(Path(self.tmp.name))

    def game(self):
        game = fixed_start_game(seed=2408, with_ai=False, fog_of_war=True)
        game.empire_name = 'Tundra Expedition'
        game.systems[0].biome = 'Ice'
        home = game.planet_at(0, 2)
        home.biome, home.name = 'Ice', 'Tundra Station'
        exploration.refresh(game)
        return game

    def legacy_profile(self):
        profile = balance.default_profile()
        profile['version'] = 17
        biomes = profile['data']['biomes']
        biomes['Tundra'] = biomes.pop('Ice')
        biomes['Tundra'].update(base_food=3, farmer_output=4, habitability=44)
        profile['data']['technologies']['habitat_shields']['description'] = '+2 credits per desert or tundra colony.'
        return profile

    def test_legacy_save_migrates_planets_surveys_and_custom_balance_without_rewriting(self):
        path = self.storage.save(self.game())
        payload = json.loads(path.read_text())
        payload['version'] = 53
        payload['game'] = old_biomes(payload['game'])
        payload['balance'] = self.legacy_profile()
        path.write_text(json.dumps(payload))
        original = path.read_bytes()
        loaded, raw = self.storage.load(path)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(raw, payload)
        self.assertEqual(loaded.systems[0].biome, 'Ice')
        home = loaded.planet_at(0, 2)
        self.assertEqual((home.biome, home.name), ('Ice', 'Tundra Station'))
        self.assertEqual(loaded.empire_name, 'Tundra Expedition')
        self.assertEqual(loaded.exploration.survey(0).worlds[2]['biome'], 'Ice')
        self.assertEqual((population.BASE_FOOD['Ice'], population.FARMER_OUTPUT['Ice'], HABITABILITY['Ice']), (3, 4, 44))
        self.assertEqual(balance.profile_for(loaded)['data']['biomes']['Ice'], payload['balance']['data']['biomes']['Tundra'])
        saved = self.storage.save(loaded)
        current = json.loads(saved.read_text())
        self.assertEqual(current['version'], SAVE_VERSION)
        self.assertEqual(current['balance']['version'], balance.VERSION)
        self.assertNotIn('Tundra', current['balance']['data']['biomes'])
        again, _ = self.storage.load(saved)
        self.assertEqual(again.to_dict(), loaded.to_dict())

    def test_profile_upgrade_preserves_custom_numbers_and_descriptions(self):
        profile = self.legacy_profile()
        original = deepcopy(profile)
        migrated = balance.upgrade_profile(profile)
        self.assertEqual(profile, original)
        self.assertFalse(balance.validate(migrated))
        self.assertEqual(migrated['data']['biomes']['Ice'], original['data']['biomes']['Tundra'])
        self.assertEqual(migrated['data']['technologies']['habitat_shields']['description'], '+2 credits per desert or ice colony.')
        profile['data']['technologies']['habitat_shields']['description'] = 'My custom habitat technology.'
        self.assertEqual(balance.upgrade_profile(profile)['data']['technologies']['habitat_shields']['description'], 'My custom habitat technology.')

    def test_current_saves_reject_obsolete_and_unknown_biomes(self):
        data = self.game().to_dict()
        for biome in ('Tundra', 'Typo world'):
            with self.subTest(biome=biome):
                broken = deepcopy(data)
                broken['systems'][0]['worlds'][2]['biome'] = biome
                with self.assertRaises(SaveError):
                    GameState.from_dict(broken)

    def test_ice_uses_existing_harsh_world_rules_and_default_values(self):
        self.assertIn('Ice', BIOMES)
        self.assertNotIn('Tundra', BIOMES)
        self.assertIn('Ice', race_victory.HARSH)
        self.assertEqual((HABITABILITY['Ice'], population.BASE_FOOD['Ice'], population.FARMER_OUTPUT['Ice']), (35, 0, 2))
        self.assertIn('habitat domes', research.TECHNOLOGIES['habitat_shields'].description)
        self.assertFalse(research.TECHNOLOGIES['habitat_shields'].effects)
        game = self.game()
        home = game.planet_at(0, 2)
        before = research.colony_yields(home, {})
        after = research.colony_yields(home, {'rough_income': 2})
        self.assertEqual(after[1] - before[1], 2)


if __name__ == '__main__':
    unittest.main()
