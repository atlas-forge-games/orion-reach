"""Diplomatic costs, AI responses, race traits, treaty income and playable screens."""

import json
import os
from pathlib import Path
import tempfile
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame as pg

from orion.empire import summarize_empire
from orion.model import GameState, PLAYER, RIVAL, RuleError, SaveError, new_game
from functools import partial

# Preserve these pre-exploration scenarios; fog-on rules have their own tests.
new_game = partial(new_game, fog_of_war=False)
from orion.races import RACES
from orion.storage import Storage


class DiplomacyRulesTests(unittest.TestCase):
    def test_races_are_selectable_and_preserve_starting_production(self):
        for race_id in RACES:
            game = new_game(seed=2408, race_id=race_id)
            self.assertEqual(game.race_id, race_id)
            self.assertNotEqual(game.opponent.race_id, race_id)
            self.assertEqual(game.planet_at(0, 2).yields_per_turn, (6, 8, 0))
            self.assertEqual(game.credits, 120)
            self.assertEqual(game.diplomacy.relations, 0)
            for rival_race in RACES:
                chosen = new_game(seed=2408, race_id=race_id, rival_race_id=rival_race)
                self.assertEqual(chosen.opponent.race_id, rival_race)
                self.assertEqual(GameState.from_dict(chosen.to_dict()), chosen)
        for kwargs in ({"race_id": "unknown"}, {"race_id": []}, {"rival_race_id": "unknown"}):
            with self.assertRaises(SaveError):
                new_game(seed=2408, **kwargs)

    def test_envoy_costs_and_cooldowns_apply_to_each_race(self):
        for race_id, expected_gain in (("terran", 12), ("kharuun", 8), ("aelari", 8)):
            game = new_game(seed=2408, race_id=race_id)
            game.diplomacy_action("envoy")
            self.assertEqual(game.credits, 110)
            self.assertEqual(game.diplomacy.relations, expected_gain)
            self.assertEqual(game.opponent.credits, 120)
            for _ in range(3):
                before = game.to_dict()
                with self.assertRaisesRegex(RuleError, "turn 4"):
                    game.diplomacy_action("envoy")
                self.assertEqual(game.to_dict(), before)
                game.advance_turn()
            game.diplomacy_action("envoy")
            self.assertEqual(game.diplomacy.relations, 2*expected_gain)

    def test_gift_transfers_credits_once_and_saves_recipient_balance(self):
        game = new_game(seed=2408)
        game.diplomacy_action("gift")
        self.assertEqual((game.credits, game.opponent.credits), (70, 170))
        self.assertEqual(game.diplomacy.relations, 15)
        before = game.to_dict()
        with self.assertRaisesRegex(RuleError, "turn 6"):
            game.diplomacy_action("gift")
        self.assertEqual(game.to_dict(), before)
        self.assertEqual(GameState.from_dict(before), game)

    def test_invalid_unaffordable_and_no_contact_actions_are_atomic(self):
        game = new_game(seed=2408)
        for action in ("unknown", "end_trade", "end_research"):
            before = game.to_dict()
            with self.assertRaises(RuleError):
                game.diplomacy_action(action)
            self.assertEqual(game.to_dict(), before)
        game.credits = 9
        for action in ("envoy", "gift"):
            before = game.to_dict()
            with self.assertRaisesRegex(RuleError, "credits"):
                game.diplomacy_action(action)
            self.assertEqual(game.to_dict(), before)
        peaceful = new_game(seed=2408, with_ai=False)
        before = peaceful.to_dict()
        with self.assertRaisesRegex(RuleError, "contact"):
            peaceful.diplomacy_action("trade")
        with self.assertRaises(RuleError):
            peaceful.add_opponent("unknown")
        self.assertEqual(peaceful.to_dict(), before)

    def test_rival_race_controls_acceptance_and_offers_share_a_cooldown(self):
        for race, trade, research in (("terran", 20, 30), ("kharuun", 15, 45), ("aelari", 30, 15)):
            for action, threshold in (("trade", trade), ("research", research)):
                with self.subTest(race=race, action=action):
                    game = new_game(seed=2408, rival_race_id=race)
                    game.diplomacy.relations = threshold-1
                    response = game.diplomacy_action(action)
                    self.assertIn("declined", response)
                    self.assertFalse(getattr(game.diplomacy, f"{action}_active"))
                    self.assertEqual(game.credits, 120)
                    for offer in ("trade", "research"):
                        before = game.to_dict()
                        with self.assertRaises(RuleError):
                            game.diplomacy_action(offer)
                        self.assertEqual(game.to_dict(), before)
                    for _ in range(3):
                        game.advance_turn()
                    game.diplomacy.relations = threshold
                    self.assertIn("accepted", game.diplomacy_action(action))
                    self.assertTrue(getattr(game.diplomacy, f"{action}_active"))
                    before = game.to_dict()
                    with self.assertRaisesRegex(RuleError, "already active"):
                        game.diplomacy_action(action)
                    self.assertEqual(game.to_dict(), before)

    def test_treaty_benefits_go_to_each_empire_without_changing_local_yields(self):
        game = new_game(seed=2408, race_id="aelari", rival_race_id="kharuun")
        game.diplomacy.relations = 60
        game.diplomacy.trade_active = game.diplomacy.research_active = True
        game.opponent.credits = 0  # Keep construction spending out of the bank comparison.
        self.assertEqual(game.diplomatic_yields(PLAYER), (5, 4))
        self.assertEqual(game.diplomatic_yields(RIVAL), (6, 3))
        self.assertEqual(game.planet_at(0, 2).yields_per_turn, (6, 8, 0))
        report = game.advance_turn()
        self.assertEqual((report.income, report.research), (13, 4))
        self.assertEqual((game.credits, game.research), (133, 4))
        self.assertEqual((game.opponent.credits, game.opponent.research), (14, 3))
        self.assertEqual(game.diplomacy.relations, 62)
        for owner in (PLAYER, RIVAL):
            summary = summarize_empire(game, owner=owner)
            self.assertEqual((summary.income, summary.research), game.empire_rates_for(owner))
            self.assertEqual((summary.agreement_income, summary.agreement_research), game.diplomatic_yields(owner))
            self.assertEqual(summary.industry, 6)

    def test_ending_an_agreement_stops_income_and_negative_relations_end_the_other(self):
        game = new_game(seed=2408)
        game.diplomacy.trade_active = game.diplomacy.research_active = True
        game.diplomacy.relations = 10
        game.opponent.credits = 0
        game.diplomacy_action("end_trade")
        self.assertEqual(game.diplomacy.relations, -5)
        self.assertEqual(game.diplomatic_yields(), (0, 3))
        self.assertEqual(game.diplomacy.offer_ready_turn, 4)
        report = game.advance_turn()
        self.assertFalse(game.diplomacy.research_active)
        self.assertEqual((report.income, report.research), (8, 0))
        self.assertEqual(game.opponent.research, 0)
        self.assertIn("ended remaining agreements", game.diplomacy.events[-1].message)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_relations_are_bounded_and_zero_relations_do_not_cancel_agreements(self):
        game = new_game(seed=2408)
        game.diplomacy.relations = 98
        self.assertIn("+2", game.diplomacy_action("envoy"))
        self.assertEqual(game.diplomacy.relations, 100)
        before = game.to_dict()
        with self.assertRaises(RuleError):
            game.diplomacy_action("gift")
        self.assertEqual(game.to_dict(), before)
        game.diplomacy.trade_active = True
        game.advance_turn()
        self.assertEqual(game.diplomacy.relations, 100)
        game.diplomacy.relations = 0
        game.advance_turn()
        self.assertTrue(game.diplomacy.trade_active)
        self.assertEqual(game.diplomacy.relations, 1)

    def test_each_rival_race_still_expands_and_develops(self):
        for race_id in RACES:
            game = new_game(seed=2408, rival_race_id=race_id)
            for _ in range(70):
                game.advance_turn()
            self.assertGreaterEqual(summarize_empire(game, owner=RIVAL).colonies, 4)
            self.assertTrue(game.opponent.technology.completed)
            self.assertEqual(game.credits, 680)
            self.assertEqual(GameState.from_dict(game.to_dict()), game)


class DiplomacySaveTests(unittest.TestCase):
    def test_save_resume_preserves_traits_treaties_cooldowns_and_future_turns(self):
        game = new_game(seed=2408, race_id="aelari", rival_race_id="terran")
        game.diplomacy_action("envoy")
        game.diplomacy_action("gift")
        game.diplomacy_action("trade")
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            restored, _ = storage.load(storage.save(game))
            self.assertEqual(restored, game)
            for _ in range(20):
                self.assertEqual(restored.advance_turn(), game.advance_turn())
                self.assertEqual(restored, game)
            for state in (game, restored):
                state.diplomacy_action("research")
                state.diplomacy_action("end_trade")
            self.assertEqual(restored, game)
            self.assertEqual(storage.load(storage.save(restored))[0], game)

    def test_v5_save_migrates_to_neutral_contact_without_changing_assets_or_file(self):
        game = new_game(seed=2408)
        for _ in range(20):
            game.advance_turn()
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            path = storage.save(game)
            payload = json.loads(path.read_text())
            payload["version"] = 5
            payload["game"].pop("race_id")
            payload["game"].pop("diplomacy")
            payload["game"]["opponent"].pop("race_id")
            path.write_text(json.dumps(payload))
            before = path.read_bytes()
            restored, _ = storage.load(path)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(restored.race_id, "terran")
            self.assertEqual(restored.opponent.race_id, "kharuun")
            self.assertEqual(restored.opponent, game.opponent)
            self.assertEqual(restored.systems, game.systems)
            self.assertEqual(restored.ships, game.ships)
            self.assertEqual((restored.credits, restored.research), (game.credits, game.research))
            self.assertEqual(restored.diplomacy.relations, 0)
            self.assertFalse(restored.diplomacy.trade_active)
            self.assertFalse(restored.diplomacy.research_active)
            self.assertEqual(restored.diplomacy.events[0].turn, game.turn)
            self.assertEqual(storage.load(storage.save(restored))[0], restored)

    def test_invalid_races_diplomatic_state_and_logs_are_rejected(self):
        game = new_game(seed=2408)
        game.advance_turn()
        changes = [
            lambda d: d.update(race_id="unknown"), lambda d: d.update(race_id=[]),
            lambda d: d.pop("race_id"), lambda d: d["opponent"].update(race_id="unknown"),
            lambda d: d["opponent"].pop("race_id"), lambda d: d.pop("diplomacy"),
            lambda d: d.update(diplomacy=None),
            lambda d: d["diplomacy"].update(relations=True),
            lambda d: d["diplomacy"].update(relations=101),
            lambda d: d["diplomacy"].update(trade_active=1),
            lambda d: d["diplomacy"].update(research_active="yes"),
            lambda d: d["diplomacy"].update(envoy_ready_turn=0),
            lambda d: d["diplomacy"].update(gift_ready_turn=99),
            lambda d: d["diplomacy"].update(offer_ready_turn=True),
            lambda d: d["diplomacy"]["events"][0].update(turn=3),
            lambda d: d["diplomacy"]["events"][0].update(message="hello\nworld"),
            lambda d: d["diplomacy"].update(events=[{"turn": 1, "message": "event"}]*13),
            lambda d: d["diplomacy"].update(events=[{"turn": 2, "message": "later"}, {"turn": 1, "message": "earlier"}]),
        ]
        for index, change in enumerate(changes):
            with self.subTest(index=index):
                data = game.to_dict()
                change(data)
                with self.assertRaises(SaveError):
                    GameState.from_dict(data)
        peaceful = new_game(seed=2408, with_ai=False).to_dict()
        peaceful["diplomacy"] = game.to_dict()["diplomacy"]
        with self.assertRaises(SaveError):
            GameState.from_dict(peaceful)


class DiplomacyInterfaceTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.tmp.name), capture=True)
        self.app.present()

    def click(self, key):
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        x, y = button.rect.center
        v = self.app.viewport
        pos = (v.x+round(x*v.w/1440), v.y+round(y*v.h/900))
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, button=1, pos=pos))
            self.app.render()

    def key(self, key):
        self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=key, mod=0))
        self.app.render()

    def start(self, with_ai=True):
        self.app.game = new_game(seed=2408, with_ai=with_ai)
        self.app.go("galaxy")
        self.app.render()

    def test_setup_selects_both_races_with_letterboxed_mouse_coordinates(self):
        self.app.window = pg.display.set_mode((980, 900), pg.RESIZABLE)
        self.app.present()
        self.click("new")
        self.click("race_kharuun")
        self.assertEqual(self.app.empire, "Kharuun Assembly")
        self.app.empire = "Custom civilization"
        self.click("race_aelari")
        self.assertEqual(self.app.empire, "Custom civilization")
        self.click("rival_race_terran")
        self.app.seed = "2408"
        self.click("launch")
        self.assertEqual((self.app.game.race_id, self.app.game.opponent.race_id), ("aelari", "terran"))
        restored, _ = self.app.storage.load(self.app.storage.saves_dir/"autosave.json")
        self.assertEqual(restored, self.app.game)

    def test_diplomacy_navigation_restores_origins_and_does_not_change_selection(self):
        self.start()
        self.app.game.selected_planet = 2
        for origin in ("galaxy", "system", "planet", "colony", "shipyard", "empire", "fleets", "rival"):
            with self.subTest(origin=origin):
                self.app.go(origin)
                before = self.app.game.to_dict()
                self.click("open_diplomacy")
                self.key(pg.K_LEFT)
                self.key(pg.K_RIGHT)
                self.key(pg.K_d)
                self.assertEqual(self.app.screen, origin)
                self.assertEqual(self.app.game.to_dict(), before)
        self.key(pg.K_d)
        self.click("diplomacy_intelligence")
        self.click("rival_back")
        self.assertEqual(self.app.screen, "diplomacy")
        self.click("diplomacy_pause")
        self.click("settings")
        self.click("settings_done")
        self.click("resume")
        self.assertEqual(self.app.screen, "diplomacy")

    def test_real_actions_accept_trade_disable_repeats_and_confirm_termination(self):
        self.start()
        self.key(pg.K_d)
        self.click("diplomacy_envoy")
        self.click("diplomacy_gift")
        self.assertEqual(self.app.game.diplomacy.relations, 27)
        self.click("diplomacy_trade")
        self.assertTrue(self.app.game.diplomacy.trade_active)
        for key in ("diplomacy_envoy", "diplomacy_gift", "diplomacy_research"):
            self.assertFalse(next(b for b in self.app.buttons if b.key == key).enabled)
        before = self.app.game.to_dict()
        self.click("diplomacy_end_trade")
        self.assertIsNotNone(self.app.dialog)
        self.click("dialog_cancel")
        self.assertEqual(self.app.game.to_dict(), before)
        self.click("diplomacy_end_turn")
        self.assertEqual(self.app.game.credits, 73)
        self.click("diplomacy_end_trade")
        self.click("dialog_ok")
        self.assertFalse(self.app.game.diplomacy.trade_active)
        restored, _ = self.app.storage.load(self.app.storage.saves_dir/"autosave.json")
        self.assertEqual(restored, self.app.game)
        self.app.load_game(self.app.storage.saves_dir/"autosave.json")
        self.key(pg.K_d)
        self.assertEqual(self.app.game, restored)

    def test_peaceful_campaign_can_add_rival_and_return_to_diplomacy(self):
        self.start(with_ai=False)
        self.click("open_diplomacy")
        self.click("diplomacy_add_rival")
        self.click("add_rival")
        self.click("rival_back")
        self.assertEqual(self.app.screen, "diplomacy")
        self.assertIsNotNone(self.app.game.diplomacy)
        self.click("diplomacy_envoy")
        self.assertEqual(self.app.game.diplomacy.relations, 12)


if __name__ == "__main__":
    unittest.main()
