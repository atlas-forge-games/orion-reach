"""Render the actual setup, selected objectives and three new fuel research tiers."""

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
from orion.research import TECHNOLOGIES, choices


def main():
    with tempfile.TemporaryDirectory() as directory:
        app = App(Path(directory), capture=True)
        try:
            def capture(name):
                app.notice = ""
                app.render()
                pg.image.save(app.canvas, str(ROOT/"screenshots"/name))

            app.rival_count = 5
            app.victory_conditions = ("conquest", "council")
            app.go("setup")
            capture("setup_victory_options.png")
            app.game = new_game(seed=2408, rival_count=5, fog_of_war=False, with_tombs=False, with_guardians=False,
                                victory_conditions=app.victory_conditions)
            app.go("objectives")
            capture("selected_victory_objectives.png")
            for tier in range(1, 8):
                if tier >= 5:
                    app.go("research")
                    app.select_research_branch("materials")
                    app.select_research_tier(tier)
                    capture(f"fuel_tanks_tier_{tier}.png")
                technology = choices("materials", tier)[0]
                app.game.research = TECHNOLOGIES[technology.id].cost
                app.game.choose_research(technology.id)
        finally:
            app.audio.close()
            pg.quit()
    print("Rendered setup, objectives and fuel research previews.")


if __name__ == "__main__":
    main()
