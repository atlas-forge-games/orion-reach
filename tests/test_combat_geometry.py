"""Multi-cell collision, firing lanes, defense separation and save continuity."""

import copy
import math
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from orion import combat, combat_geometry as geo, flagships
from orion.combat_sandbox import FleetSetup, Scenario, build_game, preset
from orion.designs import ShipDesign
from orion.model import GameState, RuleError, SaveError, Ship
from orion.storage import SAVE_VERSION
from scenarios import empty_fleet_game


def unit(identifier, kind="frigate", owner="player", position=(1, 4), modules=("laser",)):
    design = ShipDesign("design_1", "Geometry test", kind, tuple(modules)) if kind in combat.HULLS else None
    hull = design.hull if design else combat.COMBAT_TYPES[kind].hull
    return combat.CombatShip(identifier, kind, owner, hull, hull, *position,
                             weapon=design.weapon if design else "none", design=design,
                             shields=design.shields if design else 0)


def arena(*ships):
    return SimpleNamespace(combat=combat.CombatState(0, "player", list(ships)),
                           seed=2408, turn=1, owners=("player", "rival"), bonuses_for=lambda owner: {})


def campaign():
    game = empty_fleet_game(seed=2408, fog_of_war=False)
    game.ships = [Ship(1, "battleship", 0), Ship(2, "titan", 0, owner="rival")]
    game.next_ship_id = 3
    game.start_combat(0)
    return game


class FootprintTests(unittest.TestCase):
    def test_hulls_occupy_their_full_rectangles(self):
        for kind, footprint in (("frigate", (1, 1)), ("destroyer", (2, 1)),
                                ("cruiser", (2, 2)), ("battleship", (3, 2)),
                                ("carrier", (3, 2)), ("titan", (3, 3)), ("mothership", (4, 3))):
            with self.subTest(kind=kind):
                ship = unit(1, kind)
                self.assertEqual(geo.size(ship), footprint)
                self.assertEqual(len(set(geo.cells(ship))), math.prod(footprint))

    def test_secondary_cells_and_board_edges_block_movement(self):
        ship = unit(1, "battleship", position=(3, 3))
        blocker = unit(2, position=(6, 4))
        game = arena(ship, blocker, unit(3, owner="rival", position=(18, 4)))
        paths = combat.reachable(game.combat, ship)
        self.assertNotIn((4, 3), paths)
        for path in paths.values():
            for position in path:
                self.assertNotIn(blocker.position, geo.cells(ship, position))
        ship.x = 21
        self.assertNotIn((22, 3), combat.reachable(game.combat, ship))

    def test_large_ship_cannot_clip_a_diagonal_corner(self):
        ship = unit(1, "battleship", position=(3, 3))
        ship.design = None
        game = arena(ship, unit(2, position=(6, 3)), unit(3, owner="rival", position=(18, 4)))
        with patch.dict(combat.MOVEMENT, battleship=1):
            self.assertNotIn((4, 4), combat.reachable(game.combat, ship))
            self.assertIn((3, 4), combat.reachable(game.combat, ship))

    def test_deployment_packs_all_hulls_and_keeps_flagship_centred_vertically(self):
        game = build_game(Scenario(player=FleetSetup(ships={"titan": 8, "battleship": 8, "frigate": 9}),
                                   rival=FleetSetup(ships={"carrier": 12, "destroyer": 7}, bases=3)))
        state = game.combat
        cells = [cell for ship in state.ships for cell in geo.cells(ship)]
        self.assertEqual(len(cells), len(set(cells)))
        self.assertGreater(state.rows, combat.MIN_ROWS)
        for ship in state.ships:
            self.assertTrue(geo.fits(ship, ship.position, set(), combat.BOARD_COLUMNS, state.rows))
        for owner in state.sides:
            self.assertLessEqual(abs(geo.center(flagships.select(state, owner))[1]-(state.rows-1)/2), .5)

    def test_drone_launch_cells_are_outside_entire_carrier(self):
        ship = unit(1, "carrier", position=(5, 4), modules=("drone_bay",))
        game = arena(ship, unit(2, owner="rival", position=(18, 4)))
        cells = game.combat.launch_cells(ship)
        self.assertTrue(cells)
        self.assertFalse(set(cells) & set(geo.cells(ship)))
        ids = combat.launch_drones(game, 1)
        self.assertEqual(len(ids), 2)
        all_cells = [cell for s in game.combat.ships for cell in geo.cells(s)]
        self.assertEqual(len(all_cells), len(set(all_cells)))

    def test_weapon_range_is_measured_between_hull_edges(self):
        ship = unit(1, "battleship", position=(1, 3))
        target = unit(2, "titan", "rival", (8, 3))
        self.assertEqual(geo.distance(ship, target), 5)
        self.assertTrue(combat.in_range(ship, target))


class FiringLaneTests(unittest.TestCase):
    def test_friendly_or_enemy_hull_blocks_beams_and_illegal_fire_is_atomic(self):
        for owner in ("player", "rival"):
            a, b = unit(1), unit(2, owner="rival", position=(7, 4))
            obstacle = unit(3, "cruiser", owner, (4, 3))
            game = arena(a, b, obstacle)
            self.assertFalse(combat.in_range(a, b, game.combat))
            with self.assertRaisesRegex(RuleError, "Line of fire blocked"):
                combat.fire(game, 1, 2)
            self.assertEqual((game.combat.acted, game.combat.shots_fired, b.hull), ([], 0, b.max_hull))
            obstacle.hull = 0
            self.assertTrue(combat.in_range(a, b, game.combat))

    def test_diagonal_corner_contact_and_secondary_cells_block(self):
        a, b = unit(1, position=(1, 1)), unit(2, owner="rival", position=(5, 5))
        blocker = unit(3, position=(3, 2))
        self.assertFalse(geo.clear_line(arena(a, b, blocker).combat, a, b))
        blocker.y = 0
        self.assertTrue(geo.clear_line(arena(a, b, blocker).combat, a, b))

    def test_mixed_volley_launches_only_unblocked_weapons(self):
        a = unit(1, modules=("laser", "torpedo"))
        b = unit(2, owner="rival", position=(7, 4))
        obstacle = unit(3, position=(4, 4))
        game = arena(a, b, obstacle)
        game.combat.accuracy = False
        self.assertEqual(a.volley(b, game.combat), (("torpedo", 10),))
        self.assertEqual(combat.fire(game, 1, 2), 0)
        self.assertEqual(game.combat.shots_fired, 1)
        self.assertEqual(len(game.combat.projectiles), 1)
        self.assertEqual(b.hull, b.max_hull)

    def test_ai_moves_sideways_to_find_a_clear_lane(self):
        a, b = unit(1), unit(2, owner="rival", position=(7, 4))
        obstacle = unit(3, "colony_ship", position=(3, 4))
        game = arena(a, b, obstacle)
        game.combat.acted = [3]
        game.combat.moved = [3]
        self.assertFalse(geo.clear_line(game.combat, a, b))
        event = combat.ai_action(game, "player")
        self.assertEqual(event["kind"], "move")
        self.assertTrue(geo.clear_line(game.combat, a, b))


class DefenseSeparationTests(unittest.TestCase):
    def test_all_projectiles_bypass_shields_and_point_defense_reduces_them(self):
        target = unit(2, owner="rival", modules=("laser", "shield", "point_defense"))
        for weapon in ("torpedo", "missile", "fusion_torpedo", "mirv", "antimatter", "bomber_torpedo"):
            with self.subTest(weapon=weapon):
                hit, absorbed = combat.hit_damage(None, target, weapon, 10)
                self.assertGreater(hit, 0)
                self.assertLess(hit, 10)
                self.assertEqual(absorbed, 0)

    def test_beams_hit_shields_and_ignore_point_defense_including_drone_beams(self):
        target = unit(2, owner="rival", modules=("laser", "shield", "point_defense"))
        for weapon in ("laser", "quantum", "pulse", "drone_beam", "interceptor_pulse"):
            self.assertEqual(combat.hit_damage(None, target, weapon, 5), (0, 5))
        target.shields = 0
        self.assertEqual(combat.hit_damage(None, target, "drone_beam", 5), (5, 0))

    def test_real_projectile_impact_leaves_a_surviving_targets_shields_intact(self):
        a = unit(1, modules=("torpedo",))
        b = unit(2, owner="rival", position=(5, 4), modules=("laser", "shield"))
        game = arena(a, b)
        game.combat.accuracy = False
        combat.fire(game, 1, 2)
        combat.end_turn(game); events = combat.end_turn(game, "rival")
        self.assertEqual((b.hull, b.shields), (b.max_hull-10, b.max_shields))
        self.assertEqual(events[0]["absorbed"], 0)


class SaveAndSimulationTests(unittest.TestCase):
    def test_multicell_campaign_round_trip_and_overlaps_are_validated(self):
        game = campaign()
        self.assertEqual(SAVE_VERSION, 53)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        raw = game.to_dict()
        a, b = raw["combat"]["ships"]
        b.update(x=a["x"]+2, y=a["y"])
        with self.assertRaises(SaveError):
            GameState.from_dict(raw)
        raw = game.to_dict(); raw["combat"]["ships"][0]["x"] = combat.BOARD_COLUMNS-1
        with self.assertRaises(SaveError):
            GameState.from_dict(raw)

    def test_v52_battle_keeps_single_cell_positions_and_resaves_cleanly(self):
        raw = campaign().to_dict()
        raw["combat"].pop("board_rows")
        for ship in raw["combat"]["ships"]:
            ship.pop("large_hull")
        before = copy.deepcopy(raw)
        loaded = GameState.from_dict(raw, version=52)
        self.assertEqual(raw, before)
        self.assertTrue(all(geo.size(ship) == (1, 1) for ship in loaded.combat.ships))
        self.assertEqual(GameState.from_dict(loaded.to_dict()), loaded)

    def test_combined_arms_ai_completes_without_overlapping_hulls(self):
        game = build_game(preset(6))
        for _ in range(5000):
            if game.combat.status != "active":
                break
            combat.ai_action(game, game.combat.active_owner)
            cells = [c for s in game.combat.ships if s.hull for c in geo.cells(s)]
            self.assertEqual(len(cells), len(set(cells)))
        self.assertNotEqual(game.combat.status, "active")


if __name__ == "__main__":
    unittest.main()
