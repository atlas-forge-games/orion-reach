"""Render every landscape through the actual planet overview."""

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
from orion import __version__
from orion.exploration import refresh
from orion.model import BIOMES, new_game


def main():
    output = ROOT / 'screenshots'
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        app = App(Path(directory), capture=True)
        try:
            app.window = pg.display.set_mode((1440, 900), pg.RESIZABLE)
            app.game = new_game(seed=2408, with_ai=False, fog_of_war=False,
                                random_starts=False, with_tombs=False,
                                with_guardians=False, with_black_holes=False)
            home = app.game.planet_at(0, 2)
            home.buildings = ['hydroponic_farm', 'fusion_plant', 'solar_array']
            for biome in BIOMES:
                home.biome = biome
                refresh(app.game)
                app.open_planet(home.id)
                app.render()
                app.present()
                version = 'v' + __version__.replace('.', '')
                pg.image.save(app.window, str(output / f'{version}_{biome.lower()}_planet.png'))
        finally:
            app.audio.close()
            pg.quit()
    print(f'Rendered {len(BIOMES)} planet overviews.')


if __name__ == '__main__':
    main()
