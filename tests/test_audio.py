"""Real MP3 playback, independent controls and preference migration."""

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

from orion.audio import Audio, MUSIC_PATH
from scenarios import fixed_start_game as new_game
from orion.storage import Storage


class AudioTests(unittest.TestCase):
    def setUp(self):
        pg.quit()
        self.addCleanup(pg.quit)

    def test_bundled_mp3_streams_and_muting_resumes_without_reloading(self):
        audio = Audio()
        self.addCleanup(audio.close)
        self.assertTrue(audio.ready)
        self.assertEqual(pg.mixer.get_init(), (48000, -16, 2))
        self.assertGreater(MUSIC_PATH.stat().st_size, 0)
        with patch.object(pg.mixer.music, "load", wraps=pg.mixer.music.load) as load, \
             patch.object(pg.mixer.music, "play", wraps=pg.mixer.music.play) as play:
            audio.apply_music(True, 30)
            self.assertTrue(pg.mixer.music.get_busy())
            self.assertAlmostEqual(pg.mixer.music.get_volume(), .30, delta=.01)
            pg.time.wait(120)
            before = pg.mixer.music.get_pos()
            self.assertGreater(before, 0)
            audio.apply_music(False, 30)
            self.assertFalse(pg.mixer.music.get_busy())
            audio.play_click(True)
            self.assertGreater(audio.click.get_num_channels(), 0)
            audio.apply_music(True, 60)
            self.assertTrue(pg.mixer.music.get_busy())
            # SDL's position estimate can shift by an audio buffer when paused.
            self.assertAlmostEqual(pg.mixer.music.get_pos(), before, delta=50)
            self.assertAlmostEqual(pg.mixer.music.get_volume(), .60, delta=.01)
            audio.apply_music(True, 0)
            self.assertFalse(pg.mixer.music.get_busy())
            audio.apply_music(True, 10)
            self.assertTrue(pg.mixer.music.get_busy())
            load.assert_called_once()
            play.assert_called_once_with(loops=-1, fade_ms=1200)
        audio.close()
        self.assertFalse(pg.mixer.music.get_busy())
        audio.close()

    def test_muted_start_and_capture_do_not_load_or_play_music(self):
        with patch.object(pg.mixer, "init") as init, patch.object(pg.mixer.music, "load") as load:
            audio = Audio(enabled=False)
            audio.apply_music(True, 100)
            audio.play_click(True)
            audio.close()
            init.assert_not_called()
            load.assert_not_called()
        audio = Audio()
        self.addCleanup(audio.close)
        with patch.object(pg.mixer.music, "load") as load:
            audio.apply_music(False, 30)
            audio.apply_music(True, 0)
            load.assert_not_called()
        self.assertFalse(pg.mixer.music.get_busy())

    def test_missing_or_corrupt_track_keeps_interface_sounds_working(self):
        with tempfile.TemporaryDirectory() as folder:
            bad = Path(folder) / "bad.mp3"
            bad.write_bytes(b"not an audio file")
            for path in (Path(folder) / "missing.mp3", bad):
                with self.subTest(path=path.name):
                    audio = Audio(music_path=path)
                    audio.apply_music(True, 30)
                    self.assertTrue(audio.ready)
                    self.assertTrue(audio.music_error)
                    self.assertFalse(pg.mixer.music.get_busy())
                    audio.play_click(True)
                    self.assertGreater(audio.click.get_num_channels(), 0)
                    audio.close()

    def test_no_audio_device_still_allows_new_game_and_settings(self):
        from orion.app import App
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(pg.mixer, "init", side_effect=pg.error("No device")):
            app = App(Path(folder), skip_intro=True)
            self.assertFalse(app.audio.ready)
            app.start_game()
            self.assertEqual(app.screen, "galaxy")
            app.show_settings("galaxy")
            app.toggle_setting("music")
            app.change_music_volume(10)
            app.render()
            self.assertIn("unavailable", app.audio.music_description)
            app.quit_now()


class MusicSettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Storage(self.tmp.name)

    def test_legacy_preferences_preserve_mute_and_are_not_rewritten_on_read(self):
        path = self.store.root / "settings.json"
        for sound in (False, True):
            path.write_text(json.dumps({"sound": sound, "animated_background": False}))
            before = path.read_bytes()
            settings = self.store.load_settings()
            self.assertEqual(settings["music"], sound)
            self.assertEqual(settings["sound"], sound)
            self.assertFalse(settings["animated_background"])
            self.assertEqual(settings["music_volume"], 30)
            self.assertEqual(path.read_bytes(), before)
        settings.update(music=True, sound=False, music_volume=80)
        self.store.save_settings(settings)
        self.assertEqual(self.store.load_settings(), settings)

    def test_music_settings_reject_invalid_types_and_out_of_range_values(self):
        path = self.store.root / "settings.json"
        for value in (True, False, -1, 101, 3.5, "50", None, [], {}):
            path.write_text(json.dumps({"music_volume": value, "music": "false"}))
            settings = self.store.load_settings()
            self.assertEqual(settings["music_volume"], 30)
            self.assertIs(settings["music"], True)
        for value in (0, 10, 100):
            self.store.save_settings({"music_volume": value, "music": False, "sound": True})
            self.assertEqual(self.store.load_settings()["music_volume"], value)
            self.assertIs(self.store.load_settings()["music"], False)


class MusicInterfaceTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        pg.quit()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.tmp.name), skip_intro=True)
        self.addCleanup(self.app.audio.close)
        self.app.window = pg.display.set_mode((980, 900), pg.RESIZABLE)
        self.app.present()

    def click(self, key):
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        self.assertTrue(button.enabled)
        x, y = button.rect.center
        view = self.app.viewport
        pos = (view.x+round(x*view.w/1440), view.y+round(y*view.h/900))
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, button=1, pos=pos))
            self.app.render()

    def test_settings_controls_survive_restart_and_music_is_independent_of_clicks(self):
        self.click("settings")
        self.click("music_louder")
        self.assertEqual(self.app.settings["music_volume"], 40)
        self.click("sound")
        self.assertFalse(self.app.settings["sound"])
        self.assertTrue(pg.mixer.music.get_busy())
        self.click("music")
        self.assertFalse(pg.mixer.music.get_busy())
        self.click("music_quieter")
        self.assertFalse(pg.mixer.music.get_busy())
        self.assertEqual(self.app.storage.load_settings()["music_volume"], 30)
        self.click("settings_done")
        self.app.quit_now()
        pg.quit()
        from orion.app import App
        self.app = App(Path(self.tmp.name), skip_intro=True)
        self.addCleanup(self.app.audio.close)
        self.assertFalse(pg.mixer.music.get_busy())
        self.assertFalse(self.app.settings["sound"])
        self.assertEqual(self.app.settings["music_volume"], 30)
        self.app.present()
        self.click("settings")
        self.click("music")
        self.assertTrue(pg.mixer.music.get_busy())
        for _ in range(3):
            self.click("music_quieter")
        self.assertFalse(pg.mixer.music.get_busy())
        self.assertFalse(next(b for b in self.app.buttons if b.key == "music_quieter").enabled)
        for _ in range(10):
            self.click("music_louder")
        self.assertEqual(self.app.settings["music_volume"], 100)
        self.assertFalse(next(b for b in self.app.buttons if b.key == "music_louder").enabled)

    def test_screen_changes_keep_playing_and_do_not_change_campaign_state(self):
        game = new_game(seed=2408)
        self.app.game = game
        before = game.to_dict()
        with patch.object(pg.mixer.music, "load", wraps=pg.mixer.music.load) as load, \
             patch.object(pg.mixer.music, "play", wraps=pg.mixer.music.play) as play:
            for screen in ("galaxy", "system", "exploration", "pause", "settings", "menu"):
                self.app.go(screen)
                self.app.render()
                self.assertTrue(pg.mixer.music.get_busy())
            self.app.toggle_setting("music")
            self.app.change_music_volume(10)
            self.app.toggle_setting("music")
            self.assertEqual(game.to_dict(), before)
            load.assert_not_called()
            play.assert_not_called()


if __name__ == "__main__":
    unittest.main()
