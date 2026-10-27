"""Capture illustrated docks, flight headings, and the unchanged Classic map."""

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
from orion.galaxy_fleet_icons import draw_map_ship
from orion.model import Ship
from orion.ui import INK, MUTED, text
from preview_galaxy_styles import demonstration


def main():
    out = ROOT/"screenshots"
    with tempfile.TemporaryDirectory() as directory:
        app = App(Path(directory), capture=True)
        try:
            app.window = pg.display.set_mode((1440, 900), pg.RESIZABLE)
            app.game = demonstration()
            app.go("galaxy")
            for style in ("classic", "clean"):
                app.set_galaxy_style(style)
                app.render()
                pg.image.save(app.canvas, str(out/f"galaxy_{style}_v0832.png"))
            for ship in app.game.ships:
                if ship.departure_pending:
                    ship.departure_pending = False
                    ship.turns_remaining -= 1
            app.render()
            pg.image.save(app.canvas, str(out/"galaxy_flights_v0832.png"))
            home = app.game.systems[0]
            app.game.ships = [Ship(1, "frigate", home.id), Ship(2, "colony_ship", home.id),
                              Ship(3, "frigate", home.id, owner="rival")]
            app.game.next_ship_id = 4
            app.map_camera.zoom = 3
            app.map_camera.center_on(home.x, home.y, MAP)
            app.render()
            pg.image.save(app.canvas, str(out/"galaxy_docked_v0832.png"))
            # Native-size rendering of all eight headings for visual QA.
            sheet = pg.Surface((720, 270))
            sheet.fill((6, 13, 22))
            text(sheet, "MAP ICONS AT GAME SIZE", (24, 20), 17, INK)
            for row, (label, color, habitat) in enumerate((("Player fleet", (44, 164, 255), False),
                                                         ("Rival fleet", (250, 168, 111), False),
                                                         ("Mothership", (203, 169, 255), True))):
                y = 94+row*64
                text(sheet, label, (24, y-8), 14, MUTED)
                for col, heading in enumerate(range(0, 360, 45)):
                    x = 210+col*62
                    draw_map_ship(sheet, (x, y), color, habitat, heading)
                    if row == 0:
                        text(sheet, str(heading)+"°", (x-10, y-40), 11, MUTED)
            pg.image.save(sheet, str(out/"galaxy_icon_headings_v0832.png"))
        finally:
            app.audio.close()
            pg.quit()
    print("Rendered v0.83.2 fleet icons, docked fleets, flights and Classic.")


if __name__ == "__main__":
    main()
