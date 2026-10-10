"""Blueprint constraints, immutable production, tactical effects and real UI flows."""

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

from orion.app import App
from orion.combat import ai_action
from orion.combat_effects import CombatAnimation
from orion.exploration import known_system, record_survey
from orion.model import GameState, PLAYER, RIVAL, RuleError, SaveError, Ship
from scenarios import fixed_start_game as new_game, place_near
from orion.storage import Storage


def scenario(ai=False):
    game = new_game(seed=2408, with_ai=ai, with_guardians=False, fog_of_war=False)
    game.ships.clear()
    game.next_ship_id = 1
    game.credits = game.resources = 5000
    game.technology.completed = ["destroyer_hulls", "cruiser_hulls", "battleship_hulls"]
    return game


def duel(weapons=("laser", "torpedo"), defenses=("shield", "point_defense")):
    game = scenario(True)
    game.technology.completed += ["radiation_shields"]
    attacker = game.save_design("Archer", "cruiser", weapons)
    defender = game.save_design("Bastion", "cruiser", ["laser", *defenses])
    game.ships = [Ship(1, "cruiser", 0, design=attacker), Ship(2, "cruiser", 0, owner=RIVAL, design=defender)]
    game.next_ship_id = 3
    game.start_combat(0)
    game.combat_move(1, 7, 4)
    return game


class DesignerRulesTests(unittest.TestCase):
    def test_capacity_category_limits_weapons_names_and_unlocks_are_enforced(self):
        game = scenario()
        bad = [("", "frigate", ["laser"]), ("A", "scout", ["laser"]),
               ("A", "frigate", ["armor"]), ("A", "frigate", ["laser"]*4),
               ("A", "frigate", ["laser", "armor", "point_defense", "armor"]),
               ("A", "cruiser", ["laser"]*5+["armor"]*4),
               ("A", "frigate", ["laser", "shield"]),
               ("A", "cruiser", ["laser", "scanner", "scanner"])]
        for args in bad:
            before = game.to_dict()
            with self.assertRaises(RuleError, msg=str(args)):
                game.save_design(*args)
            self.assertEqual(game.to_dict(), before)
        game.save_design("Vanguard", "frigate", ["laser"])
        with self.assertRaises(RuleError):
            game.save_design("vanguard", "cruiser", ["laser"])
        game.technology.completed += ["radiation_shields", "ion_drives", "research_networks", "research_instruments", "quantum_optics"]
        design = game.save_design("Advanced", "battleship", ["quantum", "torpedo", "shield", "armor", "scanner", "engine"])
        self.assertEqual((design.hull, design.shields, design.damage, design.weapon_range, design.movement), (83, 12, 24, 9, 2))

    def test_library_limit_allows_revising_an_existing_blueprint(self):
        game = scenario()
        for index in range(24):
            game.save_design(f"Pattern {index}", "frigate", ["laser"])
        with self.assertRaises(RuleError):
            game.save_design("Overflow", "frigate", ["laser"])
        updated = game.save_design("Revised", "battleship", ["torpedo"], "design_1")
        self.assertEqual(game.designs[0], updated)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_queued_and_built_ships_keep_their_blueprint_after_revision(self):
        game = scenario()
        original = game.save_design("Vanguard", "frigate", ["laser", "armor"])
        game.queue_ship(0, 2, original.id)
        project = game.planet_at(0, 2).construction_queue[0]
        project.progress = 6
        old_refund = project.refund
        updated = game.save_design("Vanguard II", "cruiser", ["torpedo", "laser"], original.id)
        self.assertEqual((project.spec, project.refund), (original, old_refund))
        game.buy_construction(0, 2)
        old_ship = game.ships[0]
        self.assertEqual((old_ship.design, old_ship.kind, old_ship.hull, old_ship.name), (original, "frigate", 28, "Vanguard 001"))
        game.queue_ship(0, 2, updated.id)
        forecast = game.queue_estimates(game.planet_at(0, 2))[-1]
        for _ in range(forecast):
            game.advance_turn()
        self.assertEqual([s.design for s in game.ships], [original, updated])
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_cost_discounts_cancellation_forecasts_and_building_slots(self):
        game = scenario()
        game.technology.completed = ["lightweight_alloys"]
        design = game.save_design("Patrol", "frigate", ["laser", "armor"])
        earth = game.planet_at(0, 2)
        slots, before = earth.free_slots, game.to_dict()
        turns = game.queue_estimates(earth, design.id)[-1]
        self.assertEqual(game.to_dict(), before)
        self.assertEqual(game.project_price(design.id), 47)
        game.queue_ship(0, 2, design.id)
        self.assertEqual(earth.free_slots, slots)
        game.cancel_construction(0, 2, 0)
        self.assertEqual(game.credits, before["credits"])
        game.queue_ship(0, 2, design.id)
        for _ in range(turns-1):
            game.advance_turn()
        self.assertFalse(game.ships)
        game.advance_turn()
        self.assertEqual(game.ships[0].design, design)

    def test_overflow_and_prioritizing_custom_production_preserve_snapshots(self):
        game = scenario()
        first = game.save_design("Alpha", "frigate", ["laser"])
        second = game.save_design("Beta", "cruiser", ["torpedo"])
        game.queue_ship(0, 2, first.id)
        game.change_production(0, 2, second.id)
        queue = game.planet_at(0, 2).construction_queue
        for project in queue:
            game.fund_project(project)
            project.progress = project.spec.work_cost-1
        game.save_design("Alpha II", "battleship", ["laser"], first.id)
        report = game.advance_turn()
        self.assertEqual([s.design for s in game.ships], [second, first])
        self.assertEqual(report.completed, ["Beta on Earth", "Alpha on Earth"])

    def test_design_ships_travel_and_resume_pending_orders(self):
        game = scenario()
        design = game.save_design("Voyager", "battleship", ["laser", "armor"])
        game.queue_ship(0, 2, design.id)
        game.buy_construction(0, 2)
        target = place_near(game, 1)
        game.send_ships([1], target.id)
        copy_game = GameState.from_dict(game.to_dict())
        self.assertEqual(copy_game, game)
        self.assertTrue(copy_game.ships[0].departure_pending)
        copy_game.cancel_departures([1])
        self.assertEqual(copy_game.ships[0].design, design)
        copy_game.send_ship(1, target.id)
        for _ in range(copy_game.ships[0].travel_total):
            copy_game.advance_turn()
        self.assertEqual(copy_game.ships[0].system_id, target.id)

    def test_unseen_surveys_render_old_design_projects_after_revision(self):
        game = scenario()
        game.fog_of_war = True
        design = game.save_design("Archive", "frigate", ["laser"])
        game.queue_ship(0, 2, design.id)
        record_survey(game, 0, PLAYER)
        game.save_design("Archive II", "cruiser", ["torpedo"], design.id)
        earth = game.planet_at(0, 2)
        earth.owner = RIVAL
        self.assertEqual(known_system(game, 0).worlds[2].construction_queue[0].spec, design)


class DesignerCombatTests(unittest.TestCase):
    @patch("orion.combat.accuracy_breakdown", new=lambda *_: {"chance": 100})
    def test_mixed_volley_uses_each_weapon_range_and_one_action(self):
        game = duel(defenses=())
        attacker, target = game.combat.ships
        target.x = 14  # Seven cells: only the torpedo can reach.
        self.assertEqual(game.combat_fire(1, 2), 10)
        self.assertEqual(target.hull, 32)
        with self.assertRaises(RuleError):
            game.combat_fire(1, 2)
        effect = CombatAnimation.from_action(game.combat, {"kind": "fire", "ship_id": 1, "target_id": 2, "damage": 10})
        self.assertEqual(effect.weapons, ("torpedo",))

    @patch("orion.combat.accuracy_breakdown", new=lambda *_: {"chance": 100})
    def test_shields_absorb_then_hull_takes_damage_and_point_defense_is_a_soft_counter(self):
        game = duel(weapons=("laser", "laser", "torpedo"))
        target = game.combat.ship(2)
        self.assertEqual(game.combat_fire(1, 2), 5)  # 10 lasers + 7 torpedo - 12 shields.
        self.assertEqual((target.hull, target.shields), (37, 0))
        game.combat_end_turn()
        game.combat_end_turn(RIVAL)
        self.assertEqual(target.shields, 0)  # No per-turn regeneration.
        self.assertEqual(game.combat_fire(1, 2), 17)
        game2 = duel(weapons=("torpedo",), defenses=("point_defense",)*3)
        self.assertEqual(game2.combat_fire(1, 2), 4)  # Interception is capped at 60%.

    def test_active_combat_save_replays_with_the_same_loadout_and_shields(self):
        game = duel()
        game.combat_fire(1, 2)
        game.combat_end_turn()
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            resumed, _ = storage.load(storage.save(game))
            self.assertEqual(resumed, game)
            for _ in range(200):
                if game.combat.status != "active":
                    break
                owner = game.combat.active_owner
                self.assertEqual(ai_action(game, owner), ai_action(resumed, owner))
                self.assertEqual(resumed, game)
            self.assertNotEqual(game.combat.status, "active")
            self.assertEqual(storage.load(storage.save(game))[0], game)
            with self.assertRaises(RuleError):
                game.save_design("Blocked", "frigate", ["laser"])

    def test_guardians_attack_designed_ships_and_destruction_still_explodes(self):
        game = new_game(seed=2408, with_ai=False)
        game.technology.completed = ["destroyer_hulls", "cruiser_hulls", "battleship_hulls"]
        guard = game.guardians[0]
        design = game.save_design("Hunter", "battleship", ["torpedo"]*4+["armor"]*4)
        game.ships = [Ship(1, "battleship", guard.system_id, design=design)]
        game.next_ship_id = 2
        game.start_combat(guard.system_id)
        for _ in range(600):
            if game.combat.status != "active":
                break
            event = ai_action(game, game.combat.active_owner)
            if event["kind"] == "fire":
                effect = CombatAnimation.from_action(game.combat, event)
                if effect.destroyed:
                    self.assertEqual(effect.duration, 1.3)
        self.assertNotEqual(game.combat.status, "active")
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_corrupt_blueprints_shields_and_battle_equipment_are_rejected(self):
        game = duel()
        base = game.to_dict()
        invalid = []
        row = copy.deepcopy(base); row["ships"][0]["design"]["modules"] = ["laser"]*12; invalid.append(row)
        row = copy.deepcopy(base); row["combat"]["ships"][0]["shields"] = 1; invalid.append(row)
        row = copy.deepcopy(base); row["combat"]["ships"][0]["design"]["name"] = "Forged"; invalid.append(row)
        row = copy.deepcopy(base); row["designs"][0]["modules"] = ["quantum"]; invalid.append(row)
        row = copy.deepcopy(base); row["ships"][0]["kind"] = "battleship"; invalid.append(row)
        for data in invalid:
            with self.assertRaises(SaveError):
                GameState.from_dict(data)


class DesignerUITests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.app = App(Path(self.folder.name), capture=True)
        self.app.game = scenario()
        self.app.game.selected_planet = 2
        self.app.go("fleets")
        self.app.present()

    def tearDown(self):
        self.app.audio.close()
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

    def test_create_revise_build_and_choose_design_from_colony_production(self):
        self.click("fleets_designer")
        self.click("design_hull_cruiser")
        self.click("design_add_torpedo")
        self.click("design_name")
        self.app.handle_event(pg.event.Event(pg.TEXTINPUT, text="Pathfinder"))
        self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_RETURN, mod=0))
        self.click("design_save")
        self.click("design_build")
        game = self.app.game
        original = game.designs[0]
        self.assertEqual(game.planet_at(0, 2).construction_queue[0].design, original)
        self.click("design_add_laser")
        self.assertFalse(next(b for b in self.app.buttons if b.key == "design_build").enabled)
        self.click("design_save")
        self.assertNotEqual(game.designs[0], original)
        self.assertEqual(game.planet_at(0, 2).construction_queue[0].design, original)
        self.assertEqual(self.app.storage.load(self.app.storage.saves_dir/"autosave.json")[0], game)
        self.app.open_production()
        while "production_build_design_1" not in {b.key for b in self.app.buttons}:
            self.click("catalog_next")
        self.click("production_build_design_1")
        self.assertEqual(game.planet_at(0, 2).construction_queue[0].design, game.designs[0])
        for screen in ("planet", "production", "shipyard", "empire", "designer"):
            self.app.go(screen)
            self.app.render()

    def test_locked_modules_capacity_and_library_pagination(self):
        self.click("fleets_designer")
        self.assertFalse(next(b for b in self.app.buttons if b.key == "design_add_shield").enabled)
        for index in range(24):
            self.app.game.save_design(f"Plan {index}", "frigate", ["laser"])
        for _ in range(3):
            self.click("design_next")
        self.click("design_load_design_24")
        self.assertEqual(self.app.design_id, "design_24")
        self.click("design_hull_battleship")
        for _ in range(7):
            self.click("design_add_laser")
        self.assertFalse(next(b for b in self.app.buttons if b.key == "design_add_laser").enabled)
        self.app.game.selected_planet = None
        self.app.open_designer()
        self.app.render()
        for button in self.app.buttons:
            self.assertTrue(self.app.canvas.get_rect().contains(button.rect), button.key)
        self.app.game.selected_system, self.app.game.selected_planet = 0, 2
        self.app.open_production()
        self.app.render()
        while next(b for b in self.app.buttons if b.key == "catalog_next").enabled:
            self.click("catalog_next")
        self.click("production_build_design_24")
        self.assertEqual(self.app.game.planet_at(0, 2).construction_queue[0].design.id, "design_24")

    @patch("orion.combat.accuracy_breakdown", new=lambda *_: {"chance": 100})
    def test_custom_weapons_draw_beams_torpedoes_and_explosions(self):
        self.app.game = duel(weapons=("laser", "laser", "torpedo"), defenses=())
        battle = self.app.game.combat
        battle.ship(2).hull = 10
        damage = self.app.game.combat_fire(1, 2)
        self.app.go("combat")
        self.app.after_combat_action({"kind": "fire", "ship_id": 1, "target_id": 2, "damage": damage})
        self.assertTrue(self.app.combat_animation.destroyed)
        self.assertEqual(self.app.combat_animation.weapons, ("laser", "torpedo"))
        for age in (.05, .2, .45, 1.1):
            self.app.combat_animation.elapsed = age
            self.app.render()


if __name__ == "__main__":
    unittest.main()
