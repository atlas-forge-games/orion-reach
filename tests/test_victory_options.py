"""Campaign options, expanded fuel research, save migration and real setup controls."""

import copy
from itertools import combinations
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame as pg
from orion import ai, council, victory
from orion.app import App
from orion.model import GameState, RuleError, SaveError, new_game
from orion.research import BRANCHES, TECHNOLOGIES, branch_tiers, choices
from orion.storage import Storage
from scenarios import place_near
from test_council import advance, convene, scenario


def campaign(**kwargs):
    kwargs.setdefault("rival_race_id", "kharuun")
    return new_game(seed=2408, fog_of_war=False, with_tombs=False, with_guardians=False, **kwargs)


def discover(game, identifier, owner="player"):
    state = game.research_state(owner)
    technology = TECHNOLOGIES[identifier]
    if technology.branch in BRANCHES:
        for tier in range(1, technology.tier):
            if tier not in state.completed_tiers(technology.branch):
                discover(game, choices(technology.branch, tier)[0].id, owner)
    game._empire(owner).research += technology.cost
    game.choose_research(identifier, owner=owner)


def finish_branches(game, owner="player", old=False):
    for branch in BRANCHES:
        for tier in branch_tiers(branch):
            if not old or (branch != "materials" or tier <= 4) and (branch != "computers" or tier <= 5):
                discover(game, choices(branch, tier)[0].id, owner)


def v32_data(game):
    data = game.to_dict()
    data.pop("victory_conditions")
    for empire in [data, data["opponent"], *data["other_opponents"].values()]:
        if empire:
            empire["technology"].pop("legacy_fuel")
            empire["technology"].pop("legacy_black_holes")
    return data


class VictoryOptionRulesTests(unittest.TestCase):
    def test_defaults_and_every_combination_round_trip(self):
        self.assertEqual(campaign().victory_conditions, victory.CONDITIONS)
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(directory)
            for count in range(4):
                for enabled in combinations(victory.CONDITIONS, count):
                    with self.subTest(enabled=enabled):
                        game = campaign(victory_conditions=list(reversed(enabled)))
                        self.assertEqual(game.victory_conditions, enabled)
                        self.assertEqual(storage.load(storage.save(game))[0], game)

    def test_bad_setup_and_saved_conditions_are_rejected(self):
        for invalid in (None, True, "science", {"science": True}, ["conquest", "conquest"], ["unknown"], [1], [[]]):
            with self.subTest(invalid=invalid):
                with self.assertRaises(SaveError):
                    campaign(victory_conditions=invalid)
                data = campaign().to_dict()
                data["victory_conditions"] = invalid
                with self.assertRaises(SaveError):
                    GameState.from_dict(data)
        data = campaign().to_dict()
        del data["victory_conditions"]
        with self.assertRaises(SaveError):
            GameState.from_dict(data)

    def test_conquest_can_be_disabled_without_disabling_elimination(self):
        for enabled in ((), ("science",), ("council",), ("conquest",)):
            game = campaign(victory_conditions=enabled)
            for system, planet in victory.colonies(game, "rival"):
                planet.owner = "player"
            game.eliminate_defeated()
            game.check_victory()
            if "conquest" in enabled:
                self.assertEqual((game.result.condition, game.result.winner), ("conquest", "player"))
            else:
                self.assertIsNone(game.result)
                advance(game)
                self.assertEqual(GameState.from_dict(game.to_dict()), game)
            lost = campaign(victory_conditions=enabled)
            lost.headquarters()[1].owner = "rival"
            lost.eliminate_defeated()
            lost.check_victory()
            self.assertIsNotNone(lost.result)
            self.assertNotEqual(lost.result.winner, "player")

    def test_disabled_council_does_not_form_or_pause_a_settled_galaxy(self):
        game = scenario((6, 4, 2))
        game.victory_conditions = ("conquest", "science")
        for _ in range(51):
            advance(game)
        self.assertEqual(game.council, council.CouncilState())
        self.assertIsNone(game.strategy_error())
        with self.assertRaises(RuleError):
            game.council_vote("player")
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_enabled_council_still_wins_when_it_is_the_only_condition(self):
        game = scenario((6, 4, 2))
        game.victory_conditions = ("council",)
        convene(game)
        game.council_vote("player")
        self.assertEqual((game.result.condition, game.result.winner), ("council", "player"))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_science_disabled_blocks_research_and_gate_for_every_empire(self):
        game = campaign(victory_conditions=("conquest",))
        before = game.to_dict()
        for owner in game.owners:
            self.assertIn("disabled", game.research_error("ascension_theory", owner=owner))
            with self.assertRaises(RuleError):
                game.choose_research("ascension_theory", owner=owner)
            system, planet = game.headquarters(owner)
            with self.assertRaises(RuleError):
                game.queue_gate(system.id, planet.id, owner=owner)
        self.assertEqual(game.to_dict(), before)
        discover(game, "cryogenic_fuel_tanks")
        self.assertIn("cryogenic_fuel_tanks", game.technology.completed)

    def test_science_only_can_finish_a_gate_and_disabled_gates_cannot_win(self):
        game = campaign(with_ai=False, victory_conditions=("science",))
        finish_branches(game)
        discover(game, "ascension_theory")
        home = game.headquarters()[1]
        home.ascension_gate = True
        home.gate_charge = 5
        game.check_victory()
        self.assertEqual(game.result.condition, "science")
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        game.victory_conditions, game.result = (), None
        self.assertIsNone(victory.current_result(game))
        home.gate_charge = 4
        victory.advance_gates(game, [(0, 2, "player")])
        self.assertEqual(home.gate_charge, 4)
        with self.assertRaises(SaveError):
            GameState.from_dict(game.to_dict())

    def test_ai_finishes_ordinary_research_without_disabled_ascension(self):
        game = campaign(victory_conditions=())
        game.opponent.research = 100000
        # Old goals should not cause AI to skip optional research forever when Science is off.
        game.opponent.technology.legacy_arsenal = True
        game.opponent.technology.legacy_fuel = True
        game.opponent.technology.legacy_black_holes = True
        count = sum(len(branch_tiers(b)) for b in BRANCHES)
        for _ in range(count+3):
            ai.research_choice(game)
        self.assertEqual(len(game.opponent.technology.completed), count)
        self.assertNotIn("ascension_theory", game.opponent.technology.completed)
        self.assertIsNone(game.opponent.technology.active)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_observer_can_continue_after_one_empire_remains(self):
        game = campaign(race_id="observer", rival_count=2, victory_conditions=())
        for _, planet in victory.colonies(game, "rival_2"):
            if not planet.habitat:
                planet.owner = "rival"
        game.ships[:] = [s for s in game.ships if s.owner != "rival_2"]
        game.eliminate_defeated()
        advance(game)
        self.assertIsNone(game.result)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_saved_council_cannot_be_injected_into_a_disabled_campaign(self):
        game = scenario()
        convene(game)
        data = game.to_dict()
        data["victory_conditions"] = ["conquest", "science"]
        with self.assertRaises(SaveError):
            GameState.from_dict(data)

    def test_v32_pending_vote_defaults_to_all_conditions_and_preserves_ballots(self):
        game = scenario()
        convene(game)
        restored = GameState.from_dict(v32_data(game), version=32)
        self.assertEqual(restored.victory_conditions, victory.CONDITIONS)
        self.assertEqual(restored.council, game.council)
        self.assertTrue(all(restored.research_state(o).legacy_fuel for o in game.owners))
        self.assertEqual(GameState.from_dict(restored.to_dict()), restored)

    def test_v32_ascension_goal_progress_and_finished_gate_survive(self):
        from scenarios import use_research_layout
        use_research_layout(self, legacy=True)
        game = campaign(with_ai=False)
        game.technology.legacy_fuel = True
        game.technology.legacy_black_holes = True
        finish_branches(game, old=True)
        game.research = 1234
        game.choose_research("ascension_theory")
        restored = GameState.from_dict(v32_data(game), version=32)
        self.assertEqual((restored.technology.active, restored.technology.progress), ("ascension_theory", 1234))
        self.assertEqual(restored.technology.finished_branches, len(BRANCHES))
        self.assertIsNone(restored.research_error("cryogenic_fuel_tanks"))
        restored.research = TECHNOLOGIES["ascension_theory"].cost-1234
        restored.advance_research()
        restored.headquarters()[1].ascension_gate = True
        restored.headquarters()[1].gate_charge = 3
        old = GameState.from_dict(v32_data(restored), version=32)
        self.assertEqual(old.headquarters()[1].gate_charge, 3)
        self.assertEqual(GameState.from_dict(old.to_dict()), old)


class AdvancedFuelTests(unittest.TestCase):
    def setUp(self):
        from scenarios import use_research_layout
        use_research_layout(self)

    def test_tanks_extend_existing_fleets_additively_without_changing_speed(self):
        game = campaign()
        discover(game, "lightweight_alloys")
        discover(game, "composite_structures")
        scout = game.ships[0]
        speed = game.ship_speed_bonus()
        game.systems[0].x, game.systems[0].y = .1, .4
        for identifier, expected in (("cryogenic_fuel_tanks", 42), ("antimatter_fuel_tanks", 57), ("spatial_compression_tanks", 77)):
            with self.subTest(tank=identifier):
                place_near(game, 1, distance=expected-.5)
                self.assertFalse(game.within_fuel_range(1))
                discover(game, identifier)
                self.assertEqual(game.fuel_range(), expected)
                self.assertEqual(game.fuel_range("rival"), 7)
                self.assertTrue(game.within_fuel_range(1))
                self.assertEqual(game.ship_speed_bonus(), speed)
                game.send_ship(scout.id, 1)
                game.cancel_departures([scout.id])
                self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_later_tanks_work_after_skipping_every_earlier_tank(self):
        game = campaign()
        for identifier in ("superconductors", "reinforced_armor", "deep_core_drills", "mirv_torpedoes",
                           "automated_refineries", "antimatter_torpedoes", "spatial_compression_tanks"):
            discover(game, identifier)
        self.assertEqual(game.fuel_range(), 27)
        self.assertEqual(game.technology.status("cryogenic_fuel_tanks"), "excluded")
        self.assertEqual(game.technology.status("antimatter_fuel_tanks"), "excluded")
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_varkesh_range_bonus_applies_to_new_tanks(self):
        game = campaign(race_id="varkesh")
        discover(game, "superconductors")
        discover(game, "cryogenic_fuel_tanks")
        self.assertEqual(game.fuel_range(), (7+10)*1.5)

    def test_tanks_keep_orders_already_underway_unchanged(self):
        game = campaign(with_ai=False)
        place_near(game, 1, distance=6)
        game.send_ship(game.ships[0].id, 1)
        advance(game)
        route = copy.deepcopy(game.ships[0])
        discover(game, "spatial_compression_tanks")
        self.assertEqual(game.ships[0], route)

    def test_ai_researches_new_tank_when_old_range_options_were_skipped(self):
        game = campaign()
        for identifier in ("superconductors", "reinforced_armor", "deep_core_drills"):
            discover(game, identifier, "rival")
        game.opponent.research = TECHNOLOGIES["cryogenic_fuel_tanks"].cost
        with patch.object(GameState, "system_explored", return_value=False), patch.object(GameState, "within_fuel_range", return_value=False):
            ai.research_choice(game)
        self.assertIn("cryogenic_fuel_tanks", game.opponent.technology.completed)
        self.assertEqual(game.fuel_range("rival"), 17)

    def test_new_campaigns_include_tank_tiers_in_ascension_requirements(self):
        game = campaign(with_ai=False)
        finish_branches(game, old=True)
        for identifier in ("planetary_data_vaults", "quantum_research_archives"):
            discover(game, identifier)
        self.assertIsNotNone(game.research_error("ascension_theory"))
        for identifier in ("automated_refineries", "antimatter_fuel_tanks", "nanostructured_materials"):
            discover(game, identifier)
        self.assertIsNone(game.research_error("ascension_theory"))


class VictorySetupScreenTests(unittest.TestCase):
    def setUp(self):
        from scenarios import use_research_layout
        use_research_layout(self)
        self.directory = tempfile.TemporaryDirectory()
        self.app = App(Path(self.directory.name), capture=True)
        self.app.window = pg.display.set_mode((980, 900), pg.RESIZABLE)
        self.app.present()

    def tearDown(self):
        self.app.audio.close()
        pg.quit()
        self.directory.cleanup()

    def click(self, key, mouse_button=1):
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        if mouse_button == 1:
            self.assertTrue(button.enabled, key)
        x, y = button.rect.center
        v = self.app.viewport
        pos = (round(v.x+x*v.w/1440), round(v.y+y*v.h/900))
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, button=mouse_button, pos=pos))
            self.app.render()

    def test_second_setup_screen_toggles_launches_and_autosaves_choices(self):
        self.app.go("race_select")
        self.click("setup_next")
        self.assertEqual(self.app.screen, "setup")
        self.click("victory_science")
        self.click("victory_council")
        self.click("setup_back")
        self.click("setup_next")
        self.assertEqual(self.app.victory_conditions, ("conquest",))
        buttons = [b for b in self.app.buttons if b.key.startswith("victory_")]
        self.assertEqual(len(buttons), 3)
        self.assertTrue(all(self.app.canvas.get_rect().contains(b.rect) for b in buttons))
        self.click("launch")
        self.assertEqual(self.app.game.victory_conditions, ("conquest",))
        restored, _ = self.app.storage.load(self.app.storage.saves_dir/"autosave.json")
        self.assertEqual(restored.victory_conditions, ("conquest",))

    def test_observer_setup_can_disable_all_victories(self):
        self.app.choose_race("observer")
        self.app.go("setup")
        for condition in victory.CONDITIONS:
            self.click("victory_"+condition)
        self.click("launch")
        self.assertTrue(self.app.game.is_observer)
        self.assertEqual(self.app.game.victory_conditions, ())
        self.app.go("objectives")
        self.app.render()
        self.assertFalse(next(b for b in self.app.buttons if b.key == "observer_council").enabled)

    def test_disabled_science_has_no_gate_or_idle_research_prompt_at_tree_end(self):
        self.app.game = campaign(with_ai=False, victory_conditions=())
        finish_branches(self.app.game)
        self.app.go("objectives")
        self.app.render()
        buttons = {b.key: b for b in self.app.buttons}
        self.assertFalse(buttons["research_ascension"].enabled)
        self.assertFalse(buttons["objectives_council"].enabled)
        self.assertNotIn("gate_build", buttons)
        self.assertFalse(self.app.needs_research_choice())
        self.app.go("research")
        self.app.render()
        self.assertFalse(next(b for b in self.app.buttons if b.key == "research_choose_ascension_theory").enabled)
        self.click("research_choose_ascension_theory", mouse_button=3)
        self.assertEqual(self.app.dialog["technology"], "ascension_theory")

    def test_new_tank_can_be_inspected_selected_and_switched_with_transferred_rp(self):
        self.app.game = campaign(with_ai=False)
        discover(self.app.game, "deep_core_drills")
        self.app.game.research = 120
        self.app.go("research")
        self.click("research_choose_cryogenic_fuel_tanks", mouse_button=3)
        self.assertEqual(self.app.dialog["technology"], "cryogenic_fuel_tanks")
        self.click("dialog_close")
        self.click("research_choose_cryogenic_fuel_tanks")
        self.assertEqual(self.app.game.technology.progress, 120)
        self.click("research_choose_mirv_torpedoes")
        self.assertEqual(self.app.game.technology.active, "mirv_torpedoes")
        self.assertEqual(self.app.game.technology.progress, 120)


if __name__ == "__main__":
    unittest.main()
