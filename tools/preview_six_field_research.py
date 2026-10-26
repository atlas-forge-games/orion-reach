"""Capture v0.83 research screens with the game's actual widgets and artwork."""
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
from orion import balance
from orion.app import App
from orion.model import new_game


def main():
    output = ROOT/'screenshots'
    output.mkdir(exist_ok=True)
    previous = balance.active_profile()
    balance.activate(balance.default_profile())
    with tempfile.TemporaryDirectory() as folder:
        app = App(Path(folder), capture=True)
        try:
            app.game = new_game(seed=2408, with_ai=False, with_guardians=False,
                                with_tombs=False, with_black_holes=False,
                                with_encounters=False, random_starts=False)
            planet = app.game.headquarters()[1]
            planet.buildings = ['solar_array', 'research_lab']
            planet.scientists = 2
            app.game.research = 21
            app.game.choose_research('automated_factories')

            def capture(name):
                app.notice = ''
                app.render()
                pg.image.save(app.canvas, str(output/(name+'.png')))

            app.go('galaxy')
            app.open_research()
            capture('research_six_fields')
            app.select_research_branch('construction')
            app.select_research_tier(1)
            capture('research_three_choices')
            app.show_technology_info('automated_factories')
            capture('research_building_unlock')
        finally:
            app.audio.close()
            pg.quit()
            balance.activate(previous)
    print(output)


if __name__ == '__main__':
    main()
