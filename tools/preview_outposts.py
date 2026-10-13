"""Reproduce the v0.58 portrait, production, outpost and combined-range screens."""
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
from orion.app import App, MAP
from orion.model import new_game, Ship
from orion import outposts, specialists, exploration


def main():
    output = ROOT/"screenshots"
    with tempfile.TemporaryDirectory() as folder:
        app = App(Path(folder), capture=True)
        try:
            game = app.game = new_game(seed=12, random_starts=False, with_ai=True, with_guardians=False,
                                       with_tombs=False, with_black_holes=False)
            game.credits = game.resources = 2000
            earth = game.planet_at(0, 2)
            earth.buildings.append("space_hub")
            for key in ("mara_voss", "orun_basalt"):
                person = specialists.person(game, key)
                person.visitor, person.system_id, person.planet_id, person.expires = "player", 0, 2, 7
            specialists.hire(game, "mara_voss")
            specialists.assign(game, "mara_voss", 0, 2)

            def capture(name):
                app.notice = ""
                app.render()
                pg.image.save(app.canvas, str(output/("v058_"+name+".png")))

            app.open_planet(2)
            app.open_specialists()
            app.specialist_set_tab("hired")
            app.specialist_select("mara_voss")
            capture("mara")
            app.specialist_set_tab("visitors")
            app.specialist_select("orun_basalt")
            capture("orun")
            app.go("planet")
            capture("leader_planet")
            app.open_production()
            capture("production")

            system = next(s for s in game.systems[1:] if s.worlds and not any(p.colonized for p in s.worlds))
            # Arrange a compact sample of overlapping coverage, independent of seed layout.
            home = game.systems[0]
            home.x, home.y = .42, .5
            system.x, system.y = .46, .5
            world = system.worlds[0]
            game.ships.append(Ship(game.next_ship_id, "outpost_ship", system.id))
            game.next_ship_id += 1
            exploration.refresh(game)
            game.selected_system = system.id
            app.open_planet(world.id)
            capture("deploy")
            outposts.deploy(game, game.next_ship_id-1, system.id, world.id)
            capture("outpost")
            app.go("galaxy")
            app.route_ship_id = 1
            app.map_camera.zoom = 2.5
            app.map_camera.center_on(.445, .5, MAP)
            capture("range")
            app.route_ship_id = None
            world.outpost_owner = "rival"
            game.ships.append(Ship(game.next_ship_id, "frigate", system.id))
            game.next_ship_id += 1
            app.open_planet(world.id)
            capture("attack")
        finally:
            app.audio.close()
            pg.quit()
    print(output)


if __name__ == "__main__":
    main()
