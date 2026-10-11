"""Render real campaign screens for the black-hole expedition update."""

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
from orion.model import Ship, new_game
from orion.research import TECHNOLOGIES, choices
from orion import black_hole_view, combat


def discover(game, identifier):
    game.research += TECHNOLOGIES[identifier].cost
    game.choose_research(identifier)


def main():
    with tempfile.TemporaryDirectory() as directory:
        app = App(Path(directory), capture=True)
        try:
            app.window = pg.display.set_mode((1440, 900), pg.RESIZABLE)
            game = app.game = new_game(seed=42, fog_of_war=False, rival_count=3)
            for tier in range(1, 7):
                discover(game, choices("computers", tier)[0].id)
            game.choose_research("ion_drives")
            app.go("galaxy")
            sites = {s.kind: s for s in game.black_holes.sites}
            game.selected_system = sites["maw"].system_id
            def capture(name):
                app.render()
                app.present()
                pg.image.save(app.window, str(ROOT / "screenshots" / (name+".png")))
            capture("black_holes_mapped")

            target = game.systems[sites["maw"].system_id]
            home = game.systems[0]
            original = target.x, target.y
            target.x, target.y = home.x+6/140 if home.x < .9 else home.x-6/140, home.y
            app.open_map_fleet(1)
            app.send_map_fleet(target.id)
            capture("black_holes_warning")
            app.cancel_dialog()
            app.close_fleet_popup()
            target.x, target.y = original

            discover(game, "event_horizon_navigation")
            game.choose_research("ion_drives")
            app.go("galaxy")
            for kind, site in sites.items():
                game.selected_system = site.system_id
                capture("black_holes_"+kind)
            black_hole_view.open_navigation(app)
            capture("black_holes_research")
            app.go("galaxy")
            site = sites["maw"]
            game.selected_system = site.system_id
            for _ in range(8):
                game.ships.append(Ship(game.next_ship_id, "titan", site.system_id))
                game.next_ship_id += 1
            game.start_combat(site.system_id)
            app.go("combat")
            capture("black_holes_guardian")
            combat.autoresolve(game)
            assert game.combat.status == "player_victory"
            capture("black_holes_victory")
            game.finish_combat()
            app.go("galaxy")
            capture("black_holes_recovered")
            black_hole_view.open_guide(app, site.relic_id)
            capture("black_holes_collection")
        finally:
            app.audio.close()
            pg.quit()
    print("Rendered black-hole map, warning, research, guardian, victory and collection screens.")


if __name__ == "__main__":
    main()
