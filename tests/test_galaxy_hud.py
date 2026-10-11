"""Resource visibility, bottom navigation and fog-safe ownership labels."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame as pg

from orion.empires import empire_color
from orion.exploration import refresh
from orion.galaxy_labels import LABEL_FAMILY, LABEL_SIZE, draw_system_label, label_bands, system_label
from orion.model import Ship
from orion.ui import font, text_image
from scenarios import fixed_start_game as new_game


class GalaxyHudTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.folder.name), capture=True)
        self.app.game = new_game(seed=2408, with_guardians=False, with_tombs=False,
                                 fog_of_war=False, rival_count=3)
        self.app.go("galaxy")
        self.app.present()

    def click(self, key):
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        x, y = button.rect.center
        view = self.app.viewport
        pos = (view.x+round(x*view.w/1440), view.y+round(y*view.h/900))
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, button=1, pos=pos))
            self.app.render()

    def test_unexplored_names_become_surveyed_and_never_leak_later_ownership(self):
        game = self.app.game = new_game(seed=2408, fog_of_war=True, with_guardians=False)
        target = game.systems[game.opponent.home_system]
        before = game.to_dict()
        self.assertEqual(system_label(game, target), f"({target.name.upper()})")
        self.assertNotEqual(label_bands(game, target)[1][0][2], empire_color("rival"))
        self.assertEqual(game.to_dict(), before)
        scout = Ship(game.next_ship_id, "scout", target.id)
        game.next_ship_id += 1
        game.ships.append(scout)
        refresh(game)
        self.assertEqual(system_label(game, target), target.name.upper())
        expected = label_bands(game, target)
        self.assertEqual(expected[1][0][2], empire_color("rival"))
        scout.system_id = 0
        for planet in target.worlds:
            if planet.colonized:
                planet.owner = None
                planet.colonized = False
                planet.population = 0
        self.assertEqual(label_bands(game, target), expected)
        scout.system_id = target.id
        refresh(game)
        self.assertNotEqual(label_bands(game, target)[1][0][2], empire_color("rival"))

    def test_shared_oberon_splits_whole_letters_and_selected_color_is_preserved(self):
        game = self.app.game
        target = game.systems[0]
        target.name = "Oberon"
        # Two colonies for one owner must not give that owner a larger share.
        for planet, owner in zip(target.worlds, ("player", "rival", "player", None)):
            planet.owner, planet.colonized = owner, owner is not None
        label, bands = label_bands(game, target)
        split, width = font(LABEL_SIZE, LABEL_FAMILY).size("OBE")[0], font(LABEL_SIZE, LABEL_FAMILY).size("OBERON")[0]
        self.assertEqual(label, "OBERON")
        self.assertEqual(bands, ((0, split, empire_color("player")),
                                 (split, width, empire_color("rival"))))
        self.assertEqual(label_bands(game, target, selected=True), (label, bands))
        rendered = pg.Surface((width, 20), pg.SRCALPHA)
        draw_system_label(rendered, game, target, (0, 0))
        for left, right, color in bands:
            pixels = [rendered.get_at((x, y)) for x in range(left, right) for y in range(20)]
            self.assertTrue(any(tuple(pixel[:3]) == color and pixel.a > 0 for pixel in pixels))

    def test_three_owners_and_more_owners_than_letters_all_remain_visible(self):
        game, target = self.app.game, self.app.game.systems[0]
        for planet, owner in zip(target.worlds, ("player", "rival", "rival_2", "rival_3")):
            planet.owner, planet.colonized = owner, True
        target.name = "Sol"
        _, bands = label_bands(game, target)
        self.assertEqual([b[2] for b in bands], [empire_color(o) for o in game.owners])
        self.assertTrue(all(right > left for left, right, color in bands))
        target.worlds[-1].owner, target.worlds[-1].colonized = None, False
        target.name = "Oberon"
        edges = [font(LABEL_SIZE, LABEL_FAMILY).size(target.name.upper()[:index])[0] for index in (0, 2, 4, 6)]
        self.assertEqual([right-left for left, right, _ in label_bands(game, target)[1]],
                         [end-start for start, end in zip(edges, edges[1:])])

    def test_dock_and_top_research_open_each_screen_at_multiple_window_sizes(self):
        routes = {"open_empire": "empire", "open_diplomacy": "diplomacy", "open_research": "research",
                  "open_fleets": "fleets", "open_objectives": "objectives", "open_news": "news", "open_info": "info"}
        for size in ((980, 900), (1280, 800), (1920, 1080)):
            self.app.window = pg.display.set_mode(size, pg.RESIZABLE)
            self.app.present()
            self.app.go("galaxy")
            self.app.render()
            buttons = {b.key: b for b in self.app.buttons}
            self.assertNotIn("save", buttons)
            self.assertNotIn("open_exploration", buttons)
            commands = [buttons[k] for k in (*routes, "pause", "end_turn") if k != "open_research"]
            self.assertEqual(buttons["end_turn"].rect, pg.Rect(1081, 813, 295, 61))
            self.assertLess(buttons["open_research"].rect.bottom, 130)
            self.assertLess(buttons["open_diplomacy"].rect.right, buttons["pause"].rect.left)
            self.assertLess(buttons["open_info"].rect.right, buttons["pause"].rect.left)
            self.assertEqual(buttons["pause"].rect, pg.Rect(496, 813, 132, 61))
            self.assertLess(buttons["pause"].rect.right, buttons["open_fleets"].rect.left)
            for i, button in enumerate(commands):
                self.assertGreaterEqual(button.rect.top, 800)
                self.assertEqual(button.rect.collidelist([b.rect for b in commands[i+1:]]), -1)
            for key, screen in routes.items():
                self.app.go("galaxy")
                self.click(key)
                self.assertEqual(self.app.screen, screen)

    def test_menu_saves_and_resumes_without_changing_a_fleet_order(self):
        self.click("map_fleet_1")
        before = self.app.game.to_dict()
        selected = self.app.map_order_ids
        self.click("pause")
        self.assertEqual(self.app.screen, "pause")
        self.click("save")
        manual = [p for p in self.app.storage.saves_dir.glob("*.json") if p.name != "autosave.json"]
        self.assertEqual(len(manual), 1)
        loaded, _ = self.app.storage.load(manual[0])
        self.assertEqual(loaded.to_dict(), before)
        self.click("resume")
        self.assertEqual(self.app.screen, "galaxy")
        self.assertEqual(self.app.map_order_ids, selected)
        self.assertEqual(self.app.game.to_dict(), before)
        self.click("cancel_fleet_course")
        self.assertFalse(self.app.fleet_popup)

    def test_resource_bar_shows_net_income_and_local_shortage_with_positive_total_food(self):
        game = self.app.game
        home, hungry = game.systems[0].worlds[2], game.systems[0].worlds[3]
        home.farmers, home.scientists = 8, 0
        hungry.colonized, hungry.owner = True, "player"
        hungry.population, hungry.farmers, hungry.scientists = 5, 0, 0
        income, research = game.empire_rates
        game.credits, game.research = 1234, 87
        with patch("orion.ui.text_image", wraps=text_image) as drawn:
            self.app.render()
        values = [call.args[0] for call in drawn.call_args_list]
        self.assertIn("1,234 CR", values)
        self.assertIn("87 RP", values)
        self.assertIn(f"{income:+,} CR net / turn", values)
        self.assertIn(f"{research:+,} RP / turn", values)
        self.assertIn("+9 / turn", values)
        self.assertIn("22 made / 13 used", values)
        self.assertIn("1 local shortage", values)

    def test_unexplored_label_rectangles_include_parentheses_without_overlap(self):
        from orion.app import MAP
        from orion.galaxy_fleet_view import star_label_rects
        self.app.game = new_game(seed=116545103, galaxy_size="Expansive", rival_count=5)
        labels = star_label_rects(self.app, MAP)
        for i, (identifier, rect) in enumerate(labels.items()):
            self.assertEqual(rect.size, font(LABEL_SIZE, LABEL_FAMILY).size(system_label(self.app.game, self.app.game.systems[identifier])))
            self.assertTrue(MAP.contains(rect))
            self.assertEqual(rect.collidelist(list(labels.values())[i+1:]), -1)


if __name__ == "__main__":
    unittest.main()
