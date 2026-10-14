"""Capture the live diplomacy breakdown, racial matrix and balance controls."""
import os
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT','1')
from pathlib import Path
import sys,tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pygame as pg
from orion.app import App
from orion.model import new_game
from orion.balance_editor import BalanceEditor

with tempfile.TemporaryDirectory() as folder:
    app=App(Path(folder),capture=True)
    try:
        game=app.game=new_game(seed=12,random_starts=False,rival_race_id='varkesh',
                              with_guardians=False,with_tombs=False,with_black_holes=False,fog_of_war=False)
        app.go('galaxy')
        app.open_diplomacy()
        def capture(name):
            app.notice=''
            app.render()
            pg.image.save(app.canvas,str(ROOT/'screenshots'/('v061_'+name+'.png')))
        capture('diplomacy')
        app.show_alignment('rival')
        capture('values')
        app.dialog['alignment_matrix']=True
        capture('matrix')
        app.cancel_dialog()
        game.diplomacy.relations = 30
        game.diplomacy_action('friendship')
        app.show_alignment('rival')
        capture('history')
    finally:
        app.audio.close();pg.quit()
    editor=BalanceEditor(Path(folder)/'balance.json')
    editor.select_section('alignment')
    editor.draw()
    pg.image.save(editor.canvas,str(ROOT/'screenshots/v061_editor.png'))
    pg.quit()
