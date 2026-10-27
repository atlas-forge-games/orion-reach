"""Render active flight paths in the busy galaxy and a zoomed camera view."""

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
from orion.app import App, MAP
from preview_galaxy_styles import demonstration


def main():
    out = ROOT/"screenshots"
    out.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        app = App(Path(directory), capture=True)
        try:
            app.window = pg.display.set_mode((1440, 900), pg.RESIZABLE)
            app.game = demonstration()
            for ship in app.game.ships:
                if ship.departure_pending:
                    ship.departure_pending = False
                    ship.turns_remaining -= 1
            app.go("galaxy")
            before = app.game.to_dict()
            for style in ("classic", "clean"):
                app.set_galaxy_style(style)
                app.render()
                pg.image.save(app.canvas, str(out/f"galaxy_routes_{style}_v0833.png"))
            ship = next(s for s in app.game.ships if s.in_transit)
            origin, target = app.game.systems[ship.system_id], app.game.systems[ship.destination]
            app.map_camera.zoom = 3
            app.map_camera.center_on((origin.x+target.x)/2, (origin.y+target.y)/2, MAP)
            app.render()
            pg.image.save(app.canvas, str(out/"galaxy_routes_zoomed_v0833.png"))
            assert app.game.to_dict() == before
        finally:
            app.audio.close()
            pg.quit()
    print("Rendered active routes in Clean, Classic and a zoomed Clean map.")


if __name__ == "__main__":
    main()
