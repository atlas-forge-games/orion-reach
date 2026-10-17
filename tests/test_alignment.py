"""Fixed diplomacy baselines, existing-save continuity and the visible matrix."""
import copy
import itertools
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT','1')

import pygame as pg
from orion import alignment, balance, first_contact
from orion.diplomacy import advance_diplomacy
from orion.model import new_game, GameState
from orion.races import RACES
from orion.storage import Storage


def campaign(**kwargs):
    return new_game(seed=12, random_starts=False, with_guardians=False, with_tombs=False,
                    with_black_holes=False, fog_of_war=kwargs.pop('fog_of_war',False), **kwargs)


class AlignmentTests(unittest.TestCase):
    def setUp(self):
        previous=balance.active_profile()
        balance.activate(balance.default_profile())
        self.addCleanup(lambda:balance.activate(previous))

    def test_published_matrix_and_zero_centre(self):
        expected=[
            [25,15,11,4,-16,22,1,-2,11,-2,-6],
            [15,25,8,8,-6,11,4,8,8,1,-2],
            [11,8,25,-2,-23,8,8,-2,25,-2,-6],
            [4,8,-2,25,-2,1,1,-2,-2,-9,15],
            [-16,-6,-23,-2,25,-19,-13,4,-23,4,-6],
            [22,11,8,1,-19,25,-2,-6,8,-6,-9],
            [1,4,8,1,-13,-2,25,1,8,-6,-2],
            [-2,8,-2,-2,4,-6,1,25,-2,11,-6],
            [11,8,25,-2,-23,8,8,-2,25,-2,-6],
            [-2,1,-2,-9,4,-6,-6,11,-2,25,-13],
            [-6,-2,-6,15,-6,-9,-2,-6,-6,-13,25],
        ]
        self.assertEqual(set(alignment.PROFILES),set(RACES))
        # The published eleven-race reference remains fixed as the roster expands.
        races=[race for race in alignment.PROFILES if race not in ('serevan', 'skirr')]
        self.assertEqual([[alignment.score(a,b) for b in races] for a in races],expected)
        pairs=list(itertools.combinations(races,2))
        self.assertAlmostEqual(sum(alignment.raw_score(a,b) for a,b in pairs)/len(pairs),0)
        self.assertEqual(alignment.score('serevan', 'skirr'), -25)
        self.assertEqual(alignment.score('terran', 'serevan'), 15)

    def test_all_empire_pairs_start_at_their_alignment(self):
        for observer in (False,True):
            game=campaign(race_id='observer' if observer else 'terran',rival_count=5)
            for a,b in itertools.combinations(game.owners,2):
                r=alignment.relationship(game,a,b)
                self.assertEqual(r.total,alignment.between(game,a,b))
                self.assertEqual(r.history,0)
                self.assertEqual(alignment.between(game,a,b),alignment.between(game,b,a))
            self.assertEqual(GameState.from_dict(game.to_dict()),game)

    def test_roster_changes_cannot_change_existing_pairs(self):
        a=campaign(rival_race_id='varkesh',rival_count=1)
        b=campaign(rival_race_id='varkesh',rival_count=5)
        self.assertEqual(a.diplomacy.relations,b.diplomacy.relations)
        quiet=campaign(with_ai=False)
        quiet.add_opponent('kharuun')
        self.assertEqual(quiet.diplomacy.relations,15)

    def test_alignment_is_never_added_per_turn_or_load(self):
        for race in RACES:
            game=campaign(rival_race_id=race)
            initial=game.diplomacy.relations
            for turn in range(1,65):
                game.turn,game.year=turn,2299+turn
                advance_diplomacy(game)
                self.assertEqual(game.diplomacy.relations,initial)
            for _ in range(3):
                game=GameState.from_dict(game.to_dict())
                self.assertEqual(game.diplomacy.relations,initial)

    def test_history_changes_without_losing_alignment(self):
        game=campaign(rival_race_id='kharuun')
        self.assertEqual(alignment.relationship(game,'player','rival'),alignment.Relationship(15,0,15))
        self.assertIn('accepted',game.diplomacy_action('trade'))
        advance_diplomacy(game)
        self.assertEqual(alignment.relationship(game,'player','rival'),alignment.Relationship(15,1,16))
        game.diplomacy.relations=-100
        self.assertEqual(alignment.relationship(game,'player','rival'),alignment.Relationship(15,-115,-100))
        advance_diplomacy(game)
        self.assertFalse(game.diplomacy.trade_active)
        self.assertEqual(game.diplomacy.relations,-100)

    def test_passive_forgiveness_stops_at_alignment(self):
        game=campaign(rival_race_id='wanderers')
        game.diplomacy.relations=20
        for turn in range(1,33):
            game.turn,game.year=turn,2299+turn
            advance_diplomacy(game)
        self.assertEqual(game.diplomacy.relations,22)
        game=campaign(rival_race_id='varkesh')
        game.diplomacy.relations=-18
        for turn in range(1,33):
            game.turn,game.year=turn,2299+turn
            advance_diplomacy(game)
        self.assertEqual(game.diplomacy.relations,-16)

    def test_legacy_profile_and_relation_scores_survive_repeated_loading(self):
        game=campaign()
        game.diplomacy.relations=47
        game.diplomacy.trade_active=True
        with tempfile.TemporaryDirectory() as folder:
            storage=Storage(folder)
            path=storage.save(game)
            payload=json.loads(path.read_text())
            payload['balance']['version']=7
            del payload['balance']['data']['alignment']
            del payload['balance']['data']['rules']['alignment']
            path.write_text(json.dumps(payload))
            restored,_=storage.load(path)
            self.assertEqual(restored,game)
            self.assertEqual(alignment.relationship(restored,'player','rival'),alignment.Relationship(15,32,47))
            again,_=storage.load(storage.save(restored))
            self.assertEqual(again,restored)

    def test_editor_values_and_bounds_and_saved_profile(self):
        profile=balance.default_profile()
        profile['data']['alignment']['kharuun']['openness']=-2
        balance.require_valid(profile)
        balance.activate(profile)
        with patch('orion.balance.prepare_new_game'):
            game=campaign()
        self.assertEqual(game.diplomacy.relations,4)
        with tempfile.TemporaryDirectory() as folder:
            storage=Storage(folder)
            path=storage.save(game)
            balance.activate(balance.default_profile())
            restored,_=storage.load(path)
            self.assertEqual(alignment.between(restored,'player','rival'),4)
        for value in (-3,3,True,1.5):
            invalid=copy.deepcopy(profile)
            invalid['data']['alignment']['terran']['autonomy']=value
            self.assertTrue(balance.validate(invalid))
        invalid=copy.deepcopy(profile)
        invalid['data']['rules']['alignment']['REFERENCE_DISTANCE']=0
        self.assertTrue(balance.validate(invalid))

    def test_hidden_contacts_remain_hidden(self):
        game=campaign(fog_of_war=True,rival_race_id='varkesh')
        self.assertEqual(game.diplomacy.relations,-16)
        self.assertFalse(first_contact.known(game,'player','rival'))
        self.assertEqual(first_contact.pending(game),[])


class AlignmentInterfaceTests(unittest.TestCase):
    def test_compare_and_matrix_close_without_changing_game(self):
        from orion.app import App
        from orion.balance_editor import BalanceEditor
        with tempfile.TemporaryDirectory() as folder:
            app=App(Path(folder),capture=True)
            try:
                app.game=campaign()
                before=app.game.to_dict()
                app.go('galaxy')
                app.open_diplomacy()
                app.render()
                self.assertIn('diplomacy_alignment',[b.key for b in app.buttons])
                app.show_alignment('rival')
                app.render()
                button=next(b for b in app.buttons if b.key=='dialog_alignment_matrix')
                app.activate(button)
                app.render()
                self.assertTrue(app.dialog['alignment_matrix'])
                app.handle_event(pg.event.Event(pg.KEYDOWN,key=pg.K_ESCAPE))
                self.assertIsNone(app.dialog)
                self.assertEqual(app.game.to_dict(),before)
                app.game=campaign(fog_of_war=True)
                app.show_alignment('rival')
                self.assertIsNone(app.dialog)
                app.show_alignment()
                app.render()
                self.assertTrue(app.dialog['alignment_matrix'])
                self.assertEqual(first_contact.pending(app.game),[])
            finally:
                app.audio.close()
                pg.quit()
            editor=BalanceEditor(Path(folder)/'balance.json')
            editor.select_section('alignment')
            editor.draw()
            self.assertEqual(len(editor.document.fields('alignment','terran')),5)
            pg.quit()
