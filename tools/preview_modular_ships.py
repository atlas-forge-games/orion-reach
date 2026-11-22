"""Render the shared ship sprites and actual designer, map and combat screens."""

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
from orion import modular_art, designer_controls
from orion.app import App
from orion.designs import HULLS
from orion.ship_fitting import build_design
from orion.model import new_game, Ship
from orion.research import TECHNOLOGIES
from orion.ui import CYAN, GOLD, INK, MUTED, text


def designs():
    result = {}
    for i, (kind, hull) in enumerate(HULLS.items()):
        weapons = ["laser", "laser", "torpedo", "point_defense", "torpedo", "point_defense"][:hull.external_mounts]
        systems = ["shield", "damage_control", "command_relay"][:hull.internal_bays]
        modules = weapons+systems+["engine", "reinforced_armor"]+["drone_bay"]*hull.hangar_bays
        result[kind] = build_design(f"design_{i+1}", "Modular "+hull.name, kind, modules)
    return result


def render(output):
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        app = App(Path(directory), capture=True)
        try:
            app.game = new_game(seed=131, with_ai=True, with_guardians=False, with_tombs=False,
                                with_encounters=False, with_black_holes=False, fog_of_war=False)
            app.game.technology.completed = list(TECHNOLOGIES)
            app.game.resources = app.game.credits = 50000
            app.game.designs = list(designs().values())
            app.settings["autosave"] = False
            app.window = pg.display.set_mode((1920, 1080), pg.RESIZABLE)
            app.open_designer()
            for design in app.game.designs:
                app.load_design(design)
                designer_controls.select(app, "core_1")
                app.render(); app.present()
                pg.image.save(app.window, str(output/f"designer_{design.kind}.png"))
            # Match all four classes of equipment at small and large UI sizes.
            for size in ((980, 900), (1280, 800)):
                app.window = pg.display.set_mode(size, pg.RESIZABLE)
                app.load_design(app.game.designs[0])
                app.render(); app.present()
                pg.image.save(app.window, str(output/f"designer_{size[0]}x{size[1]}.png"))
            app.window = pg.display.set_mode((1920, 1080), pg.RESIZABLE)
            app.game.ships = [Ship(i+1, design.kind, 0, design=design) for i, design in enumerate(app.game.designs)]
            app.game.ships += [Ship(21, "cruiser", 0, owner="rival", design=app.game.designs[2]),
                               Ship(22, "battleship", 0, owner="rival", design=app.game.designs[3])]
            app.game.next_ship_id = 23
            app.go("galaxy"); app.render(); app.present()
            pg.image.save(app.window, str(output/"modular_galaxy.png"))
            app.game.start_combat(0)
            app.go("combat"); app.combat_ship_id = 3
            app.render(); app.present()
            pg.image.save(app.window, str(output/"modular_combat.png"))
            canvas = pg.Surface((1800, 1280)); canvas.fill((7, 17, 25))
            text(canvas, "AGE OF THE STARS", (38, 24), 17, GOLD, "mono", 2)
            text(canvas, "Original hulls, fitted equipment", (38, 53), 34, INK, "title")
            for i, design in enumerate(app.game.designs):
                x, y = 28+(i%3)*590, 114+(i//3)*575
                pg.draw.rect(canvas, (16, 32, 42), (x, y, 574, 552), border_radius=10)
                text(canvas, HULLS[design.kind].name, (x+20, y+15), 25, INK, "title")
                modular_art.draw(canvas, design.kind, (x+12, y+65, 264, 399), design=design, cutaway=True)
                modular_art.draw(canvas, design.kind, (x+294, y+65, 264, 399), design=design)
                text(canvas, "DESIGNER CUTAWAY", (x+28, y+491), 12, CYAN, "mono")
                text(canvas, "IN FLIGHT / COMBAT", (x+307, y+491), 12, MUTED, "mono")
            pg.image.save(canvas, str(output/"modular_ship_catalogue.png"))
        finally:
            app.audio.close()
            pg.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT/"screenshots/modular-preview")
    render(parser.parse_args().output)
