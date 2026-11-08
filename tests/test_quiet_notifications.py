"""Quiet successful orders, visible failures, and durable strategic reports."""

from copy import deepcopy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame as pg

from orion import coalitions, exploration, news
from orion.model import GameState, SaveError, Ship
from orion.storage import Storage
from test_galaxy_fleets import fixture
from test_motherships import campaign


def discover(game, owner="player"):
    """Recover a real discovery with a scout, without advancing the turn."""
    claimed = {d.system_id for d in game.exploration.discoveries}
    homes = {0, *(r.home_system for r in game.opponents.values())}
    system = next(s for s in game.systems if s.id not in claimed | homes
                  and exploration.discovery_at(game, s.id))
    scout = Ship(game.next_ship_id, "scout", system.id, owner=owner)
    game.next_ship_id += 1
    game.ships.append(scout)
    exploration.refresh(game, recover=True)
    return next(d for d in game.exploration.discoveries if d.system_id == system.id)


class QuietNotificationTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.folder.name), capture=True)
        self.addCleanup(self.app.audio.close)
        self.app.game = campaign(race_id="terran", with_encounters=False)
        self.app.settings["autosave"] = False
        self.app.go("galaxy")

    def test_course_and_queue_changes_are_silent_and_still_take_effect(self):
        app = self.app
        app.game = fixture()
        app.map_order_ids = (1, 2)
        app.send_map_fleet(1)
        self.assertTrue(app.game.ship_at(1).departure_pending)
        self.assertEqual(app.game.ship_at(2).destination, 1)
        self.assertEqual(app.notice, "")
        app.send_map_fleet(1)  # Re-select the already queued route.
        self.assertEqual(app.notice, "")
        app.send_map_fleet(0)  # Cancel the pending departure.
        self.assertFalse(app.game.ship_at(1).has_course)
        self.assertEqual(app.notice, "")
        app.game.selected_system, app.game.selected_planet = 0, 2
        app.queue_building("factory")
        self.assertEqual(len(app.game.planet_at(0, 2).construction_queue), 1)
        app.cancel_construction(0)
        self.assertFalse(app.game.planet_at(0, 2).construction_queue)
        self.assertEqual(app.notice, "")

    def test_invalid_orders_and_save_failures_remain_visible(self):
        app = self.app
        app.game = fixture()
        app.map_order_ids = (1,)
        far = next(s.id for s in app.game.systems if not app.game.can_reach(s.id))
        before = app.game.to_dict()
        app.send_map_fleet(far)
        self.assertTrue(app.notice_error)
        self.assertTrue(app.notice)
        self.assertEqual(app.game.to_dict(), before)
        deadline = app.notice_until
        app.toast("Course set")
        self.assertEqual(app.notice_until, deadline)
        self.assertNotEqual(app.notice, "Course set")
        app.settings["autosave"] = True
        with patch.object(app.storage, "save", side_effect=SaveError("Disk full")):
            app.send_map_fleet(1)
        self.assertTrue(app.game.ship_at(1).departure_pending)
        self.assertEqual(app.notice, "Disk full")
        self.assertTrue(app.notice_error)
        self.assertEqual(app.saved_until, 0)

    def test_manual_save_indicator_expires_autosaves_and_loads_are_silent(self):
        app = self.app
        app.time = 10
        self.assertTrue(app.save_game())
        path = next(app.storage.saves_dir.glob("save-*.json"))
        restored, _ = app.storage.load(path)
        self.assertEqual(restored, app.game)
        self.assertEqual(app.notice, "")
        with patch("orion.notifications.text") as drawn:
            app.render()
            self.assertTrue(any(c.args[1] == "Saved ✓" for c in drawn.call_args_list))
        app.time = app.saved_until+1
        app.settings["autosave"] = True
        self.assertTrue(app.save_game(autosave=True))
        with patch("orion.notifications.draw_saved") as indicator:
            app.render()
            indicator.assert_not_called()
        app.save_game()
        app.load_game(path)
        self.assertEqual(app.notice, "")
        self.assertEqual(app.saved_until, 0)

    def test_failed_manual_save_never_shows_saved_and_retry_recovers(self):
        app = self.app
        app.save_game()
        with patch.object(app.storage, "save", side_effect=SaveError("Disk full")):
            self.assertFalse(app.save_game())
        self.assertEqual(app.notice, "Disk full")
        self.assertEqual(app.saved_until, 0)
        self.assertTrue(app.save_game())
        self.assertFalse(app.notice_error)
        self.assertGreater(app.saved_until, app.time)

    def test_information_and_demolition_confirmation_still_work(self):
        app = self.app
        planet = app.game.planet_at(0, 2)
        planet.buildings.append("factory")
        exploration.refresh(app.game)
        app.game.selected_system, app.game.selected_planet = 0, 2
        app.go("planet")
        app.show_building_info("surface_factory")
        self.assertIn("building_info", app.dialog)
        app.cancel_dialog()
        app.demolish_request(0)
        self.assertIn("factory", planet.buildings)
        self.assertIn("action", app.dialog)
        app.cancel_dialog()
        self.assertIn("factory", planet.buildings)
        app.demolish_request(0)
        app.accept_dialog()
        self.assertNotIn("factory", planet.buildings)
        self.assertEqual(app.notice, "")

    def test_discovery_badge_waits_for_news_and_report_opens_its_system(self):
        from orion.research import TECHNOLOGIES
        app = self.app
        discovery = discover(app.game)
        for _, planet in app.game.settlements("player"):
            planet.trade_goods = True
        app.game.choose_research(next(t for t in TECHNOLOGIES if app.game.research_error(t) is None))
        app.finish_turn()
        self.assertNotEqual(app.screen, "news")
        self.assertGreater(news.unread_count(app.game), 0)
        app.go("news")
        app.render()
        self.assertEqual(news.unread_count(app.game), 0)
        button = next(b for b in app.buttons if b.key.endswith("_discovery"))
        app.activate(button)
        self.assertEqual(app.screen, "system")
        self.assertEqual(app.game.selected_system, discovery.system_id)


class StrategicNewsTests(unittest.TestCase):
    def test_discoveries_survive_reload_and_same_turn_read_tracking(self):
        game = campaign(race_id="terran", with_encounters=False)
        news.mark_read(game)
        discovery = discover(game)
        spec = exploration.DISCOVERIES[discovery.kind]
        reports = [r for r in news.entries(game) if r.category == "DISCOVERY"]
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].headline, spec.name)
        self.assertIn(spec.reward, reports[0].detail)
        self.assertEqual(news.unread_count(game), 1)
        self.assertEqual(news.unread_count(game, interrupting_only=True), 0)
        with tempfile.TemporaryDirectory() as folder:
            store = Storage(folder)
            restored, _ = store.load(store.save(game))
            self.assertEqual(news.entries(restored), news.entries(game))
            self.assertEqual(news.unread_count(restored), 1)
            news.mark_read(restored)
            restored, _ = store.load(store.save(restored))
            self.assertEqual(news.unread_count(restored), 0)
            discover(restored)
            self.assertEqual(restored.turn, game.turn)
            self.assertEqual(news.unread_count(restored), 1)
            self.assertEqual(sum(r.category == "DISCOVERY" for r in news.entries(restored)), 2)

    def test_foreign_discoveries_stay_private(self):
        game = campaign(race_id="terran", with_ai=True, with_encounters=False)
        news.mark_read(game)
        discover(game, "rival")
        self.assertFalse(any(r.category == "DISCOVERY" for r in news.entries(game)))
        self.assertEqual(news.unread_count(game), 0)
        discover(game)
        self.assertEqual(sum(r.category == "DISCOVERY" for r in news.entries(game)), 1)
        self.assertEqual(news.unread_count(game), 1)

    def test_observer_keeps_one_existing_dispatch_per_discovery(self):
        game = campaign(race_id="observer", rival_count=3, with_encounters=False)
        news.mark_read(game)
        discovery = discover(game, "rival")
        spec = exploration.DISCOVERIES[discovery.kind]
        reports = [r for r in news.entries(game) if spec.name in r.detail or spec.name in r.headline]
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].category, "EMPIRE ACTIVITY")

    def test_previous_saves_load_and_invalid_cursors_are_rejected(self):
        game = campaign(race_id="terran", with_encounters=False)
        discover(game)
        legacy = game.to_dict()
        legacy["exploration"].pop("news_read")
        restored = GameState.from_dict(legacy, version=63)
        self.assertEqual(news.unread_count(restored), 1)
        self.assertEqual(restored.exploration.news_read, 0)
        for invalid in (-1, True, 2, "0"):
            data = deepcopy(game.to_dict())
            data["exploration"]["news_read"] = invalid
            with self.subTest(cursor=invalid), self.assertRaises(SaveError):
                GameState.from_dict(data)

    def test_diplomatic_acceptance_refusal_and_war_are_saved_once(self):
        for action, relations, expected in (("trade", 20, "accepted"),
                                            ("trade", 0, "declined"),
                                            ("declare_war", 20, "War declared")):
            with self.subTest(action=action, relations=relations):
                game = campaign(race_id="terran", with_ai=True, rival_race_id="kharuun",
                                fog_of_war=False, with_encounters=False)
                game.diplomacy.relations = relations
                news.mark_read(game)
                response = game.diplomacy_action(action)
                self.assertIn(expected, response)
                reports = [r for r in news.entries(game) if response in r.detail]
                self.assertEqual(len(reports), 1)
                self.assertIn(game.opponent.name, reports[0].detail)
                self.assertGreater(news.unread_count(game), 0)
                self.assertEqual(news.unread_count(game, interrupting_only=True), 0)
                restored = GameState.from_dict(game.to_dict())
                self.assertEqual(news.entries(restored), news.entries(game))
                news.mark_read(restored)
                self.assertEqual(news.unread_count(restored), 0)

    def test_quiet_news_does_not_hide_urgent_dispatches_or_weaken_validation(self):
        game = campaign(race_id="terran", with_ai=True, fog_of_war=False, with_encounters=False)
        news.mark_read(game)
        discover(game)
        coalitions.notify(game, ("player", "rival"), "A hostile coalition has declared war.")
        self.assertEqual(news.unread_count(game), 2)
        self.assertEqual(news.unread_count(game, interrupting_only=True), 1)
        restored = GameState.from_dict(game.to_dict())
        self.assertEqual(news.unread_count(restored, interrupting_only=True), 1)
        legacy = game.to_dict()
        legacy["exploration"].pop("news_read")
        legacy["diplomatic_news"][0].pop("quiet")
        self.assertFalse(GameState.from_dict(legacy, version=63).diplomatic_news[0].quiet)
        data = game.to_dict()
        data["diplomatic_news"][0]["quiet"] = "true"
        with self.assertRaises(SaveError):
            GameState.from_dict(data)


if __name__ == "__main__":
    unittest.main()
