"""Illustrated fleets keep stable docks and follow their true flight geometry."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame as pg
from orion import navigation
from orion.galaxy_fleet_icons import flight_heading, icon_master, icon_sprite
from orion.galaxy_fleet_view import draw_map_fleets, fleet_markers, star_label_rects
from orion.model import Ship
from scenarios import fixed_start_game as new_game


class FleetIconTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App, MAP
        self.map = MAP
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.directory.name), capture=True)
        self.addCleanup(self.app.audio.close)
        self.app.game = new_game(seed=804, with_ai=False, with_guardians=False, fog_of_war=False)
        self.game = self.app.game
        self.game.systems[0].x = self.game.systems[0].y = .5
        self.game.ships = [Ship(10, "frigate", 0), Ship(11, "frigate", 0)]
        self.game.next_ship_id = 12
        self.app.go("galaxy")
        self.app.present()

    def markers(self):
        return {ships[0].id: (rect, anchor) for ships, rect, anchor in fleet_markers(self.app, self.map)}

    def test_art_is_transparent_detailed_bounded_and_has_a_missing_file_fallback(self):
        for habitat in (False, True):
            self.assertIsNotNone(icon_master(habitat))
            for heading in range(0, 360, 45):
                sprite = icon_sprite((44, 164, 255), habitat, heading)
                self.assertEqual(sprite.get_size(), (22, 22))
                self.assertEqual(sprite.get_at((0, 0)).a, 0)
                self.assertTrue(pg.Rect(0, 0, 22, 22).contains(sprite.get_bounding_rect()))
                pixels = {tuple(sprite.get_at((x, y))) for x in range(22) for y in range(22)
                          if sprite.get_at((x, y)).a > 100}
                self.assertGreater(len(pixels), 20)
        icon_sprite.cache_clear()
        with patch("orion.galaxy_fleet_icons.icon_master", return_value=None):
            self.assertGreater(pg.mask.from_surface(icon_sprite((250, 168, 111), False, 90)).count(), 20)
        icon_sprite.cache_clear()

    def test_dock_offset_survives_labels_zoom_and_pan(self):
        home = self.game.systems[0]
        for zoom in (1, 1.25, 2, 4):
            self.app.map_camera.zoom = zoom
            self.app.map_camera.center_on(home.x, home.y, self.map)
            self.app.map_camera.pan(13, -7, self.map)
            before, anchor = self.markers()[10]
            self.assertEqual(before.center, (round(anchor[0]+30), round(anchor[1]+24)))
            home.name = "The Long Named Docking System"
            labels = star_label_rects(self.app, self.map)
            self.assertEqual(self.markers()[10][0], before)
            self.assertEqual(before.collidelist(list(labels.values())), -1)
            self.assertEqual(flight_heading(self.app, self.game.ships[0]), 0)

    def test_existing_slots_stay_put_when_other_fleets_arrive_split_or_depart(self):
        original = self.markers()[10][0]
        self.game.ships.append(Ship(1, "scout", 0, owner="rival"))
        added = self.markers()
        self.assertEqual(added[10][0], original)
        self.assertFalse(added[1][0].colliderect(original))
        self.game.ships.pop()
        self.assertEqual(self.markers()[10][0], original)
        second = self.game.ships[1]
        second.destination, second.departure_pending = 1, True
        second.travel_total = second.turns_remaining = 4
        split = self.markers()
        self.assertEqual(split[10][0], original)
        self.assertFalse(split[11][0].colliderect(original))
        self.game.cancel_departures([second.id])
        self.assertEqual(self.markers()[10][0], original)
        self.game.ships.pop(0)
        self.assertEqual(self.markers()[11][0], original)

    def test_flight_headings_use_screen_geometry_in_all_eight_directions(self):
        ship = self.game.ships[0]
        self.game.ships = [ship]
        ship.destination, ship.departure_pending = 1, False
        ship.travel_total, ship.turns_remaining = 4, 2
        home, destination = self.game.systems[:2]
        for dx, dy, expected in ((0, -80, 0), (80, -80, 45), (80, 0, 90), (80, 80, 135),
                                 (0, 80, 180), (-80, 80, 225), (-80, 0, 270), (-80, -80, 315)):
            destination.x = home.x+dx/(self.map.w-80)
            destination.y = home.y+dy/(self.map.h-64)
            for zoom in (1, 2):
                self.app.map_camera.zoom = zoom
                self.app.map_camera.center_on(home.x, home.y, self.map)
                self.assertAlmostEqual(flight_heading(self.app, ship), expected)
                before = self.game.to_dict()
                rect, anchor = self.markers()[ship.id]
                expected_position = self.app.map_pos(*navigation.position(self.game, ship))
                self.assertEqual(rect.center, tuple(round(v) for v in expected_position))
                with patch("orion.galaxy_fleet_view.draw_map_ship") as draw:
                    draw_map_fleets(self.app, self.map)
                self.assertAlmostEqual(draw.call_args.args[4], expected)
                self.assertEqual(self.game.to_dict(), before)

    def test_arrival_returns_icon_to_the_destination_dock(self):
        ship = self.game.ships[0]
        self.game.ships = [ship]
        destination = self.game.systems[1]
        destination.x, destination.y = .6, .5
        ship.destination, ship.departure_pending = 1, False
        ship.travel_total, ship.turns_remaining = 4, 2
        moving = self.markers()[10][0]
        ship.system_id, ship.destination, ship.turns_remaining = 1, None, 0
        docked, anchor = self.markers()[10]
        self.assertNotEqual(docked, moving)
        self.assertEqual(docked.center, (round(anchor[0]+30), round(anchor[1]+24)))
        self.assertEqual(flight_heading(self.app, ship), 0)

    def test_viewport_clips_the_hit_target_without_sliding_the_dock(self):
        self.app.map_camera.zoom = 4
        home = self.game.systems[0]
        self.app.map_camera.center_on(home.x, home.y, self.map)
        self.app.map_camera.pan(self.map.right-35-self.app.star_pos(home)[0], 0, self.map)
        self.app.render()
        rect, anchor = self.markers()[10]
        self.assertEqual(rect.center, (round(anchor[0]+30), round(anchor[1]+24)))
        self.assertGreater(rect.right, self.map.right)
        button = next(b for b in self.app.buttons if b.key == "map_fleet_10")
        self.assertEqual(button.rect, rect.clip(self.map))
        button.action()
        self.assertTrue(self.app.fleet_popup)


if __name__ == "__main__":
    unittest.main()
