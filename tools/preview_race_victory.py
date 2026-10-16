"""Render setup, known-empire objectives, finite research and the actual win UI."""
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
from orion import first_contact, hyperlanes, motherships
from orion.model import new_game


with tempfile.TemporaryDirectory() as folder:
    app = App(Path(folder), capture=True)
    try:
        def capture(name):
            app.dialog, app.notice, app.mouse = None, '', (-1, -1)
            app.render()
            pg.image.save(app.canvas, str(ROOT/'screenshots'/('v067_'+name+'.png')))

        app.go('setup')
        capture('victory_setup')
        app.game = game = new_game('Wanderer Flotillas', seed=12, race_id='wanderers',
                                  rival_race_id='wanderers', rival_count=5, random_starts=False,
                                  with_guardians=False, with_tombs=False, with_black_holes=False)
        for owner in game.opponents:
            first_contact.establish(game, 'player', owner, notify=False)
        for _ in range(3):
            hyperlanes.start(game, 0)
            game.research = 300
            hyperlanes.invest(game, 0)
        for lane in game.hidden_hyperlanes[:9]:
            game.hyperlane_projects.append(hyperlanes.HyperlaneProject(
                'rival', lane.first, lane.second, progress=300, completed_turn=game.turn))
        app.go('galaxy')
        app.open_objectives()
        capture('standard_objectives')
        app.objectives_tab = 'race'
        capture('race_objectives')
        app.open_hyperlane(0)
        capture('more_hyperlanes')
        home = motherships.homes(game, 'player')[0]
        empty = next(s.id for s in game.systems if not any(s.id in lane.pair for lane in game.hidden_hyperlanes))
        home.system_id = empty
        hyperlanes.survey_stationed(game, 'player')
        app.open_hyperlane(empty)
        capture('empty_system')
        home.system_id = 0
        discovered = {tuple(sorted((p.system_id, p.destination))) for p in game.hyperlane_projects if p.owner == 'player'}
        for lane in game.hidden_hyperlanes:
            if lane.pair not in discovered:
                game.hyperlane_projects.append(hyperlanes.HyperlaneProject(
                    'player', lane.first, lane.second, progress=300, completed_turn=game.turn))
        game.check_victory(convene=False)
        app.go('result')
        capture('wanderer_victory')
    finally:
        app.audio.close()
        pg.quit()
