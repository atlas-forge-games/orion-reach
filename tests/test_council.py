"""Council thresholds, public world-weighted ballots, defiance, saves and UI routing."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame as pg
from orion import council, first_contact, news
from orion.model import GameState, RuleError, SaveError, Ship, new_game
from orion.research import ASCENSION_COST, ResearchState, TECHNOLOGIES
from orion.storage import Storage


def scenario(counts=(4, 4, 4), *, observer=False, fog=False):
    game = new_game(seed=2408, galaxy_size="Compact", race_id="observer" if observer else "terran",
                    rival_race_id="kharuun", rival_count=len(counts) if observer else len(counts)-1,
                    fog_of_war=fog, with_guardians=False, with_tombs=False)
    game.ships.clear()
    for owner, wanted in zip(game.owners, counts):
        while council.world_votes(game).get(owner, 0) < wanted:
            system = next(s for s in game.systems if s.worlds and not any(p.colonized for p in s.worlds))
            settle(system.worlds[0], owner)
    for owner in first_contact.pending(game):
        first_contact.acknowledge(game, owner)
    return game


def settle(planet, owner):
    planet.biome = "Terran"
    planet.owner, planet.colonized, planet.population = owner, True, 1


def advance(game):
    # Keep the election fixture's census fixed while exercising real turn processing.
    with patch("orion.ai.run_ai", return_value=[]):
        game.advance_turn()


def convene(game):
    advance(game)
    assert game.council.election is not None
    return game.council.election


class CouncilRulesTests(unittest.TestCase):
    def test_first_election_requires_half_of_distinct_systems(self):
        game = scenario((4, 4, 3))
        system = next(s for s in game.systems if any(p.owner == "player" for p in s.worlds)
                      and any(not p.colonized for p in s.worlds))
        settle(next(p for p in system.worlds if not p.colonized), "rival")
        advance(game)
        self.assertEqual(sum(council.world_votes(game).values()), 12)
        self.assertEqual(council.settled_systems(game), 11)
        self.assertFalse(game.council.formed_turn)
        empty = next(s for s in game.systems if s.worlds and not any(p.colonized for p in s.worlds))
        settle(empty.worlds[0], "player")
        advance(game)
        self.assertEqual(game.council.formed_turn, game.turn)
        self.assertTrue(game.council.pending)
        self.assertEqual(game.council.election.weights, {"player": 5, "rival": 5, "rival_2": 3})
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_solo_campaign_does_not_form_a_council(self):
        game = scenario((12,))
        advance(game)
        self.assertFalse(game.council.formed_turn)

    def test_one_world_one_vote_regardless_of_population(self):
        game = scenario((6, 4, 2))
        for system in game.systems:
            for p in system.worlds:
                if p.owner == "rival":
                    p.population = 10
        election = convene(game)
        self.assertEqual(election.weights, {"player": 6, "rival": 4, "rival_2": 2})
        self.assertEqual(election.votes_needed, 6)
        game.council_vote("player")
        self.assertEqual((game.result.winner, game.result.condition), ("player", "council"))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_exact_half_tie_is_unsuccessful_and_repeats_after_50_turns(self):
        game = scenario((6, 6))
        election = convene(game)
        game.council_vote("player")
        self.assertEqual(election.status, "failed")
        self.assertIsNone(game.result)
        self.assertEqual(game.council.next_vote_turn, election.turn+50)
        system = next(s for s in game.systems if s.worlds and not any(p.colonized for p in s.worlds))
        settle(system.worlds[0], "player")
        for _ in range(49):
            advance(game)
        self.assertIs(game.council.election, election)
        advance(game)
        self.assertIsNot(game.council.election, election)
        self.assertEqual(game.council.election.turn, election.turn+50)
        self.assertEqual(game.council.election.weights, {"player": 7, "rival": 6})
        self.assertTrue(game.council.pending)

    def test_abstention_keeps_all_worlds_in_the_denominator(self):
        game = scenario((4, 4, 4))
        election = convene(game)
        game.council_vote(None)
        self.assertIsNone(election.ballots["player"])
        self.assertEqual((election.total_votes, election.votes_needed), (12, 6))
        self.assertEqual(election.status, "failed")
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_ai_backs_larger_friendly_empires_but_not_hostile_or_equal_ones(self):
        game = scenario((6, 4, 2))
        game.diplomacy.relations = 40
        game.diplomacy_between("player", "rival_2").relations = -100
        election = convene(game)
        self.assertEqual(election.ballots, {"rival": "player", "rival_2": "rival_2"})
        self.assertEqual(election.tally["player"], 4)
        self.assertEqual(council.ai_choice(game, "rival", {"player": 4, "rival": 4}), "rival")

    def test_foreign_winner_waits_for_human_acceptance(self):
        game = scenario((2, 8, 2))
        convene(game)
        game.council_vote("player")
        self.assertIsNone(game.result)
        self.assertEqual(game.council.election.status, "decision")
        before = game.to_dict()
        for action in (game.advance_turn, lambda: game.diplomacy_action("gift"),
                       lambda: game.choose_research("ion_drives"), lambda: game.queue_building(0, 2, "factory")):
            with self.assertRaisesRegex(RuleError, "Council"):
                action()
            self.assertEqual(game.to_dict(), before)
        game.council_ruling(True)
        self.assertEqual((game.result.winner, game.result.condition), ("rival", "council"))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_defiance_breaks_all_ai_treaties_and_stops_elections(self):
        game = scenario((2, 8, 2))
        for owner in game.opponents:
            relations = game.diplomacy_between("player", owner)
            relations.relations = 70
            relations.trade_active = relations.research_active = True
        convene(game)
        game.council_vote("rival")
        game.council_ruling(False)
        self.assertIsNone(game.result)
        self.assertEqual((game.council.election.status, game.council.next_vote_turn), ("defied", 0))
        for owner in game.opponents:
            relations = game.diplomacy_between("player", owner)
            self.assertEqual(relations.relations, -100)
            self.assertFalse(relations.trade_active or relations.research_active)
        restored = GameState.from_dict(game.to_dict())
        for _ in range(51):
            advance(game)
            advance(restored)
        self.assertEqual(restored, game)
        self.assertEqual(game.council.election.status, "defied")
        self.assertIsNone(game.result)

    def test_eliminated_empires_have_no_seat(self):
        game = scenario()
        for system in game.systems:
            for p in system.worlds:
                if p.owner == "rival_2":
                    p.owner = "rival"
        self.assertNotIn("rival_2", convene(game).weights)

    def test_defiant_player_can_still_win_by_conquest(self):
        game = scenario((2, 8, 2))
        convene(game)
        game.council_vote(None)
        game.council_ruling(False)
        # Model the territorial outcome of the ensuing war; invasion rules have their own tests.
        for system in game.systems:
            for planet in system.worlds:
                if planet.owner in game.opponents:
                    planet.owner = "player"
        game.eliminate_defeated()
        game.check_victory()
        self.assertEqual((game.result.winner, game.result.condition), ("player", "conquest"))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_council_establishes_contacts_without_revealing_worlds(self):
        game = scenario(fog=True)
        unexplored = {s.id for s in game.systems if not game.system_explored(s.id)}
        convene(game)
        self.assertTrue(all(first_contact.known(game, "player", o) for o in game.opponents))
        self.assertTrue(unexplored)
        self.assertTrue(all(not game.system_explored(sid) for sid in unexplored))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_due_election_waits_for_combat_and_opens_after_continuing(self):
        game = scenario()
        game.ships = [Ship(1, "frigate", 0), Ship(2, "frigate", 0, owner="rival")]
        game.next_ship_id = 3
        game.start_combat(0)
        council.schedule(game)
        game.check_victory()
        self.assertIsNone(game.council.election)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        game.combat.status = "victory"  # Test the post-battle handoff, independently of damage rules.
        game.finish_combat()
        self.assertTrue(game.council.pending)
        self.assertIsNone(game.combat)

    def test_observer_resolves_votes_without_player_input(self):
        game = scenario((8, 2, 2), observer=True)
        convene(game)
        self.assertEqual(game.council.election.status, "accepted")
        self.assertEqual((game.result.winner, game.result.condition), ("rival", "council"))
        self.assertNotIn("player", game.council.election.weights)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        with self.assertRaises(RuleError):
            game.council_vote("rival")

    def test_invalid_and_duplicate_choices_do_not_mutate_the_game(self):
        game = scenario()
        convene(game)
        for candidate in ("missing", [], True):
            before = game.to_dict()
            with self.assertRaises(RuleError):
                game.council_vote(candidate)
            self.assertEqual(game.to_dict(), before)
        game.council_vote(None)
        before = game.to_dict()
        with self.assertRaises(RuleError):
            game.council_vote("player")
        self.assertEqual(game.to_dict(), before)


class CouncilSaveTests(unittest.TestCase):
    def test_pending_vote_decision_and_news_round_trip(self):
        game = scenario((2, 8, 2))
        convene(game)
        self.assertGreater(news.unread_count(game), 0)
        news.mark_read(game)
        self.assertEqual(news.unread_count(game), 0)
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            restored, _ = storage.load(storage.save(game))
            self.assertEqual(restored, game)
            game.council_vote(None)
            restored.council_vote(None)
            self.assertEqual(restored, game)
            self.assertGreater(news.unread_count(game), 0)
            restored, _ = storage.load(storage.save(game))
            self.assertEqual(restored, game)
            game.council_ruling(False)
            self.assertEqual(storage.load(storage.save(game))[0], game)

    def test_v31_campaign_gains_council_on_next_eligible_turn(self):
        game = scenario()
        data = game.to_dict()
        data.pop("council")
        for empire in [data, data["opponent"], *data["other_opponents"].values()]:
            if empire:
                empire["technology"].pop("legacy_fuel")
        restored = GameState.from_dict(data, version=31)
        self.assertEqual(restored.council, council.CouncilState())
        convene(restored)
        self.assertTrue(restored.council.pending)

    def test_bad_ballots_tallies_census_schedules_and_events_are_rejected(self):
        game = scenario()
        convene(game)
        mutations = [lambda c: c.update(next_vote_turn=game.turn+49),
                     lambda c: c.update(formed_turn=True),
                     lambda c: c.update(news_read=100),
                     lambda c: c['events'][0].update(id=3),
                     lambda c: c['election']['weights'].update(player=400),
                     lambda c: c['election']['weights'].update(player=True),
                     lambda c: c['election']['ballots'].update(rival="missing"),
                     lambda c: c['election']['ballots'].update(player="player"),
                     lambda c: c['election'].update(status="accepted", winner="rival")]
        for mutate in mutations:
            data = game.to_dict()
            mutate(data['council'])
            with self.assertRaises(SaveError):
                GameState.from_dict(data)
        game.council_vote(None)
        data = game.to_dict()
        data['council']['election']['winner'] = "rival"
        with self.assertRaises(SaveError):
            GameState.from_dict(data)


class AscensionCostTests(unittest.TestCase):
    def test_theory_cost_is_5000_and_preserves_unfinished_points(self):
        self.assertEqual(TECHNOLOGIES['ascension_theory'].cost, 5000)
        from test_victory import discover_branches
        game = new_game(seed=2408, with_ai=False, with_tombs=False)
        discover_branches(game)
        game.research = 499
        game.choose_research('ascension_theory')
        self.assertEqual((game.technology.active, game.technology.progress), ('ascension_theory', 499))
        restored = GameState.from_dict(game.to_dict())
        restored.research = ASCENSION_COST-499+17
        restored.advance_research()
        self.assertIn('ascension_theory', restored.technology.completed)
        self.assertEqual(restored.research, 17)

    def test_previous_cost_bounds_are_validated_before_migration(self):
        from test_victory import discover_branches
        game = new_game(seed=2408, with_ai=False, with_tombs=False)
        discover_branches(game)
        game.research = 499
        game.choose_research('ascension_theory')
        data = game.to_dict()
        data.pop('council')
        data['technology'].pop('legacy_fuel')
        data['technology']['completed'] = [t for t in data['technology']['completed'] if TECHNOLOGIES[t].branch != 'materials' or TECHNOLOGIES[t].tier <= 4]
        restored = GameState.from_dict(data, version=31)
        self.assertEqual(restored.technology.progress, 499)
        self.assertEqual(restored.technology.project_cost, 5000)
        data['technology']['progress'] = 500
        with self.assertRaises(SaveError):
            GameState.from_dict(data, version=31)

    def test_legacy_active_theory_uses_new_price_and_can_save_over_500_rp(self):
        from orion.legacy_research import LEGACY_TECHNOLOGIES
        completed = [key for key, row in LEGACY_TECHNOLOGIES.items() if row[1] <= 2 and row[3]]
        # Choose the first alternative in each original tier, preserving order.
        seen, selected = set(), []
        for key in completed:
            tier = LEGACY_TECHNOLOGIES[key][:2]
            if tier not in seen:
                selected.append(key)
                seen.add(tier)
        state = ResearchState.from_dict({'completed': selected, 'active': 'ascension_theory', 'progress': 123}, version=27)
        self.assertEqual(state.project_cost, 5000)
        state.spend(600)
        from dataclasses import asdict
        restored = ResearchState.from_dict(asdict(state))
        self.assertEqual((restored.progress, restored.project_cost), (723, 5000))


class CouncilScreenTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        self.tmp = tempfile.TemporaryDirectory()
        self.app = App(Path(self.tmp.name), capture=True)
        self.app.window = pg.display.set_mode((980, 900), pg.RESIZABLE)
        self.app.present()

    def tearDown(self):
        self.app.audio.close()
        pg.quit()
        self.tmp.cleanup()

    def click(self, key):
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        self.assertTrue(button.enabled)
        x, y = button.rect.center
        v = self.app.viewport
        pos = (v.x+round(x*v.w/1440), v.y+round(y*v.h/900))
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, button=1, pos=pos))
            self.app.render()

    def test_end_turn_opens_council_before_idle_research_and_survives_reload(self):
        self.app.game = scenario()
        self.app.go('galaxy')
        with patch('orion.ai.run_ai', return_value=[]):
            self.app.advance_turn()
        self.assertEqual(self.app.screen, 'council')
        turn = self.app.game.turn
        self.app.advance_turn()
        self.assertEqual(self.app.game.turn, turn)
        self.app.load_game(self.app.storage.saves_dir/'autosave.json')
        self.assertEqual(self.app.screen, 'council')
        self.click('council_abstain')
        self.assertEqual(self.app.game.council.election.status, 'failed')
        self.click('council_back')
        self.assertEqual(self.app.screen, 'galaxy')

    def test_foreign_election_can_be_defied_with_letterboxed_clicks(self):
        self.app.game = scenario((2, 8, 2))
        convene(self.app.game)
        self.app.go('council')
        self.click('council_vote_player')
        self.assertEqual(self.app.game.council.election.status, 'decision')
        self.click('council_defy')
        self.assertEqual(self.app.screen, 'news')
        self.assertIsNone(self.app.game.result)
        self.assertEqual(self.app.game.diplomacy.relations, -100)

    def test_acceptance_and_human_win_show_council_result(self):
        for counts, candidate in (((2, 8, 2), 'rival'), ((6, 4, 2), 'player')):
            self.app.game = scenario(counts)
            convene(self.app.game)
            self.app.go('council')
            self.click('council_vote_'+candidate)
            if candidate == 'rival':
                self.click('council_accept')
            self.assertEqual(self.app.screen, 'result')
            self.assertEqual(self.app.game.result.condition, 'council')
            self.click('result_news')
            self.assertEqual(self.app.screen, 'news')

    def test_objectives_offer_all_three_victory_paths_and_council_preview(self):
        self.app.game = scenario((1, 1, 1))
        self.app.go('objectives')
        self.app.render()
        keys = {b.key for b in self.app.buttons}
        self.assertTrue({'research_ascension','gate_build','objectives_council'} <= keys)
        self.click('objectives_council')
        self.assertEqual(self.app.screen, 'council')
        self.assertFalse(any(b.key.startswith('council_vote_') for b in self.app.buttons))
