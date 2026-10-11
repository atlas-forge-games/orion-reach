"""Render real planet-bound batteries and their surface missile effects."""

from io import BytesIO
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
from orion import defenses
from orion.app import App
from orion.model import PLAYER, RIVAL, Ship, new_game


def scenario(*, enemy_ships=True, damaged_base=False, extra_world=False):
    game = new_game(seed=2408, fog_of_war=False, random_starts=False,
                    with_tombs=False, with_guardians=False, with_black_holes=False)
    earth = game.planet_at(0, 2)
    mars = game.planet_at(0, 3)
    mars.colonized, mars.owner, mars.population, mars.biome = True, RIVAL, 3, "Desert"
    worlds = [earth, mars]
    if extra_world:
        venus = game.planet_at(0, 1)
        venus.colonized, venus.owner, venus.population, venus.biome = True, PLAYER, 3, "Tundra"
        worlds.append(venus)
    for world in worlds:
        world.buildings.append("missile_base")
        defenses.commissioned(game, world, "missile_base")
    if damaged_base:
        mars.battery_hull = 5
    rows = [("cruiser", PLAYER)]*3+([("frigate", RIVAL)]*2 if enemy_ships else [])
    game.ships = [Ship(i, kind, 0, owner=owner) for i, (kind, owner) in enumerate(rows, 1)]
    game.next_ship_id = len(rows)+1
    game.start_combat(0)
    return game, earth, mars


def main():
    with tempfile.TemporaryDirectory() as directory:
        app = App(Path(directory), capture=True)
        try:
            app.window = pg.display.set_mode((1440, 900), pg.RESIZABLE)
            game, earth, mars = scenario(extra_world=True)
            app.game = game
            app.go("combat")
            app.select_combat_ship(PLAYER, defenses.base_id(0, earth.id))
            app.select_combat_ship(RIVAL, defenses.base_id(0, mars.id))

            def capture(name):
                app.render()
                app.present()
                buffer = BytesIO()
                pg.image.save(app.window, buffer, "preview.png")
                (ROOT/"screenshots"/(name+".png")).write_bytes(buffer.getvalue())

            def tick(seconds=2):
                app.time += seconds
                app.update_combat()

            capture("planetary_combat_defense")
            app.combat_action("fire")
            assert app.combat_animation is not None
            tick(.035)
            capture("planetary_combat_missiles")
            tick()
            app.toggle_combat_auto()
            for _ in range(1000):
                tick()
                target = game.combat.ship(defenses.base_id(0, mars.id))
                if target.hull == 0 and app.combat_animation is None:
                    capture("planetary_combat_destroyed")
                    break
            else:
                raise AssertionError("Planetary battery was not destroyed")
        finally:
            app.audio.close()
            pg.quit()
    print("Rendered planetary batteries, surface missile fire and the surviving world.")


if __name__ == "__main__":
    main()
