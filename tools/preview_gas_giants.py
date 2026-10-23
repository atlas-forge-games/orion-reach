"""Render a generated gas giant in the actual system and atmospheric views."""
import os
from pathlib import Path
import sys
import tempfile

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pygame as pg
from orion.app import App
from orion.model import new_game


def main():
    output = ROOT / 'screenshots'
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        app = App(Path(directory), capture=True)
        try:
            app.window = pg.display.set_mode((1440, 900), pg.RESIZABLE)
            app.game = new_game(seed=2408, with_ai=False, fog_of_war=False)
            system, giant = next((s, p) for s in app.game.systems for p in s.worlds if p.is_gas_giant)
            app.open_system(system.id)
            app.render()
            pg.image.save(app.canvas, str(output / 'v079_gas_giant_system.png'))
            app.open_planet(giant.id)
            app.render()
            pg.image.save(app.canvas, str(output / 'v079_gas_giant_overview.png'))
        finally:
            app.audio.close()
            pg.quit()
    print('Rendered gas giant system and atmospheric overview.')


if __name__ == '__main__':
    main()
