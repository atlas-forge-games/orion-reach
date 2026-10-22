"""Capture the complete nine-cell landing preview of a one-step titan move."""

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
from orion import combat_camera as camera
from orion.combat_sandbox import FleetSetup, Scenario
from orion.combat_simulator import CombatSimulator


def main():
    scenario = Scenario(name='Full movement footprints',
                        player=FleetSetup(ships={'titan': 1}),
                        rival=FleetSetup(ships={'battleship': 1}))
    with tempfile.TemporaryDirectory() as folder:
        app = CombatSimulator(Path(folder), scenario=scenario, capture=True)
        try:
            app.launch(False)
            ship = next(s for s in app.game.combat.ships if s.owner == 'player')
            ship.x, ship.y = 5, 5
            app.combat_ship_id = ship.id
            app.combat_zoom = 1.5
            camera.reveal(app, ((4, 4), (8, 8)))
            app.mouse = camera.view(app).project((8, 6))
            before = app.game.to_dict()
            app.render()
            output = ROOT / 'screenshots' / 'v0751_combat_movement.png'
            output.parent.mkdir(exist_ok=True)
            pg.image.save(app.canvas, output)
            assert app.game.to_dict() == before
            print(output)
        finally:
            app.audio.close()
            pg.quit()


if __name__ == '__main__':
    main()
