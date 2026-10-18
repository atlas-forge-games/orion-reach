"""Render the actual setup, research, objectives and result screens."""
import os
from pathlib import Path
import sys
import tempfile
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'tests')]
import pygame as pg
from orion.app import App
from orion.races import RACES
from test_civilization_legacies import prepared, tick


def main():
    with tempfile.TemporaryDirectory() as directory:
        app = App(Path(directory), capture=True)
        try:
            def capture(name):
                app.render()
                pg.image.save(app.canvas, ROOT/'screenshots'/f'v072_{name}.png')
            app.go('setup'); capture('setup')
            for rid in ('serevan', 'skirr'):
                app.game = prepared(rid)
                app.game.empire_name = RACES[rid].default_empire
                app.go('objectives'); app.objectives_tab = 'race'
                capture('union_objectives' if rid == 'serevan' else 'skirr_objectives')
            app.go('research'); app.research_overview = True; capture('research')
            app.game = prepared('kharuun')
            app.game.empire_name = RACES['kharuun'].default_empire
            for _ in range(5): tick(app.game)
            app.go('result'); capture('kharuun_victory')
        finally:
            app.audio.close()
            pg.quit()


if __name__ == '__main__':
    main()
