"""Capture the supplied Varkesh portrait and in-game diplomatic transmissions."""

import os
from pathlib import Path
import sys
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pygame as pg
from orion.app import App
from orion.model import new_game


def main():
    output = ROOT/"screenshots"
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        app = App(Path(folder), capture=True)
        try:
            app.choose_race("varkesh")
            app.go("race_select")
            app.render()
            pg.image.save(app.canvas, str(output/"varkesh_warlord_race.png"))
            app.go("setup")
            app.render()

            app.game = new_game(seed=2408, race_id="terran", rival_race_id="varkesh",
                                fog_of_war=False, with_guardians=False,
                                with_tombs=False)
            app.go("galaxy")
            app.show_first_contact()
            app.render()
            pg.image.save(app.canvas, str(output/"varkesh_warlord_contact.png"))

            app.finish_contact()
            app.open_diplomacy()
            app.diplomatic_action("envoy")
            app.diplomatic_action("gift")
            app.notice = ""
            app.render()
            pg.image.save(app.canvas, str(output/"varkesh_warlord_diplomacy.png"))
        finally:
            app.audio.close()
            pg.quit()
    print(output)


if __name__ == "__main__":
    main()
