"""Debt settlement, compulsory defeat, AI collapse and saved-campaign migration."""

import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from orion import ai, treasury
from orion.empire import summarize_empire
from orion.model import GameState, RuleError, SaveError
from orion.storage import SAVE_VERSION, Storage
from test_ship_maintenance import campaign


class TreasuryRulesTests(unittest.TestCase):
    def test_interest_rounds_up_and_nonnegative_balances_cost_nothing(self):
        for credits, expected in ((120, 0), (0, 0), (-1, 1), (-9, 1), (-10, 1),
                                  (-11, 2), (-1000, 100), (-9999, 1000)):
            self.assertEqual(treasury.interest(credits), expected)

    def test_budget_and_turn_charge_interest_once_then_compound(self):
        game = campaign(with_ai=False)
        normal = game.empire_rates[0]
        game.credits = -1000
        self.assertEqual(game.empire_rates[0], normal-100)
        for _ in range(3):
            before, expected, charge = game.credits, game.empire_rates[0], treasury.interest(game.credits)
            summary = summarize_empire(game)
            self.assertEqual(summary.interest, charge)
            self.assertEqual(summary.income, summary.gross_income-summary.maintenance-summary.interest)
            report = game.advance_turn()
            self.assertEqual(game.credits, before+expected)
            self.assertEqual(report.income, expected)
            self.assertEqual(sum(message.startswith("Debt interest:") for message in report.alerts), 1)
            self.assertTrue(any(f"{charge:,} CR charged" in message for message in report.alerts))
            self.assertNotIn("_turn_interest", game.__dict__)

    def test_new_debt_starts_paying_on_the_following_turn(self):
        game = campaign(with_ai=False)
        game.credits = 0
        for system, planet in game.settlements("player"):
            planet.trade_goods = False
        from orion.model import Ship
        game.ships.extend(Ship(game.next_ship_id+i, "titan", 0) for i in range(3))
        game.next_ship_id += 3
        income = game.empire_rates[0]
        self.assertLess(income, 0)
        self.assertEqual(game.debt_interest(), 0)
        game.advance_turn()
        self.assertEqual(game.credits, income)
        self.assertGreater(game.debt_interest(), 0)

    def test_opening_debt_is_frozen_before_ai_actions_for_all_empires(self):
        game = campaign(rival_count=2)
        for index, owner in enumerate(game.owners):
            game._empire(owner).credits = -1000*(index+1)
        before = {owner: game.treasury_for(owner) for owner in game.owners}
        expected = {owner: game.empire_rates_for(owner)[0] for owner in game.owners}
        def receive_credits(state, owner, **kwargs):
            state._empire(owner).credits += 100
            self.assertEqual(state.debt_interest(owner), treasury.interest(before[owner]))
            return []
        with patch("orion.ai.run_ai", side_effect=receive_credits):
            game.advance_turn()
        for owner in game.owners:
            self.assertEqual(game.treasury_for(owner), before[owner]+expected[owner]+(100 if owner != "player" else 0))

    def test_ai_budget_includes_interest(self):
        game = campaign()
        with patch.object(game, "planet_yields", return_value=(0, 10, 0)):
            baseline = ai.projected_income(game, "rival")
            game.opponent.credits = -1000
            self.assertEqual(ai.projected_income(game, "rival"), baseline-100)

    def test_interrupted_end_turn_never_charges_interest(self):
        game = campaign(with_ai=False)
        game.credits = -1000
        turn = game.turn
        with patch("orion.monsters.intercept", return_value=True):
            report = game.advance_turn()
        self.assertEqual((game.turn, game.credits, report.income), (turn, -1000, 0))
        self.assertNotIn("_turn_interest", game.__dict__)
        expected = game.empire_rates[0]
        game.advance_turn()
        self.assertEqual(game.credits, -1000+expected)

    def test_bankruptcy_boundary_is_inclusive_and_cannot_be_disabled(self):
        for conditions in ((), ("conquest",), ("council",), ("race",)):
            for credits, loses in ((-9999, False), (-10000, True), (-10001, True)):
                game = campaign(with_ai=False, victory_conditions=conditions)
                game.credits = credits
                result = game.check_victory(convene=False)
                self.assertEqual(result is not None, loses)
                if loses:
                    self.assertEqual((result.winner, result.condition), (None, "bankruptcy"))
                    with self.assertRaises(RuleError):
                        game.advance_turn()
                    with self.assertRaises(RuleError):
                        game.queue_ship(0, 2, "scout")

    def test_interest_can_cause_defeat_before_new_combat_and_round_trips(self):
        game = campaign(with_ai=False)
        game.credits = -9500
        expected = game.credits+game.empire_rates[0]
        self.assertGreater(game.credits+game.empire_rates[0]+game.debt_interest(), treasury.BANKRUPTCY_LIMIT)
        self.assertLessEqual(expected, treasury.BANKRUPTCY_LIMIT)
        with patch("orion.monsters.intercept", return_value=False) as intercept:
            game.advance_turn()
        self.assertEqual(intercept.call_count, 1)  # Only the pre-turn check ran.
        self.assertEqual(game.credits, expected)
        self.assertEqual(game.result.condition, "bankruptcy")
        self.assertEqual(GameState.from_dict(game.to_dict()).to_dict(), game.to_dict())

    def test_bankrupt_ai_collapses_and_its_final_debt_stops_compounding(self):
        game = campaign(rival_count=2, victory_conditions=())
        game.opponent.credits = -10000
        self.assertTrue(game.colony_systems("rival"))
        self.assertTrue(game.ships_owned_by("rival"))
        self.assertIsNone(game.check_victory(convene=False))
        self.assertFalse(game.colony_systems("rival"))
        self.assertFalse(game.ships_owned_by("rival"))
        self.assertTrue(any("bankrupt" in event.message for event in game.opponent.events))
        events = copy.deepcopy(game.opponent.events)
        game.check_victory(convene=False)
        self.assertEqual(game.opponent.events, events)
        with patch("orion.ai.run_ai", return_value=[]):
            game.advance_turn()
        self.assertEqual(game.opponent.credits, -10000)
        self.assertEqual(GameState.from_dict(game.to_dict()).to_dict(), game.to_dict())

    def test_last_bankrupt_rival_allows_conquest_but_player_debt_has_priority(self):
        for bankrupt_player in (False, True):
            game = campaign(victory_conditions=("conquest",))
            game.opponent.credits = -10000
            if bankrupt_player:
                game.credits = -10000
            result = game.check_victory(convene=False)
            self.assertEqual(result.condition, "bankruptcy" if bankrupt_player else "conquest")
            self.assertEqual(result.winner, None if bankrupt_player else "player")

    def test_observer_is_not_bankrupt_and_mobile_rival_homes_can_collapse(self):
        game = campaign(race_id="observer", rival_count=2, rival_race_id="wanderers",
                        victory_conditions=())
        self.assertEqual(game.credits, 0)
        self.assertFalse(treasury.bankrupt(game))
        self.assertEqual(game.debt_interest(), 0)
        game.opponent.credits = -10000
        game.check_victory(convene=False)
        self.assertFalse(game.settlements("rival"))
        self.assertFalse(game.ships_owned_by("rival"))
        self.assertIsNone(game.result)
        self.assertTrue(any("bankrupt" in event.message for event in game.observer_events))
        self.assertEqual(GameState.from_dict(game.to_dict()).to_dict(), game.to_dict())

    def test_old_indebted_saves_migrate_without_rewriting_and_new_defeat_saves_load(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(directory)
            for credits in (-1000, -10000, -50000):
                game = campaign(with_ai=False)
                path = storage.save(game)
                payload = json.loads(path.read_text())
                payload["version"] = 59
                payload["game"]["credits"] = credits
                path.write_text(json.dumps(payload))
                original = path.read_bytes()
                loaded, _ = storage.load(path)
                self.assertEqual(path.read_bytes(), original)
                self.assertEqual(loaded.credits, credits)
                self.assertEqual(loaded.result is not None, credits <= -10000)
                rewritten = storage.save(loaded)
                self.assertEqual(json.loads(rewritten.read_text())["version"], SAVE_VERSION)
                restored, _ = storage.load(rewritten)
                self.assertEqual(restored.to_dict(), loaded.to_dict())

    def test_terminal_legacy_outcomes_stay_immutable_and_false_financial_outcomes_fail(self):
        game = campaign()
        from orion.raiding import abandon
        for _, planet in game.settlements("rival"):
            abandon(planet)
        game.eliminate_defeated()
        game.check_victory(convene=False)
        self.assertEqual(game.result.winner, "player")
        game.credits = -20000  # A completed campaign from before debt rules existed.
        restored = GameState.from_dict(game.to_dict(), version=59)
        self.assertEqual(restored.result, game.result)
        self.assertEqual(GameState.from_dict(restored.to_dict()).result, game.result)
        ordinary = campaign(with_ai=False)
        data = ordinary.to_dict()
        data["result"] = {"winner": None, "condition": "bankruptcy", "turn": ordinary.turn}
        with self.assertRaises(SaveError):
            GameState.from_dict(data)
        data["result"] = None
        data["credits"] = -10000
        with self.assertRaises(SaveError):
            GameState.from_dict(data)


class TreasuryInterfaceTests(unittest.TestCase):
    def setUp(self):
        import pygame as pg
        from orion.app import App
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.folder.name), capture=True)
        self.addCleanup(self.app.audio.close)
        self.app.game = campaign(with_ai=False)
        self.app.go("galaxy")

    def test_header_and_empire_expose_interest_and_limit_without_mutating_state(self):
        from orion.ui import text
        self.app.game.credits = -1000
        before = self.app.game.to_dict()
        with patch("orion.galaxy_hud.text", wraps=text) as written:
            self.app.render()
        self.assertTrue(any("Interest 100/turn" in str(call.args[1]) for call in written.call_args_list))
        self.app.open_empire()
        with patch("orion.empire_view.text", wraps=text) as written:
            self.app.render()
        self.assertTrue(any("Bankruptcy at -10,000" in str(call.args[1]) for call in written.call_args_list))
        self.assertTrue(any("100 interest =" in str(call.args[1]) for call in written.call_args_list))
        self.assertEqual(self.app.game.to_dict(), before)

    def test_end_turn_opens_defeat_screen_and_autosave_restores_bankruptcy(self):
        from orion.ui import text
        for system, planet in self.app.game.settlements("player"):
            self.app.game.set_trade_goods(system.id, planet.id)
        self.app.game.credits = -9500
        self.app.advance_turn()
        self.assertEqual(self.app.screen, "result")
        with patch("orion.victory_view.text", wraps=text) as written:
            self.app.render()
        self.assertIn("Defeat", [call.args[1] for call in written.call_args_list])
        self.assertNotIn("Draw", [call.args[1] for call in written.call_args_list])
        saved = self.app.storage.saves_dir/"autosave.json"
        loaded, _ = self.app.storage.load(saved)
        self.assertEqual(loaded.result.condition, "bankruptcy")


if __name__ == "__main__":
    unittest.main()
