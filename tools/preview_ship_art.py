"""Render the ship artwork and real research, design, shipyard and carrier screens."""

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
from orion.designs import HULLS
from orion.fleet_art import load_ship_art, ship_icon
from orion.first_contact import acknowledge, pending
from orion.model import new_game, Ship
from orion.research import TECHNOLOGIES
from orion.ui import CYAN, GOLD, INK, LINE, MUTED, panel, text


def catalogue(output):
    pg.init(); pg.display.set_mode((1, 1))
    canvas = pg.Surface((1600, 1150)); canvas.fill((7, 15, 22))
    text(canvas, "ORION REACH", (44, 28), 15, GOLD, "mono", 3)
    text(canvas, "Starship engineering", (44, 57), 39, INK, "title")
    text(canvas, "Research the hull. Build the fleet. Launch the drones.", (46, 110), 17, MUTED)
    roles = {"frigate": "Starting escort", "destroyer": "Fast torpedo attack", "cruiser": "Versatile frontline hull",
             "battleship": "Heavy gun platform", "carrier": "Drone command ship", "titan": "Capital flagship"}
    for index, (kind, spec) in enumerate(HULLS.items()):
        x, y = 36+(index%3)*514, 157+(index//3)*421
        panel(canvas, (x, y, 498, 405), (12, 25, 34), LINE)
        sprite = load_ship_art(kind)
        scaled = pg.transform.smoothscale(sprite, (round(sprite.get_width()*275/sprite.get_height()), 275))
        canvas.blit(scaled, scaled.get_rect(center=(x+249, y+155)))
        text(canvas, spec.name, (x+20, y+300), 27, INK, "title")
        text(canvas, roles[kind], (x+21, y+341), 15, CYAN)
        text(canvas, f"{spec.hull} base hull · {spec.capacity} module capacity", (x+21, y+373), 12, MUTED)
    panel(canvas, (36, 1017, 1526, 96), (12, 25, 34), GOLD)
    ship_icon(canvas, (107, 1065), 1.75, kind="combat_drone", facing=1)
    text(canvas, "COMBAT DRONES", (180, 1035), 13, GOLD, "mono", 1)
    text(canvas, "Each bay: 2 active drones · 4 launches per battle · Launch instead of firing", (180, 1067), 17, INK)
    text(canvas, "v0.39.0", (1561, 1126), 12, MUTED, right=True)
    pg.image.save(canvas, str(output/"ship_art_catalogue.png")); pg.quit()


def screens(output):
    with tempfile.TemporaryDirectory() as folder:
        app = App(Path(folder), capture=True)
        game = new_game(seed=2408, random_starts=False, with_guardians=False, with_tombs=False, fog_of_war=False)
        for owner in pending(game):
            acknowledge(game, owner)
        app.game = game
        game.credits = game.resources = 5000
        game.selected_planet = 2
        for identifier in ("destroyer_hulls", "cruiser_hulls"):
            game.research += TECHNOLOGIES[identifier].cost; game.choose_research(identifier)
        app.go("galaxy"); app.open_research(); app.select_research_branch("starships"); app.select_research_tier(3)
        app.render(); pg.image.save(app.canvas, str(output/"ship_research.png"))
        game.research = 120; game.choose_research("drone_carriers")
        design = game.save_design("Vigilant", "carrier", ["drone_bay", "drone_bay", "laser", "point_defense", "armor"])
        app.open_designer(); app.load_design(design); app.render()
        pg.image.save(app.canvas, str(output/"carrier_designer.png"))
        app.open_shipyard(0, 2); app.shipyard_catalog_page = 1; app.render()
        pg.image.save(app.canvas, str(output/"ship_classes.png"))
        game.ships = [Ship(1, "carrier", 0, design=design), Ship(2, "destroyer", 0),
                      Ship(3, "cruiser", 0, owner="rival"), Ship(4, "frigate", 0, owner="rival")]
        game.next_ship_id = 5
        game.start_combat(0)
        game.combat_move(1, 5, 4); game.combat_move(2, 7, 6)
        drones = game.combat_launch_drones(1)
        game.combat_move(drones[0], 10, 3)
        game.combat_move(drones[1], 9, 5)
        game.combat_end_turn(); game.combat_end_turn("rival")
        app.go("combat"); app.combat_ship_id = 1; app.combat_target_id = 3; app.render()
        pg.image.save(app.canvas, str(output/"carrier_combat.png"))
        app.audio.close(); pg.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT/"screenshots")
    destination = parser.parse_args().output
    destination.mkdir(parents=True, exist_ok=True)
    catalogue(destination); screens(destination)
    print(destination)
