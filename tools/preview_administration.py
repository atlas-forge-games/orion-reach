"""Reproduce v0.59's capital, distant colony and settlement preview screens."""
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
from orion.model import new_game, Ship
from orion import exploration, specialists


def main():
    output = ROOT/"screenshots"
    with tempfile.TemporaryDirectory() as folder:
        app = App(Path(folder), capture=True)
        try:
            game = app.game = new_game(seed=12, random_starts=False, with_ai=False,
                                       with_guardians=False, with_tombs=False, with_black_holes=False,
                                       fog_of_war=False)
            game.turn, game.year = 25, 2324
            game.resources = game.credits = 2000
            systems = [s for s in game.systems[1:] if s.worlds][:6]
            for i, system in enumerate(systems[:5]):
                system.x, system.y = game.systems[0].x+(7+i*5.25)/140, game.systems[0].y
                planet = system.worlds[0]
                planet.biome = "Terran"
                ship = Ship(game.next_ship_id, "colony_ship", system.id)
                game.next_ship_id += 1
                game.ships.append(ship)
                game.colonize(ship.id, system.id, 0)
                planet.population, planet.farmers, planet.scientists, planet.miners = 12, 5, 2, 2
                planet.buildings = ["factory", "research_lab", "mine"]
            for system in systems[:2]:
                del game.system_integration["player"][str(system.id)]
            home = game.planet_at(0, 2)
            home.buildings = ["factory", "research_lab", "mine", "space_hub"]
            person = specialists.person(game, "mara_voss")
            person.visitor, person.system_id, person.planet_id, person.expires = "player", 0, 2, 30
            specialists.hire(game, "mara_voss")
            specialists.assign(game, "mara_voss", 0, 2)
            exploration.refresh(game)

            def capture(name):
                app.notice = ""
                app.render()
                pg.image.save(app.canvas, str(output/("v059_"+name+".png")))

            game.selected_system = 0
            app.open_planet(2)
            capture("capital")
            game.selected_system = systems[4].id
            app.open_planet(0)
            capture("frontier")
            app.open_production()
            capture("production")
            system = systems[5]
            system.x, system.y = game.systems[0].x+21/140, game.systems[0].y
            system.worlds[0].biome = "Terran"
            game.ships.append(Ship(game.next_ship_id, "colony_ship", system.id))
            game.next_ship_id += 1
            exploration.refresh(game)
            game.selected_system = system.id
            app.open_planet(0)
            app.colonize_request()
            capture("settlement")
        finally:
            app.audio.close()
            pg.quit()
    print(output)


if __name__ == "__main__":
    main()
