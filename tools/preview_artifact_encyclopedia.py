"""Render planned flagship and capital artifacts in the real encyclopedia."""

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
from preview_galaxy_colors import demonstration


def main():
    with tempfile.TemporaryDirectory() as directory:
        app = App(Path(directory), capture=True)
        try:
            app.game = demonstration()
            app.go("galaxy")
            app.open_info()
            app.select_info_category("artifacts")
            for identifier, name in (("heart_of_a_dead_sun", "flagship"),
                                     ("worldseed", "capital"),
                                     ("throne_of_the_last_emperor", "last_page")):
                app.select_info_article("artifact_"+identifier)
                app.render()
                app.present()
                pg.image.save(app.window, str(ROOT/"screenshots"/f"encyclopedia_artifact_{name}.png"))
        finally:
            app.audio.close()
            pg.quit()
    print("Rendered three encyclopedia artifact previews.")


if __name__ == "__main__":
    main()
