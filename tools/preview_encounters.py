"""Render the actual setup, discovery, guard and pirate combat screens."""
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
from orion import encounters, exploration, combat
from orion.model import new_game, Ship

with tempfile.TemporaryDirectory() as folder:
    app = App(Path(folder), capture=True)
    try:
        def capture(name):
            app.dialog, app.notice, app.mouse = None, '', (-1, -1)
            app.render()
            pg.image.save(app.canvas, str(ROOT/'screenshots'/('v068_'+name+'.png')))
        app.go('setup')
        capture('encounter_setup')
        game = app.game = new_game(seed=12, with_ai=False, random_starts=False,
                                  with_guardians=False, with_tombs=False, with_black_holes=False, with_encounters=True)
        guard = game.encounters.fleets[0]
        sid = guard.system_id
        for s in game.ships:
            s.system_id = sid
        for _ in range(3):
            game.ships.append(Ship(game.next_ship_id, 'frigate', sid))
            game.next_ship_id += 1
        exploration.refresh(game)
        app.go('galaxy')
        app.select_star(sid)
        app.ensure_map_system(sid)
        capture('pirate_galaxy')
        app.open_system(sid)
        capture('guarded_system')
        app.open_planet(guard.planet_id)
        capture('guarded_planet')
        app.open_encounters(sid)
        capture('planet_guards')
        encounters.start_search(game, sid)
        game.advance_turn()
        capture('scout_search')
        game.advance_turn()
        encounters.create(game, sid, 'raid', target_owner='player')
        capture('raid_warning')
        combat.begin_pirate_combat(game, guard.id)
        app.reset_combat_view()
        app.go('combat')
        capture('pirate_combat')
    finally:
        app.audio.close()
        pg.quit()
