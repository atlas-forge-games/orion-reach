"""Research field selection and reminders across real campaign transitions."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame as pg

from orion import combat, tomb_worlds
from orion.app import App
from orion.model import GameState, Ship, new_game
from orion.research import BRANCHES, TECHNOLOGIES, branch_tiers, choices
from orion.ui import text, wrapped_lines
from scenarios import empty_fleet_game


class ResearchOverviewTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.folder.name), capture=True)
        self.app.game = self.campaign()
        self.app.go("galaxy")
        self.app.present()

    @staticmethod
    def campaign(**kwargs):
        game = empty_fleet_game(seed=2408, with_ai=kwargs.pop("with_ai", False),
                                fog_of_war=False, **kwargs)
        game.headquarters()[1].scientists = 1
        from scenarios import set_idle_trade_goods
        set_idle_trade_goods(game)
        return game

    def click(self, key, mouse_button=1):
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        if mouse_button == 1:
            self.assertTrue(button.enabled, key)
        x, y = button.rect.center
        v = self.app.viewport
        pos = (round(v.x+x*v.w/1440), round(v.y+y*v.h/900))
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, pos=pos, button=mouse_button))
            self.app.render()

    def test_ten_fields_and_direct_choices_work_at_letterboxed_window_sizes(self):
        before = self.app.game.to_dict()
        for size in ((980, 900), (1280, 800), (1920, 1080)):
            self.app.window = pg.display.set_mode(size, pg.RESIZABLE)
            self.app.present()
            self.app.go("galaxy")
            self.click("open_research")
            self.assertTrue(self.app.research_overview)
            fields = [b for b in self.app.buttons if b.key.startswith("research_branch_")]
            self.assertEqual(len(fields), 10)
            self.assertEqual(len({b.rect.x for b in fields}), 2)
            self.assertEqual(len({b.rect.y for b in fields}), 5)
            expected = {"research_choose_"+t.id for b in BRANCHES for t in choices(b, 1)}
            expected.add("research_choose_ascension_theory")
            self.assertEqual({b.key for b in self.app.buttons if b.key.startswith("research_choose_")}, expected)
            self.assertTrue(all(self.app.canvas.get_rect().contains(b.rect) for b in self.app.buttons))
            for branch in BRANCHES:
                identifier = choices(branch, 1)[1].id
                self.click("research_choose_"+identifier, mouse_button=3)
                self.assertEqual(self.app.dialog["technology"], identifier)
                self.click("dialog_close")
            self.assertEqual(self.app.game.to_dict(), before)

    def test_heading_opens_full_tiers_and_all_fields_returns_to_grid(self):
        self.click("open_research")
        self.click("research_branch_starships")
        self.assertFalse(self.app.research_overview)
        self.click("research_tier_3")
        self.assertIn("research_choose_drone_carriers", [b.key for b in self.app.buttons])
        self.click("research_fields")
        self.assertTrue(self.app.research_overview)
        self.assertEqual(len([b for b in self.app.buttons if b.key.startswith("research_branch_")]), 10)

    def test_idle_end_turn_banks_points_autosaves_and_opens_once(self):
        game = self.app.game
        rate, before = game.empire_rates[1], game.research
        self.click("end_turn")
        self.assertEqual((game.turn, self.app.screen), (2, "research"))
        self.assertEqual(game.research, before+rate)
        self.assertIsNone(game.technology.active)
        loaded, _ = self.app.storage.load(self.app.storage.saves_dir/"autosave.json")
        self.assertEqual(loaded, game)
        self.click("research_back")
        self.assertEqual(self.app.screen, "galaxy")
        self.app.open_empire()
        self.assertEqual(self.app.screen, "empire")
        self.app.close_empire()
        self.click("end_turn")
        self.assertEqual((game.turn, self.app.screen), (3, "research"))

    def test_unfinished_project_keeps_map_but_completion_prompts_next_tier(self):
        game = self.app.game
        game.choose_research("civil_engineering")
        self.click("end_turn")
        self.assertEqual(self.app.screen, "galaxy")
        game.technology.progress = game.technology.project_cost-1
        self.click("end_turn")
        self.assertEqual(self.app.screen, "research")
        self.assertTrue(self.app.research_overview)
        self.assertIn("civil_engineering", game.technology.completed)
        self.assertTrue(next(b for b in self.app.buttons if b.key == "research_choose_orbital_assembly").enabled)

    def test_reminder_returns_to_origin_with_selected_planet_unchanged(self):
        game = self.app.game
        game.selected_planet = 2
        self.app.go("planet")
        selection = (game.selected_system, game.selected_planet)
        self.app.advance_turn()
        self.assertEqual(self.app.screen, "research")
        self.click("research_back")
        self.assertEqual(self.app.screen, "planet")
        self.assertEqual((game.selected_system, game.selected_planet), selection)

    def test_ending_turn_from_old_news_still_prompts_when_there_are_no_new_reports(self):
        self.app.open_news()
        self.click("news_end_turn")
        self.assertEqual(self.app.screen, "research")
        self.click("research_back")
        self.assertEqual(self.app.screen, "news")

    def test_greeting_and_tomb_news_precede_research_reminder(self):
        self.app.game.tomb_worlds.append(tomb_worlds.TombWorld(0, 3))
        with patch("orion.tomb_worlds.awakening_due", return_value=True):
            self.app.advance_turn()
        self.assertEqual(self.app.screen, "contact")
        self.app.skip_contacts()
        self.assertEqual(self.app.screen, "news")
        self.click("news_back")
        self.assertEqual(self.app.screen, "research")
        self.click("research_back")
        self.assertEqual(self.app.screen, "galaxy")

    def test_ground_report_then_news_then_research(self):
        game = self.app.game
        home = game.headquarters()[1]
        home.buildings, home.garrison = ["barracks", "fortifications"], 8
        game.tomb_worlds.append(tomb_worlds.TombWorld(0, 2))
        with patch("orion.tomb_worlds.awakening_due", return_value=True):
            self.app.advance_turn()
        self.assertEqual(self.app.screen, "ground")
        self.click("ground_continue")
        self.assertEqual(self.app.screen, "news")
        self.click("news_back")
        self.assertEqual(self.app.screen, "research")

    def test_space_battle_precedes_research_reminder(self):
        game = self.app.game = self.campaign(with_ai=True)
        game.ships = [Ship(1, "frigate", 0), Ship(2, "frigate", 0, owner="rival")]
        game.next_ship_id = 3
        game.diplomacy.relations = -100
        self.app.advance_turn()
        self.assertEqual(self.app.screen, "combat")
        combat.autoresolve(game)
        self.app.finish_combat()
        self.assertEqual(self.app.screen, "research")
        self.click("research_back")
        self.assertEqual(self.app.screen, "system")

    def test_ascension_is_selectable_from_tenth_field_and_exhausted_tree_does_not_prompt(self):
        game = self.app.game
        game.research = sum(choices(b, t)[0].cost for b in BRANCHES for t in branch_tiers(b))+TECHNOLOGIES["ascension_theory"].cost
        for branch in BRANCHES:
            for tier in branch_tiers(branch):
                game.choose_research(choices(branch, tier)[0].id)
        self.click("open_research")
        self.click("research_choose_ascension_theory")
        self.assertIsNone(self.app.dialog)
        self.assertIn("ascension_theory", game.technology.completed)
        self.click("research_back")
        self.click("end_turn")
        self.assertEqual(self.app.screen, "galaxy")

    def test_observer_and_finished_campaign_never_prompt_for_player_research(self):
        self.app.game = new_game(seed=2408, race_id="observer", rival_count=2,
                                 with_tombs=False, with_guardians=False)
        self.app.advance_turn()
        self.assertEqual(self.app.screen, "galaxy")
        self.click("open_research")
        self.assertEqual((self.app.screen, self.app.observer_tab), ("observer", "research"))
        self.click("end_turn")
        self.assertEqual(self.app.screen, "observer")
        game = self.app.game = self.campaign(with_ai=True)
        for system in game.systems:
            for world in system.worlds:
                if world.owner == "rival":
                    world.owner = "player"
        game.check_victory()
        self.app.advance_turn()
        self.assertEqual(self.app.screen, "result")

    def test_full_technology_information_fits_and_keeps_save_state(self):
        game = self.app.game
        game.research = 1000
        game.choose_research("destroyer_hulls")
        game.choose_research("cruiser_hulls")
        before = game.to_dict()
        self.click("open_research")
        self.click("research_choose_drone_carriers", mouse_button=3)
        bounds = []
        lines = wrapped_lines(TECHNOLOGIES["drone_carriers"].description, 784, 17)
        values = []
        def capture(surface, value, *args, **kwargs):
            rect = text(surface, value, *args, **kwargs)
            if kwargs.get("family", "sans") == "sans":
                bounds.append(rect)
                values.append(value)
            return rect
        with patch("orion.ui.text", side_effect=capture):
            self.app.render()
        self.assertTrue(all(line in values for line in lines))
        close = next(b for b in self.app.buttons if b.key == "dialog_close")
        paragraphs = [r for r in bounds if r.left == 322]
        self.assertLess(max(r.bottom for r in paragraphs), close.rect.top)
        self.assertTrue(all(self.app.canvas.get_rect().contains(b.rect) for b in self.app.buttons))
        self.click("dialog_close")
        self.assertEqual(game.to_dict(), before)
        self.assertEqual(GameState.from_dict(game.to_dict()).to_dict(), before)


if __name__ == "__main__":
    unittest.main()
