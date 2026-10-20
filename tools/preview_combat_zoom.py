"""Render the shared tactical camera at overview and close-up magnifications."""

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
from orion.combat_sandbox import preset
from orion.combat_simulator import CombatSimulator


def main():
    with tempfile.TemporaryDirectory() as folder:
        app = CombatSimulator(Path(folder), scenario=preset(6), capture=True)
        try:
            app.launch(True)
            for _ in range(1500):
                app.time += 2
                app.update_combat()
                if app.combat_animation is None and any(p.age for p in app.game.combat.projectiles):
                    break
            else:
                raise AssertionError('No in-flight volley to preview')
            app.combat_auto = False
            battle = app.game.combat
            app.combat_ship_id = next(s.id for s in battle.fleet('player') if s.kind == 'titan')
            shot = next(p for p in battle.projectiles if p.age)
            app.combat_target_id = shot.source_id if shot.owner == 'rival' else shot.target_id
            before = app.game.to_dict()
            for zoom, name in ((.5, 'combat_zoom_overview'), (1.5, 'combat_zoom_detail'), (3, 'combat_zoom_closeup')):
                app.combat_zoom = zoom
                camera.clamp(app)
                points = (battle.ship(app.combat_ship_id).position, battle.ship(app.combat_target_id).position)
                camera.reveal(app, points if zoom < 3 else points[:1])
                app.render()
                pg.image.save(app.canvas, ROOT/'screenshots'/f'{name}.png')
                assert app.game.to_dict() == before
        finally:
            app.audio.close()
            pg.quit()
    print('Captured 50%, 150% and 300% combat views without changing battle state.')


if __name__ == '__main__':
    main()
