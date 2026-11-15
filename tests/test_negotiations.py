"""Player agency, ceasefire enforcement, promise consequences and save migration."""
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')

from orion import ai, coalitions, diplomacy, exploration, negotiations as rules
from orion.model import GameState, RuleError, SaveError, Ship
from orion.storage import Storage
from scenarios import empty_fleet_game


def campaign(**kwargs):
    game = empty_fleet_game(seed=12, fog_of_war=False, rival_race_id=kwargs.pop('rival_race_id', 'terran'), **kwargs)
    game.diplomacy.relations = 40
    for i, owner in enumerate(game.owners):
        home, _ = game.headquarters(owner)
        home.x, home.y = .30+i*.04, .50
    homes = {s.id for o in game.owners for s in game.colony_systems(o)}
    system = next(s for s in game.systems if s.id not in homes and s.worlds)
    system.x, system.y = .32, .51
    system.worlds[0].biome = 'Terran'
    exploration.refresh(game)
    return game, system.id


def later(game, count):
    game.turn += count
    game.year += count


def colony_ship(game, sid, owner='player'):
    ship = Ship(game.next_ship_id, 'colony_ship', sid, owner=owner)
    game.next_ship_id += 1
    game.ships.append(ship)
    return ship


class ProposalTests(unittest.TestCase):
    def test_ai_offer_requires_human_acceptance_and_survives_save(self):
        game, _ = campaign()
        later(game, 3)
        rules.ai_orders(game, 'rival')
        self.assertEqual(len(rules.incoming(game)), 1)
        p = game.diplomacy.proposal
        self.assertFalse(getattr(game.diplomacy, p.kind+'_active'))
        with tempfile.TemporaryDirectory() as folder:
            store = Storage(folder)
            restored, meta = store.load(store.save(game))
            self.assertEqual(meta['version'], 65)
            self.assertEqual(restored, game)
            rules.respond(restored, 'rival', True)
            self.assertTrue(getattr(restored.diplomacy, p.kind+'_active'))
            self.assertIsNone(restored.diplomacy.proposal)
            self.assertEqual(GameState.from_dict(restored.to_dict()), restored)

    def test_refusal_expiry_cooldown_and_stale_response(self):
        game, _ = campaign()
        rules.offer(game, 'rival', 'player', 'trade')
        p = game.diplomacy.proposal
        before = game.diplomacy.relations
        rules.respond(game, 'rival', False)
        self.assertEqual(game.diplomacy.relations, before)
        with self.assertRaises(RuleError):
            rules.offer(game, 'rival', 'player', 'trade')
        later(game, rules.INITIATIVE_COOLDOWN)
        rules.offer(game, 'rival', 'player', 'trade')
        with self.assertRaises(RuleError):
            rules.respond(game, 'rival', True, created_turn=p.created_turn)
        later(game, rules.PROPOSAL_TURNS)
        rules.advance(game)
        self.assertIsNone(game.diplomacy.proposal)
        self.assertFalse(game.diplomacy.trade_active)

    def test_pending_offer_does_not_block_end_turn(self):
        game, _ = campaign()
        rules.offer(game, 'rival', 'player', 'trade')
        game.advance_turn()
        self.assertEqual(game.turn, 2)
        self.assertIsNotNone(game.diplomacy.proposal)

    def test_one_new_proposal_per_turn_and_no_skirr_treaties(self):
        game, _ = campaign(rival_count=3)
        later(game, 3)
        for owner in game.opponents:
            game.diplomacy_between('player', owner).relations = 90
            rules.ai_orders(game, owner)
        self.assertEqual(len(rules.incoming(game)), 1)
        skirr, _ = campaign(rival_race_id='skirr')
        with self.assertRaisesRegex(RuleError, 'Skirr'):
            rules.offer(skirr, 'player', 'rival', 'peace')

    def test_reading_reasons_has_no_side_effects_and_matches_decisions(self):
        for relations, accepted in ((9, False), (10, True)):
            game, _ = campaign()
            game.diplomacy.relations = relations
            before = game.to_dict()
            report, yes = rules.treaty_assessment(game, 'trade', 'rival')
            self.assertEqual(yes, accepted)
            self.assertEqual(report.score, relations-10)
            self.assertEqual(game.to_dict(), before)
            game.diplomacy_action('trade')
            self.assertEqual(game.diplomacy.trade_active, accepted)

    def test_incoming_coalition_never_enlists_player_without_acceptance(self):
        game, _ = campaign(rival_count=2)
        game.diplomacy.relations = 60
        # Place the shared rival close enough to threaten both partners.
        third, _ = game.headquarters('rival_2')
        third.x = .32
        exploration.refresh(game)
        self.assertTrue(coalitions.willingness(game, 'rival', 'player', 'rival_2')[1])
        rules.offer(game, 'rival', 'player', 'coalition', target='rival_2')
        self.assertIsNone(game.diplomacy.coalition_target)
        rules.respond(game, 'rival', True)
        self.assertEqual(game.diplomacy.coalition_target, 'rival_2')


class PromiseTests(unittest.TestCase):
    def test_accepting_and_breaking_promise_uses_real_colonization(self):
        game, sid = campaign(rival_race_id='lithar')
        self.assertIn(sid, rules.territorial_candidates(game, 'rival', 'player'))
        rules.offer(game, 'rival', 'player', 'territory', system_id=sid)
        rules.respond(game, 'rival', True)
        ship = colony_ship(game, sid)
        self.assertIn('BREAKS YOUR PROMISE', rules.settlement_warning(game, 'player', sid))
        before = game.diplomacy.relations
        game.colonize(ship.id, sid, 0)
        self.assertEqual(game.diplomacy.relations, before-15)
        self.assertEqual(game.diplomacy.broken_promises['player'], 1)
        self.assertFalse(game.diplomacy.at_war)
        self.assertFalse(rules.promises_at(game, 'player', sid))
        later(game, 100)
        diplomacy.advance_diplomacy(game)
        self.assertEqual(game.diplomacy.broken_promises['player'], 1)

    def test_ai_honours_restriction_then_it_expires_and_rewards_once(self):
        game, sid = campaign()
        game.diplomacy.relations = 90
        rules.offer(game, 'player', 'rival', 'territory', system_id=sid)
        self.assertTrue(rules.promises_at(game, 'rival', sid))
        self.assertEqual(ai.available_worlds(game, game.systems[sid], 'rival'), [])
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        before = game.diplomacy.relations
        later(game, rules.PROMISE_TURNS)
        rules.advance(game)
        self.assertTrue(ai.available_worlds(game, game.systems[sid], 'rival'))
        self.assertEqual(game.diplomacy.relations, before+5)
        self.assertEqual(game.diplomacy.honoured_promises['rival'], 1)
        rules.advance(game)
        self.assertEqual(game.diplomacy.relations, before+5)

    def test_refusal_is_less_costly_than_breach_and_never_declares_war(self):
        game, sid = campaign()
        game.diplomacy.relations = -29
        rules.offer(game, 'rival', 'player', 'territory', system_id=sid)
        rules.respond(game, 'rival', False)
        self.assertEqual(game.diplomacy.relations, -30)
        self.assertFalse(game.diplomacy.at_war)
        self.assertFalse(game.diplomacy.broken_promises)

    def test_ai_territorial_warning_requires_visible_expedition(self):
        game, sid = campaign()
        later(game, 3)
        colony_ship(game, sid)
        with patch.object(type(game), 'visible_ships', return_value=[]):
            rules.ai_orders(game, 'rival')
        self.assertNotEqual(game.diplomacy.proposal.kind, 'territory')
        game.diplomacy.proposal = None
        game.diplomacy.initiative_ready_turn = 1
        rules.ai_orders(game, 'rival')
        self.assertEqual(game.diplomacy.proposal.kind, 'territory')

    def test_promise_marker_and_wartime_completion_do_not_make_peace(self):
        from orion.galaxy_labels import system_label
        game, sid = campaign()
        rules.offer(game, 'rival', 'player', 'territory', system_id=sid)
        rules.respond(game, 'rival', True)
        self.assertIn('◇', system_label(game, game.systems[sid], 'clean'))
        diplomacy.start_war(game, 'rival', 'player')
        game.diplomacy.relations = -32
        later(game, 20)
        rules.advance(game)
        self.assertTrue(game.diplomacy.at_war)
        self.assertNotIn('◇', system_label(game, game.systems[sid], 'clean'))


class PeaceTests(unittest.TestCase):
    def wartime(self, **kwargs):
        game, sid = campaign(**kwargs)
        diplomacy.start_war(game, 'player', 'rival')
        later(game, 15)
        return game, sid

    def test_status_quo_peace_and_expiry_do_not_restart_war(self):
        game, _ = self.wartime()
        colonies = [(s.id, p.id, p.owner) for s, p in game.settlements()]
        self.assertTrue(rules.peace_assessment(game, 'rival', 'player')[1])
        rules.offer(game, 'player', 'rival', 'peace')
        self.assertFalse(game.diplomacy.at_war)
        self.assertEqual(colonies, [(s.id, p.id, p.owner) for s, p in game.settlements()])
        for a, b in (('player', 'rival'), ('rival', 'player')):
            self.assertIn('ceasefire', diplomacy.aggression_error(game, a, b))
            before = game.to_dict()
            with self.assertRaises(RuleError):
                diplomacy.start_war(game, a, b)
            self.assertEqual(game.to_dict(), before)
        self.assertNotIn('player', ai.enemies(game, 'rival'))
        later(game, rules.CEASEFIRE_TURNS)
        rules.advance(game)
        self.assertFalse(game.diplomacy.at_war)
        self.assertIsNone(diplomacy.aggression_error(game, 'player', 'rival'))

    def test_reparations_are_conserved_and_revalidated(self):
        game, _ = self.wartime()
        game.credits = 500
        total = game.credits+game.opponent.credits
        enemy_money = game.opponent.credits
        rules.offer(game, 'player', 'rival', 'peace', payment=100)
        self.assertEqual(game.credits, 400)
        self.assertEqual(game.opponent.credits, enemy_money+100)
        self.assertEqual(game.credits+game.opponent.credits, total)
        other, _ = self.wartime()
        before = other.to_dict()
        with self.assertRaises(RuleError):
            rules.offer(other, 'player', 'rival', 'peace', payment=other.credits+1)
        self.assertEqual(other.to_dict(), before)

    def test_recent_defeat_changes_willingness(self):
        game, _ = campaign()
        diplomacy.start_war(game, 'player', 'rival')
        later(game, 3)
        self.assertFalse(rules.peace_assessment(game, 'rival', 'player')[1])
        diplomacy.record_defeat(game, 'rival', 'player')
        self.assertTrue(rules.peace_assessment(game, 'rival', 'player')[1])

    def test_incoming_peace_is_not_automatic(self):
        game, _ = self.wartime()
        rules.ai_orders(game, 'rival')
        self.assertEqual(game.diplomacy.proposal.kind, 'peace')
        self.assertTrue(game.diplomacy.at_war)
        rules.respond(game, 'rival', True)
        self.assertFalse(game.diplomacy.at_war)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_peace_protects_against_varkesh_raid_targeting(self):
        game, _ = self.wartime(rival_race_id='varkesh')
        later(game, 20)
        rules.offer(game, 'player', 'rival', 'peace', payment=100)
        self.assertNotIn('player', ai.enemies(game, 'rival'))

    def test_ceasefire_blocks_combat_bombardment_invasion_and_coalition_entry(self):
        from orion import combat, defenses, victory
        game, _ = self.wartime(rival_count=2)
        rules.offer(game, 'player', 'rival', 'peace')
        system, planet = game.headquarters('rival')
        for owner in ('player', 'rival'):
            game.ships.append(Ship(game.next_ship_id, 'frigate', system.id, owner=owner))
            game.next_ship_id += 1
        self.assertIn('ceasefire', combat.engagement_error(game, system.id, target='rival'))
        self.assertIn('ceasefire', defenses.bombardment_error(game, system.id, planet.id))
        self.assertIn('ceasefire', victory.invasion_error(game, system.id, planet.id))
        self.assertIn('ceasefire', game.diplomacy_error('declare_war', 'rival'))
        self.assertIn('protection', coalitions.proposal_error(game, 'player', 'rival_2', 'rival'))

    def test_unaffordable_incoming_payment_and_active_combat_are_atomic(self):
        game, _ = self.wartime()
        game.opponent.credits = 100
        rules.offer(game, 'rival', 'player', 'peace', payment=100)
        game.opponent.credits = 0
        before = game.to_dict()
        with self.assertRaisesRegex(RuleError, 'afford'):
            rules.respond(game, 'rival', True)
        self.assertEqual(game.to_dict(), before)
        with patch.object(type(game), 'strategy_error', return_value='Finish the current battle first.'):
            with self.assertRaisesRegex(RuleError, 'battle'):
                rules.respond(game, 'rival', False)
        self.assertEqual(game.to_dict(), before)


class NegotiationSaveTests(unittest.TestCase):
    def test_legacy_war_keeps_hostility_without_inventing_a_start_date(self):
        game, _ = campaign()
        diplomacy.start_war(game, 'player', 'rival')
        data = game.to_dict()
        for field in rules.STATE_FIELDS:
            data['diplomacy'].pop(field)
        restored = GameState.from_dict(data, version=64)
        self.assertTrue(restored.diplomacy.at_war)
        self.assertEqual(restored.diplomacy.war_started_turn, 0)
        self.assertEqual(restored.ships, game.ships)

    def test_save_resume_stays_deterministic_across_offer_and_promise_deadlines(self):
        game, sid = campaign()
        rules.offer(game, 'rival', 'player', 'territory', system_id=sid)
        rules.respond(game, 'rival', True)
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            restored, _ = storage.load(storage.save(game))
            for _ in range(25):
                self.assertEqual(game.advance_turn(), restored.advance_turn())
                self.assertEqual(game, restored)
            self.assertFalse(game.diplomacy.territorial_promises)

    def test_v64_migration_and_corrupt_new_fields(self):
        game, sid = campaign()
        rules.offer(game, 'rival', 'player', 'territory', system_id=sid)
        original = game.to_dict()
        old = copy.deepcopy(original)
        for field in rules.STATE_FIELDS:
            old['diplomacy'].pop(field)
        migrated = GameState.from_dict(old, version=64)
        self.assertIsNone(migrated.diplomacy.proposal)
        self.assertFalse(migrated.diplomacy.territorial_promises)
        self.assertEqual(migrated.systems, game.systems)
        changes = [lambda d: d.update(ceasefire_until=True),
                   lambda d: d.update(initiative_ready_turn=9999),
                   lambda d: d['proposal'].update(sender='ghost'),
                   lambda d: d['proposal'].update(system_id=9999),
                   lambda d: d['proposal'].update(expires_turn=9999),
                   lambda d: d['proposal'].update(payment=-1),
                   lambda d: d.update(honoured_promises={'ghost': 1})]
        for change in changes:
            data = copy.deepcopy(original)
            change(data['diplomacy'])
            with self.assertRaises(SaveError):
                GameState.from_dict(data)


class NegotiationInterfaceTests(unittest.TestCase):
    def setUp(self):
        import pygame as pg
        from orion.app import App
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.folder.name), capture=True)
        self.addCleanup(self.app.audio.close)
        self.app.game, self.sid = campaign()
        self.app.go('galaxy')
        self.app.open_diplomacy()
        self.app.present()

    def click(self, key):
        import pygame as pg
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        self.assertTrue(button.enabled, key)
        point = self.app.window_pos(button.rect.center)
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, button=1, pos=point))
            self.app.render()

    def test_real_buttons_accept_and_autosave_an_incoming_offer(self):
        rules.offer(self.app.game, 'rival', 'player', 'trade')
        self.click('diplomacy_review_proposal')
        self.click('dialog_proposal_accept')
        self.click('dialog_ok')
        self.assertTrue(self.app.game.diplomacy.trade_active)
        restored, _ = self.app.storage.load(self.app.storage.saves_dir/'autosave.json')
        self.assertEqual(restored, self.app.game)

    def test_reasons_and_peace_flow(self):
        self.click('diplomacy_why_trade')
        self.assertEqual(self.app.dialog['affairs_tab'], 'reasons')
        self.click('dialog_close')
        diplomacy.start_war(self.app.game, 'player', 'rival')
        later(self.app.game, 15)
        self.click('diplomacy_negotiate')
        self.click('dialog_peace_0')
        self.click('dialog_ok')
        self.assertFalse(self.app.game.diplomacy.at_war)
        self.assertGreater(self.app.game.diplomacy.ceasefire_until, self.app.game.turn)


if __name__ == '__main__':
    unittest.main()
