"""Finite forgotten networks, racial wins, migrations and contact-only progress."""

import copy
from collections import Counter
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_motherships import campaign, advance
from test_hyperlanes import scientists, recovered
import test_hyperlanes
from orion import first_contact, hyperlanes as lanes, motherships, victory
from orion.model import GameState, RuleError, SaveError


def network(game, *pairs):
    game.hidden_hyperlanes = [lanes.HiddenHyperlane(*sorted(pair)) for pair in pairs]


class HiddenNetworkTests(unittest.TestCase):
    def test_seeded_once_unique_ordinary_endpoints_and_save_stable(self):
        game = campaign(with_black_holes=True)
        pairs = [lane.pair for lane in game.hidden_hyperlanes]
        self.assertTrue(pairs)
        self.assertEqual(len(pairs), len(set(pairs)))
        self.assertTrue(all(a < b for a, b in pairs))
        from orion.black_holes import KIND
        self.assertTrue(all(game.systems[sid].kind != KIND for pair in pairs for sid in pair))
        self.assertEqual(game.hidden_hyperlanes, campaign(with_black_holes=True).hidden_hyperlanes)
        self.assertNotEqual(game.hidden_hyperlanes, campaign(seed=13, with_black_holes=True).hidden_hyperlanes)
        advance(game)
        self.assertEqual(pairs, [lane.pair for lane in game.hidden_hyperlanes])
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_incident_route_probabilities_decay_geometrically(self):
        stars = [SimpleNamespace(id=i, kind='yellow') for i in range(48)]
        tails = Counter()
        for seed in range(600):
            routes = lanes.generate_network(SimpleNamespace(seed=seed, systems=stars))
            degree = Counter(sid for route in routes for sid in route.pair)
            for n in (1, 2, 3, 4):
                tails[n] += sum(degree[i] >= n for i in range(48))
        for n in tails:
            self.assertAlmostEqual(tails[n]/(600*48), .5**n, delta=.02)

    def test_empty_system_costs_nothing_and_multiple_routes_are_finite(self):
        game = campaign(victory_conditions=())
        network(game, (0, 1), (0, 2))
        home = motherships.homes(game)[0]
        home.system_id = 3
        game.research = 500
        before = game.to_dict()
        with self.assertRaisesRegex(RuleError, 'No undiscovered'):
            lanes.start(game, 3)
        self.assertEqual(game.to_dict(), before)
        home.system_id = 0
        first = lanes.start(game, 0)
        self.assertNotIn(0, lanes.candidates(game, first.destination, 'player'))
        with self.assertRaisesRegex(RuleError, 'one forgotten'):
            lanes.start(game, 0)
        lanes.invest(game, 0)
        second = recovered(game)
        self.assertNotEqual(first.destination, second.destination)
        self.assertEqual(victory.race_goal(game).current, 2)
        self.assertEqual(lanes.project_at(game, 0), second)
        self.assertEqual(lanes.connections(game, 0), [1, 2])
        with self.assertRaisesRegex(RuleError, 'No undiscovered'):
            lanes.start(game, 0)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_each_wanderer_must_discover_the_shared_network_independently(self):
        game = campaign(with_ai=True, rival_race_id='wanderers', victory_conditions=())
        rival = motherships.homes(game, 'rival')[0]
        network(game, (0, rival.system_id))
        project = recovered(game)
        self.assertEqual((victory.race_goal(game).current, victory.race_goal(game, 'rival').current), (1, 0))
        self.assertFalse(lanes.connects(game, rival.system_id, 0, 'rival'))
        other = recovered(game, rival.system_id, 'rival')
        self.assertEqual(other.destination, 0)
        self.assertEqual(lanes.visible_routes(game), [project])
        self.assertEqual(GameState.from_dict(game.to_dict()), game)


class RaceVictoryTests(unittest.TestCase):
    def test_last_banked_discovery_wins_solo_and_disabled_goal_keeps_playing(self):
        for enabled in (('race',), ()):
            with self.subTest(enabled=enabled):
                game = campaign(victory_conditions=enabled)
                network(game, (0, 1), (0, 2))
                recovered(game)
                self.assertIsNone(game.result)
                recovered(game)
                self.assertTrue(victory.race_goal(game).complete)
                if enabled:
                    self.assertEqual(game.result, victory.CampaignResult('player', 'race', game.turn))
                else:
                    self.assertIsNone(game.result)
                    advance(game)
                self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_rival_can_win_and_simultaneous_final_discoveries_draw(self):
        for simultaneous in (False, True):
            with self.subTest(simultaneous=simultaneous):
                game = campaign(with_ai=True, rival_race_id='wanderers', victory_conditions=('race',))
                rival = motherships.homes(game, 'rival')[0]
                network(game, (0, rival.system_id))
                owners = game.owners if simultaneous else ('rival',)
                for owner in owners:
                    home = scientists(game, motherships.homes(game, owner)[0])
                    project = lanes.start(game, home.system_id, owner)
                    project.progress = project.cost-1
                advance(game)
                self.assertEqual(game.result, victory.CampaignResult(None if simultaneous else 'rival', 'race', game.turn))
                self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_eliminated_wanderer_cannot_win_and_forged_outcome_is_rejected(self):
        game = campaign(with_ai=True, race_id='terran', rival_race_id='wanderers', victory_conditions=('race',))
        rival = motherships.homes(game, 'rival')[0]
        network(game, (0, rival.system_id))
        game.hyperlane_projects.append(lanes.HyperlaneProject('rival', rival.system_id, 0, progress=300, completed_turn=1))
        game.ships[:] = [s for s in game.ships if s.owner != 'rival']
        self.assertIsNone(victory.current_result(game))
        data = game.to_dict()
        data['result'] = dict(winner='rival', condition='race', turn=game.turn)
        with self.assertRaises(SaveError):
            GameState.from_dict(data)

    def test_known_empires_only_and_no_invented_goals_for_other_races(self):
        game = campaign(with_ai=True, rival_race_id='wanderers', rival_count=2)
        for owner in game.opponents:
            game.diplomacy_between('player', owner).contact_turn = 0
        self.assertEqual(victory.known_race_goals(game), [])
        first_contact.establish(game, 'player', 'rival', notify=False)
        self.assertEqual([owner for owner, _ in victory.known_race_goals(game)], ['rival'])
        self.assertEqual(victory.race_goal(campaign(race_id='terran')).title, 'The Galactic Charter')

    def test_ai_explores_without_looking_up_unvisited_routes_then_researches(self):
        game = campaign(with_ai=True, rival_race_id='wanderers', victory_conditions=('race',))
        home = scientists(game, motherships.homes(game, 'rival')[0])
        origin = home.system_id
        network(game, (0, 1))
        game.systems[1].x = game.systems[origin].x+6/140
        game.systems[1].y = game.systems[origin].y
        game.hyperlane_surveys['rival'] = [origin]
        original_candidates = lanes.candidates
        def inspected_only(current, sid, owner):
            self.assertIn(sid, current.hyperlane_surveys[owner])
            return original_candidates(current, sid, owner)
        with patch('orion.hyperlanes.candidates', side_effect=inspected_only):
            motherships.ai_orders(game, 'rival')
        self.assertTrue(home.departure_pending)
        game.cancel_departures([home.id], owner='rival')
        network(game, (0, origin))
        lanes.ai_orders(game, 'rival')
        self.assertIsNotNone(lanes.project_at(game, origin, 'rival'))
        motherships.ai_orders(game, 'rival')
        self.assertFalse(home.has_course)

    def test_ai_can_backtrack_through_an_exhausted_system_to_reach_new_stars(self):
        game = campaign(with_ai=True, rival_race_id='wanderers', victory_conditions=('race',))
        home = motherships.homes(game, 'rival')[0]
        origin, middle, destination = game.systems[home.system_id], game.systems[8], game.systems[9]
        for star in game.systems:
            star.x, star.y = .95, .95
        origin.x, origin.y = .1, .3
        middle.x, middle.y = .25, .3
        destination.x, destination.y = .4, .3
        network(game, (9, 10))
        game.hyperlane_surveys['rival'] = [s.id for s in game.systems if s.id != 9]
        self.assertFalse(game.can_reach(9, 'rival', ships=[home]))
        motherships.ai_orders(game, 'rival')
        self.assertEqual(home.destination, 8)


class RaceSaveTests(unittest.TestCase):
    def test_v47_preserves_existing_routes_voyages_and_progress_without_new_victory(self):
        game = campaign(victory_conditions=('conquest', 'council'))
        absent = next(s.id for s in game.systems if s.id != 0 and s.id not in lanes.candidates(game, 0, 'player'))
        network(game, (0, absent))
        recovered(game)
        home = motherships.homes(game)[0]
        game.send_ship(home.id, absent)
        a, b = next(lane.pair for lane in lanes.generate_network(game) if 0 not in lane.pair)
        game.hyperlane_projects.append(lanes.HyperlaneProject('player', a, b, progress=125, paused=True))
        raw = game.to_dict()
        raw.pop('hidden_hyperlanes')
        raw.pop('hyperlane_surveys')
        before = copy.deepcopy(raw)
        loaded = GameState.from_dict(raw, version=47)
        self.assertEqual(raw, before)
        self.assertEqual(loaded, GameState.from_dict(raw, version=47))
        self.assertIn(lanes.HiddenHyperlane(0, absent), loaded.hidden_hyperlanes)
        self.assertEqual(loaded.hyperlane_projects, game.hyperlane_projects)
        self.assertTrue(loaded.ship_at(home.id).hyperlane)
        self.assertNotIn('race', loaded.victory_conditions)
        self.assertEqual(GameState.from_dict(loaded.to_dict()), loaded)

    def test_invalid_network_survey_and_duplicate_research_are_rejected(self):
        game = campaign(victory_conditions=())
        network(game, (0, 1), (0, 2))
        lanes.start(game, 0)
        base = game.to_dict()
        cases = []
        for field, value in (
            ('hidden_hyperlanes', []),
            ('hidden_hyperlanes', [{'first': 0, 'second': 0}]),
            ('hidden_hyperlanes', [{'first': False, 'second': 1}]),
            ('hidden_hyperlanes', [{'first': 1, 'second': 2}]),
            ('hidden_hyperlanes', base['hidden_hyperlanes']*2),
            ('hyperlane_surveys', {'missing': [0]}),
            ('hyperlane_surveys', {'player': [0, 0]}),
            ('hyperlane_surveys', {'player': [True]}),
        ):
            data = copy.deepcopy(base)
            data[field] = value
            cases.append(data)
        duplicate = copy.deepcopy(base)
        second = copy.deepcopy(duplicate['hyperlane_projects'][0])
        second['destination'] = 3-second['destination']
        duplicate['hyperlane_projects'].append(second)
        cases.append(duplicate)
        for data in cases:
            with self.subTest(data=data):
                with self.assertRaises(SaveError):
                    GameState.from_dict(data)


class RaceObjectivesScreenTests(unittest.TestCase):
    setUp = test_hyperlanes.HyperlaneScreenTests.setUp
    click = test_hyperlanes.HyperlaneScreenTests.click
    drawn = test_hyperlanes.HyperlaneScreenTests.drawn

    def test_objectives_button_progress_and_contact_filter_do_not_mutate_world(self):
        app = self.app
        app.game = game = campaign(with_ai=True, rival_race_id='wanderers', rival_count=2)
        for owner in game.opponents:
            game.diplomacy_between('player', owner).contact_turn = 0
        app.open_objectives()
        self.click('objectives_race')
        before = game.to_dict()
        drawn = self.drawn()
        self.assertIn('Recover every forgotten hyperlane', drawn)
        self.assertIn(f'0 / {len(game.hidden_hyperlanes)} routes', drawn)
        for owner in game.opponents:
            self.assertNotIn(game.empire_name_for(owner), drawn)
        first_contact.establish(game, 'player', 'rival', notify=False)
        drawn = self.drawn()
        self.assertIn(game.empire_name_for('rival'), drawn)
        self.assertNotIn(game.empire_name_for('rival_2'), drawn)
        before['diplomacy'] = game.to_dict()['diplomacy']
        self.assertEqual(game.to_dict(), before)
        self.click('objectives_hyperlanes')
        self.assertEqual(app.screen, 'hyperlane')

    def test_completed_project_can_start_another_then_final_investment_opens_result(self):
        app, game = self.app, self.app.game
        game.victory_conditions = ('race',)
        network(game, (0, 1), (0, 2))
        app.open_hyperlane(0)
        self.click('hyperlane_start')
        game.research = 600
        self.click('hyperlane_invest')
        self.assertEqual(app.screen, 'hyperlane')
        self.click('hyperlane_start')
        self.click('hyperlane_invest')
        self.assertEqual(app.screen, 'result')
        self.assertIn('RACE-SPECIFIC VICTORY', self.drawn())
        self.assertEqual(GameState.from_dict(game.to_dict()), game)


if __name__ == '__main__':
    unittest.main()
