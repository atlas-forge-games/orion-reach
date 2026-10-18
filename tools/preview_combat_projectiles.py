"""Capture the real deployment, in-flight ordnance and simulator inspector."""

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
from orion.combat_sandbox import preset
from orion.combat_simulator import CombatSimulator


def main():
    with tempfile.TemporaryDirectory() as folder:
        app = CombatSimulator(Path(folder), scenario=preset(6), capture=True)
        try:
            app.launch(False)
            def capture(name):
                app.render()
                pg.image.save(app.canvas, ROOT/'screenshots'/f'{name}.png')
            capture('combat_wide_deployment')
            app.toggle_combat_auto()
            for _ in range(1500):
                app.time += 2
                app.update_combat()
                battle = app.game.combat
                if app.combat_animation is None and any(p.age for p in battle.projectiles):
                    shot = next(p for p in battle.projectiles if p.age)
                    app.combat_ship_id = shot.source_id if shot.owner == 'player' else shot.target_id
                    app.combat_target_id = shot.target_id if shot.owner == 'player' else shot.source_id
                    capture('combat_torpedoes')
                    app.inspect_ship(shot.source_id)
                    capture('combat_ship_inspector')
                    app.inspect_tab('ordnance')
                    capture('combat_ordnance_inspector')
                    break
            else:
                raise AssertionError('No visible in-flight volley')
        finally:
            app.audio.close()
            pg.quit()
    print('Captured deployment, torpedo flight and both inspection tabs.')


if __name__ == '__main__':
    main()
