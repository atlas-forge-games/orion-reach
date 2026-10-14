"""Render reproducible megastructure screens without touching campaign saves."""
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
from orion.app import App
from orion.model import new_game
from orion import megastructures as mega
from orion.research import choices


def main():
    output = ROOT/"screenshots"
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        app = App(Path(folder), capture=True)
        try:
            game = app.game = new_game(seed=12, random_starts=False, with_ai=False,
                with_guardians=False, with_tombs=False, with_black_holes=False, fog_of_war=False)
            game.resources, game.credits = 25000, 8000
            game.turn, game.year = 120, 2419
            game.ships.clear()
            for spec in mega.MEGASTRUCTURES.values():
                for tier in range(1, spec.tier+1):
                    if tier not in game.technology.completed_tiers(spec.branch):
                        game.technology.completed.append(choices(spec.branch, tier)[0].id)
            game.selected_system = 0

            def capture(name, screen):
                app.go(screen)
                app.notice = ""
                app.render()
                pg.image.save(app.canvas, str(output/f"v060_{name}.png"))

            capture("catalog", "megastructure")
            for kind in mega.MEGASTRUCTURES:
                game.systems[0].megastructure = None
                mega.start(game, 0, kind)
                m = game.systems[0].megastructure
                m.stage = 4 if kind == "dyson_sphere" else 3
                m.hull = m.max_hull
                m.progress = 0 if m.stage == 4 else m.stage_work//3
                capture(kind, "megastructure")
                if kind == "dyson_sphere":
                    capture("system", "system")
                    game.selected_planet = 2
                    capture("dyson_energy", "planet")
        finally:
            app.audio.close()
            pg.quit()
    print(output)


if __name__ == "__main__":
    main()
