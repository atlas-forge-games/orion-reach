"""Launch the prototype. Run `python main.py --help` for capture options."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Orion Reach — Python space strategy prototype")
    parser.add_argument("--data-dir", type=Path, help="override the user save/settings directory")
    parser.add_argument("--headless", action="store_true", help="use SDL's dummy video/audio drivers")
    parser.add_argument("--screenshot", type=Path, help="render one screen to PNG, then exit")
    parser.add_argument("--screen", choices=("menu", "setup", "load", "settings", "galaxy", "system", "planet", "colony", "empire", "shipyard", "fleets", "rival", "diplomacy", "research", "about"), default="menu")
    args = parser.parse_args()
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    if args.headless:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"
    try:
        import pygame
    except ImportError:
        raise SystemExit("Install the dependency first: python -m pip install -r requirements.txt")
    from orion.app import App
    app = App(args.data_dir, capture=bool(args.screenshot))
    try:
        if args.screenshot:
            if args.screen in ("galaxy", "system", "planet", "colony", "empire", "shipyard", "fleets", "rival", "diplomacy", "research"):
                from orion.model import new_game
                app.game = new_game(seed=2408)
                if args.screen in ("planet", "colony", "shipyard"):
                    app.game.selected_planet = 2
            app.go(args.screen)
            app.time = 3.0
            app.render()
            args.screenshot.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(app.canvas, args.screenshot)
            print(f"Screenshot: {args.screenshot}")
        else:
            app.run()
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
