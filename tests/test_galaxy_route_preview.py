"""Mouse previews and immediate course placement through the real galaxy UI."""

import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame as pg
from orion import navigation
from orion.galaxy_fleet_icons import flight_heading
from orion.galaxy_fleet_view import draw_dashed_route, fleet_markers
from orion.model import Ship
from orion.ui import GOLD, RED
from test_galaxy_fleets import fixture


class RoutePreviewTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App, MAP
        self.map = MAP
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.folder.name), capture=True)
        self.addCleanup(self.app.audio.close)
        self.app.window = pg.display.set_mode((1440, 900), pg.RESIZABLE)
        self.app.game = fixture()
        self.app.go("galaxy")
        self.app.present()

    def click(self, key):
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        view = self.app.viewport
        x, y = button.rect.center
        point = (round(view.x+x*view.w/1440), round(view.y+y*view.h/900))
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, button=1, pos=point))
            self.app.render()

    def hover(self, target):
        point = self.app.star_pos(self.app.game.systems[target]) if target is not None else (1040, 100)
        view = self.app.viewport
        position = (round(view.x+point[0]*view.w/1440), round(view.y+point[1]*view.h/900))
        self.app.handle_event(pg.event.Event(pg.MOUSEMOTION, pos=position, rel=(0, 0), buttons=(0, 0, 0)))

    def routes(self):
        with patch("orion.galaxy_fleet_view.draw_dashed_route", wraps=draw_dashed_route) as draw:
            self.app.render()
        return [(call.args[1], call.args[2], call.args[3]) for call in draw.call_args_list]

    def marker(self, identifier):
        return next(rect for ships, rect, _ in fleet_markers(self.app, self.map)
                    if any(ship.id == identifier for ship in ships))

    def assert_on_route(self, identifier):
        ship = next(s for s in self.app.game.ships if s.id == identifier)
        origin = pg.Vector2(self.app.star_pos(self.app.game.systems[ship.system_id]))
        destination = pg.Vector2(self.app.star_pos(self.app.game.systems[ship.destination]))
        offset = pg.Vector2(self.marker(identifier).center)-origin
        vector = destination-origin
        self.assertGreater(offset.dot(vector), 0)
        self.assertLess(offset.dot(vector), vector.length_squared())
        self.assertLessEqual(abs(offset.cross(vector))/vector.length(), 1)
        self.assertAlmostEqual(flight_heading(self.app, ship), math.degrees(math.atan2(vector.x, -vector.y)) % 360)

    def test_hover_previews_reachable_and_unreachable_targets_without_orders(self):
        self.click("map_fleet_1")
        before = self.app.game.to_dict()
        dock = self.marker(1).copy()
        self.hover(1)
        routes = self.routes()
        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0][0], GOLD)
        self.assertIn(self.app.star_pos(self.app.game.systems[1]), routes[0][1:])
        self.assertEqual(self.marker(1), dock)
        self.assertEqual(self.app.game.to_dict(), before)
        far = next(s.id for s in self.app.game.systems if not self.app.game.can_reach(s.id))
        self.hover(far)
        self.assertEqual(self.routes()[0][0], RED)
        self.click(f"star_{far}")
        self.assertTrue(self.app.notice_error)
        self.assertEqual(self.marker(1), dock)
        self.assertTrue(all(not s.has_course for s in self.app.game.ships))
        self.hover(None)
        self.assertEqual(self.routes(), [])
        self.click("fleet_select_none")
        self.hover(1)
        self.assertEqual(self.routes(), [])

    def test_click_places_only_ordered_ships_on_route_and_cancel_returns_them_to_dock(self):
        dock = self.marker(1).copy()
        self.click("map_fleet_1")
        self.click("fleet_select_2")
        self.click("fleet_select_4")
        turn = self.app.game.turn
        self.hover(1)
        self.click("star_1")
        self.assertEqual(self.app.game.turn, turn)
        for identifier in (1, 3):
            ship = self.app.game.ship_at(identifier)
            self.assertTrue(ship.departure_pending)
            self.assertEqual(ship.turns_remaining, ship.travel_total)
            origin = self.app.game.systems[0]
            self.assertEqual(navigation.position(self.app.game, ship), (origin.x, origin.y))
            self.assert_on_route(identifier)
        self.assertEqual(self.marker(2), dock)
        self.assertNotEqual(self.marker(1), dock)
        self.click("fleet_popup_close")
        self.hover(None)
        self.assertEqual(len(self.routes()), 1)
        placed = self.marker(1).copy()
        saved = self.app.storage.saves_dir/"autosave.json"
        self.app.load_game(saved)
        self.app.render()
        self.assertEqual(self.marker(1), placed)
        self.assertEqual(len(self.routes()), 1)
        self.click("map_fleet_1")
        self.click("star_0")
        self.assertTrue(all(not ship.has_course for ship in self.app.game.ships))
        self.assertEqual(self.marker(1), dock)
        self.hover(None)
        self.assertEqual(self.routes(), [])

    def test_hovering_a_new_destination_keeps_the_issued_icon_until_clicked(self):
        self.click("map_fleet_1")
        self.click("star_1")
        issued = self.marker(1).copy()
        before = self.app.game.to_dict()
        self.hover(11)
        routes = self.routes()
        self.assertEqual(len(routes), 2)
        self.assertEqual(sum(color == GOLD for color, _, _ in routes), 1)
        self.assertEqual(self.marker(1), issued)
        self.assertEqual(self.app.game.to_dict(), before)
        self.click("star_11")
        self.assertTrue(all(ship.destination == 11 for ship in self.app.game.ships))
        self.assert_on_route(1)
        self.assertNotEqual(self.marker(1), issued)
        self.assertEqual(len(self.routes()), 1)

    def test_queued_headings_and_positions_follow_all_directions_pan_and_zoom(self):
        ship = self.app.game.ships[0]
        self.app.game.ships = [ship]
        origin, target = self.app.game.systems[:2]
        origin.x = origin.y = .5
        ship.destination, ship.departure_pending = 1, True
        ship.travel_total = ship.turns_remaining = 4
        for dx, dy in ((0, -80), (80, -80), (80, 0), (80, 80),
                       (0, 80), (-80, 80), (-80, 0), (-80, -80)):
            target.x = .5+dx/(self.map.w-80)
            target.y = .5+dy/(self.map.h-64)
            for zoom in (1, 2, 4):
                self.app.map_camera.zoom = zoom
                self.app.map_camera.center_on(.5, .5, self.map)
                self.app.map_camera.pan(13, -7, self.map)
                before = self.app.game.to_dict()
                self.app.render()
                self.assert_on_route(ship.id)
                self.assertEqual(self.app.game.to_dict(), before)
        ship.departure_pending, ship.turns_remaining = False, 2
        rect = self.marker(ship.id)
        position = self.app.map_pos(*navigation.position(self.app.game, ship))
        self.assertEqual(rect.center, tuple(round(v) for v in position))

    def test_enemy_queued_routes_and_headings_stay_hidden_in_fog(self):
        self.app.game = fixture(ai=True)
        game = self.app.game
        game.fog_of_war = True
        enemy = Ship(8, "frigate", 0, owner="rival", destination=1,
                     departure_pending=True, travel_total=4, turns_remaining=4)
        game.ships = [enemy]
        self.assertIn(enemy, game.visible_ships())
        dock = self.marker(enemy.id).copy()
        self.click("map_fleet_8")
        self.assertEqual(self.routes(), [])
        self.assertEqual(flight_heading(self.app, enemy), 0)
        enemy.destination = 11
        self.assertEqual(self.marker(enemy.id), dock)
        self.assertEqual(self.routes(), [])
        game.fog_of_war = False
        self.assertEqual(len(self.routes()), 1)
        self.assert_on_route(enemy.id)


if __name__ == "__main__":
    unittest.main()
