"""Launch the prototype. Run `python main.py --help` for capture options."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Orion Reach — Python space strategy prototype")
    parser.add_argument("--data-dir", type=Path, help="override the user save/settings directory")
    parser.add_argument("--headless", action="store_true", help="use SDL's dummy video/audio drivers")
    parser.add_argument("--skip-intro", action="store_true", help="go straight to the menu without the studio splash")
    parser.add_argument("--screenshot", type=Path, help="render one screen to PNG, then exit")
    parser.add_argument("--screen", choices=("splash", "menu", "setup", "load", "settings", "galaxy", "system", "planet", "colony", "empire", "shipyard", "fleets", "rival", "diplomacy", "research", "combat", "objectives", "result", "about"), default="menu")
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
    app = App(args.data_dir, capture=bool(args.screenshot), skip_intro=args.skip_intro)
    try:
        if args.screenshot:
            if args.screen in ("galaxy", "system", "planet", "colony", "empire", "shipyard", "fleets", "rival", "diplomacy", "research", "combat", "objectives", "result"):
                from orion.model import new_game
                app.game = new_game(seed=2408)
                if args.screen in ("planet", "colony", "shipyard"):
                    app.game.selected_planet = 2
                if args.screen == "combat":
                    from orion.model import RIVAL, Ship
                    # A local screenshot fixture; ordinary campaigns start without fleets.
                    app.game.ships = [Ship(1, "frigate", 0), Ship(2, "frigate", 0), Ship(3, "colony_ship", 0),
                                      Ship(4, "frigate", 0, owner=RIVAL), Ship(5, "frigate", 0, owner=RIVAL),
                                      Ship(6, "colony_ship", 0, owner=RIVAL)]
                    app.game.next_ship_id = 7
                    app.game.start_combat(0)
                    app.game.combat_fire(1, 4)
                    app.game.combat_ai_action()
                if args.screen == "result":
                    from orion.research import BRANCHES, choices
                    # Preview a science result without altering a real campaign.
                    game = app.game
                    game.research = 1620
                    for branch in BRANCHES:
                        for tier in (1, 2):
                            game.choose_research(choices(branch, tier)[0].id)
                    game.choose_research("ascension_theory")
                    earth = game.planet_at(0, 2)
                    earth.ascension_gate, earth.gate_charge = True, 5
                    game.check_victory()
            app.go(args.screen)
            app.time = 1.0 if args.screen == "splash" else 3.0
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
