"""Render the smaller galaxy labels and faction-colored fleets at game size."""

import argparse
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
from orion.exploration import refresh
from orion.galaxy_fleet_icons import draw_map_ship
from orion.model import new_game
from orion.ui import INK, MUTED, text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT/"screenshots")
    out = parser.parse_args().output
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        app = App(Path(directory), capture=True)
        try:
            app.window = pg.display.set_mode((1920, 1080))
            app.settings["animated_background"] = False
            app.game = new_game(seed=116545103, galaxy_size="Expansive",
                                rival_count="all", fog_of_war=False,
                                with_tombs=False, with_encounters=False,
                                with_guardians=True, random_starts=False)
            game = app.game
            # Put every civilization on the same map with a mix of parked and
            # travelling fleets, including the Wanderers' real mothership.
            for index, owner in enumerate(game.owners):
                ships = game.ships_owned_by(owner)
                if index % 3 != 1 or not ships:
                    continue
                ship = next((s for s in ships if s.kind == "scout"), ships[0])
                home = game.systems[ship.system_id]
                destination = min((s for s in game.systems if s.id != home.id and s.kind != "Black hole"),
                                  key=lambda s: (s.x-home.x)**2+(s.y-home.y)**2)
                ship.destination = destination.id
                ship.travel_total, ship.turns_remaining = 4, 2
                ship.departure_pending = False
            refresh(game)
            app.go("galaxy")
            app.inspector_collapsed = True
            before = game.to_dict()
            app.render()
            assert game.to_dict() == before
            pg.image.save(app.canvas, str(out/"galaxy_compact_factions.png"))
            chart = app.canvas.slot(app.map_rect).clip(app.canvas.get_rect())
            pg.image.save(app.canvas.subsurface(chart), str(out/"galaxy_compact_factions_map.png"))

            sheet = pg.Surface((1020, 440))
            sheet.fill((6, 13, 22))
            text(sheet, "Civilization colors at game size", (24, 18), 22, INK)
            text(sheet, "Parked / travelling / mothership", (24, 52), 14, MUTED)
            for index, owner in enumerate(game.owners):
                column, row = divmod(index, 7)
                x, y = 24+column*510, 108+row*46
                color = app.empire_color(owner)
                pg.draw.circle(sheet, color, (x+6, y), 5)
                name = game.empire_name_for(owner)
                text(sheet, name, (x+23, y-9), 15, color)
                for dx, heading, habitat in ((335, 0, False), (385, 55, False), (435, 0, True)):
                    draw_map_ship(sheet, (x+dx, y), color, habitat, heading)
            pg.image.save(sheet, str(out/"galaxy_faction_ship_colors.png"))
        finally:
            app.audio.close()
            pg.quit()
    print("Rendered compact galaxy map and all civilization colors.")


if __name__ == "__main__":
    main()
