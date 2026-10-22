"""Capture the real simulator with large hulls and an obstructed beam shot."""

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
from orion.combat_sandbox import FleetSetup, Scenario
from orion.combat_simulator import CombatSimulator
from orion import combat_geometry as geometry


def main():
    scenario = Scenario(name="Firing lanes", player=FleetSetup(ships={"titan": 1, "cruiser": 1, "frigate": 1}),
                        rival=FleetSetup(ships={"battleship": 1, "destroyer": 1, "frigate": 1}))
    with tempfile.TemporaryDirectory() as folder:
        app = CombatSimulator(Path(folder), scenario=scenario, capture=True)
        try:
            app.launch(False)
            battle = app.game.combat
            locations = {("player", "titan"): (2, 5), ("player", "cruiser"): (6, 5),
                         ("player", "frigate"): (6, 2), ("rival", "battleship"): (11, 5),
                         ("rival", "destroyer"): (13, 9), ("rival", "frigate"): (14, 2)}
            for ship in battle.ships:
                ship.x, ship.y = locations[(ship.owner, ship.kind)]
            app.combat_ship_id = next(s.id for s in battle.ships if s.kind == "titan")
            app.combat_target_id = next(s.id for s in battle.ships if s.kind == "battleship")
            cells = [c for s in battle.ships for c in geometry.cells(s)]
            assert len(cells) == len(set(cells))
            before = app.game.to_dict()
            app.render()
            target = ROOT / "screenshots" / "v075_combat_geometry.png"
            target.parent.mkdir(exist_ok=True)
            pg.image.save(app.canvas, target)
            assert app.game.to_dict() == before
            print(target)
        finally:
            app.audio.close()
            pg.quit()


if __name__ == "__main__":
    main()
