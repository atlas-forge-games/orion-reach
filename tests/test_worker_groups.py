"""Real pointer and keyboard group transfers, including large captive workforces."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame as pg

from orion.model import GameState, RuleError, new_game
from orion.population import WORKER_ROLES


def campaign(**kwargs):
    return new_game(seed=804, with_ai=False, with_guardians=False, with_tombs=False,
                    fog_of_war=False, random_starts=False, **kwargs)


class GroupTransferRulesTests(unittest.TestCase):
    def test_batch_validates_before_changing_any_job_and_preserves_total_population(self):
        game = campaign()
        planet = game.planet_at(0, 2)
        planet.population = 12
        game.set_workforce(0, 2, 2, 7, 1)
        before = game.to_dict()
        for count in (0, -1, True, 1.2, 8, "5", None):
            with self.subTest(count=count):
                with self.assertRaises(RuleError):
                    game.move_worker(0, 2, "scientists", "farmers", count=count)
                self.assertEqual(game.to_dict(), before)
        game.move_worker(0, 2, "scientists", "farmers", count=5)
        self.assertEqual((planet.farmers, planet.scientists, planet.miners, planet.workers), (7, 2, 1, 2))
        self.assertEqual(sum(getattr(planet, r) for r in WORKER_ROLES), 12)
        self.assertEqual((game.credits, game.resources, game.turn), (120, 120, 1))
        self.assertEqual(GameState.from_dict(game.to_dict()), game)


class GroupTransferInterfaceTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(folder.name), capture=True)
        # Letterboxing and scaling must preserve the boundary before a worker.
        self.app.window = pg.display.set_mode((980, 900), pg.RESIZABLE)
        self.app.game = campaign()
        self.planet = self.app.game.planet_at(0, 2)
        self.planet.population = 12
        self.app.game.set_workforce(0, 2, 2, 7, 1)
        self.app.open_planet(2)

    def click_at(self, x, y):
        self.app.render()
        self.app.present()
        v = self.app.viewport
        pos = (v.x+round(x*v.w/1440), v.y+round(y*v.h/900))
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, button=1, pos=pos))
            self.app.render()

    def key(self, key):
        self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=key, mod=0))
        self.app.render()

    def test_gap_before_third_scientist_selects_five_then_moves_and_autosaves_once(self):
        before = self.app.game.to_dict()
        with patch.object(self.app, "save_game", wraps=self.app.save_game) as save:
            self.click_at(491, 224)  # Seven scientists; gap before the third.
            self.assertEqual((self.app.worker_source, self.app.worker_count), ("scientists", 5))
            self.assertEqual(self.app.game.to_dict(), before)
            save.assert_not_called()
            self.click_at(320, 162)  # Destination can be anywhere in Farming.
            save.assert_called_once_with(autosave=True)
        self.assertEqual((self.planet.scientists, self.planet.farmers), (2, 7))
        self.assertEqual(self.app.game.planet_yields(self.planet), (2, 12, 4))
        self.assertEqual(self.app.game.population_report(self.planet).produced, 20)
        self.assertEqual((self.app.worker_source, self.app.worker_count), (None, 0))
        loaded, _ = self.app.storage.load(self.app.storage.saves_dir/"autosave.json")
        self.assertEqual(loaded, self.app.game)

    def test_last_icon_selects_one_and_left_of_first_selects_the_whole_role(self):
        self.click_at(567, 224)  # Last of seven.
        self.assertEqual(self.app.worker_count, 1)
        self.click_at(960, 255)  # Mining receives the selected amount.
        self.assertEqual((self.planet.scientists, self.planet.miners), (6, 2))
        self.click_at(452, 224)  # Left of the first remaining scientist.
        self.assertEqual(self.app.worker_count, 6)
        self.click_at(960, 193)
        self.assertEqual((self.planet.scientists, self.planet.workers), (0, 8))
        self.assertEqual(sum(getattr(self.planet, r) for r in WORKER_ROLES), 12)

    def test_same_row_escape_and_planet_switch_cancel_without_moving_or_saving(self):
        before = self.app.game.to_dict()
        with patch.object(self.app, "save_game", wraps=self.app.save_game) as save:
            self.click_at(491, 224)
            self.click_at(550, 224)
            self.assertEqual((self.app.worker_source, self.app.worker_count), (None, 0))
            self.click_at(491, 224)
            self.key(pg.K_ESCAPE)
            self.assertEqual(self.app.screen, "planet")
            self.assertEqual((self.app.worker_source, self.app.worker_count), (None, 0))
            self.assertEqual(self.app.game.to_dict(), before)
            self.click_at(491, 224)
            self.app.open_planet(3)
            self.assertEqual((self.app.worker_source, self.app.worker_count), (None, 0))
            save.assert_not_called()
        self.assertEqual((self.planet.farmers, self.planet.scientists), (2, 7))

    def test_keyboard_selects_and_adjusts_group_without_switching_planets(self):
        self.app.render()
        self.app.focus, self.app.keyboard_mode = "worker_scientists", True
        self.key(pg.K_RETURN)
        self.assertEqual(self.app.worker_count, 1)
        self.key(pg.K_LEFT)
        self.assertEqual(self.app.worker_count, 1)
        for _ in range(8):
            self.key(pg.K_RIGHT)
        self.assertEqual(self.app.worker_count, 7)
        self.key(pg.K_LEFT)
        self.key(pg.K_LEFT)
        self.assertEqual(self.app.worker_count, 5)
        self.assertEqual(self.app.game.selected_planet, 2)
        self.app.focus = "worker_farmers"
        self.key(pg.K_RETURN)
        self.assertEqual((self.planet.scientists, self.planet.farmers), (2, 7))

    def test_large_captive_workforce_keeps_last_five_and_whole_group_selectable(self):
        self.app.game = campaign(race_id="varkesh")
        p = self.app.game.planet_at(0, 2)
        p.slaves = 100
        self.app.game.set_workforce(0, 2, 2, 100, 0)
        self.app.open_planet(2)
        self.click_at(784, 224)  # Gap before the last five of the 24 visible icons.
        self.assertEqual(self.app.worker_count, 5)
        self.click_at(320, 162)
        self.assertEqual((p.farmers, p.scientists, p.slaves), (7, 95, 100))
        self.click_at(468, 224)  # +N prefix includes the hidden workers and visible tail.
        self.assertEqual(self.app.worker_count, 95)
        self.click_at(960, 193)
        self.assertEqual((p.workers, p.scientists, p.workforce), (101, 0, 108))
        loaded, _ = self.app.storage.load(self.app.storage.saves_dir/"autosave.json")
        self.assertEqual(loaded, self.app.game)

    def test_end_turn_clears_pending_group_before_population_can_change(self):
        self.click_at(491, 224)
        self.key(pg.K_e)
        self.assertEqual((self.app.worker_source, self.app.worker_count), (None, 0))
        self.assertEqual((self.planet.farmers, self.planet.scientists), (2, 7))
        self.assertEqual(self.app.game.turn, 2)


if __name__ == "__main__":
    unittest.main()
