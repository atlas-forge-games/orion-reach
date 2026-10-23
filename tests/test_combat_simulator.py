"""Standalone scenarios, real combat integration, and desktop simulator controls."""

from copy import deepcopy
from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame as pg

from orion import balance, combat, defenses
from orion.combat_sandbox import (MAX_SHIPS, PRESETS, ROUND_LIMIT, FleetSetup, Scenario,
                                  ScenarioError, battle_report, build_game, load_scenario,
                                  preset, save_scenario)
from orion.combat_simulator import CombatSimulator
from orion.designs import ShipDesign
from orion.races import RACES
from orion.storage import Storage


def finish(game, maximum=20000):
    for _ in range(maximum):
        if game.combat.status != "active":
            return battle_report(game)
        if game.combat.round > ROUND_LIMIT:
            raise AssertionError("Scenario did not finish within the round limit")
        game.combat_ai_action()
    raise AssertionError("Scenario exceeded its action limit")


class ScenarioTests(unittest.TestCase):
    def test_every_preset_finishes_using_ordinary_combat_and_preserves_setup(self):
        for index, name in enumerate(PRESETS):
            with self.subTest(name=name):
                scenario = preset(index)
                original = asdict(scenario)
                game = build_game(scenario)
                self.assertIsInstance(game.combat, combat.CombatState)
                finish(game)
                self.assertEqual(asdict(scenario), original)
                self.assertEqual(game.turn, 1)
                self.assertIsNone(game.result)

    def test_seed_and_order_reproduce_outcomes_even_after_a_previous_battle(self):
        scenario = preset(1)
        first = finish(build_game(scenario))
        second = finish(build_game(scenario))
        self.assertEqual(first, second)
        outcomes = []
        for seed in range(5):
            scenario.seed = seed
            outcomes.append(finish(build_game(scenario)))
        self.assertGreater(len({(r["status"], r["rounds"], r["shots"]) for r in outcomes}), 1)

    def test_custom_weapon_shields_and_drone_roles_are_real_equipment(self):
        scenario = Scenario(designs=[ShipDesign("design_1", "Drone experiment", "carrier",
                           ("phased", "hardened_shield", "interceptor_bay", "bomber_bay"))])
        scenario.player.ships = {"design_1": 1}
        game = build_game(scenario)
        carrier = game.combat.fleet("player")[0]
        self.assertEqual(carrier.design, scenario.designs[0])
        self.assertEqual(carrier.shields, scenario.designs[0].shields)
        drones = game.combat_launch_drones(carrier.id, role="bomber")
        self.assertTrue(drones)
        self.assertTrue(all(game.combat.ship(i).drone_role == "bomber" for i in drones))
        self.assertEqual(build_game(scenario).combat.fleet("player")[0].launched_drones, 0)

    def test_each_side_has_independent_research_and_first_move(self):
        scenario = Scenario(first="rival")
        scenario.rival.upgrades = "advanced"
        game = build_game(scenario)
        self.assertEqual(game.combat.active_owner, "rival")
        self.assertEqual(game.bonuses_for("player").get("accuracy", 0), 0)
        self.assertGreater(game.bonuses_for("rival")["accuracy"], 0)
        self.assertEqual(game.combat.fleet("player")[1].weapon, "laser")
        if balance.active_profile()['data']['rules']['ship_scaling']['ENABLED']:
            # Research improves aim; preset hardware is paid for at construction.
            self.assertEqual([s.design.modules for s in game.combat.fleet('player')],
                             [s.design.modules for s in game.combat.fleet('rival')])
        else:
            self.assertIn("quantum", [s.weapon for s in game.combat.fleet("rival")])
        first = game.combat.fleet("rival")[0]
        game.combat_hold(first.id, "rival")
        self.assertIn(first.id, game.combat.acted)

    def test_accuracy_switch_is_local_to_the_battle(self):
        scenario = Scenario(accuracy=False)
        game = build_game(scenario)
        attacker, target = game.combat.fleet("player")[1], game.combat.fleet("rival")[1]
        self.assertEqual(combat.accuracy_breakdown(game, attacker, target, attacker.weapon)["chance"], 100)
        normal = build_game(Scenario())
        attacker, target = normal.combat.fleet("player")[1], normal.combat.fleet("rival")[1]
        self.assertLess(combat.accuracy_breakdown(normal, attacker, target, attacker.weapon)["chance"], 100)

    def test_planetary_defenders_work_without_a_fleet_and_are_restored(self):
        scenario = preset(4)
        scenario.rival.ships = {}
        game = build_game(scenario)
        batteries = [s for s in game.combat.ships if s.kind == "missile_base"]
        self.assertEqual(len(batteries), 2)
        self.assertTrue(all(defenses.base_planet(game, s.id).owner == "rival" for s in batteries))
        finish(game)
        fresh = build_game(scenario)
        self.assertEqual(len(defenses.bases(fresh, 0, "rival")), 2)
        self.assertTrue(all(s.hull == defenses.BASE_HULL for s in fresh.combat.fleet("rival")))

    def test_all_races_and_motherships_can_be_tested_with_safe_retreats(self):
        for race in RACES:
            with self.subTest(race=race):
                scenario = Scenario(player=FleetSetup(race=race, ships={"mothership": 1, "frigate": 1}))
                game = build_game(scenario)
                ark = next(s for s in game.ships if s.kind == "mothership")
                self.assertIsNotNone(ark.habitat)
                self.assertGreater(game.combat.ship(ark.id).shields, 0)
                self.assertIsNotNone(combat.retreat_destination(game))
                game.combat_retreat()
                self.assertEqual(game.combat.status, "player_retreat")
                self.assertEqual(asdict(scenario.player)["ships"], {"mothership": 1, "frigate": 1})

    def test_maximum_fleets_deploy_in_unique_in_bounds_cells(self):
        scenario = Scenario(player=FleetSetup(ships={"frigate": MAX_SHIPS}, bases=3),
                            rival=FleetSetup(ships={"frigate": MAX_SHIPS}, bases=3))
        state = build_game(scenario).combat
        self.assertEqual(len(state.ships), 2*(MAX_SHIPS+3))
        self.assertEqual(len({s.position for s in state.ships}), len(state.ships))
        self.assertTrue(all(0 <= s.x < combat.BOARD_COLUMNS and 0 <= s.y < state.rows for s in state.ships))

    def test_scenario_round_trip_includes_custom_loadouts_and_empty_editable_fleets(self):
        scenario = preset(3)
        scenario.player.ships = {}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"scenario.json"
            save_scenario(path, scenario)
            loaded = load_scenario(path)
            self.assertEqual(asdict(loaded), asdict(scenario))
            with self.assertRaisesRegex(ScenarioError, "each side"):
                build_game(loaded)
            loaded.change("player", "design_2", 3)
            self.assertEqual(len(build_game(loaded).combat.fleet("player")), 3)

    def test_malformed_scenarios_and_illegal_fleets_are_rejected(self):
        changes = [("seed", True), ("seed", -1), ("first", "pirates"), ("accuracy", 1),
                   ("player", {"race": "observer", "upgrades": "none", "ships": {}, "bases": 0}),
                   ("player", {"race": "terran", "upgrades": "none", "ships": {"frigate": 61}, "bases": 0}),
                   ("player", {"race": "terran", "upgrades": "none", "ships": {"made_up": 1}, "bases": 0}),
                   ("player", {"race": "terran", "upgrades": "none", "ships": {"frigate": True}, "bases": 0}),
                   ("designs", [{"id": "design_1", "name": "Illegal", "kind": "frigate", "modules": ["laser"]*20, "fit_version": 2}])]
        for key, value in changes:
            with self.subTest(key=key, value=value):
                payload = asdict(Scenario())
                payload[key] = value
                with self.assertRaises(ScenarioError):
                    Scenario.from_dict(payload)
        unarmed = Scenario(player=FleetSetup(ships={"scout": 1}))
        with self.assertRaisesRegex(ScenarioError, "moving first"):
            build_game(unarmed)
        unarmed.first = "rival"
        self.assertEqual(build_game(unarmed).combat.active_owner, "rival")

    def test_loaded_balance_applies_to_the_simulation(self):
        original = balance.active_profile()
        try:
            profile = deepcopy(original)
            profile['data']['rules']['ship_scaling']['ENABLED'] = False
            profile["data"]["ships"]["frigate"]["hull"] = 37
            balance.activate(profile)
            state = build_game(Scenario()).combat
            self.assertTrue(all(s.hull == 37 for s in state.ships if s.kind == "frigate"))
        finally:
            balance.activate(original)


class SimulatorUITests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.app = CombatSimulator(self.root, capture=True)
        self.app.window = pg.display.set_mode((980, 690), pg.RESIZABLE)
        self.app.present()

    def tearDown(self):
        self.app.audio.close()
        pg.quit()
        self.folder.cleanup()

    def button(self, key):
        self.app.render()
        return next(b for b in self.app.buttons if b.key == key)

    def click(self, key):
        b = self.button(key)
        self.assertTrue(b.enabled, key)
        x, y = b.rect.center
        v = self.app.viewport
        pos = (round(v.x+x*v.w/1440), round(v.y+y*v.h/900))
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, pos=pos, button=1))
            self.app.render()

    def key(self, key, mod=0):
        self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=key, mod=mod))
        self.app.render()

    def tick(self, amount=2):
        self.app.time += amount
        self.app.update_combat()

    def right_click_ship(self, ship, position=None):
        from orion.combat_view import cell_center
        x, y = cell_center(position or ship.position, self.app.combat_camera_row)
        v = self.app.viewport
        pos = (round(v.x+x*v.w/1440), round(v.y+y*v.h/900))
        self.app.handle_event(pg.event.Event(pg.MOUSEBUTTONDOWN, pos=pos, button=3))
        self.app.render()

    def test_right_click_inspects_either_side_without_changing_orders_or_auto_state(self):
        from test_arsenal import duel
        self.app.game = duel(["laser", "torpedo", "shield", "armor", "scanner", "point_defense"])
        self.app.go("combat")
        self.app.combat_auto = True
        self.app.combat_ship_id, self.app.combat_target_id = 1, 2
        self.app.focus = "combat_auto"
        before = self.app.game.to_dict()
        for ship in self.app.game.combat.ships:
            self.right_click_ship(ship)
            self.assertEqual(self.app.dialog["combat_ship_info"], ship.id)
            self.tick(30)
            self.assertEqual(self.app.game.to_dict(), before)
            self.click("dialog_inspect_equipment")
            if ship.id == 1:
                self.click("dialog_inspect_next")
                self.assertEqual(self.app.dialog["inspection_page"], 1)
                self.click("dialog_inspect_previous")
            self.click("dialog_inspect_ordnance")
            self.click("dialog_inspect_weapons")
            self.key(pg.K_ESCAPE)
            self.assertFalse(self.app.dialog)
            self.assertEqual(self.app.focus, "combat_auto")
            self.assertTrue(self.app.combat_auto)
            self.assertFalse(self.app.sim_paused)
            self.assertEqual((self.app.combat_ship_id, self.app.combat_target_id), (1, 2))
            self.assertEqual(self.app.game.to_dict(), before)
        self.tick(.1)  # Closing does not catch up the thirty seconds spent in the panel.
        self.assertEqual(self.app.game.to_dict(), before)

    def test_right_click_moving_ship_pauses_animation_and_shows_real_incoming_ordnance(self):
        from test_arsenal import duel
        self.app.launch(True)
        self.tick()
        effect = self.app.combat_animation
        self.assertEqual(effect.kind, "move")
        effect.elapsed = effect.duration/2
        self.right_click_ship(self.app.game.combat.ship(effect.ship_id), effect.moving_position())
        elapsed, before = effect.elapsed, self.app.game.to_dict()
        self.tick(10)
        self.assertEqual((effect.elapsed, self.app.game.to_dict()), (elapsed, before))
        self.click("dialog_close")
        self.assertIs(self.app.combat_animation, effect)
        self.app.game = duel(["torpedo"])
        self.app.game.combat_fire(1, 2)
        self.app.reset_combat_view()
        self.app.go("combat")
        self.app.sim_paused = True
        self.right_click_ship(self.app.game.combat.ship(2))
        self.click("dialog_inspect_ordnance")
        from orion.combat_inspector import ordnance_rows
        rows = ordnance_rows(self.app.game.combat, self.app.game.combat.ship(2))
        self.assertIn("Incoming from", rows[0][1])
        self.assertEqual(rows[0][3], "~1 round")
        self.click("dialog_close")
        self.assertTrue(self.app.sim_paused)

    def test_scaled_clicks_configure_both_sides_and_launch_real_combat(self):
        self.click("sim_add_player_carrier")
        self.click("sim_add_rival_titan")
        self.click("sim_base_plus_rival")
        self.click("sim_first")
        self.click("sim_upgrades_rival")
        self.click("sim_launch_manual")
        game = self.app.game
        self.assertEqual(self.app.screen, "combat")
        self.assertEqual(game.combat.active_owner, "rival")
        self.assertEqual(len(game.combat.fleet("player")), 5)
        self.assertEqual(len(game.combat.fleet("rival")), 6)
        self.assertGreater(game.bonuses_for("rival")["accuracy"], 0)

    def test_designer_saves_late_game_loadout_and_adds_it_to_both_fleets(self):
        self.click("sim_design_new")
        self.click("design_hull_carrier")
        self.click("design_filter_support")
        self.click("design_add_bomber_bay")
        self.click("design_name")
        self.app.handle_event(pg.event.Event(pg.TEXTINPUT, text="Test carrier"))
        self.key(pg.K_RETURN)
        self.click("design_save")
        self.click("design_add_player")
        self.click("design_add_rival")
        self.click("design_build")
        self.click("sim_launch_manual")
        customs = [s for s in self.app.game.combat.ships if s.design in self.app.scenario.designs]
        self.assertEqual(len(customs), 2)
        self.assertTrue(all("bomber_bay" in s.design.modules for s in customs))
        self.assertEqual(self.app.game.technology.completed, [])

    def test_campaign_shortcuts_do_not_advance_time_or_leave_the_designer(self):
        self.click("sim_design_new")
        before = self.app.game.to_dict()
        for key in (pg.K_e, pg.K_i, pg.K_f, pg.K_d, pg.K_r, pg.K_v, pg.K_x):
            self.key(key)
        self.assertEqual(self.app.screen, "designer")
        self.assertEqual(self.app.game.to_dict(), before)

    def test_auto_pause_speed_takeover_and_rematch_restore_full_fleets(self):
        self.click("sim_launch_auto")
        original = asdict(self.app.game.combat)
        self.tick()
        self.assertIsNotNone(self.app.combat_animation)
        self.key(pg.K_p)
        frozen = self.app.game.to_dict()
        elapsed = self.app.combat_animation.elapsed
        self.tick(30)
        self.assertEqual(self.app.game.to_dict(), frozen)
        self.assertEqual(self.app.combat_animation.elapsed, elapsed)
        self.key(pg.K_p)
        self.click("sim_speed")
        self.assertEqual(self.app.sim_speed, 4)
        self.key(pg.K_a)
        self.tick()
        self.assertFalse(self.app.combat_auto)
        self.assertTrue(self.app.combat_input_ready())
        self.key(pg.K_r)
        self.assertEqual(asdict(self.app.game.combat), original)
        self.assertTrue(self.app.combat_auto)

    def test_ai_result_can_be_replayed_or_return_to_editing(self):
        self.click("sim_launch_auto")
        for _ in range(2000):
            self.tick()
            if self.app.game.combat.status != "active" and self.app.combat_animation is None:
                break
        self.assertNotEqual(self.app.game.combat.status, "active")
        self.assertEqual(self.button("combat_continue").label, "Edit fleets")
        self.click("combat_save")
        self.assertEqual(self.app.game.combat.status, "active")
        self.assertTrue(all(s.hull == s.max_hull for s in self.app.game.combat.ships))
        self.click("sim_setup_back")
        self.assertEqual(self.app.screen, "sim_setup")
        self.assertIsNone(self.app.game.combat)

    def test_saving_during_combat_stores_setup_never_campaign_state(self):
        sentinel = self.root/"saves"/"autosave.json"
        sentinel.parent.mkdir()
        sentinel.write_text("existing campaign", encoding="utf-8")
        with patch.object(Storage, "save", side_effect=AssertionError("Campaign save was called")):
            self.click("sim_launch_auto")
            for _ in range(8):
                self.tick()
            self.key(pg.K_F5)
        files = list(self.app.scenarios_dir.glob("*.json"))
        self.assertEqual(len(files), 1)
        self.assertEqual(asdict(load_scenario(files[0])), asdict(self.app.scenario))
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "existing campaign")
        self.click("sim_setup_back")
        self.click("sim_clear_player")
        self.click("sim_load")
        self.click("sim_load_row_0")
        self.assertEqual(self.app.scenario.player.count, 4)

    def test_invalid_scenario_loading_keeps_existing_setup(self):
        before = asdict(self.app.scenario)
        broken = self.root/"broken.json"
        broken.write_text(json.dumps({"format": "orion-reach", "game": {}}), encoding="utf-8")
        self.app.load_selected_scenario(broken)
        self.assertTrue(self.app.notice_error)
        self.assertEqual(asdict(self.app.scenario), before)

    def test_distinct_scenario_names_do_not_overwrite_each_other(self):
        for name in ("Beams / shields", "Beams : shields"):
            self.app.scenario_name = name
            self.assertTrue(self.app.save_game())
        files = list(self.app.scenarios_dir.glob("*.json"))
        self.assertEqual(len(files), 2)
        self.assertEqual({load_scenario(p).name for p in files}, {"Beams / shields", "Beams : shields"})

    def test_empty_fleet_blocks_launch_bases_allow_it_and_mirror_is_independent(self):
        self.click("sim_clear_player")
        self.assertFalse(self.button("sim_launch_manual").enabled)
        self.click("sim_base_plus_player")
        self.assertTrue(self.button("sim_launch_manual").enabled)
        self.click("sim_mirror")
        self.click("sim_base_plus_player")
        self.assertEqual(self.app.scenario.player.bases, 2)
        self.assertEqual(self.app.scenario.rival.bases, 1)

    def test_round_limit_pauses_without_forcing_a_fake_victory(self):
        self.click("sim_launch_auto")
        self.app.game.combat.round = ROUND_LIMIT+1
        self.tick()
        self.assertTrue(self.app.sim_paused)
        self.assertEqual(self.app.game.combat.status, "active")
        self.key(pg.K_p)
        self.tick()
        self.assertFalse(self.app.sim_paused)


if __name__ == "__main__":
    unittest.main()
