"""Capture the live diplomacy portrait strip, friendship and war controls."""
import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
from pathlib import Path
import sys, tempfile
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pygame as pg
from orion.app import App
from orion.model import new_game

with tempfile.TemporaryDirectory() as folder:
    app = App(Path(folder), capture=True)
    try:
        game = app.game = new_game(seed=12, random_starts=False, rival_race_id='aelari', rival_count=5,
                                  with_guardians=False, with_tombs=False, with_black_holes=False, fog_of_war=False)
        app.go('galaxy')
        app.open_diplomacy()
        def capture(name):
            app.notice = ''
            app.render()
            pg.image.save(app.canvas, str(ROOT/'screenshots'/('v062_'+name+'.png')))
        capture('diplomacy')
        game.diplomacy.relations = 30
        game.diplomacy_action('friendship')
        capture('friendship')
        app.diplomatic_action('declare_war')
        capture('declare_war')
    finally:
        app.audio.close()
        pg.quit()
