"""Capture the galaxy artwork, the plain map, and their Settings control."""

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
            app.window = pg.display.set_mode((1440, 900), pg.RESIZABLE)
            app.game = demonstration()
            app.go("galaxy")
            for enabled, name in ((True, "galaxy_nebula_background"),
                                  (False, "galaxy_plain_background")):
                app.settings["galaxy_background"] = enabled
                app.render()
                app.present()
                pg.image.save(app.window, str(ROOT / "screenshots" / (name + ".png")))
            app.settings["galaxy_background"] = True
            app.show_settings("pause")
            app.select_settings_section("graphics")
            app.render()
            app.present()
            pg.image.save(app.window, str(ROOT / "screenshots" / "galaxy_background_settings.png"))
        finally:
            app.audio.close()
            pg.quit()
    print("Rendered the galaxy image, plain map, and Settings screen.")


if __name__ == "__main__":
    main()
