"""Capture the specialist screens with the live controls and a reproducible game."""
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
from orion import specialists as rules
from orion.balance_editor import BalanceEditor


def main():
    output = ROOT/"screenshots"
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        app = App(Path(folder), capture=True)
        try:
            game = app.game = new_game(seed=12, with_ai=False, with_guardians=False,
                                       with_tombs=False, with_black_holes=False, random_starts=False)
            game.credits = game.resources = 1000

            def capture(name):
                app.notice = ""
                app.render()
                pg.image.save(app.canvas, str(output/("specialists_"+name+".png")))

            app.open_planet(2)
            app.open_specialists()
            capture("getting_started")
            game.queue_building(0, 2, "space_hub")
            game.buy_construction(0, 2)
            game.advance_turn()
            app.open_specialists()
            capture("visitors")
            leader = next(p for p in rules.visitors(game) if p.spec.role == "leader")
            explorer = next(p for p in rules.visitors(game) if p.spec.role == "explorer")
            app.specialist_action("hire", leader.id)
            app.specialist_action("assign", leader.id, 0, 2)
            app.specialist_action("hire", explorer.id)
            app.specialist_action("assign", explorer.id, 0, None)
            for _ in range(5): game.advance_turn()
            app.specialist_select(leader.id)
            capture("leader")
            app.specialist_select(explorer.id)
            capture("explorer")
            app.specialist_set_tab("sites")
            capture("discovery")
            app.go("planet")
            capture("planet")
            app.open_empire()
            capture("empire")
        finally:
            app.audio.close()
            pg.quit()
        editor = BalanceEditor(Path(folder)/"preview-balance.json")
        editor.select_section("specialists")
        editor.draw()
        pg.image.save(editor.canvas, str(output/"specialists_editor.png"))
        pg.quit()
    print(output)


if __name__ == "__main__":
    main()
