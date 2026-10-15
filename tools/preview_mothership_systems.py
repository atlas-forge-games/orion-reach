"""Render real system controls, ownership colors and 25 LY convoy selection."""
import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pygame as pg
from orion.app import App
from orion.model import new_game
from orion.motherships import homes

with tempfile.TemporaryDirectory() as folder:
    app = App(Path(folder), capture=True)
    try:
        app.game = game = new_game('Wanderer Flotillas', seed=12, race_id='wanderers',
                                  with_ai=False, random_starts=False, with_guardians=False,
                                  with_tombs=False, with_black_holes=False)
        home = homes(game)[0]
        home.habitat.trade_goods = True
        def capture(name):
            app.dialog = None
            app.notice = ''
            app.render()
            pg.image.save(app.canvas, str(ROOT/'screenshots'/('v0641_'+name+'.png')))
        app.open_system(home.system_id)
        capture('mothership_system')
        app.go('galaxy')
        capture('mothership_galaxy')
        origin, dest = game.systems[0], game.systems[1]
        dest.x, dest.y = origin.x+20/140, origin.y
        app.open_map_fleet(home.id)
        game.selected_system = dest.id
        app.mouse = (-1, -1)
        capture('mothership_range')
    finally:
        app.audio.close()
        pg.quit()
