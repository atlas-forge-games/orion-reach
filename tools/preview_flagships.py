"""Capture the shared flagship aura and simulator inspection using real game UI."""

import os
from pathlib import Path
import sys
import tempfile

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pygame as pg
from orion import flagships
from orion.combat_sandbox import FleetSetup, Scenario
from orion.combat_simulator import CombatSimulator


def main():
    scenario = Scenario(name='Flagship command',
                        player=FleetSetup(ships={'frigate': 5, 'destroyer': 2, 'titan': 1}),
                        rival=FleetSetup(ships={'frigate': 6, 'destroyer': 1}))
    with tempfile.TemporaryDirectory() as folder:
        app = CombatSimulator(Path(folder), scenario=scenario, capture=True)
        try:
            app.launch(False)
            battle = app.game.combat
            leader = flagships.select(battle, 'player')
            app.combat_ship_id = leader.id
            app.combat_target_id = flagships.select(battle, 'rival').id
            before = app.game.to_dict()
            app.render()
            pg.image.save(app.canvas, ROOT/'screenshots'/'v074_flagships.png')
            app.inspect_ship(leader.id)
            app.render()
            pg.image.save(app.canvas, ROOT/'screenshots'/'v074_flagship_inspector.png')
            assert app.game.to_dict() == before
        finally:
            app.audio.close()
            pg.quit()
    print('Captured titan/destroyer flagship radii and inspection without changing combat.')


if __name__ == '__main__':
    main()
