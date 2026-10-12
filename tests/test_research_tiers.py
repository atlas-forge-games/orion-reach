"""Paired tiers, independent upgrades, genuine legacy research and UI traversal."""

from dataclasses import asdict
from itertools import product
import json
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame as pg
from orion import ai
from orion.legacy_research import LEGACY_TECHNOLOGIES
from orion.model import GameState
from orion.research import BRANCHES, TECHNOLOGIES, ResearchState, branch_tiers, choices
from orion.storage import Storage
from scenarios import empty_fleet_game

FIXTURES = Path(__file__).parent/"fixtures"


def complete(state, identifier):
    error = state.choice_error(identifier)
    if error:
        raise AssertionError(error)
    state.active = identifier
    bank, technology = state.spend(TECHNOLOGIES[identifier].cost)
    assert bank == 0 and technology.id == identifier


def fund(game, *identifiers):
    for identifier in identifiers:
        game.research += TECHNOLOGIES[identifier].cost
        game.choose_research(identifier)


class TierRulesTests(unittest.TestCase):
    def test_every_path_has_two_choices_per_tier_and_no_dead_ends(self):
        self.assertLessEqual(set(LEGACY_TECHNOLOGIES), set(TECHNOLOGIES))
        self.assertEqual([len(branch_tiers(b)) for b in BRANCHES], [3, 4, 8, 5, 7, 2, 7, 2, 6])
        for branch in BRANCHES:
            tiers = branch_tiers(branch)
            self.assertEqual(tiers, tuple(range(1, len(tiers)+1)))
            for path in product((0, 1), repeat=len(tiers)):
                with self.subTest(branch=branch, path=path):
                    state = ResearchState()
                    for tier, option in zip(tiers, path):
                        options = choices(branch, tier)
                        self.assertEqual(len(options), 2)
                        self.assertTrue(all(state.choice_error(t.id) is None for t in options))
                        for later in tiers[tier:]:
                            self.assertTrue(all(state.status(t.id) == "locked" for t in choices(branch, later)))
                        selected, alternative = options[option], options[1-option]
                        complete(state, selected.id)
                        self.assertEqual(state.status(alternative.id), "excluded")
                        self.assertEqual(ResearchState.from_dict(asdict(state)), state)
                    self.assertEqual(state.finished_branches, 1)
                    self.assertEqual(len(state.completed), len(tiers))

    def test_advanced_shields_interdiction_and_sensors_unlock_without_lower_upgrade(self):
        cases = (
            (("radiation_shields", "thermal_barriers", "gravity_wells", "barrier_fields"),
             "planetary_shielding", "planetary_shield", "shield_capacity", 200),
            (("radiation_shields", "thermal_barriers", "planetary_shielding", "subspace_interdiction"),
             "gravity_wells", "interdictor", "interdiction_slow", 40),
            (("research_networks", "distributed_computing", "targeting_computers", "long_range_sensors"),
             "deep_space_radar", "sensor_array", "sensor_range", 10),
            (("research_networks", "distributed_computing", "targeting_computers", "predictive_fire_control", "subspace_scanners"),
             "deep_space_radar", "sensor_array", "sensor_range", 20),
        )
        for path, earlier, building, bonus, expected in cases:
            with self.subTest(upgrade=path[-1]):
                game = empty_fleet_game(seed=2408, with_ai=False)
                fund(game, *path)
                self.assertNotIn(earlier, game.technology.completed)
                self.assertEqual(game.bonuses_for()[bonus], expected)
                self.assertIsNone(game.build_error(0, 2, building))
                game.resources, game.credits = 1000, 1000
                game.queue_building(0, 2, building)
                game.buy_construction(0, 2)
                self.assertIn(building, game.planet_at(0, 2).buildings)
                if building == "planetary_shield":
                    self.assertEqual(game.planet_at(0, 2).shield_points, 200)
                self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_targeting_can_start_at_higher_tiers_and_upgrades_do_not_double_count(self):
        for path, expected in (
            (("deep_space_radar", "predictive_fire_control"), 20),
            (("deep_space_radar", "long_range_sensors", "quantum_targeting"), 30),
            (("targeting_computers", "predictive_fire_control", "quantum_targeting"), 30),
        ):
            state = ResearchState()
            for identifier in ("research_networks", "distributed_computing", *path):
                complete(state, identifier)
            self.assertEqual(state.bonuses["accuracy"], expected)
        state = ResearchState()
        for identifier in ("radiation_shields", "thermal_barriers", "planetary_shielding", "barrier_fields"):
            complete(state, identifier)
        self.assertEqual(state.bonuses["shield_capacity"], 200)
        self.assertEqual(state.bonuses["shield_upkeep"], 2)

    def test_ai_obeys_all_tiers_and_reaches_ascension(self):
        for race in ("terran", "kharuun", "aelari"):
            game = empty_fleet_game(seed=2408, rival_race_id=race, fog_of_war=False)
            game.opponent.research = 100000
            for _ in range(sum(len(branch_tiers(b)) for b in BRANCHES)+1):
                count = len(game.opponent.technology.completed)
                ai.research_choice(game)
                self.assertEqual(len(game.opponent.technology.completed), count+1)
            state = game.opponent.technology
            self.assertEqual(state.finished_branches, 9)
            self.assertEqual(state.completed[-1], "ascension_theory")
            self.assertEqual(GameState.from_dict(game.to_dict()), game)


class LegacyResearchTests(unittest.TestCase):
    def setUp(self):
        self.cases = json.loads((FIXTURES/"v0361_research_states.json").read_text())

    def test_authentic_save_keeps_discoveries_conflicting_choices_project_and_gate(self):
        source = FIXTURES/"v0361_research.json"
        original = source.read_bytes()
        old = json.loads(original)["game"]
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            game, _ = storage.load(source)
            for owner, previous in (("player", old), ("rival", old["opponent"])):
                state, before = game.research_state(owner), previous["technology"]
                self.assertEqual((state.completed, state.active, state.progress),
                                 (before["completed"], before["active"], before["progress"]))
            self.assertTrue({"planetary_shielding", "gravity_wells"} <= set(game.technology.completed))
            self.assertTrue({"barrier_fields", "subspace_interdiction"} <= set(game.technology.completed))
            self.assertEqual(game.bonuses_for()["shield_capacity"], 200)
            self.assertEqual(game.bonuses_for()["interdiction_slow"], 40)
            self.assertEqual(game.bonuses_for()["sensor_range"], 20)
            self.assertEqual(game.bonuses_for()["accuracy"], 30)
            self.assertEqual(game.planet_at(0, 2).construction_queue[0].item_id, "ascension_gate")
            self.assertEqual(storage.load(storage.save(game))[0], game)
            game.research = 90
            self.assertEqual(game.advance_research().id, "electronic_countermeasures")
            game.opponent.research = game.opponent.technology.project_cost-game.opponent.technology.progress
            self.assertEqual(game.advance_research("rival").id, "ascension_theory")
            self.assertEqual(GameState.from_dict(game.to_dict()), game)
            self.assertEqual(source.read_bytes(), original)

    def test_relocated_active_research_keeps_its_original_remaining_cost(self):
        state = ResearchState.from_dict(self.cases["relocated_active"], version=27)
        self.assertEqual(TECHNOLOGIES[state.active].cost, 880)
        self.assertEqual((state.progress, state.project_cost), (30, 120))
        state = ResearchState.from_dict(asdict(state))
        self.assertEqual(state.spend(89), (0, None))
        state = ResearchState.from_dict(asdict(state))
        bank, finished = state.spend(11)
        self.assertEqual((bank, finished.id), (10, "field_stabilization"))
        self.assertFalse(state.legacy_active)
        self.assertEqual(ResearchState.from_dict(asdict(state)), state)

    def test_old_skipped_tiers_are_preserved_but_new_research_follows_sequence(self):
        state = ResearchState.from_dict(self.cases["missing_middle"], version=27)
        self.assertEqual(state.status("quantum_targeting"), "locked")
        self.assertEqual(state.status("targeting_computers"), "discovered")
        self.assertEqual(state.status("deep_space_radar"), "discovered")
        complete(state, "distributed_computing")
        self.assertEqual(state.status("quantum_targeting"), "available")
        complete(state, "quantum_targeting")
        self.assertEqual(state.status("subspace_scanners"), "excluded")
        self.assertEqual(state.legacy_count, 4)
        self.assertEqual(state.finished_branches, 1)
        self.assertEqual(ResearchState.from_dict(asdict(state)), state)

    def test_malformed_migration_metadata_and_illegal_new_choices_are_rejected(self):
        state = ResearchState.from_dict(self.cases["relocated_active"], version=27)
        for changes in (
            {"legacy_count": True}, {"legacy_count": -1}, {"legacy_count": 2},
            {"legacy_active": 1}, {"active": None}, {"progress": 120},
            {"completed": ["fusion_drives"]}, {"legacy_active": False},
        ):
            data = dict(asdict(state), **changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                ResearchState.from_dict(data)
        state = ResearchState.from_dict(self.cases["missing_middle"], version=27)
        complete(state, "distributed_computing")
        data = asdict(state)
        data["completed"].append("planetary_automation")
        with self.assertRaises(ValueError):
            ResearchState.from_dict(data)


class TierInterfaceTests(unittest.TestCase):
    def test_all_tiers_are_browsable_by_pointer_and_keyboard_with_exactly_two_cards(self):
        from orion.app import App
        with tempfile.TemporaryDirectory() as folder:
            app = App(folder, capture=True)
            app.game = empty_fleet_game(seed=2408, with_ai=False)
            app.go("research")
            app.window = pg.display.set_mode((980, 900), pg.RESIZABLE)
            app.present()
            for branch in BRANCHES:
                app.select_research_branch(branch)
                for tier in branch_tiers(branch):
                    app.render()
                    button = next(b for b in app.buttons if b.key == f"research_tier_{tier}")
                    x, y = button.rect.center
                    v = app.viewport
                    pos = (round(v.x+x*v.w/1440), round(v.y+y*v.h/900))
                    for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
                        app.handle_event(pg.event.Event(kind, pos=pos, button=1))
                        app.render()
                    self.assertEqual(app.research_tier, tier)
                    visible = {b.key for b in app.buttons if b.key.startswith("research_choose_")}
                    self.assertEqual(visible, {"research_choose_"+t.id for t in choices(branch, tier)})
                    self.assertTrue(all(app.canvas.get_rect().contains(b.rect) for b in app.buttons))
                app.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_PAGEUP, mod=0))
                self.assertEqual(app.research_tier, len(branch_tiers(branch))-1)
                app.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_PAGEDOWN, mod=0))
                self.assertEqual(app.research_tier, len(branch_tiers(branch)))
        pg.quit()


if __name__ == "__main__":
    unittest.main()
