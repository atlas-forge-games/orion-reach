"""Capture the research overview, project switching, information and galaxy access."""

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


def main():
    output = ROOT/"screenshots"
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        app = App(Path(folder), capture=True)
        def capture(name):
            app.notice = ""
            app.render()
            pg.image.save(app.canvas, str(output/f"{name}.png"))
        try:
            app.game = new_game(seed=2408, with_tombs=False, with_guardians=False)
            app.game.headquarters()[1].scientists = 2
            app.go("galaxy")
            capture("research_top_bar")
            app.advance_turn()
            capture("research_fields")
            for identifier, budget in (("destroyer_hulls", 40), ("cruiser_hulls", 100)):
                app.game.research = budget
                app.game.choose_research(identifier)
            app.game.research = 24
            app.research_request("battleship_hulls")
            app.show_technology_info("drone_carriers")
            capture("research_technology_info")
            app.cancel_dialog()
            app.research_request("drone_carriers")
            capture("research_fields_active")
            app.show_research_technology("drone_carriers")
            capture("research_field_tiers")
        finally:
            app.audio.close()
            pg.quit()
    print(output)


if __name__ == "__main__":
    main()
