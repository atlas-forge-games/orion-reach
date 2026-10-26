"""Researched hulls, carrier combat, deterministic saves and playable UI controls."""

import copy
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
from orion import ai
from orion.app import App
from orion.combat import ai_action, autoresolve, check_losses
from orion.designs import HULLS, loadout_error
from orion.model import GameState, PLAYER, RIVAL, RuleError, SaveError, Ship
from orion.research import BRANCHES, TECHNOLOGIES, branch_tiers, choices
from orion.storage import Storage
from scenarios import empty_fleet_game, place_near


def campaign():
    game = empty_fleet_game(seed=2408, fog_of_war=False)
    game.credits = game.resources = 10000
    return game


def research(game, *identifiers, owner=PLAYER):
    from scenarios import research_to
    research_to(game, *identifiers, owner=owner)


def carrier_battle(*, enemy="frigate", custom=False, two=False):
    game = campaign()
    research(game, "destroyer_hulls", "cruiser_hulls", "drone_carriers")
    design = game.save_design("Hive", "carrier", ["drone_bay", "drone_bay"]) if custom else None
    game.ships = [Ship(1, "carrier", 0, design=design), Ship(2, enemy, 0, owner=RIVAL)]
    if two:
        game.ships.append(Ship(3, "carrier", 0))
    game.next_ship_id = len(game.ships)+1
    place_near(game, 1)
    game.start_combat(0)
    return game


class HullResearchTests(unittest.TestCase):
    def setUp(self):
        from scenarios import use_research_layout
        use_research_layout(self, classic=True)

    def test_named_research_gates_custom_and_standard_construction_for_both_empires(self):
        for owner in (PLAYER, RIVAL):
            game = campaign()
            sid, planet = game.headquarters(owner)
            for kind in HULLS:
                if kind == "frigate":
                    continue
                planned = game.save_design("Planned "+kind, kind, ["laser"]) if owner == PLAYER else None
                before = game.to_dict()
                with self.assertRaisesRegex(RuleError, "Requires"):
                    game.queue_ship(sid.id, planet.id, kind, owner=owner)
                if planned:
                    with self.assertRaisesRegex(RuleError, "Requires"):
                        game.queue_ship(sid.id, planet.id, planned.id)
                self.assertEqual(game.to_dict(), before)
            research(game, "destroyer_hulls", "cruiser_hulls", "drone_carriers", "mass_ship_production", "titan_hulls", owner=owner)
            for kind in ("destroyer", "cruiser", "carrier", "titan"):
                game.queue_ship(sid.id, planet.id, kind, owner=owner)
                if owner == PLAYER:
                    game.save_design(kind, kind, ["drone_bay"] if kind == "carrier" else ["laser"])
            self.assertIn("Battleship", game.ship_build_error(sid.id, planet.id, "battleship", owner=owner))
            self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_skipped_hulls_stay_locked_even_after_later_research(self):
        game = campaign()
        research(game, "modular_spaceframes", "deep_space_logistics", "advanced_flak", "battleship_hulls", "titan_hulls")
        self.assertTrue(game.technology.hull_unlocked("battleship"))
        self.assertTrue(game.technology.hull_unlocked("titan"))
        for kind in ("destroyer", "cruiser", "carrier"):
            self.assertFalse(game.technology.hull_unlocked(kind))
        self.assertEqual(game.bonuses_for()["fuel_range"], 5)

    def test_carrier_research_builds_stock_and_custom_ships_with_bays(self):
        game = campaign()
        research(game, "destroyer_hulls", "cruiser_hulls", "drone_carriers")
        design = game.save_design("Hive", "carrier", ["drone_bay"]*2+["laser", "point_defense"])
        for kind in ("carrier", design.id):
            game.queue_ship(0, 2, kind)
            game.buy_construction(0, 2)
        self.assertEqual([s.drone_bays for s in game.ships], [2, 2])
        self.assertEqual([s.kind for s in game.ships], ["carrier", "carrier"])
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        self.assertIsNotNone(loadout_error("titan", ["drone_bay"]))
        self.assertIsNotNone(loadout_error("carrier", ["drone_bay"]*3))

    def test_new_science_victory_requires_starship_research(self):
        game = campaign()
        for branch in BRANCHES:
            if branch == "starships":
                continue
            for tier in branch_tiers(branch):
                research(game, choices(branch, tier)[0].id)
        self.assertEqual(game.technology.finished_branches, 8)
        self.assertIsNotNone(game.research_error("ascension_theory"))
        research(game, "destroyer_hulls", "cruiser_hulls", "drone_carriers", "battleship_hulls",
                 "interceptor_drones", "bomber_drones")
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_ai_researches_and_selects_buildable_advanced_ships(self):
        from orion.production import SHIP_TYPES
        game = campaign()
        game.opponent.resources = 10000
        research(game, "destroyer_hulls", "cruiser_hulls", "drone_carriers", owner=RIVAL)
        with patch('orion.ai.projected_income', return_value=SHIP_TYPES['carrier'].maintenance+1):
            self.assertEqual(ai.warship_choice(game, RIVAL), "carrier")
        game.ships = [Ship(1, "carrier", 0, owner=RIVAL)]
        game.next_ship_id = 2
        # After existing upkeep, a small surplus supports only a frigate;
        # a developed economy can afford an escort for the existing carrier.
        with patch('orion.ai.projected_income', return_value=3):
            self.assertEqual(ai.warship_choice(game, RIVAL), "frigate")
        with patch('orion.ai.projected_income', return_value=SHIP_TYPES['destroyer'].maintenance+1):
            self.assertEqual(ai.warship_choice(game, RIVAL), "destroyer")
        game.opponent.resources = 0
        self.assertEqual(ai.warship_choice(game, RIVAL), "frigate")

    def test_ai_includes_carriers_in_guardian_expeditions(self):
        from orion.model import new_game
        from orion.monsters import ai_orders
        game = new_game(seed=2408, rival_race_id="kharuun", with_tombs=False, fog_of_war=False)
        guardian = game.guardians[0]
        home = game.opponent.home_system
        place_near(game, guardian.system_id, anchor=home, distance=6)
        game.ships = [Ship(i, "carrier", home, owner=RIVAL) for i in range(1, 5)]
        game.next_ship_id = 5
        self.assertEqual(ai_orders(game), {1, 2, 3, 4})
        self.assertTrue(all(s.destination == guardian.system_id for s in game.ships))


class CarrierCombatTests(unittest.TestCase):
    def setUp(self):
        from scenarios import use_research_layout
        use_research_layout(self, legacy=True)

    def test_launch_creates_independent_ready_units_and_spends_firing_action(self):
        game = carrier_battle()
        campaign_before = copy.deepcopy(game.ships)
        identifiers = game.combat_launch_drones(1)
        self.assertEqual(len(identifiers), 4)
        self.assertEqual(game.ships, campaign_before)
        self.assertEqual(len({s.position for s in game.combat.ships}), 6)
        for identifier in identifiers:
            drone = game.combat.ship(identifier)
            self.assertEqual((drone.kind, drone.carrier_id, drone.hull, drone.movement), ("combat_drone", 1, 6, 5))
            self.assertTrue(game.combat.can_move(drone))
            self.assertTrue(game.combat.can_fire(drone))
        self.assertFalse(game.combat.can_fire(game.combat.ship(1)))
        self.assertTrue(game.combat.can_move(game.combat.ship(1)))
        before = game.to_dict()
        with self.assertRaises(RuleError):
            game.combat_launch_drones(1)
        with self.assertRaises(RuleError):
            game.combat_launch_drones(identifiers[0])
        self.assertEqual(game.to_dict(), before)

    def test_finite_reserve_and_active_limit_prevent_infinite_replacements(self):
        game = carrier_battle()
        identifiers = game.combat_launch_drones(1)
        game.combat_end_turn(); game.combat_end_turn(RIVAL)
        with self.assertRaisesRegex(RuleError, "maximum"):
            game.combat_launch_drones(1)
        game.combat.ship(identifiers[0]).hull = 0
        replacement = game.combat_launch_drones(1)
        self.assertEqual(len(replacement), 1)
        self.assertNotIn(replacement[0], identifiers)
        game.combat_end_turn(); game.combat_end_turn(RIVAL)
        for drone in game.combat.drones(game.combat.ship(1)):
            drone.hull = 0
        self.assertEqual(len(game.combat_launch_drones(1)), 3)
        self.assertEqual(game.combat.ship(1).drone_reserve, 0)
        game.combat_end_turn(); game.combat_end_turn(RIVAL)
        with self.assertRaisesRegex(RuleError, "exhausted"):
            game.combat_launch_drones(1)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_launch_blocked_by_surrounding_units_does_not_spend_action(self):
        game = carrier_battle()
        carrier = game.combat.ship(1)
        # Surround with an actual strategic fleet, then redeploy each escort.
        from orion.combat import battle_ship
        for index, cell in enumerate(game.combat.launch_cells(carrier), 3):
            ship = Ship(index, "scout", 0)
            game.ships.append(ship)
            unit = battle_ship(game, ship)
            unit.x, unit.y = cell
            game.combat.ships.append(unit)
        game.next_ship_id = max(s.id for s in game.ships)+1
        before = game.to_dict()
        with self.assertRaisesRegex(RuleError, "space"):
            game.combat_launch_drones(1)
        self.assertEqual(game.to_dict(), before)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    @patch("orion.combat.accuracy_breakdown", new=lambda *_: {"chance": 100})
    def test_drones_move_and_fire_and_point_defense_reduces_their_damage(self):
        for modules, expected in ((["laser"], 3), (["laser", "point_defense"], 2), (["laser", "point_defense"]*2, 1)):
            game = carrier_battle()
            # A valid cruiser blueprint gives the enemy point defense.
            from orion.designs import ShipDesign
            design = ShipDesign("design_1", "Defender", "cruiser", tuple(modules))
            game.ships[1] = Ship(2, "cruiser", 0, owner=RIVAL, design=design)
            from orion.combat import battle_ship
            target = battle_ship(game, game.ships[1]); target.x, target.y = 10, 4
            game.combat.ships[1] = target
            drone_id = game.combat_launch_drones(1)[0]
            game.combat_move(drone_id, 8, 4)
            self.assertEqual(game.combat_fire(drone_id, 2), expected)
            self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_carrier_loss_disables_only_its_drones_and_resolves_defeat(self):
        game = carrier_battle(two=True)
        first = game.combat_launch_drones(1)
        second = game.combat_launch_drones(3)
        game.combat.ship(1).hull = 0
        check_losses(game)
        self.assertTrue(all(game.combat.ship(i).hull == 0 for i in first))
        self.assertTrue(all(game.combat.ship(i).hull > 0 for i in second))
        self.assertEqual(game.combat.status, "active")
        game.combat.ship(3).hull = 0
        check_losses(game)
        self.assertEqual(game.combat.status, "rival_victory")
        self.assertEqual([s.id for s in game.ships], [2])
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_pure_bay_design_can_engage_and_ai_launches_and_finishes_battle(self):
        game = carrier_battle(custom=True)
        self.assertEqual(game.combat.ship(1).damage, 0)
        self.assertGreater(game.military_strength(game.ships[0]), 0)
        self.assertEqual(ai_action(game, PLAYER)["kind"], "launch")
        autoresolve(game)
        self.assertIsNotNone(game.combat)
        self.assertNotEqual(game.combat.status, "active")
        self.assertTrue(all(s.kind != "combat_drone" for s in game.ships))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_save_resume_replays_ai_orders_and_hits_for_both_carriers(self):
        game = carrier_battle(enemy="carrier")
        game.combat_launch_drones(1)
        with tempfile.TemporaryDirectory() as folder:
            store = Storage(folder)
            restored, _ = store.load(store.save(game))
            for _ in range(1000):
                if game.combat.status != "active":
                    break
                event = ai_action(game, game.combat.active_owner)
                self.assertEqual(event, ai_action(restored, restored.combat.active_owner))
            self.assertNotEqual(game.combat.status, "active")
            self.assertEqual(game, restored)
            self.assertEqual(store.load(store.save(game))[0], game)

    def test_retreat_recovers_drones_and_next_battle_gets_a_fresh_reserve(self):
        game = carrier_battle()
        game.combat_launch_drones(1)
        game.combat_retreat()
        self.assertEqual(len(game.ships), 2)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        game.finish_combat()
        game._clear_course(game.ships[0])
        game.start_combat(0)
        self.assertEqual(game.combat.ship(1).drone_reserve, 8)
        self.assertEqual(len(game.combat.ships), 2)

    def test_invalid_parent_ids_reserves_owner_and_campaign_drones_are_rejected(self):
        game = carrier_battle()
        game.combat_launch_drones(1)
        original = game.to_dict()
        mutations = [lambda d: d["combat"]["ships"][2].update(carrier_id=2),
                     lambda d: d["combat"]["ships"][2].update(owner=RIVAL),
                     lambda d: d["combat"]["ships"][2].update(id=-999999),
                     lambda d: d["combat"]["ships"][0].update(launched_drones=9),
                     lambda d: d["combat"]["ships"][0].update(launched_drones=True),
                     lambda d: d["combat"]["ships"][0].update(hull=0),
                     lambda d: d["ships"][0].update(kind="combat_drone"),
                     lambda d: d["combat"]["ships"][2].update(carrier_id=True)]
        for mutate in mutations:
            data = copy.deepcopy(original); mutate(data)
            with self.assertRaises(SaveError):
                GameState.from_dict(data)

    def test_guardian_and_drone_identifiers_coexist_through_combat_and_save(self):
        from orion.model import new_game
        game = new_game(seed=2408, with_ai=False, with_tombs=False)
        guardian = game.guardians[0]
        game.ships = [Ship(1, "carrier", guardian.system_id)]
        game.next_ship_id = 2
        game.start_combat(guardian.system_id)
        game.combat_launch_drones(1)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        autoresolve(game)
        self.assertIsNotNone(game.combat)
        self.assertNotEqual(game.combat.status, "active")
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_two_ai_empires_autoresolve_carriers_without_campaign_drones(self):
        from orion.model import new_game
        game = new_game(seed=2408, rival_count=2, with_guardians=False, with_tombs=False)
        game.ships = [Ship(1, "carrier", 1, owner=RIVAL), Ship(2, "carrier", 1, owner="rival_2")]
        game.next_ship_id = 3
        game.start_combat(1, RIVAL, "rival_2")
        autoresolve(game)
        self.assertIsNotNone(game.combat)
        self.assertNotEqual(game.combat.status, "active")
        self.assertTrue(any(s.kind == "combat_drone" for s in game.combat.ships))
        self.assertTrue(all(s.kind == "carrier" for s in game.ships))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)


class LegacyHullTests(unittest.TestCase):
    def test_authentic_v28_saves_keep_hulls_queues_and_science_goal(self):
        from scenarios import use_research_layout
        use_research_layout(self, legacy=True)
        fixtures = list((Path(__file__).parent/"fixtures").glob("v0381_*_v28.json"))
        self.assertEqual(len(fixtures), 2)
        for path in fixtures:
            original = path.read_bytes()
            data = json.loads(original)
            game = GameState.from_dict(data["game"], version=data["version"])
            self.assertTrue(game.technology.legacy_starships)
            self.assertEqual(len(game.technology.required_branches), 8)
            self.assertTrue(game.technology.hull_unlocked("cruiser"))
            self.assertFalse(game.technology.hull_unlocked("carrier"))
            self.assertEqual([d.name for d in game.designs], ["Legacy Cruiser", "Legacy Battleship"])
            self.assertEqual(game.planet_at(0, 2).construction_queue[0].design.kind, "battleship")
            if game.combat is None:
                self.assertEqual((game.technology.active, game.technology.progress), (None, 0))
                self.assertEqual(game.research, data["game"]["research"]+123)
                self.assertNotIn("ascension_theory", game.technology.completed)
                game.save_design("Still available", "cruiser", ["laser"])
            self.assertEqual(GameState.from_dict(game.to_dict()), game)
            self.assertEqual(path.read_bytes(), original)


class StarshipUITests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.app = App(Path(self.folder.name), capture=True)
        self.app.game = campaign()
        self.app.game.selected_planet = 2

    def tearDown(self):
        self.app.audio.close(); pg.quit(); self.folder.cleanup()

    def test_research_locked_and_unlocked_hulls_and_all_shipyard_pages_render(self):
        app = self.app
        app.open_designer(); app.choose_design_hull("carrier"); app.render()
        self.assertFalse(next(b for b in app.buttons if b.key == "design_save").enabled)
        research(app.game, "destroyer_hulls", "cruiser_hulls", "drone_carriers", "titan_hulls")
        app.design_name = "Hive"
        app.change_design_module("drone_bay", 1); app.render()
        self.assertTrue(next(b for b in app.buttons if b.key == "design_save").enabled)
        app.save_ship_design(); app.open_shipyard(0, 2)
        seen = set()
        for page in range(3):
            app.shipyard_catalog_page = page; app.render()
            seen.update(b.key for b in app.buttons if b.key.startswith("build_"))
            self.assertTrue(all(app.canvas.get_rect().contains(b.rect) for b in app.buttons))
        self.assertTrue({"build_carrier", "build_titan", "build_destroyer"} <= seen)
        app.open_research(); app.select_research_branch("starships"); app.select_research_tier(3); app.render()
        self.assertTrue(all(app.canvas.get_rect().contains(b.rect) for b in app.buttons))
        self.assertIn("research_choose_drone_carriers", [b.key for b in app.buttons])

    def test_launch_control_deploys_selectable_drones_and_autosaves(self):
        app = self.app
        app.game = carrier_battle(custom=True)
        app.go("combat"); app.combat_ship_id = 1; app.render()
        self.assertTrue(next(b for b in app.buttons if b.key == "combat_launch").enabled)
        app.combat_action("launch"); app.render()
        drones = app.game.combat.drones(app.game.combat.ship(1))
        self.assertEqual(len(drones), 4)
        for drone in drones:
            self.assertIn(f"combat_ship_{drone.id}", [b.key for b in app.buttons])
        app.select_combat_ship(PLAYER, drones[0].id); app.render()
        self.assertEqual(app.combat_ship_id, drones[0].id)
        self.assertEqual(Storage(self.folder.name).load(Path(self.folder.name)/"saves/autosave.json")[0], app.game)


if __name__ == "__main__":
    unittest.main()
