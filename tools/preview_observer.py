"""Capture real Observer setup, galaxy, reports and news screens."""

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


def main():
    output = ROOT/"screenshots"
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        app = App(Path(folder), capture=True)
        try:
            app.choose_race("observer")
            app.seed, app.rival_count = "2408", 5
            for screen in ("race_select", "setup"):
                app.go(screen)
                app.render()
                pg.image.save(app.canvas, str(output/f"observer_{screen}.png"))
            app.start_game()
            for _ in range(20):
                if app.game.result:
                    break
                app.advance_turn()
            app.notice = ""
            app.render()
            pg.image.save(app.canvas, str(output/"observer_galaxy.png"))
            app.open_empire()
            app.render()
            pg.image.save(app.canvas, str(output/"observer_empires.png"))
            app.open_news()
            app.render()
            pg.image.save(app.canvas, str(output/"observer_news.png"))
        finally:
            app.audio.close()
            pg.quit()
    print(output)


if __name__ == "__main__":
    main()
