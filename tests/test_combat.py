"""Tactical rules, strategic consequences, save continuity and real UI controls."""

import json
import os
import tempfile
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame as pg

from orion.combat import ai_action, retreat_destination
from orion.model import GameState, PLAYER, RIVAL, RuleError, SaveError, Ship
from scenarios import empty_fleet_game as new_game
from functools import partial

# Preserve these pre-exploration scenarios; fog-on rules have their own tests.
new_game = partial(new_game, fog_of_war=False)
from orion.storage import Storage, SAVE_VERSION


def encounter(own=("frigate",), enemy=("frigate",), start=True):
    game = new_game(seed=2408)
    rows = [(kind, PLAYER) for kind in own]+[(kind, RIVAL) for kind in enemy]
    game.ships = [Ship(i, kind, 0, owner=owner) for i, (kind, owner) in enumerate(rows, 1)]
    game.next_ship_id = len(rows)+1
    if start:
        game.start_combat(0)
    return game


def player_action(game):
    if any(s.damage for s in game.combat.fleet(PLAYER)):
        ai_action(game, PLAYER)
    else:
        ready = game.combat.ready(PLAYER)
        if ready:
            game.combat_hold(ready[0].id)
        else:
            game.combat_end_turn()


def enemy_turn(game):
    for _ in range(100):
        if game.combat.status != "active" or game.combat.active_owner != RIVAL:
            return
        game.combat_ai_action()
    raise AssertionError("Enemy turn did not terminate")


def resolve_battle(game):
    for _ in range(300):
        if game.combat.status != "active":
            return
        if game.combat.active_owner == PLAYER:
            player_action(game)
        else:
            game.combat_ai_action()
    raise AssertionError("Battle did not terminate")


class CombatRulesTests(unittest.TestCase):
    def test_frigates_use_real_credits_work_discounts_and_no_building_slot(self):
        game = new_game(seed=2408, with_ai=False)
        earth = game.planet_at(0, 2)
        game.queue_ship(0, 2, "frigate")
        self.assertEqual((game.credits, earth.used_slots, game.queue_estimates(earth)), (60, 0, [6]))
        for _ in range(6):
            game.advance_turn()
        ship = game.ships[0]
        self.assertEqual((ship.kind, ship.hull, ship.damage, ship.owner), ("frigate", 20, 5, PLAYER))
        self.assertEqual(earth.buildings, [])
        game.research = 140
        game.choose_research("civil_engineering")
        game.choose_research("orbital_assembly")
        self.assertEqual(game.project_price("frigate"), 48)
        before = game.credits
        game.queue_ship(0, 2, "frigate")
        self.assertEqual(game.credits, before-48)
        self.assertEqual(game.cancel_construction(0, 2, 0), 48)

    def test_engagement_is_atomic_and_breaks_treaties_only_when_started(self):
        game = encounter(start=False)
        game.diplomacy.relations = 65
        game.diplomacy.trade_active = game.diplomacy.research_active = True
        for system_id in (1, -1, True, "0", None):
            before = game.to_dict()
            with self.assertRaises(RuleError):
                game.start_combat(system_id)
            self.assertEqual(game.to_dict(), before)
        game.start_combat(0)
        self.assertEqual((game.diplomacy.relations, game.diplomatic_yields()), (-100, (0, 0)))
        self.assertFalse(game.diplomacy.trade_active or game.diplomacy.research_active)
        self.assertEqual(game.combat.active_owner, PLAYER)
        self.assertEqual(game.turn, 1)
        with self.assertRaises(RuleError):
            game.start_combat(0)
        unarmed = encounter(own=("colony_ship",), start=False)
        self.assertIn("unarmed", unarmed.engagement_error(0))
        with self.assertRaises(RuleError):
            unarmed.start_combat(0)
        unarmed.send_ship(1, 1)
        self.assertIsNone(unarmed.engagement_error(0, RIVAL))  # It has not departed yet.
        unarmed.ship_at(1).departure_pending = False
        self.assertIn("orbit", unarmed.engagement_error(0, RIVAL))

    def test_fixed_damage_side_turns_prevent_duplicate_or_friendly_attacks(self):
        game = encounter(own=("frigate", "frigate"), enemy=("frigate", "colony_ship"))
        for attacker, target in ((True, 3), (3, 1), (1, 2), (None, 3), (1, None), (1, 99)):
            before = game.to_dict()
            with self.assertRaises(RuleError):
                game.combat_fire(attacker, target)
            self.assertEqual(game.to_dict(), before)
        game.combat_move(1, 7, 4)
        self.assertEqual(game.combat_fire(1, 3), 5)
        self.assertEqual((game.combat.ship(3).hull, game.combat.active_owner), (15, PLAYER))
        with self.assertRaises(RuleError):
            game.combat_fire(3, 1, RIVAL)
        before = game.to_dict()
        with self.assertRaises(RuleError):
            game.combat_fire(1, 3)
        self.assertEqual(game.to_dict(), before)
        game.combat_move(2, 7, 5)
        game.combat_fire(2, 4)
        game.combat_end_turn()
        with self.assertRaises(RuleError):
            game.combat_fire(2, 4)
        enemy_turn(game)
        self.assertEqual((game.combat.round, game.combat.acted, game.combat.active_owner), (2, [], PLAYER))
        self.assertEqual(game.combat.ship(1).hull, 15)

    def test_unarmed_hold_and_unequal_fleets_do_not_stall_turn_order(self):
        game = encounter(own=("frigate", "colony_ship"), enemy=("frigate", "frigate", "frigate"))
        game.combat_move(1, 7, 4)
        game.combat_fire(1, 3)
        before = game.to_dict()
        with self.assertRaisesRegex(RuleError, "unarmed"):
            game.combat_fire(2, 3)
        self.assertEqual(game.to_dict(), before)
        game.combat_hold(2)
        game.combat_end_turn()
        self.assertEqual(game.combat.active_owner, RIVAL)
        enemy_turn(game)
        self.assertEqual((game.combat.round, game.combat.active_owner), (2, PLAYER))
        resolve_battle(game)
        self.assertEqual(game.combat.status, "rival_victory")
        self.assertEqual(game.ships_owned_by(), [])
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_victory_commits_losses_damage_and_keeps_planet_ownership(self):
        game = encounter()
        colonies = [(p.owner, p.population, p.buildings.copy()) for s in game.systems for p in s.worlds]
        before_turn, before_credits = game.turn, game.credits
        resolve_battle(game)
        self.assertEqual(game.combat.status, "player_victory")
        self.assertEqual([(s.id, s.hull) for s in game.ships], [(1, 5)])
        self.assertEqual((game.turn, game.credits), (before_turn, before_credits))
        self.assertEqual([(p.owner, p.population, p.buildings) for s in game.systems for p in s.worlds], colonies)
        before = game.to_dict()
        with self.assertRaises(RuleError):
            game.combat_fire(1, 2)
        self.assertEqual(game.to_dict(), before)
        self.assertEqual(game.finish_combat(), 0)
        self.assertIsNone(game.combat)
        with self.assertRaises(RuleError):
            game.finish_combat()
        self.assertEqual(game.next_ship_id, 3)

    def test_retreat_moves_all_survivors_to_friendly_system_with_damage_and_normal_eta(self):
        game = encounter(own=("frigate", "colony_ship"), start=False)
        friend = next(s for s in game.systems[1:] if s.id != game.opponent.home_system and s.worlds)
        world = friend.worlds[0]
        world.colonized, world.owner, world.population = True, PLAYER, 1
        game.start_combat(0)
        game.combat_move(1, 7, 4)
        game.combat_fire(1, 3)
        game.combat_end_turn()
        enemy_turn(game)
        self.assertEqual(retreat_destination(game).id, friend.id)
        eta = game.travel_turns(game.systems[0], friend)
        game.combat_retreat()
        self.assertEqual(game.combat.status, "player_retreat")
        self.assertEqual([(s.destination, s.turns_remaining) for s in game.ships_owned_by()], [(friend.id, eta)]*2)
        self.assertEqual(game.ships[0].hull, 15)
        self.assertEqual(game.ship_at(3, owner=RIVAL).hull, 15)
        self.assertFalse(game.ship_at(3, owner=RIVAL).in_transit)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_retreat_fallback_and_civilian_ai_escape(self):
        game = encounter(enemy=("colony_ship",))
        game.combat_move(1, 7, 4)
        game.combat_fire(1, 2)
        game.combat_end_turn()
        game.combat_ai_action()
        self.assertEqual(game.combat.status, "rival_retreat")
        self.assertEqual(game.ship_at(2, owner=RIVAL).hull, 7)
        self.assertEqual(game.ship_at(2, owner=RIVAL).destination, game.opponent.home_system)
        own = encounter(own=("colony_ship",), start=False)
        own.start_combat(0, RIVAL)
        enemy_turn(own)
        self.assertEqual(own.combat.active_owner, PLAYER)
        destination = retreat_destination(own)
        self.assertIsNotNone(destination)
        self.assertNotEqual(destination.id, 0)
        own.combat_retreat()
        self.assertEqual(own.ships[0].hull, 7)
        self.assertEqual(GameState.from_dict(own.to_dict()), own)

    def test_no_safe_retreat_is_rejected_without_mutation(self):
        game = encounter(start=False)
        for system in game.systems[1:]:
            game.ships.append(Ship(game.next_ship_id, "frigate", system.id, owner=RIVAL))
            game.next_ship_id += 1
        game.start_combat(0)
        self.assertIsNone(retreat_destination(game))
        before = game.to_dict()
        with self.assertRaisesRegex(RuleError, "safe retreat"):
            game.combat_retreat()
        self.assertEqual(game.to_dict(), before)

    def test_battle_blocks_all_strategic_mutations_and_result_cannot_be_skipped(self):
        game = encounter(start=False)
        game.queue_building(0, 2, "factory")
        game.planet_at(0, 2).buildings = ["mine"]
        game.start_combat(0)
        actions = [game.advance_turn, lambda: game.queue_ship(0, 2, "frigate"),
                   lambda: game.queue_building(0, 2, "mine"), lambda: game.send_ship(1, 1),
                   lambda: game.cancel_construction(0, 2, 0), lambda: game.demolish_building(0, 2, 0),
                   lambda: game.choose_research("civil_engineering"), lambda: game.diplomacy_action("envoy"),
                   game.advance_research, game.add_opponent, game.finish_combat]
        for action in actions:
            before = game.to_dict()
            with self.assertRaises(RuleError):
                action()
            self.assertEqual(game.to_dict(), before)
        self.assertIn("battle", game.colonize_error(0, 3))
        resolve_battle(game)
        with self.assertRaises(RuleError):
            game.advance_turn()

    def test_repairs_need_a_full_unopposed_turn_at_a_friendly_colony(self):
        game = new_game(seed=2408)
        game.ships = [Ship(1, "frigate", 0, hull=7)]
        game.next_ship_id = 2
        game.advance_turn()
        self.assertEqual(game.ships[0].hull, 11)
        game.ships.append(Ship(2, "frigate", 0, owner=RIVAL))
        game.next_ship_id = 3
        game.advance_turn()  # Neutral fleets coexist, but repairs stop.
        self.assertEqual(game.ships[0].hull, 11)
        friend = next(s for s in game.systems[1:] if s.id != game.opponent.home_system and s.worlds)
        planet = friend.worlds[0]
        planet.colonized, planet.owner, planet.population = True, PLAYER, 1
        duration = game.send_ship(1, friend.id)
        for _ in range(duration):
            game.advance_turn()
        self.assertEqual(game.ship_at(1).hull, 11)  # No repair on the arrival turn.
        game.advance_turn()
        self.assertEqual(game.ship_at(1).hull, 15)

    def test_hostile_encounter_interrupts_before_income_and_arrival_starts_only_one_turn(self):
        game = encounter(start=False)
        game.diplomacy.relations = -100
        credits, turn = game.credits, game.turn
        report = game.advance_turn()
        self.assertEqual((game.credits, game.turn, report.income), (credits, turn, 0))
        self.assertEqual(game.combat.active_owner, RIVAL)
        moving = new_game(seed=2408)
        home = moving.opponent.home_system
        moving.ships = [Ship(1, "frigate", 0), Ship(2, "frigate", home, owner=RIVAL)]
        moving.next_ship_id = 3
        moving.diplomacy.relations = -100
        duration = moving.send_ship(1, home)
        for index in range(duration):
            moving.advance_turn()
            self.assertEqual(moving.turn, index+2)
            if index < duration-1:
                self.assertIsNone(moving.combat)
        self.assertEqual(moving.credits, 120+8*duration)
        self.assertEqual(moving.combat.system_id, home)
        self.assertEqual(moving.combat.active_owner, RIVAL)

    def test_ai_builds_warships_without_using_them_as_transports_or_attacking_neutrals(self):
        game = new_game(seed=2408)
        for _ in range(45):
            game.advance_turn()
            self.assertIsNone(game.combat)
        self.assertTrue(any(s.kind == "frigate" for s in game.ships_owned_by(RIVAL)))
        self.assertGreaterEqual(sum(p.owner == RIVAL for s in game.systems for p in s.worlds), 3)
        coexist = encounter(start=False)
        coexist.advance_turn()
        self.assertIsNone(coexist.combat)
        self.assertEqual(len(coexist.fleet_at(0)), 1)
        self.assertEqual(len(coexist.fleet_at(0, RIVAL)), 1)


class CombatSaveTests(unittest.TestCase):
    def test_save_before_ai_action_and_after_retreat_or_victory_preserves_exact_state(self):
        game = encounter(own=("frigate", "frigate", "colony_ship"), enemy=("frigate", "frigate"))
        game.combat_move(1, 7, 4)
        game.combat_fire(1, 4)
        game.combat_end_turn()
        self.assertEqual(game.ship_at(4, owner=RIVAL).hull, 20)  # Tactical damage is committed on resolution.
        self.assertEqual(game.combat.ship(4).hull, 15)
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            restored, _ = storage.load(storage.save(game))
            for _ in range(100):
                if game.combat.status != "active":
                    break
                if game.combat.active_owner == RIVAL:
                    game.combat_ai_action()
                    restored.combat_ai_action()
                else:
                    player_action(game)
                    player_action(restored)
                self.assertEqual(restored, game)
            self.assertNotEqual(game.combat.status, "active")
            self.assertEqual(storage.load(storage.save(game))[0], game)
            retreat = encounter()
            retreat.combat_retreat()
            self.assertEqual(storage.load(storage.save(retreat))[0], retreat)

    def test_v7_migration_keeps_research_routes_and_orders_and_adds_full_hulls(self):
        game = new_game(seed=2408)
        game.research = 53
        game.choose_research("civil_engineering")
        game.choose_research("ion_drives")
        game.queue_building(0, 2, "factory")
        game.ships = [Ship(1, "colony_ship", 0)]
        game.next_ship_id = 2
        game.send_ship(1, game.opponent.home_system)
        game.ship_at(1).departure_pending = False  # A v7 course was already committed.
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            path = storage.save(game)
            payload = json.loads(path.read_text())
            payload["version"] = 7
            payload["game"].pop("combat")
            for ship in payload["game"]["ships"]:
                ship.pop("hull")
            path.write_text(json.dumps(payload))
            restored, _ = storage.load(path)
            self.assertEqual(restored, game)
            self.assertEqual(restored.ships[0].hull, 12)
            self.assertEqual(json.loads(storage.save(restored).read_text())["version"], SAVE_VERSION)

    def test_malformed_combat_and_health_are_rejected(self):
        game = encounter()
        mutations = [
            lambda d: d.update(system_id=999), lambda d: d.update(round=True),
            lambda d: d.update(active_owner="unknown"), lambda d: d.update(acted=[1, 1]),
            lambda d: d.update(acted=[999]), lambda d: d.update(moved=[True]),
            lambda d: d.update(status="player_victory", active_owner=None),
            lambda d: d.update(retreat_destination=1), lambda d: d.update(ships=d["ships"][:1]),
            lambda d: d["ships"][0].update(hull=21), lambda d: d["ships"][0].update(hull=True),
            lambda d: d["ships"][0].update(owner=RIVAL), lambda d: d["ships"][1].update(id=1),
            lambda d: d["ships"][0].update(initial_hull=19), lambda d: d.update(log=["x"*181]),
        ]
        for mutate in mutations:
            data = game.to_dict()
            mutate(data["combat"])
            with self.assertRaises(SaveError):
                GameState.from_dict(data)
        for value in (True, 0, -1, 21, None):
            data = game.to_dict()
            data["ships"][0]["hull"] = value
            with self.assertRaises(SaveError):
                GameState.from_dict(data)
        for key, value in (("relations", 0), ("trade_active", True), ("research_active", True)):
            data = game.to_dict()
            data["diplomacy"][key] = value
            with self.assertRaises(SaveError):
                GameState.from_dict(data)
        game.combat_retreat()
        data = game.to_dict()
        data["ships"][0]["destination"] = None
        data["ships"][0]["turns_remaining"] = data["ships"][0]["travel_total"] = 0
        with self.assertRaises(SaveError):
            GameState.from_dict(data)


class CombatScreenTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        self.folder = tempfile.TemporaryDirectory()
        self.app = App(self.folder.name, capture=True)
        self.app.game = encounter(start=False)
        self.app.game.selected_planet = 2
        self.app.go("system")
        self.app.window = pg.display.set_mode((980, 900), pg.RESIZABLE)
        self.app.present()
        self.app.render()

    def tearDown(self):
        pg.quit()
        self.folder.cleanup()

    def click(self, key):
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        self.assertTrue(button.enabled, key)
        x, y = button.rect.center
        v = self.app.viewport
        pos = (round(v.x+x*v.w/1440), round(v.y+y*v.h/900))
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, button=1, pos=pos))
            self.app.render()

    def key(self, key):
        self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=key, mod=0))
        self.app.render()

    def enemy_action(self):
        self.app.time += 1
        self.app.update_combat()
        self.app.render()

    def finish_animation(self):
        if self.app.combat_animation:
            self.app.time += 2
            self.app.update_combat()
            self.app.render()

    def test_build_frigate_and_engage_from_fleet_with_cancel_safe_confirmation(self):
        self.app.go("shipyard")
        self.click("build_frigate")
        self.assertEqual(self.app.game.credits, 60)
        self.assertEqual(self.app.game.planet_at(0, 2).construction_queue[0].item_id, "frigate")
        self.key(pg.K_f)
        before = self.app.game.to_dict()
        self.click("ship_engage_1")
        self.click("dialog_cancel")
        self.assertEqual(self.app.game.to_dict(), before)
        self.click("ship_engage_1")
        self.click("dialog_ok")
        self.assertEqual(self.app.screen, "combat")
        self.assertEqual(self.app.game.diplomacy.relations, -100)

    def test_battle_controls_pause_save_reload_and_victory_cannot_advance_strategic_time(self):
        self.click("system_engage")
        self.click("dialog_ok")
        game = self.app.game
        initial_turn = game.turn
        self.click("combat_ship_1")
        self.click("combat_cell_7_4")
        self.finish_animation()
        self.click("combat_ship_2")
        self.assertEqual(game.combat.active_owner, PLAYER)
        self.assertFalse(next(b for b in self.app.buttons if b.key == "combat_fire").enabled)
        before = game.to_dict()
        for key in (pg.K_e, pg.K_i, pg.K_r, pg.K_d, pg.K_f):
            self.key(key)
        self.assertEqual(game.to_dict(), before)
        self.assertEqual(self.app.screen, "combat")
        self.key(pg.K_ESCAPE)
        self.enemy_action()
        self.assertEqual(game.to_dict(), before)
        self.click("settings")
        self.enemy_action()
        self.assertEqual(game.to_dict(), before)
        self.click("settings_done")
        self.click("save")
        path = next(p for p in self.app.storage.saves_dir.glob("*.json") if p.name != "autosave.json")
        self.app.load_game(path)
        self.assertEqual(self.app.screen, "combat")
        self.assertEqual(self.app.game, game)
        game = self.app.game
        for _ in range(40):
            self.finish_animation()
            if game.combat.status != "active":
                break
            if game.combat.active_owner == RIVAL:
                self.enemy_action()
            elif game.combat.ready(PLAYER) and game.combat.can_fire(game.combat.ship(self.app.combat_ship_id)):
                self.click("combat_fire")
            else:
                self.click("combat_end_turn")
        self.assertEqual(game.combat.status, "player_victory")
        self.assertEqual(game.turn, initial_turn)
        self.click("combat_continue")
        self.assertEqual(self.app.screen, "system")
        self.assertEqual([(s.id, s.hull) for s in game.ships], [(1, 5)])
        self.assertEqual(self.app.storage.load(self.app.storage.saves_dir/"autosave.json")[0], game)

    def test_retreat_confirmation_and_continue_apply_only_once(self):
        self.click("system_engage")
        self.click("dialog_ok")
        before = self.app.game.to_dict()
        self.click("combat_retreat")
        self.click("dialog_cancel")
        self.assertEqual(self.app.game.to_dict(), before)
        self.click("combat_retreat")
        self.click("dialog_ok")
        self.assertEqual(self.app.game.combat.status, "player_retreat")
        self.click("combat_continue")
        self.assertTrue(self.app.game.ship_at(1).in_transit)
        self.assertIsNone(self.app.game.combat)
        self.assertEqual(self.app.game.turn, 1)

    def test_all_ships_are_on_the_battlefield_and_clicking_enemy_fires(self):
        self.app.game = encounter(own=("frigate",)*6, enemy=("frigate",)*6)
        self.app.reset_combat_view()
        self.app.go("combat")
        self.click("combat_ship_6")
        self.click("combat_cell_7_7")
        self.finish_animation()
        self.click("combat_ship_12")
        self.assertEqual(self.app.game.combat.ship(12).hull, 15)
        self.finish_animation()
        self.assertEqual(self.app.game.combat.active_owner, PLAYER)
        self.assertEqual(GameState.from_dict(self.app.game.to_dict()), self.app.game)


if __name__ == "__main__":
    unittest.main()
