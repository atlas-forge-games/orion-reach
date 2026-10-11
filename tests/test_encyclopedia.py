"""Read-only reference navigation preserves campaign actions and view context."""

import os
from pathlib import Path
import tempfile
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame as pg

from orion.encyclopedia import category_articles
from orion.encyclopedia_view import article_body_rect, article_illustration, article_lines, illustration_rect, selected_article
from orion.model import GameState, Ship, new_game as make_game
from scenarios import fixed_start_game as new_game, place_near


class EncyclopediaTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.directory.name), capture=True)
        self.addCleanup(self.app.audio.close)
        self.app.game = new_game(seed=2408, with_guardians=False, with_tombs=False, fog_of_war=True)
        self.app.go("galaxy")
        self.app.present()

    def click(self, key):
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        self.assertTrue(button.enabled, key)
        x, y = button.rect.center
        view = self.app.viewport
        pos = (view.x+round(x*view.w/1440), view.y+round(y*view.h/900))
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, button=1, pos=pos))
            self.app.render()

    def key(self, key):
        self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=key, mod=0))
        self.app.render()

    def test_dock_preserves_pending_orders_selection_and_hidden_intelligence(self):
        game = self.app.game
        place_near(game, 1)
        game.send_ship(1, 1)
        self.click("map_fleet_1")
        before = game.to_dict()
        selection = (self.app.map_order_ids, self.app.fleet_selected_ids,
                     self.app.fleet_popup, self.app.route_ship_id, self.app.campaign_view)
        self.click("open_info")
        self.click("info_category_civilizations")
        self.click("info_next")
        for key in (pg.K_e, pg.K_r, pg.K_f, pg.K_n):
            self.key(key)
            self.assertEqual(self.app.screen, "info")
        self.key(pg.K_ESCAPE)
        self.assertEqual(self.app.screen, "galaxy")
        self.assertEqual((self.app.map_order_ids, self.app.fleet_selected_ids,
                          self.app.fleet_popup, self.app.route_ship_id, self.app.campaign_view), selection)
        self.assertEqual(game.to_dict(), before)

    def test_research_reference_does_not_select_a_project_and_returns_to_same_tier(self):
        app, game = self.app, self.app.game
        game.choose_research("ion_drives")
        self.click("open_research")
        app.select_research_branch("physics")
        app.select_research_tier(6)
        state = (app.research_branch, app.research_tier, app.research_overview)
        before = game.to_dict()
        self.key(pg.K_F1)
        self.click("info_category_research")
        # Browse the entire index through its actual controls, including the
        # final page. Every technology must be reachable without unlocking it.
        seen = set()
        while True:
            seen.update(b.key.removeprefix("info_article_") for b in app.buttons
                        if b.key.startswith("info_article_"))
            if not next(b for b in app.buttons if b.key == "info_next").enabled:
                break
            self.click("info_next")
        self.assertEqual(seen, {article.id for article in category_articles("research")})
        self.click("info_article_"+category_articles("research")[-1].id)
        self.key(pg.K_F1)
        self.assertEqual(app.screen, "research")
        self.assertEqual((app.research_branch, app.research_tier, app.research_overview), state)
        self.assertEqual(game.to_dict(), before)

    def test_long_article_scrolls_to_the_end_and_back_for_observers_too(self):
        app = self.app
        app.game = make_game(seed=2408, race_id="observer", rival_count=3,
                             with_guardians=False, with_tombs=False)
        app.go("galaxy")
        before = app.game.to_dict()
        self.click("open_info")
        self.click("info_article_controls")
        article = selected_article(app)
        area = article_body_rect(article)
        lines, height = article_lines(article, area.w)
        self.key(pg.K_PAGEDOWN)
        self.assertGreater(app.info_scroll, 0)
        while next(b for b in app.buttons if b.key == "info_scroll_down").enabled:
            self.click("info_scroll_down")
        self.assertEqual(app.info_scroll, height-area.h)
        self.assertLessEqual(lines[-1][1]+24-app.info_scroll, area.h)
        app.mouse = area.center
        app.handle_event(pg.event.Event(pg.MOUSEWHEEL, y=100, x=0))
        app.render()
        self.assertEqual(app.info_scroll, 0)
        self.assertFalse(next(b for b in app.buttons if b.key == "info_scroll_up").enabled)
        self.click("info_back")
        self.assertEqual(app.screen, "galaxy")
        self.assertEqual(app.game.to_dict(), before)

    def test_battle_is_paused_while_reading_and_modal_actions_are_not_bypassed(self):
        app, game = self.app, self.app.game
        game.ships = [Ship(1, "frigate", 0, owner="player"), Ship(2, "frigate", 0, owner="rival")]
        game.next_ship_id = 3
        game.start_combat(0)
        game.combat_end_turn()
        app.go("combat")
        self.assertEqual(game.combat.active_owner, "rival")
        before = game.to_dict()
        self.key(pg.K_F1)
        self.click("info_category_artifacts")
        self.click("info_article_artifact_heart_of_a_dead_sun")
        app.time += 20
        app.update_combat()
        self.key(pg.K_e)
        self.assertEqual(game.to_dict(), before)
        self.key(pg.K_F1)
        self.assertEqual(app.screen, "combat")
        app.update_combat()
        self.assertEqual(game.to_dict(), before)
        self.assertGreater(app.combat_ai_due, app.time)
        app.confirm("Leave battle?", "Keep this decision open.", "Continue", lambda: None)
        dialog = app.dialog
        self.key(pg.K_F1)
        self.assertEqual(app.screen, "combat")
        self.assertIs(app.dialog, dialog)

    def test_all_ten_artifacts_are_illustrated_previews_without_campaign_effects(self):
        app, game = self.app, self.app.game
        before = game.to_dict()
        control = GameState.from_dict(before)
        self.click("open_info")
        self.click("info_category_artifacts")
        entries = category_articles("artifacts")
        self.assertEqual(len(entries), 10)
        for entry in entries:
            with self.subTest(artifact=entry.id):
                if not any(b.key == "info_article_"+entry.id for b in app.buttons):
                    self.click("info_next")
                self.click("info_article_"+entry.id)
                self.assertTrue(selected_article(app).planned)
                rect = illustration_rect(entry)
                self.assertIsNotNone(article_illustration(entry.image, rect.size))
                image_before = pg.image.tobytes(app.canvas.subsurface(rect), "RGB")
                self.key(pg.K_PAGEDOWN)
                self.assertEqual(pg.image.tobytes(app.canvas.subsurface(rect), "RGB"), image_before)
                self.assertEqual(game.to_dict(), before)
        self.assertEqual(app.info_page, 1)
        self.key(pg.K_ESCAPE)
        self.assertEqual(app.screen, "galaxy")
        # Reading every proposed bonus must also leave future turn results
        # identical, including AI, economic and research outcomes.
        game.advance_turn()
        control.advance_turn()
        self.assertEqual(game.to_dict(), control.to_dict())


if __name__ == "__main__":
    unittest.main()
