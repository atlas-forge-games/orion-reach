"""Persistent ground forces, honest previews, AI invasions and playable UI flows."""

import copy
import os
from pathlib import Path
import tempfile
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame as pg

from orion.ai import invasion_orders, run_ai
from orion.exploration import record_survey
from orion.ground_combat import GroundForces, forces, resolve, train, transports_needed
from orion.model import GameState, PLAYER, RIVAL, RuleError, SaveError, Ship
from orion.production import TROOP_STRENGTH
from orion.storage import Storage
from scenarios import empty_fleet_game, place_near


def scenario(**kwargs):
    return empty_fleet_game(seed=2408, fog_of_war=kwargs.pop("fog_of_war", False), **kwargs)


def add_transports(game, sid, count, owner=PLAYER):
    for _ in range(count):
        game.ships.append(Ship(game.next_ship_id, "troop_transport", sid, owner=owner))
        game.next_ship_id += 1


def fortified_target(game):
    sid, pid = game.opponent.home_system, game.opponent.home_planet
    planet = game.planet_at(sid, pid)
    planet.buildings = ["barracks", "fortifications"]
    planet.garrison = 8
    return sid, pid, planet


class GroundBuildingTests(unittest.TestCase):
    def test_barracks_finish_before_training_then_cap_at_eight(self):
        game = scenario(with_ai=False)
        planet = game.planet_at(0, 2)
        self.assertIn("barracks", game.ship_build_error(0, 2, "troop_transport"))
        game.queue_building(0, 2, "barracks")
        self.assertEqual((game.credits, planet.used_slots), (70, 1))
        for _ in range(5):
            game.advance_turn()
            self.assertEqual(planet.garrison, 0)
        self.assertEqual(planet.buildings, ["barracks"])
        self.assertIsNone(game.ship_build_error(0, 2, "troop_transport"))
        for troops in range(1, 9):
            game.advance_turn()
            self.assertEqual(planet.garrison, troops)
        game.advance_turn()
        self.assertEqual(planet.garrison, 8)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_training_does_not_spend_population_or_shrink_occupation_forces(self):
        planet = scenario(with_ai=False).planet_at(0, 2)
        planet.buildings = ["barracks"]
        before = planet.population, planet.farmers, planet.scientists, planet.workers
        self.assertEqual(train(planet), 1)
        self.assertEqual((planet.population, planet.farmers, planet.scientists, planet.workers), before)
        planet.garrison = 15
        self.assertEqual(train(planet), 0)
        self.assertEqual(planet.garrison, 15)

    def test_unique_buildings_queued_built_demolished_and_full_slots(self):
        for kind in ("barracks", "fortifications"):
            game = scenario(with_ai=False)
            planet = game.planet_at(0, 2)
            game.queue_building(0, 2, kind)
            before = game.to_dict()
            with self.assertRaisesRegex(RuleError, "Only one"):
                game.queue_building(0, 2, kind)
            self.assertEqual(game.to_dict(), before)
            planet.finish_current_project()
            with self.assertRaisesRegex(RuleError, "Only one"):
                game.queue_building(0, 2, kind)
            planet.garrison = 6
            game.demolish_building(0, 2, 0)
            self.assertEqual(train(planet), 0)
            self.assertEqual((planet.garrison, forces(planet).defence_bonus), (6, 0))
            game.credits = 1000
            planet.buildings = ["factory"]*planet.building_capacity
            with self.assertRaisesRegex(RuleError, "slots"):
                game.queue_building(0, 2, kind)

    def test_queued_transports_keep_progress_after_barracks_demolition(self):
        game = scenario(with_ai=False)
        planet = game.planet_at(0, 2)
        planet.buildings = ["barracks"]
        game.queue_ship(0, 2, "troop_transport")
        planet.construction_queue[0].progress = 40
        game.demolish_building(0, 2, 0)
        self.assertIn("barracks", game.ship_build_error(0, 2, "troop_transport"))
        game.advance_turn()
        self.assertEqual([s.kind for s in game.ships], ["troop_transport"])
        self.assertEqual(GameState.from_dict(game.to_dict()), game)


class GroundBattleTests(unittest.TestCase):
    def test_simultaneous_round_and_fortifications_change_the_winner(self):
        plain = resolve(24, GroundForces(12, 8, 0))
        fortified = resolve(24, GroundForces(12, 8, 50))
        self.assertEqual((plain.attackers, plain.defenders, plain.captured), (9, 0, True))
        self.assertEqual((fortified.attackers, fortified.defenders, fortified.captured), (0, 3, False))
        first = fortified.rounds[0]
        self.assertEqual((first.attacker_losses, first.defender_losses), (8, 6))
        self.assertEqual((first.attackers, first.defenders), (16, 14))
        self.assertFalse(resolve(8, GroundForces(8, 0, 0)).captured)
        self.assertFalse(resolve(0, GroundForces(0, 0, 0)).captured)
        self.assertTrue(resolve(8, GroundForces(0, 0, 0)).captured)

    def test_preview_matches_capture_and_survivors_become_garrison(self):
        game = scenario()
        sid, pid, planet = fortified_target(game)
        add_transports(game, sid, 4)
        before = game.to_dict()
        prediction = resolve(32, forces(planet))
        self.assertEqual(game.to_dict(), before)
        population = planet.population
        report = game.invade(sid, pid)
        self.assertTrue(report.captured)
        self.assertEqual(report.rounds, prediction.rounds)
        self.assertEqual((report.attacker_survivors, planet.garrison), (15, 15))
        self.assertEqual((planet.owner, planet.population, forces(planet).militia), (PLAYER, population, 0))
        self.assertFalse(game.ships)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_failed_attack_depletes_garrison_and_militia_across_save_load(self):
        game = scenario()
        sid, pid, planet = fortified_target(game)
        add_transports(game, sid, 3)
        report = game.invade(sid, pid)
        self.assertFalse(report.captured)
        self.assertEqual((planet.garrison, forces(planet).militia, planet.militia_losses), (0, 3, 9))
        self.assertEqual(forces(planet).troops, report.defender_survivors)
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            restored, _ = storage.load(storage.save(game))
        self.assertEqual(restored, game)
        add_transports(restored, sid, 1)
        followup = restored.invade(sid, pid)
        self.assertEqual((followup.garrison, followup.militia), (0, 3))
        self.assertTrue(followup.captured)

    def test_mutual_destruction_retains_colony_without_free_replacements(self):
        game = scenario()
        sid, pid = game.opponent.home_system, game.opponent.home_planet
        planet = game.planet_at(sid, pid)
        planet.population = 4
        add_transports(game, sid, 1)
        report = game.invade(sid, pid)
        self.assertEqual((report.attacker_survivors, report.defender_survivors, report.captured), (0, 0, False))
        self.assertEqual((planet.owner, forces(planet).troops), (RIVAL, 0))
        train(planet)
        self.assertEqual(forces(planet).troops, 1)

    def test_transports_needed_is_the_minimum_winning_force(self):
        planet = scenario().planet_at(0, 2)
        for garrison in (0, 8, 25):
            for bonus in (False, True):
                planet.garrison = garrison
                planet.buildings = ["fortifications"] if bonus else []
                required = transports_needed(planet, TROOP_STRENGTH)
                self.assertTrue(resolve(required*TROOP_STRENGTH, forces(planet)).captured)
                self.assertFalse(resolve((required-1)*TROOP_STRENGTH, forces(planet)).captured)

    def test_invalid_garrisons_casualties_and_duplicate_buildings_rejected(self):
        game = scenario()
        for field, values in (("garrison", (-1, True, 1.5, 100001)), ("militia_losses", (-1, True, 1.5, 105))):
            for value in values:
                data = game.to_dict()
                data["systems"][0]["worlds"][2][field] = value
                with self.subTest(field=field, value=value), self.assertRaises(SaveError):
                    GameState.from_dict(data)
        for building in ("barracks", "fortifications"):
            data = game.to_dict()
            data["systems"][0]["worlds"][2]["buildings"] = [building, building]
            with self.assertRaises(SaveError):
                GameState.from_dict(data)
        data = game.to_dict()
        data["systems"][0]["worlds"][3]["garrison"] = 1
        with self.assertRaises(SaveError):
            GameState.from_dict(data)

    def test_hidden_survey_keeps_last_seen_garrison_and_militia(self):
        game = scenario(fog_of_war=True)
        sid, pid, planet = fortified_target(game)
        planet.militia_losses = 2
        record_survey(game, sid, PLAYER)
        saved = copy.deepcopy(game.exploration.survey(sid).worlds)
        planet.garrison, planet.militia_losses = 3, 7
        observed = game.known_system(sid).worlds[pid]
        self.assertEqual((observed.garrison, observed.militia_losses), (8, 2))
        self.assertEqual(game.exploration.survey(sid).worlds, saved)
        self.assertEqual(GameState.from_dict(game.to_dict()).known_system(sid).worlds[pid], observed)

    def test_invasion_updates_only_participant_surveys(self):
        game = scenario(fog_of_war=True, rival_count=2)
        sid, pid, planet = fortified_target(game)
        record_survey(game, sid, "rival_2")
        observation = copy.deepcopy(game.exploration.survey(sid, "rival_2"))
        add_transports(game, sid, 3)
        game.invade(sid, pid)
        self.assertEqual(game.exploration.survey(sid, "rival_2"), observation)
        for owner in (PLAYER, RIVAL):
            seen = game.exploration.survey(sid, owner).worlds[pid]
            self.assertEqual((seen["garrison"], seen["militia_losses"]), (planet.garrison, planet.militia_losses))


class GroundAITests(unittest.TestCase):
    def test_hidden_ai_war_does_not_publish_ground_reports_or_alerts(self):
        game = scenario(fog_of_war=True, rival_count=2)
        target = game._empire("rival_2")
        sid, pid = target.home_system, target.home_planet
        game.diplomacy_between(RIVAL, "rival_2").relations = -100
        add_transports(game, sid, 2, RIVAL)
        reports = []
        self.assertFalse(game.system_visible(sid))
        self.assertEqual(invasion_orders(game, RIVAL, ground_reports=reports), [])
        self.assertEqual(reports, [])
        self.assertEqual(game.planet_at(sid, pid).owner, RIVAL)
        self.assertIsNone(game.exploration.survey(sid, PLAYER))

    def test_ai_waits_for_enough_transports_against_fortifications(self):
        game = scenario()
        planet = game.planet_at(0, 2)
        planet.buildings, planet.garrison = ["barracks", "fortifications"], 8
        game.diplomacy.relations = -100
        add_transports(game, 0, 3, RIVAL)
        before = game.to_dict()
        self.assertEqual(invasion_orders(game), [])
        self.assertEqual(game.to_dict(), before)
        add_transports(game, 0, 1, RIVAL)
        reports = []
        self.assertTrue(invasion_orders(game, ground_reports=reports))
        self.assertEqual((reports[0].defender, reports[0].attacker_survivors), (PLAYER, 15))
        self.assertEqual(planet.owner, RIVAL)

    def test_turn_report_contains_final_defeat_before_production(self):
        game = scenario()
        game.diplomacy.relations = -100
        add_transports(game, 0, 2, RIVAL)
        report = game.advance_turn()
        self.assertEqual((report.income, report.research, game.turn), (0, 0, 1))
        self.assertEqual(len(report.ground_battles), 1)
        self.assertEqual(report.ground_battles[0].defender, PLAYER)
        self.assertEqual(game.result.winner, RIVAL)

    def test_ai_builds_barracks_and_fortifications_then_trains(self):
        game = scenario()
        game.diplomacy.relations = -100
        home = game.planet_at(game.opponent.home_system, game.opponent.home_planet)
        for _ in range(35):
            game.advance_turn()
        self.assertIn("barracks", home.buildings)
        self.assertIn("fortifications", home.buildings)
        self.assertEqual(home.garrison, 8)

    def test_old_full_shipyard_makes_room_for_barracks(self):
        game = scenario()
        game.diplomacy.relations = -100
        sid, pid = game.opponent.home_system, game.opponent.home_planet
        place_near(game, sid)
        home = game.planet_at(sid, pid)
        # Keep this full colony solvent so military expansion is the priority.
        home.buildings = ["hydroponic_farm", "research_lab"]+["trade_center"]*2+["factory"]*(home.building_capacity-4)
        game.opponent.credits = 300
        run_ai(game)
        self.assertEqual(home.construction_queue[0].item_id, "barracks")
        self.assertIn("hydroponic_farm", home.buildings)
        self.assertIn("research_lab", home.buildings)
        self.assertEqual(home.free_slots, 0)


class GroundInterfaceTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.directory.name), capture=True)
        self.app.game = scenario()
        self.app.window = pg.display.set_mode((980, 900), pg.RESIZABLE)
        self.app.present()

    def click(self, key):
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        self.assertTrue(button.enabled, key)
        self.assertTrue(pg.Rect(0, 0, 1440, 900).contains(button.rect), key)
        x, y = button.rect.center
        v = self.app.viewport
        pos = (round(v.x+x*v.w/1440), round(v.y+y*v.h/900))
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, button=1, pos=pos))
            self.app.render()

    def key(self, key):
        self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=key, mod=0))
        self.app.render()

    def test_preview_cancel_loss_report_and_autosave_through_scaled_controls(self):
        game = self.app.game
        sid, pid, planet = fortified_target(game)
        add_transports(game, sid, 3)
        self.app.open_system(sid)
        self.app.open_planet(pid)
        original = game.to_dict()
        self.click("invade_planet")
        self.assertEqual(self.app.screen, "ground")
        self.app.render()
        self.key(pg.K_e)
        self.assertEqual(game.to_dict(), original)
        self.click("ground_cancel")
        self.assertEqual(game.to_dict(), original)
        self.click("invade_planet")
        self.click("ground_launch")
        self.assertFalse(self.app.ground_reports[0].captured)
        self.assertEqual(forces(planet).troops, 3)
        self.assertEqual(self.app.storage.load(self.app.storage.saves_dir/"autosave.json")[0], game)
        for key in (pg.K_e, pg.K_i, pg.K_r, pg.K_f):
            self.key(key)
            self.assertEqual(self.app.screen, "ground")
        self.click("ground_continue")
        self.assertEqual(self.app.screen, "planet")

    def test_ai_defeat_report_precedes_campaign_result_and_reload_is_committed(self):
        game = self.app.game
        game.diplomacy.relations = -100
        add_transports(game, 0, 2, RIVAL)
        self.app.go("galaxy")
        self.key(pg.K_e)
        self.assertEqual(self.app.screen, "ground")
        self.assertEqual(self.app.ground_reports[0].defender, PLAYER)
        self.app.pause()
        self.app.resume()
        self.app.render()
        self.assertEqual(self.app.screen, "ground")
        self.click("ground_continue")
        self.assertEqual(self.app.screen, "result")
        self.app.load_game(self.app.storage.saves_dir/"autosave.json")
        self.assertEqual(self.app.screen, "result")
        self.assertEqual(self.app.game, game)

    def test_both_buildings_visible_clickable_and_surface_uses_new_art(self):
        game = self.app.game
        game.credits = 500
        self.app.open_planet(2)
        self.app.go("colony")
        self.click("build_barracks")
        self.click("build_fortifications")
        self.assertEqual([q.item_id for q in game.planet_at(0, 2).construction_queue], ["barracks", "fortifications"])
        self.app.go("planet")
        self.click("surface_barracks")
        self.assertEqual(self.app.screen, "colony")
        self.click("cancel_construction")
        self.app.go("planet")
        self.click("surface_fortifications")
        self.assertEqual(self.app.colony_slot, 0)

    def test_multiple_ai_invasions_are_acknowledged_before_final_defeat(self):
        game = self.app.game = scenario(rival_count=2)
        # This fixture covers occupation, while Varkesh raids have their own news flow.
        game.other_opponents["rival_2"].race_id = "aelari"
        system, planet = next((s, p) for s in game.systems[1:] for p in s.worlds
                              if not p.colonized and p.habitability > 0
                              and all(w.owner is None for w in s.worlds))
        planet.colonized, planet.owner, planet.population = True, PLAYER, 8
        for owner, sid in ((RIVAL, 0), ("rival_2", system.id)):
            game.diplomacy_between(PLAYER, owner).relations = -100
            add_transports(game, sid, 2, owner)
        self.app.go("galaxy")
        self.key(pg.K_e)
        self.assertEqual(len(self.app.ground_reports), 2)
        self.assertEqual(self.app.screen, "ground")
        self.click("ground_continue")
        self.assertEqual(len(self.app.ground_reports), 1)
        self.assertEqual(self.app.screen, "ground")
        self.assertEqual(self.app.ground_reports[0].system_id, system.id)
        self.click("ground_continue")
        self.assertEqual(self.app.screen, "result")
        self.assertEqual(game.result.condition, "elimination")
