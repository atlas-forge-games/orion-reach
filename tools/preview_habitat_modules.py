"""Reproduce module screens using the normal renderer and Space Hub rules."""
import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pygame as pg
from orion.app import App
from orion.model import new_game
from orion import motherships, specialists
from orion.buildings import BUILDINGS
from orion.habitat_modules import MODULE_NAMES, display_name
from orion.building_art import draw_building_art
from orion.ui import INK, GOLD, MUTED, panel, text, wrapped_lines


def run():
    output = ROOT/'screenshots'
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        app = App(Path(folder), capture=True)
        try:
            app.game = game = new_game('Cities of the Stars', seed=12, race_id='wanderers',
                random_starts=False, with_ai=False, with_guardians=False,
                with_tombs=False, with_black_holes=False)
            ship = motherships.homes(game)[0]
            home = ship.habitat
            home.population = 24
            home.farmers, home.scientists, home.miners = 8, 4, 4
            home.buildings = ['hydroponic_farm', 'factory', 'research_lab', 'mine', 'solar_array', 'space_hub']
            home.construction_queue.clear()
            game.resources, game.credits = 1200, 1500
            game.queue_building(ship.system_id, home.id, 'trade_center')
            specialists.advance_visitors(game)
            app.open_mothership(ship.id)

            def capture(name):
                app.notice, app.dialog = '', None
                app.render()
                pg.image.save(app.canvas, str(output/f'v0661_{name}.png'))

            capture('mothership_modules')
            app.inspect_surface_building(1)
            capture('module_management')
            app.open_production()
            capture('module_construction')
            app.go('planet')
            app.inspect_surface_building(5)
            capture('space_hub')

            app.canvas.fill((6, 15, 24))
            text(app.canvas, 'MOTHERSHIP MODULES', (32, 22), 28, GOLD, 'title')
            for i, identifier in enumerate(MODULE_NAMES):
                x, y = 28+(i%5)*280, 80+(i//5)*200
                panel(app.canvas, (x, y, 264, 184))
                draw_building_art(app.canvas, identifier, (x+55, y+8, 154, 116), habitat=True)
                for line, value in enumerate(wrapped_lines(display_name(BUILDINGS[identifier], True), 240, 15)):
                    text(app.canvas, value, (x+12, y+132+line*19), 15, INK)
            text(app.canvas, 'Shared facility costs and effects · Advanced modules retain tier markers', (32, 875), 12, MUTED)
            pg.image.save(app.canvas, str(output/'v0661_module_art_catalogue.png'))
        finally:
            app.audio.close()
            pg.quit()


if __name__ == '__main__':
    run()
