"""Selectable map presentation: no lost fleets, counts only after selection."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame as pg

from orion.exploration import record_survey
from orion.galaxy_fleet_view import draw_map_fleets, fleet_markers, star_label_rects
from orion.galaxy_labels import label_bands
from orion.model import Ship
from orion.sensors import Contact
from orion.storage import Storage
from orion.ui import text
from scenarios import fixed_start_game as new_game, use_nearby_system


class MapStylePreferenceTests(unittest.TestCase):
    def test_old_and_invalid_settings_use_clean_without_rewriting_files(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(directory)
            self.assertEqual(storage.load_settings()["galaxy_style"], "clean")
            path = Path(directory)/"settings.json"
            for value in (None, False, 3, [], {}, "", "CLEAN", "unknown"):
                payload = {"galaxy_palette": "turquoise", "music_volume": 40}
                if value is not None:
                    payload["galaxy_style"] = value
                path.write_text(json.dumps(payload))
                before = path.read_bytes()
                settings = storage.load_settings()
                self.assertEqual(settings["galaxy_style"], "clean")
                self.assertEqual(settings["galaxy_palette"], "turquoise")
                self.assertEqual(settings["music_volume"], 40)
                self.assertEqual(path.read_bytes(), before)


class MapStyleUITests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.directory.name), capture=True)
        self.addCleanup(self.app.audio.close)
        self.app.game = new_game(seed=804, with_ai=False, rival_count=1,
                                 with_guardians=False, fog_of_war=False)
        self.app.game.ships = [Ship(1, "frigate", 0), Ship(2, "frigate", 0),
                               Ship(3, "colony_ship", 0)]
        self.app.game.next_ship_id = 4
        self.app.go("galaxy")
        self.app.present()

    def click(self, key, *, edge=False):
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        x, y = (button.rect.right-3, button.rect.centery) if edge else button.rect.center
        view = self.app.viewport
        pos = (view.x+round(x*view.w/1440), view.y+round(y*view.h/900))
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, button=1, pos=pos))
            self.app.render()

    def test_settings_switch_immediately_persist_and_preserve_campaign(self):
        self.click("map_fleet_1")
        before = self.app.game.to_dict()
        selected = self.app.map_order_ids
        save = self.app.storage.save(self.app.game)
        saved = save.read_bytes()
        self.click("pause")
        self.click("settings")
        self.click("settings_category_interface")
        for size in ((980, 900), (1280, 800), (1920, 1080)):
            self.app.window = pg.display.set_mode(size, pg.RESIZABLE)
            self.app.present()
            for style in ("classic", "clean"):
                self.click("galaxy_style_"+style)
                self.assertEqual(self.app.settings["galaxy_style"], style)
                self.assertEqual(Storage(self.directory.name).load_settings()["galaxy_style"], style)
                choice = next(b for b in self.app.buttons if b.key == "galaxy_style_"+style)
                self.assertEqual(choice.style, "tab_active")
                for button in (b for b in self.app.buttons if b.key.startswith("galaxy_")):
                    self.assertTrue(self.app.canvas.get_rect().contains(button.rect))
                    self.assertEqual(button.rect.collidelist([b.rect for b in self.app.buttons if b is not button]), -1)
        self.click("settings_done")
        self.click("resume")
        self.assertEqual(self.app.map_order_ids, selected)
        self.assertEqual(self.app.game.to_dict(), before)
        self.assertEqual(save.read_bytes(), saved)
        restored, _ = self.app.storage.load(save)
        self.assertEqual(restored.to_dict(), before)

    def test_small_fleet_target_opens_full_count_and_orders_still_work(self):
        from orion.app import MAP
        self.assertEqual(self.app.settings["galaxy_style"], "clean")
        with patch("orion.galaxy_fleet_view.text", wraps=text) as written:
            draw_map_fleets(self.app, MAP)
        self.assertEqual(written.call_count, 0)
        _, target, _ = fleet_markers(self.app, MAP)[0]
        self.assertGreaterEqual(target.w, 22)
        self.click("map_fleet_1", edge=True)
        self.assertTrue(self.app.fleet_popup)
        self.assertEqual(self.app.fleet_selected_ids, {1, 2, 3})
        with patch("orion.galaxy_fleet_view.text", wraps=text) as written:
            self.app.render()
        self.assertIn("3 / 3 selected", [str(call.args[1]) for call in written.call_args_list])
        use_nearby_system(self.app.game, 1)
        self.click("star_1")
        self.assertTrue(all(s.destination == 1 and s.departure_pending for s in self.app.game.ships))

    def test_routes_and_counts_disappear_only_in_clean(self):
        from orion.app import MAP
        use_nearby_system(self.app.game, 1)
        self.app.game.send_ships([1, 2, 3], 1)
        self.app.open_map_fleet(1)
        self.app.render()
        for style in ("clean", "classic"):
            self.app.settings["galaxy_style"] = style
            # Isolate map annotations from strokes inside the ship artwork.
            with patch("orion.galaxy_fleet_view.ship_icon"), \
                 patch("pygame.draw.line") as lines, \
                 patch("orion.galaxy_fleet_view.text") as written:
                draw_map_fleets(self.app, MAP)
            if style == "clean":
                self.assertFalse(lines.called)
                self.assertFalse(written.called)
            else:
                self.assertTrue(lines.called)
                self.assertIn("3", [str(call.args[1]) for call in written.call_args_list])

    def test_dense_map_labels_avoid_fixed_fleet_slots_at_multiple_zooms(self):
        from orion.app import MAP
        self.app.game = new_game(seed=116545103, galaxy_size="Expansive", rival_count=5,
                                 fog_of_war=False, with_guardians=True, with_ai=False)
        game = self.app.game
        game.ships = [Ship(index+1, "scout", system.id, owner=owner)
                      for index, (system, owner) in enumerate((s, o) for s in game.systems
                                                               for o in ("player", "rival"))]
        game.next_ship_id = len(game.ships)+1
        self.app.go("galaxy")
        for zoom in (1.0, 2.0, 4.0):
            self.app.map_camera.zoom = zoom
            self.app.render()
            markers = fleet_markers(self.app, MAP)
            visible = {s.id for s in game.visible_ships()
                       if MAP.collidepoint(self.app.star_pos(game.systems[s.system_id]))}
            shown = {s.id for ships, _, _ in markers for s in ships}
            self.assertTrue(shown)
            self.assertLessEqual(shown, visible)
            labels = list(star_label_rects(self.app, MAP).values())
            per_system = {}
            for ships, rect, _ in markers:
                self.assertTrue(MAP.colliderect(rect))
                self.assertEqual(rect.collidelist(labels), -1)
                siblings = per_system.setdefault(ships[0].system_id, [])
                self.assertEqual(rect.collidelist(siblings), -1)
                siblings.append(rect)

    def test_clean_labels_keep_fog_and_multicolor_ownership(self):
        game = self.app.game = new_game(seed=804, fog_of_war=True, with_guardians=False, with_ai=False)
        unknown = next(s for s in game.systems if not game.system_explored(s.id))
        self.assertEqual(label_bands(game, unknown, style="clean"), ("", ()))
        shared = game.systems[0]
        shared.name = "Oberon"
        for world, owner in zip(shared.worlds, ("player", "rival")):
            world.owner, world.colonized = owner, True
        record_survey(game, shared.id, "player")
        for palette in ("blue", "turquoise"):
            self.app.set_galaxy_palette(palette)
            label, bands = label_bands(game, shared, palette=palette, style="clean")
            self.assertEqual(label, "Oberon")
            self.assertEqual([band[2] for band in bands],
                             [self.app.empire_color("player"), self.app.empire_color("rival")])
            self.assertEqual(bands[0][1], bands[1][0])

    def test_sensor_count_appears_only_after_click(self):
        from orion.app import MAP
        from orion.sensor_view import draw_contacts
        game = self.app.game
        game.fog_of_war = True
        contact = Contact("player", 9001, "rival", .5, .5, game.turn, 0, 2, 7)
        with patch("orion.sensors.contacts", return_value=[contact]):
            with patch("orion.sensor_view.text", wraps=text) as written:
                draw_contacts(self.app, MAP)
            self.assertFalse(written.called)
            self.click("sensor_contact_9001")
            self.assertEqual(self.app.sensor_contact_id, 9001)
            with patch("orion.sensor_view.text", wraps=text) as written:
                self.app.render()
            self.assertIn("FLEET SIZE: 7", [str(call.args[1]) for call in written.call_args_list])

    def test_hyperlane_connections_hidden_but_known_portals_remain(self):
        from orion.app import MAP
        from orion.hyperlane_art import draw_network
        from orion.hyperlanes import HyperlaneProject
        project = HyperlaneProject("player", 0, 1, 300)
        with patch("orion.hyperlane_art.hyperlanes.visible_routes", return_value=[project]), \
             patch("orion.hyperlane_art.draw_portal") as portals, \
             patch("pygame.draw.lines") as lines:
            draw_network(self.app, MAP)
        self.assertFalse(lines.called)
        self.assertEqual(portals.call_count, 2)


if __name__ == "__main__":
    unittest.main()
