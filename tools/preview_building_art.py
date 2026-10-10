"""Render the building catalogue using the same PNG loader as the game."""

import argparse
import os
from pathlib import Path
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pygame as pg

from orion.building_art import draw_building_art
from orion.buildings import BUILDINGS
from orion.ui import GOLD, INK, MUTED, text


def render(output):
    pg.init()
    pg.display.set_mode((1, 1))
    canvas = pg.Surface((1600, 1796))
    canvas.fill((7, 15, 22))
    text(canvas, "ORION REACH", (44, 30), 15, GOLD, "mono", 3)
    text(canvas, "Colony architecture", (44, 61), 38, INK, "title")
    text(canvas, "Complete building set · Shared materials, lighting and perspective", (46, 112), 17, MUTED)
    order = ("headquarters", "factory", "shipyard", "research_lab", "trade_center", "mine",
             "hydroponic_farm", "barracks", "fortifications", "missile_base", "planetary_shield",
             "sensor_array", "jump_gate", "interdictor", "ascension_gate", "solar_array",
             "geothermal_plant", "fusion_plant", "thermal_plant", "singularity_plant")
    special = {"headquarters": "Headquarters palace", "shipyard": "Shipyard", "ascension_gate": "Ascension Gate"}
    for index, building_id in enumerate(order):
        x, y = 36+index%4*386, 158+index//4*316
        card = pg.Rect(x, y, 370, 300)
        pg.draw.rect(canvas, (12, 25, 34), card, border_radius=5)
        pg.draw.rect(canvas, (42, 62, 72), card, 1, border_radius=5)
        draw_building_art(canvas, building_id, (x+24, y+15, 322, 239))
        name = special.get(building_id) or BUILDINGS[building_id].name
        text(canvas, name, (x+18, y+267), 18, INK)
    text(canvas, "Original game artwork · v0.38.1", (44, 1759), 13, MUTED)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    pg.image.save(canvas, str(output))
    pg.quit()
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT/"screenshots/building_art_catalogue.png")
    print(render(parser.parse_args().output))
