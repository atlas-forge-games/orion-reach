"""Render the actual Info dock button and encyclopedia at normal window size."""

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
            def capture(name):
                app.render()
                app.present()
                pg.image.save(app.window, str(ROOT/"screenshots"/name))

            app.game = demonstration()
            app.go("galaxy")
            capture("galaxy_info_button.png")
            app.open_info()
            capture("encyclopedia_overview.png")
            app.select_info_category("buildings")
            app.select_info_article("building_thermal_plant")
            capture("encyclopedia_buildings.png")
            app.select_info_category("research")
            app.select_info_article("technology_graviton_beams")
            capture("encyclopedia_research.png")
        finally:
            app.audio.close()
            pg.quit()
    print("Rendered the Info button and three encyclopedia views.")


if __name__ == "__main__":
    main()
