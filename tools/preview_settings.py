"""Render the real settings overview and every category without changing user data."""

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
    with tempfile.TemporaryDirectory() as directory:
        app = App(Path(directory), capture=True)
        try:
            app.show_settings()
            for section in (None, "graphics", "sound", "gameplay", "interface"):
                if section:
                    app.select_settings_section(section)
                app.render()
                pg.image.save(app.canvas, str(ROOT/"screenshots"/f"v0721_settings_{section or 'overview'}.png"))
        finally:
            app.audio.close()
            pg.quit()


if __name__ == "__main__":
    main()
