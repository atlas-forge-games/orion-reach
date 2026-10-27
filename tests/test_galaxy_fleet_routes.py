"""Active flight paths stay legible without revealing hidden fleet destinations."""

import os
from types import SimpleNamespace
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame as pg

from orion import navigation
from orion.galaxy_camera import GalaxyCamera
from orion.galaxy_fleet_view import draw_clean_fleet_routes, draw_dashed_route
from orion.model import Ship
from orion.sensors import Contact
from scenarios import fixed_start_game as new_game


class FleetRouteTests(unittest.TestCase):
    def setUp(self):
        self.game = new_game(seed=804, with_ai=False, with_guardians=False, fog_of_war=False)
        self.game.systems[0].x, self.game.systems[0].y = .1, .5
        self.game.systems[1].x, self.game.systems[1].y = .9, .5
        self.ship = Ship(1, "frigate", 0)
        self.game.ships = [self.ship]
        self.game.next_ship_id = 2
        self.map = pg.Rect(20, 20, 320, 200)
        self.camera = GalaxyCamera()
        self.app = SimpleNamespace(
            game=self.game, canvas=pg.Surface((360, 240), pg.SRCALPHA),
            settings={"galaxy_style": "clean"},
            map_order_ids=(), route_ship_id=None,
            star_pos=lambda star: self.camera.position(star.x, star.y, self.map),
            empire_color=lambda owner: (50, 180, 250) if owner == "player" else (250, 160, 50),
        )

    def fly(self):
        self.ship.destination = 1
        self.ship.departure_pending = False
        self.ship.travel_total, self.ship.turns_remaining = 4, 2

    def draw(self):
        self.app.canvas.fill((0, 0, 0, 0))
        draw_clean_fleet_routes(self.app, self.map)
        return pg.mask.from_surface(self.app.canvas).count()

    def test_issued_courses_show_immediately_and_rendering_preserves_campaign(self):
        self.assertEqual(self.draw(), 0)
        self.fly()
        self.ship.departure_pending = True
        before = self.game.to_dict()
        self.assertGreater(self.draw(), 0)
        self.assertEqual(self.game.to_dict(), before)
        self.ship.departure_pending = False
        before = self.game.to_dict()
        self.assertGreater(self.draw(), 0)
        self.assertEqual(self.game.to_dict(), before)
        self.app.settings["galaxy_style"] = "classic"
        self.assertEqual(self.draw(), 0)  # Classic keeps its existing route renderer.
        self.app.settings["galaxy_style"] = "clean"
        self.ship.system_id, self.ship.destination = 1, None
        self.assertEqual(self.draw(), 0)

    def test_sensor_only_enemy_flights_do_not_reveal_their_destinations(self):
        self.fly()
        self.ship.owner = "rival"
        self.game.fog_of_war = True
        self.game.sensor_contacts = [Contact("player", 1, "rival", .5, .5,
                                            self.game.turn, 0, 3, count=1, heading=90)]
        self.assertNotIn(self.ship, self.game.visible_ships())
        self.assertEqual(self.draw(), 0)
        self.game.fog_of_war = False
        self.assertGreater(self.draw(), 0)
        self.game.fog_of_war = True
        self.game.race_id = "observer"
        self.assertGreater(self.draw(), 0)

    def test_crossing_routes_remain_visible_with_offscreen_fleets_and_restore_clip(self):
        self.fly()
        self.ship.travel_total, self.ship.turns_remaining = 10, 9
        self.camera.zoom = 4
        for offset in (0, 13):
            self.camera.offset_x = offset
            self.assertFalse(self.map.collidepoint(self.app.star_pos(self.game.systems[0])))
            self.assertFalse(self.map.collidepoint(self.app.star_pos(self.game.systems[1])))
            position = self.camera.position(*navigation.position(self.game, self.ship), self.map)
            self.assertFalse(self.map.collidepoint(position))
            self.assertGreater(self.draw(), 0)
            bounds = self.app.canvas.get_bounding_rect()
            self.assertTrue(self.map.contains(bounds))
            reference = self.app.canvas.copy()
            clip = pg.Rect(111, 50, 111, 130)
            self.app.canvas.fill((0, 0, 0, 0))
            self.app.canvas.set_clip(clip)
            draw_clean_fleet_routes(self.app, self.map)
            self.assertEqual(self.app.canvas.get_clip(), clip)
            self.assertTrue(clip.contains(self.app.canvas.get_bounding_rect()))
            self.assertEqual(pg.image.tobytes(self.app.canvas.subsurface(clip), "RGBA"),
                             pg.image.tobytes(reference.subsurface(clip), "RGBA"))
            self.app.canvas.set_clip(None)

    def test_shared_routes_keep_gaps_and_short_or_diagonal_routes_render_safely(self):
        self.fly()
        self.draw()
        original = pg.image.tobytes(self.app.canvas, "RGBA")
        other = Ship(2, "scout", 1, destination=0, travel_total=8, turns_remaining=1)
        self.game.ships.append(other)
        self.draw()
        self.assertEqual(pg.image.tobytes(self.app.canvas, "RGBA"), original)
        y = round(self.app.star_pos(self.game.systems[0])[1])
        row = [bool(self.app.canvas.get_at((x, y)).a) for x in range(100, 240)]
        self.assertTrue(any(row))
        self.assertFalse(all(row))
        for destination in ((100, 100), (101, 100), (150, 150), (50, 150), (50, 50), (150, 50)):
            self.app.canvas.fill((0, 0, 0, 0))
            draw_dashed_route(self.app.canvas, (30, 108, 150), (100, 100), destination)
            mask = pg.mask.from_surface(self.app.canvas)
            if destination == (100, 100):
                self.assertEqual(mask.count(), 0)
            else:
                self.assertGreater(mask.count(), 0)
                dx, dy = destination[0]-100, destination[1]-100
                for point in mask.outline():
                    self.assertLessEqual(abs((point[0]-100)*dy-(point[1]-100)*dx), 1)


if __name__ == "__main__":
    unittest.main()
