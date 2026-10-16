"""Combat prizes, ownership, raid limits and old campaign compatibility."""
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
from orion import boarding, combat, motherships, ground_combat, balance, exploration
from orion.model import new_game, Ship, GameState, RuleError, SaveError
from orion.storage import Storage
from orion.victory import transport_losses


def scenario(race='terran'):
    game = new_game(seed=12, race_id=race, rival_race_id='wanderers', with_ai=True,
                    random_starts=False, with_guardians=False, with_tombs=False, with_black_holes=False)
    home = motherships.homes(game, 'rival')[0]
    motherships.create(game, home.system_id, 'rival')  # Keep the war going after capture.
    home.system_id = 0
    home.habitat.population = 20
    home.habitat.buildings = ['factory', 'research_lab']
    frigate = add_ship(game, 'frigate')
    for _ in range(8):
        add_ship(game, 'troop_transport')
    exploration.refresh(game)
    return game, home, frigate


def add_ship(game, kind, owner='player', sid=0):
    ship = Ship(game.next_ship_id, kind, sid, owner=owner)
    game.next_ship_id += 1
    game.ships.append(ship)
    return ship


def defeat(game, home):
    game.start_combat(home.system_id, target=home.owner)
    victim = game.combat.ship(home.id)
    victim.hull = victim.shields = 0
    combat.check_losses(game)
    game.finish_combat()


class MothershipBoardingTests(unittest.TestCase):
    def test_starting_lasers_and_shields_absorb_real_hits(self):
        game, home, frigate = scenario()
        battle = game.start_combat(0, target='rival')
        target, gun = battle.ship(home.id), battle.ship(frigate.id)
        self.assertEqual((target.weapon, target.shields, target.max_shields), ('laser', 12, 12))
        gun.x, gun.y = 4, 4
        target.x, target.y = 5, 4
        before = target.hull
        combat.fire(game, gun.id, target.id)
        self.assertEqual(target.hull, before)
        self.assertLess(target.shields, 12)
        self.assertGreater(target.damage, 0)

    def test_disable_then_capture_preserves_city_and_surviving_transports(self):
        game, home, _ = scenario()
        home.habitat.garrison = 5
        name, buildings, population = home.name, home.habitat.buildings.copy(), home.habitat.population
        defeat(game, home)
        self.assertEqual((home.hull, home.disabled_turns), (1, 3))
        self.assertFalse(list(combat.hostile_pairs(game)))
        with self.assertRaises(RuleError):
            game.send_ship(home.id, 1, owner='rival')
        before = len([s for s in game.ships if s.kind == 'troop_transport'])
        report = game.invade(0, home.habitat.id)
        self.assertTrue(report.captured)
        self.assertEqual((home.owner, home.habitat.owner), ('player', 'player'))
        self.assertEqual((home.name, home.habitat.buildings, home.habitat.population), (name, buildings, population))
        lost, garrison = transport_losses(before, report.attacker_survivors)
        self.assertEqual(len([s for s in game.ships if s.kind == 'troop_transport']), before-lost)
        self.assertEqual(home.habitat.garrison, garrison)
        self.assertIn('Wanderers', game.ship_build_error(0, home.habitat.id, 'mothership'))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        for _ in range(3):
            boarding.advance(game)
        self.assertEqual(home.disabled_turns, 0)
        self.assertIsNone(game.ship_build_error(0, home.habitat.id, 'scout'))
        game.systems[1].x, game.systems[1].y = game.systems[0].x+.03, game.systems[0].y
        game.send_ship(home.id, 1)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_raid_uses_actual_stocks_leaves_owner_and_has_persistent_cooldown(self):
        game, home, _ = scenario()
        defeat(game, home)
        game.opponent.credits, game.opponent.resources = 17, 9
        before = game.credits, game.resources
        report = boarding.assault(game, home.id, 'raid')
        self.assertTrue(report.captured)
        self.assertEqual((report.credits_stolen, report.resources_stolen, report.slaves_taken), (17, 9, 0))
        self.assertEqual((game.credits, game.resources), (before[0]+17, before[1]+9))
        self.assertEqual((game.opponent.credits, game.opponent.resources), (0, 0))
        self.assertEqual((home.owner, home.habitat.population), ('rival', 20))
        with self.assertRaises(RuleError):
            boarding.assault(game, home.id, 'raid')
        loaded = GameState.from_dict(game.to_dict())
        loaded.turn += 1
        self.assertIn('9 turns', boarding.error(loaded, home.id, 'raid'))
        loaded.turn += 9
        self.assertIsNone(boarding.error(loaded, home.id, 'raid'))

    def test_varkesh_captives_capped_by_population_and_home_capacity(self):
        game, home, _ = scenario('varkesh')
        prison = game.planet_at(0, 2)
        prison.slaves = 98
        defeat(game, home)
        report = boarding.assault(game, home.id, 'raid')
        self.assertEqual(report.slaves_taken, 2)
        self.assertEqual(prison.slaves, 100)
        self.assertEqual(home.habitat.population, 18)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        home.habitat.population = 1
        self.assertEqual(boarding.loot(game, home)[2], 0)

    def test_failed_boarding_has_casualties_no_loot_or_capture(self):
        game, home, _ = scenario()
        defeat(game, home)
        transports = [s for s in game.ships if s.kind == 'troop_transport']
        game.ships[:] = [s for s in game.ships if s not in transports[1:]]
        stocks = game.credits, game.resources, game.opponent.credits, game.opponent.resources
        report = boarding.assault(game, home.id, 'raid')
        self.assertFalse(report.captured)
        self.assertEqual((game.credits, game.resources, game.opponent.credits, game.opponent.resources), stocks)
        self.assertEqual(home.owner, 'rival')
        self.assertGreater(home.habitat.militia_losses, 0)
        self.assertEqual(home.raided_turn, 0)

    def test_protection_treaties_and_action_preconditions(self):
        game, home, _ = scenario()
        self.assertIn('defenses first', boarding.error(game, home.id))
        defeat(game, home)
        escort = add_ship(game, 'frigate', 'rival')
        self.assertIn('defending fleet', boarding.error(game, home.id))
        game.ships.remove(escort)
        game.diplomacy.non_aggression_active = True
        self.assertIsNotNone(boarding.error(game, home.id))
        game.diplomacy.non_aggression_active = False
        game.ships[:] = [s for s in game.ships if s.kind != 'troop_transport']
        self.assertIn('troop transports', boarding.error(game, home.id))
        self.assertIsNone(boarding.error(game, home.id, 'destroy'))

    def test_destroy_grants_salvage_once_and_retains_readable_news(self):
        game, home, _ = scenario()
        defeat(game, home)
        name = home.name
        expected, before = boarding.salvage(game, home), game.resources
        self.assertEqual(boarding.assault(game, home.id, 'destroy'), expected)
        self.assertEqual(game.resources, before+expected)
        self.assertNotIn(home, game.ships)
        self.assertIn(name, game.diplomatic_news[-1].message)
        with self.assertRaises(RuleError):
            boarding.assault(game, home.id, 'destroy')
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_live_resolved_captured_saves_and_old_unarmed_battle_migrate(self):
        game, home, _ = scenario()
        game.start_combat(0, target='rival')
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        old = game.to_dict()
        for ship in old['ships']:
            for key in ('disabled_turns', 'raided_turn', 'assaulted_turn'):
                ship.pop(key)
        for ship in old['combat']['ships']:
            if ship['kind'] == 'mothership':
                ship['weapon'], ship['shields'] = 'none', 0
        original = copy.deepcopy(old)
        migrated = GameState.from_dict(old, version=46)
        self.assertEqual(old, original)
        self.assertEqual(migrated.combat.ship(home.id).weapon, 'laser')
        victim = game.combat.ship(home.id)
        victim.hull = victim.shields = 0
        combat.check_losses(game)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        game.finish_combat()
        boarding.assault(game, home.id)
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            self.assertEqual(storage.load(storage.save(game))[0], game)

    def test_malformed_disable_and_raid_state_rejected(self):
        game, home, _ = scenario()
        raw = game.to_dict()
        index = next(i for i, s in enumerate(raw['ships']) if s['id'] == home.id)
        for change in ({'disabled_turns': -1}, {'disabled_turns': 4}, {'raided_turn': game.turn+1}, {'assaulted_turn': True}):
            broken = copy.deepcopy(raw)
            broken['ships'][index].update(change)
            with self.subTest(change=change), self.assertRaises(SaveError):
                GameState.from_dict(broken)

    def test_disabled_home_recovers_only_with_completed_turns_and_cannot_launch(self):
        game, home, _ = scenario()
        defeat(game, home)
        game.resources = game.credits = 10000
        self.assertIn('repairs', game.ship_build_error(0, home.habitat.id, 'scout', owner='rival'))
        with patch('orion.ai.run_ai', return_value=[]):
            for remaining in (2, 1):
                game.advance_turn()
                self.assertEqual(home.disabled_turns, remaining)
            game.advance_turn()
        self.assertEqual(home.disabled_turns, 0)
        # The restored defenses now trigger an encounter; the turn itself completed.
        self.assertGreater(home.hull, 1)

    def test_balance_upgrade_preserves_custom_nonzero_armament(self):
        profile = balance.default_profile()
        profile['version'] = 11
        profile['data']['ships']['mothership']['damage'] = 0
        upgraded = balance.upgrade_profile(profile)
        self.assertEqual(upgraded['data']['ships']['mothership']['damage'], 5)
        self.assertEqual(profile['data']['ships']['mothership']['damage'], 0)
        profile['data']['ships']['mothership']['damage'] = 7
        self.assertEqual(balance.upgrade_profile(profile)['data']['ships']['mothership']['damage'], 7)

    def test_tactical_autoresolve_leaves_a_boardable_city(self):
        game, home, _ = scenario()
        for _ in range(3):
            add_ship(game, 'battleship')
        game.start_combat(0, target='rival')
        combat.autoresolve(game)
        self.assertEqual(game.combat.status, 'player_victory')
        self.assertEqual(home.disabled_turns, 3)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        game.finish_combat()
        self.assertIsNone(boarding.error(game, home.id))

    def test_ai_captures_disabled_player_home_and_returns_report(self):
        game, home, _ = scenario()
        # Give the mobile home to the player and put the assault fleet on the AI side.
        home.owner = home.habitat.owner = 'player'
        for ship in game.ships:
            if ship.system_id == 0 and ship is not home:
                ship.owner = 'rival'
        from orion.diplomacy import start_war
        start_war(game, 'rival', 'player')
        boarding.disable(game, home)
        reports = []
        messages = boarding.ai_orders(game, 'rival', reports)
        self.assertTrue(messages)
        self.assertEqual(home.owner, 'rival')
        self.assertEqual(reports[0].cause, 'boarding')
        self.assertTrue(reports[0].captured)

    def test_wanderers_can_recapture_an_enemy_mothership(self):
        game, home, _ = scenario('wanderers')
        defeat(game, home)
        self.assertIsNone(game.invasion_error(0, home.habitat.id))
        self.assertTrue(game.invade(0, home.habitat.id).captured)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_disabled_shipyard_queue_estimate_matches_completion(self):
        from orion.model import ConstructionProject
        game = new_game(seed=12, race_id='wanderers', with_ai=False, random_starts=False,
                        with_guardians=False, with_tombs=False, with_black_holes=False)
        home = motherships.homes(game)[0]
        game.resources = 10000
        home.habitat.construction_queue = [ConstructionProject('scout')]
        project = home.habitat.construction_queue[0]
        project.progress = project.spec.work_cost-1
        boarding.disable(game, home)
        estimate = game.queue_estimates(home.habitat)[0]
        self.assertEqual(estimate, 4)
        for _ in range(3):
            game.advance_turn()
            self.assertTrue(home.habitat.construction_queue)
        game.advance_turn()
        self.assertFalse(home.habitat.construction_queue)

    def test_retreat_saves_mobile_convoys_and_leaves_disabled_homes_behind(self):
        for disabled in (False, True):
            with self.subTest(disabled=disabled):
                game, home, _ = scenario()
                escort = add_ship(game, 'frigate', 'rival')
                game.start_combat(0, target='rival')
                if disabled:
                    unit = game.combat.ship(home.id)
                    unit.hull = unit.shields = 0
                    combat.check_losses(game)
                combat.end_turn(game)
                combat.retreat(game, 'rival')
                self.assertTrue(escort.in_transit)
                self.assertEqual(escort.speed_bonus, game.ship_speed_bonus('rival', slow=not disabled))
                self.assertEqual(home.in_transit, not disabled)
                self.assertEqual(home.disabled_turns, 3 if disabled else 0)
                self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_home_controls_launch_boarding_raid_and_confirm_destruction(self):
        import pygame as pg
        from orion.app import App
        from orion.fleet_art import load_ship_art
        with tempfile.TemporaryDirectory() as folder:
            app = App(Path(folder), capture=True)
            try:
                app.game, home, _ = scenario('varkesh')
                game = app.game
                defeat(game, home)
                from orion.first_contact import acknowledge
                acknowledge(game, "rival")
                app.open_mothership(home.id)
                app.dialog = None
                app.render()
                self.assertIsNotNone(load_ship_art('mothership'))
                actions = {b.key: b for b in app.buttons}
                for mode in ('capture', 'raid', 'destroy'):
                    self.assertTrue(actions['mothership_'+mode].enabled)
                actions['mothership_capture'].action()
                app.render()
                self.assertEqual(app.ground_mode, 'capture')
                self.assertEqual(app.screen, 'ground')
                app.close_ground()
                app.mothership_action_request(home.id, 'raid')
                app.render()
                app.launch_ground_assault()
                app.render()
                self.assertEqual(app.ground_reports[0].cause, 'mothership_raid')
                app.close_ground()
                app.render()
                self.assertFalse(next(b for b in app.buttons if b.key == 'mothership_raid').enabled)
                app.mothership_action_request(home.id, 'destroy')
                self.assertIsNotNone(app.dialog)
                self.assertIn(home, game.ships)
            finally:
                app.audio.close()
                pg.quit()


if __name__ == '__main__':
    unittest.main()
