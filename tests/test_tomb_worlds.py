from scenarios import legacy_research_payload
"""Tomb generation, ground outcomes, private news, turn ordering and save upgrades."""

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

from orion import tomb_worlds as tombs
from orion.exploration import record_survey, refresh
from orion.ground_combat import forces, resolve
from orion.model import ConstructionProject, GameState, RuleError, SaveError, Ship, new_game
from orion.storage import SAVE_VERSION, Storage
from scenarios import empty_fleet_game, place_near


def scenario(**kwargs):
    return empty_fleet_game(seed=2408, fog_of_war=kwargs.pop("fog_of_war", True), **kwargs)


def vault(game, sid=0, pid=3):
    tomb = tombs.TombWorld(sid, pid)
    game.tomb_worlds.append(tomb)
    return tomb


def next_turn(game):
    with patch("orion.tomb_worlds.awakening_due", return_value=True), patch("orion.ai.run_ai", return_value=[]):
        return game.advance_turn()


class GenerationTests(unittest.TestCase):
    def test_generation_is_seeded_without_changing_layout_races_or_fleets(self):
        a = new_game(seed=14, rival_count=5)
        b = new_game(seed=14, rival_count=5)
        off = new_game(seed=14, rival_count=5, with_tombs=False)
        self.assertEqual(a.tomb_worlds, b.tomb_worlds)
        self.assertTrue(a.tomb_worlds)
        self.assertEqual((a.systems, a.ships, a.opponents), (off.systems, off.ships, off.opponents))
        self.assertNotEqual(a.tomb_worlds, new_game(seed=15, rival_count=5).tomb_worlds)
        self.assertEqual(a, GameState.from_dict(a.to_dict()))

    def test_every_world_including_homes_harsh_worlds_and_guardian_prizes_is_eligible(self):
        game = new_game(seed=2408, rival_count=5, with_tombs=False)
        with patch("orion.tomb_worlds.random.Random") as rng:
            rng.return_value.randrange.return_value = 0
            tombs.seed_worlds(game)
            self.assertEqual(rng.return_value.randrange.call_count, sum(s.planets for s in game.systems))
            self.assertTrue(all(call.args == (10,) for call in rng.return_value.randrange.call_args_list))
        self.assertEqual({(t.system_id, t.planet_id) for t in game.tomb_worlds},
                         {(s.id, p.id) for s in game.systems for p in s.worlds})
        refresh(game)
        self.assertFalse(tombs.news(game))
        self.assertTrue(all("tomb" not in key for s in game.exploration.surveys for p in s.worlds for key in p))

    def test_probability_is_one_in_200_and_reload_preserves_future_rolls(self):
        game = scenario()
        tomb = vault(game)
        for roll in (0, 1, 199):
            with patch("orion.tomb_worlds.random.Random") as rng:
                rng.return_value.randrange.return_value = roll
                self.assertEqual(tombs.awakening_due(game, tomb), roll == 0)
                rng.return_value.randrange.assert_called_once_with(200)
        loaded = GameState.from_dict(game.to_dict())
        results = []
        for turn in range(2, 1002):
            game.turn = loaded.turn = turn
            game.year = loaded.year = 2299+turn
            results.append(tombs.awakening_due(game, tomb))
            self.assertEqual(results[-1], tombs.awakening_due(loaded, loaded.tomb_worlds[0]))
        self.assertIn(True, results)
        self.assertIn(False, results)


class AwakeningTests(unittest.TestCase):
    def test_uncolonized_world_joins_existing_remnant_without_ships_or_transports(self):
        game = scenario(rival_race_id="remnant")
        tomb, ships, old_credits = vault(game), game.ships.copy(), game.opponent.credits
        self.assertIsNone(tombs.awaken(game, tomb))
        planet = game.planet_at(0, 3)
        self.assertEqual((planet.owner, planet.colonized, planet.population, planet.garrison), ("rival", True, 2, 16))
        self.assertEqual(game.ships, ships)
        self.assertEqual(game.opponent.credits, old_credits)
        self.assertEqual(tomb.outcome, "founded")
        self.assertEqual(game, GameState.from_dict(game.to_dict()))

    def test_harsh_worlds_have_life_support_and_working_economies(self):
        for biome in ("Barren", "Volcanic", "Desert", "Tundra", "Gaia"):
            game = scenario(with_ai=False)
            tomb = vault(game)
            planet = game.planet_at(0, 3)
            planet.biome = biome
            tombs.awaken(game, tomb)
            refresh(game)
            self.assertIn("hydroponic_farm", planet.buildings)
            self.assertGreater(game.population_report(planet).produced, game.population_report(planet).consumed)
            self.assertGreater(game.planet_yields(planet)[0], 0)
            self.assertEqual(game, GameState.from_dict(game.to_dict()))

    def test_player_remnant_receives_colonies_and_friendly_reinforcements(self):
        game = scenario(race_id="remnant")
        home, remote = vault(game, 0, 2), vault(game)
        game.planet_at(0, 2).garrison = 7
        self.assertIsNone(tombs.awaken(game, home))
        tombs.awaken(game, remote)
        self.assertEqual(game.planet_at(0, 2).garrison, 23)
        self.assertEqual((home.outcome, remote.outcome, remote.remnant_owner), ("reinforced", "founded", "player"))
        self.assertEqual(game.planet_at(0, 3).owner, "player")
        self.assertEqual(len(game.opponents), 1)

    def test_once_only_including_repulsed_and_friendly_awakenings(self):
        for race in ("terran", "remnant"):
            game = scenario(race_id=race)
            tomb = vault(game, 0, 2)
            game.planet_at(0, 2).garrison = 100
            tombs.awaken(game, tomb)
            before = game.to_dict()
            self.assertIsNone(tombs.awaken(game, tomb))
            self.assertEqual(before, game.to_dict())
            with patch("orion.tomb_worlds.awakening_due") as roll:
                tombs.advance(game, [], [])
                roll.assert_not_called()

    def test_capture_uses_existing_ground_rules_and_preserves_civilians_and_paid_projects(self):
        game = scenario(rival_race_id="remnant")
        tomb = vault(game, 0, 2)
        planet = game.planet_at(0, 2)
        planet.buildings = ["research_lab"]
        planet.construction_queue = [ConstructionProject("factory", progress=9)]
        before = (planet.population, planet.farmers, planet.scientists, planet.buildings.copy(), copy.deepcopy(planet.construction_queue))
        expected = resolve(16, forces(planet))
        game.ships = [Ship(1, "frigate", 0)]
        game.next_ship_id = 2
        game.diplomacy.trade_active = game.diplomacy.research_active = True
        report = tombs.awaken(game, tomb)
        self.assertTrue(report.captured)
        self.assertEqual(report.rounds, expected.rounds)
        self.assertEqual((planet.owner, planet.garrison, forces(planet).militia), ("rival", expected.attackers, 0))
        self.assertEqual(before, (planet.population, planet.farmers, planet.scientists, planet.buildings, planet.construction_queue))
        self.assertEqual(len(game.ships), 1)  # Buried armies bypass ships in orbit.
        self.assertEqual((report.transports, report.cause), (0, "tomb"))
        self.assertEqual(game.diplomacy.relations, -100)
        self.assertFalse(game.diplomacy.trade_active or game.diplomacy.research_active)
        game.check_victory()
        self.assertEqual(game.result.winner, "rival")
        self.assertEqual(game, GameState.from_dict(game.to_dict()))

    def test_fortifications_repulse_and_persist_real_casualties(self):
        game = scenario(rival_race_id="remnant")
        tomb = vault(game, 0, 2)
        planet = game.planet_at(0, 2)
        planet.buildings, planet.garrison = ["barracks", "fortifications"], 8
        expected = resolve(16, forces(planet))
        report = tombs.awaken(game, tomb)
        self.assertFalse(report.captured)
        self.assertEqual(report.rounds, expected.rounds)
        self.assertEqual((planet.owner, forces(planet).troops), ("player", expected.defenders))
        self.assertLess(planet.garrison, 8)
        self.assertEqual(game, GameState.from_dict(game.to_dict()))

    def test_successful_capture_destroys_gate_and_queued_gate_only(self):
        for built in (True, False):
            game = scenario(rival_race_id="remnant")
            tomb = vault(game, 0, 2)
            planet = game.planet_at(0, 2)
            planet.ascension_gate, planet.gate_charge = built, 4 if built else 0
            planet.construction_queue = [ConstructionProject("factory")]
            if not built:
                planet.construction_queue.append(ConstructionProject("ascension_gate"))
            tombs.awaken(game, tomb)
            self.assertFalse(planet.ascension_gate)
            self.assertEqual(planet.gate_charge, 0)
            self.assertEqual([p.item_id for p in planet.construction_queue], ["factory"])

    def test_absent_remnant_emerges_only_on_success_and_joins_later_worlds(self):
        game = scenario(with_ai=False)
        home, first, second = vault(game, 0, 2), vault(game, 0, 1), vault(game)
        game.planet_at(0, 2).garrison = 100
        report = tombs.awaken(game, home)
        self.assertIsNone(report.attacker)
        self.assertFalse(game.opponents)
        self.assertIsNone(game.check_victory())
        tombs.awaken(game, first)
        tombs.awaken(game, second)
        self.assertEqual(first.remnant_owner, second.remnant_owner)
        self.assertEqual(len(game.opponents), 1)
        self.assertEqual(game.opponent.race_id, "remnant")
        self.assertFalse(game.ships)
        self.assertEqual(game, GameState.from_dict(game.to_dict()))

    def test_sixth_empire_can_emerge_without_replacing_five_starting_rivals(self):
        game = next(g for seed in range(30) if not tombs.remnant_empire(g := new_game(seed=seed, rival_count=5, with_tombs=False)))
        before = copy.deepcopy(game.opponents)
        tomb = vault(game)
        tombs.awaken(game, tomb)
        self.assertEqual(tomb.remnant_owner, "rival_6")
        self.assertEqual({owner: game.opponents[owner] for owner in before}, before)
        self.assertEqual(len(game.owners), 7)
        self.assertEqual(len(game.other_diplomacy)+1, 21)
        self.assertEqual(game, GameState.from_dict(game.to_dict()))
        next_turn(game)
        self.assertEqual(game, GameState.from_dict(game.to_dict()))

    def test_defeated_remnant_can_reawaken_while_other_empires_are_alive(self):
        game = scenario(rival_count=2, rival_race_id="remnant")
        old = game.planet_at(game.opponent.home_system, game.opponent.home_planet)
        old.owner = "rival_2"
        game.eliminate_defeated()
        self.assertIsNone(game.check_victory())
        tomb = vault(game)
        tombs.awaken(game, tomb)
        self.assertEqual(tomb.remnant_owner, "rival")
        self.assertEqual(len(game.opponents), 2)
        self.assertEqual(game, GameState.from_dict(game.to_dict()))

    def test_guardian_and_prize_survive_awakened_colony_and_save_reload(self):
        game = new_game(seed=2408, with_tombs=False)
        guardian = game.guardians[0]
        tomb = vault(game, guardian.system_id, guardian.planet_id)
        planet = game.planet_at(tomb.system_id, tomb.planet_id)
        original = (guardian.hull, planet.biome, planet.size, planet.richness)
        tombs.awaken(game, tomb)
        refresh(game)
        self.assertEqual((guardian.hull, planet.biome, planet.size, planet.richness), original)
        self.assertEqual(game, GameState.from_dict(game.to_dict()))


class NewsAndTurnTests(unittest.TestCase):
    def test_unexplored_awakening_is_hidden_and_later_visit_does_not_backfill_news(self):
        game = scenario()
        system = next(s for s in game.systems if s.worlds and not game.system_explored(s.id))
        tomb = vault(game, system.id, 0)
        report = next_turn(game)
        self.assertFalse(tombs.news(game))
        self.assertFalse(report.alerts)
        self.assertFalse(report.ground_battles)
        self.assertIsNone(game.known_system(system.id))
        record_survey(game, system.id, "player")
        self.assertFalse(tombs.news(game))
        self.assertNotIn("player", tomb.notified_owners)

    def test_previous_scouting_receives_exact_headline_without_refreshing_remote_intelligence(self):
        game = scenario()
        system = next(s for s in game.systems if s.worlds and not game.system_explored(s.id))
        record_survey(game, system.id, "player")
        survey = copy.deepcopy(game.exploration.survey(system.id))
        tomb = vault(game, system.id, 0)
        report = next_turn(game)
        name = game.planet_at(system.id, 0).name
        self.assertIn(f"Tomb world {name} has awakened as a tomb world of the Remnant.", report.alerts)
        self.assertEqual(tombs.news(game), [tomb])
        self.assertEqual(game.exploration.survey(system.id), survey)
        self.assertEqual(tombs.unread_count(game), 1)
        game.news_read_turn = game.turn
        self.assertEqual(tombs.unread_count(GameState.from_dict(game.to_dict())), 0)

    def test_fog_off_announces_all_awakenings(self):
        game = scenario(fog_of_war=False)
        system = next(s for s in game.systems[1:] if s.worlds and not s.worlds[0].colonized)
        tomb = vault(game, system.id, 0)
        self.assertIn(tombs.headline(game, tomb), next_turn(game).alerts)

    def test_newly_arrived_scout_knows_world_before_awakening(self):
        game = scenario(with_ai=False)
        target = next(s for s in game.systems[1:] if s.worlds)
        place_near(game, target.id)
        game.ships = [Ship(1, "scout", 0)]
        game.next_ship_id = 2
        game.send_ship(1, target.id)
        game.ships[0].turns_remaining = 1
        vault(game, target.id, 0)
        self.assertTrue(next_turn(game).alerts)
        self.assertEqual(len(tombs.news(game)), 1)

    def test_opening_pending_space_combat_does_not_roll_or_advance_tombs(self):
        game = scenario()
        vault(game)
        game.ships = [Ship(1, "frigate", 0), Ship(2, "frigate", 0, owner="rival")]
        game.next_ship_id = 3
        game.diplomacy.relations = -100
        with patch("orion.tomb_worlds.awakening_due") as roll:
            report = game.advance_turn()
            roll.assert_not_called()
        self.assertIsNotNone(game.combat)
        self.assertEqual(game.turn, 1)
        self.assertFalse(report.ground_battles)

    def test_new_colony_produces_only_next_turn_and_event_does_not_repeat(self):
        game = scenario(race_id="remnant", with_ai=False)
        vault(game)
        rates = game.empire_rates
        report = next_turn(game)
        self.assertEqual((report.income, report.research), rates)
        self.assertEqual(game.credits, 120+rates[0])
        self.assertGreater(game.empire_rates[0], rates[0])
        self.assertFalse(next_turn(game).alerts)
        self.assertEqual(len(tombs.news(game)), 1)

    def test_multiple_awakenings_resolve_before_final_elimination(self):
        game = scenario(rival_race_id="remnant")
        home, extra = vault(game, 0, 2), vault(game)
        report = next_turn(game)
        self.assertEqual((home.outcome, extra.outcome), ("captured", "founded"))
        self.assertEqual(len(report.ground_battles), 1)
        self.assertEqual(game.result.winner, "rival")
        self.assertEqual(len(tombs.news(game)), 2)
        self.assertEqual(game, GameState.from_dict(game.to_dict()))
        with self.assertRaises(RuleError):
            game.advance_turn()

    def test_awakening_on_other_empire_only_emits_news_for_player_observers(self):
        game = scenario(rival_race_id="remnant", rival_count=2)
        empire = game.other_opponents["rival_2"]
        tomb = vault(game, empire.home_system, empire.home_planet)
        record_survey(game, tomb.system_id, "player")
        report = next_turn(game)
        self.assertEqual(tomb.outcome, "captured")
        self.assertEqual(len(report.alerts), 1)
        self.assertFalse(report.ground_battles)
        self.assertEqual(game, GameState.from_dict(game.to_dict()))


class SaveTests(unittest.TestCase):
    def test_v21_load_keeps_existing_campaign_without_reseeding_tombs(self):
        game = scenario()
        for owner in game.owners:
            game.research_state(owner).legacy_starships = True
        data = game.to_dict()
        data.pop("tomb_worlds")
        data.pop("news_read_turn")
        legacy_research_payload(data)
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(directory)
            path = storage.saves_dir/"previous.json"
            storage.saves_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"format": "orion-reach", "version": 21,
                                        "saved_at": "2026-10-09T12:00:00+00:00", "game": data}), encoding="utf-8")
            before = path.read_bytes()
            loaded = storage.load(path)[0]
            self.assertEqual(loaded, game)
            self.assertFalse(loaded.tomb_worlds)
            self.assertEqual(path.read_bytes(), before)
            updated = storage.save(loaded)
            self.assertEqual(json.loads(updated.read_text())["version"], SAVE_VERSION)

    def test_invalid_tomb_records_are_rejected(self):
        game = scenario()
        vault(game)
        cases = [lambda d: d["tomb_worlds"].append(copy.deepcopy(d["tomb_worlds"][0])),
                 lambda d: d["tomb_worlds"][0].update(system_id=True),
                 lambda d: d["tomb_worlds"][0].update(planet_id=99),
                 lambda d: d["tomb_worlds"][0].update(awakened_turn=2),
                 lambda d: d["tomb_worlds"][0].update(outcome="captured"),
                 lambda d: d["tomb_worlds"][0].update(notified_owners=["missing"]),
                 lambda d: d.update(news_read_turn=2),
                 lambda d: d.update(news_read_turn=True)]
        for mutate in cases:
            data = game.to_dict()
            mutate(data)
            with self.assertRaises(SaveError):
                GameState.from_dict(data)
        tombs.awaken(game, game.tomb_worlds[0])
        for changes in ({"remnant_owner": "player"}, {"notified_owners": ["player", "player"]},
                        {"defender": "rival"}, {"outcome": "anything"}, {"awakened_turn": False}):
            data = game.to_dict()
            data["tomb_worlds"][0].update(changes)
            with self.assertRaises(SaveError):
                GameState.from_dict(data)


class NewsInterfaceTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.directory.name), capture=True)
        self.app.game = scenario(rival_race_id="remnant")
        self.app.go("galaxy")

    def key(self, key):
        self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=key, mod=0))
        self.app.render()

    def click(self, key):
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        self.assertTrue(button.enabled, key)
        self.assertTrue(pg.Rect(0, 0, 1440, 900).contains(button.rect), key)
        self.app.activate(button)
        self.app.render()

    def advance(self):
        with patch("orion.tomb_worlds.awakening_due", return_value=True), patch("orion.ai.run_ai", return_value=[]):
            self.key(pg.K_e)

    def test_new_news_opens_automatically_can_reopen_and_reload_from_save(self):
        game = self.app.game
        vault(game)
        self.advance()
        self.assertEqual(self.app.screen, "contact")
        self.click("contact_continue")
        self.assertEqual(self.app.screen, "news")
        self.assertEqual(game.news_read_turn, 2)
        self.click("news_back")
        self.click("open_news")
        self.assertEqual(self.app.screen, "news")
        self.click("news_save")
        self.app.load_game(self.app.storage.saves_dir/"autosave.json")
        self.key(pg.K_n)
        self.assertEqual(self.app.screen, "news")
        self.assertEqual(len(tombs.news(self.app.game)), 1)
        self.click("news_system_0_3")
        self.assertEqual(self.app.screen, "system")

    def test_defence_report_precedes_news_and_final_result_remains_accessible(self):
        game = self.app.game
        vault(game, 0, 2)
        self.advance()
        self.assertEqual(self.app.screen, "ground")
        self.assertEqual(self.app.ground_reports[0].cause, "tomb")
        self.assertEqual(game.result.winner, "rival")
        self.key(pg.K_e)
        self.assertEqual(game.turn, 2)
        self.click("ground_continue")
        self.assertEqual(self.app.screen, "news")
        self.assertFalse(next(b for b in self.app.buttons if b.key == "news_end_turn").enabled)
        self.click("news_back")
        self.assertEqual(self.app.screen, "result")
        self.click("result_news")
        self.assertEqual(self.app.screen, "news")
        loaded = self.app.storage.load(self.app.storage.saves_dir/"autosave.json")[0]
        self.assertEqual(loaded.result, game.result)
        self.assertEqual(loaded.tomb_worlds, game.tomb_worlds)

    def test_repulsed_vault_with_no_remnant_empire_has_renderable_ground_report(self):
        self.app.game = scenario(with_ai=False)
        game = self.app.game
        vault(game, 0, 2)
        planet = game.planet_at(0, 2)
        planet.buildings, planet.garrison = ["barracks", "fortifications"], 8
        self.advance()
        self.assertEqual(self.app.screen, "ground")
        self.assertIsNone(self.app.ground_reports[0].attacker)
        self.click("ground_continue")
        self.assertEqual(self.app.screen, "news")
        self.assertIsNone(game.result)

    def test_news_pagination_and_keyboard_keep_all_reports_reachable(self):
        game = self.app.game
        for pid in (0, 1, 3):
            tombs.awaken(game, vault(game, 0, pid))
        target = next(s for s in game.systems[1:] if s.worlds and s.id != game.opponent.home_system)
        record_survey(game, target.id, "player")
        tombs.awaken(game, vault(game, target.id, 0))
        self.key(pg.K_n)
        self.assertEqual(len(tombs.news(game)), 4)
        self.click("news_next")
        self.assertEqual(self.app.news_page, 1)
        self.key(pg.K_PAGEUP)
        self.assertEqual(self.app.news_page, 0)
        self.key(pg.K_ESCAPE)
        self.assertEqual(self.app.screen, "galaxy")

    def test_space_battle_defers_news_until_combat_is_acknowledged(self):
        from orion.combat import autoresolve
        game = self.app.game
        tombs.awaken(game, vault(game))
        game.ships = [Ship(1, "frigate", 0), Ship(2, "frigate", 0, owner="rival")]
        game.next_ship_id = 3
        game.start_combat(0)
        self.app.go("news")
        self.assertEqual(self.app.screen, "combat")
        self.assertEqual(game.news_read_turn, 0)
        autoresolve(game)
        self.app.finish_combat()
        self.app.render()
        self.assertEqual(self.app.screen, "contact")
        self.click("contact_continue")
        self.assertEqual(self.app.screen, "news")
        self.assertEqual(game.news_read_turn, game.turn)
