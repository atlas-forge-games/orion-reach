"""Capture the implemented galaxy palettes and their real Settings controls."""

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
from orion.exploration import record_survey, refresh
from orion.model import new_game


def demonstration():
    game = new_game(seed=804, rival_count=5, fog_of_war=True, with_tombs=False,
                    with_guardians=False, random_starts=False)
    home = game.systems[0]
    earth = home.worlds[2]
    earth.population = 12
    earth.farmers, earth.scientists, earth.miners = 4, 3, 2
    earth.buildings = ["factory", "research_lab", "mine", "solar_array", "hydroponic_farm"]
    game.credits, game.research, game.resources = 284, 42, 128
    nearby = sorted((s for s in game.systems[1:] if len(s.worlds) >= 2 and not any(p.colonized for p in s.worlds)),
                    key=lambda s: (s.x-home.x)**2 + (s.y-home.y)**2)
    for index, system in enumerate(nearby[:6]):
        owners = ("player", "rival") if index == 0 else (game.owners[index],)
        if index == 0:
            system.name = "Oberon"
        for world, owner in zip(system.worlds, owners):
            world.owner, world.colonized, world.population = owner, True, 5
            world.biome, world.farmers = "Terran", 2
    refresh(game)
    for system in game.systems:
        if system.id % 3 != 1 or any(p.colonized for p in system.worlds):
            record_survey(game, system.id, "player")
    game.selected_system, game.selected_planet = 0, 2
    return game


def main():
    with tempfile.TemporaryDirectory() as directory:
        app = App(Path(directory), capture=True)
        try:
            app.game = demonstration()
            for palette in ("blue", "turquoise"):
                app.set_galaxy_palette(palette)
                app.go("galaxy")
                app.render()
                app.present()
                pg.image.save(app.window, str(ROOT/"screenshots"/f"galaxy_saturated_{palette}.png"))
            app.set_galaxy_palette("blue")
            app.show_settings("pause")
            app.render()
            app.present()
            pg.image.save(app.window, str(ROOT/"screenshots"/"galaxy_color_settings.png"))
        finally:
            app.audio.close()
            pg.quit()
    print("Rendered both galaxy palettes and the Settings screen.")


if __name__ == "__main__":
    main()
