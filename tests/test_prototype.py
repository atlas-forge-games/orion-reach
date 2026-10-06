"""Headless checks for persistence and actual UI event flows (standard unittest)."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"]="dummy"
os.environ["SDL_AUDIODRIVER"]="dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"]="1"

import pygame as pg
from orion.model import GALAXY_SIZES, GameState, SaveError, new_game
from orion.storage import Storage


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store=Storage(self.tmp.name)

    def test_generation_is_reproducible_and_correct_size(self):
        for size,count in GALAXY_SIZES.items():
            a=new_game("My Empire",size,274)
            b=new_game("My Empire",size,274)
            self.assertEqual(a.systems,b.systems)
            self.assertEqual(len(a.systems),count)
            self.assertEqual(a.systems[0].name,"Sol")
            self.assertEqual(a,GameState.from_dict(a.to_dict()))

    def test_save_round_trip_and_snapshots(self):
        game=new_game("Kies Federation",seed=2026)
        game.selected_system=7
        first=self.store.save(game)
        game.advance_turn()
        second=self.store.save(game)
        self.store.save(game,autosave=True)
        game.advance_turn()
        self.store.save(game,autosave=True)
        self.assertEqual(len(self.store.list_saves()),3)
        self.assertEqual(self.store.load(first)[0].turn,1)
        self.assertEqual(self.store.load(second)[0].credits,128)
        self.assertEqual(self.store.load(self.store.saves_dir/"autosave.json")[0],game)

    def test_bad_saves_do_not_hide_good_saves(self):
        self.store.save(new_game(seed=0))
        (self.store.saves_dir/"broken.json").write_text("{not json",encoding="utf-8")
        rows=self.store.list_saves()
        self.assertEqual(len(rows),2)
        self.assertEqual(sum("error" in row for row in rows),1)

    def test_unsupported_version_and_invalid_coordinates_are_rejected(self):
        path=self.store.save(new_game(seed=0))
        payload=json.loads(path.read_text())
        payload["version"]=999
        path.write_text(json.dumps(payload))
        with self.assertRaisesRegex(SaveError,"version"):
            self.store.load(path)
        payload["version"]=1
        payload["game"]["systems"][0]["x"]=float("nan")
        path.write_text(json.dumps(payload))
        with self.assertRaisesRegex(SaveError,"invalid"):
            self.store.load(path)

    def test_interrupted_save_preserves_previous_autosave(self):
        state=new_game(seed=10)
        path=self.store.save(state,autosave=True)
        original=path.read_bytes()
        state.advance_turn()
        with patch("orion.storage.os.replace",side_effect=OSError("disk full")):
            with self.assertRaises(SaveError):
                self.store.save(state,autosave=True)
        self.assertEqual(path.read_bytes(),original)
        self.assertEqual(list(self.store.saves_dir.glob(".writing-*")),[])

    def test_settings_validate_types_and_recover_from_damage(self):
        settings={"fullscreen":False,"animated_background":False,"sound":False}
        self.store.save_settings(settings)
        self.assertEqual(self.store.load_settings(),settings)
        (self.store.root/"settings.json").write_text('{"sound":"false","fullscreen":true}')
        self.assertIs(self.store.load_settings()["sound"],True)
        (self.store.root/"settings.json").write_text("[]")
        self.assertEqual(self.store.load_settings()["fullscreen"],False)


class InterfaceTests(unittest.TestCase):
    def setUp(self):
        from orion.app import App
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(pg.quit)
        self.app=App(Path(self.tmp.name),capture=True)
        self.app.present()

    def click(self,key):
        self.app.render()
        button=next(b for b in self.app.buttons if b.key==key)
        x,y=button.rect.center
        v=self.app.viewport
        pos=(v.x+round(x*v.w/1440),v.y+round(y*v.h/900))
        for kind in (pg.MOUSEBUTTONDOWN,pg.MOUSEBUTTONUP):
            self.app.handle_event(pg.event.Event(kind,button=1,pos=pos))
            self.app.render()

    def key(self,key,mod=0):
        self.app.handle_event(pg.event.Event(pg.KEYDOWN,key=key,mod=mod))
        self.app.render()

    def test_new_save_load_through_actual_events(self):
        self.click("new")
        self.assertEqual(self.app.screen,"setup")
        self.click("empire")
        self.app.handle_event(pg.event.Event(pg.TEXTINPUT,text="Kies Federation"))
        self.key(pg.K_RETURN)
        self.assertEqual(self.app.screen,"setup")
        self.assertIsNone(self.app.field)
        self.click("seed")
        self.app.handle_event(pg.event.Event(pg.TEXTINPUT,text="2026"))
        self.click("size_Compact")
        self.click("launch")
        self.assertEqual(self.app.screen,"galaxy")
        self.assertEqual(len(self.app.game.systems),24)
        self.assertEqual(self.app.game.seed,2026)
        self.assertEqual(self.app.game.empire_name,"Kies Federation")
        self.key(pg.K_RIGHT)
        self.key(pg.K_e)
        self.assertEqual(self.app.game.turn,2)
        self.key(pg.K_F5)
        expected=self.app.game.to_dict()
        self.key(pg.K_ESCAPE)
        self.click("main_menu")
        self.assertEqual(self.app.screen,"menu")
        self.app.game=None  # Simulate a fresh process, with only files retained.
        self.click("load")
        self.click("load_0")
        self.assertEqual(self.app.game.to_dict(),expected)

    def test_keyboard_navigation_empty_load_and_settings(self):
        self.key(pg.K_DOWN)
        self.key(pg.K_DOWN)
        self.key(pg.K_RETURN)
        self.assertEqual(self.app.screen,"load")
        self.assertEqual(self.app.load_rows,[])
        self.click("empty_new")
        self.key(pg.K_ESCAPE)
        self.click("settings")
        self.click("sound")
        self.click("animated_background")
        self.assertFalse(self.app.storage.load_settings()["sound"])
        self.assertFalse(self.app.storage.load_settings()["animated_background"])
        self.key(pg.K_ESCAPE)
        self.assertEqual(self.app.screen,"menu")

    def test_scaled_letterbox_and_quit_cancel(self):
        self.app.window=pg.display.set_mode((1000,900),pg.RESIZABLE)
        self.app.present()
        self.assertGreater(self.app.viewport.y,0)
        self.assertEqual(self.app.logical_pos((2,2)),(-1,-1))
        self.click("quit")
        self.assertIsNotNone(self.app.dialog)
        self.assertTrue(all(b.key.startswith("dialog_") for b in self.app.buttons))
        self.click("dialog_cancel")
        self.assertTrue(self.app.running)
        self.click("quit")
        self.click("dialog_ok")
        self.assertFalse(self.app.running)

    def test_save_failure_keeps_game_open_until_explicit_exit(self):
        self.app.game=new_game(seed=7)
        self.app.go("galaxy")
        with patch.object(self.app.storage,"save",side_effect=SaveError("Disk full")):
            self.app.quit_saved()
        self.app.render()
        self.assertTrue(self.app.running)
        self.assertEqual(self.app.dialog["label"],"Exit without saving")
        self.click("dialog_cancel")
        self.assertIsNotNone(self.app.game)

    def test_multiple_save_pages_and_corrupt_row_render(self):
        game=new_game(seed=24)
        for _ in range(5):
            self.app.storage.save(game)
            game.advance_turn()
        (self.app.storage.saves_dir/"bad.json").write_text("oops")
        self.app.go("load")
        self.app.render()
        self.assertEqual(len(self.app.load_rows),6)
        self.click("next")
        self.assertEqual(self.app.load_page,1)
        self.click("prev")
        self.assertEqual(self.app.load_page,0)


if __name__=="__main__":
    unittest.main()
