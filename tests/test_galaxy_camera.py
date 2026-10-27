"""Map transforms, zoomed hit testing, view boundaries and safe pan gestures."""

import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame as pg

from orion.app import App, MAP
from orion import black_holes, navigation, sensors
from orion.galaxy_camera import GalaxyCamera, MAX_ZOOM, update_map_input
from orion.galaxy_fleet_view import fleet_markers, guardian_markers, star_label_rects, draw_fuel_range
from orion.model import Ship, new_game as make_game
from orion.sensor_view import contact_markers, draw_coverage
from scenarios import fixed_start_game, use_nearby_system


class CameraTransformTests(unittest.TestCase):
    def test_cursor_anchor_and_world_distances_scale_together(self):
        camera = GalaxyCamera()
        point = (MAP.x+MAP.w*.3, MAP.y+MAP.h*.4)
        world = camera.unproject(point, MAP)
        before = camera.position(.4, .5, MAP)
        other = camera.position(.6, .7, MAP)
        radii = camera.radii(20, MAP)
        camera.zoom_at(3, point, MAP)
        for actual, expected in zip(camera.transform(world, MAP), point):
            self.assertAlmostEqual(actual, expected)
        after, shifted = camera.position(.4, .5, MAP), camera.position(.6, .7, MAP)
        for axis in (0, 1):
            self.assertAlmostEqual(shifted[axis]-after[axis], (other[axis]-before[axis])*camera.zoom)
            self.assertAlmostEqual(camera.radii(20, MAP)[axis], radii[axis]*camera.zoom)

    def test_limits_keep_view_inside_the_full_map_and_fit_restores_it(self):
        camera = GalaxyCamera()
        camera.zoom_at(1000, MAP.center, MAP)
        self.assertEqual(camera.zoom, MAX_ZOOM)
        for dx, dy in ((1e6, 1e6), (-1e6, -1e6), (1e6, -1e6), (-1e6, 1e6)):
            camera.pan(dx, dy, MAP)
            left, top = camera.unproject(MAP.topleft, MAP)
            right, bottom = camera.unproject(MAP.bottomright, MAP)
            self.assertGreaterEqual(left, MAP.left)
            self.assertGreaterEqual(top, MAP.top)
            self.assertLessEqual(right, MAP.right)
            self.assertLessEqual(bottom, MAP.bottom)
        camera.zoom_at(-1000, MAP.center, MAP)
        self.assertEqual(camera, GalaxyCamera())
        camera.pan(100, -100, MAP)
        self.assertEqual(camera, GalaxyCamera())


class CameraInterfaceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.directory.name), capture=True)
        self.addCleanup(self.app.audio.close)
        pg.key.set_mods(0)
        self.app.game = fixed_start_game(seed=2408, with_ai=False, with_guardians=False, fog_of_war=False)
        self.app.go("galaxy")
        self.app.window = pg.display.set_mode((980, 900), pg.RESIZABLE)
        self.app.render()
        self.app.present()

    def window_pos(self, point):
        viewport = self.app.viewport
        return (round(viewport.x+point[0]*viewport.w/1440), round(viewport.y+point[1]*viewport.h/900))

    def move(self, point):
        self.app.handle_event(pg.event.Event(pg.MOUSEMOTION, pos=self.window_pos(point), rel=(0, 0), buttons=(0, 0, 0)))

    def click(self, key):
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, pos=self.window_pos(button.rect.center), button=1))
            self.app.render()

    def key(self, key, mod=0, kind=pg.KEYDOWN):
        self.app.handle_event(pg.event.Event(kind, key=key, mod=mod))
        self.app.render()

    def drag(self, start, end, button=3):
        self.app.handle_event(pg.event.Event(pg.MOUSEBUTTONDOWN, pos=self.window_pos(start), button=button))
        self.move(end)
        self.app.handle_event(pg.event.Event(pg.MOUSEBUTTONUP, pos=self.window_pos(end), button=button))
        self.app.render()

    def test_wheel_anchors_at_cursor_and_side_panel_keeps_its_scrolling(self):
        self.click("map_fleet_1")
        game = self.app.game
        before, orders = game.to_dict(), self.app.map_order_ids
        self.move(MAP.center)
        world = self.app.map_camera.unproject(self.app.mouse, MAP)
        self.app.handle_event(pg.event.Event(pg.MOUSEWHEEL, y=2, x=0))
        self.app.render()
        self.assertGreater(self.app.map_camera.zoom, 1)
        for actual, expected in zip(self.app.map_camera.transform(world, MAP), self.app.mouse):
            self.assertAlmostEqual(actual, expected)
        self.assertTrue(self.app.fleet_popup)
        self.assertEqual(orders, self.app.map_order_ids)
        self.assertEqual(before, game.to_dict())
        camera = copy.copy(self.app.map_camera)
        self.move(self.app.fleet_popup_rect.center)
        with patch.object(self.app, "change_manifest_page") as change:
            self.app.handle_event(pg.event.Event(pg.MOUSEWHEEL, y=-1, x=0))
            change.assert_called_once_with(1)
        self.assertEqual(camera, self.app.map_camera)

    def test_dragging_over_systems_preserves_selection_and_never_issues_an_order(self):
        self.click("map_fleet_1")
        self.app.zoom_map(4)
        self.app.center_map()
        before, orders = self.app.game.to_dict(), self.app.map_order_ids
        for button in (3, 2):
            camera = copy.copy(self.app.map_camera)
            start = self.app.star_pos(self.app.game.systems[0])
            self.drag(start, (start[0]-90, start[1]+65), button)
            self.assertNotEqual(camera, self.app.map_camera)
            self.assertIsNone(self.app.map_drag)
            self.assertEqual(orders, self.app.map_order_ids)
            self.assertEqual(before, self.app.game.to_dict())
        self.assertTrue(self.app.fleet_popup)

    def test_zoomed_fleet_and_destination_clicks_still_make_a_valid_course(self):
        game = self.app.game
        target = use_nearby_system(game, 1)
        self.app.zoom_map(4, self.app.star_pos(game.systems[0]))
        self.app.center_map()
        self.click("map_fleet_1")
        self.click(f"star_{target.id}")
        self.assertTrue(all(s.departure_pending and s.destination == target.id for s in game.ships))
        self.click("star_0")
        self.assertTrue(all(not s.has_course for s in game.ships))

    def test_offscreen_systems_and_fleets_have_no_labels_or_click_targets(self):
        app, game = self.app, self.app.game
        # Classic clamps badges into the viewport; fixed Clean anchors are
        # tested separately, including partial clipping without repositioning.
        app.settings["galaxy_style"] = "classic"
        game.ships = [Ship(i+1, "scout", system.id) for i, system in enumerate(game.systems)]
        game.next_ship_id = len(game.ships)+1
        app.zoom_map(20)
        app.map_camera.center_on(.5, .5, MAP)
        app.render()
        visible = {s.id for s in game.systems if MAP.collidepoint(app.star_pos(s))}
        self.assertLess(len(visible), len(game.systems))
        self.assertEqual(set(star_label_rects(app, MAP)), visible)
        self.assertEqual({s[0].system_id for s, _, _ in fleet_markers(app, MAP)}, visible)
        self.assertEqual({int(b.key.removeprefix("star_")) for b in app.buttons if b.key.startswith("star_")}, visible)
        for b in app.buttons:
            if b.key.startswith(("star_", "map_fleet_")):
                self.assertTrue(MAP.contains(b.rect))
        for label in star_label_rects(app, MAP).values():
            self.assertTrue(MAP.contains(label))

    def test_guardians_and_sensor_contacts_follow_the_camera_and_cull_at_edges(self):
        app = self.app
        app.game = make_game(seed=804, race_id="observer", rival_count=5, with_tombs=False)
        app.fit_map()
        app.go("galaxy")
        self.assertTrue(guardian_markers(app, MAP))
        app.zoom_map(20)
        guardian = app.game.guardians[0]
        star = app.game.systems[guardian.system_id]
        app.map_camera.center_on(star.x, star.y, MAP)
        for threat, badge, anchor in guardian_markers(app, MAP):
            self.assertEqual(anchor, app.star_pos(app.game.systems[threat.system_id]))
            self.assertTrue(MAP.contains(badge))
        contacts = [sensors.Contact("player", 900+i, "rival", s.x, s.y, 1, s.id, 1)
                    for i, s in enumerate(app.game.systems)]
        with patch("orion.sensor_view.map_contacts", return_value=contacts):
            markers = contact_markers(app, MAP)
        self.assertLess(len(markers), len(contacts))
        self.assertTrue(markers)
        for contact, badge, anchor in markers:
            self.assertEqual(anchor, app.map_pos(contact.x, contact.y))
            self.assertTrue(MAP.collidepoint(anchor))
            self.assertTrue(MAP.contains(badge))

    def test_fog_and_hidden_black_holes_stay_private_at_every_zoom(self):
        app = self.app
        app.game = make_game(seed=804, rival_count=2, fog_of_war=True, with_tombs=False)
        app.go("galaxy")
        before = app.game.to_dict()
        for site in app.game.black_holes.sites:
            star = app.game.systems[site.system_id]
            app.zoom_map(20)
            app.map_camera.center_on(star.x, star.y, MAP)
            app.render()
            self.assertFalse(any(b.key == f"star_{star.id}" for b in app.buttons))
            self.assertNotIn(star.id, star_label_rects(app, MAP))
        visible_ships = {ship.id for ship in app.game.visible_ships()}
        self.assertTrue(all(ship.id in visible_ships for ships, _, _ in fleet_markers(app, MAP) for ship in ships))
        self.assertEqual(before, app.game.to_dict())

    def test_transit_positions_and_range_overlays_share_zoomed_geometry(self):
        app, game = self.app, self.app.game
        target = use_nearby_system(game, 1)
        game.send_ship(1, target.id)
        ship = game.ship_at(1)
        ship.departure_pending = False
        ship.turns_remaining -= 1
        app.zoom_map(4)
        nx, ny = navigation.position(game, ship)
        app.map_camera.center_on(nx, ny, MAP)
        anchor = next(a for group, _, a in fleet_markers(app, MAP) if group[0].id == 1)
        self.assertEqual(anchor, app.map_pos(nx, ny))
        app.route_ship_id = 2
        app.show_sensors = True
        home = game.systems[0]
        radius = game.fuel_range(ships=[game.ship_at(app.route_ship_id)])
        with patch("pygame.draw.ellipse") as ellipse:
            draw_fuel_range(app, MAP)
            fuel = ellipse.call_args_list[0].args[2]
        with patch("orion.sensor_view.sensors.centers", return_value=[(home, radius)]), patch("pygame.draw.ellipse") as ellipse:
            draw_coverage(app, MAP)
            coverage = ellipse.call_args_list[0].args[2]
        # The union mask carries a two-pixel clipping margin on each side.
        self.assertEqual(fuel.move(-2, -2), coverage)
        rx, ry = app.map_camera.radii(radius, MAP)
        self.assertEqual(coverage.size, (round(2*rx), round(2*ry)))
        self.assertAlmostEqual(coverage.centerx, app.star_pos(home)[0]-MAP.x, delta=1)
        self.assertAlmostEqual(coverage.centery, app.star_pos(home)[1]-MAP.y, delta=1)

    def test_shift_arrows_pan_while_ordinary_arrows_keep_navigation(self):
        self.app.zoom_map(4)
        selected = self.app.game.selected_system
        before = copy.copy(self.app.map_camera)
        self.key(pg.K_RIGHT, pg.KMOD_SHIFT)
        update_map_input(self.app, .1, MAP)
        self.assertLess(self.app.map_camera.offset_x, before.offset_x)
        self.assertEqual(self.app.game.selected_system, selected)
        self.key(pg.K_DOWN, pg.KMOD_SHIFT)
        self.assertLess(self.app.map_camera.offset_y, before.offset_y)
        self.key(pg.K_LSHIFT, kind=pg.KEYUP)
        stopped = copy.copy(self.app.map_camera)
        update_map_input(self.app, .1, MAP)
        self.assertEqual(self.app.map_camera, stopped)
        self.key(pg.K_RIGHT)
        self.assertNotEqual(self.app.game.selected_system, selected)
        self.assertTrue(MAP.collidepoint(self.app.star_pos(self.app.game.systems[self.app.game.selected_system])))

    def test_navigation_buttons_preserve_game_and_view_survives_screen_visits(self):
        before = self.app.game.to_dict()
        self.click("map_zoom_in")
        self.click("map_zoom_in")
        self.drag(MAP.center, (MAP.centerx+90, MAP.centery+50))
        camera = copy.copy(self.app.map_camera)
        self.app.open_research()
        self.app.close_research()
        self.assertEqual(camera, self.app.map_camera)
        self.click("map_center")
        self.assertTrue(MAP.collidepoint(self.app.star_pos(self.app.game.systems[0])))
        self.click("map_fit")
        self.assertEqual(self.app.map_camera, GalaxyCamera())
        self.assertEqual(before, self.app.game.to_dict())
        self.key(pg.K_PLUS)
        self.key(pg.K_HOME)
        self.assertEqual(self.app.map_camera, GalaxyCamera())

    def test_dialog_focus_loss_and_screen_changes_stop_drag_and_held_keys(self):
        app = self.app
        app.zoom_map(4)
        self.key(pg.K_LEFT, pg.KMOD_SHIFT)
        app.handle_event(pg.event.Event(pg.MOUSEBUTTONDOWN, pos=self.window_pos(MAP.center), button=3))
        app.handle_event(pg.event.Event(pg.WINDOWFOCUSLOST))
        self.assertIsNone(app.map_drag)
        self.assertFalse(app.map_pan_keys)
        stopped = copy.copy(app.map_camera)
        app.confirm("Test", "A modal dialog", "OK", lambda: None)
        self.move(MAP.center)
        app.handle_event(pg.event.Event(pg.MOUSEWHEEL, x=0, y=1))
        self.drag(MAP.center, (MAP.centerx+100, MAP.centery))
        update_map_input(app, .1, MAP)
        self.assertEqual(stopped, app.map_camera)
        app.cancel_dialog()
        app.handle_event(pg.event.Event(pg.MOUSEBUTTONDOWN, pos=self.window_pos(MAP.center), button=2))
        app.go("research")
        self.assertIsNone(app.map_drag)
        self.assertFalse(app.map_pan_keys)

    def test_loading_campaign_resets_only_the_camera_not_gameplay(self):
        app = self.app
        path = app.storage.save(app.game)
        before = app.game.to_dict()
        app.zoom_map(4)
        self.drag(MAP.center, (MAP.centerx+80, MAP.centery+50))
        self.assertNotEqual(app.map_camera, GalaxyCamera())
        app.load_game(path)
        self.assertEqual(app.map_camera, GalaxyCamera())
        self.assertEqual(app.game.to_dict(), before)

    def test_zoomed_drawing_stays_inside_map_and_horizontal_wheel_pans(self):
        app = self.app
        before = app.canvas.copy()
        app.zoom_map(4)
        self.move(MAP.center)
        app.handle_event(pg.event.Event(pg.MOUSEWHEEL, x=1, y=0))
        self.assertLess(app.map_camera.offset_x, 0)
        pg.key.set_mods(pg.KMOD_SHIFT)
        self.addCleanup(pg.key.set_mods, 0)
        app.handle_event(pg.event.Event(pg.MOUSEWHEEL, x=0, y=1))
        self.assertGreater(app.map_camera.offset_y, 0)
        app.render()
        for rect in (pg.Rect(0, 0, 1440, MAP.top), pg.Rect(MAP.right+1, MAP.top, 400, MAP.h),
                     pg.Rect(0, MAP.bottom+1, 1440, 900-MAP.bottom-1)):
            self.assertEqual(pg.image.tobytes(before.subsurface(rect), "RGB"),
                             pg.image.tobytes(app.canvas.subsurface(rect), "RGB"))


if __name__ == "__main__":
    unittest.main()
