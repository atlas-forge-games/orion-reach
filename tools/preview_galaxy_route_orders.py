"""Capture a route under the pointer and its immediate post-click placement."""

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
from orion.model import Ship, new_game


def main():
    out = ROOT/"screenshots"
    out.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        app = App(Path(directory), capture=True)
        try:
            app.window = pg.display.set_mode((1440, 900), pg.RESIZABLE)
            app.game = new_game(seed=804, random_starts=False, with_ai=False,
                                with_guardians=False, with_tombs=False,
                                with_encounters=False, fog_of_war=False)
            origin, target = app.game.systems[:2]
            origin.x, origin.y = .5, .6
            target.x, target.y = .525, .55
            app.game.ships = [Ship(1, "frigate", 0), Ship(2, "frigate", 0), Ship(3, "scout", 0)]
            app.game.next_ship_id = 4
            app.go("galaxy")
            app.map_camera.zoom = 3
            app.map_camera.center_on((origin.x+target.x)/2, (origin.y+target.y)/2, MAP)
            app.open_map_fleet(1)
            app.toggle_fleet_ship(3)  # Leave a ship docked to show the split clearly.
            app.mouse = app.star_pos(target)
            app.keyboard_mode = False
            before = app.game.to_dict()
            app.render()
            assert app.game.to_dict() == before
            pg.image.save(app.canvas, str(out/"galaxy_route_hover_v0834.png"))
            app.select_star(target.id)
            assert app.game.ship_at(1).departure_pending
            assert app.game.turn == before["turn"]
            app.render()
            pg.image.save(app.canvas, str(out/"galaxy_route_queued_v0834.png"))
            app.set_galaxy_style("classic")
            app.render()
            pg.image.save(app.canvas, str(out/"galaxy_route_classic_v0834.png"))
            app.set_galaxy_style("clean")
            app.close_fleet_popup()
            app.mouse = (-1, -1)
            app.render()
            pg.image.save(app.canvas, str(out/"galaxy_route_closed_v0834.png"))
        finally:
            app.audio.close()
            pg.quit()
    print("Rendered hovered, queued and closed fleet orders, plus Classic.")


if __name__ == "__main__":
    main()
