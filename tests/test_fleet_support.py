"""Passive cooperation, counterplay, battle continuity, AI and tactical rendering."""

from copy import deepcopy
from dataclasses import asdict
import math
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame as pg
from orion import ai, balance, combat, combat_geometry as geometry, fleet_support as support
from orion.auto_designs import auto_design
from orion.combat_effects import CombatAnimation
from orion.combat_sandbox import FleetSetup, Scenario, build_game, preset
from orion.combat_simulator import CombatSimulator
from orion.combat_view import CELL, SHIP_LENGTHS, tactical_sprite
from orion.designer_info import module_sections
from orion.designs import HULLS, MODULES, SUPPORT_HULLS, ShipDesign, loadout_error
from orion.model import GameState, Ship
from orion.research import ResearchState, TECHNOLOGIES
from orion.storage import Storage
from test_arsenal import campaign, equip


def unit(identifier, kind="frigate", owner="player", pos=(5, 4), modules=None):
    design = ShipDesign("design_1", "Test "+kind, kind, tuple(modules)) if modules else None
    hull = design.hull if design else combat.COMBAT_TYPES[kind].hull
    return combat.CombatShip(identifier, kind, owner, hull, hull, *pos,
                            weapon=design.weapon if design else "laser", design=design, large_hull=False)


def arena(*ships):
    return SimpleNamespace(combat=combat.CombatState(0, "player", list(ships)),
                           seed=2408, turn=1, owners=("player", "rival"), bonuses_for=lambda owner: {})


class FleetSupportTests(unittest.TestCase):
    def setUp(self):
        previous = balance.active_profile()
        # These isolated aura fixtures intentionally use the original unarmored
        # standard ships. New preset equipment is covered by test_ship_scaling.
        profile = balance.default_profile()
        legacy = balance.legacy_profile()['data']
        for section in ('ships', 'hulls'):
            profile['data'][section] = legacy[section]
        profile['data']['rules']['ship_scaling']['ENABLED'] = False
        balance.activate(profile)
        self.addCleanup(lambda: balance.activate(previous))

    def test_escort_protection_tracks_real_movement_and_survives_spent_actions(self):
        target, escort = unit(1, "battleship"), unit(2, "destroyer", pos=(3, 4))
        enemy = unit(3, owner="rival", pos=(10, 4))
        game = arena(target, escort, enemy)
        self.assertEqual(combat.interception(game.combat, target), 25)
        self.assertEqual(combat.interception(game.combat, escort), 0)
        combat.move(game, 2, 2, 4)
        self.assertEqual(combat.interception(game.combat, target), 0)
        combat.end_turn(game); combat.end_turn(game, "rival")
        combat.move(game, 2, 3, 4)
        combat.hold(game, 2)
        self.assertEqual(combat.interception(game.combat, target), 25)
        escort.hull = 0
        self.assertEqual(combat.interception(game.combat, target), 0)

    def test_enemy_escorts_do_not_help_and_custom_destroyers_need_the_module(self):
        target = unit(1)
        enemy = unit(2, "destroyer", "rival", (5, 5))
        torpedo = unit(3, "destroyer", pos=(5, 3), modules=("torpedo", "engine"))
        game = arena(target, enemy, torpedo)
        self.assertEqual(combat.interception(game.combat, target), 0)
        torpedo.design = ShipDesign("design_1", "Escort", "destroyer", ("laser", "escort_array"))
        self.assertEqual(combat.interception(game.combat, target), 25)

    def test_overlapping_arrays_drones_and_local_flak_respect_caps(self):
        target = unit(1, "battleship", modules=("laser", "flak"))
        ships = [target, unit(2, "destroyer", pos=(5, 3)), unit(3, "destroyer", pos=(5, 5)),
                 unit(4, "destroyer", pos=(4, 4))]
        drone = unit(-1000000, "combat_drone", pos=(6, 4))
        drone.drone_role = "interceptor"
        game = arena(*ships, drone, unit(9, owner="rival", pos=(10, 4)))
        self.assertEqual(support.interception_breakdown(game.combat, target)["shared"], 50)
        self.assertEqual(combat.interception(game.combat, target), 90)
        self.assertEqual(support.screen_sources(game.combat, target), (2, 3, 4, -1000000))
        for ship in ships[1:]:
            ship.hull = 0
        self.assertEqual(combat.interception(game.combat, target), 65)

    def test_screens_reduce_projectiles_and_bombers_but_not_beams(self):
        target = unit(1, "battleship")
        game = arena(target, unit(2, "destroyer", pos=(4, 4)), unit(3, owner="rival"))
        for weapon, expected in (("torpedo", 15), ("bomber_torpedo", 30), ("laser", 20)):
            self.assertEqual(combat.hit_damage(game.combat, target, weapon, 20)[0], expected)
        self.assertGreater(combat.hit_damage(game.combat, target, "mirv", 20)[0],
                           combat.hit_damage(game.combat, target, "torpedo", 20)[0])

    def test_real_fire_and_ai_forecast_use_the_same_screen_without_extra_actions(self):
        attacker = unit(1, "destroyer", pos=(7, 4), modules=("torpedo",))
        target = unit(2, "battleship", "rival", (9, 4))
        escort = unit(3, "destroyer", "rival", (10, 4))
        game = arena(attacker, target, escort)
        game.combat.accuracy = False
        forecast = combat.expected_volley(game, attacker, target)
        before = target.hull
        self.assertEqual(combat.fire(game, 1, 2), 0)
        self.assertEqual(forecast, 8)
        self.assertEqual(game.combat.acted, [1])
        self.assertEqual(game.combat.moved, [])
        combat.end_turn(game)
        combat.end_turn(game, "rival")
        self.assertEqual(before-target.hull, forecast)
        self.assertIn("Escort screen", game.combat.log[-1])

    def test_command_uses_only_strongest_source_and_excludes_self_drones_and_bases(self):
        attacker = unit(1, pos=(5, 4))
        relay = unit(2, "cruiser", pos=(4, 4), modules=("laser", "command_relay"))
        titan = unit(3, "titan", pos=(5, 7))
        enemy = unit(4, owner="rival", pos=(8, 4))
        game = arena(attacker, relay, titan, enemy)
        result = combat.accuracy_breakdown(game, attacker, enemy, "laser")
        self.assertEqual((result["command"], result["chance"]), (12, 84))
        titan.y = 9
        self.assertEqual(combat.accuracy_breakdown(game, attacker, enemy, "laser")["command"], 8)
        relay.hull = 0
        self.assertEqual(combat.accuracy_breakdown(game, attacker, enemy, "laser")["command"], 8)
        titan.x = 14  # Outside innate flagship coverage as well as fitted command.
        self.assertEqual(combat.accuracy_breakdown(game, attacker, enemy, "laser")["command"], 0)
        titan.x = 5
        titan.y = 5
        self.assertEqual(support.strongest(game.combat, titan, "command_accuracy"), 0)
        for kind in ("combat_drone", "missile_base"):
            receiver = unit(5, kind)
            self.assertEqual(support.strongest(game.combat, receiver, "command_accuracy"), 0)

    def test_command_does_not_remove_size_tracking_disadvantage(self):
        titan = unit(1, "titan", modules=("laser",))
        commander = unit(2, "titan", pos=(4, 4))
        target = unit(3, owner="rival", pos=(8, 4))
        game = arena(titan, commander, target)
        values = combat.accuracy_breakdown(game, titan, target, "laser")
        self.assertEqual((values["tracking"], values["command"]), (70, 12))
        self.assertLess(values["chance"], 20)

    def test_ecm_protects_other_allies_only_and_never_stacks(self):
        attacker, target = unit(1), unit(2, owner="rival", pos=(8, 4))
        jammers = [unit(3, "cruiser", "rival", (8, 3), ("laser", "ecm_projector")),
                   unit(4, "cruiser", "rival", (9, 4), ("laser", "ecm_projector"))]
        game = arena(attacker, target, *jammers)
        values = combat.accuracy_breakdown(game, attacker, target, "laser")
        self.assertEqual((values["jamming"], values["formation"], values["chance"]), (8, 5, 59))
        jammers[1].hull = 0
        self.assertEqual(support.strongest(game.combat, jammers[0], "jamming"), 0)
        jammers[0].x = 12
        self.assertEqual(combat.accuracy_breakdown(game, attacker, target, "laser")["jamming"], 0)

    def test_guaranteed_hits_disable_command_and_ecm_but_keep_interception(self):
        game = arena(unit(1), unit(2, "titan", pos=(4, 4)),
                     unit(3, "battleship", "rival", (8, 4)),
                     unit(4, "cruiser", "rival", (8, 5), ("laser", "ecm_projector")),
                     unit(5, "destroyer", "rival", (9, 4)))
        game.combat.accuracy = False
        values = combat.accuracy_breakdown(game, game.combat.ship(1), game.combat.ship(3), "torpedo")
        self.assertEqual((values["chance"], values["command"], values["jamming"]), (100, 0, 0))
        self.assertEqual(combat.hit_damage(game.combat, game.combat.ship(3), "torpedo", 20)[0], 15)

    def test_support_fittings_require_correct_hulls_research_and_single_copies(self):
        for identifier, hulls in SUPPORT_HULLS.items():
            for kind in HULLS:
                error = loadout_error(kind, ("laser", identifier), list(TECHNOLOGIES))
                self.assertEqual(error is None, kind in hulls, (identifier, kind))
            self.assertIsNotNone(loadout_error(hulls[0], ("laser", identifier, identifier)))
            if MODULES[identifier].technology:
                self.assertIsNotNone(loadout_error(hulls[0], ("laser", identifier), []))
        self.assertIsNotNone(loadout_error("titan", ("laser", "command_relay", "flag_bridge")))
        self.assertIsNotNone(loadout_error("destroyer", ("laser", "escort_array", "engine", "scanner")))

    def test_auto_fit_uses_real_support_modules_at_their_full_prices(self):
        for kind, expected in (("destroyer", "escort_array"), ("cruiser", "ecm_projector"), ("titan", "flag_bridge")):
            design = auto_design(kind, tuple(TECHNOLOGIES))
            self.assertIn(expected, design.modules)
            self.assertIsNone(loadout_error(kind, design.modules, list(TECHNOLOGIES)))
            plain = ShipDesign("design_1", "Without support", kind, tuple(m for m in design.modules if m != expected))
            self.assertGreater(design.resource_cost, plain.resource_cost)

    def test_ai_follows_capital_instead_of_chasing_outside_escort_range(self):
        escort = unit(1, "destroyer", pos=(2, 4), modules=("laser", "escort_array"))
        capital = unit(2, "battleship", pos=(6, 4))
        enemy = unit(3, "titan", "rival", (13, 4))
        game = arena(escort, capital, enemy)
        game.combat.acted = [2]; game.combat.moved = [2]
        action = combat.ai_action(game, "player")
        self.assertEqual(action["kind"], "move")
        self.assertLessEqual(math.dist(escort.position, capital.position), 2)
        self.assertEqual(combat.interception(game.combat, capital), 25)
        self.assertEqual(combat.ai_action(game, "player")["kind"], "hold")

    def test_destroying_escort_opens_a_target_and_ai_values_that_change(self):
        attacker = unit(1, "destroyer", modules=("torpedo",))
        target = unit(2, "battleship", "rival", (8, 4))
        escort = unit(3, "destroyer", "rival", (8, 5))
        game = arena(attacker, target, escort)
        protected = combat.expected_volley(game, attacker, target)
        escort.hull = 0
        self.assertGreater(combat.expected_volley(game, attacker, target), protected)

    def test_support_only_formations_still_advance_without_a_follow_loop(self):
        game = arena(unit(1, "cruiser", pos=(1, 3), modules=("laser", "command_relay")),
                     unit(2, "cruiser", pos=(1, 6), modules=("laser", "ecm_projector")),
                     unit(3, "titan", "rival", (15, 4)))
        self.assertEqual(combat.ai_action(game, "player")["kind"], "move")

    def test_balance_v14_migration_preserves_edits_and_adds_support_controls(self):
        old = balance.default_profile()
        old["version"] = 14
        old["data"]["modules"]["laser"]["damage"] = 17
        for identifier in SUPPORT_HULLS:
            del old["data"]["modules"][identifier]
        for entry in old["data"]["modules"].values():
            for key in ("support_range", *support.EFFECTS):
                entry.pop(key)
        del old["data"]["rules"]["fleet_support"]
        original = deepcopy(old)
        migrated = balance.upgrade_profile(old)
        self.assertEqual(old, original)
        self.assertFalse(balance.validate(migrated))
        self.assertEqual(migrated["data"]["modules"]["laser"]["damage"], 17)
        migrated["data"]["modules"]["escort_array"].update(escort_interception=17, support_range=3)
        balance.activate(migrated)
        target = unit(1)
        game = arena(target, unit(2, "destroyer", pos=(2, 4)), unit(3, owner="rival"))
        self.assertEqual(combat.interception(game.combat, target), 17)
        migrated["data"]["modules"]["escort_array"]["support_range"] = 0
        self.assertTrue(balance.validate(migrated))

    def test_save_reload_preserves_designs_orders_and_support_mid_battle(self):
        game = campaign()
        design = equip(game, ("laser", "escort_array"), kind="destroyer")
        game.ships = [Ship(1, "destroyer", 0, design=design), Ship(2, "battleship", 0),
                      Ship(3, "cruiser", 0, owner="rival")]
        game.next_ship_id = 4
        game.start_combat(0)
        game.combat_hold(1)
        before = combat.interception(game.combat, game.combat.ship(2))
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(Path(folder))
            restored, _ = storage.load(storage.save(game))
        self.assertEqual(game, restored)
        self.assertEqual(combat.interception(restored.combat, restored.combat.ship(2)), before)
        self.assertIn(1, restored.combat.acted)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_ai_builds_escorts_and_counts_already_queued_escorts(self):
        game = campaign()
        equip(game, ("laser", "escort_array"), kind="destroyer", owner="rival")
        equip(game, ("laser",), kind="cruiser", owner="rival")
        game.ships = [Ship(1, "battleship", 0, owner="rival")]
        game.next_ship_id = 2
        with patch("orion.ai.projected_income", return_value=100):
            self.assertEqual(ai.warship_choice(game, "rival"), "destroyer")
            system, planet = game.headquarters("rival")
            game.queue_ship(system.id, planet.id, "destroyer", owner="rival")
            self.assertEqual(ai.warship_choice(game, "rival"), "cruiser")
            self.assertIn("escort_array", planet.construction_queue[0].design.modules)

    def test_combined_arms_finishes_deterministically_across_multiple_seeds(self):
        results = []
        for seed in (9, 21, 9):
            scenario = preset(6)
            scenario.seed = seed
            original = asdict(scenario)
            game = build_game(scenario)
            for _ in range(20000):
                if game.combat.status != "active":
                    break
                game.combat_ai_action()
            self.assertNotEqual(game.combat.status, "active")
            self.assertLess(game.combat.round, 100)
            results.append((game.combat.status, game.combat.shots_fired,
                            [(s.id, s.hull) for s in game.combat.ships]))
            self.assertEqual(asdict(scenario), original)
        self.assertEqual(results[0], results[2])


class SupportPresentationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.app = CombatSimulator(Path(self.folder.name), scenario=preset(6), capture=True)
        self.addCleanup(self.folder.cleanup)
        self.addCleanup(pg.quit)
        self.addCleanup(self.app.audio.close)

    def test_distinct_ship_sizes_fit_cells_and_keep_full_click_targets(self):
        widths = [tactical_sprite(kind, (50, 170, 255), 1).get_width()
                  for kind in ("frigate", "destroyer", "cruiser", "battleship", "titan")]
        self.assertEqual(widths, sorted(set(widths)))
        self.assertGreater(widths[-1], widths[0]*1.9)
        for kind in SHIP_LENGTHS:
            sprite = tactical_sprite(kind, (50, 170, 255), -1)
            self.assertLessEqual(sprite.get_width(), CELL)
            self.assertLessEqual(sprite.get_height(), 38)
        self.app.launch(False); self.app.render()
        clicks = [b for b in self.app.buttons if b.key.startswith("combat_ship_")]
        self.assertTrue(any(b.rect.width > CELL*2 for b in clicks))
        for button in clicks:
            ship = self.app.game.combat.ship(int(button.key.removeprefix("combat_ship_")))
            from orion.combat_camera import view, BOARD
            for cell in geometry.cells(ship):
                point = view(self.app).project(cell)
                if BOARD.collidepoint(point):
                    self.assertTrue(button.rect.collidepoint(point))

    def test_manual_shot_has_escort_animation_and_no_new_support_buttons(self):
        self.app.scenario = Scenario(player=FleetSetup(ships={"destroyer": 1, "frigate": 1}),
                                     rival=FleetSetup(ships={"battleship": 1, "destroyer": 1}), accuracy=False)
        self.app.launch(False)
        battle = self.app.game.combat
        shooter, target, escort = battle.ship(1), battle.ship(3), battle.ship(4)
        shooter.x, shooter.y = 8, 4
        target.x, target.y = 10, 4
        escort.x, escort.y = 11, 4
        self.app.combat_ship_id, self.app.combat_target_id = shooter.id, target.id
        self.app.combat_action("fire")
        animation = self.app.combat_animation
        self.assertEqual(target.hull, target.initial_hull)
        self.assertEqual(animation.kind, "launch_projectile")
        self.assertEqual(battle.acted, [shooter.id])
        self.assertEqual(battle.moved, [])
        combat.end_turn(self.app.game)
        flights = combat.end_turn(self.app.game, "rival")
        self.app.after_combat_action({"kind": "end_turn", "flights": flights})
        animation = self.app.combat_animation
        # New preset: two 30-damage torpedoes, 30% local PD + 25% escort.
        damage = 28 if balance.active_profile()['data']['rules']['ship_scaling']['ENABLED'] else 8
        self.assertEqual(target.hull, target.initial_hull-damage)
        self.assertTrue(animation.flights[0]["escorts"])
        animation.elapsed = .45
        self.app.render()
        self.assertFalse(any("battle_plan" in b.key for b in self.app.buttons))
        beam = CombatAnimation.from_action(battle, {"kind": "fire", "ship_id": shooter.id,
            "target_id": target.id, "weapons": ("laser",), "damage": 5, "support_ids": (escort.id,)})
        self.assertFalse(beam.escorts)

    def test_equipment_help_explains_range_restrictions_and_passive_effects(self):
        for identifier, kinds in SUPPORT_HULLS.items():
            info = " ".join(body for _, body in module_sections(kinds[0], identifier, ResearchState()))
            self.assertIn("automatically", info)
            self.assertIn("never its own ship", info)
            self.assertIn("cells", info)


if __name__ == "__main__":
    unittest.main()
