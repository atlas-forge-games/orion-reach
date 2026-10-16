"""Observer isolation, independent AI play, save compatibility and UI controls."""

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

from orion import combat, first_contact, news, tomb_worlds
from orion.model import GameState, RuleError, SaveError, Ship, new_game
from orion.observer import MAX_EVENTS
from orion.races import RACES, SETUP_RACES
from orion.storage import Storage
from orion.research import TECHNOLOGIES
from orion.ui import text_image
from orion.victory import current_result, LEGACY_CONDITIONS


def observation(**kwargs):
    settings = dict(seed=2408, race_id="observer", rival_count=3, with_guardians=False, with_tombs=False)
    settings.update(kwargs)
    return new_game(**settings)


class ObserverRulesTests(unittest.TestCase):
    def test_observer_is_not_an_empire_or_a_random_rival(self):
        self.assertIn("observer", SETUP_RACES)
        self.assertNotIn("observer", RACES)
        game = observation(rival_count=5)
        self.assertEqual(len(game.owners), 5)
        self.assertNotIn("player", game.owners)
        self.assertEqual(len({e.race_id for e in game.opponents.values()}), 5)
        self.assertFalse(any(e.race_id == "observer" for e in game.opponents.values()))
        self.assertFalse(game.colony_systems("player"))
        self.assertFalse(game.ships_owned_by("player"))
        self.assertEqual((game.credits, game.resources, game.research), (0, 0, 0))
        self.assertIsNone(game.diplomacy)
        self.assertTrue(all("player" not in key for key in game.other_diplomacy))
        self.assertIsNone(current_result(game))
        self.assertFalse(first_contact.pending(game))
        self.assertEqual(first_contact.known_opponents(game), list(game.opponents))
        for owner, empire in game.opponents.items():
            home = game.planet_at(empire.home_system, empire.home_planet)
            self.assertEqual(home.owner, owner)
            self.assertEqual(home.name, RACES[empire.race_id].homeworld)
            self.assertEqual(game.systems[empire.home_system].name, RACES[empire.race_id].home_system)
            self.assertGreaterEqual(len(game.ships_owned_by(owner)), 3)

    def test_setup_limits_and_observer_rival_are_validated(self):
        for count in (0, 1, 6, True):
            with self.assertRaises(SaveError):
                observation(rival_count=count)
        for count in (2, 5):
            self.assertEqual(len(observation(rival_count=count).owners), count)
        with self.assertRaises(SaveError):
            new_game(rival_race_id="observer")
        self.assertEqual(len(new_game(race_id="observer", seed=24).owners), 3)

    def test_full_observer_visibility_does_not_give_ai_extra_intelligence(self):
        game = observation(fog_of_war=True)
        before = game.to_dict()
        self.assertTrue(all(game.system_visible(s.id) for s in game.systems))
        self.assertTrue(all(game.known_system(s.id) is s for s in game.systems))
        self.assertEqual(game.visible_ships(), game.ships)
        for owner in game.owners:
            self.assertTrue(any(game.known_system(s.id, owner) is None for s in game.systems))
            self.assertLess(len(game.visible_ships(owner)), len(game.ships))
        self.assertEqual(game.to_dict(), before)
        game.fog_of_war = False
        self.assertTrue(all(game.system_explored(s.id, "rival") for s in game.systems))

    def test_player_orders_are_blocked_but_ai_research_is_allowed(self):
        game = observation()
        sid, pid = game.opponent.home_system, game.opponent.home_planet
        before = game.to_dict()
        actions = [lambda: game.choose_research("targeting_computers"),
                   lambda: game.save_design("Hidden orders", "frigate", ["laser"]),
                   lambda: game.set_workforce(sid, pid, 1, 1),
                   lambda: game.queue_building(sid, pid, "factory"),
                   lambda: game.diplomacy_action("envoy"),
                   lambda: game.add_opponent(),
                   lambda: game.send_ship(game.ships[0].id, (sid+1)%len(game.systems))]
        for action in actions:
            with self.assertRaises(RuleError):
                action()
        self.assertEqual(game.to_dict(), before)
        self.assertFalse(game.can_settle(game.planet_at(sid, pid)))
        self.assertIsNone(game.research_error("civil_engineering", owner="rival"))
        game.choose_research("civil_engineering", owner="rival")
        self.assertEqual(game.opponent.technology.active, "civil_engineering")

    def test_ai_ground_invasion_can_end_an_observed_campaign(self):
        game = observation(seed=13, rival_count=2, rival_race_id="terran")
        defender = game.opponents["rival_2"]
        sid, pid = defender.home_system, defender.home_planet
        game.ships = [Ship(i, "troop_transport", sid, owner="rival") for i in range(1, 9)]
        game.next_ship_id = 9
        report = game.invade(sid, pid, owner="rival")
        self.assertTrue(report.captured)
        self.assertEqual(game.result.winner, "rival")
        self.assertIsNone(game.combat)
        self.assertEqual(GameState.from_dict(game.to_dict()).to_dict(), game.to_dict())

    def test_all_empires_take_turns_and_save_resume_is_deterministic(self):
        game = observation(with_guardians=True, with_tombs=True)
        restored = GameState.from_dict(game.to_dict())
        with patch("orion.ai.run_ai", wraps=__import__("orion.ai", fromlist=["run_ai"]).run_ai) as ai:
            game.advance_turn()
            self.assertEqual([c.args[1] for c in ai.call_args_list], list(restored.owners))
        restored.advance_turn()
        for _ in range(24):
            self.assertEqual(game.advance_turn(), restored.advance_turn())
        self.assertEqual(game.to_dict(), restored.to_dict())
        self.assertEqual(game.turn, 26)
        self.assertIsNone(game.result)
        self.assertIsNone(game.combat)
        self.assertTrue(any(p.buildings for s in game.systems for p in s.worlds))
        self.assertTrue(game.observer_events)
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            loaded, _ = storage.load(storage.save(game))
            self.assertEqual(loaded.to_dict(), game.to_dict())
            self.assertTrue(loaded.is_observer)

    def test_ai_space_battle_resolves_without_human_input(self):
        game = observation(rival_count=2)
        sid = game.opponent.home_system
        game.ships = [Ship(1, "frigate", sid, owner="rival"), Ship(2, "scout", sid, owner="rival_2")]
        game.next_ship_id = 3
        game.diplomacy_between("rival", "rival_2").relations = -100
        self.assertFalse(combat.intercept(game))
        self.assertIsNone(game.combat)
        self.assertTrue(any("battle" in e.message.lower() or "retreated" in e.message for e in game.observer_events))
        self.assertEqual(GameState.from_dict(game.to_dict()).to_dict(), game.to_dict())
        game.advance_turn()
        self.assertEqual(game.turn, 2)

    def test_tomb_emergence_adds_a_real_empire_and_observer_gets_news(self):
        for seed in range(20):
            game = observation(seed=seed, rival_count=5)
            if all(e.race_id != "remnant" for e in game.opponents.values()):
                break
        else:
            self.fail("Could not find a setup without the Remnant")
        sid, pid = next((s.id, p.id) for s in game.systems for p in s.worlds if not p.colonized)
        tomb = tomb_worlds.TombWorld(sid, pid)
        game.tomb_worlds.append(tomb)
        tomb_worlds.awaken(game, tomb)
        self.assertIn("rival_6", game.owners)
        self.assertNotIn("player", tomb.notified_owners)
        self.assertIn(tomb, tomb_worlds.news(game))
        self.assertTrue(any(e.category == "REMNANT AWAKENING" for e in news.entries(game)))
        self.assertEqual(GameState.from_dict(game.to_dict()).to_dict(), game.to_dict())

    def test_only_actual_empires_can_win_and_observer_is_never_eliminated(self):
        game = observation(rival_count=2)
        self.assertIsNone(game.check_victory())
        for system in game.systems:
            for planet in system.worlds:
                if planet.owner == "rival_2":
                    planet.owner = "rival"
        game.check_victory()
        self.assertEqual((game.result.winner, game.result.condition), ("rival", "conquest"))
        with self.assertRaises(RuleError):
            game.advance_turn()
        self.assertEqual(GameState.from_dict(game.to_dict()).result, game.result)

    def test_journal_is_bounded_and_new_same_turn_events_become_unread(self):
        game = observation()
        news.mark_read(game)
        self.assertEqual(news.unread_count(game), 0)
        for i in range(MAX_EVENTS+5):
            game.rival_event(f"Observation {i}.", owner="rival")
        self.assertEqual(len(game.observer_events), MAX_EVENTS)
        self.assertEqual(news.unread_count(game), MAX_EVENTS)
        restored = GameState.from_dict(game.to_dict())
        self.assertEqual(news.entries(restored), news.entries(game))
        news.mark_read(restored)
        self.assertEqual(news.unread_count(restored), 0)

    def test_science_victory_and_simultaneous_ascension_belong_to_computers(self):
        from orion.research import BRANCHES, branch_tiers, choices
        game = observation(rival_count=2)
        for owner in game.owners:
            for branch in BRANCHES:
                for tier in branch_tiers(branch):
                    technology = choices(branch, tier)[0]
                    game._empire(owner).research += technology.cost
                    game.choose_research(technology.id, owner=owner)
            game._empire(owner).research += TECHNOLOGIES["ascension_theory"].cost
            game.choose_research("ascension_theory", owner=owner)
            world = game.headquarters(owner)[1]
            world.ascension_gate, world.gate_charge = True, 5
            expected = current_result(game)
            self.assertEqual(expected.condition, "science")
            self.assertEqual(expected.winner, "rival" if owner == "rival" else None)
        game.check_victory()
        self.assertEqual(GameState.from_dict(game.to_dict()).result, game.result)

    def test_invalid_observer_saves_are_rejected(self):
        game = observation()
        original = game.to_dict()
        changes = [lambda d: d.update(credits=1), lambda d: d.update(resources=1),
                   lambda d: d["ships"][0].update(owner="player"),
                   lambda d: d["opponent"].update(race_id="observer"),
                   lambda d: d["observer_events"][0].update(owner="player"),
                   lambda d: d["observer_events"][0].update(id=0),
                   lambda d: d.update(observer_news_read=d["next_observer_event_id"]),
                   lambda d: d.update(next_observer_event_id=True)]
        for change in changes:
            data = copy.deepcopy(original)
            change(data)
            with self.assertRaises(SaveError):
                GameState.from_dict(data)

    def test_v039_saves_remain_normal_player_campaigns(self):
        game = new_game(seed=2408, rival_race_id="kharuun", with_tombs=False, with_black_holes=False,
                        victory_conditions=LEGACY_CONDITIONS)
        for owner in game.owners:
            game.research_state(owner).legacy_arsenal = True
            game.research_state(owner).legacy_fuel = True
            game.research_state(owner).legacy_black_holes = True
        data = game.to_dict()
        for empire in [data, data["opponent"], *data["other_opponents"].values()]:
            if empire:
                empire["technology"].pop("legacy_arsenal")
                empire["technology"].pop("legacy_fuel")
                empire["technology"].pop("legacy_black_holes")
        for key in ("observer_events", "next_observer_event_id", "observer_news_read"):
            del data[key]
        restored = GameState.from_dict(data, version=29)
        self.assertFalse(restored.is_observer)
        self.assertEqual(restored.to_dict(), game.to_dict())


class ObserverInterfaceTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.folder.name), capture=True)
        self.addCleanup(self.app.audio.close)
        self.app.game = observation()
        self.app.go("galaxy")
        self.app.present()

    def click(self, key):
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        self.assertTrue(button.enabled, key)
        viewport = self.app.viewport
        pos = (viewport.x+round(button.rect.centerx*viewport.w/1440),
               viewport.y+round(button.rect.centery*viewport.h/900))
        for event in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(event, button=1, pos=pos))
            self.app.render()

    def test_observer_can_be_chosen_and_returns_to_normal_race_setup(self):
        self.app.go("race_select")
        self.click("race_observer")
        self.assertEqual(self.app.empire, "The Observer")
        self.assertGreaterEqual(self.app.rival_count, 2)
        self.click("setup_next")
        buttons = {b.key: b for b in self.app.buttons}
        self.assertFalse(buttons["rival_count_0"].enabled)
        self.assertFalse(buttons["rival_count_1"].enabled)
        self.click("launch")
        self.assertTrue(self.app.game.is_observer)
        self.assertEqual(self.app.screen, "galaxy")
        self.app.choose_race("terran")
        self.assertEqual(self.app.empire, "Terran Union")
        self.app.start_game()
        self.assertFalse(self.app.game.is_observer)
        self.assertTrue(self.app.game.colony_systems("player"))

    def test_all_dock_buttons_and_keyboard_shortcuts_open_read_only_reports(self):
        for tab, button, key in (("empires", "open_empire", pg.K_i), ("research", "open_research", pg.K_r),
                                 ("diplomacy", "open_diplomacy", pg.K_d), ("fleets", "open_fleets", pg.K_f),
                                 ("objectives", "open_objectives", pg.K_v)):
            self.app.go("galaxy")
            self.click(button)
            self.assertEqual((self.app.screen, self.app.observer_tab), ("observer", tab))
            self.assertIn("end_turn", [b.key for b in self.app.buttons])
            self.app.go("galaxy")
            self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=key, mod=0))
            self.app.render()
            self.assertEqual((self.app.screen, self.app.observer_tab), ("observer", tab))

    def test_end_turn_stays_in_view_and_menu_saves_observation(self):
        self.click("end_turn")
        self.assertEqual(self.app.screen, "galaxy")
        self.assertEqual(self.app.game.turn, 2)
        self.click("open_research")
        self.click("end_turn")
        self.assertEqual(self.app.screen, "observer")
        self.click("pause")
        self.click("save")
        paths = [p for p in self.app.storage.saves_dir.glob("save-*.json")]
        self.assertEqual(len(paths), 1)
        saved = self.app.game.to_dict()
        self.app.load_game(paths[0])
        self.assertTrue(self.app.game.is_observer)
        self.assertEqual(self.app.game.to_dict(), saved)
        self.assertEqual(self.app.screen, "galaxy")

    def test_planet_and_fleet_views_cannot_manage_or_attack(self):
        game = self.app.game
        game.selected_system, game.selected_planet = game.opponent.home_system, game.opponent.home_planet
        self.app.go("planet")
        self.app.render()
        controls = {b.key: b for b in self.app.buttons}
        self.assertFalse(any(b.enabled for key, b in controls.items() if key.startswith("worker_")))
        self.assertFalse({"colonize_planet", "invade_planet", "bombard_planet", "planet_buy"} & controls.keys())
        self.click("observer_planet_empire")
        self.assertEqual(self.app.screen, "rival")
        self.app.open_map_fleet(game.ships[0].id)
        self.app.render()
        self.assertFalse(self.app.fleet_selected_ids)
        self.assertNotIn("fleet_select_all", [b.key for b in self.app.buttons])

    def test_observer_result_never_says_defeat(self):
        game = self.app.game
        for system in game.systems:
            for planet in system.worlds:
                if planet.owner:
                    planet.owner = "rival"
        game.check_victory()
        self.app.go("result")
        with patch("orion.ui.text_image", wraps=text_image) as drawn:
            self.app.render()
        words = [call.args[0] for call in drawn.call_args_list]
        self.assertIn("Campaign complete", words)
        self.assertNotIn("Defeat", words)


if __name__ == "__main__":
    unittest.main()
