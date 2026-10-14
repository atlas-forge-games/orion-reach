"""Render the live diplomacy dialogs using a deterministic small campaign."""
import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
from pathlib import Path
import sys
import tempfile
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pygame as pg
from orion.app import App
from orion.model import new_game, Ship
from orion import coalitions, tribute

with tempfile.TemporaryDirectory() as folder:
    app = App(Path(folder), capture=True)
    try:
        app.game = game = new_game(seed=12, race_id='varkesh', rival_race_id='lithar', rival_count=5,
                                  random_starts=False, fog_of_war=False, with_guardians=False,
                                  with_tombs=False, with_black_holes=False)
        game.ships.clear()
        for i, owner in enumerate(game.owners):
            system, _ = game.headquarters(owner)
            system.x, system.y = .2+i*.025, .5
        game.diplomacy.relations = 40
        for _ in range(24):
            game.ships.append(Ship(game.next_ship_id, 'frigate', game.opponent.home_system))
            game.next_ship_id += 1
        app.go('galaxy')
        app.open_diplomacy()
        def capture(name):
            app.notice = ''
            app.render()
            pg.image.save(app.canvas, ROOT/'screenshots'/('v063_'+name+'.png'))
        capture('diplomacy')
        for tab in ('coalitions', 'tribute', 'priorities'):
            app.show_diplomatic_affairs(tab, 'rival')
            capture(tab)
            app.cancel_dialog()
        coalitions.form(game, 'player', 'rival', 'rival_2')
        app.show_diplomatic_affairs('coalitions', 'rival')
        capture('active_coalition')
        app.cancel_dialog()
        tribute.demand(game, 'rival', 'player')
        app.show_diplomatic_affairs('tribute', 'rival')
        capture('incoming_demand')
    finally:
        app.audio.close()
        pg.quit()
