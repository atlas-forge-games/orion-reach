"""Persistent autosave preferences and manual-only campaign workflows."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_motherships import campaign
from orion.model import SaveError
from orion.storage import Storage


class AutosavePreferenceTests(unittest.TestCase):
    def test_missing_legacy_and_invalid_settings_default_to_on_without_rewriting(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Storage(folder)
            self.assertIs(store.load_settings()['autosave'], True)
            path = Path(folder)/'settings.json'
            payloads = [{'sound': False}, *({'autosave': value} for value in ('false', 0, 1, None, [], {}))]
            for payload in payloads:
                with self.subTest(payload=payload):
                    before = json.dumps(payload)
                    path.write_text(before)
                    self.assertIs(store.load_settings()['autosave'], True)
                    self.assertEqual(path.read_text(), before)

    def test_off_and_on_are_remembered(self):
        with tempfile.TemporaryDirectory() as folder:
            for enabled in (False, True):
                store = Storage(folder)
                settings = store.load_settings()
                settings['autosave'] = enabled
                store.save_settings(settings)
                self.assertIs(Storage(folder).load_settings()['autosave'], enabled)


class OptionalAutosaveInterfaceTests(unittest.TestCase):
    def setUp(self):
        import pygame as pg
        from orion.app import App
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.addCleanup(pg.quit)
        self.app = App(Path(self.folder.name), capture=True)
        self.addCleanup(self.app.audio.close)
        self.app.game = campaign()
        for _, planet in self.app.game.settlements('player'):
            planet.trade_goods = True
        self.app.go('galaxy')
        self.app.present()

    def click(self, key):
        import pygame as pg
        self.app.render()
        button = next(b for b in self.app.buttons if b.key == key)
        self.assertTrue(button.enabled, key)
        x, y = button.rect.center
        viewport = self.app.viewport
        pos = (round(viewport.x+x*viewport.w/1440), round(viewport.y+y*viewport.h/900))
        for kind in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind, button=1, pos=pos))
            self.app.render()

    def test_settings_toggle_preserves_old_autosave_during_consecutive_turns_and_manual_save_works(self):
        app, game = self.app, self.app.game
        app.save_game(autosave=True)
        old = app.storage.saves_dir/'autosave.json'
        before = old.read_bytes()
        self.click('pause')
        self.click('settings')
        self.click('settings_category_gameplay')
        self.click('autosave')
        self.assertIs(app.storage.load_settings()['autosave'], False)
        self.click('settings_done')
        self.click('resume')
        with patch.object(app.storage, 'save', wraps=app.storage.save) as saving:
            for _ in range(3):
                app.advance_turn()
            self.assertEqual(game.turn, 4)
            saving.assert_not_called()
        self.assertEqual(old.read_bytes(), before)
        import pygame as pg
        app.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_F5, mod=0))
        manual = list(app.storage.saves_dir.glob('save-*.json'))
        self.assertEqual(len(manual), 1)
        restored, meta = app.storage.load(manual[0])
        self.assertEqual(restored, game)
        self.assertFalse(meta['autosave'])
        self.assertEqual(old.read_bytes(), before)

    def test_reenabling_updates_autosave_on_the_next_turn(self):
        app = self.app
        app.settings['autosave'] = False
        app.advance_turn()
        self.assertFalse((app.storage.saves_dir/'autosave.json').exists())
        app.toggle_setting('autosave')
        app.advance_turn()
        restored, meta = app.storage.load(app.storage.saves_dir/'autosave.json')
        self.assertEqual(restored.turn, app.game.turn)
        self.assertTrue(meta['autosave'])
        self.assertIs(app.storage.load_settings()['autosave'], True)

    def test_disabled_autosave_applies_to_project_actions_and_menu_exit(self):
        from orion.hyperlane_view import perform
        from orion.hyperlanes import start
        app = self.app
        app.settings['autosave'] = False
        with patch.object(app.storage, 'save', wraps=app.storage.save) as saving:
            perform(app, lambda: start(app.game, 0))
            self.assertEqual(len(app.game.hyperlane_projects), 1)
            app.to_menu()
            self.assertEqual(app.screen, 'menu')
            saving.assert_not_called()

    def test_new_campaign_respects_remembered_off_preference(self):
        from orion.app import App
        import pygame as pg
        self.app.toggle_setting('autosave')
        self.app.audio.close()
        pg.quit()
        app = self.app = App(Path(self.folder.name), capture=True)
        self.addCleanup(app.audio.close)
        self.assertIs(app.settings['autosave'], False)
        app.rival_count = 0
        with patch.object(app.storage, 'save', wraps=app.storage.save) as saving:
            app.start_game()
            self.assertIsNotNone(app.game)
            saving.assert_not_called()

    def test_quit_message_and_writes_follow_the_preference(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                app = self.app
                app.settings['autosave'] = enabled
                app.quit_request()
                expected = 'will be autosaved' if enabled else 'Autosave is off'
                self.assertIn(expected, app.dialog['body'])
                with patch.object(app.storage, 'save', wraps=app.storage.save) as saving, patch.object(app, 'quit_now') as quitting:
                    app.accept_dialog()
                    self.assertEqual(saving.call_count, int(enabled))
                    quitting.assert_called_once()

    def test_manual_save_failures_are_still_reported_with_autosave_off(self):
        self.app.settings['autosave'] = False
        with patch.object(self.app.storage, 'save', side_effect=SaveError('Disk unavailable')):
            self.assertFalse(self.app.save_game())
        self.assertTrue(self.app.notice_error)
        self.assertIn('Disk unavailable', self.app.notice)

    def test_all_settings_controls_fit_and_do_not_overlap_at_supported_sizes(self):
        import pygame as pg
        before = self.app.game.to_dict()
        for size in ((980, 900), (1280, 800), (1920, 1080)):
            self.app.window = pg.display.set_mode(size, pg.RESIZABLE)
            self.app.present()
            self.app.show_settings('galaxy')
            for category in (None, 'graphics', 'sound', 'gameplay', 'interface'):
                if category:
                    self.click('settings_category_'+category)
                self.app.render()
                for index, button in enumerate(self.app.buttons):
                    self.assertTrue(self.app.canvas.get_rect().contains(button.rect), button.key)
                    self.assertEqual(button.rect.collidelist([b.rect for b in self.app.buttons[index+1:]]), -1, button.key)
            self.click('settings_category_gameplay')
            self.click('autosave')
            self.click('back')
            self.assertIsNone(self.app.settings_section)
            self.click('settings_done')
            self.assertEqual(self.app.screen, 'galaxy')
        self.assertEqual(self.app.game.to_dict(), before)


if __name__ == '__main__':
    unittest.main()
