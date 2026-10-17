"""Render the real galaxy UI with the rival home system still undiscovered."""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
from pathlib import Path
import sys
import tempfile
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pygame as pg
from orion.app import App
from orion.model import new_game

with tempfile.TemporaryDirectory() as folder:
    app = App(Path(folder), capture=True)
    try:
        app.game = new_game(seed=4242, galaxy_size="Compact", rival_race_id="serevan",
                            random_starts=False, with_guardians=False,
                            with_tombs=False, with_black_holes=False, with_encounters=False)
        app.go("galaxy")
        app.select_star(app.game.opponent.home_system)
        app.mouse = (-1, -1)
        app.render()
        output = ROOT / "screenshots" / "v0691_hidden_names.png"
        pg.image.save(app.canvas, str(output))
        print(output)
    finally:
        app.audio.close()
        pg.quit()
