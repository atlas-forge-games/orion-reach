"""Diplomatic commitments, fog-aware intimidation, conserved tribute and migration."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')

from orion import ai, balance, coalitions, diplomacy, first_contact, news, tribute
from orion import diplomatic_preferences as preferences
from orion.model import GameState, RuleError, SaveError, Ship
from orion.storage import Storage
from scenarios import empty_fleet_game


def campaign(**kwargs):
    return empty_fleet_game(seed=12, fog_of_war=kwargs.pop('fog_of_war', False),
                            rival_race_id=kwargs.pop('rival_race_id', 'terran'), with_guardians=False, **kwargs)


def frontier():
    game = campaign(rival_count=2)
    for i, owner in enumerate(game.owners):
        system, _ = game.headquarters(owner)
        system.x, system.y = .2+i*.025, .5
    game.diplomacy.relations = 30
    return game


def navy(game, owner, system, count=24):
    for _ in range(count):
        game.ships.append(Ship(game.next_ship_id, 'frigate', system, owner=owner))
        game.next_ship_id += 1


def later(game, turns):
    game.turn += turns
    game.year += turns


class CoalitionTests(unittest.TestCase):
    def test_frontier_pressure_forms_defensive_agreement(self):
        game = frontier()
        self.assertTrue(coalitions.willingness(game, 'rival', 'player', 'rival_2')[1])
        coalitions.form(game, 'player', 'rival', 'rival_2')
        self.assertEqual(game.diplomacy.coalition_target, 'rival_2')
        self.assertFalse(game.diplomacy_between('player', 'rival_2').at_war)
        self.assertIn('coalition', diplomacy.aggression_error(game, 'player', 'rival'))
        self.assertNotIn('player', ai.enemies(game, 'rival'))
        diplomacy.advance_diplomacy(game)
        self.assertEqual(game.diplomacy.relations, 31)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_target_attack_calls_partner_but_offensive_declaration_does_not(self):
        for offensive in (False, True):
            game = frontier()
            coalitions.form(game, 'player', 'rival', 'rival_2')
            diplomacy.start_war(game, *('player', 'rival_2') if offensive else ('rival_2', 'player'))
            self.assertEqual(game.diplomacy_between('rival', 'rival_2').at_war, not offensive)
            # Subsequent combat during the war must not convert an offensive war to a defensive call.
            diplomacy.start_war(game, 'rival_2', 'player')
            self.assertEqual(game.diplomacy_between('rival', 'rival_2').at_war, not offensive)
            self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_existing_war_requires_explicit_atomic_confirmation(self):
        game = frontier()
        diplomacy.start_war(game, 'rival_2', 'rival')
        before = game.to_dict()
        with self.assertRaisesRegex(RuleError, 'Explicitly confirm'):
            coalitions.form(game, 'player', 'rival', 'rival_2')
        self.assertEqual(game.to_dict(), before)
        coalitions.form(game, 'player', 'rival', 'rival_2', join_war=True)
        self.assertTrue(game.diplomacy_between('player', 'rival_2').at_war)

    def test_conflicting_protection_pacts_block_proposals_in_both_directions(self):
        game = frontier()
        game.diplomacy_between('player', 'rival_2').non_aggression_active = True
        self.assertIn('protection', coalitions.proposal_error(game, 'player', 'rival', 'rival_2'))
        game.diplomacy_between('player', 'rival_2').non_aggression_active = False
        coalitions.form(game, 'player', 'rival', 'rival_2')
        for action in ('non_aggression', 'friendship'):
            self.assertIn('coalition', game.diplomacy_error(action, 'rival_2'))

    def test_no_common_threat_and_unknown_target_cannot_create_coalition(self):
        game = campaign(rival_count=2, fog_of_war=True)
        before = game.to_dict()
        with self.assertRaises(RuleError):
            coalitions.form(game, 'player', 'rival', 'rival_2')
        self.assertEqual(game.to_dict(), before)
        for a, b in (('player', 'rival'), ('player', 'rival_2'), ('rival', 'rival_2')):
            first_contact.establish(game, a, b)
        game.diplomacy.relations = 100
        self.assertFalse(coalitions.willingness(game, 'rival', 'player', 'rival_2')[1])
        self.assertIn('declined', coalitions.form(game, 'player', 'rival', 'rival_2'))

    def test_leaving_remembers_betrayal_but_target_defeat_does_not(self):
        game = frontier()
        coalitions.form(game, 'player', 'rival', 'rival_2')
        game.diplomacy.trade_active = True
        coalitions.leave(game, 'player', 'rival')
        self.assertEqual(game.diplomacy.broken_promises, {'player': 1})
        self.assertTrue(game.diplomacy.trade_active)
        game = frontier()
        coalitions.form(game, 'player', 'rival', 'rival_2')
        for system in game.colony_systems('rival_2'):
            for world in system.worlds:
                if world.owner == 'rival_2':
                    world.owner, world.colonized = None, False
        game.eliminate_defeated()
        self.assertIsNone(game.diplomacy.coalition_target)
        self.assertFalse(game.diplomacy.broken_promises)

    def test_ai_can_form_coalitions_without_enrolling_human(self):
        game = frontier()
        before = game.to_dict()
        with self.assertRaisesRegex(RuleError, 'player must propose'):
            coalitions.form(game, 'rival', 'player', 'rival_2', join_war=True)
        self.assertEqual(game.to_dict(), before)
        later(game, 5)
        game.diplomacy_between('rival', 'rival_2').relations = 80
        diplomacy.start_war(game, 'player', 'rival')
        diplomacy.start_war(game, 'player', 'rival_2')
        coalitions.ai_orders(game, 'rival')
        self.assertEqual(game.diplomacy_between('rival', 'rival_2').coalition_target, 'player')
        self.assertFalse(game.diplomacy.coalition_target)
        self.assertGreater(news.unread_count(game), 0)
        news.mark_read(game)
        self.assertEqual(news.unread_count(game), 0)

    def test_linked_partners_all_defend_against_same_target(self):
        game = campaign(rival_count=3)
        for partner in ('rival', 'rival_2'):
            state = game.diplomacy_between('player', partner)
            state.coalition_target, state.coalition_turn = 'rival_3', 1
        diplomacy.start_war(game, 'rival_3', 'rival')
        for defender in ('player', 'rival', 'rival_2'):
            self.assertTrue(game.diplomacy_between(defender, 'rival_3').at_war)


class FearAndPriorityTests(unittest.TestCase):
    def test_unknown_and_hidden_fleets_do_not_create_fear(self):
        game = campaign(fog_of_war=True)
        navy(game, 'player', 0, 50)
        self.assertEqual(preferences.fear(game, 'rival', 'player').score, 0)
        first_contact.establish(game, 'player', 'rival')
        before = preferences.fear(game, 'rival', 'player')
        navy(game, 'player', 0, 50)
        self.assertEqual(preferences.fear(game, 'rival', 'player'), before)
        self.assertEqual(preferences.threat(game, 'rival', 'player').score, 0)

    def test_fear_is_directional_and_separate_from_relations(self):
        game = campaign()
        navy(game, 'player', game.opponent.home_system)
        before = game.diplomacy.relations
        fear = preferences.fear(game, 'rival', 'player').score
        self.assertGreaterEqual(fear, tribute.FEAR_THRESHOLD)
        self.assertEqual(preferences.fear(game, 'player', 'rival').score, 0)
        game.diplomacy.relations = -100
        self.assertEqual(preferences.fear(game, 'rival', 'player').score, fear)
        game.diplomacy.relations = before
        for ship in game.ships:
            ship.system_id = 0
        self.assertLess(preferences.fear(game, 'rival', 'player').score, fear)

    def test_allies_reduce_fear_and_recent_defeats_increase_it(self):
        game = frontier()
        navy(game, 'player', game.opponent.home_system, 8)
        before = preferences.fear(game, 'rival', 'player').score
        diplomacy.record_defeat(game, 'rival', 'player')
        self.assertGreater(preferences.fear(game, 'rival', 'player').score, before)
        partner = game.diplomacy_between('rival', 'rival_2')
        partner.coalition_target, partner.coalition_turn = 'player', game.turn
        self.assertLess(preferences.fear(game, 'rival', 'player').score,
                        before+15)

    def test_ecology_energy_and_industry_priorities_follow_known_worlds(self):
        game = frontier()
        star, world = game.headquarters('rival_2')
        star.kind, world.biome, world.richness = 'Blue star', 'Gaia', 'Ultra-rich'
        for race in ('xenonflora', 'aetheri', 'nexus'):
            game.race_id = race
            report = preferences.threat(game, 'player', 'rival_2')
            self.assertGreater(dict(report.reasons)['Competing interests: '+preferences.PROFILES[race].interest], 0)

    def test_lithar_betrayal_memory_survives_time_and_save(self):
        game = campaign(rival_race_id='lithar')
        game.diplomacy.relations = 50
        game.diplomacy.non_aggression_active = True
        game.diplomacy_action('end_non_aggression')
        later(game, 200)
        diplomacy.advance_diplomacy(game)
        restored = GameState.from_dict(game.to_dict())
        self.assertEqual(restored.diplomacy.broken_promises, {'player': 1})
        self.assertGreater(diplomacy.acceptance_threshold(restored, 'friendship', 'rival'), 30)
        self.assertEqual(diplomacy.acceptance_threshold(restored, 'trade', 'rival'), 10)

    def test_priorities_choose_different_ai_treaties(self):
        for race, pact in (('kharuun', 'trade'), ('aelari', 'research'), ('serevan', 'friendship')):
            game = campaign(rival_count=2, rival_race_id=race)
            later(game, 5)
            state = game.diplomacy_between('rival', 'rival_2')
            state.relations = 100
            diplomacy.ai_treaty_orders(game, 'rival')
            self.assertTrue(getattr(state, pact+'_active'), race)
            self.assertFalse(game.diplomacy.friendship_active)  # Human chooses their own treaties.


class TributeTests(unittest.TestCase):
    def test_payment_is_conserved_and_cooldown_is_global_for_100_turns(self):
        game = campaign(rival_count=2)
        navy(game, 'player', game.opponent.home_system)
        amount = tribute.quote(game, 'player', 'rival')
        own, other = game.credits, game.opponent.credits
        self.assertIn('paid', tribute.demand(game, 'player', 'rival'))
        self.assertEqual((game.credits, game.opponent.credits), (own+amount, other-amount))
        self.assertEqual(game.tribute_ready['player'], 101)
        before = game.to_dict()
        with self.assertRaisesRegex(RuleError, '101'):
            tribute.demand(game, 'player', 'rival_2')
        self.assertEqual(game.to_dict(), before)
        later(game, 99)
        self.assertIsNotNone(tribute.demand_error(game, 'player', 'rival_2'))
        later(game, 1)
        self.assertIsNone(tribute.demand_error(game, 'player', 'rival_2'))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_refusal_consumes_cooldown_changes_relations_but_does_not_start_war(self):
        game = campaign()
        game.diplomacy.relations = -25
        before = game.credits, game.opponent.credits
        self.assertIn('refused', tribute.demand(game, 'player', 'rival'))
        self.assertEqual((game.credits, game.opponent.credits), before)
        self.assertFalse(game.diplomacy.at_war)
        self.assertEqual(game.tribute_ready['player'], 101)
        self.assertGreater(preferences.threat(game, 'rival', 'player').score, 0)

    def test_varkesh_population_uses_existing_slave_capacity_and_preserves_colony(self):
        game = campaign(race_id='varkesh')
        navy(game, 'player', game.opponent.home_system)
        _, donor = game.headquarters('rival')
        home = game.planet_at(0, 2)
        before = donor.population
        self.assertIn('paid', tribute.demand(game, 'player', 'rival', 'population'))
        self.assertEqual((home.slaves, donor.population), (1, before-1))
        self.assertTrue(donor.colonized)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        later(game, 100)
        donor.population = 1
        self.assertIsNotNone(tribute.demand_error(game, 'player', 'rival', 'population'))
        donor.population = 2
        home.slaves = 100
        self.assertIsNotNone(tribute.demand_error(game, 'player', 'rival', 'population'))

    def test_invalid_demands_are_atomic_and_treasury_caps_apply(self):
        game = campaign()
        before = game.to_dict()
        for target, kind in (('player', 'money'), ('rival', 'population'), ('rival', 'technology')):
            with self.assertRaises(RuleError):
                tribute.demand(game, 'player', target, kind)
            self.assertEqual(game.to_dict(), before)
        game.opponent.credits = 2
        self.assertEqual(tribute.quote(game, 'player', 'rival'), 2)
        game.credits = 1_000_000_000
        self.assertEqual(tribute.quote(game, 'player', 'rival'), 0)

    def test_incoming_demands_wait_for_human_and_survive_save(self):
        game = campaign()
        navy(game, 'rival', 0)
        before = game.credits
        tribute.demand(game, 'rival', 'player')
        self.assertEqual(game.credits, before)
        game = GameState.from_dict(game.to_dict())
        with self.assertRaisesRegex(RuleError, 'pending tribute'):
            game.advance_turn()
        tribute.respond(game, 'rival', False)
        self.assertEqual(game.credits, before)
        self.assertFalse(game.tribute_demands)
        later(game, 100)
        tribute.demand(game, 'rival', 'player')
        amount = game.tribute_demands[0].amount
        tribute.respond(game, 'rival', True)
        self.assertEqual(game.credits, before-amount)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_ai_demands_from_frightened_player_without_spending_for_them(self):
        game = campaign()
        later(game, 11)
        game.diplomacy.relations = 0
        navy(game, 'rival', 0)
        credits = game.credits
        tribute.ai_orders(game, 'rival')
        self.assertEqual(game.credits, credits)
        self.assertEqual(len(game.tribute_demands), 1)
        tribute.ai_orders(game, 'rival')
        self.assertEqual(len(game.tribute_demands), 1)


class SaveTests(unittest.TestCase):
    def test_previous_save_and_balance_profile_upgrade_without_changing_other_settings(self):
        game = frontier()
        game.diplomacy.relations = 23
        with tempfile.TemporaryDirectory() as folder:
            store = Storage(folder)
            path = store.save(game)
            data = json.loads(path.read_text())
            data['version'] = 43
            for key in ('tribute_ready', 'tribute_demands', 'diplomatic_news', 'diplomatic_news_read'):
                data['game'].pop(key)
            path.write_text(json.dumps(data))
            restored, _ = store.load(path)
            self.assertEqual(restored.diplomacy.relations, 23)
            self.assertFalse(restored.tribute_ready or restored.diplomacy.coalition_target)
        old = balance.default_profile()
        old['version'] = 9
        old['data'].pop('diplomatic_preferences')
        for key in ('tribute', 'coalitions'):
            old['data']['rules'].pop(key)
        old['data']['rules']['diplomacy']['RESEARCH_INCOME'] = 12
        upgraded = balance.upgrade_profile(old)
        self.assertEqual(balance.validate(upgraded), [])
        self.assertEqual(upgraded['data']['rules']['diplomacy']['RESEARCH_INCOME'], 12)

    def test_corrupt_current_save_data_is_rejected(self):
        game = frontier()
        coalitions.form(game, 'player', 'rival', 'rival_2')
        for field, value in (('coalition_target', 'rival'), ('coalition_turn', 0), ('cooperation_turns', True),
                             ('broken_promises', {'rival_2': 1}), ('last_defeat', {'player': 20})):
            data = game.to_dict()
            data['diplomacy'][field] = value
            with self.assertRaises(SaveError, msg=field):
                GameState.from_dict(data)
        for field, value in (('tribute_ready', {'player': 102}), ('tribute_demands', [{}]),
                             ('diplomatic_news_read', 999)):
            data = game.to_dict()
            data[field] = value
            with self.assertRaises(SaveError, msg=field):
                GameState.from_dict(data)


class InteractionTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        import pygame as pg
        self.tmp = tempfile.TemporaryDirectory()
        self.app = App(Path(self.tmp.name), capture=True)
        self.app.game = frontier()
        self.app.go('galaxy')
        self.app.open_diplomacy()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(pg.quit)
        self.addCleanup(self.app.audio.close)

    def click(self, key):
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        self.assertTrue(button.enabled, key)
        self.app.activate(button)

    def test_coalition_button_requires_confirmation_before_war_entry(self):
        app, game = self.app, self.app.game
        diplomacy.start_war(game, 'rival_2', 'rival')
        self.click('diplomacy_affairs')
        self.click('dialog_form_coalition')
        self.assertIn('CONFIRM WAR ENTRY', app.dialog['body'])
        self.assertFalse(game.diplomacy.coalition_target)
        self.assertFalse(game.diplomacy_between('player', 'rival_2').at_war)
        self.click('dialog_ok')
        self.assertTrue(game.diplomacy_between('player', 'rival_2').at_war)
        self.assertEqual(game.diplomacy.coalition_target, 'rival_2')
        app.render()

    def test_cancelled_tribute_does_not_spend_cooldown_and_confirmed_one_does(self):
        app, game = self.app, self.app.game
        app.show_diplomatic_affairs('tribute')
        self.click('dialog_demand_money')
        self.click('dialog_cancel')
        self.assertFalse(game.tribute_ready)
        app.show_diplomatic_affairs('tribute')
        self.click('dialog_demand_money')
        self.click('dialog_ok')
        self.assertEqual(game.tribute_ready['player'], 101)
        app.render()

    def test_end_turn_opens_pending_demand_and_close_does_not_accept(self):
        app, game = self.app, self.app.game
        tribute.demand(game, 'rival', 'player')
        before = game.turn, game.credits
        app.advance_turn()
        app.render()
        self.assertEqual(app.dialog['affairs_tab'], 'tribute')
        self.click('dialog_close')
        self.assertEqual((game.turn, game.credits), before)
        self.assertTrue(game.tribute_demands)
        app.advance_turn()
        self.click('dialog_tribute_refuse')
        self.click('dialog_ok')
        self.assertFalse(game.tribute_demands)
        self.assertEqual((game.turn, game.credits), before)


if __name__ == '__main__':
    unittest.main()
