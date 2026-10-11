"""Render automatic orders, manual takeover and results in the real combat UI."""

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
from orion.app import App
from orion.model import PLAYER, RIVAL, Ship, new_game


def main():
    with tempfile.TemporaryDirectory() as directory:
        app = App(Path(directory), capture=True)
        try:
            app.window = pg.display.set_mode((1440, 900), pg.RESIZABLE)
            game = app.game = new_game(seed=42, fog_of_war=False, random_starts=False,
                                       with_tombs=False, with_guardians=False, with_black_holes=False)
            ships = [("cruiser", PLAYER)]*3+[("carrier", PLAYER)]+[("destroyer", RIVAL)]*3
            game.ships = [Ship(i, kind, 0, owner=owner) for i, (kind, owner) in enumerate(ships, 1)]
            game.next_ship_id = len(game.ships)+1
            game.start_combat(0)
            app.go("combat")

            def capture(name):
                app.render()
                app.present()
                buffer = BytesIO()
                pg.image.save(app.window, buffer, "preview.png")
                (ROOT/"screenshots"/(name+".png")).write_bytes(buffer.getvalue())

            def tick(seconds=2):
                app.time += seconds
                app.update_combat()

            app.toggle_combat_auto()
            for _ in range(100):
                tick()
                effect = app.combat_animation
                if effect and effect.kind == "fire" and game.combat.ship(effect.ship_id).owner == PLAYER:
                    tick(.2)
                    capture("autocombat_active")
                    break
            else:
                raise AssertionError("Player fleet did not fire")

            app.toggle_combat_auto()
            tick()
            capture("autocombat_take_control")
            app.toggle_combat_auto()
            for _ in range(1500):
                tick()
                if game.combat.status != "active" and app.combat_animation is None:
                    capture("autocombat_result")
                    break
            else:
                raise AssertionError("Automatic battle did not finish")
        finally:
            app.audio.close()
            pg.quit()
    print("Rendered automatic combat, manual takeover and battle results.")


if __name__ == "__main__":
    main()
