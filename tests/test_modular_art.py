"""Loadouts stay visually consistent without rewriting existing ship snapshots."""

from dataclasses import asdict, replace
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame as pg

from orion import balance, modular_art
from orion.app import App
from orion.combat_view import tactical_sprite
from orion.designs import HULLS, ShipDesign, standard_design
from orion.fleet_art import load_ship_art, ship_sprite
from orion.galaxy_fleet_icons import icon_sprite
from orion.model import GameState, Ship, new_game
from orion.ship_fitting import build_design
from scenarios import research_to


def pixels(surface):
    return pg.image.tobytes(surface, "RGBA")


class ModularArtworkTests(unittest.TestCase):
    def setUp(self):
        previous, configured = balance.active_profile(), balance._configured_path
        self.addCleanup(lambda: balance.activate(previous))
        self.addCleanup(lambda: setattr(balance, "_configured_path", configured))
        balance._configured_path = None
        balance.activate(balance.default_profile())
        pg.init()
        self.addCleanup(pg.quit)

    def test_stock_and_legacy_equipment_render_like_the_equivalent_modular_fit(self):
        for kind in HULLS:
            stock = standard_design(kind)
            legacy = ShipDesign(stock.id, stock.name, kind, stock.modules)
            before = asdict(legacy)
            with self.subTest(kind=kind):
                image = load_ship_art(kind, stock)
                self.assertIsNotNone(image)
                self.assertEqual(pixels(load_ship_art(kind)), pixels(image))
                self.assertEqual(pixels(load_ship_art(kind, legacy)), pixels(image))
                self.assertEqual(asdict(legacy), before)
                self.assertEqual(image.get_at((0, 0)).a, 0)

    def test_actual_mount_choice_changes_designer_combat_and_map_art(self):
        left = build_design("design_1", "Port", "frigate", ["laser"], (("weapon_1", "laser"),))
        right = build_design("design_1", "Starboard", "frigate", ["laser"], (("weapon_4", "laser"),))
        views = (
            lambda d: modular_art.ship_image("frigate", d, cutaway=True),
            lambda d: ship_sprite("frigate", 300, design=d),
            lambda d: tactical_sprite("frigate", (80, 180, 230), 1, 80, (3, 2), d),
            lambda d: icon_sprite((80, 180, 230), heading=90, kind="frigate", design=d),
        )
        for render in views:
            self.assertNotEqual(pixels(render(left)), pixels(render(right)))
            self.assertEqual(pixels(render(left)), pixels(render(replace(left, name="Renamed"))))
        self.assertEqual((left.damage, left.hull, left.movement), (right.damage, right.hull, right.movement))

    def test_closed_internal_bays_and_visible_engine_armor_and_hangar_changes(self):
        shield = build_design("design_1", "Shield", "frigate", ["laser", "shield"])
        repair = build_design("design_2", "Repair", "frigate", ["laser", "damage_control"])
        self.assertEqual(pixels(load_ship_art("frigate", shield)), pixels(load_ship_art("frigate", repair)))
        self.assertNotEqual(pixels(modular_art.ship_image("frigate", shield, cutaway=True)),
                            pixels(modular_art.ship_image("frigate", repair, cutaway=True)))
        base = build_design("design_3", "Base", "frigate", ["laser"])
        for identifier in ("engine", "armor", "reinforced_armor"):
            equipped = build_design("design_4", "Refit", "frigate", ["laser", identifier])
            self.assertNotEqual(pixels(load_ship_art("frigate", base)), pixels(load_ship_art("frigate", equipped)))
        empty = build_design("design_5", "Empty hangars", "carrier", ["laser"])
        drones = build_design("design_6", "Drone carrier", "carrier", ["laser", "drone_bay"])
        self.assertNotEqual(pixels(load_ship_art("carrier", empty)), pixels(load_ship_art("carrier", drones)))

    def test_viewing_an_old_ship_with_excess_internal_equipment_does_not_migrate_it(self):
        game = new_game(seed=14, with_ai=False, with_guardians=False, with_tombs=False,
                        with_black_holes=False, with_encounters=False)
        research_to(game, "radiation_shields", "automated_damage_control")
        legacy = ShipDesign("design_1", "Legacy frigate", "frigate", ("laser", "shield", "damage_control"))
        game.designs = [legacy]
        game.ships = [Ship(1, "frigate", 0, design=legacy)]
        game.next_ship_id = 2
        before = game.to_dict()
        restored = GameState.from_dict(before)
        for design in (legacy, restored.ships[0].design):
            load_ship_art("frigate", design)
            modular_art.ship_image("frigate", design, cutaway=True)
            tactical_sprite("frigate", (80, 180, 230), 1, design=design)
            icon_sprite((80, 180, 230), kind="frigate", design=design)
        self.assertEqual(game.to_dict(), before)
        self.assertEqual(restored.ships[0].design, legacy)
        self.assertEqual(restored.ships[0].design.repair_rate, legacy.repair_rate)

    def test_map_and_combat_draw_built_snapshots_after_library_blueprint_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            app = App(Path(directory), capture=True)
            self.addCleanup(app.audio.close)
            app.game = new_game(seed=14, with_ai=True, with_guardians=False, with_tombs=False,
                                with_black_holes=False, with_encounters=False, fog_of_war=False)
            original = build_design("design_1", "Original", "frigate", ["laser"])
            revised = build_design("design_1", "Revised", "frigate", ["torpedo", "engine"])
            app.game.designs = [revised]
            app.game.ships = [Ship(1, "frigate", 0, design=original), Ship(2, "frigate", 0, owner="rival")]
            app.game.next_ship_id = 3
            from orion.galaxy_fleet_icons import draw_map_ship
            app.go("galaxy")
            with patch("orion.galaxy_fleet_view.draw_map_ship", wraps=draw_map_ship) as draw:
                app.render()
                self.assertTrue(any(call.kwargs.get("design") == original for call in draw.call_args_list))
                self.assertFalse(any(call.kwargs.get("design") == revised for call in draw.call_args_list))
            app.game.start_combat(0)
            app.go("combat")
            with patch("orion.combat_view.tactical_sprite", wraps=tactical_sprite) as draw:
                app.render()
                self.assertTrue(any(call.args[-1] == original for call in draw.call_args_list))
            self.assertEqual(app.game.ships[0].design, original)


if __name__ == "__main__":
    unittest.main()
