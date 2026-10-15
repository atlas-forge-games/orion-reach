"""Capture the real project, orbital portal and recovered route screens."""
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
from orion import hyperlanes, motherships
from orion.model import new_game

with tempfile.TemporaryDirectory() as folder:
    app = App(Path(folder), capture=True)
    try:
        app.game = game = new_game('Wanderer Flotillas', seed=12, race_id='wanderers',
                                  with_ai=False, random_starts=False, with_guardians=False,
                                  with_tombs=False, with_black_holes=False)
        home = motherships.homes(game)[0]
        home.habitat.trade_goods = True
        game.set_workforce(0, home.habitat.id, 2, 3, 1)

        def capture(name):
            app.dialog, app.notice, app.mouse = None, '', (-1, -1)
            app.render()
            pg.image.save(app.canvas, str(ROOT/'screenshots'/('v065_'+name+'.png')))

        app.open_hyperlane(0)
        capture('hyperlane_start')
        project = hyperlanes.start(game, 0)
        game.research = 153
        hyperlanes.invest(game, 0)
        capture('hyperlane_research')
        game.research = 147
        hyperlanes.invest(game, 0)
        capture('hyperlane_complete')
        app.open_system(0)
        capture('hyperlane_system')
        app.go('galaxy')
        capture('hyperlane_galaxy')
        app.open_map_fleet(home.id)
        game.selected_system = project.destination
        capture('hyperlane_course')
    finally:
        app.audio.close()
        pg.quit()
