"""Treaty protection, economic trade, shared sensor privacy and save migration."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')

from orion import ai, balance, combat, diplomacy, first_contact, navigation, outposts, sensors
from orion.model import GameState, RuleError, SaveError, Ship
from orion.races import RACES
from orion.storage import Storage
from scenarios import empty_fleet_game, place_near
from test_research_expansion import discover


def campaign(**kwargs):
    return empty_fleet_game(seed=12, fog_of_war=kwargs.pop('fog_of_war', False), **kwargs)


def friend(game, first, second):
    first_contact.establish(game, first, second)
    state = game.diplomacy_between(first, second)
    state.relations = 30
    state.friendship_active = state.non_aggression_active = state.trade_active = True


class TreatyTests(unittest.TestCase):
    def test_trade_accepts_at_ten_for_every_race_and_grows_each_turn(self):
        for race in RACES:
            with self.subTest(race=race):
                game = campaign(rival_race_id=race)
                game.diplomacy.relations = 9
                self.assertIn('declined', game.diplomacy_action('trade'))
                game.turn += diplomacy.OFFER_COOLDOWN
                game.year += diplomacy.OFFER_COOLDOWN
                game.diplomacy.relations = 10
                self.assertIn('accepted', game.diplomacy_action('trade'))
                for _ in range(5):
                    diplomacy.advance_diplomacy(game)
                    game.turn += 1
                    game.year += 1
                self.assertGreaterEqual(game.diplomacy.relations, 15)
                game.diplomacy.relations = 100
                diplomacy.advance_diplomacy(game)
                self.assertEqual(game.diplomacy.relations, 100)

    def test_retired_actions_are_atomic_and_cannot_spend_credits(self):
        game = campaign()
        for action in ('envoy', 'gift'):
            before = game.to_dict()
            with self.assertRaisesRegex(RuleError, 'Unknown diplomatic action'):
                game.diplomacy_action(action)
            self.assertEqual(game.to_dict(), before)

    def test_non_aggression_builds_a_path_to_trade(self):
        game = campaign(rival_race_id='concord')
        game.diplomacy.relations = 0
        self.assertIn('accepted', game.diplomacy_action('non_aggression'))
        for _ in range(10):
            diplomacy.advance_diplomacy(game)
            game.turn += 1
            game.year += 1
        self.assertEqual(game.diplomacy.relations, 10)
        self.assertIn('accepted', game.diplomacy_action('trade'))

    def test_friendship_bundles_treaties_once_and_ends_as_one_bundle(self):
        game = campaign(rival_race_id='kharuun')
        game.diplomacy.relations = 30
        game.diplomacy.trade_active = True
        self.assertIn('accepted', game.diplomacy_action('friendship'))
        self.assertTrue(game.diplomacy.non_aggression_active)
        income = diplomacy.trade_income(game, 'player', 'rival')
        self.assertEqual(game.diplomatic_yields()[0], income)
        for action in ('end_trade', 'end_non_aggression'):
            before = game.to_dict()
            with self.assertRaisesRegex(RuleError, 'friendship'):
                game.diplomacy_action(action)
            self.assertEqual(game.to_dict(), before)
        diplomacy.advance_diplomacy(game)
        self.assertEqual(game.diplomacy.relations, 32)
        game.diplomacy_action('end_friendship')
        self.assertEqual(game.diplomacy.relations, 17)
        self.assertFalse(game.diplomacy.friendship_active or game.diplomacy.non_aggression_active or game.diplomacy.trade_active)
        self.assertEqual(game.diplomatic_yields(), (0, 0))

    def test_all_attack_paths_and_ai_respect_non_aggression(self):
        game = campaign(race_id='varkesh', rival_race_id='concord')
        sid, planet = game.headquarters('rival')
        friend(game, 'player', 'rival')
        game.diplomacy.relations = -60  # Protection remains even after a grievance.
        game.ships = [Ship(1, 'frigate', sid.id), Ship(2, 'troop_transport', sid.id),
                      Ship(3, 'frigate', sid.id, owner='rival')]
        game.next_ship_id = 4
        for owner, other in (('player', 'rival'), ('rival', 'player')):
            self.assertFalse(navigation.hostile(game, owner, other))
            self.assertNotIn(other, ai.enemies(game, owner))
        for operation in (lambda: game.start_combat(sid.id),
                          lambda: game.invade(sid.id, planet.id),
                          lambda: game.bombard(sid.id, planet.id)):
            before = game.to_dict()
            with self.assertRaisesRegex(RuleError, 'non-aggression'):
                operation()
            self.assertEqual(game.to_dict(), before)
        outpost = next(p for s in game.systems for p in s.worlds if not p.colonized)
        system = next(s for s in game.systems if outpost in s.worlds)
        outpost.outpost_owner, outpost.outpost_hull = 'rival', 30
        with self.assertRaisesRegex(RuleError, 'non-aggression'):
            outposts.attack(game, system.id, outpost.id)
        game.turn, game.year = 18, 2317
        self.assertEqual(ai.diplomatic_orders(game, 'rival'), [])
        self.assertEqual(list(combat.hostile_pairs(game)), [])
        game.diplomacy_action('declare_war')
        self.assertEqual(game.diplomacy.relations, -100)
        self.assertEqual(game.diplomatic_yields(), (0, 0))
        self.assertTrue(navigation.hostile(game, 'player', 'rival'))
        self.assertIsNone(game.engagement_error(sid.id))
        with self.assertRaisesRegex(RuleError, 'already at war'):
            game.diplomacy_action('declare_war')

    def test_unknown_and_eliminated_empires_cannot_form_treaties(self):
        game = campaign(fog_of_war=True)
        for action in ('trade', 'non_aggression', 'friendship', 'declare_war'):
            self.assertIn('first contact', game.diplomacy_error(action))
        friend(game, 'player', 'rival')
        for s in game.colony_systems('rival'):
            for p in s.worlds:
                if p.owner == 'rival':
                    p.owner, p.colonized = None, False
        self.assertEqual(game.diplomatic_yields(), (0, 0))
        self.assertIn('eliminated', game.diplomacy_error('friendship'))
        self.assertNotIn('rival', sensors.sources(game))
        game.eliminate_defeated()
        self.assertFalse(game.diplomacy.friendship_active or game.diplomacy.non_aggression_active)

    def test_current_save_round_trip_and_v42_migration(self):
        game = campaign()
        friend(game, 'player', 'rival')
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            self.assertEqual(storage.load(storage.save(game))[0], game)
            payload = json.loads(storage.save(game).read_text())
            payload['version'] = 42
            old = payload['game']['diplomacy']
            old.pop('friendship_active')
            old.pop('non_aggression_active')
            old['relations'] = 17
            path = Path(folder)/'legacy.json'
            path.write_text(json.dumps(payload))
            restored, _ = storage.load(path)
            self.assertEqual(restored.diplomacy.relations, 17)
            self.assertTrue(restored.diplomacy.trade_active)
            self.assertFalse(restored.diplomacy.friendship_active or restored.diplomacy.non_aggression_active)

    def test_invalid_or_partial_friendship_saves_are_rejected(self):
        game = campaign()
        for field, value in (('friendship_active', 1), ('non_aggression_active', 'yes'), ('friendship_active', True)):
            data = game.to_dict()
            data['diplomacy'][field] = value
            with self.assertRaises(SaveError):
                GameState.from_dict(data)
        for field in ('friendship_active', 'non_aggression_active'):
            data = game.to_dict()
            data['diplomacy'].pop(field)
            with self.assertRaises(SaveError):
                GameState.from_dict(data)


class EconomicTradeTests(unittest.TestCase):
    def test_joint_economy_and_distance_have_measurable_effects(self):
        game = campaign(race_id='terran', rival_race_id='terran')
        a, _ = game.headquarters('player')
        b, _ = game.headquarters('rival')
        a.x, a.y = .1, .5
        b.x, b.y = .1+50/140, .5
        strengths = {'player': 400, 'rival': 100}
        # 25% of sqrt(400*100) = 50; fifty light-years halves that.
        self.assertEqual(diplomacy.trade_income(game, 'player', 'rival', strengths=strengths), 25)
        self.assertEqual(diplomacy.trade_income(game, 'rival', 'player', strengths=strengths), 25)
        b.x = a.x+100/140
        self.assertEqual(diplomacy.trade_income(game, 'player', 'rival', strengths=strengths), 17)
        strengths['rival'] = 400
        self.assertEqual(diplomacy.trade_income(game, 'player', 'rival', strengths=strengths), 33)
        strengths['player'] = 0
        self.assertEqual(diplomacy.trade_income(game, 'player', 'rival', strengths=strengths), 0)

    def test_strength_ignores_treaty_income_treasury_and_upkeep(self):
        game = campaign(rival_race_id='kharuun')
        before = diplomacy.economic_strength(game, 'player')
        game.diplomacy.trade_active = True
        game.credits = 100000
        self.assertEqual(diplomacy.economic_strength(game, 'player'), before)
        home = game.planet_at(0, 2)
        home.buildings.append('factory')
        self.assertEqual(diplomacy.economic_strength(game, 'player'), before)
        home.buildings.append('trade_center')
        self.assertGreater(diplomacy.economic_strength(game, 'player'), before)
        home.trade_goods = True
        self.assertGreater(diplomacy.economic_strength(game, 'player'), before)

    def test_profile_upgrade_preserves_other_settings_and_adds_trade_controls(self):
        old = balance.default_profile()
        old['version'] = 8
        rules = old['data']['rules']['diplomacy']
        for key in ('TRADE_THRESHOLD', 'NON_AGGRESSION_THRESHOLD', 'FRIENDSHIP_THRESHOLD', 'TRADE_SHARE_PERCENT', 'TRADE_DISTANCE_LY'):
            rules.pop(key)
        rules.update(ENVOY_COST=99, TRADE_INCOME=12, RESEARCH_INCOME=9)
        old['data']['races']['terran']['envoy_bonus'] = 12
        old['data']['races']['terran']['trade_threshold'] = 80
        old['data']['personalities']['terran'].update(envoy=5, gift=5)
        upgraded = balance.upgrade_profile(old)
        self.assertEqual(balance.validate(upgraded), [])
        self.assertEqual(upgraded['data']['rules']['diplomacy']['RESEARCH_INCOME'], 9)
        self.assertEqual(upgraded['data']['rules']['diplomacy']['TRADE_THRESHOLD'], 10)
        self.assertNotIn('envoy_bonus', upgraded['data']['races']['terran'])
        self.assertEqual(old['version'], 8)


class FriendshipSensorsTests(unittest.TestCase):
    def setUp(self):
        self.game = game = campaign(rival_count=3, fog_of_war=True)
        self.friend, self.other = 'rival', 'rival_2'
        home = game.opponent.home_system
        self.remote = next(s for s in game.systems if s.id not in {0, *(r.home_system for r in game.opponents.values())})
        place_near(game, self.remote.id, anchor=home, distance=4)
        self.ship = Ship(1, 'frigate', self.remote.id, owner=self.other)
        game.ships.append(self.ship)
        game.next_ship_id = 2
        discover(game, 'deep_space_radar', self.friend)
        self.assertFalse(sensors.contacts(game))

    def test_live_partner_output_preserves_detail_and_does_not_grant_surveys(self):
        game = self.game
        friend(game, 'player', self.friend)
        sensors.refresh(game)
        first_contact.refresh(game)
        contact, = sensors.contacts(game)
        self.assertEqual((contact.owner, contact.level, contact.count, contact.classes), (self.other, 1, None, []))
        self.assertTrue(first_contact.known(game, 'player', self.other))
        self.assertFalse(game.system_explored(self.remote.id))
        self.assertNotIn(self.ship, game.visible_ships())
        discover(game, 'subspace_scanners', 'player')
        self.assertEqual(sensors.contacts(game)[0].level, 1)  # Cannot upgrade a friend's weaker data.
        discover(game, 'long_range_sensors', self.friend)
        self.assertEqual(sensors.contacts(game)[0].count, 1)
        discover(game, 'subspace_scanners', self.friend)
        self.assertEqual(sensors.contacts(game)[0].classes, ['Frigate × 1'])
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_sharing_is_bilateral_but_never_transitive(self):
        game = self.game
        friend(game, 'player', self.friend)
        friend(game, self.friend, 'rival_3')
        # A fleet observed only by the third friend must not be relayed onward.
        self.ship.system_id = game._empire('rival_3').home_system
        self.assertTrue(sensors.contacts(game, self.friend))
        self.assertFalse(sensors.contacts(game))
        self.ship.owner, self.ship.system_id = 'rival_3', 0
        self.assertTrue(any(c.owner == 'rival_3' for c in sensors.contacts(game, self.friend)))
        self.assertIn(game.systems[game.opponent.home_system], [s for s, _ in sensors.centers(game)])

    def test_end_friendship_and_war_stop_live_feed_but_keep_dated_sightings(self):
        for action in ('end_friendship', 'declare_war'):
            game = copy.deepcopy(self.game)
            friend(game, 'player', self.friend)
            sensors.refresh(game)
            first_contact.refresh(game)
            previous = sensors.contacts(game)[0]
            game.diplomacy_action(action, self.friend)
            self.ship = game.ships[0]
            self.ship.system_id = game._empire(self.other).home_system
            contact, = sensors.contacts(game)
            self.assertFalse(contact.active)
            self.assertEqual((contact.x, contact.y, contact.seen_turn), (previous.x, previous.y, previous.seen_turn))
            self.assertEqual(GameState.from_dict(game.to_dict()), game)


if __name__ == '__main__':
    unittest.main()
