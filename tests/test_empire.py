"""Empire totals and real UI navigation with multi-colony test fixtures."""

import os
from pathlib import Path
import tempfile
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame as pg

from orion.empire import EmpireSummary, colony_rows, summarize_empire
from orion.model import ConstructionProject, new_game


def varied_empire():
    """Synthetic settlements with varied economies for report checks."""
    game = new_game(seed=2408)
    mercury, _, earth, mars = game.systems[0].worlds
    earth.buildings = ["factory", "trade_center"]
    earth.construction_queue = [ConstructionProject("research_lab", 12)]
    mercury.colonized, mercury.population = True, 1
    mercury.buildings = ["research_lab"]*4
    mars.colonized, mars.population, mars.richness = True, 3, "Rich"
    mars.buildings = ["mine"]
    remote = next(p for s in game.systems[1:] for p in s.worlds)
    remote.name, remote.size, remote.richness = "Altair Haven", "Large", "Average"
    remote.colonized, remote.population = True, 5
    remote.buildings = ["factory", "factory", "mine"]
    return game


class EmpireReportTests(unittest.TestCase):
    def test_totals_cover_all_colonies_and_reserved_slots(self):
        game = varied_empire()
        self.assertEqual(summarize_empire(game), EmpireSummary(
            colonies=4, population=17, industry=41, income=23, research=16,
            used_slots=11, capacity=28, projects=1, idle=3))
        self.assertEqual(game.empire_rates, (23, 16))
        colony_rows(game, "full", "population", True)
        self.assertEqual(summarize_empire(game).colonies, 4)

    def test_filters_and_numerical_sorts_include_only_settlements(self):
        game = varied_empire()
        names = lambda **kwargs: [p.name for _, p in colony_rows(game, **kwargs)]
        self.assertEqual(names(), ["Altair Haven", "Earth", "Mars", "Mercury"])
        self.assertEqual(names(filter_by="building"), ["Earth"])
        self.assertEqual(names(filter_by="idle"), ["Altair Haven", "Mars", "Mercury"])
        self.assertEqual(names(filter_by="full"), ["Mercury"])
        self.assertEqual(names(sort_by="population", descending=True), ["Earth", "Altair Haven", "Mars", "Mercury"])
        self.assertEqual(names(sort_by="industry", descending=True), ["Altair Haven", "Earth", "Mars", "Mercury"])
        self.assertEqual(names(sort_by="income", descending=True), ["Earth", "Altair Haven", "Mars", "Mercury"])
        self.assertEqual(names(sort_by="research", descending=True), ["Mercury", "Altair Haven", "Earth", "Mars"])
        self.assertEqual(names(sort_by="slots", descending=True), ["Mercury", "Altair Haven", "Earth", "Mars"])

    def test_reports_do_not_modify_saves_and_refresh_after_completion(self):
        game = varied_empire()
        before = game.to_dict()
        for sort in ("name", "population", "industry", "income", "research", "slots"):
            for filter_by in ("all", "building", "idle", "full"):
                colony_rows(game, filter_by, sort, True)
                summarize_empire(game)
        self.assertEqual(game.to_dict(), before)
        game.advance_turn()
        self.assertEqual(summarize_empire(game).research, 16)
        game.advance_turn()
        self.assertEqual(summarize_empire(game).research, 20)
        self.assertEqual(summarize_empire(game).projects, 0)
        self.assertEqual(summarize_empire(game).idle, 4)
        self.assertEqual(set(game.to_dict()), set(before))


class EmpireInterfaceTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.tmp.name), capture=True)
        self.app.game = new_game(seed=2408)
        self.app.go("galaxy")
        self.app.render()
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

    def row_keys(self):
        return [b.key for b in self.app.buttons if b.key.startswith("empire_colony_")]

    def test_empire_button_and_shortcut_return_to_each_origin(self):
        self.app.game.selected_planet = 2
        for origin in ("galaxy", "system", "planet", "colony"):
            with self.subTest(origin=origin):
                self.app.go(origin)
                self.app.render()
                before = self.app.game.to_dict()
                self.click("open_empire")
                self.assertEqual(self.app.screen, "empire")
                self.key(pg.K_i)
                self.assertEqual(self.app.screen, origin)
                self.key(pg.K_i)
                self.key(pg.K_ESCAPE)
                self.assertEqual(self.app.screen, origin)
                self.assertEqual(self.app.game.to_dict(), before)
        self.key(pg.K_i)
        self.key(pg.K_RETURN)
        self.assertEqual(self.app.screen, "colony")
        self.assertEqual(self.app.game.selected_planet, 2)
        self.click("open_empire")
        self.assertEqual(self.app.screen, "empire")

    def test_sorted_pagination_opens_correct_ids_with_letterboxing(self):
        colonies = [(s, p) for s in self.app.game.systems for p in s.worlds][:12]
        for index, (_, planet) in enumerate(colonies):
            planet.colonized = True
            planet.population = index+1
            planet.name = f"Colony {index:02}"
        self.app.window = pg.display.set_mode((980, 900), pg.RESIZABLE)
        self.app.present()
        self.click("open_empire")
        self.assertEqual(len(self.row_keys()), 5)
        self.click("empire_sort_population")
        expected_system, expected_planet = colonies[11]
        self.assertEqual(self.row_keys()[0], f"empire_colony_{expected_system.id}_{expected_planet.id}")
        selection = self.app.game.selected_system, self.app.game.selected_planet
        self.key(pg.K_PAGEDOWN)
        self.assertEqual(self.app.empire_page, 1)
        self.app.handle_event(pg.event.Event(pg.MOUSEWHEEL, y=-1, x=0))
        self.app.render()
        self.assertEqual(len(self.row_keys()), 2)
        self.key(pg.K_RIGHT)
        self.assertEqual(self.app.empire_page, 2)
        self.assertEqual(selection, (self.app.game.selected_system, self.app.game.selected_planet))
        self.key(pg.K_PAGEUP)
        expected_system, expected_planet = colonies[6]
        self.click(self.row_keys()[0])
        self.assertEqual(self.app.screen, "colony")
        self.assertEqual(self.app.game.selected_system, expected_system.id)
        self.assertEqual(self.app.game.selected_planet, expected_planet.id)
        self.click("open_empire")
        self.assertEqual(self.app.empire_page, 1)
        self.click("empire_sort_population")
        self.assertEqual(self.app.empire_page, 0)
        expected_system, expected_planet = colonies[0]
        self.assertEqual(self.row_keys()[0], f"empire_colony_{expected_system.id}_{expected_planet.id}")

    def test_turn_completion_refreshes_filters_and_autosaves(self):
        earth = self.app.game.systems[0].worlds[2]
        self.app.game.queue_building(0, 2, "factory")
        for _ in range(3):
            self.app.game.advance_turn()
        self.click("open_empire")
        self.click("empire_filter_building")
        self.assertEqual(self.row_keys(), ["empire_colony_0_2"])
        self.click("empire_end_turn")
        self.assertEqual(earth.buildings, ["factory"])
        self.assertEqual(self.row_keys(), [])
        self.assertTrue(any(b.key == "empire_clear_filter" for b in self.app.buttons))
        self.click("empire_clear_filter")
        self.assertEqual(self.row_keys(), ["empire_colony_0_2"])
        self.click("empire_filter_idle")
        self.assertEqual(len(self.row_keys()), 1)
        self.click("empire_filter_full")
        self.assertEqual(self.row_keys(), [])
        restored, _ = self.app.storage.load(self.app.storage.saves_dir/"autosave.json")
        self.assertEqual(restored, self.app.game)

    def test_pause_settings_continue_and_save_load_keep_campaign(self):
        self.app.game.queue_building(0, 2, "mine")
        self.click("open_empire")
        self.click("empire_filter_building")
        self.key(pg.K_e)
        expected = self.app.game.to_dict()
        self.click("empire_pause")
        self.click("settings")
        self.click("settings_done")
        self.click("resume")
        self.assertEqual(self.app.screen, "empire")
        self.assertEqual(self.app.empire_filter, "building")
        self.click("empire_pause")
        self.click("main_menu")
        self.click("resume")
        self.assertEqual(self.app.screen, "empire")
        self.click("empire_save")
        path = next(p for p in self.app.storage.saves_dir.glob("*.json") if p.name != "autosave.json")
        self.app.load_game(path)
        self.key(pg.K_i)
        self.assertEqual(self.app.game.to_dict(), expected)
        self.assertEqual(self.app.empire_filter, "all")
        self.assertEqual(self.row_keys(), ["empire_colony_0_2"])

    def test_empty_empire_and_filtered_page_clamping(self):
        earth = self.app.game.systems[0].worlds[2]
        earth.colonized = False
        earth.population = 0
        self.click("open_empire")
        self.assertEqual(summarize_empire(self.app.game), EmpireSummary())
        self.assertEqual(self.row_keys(), [])
        self.key(pg.K_PAGEDOWN)
        self.key(pg.K_LEFT)
        self.assertEqual(self.app.empire_page, 0)
        self.assertFalse(next(b for b in self.app.buttons if b.key == "empire_next").enabled)
        earth.colonized, earth.population = True, 8
        self.app.empire_page = 50
        self.app.render()
        self.assertEqual(self.app.empire_page, 0)
        self.assertEqual(self.row_keys(), ["empire_colony_0_2"])


if __name__ == "__main__":
    unittest.main()
