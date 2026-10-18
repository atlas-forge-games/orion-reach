"""Conservation of research points and read-only technology information."""

import json
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame as pg
from orion.app import App
from orion.model import GameState, RuleError
from orion.research import ResearchState, TECHNOLOGIES
from orion.research_view import project_eta
from scenarios import empty_fleet_game


def campaign(**kwargs):
    return empty_fleet_game(seed=2408, with_ai=kwargs.pop("with_ai", False), fog_of_war=False, **kwargs)


class ResearchSwitchingTests(unittest.TestCase):
    def test_alternative_and_cross_branch_switches_preserve_every_point_without_early_effects(self):
        game = campaign()
        game.research = 24
        game.choose_research("civil_engineering")
        game.research = 5
        for identifier in ("automated_factories", "ion_drives", "compact_reactors", "civil_engineering")*4:
            game.choose_research(identifier)
            self.assertEqual((game.technology.progress, game.research), (29, 0))
            self.assertEqual(game.technology.completed, [])
            self.assertEqual(game.technology.bonuses, {})
        game.research = TECHNOLOGIES["civil_engineering"].cost-29
        game.advance_research()
        self.assertEqual(game.technology.completed, ["civil_engineering"])
        self.assertEqual(game.technology.status("automated_factories"), "excluded")
        self.assertEqual(game.technology.bonuses, {"colony_industry": 2})

    def test_switch_to_more_expensive_project_then_cheaper_project_banks_overflow(self):
        game = campaign()
        game.research = TECHNOLOGIES["civil_engineering"].cost
        game.choose_research("civil_engineering")
        game.research = 30
        game.choose_research("ion_drives")
        game.choose_research("orbital_assembly")
        self.assertEqual((game.technology.progress, game.technology.project_cost), (30, TECHNOLOGIES["orbital_assembly"].cost))
        game.research = TECHNOLOGIES["research_instruments"].cost+50-30
        game.choose_research("prefabricated_structures")
        self.assertEqual(game.technology.progress, TECHNOLOGIES["research_instruments"].cost+50)
        self.assertEqual(game.choose_research("research_instruments").id, "research_instruments")
        self.assertEqual((game.research, game.technology.progress, game.technology.active), (50, 0, None))
        self.assertNotIn("prefabricated_structures", game.technology.completed)
        self.assertNotIn("ion_drives", game.technology.completed)
        game.choose_research("orbital_assembly")
        self.assertEqual((game.research, game.technology.progress), (0, 50))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_invalid_switch_is_atomic_and_unfinished_project_does_not_unlock_next_tier(self):
        game = campaign()
        game.research = 17
        game.choose_research("civil_engineering")
        for invalid in ("civil_engineering", "orbital_assembly", "ascension_theory", "missing", None, []):
            before = game.to_dict()
            with self.assertRaises(RuleError):
                game.choose_research(invalid)
            self.assertEqual(game.to_dict(), before)
        game.research = TECHNOLOGIES["civil_engineering"].cost-17
        game.advance_research()
        game.research = 15
        game.choose_research("ion_drives")
        for identifier in ("civil_engineering", "automated_factories"):
            before = game.to_dict()
            with self.assertRaises(RuleError):
                game.choose_research(identifier)
            self.assertEqual(game.to_dict(), before)

    def test_another_empire_has_its_own_transfer_balance(self):
        game = campaign(with_ai=True)
        game.research, game.opponent.research = 9, 31
        game.choose_research("civil_engineering")
        game.choose_research("ion_drives", owner="rival")
        game.choose_research("compact_reactors", owner="rival")
        self.assertEqual((game.technology.active, game.technology.progress), ("civil_engineering", 9))
        self.assertEqual((game.opponent.technology.active, game.opponent.technology.progress), ("compact_reactors", 31))
        self.assertEqual((game.research, game.opponent.research), (0, 0))

    def test_switch_from_legacy_project_retains_old_discoveries_and_uses_new_target_cost(self):
        game = campaign()
        fixture = json.loads((Path(__file__).parent/"fixtures/v0361_research_states.json").read_text())
        game.technology = ResearchState.from_dict(fixture["relocated_active"], version=27)
        self.assertEqual(game.technology.project_cost, 120)
        before = GameState.from_dict(game.to_dict())
        self.assertEqual(before.technology.progress, 30)
        game.choose_research("civil_engineering")
        self.assertEqual((game.technology.progress, game.technology.project_cost), (30, TECHNOLOGIES["civil_engineering"].cost))
        self.assertFalse(game.technology.legacy_active)
        self.assertEqual(game.technology.legacy_count, 1)
        self.assertEqual(game.technology.completed, ["compact_reactors"])
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_saved_switched_project_resumes_with_identical_progress_and_completion(self):
        game = campaign()
        game.headquarters()[1].scientists = 1
        game.research = TECHNOLOGIES["research_networks"].cost-9
        game.choose_research("civil_engineering")
        game.choose_research("research_networks")
        restored = GameState.from_dict(game.to_dict())
        for _ in range(5):
            self.assertEqual(game.advance_turn(), restored.advance_turn())
        self.assertEqual(game, restored)
        self.assertIn("research_networks", game.technology.completed)
        self.assertNotIn("civil_engineering", game.technology.completed)

    def test_estimates_include_transferred_work_and_banked_points(self):
        game = campaign()
        game.research = TECHNOLOGIES["ion_drives"].cost-13
        game.choose_research("ion_drives")
        game.research = 5
        self.assertEqual(project_eta(game, TECHNOLOGIES["civil_engineering"], 4), "2 turns")
        self.assertEqual(project_eta(game, TECHNOLOGIES["ion_drives"], 4), "2 turns")
        game.research = 20
        self.assertEqual(project_eta(game, TECHNOLOGIES["civil_engineering"], 0), "Ready now")


class TechnologyInformationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.folder.name), capture=True)
        self.app.game = campaign()
        self.app.go("galaxy")
        self.app.open_research()
        self.app.present()

    def click(self, key, button=1):
        self.app.render()
        control = next(b for b in self.app.buttons if b.key == key)
        if button == 1:
            self.assertTrue(control.enabled)
        x, y = control.rect.center
        v = self.app.viewport
        pos = (round(v.x+x*v.w/1440), round(v.y+y*v.h/900))
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, pos=pos, button=button))
            self.app.render()

    def test_click_and_keyboard_select_without_dialog_and_autosave_transferred_points(self):
        game = self.app.game
        game.research = 24
        self.click("research_choose_civil_engineering")
        self.assertIsNone(self.app.dialog)
        self.click("research_choose_automated_factories")
        self.assertIsNone(self.app.dialog)
        self.assertEqual(game.technology.progress, 24)
        self.app.focus = "research_choose_ion_drives"
        self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_RETURN, mod=0))
        self.app.render()
        self.assertEqual((game.technology.active, game.technology.progress), ("ion_drives", 24))
        loaded, _ = self.app.storage.load(self.app.storage.saves_dir/"autosave.json")
        self.assertEqual(loaded, game)
        self.assertIsNone(self.app.dialog)

    def test_right_click_can_inspect_active_available_discovered_excluded_and_locked_choices(self):
        game = self.app.game
        game.research = TECHNOLOGIES["civil_engineering"].cost
        game.choose_research("civil_engineering")
        game.research = 12
        game.choose_research("orbital_assembly")
        before = game.to_dict()
        for size in ((980, 900), (1920, 1080)):
            self.app.window = pg.display.set_mode(size, pg.RESIZABLE)
            self.app.present()
            for identifier in ("civil_engineering", "automated_factories", "orbital_assembly",
                               "prefabricated_structures", "advanced_fortifications"):
                self.app.show_research_technology(identifier)
                self.click("research_choose_"+identifier, button=3)
                self.assertEqual(self.app.dialog["technology"], identifier)
                self.assertEqual([b.key for b in self.app.buttons], ["dialog_close"])
                self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_e, mod=0))
                self.assertEqual(game.to_dict(), before)
                self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_ESCAPE, mod=0))
                self.assertIsNone(self.app.dialog)
        self.app.show_research_overview()
        self.app.render()
        self.assertNotIn("research_choose_ascension_theory", {b.key for b in self.app.buttons})
        self.assertIn("research_legacy_objectives", {b.key for b in self.app.buttons})
        self.assertEqual(game.to_dict(), before)

    def test_right_click_on_active_title_is_read_only_and_no_stale_hotspots_after_navigation(self):
        game = self.app.game
        game.research = 24
        self.click("research_choose_ion_drives")
        saved = (self.app.storage.saves_dir/"autosave.json").read_bytes()
        self.click("research_show_active", button=3)
        self.assertEqual(self.app.dialog["technology"], "ion_drives")
        self.click("dialog_close")
        self.assertEqual((self.app.storage.saves_dir/"autosave.json").read_bytes(), saved)
        self.app.go("galaxy")
        v = self.app.viewport
        pos = (round(v.x+780*v.w/1440), round(v.y+237*v.h/900))
        self.app.handle_event(pg.event.Event(pg.MOUSEBUTTONUP, pos=pos, button=3))
        self.assertIsNone(self.app.dialog)
        self.click("open_research", button=3)
        self.assertEqual(self.app.dialog["technology"], "ion_drives")
        self.assertEqual(self.app.screen, "galaxy")
        self.click("dialog_close")


if __name__ == "__main__":
    unittest.main()
