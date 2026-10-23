"""Gas giant generation, permanent settlement exclusion, saves and actual screens."""

from copy import deepcopy
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

from orion import balance, environments, exploration, gas_giants, outposts, tomb_worlds
from orion.ai import available_worlds
from orion.model import GameState, HABITABILITY, RuleError, SaveError, Ship, new_game
from orion.races import RACES
from orion.storage import Storage


class GasGiantTests(unittest.TestCase):
    def setUp(self):
        old, configured = balance.active_profile(), balance._configured_path
        self.addCleanup(lambda: balance.activate(old))
        self.addCleanup(lambda: setattr(balance, '_configured_path', configured))
        balance._configured_path = None
        balance.activate(balance.default_profile())
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def game(self, **options):
        settings = dict(seed=2408, with_ai=False, fog_of_war=False,
                        with_guardians=False, with_tombs=False,
                        with_black_holes=False, with_encounters=False)
        settings.update(options)
        return new_game(**settings)

    def giant(self, game):
        return next((s, p) for s in game.systems for p in s.worlds if p.is_gas_giant)

    def test_giants_append_in_outer_orbits_without_changing_existing_worlds_or_homes(self):
        for seed in (1, 42, 2408):
            with self.subTest(seed=seed):
                with patch('orion.gas_giants.seed'):
                    before = new_game(seed=seed, rival_count=5)
                after = new_game(seed=seed, rival_count=5)
                homes = {s.id for s, _ in after.settlements()}
                self.assertTrue(any(p.is_gas_giant for s in after.systems for p in s.worlds))
                for old, current in zip(before.systems, after.systems):
                    self.assertEqual((old.x, old.y, old.name, old.kind),
                                     (current.x, current.y, current.name, current.kind))
                    self.assertEqual(current.worlds[:len(old.worlds)], old.worlds)
                    self.assertEqual(current.planets, len(current.worlds))
                    self.assertLessEqual(current.planets, 8)
                    if current.planets > old.planets:
                        giant = current.worlds[-1]
                        self.assertNotIn(current.id, homes)
                        self.assertTrue(giant.is_gas_giant)
                        self.assertGreater(giant.orbit_au, old.worlds[-1].orbit_au)
                        self.assertEqual((giant.size, giant.gravity), ('Huge', 'High'))
                self.assertEqual(after.tomb_worlds, before.tomb_worlds)
                self.assertEqual(after.guardians, before.guardians)
                self.assertEqual(after.encounters, before.encounters)

    def test_generation_is_deterministic_and_idempotent(self):
        first, second = self.game(), self.game()
        self.assertEqual(first.systems, second.systems)
        before = deepcopy(first.systems)
        gas_giants.seed(first)
        self.assertEqual(first.systems, before)

    def test_no_race_or_technology_or_custom_habitability_can_settle_giants(self):
        for race in RACES:
            game = self.game(race_id=race)
            _, giant = self.giant(game)
            with patch.object(game, 'bonuses_for', return_value={'barren': 1, 'volcanic': 1, 'gas giant': 1}), patch.dict(HABITABILITY, {'Gas Giant': 100}):
                self.assertFalse(game.can_settle(giant), race)
            self.assertEqual(environments.growth_factor(giant, race), 0)
            self.assertEqual((giant.population_capacity, giant.building_capacity), (0, 0))

    def test_real_colonization_and_outpost_orders_fail_without_consuming_ships(self):
        game = self.game()
        system, giant = self.giant(game)
        colony = next(s for s in game.ships if s.kind == 'colony_ship')
        colony.system_id = system.id
        base = Ship(game.next_ship_id, 'outpost_ship', system.id)
        game.next_ship_id += 1
        game.ships.append(base)
        before = game.to_dict()
        self.assertIn('Gas giants', game.colonize_error(system.id, giant.id))
        with self.assertRaisesRegex(RuleError, 'Gas giants'):
            game.colonize(colony.id, system.id, giant.id)
        with self.assertRaisesRegex(RuleError, 'Gas giants'):
            outposts.deploy(game, base.id, system.id, giant.id)
        self.assertEqual(game.to_dict(), before)

    def test_ai_target_lists_exclude_giants(self):
        game = self.game(with_ai=True, rival_race_id='nexus')
        system, giant = self.giant(game)
        self.assertNotIn(giant.id, [p.id for p in available_worlds(game, system, 'rival')])
        system.worlds = [replace(giant, id=0)]
        system.planets = 1
        exploration.refresh(game)
        self.assertEqual(available_worlds(game, system, 'rival'), [])
        self.assertNotIn(system.id, [s.id for _, s in outposts.expansion_targets(game, 'rival')])

    def test_mobile_habitats_keep_their_capacity_and_environment(self):
        game = self.game(race_id='wanderers')
        habitat = next(s.habitat for s in game.ships if s.habitat)
        habitat.biome = 'Gas Giant'
        self.assertFalse(habitat.is_gas_giant)
        self.assertEqual((habitat.population_capacity, habitat.building_capacity), (50, 12))
        self.assertEqual(environments.growth_factor(habitat), 100)

    def test_giants_and_surveys_survive_saving_and_turn_continuation(self):
        game = self.game(with_ai=True, fog_of_war=True)
        system, giant = self.giant(game)
        exploration.record_survey(game, system.id, 'player')
        storage = Storage(self.tmp.name)
        loaded, metadata = storage.load(storage.save(game))
        self.assertEqual(metadata['version'], 56)
        self.assertEqual(loaded, game)
        self.assertTrue(loaded.known_system(system.id).worlds[giant.id].is_gas_giant)
        game.advance_turn(); loaded.advance_turn()
        self.assertEqual(loaded, game)

    def test_old_campaign_and_custom_balance_upgrade_without_adding_worlds(self):
        with patch('orion.gas_giants.seed'):
            game = self.game()
        storage = Storage(self.tmp.name)
        path = storage.save(game)
        payload = json.loads(path.read_text())
        payload['version'] = 55
        payload['balance']['version'] = 19
        del payload['balance']['data']['biomes']['Gas Giant']
        payload['balance']['data']['environments']['terran']['Ice'] = 65
        path.write_text(json.dumps(payload))
        before = path.read_bytes()
        loaded, _ = storage.load(path)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(loaded.systems, game.systems)
        self.assertFalse(any(p.is_gas_giant for s in loaded.systems for p in s.worlds))
        upgraded = balance.profile_for(loaded)
        self.assertEqual(upgraded['version'], 20)
        self.assertEqual(upgraded['data']['environments']['terran']['Ice'], 65)
        self.assertEqual(upgraded['data']['biomes']['Gas Giant']['habitability'], 0)

    def test_saves_reject_forged_giant_colonies_outposts_and_tombs(self):
        game = self.game()
        system, giant = self.giant(game)
        for kind in ('colony', 'outpost', 'tomb'):
            data = game.to_dict()
            world = data['systems'][system.id]['worlds'][giant.id]
            if kind == 'colony':
                world.update(colonized=True, owner='player', population=2, species={'terran': 2})
            elif kind == 'outpost':
                world.update(outpost_owner='player', outpost_hull=30)
            else:
                data['tomb_worlds'].append(asdict(tomb_worlds.TombWorld(system.id, giant.id)))
            with self.subTest(kind=kind), self.assertRaises(SaveError):
                GameState.from_dict(data)
        before = game.to_dict()
        self.assertIsNone(tomb_worlds.awaken(game, tomb_worlds.TombWorld(system.id, giant.id)))
        self.assertEqual(game.to_dict(), before)
        tomb_worlds.seed_worlds(game)
        self.assertTrue(all(not game.planet_at(t.system_id, t.planet_id).is_gas_giant for t in game.tomb_worlds))

    def test_actual_overview_disables_settlement_and_hides_worker_controls(self):
        import pygame as pg
        from orion.app import App
        app = App(Path(self.tmp.name), capture=True)
        self.addCleanup(pg.quit)
        self.addCleanup(app.audio.close)
        app.game = self.game()
        system, giant = self.giant(app.game)
        app.game.selected_system = system.id
        app.open_planet(giant.id)
        before = app.game.to_dict()
        app.render()
        buttons = {b.key: b for b in app.buttons}
        self.assertFalse(buttons['colonize_planet'].enabled)
        self.assertFalse(buttons['establish_outpost'].enabled)
        self.assertFalse(any(key.startswith(('worker_', 'surface_')) for key in buttons))
        self.assertEqual(app.game.to_dict(), before)

    def test_large_globes_have_full_click_targets_without_overlap(self):
        from orion.system_views import system_layout
        _, giant = self.giant(self.game())
        for count in (2, 4, 6, 8):
            worlds = [replace(giant, id=i, biome='Terran') for i in range(count-1)] + [giant]
            layout = system_layout(worlds)
            for _, center, diameter, hit in layout:
                self.assertGreaterEqual(hit.width, diameter)
                self.assertTrue(hit.collidepoint(center))
            self.assertGreater(layout[-1][2], layout[0][2])
            self.assertFalse(any(a[3].colliderect(b[3]) for i, a in enumerate(layout) for b in layout[i+1:]))


if __name__ == '__main__':
    unittest.main()
