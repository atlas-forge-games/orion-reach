"""Live strategic chart geometry, condensed resource reports and panel interactions."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame as pg
from orion import black_holes
from orion.app import App
from orion.galaxy_layout import GalaxyLayout
from orion.model import new_game
from orion.ui import text
from scenarios import fixed_start_game, place_near, research_to


class GalaxyWorkspaceTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(folder.name), capture=True)
        self.addCleanup(self.app.audio.close)
        self.app.settings.update(autosave=False, animated_background=False)
        self.app.window = pg.display.set_mode((1844, 952))
        self.app.game = fixed_start_game(seed=2408, with_ai=False, with_guardians=False)
        self.app.go("galaxy")
        self.frame()

    def frame(self):
        self.app.render()
        self.app.present()

    def click(self, key):
        app = self.app
        rect = next(b.rect for b in app.buttons if b.key == key and b.enabled)
        app.display_view.ensure_visible(rect)
        self.frame()
        point = app.window_pos(rect.center)
        self.assertTrue(app.window.get_rect().collidepoint(point), key)
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            app.handle_event(pg.event.Event(kind, pos=point, button=1))
        self.frame()

    def test_extra_width_goes_to_the_chart_and_all_controls_fit(self):
        small = GalaxyLayout.fit((1440, 900))
        wide = GalaxyLayout.fit((1800, 900))
        self.assertEqual(wide.inspector.w, small.inspector.w)
        self.assertEqual(wide.chart.w-small.chart.w, 360)
        for size in ((1800, 900), (1440, 900), (1150, 680), (823, 514), (548, 1100)):
            for collapsed in (True, False):
                for subview in (True, False):
                    with self.subTest(size=size, collapsed=collapsed, subview=subview):
                        layout = GalaxyLayout.fit(size, collapsed=collapsed, system_view=subview)
                        frame = pg.Rect((0, 0), layout.size)
                        pieces = [layout.identity, *layout.cards, layout.chart, *layout.commands, layout.end_turn]
                        pieces += [r for r in (layout.inspector, layout.galaxy_link) if r]
                        for index, r in enumerate(pieces):
                            self.assertTrue(frame.contains(r))
                            self.assertEqual(r.collidelist(pieces[index+1:]), -1)
                        corners = [layout.camera_tools, layout.sensors, layout.panel_toggle]
                        for index, r in enumerate(corners):
                            self.assertTrue(layout.chart.contains(r))
                            self.assertEqual(r.collidelist(corners[index+1:]), -1)
                        self.assertEqual(layout.end_turn.right, frame.right-18)
        pixels = self.app.canvas.rect(self.app.map_rect)
        self.assertGreater(pixels.w, 1400)
        self.assertGreater(pixels.h, 750)

    def test_each_resource_draws_three_lines_and_opens_its_live_detail(self):
        app = self.app
        with patch("orion.galaxy_hud.text", wraps=text) as drawn:
            self.frame()
        for card in app.galaxy_layout.cards:
            lines = [call.args for call in drawn.call_args_list if card.collidepoint(call.args[2])]
            self.assertEqual(len(lines), 3)
            self.assertEqual(len({args[2][1] for args in lines}), 3)
        before = app.game.to_dict()
        for key, phrase in (("credit_report", "Upkeep"), ("resource_report", "after fuel"), ("food_report", "supplied locally")):
            self.click(key)
            self.assertIn(phrase, app.dialog["body"])
            self.click("dialog_cancel")
            self.assertEqual(app.focus, key)
        self.assertEqual(app.game.to_dict(), before)
        self.click("open_info")
        with patch("orion.encyclopedia_view.text", wraps=text) as guide:
            self.frame()
        self.assertIn(f"{app.game.galaxy_size} galaxy · Seed {app.game.seed}", [c.args[1] for c in guide.call_args_list])

    def test_zoomed_resize_and_folding_preserve_center_selection_and_orders(self):
        app, game = self.app, self.app.game
        self.click("map_fleet_1")
        app.zoom_map(3)
        app.map_camera.center_on(.5,.5,app.map_rect)
        app.map_camera.pan(31, -16, app.map_rect)
        def center_offset():
            scale = app.map_camera.fit_scale(app.map_rect)*app.map_camera.zoom
            return (app.map_camera.offset_x/scale, app.map_camera.offset_y/scale)
        offset, zoom, orders, before = center_offset(), app.map_camera.zoom, app.map_order_ids, game.to_dict()
        width = app.map_rect.w
        self.click("toggle_inspector")
        self.assertGreater(app.map_rect.w, width)
        self.assertIsNone(app.galaxy_layout.inspector)
        self.assertFalse(any(b.key.startswith(("galaxy_world_", "fleet_select_")) for b in app.buttons))
        app.window = pg.display.set_mode((1600, 900))
        self.frame()
        self.click("toggle_inspector")
        for previous, actual in zip(offset, center_offset()):
            self.assertAlmostEqual(previous, actual)
        self.assertEqual(app.map_camera.zoom, zoom)
        self.assertEqual(app.map_order_ids, orders)
        self.assertEqual(game.to_dict(), before)
        self.assertTrue(app.galaxy_layout.inspector.contains(next(b.rect for b in app.buttons if b.key=="fleet_select_1")))
        self.click("toggle_inspector")
        app.fit_map()
        place_near(game, 1)
        self.frame()
        self.click("star_1")
        self.assertTrue(all(game.ship_at(s).destination==1 for s in orders))

    def test_stars_in_the_gap_between_floating_controls_remain_clickable(self):
        app, game = self.app, self.app.game
        r = app.map_rect
        app.zoom_map(3)
        target = game.systems[1]
        target.x = target.y = .5
        x, y = app.star_pos(target)
        app.map_camera.pan(r.centerx-x, r.y+24-y, r)
        self.frame()
        self.assertTrue(app.map_background_at(app.star_pos(target)))
        self.click("star_1")
        self.assertEqual(game.selected_system, 1)
        self.assertFalse(app.map_background_at(app.galaxy_layout.camera_tools.center))

    def test_fatal_approach_is_visible_and_requires_confirmation_when_folded(self):
        app = self.app
        game = app.game = new_game(seed=42, with_ai=False, with_tombs=False, random_starts=False,
                                   with_guardians=False, with_black_holes=True)
        research_to(game, "gravitic_mapping")
        site = game.black_holes.sites[0]
        place_near(game, site.system_id)
        self.assertTrue(black_holes.risk(game,site.system_id))
        app.go("galaxy")
        self.frame()
        self.click("map_fleet_1")
        self.click("toggle_inspector")
        app.mouse = app.star_pos(game.systems[site.system_id])
        app.keyboard_mode = False
        with patch("orion.app.text", wraps=text) as drawn:
            self.frame()
        self.assertTrue(any("Fatal approach" in str(c.args[1]) for c in drawn.call_args_list))
        self.click(f"star_{site.system_id}")
        self.assertIn("every ship", app.dialog["body"])
        self.click("dialog_cancel")
        self.assertTrue(all(not ship.has_course for ship in game.ships))

    def test_observer_black_hole_keeps_both_campaign_actions(self):
        app = self.app
        app.game = new_game(seed=42, race_id="observer", rival_count=3)
        app.game.selected_system = app.game.black_holes.sites[0].system_id
        app.go("system")
        self.frame()
        before = app.game.to_dict()
        self.assertIn("black_hole_guide", [b.key for b in app.buttons])
        self.click("toggle_inspector")
        self.assertIsNone(app.galaxy_layout.inspector)
        self.assertNotIn("sensor_overlay", [b.key for b in app.buttons])
        self.assertEqual(sum(b.key=="end_turn" for b in app.buttons), 1)
        self.click("toggle_inspector")
        self.assertEqual(app.game.to_dict(), before)
        self.click("galaxy_map")
        self.assertEqual(app.screen, "galaxy")
        self.assertFalse(any(b.key=="galaxy_map" for b in app.buttons))
