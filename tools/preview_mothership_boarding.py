"""Render the real mothership art, combat defenses and boarding controls."""
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
from orion.model import new_game, Ship
from orion import motherships, combat, exploration


def run():
    with tempfile.TemporaryDirectory() as folder:
        app = App(Path(folder), capture=True)
        try:
            def capture(name):
                app.dialog = None
                app.notice = ''
                app.render()
                pg.image.save(app.canvas, str(ROOT/'screenshots'/('v066_'+name+'.png')))

            app.game = game = new_game('Cities of the Stars', seed=12, race_id='wanderers',
                with_ai=True, rival_race_id='terran', random_starts=False, with_guardians=False, with_tombs=False, with_black_holes=False)
            home = motherships.homes(game)[0]
            home.habitat.population = 24
            home.habitat.farmers, home.habitat.scientists, home.habitat.miners = 6, 4, 4
            home.habitat.buildings = ['hydroponic_farm', 'factory', 'research_lab', 'mine', 'solar_array', 'space_hub']
            home.habitat.trade_goods = True
            app.open_mothership(home.id)
            capture('mothership_home')
            app.open_system(home.system_id)
            capture('mothership_system')
            enemy = Ship(game.next_ship_id, 'frigate', home.system_id, owner='rival')
            game.next_ship_id += 1
            game.ships.append(enemy)
            game.start_combat(home.system_id, target='rival')
            app.reset_combat_view()
            app.go('combat')
            app.combat_ship_id = home.id
            app.combat_target_id = enemy.id
            capture('mothership_defenses')

            app.game = game = new_game('Boarding the Ark', seed=12, race_id='varkesh', rival_race_id='wanderers',
                with_ai=True, random_starts=False, with_guardians=False, with_tombs=False, with_black_holes=False)
            home = motherships.homes(game, 'rival')[0]
            motherships.create(game, home.system_id, 'rival')
            home.system_id = 0
            home.habitat.population = 30
            home.habitat.farmers = 8
            home.habitat.buildings = ['hydroponic_farm', 'factory', 'research_lab', 'mine', 'solar_array', 'space_hub']
            for kind in ['frigate']+['troop_transport']*8:
                game.ships.append(Ship(game.next_ship_id, kind, 0))
                game.next_ship_id += 1
            exploration.refresh(game)
            game.start_combat(0, target='rival')
            unit = game.combat.ship(home.id)
            unit.hull = unit.shields = 0
            combat.check_losses(game)
            game.finish_combat()
            app.open_mothership(home.id)
            capture('disabled_mothership')
            app.mothership_action_request(home.id, 'capture')
            capture('boarding_plan')
            app.close_ground()
            app.mothership_action_request(home.id, 'raid')
            app.launch_ground_assault()
            capture('raid_report')
        finally:
            app.audio.close()
            pg.quit()


if __name__ == '__main__':
    run()
