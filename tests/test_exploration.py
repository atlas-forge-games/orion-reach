from scenarios import legacy_research_payload
from scenarios import legacy_economy
"""Fog boundaries, scout discoveries, knowledge persistence and actual UI flows."""

import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame as pg

from orion.exploration import DISCOVERIES, discovery_at, known_rival_colonies, refresh
from orion.model import GameState, PLAYER, RIVAL, RuleError, SaveError, Ship
from scenarios import empty_fleet_game as new_game, place_near
from orion.storage import SAVE_VERSION, Storage


def discovery_system(game, kind=None):
    candidates = [s for s in game.systems if discovery_at(game, s.id) and
                (kind is None or discovery_at(game, s.id) == kind) and
                (game.opponent is None or s.id != game.opponent.home_system)]
    target = min(candidates, key=lambda s: game.supply_distance(s.id))
    if not game.within_fuel_range(target.id):
        place_near(game, target.id)  # A local discovery fixture, not an unlimited-range order.
    return target


def arrive(game, ids, destination):
    duration = game.send_ships(ids, destination)
    for _ in range(duration):
        report = game.advance_turn()
    return duration, report


class ExplorationRulesTests(unittest.TestCase):
    def test_new_game_knowledge_is_private_and_fog_option_does_not_change_galaxy(self):
        hidden = new_game(seed=2408)
        revealed = new_game(seed=2408, fog_of_war=False)
        self.assertTrue(hidden.fog_of_war)
        self.assertEqual(hidden.systems, revealed.systems)
        self.assertEqual({s.id for s in hidden.systems if hidden.system_explored(s.id)}, {0})
        home = hidden.opponent.home_system
        self.assertEqual({s.id for s in hidden.systems if hidden.system_explored(s.id, RIVAL)}, {home})
        self.assertTrue(all(revealed.system_visible(s.id) for s in revealed.systems))
        self.assertEqual(hidden.exploration.discoveries, [])
        self.assertEqual(hidden.ships, [])
        for setting in (None, 0, "false", []):
            with self.assertRaises(SaveError):
                new_game(seed=1, fog_of_war=setting)

    def test_any_ship_surveys_only_on_arrival_but_only_scouts_recover_discoveries(self):
        game = new_game(seed=2408, with_ai=False)
        target = discovery_system(game)
        game.ships = [Ship(1, "frigate", 0), Ship(2, "scout", 0)]
        game.next_ship_id = 3
        duration = game.send_ship(1, target.id)
        self.assertFalse(game.system_explored(target.id))
        self.assertIsNone(game.known_system(target.id))
        for _ in range(duration-1):
            game.advance_turn()
            self.assertFalse(game.system_explored(target.id))
        report = game.advance_turn()
        self.assertTrue(game.system_explored(target.id))
        self.assertTrue(any(target.name in s for s in report.exploration))
        self.assertEqual(game.exploration.discoveries, [])
        arrive(game, [2], target.id)
        self.assertEqual(len(game.exploration.discoveries), 1)

    def test_scout_production_cost_hull_role_and_shared_queue(self):
        game = new_game(seed=2408, with_ai=False)
        earth = game.planet_at(0, 2)
        game.queue_ship(0, 2, "scout")
        self.assertEqual(game.credits, 120)
        self.assertEqual(game.queue_estimates(earth), [2])
        self.assertEqual(earth.used_slots, 0)
        game.advance_turn()
        self.assertEqual(game.ships, [])
        game.advance_turn()
        ship = game.ships[0]
        self.assertEqual((ship.kind, ship.hull, ship.damage), ("scout", 8, 0))
        with self.assertRaises(RuleError):
            game.colonize(ship.id, 0, 3)
        self.assertEqual(game.exploration.discoveries, [])

    def test_all_discovery_rewards_apply_once_even_with_fog_off_or_multiple_scouts(self):
        for fog in (False, True):
            for kind, spec in DISCOVERIES.items():
                with self.subTest(fog=fog, kind=kind):
                    game = new_game(seed=2408, with_ai=False, fog_of_war=fog)
                    target = discovery_system(game, kind)
                    game.ships = [Ship(1, "scout", 0), Ship(2, "scout", 0)]
                    game.next_ship_id = 3
                    baseline = GameState.from_dict(game.to_dict())
                    duration, report = arrive(game, [1, 2], target.id)
                    for _ in range(duration):
                        baseline.advance_turn()
                    self.assertEqual(game.credits, baseline.credits+spec.credits)
                    self.assertEqual(game.research, spec.research)
                    self.assertEqual(len(game.exploration.discoveries), 1)
                    self.assertTrue(any(spec.name in s for s in report.exploration))
                    bank = game.research
                    game.advance_turn()
                    self.assertEqual(game.research, bank)
                    arrive(game, [1, 2], 0)
                    before = game.credits
                    duration = game.send_ships([1, 2], target.id)
                    for _ in range(duration):
                        before += game.empire_rates[0]  # Tax income includes natural growth.
                        game.advance_turn()
                    self.assertEqual(game.credits, before)
                    self.assertEqual(len(game.exploration.discoveries), 1)
                    self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_research_discovery_completes_active_project_and_preserves_overflow(self):
        game = new_game(seed=2408, with_ai=False)
        target = discovery_system(game, "ancient_archive")
        from orion.research import TECHNOLOGIES
        game.research = TECHNOLOGIES["automated_factories"].cost-25
        game.choose_research("automated_factories")
        game.ships = [Ship(1, "scout", 0)]
        game.next_ship_id = 2
        _, report = arrive(game, [1], target.id)
        self.assertIn("automated_factories", game.technology.completed)
        self.assertEqual(game.research, 5)
        self.assertTrue(report.discoveries)

    def test_stale_surveys_do_not_update_ownership_population_buildings_or_fleets(self):
        game = new_game(seed=2408)
        home = game.opponent.home_system
        place_near(game, home)
        planet = game.planet_at(home, game.opponent.home_planet)
        game.ships = [Ship(1, "scout", home), Ship(2, "frigate", home, owner=RIVAL)]
        game.next_ship_id = 3
        refresh(game)
        self.assertEqual([s.id for s in game.visible_ships()], [1, 2])
        game.send_ship(1, 0)
        self.assertTrue(game.system_visible(home))  # Departure is still editable.
        with patch("orion.ai.run_ai", return_value=[]):
            game.advance_turn()
        planet.population = 19
        planet.buildings.append("factory")
        self.assertFalse(game.system_visible(home))
        known = game.known_system(home).worlds[planet.id]
        self.assertEqual(known.population, 8)
        self.assertEqual(known.buildings, [])
        self.assertEqual([s.id for s in game.visible_ships()], [1])
        with patch("orion.ai.run_ai", return_value=[]):
            while game.ship_at(1).in_transit:
                game.advance_turn()
        self.assertEqual(game.known_system(home).worlds[planet.id].population, 8)
        with patch("orion.ai.run_ai", return_value=[]):
            arrive(game, [1], home)
        self.assertEqual(game.known_system(home).worlds[planet.id].population, 19)
        game.send_ship(2, 0, owner=RIVAL)
        with patch("orion.ai.run_ai", return_value=[]):
            game.advance_turn()
        self.assertNotIn(2, [s.id for s in game.visible_ships()])
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_enemy_expansion_stays_hidden_until_observed(self):
        game = new_game(seed=2408)
        remote = next(s for s in game.systems[1:] if s.id != game.opponent.home_system and s.worlds)
        self.assertIsNone(game.known_system(remote.id))
        world = remote.worlds[0]
        world.owner, world.colonized, world.population = RIVAL, True, 1
        refresh(game)
        self.assertEqual(known_rival_colonies(game), [])
        game.ships = [Ship(1, "scout", remote.id)]
        game.next_ship_id = 2
        refresh(game)
        self.assertEqual([(s.id, p.id) for s, p in known_rival_colonies(game)], [(remote.id, 0)])

    def test_first_scout_claim_is_shared_between_empires_and_survives_reload(self):
        game = new_game(seed=2408)
        target = discovery_system(game)
        game.ships = [Ship(1, "scout", target.id, owner=RIVAL), Ship(2, "scout", target.id)]
        game.next_ship_id = 3
        refresh(game, recover=True)
        self.assertEqual(len(game.exploration.discoveries), 1)
        self.assertEqual(game.exploration.discoveries[0].owner, RIVAL)
        self.assertEqual(game.credits, 120)
        restored = GameState.from_dict(game.to_dict())
        bank = (restored.credits, restored.research, restored.opponent.credits, restored.opponent.research)
        refresh(restored, recover=True)
        self.assertEqual(bank, (restored.credits, restored.research, restored.opponent.credits, restored.opponent.research))

    def test_scout_combat_and_lost_visibility_round_trip(self):
        game = new_game(seed=2408)
        home = game.opponent.home_system
        game.ships = [Ship(1, "scout", home), Ship(2, "frigate", home, owner=RIVAL)]
        game.next_ship_id = 3
        refresh(game, recover=True)
        self.assertIn("unarmed", game.engagement_error(home).lower())
        game.start_combat(home, RIVAL)
        for _ in range(20):
            if game.combat.status != "active":
                break
            if game.combat.active_owner == RIVAL:
                game.combat_ai_action()
            else:
                game.combat_end_turn()
        self.assertEqual(game.combat.status, "rival_victory")
        self.assertFalse(game.system_visible(home))
        self.assertIsNotNone(game.known_system(home))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_ai_uses_scouts_and_known_targets_and_resumes_deterministically(self):
        from orion.ai import available_worlds
        game = new_game(seed=172)  # Naturally has two stars within the rival's initial range.
        hidden = next(s for s in game.systems if s.id != game.opponent.home_system)
        self.assertEqual(available_worlds(game, hidden), [])
        for _ in range(55):  # Mining and power infrastructure also precede expansion.
            game.advance_turn()
        self.assertTrue(any(s.kind == "scout" for s in game.ships_owned_by(RIVAL)))
        self.assertGreater(len(game.exploration.scanned_rival), 2)
        self.assertGreater(sum(p.owner == RIVAL for s in game.systems for p in s.worlds), 1)
        clone = GameState.from_dict(game.to_dict())
        for _ in range(15):
            if game.result:
                break
            self.assertEqual(game.advance_turn(), clone.advance_turn())
            self.assertEqual(game, clone)
        self.assertEqual(sum(s.owner == PLAYER for s in game.exploration.surveys), 1)

    def test_old_v9_save_keeps_revealed_map_assets_and_original_file(self):
        game = new_game(seed=2408, fog_of_war=False)
        game.ships = [Ship(1, "frigate", 0, hull=13), Ship(2, "colony_ship", 0)]
        game.next_ship_id = 3
        place_near(game, 1)
        game.send_ship(2, 1)
        game.ship_at(2).departure_pending = False  # Legacy journeys were committed immediately.
        game.queue_building(0, 2, "factory")
        legacy_economy(game)
        with tempfile.TemporaryDirectory() as folder:
            store = Storage(folder)
            path = store.save(game)
            payload = json.loads(path.read_text())
            payload["version"] = 9
            legacy_research_payload(payload)
            payload["game"].pop("fog_of_war")
            payload["game"].pop("exploration")
            path.write_text(json.dumps(payload))
            original = path.read_bytes()
            restored, _ = store.load(path)
            self.assertEqual(restored, game)
            self.assertEqual(path.read_bytes(), original)
            self.assertFalse(restored.fog_of_war)
            self.assertEqual(json.loads(store.save(restored).read_text())["version"], SAVE_VERSION)

    def test_invalid_fog_surveys_scans_and_duplicate_claims_are_rejected(self):
        game = new_game(seed=2408)
        target = discovery_system(game)
        game.ships = [Ship(1, "scout", target.id)]
        game.next_ship_id = 2
        refresh(game, recover=True)
        def bad_fog(d): d["fog_of_war"] = "false"
        def missing(d): d.pop("exploration")
        def duplicate_survey(d): d["exploration"]["surveys"].append(copy.deepcopy(d["exploration"]["surveys"][0]))
        def future(d): d["exploration"]["surveys"][0]["last_seen"] = game.turn+1
        def malformed(d): d["exploration"]["surveys"][0]["worlds"] = []
        def duplicate_scan(d): d["exploration"]["scanned_player"] *= 2
        def duplicate_find(d): d["exploration"]["discoveries"] *= 2
        def unknown_kind(d): d["exploration"]["discoveries"][0]["kind"] = "money_printer"
        for mutate in (bad_fog, missing, duplicate_survey, future, malformed, duplicate_scan, duplicate_find, unknown_kind):
            with self.subTest(mutate=mutate.__name__):
                data = game.to_dict()
                mutate(data)
                with self.assertRaises(SaveError):
                    GameState.from_dict(data)

    def test_adding_a_rival_after_a_discovery_cannot_invalidate_the_save(self):
        for seed in range(50):
            game = new_game(seed=seed, with_ai=False)
            home, _ = game.opponent_home()
            if discovery_at(game, home.id):
                break
        self.assertIsNotNone(discovery_at(game, home.id))
        game.ships = [Ship(1, "scout", home.id)]
        game.next_ship_id = 2
        refresh(game, recover=True)
        game.add_opponent()
        self.assertEqual(len(game.exploration.discoveries), 1)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)


class ExplorationInterfaceTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.tmp.name), capture=True)
        self.app.game = new_game(seed=2408, with_ai=False)
        self.app.go("galaxy")
        self.app.window = pg.display.set_mode((980, 900), pg.RESIZABLE)
        self.app.render()
        self.app.present()

    def click(self, key):
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        x, y = button.rect.center
        v = self.app.viewport
        position = round(v.x+x*v.w/1440), round(v.y+y*v.h/900)
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, button=1, pos=position))
            self.app.render()

    def key(self, key):
        self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=key, mod=0))
        self.app.render()

    def drawn_text(self):
        from orion.ui import text_image
        with patch("orion.ui.text_image", wraps=text_image) as render_text:
            self.app.render()
        return "\n".join(str(c.args[0]) for c in render_text.call_args_list)

    def test_setup_toggle_is_saved_and_new_games_default_to_fog_on(self):
        self.app.go("setup")
        self.assertTrue(self.app.fog_of_war)
        self.click("fog_of_war")
        self.click("launch")
        self.assertFalse(self.app.game.fog_of_war)
        restored, _ = self.app.storage.load(self.app.storage.saves_dir/"autosave.json")
        self.assertFalse(restored.fog_of_war)
        self.app.go("setup")
        self.click("fog_of_war")
        self.click("launch")
        self.assertTrue(self.app.game.fog_of_war)
        self.assertEqual(sum(self.app.game.system_explored(s.id) for s in self.app.game.systems), 1)

    def test_build_scout_explore_find_and_reload_using_real_controls(self):
        self.key(pg.K_x)
        self.click("exploration_build_scout")
        self.click("build_scout")
        self.key(pg.K_e)
        self.key(pg.K_e)
        self.click("research_back")
        self.assertEqual(self.app.screen, "planet")
        self.click("planet_return")
        self.assertEqual(self.app.screen, "galaxy")
        self.click("map_fleet_1")
        target = discovery_system(self.app.game)
        self.click(f"star_{target.id}")
        self.assertFalse(self.app.game.system_explored(target.id))
        while self.app.game.ships[0].has_course:
            self.key(pg.K_e)
        self.click("research_back")
        self.assertTrue(self.app.game.system_explored(target.id))
        self.assertEqual(len(self.app.game.exploration.discoveries), 1)
        self.key(pg.K_x)
        self.assertEqual(self.app.screen, "exploration")
        self.assertIn(DISCOVERIES[discovery_at(self.app.game, target.id)].name, self.drawn_text())
        saved = self.app.storage.saves_dir/"autosave.json"
        before = self.app.game.to_dict()
        self.app.load_game(saved)
        self.assertEqual(before, self.app.game.to_dict())
        self.key(pg.K_x)
        self.click(f"discovery_system_{target.id}")
        self.assertEqual(self.app.screen, "system")

    def test_unknown_system_has_no_planets_or_backdoor_to_colony_screens(self):
        self.app.game = new_game(seed=2408)
        game = self.app.game
        sid = game.opponent.home_system
        secret = game.planet_at(sid, game.opponent.home_planet).name
        self.click(f"star_{sid}")
        self.assertEqual(self.app.screen, "galaxy")
        self.assertFalse(any(b.key.startswith("galaxy_world_") for b in self.app.buttons))
        self.assertNotIn(secret, self.drawn_text())
        self.click("open_system")
        self.assertEqual(self.app.screen, "system")
        self.assertFalse(any(b.key.startswith("world_") for b in self.app.buttons))
        self.assertNotIn(secret, self.drawn_text())
        self.app.open_planet(game.opponent.home_planet)
        self.assertEqual(self.app.screen, "system")
        game.selected_planet = game.opponent.home_planet
        self.app.go("colony")
        self.assertEqual(self.app.screen, "system")
        self.key(pg.K_RIGHT)
        self.assertNotIn(secret, self.drawn_text())

    def test_rival_map_report_and_objectives_do_not_leak_hidden_locations_or_totals(self):
        self.app.game = new_game(seed=2408)
        game = self.app.game
        sid = game.opponent.home_system
        secret = game.planet_at(sid, game.opponent.home_planet).name
        game.opponent.credits = 876543
        game.ships = [Ship(1, "frigate", sid, owner=RIVAL)]
        game.next_ship_id = 2
        self.app.render()
        self.assertFalse(any(b.key.startswith("map_fleet_") for b in self.app.buttons))
        self.app.open_map_fleet(1)
        self.assertEqual(self.app.screen, "galaxy")
        self.app.open_rival()
        text = self.drawn_text()
        self.assertNotIn(secret, text)
        self.assertNotIn("876,543", text)
        self.assertFalse(any(b.key.startswith("rival_colony_") for b in self.app.buttons))
        self.app.open_objectives()
        self.assertNotIn(secret, self.drawn_text())

    def test_last_known_planet_is_read_only_and_keeps_old_population(self):
        self.app.game = new_game(seed=2408)
        game = self.app.game
        sid, pid = game.opponent.home_system, game.opponent.home_planet
        game.ships = [Ship(1, "scout", sid)]
        game.next_ship_id = 2
        refresh(game)
        game.send_ship(1, 0)
        with patch("orion.ai.run_ai", return_value=[]):
            game.advance_turn()
        game.planet_at(sid, pid).population = 77
        self.app.open_system(sid)
        self.click(f"world_{pid}")
        text = self.drawn_text()
        self.assertIn("8 B inhabitants", " ".join(text.split()))
        self.assertNotIn("77", text)
        self.assertFalse(next(b for b in self.app.buttons if b.key == "surface_shipyard").enabled)
        self.assertFalse(any(b.key in ("planet_change", "planet_buy") for b in self.app.buttons))
        self.app.go("shipyard")
        self.assertEqual(self.app.screen, "planet")
        self.assertFalse(any(b.key == "invade_planet" for b in self.app.buttons))

    def test_route_preview_has_no_planet_or_fleet_intelligence_before_arrival(self):
        self.app.game = new_game(seed=2408)
        game = self.app.game
        home = game.opponent.home_system
        place_near(game, home)
        game.ships = [Ship(1, "scout", 0), Ship(2, "frigate", home, owner=RIVAL)]
        game.next_ship_id = 3
        self.click("map_fleet_1")
        self.app.keyboard_mode = True
        game.selected_system = home
        text = self.drawn_text()
        self.assertIn("Planets unknown", text)
        self.assertNotIn("1 rival ships", text)
        self.assertNotIn(game.planet_at(home, game.opponent.home_planet).name, text)
        self.key(pg.K_ESCAPE)
        self.assertTrue(all(not s.in_transit for s in game.ships))

    def test_exploration_and_fleet_navigation_to_other_overviews_returns_safely(self):
        self.app.game.ships = [Ship(1, "scout", 0)]
        self.app.game.next_ship_id = 2
        for origin in ("exploration", "galaxy"):
            if origin == "galaxy":
                self.app.open_map_fleet(1)
            else:
                self.app.open_exploration()
            for key in (pg.K_i, pg.K_r, pg.K_f, pg.K_d, pg.K_v):
                self.key(key)
                self.key(pg.K_ESCAPE)
                self.assertEqual(self.app.screen, origin)
            self.key(pg.K_ESCAPE)


if __name__ == "__main__":
    unittest.main()
