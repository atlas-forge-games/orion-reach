"""Historical economic graphs: contact filtering, correct totals and persistence."""

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

from orion import economy, first_contact, statistics
from orion.app import App
from orion.empire import summarize_empire
from orion.model import GameState, SaveError, new_game
from orion.statistics_view import PLOT, axis_ticks, compact_points
from orion.storage import Storage


def campaign(**kwargs):
    options = dict(seed=2408, with_guardians=False, with_tombs=False, random_starts=False, fog_of_war=True,
                   victory_conditions=())
    options.update(kwargs)
    return new_game(**options)


class StatisticsRulesTests(unittest.TestCase):
    def test_every_starting_empire_has_turn_one_but_only_contacts_are_visible(self):
        game = campaign()
        self.assertEqual(set(game.statistics), set(game.owners))
        self.assertEqual(set(statistics.visible_series(game, "population")), {"player"})
        with patch("orion.ai.run_ai", return_value=[]):
            for _ in range(4):
                game.advance_turn()
        self.assertEqual([row[0] for row in game.statistics["rival"]], [1, 2, 3, 4, 5])
        self.assertEqual(set(statistics.visible_series(game, "industry")), {"player"})
        first_contact.establish(game, "player", "rival")
        for metric in statistics.METRICS:
            self.assertEqual([t for t, _ in statistics.visible_series(game, metric)["rival"]], [1, 2, 3, 4, 5])
        self.assertIsNone(game.known_system(game.opponent.home_system))

    def test_live_totals_match_colony_rules_and_include_goods_and_treaties(self):
        game = campaign(fog_of_war=False)
        earth = game.planet_at(0, 2)
        earth.slaves = 3
        game.set_trade_goods(0, 2)
        game.diplomacy.trade_active = True
        summary = summarize_empire(game)
        row = statistics.sample(game, "player")
        self.assertEqual(row, [game.turn, summary.population, summary.industry, summary.food_produced,
                               summary.resources, summary.energy_generated, summary.income])
        self.assertEqual(row[1], earth.population+earth.slaves)
        self.assertEqual(row[6], game.planet_yields(earth)[1]+game.diplomatic_yields()[0]-game.fleet_maintenance())
        self.assertGreater(game.diplomatic_yields()[0], 0)
        # A fueled local grid consumes mining resources; statistics shows gross mining.
        from orion.buildings import BUILDINGS
        generator = next(key for key, b in BUILDINGS.items() if b.energy_per_resource)
        load = max(BUILDINGS, key=lambda key: BUILDINGS[key].energy_use)
        earth.buildings = [generator]+[load]*3
        power = game.planet_energy(earth)
        self.assertGreater(power.fuel_used, 0)
        row = statistics.sample(game, "player")
        self.assertEqual(row[4], game.resource_rate()+power.fuel_used)
        self.assertEqual(row[5], power.generated)
        earth.population, earth.slaves = 1, 0
        earth.farmers = earth.miners = earth.scientists = 0
        earth.trade_goods = game.diplomacy.trade_active = False
        self.assertLess(statistics.sample(game, "player")[6], 0)

    def test_live_current_point_does_not_mutate_history_and_is_frozen_when_turn_ends(self):
        game = campaign(with_ai=False)
        history = copy.deepcopy(game.statistics)
        game.set_workforce(0, 2, 1, 0, 3)
        live = statistics.sample(game, "player")
        for metric in statistics.METRICS:
            statistics.visible_series(game, metric)
        self.assertEqual(game.statistics, history)
        game.advance_turn()
        self.assertEqual(game.statistics["player"][0], live)
        self.assertEqual(len(game.statistics["player"]), 2)
        frozen = copy.deepcopy(game.statistics["player"][0])
        game.set_workforce(0, 2, 2, 0, 2)
        game.advance_turn()
        self.assertEqual(game.statistics["player"][0], frozen)

    def test_save_load_and_continuation_preserve_all_samples(self):
        game = campaign(fog_of_war=False)
        with patch("orion.ai.run_ai", return_value=[]):
            game.advance_turn()
            game.advance_turn()
            with tempfile.TemporaryDirectory() as folder:
                storage = Storage(folder)
                restored, meta = storage.load(storage.save(game))
                self.assertEqual(meta["version"], 50)
                self.assertEqual(restored, game)
                game.advance_turn()
                restored.advance_turn()
                self.assertEqual(restored, game)

    def test_old_saves_begin_at_load_turn_and_are_not_rewritten(self):
        game = campaign(with_ai=False)
        game.turn, game.year = 17, 2316
        with tempfile.TemporaryDirectory() as folder:
            storage = Storage(folder)
            path = storage.save(game)
            payload = json.loads(path.read_text())
            payload["version"] = 37
            payload["game"].pop("statistics")
            path.write_text(json.dumps(payload))
            before = path.read_bytes()
            restored, _ = storage.load(path)
            self.assertEqual([r[0] for r in restored.statistics["player"]], [17])
            self.assertEqual(statistics.visible_series(restored, "population")["player"], [(17, 8)])
            restored.advance_turn()
            self.assertEqual([r[0] for r in restored.statistics["player"]], [17, 18])
            self.assertEqual(path.read_bytes(), before)

    def test_new_empires_start_at_birth_and_defeated_empires_remain_in_graphs(self):
        game = campaign(with_ai=False, fog_of_war=False)
        game.advance_turn(); game.advance_turn()
        planet = game.add_opponent("remnant")
        self.assertEqual(statistics.visible_series(game, "population")["rival"], [(3, 8)])
        with patch("orion.ai.run_ai", return_value=[]):
            game.advance_turn()
        self.assertEqual([r[0] for r in game.statistics["rival"]], [3, 4])
        planet.owner = "player"
        self.assertEqual(statistics.visible_series(game, "population")["rival"], [(3, 8), (4, 0)])
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_observer_records_every_empire_without_a_player_series(self):
        game = campaign(race_id="observer", rival_count=3)
        self.assertEqual(set(statistics.visible_series(game, "population")), set(game.owners))
        self.assertNotIn("player", game.statistics)
        self.assertEqual(GameState.from_dict(game.to_dict()), game)

    def test_interrupted_turn_does_not_append_history(self):
        game = campaign()
        before = copy.deepcopy(game.statistics)
        with patch("orion.combat.intercept", return_value=True):
            game.advance_turn()
        self.assertEqual(game.turn, 1)
        self.assertEqual(game.statistics, before)

    def test_corrupt_history_rejected_and_loaded_history_does_not_alias_input(self):
        game = campaign(with_ai=False)
        game.advance_turn()
        data = game.to_dict()
        bad = [None, [], {"secret": [[1, 1, 1, 1, 1, 1, 1]]},
               {"player": [[3, 1, 1, 1, 1, 1, 1]]}, {"player": [[1, True, 1, 1, 1, 1, 1]]},
               {"player": [[1, -1, 1, 1, 1, 1, 1]]}, {"player": [[1, 1, 1, 1, 1, 1]]},
               {"player": [[1, 1, 1, 1, 1, 1, 1]]*2}, {"player": [[1, 1, 1, 1, 1, 1, float("nan")]]},
               {"player": [[2, 1, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 1, 1]]}]
        for history in bad:
            with self.subTest(history=history), self.assertRaises(SaveError):
                GameState.from_dict({**data, "statistics": history})
        without = dict(data); without.pop("statistics")
        with self.assertRaises(SaveError):
            GameState.from_dict(without)
        restored = GameState.from_dict(data)
        restored.statistics["player"][0][1] += 1
        self.assertNotEqual(restored.statistics, data["statistics"])


class StatisticsUITests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.app = App(Path(self.folder.name), capture=True)
        self.app.game = campaign()
        self.app.go("galaxy")
        self.app.present()

    def tearDown(self):
        self.app.audio.close()
        pg.quit()
        self.folder.cleanup()

    def click(self, key):
        app = self.app
        app.render()
        button = next(b for b in app.buttons if b.key == key)
        self.assertTrue(button.enabled, key)
        v = app.viewport
        pos = (round(v.x+button.rect.centerx*v.w/1440), round(v.y+button.rect.centery*v.h/900))
        for event in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            app.handle_event(pg.event.Event(event, button=1, pos=pos))
            app.render()

    def test_diplomacy_button_graph_controls_and_return_are_read_only(self):
        self.click("open_diplomacy")
        before = self.app.game.to_dict()
        self.click("diplomacy_statistics")
        self.assertEqual(self.app.screen, "statistics")
        self.assertNotIn("statistics_empire_rival", [b.key for b in self.app.buttons])
        for metric in statistics.METRICS:
            self.click("statistics_metric_"+metric)
            self.assertEqual(self.app.statistics_metric, metric)
        for span in (25, 100, 0):
            self.click("statistics_range_"+str(span))
            self.assertEqual(self.app.statistics_range, span)
        self.click("statistics_empire_player")
        self.assertEqual(self.app.statistics_hidden, {"player"})
        self.click("statistics_empire_player")
        self.click("open_diplomacy")
        self.assertEqual(self.app.screen, "diplomacy")
        self.click("diplomacy_statistics")
        self.app.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_ESCAPE, mod=0))
        self.assertEqual(self.app.screen, "diplomacy")
        self.click("diplomacy_back")
        self.assertEqual(self.app.screen, "galaxy")
        self.assertEqual(self.app.game.to_dict(), before)

    def test_contact_adds_full_series_and_letterboxed_hover_inspects_exact_turn(self):
        with patch("orion.ai.run_ai", return_value=[]):
            for _ in range(4):
                self.app.game.advance_turn()
        self.app.open_statistics(); self.app.render()
        self.assertNotIn("statistics_empire_rival", [b.key for b in self.app.buttons])
        first_contact.establish(self.app.game, "player", "rival")
        self.app.render()
        self.assertIn("statistics_empire_rival", [b.key for b in self.app.buttons])
        self.assertEqual(statistics.visible_series(self.app.game, "population")["rival"][0][0], 1)
        self.app.viewport = pg.Rect(90, 80, 960, 600)
        v = self.app.viewport
        pos = (round(v.x+PLOT.centerx*v.w/1440), round(v.y+PLOT.centery*v.h/900))
        self.app.handle_event(pg.event.Event(pg.MOUSEMOTION, pos=pos))
        self.app.render()
        self.assertEqual(self.app.statistics_cursor_turn, 3)
        self.app.handle_event(pg.event.Event(pg.MOUSEMOTION, pos=(0, 0)))
        self.app.render()
        self.assertEqual(self.app.statistics_cursor_turn, 5)

    def test_every_metric_seven_lines_deficits_empty_and_observer_render(self):
        game = campaign(rival_count=5, fog_of_war=False)
        # Six starting empires plus a possible Remnant enclave.
        candidate = next((s, p) for s in game.systems for p in s.worlds if not p.colonized)
        game._place_opponent("rival_6", "remnant", *candidate, "The Awakened Remnant")
        first_contact.establish(game, "player", "rival_6")
        self.app.game = game
        self.app.open_statistics()
        for metric in statistics.METRICS:
            self.app.set_statistics_metric(metric); self.app.render()
            self.assertEqual(len([b for b in self.app.buttons if b.key.startswith("statistics_empire_")]), 7)
            self.assertTrue(all(self.app.canvas.get_rect().contains(b.rect) for b in self.app.buttons))
        self.app.statistics_hidden = set(game.owners)
        self.app.render()
        self.app.game = campaign(race_id="observer", rival_count=3)
        self.app.reset_empire_view()
        self.app.go("observer")
        self.app.observer_tab = "empires"
        self.click("observer_statistics")
        self.assertEqual(self.app.screen, "statistics")
        self.assertNotIn("statistics_empire_player", [b.key for b in self.app.buttons])
        self.click("statistics_back")
        self.assertEqual((self.app.screen, self.app.observer_tab), ("observer", "empires"))

    def test_chart_scale_and_pixel_reduction_keep_zero_deficits_and_spikes(self):
        self.assertEqual(axis_ticks([0, 0]), (0, 1))
        ticks = axis_ticks([-9, 21])
        self.assertLessEqual(ticks[0], -9)
        self.assertGreaterEqual(ticks[-1], 21)
        self.assertIn(0, ticks)
        points = [(1+i/100, 80 if i == 11 else -50 if i == 20 else i) for i in range(30)]
        compact = compact_points(points)
        self.assertEqual((compact[0], compact[-1]), (points[0], points[-1]))
        self.assertEqual((min(p[1] for p in compact), max(p[1] for p in compact)), (-50, 80))
        self.assertLess(len(compact), len(points))

    def test_advance_pause_and_save_from_statistics_keep_the_history(self):
        self.app.game = campaign(with_ai=False)
        self.app.game.set_trade_goods(0, 2)
        self.app.game.choose_research("civil_engineering")
        self.app.open_statistics()
        self.click("statistics_end_turn")
        self.assertEqual((self.app.screen, self.app.game.turn), ("statistics", 2))
        self.assertEqual([r[0] for r in self.app.game.statistics["player"]], [1, 2])
        self.click("statistics_pause")
        self.click("resume")
        self.assertEqual(self.app.screen, "statistics")
        self.click("statistics_save")
        saved = next(p for p in self.app.storage.saves_dir.glob("*.json") if p.name != "autosave.json")
        restored, _ = self.app.storage.load(saved)
        self.assertEqual(restored, self.app.game)


if __name__ == "__main__":
    unittest.main()
