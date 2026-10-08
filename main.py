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
    parser.add_argument("--screen", choices=("splash", "menu", "setup", "load", "settings", "galaxy", "system", "unexplored", "exploration", "planet", "production", "colony", "empire", "shipyard", "fleets", "fleet", "fleet_course", "rival", "diplomacy", "research", "combat", "objectives", "result", "about"), default="menu")
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
            if args.screen in ("galaxy", "system", "unexplored", "exploration", "planet", "production", "colony", "empire", "shipyard", "fleets", "fleet", "fleet_course", "rival", "diplomacy", "research", "combat", "objectives", "result"):
                from orion.model import new_game
                app.game = new_game(seed=2408)
                if args.screen in ("planet", "production", "colony", "shipyard"):
                    app.game.selected_planet = 2
                if args.screen in ("galaxy", "fleet", "fleet_course"):
                    from orion.model import RIVAL, Ship
                    # Unsaved fleet fixtures for captures; ordinary starts are unchanged.
                    home = app.game.opponent.home_system
                    app.game.ships = [Ship(1, "frigate", 0, hull=16), Ship(2, "frigate", 0),
                                      Ship(3, "colony_ship", 0), Ship(4, "troop_transport", 0),
                                      Ship(5, "scout", 2), Ship(6, "frigate", home, owner=RIVAL),
                                      Ship(7, "colony_ship", home, owner=RIVAL), Ship(8, "scout", 0)]
                    app.game.next_ship_id = 9
                    app.game.send_ship(5, 3)
                if args.screen == "unexplored":
                    app.game.selected_system = 1
                if args.screen == "exploration":
                    from orion.model import Ship
                    from orion.exploration import DISCOVERIES, discovery_at, refresh
                    for index, kind in enumerate(DISCOVERIES, 1):
                        system = next(s for s in app.game.systems if discovery_at(app.game, s.id) == kind
                                      and s.id != app.game.opponent.home_system)
                        app.game.ships.append(Ship(index, "scout", system.id))
                    app.game.next_ship_id = len(app.game.ships)+1
                    refresh(app.game, recover=True)
                if args.screen == "combat":
                    from orion.model import RIVAL, Ship
                    # A local screenshot fixture; ordinary campaigns start without fleets.
                    app.game.ships = [Ship(1, "frigate", 0), Ship(2, "frigate", 0), Ship(3, "colony_ship", 0),
                                      Ship(4, "frigate", 0, owner=RIVAL), Ship(5, "frigate", 0, owner=RIVAL),
                                      Ship(6, "colony_ship", 0, owner=RIVAL)]
                    app.game.next_ship_id = 7
                    app.game.start_combat(0)
                    app.game.combat_move(1, 7, 4)
                    app.game.combat_fire(1, 4)
                    app.game.combat_move(2, 7, 5)
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
            app.go("galaxy" if args.screen == "fleet_course" else "system" if args.screen == "unexplored" else args.screen)
            if args.screen in ("fleet", "fleet_course"):
                app.open_map_fleet(1)
                app.toggle_fleet_ship(4)
                if args.screen == "fleet_course":
                    app.plot_fleet_course()
                    app.game.selected_system = 1
                    app.focus = "star_1"
                    app.keyboard_mode = True
            app.time = 1.0 if args.screen == "splash" else 3.0
            app.render()
            args.screenshot.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(app.canvas, args.screenshot)
            print(f"Screenshot: {args.screenshot}")
        else:
            app.run()
    finally:
        app.audio.close()
        pygame.quit()


if __name__ == "__main__":
    main()
