"""Render both styles from one busy campaign without changing the game state."""

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
from orion.model import Ship, new_game


def demonstration():
    game = new_game(seed=116545103, galaxy_size="Expansive", rival_count=3,
                    fog_of_war=False, with_guardians=True, with_tombs=False,
                    with_encounters=False, with_black_holes=True, random_starts=False)
    systems = [s for s in game.systems if s.kind != "Black hole"]
    game.ships = []
    for index, system in enumerate(systems):
        if index % 3 == 1:
            continue
        owner = game.owners[index % len(game.owners)]
        for number in range(1+index % 4):
            ship = Ship(len(game.ships)+1, "scout" if number == 0 else "frigate", system.id, owner=owner)
            if index % 5 == 0:
                destination = min((s for s in systems if s.id != system.id),
                                  key=lambda s: (s.x-system.x)**2+(s.y-system.y)**2)
                ship.destination = destination.id
                ship.travel_total = ship.turns_remaining = 3
                ship.departure_pending = True
            game.ships.append(ship)
    game.next_ship_id = len(game.ships)+1
    refresh(game)
    game.selected_system = 0
    return game


def main():
    destination = ROOT/"screenshots"
    destination.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        app = App(Path(directory), capture=True)
        try:
            app.window = pg.display.set_mode((1440, 900), pg.RESIZABLE)
            app.game = demonstration()
            app.go("galaxy")
            before = app.game.to_dict()
            for style in ("clean", "classic"):
                app.set_galaxy_style(style)
                app.render()
                app.present()
                pg.image.save(app.canvas, str(destination/f"galaxy_{style}_v0831.png"))
                assert app.game.to_dict() == before
            app.set_galaxy_style("clean")
            app.open_map_fleet(app.game.ships[0].id)
            app.render()
            pg.image.save(app.canvas, str(destination/"galaxy_fleet_details_v0831.png"))
            app.show_settings("pause")
            app.select_settings_section("interface")
            app.render()
            pg.image.save(app.canvas, str(destination/"galaxy_style_options_v0831.png"))
        finally:
            app.audio.close()
            pg.quit()
    print("Rendered Clean, Classic, fleet details and Interface settings.")


if __name__ == "__main__":
    main()
