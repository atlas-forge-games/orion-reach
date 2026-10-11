"""Saved display preferences, immediate recoloring and campaign independence."""

import json
import os
from pathlib import Path
import tempfile
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame as pg

from orion.empires import PLAYER_PALETTES
from orion.galaxy_fleet_view import fleet_markers, star_label_rects
from orion.galaxy_labels import label_bands
from orion.storage import Storage
from orion.ui import FAINT, MUTED
from scenarios import fixed_start_game as new_game


class ColorPreferenceStorageTests(unittest.TestCase):
    def test_missing_old_and_invalid_preferences_default_to_blue(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(directory)
            self.assertEqual(storage.load_settings()["galaxy_palette"], "blue")
            path = Path(directory)/"settings.json"
            for value in (None, True, 7, [], {}, "", "red", "BLUE"):
                with self.subTest(value=value):
                    payload = {"sound": False, "music_volume": 80}
                    if value is not None:
                        payload["galaxy_palette"] = value
                    path.write_text(json.dumps(payload))
                    before = path.read_bytes()
                    settings = storage.load_settings()
                    self.assertEqual(settings["galaxy_palette"], "blue")
                    self.assertEqual(settings["music_volume"], 80)
                    self.assertFalse(settings["sound"])
                    self.assertEqual(path.read_bytes(), before)


class ColorPreferenceUITests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.directory.name), capture=True)
        self.addCleanup(self.app.audio.close)
        self.app.game = new_game(seed=804, with_guardians=False, with_tombs=False, fog_of_war=True)
        self.app.go("galaxy")
        self.app.present()

    def click(self, key):
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        x, y = button.rect.center
        viewport = self.app.viewport
        pos = (viewport.x + round(x*viewport.w/1440), viewport.y + round(y*viewport.h/900))
        for event in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(event, button=1, pos=pos))
            self.app.render()

    def assert_player_markers(self, expected):
        from orion.app import MAP
        app = self.app
        app.render()
        home = app.game.headquarters()[0]
        x, y = (int(v) for v in app.star_pos(home))
        self.assertEqual(tuple(app.canvas.get_at((x + 10, y)))[:3], expected)
        label = star_label_rects(app, MAP)[home.id]
        pixels = [tuple(app.canvas.get_at((x, y)))[:3]
                  for x in range(label.left, label.right) for y in range(label.top, label.bottom)]
        self.assertIn(expected, pixels)
        own = next(rect for ships, rect, _ in fleet_markers(app, MAP) if ships[0].owner == "player")
        self.assertEqual(tuple(app.canvas.get_at((own.left + 10, own.top)))[:3], expected)

    def test_options_recolor_real_markers_and_survive_restart(self):
        from orion.app import App
        before = self.app.game.to_dict()
        save = self.app.storage.save(self.app.game)
        save_before = save.read_bytes()
        self.assert_player_markers((44, 164, 255))
        self.click("pause")
        self.click("settings")
        self.click("galaxy_palette_turquoise")
        self.assertEqual(self.app.storage.load_settings()["galaxy_palette"], "turquoise")
        selected = next(b for b in self.app.buttons if b.key == "galaxy_palette_turquoise")
        self.assertEqual(selected.style, "tab_active")
        self.click("settings_done")
        self.assertEqual(self.app.screen, "pause")
        self.click("resume")
        self.assert_player_markers((0, 218, 225))
        self.assertEqual(self.app.game.to_dict(), before)
        self.assertEqual(save.read_bytes(), save_before)
        restarted = App(Path(self.directory.name), capture=True)
        self.addCleanup(restarted.audio.close)
        self.assertEqual(restarted.settings["galaxy_palette"], "turquoise")
        self.assertEqual(restarted.empire_color("player"), (0, 218, 225))
        restarted.game, _ = restarted.storage.load(save)
        restarted.go("galaxy")
        restarted.render()
        self.assertEqual(restarted.game.to_dict(), before)

    def test_menu_switches_both_ways_without_changing_pending_fleet_selection(self):
        self.click("map_fleet_1")
        before = self.app.game.to_dict()
        selected = self.app.map_order_ids
        self.click("pause")
        self.click("settings")
        self.click("galaxy_palette_turquoise")
        self.click("galaxy_palette_blue")
        self.click("settings_done")
        self.click("resume")
        self.assertEqual(self.app.settings["galaxy_palette"], "blue")
        self.assertEqual(self.app.storage.load_settings()["galaxy_palette"], "blue")
        self.assertEqual(self.app.map_order_ids, selected)
        self.assertEqual(self.app.game.to_dict(), before)

    def test_schemes_preserve_neutral_labels_fog_and_shared_ownership(self):
        game = self.app.game
        unknown = next(s for s in game.systems if game.known_system(s.id) is None)
        from orion.exploration import record_survey
        neutral = next(s for s in game.systems if s.id != unknown.id and not any(p.colonized for p in s.worlds))
        record_survey(game, neutral.id, "player")
        shared = game.systems[0]
        shared.name = "Oberon"
        for planet, owner in zip(shared.worlds, ("player", "rival", "player", None)):
            planet.owner, planet.colonized = owner, owner is not None
        record_survey(game, shared.id, "player")
        before = game.to_dict()
        for palette in PLAYER_PALETTES:
            self.app.set_galaxy_palette(palette)
            label, bands = label_bands(game, unknown, palette=palette)
            self.assertTrue(label.startswith("(") and label.endswith(")"))
            self.assertEqual(bands[0][2], FAINT)
            self.assertEqual(label_bands(game, neutral, palette=palette)[1][0][2], MUTED)
            label, bands = label_bands(game, shared, palette=palette)
            self.assertEqual(label, "OBERON")
            self.assertEqual([band[2] for band in bands],
                             [self.app.empire_color("player"), self.app.empire_color("rival")])
            self.assertEqual(bands[0][1], bands[1][0])
        self.assertEqual(game.to_dict(), before)

    def test_settings_buttons_fit_small_and_wide_windows(self):
        self.app.go("menu")
        self.click("settings")
        for size in ((980, 900), (1280, 800), (1920, 1080)):
            self.app.window = pg.display.set_mode(size, pg.RESIZABLE)
            self.app.present()
            self.app.render()
            choices = [b for b in self.app.buttons if b.key.startswith("galaxy_palette_")]
            self.assertEqual(len(choices), 2)
            for choice in choices:
                self.assertTrue(self.app.canvas.get_rect().contains(choice.rect))
                self.assertEqual(choice.rect.collidelist([b.rect for b in self.app.buttons if b is not choice]), -1)
            self.click("galaxy_palette_turquoise")
            self.assertEqual(self.app.settings["galaxy_palette"], "turquoise")
            self.click("galaxy_palette_blue")
            self.assertEqual(self.app.settings["galaxy_palette"], "blue")


if __name__ == "__main__":
    unittest.main()
