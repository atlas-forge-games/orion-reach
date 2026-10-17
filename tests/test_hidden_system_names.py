"""Unknown homeworld names must not escape through map or navigation UI."""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import pygame as pg

from orion import exploration, first_contact, hyperlanes, news, sensors
from orion.galaxy_labels import system_label
from orion.model import GameState, new_game
from orion.ui import text_image


def campaign(**kwargs):
    options = dict(seed=12, race_id="terran", rival_race_id="serevan",
                   random_starts=False, fog_of_war=True, with_guardians=False,
                   with_tombs=False, with_black_holes=False, with_encounters=False,
                   victory_conditions=())
    options.update(kwargs)
    return new_game(**options)


class HiddenNameTests(unittest.TestCase):
    def test_names_are_private_and_catalogue_ids_survive_loading(self):
        game = campaign()
        target = game.systems[game.opponent.home_system]
        alias = game.system_name(target.id)
        self.assertNotEqual(alias, target.name)
        self.assertEqual(game.system_name(target.id, "rival"), target.name)
        first_contact.establish(game, "player", "rival")
        self.assertEqual(game.system_name(target.id), alias)
        hidden = [s for s in game.systems if not game.system_explored(s.id)]
        self.assertEqual(len({game.system_name(s.id) for s in hidden}), len(hidden))
        restored = GameState.from_dict(game.to_dict())
        self.assertEqual(restored.system_name(target.id), alias)
        self.assertEqual(restored.systems[target.id].name, target.name)
        target.name = "AnotherSecretName"
        self.assertEqual(game.system_name(target.id), alias)

    def test_names_unlock_on_arrival_and_remain_after_departure(self):
        game = campaign()
        target = game.systems[game.opponent.home_system]
        scout = game.ship_at(1)
        target.x, target.y = game.systems[0].x+6/140, game.systems[0].y
        game.send_ship(scout.id, target.id)
        while scout.has_course:
            self.assertNotEqual(game.system_name(target.id), target.name)
            with patch("orion.ai.run_ai", return_value=[]):
                game.advance_turn()
        self.assertEqual(system_label(game, target), target.name.upper())
        scout.system_id = 0
        exploration.refresh(game)
        self.assertFalse(game.system_visible(target.id))
        self.assertEqual(game.system_name(target.id), target.name)

    def test_fog_off_and_observer_show_real_names(self):
        for game in (campaign(fog_of_war=False), campaign(race_id="observer", rival_count=2)):
            for star in game.systems:
                self.assertEqual(system_label(game, star), star.name.upper())


class HiddenNameInterfaceTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.folder.name), capture=True)
        self.addCleanup(self.app.audio.close)
        self.app.game = self.game = campaign()
        self.target = self.game.systems[self.game.opponent.home_system]
        self.target.name = "SecretUnionHome"
        self.alias = self.game.system_name(self.target.id)
        self.app.mouse = (-1, -1)
        self.app.keyboard_mode = True
        self.app.go("galaxy")

    def drawn_text(self):
        with patch("orion.ui.text_image", wraps=text_image) as ui, \
                patch("orion.galaxy_labels.text_image", wraps=text_image) as labels:
            self.app.render()
        return "\n".join(str(c.args[0]) for c in ui.call_args_list+labels.call_args_list)

    def assert_hidden(self):
        shown = self.drawn_text()
        self.assertNotIn(self.target.name.casefold(), shown.casefold())
        self.assertIn(self.alias, shown)

    def test_selection_previews_and_queued_courses_never_show_secret_names(self):
        self.app.select_star(self.target.id)
        self.assert_hidden()
        self.app.open_system(self.target.id)
        self.assert_hidden()
        self.app.open_map_fleet(1)
        self.game.selected_system = self.target.id
        self.assert_hidden()
        # Fuel errors must use the same catalogue ID.
        self.target.x, self.target.y = .99, .99
        problem = self.game.fuel_range_error(self.target.id)
        self.assertIn(self.alias, problem)
        self.assertNotIn(self.target.name, problem)
        self.target.x, self.target.y = self.game.systems[0].x+6/140, self.game.systems[0].y
        with patch.object(self.app, "toast") as toast:
            self.app.send_map_fleet(self.target.id)
        message = str(toast.call_args.args[0])
        self.assertIn(self.alias, message)
        self.assertNotIn(self.target.name, message)
        self.assert_hidden()
        self.app.close_fleet_popup()
        self.app.open_fleets()
        self.assert_hidden()

    def test_sensor_contacts_and_news_do_not_disclose_unvisited_names(self):
        contact = sensors.Contact("player", 900, "rival", self.target.x, self.target.y,
                                  self.game.turn, self.target.id, 1)
        self.game.sensor_reports.append(sensors.SensorReport(1, self.game.turn, "player", "rival", self.target.id, None))
        self.app.sensor_contact_id = 900
        with patch("orion.sensors.contacts", return_value=[contact]):
            self.assert_hidden()
        self.app.open_news()
        self.assert_hidden()
        self.assertNotIn(self.target.name, str(news.entries(self.game)))

    def test_hyperlane_research_reveals_destination_coordinates_without_name(self):
        self.app.game = game = campaign(race_id="wanderers", with_ai=False)
        self.target = game.systems[1]
        self.target.name = "SecretUnionHome"
        self.alias = game.system_name(1)
        game.hidden_hyperlanes = [hyperlanes.HiddenHyperlane(0, 1)]
        project = hyperlanes.start(game, 0)
        game.research = project.cost
        message = hyperlanes.invest(game, 0)
        self.assertNotIn(self.target.name, str(message))
        self.assertNotIn(self.target.name, str(news.entries(game)))
        self.app.open_hyperlane(0)
        self.assert_hidden()
        self.app.open_system(1)
        self.assert_hidden()


if __name__ == "__main__":
    unittest.main()
