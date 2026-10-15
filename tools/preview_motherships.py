"""Render the integrated Wanderer home and galaxy controls headlessly."""
import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
from pathlib import Path
import sys,tempfile
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pygame as pg
from orion.app import App
from orion.model import new_game
from orion.motherships import homes

with tempfile.TemporaryDirectory() as folder:
    app=App(Path(folder),capture=True)
    try:
        app.game=game=new_game('Wanderer Flotillas',seed=12,race_id='wanderers',with_ai=False,random_starts=False,
                              with_guardians=False,with_tombs=False,with_black_holes=False)
        ship=homes(game)[0]
        ship.habitat.population=24
        ship.habitat.farmers=6
        ship.habitat.scientists=4
        ship.habitat.miners=4
        ship.habitat.buildings=['hydroponic_farm','factory','research_lab','mine','solar_array','space_hub']
        ship.habitat.trade_goods=True
        def capture(name):
            app.notice=''
            app.dialog=None
            app.render()
            pg.image.save(app.canvas, str(ROOT/'screenshots'/('v064_'+name+'.png')))
        app.go('galaxy')
        app.open_map_fleet(ship.id)
        capture('mothership_galaxy')
        app.open_mothership(ship.id)
        capture('mothership_home')
        app.go('production')
        capture('mothership_production')
        app.go('galaxy')
        target=min((s for s in game.systems if s.id != ship.system_id),key=lambda s:game.supply_distance(s.id))
        game.send_ships([s.id for s in game.ships],target.id)
        for _ in range(5):
            game.advance_turn()
        app.open_map_fleet(ship.id)
        capture('mothership_transit')
        app.open_mothership(ship.id)
        capture('mothership_inflight_home')
    finally:
        app.audio.close()
        pg.quit()
