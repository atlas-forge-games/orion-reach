"""Render the native Skirr home, race selection and a prospective Toxic colony."""
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
from orion.exploration import refresh
from orion.model import new_game


def main():
    output = ROOT / 'screenshots'
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        app = App(Path(directory), capture=True)
        try:
            app.window = pg.display.set_mode((1440, 900), pg.RESIZABLE)
            app.race_id = 'skirr'
            app.go('race_select')
            app.render()
            pg.image.save(app.canvas, str(output / 'v078_skirr_selection.png'))
            app.go('setup')
            app.render()
            pg.image.save(app.canvas, str(output / 'v078_skirr_setup.png'))
            app.game = new_game(seed=2408, race_id='skirr', with_ai=False,
                                fog_of_war=False, random_starts=False,
                                with_tombs=False, with_guardians=False,
                                with_black_holes=False, with_encounters=False)
            app.open_planet(2)
            app.render()
            pg.image.save(app.canvas, str(output / 'v078_skirr_home.png'))
            home = app.game.headquarters()[1]
            home.buildings = ['hydroponic_farm', 'fusion_plant', 'solar_array']
            refresh(app.game)
            app.render()
            pg.image.save(app.canvas, str(output / 'v078_toxic_colony.png'))
            app.go('colony')
            app.render()
            pg.image.save(app.canvas, str(output / 'v078_toxic_management.png'))
            app.game = new_game(seed=2408, with_ai=False, fog_of_war=False,
                                random_starts=False, with_tombs=False,
                                with_guardians=False, with_black_holes=False)
            app.game.planet_at(0, 3).biome = 'Toxic'
            refresh(app.game)
            app.open_planet(3)
            app.render()
            pg.image.save(app.canvas, str(output / 'v078_toxic_survey.png'))
        finally:
            app.audio.close()
            pg.quit()
    print('Rendered environmental preference screens.')


if __name__ == '__main__':
    main()
