"""Capture the v0.56 tree and advanced facility screens using live game widgets."""
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
from orion.buildings import ADVANCED_FACILITIES, BUILDINGS
from orion.model import new_game
from orion.research import TECHNOLOGIES, choices


def main():
    output = ROOT/'screenshots'
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        app = App(Path(folder), capture=True)
        try:
            app.game = new_game(seed=2408, with_ai=False, with_guardians=False,
                                with_tombs=False, with_black_holes=False, random_starts=False)
            game = app.game

            def capture(name):
                app.notice = ''
                app.render()
                pg.image.save(app.canvas, str(output/(name+'.png')))

            game.research = TECHNOLOGIES['research_instruments'].cost
            game.choose_research('research_instruments')
            app.go('research')
            app.show_research_technology('pulse_beams')
            capture('research_progression_beams')
            app.show_research_technology('deep_core_drills')
            capture('research_progression_mining')

            picks = {(TECHNOLOGIES[BUILDINGS[b].technology].branch,
                      TECHNOLOGIES[BUILDINGS[b].technology].tier): BUILDINGS[b].technology
                     for b in ADVANCED_FACILITIES}
            for branch in dict.fromkeys(b for b, _ in picks):
                for tier in range(1, max(t for b, t in picks if b == branch)+1):
                    if tier in game.technology.completed_tiers(branch):
                        continue
                    identifier = picks.get((branch, tier), choices(branch, tier)[0].id)
                    game.research = TECHNOLOGIES[identifier].cost
                    game.choose_research(identifier)
            game.resources = game.credits = 10000
            app.open_planet(2)
            app.go('colony')
            app.colony_build_page = 3
            capture('advanced_facilities_catalogue')
            for identifier in ('advanced_research_lab', 'robotic_factory', 'deep_core_mine', 'solar_array'):
                game.queue_building(0, 2, identifier)
                game.buy_construction(0, 2)
            app.go('planet')
            capture('advanced_facilities_surface')
        finally:
            app.audio.close()
            pg.quit()
    print(output)


if __name__ == '__main__':
    main()
