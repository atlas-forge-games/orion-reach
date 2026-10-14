"""Preview the Space Hub, clean galaxy map and revised invasion report."""
import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
from pathlib import Path
import sys
import tempfile
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'tests'))
import pygame as pg
from orion.app import App
from orion.model import new_game
from test_ground_combat import scenario, fortified_target, add_transports

with tempfile.TemporaryDirectory() as folder:
    app = App(Path(folder), capture=True)
    try:
        app.game = new_game(seed=12, random_starts=False, with_ai=False,
                            with_guardians=False, with_tombs=False, with_black_holes=False)
        app.game.planet_at(0,2).buildings = ['factory', 'research_lab', 'mine', 'space_hub']
        def capture(name):
            app.notice = ''
            app.render()
            pg.image.save(app.canvas, str(ROOT/'screenshots'/('v0601_'+name+'.png')))
        app.go('galaxy')
        capture('galaxy')
        app.open_planet(2)
        capture('space_hub')
        app.game = game = scenario()
        sid,pid,planet = fortified_target(game)
        add_transports(game,sid,4)
        app.ground_reports = [game.invade(sid,pid)]
        app.ground_page = 0
        app.go('ground')
        capture('invasion')
    finally:
        app.audio.close()
        pg.quit()
