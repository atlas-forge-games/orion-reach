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
from orion.model import GALAXY_SIZES, GameState, SaveError, generate_planets, new_game
from functools import partial

# Keep the original single-empire regression fixtures isolated from AI turns.
new_game = partial(new_game, with_ai=False, fog_of_war=False)
from orion.storage import SAVE_VERSION, Storage


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
        payload["version"]=SAVE_VERSION
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
        settings={"fullscreen":False,"animated_background":False,"sound":False,"music":False,"music_volume":40}
        self.store.save_settings(settings)
        self.assertEqual(self.store.load_settings(),settings)
        (self.store.root/"settings.json").write_text('{"sound":"false","fullscreen":true}')
        self.assertIs(self.store.load_settings()["sound"],True)
        (self.store.root/"settings.json").write_text("[]")
        self.assertEqual(self.store.load_settings()["fullscreen"],False)

    def test_v1_save_migration_preserves_campaign_and_original_file(self):
        old_game=new_game("Old campaign",seed=44)
        old_game.advance_turn()
        old_game.planet_at(0, 2).growth_progress=0  # v1 had no population growth.
        old_game.selected_system=4
        path=self.store.save(old_game)
        payload=json.loads(path.read_text())
        payload["version"]=1
        payload["game"].pop("selected_planet")
        payload["game"].pop("research")
        for system in payload["game"]["systems"]:
            system.pop("worlds")
        path.write_text(json.dumps(payload))
        before=path.read_bytes()
        migrated,_=self.store.load(path)
        self.assertEqual(path.read_bytes(),before)
        self.assertEqual(migrated,old_game)
        self.assertEqual(migrated.systems[0].worlds[2].name,"Earth")
        self.assertTrue(migrated.systems[0].worlds[2].colonized)
        new_path=self.store.save(migrated)
        self.assertEqual(json.loads(new_path.read_text())["version"],SAVE_VERSION)

    def test_planet_state_and_selection_are_persisted_not_regenerated(self):
        game=new_game(seed=29)
        game.selected_planet=2
        game.systems[0].worlds[2].population=9
        game.systems[0].worlds[1].richness="Rich"
        path=self.store.save(game)
        restored,_=self.store.load(path)
        self.assertEqual(restored,game)
        self.assertEqual(restored.systems[0].worlds[2].population,9)
        self.assertEqual(restored.selected_planet,2)

    def test_invalid_planet_data_is_rejected(self):
        game=new_game(seed=3)
        for failure in ("missing_worlds","count","name","orbit","id","selection"):
            with self.subTest(failure=failure):
                data=game.to_dict()
                if failure=="missing_worlds":
                    data["systems"][0].pop("worlds")
                elif failure=="count":
                    data["systems"][0]["worlds"].pop()
                elif failure=="name":
                    data["systems"][0]["worlds"][0]["name"]=""
                elif failure=="orbit":
                    data["systems"][0]["worlds"][1]["orbit_au"]=.01
                elif failure=="id":
                    data["systems"][0]["worlds"][0]["id"]=8
                elif failure=="selection":
                    data["selected_planet"]=99
                with self.assertRaises(SaveError):
                    GameState.from_dict(data)


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
        self.click_position(button.rect.center)

    def click_position(self,logical_pos):
        x,y=logical_pos
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

    def test_star_to_system_to_planet_and_back(self):
        self.app.game=new_game(seed=2408)
        self.app.go("galaxy")
        self.click("star_0")
        self.assertEqual(self.app.screen,"system")
        self.assertIsNone(self.app.game.selected_planet)
        self.click("world_2")
        self.assertEqual(self.app.screen,"planet")
        self.assertEqual(self.app.game.selected_planet,2)
        self.key(pg.K_ESCAPE)
        self.assertEqual(self.app.screen,"system")
        self.assertEqual(self.app.game.selected_planet,2)
        self.key(pg.K_ESCAPE)
        self.assertEqual(self.app.screen,"galaxy")
        self.assertEqual(self.app.game.selected_system,0)
        self.click("open_system")
        self.click("world_1")
        self.click("planet_return")
        self.click("system_back")
        self.assertEqual(self.app.screen,"galaxy")

    def test_navigation_works_at_actual_globe_positions_with_letterboxing(self):
        from orion.system_views import system_layout
        self.app.window=pg.display.set_mode((980,900),pg.RESIZABLE)
        self.app.present()
        self.app.game=new_game(seed=2408)
        self.app.go("galaxy")
        self.app.render()
        self.click_position(self.app.star_pos(self.app.game.systems[0]))
        self.assertEqual(self.app.screen,"system")
        center=system_layout(self.app.game.systems[0].worlds)[2][1]
        self.click_position(center)
        self.assertEqual(self.app.screen,"planet")
        self.assertEqual(self.app.game.selected_planet,2)

    def test_planet_pause_settings_save_load_and_context(self):
        self.app.game=new_game(seed=37)
        self.app.open_system(0)
        self.app.open_planet(2)
        self.key(pg.K_p)
        self.assertEqual(self.app.pause_return,"planet")
        self.click("settings")
        self.click("settings_done")
        self.click("resume")
        self.assertEqual(self.app.screen,"planet")
        self.key(pg.K_F5)
        self.assertFalse(self.app.notice_error)
        self.key(pg.K_p)
        self.click("main_menu")
        self.click("resume")
        self.assertEqual(self.app.screen,"planet")
        self.assertEqual(self.app.game.selected_planet,2)
        self.app.load_game(self.app.storage.saves_dir/"autosave.json")
        self.assertEqual(self.app.screen,"galaxy")
        self.click("star_0")
        self.key(pg.K_RETURN)
        self.assertEqual(self.app.screen,"planet")
        self.assertEqual(self.app.game.selected_planet,2)

    def test_keyboard_navigation_and_empty_system(self):
        self.app.game=new_game(seed=2408)
        self.app.go("galaxy")
        self.app.render()
        self.key(pg.K_RIGHT)
        self.key(pg.K_RETURN)
        self.assertEqual(self.app.screen,"system")
        self.assertEqual(self.app.game.selected_system,1)
        self.app.open_system(0)
        self.app.render()
        self.key(pg.K_RETURN)
        self.assertEqual(self.app.screen,"planet")
        self.assertEqual(self.app.game.selected_planet,2)
        self.key(pg.K_RIGHT)
        self.assertEqual(self.app.game.selected_planet,3)
        self.key(pg.K_LEFT)
        self.assertEqual(self.app.game.selected_planet,2)
        empty=next(s for s in self.app.game.systems if not s.worlds)
        self.app.open_system(empty.id)
        self.app.render()
        self.assertIsNone(self.app.game.selected_planet)
        self.assertFalse(any(b.key.startswith("world_") for b in self.app.buttons))
        self.key(pg.K_RIGHT)
        self.click("system_back")
        self.assertEqual(self.app.screen,"galaxy")

    def test_eight_world_layout_has_separate_click_targets(self):
        from orion.system_views import system_layout
        self.app.game=new_game(seed=7)
        system=self.app.game.systems[1]
        system.planets=8
        system.worlds=generate_planets(system,7)
        self.app.open_system(1)
        layout=system_layout(system.worlds)
        for i,(world,center,diameter,rect) in enumerate(layout):
            self.assertTrue(pg.Rect(64,308,1312,311).contains(rect))
            for other in layout[i+1:]:
                self.assertFalse(rect.colliderect(other[3]))
            self.app.go("system")
            self.app.render()
            self.click_position(center)
            self.assertEqual(self.app.game.selected_planet,world.id)
            self.assertEqual(self.app.screen,"planet")

    def test_colony_construction_cancel_and_demolition_at_scaled_size(self):
        self.app.window=pg.display.set_mode((980,900),pg.RESIZABLE)
        self.app.present()
        self.app.game=new_game(seed=2408)
        self.app.go("galaxy")
        self.click("star_0")
        self.click("world_2")
        self.app.go("colony")
        self.app.render()
        self.assertEqual(self.app.screen,"colony")
        earth=self.app.game.systems[0].worlds[2]
        self.click("build_factory")
        self.assertEqual(self.app.game.credits,75)
        self.assertEqual(earth.used_slots,1)
        saved,_=self.app.storage.load(self.app.storage.saves_dir/"autosave.json")
        self.assertEqual(saved,self.app.game)
        self.click("colony_end_turn")
        self.assertEqual(earth.construction_queue[0].progress,6)
        self.click("cancel_construction")
        self.assertEqual(self.app.game.credits,116)
        self.assertEqual(earth.used_slots,0)
        self.click("build_factory")
        for _ in range(4):
            self.key(pg.K_e)
        self.assertEqual(earth.buildings,["factory"])
        self.assertEqual(earth.industry_per_turn,10)
        self.click("colony_slot_0")
        self.click("demolish_building")
        self.assertIsNotNone(self.app.dialog)
        self.click("dialog_cancel")
        self.assertEqual(earth.buildings,["factory"])
        credits=self.app.game.credits
        self.click("demolish_building")
        self.click("dialog_ok")
        self.assertEqual(earth.industry_per_turn,6)
        self.assertEqual(earth.used_slots,0)
        self.assertEqual(self.app.game.credits,credits)

    def test_colony_controls_disable_for_uncolonized_full_and_unaffordable(self):
        self.app.game=new_game(seed=2408)
        self.app.open_system(0)
        self.app.open_planet(3)
        self.app.go("colony")
        self.app.render()
        before=self.app.game.to_dict()
        self.assertTrue(all(not b.enabled for b in self.app.buttons if b.key.startswith("build_")))
        self.click("build_factory")
        self.assertEqual(self.app.game.to_dict(),before)
        self.key(pg.K_LEFT)
        self.assertEqual(self.app.game.selected_planet,2)
        self.assertEqual(self.app.screen,"colony")
        earth=self.app.game.systems[0].worlds[2]
        earth.size="Tiny"
        self.app.game.credits=1000
        for _ in range(4):
            self.click("build_mine")
        self.assertEqual(len([b for b in self.app.buttons if b.key.startswith("colony_slot_")]),4)
        self.assertTrue(all(not b.enabled for b in self.app.buttons if b.key.startswith("build_")))
        before=self.app.game.to_dict()
        self.click("build_factory")
        self.assertEqual(self.app.game.to_dict(),before)
        self.click("cancel_construction")
        self.app.game.credits=29
        self.app.render()
        self.assertTrue(all(not b.enabled for b in self.app.buttons if b.key.startswith("build_")))

    def test_colony_pause_save_load_and_back_navigation(self):
        self.app.game=new_game(seed=38)
        self.app.open_system(0)
        self.app.open_planet(2)
        self.app.go("colony")
        self.app.render()
        self.click("build_mine")
        self.key(pg.K_e)
        expected=self.app.game.to_dict()
        self.click("colony_pause")
        self.click("settings")
        self.click("settings_done")
        self.click("resume")
        self.assertEqual(self.app.screen,"colony")
        self.click("colony_save")
        path=next(p for p in self.app.storage.saves_dir.glob("*.json") if p.name!="autosave.json")
        self.app.load_game(path)
        self.click("star_0")
        self.click("world_2")
        self.app.go("colony")
        self.app.render()
        self.assertEqual(self.app.game.to_dict(),expected)
        self.key(pg.K_ESCAPE)
        self.assertEqual(self.app.screen,"planet")
        self.key(pg.K_ESCAPE)
        self.assertEqual(self.app.screen,"system")


if __name__=="__main__":
    unittest.main()
