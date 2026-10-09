"""Direct galaxy-to-planet navigation, paging and survey privacy."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame as pg

from orion.exploration import refresh
from orion.galaxy_system_view import SYSTEM_PANEL
from orion.model import Ship, generate_planets
from scenarios import fixed_start_game as new_game


class GalaxySystemInterfaceTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.tmp.name), capture=True)
        self.app.game = new_game(seed=2408, with_ai=False, with_guardians=False, fog_of_war=False)
        self.app.go("galaxy")
        self.app.window = pg.display.set_mode((980, 900), pg.RESIZABLE)
        self.app.present()

    def click(self, key):
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        x, y = button.rect.center
        v = self.app.viewport
        pos = (v.x+round(x*v.w/1440), v.y+round(y*v.h/900))
        for event in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(event, button=1, pos=pos))
            self.app.render()

    def key(self, key):
        self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=key, mod=0))
        self.app.render()

    def text(self):
        from orion.ui import text_image
        with patch("orion.ui.text_image", wraps=text_image) as drawn:
            self.app.render()
        return "\n".join(str(call.args[0]) for call in drawn.call_args_list)

    def planet_buttons(self):
        self.app.render()
        return [b for b in self.app.buttons if b.key.startswith("galaxy_world_")]

    def test_direct_planet_nested_views_and_return_keep_galaxy_context(self):
        self.click("star_0")
        self.assertEqual(self.app.screen, "galaxy")
        self.assertEqual(len(self.planet_buttons()), 4)
        self.click("galaxy_world_2")
        self.assertEqual(self.app.screen, "planet")
        self.assertEqual(self.app.game.selected_planet, 2)
        self.click("surface_shipyard")
        self.key(pg.K_ESCAPE)
        self.assertEqual(self.app.screen, "planet")
        self.click("planet_return")
        self.assertEqual(self.app.screen, "galaxy")
        self.assertEqual(self.app.focus, "galaxy_world_2")
        self.key(pg.K_RETURN)
        self.assertEqual(self.app.screen, "planet")
        self.key(pg.K_ESCAPE)
        self.assertEqual(self.app.screen, "galaxy")
        self.assertEqual(self.app.game.selected_system, 0)
        self.assertTrue(all(not s.has_course for s in self.app.game.ships))

    def test_full_orbital_view_remains_optional_with_its_own_return_path(self):
        self.click("galaxy_world_2")
        self.click("planet_return")
        self.click("open_system")
        self.assertEqual(self.app.screen, "system")
        self.click("world_3")
        self.click("planet_return")
        self.assertEqual(self.app.screen, "system")
        self.click("system_back")
        self.assertEqual(self.app.screen, "galaxy")

    def test_eight_worlds_page_without_overlap_and_restore_selected_planet(self):
        system = self.app.game.systems[1]
        system.planets = 8
        system.worlds = generate_planets(system, self.app.game.seed)
        self.click("star_1")
        seen = []
        for page in range(2):
            buttons = self.planet_buttons()
            self.assertEqual(len(buttons), 4)
            seen.extend(b.key for b in buttons)
            for index, button in enumerate(buttons):
                self.assertTrue(SYSTEM_PANEL.contains(button.rect))
                self.assertEqual(button.rect.collidelist([b.rect for b in buttons[index+1:]]), -1)
            if not page:
                self.click("galaxy_planets_next")
        self.assertEqual(seen, [f"galaxy_world_{i}" for i in range(8)])
        self.click("galaxy_world_6")
        self.key(pg.K_ESCAPE)
        self.assertEqual(self.app.galaxy_planet_page, 1)
        self.assertEqual(self.app.focus, "galaxy_world_6")
        self.key(pg.K_PAGEUP)
        self.assertEqual(self.app.galaxy_planet_page, 0)
        self.app.mouse = (300, 300)
        self.app.handle_event(pg.event.Event(pg.MOUSEWHEEL, y=-1))
        self.assertEqual(self.app.galaxy_planet_page, 0)
        self.app.mouse = SYSTEM_PANEL.center
        self.app.handle_event(pg.event.Event(pg.MOUSEWHEEL, y=-1))
        self.app.render()
        self.assertEqual(self.app.galaxy_planet_page, 1)
        self.key(pg.K_PAGEDOWN)
        self.assertEqual(self.app.galaxy_planet_page, 1)
        self.click("star_0")
        self.assertEqual(self.app.galaxy_planet_page, 0)
        self.click("star_1")
        self.assertEqual(self.app.galaxy_planet_page, 0)

    def test_unknown_and_empty_systems_have_no_planet_controls(self):
        self.app.game = new_game(seed=2408)
        game = self.app.game
        sid = game.opponent.home_system
        secrets = [p.name for p in game.systems[sid].worlds]
        self.click(f"star_{sid}")
        self.assertEqual(self.planet_buttons(), [])
        drawn = self.text()
        self.assertIn("UNCHARTED", drawn)
        for name in secrets:
            self.assertNotIn(name, drawn)
        self.assertFalse(any(b.key == "galaxy_engage" for b in self.app.buttons))
        self.click("galaxy_build_scout")
        self.assertEqual(self.app.screen, "shipyard")
        self.key(pg.K_ESCAPE)
        self.key(pg.K_ESCAPE)
        self.assertEqual(self.app.screen, "galaxy")
        game.fog_of_war = False
        empty = next(s for s in game.systems if not s.worlds)
        self.click(f"star_{empty.id}")
        self.assertEqual(self.planet_buttons(), [])
        self.assertIn("No planets detected", self.text())
        self.key(pg.K_PAGEDOWN)
        self.assertEqual(self.app.screen, "galaxy")

    def test_stale_panel_uses_survey_population_and_hides_current_fleets(self):
        self.app.game = new_game(seed=2408, with_guardians=False)
        game = self.app.game
        sid, pid = game.opponent.home_system, game.opponent.home_planet
        scout = Ship(game.next_ship_id, "scout", sid)
        game.next_ship_id += 1
        game.ships.append(scout)
        refresh(game)
        scout.system_id = 0
        world = game.planet_at(sid, pid)
        old_name = world.name
        world.name, world.population = "Secret renamed colony", 77
        game.ships.append(Ship(game.next_ship_id, "frigate", sid, owner="rival"))
        game.next_ship_id += 1
        self.click(f"star_{sid}")
        before = game.to_dict()
        drawn = self.text()
        self.assertIn(old_name, drawn)
        self.assertIn("8 B", drawn)
        self.assertIn("Stored survey · Enemy activity unknown", drawn)
        self.assertNotIn("Secret renamed colony", drawn)
        self.assertNotIn("77 B", drawn)
        self.assertNotIn("rival ships", drawn)
        self.assertFalse(any(b.key == "galaxy_engage" for b in self.app.buttons))
        self.assertEqual(game.to_dict(), before)
        self.click(f"galaxy_world_{pid}")
        self.assertEqual(self.app.screen, "planet")
        self.assertFalse(next(b for b in self.app.buttons if b.key == "surface_shipyard").enabled)
        self.key(pg.K_ESCAPE)
        self.assertEqual(self.app.screen, "galaxy")

    def test_fleet_popup_and_course_controls_do_not_leave_hidden_planet_links(self):
        self.click("map_fleet_1")
        self.assertEqual(self.planet_buttons(), [])
        self.click("fleet_popup_close")
        self.assertEqual(len(self.planet_buttons()), 4)
        self.app.plot_course(1)
        self.assertEqual(self.planet_buttons(), [])
        self.assertTrue(any(b.key == "send_course" for b in self.app.buttons))

    def test_guardian_action_requires_confirmation_from_sidebar(self):
        self.app.game = new_game(seed=2408, with_ai=False, fog_of_war=False)
        game = self.app.game
        guardian = game.guardians[0]
        game.ships.append(Ship(game.next_ship_id, "frigate", guardian.system_id))
        game.next_ship_id += 1
        self.click(f"guardian_{guardian.system_id}")
        self.assertEqual(self.app.screen, "galaxy")
        self.assertIn("GUARDED", self.text())
        self.assertIsNone(game.combat)
        self.click("galaxy_engage")
        self.assertIn("guardian", self.app.dialog["title"])
        self.click("dialog_cancel")
        self.assertIsNone(game.combat)
        self.assertEqual(self.app.screen, "galaxy")

    def test_multiple_rival_target_selection_uses_chosen_empire(self):
        self.app.game = new_game(seed=2408, rival_count=2, with_guardians=False, fog_of_war=False)
        game = self.app.game
        for owner in game.owners:
            game.ships.append(Ship(game.next_ship_id, "frigate", 0, owner=owner))
            game.next_ship_id += 1
        self.app.render()
        self.click("galaxy_target_next")
        target = self.app.rival_id
        self.assertEqual(target, list(game.opponents)[1])
        self.click("galaxy_engage")
        self.assertIn(game.empire_name_for(target), self.app.dialog["body"])
        self.click("dialog_ok")
        self.assertEqual(self.app.screen, "combat")
        self.assertEqual(game.combat.enemy("player"), target)


if __name__ == "__main__":
    unittest.main()
