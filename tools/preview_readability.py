"""Render real screens at supported sizes without touching player data."""
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
    output = ROOT/'screenshots'
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        app = App(Path(directory), capture=True)
        try:
            app.game = new_game(seed=12, random_starts=False, with_ai=False,
                                with_guardians=False, with_black_holes=False,
                                with_tombs=False, with_encounters=False, fog_of_war=False)
            app.settings['animated_background'] = False
            app.settings['autosave'] = False
            app.game.credits = 439
            earth = app.game.planet_at(0, 2)
            earth.population = 12
            earth.buildings = ['factory', 'research_lab']
            earth.trade_goods = True
            for window, scale, name in (((1920, 1080), 100, 'empire_readable_v0850'),
                                         ((1280, 800), 100, 'empire_small_window_v0850'),
                                         ((1280, 800), 175, 'empire_large_text_v0850')):
                app.window = pg.display.set_mode(window, pg.RESIZABLE)
                app.settings['ui_scale'] = scale
                app.go('empire')
                app.render(); app.present()
                pg.image.save(app.window, str(output/(name+'.png')))
                if scale == 175:
                    app.display_view.scroll(0, 100000)
                    app.render(); app.present()
                    pg.image.save(app.window, str(output/'empire_large_text_bottom_v0850.png'))
            app.window = pg.display.set_mode((1440, 900), pg.RESIZABLE)
            app.settings['ui_scale'] = 100
            app.show_settings()
            app.select_settings_section('interface')
            app.render(); app.present()
            pg.image.save(app.window, str(output/'interface_size_v0850.png'))
            print('Rendered five readability captures.')
        finally:
            app.audio.close()
            pg.quit()


if __name__ == '__main__':
    main()
