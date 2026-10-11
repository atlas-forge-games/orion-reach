"""Render support-ship artwork and the actual shipyard, fleet and combat screens."""

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
from orion import __version__
from orion.app import App
from orion.fleet_art import ship_icon, ship_sprite
from orion.first_contact import acknowledge, pending
from orion.model import new_game, Ship
from orion.production import SHIP_TYPES
from orion.ui import CYAN, GOLD, INK, LINE, MUTED, panel, text


SUPPORT_SHIPS = (
    ("troop_transport", "Armored personnel modules", "Carry an invasion force"),
    ("colony_ship", "Habitat pods and greenhouses", "Establish a new colony"),
    ("scout", "Sensor dishes and survey optics", "Chart unexplored systems"),
)


def catalogue(output):
    pg.init()
    pg.display.set_mode((1, 1))
    try:
        canvas = pg.Surface((1600, 900))
        canvas.fill((7, 15, 22))
        text(canvas, "ORION REACH", (44, 28), 15, GOLD, "mono", 3)
        text(canvas, "Exploration and expedition ships", (44, 57), 39, INK, "title")
        text(canvas, "Three distinct roles. One fleet.", (46, 111), 17, MUTED)
        for index, (kind, features, role) in enumerate(SUPPORT_SHIPS):
            x, y = 36+index*514, 157
            panel(canvas, (x, y, 498, 680), (12, 25, 34), LINE)
            sprite = ship_sprite(kind, 386)
            if sprite is None:
                raise RuntimeError(f"Missing ship illustration: {kind}")
            canvas.blit(sprite, sprite.get_rect(center=(x+249, y+215)))
            text(canvas, SHIP_TYPES[kind].name, (x+24, y+433), 28, INK, "title")
            text(canvas, features, (x+25, y+480), 16, CYAN)
            text(canvas, role+" · Unarmed", (x+25, y+511), 14, MUTED)
            pg.draw.line(canvas, LINE, (x+24, y+547), (x+474, y+547))
            text(canvas, "SHIPYARD", (x+26, y+566), 10, GOLD, "mono", 1)
            text(canvas, "FLEET", (x+174, y+566), 10, GOLD, "mono", 1)
            text(canvas, "COMBAT", (x+309, y+566), 10, GOLD, "mono", 1)
            ship_icon(canvas, (x+76, y+620), 1.0, kind=kind)
            ship_icon(canvas, (x+202, y+620), .67, kind=kind)
            ship_icon(canvas, (x+330, y+620), .55, kind=kind, facing=1)
            ship_icon(canvas, (x+420, y+620), .55, (221, 129, 103), kind=kind, facing=-1)
        text(canvas, "Original support ships · Same materials and lighting as the warship fleet", (44, 863), 13, MUTED)
        text(canvas, f"v{__version__}", (1560, 864), 12, MUTED, right=True)
        pg.image.save(canvas, str(output/"support_ship_art.png"))
    finally:
        pg.quit()


def screens(output):
    with tempfile.TemporaryDirectory() as folder:
        app = App(Path(folder), capture=True)
        try:
            game = new_game(seed=2408, random_starts=False, with_guardians=False,
                            with_tombs=False, fog_of_war=False)
            for owner in pending(game):
                acknowledge(game, owner)
            app.game = game
            system, planet = game.headquarters()
            game.credits = game.resources = 2000
            if "barracks" not in planet.buildings:
                planet.buildings.append("barracks")
            kinds = ("scout", "colony_ship", "troop_transport", "frigate")
            game.ships = [Ship(index, kind, system.id) for index, kind in enumerate(kinds, 1)]
            game.next_ship_id = 5
            for kind in kinds[:3]:
                game.queue_ship(system.id, planet.id, kind)
            app.open_shipyard(system.id, planet.id)
            app.render()
            pg.image.save(app.canvas, str(output/"support_shipyard.png"))
            app.open_fleets()
            app.render()
            pg.image.save(app.canvas, str(output/"support_fleet.png"))
            game.ships.append(Ship(game.next_ship_id, "frigate", system.id, owner="rival"))
            game.next_ship_id += 1
            game.start_combat(system.id)
            app.go("combat")
            app.combat_ship_id = 3
            app.combat_target_id = 5
            app.render()
            pg.image.save(app.canvas, str(output/"support_ship_combat.png"))
        finally:
            app.audio.close()
            pg.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT/"screenshots")
    destination = parser.parse_args().output
    destination.mkdir(parents=True, exist_ok=True)
    catalogue(destination)
    screens(destination)
    print(destination)
