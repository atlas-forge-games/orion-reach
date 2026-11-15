"""Render the actual queued position and the next two turns of the same voyage."""

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
from orion.galaxy_fleet_view import fleet_markers
from orion.model import Ship, new_game


def main():
    output = ROOT/"screenshots"/"route_departure_progress.png"
    output.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        app = App(Path(directory), capture=True)
        try:
            app.window = pg.display.set_mode((1440, 900), pg.RESIZABLE)
            app.game = new_game(seed=804, random_starts=False, with_ai=False,
                                with_guardians=False, with_tombs=False,
                                with_encounters=False, with_black_holes=False,
                                fog_of_war=False)
            origin, target = app.game.systems[:2]
            origin.x, origin.y = .54, .5
            target.x, target.y = .458, .495
            target.name = "Menkar"
            for star in app.game.systems[2:]:
                star.x, star.y = .1, .1
            app.game.ships = [Ship(1, "scout", 0), Ship(2, "scout", 0),
                              Ship(3, "scout", 1)]
            app.game.next_ship_id = 4
            app.go("galaxy")
            app.map_camera.zoom = 4
            app.map_camera.center_on((origin.x+target.x)/2, .5, app.map_rect)
            app.game.send_ship(1, target.id)
            app.mouse = (-1, -1)
            start = pg.Vector2(app.star_pos(origin))
            destination = pg.Vector2(app.star_pos(target))
            direction = destination-start
            crop = pg.Rect(round(min(start.x, destination.x))-90,
                           round(min(start.y, destination.y))-70,
                           round(abs(direction.x))+180, 190)
            board = pg.Surface((crop.w, 3*(crop.h+44)))
            board.fill((5, 12, 20))
            label_font = pg.font.Font(None, 25)
            previous = None
            labels = ("Order issued - at the beginning", "After 1 turn", "After 2 turns")
            for index, label in enumerate(labels):
                if index:
                    app.game.advance_turn()
                snapshot = app.game.to_dict()
                app.render()
                assert app.game.to_dict() == snapshot
                center = next(rect.center for ships, rect, _ in fleet_markers(app, app.map_rect)
                              if any(ship.id == 1 for ship in ships))
                distance = (pg.Vector2(center)-start).dot(direction.normalize())
                if previous is None:
                    assert distance <= direction.length()*.1+1
                else:
                    assert distance > previous
                previous = distance
                y = index*(crop.h+44)
                board.blit(label_font.render(label, True, (211, 226, 234)), (18, y+12))
                board.blit(app.canvas, (0, y+44), crop)
                print(f"{label}: {distance:.1f} / {direction.length():.1f} pixels")
            pg.image.save(board, str(output))
            print(output)
        finally:
            app.audio.close()
            pg.quit()


if __name__ == "__main__":
    main()
