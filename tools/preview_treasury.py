"""Capture interest in the budget, an imminent bankruptcy warning and defeat."""

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
from orion.model import new_game


def main():
    out = ROOT/"screenshots"
    out.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        app = App(Path(directory), capture=True)
        try:
            app.window = pg.display.set_mode((1440, 900), pg.RESIZABLE)
            app.game = new_game(seed=12, random_starts=False, with_ai=False,
                                with_guardians=False, with_black_holes=False,
                                with_tombs=False, with_encounters=False, fog_of_war=False)
            for system, planet in app.game.settlements("player"):
                app.game.set_trade_goods(system.id, planet.id)
            app.game.credits = -1000
            app.go("galaxy")
            app.open_empire()
            app.render()
            pg.image.save(app.canvas, str(out/"treasury_interest_v0840.png"))
            app.game.credits = -9500
            app.go("galaxy")
            app.render()
            pg.image.save(app.canvas, str(out/"treasury_warning_v0840.png"))
            app.advance_turn()
            assert app.screen == "result" and app.game.result.condition == "bankruptcy"
            app.render()
            pg.image.save(app.canvas, str(out/"treasury_bankruptcy_v0840.png"))
        finally:
            app.audio.close()
            pg.quit()
    print("Rendered debt budget, bankruptcy warning and defeat.")


if __name__ == "__main__":
    main()
