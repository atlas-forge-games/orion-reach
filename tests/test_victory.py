from scenarios import legacy_research_payload
from scenarios import legacy_economy
"""Playable conquest/science endings, real AI orders, save upgrades and UI flows."""

import copy
import json
import os
from pathlib import Path
import tempfile
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame as pg

from orion.model import ConstructionProject, GameState, PLAYER, RIVAL, RuleError, SaveError, Ship
from scenarios import empty_fleet_game as new_game, place_near
from functools import partial

# Preserve these pre-exploration scenarios; fog-on rules have their own tests.
new_game = partial(new_game, fog_of_war=False)
from orion.production import ASCENSION_GATE, GATE_CHARGE_TURNS
from orion.research import BRANCHES, TECHNOLOGIES, branch_tiers, choices
from orion.storage import SAVE_VERSION, Storage
from orion.victory import colonies, gate_site, invasion_strength


def discover_branches(game, owner=PLAYER, option=0):
    for branch in BRANCHES:
        for tier in branch_tiers(branch):
            tech = choices(branch, tier)[option]
            game._empire(owner).research += tech.cost
            game.choose_research(tech.id, owner=owner)


def discover_theory(game, owner=PLAYER):
    discover_branches(game, owner)
    game._empire(owner).research += TECHNOLOGIES["ascension_theory"].cost
    game.choose_research("ascension_theory", owner=owner)


def transports(game, system_id, count=2, owner=PLAYER):
    ids = []
    for _ in range(count):
        ids.append(game.next_ship_id)
        game.ships.append(Ship(game.next_ship_id, "troop_transport", system_id, owner=owner))
        game.next_ship_id += 1
    return ids


def extra_colony(game, owner):
    system, planet = next((s, p) for s in game.systems[1:] for p in s.worlds if not p.colonized and p.habitability > 0)
    planet.colonized, planet.owner, planet.population = True, owner, 1
    return system, planet


class ConquestRulesTests(unittest.TestCase):
    def test_troop_transports_use_real_costs_queue_and_ship_rules(self):
        game = new_game(seed=2408, with_ai=False)
        game.planet_at(0, 2).buildings = ["barracks"]
        game.queue_ship(0, 2, "troop_transport")
        earth = game.planet_at(0, 2)
        self.assertEqual((game.credits, earth.used_slots, game.queue_estimates(earth)), (120, 1, [7]))
        for _ in range(7):
            game.advance_turn()
        ship = game.ships[0]
        self.assertEqual((ship.kind, ship.hull, ship.damage), ("troop_transport", 16, 0))
        with self.assertRaises(RuleError):
            game.colonize(ship.id, 0, 3)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_invasion_rejects_missing_transports_enemy_fleets_and_invalid_ownership(self):
        game = new_game(seed=2408)
        sid, pid = game.opponent.home_system, game.opponent.home_planet
        before = game.to_dict()
        for target in ((sid, pid), (0, 2), (0, 3), (True, pid), (sid, 999)):
            with self.assertRaises(RuleError):
                game.invade(*target)
            self.assertEqual(game.to_dict(), before)
        ids = transports(game, sid)
        enemy = Ship(game.next_ship_id, "colony_ship", sid, owner=RIVAL)
        game.ships.append(enemy)
        game.next_ship_id += 1
        before = game.to_dict()
        with self.assertRaisesRegex(RuleError, "opposing ships"):
            game.invade(sid, pid)
        self.assertEqual(game.to_dict(), before)
        game.ships.remove(enemy)
        for identifier in ids:
            game.send_ship(identifier, 0)
            game.ship_at(identifier).departure_pending = False  # Already departed.
        with self.assertRaisesRegex(RuleError, "orbit"):
            game.invade(sid, pid)

    def test_ties_favour_defender_and_failed_landings_consume_transports_and_end_treaties(self):
        game = new_game(seed=2408)
        sid, pid = game.opponent.home_system, game.opponent.home_planet
        planet = game.planet_at(sid, pid)
        planet.population = 4
        transports(game, sid, 1)
        game.diplomacy.trade_active = game.diplomacy.research_active = True
        report = game.invade(sid, pid)
        self.assertEqual((report.attack, report.defence, report.captured), (8, 8, False))
        self.assertEqual((planet.owner, planet.population), (RIVAL, 4))
        self.assertEqual(game.ships, [])
        self.assertEqual(game.diplomacy.relations, -100)
        self.assertFalse(game.diplomacy.trade_active or game.diplomacy.research_active)
        self.assertIsNone(game.result)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_capture_preserves_population_buildings_paid_orders_and_relocates_headquarters(self):
        game = new_game(seed=2408)
        new_home = extra_colony(game, RIVAL)
        sid, pid = game.opponent.home_system, game.opponent.home_planet
        planet = game.planet_at(sid, pid)
        planet.buildings = ["factory", "research_lab"]
        game.queue_building(sid, pid, "trade_center", owner=RIVAL)
        game.fund_project(planet.construction_queue[0], RIVAL)
        planet.construction_queue[0].progress = 7
        queued = copy.deepcopy(planet.construction_queue)
        population = planet.population
        credits = game.credits, game.opponent.credits
        transports(game, sid)
        report = game.invade(sid, pid)
        self.assertTrue(report.captured)
        self.assertEqual((planet.owner, planet.population, planet.buildings), (PLAYER, population, ["factory", "research_lab"]))
        self.assertEqual(planet.construction_queue, queued)
        self.assertEqual((game.credits, game.opponent.credits), credits)
        self.assertEqual(game.headquarters(RIVAL), new_home)
        self.assertIsNone(game.result)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        before = planet.construction_queue[0].progress
        game.advance_turn()
        self.assertTrue(not planet.construction_queue or planet.construction_queue[0].progress > before)

    def test_last_colony_capture_ends_campaign_even_with_surviving_enemy_colony_ship(self):
        game = new_game(seed=2408)
        sid, pid = game.opponent.home_system, game.opponent.home_planet
        transports(game, sid)
        game.ships.append(Ship(game.next_ship_id, "colony_ship", 0, owner=RIVAL))
        game.next_ship_id += 1
        game.invade(sid, pid)
        self.assertEqual((game.result.winner, game.result.condition, game.result.turn), (PLAYER, "conquest", 1))
        self.assertEqual(len(game.ships_owned_by(RIVAL)), 1)
        before = game.to_dict()
        actions = (game.advance_turn, lambda: game.queue_ship(0, 2, "frigate"),
                   lambda: game.queue_building(0, 2, "factory"), lambda: game.choose_research("ion_drives"),
                   lambda: game.send_ship(game.ships[0].id, sid, owner=RIVAL),
                   lambda: game.colonize(game.ships[0].id, 0, 3, owner=RIVAL),
                   lambda: game.diplomacy_action("gift"), lambda: game.invade(sid, pid),
                   lambda: game.start_combat(0), lambda: game.queue_gate(0, 2), game.add_opponent)
        for action in actions:
            with self.assertRaises(RuleError):
                action()
            self.assertEqual(game.to_dict(), before)
        self.assertIs(game.check_victory(), game.result)
        self.assertEqual(GameState.from_dict(before), game)

    def test_ai_capture_of_last_colony_stops_before_income_or_production(self):
        game = new_game(seed=2408)
        transports(game, 0, owner=RIVAL)
        game.diplomacy.relations = -100
        game.diplomacy.research_active = True  # Also exercise pending treaty termination.
        game.queue_building(0, 2, "factory")
        before = game.turn, game.credits, game.opponent.credits
        report = game.advance_turn()
        self.assertEqual((game.result.winner, game.result.condition), (RIVAL, "conquest"))
        self.assertEqual((game.turn, game.credits, game.opponent.credits), before)
        self.assertEqual((report.income, report.research), (0, 0))
        self.assertEqual(game.planet_at(0, 2).construction_queue[0].progress, 0)
        self.assertTrue(report.alerts)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_hostile_ai_builds_escorts_and_transports_travels_and_conquers(self):
        game = new_game(seed=2408)
        place_near(game, game.opponent.home_system)
        game.diplomacy.relations = -100
        seen = set()
        travelled = False
        for _ in range(180):
            if game.result:
                break
            game.advance_turn()
            seen.update(s.kind for s in game.ships_owned_by(RIVAL))
            travelled |= any(s.in_transit and s.kind == "troop_transport" for s in game.ships_owned_by(RIVAL))
            self.assertIsNone(game.combat)  # Player has no ships to fight.
            self.assertEqual(GameState.from_dict(game.to_dict()), game)
        self.assertTrue({"frigate", "troop_transport"} <= seen)
        self.assertTrue(travelled)
        self.assertIsNotNone(game.result)
        self.assertEqual((game.result.winner, game.result.condition), (RIVAL, "conquest"))


class ScienceRulesTests(unittest.TestCase):
    def test_ultimate_research_accepts_either_branch_choice_and_uses_banked_points(self):
        for option in (0, 1):
            game = new_game(seed=2408, with_ai=False)
            with self.assertRaisesRegex(RuleError, "9 required"):
                game.choose_research("ascension_theory")
            discover_branches(game, option=option)
            self.assertEqual(game.technology.finished_branches, 9)
            game.research = TECHNOLOGIES["ascension_theory"].cost+13
            game.choose_research("ascension_theory")
            self.assertEqual(game.research, 13)
            self.assertEqual(len(game.technology.completed), sum(len(branch_tiers(b)) for b in BRANCHES)+1)
            self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_gate_is_a_unique_shared_queue_project_with_fixed_cost_and_no_slot(self):
        game = new_game(seed=2408, with_ai=False)
        with self.assertRaisesRegex(RuleError, "Theory"):
            game.queue_gate(0, 2)
        discover_theory(game)
        earth = game.planet_at(0, 2)
        earth.buildings = ["factory"]*earth.building_capacity
        game.credits, game.resources = 700, 499
        game.queue_ship(0, 2, "frigate")
        game.queue_gate(0, 2)  # Unfunded orders are allowed and wait for supply.
        self.assertEqual(earth.free_slots, 0)
        self.assertEqual(game.project_price("ascension_gate"), 500)
        self.assertEqual([q.item_id for q in earth.construction_queue], ["frigate", "ascension_gate"])
        self.assertEqual((game.credits, game.resources), (700, 499))
        other_system, other = extra_colony(game, PLAYER)
        with self.assertRaisesRegex(RuleError, "already"):
            game.queue_gate(other_system.id, other.id)
        self.assertEqual(game.cancel_construction(0, 2, 1), "0 RES")
        game.queue_gate(other_system.id, other.id)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_scientific_victory_requires_construction_then_five_separate_clear_turns(self):
        game = new_game(seed=2408, with_ai=False)
        discover_theory(game)
        game.credits = game.resources = 500
        game.queue_gate(0, 2)
        earth = game.planet_at(0, 2)
        eta = game.queue_estimates(earth)[0]
        for _ in range(eta-1):
            game.advance_turn()
            self.assertFalse(earth.ascension_gate)
        game.advance_turn()
        self.assertTrue(earth.ascension_gate)
        self.assertEqual(earth.gate_charge, 0)
        for count in range(1, 5):
            game.advance_turn()
            self.assertEqual(earth.gate_charge, count)
            self.assertIsNone(game.result)
        game.advance_turn()
        self.assertEqual((game.result.winner, game.result.condition), (PLAYER, "science"))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_arriving_enemy_ships_pause_gate_and_departure_resumes_preserved_charge(self):
        game = new_game(seed=2408)
        discover_theory(game)
        earth = game.planet_at(0, 2)
        earth.ascension_gate, earth.gate_charge = True, 4
        ship = Ship(1, "frigate", game.opponent.home_system, owner=RIVAL)
        game.ships, game.next_ship_id = [ship], 2
        place_near(game, game.opponent.home_system)
        game.send_ship(1, 0, owner=RIVAL)
        ship.turns_remaining = 1
        game.advance_turn()
        self.assertEqual((ship.system_id, earth.gate_charge, game.result), (0, 4, None))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)
        game.send_ship(1, game.opponent.home_system, owner=RIVAL)
        game.advance_turn()
        self.assertEqual((earth.gate_charge, game.result.winner), (5, PLAYER))

    def test_capture_destroys_built_or_queued_enemy_gate_but_preserves_your_gate(self):
        for built in (False, True):
            game = new_game(seed=2408)
            discover_theory(game)
            discover_theory(game, RIVAL)
            extra_colony(game, RIVAL)
            sid, pid = game.opponent.home_system, game.opponent.home_planet
            enemy = game.planet_at(sid, pid)
            game.credits = game.opponent.credits = 500
            game.queue_gate(0, 2)
            if built:
                enemy.ascension_gate, enemy.gate_charge = True, 4
            else:
                game.queue_gate(sid, pid, owner=RIVAL)
                enemy.construction_queue[0].progress = 120
                enemy.construction_queue.append(ConstructionProject("factory"))
            transports(game, sid)
            game.invade(sid, pid)
            self.assertFalse(enemy.ascension_gate)
            self.assertEqual(enemy.gate_charge, 0)
            self.assertTrue(all(q.item_id != "ascension_gate" for q in enemy.construction_queue))
            self.assertIsNotNone(gate_site(game))
            self.assertIsNone(gate_site(game, RIVAL))
            self.assertEqual(game.opponent.credits, 500)
            self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_simultaneous_gates_are_a_saved_draw_without_player_order_bias(self):
        game = new_game(seed=2408)
        for owner in (PLAYER, RIVAL):
            discover_theory(game, owner)
            planet = colonies(game, owner)[0][1]
            planet.ascension_gate, planet.gate_charge = True, 4
        game.advance_turn()
        self.assertEqual((game.result.winner, game.result.condition), (None, "science"))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)


class VictorySaveTests(unittest.TestCase):
    def test_malformed_gates_research_and_outcomes_are_rejected(self):
        game = new_game(seed=2408)
        mutations = [lambda d: d.update(result={"winner": PLAYER, "condition": "science", "turn": 1}),
                     lambda d: d["systems"][0]["worlds"][2].update(ascension_gate=True),
                     lambda d: d["systems"][0]["worlds"][2].update(gate_charge=1),
                     lambda d: d["systems"][0]["worlds"][2].update(gate_charge=True),
                     lambda d: d["technology"].update(completed=["ascension_theory"])]
        for mutate in mutations:
            data = game.to_dict()
            mutate(data)
            with self.assertRaises(SaveError):
                GameState.from_dict(data)
        discover_theory(game)
        earth = game.planet_at(0, 2)
        earth.ascension_gate = True
        _, other = extra_colony(game, PLAYER)
        other.ascension_gate = True
        with self.assertRaises(SaveError):
            GameState.from_dict(game.to_dict())
        other.ascension_gate = False
        earth.gate_charge = 5
        game.check_victory()
        for result in (None, {"winner": RIVAL, "condition": "science", "turn": 1},
                       {"winner": PLAYER, "condition": "conquest", "turn": 1},
                       {"winner": PLAYER, "condition": "science", "turn": True}):
            data = game.to_dict()
            data["result"] = result
            with self.assertRaises(SaveError):
                GameState.from_dict(data)

    def test_v8_upgrade_preserves_in_flight_ships_damaged_combat_and_research(self):
        game = new_game(seed=2408)
        game.choose_research("ion_drives")
        game.queue_building(0, 2, "factory")
        game.ships = [Ship(1, "frigate", 0), Ship(2, "frigate", 0, owner=RIVAL), Ship(3, "colony_ship", 0)]
        game.next_ship_id = 4
        place_near(game, game.opponent.home_system)
        game.send_ship(3, game.opponent.home_system)
        game.ship_at(3).departure_pending = False  # Reproduce an already committed v8 voyage.
        game.start_combat(0)
        game.combat_move(1, 7, 4)
        game.combat_fire(1, 2)
        game.combat_end_turn()
        # v8 had no positions: a resumed battle deploys its surviving snapshot.
        from orion.combat import deploy
        deploy(game.combat)
        legacy_economy(game)
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(directory)
            path = storage.save(game)
            payload = json.loads(path.read_text())
            payload["version"] = 8
            legacy_research_payload(payload)
            payload["game"].pop("result")
            payload["game"]["combat"].pop("moved")
            for ship in payload["game"]["combat"]["ships"]:
                for key in ("x", "y", "weapon", "design", "shields"):
                    ship.pop(key)
            for system in payload["game"]["systems"]:
                for planet in system["worlds"]:
                    planet.pop("ascension_gate")
                    planet.pop("gate_charge")
            path.write_text(json.dumps(payload))
            original = path.read_bytes()
            restored, _ = storage.load(path)
            expected = copy.deepcopy(game)
            expected.combat.accuracy = False
            expected.combat.shots_fired = 0
            self.assertEqual(restored, expected)
            self.assertEqual(path.read_bytes(), original)
            restored.combat_ai_action()
            restored.combat_ai_action()
            self.assertEqual(restored.combat.ship(1).hull, 15)
            saved = storage.save(restored)
            self.assertEqual(json.loads(saved.read_text())["version"], SAVE_VERSION)
            self.assertEqual(storage.load(saved)[0], restored)

    def test_gate_build_and_charge_continue_identically_after_saving(self):
        game = new_game(seed=2408, with_ai=False)
        discover_theory(game)
        game.credits = game.resources = 500
        game.queue_gate(0, 2)
        game.advance_turn()
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(directory)
            restored, _ = storage.load(storage.save(game))
            for _ in range(100):
                if game.result:
                    break
                self.assertEqual(game.advance_turn(), restored.advance_turn())
                self.assertEqual(game, restored)
                if game.planet_at(0, 2).ascension_gate:
                    restored, _ = storage.load(storage.save(restored))
            self.assertEqual(game.result.condition, "science")
            self.assertEqual(storage.load(storage.save(game))[0], game)


class VictoryScreenTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        self.directory = tempfile.TemporaryDirectory()
        self.app = App(self.directory.name, capture=True)
        self.app.game = new_game(seed=2408)
        self.app.game.selected_planet = 2
        self.app.go("galaxy")
        self.app.window = pg.display.set_mode((980, 900), pg.RESIZABLE)
        self.app.present()

    def tearDown(self):
        pg.quit()
        self.directory.cleanup()

    def click(self, key):
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        self.assertTrue(button.enabled, key)
        x, y = button.rect.center
        viewport = self.app.viewport
        pos = (round(viewport.x+x*viewport.w/1440), round(viewport.y+y*viewport.h/900))
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, button=1, pos=pos))
            self.app.render()

    def key(self, key):
        self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=key, mod=0))
        self.app.render()

    def test_objectives_research_gate_confirmations_navigation_and_save(self):
        game = self.app.game
        discover_branches(game)
        game.research, game.credits = TECHNOLOGIES["ascension_theory"].cost, 500
        self.key(pg.K_v)
        self.assertEqual(self.app.screen, "objectives")
        self.click("research_ascension")
        self.assertIsNone(self.app.dialog)
        self.assertIn("ascension_theory", game.technology.completed)
        self.click("gate_build")
        self.click("dialog_cancel")
        self.assertIsNone(gate_site(game))
        self.click("gate_build")
        self.click("dialog_ok")
        self.assertEqual(game.credits, 500)
        self.click("gate_visit")
        self.assertEqual(self.app.screen, "planet")
        self.key(pg.K_v)
        self.key(pg.K_i)
        self.assertEqual(self.app.screen, "empire")
        self.key(pg.K_ESCAPE)
        self.assertEqual(self.app.screen, "objectives")
        self.key(pg.K_F5)
        path = self.app.storage.list_saves()[0]["path"]
        self.app.load_game(path)
        self.assertEqual(self.app.game, game)

    def test_active_ultimate_research_view_uses_objectives_without_a_ninth_branch(self):
        discover_branches(self.app.game)
        self.app.game.choose_research("ascension_theory")
        self.key(pg.K_r)
        self.assertEqual(self.app.research_branch, "construction")
        self.click("research_show_active")
        self.assertEqual(self.app.screen, "objectives")
        self.click("objectives_galaxy")
        self.assertEqual(self.app.screen, "galaxy")

    def test_build_transport_then_capture_through_controls_and_preserve_final_result(self):
        game = self.app.game
        game.planet_at(0, 2).buildings = ["barracks"]
        self.app.go("shipyard")
        self.click("build_troop_transport")
        self.assertEqual(game.planet_at(0, 2).construction_queue[0].item_id, "troop_transport")
        sid, pid = game.opponent.home_system, game.opponent.home_planet
        transports(game, sid)
        self.app.open_system(sid)
        self.app.open_planet(pid)
        before = game.to_dict()
        self.click("invade_planet")
        self.click("ground_cancel")
        self.assertEqual(game.to_dict(), before)
        self.click("invade_planet")
        self.click("ground_launch")
        self.assertEqual(self.app.screen, "ground")
        self.click("ground_continue")
        self.assertEqual(self.app.screen, "result")
        self.assertEqual(game.result.winner, PLAYER)
        before = game.to_dict()
        for key in (pg.K_e, pg.K_i, pg.K_r, pg.K_f, pg.K_d, pg.K_v):
            self.key(key)
            self.assertEqual(game.to_dict(), before)
            self.assertEqual(self.app.screen, "result")
        self.click("result_save")
        path = self.app.storage.list_saves()[0]["path"]
        self.click("result_menu")
        self.assertEqual(self.app.screen, "menu")
        self.app.load_game(path)
        self.app.render()
        self.assertEqual(self.app.screen, "result")
        self.assertEqual(self.app.game, game)
        self.click("result_new")
        self.assertEqual(self.app.screen, "race_select")

    def test_rival_science_victory_opens_defeat_screen_and_charge_survives_reload(self):
        game = self.app.game
        discover_theory(game, RIVAL)
        planet = colonies(game, RIVAL)[0][1]
        planet.ascension_gate, planet.gate_charge = True, 4
        self.key(pg.K_e)
        self.assertEqual(self.app.screen, "result")
        self.assertEqual((game.result.winner, game.result.condition), (RIVAL, "science"))
        restored, _ = self.app.storage.load(self.app.storage.saves_dir / "autosave.json")
        self.assertEqual(restored, game)


if __name__ == "__main__":
    unittest.main()
