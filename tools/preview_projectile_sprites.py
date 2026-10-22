"""Capture the imported projectile artwork and a real simulator flight."""

import os
from pathlib import Path
import sys
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pygame as pg
from orion import combat_camera as camera, projectile_art
from orion.combat_sandbox import FleetSetup, Scenario
from orion.combat_simulator import CombatSimulator
from orion.designs import ShipDesign
from orion.ui import text


def main():
    pg.init()
    sheet = pg.Surface((1500, 1010))
    sheet.fill((8, 19, 34))
    text(sheet, "TORPEDOES & MISSILES", (48, 35), 34)
    text(sheet, "Imported artwork · combat renderer preview", (50, 90), 19, (155, 177, 198))
    labels = ("Standard torpedo", "Fusion torpedo", "MIRV torpedo", "Antimatter torpedo",
              "Bomber-drone torpedo", "Defense missile")
    for index, (key, label) in enumerate(zip(projectile_art.PROJECTILE_ART, labels)):
        x, y = 48 + index % 2*720, 147 + index//2*275
        pg.draw.rect(sheet, (16, 31, 50), (x, y, 684, 250), border_radius=12)
        pg.draw.rect(sheet, (39, 61, 85), (x, y, 684, 250), 1, border_radius=12)
        text(sheet, label, (x+22, y+16), 23)
        # Use the same cached artwork and body anchor as live combat.
        zoom = 370/(14 if key in ("missile", "bomber_torpedo") else 18)
        projectile_art.draw(sheet, (x+386, y+124), (1, 0), key, zoom=zoom)
        text(sheet, "300% zoom", (x+22, y+210), 15, (148, 169, 191))
        for dx, direction in ((230, (1, 0)), (370, (1, -1)), (510, (-1, 0))):
            projectile_art.draw(sheet, (x+dx, y+215), direction, key, zoom=3)
    output = ROOT / "screenshots" / "v0753_projectile_art.png"
    pg.image.save(sheet, output)
    print(output)

    scenario = Scenario(name="Imported projectile artwork", accuracy=False,
                        player=FleetSetup(ships={"design_1": 1}, bases=1),
                        rival=FleetSetup(ships={"battleship": 1}),
                        designs=[ShipDesign("design_1", "Torpedo titan", "titan", ("torpedo",))])
    with tempfile.TemporaryDirectory() as folder:
        app = CombatSimulator(Path(folder), scenario=scenario, capture=True)
        try:
            app.launch(False)
            battle = app.game.combat
            titan = next(s for s in battle.ships if s.kind == "titan")
            battery = next(s for s in battle.ships if s.kind == "missile_base")
            target = next(s for s in battle.ships if s.kind == "battleship")
            titan.x, titan.y = 2, 4
            battery.x, battery.y = 3, 8
            target.x, target.y = 10, 4
            app.combat_ship_id, app.combat_target_id = titan.id, target.id
            app.game.combat_fire(titan.id, target.id)
            app.game.combat_fire(battery.id, target.id)
            app.game.combat_end_turn()
            flights = app.game.combat_end_turn("rival")
            app.after_combat_action({"kind": "end_turn", "flights": flights})
            app.combat_animation.elapsed = .2
            app.mouse = (-1, -1)
            app.combat_zoom = 2.0
            app.combat_camera_col, app.combat_camera_row = 1, 3
            camera.clamp(app)
            before = app.game.to_dict()
            app.render()
            assert app.game.to_dict() == before
            output = ROOT / "screenshots" / "v0753_combat_sprites.png"
            pg.image.save(app.canvas, output)
            print(output)
        finally:
            app.audio.close()
            pg.quit()


if __name__ == "__main__":
    main()
