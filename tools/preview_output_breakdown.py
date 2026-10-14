"""Render all production explanations and the outpost sprite at game scale."""
import os
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
from pathlib import Path
import sys,tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pygame as pg
from orion.app import App
from orion.model import new_game
from orion.fleet_art import ship_icon
from orion.production_breakdown import KINDS
with tempfile.TemporaryDirectory() as folder:
    app=App(Path(folder),capture=True)
    try:
        app.game=new_game(seed=12,random_starts=False,with_ai=False,with_guardians=False,with_tombs=False,with_black_holes=False)
        p=app.game.planet_at(0,2)
        p.buildings=['factory','research_lab','mine','space_hub']
        p.farmers,p.scientists,p.miners=2,1,1
        app.open_planet(2)
        for kind in KINDS:
            app.show_output_breakdown(kind)
            app.render()
            pg.image.save(app.canvas,str(ROOT/'screenshots'/('v0602_'+kind+'.png')))
            app.cancel_dialog()
        canvas=pg.Surface((600,520));canvas.fill((8,18,27))
        ship_icon(canvas,(220,260),scale=5,kind='outpost_ship')
        ship_icon(canvas,(490,260),scale=1,kind='outpost_ship')
        pg.image.save(canvas,str(ROOT/'screenshots/v0602_outpost_ship.png'))
    finally:
        app.audio.close();pg.quit()
