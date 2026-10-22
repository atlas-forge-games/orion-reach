"""Capture native ship detail and real torpedo / missile positions at high zoom."""

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
from orion.designs import ShipDesign


def main():
    scenario = Scenario(name='Ship detail and ordnance', accuracy=False,
                        player=FleetSetup(ships={'design_1': 1}, bases=1),
                        rival=FleetSetup(ships={'battleship': 1}),
                        designs=[ShipDesign('design_1', 'Torpedo titan', 'titan', ('torpedo',))])
    with tempfile.TemporaryDirectory() as folder:
        app = CombatSimulator(Path(folder), scenario=scenario, capture=True)
        try:
            app.launch(False)
            battle = app.game.combat
            titan = next(s for s in battle.ships if s.kind == 'titan')
            battery = next(s for s in battle.ships if s.kind == 'missile_base')
            target = next(s for s in battle.ships if s.kind == 'battleship')
            titan.x, titan.y = 2, 4
            battery.x, battery.y = 3, 8
            target.x, target.y = 10, 4
            app.combat_ship_id, app.combat_target_id = titan.id, target.id
            app.game.combat_fire(titan.id, target.id)
            app.game.combat_fire(battery.id, target.id)
            app.game.combat_end_turn()
            flights = app.game.combat_end_turn('rival')
            app.after_combat_action({'kind': 'end_turn', 'flights': flights})
            app.combat_animation.elapsed = .2
            app.mouse = (-1, -1)
            before = app.game.to_dict()
            for zoom, filename in ((2.0, 'v0752_ordnance.png'), (3.0, 'v0752_combat_detail.png')):
                app.combat_zoom = zoom
                app.combat_camera_col, app.combat_camera_row = 1, 3
                camera.clamp(app)
                app.render()
                output = ROOT / 'screenshots' / filename
                pg.image.save(app.canvas, output)
                print(output)
            assert app.game.to_dict() == before
        finally:
            app.audio.close()
            pg.quit()


if __name__ == '__main__':
    main()
